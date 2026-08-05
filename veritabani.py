import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import DictCursor
import os
from contextlib import contextmanager
from datetime import datetime, timedelta

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        dbname = os.getenv("POSTGRES_DB", "solar_db")
        user = os.getenv("POSTGRES_USER", "solar_user")
        password = os.getenv("POSTGRES_PASSWORD", "solar_pass_2026")
        
        try:
            _pool = ThreadedConnectionPool(
                minconn=1, maxconn=20, 
                host=host, port=port, dbname=dbname, user=user, password=password
            )
        except Exception as e:
            print(f"[DB_HATA] PostgreSQL havuzu oluşturulamadı: {e}")
    return _pool

class PooledConnectionProxy:
    """Havuzdan alinan baglantiyi sarar.

    close() baglantiyi gercekten kapatmaz, havuza geri verir. Bu yuzden
    close() cagrilmadan cikilan her kod yolu havuzdan kalici olarak bir slot
    eksiltir (maxconn dolunca tum uygulama DB'siz kalir) — cagiran taraf
    close()'u her zaman finally icinde cagirmalidir.
    """

    # Proxy'nin kendi durumu; bunlarin disindaki her atama gercek baglantiya
    # yonlendirilir.
    _KENDI_ALANLARI = frozenset({"_pool", "_conn", "_returned"})

    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn
        self._returned = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        """Atamalari gercek baglantiya yonlendirir.

        __setattr__ olmadigi surece `conn.autocommit = True` yalnizca proxy
        nesnesinde bir alan olusturuyordu; gercek psycopg2 baglantisi
        autocommit=False kaliyordu. Sonuc: autocommit gerektiren TimescaleDB
        DDL'i (create_hypertable, continuous aggregate, add_retention_policy)
        transaction icinde kosuyor, putconn sirasindaki rollback ile sessizce
        geri aliniyordu — ustelik `conn.autocommit` okundugunda True gorundugu
        icin hicbir hata da uretmiyordu. Temiz kurulumda hypertable hic
        olusmuyor, retention senkronizasyonu hic uygulanmiyordu.
        """
        if name in PooledConnectionProxy._KENDI_ALANLARI:
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def cursor(self, *args, **kwargs):
        if 'cursor_factory' not in kwargs:
            kwargs['cursor_factory'] = DictCursor
        return self._conn.cursor(*args, **kwargs)

    def close(self):
        # Ayni proxy iki kez kapatilirsa baglanti havuza iki kez eklenmesin.
        if self._returned:
            return
        self._returned = True
        try:
            # DDL bloklari autocommit'i True'ya cekiyor; bu durum havuzdaki
            # baglantiya sizmasin diye geri vermeden once normalize ediyoruz.
            if not self._conn.closed and self._conn.autocommit:
                self._conn.autocommit = False
        except Exception:
            pass
        self._pool.putconn(self._conn)

def get_db_connection():
    """Çoklu container ve thread erişimi için PostgreSQL havuzundan bağlantı döndürür."""
    pool = get_pool()
    if pool:
        try:
            conn = pool.getconn()
            return PooledConnectionProxy(pool, conn)
        except Exception as e:
            print(f"[DB_HATA] Havuzdan bağlantı alınamadı: {e}")
    return None


class DBBaglantiYok(RuntimeError):
    """Havuzdan bağlantı alınamadığında yükseltilir."""


@contextmanager
def db_cursor(commit=False, cursor_factory=None):
    """Havuz güvenli cursor: bağlantı her koşulda havuza geri verilir.

    Yeni veritabanı fonksiyonları bu context manager ile yazılmalıdır:

        with db_cursor(commit=True) as cur:
            cur.execute(...)

    Bağlantı kurulamazsa DBBaglantiYok yükseltir; hata durumunda rollback
    yapıp bağlantıyı temiz halde havuza döndürür.
    """
    conn = get_db_connection()
    if conn is None:
        raise DBBaglantiYok("PostgreSQL havuzundan baglanti alinamadi")
    try:
        cursor = conn.cursor(cursor_factory=cursor_factory) if cursor_factory else conn.cursor()
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


# ── Fabrika Tanımları ──
FABRIKALAR = {
    "mekanik": {"ad": "Mekanik Fabrika", "ikon": "🔧", "varsayilan_ip": "10.35.14.10"},
    "uretim":  {"ad": "Üretim Fabrika",  "ikon": "🏭", "varsayilan_ip": "10.35.14.11"},
}
VARSAYILAN_FABRIKA = "mekanik"

def init_db():
    print("[DB] PostgreSQL Veritabanı Başlatılıyor...")
    conn = get_db_connection()
    if not conn:
        print("[DB_HATA] init_db: baglanti kurulamadi, kurulum atlandi.")
        return
    # Sema kurulumu ayri fonksiyonda tutuluyor ki DDL hatasinda da baglanti
    # havuza geri donsun (aksi halde her basarisiz init havuzdan slot yer).
    try:
        _init_db_semasi(conn)
    finally:
        conn.close()


def _init_db_semasi(conn):
    """Tablolari, indeksleri, varsayilan ayarlari ve TimescaleDB kurulumunu yapar."""
    cursor = conn.cursor()

    # 1. Ölçümler Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS osos_verileri (
            fabrika_id VARCHAR(50),
            tarih DATE,
            aktif_cekis DOUBLE PRECISION DEFAULT 0,
            aktif_veris DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (fabrika_id, tarih)
        )
    """)
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

    # 7. Collector Heartbeat Tablosu
    #
    # Neden gerekli: healthcheck "son olcum ne kadar eski" diye bakiyordu, ama
    # olcum akisi mesru sekilde kesintili — sahada okumalarin buyuk bolumu
    # basarisiz oluyor (24 saatte 1611 [CEVAP YOK], cihaz basina 39 dakikaya
    # varan bosluklar). Bu olcut "collector oldu" ile "cihaz cevap vermiyor"
    # durumlarini ayirt edemiyor.
    #
    # Collector artik cihazlardan cevap alamasa bile her dongude buraya kalp
    # atisi yaziyor; healthcheck canlilik icin bu tabloya, cihaz sessizligi
    # icin cihaz_durum_log'a bakiyor.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collector_heartbeat (
            fabrika_id VARCHAR(50) PRIMARY KEY,
            son_dongu TIMESTAMP,
            dongu_suresi_sn DOUBLE PRECISION DEFAULT 0,
            okunan_cihaz INTEGER DEFAULT 0,
            cevapsiz_cihaz INTEGER DEFAULT 0,
            beklenen_periyot_sn DOUBLE PRECISION DEFAULT 60
        )
    """)

    # 8. Cihaz Cevap Durumu Log Tablosu (Stateful)
    #
    # Basarisiz okumalar bugune kadar yalnizca stdout'a "[CEVAP YOK]" olarak
    # basiliyordu: veritabaninda iz yok, metrik yok, alarm yok. Sahada 3
    # inverterin 2'si orneklerinin ~%75'ini kaybediyor (24 saatte 364/1440 ve
    # 312/1440 satir) ve bu hicbir ekranda gorunmuyor.
    #
    # Cevapsizlik artik hata_log ile ayni stateful kalipla burada tutulur:
    # cihaz sustugunda kayit acilir, tekrar cevap verdiginde kapanir. Boylece
    # calisabilirlik (availability) olculebilir hale gelir.
    # olcumler tablosuna kolon eklenmedi — mevcut rapor/ortalama sorgulari
    # (AVG, COUNT) boylece hic etkilenmiyor.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cihaz_durum_log (
            id SERIAL PRIMARY KEY,
            fabrika_id VARCHAR(50),
            slave_id INTEGER,
            durum VARCHAR(20) DEFAULT 'CEVAP_YOK',
            baslangic_zamani TIMESTAMP,
            bitis_zamani TIMESTAMP
        )
    """)
    try:
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cihaz_durum_aktif
            ON cihaz_durum_log(fabrika_id, slave_id)
            WHERE bitis_zamani IS NULL
        """)
    except Exception as e:
        conn.rollback()
        print(f"[WARN] cihaz_durum_log index hatasi: {e}")

    conn.commit()

    # TimescaleDB kurulumu — continuous aggregate DDL'i transaction icinde
    # calisamadigi icin tablolar commit edildikten sonra autocommit ile yapilir.
    _timescale_kurulumu(conn)


def _timescale_kurulumu(conn):
    """Hypertable, saatlik continuous aggregate ve retention policy kurulumu.

    CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous) transaction
    icinde calistirilamaz; bu yuzden bu blok autocommit modunda yurutulur.
    """
    conn.autocommit = True
    cursor = conn.cursor()
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
        cursor.execute("SELECT create_hypertable('olcumler', 'zaman', if_not_exists => TRUE);")
    except Exception as e:
        print(f"[DB] TimescaleDB hypertable kurulamadi (uzanti eksik olabilir): {e}")
        conn.autocommit = False
        return

    try:
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
            GROUP BY time_bucket('1 hour', zaman), fabrika_id, slave_id
            WITH NO DATA;
        """)
    except Exception as e:
        print(f"[DB] olcumler_saatlik view olusturulamadi: {e}")

    try:
        cursor.execute("""
            SELECT add_continuous_aggregate_policy('olcumler_saatlik',
                start_offset => INTERVAL '3 days',
                end_offset => INTERVAL '1 hour',
                schedule_interval => INTERVAL '1 hour',
                if_not_exists => TRUE);
        """)
    except Exception as e:
        print(f"[DB] Continuous aggregate policy eklenemedi: {e}")

    retention_policy_senkronize(conn)
    conn.autocommit = False


def retention_policy_senkronize(conn=None):
    """TimescaleDB retention policy'sini ayarlardaki veri_saklama_gun ile eslestirir.

    Retention policy tablo genelinde tek oldugu icin tum fabrikalarin en uzun
    saklama suresi esas alinir; herhangi bir fabrika 0 (sinirsiz) istiyorsa
    policy tamamen kaldirilir. Boylece hicbir fabrikanin verisi ayarlarda
    yazandan daha erken silinmez.
    """
    kendi_baglantisi = conn is None
    if kendi_baglantisi:
        conn = get_db_connection()
    if not conn:
        return
    conn.autocommit = True
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT deger FROM ayarlar WHERE anahtar = 'veri_saklama_gun'")
        gunler = []
        for (deger,) in cursor.fetchall():
            try:
                gunler.append(int(deger))
            except (TypeError, ValueError):
                pass

        if not gunler:
            gun = 365
        elif 0 in gunler:
            gun = 0
        else:
            gun = max(gunler)

        cursor.execute("SELECT remove_retention_policy('olcumler', if_exists => TRUE);")
        if gun > 0:
            cursor.execute("SELECT add_retention_policy('olcumler', make_interval(days => %s));", (gun,))
            print(f"[DB] Retention policy: {gun} gun olarak ayarlandi.")
        else:
            print("[DB] Retention policy kaldirildi (sinirsiz saklama).")
    except Exception as e:
        print(f"[DB] Retention policy senkronizasyon hatasi: {e}")
    finally:
        # DDL icin acilan autocommit modu havuzdaki baglantiya sizmasin; aksi
        # halde bu baglantiyi sonra kullanan fonksiyon farkinda olmadan
        # autocommit modunda calisir ve rollback'i etkisiz kalir.
        try:
            conn.autocommit = False
        except Exception:
            pass
        if kendi_baglantisi:
            conn.close()


def ayar_oku(anahtar, varsayilan=None, fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    if not conn:
        return varsayilan
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT deger FROM ayarlar WHERE fabrika_id = %s AND anahtar = %s', (fabrika_id, anahtar))
        sonuc = cursor.fetchone()
        if sonuc:
            return sonuc[0]
        return varsayilan
    except Exception as e:
        print(f"[WARN] Ayar okuma hatası ({anahtar}): {e}")
        return varsayilan
    finally:
        conn.close()

def ayar_yaz(anahtar, deger, fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ayarlar (fabrika_id, anahtar, deger, guncelleme_zamani)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (fabrika_id, anahtar)
            DO UPDATE SET deger = EXCLUDED.deger, guncelleme_zamani = EXCLUDED.guncelleme_zamani
        """, (fabrika_id, anahtar, str(deger)))
        conn.commit()
        return True
    except Exception as e:
        print(f"[WARN] Ayar yazma hatası ({anahtar}): {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()

def _varsayilan_ayarlar(fabrika_id: str) -> dict:
    """DB okunamadiginda kullanilan varsayilan ayar seti."""
    fab_ip = FABRIKALAR.get(fabrika_id, {}).get('varsayilan_ip', '10.35.14.10')
    return {
        'refresh_rate': '60', 'guc_scale': '1.0', 'volt_scale': '1.0',
        'akim_scale': '0.1', 'isi_scale': '1.0', 'guc_addr': '70',
        'volt_addr': '71', 'akim_addr': '72', 'isi_addr': '73',
        'uretim_addr': '36', 'uretim_scale': '1.0',
        'target_ip': fab_ip, 'target_port': '502', 'slave_ids': '1,2,3',
        'veri_saklama_gun': '365', 'lat': '38.4237', 'lon': '27.1428'
    }

def tum_ayarlari_oku(fabrika_id: str):
    conn = get_db_connection()
    if not conn:
        return _varsayilan_ayarlar(fabrika_id)
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT anahtar, deger FROM ayarlar WHERE fabrika_id = %s', (fabrika_id,))
        ayarlar = {row[0]: row[1] for row in cursor.fetchall()}
        return ayarlar
    except Exception as e:
        print(f"[WARN] tum_ayarlari_oku hatasi: {e}")
        return _varsayilan_ayarlar(fabrika_id)
    finally:
        conn.close()

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
        # Yarim kalan islemi geri al: baglanti havuza temiz halde donsun.
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()

def veri_kaydet(fabrika_id, slave_id, guc, voltaj, akim, sicaklik, modbus_uretim=0, hatalar=None, voltaj_ab=0, voltaj_bc=0, voltaj_ca=0, akim_a=0, akim_b=0, akim_c=0):
    if hatalar is None: hatalar = []
    conn = get_db_connection()
    if not conn: return
    try:
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
    except Exception as e:
        print(f"[ERROR] veri_kaydet hatasi: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()

def son_verileri_getir(slave_id, limit=100, fabrika_id=VARSAYILAN_FABRIKA):
    try:
        slave_id = int(slave_id)
        limit = int(limit)
    except (ValueError, TypeError):
        return []

    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112, hata_kodu_114, hata_kodu_115, hata_kodu_116, hata_kodu_117, hata_kodu_118, hata_kodu_119, hata_kodu_120, hata_kodu_121, hata_kodu_122, voltaj_ab, voltaj_bc, voltaj_ca, akim_a, akim_b, akim_c
            FROM olcumler WHERE fabrika_id = %s AND slave_id = %s
            ORDER BY zaman DESC LIMIT %s
        """, (fabrika_id, slave_id, limit))
        rows = cursor.fetchall()
        return rows[::-1]
    except Exception as e:
        print(f"[WARN] son_verileri_getir hatasi (slave {slave_id}): {e}")
        return []
    finally:
        conn.close()

def karsilastirma_verisi_getir(slave_id, limit=2880, fabrika_id=VARSAYILAN_FABRIKA):
    try:
        slave_id = int(slave_id)
        limit = int(limit)
    except (ValueError, TypeError):
        return []

    conn = get_db_connection()
    if not conn: return []
    try:
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
        return rows[::-1]
    except Exception as e:
        print(f"[WARN] karsilastirma_verisi_getir hatasi (slave {slave_id}): {e}")
        return []
    finally:
        conn.close()


def tum_cihazlarin_son_durumu(fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute("""
            SELECT DISTINCT ON (slave_id)
                   slave_id, zaman as son_zaman, guc, voltaj, akim, sicaklik,
                   hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112,
                   hata_kodu_114, hata_kodu_115, hata_kodu_116,
                   hata_kodu_117, hata_kodu_118, hata_kodu_119,
                   hata_kodu_120, hata_kodu_121, hata_kodu_122,
                   modbus_uretim
            FROM olcumler
            WHERE fabrika_id = %s
            ORDER BY slave_id ASC, zaman DESC
        """, (fabrika_id,))
        return cursor.fetchall()
    except Exception as e:
        print(f"[WARN] tum_cihazlarin_son_durumu hatasi ({fabrika_id}): {e}")
        return []
    finally:
        conn.close()

def db_temizle(fabrika_id=None):
    conn = get_db_connection()
    if not conn: return False
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
    if not conn: return 0
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
    if not conn: return None
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
    conn = get_db_connection()
    if not conn:
        return []
    try:
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
        return cursor.fetchall()
    except Exception as e:
        print(f"[WARN] Saatlik ozet verisi cekme hatasi: {e}")
        return []
    finally:
        conn.close()

def tarih_araliginda_ortalamalar(baslangic, bitis, slave_id=None, fabrika_id=VARSAYILAN_FABRIKA):
    from datetime import datetime
    conn = get_db_connection()
    if not conn: return None
    try:
        with conn.cursor() as cursor:
            baslangic_str = f"{baslangic} 00:00:00"
            bitis_str = f"{bitis} 23:59:59"
            
            is_long = False
            try:
                b_date = datetime.strptime(baslangic, '%Y-%m-%d')
                e_date = datetime.strptime(bitis, '%Y-%m-%d')
                if (e_date - b_date).days > 1:
                    is_long = True
            except: pass
            
            table_name = "olcumler_saatlik" if is_long else "olcumler"
            time_col = "zaman_saati" if is_long else "zaman"
            
            try:
                if slave_id:
                    cursor.execute(f'''SELECT AVG(guc), AVG(voltaj), AVG(akim), AVG(sicaklik), MAX(guc), MIN(guc), COUNT(*)
                        FROM {table_name} WHERE fabrika_id = %s AND {time_col} BETWEEN %s AND %s AND slave_id = %s''',
                        (fabrika_id, baslangic_str, bitis_str, slave_id))
                else:
                    cursor.execute(f'''SELECT AVG(guc), AVG(voltaj), AVG(akim), AVG(sicaklik), MAX(guc), MIN(guc), COUNT(*)
                        FROM {table_name} WHERE fabrika_id = %s AND {time_col} BETWEEN %s AND %s''',
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
def haftalik_uretim_ozeti(fabrika_id=VARSAYILAN_FABRIKA, gun_sayisi=7):
    """
    Son X gün için, her bir cihazın (slave_id) günlük üretim verisini tek bir sorguda getirir.
    Dönen yapı: 
    {
        (tarih_str, slave_id): {'modbus_uretim': ..., 'uretim_kwh': ...},
        (tarih_str, None): {'modbus_uretim': ..., 'uretim_kwh': ...} # Toplam
    }
    """
    ozet = {}
    conn = get_db_connection()
    if not conn: return ozet
    try:
        with conn.cursor() as cursor:
            # PostgreSQL'de INTERVAL '6 days' (bugün + 6 gün önce = 7 gün)
            interval_str = f"{gun_sayisi - 1} days"
            cursor.execute(f"""
                SELECT 
                    slave_id, 
                    DATE(zaman) as gun,
                    AVG(guc) as ort_guc,
                    COUNT(*) as olcum_sayisi,
                    MAX(CASE WHEN guc > 0 THEN modbus_uretim ELSE 0 END) as modbus_uretim
                FROM olcumler
                WHERE fabrika_id = %s AND zaman >= CURRENT_DATE - INTERVAL '{interval_str}'
                GROUP BY slave_id, DATE(zaman)
            """, (fabrika_id,))
            
            rows = cursor.fetchall()
            
            # Günlük cihaz verileri
            for row in rows:
                s_id = row['slave_id']
                # DictCursor ile row['gun'] doğrudan datetime.date objesi döner
                gun_str = row['gun'].strftime('%Y-%m-%d')
                ort_guc = row['ort_guc'] or 0
                modbus_ur = row['modbus_uretim'] or 0
                uretim_kwh = (ort_guc * 24) / 1000
                
                ozet[(gun_str, s_id)] = {
                    'modbus_uretim': modbus_ur,
                    'uretim_kwh': uretim_kwh
                }
                
                # O günün toplamını da ekleyelim
                if (gun_str, None) not in ozet:
                    ozet[(gun_str, None)] = {'modbus_uretim': 0.0, 'uretim_kwh': 0.0}
                
                ozet[(gun_str, None)]['modbus_uretim'] += modbus_ur
                ozet[(gun_str, None)]['uretim_kwh'] += uretim_kwh

    finally:
        conn.close()
    return ozet


def gunluk_uretim_hesapla(tarih, slave_id=None, fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    if not conn: return None
    cursor = conn.cursor()
    baslangic = f"{tarih} 00:00:00"
    bitis = f"{tarih} 23:59:59"
    try:
        if slave_id:
            # guc > 0 kosulu: cihaz kapaliyken register'dan gelen sahte/artik
            # uretim degerlerinin gunluk toplami sisirmesini engeller.
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
    if not conn: return None
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

# ─────────────────────────────────────────────
# Collector Heartbeat ve Cihaz Cevap Durumu
# ─────────────────────────────────────────────

def heartbeat_yaz(fabrika_id, dongu_suresi_sn=0.0, okunan_cihaz=0,
                  cevapsiz_cihaz=0, beklenen_periyot_sn=60.0, zaman=None):
    """Collector'in bir döngüyü tamamladığını kaydeder.

    Cihazlar cevap vermese bile çağrılır — healthcheck'in "collector yaşıyor mu"
    sorusunu ölçüm tazeliğinden bağımsız yanıtlaması için tek kaynak budur.
    """
    simdi = zaman or datetime.now()
    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO collector_heartbeat
                    (fabrika_id, son_dongu, dongu_suresi_sn, okunan_cihaz,
                     cevapsiz_cihaz, beklenen_periyot_sn)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (fabrika_id) DO UPDATE SET
                    son_dongu = EXCLUDED.son_dongu,
                    dongu_suresi_sn = EXCLUDED.dongu_suresi_sn,
                    okunan_cihaz = EXCLUDED.okunan_cihaz,
                    cevapsiz_cihaz = EXCLUDED.cevapsiz_cihaz,
                    beklenen_periyot_sn = EXCLUDED.beklenen_periyot_sn
            """, (fabrika_id, simdi, float(dongu_suresi_sn), int(okunan_cihaz),
                  int(cevapsiz_cihaz), float(beklenen_periyot_sn)))
        return True
    except Exception as e:
        print(f"[WARN] Heartbeat yazma hatasi ({fabrika_id}): {e}")
        return False


def heartbeat_getir(fabrika_id=None):
    """Kalp atışı kayıtlarını döndürür.

    fabrika_id verilirse tek kayıt (dict) ya da None; verilmezse fabrika_id
    anahtarlı dict döner.
    """
    try:
        with db_cursor() as cursor:
            if fabrika_id:
                cursor.execute("""
                    SELECT fabrika_id, son_dongu, dongu_suresi_sn, okunan_cihaz,
                           cevapsiz_cihaz, beklenen_periyot_sn
                    FROM collector_heartbeat WHERE fabrika_id = %s
                """, (fabrika_id,))
                row = cursor.fetchone()
                return dict(row) if row else None

            cursor.execute("""
                SELECT fabrika_id, son_dongu, dongu_suresi_sn, okunan_cihaz,
                       cevapsiz_cihaz, beklenen_periyot_sn
                FROM collector_heartbeat
            """)
            return {row["fabrika_id"]: dict(row) for row in cursor.fetchall()}
    except Exception as e:
        print(f"[WARN] Heartbeat okuma hatasi: {e}")
        return None if fabrika_id else {}


def cihaz_cevap_durumu_guncelle(cursor, fabrika_id, slave_id, cevap_var, zaman):
    """Cihazın cevap verme durumunu stateful olarak günceller.

    `hata_durumu_guncelle` ile aynı kalıp: cihaz sustuğunda açık kayıt açılır,
    tekrar cevap verdiğinde `bitis_zamani` yazılıp kapatılır. Açık kayıt zaten
    varsa yenisi açılmaz, böylece uzun kesinti tek aralık olarak durur.

    Çağıran taraf cursor'ı sağlar ki cihaz okuma sonucuyla aynı transaction'da
    yazılabilsin.
    """
    cursor.execute("""
        SELECT id FROM cihaz_durum_log
        WHERE fabrika_id = %s AND slave_id = %s AND bitis_zamani IS NULL
        ORDER BY baslangic_zamani DESC LIMIT 1
    """, (fabrika_id, slave_id))
    acik_kayit = cursor.fetchone()

    if cevap_var:
        if acik_kayit:
            cursor.execute(
                "UPDATE cihaz_durum_log SET bitis_zamani = %s WHERE id = %s",
                (zaman, acik_kayit[0])
            )
    elif not acik_kayit:
        cursor.execute("""
            INSERT INTO cihaz_durum_log
                (fabrika_id, slave_id, durum, baslangic_zamani)
            VALUES (%s, %s, 'CEVAP_YOK', %s)
        """, (fabrika_id, slave_id, zaman))


def cihaz_cevap_durumlarini_guncelle(durumlar, zaman=None):
    """Bir collector döngüsündeki tüm cihazların cevap durumunu tek işlemde yazar.

    durumlar: [(fabrika_id, slave_id, cevap_var), ...]

    Döngü başına tek bağlantı kullanılır; cihaz başına ayrı bağlantı açmak
    havuzu gereksiz yorardı.
    """
    if not durumlar:
        return True
    simdi = zaman or datetime.now()
    try:
        with db_cursor(commit=True) as cursor:
            for fabrika_id, slave_id, cevap_var in durumlar:
                cihaz_cevap_durumu_guncelle(cursor, fabrika_id, slave_id, cevap_var, simdi)
        return True
    except Exception as e:
        print(f"[WARN] Cihaz cevap durumu yazma hatasi: {e}")
        return False


def cihaz_cevap_durumu_kaydet(fabrika_id, slave_id, cevap_var, zaman=None):
    """Tek cihaz için sarmalayıcı (toplu sürümü `cihaz_cevap_durumlarini_guncelle`)."""
    return cihaz_cevap_durumlarini_guncelle([(fabrika_id, slave_id, cevap_var)], zaman)


def cevapsiz_cihazlari_getir(fabrika_id=None):
    """Şu anda cevap vermeyen cihazları (açık kayıtları) döndürür."""
    try:
        with db_cursor() as cursor:
            if fabrika_id:
                cursor.execute("""
                    SELECT fabrika_id, slave_id, baslangic_zamani
                    FROM cihaz_durum_log
                    WHERE bitis_zamani IS NULL AND fabrika_id = %s
                    ORDER BY slave_id
                """, (fabrika_id,))
            else:
                cursor.execute("""
                    SELECT fabrika_id, slave_id, baslangic_zamani
                    FROM cihaz_durum_log
                    WHERE bitis_zamani IS NULL
                    ORDER BY fabrika_id, slave_id
                """)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[WARN] Cevapsiz cihaz listesi hatasi: {e}")
        return []


def cihaz_calisabilirligi(baslangic, bitis, fabrika_id=VARSAYILAN_FABRIKA):
    """Cihaz başına çalışabilirlik (availability) yüzdesini hesaplar.

    Verilen aralıkta cevapsız geçirilen süre toplanır ve aralığa oranlanır.
    Aralığın dışına taşan kesintiler kırpılır; hâlâ açık olan kesinti için
    bitiş olarak aralık sonu kabul edilir.
    """
    try:
        with db_cursor() as cursor:
            cursor.execute("""
                SELECT slave_id,
                       SUM(EXTRACT(EPOCH FROM (
                           LEAST(COALESCE(bitis_zamani, %s::timestamp), %s::timestamp)
                           - GREATEST(baslangic_zamani, %s::timestamp)
                       ))) AS cevapsiz_sn
                FROM cihaz_durum_log
                WHERE fabrika_id = %s
                  AND baslangic_zamani < %s::timestamp
                  AND COALESCE(bitis_zamani, %s::timestamp) > %s::timestamp
                GROUP BY slave_id
                ORDER BY slave_id
            """, (bitis, bitis, baslangic, fabrika_id, bitis, bitis, baslangic))
            satirlar = cursor.fetchall()

        with db_cursor() as cursor:
            cursor.execute(
                "SELECT EXTRACT(EPOCH FROM (%s::timestamp - %s::timestamp))",
                (bitis, baslangic)
            )
            aralik_sn = float(cursor.fetchone()[0] or 0)

        if aralik_sn <= 0:
            return {}

        sonuc = {}
        for row in satirlar:
            cevapsiz = max(0.0, float(row[1] or 0))
            sonuc[row[0]] = {
                "cevapsiz_sn": round(cevapsiz, 1),
                "calisabilirlik_yuzde": round(max(0.0, 100.0 * (1 - cevapsiz / aralik_sn)), 2),
            }
        return sonuc
    except Exception as e:
        print(f"[WARN] Calisabilirlik hesaplama hatasi: {e}")
        return {}


def audit_log_kaydet(kullanici, islem, detay="", fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log (kullanici, islem, detay, fabrika_id, zaman)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (kullanici, islem, detay, fabrika_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"[WARN] Audit log hatası: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()

def audit_log_getir(limit=100, fabrika_id=VARSAYILAN_FABRIKA):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, kullanici, islem, detay, zaman, fabrika_id
            FROM audit_log
            WHERE fabrika_id = %s
            ORDER BY zaman DESC LIMIT %s
        """, (fabrika_id, limit))
        rows = cursor.fetchall()

        formatted_rows = []
        for r in rows:
            formatted_rows.append((r[0], r[1], r[2], r[3], str(r[4]), r[5]))
        return formatted_rows
    except Exception as e:
        print(f"[WARN] Audit log getirme hatası: {e}")
        return []
    finally:
        conn.close()

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

def osos_veri_ekle(fabrika_id, tarih_str, aktif_cekis, aktif_veris):
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO osos_verileri (fabrika_id, tarih, aktif_cekis, aktif_veris)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (fabrika_id, tarih) DO UPDATE SET
                aktif_cekis = EXCLUDED.aktif_cekis,
                aktif_veris = EXCLUDED.aktif_veris
        """, (fabrika_id, tarih_str, aktif_cekis, aktif_veris))
        conn.commit()
        return True
    except Exception as e:
        print(f"OSOS veri ekleme hatasi: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def osos_veri_getir(fabrika_id, tarih_str):
    conn = get_db_connection()
    if not conn: return None
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT aktif_cekis, aktif_veris 
            FROM osos_verileri 
            WHERE fabrika_id = %s AND tarih = %s
        """, (fabrika_id, tarih_str))
        row = cursor.fetchone()
        if row:
            return {'aktif_cekis': row[0], 'aktif_veris': row[1]}
        return None
    except Exception as e:
        print(f"OSOS veri okuma hatasi: {e}")
        return None
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def aylik_uretim_getir(fabrika_id, yil):
    conn = get_db_connection()
    if not conn: return {}
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT ay, SUM(max_uretim)
            FROM (
                SELECT date(zaman) as gun, EXTRACT(MONTH FROM zaman) as ay, MAX(CASE WHEN guc > 0 THEN modbus_uretim ELSE 0 END) as max_uretim
                FROM olcumler
                WHERE fabrika_id = %s AND EXTRACT(YEAR FROM zaman) = %s
                GROUP BY slave_id, date(zaman), EXTRACT(MONTH FROM zaman)
            ) as alt_sorgu
            GROUP BY ay
            ORDER BY ay
        ''', (fabrika_id, yil))
        sonuc = cursor.fetchall()
        return {int(row[0]): float(row[1] or 0.0) for row in sonuc}
    except Exception as e:
        print(f"Aylık üretim getirme hatası: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()

def aylik_osos_getir(fabrika_id, yil):
    conn = get_db_connection()
    if not conn: return {}
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT EXTRACT(MONTH FROM tarih) as ay, SUM(aktif_cekis), SUM(aktif_veris)
            FROM osos_verileri
            WHERE fabrika_id = %s AND EXTRACT(YEAR FROM tarih) = %s
            GROUP BY EXTRACT(MONTH FROM tarih)
            ORDER BY ay
        ''', (fabrika_id, yil))
        sonuc = cursor.fetchall()
        return {int(row[0]): {'aktif_cekis': float(row[1]), 'aktif_veris': float(row[2])} for row in sonuc}
    except Exception as e:
        print(f"Aylık OSOS getirme hatası: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()

def osos_kayit_sayisi_getir(fabrika_id):
    conn = get_db_connection()
    if not conn: return 0
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM osos_verileri WHERE fabrika_id = %s", (fabrika_id,))
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception as e:
        print(f"OSOS kayit sayisi hatasi: {e}")
        return 0
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

def osos_verileri_sil(fabrika_id):
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM osos_verileri WHERE fabrika_id = %s", (fabrika_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"OSOS silme hatasi: {e}")
        return False
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()
