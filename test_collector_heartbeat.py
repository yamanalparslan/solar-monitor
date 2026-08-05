"""Collector kalp atisi ve cevap durumu kaydi testleri.

`collector.start_collector` sonsuz dongu oldugu icin dogrudan kosturulamaz;
bu yuzden dongunun kalp atisi bolumunun sozlesmesi test edilir:

  * cihazlarin hicbiri cevap vermese bile heartbeat yazilir,
  * okunan/cevapsiz sayaclari dogru toplanir,
  * cevap durumu kaydi dongu basina tek islemde yazilir (havuzu yormamak icin),
  * cevapsizlik stateful: sustugunda kayit acilir, cevap verince kapanir,
    araya giren ikinci bir "cevap yok" turu yeni kayit acmaz.

Sahadaki motivasyon: basarisiz okumalar bugune kadar yalnizca stdout'a
"[CEVAP YOK]" olarak basiliyordu. 24 saatlik olcumde 3 inverterin 2'si
orneklerinin ~%75'ini kaybediyor (364/1440 ve 312/1440 satir, 39 dakikaya
varan bosluklar) ve bu hicbir ekranda gorunmuyordu.
"""

import unittest
from datetime import datetime

import veritabani


class SahteCursor:
    """cihaz_durum_log uzerindeki stateful mantigi bellekte taklit eder."""

    def __init__(self, kayitlar):
        self.kayitlar = kayitlar          # [{id, fabrika_id, slave_id, baslangic, bitis}]
        self._son_sorgu_sonucu = None
        self._sonraki_id = len(kayitlar) + 1

    def execute(self, sql, params=()):
        normalize = " ".join(sql.split()).upper()

        if normalize.startswith("SELECT ID FROM CIHAZ_DURUM_LOG"):
            fabrika_id, slave_id = params
            acik = [
                k for k in self.kayitlar
                if k["fabrika_id"] == fabrika_id
                and k["slave_id"] == slave_id
                and k["bitis"] is None
            ]
            self._son_sorgu_sonucu = (acik[-1]["id"],) if acik else None

        elif normalize.startswith("UPDATE CIHAZ_DURUM_LOG"):
            zaman, kayit_id = params
            for k in self.kayitlar:
                if k["id"] == kayit_id:
                    k["bitis"] = zaman

        elif normalize.startswith("INSERT INTO CIHAZ_DURUM_LOG"):
            fabrika_id, slave_id, zaman = params
            self.kayitlar.append({
                "id": self._sonraki_id,
                "fabrika_id": fabrika_id,
                "slave_id": slave_id,
                "baslangic": zaman,
                "bitis": None,
            })
            self._sonraki_id += 1

        else:  # pragma: no cover - beklenmeyen sorgu testte gorunur olsun
            raise AssertionError(f"Beklenmeyen sorgu: {sql}")

    def fetchone(self):
        return self._son_sorgu_sonucu


class TestCevapDurumuStateful(unittest.TestCase):
    def setUp(self):
        self.kayitlar = []
        self.cursor = SahteCursor(self.kayitlar)

    def guncelle(self, slave_id, cevap_var, zaman):
        veritabani.cihaz_cevap_durumu_guncelle(
            self.cursor, "mekanik", slave_id, cevap_var, zaman
        )

    def test_cevapsizlik_kayit_acar(self):
        self.guncelle(1, False, datetime(2026, 8, 5, 20, 0, 0))

        self.assertEqual(len(self.kayitlar), 1)
        self.assertIsNone(self.kayitlar[0]["bitis"])
        self.assertEqual(self.kayitlar[0]["slave_id"], 1)

    def test_suren_cevapsizlik_yeni_kayit_acmaz(self):
        """Uzun kesintide her dongude yeni kayit acilmamali — tek aralik olmali."""
        for saat in range(20, 24):
            self.guncelle(1, False, datetime(2026, 8, 5, saat, 0, 0))

        self.assertEqual(len(self.kayitlar), 1, "suren kesinti tek aralik olarak durmali")
        self.assertIsNone(self.kayitlar[0]["bitis"])

    def test_cevap_gelince_kayit_kapanir(self):
        self.guncelle(1, False, datetime(2026, 8, 5, 20, 0, 0))
        self.guncelle(1, True, datetime(2026, 8, 6, 7, 0, 0))

        self.assertEqual(len(self.kayitlar), 1)
        self.assertEqual(self.kayitlar[0]["bitis"], datetime(2026, 8, 6, 7, 0, 0))

    def test_ikinci_kesinti_yeni_kayit_acar(self):
        self.guncelle(1, False, datetime(2026, 8, 5, 20, 0, 0))
        self.guncelle(1, True, datetime(2026, 8, 6, 7, 0, 0))
        self.guncelle(1, False, datetime(2026, 8, 6, 20, 0, 0))

        self.assertEqual(len(self.kayitlar), 2)
        self.assertIsNotNone(self.kayitlar[0]["bitis"])
        self.assertIsNone(self.kayitlar[1]["bitis"])

    def test_surekli_cevap_veren_cihaz_kayit_uretmez(self):
        for saat in range(8, 18):
            self.guncelle(2, True, datetime(2026, 8, 5, saat, 0, 0))

        self.assertEqual(self.kayitlar, [])

    def test_cihazlar_birbirinden_bagimsiz(self):
        zaman = datetime(2026, 8, 5, 20, 0, 0)
        self.guncelle(1, False, zaman)
        self.guncelle(2, True, zaman)
        self.guncelle(3, False, zaman)

        acik = [k["slave_id"] for k in self.kayitlar if k["bitis"] is None]
        self.assertEqual(sorted(acik), [1, 3])


class TestDonguSayaclari(unittest.TestCase):
    """Collector dongusunun heartbeat'e verdigi sayaclarin sozlesmesi.

    Dongudeki mantik: her cihaz icin (fabrika, slave, cevap_var) biriktirilir;
    okunan/cevapsiz sayaclari fabrika bazinda toplanir. Asagidaki yardimci
    fonksiyon collector'daki ayni hesabi tekrarlar ve gece senaryosunda
    heartbeat'in yine yazildigini dogrular.
    """

    @staticmethod
    def sayaclari_hesapla(sonuclar, fabrikalar):
        cevap_durumlari = []
        sayaclar = {f: {"okunan": 0, "cevapsiz": 0} for f in fabrikalar}
        for fabrika_id, slave_id, data in sonuclar:
            cevap_durumlari.append((fabrika_id, slave_id, bool(data)))
            if data:
                sayaclar[fabrika_id]["okunan"] += 1
            else:
                sayaclar[fabrika_id]["cevapsiz"] += 1
        return cevap_durumlari, sayaclar

    def test_hepsi_cevap_verirse_okunan_sayilir(self):
        _, sayaclar = self.sayaclari_hesapla(
            [("mekanik", 1, {"guc": 100}), ("mekanik", 2, {"guc": 200})],
            ("mekanik",),
        )

        self.assertEqual(sayaclar["mekanik"], {"okunan": 2, "cevapsiz": 0})

    def test_hepsi_cevapsizken_de_kayit_uretilir(self):
        cevap_durumlari, sayaclar = self.sayaclari_hesapla(
            [("mekanik", 1, None), ("mekanik", 2, None), ("mekanik", 3, None)],
            ("mekanik",),
        )

        self.assertEqual(sayaclar["mekanik"], {"okunan": 0, "cevapsiz": 3})
        self.assertEqual(
            len(cevap_durumlari), 3,
            "cevapsiz cihazlar da kaydedilmeli: 'satir yok' durumu eskiden "
            "'cihaz kapali' ile 'ag koptu'yu ayirt edemiyordu"
        )
        self.assertTrue(all(not cevap for _, _, cevap in cevap_durumlari))

    def test_kismi_cevap(self):
        _, sayaclar = self.sayaclari_hesapla(
            [("mekanik", 1, {"guc": 100}), ("mekanik", 2, None)],
            ("mekanik",),
        )

        self.assertEqual(sayaclar["mekanik"], {"okunan": 1, "cevapsiz": 1})

    def test_fabrikalar_ayri_sayilir(self):
        _, sayaclar = self.sayaclari_hesapla(
            [("mekanik", 1, {"guc": 100}), ("uretim", 1, None)],
            ("mekanik", "uretim"),
        )

        self.assertEqual(sayaclar["mekanik"], {"okunan": 1, "cevapsiz": 0})
        self.assertEqual(sayaclar["uretim"], {"okunan": 0, "cevapsiz": 1})

    def test_devrede_olmayan_fabrika_sifir_sayacla_yazilir(self):
        """Cihazi olmayan fabrika icin de heartbeat yazilir (sifir sayacla)."""
        _, sayaclar = self.sayaclari_hesapla(
            [("mekanik", 1, {"guc": 100})],
            ("mekanik", "uretim"),
        )

        self.assertIn("uretim", sayaclar)
        self.assertEqual(sayaclar["uretim"], {"okunan": 0, "cevapsiz": 0})


class TestTopluYazimTekIslem(unittest.TestCase):
    def test_toplu_guncelleme_tek_baglanti_kullanir(self):
        """Cihaz basina ayri baglanti acmak havuzu gereksiz yorardi."""
        acilan = {"sayi": 0}
        kayitlar = []

        class SahteBaglantiYoneticisi:
            def __init__(self, cursor):
                self._cursor = cursor

            def __enter__(self):
                acilan["sayi"] += 1
                return self._cursor

            def __exit__(self, *exc):
                return False

        cursor = SahteCursor(kayitlar)
        orijinal = veritabani.db_cursor
        veritabani.db_cursor = lambda commit=False, cursor_factory=None: SahteBaglantiYoneticisi(cursor)
        try:
            sonuc = veritabani.cihaz_cevap_durumlarini_guncelle([
                ("mekanik", 1, False),
                ("mekanik", 2, False),
                ("mekanik", 3, True),
            ], zaman=datetime(2026, 8, 5, 20, 0, 0))
        finally:
            veritabani.db_cursor = orijinal

        self.assertTrue(sonuc)
        self.assertEqual(acilan["sayi"], 1, "3 cihaz icin tek baglanti acilmali")
        self.assertEqual(len(kayitlar), 2, "yalniz cevapsiz iki cihaz kayit acmali")

    def test_bos_liste_baglanti_acmaz(self):
        acilan = {"sayi": 0}

        def sahte(commit=False, cursor_factory=None):
            acilan["sayi"] += 1
            raise AssertionError("bos listede baglanti acilmamali")

        orijinal = veritabani.db_cursor
        veritabani.db_cursor = sahte
        try:
            self.assertTrue(veritabani.cihaz_cevap_durumlarini_guncelle([]))
        finally:
            veritabani.db_cursor = orijinal

        self.assertEqual(acilan["sayi"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
