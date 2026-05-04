"""
Gercek Modbus uygulama cevabini tarayan CLI arac.
"""

import sys

from modbus_diagnostics import load_runtime_config, probe_target


def main():
    runtime_config = load_runtime_config()

    print("=" * 60)
    print("MODBUS PROBE")
    print("=" * 60)
    print(f"Aktif ayar kaynagi : {runtime_config.source}")
    print(f"Hedef              : {runtime_config.target_ip}:{runtime_config.target_port}")
    print(f"Slave ID listesi   : {list(runtime_config.slave_ids)}")
    print(
        "Adresler           : "
        f"G={runtime_config.guc_addr} "
        f"V={runtime_config.volt_addr} "
        f"A={runtime_config.akim_addr} "
        f"T={runtime_config.isi_addr}"
    )
    print(f"Refresh            : {runtime_config.refresh_rate}s")
    print("-" * 60)

    probe_result = probe_target(runtime_config, exhaustive=True, timeout=0.7)

    if not probe_result["tcp_open"]:
        print("[HATA] TCP portu acilmadi.")
        return 1

    if probe_result["successes"]:
        print("[OK] Modbus cevabi alindi.")
        for hit in probe_result["successes"][:10]:
            print(
                f"  - framer={hit['framer']} func={hit['function']} "
                f"slave={hit['slave_id']} addr={hit['address']} "
                f"count={hit['count']} values={list(hit['values'])}"
            )
        if len(probe_result["successes"]) > 10:
            print(f"  ... toplam {len(probe_result['successes'])} basarili okuma")
        return 0

    print("[HATA] TCP acik ama hicbir Modbus istegi cevap vermedi.")
    print("Olasiliklar:")
    print("  - Yanlis slave ID")
    print("  - Yanlis register/function code")
    print("  - Cihaz Modbus yerine baska bir protokol dinliyor")
    print("  - Gateway baglanti aciyor ama arka cihaz cevap vermiyor")

    if probe_result["errors"]:
        print("-" * 60)
        print("Ilk hata ornekleri:")
        for error in probe_result["errors"][:8]:
            print(f"  - {error}")

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
