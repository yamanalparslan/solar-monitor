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
/*  GOOGLE FONT  */
@import url('https://fonts.googleapis.com/css2Infinitefamily=Inter:wght@300;400;500;600;700;800&display=swap');

/*  ROOT DEKENLER  */
:root {
    --bg-primary: #0a0e1a;
    --bg-secondary: #111827;
    --bg-card: rgba(17, 24, 39, 0.7);
    --bg-glass: rgba(255, 255, 255, 0.03);
    --border-glass: rgba(255, 255, 255, 0.08);
    --border-glow: rgba(99, 102, 241, 0.3);
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent-blue: #6366f1;
    --accent-cyan: #22d3ee;
    --accent-green: #10b981;
    --accent-amber: #f59e0b;
    --accent-red: #ef4444;
    --accent-pink: #ec4899;
    --gradient-primary: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
    --gradient-success: linear-gradient(135deg, #10b981 0%, #34d399 100%);
    --gradient-danger: linear-gradient(135deg, #ef4444 0%, #f97316 100%);
    --gradient-info: linear-gradient(135deg, #3b82f6 0%, #22d3ee 100%);
    --shadow-glow: 0 0 20px rgba(99, 102, 241, 0.15);
    --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.4);
    --radius: 16px;
    --radius-sm: 10px;
    --radius-lg: 20px;
}

/*  BASE TEMA  */
html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

.stApp {
    background: 
        radial-gradient(ellipse at 20% 50%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 20%, rgba(34, 211, 238, 0.05) 0%, transparent 50%),
        radial-gradient(ellipse at 50% 80%, rgba(168, 85, 247, 0.05) 0%, transparent 50%),
        var(--bg-primary) !important;
}

/*  SCROLLBAR  */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(99, 102, 241, 0.5); }

/*  BALIKLAR  */
h1 {
    background: var(--gradient-primary) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    font-weight: 800 !important;
    letter-spacing: -0.5px !important;
}
h2 {
    color: var(--text-primary) !important;
    font-weight: 700 !important;
    letter-spacing: -0.3px !important;
}
h3 {
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
}

/*  SIDEBAR (GLASSMORPHISM)  */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, 
        rgba(15, 23, 42, 0.95) 0%, 
        rgba(10, 14, 26, 0.98) 100%) !important;
    border-right: 1px solid var(--border-glass) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2 {
    font-size: 1rem !important;
    color: var(--text-secondary) !important;
    -webkit-text-fill-color: var(--text-secondary) !important;
    background: none !important;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

/*  METRK KARTLARI (GLOSSY)  */
div[data-testid="stMetric"] {
    background: linear-gradient(145deg, 
        rgba(30, 41, 59, 0.8) 0%, 
        rgba(15, 23, 42, 0.6) 100%) !important;
    border: 1px solid var(--border-glass) !important;
    border-radius: var(--radius) !important;
    padding: 20px 24px !important;
    box-shadow: var(--shadow-card), inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    position: relative;
    overflow: hidden;
}
div[data-testid="stMetric"]::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--gradient-primary);
    border-radius: var(--radius) var(--radius) 0 0;
}
div[data-testid="stMetric"]:hover {
    border-color: var(--border-glow) !important;
    box-shadow: var(--shadow-glow), var(--shadow-card), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
    transform: translateY(-2px);
}
div[data-testid="stMetricValue"] {
    font-size: 1.8rem !important;
    font-weight: 800 !important;
    background: var(--gradient-info) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
}
div[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
}
div[data-testid="stMetricDelta"] {
    font-weight: 600 !important;
}

/*  DATAFRAME / TABLO (DARK GLASS)  */
div[data-testid="stDataFrame"],
.stDataFrame {
    border-radius: var(--radius) !important;
    overflow: hidden !important;
    border: 1px solid var(--border-glass) !important;
    box-shadow: var(--shadow-card) !important;
}
div[data-testid="stDataFrame"] > div {
    border-radius: var(--radius) !important;
}

/*  BUTONLAR (GLOSSY)  */
.stButton > button {
    background: linear-gradient(145deg, 
        rgba(99, 102, 241, 0.2) 0%, 
        rgba(139, 92, 246, 0.15) 100%) !important;
    border: 1px solid rgba(99, 102, 241, 0.3) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    padding: 10px 24px !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 12px rgba(99, 102, 241, 0.1) !important;
    backdrop-filter: blur(8px) !important;
    -webkit-backdrop-filter: blur(8px) !important;
}
.stButton > button:hover {
    background: linear-gradient(145deg, 
        rgba(99, 102, 241, 0.35) 0%, 
        rgba(139, 92, 246, 0.3) 100%) !important;
    border-color: rgba(99, 102, 241, 0.5) !important;
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.25) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="primary"] {
    background: var(--gradient-primary) !important;
    border: none !important;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 24px rgba(99, 102, 241, 0.45) !important;
}

/*  INPUT / SELECT / SLIDER  */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid var(--border-glass) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.2s ease !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus {
    border-color: var(--accent-blue) !important;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15) !important;
}

/*  EXPANDER (GLASSMORPHISM)  */
div[data-testid="stExpander"] {
    background: linear-gradient(145deg, 
        rgba(30, 41, 59, 0.5) 0%, 
        rgba(15, 23, 42, 0.3) 100%) !important;
    border: 1px solid var(--border-glass) !important;
    border-radius: var(--radius) !important;
    backdrop-filter: blur(8px) !important;
    -webkit-backdrop-filter: blur(8px) !important;
}

/*  TABS  */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(15, 23, 42, 0.5) !important;
    border-radius: var(--radius-sm) !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid var(--border-glass) !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.2s ease !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: rgba(99, 102, 241, 0.2) !important;
    color: var(--text-primary) !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: var(--gradient-primary) !important;
    border-radius: 8px;
}

/*  INFO / WARNING / ERROR / SUCCESS  */
div[data-testid="stAlert"] {
    border-radius: var(--radius-sm) !important;
    backdrop-filter: blur(8px) !important;
    -webkit-backdrop-filter: blur(8px) !important;
    border: 1px solid var(--border-glass) !important;
}

/*  DOWNLOAD BUTTON  */
.stDownloadButton > button {
    background: linear-gradient(145deg, 
        rgba(16, 185, 129, 0.2) 0%, 
        rgba(52, 211, 153, 0.15) 100%) !important;
    border: 1px solid rgba(16, 185, 129, 0.3) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--accent-green) !important;
    font-weight: 600 !important;
}
.stDownloadButton > button:hover {
    background: linear-gradient(145deg, 
        rgba(16, 185, 129, 0.35) 0%, 
        rgba(52, 211, 153, 0.3) 100%) !important;
    box-shadow: 0 4px 20px rgba(16, 185, 129, 0.2) !important;
}

/*  DIVIDER  */
hr {
    border-color: var(--border-glass) !important;
    opacity: 0.5 !important;
}

/*  SELECTBOX  */
div[data-testid="stSelectbox"] > div > div {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid var(--border-glass) !important;
    border-radius: var(--radius-sm) !important;
}

/*  MULTISELECT  */
div[data-testid="stMultiSelect"] > div > div {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid var(--border-glass) !important;
    border-radius: var(--radius-sm) !important;
}

/*  DATE INPUT  */
div[data-testid="stDateInput"] > div > div > input {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid var(--border-glass) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
}

/*  CUSTOM CARD COMPONENT  */
.glossy-card {
    background: linear-gradient(145deg, 
        rgba(30, 41, 59, 0.7) 0%, 
        rgba(15, 23, 42, 0.5) 100%);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.glossy-card:hover {
    border-color: rgba(99, 102, 241, 0.2);
    box-shadow: 0 0 20px rgba(99, 102, 241, 0.1), 0 4px 24px rgba(0, 0, 0, 0.3);
    transform: translateY(-2px);
}
.glossy-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
}

/*  STATUS BAR  */
.status-active {
    background: linear-gradient(145deg, 
        rgba(16, 185, 129, 0.15) 0%, 
        rgba(5, 46, 22, 0.3) 100%);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-left: 4px solid #10b981;
    padding: 14px 20px;
    border-radius: 12px;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    font-family: 'Inter', sans-serif;
    color: #a7f3d0;
    box-shadow: 0 2px 12px rgba(16, 185, 129, 0.1);
}
.status-idle {
    background: linear-gradient(145deg, 
        rgba(99, 102, 241, 0.1) 0%, 
        rgba(23, 37, 84, 0.3) 100%);
    border: 1px solid rgba(99, 102, 241, 0.15);
    border-left: 4px solid #6366f1;
    padding: 14px 20px;
    border-radius: 12px;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    font-family: 'Inter', sans-serif;
    color: #c7d2fe;
    box-shadow: 0 2px 12px rgba(99, 102, 241, 0.08);
}

/*  ALARM KARTLARI  */
.alarm-card-error {
    background: linear-gradient(145deg, 
        rgba(239, 68, 68, 0.12) 0%, 
        rgba(127, 29, 29, 0.2) 100%);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-left: 4px solid #ef4444;
    padding: 18px 22px;
    border-radius: 14px;
    margin: 10px 0;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 2px 16px rgba(239, 68, 68, 0.1);
    transition: all 0.3s ease;
}
.alarm-card-error:hover {
    border-color: rgba(239, 68, 68, 0.4);
    box-shadow: 0 4px 24px rgba(239, 68, 68, 0.15);
    transform: translateY(-1px);
}
.alarm-card-ok {
    background: linear-gradient(145deg, 
        rgba(16, 185, 129, 0.08) 0%, 
        rgba(6, 78, 59, 0.15) 100%);
    border: 1px solid rgba(16, 185, 129, 0.15);
    border-left: 4px solid #10b981;
    padding: 18px 22px;
    border-radius: 14px;
    margin: 10px 0;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: 0 2px 16px rgba(16, 185, 129, 0.06);
}


/*  BADGE / CHIP  */
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-family: 'Inter', sans-serif;
}
.badge-danger {
    background: rgba(239, 68, 68, 0.15);
    color: #fca5a5;
    border: 1px solid rgba(239, 68, 68, 0.25);
}
.badge-success {
    background: rgba(16, 185, 129, 0.15);
    color: #6ee7b7;
    border: 1px solid rgba(16, 185, 129, 0.25);
}
.badge-warning {
    background: rgba(245, 158, 11, 0.15);
    color: #fde68a;
    border: 1px solid rgba(245, 158, 11, 0.25);
}
.badge-info {
    background: rgba(99, 102, 241, 0.15);
    color: #a5b4fc;
    border: 1px solid rgba(99, 102, 241, 0.25);
}

/*  SECTION HEADER  */
.section-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 20px 0 16px 0;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-glass);
}
.section-header .icon {
    font-size: 1.5rem;
}
.section-header .title {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-primary);
    font-family: 'Inter', sans-serif;
    letter-spacing: -0.3px;
}
.section-header .subtitle {
    font-size: 0.8rem;
    color: var(--text-muted);
    font-family: 'Inter', sans-serif;
}

/*  KPI ROW  */
.kpi-container {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}
.kpi-card {
    flex: 1;
    min-width: 160px;
    background: linear-gradient(145deg, 
        rgba(30, 41, 59, 0.7) 0%, 
        rgba(15, 23, 42, 0.5) 100%);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(12px);
    transition: all 0.3s ease;
}
.kpi-card:hover {
    transform: translateY(-2px);
    border-color: rgba(99, 102, 241, 0.2);
}
.kpi-value {
    font-size: 1.8rem;
    font-weight: 800;
    font-family: 'Inter', sans-serif;
    letter-spacing: -1px;
}
.kpi-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-top: 4px;
    font-family: 'Inter', sans-serif;
}

/*  RESPONSIVE  */
@media (max-width: 768px) {
    div[data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
    }
    .main .block-container {
        padding: 0.5rem 0.8rem !important;
    }
    div[data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
    }
    div[data-testid="stHorizontalBlock"] > div {
        width: 100% !important;
        flex: none !important;
    }
    h1 {
        font-size: 1.5rem !important;
    }
    .kpi-container {
        gap: 8px;
    }
    .kpi-card {
        min-width: 120px;
        padding: 14px;
    }
    .kpi-value {
        font-size: 1.3rem;
    }
}

/*  ANIMASYONLAR  */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 8px rgba(99, 102, 241, 0.2); }
    50% { box-shadow: 0 0 18px rgba(99, 102, 241, 0.35); }
}
.animate-in {
    animation: fadeInUp 0.4s ease-out;
}
.pulse {
    animation: pulse-glow 2s infinite;
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


def alarm_card(device_id: int, has_error: bool, content_html: str):
    """Alarm kart oluturur."""
    cls = "alarm-card-error" if has_error else "alarm-card-ok"
    st.markdown(f'<div class="{cls}">{content_html}</div>', unsafe_allow_html=True)



