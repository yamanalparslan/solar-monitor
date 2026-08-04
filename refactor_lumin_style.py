import sys

# 1. Update auth.py
with open("auth.py", "r", encoding="utf-8") as f:
    auth_content = f.read()

start_idx_auth = auth_content.find("_LOGIN_CSS = ")
end_idx_auth = auth_content.find("def check_auth() -> bool:")

new_auth_css = '''_LOGIN_CSS = """
<style>
/* GIZLI YAPI */
[data-testid="stSidebar"], [data-testid="stHeader"], footer, header {
    display: none !important;
    visibility: hidden !important;
    height: 0px !important;
}

/* Split Background */
.stApp, [data-testid="stAppViewContainer"] {
    background: linear-gradient(165deg, #1c2950 55%, #f4f6f9 55%) !important;
    background-size: cover !important;
    background-attachment: fixed !important;
}

/* KART TASARIMI (Solid White) */
.login-card {
    background: #ffffff !important;
    border-radius: 8px !important;
    padding: 40px 36px 40px 36px !important;
    box-shadow: 0 10px 40px rgba(0,0,0,0.08) !important;
    text-align: center;
}

.login-title {
    text-align: left;
    font-family: -apple-system, BlinkMacSystemFont, 'Outfit', sans-serif;
    font-size: 1.8rem;
    font-weight: 800;
    color: #1c2950;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 12px;
}
.login-title-icon {
    background: #2563eb;
    color: white;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 16px;
}

.login-subtitle {
    text-align: left;
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
    color: #64748b;
    margin-bottom: 24px;
}

div[data-testid="column"] > div {
    margin-top: -24px !important; 
}

/* Input Alanlari */
[data-testid="stTextInput"] input {
    background: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    color: #1e293b !important;
    border-radius: 6px !important;
    padding: 12px 14px !important;
    font-weight: 500 !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2) !important;
}
[data-testid="stTextInput"] label {
    color: #475569 !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
}

/* Buton */
[data-testid="stButton"] button {
    background: #2563eb !important;
    border: none !important;
    color: #ffffff !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    padding: 24px 12px !important;
    transition: all 0.2s ease !important;
    margin-top: 10px !important;
}
[data-testid="stButton"] button:hover {
    background: #1d4ed8 !important;
}

/* Hata Mesajlari */
[data-testid="stNotification"] {
    background: #fef2f2 !important;
    border: 1px solid #fecaca !important;
    color: #b91c1c !important;
    border-radius: 6px !important;
}
</style>
"""

'''
auth_content = auth_content[:start_idx_auth] + new_auth_css + auth_content[end_idx_auth:]

# Update the form HTML to include the icon
auth_content = auth_content.replace(
    '<div class="login-title">SOLAR MONITOR</div>',
    '<div class="login-title"><div class="login-title-icon">◑</div> <span>Solar<span style="color:white;">Monitor</span></span></div>'
)

with open("auth.py", "w", encoding="utf-8") as f:
    f.write(auth_content)


# 2. Update 1_PANEL.py
with open("1_PANEL.py", "r", encoding="utf-8") as f:
    panel_content = f.read()

start_marker = "if st.session_state.fabrika_id is None:"
end_marker = "fab_id = st.session_state.fabrika_id"

start_idx_panel = panel_content.find(start_marker)
end_idx_panel = panel_content.find(end_marker)

new_panel_css = '''if st.session_state.fabrika_id is None:
    st.markdown("""
    <style>
    /* Split Background */
    .stApp, [data-testid="stAppViewContainer"] {
        background: linear-gradient(165deg, #1c2950 55%, #f4f6f9 55%) !important;
        background-size: cover !important;
        background-attachment: fixed !important;
    }
    
    .top-nav {
        display: none !important;
    }
    
    /* Title Card */
    .factory-card-top {
        background: #ffffff !important;
        border: none !important;
        border-radius: 8px 8px 0 0 !important;
        padding: 50px 36px 10px 36px;
        text-align: center;
        box-shadow: 0 10px 40px rgba(0,0,0,0.08) !important;
        position: relative;
    }
    
    .factory-card-bottom {
        background: #ffffff !important;
        border: none !important;
        border-radius: 0 0 8px 8px !important;
        padding: 20px 36px 50px 36px !important;
        box-shadow: 0 20px 40px rgba(0,0,0,0.08) !important;
    }
    
    div[data-testid="column"] > div {
        margin-top: -24px !important; 
    }
    
    /* Buttons */
    [data-testid="stButton"] button {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        color: #1e293b !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        padding: 30px 20px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.02) !important;
        height: auto !important;
    }
    [data-testid="stButton"] button:hover {
        background: #f8fafc !important;
        border-color: #2563eb !important;
        color: #2563eb !important;
    }
    
    .login-title {
        text-align: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Outfit', sans-serif;
        font-size: 2.2rem;
        font-weight: 800;
        color: #1c2950;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
    }
    .login-title-icon {
        background: #2563eb;
        color: white;
        width: 36px;
        height: 36px;
        border-radius: 8px;
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 20px;
    }
    .login-subtitle {
        text-align: center;
        font-family: 'Outfit', sans-serif;
        font-size: 1rem;
        color: #64748b;
        margin-bottom: 0px;
        font-weight: 600;
    }
    </style>
    
    <br><br><br><br>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("""
        <div class="factory-card-top">
            <div class="login-title"><div class="login-title-icon">◑</div> <span>Solar<span style="color:white;">Monitor</span></span></div>
            <div class="login-subtitle">IZLEMEK ISTEDIGINIZ FABRIKAYI SECIN</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="factory-card-bottom">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔧 MEKANIK FABRIKA", width='stretch', type="secondary"):
                st.session_state.fabrika_id = "mekanik"
                st.rerun()
        with c2:
            if st.button("🏭 URETIM FABRIKASI", width='stretch', type="secondary"):
                st.session_state.fabrika_id = "uretim"
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

'''

panel_content = panel_content[:start_idx_panel] + new_panel_css + panel_content[end_idx_panel:]

with open("1_PANEL.py", "w", encoding="utf-8") as f:
    f.write(panel_content)

print("SUCCESS")
