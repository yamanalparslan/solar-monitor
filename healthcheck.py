#!/usr/bin/env python3
"""
Solar Monitor - Healthcheck Betiği
====================================
Docker ortamı veya izleme sistemleri için uygulamanın ve veritabanının
sağlıklı çalışıp çalışmadığını test eder (Exit code kullanır).
"""

import sys
import sqlite3
import veritabani
from modbus_diagnostics import load_runtime_config, probe_target

def test_database():
    """Veritabanı erişimini ve tablo yapısını doğrular."""
    try:
        conn = sqlite3.connect(veritabani.DB_NAME)
        cursor = conn.cursor()
        
        # Sadece basit bir sorgu atarak DB okumasını doğrula
        cursor.execute("SELECT 1 FROM ayarlar LIMIT 1")
        conn.close()
        return True
    except Exception as e:
        print(f"Veritabani baglanti veya sorgu hatasi: {e}")
        return False

def run_healthcheck():
    """Tüm denetimleri koşturup EXIT_CODE ile sonucu bildirir."""
    
    # Kural 1: Veritabanı sağlıklı olmalı
    db_ok = test_database()
    if not db_ok:
        print("HEALTHCHECK FAILED - Database connection error.")
        sys.exit(1)
        
    # Kural 2: (İsteğe Bağlı) Modbus uygulama seviyesi testi
    # Local ortam testlerinde inverter olmayacağı için bu adım sadece loglanıyor, çökmeye sebep olmaz
    runtime_config = load_runtime_config()
    probe_result = probe_target(runtime_config, exhaustive=False, timeout=1.0)
    if not probe_result["tcp_open"]:
        print(
            f"Warning: Modbus target {runtime_config.target_ip}:{runtime_config.target_port} "
            "TCP olarak erisilemiyor."
        )
    elif not probe_result["successes"]:
        print(
            f"Warning: TCP acik ancak {runtime_config.target_ip}:{runtime_config.target_port} "
            "hedefinden Modbus cevabi alinamadi."
        )
    
    # Testler başarılıysa
    print("HEALTHCHECK PASSED")
    sys.exit(0)

if __name__ == "__main__":
    run_healthcheck()
