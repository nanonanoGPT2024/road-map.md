# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Structured Outputs & Advanced Schema Engineering**  
**Jalur: 08-AI-Data-and-Autonomous-Agents**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Memahami mekanisme internal *constrained decoding* berbasis *Context-Free Grammar* (CFG) dan *Finite State Machine* (FSM) pada inference engine LLM.
- Merancang dan mengompilasi schema data tingkat lanjut menggunakan Pydantic V2, mencakup *discriminated unions*, *recursive models*, dan validasi runtime berlapis.
- Mengimplementasikan pipeline *structured output* dengan garansi integritas schema 100% menggunakan native provider API (`strict: true`) dan framework validasi deterministik.
- Membangun mekanisme *streaming partial-JSON parsing* untuk mengurangi *Time-To-First-Token* (TTFT) dan *Perceived Latency* pada antarmuka agen interaktif.
- Menerapkan arsitektur *Schema Registry* terdesentralisasi, mitigasi *schema drift*, dan automated self-healing/repair loops pada pipeline enterprise.

---

## 2. Prerequisite

Peserta diasumsikan telah memiliki pemahaman mendalam pada:
- **Python 3.11+ Core**: Type hints lanjutan (`typing.Annotated`, `typing.Literal`, `typing.Union`, Generic Types).
- **Pydantic V2**: Konsep `BaseModel`, `field_validator`, `model_validator`, dan serialisasi JSON Schema.
- **REST & JSON Schema Core**: JSON Schema Draft 7 / Draft 2020-12 specification.
- **Konsep LLM Dasar**: Arsitektur Transformer autoregresif, mekanisme tokenisasi (BPE/SentencePiece), sampling temperature, top-p, dan logits.

---

## 3. Concept & Internal Architecture

Dalam rekayasa sistem agen otonom, *Structured Outputs* bukan sekadar teknik rekayasa prompt ("*Return output as valid JSON*"). Pada tingkat enterprise, pendekatan berbasis prompt memiliki tingkat kegagalan fatal (halusinasi sintaksis, *markdown code fences leakage*, *truncated objects*). Modul ini berfokus pada **Constrained Decoding Deterministic**.

### 3.1 Anatomi Constrained Decoding (Grammar-Guided Generation)

Pada proses inferensi LLM standar, distribusi probabilitas token berikutnya dihitung melalui fungsi Softmax terhadap seluruh vocabulary ($V$):

$$P(w_{t} \mid w_{<t}) = \text{softmax}(z_t)$$

Di mana $z_t \in \mathbb{R}^{|V|}$ adalah vektor logits mentah pada time-step $t$.

Dalam arsitektur *Constrained Decoding* (diadopsi oleh engine modern seperti `vLLM`, `Outlines`, `llama.cpp` via GBNF, dan OpenAI API `strict: true`):

```
       JSON Schema (Pydantic / Draft-07)
                      │
                      ▼
        Regex / Context-Free Grammar (CFG)
                      │
                      ▼
         Deterministic Finite Automaton (DFA)
                      │
   State t ───────────┴───────────┐
      │                           ▼
      │             Vocabulary Logit Masking
      │             (Invalid token indices -> -inf)
      ▼                           │
 Raw Logits [z_t] ───────────────► ⊘ Filtered Logits [z'_t]
                                  │
                                  ▼
                            Softmax Sampling
                                  │
                                  ▼
                         Sampled Token w_t
                                  │
                        Update DFA State -> t+1
```

1. **Schema Compilation**: JSON Schema target dikompilasi menjadi *Context-Free Grammar* (CFG) atau *Deterministic Finite Automaton* (DFA).
2. **State Tracking**: Engine inferensi melacak status parsing sintaksis saat ini ($State_t$).
3. **Logit Masking**: Sebelum Softmax dieksekusi, engine memindai seluruh vocabulary token. Token yang jika di-generate akan melanggar aturan tata bahasa (misalnya: token alfabet ketika parser sedang mengekspektasikan penutup string `"` atau titik dua `:`) di-mask dengan nilai $-\infty$:

$$z'_{t, i} = \begin{cases} z_{t, i} & \text{jika token } i \in \text{LegalTokens}(State_t) \\ -\infty & \text{jika token } i \notin \text{LegalTokens}(State_t) \end{cases}$$

4. **Zero-Probability Softmax**: Token yang tidak valid memiliki probabilitas matematis mutlak $0\%$. Model secara matematis mustahil menghasilkan JSON yang *malformed*.

### 3.2 Dynamic Action Routing via Discriminated Unions

Agen otonom tingkat lanjut tidak menggunakan prompt branching tunggal. Mereka memanfaatkan dynamic action schema berbasis *Tagged/Discriminated Unions*. Setiap aksi merepresentasikan *state transition* yang tervalidasi secara tipe data sebelum dieksekusi oleh runtime execution engine.

---

## 4. Why & What

| Fitur | Prompt-Based Formatting (Old Way) | Grammar-Constrained Output (Production Way) |
| :--- | :--- | :--- |
| **Garansi Sintaks** | Probabilistik (90% - 98% akurasi sintaks). | Deterministik (100% compliant terhadap schema). |
| **Penanganan Error** | Mengharuskan regex cleaning, retry loop mahal. | Zero structural syntax errors at generation time. |
| **Token Efficiency**| Token terbuang untuk penjelas format di prompt. | Prompt ringkas; model dipaksa pada level decoding. |
| **Throughput & VRAM**| Ringan di inference engine, boros di downstream retry. | Membutuhkan kompilasi grammar & dynamic masking memory overhead. |
| **Parsing Streaming** | Menunggu payload selesai secara utuh (`json.loads`). | Chunk streaming parsing menggunakan event-driven lexical analyzers. |

---

## 5. How: End-to-End Enterprise Architecture

Alur kerja pipeline *Advanced Schema Engineering*:

```
User Intent
    │
    ▼
Schema Selection Router ──► [Schema Registry / Catalog]
    │                                  │
    │ (Selected: ToolExecutionSchema)  │
    ▼                                  ▼
Dynamic System Context Injector ◄──────┘
    │
    ▼
LLM Inference Engine (vLLM / OpenAI Engine)
    ├── Logit Masking Engine (CFG/FSM Evaluator)
    └── Token-by-Token Streaming Output
          │
          ▼
Streaming Event-Driven Parser (Partial JSON Deserializer)
    │
    ├── Partial Yield: UI Realtime Render (Delta updates)
    │
    ▼
Terminal Payload -> Pydantic Runtime Deep Validation
    ├── Success ──► Execution Engine (Agent Sandbox)
    └── Validation Error (Semantic Breach)
          │
          ▼
    Reflection Loop (Self-Healing Context + Error Metadata)
          │
          ▼ (Re-submission to LLM)
```

1. **Schema Retrieval**: Router memilih schema aksi berdasarkan intent dan state agen saat ini.
2. **Grammar Injection**: Schema disuntikkan ke parameter decoding LLM (`response_format` dengan flag `strict=True`).
3. **Streaming Token Generation**: Logit mask memastikan token mengikuti spesifikasi RFC 8259 secara ketat.
4. **Intermediate Parsing**: Output diurai secara inkremental menggunakan lexical token emitter.
5. **Runtime Validation & Execution**: Begitu payload lengkap, schema dievaluasi ulang terhadap business logic (bukan hanya sintaksis, melainkan batasan referensial/semantik) sebelum eksekusi.

---

## 6. Analogy & Diagram ASCII

### Analogi: Lintasan Rel Kereta (Grammar-Constrained) vs Jalur Terbuka (Prompt-Based)

* **Prompt-Based Decoding** ibarat menyuruh masinis mengemudikan truk di lapangan terbuka bermodal instruksi tertulis: *"Tolong jalan lurus dan hanya belok di marka jalan."* Masinis bisa saja tergelincir, keluar jalur, atau salah membaca tanda.
* **Constrained Decoding** ibarat kereta api di atas rel baja. Persimpangan rel (FSM state) secara mekanis mengunci roda sehingga roda **secara fisik tidak bisa** berbelok ke arah yang tidak ada relnya.

### State Transition Diagram (JSON String Parsing FSM)

```
       [ Non-Quote Token ]
          ┌────────┐
          │        │
          ▼        │
   ───► ( IN_STRING ) ─────── Quote Token ["] ───────► ( EXPECT_COLON )
          │                                                   │
     Escape Token [\]                                    Colon Token [:]
          │                                                   │
          ▼                                                   ▼
     ( IN_ESCAPE ) ─── Valid Escaped Token ───►          ( VALUE_START )
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Skema Dasar dengan OpenAI Native Strict Mode

```python
import os
from pydantic import BaseModel, Field
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

class SimpleAgentAction(BaseModel):
    action_type: str = Field(description="Jenis tindakan yang akan diambil")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Tingkat keyakinan agen")
    payload: dict[str, str] = Field(description="Parameter eksekusi key-value")

completion = client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Tentukan aksi berdasarkan kebutuhan user."},
        {"role": "user", "content": "Simpan alamat email dev@enterprise.internal ke database."}
    ],
    response_format=SimpleAgentAction,
)

parsed_output: SimpleAgentAction = completion.choices[0].message.parsed
print(f"Action: {parsed_output.action_type}, Score: {parsed_output.confidence_score}")
```

### 7.2 Practical Example: Enterprise Multi-Tool Intent Routing dengan Discriminated Unions & Streaming Parsing

File: `action_pipeline.py`

```python
from __future__ import annotations
import json
import os
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, ValidationError, IPvAnyAddress
from openai import OpenAI
import jiter  # Fast JSON parsing library

# =====================================================================
# 1. Advanced Enterprise Schema: Polymorphic Agent Tool Call
# =====================================================================

class QueryDatabaseAction(BaseModel):
    action: Literal["database_query"] = "database_query"
    query_string: str = Field(..., min_length=10, description="Ekspresi SQL read-only.")
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    read_replica: bool = Field(default=True)

class ProvisionServerAction(BaseModel):
    action: Literal["provision_server"] = "provision_server"
    hostname: str = Field(..., pattern=r"^[a-z0-9-]+(\.[a-z0-9-]+)*$")
    datacenter: Literal["us-east-1", "eu-central-1", "ap-southeast-1"]
    ip_reservation: IPvAnyAddress
    allocated_ram_gb: int = Field(..., ge=4, le=512)

class SecurityAuditAction(BaseModel):
    action: Literal["security_audit"] = "security_audit"
    target_arn: str = Field(..., pattern=r"^arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]{12}:.+$")
    depth_level: Literal["surface", "standard", "exhaustive"]
    notify_ops: bool = True

# Polymorphic Discriminated Union
AgentActionUnion = Annotated[
    Union[QueryDatabaseAction, ProvisionServerAction, SecurityAuditAction],
    Field(discriminator="action")
]

class AgentExecutionPlan(BaseModel):
    plan_id: str = Field(..., description="UUID unik rencana eksekusi.")
    rationale: str = Field(..., min_length=20, description="Penalaran teknis arsitektural.")
    execution_graph: list[AgentActionUnion] = Field(..., min_items=1)

# =====================================================================
# 2. Execution Pipeline with Self-Healing Fallback Strategy
# =====================================================================

class DeterministicActionPipeline:
    def __init__(self, api_key: str | None = None):
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = "gpt-4o"

    def execute_plan_generation(self, user_intent: str, max_retries: int = 2) -> AgentExecutionPlan:
        system_prompt = (
            "Anda adalah Enterprise Infrastructure Controller Agent. "
            "Anda WAJIB menghasilkan execution plan terstruktur dengan validasi sintaks mutlak. "
            "Gunakan discriminator 'action' secara presisi."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_intent}
        ]

        for attempt in range(max_retries + 1):
            try:
                # Menggunakan native strict response format OpenAI (Constrained Decoding)
                completion = self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=messages,
                    response_format=AgentExecutionPlan,
                    temperature=0.1,  # Reduksi entropi decoding
                )
                
                plan: AgentExecutionPlan = completion.choices[0].message.parsed
                if completion.choices[0].message.refusal:
                    raise PermissionError(f"Model menolak eksekusi: {completion.choices[0].message.refusal}")
                
                return plan

            except (ValidationError, Exception) as exc:
                if attempt == max_retries:
                    raise RuntimeError(f"Gagal menghasilkan schema valid setelah {max_retries} perbaikan. Error: {str(exc)}") from exc
                
                # Dynamic Self-Healing Loop: Masukkan error validasi kembali ke context window
                messages.append({
                    "role": "assistant",
                    "content": completion.choices[0].message.content if 'completion' in locals() else "{}"
                })
                messages.append({
                    "role": "user",
                    "content": f"[RUNTIME_SCHEMA_ERROR] Output Anda gagal divalidasi dengan error:\n{str(exc)}\nPerbaiki JSON secara instan sesuai schema."
                })

    def stream_and_parse_incremental(self, user_intent: str):
        """
        Streaming parsial untuk latency optimization menggunakan Jiter
        """
        response_stream = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Hasilkan AgentExecutionPlan JSON murni tanpa markdown wrapper."},
                {"role": "user", "content": user_intent}
            ],
            response_format={"type": "json_object"},
            stream=True
        )

        accumulated_chunks = []
        print("[Streaming Chunk Tokens]:", end=" ", flush=True)

        for chunk in response_stream:
            content = chunk.choices[0].delta.content
            if content:
                print(content, end="", flush=True)
                accumulated_chunks.append(content)
        
        print("\n[Stream Complete] Memulai Deep Validation...")
        full_json = "".join(accumulated_chunks)
        
        # Validasi parsial menggunakan Jiter untuk parsing kecepatan tinggi (Rust core)
        parsed_raw = jiter.from_json(full_json.encode('utf-8'))
        validated_plan = AgentExecutionPlan.model_validate(parsed_raw)
        return validated_plan

if __name__ == "__main__":
    pipeline = DeterministicActionPipeline()
    sample_request = (
        "Infrastruktur kita down di database analitik! Siapkan server baru di Singapore (ap-southeast-1) "
        "dengan IP 192.168.10.45 dan RAM 64GB, lalu jalankan read-only query "
        "'SELECT status, latency FROM cluster_nodes WHERE healthy = false;' untuk inspeksi. "
        "ID Plan: arch-exec-88912"
    )
    
    print("\n--- Testing Strict Parsing ---")
    result = pipeline.execute_plan_generation(sample_request)
    print(f"Generated Plan ID: {result.plan_id}")
    for idx, act in enumerate(result.execution_graph, start=1):
        print(f"  Step {idx}: Action Type = {act.action} -> Payload: {act.model_dump()}")
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Financial Transaction Extraction & Multi-Action Reconciliation Engine
* **Perusahaan**: Multinasional Payment Gateway (Fintech Core System).
* **Volume**: ~250.000 transaksi non-standar/dokumen bukti transfer harian dari 8 negara.
* **Tantangan**: Model awal menggunakan format prompt standar menghasilkan 4.2% *parsing failure* (JSON rusak, tanggal bervariasi format, nilai nominal `string` versus `float`). Error 4.2% tersebut membebani 10.500 transaksi per hari yang terlempar ke tim review manual, menyebabkan *operational backlog* hingga 18 jam.

### Solusi Arsitektural:
1. **Schema Centralization**: Membuat dynamic registry berbasis Pydantic V2 dengan batasan ISO 4217 currency, dynamic currency scaling, dan nested audit trace.
2. **Local Grammar Engine Transition**: Mengalihkan proses decoding pada cluster inferensi internal (`vLLM` engine) dengan CFG Grammar Enforcement melalui `Outlines`.
3. **Double Verification Barrier**:
   * *Barrier 1 (Logit Level)*: Engine menolak pembentukan token di luar regex format tanggal RFC 3339 dan decimal numbers.
   * *Barrier 2 (Semantic Business Validator)*: Schema memverifikasi balance: $\sum Debit - \sum Credit = 0$ via Pydantic model validator.

### Hasil Metrik:
* **Syntax Parsing Errors**: Dari **4.2%** turun menjadi **0.000%** (Nol mutlak kegagalan sintaks).
* **Semantic Error Drops**: Turun dari **1.8%** ke **0.04%** (ditangani oleh reflection retry loop otomatis).
* **Manual Review Queue**: Terpangkas sebesar **93%**, menghemat $1.4M operating cost per tahun.
* **Throughput Multiplier**: Latency per inferensi turun 140ms karena model tidak lagi mengekspresikan token naratif pembuka (*"Sure, here is your JSON:"*).

---

## 9. Trade-offs: Performance, Latency, Scalability, Cost

```
               [ Grammar Constraint Level ]
                     ▲
                     │
      High           │        ● Outlines / CFG (Zero Syntax Error, High TTFT Prep)
  Deterministic      │
  Reliability        │                  ● Native API Strict (Optimized balanced)
                     │
      Low            │  ● Prompting Only (Fast TTFT, High Error Rate/Cost Retry)
                     └────────────────────────────────────────►
                      Low                                High
                               Latency & Memory Overhead
```

### 1. Latensi & First-Token Overhead (TTFT)
* **Konsekuensi**: Mengompilasi JSON Schema besar (terutama nested schemas lebih dari 4 level kedalaman atau regex kompleks) menjadi CFG/FSM membutuhkan kompilasi awal.
* **Dampak**: Peningkatan drastis pada *Time-To-First-Token* (TTFT) pada token pertama jika grammar tidak di-cache oleh inference server.

### 2. GPU Memory Footprint
* **Konsekuensi**: Logit mask computation mengharuskan alokasi state index matrix per active request di VRAM.
* **Dampak**: Menurunkan konkurensi (batch size) server inferensi lokal (`vLLM`) sekitar 10–25% dibandingkan decoding bebas (*unconstrained*).

### 3. Provider Vendor Lock-in vs. Local Deployment
* **OpenAI Strict Mode**: Cepat dan minim pemeliharaan, namun memiliki restriksi JSON Schema subset (misal: tidak mendukung `patternProperties`, `default` values opsional diabaikan dan semua field wajib masuk list `required`).
* **Self-Hosted CFG Engine (Outlines/vLLM)**: Fleksibilitas 100% pada semua grammar, tetapi tim wajib mengelola resource VRAM dan infrastruktur compiler state machine sendiri.

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Kesalahan Fatal: Mengabaikan Seluruh Field sebagai `Required` pada OpenAI Strict Mode
* **Gejala**: API mengembalikan error `400 Invalid schema for response_format: 'strict' mode requires all fields to be listed in 'required'`.
* **Solusi**: Pada Pydantic, gunakan `Optional[T] = None` dengan konfigurasi serializer yang tetap memasukkan field ke dalam list `required`, namun dengan tipe schema union `[T, "null"]`.

### 10.2 Explosive Enum Memory Bottleneck
* **Gejala**: Mendefinisikan `Enum` dengan ribuan anggota (misalnya: database kode pos seluruh negara bagian) ke dalam Pydantic model menyebabkan latency kompilasi grammar melonjak > 10 detik atau OOM crash.
* **Troubleshooting**: Jangan gunakan Enum statis raksasa dalam schema LLM. Gunakan type string generik dengan validasi downstream via Tool/Vector Database lookup pasca-generasi.

### 10.3 Infinite Reflection Repair Loop
* **Gejala**: Pipeline agen terus melakukan looping perbaikan saat menghadapi logical error, menghabiskan token budget tanpa henti.
* **Solusi**: Implementasikan `Max Retry Limit` tegas (maksimal 2x) dan *circuit breaker* yang melempar exception ke antrean dead-letter (DLQ) untuk inspeksi manual.

---

## 11. Best Practices: Production Checklist

- [ ] **Schema Versioning**: Terapkan semantic versioning pada setiap model schema (contoh: `PaymentPlanSchema_v2_1`).
- [ ] **Strict Flag Enforcement**: Selalu aktifkan parameter `strict: True` jika memanggil API penyedia model.
- [ ] **No Default Dropping**: Pastikan `BaseModel` menggunakan `extra = "forbid"` untuk mencegah model menginjeksi arbitrary keys tak terdaftar (*hallucinated attributes*).
- [ ] **Pre-Compile Grammars**: Jika menggunakan self-hosted inference engine, lakukan pre-compile FSM/CFG saat *cold boot* server worker, jangan kompilasi di setiap request.
- [ ] **Streaming Parser Resiliency**: Gunakan event-based stream parsing (seperti `ijson` atau `jiter`) untuk ekstraksi field awal sebelum seluruh payload selesai di-decode.
- [ ] **Semantic Guardrails**: Jangan limpahkan validasi kriptografis/matematis (hashing, checksum, UUID generation) ke LLM. Validasi tersebut adalah tanggung jawab kode deterministik Python di layer post-decoding.

---

## 12. Hands-on Practice

Target path direktori: `hands-on/m02/`

### File Structure:
```
hands-on/m02/
├── .env.example
├── pyproject.toml
├── main.py
├── schemas/
│   ├── __init__.py
│   └── agent_protocol.py
└── engine/
    ├── __init__.py
    ├── parser.py
    └── validator.py
```

### Langkah 1: Setup Environment & Dependencies
```bash
mkdir -p hands-on/m02/schemas hands-on/m02/engine
cd hands-on/m02
python3 -m venv .venv
source .venv/bin/activate
pip install pydantic==2.7.4 openai==1.35.3 jiter==0.4.2 python-dotenv==1.0.1
```

### Langkah 2: Buat Schema Protokol (`schemas/agent_protocol.py`)
```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, ConfigDict

class BaseAgentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class ComputeTask(BaseAgentSchema):
    kind: Literal["compute"] = "compute"
    algorithm: Literal["linear_regression", "kmeans", "pca"]
    dataset_uri: str = Field(..., pattern=r"^s3://[a-zA-Z0-9.\-_/]+$")
    worker_nodes: int = Field(default=2, ge=1, le=32)

class NotificationTask(BaseAgentSchema):
    kind: Literal["notify"] = "notify"
    channel: Literal["slack", "email", "pagerduty"]
    target: str = Field(..., min_length=3)
    message_body: str = Field(..., max_length=500)

TaskPayload = Annotated[
    Union[ComputeTask, NotificationTask],
    Field(discriminator="kind")
]

class MasterExecutionManifest(BaseAgentSchema):
    manifest_id: str = Field(..., min_length=8)
    tasks: list[TaskPayload] = Field(..., min_items=1)
```

### Langkah 3: Eksekusi Pipeline Validator (`main.py`)
```python
import os
from dotenv import load_dotenv
from openai import OpenAI
from schemas.agent_protocol import MasterExecutionManifest

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

user_prompt = """
Jalankan analisis klaster data pengguna yang berada di s3://analytics-bucket/v2/users.parquet
menggunakan metode kmeans pada 4 worker nodes.
Jika selesai, beri tahu tim melalui Slack di channel '#data-engineering-ops' dengan pesan 'Clustering Selesai'.
Manifest ID harus diset ke 'run-job-2024-alpha'.
"""

def run():
    print("[*] Mengirim payload ke OpenAI dengan Strict Constrained Decoding...")
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a cloud scheduler orchestration agent."},
            {"role": "user", "content": user_prompt}
        ],
        response_format=MasterExecutionManifest
    )
    
    manifest = completion.choices[0].message.parsed
    print("\n[+] Manifest Berhasil Diterima & Terverifikasi Deterministik:")
    print(manifest.model_dump_json(indent=2))

if __name__ == "__main__":
    run()
```

---

## 13. Exercise

### Level Easy
Modifikasi skema `ComputeTask` di hands-on untuk menyertakan atribut opsional `max_cost_limit_usd` (tipe `float`, rentang 1.0 hingga 100.0). Pastikan skema tetap mematuhi aturan strict parsing Pydantic v2.

### Level Medium
Bangun *custom Pydantic model validator* pada level model `MasterExecutionManifest` yang memastikan: jika sebuah task bertipe `ComputeTask` dengan parameter `worker_nodes > 8` ada di dalam daftar, maka harus ada task berikutnya bertipe `NotificationTask` dengan channel `pagerduty`. Jika aturan ini dilanggar, Pydantic wajib melempar validation error semantik.

### Level Hard
Implementasikan generator fungsi Python mandiri yang mampu membaca *abstract syntax tree* (AST) dari sebuah class Pydantic dan mengompilasinya menjadi ekspresi Regular Expression non-rekursif tingkat tinggi (Subset Regex) yang kompatibel dengan format grammar logit-masking engine (`llama.cpp` GBNF atau vLLM custom logits processor).

---

## 14. Challenge: The Zero-Fault Core Banking Reconciliation Agent

### Skenario:
Sebuah bank digital memproses rekonsiliasi data dari legacy file dump (format teks acak, semi-terstruktur, mixed character encodings). Anda diminta merancang arsitektur sistem agen autonomus yang mengekstrak mutasi debit, mutasi kredit, metadata referensi audit, dan secara bersamaan memvalidasi integrasi ledger.

### Spesifikasi Kebutuhan:
1. **Zero Data Corruption**: Sistem dilarang keras mengembalikan payload JSON parsial atau memiliki tipe data string numerik tanpa skala desimal presisi (`Decimal(18, 4)`).
2. **Schema Switching Dinamis**: Agen harus secara otomatis mengubah output grammar berdasarkan jenis transaksi yang terdeteksi di teks:
   * SWIFT Wire Transfer
   * Domestic Clearing / RTGS
   * Internal Ledger Transfer
3. **Resilience & Fallback Engine**: Jika API utama model mengalami penurunan kapasitas (rate limit/latency spike), sistem harus otomatis mengalihkan streaming ke Local LLM Engine (`vLLM` on-premise) yang menjalankan model quantized 8-bit, dengan grammar masking yang identik 100% tanpa perbedaan satu karakter pun pada struktur respons.

### Ekspektasi Pengiriman Solusi:
Dokumen arsitektur lengkap beserta implementasi modul Python yang mencakup implementasi Pydantic Schema, skrip konversi dynamic schema ke CFG grammar format, adapter fallback runtime, dan unit test validasi error injection.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. Apa penyebab utama pendekatan prompting biasa ("Output strictly as JSON") sering gagal pada beban kerja enterprise?  
   A. Prompting biasa menggunakan token limit yang terlalu rendah.  
   B. Output tetap diproses melalui sampling probabilistik tanpa batasan grammar mekanis di tingkat Softmax decoding.  
   C. Model LLM tidak dilatih membaca sintaksis kurung kurawal `{}`.  
   D. JSON Schema secara otomatis memutus koneksi API.

2. Pada level arsitektur internal LLM, apa yang dilakukan oleh engine constrained decoding terhadap token yang melanggar aturan JSON pada time-step tertentu?  
   A. Menghapus token tersebut setelah seluruh kalimat di-generate.  
   B. Mengubah logits token terlarang menjadi $-\infty$ sebelum Softmax dieksekusi.  
   C. Memperbaiki token secara otomatis menggunakan prompt tersembunyi.  
   D. Memotong token output secara instan (*early termination*).

3. Atribut konfigurasi Pydantic V2 apa yang wajib didefinisikan untuk mencegah model LLM menginjeksi field tak dikenal (*arbitrary hallucinated keys*)?  
   A. `model_config = ConfigDict(allow_mutation=False)`  
   B. `model_config = ConfigDict(extra="forbid")`  
   C. `model_config = ConfigDict(frozen=True)`  
   D. `model_config = ConfigDict(validate_assignment=False)`

4. Apa peran utama *discriminator* pada Pydantic Discriminated Union dalam konteks AI Agents?  
   A. Menghapus field duplikat secara otomatis saat serialisasi data.  
   B. Memberikan tag eksplisit (misal: `action: Literal["execute_sql"]`) agar validator dapat menentukan model schema turunan secara deterministik dan cepat.  
   C. Mengonversi tipe data numerik menjadi representasi string biner.  
   D. Menjalankan enkripsi data sensitif secara transparan di memori.

5. Manakah karakteristik yang **TIDAK** didukung oleh OpenAI Strict Structured Outputs?  
   A. `pattern` (Regex matching sederhana).  
   B. `enum` berbasis String.  
   C. `default` parameter opsional yang tidak masuk dalam list properti `required`.  
   D. Nested `BaseModel` objek bersarang.

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Teknis)

6. Apa trade-off performa paling dominan dari implementasi *Context-Free Grammar* (CFG) constrained decoding lokal dibanding sampling biasa?  
   A. Mengurangi pemakaian VRAM hingga 50%.  
   B. Meningkatkan *Time-To-First-Token* (TTFT) akibat kebutuhan kompilasi FSM grammar dan komputasi masking di vocabulary matrix.  
   C. Mengurangi keakuratan nalar (*reasoning capabilities*) agen secara dramatis.  
   D. Mengharuskan model dilatih ulang (*fine-tuning*) dari nol.

7. Perhatikan potongan schema berikut:
   ```python
   class AgentState(BaseModel):
       task_id: str
       sub_tasks: list[AgentState] = []
   ```
   Tantangan arsitektur apa yang terjadi jika schema rekursif di atas dikompilasi ke engine strict constrained decoding primitif?  
   A. Engine mengalami *stack overflow* atau infinite loop pada saat pembuatan tabel transisi FSM jika tidak dibatasi kedalaman (*depth-limit*)-nya.  
   B. Pydantic V2 tidak mendukung schema rekursif.  
   C. Output JSON akan selalu bernilai `null`.  
   D. Model LLM akan otomatis mematikan token generation.

8. Mengapa library parsing cepat berbasis stream seperti `jiter` atau `ijson` lebih direkomendasikan daripada `json.loads` bawaan Python pada arsitektur agen streaming?  
   A. `json.loads` mengonsumsi memori GPU secara langsung.  
   B. `json.loads` hanya bisa membaca file dari disk lokal, bukan dari network.  
   C. Parsing stream memungkinkan ekstraksi field secara parsial/inkremental dari buffer token sebelum seluruh payload selesai diunduh, memangkas *perceived latency*.  
   D. `json.loads` tidak kompatibel dengan Python 3.11+.

9. Ketika model mengembalikan error validasi semantik (misal: *target IP subnet tidak terdaftar di VPC*), strategi penanganan error agen modern yang paling efisien adalah:  
   A. Memulai thread percakapan baru (*cold restart*) dan mengulang instruksi dari awal.  
   B. Menyuntikkan metadata error validasi spesifik ke turn percakapan berikutnya sebagai mekanisme *reflection self-healing loop*.  
   C. Mengabaikan error tersebut dan membiarkan sistem mengeksekusi payload apa adanya.  
   D. Mengurangi parameter temperature menjadi 0.0 dan mengirimkan prompt yang sama persis tanpa modifikasi.

10. Bagaimana cara penanganan struktur data Polymorphic Union pada schema OpenAI Strict Mode yang menolak `Union` tanpa tag yang jelas?  
    A. Mengonversi semua field union menjadi tipe data `Any`.  
    B. Menggunakan model flat tunggal dengan semua kemungkinan field ditandai opsional (`Optional[T] = None`).  
    C. Menggunakan `Annotated[Union[...], Field(discriminator="field_name")]` di mana setiap anggota union memiliki nilai literal pembeda yang unik.  
    D. Membagi API call menjadi 10 call terpisah untuk setiap kemungkinan tipe data.

---

### Bagian 3: Skenario Kasus Produksi (Analisis Arsitektur)

11. **Kasus 1**: Sistem agen Anda menggunakan OpenAI `beta.chat.completions.parse` dengan model ketat. Tiba-tiba di production muncul error HTTP 400: *"Invalid schema: string pattern is too complex"*.  
    *Tugas Analisis*: Jelaskan akar penyebab masalah ini dari perspektif compiler grammar internal penyedia dan bagaimana solusi arsitektural untuk mengatasinya tanpa mengurangi validitas format data akhir!

12. **Kasus 2**: Sebuah klaster inferensi lokal menggunakan engine `vLLM` dengan 4x GPU NVIDIA A100. Tim Anda menerapkan constrained decoding grammar untuk memvalidasi output agen. Saat traffic naik ke 200 concurrency requests, sistem mengalami degradasi throughput hingga 70% dan latensi per request melonjak.  
    *Tugas Analisis*: Analisis komponen mana di inferensi engine yang menjadi bottleneck, dan arsitektur mitigasi apa yang wajib diterapkan pada layer API Gateway dan Grammar Caching!

13. **Kasus 3**: Anda membangun sistem agen autonomous execution yang mengeksekusi transaksi perbankan. Model output berhasil lolos 100% validasi sintaksis JSON Schema, namun agen melakukan transfer uang sebesar $10.000.000 ke rekening yang tidak memiliki saldo mencukupi di basis data.  
    *Tugas Analisis*: Evaluasi mengapa JSON Schema Constrained Decoding saja tidak cukup untuk keamanan agen otonom tingkat tinggi (*Defense-in-Depth*), dan rancang arsitektur validasi berlapis yang seharusnya diterapkan!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1
1. **B** — Output pada prompting biasa bergantung pada sampling probabilistik normal. Jika distribusi logits memunculkan token rusak, tidak ada batasan mekanis yang menahannya.
2. **B** — Constrained decoding melakukan manipulasi masking logits secara langsung sebelum fase softmax, memberi nilai $-\infty$ ke token ilegal.
3. **B** — `extra="forbid"` secara eksplisit melarang field di luar deklarasi schema masuk ke parsing pipeline.
4. **B** — Tag literal discriminator memandu validator secara deterministik ke kelas schema tujuan tanpa ambiguitas parsing.
5. **C** — OpenAI strict mode mewajibkan semua properti terdaftar dalam array `required`; field opsional harus dimodelkan sebagai Union tipe dengan tipe `null`.

#### Bagian 2
6. **B** — State tracking dan logit masking per token menambah beban komputasi inference loop, secara khusus berdampak pada TTFT dan inter-token latency.
7. **A** — Definisi grammar rekursif tak terbatas menghasilkan ruang status automata yang tak terhingga (*infinite DFA expansion*) jika tidak ada batasan kedalaman rekursi.
8. **C** — Stream parser memecah JSON per token secara lexer-level, memungkinkan sistem backend membaca aksi pertama saat LLM masih men-generate aksi ketiga.
9. **B** — Reflection loop menyuplai konteks kegagalan secara granular kepada model sehingga ia dapat memodifikasi field yang salah tanpa kehilangan konteks sebelumnya.
10. **C** — Pydantic discriminated union dengan tag literal adalah standar resmi untuk serialisasi polymorphic types pada JSON Schema modern.

#### Bagian 3 (Panduan Jawaban Kasus)
11. **Solusi Analisis Kasus 1**:  
    *Akar Masalah*: Engine penyedia API mengompilasi regex ke FSM/DFA pada hardware inferensi. Regex yang memiliki fitur *backtracking*, nested quantifiers, atau lookaround assertions memerlukan memori dan waktu kompilasi eksponensial, sehingga engine menolaknya demi stabilitas.  
    *Solusi*: Sederhanakan regex di level JSON Schema menjadi pola regex dasar (Deterministic Finite Automata-friendly, misal: ganti lookahead dengan format pattern linear). Pindahkan validasi regex kompleks ke level Pydantic `@field_validator` di aplikasi lokal pasca LLM menghasilkan output string tersebut.
12. **Solusi Analisis Kasus 2**:  
    *Akar Masalah*: Kompilasi FSM grammar yang berulang di CPU/GPU untuk setiap request konkuren memicu *CPU serialization lock* dan kehabisan alokasi thread. Logit processor masking pada vocabulary besar (32k–128k tokens) membebani memory bandwidth saat batch size tinggi.  
    *Solusi*:
    *   Terapkan **Grammar Compilation Caching**: Simpan FSM yang sudah terkompilasi dalam LRU memory cache global berdasarkan hash schema.
    *   Kelompokkan batch request dengan schema grammar yang sama (*Grammar-Aware Batching*).
    *   Offload validasi sebagian ke *speculative decoding* berbasis draft model kecil jika schema sangat restriktif.
13. **Solusi Analisis Kasus 3**:  
    *Akar Masalah*: *Confusing Syntax with Semantics*. JSON Schema hanya menjamin **integritas bentuk data** (misal: `amount` adalah float dan `account_id` adalah string), bukan **kebenaran logika domain atau state dunia nyata**.  
    *Solusi Defense-in-Depth*: Terapkan arsitektur validasi berlapis:
    *   *Layer 1 (Syntactic & Type Enforcement)*: Constrained Decoding (JSON Schema/Pydantic).
    *   *Layer 2 (State & Relational Assertion)*: Determinisitic Policy Engine (misal: OPA - Open Policy Agent) yang memverifikasi database ledger apakah balance $\ge$ amount.
    *   *Layer 3 (Human-in-the-Loop / Multi-Sig Guardrail)*: Triger manual approval jika nilai transaksi melebihi batas toleransi tertentu (misal: > $50.000).

---

## 16. Summary

* **Constrained Decoding** mengubah paradigma manipulasi output LLM dari "berdoa berbasis prompt" menjadi "garansi deterministik matematis" dengan memanipulasi logits secara real-time via automata grammar (CFG/FSM).
* **Pydantic V2** adalah standar industri rekayasa schema Python, yang menyediakan fitur esensial seperti Discriminated Unions untuk perutean aksi multi-alat yang aman dan efisien.
* **Performa vs Keandalan**: Terdapat trade-off nyata pada *Time-To-First-Token* dan pemakaian resource inferensi, yang wajib diatasi melalui caching grammar, streaming parsing (`jiter`), dan simplifikasi regex.
* **Integritas Sistem Agen**: Keberhasilan sistem agen tingkat enterprise menuntut strategi *Defense-in-Depth*—mengombinasikan constrained decoding di level token dengan validasi bisnis semantik deterministik dan arsitektur self-healing loop yang terukur.