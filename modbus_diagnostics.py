"""
Modbus baglanti tani yardimcilari.
"""

from contextlib import closing
from dataclasses import dataclass
import socket
from typing import Callable

from pymodbus.client import ModbusTcpClient
from pymodbus.framer import Framer

import utils
import veritabani
from config import config as env_config


DEFAULT_SCAN_ADDRESSES = (0, 1, 70, 71, 72, 73, 74, 76, 94, 107, 111)
COMMON_SLAVE_IDS = (1, 2, 3, 10, 16, 100, 247, 255)


def _unique(values):
    seen = set()
    ordered = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


@dataclass(frozen=True)
class RuntimeModbusConfig:
    target_ip: str
    target_port: int
    slave_ids: tuple[int, ...]
    refresh_rate: float
    guc_addr: int
    volt_addr: int
    akim_addr: int
    isi_addr: int
    source: str

    @property
    def configured_addresses(self) -> tuple[int, ...]:
        return _unique((self.guc_addr, self.volt_addr, self.akim_addr, self.isi_addr))


def _pick_setting(raw_settings, key, fallback):
    value = raw_settings.get(key)
    if value in (None, ""):
        return fallback, False
    return value, True


def load_runtime_config():
    """
    Collector ile ayni aktif ayarlari yukler.
    Veritabani doluysa onu, degilse .env varsayimlarini kullanir.
    """
    raw_settings = veritabani.tum_ayarlari_oku()
    db_hits = []

    target_ip, used_db = _pick_setting(raw_settings, "target_ip", env_config.MODBUS_IP)
    if used_db:
        db_hits.append("target_ip")

    target_port, used_db = _pick_setting(raw_settings, "target_port", env_config.MODBUS_PORT)
    if used_db:
        db_hits.append("target_port")

    refresh_rate, used_db = _pick_setting(raw_settings, "refresh_rate", env_config.REFRESH_RATE)
    if used_db:
        db_hits.append("refresh_rate")

    slave_ids_raw, used_db = _pick_setting(raw_settings, "slave_ids", env_config.SLAVE_IDS)
    if used_db:
        db_hits.append("slave_ids")

    guc_addr, used_db = _pick_setting(raw_settings, "guc_addr", env_config.GUC_ADDR)
    if used_db:
        db_hits.append("guc_addr")

    volt_addr, used_db = _pick_setting(raw_settings, "volt_addr", env_config.VOLT_ADDR)
    if used_db:
        db_hits.append("volt_addr")

    akim_addr, used_db = _pick_setting(raw_settings, "akim_addr", env_config.AKIM_ADDR)
    if used_db:
        db_hits.append("akim_addr")

    isi_addr, used_db = _pick_setting(raw_settings, "isi_addr", env_config.ISI_ADDR)
    if used_db:
        db_hits.append("isi_addr")

    slave_ids, _ = utils.parse_id_list(str(slave_ids_raw))
    if not slave_ids:
        fallback_ids, _ = utils.parse_id_list(env_config.SLAVE_IDS)
        slave_ids = fallback_ids or [1]

    if not db_hits:
        source = "env"
    elif len(db_hits) == 8:
        source = "database"
    else:
        source = "database+env"

    return RuntimeModbusConfig(
        target_ip=str(target_ip),
        target_port=int(target_port),
        slave_ids=tuple(slave_ids),
        refresh_rate=float(refresh_rate),
        guc_addr=int(guc_addr),
        volt_addr=int(volt_addr),
        akim_addr=int(akim_addr),
        isi_addr=int(isi_addr),
        source=source,
    )


def tcp_port_open(ip, port, timeout=2.0):
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((ip, int(port))) == 0
    except OSError:
        return False


def build_probe_requests(runtime_config, exhaustive=False):
    requests = []

    for address in runtime_config.configured_addresses:
        requests.append(("holding", address, 1))

    if runtime_config.configured_addresses:
        block_starts = _unique((runtime_config.guc_addr, min(runtime_config.configured_addresses)))
    else:
        block_starts = (runtime_config.guc_addr,)

    for start_addr in block_starts:
        requests.append(("holding", start_addr, 4))

    if exhaustive:
        scan_addresses = _unique(runtime_config.configured_addresses + DEFAULT_SCAN_ADDRESSES)
        for function_name in ("holding", "input"):
            for address in scan_addresses:
                requests.append((function_name, address, 1))
            for start_addr in block_starts:
                requests.append((function_name, start_addr, 4))
            requests.append((function_name, 107, 2))
            requests.append((function_name, 111, 1))

    return _unique(requests)


def build_slave_scan_list(runtime_config, exhaustive=False):
    if exhaustive and runtime_config.slave_ids:
        return runtime_config.slave_ids
    if exhaustive:
        return COMMON_SLAVE_IDS
    return runtime_config.slave_ids


def probe_target(
    runtime_config,
    exhaustive=False,
    timeout=1.0,
    framers=None,
    client_factory: Callable[..., ModbusTcpClient] = ModbusTcpClient,
    max_errors=25,
):
    if framers is None:
        framers = (Framer.SOCKET, Framer.RTU) if exhaustive else (Framer.SOCKET,)

    result = {
        "tcp_open": tcp_port_open(runtime_config.target_ip, runtime_config.target_port, timeout=timeout),
        "attempts": 0,
        "successes": [],
        "errors": [],
    }

    if not result["tcp_open"]:
        return result

    requests = build_probe_requests(runtime_config, exhaustive=exhaustive)
    slave_ids = build_slave_scan_list(runtime_config, exhaustive=exhaustive)

    for framer in framers:
        client = client_factory(
            runtime_config.target_ip,
            port=runtime_config.target_port,
            timeout=timeout,
            framer=framer,
        )
        try:
            connected = client.connect()
        except Exception as exc:
            connected = False
            if len(result["errors"]) < max_errors:
                result["errors"].append(f"{framer.value}: connect exception: {exc}")

        if not connected:
            if len(result["errors"]) < max_errors:
                result["errors"].append(f"{framer.value}: connect failed")
            continue

        for slave_id in slave_ids:
            for function_name, address, count in requests:
                method_name = "read_holding_registers" if function_name == "holding" else "read_input_registers"
                method = getattr(client, method_name)
                result["attempts"] += 1

                try:
                    response = method(address=address, count=count, slave=slave_id)
                except Exception as exc:
                    if len(result["errors"]) < max_errors:
                        result["errors"].append(
                            f"{framer.value}/{function_name} slave={slave_id} addr={address} count={count}: {exc}"
                        )
                    continue

                if response.isError():
                    if len(result["errors"]) < max_errors:
                        result["errors"].append(
                            f"{framer.value}/{function_name} slave={slave_id} addr={address} count={count}: {response}"
                        )
                    continue

                result["successes"].append(
                    {
                        "framer": framer.value,
                        "function": function_name,
                        "slave_id": slave_id,
                        "address": address,
                        "count": count,
                        "values": tuple(getattr(response, "registers", ()) or ()),
                    }
                )
                if not exhaustive:
                    client.close()
                    return result
        client.close()

    return result
