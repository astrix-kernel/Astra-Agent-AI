"""Multi-agent orchestration: Planner + Executor."""
import json
import re
import os
import subprocess

def run_multi_agent(goal, planner_model=None, coder_model=None, on_log=None, max_tasks=5,
                    base_url=None, api_key=None, model=None):
    """Plan → Execute → Return results. Support custom API params."""
    
    def log(msg):
        if on_log: on_log(msg)
        print(f"[MULTI] {msg}", flush=True)
    
    from chat import chat_turn
    
    # Base params — dipake buat semua call
    base_kwargs = {
        "custom_base_url": base_url,
        "custom_api_key": api_key,
        "custom_model": model,
    }
    
    log(f"🎯 Goal: {goal}")
    log(f"🔌 API: {'custom (' + str(base_url) + ')' if base_url else 'default'}")
    log(f"🧠 Model: {model or 'default'}")
    log("📋 Phase 1: Planning...")
    
    # Phase 1: Planner
    planner_prompt = f"""Break down this goal into 2-{max_tasks} atomic tasks.

GOAL: {goal}

Return ONLY a JSON array of strings. Example:
["Read Makefile", "Add target foo", "Run make foo"]

No explanation. No markdown. Just JSON array."""
    
    try:
        plan_result, _ = chat_turn(
            [], planner_prompt,
            system_prompt="You are a software architect. Break goals into atomic tasks. Respond with ONLY a JSON array, nothing else.",
            temperature=0.3, max_tokens=1024,
            **base_kwargs
        )
        log(f"📥 Planner response: {len(plan_result)} chars")
        log(f"📥 Preview: {plan_result[:200]}")
    except Exception as e:
        log(f"❌ Planner error: {e}")
        return {"error": str(e)}
    
    # Parse JSON array — multiple attempts
    tasks = []
    
    # Attempt 1: direct JSON parse
    try:
        parsed = json.loads(plan_result.strip())
        if isinstance(parsed, list):
            tasks = [str(t) for t in parsed if str(t).strip()][:max_tasks]
    except: pass
    
    # Attempt 2: extract JSON array via regex
    if not tasks:
        try:
            m = re.search(r'\[\s*"[\s\S]*?\]', plan_result)
            if m:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, list):
                    tasks = [str(t) for t in parsed if str(t).strip()][:max_tasks]
        except: pass
    
    # Attempt 3: extract bullet points
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
    
    for i, t in enumerate(tasks, 1):
        log(f"  {i}. {t[:80]}")
    
    # Phase 2: Execute (REAL TOOL CALLING)
    results = []
    history = []
    
    AVAILABLE_TOOLS = """Kamu punya akses ke alat ini: 
1. read_file(path)
2. write_file(path, content)
3. run_command(command)"""
    
    for i, task in enumerate(tasks, 1):
        log(f"⚙️ Task {i}/{len(tasks)}: {task[:60]}")
        
        exec_prompt = f"""Task {i}/{len(tasks)}: {task}

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
                system_prompt="You are a precise executor. Complete tasks with clear concise output.",
                temperature=0.3, max_tokens=2048,
                **base_kwargs
            )
            
            # Cek apakah AI membalas dengan JSON Tool Call
            result_clean = result.strip()
            # Bersihkan markdown block jika AI bandel pakai ```json
            result_clean = re.sub(r'^```(?:json)?\n', '', result_clean)
            result_clean = re.sub(r'\n```$', '', result_clean)
            
            if result_clean.startswith("{") and result_clean.endswith("}"):
                try:
                    tool_call = json.loads(result_clean)
                    tool_name = tool_call.get("tool")
                    tool_args = tool_call.get("args", {})
                    
                    log(f"🛠️ AI memanggil tool: {tool_name}")
                    
                    from tools import TOOLS
                    
                    if tool_name in TOOLS:
                        tool_result = TOOLS[tool_name](**tool_args)
                        log(f"✅ Tool {tool_name} berhasil: {str(tool_result)[:100]}")
                        
                        history.append({"role": "user", "content": exec_prompt})
                        history.append({"role": "assistant", "content": result})
                        history.append({"role": "user", "content": f"Hasil dari {tool_name}: {tool_result}"})
                        
                        final_result, _ = chat_turn(
                            history, "Berikan ringkasan hasil eksekusi tool tersebut.",
                            system_prompt="You are a helpful assistant.",
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
    return {"goal": goal, "tasks": tasks, "results": results}
