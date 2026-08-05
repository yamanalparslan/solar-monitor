"""collector.py (senkron collector) testleri.

NOT: Bu testler daha once hic kosmuyordu. collector.py import edilirken
`sys.stdout` yeni bir TextIOWrapper ile degistiriliyordu; bu pytest'in cikti
yakalamasini bozdugu icin dosyadan hicbir test toplanamiyordu (sessiz sifir
kapsama). stdout artik `reconfigure` ile ayarlaniyor ve testler kosuyor.

Eski surumleri `read_device`'in artik kullanmadigi davranislari test ediyordu:
input-register fallback'i ve `guc = voltaj * akim` sentezi. Ikisi de bilincli
olarak kaldirildi (bkz. collector.py icindeki "sahte guc uretilmesini
engelledik" notu). Testler guncel davranisa gore yeniden yazildi.
"""

import pytest

import collector


# ─────────────────────────────────────────────
# Taklit Modbus istemcisi
# ─────────────────────────────────────────────

# Testlerde kullanilan register haritasi
AKIM_ADDR, VOLT_ADDR, GUC_ADDR, ISI_ADDR = 70, 73, 76, 94
ALARM_107, ALARM_111 = 107, 111

HAM_AKIM, HAM_VOLT, HAM_GUC, HAM_ISI = 8, 7828, 500, 314

CONFIG = {
    "guc_addr": GUC_ADDR,
    "volt_addr": VOLT_ADDR,
    "akim_addr": AKIM_ADDR,
    "isi_addr": ISI_ADDR,
    "guc_scale": 0.01,
    "volt_scale": 0.1,
    "akim_scale": 0.01,
    "isi_scale": 0.01,
    "alarm_registers": [
        {"addr": ALARM_107, "key": "hata_kodu", "count": 2},
        {"addr": ALARM_111, "key": "hata_kodu_111", "count": 1},
    ],
}


class FakeResponse:
    def __init__(self, registers=None, error=False):
        self.registers = registers or []
        self._error = error

    def isError(self):
        return self._error

    def __str__(self):
        return "fake-error" if self._error else "fake-ok"


class FakeClient:
    """read_device'in yaptigi iki blok okumaya cevap verir.

    1. Temel metrikler: min(adres)..max(adres) tek blok (70..94 -> 25 register)
    2. Alarmlar: min(alarm)..max(alarm)+1 tek blok (107..111 -> 5 register)
    """

    TEMEL_START = AKIM_ADDR
    TEMEL_COUNT = (ISI_ADDR - AKIM_ADDR) + 1  # 25
    ALARM_START = ALARM_107
    ALARM_COUNT = (ALARM_111 + 1) - ALARM_107  # 5

    def __init__(self):
        self.connected = True
        self.okunan_bloklar = []

    def connect(self):
        self.connected = True
        return True

    def close(self):
        self.connected = False

    def _temel_blok(self):
        regs = [0] * self.TEMEL_COUNT
        regs[AKIM_ADDR - self.TEMEL_START] = HAM_AKIM
        regs[VOLT_ADDR - self.TEMEL_START] = HAM_VOLT
        regs[GUC_ADDR - self.TEMEL_START] = HAM_GUC
        regs[ISI_ADDR - self.TEMEL_START] = HAM_ISI
        return regs

    def _alarm_blok(self):
        # hata_kodu 32-bit: (yuksek << 16) | alcak  ->  (0 << 16) | 3 = 3
        regs = [0] * self.ALARM_COUNT
        regs[0] = 3                                    # 107 alcak word
        regs[1] = 0                                    # 108 yuksek word
        regs[ALARM_111 - self.ALARM_START] = 5         # 111
        return regs

    def read_holding_registers(self, address, count, slave):
        self.okunan_bloklar.append((address, count))
        if address == self.TEMEL_START and count == self.TEMEL_COUNT:
            return FakeResponse(self._temel_blok())
        if address == self.ALARM_START and count == self.ALARM_COUNT:
            return FakeResponse(self._alarm_blok())
        return FakeResponse(error=True)

    def read_input_registers(self, address, count, slave):
        # read_device artik input-register fallback'i kullanmiyor; cagrilirsa
        # test bunu yakalasin diye acikca hata donuyoruz.
        return FakeResponse(error=True)


@pytest.fixture(autouse=True)
def _sleep_yok(monkeypatch):
    """Testler gateway bekleme surelerini beklemesin."""
    monkeypatch.setattr(collector.time, "sleep", lambda *_a, **_k: None)


# ─────────────────────────────────────────────
# build_metric_candidates
# ─────────────────────────────────────────────

def test_build_metric_candidates_includes_block_fallbacks():
    candidates = collector.build_metric_candidates(73)

    assert ("holding", 73, 1, 0) in candidates
    assert ("input", 73, 1, 0) in candidates
    assert ("input", 70, 4, 3) in candidates


# ─────────────────────────────────────────────
# read_device
# ─────────────────────────────────────────────

def test_read_device_blok_okumadan_dogru_degerleri_cozer():
    client = FakeClient()

    data = collector.read_device(client, 1, CONFIG, max_retries=1)

    assert data is not None
    assert data["akim"] == pytest.approx(HAM_AKIM * CONFIG["akim_scale"])      # 0.08
    assert data["voltaj"] == pytest.approx(HAM_VOLT * CONFIG["volt_scale"])    # 782.8
    assert data["sicaklik"] == pytest.approx(HAM_ISI * CONFIG["isi_scale"])    # 3.14

    # Guc dogrudan register'dan gelir; voltaj * akim ile sentezlenmez.
    assert data["guc"] == pytest.approx(HAM_GUC * CONFIG["guc_scale"])         # 5.0
    assert data["guc"] != pytest.approx(data["voltaj"] * data["akim"])


def test_read_device_alarm_registerlarini_cozer():
    data = collector.read_device(FakeClient(), 1, CONFIG, max_retries=1)

    assert data is not None
    assert data["hata_kodu"] == 3          # 32-bit: (0 << 16) | 3
    assert data["hata_kodu_111"] == 5      # 16-bit tekil


def test_read_device_tek_blok_okuma_yapar():
    """Adres araligi tek blokta okunmali (cihaz basina sorgu sayisi onemli)."""
    client = FakeClient()

    collector.read_device(client, 1, CONFIG, max_retries=1)

    assert client.okunan_bloklar == [
        (FakeClient.TEMEL_START, FakeClient.TEMEL_COUNT),
        (FakeClient.ALARM_START, FakeClient.ALARM_COUNT),
    ]


def test_read_device_tamami_sifir_olcumu_atar():
    """Cihaz uykuda/cevapsizken sifir dolu blok veri olarak kaydedilmemeli."""

    class SifirClient(FakeClient):
        def _temel_blok(self):
            return [0] * self.TEMEL_COUNT

    assert collector.read_device(SifirClient(), 1, CONFIG, max_retries=1) is None


def test_read_device_okuma_hatasinda_none_doner():
    class HataliClient(FakeClient):
        def read_holding_registers(self, address, count, slave):
            return FakeResponse(error=True)

    assert collector.read_device(HataliClient(), 1, CONFIG, max_retries=2) is None
