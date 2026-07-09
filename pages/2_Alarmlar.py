# pyrefly: ignore [missing-import]
import streamlit as st
import time
import sys, os
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
from models import FAULT_MAP_107, FAULT_MAP_109, FAULT_MAP_111, FAULT_MAP_112, FAULT_MAP_114, FAULT_MAP_115, FAULT_MAP_116, FAULT_MAP_117, FAULT_MAP_118, FAULT_MAP_119, FAULT_MAP_120, FAULT_MAP_121, FAULT_MAP_122, determine_severity
from styles import render_top_nav, inject_glossy_css, section_header, alarm_card, badge, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="AKTIF ALARMLAR", page_icon="", layout="wide")
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

st.title("DONANIM ARIZALARI VE ALARMLAR")

def hata_bit_coz(kod, fault_map):
    hatalar = []
    gorulen_aciklamalar = set()
    for bit in range(32):
        if (kod >> bit) & 1:
            aciklama = fault_map.get(bit, "")
            if aciklama and aciklama.lower() != "spare":
                if aciklama not in gorulen_aciklamalar:
                    sev = determine_severity(aciklama)
                    hatalar.append((bit, aciklama, sev))
                    gorulen_aciklamalar.add(aciklama)
    return hatalar

tab_aktif, tab_gecmis = st.tabs(["🔴 AKTIF ALARMLAR", "📜 ALARM GECMISI"])

with tab_aktif:
    section_header("", "CANLI ALARM PANELI", "CIHAZLARDAN GELEN HATA KODLARININ DETAYLI DOKUMU")
    
    col_r, col_t = st.columns([1, 3])
    with col_r:
        auto_refresh = st.toggle("Otomatik Yenileme (10s)", value=False)
    with col_t:
        if st.button("Simdi Yenile"):
            st.rerun()
        st.caption('Son guncelleme: ' + datetime.now().strftime('%H:%M:%S'))

    durumlar = veritabani.tum_cihazlarin_son_durumu(fab_id)

    if not durumlar:
        st.warning("Henuz veri yok.")
    else:
        hata_sayisi = 0
        temiz_sayisi = 0

        from models import CihazDurumu
        for row in durumlar:
            # DB'den donen row'u CihazDurumu ile eslestir (eksik sutun gelme ihtimaline karsi)
            padded_row = list(row) + [0] * max(0, 19 - len(row))
            cd = CihazDurumu(*padded_row[:19])
            
            dev_id = cd.slave_id
            guc = cd.guc
            voltaj = cd.voltaj
            
            h107 = cd.hata_kodu or 0
            h109 = cd.hata_kodu_109 or 0
            h111 = cd.hata_kodu_111 or 0
            h112 = cd.hata_kodu_112 or 0
            h114 = cd.hata_kodu_114 or 0
            h115 = cd.hata_kodu_115 or 0
            h116 = cd.hata_kodu_116 or 0
            h117 = cd.hata_kodu_117 or 0
            h118 = cd.hata_kodu_118 or 0
            h119 = cd.hata_kodu_119 or 0
            h120 = cd.hata_kodu_120 or 0
            h121 = cd.hata_kodu_121 or 0
            h122 = cd.hata_kodu_122 or 0
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

            has_critical_or_major = False
            has_warning = False
            
            for h_list in [hatalar_107, hatalar_109, hatalar_111, hatalar_112, hatalar_114, hatalar_115, hatalar_116, hatalar_117, hatalar_118, hatalar_119, hatalar_120, hatalar_121, hatalar_122]:
                if h_list:
                    for bit, aciklama, sev in h_list:
                        if sev in ["CRITICAL", "MAJOR"]:
                            has_critical_or_major = True
                        else:
                            has_warning = True

            is_arizali = False
            is_uyku = False
            
            if has_critical_or_major:
                is_arizali = True
            elif voltaj <= 5 and guc <= 0:
                is_uyku = True
            elif guc > 0:
                is_arizali = False
            else:
                is_arizali = True

            has_any_error_to_show = bool(has_critical_or_major or has_warning)

            if is_arizali:
                hata_sayisi += 1
                card_status_html = f'<div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;"><span style="font-size:1.1rem; font-weight:700; color:#FF3B30; font-family:Outfit,sans-serif;">ID: {dev_id}</span>{badge("ARIZA", "danger")}</div>'
                card_status = "error"
            elif is_uyku:
                # uyku_sayisi += 1 (Eger KPI eklenecekse buraya eklenebilir, simdilik temiz sayalim veya sadece ayri gosterelim)
                # Sadece arizalari sayiyoruz gerisi temiz ya da uyku
                temiz_sayisi += 1
                card_status_html = f'<div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;"><span style="font-size:1.1rem; font-weight:700; color:#0071E3; font-family:Outfit,sans-serif;">ID: {dev_id}  Sistem Uykuda</span>{badge("UYKU", "info")}</div>'
                card_status = "sleep"
            else:
                temiz_sayisi += 1
                card_status_html = f'<div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;"><span style="font-size:1.1rem; font-weight:700; color:#34C759; font-family:Outfit,sans-serif;">ID: {dev_id}  Sistem Stabil</span>{badge("OK", "success")}</div>'
                card_status = "ok"

            if has_any_error_to_show:
                parts = [card_status_html]

                for h_list, reg_name in [
                    (hatalar_107, "107"), (hatalar_109, "109"), (hatalar_111, "111"),
                    (hatalar_112, "112"), (hatalar_114, "114"), (hatalar_115, "115"),
                    (hatalar_116, "116"), (hatalar_117, "117"), (hatalar_118, "118"),
                    (hatalar_119, "119"), (hatalar_120, "120"), (hatalar_121, "121"),
                    (hatalar_122, "122")
                ]:
                    if h_list:
                        parts.append(f'<div style="margin:8px 0 4px 0; font-weight:600; color:#86868B; font-family:Outfit,sans-serif;">Register {reg_name} Hatalari:</div>')
                        for bit, aciklama, sev in h_list:
                            color = "#fca5a5" if sev == "CRITICAL" else ("#fb923c" if sev == "MAJOR" else "#fde047")
                            bg_color = "rgba(239, 68, 68, 0.15)" if sev == "CRITICAL" else ("rgba(249, 115, 22, 0.15)" if sev == "MAJOR" else "rgba(234, 179, 8, 0.15)")
                            b_color = "rgba(239, 68, 68, 0.25)" if sev == "CRITICAL" else ("rgba(249, 115, 22, 0.25)" if sev == "MAJOR" else "rgba(234, 179, 8, 0.25)")
                            badge_html = f'<span style="background:{bg_color}; border:1px solid {b_color}; color:{color}; padding:2px 8px; border-radius:12px; font-size:0.7rem; font-weight:bold; margin-left:8px;">{sev}</span>'
                            parts.append(f'<div style="padding:3px 0 3px 16px; color:{color}; font-size:0.9rem; font-family:Outfit,sans-serif;"> Bit {bit}: {aciklama} {badge_html}</div>')

                parts.append('<div style="margin-top:8px; font-size:0.75rem; color:#64748b; font-family:Outfit,sans-serif;">Hex: R107=0x' + format(h107, "08X") + ' | R109=0x' + format(h109, "08X") + ' | R111=0x' + format(h111, "04X") + ' | R112=0x' + format(h112, "08X") + ' | R114=0x' + format(h114, "04X") + ' | R115=0x' + format(h115, "04X") + ' | R116=0x' + format(h116, "04X") + ' | R117=0x' + format(h117, "04X") + ' | R118=0x' + format(h118, "04X") + ' | R119=0x' + format(h119, "04X") + ' | R120=0x' + format(h120, "04X") + ' | R121=0x' + format(h121, "04X") + ' | R122=0x' + format(h122, "04X") + '</div>')
                alarm_card(dev_id, card_status, ''.join(parts))
            else:
                if is_uyku:
                    content = f'<div style="display:flex; align-items:center; gap:12px;"><span style="font-size:1.3rem;"></span><span style="font-size:1.05rem; font-weight:600; color:#0071E3; font-family:Outfit,sans-serif;">ID: {dev_id}  Sistem Uykuda</span>{badge("UYKU", "info")}</div>'
                    alarm_card(dev_id, "sleep", content)
                else:
                    content = f'<div style="display:flex; align-items:center; gap:12px;"><span style="font-size:1.3rem;"></span><span style="font-size:1.05rem; font-weight:600; color:#34C759; font-family:Outfit,sans-serif;">ID: {dev_id}  Sistem Stabil</span>{badge("OK", "success")}</div>'
                    alarm_card(dev_id, "ok", content)

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
                <div style="font-size:1.1rem; font-weight:600; color:#34C759; font-family:Outfit,sans-serif;">
                    Harika! Sistemde su an hic aktif ariza yok.
                </div>
            </div>
            ''', unsafe_allow_html=True)

    if auto_refresh:
        time.sleep(10)
        st.rerun()


with tab_gecmis:
    section_header("", "GECMIS ALARMLAR", "KAYDEDILMIS SON 100 ALARM KAYDI")
    gecmis = veritabani.gecmis_alarmlari_getir(fab_id, limit=100)
    
    if not gecmis:
        st.info("Sistemde kayitli gecmis alarm bulunmamaktadir.")
    else:
        import pandas as pd
        tablo_verisi = []
        for row in gecmis:
            dev_id = row[0]
            baslangic = row[1]
            bitis = row[2]
            reg = row[3]
            kod = row[4]
            durum = row[5]
            
            f_map = {}
            if reg == 107: f_map = FAULT_MAP_107
            elif reg == 109: f_map = FAULT_MAP_109
            elif reg == 111: f_map = FAULT_MAP_111
            elif reg == 112: f_map = FAULT_MAP_112
            elif reg == 114: f_map = FAULT_MAP_114
            elif reg == 115: f_map = FAULT_MAP_115
            elif reg == 116: f_map = FAULT_MAP_116
            elif reg == 117: f_map = FAULT_MAP_117
            elif reg == 118: f_map = FAULT_MAP_118
            elif reg == 119: f_map = FAULT_MAP_119
            elif reg == 120: f_map = FAULT_MAP_120
            elif reg == 121: f_map = FAULT_MAP_121
            elif reg == 122: f_map = FAULT_MAP_122

            tum_hatalar = []
            if kod > 0:
                bitler = hata_bit_coz(kod, f_map)
                for bit, aciklama, sev in bitler:
                    if sev == "CRITICAL":
                        sev_icon = "🔴"
                    elif sev == "MAJOR":
                        sev_icon = "🟠"
                    else:
                        sev_icon = "🟡"
                    tum_hatalar.append(f"{sev_icon} R{reg} B{bit}: {aciklama}")
            
            hata_metni = " | ".join(tum_hatalar) if tum_hatalar else f"Bilinmeyen Hata (Kod: {kod})"
            
            tablo_verisi.append({
                "Durum": durum,
                "Baslama Zamani": baslangic,
                "Bitis Zamani": bitis,
                "ID": dev_id,
                "Hata Detaylari": hata_metni
            })
            
        df = pd.DataFrame(tablo_verisi)
        
        import io
        # Ust kisma indirme butonu koyalim
        c1, c2 = st.columns([4, 1])
        with c2:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Alarm_Gecmisi')
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 Excel Olarak Indir",
                data=excel_data,
                file_name=f"alarm_gecmisi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        st.markdown("### Filtreleme")
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            durum_secim = st.multiselect("Durum", options=df["Durum"].unique(), default=df["Durum"].unique())
        with f_col2:
            id_secim = st.multiselect("Cihaz ID", options=df["ID"].unique(), default=df["ID"].unique())
        with f_col3:
            kelime_ara = st.text_input("Hata İçeriğinde Ara", placeholder="Örn: Voltaj...")
            
        if durum_secim:
            df = df[df["Durum"].isin(durum_secim)]
        if id_secim:
            df = df[df["ID"].isin(id_secim)]
        if kelime_ara:
            df = df[df["Hata Detaylari"].str.contains(kelime_ara, case=False, na=False)]
            
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=500
        )
