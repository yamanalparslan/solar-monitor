import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys, os
import plotly.graph_objects as go

# Yolu ayarlama ve zel modlleri ie aktarma
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
import utils
from styles import render_top_nav, inject_glossy_css, section_header, kpi_row, solar_table
from auth import check_auth, logout_button



# --- SAYFA AYARLARI VE KONTROLLER ---
st.set_page_config(page_title="GUNLUK RAPORLAR", page_icon="", layout="wide")
inject_glossy_css()
render_top_nav()

if not check_auth():
    st.stop()


veritabani.init_db()

# --- Fabrika Kontrolü ---
from veritabani import FABRIKALAR
if 'fabrika_id' not in st.session_state or st.session_state.fabrika_id is None:
    st.warning("Lütfen ana sayfadan bir fabrika seçin.")
    st.stop()
fab_id = st.session_state.fabrika_id
fab_info = FABRIKALAR[fab_id]

# --- OTOMATIK YENILEME AYARI ---
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30


# --- BALIK ---
st.title("GUNLUK PERFORMANS VE URETIM RAPORU")
section_header("", "URETIM ANALIZI", "SECILEN TARIHE GORE TUM CIHAZLARIN URETIM VE VERIMLILIK OZETI")

# --- AYARLARI OKUMA ---
ayarlar = veritabani.tum_ayarlari_oku(fab_id)
isi_scale = float(ayarlar.get('isi_scale', '1.0'))

import collector_async
cfg = collector_async.load_config(fab_id)
slave_ids = []
for device in cfg["target_devices"]:
    for s_id in device["slave_ids"]:
        slave_ids.append(s_id)

# --- OSOS VERİ YÜKLEME ---
with st.expander(f"OSOS Verisi Yükle - {fab_info['ad']} (CSV/Excel)"):
    kayit_sayisi = veritabani.osos_kayit_sayisi_getir(fab_id)
    if kayit_sayisi > 0:
        col_info, col_del = st.columns([3, 1])
        with col_info:
            st.info(f"Sistemde bu fabrika için {kayit_sayisi} günlük OSOS verisi bulunuyor.")
        with col_del:
            if st.button("Verileri Sil", type="primary", use_container_width=True, key=f"del_osos_{fab_id}"):
                if veritabani.osos_verileri_sil(fab_id):
                    st.success("Silindi!")
                    st.rerun()
                else:
                    st.error("Hata!")
                    
    uploaded_file = st.file_uploader("OSOS verilerinizi yükleyin", type=["csv", "xlsx"], key=f"osos_uploader_{fab_id}")
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_osos = pd.read_csv(uploaded_file, sep=None, engine='python')
            else:
                df_osos = pd.read_excel(uploaded_file)
            
            # Gerekli sütunları kontrol et
            if all(col in df_osos.columns for col in ["Tarih", "Aktif Çekiş", "Aktif Veriş"]):
                # Türkçe ayları İngilizceye çevir veya doğrudan datetime parse et
                aylar = {
                    "Ocak": "01", "Şubat": "02", "Mart": "03", "Nisan": "04", "Mayıs": "05", "Haziran": "06",
                    "Temmuz": "07", "Ağustos": "08", "Eylül": "09", "Ekim": "10", "Kasım": "11", "Aralık": "12",
                    "Subat": "02", "Mayis": "05", "Agustos": "08", "Eylul": "09", "Kasim": "11", "Aralik": "12"
                }
                
                basarili = 0
                for index, row in df_osos.iterrows():
                    tarih_str = str(row["Tarih"])
                    for tr_ay, num_ay in aylar.items():
                        tarih_str = tarih_str.replace(tr_ay, num_ay)
                    
                    try:
                        # İlk olarak tam formatı dene
                        dt = pd.to_datetime(tarih_str, format="%d/%m/%Y %H:%M", errors='coerce')
                        if pd.isna(dt):
                            # Fallback olarak dayfirst=True ile serbest parse et (DD/MM/YYYY)
                            dt = pd.to_datetime(tarih_str, errors='coerce', dayfirst=True)
                            
                        if not pd.isna(dt):
                            cekis = float(str(row["Aktif Çekiş"]).replace(',', '.'))
                            veris = float(str(row["Aktif Veriş"]).replace(',', '.'))
                            if veritabani.osos_veri_ekle(fab_id, dt.strftime('%Y-%m-%d'), cekis, veris):
                                basarili += 1
                    except Exception as e:
                        continue
                
                if basarili > 0:
                    st.success(f"{basarili} adet günlük OSOS verisi başarıyla kaydedildi!")
                else:
                    st.warning("Veriler okundu ancak uygun tarih formatı bulunamadığı için kaydedilemedi.")
            else:
                st.error("Yüklenen dosyada 'Tarih', 'Aktif Çekiş' veya 'Aktif Veriş' sütunu bulunamadı!")
        except Exception as e:
            st.error(f"Dosya okuma hatası: {e}")


@st.fragment(run_every=f"{int(st.session_state.refresh_interval)}s")
def goster_rapor():
    # --- TARH SEM ---
    col_date, col_range, col_time, col_btn = st.columns([1, 1, 1, 1])
    with col_date:
        secilen_tarih = st.date_input("Rapor Tarihi:", datetime.now())
    with col_range:
        grafik_secim = st.selectbox("Grafik Aralığı:", [7, 14, 30, "Aylık"], format_func=lambda x: "Aylık (Bu Yıl)" if x == "Aylık" else f"Son {x} Gün")
    with col_time:
        st.caption(f"Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}")
    with col_btn:
        if st.button("Şimdi Yenile", width='stretch'):
            st.rerun()
    tarih_str = secilen_tarih.strftime('%Y-%m-%d')

    # --- VER TOPLAMA ---
    rapor_listesi = []
    for s_id in slave_ids:
        uretim = veritabani.gunluk_uretim_hesapla(tarih_str, slave_id=s_id, fabrika_id=fab_id)
        istatistik = veritabani.tarih_araliginda_ortalamalar(tarih_str, tarih_str, slave_id=s_id, fabrika_id=fab_id)
        hatalar = veritabani.hata_sayilarini_getir(tarih_str, tarih_str, slave_id=s_id, fabrika_id=fab_id)
        
        if istatistik and istatistik.get('toplam_olcum', 0) > 0:
            # Tum 13 alarm register toplami
            hata_toplam = 0
            if hatalar:
                hata_toplam = sum(
                    hatalar.get(k, 0) or 0
                    for k in [
                        'hata_107_sayisi', 'hata_109_sayisi', 'hata_111_sayisi',
                        'hata_112_sayisi', 'hata_114_sayisi', 'hata_115_sayisi',
                        'hata_116_sayisi', 'hata_117_sayisi', 'hata_118_sayisi',
                        'hata_119_sayisi', 'hata_120_sayisi', 'hata_121_sayisi',
                        'hata_122_sayisi',
                    ]
                )

            kwh_value = 0
            if uretim:
                kwh_value = uretim.get('modbus_uretim', 0) if uretim.get('modbus_uretim', 0) > 0 else uretim.get('uretim_kwh', 0)

            rapor_listesi.append({
                "Cihaz ID": s_id,
                "Uretim (kWh)": round(kwh_value, 3),
                "Ort. Guc (W)": round(istatistik['ort_guc'], 1),
                "Maks. Guc (W)": round(istatistik['max_guc'], 1),
                "Ort. Voltaj (V)": round(istatistik['ort_voltaj'], 1),
                "Ort. Sicaklik (C)": round(utils.normalize_temperature_value(istatistik.get('ort_sicaklik', 0) or 0), 1),
                "Toplam Hata": hata_toplam,
                "Calisma (Saat)": round(uretim['calisma_suresi_saat'], 2) if uretim else 0
            })

    # --- TABLO VE GRAFK GSTERM ---
    if rapor_listesi:
        df_rapor = pd.DataFrame(rapor_listesi)
        
        total_kwh = df_rapor["Uretim (kWh)"].sum()
        total_errors = df_rapor["Toplam Hata"].sum()

        osos_verisi = veritabani.osos_veri_getir(fab_id, tarih_str)
        
        if osos_verisi:
            aktif_cekis = osos_verisi['aktif_cekis']
            aktif_veris = osos_verisi['aktif_veris']
            gunluk_satilan = aktif_veris
            oz_tuketim = max(0.0, total_kwh - aktif_veris)
            gunluk_toplam_kullanilan = aktif_cekis + oz_tuketim
            
            kpi_row([
                {"value": f"{total_kwh:.1f} kWh", "label": "İNV ÜRETİM", "color": "#f59e0b"},
                {"value": f"{oz_tuketim:.1f} kWh", "label": "ÖZ TÜKETİM", "color": "#3b82f6"},
                {"value": f"{gunluk_toplam_kullanilan:.1f} kWh", "label": "TOPLAM KULLANIM", "color": "#ef4444"},
                {"value": f"{gunluk_satilan:.1f} kWh", "label": "ŞEBEKEYE SATILAN", "color": "#10b981"},
            ])
        else:
            kpi_row([
                {"value": f"{total_kwh:.1f} kWh", "label": "TOPLAM URETIM", "color": "#f59e0b"},
                {"value": str(len(df_rapor)), "label": "AKTIF CIHAZ", "color": "#10b981"},
                {"value": str(int(total_errors)), "label": "TOPLAM HATA", "color": "#ef4444"},
            ])
            st.caption("OSOS verisi yüklenmediği için tüketim ve şebeke analizi gösterilemiyor.")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- GÜNLÜK ÜRETİM VE OSOS TRENDİ GRAFİKLERİ ---
        trend_data = []
        osos_trend = []
        
        if grafik_secim == "Aylık":
            yil = secilen_tarih.year
            aylik_uretim = veritabani.aylik_uretim_getir(fab_id, yil)
            aylik_osos = veritabani.aylik_osos_getir(fab_id, yil)
            
            ay_isimleri = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            
            for ay in range(1, 13):
                ay_adi = ay_isimleri[ay - 1]
                u_kwh = aylik_uretim.get(ay, 0)
                trend_data.append({"Tarih": ay_adi, "Üretim": round(u_kwh, 2)})
                
                osos = aylik_osos.get(ay)
                if osos:
                    aktif_cekis = osos['aktif_cekis']
                    aktif_veris = osos['aktif_veris']
                    oz_tuketim = max(0.0, u_kwh - aktif_veris)
                    toplam_kullanim = aktif_cekis + oz_tuketim
                    osos_trend.append({
                        "Tarih": ay_adi,
                        "Satılan": aktif_veris,
                        "Toplam Kullanım": toplam_kullanim,
                        "Öz Tüketim": oz_tuketim
                    })
                else:
                    osos_trend.append({
                        "Tarih": ay_adi,
                        "Satılan": 0,
                        "Toplam Kullanım": 0,
                        "Öz Tüketim": 0
                    })
        else:
            for i in range(grafik_secim - 1, -1, -1):
                gun_tarih = (secilen_tarih - timedelta(days=i)).strftime('%Y-%m-%d')
                uretim = veritabani.gunluk_uretim_hesapla(gun_tarih, slave_id=None, fabrika_id=fab_id)
                u_kwh = 0
                if uretim:
                    u_kwh = uretim.get('modbus_uretim', 0) if uretim.get('modbus_uretim', 0) > 0 else uretim.get('uretim_kwh', 0)
                trend_data.append({"Tarih": gun_tarih, "Üretim": round(u_kwh, 2)})
                
                osos = veritabani.osos_veri_getir(fab_id, gun_tarih)
                if osos:
                    aktif_cekis = osos['aktif_cekis']
                    aktif_veris = osos['aktif_veris']
                    oz_tuketim = max(0.0, u_kwh - aktif_veris)
                    toplam_kullanim = aktif_cekis + oz_tuketim
                    osos_trend.append({
                        "Tarih": gun_tarih,
                        "Satılan": aktif_veris,
                        "Toplam Kullanım": toplam_kullanim,
                        "Öz Tüketim": oz_tuketim
                    })
                else:
                    osos_trend.append({
                        "Tarih": gun_tarih,
                        "Satılan": 0,
                        "Toplam Kullanım": 0,
                        "Öz Tüketim": 0
                    })
                
        df_trend = pd.DataFrame(trend_data)
        df_osos_trend = pd.DataFrame(osos_trend)
        
        # Draw OSOS Trend Chart
        if not df_osos_trend.empty:
            fig_osos = go.Figure()
            fig_osos.add_trace(go.Bar(
                x=df_osos_trend["Tarih"], y=df_osos_trend["Öz Tüketim"],
                name="Öz Tüketim", marker_color="#3b82f6"
            ))
            fig_osos.add_trace(go.Bar(
                x=df_osos_trend["Tarih"], y=df_osos_trend["Satılan"],
                name="Şebekeye Satılan", marker_color="#10b981"
            ))
            fig_osos.add_trace(go.Bar(
                x=df_osos_trend["Tarih"], y=df_osos_trend["Toplam Kullanım"],
                name="Toplam Kullanım", marker_color="#ef4444"
            ))
            baslik_zaman = f"{secilen_tarih.year} Yılı" if grafik_secim == "Aylık" else f"Son {grafik_secim} Günlük"
            fig_osos.update_layout(
                barmode='group',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=0, r=0, t=35, b=0),
                height=320,
                title=dict(text=f"{baslik_zaman} Enerji Tüketim ve Satış Özeti (kWh)", font=dict(size=14, color='#1D1D1F', family='Outfit', weight='bold')),
                yaxis=dict(gridcolor='rgba(0,0,0,0.05)', showgrid=True, zeroline=False, rangemode='tozero', title="kWh"),
                xaxis=dict(showgrid=False, showline=True, linecolor='rgba(0,0,0,0.1)'),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                font=dict(color='#86868B', family='Outfit'),
                hovermode='x unified'
            )
            st.plotly_chart(fig_osos, use_container_width=True, config={"displayModeBar": False})
            st.markdown("<br>", unsafe_allow_html=True)

        if not df_trend.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_trend["Tarih"], y=df_trend["Üretim"],
                name='İnverter Üretimi',
                marker=dict(color='rgba(245, 158, 11, 0.75)', line=dict(color='#f59e0b', width=2)),
                hovertemplate='%{x}<br>Üretim: %{y:.1f} kWh<extra></extra>'
            ))
            baslik_uretim = f"{secilen_tarih.year} Yılı" if grafik_secim == "Aylık" else f"Son {grafik_secim} Günlük"
            fig.update_layout(
                paper_bgcolor='rgba(255,255,255,0)',
                plot_bgcolor='rgba(255,255,255,0)',
                margin=dict(l=0, r=0, t=35, b=0),
                height=280,
                title=dict(text=f"Tesisin {baslik_uretim} Üretim Trendi", font=dict(size=14, color='#1D1D1F', family='Outfit', weight='bold')),
                xaxis=dict(showgrid=False, showline=True, linecolor='rgba(0,0,0,0.1)'),
                yaxis=dict(gridcolor='rgba(0,0,0,0.05)', showgrid=True, zeroline=False, rangemode='tozero', title="kWh"),
                font=dict(color='#86868B', family='Outfit'),
                hovermode='x unified',
                hoverlabel=dict(
                    bgcolor='rgba(255,255,255,0.95)',
                    bordercolor='rgba(245, 158, 11, 0.5)',
                    font=dict(family='Outfit', size=13, color='#1D1D1F'),
                    align='left',
                ),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown("<br>", unsafe_allow_html=True)

            # --- KAZANÇ TRENDİ ---
            if not df_osos_trend.empty:
                df_kazanc = df_osos_trend.copy()
                df_kazanc["Kazanç (TL)"] = df_kazanc["Satılan"] * 2.9097037
                
                fig_kazanc = go.Figure()
                fig_kazanc.add_trace(go.Bar(
                    x=df_kazanc["Tarih"], y=df_kazanc["Kazanç (TL)"],
                    name='Günlük Kazanç',
                    marker=dict(color='rgba(16, 185, 129, 0.75)', line=dict(color='#10b981', width=2)),
                    hovertemplate='%{x}<br>Kazanç: %{y:.2f} TL<extra></extra>'
                ))
                
                fig_kazanc.update_layout(
                    paper_bgcolor='rgba(255,255,255,0)',
                    plot_bgcolor='rgba(255,255,255,0)',
                    margin=dict(l=0, r=0, t=35, b=0),
                    height=280,
                    title=dict(text=f"Tesisin {baslik_uretim} Satış Kazancı Trendi (TL)", font=dict(size=14, color='#1D1D1F', family='Outfit', weight='bold')),
                    xaxis=dict(showgrid=False, showline=True, linecolor='rgba(0,0,0,0.1)'),
                    yaxis=dict(gridcolor='rgba(0,0,0,0.05)', showgrid=True, zeroline=False, rangemode='tozero', title="TL", tickformat=".2f"),
                    font=dict(color='#86868B', family='Outfit'),
                    hovermode='x unified',
                    hoverlabel=dict(
                        bgcolor='rgba(255,255,255,0.95)',
                        bordercolor='rgba(16, 185, 129, 0.5)',
                        font=dict(family='Outfit', size=13, color='#1D1D1F'),
                        align='left',
                    ),
                )
                st.plotly_chart(fig_kazanc, use_container_width=True, config={"displayModeBar": False})
                st.markdown("<br>", unsafe_allow_html=True)

            # --- O GUNUN GUC PROFILI ---
            profil_tarih = secilen_tarih.strftime('%Y-%m-%d')
            conn = veritabani.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT date_trunc('hour', zaman) as saat, AVG(guc)
                    FROM olcumler 
                    WHERE fabrika_id = %s AND DATE(zaman) = %s AND guc > 0
                    GROUP BY saat
                    ORDER BY saat
                """, (fab_id, profil_tarih))
                rows = cursor.fetchall()
                conn.close()
                
                if rows:
                    df_guc = pd.DataFrame(rows, columns=['saat', 'ort_guc'])
                    fig_guc = go.Figure()
                    
                    # Glow effect trace
                    fig_guc.add_trace(go.Scatter(
                        x=df_guc['saat'], y=df_guc['ort_guc'],
                        mode='lines',
                        line=dict(color="rgba(16, 185, 129, 0.25)", width=8, shape='spline', smoothing=1.3),
                        hoverinfo='skip',
                        showlegend=False
                    ))
                    
                    # Main trace
                    fig_guc.add_trace(go.Scatter(
                        x=df_guc['saat'], y=df_guc['ort_guc'],
                        mode='lines',
                        name='Ortalama Güç',
                        line=dict(color="#10b981", width=3, shape='spline', smoothing=1.3),
                        fill='tozeroy',
                        fillcolor='rgba(16, 185, 129, 0.15)',
                        hovertemplate='%{x|%H:%M}<br>Güç: %{y:.1f} W<extra></extra>'
                    ))
                    fig_guc.update_layout(
                        paper_bgcolor='rgba(255,255,255,0)',
                        plot_bgcolor='rgba(255,255,255,0)',
                        margin=dict(l=0, r=0, t=35, b=0),
                        height=280,
                        title=dict(text=f"{profil_tarih} Tarihli Ortalama Güç Profili (Saatlik)", font=dict(size=14, color='#1D1D1F', family='Outfit', weight='bold')),
                        xaxis=dict(showgrid=False, showline=True, linecolor='rgba(0,0,0,0.1)'),
                        yaxis=dict(gridcolor='rgba(0,0,0,0.05)', showgrid=True, zeroline=False, rangemode='tozero', title="Güç (W)"),
                        font=dict(color='#86868B', family='Outfit'),
                        hovermode='x unified',
                        hoverlabel=dict(
                            bgcolor='rgba(255,255,255,0.95)',
                            bordercolor='rgba(16, 185, 129, 0.5)',
                            font=dict(family='Outfit', size=13, color='#1D1D1F'),
                        )
                    )
                    st.plotly_chart(fig_guc, width='stretch', config={"displayModeBar": False})
                    st.markdown("<br>", unsafe_allow_html=True)

        # solar_table ile premium HTML tablo
        tablo_headers = ["CIHAZ", "URETIM (kWh)", "ORT. GUC (W)", "MAKS. GUC (W)", "ORT. VOLTAJ (V)", "ORT. ISI (C)", "HATA", "CALISMA (sa)"]
        tablo_rows = [
            [
                f"Inv {r['Cihaz ID']}",
                f"{r['Uretim (kWh)']:.1f}",
                f"{r['Ort. Guc (W)']:.1f}",
                f"{r['Maks. Guc (W)']:.1f}",
                f"{r['Ort. Voltaj (V)']:.1f}",
                f"{r['Ort. Sicaklik (C)']:.1f}",
                str(r['Toplam Hata']),
                f"{r['Calisma (Saat)']:.2f}",
            ]
            for r in rapor_listesi
        ]
        solar_table(
            tablo_rows,
            headers=tablo_headers,
            status_col_idx=6,
            status_colors={"0": "#10b981"},   # hata 0 ise yesil
        )

        # CSV indirme
        csv = df_rapor.to_csv(index=False).encode('utf-8-sig')
        st.download_button("CSV Indir", csv, "gunluk_rapor_" + tarih_str + ".csv", "text/csv")
        
    else:
        # Veri yoksa gsterilecek bo ekran
        st.markdown(
            '<div class="glossy-card" style="text-align:center;">'
            '<div style="font-size:2rem; margin-bottom:8px;"></div>'
            '<div style="font-size:1rem; color:#86868B; font-family:Outfit,sans-serif;">Secilen tarihte veri bulunamadi.</div>'
            '</div>', 
            unsafe_allow_html=True
        )

goster_rapor()