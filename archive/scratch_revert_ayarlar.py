import veritabani
conn = veritabani.get_db_connection()
cursor = conn.cursor()

# Revert guc_addr to 93
cursor.execute("UPDATE ayarlar SET deger='93' WHERE fabrika_id='uretim' AND anahtar='guc_addr'")
# Revert guc_scale to 0.01
cursor.execute("UPDATE ayarlar SET deger='0.01' WHERE fabrika_id='uretim' AND anahtar='guc_scale'")

conn.commit()
conn.close()
print("ayarlar reverted to 93 and 0.01")
