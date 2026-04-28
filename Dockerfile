# ===== Stage 1: Builder =====
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ===== Stage 2: Runtime =====
FROM python:3.11-slim AS runtime

# Güvenlik: root olmayan kullanıcı
RUN groupadd -r solar && useradd -r -g solar -d /app -s /sbin/nologin solar

WORKDIR /app

# Zaman dilimi
ENV TZ=Europe/Istanbul
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Builder'dan bağımlılıkları kopyala
COPY --from=builder /install /usr/local

# Uygulama dosyalarını kopyala
COPY --chown=solar:solar config.py models.py veritabani.py collector.py collector_async.py panel.py auth.py notifications.py utils.py sanal_inverter.py styles.py healthcheck.py api.py prometheus_exporter.py mqtt_listener.py crm_embed.py ./
COPY --chown=solar:solar pages/ ./pages/
COPY --chown=solar:solar .streamlit/ ./.streamlit/
COPY --chown=solar:solar .env.example ./.env.example

# .env yoksa example'dan oluştur
RUN cp -n .env.example .env 2>/dev/null || true

# Data dizini oluştur ve tüm dosyalara izin ver
RUN mkdir -p /app/data && chown -R solar:solar /app

# Port (Streamlit + Healthcheck + API + Prometheus)
EXPOSE 8501 8502 8503 9100

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Kullanıcı değiştir
USER solar

# Varsayılan: Streamlit panel
ENTRYPOINT ["streamlit", "run", "panel.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]

ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8