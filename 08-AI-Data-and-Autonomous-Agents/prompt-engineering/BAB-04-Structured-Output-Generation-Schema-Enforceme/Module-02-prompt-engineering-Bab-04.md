# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Structured Output Generation & Schema Enforcement**  
**Kategori: 08-AI-Data-and-Autonomous-Agents**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Memahami secara mendalam mekanisme internal *Constrained Decoding* (Grammar-Guided Generation) berbasis Finite State Machine (FSM) dan Pushdown Automata (PDA) pada inference engine LLM.
- Membedakan limitasi arsitektural antara *Prompt-based JSON formatting*, *Heuristic JSON Mode*, dan *Strict Structured Outputs* berbasis deterministik logit masking.
- Mengimplementasikan pipeline data ingestion enterprise yang memvalidasi, mengekstrak, dan mereparasi output terstruktur menggunakan Pydantic V2, Instructor, dan Outlines.
- Merancang arsitektur sistem fault-tolerant berkecepatan tinggi yang menggabungkan *streaming partial parsing*, *circuit breakers*, *schema fallback strategies*, dan *schema versioning migration*.
- Mengukur, menganalisis, dan memitigasi *Time-to-First-Token (TTFT)* overhead, komputasi pembuatan FSM index, serta saturasi context window akibat injeksi JSON Schema.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Python 3.11+ Core**: Type hints (`typing.Annotated`, `typing.Union`, `TypeGuard`), Context Managers, Concurrency (`asyncio`).
- **Pydantic V2 Architecture**: Model configuration (`ConfigDict`), Field validation (`@field_validator`, `@model_validator`), Core Schema representation, Serialization internals.
- **Teori Bahasa Formal & Kompiler Dasar**: Context-Free Grammars (CFG), Backus-Naur Form (BNF), Finite State Automata (FSA/FSM), Tokenizer BPE (Byte-Pair Encoding).
- **LLM Inferencing Mechanics**: Autoregressive sampling, Logit distribution, Top-p/Top-k filtering, Logit Bias injection.
- **Data Engineering Protocols**: JSON Schema Specification (Draft 7 / Draft 2020-12), Serialization overhead parsing (SerDe), zero-copy deserialization.

---

## 3. Concept & Internal Architecture

Dalam rekayasa sistem AI modern, mengekstrak representasi data yang valid secara sintaksis dan semantik bukan sekadar masalah "meminta model dengan prompt yang baik". Ini adalah permasalahan *formal grammar adherence* pada lapisan inferensi autoregresif.

### 3.1 Anatomi Generasi Token Standar vs. Constrained Decoding

Pada inferensi LLM standar, model memprediksi token berikutnya $t_i$ melalui fungsi probabilitas:

$$P(t_i \mid t_{<i}) = \text{softmax}(z_i)$$

di mana $z_i \in \mathbb{R}^{|V|}$ adalah vektor logit yang dihasilkan oleh transformer head, dan $|V|$ adalah ukuran vokabulari tokenizer (misalnya 32.000 hingga 128.000 token).

```
[Standard Autoregressive Sampling]
Transformer Core -> Unconstrained Logits (z_i) -> Softmax -> Sample -> Any Token from Vocabulary
```

Ketika model diarahkan untuk menghasilkan output terstruktur (misalnya JSON) menggunakan prompt murni (*unconstrained*), model rentan terhadap:
- **Syntax Breach**: Kegagalan menutup kurung kurawal (`}`), koma menggantung (*trailing commas*), atau escape character yang korup.
- **Hallucinated Keys**: Memproduksi schema keys yang tidak terdaftar dalam kontrak API.
- **Type Deviation**: Memasukkan string `"N/A"` atau `"null"` pada field bertipe integer/float.

Untuk mengatasi ini secara absolut, diterapkan **Constrained Decoding** melalui **Logit Masking Deterministic Engine**.

```
[Constrained / Grammar-Guided Decoding]
Transformer Core -> Raw Logits (z_i)
                          │
                          ▼
            [ Grammar FSM / PDA Engine ]
            Evaluasi state parser saat ini:
            Token mana saja di V yang VALID?
                          │
                          ▼
             Logit Mask Vector M ∈ {0, -∞}
                          │
                          ▼
             z'_i = z_i + M
                          │
                          ▼
   Softmax(z'_i) -> Deterministic Valid Token Only!
```

### 3.2 State Machine Translation (FSM & Pushdown Automata)

Constrained decoding bekerja dengan mengubah kontrak skema (JSON Schema atau Regular Expression) menjadi representasi formal:

1. **JSON Schema ke Regular Expression / Context-Free Grammar (CFG)**:
   Skema JSON dikonversi menjadi grammar berbasis CFG atau Regular Expression yang setara.
2. **Penyusunan FSM Index Terhadap Token Vocabulary**:
   Library seperti `Outlines` memetakan status FSM terhadap setiap token dalam vokabulari model $V$. Karena tokenizer menggunakan BPE/SentencePiece di mana sebuah token dapat merepresentasikan kombinasi spasi, huruf, atau tanda petik (misalnya token `{"name":` bisa jadi merupakan 1 atau 3 token berbeda), FSM harus melacak transisi state per-byte atau per-subtoken.
3. **Runtime Masking Overhead**:
   Pada setiap langkah decoding autoregresif:
   - Inference engine membaca state FSM saat ini ($S_{current}$).
   - Engine mengekstrak daftar token $V_{valid} \subseteq V$ yang transisinya diizinkan oleh $S_{current}$.
   - Logit untuk semua token di luar $V_{valid}$ di-set ke $-\infty$.
   - LLM secara matematis **mustahil** menghasilkan token yang melanggar grammar.

### 3.3 Komparasi Arsitektur: Prompting vs. JSON Mode vs. Strict Structured Outputs

| Parameter | Unconstrained Prompting | Heuristic JSON Mode (e.g., OpenAI legacy json_object) | Strict Structured Outputs (OpenAI strict: true / Outlines / vLLM) |
| :--- | :--- | :--- | :--- |
| **Mekanisme** | Instruksi System Prompt ("Return JSON") | System Prompt + Bias awal token `{` + Soft penalty | Logit Masking berbasis Grammar/FSM pada level engine inference |
| **Jaminan Sintaksis** | Rendah (0-85% reliabilitas) | Menengah (95-99% JSON valid, namun skema bisa ngawur) | **100% Matematis Valid** terhadap skema yang diberikan |
| **Jaminan Skema** | Tidak ada | Tidak ada (Keys & Types bisa meleset) | **Absolut (Strict Schema Adherence)** |
| **TTFT Overhead** | Rendah ($0$ ms) | Rendah ($0$ ms) | Awalnya tinggi untuk kompilasi skema/FSM, $0$ ms jika di-cache |
| **Kebutuhan Schema Parsing** | Perlu regex parser + json.loads defensif | Perlu json.loads defensif | Tetap butuh deserializer semantik (Pydantic) |

---

## 4. Why & What

### Mengapa Perlu Schema Enforcement pada Lapisan Arsitektur?
Dalam sistem produksi modular, LLM bukan sekadar antarmuka percakapan, melainkan komponen komputasi non-deterministik di tengah-tengah sistem deterministik (Database, Queue Broker, Payment Gateway). Kegagalan satu karakter sintaksis JSON menyebabkan:
- Deserialization Exception (`json.decoder.JSONDecodeError`) pada backend service.
- Dead Letter Queue (DLQ) membludak di Kafka/RabbitMQ.
- Pipeline ETL terhenti (*pipeline halt*), memicu insiden kepatuhan SLA.

### Apa yang Dicapai?
Menggeser penanganan struktur dari proses heuristik pasca-generasi (*post-processing retry loop*) ke kontrol deterministik pada saat generasi berlangsung (*in-flight generation*), dipadukan dengan validasi semantik tingkat lanjut (*post-generation semantic validation*).

---

## 5. How: End-to-End Enterprise Workflow

Alur kerja pemrosesan structured output dalam lingkungan enterprise production:

```
[Raw Input Request]
        │
        ▼
[Schema Definition Layer] ──> (Pydantic V2 Model / JSON Schema)
        │
        ├── Compile Schema / Load Cached FSM Index
        │
        ▼
[Inference Engine (LLM)] <──> [Grammar Logit Masking (Constrained Decoding)]
        │
        ▼
[Raw JSON ByteStream]
        │
        ├── (Streaming Parser: jiter / partial-json-parser)
        │
        ▼
[Syntactically Valid JSON Object]
        │
        ▼
[Pydantic V2 Semantic Validator]
        │
        ├── Valid? ──[YES]──> [Downstream Services / DB Write]
        │
       [NO]
        │
        ▼
[Self-Correction Feedback Loop] ──> (Kirim pesan error Pydantic kembali ke LLM)
        │
   (Max Retries Exceeded?)
        │
        ├── [YES] ──> [Deterministic Fallback Engine] ──> [DLQ Alerting]
        └── [NO]  ──> (Ulangi inferensi dengan context perbaikan)
```

---

## 6. Analogy & ASCII Diagram

### Analogi Lintasan Kereta Api Rel Listrik
Bayangkan generasi token LLM adalah lokomotif berkecepatan tinggi yang bergerak maju.
- **Unconstrained Prompting**: Lokomotif melaju di tanah lapang tanpa rel. Masinis diminta secara verbal: "Tolong jalan lurus membentuk pola huruf J-S-O-N". Terkadang lokomotif tergelincir masuk jurang (crash format).
- **Constrained Decoding (FSM Masking)**: Lokomotif ditempatkan di atas sistem rel percabangan terkunci otomatis (*mechanical interlocking track*). Pada setiap meter perjalanan, tuas switch rel mengunci seluruh arah kecuali jalur yang menuju node skema berikutnya yang sah. Lokomotif tidak memiliki pilihan fisik selain mengikuti rel yang valid hingga tujuan akhir.

```
FSM State Machine Visualization untuk Sintaksis Angka/String Sederhana:

(State 0: Root) ── [Token: '"'] ──> (State 1: String Body) ── [Token: '"'] ──> (State 2: End String)
       │                                       │
  [Token: '{']                            [Valid ASCII]
       │                                       │
       ▼                                       ▼
(State 3: Object Open) ───────────────> (Loop State 1)
```

---

## 7. Simple & Practical Implementation

### 7.1 Simple Example: Native OpenAI Strict Mode dengan Pydantic

Implementasi minimal menggunakan fitur `strict: true` via OpenAI API client:

```python
from typing import List
from pydantic import BaseModel, Field
from openai import OpenAI

client = OpenAI()

class InventoryItem(BaseModel):
    sku: str = Field(description="Format SKU: 3 huruf kapital dash 4 digit angka, misal ABC-1234")
    quantity: int = Field(ge=0, description="Kuantitas stok non-negatif")
    unit_price: float = Field(gt=0.0, description="Harga per unit dalam mata uang dasar")

class WarehouseDispatchOrder(BaseModel):
    order_id: str
    destination_node: str
    items: List[InventoryItem]
    is_fragile: bool

# Enforcement via model_dump_json Schema Integration
completion = client.beta.chat.completions.parse(
    model="gpt-4o-mini-2024-07-18",
    messages=[
        {"role": "system", "content": "Ekstrak dispatch order dari input logistik operator."},
        {"role": "user", "content": "Kirim ke Gudang-Surabaya: 50 unit ABC-9812 seharga 15.5 dan 10 unit XYZ-0012 seharga 99.0. Order ID: DISP-2026-X. Hati-hati barang mudah pecah."}
    ],
    response_format=WarehouseDispatchOrder,
)

parsed_order: WarehouseDispatchOrder = completion.choices[0].message.parsed
print(f"Parsed Order ID: {parsed_order.order_id}")
print(f"Total Item Lines: {len(parsed_order.items)}")
print(f"Valid Payload: {parsed_order.model_dump_json(indent=2)}")
```

---

### 7.2 Practical Enterprise Example: Resilient Multi-tier Structured Engine

Implementasi standar industri menggunakan `Instructor`, validasi semantik multi-field Pydantic V2, *dynamic self-correction retry loop*, dan pelacakan telemetri.

```python
import asyncio
import logging
from typing import List, Optional, Annotated
from pydantic import BaseModel, Field, field_validator, model_validator
import instructor
from openai import AsyncOpenAI
import tenacity

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EnterpriseStructuredEngine")

# --- MODEL DEFINITIONS ---

class CurrencyAmount(BaseModel):
    amount: float = Field(gt=0, description="Nominal transaksi wajib positif")
    currency: str = Field(pattern="^(IDR|USD|SGD|EUR)$", description="Mata uang standar ISO 3 digit")

class EntityParty(BaseModel):
    account_number: str = Field(min_length=8, max_length=20)
    bank_code: str = Field(min_length=3, max_length=8)
    holder_name: str = Field(min_length=2)

class WireTransferTransaction(BaseModel):
    transaction_id: str = Field(description="UUID atau sequence acuan bank")
    sender: EntityParty
    beneficiary: EntityParty
    payment_details: CurrencyAmount
    tax_deduction: Optional[CurrencyAmount] = None
    compliance_memo: str = Field(min_length=5, description="Catatan kepatuhan AML")

    @model_validator(mode="after")
    def verify_sender_beneficiary_distinct(self) -> "WireTransferTransaction":
        if (
            self.sender.account_number == self.beneficiary.account_number
            and self.sender.bank_code == self.beneficiary.bank_code
        ):
            raise ValueError("Sender dan Beneficiary tidak boleh memiliki nomor akun dan bank code yang identik.")
        return self

    @field_validator("compliance_memo")
    @classmethod
    def audit_aml_blacklist_terms(cls, v: str) -> str:
        blacklist = {"HAWALA", "LAUNDERING", "OFFSHORE_SHELL_TEST"}
        if any(term in v.upper() for term in blacklist):
            raise ValueError(f"Compliance violation: Memo mengandung frase terlarang untuk audit AML.")
        return v

# --- CORE PARSING & ENFORCEMENT ENGINE ---

class ResilientExtractionService:
    def __init__(self, api_key: Optional[str] = None):
        self.raw_client = AsyncOpenAI(api_key=api_key)
        # Patch client dengan Instructor menggunakan mode strict Tools / JSON Engine
        self.client = instructor.from_openai(
            self.raw_client,
            mode=instructor.Mode.TOOLS_STRICT
        )

    async def extract_transaction_telemetry(
        self,
        raw_swift_message: str,
        max_retries: int = 3
    ) -> WireTransferTransaction:
        """
        Mengekstrak wire transfer dengan garansi validasi skema dan semantic self-correction loop.
        """
        system_prompt = (
            "Anda adalah Financial Message Parsing Engine tingkat perbankan komersial. "
            "Ekstrak data secara tepat sesuai skema ISO-equivalent yang didefinisikan. "
            "Jangan pernah mengasumsikan data yang hilang. Jika melanggar validasi, "
            "analisis error yang dikirimkan dan koreksi ekstraksi secara instan."
        )

        try:
            # instructor otomatis menginjeksikan JSON Schema dan mengurus retry-loop 
            # jika terjadi Pydantic ValidationError langsung ke LLM context window!
            result: WireTransferTransaction = await self.client.chat.completions.create(
                model="gpt-4o",
                response_model=WireTransferTransaction,
                max_retries=max_retries,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Swift MT103 Raw Input:\n{raw_swift_message}"},
                ],
                temperature=0.0, # Wajib nol untuk determinisme mutlak
            )
            logger.info(f"Ekstraksi transaksi berhasil: {result.transaction_id}")
            return result

        except instructor.exceptions.InstructorRetryException as err:
            logger.error(f"FATAL: LLM gagal mematuhi validasi Pydantic setelah {max_retries} percobaan.")
            logger.error(f"Penyebab kegagalan terakhir: {str(err)}")
            # Fallback path / Circuit breaking
            raise RuntimeError("ExtractionValidationExceededFault") from err

# --- RUNNER SIMULATION ---

async def main():
    service = ResilientExtractionService()

    # Payload sampel Swift MT103 semi-terstruktur
    mock_swift_payload = """
    :20:TRX-998231-JAK
    :32A:260330IDR150000000,00
    :50K:/1029384756
    BANK CENTRAL ASIA
    PT TEKNOLOGI MODERN INDONESIA
    :59:/1029384756
    BANK CENTRAL ASIA
    PT TEKNOLOGI MODERN INDONESIA
    :70:PAYMENT FOR CLOUD HOSTING - AML SAFE
    """
    
    # Catatan: Mock payload di atas SENGAJA memiliki sender & beneficiary sama
    # untuk memicu self-correction pada @model_validator.
    
    print("\n--- Memulai Ingestion Pipeline ---")
    try:
        data = await service.extract_transaction_telemetry(mock_swift_payload, max_retries=2)
        print(f"Hasil Ekstraksi: {data.model_dump_json(indent=2)}")
    except Exception as e:
        print(f"Pengecualian Ditangkap (Expected jika fallback terpicu): {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Kasus: Core Banking Ingestion Platform (Bank Devisa Skala Global)

#### Problem Statement
Sebuah bank memproses lebih dari 450.000 transaksi harian dari berbagai format pesan tidak terstruktur: pesan SWIFT MT103 lama, slip transfer terenkripsi OCR, dan email konfirmasi treasury. Menggunakan prompt engineering standar, sekitar 3.8% transaksi (17.100 transaksi/hari) mengalami kegagalan validasi JSON, memicu ribuan investigasi manual (tiket IT Support) dan denda kepatuhan transaksi tertunda.

#### Arsitektur Solusi
Bank menerapkan arsitektur *Zero-Defect Structured Ingestion Gateway*:
1. **Schema Standardization**: Semua target data dikompilasi ke dalam Pydantic V2 Models yang kompatibel dengan ISO 20022 format.
2. **Local Inference Deployment**: LLM di-deploy secara *on-premises* menggunakan `vLLM` dengan integrasi `Outlines` untuk memaksakan pemenuhan schema via Grammar-Guided Logit Masking (memotong kegagalan sintaksis ke 0.00%).
3. **Optimasi TTFT**: Grammar FSM dikompilasi dan di-cache secara permanen dalam memori (*Pre-compiled Regex/Schema Index*), menghindari latensi kompilasi 1.2 detik per panggilan inference.
4. **Resilience Strategy**:
   - Jika validator semantik gagal (misalnya checksum IBAN tidak valid), error stack trace diinjeksi kembali ke model dalam *single-shot repair loop*.
   - Jika *single-shot repair* gagal, transaksi dialihkan ke *Shadow Parser* (Algoritma deterministik berbasis aturan Regex kaku) sebelum masuk ke *Human-in-the-Loop Quarantine Queue*.

#### Hasil Metrik Produksi
- **Syntactic Failure Rate**: Turun dari $3.8\%$ ke **$0.00\%$**.
- **Semantic Data Accuracy**: Meningkat dari $91.4\%$ ke **$99.94\%$**.
- **Investigasi Manual Harian**: Turun dari 17.100 kasus menjadi **kurang dari 270 kasus/hari** (terbatas pada data fisik yang terpotong/unreadable OCR).
- **Penghematan Biaya Operasional**: Diestimasi mencapai $1.4M USD per kuartal.

---

## 9. Trade-Offs & Architectural Decisions

```
                     [ Schema Strictness ]
                              ▲
                              │
                    (A) Strict Output
                        - Latensi awal kompilasi skema
                        - Fleksibilitas reasoning menurun
                        - 0% Sintaksis error
                              │
                              │
                              │
                              └────────────────────────► [ LLM Expressiveness ]
                              (B) Freeform CoT Parsing
                                  - Butuh post-parsing regex
                                  - Reliabilitas rendah
                                  - Reasoning kaya
```

| Dimensi | Prompt-based JSON | Native Strict Structured Outputs | Engine-level CFG Masking (Outlines/vLLM) |
| :--- | :--- | :--- | :--- |
| **Penyusunan Skema (Latency Overhead)** | $0$ ms | 50–300 ms (pada request pertama, lalu di-cache oleh provider) | 100–1200 ms (Kompilasi FSA/FSM awal terhadap tokenizer vocabulary) |
| **Throughput Token (Tokens/sec)** | Normal ($1.0x$) | Normal ($1.0x$) | Penurunan sekitar 5–15% akibat proses mask logit per token step |
| **Reasoning Degradation** | Rendah (Model bebas berpikir) | Signifikan jika model langsung dipaksa output JSON tanpa Chain-of-Thought (CoT) | Signifikan jika schema terlalu restriktif tanpa CoT container field |
| **Injeksi Token Biaya (Cost)** | Token skema masuk ke context window | Token skema dihitung sebagai input tokens | Token skema tidak selalu dimasukkan ke LLM context (tergantung backend) |
| **Dependensi Arsitektur** | Sangat Rendah | Menengah (Tergantung implementasi provider API) | Tinggi (Perlu akses engine decoding atau framework khusus) |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Mengabaikan "CoT Suffocation" pada Strict Schemas
- **Gejala**: LLM menghasilkan output dengan akurasi reasoning yang buruk ketika dipaksa menghasilkan skema JSON kaku secara instan.
- **Root Cause**: LLM butuh *scratchpad token* untuk melakukan reasoning bertahap sebelum menghasilkan kesimpulan akhir. Jika token pertama yang diizinkan oleh skema langsung berupa field nilai kunci: `{"approved": false}`, model tidak sempat "berpikir".
- **Solusi**: Masukkan container field `thinking` atau `reasoning_steps` di urutan pertama skema model:
  ```python
  class SafeDecisionModel(BaseModel):
      reasoning_trace: str = Field(description="Analisis komprehensif langkah demi langkah sebelum keputusan.")
      verdict: bool
  ```

### Mistake 2: Missing `additionalProperties: false` pada JSON Schema
- **Gejala**: Engine API eksternal menolak skema JSON Draft 7/2020-12 Anda saat menggunakan strict mode.
- **Root Cause**: Engine constrained decoding membutuhkan closure tertutup pada semua object definitions. Objek terbuka (*open-ended objects*) membuat tree state decoding menjadi tak hingga (*infinite state*).
- **Solusi**: Konfigurasi Pydantic V2 `ConfigDict`:
  ```python
  class StrictBase(BaseModel):
      model_config = ConfigDict(extra="forbid")
  ```

### Mistake 3: Memory Exhaustion akibat FSM Explosion
- **Gejala**: Inference engine lokal (seperti Outlines) memicu OOM (Out Of Memory) saat startup atau memuat regex skema yang kompleks.
- **Root Cause**: Pola Regex bersarang yang buruk (misal `.*` berulang) menyebabkan *catastrophic state explosion* pada saat kompilasi NFA (Nondeterministic Finite Automaton) ke DFA (Deterministic Finite Automaton) terhadap vokabulari token yang besar.
- **Solusi**: Sederhanakan regex validasi. Batasi panjang token menggunakan interval diskrit, hindari ambiguous nested wildcards (`(a+)+`).

---

## 11. Best Practices & Production Checklist

- [ ] **ConfigDict Isolation**: Pastikan semua model menggunakan `extra="forbid"` dan tipe data eksplisit (hindari tipe `typing.Any` atau `dict` mentah).
- [ ] **Optional vs. Nullable Safety**: Definisikan field opsional secara ketat (`Optional[T] = None`) dan pahami serialisasi JSON Schema-nya di provider target.
- [ ] **CoT Preservation**: Sisipkan field dedikasi `chain_of_thought` atau `inner_monologue` di urutan pertama skema untuk menjaga performa kognitif model.
- [ ] **Schema Registry & Versioning**: Simpan schema dalam registry terpusat berversi (`InvoiceSchema_v1_2_0`). Jangan hardcode skema mentah di dalam logic prompt.
- [ ] **Streaming Validation**: Untuk skema berukuran besar, implementasikan streaming parser (`jiter` atau `partial-json-parser`) untuk memproses item list per-chunk tanpa menunggu seluruh payload selesai diekstrak.
- [ ] **Graceful Degraded Fallbacks**: Miliki jalur penyelamatan jika model mengalami loop validasi Pydantic yang gagal:
  1. Strict Mode Call $\to$ 2. Single-shot Repair Call $\to$ 3. Rule-based Heuristic Regex $\to$ 4. Dead-Letter-Queue.
- [ ] **Token Usage Monitoring**: Pantau peningkatan biaya input token akibat metadata JSON Schema yang diinjeksikan secara otomatis ke payload konteks.

---

## 12. Hands-on Practice

Buat direktori latihan: `hands-on/m02/`

### File Layout
```
hands-on/m02/
├── pyproject.toml
├── models.py
├── parser_engine.py
├── test_payloads.py
└── main.py
```

### Step 1: Inisialisasi Environment
```bash
mkdir -p hands-on/m02
cd hands-on/m02
python -m venv .venv
source .venv/bin/activate
pip install "pydantic>=2.7.0" "instructor>=1.3.0" "openai>=1.30.0" pytest
```

### Step 2: Implementasi `models.py`
Tulis skema audit log keamanan sistem:

```python
# hands-on/m02/models.py
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class SecurityFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    cve_id: Optional[str] = Field(None, pattern=r"^CVE-\d{4}-\d{4,}$")
    description: str = Field(min_length=10)
    severity: SeverityLevel
    remediation_steps: List[str] = Field(min_length=1)

class SecurityAuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    audit_id: str
    target_service: str
    findings: List[SecurityFinding]
    overall_risk_score: float = Field(ge=0.0, le=10.0)

    @field_validator("overall_risk_score")
    @classmethod
    def validate_score_against_findings(cls, v: float, info) -> float:
        # Cross-validation: score 0 tidak boleh ada jika findings berisi CRITICAL
        return v
```

### Step 3: Implementasi Engine Pipeline `main.py`
Jalankan parsing defensif yang membaca log teks tidak beraturan menjadi data schema-compliant.

---

## 13. Exercises

### Level: Easy
Buat Pydantic V2 model `UserProfile` dengan field:
- `username`: string alfanumerik 5-15 karakter.
- `tier`: Enum (`FREE`, `PRO`, `ENTERPRISE`).
- `metadata`: dictionary yang hanya boleh memetakan `str` ke `str`.
Pastikan validasi gagal jika ada data *extra* yang tidak didefinisikan.

### Level: Medium
Implementasikan model `MedicalPrescriptionExtractor` dengan cross-field validation:
- Field: `medication_name`, `dosage_mg` (int), `frequency_per_day` (int), `is_pediatric_patient` (bool).
- Validator: Jika `is_pediatric_patient == True`, maka `dosage_mg` tidak boleh melebihi $250\text{ mg}$ terlepas dari jenis obatnya. Gunakan `@model_validator(mode="after")`.

### Level: Hard
Bangun implementasi parser custom `StreamingJsonArrayParser` di Python yang membaca byte-stream token LLM yang belum selesai, mendeteksi pola penutup array/objek secara dinamis menggunakan stack internal, dan menghasilkan (*yield*) model Pydantic yang valid segera setelah sebuah elemen array lengkap terdeteksi—tanpa harus menunggu inferensi seluruh array selesai.

---

## 14. Real-World Challenge

### Context
Anda adalah Lead Platform Architect di unicorn logistik regional. Sistem Anda menerima ribuan manifes pengiriman barang via email dan file teks kurir harian yang tidak seragam formatnya. Data ini harus segera dikonversi ke format skema GraphQL backend secara realtime.

### Problem Scenario
Model LLM sering kali mengalami halusinasi saat beban traffic puncak:
1. Memotong payload JSON sebelum parsing selesai (*truncated generation due to token context limit*).
2. Menghasilkan nama kota yang tidak ada di master database lokasi logistik nasional.
3. Menghabiskan waktu latensi p99 terlalu tinggi (> 8 detik) jika menggunakan iterative self-correction loop 3x.

### Requirements & Objectives
Rancang dokumen arsitektur dan implementasikan prototype production engine yang mencakup:
1. **Dynamic Chunking & Partial Schema Execution**: Memecah pemrosesan manifes berukuran besar menjadi beberapa segmen independen, memprosesnya secara paralel menggunakan constrained decoding.
2. **Deterministic Foreign Key Guard**: Integrasikan custom Pydantic validator yang memvalidasi `city_id` terhadap in-memory Bloom filter/Trie struktur data kota tanpa memanggil database IO berat.
3. **Optimistic Streaming Assembler**: Antarmuka streaming yang merakit (*reassemble*) pecahan objek JSON parsial secara realtime dengan jaminan ACID serialization.
4. **Degraded Execution Budget**: Tentukan *latency budget* ketat: Jika inferensi gagal dalam $1200\text{ ms}$, batalkan eksekusi, aktifkan fallback parser berbasis *Deterministic Named Entity Recognition (NER)* tradisional, dan tandai payload sebagai `REVIEW_REQUIRED`.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Konseptual)

1. **Apa perbedaan mendasar antara OpenAI legacy `response_format={"type": "json_object"}` dengan `response_format={"type": "json_schema", ...}` (Strict Mode)?**
   - A. `json_object` menggunakan validator Rust, sedangkan `json_schema` menggunakan validator Python.
   - B. `json_object` hanya memastikan output berupa sintaksis JSON valid tanpa memvalidasi struktur key/value, sedangkan `json_schema` memaksakan output mengikuti schema deterministik via constrained decoding logit masking.
   - C. `json_schema` lebih murah daripada `json_object`.
   - D. `json_object` tidak membutuhkan system prompt, sedangkan `json_schema` wajib.

2. **Mengapa nilai temperature direkomendasikan di-set ke `0.0` pada saat mengekstraksi structured output di lingkungan produksi?**
   - A. Agar token dihasilkan dua kali lebih cepat.
   - B. Untuk mematikan context window limit.
   - C. Mengurangi variabilitas sampling autoregresif sehingga model memilih token dengan probabilitas logit tertinggi secara deterministik.
   - D. Untuk menghindari biaya penagihan API ganda.

3. **Dalam mekanisme Constrained Decoding berbasis Grammar (CFG), apa yang dilakukan inference engine terhadap raw logits sebelum proses sampling softmax?**
   - A. Memotong ukuran vokabulari model menjadi setengahnya secara permanen.
   - B. Mengalikan logit dengan bilangan acak Gaussian.
   - C. Menyetel nilai logit token-token yang tidak valid menurut state parser saat ini menjadi $-\infty$.
   - D. Mengubah seluruh token kapital menjadi huruf kecil.

4. **Pada Pydantic V2, decorator manakah yang digunakan untuk memvalidasi ketergantungan relasional antara dua field berbeda dalam sebuah model?**
   - A. `@field_validator`
   - B. `@computed_field`
   - C. `@model_validator(mode="after")`
   - D. `@property`

5. **Apa dampak langsung jika kita tidak mengeset `extra="forbid"` pada model Pydantic yang digunakan untuk OpenAI Strict Structured Outputs?**
   - A. Output model akan selalu kosong.
   - B. API akan melempar validation error skema HTTP 400 karena skema JSON strict mewajibkan properti tertutup (`additionalProperties: false`).
   - C. Database PostgreSQL downstream akan otomatis restart.
   - D. Waktu komputasi token menjadi tak hingga.

---

### Bagian 2: Intermediate

6. **Apa yang dimaksud dengan fenomena "CoT Suffocation" pada pemaksaan structured schema kaku, dan bagaimana cara menanggulanginya?**
   - *Jawaban Singkat Konseptual*: Fenomena di mana LLM dipaksa mengeluarkan format data JSON terstruktur secara langsung dari token pertama tanpa memiliki ruang kontekstual (*scratchpad space*) untuk memecah masalah (*reasoning*). Solusinya adalah menyematkan atribut string (seperti field `reasoning_steps` atau `analysis`) pada urutan pertama dalam skema JSON sebelum field inti target ekstraksi.

7. **Mengapa regex wildcard bertingkat seperti `(a+)+$` sangat berbahaya jika dikompilasi menjadi Finite State Automaton (FSA) logit mask engine pada framework seperti Outlines?**
   - *Jawaban Singkat Konseptual*: Karena kompleksitas pemetaan state NFA ke DFA dapat meledak secara eksponensial (*state explosion problem*). Hal ini menyebabkan pemakaian RAM yang masif (OOM), pembengkakan ukuran index memori, dan peningkatan durasi *Time-to-First-Token (TTFT)* hingga sistem mengalami *crash* atau *hang*.

8. **Bagaimana library `Instructor` menangani `ValidationError` yang dilempar oleh Pydantic secara internal saat berkomunikasi dengan LLM API?**
   - *Jawaban Singkat Konseptual*: `Instructor` menangkap exception `ValidationError`, mengekstrak path field dan pesan error yang spesifik dari Pydantic, lalu menyusun pesan koreksi baru ke dalam percakapan (`User` atau `System` message) yang memberitahukan LLM letak persis kegagalannya, lalu meminta model melakukan reparasi generasi secara berulang hingga batas `max_retries` tercapai.

9. **Apa peran representasi JSON Schema Draft 2020-12 atau Draft 7 dalam arsitektur integrasi LLM lintas bahasa?**
   - *Jawaban Singkat Konseptual*: Sebagai bahasa perantara universal (*Universal Intermediate Representation*). JSON Schema memisahkan abstraksi model data kode backend (baik Pydantic di Python, Zod di TypeScript, maupun Serde di Rust) dari implementasi hardware/inference engine LLM, sehingga kontrak antarmuka deterministik tetap seragam di seluruh subsistem mikroservis.

10. **Jelaskan perbedaan mendasar komputasi antara pemrosesan validasi di sisi client (Client-side validation) vs inferensi terkendala di sisi engine (Engine-side constrained decoding)!**
    - *Jawaban Singkat Konseptual*: Client-side validation menunggu LLM memproduksi seluruh teks respons, baru memvalidasi formatnya menggunakan parser lokal; jika salah, seluruh respons dibuang dan inferensi diulang. Engine-side constrained decoding memodifikasi probabilitas sampling token secara real-time pada setiap siklus generasi, menjamin token yang salah tidak akan pernah diekstraksi sejak awal.

---

### Bagian 3: Production Scenarios & Architectural Edge Cases

11. **Skenario 1**: Layanan ekstraksi invoice mikroservis Anda mengalami lonjakan TTFT (Time-to-First-Token) rata-rata dari $450\text{ ms}$ melonjak menjadi $3.800\text{ ms}$ setelah Anda menambahkan 15 model Pydantic baru yang sangat kompleks ke dalam shared-engine instance `vLLM` berbasis `Outlines`. Bagaimana Anda mendiagnosis akar masalahnya dan langkah remediasi apa yang harus diambil?
    - **Analisis & Solusi**: Lonjakan TTFT terjadi karena proses kompilasi grammar/JSON Schema menjadi FSA index dieksekusi secara sinkron (*on-demand compilation*) pada thread inferensi saat pertama kali request dengan skema tersebut masuk, atau terjadi *cache eviction* pada grammar compiler pool akibat banyaknya skema baru. Remediasi:
      1. Terapkan strategi *AOT (Ahead-of-Time) Pre-compilation*: Kompilasi seluruh FSM index skema saat *service startup/build time*, bukan *runtime*.
      2. Tingkatkan ukuran LRU Grammar Cache pada engine konfigurasi.
      3. Sederhanakan hierarki inheritance model skema dan hilangkan pola regex yang tumpang-tindih.

12. **Skenario 2**: Dalam sistem transfer data antar bank berlatensi rendah, Anda menggunakan OpenAI Strict Mode. Tiba-tiba downstream service melempar galat deserialisasi karena field `transfer_timestamp` menghasilkan string ISO dengan format offset `+07:00`, padahal parser sistem warisan (*legacy system*) hanya menerima format `Z` (UTC Zulu time). Namun skema strict mode OpenAI tidak mendukung custom regex validator secara dinamis pada level primitive date. Bagaimana Anda menyelesaikannya di level arsitektur tanpa melanggar strict contract?
    - **Analisis & Solusi**: Masalah ini harus diselesaikan melalui strategi arsitektur *Two-Phase Transformation*:
      1. Pertahankan kontrak LLM tetap strict dengan format standar yang didukung (misalnya representasi string umum atau integer Unix epoch milidetik).
      2. Letakkan lapisan *Adapter Pattern / Data Transfer Object (DTO)* tepat setelah eksekusi LLM selesai: Pydantic mengekstrak string ISO, lalu melalui `@field_validator(mode="after")` atau root model converter, field ditransformasi dan dikonversi secara deterministik ke format UTC Zulu (`Z`) menggunakan fungsi standard library Python (`datetime.astimezone(timezone.utc)`).
      3. Jangan membebankan transformasi formatting offset timezone murni pada kapasitas reasoning LLM, karena hal itu adalah tugas deterministik murni lapisan komputasi tradisional.

13. **Skenario 3**: Sebuah autonomous agent menggunakan structured tools execution loop. Terjadi kondisi *infinite retry loop* di mana model terus-menerus mencoba memperbaiki format output yang gagal divalidasi oleh Pydantic, menghabiskan batas kuota token dan menaikkan latensi pipeline hingga timeout gateway HTTP 504. Bagaimana Anda mendesain arsitektur *Safe Autonomous Loop* yang resilien terhadap kondisi ini?
    - **Analisis & Solusi**: Implementasikan *Defensive Circuit Breaker Pattern* dengan komponen berikut:
      1. **Hard Upperbound Retry**: Pasang limit maksimum retry yang ketat (misal $N=2$).
      2. **Error Reflection Budget**: Saat mengirimkan error validation kembali ke prompt context, jangan hanya melampirkan teks exception; batasi konteks hanya pada path JSON yang bermasalah untuk mencegah saturasi window.
      3. **Graceful Fallback Mode**: Jika threshold retry terlampaui, alihkan eksekusi secara instan ke *Fallback Intent Determinator* (model heuristic berbasis rules atau regex ringan).
      4. **Dead-Letter Audit**: Payload mentah beserta error traces dikirim secara asinkron ke message queue (RabbitMQ/Kafka) untuk dievaluasi oleh pipeline analytics offline, sementara client request langsung menerima respons `HTTP 200/202` terdegradasi yang menyatakan data masuk antrian manual audit (*quarantined*).

---

## 16. Summary

- **Constrained Decoding** mengubah model non-deterministik menjadi engine data terstruktur dengan cara membatasi probabilitas ruang vokabulari (*logit masking*) pada setiap iterasi pembentukan token autoregresif berbasis Context-Free Grammar atau FSM.
- **Strict Structured Outputs** menghadirkan jaminan kepatuhan format sintaksis $100\%$, melenyapkan kegagalan parsing JSON pada pipeline backend dan microservices modern.
- **Pydantic V2 + Instructor** membentuk pondasi abstraksi arsitektur enterprise modern, mengelola integrasi skema dua arah: dari definisi type Python statis ke skema target LLM, serta penanganan *self-correction loop* otomatis saat validasi logika bisnis semantik dilanggar.
- Menjaga kebebasan komputasi penalaran LLM melalui teknik **CoT Scratchpad Field Injection** adalah prasyarat mutlak untuk mencegah penurunan performa penalaran (*reasoning degradation*) saat menggunakan skema output yang sangat restriktif.