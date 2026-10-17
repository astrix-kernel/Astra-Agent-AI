"""Vision — analisis gambar/screenshot."""
import base64
from pathlib import Path


def encode_image(path):
    """Encode image ke base64 untuk API."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image(image_path, question="Jelaskan apa yang lu lihat di gambar ini, fokus ke masalah teknis kalau ada."):
    """Kirim gambar ke model vision-capable."""
    import requests, json
    from config import LLM_URL, LLM_API_KEY
    import runtime

    b64 = encode_image(image_path)
    ext = Path(image_path).suffix.lstrip(".") or "png"
    if ext == "jpg": ext = "jpeg"

    model = "nvidia/moonshotai/kimi-k3"
    try:
        model = runtime.get_model_id()
    except Exception:
        pass

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:image/{ext};base64,{b64}"}},
            ]
        }
    ]

    try:
        r = requests.post(
            LLM_URL,
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 2048,
                "temperature": 0.3,
            },
            timeout=120,
        )
        if r.status_code != 200:
            return f"❌ HTTP {r.status_code}: {r.text[:200]}"
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ Error: {e}"


def analyze_screenshot_latest(question=None):
    """Analisis screenshot QEMU terbaru."""
    shots = Path.home() / ".astrix-agent/screenshots"
    if not shots.exists():
        return "❌ Belum ada screenshot"
    pngs = sorted(shots.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pngs:
        return "❌ Belum ada screenshot"
    q = question or "Ini screenshot OS dari QEMU. Analisis: apa yang keliatan? Ada error/bug? Framebuffer bener?"
    return analyze_image(str(pngs[0]), q)
