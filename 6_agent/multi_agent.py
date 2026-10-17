"""Multi-agent orchestration: Planner + Executor."""
import json
import re


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
    
    # Phase 2: Execute
    results = []
    history = []
    exec_context = ""
    for i, task in enumerate(tasks, 1):
        log(f"⚙️ Task {i}/{len(tasks)}: {task[:60]}")
        # AUTO-INJECT: file content kalau task nyebut path
        file_context = ""
        try:
            import os as _os
            paths = re.findall(r'/\S+/\S+', task)
            if not paths:
                m = re.search(r'\b([A-Z][a-zA-Z0-9_.-]{2,30}\.(?:md|txt|c|h|cpp|py|json|yaml|yml|toml|cfg|conf))\b', task)
                if m: paths = [m.group(1)]
            workspace = str(ASTRIX_ROOT)
            for _path in paths:
                _candidates = [_path] if _path.startswith("/") else [_os.path.join(workspace, _path), _path]
                for _c in _candidates:
                    if _os.path.isfile(_c):
                        try:
                            with open(_c, "r", errors="ignore") as _f:
                                _content = _f.read()[:15000]
                            file_context += "\n\n=== [FILE CONTENT: " + _c + "] ===\n" + _content + "\n=== [END FILE] ==="
                            log("📄 Auto-loaded: " + _c + " (" + str(len(_content)) + " chars)")
                            break
                        except Exception as _e:
                            log("⚠ Read error: " + str(_e))
        except Exception as _e:
            log("⚠ File inject error: " + str(_e))
        
        # === AUTO-EXECUTE: detect file write / command in task ===
        action_result = ""
        action_type = None
        
        try:
            import os as _os
            import subprocess as _sub
            
            # Detect: WRITE FILE
            # Pattern: "write X to Y" / "create Y with X" / "tulis X ke Y" / "save to Y"
            write_m = re.search(
                r'(?:write|create|save|tulis|buat|simpan)\s+(?:.*?)\s+(?:to|ke|at|di)\s+[`\'"]?(/[\w/.\-]+)', 
                task, re.I
            )
            if not write_m:
                write_m = re.search(r'(?:write|create|tulis|buat)\s+[`\'"]?(/[\w/.\-]+)', task, re.I)
            
            # Detect: RUN COMMAND
            run_m = re.search(
                r'(?:run|execute|jalankan|make|build|test|compile|eksekusi)\s+[`\'"]?([^`\'"\n]+?)[`\'"]?$',
                task, re.I
            )
            
            if write_m:
                target_path = write_m.group(1)
                log(f"📝 WRITE detected: {target_path}")
                
                # Ask AI to generate file content
                gen_prompt = f"""Generate COMPLETE content for file: {target_path}

Task context: {task}

Output ONLY the raw file content. NO markdown fences. NO explanation. NO "Here is...". Just the file content."""
                
                gen_result, _ = chat_turn(
                    [], gen_prompt,
                    system_prompt="You generate file content. Output ONLY the file body. No fences, no intro, no outro.",
                    temperature=0.3, max_tokens=4000,
                    **base_kwargs
                )
                
                # Clean up any accidental markdown fences
                gen_result = gen_result.strip()
                gen_result = re.sub(r'^```\w*\n', '', gen_result)
                gen_result = re.sub(r'\n```$', '', gen_result)
                
                # Safety: check path is not outside workspace
                abs_path = _os.path.abspath(_os.path.expanduser(target_path))
                workspace = str(ASTRIX_ROOT)
                if not abs_path.startswith(workspace) and not abs_path.startswith(_os.path.expanduser("~")):
                    action_result = f"⚠️ BLOCKED: {target_path} outside safe zone"
                    log(action_result)
                else:
                    try:
                        _os.makedirs(_os.path.dirname(abs_path), exist_ok=True)
                        with open(abs_path, 'w') as _f:
                            _f.write(gen_result)
                        action_result = f"✅ File written: {target_path} ({len(gen_result)} bytes)"
                        log(action_result)
                        action_type = "write"
                    except Exception as _we:
                        action_result = f"❌ Write failed: {_we}"
                        log(action_result)
            
            elif run_m:
                cmd = run_m.group(1).strip().strip('`\'"')
                log(f"⚙️ RUN command: {cmd}")
                
                try:
                    result = _sub.run(
                        cmd, shell=True, capture_output=True, text=True,
                        timeout=60, cwd=str(ASTRIX_ROOT)
                    )
                    stdout = result.stdout[:3000]
                    stderr = result.stderr[:1000]
                    rc = result.returncode
                    
                    action_result = f"Command: {cmd}\nExit: {rc}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
                    action_type = "run"
                    log(f"✅ Command exit={rc}, stdout={len(stdout)}B, stderr={len(stderr)}B")
                except _sub.TimeoutExpired:
                    action_result = f"⏱ Command timeout (60s): {cmd}"
                    log(action_result)
                except Exception as _re:
                    action_result = f"❌ Command error: {_re}"
                    log(action_result)
        
        except Exception as _ae:
            log(f"⚠ Auto-exec error: {_ae}")
        
        exec_prompt = f"""Task {i}/{len(tasks)}: {task}

Context dari task sebelumnya:
{chr(10).join([f'- {r[:300]}' for r in results[-2:]]) or 'Belum ada'}

{file_context}

{f"═══ [AUTO-EXECUTION RESULT] ═══{chr(10)}{action_result}{chr(10)}═══ [END RESULT] ═══" if action_result else ""}

WAJIB: Kalau ada AUTO-EXECUTION RESULT di atas, gunakan sebagai hasil aktual. JANGAN bilang "tidak punya tool". File/command sudah di-eksekusi otomatis."""
        
        # === AUTO-WRITE: detect write/create file ===
        try:
            import re as _rew, os as _osw
            write_m = _rew.search(r"(?:write|create|save|tulis|buat|simpan)\s+[`'\"]?(/[\w/.\-]+)", task, _rew.I)
            if write_m:
                target = write_m.group(1)
                print(f"[AUTO-WRITE] path={target}", flush=True)
                gen_prompt = f"Generate COMPLETE file content for: {target}\n\nTask: {task}\n\nOutput ONLY raw content. NO markdown. NO explanation."
                gen_result, _ = chat_turn([], gen_prompt, system_prompt="Output raw file content only. No fences.", temperature=0.3, max_tokens=4000, **base_kwargs)
                gen_result = gen_result.strip()
                gen_result = _rew.sub(r'^```\w*\n', '', gen_result)
                gen_result = _rew.sub(r'\n```$', '', gen_result)
                abs_path = _osw.path.abspath(_osw.path.expanduser(target))
                if not abs_path.startswith(_osw.path.expanduser("~")):
                    log(f"⚠ BLOCKED: {target} outside home")
                else:
                    try:
                        _osw.makedirs(_osw.path.dirname(abs_path), exist_ok=True)
                        with open(abs_path, 'w') as _wf:
                            _wf.write(gen_result)
                        log(f"✅ File written: {target} ({len(gen_result)} bytes)")
                    except Exception as _we:
                        log(f"❌ Write failed: {_we}")
        except Exception as _wae:
            log(f"⚠ Auto-write error: {_wae}")

        # === AUTO-RUN: detect run/execute command ===
        try:
            import re as _rer, subprocess as _subr
            run_m = _rer.search(r"(?:run|execute|jalankan|eksekusi|test|build|compile)\s+[`'\"]([^`'\"]+)[`'\"]", task, _rer.I)
            if run_m:
                cmd = run_m.group(1).strip()
                print(f"[AUTO-RUN] cmd={cmd}", flush=True)
                try:
                    result_run = _subr.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=str(ASTRIX_ROOT))
                    stdout = result_run.stdout[:2000]
                    stderr = result_run.stderr[:500]
                    rc = result_run.returncode
                    log(f"✅ Command exit={rc}, stdout={len(stdout)}B")
                    exec_context += f"\n\n[COMMAND: {cmd}]\nEXIT: {rc}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}\n[END]"
                except Exception as _re:
                    log(f"❌ Command error: {_re}")
        except Exception as _rae:
            log(f"⚠ Auto-run error: {_rae}")

        try:
            result, _ = chat_turn(
                history, exec_prompt,
                system_prompt="You are a precise executor. Complete tasks with clear concise output.",
                temperature=0.5, max_tokens=2048,
                **base_kwargs
            )
            
            if not result or not result.strip():
                result = f"⚠️ Empty response for task: {task}"
            
            results.append(result)
            history.append({"role": "user", "content": exec_prompt})
            history.append({"role": "assistant", "content": result[:1000]})
            log(f"✅ Task {i} done ({len(result)} chars)")
        except Exception as e:
            results.append(f"❌ Error: {e}")
            log(f"❌ Task {i} error: {e}")
    
    log(f"🎉 Complete: {len(results)}/{len(tasks)} tasks")
    return {"goal": goal, "tasks": tasks, "results": results}
