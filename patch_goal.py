import re

# 1. Patch Frontend (index.html) biar ngedeteksi /goal
html_path = "web/static/index.html"
with open(html_path, "r") as f:
    html = f.read()

# Cari fungsi sendMessage, tambahin logic /goal
if "if (text.startsWith('/goal '))" not in html:
    # Kita suntikin logika deteksi /goal sebelum kirim ke websocket
    # (Sesuaikan dengan nama variabel input di file lo, biasanya `input.value` atau `msg`)
    target_script = "async function sendMessage()"
    if target_script in html:
        insert_code = """async function sendMessage() {
    const input = document.getElementById('chat-input');
    if (!input || !input.value.trim()) return;
    let text = input.value.trim();
    
    // === FITUR /GOAL ===
    if (text.startsWith('/goal ')) {
        const goal = text.replace('/goal ', '');
        input.value = '';
        // Kirim ke endpoint multi-agent (sesuaikan nama fungsinya dengan yang ada di file lo)
        if (typeof runMultiAgent === 'function') {
            runMultiAgent(goal);
            return;
        } else {
            console.log("Mode Multi-Agent belum diinisialisasi di frontend");
        }
    }
    // ===================
"""
        html = html.replace(target_script, insert_code, 1)
        with open(html_path, "w") as f:
            f.write(html)
        print("✅ Frontend (index.html) berhasil dipatch untuk /goal")
    else:
        print("⚠️ Gagal nemu fungsi sendMessage di index.html. Cek manual.")
else:
    print("✅ Frontend udah ada fitur /goal")

# 2. Patch Backend (server.py)
# Kita pastiin backend bisa nerima request multi-agent
server_path = "web/server.py"
with open(server_path, "r") as f:
    server = f.read()

if "from multi_agent import run_multi_agent" not in server:
    # Tambahin import di atas
    server = server.replace("from fastapi import", "from multi_agent import run_multi_agent\nfrom fastapi import", 1)
    with open(server_path, "w") as f:
        f.write(server)
    print("✅ Backend (server.py) berhasil ditambahin import run_multi_agent")
else:
    print("✅ Backend udah ada import multi_agent")
