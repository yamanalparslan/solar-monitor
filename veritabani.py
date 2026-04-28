import sqlite3
import os
from datetime import datetime, timedelta

# ── Fabrika Tanımları ──
FABRIKALAR = {
    "mekanik": {"ad": "Mekanik Fabrika", "ikon": "🔧", "varsayilan_ip": "10.35.14.10"},
    "uretim":  {"ad": "Üretim Fabrika",  "ikon": "🏭", "varsayilan_ip": "10.35.14.11"},
}
VARSAYILAN_FABRIKA = "mekanik"

# --- VERİTABANI YOL AYARLARI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _local_db_path():
    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "solar_log.db")

# Docker içinde miyiz kontrolü (/app/data genellikle Docker volume yoludur)
if os.path.exists("/app/data"):
    DB_NAME = "/app/data/solar_log.db"
else:
    DB_NAME = _local_db_path()

def init_db():
    # Debug için yol bilgisini yazdıralım
    print(f"[DB] Veritabanı Bağlanıyor: {DB_NAME}")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Ölçümler Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS olcumler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fabrika_id TEXT DEFAULT 'mekanik',
            slave_id INTEGER, 
            zaman TIMESTAMP,
            guc REAL,
            voltaj REAL,
            akim REAL,
            sicaklik REAL,
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
            hata_kodu_122 INTEGER DEFAULT 0
        )
    """)
    
    # Index: zaman (her zaman güvenli)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_zaman 
        ON olcumler(zaman DESC)
    """)

    # 2. Ayarlar Tablosu (fabrika bazlı)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ayarlar (
            anahtar TEXT,
            deger TEXT,
            aciklama TEXT,
            fabrika_id TEXT DEFAULT 'mekanik',
            guncelleme_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (fabrika_id, anahtar)
        )
    """)

    # MIGRATION: Eski ayarlar tablosuna yeni kolonlar ekle
    try:
        ayarlar_sutunlar = [row[1] for row in cursor.execute("PRAGMA table_info(ayarlar)")]
        if 'aciklama' not in ayarlar_sutunlar:
            cursor.execute("ALTER TABLE ayarlar ADD COLUMN aciklama TEXT")
        if 'guncelleme_zamani' not in ayarlar_sutunlar:
            cursor.execute("ALTER TABLE ayarlar ADD COLUMN guncelleme_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except:
        pass

    # MIGRATION: ayarlar tablosunda fabrika_id yoksa eski tablodaki verileri tasi
    # ÖNEMLİ: Bu migration varsayılan ayar eklenmeden ÖNCE çalışmalı!
    try:
        ayar_sutunlar = [row[1] for row in cursor.execute("PRAGMA table_info(ayarlar)")]
        if 'fabrika_id' not in ayar_sutunlar:
            cursor.execute("ALTER TABLE ayarlar RENAME TO ayarlar_eski")
            cursor.execute("""
                CREATE TABLE ayarlar (
                    anahtar TEXT, deger TEXT, aciklama TEXT,
                    fabrika_id TEXT DEFAULT 'mekanik',
                    guncelleme_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (fabrika_id, anahtar)
                )
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO ayarlar (fabrika_id, anahtar, deger, aciklama)
                SELECT 'mekanik', anahtar, deger, aciklama FROM ayarlar_eski
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO ayarlar (fabrika_id, anahtar, deger, aciklama)
                SELECT 'uretim', anahtar, deger, aciklama FROM ayarlar_eski
            """)
            cursor.execute("UPDATE ayarlar SET deger = '10.35.14.11' WHERE fabrika_id = 'uretim' AND anahtar = 'target_ip'")
            cursor.execute("DROP TABLE ayarlar_eski")
            print("[MIGRATION] ayarlar tablosu fabrika bazlı yapıldı")
    except Exception as e:
        print(f"[MIGRATION WARN] ayarlar migration: {e}")

    # MIGRATION: fabrika_id kolonu yoksa ekle ve mevcut verileri 'mekanik' yap
    try:
        mevcut_sutunlar = [row[1] for row in cursor.execute("PRAGMA table_info(olcumler)")]
        if 'fabrika_id' not in mevcut_sutunlar:
            cursor.execute("ALTER TABLE olcumler ADD COLUMN fabrika_id TEXT DEFAULT 'mekanik'")
            cursor.execute("UPDATE olcumler SET fabrika_id = 'mekanik' WHERE fabrika_id IS NULL")
            print("[MIGRATION] olcumler tablosuna fabrika_id eklendi")
    except:
        pass

    # MIGRATION: hata kolonlari
    try:
        mevcut_sutunlar = [row[1] for row in cursor.execute("PRAGMA table_info(olcumler)")]
        for hk in ['hata_kodu_109','hata_kodu_111','hata_kodu_112','hata_kodu_114','hata_kodu_115','hata_kodu_116','hata_kodu_117','hata_kodu_118','hata_kodu_119','hata_kodu_120','hata_kodu_121','hata_kodu_122']:
            if hk not in mevcut_sutunlar:
                cursor.execute(f"ALTER TABLE olcumler ADD COLUMN {hk} INTEGER DEFAULT 0")
    except:
        pass

    # fabrika_id index'i (migration'dan sonra güvenli)
    try:
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fabrika_slave_zaman 
            ON olcumler(fabrika_id, slave_id, zaman DESC)
        """)
    except:
        pass

    # 3. Varsayılan Ayarları Her Fabrika İçin Ekle (migration'lardan SONRA)
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
            ('isi_addr', '74', 'Sıcaklık register adresi'),
            ('target_ip', fab_info['varsayilan_ip'], 'Modbus IP adresi'),
            ('target_port', '502', 'Modbus Port'),
            ('slave_ids', '1,2,3', 'İnverter ID listesi'),
            ('veri_saklama_gun', '365', 'Veri saklama süresi (gün) - 0: Sınırsız')
        ]
        for anahtar, deger, aciklama in varsayilan_ayarlar:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO ayarlar (fabrika_id, anahtar, deger, aciklama)
                    VALUES (?, ?, ?, ?)
                """, (fab_id, anahtar, deger, aciklama))
            except:
                pass

    # 5. Audit Log Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fabrika_id TEXT DEFAULT 'mekanik',
            kullanici TEXT DEFAULT 'admin',
            islem TEXT,
            detay TEXT,
            zaman TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def ayar_oku(anahtar, varsayilan=None, fabrika_id=VARSAYILAN_FABRIKA):
    """Veritabanından ayar oku"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT deger FROM ayarlar WHERE fabrika_id = ? AND anahtar = ?', (fabrika_id, anahtar))
        sonuc = cursor.fetchone()
        conn.close()
        if sonuc:
            return sonuc[0]
        return varsayilan
    except Exception as e:
        print(f"[WARN] Ayar okuma hatası ({anahtar}): {e}")
        return varsayilan

def ayar_yaz(anahtar, deger, fabrika_id=VARSAYILAN_FABRIKA):
    """Veritabanına ayar yaz"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO ayarlar (fabrika_id, anahtar, deger, guncelleme_zamani)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (fabrika_id, anahtar, str(deger)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[WARN] Ayar yazma hatası ({anahtar}): {e}")
        return False

def tum_ayarlari_oku(fabrika_id=VARSAYILAN_FABRIKA):
    """Tüm ayarları dict olarak döndür"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT anahtar, deger FROM ayarlar WHERE fabrika_id = ?', (fabrika_id,))
        ayarlar = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return ayarlar
    except:
        fab_ip = FABRIKALAR.get(fabrika_id, {}).get('varsayilan_ip', '10.35.14.10')
        return {
            'refresh_rate': '60', 'guc_scale': '1.0', 'volt_scale': '1.0',
            'akim_scale': '0.1', 'isi_scale': '1.0', 'guc_addr': '70',
            'volt_addr': '71', 'akim_addr': '72', 'isi_addr': '74',
            'target_ip': fab_ip, 'target_port': '502', 'slave_ids': '1,2,3',
            'veri_saklama_gun': '365'
        }

def veri_ekle(slave_id, data, fabrika_id=VARSAYILAN_FABRIKA):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    simdi = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
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
    cursor.execute("""
        INSERT INTO olcumler (fabrika_id, slave_id, zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112, hata_kodu_114, hata_kodu_115, hata_kodu_116, hata_kodu_117, hata_kodu_118, hata_kodu_119, hata_kodu_120, hata_kodu_121, hata_kodu_122)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (fabrika_id, slave_id, simdi, data['guc'], data['voltaj'], data['akim'], data['sicaklik'], hk_107, hk_109, hk_111, hk_112, hk_114, hk_115, hk_116, hk_117, hk_118, hk_119, hk_120, hk_121, hk_122))
    conn.commit()
    conn.close()

def son_verileri_getir(slave_id, limit=100, fabrika_id=VARSAYILAN_FABRIKA):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112, hata_kodu_114, hata_kodu_115, hata_kodu_116, hata_kodu_117, hata_kodu_118, hata_kodu_119, hata_kodu_120, hata_kodu_121, hata_kodu_122
        FROM olcumler WHERE fabrika_id = ? AND slave_id = ?
        ORDER BY zaman DESC LIMIT ?
    """, (fabrika_id, slave_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows[::-1]

def tum_cihazlarin_son_durumu(fabrika_id=VARSAYILAN_FABRIKA):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.slave_id, o.zaman, o.guc, o.voltaj, o.akim, o.sicaklik, o.hata_kodu, o.hata_kodu_109, o.hata_kodu_111, o.hata_kodu_112, o.hata_kodu_114, o.hata_kodu_115, o.hata_kodu_116
        FROM olcumler o
        WHERE o.fabrika_id = ? AND o.id = (
            SELECT COALESCE(
                (
                    SELECT i.id
                    FROM olcumler i
                    WHERE i.fabrika_id = ? AND i.slave_id = o.slave_id
                      AND (
                          COALESCE(i.guc, 0) <> 0
                          OR COALESCE(i.voltaj, 0) <> 0
                          OR COALESCE(i.akim, 0) <> 0
                          OR COALESCE(i.sicaklik, 0) <> 0
                      )
                    ORDER BY i.zaman DESC, i.id DESC
                    LIMIT 1
                ),
                (
                    SELECT i.id
                    FROM olcumler i
                    WHERE i.fabrika_id = ? AND i.slave_id = o.slave_id
                    ORDER BY i.zaman DESC, i.id DESC
                    LIMIT 1
                )
            )
        )
        ORDER BY o.slave_id ASC
    """, (fabrika_id, fabrika_id, fabrika_id))
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_temizle(fabrika_id=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        if fabrika_id:
            cursor.execute('DELETE FROM olcumler WHERE fabrika_id = ?', (fabrika_id,))
        else:
            cursor.execute('DELETE FROM olcumler')
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

# ==================== YENİ FONKSİYONLAR: GEÇMİŞ VERİ YÖNETİMİ ====================

def eski_verileri_temizle(gun_sayisi=None, fabrika_id=None):
    """
    Belirtilen günden eski verileri sil
    gun_sayisi None ise ayarlardan oku
    gun_sayisi 0 ise sınırsız saklama (silme yapma)
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        if gun_sayisi is None:
            gun_sayisi = int(ayar_oku('veri_saklama_gun', '365'))
        
        if gun_sayisi == 0:
            return 0
        
        tarih = datetime.now() - timedelta(days=gun_sayisi)
        tarih_str = tarih.strftime('%Y-%m-%d %H:%M:%S')
        if fabrika_id:
            cursor.execute('DELETE FROM olcumler WHERE zaman < ? AND fabrika_id = ?', (tarih_str, fabrika_id))
        else:
            cursor.execute('DELETE FROM olcumler WHERE zaman < ?', (tarih_str,))
        silinen = cursor.rowcount
        conn.commit()
        
        if silinen > 0:
            cursor.execute('VACUUM')
            print(f"[CLEAN] {silinen} eski kayıt temizlendi ({gun_sayisi} günden eski)")
        
        return silinen
    except Exception as e:
        print(f"[WARN] Eski veri temizleme hatası: {e}")
        return 0
    finally:
        conn.close()

def veritabani_istatistikleri(fabrika_id=None):
    """Veritabanı boyutu ve kayıt sayısı hakkında bilgi"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        if fabrika_id:
            cursor.execute('SELECT COUNT(*) FROM olcumler WHERE fabrika_id = ?', (fabrika_id,))
        else:
            cursor.execute('SELECT COUNT(*) FROM olcumler')
        toplam_kayit = cursor.fetchone()[0]
        
        if fabrika_id:
            cursor.execute('SELECT MIN(zaman), MAX(zaman) FROM olcumler WHERE fabrika_id = ?', (fabrika_id,))
        else:
            cursor.execute('SELECT MIN(zaman), MAX(zaman) FROM olcumler')
        tarih_araligi = cursor.fetchone()
        
        if fabrika_id:
            cursor.execute('''SELECT slave_id, COUNT(*), MIN(zaman), MAX(zaman)
                FROM olcumler WHERE fabrika_id = ? GROUP BY slave_id ORDER BY slave_id''', (fabrika_id,))
        else:
            cursor.execute('''SELECT slave_id, COUNT(*), MIN(zaman), MAX(zaman)
                FROM olcumler GROUP BY slave_id ORDER BY slave_id''')
        cihaz_istatistik = cursor.fetchall()
        
        db_boyut = os.path.getsize(DB_NAME) / (1024 * 1024)
        
        return {
            'toplam_kayit': toplam_kayit,
            'ilk_kayit': tarih_araligi[0],
            'son_kayit': tarih_araligi[1],
            'cihaz_istatistik': cihaz_istatistik,
            'db_boyut_mb': round(db_boyut, 2)
        }
    except Exception as e:
        print(f"[WARN] İstatistik hatası: {e}")
        return None
    finally:
        conn.close()

def tarih_araliginda_ortalamalar(baslangic, bitis, slave_id=None, fabrika_id=VARSAYILAN_FABRIKA):
    """Belirtilen tarih aralığındaki ortalama değerler"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    baslangic_str = f"{baslangic} 00:00:00"
    bitis_str = f"{bitis} 23:59:59"
    try:
        if slave_id:
            cursor.execute('''SELECT AVG(guc), AVG(voltaj), AVG(akim), AVG(sicaklik), MAX(guc), MIN(guc), COUNT(*)
                FROM olcumler WHERE fabrika_id = ? AND zaman BETWEEN ? AND ? AND slave_id = ?''',
                (fabrika_id, baslangic_str, bitis_str, slave_id))
        else:
            cursor.execute('''SELECT AVG(guc), AVG(voltaj), AVG(akim), AVG(sicaklik), MAX(guc), MIN(guc), COUNT(*)
                FROM olcumler WHERE fabrika_id = ? AND zaman BETWEEN ? AND ?''',
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
    """Belirli bir gün için toplam enerji üretimi tahmini (Wh)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    baslangic = f"{tarih} 00:00:00"
    bitis = f"{tarih} 23:59:59"
    try:
        if slave_id:
            cursor.execute('''SELECT AVG(guc), COUNT(*) FROM olcumler
                WHERE fabrika_id = ? AND zaman BETWEEN ? AND ? AND slave_id = ?''',
                (fabrika_id, baslangic, bitis, slave_id))
        else:
            cursor.execute('''SELECT AVG(guc), COUNT(*) FROM olcumler
                WHERE fabrika_id = ? AND zaman BETWEEN ? AND ?''',
                (fabrika_id, baslangic, bitis))
        sonuc = cursor.fetchone()
        ort_guc = sonuc[0] or 0
        olcum_sayisi = sonuc[1] or 0
        ayarlar = tum_ayarlari_oku(fabrika_id)
        refresh_rate = float(ayarlar.get('refresh_rate', 60))
        toplam_saat = (olcum_sayisi * refresh_rate) / 3600
        uretim_wh = ort_guc * toplam_saat
        return {'uretim_wh': round(uretim_wh, 2), 'uretim_kwh': round(uretim_wh / 1000, 3),
                'ort_guc': round(ort_guc, 2), 'calisma_suresi_saat': round(toplam_saat, 2)}
    except Exception as e:
        print(f"[WARN] Üretim hesaplama hatası: {e}")
        return None
    finally:
        conn.close()

def hata_sayilarini_getir(baslangic, bitis, slave_id=None, fabrika_id=VARSAYILAN_FABRIKA):
    """Belirtilen tarih aralığındaki hata kayıtlarını getir"""
    conn = sqlite3.connect(DB_NAME)
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
        FROM olcumler WHERE fabrika_id = ? AND zaman BETWEEN ? AND ?"""
    try:
        if slave_id:
            cursor.execute(hata_sql + " AND slave_id = ?", (fabrika_id, baslangic_str, bitis_str, slave_id))
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

# ==================== AUDİT LOG FONKSİYONLARI ====================

def audit_log_kaydet(kullanici, islem, detay=""):
    """Audit log kaydı ekle.
    
    Args:
        kullanici: İşlemi yapan kullanıcı
        islem: İşlem tipi (ayar_degistir, veri_sil, vb.)
        detay: Ek açıklama
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log (kullanici, islem, detay, zaman)
            VALUES (?, ?, ?, ?)
        """, (kullanici, islem, detay, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[WARN] Audit log hatası: {e}")
        return False


def audit_log_getir(limit=100):
    """Audit log kayıtlarını getir.
    
    Returns:
        list of tuples: (id, kullanici, islem, detay, zaman)
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, kullanici, islem, detay, zaman
            FROM audit_log
            ORDER BY zaman DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"[WARN] Audit log getirme hatası: {e}")
        return []
