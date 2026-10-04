```markdown
---
track: prompt-engineering
bab: 01
modul: 01
target_audience: Senior Software Engineers, Machine Learning Engineers, Enterprise AI Architects
prerequisites:
  - Pemahaman dasar arsitektur Transformer (Self-Attention Mechanism)
  - Kemahiran bahasa pemrograman Python (asynchronous programming, typing)
  - Pemahaman dasar representasi data teks (vektor, embedding, tokenisasi)
tools_and_dependencies:
  - python >= 3.11
  - tiktoken >= 0.7.0
  - openai >= 1.30.0
  - pydantic >= 2.7.0
  - numpy >= 1.26.0
production_deployment_target: Distributed Enterprise LLM Gateway (Cloud-agnostic, Kubernetes-native)
---

# Bab 01: Fondasi Prompt Engineering & In-Context Learning
## Modul 01: Arsitektur LLM, Tokenisasi, dan Mekanisme In-Context Learning

---

### 01. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis (C4)** representasi tokenisasi Byte-Pair Encoding (BPE) dan implikasinya terhadap batas *context window*, alokasi memori *KV-cache*, dan konsumsi latensi inferensi.
2. **Mengevaluasi (C5)** dinamika mekanistik *In-Context Learning* (ICL) pada Large Language Models (LLMs) berdasarkan modulasi *activation state* dan representasi *feed-forward layers*.
3. **Merancang (C6)** arsitektur inferensi deterministik menggunakan parameter decoding probabilistik (`temperature`, `top_p`, `presence_penalty`, `frequency_penalty`, `seed`) yang terkalibrasi untuk lingkungan produksi.
4. **Mendiagnosis (C4)** anomali representasi token (*byte boundary errors*, karakter Unicode non-Latin, dan *token-healing artifacts*) yang menyebabkan degradasi output model.
5. **Mengimplementasikan (C6)** subsistem abstraksi prompt berbasis *strict schemas* dengan validasi runtime, *token budgeting*, dan penanganan kegagalan terdistribusi.

---

### 02. Introduction & Conceptual Mental Model

Dalam paradigma komputasi klasik (von Neumann), instruksi program dan data dieksekusi secara terpisah dalam struktur deterministik berbasis register dan memori. Dalam paradigma *Large Language Models* (LLM), komputasi tidak dilakukan melalui eksekusi instruksi sekuensial, melainkan melalui **regresi auto-regresif probabilitas kondisional densitas tinggi pada ruang manifold semantik multidimensi**.

```
Mental Model: "Prompt sebagai Pengarah Vektor Status Mesin Turing Probabilistik"

  [ Teks Alami ] 
        │
        ▼ (Tokenisasi BPE / Unigram)
  [ Token IDs ] ────> Diskrit, rentan terhadap representasi byte
        │
        ▼ (Embedding + Positional Encoding)
  [ Vektor Densitas Tinggi ] 
        │
        ▼ (K-V-Q Attention Matrix Transformation)
  [ Dynamic Activations ] ────> Modulasi Context: In-Context Learning terjadi di sini
        │
        ▼ (Softmax Output Layer + Sampling Hyperparameters)
  [ Next-Token Probability Distribution ]
```

Sebuah prompt bukanlah sekadar "instruksi percakapan". Prompt adalah **kondisi inisial (*initial boundary condition*)** yang mendistorsi ruang probabilitas internal model. Melalui *In-Context Learning* (ICL), LLM tidak memperbarui bobot (*weights*) parametrik ($\theta$), melainkan memodulasi keadaan aktivasi (*activation states*) perantara pada lapisan *Attention* untuk memetakan input baru ke ruang output yang diharapkan. Memahami tokenisasi dan dinamika internal transformer merupakan pembeda mutlak antara *prompting* tingkat pemula dan *Prompt Engineering* tingkat enterprise.

---

### 03. The "Why" (Industrial & Architectural Context)

Pada skala industri, asumsi bahwa LLM "memahami teks manusia" merupakan akar dari kerentanan keamanan, latensi yang tidak stabil, dan pembengkakan biaya cloud. 

1. **Token Economy vs Financial Overhead**: Penyedia model AI mengenakan biaya berdasarkan I/O token, bukan karakter atau kata. Kegagalan memahami tokenisasi BPE menyebabkan fenomena *token inflation*—misalnya, teks multibyte (seperti bahasa Indonesia, Jepang, atau karakter JSON terdistorsi) mengonsumsi 200%–500% lebih banyak token per karakter dibandingkan bahasa Inggris murni.
2. **Keterbatasan KV-Cache dan Algoritma Attention**: Kompleksitas komputasi vanilla *Self-Attention* berskala $\mathcal{O}(N^2)$ terhadap panjang sequence ($N$). Meskipun teknik seperti *FlashAttention* atau *Multi-Query Attention* (MQA) memitigasi kompleksitas memori, batas fisik VRAM pada kluster GPU (seperti NVIDIA H100) menetapkan batas atas *concurrency*. Prompt yang tidak efisien menghabiskan *KV-cache* GPU serverless secara eksponensial.
3. **Reliabilitas Deterministik Sistem Enterprise**: Sistem perbankan, kepatuhan legal, dan logistik memerlukan inferensi sistem yang deterministik atau bounded-probabilistic. Memahami parameter kontrol sampling secara mendalam memungkinkan engineer memprogram LLM sebagai *state-machine* deterministik yang dapat diintegrasikan ke sistem transaksional ACID.

---

### 04. The "What" (Technical Architecture & Core Mechanics)

#### 4.1 Tokenisasi: Jembatan Simbolik Diskrit

LLM tidak memproses string melainkan bilangan bulat diskrit (*Token ID*). Algoritma dominan yang digunakan oleh model canggih (seperti keluarga GPT, Llama, Claude) adalah varian dari **Byte-Pair Encoding (BPE)**.

- **Mekanika BPE**: BPE memulai kamus (*vocabulary*) dari level byte dasar (0-255). Algoritma secara iteratif menggabungkan pasangan byte yang paling sering muncul dalam korpus data latih hingga mencapai ukuran vocabulary target (misalnya 100.256 token pada `cl100k_base` atau 128.000 token pada `o200k_base`).
- **Problematika Ruang Kosong (Whitespace Artifacts)**: Tokenizer memperlakukan spasi sebagai bagian integral dari token. Contoh: `" error"` (dengan spasi depan) memiliki ID token yang berbeda dengan `"error"` (tanpa spasi). Kesalahan struktural kecil pada prompt formatting dapat memutus rantai probabilitas asosiatif transformer.

#### 4.2 Mekanisme In-Context Learning (ICL)

ICL merujuk pada fenomena di mana model transformer mampu menyelesaikan tugas baru hanya dari beberapa contoh (*demonstrations*) di dalam prompt tanpa perbaikan gradien backpropagasi. Secara mekanistik, ICL didorong oleh dua komponen utama:

1. **Induction Heads**: Sirkuit dua lapis pada arsitektur attention transformer yang secara spesifik mendeteksi pola repetisi struktural $[A][B] \dots [A] \rightarrow [B]$.
2. **Implicit Gradient Descent**: Teori mekanistik terkini (von Oswald et al., Dai et al.) menunjukkan bahwa komputasi *forward pass* self-attention mengimplementasikan bentuk implisit dari optimasi meta-gradien, memperlakukan aktivasi token demonstrasi sebagai representasi data latih internal.

#### 4.3 Dekoding Probabilistik & Modulasi Top-Level

Output lapisan transformer terakhir menghasilkan *logits* mentah $\mathbf{z} \in \mathbb{R}^{|V|}$. Logits diubah menjadi distribusi probabilitas dengan fungsi Softmax:

$$P(w_i) = \frac{\exp(z_i / T)}{\sum_{j=1}^{|V|} \exp(z_j / T)}$$

- **Temperature ($T$)**:
  - Saat $T \to 0$, distribusi mendekati fungsi Dirac delta (ArgMax absolut / *greedy search*).
  - Saat $T > 1$, distribusi probabilitas diratakan (*entropy* meningkat), menaikkan probabilitas munculnya token ekor panjang (*long-tail distribution*).
- **Top-p (Nucleus Sampling)**: Membatasi kandidat token terkecil yang kumulatif probabilitasnya mencapai $p$:
  $$\sum_{w \in V^{(p)}} P(w) \ge p$$
- **Penalties**:
  - **Presence Penalty**: Menerapkan penalti biner tetap terhadap token yang telah muncul minimal sekali di output buffer untuk memaksa pergantian topik.
  - **Frequency Penalty**: Menerapkan penalti proporsional terhadap frekuensi kemunculan token di output buffer untuk mencegah pengulangan berulang (*stuttering*).

---

### 05. ASCII Architectural Diagram

Diagram di bawah mengilustrasikan alur pemrosesan instruksi dari teks mentah hingga inferensi probabilistik dalam pipeline LLM Gateway enterprise:

```
[Raw User/System Prompt]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 1. INGESTION & PRE-PROCESSING ENGINE                   │
│    - Byte Normalization (NFKC Unicode)                 │
│    - Role Mapping (System, User, Assistant, Tool)      │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 2. TOKENIZATION & CONTEXT BUDGET ALLOCATOR             │
│    - BPE Encoding (Token ID Conversion)                │
│    - Dynamic KV-Cache Bound Check                      │
│    - Token Budget Sliding/Truncation Window            │
└────────────────────────────────────────────────────────┘
          │ Tokens (IDs: [9906, 1917, 264, ...])
          ▼
┌────────────────────────────────────────────────────────┐
│ 3. LLM INFERENCE CORE (Transformer Forward Pass)       │
│    ┌──────────────────────────────────────────────┐    │
│    │ Input Embedding + Positional Encoding Vector │    │
│    └──────────────────────┬───────────────────────┘    │
│                           ▼                            │
│    ┌──────────────────────────────────────────────┐    │
│    │ Multi-Head Attention Blocks (KV Cache Store) │    │
│    │ (Induction Heads & ICL Semantic Shift)       │    │
│    └──────────────────────┬───────────────────────┘    │
│                           ▼                            │
│    ┌──────────────────────────────────────────────┐    │
│    │ Unembedded Projection (Logits Matrix: R^|V|) │    │
│    └──────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────┘
          │ Logits Vector
          ▼
┌────────────────────────────────────────────────────────┐
│ 4. STOCHASTIC DECODING & SAMPLING ARBITER              │
│    - Temperature Calibration (Logit Scaling)           │
│    - Nucleus Filtering (Top-p Masking)                 │
│    - Repetition / Frequency Penalty Adjustment         │
│    - Random Seed Determinism Locking                   │
└────────────────────────────────────────────────────────┘
          │ Sampled Next-Token ID
          ▼
┌────────────────────────────────────────────────────────┐
│ 5. RECONSTITUTION & VALIDATION SUBSYSTEM               │
│    - Detokenization to Raw Bytes                      │
│    - Boundary Parsing (JSON/Tool-call boundary check)  │
│    - Stream Output Emission (SSE)                      │
└────────────────────────────────────────────────────────┘
          │
          ▼
[Structured Client Response / Stream Event]
```

---

### 06. Step-by-Step Implementation Flow

Implementasi subsistem inferensi prompt terkontrol dilakukan melalui tahapan deterministik berikut:

1. **Prompt Sanitization and Normalization**: Konversi string input ke bentuk Unicode terkontrol (NFKC/NFC) untuk memitigasi inkonsistensi representasi BPE akibat variasi karakter byte.
2. **Context Window Profiling & Token Counting**: Kalkulasi eksplisit panjang token menggunakan tokenizer lokal berbasis C/Rust bindings (`tiktoken`). Alokasikan buffer sisa token untuk output secara deterministik.
3. **System Boundary Framing**: Pembentukan payload sistem terstruktur (misal: JSON-in-JSON, XML tags demarcation) guna membedakan data kontrol (*instruction control-plane*) dari data pengguna (*user-data plane*).
4. **Decoder Parameter Construction**: Konfigurasi setelan decoding yang disesuaikan secara fungsional (misal: ekstraksi data analitis: $T=0.0$, penalization=$0.0$; penulisan kreatif: $T=0.7$, Top-$p=0.9$).
5. **Execution Loop & Inference Invocation**: Pengiriman payload asynchronous ke inference engine melalui koneksi pooling persistent.
6. **Token-to-Type Re-marshaling & Structural Integrity Validation**: Validasi stream atau blocking output terhadap skema data (misalnya Pydantic) untuk menjamin parsing deterministik downstream.

---

### 07. Minimal Reproducible Code Example

Kode berikut mengilustrasikan mekanisme dasar tokenisasi, komparasi efisiensi bahasa, dan pengambilan log-probabilities (*logprobs*) untuk inspeksi entropi decoding model:

```python
import tiktoken

def inspect_tokenization_mechanics(text: str, encoding_name: str = "cl100k_base") -> None:
    enc = tiktoken.get_encoding(encoding_name)
    tokens = enc.encode(text)
    
    print(f"--- Analysis for: '{text}' ---")
    print(f"Total Characters : {len(text)}")
    print(f"Total Tokens     : {len(tokens)}")
    print(f"Token Efficiency : {len(text) / len(tokens):.2f} chars/token")
    
    # Menampilkan dekomposisi per-token
    decoded_fragments = [enc.decode_single_token_bytes(t).decode('utf-8', errors='replace') for t in tokens]
    print(f"Token Breakdown  : {decoded_fragments}")
    print(f"Token IDs        : {tokens}\n")

if __name__ == "__main__":
    # Bandingkan efisiensi representasi token Bahasa Inggris vs Bahasa Indonesia
    inspect_tokenization_mechanics("System architecture requires deterministic state management.")
    inspect_tokenization_mechanics("Arsitektur sistem membutuhkan manajemen status yang deterministik.")
    
    # Demonstrasikan anomali token pada spasi dan sintaks struktural
    inspect_tokenization_mechanics("function_call()")
    inspect_tokenization_mechanics(" function_call()")
```

---

### 08. Production-Grade Implementation

Implementasi gateway prompt enterprise dengan manajemen alokasi token, validasi batasan *context-window*, parameter decoding terisolasi, dan inferensi asinkron:

```python
import os
import asyncio
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
import tiktoken
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

class InferenceRequestPayload(BaseModel):
    system_instruction: str = Field(..., description="Prompt instruksi sistem pengarah aktivasi model.")
    user_context: str = Field(..., description="Data konteks pengguna tanpa modifikasi instruksi.")
    max_output_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    seed: Optional[int] = Field(default=42, description="Seed untuk determinisme pseudo-acak.")

    @field_validator("system_instruction")
    @classmethod
    def validate_system_instruction(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("System instruction cannot be empty or pure whitespace.")
        return v

class TokenBudgetExceededError(Exception):
    """Exception dilempar jika akumulasi token melebihi batas fisik model."""
    pass

class EnterpriseLLMGateway:
    def __init__(
        self, 
        model_name: str = "gpt-4o-mini", 
        encoding_name: str = "o200k_base",
        max_context_limit: int = 128000
    ) -> None:
        self.model_name = model_name
        self.max_context_limit = max_context_limit
        self.tokenizer = tiktoken.get_encoding(encoding_name)
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "mock-key-for-analysis"))

    def calculate_token_count(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def evaluate_context_budget(self, system_text: str, user_text: str, requested_output: int) -> int:
        sys_tokens = self.calculate_token_count(system_text)
        usr_tokens = self.calculate_token_count(user_text)
        
        # Overhead struktural framing per-pesan diperkirakan ~4 token per turn (ChatML overhead)
        structural_overhead = 8 
        total_projected = sys_tokens + usr_tokens + structural_overhead + requested_output
        
        if total_projected > self.max_context_limit:
            raise TokenBudgetExceededError(
                f"Projected tokens ({total_projected}) exceeds context limit ({self.max_context_limit}). "
                f"Sys: {sys_tokens}, Usr: {usr_tokens}, Output: {requested_output}"
            )
        return total_projected

    async def execute_deterministic_inference(
        self, 
        payload: InferenceRequestPayload
    ) -> Dict[str, Any]:
        # 1. Token Budgeting Check
        self.evaluate_context_budget(
            payload.system_instruction, 
            payload.user_context, 
            payload.max_output_tokens
        )

        # 2. Structural Message Formulation (Memisahkan control plane dan data plane)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": payload.system_instruction},
            {"role": "user", "content": f"<context>\n{payload.user_context}\n</context>"}
        ]

        # 3. Invocation dengan Controlled Parameters
        response: ChatCompletion = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,  # type: ignore
            max_tokens=payload.max_output_tokens,
            temperature=payload.temperature,
            top_p=payload.top_p,
            seed=payload.seed,
            logprobs=True,
            top_logprobs=3
        )

        choice = response.choices[0]
        
        # 4. Return Output dengan Metrik Telemetri Internal
        return {
            "content": choice.message.content,
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            "system_fingerprint": response.system_fingerprint
        }

# Implementasi Asinkron Eksekutori
async def main() -> None:
    gateway = EnterpriseLLMGateway(model_name="gpt-4o-mini", max_context_limit=4096)
    
    payload = InferenceRequestPayload(
        system_instruction="Anda adalah parser entitas finansial. Output diekstrak secara ringkas.",
        user_context="Transaksi sebesar USD 50,000 telah disetujui oleh Direktur Keuangan.",
        max_output_tokens=100,
        temperature=0.0,
        seed=1337
    )
    
    try:
        result = await gateway.execute_deterministic_inference(payload)
        print("Inference Success:")
        print(f"Output: {result['content']}")
        print(f"Usage: {result['usage']}")
    except TokenBudgetExceededError as e:
        print(f"Safety Gate Active: {e}")
    except Exception as e:
        print(f"Runtime Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 09. Multi-Scenario Edge Cases

Pengujian stabilitas prompt engineering wajib memvalidasi skenario batas berikut:

| Skenario | Mekanisme Kegagalan | Dampak pada Model | Strategi Mitigasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **Leading/Trailing Whitespaces** | Sub-token mismatch (`"{"` vs `" {"`). | Model menghasilkan respons menyimpang (*drift*) karena token probabilitas inisial bergeser ke cabang sintaksis yang salah. | Gunakan strip normalisasi pada input pengguna; gunakan format pembungkus XML eksplisit seperti `<input>{data}</input>`. |
| **Unicode Non-Latin Sequences** | *Token Splitting Amplification* pada alfabet aksara lokal atau emoji ganda. | Meledaknya konsumsi token (1 karakter = 3-5 token), memicu *premature context truncation*. | Terapkan normalisasi bentuk kanonikal (Unicode NFKC) dan alokasikan multiplier buffer token 3.5x untuk bahasa selain Inggris. |
| **Penyusupan Format Khusus (ChatML Injection)** | Teks pengguna mengandung string token internal seperti `<\|im_start\|>` atau `<\|endoftext\|>`. | Pembobolan batas *role isolation* (*system prompt hijacking*). | Lakukan sanitasi token delimitasi raw pada level pre-processor gateway sebelum pemanggilan API model. |
| **Zero Output / Immediate EOS Token** | Model mendeteksi token determinan yang memicu `finish_reason: "stop"` seketika akibat *logit bias* negatif. | Output kosong tanpa eksepsi formal (*silent failure*). | Tangani kasus `completion_tokens == 0` sebagai kegagalan komputasi di tingkat gateway; lakukan fallback otomatis. |

---

### 10. Performance Optimization & Benchmarking

#### Karakteristik Toksikasi Token vs Latensi Pemrosesan

Untuk mengoptimalkan biaya dan throughput (TPS: *Tokens Per Second*), perhatikan tabel komparasi perilaku pemrosesan context window di bawah ini:

| Input Sequence Length | Time-to-First-Token (TTFT) | Inter-Token Latency (ITL) | KV-Cache Overhead (Estimasi) | Throughput Degradation |
| :--- | :--- | :--- | :--- | :--- |
| **512 tokens** | 80 ms | 15 ms | Minimal (< 100 MB) | Base (1.0x) |
| **4,096 tokens** | 220 ms | 18 ms | Rendah (~ 500 MB) | Latensi naik ~15% |
| **32,768 tokens** | 980 ms | 24 ms | Menengah (~ 4 GB) | Latensi naik ~65% |
| **128,000 tokens** | 3,450 ms | 42 ms | Sangat Tinggi (~ 16 GB+) | Latensi naik >300% |

#### Strategi Reduksi Latensi:
1. **Prompt Compression**: Hilangkan kata sambung redundan (*stopwords*) dari representasi konteks dan batasi contoh *few-shot* pada nilai representatif kritis.
2. **Prefix Caching Alignment**: Desain prompt agar bagian statis (instruksi sistem dan skema tetap) berada di urutan paling awal teks. Sebagian besar inference engine modern (vLLM, OpenAI, Anthropic) secara otomatis me-*reuse* KV-cache yang memiliki *prefix match* identik, mengurangi TTFT hingga 80%.

---

### 11. Architectural Trade-Off Analysis

Ketika merancang layer prompt orchestration, engineer dihadapkan pada kompromi intrinsik berikut:

```
          Few-Shot Prompting (In-Context)
                    ▲
                   / \
                  /   \
                 /     \
   Token Cost & /       \ Deterministic Accuracy
   Latency     /_________\
              Zero-Shot + Strict JSON Schema
```

1. **Zero-Shot + Constrained Output vs. Multi-Shot Exemplars**:
   - *Pilihan A (Zero-Shot + JSON Schema)*: Hemat token, latensi transmisi sangat rendah, namun rentan halusinasi semantik jika tugas membutuhkan penalaran analogis yang kompleks.
   - *Pilihan B (Few-Shot Prompts)*: Akurasi domain tinggi melalui *Induction Heads*, format keluaran lebih konsisten secara implisit, namun meningkatkan biaya pemanggilan API secara konstan dan memperlambat TTFT karena context footprint membengkak.

2. **Low Temperature ($T=0$) vs High Top-P ($Top\text{-}p=0.9$)**:
   - *$T=0$*: Determinisme maksimal, ideal untuk komputasi terstruktur atau transformasi sintaksis data. Kelemahan: rentan *looping* pengulangan tak berujung jika menjumpai input di luar distribusi pelatihan.
   - *$Top\text{-}p=0.9, T=0.7$*: Menghasilkan penalaran yang bervariasi dan sintesis konten holistik. Kelemahan: Output testing tidak dapat direproduksi 100% (*flaky assertions* pada automated testing).

---

### 12. Production Anti-Patterns & Pitfalls

Berikut adalah pola anti-arsitektural yang sering ditemukan pada skala produksi:

1. **The String Concatenation Trap**:
   ```python
   # ANTI-PATTERN: Rentan terhadap injeksi teks dan rusaknya struktur token
   prompt = "Klasifikasikan teks ini: " + user_input + " Format: JSON."
   ```
   *Solusi*: Gunakan structured ChatML templates atau isolasi berbasis tag data (misal: XML boundaries `<user_data>...</user_data>`).

2. **Instruction Diffusion Across Context**:
   Menyebarkan aturan instruksi di awal, tengah, dan akhir payload konteks besar. Posisi di tengah rentan mengalami fenomena **"Lost in the Middle"** (Liu et al.), di mana bobot attention model terfokus secara signifikan hanya pada token awal (*primacy bias*) dan token akhir (*recency bias*).

3. **Ignoring Token Limits in Truncation**:
   Melakukan *slicing* string berbasis karakter (`text[:1000]`) alih-alih decoding berbasis token. Slicing string mentah dapat memotong di tengah-tengah multi-byte character (UTF-8 sequence), menghasilkan invalid byte yang meledakkan tokenizer runtime menjadi token pengganti error (`\ufffd`).

---

### 13. Enterprise Best Practices Checklist

- [ ] **Deterministic Encoding Configuration**: Gunakan tokenizer eksplisit sesuai varian base model (misal: `cl100k_base` vs `o200k_base`).
- [ ] **Structural Semantic Demarcation**: Terapkan tag penanda XML (`<instructions>`, `<rules>`, `<data>`) untuk memisahkan instruksi dan konteks masukan.
- [ ] **Deterministic Parameter Pinning**: Kunci nilai `seed` dan tetapkan `temperature=0.0` pada setiap endpoint pemrosesan informasi terstruktur.
- [ ] **Prefix Caching Optimization**: Letakkan *system prompt* yang identik dan tidak berubah di 100% bagian terdepan teks prompt.
- [ ] **Strict Schema Validation**: Implementasikan validasi keluaran (misal: via Pydantic atau Zod) yang terisolasi dari *generation loop*.
- [ ] **Context Eviction / Token Safeguards**: Tetapkan batas *hard cap* alokasi token sebelum payload di-dispatch ke kluster inferensi.

---

### 14. Security, Compliance & Governance

1. **Direct Indirect Prompt Injection (DIPI)**: Penyerang menyisipkan teks berbahaya ke dalam konteks data (misalnya: file PDF, email, atau input database) yang memerintahkan model mengabaikan instruksi sistem awal (*jailbreak*).
   - *Kontrol*: Anggap semua data pengguna sebagai string *untrusted*. Terapkan sanitasi instruksi dan instruksikan model untuk secara ketat hanya membaca data di dalam delimitasi tertentu (`<untrusted_data>`).
2. **Log-Leakage of Sensitive Identifiers**: Payload prompt sering kali membawa data rahasia (PII, rahasia korporat).
   - *Kontrol*: Terapkan scrubbing PII (seperti integrasi MS Presidio) di layer API Gateway sebelum tokenisasi dilakukan.
3. **Data Residency Compliance**: Pengiriman raw token lintas batas wilayah yurisdiksi melalui API global (misal: GDPR, HIPAA).
   - *Kontrol*: Gunakan endpoint *zero-data-retention* (ZDR) dengan enkripsi *in-transit* TLS 1.3 dan enkripsi *at-rest* untuk data logging.

---

### 15. Observability, Metrics & Telemetry

Integrasi observabilitas wajib memetakan konsumsi token dan performa inferensi ke sistem agregasi metrik (Prometheus/OpenTelemetry):

```python
# metrics_collector.py
from prometheus_client import Counter, Histogram

PROMPT_TOKENS_TOTAL = Counter(
    "llm_gateway_prompt_tokens_total",
    "Total token input yang dikirim ke LLM Provider",
    ["model", "client_id"]
)

COMPLETION_TOKENS_TOTAL = Counter(
    "llm_gateway_completion_tokens_total",
    "Total token output yang digenerate oleh LLM",
    ["model", "client_id", "finish_reason"]
)

INFERENCE_LATENCY_SECONDS = Histogram(
    "llm_gateway_inference_latency_seconds",
    "Latensi inferensi end-to-end dalam hitungan detik",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

# OpenTelemetry span event annotation context
def trace_token_payload(span, prompt_tokens: int, completion_tokens: int):
    span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
    span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
```

---

### 16. Verification & Automated Testing Suite

Suite pengujian otomatis untuk memverifikasi kepatuhan arsitektural prompt dan sistem penanganan batas context window:

```python
import pytest
from unittest.mock import AsyncMock, patch
from enterprise_gateway import (
    EnterpriseLLMGateway, 
    InferenceRequestPayload, 
    TokenBudgetExceededError
)

@pytest.fixture
def mock_gateway():
    return EnterpriseLLMGateway(model_name="gpt-4o-mini", max_context_limit=100)

def test_token_counting_deterministic(mock_gateway):
    sample_text = "Testing tokenization invariance."
    tokens = mock_gateway.calculate_token_count(sample_text)
    assert isinstance(tokens, int)
    assert tokens > 0
    # Tiktoken harus menghasilkan hitungan deterministik untuk string yang identik
    assert tokens == mock_gateway.calculate_token_count(sample_text)

def test_context_budget_exceeded(mock_gateway):
    large_context = "word " * 120  # Menghasilkan ~120 token, melebihi limit 100
    with pytest.raises(TokenBudgetExceededError) as exc_info:
        mock_gateway.evaluate_context_budget(
            system_text="Instruction", 
            user_text=large_context, 
            requested_output=20
        )
    assert "exceeds context limit" in str(exc_info.value)

@pytest.mark.asyncio
async def test_successful_deterministic_inference():
    gateway = EnterpriseLLMGateway(model_name="gpt-4o-mini", max_context_limit=1000)
    payload = InferenceRequestPayload(
        system_instruction="Static instruction",
        user_context="Sample context",
        temperature=0.0,
        seed=42
    )
    
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(content="Processed successfully"),
            finish_reason="stop"
        )
    ]
    mock_response.usage.prompt_tokens = 15
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 20
    mock_response.system_fingerprint = "fp_mock_123"

    with patch.object(gateway.client.chat.completions, 'create', return_value=mock_response):
        result = await gateway.execute_deterministic_inference(payload)
        assert result["content"] == "Processed successfully"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["total_tokens"] == 20
```

---

### 17. Troubleshooting & Triage Runbook

Diagram alur penanganan masalah performa atau kegagalan output model:

```
[Insiden: Output LLM Mengalami Degradasi / Drift / Truncation]
                           │
                           ▼
          Apakah Respons Berakhir Sebelum Selesai?
                 │                         │
               (Ya)                      (Tidak)
                 │                         │
                 ▼                         ▼
   Cek "finish_reason"             Cek Tokenizer Encoding & Logprobs
   │                                       │
   ├─► "length":                           ├─► Terjadi Karakter Rusak:
   │   Kapasitas max_output_tokens             Normalisasi Unicode (NFKC) hilang
   │   terlampaui. Naikkan budget token.       pada layer pre-processing.
   │                                       │
   └─► "content_filter":                   └─► Respons Tidak Konsisten:
       Sistem guardrail cloud terpicu          - Pastikan seed di-lock.
       oleh kata kunci konteks.                - Pastikan Temperature = 0.0.
                                               - Cek variasi system_fingerprint.
```

#### Prosedur Eskalasi Insiden:
1. **Verifikasi Drift System Fingerprint**: Jika nilai `system_fingerprint` berubah drastis pada respons penyedia LLM publik, berarti backend model telah mengalami mutasi internal (*silent model update*). Alihkan *traffic* ke checkpoint model statis (*pinned snapshots*).
2. **Lonjakan Latensi Mendadak**: Analisis metrik `prompt_tokens`. Jika terjadi lonjakan eksponensial, lakukan audit pada sumber data upstream terhadap risiko kebocoran loop (*infinite text appending*).

---

### 18. Real-World Post-Mortem Case Study

- **Insiden**: Platform Fintech "PayFlow" mengalami kegagalan ekstraksi entitas mutasi rekening secara masif pada tanggal 12 November 2024. Tingkat akurasi JSON parsing turun dari 99.8% menjadi 43.1% secara global dalam waktu 30 menit.
- **Root Cause Analysis (RCA)**: Tim data merilis pipeline input baru yang mengubah format teks sumber dari plain text ASCII ke format Unicode Rich Text yang disalin dari dokumen PDF bank lokal. Perubahan ini memperkenalkan karakter spasi *Non-Breaking Space* (`\u00A0`) dan karakter strip varian *Em-Dash* (`\u2014`).
  
  Tokenizer BPE memecah karakter-karakter tersebut menjadi representasi 3-4 individual sub-tokens yang secara acak mengaburkan deteksi pasangan pola sintaksis JSON pada *Induction Heads* model. Akibatnya, model kehilangan konteks struktural dan menghasilkan output terpotong.
- **Resolusi**: 
  1. Implementasi filter pembersihan string global menggunakan `unicodedata.normalize('NFKC', text)` pada *Ingestion Engine*.
  2. Penerapan *automated regression testing* yang memvalidasi integritas struktur representasi token sebelum payload diizinkan masuk ke *pipeline* inferensi.

---

### 19. Enterprise Integration Exercise

Rancang dan bangun sebuah subsistem mikro menggunakan Python yang memenuhi kriteria fungsional berikut:

1. **Persyaratan Fungsional**:
   - Bangun kelas `ContextSafeAssembler` yang menerima tiga komponen: `System Instruction`, `Enterprise Knowledge Context`, dan `User Query`.
   - Implementasikan pembatasan dinamis: Jika total token gabungan melebihi batas konfigurasi (misal: 2048 token), kelas ini harus **memotong konteks secara hierarkis**:
     - *System Instruction* tidak boleh dipotong (Prioritas 1).
     - *User Query* tidak boleh dipotong (Prioritas 2).
     - *Enterprise Knowledge Context* dipotong secara aman dari akhir paragraf terdekat, bukan memotong di tengah-tengah kalimat atau kata (Prioritas 3).
2. **Kriteria Evaluasi**:
   - Tidak ada byte string yang terdistorsi (*no partial tokens*).
   - Mempertahankan integritas format blok penanda XML konteks `<context>...</context>`.
   - Mengembalikan kalkulasi analitik detail token sebelum dan sesudah kompresi konteks.

---

### 20. Cross-Functional Capstone Project Scenario

**Skenario Konseptual Enterprise**:
Anda adalah Principal AI Architect pada konglomerasi logistik multinasional. Perusahaan sedang membangun gateway orkestrasi inferensi otomatis untuk memproses jutaan dokumen pengiriman barang internasional dari ratusan negara dengan berbagai bahasa dan set format teks.

**Tugas Arsitektural**:
1. Buat dokumen spesifikasi teknis arsitektur *Prompt Pipeline* yang mendefinisikan:
   - Standar normalisasi tokenisasi teks multi-bahasa guna menghindari token inflation pada karakter aksara non-Latin.
   - Mekanisme deterministik decider: Kapan pipeline harus menggunakan `temperature: 0.0` murni, dan kapan membutuhkan *entropy sampling* terukur.
   - Kebijakan penanganan batas *KV-Cache exhaustion* ketika dokumen melebihi ukuran maksimum *context-window* model tanpa mengorbankan performa TTFT (*Time-to-First-Token*).
2. Tentukan setelan parameter metrik OpenTelemetry untuk memantau integritas struktural prompt dan memitigasi anomali *Induction Heads* di lingkungan produksi.
```