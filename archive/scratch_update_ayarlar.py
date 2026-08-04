import veritabani
conn = veritabani.get_db_connection()
cursor = conn.cursor()

# Set guc_addr to 33
cursor.execute("UPDATE ayarlar SET deger='33' WHERE fabrika_id='uretim' AND anahtar='guc_addr'")
if cursor.rowcount == 0:
    cursor.execute("INSERT INTO ayarlar (fabrika_id, anahtar, deger) VALUES ('uretim', 'guc_addr', '33')")

# Set guc_scale to 0.1
cursor.execute("UPDATE ayarlar SET deger='0.1' WHERE fabrika_id='uretim' AND anahtar='guc_scale'")
if cursor.rowcount == 0:
    cursor.execute("INSERT INTO ayarlar (fabrika_id, anahtar, deger) VALUES ('uretim', 'guc_scale', '0.1')")

conn.commit()
conn.close()
print("ayarlar guncellendi")
