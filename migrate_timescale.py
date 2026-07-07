import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def migrate():
    # .env yükle (Eğer varsa)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    db_name = os.getenv("POSTGRES_DB", "solar_db")
    user = os.getenv("POSTGRES_USER", "solar_user")
    password = os.getenv("POSTGRES_PASSWORD", "solar_pass_2026")
    # Docker internal network host
    host = "solar_postgres" 
    port = os.getenv("POSTGRES_PORT", "5432")

    print(f"Veritabanına bağlanılıyor: {host}:{port} ({db_name})")
    
    try:
        conn = psycopg2.connect(dbname=db_name, user=user, password=password, host=host, port=port)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("1. TimescaleDB eklentisi kontrol ediliyor...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
        
        print("2. 'olcumler' tablosunun Hypertable olup olmadığı kontrol ediliyor...")
        cursor.execute("""
            SELECT count(*) 
            FROM timescaledb_information.hypertables 
            WHERE hypertable_name = 'olcumler'
        """)
        is_hyper = cursor.fetchone()[0] > 0
        
        if not is_hyper:
            print(" - 'olcumler' tablosu normal bir tablo, Hypertable'a dönüştürülüyor...")
            
            # Primary Key (id) varsa kaldır (Hypertable'larda zamana dayalı partition olduğu için id PK olamaz)
            print(" - Primary Key (id) kaldırılıyor...")
            try:
                cursor.execute("ALTER TABLE olcumler DROP CONSTRAINT IF EXISTS olcumler_pkey;")
            except Exception as e:
                print(f"   [!] Hata (önemsiz olabilir): {e}")

            # Hypertable'a çevir (migrate_data => TRUE ile mevcut verileri koru)
            print(" - Hypertable'a çevriliyor (Bu işlem mevcut veri boyutuna göre birkaç dakika sürebilir)...")
            cursor.execute("SELECT create_hypertable('olcumler', 'zaman', migrate_data => TRUE);")
            print(" - Dönüştürme başarılı!")
        else:
            print(" - 'olcumler' zaten bir Hypertable.")

        # 3. Continuous Aggregate (Saatlik Özet) oluştur
        print("3. Continuous Aggregate (Saatlik Özet) view oluşturuluyor...")
        try:
            # Drop it if exists to recreate safely (optional, but good for idempotency)
            # Cannot use DROP MATERIALIZED VIEW IF EXISTS on continuous aggregates directly sometimes, 
            # but we can try.
            cursor.execute("DROP MATERIALIZED VIEW IF EXISTS olcumler_saatlik CASCADE;")
            
            cursor.execute("""
                CREATE MATERIALIZED VIEW olcumler_saatlik
                WITH (timescaledb.continuous) AS
                SELECT 
                    time_bucket('1 hour', zaman) AS zaman_saati,
                    fabrika_id,
                    slave_id,
                    AVG(guc) AS guc,
                    AVG(voltaj) AS voltaj,
                    AVG(akim) AS akim,
                    AVG(sicaklik) AS sicaklik,
                    MAX(modbus_uretim) AS max_uretim
                FROM olcumler
                GROUP BY time_bucket('1 hour', zaman), fabrika_id, slave_id;
            """)
            print(" - Saatlik özet tablosu oluşturuldu.")
        except Exception as e:
            print(f" - Saatlik özet tablosu zaten var veya bir hata oluştu: {e}")

        # 4. Refresh Policy ekle (Her saat başı güncellensin)
        print("4. Continuous Aggregate için Refresh Policy ekleniyor...")
        try:
            # Remove existing policy if any
            cursor.execute("SELECT remove_continuous_aggregate_policy('olcumler_saatlik', if_exists => true);")
            cursor.execute("""
                SELECT add_continuous_aggregate_policy('olcumler_saatlik',
                    start_offset => INTERVAL '3 days',
                    end_offset => INTERVAL '1 hour',
                    schedule_interval => INTERVAL '1 hour');
            """)
            print(" - Refresh policy başarıyla eklendi.")
        except Exception as e:
            print(f" - Refresh policy eklenirken hata (veya zaten var): {e}")

        # 5. Veri Silme Kuralı (Retention Policy) ekle - Saniyelik veriler 30 gün sonra silinsin
        print("5. 30 Günlük Veri Saklama (Retention) Policy ekleniyor...")
        try:
            cursor.execute("SELECT remove_retention_policy('olcumler', if_exists => true);")
            cursor.execute("SELECT add_retention_policy('olcumler', INTERVAL '30 days');")
            print(" - 30 günlük retention policy başarıyla eklendi.")
        except Exception as e:
            print(f" - Retention policy eklenirken hata: {e}")

        print("\nTÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!")
        conn.close()

    except Exception as e:
        print(f"\n[KRITIK HATA] Migration sırasında hata oluştu: {e}")

if __name__ == "__main__":
    migrate()
