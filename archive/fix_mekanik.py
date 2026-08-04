import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

import veritabani

def fix_mekanik():
    veritabani.init_db()
    conn = veritabani.get_db_connection()
    cur = conn.cursor()
    try:
        print("Fixing mekanik...")
        cur.execute("UPDATE olcumler SET slave_id = 1 WHERE fabrika_id = 'mekanik' AND slave_id = 2;")
        cur.execute("UPDATE hata_log SET slave_id = 1 WHERE fabrika_id = 'mekanik' AND slave_id = 2;")
        conn.commit()
        print("Success.")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()

if __name__ == "__main__":
    fix_mekanik()
