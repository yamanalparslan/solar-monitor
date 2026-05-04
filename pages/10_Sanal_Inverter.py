import streamlit as st
import sys, os, time, socket, subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from styles import inject_glossy_css, section_header, badge
from auth import check_auth, logout_button

st.set_page_config(page_title="Sanal Inverter", page_icon="", layout="wide")
inject_glossy_css()
if not check_auth():
    st.stop()
logout_button()

st.title("Sanal Inverter (Simulator)")
section_header("", "Sistem Simulasyonu", "Fiziksel panellere baglanmadan test verileri uretir")

def is_simulator_running():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', 5020)) == 0
    except:
        return False

# Session state initialization
if 'sim_process' not in st.session_state:
    st.session_state.sim_process = None
if 'collector_process' not in st.session_state:
    st.session_state.collector_process = None

# Durum Bar
is_running = is_simulator_running()

col_status, col_action = st.columns([2, 1])

with col_status:
    if is_running:
        st.markdown(f'<div class="glossy-card" style="border-left: 4px solid #10b981; padding:20px;">'
                    f'<div style="font-size:1.4rem; color:#10b981; font-weight:700;">SIMULATOR AKTIF</div>'
                    f'<div style="color:#94a3b8; margin-top:8px;">Sanal inverter arka planda basariyla calisiyor ve 5020 portundan Modbus TCP verisi yayinliyor. Collector bu portu okuyabilir.</div>'
                    f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="glossy-card" style="border-left: 4px solid #ef4444; padding:20px;">'
                    f'<div style="font-size:1.4rem; color:#ef4444; font-weight:700;">SIMULATOR KAPALI</div>'
                    f'<div style="color:#94a3b8; margin-top:8px;">Sistemde anlik olarak calisan bir sanal inverter tespit edilemedi. Test verisi akisi durmus durumda.</div>'
                    f'</div>', unsafe_allow_html=True)

with col_action:
    st.markdown("<br>", unsafe_allow_html=True)
    if not is_running:
        if st.button("Simulator Baslat", type="primary", use_container_width=True):
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sanal_inverter.py'))
            try:
                if sys.platform == "win32":
                    st.session_state.sim_process = subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path), creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    st.session_state.sim_process = subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                st.success("Baslatildi! Baglanti kuruluyor...")
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"Baslatilamadi: {e}")
    else:
        if st.button("Simulator Durdur", type="secondary", use_container_width=True):
            if st.session_state.sim_process:
                st.session_state.sim_process.terminate()
                st.session_state.sim_process = None
            else:
                # Eger bu oturumdan bagimsiz baslatildiysa socket / port uzerinden kill yapilmali
                # Bu ornekte sadece uygulama icinden baslatilanlar durdurulabilir.
                st.warning("Bu islem manuel baslatildigi icin buradan durdurulamaz. Terminalden kapatin.")
            time.sleep(1)
            st.rerun()

# --- COLLECTOR BOLUMU ---
def is_collector_running():
    return st.session_state.collector_process is not None and st.session_state.collector_process.poll() is None

st.markdown("<hr style='border-color: rgba(255,255,255,0.05);'>", unsafe_allow_html=True)
st.subheader("Veri Toplayici (Collector)")

col_status_c, col_action_c = st.columns([2, 1])

with col_status_c:
    if is_collector_running():
        st.markdown(f'<div class="glossy-card" style="border-left: 4px solid #10b981; padding:20px;">'
                    f'<div style="font-size:1.4rem; color:#10b981; font-weight:700;">COLLECTOR AKTIF</div>'
                    f'<div style="color:#94a3b8; margin-top:8px;">Arka planda (Asenkron) Modbus verileri cekilerek SQLite veritabanina yaziliyor.</div>'
                    f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="glossy-card" style="border-left: 4px solid #ef4444; padding:20px;">'
                    f'<div style="font-size:1.4rem; color:#ef4444; font-weight:700;">COLLECTOR KAPALI</div>'
                    f'<div style="color:#94a3b8; margin-top:8px;">Veri toplayici calismiyor. Dashboard guncellenmeyecektir.</div>'
                    f'</div>', unsafe_allow_html=True)

with col_action_c:
    st.markdown("<br>", unsafe_allow_html=True)
    if not is_collector_running():
        if st.button("Collector Baslat", type="primary", use_container_width=True, key="start_coll"):
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'collector_async.py'))
            try:
                if sys.platform == "win32":
                    st.session_state.collector_process = subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path), creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    st.session_state.collector_process = subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                st.success("Collector Baslatildi!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Hata: {e}")
    else:
        if st.button("Collector Durdur", type="secondary", use_container_width=True, key="stop_coll"):
            st.session_state.collector_process.terminate()
            st.session_state.collector_process = None
            time.sleep(1)
            st.rerun()

st.markdown("<br>", unsafe_allow_html=True)
section_header("", "Simulasyon Detaylari")

st.markdown("""
<div class="glossy-card" style="padding: 20px;">
    <h4>Simulator Parametreleri</h4>
    <p style="color:#cbd5e1;">Arka planda calisan <code>sanal_inverter.py</code> scripti, fiziksel cihaz eksikligini kapatmak icin su varsayilan degerleri simule eder:</p>
    <ul>
        <li><b>Baglanti Modu:</b> Asenkron Modbus TCP (Port: 5020)</li>
        <li><b>Simule Edilen Cihazlar (Slave ID):</b> 1, 2, 3</li>
        <li><b>Davranis Oruntusu:</b> Gunduz gercekci gun isigi, sicakliga bagli voltaj dususu</li>
        <li><b>Hata Enjeksiyonu:</b> Rastgele Hata Kodu 107 ve Hata Kodu 111 simulasyonlari</li>
        <li><b>Dongu Hizi:</b> Her 10 dakika, sistem icin sanal 24 saati temsil eder ve hizlandirilmis uretim yapar.</li>
    </ul>
    Eger collector verileri okuyamiyorsa <i>Panel -> Ayarlar</i> sekmesinden IP adresini yapilandirdiginizdan emin olun (Docker icin <code>solar-monitor</code>).
</div>
""", unsafe_allow_html=True)
