import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani, utils
from styles import inject_glossy_css, section_header, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="Karsilastirma", page_icon="", layout="wide")

if not check_auth():
    st.stop()

inject_glossy_css()
logout_button()

veritabani.init_db()

from veritabani import FABRIKALAR
if 'fabrika_id' not in st.session_state or st.session_state.fabrika_id is None:
    st.warning("Lütfen ana sayfadan bir fabrika seçin.")
    st.stop()
fab_id = st.session_state.fabrika_id

st.title("Cihaz Karsilastirma")
section_header("", "Coklu Cihaz Analizi", "Secilen cihazlarin performansini yan yana karsilastirin")

ayarlar = veritabani.tum_ayarlari_oku(fab_id)
slave_ids, _ = utils.parse_id_list(ayarlar.get('slave_ids', '1,2,3'))

secili = st.multiselect("Karsilastirilacak Cihazlar:", slave_ids, default=slave_ids[:3])
metrik = st.selectbox("Metrik:", ["guc", "voltaj", "akim", "sicaklik"],
    format_func=lambda x: {"guc": "Guc (W)", "voltaj": " Voltaj (V)", "akim": "Akim (A)", "sicaklik": "Sicaklik (C)"}[x])

metrik_birim = {"guc": "W", "voltaj": "V", "akim": "A", "sicaklik": "C"}
metrik_baslik = {"guc": "Guc Karsilastirma", "voltaj": " Voltaj Karlatrma", "akim": "Akim Karsilastirma", "sicaklik": "Sicaklik Karsilastirma"}

# Veritabanından dönen sütunlar (son_verileri_getir)
DB_COLUMNS = ["ts", "guc", "voltaj", "akim", "sicaklik", "hata_kodu", "hata_kodu_109", "hata_kodu_111", "hata_kodu_112", "hata_kodu_114", "hata_kodu_115", "hata_kodu_116", "hata_kodu_117", "hata_kodu_118", "hata_kodu_119", "hata_kodu_120", "hata_kodu_121", "hata_kodu_122"]

if secili:
    colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#a855f7', '#f97316', '#22d3ee', '#e879f9']
    fig = go.Figure()
    ozet_veriler = []

    for i, did in enumerate(secili):
        data = veritabani.son_verileri_getir(did, limit=200, fabrika_id=fab_id)
        if not data:
            continue
        
        # Stun saysna gre uyumlu DataFrame olutur
        num_cols = len(data[0]) if data else 0
        cols = DB_COLUMNS[:num_cols]
        df = pd.DataFrame(data, columns=cols)
        
        # Sayisallastirma (Categorical Plotly Hatalarini Onlem)
        for c in ["guc", "voltaj", "akim", "sicaklik"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        
        df["ts"] = pd.to_datetime(df["ts"], format='mixed', errors='coerce')
        df = df.dropna(subset=['ts']).sort_values(by="ts", ascending=True)
        if metrik not in df.columns:
            continue
        
        fig.add_trace(go.Scatter(
            x=df["ts"], y=df[metrik],
            mode='lines',
            name=f'ID {did}',
            line=dict(color=colors[i % len(colors)], width=2.5)
        ))

        # zet istatistik topla
        ozet_veriler.append({
            "Cihaz": f"ID {did}",
            "Ortalama": round(df[metrik].mean(), 2),
            "Maks": round(df[metrik].max(), 2),
            "Min": round(df[metrik].min(), 2),
        })

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,14,26,0.5)',
        height=450,
        margin=dict(l=10, r=10, t=40, b=10),
        title=dict(text=metrik_baslik[metrik], font=dict(size=14, color='#94a3b8', family='Inter')),
        xaxis=dict(gridcolor='rgba(255,255,255,0.04)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.04)', title=metrik_birim[metrik]),
        font=dict(color='#94a3b8', family='Inter'),
        hovermode='x unified',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8')
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    # zet tablo
    if ozet_veriler:
        st.markdown("<br>", unsafe_allow_html=True)
        section_header("", "Istatistik Ozeti", f"{metrik_baslik[metrik]} - Secili cihazlarin karsilastirmali ozeti")
        
        kpi_items = []
        for oz in ozet_veriler:
            kpi_items.append({
                "value": f"{oz['Ortalama']} {metrik_birim[metrik]}",
                "label": f"{oz['Cihaz']} Ort.",
                "color": colors[ozet_veriler.index(oz) % len(colors)]
            })
        kpi_row(kpi_items)

        st.markdown("<br>", unsafe_allow_html=True)
        df_ozet = pd.DataFrame(ozet_veriler).set_index("Cihaz")
        st.dataframe(df_ozet, use_container_width=True)
else:
    st.markdown("""<div class="glossy-card" style="text-align:center;"><div style="font-size:2rem; margin-bottom:8px;"></div><div style="font-size:1rem; color:#94a3b8; font-family:Inter,sans-serif;">Karsilastirmak icin en az bir cihaz secin.</div></div>""", unsafe_allow_html=True)
