import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani, utils
from styles import render_top_nav, inject_glossy_css, section_header, kpi_row, solar_table
from auth import check_auth, logout_button

st.set_page_config(page_title="KARSILASTIRMA", page_icon="", layout="wide")

if not check_auth():
    st.stop()

inject_glossy_css()
render_top_nav()


veritabani.init_db()

from veritabani import FABRIKALAR
if 'fabrika_id' not in st.session_state or st.session_state.fabrika_id is None:
    st.warning("Lütfen ana sayfadan bir fabrika seçin.")
    st.stop()
fab_id = st.session_state.fabrika_id

st.title("CIHAZ KARSILASTIRMA")
section_header("", "COKLU CIHAZ ANALIZI", "SECILEN CIHAZLARIN PERFORMANSINI YAN YANA KARSILASTIRIN")

ayarlar = veritabani.tum_ayarlari_oku(fab_id)
slave_ids, _ = utils.parse_id_list(ayarlar.get('slave_ids', '1,2,3'))

tum_cihazlar = []
default_secim = []

for f_id, f_info in FABRIKALAR.items():
    f_ayarlar = veritabani.tum_ayarlari_oku(f_id)
    f_slave_ids, _ = utils.parse_id_list(f_ayarlar.get('slave_ids', '1,2,3'))
    for s_id in f_slave_ids:
        isim = f"{f_info.get('isim', f_id)} - Cihaz {s_id}"
        cihaz_obj = {"fab_id": f_id, "slave_id": s_id, "isim": isim}
        tum_cihazlar.append(cihaz_obj)
        if f_id == fab_id and s_id in slave_ids[:3]:
            default_secim.append(cihaz_obj)

secili = st.multiselect(
    "Karsilastirilacak Cihazlar:", 
    options=tum_cihazlar, 
    default=default_secim,
    format_func=lambda x: x["isim"]
)

metrik = st.selectbox("Metrik:", ["guc", "voltaj", "akim", "sicaklik"],
    format_func=lambda x: {"guc": "Guc (kW)", "voltaj": " Voltaj (V)", "akim": "Akim (A)", "sicaklik": "Sicaklik (C)"}[x])

metrik_birim = {"guc": "kW", "voltaj": "V", "akim": "A", "sicaklik": "C"}
metrik_baslik = {"guc": "Guc Karsilastirma", "voltaj": " Voltaj Karlatrma", "akim": "Akim Karsilastirma", "sicaklik": "Sicaklik Karsilastirma"}

if secili:
    colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#a855f7', '#f97316', '#22d3ee', '#e879f9']
    glow_colors = ['rgba(99, 102, 241, 0.25)', 'rgba(236, 72, 153, 0.25)', 'rgba(16, 185, 129, 0.25)', 'rgba(245, 158, 11, 0.25)', 'rgba(168, 85, 247, 0.25)', 'rgba(249, 115, 22, 0.25)', 'rgba(34, 211, 238, 0.25)', 'rgba(232, 121, 249, 0.25)']
    fig = go.Figure()
    ozet_veriler = []

    for i, secim in enumerate(secili):
        f_id = secim["fab_id"]
        did = secim["slave_id"]
        
        # Yeni ve hizli downsampling fonksiyonunu kullaniyoruz
        data = veritabani.karsilastirma_verisi_getir(did, limit=2880, fabrika_id=f_id)
        if not data:
            continue
        
        # karsilastirma_verisi_getir sadece 5 kolon doner: zaman_dk, guc, voltaj, akim, sicaklik
        cols = ["ts", "guc", "voltaj", "akim", "sicaklik"]
        df = pd.DataFrame(data, columns=cols)
        
        # Sayisallastirma (Categorical Plotly Hatalarini Onlem)
        for c in ["guc", "voltaj", "akim", "sicaklik"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        
        df = df[~(df["guc"].fillna(0).eq(0) & df["voltaj"].fillna(0).eq(0) & df["akim"].fillna(0).eq(0))]
        df["ts"] = pd.to_datetime(df["ts"], errors='coerce')
        df = df.dropna(subset=["ts"]).sort_values(by="ts", ascending=True)
        if metrik not in df.columns:
            continue
        
        # Glow effect trace
        fig.add_trace(go.Scatter(
            x=df['ts'], y=df[metrik],
            mode='lines',
            line=dict(color=glow_colors[i % len(glow_colors)], width=7, shape='spline', smoothing=1.3),
            hoverinfo='skip',
            showlegend=False
        ))
        
        # Main trace
        fig.add_trace(go.Scatter(
            x=df['ts'], y=df[metrik],
            mode='lines',
            name=secim["isim"],
            line=dict(color=colors[i % len(colors)], width=3, shape='spline', smoothing=1.3)
        ))

        ozet_veriler.append({
            "Cihaz": secim["isim"],
            "Ortalama": round(df[metrik].mean(), 2),
            "Maks": round(df[metrik].max(), 2),
            "Min": round(df[metrik].min(), 2),
        })

    fig.update_layout(
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(255,255,255,0)',
        height=450,
        margin=dict(l=10, r=10, t=45, b=10),
        title=dict(text=metrik_baslik[metrik], font=dict(size=15, color='#1D1D1F', family='Outfit', weight='bold')),
        xaxis=dict(gridcolor='rgba(0,0,0,0.05)', showgrid=False, showline=True, linecolor='rgba(0,0,0,0.1)'),
        yaxis=dict(gridcolor='rgba(0,0,0,0.05)', showgrid=True, title=metrik_birim[metrik]),
        font=dict(color='#86868B', family='Outfit'),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='rgba(255,255,255,0.95)',
            bordercolor='rgba(99, 102, 241, 0.35)',
            font=dict(family='Outfit', size=13, color='#1D1D1F'),
            align='left',
        ),
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            bgcolor='rgba(255,255,255,0)', font=dict(color='#86868B')
        ),
    )
    st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})

    # zet tablo
    if ozet_veriler:
        st.markdown("<br>", unsafe_allow_html=True)
        section_header("", "ISTATISTIK OZETI", f"{metrik_baslik[metrik]} - SECILI CIHAZLARIN KARSILASTIRMALI OZETI")
        
        kpi_items = []
        for oz in ozet_veriler:
            kpi_items.append({
                "value": f"{oz['Ortalama']} {metrik_birim[metrik]}",
                "label": f"{oz['Cihaz']} Ort.",
                "color": colors[ozet_veriler.index(oz) % len(colors)]
            })
        kpi_row(kpi_items)

        st.markdown("<br>", unsafe_allow_html=True)
        solar_table(
            [[oz['Cihaz'], str(oz['Ortalama']), str(oz['Maks']), str(oz['Min'])] for oz in ozet_veriler],
            headers=["CIHAZ", f"ORTALAMA ({metrik_birim[metrik]})", f"MAKS ({metrik_birim[metrik]})", f"MIN ({metrik_birim[metrik]})"],
        )
else:
    st.markdown("""<div class="glossy-card" style="text-align:center;"><div style="font-size:2rem; margin-bottom:8px;"></div><div style="font-size:1rem; color:#86868B; font-family:Outfit,sans-serif;">Karsilastirmak icin en az bir cihaz secin.</div></div>""", unsafe_allow_html=True)
