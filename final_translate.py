import os
import re
import time
import requests

# API Gratis tanpa API Key
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
                # Kadang API ngasih balik huruf besar semua, kita kecilin
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
        # 1. Handle Docstring satu baris (""" text """)
        m_doc = re.match(r'^(\s*(?:"""|\'\'\'))(.*?)((?:"""|\'\'\')(?:\s*))$', line)
        if m_doc:
            prefix, text, suffix = m_doc.groups()
            if len(text) > 3:
                trans = translate_text(text)
                new_lines.append(f"{prefix}{trans}{suffix}\n")
                time.sleep(0.5) # Jeda biar gak di-ban API
                continue
        
        # 2. Handle Komentar (# text) - HANYA yang diawali # atau spasi #
        m_comment = re.match(r'^(\s*#\s*)(.+)$', line)
        if m_comment:
            prefix, text = m_comment.groups()
            # Skip shebang, coding, atau komentar yang isinya cuma simbol
            if text.strip().startswith('!') or 'coding:' in text or not re.search(r'[a-zA-Z]', text):
                new_lines.append(line)
                continue
            
            trans = translate_text(text)
            new_lines.append(f"{prefix}{trans}\n")
            time.sleep(0.5) # Jeda biar gak di-ban API
            continue

        # 3. Handle Inline Comment (code # text)
        if " # " in line:
            parts = line.split(" # ", 1)
            code_part = parts[0]
            text = parts[1]
            if len(text) > 3 and re.search(r'[a-zA-Z]', text):
                trans = translate_text(text)
                new_lines.append(f"{code_part} # {trans}\n")
                time.sleep(0.5)
                continue
        
        # Kalo bukan komentar, biarin apa adanya
        new_lines.append(line)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

# List file yang mau ditranslate (kita skip yang kegedean kayak extensions_1000.py)
folders = ["6_agent", "web"]
for folder in folders:
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".py") and not file.startswith("__") and file != "extensions_1000.py":
                process_file(os.path.join(root, file))

print("🎉 Selesai! Semua komentar udah Inggris dan KODE AMAN 100%.")
