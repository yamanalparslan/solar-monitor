#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOLAR MONITOR - HIZLI KURULUM ARACI
====================================
Bu script, güncellenmiş veritabani.py, collector.py ve panel.py 
dosyalarını mevcut klasörünüzde oluşturur.

Kullanım:
    python kurulum_yap.py
"""

import os
import shutil
from datetime import datetime

# Renk kodları (Windows için opsiyonel)
try:
    import colorama
    colorama.init()
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
except:
    GREEN = YELLOW = RED = RESET = ''

def banner():
    print("=" * 60)
    print(" 🌞 SOLAR MONITOR - HIZLI KURULUM")
    print("=" * 60)
    print()

def yedekle(dosya):
    """Dosya varsa yedekle"""
    if os.path.exists(dosya):
        yedek = f"{dosya}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(dosya, yedek)
        print(f"{YELLOW}   ✓{RESET} {dosya} → {yedek}")
        return True
    return False

def dosya_olustur(isim, icerik):
    """Dosya oluştur"""
    with open(isim, 'w', encoding='utf-8') as f:
        f.write(icerik)
    print(f"{GREEN}   ✓{RESET} {isim} oluşturuldu ({len(icerik)} byte)")

# ==================== DOSYA İÇERİKLERİ ====================

VERITABANI_PY = '''import sqlite3
from datetime import datetime

DB_NAME = "solar_log.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Ölçümler Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS olcumler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slave_id INTEGER, 
            zaman TIMESTAMP,
            guc REAL,
            voltaj REAL,
            akim REAL,
            sicaklik REAL,
            hata_kodu INTEGER DEFAULT 0,
            hata_kodu_111 INTEGER DEFAULT 0
        )
    """)

    # 2. Ayarlar Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ayarlar (
            anahtar TEXT PRIMARY KEY,
            deger TEXT,
            aciklama TEXT,
            guncelleme_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    # 3. Varsayılan Ayarları Ekle
    varsayilan_ayarlar = [
        ('refresh_rate', '2', 'Veri çekme sıklığı (saniye)'),
        ('guc_scale', '1.0', 'Güç çarpanı'),
        ('volt_scale', '0.1', 'Voltaj çarpanı'),
        ('akim_scale', '0.1', 'Akım çarpanı'),
        ('isi_scale', '1.0', 'Sıcaklık çarpanı'),
        ('guc_addr', '70', 'Güç register adresi'),
        ('volt_addr', '71', 'Voltaj register adresi'),
        ('akim_addr', '72', 'Akım register adresi'),
        ('isi_addr', '73', 'Sıcaklık register adresi'),
        ('target_ip', '10.35.14.10', 'Modbus IP adresi'),
        ('target_port', '502', 'Modbus Port'),
        ('slave_ids', '1,2,3', 'İnverter ID listesi')
    ]
    
    for anahtar, deger, aciklama in varsayilan_ayarlar:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO ayarlar (anahtar, deger, aciklama)
                VALUES (?, ?, ?)
            """, (anahtar, deger, aciklama))
        except:
            cursor.execute("""
                INSERT OR IGNORE INTO ayarlar (anahtar, deger)
                VALUES (?, ?)
            """, (anahtar, deger))
    
    # MIGRATION: hata_kodu_111 kolonu yoksa ekle
    try:
        mevcut_sutunlar = [row[1] for row in cursor.execute("PRAGMA table_info(olcumler)")]
        if 'hata_kodu_111' not in mevcut_sutunlar:
            cursor.execute("ALTER TABLE olcumler ADD COLUMN hata_kodu_111 INTEGER DEFAULT 0")
    except:
        pass
        
    conn.commit()
    conn.close()

def ayar_oku(anahtar, varsayilan=None):
    """Veritabanından ayar oku"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT deger FROM ayarlar WHERE anahtar = ?', (anahtar,))
        sonuc = cursor.fetchone()
        conn.close()
        if sonuc:
            return sonuc[0]
        return varsayilan
    except Exception as e:
        print(f"⚠️ Ayar okuma hatası ({anahtar}): {e}")
        return varsayilan

def ayar_yaz(anahtar, deger):
    """Veritabanına ayar yaz"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO ayarlar (anahtar, deger, guncelleme_zamani)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (anahtar, str(deger)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Ayar yazma hatası ({anahtar}): {e}")
        return False

def tum_ayarlari_oku():
    """Tüm ayarları dict olarak döndür"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT anahtar, deger FROM ayarlar')
        ayarlar = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return ayarlar
    except:
        return {
            'refresh_rate': '2', 'guc_scale': '1.0', 'volt_scale': '0.1',
            'akim_scale': '0.1', 'isi_scale': '1.0', 'guc_addr': '70',
            'volt_addr': '71', 'akim_addr': '72', 'isi_addr': '73',
            'target_ip': '10.35.14.10', 'target_port': '502', 'slave_ids': '1,2,3'
        }

def veri_ekle(slave_id, data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    simdi = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    hk_107 = data.get('hata_kodu', 0)
    hk_111 = data.get('hata_kodu_111', 0)
    cursor.execute("""
        INSERT INTO olcumler (slave_id, zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_111)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (slave_id, simdi, data['guc'], data['voltaj'], data['akim'], data['sicaklik'], hk_107, hk_111))
    conn.commit()
    conn.close()

def son_verileri_getir(slave_id, limit=100):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_111
        FROM olcumler WHERE slave_id = ?
        ORDER BY zaman DESC LIMIT ?
    """, (slave_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows[::-1]

def tum_cihazlarin_son_durumu():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT slave_id, MAX(zaman) as son_zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_111
        FROM olcumler GROUP BY slave_id ORDER BY slave_id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_temizle():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM olcumler')
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()
'''

COLLECTOR_PY = '''import time
import logging
from pymodbus.client import ModbusTcpClient
import veritabani

def load_config():
    """Veritabanından ayarları yükle"""
    ayarlar = veritabani.tum_ayarlari_oku()
    return {
        'target_ip': ayarlar.get('target_ip', '10.35.14.10'),
        'target_port': int(ayarlar.get('target_port', 502)),
        'refresh_rate': float(ayarlar.get('refresh_rate', 2)),
        'slave_ids': [int(x.strip()) for x in ayarlar.get('slave_ids', '1,2,3').split(',')],
        'start_addr': int(ayarlar.get('guc_addr', 70)),
        'guc_scale': float(ayarlar.get('guc_scale', 1.0)),
        'volt_scale': float(ayarlar.get('volt_scale', 0.1)),
        'akim_scale': float(ayarlar.get('akim_scale', 0.1)),
        'isi_scale': float(ayarlar.get('isi_scale', 1.0)),
        'alarm_registers': [
            {'addr': 107, 'key': 'hata_kodu', 'count': 2},
            {'addr': 111, 'key': 'hata_kodu_111', 'count': 1}
        ]
    }

def read_device(client, slave_id, config):
    try:
        if not client.connected: 
            client.connect()
            time.sleep(0.1)
        
        rr = client.read_holding_registers(config['start_addr'], count=4, slave=slave_id)
        if rr.isError(): 
            return None

        veriler = {
            "guc": rr.registers[0] * config['guc_scale'],
            "voltaj": rr.registers[1] * config['volt_scale'],
            "akim": rr.registers[2] * config['akim_scale'],
            "sicaklik": rr.registers[3] * config['isi_scale']
        }

        for reg in config['alarm_registers']:
            try:
                time.sleep(0.05)
                r_hata = client.read_holding_registers(reg['addr'], count=reg.get('count', 2), slave=slave_id)
                if not r_hata.isError():
                    if reg.get('count', 2) == 2:
                        veriler[reg['key']] = (r_hata.registers[0] << 16) | r_hata.registers[1]
                    else:
                        veriler[reg['key']] = r_hata.registers[0]
                else:
                    veriler[reg['key']] = 0
            except:
                veriler[reg['key']] = 0

        return veriler

    except Exception as e:
        logging.error(f"ID {slave_id} Hata: {e}")
        client.close()
        return None

def start_collector():
    veritabani.init_db()
    print("=" * 60)
    print("🚀 COLLECTOR BAŞLATILDI (Dinamik Ayar Modu)")
    print("=" * 60)
    
    config = load_config()
    client = ModbusTcpClient(config['target_ip'], port=config['target_port'], timeout=2.0)
    
    print(f"📡 IP: {config['target_ip']}:{config['target_port']}")
    print(f"⏱️  Refresh: {config['refresh_rate']}s")
    print(f"🔢 Slave IDs: {config['slave_ids']}")
    print(f"📊 Çarpanlar: Güç={config['guc_scale']}, V={config['volt_scale']}, A={config['akim_scale']}, °C={config['isi_scale']}")
    print("=" * 60)
    
    ayar_kontrol_sayaci = 0
    
    while True:
        start_time = time.time()
        
        ayar_kontrol_sayaci += 1
        if ayar_kontrol_sayaci >= 10:
            yeni_config = load_config()
            if (yeni_config['target_ip'] != config['target_ip'] or 
                yeni_config['target_port'] != config['target_port']):
                print("\\n🔄 IP/Port değişti, bağlantı yenileniyor...")
                client.close()
                client = ModbusTcpClient(yeni_config['target_ip'], port=yeni_config['target_port'], timeout=2.0)
            config = yeni_config
            ayar_kontrol_sayaci = 0
            print(f"\\n✅ Ayarlar güncellendi (Refresh: {config['refresh_rate']}s)")
        
        for dev_id in config['slave_ids']:
            print(f"📡 ID {dev_id}...", end=" ")
            time.sleep(0.5)
            data = read_device(client, dev_id, config)
            if data:
                veritabani.veri_ekle(dev_id, data)
                h107 = data.get('hata_kodu', 0)
                h111 = data.get('hata_kodu_111', 0)
                if h107 == 0 and h111 == 0:
                    durum = "TEMİZ"
                else:
                    durum = f"⚠️ HATA (107:{h107}, 111:{h111})"
                print(f"✅ [OK] {durum}")
            else:
                print(f"❌ [YOK]")
        
        elapsed = time.time() - start_time
        time.sleep(max(0, config['refresh_rate'] - elapsed))

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    start_collector()
'''

# ==================== MAIN ====================

def main():
    banner()
    
    # Gerekli dosyaları kontrol et
    if not os.path.exists('docker-compose.yml'):
        print(f"{RED}❌ HATA:{RESET} docker-compose.yml bulunamadı!")
        print("   Bu scripti proje klasörünüzde çalıştırın.")
        return
    
    print("📦 [1/3] Eski dosyalar yedekleniyor...")
    yedekle('veritabani.py')
    yedekle('collector.py')
    yedekle('panel.py')
    
    print()
    print("🔧 [2/3] Yeni dosyalar oluşturuluyor...")
    dosya_olustur('veritabani.py', VERITABANI_PY)
    dosya_olustur('collector.py', COLLECTOR_PY)
    print(f"{YELLOW}   ℹ{RESET} panel.py çok büyük, indirilen dosyayı kullanın")
    
    print()
    print("🐳 [3/3] Docker yeniden başlatılsın mı? (E/H)")
    cevap = input("   > ").strip().lower()
    
    if cevap in ['e', 'y', 'yes', 'evet']:
        print(f"{GREEN}   ✓{RESET} Docker yeniden başlatılıyor...")
        os.system('docker-compose down')
        os.system('docker-compose up -d --build')
    else:
        print(f"{YELLOW}   ⏭{RESET} Docker başlatma atlandı")
        print("   Manuel başlatma: docker-compose down && docker-compose up -d --build")
    
    print()
    print("=" * 60)
    print(f" {GREEN}✅ KURULUM TAMAMLANDI!{RESET}")
    print("=" * 60)
    print()
    print("📋 SONRAKI ADIMLAR:")
    print("  1. Panel'i açın: http://localhost:8501")
    print("  2. Sol menüden ayarları yapın")
    print("  3. '💾 AYARLARI KAYDET' butonuna basın")
    print()
    print("📊 LOGLAR:")
    print("  docker logs solar_collector -f")
    print("  docker logs solar_monitor_pro -f")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\\n{YELLOW}⚠️ İptal edildi{RESET}")
    except Exception as e:
        print(f"\\n{RED}❌ HATA: {e}{RESET}")
        import traceback
        traceback.print_exc()