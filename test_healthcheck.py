"""Healthcheck karar mantigi testleri.

Eski olcut "son olcum ne kadar eski" idi ve iki farkli durumu ayirt
edemiyordu: collector'in kendi arizasi ile cihazin cevap vermemesi. Sahada
okumalarin buyuk bolumu basarisiz oluyor (24 saatte 1611 [CEVAP YOK], cihaz
basina 39 dakikaya varan bosluklar), yani olcum akisi mesru sekilde
kesintili — bu olcutle collector sapasaglam calisirken de unhealthy
gorunebiliyor.

Yeni kural:
  * collector dongu ceviriyorsa (collector_heartbeat tazeyse) -> healthy
  * cihazlar cevap vermiyorsa -> healthy + degraded
  * collector dongu cevirmiyorsa ya da DB yoksa -> unhealthy

Testler gercek PostgreSQL gerektirmez; veritabani fonksiyonlari taklit edilir.
"""

import unittest
from datetime import datetime, timedelta

import healthcheck


class HealthcheckTestTemeli(unittest.TestCase):
    """veritabani cagrilarini taklit eder, testler arasinda geri yukler."""

    def setUp(self):
        self._orijinal = {
            "test_database": healthcheck.test_database,
            "heartbeat_getir": healthcheck.veritabani.heartbeat_getir,
            "cevapsiz_cihazlari_getir": healthcheck.veritabani.cevapsiz_cihazlari_getir,
            "FABRIKALAR": dict(healthcheck.veritabani.FABRIKALAR),
        }

    def tearDown(self):
        healthcheck.test_database = self._orijinal["test_database"]
        healthcheck.veritabani.heartbeat_getir = self._orijinal["heartbeat_getir"]
        healthcheck.veritabani.cevapsiz_cihazlari_getir = self._orijinal["cevapsiz_cihazlari_getir"]
        healthcheck.veritabani.FABRIKALAR.clear()
        healthcheck.veritabani.FABRIKALAR.update(self._orijinal["FABRIKALAR"])

    def ortam_kur(self, kalp_atislari, cevapsizlar=None, db_ok=True, fabrikalar=("mekanik",)):
        healthcheck.test_database = lambda: (db_ok, "taklit DB")
        healthcheck.veritabani.heartbeat_getir = lambda fabrika_id=None: (
            kalp_atislari.get(fabrika_id) if fabrika_id else kalp_atislari
        )
        healthcheck.veritabani.cevapsiz_cihazlari_getir = lambda fabrika_id=None: (cevapsizlar or [])
        healthcheck.veritabani.FABRIKALAR.clear()
        healthcheck.veritabani.FABRIKALAR.update({f: {"ad": f} for f in fabrikalar})

    @staticmethod
    def kalp_atisi(yas_sn, okunan=3, cevapsiz=0, periyot=60.0):
        return {
            "son_dongu": datetime.now() - timedelta(seconds=yas_sn),
            "dongu_suresi_sn": 5.0,
            "okunan_cihaz": okunan,
            "cevapsiz_cihaz": cevapsiz,
            "beklenen_periyot_sn": periyot,
        }


class TestCihazSessizligi(HealthcheckTestTemeli):
    """Asil regresyon: cihazlar cevap vermiyor ama collector calisiyor."""

    def test_cihazlar_sessizken_healthy_ama_degraded(self):
        self.ortam_kur(
            kalp_atislari={"mekanik": self.kalp_atisi(yas_sn=30, okunan=0, cevapsiz=3)},
            cevapsizlar=[
                {"fabrika_id": "mekanik", "slave_id": 1, "baslangic_zamani": datetime.now()},
                {"fabrika_id": "mekanik", "slave_id": 2, "baslangic_zamani": datetime.now()},
                {"fabrika_id": "mekanik", "slave_id": 3, "baslangic_zamani": datetime.now()},
            ],
        )

        sonuc = healthcheck.durum_topla()

        self.assertEqual(
            sonuc["status"], "healthy",
            "cihaz sessizligi collector arizasi gibi raporlanmamali — "
            "duzeltme oncesi burada unhealthy donuyordu"
        )
        self.assertTrue(sonuc["degraded"], "cihazlardan veri gelmiyorsa degraded bildirilmeli")
        self.assertFalse(sonuc["checks"]["veri_akisi"]["ok"])
        self.assertFalse(sonuc["checks"]["veri_akisi"]["kritik"])
        self.assertTrue(sonuc["checks"]["collector_canli"]["ok"])

    def test_butun_cihazlar_okunuyorsa_temiz(self):
        self.ortam_kur(kalp_atislari={"mekanik": self.kalp_atisi(yas_sn=20, okunan=3)})

        sonuc = healthcheck.durum_topla()

        self.assertEqual(sonuc["status"], "healthy")
        self.assertFalse(sonuc["degraded"])


class TestCollectorOlduyse(HealthcheckTestTemeli):
    """Yeniden baslatmanin duzeltebilecegi durumlar unhealthy olmali."""

    def test_kalp_atisi_eskiyse_unhealthy(self):
        # periyot 60 sn -> tolerans max(180, 180) = 180 sn
        self.ortam_kur(kalp_atislari={"mekanik": self.kalp_atisi(yas_sn=600, okunan=3)})

        sonuc = healthcheck.durum_topla()

        self.assertEqual(sonuc["status"], "unhealthy")
        self.assertFalse(sonuc["checks"]["collector_canli"]["ok"])

    def test_tolerans_sinirinin_altinda_healthy(self):
        self.ortam_kur(kalp_atislari={"mekanik": self.kalp_atisi(yas_sn=170, okunan=3)})

        self.assertEqual(healthcheck.durum_topla()["status"], "healthy")

    def test_uzun_refresh_rate_toleransi_buyutur(self):
        # periyot 300 sn -> tolerans 900 sn; 600 sn'lik yas hala kabul edilir
        self.ortam_kur(
            kalp_atislari={"mekanik": self.kalp_atisi(yas_sn=600, okunan=3, periyot=300.0)}
        )

        self.assertEqual(healthcheck.durum_topla()["status"], "healthy")

    def test_db_yoksa_unhealthy(self):
        self.ortam_kur(kalp_atislari={"mekanik": self.kalp_atisi(yas_sn=10)}, db_ok=False)

        sonuc = healthcheck.durum_topla()

        self.assertEqual(sonuc["status"], "unhealthy")
        self.assertFalse(sonuc["degraded"], "DB yoksa degraded degil dogrudan unhealthy")


class TestKenarDurumlar(HealthcheckTestTemeli):
    def test_hic_kalp_atisi_yoksa_hosgorulu(self):
        """Ilk kurulum: collector henuz ilk dongusunu bitirmemis olabilir."""
        self.ortam_kur(kalp_atislari={})

        sonuc = healthcheck.durum_topla()

        self.assertEqual(sonuc["status"], "healthy")
        self.assertFalse(sonuc["degraded"])

    def test_devrede_olmayan_fabrika_unhealthy_yapmaz(self):
        """Ikinci fabrikada hic cihaz yoksa kalici unhealthy uretmemeli.

        Duzeltme oncesi 'uretim: hic veri yok' kaydi healthcheck'i surekli
        basarisiz kiliyordu.
        """
        self.ortam_kur(
            kalp_atislari={"mekanik": self.kalp_atisi(yas_sn=20, okunan=3)},
            fabrikalar=("mekanik", "uretim"),
        )

        sonuc = healthcheck.durum_topla()

        self.assertEqual(sonuc["status"], "healthy")
        self.assertIn("uretim", sonuc["checks"]["collector_canli"]["detail"])

    def test_heartbeat_okunamazsa_unhealthy(self):
        healthcheck.test_database = lambda: (True, "taklit DB")
        healthcheck.veritabani.heartbeat_getir = lambda fabrika_id=None: None
        healthcheck.veritabani.cevapsiz_cihazlari_getir = lambda fabrika_id=None: []

        sonuc = healthcheck.durum_topla()

        self.assertEqual(sonuc["status"], "unhealthy")

    def test_bir_cihaz_cevapsizken_degraded(self):
        """Kismi sessizlik de gorunur olmali ama restart tetiklememeli."""
        self.ortam_kur(
            kalp_atislari={"mekanik": self.kalp_atisi(yas_sn=20, okunan=2, cevapsiz=1)},
            cevapsizlar=[{"fabrika_id": "mekanik", "slave_id": 3,
                          "baslangic_zamani": datetime.now()}],
        )

        sonuc = healthcheck.durum_topla()

        self.assertEqual(sonuc["status"], "healthy")
        self.assertTrue(sonuc["degraded"])
        self.assertIn("mekanik/3", sonuc["checks"]["veri_akisi"]["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
