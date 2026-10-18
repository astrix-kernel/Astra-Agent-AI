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

def _get_prioritized_files(goal, current_files):
    """Return merged priority files from goal + current_files. Never raises.

    GENERIC version — works for ANY project structure (not project-specific).
    Strategy:
      1. Extract meaningful keywords from goal (auto-filter stopwords)
      2. Scan workspace directories, match by keyword
      3. Balanced round-robin file collection
    """
    try:
        import re, os
        from pathlib import Path
        import config as _cfg
        _ws = Path(str(_cfg.WORKSPACE))
        if not _ws.exists():
            return current_files

        # Step 1: keywords from goal (auto-detect language stopwords)
        _stop_id = {
            'yang','untuk','dan','atau','dengan','dari','sampai','sebagai',
            'pantas','disebut','khusus','game','nya','mau','bisa','adalah',
            'seperti','tolong','lanjutkan','build','sampe','yaitu','the',
            'bikin','buat','sudah','juga','biar','agar','masih','dalam',
            'pada','ke','di','ini','itu','ada','tidak','juga','sangat',
            'the','and','or','with','from','to','for','of','in','on','is',
            'a','an','this','that','these','those','build','make','create',
            'add','update','fix','improve','continue','extend','want','need',
        }
        _keywords = set()
        for _kw in re.findall(r'[a-zA-Z][a-zA-Z0-9_]{2,}', goal):
            _kw_low = _kw.lower()
            if _kw_low not in _stop_id:
                _keywords.add(_kw_low)

        if not _keywords:
            return current_files

        # Step 2: scan workspace — cari dir yang match keywords
        _skip = {
            'kernel','src','include','build','bin','lib','test','tests',
            'docs','doc','tool','tools','script','scripts','.git','.kilo',
            'node_modules','venv','.venv','__pycache__','.idea','.vscode',
            'target','dist','out','tmp','temp','log','logs','cache','.cache',
            'examples','example','demo','demos','samples','sample',
        }
        
        # Scan multiple possible roots
        _scan_roots = [_ws]
        for _sub in ['kernel', 'src', 'include', 'lib', 'app', 'apps', 'pkg', 'packages', 'modules']:
            _sp = _ws / _sub
            if _sp.is_dir():
                _scan_roots.append(_sp)

        _prio_dirs = set()
        _dir_scores = {}  # dir -> jumlah keyword yang match
        for _root in _scan_roots:
            if not _root.is_dir():
                continue
            try:
                for _entry in _root.iterdir():
                    if not _entry.is_dir():
                        continue
                    if _entry.name.lower() in _skip:
                        continue
                    if _entry.name.startswith('.'):
                        continue
                    _name = _entry.name.lower()
                    _score = 0
                    for _kw in _keywords:
                        # Min length 3 untuk hindari false positive
                        if len(_kw) < 3:
                            continue
                        # Match if keyword ada di nama dir, atau nama dir ada di keyword
                        if _kw in _name or (len(_name) >= 3 and _name in _kw):
                            _score += 1
                    if _score > 0:
                        _prio_dirs.add(_entry)
                        _dir_scores[_entry] = _score
            except Exception:
                pass

        if not _prio_dirs:
            return current_files

        # Step 3: balanced round-robin file collection
        _exts = ('.c','.h','.cpp','.hpp','.cc','.hh','.S','.s','.asm','.ld',
                 '.rs','.go','.py','.js','.ts','.tsx','.jsx','.java','.kt',
                 '.rb','.php','.lua','.m','.mm','.swift','.dart','.cs',
                 '.mk','.make','.toml','.cfg','.cmake')
        
        _per_dir = {}
        _seen = set()
        for _d in _prio_dirs:
            _dir_files = []
            try:
                for _root, _, _fs in os.walk(str(_d)):
                    # Skip subdir yang jelas bukan source
                    _root_low = _root.lower()
                    if any(x in _root_low for x in ['/.git', '/node_modules', '/__pycache__', '/.venv', '/venv']):
                        continue
                    for _fn in _fs:
                        if _fn.endswith(_exts) or _fn in ('Makefile','CMakeLists.txt','meson.build','Cargo.toml','go.mod','package.json'):
                            _rel = os.path.relpath(os.path.join(_root, _fn), str(_ws))
                            if _rel not in _seen:
                                _dir_files.append(_rel)
                                _seen.add(_rel)
            except Exception:
                pass
            if _dir_files:
                # Sort: root dir file dulu (subdir count = 0), lalu alfabetis
                _dir_files.sort(key=lambda x: (x.count(os.sep) - _d.name.count(os.sep) if _d.name else 0, x))
                _per_dir[_d] = _dir_files

        # Sort directories by score (paling relevan duluan)
        _sorted_dirs = sorted(_per_dir.keys(), key=lambda d: -_dir_scores.get(d, 0))

        # Round-robin collection
        _total = 15
        _collected = []
        _idx = 0
        while len(_collected) < _total:
            _added = False
            for _d in _sorted_dirs:
                _flist = _per_dir[_d]
                if _idx < len(_flist):
                    _collected.append(_flist[_idx])
                    _added = True
                    if len(_collected) >= _total:
                        break
            if not _added:
                break
            _idx += 1

        _total_found = sum(len(v) for v in _per_dir.values())
        if _collected:
            print(f"[PRIORITY] {_total_found} files in {len(_prio_dirs)} dirs (keywords: {len(_keywords)})", flush=True)
            for _fp in _collected[:15]:
                print(f"[PRIORITY]   -> {_fp}", flush=True)
            _merged = _collected[:15]
            for _cf in (current_files or []):
                if _cf not in _merged:
                    _merged.append(_cf)
            return _merged
    except Exception as _e:
        print(f"[PRIORITY] scan failed: {_e}", flush=True)
    return current_files


def _extract_json_array(text):
    # Extract JSON array of strings from model response
    import json as _j
    import re as _re
    
    text = text.strip()
    text = _re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = _re.sub(r'\n?```\s*$', '', text)
    text = text.strip()
    
    # Remove trailing commas
    fixed = _re.sub(r',(\s*[\}\]])', r'\1', text)
    
    # Try fixed first, then original
    for candidate in [fixed, text]:
        try:
            result = _j.loads(candidate)
            if isinstance(result, list):
                return [str(x) for x in result]
        except _j.JSONDecodeError:
            pass
    
    # Fallback: find array with raw_decode
    start = text.find('[')
    if start != -1:
        decoder = _j.JSONDecoder()
        for i in range(start, len(text)):
            if text[i] != '[':
                continue
            try:
                obj, end = decoder.raw_decode(text[i:])
                if isinstance(obj, list) and all(isinstance(x, str) for x in obj):
                    return obj
            except _j.JSONDecodeError:
                continue
    
    return []


def _extract_first_json(text):
    """Extract first valid JSON object with 'tool' key from text."""
    import json as _j
    import re as _re
    decoder = _j.JSONDecoder()
    pos = 0
    while pos < len(text):
        match = _re.search(r'\{', text[pos:])
        if not match:
            break
        start = pos + match.start()
        try:
            obj, end = decoder.raw_decode(text[start:])
            if isinstance(obj, dict) and "tool" in obj:
                return obj
        except _j.JSONDecodeError:
            pass
        pos = start + 1
    return None


def _deep_analyze_workspace(goal, max_files=20):
    """Read key files and return structured analysis."""
    import subprocess as _sp
    from pathlib import Path as _P
    from config import WORKSPACE as _WS
    
    analysis = {
        "structure": [],
        "key_files": {},
        "project_type": "unknown",
        "languages": [],
    }
    
    try:
        r = _sp.run(
            ["find", ".", "-maxdepth", "2", "-type", "f"],
            cwd=str(_WS), capture_output=True, text=True, timeout=10
        )
        analysis["structure"] = [f.strip() for f in r.stdout.strip().split("\n") if f.strip()][:50]
    except Exception:
        pass
    
    for marker, ptype in [
        ("CMakeLists.txt", "cmake"),
        ("Makefile", "make"),
        ("setup.py", "python"),
        ("Cargo.toml", "rust"),
        ("package.json", "node"),
        ("meson.build", "meson"),
        ("Kconfig", "kconfig"),
    ]:
        p = _P(_WS) / marker
        if p.exists():
            try:
                analysis["key_files"][marker] = p.read_text()[:2000]
                if analysis["project_type"] == "unknown":
                    analysis["project_type"] = ptype
            except Exception:
                pass
    
    for readme in ["README.md", "README.txt", "README"]:
        p = _P(_WS) / readme
        if p.exists():
            try:
                analysis["key_files"][readme] = p.read_text()[:2000]
            except Exception:
                pass
    
    try:
        r = _sp.run(
            ["find", ".", "-maxdepth", "3", "-type", "f"],
            cwd=str(_WS), capture_output=True, text=True, timeout=10
        )
        ext_map = {".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
                   ".py": "python", ".rs": "rust", ".js": "js", ".ts": "ts",
                   ".go": "go", ".java": "java", ".asm": "asm", ".S": "asm"}
        langs = set()
        for f in r.stdout.strip().split("\n"):
            for ext, lang in ext_map.items():
                if f.endswith(ext):
                    langs.add(lang)
        analysis["languages"] = sorted(langs)
    except Exception:
        pass
    
    return analysis


def _compatibility_check(goal, analysis, chat_turn_fn, base_kwargs):
    """Ask LLM: does goal fit existing project?"""
    import json as _j
    import re as _re
    
    key_files_str = "\n\n".join([
        "=== " + k + " ===\n" + v[:1000]
        for k, v in analysis["key_files"].items()
    ]) or "(no key files)"
    
    prompt = "You are a senior developer doing pre-flight analysis.\n\n"
    prompt += "PROJECT:\n"
    prompt += "- Type: " + str(analysis["project_type"]) + "\n"
    prompt += "- Languages: " + ", ".join(analysis["languages"]) + "\n"
    prompt += "- Files: " + ", ".join(analysis["structure"][:20]) + "\n\n"
    prompt += "KEY FILES:\n" + key_files_str + "\n\n"
    prompt += "USER GOAL: " + goal + "\n\n"
    prompt += "Analyze if compatible. Respond JSON only:\n"
    prompt += '{"compatible": true, "confidence": 0-100, "reasoning": "...", "recommended_approach": "...", "files_to_read_first": [], "warnings": []}\n'
    
    try:
        response, _ = chat_turn_fn([], prompt, system_prompt="You analyze code. Respond with JSON only.", **base_kwargs)
        if not response:
            return {"compatible": True, "confidence": 50, "reasoning": "no response", "files_to_read_first": [], "warnings": []}
        
        resp_clean = response.strip()
        resp_clean = _re.sub(r'^```(?:json)?\s*\n?', '', resp_clean)
        resp_clean = _re.sub(r'\n?```\s*$', '', resp_clean)
        resp_clean = _re.sub(r',(\s*[\}\]])', r'\1', resp_clean)
        
        m = _re.search(r'\{.*"compatible".*\}', resp_clean, _re.DOTALL)
        if m:
            return _j.loads(m.group(0))
    except Exception as e:
        print("[COMPAT] Check failed: " + str(e), flush=True)
    
    return {"compatible": True, "confidence": 50, "reasoning": "fallback", "files_to_read_first": [], "warnings": []}

def _classify_task(task):
    """Returns (intent, suggested_tool)"""
    import re as _re
    t = task.lower()
    
    # Directory creation
    if _re.search(r'(?:create|make|bikin|buat|mkdir)\s+(?:a\s+)?(?:directory|folder|dir)\b', t) or 'mkdir' in t:
        return ('mkdir', 'run_command')
    
    # File creation - extended extensions + Makefile/CMakeLists/Kconfig
    # Match filename.ext (with .asm, .S, .c, .h, etc.)
    if _re.search(r'[a-zA-Z0-9_./-]+\.(cpp|hpp|h|c|cc|asm|s|S|txt|md|py|js|ts|html|css|json|yml|yaml|toml|cmake|in|cfg|mk|sh|rs|go|java|ld|lds)', task):
        return ('write', 'write_file')
    # Match Makefile, CMakeLists.txt, Kconfig (no extension)
    if _re.search(r'(?:create|write|tulis|bikin|buat)\s+(?:file\s+)?(?:Makefile|CMakeLists\.txt|Kconfig|Dockerfile)', task, _re.IGNORECASE):
        return ('write', 'write_file')
    
    # Read
    if any(kw in t for kw in ['read ', 'baca ', 'analisa', 'analyze', 'inspect', 'check if']):
        return ('read', 'read_file')
    
    # Build/run
    if any(kw in t for kw in ['build', 'compile', 'run ', 'execute', 'test', 'verify', 'install', 'configure', 'setup ', 'make ']):
        return ('run', 'run_command')
    
    # List/search
    if any(kw in t for kw in ['list ', 'search', 'find ', 'cari ', 'explore', 'ls ']):
        return ('list', 'run_command')
    
    return ('unknown', 'run_command')




def _ensure_real_content(tool_name, tool_args, task, chat_fn, base_kwargs):
    print("[ENSURE] Called: " + str(tool_name) + " path=" + ((str(tool_args.get("path", "?")) if isinstance(tool_args, dict) else "?"))[:60], flush=True)
    """Kalau LLM kasih write_file tanpa content real, panggil LLM lagi buat generate."""
    if tool_name != "write_file":
        return tool_name, tool_args
    
    path = tool_args.get("path", "") if isinstance(tool_args, dict) else ""
    content = tool_args.get("content", "") if isinstance(tool_args, dict) else ""
    
    # Detect placeholder content
    # SUPER aggressive placeholder detection
    # Aggressive placeholder detection (no escapes)
    is_placeholder = (
        not content.strip()
        or len(content.strip()) < 200
        or 'TODO' in content
        or 'int initialized;' in content
        or 'm_initialized' in content
    )
    
    if not is_placeholder:
        return tool_name, tool_args
    
    # Panggil LLM buat generate content real
    import re as _re
    ext = path.split(".")[-1].lower() if "." in path else "txt"
    
    lang_hint = {
        "c": "C (kernel-style, no libc unless needed)",
        "h": "C header",
        "cpp": "C++20",
        "hpp": "C++20 header",
        "py": "Python 3",
        "md": "Markdown",
        "txt": "plain text",
    }.get(ext, "code")
    
    prompt = (
        f"Write COMPLETE {lang_hint} code for: {task}\n"
        f"File: {path}\n\n"
        f"RULES:\n"
        f"1. Output ONLY the code, no markdown, no explanation\n"
        f"2. For .c/.cpp: include ALL function bodies (no TODOs)\n"
        f"3. For .h/.hpp: include proper declarations + inline impl\n"
        f"4. For .md: write actual content, not TODO\n"
        f"5. Keep it functional but concise (<200 lines)\n"
        f"6. Match existing project style from context\n\n"
        f"Code:"
    )
    
    try:
        gen_result, _ = chat_fn([], prompt, system_prompt="You are a senior C/C++ kernel developer. Output code only.", **base_kwargs)
        if gen_result:
            # Strip markdown
            clean = gen_result.strip()
            clean = _re.sub(r'^```[a-z]*\s*\n', '', clean)
            clean = _re.sub(r'\n```\s*$', '', clean)
            clean = clean.strip()
            
            if clean and len(clean) > 30:
                return "write_file", {"path": path, "content": clean}
    except Exception as e:
        print(f"[CONTENT-GEN] Failed: {e}", flush=True)
    
    return tool_name, tool_args

def _generate_file_content(fname, task):
    """Generate realistic placeholder content based on filename."""
    fname_lower = fname.lower()
    base_name = fname.split("/")[-1]
    
    # Handle known filenames without extension
    if base_name == "Makefile":
        return f"""# {task}
# Auto-generated Makefile

CC      = gcc
CXX     = g++
ASM     = nasm
LD      = ld

CFLAGS  = -Wall -Wextra -O2 -ffreestanding -nostdlib
LDFLAGS = -T linker.ld

SRCS    = $(wildcard *.c)
OBJS    = $(SRCS:.c=.o)
TARGET  = build/kernel.bin

all: $(TARGET)

$(TARGET): $(OBJS)
\t@mkdir -p build
\t$(CC) $(LDFLAGS) -o $@ $^

%.o: %.c
\t$(CC) $(CFLAGS) -c $< -o $@

clean:
\trm -rf build *.o

.PHONY: all clean
"""
    
    if base_name in ("CMakeLists.txt",) or fname_lower.endswith(".cmake"):
        return f"""# {task}
cmake_minimum_required(VERSION 3.20)
project(MyEngine VERSION 0.1.0 LANGUAGES C CXX ASM)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# TODO: add subdirectories
message(STATUS "My Engine configure complete")
"""
    
    class_name = base_name.replace(".hpp", "").replace(".cpp", "").replace(".h", "").replace(".c", "").replace(".cc", "")
    guard = fname.upper().replace(".", "_").replace("/", "_").replace("-", "_")
    
    if fname_lower.endswith((".hpp",)):
        return f"""// {task}
// My Engine - C++ Header

#ifndef {guard}
#define {guard}

#include <cstdint>
#include <memory>

namespace mymod {{

class {class_name} {{
public:
    {class_name}();
    ~{class_name}();
    
    void init();
    void update(float dt);
    void shutdown();

private:
    bool m_initialized = false;
}};

}} // namespace mymod

#endif // {guard}
"""
    
    if fname_lower.endswith((".h",)):
        return f"""/* {task} */
/* My Engine - C Header */

#ifndef {guard}
#define {guard}

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {{
#endif

typedef struct {{
    int initialized;
    /* TODO: add fields */
}} {class_name}_t;

void {class_name}_init({class_name}_t *self);
void {class_name}_update({class_name}_t *self, float dt);
void {class_name}_shutdown({class_name}_t *self);

#ifdef __cplusplus
}}
#endif

#endif /* {guard} */
"""
    
    if fname_lower.endswith((".cpp", ".cc")):
        return f"""// {task}
// My Engine - C++ Source

#include "{class_name}.hpp"
#include <cstdio>

namespace mymod {{

{class_name}::{class_name}() {{ puts("[{class_name}] ctor"); }}
{class_name}::~{class_name}() {{ shutdown(); }}

void {class_name}::init() {{
    if (m_initialized) return;
    puts("[{class_name}] init");
    m_initialized = true;
}}

void {class_name}::update(float dt) {{
    if (!m_initialized) return;
    (void)dt;
}}

void {class_name}::shutdown() {{
    if (!m_initialized) return;
    puts("[{class_name}] shutdown");
    m_initialized = false;
}}

}} // namespace mymod
"""
    
    if fname_lower.endswith((".c",)):
        return f"""/* {task} */
/* My Engine - C Source */

#include "{class_name}.h"
#include <stdio.h>

void {class_name}_init({class_name}_t *self) {{
    if (!self || self->initialized) return;
    puts("[{class_name}] init");
    self->initialized = 1;
}}

void {class_name}_update({class_name}_t *self, float dt) {{
    if (!self || !self->initialized) return;
    (void)dt;
}}

void {class_name}_shutdown({class_name}_t *self) {{
    if (!self || !self->initialized) return;
    puts("[{class_name}] shutdown");
    self->initialized = 0;
}}
"""
    
    if fname_lower.endswith((".asm", ".s")):
        return f"""; {task}
; My Engine - Assembly (NASM)
; TODO: implement

section .text
global _start

_start:
    ; TODO: entry point
    hlt
    jmp $
"""
    
    if fname_lower.endswith(".s") and fname.endswith(".S"):
        return f"""/* {task} */
/* My Engine - Assembly (GAS/AT&T) */

.section .text
.global _start

_start:
    /* TODO: entry point */
    hlt
    jmp .
"""
    
    if fname_lower.endswith((".ld", ".lds")):
        return f"""/* {task} */
/* Linker script */

ENTRY(_start)

SECTIONS {{
    . = 0x100000;
    .text : {{ *(.text*) }}
    .rodata : {{ *(.rodata*) }}
    .data : {{ *(.data*) }}
    .bss : {{ *(.bss*) }}
}}
"""
    
    if fname_lower.endswith(".md"):
        title = base_name.replace(".md", "").replace("-", " ").replace("_", " ").title()
        return f"""# {title}

> Auto-generated by Astra Agent

## Task
{task}

## TODO
- [ ] Fill content
"""
    
    if fname_lower.endswith(".txt"):
        return f"{task}\n"
    
    if fname_lower.endswith(".py"):
        return f"""# {task}

def main():
    print("TODO: {fname}")

if __name__ == "__main__":
    main()
"""
    
    return f"# {task}\nTODO: implement\n"


def _smart_override(tool_name, tool_args, task):
    """Minimal override: only fix wrong tool name. Content empty — let LLM generate."""
    import re as _re
    intent, _ = _classify_task(task)

    if intent == "mkdir":
        match = _re.search(r"(?:directory|folder|dir)\s+([a-zA-Z0-9_./-]+)", task, _re.IGNORECASE)
        if not match:
            words = [w.strip(".,;:") for w in task.split() if "/" in w]
            dir_name = words[-1] if words else "my_module"
        else:
            dir_name = match.group(1)
        return ("run_command", {"command": "mkdir -p " + dir_name})

    if intent == "write" and tool_name != "write_file":
        m = _re.search(r"[a-zA-Z0-9_./-]+\.(cpp|hpp|h|c|cc|asm|s|S|txt|md|py|js|ts|html|css|json|yml|yaml|toml|cmake|in|cfg|mk|sh|rs|go|java|ld|lds)", task)
        if m:
            return ("write_file", {"path": m.group(0), "content": ""})
        m2 = _re.search(r"(?:Makefile|CMakeLists\.txt|Kconfig)", task, _re.IGNORECASE)
        if m2:
            return ("write_file", {"path": m2.group(0), "content": ""})

    return (tool_name, tool_args)


def _estimate_complexity(goal: str):
    """
    Estimate task complexity based on goal.
    Returns (level, max_tasks, description).
    
    Levels:
    - LIGHT: 10 tasks (single file, script, hello world)
    - MEDIUM: 30 tasks (module, class, multi-component)
    - HEAVY: 80 tasks (engine, framework, multi-file project)
    - MASSIVE: 200 tasks (full engine + game from scratch)
    """
    g = goal.lower()
    length = len(goal)
    
    # === Explicit user hints (highest priority) ===
    if any(kw in g for kw in ['200 task', '200 tasks', 'massive', 'gila', 'seluruh engine']):
        return ('MASSIVE', 40, 'user-specified (max 40)')
    if any(kw in g for kw in ['100 task', '100 tasks', 'huge', 'big project']):
        return ('HEAVY', 100, 'user-specified 100 tasks')
    
    # === MASSIVE: full engine from scratch ===
    massive_kw = [
        'engine from scratch', 'complete engine', 'full engine', 'entire engine',
        'build entire', 'full framework', 'whole system', 'os from scratch',
        'game engine', '3d engine', 'vulkan engine', 'opengl engine',
        'pantas disebut', 'sampai jadi engine', 'sampai lengkap',
        'multi file engine', 'engine + game', 'engine dan game',
        'lanjutkan build', 'continue build', 'extend build',
        'engine untuk game', 'pantas di sebut', 'sampe pantas',
        'action-rpg', 'open world', 'gacha', 'monster',
    ]
    massive_count = sum(1 for kw in massive_kw if kw in g)
    if massive_count >= 2 or 'lanjutkan build' in g or 'continue build' in g:
        return ('MASSIVE', 40, f'full engine ({massive_count} keywords matched, AI decides count)')
    
    # === HEAVY: engine/framework components ===
    heavy_kw = [
        'engine', 'framework', 'vulkan', 'opengl', 'renderer', 'physics',
        'complete project', 'full stack', 'multi-file', 'entire project',
        'whole application', 'full implementation', 'sampai selesai',
    ]
    heavy_count = sum(1 for kw in heavy_kw if kw in g)
    if heavy_count >= 2 or length > 500:
        return ('HEAVY', 80, f'{heavy_count} heavy keywords, length={length}')
    
    # === MEDIUM: multi-component ===
    medium_kw = [
        'class', 'module', 'component', 'multiple files', 'system',
        'manager', 'controller', 'handler', 'service', 'api',
        '3 files', '5 files', 'beberapa file',
    ]
    if any(kw in g for kw in medium_kw) or length > 200:
        return ('MEDIUM', 30, 'multi-component task')
    
    # === LIGHT: simple ===
    light_kw = [
        'simple', 'quick', 'one file', 'single file', 'hello world',
        'bikin file', 'buat file', 'create file', 'buat script',
        'test', 'example', 'contoh',
    ]
    if any(kw in g for kw in light_kw) or length < 100:
        return ('LIGHT', 10, 'simple single-file task')
    
    # === Default ===
    return ('MEDIUM', 30, 'default medium')


def _scan_workspace(max_files=80):
    """Scan workspace to give agent context about existing files."""
    import subprocess as _sp
    from pathlib import Path as _P
    from config import WORKSPACE as _WS
    
    try:
        result = _sp.run(
            ["find", ".", "-maxdepth", "4", "-type", "f",
             "(", "-name", "*.c", "-o", "-name", "*.h", "-o", "-name", "*.cpp", "-o",
             "-name", "*.hpp", "-o", "-name", "*.asm", "-o", "-name", "*.S", "-o",
             "-name", "Makefile", "-o", "-name", "*.mk", "-o", "-name", "CMakeLists.txt", "-o",
             "-name", "Kconfig", "-o", "-name", "*.md", "-o", "-name", "*.py", ")", "-not", "-path", "*/.*"],
            cwd=str(_WS), capture_output=True, text=True, timeout=10
        )
        files = [l for l in result.stdout.strip().split('\n') if l][:max_files]
        
        # Get top-level dirs
        dirs_result = _sp.run(
            ["find", ".", "-maxdepth", "2", "-type", "d", "-not", "-path", "*/.*"],
            cwd=str(_WS), capture_output=True, text=True, timeout=10
        )
        dirs = [l for l in dirs_result.stdout.strip().split('\n') if l and l != '.'][:30]
        
        return {"files": files, "dirs": dirs, "workspace": str(_WS)}
    except Exception as e:
        return {"files": [], "dirs": [], "workspace": str(_WS), "error": str(e)}

def run_multi_agent(goal, planner_model=None, coder_model=None, on_log=None, max_tasks=40, max_total_attempts=None,  # auto-set based on complexity
                    base_url=None, api_key=None, model=None, coder_mode=False, status_callback=None, workspace=None):
    if workspace:
        try:
            from config import set_workspace
            set_workspace(workspace)
        except Exception as e:
            print(f"[WORKSPACE] Failed: {e}", flush=True)
    
    """Plan → Execute → Return results. Support custom API params."""
    
    def log(msg):
        if on_log: on_log(msg)
        print(f"[MULTI] {msg}", flush=True)
    

    # === AUTO-DETECT COMPLEXITY ===
    complexity_level, auto_tasks, complexity_reason = _estimate_complexity(goal)
    # Pakai auto_tasks kalau ada, kalau gak ada pakai max_tasks (default 200)
    effective_max_tasks = auto_tasks if auto_tasks else max_tasks
    effective_max_attempts = max_total_attempts if max_total_attempts else (effective_max_tasks * 3)
    # AUTO-SYNC: pakai effective_max_tasks untuk slice tasks nanti
    max_tasks = effective_max_tasks
    
    log(f"🎯 Complexity: {complexity_level} -> max {effective_max_tasks} tasks ({complexity_reason})")
    log(f"🎯 Retry budget: {effective_max_attempts} total attempts")
    
    if status_callback:
        status_callback("complexity", f"🎯 {complexity_level}: {effective_max_tasks} tasks max")
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
    
    # Task count range based on complexity
    task_ranges = {
        'LIGHT': (3, 10),
        'MEDIUM': (10, 30),
        'HEAVY': (30, 80),
        'MASSIVE': (10, 40),   # AI decides actual count within this range
    }
    min_tasks, suggested_max = task_ranges.get(complexity_level, (10, 30))
    
    # === SCAN WORKSPACE ===
    _ws_info = _scan_workspace()
    _ws_files = "\n".join(_ws_info["files"][:40]) or "(kosong)"
    _ws_dirs = "\n".join(_ws_info["dirs"][:20]) or "(kosong)"
    log(f"📂 Scanned workspace: {len(_ws_info['files'])} files, {len(_ws_info['dirs'])} dirs")
    # ============ PHASE 0: DEEP ANALYSIS ============
    try:
        log("🔬 Phase 0: Deep Analysis...")
        _analysis = _deep_analyze_workspace(goal)
        log(f"📊 Project: {_analysis['project_type']}, langs: {_analysis['languages']}")
        log(f"📄 Key files: {list(_analysis['key_files'].keys())[:5]}")
        
        if status_callback:
            status_callback("analysis", f"🔬 Analyzing ({_analysis['project_type']})")
        
        log("🔍 Phase 0.5: Compatibility Check...")
        _compat = _compatibility_check(goal, _analysis, chat_turn, base_kwargs)
        
        _compat_ok = _compat.get("compatible", True)
        _confidence = _compat.get("confidence", 50)
        _reasoning = _compat.get("reasoning", "")
        
        log(f"✅ Compatible: {_compat_ok} ({_confidence}%)")
        log(f"📝 {_reasoning[:200]}")
        
        for _w in _compat.get("warnings", [])[:3]:
            log(f"⚠️ Warning: {_w}")
        
        if not _compat_ok and _confidence > 70:
            log("❌ INCOMPATIBLE — aborting")
            pass  # BYPASSED — abort disabled
        
                # (v1 pre-scan removed — using generic _get_prioritized_files)


        _files_to_read = _get_prioritized_files(goal, _compat.get("files_to_read_first", []))
        if _files_to_read:
            log(f"📖 Reading {len(_files_to_read)} files...")
            from pathlib import Path as _P0
            from config import WORKSPACE as _WS0
            for _fname in _files_to_read[:5]:
                try:
                    _content = (_P0(_WS0) / _fname).read_text(errors="replace")[:3000]
                    _analysis["key_files"][_fname] = _content
                    log(f"   📖 {_fname}")
                except Exception as _e:
                    log(f"   ⚠️ {_fname}: {_e}")
    except Exception as _phase0_err:
        log(f"⚠️ Phase 0 failed: {_phase0_err}")
        _analysis = {"project_type": "unknown", "languages": [], "structure": [], "key_files": {}}
        _compat = {"compatible": True, "confidence": 50, "reasoning": "analysis failed", "files_to_read_first": [], "warnings": []}
    # ============ END PHASE 0 ============
    
    
    planner_prompt = f"""Break down this goal into atomic, executable tasks.

GOAL: {goal}

COMPLEXITY LEVEL: {complexity_level}
TARGET TASK COUNT: YOU DECIDE based on real scope (min useful, max {suggested_max})

DECISION GUIDE:
- Kalau perubahan kecil / fix bug / 1-2 file: 3-6 tasks
- Kalau fitur medium / 1 subsystem / 5-10 file: 8-15 tasks  
- Kalau proyek besar / multi subsystem: 20-{suggested_max} tasks
- Kalau workspace SUDAH punya banyak file existing: kurangi task baru, fokus integrasi
- JANGAN buang task untuk "explore" file yang nggak relevan dengan goal
- Kalau bisa digabung (misal .h + .c 1 modul): GABUNG jadi 1 task

=== PROJECT ANALYSIS ===
Type: {_analysis.get("project_type", "unknown")}
Languages: {", ".join(_analysis.get("languages", [])) or "unknown"}
Top files: {", ".join(_analysis.get("structure", [])[:15])}

Key files:
{chr(10).join(["=== " + k + " ===" + chr(10) + v[:1000] for k, v in list(_analysis.get("key_files", {}).items())[:3]])}

=== COMPATIBILITY ===
Compatible: {_compat.get("compatible", True)}
Confidence: {_compat.get("confidence", 50)}%
Approach: {_compat.get("recommended_approach", "normal")}
Warnings: {", ".join(_compat.get("warnings", [])) or "none"}

⚠️ FIT the existing structure. Use exact paths from analysis.

=== CURRENT WORKSPACE (already exists!) ===
Workspace: {_ws_info['workspace']}

Existing FILES (do NOT create duplicates, REUSE if relevant):
{_ws_files}

Existing DIRECTORIES (do NOT create duplicates):
{_ws_dirs}

⚠️ CRITICAL: Before creating a NEW folder or file, CHECK if similar path already exists above.
- If `src/mymod/` exists, EXTEND it, don't create `mymod/`
- If `include/mymod/` exists, ADD to it, don't create `include/mymod/`
- Use EXACT paths from the file list when modifying existing code

CRITICAL RULES:
1. Each task = ONE actionable step
2. For file creation: "Create <file>" (bukan "write content")
3. For complex projects: MANY TASKS (each file = 1 task)
4. For source files: 1 task per file
5. For build: "Create CMakeLists.txt" + "Configure build" + "Compile" + "Test"
6. NEVER echo the original goal as one task

CRITICAL RULES FOR MASSIVE GOALS (GENERIC):

🚨 EXTEND EXISTING, DO NOT REPLACE:
- The workspace ALREADY HAS code (see "files_to_read_first" context you were given).
- Your job is to EXTEND existing directories and files, NOT create parallel new structures.
- Read the file list carefully. Note the EXACT path convention used in this project.
- If a subsystem exists at `foo/bar/` with .c/.h files, DO NOT create `foo/bar_v2/` or `bar/` at root.
- Follow the EXACT path convention of existing files (same parent dir, same naming style).
- "Lanjutkan build" / "continue build" / "extend" means ADD FILES to existing dirs + FIX bugs. NOT start fresh.

🚨 RESPECT EXISTING TECH STACK:
- Check what build system already exists (Makefile? CMakeLists.txt? Cargo.toml? package.json?).
- DO NOT introduce a different build system.
- DO NOT add frameworks not present in the project.
- Match the language/runtime of existing code (kernel C vs userspace Python vs web JS, etc).

🚨 PRIORITIZE BY GAP, NOT BY AMBITION:
- Read the files you were given. Identify what is MISSING (stubs, empty files, TODO, broken builds).
- First 2-3 tasks: fix build errors + complete empty stubs in existing files.
- Later tasks: add NEW files ONLY when a subsystem is completely absent.
- Do NOT duplicate functionality that already exists in other files.

🚨 EXPLICIT PATHS FROM GOAL:
- If the user's goal mentions specific directories (e.g. "src/foo"), all your tasks MUST use those paths.
- If no paths mentioned, infer from existing structure.

CRITICAL RULES FOR MASSIVE GOALS (ENGINE/KERNEL):
Do NOT blindly generate 200 files! You must follow this strict sequence:
1. EKSPLORASI: Read Makefile, read main kernel entry (e.g. kernel.c), read configs.
2. IDENTIFIKASI ERROR: Run `make` to see if the current code even compiles.
3. ANALISIS ERROR: If build fails, the FIRST tasks MUST be to fix the build errors.
4. IMPLEMENTASI BERTAHAP: Only after the build is successful (or if no errors), start creating new files (1 file per task).
5. VERIFIKASI: After every new file, immediately try to build again to catch missing dependencies.

EXAMPLE for MASSIVE goal "build a complex engine":
[
  "Eksplorasi: baca Makefile",
  "Eksplorasi: baca kernel entry",
  "Identifikasi error: coba build dengan make",
  "Analisis: identifikasi penyebab error build",
  "Buat file: src/mymod/mymod.h",
  "Buat file: src/mymod/mymod.c",
  "Verifikasi: jalankan build setelah membuat modul"
]

Return ONLY a JSON array of strings. Keep tasks highly actionable and focused on fixing current state before adding massive features.

Return ONLY a JSON array of strings (between {min_tasks} and {suggested_max}).

Now generate tasks for the goal above:
"""
    
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

            temperature=0.3, max_tokens=8192,
            **base_kwargs
        )
        log(f"📥 Planner response: {len(plan_result)} chars")
        log(f"📥 Preview: {plan_result[:200]}")
    except Exception as e:
        log(f"❌ Planner error: {e}")
        return {"error": str(e)}
    
    # === ROBUST PARSER: 3 layer fallback ===
    tasks = []
    
    # Layer 1: _extract_json_array (most robust)
    try:
        parsed = _extract_json_array(plan_result)
        if parsed:
            tasks = [str(t).strip() for t in parsed if str(t).strip()][:max_tasks]
            log(f"✅ Layer 1 (json_array): {len(tasks)} tasks")
    except Exception as e:
        log(f"⚠ Layer 1 error: {e}")
    
    # Layer 2: Direct json.loads (fallback)
    if not tasks:
        try:
            clean = plan_result.strip()
            # Strip markdown
            import re as _re
            clean = _re.sub(r'^```(?:json)?\s*\n?', '', clean)
            clean = _re.sub(r'\n?```\s*$', '', clean)
            # Remove trailing commas
            clean = _re.sub(r',\s*([\]}])', r'\1', clean)
            parsed = json.loads(clean)
            if isinstance(parsed, list):
                tasks = [str(t).strip() for t in parsed if str(t).strip()][:max_tasks]
                log(f"✅ Layer 2 (json.loads): {len(tasks)} tasks")
        except Exception as e:
            log(f"⚠ Layer 2 error: {e}")
    
    # Layer 3: Line-by-line
    if not tasks:
        for line in plan_result.split('\n'):
            line = line.strip()
            m = re.match(r'^(?:\d+\.|\-|\*|")\s*(.+?)[",]?$', line)
            if m:
                task_text = m.group(1).strip().strip('"\'[]')
                if task_text and len(task_text) > 5 and not task_text.lower().startswith(('create a single', 'break down')):
                    tasks.append(task_text[:200])
                    if len(tasks) >= max_tasks: break
        if tasks:
            log(f"✅ Layer 3 (line): {len(tasks)} tasks")
    
    if not tasks:
        log("⚠ All parsers failed, using goal as single task")
        tasks = [goal]
    else:
        log(f"✅ Plan ready: {len(tasks)} tasks")
    if status_callback: status_callback("plan", f"📋 Rencana: {len(tasks)} langkah")
    
    for i, t in enumerate(tasks, 1):
        log(f"  {i}. {t[:80]}")
    
    results = []
    history = []
    
    AVAILABLE_TOOLS = """Kamu punya akses ke alat ini:

1. **read_file(path)** → BACA file yang SUDAH ADA. Kalau file nggak ada, akan error.
2. **write_file(path, content)** → TULIS/BUAT file baru (atau timpa yang lama). Pakai ini untuk CREATE atau MODIFY.
3. **run_command(command)** → Jalanin shell command (ls, cat, make, gcc, find, dll).

⚠️ PENTING:
- Kalau task = "Create X" atau "Write X" → pakai write_file
- Kalau task = "Read X" atau "Check X" → pakai read_file
- Kalau task = "List" atau "Find" → pakai run_command
- JANGAN pake read_file buat file yang belum ada.
    
    
    
- search_text(pattern, path=".", include="*.c,*.h"): cari regex di file
- find_files(pattern, path="."): cari file by glob
- multi_write(files): tulis BANYAK file sekaligus. files=[{"path":"a.h","content":"..."},{"path":"a.c","content":"..."}]
- rename_file(old, new): rename/move
- copy_file(src, dst): copy
- git_status(): git status short
- git_diff(path=""): git diff

"""
    coder_instructions = """
    [CODER MODE ACTIVE - HUMAN-LIKE REPORTER]
    
    You are a friendly autonomous coding agent that TALKS to the user while working.
    
    For every task:
    1. SCAN: Read file / check state. THEN report what you found.
    2. CODE: Make changes via tools. THEN report what you changed.
    3. VERIFY: Run build/syntax check. THEN report the result.
    4. FIX: If error, fix and re-verify. Report each step.
    
    REPORTING RULES (WAJIB):
    - After each tool call, ALWAYS say something to the user.
    - Use the user's language (Bahasa Indonesia if user uses Indonesian).
    - Examples:
      * "Aku cek file mymod_core.c... ada 3 function utama, ada warning di baris 42."
      * "Aku udah ubah fungsi render() - sekarang handle null pointer juga."
      * "Aku jalanin make... hasilnya sukses! Binary di build/myapp."
      * "Waduh, error di baris 42. Coba aku fix..."
      * "Beres! Ringkasan: aku tambah file X, ubah Y, build Z sukses."
    
    Tone: casual, friendly, informative. Kayak senior dev mentoring junior.
    JANGAN cuma "OK" atau "Done" tanpa penjelasan.
    """ if coder_mode else ""

    # Extract workspace name (computed once per run)
    try:
        from config import WORKSPACE as _WS
        workspace_name = _WS.name or str(_WS)
    except Exception:
        workspace_name = "workspace"
    
    total_attempts = 0
    max_retries_per_task = 2
    created_files_this_run = set()  # ← track per-run
    
    for i, task in enumerate(tasks, 1):
        log(f"⚙️ Task {i}/{len(tasks)}: {task[:60]}")
        if status_callback: status_callback("task", f"⚙️ Task {i}/{len(tasks)}: {task[:50]}")
        
        task_done = False
        task_attempts = 0
        task_result = None
        
        while not task_done and task_attempts < max_retries_per_task and total_attempts < effective_max_attempts:
            task_attempts += 1
            total_attempts += 1
            
            if task_attempts > 1:
                log(f"  🔄 Retry {task_attempts}/{max_retries_per_task} (total attempt: {total_attempts}/{effective_max_attempts})")

        
        exec_prompt = f"""Task {i}/{len(tasks)}: {task}

    [WORKSPACE CONTEXT - READ CAREFULLY]
    - You are ALREADY INSIDE the workspace folder `{workspace_name}`.
    - Current working directory (cwd) for ALL commands = `{workspace_name}`.
    - DO NOT prefix paths with `{workspace_name}/` - that will fail.
    - Use RELATIVE paths (e.g., `ls .`, `ls kernel/`, `cat main.c`).
    - Example BENAR: `ls -la .` atau `find . -name "*.c"`
    - Example SALAH: `ls -la {workspace_name}` atau `ls -la SomeProject/`
    - This is a LOCAL FOLDER on filesystem, NOT a website URL. Do NOT use browser tools.
    

{coder_instructions}
{coder_instructions}

Context dari task sebelumnya:
{chr(10).join([f'- {r[:300]}' for r in results[-2:] if r]) or 'Belum ada'}

{AVAILABLE_TOOLS}

INSTRUKSI KERAS:
1. JIKA TUGASNYA "Buat file" (file baru) dan file tersebut BELUM ADA, LANGSUNG pakai `write_file`. DILARANG nge-ls atau baca file yang belum ada!
2. JIKA TUGASNYA "Update file" (file sudah ada), BARU kamu wajib pakai `read_file` dulu sebelum edit.
3. Kalau butuh ngecek error build, pakai `run_command` (misal: `make`).
4. Kalau butuh tool, balas HANYA dengan JSON (tanpa teks lain):
   {{"tool": "write_file", "args": {{"path": "main.c", "content": "..."}}}}
   {{"tool": "run_command", "args": {{"command": "make -j4"}}}}

2. Kalau udah selesai / nggak butuh tool lagi, balas dengan LAPORAN NATURAL:
   - APA yang kamu temukan (kalau abis baca file)
   - APA yang kamu ubah (kalau abis edit)
   - HASIL (kalau abis run command)
   - Bahasa manusia, bukan "OK" doang.
   - Pakai bahasa user (Indonesia kalau user Indonesia).
   
   Contoh laporan bagus:
   - "Aku udah cek `mymod_core.c`. Ada 3 function: init, render, cleanup. Semua ada warning unused variable."
   - "Aku udah tambahin `mymod_glob.c` dengan fungsi `mymod_glob_init()`. Coba `make`."
   - "Waduh, `make` gagal di baris 42: missing semicolon. Aku fix dulu..."
   - "Beres! Build sukses. Binary ada di `build/myapp`."
"""

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

                temperature=0.3, max_tokens=16000,
                **base_kwargs
            )
            
            if not result:
                log(f"⚠️ Attempt {task_attempts}: AI return empty")
                if task_attempts >= max_retries_per_task:
                    log(f"  ❌ Task failed after {task_attempts} attempts")
                    results.append(f"FAILED: {task[:80]}")
                continue
            result_clean = result.strip()
            result_clean = re.sub(r'^```(?:json)?\n', '', result_clean)
            result_clean = re.sub(r'\n```$', '', result_clean)
            
            tool_call = _extract_first_json(result_clean)
            
            # Kalau JSON gagal di attempt > 1, paksa model pake format ketat
            if not tool_call and task_attempts > 1:
                log(f"⚠️ Attempt {task_attempts}: JSON invalid, forcing strict format...")
                try:
                    from chat import chat_turn as _ct
                except ImportError:
                    _ct = None
                strict_prompt = f"""TASK: {task}

RESPOND WITH ONLY ONE JSON OBJECT, NOTHING ELSE. No explanation, no markdown.

{{"tool": "write_file", "args": {{"path": "file.ext", "content": "..."}}}}
OR
{{"tool": "run_command", "args": {{"command": "mkdir -p dir"}}}}

Your answer:"""
                if _ct:
                    try:
                        retry_result, _ = _ct(history, strict_prompt, **base_kwargs)
                        if retry_result:
                            tool_call = _extract_first_json(retry_result.strip())
                            if tool_call:
                                log(f"✅ Retry success: {tool_call.get('tool')}")
                    except Exception as _e:
                        log(f"Retry error: {_e}")
            
            if tool_call:
                try:
                    tool_name = tool_call.get("tool")
                    tool_args = tool_call.get("args", {})
                    
                    log(f"🛠️ AI memanggil tool: {tool_name}")
                    
                    # Smart override: DISABLED (Membuat AI alergi ngecek dan halusinasi)
                    # _new_tool, _new_args = _smart_override(tool_name, tool_args, task)
                    pass

                    # Ensure real content for write_file
                    if tool_name == "write_file" and isinstance(tool_args, dict):
                        _before = tool_args.get("content", "")[:80]
                        tool_name, tool_args = _ensure_real_content(tool_name, tool_args, task, chat_turn, base_kwargs)
                        _after = tool_args.get("content", "")[:80] if isinstance(tool_args, dict) else ""
                        if _before != _after:
                            log("Content regenerated by LLM (" + str(len(tool_args.get("content", ""))) + " bytes)")
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
                        # Skip if directory already exists
                        if tool_name == "run_command" and isinstance(tool_args, dict):
                            _cmd = str(tool_args.get("command", ""))
                            if _cmd.startswith("mkdir"):
                                import re as _re_skip
                                _m = _re_skip.search(r"mkdir\s+-p\s+([a-zA-Z0-9_./-]+)", _cmd)
                                if _m:
                                    from pathlib import Path as _P
                                    from config import WORKSPACE as _WS
                                    _tgt = _P(_WS) / _m.group(1)
                                    if _tgt.is_dir():
                                        log(f"⏭️ Skip: {_m.group(1)} already exists")
                                        results.append(f"OK: {_m.group(1)} already exists")
                                        continue
                        tool_result = TOOLS[tool_name](**tool_args)
                        log(f"✅ Tool {tool_name} berhasil: {str(tool_result)[:100]}")
                        if status_callback: status_callback("done_tool", f"✅ {tool_name}")
                        
                        history.append({"role": "user", "content": exec_prompt})
                        history.append({"role": "assistant", "content": result})
                        history.append({"role": "user", "content": f"Hasil dari {tool_name}: {tool_result}"})
                        # Batasi history maksimal 6 pesan terakhir agar LLM tidak bingung (JSON invalid)
                        if len(history) > 6:
                            history = history[-6:]
                        
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

                            temperature=0.3, max_tokens=2048,
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
    
    # === FINAL SUMMARY ===
    import os as _os
    from pathlib import Path as _P2
    from config import WORKSPACE as _WS2
    
    try:
        created_files = sorted(list(created_files_this_run))
    except NameError:
        created_files = []
    
    log(f"📊 Summary:")
    log(f"   - Complexity: {complexity_level} (max {effective_max_tasks} tasks)")
    log(f"   - Tasks completed: {sum(1 for r in results if r and not r.startswith('FAILED'))}/{len(tasks)}")
    log(f"   - Files created/modified: {len(created_files)}")
    if created_files[:10]:
        log(f"   - Files: {', '.join(created_files[:10])}")
        if len(created_files) > 10:
            log(f"   - ... and {len(created_files) - 10} more")
    
    return {
        "goal": goal, 
        "tasks": tasks, 
        "results": results,
        "complexity": complexity_level,
        "created_files": created_files,
        "stats": {
            "total_tasks": len(tasks),
            "completed": sum(1 for r in results if r and not r.startswith('FAILED')),
            "failed": sum(1 for r in results if r and r.startswith('FAILED')),
        }
    }
