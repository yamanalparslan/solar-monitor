"""
Solar Monitor - Premium Glossy UI Tema Sistemi
================================================
Tm Streamlit sayfalarnda kullanlan glassmorphism + glossy
CSS tanmlamalar. Merkezi tema ynetimi.

Kullanm:
    from styles import inject_glossy_css
    inject_glossy_css()
"""

import streamlit as st

# 
#  ANA GLOSSY TEMA CSS
# 

GLOSSY_CSS = """
<style>
/*  GOOGLE FONT (Apple-like)  */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700;800&display=swap');

/*  ROOT DEKENLER - APPLE SMOOTH & MINIMALIST LIGHT THEME  */
:root {
    --bg-primary: #F5F5F7;
    --bg-secondary: #FFFFFF;
    --bg-card: rgba(255, 255, 255, 0.75);
    --bg-glass: rgba(255, 255, 255, 0.6);
    --border-glass: rgba(0, 0, 0, 0.06);
    --border-glow: rgba(0, 113, 227, 0.3);
    --text-primary: #1D1D1F;
    --text-secondary: #86868B;
    --text-muted: #A1A1A6;
    --accent-blue: #0071E3;
    --accent-indigo: #0071E3;
    --accent-cyan: #32ADE6;
    --accent-green: #34C759;
    --accent-amber: #FF9F0A;
    --accent-red: #FF3B30;
    --gradient-primary: linear-gradient(135deg, #0071E3 0%, #47A1FF 100%);
    --gradient-success: linear-gradient(135deg, #34C759 0%, #30D158 100%);
    --gradient-danger: linear-gradient(135deg, #FF3B30 0%, #FF453A 100%);
    --gradient-info: linear-gradient(135deg, #0071E3 0%, #32ADE6 100%);
    --shadow-glow: 0 0 20px rgba(0, 113, 227, 0.15);
    --shadow-card: 0 8px 30px rgba(0, 0, 0, 0.04);
    --radius: 20px;
    --radius-sm: 12px;
    --radius-lg: 32px;
}

/*  BASE TEMA  */
html, body, .stApp {
    font-family: -apple-system, BlinkMacSystemFont, 'Outfit', 'Inter', sans-serif !important;
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

.stApp {
    background: var(--bg-primary) !important;
}

/* GİZLİ STREAMLIT BİLEŞENLERİ */
[data-testid="stHeader"] { display: none !important; visibility: hidden !important; background: transparent !important; height: 0px !important; }
header[data-testid="stHeader"] { display: none !important; visibility: hidden !important; background: transparent !important; height: 0px !important; }
#MainMenu { visibility: hidden !important; display: none !important; }
.stDeployButton { display: none !important; }
header { visibility: hidden !important; display: none !important; background: transparent !important; height: 0px !important; }


/*  PAGE FADE-IN-UP ANIMATION  */
@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(24px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Apply animation to elements inside block-container EXCEPT the parent of top nav */
.block-container > div > div > div:not(:has(.top-nav-wrapper)) {
    animation: fadeInUp 0.7s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
}

/*  SCROLLBAR  */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.15); border-radius: 10px; border: 2px solid var(--bg-primary); }
::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.3); }

/*  BALIKLAR  */
h1 {
    color: var(--text-primary) !important;
    font-weight: 700 !important;
    letter-spacing: -0.8px !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Outfit', sans-serif !important;
}
h2 {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    letter-spacing: -0.5px !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Outfit', sans-serif !important;
}
h3 {
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
}

/*  SIDEBAR GIZLEME (APPLE TOP NAV ICIN)  */
[data-testid="collapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; width: 0 !important; }

/*  METRK KARTLARI (SMOOTH & MINIMAL)  */
div[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-glass) !important;
    border-radius: var(--radius) !important;
    padding: 24px 28px !important;
    box-shadow: var(--shadow-card) !important;
    backdrop-filter: blur(20px) saturate(180%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
    transition: all 0.3s cubic-bezier(0.25, 0.1, 0.25, 1) !important;
    position: relative;
    overflow: hidden;
}
div[data-testid="stMetric"]:hover {
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.08) !important;
    transform: translateY(-2px);
}
div[data-testid="stMetricValue"] {
    font-size: 2.4rem !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Outfit', sans-serif !important;
    letter-spacing: -1px;
}
div[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    margin-bottom: 4px !important;
}
div[data-testid="stMetricDelta"] {
    font-weight: 500 !important;
    padding-top: 4px;
}

/*  DATAFRAME / TABLO  */
div[data-testid="stDataFrame"],
.stDataFrame {
    border-radius: var(--radius-sm) !important;
    overflow: hidden !important;
    border: 1px solid var(--border-glass) !important;
    box-shadow: var(--shadow-card) !important;
    background: #FFFFFF !important;
}

/*  BUTONLAR (APPLE STYLE)  */
.stButton > button {
    background: rgba(0, 113, 227, 0.05) !important;
    border: 1px solid rgba(0, 113, 227, 0.15) !important;
    border-radius: 980px !important; /* Fully rounded buttons like Apple */
    color: var(--accent-blue) !important;
    font-weight: 500 !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Outfit', sans-serif !important;
    padding: 10px 24px !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.3px;
}
.stButton > button:hover {
    background: rgba(0, 113, 227, 0.1) !important;
    transform: scale(1.02) !important;
}
.stButton > button[kind="primary"] {
    background: var(--accent-blue) !important;
    border: none !important;
    color: white !important;
    box-shadow: 0 4px 14px rgba(0, 113, 227, 0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #0077ED !important;
    box-shadow: 0 6px 20px rgba(0, 113, 227, 0.4) !important;
}

/*  INPUT / SELECT / SLIDER  */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
    background: #FFFFFF !important;
    border: 1px solid rgba(0,0,0,0.1) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif !important;
    padding: 12px 16px !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 5px rgba(0,0,0,0.02) !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus {
    border-color: var(--accent-blue) !important;
    box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.15) !important;
}

/*  EXPANDER  */
div[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-glass) !important;
    border-radius: var(--radius-sm) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    box-shadow: var(--shadow-card) !important;
}

/*  TABS (APPLE STYLE SEGMENTED CONTROL)  */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(0, 0, 0, 0.05) !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: none !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Outfit', sans-serif !important;
    padding: 8px 16px !important;
    transition: all 0.2s ease !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text-primary) !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: #FFFFFF !important;
    color: var(--text-primary) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    display: none !important; /* Hide the bottom line in Apple style */
}

/*  INFO / WARNING / ERROR / SUCCESS  */
div[data-testid="stAlert"] {
    border-radius: var(--radius-sm) !important;
    border: 1px solid var(--border-glass) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
    background: #FFFFFF !important;
}

/*  DOWNLOAD BUTTON  */
.stDownloadButton > button {
    background: rgba(52, 199, 89, 0.1) !important;
    border: 1px solid rgba(52, 199, 89, 0.2) !important;
    border-radius: 980px !important;
    color: #248A3D !important;
    font-weight: 500 !important;
    box-shadow: none !important;
}
.stDownloadButton > button:hover {
    background: rgba(52, 199, 89, 0.15) !important;
    transform: scale(1.02) !important;
}

/*  DIVIDER  */
hr {
    border-color: rgba(0,0,0,0.08) !important;
    margin: 2rem 0 !important;
}

/*  SELECTBOX & MULTISELECT  */
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stMultiSelect"] > div > div {
    background: #FFFFFF !important;
    border: 1px solid rgba(0,0,0,0.1) !important;
    border-radius: var(--radius-sm) !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stSelectbox"] > div > div:hover,
div[data-testid="stMultiSelect"] > div > div:hover {
    border-color: rgba(0,0,0,0.2) !important;
}

/*  DATE INPUT  */
div[data-testid="stDateInput"] > div > div > input {
    background: #FFFFFF !important;
    border: 1px solid rgba(0,0,0,0.1) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
}

/*  CUSTOM CARD COMPONENT  */
.glossy-card {
    background: var(--bg-card);
    border: 1px solid var(--border-glass);
    border-radius: var(--radius);
    padding: 32px;
    box-shadow: var(--shadow-card);
    backdrop-filter: blur(24px) saturate(180%);
    -webkit-backdrop-filter: blur(24px) saturate(180%);
    transition: all 0.3s cubic-bezier(0.25, 0.1, 0.25, 1);
    position: relative;
    overflow: hidden;
}
.glossy-card:hover {
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.08);
    transform: translateY(-2px);
}

/*  STATUS BAR  */
.status-active {
    background: rgba(52, 199, 89, 0.1);
    border: 1px solid rgba(52, 199, 89, 0.2);
    padding: 16px 24px;
    border-radius: var(--radius-sm);
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    color: #248A3D;
    font-weight: 500;
    display: flex; align-items: center; gap: 12px;
}
.status-idle {
    background: rgba(0, 113, 227, 0.08);
    border: 1px solid rgba(0, 113, 227, 0.15);
    padding: 16px 24px;
    border-radius: var(--radius-sm);
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    color: #0071E3;
    font-weight: 500;
    display: flex; align-items: center; gap: 12px;
}

/*  ALARM KARTLARI  */
.alarm-card-error {
    background: #FFFFFF;
    border: 1px solid rgba(255, 59, 48, 0.2);
    border-left: 5px solid #FF3B30;
    padding: 20px 24px;
    border-radius: var(--radius-sm);
    margin: 12px 0;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
    transition: all 0.2s ease;
    position: relative;
}
.alarm-card-error:hover {
    box-shadow: 0 8px 24px rgba(255, 59, 48, 0.1);
    transform: translateY(-2px);
}
.alarm-card-ok {
    background: #FFFFFF;
    border: 1px solid rgba(52, 199, 89, 0.2);
    border-left: 5px solid #34C759;
    padding: 20px 24px;
    border-radius: var(--radius-sm);
    margin: 12px 0;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
    transition: all 0.2s ease;
}
.alarm-card-ok:hover {
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
    transform: translateY(-2px);
}
.alarm-card-sleep {
    background: #FFFFFF;
    border: 1px solid rgba(0, 113, 227, 0.15);
    border-left: 5px solid #0071E3;
    padding: 20px 24px;
    border-radius: var(--radius-sm);
    margin: 12px 0;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
    transition: all 0.2s ease;
}
.alarm-card-sleep:hover {
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
    transform: translateY(-2px);
}

/*  BADGE / CHIP  */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 980px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}
.badge-danger {
    background: rgba(255, 59, 48, 0.1);
    color: #D70015;
}
.badge-success {
    background: rgba(52, 199, 89, 0.1);
    color: #248A3D;
}
.badge-warning {
    background: rgba(255, 149, 0, 0.1);
    color: #B25000;
}
.badge-info {
    background: rgba(0, 113, 227, 0.1);
    color: #0071E3;
}

/*  SECTION HEADER  */
.section-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin: 28px 0 20px 0;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(0,0,0,0.06);
}
.section-header .icon {
    font-size: 1.8rem;
    padding: 10px;
    background: #FFFFFF;
    border-radius: 12px;
    border: 1px solid rgba(0,0,0,0.05);
    box-shadow: 0 4px 12px rgba(0,0,0,0.04);
    color: #0071E3;
}
.section-header .title {
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, 'Outfit', sans-serif;
    letter-spacing: -0.3px;
}
.section-header .subtitle {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-top: 2px;
}

/*  KPI ROW  */
.kpi-container {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    margin-bottom: 24px;
}
.kpi-card {
    flex: 1;
    min-width: 180px;
    background: var(--bg-card);
    border: 1px solid var(--border-glass);
    border-radius: var(--radius);
    padding: 24px;
    text-align: center;
    box-shadow: var(--shadow-card);
    backdrop-filter: blur(20px) saturate(180%);
    transition: all 0.3s ease;
}
.kpi-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 30px rgba(0,0,0,0.06);
}
.kpi-value {
    font-size: 2.2rem;
    font-weight: 700;
    font-family: -apple-system, BlinkMacSystemFont, 'Outfit', sans-serif;
    letter-spacing: -1px;
    line-height: 1.1;
    margin-bottom: 4px;
    color: var(--text-primary);
}
.kpi-label {
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/*  RESPONSIVE  */
@media (max-width: 768px) {
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
    }
    .main .block-container {
        padding: 1.5rem !important;
    }
    div[data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
    }
    div[data-testid="stHorizontalBlock"] > div {
        width: 100% !important;
        flex: none !important;
    }
    h1 {
        font-size: 1.8rem !important;
    }
    .kpi-container {
        gap: 12px;
    }
    .kpi-card {
        min-width: 140px;
        padding: 18px;
    }
    .kpi-value {
        font-size: 1.8rem;
    }
}

/*  ANIMASYONLAR  */
@keyframes page-in {
    from { opacity: 0; transform: translateY(10px) scale(0.99); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
.main .block-container {
    animation: page-in 0.4s cubic-bezier(0.25, 0.1, 0.25, 1);
}

section[data-testid="stSidebar"] {
    transition: transform 0.3s cubic-bezier(0.25, 0.1, 0.25, 1), opacity 0.3s ease !important;
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
.animate-in {
    animation: fadeInUp 0.4s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.live-indicator {
    display: inline-block;
    width: 8px;
    height: 8px;
    background-color: #FF3B30;
    border-radius: 50%;
    margin-right: 8px;
    box-shadow: 0 0 6px rgba(255, 59, 48, 0.5);
    animation: blinker 1.5s linear infinite;
}
@keyframes blinker {
    50% { opacity: 0.3; }
}

/* ── Toast Bildirim ── */
@keyframes toast-in {
    from { transform: translateX(100%) scale(0.95); opacity: 0; }
    to   { transform: translateX(0) scale(1); opacity: 1; }
}
@keyframes toast-out {
    from { opacity: 1; transform: translateX(0) scale(1); }
    to   { opacity: 0; transform: translateX(100%) scale(0.95); }
}
.toast-wrap {
    position: fixed;
    bottom: 32px;
    right: 32px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 12px;
    pointer-events: none;
}
.toast {
    min-width: 280px;
    max-width: 360px;
    padding: 16px 20px;
    border-radius: 16px;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.9rem;
    font-weight: 500;
    background: rgba(255,255,255,0.9);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    box-shadow: 0 10px 40px rgba(0,0,0,0.1);
    border: 1px solid rgba(0,0,0,0.05);
    color: #1D1D1F;
    animation: toast-in 0.4s cubic-bezier(0.25, 0.1, 0.25, 1) forwards;
    pointer-events: all;
    display: flex;
    align-items: center;
}
.toast-success .toast-icon { color: #34C759; }
.toast-error .toast-icon { color: #FF3B30; }
.toast-info .toast-icon { color: #0071E3; }
.toast-icon {
    margin-right: 12px;
    font-size: 1.2rem;
}
</style>
"""


def inject_glossy_css():
    """Glossy CSS temasn Streamlit sayfasna enjekte eder."""
    st.markdown(GLOSSY_CSS, unsafe_allow_html=True)


def glossy_card(content: str, extra_class: str = ""):
    """Glossy kart bileeni oluturur."""
    st.markdown(f'<div class="glossy-card {extra_class}">{content}</div>', unsafe_allow_html=True)


def status_bar(active: bool, text: str):
    """Durum ubuu oluturur (aktif/pasif)."""
    cls = "status-active" if active else "status-idle"
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def section_header(icon: str, title: str, subtitle: str = ""):
    """Blm bal oluturur."""
    sub_html = f'<div class="subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(f'''
        <div class="section-header">
            <span class="icon">{icon}</span>
            <div>
                <div class="title">{title}</div>
                {sub_html}
            </div>
        </div>
    ''', unsafe_allow_html=True)


def badge(text: str, tipo: str = "info"):
    """Badge/chip bileeni dner (HTML string)."""
    return f'<span class="badge badge-{tipo}">{text}</span>'


def kpi_row(items: list):
    """KPI kartlar satr oluturur.
    
    Args:
        items: [{'value': '1234', 'label': 'Toplam', 'color': '#6366f1'}, ...]
    """
    cards_html = ""
    for item in items:
        color = item.get('color', '#6366f1')
        cards_html += f"""<div class="kpi-card"><div class="kpi-value" style="color: {color};">{item['value']}</div><div class="kpi-label">{item['label']}</div></div>"""
    st.markdown(f'<div class="kpi-container">{cards_html}</div>', unsafe_allow_html=True)


def alarm_card(device_id: int, status: str, content_html: str):
    """Alarm kart olusturur. status: 'error', 'ok', veya 'sleep' olabilir."""
    if status == "error":
        cls = "alarm-card-error"
    elif status == "sleep":
        cls = "alarm-card-sleep"
    else:
        cls = "alarm-card-ok"
    st.markdown(f'<div class="{cls}">{content_html}</div>', unsafe_allow_html=True)


def toast(message: str, tipo: str = "info", icon: str = ""):
    """Sag alt kosede kayan bildirim gosterir.

    Args:
        message: Gosterilecek metin
        tipo: 'success' | 'error' | 'info'
        icon: Emoji veya bos birakabilirsiniz
    """
    icon_defaults = {"success": "✅", "error": "❌", "info": "ℹ️"}
    _icon = icon or icon_defaults.get(tipo, "")
    st.markdown(
        f"""
        <div class="toast-wrap">
          <div class="toast toast-{tipo}">
            <span class="toast-icon">{_icon}</span>{message}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def solar_table(
    rows: list,
    headers: list,
    status_col_idx: int | None = None,
    status_colors: dict | None = None,
):
    """Premium HTML tablo olusturur.

    Args:
        rows: [[hucre1, hucre2, ...], ...] seklinde veri listesi
        headers: Sutun basliklarinin listesi
        status_col_idx: Renk kodlamak istedigimiz sutunun indeksi (opsiyonel)
        status_colors: {deger: renk_hex} eslestirmesi (opsiyonel)
    """
    _sc = status_colors or {}

    th_cells = "".join(f"<th>{h}</th>" for h in headers)
    body_rows = ""
    for row in rows:
        td_cells = ""
        for i, cell in enumerate(row):
            style = ""
            if status_col_idx is not None and i == status_col_idx:
                color = _sc.get(str(cell), "")
                if color:
                    style = f' style="color:{color};font-weight:600"'
            td_cells += f"<td{style}>{cell}</td>"
        body_rows += f"<tr>{td_cells}</tr>"

    html = f"""
    <style>
    .solar-table-wrap {{ overflow-x: auto; border-radius: var(--radius); }}
    .solar-table {{
        width: 100%; border-collapse: collapse;
        font-family: -apple-system, BlinkMacSystemFont, 'Outfit', 'Inter', sans-serif; font-size: 0.84rem;
    }}
    .solar-table th {{
        background: rgba(0, 113, 227, 0.05);
        padding: 10px 16px; text-align: left;
        color: #1D1D1F; text-transform: uppercase;
        letter-spacing: 0.9px; font-size: 0.71rem; font-weight: 800;
        border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        white-space: nowrap;
    }}
    .solar-table td {{
        padding: 11px 16px;
        color: #1D1D1F;
        border-bottom: 1px solid rgba(0, 0, 0, 0.04);
        transition: background 0.15s;
    }}
    .solar-table tr:hover td {{ background: rgba(0, 113, 227, 0.03); }}
    .solar-table tr:last-child td {{ border-bottom: none; }}
    </style>
    <div class="solar-table-wrap">
      <table class="solar-table">
        <thead><tr>{th_cells}</tr></thead>
        <tbody>{body_rows}</tbody>
      </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_top_nav():
    """Apple web sitesi tarzinda yatay (top) navigation bar cizer."""
    # Top navbar container CSS
    st.markdown("""
    <style>
    /* Top Navbar Wrapper */
    .top-nav-wrapper {
        position: sticky;
        top: 0;
        z-index: 999999;
        background: rgba(255, 255, 255, 0.65) !important;
        backdrop-filter: blur(40px) saturate(200%) !important;
        -webkit-backdrop-filter: blur(40px) saturate(200%) !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.5) !important;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.08) !important;
        padding: 12px 24px;
        margin-top: -60px; /* Streamlit ust boslugunu kapatmak icin */
        margin-bottom: 24px;
        margin-left: -4rem; /* Container disina tasirmak icin */
        margin-right: -4rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    /* Top Nav Links */
    .top-nav-links {
        display: flex;
        gap: 24px;
        align-items: center;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }
    .top-nav-links::-webkit-scrollbar { display: none; }
    
    .nav-link {
        color: #1D1D1F;
        text-decoration: none;
        font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
        font-size: 0.85rem;
        font-weight: 500;
        letter-spacing: -0.01em;
        white-space: nowrap;
        transition: color 0.2s ease;
        padding: 4px 8px;
        border-radius: 6px;
    }
    .nav-link:hover {
        color: #0071E3;
        background: rgba(0, 0, 0, 0.03);
    }
    .nav-logo {
        font-weight: 700;
        font-size: 1.1rem;
        color: #1D1D1F;
        margin-right: 12px;
        background: linear-gradient(135deg, #0071E3, #32ADE6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Top padding adjustment for the main content to clear the sticky navbar */
    .block-container {
        padding-top: 1rem !important;
    }
    
    /* Make page links shrink text instead of truncating */
    div[data-testid="stPageLink"] a p {
        font-size: clamp(10px, 1vw, 15px) !important;
        white-space: normal !important;
        line-height: 1.2 !important;
        text-overflow: clip !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Render the nav layout natively
    col1, col2, col3 = st.columns([1.5, 8, 1.5], vertical_alignment="center")
    
    with col1:
        if st.session_state.get('fabrika_id'):
            c_logo, c_btn = st.columns([0.75, 0.25], vertical_alignment="center")
            with c_logo:
                st.markdown("<span class='nav-logo' style='margin-right:0;'>SolarMonitor</span>", unsafe_allow_html=True)
            with c_btn:
                if st.button("🏭", help="Fabrika Değiştir"):
                    st.session_state.fabrika_id = None
                    st.switch_page("1_PANEL.py")
        else:
            st.markdown("<span class='nav-logo'>SolarMonitor</span>", unsafe_allow_html=True)
    with col2:
        if st.session_state.get('fabrika_id'):
            # Ana sayfalar
            main_pages = {
                "Panel": "1_PANEL.py",
                "Günlük Rapor": "pages/1_GUNLUK_RAPOR.py",
                "Alarmlar": "pages/2_ALARMLAR.py",
                "Karşılaştır": "pages/8_KARSILASTIR.py",
            }
            
            # Açılır menüdeki diğer sayfalar
            other_pages = {
                "Export": "pages/3_EXPORT.py",
                "Audit Log": "pages/5_AUDIT_LOG.py",
                "PDF Rapor": "pages/6_PDF_RAPOR.py",
                "Tahmin": "pages/7_TAHMIN.py",
                "Sistem": "pages/9_SISTEM.py",
                "Sanal İnverter": "pages/10_SANAL_INVERTER.py"
            }
            
            widths = [max(8, len(title)) for title in main_pages.keys()]
            widths.append(12) # Dropdown butonu için genişlik
            widths.append(50) # Boşluk (spacer)
            cols = st.columns(widths, vertical_alignment="center")
            
            for idx, (title, path) in enumerate(main_pages.items()):
                with cols[idx]:
                    st.page_link(path, label=title)
                    
            with cols[-1]:
                # Streamlit altyapısında hover ile açılan menü doğrudan desteklenmediğinden 
                # tıklama ile açılan (ve mobil uyumlu olan) yerel popover kullanıyoruz.
                with st.popover("Daha Fazla ▾", use_container_width=True):
                    for title, path in other_pages.items():
                        st.page_link(path, label=title)
                
    with col3:
        # We will render the logout button here via auth.py
        from auth import top_nav_logout_button
        top_nav_logout_button()
    
    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)
