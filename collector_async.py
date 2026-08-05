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

# ─────────────────────────────────────────────
# Gateway zamanlamasi (ayarlanabilir)
# ─────────────────────────────────────────────
#
# RS485 gateway istekler arasinda bosluk bekliyor. Sahada olculdu: bosluksuz
# giden tek okuma (akim'in hemen ardindan gelen voltaj) 24 saatte 1674 kez
# basarisiz oldu, bosluklu okumalarin toplam hata sayisi 2'ydi. Ucuncu cihaz
# (uretim/1) hic hata vermedi; digerleri dongulerin ~%60'ini kaybetti.
#
# Bu yuzden: (1) her istekten once bosluk birakilir, (2) yakin adres
# araliklari tek blokta okunarak istek sayisi dusurulur, (3) sureler
# .env'den ayarlanabilir cunku dogru deger gateway modeline gore degisir.
GATEWAY_ILK_GECIKME_SN = float(os.getenv("MODBUS_GATEWAY_ILK_GECIKME_SN", "1.5"))
GATEWAY_ISTEK_ARASI_SN = float(os.getenv("MODBUS_ISTEK_ARASI_GECIKME_SN", "0.5"))
GATEWAY_ALARM_GECIKME_SN = float(os.getenv("MODBUS_ALARM_GECIKME_SN", "0.5"))
# Tek istekte okunacak azami register sayisi. Uretimde 33-44 (12 register)
# sorunsuz okunuyor; 16 guvenli bir ust sinir.
MAX_BLOK_REGISTER = int(os.getenv("MODBUS_MAX_BLOK_REGISTER", "16"))


def okuma_plani(araliklar, max_blok: int = None):
    """Yakin adres araliklarini tek blok okumaya gruplar.

    araliklar: [(ad, baslangic, adet), ...]
    Doner:     [{"start": int, "count": int, "offsetler": {ad: offset}}, ...]

    Neden: her Modbus istegi gateway'de bosluk bekletmesi gerektiriyor, yani
    istek sayisi dogrudan dongu suresi ve hata olasiligi demek. Uretim
    ayarlarinda akim=26, voltaj=29 (3'er register) ardisik oldugu icin tek
    26-31 blogunda okunur; uretim=36 zaten guc=33..isi=44 araliginin icinde
    kaldigi icin ayrica okunmasina gerek yoktur (eskiden register 36 her
    dongude iki kez okunuyordu).

    Ornek (uretim ayarlari, max_blok=16):
        akim 26+3, voltaj 29+3, uretim 36+1, guc 33+1, isi 44+1
        -> [ {26, 6, {akim:0, voltaj:3}},
             {33, 12, {guc:0, uretim:3, isi:11}} ]
        4 istek yerine 2 istek.
    """
    if max_blok is None:
        max_blok = MAX_BLOK_REGISTER

    gruplar = []
    for ad, baslangic, adet in sorted(araliklar, key=lambda a: (a[1], a[0])):
        if gruplar:
            grup = gruplar[-1]
            yeni_son = max(grup["start"] + grup["count"], baslangic + adet)
            if yeni_son - grup["start"] <= max_blok:
                grup["count"] = yeni_son - grup["start"]
                grup["offsetler"][ad] = baslangic - grup["start"]
                grup["araliklar"][ad] = (baslangic, adet)
                continue

        gruplar.append({
            "start": baslangic,
            "count": adet,
            "offsetler": {ad: 0},
            # Blok okuma basarisiz olursa tek tek denemek icin gerekli.
            "araliklar": {ad: (baslangic, adet)},
        })

    return gruplar


async def read_registers_smart(client: AsyncModbusTcpClient, start_addr: int, count: int, slave_id: int,
                               istek_arasi_sn: float = None):
    """
    Önce holding registers olarak blok halinde okumayı dener.
    Hata alırsa veya boşsa input registers olarak okumayı dener.
    Hepsinde hata alırsa None döner.

    Iki deneme arasinda da gateway boslugu birakilir: holding hemen ardindan
    input istegi gondermek tam olarak sahada cokmesine yol acan bosluksuz
    istek kalibiydi.
    """
    if istek_arasi_sn is None:
        istek_arasi_sn = GATEWAY_ISTEK_ARASI_SN

    try:
        rr = await client.read_holding_registers(address=start_addr, count=count, slave=slave_id)
        if rr is not None and not rr.isError() and getattr(rr, "registers", None):
            return rr.registers
    except Exception:
        pass

    if istek_arasi_sn > 0:
        await asyncio.sleep(istek_arasi_sn)

    try:
        rr = await client.read_input_registers(address=start_addr, count=count, slave=slave_id)
        if rr is not None and not rr.isError() and getattr(rr, "registers", None):
            return rr.registers
    except Exception:
        pass

    return None


async def metrikleri_oku(client, slave_id: int, araliklar, ip_address: str = "",
                         istek_arasi_sn: float = None, max_blok: int = None):
    """Plani uygulayip {ad: [register...]} dondurur.

    Bir blok okunamazsa o blogun icindeki araliklar tek tek, aralarinda
    gateway boslugu birakilarak yeniden denenir. Boylece 6 register'lik blok
    okumayi kabul etmeyen bir cihaz eski davranisla calismaya devam eder.
    """
    if istek_arasi_sn is None:
        istek_arasi_sn = GATEWAY_ISTEK_ARASI_SN

    sonuc = {}
    ilk_istek = True

    for grup in okuma_plani(araliklar, max_blok):
        if not ilk_istek and istek_arasi_sn > 0:
            await asyncio.sleep(istek_arasi_sn)
        ilk_istek = False

        regs = await read_registers_smart(
            client, grup["start"], grup["count"], slave_id, istek_arasi_sn
        )

        if regs and len(regs) >= grup["count"]:
            for ad, offset in grup["offsetler"].items():
                _, adet = grup["araliklar"][ad]
                sonuc[ad] = regs[offset:offset + adet]
            continue

        # Blok okuma basarisiz: araliklari tek tek dene.
        logger.warning(
            "IP %s ID %s blok okuma basarisiz (%s-%s), araliklar tek tek denenecek",
            ip_address, slave_id, grup["start"], grup["start"] + grup["count"] - 1
        )
        for ad, (baslangic, adet) in grup["araliklar"].items():
            if istek_arasi_sn > 0:
                await asyncio.sleep(istek_arasi_sn)
            tek = await read_registers_smart(client, baslangic, adet, slave_id, istek_arasi_sn)
            if tek and len(tek) >= adet:
                sonuc[ad] = tek[:adet]

    return sonuc


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

            # ── 1. ADIM: TEMEL METRIKLERI PLANLI BLOK OKUMAYLA AL ──
            # Tum metrik araliklari tek planda gruplanir; boylece bosluksuz
            # ardisik istek kalmaz ve istek sayisi duser (uretim ayarlarinda
            # 4 istek yerine 2). Sahada cokme tam olarak bosluksuz istekte
            # yasaniyordu.
            try:
                akim_addr = int(config["akim_addr"])
                volt_addr = int(config["volt_addr"])
                guc_addr = int(config["guc_addr"])
                isi_addr = int(config["isi_addr"])
                uretim_addr = int(config["uretim_addr"])

                await asyncio.sleep(GATEWAY_ILK_GECIKME_SN)  # Gateway icin nefes alma suresi

                degerler = await metrikleri_oku(
                    client, slave_id,
                    [
                        ("akim", akim_addr, 3),
                        ("voltaj", volt_addr, 3),
                        ("guc", guc_addr, 1),
                        ("isi", isi_addr, 1),
                        ("uretim", uretim_addr, 1),
                    ],
                    ip_address=ip_address,
                )

                if "akim" not in degerler:
                    raise Exception(f"Akim ({akim_addr}) okunamadi")
                if "voltaj" not in degerler:
                    raise Exception(f"Voltaj ({volt_addr}) okunamadi")
                if "guc" not in degerler:
                    raise Exception(f"Guc ({guc_addr}) okunamadi")
                if "isi" not in degerler:
                    raise Exception(f"Isi ({isi_addr}) okunamadi")

                raw_akim_a, raw_akim_b, raw_akim_c = degerler["akim"][:3]
                raw_volt_ab, raw_volt_bc, raw_volt_ca = degerler["voltaj"][:3]
                raw_guc = degerler["guc"][0]
                raw_isi = degerler["isi"][0]

                # Uretim soft-fail: bazi inverterlarda bu register yok.
                raw_uretim = degerler["uretim"][0] if "uretim" in degerler else 0

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
                    # Onceki metrik istegiyle arasinda gateway boslugu birakilir
                    # (eskiden 0.05 sn idi, yani pratikte bosluksuz).
                    await asyncio.sleep(GATEWAY_ALARM_GECIKME_SN)
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

                            # Her istek oncesi bosluk: bu dongu eskiden hem
                            # register'lar arasinda hem holding/input denemeleri
                            # arasinda bosluksuz istek gonderiyordu.
                            await asyncio.sleep(GATEWAY_ISTEK_ARASI_SN)
                            rr_alarm = await client.read_holding_registers(address=a_addr, count=a_count, slave=slave_id)
                            if rr_alarm.isError():
                                await asyncio.sleep(GATEWAY_ISTEK_ARASI_SN)
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
