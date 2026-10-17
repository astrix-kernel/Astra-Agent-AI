"""Multi-model consultation — tanya beberapa model, sintesis jawaban."""
import concurrent.futures
from llm import call_llm


CONSULT_PROMPT = """Kamu adalah salah satu dari beberapa AI yang diminta jawab pertanyaan.
Jawab dengan jujur, singkat, fokus. Kalau nggak tau, bilang nggak tau.
Berikan perspektif terbaikmu, nggak usah basa-basi."""


SYNTHESIS_PROMPT = """Kamu adalah sintesisator. Beberapa AI udah jawab pertanyaan yang sama.
Tugasmu: gabungkan jawaban terbaik dari semua, buang yang salah/kontradiktif,
hasilkan JAWABAN FINAL yang paling akurat dan lengkap.

Format:
1. **Jawaban Final**: [jawaban gabungan]
2. **Konsensus**: [poin yang semua setuju]
3. **Perbedaan**: [kalau ada yang beda pendapat]

Jangan sebut "AI 1 bilang...", langsung sintesis aja."""


def consult(question, models=None, max_workers=3):
    """
    Tanya beberapa model, terus sintesis.
    models: list of model keys (contoh ["nemotron-ultra", "kimi-k3"])
    """
    import runtime

    if models is None:
        # Default: pilih 2-3 model berbeda karakter
        models = ["nemotron-ultra", "kimi-k3"]

    old_model = runtime.get_model_key()
    results = {}

    def ask_one(model_key):
        try:
            runtime.set_model(model_key)
            msgs = [
                {"role": "system", "content": CONSULT_PROMPT},
                {"role": "user", "content": question},
            ]
            response = call_llm(msgs, max_tokens=2048, temperature=0.3)
            return model_key, response
        except Exception as e:
            return model_key, f"[ERROR: {e}]"

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(ask_one, m) for m in models]
        for f in concurrent.futures.as_completed(futures):
            try:
                k, v = f.result()
                results[k] = v
            except Exception:
                pass

    # Balikin ke model semula
    try:
        runtime.set_model(old_model)
    except Exception:
        pass

    # Kalau cuma 1 berhasil, balikin aja
    if len(results) <= 1:
        return list(results.values())[0] if results else "(no response)"

    # Sintesis
    try:
        combined = "\n\n".join(f"## Jawaban dari {k}:\n{v}" for k, v in results.items())
        syn_msgs = [
            {"role": "system", "content": SYNTHESIS_PROMPT},
            {"role": "user", "content": f"Pertanyaan: {question}\n\n{combined}"},
        ]
        final = call_llm(syn_msgs, max_tokens=3000, temperature=0.3)
        return final
    except Exception as e:
        # Kalau sintesis gagal, gabung manual
        return "\n\n---\n\n".join(f"**{k}:**\n{v}" for k, v in results.items())


def should_consult(user_msg):
    """Cek apakah pertanyaan worth consult multi-model."""
    m = user_msg.lower()
    triggers = [
        "kenapa", "mengapa", "analisis", "bandingin", "bandingkan",
        "mana yang lebih", "review", "kritik", "saran", "menurut lu",
        "gimana cara", "solusi terbaik", "best practice"
    ]
    if any(t in m for t in triggers) and len(user_msg) > 30:
        return True
    return False
