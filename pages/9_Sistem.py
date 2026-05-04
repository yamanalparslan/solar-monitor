import streamlit as st
import sys, os, platform
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
from config import config
from modbus_diagnostics import load_runtime_config
from styles import inject_glossy_css, section_header, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="Sistem", page_icon="", layout="wide")
inject_glossy_css()
if not check_auth():
    st.stop()
logout_button()
veritabani.init_db()

from veritabani import FABRIKALAR
if 'fabrika_id' not in st.session_state or st.session_state.fabrika_id is None:
    st.warning("Lütfen ana sayfadan bir fabrika seçin.")
    st.stop()
fab_id = st.session_state.fabrika_id
runtime_config = load_runtime_config()
st.title(" Sistem Durumu")
section_header("", "Sistem Bilgileri", "Konfigurasyon ve ortam durumu")

kpi_row([
    {"value": platform.node()[:15], "label": "Hostname", "color": "#6366f1"},
    {"value": platform.python_version(), "label": "Python", "color": "#10b981"},
    {"value": platform.system(), "label": "OS", "color": "#f59e0b"},
])
st.markdown("<br>", unsafe_allow_html=True)

section_header("", "Modbus")
c1, c2, c3 = st.columns(3)
c1.metric("IP", runtime_config.target_ip)
c2.metric("Port", runtime_config.target_port)
c3.metric("Refresh", str(runtime_config.refresh_rate) + "s")
st.caption(f"Aktif ayar kaynagi: {runtime_config.source}")

section_header("", "Veritabani")
try:
    import sqlite3
    conn = sqlite3.connect(veritabani.DB_NAME)
    oc = conn.execute("SELECT COUNT(*) FROM olcumler").fetchone()[0]
    sz = os.path.getsize(veritabani.DB_NAME) if os.path.exists(veritabani.DB_NAME) else 0
    conn.close()
    kpi_row([
        {"value": format(oc, ','), "label": "Olcum", "color": "#22d3ee"},
        {"value": str(round(sz/1024)) + " KB", "label": "DB", "color": "#a855f7"},
    ])
except Exception as e:
    st.error("DB Hatas: " + str(e))

section_header("", "MQTT")
c1, c2 = st.columns(2)
c1.metric("MQTT", "Aktif" if config.MQTT_ENABLED else "Kapali")
c2.metric("Broker", config.MQTT_HOST + ":" + str(config.MQTT_PORT))
