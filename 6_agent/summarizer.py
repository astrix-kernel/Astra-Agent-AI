"""Auto-summarize long sessions."""

from llm import call_llm


SUMMARIZE_PROMPT = """Kamu adalah summarizer. Ringkas percakapan berikut jadi poin-poin penting.
Format:
- [poin 1]
- [poin 2]

- [poin]

- [poin]

Singkat, padat, max 200 kata. Fokus yang penting-penting aja."""


def summarize_history(messages):
    """Summarize the message list into a short summary."""

    if not messages or len(messages) < 10:
        return None

    recent = messages[-30:]
    convo = "\n".join(
        f"{m['role'].upper()}: {m['content'][:500]}"
        for m in recent
    )

    try:
        response = call_llm(
            [
                {"role": "system", "content": SUMMARIZE_PROMPT},
                {"role": "user", "content": convo},
            ],
            max_tokens=800,
            temperature=0.3,
        )
        return response
    except Exception as e:
        return None


def should_summarize(messages, threshold=40):
    """Check whether the history needs to be summarized."""

    return len(messages) >= threshold
