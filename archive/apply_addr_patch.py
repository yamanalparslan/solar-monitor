"""
Solar Monitor - Adres Guncelleme Yamasi
========================================
veritabani.py, config.py ve .env.example icindeki
register adres varsayilanlarini gunceller.

Calistirma (proje kok klasoründen):
    python apply_addr_patch.py
"""

import os
import re

PROJE_KOK = os.path.dirname(os.path.abspath(__file__))

ADRESLER = {
    "guc_addr":  93,
    "volt_addr": 29,
    "akim_addr": 26,
    "isi_addr":  44,
}

# ─── veritabani.py ───────────────────────────────────────────────────────────

def patch_veritabani():
    yol = os.path.join(PROJE_KOK, "veritabani.py")
    with open(yol, encoding="utf-8") as f:
        icerik = f.read()

    degisiklikler = {
        "('guc_addr',  '70',": "('guc_addr',  '93',",
        "('guc_addr', '70',":  "('guc_addr', '93',",
        "('volt_addr', '71',": "('volt_addr', '29',",
        "('akim_addr', '72',": "('akim_addr', '26',",
        "('isi_addr',  '74',": "('isi_addr',  '44',",
        "('isi_addr', '74',":  "('isi_addr', '44',",
    }

    for eski, yeni in degisiklikler.items():
        icerik = icerik.replace(eski, yeni)

    # fallback sozlukler (tum_ayarlari_oku except blogu)
    icerik = icerik.replace("'guc_addr': '70'",  "'guc_addr': '93'")
    icerik = icerik.replace("'volt_addr': '71'", "'volt_addr': '29'")
    icerik = icerik.replace("'akim_addr': '72'", "'akim_addr': '26'")
    icerik = icerik.replace("'isi_addr': '74'",  "'isi_addr': '44'")

    with open(yol, "w", encoding="utf-8") as f:
        f.write(icerik)
    print(f"[OK] veritabani.py guncellendi")


# ─── config.py ───────────────────────────────────────────────────────────────

def patch_config():
    yol = os.path.join(PROJE_KOK, "config.py")
    with open(yol, encoding="utf-8") as f:
        icerik = f.read()

    # Config dataclass default'lari
    icerik = re.sub(r'(GUC_ADDR.*?default_factory.*?\()(\d+)(\))',
                    lambda m: m.group(1) + "93" + m.group(3), icerik)
    icerik = re.sub(r'(VOLT_ADDR.*?default_factory.*?\()(\d+)(\))',
                    lambda m: m.group(1) + "29" + m.group(3), icerik)
    icerik = re.sub(r'(AKIM_ADDR.*?default_factory.*?\()(\d+)(\))',
                    lambda m: m.group(1) + "26" + m.group(3), icerik)
    icerik = re.sub(r'(ISI_ADDR.*?default_factory.*?\()(\d+)(\))',
                    lambda m: m.group(1) + "44" + m.group(3), icerik)

    with open(yol, "w", encoding="utf-8") as f:
        f.write(icerik)
    print(f"[OK] config.py guncellendi")


# ─── .env.example ────────────────────────────────────────────────────────────

def patch_env_example():
    yol = os.path.join(PROJE_KOK, ".env.example")
    with open(yol, encoding="utf-8") as f:
        icerik = f.read()

    icerik = re.sub(r'^GUC_ADDR=\d+',  'GUC_ADDR=93',  icerik, flags=re.MULTILINE)
    icerik = re.sub(r'^VOLT_ADDR=\d+', 'VOLT_ADDR=29', icerik, flags=re.MULTILINE)
    icerik = re.sub(r'^AKIM_ADDR=\d+', 'AKIM_ADDR=26', icerik, flags=re.MULTILINE)
    icerik = re.sub(r'^ISI_ADDR=\d+',  'ISI_ADDR=44',  icerik, flags=re.MULTILINE)

    with open(yol, "w", encoding="utf-8") as f:
        f.write(icerik)
    print(f"[OK] .env.example guncellendi")


# ─── Veritabani Canli Guncelleme ─────────────────────────────────────────────

def guncelle_veritabani_canli():
    """
    Calisan bir sistemde mevcut DB'deki ayarlari gunceller.
    (Yeni kurulum icin gerek yok, init_db() zaten dogru degerleri yazar.)
    """
    try:
        import veritabani as vt
        from veritabani import FABRIKALAR

        for fab_id in FABRIKALAR:
            vt.ayar_yaz("guc_addr",  93, fab_id)
            vt.ayar_yaz("volt_addr", 29, fab_id)
            vt.ayar_yaz("akim_addr", 26, fab_id)
            vt.ayar_yaz("isi_addr",  44, fab_id)
            print(f"[OK] DB guncellendi: {fab_id}")
    except Exception as e:
        print(f"[WARN] DB canli guncelleme atlamalı (yeni kurulumda normal): {e}")


if __name__ == "__main__":
    patch_veritabani()
    patch_config()
    patch_env_example()
    guncelle_veritabani_canli()
    print()
    print("Adres guncellemesi tamamlandi:")
    print(f"  GUC_ADDR  = {ADRESLER['guc_addr']}")
    print(f"  VOLT_ADDR = {ADRESLER['volt_addr']}")
    print(f"  AKIM_ADDR = {ADRESLER['akim_addr']}")
    print(f"  ISI_ADDR  = {ADRESLER['isi_addr']}")
    print()
    print("Sonraki adim:")
    print("  docker compose down && docker compose up -d --build")