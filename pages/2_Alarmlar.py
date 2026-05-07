import streamlit as st
import time
import sys, os
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
from models import FAULT_MAP_107, FAULT_MAP_109, FAULT_MAP_111, FAULT_MAP_112, FAULT_MAP_114, FAULT_MAP_115, FAULT_MAP_116, FAULT_MAP_117, FAULT_MAP_118, FAULT_MAP_119, FAULT_MAP_120, FAULT_MAP_121, FAULT_MAP_122
from styles import inject_glossy_css, section_header, alarm_card, badge, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="AKTIF ALARMLAR", page_icon="", layout="wide")
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

st.title("AKTIF DONANIM ARIZALARI")
section_header("", "CANLI ALARM PANELI", "CIHAZLARDAN GELEN HATA KODLARININ (REGISTER 107 & 111) DETAYLI DOKUMU")

col_r, col_t = st.columns([1, 3])
with col_r:
    auto_refresh = st.toggle("Otomatik Yenileme (10s)", value=False)
with col_t:
    if st.button("Simdi Yenile"):
        st.rerun()
    st.caption('Son guncelleme: ' + datetime.now().strftime('%H:%M:%S'))


def hata_bit_coz(kod, fault_map):
    hatalar = []
    for bit in range(32):
        if (kod >> bit) & 1:
            aciklama = fault_map.get(bit, "Bilinmeyen Hata (Bit " + str(bit) + ")")
            hatalar.append((bit, aciklama))
    return hatalar


durumlar = veritabani.tum_cihazlarin_son_durumu(fab_id)

if not durumlar:
    st.warning("Henuz veri yok.")
else:
    hata_sayisi = 0
    temiz_sayisi = 0

    for row in durumlar:
        dev_id = row[0]
        h107 = row[6] if len(row) > 6 and row[6] else 0
        h109 = row[7] if len(row) > 7 and row[7] else 0
        h111 = row[8] if len(row) > 8 and row[8] else 0
        h112 = row[9] if len(row) > 9 and row[9] else 0
        h114 = row[10] if len(row) > 10 and row[10] else 0
        h115 = row[11] if len(row) > 11 and row[11] else 0
        h116 = row[12] if len(row) > 12 and row[12] else 0
        h117 = row[13] if len(row) > 13 and row[13] else 0
        h118 = row[14] if len(row) > 14 and row[14] else 0
        h119 = row[15] if len(row) > 15 and row[15] else 0
        h120 = row[16] if len(row) > 16 and row[16] else 0
        h121 = row[17] if len(row) > 17 and row[17] else 0
        h122 = row[18] if len(row) > 18 and row[18] else 0
        has_error = (h107 != 0) or (h109 != 0) or (h111 != 0) or (h112 != 0) or (h114 != 0) or (h115 != 0) or (h116 != 0) or (h117 != 0) or (h118 != 0) or (h119 != 0) or (h120 != 0) or (h121 != 0) or (h122 != 0)

        if has_error:
            hata_sayisi += 1
            hatalar_107 = hata_bit_coz(h107, FAULT_MAP_107)
            hatalar_109 = hata_bit_coz(h109, FAULT_MAP_109)
            hatalar_111 = hata_bit_coz(h111, FAULT_MAP_111)
            hatalar_112 = hata_bit_coz(h112, FAULT_MAP_112)
            hatalar_114 = hata_bit_coz(h114, FAULT_MAP_114)
            hatalar_115 = hata_bit_coz(h115, FAULT_MAP_115)
            hatalar_116 = hata_bit_coz(h116, FAULT_MAP_116)
            hatalar_117 = hata_bit_coz(h117, FAULT_MAP_117)
            hatalar_118 = hata_bit_coz(h118, FAULT_MAP_118)
            hatalar_119 = hata_bit_coz(h119, FAULT_MAP_119)
            hatalar_120 = hata_bit_coz(h120, FAULT_MAP_120)
            hatalar_121 = hata_bit_coz(h121, FAULT_MAP_121)
            hatalar_122 = hata_bit_coz(h122, FAULT_MAP_122)

            parts = []
            parts.append('<div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">')
            parts.append('<span style="font-size:1.3rem;"></span>')
            parts.append('<span style="font-size:1.1rem; font-weight:700; color:#fca5a5; font-family:Inter,sans-serif;">ID: ' + str(dev_id) + '</span>')
            parts.append(badge("ARIZA", "danger"))
            parts.append('</div>')

            if hatalar_107:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 107 Hatalari:</div>')
                for bit, aciklama in hatalar_107:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_109:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 109 Hatalari:</div>')
                for bit, aciklama in hatalar_109:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_111:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 111 Hatalari:</div>')
                for bit, aciklama in hatalar_111:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_112:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 112 Hatalari:</div>')
                for bit, aciklama in hatalar_112:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_114:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 114 Hatalari:</div>')
                for bit, aciklama in hatalar_114:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_115:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 115 Hatalari:</div>')
                for bit, aciklama in hatalar_115:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_116:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 116 Hatalari:</div>')
                for bit, aciklama in hatalar_116:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_117:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 117 Hatalari:</div>')
                for bit, aciklama in hatalar_117:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_118:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 118 Hatalari:</div>')
                for bit, aciklama in hatalar_118:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_119:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 119 Hatalari:</div>')
                for bit, aciklama in hatalar_119:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_120:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 120 Hatalari:</div>')
                for bit, aciklama in hatalar_120:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_121:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 121 Hatalari:</div>')
                for bit, aciklama in hatalar_121:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_122:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 122 Hatalari:</div>')
                for bit, aciklama in hatalar_122:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;"> Bit ' + str(bit) + ': ' + aciklama + '</div>')

            parts.append('<div style="margin-top:8px; font-size:0.75rem; color:#64748b; font-family:Inter,sans-serif;">Hex: R107=0x' + format(h107, "08X") + ' | R109=0x' + format(h109, "08X") + ' | R111=0x' + format(h111, "04X") + ' | R112=0x' + format(h112, "08X") + ' | R114=0x' + format(h114, "04X") + ' | R115=0x' + format(h115, "04X") + ' | R116=0x' + format(h116, "04X") + ' | R117=0x' + format(h117, "04X") + ' | R118=0x' + format(h118, "04X") + ' | R119=0x' + format(h119, "04X") + ' | R120=0x' + format(h120, "04X") + ' | R121=0x' + format(h121, "04X") + ' | R122=0x' + format(h122, "04X") + '</div>')
            alarm_card(dev_id, True, ''.join(parts))
        else:
            temiz_sayisi += 1
            content = '<div style="display:flex; align-items:center; gap:12px;"><span style="font-size:1.3rem;"></span><span style="font-size:1.05rem; font-weight:600; color:#6ee7b7; font-family:Inter,sans-serif;">ID: ' + str(dev_id) + '  Sistem Stabil</span>' + badge("OK", "success") + '</div>'
            alarm_card(dev_id, False, content)

    st.markdown("---")
    kpi_row([
        {"value": str(len(durumlar)), "label": "TOPLAM CIHAZ", "color": "#6366f1"},
        {"value": str(hata_sayisi), "label": "ARIZALI", "color": "#ef4444"},
        {"value": str(temiz_sayisi), "label": "SAGLIKLI", "color": "#10b981"},
    ])

    if hata_sayisi == 0:
        st.markdown('''
        <div class="glossy-card" style="text-align:center; margin-top:20px;">
            <div style="font-size:2rem; margin-bottom:8px;"></div>
            <div style="font-size:1.1rem; font-weight:600; color:#6ee7b7; font-family:Inter,sans-serif;">
                Harika! Sistemde su an hic aktif ariza yok.
            </div>
        </div>
        ''', unsafe_allow_html=True)

if auto_refresh:
    time.sleep(10)
    st.rerun()
