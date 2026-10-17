import os
import requests
import time
import re

# Ambil config dari .env lo
with open(".env", "r") as f:
    env_content = f.read()
    
api_key_match = re.search(r'LLM_API_KEY=(.*)', env_content)
api_key = api_key_match.group(1).strip() if api_key_match else ""
url_match = re.search(r'LLM_URL=(.*)', env_content)
url = url_match.group(1).strip() if url_match else "http://localhost:20128/v1/chat/completions"

# Model yang lo pake (bisa diganti)
MODEL = "openrouter/deepseek/deepseek-v4-flash"

def translate_file(filepath):
    print(f"🔄 Translating: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()

    # Skip file yang terlalu kecil atau gak ada komentar
    if len(code) < 50:
        return

    prompt = f"""You are an expert Python developer. I will provide you with a Python file that contains Indonesian comments, docstrings, and strings.
Your task is to translate ALL Indonesian text in the comments (#), docstrings (\"\"\" or '''), and user-facing strings to English.

CRITICAL RULES:
1. DO NOT change any executable code, variable names, function names, classes, or logic.
2. DO NOT translate library imports or API paths.
3. DO NOT wrap the output in markdown code blocks (no ```python). Just return the raw code.
4. Keep the exact same indentation and structure.
5. If a string is used for internal logic (e.g. dictionary keys), DO NOT translate it unless you are sure it's safe.

Here is the code:
{code}"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 8000
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=(30, 120))
        if r.ok:
            data = r.json()
            translated_code = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Bersihin kalau AI bandel naro markdown ```python
            translated_code = re.sub(r'^```(?:python)?\n', '', translated_code)
            translated_code = re.sub(r'\n```$', '', translated_code)

            if translated_code and len(translated_code) > len(code) * 0.5:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(translated_code)
                print(f"✅ Success: {filepath}")
            else:
                print(f"⚠️ Skipped (AI response too short/empty): {filepath}")
        else:
            print(f"❌ Failed {filepath}: HTTP {r.status_code} - {r.text[:100]}")
    except Exception as e:
        print(f"❌ Error {filepath}: {e}")
    
    time.sleep(1) # Jeda biar gak kena rate limit

# List folder yang mau ditranslate
folders = ["6_agent", "web"]
for folder in folders:
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                translate_file(os.path.join(root, file))

print("🎉 Translasi selesai! Silakan cek pake 'git diff'.")
