"""
Solar Monitor - Kimlik Dogrulama Sistemi
==========================================
Streamlit session state tabanli login/logout.
Glossy tasarimli giris ekrani.

Kullanm:
    from auth import check_auth, logout_button
    if not check_auth():
        st.stop()
    logout_button()
"""

import os
import hashlib
import streamlit as st
import time

import sqlite3
import os

_AUTH_DB_PATH = os.path.join("data", "auth.db")

def _get_db():
    os.makedirs("data", exist_ok=True)
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
    """Kullanc ad ve ifre hash'ini dner.
    
    Returns:
        (username, password_hash)  hash bosa varsaylan 'admin' ifresi kullanlr
    """
    username = os.getenv("AUTH_USERNAME", "admin")
    password_hash = os.getenv("AUTH_PASSWORD_HASH", "")

    # Hash tanml deilse varsaylan ifre: "admin"
    if not password_hash:
        password_hash = _DEFAULT_ADMIN_HASH

    return username, password_hash


# 
# LOGIN CSS (Glossy Tasarm)
# 
_LOGIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2Infinitefamily=Inter:wght@300;400;500;600;700;800&display=swap');

.login-container {
    max-width: 420px;
    margin: 60px auto;
    padding: 0;
}
.login-card {
    background: linear-gradient(145deg, 
        rgba(30, 41, 59, 0.85) 0%, 
        rgba(15, 23, 42, 0.7) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 40px 36px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    position: relative;
    overflow: hidden;
}
.login-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7);
}
.login-logo {
    text-align: center;
    margin-bottom: 8px;
    font-size: 3rem;
}
.login-title {
    text-align: center;
    font-family: 'Inter', sans-serif;
    font-size: 1.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 4px;
}
.login-subtitle {
    text-align: center;
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    color: #64748b;
    margin-bottom: 28px;
}
.login-footer {
    text-align: center;
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    color: #475569;
    margin-top: 20px;
}
</style>
"""


def check_auth() -> bool:
    """Kimlik dorulama kontrol.

    Auth devre dysa True dner.
    Giri yaplmsa True dner.
    Giri yaplmamsa login formu gsterir ve False dner.
    """
    if not _is_auth_enabled():
        return True

    # Zaten giri yaplm mInfinite
    if st.session_state.get("authenticated"):
        return True

    # Login ekrann gster
    _show_login_form()
    return False


def _show_login_form():
    """Glossy login formu gsterir."""
    # Arka plan ve login CSS
    st.markdown("""
    <style>
    .stApp {
        background: 
            radial-gradient(ellipse at 20% 50%, rgba(99, 102, 241, 0.1) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 20%, rgba(168, 85, 247, 0.08) 0%, transparent 50%),
            #0a0e1a !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="login-container">
        <div class="login-card">
            <div class="login-logo"></div>
            <div class="login-title">Solar Monitor</div>
            <div class="login-subtitle">Gunes Enerjisi Santrali Izleme Sistemi</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Login formu (Streamlit native  CSS card'n altna yerleir)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Kullanici Adi", placeholder="admin")
            password_input = st.text_input("Sifre", type="password", placeholder="")
            submitted = st.form_submit_button("Giris Yap", width='stretch', type="primary")

            if submitted:
                client_ip = _get_client_ip()
                rate_key = f"{client_ip}_{username_input}"
                
                rate_record = _get_rate_record(rate_key)
                current_time = time.time()
                
                if current_time < rate_record["lockout_until"]:
                    kalan = int(rate_record["lockout_until"] - current_time)
                    st.error(f"Çok fazla hatalı deneme yaptınız. Lütfen {kalan} saniye bekleyin.")
                else:
                    # Süre dolmuşsa resetle
                    if rate_record["attempts"] >= 3:
                        rate_record["attempts"] = 0
                        
                    expected_user, expected_hash = _get_credentials()
                    if username_input == expected_user and _verify_password(password_input, expected_hash):
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = username_input
                        rate_record["attempts"] = 0 # Başarılı girişte sıfırla
                        _save_rate_record(rate_key, rate_record)
                        st.rerun()
                    else:
                        rate_record["attempts"] += 1
                        if rate_record["attempts"] >= 3:
                            rate_record["lockout_until"] = current_time + 30
                            st.error("Çok fazla hatalı deneme yaptınız. Lütfen 30 saniye bekleyin.")
                        else:
                            st.error(f"Kullanici adi veya sifre hatali! (Kalan deneme: {3 - rate_record['attempts']})")
                        _save_rate_record(rate_key, rate_record)
                        time.sleep(1) # Time-delay attack mitigation

        st.markdown("""
        <div class="login-footer">
            Sisteme giris yapmak icin yetkili bilgilerinizi kullanin.<br>
            (Ayarlar .env dosyasindan yapilandirilabilir)
        </div>
        """, unsafe_allow_html=True)


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


def get_current_user() -> str:
    """Mevcut oturumdaki kullanc adn dner."""
    return st.session_state.get("username", "admin")

def get_user_role(username: str) -> str:
    """Kullanıcının rolünü .env'den (USER_ROLES) okur. Varsayılan: viewer."""
    roles_str = os.getenv("USER_ROLES", "admin:admin")
    roles = {}
    for pair in roles_str.split(","):
        if ":" in pair:
            u, r = pair.split(":", 1)
            roles[u.strip()] = r.strip().lower()
    
    return roles.get(username, "viewer")
