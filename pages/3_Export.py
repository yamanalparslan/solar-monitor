import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani, utils
from styles import inject_glossy_css, section_header
from auth import check_auth, logout_button

st.set_page_config(page_title="VERI AKTARIMI", page_icon="", layout="wide")
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

st.title("VERI AKTARIMI")
section_header("", "VERI AKTARIMI", "CSV FORMATINDA VERI INDIRIN")

ayarlar = veritabani.tum_ayarlari_oku(fab_id)
slave_ids, _ = utils.parse_id_list(ayarlar.get('slave_ids', '1,2,3'))
col1, col2, col3 = st.columns(3)
with col1:
    baslangic = st.date_input("Baslangic:", datetime.now() - timedelta(days=7))
with col2:
    bitis = st.date_input("Bitis:", datetime.now())
with col3:
    secilen = st.selectbox("Cihaz:", ["Tum"] + ["ID " + str(s) for s in slave_ids])
if st.button("Verileri Getir", type="primary"):
    sid = None if secilen == "Tum" else int(secilen.split()[-1])
    tum = []
    for s in (slave_ids if sid is None else [sid]):
        for r in veritabani.son_verileri_getir(s, limit=50000, fabrika_id=fab_id):
            tum.append({"slave_id": s, "zaman": r[0], "guc": r[1], "voltaj": r[2], "akim": r[3], "sicaklik": r[4], "hata_kodu": r[5]})
    if tum:
        df = pd.DataFrame(tum)
        df["zaman"] = pd.to_datetime(df["zaman"])
        df = df[(df["zaman"].dt.date >= baslangic) & (df["zaman"].dt.date <= bitis)]
        if len(df) > 0:
            st.success(" " + str(len(df)) + " kayit bulundu.")
            st.dataframe(df, width='stretch')
            st.download_button("CSV Indir", df.to_csv(index=False).encode('utf-8-sig'), "export.csv", "text/csv")
        else:
            st.info("Aralikta veri yok.")
    else:
        st.warning("Veri yok.")
