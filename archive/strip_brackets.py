import re

file_path = "models.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace any occurrence of " [1]", "[1]", " [2]", "[2]" etc inside quotes
# Pattern: \s*\[\d+\]" -> ""
new_content = re.sub(r'\s*\[\d+\]"', '"', content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Removed bracket suffixes from models.py")
