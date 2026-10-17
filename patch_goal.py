import re

html_path = "web/static/index.html"
with open(html_path, "r") as f:
    html = f.read()

if "if (text.startsWith('/goal '))" not in html:
    target_script = "async function sendMessage()"
    if target_script in html:
        insert_code = """async function sendMessage() {
    const input = document.getElementById('chat-input');
    if (!input || !input.value.trim()) return;
    let text = input.value.trim();
    
    // === /GOAL FEATURE ===
    if (text.startsWith('/goal ')) {
        const goal = text.replace('/goal ', '');
        input.value = '';
        // Send to multi-agent endpoint (adjust the function name with the one in your file)
        if (typeof runMultiAgent === 'function') {
            runMultiAgent(goal);
            return;
        } else {
            console.log("Multi-Agent mode is not initialized in the frontend");
        }
    }
    // ===================
"""
        html = html.replace(target_script, insert_code, 1)
        with open(html_path, "w") as f:
            f.write(html)
        print("✅ Frontend (index.html) successfully patched for /goal")
    else:
        print("⚠️ Failed to find sendMessage function in index.html. Check manually.")
else:
    print("✅ Frontend already has /goal feature")

server_path = "web/server.py"
with open(server_path, "r") as f:
    server = f.read()

if "from multi_agent import run_multi_agent" not in server:
    server = server.replace("from fastapi import", "from multi_agent import run_multi_agent\nfrom fastapi import", 1)
    with open(server_path, "w") as f:
        f.write(server)
    print("✅ Backend (server.py) successfully added run_multi_agent import")
else:
    print("✅ Backend already has multi_agent import")
