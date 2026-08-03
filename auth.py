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


_DEFAULT_ADMIN_HASH = "0139dcacdd93868fd19a701191131882297aab91532bfb7b825b886f19ae7a53"

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
        except Exception:
            pass
    # Fallback: return default admin user
    return {"admin": {"hash": _DEFAULT_ADMIN_HASH, "role": "admin"}}

# LOGIN CSS (Animated Premium)
_LOGIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* GIZLI YAPI */
[data-testid="stSidebar"], [data-testid="stHeader"], footer, header {
    display: none !important;
    visibility: hidden !important;
    height: 0px !important;
}

/* ===== ANIMATED GRADIENT BACKGROUND ===== */
.stApp {
    background: linear-gradient(-45deg, #0a0f1e, #1c2950, #1a3a5c, #0f1b38, #1c2950) !important;
    background-color: transparent !important;
    background-size: 300% 300% !important;
    animation: gradientShift 8s ease infinite !important;
}
[data-testid="stAppViewContainer"] {
    background: transparent !important;
    background-color: transparent !important;
}
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {
    background: transparent !important;
}

@keyframes gradientShift {
    0%   { background-position: 0% 50%; }
    25%  { background-position: 50% 100%; }
    50%  { background-position: 100% 50%; }
    75%  { background-position: 50% 0%; }
    100% { background-position: 0% 50%; }
}

/* ===== KART — Slide-up + Fade-in ===== */
div[data-testid="column"]:nth-child(2) {
    background: #ffffff !important;
    border-radius: 16px !important;
    padding: 44px 40px !important;
    box-shadow: 0 25px 60px rgba(0,0,0,0.3) !important;
    animation: cardEntrance 1s cubic-bezier(0.16, 1, 0.3, 1) both !important;
}

@keyframes cardEntrance {
    from {
        opacity: 0;
        transform: translateY(50px) scale(0.95);
    }
    to {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

/* Ensure form wrapper has no border since col2 is the card */
[data-testid="stForm"] {
    border: none !important;
    padding: 0 !important;
}

/* ===== TITLE ===== */
.login-title {
    text-align: center;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 1.8rem;
    font-weight: 800;
    color: #1e293b;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    animation: fadeSlideDown 0.6s ease 0.3s both;
}

@keyframes fadeSlideDown {
    from { opacity: 0; transform: translateY(-15px); }
    to   { opacity: 1; transform: translateY(0); }
}

.login-title-icon {
    background: linear-gradient(135deg, #2563eb, #3b82f6);
    color: white;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 18px;
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
    font-size: 0.9rem;
    color: #94a3b8;
    margin-bottom: 24px;
    animation: fadeSlideDown 0.6s ease 0.5s both;
    letter-spacing: 0.5px;
}

div[data-testid="column"] > div {
    margin-top: -24px !important;
}

/* ===== INPUT ALANLARI ===== */
[data-testid="stTextInput"] input {
    background: #f8fafc !important;
    border: 1.5px solid #e2e8f0 !important;
    color: #1e293b !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.3s ease !important;
}
[data-testid="stTextInput"] input:focus {
    background: #ffffff !important;
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
}
[data-testid="stTextInput"] label {
    color: #475569 !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    font-family: 'Inter', sans-serif !important;
    letter-spacing: 0.3px;
}

/* ===== GIRIS BUTONU — Glow Pulse ===== */
[data-testid="stButton"] button {
    background: linear-gradient(135deg, #2563eb, #3b82f6) !important;
    border: none !important;
    color: #ffffff !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-family: 'Inter', sans-serif !important;
    padding: 24px 12px !important;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    margin-top: 10px !important;
    letter-spacing: 0.5px;
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
[data-testid="stButton"] button:active {
    transform: translateY(0px) scale(0.98) !important;
}

/* ===== HATA MESAJLARI ===== */
[data-testid="stNotification"] {
    background: #fef2f2 !important;
    border: 1px solid #fecaca !important;
    color: #b91c1c !important;
    border-radius: 10px !important;
    animation: shakeError 0.4s ease !important;
}

@keyframes shakeError {
    0%, 100% { transform: translateX(0); }
    20%      { transform: translateX(-8px); }
    40%      { transform: translateX(8px); }
    60%      { transform: translateX(-4px); }
    80%      { transform: translateX(4px); }
}
</style>
"""

# Floating particles HTML component (runs in its own iframe with JS)
_PARTICLES_HTML = """
<div id="particle-canvas" style="position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:9999;overflow:hidden;"></div>
<script>
const canvas = document.getElementById('particle-canvas');
const colors = ['rgba(37,99,235,0.35)','rgba(59,130,246,0.25)','rgba(99,102,241,0.2)','rgba(245,158,11,0.25)','rgba(16,185,129,0.2)'];
for (let i = 0; i < 25; i++) {
    const p = document.createElement('div');
    const size = Math.random() * 10 + 4;
    const dur = Math.random() * 14 + 8;
    const delay = Math.random() * 12;
    const left = Math.random() * 100;
    p.style.cssText = `
        position:absolute; border-radius:50%;
        width:${size}px; height:${size}px;
        left:${left}%; bottom:-20px;
        background:${colors[Math.floor(Math.random()*colors.length)]};
        animation: rise ${dur}s linear ${delay}s infinite;
    `;
    canvas.appendChild(p);
}
const style = document.createElement('style');
style.textContent = `
    @keyframes rise {
        0%   { transform: translateY(0) scale(0); opacity:0; }
        10%  { opacity:0.7; transform: translateY(-10vh) scale(1); }
        90%  { opacity:0.2; }
        100% { transform: translateY(-110vh) scale(0.5); opacity:0; }
    }
`;
document.head.appendChild(style);
</script>
"""

def check_auth() -> bool:
    if not _is_auth_enabled():
        return True
    if st.session_state.get("authenticated"):
        return True
    _show_login_form()
    return False


def _show_login_form():
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)
    
    # Floating particles via st.components.v1.html (supports JavaScript)
    import streamlit.components.v1 as components
    components.html(_PARTICLES_HTML, height=0, scrolling=False)
    
    # Boşluk bırakalım ki form çok yukarda durmasın
    st.markdown("<br><br><br>", unsafe_allow_html=True)

    # Login formunu ve kartını aynı kolon içine alıyoruz (Böylece genişlikleri BİREBİR aynı olur)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("""
                    <div class="login-title"><div class="login-title-icon">◑</div> <span>Solar<span style="color:#2563eb;">Monitor</span></span></div>
            <div class="login-subtitle">Gunes Enerjisi Santrali Izleme Sistemi</div>
        </div>
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
