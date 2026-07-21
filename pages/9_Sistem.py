import streamlit as st
import sys, os, platform
import json
import uuid
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
from config import config
from modbus_diagnostics import load_runtime_config
from styles import render_top_nav, inject_glossy_css, section_header, kpi_row
from auth import check_auth, logout_button, get_current_user, get_user_role
import utils
import pandas as pd

st.set_page_config(page_title="SISTEM", page_icon="⚙️", layout="wide")
inject_glossy_css()
render_top_nav()
if not check_auth():
    st.stop()

veritabani.init_db()

from veritabani import FABRIKALAR
if 'fabrika_id' not in st.session_state or st.session_state.fabrika_id is None:
    st.warning("Lütfen ana sayfadan bir fabrika seçin.")
    st.stop()
fab_id = st.session_state.fabrika_id

st.title("⚙️ SISTEM DURUMU")

api_pass = st.text_input("Sistem Sayfası Şifresi", type="password", key="sys_pass")
if api_pass != "1444":
    if api_pass:
        st.error("Hatalı şifre.")
    st.stop()

runtime_config = load_runtime_config()
section_header("⚙", "SISTEM BILGILERI", "KONFIGURASYON VE ORTAM DURUMU")

kpi_row([
    {"value": platform.node()[:15], "label": "Hostname", "color": "#6366f1"},
    {"value": platform.python_version(), "label": "Python", "color": "#10b981"},
    {"value": platform.system(), "label": "OS", "color": "#f59e0b"},
])
st.markdown("<br>", unsafe_allow_html=True)

section_header("🔌", "Modbus")
c1, c2, c3 = st.columns(3)
c1.metric("IP", runtime_config.target_ip)
c2.metric("Port", runtime_config.target_port)
c3.metric("Refresh", str(runtime_config.refresh_rate) + "s")
st.caption(f"Aktif ayar kaynagi: {runtime_config.source}")

section_header("💾", "Veritabani")
try:
    conn = veritabani.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM olcumler")
    oc = cursor.fetchone()[0]
    cursor.execute("SELECT pg_database_size(current_database())")
    sz = cursor.fetchone()[0]
    conn.close()
    kpi_row([
        {"value": format(oc, ','), "label": "Olcum", "color": "#22d3ee"},
        {"value": str(round(sz/1024)) + " KB", "label": "DB", "color": "#a855f7"},
    ])
except Exception as e:
    st.error("DB Hatası: " + str(e))

section_header("📡", "MQTT")
c1, c2 = st.columns(2)
c1.metric("MQTT", "Aktif" if config.MQTT_ENABLED else "Kapali")
c2.metric("Broker", config.MQTT_HOST + ":" + str(config.MQTT_PORT))

st.markdown("<hr>", unsafe_allow_html=True)

section_header("⚙️", "SİSTEM VE CİHAZ AYARLARI", "GENEL AYARLAR")

current_user = get_current_user()
user_role = get_user_role(current_user)

st.header("PULSAR AYARLARI")

mevcut_ayarlar = veritabani.tum_ayarlari_oku(fab_id)
interval_options = {
    "10 saniye": 10,
    "30 saniye": 30,
    "1 dakika": 60,
    "10 dakika": 600,
    "30 dakika": 1800,
    "1 saat": 3600,
    "2 saat": 7200
}

current_refresh = float(mevcut_ayarlar.get('refresh_rate', 600))
current_label = "10 dakika"
for label, value in interval_options.items():
    if value == current_refresh:
        current_label = label
        break

if st.session_state.get('ayarlar_kaydedildi', False):
    st.success("Ayarlar başarıyla kaydedildi! Collector yeni ayarlarla okumaya devam edecek.")
    st.session_state.ayarlar_kaydedildi = False

with st.form("ayar_form"):
    target_ip = st.text_input(
        "IP ADRESI",
        value=mevcut_ayarlar.get('target_ip', '10.35.14.10'),
        key="target_ip_input",
    )
    target_port = st.number_input(
        "PORT",
        value=int(mevcut_ayarlar.get('target_port', 502)),
        step=1,
        key="target_port_input",
    )

    st.info("VIRGUL VEYA TIRE ILE AYIRIN (ORN: 1, 2, 5-8)")
    id_input = st.text_input(
        "INVERTER ID LISTESI",
        value=mevcut_ayarlar.get('slave_ids', '1,2,3'),
        key="slave_ids_input",
    )
    target_ids, id_errors = utils.parse_id_list(id_input)

    if id_errors:
        st.warning(f"Bazi ID'ler parse edilemedi: {', '.join(id_errors)}")

    st.write(f"Izlenecek ID'ler: {utils.format_id_list_display(target_ids)}")

    st.divider()
    st.header("LOKASYON AYARLARI (Hava Durumu İçin)")
    c1, c2 = st.columns(2)
    with c1:
        lat_input = st.text_input(
            "ENLEM (Latitude)",
            value=mevcut_ayarlar.get('lat', '38.4237'),
            key="lat_input"
        )
    with c2:
        lon_input = st.text_input(
            "BOYLAM (Longitude)",
            value=mevcut_ayarlar.get('lon', '27.1428'),
            key="lon_input"
        )

    st.divider()
    st.header("ZAMANLAYICI")

    selected_interval = st.select_slider(
        "VERI TOPLAMA SIKLIGI",
        options=list(interval_options.keys()),
        value=current_label,
        key="refresh_rate_slider",
    )

    refresh_rate = interval_options[selected_interval]
    st.info(f" Secilen: {selected_interval} ({refresh_rate} saniye)")

    st.markdown("---")
    st.header("ADRES HARITASI")
    with st.expander("DETAYLI ADRES AYARLARI", expanded=False):
        c_guc_adr = st.number_input(
            "GUC ADRESI",
            value=int(mevcut_ayarlar.get('guc_addr', 75)),
            key="guc_addr_input",
        )
        c_guc_sc = st.number_input(
            "GUC CARPAN",
            value=float(mevcut_ayarlar.get('guc_scale', 0.1)),
            step=0.01,
            format="%.4f",
            key="guc_scale_input",
            help="Ondalik olarak yazabilirsiniz. Ornek: 0.01",
        )

        c_volt_adr = st.number_input(
            "VOLTAJ ADRESI",
            value=int(mevcut_ayarlar.get('volt_addr', 73)),
            key="volt_addr_input",
        )
        c_volt_sc = st.number_input(
            "VOLTAJ CARPAN",
            value=float(mevcut_ayarlar.get('volt_scale', 0.1)),
            step=0.01,
            format="%.4f",
            key="volt_scale_input",
            help="Ondalik olarak yazabilirsiniz. Ornek: 0.1",
        )

        c_akim_adr = st.number_input(
            "AKIM ADRESI",
            value=int(mevcut_ayarlar.get('akim_addr', 70)),
            key="akim_addr_input",
        )
        c_akim_sc = st.number_input(
            "AKIM CARPANI",
            value=float(mevcut_ayarlar.get('akim_scale', 0.1)),
            step=0.01,
            format="%.4f",
            key="akim_scale_input",
            help="Ondalik olarak yazabilirsiniz. Ornek: 0.01",
        )

        c_isi_adr = st.number_input(
            "ISI ADRESI",
            value=int(mevcut_ayarlar.get('isi_addr', 93)),
            key="isi_addr_input",
        )
        c_isi_sc = st.number_input(
            "ISI CARPANI",
            value=float(mevcut_ayarlar.get('isi_scale', 1.0)),
            step=0.01,
            format="%.4f",
            key="isi_scale_input",
            help="Ondalik olarak yazabilirsiniz. Ornek: 0.01 veya 0.001",
        )

        c_uretim_adr = st.number_input(
            "GUNLUK URETIM ADRESI",
            value=int(mevcut_ayarlar.get('uretim_addr', 36)),
            key="uretim_addr_input",
        )
        c_uretim_sc = st.number_input(
            "GUNLUK URETIM CARPANI",
            value=float(mevcut_ayarlar.get('uretim_scale', 1.0)),
            step=0.01,
            format="%.4f",
            key="uretim_scale_input",
            help="Ondalik olarak yazabilirsiniz. Ornek: 1.0 veya 0.1",
        )

    # Sistem sayfasında admin onayı ve sayfa şifresi 1444 onaylandığı için bu ayar butonunu aktifleştirebiliriz.
    submitted = st.form_submit_button("AYARLARI KALICI OLARAK KAYDET", type="primary", width='stretch')

if submitted:
    veritabani.ayar_yaz('target_ip', target_ip, fab_id)
    veritabani.ayar_yaz('target_port', target_port, fab_id)
    veritabani.ayar_yaz('slave_ids', id_input, fab_id)
    veritabani.ayar_yaz('refresh_rate', refresh_rate, fab_id)
    veritabani.ayar_yaz('guc_addr', c_guc_adr, fab_id)
    veritabani.ayar_yaz('guc_scale', c_guc_sc, fab_id)
    veritabani.ayar_yaz('volt_addr', c_volt_adr, fab_id)
    veritabani.ayar_yaz('volt_scale', c_volt_sc, fab_id)
    veritabani.ayar_yaz('akim_addr', c_akim_adr, fab_id)
    veritabani.ayar_yaz('akim_scale', c_akim_sc, fab_id)
    veritabani.ayar_yaz('isi_addr', c_isi_adr, fab_id)
    veritabani.ayar_yaz('isi_scale', c_isi_sc, fab_id)
    veritabani.ayar_yaz('uretim_addr', c_uretim_adr, fab_id)
    veritabani.ayar_yaz('uretim_scale', c_uretim_sc, fab_id)
    veritabani.ayar_yaz('lat', lat_input, fab_id)
    veritabani.ayar_yaz('lon', lon_input, fab_id)

    st.session_state.ayarlar_kaydedildi = True
    kullanici = st.session_state.get('username', 'admin')
    veritabani.audit_log_kaydet(kullanici, "ayar_degistir", f"IP={target_ip}, Port={target_port}, IDs={id_input}", fab_id)
    st.rerun()

# Yenileme suresi ayar
st.markdown("---")
st.header("YENILEME AYARLARI")

if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30

refresh_interval = st.select_slider(
    "OTOMATIK YENILEME SURESI (Arayüz)",
    options=[10, 15, 30, 60, 120, 300, 600, 1800, 3600, 7200],
    value=st.session_state.refresh_interval,
    format_func=lambda x: f"{x} saniye"
)

st.session_state.refresh_interval = refresh_interval

st.caption(f"Panel {refresh_interval} saniyede bir yenilenecek")

st.markdown("---")
st.header("COLLECTOR DURUMU")
_son = veritabani.tum_cihazlarin_son_durumu(fab_id)
if _son:
    try:
        _sz = max(r[1] for r in _son if r[1])
        _dt = pd.to_datetime(_sz)
        _gs = (datetime.now() - _dt).total_seconds()
        if _gs < 120:
            st.success(f"🟢 Collector aktif ({int(_gs)}s önce)")
        else:
            st.warning(f"🟡 Son veri {int(_gs/60)} dk önce")
    except Exception:
        st.error("🔴 Collector verisi yok")
else:
    st.error("🔴 DB'de hiç veri yok")
st.caption("Collector arka planda (Docker) otomatik olarak calismaktadir.")

st.markdown("---")
st.header(" VERI YONETIMI")

# Çift Onay (Double Confirmation) Sistemi
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = False
    
if not st.session_state.confirm_delete:
    if st.button("TUM VERILERI SIL", type="secondary"):
        st.session_state.confirm_delete = True
        st.rerun()
else:
    st.warning("⚠️ DİKKAT: Tüm veriler kalıcı olarak silinecek. Onaylıyor musunuz?")
    col_y, col_n = st.columns(2)
    with col_y:
        if st.button("EVET, SİL", type="primary"):
            if veritabani.db_temizle(fab_id):
                kullanici = st.session_state.get('username', 'admin')
                veritabani.audit_log_kaydet(kullanici, "veri_sil", f"[{fab_id}] Tum olcum verileri silindi", fab_id)
                st.success("Temizlendi!")
                st.session_state.confirm_delete = False
                st.rerun()
    with col_n:
        if st.button("İPTAL"):
            st.session_state.confirm_delete = False
            st.rerun()


st.markdown("<hr>", unsafe_allow_html=True)
section_header("🔑", "API Üretici", "Dış Sistemler İçin Yetkili API Anahtarı Oluşturun")

config_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'api_config.json')
os.makedirs(os.path.dirname(config_path), exist_ok=True)

config_data = {}
if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if "api_key" in loaded and isinstance(loaded["api_key"], str):
                config_data[loaded["api_key"]] = {
                    "allowed_fields": loaded.get("allowed_fields", []),
                    "created_at": "Önceki"
                }
            else:
                config_data = loaded
    except Exception:
        pass

st.subheader("Yeni API Anahtarı Oluştur")
secilen_alanlar = st.multiselect(
    "API ile Dışarıya Açılacak Verileri Seçin",
    ["slave_id", "zaman", "guc", "voltaj", "akim", "sicaklik", "hata_kodu", "durum"],
    default=["slave_id", "zaman", "guc"]
)

if st.button("API Anahtarı Üret"):
    new_key = str(uuid.uuid4()).replace("-", "")[:24]
    config_data[new_key] = {
        "allowed_fields": secilen_alanlar,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)
    
    st.success("API Anahtarı başarıyla üretildi ve kaydedildi!")
    st.code(f"API Key: {new_key}", language="text")
    st.info(f"Örnek Kullanım (Curl):\ncurl -H \"X-API-Key: {new_key}\" http://SUNUCU_IP:8503/api/v1/devices\n\nYetkili alanlar: {', '.join(secilen_alanlar)}")
    st.rerun()

st.markdown("---")
st.subheader("Aktif API'ler")

if config_data:
    for key, info in list(config_data.items()):
        col1, col2, col3 = st.columns([2, 4, 1])
        with col1:
            st.code(key)
        with col2:
            st.write(f"**Tarih:** {info.get('created_at', 'Bilinmiyor')} | **Yetki:** {', '.join(info.get('allowed_fields', []))}")
        with col3:
            if st.button("İptal Et", key=f"del_{key}"):
                del config_data[key]
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, indent=4)
                st.rerun()
else:
    st.info("Henüz üretilmiş aktif bir API anahtarı bulunmuyor.")
