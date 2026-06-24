import glob

# Add to config.toml
with open('.streamlit/config.toml', 'a', encoding='utf-8') as f:
    f.write('\n[client]\nshowSidebarNavigation = false\n')

# Remove  usage from all files
files = glob.glob('*.py') + glob.glob('pages/*.py')
for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove the call to 
    new_content = content.replace("", "")
    
    # Optional: in auth.py, we can leave the definition, but just not call it.
    
    # In 1_PANEL.py, also change initial_sidebar_state="expanded" to "collapsed"
    if "1_PANEL.py" in filepath:
        new_content = new_content.replace('initial_sidebar_state="expanded"', 'initial_sidebar_state="collapsed"')
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
