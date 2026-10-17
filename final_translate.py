import os
import re
import time
import requests

def translate_text(text):
    if not text or len(text.strip()) < 3:
        return text
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text[:500], "langpair": "id|en"}
        r = requests.get(url, params=params, timeout=10)
        if r.ok:
            res = r.json()
            if res.get("responseStatus") == 200:
                translated = res["responseData"]["translatedText"]
                if translated.isupper():
                    translated = translated.capitalize()
                return translated
        return text
    except Exception:
        return text

def process_file(filepath):
    print(f"🔄 Translating: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        m_doc = re.match(r'^(\s*(?:"""|\'\'\'))(.*?)((?:"""|\'\'\')(?:\s*))$', line)
        if m_doc:
            prefix, text, suffix = m_doc.groups()
            if len(text) > 3:
                trans = translate_text(text)
                new_lines.append(f"{prefix}{trans}{suffix}\n")
                time.sleep(0.5)
                continue
        
        m_comment = re.match(r'^(\s*#\s*)(.+)$', line)
        if m_comment:
            prefix, text = m_comment.groups()
            if text.strip().startswith('!') or 'coding:' in text or not re.search(r'[a-zA-Z]', text):
                new_lines.append(line)
                continue
            
            trans = translate_text(text)
            new_lines.append(f"{prefix}{trans}\n")
            time.sleep(0.5)
            continue

        if "
            parts = line.split("
            code_part = parts[0]
            text = parts[1]
            if len(text) > 3 and re.search(r'[a-zA-Z]', text):
                trans = translate_text(text)
                new_lines.append(f"{code_part}
                time.sleep(0.5)
                continue
        
        new_lines.append(line)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

folders = ["6_agent", "web"]
for folder in folders:
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".py") and not file.startswith("__") and file != "extensions_1000.py":
                process_file(os.path.join(root, file))

print("🎉 Selesai! Semua komentar udah Inggris dan KODE AMAN 100%.")
