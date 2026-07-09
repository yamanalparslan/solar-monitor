"""
Solar Monitor - Senkron Veri Toplayici
=======================================
Bu dosya test uyumlulugu icin korunmaktadir.
Uretim ortaminda collector_async.py kullanin.

NOT: Konfigurasyon ve webhook mantigi collector_config.py modülünde
     merkezilestirilerek kod tekrari giderilmistir.
"""

import logging
import os
import time
import sys
import io
import datetime
import threading
import requests

from pymodbus.client import ModbusTcpClient

import utils
import veritabani

# UTF-8 stdout (Windows uyumlulugu)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

WS_NOTIFY_URL = os.getenv("WS_NOTIFY_URL", "http://solar_api:8503/ws/notify")

def _notify_websocket():
    """Collector veri yazdiktan sonra API'ye bildirim gonderir."""
    try:
        import urllib.request
        req = urllib.request.Request(WS_NOTIFY_URL, data=b"", method="POST")
        req.add_header("Content-Type", "application/json")
        api_key = os.getenv("CRM_API_KEY", "")
        if api_key:
            req.add_header("x-api-key", api_key)
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass


# ── Paylasilan konfigurasyon modülünden import et (DRY prensibi) ──
from collector_config import load_config, start_daily_webhook_thread  # noqa: F401


# ─────────────────────────────────────────────
# Modbus Okuma Stratejisi
# ─────────────────────────────────────────────

def build_metric_candidates(start_addr: int, is_32bit: bool = False) -> list:
    """
    Tek bir register adresi icin denenecek (func, addr, count, offset) adaylarini uretir.
    32-bit (2 register) okuma destegi eklenmistir.
    """
    candidates = []
    read_count = 2 if is_32bit else 1

    # Tekil okumalar
    candidates.append(("holding", start_addr, read_count, 0))
    candidates.append(("input",   start_addr, read_count, 0))

    # Blok okumalar (geriden ileri)
    max_lookback = min(4, start_addr + 1)
    for block_offset in range(max_lookback):
        block_start = start_addr - block_offset
        if block_start >= 0:
            # 32-bit okunacaksa blok boyutu offset'i ve 2 register'i kapsamalidir
            block_size = max(4, block_offset + read_count)
            candidates.append(("input",   block_start, block_size, block_offset))
            candidates.append(("holding", block_start, block_size, block_offset))

    return candidates


def _sync_read_registers(client, func: str, address: int, count: int, slave_id: int):
    """Senkron register okur. Hata durumunda None doner."""
    try:
        time.sleep(0.05)
        if func == "holding":
            rr = client.read_holding_registers(address=address, count=count, slave=slave_id)
        else:
            rr = client.read_input_registers(address=address, count=count, slave=slave_id)

        if getattr(rr, "isError", lambda: True)():
            return None
        regs = getattr(rr, "registers", None)
        return regs if regs else None
    except Exception:
        return None


def _try_read_metric_sync(client, addr: int, slave_id: int, is_32bit: bool = False) -> tuple:
    """
    Bir metrik adresi icin tum adaylari sirayla dener.
    is_32bit True ise, 2 adet 16-bit register okuyup birlestirir.
    Returns: (raw_value, func_adi) veya (None, None)
    """
    for func, address, count, offset in build_metric_candidates(addr, is_32bit):
        regs = _sync_read_registers(client, func, address, count, slave_id)
        if regs is not None:
            if is_32bit and len(regs) >= (offset + 2):
                # 32-bit okuma: Iki register'i birlestir (High-Word, Low-Word)
                combined_value = (regs[offset] << 16) | regs[offset + 1]
                return combined_value, func
            elif not is_32bit and len(regs) > offset:
                # 16-bit okuma
                return regs[offset], func
    return None, None


def read_device(client, slave_id: int, config: dict, max_retries: int = 3):
    """
    Senkron Modbus okuma (Dinamik Blok Okuma).
    .env dosyasına girilen adres aralıklarını otomatik hesaplar ve tek seferde okur.
    """
    for attempt in range(max_retries):
        try:
            if not client.connected:
                client.connect()
                time.sleep(0.1)

            # ── 1. ADIM: TEMEL METRİKLERİ DİNAMİK BLOK OLARAK OKU ──
            # Ayarlardaki adreslerin en küçüğünü ve en büyüğünü bul
            metrik_adresleri = [
                config["akim_addr"], 
                config["volt_addr"], 
                config["guc_addr"], 
                config["isi_addr"]
            ]
            start_addr = min(metrik_adresleri)
            end_addr = max(metrik_adresleri)
            
            # Aradaki fark kadar register oku (+1 dahil etmek için)
            count = (end_addr - start_addr) + 1 
            
            time.sleep(0.05)
            rr_temel = client.read_holding_registers(address=start_addr, count=count, slave=slave_id)
            
            if getattr(rr_temel, "isError", lambda: True)():
                continue  
            
            regs = rr_temel.registers

            if len(regs) < count:
                continue
            
            # Değerleri diziden dinamik ofset hesaplayarak al (Güvenli yöntem)
            raw_akim = regs[config["akim_addr"] - start_addr]
            raw_volt = regs[config["volt_addr"] - start_addr]
            raw_guc  = regs[config["guc_addr"] - start_addr]
            raw_isi  = regs[config["isi_addr"] - start_addr]

            # ── Değer Dönüşümleri ──
            val_volt = utils.to_signed16(raw_volt) * config["volt_scale"]
            val_akim = utils.to_signed16(raw_akim) * config["akim_scale"]
            val_guc  = utils.to_signed16(raw_guc)  * config["guc_scale"]
            val_isi  = utils.decode_temperature_register(raw_isi, config["isi_scale"])

            # Eğer inverter gücü 0 gönderiyorsa, volt * akım hesabı ile sahte güç üretilmesini engelledik.
            # Bu sayede Modbus'ta 0 ise panelde de tam olarak 0 görünür.

            if val_volt == 0 and val_akim == 0 and val_guc == 0 and val_isi == 0:
                return None

            print(
                f"  [ID {slave_id}] "
                f"V={val_volt:.1f}V  A={val_akim:.2f}A  G={val_guc:.1f}W  T={val_isi:.1f}C"
            )

            veriler = {
                "guc":      val_guc,
                "voltaj":   val_volt,
                "akim":     val_akim,
                "sicaklik": val_isi,
            }

            # ── 2. ADIM: ALARMLARI DİNAMİK BLOK OLARAK OKU ──
            # Alarm adreslerinin sınırlarını bul
            alarm_adresleri = [reg["addr"] for reg in config["alarm_registers"]]
            if not alarm_adresleri:
                return veriler

            alarm_start = min(alarm_adresleri)
            alarm_end = max(alarm_adresleri) + 1 # count=2 olanlar için +1 ekliyoruz
            alarm_count = alarm_end - alarm_start

            time.sleep(0.05)
            rr_alarm = client.read_holding_registers(address=alarm_start, count=alarm_count, slave=slave_id)
            
            if not getattr(rr_alarm, "isError", lambda: True)():
                alarm_regs = rr_alarm.registers
                for reg in config["alarm_registers"]:
                    a_addr = reg["addr"]
                    a_count = reg.get("count", 2)
                    offset = a_addr - alarm_start
                    
                    if offset >= 0 and (offset + a_count) <= len(alarm_regs):
                        if a_count == 2:
                            veriler[reg["key"]] = (alarm_regs[offset + 1] << 16) | alarm_regs[offset]
                        else:
                            veriler[reg["key"]] = alarm_regs[offset]
                    else:
                        veriler[reg["key"]] = 0
            else:
                for reg in config["alarm_registers"]:
                    veriler[reg["key"]] = 0

            return veriler

        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                try: client.close()
                except: pass
                continue
            logging.error("ID %d okuma hatasi (deneme %d): %s", slave_id, attempt + 1, exc)
            return None

def otomatik_veri_temizle(config: dict) -> int:
    saklama_gun = config.get("veri_saklama_gun", 365)
    if saklama_gun == 0:
        return 0
    try:
        silinen = veritabani.eski_verileri_temizle(saklama_gun)
        if silinen > 0:
            print(f"\nOtomatik Temizlik: {silinen} kayit silindi")
        return silinen
    except Exception:
        return 0

# start_daily_webhook_thread → collector_config.py'den re-export edildi


def start_collector():
    """Senkron collector baslangici (geriye donuk uyumluluk / test)."""
    veritabani.init_db()
    print("=" * 60)
    print("COLLECTOR BASLATILDI (Multi-IP Senkron Modu)")
    print("NOT: Uretim icin collector_async.py kullanin!")
    print("=" * 60)

    from veritabani import FABRIKALAR

    temizlik_sayaci = 0
    TEMIZLIK_PERIYODU = 1800

    clients = {}
    
    # Günlük özet gönderim servisini başlat
    start_daily_webhook_thread()

    fab_configs = {}
    for fab_id in FABRIKALAR:
        fab_configs[fab_id] = load_config(fab_id)

    last_config_update = time.time()

    while True:
        baslangic = time.time()
        refresh_rate = 60 
        
        if time.time() - last_config_update > 30:
            for fab_id in FABRIKALAR:
                fab_configs[fab_id] = load_config(fab_id)
            last_config_update = time.time()

        for fab_id in FABRIKALAR:
            config = fab_configs[fab_id]
            port = config["target_port"]
            refresh_rate = config["refresh_rate"]

            for device in config["target_devices"]:
                ip = device["ip"]
                for slave_id in device["slave_ids"]:
                    dev_id = slave_id
                    
                    print(f"[{fab_id.upper()}] IP {ip} ID {slave_id} (DevID: {dev_id})...", end=" ", flush=True)
                    time.sleep(0.5)

                    client_key = f"{ip}:{port}"
                    if client_key not in clients:
                        clients[client_key] = ModbusTcpClient(ip, port=port, timeout=3.0)
                    
                    client = clients[client_key]

                    data = read_device(client, slave_id, config, max_retries=3)
                    if data:
                        save_id = dev_id
                        if fab_id == "uretim":
                            if save_id == 1:
                                save_id = 2
                            elif save_id == 2:
                                save_id = 1
                        veritabani.veri_ekle(save_id, data, fabrika_id=fab_id)

                        hata_kodlari = [data.get(f"hata_kodu_{r}", 0) for r in [107,109,111,112,114,115,116,117,118,119,120,121,122]]
                        hata_kodlari[0] = data.get("hata_kodu", 0)
                        durum = "TEMIZ" if all(h == 0 for h in hata_kodlari) else "HATA"
                        print(f"[OK] {durum}")
                    else:
                        print("[YOK]")

        temizlik_sayaci += 1
        if temizlik_sayaci * refresh_rate >= TEMIZLIK_PERIYODU:
            for fab_id in FABRIKALAR:
                otomatik_veri_temizle(fab_configs[fab_id])
            temizlik_sayaci = 0

        _notify_websocket()

        gecen = time.time() - baslangic
        time.sleep(max(0, refresh_rate - gecen))

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    start_collector()