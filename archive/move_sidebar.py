import sys

with open("1_PANEL.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
sidebar_lines = []

in_sidebar = False

# We will also insert render_top_nav() after inject_glossy_css()
# and import render_top_nav from styles.

# First pass to find "from styles import" and inject render_top_nav
for i, line in enumerate(lines):
    if "from styles import" in line and "render_top_nav" not in line:
        lines[i] = line.replace("from styles import", "from styles import render_top_nav,")
        break

for i, line in enumerate(lines):
    if line.strip() == "with st.sidebar:":
        in_sidebar = True
        sidebar_lines.append("st.markdown('<div style=\"margin-top: 50px;\"></div>', unsafe_allow_html=True)\n")
        sidebar_lines.append("st.subheader('SİSTEM VE CİHAZ AYARLARI')\n")
        sidebar_lines.append("with st.container():\n")
        continue
    
    if in_sidebar:
        # Check if we exited the with st.sidebar: block. The block is indented by 4 spaces.
        if line.strip() and not line.startswith("    "):
            in_sidebar = False
            new_lines.append(line)
        else:
            sidebar_lines.append(line)
    else:
        new_lines.append(line)

# Also we need to call render_top_nav() after inject_glossy_css
final_lines = []
for line in new_lines:
    final_lines.append(line)
    if "inject_glossy_css(" in line:
        final_lines.append("    render_top_nav()\n")

# Append sidebar lines at the very end
final_lines.extend(sidebar_lines)

with open("1_PANEL.py", "w", encoding="utf-8") as f:
    f.writelines(final_lines)
