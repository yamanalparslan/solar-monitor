"""
Solar Monitor - Birlesik Asenkron Veri Toplayici (Ana Collector)
=================================================================
collector.py'nin tum ozelliklerini icerir + AsyncModbus mimarisi.
Bu dosya artik tek ve ana collector olarak kullanilir.

Modbus Veri Kalitesi Duzeltmeleri:
    - Dinamik Blok Okuma: Metrik ve alarmlari tek paket halinde okur (Modbus Poll mantigi)
    - to_signed16: voltaj/akim negatif olabilir, signed cevirme zorunlu
    - decode_temperature_register: otomatik scale tespiti
"""

import asyncio
import datetime
import io
import logging
import os
import sys
import threading
import time

import requests

import utils
import veritabani
from config import setup_logging
from pymodbus.client import AsyncModbusTcpClient

# UTF-8 stdout (Windows uyumlulugu)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

logger = setup_logging("collector_async")

WS_NOTIFY_URL = os.getenv("WS_NOTIFY_URL", "http://solar_api:8503/ws/notify")


# ─────────────────────────────────────────────
# WebSocket Bildirimi
# ─────────────────────────────────────────────

def _ws_notify_sync():
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


async def _notify_websocket():
    """Async sarmalayici - bloklamamak icin executor'da calistirir."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _ws_notify_sync)


# ─────────────────────────────────────────────
# Konfigurasyon
# ─────────────────────────────────────────────

# ── Paylasilan konfigurasyon modülünden import et (DRY prensibi) ──
from collector_config import load_config, start_daily_webhook_thread  # noqa: F401


# ─────────────────────────────────────────────
# Cihaz Okuma (Dinamik Blok Okuma - Async)
# ─────────────────────────────────────────────

async def read_device_async(
    client: AsyncModbusTcpClient, dev_id: int, ip_address: str, slave_id: int, config: dict
) -> tuple:
    """
    Tek bir inverter cihazindan tum verileri asenkron ve dinamik blok okuma ile alir.
    """
    try:
        if not client.connected:
            await client.connect()
            await asyncio.sleep(0.1)

        # ── 1. ADIM: TEMEL METRIKLERI DINAMIK BLOK OLARAK OKU ──
        metrik_adresleri = [
            config["akim_addr"],
            config["volt_addr"],
            config["guc_addr"],
            config["isi_addr"],
            config["uretim_addr"]
        ]
        start_addr = min(metrik_adresleri)
        end_addr = max(metrik_adresleri)
        count = (end_addr - start_addr) + 1

        await asyncio.sleep(0.05)
        rr_temel = await client.read_holding_registers(address=start_addr, count=count, slave=slave_id)
        
        if rr_temel.isError():
            # Input register denemesi (fallback)
            rr_temel = await client.read_input_registers(address=start_addr, count=count, slave=slave_id)
            if rr_temel.isError():
                return dev_id, ip_address, slave_id, None

        regs = rr_temel.registers
        
        raw_akim = regs[config["akim_addr"] - start_addr]
        raw_volt = regs[config["volt_addr"] - start_addr]
        raw_guc  = regs[config["guc_addr"] - start_addr]
        raw_isi  = regs[config["isi_addr"] - start_addr]
        raw_uretim = regs[config["uretim_addr"] - start_addr]

        # ── Deger Donusumleri ──
        val_volt = utils.to_signed16(raw_volt) * config["volt_scale"]
        val_akim = utils.to_signed16(raw_akim) * config["akim_scale"]
        val_guc  = utils.to_signed16(raw_guc)  * config["guc_scale"]
        val_isi  = utils.decode_temperature_register(raw_isi, config["isi_scale"])
        val_uretim = float(raw_uretim) * config["uretim_scale"]

        if val_guc <= 0 and val_volt > 0 and val_akim > 0:
            val_guc = round(val_volt * val_akim, 2)

        if val_volt == 0 and val_akim == 0 and val_guc == 0 and val_isi == 0:
            return dev_id, ip_address, slave_id, None

        veriler = {
            "guc":      val_guc,
            "voltaj":   val_volt,
            "akim":     val_akim,
            "sicaklik": val_isi,
            "modbus_uretim": val_uretim,
        }

        # ── 2. ADIM: ALARMLARI DINAMIK BLOK OLARAK OKU ──
        if config["alarm_registers"]:
            alarm_start = min(reg["addr"] for reg in config["alarm_registers"])
            max_reg = max(config["alarm_registers"], key=lambda r: r["addr"])
            alarm_count = (max_reg["addr"] + max_reg.get("count", 2)) - alarm_start

            await asyncio.sleep(0.05)
            rr_alarm = await client.read_holding_registers(address=alarm_start, count=alarm_count, slave=slave_id)
            
            if not rr_alarm.isError():
                alarm_regs = rr_alarm.registers
                for reg in config["alarm_registers"]:
                    a_addr = reg["addr"]
                    a_count = reg.get("count", 2)
                    offset = a_addr - alarm_start
                    
                    if offset >= 0 and (offset + a_count) <= len(alarm_regs):
                        if a_count == 2:
                            # Inverters usually map the first register to bits 0-15 and the second to bits 16-31 for alarms
                            veriler[reg["key"]] = (alarm_regs[offset + 1] << 16) | alarm_regs[offset]
                        else:
                            veriler[reg["key"]] = alarm_regs[offset]
                    else:
                        veriler[reg["key"]] = 0
            else:
                for reg in config["alarm_registers"]:
                    veriler[reg["key"]] = 0

        return dev_id, ip_address, slave_id, veriler

    except Exception as exc:
        logger.error("IP %s ID %d baglanti/okuma hatasi: %s", ip_address, slave_id, exc)
        return dev_id, ip_address, slave_id, None


# ─────────────────────────────────────────────
# Veri Temizleme
# ─────────────────────────────────────────────

def otomatik_veri_temizle(config: dict) -> int:
    saklama_gun = config.get("veri_saklama_gun", 365)
    if saklama_gun == 0:
        return 0
    try:
        silinen = veritabani.eski_verileri_temizle(saklama_gun)
        if silinen > 0:
            logger.info("Otomatik temizlik: %d eski kayit silindi", silinen)
        return silinen
    except Exception:
        return 0


# ─────────────────────────────────────────────
# Ana Dongu
# ─────────────────────────────────────────────

# start_daily_webhook_thread → collector_config.py'den re-export edildi


async def main_loop():
    """
    Tum fabrikalari asenkron tarar.
    """
    veritabani.init_db()
    from veritabani import FABRIKALAR

    print("=" * 65)
    print("ASENKRON COLLECTOR BASLATILDI - Dinamik Blok Okuma Modu")
    print("=" * 65)

    # Günlük özet gönderim servisini başlat
    start_daily_webhook_thread()

    fab_configs: dict = {}
    clients: dict = {}

    for fab_id, fab_info in FABRIKALAR.items():
        cfg = load_config(fab_id)
        fab_configs[fab_id] = cfg
        print(f"  {fab_info['ikon']} {fab_info['ad']} Config Yuklendi.")

    print("=" * 65)

    temizlik_sayaci = 0
    TEMIZLIK_PERIYODU = 1800
    last_config_update = time.time()

    while True:
        dongu_baslangic = time.time()
        tasks = []
        task_info = []
        
        # 30 saniyede bir veritabanindan ayarlari tazele
        if time.time() - last_config_update > 30:
            for fab_id in FABRIKALAR:
                fab_configs[fab_id] = load_config(fab_id)
            last_config_update = time.time()

        for fab_id in FABRIKALAR:
            cfg = fab_configs[fab_id]
            port = cfg["target_port"]

            for device in cfg["target_devices"]:
                ip = device["ip"]
                client_key = f"{ip}:{port}"
                
                if client_key not in clients:
                    clients[client_key] = AsyncModbusTcpClient(ip, port=port, timeout=3.0)
                client = clients[client_key]
                
                for slave_id in device["slave_ids"]:
                    dev_id = slave_id
                    
                    tasks.append(read_device_async(client, dev_id, ip, slave_id, cfg))
                    task_info.append(fab_id)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            fab_id = task_info[i]
            if isinstance(result, Exception):
                logger.error("Gorev istisnasi: %s", result)
                continue

            dev_id, ip_address, slave_id, data = result
            if data:
                veritabani.veri_ekle(dev_id, data, fabrika_id=fab_id)
                hata_var = data.get("hata_kodu", 0) != 0 or any(
                    data.get(f"hata_kodu_{r}", 0) != 0
                    for r in [109, 111, 112, 114, 115, 116, 117, 118, 119, 120, 121, 122]
                )
                durum = "[HATA]" if hata_var else "[TEMIZ]"
                print(
                    f"[{fab_id.upper()}] IP {ip_address} ID {slave_id} (DevID: {dev_id}) | "
                    f"G={data['guc']:.1f}W  V={data['voltaj']:.1f}V  "
                    f"A={data['akim']:.2f}A  T={data['sicaklik']:.1f}C  "
                    f"{durum}"
                )
            else:
                print(f"[{fab_id.upper()}] IP {ip_address} ID {slave_id} (DevID: {dev_id}) | [CEVAP YOK]")

        temizlik_sayaci += 1
        min_refresh = min((c["refresh_rate"] for c in fab_configs.values()), default=60)
        if temizlik_sayaci * min_refresh >= TEMIZLIK_PERIYODU:
            for fab_id in FABRIKALAR:
                otomatik_veri_temizle(fab_configs[fab_id])
            temizlik_sayaci = 0

        await _notify_websocket()

        gecen = time.time() - dongu_baslangic
        await asyncio.sleep(max(1.0, min_refresh - gecen))


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nAsenkron Collector durduruldu.")
