import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import veritabani

def update_data():
    conn = veritabani.get_db_connection()
    if not conn:
        print("DB connection failed")
        return

    cursor = conn.cursor()
    
    try:
        # 1 Ağustos ve 2 Ağustos 12:00:00 için girdiğimiz kayıtları 1150 olarak güncelliyoruz
        cursor.execute("""
            UPDATE olcumler 
            SET modbus_uretim = 1150 
            WHERE guc = 1 
              AND zaman IN ('2026-08-01 12:00:00', '2026-08-02 12:00:00')
        """)
        
        updated_rows = cursor.rowcount
        conn.commit()
        print(f"{updated_rows} kayıt güncellendi.")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_data()
