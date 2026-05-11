"""
Solar Monitor - Prometheus Dışa Aktarıcı
=========================================
Grafana ve Prometheus sistemleri ile veri paylaşımı için
Modbus kayıtlarını Prometheus formatındaki (metric) HTTP `/metrics` 
arayüzüne dönüştürerek yayınlar.
"""

import time
import logging
from prometheus_client import start_http_server, Gauge
import veritabani
from config import setup_logging

logger = setup_logging("prometheus_exporter")

# -----------------
# Prometheus Metrics (Gauges)
# -----------------
# Her bir metrik (Gauge) "solar_" prefixiyle başlar ve cihazın slave_id'sini etiket (label) olarak tutar.

solar_guc = Gauge('solar_power_watts', 'Inverter Anlik Uretim Gucu', ['slave_id', 'fabrika'])
solar_voltaj = Gauge('solar_voltage_volts', 'Inverter DC Voltaj Degeri', ['slave_id', 'fabrika'])
solar_akim = Gauge('solar_current_amps', 'Inverter DC Akim Degeri', ['slave_id', 'fabrika'])
solar_sicaklik = Gauge('solar_temperature_celsius', 'Inverter İc Sicakligi', ['slave_id', 'fabrika'])
solar_hata = Gauge('solar_error_status', 'Inverter Hata Kodu Durumu (107 ve 111)', ['slave_id', 'register', 'fabrika'])

def update_metrics():
    """
    Veritabanından en güncel invertör ölçümlerini çeker ve
    Prometheus metriklerini bu değerlere göre günceller.
    """
    try:
        from veritabani import FABRIKALAR
        from models import CihazDurumu
        for fab_id in FABRIKALAR:
            cihaz_durumlari = veritabani.tum_cihazlarin_son_durumu(fab_id)
            
            for cihaz in cihaz_durumlari:
                padded_cihaz = list(cihaz) + [0] * max(0, 19 - len(cihaz))
                cd = CihazDurumu(*padded_cihaz[:19])
                
                s_id = str(cd.slave_id)
                
                # Prometheus ölçüm ibrelerini (gauge) güncelle
                solar_guc.labels(slave_id=s_id, fabrika=fab_id).set(cd.guc)
                solar_voltaj.labels(slave_id=s_id, fabrika=fab_id).set(cd.voltaj)
                solar_akim.labels(slave_id=s_id, fabrika=fab_id).set(cd.akim)
                solar_sicaklik.labels(slave_id=s_id, fabrika=fab_id).set(cd.sicaklik)
                
                # Tüm Hata kodlarını ayrı labellarla kayıt et
                hatalar = {
                    "107": cd.hata_kodu or 0,
                    "109": cd.hata_kodu_109 or 0,
                    "111": cd.hata_kodu_111 or 0,
                    "112": cd.hata_kodu_112 or 0,
                    "114": cd.hata_kodu_114 or 0,
                    "115": cd.hata_kodu_115 or 0,
                    "116": cd.hata_kodu_116 or 0,
                    "117": cd.hata_kodu_117 or 0,
                    "118": cd.hata_kodu_118 or 0,
                    "119": cd.hata_kodu_119 or 0,
                    "120": cd.hata_kodu_120 or 0,
                    "121": cd.hata_kodu_121 or 0,
                    "122": cd.hata_kodu_122 or 0,
                }
                
                for reg, val in hatalar.items():
                    solar_hata.labels(slave_id=s_id, register=reg, fabrika=fab_id).set(val)
            
    except Exception as e:
        logger.error(f"Prometheus metrik guncelleme hatasi: {e}")

import os

def start_exporter(port=None, update_interval=5):
    """
    Prometheus metrics sunucusunu başlatır ve sonsuz döngüde metrikleri günceller.
    """
    port = port or int(os.getenv("PROMETHEUS_PORT", 9100))
    logger.info(f"Prometheus Exporter http://0.0.0.0:{port}/metrics adresinde baslatiliyor...")
    try:
        start_http_server(port)
        
        while True:
            update_metrics()
            time.sleep(update_interval)
            
    except Exception as e:
        logger.critical(f"Prometheus sunucusu yaniti kesti: {e}")

if __name__ == "__main__":
    start_exporter()
