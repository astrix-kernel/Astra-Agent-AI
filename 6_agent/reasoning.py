"""Chain-of-Thought reasoning for agents."""


REASONING_TEMPLATE = """

Sebelum jawab atau eksekusi, MIKIR DULU dalam 3 langkah:

**1. UNDERSTAND** — Apa yang user sebenernya minta?
- Apa pertanyaan/masalah intinya?
- Apa konteks yang gw tau?
- Apa yang belum jelas?

**2. ANALYZE** — Bagaimana cara terbaik?
- Approach apa aja yang mungkin?
- Mana yang paling efisien?
- Apa risiko/trade-off-nya?
- Apa yang bisa salah?

**3. PLAN** — Langkah konkret?
- Langkah 1: ...
- Langkah 2: ...
- Kalau gagal: fallback apa?

Setelah 3 langkah ini, BARU eksekusi/jawab.


User: "kok kernel panic pas init driver?"

❌ JAWABAN BURUK (langsung jawab):
"Kayaknya null pointer. Cek line 342."

✅ JAWABAN BAIK (CoT):
"Oke gw analisis:
1. UNDERSTAND: Kernel panic pas init driver = driver akses memory/hardware salah waktu init
2. ANALYZE: Kemungkinan penyebab:
   - Null pointer (paling umum)
   - Akses alamat fisik salah
   - Hardware belum ready
   - Interrupt handler bug
3. PLAN: Cek log panic dulu (error code + RIP), terus lihat fungsi init driver yang dipanggil. Kalau null pointer, cek return value alloc gagal di-handle.

Coba kasih gw output panic-nya, gw baca dulu."
"""


def get_reasoning_addon():
    return REASONING_TEMPLATE
