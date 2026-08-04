import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

import veritabani

def swap_db_ids():
    veritabani.init_db()
    conn = veritabani.get_db_connection()
    cur = conn.cursor()
    tables = ["olcumler", "hata_log"]
    for table in tables:
        try:
            print(f"Swapping {table}...")
            # 1 -> 9999
            cur.execute(f"UPDATE {table} SET slave_id = 9999 WHERE slave_id = 1;")
            # 2 -> 1
            cur.execute(f"UPDATE {table} SET slave_id = 1 WHERE slave_id = 2;")
            # 9999 -> 2
            cur.execute(f"UPDATE {table} SET slave_id = 2 WHERE slave_id = 9999;")
            conn.commit()
            print(f"Success for {table}.")
        except Exception as e:
            print(f"Error swapping {table}: {e}")
            conn.rollback()

if __name__ == "__main__":
    swap_db_ids()
