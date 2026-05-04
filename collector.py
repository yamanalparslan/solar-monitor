"""
Solar Monitor - Senkron Veri Toplayici
=======================================
Bu dosya test uyumlulugu icin korunmaktadir.
Uretim ortaminda collector_async.py kullanin.

Degisiklikler:
  - build_metric_candidates() eklendi (test_collector.py uyumlulugu)
  - read_device() guncellendi: her metrik icin holding+input+blok okuma denenir
  - to_signed16 kullanilir (voltaj/akim negatif olabilir)
  - decode_temperature_register kullanilir (otomatik scale)
  - Guc=0 ve V,A gecerliyse P=V*I hesaplanir
  - Tum degerler sifirsa None doner
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
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass


def load_config(fabrika_id: str = "mekanik") -> dict:
    ayarlar = veritabani.tum_ayarlari_oku(fabrika_id)
    
    # Fabrikaya özel IP ve ID'leri .env dosyasından okuyoruz
    env_key = f"TARGET_DEVICES_{fabrika_id.upper()}"
    target_devices_raw = os.getenv(env_key)
    
    if not target_devices_raw:
        # Eğer özel .env bulunamazsa veritabanındaki varsayılanlara dön
        eski_ip = ayarlar.get("target_ip", "10.35.14.10")
        eski_ids = ayarlar.get("slave_ids", "1")
        target_devices_raw = f"{eski_ip}:{eski_ids}"

    target_devices = []
    for part in target_devices_raw.split(";"):
        part = part.strip()
        if not part: continue
        if ":" in part:
            ip, ids_str = part.split(":", 1)
            ids = [int(i.strip()) for i in ids_str.split(",") if i.strip().isdigit()]
            target_devices.append({"ip": ip.strip(), "slave_ids": ids})
        else:
            target_devices.append({"ip": part.strip(), "slave_ids": [1]})

    webhook_enabled = os.getenv("WEBHOOK_ENABLED", "false").lower() == "true"
    webhook_url = os.getenv("WEBHOOK_URL", "")
    webhook_api_key = os.getenv("WEBHOOK_API_KEY", "")
    webhook_daily_time = os.getenv("WEBHOOK_DAILY_TIME", "23:50")

    return {
        "target_devices": target_devices,
        "target_port":    int(ayarlar.get("target_port", 502)),
        "refresh_rate":   float(ayarlar.get("refresh_rate", 60)),
        "webhook_enabled": webhook_enabled,
        "webhook_url":     webhook_url,
        "webhook_api_key": webhook_api_key,
        "webhook_daily_time": webhook_daily_time,
        "guc_addr":       int(os.getenv("GUC_ADDR", ayarlar.get("guc_addr", 93))),
        "volt_addr":      int(os.getenv("VOLT_ADDR", ayarlar.get("volt_addr", 29))),
        "akim_addr":      int(os.getenv("AKIM_ADDR", ayarlar.get("akim_addr", 26))),
        "isi_addr":       int(os.getenv("ISI_ADDR", ayarlar.get("isi_addr", 44))),
        "guc_scale":      float(ayarlar.get("guc_scale", 1.0)),
        "volt_scale":     float(ayarlar.get("volt_scale", 1.0)),
        "akim_scale":     float(ayarlar.get("akim_scale", 0.1)),
        "isi_scale":      float(ayarlar.get("isi_scale", 1.0)),
        "veri_saklama_gun": int(ayarlar.get("veri_saklama_gun", 365)),
        "alarm_registers": [
            {"addr": 107, "key": "hata_kodu",     "count": 2},
            {"addr": 109, "key": "hata_kodu_109", "count": 2},
            {"addr": 111, "key": "hata_kodu_111", "count": 1},
            {"addr": 112, "key": "hata_kodu_112", "count": 2},
            {"addr": 114, "key": "hata_kodu_114", "count": 1},
            {"addr": 115, "key": "hata_kodu_115", "count": 1},
            {"addr": 116, "key": "hata_kodu_116", "count": 1},
            {"addr": 117, "key": "hata_kodu_117", "count": 1},
            {"addr": 118, "key": "hata_kodu_118", "count": 1},
            {"addr": 119, "key": "hata_kodu_119", "count": 1},
            {"addr": 120, "key": "hata_kodu_120", "count": 1},
            {"addr": 121, "key": "hata_kodu_121", "count": 1},
            {"addr": 122, "key": "hata_kodu_122", "count": 1},
        ],
    }


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

            if val_guc <= 0 and val_volt > 0 and val_akim > 0:
                val_guc = round(val_volt * val_akim, 2)

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
            alarm_count = (alarm_end - alarm_start) + 1

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
                            veriler[reg["key"]] = (alarm_regs[offset] << 16) | alarm_regs[offset + 1]
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

def start_daily_webhook_thread():
    def _daily_task():
        from veritabani import FABRIKALAR, gunluk_uretim_hesapla, tarih_araliginda_ortalamalar, hata_sayilarini_getir
        while True:
            now = datetime.datetime.now()
            config = load_config("mekanik")
            
            if config.get("webhook_enabled") and config.get("webhook_url"):
                target_time = config.get("webhook_daily_time", "23:50").split(":")
                if len(target_time) == 2 and now.hour == int(target_time[0]) and now.minute == int(target_time[1]):
                    today_str = now.strftime('%Y-%m-%d')
                    
                    for fab_id in FABRIKALAR:
                        fab_config = load_config(fab_id)
                        for device in fab_config["target_devices"]:
                            ip = device["ip"]
                            for slave_id in device["slave_ids"]:
                                try:
                                    base_dev_id = int(ip.split(".")[-1])
                                    dev_id = base_dev_id if slave_id == 1 else int(f"{base_dev_id}{slave_id}")
                                    
                                    uretim = gunluk_uretim_hesapla(today_str, slave_id=dev_id, fabrika_id=fab_id) or {}
                                    ortalama = tarih_araliginda_ortalamalar(today_str, today_str, slave_id=dev_id, fabrika_id=fab_id) or {}
                                    hatalar = hata_sayilarini_getir(today_str, today_str, slave_id=dev_id, fabrika_id=fab_id) or {}
                                    
                                    payload = {
                                        "tarih": today_str,
                                        "fabrika_id": fab_id,
                                        "device_id": dev_id,
                                        "ip_address": ip,
                                        "ozet": {
                                            "toplam_uretim_kwh": uretim.get("uretim_kwh", 0),
                                            "calisma_suresi_saat": uretim.get("calisma_suresi_saat", 0),
                                            "ortalama_sicaklik": round(ortalama.get("ort_sicaklik", 0) or 0, 2),
                                            "max_guc": round(ortalama.get("max_guc", 0) or 0, 2),
                                            "toplam_hata_sayisi": hatalar.get("hata_107_sayisi", 0) or 0
                                        }
                                    }
                                    
                                    headers = {"Content-Type": "application/json"}
                                    if config.get("webhook_api_key"):
                                        headers["Authorization"] = f"Bearer {config['webhook_api_key']}"
                                    
                                    response = requests.post(config["webhook_url"], json=payload, headers=headers, timeout=10)
                                    response.raise_for_status()
                                    logging.info(f"[WEBHOOK] Gunluk ozet gonderildi: Fabrika {fab_id}, Cihaz {dev_id}")
                                except Exception as e:
                                    logging.error(f"Gunluk webhook hatasi (Cihaz {dev_id}): {e}")
                    
                    time.sleep(65)
            time.sleep(30)

    thread = threading.Thread(target=_daily_task, daemon=True)
    thread.start()


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

    while True:
        baslangic = time.time()
        refresh_rate = 60 

        for fab_id in FABRIKALAR:
            config = load_config(fab_id)
            port = config["target_port"]
            refresh_rate = config["refresh_rate"]

            for device in config["target_devices"]:
                ip = device["ip"]
                for slave_id in device["slave_ids"]:
                    try:
                        base_dev_id = int(ip.split(".")[-1])
                    except ValueError:
                        base_dev_id = 1
                    
                    if slave_id == 1:
                        dev_id = base_dev_id
                    else:
                        dev_id = int(f"{base_dev_id}{slave_id}")
                    
                    print(f"[{fab_id.upper()}] IP {ip} ID {slave_id} (DevID: {dev_id})...", end=" ", flush=True)
                    time.sleep(0.5)

                    client_key = f"{ip}:{port}"
                    if client_key not in clients:
                        clients[client_key] = ModbusTcpClient(ip, port=port, timeout=3.0)
                    
                    client = clients[client_key]

                    data = read_device(client, slave_id, config, max_retries=3)
                    if data:
                        veritabani.veri_ekle(dev_id, data, fabrika_id=fab_id)

                        hata_kodlari = [data.get(f"hata_kodu_{r}", 0) for r in [107,109,111,112,114,115,116,117,118,119,120,121,122]]
                        hata_kodlari[0] = data.get("hata_kodu", 0)
                        durum = "TEMIZ" if all(h == 0 for h in hata_kodlari) else "HATA"
                        print(f"[OK] {durum}")
                    else:
                        print("[YOK]")

        temizlik_sayaci += 1
        if temizlik_sayaci * refresh_rate >= TEMIZLIK_PERIYODU:
            for fab_id in FABRIKALAR:
                otomatik_veri_temizle(load_config(fab_id))
            temizlik_sayaci = 0

        _notify_websocket()

        gecen = time.time() - baslangic
        time.sleep(max(0, refresh_rate - gecen))

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    start_collector()