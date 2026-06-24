import glob
import os

files = glob.glob('pages/*.py')

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "render_top_nav" in content:
        continue

    # Add import
    if "from styles import" in content:
        content = content.replace("from styles import", "from styles import render_top_nav,")
    else:
        # If styles isn't imported at all
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                lines.insert(i, "from styles import render_top_nav")
                break
        content = '\n'.join(lines)
    
    # Add render_top_nav() after inject_glossy_css() or inject_embed_mode()
    if "inject_glossy_css(" in content:
        content = content.replace("inject_glossy_css()", "inject_glossy_css()\n    render_top_nav()")
        content = content.replace("inject_glossy_css(True)", "inject_glossy_css(True)\n    render_top_nav()")
        content = content.replace("inject_glossy_css(False)", "inject_glossy_css(False)\n    render_top_nav()")
    elif "inject_embed_mode" in content:
        content = content.replace("hide_sidebar=False)", "hide_sidebar=False)\nrender_top_nav()")
        content = content.replace("hide_sidebar=True)", "hide_sidebar=True)\nrender_top_nav()")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
