# Advanced Prompt Engineering: Chain-of-Thought, ReAct Orchestration, & Strict Structured JSON Schema

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda mampu:

1. **Membangun** prompt Chain-of-Thought (CoT) multi-langkah yang menghasilkan reasoning trace yang dapat diaudit dan diverifikasi secara deterministik.
2. **Mengimplementasikan** pola ReAct (Reasoning + Acting) untuk membangun agen LLM yang dapat memanggil tools eksternal secara iteratif berdasarkan observasi.
3. **Merancang** JSON Schema yang ketat (strict) sebagai kontrak output LLM sehingga respons dapat diintegrasikan langsung ke pipeline produksi tanpa post-processing manual.
4. **Mendiagnosis** kegagalan prompt seperti hallucination dalam reasoning chain, tool-call loop tak terbatas, dan schema violation secara sistematis.
5. **Memilih** teknik prompt engineering yang tepat berdasarkan kompleksitas tugas, latensi requirement, dan cost constraint dalam sistem produksi.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:

| Konsep | Tingkat Pemahaman yang Dibutuhkan |
|---|---|
| Cara kerja LLM (autoregressive generation, temperature, top-p) | Menengah — tahu bahwa LLM memprediksi token berikutnya |
| Tokenization (BPE, tiktoken) | Dasar — memahami bahwa teks dipecah menjadi token dan ada batas konteks |
| Transformer architecture (attention mechanism) | Dasar — memahami bahwa model memproses konteks secara paralel |
| Prompt anatomy (system/user/assistant roles) | Dasar — pernah membuat prompt multi-turn |
| Python async programming | Menengah — memahami `async/await`, `asyncio` |
| JSON dan JSON Schema draft-07/2020-12 | Dasar — memahami `type`, `properties`, `required`, `enum` |
| REST API dan HTTP | Dasar — pernah memanggil API dengan `requests` atau `httpx` |

---

## 3. Concept

### Mengapa Prompt Engineering Adalah Disiplin Rekayasa, Bukan Seni

Prompt engineering sering disalahpahami sebagai aktivitas "mencoba-coba kata-kata" hingga model menghasilkan output yang diinginkan. Pandangan ini fundamental salah di konteks produksi. Prompt adalah **kode yang dieksekusi oleh mesin probabilistik** — setiap token dalam prompt menggeser distribusi probabilitas output secara matematis.

Ketiga teknik dalam modul ini — CoT, ReAct, dan Structured Output — mewakili tiga lapisan abstraksi berbeda dalam rekayasa prompt:

```
┌─────────────────────────────────────────────────────┐
│           LAPISAN ABSTRAKSI PROMPT ENGINEERING       │
├─────────────────────────────────────────────────────┤
│  L3: ORCHESTRATION    │  ReAct — agen multi-step    │
│                       │  dengan tool calls          │
├─────────────────────────────────────────────────────┤
│  L2: REASONING        │  Chain-of-Thought           │
│                       │  reasoning traces           │
├─────────────────────────────────────────────────────┤
│  L1: OUTPUT CONTRACT  │  JSON Schema enforcement    │
│                       │  structured output          │
└─────────────────────────────────────────────────────┘
```

**Chain-of-Thought** beroperasi di level reasoning — ia memaksa model untuk "berpikir keras" sebelum menjawab, mengeksternalisasi proses inferensi yang normalnya terjadi secara implisit dalam lapisan attention.

**ReAct** beroperasi di level orchestration — ia menciptakan loop Thought → Action → Observation yang memungkinkan LLM bertindak sebagai agen yang dapat berinteraksi dengan dunia luar secara iteratif.

**Structured JSON Schema** beroperasi di level output contract — ia mendefinisikan "bahasa" yang harus digunakan LLM untuk berkomunikasi dengan sistem downstream, menjamin interoperabilitas.

### Hubungan Matematis: Bagaimana Prompt Mempengaruhi Distribusi

Secara formal, LLM menghasilkan distribusi:

```
P(output | prompt, θ)
```

Di mana `θ` adalah parameter model (fixed setelah training). Satu-satunya variabel yang dapat kita kontrol adalah `prompt`. Chain-of-Thought bekerja dengan memanfaatkan fakta bahwa:

```
P(answer | question) << P(answer | question, reasoning_steps)
```

Dengan kata lain: probabilitas jawaban yang benar secara dramatis meningkat ketika model dikondisikan pada intermediate reasoning steps. Ini bukan magic — ini adalah konsekuensi dari bagaimana model ditraining pada teks manusia di mana jawaban yang baik selalu didahului oleh reasoning yang baik.

---

## 4. Why?

### Masalah yang Dipecahkan oleh Setiap Teknik

#### Masalah 1: "Black Box Reasoning" → Solusi: Chain-of-Thought

Tanpa CoT, LLM menghasilkan jawaban langsung. Ini bermasalah karena:

- **Tidak dapat diaudit**: Anda tidak tahu mengapa model menjawab demikian
- **Error rate tinggi pada tugas kompleks**: Model sering "short-circuit" ke jawaban salah
- **Tidak dapat diperbaiki**: Jika jawaban salah, Anda tidak tahu di mana reasoning-nya gagal

```python
# TANPA CoT — Black box, error rate tinggi
prompt = "Berapa 17% dari 340 ditambah 23% dari 150?"
# Output: "92.3" (mungkin salah, tidak ada cara verifikasi)

# DENGAN CoT — Transparent reasoning
prompt = """
Berapa 17% dari 340 ditambah 23% dari 150?
Mari kita hitung langkah demi langkah:
"""
# Output:
# Langkah 1: 17% dari 340 = 0.17 × 340 = 57.8
# Langkah 2: 23% dari 150 = 0.23 × 150 = 34.5
# Langkah 3: 57.8 + 34.5 = 92.3
# Jawaban: 92.3
```

#### Masalah 2: "LLM Terisolasi dari Dunia" → Solusi: ReAct

LLM memiliki knowledge cutoff dan tidak dapat:
- Mengambil data real-time (harga saham, cuaca, status order)
- Melakukan kalkulasi kompleks dengan presisi tinggi
- Berinteraksi dengan database atau API
- Mengeksekusi kode

ReAct memecahkan ini dengan memberi LLM kemampuan untuk **memanggil tools** dan **mengobservasi hasilnya** sebelum memberikan jawaban final.

#### Masalah 3: "Output Tidak Dapat Diprediksi" → Solusi: Structured JSON Schema

Output LLM adalah teks bebas. Untuk integrasi sistem, ini berarti:
- Parsing yang rapuh (regex yang mudah rusak)
- Tidak ada jaminan field yang diperlukan ada
- Type mismatch yang menyebabkan runtime error
- Tidak ada validasi semantik

JSON Schema enforcement mengubah LLM dari "chatbot" menjadi **API yang dapat diandalkan**.

---

## 5. What?

### 5.1 Chain-of-Thought (CoT) — Definisi Presisi

**Chain-of-Thought Prompting** adalah teknik di mana prompt secara eksplisit menginstruksikan atau mendemonstrasikan bahwa model harus menghasilkan serangkaian intermediate reasoning steps sebelum menghasilkan jawaban final.

**Taksonomi CoT:**

| Varian | Mekanisme | Kapan Digunakan |
|---|---|---|
| **Zero-shot CoT** | Append "Let's think step by step" | Tugas umum, tidak ada contoh |
| **Few-shot CoT** | Berikan 2-5 contoh (Q + reasoning + A) | Tugas domain-spesifik |
| **Self-consistency CoT** | Generate N reasoning paths, majority vote | Tugas kritis, akurasi > latensi |
| **Tree-of-Thought (ToT)** | Explore multiple branches, backtrack | Problem solving kompleks |
| **Program-of-Thought (PoT)** | Generate kode Python, eksekusi | Kalkulasi numerik presisi tinggi |

### 5.2 ReAct — Definisi Presisi

**ReAct (Reasoning + Acting)** adalah pola prompting yang menggabungkan reasoning traces (seperti CoT) dengan action execution dalam loop iteratif. Diperkenalkan dalam paper "ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., 2022).

**Siklus ReAct:**
```
Thought → Action → Observation → Thought → Action → ... → Final Answer
```

**Komponen formal:**
- **Thought**: Reasoning internal LLM tentang state saat ini dan apa yang harus dilakukan
- **Action**: Pemanggilan tool dengan parameter spesifik (format: `tool_name[parameter]`)
- **Observation**: Output dari tool yang dieksekusi oleh orchestrator
- **Final Answer**: Jawaban akhir setelah semua informasi terkumpul

### 5.3 Structured JSON Schema Output — Definisi Presisi

**Structured Output** adalah kemampuan LLM (atau lapisan enforcement di atasnya) untuk menjamin bahwa output selalu conform terhadap JSON Schema yang telah didefinisikan. Ini dapat diimplementasikan melalui:

1. **Prompt-only enforcement**: Instruksi dalam prompt + post-processing validation
2. **Grammar-constrained decoding**: Memodifikasi logits selama generation (Outlines, LMQL)
3. **API-level enforcement**: OpenAI `response_format`, Anthropic tool use
4. **Function calling**: Mendefinisikan schema sebagai "function" yang harus dipanggil model

**JSON Schema Constraints yang Relevan untuk LLM:**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "field": {
      "type": "string",
      "enum": ["value1", "value2"],     // Membatasi nilai valid
      "pattern": "^[A-Z]{3}-\\d{4}$",  // Regex constraint
      "minLength": 1,                    // Mencegah empty string
      "maxLength": 500                   // Mencegah output terlalu panjang
    },
    "score": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,                      // Normalisasi range
      "multipleOf": 0.01                 // Presisi desimal
    }
  },
  "required": ["field", "score"],        // Field wajib
  "additionalProperties": false          // KRITIS: tolak field tak terdefinisi
}
```

---

## 6. How?

### 6.1 Mekanisme Internal Chain-of-Thought

**Mengapa CoT bekerja secara mekanistik:**

Ketika model menghasilkan token reasoning step, token-token tersebut masuk ke dalam context window dan menjadi bagian dari input untuk prediksi token berikutnya. Ini menciptakan **kondisioning bertahap** — setiap langkah reasoning mempersempit ruang hipotesis yang perlu dipertimbangkan model.

```
INPUT CONTEXT GROWS DURING GENERATION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 0: [prompt]
        P(next_token | prompt)

Step 1: [prompt][Langkah 1: ...]
        P(next_token | prompt + step1)
        ← distribusi sudah lebih sempit

Step 2: [prompt][Langkah 1: ...][Langkah 2: ...]
        P(next_token | prompt + step1 + step2)
        ← distribusi semakin sempit, jawaban lebih akurat

Step N: [prompt][step1]...[stepN]
        P(answer | prompt + all_steps)
        ← distribusi sangat terfokus pada jawaban benar
```

**Proses step-by-step implementasi CoT:**

1. **Desain reasoning template**: Tentukan format langkah-langkah yang diinginkan
2. **Buat few-shot exemplars**: 2-5 contoh Q + reasoning chain + A yang berkualitas tinggi
3. **Definisikan stop condition**: Kapan reasoning selesai dan jawaban dimulai
4. **Parse output**: Ekstrak jawaban final dari reasoning trace

### 6.2 Mekanisme Internal ReAct

**Loop ReAct secara detail:**

```
ITERATION 1:
┌─────────────────────────────────────────────────┐
│ PROMPT:                                         │
│ [System: Anda adalah agen dengan tools...]      │
│ [User: Pertanyaan]                              │
│                                                 │
│ LLM GENERATES:                                  │
│ Thought: Saya perlu mencari X terlebih dahulu  │
│ Action: search["query X"]                       │
└─────────────────────────────────────────────────┘
          │
          ▼ Orchestrator mendeteksi Action
          │ Memanggil tool search("query X")
          │ Mendapat hasil: "Hasil pencarian..."
          ▼
ITERATION 2:
┌─────────────────────────────────────────────────┐
│ PROMPT (diperpanjang):                          │
│ [System]                                        │
│ [User: Pertanyaan]                              │
│ Thought: Saya perlu mencari X                  │
│ Action: search["query X"]                       │
│ Observation: Hasil pencarian...   ← DITAMBAH   │
│                                                 │
│ LLM GENERATES:                                  │
│ Thought: Dari hasil ini, saya perlu Y           │
│ Action: calculate["formula Y"]                  │
└─────────────────────────────────────────────────┘
          │
          ▼ [loop berlanjut...]
          │
FINAL ITERATION:
┌─────────────────────────────────────────────────┐
│ LLM GENERATES:                                  │
│ Thought: Saya sudah punya semua informasi       │
│ Final Answer: [jawaban lengkap]                 │
└─────────────────────────────────────────────────┘
```

### 6.3 Mekanisme Structured Output Enforcement

**Dua pendekatan utama:**

**Pendekatan 1: API-level (OpenAI Structured Outputs)**
```
1. Developer mendefinisikan JSON Schema
2. Schema dikirim ke API sebagai parameter
3. Model menggunakan const
