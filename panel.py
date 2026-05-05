import streamlit as st
import time
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import veritabani
import utils
from styles import inject_glossy_css, section_header, status_bar, kpi_row
from auth import check_auth, logout_button
from crm_embed import inject_embed_mode, is_embed_mode

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Solar Monitor",
    layout="wide",
    page_icon="",
    initial_sidebar_state="expanded"
)

# --- AUTH KONTROLU ---
if not check_auth():
    st.stop()

# DB Baslat
veritabani.init_db()

# --- GLOSSY CSS TEMA ---
inject_glossy_css()
logout_button()

# --- CRM EMBED MODU ---
inject_embed_mode(hide_sidebar=False)

# --- FABRİKA SEÇİMİ ---
from veritabani import FABRIKALAR, VARSAYILAN_FABRIKA

if 'fabrika_id' not in st.session_state:
    st.session_state.fabrika_id = None

# Fabrika seçilmemişse seçim ekranı göster
if st.session_state.fabrika_id is None:
    st.markdown("""
    <div style="display:flex;justify-content:center;align-items:center;min-height:60vh;">
        <div style="text-align:center;">
            <h1 style="font-size:2.5rem;font-weight:800;
                background:linear-gradient(135deg,#6366f1,#a855f7);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                margin-bottom:8px;">☀️ Solar Monitor</h1>
            <p style="color:#64748b;font-size:1.1rem;margin-bottom:32px;">İzlemek istediğiniz fabrikayı seçin</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔧 Mekanik Fabrika", use_container_width=True, type="primary"):
                st.session_state.fabrika_id = "mekanik"
                st.rerun()
        with c2:
            if st.button("🏭 Üretim Fabrika", use_container_width=True, type="primary"):
                st.session_state.fabrika_id = "uretim"
                st.rerun()
    st.stop()

fab_id = st.session_state.fabrika_id
fab_info = FABRIKALAR[fab_id]

# --- YARDIMCI ---
if 'ayarlar_kaydedildi' not in st.session_state:
    st.session_state.ayarlar_kaydedildi = False

# --- YAN MENU ---
with st.sidebar:
    # Fabrika değiştirme butonu
    st.caption(f"{fab_info['ikon']} {fab_info['ad']}")
    if st.button("🔄 Fabrika Değiştir", use_container_width=True):
        st.session_state.fabrika_id = None
        st.rerun()
    st.divider()
    st.header("PULSAR Ayarlari")

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

    target_ip = st.text_input(
        "IP Adresi",
        value=mevcut_ayarlar.get('target_ip', '10.35.14.10'),
        key="target_ip_input",
    )
    target_port = st.number_input(
        "Port",
        value=int(mevcut_ayarlar.get('target_port', 502)),
        step=1,
        key="target_port_input",
    )

    st.info("Virgul veya tire ile ayirin (Orn: 1, 2, 5-8)")
    id_input = st.text_input(
        "Inverter ID Listesi",
        value=mevcut_ayarlar.get('slave_ids', '1,2,3'),
        key="slave_ids_input",
    )
    target_ids, id_errors = utils.parse_id_list(id_input)

    if id_errors:
        st.warning(f"Bazi ID'ler parse edilemedi: {', '.join(id_errors)}")

    st.write(f"Izlenecek ID'ler: {utils.format_id_list_display(target_ids)}")

    st.divider()
    st.header("Zamanlayici")

    selected_interval = st.select_slider(
        "Veri Toplama Sikligi",
        options=list(interval_options.keys()),
        value=current_label,
        key="refresh_rate_slider",
    )

    refresh_rate = interval_options[selected_interval]
    st.info(f" Secilen: {selected_interval} ({refresh_rate} saniye)")

    st.markdown("---")
    st.header("Adres Haritasi")
    with st.expander("Detayli Adres Ayarlari", expanded=False):
        c_guc_adr = st.number_input(
            "Guc Adresi",
            value=int(mevcut_ayarlar.get('guc_addr', 70)),
            key="guc_addr_input",
        )
        c_guc_sc = st.number_input(
            "Guc Carpan",
            value=float(mevcut_ayarlar.get('guc_scale', 1.0)),
            step=0.01,
            format="%.4f",
            key="guc_scale_input",
            help="Ondalik olarak yazabilirsiniz. Ornek: 0.01",
        )

        c_volt_adr = st.number_input(
            "Voltaj Adresi",
            value=int(mevcut_ayarlar.get('volt_addr', 71)),
            key="volt_addr_input",
        )
        c_volt_sc = st.number_input(
            "Voltaj Carpan",
            value=float(mevcut_ayarlar.get('volt_scale', 1.0)),
            step=0.01,
            format="%.4f",
            key="volt_scale_input",
            help="Ondalik olarak yazabilirsiniz. Ornek: 0.1",
        )

        c_akim_adr = st.number_input(
            "Akim Adresi",
            value=int(mevcut_ayarlar.get('akim_addr', 72)),
            key="akim_addr_input",
        )
        c_akim_sc = st.number_input(
            "Akim Carpani",
            value=float(mevcut_ayarlar.get('akim_scale', 0.1)),
            step=0.01,
            format="%.4f",
            key="akim_scale_input",
            help="Ondalik olarak yazabilirsiniz. Ornek: 0.01",
        )

        c_isi_adr = st.number_input(
            "Isi Adresi",
            value=int(mevcut_ayarlar.get('isi_addr', 74)),
            key="isi_addr_input",
        )
        c_isi_sc = st.number_input(
            "Isi Carpani",
            value=float(mevcut_ayarlar.get('isi_scale', 0.001)),
            step=0.01,
            format="%.4f",
            key="isi_scale_input",
            help="Ondalik olarak yazabilirsiniz. Ornek: 0.01 veya 0.001",
        )

    submitted = st.button("AYARLARI KALICI OLARAK KAYDET", type="primary", use_container_width=True)

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

        st.success("Ayarlar kaydedildi! Collector bir sonraki okuma dongusunda guncellenecek.")
        kullanici = st.session_state.get('username', 'admin')
        veritabani.audit_log_kaydet(kullanici, "ayar_degistir", f"IP={target_ip}, Port={target_port}, IDs={id_input}")
        st.rerun()

    # Yenileme suresi ayar
    st.markdown("---")
    st.header("Yenileme Ayarlari")

    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 30

    refresh_interval = st.select_slider(
        "Otomatik Yenileme Suresi",
        options=[10, 15, 30, 60, 120, 300, 600, 1800, 3600, 7200],
        value=st.session_state.refresh_interval,
        format_func=lambda x: f"{x} saniye"
    )

    st.session_state.refresh_interval = refresh_interval

    st.caption(f"Panel {refresh_interval} saniyede bir yenilenecek")

    st.markdown("---")
    st.header("Collector Durumu")
    # Collector'ın son veriyi ne zaman yazdığını DB'den kontrol et
    _son = veritabani.tum_cihazlarin_son_durumu(fab_id)
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

    st.markdown("---")
    st.header(" Veri Yonetimi")
    if st.button("Tum Verileri Sil"):
        if veritabani.db_temizle(fab_id):
            kullanici = st.session_state.get('username', 'admin')
            veritabani.audit_log_kaydet(kullanici, "veri_sil", f"[{fab_id}] Tum olcum verileri silindi")
            st.success("Temizlendi!")
            time.sleep(1)
            st.rerun()

# --- ANA EKRAN ---
st.title("Gunes Enerjisi Santrali Izleme")

section_header("", "Canli Filo Durumu", "Tum cihazlarin anlik durum ozeti")

# --- Plotly Grafik Yardmclar ---
def create_plotly_chart(df, column, title, color, unit=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df[column],
        mode='lines',
        line=dict(color=color, width=2.5),
        fill='tozeroy',
        fillcolor=color.replace(')', ',0.08)').replace('rgb', 'rgba'),
        hovertemplate=f'%{{x|%H:%M:%S}}<br>{title}: %{{y:.1f}} {unit}<extra></extra>',
        name=title
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10, 14, 26, 0.5)',
        margin=dict(l=10, r=10, t=35, b=10),
        height=260,
        title=dict(text=title, font=dict(size=13, color='#94a3b8', family='Inter')),
        xaxis=dict(gridcolor='rgba(255,255,255,0.04)', showgrid=True, zeroline=False),
        yaxis=dict(gridcolor='rgba(255,255,255,0.04)', showgrid=True, zeroline=False),
        font=dict(color='#94a3b8', family='Inter'),
        hovermode='x unified',
    )
    return fig


def create_comparison_chart(ids, metric, title, colors):
    fig = go.Figure()
    for i, dev_id in enumerate(ids):
        data = veritabani.son_verileri_getir(dev_id, limit=100, fabrika_id=fab_id)
        if not data:
            continue
            
        cols = ["timestamp", "guc", "voltaj", "akim", "sicaklik", "hata_kodu", "hata_kodu_109", "hata_kodu_111", "hata_kodu_112", "hata_kodu_114", "hata_kodu_115", "hata_kodu_116", "hata_kodu_117", "hata_kodu_118", "hata_kodu_119", "hata_kodu_120", "hata_kodu_121", "hata_kodu_122"]
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

        color = colors[i % len(colors)]
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df[metric],
            mode='lines', name=f'ID {dev_id}',
            line=dict(color=color, width=2.5),
        ))
        
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10, 14, 26, 0.5)',
        margin=dict(l=10, r=10, t=40, b=10),
        height=360,
        title=dict(text=title, font=dict(size=14, color='#94a3b8', family='Inter')),
        xaxis=dict(gridcolor='rgba(255,255,255,0.04)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.04)'),
        font=dict(color='#94a3b8', family='Inter'),
        hovermode='x unified',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8')
        ),
    )
    return fig

# --- Cihaz Saglk Kartlar ---
@st.fragment(run_every=f"{int(st.session_state.refresh_interval)}s")
def guncel_verileri_goster():
    gauge_spot = st.empty()
    table_spot = st.empty()

    import collector_async
    cfg = collector_async.load_config(fab_id)
    active_dev_ids = []
    for device in cfg["target_devices"]:
        for s_id in device["slave_ids"]:
            active_dev_ids.append(s_id)

    # --- Grafik Secimi ---
    st.markdown("---")

    tab_tekli, tab_karsilastirma = st.tabs([" Tekli Cihaz", "Karsilastirma"])

    with tab_tekli:
        col_sel, col_info = st.columns([1, 3])
        with col_sel:
            selected_id = st.selectbox("Cihaz Sec:", active_dev_ids, key="tek_cihaz")
        with col_info:
            st.info(" Detayli ariza kodlarini gormek icin sol menuden **Alarmlar** sayfasina gidin.")

        row1_c1, row1_c2 = st.columns(2)
        row2_c1, row2_c2 = st.columns(2)
        with row1_c1:
            chart_guc = st.empty()
        with row1_c2:
            chart_volt = st.empty()
        with row2_c1:
            chart_akim = st.empty()
        with row2_c2:
            chart_isi = st.empty()

    with tab_karsilastirma:
        karsilastirma_ids = st.multiselect("Karsilastirilacak Cihazlar:", active_dev_ids, default=active_dev_ids[:3])
        karsilastirma_metrik = st.selectbox("Metrik:", ["guc", "voltaj", "akim", "sicaklik"],
                                             format_func=lambda x: {"guc": " Guc (W)", "voltaj": " Voltaj (V)",
                                                                      "akim": "Akim (A)", "sicaklik": "Sicaklik (C)"}[x])

        chart_karsilastirma = st.empty()

    status_spot = st.empty()

    # 1. TABLO VE KART GUNCELLEME
    summary_data = veritabani.tum_cihazlarin_son_durumu(fab_id)
    if summary_data:
        with gauge_spot.container():
            num_devices = len(summary_data)
            cols_per_row = min(num_devices, 4)
            gauge_cols = st.columns(cols_per_row)

            for idx, row in enumerate(summary_data):
                col_idx = idx % cols_per_row
                dev_id = row[0]
                dev_guc = row[2] if row[2] is not None else 0
                dev_volt = round(float(row[3]), 1) if row[3] is not None else 0
                dev_akim = round(float(row[4]), 2) if row[4] is not None else 0
                dev_temp = round(utils.normalize_temperature_value(row[5]), 1) if row[5] is not None else 0
                dev_hata = (row[6] if len(row) > 6 and row[6] else 0) or (row[7] if len(row) > 7 and row[7] else 0)

                durum_renk = "#ef4444" if dev_hata else ("#10b981" if dev_guc > 0 else "#f59e0b")
                durum_text = "ARIZA" if dev_hata else ("AKTIF" if dev_guc > 0 else "BEKLEMEDE")

                with gauge_cols[col_idx]:
                    fig_gauge = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=dev_guc,
                        title={'text': f"ID:{dev_id}", 'font': {'size': 14, 'color': '#94a3b8', 'family': 'Inter'}},
                        number={'suffix': 'kW', 'font': {'size': 22, 'color': durum_renk, 'family': 'Inter'}},
                        gauge={
                            'axis': {'range': [0, 1000], 'tickcolor': '#334155', 'tickfont': {'color': '#475569'}},
                            'bar': {'color': durum_renk},
                            'bgcolor': 'rgba(15, 23, 42, 0.6)',
                            'borderwidth': 1,
                            'bordercolor': 'rgba(255, 255, 255, 0.06)',
                            'steps': [
                                {'range': [0, max(dev_guc * 1.5, 1000) * 0.3], 'color': 'rgba(15, 23, 42, 0.4)'},
                                {'range': [max(dev_guc * 1.5, 1000) * 0.3, max(dev_guc * 1.5, 1000) * 0.7], 'color': 'rgba(30, 41, 59, 0.4)'},
                                {'range': [max(dev_guc * 1.5, 1000) * 0.7, max(dev_guc * 1.5, 1000)], 'color': 'rgba(99, 102, 241, 0.08)'},
                            ],
                        },
                    ))
                    fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=185, margin=dict(l=20, r=20, t=40, b=10), font=dict(color='#94a3b8', family='Inter'))
                    st.plotly_chart(fig_gauge, width='stretch', key=f"gauge_dyn_{dev_id}")

                    st.markdown(
                        f'<div style="text-align:center; font-size:0.85rem; color:#94a3b8; margin-top:-10px; font-family: Inter, sans-serif;">'
                        f'{dev_volt:.1f}V &nbsp; {dev_akim:.2f}A &nbsp; {dev_temp:.1f}°C'
                        f' &nbsp; | &nbsp; <span style="color:{durum_renk};font-weight:700;">{durum_text}</span>'
                        f'</div>', unsafe_allow_html=True
                    )

        # Tablo Guncelleme
        df_sum = pd.DataFrame([row[:6] for row in summary_data], columns=["ID", "Son Zaman", "Guc (W)", "Voltaj (V)", "Akim (A)", "Isi (C)"])
        df_sum["Son Zaman"] = pd.to_datetime(df_sum["Son Zaman"], format='mixed', errors='coerce').dt.strftime('%H:%M:%S')
        df_sum[df_sum.columns[-1]] = pd.to_numeric(df_sum[df_sum.columns[-1]], errors='coerce').fillna(0).apply(utils.normalize_temperature_value).round(1)
        table_spot.dataframe(df_sum.set_index("ID"), width='stretch')

    # 2. PLOTLY GRAFIK GUNCELLEME (Tekli)
    detail_data = veritabani.son_verileri_getir(selected_id, limit=100, fabrika_id=fab_id)
    if detail_data:
        try:
            cols_det = ["timestamp", "guc", "voltaj", "akim", "sicaklik", "hata_kodu", "hata_kodu_109", "hata_kodu_111", "hata_kodu_112", "hata_kodu_114", "hata_kodu_115", "hata_kodu_116", "hata_kodu_117", "hata_kodu_118", "hata_kodu_119", "hata_kodu_120", "hata_kodu_121", "hata_kodu_122"]
            df_det = pd.DataFrame(detail_data, columns=cols_det[:len(detail_data[0])] if detail_data else cols_det)
            
            df_det["timestamp"] = pd.to_datetime(df_det["timestamp"], format='mixed', errors='coerce')
            df_det["guc"] = pd.to_numeric(df_det["guc"], errors='coerce')
            df_det["voltaj"] = pd.to_numeric(df_det["voltaj"], errors='coerce')
            df_det["akim"] = pd.to_numeric(df_det["akim"], errors='coerce')
            df_det["sicaklik"] = pd.to_numeric(df_det["sicaklik"], errors='coerce').apply(utils.normalize_temperature_value)
            df_det = df_det[
                ~(
                    df_det["guc"].fillna(0).eq(0)
                    & df_det["voltaj"].fillna(0).eq(0)
                    & df_det["akim"].fillna(0).eq(0)
                    & df_det["sicaklik"].fillna(0).eq(0)
                )
            ]
            if df_det.empty:
                pass
            else:
                df_det = df_det.dropna(subset=['timestamp']).sort_values("timestamp", ascending=True)
                df_det = df_det.set_index("timestamp")

                chart_guc.plotly_chart(create_plotly_chart(df_det, "guc", " Guc", "rgb(255,215,0)", "W"), width='stretch')
                chart_volt.plotly_chart(create_plotly_chart(df_det, "voltaj", " Voltaj", "rgb(99,102,241)", "V"), width='stretch')
                chart_akim.plotly_chart(create_plotly_chart(df_det, "akim", "Akim", "rgb(16,185,129)", "A"), width='stretch')
                chart_isi.plotly_chart(create_plotly_chart(df_det, "sicaklik", "Sicaklik", "rgb(239,83,80)", "C"), width='stretch')
        except Exception as e:
            st.error(f"Grafik verisi islenirken hata: {e}")

    # 3. KARILATIRMA GRAFII
    if karsilastirma_ids:
        colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#a855f7', '#f97316', '#22d3ee', '#e879f9']
        metrik_labels = {"guc": " Guc Karslastrma (W)", "voltaj": " Voltaj Karslastrma (V)",
                         "akim": " Akm Karslastrma (A)", "sicaklik": " Scaklk Karslastrma (C)"}
        
        chart_karsilastirma.plotly_chart(
            create_comparison_chart(karsilastirma_ids, karsilastirma_metrik, metrik_labels[karsilastirma_metrik], colors),
            width='stretch'
        )

    # Collector durumunu kontrol et
    collector_aktif = False
    veri_bos_gorunuyor = False
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

    with status_spot:
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

guncel_verileri_goster()
