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

Tasarım kararı — iki durum birbirinden ayrılır:

  1. "Collector öldü / DB'ye yazamıyor"  → unhealthy (exit 1, HTTP 503).
  2. "Cihazlar cevap vermiyor" → degraded (exit 0, HTTP 200, gövdede
     `degraded: true`). Sahada okumaların büyük bölümü başarısız oluyor
     (24 saatte 1611 [CEVAP YOK], cihaz başına 39 dakikaya varan boşluklar);
     bu collector'ın arızası değil, hattın/cihazın durumu.

Eski ölçüt "son ölçüm ne kadar eski" idi ve bu ikisini ayırt edemiyordu:
ölçüm akışı meşru sekilde kesintili olduğu için collector sapasağlam
çalışırken de unhealthy görünebiliyordu. Canlılık ölçütü artık
`collector_heartbeat` tablosu — collector cihazlardan cevap alamasa bile
her döngüde oraya kalp atışı yazar.

NOT: `unhealthy` durumu tek başına konteyneri yeniden başlatmaz. Docker'ın
restart politikası konteynerin *çıkışına* tepki verir, sağlık durumuna değil
(unhealthy'de restart yalnızca Swarm/Kubernetes davranışıdır). Buradaki exit
kodunun işlevi durumu doğru raporlamak ve izleme tarafına sinyal vermektir.
"""

import json
import os
import sys

import veritabani

# Kalp atışı, beklenen periyodun bu katından eskiyse collector durmuş sayılır.
TAZELIK_TOLERANS_KATI = 3.0
# Tolerans hiçbir zaman bu değerin altına inmesin (kısa refresh_rate'lerde
# tek bir gecikmiş döngü yüzünden alarm üretmemek için).
MIN_TOLERANS_SN = 180.0
# Kalp atışı hiç yoksa (ilk kurulum, collector henüz ilk döngüsünü bitirmedi)
# bu süre boyunca hoşgörü gösterilir. Docker start_period bunu zaten kapsıyor.
ILK_KALP_ATISI_TOLERANS_SN = 300.0


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


def test_collector_canli() -> tuple[bool, str]:
    """Collector'ın döngüsünü hâlâ çevirdiğini doğrular.

    Ölçüm tazeliği yerine `collector_heartbeat` tablosuna bakılır: cihazlar
    cevap vermese bile collector her döngüde oraya yazar. Böylece cihaz
    sessizliği collector arızası gibi raporlanmaz.

    Yaş, SQL'deki NOW() yerine Python tarafında hesaplanır: zaman kolonu
    timezone taşımıyor ve collector yerel saat yazıyor, dolayısıyla doğru
    karşılaştırma collector ile aynı saat kaynağını kullanmakla yapılır.
    """
    from datetime import datetime

    from veritabani import FABRIKALAR

    kayitlar = veritabani.heartbeat_getir()
    if kayitlar is None:
        return False, "Kalp atisi okunamadi (DB hatasi)"

    if not kayitlar:
        # Henüz hiç döngü tamamlanmadı. Docker start_period bunu kapsar;
        # kalıcı olarak unhealthy'e düşmemek için hoşgörülü davranıyoruz.
        return True, (
            "Kalp atisi henuz yok — collector ilk dongusunu tamamlamamis olabilir "
            f"({int(ILK_KALP_ATISI_TOLERANS_SN)}s hosgoru)"
        )

    sorunlar = []
    detaylar = []

    for fab_id in FABRIKALAR:
        kayit = kayitlar.get(fab_id)
        if not kayit or kayit.get("son_dongu") is None:
            detaylar.append(f"{fab_id}: kalp atisi yok (fabrika devrede olmayabilir)")
            continue

        yas = (datetime.now() - kayit["son_dongu"]).total_seconds()
        beklenen = float(kayit.get("beklenen_periyot_sn") or 60.0)
        tolerans = max(MIN_TOLERANS_SN, beklenen * TAZELIK_TOLERANS_KATI)

        detaylar.append(
            f"{fab_id}: son dongu {int(yas)}s once "
            f"(limit {int(tolerans)}s, {kayit.get('okunan_cihaz', 0)} okundu / "
            f"{kayit.get('cevapsiz_cihaz', 0)} cevapsiz)"
        )

        if yas > tolerans:
            sorunlar.append(
                f"{fab_id}: collector {int(yas)}s dongu cevirmedi — {int(tolerans)}s limitini asti"
            )

    if sorunlar:
        return False, "; ".join(sorunlar)
    if not detaylar:
        return True, "Fabrika tanimli degil"
    return True, "; ".join(detaylar)


def test_veri_akisi() -> tuple[bool, str]:
    """Cihazlardan veri gelip gelmediğini raporlar — bilgilendirme amaçlı.

    Bu kontrol `unhealthy` üretmez: cihaz sessizliği collector'ın arızası
    değil, hattın/cihazın durumudur ve collector'a müdahale ile düzelmez.
    Sonuç `degraded` bayrağı olarak gövdeye yazılır; alarm/bildirim tarafının
    ve `cihaz_durum_log` üzerinden çalışabilirlik raporunun işi.
    """
    kayitlar = veritabani.heartbeat_getir()
    if not kayitlar:
        return True, "Kalp atisi yok — veri akisi degerlendirilemedi"

    cevapsizlar = veritabani.cevapsiz_cihazlari_getir()
    toplam_okunan = sum(int(k.get("okunan_cihaz") or 0) for k in kayitlar.values())

    if toplam_okunan == 0:
        detay = "Hicbir cihazdan veri alinamiyor"
        if cevapsizlar:
            liste = ", ".join(f"{c['fabrika_id']}/{c['slave_id']}" for c in cevapsizlar[:10])
            detay += f" (cevapsiz: {liste})"
        return False, detay

    if cevapsizlar:
        liste = ", ".join(f"{c['fabrika_id']}/{c['slave_id']}" for c in cevapsizlar[:10])
        return False, f"{toplam_okunan} cihaz okunuyor, cevapsiz: {liste}"

    return True, f"{toplam_okunan} cihazdan veri aliniyor"


def durum_topla() -> dict:
    """Tüm kontrolleri koşturup yapılandırılmış sonuç döner.

    `status` yalnızca sistemin kendi arızalarında "unhealthy" olur (DB
    erişilemez ya da collector döngü çevirmiyor). Cihaz sessizliği `degraded`
    bayrağıyla bildirilir ama sağlık durumunu bozmaz — aksi halde meşru
    kesintiler sürekli yanlış alarm üretir ve gerçek arıza gözden kaçar.
    """
    db_ok, db_msg = test_database()

    if db_ok:
        collector_ok, collector_msg = test_collector_canli()
        akis_ok, akis_msg = test_veri_akisi()
    else:
        collector_ok, collector_msg = False, "DB erisilemedigi icin kontrol edilmedi"
        akis_ok, akis_msg = False, "DB erisilemedigi icin kontrol edilmedi"

    saglikli = db_ok and collector_ok

    return {
        "status": "healthy" if saglikli else "unhealthy",
        # Sistem ayakta ama cihazlardan veri gelmiyor: izleme icin gorunur,
        # Docker restart'i icin tetikleyici degil.
        "degraded": saglikli and not akis_ok,
        "checks": {
            "database": {"ok": db_ok, "detail": db_msg},
            "collector_canli": {"ok": collector_ok, "detail": collector_msg},
            "veri_akisi": {"ok": akis_ok, "detail": akis_msg, "kritik": False},
        },
    }


def run_healthcheck() -> None:
    """Tek seferlik kontrol — Docker HEALTHCHECK için exit code döner."""
    sonuc = durum_topla()

    for ad, kontrol in sonuc["checks"].items():
        if kontrol["ok"]:
            isaret = "OK"
        # Kritik olmayan kontroller (cihaz sessizligi) saglik durumunu bozmaz;
        # loglarda FAIL yerine WARN gorunsun ki gercek ariza gozden kacmasin.
        elif kontrol.get("kritik", True):
            isaret = "FAIL"
        else:
            isaret = "WARN"
        print(f"[{isaret}] {ad}: {kontrol['detail']}")

    if sonuc["status"] != "healthy":
        print("HEALTHCHECK FAILED")
        sys.exit(1)

    if sonuc.get("degraded"):
        # Cihazlar sessiz ama sistem ayakta: yeniden baslatmak bunu cozmez.
        print("HEALTHCHECK PASSED (DEGRADED — cihazlardan veri gelmiyor)")
        sys.exit(0)

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
