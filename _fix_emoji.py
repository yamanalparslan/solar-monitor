import os, sys, re

sys.stdout.reconfigure(encoding='utf-8')

replacements = {
    '📂': '[DB]',
    '⚠️': '[WARN]',
    '🧹': '[CLEAN]',
    '✅': '[OK]',
    '❌': '[FAIL]',
    '📡': '[MODBUS]',
    '⏱️': '[TIME]',
    '🔢': '[IDS]',
    '📊': '[STAT]',
    '♾️': '[INF]',
    '🗄️': '[STORE]',
    '🔄': '[RELOAD]',
    '🚀': '[START]',
}

root = r'c:\Users\ARGE TEST\Desktop\TCP_analiz_test-main'
files = ['veritabani.py', 'collector.py']

for fname in files:
    fpath = os.path.join(root, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    changed = False
    for emoji, ascii_rep in replacements.items():
        if emoji in content:
            content = content.replace(emoji, ascii_rep)
            changed = True
    
    # Also replace any remaining non-ASCII in print() lines with safe versions
    # Turkish chars are fine for Streamlit but not for console print()
    
    if changed:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed: {fname}')
    else:
        print(f'No changes: {fname}')

print('Done')
