import veritabani
conn = veritabani.get_db_connection()
cursor = conn.cursor()
cursor.execute("UPDATE olcumler SET hata_kodu=0 WHERE fabrika_id='uretim'")
conn.commit()
conn.close()
print("Hata kodlari sifirlandi.")
