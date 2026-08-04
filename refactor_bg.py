import sys

with open("1_PANEL.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the base64 reading part
old_part = """    import base64
    import os
    bg_path = os.path.join("static", "bg.jpg")
    if os.path.exists(bg_path):
        with open(bg_path, "rb") as f:
            bg_b64 = base64.b64encode(f.read()).decode()
        bg_url = f"url('data:image/jpeg;base64,{bg_b64}')"
    else:
        bg_url = "linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)"

    st.markdown(\"""
    <style>
    .stApp {
        background: \""" + bg_url + \""" no-repeat center center fixed !important;
        background-size: cover !important;
    }"""

new_part = """    st.markdown(\"""
    <style>
    .stApp, [data-testid="stAppViewContainer"] {
        background: url('/app/static/bg.jpg') no-repeat center center fixed !important;
        background-size: cover !important;
    }"""

content = content.replace(old_part, new_part)

with open("1_PANEL.py", "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS")
