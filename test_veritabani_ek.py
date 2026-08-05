"""SQLite dönemine ait test — PostgreSQL geçişinden sonra geçersiz.

İki nedenle çalışamaz:

1. `veritabani.DB_NAME`'i geçici bir SQLite dosyasına yönlendiriyor; bu değişken
   PostgreSQL geçişinde kaldırıldı.
2. `tum_cihazlarin_son_durumu` artık düz tuple değil `DictCursor` satırı
   döndürüyor ve kolon sayısı 19'dan 20'ye çıktı (`modbus_uretim` eklendi),
   dolayısıyla satır 29-30'daki tuple karşılaştırmaları yapısal olarak da geçersiz.

Yerine yazılması gereken test: CI'da `services: postgres` (timescaledb image) ile
gerçek DB'ye karşı `veri_ekle → tum_cihazlarin_son_durumu → gunluk_uretim_hesapla`
zinciri. Havuz davranışının testleri `test_db_pool.py` içinde (gerçek DB gerektirmez).
"""

import unittest

# unittest.SkipTest kullaniliyor (pytest.skip yerine): hem pytest hem
# `python -m unittest` bunu modul seviyesinde atlama olarak kabul eder.
raise unittest.SkipTest(
    "SQLite donemi testi: veritabani.DB_NAME artik yok ve satir yapisi degisti "
    "(DictCursor, 20 kolon). Yerine PG servisli entegrasyon testi yazilmali."
)
