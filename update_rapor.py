import re

new_body = """
    # --- TARİH VE PERİYOT SEÇİMİ ---
    import calendar
    today = datetime.now()
    
    col_type, col_date, col_time, col_btn = st.columns([1, 2, 1, 1])
    with col_type:
        rapor_tipi = st.selectbox("Rapor Tipi:", ["Günlük", "Haftalık", "Aylık", "Yıllık"])
        
    with col_date:
        if rapor_tipi == "Günlük":
            secilen_tarih = st.date_input("Rapor Tarihi:", today)
            baslangic_tarih = secilen_tarih.strftime('%Y-%m-%d')
            bitis_tarih = baslangic_tarih
            grafik_baslik = f"{baslangic_tarih} Tarihli"
        elif rapor_tipi == "Haftalık":
            secilen_tarih = st.date_input("Haftanın Herhangi Bir Günü:", today)
            start_of_week = secilen_tarih - timedelta(days=secilen_tarih.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            baslangic_tarih = start_of_week.strftime('%Y-%m-%d')
            bitis_tarih = end_of_week.strftime('%Y-%m-%d')
            grafik_baslik = f"Haftalık ({start_of_week.strftime('%d.%m')} - {end_of_week.strftime('%d.%m')})"
        elif rapor_tipi == "Aylık":
            ay_isimleri = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            c1, c2 = st.columns(2)
            secilen_ay = c1.selectbox("Ay:", ay_isimleri, index=today.month - 1)
            secilen_yil = c2.selectbox("Yıl:", range(2024, today.year + 2), index=today.year - 2024)
            ay_index = ay_isimleri.index(secilen_ay) + 1
            son_gun = calendar.monthrange(secilen_yil, ay_index)[1]
            baslangic_tarih = f"{secilen_yil}-{ay_index:02d}-01"
            bitis_tarih = f"{secilen_yil}-{ay_index:02d}-{son_gun:02d}"
            grafik_baslik = f"{secilen_ay} {secilen_yil}"
        elif rapor_tipi == "Yıllık":
            secilen_yil = st.selectbox("Yıl:", range(2024, today.year + 2), index=today.year - 2024)
            baslangic_tarih = f"{secilen_yil}-01-01"
            bitis_tarih = f"{secilen_yil}-12-31"
            grafik_baslik = f"{secilen_yil} Yılı"

    with col_time:
        st.caption(f"Son Güncelleme:<br>{datetime.now().strftime('%H:%M:%S')}", unsafe_allow_html=True)
    with col_btn:
        st.write("") # padding
        if st.button("Şimdi Yenile", width='stretch'):
            st.rerun()

    # --- VERİ TOPLAMA ---
    rapor_listesi = []
    for s_id in slave_ids:
        if rapor_tipi == "Günlük":
            uretim = veritabani.gunluk_uretim_hesapla(baslangic_tarih, slave_id=s_id, fabrika_id=fab_id)
        else:
            uretim = veritabani.aralik_uretim_hesapla(baslangic_tarih, bitis_tarih, slave_id=s_id, fabrika_id=fab_id)
            
        istatistik = veritabani.tarih_araliginda_ortalamalar(baslangic_tarih, bitis_tarih, slave_id=s_id, fabrika_id=fab_id)
        hatalar = veritabani.hata_sayilarini_getir(baslangic_tarih, bitis_tarih, slave_id=s_id, fabrika_id=fab_id)
        
        if istatistik and istatistik.get('toplam_olcum', 0) > 0:
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

    # --- TABLO VE GRAFİK GÖSTERİMİ ---
    if rapor_listesi:
        df_rapor = pd.DataFrame(rapor_listesi)
        
        total_kwh = df_rapor["Uretim (kWh)"].sum()
        total_errors = df_rapor["Toplam Hata"].sum()

        kpi_row([
            {"value": f"{total_kwh:.1f} kWh", "label": f"TOPLAM ÜRETİM ({grafik_baslik.upper()})", "color": "#f59e0b"},
            {"value": str(len(df_rapor)), "label": "AKTİF CİHAZ", "color": "#10b981"},
            {"value": str(int(total_errors)), "label": "TOPLAM HATA", "color": "#ef4444"},
        ])

        st.markdown("<br>", unsafe_allow_html=True)

        # --- ÜRETİM TRENDİ GRAFİĞİ ---
        trend_data = []
        if rapor_tipi != "Günlük":
            if rapor_tipi == "Haftalık":
                for i in range(7):
                    gun = (start_of_week + timedelta(days=i)).strftime('%Y-%m-%d')
                    uretim = veritabani.gunluk_uretim_hesapla(gun, slave_id=None, fabrika_id=fab_id)
                    kwh = uretim.get('modbus_uretim', 0) if (uretim and uretim.get('modbus_uretim', 0) > 0) else (uretim.get('uretim_kwh', 0) if uretim else 0)
                    gun_adlari = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
                    trend_data.append({"Tarih": f"{gun_adlari[i]} ({gun[-2:]})", "Üretim": round(kwh, 2)})
            elif rapor_tipi == "Aylık":
                for d in range(1, son_gun + 1):
                    gun = f"{secilen_yil}-{ay_index:02d}-{d:02d}"
                    uretim = veritabani.gunluk_uretim_hesapla(gun, slave_id=None, fabrika_id=fab_id)
                    kwh = uretim.get('modbus_uretim', 0) if (uretim and uretim.get('modbus_uretim', 0) > 0) else (uretim.get('uretim_kwh', 0) if uretim else 0)
                    trend_data.append({"Tarih": f"{d:02d}.{ay_index:02d}", "Üretim": round(kwh, 2)})
            elif rapor_tipi == "Yıllık":
                ay_isimleri_kisa = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
                for m in range(1, 13):
                    son = calendar.monthrange(secilen_yil, m)[1]
                    m_bas = f"{secilen_yil}-{m:02d}-01"
                    m_bit = f"{secilen_yil}-{m:02d}-{son:02d}"
                    uretim = veritabani.aralik_uretim_hesapla(m_bas, m_bit, slave_id=None, fabrika_id=fab_id)
                    kwh = uretim.get('modbus_uretim', 0) if (uretim and uretim.get('modbus_uretim', 0) > 0) else (uretim.get('uretim_kwh', 0) if uretim else 0)
                    trend_data.append({"Tarih": ay_isimleri_kisa[m-1], "Üretim": round(kwh, 2)})

            df_trend = pd.DataFrame(trend_data)
            
            if not df_trend.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df_trend["Tarih"], y=df_trend["Üretim"],
                    name='Üretim',
                    marker=dict(color='rgba(245, 158, 11, 0.75)', line=dict(color='#f59e0b', width=2)),
                    hovertemplate='%{x}<br>Üretim: %{y:.1f} kWh<extra></extra>'
                ))
                fig.update_layout(
                    paper_bgcolor='rgba(255,255,255,0)',
                    plot_bgcolor='rgba(255,255,255,0)',
                    margin=dict(l=0, r=0, t=35, b=0),
                    height=280,
                    title=dict(text=f"Tesisin {grafik_baslik} Üretim Trendi", font=dict(size=14, color='#1D1D1F', family='Outfit', weight='bold')),
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
                st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
                st.markdown("<br>", unsafe_allow_html=True)

        if rapor_tipi == "Günlük":
            # --- O GUNUN GUC PROFILI ---
            conn = veritabani.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(\"\"\"
                    SELECT date_trunc('hour', zaman) as saat, AVG(guc)
                    FROM olcumler 
                    WHERE fabrika_id = %s AND DATE(zaman) = %s AND guc > 0
                    GROUP BY saat
                    ORDER BY saat
                \"\"\", (fab_id, baslangic_tarih))
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
                        title=dict(text=f"{baslangic_tarih} Tarihli Ortalama Güç Profili (Saatlik)", font=dict(size=14, color='#1D1D1F', family='Outfit', weight='bold')),
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
        tablo_headers = ["CİHAZ", "ÜRETİM (kWh)", "ORT. GÜÇ (W)", "MAKS. GÜÇ (W)", "ORT. VOLTAJ (V)", "ORT. ISI (C)", "HATA", "ÇALIŞMA (sa)"]
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
        st.download_button("CSV İndir", csv, f"rapor_{baslangic_tarih}_{bitis_tarih}.csv", "text/csv")
        
    else:
        # Veri yoksa gosterilecek bos ekran
        st.markdown(
            '<div class="glossy-card" style="text-align:center;">'
            '<div style="font-size:2rem; margin-bottom:8px;"></div>'
            '<div style="font-size:1rem; color:#86868B; font-family:Outfit,sans-serif;">Seçilen aralıkta veri bulunamadı.</div>'
            '</div>', 
            unsafe_allow_html=True
        )
"""

with open("pages/1_GUNLUK_RAPOR.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the function def and replace everything after it
start_idx = content.find("def goster_rapor():")
if start_idx != -1:
    content = content[:start_idx + len("def goster_rapor():")] + "\n" + new_body
    with open("pages/1_GUNLUK_RAPOR.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Replace success!")
else:
    print("Function not found!")
