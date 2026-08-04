import veritabani
conn = veritabani.get_db_connection()
c = conn.cursor()
c.execute("SELECT zaman, fabrika_id, slave_id, guc, voltaj, akim FROM olcumler ORDER BY zaman DESC LIMIT 10")
for row in c.fetchall():
    print(row)
conn.close()
