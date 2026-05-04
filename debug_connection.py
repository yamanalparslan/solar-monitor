"""
Solar Monitor - Baglanti tanilama araci.
Collector ile ayni aktif ayarlari kullanir.
"""

from modbus_diagnostics import load_runtime_config, probe_target

def run_diagnostic():
    print("=" * 50)
    print("MODBUS BAGLANTI TESHIS ARACI")
    print("=" * 50)
    runtime_config = load_runtime_config()
    print(f"Aktif Kaynak: {runtime_config.source}")
    print(f"Hedef IP    : {runtime_config.target_ip}")
    print(f"Hedef Port  : {runtime_config.target_port}")
    print(f"Slave ID'ler: {list(runtime_config.slave_ids)}")
    print(
        "Adresler    : "
        f"G={runtime_config.guc_addr} "
        f"V={runtime_config.volt_addr} "
        f"A={runtime_config.akim_addr} "
        f"T={runtime_config.isi_addr}"
    )
    print("-" * 50)

    probe_result = probe_target(runtime_config, exhaustive=True, timeout=0.7)

    if not probe_result["tcp_open"]:
        print("[!] KRITIK: TCP portu kapali veya IP yanlis.")
        print("\n" + "=" * 50)
        print("TESHIS TAMAMLANDI")
        return

    print("[+] TCP baglantisi basarili.")

    if probe_result["successes"]:
        print("[+] Modbus uygulama cevabi alindi.")
        for hit in probe_result["successes"][:10]:
            print(
                f"   [+] framer={hit['framer']} func={hit['function']} "
                f"slave={hit['slave_id']} addr={hit['address']} "
                f"count={hit['count']} values={list(hit['values'])}"
            )
    else:
        print("[!] TCP acik ama hicbir Modbus istegi cevap vermedi.")
        for error in probe_result["errors"][:8]:
            print(f"   [-] {error}")

    print("\n" + "=" * 50)
    print("TESHIS TAMAMLANDI")

if __name__ == "__main__":
    run_diagnostic()
