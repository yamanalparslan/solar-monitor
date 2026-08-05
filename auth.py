"""
Solar Monitor - Kimlik Dogrulama Sistemi
==========================================
Streamlit session state tabanli login/logout.
Glossy tasarimli giris ekrani.

Kullanm:
    from auth import check_auth, logout_button
    if not check_auth():
        st.stop()
    
"""

import os
import hashlib
import streamlit as st
import time

import sqlite3
import os

_AUTH_DB_PATH = os.path.join("data", "auth.db")

def _get_db():
    try:
        os.makedirs("data", exist_ok=True)
    except OSError:
        pass
    conn = sqlite3.connect(_AUTH_DB_PATH, timeout=10.0)
    conn.execute("CREATE TABLE IF NOT EXISTS failed_logins (rate_key TEXT PRIMARY KEY, attempts INTEGER, lockout_until REAL)")
    return conn

def _get_rate_record(rate_key):
    with _get_db() as conn:
        row = conn.execute("SELECT attempts, lockout_until FROM failed_logins WHERE rate_key=?", (rate_key,)).fetchone()
        if row:
            return {"attempts": row[0], "lockout_until": row[1]}
        return {"attempts": 0, "lockout_until": 0.0}

def _save_rate_record(rate_key, record):
    with _get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO failed_logins (rate_key, attempts, lockout_until) VALUES (?, ?, ?)", 
                     (rate_key, record["attempts"], record["lockout_until"]))


def _get_client_ip():
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            return st.context.headers.get("X-Forwarded-For", "unknown")
    except Exception:
        pass
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        headers = _get_websocket_headers()
        return headers.get("X-Forwarded-For", "unknown")
    except Exception:
        pass
    return "unknown"

# PBKDF2 sabitleri
_PBKDF2_ITERATIONS = 100_000

def _get_password_hash(password: str) -> str:
    """PBKDF2-HMAC-SHA256 ile güçlü şifre hash'i oluşturur (100K iterasyon) rastgele salt ile."""
    salt = os.urandom(16)
    hash_hex = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt, _PBKDF2_ITERATIONS
    ).hex()
    return f"{salt.hex()}:{hash_hex}"

def _verify_password(password: str, stored_hash: str) -> bool:
    """Şifreyi PBKDF2 hash ile karşılaştırır (Geriye dönük uyumluluk içerir)."""
    if ":" in stored_hash:
        salt_hex, hash_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), salt, _PBKDF2_ITERATIONS
        ).hex()
        return expected_hash == hash_hex
    else:
        # Eski sabit salt (solar_monitor_v2) için geriye dönük uyumluluk
        expected_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), b'solar_monitor_v2', _PBKDF2_ITERATIONS
        ).hex()
        return expected_hash == stored_hash


def _is_auth_enabled() -> bool:
    """Authentication aktif mi kontrol eder (.env AUTH_ENABLED ile yönetilir)."""
    return os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")


def _get_credentials() -> tuple[str, str]:
    pass # Deprecated



# 
import json
_USERS_JSON_PATH = os.path.join("data", "users.json")

def load_users() -> dict:
    if os.path.exists(_USERS_JSON_PATH):
        try:
            with open(_USERS_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            pass
    # Kullanıcı veritabanı yoksa veya okunamadıysa boş döneriz,
    # check_auth() ilk kurulum uyarısı verecek.
    return {}

def save_users(users: dict):
    os.makedirs(os.path.dirname(_USERS_JSON_PATH), exist_ok=True)
    with open(_USERS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)

def add_user(username: str, password: str, role: str = "user") -> bool:
    users = load_users()
    if username in users:
        return False
    password_hash = _get_password_hash(password)
    users[username] = {"hash": password_hash, "role": role}
    save_users(users)
    return True

def delete_user(username: str) -> bool:
    users = load_users()
    if username in users:
        del users[username]
        save_users(users)
        return True
    return False

# ===== DYNAMIC SKY BACKGROUND SYSTEM =====
import math
import urllib.parse

def _build_sky_css():
    """Saate gore gokyuzu CSS'i olusturur (gradient, gunes/ay, siluet - hepsi CSS icinde)."""
    from datetime import datetime
    now = datetime.now()
    hour = now.hour + now.minute / 60.0

    # === GOKYUZU RENKLERI ===
    if 5 <= hour < 6.5:
        sky = "linear-gradient(180deg, #1a1a2e 0%, #16213e 25%, #e94560 60%, #ff8a5c 85%, #ffd89b 100%)"
        sil = "%230a0a15"
    elif 6.5 <= hour < 9:
        sky = "linear-gradient(180deg, #4a90d9 0%, #87ceeb 45%, #b4d7f5 75%, #ffecd2 100%)"
        sil = "%2312182a"
    elif 9 <= hour < 15:
        sky = "linear-gradient(180deg, #1e3c72 0%, #2a5298 35%, #4a90d9 65%, #87ceeb 100%)"
        sil = "%230f1b2d"
    elif 15 <= hour < 17.5:
        sky = "linear-gradient(180deg, #2c3e50 0%, #3498db 30%, #e67e22 70%, #f39c12 100%)"
        sil = "%230d1520"
    elif 17.5 <= hour < 20:
        sky = "linear-gradient(180deg, #2c3e50 0%, #8e44ad 25%, #e74c3c 55%, #f39c12 80%, #f5d061 100%)"
        sil = "%230a0a15"
    else:
        sky = "linear-gradient(180deg, #050510 0%, #0a0a1a 35%, #0f1b38 65%, #1c2950 100%)"
        sil = "%23030308"

    # === GUNES / AY (CSS ::before) ===
    if 6 <= hour <= 20:
        progress = (hour - 6) / 14.0
        angle = math.pi * progress
        sun_x = 15 + 70 * progress
        sun_y = 70 - 55 * math.sin(angle)
        sun_size = 30 + 20 * math.sin(angle)
        if hour < 8:
            sun_color, glow = "#ff6b35", "rgba(255,107,53,0.5)"
        elif hour < 16:
            sun_color, glow = "#ffd700", "rgba(255,215,0,0.4)"
        else:
            sun_color, glow = "#ff4500", "rgba(255,69,0,0.5)"
        sun_css = f"""
            content: '';
            position: fixed;
            left: {sun_x:.1f}%; top: {sun_y:.1f}%;
            width: {sun_size:.0f}px; height: {sun_size:.0f}px;
            background: radial-gradient(circle, {sun_color} 30%, {glow} 70%, transparent 100%);
            border-radius: 50%;
            box-shadow: 0 0 {sun_size:.0f}px {glow}, 0 0 {sun_size*2:.0f}px {glow};
            transform: translate(-50%, -50%);
            pointer-events: none;
            z-index: 1;
        """
    else:
        sun_css = """
            content: '';
            position: fixed;
            left: 72%; top: 18%;
            width: 28px; height: 28px;
            background: radial-gradient(circle at 35% 35%, #f5f5f5 0%, #e0e0e0 50%, #ccc 100%);
            border-radius: 50%;
            box-shadow: 0 0 20px rgba(255,255,255,0.3), 0 0 60px rgba(255,255,255,0.1);
            transform: translate(-50%, -50%);
            pointer-events: none;
            z-index: 1;
        """

    # === YILDIZLAR (CSS box-shadow trick) ===
    stars_css = ""
    if hour < 6.5 or hour > 18.5:
        import random
        rng = random.Random(now.day)
        shadows = []
        for _ in range(40):
            sx = rng.randint(10, 1900)
            sy = rng.randint(10, 600)
            so = rng.uniform(0.3, 0.9)
            shadows.append(f"{sx}px {sy}px 0 0 rgba(255,255,255,{so:.1f})")
        stars_css = f"""
            .stApp::after {{
                content: '';
                position: fixed;
                top: 0; left: 0;
                width: 1px; height: 1px;
                box-shadow: {', '.join(shadows)};
                pointer-events: none;
                z-index: 1;
            }}
        """

    # === SILUET SVG (data URI olarak encode) ===
    svg_raw = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 200" preserveAspectRatio="none"><path d="M0,200 L0,140 Q100,80 200,120 Q320,55 450,100 Q550,45 680,90 Q800,40 920,95 Q1050,60 1200,120 L1200,200 Z" fill="{sil}"/><g transform="translate(460,78) rotate(-12)"><rect x="0" y="0" width="28" height="2" fill="{sil}"/><rect x="2" y="-11" width="24" height="10" fill="{sil}" rx="1"/><line x1="14" y1="0" x2="14" y2="-11" stroke="{sil}" stroke-width="2"/></g><g transform="translate(498,72) rotate(-6)"><rect x="0" y="0" width="28" height="2" fill="{sil}"/><rect x="2" y="-11" width="24" height="10" fill="{sil}" rx="1"/><line x1="14" y1="0" x2="14" y2="-11" stroke="{sil}" stroke-width="2"/></g><g transform="translate(536,70) rotate(-2)"><rect x="0" y="0" width="28" height="2" fill="{sil}"/><rect x="2" y="-11" width="24" height="10" fill="{sil}" rx="1"/><line x1="14" y1="0" x2="14" y2="-11" stroke="{sil}" stroke-width="2"/></g><line x1="820" y1="70" x2="820" y2="20" stroke="{sil}" stroke-width="3"/><g transform="translate(820,20)"><line x1="0" y1="0" x2="-18" y2="-12" stroke="{sil}" stroke-width="2.5"/><line x1="0" y1="0" x2="16" y2="-10" stroke="{sil}" stroke-width="2.5"/><line x1="0" y1="0" x2="2" y2="18" stroke="{sil}" stroke-width="2.5"/></g><rect x="120" y="100" width="55" height="40" fill="{sil}"/><rect x="135" y="82" width="10" height="58" fill="{sil}"/><rect x="158" y="88" width="8" height="52" fill="{sil}"/><rect x="960" y="88" width="28" height="18" fill="{sil}"/><polygon points="960,88 974,74 988,88" fill="{sil}"/><rect x="1000" y="92" width="22" height="14" fill="{sil}"/><polygon points="1000,92 1011,80 1022,92" fill="{sil}"/><line x1="700" y1="65" x2="700" y2="30" stroke="{sil}" stroke-width="2"/><line x1="688" y1="35" x2="712" y2="35" stroke="{sil}" stroke-width="2"/><line x1="691" y1="42" x2="709" y2="42" stroke="{sil}" stroke-width="2"/></svg>'

    # Note: sil already uses %23 prefix for # in URL encoding
    silhouette_css = f"""
        .sky-silhouette {{
            position: fixed;
            bottom: 0; left: 0;
            width: 100%; height: 28%;
            background-image: url("data:image/svg+xml,{svg_raw}");
            background-size: cover;
            background-repeat: no-repeat;
            pointer-events: none;
            z-index: 2;
        }}
    """

    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700;800&display=swap');
    .stApp {{
        background: {sky} !important;
        background-color: transparent !important;
    }}
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {{
        background: transparent !important;
        background-color: transparent !important;
    }}
    .stApp::before {{
        {sun_css}
    }}
    {stars_css}
    {silhouette_css}
    </style>
    <div class="sky-silhouette"></div>
    """


# LOGIN CSS (Card + Form styling only, background handled by sky HTML)
_LOGIN_CSS_TEMPLATE = """
<style>


[data-testid="stSidebar"], [data-testid="stHeader"], footer, header {
    display: none !important;
    visibility: hidden !important;
    height: 0px !important;
}

[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stMainBlockContainer"] {
    background: transparent !important;
    background-color: transparent !important;
}

/* ===== KART — Slide-up + Fade-in ===== */
div[data-testid="column"]:nth-child(2) {
    background: rgba(255,255,255,0.95) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border-radius: 16px !important;
    padding: 44px 40px !important;
    box-shadow: 0 25px 60px rgba(0,0,0,0.25) !important;
    animation: cardEntrance 1s cubic-bezier(0.16, 1, 0.3, 1) both !important;
    position: relative;
    z-index: 10;
}
@keyframes cardEntrance {
    from { opacity: 0; transform: translateY(50px) scale(0.95); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}

[data-testid="stForm"] {
    border: none !important;
    padding: 0 !important;
}

.login-title {
    text-align: center;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 3.2rem;
    font-weight: 900;
    color: #1e293b;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    animation: fadeSlideDown 0.6s ease 0.3s both;
}
@keyframes fadeSlideDown {
    from { opacity: 0; transform: translateY(-15px); }
    to   { opacity: 1; transform: translateY(0); }
}

.login-title-icon {
    background: linear-gradient(135deg, #2563eb, #3b82f6);
    color: white;
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 24px;
    animation: iconPulse 3s ease-in-out infinite !important;
    box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4);
}
@keyframes iconPulse {
    0%, 100% { box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4); transform: scale(1); }
    50%      { box-shadow: 0 8px 30px rgba(37, 99, 235, 0.7); transform: scale(1.08); }
}

.login-subtitle {
    text-align: center;
    font-family: 'Inter', sans-serif;
    font-size: 1.2rem;
    color: #ffffff;
    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    margin-bottom: 30px;
    font-weight: 600;
    animation: fadeSlideDown 0.6s ease 0.5s both;
    letter-spacing: 0.5px;
}

div[data-testid="column"] > div {
    margin-top: -24px !important;
}

[data-testid="stTextInput"] input {
    background: #f8fafc !important;
    border: 2px solid #cbd5e1 !important;
    color: #0f172a !important;
    border-radius: 10px !important;
    padding: 16px 18px !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.3s ease !important;
}
[data-testid="stTextInput"] input:focus {
    background: #ffffff !important;
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
}
[data-testid="stTextInput"] label {
    color: #1e293b !important;
    font-weight: 800 !important;
    font-size: 1.1rem !important;
    font-family: 'Inter', sans-serif !important;
    letter-spacing: 0.5px;
    margin-bottom: 8px !important;
}

[data-testid="stButton"] button {
    background: linear-gradient(135deg, #2563eb, #3b82f6) !important;
    border: none !important;
    color: #ffffff !important;
    border-radius: 10px !important;
    font-weight: 800 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 1.15rem !important;
    padding: 26px 12px !important;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    margin-top: 15px !important;
    animation: buttonGlow 2.5s ease-in-out infinite !important;
}
@keyframes buttonGlow {
    0%, 100% { box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3); }
    50%      { box-shadow: 0 8px 40px rgba(37, 99, 235, 0.6); }
}
[data-testid="stButton"] button:hover {
    background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 12px 35px rgba(37, 99, 235, 0.5) !important;
}

[data-testid="stNotification"] {
    background: #fef2f2 !important;
    border: 1px solid #fecaca !important;
    color: #b91c1c !important;
    border-radius: 10px !important;
    animation: shakeError 0.4s ease !important;
}
@keyframes shakeError {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-8px); }
    40% { transform: translateX(8px); }
    60% { transform: translateX(-4px); }
    80% { transform: translateX(4px); }
}
</style>
"""


def check_auth() -> bool:
    if not _is_auth_enabled():
        return True
    if st.session_state.get("authenticated"):
        return True
        
    if not os.path.exists(_USERS_JSON_PATH):
        st.error("⚠️ Sistemde tanımlı hiçbir kullanıcı bulunamadı (`users.json` eksik).")
        st.info("Lütfen sunucu üzerinden `python kurulum_yap.py` komutunu çalıştırarak ilk kurulumu tamamlayın.")
        st.stop()
        
    _show_login_form()
    return False


def _show_login_form():
    # Dynamic sky background (pure CSS - computed from current hour)
    sky_css = _build_sky_css()
    st.markdown(sky_css, unsafe_allow_html=True)
    st.markdown(_LOGIN_CSS_TEMPLATE, unsafe_allow_html=True)

    # Boşluk bırakalım ki form çok yukarda durmasın
    st.markdown("<br><br><br>", unsafe_allow_html=True)

    # Login formunu ve kartını aynı kolon içine alıyoruz
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("""
            <div class="login-title"><div class="login-title-icon">◑</div> <span>Solar<span style="color:white;">Monitor</span></span></div>
            <div class="login-subtitle">Gunes Enerjisi Santrali Izleme Sistemi</div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Kullanici Adi", placeholder="admin")
            password_input = st.text_input("Sifre", type="password", placeholder="")
            submitted = st.form_submit_button("Giris Yap", width='stretch', type="primary")

            if submitted:
                client_ip = _get_client_ip()
                rate_key = f"{client_ip}_{username_input}"
                
                rate_record = _get_rate_record(rate_key)
                import time
                current_time = time.time()
                
                if current_time < rate_record["lockout_until"]:
                    kalan = int(rate_record["lockout_until"] - current_time)
                    st.error(f"Cok fazla hatali deneme yaptiniz. Lutfen {kalan} saniye bekleyin.")
                else:
                    if rate_record["attempts"] >= 3:
                        rate_record["attempts"] = 0
                        
                    users = load_users()
                    if username_input in users and _verify_password(password_input, users[username_input]["hash"]):
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = username_input
                        rate_record["attempts"] = 0
                        _save_rate_record(rate_key, rate_record)
                        st.rerun()
                    else:
                        rate_record["attempts"] += 1
                        if rate_record["attempts"] >= 3:
                            rate_record["lockout_until"] = current_time + 30
                            st.error("Cok fazla hatali deneme yaptiniz. Lutfen 30 saniye bekleyin.")
                        else:
                            st.error(f"Kullanici adi veya sifre hatali! (Kalan deneme: {3 - rate_record['attempts']})")
                        _save_rate_record(rate_key, rate_record)
                        import time as _time
                        _time.sleep(1)

        



def logout_button():
    """Sidebar'da k butonu gsterir."""
    if not _is_auth_enabled():
        return

    if st.session_state.get("authenticated"):
        with st.sidebar:
            st.markdown("---")
            user = st.session_state.get("username", "admin")
            st.caption(f" {user}")
            if st.button("Cikis Yap", key="logout_btn"):
                st.session_state["authenticated"] = False
                st.session_state.pop("username", None)
                st.rerun()

def top_nav_logout_button():
    """Top Navigation Bar icin Cikis Yap butonu."""
    if not _is_auth_enabled():
        return

    if st.session_state.get("authenticated"):
        if st.button("Cikis Yap", key="top_logout_btn", type="secondary"):
            st.session_state["authenticated"] = False
            st.session_state.pop("username", None)
            st.rerun()
def get_current_user() -> str:
    """Mevcut oturumdaki kullanc adn dner."""
    return st.session_state.get("username", "admin")

def get_user_role(username: str) -> str:
    """Kullanıcının rolünü users.json'dan okur."""
    users = load_users()
    if username in users:
        return users[username].get("role", "viewer")
    return "viewer"
