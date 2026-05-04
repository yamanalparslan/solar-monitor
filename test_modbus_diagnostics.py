from types import SimpleNamespace
from unittest.mock import patch

import modbus_diagnostics as md


def test_load_runtime_config_prefers_database_values():
    fake_env = SimpleNamespace(
        MODBUS_IP="127.0.0.1",
        MODBUS_PORT=5020,
        SLAVE_IDS="1,2,3",
        REFRESH_RATE=2.0,
        GUC_ADDR=70,
        VOLT_ADDR=71,
        AKIM_ADDR=72,
        ISI_ADDR=74,
    )
    fake_db = {
        "target_ip": "10.0.0.25",
        "target_port": "1502",
        "slave_ids": "7,8",
        "refresh_rate": "60",
        "guc_addr": "76",
        "volt_addr": "73",
        "akim_addr": "70",
        "isi_addr": "94",
    }

    with patch.object(md, "env_config", fake_env), patch.object(md.veritabani, "tum_ayarlari_oku", return_value=fake_db):
        runtime_config = md.load_runtime_config()

    assert runtime_config.source == "database"
    assert runtime_config.target_ip == "10.0.0.25"
    assert runtime_config.target_port == 1502
    assert runtime_config.slave_ids == (7, 8)
    assert runtime_config.refresh_rate == 60.0
    assert runtime_config.configured_addresses == (76, 73, 70, 94)


def test_build_probe_requests_adds_exhaustive_input_checks():
    runtime_config = md.RuntimeModbusConfig(
        target_ip="10.35.14.10",
        target_port=502,
        slave_ids=(1,),
        refresh_rate=60.0,
        guc_addr=76,
        volt_addr=73,
        akim_addr=70,
        isi_addr=94,
        source="database",
    )

    requests = md.build_probe_requests(runtime_config, exhaustive=True)

    assert ("holding", 76, 1) in requests
    assert ("holding", 76, 4) in requests
    assert ("input", 76, 1) in requests
    assert ("holding", 107, 2) in requests
    assert ("input", 111, 1) in requests


def test_probe_target_returns_first_success_from_mock_client():
    runtime_config = md.RuntimeModbusConfig(
        target_ip="10.35.14.10",
        target_port=502,
        slave_ids=(1,),
        refresh_rate=60.0,
        guc_addr=70,
        volt_addr=71,
        akim_addr=72,
        isi_addr=74,
        source="database",
    )

    class FakeResponse:
        def __init__(self, registers=None, error=False):
            self.registers = registers or []
            self._error = error

        def isError(self):
            return self._error

        def __str__(self):
            return "fake-error" if self._error else "fake-ok"

    class FakeClient:
        def __init__(self, host, port=502, timeout=1.0, framer=None):
            self.closed = False

        def connect(self):
            return True

        def read_holding_registers(self, address, count, slave):
            if address == 70 and count == 1 and slave == 1:
                return FakeResponse([1234])
            return FakeResponse(error=True)

        def read_input_registers(self, address, count, slave):
            return FakeResponse(error=True)

        def close(self):
            self.closed = True

    with patch.object(md, "tcp_port_open", return_value=True):
        probe_result = md.probe_target(
            runtime_config,
            exhaustive=False,
            client_factory=FakeClient,
        )

    assert probe_result["tcp_open"] is True
    assert probe_result["attempts"] == 1
    assert probe_result["successes"][0]["values"] == (1234,)
