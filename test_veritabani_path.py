"""SQLite dönemine ait test — PostgreSQL geçişinden sonra geçersiz.

`veritabani.DB_NAME` ve `veritabani.BASE_DIR` PostgreSQL/TimescaleDB geçişinde
kaldırıldı; bağlantı artık `POSTGRES_*` ortam değişkenlerinden kurulan havuz
üzerinden yönetiliyor (`veritabani.get_pool`). Bu dosya bir dosya yolu iddiasını
test ediyordu, karşılığı olan bir davranış artık yok.

Silinmedi çünkü git geçmişinde kalması yeterli olsa da CI'ın neden atladığının
görünür olması tercih edildi. Havuz davranışının yeni testleri
`test_db_pool.py` içinde.
"""

import unittest

# unittest.SkipTest kullaniliyor (pytest.skip yerine): hem pytest hem
# `python -m unittest` bunu modul seviyesinde atlama olarak kabul eder.
raise unittest.SkipTest(
    "SQLite donemi testi: veritabani.DB_NAME/BASE_DIR artik yok (PostgreSQL gecisi). "
    "Havuz testleri icin bkz. test_db_pool.py"
)
