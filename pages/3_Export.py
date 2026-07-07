# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani, utils
from styles import render_top_nav, inject_glossy_css, section_header, solar_table
from auth import check_auth, logout_button

st.set_page_config(page_title="VERI AKTARIMI", page_icon="", layout="wide")
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

st.title("VERI AKTARIMI")
section_header("", "VERI AKTARIMI", "CSV FORMATINDA VERI INDIRIN")

ayarlar = veritabani.tum_ayarlari_oku(fab_id)
slave_ids, _ = utils.parse_id_list(ayarlar.get('slave_ids', '1,2,3'))
col1, col2, col3, col4 = st.columns(4)
with col1:
    baslangic = st.date_input("Baslangic:", datetime.now() - timedelta(days=7))
with col2:
    bitis = st.date_input("Bitis:", datetime.now())
with col3:
    secilen = st.selectbox("Cihaz:", ["Tum"] + ["ID " + str(s) for s in slave_ids])
with col4:
    cozunurluk = st.selectbox("Cozunurluk:", ["Saniyelik Ham Veri (Son 30 Gun)", "Saatlik Ozet (Tum Zamanlar)"])

if st.button("Verileri Getir", type="primary"):
    sid = None if secilen == "Tum" else int(secilen.split()[-1])
    tum = []
    
    # DateTime nesnelerine çevir
    b_dt = datetime.combine(baslangic, datetime.min.time())
    bit_dt = datetime.combine(bitis, datetime.max.time())
    
    for s in (slave_ids if sid is None else [sid]):
        if "Saatlik" in cozunurluk:
            # Saatlik özet tablosunu (Continuous Aggregate) kullan
            for r in veritabani.saatlik_ozet_getir(s, b_dt, bit_dt, fab_id):
                # r format: ts, guc, voltaj, akim, sicaklik, modbus_uretim
                tum.append({"slave_id": s, "zaman": r[0], "guc": r[1], "voltaj": r[2], "akim": r[3], "sicaklik": r[4], "uretim": r[5]})
        else:
            # Ham veriyi kullan
            for r in veritabani.son_verileri_getir(s, limit=50000, fabrika_id=fab_id):
                tum.append({"slave_id": s, "zaman": r[0], "guc": r[1], "voltaj": r[2], "akim": r[3], "sicaklik": r[4], "hata_kodu": r[5]})
    
    if tum:
        df = pd.DataFrame(tum)
        df["zaman"] = pd.to_datetime(df["zaman"])
        if "Saatlik" not in cozunurluk:
            df = df[(df["zaman"] >= b_dt) & (df["zaman"] <= bit_dt)]
            
        if len(df) > 0:
            st.success(" " + str(len(df)) + " kayit bulundu.")
            # Ilk 200 satiri solar_table ile goster
            preview = df.head(200)
            solar_table(
                preview.values.tolist(),
                headers=list(preview.columns),
            )
            if len(df) > 200:
                st.caption(f"Tum {len(df)} kayit CSV'de mevcut, onizleme ilk 200 satirla sinirlidir.")
            st.download_button("CSV Indir", df.to_csv(index=False).encode('utf-8-sig'), "export.csv", "text/csv")
        else:
            st.info("Aralikta veri yok.")
    else:
        st.warning("Veri yok.")
