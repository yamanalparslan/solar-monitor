# pyrefly: ignore [missing-import]
import streamlit as st
import time
import pandas as pd
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
import plotly.graph_objects as go
import veritabani
import utils
from styles import render_top_nav, inject_glossy_css, section_header, status_bar, kpi_row, solar_table, toast
from auth import check_auth, logout_button, get_current_user, get_user_role
from crm_embed import inject_embed_mode, is_embed_mode
import weather
from plotly.subplots import make_subplots

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="SOLAR MONITOR",
    layout="wide",
    page_icon="",
    initial_sidebar_state="collapsed"
)

# --- AUTH KONTROLU ---
if not check_auth():
    st.stop()

# DB Baslat
veritabani.init_db()

# --- GLOSSY CSS TEMA ---
inject_glossy_css()
render_top_nav()


# --- CRM EMBED MODU ---
inject_embed_mode(hide_sidebar=False)

# --- FABRİKA SEÇİMİ ---
from veritabani import FABRIKALAR, VARSAYILAN_FABRIKA

if 'fabrika_id' not in st.session_state:
    st.session_state.fabrika_id = None

if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30
# Fabrika seçilmemişse seçim ekranı göster
if st.session_state.fabrika_id is None:
    st.markdown("""
    <style>
    .stApp {
        background: url('https://sp.sanayigazetesi.com.tr/wp-content/uploads/2025/03/Resim-2025-03-30T160718.008.webp') no-repeat center center fixed !important;
        background-size: cover !important;
    }
    .factory-select-container {
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        padding: 40px 60px;
        border-radius: 24px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        text-align: center;
    }
    </style>
    <div style="display:flex;justify-content:center;align-items:center;min-height:60vh;">
        <div class="factory-select-container">
            <h1 style="font-size:3rem;font-weight:800;
                background:linear-gradient(135deg,#0071E3,#32ADE6);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                margin-bottom:8px;">☀️ SOLAR MONITOR</h1>
            <p style="color:#515154;font-size:1.1rem;margin-bottom:32px;font-weight:500;">IZLEMEK ISTEDIGINIZ FABRIKAYI SECIN</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔧 MEKANIK FABRIKA", width='stretch', type="primary"):
                st.session_state.fabrika_id = "mekanik"
                st.rerun()
        with c2:
            if st.button("🏭 URETIM FABRIKASI", width='stretch', type="primary"):
                st.session_state.fabrika_id = "uretim"
                st.rerun()
    st.stop()

fab_id = st.session_state.fabrika_id
fab_info = FABRIKALAR[fab_id]

# --- YARDIMCI ---
if 'ayarlar_kaydedildi' not in st.session_state:
    st.session_state.ayarlar_kaydedildi = False

# --- YARDIMCI FONKSIYONLAR ---
@st.cache_data(ttl=timedelta(seconds=2), show_spinner=False)
def _fetch_summary_data(fab_id: str):
    """Aynı saniye içerisinde defalarca db okumasını engellemek için cache'lenir."""
    return veritabani.tum_cihazlarin_son_durumu(fab_id)

@st.cache_data(ttl=timedelta(seconds=30), show_spinner=False)
def _fetch_device_data(dev_id: int, fab_id: str, limit: int = 2880):
    """Tekil cihaz grafigi icin cihaz verisini onbellek ile getirir."""
    return veritabani.son_verileri_getir(dev_id, limit=limit, fabrika_id=fab_id)

# --- YAN MENU ---
# --- ANA EKRAN ---
st.title("GUNES ENERJISI SANTRALI IZLEME")

try:
    lat_val = float(veritabani.ayar_oku('lat', '38.4237', fab_id))
    lon_val = float(veritabani.ayar_oku('lon', '27.1428', fab_id))
    current_weather = weather.get_current_weather(lat_val, lon_val)
    
    # Son alarmı al
    latest_alarms = veritabani.gecmis_alarmlari_getir(fab_id, limit=1)
    alarm_html = ""
    if latest_alarms:
        import models
        alrm = latest_alarms[0]
        a_slave = alrm[0]
        a_bas = alrm[1]
        a_reg = alrm[3]
        a_kod = alrm[4]
        a_durum = alrm[5] # 'AKTIF' or 'DUZELDI'
        
        fault_map = getattr(models, f"FAULT_MAP_{a_reg}", {})
        faults = models.get_active_faults_with_severity(a_kod, fault_map)
        hata_aciklama = faults[0][1] if faults else "Bilinmeyen Hata"
        
        try:
            dt = datetime.strptime(str(a_bas).split('.')[0], "%Y-%m-%d %H:%M:%S")
            zaman_str = dt.strftime("%d.%m %H:%M")
        except:
            zaman_str = str(a_bas)[:16]
            
        if a_durum == "AKTIF":
            bg_color = "rgba(254,226,226,0.9)"
            border_color = "rgba(239,68,68,0.2)"
            title_color = "#991b1b"
            text_color = "#7f1d1d"
            time_color = "#b91c1c"
            durum_renk = "#ef4444"
            durum_ikon = "🚨"
        else:
            bg_color = "rgba(209,250,229,0.9)"
            border_color = "rgba(16,185,129,0.2)"
            title_color = "#065f46"
            text_color = "#064e3b"
            time_color = "#047857"
            durum_renk = "#10b981"
            durum_ikon = "✅"
            
        alarm_html = f"""
            <div style="background: {bg_color}; backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 15px 25px; border-radius: 16px; margin-bottom: 24px; display: inline-flex; align-items: center; gap: 20px; border: 1px solid {border_color}; box-shadow: 0 4px 15px {border_color.replace('0.2', '0.1')};">
                <div style="font-size: 2.5rem; line-height: 1;">{durum_ikon}</div>
                <div>
                    <div style="font-size: 0.75rem; color: {title_color}; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 4px;">SON ALARM DURUMU</div>
                    <div style="font-size: 1.1rem; color: {text_color}; font-weight: 500;">
                        <b>ID: {a_slave}</b> - {hata_aciklama} &nbsp;&nbsp;|&nbsp;&nbsp;
                        <span style="color:{time_color};">Zaman: {zaman_str}</span> &nbsp;&nbsp;|&nbsp;&nbsp;
                        <span style="color:{durum_renk}; font-weight: 700;">Durum: {a_durum}</span>
                    </div>
                </div>
            </div>
        """

    weather_html = ""
    if current_weather:
        weather_html = f"""
            <div style="background: rgba(255,255,255,0.7); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 15px 25px; border-radius: 16px; margin-bottom: 24px; display: inline-flex; align-items: center; gap: 20px; border: 1px solid rgba(0,0,0,0.05); box-shadow: 0 4px 15px rgba(0,0,0,0.03);">
                <div style="font-size: 2.5rem; line-height: 1;">{current_weather['icon']}</div>
                <div>
                    <div style="font-size: 0.75rem; color: #86868B; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 4px;">ANLIK HAVA DURUMU</div>
                    <div style="font-size: 1.1rem; color: #1D1D1F; font-weight: 500;">
                        {current_weather['desc']}, <b>{current_weather['temp']}°C</b> &nbsp;&nbsp;|&nbsp;&nbsp; 
                        <span style="color:#6366f1;">☁️ Bulutluluk: %{current_weather['cloud_cover']}</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
                        <span style="color:#f59e0b;">☀️ Işınım (DNI): {current_weather['irradiance']} W/m²</span>
                    </div>
                </div>
            </div>
        """
        
    if weather_html or alarm_html:
        st.markdown(f"""
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                {weather_html}
                {alarm_html}
            </div>
        """, unsafe_allow_html=True)
except Exception as e:
    print(f"[WIDGET ERROR] {e}")

section_header("", "CANLI FILO DURUMU", "TUM CIHAZLARIN ANLIK DURUM OZETI")

# --- Plotly Grafik Yardmclar ---
def create_plotly_chart(df, column, title, color, unit="", ymax=None, irradiance_df=None, **kwargs):
    # Her zaman subplot altyapısı ile oluştur ki add_trace(..., secondary_y=False) hata vermesin.
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Glow effect trace
    fig.add_trace(go.Scatter(
        x=df.index, y=df[column],
        mode='lines',
        line=dict(color=color.replace(')', ',0.3)').replace('rgb', 'rgba'), width=8, shape='spline', smoothing=1.3),
        hoverinfo='skip',
        showlegend=False
    ), secondary_y=False)
    
    # Main line trace with richer fill
    fig.add_trace(go.Scatter(
        x=df.index, y=df[column],
        mode='lines',
        line=dict(color=color, width=3, shape='spline', smoothing=1.3),
        fill='tozeroy',
        fillcolor=color.replace(')', ',0.15)').replace('rgb', 'rgba'),
        hovertemplate=f'%{{x|%H:%M:%S}}<br>{title}: %{{y:.1f}} {unit}<extra></extra>',
        name=title
    ), secondary_y=False)

    if irradiance_df is not None and not irradiance_df.empty:
        fig.add_trace(go.Scatter(
            x=irradiance_df["timestamp"], y=irradiance_df["irradiance"],
            mode='lines',
            line=dict(color='rgba(245, 158, 11, 0.6)', width=2, dash='dot', shape='spline'),
            fill='tozeroy',
            fillcolor='rgba(245, 158, 11, 0.05)',
            name='Güneş Işınımı (W/m²)',
            hovertemplate='%{x|%H:%M}<br>Işınım: %{y:.1f} W/m²<extra></extra>'
        ), secondary_y=True)

    yaxis_params = dict(gridcolor='rgba(0,0,0,0.05)', showgrid=True, zeroline=False, rangemode='tozero', title=unit)
    if ymax is not None:
        yaxis_params['range'] = [0, ymax]

    layout_update = dict(
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(255,255,255,0)',
        margin=dict(l=0, r=0, t=30, b=0),
        height=220,
        title=dict(text=title, font=dict(size=14, color='#1D1D1F', family='Outfit', weight='bold')),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickformat="%H:%M",
            showline=True,
            linecolor='rgba(0,0,0,0.1)',
            range=kwargs.get('fixed_x_range', None)
        ),
        yaxis=yaxis_params,
        font=dict(color='#86868B', family='Outfit'),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='rgba(255,255,255,0.95)',
            bordercolor=color.replace(')', ',0.5)').replace('rgb', 'rgba'),
            font=dict(family='Outfit', size=13, color='#1D1D1F'),
            align='left',
        ),
        showlegend=True if irradiance_df is not None else False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_layout(**layout_update)
    if irradiance_df is not None and not irradiance_df.empty:
        fig.update_yaxes(title_text="Işınım (W/m²)", showgrid=False, secondary_y=True)
        
    return fig

def create_multi_plotly_chart(df, columns, names, colors, title, unit="", ymax=None, **kwargs):
    fig = go.Figure()
    
    glow_colors = ['rgba(99, 102, 241, 0.25)', 'rgba(236, 72, 153, 0.25)', 'rgba(16, 185, 129, 0.25)', 'rgba(245, 158, 11, 0.25)', 'rgba(168, 85, 247, 0.25)', 'rgba(249, 115, 22, 0.25)', 'rgba(34, 211, 238, 0.25)', 'rgba(232, 121, 249, 0.25)']
    
    for i, (col, name, color) in enumerate(zip(columns, names, colors)):
        # Glow effect trace
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col],
            mode='lines',
            line=dict(color=glow_colors[i % len(glow_colors)], width=7, shape='spline', smoothing=1.3),
            hoverinfo='skip',
            showlegend=False
        ))
        
        # Main trace
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col],
            mode='lines',
            line=dict(color=color, width=3, shape='spline', smoothing=1.3),
            fill='tozeroy',
            fillcolor='rgba(255,255,255,0)', # Use transparent for multi to not clutter
            hovertemplate=f'%{{x|%H:%M:%S}}<br>{name}: %{{y:.1f}} {unit}<extra></extra>',
            name=name
        ))

    yaxis_params = dict(gridcolor='rgba(0,0,0,0.05)', showgrid=True, zeroline=False, rangemode='tozero')
    if ymax is not None:
        yaxis_params['range'] = [0, ymax]

    fig.update_layout(
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(255,255,255,0)',
        margin=dict(l=0, r=0, t=30, b=0),
        height=kwargs.get('height', 220),
        title=dict(text=title, font=dict(size=14, color='#1D1D1F', family='Outfit', weight='bold')),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickformat="%H:%M",
            showline=True,
            linecolor='rgba(0,0,0,0.1)',
            range=kwargs.get('fixed_x_range', None)
        ),
        yaxis=yaxis_params,
        font=dict(color='#86868B', family='Outfit'),
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig






# --- Cihaz Saglk Kartlar ---
import collector_async
cfg = collector_async.load_config(fab_id)
active_dev_ids = []
for device in cfg["target_devices"]:
    for s_id in device["slave_ids"]:
        active_dev_ids.append(s_id)

@st.fragment(run_every=f"{int(st.session_state.refresh_interval)}s")
def render_summary_section():
    # 1. TABLO VE KART GUNCELLEME
    summary_data = _fetch_summary_data(fab_id)
    if summary_data:
        num_devices = len(summary_data)
        cols_per_row = min(num_devices, 4)
        gauge_cols = st.columns(cols_per_row)

        from models import CihazDurumu
        for idx, row in enumerate(summary_data):
            col_idx = idx % cols_per_row
            
            # Make sure the row has enough elements to unpack into CihazDurumu
            padded_row = list(row) + [0] * max(0, 19 - len(row))
            cd = CihazDurumu(*padded_row[:19])
            
            dev_id = cd.slave_id
            dev_guc = cd.guc if cd.guc is not None else 0
            dev_volt = round(float(cd.voltaj), 1) if cd.voltaj is not None else 0
            dev_akim = round(float(cd.akim), 2) if cd.akim is not None else 0
            dev_temp = round(utils.normalize_temperature_value(cd.sicaklik), 1) if cd.sicaklik is not None else 0
            dev_hata = cd.has_critical_or_major_error
            alarm_count = cd.active_fault_count

            durum_renk = cd.durum_renk
            durum_text = cd.durum_text

            with gauge_cols[col_idx]:
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=dev_guc,
                    title={'text': f"ID:{dev_id}", 'font': {'size': 14, 'color': '#94a3b8', 'family': 'Inter'}},
                    number={'suffix': 'KW', 'font': {'size': 22, 'color': durum_renk, 'family': 'Inter'}},
                    gauge={
                        'axis': {'range': [0, 250], 'tickcolor': '#334155', 'tickfont': {'color': '#475569'}},
                        'bar': {'color': durum_renk},
                        'bgcolor': 'rgba(15, 23, 42, 0.6)',
                        'borderwidth': 1,
                        'bordercolor': 'rgba(255, 255, 255, 0.06)',
                        'steps': [
                            {'range': [0, max(dev_guc * 1.5, 250) * 0.3], 'color': 'rgba(15, 23, 42, 0.4)'},
                            {'range': [max(dev_guc * 1.5, 250) * 0.3, max(dev_guc * 1.5, 250) * 0.7], 'color': 'rgba(30, 41, 59, 0.4)'},
                            {'range': [max(dev_guc * 1.5, 250) * 0.7, max(dev_guc * 1.5, 250)], 'color': 'rgba(99, 102, 241, 0.08)'},
                        ],
                    },
                ))
                fig_gauge.update_layout(paper_bgcolor='rgba(255,255,255,0)', plot_bgcolor='rgba(255,255,255,0)', height=185, margin=dict(l=20, r=20, t=40, b=10), font=dict(color='#86868B', family='Outfit'))
                st.plotly_chart(fig_gauge, width='stretch', key=f"gauge_dyn_{dev_id}")

                st.markdown(
                    f'<div style="text-align:center; font-size:0.85rem; color:#86868B; margin-top:-10px; font-family:Outfit,sans-serif;">'
                    f'{dev_volt:.1f}V &nbsp; {dev_akim:.2f}A &nbsp; {dev_temp:.1f}°C'
                    f' &nbsp; | &nbsp; <span style="color:{durum_renk};font-weight:700;">{durum_text}</span>'
                    f'</div>', unsafe_allow_html=True
                )

        # TABLO: st.dataframe yerine solar_table (hover row highlight)
        tablo_rows = []
        for row in summary_data:
            zaman_fmt = pd.to_datetime(row[1], errors='coerce')
            zaman_fmt = zaman_fmt.strftime('%H:%M:%S') if pd.notna(zaman_fmt) else "-"
            isi_val = utils.normalize_temperature_value(float(row[5] or 0))
            tablo_rows.append([
                row[0],          # ID
                zaman_fmt,
                f"{float(row[2] or 0):.1f}",
                f"{float(row[3] or 0):.1f}",
                f"{float(row[4] or 0):.2f}",
                f"{isi_val:.1f}",
            ])
        solar_table(
            tablo_rows,
            headers=["ID", "SON ZAMAN", "GUC (kW)", "VOLTAJ (V)", "AKIM (A)", "ISI (C)"],
        )

        st.markdown("<br>", unsafe_allow_html=True)
        
        # Son 7 günlük üretim tablosu
        from datetime import datetime, timedelta
        bugun = datetime.now()
        
        gunler_headers = ["INVERTER"]
        for i in range(6, -1, -1):
            gunler_headers.append((bugun - timedelta(days=i)).strftime('%d %b'))
            
        tablo_verileri = []
        
        # Her inverter icin ayri satir
        for dev_id in active_dev_ids:
            row = [f"ID {dev_id}"]
            for i in range(6, -1, -1):
                t = bugun - timedelta(days=i)
                gun_str = t.strftime('%Y-%m-%d')
                ur = veritabani.gunluk_uretim_hesapla(gun_str, slave_id=dev_id, fabrika_id=fab_id)
                val = 0
                if ur:
                    val = ur.get('modbus_uretim', 0) if ur.get('modbus_uretim', 0) > 0 else ur.get('uretim_kwh', 0)
                row.append(f"{val:.1f}")
            tablo_verileri.append(row)
            
        # Toplam satiri
        toplam_row = ["TOPLAM"]
        for i in range(6, -1, -1):
            t = bugun - timedelta(days=i)
            gun_str = t.strftime('%Y-%m-%d')
            ur = veritabani.gunluk_uretim_hesapla(gun_str, slave_id=None, fabrika_id=fab_id)
            val = 0
            if ur:
                val = ur.get('modbus_uretim', 0) if ur.get('modbus_uretim', 0) > 0 else ur.get('uretim_kwh', 0)
            toplam_row.append(f"{val:.1f}")
            
        if len(active_dev_ids) > 1:
            tablo_verileri.append(toplam_row)
            
        st.markdown("<div style='text-align: center; color: #1D1D1F; margin-bottom: 10px; font-size: 14px; font-weight: 800; font-family: Outfit;'>SON 7 GÜN ÜRETİM ÖZETİ (kWh)</div>", unsafe_allow_html=True)
        solar_table(tablo_verileri, headers=gunler_headers)

render_summary_section()

# --- GRAFIK SECIMI ---
st.markdown("---")
st.subheader(" TEKLI CIHAZ INCELEMESI")

@st.fragment(run_every=f"{int(st.session_state.refresh_interval)}s")
def render_tek_cihaz_grafikleri(sel_id, metrik_isim):
    chart_area = st.empty()

    detail_data = veritabani.son_verileri_getir(sel_id, limit=2880, fabrika_id=fab_id)
    if detail_data:
        try:
            cols_det = ["timestamp", "guc", "voltaj", "akim", "sicaklik", "hata_kodu", "hata_kodu_109", "hata_kodu_111", "hata_kodu_112", "hata_kodu_114", "hata_kodu_115", "hata_kodu_116", "hata_kodu_117", "hata_kodu_118", "hata_kodu_119", "hata_kodu_120", "hata_kodu_121", "hata_kodu_122", "voltaj_ab", "voltaj_bc", "voltaj_ca", "akim_a", "akim_b", "akim_c"]
            df_det = pd.DataFrame(detail_data, columns=cols_det[:len(detail_data[0])] if detail_data else cols_det)
            
            df_det["timestamp"] = pd.to_datetime(df_det["timestamp"], errors='coerce')
            df_det["guc"] = pd.to_numeric(df_det["guc"], errors='coerce')
            df_det["voltaj"] = pd.to_numeric(df_det["voltaj"], errors='coerce')
            
            if "voltaj_ab" in df_det.columns:
                df_det["voltaj_ab"] = pd.to_numeric(df_det["voltaj_ab"], errors='coerce')
                df_det["voltaj_bc"] = pd.to_numeric(df_det["voltaj_bc"], errors='coerce')
                df_det["voltaj_ca"] = pd.to_numeric(df_det["voltaj_ca"], errors='coerce')
            else:
                df_det["voltaj_ab"] = df_det["voltaj"]
                df_det["voltaj_bc"] = df_det["voltaj"]
                df_det["voltaj_ca"] = df_det["voltaj"]
                
            df_det["akim"] = pd.to_numeric(df_det["akim"], errors='coerce')
            if "akim_a" in df_det.columns:
                df_det["akim_a"] = pd.to_numeric(df_det["akim_a"], errors='coerce')
                df_det["akim_b"] = pd.to_numeric(df_det["akim_b"], errors='coerce')
                df_det["akim_c"] = pd.to_numeric(df_det["akim_c"], errors='coerce')
            else:
                df_det["akim_a"] = df_det["akim"]
                df_det["akim_b"] = df_det["akim"]
                df_det["akim_c"] = df_det["akim"]
            df_det["sicaklik"] = pd.to_numeric(df_det["sicaklik"], errors='coerce').apply(utils.normalize_temperature_value)
            df_det = df_det[
                ~(
                    df_det["guc"].fillna(0).eq(0)
                    & df_det["voltaj"].fillna(0).eq(0)
                    & df_det["akim"].fillna(0).eq(0)
                    & df_det["sicaklik"].fillna(0).eq(0)
                )
            ]
            if not df_det.empty:
                df_det = df_det.dropna(subset=['timestamp']).sort_values("timestamp", ascending=True)
                df_det = df_det.set_index("timestamp")

                from datetime import datetime, time
                bugun = datetime.now().date()
                start_time = datetime.combine(bugun, time.min)
                end_time = datetime.combine(bugun, time.max)
                fixed_range = [start_time, end_time]

                if metrik_isim == "VOLTAJ":
                    # 3 Fazli voltaj grafigi cizelim
                    fig = create_multi_plotly_chart(
                        df_det, 
                        columns=["voltaj_ab", "voltaj_bc", "voltaj_ca"],
                        names=["Faz AB", "Faz BC", "Faz CA"],
                        colors=["rgb(239,68,68)", "rgb(34,197,94)", "rgb(59,130,246)"], # Kirmizi, Yesil, Mavi
                        title=" VOLTAJ (3 FAZ)",
                        unit="V",
                        ymax=None,
                        fixed_x_range=fixed_range,
                        height=350
                    )
                elif metrik_isim == "AKIM":
                    # 3 Fazli akim grafigi cizelim
                    fig = create_multi_plotly_chart(
                        df_det, 
                        columns=["akim_a", "akim_b", "akim_c"],
                        names=["Faz A", "Faz B", "Faz C"],
                        colors=["rgb(245,158,11)", "rgb(16,185,129)", "rgb(99,102,241)"], # Turuncu, Yesil, Indigo
                        title=" AKIM (3 FAZ)",
                        unit="A",
                        ymax=None,
                        fixed_x_range=fixed_range,
                        height=350
                    )
                else:
                    metrik_map = {
                        "GUC": ("guc", " GUC", "rgb(255,215,0)", "kW", None),
                        "SICAKLIK": ("sicaklik", "SICAKLIK", "rgb(239,83,80)", "C", None)
                    }
                    col, title, color, unit, height = metrik_map[metrik_isim]
                    
                    irradiance_df = None
                    if metrik_isim == "GUC":
                        lat_val = float(veritabani.ayar_oku('lat', '38.4237', fab_id))
                        lon_val = float(veritabani.ayar_oku('lon', '27.1428', fab_id))
                        irradiance_df = weather.get_historical_irradiance(lat_val, lon_val, past_days=2)
                        
                    fig = create_plotly_chart(df_det, col, title, color, unit, ymax=None, fixed_x_range=fixed_range, irradiance_df=irradiance_df)
                    fig.update_layout(height=350)
                    
                chart_area.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        except Exception as e:
            st.error(f"GRAFIK VERISI ISLENIRKEN HATA: {e}")

col_sel, col_metrik, col_info = st.columns([1, 1, 2])
with col_sel:
    selected_id = st.selectbox("CIHAZ SEC:", active_dev_ids, key="tek_cihaz")
with col_metrik:
    secilen_metrik = st.selectbox("INCELE:", ["GUC", "VOLTAJ", "AKIM", "SICAKLIK"], key="tek_metrik")
with col_info:
    st.info(" DETAYLI ARIZA KODLARINI GORMEK ICIN SOL MENUDEN ALARMLAR SAYFASINA GIDIN.")

render_tek_cihaz_grafikleri(selected_id, secilen_metrik)


@st.fragment(run_every=f"{int(st.session_state.refresh_interval)}s")
def render_status_bar():
    summary_data = _fetch_summary_data(fab_id)
    collector_aktif = False
    veri_bos_gorunuyor = False
    gecen_sure = 0
    
    if summary_data:
        from datetime import datetime
        try:
            son_zaman = max(row[1] for row in summary_data if row[1])
            son_dt = pd.to_datetime(son_zaman) if son_zaman else None
            if son_dt:
                gecen_sure = (datetime.now() - son_dt).total_seconds()
                collector_aktif = gecen_sure < 120
            veri_bos_gorunuyor = all(
                (float(row[2] or 0) == 0.0)
                and (float(row[3] or 0) == 0.0)
                and (float(row[4] or 0) == 0.0)
                for row in summary_data
            )
        except Exception:
            pass

    if collector_aktif and veri_bos_gorunuyor:
        status_bar(False,
            f'⚠️ <b>Collector aktif ama veri bos gorunuyor</b> — '
            f'Son kayit {int(gecen_sure)}s once. Modbus adres/function ayari kontrol edilmeli.')
    elif collector_aktif:
        status_bar(True,
            f'✅ <b>Canlı Veri Akışı</b> — DB her '
            f'{st.session_state.refresh_interval}s yenileniyor | '
            f'Collector son veri: {int(gecen_sure)}s önce')
    else:
        status_bar(False,
            '⚠️ <b>Collector Bağlantısı Yok</b> — '
            'Sistem arka planda (Docker) veri çekmeyi durdurmuş olabilir. '
            'Panel DB\'deki mevcut verileri gösteriyor.')

render_status_bar()

