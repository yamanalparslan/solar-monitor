"""Bağlantı havuzu sızıntısı regresyon testleri.

Arka plan: `veritabani.PooledConnectionProxy.close()` bağlantıyı kapatmaz,
havuza geri verir. Bu yüzden `close()` çağrılmadan çıkılan her kod yolu
havuzdan kalıcı olarak bir slot eksiltir. `maxconn` dolduğunda `getconn()`
hata verir, `get_db_connection()` None döner ve panel/API/collector/healthcheck
hep birlikte veritabanısız kalır — konteyner yeniden başlatılmadan toparlamaz.

Bu testler gerçek bir PostgreSQL gerektirmez: havuz ve bağlantı taklit edilir,
her fonksiyon hem başarılı hem hatalı sorgu yolunda koşturulur ve havuzdaki
açık bağlantı sayısının sıfıra döndüğü doğrulanır.

Çalıştırma:
    python -m pytest test_db_pool.py -v
    python -m unittest test_db_pool -v
"""

import unittest

import veritabani


# ─────────────────────────────────────────────
# Taklit havuz ve bağlantı
# ─────────────────────────────────────────────

class FakeCursor:
    def __init__(self, hata=False, rows=None):
        self._hata = hata
        self._rows = rows if rows is not None else []

    def execute(self, *args, **kwargs):
        if self._hata:
            raise RuntimeError("simulasyon: SQL hatasi")

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        pass


class FakeConn:
    def __init__(self, hata=False, rows=None):
        self.autocommit = False
        self.closed = False
        self.commit_sayisi = 0
        self.rollback_sayisi = 0
        self._hata = hata
        self._rows = rows

    def cursor(self, *args, **kwargs):
        return FakeCursor(self._hata, self._rows)

    def commit(self):
        self.commit_sayisi += 1

    def rollback(self):
        self.rollback_sayisi += 1

    def close(self):
        self.closed = True


class FakePool:
    """maxconn sınırlı havuz: geri verilmeyen bağlantı slot tüketir."""

    def __init__(self, maxconn=20, hata=False, rows=None):
        self.maxconn = maxconn
        self.verilen = 0
        self.geri_alinan = 0
        self.son_conn = None
        self._hata = hata
        self._rows = rows

    def getconn(self):
        if self.acikta >= self.maxconn:
            raise RuntimeError("connection pool exhausted")
        self.verilen += 1
        self.son_conn = FakeConn(self._hata, self._rows)
        return self.son_conn

    def putconn(self, conn):
        self.geri_alinan += 1

    @property
    def acikta(self):
        return self.verilen - self.geri_alinan


class HavuzTestTemeli(unittest.TestCase):
    """Testler arasında modül seviyesindeki havuzu izole eder."""

    def setUp(self):
        self._orijinal_pool = veritabani._pool

    def tearDown(self):
        veritabani._pool = self._orijinal_pool

    def havuz_kur(self, **kwargs):
        pool = FakePool(**kwargs)
        veritabani._pool = pool
        return pool


# ─────────────────────────────────────────────
# Proxy davranışı
# ─────────────────────────────────────────────

class TestPooledConnectionProxy(HavuzTestTemeli):
    def test_close_baglantiyi_kapatmaz_havuza_geri_verir(self):
        pool = self.havuz_kur()
        conn = veritabani.get_db_connection()
        conn.close()
        self.assertEqual(pool.acikta, 0)
        self.assertFalse(pool.son_conn.closed, "baglanti gercekten kapatilmamali")

    def test_cift_close_havuza_iki_kez_eklemez(self):
        pool = self.havuz_kur()
        conn = veritabani.get_db_connection()
        conn.close()
        conn.close()
        self.assertEqual(
            pool.geri_alinan, 1,
            "ayni proxy iki kez kapatilirsa baglanti havuza iki kez eklenmemeli"
        )

    def test_atama_gercek_baglantiya_yonlendirilir(self):
        """`conn.autocommit = True` proxy'de kalmamali, gercek baglantiya gecmeli.

        __setattr__ olmadigi surece atama yalnizca proxy nesnesinde bir alan
        olusturuyordu ve gercek baglanti autocommit=False kaliyordu. Sonuc:
        autocommit gerektiren TimescaleDB DDL'i (create_hypertable, continuous
        aggregate, add_retention_policy) transaction icinde kosup putconn'daki
        rollback ile sessizce geri aliniyordu. Temiz kurulumda hypertable hic
        olusmuyordu; `conn.autocommit` True gorundugu icin hata da yoktu.
        """
        pool = self.havuz_kur()
        conn = veritabani.get_db_connection()

        conn.autocommit = True

        self.assertTrue(
            pool.son_conn.autocommit,
            "atama gercek psycopg2 baglantisina gecmeli — aksi halde DDL rollback olur"
        )

    def test_proxy_kendi_alanlari_baglantiya_yazilmaz(self):
        pool = self.havuz_kur()
        conn = veritabani.get_db_connection()

        self.assertFalse(hasattr(pool.son_conn, "_pool"))
        self.assertFalse(hasattr(pool.son_conn, "_returned"))
        self.assertIs(conn._conn, pool.son_conn)

    def test_autocommit_geri_vermeden_once_normalize_edilir(self):
        # DDL bloklari (TimescaleDB kurulumu, retention policy) autocommit'i
        # True'ya cekiyor; bu durum havuzdaki baglantiya sizmamali.
        pool = self.havuz_kur()
        conn = veritabani.get_db_connection()
        conn.autocommit = True
        conn.close()
        self.assertFalse(pool.son_conn.autocommit)

    def test_havuz_tukendiginde_none_doner(self):
        pool = self.havuz_kur(maxconn=1)
        birinci = veritabani.get_db_connection()
        self.assertIsNotNone(birinci)
        self.assertIsNone(veritabani.get_db_connection(), "havuz dolu: None donmeli")
        birinci.close()
        self.assertIsNotNone(veritabani.get_db_connection(), "slot bosaldi: yeniden verilmeli")
        self.assertEqual(pool.acikta, 1)


# ─────────────────────────────────────────────
# db_cursor context manager
# ─────────────────────────────────────────────

class TestDbCursor(HavuzTestTemeli):
    def test_basarili_yolda_commit_ve_geri_verme(self):
        pool = self.havuz_kur()
        with veritabani.db_cursor(commit=True) as cur:
            cur.execute("SELECT 1")
        self.assertEqual(pool.acikta, 0)
        self.assertEqual(pool.son_conn.commit_sayisi, 1)

    def test_hata_yolunda_rollback_ve_geri_verme(self):
        pool = self.havuz_kur(hata=True)
        with self.assertRaises(RuntimeError):
            with veritabani.db_cursor(commit=True) as cur:
                cur.execute("SELECT 1")
        self.assertEqual(pool.acikta, 0, "hata halinde de baglanti havuza donmeli")
        self.assertEqual(pool.son_conn.rollback_sayisi, 1)
        self.assertEqual(pool.son_conn.commit_sayisi, 0)

    def test_baglanti_yoksa_dbbaglantiyok_yukseltir(self):
        self.havuz_kur(maxconn=0)
        with self.assertRaises(veritabani.DBBaglantiYok):
            with veritabani.db_cursor():
                pass


# ─────────────────────────────────────────────
# Asıl regresyon: fonksiyonlar sızdırıyor mu?
# ─────────────────────────────────────────────

# (ad, cagri) — hepsi tek basina cagrilabilir olmali
SORGU_FONKSIYONLARI = [
    ("ayar_oku", lambda: veritabani.ayar_oku("refresh_rate", "60", "mekanik")),
    ("ayar_yaz", lambda: veritabani.ayar_yaz("refresh_rate", "60", "mekanik")),
    ("tum_ayarlari_oku", lambda: veritabani.tum_ayarlari_oku("mekanik")),
    ("son_verileri_getir", lambda: veritabani.son_verileri_getir(1, 10, "mekanik")),
    ("karsilastirma_verisi_getir", lambda: veritabani.karsilastirma_verisi_getir(1, 10, "mekanik")),
    ("tum_cihazlarin_son_durumu", lambda: veritabani.tum_cihazlarin_son_durumu("mekanik")),
    ("saatlik_ozet_getir", lambda: veritabani.saatlik_ozet_getir(1, "2026-08-01", "2026-08-05", "mekanik")),
    ("audit_log_kaydet", lambda: veritabani.audit_log_kaydet("test", "islem", "detay", "mekanik")),
    ("audit_log_getir", lambda: veritabani.audit_log_getir(10, "mekanik")),
    ("veri_kaydet", lambda: veritabani.veri_kaydet("mekanik", 1, 100, 220, 5, 20)),
    ("veri_ekle", lambda: veritabani.veri_ekle(1, {"guc": 100, "voltaj": 220}, "mekanik")),
    ("gunluk_uretim_hesapla", lambda: veritabani.gunluk_uretim_hesapla("2026-08-05", 1, "mekanik")),
    ("hata_sayilarini_getir", lambda: veritabani.hata_sayilarini_getir("2026-08-01", "2026-08-05", 1, "mekanik")),
    ("tarih_araliginda_ortalamalar", lambda: veritabani.tarih_araliginda_ortalamalar("2026-08-01", "2026-08-05", 1, "mekanik")),
    ("haftalik_uretim_ozeti", lambda: veritabani.haftalik_uretim_ozeti("mekanik", 7)),
    ("veritabani_istatistikleri", lambda: veritabani.veritabani_istatistikleri("mekanik")),
    ("gecmis_alarmlari_getir", lambda: veritabani.gecmis_alarmlari_getir("mekanik", 10)),
    ("heartbeat_yaz", lambda: veritabani.heartbeat_yaz("mekanik", 12.5, 3, 0, 60.0)),
    ("heartbeat_getir", lambda: veritabani.heartbeat_getir()),
    ("heartbeat_getir(fabrika)", lambda: veritabani.heartbeat_getir("mekanik")),
    ("cihaz_cevap_durumlarini_guncelle", lambda: veritabani.cihaz_cevap_durumlarini_guncelle(
        [("mekanik", 1, True), ("mekanik", 2, False)])),
    ("cevapsiz_cihazlari_getir", lambda: veritabani.cevapsiz_cihazlari_getir()),
    ("cihaz_calisabilirligi", lambda: veritabani.cihaz_calisabilirligi(
        "2026-08-04 00:00:00", "2026-08-05 00:00:00", "mekanik")),
]


class TestFonksiyonlarSizdirmiyor(HavuzTestTemeli):
    def test_hatali_sorgu_yolunda_sizinti_yok(self):
        """Her SQL hatası bir slot yiyorsa 20 hatadan sonra sistem ölür."""
        for ad, cagri in SORGU_FONKSIYONLARI:
            with self.subTest(fonksiyon=ad):
                pool = self.havuz_kur(hata=True)
                try:
                    cagri()
                except Exception as e:  # noqa: BLE001 — bazi fonksiyonlar yükseltebilir
                    hata = e
                else:
                    hata = None
                self.assertEqual(
                    pool.acikta, 0,
                    f"{ad}: SQL hatasi sonrasi baglanti havuza donmedi "
                    f"(verilen={pool.verilen}, geri={pool.geri_alinan}, hata={hata})"
                )

    def test_basarili_yolda_sizinti_yok(self):
        for ad, cagri in SORGU_FONKSIYONLARI:
            with self.subTest(fonksiyon=ad):
                pool = self.havuz_kur(hata=False, rows=[])
                try:
                    cagri()
                except Exception as e:  # noqa: BLE001
                    hata = e
                else:
                    hata = None
                self.assertEqual(
                    pool.acikta, 0,
                    f"{ad}: basarili yolda baglanti havuza donmedi (hata={hata})"
                )

    def test_tekrarlanan_hata_havuzu_tuketmez(self):
        """Asil senaryo: gecici DB kesintisi maxconn kadar tekrarlaninca ne olur?

        Duzeltme oncesi bu test 20. iterasyonda `acikta == 20` ile patlardi ve
        sonrasinda hicbir fonksiyon veri okuyamazdi.
        """
        pool = self.havuz_kur(maxconn=20, hata=True)
        for i in range(60):
            veritabani.tum_cihazlarin_son_durumu("mekanik")
            veritabani.son_verileri_getir(1, 10, "mekanik")
            veritabani.ayar_oku("refresh_rate", "60", "mekanik")
            self.assertEqual(pool.acikta, 0, f"{i + 1}. iterasyonda sizinti olustu")

        # Havuz hala calisiyor olmali.
        self.assertIsNotNone(veritabani.get_db_connection())


if __name__ == "__main__":
    unittest.main(verbosity=2)
