import logging
import os
import time

from pymodbus.client import ModbusTcpClient

import utils
import veritabani

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

INTER_REQUEST_DELAY = 0.25
BLOCK_CANDIDATE_SIZE = 4
WS_NOTIFY_URL = os.getenv("WS_NOTIFY_URL", "http://solar_api:8503/ws/notify")


def _notify_websocket():
    """API'ye bildirim göndererek WebSocket istemcilerini günceller."""
    try:
        import urllib.request
        req = urllib.request.Request(WS_NOTIFY_URL, data=b"", method="POST")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass  # WS bildirimi kritik değil, sessizce devam et


def load_config():
    """Veritabanindan ayarlari yukle."""
    ayarlar = veritabani.tum_ayarlari_oku()

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


def read_registers(client, function_name, address, count, slave_id):
    method = client.read_holding_registers if function_name == "holding" else client.read_input_registers
    rr = method(address=address, count=count, slave=slave_id)
    if rr.isError():
        return None
    return rr.registers


def _unique_candidates(candidates):
    unique = []
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def build_metric_candidates(address):
    candidates = [
        ("holding", address, 1, 0),
        ("input", address, 1, 0),
    ]

    block_starts = [address]
    for offset in range(1, BLOCK_CANDIDATE_SIZE):
        start_addr = address - offset
        if start_addr >= 0:
            block_starts.append(start_addr)

    for start_addr in block_starts:
        index = address - start_addr
        candidates.append(("holding", start_addr, BLOCK_CANDIDATE_SIZE, index))
        candidates.append(("input", start_addr, BLOCK_CANDIDATE_SIZE, index))

    return _unique_candidates(candidates)


def read_metric_with_fallback(client, address, slave_id, cache):
    for function_name, start_addr, count, index in build_metric_candidates(address):
        cache_key = (function_name, start_addr, count)
        if cache_key not in cache:
            try:
                cache[cache_key] = read_registers(client, function_name, start_addr, count, slave_id)
            except Exception:
                cache[cache_key] = None
            time.sleep(INTER_REQUEST_DELAY)

        registers = cache[cache_key]
        if registers is None or index >= len(registers):
            continue

        source = f"{function_name}:{start_addr}/{count}[{index}]"
        return registers[index], source

    return None, "-"


def read_device(client, slave_id, config, max_retries=3):
    for attempt in range(max_retries):
        try:
            if not client.connected:
                client.connect()
                time.sleep(0.1)

            cache = {}
            raw_guc, src_guc = read_metric_with_fallback(client, config["guc_addr"], slave_id, cache)
            raw_volt, src_volt = read_metric_with_fallback(client, config["volt_addr"], slave_id, cache)
            raw_akim, src_akim = read_metric_with_fallback(client, config["akim_addr"], slave_id, cache)
            raw_isi, src_isi = read_metric_with_fallback(client, config["isi_addr"], slave_id, cache)

            available_metric_count = sum(value is not None for value in (raw_guc, raw_volt, raw_akim, raw_isi))
            nonzero_metric_count = sum(bool(value) for value in (raw_guc, raw_volt, raw_akim, raw_isi) if value is not None)

            if available_metric_count == 0 or (available_metric_count < 2 and nonzero_metric_count == 0):
                if attempt < max_retries - 1:
                    time.sleep(0.75)
                    try:
                        client.close()
                    except Exception:
                        pass
                    continue

                logging.error(
                    "Modbus veri yetersiz (ID=%s, kaynaklar G=%s V=%s A=%s T=%s)",
                    slave_id,
                    src_guc,
                    src_volt,
                    src_akim,
                    src_isi,
                )
                try:
                    client.close()
                except Exception:
                    pass
                return None

            # ── Değerleri hesapla ──
            val_guc = 0 if raw_guc is None else raw_guc * config["guc_scale"]
            val_volt = 0 if raw_volt is None else utils.to_signed16(raw_volt) * config["volt_scale"]
            val_akim = 0 if raw_akim is None else utils.to_signed16(raw_akim) * config["akim_scale"]
            val_isi = 0 if raw_isi is None else utils.decode_temperature_register(raw_isi, config["isi_scale"])

            if val_guc <= 0 and val_volt > 0 and val_akim > 0:
                val_guc = round(val_volt * val_akim, 2)

            if val_guc == 0 and val_volt == 0 and val_akim == 0 and val_isi == 0:
                if attempt < max_retries - 1:
                    time.sleep(0.75)
                    try:
                        client.close()
                    except Exception:
                        pass
                    continue

                logging.error("Tum metrikler sifir dondu (ID=%s)", slave_id)
                try:
                    client.close()
                except Exception:
                    pass
                return None

            print(
                f"  [Addr G={config['guc_addr']} V={config['volt_addr']} "
                f"A={config['akim_addr']} T={config['isi_addr']}] "
                f"raw=[{raw_guc},{raw_volt},{raw_akim},{raw_isi}] "
                f"src=[{src_guc},{src_volt},{src_akim},{src_isi}] "
                f"-> G={val_guc:.1f}W V={val_volt:.1f}V A={val_akim:.2f}A T={val_isi:.1f}C"
            )

            veriler = {
                "guc": val_guc,
                "voltaj": val_volt,
                "akim": val_akim,
                "sicaklik": val_isi,
            }

            # ── 5. Hata Kodları ──
            for reg in config["alarm_registers"]:
                try:
                    time.sleep(0.05)
                    r_hata = client.read_holding_registers(
                        address=reg["addr"],
                        count=reg.get("count", 2),
                        slave=slave_id,
                    )
                    if not r_hata.isError():
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
                try:
                    client.close()
                except Exception:
                    pass
                continue
            else:
                logging.error("ID %s hata: %s", slave_id, exc)
                try:
                    client.close()
                except Exception:
                    pass
                return None


def otomatik_veri_temizle(config):
    """
    Ayarlara gore eski verileri otomatik temizle.
    0 = sinirsiz saklama (temizleme yapma)
    """
    saklama_gun = config.get("veri_saklama_gun", 365)

    if saklama_gun == 0:
        return 0

    try:
        silinen = veritabani.eski_verileri_temizle(saklama_gun)
        if silinen > 0:
            print(f"\nOtomatik Temizlik: {silinen} kayit silindi ({saklama_gun} gunden eski)")
        return silinen
    except Exception as exc:
        print(f"\nOtomatik temizlik hatasi: {exc}")
        return 0


def start_collector():
    veritabani.init_db()
    print("=" * 60)
    print("COLLECTOR BASLATILDI (Dinamik Ayar Modu)")
    print("=" * 60)

    config = load_config()
    client = ModbusTcpClient(config["target_ip"], port=config["target_port"], timeout=5.0)

    print(f"IP: {config['target_ip']}:{config['target_port']}")
    print(f"Refresh: {config['refresh_rate']}s")
    print(f"Slave IDs: {config['slave_ids']}")
    print(
        "Carpanlar: "
        f"Guc={config['guc_scale']}, "
        f"V={config['volt_scale']}, "
        f"A={config['akim_scale']}, "
        f"C={config['isi_scale']}"
    )
    print(
        "Adresler: "
        f"Guc={config['guc_addr']}, "
        f"V={config['volt_addr']}, "
        f"A={config['akim_addr']}, "
        f"C={config['isi_addr']}"
    )

    if config["veri_saklama_gun"] == 0:
        print("Veri Saklama: Sinirsiz")
    else:
        print(f"Veri Saklama: {config['veri_saklama_gun']} Gun")

    print("=" * 60)

    temizlik_sayaci = 0
    temizlik_periyodu = 1800

    otomatik_veri_temizle(config)

    while True:
        start_time = time.time()

        yeni_config = load_config()
        if yeni_config != config:
            if (
                yeni_config["target_ip"] != config["target_ip"]
                or yeni_config["target_port"] != config["target_port"]
            ):
                print("\nIP/Port degisti, baglanti yenileniyor...")
                client.close()
                client = ModbusTcpClient(
                    yeni_config["target_ip"],
                    port=yeni_config["target_port"],
                    timeout=5.0,
                )
            config = yeni_config
            print(f"\nAyarlar guncellendi (Refresh: {config['refresh_rate']}s)")

        temizlik_sayaci += 1
        if temizlik_sayaci >= temizlik_periyodu:
            otomatik_veri_temizle(config)
            temizlik_sayaci = 0

        for dev_id in config["slave_ids"]:
            print(f"ID {dev_id}...", end=" ")
            time.sleep(0.5)
            data = read_device(client, dev_id, config)
            if data:
                veritabani.veri_ekle(dev_id, data)
                h107 = data.get("hata_kodu", 0)
                h109 = data.get("hata_kodu_109", 0)
                h111 = data.get("hata_kodu_111", 0)
                h112 = data.get("hata_kodu_112", 0)
                h114 = data.get("hata_kodu_114", 0)
                h115 = data.get("hata_kodu_115", 0)
                h116 = data.get("hata_kodu_116", 0)
                h117 = data.get("hata_kodu_117", 0)
                h118 = data.get("hata_kodu_118", 0)
                h119 = data.get("hata_kodu_119", 0)
                h120 = data.get("hata_kodu_120", 0)
                h121 = data.get("hata_kodu_121", 0)
                h122 = data.get("hata_kodu_122", 0)
                if h107 == 0 and h109 == 0 and h111 == 0 and h112 == 0 and h114 == 0 and h115 == 0 and h116 == 0 and h117 == 0 and h118 == 0 and h119 == 0 and h120 == 0 and h121 == 0 and h122 == 0:
                    durum = "TEMIZ"
                else:
                    durum = f"HATA (107:{h107}, 109:{h109}, 111:{h111}, 112:{h112}, 114:{h114}, 115:{h115}, 116:{h116}, 117:{h117}, 118:{h118}, 119:{h119}, 120:{h120}, 121:{h121}, 122:{h122})"
                print(f"[OK] {durum}")
            else:
                print("[YOK]")

        elapsed = time.time() - start_time

        # WebSocket istemcilerini bilgilendir
        _notify_websocket()

        time.sleep(max(0, config["refresh_rate"] - elapsed))


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    start_collector()
