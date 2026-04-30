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

from pymodbus.client import ModbusTcpClient

import utils
import veritabani

sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
)

WS_NOTIFY_URL = os.getenv("WS_NOTIFY_URL", "http://solar_api:8503/ws/notify")


def _notify_websocket():
    try:
        import urllib.request
        req = urllib.request.Request(WS_NOTIFY_URL, data=b"", method="POST")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass


def load_config(fabrika_id: str = "mekanik") -> dict:
    ayarlar = veritabani.tum_ayarlari_oku(fabrika_id)
    slave_ids_raw = ayarlar.get("slave_ids", "1,2,3")
    slave_ids, parse_errors = utils.parse_id_list(slave_ids_raw)

    if parse_errors:
        logging.warning("ID parsing hatalari: %s", ", ".join(parse_errors))

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
# Modbus Okuma Stratejisi
# ─────────────────────────────────────────────

def build_metric_candidates(start_addr: int) -> list:
    """
    Tek bir register adresi icin denenecek (func, addr, count, offset) adaylarini uretir.

    Strateji:
      1. Tekil holding register  (FC3, count=1)
      2. Tekil input  register   (FC4, count=1)
      3. Blok okumalar (count=4): start_addr'dan geriye 0-3 offset ile farkli bloklar

    Ornek - start_addr=73:
      ("holding", 73, 1, 0), ("input", 73, 1, 0),
      ("input",  73, 4, 0),  ("holding", 73, 4, 0),
      ("input",  72, 4, 1),  ("holding", 72, 4, 1),
      ("input",  71, 4, 2),  ("holding", 71, 4, 2),
      ("input",  70, 4, 3),  ("holding", 70, 4, 3)  <-- en yaygin blok
    """
    candidates = []

    # Tekil okumalar
    candidates.append(("holding", start_addr, 1, 0))
    candidates.append(("input",   start_addr, 1, 0))

    # Blok okumalar (geriden ileri)
    max_lookback = min(4, start_addr + 1)
    for block_offset in range(max_lookback):
        block_start = start_addr - block_offset
        if block_start >= 0:
            candidates.append(("input",   block_start, 4, block_offset))
            candidates.append(("holding", block_start, 4, block_offset))

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


def _try_read_metric_sync(client, addr: int, slave_id: int) -> tuple:
    """
    Bir metrik adresi icin tum adaylari sirayla dener.
    Returns: (raw_value, func_adi) veya (None, None)
    """
    for func, address, count, offset in build_metric_candidates(addr):
        regs = _sync_read_registers(client, func, address, count, slave_id)
        if regs is not None and len(regs) > offset:
            return regs[offset], func
    return None, None


def read_device(client, slave_id: int, config: dict, max_retries: int = 1):
    """
    Senkron Modbus okuma.

    Her metrik icin holding + input + blok okuma fallback dener.
    Signed16 donusumu ve sicaklik scale tespiti uygulanir.

    Returns:
        dict (veriler) veya None (cihaz yanitsiz / tum degerler sifir)
    """
    for attempt in range(max_retries):
        try:
            if not client.connected:
                client.connect()
                time.sleep(0.1)

            # ── Temel metrikler ──
            raw_volt, volt_src = _try_read_metric_sync(client, config["volt_addr"], slave_id)
            if raw_volt is None:
                return None

            raw_guc,  guc_src  = _try_read_metric_sync(client, config["guc_addr"],  slave_id)
            raw_akim, akim_src = _try_read_metric_sync(client, config["akim_addr"], slave_id)
            raw_isi,  isi_src  = _try_read_metric_sync(client, config["isi_addr"],  slave_id)

            # ── Deger Donusumu ──
            val_volt = utils.to_signed16(raw_volt) * config["volt_scale"]
            val_akim = (
                0.0 if raw_akim is None
                else utils.to_signed16(raw_akim) * config["akim_scale"]
            )
            val_guc = 0.0 if raw_guc is None else raw_guc * config["guc_scale"]
            val_isi = (
                0.0 if raw_isi is None
                else utils.decode_temperature_register(raw_isi, config["isi_scale"])
            )

            # Guc sifir ama V ve A gecerliyse hesapla
            if val_guc <= 0 and val_volt > 0 and val_akim > 0:
                val_guc = round(val_volt * val_akim, 2)

            # Tum sifir = veri yok
            if val_guc == 0.0 and val_volt == 0.0 and val_akim == 0.0 and val_isi == 0.0:
                return None

            print(
                f"  [ID {slave_id}] "
                f"V={val_volt:.1f}V({volt_src})  "
                f"A={val_akim:.2f}A({akim_src})  "
                f"G={val_guc:.1f}W({guc_src})  "
                f"T={val_isi:.1f}C({isi_src})"
            )

            veriler = {
                "guc":      val_guc,
                "voltaj":   val_volt,
                "akim":     val_akim,
                "sicaklik": val_isi,
            }

            # ── Alarm Register'lari ──
            for reg in config["alarm_registers"]:
                try:
                    time.sleep(0.05)
                    count = reg.get("count", 2)
                    r_hata = client.read_holding_registers(
                        address=reg["addr"], count=count, slave=slave_id
                    )
                    if not getattr(r_hata, "isError", lambda: True)():
                        regs = r_hata.registers
                        if count == 2 and len(regs) >= 2:
                            veriler[reg["key"]] = (regs[0] << 16) | regs[1]
                        elif len(regs) >= 1:
                            veriler[reg["key"]] = regs[0]
                        else:
                            veriler[reg["key"]] = 0
                    else:
                        veriler[reg["key"]] = 0
                except Exception:
                    veriler[reg["key"]] = 0

            return veriler

        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                try:
                    client.close()
                except Exception:
                    pass
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


def start_collector():
    """Senkron collector baslangici (geriye donuk uyumluluk / test)."""
    veritabani.init_db()
    print("=" * 60)
    print("COLLECTOR BASLATILDI (Senkron - Coklu Fabrika Modu)")
    print("NOT: Uretim icin collector_async.py kullanin!")
    print("=" * 60)

    from veritabani import FABRIKALAR

    fab_state = {}
    for fab_id, fab_info in FABRIKALAR.items():
        config = load_config(fab_id)
        client = ModbusTcpClient(
            config["target_ip"], port=config["target_port"], timeout=3.0
        )
        fab_state[fab_id] = {"config": config, "client": client}
        print(
            f"  {fab_info['ikon']} {fab_info['ad']}: "
            f"{config['target_ip']}:{config['target_port']} IDs={config['slave_ids']}"
        )

    print("=" * 60)

    temizlik_sayaci = 0
    TEMIZLIK_PERIYODU = 1800

    while True:
        baslangic = time.time()

        for fab_id in FABRIKALAR:
            state = fab_state[fab_id]
            config = state["config"]
            client = state["client"]

            yeni_config = load_config(fab_id)
            if (yeni_config["target_ip"] != config["target_ip"] or
                    yeni_config["target_port"] != config["target_port"]):
                print(f"\n[{fab_id.upper()}] IP/Port degisti, yenileniyor...")
                client.close()
                client = ModbusTcpClient(
                    yeni_config["target_ip"], port=yeni_config["target_port"], timeout=3.0
                )
                state["client"] = client
            config = yeni_config
            state["config"] = config

            for dev_id in config["slave_ids"]:
                print(f"[{fab_id.upper()}] ID {dev_id}...", end=" ", flush=True)
                time.sleep(0.5)
                data = read_device(client, dev_id, config)
                if data:
                    veritabani.veri_ekle(dev_id, data, fabrika_id=fab_id)
                    hata_var = data.get("hata_kodu", 0) != 0 or any(
                        data.get(f"hata_kodu_{r}", 0) != 0
                        for r in [109, 111, 112, 114, 115, 116, 117, 118, 119, 120, 121, 122]
                    )
                    print("[OK]" if not hata_var else "[OK - HATA KODU VAR]")
                else:
                    print("[YOK]")

        temizlik_sayaci += 1
        if temizlik_sayaci * min(s["config"]["refresh_rate"] for s in fab_state.values()) >= TEMIZLIK_PERIYODU:
            for fab_id in FABRIKALAR:
                otomatik_veri_temizle(fab_state[fab_id]["config"])
            temizlik_sayaci = 0

        _notify_websocket()

        gecen = time.time() - baslangic
        min_refresh = min(s["config"]["refresh_rate"] for s in fab_state.values())
        time.sleep(max(0, min_refresh - gecen))


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    start_collector()