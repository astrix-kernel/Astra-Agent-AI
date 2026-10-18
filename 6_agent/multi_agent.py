"""Multi-agent orchestration: Planner + Executor."""
import json
import re

MODE_PROMPTS = {
    "coder": "You are an autonomous coding agent. Focus on writing, reading, and fixing code.",
    "analysis": "You are an analytical agent. Focus on explaining, debugging, and deep system analysis.",
    "chat": "You are a conversational agent. Answer briefly and naturally.",
    "multi_agent": "You are a coordinator. Break tasks into sub-tasks and execute them sequentially.",
    "creative": "You are a creative agent. Generate ideas, stories, or design concepts.",
    "knowledge": "You are a document manager. Focus on reading files, summarizing, and organizing data.",
    "search": "You are a researcher. Focus on finding information (simulated).",
    "autonomous": "You are an autonomous executor. Complete the task from start to finish."
}

import os

import subprocess

def run_multi_agent(goal, planner_model=None, coder_model=None, on_log=None, max_tasks=5,
                    base_url=None, api_key=None, model=None, coder_mode=False, status_callback=None):
    """Plan → Execute → Return results. Support custom API params."""
    
    def log(msg):
        if on_log: on_log(msg)
        print(f"[MULTI] {msg}", flush=True)
    
    from chat import chat_turn
    
    base_kwargs = {
        "custom_base_url": base_url,
        "custom_api_key": api_key,
        "custom_model": model,
    }
    
    log(f"🎯 Goal: {goal}")
    log(f"🔌 API: {'custom (' + str(base_url) + ')' if base_url else 'default'}")
    log(f"🧠 Model: {model or 'default'}")
    log("📋 Phase 1: Planning...")
    if status_callback: status_callback("thinking", "🧠 Thinking... menganalisis tugas")
    
    planner_prompt = f"""Break down this goal into 1-{max_tasks} atomic, executable tasks.

GOAL: {goal}

CRITICAL RULES:
1. Each task must be a SINGLE actionable step (not a repeat of the goal)
2. For file creation, split into: "Create <file>" + "Write <content> to <file>"
3. For compilation, add: "Compile <file> with gcc"
4. NEVER just echo the original goal as one task
5. Keep tasks specific and testable

Return ONLY a JSON array of strings. Example for "bikin file hello.txt isinya Halo":
["Create hello.txt", "Write 'Halo' into hello.txt", "Verify hello.txt exists"]

Now generate the tasks for the goal above:


    [CRITICAL CONTEXT]
    The user is talking about a LOCAL FOLDER (workspace), NOT a website. 
    Do NOT plan to "open a browser", "login", or "reset password" unless the user explicitly asks to search the web.
    If the user asks to "access" or "see" a folder, plan to use filesystem tools like list_dir, read_file, or run_command (ls).
    No explanation. No markdown. Just JSON array."""
    
    try:
        plan_result, _ = chat_turn(
                [], planner_prompt,
                system_prompt="""You are a precise executor. Complete tasks with clear concise output.

[CASCADING PROTOCOL - MANDATORY]
If a task or command fails, DO NOT give up. 
1. Try alternative tools (e.g., if 'find' fails, use 'ls -R').
2. If 'read_file' fails, use 'cat' or 'head'.
3. Break down complex tasks into smaller sub-tasks.
4. Analyze the error, adapt, and retry until you succeed.
""",

            temperature=0.3, max_tokens=1024,
            **base_kwargs
        )
        log(f"📥 Planner response: {len(plan_result)} chars")
        log(f"📥 Preview: {plan_result[:200]}")
    except Exception as e:
        log(f"❌ Planner error: {e}")
        return {"error": str(e)}
    
    tasks = []
    
    try:
        parsed = json.loads(plan_result.strip())
        if isinstance(parsed, list):
            tasks = [str(t) for t in parsed if str(t).strip()][:max_tasks]
    except: pass
    
    if not tasks:
        try:
            m = re.search(r'\[\s*"[\s\S]*?\]', plan_result)
            if m:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, list):
                    tasks = [str(t) for t in parsed if str(t).strip()][:max_tasks]
        except: pass
    
    if not tasks:
        lines = plan_result.split('\n')
        for line in lines:
            line = line.strip()
            m = re.match(r'^(?:\d+\.|\-|\*)\s*(.+)$', line)
            if m:
                task_text = m.group(1).strip().strip('"\'')
                if task_text and len(task_text) > 3:
                    tasks.append(task_text[:200])
                    if len(tasks) >= max_tasks: break
    
    if not tasks:
        log("⚠ Could not parse any tasks, using goal as single task")
        tasks = [goal]
    else:
        log(f"✅ Plan ready: {len(tasks)} tasks")
    if status_callback: status_callback("plan", f"📋 Rencana: {len(tasks)} langkah")
    
    for i, t in enumerate(tasks, 1):
        log(f"  {i}. {t[:80]}")
    
    results = []
    history = []
    
    AVAILABLE_TOOLS = """Kamu punya akses ke alat ini: 
1. read_file(path)
2. write_file(path, content)
3. run_command(command)"""
    
    
    coder_instructions = """
    [CODER MODE ACTIVE]
    You are an autonomous coding agent. For EVERY task, you MUST follow this loop:
    1. SCAN: Read the file and check for current errors.
    2. CODE: Make the necessary changes.
    3. VERIFY: IMMEDIATELY run a build or syntax check (e.g., make, gcc -fsyntax-only <file>, or python3 -m py_compile <file>).
    4. FIX: If there is an error, fix it and VERIFY again.
    DO NOT finish the task until the code successfully compiles.
    """ if coder_mode else ""

    for i, task in enumerate(tasks, 1):
        log(f"⚙️ Task {i}/{len(tasks)}: {task[:60]}")
        if status_callback: status_callback("task", f"⚙️ Task {i}/{len(tasks)}: {task[:50]}")
        
        exec_prompt = f"""Task {i}/{len(tasks)}: {task}

    [WORKSPACE CONTEXT]
    CRITICAL: The 'Astrix.OSdev' is a LOCAL FOLDER on the filesystem, NOT a website URL. 
    Do NOT use browser tools to open it. 
    Use filesystem tools like list_dir, read_file, or run_command (e.g., 'ls', 'find') to inspect its contents.
    

{coder_instructions}
{coder_instructions}

Context dari task sebelumnya:
{chr(10).join([f'- {r[:300]}' for r in results[-2:]]) or 'Belum ada'}

{AVAILABLE_TOOLS}

INSTRUKSI WAJIB: 
Jika kamu butuh membaca file, tulis file, atau menjalankan terminal, KAMU HARUS membalas dengan format JSON seperti ini (jangan pakai markdown, jangan pakai teks lain):
{{"tool": "write_file", "args": {{"path": "main.c", "content": "..."}}}}
Atau
{{"tool": "run_command", "args": {{"command": "make -j4"}}}}

Jika tidak butuh alat, jawab dengan teks biasa."""

        try:
            result, _ = chat_turn(
                history, exec_prompt,
                system_prompt="""You are a precise executor. Complete tasks with clear concise output.

[CASCADING PROTOCOL - MANDATORY]
If a task or command fails, DO NOT give up. 
1. Try alternative tools (e.g., if 'find' fails, use 'ls -R').
2. If 'read_file' fails, use 'cat' or 'head'.
3. Break down complex tasks into smaller sub-tasks.
4. Analyze the error, adapt, and retry until you succeed.
""",

                temperature=0.3, max_tokens=2048,
                **base_kwargs
            )
            
            if not result:
                log("⚠️ AI tidak memberikan respons (server down / rate limit). Lanjut task berikutnya.")
                continue
            result_clean = result.strip()
            result_clean = re.sub(r'^```(?:json)?\n', '', result_clean)
            result_clean = re.sub(r'\n```$', '', result_clean)
            
            json_match = re.search(r'\{.*"tool".*\}', result_clean, re.DOTALL)
            if json_match:
                try:
                    tool_call = json.loads(json_match.group(0))
                    tool_name = tool_call.get("tool")
                    tool_args = tool_call.get("args", {})
                    
                    log(f"🛠️ AI memanggil tool: {tool_name}")
                    if status_callback:
                        if tool_name == "write_file":
                            _path = tool_args.get("path", "?")
                            status_callback("add", f"➕ Ditambahkan {_path}")
                        elif tool_name == "read_file":
                            _path = tool_args.get("path", "?")
                            status_callback("read", f"📖 Baca {_path}")
                        elif tool_name == "run_command":
                            _cmd = tool_args.get("command", "")
                            if "make" in _cmd.lower():
                                status_callback("run", f"⚙️ Makefile")
                            else:
                                status_callback("run", f"▶️ {_cmd[:60]}")
                        elif tool_name == "list_dir":
                            status_callback("list", f"📂 List folder")
                        else:
                            status_callback("tool", f"🔧 {tool_name}")
                    
                    from tools import TOOLS
                    
                    if tool_name in TOOLS:
                        tool_result = TOOLS[tool_name](**tool_args)
                        log(f"✅ Tool {tool_name} berhasil: {str(tool_result)[:100]}")
                        if status_callback: status_callback("done_tool", f"✅ {tool_name}")
                        
                        history.append({"role": "user", "content": exec_prompt})
                        history.append({"role": "assistant", "content": result})
                        history.append({"role": "user", "content": f"Hasil dari {tool_name}: {tool_result}"})
                        
                        final_result, _ = chat_turn(
                history, exec_prompt,
                system_prompt="""You are a precise executor. Complete tasks with clear concise output.

[CASCADING PROTOCOL - MANDATORY]
If a task or command fails, DO NOT give up. 
1. Try alternative tools (e.g., if 'find' fails, use 'ls -R').
2. If 'read_file' fails, use 'cat' or 'head'.
3. Break down complex tasks into smaller sub-tasks.
4. Analyze the error, adapt, and retry until you succeed.
""",

                            temperature=0.3, max_tokens=1024,
                            **base_kwargs
                        )
                        results.append(final_result)
                    else:
                        results.append(f"❌ Tool {tool_name} tidak dikenal.")
                except Exception as e:
                    log(f"❌ Gagal parsing JSON tool call: {e}")
                    results.append(result)
            else:
                results.append(result)
                
        except Exception as e:
            results.append(f"❌ Error: {e}")
            log(f"❌ Task {i} error: {e}")
    
    log(f"🎉 Complete: {len(results)}/{len(tasks)} tasks")
    # Sanitize results: remove leaked JSON tool calls
    import re as _re_sanitize
    _clean_results = []
    for _r in results:
        if not isinstance(_r, str):
            _clean_results.append(str(_r))
            continue
        _clean_lines = []
        for _line in _r.split('\n'):
            _stripped = _line.strip()
            # Skip lines that are pure JSON tool calls
            if _stripped.startswith('{') and '"tool"' in _stripped and _stripped.endswith('}'):
                continue
            _clean_lines.append(_line)
        _cleaned = '\n'.join(_clean_lines)
        _cleaned = _re_sanitize.sub(r'\n{3,}', '\n\n', _cleaned).strip()
        if _cleaned:
            _clean_results.append(_cleaned)
    results = _clean_results
    
    return {"goal": goal, "tasks": tasks, "results": results}
