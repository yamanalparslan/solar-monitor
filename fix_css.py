import re
with open('auth.py', 'r', encoding='utf-8') as f:
    content = f.read()

def replacer(match):
    css_block = match.group(1)
    css_block = css_block.replace("{{", "{").replace("}}", "}")
    return '_LOGIN_CSS_TEMPLATE = """' + css_block + '"""'

new_content = re.sub(r'_LOGIN_CSS_TEMPLATE = """([\s\S]*?)"""', replacer, content)

with open('auth.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Done")
