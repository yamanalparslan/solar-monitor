import logging
import os
import time

from pymodbus.client import ModbusTcpClient

import utils
import veritabani

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

WS_NOTIFY_URL = os.getenv("WS_NOTIFY_URL", "http://solar_api:8503/ws/notify")

def _notify_websocket():
    try:
        import urllib.request
        req = urllib.request.Request(WS_NOTIFY_URL, data=b"", method="POST")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass

def load_config(fabrika_id="mekanik"):
    ayarlar = veritabani.tum_ayarlari_oku(fabrika_id)
    slave_ids_raw = ayarlar.get("slave_ids", "1,2,3")
    slave_ids, parse_errors = utils.parse_id_list(slave_ids_raw)

    if parse_errors:
        logging.warning("ID parsing hatalari: %s", ", ".join(parse_errors))

    return {
        "target_ip": ayarlar.get("target_ip", "10.35.14.10"),
        "target_port": int(ayarlar.get("target_port", 502)),
        "refresh_rate": float(ayarlar.get("refresh_rate", 2)),
        "slave_ids": slave_ids,
        "guc_addr": int(ayarlar.get("guc_addr", 70)),
        "volt_addr": int(ayarlar.get("volt_addr", 71)),
        "akim_addr": int(ayarlar.get("akim_addr", 72)),
        "isi_addr": int(ayarlar.get("isi_addr", 74)),
        "guc_scale": float(ayarlar.get("guc_scale", 1.0)),
        "volt_scale": float(ayarlar.get("volt_scale", 1.0)),
        "akim_scale": float(ayarlar.get("akim_scale", 0.1)),
        "isi_scale": float(ayarlar.get("isi_scale", 1.0)),
        "veri_saklama_gun": int(ayarlar.get("veri_saklama_gun", 365)),
        "alarm_registers": [
            {"addr": 107, "key": "hata_kodu", "count": 2},
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

def read_device(client, slave_id, config, max_retries=1):
    for attempt in range(max_retries):
        try:
            if not client.connected:
                client.connect()
                time.sleep(0.1)

            def hizli_oku(adres):
                time.sleep(0.05)
                rr = client.read_input_registers(address=adres, count=1, slave=slave_id)
                if getattr(rr, 'isError', lambda: True)():
                    rr = client.read_holding_registers(address=adres, count=1, slave=slave_id)
                return rr.registers[0] if not getattr(rr, 'isError', lambda: True)() else None

            raw_guc = hizli_oku(config["guc_addr"])
            raw_volt = hizli_oku(config["volt_addr"])
            raw_akim = hizli_oku(config["akim_addr"])
            raw_isi = hizli_oku(config["isi_addr"])
            
            src_guc, src_volt, src_akim, src_isi = "hizli_oku", "hizli_oku", "hizli_oku", "hizli_oku"

            if raw_guc is None and raw_volt is None and raw_akim is None and raw_isi is None:
                return None

            val_guc = 0 if raw_guc is None else raw_guc * config["guc_scale"]
            val_volt = 0 if raw_volt is None else utils.to_signed16(raw_volt) * config["volt_scale"]
            val_akim = 0 if raw_akim is None else utils.to_signed16(raw_akim) * config["akim_scale"]
            val_isi = 0 if raw_isi is None else utils.decode_temperature_register(raw_isi, config["isi_scale"])

            if val_guc <= 0 and val_volt > 0 and val_akim > 0:
                val_guc = round(val_volt * val_akim, 2)

            print(
                f"  [Addr G={config['guc_addr']} V={config['volt_addr']} "
                f"A={config['akim_addr']} T={config['isi_addr']}] "
                f"raw=[{raw_guc},{raw_volt},{raw_akim},{raw_isi}] "
                f"src=[{src_guc},{src_volt},{src_akim},{src_isi}] "
                f"-> G={val_guc:.1f}W V={val_volt:.1f}V A={val_akim:.2f}A T={val_isi:.1f}C"
            )

            veriler = {"guc": val_guc, "voltaj": val_volt, "akim": val_akim, "sicaklik": val_isi}

            for reg in config["alarm_registers"]:
                try:
                    time.sleep(0.05)
                    r_hata = client.read_holding_registers(
                        address=reg["addr"],
                        count=reg.get("count", 2),
                        slave=slave_id,
                    )
                    if not getattr(r_hata, 'isError', lambda: True)():
                        if reg.get("count", 2) == 2:
                            veriler[reg["key"]] = (r_hata.registers[0] << 16) | r_hata.registers[1]
                        else:
                            veriler[reg["key"]] = r_hata.registers[0]
                    else:
                        veriler[reg["key"]] = 0
                except Exception:
                    veriler[reg["key"]] = 0

            return veriler

        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                try: client.close()
                except: pass
                continue
            return None

def otomatik_veri_temizle(config):
    saklama_gun = config.get("veri_saklama_gun", 365)
    if saklama_gun == 0: return 0
    try:
        silinen = veritabani.eski_verileri_temizle(saklama_gun)
        if silinen > 0: print(f"\nOtomatik Temizlik: {silinen} kayit silindi")
        return silinen
    except Exception:
        return 0

def start_collector():
    veritabani.init_db()
    print("=" * 60)
    print("COLLECTOR BASLATILDI (Çoklu Fabrika Modu)")
    print("=" * 60)

    from veritabani import FABRIKALAR

    fab_state = {}
    for fab_id, fab_info in FABRIKALAR.items():
        config = load_config(fab_id)
        # Timeout süresi invertör cevap verebilsin diye 3.0 saniyeye çıkarıldı
        client = ModbusTcpClient(config["target_ip"], port=config["target_port"], timeout=3.0)
        fab_state[fab_id] = {"config": config, "client": client}
        print(f"  {fab_info['ikon']} {fab_info['ad']}: {config['target_ip']}:{config['target_port']} IDs={config['slave_ids']}")

    print("=" * 60)

    temizlik_sayaci = 0
    temizlik_periyodu = 1800

    while True:
        start_time = time.time()

        for fab_id in FABRIKALAR:
            state = fab_state[fab_id]
            config = state["config"]
            client = state["client"]

            yeni_config = load_config(fab_id)
            if yeni_config != config:
                if yeni_config["target_ip"] != config["target_ip"] or yeni_config["target_port"] != config["target_port"]:
                    print(f"\n[{fab_id.upper()}] IP/Port degisti, baglanti yenileniyor...")
                    client.close()
                    # Timeout burada da 3.0 saniyeye çıkarıldı
                    client = ModbusTcpClient(yeni_config["target_ip"], port=yeni_config["target_port"], timeout=3.0)
                    state["client"] = client
                config = yeni_config
                state["config"] = config

            for dev_id in config["slave_ids"]:
                print(f"[{fab_id.upper()}] ID {dev_id}...", end=" ", flush=True)
                time.sleep(0.5)
                data = read_device(client, dev_id, config)
                if data:
                    veritabani.veri_ekle(dev_id, data, fabrika_id=fab_id)
                    hata_kodlari = [data.get(f"hata_kodu_{r}", 0) for r in [107,109,111,112,114,115,116,117,118,119,120,121,122]]
                    hata_kodlari[0] = data.get("hata_kodu", 0)
                    durum = "TEMIZ" if all(h == 0 for h in hata_kodlari) else "HATA"
                    print(f"[OK] {durum}")
                else:
                    print("[YOK]")

        temizlik_sayaci += 1
        if temizlik_sayaci >= temizlik_periyodu:
            otomatik_veri_temizle(config)
            temizlik_sayaci = 0

        _notify_websocket()

        elapsed = time.time() - start_time
        min_refresh = min(fab_state[f]["config"]["refresh_rate"] for f in fab_state)
        time.sleep(max(0, min_refresh - elapsed))

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    start_collector()