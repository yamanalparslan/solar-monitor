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
        for fab_id in FABRIKALAR:
            # Tuple: (slave_id, zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_109, ...)
            cihaz_durumlari = veritabani.tum_cihazlarin_son_durumu(fab_id)
            
            for cihaz in cihaz_durumlari:
                s_id = str(cihaz[0])
                guc = cihaz[2]
                voltaj = cihaz[3]
                akim = cihaz[4]
                sicaklik = cihaz[5]
                hk107 = cihaz[6]
                hk109 = cihaz[7] if len(cihaz) > 7 else 0
                
                # Prometheus ölçüm ibrelerini (gauge) güncelle
                solar_guc.labels(slave_id=s_id, fabrika=fab_id).set(guc)
                solar_voltaj.labels(slave_id=s_id, fabrika=fab_id).set(voltaj)
                solar_akim.labels(slave_id=s_id, fabrika=fab_id).set(akim)
                solar_sicaklik.labels(slave_id=s_id, fabrika=fab_id).set(sicaklik)
                
                # Hata kodlarını ayrı labellarla kayıt et
                solar_hata.labels(slave_id=s_id, register="107", fabrika=fab_id).set(hk107)
                solar_hata.labels(slave_id=s_id, register="109", fabrika=fab_id).set(hk109)
            
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
