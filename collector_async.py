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
import logging
import os
import sys
import time
import io

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
    """Veritabanindan fabrika ayarlarini yukler."""
    ayarlar = veritabani.tum_ayarlari_oku(fabrika_id)
    slave_ids_raw = ayarlar.get("slave_ids", "1,2,3")
    slave_ids, parse_errors = utils.parse_id_list(slave_ids_raw)

    if parse_errors:
        logger.warning("[%s] ID parsing hatalari: %s", fabrika_id, ", ".join(parse_errors))

    return {
        "target_ip":      ayarlar.get("target_ip", "10.35.14.10"),
        "target_port":    int(ayarlar.get("target_port", 502)),
        "refresh_rate":   float(ayarlar.get("refresh_rate", 60)),
        "slave_ids":      slave_ids,
        "guc_addr":       int(ayarlar.get("guc_addr", 93)),
        "volt_addr":      int(ayarlar.get("volt_addr", 29)),
        "akim_addr":      int(ayarlar.get("akim_addr", 26)),
        "isi_addr":       int(ayarlar.get("isi_addr", 44)),
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
    client: AsyncModbusTcpClient, slave_id: int, config: dict
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
                return slave_id, None

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

        return slave_id, veriler

    except Exception as exc:
        logger.error("ID %d baglanti/okuma hatasi: %s", slave_id, exc)
        return slave_id, None


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

async def main_loop():
    """
    Tum fabrikalari asenkron tarar.
    """
    veritabani.init_db()
    from veritabani import FABRIKALAR

    print("=" * 65)
    print("ASENKRON COLLECTOR BASLATILDI - Dinamik Blok Okuma Modu")
    print("=" * 65)

    fab_configs: dict = {}
    fab_clients: dict = {}

    for fab_id, fab_info in FABRIKALAR.items():
        cfg = load_config(fab_id)
        fab_configs[fab_id] = cfg
        fab_clients[fab_id] = AsyncModbusTcpClient(
            cfg["target_ip"], port=cfg["target_port"], timeout=3.0
        )
        print(
            f"  {fab_info['ikon']} {fab_info['ad']}: "
            f"{cfg['target_ip']}:{cfg['target_port']} "
            f"IDs={cfg['slave_ids']} Refresh={cfg['refresh_rate']}s"
        )

    print("=" * 65)

    temizlik_sayaci = 0
    TEMIZLIK_PERIYODU = 1800

    while True:
        dongu_baslangic = time.time()

        for fab_id in FABRIKALAR:
            yeni_cfg = load_config(fab_id)
            eski_cfg = fab_configs[fab_id]

            if (yeni_cfg["target_ip"]   != eski_cfg["target_ip"] or
                    yeni_cfg["target_port"] != eski_cfg["target_port"]):
                print(f"\n[{fab_id.upper()}] IP/Port degisti, client yenileniyor...")
                fab_clients[fab_id].close()
                fab_clients[fab_id] = AsyncModbusTcpClient(
                    yeni_cfg["target_ip"], port=yeni_cfg["target_port"], timeout=3.0
                )

            fab_configs[fab_id] = yeni_cfg
            client = fab_clients[fab_id]
            cfg    = yeni_cfg

            if not cfg["slave_ids"]:
                continue

            tasks = [read_device_async(client, dev_id, cfg) for dev_id in cfg["slave_ids"]]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error("Gorev istisnasi: %s", result)
                    continue

                slave_id, data = result
                if data:
                    veritabani.veri_ekle(slave_id, data, fabrika_id=fab_id)
                    hata_var = data.get("hata_kodu", 0) != 0 or any(
                        data.get(f"hata_kodu_{r}", 0) != 0
                        for r in [109, 111, 112, 114, 115, 116, 117, 118, 119, 120, 121, 122]
                    )
                    durum = "[HATA]" if hata_var else "[TEMIZ]"
                    print(
                        f"[{fab_id.upper()}] ID {slave_id} | "
                        f"G={data['guc']:.1f}W  V={data['voltaj']:.1f}V  "
                        f"A={data['akim']:.2f}A  T={data['sicaklik']:.1f}C  "
                        f"{durum}"
                    )
                else:
                    print(f"[{fab_id.upper()}] ID {slave_id} | [CEVAP YOK]")

        temizlik_sayaci += 1
        if temizlik_sayaci * min(c["refresh_rate"] for c in fab_configs.values()) >= TEMIZLIK_PERIYODU:
            for fab_id in FABRIKALAR:
                otomatik_veri_temizle(fab_configs[fab_id])
            temizlik_sayaci = 0

        await _notify_websocket()

        gecen = time.time() - dongu_baslangic
        min_refresh = min(c["refresh_rate"] for c in fab_configs.values())
        await asyncio.sleep(max(1.0, min_refresh - gecen))


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nAsenkron Collector durduruldu.")
