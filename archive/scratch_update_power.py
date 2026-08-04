import veritabani
conn = veritabani.get_db_connection()
cursor = conn.cursor()

# Update guc_addr to 33
cursor.execute("UPDATE ayarlar SET deger='33' WHERE fabrika_id='uretim' AND anahtar='guc_addr'")
if cursor.rowcount == 0:
    cursor.execute("INSERT INTO ayarlar (fabrika_id, anahtar, deger) VALUES ('uretim', 'guc_addr', '33')")

# Update guc_scale to 0.1
cursor.execute("UPDATE ayarlar SET deger='0.1' WHERE fabrika_id='uretim' AND anahtar='guc_scale'")
if cursor.rowcount == 0:
    cursor.execute("INSERT INTO ayarlar (fabrika_id, anahtar, deger) VALUES ('uretim', 'guc_scale', '0.1')")

conn.commit()
conn.close()
print("guc_addr set to 33, guc_scale set to 0.1")
