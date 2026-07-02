import sys
from veritabani import get_db_connection

def migrate():
    conn = get_db_connection()
    if not conn:
        print("Veritabani baglantisi kurulamadi.")
        return
    cursor = conn.cursor()
    
    print("hata_log tablosu temizleniyor...")
    cursor.execute("TRUNCATE TABLE hata_log RESTART IDENTITY") 
    
    print("Olcumler verisi taranıyor... Bu işlem birkaç saniye sürebilir...")
    cursor.execute("""
        SELECT fabrika_id, slave_id, zaman,
               COALESCE(hata_kodu,0), COALESCE(hata_kodu_109,0), COALESCE(hata_kodu_111,0), COALESCE(hata_kodu_112,0), 
               COALESCE(hata_kodu_114,0), COALESCE(hata_kodu_115,0), COALESCE(hata_kodu_116,0), COALESCE(hata_kodu_117,0), 
               COALESCE(hata_kodu_118,0), COALESCE(hata_kodu_119,0), COALESCE(hata_kodu_120,0), COALESCE(hata_kodu_121,0), COALESCE(hata_kodu_122,0)
        FROM olcumler
        ORDER BY zaman ASC
    """)
    rows = cursor.fetchall()
    
    registers = [107, 109, 111, 112, 114, 115, 116, 117, 118, 119, 120, 121, 122]
    
    active_alarms = {}
    completed_alarms = []
    
    for row in rows:
        fab_id = row[0]
        slave_id = row[1]
        zaman = row[2]
        
        if fab_id not in active_alarms: active_alarms[fab_id] = {}
        if slave_id not in active_alarms[fab_id]: active_alarms[fab_id][slave_id] = {}
        
        for idx, reg_no in enumerate(registers):
            val = row[3 + idx]
            current_active = active_alarms[fab_id][slave_id].get(reg_no)
            
            if val > 0:
                if current_active:
                    if current_active['hata_kodu'] != val:
                        # Kod degisti
                        completed_alarms.append((
                            fab_id, slave_id, reg_no, current_active['hata_kodu'],
                            current_active['baslangic'], zaman, 'DUZELDI'
                        ))
                        active_alarms[fab_id][slave_id][reg_no] = {'hata_kodu': val, 'baslangic': zaman}
                else:
                    # Yeni hata
                    active_alarms[fab_id][slave_id][reg_no] = {'hata_kodu': val, 'baslangic': zaman}
            else:
                if current_active:
                    # Hata duzeldi
                    completed_alarms.append((
                        fab_id, slave_id, reg_no, current_active['hata_kodu'],
                        current_active['baslangic'], zaman, 'DUZELDI'
                    ))
                    del active_alarms[fab_id][slave_id][reg_no]

    # Acik kalanlari ekle
    for fab_id, slaves in active_alarms.items():
        for slave_id, regs in slaves.items():
            for reg_no, data in regs.items():
                completed_alarms.append((
                    fab_id, slave_id, reg_no, data['hata_kodu'],
                    data['baslangic'], None, 'AKTIF'
                ))
                
    print(f"Toplam {len(completed_alarms)} adet konsolide alarm uretildi. Veritabanina yaziliyor...")
    
    if completed_alarms:
        from psycopg2.extras import execute_values
        insert_query = """
            INSERT INTO hata_log (fabrika_id, slave_id, register_no, hata_kodu, baslangic_zamani, bitis_zamani, durum)
            VALUES %s
        """
        execute_values(cursor, insert_query, completed_alarms)
    
    conn.commit()
    conn.close()
    print("Goc (Migration) basariyla tamamlandi!")

if __name__ == '__main__':
    migrate()
