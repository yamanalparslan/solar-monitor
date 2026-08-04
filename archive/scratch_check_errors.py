import veritabani
conn = veritabani.get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT slave_id, zaman, hata_kodu, hata_kodu_109, hata_kodu_111, hata_kodu_112, hata_kodu_114, hata_kodu_115, hata_kodu_116, hata_kodu_117, hata_kodu_118, hata_kodu_119, hata_kodu_120, hata_kodu_121, hata_kodu_122 FROM olcumler WHERE fabrika_id='uretim' ORDER BY zaman DESC LIMIT 2")
rows = cursor.fetchall()
print("Son 2 uretim kaydi hatalari:")
for r in rows:
    print(r)
conn.close()
