"""Collector Modbus okuma stratejisi testleri.

Sahada olculen kok neden: gateway istekler arasinda bosluk bekliyor.
`read_device_async` icinde akim okumasindan hemen sonra, arada hic bekleme
olmadan voltaj okunuyordu. 24 saatlik logda:

    Voltaj (29) okunamadi   -> 1674 hata   (bosluksuz giden tek istek)
    Guc/Isi (33-44)         ->    1 hata   (oncesinde 0.5 sn bekleme var)

Cihaz bazinda: uretim/1 hic hata vermedi, uretim/2 ve mekanik/1 dongulerin
~%60'ini kaybetti (1440 beklenen satira karsi 312 ve 364 satir).

Cozum iki parcali:
  1. Yakin adres araliklari tek blokta okunur (`okuma_plani`), boylece
     bosluksuz ardisik istek kalmaz ve istek sayisi duser. Ayrica register 36
     eskiden her dongude iki kez okunuyordu (hem tekil hem 33-44 blogunda).
  2. Kalan her istekten once gateway boslugu birakilir; sureler .env'den
     ayarlanabilir.
"""

import unittest
from unittest.mock import patch

import collector_async as ca


# Uretimdeki gercek ayarlar (2026-08-05, ayarlar tablosundan)
URETIM_ARALIKLARI = [
    ("akim", 26, 3),
    ("voltaj", 29, 3),
    ("guc", 33, 1),
    ("isi", 44, 1),
    ("uretim", 36, 1),
]


class TestOkumaPlani(unittest.TestCase):
    def test_uretim_ayarlari_istek_sayisini_dusurur(self):
        plan = ca.okuma_plani(URETIM_ARALIKLARI, max_blok=16)

        self.assertEqual(
            len(plan), 2,
            f"5 aralik en fazla 2 istege inmeli, plan: {plan}"
        )
        # Eski kod 4 ayri istek yapiyordu (akim, voltaj, uretim, guc+isi).
        self.assertLess(len(plan), 4)

    def test_ardisik_araliklar_birlesir(self):
        plan = ca.okuma_plani([("akim", 26, 3), ("voltaj", 29, 3)], max_blok=16)

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["start"], 26)
        self.assertEqual(plan[0]["count"], 6)
        self.assertEqual(plan[0]["offsetler"], {"akim": 0, "voltaj": 3})

    def test_max_blok_asilirsa_ayrilir(self):
        plan = ca.okuma_plani([("akim", 26, 3), ("isi", 44, 1)], max_blok=16)

        self.assertEqual(len(plan), 2)
        self.assertEqual([g["start"] for g in plan], [26, 44])

    def test_max_blok_sinirinda_birlesir(self):
        # 26..41 tam 16 register
        plan = ca.okuma_plani([("a", 26, 3), ("b", 41, 1)], max_blok=16)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["count"], 16)

    def test_max_blok_bir_asarsa_ayrilir(self):
        # 26..42 = 17 register
        plan = ca.okuma_plani([("a", 26, 3), ("b", 42, 1)], max_blok=16)
        self.assertEqual(len(plan), 2)

    def test_ic_ice_aralik_tek_kez_okunur(self):
        """uretim(36) guc(33)..isi(44) araligi icinde; iki kez okunmamali."""
        plan = ca.okuma_plani(
            [("guc", 33, 1), ("uretim", 36, 1), ("isi", 44, 1)], max_blok=16
        )

        self.assertEqual(len(plan), 1)
        grup = plan[0]
        self.assertEqual(grup["start"], 33)
        self.assertEqual(grup["count"], 12)
        self.assertEqual(grup["offsetler"], {"guc": 0, "uretim": 3, "isi": 11})

    def test_sirasiz_girdi_ayni_plani_verir(self):
        duz = ca.okuma_plani(URETIM_ARALIKLARI, max_blok=16)
        ters = ca.okuma_plani(list(reversed(URETIM_ARALIKLARI)), max_blok=16)

        self.assertEqual(
            [(g["start"], g["count"], g["offsetler"]) for g in duz],
            [(g["start"], g["count"], g["offsetler"]) for g in ters],
        )

    def test_tek_aralik(self):
        plan = ca.okuma_plani([("guc", 33, 1)], max_blok=16)
        self.assertEqual(len(plan), 1)
        self.assertEqual((plan[0]["start"], plan[0]["count"]), (33, 1))

    def test_fallback_icin_aralik_bilgisi_korunur(self):
        plan = ca.okuma_plani(URETIM_ARALIKLARI, max_blok=16)
        tum_adlar = set()
        for grup in plan:
            self.assertEqual(set(grup["offsetler"]), set(grup["araliklar"]))
            tum_adlar |= set(grup["araliklar"])

        self.assertEqual(tum_adlar, {"akim", "voltaj", "guc", "isi", "uretim"})


# ─────────────────────────────────────────────
# Taklit async Modbus istemcisi
# ─────────────────────────────────────────────

class SahteYanit:
    def __init__(self, registers=None, error=False):
        self.registers = registers or []
        self._error = error

    def isError(self):
        return self._error


class SahteAsyncClient:
    """Istekleri kaydeder; reddedilecek adres araliklari verilebilir."""

    def __init__(self, reddedilen_bloklar=(), register_degerleri=None):
        self.connected = True
        self.istekler = []            # [("holding"/"input", start, count)]
        self.reddedilen = set(reddedilen_bloklar)
        self.degerler = register_degerleri or {}

    async def connect(self):
        self.connected = True
        return True

    def close(self):
        self.connected = False

    def _oku(self, tur, address, count):
        self.istekler.append((tur, address, count))
        if (address, count) in self.reddedilen:
            return SahteYanit(error=True)
        return SahteYanit([self.degerler.get(address + i, 0) for i in range(count)])

    async def read_holding_registers(self, address, count, slave):
        return self._oku("holding", address, count)

    async def read_input_registers(self, address, count, slave):
        return self._oku("input", address, count)


class AsyncOkumaTestTemeli(unittest.IsolatedAsyncioTestCase):
    """asyncio.sleep taklit edilir: testler gercek beklemez, sureler kaydedilir."""

    async def asyncSetUp(self):
        self.beklemeler = []

        async def sahte_sleep(sure):
            self.beklemeler.append(sure)

        self._patcher = patch.object(ca.asyncio, "sleep", sahte_sleep)
        self._patcher.start()

    async def asyncTearDown(self):
        self._patcher.stop()


class TestMetrikleriOku(AsyncOkumaTestTemeli):
    async def test_uretim_ayarlarinda_iki_istek_yapar(self):
        client = SahteAsyncClient(register_degerleri={
            26: 11, 27: 12, 28: 13,      # akim a/b/c
            29: 21, 30: 22, 31: 23,      # voltaj ab/bc/ca
            33: 500,                      # guc
            36: 77,                       # uretim
            44: 40,                       # isi
        })

        degerler = await ca.metrikleri_oku(
            client, 1, URETIM_ARALIKLARI, istek_arasi_sn=0.5, max_blok=16
        )

        self.assertEqual(
            len(client.istekler), 2,
            f"eski kod 4 istek yapiyordu, istekler: {client.istekler}"
        )
        self.assertEqual(degerler["akim"], [11, 12, 13])
        self.assertEqual(degerler["voltaj"], [21, 22, 23])
        self.assertEqual(degerler["guc"], [500])
        self.assertEqual(degerler["uretim"], [77])
        self.assertEqual(degerler["isi"], [40])

    async def test_istekler_arasinda_bosluk_birakilir(self):
        client = SahteAsyncClient()

        await ca.metrikleri_oku(client, 1, URETIM_ARALIKLARI,
                                istek_arasi_sn=0.5, max_blok=16)

        # 2 istek -> aralarinda 1 bekleme (ilk istekten once beklenmez;
        # dongu basindaki ilk gecikme read_device_async'te uygulanir).
        self.assertEqual(self.beklemeler, [0.5])

    async def test_hicbir_istek_bosluksuz_gitmez(self):
        """Asil regresyon: bosluksuz ardisik istek kalmamali."""
        client = SahteAsyncClient()

        await ca.metrikleri_oku(client, 1, URETIM_ARALIKLARI,
                                istek_arasi_sn=0.5, max_blok=16)

        self.assertEqual(
            len(self.beklemeler), len(client.istekler) - 1,
            "ilk istek disinda her istekten once bir bekleme olmali"
        )
        self.assertTrue(all(s > 0 for s in self.beklemeler))

    async def test_blok_reddedilirse_araliklar_tek_tek_okunur(self):
        """6+ register'lik blogu kabul etmeyen cihaz eski davranisla calisir."""
        # 26..36 (11 register) blogunu reddet, tek tek okumalari kabul et
        client = SahteAsyncClient(
            reddedilen_bloklar=[(26, 11), (26, 6), (26, 8)],
            register_degerleri={26: 11, 27: 12, 28: 13, 29: 21, 30: 22, 31: 23,
                                33: 500, 36: 77, 44: 40},
        )

        degerler = await ca.metrikleri_oku(
            client, 1, URETIM_ARALIKLARI, istek_arasi_sn=0.5, max_blok=16
        )

        self.assertEqual(degerler["akim"], [11, 12, 13])
        self.assertEqual(degerler["voltaj"], [21, 22, 23])
        self.assertEqual(degerler["guc"], [500])
        self.assertEqual(degerler["isi"], [40])

    async def test_okunamayan_aralik_sonuca_girmez(self):
        """Cagiran taraf eksik metrigi ayirt edebilmeli (hard/soft fail karari)."""
        client = SahteAsyncClient(reddedilen_bloklar=[(44, 1)])

        degerler = await ca.metrikleri_oku(
            client, 1, [("guc", 33, 1), ("isi", 44, 1)],
            istek_arasi_sn=0.5, max_blok=4
        )

        self.assertIn("guc", degerler)
        self.assertNotIn("isi", degerler)


class TestReadRegistersSmart(AsyncOkumaTestTemeli):
    async def test_holding_basarisizsa_input_denenir(self):
        client = SahteAsyncClient(reddedilen_bloklar=[(29, 3)])
        # holding reddedilecek, input da ayni blogu reddedecek -> None
        sonuc = await ca.read_registers_smart(client, 29, 3, 1, istek_arasi_sn=0.5)

        self.assertIsNone(sonuc)
        self.assertEqual([t[0] for t in client.istekler], ["holding", "input"])

    async def test_holding_ve_input_arasinda_bosluk_birakilir(self):
        """Bu ikili de eskiden bosluksuz gidiyordu."""
        client = SahteAsyncClient(reddedilen_bloklar=[(29, 3)])

        await ca.read_registers_smart(client, 29, 3, 1, istek_arasi_sn=0.5)

        self.assertEqual(self.beklemeler, [0.5])

    async def test_holding_basarilıysa_input_denenmez(self):
        client = SahteAsyncClient(register_degerleri={29: 220})

        sonuc = await ca.read_registers_smart(client, 29, 1, 1, istek_arasi_sn=0.5)

        self.assertEqual(sonuc, [220])
        self.assertEqual(len(client.istekler), 1)
        self.assertEqual(self.beklemeler, [], "basarili yolda bekleme olmamali")


class TestGecikmeAyarlanabilir(unittest.TestCase):
    def test_varsayilan_gecikmeler_makul(self):
        self.assertGreater(ca.GATEWAY_ILK_GECIKME_SN, 0)
        self.assertGreater(ca.GATEWAY_ISTEK_ARASI_SN, 0)
        self.assertGreater(ca.GATEWAY_ALARM_GECIKME_SN, 0,
                           "alarm oncesi bekleme 0.05 sn idi, yani pratikte bosluksuzdu")
        self.assertGreaterEqual(ca.MAX_BLOK_REGISTER, 12,
                                "uretimde 33-44 (12 register) sorunsuz okunuyor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
