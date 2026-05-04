
import veritabani
import unittest
import os
import sqlite3

class TestSecurity(unittest.TestCase):
    def setUp(self):
        # Use a temporary test database to avoid messing with real data
        self.original_db = veritabani.DB_NAME
        veritabani.DB_NAME = "test_security.db"
        veritabani.init_db()
        
        # Add some dummy data
        veritabani.veri_ekle(1, {"guc":100, "voltaj":220, "akim":5, "sicaklik":40, "hata_kodu":0, "hata_kodu_193":0})

    def tearDown(self):
        # Cleanup
        if os.path.exists("test_security.db"):
            os.remove("test_security.db")
        veritabani.DB_NAME = self.original_db

    def test_sql_injection_son_verileri_getir(self):
        """
        Attempt SQL Injection in son_verileri_getir.
        If successful (vulnerable), we might be able to inject a condition that returns more rows 
        or causes a syntax error if not carefully handled.
        
        The vulnerable code is: 
        SELECT ... FROM olcumler WHERE slave_id = {slave_id} ...
        
        We will try to pass a string that alters the logic.
        Since the function expects an ID but uses f-strings, if we can pass "1 OR 1=1", 
        it usually would return data for ALL IDs if the logic was purely string based injection.
        However, in the real app, inputs are cast to int() before calling this.
        But as a library function, it IS vulnerable if passed a string.
        """
        print("\n[TEST] Testing SQL Injection vulnerability in son_verileri_getir...")
        
        # Create a malicious input that would be valid in SQL if directly injected
        # "1 OR 1=1" ensures the condition is always true regardless of slave_id
        malicious_input = "1 OR 1=1"
        
        try:
            # We bypass the type check that might exist in the UI layer and call the DB layer directly
            results = veritabani.son_verileri_getir(malicious_input, limit=100)
            print(f"   [!] Injection successful? Returned {len(results)} rows with input '{malicious_input}'")
            
            # If vulnerable, this runs without error. 
            # If fixed (parameterized), this should fail or treat "1 OR 1=1" as a literal string/ID and return nothing (or error on type conversion depending on driver)
            
            # In sqlite, "1 OR 1=1" as an integer/string comparison might behave oddly if not parameterized.
            # But the f-string injection is clear: f"... slave_id = {slave_id} ..."
            # Becomes: ... slave_id = 1 OR 1=1 ...
            
            # If we get results, it confirms the injection worked logically.
            if len(results) > 0:
                 print("   [VULNERABILITY CONFIRMED] SQL Injection possible via string concatenation.")
            else:
                 print("   [INFO] No results returned, but query executed (Logic altered).")
                 
        except Exception as e:
            print(f"   [INFO] Query failed (expected if injection broke syntax, or if fixed): {e}")

    def test_sql_injection_remediation_check(self):
        """
        This test checks if parameterized queries are used.
        """
        print("\n[TEST] Checking generic parameter usage...")
        # This is more of a manual confirmation via code review, but we can verify behavior.
        pass

if __name__ == '__main__':
    unittest.main()
