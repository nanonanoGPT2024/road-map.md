# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Core Prompt Anatomy & In-Context Learning**  
**Kategori: 08-AI-Data-and-Autonomous-Agents / Topic: Prompt Engineering**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Membedah Internal Attention Engine**: Memahami bagaimana mekanisme *Induction Heads* dan *Key-Value (KV) Cache* memproses token prompt serta demonstrasi *In-Context Learning* (ICL) pada arsitektur Transformer.
2. **Merancang Dynamic Few-Shot Architecture**: Mengimplementasikan pemilihan demonstrasi berbasis *Maximal Marginal Relevance* (MMR) dan *Vector Similarity* untuk memitigasi *label bias*, *recency bias*, dan *surface form competition*.
3. **Mengoptimalkan Prompt Cache & Token Budget**: Menerapkan arsitektur prompt deterministik yang memaksimalkan *prefix caching hit-rate* (OpenAI/Anthropic) hingga di atas 80%, memangkas latensi p95 hingga 50%, dan menekan biaya inferensi hingga 75%.
4. **Membangun Runtime Schema Enforcement**: Mengintegrasikan *Constrained Decoding* dan validasi skema berbasis *Pydantic v2* ke dalam pipeline produksi dengan strategi mitigasi *fallback* otomatis (deterministic self-healing).
5. **Menghindari Perangkap Context Degradation**: Mengidentifikasi dan memitigasi fenomena *Lost-in-the-Middle* serta *Context Window Saturation* pada beban kerja *real-time*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Pemahaman fundamental mengenai arsitektur Transformer (*Self-Attention*, *Query-Key-Value matrices*, *Positional Encoding*).
* Pemrograman Python tingkat lanjut (Async/Await, Type Hinting, Pydantic v2, NumPy).
* Konsep dasar Vector Embeddings dan kalkulasi jarak spasial (*Cosine Similarity*, *Euclidean Distance*).
* Akses ke LLM API modern (OpenAI GPT-4o / Anthropic Claude 3.5 Sonnet / LLM lokal via vLLM/Ollama).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Mekanisme Sirkuit Transformer pada In-Context Learning (ICL)

In-Context Learning (ICL) tidak mengubah bobot (*weights*) model melalui backpropagation; ICL adalah proses inferensi murni yang terjadi di dalam *forward pass*. Kemampuan model mempelajari pola dari contoh (*demonstrations*) secara instan berakar pada keberadaan sirkuit komputasi khusus yang disebut **Induction Heads** (diteliti secara mendalam oleh Anthropic Circuits Thread, Olsson et al.).

```
Layer L:      [Token A] ---------> Attention Head ---------> Salin representasi Token A
                  |
                  v
Layer L+1:    [Token B] pasca A -> Induction Head ---------> Prediksi kemunculan Token B 
                                                             saat Token A muncul kembali
```

Induction heads beroperasi melintasi minimal dua layer perhatian:
1. **Previous-Token Head (Layer L)**: Memetakan token sekarang ke token sebelumnya.
2. **Induction Head (Layer L+1)**: Mencari kemunculan token sebelumnya di masa lalu dalam konteks yang diberikan. Jika menemukan pola `[A][B] ... [A]`, induction head menaikkan probabilitas kemunculan `[B]` berikutnya.

Ketika demonstrasi ICL diinjeksikan ke dalam context window, induction heads membentuk sirkuit penyalinan dan asosiasi (*copying circuits*). Jika representasi token demonstrasi terdistorsi oleh noise format atau penempatan posisi yang buruk, aktivasi induction heads menurun secara signifikan, memicu kegagalan pemahaman tugas oleh LLM.

### 3.2 Positional Bias & Fenomena "Lost in the Middle"

Mekanisme self-attention Transformer $O(N^2)$ secara teoritis mampu mengakses semua token secara serentak. Namun, dalam praktiknya, distribusi perhatian (*attention distribution*) tidak merata:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

Penelitian empiris (Liu et al., *Lost in the Middle: How Language Models Use Long Contexts*) membuktikan adanya kurva berbentuk U (*U-shaped attention curve*):

```
Tingkat Akurasi Retrieval / Ekstraksi
 100% |  \                                                 /
      |   \                                               /
      |    \                                             /
      |     \___________________________________________/
   0% +-----------------------------------------------------------
      Awal Prompt (System/Prefix)   Tengah Prompt       Akhir Prompt (User/Task)
      [High Attention]             [Degradasi Tinggi]   [High Attention (Recency)]
```

* **Primacy Bias**: Token di awal prompt mendapatkan perhatian tinggi karena token `<s>` (BOS) dan instruksi sistem bertindak sebagai jangkar (*attention sink*).
* **Recency Bias**: Token di akhir prompt mempertahankan aktivasi yang kuat karena jarak posisi terdekat dengan token generasi berikutnya.
* **Middle Valley**: Token yang diletakkan di tengah-tengah context window berisiko tinggi diabaikan hingga 40-60% pada context window berukuran besar (>16k token).

### 3.3 KV Cache & Prefix Caching Mechanics

Pada mesin inferensi enterprise (misal: vLLM dengan PagedAttention, Anthropic Prompt Caching, OpenAI Prefix Matching), komputasi matriks Key ($K$) dan Value ($V$) untuk token yang identik tidak perlu dihitung ulang jika memenuhi prinsip deterministik:

1. **Prefix Invariance**: Cache hanya valid jika token dari indeks $0$ hingga indeks $K$ persis identik (*exact match* pada tingkat token ID, bukan sekadar string).
2. **Block Boundary Alignment**: Engine inferensi seperti vLLM membagi KV cache ke dalam blok-blok memori tetap (misal: 16 token per blok). Modifikasi satu spasi di awal prompt akan membatalkan seluruh blok berikutnya (*cache miss cascade*).

```
System Prompt (Statik)          Few-Shot Examples (Semi-Statik)   Dynamic Context   User Query
[Blok 0: 0-15] [Blok 1: 16-31]  [Blok 2: 32-47] [Blok 3: 48-63]   [Blok 4: 64-79]   [Blok 5: 80-...]
|<------- CACHED (Hit rate 100%) ------------->|                  |<--- UNCACHED (Compute) ------>|
```

### 3.4 Constrained Decoding vs. Post-Hoc Schema Parsing

Pendekatan rekayasa prompt konvensional mengandalkan instruksi teks bebas seperti: `"Keluarkan JSON yang valid!"`. Pendekatan ini rapuh di level produksi. Arsitektur produksi modern menggunakan salah satu dari dua metode penjaminan skema:

1. **Post-Hoc Parsing & Self-Correction**: Model menghasilkan token bebas, lalu divalidasi oleh parser (misal: `pydantic.model_validate_json`). Jika gagal, exception dikirim kembali ke model. Latensi meningkat $2\times$ hingga $3\times$.
2. **Grammar-Guided Constrained Decoding (Engine-Level)**: Engine inferensi (misal: llama.cpp, Outlines, vLLM) memodifikasi distribusi logits pada setiap langkah penarikan sampel token. Logit token yang melanggar aturan JSON Schema (atau Context-Free Grammar) disetel menjadi $-\infty$. Model secara deterministik tidak dapat menghasilkan format yang salah.

---

## 4. Why & What

| Dimensi | Prompt Naif / Hardcoded | Dynamic In-Context Production Architecture |
| :--- | :--- | :--- |
| **Kompilasi Prompt** | String template statis (`f"Jawab ini: {query}"`) | Kompilator pipeline berlapis dengan alokasi token budget otomatis. |
| **Pemilihan Few-Shot** | Contoh yang sama untuk seluruh user dan use-case | *Dynamic Retrieval* menggunakan k-NN + MMR untuk meminimalkan redundansi. |
| **Pemanfaatan Cache** | Non-deterministik; timestamp/user-ID ditaruh di awal prompt | Deterministik; prefix terisolasi, memaksimalkan KV cache reuse >80%. |
| **Penanganan Skema** | Mengandalkan ketelitian LLM menghasilkan JSON | Strict JSON Schema dengan validasi Pydantic runtime + logit bias/masking. |
| **Skalabilitas Biaya** | Linear bertambah seiring panjang konteks | Ditekan via Token Budgeting, Truncation, dan Prompt Caching discounts. |

---

## 5. How (Workflow Detail)

Arsitektur produksi end-to-end pemrosesan prompt dirancang dalam pipeline berikut:

```
[User Request Ingestion]
        │
        ▼
[Step 1: Context Sanitization & Token Budget Profiling]
        │
        ├──> Hitung Max Input Tokens = Total Context Window - Max Output Tokens - Safety Margin
        │
        ▼
[Step 2: Dynamic Few-Shot Demonstrations Retrieval]
        │
        ├──> Query Embeddings -> Vector DB
        ├──> k-NN Search (Ambil Top-N kandidat)
        └──> Maximal Marginal Relevance (MMR) Ranking (Pilih K contoh representatif & beragam)
        │
        ▼
[Step 3: Canonical Prompt Assembly & Cache Alignment]
        │
        ├──> [PREFIX] System Directive (Immutable)        <-- CACHE BREAKPOINT
        ├──> [STATIC CONTEXT] Domain Knowledge / Tools     <-- CACHE BREAKPOINT
        ├──> [FEW-SHOT EXAMPLES] MMR Selected Samples      <-- CACHE BREAKPOINT
        └──> [DYNAMIC TAIL] Live Context & User Query      <-- VOLATILE / NO-CACHE
        │
        ▼
[Step 4: Constrained Decoding Execution]
        │
        ├──> LLM Inference (Engine Level Schema Enforcement: JSON Schema)
        │
        ▼
[Step 5: Runtime Validation & Fallback Pipeline]
        │
        ├──> Pydantic Validation Success? ─────────┐
        │       │ (No)                             │ (Yes)
        │       ▼                                  │
        │    Attempt Fast Repair Function          │
        │       │                                  │
        │    Repair Failed?                        │
        │       │ (Yes)                            │
        │       ▼                                  │
        │    Deterministic Fallback Safe State     │
        │                                          │
        ▼                                          ▼
[Output Delivery to Client] <──────────────────────┘
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Assembly Line Manufaktur Presisi
Bayangkan context window LLM seperti sebuah meja kerja perakitan mekanis:
* **System Prompt** adalah cetak biru (*blueprint*) dan perkakas kerja yang dibaut permanen ke meja (tidak pernah dipindah-pindahkan).
* **Few-Shot Examples** adalah contoh produk jadi sempurna dari berbagai variasi ukuran yang dipajang di rak tepat di depan mata mekanik sebagai referensi fisik.
* **Dynamic Few-Shot Selector (MMR)** adalah asisten yang memilih variasi produk jadi yang paling relevan dengan suku cadang yang baru masuk, memastikan meja kerja tidak penuh dengan contoh yang identik.
* **User Query & Payload** adalah bahan mentah yang masuk melalui ban berjalan (*conveyor belt*).
* **Constrained Decoding** adalah cetakan baja presisi (*jig*). Mekanik tidak dapat menuangkan material melebihi batas cetakan tersebut, menjamin produk akhir presisi hingga fraksi milimeter tanpa perlu proses audit berulang kali.

### Diagram Struktur Anatomi Memory Alignment

```
0                                                                  Max Window (N Tokens)
┌─────────────────────────┬────────────────────────┬──────────────────────┬─────────────┐
│ 1. Core System Anchor   │ 2. Canonical Demonstrations│ 3. Dynamic RAG Data  │ 4. Task Tail│
│ (System Role, Persona,  │ (MMR Selected Few-Shots,│ (Document Chunks,    │ (Query,     │
│ Constraints, Base Schema)│ Frozen Format)         │ Ephemeral State)     │ Output Spec)│
└─────────────────────────┴────────────────────────┴──────────────────────┴─────────────┘
├─────────── STATIC PREFIX (KV CACHABLE) ──────────┤├────── EPHEMERAL / RUNTIME ─────────┤
▲                                                  ▲
└── Breakpoint 1                                   └── Breakpoint 2
    (Anthropic/vLLM Cache Friendly)                    (Cache Miss Boundary)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example (Anti-Pattern vs. Manual Implementation)

#### Anti-Pattern: String Concatenation Rapuh
```python
# SANGAT BURUK: Rawan format breakage, cache miss total di setiap run, rawan injeksi
def naive_prompt(query, examples, user_id, current_time):
    return f"""
    Waktu sekarang: {current_time}. User: {user_id}.
    Jawab query berikut: {query}
    Berikut contoh-contohnya:
    {examples}
    Keluarkan JSON ya!
    """
```

### 7.2 Practical Example: Enterprise-Grade Dynamic In-Context Pipeline

Di bawah ini adalah implementasi lengkap arsitektur prompt enterprise yang mencakup:
1. Dynamic Few-Shot Retrieval dengan seleksi berbasis keragaman (diversity-aware selection).
2. Penegakan Token Budget deterministik.
3. Cache-friendly canonical assembly.
4. Schema validation menggunakan Pydantic v2 dengan mekanisme fallback.

```python
import json
import logging
from typing import Any, Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EnterprisePromptEngine")

# --- 1. DOMAIN SCHEMAS ---
class ExtractionTarget(BaseModel):
    transaction_id: str = Field(..., description="ID transaksi unik alphanumeric")
    entity_name: str = Field(..., description="Nama entitas counterparty")
    amount: float = Field(..., gt=0, description="Nilai transaksi dalam nominal positif")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 Currency Code")
    risk_level: str = Field(..., pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")

class FewShotExample(BaseModel):
    input_text: str
    target_output: ExtractionTarget
    embedding: List[float]

# --- 2. VECTOR UTILS & MMR SELECTOR ---
def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(dot / (norm1 * norm2))

def maximal_marginal_relevance(
    query_embedding: np.ndarray,
    candidates: List[FewShotExample],
    k: int = 3,
    lambda_param: float = 0.6
) -> List[FewShotExample]:
    """
    Memilih k demonstrasi terbaik menggunakan MMR untuk menyeimbangkan
    relevansi semantik dan keragaman format (mengurangi bias demonstrasi redundant).
    """
    if not candidates:
        return []
        
    candidate_embeddings = np.array([c.embedding for c in candidates])
    selected_indices: List[int] = []
    unselected_indices = list(range(len(candidates)))
    
    # Precompute sim(d_i, query)
    query_similarities = np.array([
        cosine_similarity(query_embedding, emb) for emb in candidate_embeddings
    ])
    
    for _ in range(min(k, len(candidates))):
        if not selected_indices:
            # Pick token with highest query similarity
            idx = int(np.argmax(query_similarities))
            selected_indices.append(idx)
            unselected_indices.remove(idx)
            continue
            
        # Compute MMR for unselected candidates
        mmr_scores = []
        for idx in unselected_indices:
            sim_query = query_similarities[idx]
            max_sim_selected = max([
                cosine_similarity(candidate_embeddings[idx], candidate_embeddings[s_idx])
                for s_idx in selected_indices
            ])
            score = lambda_param * sim_query - (1 - lambda_param) * max_sim_selected
            mmr_scores.append(score)
            
        best_unselected_idx = unselected_indices[int(np.argmax(mmr_scores))]
        selected_indices.append(best_unselected_idx)
        unselected_indices.remove(best_unselected_idx)
        
    return [candidates[i] for i in selected_indices]

# --- 3. DYNAMIC PROMPT COMPILER ---
class EnterprisePromptCompiler:
    def __init__(self, system_instruction: str, max_total_tokens: int = 4096):
        self.system_instruction = system_instruction
        self.max_total_tokens = max_total_tokens
        
    def _approximate_tokens(self, text: str) -> int:
        # Rule of thumb deterministik: 1 token ~= 4 chars pada teks barat/simbol standar
        return len(text) // 4

    def build_prompt_payload(
        self,
        query_text: str,
        query_embedding: np.ndarray,
        few_shot_pool: List[FewShotExample],
        k_shots: int = 2
    ) -> List[Dict[str, str]]:
        # Layer 1: System Instruction (Static Prefix -> KV Cache Ready)
        messages = [
            {"role": "system", "content": self.system_instruction}
        ]
        
        # Layer 2: Demonstrations (Semi-static, derived via MMR)
        selected_shots = maximal_marginal_relevance(
            query_embedding=query_embedding,
            candidates=few_shot_pool,
            k=k_shots,
            lambda_param=0.65
        )
        
        for shot in selected_shots:
            messages.append({
                "role": "user",
                "content": f"[INSPECTION_PAYLOAD]:\n{shot.input_text}"
            })
            messages.append({
                "role": "assistant",
                "content": shot.target_output.model_dump_json(indent=None)
            })
            
        # Layer 3: Dynamic Tail (Live Payload)
        messages.append({
            "role": "user",
            "content": f"[INSPECTION_PAYLOAD]:\n{query_text}"
        })
        
        # Token Budget Validation
        total_chars = sum(len(m["content"]) for m in messages)
        estimated_tokens = self._approximate_tokens(str(total_chars))
        if estimated_tokens > self.max_total_tokens:
            raise ValueError(f"Token budget exceeded: {estimated_tokens} > {self.max_total_tokens}")
            
        return messages

# --- 4. ENGINE RUNTIME & VALIDATION DECORATOR ---
class ProductionLLMRuntime:
    def __init__(self, compiler: EnterprisePromptCompiler):
        self.compiler = compiler

    def mock_llm_call(self, messages: List[Dict[str, str]]) -> str:
        """Simulasi return dari LLM yang dikonfigurasi dengan JSON Mode/Structured Output."""
        # LLM inference simulation
        return json.dumps({
            "transaction_id": "TXB-902184",
            "entity_name": "Acme Global Treasury Corp",
            "amount": 1542000.50,
            "currency": "USD",
            "risk_level": "HIGH"
        })

    def execute_pipeline(
        self,
        raw_text: str,
        embedding: np.ndarray,
        demonstration_pool: List[FewShotExample]
    ) -> ExtractionTarget:
        payload = self.compiler.build_prompt_payload(
            query_text=raw_text,
            query_embedding=embedding,
            few_shot_pool=demonstration_pool,
            k_shots=2
        )
        
        logger.info(f"Compiled {len(payload)} message blocks. Executing model request...")
        raw_output = self.mock_llm_call(payload)
        
        # Strict parsing
        try:
            validated_output = ExtractionTarget.model_validate_json(raw_output)
            return validated_output
        except ValidationError as err:
            logger.error(f"Schema violation detected: {err.json()}")
            # Safe Fallback Engine
            return self._deterministic_fallback(raw_text)

    def _deterministic_fallback(self, raw_text: str) -> ExtractionTarget:
        logger.warning("Invoking emergency structural fallback logic.")
        return ExtractionTarget(
            transaction_id="ERR-FALLBACK",
            entity_name="UNKNOWN_CORRUPTED",
            amount=0.01,
            currency="USD",
            risk_level="CRITICAL"
        )

# --- 5. EXECUTION SUITE ---
if __name__ == "__main__":
    system_prompt = (
        "You are an automated regulatory compliance parsing engine. "
        "Extract transactional entities and output strictly according to the defined schema. "
        "No conversational filler."
    )
    
    # Setup dummy database demonstrasi
    dummy_pool = [
        FewShotExample(
            input_text="Wire transfer from Alpha Ltd of 45000 EUR under ID AL-881",
            target_output=ExtractionTarget(
                transaction_id="AL-881", entity_name="Alpha Ltd", amount=45000.0,
                currency="EUR", risk_level="LOW"
            ),
            embedding=[0.12, 0.45, 0.78, 0.01]
        ),
        FewShotExample(
            input_text="Suspicious deposit received: 9900 USD, account holder Beta Offshore, ref #SH-001",
            target_output=ExtractionTarget(
                transaction_id="SH-001", entity_name="Beta Offshore", amount=9900.0,
                currency="USD", risk_level="MEDIUM"
            ),
            embedding=[0.88, 0.12, 0.33, 0.54]
        )
    ]
    
    compiler = EnterprisePromptCompiler(system_instruction=system_prompt)
    runtime = ProductionLLMRuntime(compiler=compiler)
    
    test_input = "Urgent: Swift transfer from Acme Global Treasury Corp of 1542000.50 USD. Ref: TXB-902184"
    test_embedding = np.array([0.85, 0.15, 0.30, 0.50])
    
    result = runtime.execute_pipeline(test_input, test_embedding, dummy_pool)
    print("\n--- Validated Production Output ---")
    print(result.model_dump_json(indent=2))
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: FinTech Global Multi-Tenant AML (Anti-Money Laundering) Screening Engine
* **Skala Sistem**: 12.000.000 dokumen transaksi tidak terstruktur per hari across 14 yurisdiksi.
* **SLA**: Latensi inferensi p95 $\le 350\text{ ms}$, False Negative Rate (FNR) $\le 0.001\%$, Keabsahan parsing schema $99.999\%$.

### Masalah Utama
1. **Cache Thrashing**: Template prompt mencantumkan `Tenant-ID` dan `Timestamp` pada karakter pertama sistem prompt, sehingga setiap request menghasilkan KV Cache Miss di vLLM cluster. Biaya komputasi melambung hingga \$180.000/bulan.
2. **Format Contamination**: Penggunaan random few-shot retrieval menyebabkan model meniru currency format yang salah (misal: menggunakan koma `,` desimal Eropa pada parsing rekening Amerika Serikat).
3. **Context Collapse**: Instruksi kepatuhan compliance yang sangat panjang (4.000 token) diabaikan oleh LLM ketika diletakkan di tengah log audit transaksi.

### Solusi Arsitektural
1. **Hierarchical Deterministic Prefix**:
   * *Prefix Layer 0*: Aturan validasi yurisdiksi baku (100% identik di seluruh tenant, berumur panjang, memicu Shared Prefix Cache).
   * *Prefix Layer 1*: 3 demonstrasi terpilih melalui MMR yang diambil dari repositori yurisdiksi yang spesifik.
   * *Tail Dynamic Layer*: Data transaksi mentah yang digabungkan dengan Tenant Context Header di bagian paling belakang.
2. **Logit-Masked Guided Grammar Decoding**:
   Menggantikan prompting JSON bebas dengan *Outlines-based JSON-Schema constrained generation* yang diintegrasikan langsung pada inference gateway layer (vLLM API).
3. **Position Realignment**:
   Instruksi sanksi terpenting dipindahkan dari tengah dokumen ke 150 token terakhir sebelum tag trigger generasi `[OUTPUT]`.

### Hasil Metrik
* **KV-Cache Hit Rate**: Melonjak dari 2.4% menjadi **88.7%**.
* **p95 Latency**: Menurun drastis dari **1.450 ms** ke **280 ms**.
* **Komputasi & Biaya**: Penghematan biaya komputasi GPU bulanan sebesar **64.2%** (\$115.000/bulan).
* **Schema Validation Failure**: Turun menjadi **0.000%** (zero-failure) berkat engine-level constrained decoding.

---

## 9. Trade-offs

| Parameter | Pendekatan A: Zero-Shot Direct Execution | Pendekatan B: Static Few-Shot (N=5) | Pendekatan C: Dynamic MMR Retrieval Few-Shot |
| :--- | :--- | :--- | :--- |
| **Akurasi Tugas Kompleks** | Rendah (60-70%) | Menengah-Tinggi (80-85%) | Sangat Tinggi (>95%) |
| **Token Overhead** | Minimal (0 extra tokens) | Tinggi & Konstan (+1000 s/d 3000 tokens) | Terkontrol & Dinamis (+500 s/d 1500 tokens) |
| **Prefix Cache Hit Rate**| Sangat Tinggi (Jika prefix seragam) | Tinggi (Prefix stabil) | Menengah-Tinggi (Tergantung variasi contoh terpilih) |
| **Latency Vector Search** | 0 ms | 0 ms | 15 - 45 ms (overhead k-NN/MMR) |
| **Biaya per 1M Query** | Sangat Rendah | Tinggi | Sedang-Tinggi (Diimbangi penurunan retry rate) |
| **Kerentanan Format Drift** | Tinggi | Menengah (Bisa bias pada 5 contoh tsb) | Sangat Rendah (Adaptif terhadap domain query) |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Dynamic Prefix Cache-Buster
* **Gejala**: KV Cache hit rate bernilai 0% pada monitoring endpoint inferensi LLM enterprise.
* **Akar Masalah**: Menyisipkan variabel dinamis di baris awal prompt (misal: `Generated at: 2023-10-25 14:00:01` atau `Request-UUID: f81d4...`).
* **Solusi**: Pindahkan semua metadata volatil ke lapisan paling bawah (setelah user payload). Jaga prefix tetap deterministik dan statik secara absolut.

### 2. Label Contamination & Majority Class Bias
* **Gejala**: LLM selalu mengeluarkan klasifikasi `"HIGH RISK"` terlepas dari payload input.
* **Akar Masalah**: Pilihan few-shot demonstrations yang diambil secara k-NN kebetulan semuanya memiliki label `"HIGH RISK"`. Model mengalami bias distribusi probabilitas posterior priors (*in-context frequency bias*).
* **Solusi**: Gunakan *Class-Balanced Dynamic Retrieval*. Algoritma seleksi wajib menjamin distribusi label pada $k$ demonstrasi seimbang (misal: 1 Low, 1 Medium, 1 High).

### 3. Context Window Truncation Silently Corrupting JSON
* **Gejala**: Engine menghasilkan string terpotong seperti `{"status": "SUCCES`, menyebabkan parser Pydantic melempar `JSONDecodeError`.
* **Akar Masalah**: Alokasi `max_tokens` generasi model tidak memperhitungkan sisa kuota setelah prompt input dimasukkan, sehingga decoder berhenti mendadak karena mencapai limit context window token maksimum engine.
* **Solusi**: Terapkan assertion ketat pada prompt runtime:
  $$\text{Budget}_{\text{prompt}} \le \text{Context}_{\text{max}} - \text{Tokens}_{\text{generation\_limit}} - \text{Margin}_{\text{safety}}$$

---

## 11. Best Practices (Production Checklist)

- [ ] **Prefix Invariance Guard**: Apakah 200 token pertama prompt 100% identik untuk seluruh pengguna dan sesi?
- [ ] **Structural Delimiters**: Apakah setiap blok informasi (Instruksi, Sistem, Few-Shot, User Data) dibungkus menggunakan XML tags atau Markdown markers yang konsisten (misal: `<context></context>`, `[INSTRUCTION]`)?
- [ ] **Diversity-Aware Demonstration**: Apakah dynamic few-shot selector mengimplementasikan penalti kesamaan (misal: MMR atau cosine distance thresholding) agar tidak memasukkan contoh yang duplikat?
- [ ] **Order Permutation Resilience**: Apakah akurasi model telah diuji terhadap perubahan urutan demonstrasi few-shot (memastikan model tidak hanya menghafal demonstrasi terakhir)?
- [ ] **Grammar/Schema Binding**: Apakah parsing output diamankan menggunakan constrained decoding langsung dari inference engine, atau minimal divalidasi dengan library berbasis deserialisasi ketat (Pydantic v2)?
- [ ] **Deterministic Fallback Routing**: Apakah sistem memiliki safe-state response jika model menghasilkan exception berulang kali?
- [ ] **Token Truncation Safety**: Apakah panjang string input pengguna dipotong berbasis *tokenizer token-count* aktual (bukan pemotongan karakter string primitif)?

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### Struktur Direktori
```
hands-on/m02/
├── README.md
├── requirements.txt
├── prompt_compiler.py
└── test_pipeline.py
```

### File 1: `requirements.txt`
```
pydantic>=2.6.0
numpy>=1.26.0
```

### File 2: `prompt_compiler.py`
Buat skrip engine produksi di `hands-on/m02/prompt_compiler.py`:

```python
import hashlib
from typing import List, Dict
import numpy as np
from pydantic import BaseModel, Field

class AnalysisReport(BaseModel):
    category: str = Field(..., pattern="^(INCIDENT|REQUEST|INQUIRY)$")
    severity: int = Field(..., ge=1, le=5)
    summary: str = Field(..., min_length=10)

class ProductionCompiler:
    def __init__(self, static_directive: str):
        # Prefix immutable: menjamin cache deterministik
        self.prefix = static_directive
        
    def hash_prefix(self) -> str:
        """Mengembalikan hash sha256 untuk memantau integritas KV cache prefix."""
        return hashlib.sha256(self.prefix.encode('utf-8')).hexdigest()

    def compile(self, payload: str, examples: List[Dict[str, str]]) -> str:
        # Pembangunan urutan: Static Prefix -> Few-Shot Examples -> Payload
        buffer = [f"<SYSTEM_DIRECTIVE>\n{self.prefix}\n</SYSTEM_DIRECTIVE>"]
        
        if examples:
            buffer.append("<DEMONSTRATIONS>")
            for idx, ex in enumerate(examples, 1):
                buffer.append(f"<EXAMPLE index='{idx}'>")
                buffer.append(f"<INPUT>{ex['input']}</INPUT>")
                buffer.append(f"<OUTPUT>{ex['output']}</OUTPUT>")
                buffer.append("</EXAMPLE>")
            buffer.append("</DEMONSTRATIONS>")
            
        buffer.append(f"<RUNTIME_PAYLOAD>\n{payload}\n</RUNTIME_PAYLOAD>")
        buffer.append("<ASSISTANT_RESPONSE>\n")
        return "\n".join(buffer)

if __name__ == "__main__":
    directive = "You are a Level-3 Enterprise NOC triage engine. Classify with exact schema."
    compiler = ProductionCompiler(directive)
    print("Prefix SHA256 (Cache Key Anchor):", compiler.hash_prefix())
    
    dummy_examples = [
        {"input": "Server db-01 kernel panic", "output": '{"category": "INCIDENT", "severity": 5, "summary": "Database server fatal kernel panic"}'}
    ]
    
    compiled = compiler.compile("Network interface eth0 dropping packets > 15%", dummy_examples)
    print("\n--- Compiled Prompt Structure ---")
    print(compiled)
```

### File 3: `test_pipeline.py`
Jalankan validasi pengujian:

```bash
cd hands-on/m02
python -m venv venv
source venv/bin/activate  # atau venv\Scripts\activate pada Windows
pip install -r requirements.txt
python prompt_compiler.py
```

---

## 13. Exercise

### Level: Easy
1. Modifikasi script `prompt_compiler.py` agar fungsi `compile()` menerima parameter konfigurasi pemotongan teks pengguna (*hard-limit string truncation*) pada 1000 karakter pertama tanpa memutus prefix caching.
2. Tambahkan validasi error handling apabila data demonstrasi few-shot yang diinput berformat kosong.

### Level: Medium
1. Kembangkan class `ClassBalancedSampler` di Python yang menerima list dokumen berlabel, dan secara deterministik mengembalikan $k$ demonstrasi yang membagi kuota label secara merata (misal untuk $k=3$ dan label ada 3 tipe: Incident, Request, Inquiry, masing-masing wajib terpilih tepat 1).
2. Tunjukkan dengan pengujian unit test bahwa perubahan urutan prompt input runtime tidak mengubah *SHA256 signature* dari System Directive Prefix.

### Level: Hard
1. Buat pipeline asynchronous yang memproses 50 request secara paralel.
2. Integrasikan mekanisme *Simulated In-Memory KV Cache*:
   * Jika prefix prompt pernah terlihat dalam cache table, catat sebagai *Cache Hit* (latensi disimulasikan 5 ms).
   * Jika prefix berubah, catat sebagai *Cache Miss* (latensi disimulasikan 250 ms).
3. Buktikan secara empiris bahwa penempatan metadata timestamp di awal prompt menurunkan throughput pemrosesan sebesar $\ge 70\%$ dibandingkan penempatan di akhir payload.

---

## 14. Challenge

Rancang arsitektur **"Self-Healing Adaptive Few-Shot Injector"** kelas perbankan:
* **Kebutuhan**: Sistem menerima dokumen klaim asuransi dalam 10 bahasa berbeda. Anda memiliki database 10.000 demonstrasi historis.
* **Kendala**:
  1. Context window input dibatasi maksimal 2.048 token demi efisiensi biaya.
  2. Latensi keseluruhan pipeline (Retrieval demonstrasi + Prompt Compilation + Inferensi LLM) tidak boleh melebihi 400 ms pada p99.
  3. LLM sering kali mengalami halusinasi mata uang jika contoh few-shot menggunakan simbol mata uang yang berbeda dengan dokumen input.
* **Tugas Anda**: Buat spesifikasi arsitektur teknis lengkap (algoritma seleksi dokumen, penanganan KV Cache prefix, filtering demonstrasi strictly-matched currency, token budget manager, dan fallback circuit) tanpa menggunakan library orkestrator black-box tingkat tinggi (seperti LangChain/LlamaIndex). Sajikan dalam bentuk rancangan modul Python murni siap produksi.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic Questions
1. **Mengapa penambahan spasi atau karakter whitespace tunggal di awal system prompt dapat merusak KV Cache Prefix Matching pada LLM engine modern?**
2. **Apa peran utama dari *Induction Heads* dalam arsitektur Transformer saat menjalankan tugas In-Context Learning?**
3. **Dalam anatomi prompt terstruktur, mengapa System Instruction harus diletakkan sebelum Few-Shot Demonstrations, bukan sesudahnya?**
4. **Apa yang dimaksud dengan fenomena *Lost-in-the-Middle* pada pemrosesan LLM?**
5. **Mengapa parsing JSON berbasis regular expression (Regex) tidak disarankan untuk aplikasi produksi yang membutuhkan SLA tinggi?**

### 15.2 Intermediate Questions
6. **Bagaimana algoritma Maximal Marginal Relevance (MMR) mencegah kegagalan penalaran model pada Dynamic Few-Shot Learning dibandingkan penarikan k-NN murni berbasis Cosine Similarity?**
7. **Jelaskan perbedaan mendasar antara mekanisme penegakan skema via *Logit Masking / Constrained Decoding* versus *Post-Generation Pydantic Validation* dalam konteks konsumsi token dan waktu komputasi!**
8. **Bagaimana distribusi posisi demonstrasi few-shot memengaruhi *Recency Bias* model Transformer?**
9. **Mengapa teknik *Label Permutation Testing* penting dilakukan saat merancang arsitektur Few-Shot Prompting untuk klasifikasi biner/multikelas?**
10. **Bagaimana cara mengisolasi informasi yang bersifat volatil (seperti `User Authentication Token` dan `Request Timestamp`) dalam arsitektur prompt enterprise agar KV Cache hit-rate tetap optimal?**

### 15.3 Skenario Kasus Produksi
11. **Skenario 1**: Sebuah sistem ekstraksi dokumen legal memproses dokumen kontrak berukuran rata-rata 12.000 token. Pipeline menambahkan 5 contoh few-shot lengkap (masing-masing 1.500 token). Saat dijalankan, akurasi ekstraksi klausul di tengah kontrak anjlok hingga 32%, padahal akurasi ekstraksi pada dokumen uji berukuran kecil bernilai 96%. Analisis akar masalah teknis internal transformer dan tentukan 2 langkah mitigasi arsitektur prompt-nya!
12. **Skenario 2**: Engine inferensi cluster vLLM Anda mengalami lonjakan latensi p99 dari 200 ms menjadi 1.800 ms setelah rilis fitur baru, di mana pengembang menambahkan `Client-Session-ID` dinamis pada baris pertama teks prompt. Jelaskan secara mekanistik apa yang terjadi pada PagedAttention memory manager dan bagaimana memperbaikinya!
13. **Skenario 3**: Sebuah API klasifikasi sentimen financial news menggunakan 4 demonstrasi few-shot statis. Seluruh contoh demonstrasi yang disematkan secara kebetulan memiliki target label `POSITIVE`. Saat inferensi pada data riil yang netral atau negatif, model tetap memprediksi `POSITIVE` pada 88% kasus. Jelaskan anomali psikologi komputasi model ini dan bangun rancangan perbaikan retrieval-nya!

---

### Kunci Jawaban & Pembahasan Quiz

#### Jawaban Basic
1. **Pembahasan**: KV Cache engine memetakan token sequence secara deterministik dari indeks 0. Perubahan 1 karakter di awal prompt mengubah representasi token ID dari token awal tersebut, menyebabkan seluruh kalkulasi matriks Key-Value pada posisi-posisi berikutnya menjadi invalid (*hash mismatch*). Seluruh KV Cache dari awal hingga akhir terpaksa dihitung ulang dari nol (*full recomputation*).
2. **Pembahasan**: Induction heads bertanggung jawab untuk mengenali pengulangan pola dan relasi urutan token `[A][B] ... [A] -> [B]`. Sirkuit ini menyalin dan mengarahkan perhatian model ke token kelanjutan yang sesuai berdasarkan contoh konteks yang telah muncul sebelumnya di dalam context window.
3. **Pembahasan**: Meletakkan System Instruction di awal memanfaatkan *Primacy Bias* (attention sink token awal) untuk mengunci representasi global model, sekaligus memenuhi aturan Prefix Invariance agar blok instruksi sistem dapat disimpan permanen di KV Cache engine inferensi untuk digunakan bersama oleh semua pemanggilan berikutnya.
4. **Pembahasan**: Penurunan drastis performa penarikan informasi atau pematuhan instruksi ketika token kunci diletakkan di tengah-tengah context window yang panjang, diakibatkan oleh distribusi perhatian attention heads yang terkonsentrasi secara asimetris pada awal (*primacy*) dan akhir (*recency*) konteks.
5. **Pembahasan**: Regex hanya memeriksa pencocokan pola teks tanpa memahami hierarki sintaksis rekursif (nested brackets, escaped quotes, JSON structure validity). Regex tidak dapat mencegah terpotongnya token di tengah jalan atau menangani skema bertingkat secara deterministik, serta rentan terhadap *catastrophic backtracking*.

#### Jawaban Intermediate
6. **Pembahasan**: k-NN murni hanya memaksimalkan skor kesamaan ($\text{Sim}(D_i, Q)$), yang berisiko menarik $k$ contoh yang nyaris identik satu sama lain. Hal ini menyebabkan redundansi informasi dan pemborosan context budget. MMR menyertakan penalti keragaman ($\max \text{Sim}(D_i, D_j)$), memaksa contoh yang terpilih relevan dengan query tetapi saling berbeda secara representasi, mencakup variasi kasus edge-case yang lebih luas.
7. **Pembahasan**: *Constrained Decoding* mengeliminasi token yang melanggar grammar secara langsung pada tahap penarikan sampel logit di level engine GPU (probabilitas token diset $-\infty$). Model dijamin $100\%$ memproduksi output valid dalam $1\times$ jalan inferensi. *Post-Validation* membiarkan model berhalusinasi menghasilkan token yang salah, membuang token output, dan membutuhkan round-trip inferensi baru (retry) yang melipatgandakan latensi dan konsumsi biaya token.
8. **Pembahasan**: Model Transformer memiliki kecenderungan bawaan untuk memprioritaskan informasi yang paling dekat dengan generasi token berikutnya (*Recency Bias*). Jika contoh few-shot terakhir memiliki format atau kelas label tertentu, distribusi logit model akan terdistorsi ke arah karakteristik contoh terakhir tersebut.
9. **Pembahasan**: Untuk mendeteksi apakah model benar-benar memahami relasi input-output atau sekadar menghafal posisi/frekuensi label. Pengujian dilakukan dengan menukar susunan label pada demonstrasi (misal: membalik urutan contoh positif/negatif) untuk memastikan akurasi klasifikasi tidak berfluktuasi secara ekstrem akibat bias urutan (*order sensitivity*).
10. **Pembahasan**: Tempatkan seluruh token dinamis/volatil (user ID, timestamp, session token) di lapisan paling akhir (*payload tail*) persis sebelum token instruksi trigger inferensi. Dengan demikian, blok token dari System Prompt hingga Few-Shot Demonstrations di atasnya tetap 100% identik dan dapat di-cache secara permanen oleh layer PagedAttention/KV Cache.

#### Jawaban Skenario Kasus Produksi
11. **Pembahasan Skenario 1**:
    * *Akar Masalah*: Kombinasi konteks raksasa (12k token) dan penambahan 5 few-shot panjang (7.5k token) mendorong dokumen kontrak masuk ke area "Middle Valley" (lembah mati perhatian). Mekanisme self-attention terdistraksi oleh token demonstrasi yang masif dan gagal mempertahankan aktivasi pada klausul kontrak di area tengah.
    * *Langkah Mitigasi*:
      1. Kompresi Few-Shot: Ubah 5 demonstrasi lengkap menjadi *Micro-Demonstrations* (hanya menampilkan snippet klausul terisolasi, bukan keseluruhan dokumen), mereduksi overhead demonstrasi dari 7.500 token menjadi <600 token.
      2. Chunking & Sandwich Architecture: Pecah dokumen menjadi chunk terdistribusi, atau posisikan instruksi ekstraksi kritis beserta skema target tepat di penutup context window (*recency slot*) setelah payload dokumen, bukan di awal saja.
12. **Pembahasan Skenario 2**:
    * *Akar Masalah*: Penyisipan `Client-Session-ID` pada indeks 0 memicu *Cache Miss Cascade* total di layer PagedAttention vLLM. Setiap request dialokasikan blok memori fisik GPU baru dan memaksa GPU menghitung ulang komputasi Key-Value matrix untuk seluruh system prompt dan instrumen tools pada setiap request, menghancurkan throughput server.
    * *Solusi Perbaikan*: Pindahkan `Client-Session-ID` ke dalam metadata wrapper di akhir prompt (misal di dalam tag `<session id="..."/>` di bawah payload data). Pertahankan blok awal prompt agar 100% statik untuk seluruh tenant/session, mengembalikan KV Cache hit-rate ke level optimal (>80%) dan memulihkan latensi ke kisaran 200 ms.
13. **Pembahasan Skenario 3**:
    * *Akar Masalah*: Model mengalami *In-Context Frequency / Majority Label Contamination*. Ketika induction heads mendeteksi probabilitas transisi label target pada seluruh demonstrasi bernilai 100% `POSITIVE`, model menyesuaikan *prior probability* output generasi ke arah label tersebut, menenggelamkan bukti kontekstual pada artikel input.
    * *Rancangan Perbaikan*:
      Implementasikan *Dynamic Class-Balanced Few-Shot Selector*: Algoritma retrieval wajib mengalokasikan kuota seimbang secara deterministik (misal: k=3 wajib mengambil 1 Positive, 1 Neutral, 1 Negative menggunakan partitioned k-NN). Jika dataset query tidak memiliki representasi seimbang, fallback ke skema evaluasi *Zero-Shot* dengan instruksi kalibrasi netral eksplisit.

---

## 16. Summary

* **In-Context Learning** dikemudikan oleh sirkuit transformer (*Induction Heads*) yang memetakan dan menyalin pola transisi token tanpa memodifikasi bobot model.
* Posisi informasi di dalam prompt menentukan keberhasilan eksekusi: hindari meletakkan payload kritis di area tengah context window (*Lost-in-the-Middle*) dan manfaatkan area awal (*Primacy*) serta akhir (*Recency*).
* **Prefix Caching** adalah pilar utama efisiensi komputasi inferensi skala enterprise. Susun prompt secara bergradien dari token yang paling statis (System Prompt) ke token yang paling dinamis (User Query Tail). Hindari menyisipkan metadata variabel di awal prompt.
* Pemilihan demonstrasi few-shot dinamis wajib menggunakan metode diversifikasi seperti **Maximal Marginal Relevance (MMR)** dan penyeimbangan kelas (*Class Balancing*) guna mencegah bias label dan kontaminasi format.
* Keandalan sistem produksi dicapai dengan menggabungkan **Grammar-Guided Constrained Decoding** pada inference engine dan deserialisasi ketat via **Pydantic v2**, memastikan sistem bebas dari kegagalan parsing format JSON.