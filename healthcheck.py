#!/usr/bin/env python3
"""
Solar Monitor - Healthcheck Betiği
====================================
Docker ortamı veya izleme sistemleri için uygulamanın, veritabanının ve
veri akışının sağlıklı çalışıp çalışmadığını test eder.

İki modda çalışır:
    python healthcheck.py            → Tek seferlik kontrol, exit code döner
                                       (Docker HEALTHCHECK için)
    python healthcheck.py --serve    → HEALTH_PORT üzerinde HTTP endpoint
                                       (/health JSON döner)

En kritik kontrol veri tazeliğidir: collector ayakta görünüp veri yazmıyorsa
sessizce veri kaybederiz. Son ölçüm beklenenden eskiyse unhealthy döneriz ve
Docker restart politikası collector'ı toparlar.
"""

import json
import os
import sys

import veritabani

# Son ölçüm, beklenen periyodun bu katından eskiyse veri akışı durmuş sayılır.
TAZELIK_TOLERANS_KATI = 3.0
# Tolerans hiçbir zaman bu değerin altına inmesin (kısa refresh_rate'lerde
# tek bir gecikmiş döngü yüzünden alarm üretmemek için).
MIN_TOLERANS_SN = 180.0


def test_database() -> tuple[bool, str]:
    """Veritabanı erişimini ve tablo yapısını doğrular."""
    conn = veritabani.get_db_connection()
    if not conn:
        return False, "Veritabani baglantisi kurulamadi"
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM ayarlar LIMIT 1")
        return True, "Veritabani erisilebilir"
    except Exception as e:
        return False, f"Veritabani sorgu hatasi: {e}"
    finally:
        conn.close()


def test_veri_tazeligi() -> tuple[bool, str]:
    """Collector'ın hâlâ veri yazdığını doğrular.

    Her fabrika için son ölçümün yaşını, o fabrikanın refresh_rate ayarına
    göre beklenen süreyle karşılaştırır.

    Yaş, SQL'deki NOW() yerine Python tarafında hesaplanır: zaman kolonu
    timezone taşımıyor ve collector yerel saat yazıyor, dolayısıyla doğru
    karşılaştırma collector ile aynı saat kaynağını kullanmakla yapılır.
    """
    from datetime import datetime

    from veritabani import FABRIKALAR

    conn = veritabani.get_db_connection()
    if not conn:
        return False, "Veri tazeligi kontrol edilemedi (DB baglantisi yok)"

    try:
        cursor = conn.cursor()
        sorunlar = []
        detaylar = []

        for fab_id in FABRIKALAR:
            cursor.execute("SELECT MAX(zaman) FROM olcumler WHERE fabrika_id = %s", (fab_id,))
            row = cursor.fetchone()
            son_zaman = row[0] if row else None

            if son_zaman is None:
                sorunlar.append(f"{fab_id}: hic veri yok")
                continue

            yas = (datetime.now() - son_zaman).total_seconds()
            try:
                refresh = float(veritabani.ayar_oku("refresh_rate", "60", fab_id))
            except (TypeError, ValueError):
                refresh = 60.0

            tolerans = max(MIN_TOLERANS_SN, refresh * TAZELIK_TOLERANS_KATI)
            detaylar.append(f"{fab_id}: son veri {int(yas)}s once (limit {int(tolerans)}s)")

            if yas > tolerans:
                sorunlar.append(
                    f"{fab_id}: son veri {int(yas)}s once — {int(tolerans)}s limitini asti"
                )

        if sorunlar:
            return False, "; ".join(sorunlar)
        return True, "; ".join(detaylar) if detaylar else "Fabrika tanimli degil"
    except Exception as e:
        return False, f"Veri tazeligi kontrol hatasi: {e}"
    finally:
        conn.close()


def durum_topla() -> dict:
    """Tüm kontrolleri koşturup yapılandırılmış sonuç döner."""
    db_ok, db_msg = test_database()

    # DB erişilemiyorsa veri tazeliğini kontrol etmenin anlamı yok.
    if db_ok:
        veri_ok, veri_msg = test_veri_tazeligi()
    else:
        veri_ok, veri_msg = False, "DB erisilemedigi icin kontrol edilmedi"

    return {
        "status": "healthy" if (db_ok and veri_ok) else "unhealthy",
        "checks": {
            "database": {"ok": db_ok, "detail": db_msg},
            "veri_tazeligi": {"ok": veri_ok, "detail": veri_msg},
        },
    }


def run_healthcheck() -> None:
    """Tek seferlik kontrol — Docker HEALTHCHECK için exit code döner."""
    sonuc = durum_topla()

    for ad, kontrol in sonuc["checks"].items():
        isaret = "OK" if kontrol["ok"] else "FAIL"
        print(f"[{isaret}] {ad}: {kontrol['detail']}")

    if sonuc["status"] != "healthy":
        print("HEALTHCHECK FAILED")
        sys.exit(1)

    print("HEALTHCHECK PASSED")
    sys.exit(0)


def serve() -> None:
    """HTTP sağlık endpoint'i — HEALTH_PORT üzerinde /health JSON döner.

    Tek seferlik betik olarak restart döngüsüne girmemek için servis modunda
    kalıcı bir HTTP sunucusu çalıştırır.
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer

    port = int(os.getenv("HEALTH_PORT", 8502))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            sonuc = durum_topla()
            kod = 200 if sonuc["status"] == "healthy" else 503
            govde = json.dumps(sonuc, ensure_ascii=False).encode("utf-8")
            self.send_response(kod)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)

        def log_message(self, format, *args):
            # Her istek için erişim logu basmayalım; Docker loglarını kirletiyor.
            pass

    print(f"[*] Healthcheck endpoint http://0.0.0.0:{port}/health adresinde baslatildi")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    if "--serve" in sys.argv:
        serve()
    else:
        run_healthcheck()
