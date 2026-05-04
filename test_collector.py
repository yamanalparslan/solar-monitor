import collector


class FakeResponse:
    def __init__(self, registers=None, error=False):
        self.registers = registers or []
        self._error = error

    def isError(self):
        return self._error

    def __str__(self):
        return "fake-error" if self._error else "fake-ok"


class FakeClient:
    def __init__(self):
        self.connected = True

    def connect(self):
        self.connected = True
        return True

    def close(self):
        self.connected = False

    def read_holding_registers(self, address, count, slave):
        if address == 76 and count == 1:
            return FakeResponse([0])
        if address == 107 and count == 2:
            return FakeResponse([0, 0])
        if address == 111 and count == 1:
            return FakeResponse([0])
        return FakeResponse(error=True)

    def read_input_registers(self, address, count, slave):
        if address == 70 and count == 4:
            return FakeResponse([8, 8, 7866, 7828])
        if address == 94 and count == 1:
            return FakeResponse([314])
        return FakeResponse(error=True)


def test_build_metric_candidates_includes_block_fallbacks():
    candidates = collector.build_metric_candidates(73)

    assert ("holding", 73, 1, 0) in candidates
    assert ("input", 73, 1, 0) in candidates
    assert ("input", 70, 4, 3) in candidates


def test_read_device_uses_input_block_fallback_and_computes_power(monkeypatch):
    monkeypatch.setattr(collector.time, "sleep", lambda *_args, **_kwargs: None)

    config = {
        "guc_addr": 76,
        "volt_addr": 73,
        "akim_addr": 70,
        "isi_addr": 94,
        "guc_scale": 0.01,
        "volt_scale": 0.1,
        "akim_scale": 0.01,
        "isi_scale": 0.01,
        "alarm_registers": [
            {"addr": 107, "key": "hata_kodu", "count": 2},
            {"addr": 111, "key": "hata_kodu_111", "count": 1},
        ],
    }

    data = collector.read_device(FakeClient(), 1, config, max_retries=1)

    assert data is not None
    assert data["voltaj"] == 782.8000000000001
    assert data["akim"] == 0.08
    assert data["sicaklik"] == 3.14
    assert data["guc"] == round(data["voltaj"] * data["akim"], 2)


def test_read_device_discards_all_zero_samples(monkeypatch):
    monkeypatch.setattr(collector.time, "sleep", lambda *_args, **_kwargs: None)

    class AllZeroClient(FakeClient):
        def read_holding_registers(self, address, count, slave):
            if count == 1:
                return FakeResponse([0])
            if address == 107 and count == 2:
                return FakeResponse([0, 0])
            if address == 111 and count == 1:
                return FakeResponse([0])
            return FakeResponse([0, 0, 0, 0])

        def read_input_registers(self, address, count, slave):
            if count == 1:
                return FakeResponse([0])
            return FakeResponse([0, 0, 0, 0])

    config = {
        "guc_addr": 76,
        "volt_addr": 73,
        "akim_addr": 70,
        "isi_addr": 94,
        "guc_scale": 0.01,
        "volt_scale": 0.1,
        "akim_scale": 0.01,
        "isi_scale": 0.01,
        "alarm_registers": [
            {"addr": 107, "key": "hata_kodu", "count": 2},
            {"addr": 111, "key": "hata_kodu_111", "count": 1},
        ],
    }

    assert collector.read_device(AllZeroClient(), 1, config, max_retries=1) is None
