"""Self-reflection — review jawaban sendiri sebelum kirim."""

REFLECT_PROMPT = """Kamu adalah **Self-Critic** — reviewer internal agent.

Kamu akan lihat:
1. Pertanyaan/task user
2. Jawaban yang agent mau kirim

Tugasmu: KRITIK jawaban itu dengan keras. Cari kelemahan.

## YANG DIKRITIK
- **Akurasi**: ada yang salah/faktual salah?
- **Kelengkapan**: ada yang kelewat?
- **Kejelasan**: bisa dipahami?
- **Relevansi**: jawab pertanyaan yang diminta, bukan yang lain?
- **Halusinasi**: ada klaim tanpa dasar?
- **Logika**: kesimpulan valid dari premis?

## OUTPUT FORMAT (JSON)
{"score": 1-10, "issues": ["masalah 1", "masalah 2"], "verdict": "accept|revise", "suggestion": "cara perbaiki"}

- score 8-10 → accept (langsung kirim)
- score < 8 → revise (perbaiki dulu)

Kalau jawaban udah bagus: {"score": 9, "issues": [], "verdict": "accept", "suggestion": ""}
Kalau ada yang salah: {"score": 5, "issues": ["..."], "verdict": "revise", "suggestion": "..."}
"""


def critique(user_msg, agent_response, context=""):
    """
    Review jawaban agent. Return: (score, verdict, issues, suggestion).
    """
    import json, re
    from llm import call_llm

    prompt = f"""## USER MESSAGE
{user_msg[:1000]}

## AGENT RESPONSE
{agent_response[:3000]}

## KONTEKS
{context[:500] if context else '(none)'}

Review jawaban di atas. Output JSON."""

    try:
        raw = call_llm(
            [
                {"role": "system", "content": REFLECT_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.3,
        )

        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE)
        m = re.search(r'\{[\s\S]*\}', raw)
        if not m:
            return 8, "accept", [], ""

        obj = json.loads(m.group())
        score = obj.get("score", 8)
        verdict = obj.get("verdict", "accept")
        issues = obj.get("issues", [])
        suggestion = obj.get("suggestion", "")

        return score, verdict, issues, suggestion
    except Exception as e:
        return 8, "accept", [], f"(reflect error: {e})"


def improve(user_msg, agent_response, issues, suggestion, context=""):
    """Bikin versi perbaikan dari jawaban."""
    from llm import call_llm

    prompt = f"""Jawaban sebelumnya ada masalah. Perbaiki!

## USER MESSAGE
{user_msg[:800]}

## JAWABAN SEBELUMNYA (yang mau diperbaiki)
{agent_response[:2000]}

## MASALAH YANG DITEMUKAN
{chr(10).join('- ' + i for i in issues)}

## SARAN PERBAIKAN
{suggestion}

## KONTEKS
{context[:500] if context else '(none)'}

Sekarang tulis JAWABAN BARU yang lebih baik. Fokus perbaiki masalah di atas.
Jangan jelasin apa yang lu perbaiki — langsung kasih jawaban baru."""

    try:
        return call_llm(
            [{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.4,
        )
    except Exception:
        return agent_response  # fallback


def should_reflect(user_msg, agent_response, focus="chat"):
    """Cek apakah perlu reflect — skip kalau simpel."""
    # Skip reflection kalau:
    # - Jawaban pendek (<= 50 char)
    # - Chat simple (greeting)
    if len(agent_response) < 50:
        return False
    if focus == "chat" and len(user_msg) < 20:
        return False
    # Skip kalau code block panjang (agent eksekusi task)
    if agent_response.count("```") >= 4:
        return False
    return True


def reflect_and_improve(user_msg, agent_response, context="", max_iter=1):
    """
    Reflection + auto-improve.
    Return: (final_response, reflection_info)
    """
    if not should_reflect(user_msg, agent_response):
        return agent_response, {"skipped": True}

    score, verdict, issues, suggestion = critique(user_msg, agent_response, context)

    info = {
        "initial_score": score,
        "verdict": verdict,
        "issues": issues,
        "improved": False,
    }

    if verdict == "accept" or score >= 8:
        return agent_response, info

    # Perbaiki
    improved = improve(user_msg, agent_response, issues, suggestion, context)
    info["improved"] = True
    return improved, info
