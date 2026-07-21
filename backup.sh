#!/bin/sh
# ===================================================
# Solar Monitor — Otomatik Veritabani Yedekleme
# ===================================================
# solar-backup servisi tarafindan calistirilir. Gunde bir kez pg_dump
# ile TimescaleDB'nin tam (custom-format) yedegini alir ve eski yedekleri
# rotasyonla siler.
#
# Geri yukleme (TimescaleDB resmi proseduru):
#   createdb -U solar_user yeni_db
#   psql -U solar_user -d yeni_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
#   psql -U solar_user -d yeni_db -c "SELECT timescaledb_pre_restore();"
#   pg_restore -U solar_user -d yeni_db /backups/solar_YYYY-MM-DD.dump
#   psql -U solar_user -d yeni_db -c "SELECT timescaledb_post_restore();"
# ===================================================

set -eu

PGHOST="${POSTGRES_HOST:-solar-postgres}"
PGUSER="${POSTGRES_USER:-solar_user}"
PGDB="${POSTGRES_DB:-solar_db}"
export PGPASSWORD="${POSTGRES_PASSWORD:-solar_pass_2026}"

BACKUP_DIR="/backups"
# Kac gunluk yedek saklansin (rotasyon)
RETENTION="${BACKUP_RETENTION_DAYS:-14}"
# Gunluk yedek saati (24s formati, HH:MM)
BACKUP_TIME="${BACKUP_TIME:-02:30}"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [backup] $1"
}

yedek_al() {
    ts="$(date +%F)"
    hedef="${BACKUP_DIR}/solar_${ts}.dump"
    gecici="${hedef}.tmp"

    log "Yedek aliniyor: ${hedef}"
    # Once .tmp'e yaz, basarili olursa tasi — yarim yedek dosyasi olusmasin.
    if pg_dump -h "$PGHOST" -U "$PGUSER" -d "$PGDB" -Fc -f "$gecici"; then
        mv "$gecici" "$hedef"
        boyut="$(du -h "$hedef" | cut -f1)"
        log "Yedek tamamlandi (${boyut}): ${hedef}"
    else
        log "HATA: pg_dump basarisiz oldu, yarim dosya siliniyor."
        rm -f "$gecici"
        return 1
    fi

    # Rotasyon: RETENTION gununden eski yedekleri sil
    silinen="$(find "$BACKUP_DIR" -name 'solar_*.dump' -type f -mtime "+${RETENTION}" -print -delete | wc -l)"
    if [ "$silinen" -gt 0 ]; then
        log "Rotasyon: ${silinen} eski yedek silindi (>${RETENTION} gun)."
    fi
}

log "Yedekleme servisi basladi. Gunluk saat: ${BACKUP_TIME}, saklama: ${RETENTION} gun."

# Konteyner ilk ayaga kalkarken bir yedek al (mevcut veriyi hemen guvenceye al).
if pg_isready -h "$PGHOST" -U "$PGUSER" -d "$PGDB" >/dev/null 2>&1; then
    yedek_al || log "Baslangic yedegi alinamadi, zamanlanmis dongu devam edecek."
fi

# Her dakika saati kontrol et; hedef saate gelince gunluk yedegi al.
son_yedek_gunu=""
while true; do
    simdi="$(date +%H:%M)"
    bugun="$(date +%F)"
    if [ "$simdi" = "$BACKUP_TIME" ] && [ "$bugun" != "$son_yedek_gunu" ]; then
        yedek_al || log "Gunluk yedek alinamadi."
        son_yedek_gunu="$bugun"
    fi
    sleep 30
done
