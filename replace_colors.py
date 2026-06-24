import glob, os

files = glob.glob('*.py') + glob.glob('pages/*.py')

replacements = {
    "color='#1D1D1F'": "color='#1D1D1F'",
    "color='#86868B'": "color='#86868B'",
    "color='#1D1D1F'": "color='#1D1D1F'",
    "color='#1D1D1F'": "color='#1D1D1F'",
    "color: '#86868B'": "color: '#86868B'",
    "color: '#1D1D1F'": "color: '#1D1D1F'",
    "color: '#1D1D1F'": "color: '#1D1D1F'",
    "color:#1D1D1F": "color:#1D1D1F",
    "color:#86868B": "color:#86868B",
    "color:#FF3B30": "color:#FF3B30",
    "color:#0071E3": "color:#0071E3",
    "color:#34C759": "color:#34C759",
    "color:#0071E3": "color:#0071E3",
    "rgba(0,0,0,0.1)": "rgba(0,0,0,0.1)",
    "rgba(0,0,0,0.05)": "rgba(0,0,0,0.05)",
    "rgba(0,0,0,0)": "rgba(0,0,0,0)",
    "rgba(0,0,0,0)": "rgba(0,0,0,0)",
    "rgba(255,255,255,0.95)": "rgba(255,255,255,0.95)",
    "bgcolor='rgba(255,255,255,0)'": "bgcolor='rgba(255,255,255,0)'"
}

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements.items():
        new_content = new_content.replace(old, new)
        
    if content != new_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Updated:', filepath)
