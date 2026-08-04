import sqlite3

conn = sqlite3.connect('data/solar_log.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", tables)

for table in tables:
    tname = table[0]
    cursor.execute(f"PRAGMA table_info({tname})")
    print(f"Schema for {tname}:", cursor.fetchall())
