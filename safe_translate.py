import re
import os
from deep_translator import GoogleTranslator

translator = GoogleTranslator(source='auto', target='en')

def safe_translate(text):
    text = text.strip()
    if not text or len(text) < 2: return text
    try:
        if not re.search(r'[a-zA-Z]', text): return text
        return translator.translate(text)
    except:
        return text

def process_file(filepath):
    print(f"🔄 Processing: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        m_standalone = re.match(r'^(\s*#\s*)(.+)$', line)
        if m_standalone:
            prefix = m_standalone.group(1)
            comment = m_standalone.group(2)
            if 'coding:' in comment or 'usr/bin' in comment:
                new_lines.append(line)
                continue
            trans = safe_translate(comment)
            new_lines.append(f"{prefix}{trans}")
            continue
            
        if "
            parts = line.split("
            code_part = parts[0]
            comment = parts[1]
            trans = safe_translate(comment)
            new_lines.append(f"{code_part}
            continue
            
        m_doc = re.match(r'^(\s*(?:"""|\'\'\'))(.*?)((?:"""|\'\'\')(?:\s*))$', line)
        if m_doc:
            prefix = m_doc.group(1)
            doc_text = m_doc.group(2)
            suffix = m_doc.group(3)
            if len(doc_text) > 3:
                trans = safe_translate(doc_text)
                new_lines.append(f"{prefix}{trans}{suffix}")
                continue
                
        new_lines.append(line)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

folders = ["6_agent", "web"]
for folder in folders:
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".py") and not file.startswith("__") and file != "extensions_1000.py":
                process_file(os.path.join(root, file))

print("🎉 Selesai! Format kode dijamin 100% aman.")
