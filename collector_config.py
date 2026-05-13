"""
Solar Monitor - Ortak Collector Konfigurasyon Modulu
=====================================================
collector.py ve collector_async.py tarafından ortak kullanılan:
  - load_config()          → Fabrikaya ozgul Modbus konfigurasyon
  - ALARM_REGISTERS        → Alarm register listesi (tek kaynak)
  - start_daily_webhook_thread() → Gunluk ozet webhook servisi

Bu modul direkt calistirilmaz; collector*.py dosyalari tarafindan import edilir.
"""

import datetime
import logging
import os
import threading
import time

import requests
import veritabani

logger = logging.getLogger("collector_config")


# ─────────────────────────────────────────────
# Alarm Register Listesi (Tek Kaynak / Source of Truth)
# ─────────────────────────────────────────────

ALARM_REGISTERS: list[dict] = [
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
]


# ─────────────────────────────────────────────
# Konfigurasyon Yukleme
# ─────────────────────────────────────────────

def load_config(fabrika_id: str = "mekanik") -> dict:
    """Fabrikaya ozgul Modbus + webhook konfigurasyonunu dondurur.

    Oncelik sirasi:
        1. .env ortam degiskeni (TARGET_DEVICES_<FABRIKA_ID>)
        2. Veritabani ayarlar tablosu (DB)
        3. Sabit varsayilan degerler

    Returns:
        dict: Collector'ın kullandigi konfigurasyon sozlugu
    """
    ayarlar = veritabani.tum_ayarlari_oku(fabrika_id)

    # Fabrikaya ozel IP ve ID'leri .env dosyasindan okuyoruz
    env_key = f"TARGET_DEVICES_{fabrika_id.upper()}"
    target_devices_raw = os.getenv(env_key)

    if not target_devices_raw:
        # Eger ozel .env bulunamazsa veritabanindaki varsayilanlara don
        eski_ip = ayarlar.get("target_ip", "10.35.14.10")
        eski_ids = ayarlar.get("slave_ids", "1")
        target_devices_raw = f"{eski_ip}:{eski_ids}"

    target_devices: list[dict] = []
    for part in target_devices_raw.split(";"):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            ip, ids_str = part.split(":", 1)
            ids = [int(i.strip()) for i in ids_str.split(",") if i.strip().isdigit()]
            target_devices.append({"ip": ip.strip(), "slave_ids": ids})
        else:
            target_devices.append({"ip": part.strip(), "slave_ids": [1]})

    return {
        "target_devices":     target_devices,
        "target_port":        int(ayarlar.get("target_port", 502)),
        "refresh_rate":       float(ayarlar.get("refresh_rate", 60)),
        "webhook_enabled":    os.getenv("WEBHOOK_ENABLED", "false").lower() == "true",
        "webhook_url":        os.getenv("WEBHOOK_URL", ""),
        "webhook_api_key":    os.getenv("WEBHOOK_API_KEY", ""),
        "webhook_daily_time": os.getenv("WEBHOOK_DAILY_TIME", "23:50"),
        "guc_addr":           int(ayarlar.get("guc_addr")   or os.getenv("GUC_ADDR",   75)),
        "volt_addr":          int(ayarlar.get("volt_addr")  or os.getenv("VOLT_ADDR",  73)),
        "akim_addr":          int(ayarlar.get("akim_addr")  or os.getenv("AKIM_ADDR",  70)),
        "isi_addr":           int(ayarlar.get("isi_addr")   or os.getenv("ISI_ADDR",   44)),
        "guc_scale":          float(ayarlar.get("guc_scale")   or os.getenv("GUC_SCALE",   0.1)),
        "volt_scale":         float(ayarlar.get("volt_scale")  or os.getenv("VOLT_SCALE",  0.1)),
        "akim_scale":         float(ayarlar.get("akim_scale")  or os.getenv("AKIM_SCALE",  0.1)),
        "isi_scale":          float(ayarlar.get("isi_scale")   or os.getenv("ISI_SCALE",   1.0)),
        "uretim_addr":        int(ayarlar.get("uretim_addr")   or os.getenv("URETIM_ADDR",  36)),
        "uretim_scale":       float(ayarlar.get("uretim_scale") or os.getenv("URETIM_SCALE", 1.0)),
        "veri_saklama_gun":   int(ayarlar.get("veri_saklama_gun", 365)),
        "alarm_registers":    ALARM_REGISTERS,
    }


# ─────────────────────────────────────────────
# Gunluk Webhook Ozet Servisi
# ─────────────────────────────────────────────

def start_daily_webhook_thread() -> threading.Thread:
    """Gunluk ozet raporunu belirtilen saatte ilgili webhook URL'e gonderir.

    Thread daemon olarak baslatilir; ana process sonlaninca otomatik durur.

    Returns:
        Baslatilan threading.Thread nesnesi (test icin kullanilabilir)
    """

    def _daily_task() -> None:
        from veritabani import (
            FABRIKALAR,
            gunluk_uretim_hesapla,
            hata_sayilarini_getir,
            tarih_araliginda_ortalamalar,
        )

        while True:
            now = datetime.datetime.now()
            config = load_config("mekanik")

            if config.get("webhook_enabled") and config.get("webhook_url"):
                target_time = config.get("webhook_daily_time", "23:50").split(":")
                if (
                    len(target_time) == 2
                    and now.hour == int(target_time[0])
                    and now.minute == int(target_time[1])
                ):
                    today_str = now.strftime("%Y-%m-%d")

                    for fab_id in FABRIKALAR:
                        fab_config = load_config(fab_id)
                        for device in fab_config["target_devices"]:
                            ip = device["ip"]
                            for slave_id in device["slave_ids"]:
                                dev_id = slave_id
                                try:
                                    uretim   = gunluk_uretim_hesapla(today_str, slave_id=dev_id, fabrika_id=fab_id) or {}
                                    ortalama = tarih_araliginda_ortalamalar(today_str, today_str, slave_id=dev_id, fabrika_id=fab_id) or {}
                                    hatalar  = hata_sayilarini_getir(today_str, today_str, slave_id=dev_id, fabrika_id=fab_id) or {}

                                    payload = {
                                        "tarih":      today_str,
                                        "fabrika_id": fab_id,
                                        "device_id":  dev_id,
                                        "ip_address": ip,
                                        "ozet": {
                                            "toplam_uretim_kwh":   uretim.get("modbus_uretim", 0) or uretim.get("uretim_kwh", 0),
                                            "calisma_suresi_saat": uretim.get("calisma_suresi_saat", 0),
                                            "ortalama_sicaklik":   round(ortalama.get("ort_sicaklik", 0) or 0, 2),
                                            "max_guc":             round(ortalama.get("max_guc", 0) or 0, 2),
                                            "toplam_hata_sayisi":  hatalar.get("hata_107_sayisi", 0) or 0,
                                        },
                                    }

                                    headers = {"Content-Type": "application/json"}
                                    if config.get("webhook_api_key"):
                                        headers["Authorization"] = f"Bearer {config['webhook_api_key']}"

                                    response = requests.post(
                                        config["webhook_url"],
                                        json=payload,
                                        headers=headers,
                                        timeout=10,
                                    )
                                    response.raise_for_status()
                                    logger.info(
                                        "[WEBHOOK] Gunluk ozet gonderildi: Fabrika %s, Cihaz %s",
                                        fab_id,
                                        dev_id,
                                    )
                                except Exception as exc:
                                    logger.error(
                                        "Gunluk webhook hatasi (Cihaz %s): %s", dev_id, exc
                                    )

                    # Ayni dakika icinde tekrar calismasin
                    time.sleep(65)

            time.sleep(30)

    thread = threading.Thread(target=_daily_task, daemon=True, name="daily_webhook")
    thread.start()
    return thread
