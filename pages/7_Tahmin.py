import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
import utils
from styles import inject_glossy_css, section_header, kpi_row
from auth import check_auth, logout_button

# --- GES FİZİKSEL MODEL PARAMETRELERİ ---
P_MAX = 630.0        # Panel nominal gücü (Watt)
GAMMA = -0.0030      # Sıcaklık katsayısı (-0.30% / C)
NOCT = 45.0          # Nominal hücre sıcaklığı (C)
PANEL_COUNT = 415    # Toplam panel sayısı
INV_EFFICIENCY = 0.985      # Evirici verimi (%98.5)
INV_MAX_AC_OUT = 250000.0   # Evirici maksimum AC çıkış gücü (250 kW)
LATITUDE = 38.5359   # Sistemden Gelen Kesin Koordinat
LONGITUDE = 27.0296  # Sistemden Gelen Kesin Koordinat

def calculate_power_output(temp_amb, ghi):
    """Fiziksel formüllerle sıcaklık ve ışınım verisine göre AC çıkış gücü hesaplar."""
    if ghi <= 0:
        return 0.0
    t_cell = temp_amb + ((NOCT - 20.0) / 800.0) * ghi
    p_panel = P_MAX * (ghi / 1000.0) * (1 + GAMMA * (t_cell - 25.0))
    p_system_ac = p_panel * PANEL_COUNT * INV_EFFICIENCY
    return min(max(0, p_system_ac), INV_MAX_AC_OUT) # Inverter Clipping

st.set_page_config(page_title="URETIM TAHMINI", page_icon="☀️", layout="wide")
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

st.title("FIZIK TABANLI GES URETIM TAHMINI")
section_header("", "ASTRO-TERMODINAMIK MODEL", "CANLI METEOROLOJIK VERILER VE EVIRICI KAPASITESINE GORE URETIM SIMULASYONU")

# Ayarlar Alani
col_settings, col_info = st.columns([1, 2])
with col_settings:
    st.markdown("### Tahmin Ayarları")
    tahmin_periyodu = st.radio("Tahmin Süresi Seçin:", ["Gelecek 24 Saat", "Gelecek 7 Gün"], horizontal=False)

with col_info:
    st.markdown("""
        <div class="glossy-card" style="padding:15px; margin-top:28px;">
            <div style="font-weight:600; color:#38bdf8; margin-bottom:5px;">Model Bilgisi (Sirius 630W + 250kW Evirici)</div>
            <div style="font-size:0.9rem; color:#94a3b8;">
            <b>Algoritma:</b> Açık Hava Termodinamik & P-N Eklem Fiziği<br>
            Bu model, yapay bir veri uydurmak yerine <b>Open-Meteo API</b> üzerinden tesisin bulunduğu kordinatlara (38.5359, 27.0296) ait saatlik doğrudan ve difüz ışınım (W/m²) verilerini çeker. Datasheet üzerinden hücre ısınması (NOCT) ve sıcaklık kaybı (Gamma) hesaplanarak %98.5 verimli 250kW'lık merkezi evirici limitlerine (Clipping) göre gerçekçi AC güç tahmini oluşturur.
            </div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if st.button("Simülasyonu Başlat", type="primary"):
    with st.spinner("Meteoroloji verileri çekiliyor ve fiziksel model hesaplanıyor..."):
        
        # 1. API'den Veri Çekme
        url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&hourly=temperature_2m,direct_radiation,diffuse_radiation&timezone=auto"
        try:
            response = requests.get(url)
            response.raise_for_status()
            weather_data = response.json()
        except Exception as e:
            st.error(f"Hava durumu verisi çekilirken bir hata oluştu: {e}")
            st.stop()

        times = weather_data['hourly']['time']
        temperatures = weather_data['hourly']['temperature_2m']
        direct_rad = weather_data['hourly']['direct_radiation']
        diffuse_rad = weather_data['hourly']['diffuse_radiation']

        # 2. Periyot Ayarı (24 Saat vs 168 Saat)
        limit = 24 if "24 Saat" in tahmin_periyodu else len(times)
        
        gelecek_verisi = []
        for i in range(limit):
            # pd.to_datetime ile parse hatalarını önleyecek standart formatlama
            zaman = pd.to_datetime(times[i]) 
            temp = temperatures[i]
            ghi = direct_rad[i] + diffuse_rad[i]
            
            power_w = calculate_power_output(temp, ghi)
            
            gelecek_verisi.append({
                "ts": zaman,
                "sicaklik": temp,
                "isinım_W_m2": ghi,
                "tahmini_guc_W": power_w,
                "clipping_aktif": power_w >= INV_MAX_AC_OUT
            })

        df_gelecek = pd.DataFrame(gelecek_verisi)
        
        # Toplam KWh Hesabı (Güç değerleri saatlik olduğu için doğrudan W -> kW -> kWh dönüşümü)
        toplam_kwh = df_gelecek['tahmini_guc_W'].sum() / 1000.0
        tepe_guc_kw = df_gelecek['tahmini_guc_W'].max() / 1000.0

        # KPI Kartları
        kpi_row([
            {"value": f"{toplam_kwh:,.1f} kWh", "label": f"BEKLENEN TOPLAM URETIM", "color": "#10b981"},
            {"value": f"{tepe_guc_kw:.1f} kW", "label": "BEKLENEN TEPE GUC (MAKS 250KW)", "color": "#f59e0b"},
            {"value": f"{df_gelecek['sicaklik'].max():.1f} °C", "label": "MAKS. BEKLENEN ORTAM ISISI", "color": "#ef4444"},
        ])
        
        # Eğer kırpma (clipping) varsa kullanıcıyı uyar
        if df_gelecek['clipping_aktif'].any():
            st.warning("⚠️ **Evirici Limiti (Clipping) Tespiti:** Seçilen periyotta güneşlenme çok yüksek olduğu için sistem potansiyeli 250 kW'ı aşıyor. Evirici kapasite limiti devreye girerek gücü 250 kW'ta sabitleyecektir (Grafikteki düz tepe noktaları).")

        st.markdown("<br>", unsafe_allow_html=True)
        
        # 3. Grafik Çizimi
        fig = go.Figure()
        
        # Güç Çizgisi
        fig.add_trace(go.Scatter(
            x=df_gelecek['ts'],
            y=df_gelecek['tahmini_guc_W'] / 1000.0, # Grafikte kW göstermek daha okunaklıdır
            mode='lines',
            name='Tahmini Güç (kW)',
            line=dict(color='#0ea5e9', width=3, shape='spline'),
            fill='tozeroy',
            fillcolor='rgba(14, 165, 233, 0.2)'
        ))
        
        # Evirici Limiti Çizgisi (Görsel referans)
        fig.add_hline(y=INV_MAX_AC_OUT/1000.0, line_dash="dash", line_color="#ef4444", 
                      annotation_text="Evirici Maksimum Limiti (250 kW)", 
                      annotation_position="bottom right")
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(10,14,26,0.5)',
            height=450,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis=dict(gridcolor='rgba(255,255,255,0.04)', title="Zaman"),
            yaxis=dict(gridcolor='rgba(255,255,255,0.04)', title="Güç Çıkışı (kW)"),
            font=dict(color='#94a3b8', family='Inter'),
            hovermode='x unified',
            legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8'))
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.success("Analiz tamamlandı. Model, meteorolojik tahminler ile panel fizyolojisini birleştirerek gerçekçi üretim eğrisini çıkarttı.")