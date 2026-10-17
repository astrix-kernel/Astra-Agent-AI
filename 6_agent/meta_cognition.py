"""Meta-cognition-agent knows when to be sure vs. not."""


META_PROMPT = """Kamu adalah **Meta-Thinker** — bagian otak agent yang monitor kepastian.

Setelah agent mau jawab, KAMU evaluasi: seberapa yakin agent terhadap jawabannya?


**CERTAIN (90-100%)** — Yakin banget. Fakta jelas, evidence kuat.
**CONFIDENT (70-89%)** — Cukup yakin. Reasonable assumption.
**UNSURE (40-69%)** — Ragu-ragu. Butuh konfirmasi user.
**GUESSING (0-39%)** — Nebak. Nggak ada dasar cukup.


- **CERTAIN/CONFIDENT** → jawab langsung dengan yakin
- **UNSURE** → jawab + disclaimer: "Gw kurang yakin, tapi..."
- **GUESSING** → jangan jawab, minta klarifikasi: "Gw butuh info lebih: ..."


Kalau agent ngasih jawaban dengan nada yakin tapi confidence-nya rendah → itu HALUSINASI.
Red flag:
- Bikin klaim spesifik tanpa sumber
- Nyebut fungsi/API yang mungkin nggak ada
- Nyimpulin tanpa evidence
- Ngasih nomor/angka spesifik tanpa hitungan

{"confidence": 0-100, "level": "certain|confident|unsure|guessing", "reason": "kenapa level ini", "should_disclaim": true|false}

Kalau confidence < 40, agent HARUS minta klarifikasi bukan jawab.
"""


def evaluate(user_msg, agent_response, context=""):
    """
    Evaluasi confidence jawaban.
    Return: (confidence, level, reason, should_disclaim)
    """
    import json, re
    from llm import call_llm

    prompt = f"""## USER
{user_msg[:800]}

{agent_response[:2000]}

{context[:500] if context else '(none)'}

Evaluasi confidence agent. Output JSON."""

    try:
        raw = call_llm(
            [
                {"role": "system", "content": META_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.2,
        )

        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE)
        m = re.search(r'\{[\s\S]*\}', raw)
        if not m:
            return 80, "confident", "", False

        obj = json.loads(m.group())
        return (
            obj.get("confidence", 80),
            obj.get("level", "confident"),
            obj.get("reason", ""),
            obj.get("should_disclaim", False),
        )
    except Exception as e:
        return 80, "confident", f"(meta error: {e})", False


def add_disclaimer(response, confidence, level):
    """Add a disclaimer if necessary."""

    if level == "certain" or level == "confident":
        return response
    if level == "unsure":
        return f"⚠️ *Gw agak kurang yakin, tapi ini dugaan gw:*\n\n{response}"
    return f"❓ *Gw masih nebak nih, konfirmasi dulu ya:*\n\n{response}"


def should_ask_clarification(confidence):
    return confidence < 40
