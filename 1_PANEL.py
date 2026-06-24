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
    """Karsilastirma grafigi icin cihaz verisini onbellek ile getirir."""
    return veritabani.son_verileri_getir(dev_id, limit=limit, fabrika_id=fab_id)

# --- YAN MENU ---
# --- ANA EKRAN ---
st.title("GUNES ENERJISI SANTRALI IZLEME")

section_header("", "CANLI FILO DURUMU", "TUM CIHAZLARIN ANLIK DURUM OZETI")

# --- Plotly Grafik Yardmclar ---
def create_plotly_chart(df, column, title, color, unit="", ymax=None, **kwargs):
    fig = go.Figure()
    
    # Glow effect trace
    fig.add_trace(go.Scatter(
        x=df.index, y=df[column],
        mode='lines',
        line=dict(color=color.replace(')', ',0.3)').replace('rgb', 'rgba'), width=8, shape='spline', smoothing=1.3),
        hoverinfo='skip',
        showlegend=False
    ))
    
    # Main line trace with richer fill
    fig.add_trace(go.Scatter(
        x=df.index, y=df[column],
        mode='lines',
        line=dict(color=color, width=3, shape='spline', smoothing=1.3),
        fill='tozeroy',
        fillcolor=color.replace(')', ',0.15)').replace('rgb', 'rgba'),
        hovertemplate=f'%{{x|%H:%M:%S}}<br>{title}: %{{y:.1f}} {unit}<extra></extra>',
        name=title
    ))



    yaxis_params = dict(gridcolor='rgba(0,0,0,0.05)', showgrid=True, zeroline=False, rangemode='tozero')
    if ymax is not None:
        yaxis_params['range'] = [0, ymax]

    fig.update_layout(
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
    )
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




def create_comparison_chart(ids, metric, title, colors, ymax=None):
    fig = go.Figure()
    for i, dev_id in enumerate(ids):
        data = _fetch_device_data(dev_id, fab_id)
        if not data:
            continue
            
        cols = ["timestamp", "guc", "voltaj", "akim", "sicaklik", "hata_kodu", "hata_kodu_109", "hata_kodu_111", "hata_kodu_112", "hata_kodu_114", "hata_kodu_115", "hata_kodu_116", "hata_kodu_117", "hata_kodu_118", "hata_kodu_119", "hata_kodu_120", "hata_kodu_121", "hata_kodu_122", "voltaj_ab", "voltaj_bc", "voltaj_ca", "akim_a", "akim_b", "akim_c"]
        df = pd.DataFrame(data, columns=cols[:len(data[0])] if data else cols)
        if "sicaklik" in df.columns:
            df["sicaklik"] = pd.to_numeric(df["sicaklik"], errors='coerce').apply(utils.normalize_temperature_value)
        if "guc" in df.columns: df["guc"] = pd.to_numeric(df["guc"], errors='coerce')
        if "voltaj" in df.columns: df["voltaj"] = pd.to_numeric(df["voltaj"], errors='coerce')
        if "akim" in df.columns: df["akim"] = pd.to_numeric(df["akim"], errors='coerce')
        df = df[
            ~(
                df["guc"].fillna(0).eq(0)
                & df["voltaj"].fillna(0).eq(0)
                & df["akim"].fillna(0).eq(0)
                & df["sicaklik"].fillna(0).eq(0)
            )
        ]
        if df.empty:
            continue
        
        df["timestamp"] = pd.to_datetime(df["timestamp"], format='mixed', errors='coerce')
        df = df.dropna(subset=['timestamp'])
        df = df.sort_values(by="timestamp", ascending=True)
        


        glow_colors = ['rgba(99, 102, 241, 0.25)', 'rgba(236, 72, 153, 0.25)', 'rgba(16, 185, 129, 0.25)', 'rgba(245, 158, 11, 0.25)', 'rgba(168, 85, 247, 0.25)', 'rgba(249, 115, 22, 0.25)', 'rgba(34, 211, 238, 0.25)', 'rgba(232, 121, 249, 0.25)']
        color = colors[i % len(colors)]
        
        # Glow trace
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df[metric],
            mode='lines',
            line=dict(color=glow_colors[i % len(glow_colors)], width=7, shape='spline', smoothing=1.3),
            hoverinfo='skip',
            showlegend=False
        ))
        
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df[metric],
            mode='lines', name=f'ID {dev_id}',
            line=dict(color=color, width=3, shape='spline', smoothing=1.3),
        ))
        
    yaxis_params = dict(gridcolor='rgba(0,0,0,0.05)', showgrid=True, zeroline=False, rangemode='tozero')
    if ymax is not None:
        yaxis_params['range'] = [0, ymax]

    fig.update_layout(
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(255,255,255,0)',
        margin=dict(l=0, r=0, t=30, b=0),
        height=280,
        title=dict(text=title, font=dict(size=15, color='#1D1D1F', family='Outfit', weight='bold')),
        xaxis=dict(
            showgrid=False,
            showline=True,
            linecolor='rgba(0,0,0,0.1)',
            tickformat="%H:%M",
        ),
        yaxis=yaxis_params,
        font=dict(color='#86868B', family='Outfit'),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='rgba(255,255,255,0.95)',
            bordercolor='rgba(99, 102, 241, 0.35)',
            font=dict(family='Outfit', size=12, color='#1D1D1F'),
            align='left',
        ),
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            bgcolor='rgba(255,255,255,0)', font=dict(color='#86868B')
        ),
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
            zaman_fmt = pd.to_datetime(row[1], format='mixed', errors='coerce')
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

tab_tekli, tab_karsilastirma = st.tabs([" TEKLI CIHAZ", "KARSILASTIRMA"])

with tab_tekli:
    col_sel, col_metrik, col_info = st.columns([1, 1, 2])
    with col_sel:
        selected_id = st.selectbox("CIHAZ SEC:", active_dev_ids, key="tek_cihaz")
    with col_metrik:
        secilen_metrik = st.selectbox("INCELE:", ["GUC", "VOLTAJ", "AKIM", "SICAKLIK"], key="tek_metrik")
    with col_info:
        st.info(" DETAYLI ARIZA KODLARINI GORMEK ICIN SOL MENUDEN ALARMLAR SAYFASINA GIDIN.")

    @st.fragment(run_every=f"{int(st.session_state.refresh_interval)}s")
    def render_tek_cihaz_grafikleri(sel_id, metrik_isim):
        chart_area = st.empty()

        detail_data = veritabani.son_verileri_getir(sel_id, limit=2880, fabrika_id=fab_id)
        if detail_data:
            try:
                cols_det = ["timestamp", "guc", "voltaj", "akim", "sicaklik", "hata_kodu", "hata_kodu_109", "hata_kodu_111", "hata_kodu_112", "hata_kodu_114", "hata_kodu_115", "hata_kodu_116", "hata_kodu_117", "hata_kodu_118", "hata_kodu_119", "hata_kodu_120", "hata_kodu_121", "hata_kodu_122", "voltaj_ab", "voltaj_bc", "voltaj_ca", "akim_a", "akim_b", "akim_c"]
                df_det = pd.DataFrame(detail_data, columns=cols_det[:len(detail_data[0])] if detail_data else cols_det)
                
                df_det["timestamp"] = pd.to_datetime(df_det["timestamp"], format='mixed', errors='coerce')
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
                        fig = create_plotly_chart(df_det, col, title, color, unit, ymax=None, fixed_x_range=fixed_range)
                        fig.update_layout(height=350)
                        
                    chart_area.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
            except Exception as e:
                st.error(f"GRAFIK VERISI ISLENIRKEN HATA: {e}")

    render_tek_cihaz_grafikleri(selected_id, secilen_metrik)

with tab_karsilastirma:
    karsilastirma_ids = st.multiselect("KARSILASTIRILACAK CIHAZLAR:", active_dev_ids, default=active_dev_ids[:3])
    karsilastirma_metrik = st.selectbox("METRIK:", ["guc", "voltaj", "akim", "sicaklik"],
                                         format_func=lambda x: {"guc": " GUC (kW)", "voltaj": " VOLTAJ (V)",
                                                                  "akim": "AKIM (A)", "sicaklik": "SICAKLIK (C)"}[x])

    @st.fragment(run_every=f"{int(st.session_state.refresh_interval)}s")
    def render_karsilastirma_grafik(k_ids, k_metrik):
        if k_ids:
            colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#a855f7', '#f97316', '#22d3ee', '#e879f9']
            metrik_labels = {"guc": " GUC KARSILASTIRMA (kW)", "voltaj": " VOLTAJ KARSILASTIRMA (V)",
                             "akim": " AKIM KARSILASTIRMA (A)", "sicaklik": " SICAKLIK KARSILASTIRMA (C)"}
            
            st.plotly_chart(
                create_comparison_chart(k_ids, k_metrik, metrik_labels[k_metrik], colors),
                width='stretch', config={"displayModeBar": False}
            )

    render_karsilastirma_grafik(karsilastirma_ids, karsilastirma_metrik)


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
st.markdown('<div style="margin-top: 50px;"></div>', unsafe_allow_html=True)
st.subheader('SİSTEM VE CİHAZ AYARLARI')
with st.container():
    # Fabrika değiştirme butonu
    st.caption(f"{fab_info['ikon']} {fab_info['ad'].upper()}")
    if st.button("🔄 FABRIKA DEGISTIR", width='stretch'):
        st.session_state.fabrika_id = None
        st.rerun()
    current_user = get_current_user()
    user_role = get_user_role(current_user)

    st.divider()
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

        if user_role == "admin":
            submitted = st.form_submit_button("AYARLARI KALICI OLARAK KAYDET", type="primary", width='stretch')
        else:
            submitted = st.form_submit_button("AYARLARI KALICI OLARAK KAYDET", disabled=True, width='stretch')
            st.warning("Ayarları kaydetmek için 'admin' yetkisi gereklidir.")

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
        "OTOMATIK YENILEME SURESI",
        options=[10, 15, 30, 60, 120, 300, 600, 1800, 3600, 7200],
        value=st.session_state.refresh_interval,
        format_func=lambda x: f"{x} saniye"
    )

    st.session_state.refresh_interval = refresh_interval

    st.caption(f"Panel {refresh_interval} saniyede bir yenilenecek")

    st.markdown("---")
    st.header("COLLECTOR DURUMU")
    # Collector'ın son veriyi ne zaman yazdığını DB'den kontrol et
    _son = _fetch_summary_data(fab_id)
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

    if user_role == "admin":
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

