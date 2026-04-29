"""
Solar Monitor - Asenkron Veri Toplayıcı
========================================
Çok sayıda invertörün paralel olarak taranmasını sağlayarak
gecikmeleri engelleyen (non-blocking) Modbus okuma modülü.
"""

import asyncio
import logging
import time
from pymodbus.client import AsyncModbusTcpClient
from collector import load_config, otomatik_veri_temizle
import utils
import veritabani
from config import setup_logging

logger = setup_logging("async_collector")

async def asenkron_read_single_register(client, address, slave_id):
    """Tek bir register'i asenkron okur."""
    try:
        rr = await client.read_holding_registers(address=address, count=1, slave=slave_id)
        if rr.isError():
            return None
        return rr.registers[0]
    except Exception as e:
        logger.debug(f"Asenkron okuma hatasi (ID {slave_id}, Addr {address}): {e}")
        return None

async def read_device_async(client, slave_id, target_config):
    """Belirli bir cihazin (slave_id) tum degerlerini paralel veya sirali asenkron okur."""
    try:
        if not client.connected:
            await client.connect()
            await asyncio.sleep(0.1)

        raw_volt = await asenkron_read_single_register(client, target_config["volt_addr"], slave_id)
        if raw_volt is None:
            return slave_id, None

        raw_akim = await asenkron_read_single_register(client, target_config["akim_addr"], slave_id)
        raw_isi = await asenkron_read_single_register(client, target_config["isi_addr"], slave_id)

        h_voltaj = utils.to_signed16(raw_volt) * target_config["volt_scale"]
        h_akim = 0 if raw_akim is None else utils.to_signed16(raw_akim) * target_config["akim_scale"]

        veriler = {
            "guc": h_voltaj * h_akim,
            "voltaj": h_voltaj,
            "akim": h_akim,
            "sicaklik": 0 if raw_isi is None else utils.decode_temperature_register(raw_isi, target_config["isi_scale"]),
        }

        # Alarmlari oku (Register 107, 109, 111, 112, 114, 115, 116, 117-122)
        for reg in target_config["alarm_registers"]:
            try:
                r_hata = await client.read_holding_registers(
                    address=reg["addr"],
                    count=reg.get("count", 2),
                    slave=slave_id
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

        return slave_id, veriler

    except Exception as exc:
        logger.error(f"ID {slave_id} baglanti kesintisi: {exc}")
        return slave_id, None

async def main_loop():
    veritabani.init_db()
    from veritabani import FABRIKALAR
    print("==================================================")
    print("ASENKRON COLLECTOR BAŞLATILDI (Çoklu Fabrika)")
    print("==================================================")

    # Her fabrika için ayrı config ve client
    fabrika_configs = {}
    fabrika_clients = {}
    for fab_id in FABRIKALAR:
        cfg = load_config(fab_id)
        fabrika_configs[fab_id] = cfg
        fabrika_clients[fab_id] = AsyncModbusTcpClient(
            cfg["target_ip"], port=cfg["target_port"], timeout=2.0
        )
        print(f"[{fab_id}] Hedef: {cfg['target_ip']}:{cfg['target_port']} | ID'ler: {cfg['slave_ids']}")
    
    otomatik_veri_temizle(fabrika_configs[list(FABRIKALAR.keys())[0]])

    while True:
        start_time = time.time()
        
        for fab_id in FABRIKALAR:
            # Her döngüde ayarları güncelle
            yeni_config = load_config(fab_id)
            current_config = fabrika_configs[fab_id]
            client = fabrika_clients[fab_id]

            if (yeni_config["target_ip"] != current_config["target_ip"] or 
                yeni_config["target_port"] != current_config["target_port"]):
                print(f"\n[{fab_id}] Hedef IP/Port degisti, AsyncClient yenileniyor...")
                client.close()
                client = AsyncModbusTcpClient(yeni_config["target_ip"], port=yeni_config["target_port"], timeout=2.0)
                fabrika_clients[fab_id] = client
            fabrika_configs[fab_id] = yeni_config
            
            # Tum slave cihazlari icin asyncio gorevlerini olustur (Parallel fetch)
            tasks = [read_device_async(client, dev_id, yeni_config) for dev_id in yeni_config["slave_ids"]]
            results = await asyncio.gather(*tasks)

            # Sonuclari isleme
            for slave_id, data in results:
                if data:
                    veritabani.veri_ekle(slave_id, data, fabrika_id=fab_id)
                    h107 = data.get("hata_kodu", 0)
                    h109 = data.get("hata_kodu_109", 0)
                    h111 = data.get("hata_kodu_111", 0)
                    print(f"[Async/{fab_id}] ID {slave_id} | Guc: {data['guc']}W | H107:{h107} H109:{h109} H111:{h111}")
                else:
                    print(f"[Async/{fab_id}] ID {slave_id} Baglanti Yok")

        elapsed = time.time() - start_time
        min_refresh = min(c["refresh_rate"] for c in fabrika_configs.values())
        kalan_bekleme = max(0.5, min_refresh - elapsed)
        await asyncio.sleep(kalan_bekleme)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Asenkron Collector durduruldu.")

