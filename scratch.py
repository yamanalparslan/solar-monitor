import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432, dbname='solar_db', 
    user='solar_user', password='solar_pass_2026'
)
cur = conn.cursor()

cur.execute("""SELECT AVG(guc), COUNT(*), MAX(modbus_uretim) FROM olcumler WHERE fabrika_id = 'mekanik' AND zaman BETWEEN '2026-05-16 00:00:00' AND '2026-05-22 23:59:59' AND slave_id = 1""")
print('Slave 1:', cur.fetchone())

cur.execute("""SELECT AVG(guc), SUM(olcum_sayisi), SUM(max_uretim) FROM (
    SELECT AVG(guc) as guc, COUNT(*) as olcum_sayisi, MAX(modbus_uretim) as max_uretim
    FROM olcumler
    WHERE fabrika_id = 'mekanik' AND zaman BETWEEN '2026-05-16 00:00:00' AND '2026-05-22 23:59:59'
    GROUP BY slave_id
) as alt_sorgu""")
print('Total:', cur.fetchone())
