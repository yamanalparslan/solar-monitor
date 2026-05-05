import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import sys, os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
import utils
from styles import inject_glossy_css, section_header, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="PDF Rapor", page_icon="", layout="wide")
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

st.title("Gelismis PDF Raporlayici")
section_header("", "Belge Olustur", "Donanim analizi ve uretim verilerini profesyonel formata donusturun")

import collector_async
cfg = collector_async.load_config(fab_id)
slave_ids = []
for device in cfg["target_devices"]:
    for s_id in device["slave_ids"]:
        slave_ids.append(s_id)

col1, col2 = st.columns([1, 1])
with col1:
    baslangic = st.date_input("Baslangic Tarihi:", datetime.now() - timedelta(days=1))
with col2:
    bitis = st.date_input("Bitis Tarihi:", datetime.now())

if baslangic > bitis:
    st.error("Baslangic tarihi bitis tarihinden buyuk olamaz.")
else:
    st.info("Bu rapor, secilen tarih araligindaki tum uretim verilerini ve cihaz durumunu icerir.")
    
    if st.button("Raporu Hazirla", type="primary"):
        with st.spinner("PDF dokumani olusturuluyor... Lutfen bekleyin."):
            # Rapor verilerini topla
            baslangic_str = baslangic.strftime('%Y-%m-%d')
            bitis_str = bitis.strftime('%Y-%m-%d')
            
            rapor_verileri = []
            toplam_uretim = 0
            
            for s_id in slave_ids:
                istatistik = veritabani.tarih_araliginda_ortalamalar(baslangic_str, bitis_str, slave_id=s_id, fabrika_id=fab_id)
                hatalar = veritabani.hata_sayilarini_getir(baslangic_str, bitis_str, slave_id=s_id, fabrika_id=fab_id)
                
                delta = bitis - baslangic
                cihaz_uretimi = 0
                for i in range(delta.days + 1):
                    t_str = (baslangic + timedelta(days=i)).strftime('%Y-%m-%d')
                    u = veritabani.gunluk_uretim_hesapla(t_str, slave_id=s_id, fabrika_id=fab_id)
                    if u:
                        cihaz_uretimi += u.get('uretim_kwh', 0)
                
                toplam_uretim += cihaz_uretimi
                
                if istatistik and istatistik.get('toplam_olcum', 0) > 0:
                    hata_sayisi = 0
                    if hatalar:
                        hata_sayisi = hatalar['hata_107_sayisi'] + hatalar['hata_111_sayisi']
                    
                    rapor_verileri.append([
                        f"Inverter {s_id}",
                        f"{cihaz_uretimi:.2f} kWh",
                        f"{istatistik['ort_guc']:.1f} W",
                        f"{istatistik['max_guc']:.1f} W",
                        f"{istatistik['ort_sicaklik']:.1f} C",
                        str(hata_sayisi)
                    ])

            # PDF Icerik Uretimi
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
            elements = []
            
            styles = getSampleStyleSheet()
            title_style = styles['Heading1']
            title_style.alignment = 1 # Center
            
            elements.append(Paragraph("<b>PULSAR Solar Izleme Merkezi</b>", title_style))
            elements.append(Spacer(1, 12))
            
            elements.append(Paragraph(f"<b>Rapor Tarih Araligi:</b> {baslangic_str} / {bitis_str}", styles['Normal']))
            elements.append(Paragraph(f"<b>Toplam Uretim:</b> {toplam_uretim:.2f} kWh", styles['Normal']))
            elements.append(Spacer(1, 24))
            
            elements.append(Paragraph("<b>Cihaz Bazli Performans Ozeti</b>", styles['Heading2']))
            elements.append(Spacer(1, 12))
            
            if rapor_verileri:
                # Tablo Basliklari
                table_data = [["Cihaz ID", "Uretim", "Ort. Guc", "Maks. Guc", "Ort. Isi", "Hata Sayisi"]]
                table_data.extend(rapor_verileri)
                
                t = Table(table_data, colWidths=[80, 80, 80, 80, 80, 80])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f1f5f9')),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1'))
                ]))
                elements.append(t)
            else:
                elements.append(Paragraph("<i>Belirtilen tarihlerde veri bulunamadi.</i>", styles['Normal']))

            elements.append(Spacer(1, 36))


            doc.build(elements)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            st.success("Rapor basariyla olusturuldu!")
            
            st.download_button(
                label="INDIR: Sistem Raporu (PDF)",
                data=pdf_bytes,
                file_name=f"pulsar_rapor_{baslangic_str}_to_{bitis_str}.pdf",
                mime="application/pdf",
                type="primary"
            )
