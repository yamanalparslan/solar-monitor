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
            config["isi_addr"]
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

        # ── Deger Donusumleri ──
        val_volt = utils.to_signed16(raw_volt) * config["volt_scale"]
        val_akim = utils.to_signed16(raw_akim) * config["akim_scale"]
        val_guc  = utils.to_signed16(raw_guc)  * config["guc_scale"]
        val_isi  = utils.decode_temperature_register(raw_isi, config["isi_scale"])

        if val_guc <= 0 and val_volt > 0 and val_akim > 0:
            val_guc = round(val_volt * val_akim, 2)

        veriler = {
            "guc":      val_guc,
            "voltaj":   val_volt,
            "akim":     val_akim,
            "sicaklik": val_isi,
        }

        # ── 2. ADIM: ALARMLARI DINAMIK BLOK OLARAK OKU ──
        alarm_adresleri = [reg["addr"] for reg in config["alarm_registers"]]
        if alarm_adresleri:
            alarm_start = min(alarm_adresleri)
            alarm_end = max(alarm_adresleri) + 1
            alarm_count = (alarm_end - alarm_start) + 1

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
                            veriler[reg["key"]] = (alarm_regs[offset] << 16) | alarm_regs[offset + 1]
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
                                    dev_id = slave_id
                                    
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

    while True:
        dongu_baslangic = time.time()
        tasks = []
        task_info = []

        for fab_id in FABRIKALAR:
            cfg = load_config(fab_id)
            fab_configs[fab_id] = cfg
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
