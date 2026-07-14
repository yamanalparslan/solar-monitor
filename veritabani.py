import psycopg2
from psycopg2.extras import DictCursor
import os
from datetime import datetime, timedelta

def get_db_connection():
    """Çoklu container ve thread erişimi için PostgreSQL bağlantısı oluşturur."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "solar_db")
    user = os.getenv("POSTGRES_USER", "solar_user")
    password = os.getenv("POSTGRES_PASSWORD", "solar_pass_2026")

    try:
        # psycopg2 default is thread-safe for new connections
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        return conn
    except Exception as e:
        print(f"[DB_HATA] PostgreSQL bağlantısı kurulamadı: {e}")
        return None

# ── Fabrika Tanımları ──
FABRIKALAR = {
    "mekanik": {"ad": "Mekanik Fabrika", "ikon": "🔧", "varsayilan_ip": "10.35.14.10"},
    "uretim":  {"ad": "Üretim Fabrika",  "ikon": "🏭", "varsayilan_ip": "10.35.14.11"},
}
VARSAYILAN_FABRIKA = "mekanik"

def init_db():
    print("[DB] PostgreSQL Veritabanı Başlatılıyor...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Ölçümler Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS olcumler (
            id SERIAL,
            fabrika_id VARCHAR(50) DEFAULT 'mekanik',
            slave_id INTEGER, 
            zaman TIMESTAMP,
            guc DOUBLE PRECISION,
            voltaj DOUBLE PRECISION,
            akim DOUBLE PRECISION,
            sicaklik DOUBLE PRECISION,
            hata_kodu INTEGER DEFAULT 0,
            hata_kodu_109 INTEGER DEFAULT 0,
            hata_kodu_111 INTEGER DEFAULT 0,
            hata_kodu_112 INTEGER DEFAULT 0,
            hata_kodu_114 INTEGER DEFAULT 0,
            hata_kodu_115 INTEGER DEFAULT 0,
            hata_kodu_116 INTEGER DEFAULT 0,
            hata_kodu_117 INTEGER DEFAULT 0,
            hata_kodu_118 INTEGER DEFAULT 0,
            hata_kodu_119 INTEGER DEFAULT 0,
            hata_kodu_120 INTEGER DEFAULT 0,
            hata_kodu_121 INTEGER DEFAULT 0,
            hata_kodu_122 INTEGER DEFAULT 0,
            modbus_uretim DOUBLE PRECISION DEFAULT 0,
            voltaj_ab DOUBLE PRECISION DEFAULT 0,
            voltaj_bc DOUBLE PRECISION DEFAULT 0,
            voltaj_ca DOUBLE PRECISION DEFAULT 0,
            akim_a DOUBLE PRECISION DEFAULT 0,
            akim_b DOUBLE PRECISION DEFAULT 0,
            akim_c DOUBLE PRECISION DEFAULT 0
        )
    """)
    
    # TimescaleDB Setup
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
        cursor.execute("SELECT create_hypertable('olcumler', 'zaman', if_not_exists => TRUE);")
        
        cursor.execute("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS olcumler_saatlik
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
        
        try:
            cursor.execute("SELECT add_continuous_aggregate_policy('olcumler_saatlik', start_offset => INTERVAL '3 days', end_offset => INTERVAL '1 hour', schedule_interval => INTERVAL '1 hour');")
        except Exception:
            conn.rollback() # recover from failed transaction
        
        try:
            cursor.execute("SELECT add_retention_policy('olcumler', INTERVAL '30 days');")
        except Exception:
            conn.rollback()

    except Exception as e:
        conn.rollback()
        print(f"TimescaleDB initialization error: {e}")

    # Migration: Add new columns if they don't exist
    try:
        cursor.execute("ALTER TABLE olcumler ADD COLUMN IF NOT EXISTS voltaj_ab DOUBLE PRECISION DEFAULT 0;")
        cursor.execute("ALTER TABLE olcumler ADD COLUMN IF NOT EXISTS voltaj_bc DOUBLE PRECISION DEFAULT 0;")
        cursor.execute("ALTER TABLE olcumler ADD COLUMN IF NOT EXISTS voltaj_ca DOUBLE PRECISION DEFAULT 0;")
        cursor.execute("ALTER TABLE olcumler ADD COLUMN IF NOT EXISTS akim_a DOUBLE PRECISION DEFAULT 0;")
        cursor.execute("ALTER TABLE olcumler ADD COLUMN IF NOT EXISTS akim_b DOUBLE PRECISION DEFAULT 0;")
        cursor.execute("ALTER TABLE olcumler ADD COLUMN IF NOT EXISTS akim_c DOUBLE PRECISION DEFAULT 0;")
    except Exception as e:
        conn.rollback()
        print(f"Migration hatasi: {e}")

    # Index: zaman
    try:
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_zaman 
            ON olcumler(zaman DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fabrika_slave_zaman 
            ON olcumler(fabrika_id, slave_id, zaman DESC)
        """)
    except Exception as e:
        conn.rollback()

    # 2. Ayarlar Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ayarlar (
            anahtar VARCHAR(100),
            deger TEXT,
            aciklama TEXT,
            fabrika_id VARCHAR(50) DEFAULT 'mekanik',
            guncelleme_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (fabrika_id, anahtar)
        )
    """)

    # 3. Varsayılan Ayarları Ekle
    for fab_id, fab_info in FABRIKALAR.items():
        varsayilan_ayarlar = [
            ('refresh_rate', '60', 'Veri çekme sıklığı (saniye)'),
            ('guc_scale', '1.0', 'Güç çarpanı'),
            ('volt_scale', '1.0', 'Voltaj çarpanı'),
            ('akim_scale', '0.1', 'Akım çarpanı'),
            ('isi_scale', '1.0', 'Sıcaklık çarpanı'),
            ('guc_addr', '70', 'Güç register adresi'),
            ('volt_addr', '71', 'Voltaj register adresi'),
            ('akim_addr', '72', 'Akım register adresi'),
            ('isi_addr', '73', 'Sıcaklık register adresi'),
            ('uretim_addr', '36', 'Günlük Üretim register adresi'),
            ('uretim_scale', '1.0', 'Üretim çarpanı'),
            ('target_ip', fab_info['varsayilan_ip'], 'Modbus IP adresi'),
            ('target_port', '502', 'Modbus Port'),
            ('slave_ids', '1,2,3', 'İnverter ID listesi'),
            ('veri_saklama_gun', '365', 'Veri saklama süresi (gün) - 0: Sınırsız'),
            ('lat', '38.4237', 'Enlem (Latitude)'),
            ('lon', '27.1428', 'Boylam (Longitude)')
        ]
        for anahtar, deger, aciklama in varsayilan_ayarlar:
            try:
                cursor.execute("""
                    INSERT INTO ayarlar (fabrika_id, anahtar, deger, aciklama)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (fabrika_id, anahtar) DO NOTHING
                """, (fab_id, anahtar, deger, aciklama))
            except Exception as e:
                print(f"[WARN] Varsayilan ayar ekleme hatasi: {e}")

    # 5. Audit Log Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            fabrika_id VARCHAR(50) DEFAULT 'mekanik',
            kullanici VARCHAR(100) DEFAULT 'admin',
            islem VARCHAR(100),
            detay TEXT,
            zaman TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 6. Hata Log Tablosu (Stateful Alarms)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hata_log (
            id SERIAL PRIMARY KEY,
            fabrika_id VARCHAR(50),
            slave_id INTEGER,
            register_no INTEGER,
            hata_kodu BIGINT,
            baslangic_zamani TIMESTAMP,
            bitis_zamani TIMESTAMP,
            durum VARCHAR(20) DEFAULT 'AKTIF'
        )
    """)

    conn.commit()
    conn.close()

def ayar_oku(anahtar, varsayilan=None, fabrika_id=VARSAYILAN_FABRIKA):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT deger FROM ayarlar WHERE fabrika_id = %s AND anahtar = %s', (fabrika_id, anahtar))
        sonuc = cursor.fetchone()
        conn.close()
        if sonuc:
            return sonuc[0]
        return varsayilan
    except Exception as e:
        print(f"[WARN] Ayar okuma hatası ({anahtar}): {e}")
        return varsayilan

def ayar_yaz(anahtar, deger, fabrika_id=VARSAYILAN_FABRIKA):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ayarlar (fabrika_id, anahtar, deger, guncelleme_zamani)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (fabrika_id, anahtar) 
            DO UPDATE SET deger = EXCLUDED.deger, guncelleme_zamani = EXCLUDED.guncelleme_zamani
        """, (fabrika_id, anahtar, str(deger)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[WARN] Ayar yazma hatası ({anahtar}): {e}")
        return False

def tum_ayarlari_oku(fabrika_id: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT anahtar, deger FROM ayarlar WHERE fabrika_id = %s', (fabrika_id,))
        ayarlar = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return ayarlar
    except Exception as e:
        print(f"[WARN] tum_ayarlari_oku hatasi: {e}")
        fab_ip = FABRIKALAR.get(fabrika_id, {}).get('varsayilan_ip', '10.35.14.10')
        return {
            'refresh_rate': '60', 'guc_scale': '1.0', 'volt_scale': '1.0',
            'akim_scale': '0.1', 'isi_scale': '1.0', 'guc_addr': '70',
            'volt_addr': '71', 'akim_addr': '72', 'isi_addr': '73',
            'uretim_addr': '36', 'uretim_scale': '1.0',
            'target_ip': fab_ip, 'target_port': '502', 'slave_ids': '1,2,3',
            'veri_saklama_gun': '365', 'lat': '38.4237', 'lon': '27.1428'
        }

def hata_durumu_guncelle(cursor, fabrika_id, slave_id, register_no, hata_kodu, zaman):
    cursor.execute("""
        SELECT id, hata_kodu FROM hata_log
        WHERE fabrika_id = %s AND slave_id = %s AND register_no = %s AND durum = 'AKTIF'
    """, (fabrika_id, slave_id, register_no))
    row = cursor.fetchone()
    
    if hata_kodu > 0:
        if row:
            active_id, active_kodu = row
            if active_kodu != hata_kodu:
                # Kodu değiştiyse eskiyi kapat, yeniyi aç
                cursor.execute("UPDATE hata_log SET bitis_zamani = %s, durum = 'DUZELDI' WHERE id = %s", (zaman, active_id))
                cursor.execute("INSERT INTO hata_log (fabrika_id, slave_id, register_no, hata_kodu, baslangic_zamani, durum) VALUES (%s, %s, %s, %s, %s, 'AKTIF')", (fabrika_id, slave_id, register_no, hata_kodu, zaman))
        else:
            # Yeni hata
            cursor.execute("INSERT INTO hata_log (fabrika_id, slave_id, register_no, hata_kodu, baslangic_zamani, durum) VALUES (%s, %s, %s, %s, %s, 'AKTIF')", (fabrika_id, slave_id, register_no, hata_kodu, zaman))
    else:
        if row:
            # Hata düzeldi
            active_id = row[0]
            cursor.execute("UPDATE hata_log SET bitis_zamani = %s, durum = 'DUZELDI' WHERE id = %s", (zaman, active_id))

def veri_ekle(slave_id, data, fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    simdi = datetime.now()
    
    hk_107 = data.get('hata_kodu', 0)
    hk_109 = data.get('hata_kodu_109', 0)
    hk_111 = data.get('hata_kodu_111', 0)
    hk_112 = data.get('hata_kodu_112', 0)
    hk_114 = data.get('hata_kodu_114', 0)
    hk_115 = data.get('hata_kodu_115', 0)
    hk_116 = data.get('hata_kodu_116', 0)
    hk_117 = data.get('hata_kodu_117', 0)
    hk_118 = data.get('hata_kodu_118', 0)
    hk_119 = data.get('hata_kodu_119', 0)
    hk_120 = data.get('hata_kodu_120', 0)
    hk_121 = data.get('hata_kodu_121', 0)
    hk_122 = data.get('hata_kodu_122', 0)
    
    try:
        from models import FAULT_MAP_107, FAULT_MAP_109, FAULT_MAP_111, FAULT_MAP_112, FAULT_MAP_114, FAULT_MAP_115, FAULT_MAP_116, FAULT_MAP_117, FAULT_MAP_118, FAULT_MAP_119, FAULT_MAP_120, FAULT_MAP_121, FAULT_MAP_122
        
        def normalize_hata_kodu(kod, fault_map):
            if kod == 0: return 0
            normalized = 0
            seen = {}
            for bit in range(32):
                if (kod >> bit) & 1:
                    desc = fault_map.get(bit, "")
                    if desc and desc != "Spare":
                        if desc not in seen:
                            first_bit = bit
                            for b, d in fault_map.items():
                                if d == desc:
                                    first_bit = b
                                    break
                            seen[desc] = first_bit
                        normalized |= (1 << seen[desc])
            return normalized

        map_dict = {
            107: FAULT_MAP_107, 109: FAULT_MAP_109, 111: FAULT_MAP_111, 112: FAULT_MAP_112,
            114: FAULT_MAP_114, 115: FAULT_MAP_115, 116: FAULT_MAP_116, 117: FAULT_MAP_117,
            118: FAULT_MAP_118, 119: FAULT_MAP_119, 120: FAULT_MAP_120, 121: FAULT_MAP_121, 122: FAULT_MAP_122
        }

        # Hatalari kontrol et ve stateful logla
        hata_listesi = [
            (107, hk_107), (109, hk_109), (111, hk_111), (112, hk_112),
            (114, hk_114), (115, hk_115), (116, hk_116), (117, hk_117),
            (118, hk_118), (119, hk_119), (120, hk_120), (121, hk_121), (122, hk_122)
        ]
        for reg_no, val in hata_listesi:
            norm_val = normalize_hata_kodu(val, map_dict[reg_no])
            hata_durumu_guncelle(cursor, fabrika_id, slave_id, reg_no, norm_val, simdi)
        
        cursor.execute("""
            INSERT INTO olcumler (
                fabrika_id, slave_id, zaman, guc, voltaj, akim, sicaklik, modbus_uretim,
                hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112, 
                hata_kodu_114, hata_kodu_115, hata_kodu_116, hata_kodu_117, 
                hata_kodu_118, hata_kodu_119, hata_kodu_120, hata_kodu_121, hata_kodu_122,
                voltaj_ab, voltaj_bc, voltaj_ca, akim_a, akim_b, akim_c
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            fabrika_id, slave_id, simdi, 
            data.get('guc', 0), data.get('voltaj', 0), data.get('akim', 0), data.get('sicaklik', 0), data.get('modbus_uretim', 0),
            hk_107, hk_109, hk_111, hk_112, 
            hk_114, hk_115, hk_116, hk_117, 
            hk_118, hk_119, hk_120, hk_121, hk_122,
            data.get('voltaj_ab', 0), data.get('voltaj_bc', 0), data.get('voltaj_ca', 0),
            data.get('akim_a', 0), data.get('akim_b', 0), data.get('akim_c', 0)
        ))
        conn.commit()
    except Exception as e:
        print(f"[ERROR] veri_ekle hatasi: {e}")
    finally:
        conn.close()

def veri_kaydet(fabrika_id, slave_id, guc, voltaj, akim, sicaklik, modbus_uretim=0, hatalar=None, voltaj_ab=0, voltaj_bc=0, voltaj_ca=0, akim_a=0, akim_b=0, akim_c=0):
    if hatalar is None: hatalar = []
    try:
        conn = get_db_connection()
        if not conn: return
        cursor = conn.cursor()
        
        simdi = datetime.now()
        
        # 1. Olcum tablosuna kaydet
        query = """
            INSERT INTO olcumler (
                fabrika_id, slave_id, zaman, guc, voltaj, akim, sicaklik, modbus_uretim,
                hata_kodu_109, hata_kodu_111, hata_kodu_112, hata_kodu_114,
                hata_kodu_115, hata_kodu_116, hata_kodu_117, hata_kodu_118,
                hata_kodu_119, hata_kodu_120, hata_kodu_121, hata_kodu_122,
                voltaj_ab, voltaj_bc, voltaj_ca, akim_a, akim_b, akim_c
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
        """
        vals = (
            fabrika_id, slave_id, simdi, guc, voltaj, akim, sicaklik, modbus_uretim,
            109 in hatalar, 111 in hatalar, 112 in hatalar, 114 in hatalar,
            115 in hatalar, 116 in hatalar, 117 in hatalar, 118 in hatalar,
            119 in hatalar, 120 in hatalar, 121 in hatalar, 122 in hatalar,
            voltaj_ab, voltaj_bc, voltaj_ca, akim_a, akim_b, akim_c
        )
        cursor.execute(query, vals)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ERROR] veri_kaydet hatasi: {e}")

def son_verileri_getir(slave_id, limit=100, fabrika_id=VARSAYILAN_FABRIKA):
    try:
        slave_id = int(slave_id)
        limit = int(limit)
    except (ValueError, TypeError):
        return []

    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute("""
        SELECT zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112, hata_kodu_114, hata_kodu_115, hata_kodu_116, hata_kodu_117, hata_kodu_118, hata_kodu_119, hata_kodu_120, hata_kodu_121, hata_kodu_122, voltaj_ab, voltaj_bc, voltaj_ca, akim_a, akim_b, akim_c
        FROM olcumler WHERE fabrika_id = %s AND slave_id = %s
        ORDER BY zaman DESC LIMIT %s
    """, (fabrika_id, slave_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    return rows[::-1]

def karsilastirma_verisi_getir(slave_id, limit=2880, fabrika_id=VARSAYILAN_FABRIKA):
    try:
        slave_id = int(slave_id)
        limit = int(limit)
    except (ValueError, TypeError):
        return []

    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor()
    # dakikalık bazda gruplama yap (PostgreSQL date_trunc)
    cursor.execute("""
        SELECT 
            date_trunc('minute', zaman) as zaman_dk, 
            AVG(guc) as guc, 
            AVG(voltaj) as voltaj, 
            AVG(akim) as akim, 
            AVG(sicaklik) as sicaklik
        FROM olcumler 
        WHERE fabrika_id = %s AND slave_id = %s
          AND zaman >= NOW() - %s * INTERVAL '1 minute'
        GROUP BY zaman_dk
        ORDER BY zaman_dk DESC 
        LIMIT %s
    """, (fabrika_id, slave_id, limit, limit))
    rows = cursor.fetchall()
    conn.close()
    
    return rows[::-1]


def tum_cihazlarin_son_durumu(fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT ON (slave_id) 
               slave_id, zaman as son_zaman, guc, voltaj, akim, sicaklik,
               hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112,
               hata_kodu_114, hata_kodu_115, hata_kodu_116,
               hata_kodu_117, hata_kodu_118, hata_kodu_119,
               hata_kodu_120, hata_kodu_121, hata_kodu_122
        FROM olcumler
        WHERE fabrika_id = %s
        ORDER BY slave_id ASC, zaman DESC
    """, (fabrika_id,))
    rows = cursor.fetchall()
    conn.close()
    
    formatted_rows = []
    for r in rows:
        formatted_rows.append((r[0], str(r[1]), *r[2:]))
        
    return formatted_rows

def db_temizle(fabrika_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if fabrika_id:
            cursor.execute('DELETE FROM olcumler WHERE fabrika_id = %s', (fabrika_id,))
        else:
            cursor.execute('DELETE FROM olcumler')
        conn.commit()
        return True
    except Exception as e:
        print(f"[WARN] db_temizle hatasi: {e}")
        return False
    finally:
        conn.close()

def eski_verileri_temizle(gun_sayisi=None, fabrika_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if gun_sayisi is None:
            gun_sayisi = int(ayar_oku('veri_saklama_gun', '365'))
        
        if gun_sayisi == 0:
            return 0
        
        tarih = datetime.now() - timedelta(days=gun_sayisi)
        if fabrika_id:
            cursor.execute('DELETE FROM olcumler WHERE zaman < %s AND fabrika_id = %s', (tarih, fabrika_id))
        else:
            cursor.execute('DELETE FROM olcumler WHERE zaman < %s', (tarih,))
        silinen = cursor.rowcount
        conn.commit()
        
        if silinen > 0:
            print(f"[CLEAN] {silinen} eski kayıt temizlendi ({gun_sayisi} günden eski)")
        
        return silinen
    except Exception as e:
        print(f"[WARN] Eski veri temizleme hatası: {e}")
        return 0
    finally:
        conn.close()

def veritabani_istatistikleri(fabrika_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if fabrika_id:
            cursor.execute('SELECT COUNT(*) FROM olcumler WHERE fabrika_id = %s', (fabrika_id,))
        else:
            cursor.execute('SELECT COUNT(*) FROM olcumler')
        toplam_kayit = cursor.fetchone()[0]
        
        if fabrika_id:
            cursor.execute('SELECT MIN(zaman), MAX(zaman) FROM olcumler WHERE fabrika_id = %s', (fabrika_id,))
        else:
            cursor.execute('SELECT MIN(zaman), MAX(zaman) FROM olcumler')
        tarih_araligi = cursor.fetchone()
        
        if fabrika_id:
            cursor.execute('''SELECT slave_id, COUNT(*), MIN(zaman), MAX(zaman)
                FROM olcumler WHERE fabrika_id = %s GROUP BY slave_id ORDER BY slave_id''', (fabrika_id,))
        else:
            cursor.execute('''SELECT slave_id, COUNT(*), MIN(zaman), MAX(zaman)
                FROM olcumler GROUP BY slave_id ORDER BY slave_id''')
        cihaz_istatistik = cursor.fetchall()
        
        cursor.execute("SELECT pg_database_size(current_database())")
        db_boyut_bytes = cursor.fetchone()[0]
        db_boyut = db_boyut_bytes / (1024 * 1024)
        
        cihaz_istatistik_str = []
        for c in cihaz_istatistik:
            cihaz_istatistik_str.append((c[0], c[1], str(c[2]) if c[2] else None, str(c[3]) if c[3] else None))
            
        return {
            'toplam_kayit': toplam_kayit,
            'ilk_kayit': str(tarih_araligi[0]) if tarih_araligi[0] else None,
            'son_kayit': str(tarih_araligi[1]) if tarih_araligi[1] else None,
            'cihaz_istatistik': cihaz_istatistik_str,
            'db_boyut_mb': round(db_boyut, 2)
        }
    except Exception as e:
        print(f"[WARN] İstatistik hatası: {e}")
        return None
    finally:
        conn.close()

def saatlik_ozet_getir(slave_id, baslangic_tarihi, bitis_tarihi, fabrika_id=VARSAYILAN_FABRIKA):
    """
    TimescaleDB continuous aggregate tablosundan saatlik bazda sıkıştırılmış verileri getirir.
    Eski tarihli uzun raporlar için çok hızlıdır.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                zaman_saati as ts, 
                guc, voltaj, akim, sicaklik, max_uretim as modbus_uretim
            FROM olcumler_saatlik
            WHERE slave_id = %s AND fabrika_id = %s
            AND zaman_saati >= %s AND zaman_saati <= %s
            ORDER BY zaman_saati ASC
        '''
        
        cursor.execute(query, (slave_id, fabrika_id, baslangic_tarihi, bitis_tarihi))
        rows = cursor.fetchall()
        conn.close()
        
        return rows
    except Exception as e:
        print(f"[WARN] Saatlik ozet verisi cekme hatasi: {e}")
        return []

def tarih_araliginda_ortalamalar(baslangic, bitis, slave_id=None, fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    cursor = conn.cursor()
    baslangic_str = f"{baslangic} 00:00:00"
    bitis_str = f"{bitis} 23:59:59"
    try:
        if slave_id:
            cursor.execute('''SELECT AVG(guc), AVG(voltaj), AVG(akim), AVG(sicaklik), MAX(guc), MIN(guc), COUNT(*)
                FROM olcumler WHERE fabrika_id = %s AND zaman BETWEEN %s AND %s AND slave_id = %s''',
                (fabrika_id, baslangic_str, bitis_str, slave_id))
        else:
            cursor.execute('''SELECT AVG(guc), AVG(voltaj), AVG(akim), AVG(sicaklik), MAX(guc), MIN(guc), COUNT(*)
                FROM olcumler WHERE fabrika_id = %s AND zaman BETWEEN %s AND %s''',
                (fabrika_id, baslangic_str, bitis_str))
        sonuc = cursor.fetchone()
        return {'ort_guc': sonuc[0] or 0, 'ort_voltaj': sonuc[1] or 0, 'ort_akim': sonuc[2] or 0,
                'ort_sicaklik': sonuc[3] or 0, 'max_guc': sonuc[4] or 0, 'min_guc': sonuc[5] or 0,
                'toplam_olcum': sonuc[6] or 0}
    except Exception as e:
        print(f"[WARN] Ortalama hesaplama hatası: {e}")
        return None
    finally:
        conn.close()

def gunluk_uretim_hesapla(tarih, slave_id=None, fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    cursor = conn.cursor()
    baslangic = f"{tarih} 00:00:00"
    bitis = f"{tarih} 23:59:59"
    try:
        if slave_id:
            cursor.execute('''SELECT AVG(guc), COUNT(*), MAX(CASE WHEN guc > 0 THEN modbus_uretim ELSE 0 END) FROM olcumler
                WHERE fabrika_id = %s AND zaman BETWEEN %s AND %s AND slave_id = %s''',
                (fabrika_id, baslangic, bitis, slave_id))
            sonuc = cursor.fetchone()
            ort_guc = sonuc[0] or 0
            olcum_sayisi = sonuc[1] or 0
            modbus_uretim = sonuc[2] or 0
        else:
            cursor.execute('''SELECT AVG(guc), SUM(olcum_sayisi), SUM(max_uretim) FROM (
                SELECT AVG(guc) as guc, COUNT(*) as olcum_sayisi, MAX(CASE WHEN guc > 0 THEN modbus_uretim ELSE 0 END) as max_uretim
                FROM olcumler
                WHERE fabrika_id = %s AND zaman BETWEEN %s AND %s
                GROUP BY slave_id
            ) as alt_sorgu''', (fabrika_id, baslangic, bitis))
            sonuc = cursor.fetchone()
            ort_guc = sonuc[0] or 0
            olcum_sayisi = sonuc[1] or 0
            modbus_uretim = sonuc[2] or 0

        ayarlar = tum_ayarlari_oku(fabrika_id)
        refresh_rate = float(ayarlar.get('refresh_rate', 60))
        olcum_sayisi = float(olcum_sayisi)
        modbus_uretim = float(modbus_uretim)
        ort_guc = float(ort_guc)
        
        toplam_saat = (olcum_sayisi * refresh_rate) / 3600
        
        if modbus_uretim > 0:
            uretim_kwh = modbus_uretim
            uretim_wh = uretim_kwh * 1000
        else:
            uretim_wh = float(ort_guc) * toplam_saat
            uretim_kwh = uretim_wh / 1000

        return {'uretim_wh': round(uretim_wh, 2), 'uretim_kwh': round(uretim_kwh, 3),
                'modbus_uretim': round(modbus_uretim, 3),
                'ort_guc': round(float(ort_guc), 2), 'calisma_suresi_saat': round(toplam_saat, 2)}
    except Exception as e:
        print(f"[WARN] Üretim hesaplama hatası: {e}")
        return None
    finally:
        conn.close()

def hata_sayilarini_getir(baslangic, bitis, slave_id=None, fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    cursor = conn.cursor()
    baslangic_str = f"{baslangic} 00:00:00"
    bitis_str = f"{bitis} 23:59:59"
    hata_sql = """SELECT COUNT(*),
        SUM(CASE WHEN hata_kodu > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_109 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_111 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_112 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_114 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_115 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_116 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_117 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_118 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_119 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_120 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_121 > 0 THEN 1 ELSE 0 END),
        SUM(CASE WHEN hata_kodu_122 > 0 THEN 1 ELSE 0 END)
        FROM olcumler WHERE fabrika_id = %s AND zaman BETWEEN %s AND %s"""
    try:
        if slave_id:
            cursor.execute(hata_sql + " AND slave_id = %s", (fabrika_id, baslangic_str, bitis_str, slave_id))
        else:
            cursor.execute(hata_sql, (fabrika_id, baslangic_str, bitis_str))
        sonuc = cursor.fetchone()
        return {
            'toplam_olcum': sonuc[0] or 0, 'hata_107_sayisi': sonuc[1] or 0,
            'hata_109_sayisi': sonuc[2] or 0, 'hata_111_sayisi': sonuc[3] or 0,
            'hata_112_sayisi': sonuc[4] or 0, 'hata_114_sayisi': sonuc[5] or 0,
            'hata_115_sayisi': sonuc[6] or 0, 'hata_116_sayisi': sonuc[7] or 0,
            'hata_117_sayisi': sonuc[8] or 0, 'hata_118_sayisi': sonuc[9] or 0,
            'hata_119_sayisi': sonuc[10] or 0, 'hata_120_sayisi': sonuc[11] or 0,
            'hata_121_sayisi': sonuc[12] or 0, 'hata_122_sayisi': sonuc[13] or 0
        }
    except Exception as e:
        print(f"[WARN] Hata sayısı getirme hatası: {e}")
        return None
    finally:
        conn.close()

def audit_log_kaydet(kullanici, islem, detay="", fabrika_id=VARSAYILAN_FABRIKA):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log (kullanici, islem, detay, fabrika_id, zaman)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (kullanici, islem, detay, fabrika_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[WARN] Audit log hatası: {e}")
        return False

def audit_log_getir(limit=100, fabrika_id=VARSAYILAN_FABRIKA):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, kullanici, islem, detay, zaman, fabrika_id
            FROM audit_log
            WHERE fabrika_id = %s
            ORDER BY zaman DESC LIMIT %s
        """, (fabrika_id, limit))
        rows = cursor.fetchall()
        conn.close()
        
        formatted_rows = []
        for r in rows:
            formatted_rows.append((r[0], r[1], r[2], r[3], str(r[4]), r[5]))
        return formatted_rows
    except Exception as e:
        print(f"[WARN] Audit log getirme hatası: {e}")
        return []

def gecmis_alarmlari_getir(fabrika_id, limit=100):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT slave_id, baslangic_zamani, bitis_zamani, register_no, hata_kodu, durum
            FROM hata_log
            WHERE fabrika_id = %s
            ORDER BY baslangic_zamani DESC LIMIT %s
        """, (fabrika_id, limit))
        rows = cursor.fetchall()
        
        formatted_rows = []
        for r in rows:
            formatted_rows.append((
                r[0],
                str(r[1]) if r[1] else "",
                str(r[2]) if r[2] else "Devam Ediyor",
                r[3],
                r[4],
                r[5]
            ))
        return formatted_rows
    except Exception as e:
        print(f"[WARN] Gecmis alarm getirme hatasi: {e}")
        return []
    finally:
        if 'conn' in locals() and conn:
            conn.close()
