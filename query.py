"""
Solar Monitor - Gelişmiş Sorgu (Query) Aracı
===========================================
Sistem yöneticilerinin hızlıca veritabanını tarayarak
spesifik sorunları bulması için çalışan bir konsol uygulamasıdır.
Kullanım:
  python query.py --cihaz 1 --limit 5
  python query.py --hatalar
"""

import argparse
import sqlite3
import pandas as pd
from config import config

def run_query(query_str, params=()):
    try:
        conn = sqlite3.connect(config.DB_NAME)
        df = pd.read_sql_query(query_str, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        print(f"Hata: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Veritabani Sorgu Araci")
    parser.add_argument("--cihaz", type=int, help="Belirli bir cihazin (slave_id) loglarini getirir.")
    parser.add_argument("--limit", type=int, default=10, help="Kac satir veri cekilecegi.")
    parser.add_argument("--hatalar", action="store_true", help="Sadece 107 veya 111 registerindaki hatalari goster.")
    
    args = parser.parse_args()

    q = "SELECT slave_id, zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112, hata_kodu_114, hata_kodu_115, hata_kodu_116, hata_kodu_117, hata_kodu_118, hata_kodu_119, hata_kodu_120, hata_kodu_121, hata_kodu_122 FROM olcumler WHERE 1=1"
    params = []

    if args.cihaz:
        q += " AND slave_id = ?"
        params.append(args.cihaz)

    if args.hatalar:
        q += " AND (hata_kodu > 0 OR hata_kodu_109 > 0 OR hata_kodu_111 > 0 OR hata_kodu_112 > 0 OR hata_kodu_114 > 0 OR hata_kodu_115 > 0 OR hata_kodu_116 > 0 OR hata_kodu_117 > 0 OR hata_kodu_118 > 0 OR hata_kodu_119 > 0 OR hata_kodu_120 > 0 OR hata_kodu_121 > 0 OR hata_kodu_122 > 0)"

    q += " ORDER BY zaman DESC LIMIT ?"
    params.append(args.limit)

    print(f"\n--- Sorgu Sonuclari (Limit: {args.limit}) ---")
    df = run_query(q, tuple(params))
    
    if df is not None and not df.empty:
        print(df.to_string(index=False))
    else:
        print("Sorguya uygun veri bulunamadi.")

if __name__ == "__main__":
    main()
