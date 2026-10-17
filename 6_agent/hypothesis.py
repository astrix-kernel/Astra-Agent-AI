"""Hypothesis-driven debugging-agent acts like a detective."""


HYPOTHESIS_PROMPT = """Kamu adalah **Debug Detective** — detektif bug yang metodis.

Bukan nebak-nebak. Kamu harus:
1. Kumpulkan evidence
2. Bikin HIPOTESIS (2-4 kemungkinan penyebab)
3. Ranking hipotesis by probability
4. Test tiap hipotesis lewat tool (read_file, grep, run_command, QEMU screenshot)
5. Eliminasi yang salah
6. Konklusi dari yang tersisa

## working format

**Fase 1 — INVESTIGASI**
Baca dulu: log error, kode terkait, config. Kumpulkan evidence.

**Fase 2 — HIPOTESIS**
Bikin JSON: {"hypotheses": [
  {"id": 1, "cause": "deskripsi", "prob": "high|medium|low", "test": "cara test"},
  ...
]}

**Fase 3 — TEST SATU-SATU**
Test hipotesis #1 pakai tool. Hasil → eliminate atau confirm.

**Fase 4 — KONKLUSI**
Cuma hipotesis yang lulus test yang di-anggap benar.

## strict rules
- JANGAN langsung fix tanpa test hipotesis dulu
- Kalau ada 2+ hipotesis yang mirip, test keduanya
- Kalau semua hipotesis gagal, MUNDUR dan bikin hipotesis baru
- Evidence > opini
"""


def is_debug_task(user_msg):
    """Check if this is task debugging."""

    m = user_msg.lower()
    triggers = ["error", "bug", "crash", "panic", "fail", "gagal",
                "rusak", "broken", "nggak jalan", "kok", "kenapa", "why",
                "debug", "fix", "benerin", "perbaiki"]
    return any(t in m for t in triggers)


def build_debug_context(error_text="", file_context=""):
    """Create a context prompt for debugging."""

    parts = []
    if error_text:
        parts.append(f"## ERROR/LOG\n{error_text[:2000]}")
    if file_context:
        parts.append(f"## KODE TERKAIT\n{file_context[:2000]}")
    return "\n\n".join(parts)


def format_hypotheses(hypotheses):
    """Format the hypothesis list into a string."""

    if not hypotheses:
        return ""
    lines = ["## 🕵️ HIPOTESIS"]
    for h in hypotheses:
        icon = "🔴" if h.get("prob") == "high" else "🟡" if h.get("prob") == "medium" else "🟢"
        lines.append(f"{icon} **#{h.get('id', '?')}** ({h.get('prob', '?')}): {h.get('cause', '?')}")
        if h.get("test"):
            lines.append(f"   Test: {h['test']}")
    return "\n".join(lines)
