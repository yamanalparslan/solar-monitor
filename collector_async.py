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
import pymodbus.exceptions

# UTF-8 stdout (Windows uyumlulugu)
# reconfigure kullaniliyor: sys.stdout'u yeni bir TextIOWrapper ile degistirmek
# pytest'in cikti yakalamasini bozuyordu. Wrapper cop toplandiginda altindaki
# buffer'i da kapatiyor, pytest de kosu sonunda
# "ValueError: I/O operation on closed file" ile cokuyordu (CI kirmizi).
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

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
    except Exception as e:
        logger.debug("WS notify hatasi: %s", e)


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

async def read_registers_smart(client: AsyncModbusTcpClient, start_addr: int, count: int, slave_id: int):
    """
    Önce holding registers olarak blok halinde okumayı dener.
    Hata alırsa veya boşsa input registers olarak okumayı dener.
    Hepsinde hata alırsa None döner.
    """
    try:
        rr = await client.read_holding_registers(address=start_addr, count=count, slave=slave_id)
        if rr is not None and not rr.isError() and getattr(rr, "registers", None):
            return rr.registers
    except Exception:
        pass

    try:
        rr = await client.read_input_registers(address=start_addr, count=count, slave=slave_id)
        if rr is not None and not rr.isError() and getattr(rr, "registers", None):
            return rr.registers
    except Exception:
        pass

    return None


async def read_device_async(
    client: AsyncModbusTcpClient, dev_id: int, ip_address: str, slave_id: int, config: dict, lock: asyncio.Lock
) -> tuple:
    """
    Tek bir inverter cihazindan tum verileri asenkron ve dinamik blok okuma ile alir.
    """
    try:
        async with lock:
            if not client.connected:
                await client.connect()
                await asyncio.sleep(0.1)
            if not client.connected:
                raise Exception("TCP connection failed to establish")

            # ── 1. ADIM: TEMEL METRIKLERI PARCALI BLOK OLARAK OKU ──
            try:
                # Blok 1: Akim ve Voltaj (ayarlardan gelen adreslere gore 3'er register okuma)
                await asyncio.sleep(1.5) # Gateway için nefes alma süresi (1.5 sn)
                akim_addr = config.get("akim_addr", 25)
                regs_akim = await read_registers_smart(client, akim_addr, 3, slave_id)
                if not regs_akim or len(regs_akim) < 3:
                    raise Exception(f"Akim ({akim_addr}) okunamadi")
                
                volt_addr = config.get("volt_addr", 28)
                regs_volt = await read_registers_smart(client, volt_addr, 3, slave_id)
                if not regs_volt or len(regs_volt) < 3:
                    raise Exception(f"Voltaj ({volt_addr}) okunamadi")
                
                raw_akim_a, raw_akim_b, raw_akim_c = regs_akim[0], regs_akim[1], regs_akim[2]
                raw_volt_ab, raw_volt_bc, raw_volt_ca = regs_volt[0], regs_volt[1], regs_volt[2]

                # Blok 2: Uretim (Tekil okuma, bazi inverterlarda hata verebilir diye soft-fail)
                await asyncio.sleep(0.5)
                regs_uretim = await read_registers_smart(client, config["uretim_addr"], 1, slave_id)
                raw_uretim = regs_uretim[0] if (regs_uretim and len(regs_uretim) >= 1) else 0

                # Blok 3: Guc ve Isi Adresleri
                p_start = min(config["guc_addr"], config["isi_addr"])
                p_end = max(config["guc_addr"], config["isi_addr"])
                p_count = (p_end - p_start) + 1
                
                await asyncio.sleep(0.5)
                regs_power = await read_registers_smart(client, p_start, p_count, slave_id)
                if not regs_power or len(regs_power) < p_count:
                    raise Exception(f"Guc/Isi ({p_start}-{p_end}) okunamadi")
                
                raw_guc = regs_power[config["guc_addr"] - p_start]
                raw_isi = regs_power[config["isi_addr"] - p_start]
                
            except Exception as e:
                logger.error(f"IP {ip_address} ID {slave_id} veri okuma hatasi: {e}")
                try:
                    client.close()
                except Exception:
                    pass
                return dev_id, ip_address, slave_id, None

            # ── Deger Donusumleri ──
            val_volt_ab = utils.to_signed16(raw_volt_ab) * config["volt_scale"]
            val_volt_bc = utils.to_signed16(raw_volt_bc) * config["volt_scale"]
            val_volt_ca = utils.to_signed16(raw_volt_ca) * config["volt_scale"]
            
            # Voltaj icin genel bir ortalama deger de tutalim
            val_volt = round((val_volt_ab + val_volt_bc + val_volt_ca) / 3, 2)
            
            val_akim_a = utils.to_signed16(raw_akim_a) * config["akim_scale"]
            val_akim_b = utils.to_signed16(raw_akim_b) * config["akim_scale"]
            val_akim_c = utils.to_signed16(raw_akim_c) * config["akim_scale"]
            
            # Akim icin genel bir ortalama deger de tutalim
            val_akim = round((val_akim_a + val_akim_b + val_akim_c) / 3, 2)

            # --- MODBUS 1-REGISTER SHIFT OTO-DUZELTME ---
            # Cihaz (Gateway/Inverter) donanimsal kilitlenmeden dolayi paketleri 1 register ileri kaydirdiginda:
            # Voltaj CA adresi (40031) yerine Frekans'i (40032) okur => Deger 50.00 Hz * 0.1(scale) = 500.0 V olur.
            # (Frekans dalgalanmasindan dolayi 49.96 Hz = 499.6 V gelebilir, bu yuzden aralik kontrolu yapiyoruz)
            # Akim C adresi (40028) yerine Voltaj AB'yi (40029) okur => Deger 7600 * 0.1 = 760.0 A olur.
            if 480.0 <= val_volt_ca <= 520.0 and val_akim_c > 500.0:
                logger.warning(f"Modbus 1-Register Shift tespit edildi (IP: {ip_address}, ID: {slave_id}). Oto-duzeltme uygulaniyor.")
                
                # Voltajlari 1 adim geri kaydirarak kurtarma
                gercek_volt_bc = val_volt_ab  # Okunan Volt AB aslinda Volt BC idi
                gercek_volt_ca = val_volt_bc  # Okunan Volt BC aslinda Volt CA idi
                gercek_volt_ab = utils.to_signed16(raw_akim_c) * config["volt_scale"] # Okunan Akim C icinde Volt AB sakliydi
                
                val_volt_ab = gercek_volt_ab
                val_volt_bc = gercek_volt_bc
                val_volt_ca = gercek_volt_ca
                val_volt = round((val_volt_ab + val_volt_bc + val_volt_ca) / 3, 2)
                
                # Akimlari 1 adim geri kaydirarak kurtarma
                gercek_akim_b = val_akim_a  # Okunan Akim A aslinda Akim B idi
                gercek_akim_c = val_akim_b  # Okunan Akim B aslinda Akim C idi
                gercek_akim_a = gercek_akim_b # Gercek Akim A diziden dustugu icin, sistemi dengeli (B'ye esit) varsayiyoruz
                
                val_akim_a = gercek_akim_a
                val_akim_b = gercek_akim_b
                val_akim_c = gercek_akim_c
                val_akim = round((val_akim_a + val_akim_b + val_akim_c) / 3, 2)
                # ----------------------------------------------
            
            val_guc  = utils.to_signed16(raw_guc)  * config["guc_scale"]
            val_isi  = utils.decode_temperature_register(raw_isi, config["isi_scale"])
            val_uretim = float(raw_uretim) * config["uretim_scale"]

            logger.info(f"IP {ip_address} ID {slave_id} okunan: V={val_volt}, I={val_akim}, P={val_guc}, T={val_isi}, U={val_uretim}")

            if val_volt == 0 and val_akim == 0 and val_guc == 0 and val_isi == 0:
                return dev_id, ip_address, slave_id, None

            veriler = {
                "guc":      val_guc,
                "voltaj":   val_volt,
                "voltaj_ab": val_volt_ab,
                "voltaj_bc": val_volt_bc,
                "voltaj_ca": val_volt_ca,
                "akim":     val_akim,
                "akim_a": val_akim_a,
                "akim_b": val_akim_b,
                "akim_c": val_akim_c,
                "sicaklik": val_isi,
                "modbus_uretim": val_uretim,
            }

            # ── 2. ADIM: ALARMLARI OKU (BLOK VEYA FALLBACK) ──
            if config["alarm_registers"]:
                alarm_adresleri = [reg["addr"] for reg in config["alarm_registers"]]
                alarm_start = min(alarm_adresleri)
                alarm_end = max(alarm_adresleri) + 2
                alarm_count = alarm_end - alarm_start

                alarm_regs = None
                if alarm_count < 50:
                    await asyncio.sleep(0.05)
                    alarm_regs = await read_registers_smart(client, alarm_start, alarm_count, slave_id)

                if alarm_regs is not None and len(alarm_regs) == alarm_count:
                    # Blok okuma başarılı!
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
                    # Blok okuma başarısız, tek tek okuma fallback'i
                    try:
                        for reg in config["alarm_registers"]:
                            a_addr = reg["addr"]
                            a_count = reg.get("count", 2)
                            
                            rr_alarm = await client.read_holding_registers(address=a_addr, count=a_count, slave=slave_id)
                            if rr_alarm.isError():
                                rr_alarm = await client.read_input_registers(address=a_addr, count=a_count, slave=slave_id)
                            
                            if rr_alarm.isError():
                                if isinstance(rr_alarm, pymodbus.exceptions.ModbusIOException):
                                    logger.warning(f"IP {ip_address} ID {slave_id} alarm timeout, stopping alarm reads.")
                                    break
                                veriler[reg["key"]] = 0
                            elif len(rr_alarm.registers) == a_count:
                                if a_count == 2:
                                    veriler[reg["key"]] = (rr_alarm.registers[1] << 16) | rr_alarm.registers[0]
                                else:
                                    veriler[reg["key"]] = rr_alarm.registers[0]
                            else:
                                veriler[reg["key"]] = 0
                    except Exception as e:
                        logger.warning(f"IP {ip_address} ID {slave_id} alarm okuma hatasi: {e}. Mevcut veriler kaydedilecek.")

            return dev_id, ip_address, slave_id, veriler

    except Exception as exc:
        logger.error("IP %s ID %d baglanti/okuma hatasi: %s", ip_address, slave_id, exc)
        try:
            client.close()
        except Exception:
            pass
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
    locks: dict = {}

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

        active_client_keys = set()
        for fab_id in FABRIKALAR:
            cfg = fab_configs[fab_id]
            port = cfg["target_port"]

            for device in cfg["target_devices"]:
                ip = device["ip"]
                client_key = f"{ip}:{port}"
                active_client_keys.add(client_key)
                
                if client_key not in clients:
                    clients[client_key] = AsyncModbusTcpClient(ip, port=port, timeout=2.0, retries=3)
                client = clients[client_key]
                
                if client_key not in locks:
                    locks[client_key] = asyncio.Lock()
                lock = locks[client_key]
                
                for slave_id in device["slave_ids"]:
                    dev_id = slave_id
                    
                    task = asyncio.wait_for(
                        read_device_async(client, dev_id, ip, slave_id, cfg, lock),
                        timeout=90.0
                    )
                    tasks.append(task)
                    task_info.append({
                        "fab_id": fab_id,
                        "ip": ip,
                        "slave_id": slave_id,
                        "dev_id": dev_id
                    })

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Tüm istemcileri kapatarak cihazların kilitlenmesini engelleme ve portu serbest bırakma
        for key in list(clients.keys()):
            client_to_close = clients.pop(key)
            client_to_close.close()
            logger.info("Baglanti kapatildi ve serbest birakildi: %s", key)

        # Cihaz basina cevap durumu (heartbeat ve cevapsizlik logu icin).
        # Cevap alinamayan cihaz da kaydedilir: "satir yok" durumu eskiden
        # "cihaz kapali" ile "ag koptu"yu ayirt edemiyordu.
        cevap_durumlari = []
        fab_sayaclari = {fab_id: {"okunan": 0, "cevapsiz": 0} for fab_id in FABRIKALAR}

        for i, result in enumerate(results):
            info = task_info[i]
            fab_id = info["fab_id"]
            ip_address = info["ip"]
            slave_id = info["slave_id"]
            dev_id = info["dev_id"]

            if isinstance(result, Exception):
                err_msg = str(result)
                if isinstance(result, asyncio.TimeoutError):
                    err_msg = "Task TimeoutError (90s)"

                cevap_durumlari.append((fab_id, slave_id, False))
                fab_sayaclari[fab_id]["cevapsiz"] += 1

                logger.error(f"[{fab_id.upper()}] IP {ip_address} ID {slave_id} (DevID: {dev_id}) - Gorev hatasi: {err_msg}")
                print(f"[{fab_id.upper()}] IP {ip_address} ID {slave_id} (DevID: {dev_id}) | [HATA/ZAMAN ASIMI] - {err_msg}")
                continue

            dev_id, ip_address, slave_id, data = result

            cevap_durumlari.append((fab_id, slave_id, bool(data)))
            if data:
                fab_sayaclari[fab_id]["okunan"] += 1
            else:
                fab_sayaclari[fab_id]["cevapsiz"] += 1

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

        # ── Kalp atisi ve cevap durumu kaydi ──
        # Cihazlarin hicbiri cevap vermese bile yazilir: healthcheck bu sayede
        # "collector oldu" ile "cihaz cevap vermiyor" durumlarini ayirt eder.
        # Basarisiz okumalar eskiden yalnizca stdout'a basiliyordu; artik
        # cihaz_durum_log'a islenip calisabilirlik olarak raporlanabiliyor.
        dongu_suresi = time.time() - dongu_baslangic
        try:
            veritabani.cihaz_cevap_durumlarini_guncelle(cevap_durumlari)
            for fab_id, sayac in fab_sayaclari.items():
                veritabani.heartbeat_yaz(
                    fab_id,
                    dongu_suresi_sn=dongu_suresi,
                    okunan_cihaz=sayac["okunan"],
                    cevapsiz_cihaz=sayac["cevapsiz"],
                    beklenen_periyot_sn=fab_configs[fab_id]["refresh_rate"],
                )
        except Exception as e:
            logger.error("Heartbeat/cevap durumu yazilamadi: %s", e)

        # Dongu refresh_rate'i asiyorsa olcum araligi sessizce kayar; gorunur olsun.
        if dongu_suresi > min_refresh:
            logger.warning(
                "Dongu %.1f sn surdu, refresh_rate %.0f sn — olcum araligi kaydi. "
                "Cihaz sayisini, gateway bekleme surelerini veya refresh_rate'i gozden gecirin.",
                dongu_suresi, min_refresh
            )

        await _notify_websocket()

        gecen = time.time() - dongu_baslangic
        await asyncio.sleep(max(1.0, min_refresh - gecen))


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nAsenkron Collector durduruldu.")
