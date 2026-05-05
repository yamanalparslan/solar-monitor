import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os

# Yolu ayarlama ve zel modlleri ie aktarma
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
import utils
from styles import inject_glossy_css, section_header, kpi_row
from auth import check_auth, logout_button

# --- GVENL HATA HESAPLAMA FONKSYONU ---
def guvenli_hata_hesapla(hata_degeri):
    """Veritabanndan gelen hata dizgesini (rn: '1/2') gvenli bir ekilde toplar."""
    try:
        # Bo, None veya NaN durumlarn kontrol et
        if pd.isna(hata_degeri) or not str(hata_degeri).strip():
            return 0
        
        # Gelen veriyi string'e evirip '/' iaretinden bl
        parcalar = str(hata_degeri).split('/')
        
        # Beklenen "1/2" formatndaysa
        if len(parcalar) == 2:
            return int(parcalar[0].strip()) + int(parcalar[1].strip())
            
        # Eer yanllkla "/" olmadan sadece tek bir say ("5") gelirse
        return int(str(hata_degeri).strip())
        
    except (ValueError, AttributeError, TypeError):
        # Herhangi bir ayrtrma veya dntrme hatas olursa uygulamay kertme, 0 say
        return 0
# ------------------------------------------

# --- SAYFA AYARLARI VE KONTROLLER ---
st.set_page_config(page_title="Gunluk Raporlar", page_icon="", layout="wide")
inject_glossy_css()

if not check_auth():
    st.stop()

logout_button()
veritabani.init_db()

# --- Fabrika Kontrolü ---
from veritabani import FABRIKALAR
if 'fabrika_id' not in st.session_state or st.session_state.fabrika_id is None:
    st.warning("Lütfen ana sayfadan bir fabrika seçin.")
    st.stop()
fab_id = st.session_state.fabrika_id
fab_info = FABRIKALAR[fab_id]

# --- OTOMATIK YENILEME AYARI ---
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30


# --- BALIK ---
st.title("Gunluk Performans ve Uretim Raporu")
section_header("", "Uretim Analizi", "Secilen tarihe gore tum cihazlarin uretim ve verimlilik ozeti")

# --- AYARLARI OKUMA ---
ayarlar = veritabani.tum_ayarlari_oku(fab_id)
isi_scale = float(ayarlar.get('isi_scale', '1.0'))

import collector_async
cfg = collector_async.load_config(fab_id)
slave_ids = []
for device in cfg["target_devices"]:
    for s_id in device["slave_ids"]:
        slave_ids.append(s_id)

@st.fragment(run_every=f"{int(st.session_state.refresh_interval)}s")
def goster_rapor():
    # --- TARH SEM ---
    col_date, col_time, col_btn = st.columns([1, 1, 1])
    with col_date:
        secilen_tarih = st.date_input("Rapor Tarihi:", datetime.now())
    with col_time:
        st.caption(f"Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}")
    with col_btn:
        if st.button("Şimdi Yenile", use_container_width=True):
            st.rerun()
    tarih_str = secilen_tarih.strftime('%Y-%m-%d')

    # --- VER TOPLAMA ---
    rapor_listesi = []
    for s_id in slave_ids:
        uretim = veritabani.gunluk_uretim_hesapla(tarih_str, slave_id=s_id, fabrika_id=fab_id)
        istatistik = veritabani.tarih_araliginda_ortalamalar(tarih_str, tarih_str, slave_id=s_id, fabrika_id=fab_id)
        hatalar = veritabani.hata_sayilarini_getir(tarih_str, tarih_str, slave_id=s_id, fabrika_id=fab_id)
        
        if istatistik and istatistik.get('toplam_olcum', 0) > 0:
            hata_str = "0/0"
            if hatalar:
                hata_str = str(hatalar['hata_107_sayisi']) + " / " + str(hatalar['hata_111_sayisi'])
                
            rapor_listesi.append({
                "Cihaz ID": s_id,
                "Uretim (kWh)": uretim['uretim_kwh'] if uretim else 0,
                "Ort. Guc (W)": round(istatistik['ort_guc'], 2),
                "Maks. Guc (W)": istatistik['max_guc'],
                "Ort. Voltaj (V)": round(istatistik['ort_voltaj'], 1),
                "Ort. Sicaklik (C)": round(istatistik['ort_sicaklik'], 1) if istatistik.get('toplam_olcum', 0) > 0 else 0,
                "Hata (107/111)": hata_str,
                "Calisma (Saat)": uretim['calisma_suresi_saat'] if uretim else 0
            })

    # --- TABLO VE GRAFK GSTERM ---
    if rapor_listesi:
        df_rapor = pd.DataFrame(rapor_listesi)
        
        # Yeni ve gvenli hesaplama metodu ile toplamlar alma
        total_kwh = df_rapor["Uretim (kWh)"].sum()
        total_errors = df_rapor["Hata (107/111)"].apply(guvenli_hata_hesapla).sum()
        
        # Eksik olan kpi_row yaps tamamland
        kpi_row([
            {"value": str(round(total_kwh, 2)) + " kWh", "label": "Toplam Uretim", "color": "#f59e0b"},
            {"value": str(len(df_rapor)), "label": "Aktif Cihaz", "color": "#10b981"},
            {"value": str(total_errors), "label": "Toplam Hata", "color": "#ef4444"},
        ])
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(
            df_rapor.set_index("Cihaz ID"),
            column_config={
                "Uretim (kWh)": st.column_config.NumberColumn(format="%.2f kWh"),
                "Ort. Guc (W)": st.column_config.NumberColumn(format="%.2f W"),
                "Maks. Guc (W)": st.column_config.NumberColumn(format="%.2f W"),
                "Ort. Voltaj (V)": st.column_config.NumberColumn(format="%.1f V"),
                "Ort. Sicaklik (C)": st.column_config.NumberColumn(format="%.1f °C"),
                "Calisma (Saat)": st.column_config.NumberColumn(format="%.1f sa"),
            },
            use_container_width=True,
        )
        
        # CSV ndirme
        csv = df_rapor.to_csv(index=False).encode('utf-8-sig')
        st.download_button("CSV Indir", csv, "gunluk_rapor_" + tarih_str + ".csv", "text/csv")
        
    else:
        # Veri yoksa gsterilecek bo ekran
        st.markdown(
            '<div class="glossy-card" style="text-align:center;">'
            '<div style="font-size:2rem; margin-bottom:8px;"></div>'
            '<div style="font-size:1rem; color:#94a3b8; font-family:Inter,sans-serif;">Secilen tarihte veri bulunamadi.</div>'
            '</div>', 
            unsafe_allow_html=True
        )

goster_rapor()