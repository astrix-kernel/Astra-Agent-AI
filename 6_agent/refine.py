"""Iterative refinement — draft, critique, improve."""



DRAFT_PROMPT = """Kasih jawaban DRAFT (bisa kasar, yang penting arahnya bener)."""

CRITIQUE_PROMPT = """Kritik DRAFT jawaban di bawah ini. Cari kelemahan, error, yang kurang.

Format:
- KELEMAHAN: ...
- YANG KURANG: ...
- SARAN: ...
"""

IMPROVE_PROMPT = """Bikin versi PERBAIKAN dari draft, berdasarkan kritik.

Fokus: perbaiki kelemahan, tambah yang kurang, tetap di jalur benar.

Output: jawaban final (bukan kritik baru).
"""


def should_refine(user_msg, focus="chat"):
    """Check whether iterative refinement is needed."""

    if focus != "chat":
        return False
    m = user_msg.lower()
    complex_triggers = [
        "jelasin detail", "analisis", "bandingin", "review", "kritik",
        "gimana cara", "strategi", "arsitektur", "design", "best practice"
    ]
    return any(t in m for t in complex_triggers) and len(user_msg) > 40


def refine_once(messages, rounds=1):
    """
    Refine jawaban agent. Return final response.
    """
    from llm import call_llm

    draft = call_llm(messages, max_tokens=1500, temperature=0.5)
    if not draft or len(draft) < 100:
        return draft

    current = draft

    for i in range(rounds):
        critique_msgs = [
            {"role": "system", "content": CRITIQUE_PROMPT},
            {"role": "user", "content": f"Task asli: {messages[-1]['content'][:500]}\n\nDraft:\n{current[:2000]}"},
        ]
        critique = call_llm(critique_msgs, max_tokens=500, temperature=0.3)

        improve_msgs = [
            {"role": "system", "content": IMPROVE_PROMPT},
            {"role": "user", "content": f"Task: {messages[-1]['content'][:500]}\n\nDraft:\n{current[:2000]}\n\nKritik:\n{critique[:800]}"},
        ]
        current = call_llm(improve_msgs, max_tokens=2000, temperature=0.4)

    return current
