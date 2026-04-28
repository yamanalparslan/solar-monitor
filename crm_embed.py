"""
Solar Monitor - CRM Gömme (Embed) Yardımcı Modülü
====================================================
CRM sistemiyle entegrasyon için gerekli fonksiyonlar.

Kullanım:
    from crm_embed import inject_embed_mode, get_crm_config, send_crm_webhook

.env dosyasındaki xxxxx değerlerini kendi CRM bilgilerinizle doldurun.
"""

import os
import logging
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("crm_embed")


# ─────────────────────────────────────────────
# CRM Konfigürasyonu
# ─────────────────────────────────────────────

def get_crm_config() -> dict:
    """CRM entegrasyon ayarlarını .env'den okur.

    Doldurmanız gereken değerler:
        CRM_BASE_URL     → xxxxx  (Örn: https://crm.sirketiniz.com)
        CRM_API_KEY      → xxxxx  (CRM admin panelinden alın)
        CRM_API_SECRET   → xxxxx  (Varsa, CRM'den alın)
        CRM_TENANT_ID    → xxxxx  (Şirket/müşteri ID)
        CRM_USERNAME     → xxxxx  (Entegrasyon kullanıcısı)
        CRM_PASSWORD     → xxxxx  (Service account şifresi/token)
        CRM_ALLOWED_ORIGIN → xxxxx (Örn: https://crm.sirketiniz.com)
        SOLAR_MONITOR_EXTERNAL_URL → xxxxx (Örn: http://10.35.14.5:8501)
        CRM_WEBHOOK_URL  → xxxxx  (Alarm webhook endpoint)
        CRM_WEBHOOK_SECRET → xxxxx (Webhook doğrulama anahtarı)
    """
    return {
        "base_url": os.getenv("CRM_BASE_URL", "xxxxx"),
        "api_key": os.getenv("CRM_API_KEY", "xxxxx"),
        "api_secret": os.getenv("CRM_API_SECRET", "xxxxx"),
        "tenant_id": os.getenv("CRM_TENANT_ID", "xxxxx"),
        "username": os.getenv("CRM_USERNAME", "xxxxx"),
        "password": os.getenv("CRM_PASSWORD", "xxxxx"),
        "allowed_origin": os.getenv("CRM_ALLOWED_ORIGIN", "xxxxx"),
        "external_url": os.getenv("SOLAR_MONITOR_EXTERNAL_URL", "xxxxx"),
        "webhook_url": os.getenv("CRM_WEBHOOK_URL", "xxxxx"),
        "webhook_secret": os.getenv("CRM_WEBHOOK_SECRET", "xxxxx"),
        "embed_mode": os.getenv("CRM_EMBED_MODE", "true").lower() in ("true", "1", "yes"),
    }


def is_embed_mode() -> bool:
    """CRM gömme modu aktif mi kontrol eder."""
    return os.getenv("CRM_EMBED_MODE", "true").lower() in ("true", "1", "yes")


# ─────────────────────────────────────────────
# Embed Modu CSS — Temiz iframe görünümü
# ─────────────────────────────────────────────

_EMBED_CSS = """
<style>
    /* ── CRM Embed Modu: Gereksiz Streamlit UI elemanlarını gizle ── */

    /* Üst menü çubuğu (hamburger, deploy vb.) */
    header[data-testid="stHeader"] {
        display: none !important;
    }

    /* Alt footer ("Made with Streamlit") */
    footer {
        display: none !important;
    }

    /* Streamlit toolbar (sağ üst köşe) */
    .stDeployButton,
    #MainMenu {
        display: none !important;
    }

    /* Ana içerik padding ayarı — iframe'de sıfırla */
    .main .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0 !important;
    }

    /* Sidebar'ı varsayılan olarak gizle (embed modunda) */
    section[data-testid="stSidebar"] {
        display: none !important;
    }

    /* iframe kenarlık kaldır */
    .stApp {
        border: none !important;
    }
</style>
"""

_EMBED_CSS_WITH_SIDEBAR = """
<style>
    /* ── CRM Embed Modu (Sidebar ile): Sadece header/footer gizle ── */

    header[data-testid="stHeader"] {
        display: none !important;
    }

    footer {
        display: none !important;
    }

    .stDeployButton,
    #MainMenu {
        display: none !important;
    }

    .main .block-container {
        padding-top: 1rem !important;
    }
</style>
"""


def inject_embed_mode(hide_sidebar: bool = True):
    """CRM embed modunda gereksiz UI elemanlarını gizler.

    Args:
        hide_sidebar: True ise sidebar da gizlenir (varsayılan).
                      False ise sadece header/footer gizlenir.

    panel.py'de kullanım:
        from crm_embed import inject_embed_mode
        inject_embed_mode()
    """
    if not is_embed_mode():
        return

    if hide_sidebar:
        st.markdown(_EMBED_CSS, unsafe_allow_html=True)
    else:
        st.markdown(_EMBED_CSS_WITH_SIDEBAR, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# CRM'ye Webhook Gönderme
# ─────────────────────────────────────────────

def send_crm_webhook(event_type: str, payload: dict) -> bool:
    """CRM'ye alarm/bildirim webhook'u gönderir.

    Args:
        event_type: Olay tipi (Örn: "alarm", "device_offline", "anomaly")
        payload: Gönderilecek veri dict'i

    Returns:
        Başarılı ise True, değilse False

    .env'de doldurmanız gerekenler:
        CRM_WEBHOOK_URL    → xxxxx  (Örn: https://crm.sirketiniz.com/api/webhooks/solar)
        CRM_WEBHOOK_SECRET → xxxxx  (Webhook imzalama anahtarı)
    """
    config = get_crm_config()

    webhook_url = config["webhook_url"]
    webhook_secret = config["webhook_secret"]

    if webhook_url == "xxxxx" or not webhook_url:
        logger.warning("CRM_WEBHOOK_URL ayarlanmamış, webhook gönderilmedi.")
        return False

    try:
        import requests
        import hashlib
        import json
        import time

        data = {
            "event": event_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "tenant_id": config["tenant_id"],
            "source": "solar_monitor",
            "payload": payload,
        }

        headers = {
            "Content-Type": "application/json",
            "X-Solar-Monitor-Event": event_type,
        }

        # Webhook secret ile HMAC imza ekle (CRM doğrulama yapabilsin)
        if webhook_secret and webhook_secret != "xxxxx":
            import hmac
            body = json.dumps(data, sort_keys=True)
            signature = hmac.new(
                webhook_secret.encode("utf-8"),
                body.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            headers["X-Solar-Signature"] = signature

        resp = requests.post(webhook_url, json=data, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info("CRM webhook gönderildi: %s → %s", event_type, resp.status_code)
        return True

    except Exception as exc:
        logger.error("CRM webhook hatası: %s", exc)
        return False


# ─────────────────────────────────────────────
# CRM iframe embed kodu üretici
# ─────────────────────────────────────────────

def get_iframe_embed_code() -> str:
    """CRM'ye yapıştırılacak iframe HTML kodunu üretir.

    CRM yöneticinize bu kodu verin, ilgili sayfaya yapıştırsın.

    .env'de doldurmanız gerekenler:
        SOLAR_MONITOR_EXTERNAL_URL → xxxxx
            (Örn: http://10.35.14.5:8501 veya https://solar.sirketiniz.com)
    """
    config = get_crm_config()
    url = config["external_url"]

    if url == "xxxxx":
        return "<!-- HATA: SOLAR_MONITOR_EXTERNAL_URL .env dosyasında ayarlanmamış! -->"

    return f"""<!-- Solar Monitor - CRM Embed Kodu -->
<iframe
    src="{url}/?embed=true"
    width="100%"
    height="800"
    frameborder="0"
    style="border: none; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);"
    allow="fullscreen"
    title="Solar Monitor - Güneş Enerjisi İzleme">
</iframe>"""


# ─────────────────────────────────────────────
# CRM API'ye veri gönderme (opsiyonel)
# ─────────────────────────────────────────────

def push_data_to_crm(device_id: int, data: dict) -> bool:
    """Inverter verisini CRM API'sine push eder.

    .env'de doldurmanız gerekenler:
        CRM_BASE_URL  → xxxxx  (Örn: https://crm.sirketiniz.com)
        CRM_API_KEY   → xxxxx  (CRM admin panelinden alın)
        CRM_TENANT_ID → xxxxx  (Şirket ID)

    Args:
        device_id: İnverter slave ID
        data: Gönderilecek ölçüm verisi dict'i

    Returns:
        Başarılı ise True
    """
    config = get_crm_config()

    if config["base_url"] == "xxxxx" or config["api_key"] == "xxxxx":
        logger.warning("CRM_BASE_URL veya CRM_API_KEY ayarlanmamış.")
        return False

    try:
        import requests

        endpoint = f"{config['base_url']}/api/v1/solar/devices/{device_id}/data"

        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "X-Tenant-ID": config["tenant_id"],
        }

        resp = requests.post(endpoint, json=data, headers=headers, timeout=10)
        resp.raise_for_status()
        return True

    except Exception as exc:
        logger.error("CRM veri push hatası (ID=%s): %s", device_id, exc)
        return False
