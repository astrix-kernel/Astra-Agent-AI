"""Chat module — komunikasi ke LLM (streaming & non-streaming). Simpel aja."""
import json
import requests
import stop_flag
from config import LLM_URL, LLM_API_KEY


def _build_messages(history, user_msg, system_prompt):
    """Susun messages array buat API."""
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.extend(history or [])
    msgs.append({"role": "user", "content": user_msg})
    return msgs


def _stream_api(url, headers, payload, on_chunk, timeout=(10, 300)):
    """Stream dari API OpenAI-compatible. Return full text."""
    full = []
    try:
        r = requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout)
        if not r.ok:
            err = r.text[:300]
            if on_chunk:
                on_chunk(f"❌ API Error {r.status_code}: {err}")
            return "".join(full)
        
        for line in r.iter_lines():
            # Stop check — biar bisa cancel dari web
            if stop_flag.is_stopped():
                print('[STREAM] ⛔ Stop flag detected', flush=True)
                if on_chunk:
                    on_chunk('\n\n⛔ **Dihentikan oleh user.**')
                return ''.join(full)
            if not line:
                continue
            line_str = line.decode("utf-8", errors="ignore")
            if not line_str.startswith("data: "):
                continue
            data = line_str[6:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except Exception:
                continue
            
            choices = chunk.get("choices", [])
            if not choices:
                continue
            
            delta = choices[0].get("delta", {})
            content = delta.get("content", "")
            # SKIP reasoning_content (thinking) — cuma tampilin jawaban final
            if content:
                full.append(content)
                if on_chunk:
                    on_chunk(content)
    except requests.exceptions.Timeout:
        if on_chunk:
            on_chunk("\n\n⚠️ Timeout: API terlalu lama.")
    except Exception as e:
        if on_chunk:
            on_chunk(f"\n\n❌ {type(e).__name__}: {e}")
    return "".join(full)


def chat_turn_streaming(history, user_msg, focus="chat", on_chunk=None,
                        web_search=False, system_prompt="You are a helpful AI assistant.",
                        temperature=0.7, max_tokens=4096, compress_history=False,
                        custom_base_url=None, custom_api_key=None, custom_model=None,
                        top_p=0.9, top_k=40, freq_pen=0.0, pres_pen=0.0,
                        language="id"):
    """Chat streaming — support custom API & default OmniRoute."""
    
    # Web search instruction (simple mode)
    if web_search:
        system_prompt = system_prompt + "\n\n[WEB SEARCH MODE] Kalau butuh info real-time, bilang lu butuh search."
    
    messages = _build_messages(history, user_msg, system_prompt)
    
    # === CUSTOM API ===
    if custom_base_url and custom_api_key:
        url = custom_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {custom_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": custom_model or "gpt-4o",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": True,
        }
        print(f"[CHAT] Custom API: {url} | model={custom_model}")
        return _stream_api(url, headers, payload, on_chunk)
    
    # === DEFAULT OMNIROUTE ===
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": custom_model or "deepseek/deepseek-v4-flash",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    print(f"[CHAT] Default: {LLM_URL} | model={payload['model']}")
    return _stream_api(LLM_URL, headers, payload, on_chunk)


def chat_turn(history, user_msg, focus="chat", max_tool_rounds=None,
              web_search=False, system_prompt="You are a helpful AI assistant.",
              temperature=0.7, max_tokens=4096, compress_history=False,
              language="id", custom_base_url=None, custom_api_key=None, custom_model=None,
              top_p=0.9, top_k=40, freq_pen=0.0, pres_pen=0.0):
    """Non-streaming chat — support custom provider + default OmniRoute."""
    messages = _build_messages(history, user_msg, system_prompt)
    
    # === CUSTOM API ===
    if custom_base_url and custom_api_key:
        url = custom_base_url.rstrip('/') + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {custom_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": custom_model or "gpt-4o",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": False,
        }
        print(f"[CHAT-TURN] Custom: {url} | model={custom_model}", flush=True)
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=(30, 300))
            if r.ok:
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"[CHAT-TURN] Got {len(content)} chars", flush=True)
                return content, None
            else:
                err = r.text[:200]
                print(f"[CHAT-TURN] HTTP {r.status_code}: {err}", flush=True)
                return f"Error HTTP {r.status_code}: {err}", None
        except Exception as e:
            print(f"[CHAT-TURN] Exception: {e}", flush=True)
            return f"Error: {e}", None
    
    # === DEFAULT OMNIROUTE ===
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": custom_model or "deepseek/deepseek-v4-flash",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    print(f"[CHAT-TURN] Default: {LLM_URL}", flush=True)
    try:
        r = requests.post(LLM_URL, headers=headers, json=payload, timeout=(10, 120))
        if r.ok:
            data = r.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content, None
        return f"Error: {r.text[:200]}", None
    except Exception as e:
        return f"Error: {e}", None
