import sqlite3
import psycopg2
import os
import sys

def migrate():
    sqlite_db_path = "data/solar_log.db"
    
    if not os.path.exists(sqlite_db_path):
        print(f"SQLite veritabanı bulunamadı: {sqlite_db_path}. Göç edilecek veri yok.")
        return

    print("PostgreSQL bağlantısı kuruluyor...")
    try:
        pg_conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "solar_db"),
            user=os.getenv("POSTGRES_USER", "solar_user"),
            password=os.getenv("POSTGRES_PASSWORD", "solar_pass_2026")
        )
        pg_cursor = pg_conn.cursor()
    except Exception as e:
        print(f"PostgreSQL bağlantı hatası: {e}")
        sys.exit(1)

    print("SQLite bağlantısı kuruluyor...")
    sl_conn = sqlite3.connect(sqlite_db_path)
    sl_cursor = sl_conn.cursor()

    # Migrate olcumler
    print("Olcumler tablosu göç ediliyor...")
    try:
        sl_cursor.execute("SELECT fabrika_id, slave_id, zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112, hata_kodu_114, hata_kodu_115, hata_kodu_116, hata_kodu_117, hata_kodu_118, hata_kodu_119, hata_kodu_120, hata_kodu_121, hata_kodu_122, modbus_uretim FROM olcumler")
        olcumler_rows = sl_cursor.fetchall()
        
        if olcumler_rows:
            pg_cursor.executemany("""
                INSERT INTO olcumler (fabrika_id, slave_id, zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112, hata_kodu_114, hata_kodu_115, hata_kodu_116, hata_kodu_117, hata_kodu_118, hata_kodu_119, hata_kodu_120, hata_kodu_121, hata_kodu_122, modbus_uretim)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, olcumler_rows)
            print(f"{len(olcumler_rows)} ölçüm kaydı aktarıldı.")
    except Exception as e:
        print("Olcumler aktarılırken hata (bazi sutunlar eksik olabilir):", e)

    # Migrate ayarlar
    print("Ayarlar tablosu göç ediliyor...")
    try:
        sl_cursor.execute("SELECT anahtar, deger, aciklama, fabrika_id, guncelleme_zamani FROM ayarlar")
        ayarlar_rows = sl_cursor.fetchall()
        if ayarlar_rows:
            pg_cursor.executemany("""
                INSERT INTO ayarlar (anahtar, deger, aciklama, fabrika_id, guncelleme_zamani)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (fabrika_id, anahtar) DO UPDATE SET deger = EXCLUDED.deger
            """, ayarlar_rows)
            print(f"{len(ayarlar_rows)} ayar kaydı aktarıldı.")
    except Exception as e:
        print("Ayarlar aktarılırken hata:", e)

    # Migrate audit_log
    print("Audit Log tablosu göç ediliyor...")
    try:
        sl_cursor.execute("SELECT fabrika_id, kullanici, islem, detay, zaman FROM audit_log")
        audit_rows = sl_cursor.fetchall()
        if audit_rows:
            pg_cursor.executemany("""
                INSERT INTO audit_log (fabrika_id, kullanici, islem, detay, zaman)
                VALUES (%s, %s, %s, %s, %s)
            """, audit_rows)
            print(f"{len(audit_rows)} log kaydı aktarıldı.")
    except Exception as e:
        print("Audit log aktarılırken hata:", e)

    pg_conn.commit()
    pg_conn.close()
    sl_conn.close()
    print("Göç işlemi başarıyla tamamlandı!")

if __name__ == "__main__":
    migrate()
