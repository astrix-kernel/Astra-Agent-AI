"""LLM client — OmniRoute → Nemotron, BRUTAL retry to love server."""

import json, time, requests
from requests.adapters import HTTPAdapter
from config import LLM_URL, LLM_API_KEY

_session = requests.Session()
_adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)

def _build_payload(model_id, messages, max_tokens, temperature, stream=False):
    """Build payload-reasoning_effect medium for large reasoning models."""

    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }
    if "ultra" in model_id.lower() or "opus" in model_id.lower() or "reasoning" in model_id.lower():
        payload["reasoning_effort"] = "medium"
        payload["chat_template_kwargs"] = {"enable_thinking": True, "reasoning_effort": "medium"}
    return payload

CONNECT_TIMEOUT = 60
READ_TIMEOUT = 7200 


def call_llm(messages, max_tokens=None, temperature=None):
    """Call LLM. Handle reasoning model (content=null naikin max→_tokens)."""

    import runtime as _rt
    cfg = _rt.cfg()
    if max_tokens is None:
        max_tokens = cfg.get("max_tokens_executor", 8192)
    if temperature is None:
        temperature = cfg.get("temperature", 0.1)

    attempt = 0
    consecutive_503 = 0

    while True:
        attempt += 1
        try:
            t0 = time.time()
            r = _session.post(
                LLM_URL,
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=_build_payload(_rt.get_model_id(), messages, max_tokens, temperature, stream=False),
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            elapsed = time.time() - t0

            if r.status_code in (500, 502, 503, 504):
                consecutive_503 += 1
                wait = 3 if consecutive_503 <= 3 else min(5 + consecutive_503 * 2, 60)
                print(f"  ⏳ [{consecutive_503}x] {r.status_code}, tunggu {wait}s...", flush=True)
                time.sleep(wait)
                continue

            if r.status_code == 429:
                print(f"  ⏳ Rate limit, tunggu 30s...", flush=True)
                time.sleep(30)
                continue

            if r.status_code != 200:
                print(f"  ❌ HTTP {r.status_code}: {r.text[:200]}", flush=True)
                time.sleep(10)
                if attempt > 30:
                    raise RuntimeError(f"HTTP {r.status_code}")
                continue

            data = r.json()
            if "choices" not in data:
                print(f"  ⚠️  Response aneh, retry...", flush=True)
                time.sleep(5)
                continue

            msg = data["choices"][0].get("message", {}) or {}
            content = (msg.get("content") or "").strip()
            reasoning = (msg.get("reasoning_content") or "").strip()
            finish = data["choices"][0].get("finish_reason", "")

            if consecutive_503 > 0:
                print(f"  ✅ SUKSES setelah {consecutive_503} retry ({elapsed:.1f}s)", flush=True)
                consecutive_503 = 0

            if not content and reasoning and finish == "length":
                new_max = min(max_tokens * 4, 64000)
                print(f"  ⚠️  Reasoning kepotong, max_tokens {max_tokens} → {new_max}", flush=True)
                max_tokens = new_max
                continue

            if not content and not reasoning:
                print(f"  ⚠️  Response kosong, retry...", flush=True)
                time.sleep(2)
                continue

            return content if content else reasoning

        except requests.exceptions.ReadTimeout:
            timeout_count = locals().get('timeout_count', 0) + 1
            print(f"  ⏳ Read timeout ({timeout_count}), retry...", flush=True)
            time.sleep(5)
            continue
        except requests.exceptions.ConnectTimeout:
            print(f"  ⏳ Connect timeout, tunggu 30s...", flush=True)
            time.sleep(30)
            continue
        except requests.exceptions.ConnectionError as e:
            print(f"  ⏳ Koneksi gagal, tunggu 15s...", flush=True)
            time.sleep(15)
            continue
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if attempt > 50:
                raise
            print(f"  ⚠️  [{attempt}] {type(e).__name__}: {str(e)[:150]}, tunggu 10s...", flush=True)
            time.sleep(10)
            continue




def call_llm_stream(messages, max_tokens=None, temperature=None, on_token=None):
    """
    Panggil LLM dengan streaming. on_token callback per chunk.
    Return: (full_text, success)
    """
    import runtime as _rt
    cfg = _rt.cfg()
    if max_tokens is None:
        max_tokens = cfg.get("max_tokens_executor", 8192)
    if temperature is None:
        temperature = cfg.get("temperature", 0.1)

    attempt = 0
    consecutive_503 = 0

    while True:
        attempt += 1
        try:
            r = _session.post(
                LLM_URL,
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _rt.get_model_id(),
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                },
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                stream=True,
            )

            if r.status_code in (500, 502, 503, 504):
                consecutive_503 += 1
                wait = 3 if consecutive_503 <= 3 else min(5 + consecutive_503 * 2, 60)
                print(f"  ⏳ [{consecutive_503}] 503, tunggu {wait}s...", flush=True)
                time.sleep(wait)
                continue

            r.raise_for_status()

            full = []
            for line in r.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full.append(content)
                        if on_token:
                            on_token(content)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

            return "".join(full), True

        except requests.exceptions.ReadTimeout:
            print(f"  ⏳ Timeout, retry...", flush=True)
            time.sleep(10)
            continue
        except requests.exceptions.ConnectionError:
            print(f"  ⏳ Koneksi gagal, tunggu 30s...", flush=True)
            time.sleep(30)
            continue
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if attempt > 100:
                return "", False
            print(f"  ⚠️  [{attempt}] {str(e)[:150]}, tunggu 10s...", flush=True)
            time.sleep(10)
            continue



def call_llm_streaming(messages, max_tokens=None, temperature=None, on_chunk=None):
    """
    Streaming version — panggil on_chunk(text) tiap potongan kata datang.
    Return: full_text
    """
    import runtime as _rt
    import json as _json
    cfg = _rt.cfg()
    if max_tokens is None:
        max_tokens = cfg.get("max_tokens_chat", 4096)
    if temperature is None:
        temperature = cfg.get("temperature", 0.5)

    attempt = 0
    consecutive_503 = 0

    while True:
        attempt += 1
        try:
            r = _session.post(
                LLM_URL,
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _rt.get_model_id(),
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                },
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                stream=True,
            )

            if r.status_code in (500, 502, 503, 504):
                consecutive_503 += 1
                wait = 3 if consecutive_503 <= 3 else min(5 + consecutive_503 * 2, 60)
                print(f"  ⏳ [{consecutive_503}x] {r.status_code}, tunggu {wait}s...", flush=True)
                import time as _t
                _t.sleep(wait)
                continue

            r.raise_for_status()

            full = []
            for line in r.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = _json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content") or ""
                    reasoning = delta.get("reasoning_content") or ""
                    chunk_text = content if content else reasoning
                    if chunk_text:
                        full.append(chunk_text)
                        if on_chunk:
                            try:
                                on_chunk(chunk_text)
                            except Exception:
                                pass
                except Exception:
                    continue

            if consecutive_503 > 0:
                print(f"  ✅ Server balik setelah {consecutive_503} retry", flush=True)

            return "".join(full)

        except requests.exceptions.ConnectionError:
            print(f"  ⏳ Koneksi gagal, tunggu 10s...", flush=True)
            import time as _t
            _t.sleep(10)
            continue
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if attempt > 30:
                raise
            print(f"  ⚠️  [{attempt}] {type(e).__name__}: {str(e)[:150]}", flush=True)
            import time as _t
            _t.sleep(10)
            continue
