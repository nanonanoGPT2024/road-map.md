# Bab 02: Core Prompt Anatomy & In-Context Learning
**Module 01: Structural Decomposition & In-Context Conditioning**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mendekomposisi Anatomi Prompt Enterprise**: Menganalisis dan merancang komponen modular prompt—*System Instructions, Grounding Context, Few-Shot Demonstrations, User Payload,* dan *Structural Delimiters*—dengan determinisme tinggi.
2. **Menguasai Teori & Mekanisme In-Context Learning (ICL)**: Menjelaskan bagaimana model transformator autoregresif melakukan inferensi task tanpa modifikasi gradien melalui dinamika *activation space* dan *implicit gradient descent*.
3. **Mengoptimalkan Distribusi Bobot Atensi**: Mengatasi degradasi representasi token (*Lost-in-the-Middle* problem) dan bias kontekstual (*recency/primacy bias*) menggunakan penempatan struktural berbasis *Positional Encoding*.
4. **Membangun Dynamic Context Injection Engine**: Mengimplementasikan subsistem produksi berbasis Python 3.11+ yang secara dinamis memilih *exemplar*, mengelola alokasi anggaran token (*token budget*), dan mengonversi representasi data mentah menjadi payload terstruktur yang divalidasi oleh skema Pydantic.
5. **Mengevaluasi Trade-off Paradigma Pembelajaran**: Mengukur parameter performa, latensi, amortisasi biaya, dan fleksibilitas domain antara *Zero-Shot*, *Few-Shot*, *Retrieval-Augmented Generation (RAG)*, dan *Parameter-Efficient Fine-Tuning (PEFT/LoRA)*.

---

## 2. Concept Overview

Sebuah prompt enterprise bukanlah sekadar teks bebas (*unstructured prose*); prompt adalah **antarmuka komputasi tingkat tinggi (*high-level execution interface*)** yang mengondisikan distribusi probabilitas token pada model bahasa besar (*Large Language Model* / LLM).

Secara formal, model autoregresif memodelkan distribusi probabilitas gabungan dari sebuah sekuens token:

$$P(X) = \prod_{i=1}^{n} P(x_i \mid x_1, x_2, \dots, x_{i-1})$$

Ketika kita memberikan prompt $C = (x_1, \dots, x_k)$, kita mengondisikan komputasi sehingga model membangkitkan kelanjutan $Y = (x_{k+1}, \dots, x_{k+m})$ berdasarkan probabilitas kondisional:

$$P(Y \mid C) = \prod_{j=1}^{m} P(x_{k+j} \mid x_1, \dots, x_k, x_{k+1}, \dots, x_{k+j-1})$$

### Anatomi Inti Prompt (Core Prompt Anatomy)
Prompt modular tingkat produksi tersusun atas lima lapisan diskret:

1. **System Persona & Global Invariants**: Mendefinisikan ruang hipotesis, batasan operasional absolut (*guardrails*), nada, dan format output yang harus dipertahankan secara invarian.
2. **Grounding Context (External State)**: Data referensi dinamis yang diekstraksi dari database eksternal, dokumen, atau state sesi saat ini untuk memitigasi halusinasi faktual.
3. **In-Context Demonstrations (Exemplars)**: Pasangan input-output kanonikal yang memandu pemetaan manifold representasi input ke manifold output yang diinginkan secara induktif.
4. **Task Instruction & Execution Payload**: Pertanyaan spesifik atau data transaksional runtime yang harus diproses oleh model.
5. **Output Formatting Directives & Delimiters**: Batasan sintaksis eksplisit (misalnya JSON Schema, XML blocks, TypeScript signatures) dan penanda parsing terstruktur.

```
+-----------------------------------------------------------------------+
| SYSTEM DIRECTIVES: Roles, Operational Limits, Safety Invariants      |
+-----------------------------------------------------------------------+
| GROUNDING CONTEXT: Deterministic Reference Data & External State      |
+-----------------------------------------------------------------------+
| EXEMPLARS (Few-Shot): In-Context Inductive Demos (Input -> Output)    |
+-----------------------------------------------------------------------+
| TASK PAYLOAD: Current Transactional Data & User Directive             |
+-----------------------------------------------------------------------+
| STRUCTURAL CONSTRAINTS: Grammar, Schema, & Delimited Output Bounds    |
+-----------------------------------------------------------------------+
```

### In-Context Learning (ICL)
**In-Context Learning (ICL)** adalah kapabilitas model transformer untuk mengeksekusi tugas baru pada saat inferensi tanpa pembaruan bobot model ($\Delta W = 0$). Berbeda dengan *supervised fine-tuning* yang memodifikasi matriks bobot melalui algoritma *backpropagation*, ICL beroperasi sepenuhnya di dalam konteks inferensi maju (*forward pass*). 

Secara teoritis, lapisan *self-attention* transformer bertindak sebagai pengoptimal meta (*meta-optimizer*) yang melakukan *implicit gradient descent* pada ruang aktivasi, menyelaraskan representasi laten dengan tugas yang dipetakan oleh *exemplars*.

---

## 3. Why It Matters

Dalam arsitektur sistem enterprise modern, kegagalan dalam menstrukturkan anatomi prompt menyebabkan tiga masalah fatal:

1. **Non-deterministic Failure & Parser Breakage**: Penggunaan instruksi bahasa alami yang longgar sering kali menghasilkan output yang menyimpang dari format sintaksis (misalnya, markdown tambahan di sekitar payload JSON), menyebabkan microservice downstream gagal melakukan parsing (`JSONDecodeError`) dan menghentikan pipeline transaksi.
2. **Context Drifting & Instruction Dilution**: Ketika konteks membesar (misalnya di atas 16.000 token), model cenderung mengalami degradasi perhatian terhadap instruksi awal (*lost-in-the-middle*). Tanpa arsitektur isolasi delimitasi yang tepat (menggunakan tag XML atau penanda Markdown terisolasi), instruksi sistem rentan diabaikan atau ditimpa oleh data konteks eksternal (indikasi kerentanan terhadap *Indirect Prompt Injection*).
3. **Financial Inefficiency & Token Bloat**: Penambahan contoh (few-shot) yang tidak dioptimalkan secara dinamis menyebabkan lonjakan konsumsi token input. Jika sebuah layanan melayani $10^7$ kueri per hari, redundansi 500 token per permintaan akibat struktur prompt yang buruk memicu pembengkakan biaya ribuan dolar per bulan tanpa peningkatan metrik akurasi (*Accuracy / F1-Score*).

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut merepresentasikan aliran data dari permintaan mentah (*raw client request*) melalui **Dynamic Prompt Assembly Pipeline** hingga terbentuknya *Attention Mask* terstruktur pada KV Cache model:

```
[Client Request Payload]
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Dynamic Prompt Synthesis Engine                      │
├────────────────────────────────┬───────────────────────────────────────┤
│ 1. Token Budget Allocation     │ Menghitung kuota max per segmen:       │
│                                │ [Sys: 15% | Ctx: 50% | Demos: 25% | ...│
├────────────────────────────────┼───────────────────────────────────────┤
│ 2. Vector Index / Exemplar DB  │ Semantic Retrieval (k-NN) k exemplar  │
│                                │ paling representatif terhadap task    │
├────────────────────────────────┼───────────────────────────────────────┤
│ 3. Delimiter Engine & Escaper  │ Sanitasi & enkapsulasi XML (<ctx>,    │
│                                │ <inst>, <schema>) cegah injection     │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Structured Token Context Buffer (Assembly)               │
├────────────────────────────────────────────────────────────────────────┤
│ <system_policy>      -> Invariant constraints & identity               │
│ <grounding_data>     -> Injected RAG documents (token-bounded)         │
│ <task_demonstration> -> Exemplar 1 (Input/Output schema)               │
│ <task_demonstration> -> Exemplar N (Input/Output schema)               │
│ <runtime_execution>  -> Sanitized input payload                        │
│ <response_contract>  -> Strict Pydantic-driven JSON Schema             │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 Autoregressive Transformer Core                        │
├────────────────────────────────────────────────────────────────────────┤
│ Tokenization & Positional Encoding (RoPE / ALiBi)                      │
│ Multi-Head Self-Attention Blocks:                                      │
│   Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) * V                  │
│ KV Cache Retention across prefix tokens                                │
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                 [Strictly Structured JSON Output]
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Teori Matematika: In-Context Learning sebagai Implicit Gradient Descent
Riset empiris dan teoretis terkini (von Oswald et al., 2023; Dai et al., 2023) menunjukkan bahwa komputasi *multi-head attention* pada transformer dapat diinterpretasikan sebagai operasi penurunan gradien implisit. 

Diberikan matriks *query* $Q$, *key* $K$, dan *value* $V$, operasi atensi dasar adalah:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

Ketika prompt memuat demonstrasi pasangan input-output $D = \{(x_1, y_1), (x_2, y_2), \dots, (x_m, y_m)\}$, representasi dari demonstrasi tersebut disimpan ke dalam matriks kunci ($K$) dan nilai ($V$). Selama *forward pass*, pembaruan status tersembunyi (*hidden states*) pada lapisan *feed-forward* dan *cross-token attention* memiliki sifat dual linier terhadap langkah pembaruan bobot berbasis gradien:

$$\Delta W_{ICL} \propto \sum_{i=1}^{m} e_i \otimes x_i$$

Artinya, model menggunakan token-token exemplar sebagai data training instan, menghitung sinyal kesalahan implisit ($e_i$) melalui *attention scores*, dan memproyeksikan transformasi representasi secara langsung pada representasi token kueri baru tanpa pernah mengubah bobot dasar $W_{LLM}$.

### 5.2 Positional Encodings dan "Lost-in-the-Middle" Phenomenon
Mekanisme penandaan posisi seperti *Rotary Position Embedding (RoPE)* memperkenalkan peluruhan atensi terhadap jarak token yang sangat jauh:

$$R_{\Theta, m}^d = \text{diag}\left(R_{\theta_1, m}, R_{\theta_2, m}, \dots, R_{\theta_{d/2}, m}\right)$$

Hal ini memengaruhi kinerja model pada sekuens panjang. Model berbasis transformer cenderung mempertahankan representasi yang kuat pada awal dokumen (**Primacy Effect**) dan akhir dokumen (**Recency Effect**), namun mengalami distorsi informasi pada token yang terletak di kuadran tengah (30% - 70% dari total panjang konteks).

```
Kemampuan Recall / Presisi Atensi
1.0 ──┐                                         ┌───
      │ \                                     / │
0.5 ──┤  \                                   /  │
      │   \                                 /   │
0.0 ──┴────\───────────────────────────────/────┴───
     0% (Start)        50% (Tengah)          100% (End)
               Lokasi Relatif Token dalam Konteks
```

**Implikasi Struktural Produksi:**
* **System Directives** dan **JSON Schemas** harus diletakkan pada batas ekstrem: System Instruction di titik $0\%$ konteks; Formatting Directives dan Target Execution Payload di titik $100\%$ konteks.
* **Grounding Context (Data Eksternal)** harus ditempatkan di tengah, diapit oleh tag pembatas eksplisit (misal: `<context>...</context>`).

### 5.3 Peran Delimiter dan Sintaks Penanda Struktur
Penggunaan pembatas (*delimiters*) berbasis XML (misal `<context>`, `<task>`, `<rules>`) terbukti mengungguli pemisah berbasis karakter umum (`---`, `###`). LLM modern (seperti Claude, GPT-4, Llama 3) telah di-*pre-train* secara masif pada data korpus web dan kode terstruktur. Tag XML memberikan batasan pohon sintaksis (*syntactic parse tree boundaries*) yang jelas, memisahkan lapisan instruksi fungsional dari lapisan data mentah secara matematis pada matriks atensi, secara signifikan mengurangi risiko injeksi instruksi dari data kontekstual yang tidak tepercaya.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi Python 3.11+ tingkat produksi yang mengimplementasikan **Dynamic Token-Bounded Few-Shot Prompt Assembler**. Modul ini menyediakan typing ketat, manajemen batas token deterministik menggunakan `tiktoken`, parsing skema menggunakan Pydantic v2, serta perakitan prompt modular terisolasi XML.

```python
"""
core_prompt_engine.py
Komponen produksi untuk perakitan prompt dinamis terstruktur dan In-Context Learning.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import StrEnum
import tiktoken
from pydantic import BaseModel, Field, ValidationError


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Exemplar(BaseModel):
    """Representasi pasangan input-output untuk In-Context Demonstrations."""
    input_text: str = Field(..., min_length=1, description="Raw input context")
    target_output: str = Field(..., min_length=1, description="Canonical expected output")
    task_category: str = Field(..., min_length=1, description="Metadata categorisation for filtering")


class ChatMessage(BaseModel):
    """Skema pesan LLM standar chat-completion."""
    role: Role
    content: str


@dataclass(frozen=True)
class PromptBudgetConfig:
    """Konfigurasi alokasi kuota token absolut per blok konteks."""
    max_total_tokens: int = 4096
    max_system_tokens: int = 512
    max_grounding_tokens: int = 2048
    max_exemplar_tokens: int = 1024
    reserved_response_tokens: int = 512


class TokenManager:
    """Manajer token deterministik berbasis tiktoken."""
    def __init__(self, model_name: str = "gpt-4"):
        try:
            self.tokenizer = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def truncate_to_budget(self, text: str, max_tokens: int) -> str:
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)


class ProductionPromptAssembler:
    """
    Orchestrator perakitan prompt modular enterprise dengan isolasi XML,
    alokasi kuota token, dan injeksi exemplar dinamis.
    """
    def __init__(self, budget_config: PromptBudgetConfig, model_name: str = "gpt-4"):
        self.budget = budget_config
        self.tokenizer = TokenManager(model_name=model_name)

    def _format_exemplars(self, exemplars: List[Exemplar], remaining_tokens: int) -> str:
        """Memformat demonstrasi few-shot dengan batasan anggaran token."""
        formatted_blocks: List[str] = []
        current_token_count = 0

        for idx, ex in enumerate(exemplars, 1):
            block = (
                f'<demonstration id="{idx}" category="{ex.task_category}">\n'
                f"  <input>\n    {ex.input_text}\n  </input>\n"
                f"  <output>\n    {ex.target_output}\n  </output>\n"
                f"</demonstration>\n"
            )
            block_tokens = self.tokenizer.count_tokens(block)
            if current_token_count + block_tokens > remaining_tokens:
                break
            formatted_blocks.append(block)
            current_token_count += block_tokens

        return "".join(formatted_blocks)

    def assemble(
        self,
        system_instructions: str,
        grounding_context: Optional[str],
        exemplars: List[Exemplar],
        runtime_input: str,
        response_schema: Optional[str] = None
    ) -> List[ChatMessage]:
        """
        Menyusun prompt modular dengan determinisme alokasi token.
        Menghasilkan list format ChatMessage yang siap dikonsumsi LLM API.
        """
        # 1. Validasi dan pangkas Instruksi Sistem
        truncated_system = self.tokenizer.truncate_to_budget(
            system_instructions, self.budget.max_system_tokens
        )
        
        system_payload = (
            "<system_directives>\n"
            f"{truncated_system}\n"
            "</system_directives>"
        )

        # 2. Pemrosesan Data Eksternal (Grounding Data)
        grounding_payload = ""
        if grounding_context:
            truncated_context = self.tokenizer.truncate_to_budget(
                grounding_context, self.budget.max_grounding_tokens
            )
            grounding_payload = (
                "\n<reference_context>\n"
                f"{truncated_context}\n"
                "</reference_context>\n"
            )

        # 3. Penataan Demonstrasi (Few-Shot Exemplars)
        exemplar_payload = ""
        if exemplars:
            exemplars_text = self._format_exemplars(exemplars, self.budget.max_exemplar_tokens)
            if exemplars_text:
                exemplar_payload = (
                    "<in_context_demonstrations>\n"
                    f"{exemplars_text}"
                    "</in_context_demonstrations>\n"
                )

        # 4. Konstruksi Skema & Batasan Respon
        constraint_payload = ""
        if response_schema:
            constraint_payload = (
                "<output_contract>\n"
                "Return output strictly adhering to the JSON schema below without conversational filler:\n"
                f"{response_schema}\n"
                "</output_contract>\n"
            )

        # 5. Integrasi Payload Runtime
        user_execution_payload = (
            f"{grounding_payload}"
            f"{exemplar_payload}"
            f"{constraint_payload}"
            "<runtime_task>\n"
            f"{runtime_input}\n"
            "</runtime_task>"
        )

        # Total Assembly Token Validation
        total_tokens = (
            self.tokenizer.count_tokens(system_payload) + 
            self.tokenizer.count_tokens(user_execution_payload)
        )
        
        allowed_tokens = self.budget.max_total_tokens - self.budget.reserved_response_tokens
        if total_tokens > allowed_tokens:
            raise ValueError(
                f"Konteks terpasang ({total_tokens} tokens) melampaui batas anggaran ({allowed_tokens} tokens)."
            )

        return [
            ChatMessage(role=Role.SYSTEM, content=system_payload),
            ChatMessage(role=Role.USER, content=user_execution_payload)
        ]


# ---------------------------------------------------------
# Verifikasi Komponen & Demonstrasi Eksekusi
# ---------------------------------------------------------
if __name__ == "__main__":
    # Inisialisasi Konfigurasi
    config = PromptBudgetConfig(
        max_total_tokens=2048,
        max_system_tokens=256,
        max_grounding_tokens=1024,
        max_exemplar_tokens=512,
        reserved_response_tokens=256
    )
    
    assembler = ProductionPromptAssembler(budget_config=config, model_name="gpt-4")

    # Data Komponen
    system_policy = "Anda adalah Financial Risk Analyzer. Analisis risiko kredit transaksi dan berikan output dalam format JSON strictly valid."
    
    context_data = "Nasabah ID: 98124. Riwayat: 3 keterlambatan bayar dalam 12 bulan terakhir. DSR: 62%."
    
    few_shot_demos = [
        Exemplar(
            input_text="Nasabah ID: 102. Riwayat: Bersih. DSR: 20%.",
            target_output='{"risk_level": "LOW", "score": 850, "recommendation": "APPROVE"}',
            task_category="credit_scoring"
        ),
        Exemplar(
            input_text="Nasabah ID: 404. Riwayat: Default 60 hari lalu. DSR: 80%.",
            target_output='{"risk_level": "CRITICAL", "score": 320, "recommendation": "REJECT"}',
            task_category="credit_scoring"
        )
    ]
    
    current_input = "Analisis transaksi Nasabah ID: 98124."
    schema_spec = '{"risk_level": "LOW|MEDIUM|HIGH|CRITICAL", "score": "int", "recommendation": "APPROVE|REVIEW|REJECT"}'

    # Eksekusi Sintesis
    try:
        messages = assembler.assemble(
            system_instructions=system_policy,
            grounding_context=context_data,
            exemplars=few_shot_demos,
            runtime_input=current_input,
            response_schema=schema_spec
        )
        for msg in messages:
            print(f"=== ROLE: {msg.role.value.upper()} ===")
            print(msg.content)
            print("-" * 50)
    except ValidationError as ve:
        print(f"Schema Validation Error: {ve}")
    except ValueError as e:
        print(f"Token Budget Exceeded: {e}")
```

---

## 7. Edge Cases & Failure Modes

Dalam lingkungan produksi skala besar (*high-throughput*), kegagalan prompt sering kali halus (*subtle*) dan sulit dideteksi tanpa telemetri yang memadai.

### 7.1 Recency and Order Bias dalam Few-Shot Learning
* **Failure Mode**: Model memiliki bias terhadap format atau label dari exemplar terakhir (*last-shown exemplar*). Jika exemplar terakhir memiliki label `REJECT`, model memiliki kecenderungan statistik yang lebih tinggi untuk memprediksi `REJECT` pada data runtime, terlepas dari fakta semantik input.
* **Mitigasi**: Implementasikan pengacakan posisi exemplar secara deterministik pada runtime atau lakukan *balanced distribution sampling* untuk memastikan distribusi kelas target pada exemplar setara (misalnya 1 Approve, 1 Reject).

### 7.2 Format Degeneration & Escaping Failures
* **Failure Mode**: Jika `runtime_input` memuat karakter XML ilegal atau tag penutup tidak terduga seperti `</runtime_task>`, *syntactic parser* internal model akan terdisrupsi, menyebabkan model menginterpretasikan sisa data sebagai instruksi baru (*Prompt Injection Vulnerability*).
* **Mitigasi**: Lakukan sanitasi dan *escaping* terhadap seluruh entitas input runtime (mengubah `<` menjadi `&lt;` dan `>` menjadi `&gt;`) sebelum dimasukkan ke dalam template konteks.

### 7.3 Context Length Overflow & Fallback Mechanics
* **Failure Mode**: Lonjakan tiba-tiba ukuran dokumen dari RAG melebihi batas jendela konteks fisik model, memicu galat API `400 InvalidRequestError: Context length exceeded`.
* **Mitigasi**: Gunakan *Graceful Degradation Algorithm*:
  1. Tahap 1: Pangkas kuota exemplar few-shot menjadi 0 (beralih ke *zero-shot mode*).
  2. Tahap 2: Terapkan *summarization map-reduce* pada dokumen konteks grounding.
  3. Tahap 3: Jika batas tetap terlampaui, alihkan (*fallback*) eksekusi ke model dengan *extended window* (misalnya dari context window 8K ke 32K/128K) secara otomatis.

---

## 8. Trade-offs & Alternatif Solusi

Setiap teknik adaptasi model bahasa memiliki trade-off komputasi, biaya, dan fleksibilitas:

| Metrik Evaluasi | Zero-Shot Prompting | Few-Shot (In-Context) | RAG + Context Injection | PEFT / LoRA Fine-Tuning |
| :--- | :--- | :--- | :--- | :--- |
| **Latensi Inferensi (TTFT)** | **Sangat Rendah** (Minimal token prefix) | **Sedang** (+200-1000 input tokens) | **Tinggi** (Overhead latensi retrieval + token RAG) | **Sangat Rendah** (Konteks prompt tetap minimal) |
| **Amortisasi Biaya Token** | **Paling Murah** | **Sedang** (Biaya berulang pada tiap inferensi) | **Tinggi** (Biaya embedder + retrieval + tokens) | **Optimal** (Biaya per panggilan kecil, capital upfront) |
| **Adaptabilitas Runtime** | Statis | Dinamis (Exemplar dapat ditukar per-request) | Sangat Dinamis (Konteks diambil secara ad-hoc) | Kaku (Model bobot harus di-deploy ulang/di-swap) |
| **Determinisme Format** | Rendah (Rentan distorsi parsing) | **Tinggi** (Model mereplikasi pola demonstrasi) | Tinggi (Jika didukung demonstrasi yang baik) | **Maksimal** (Format telah tertanam dalam bobot) |
| **Risiko Halusinasi** | Sangat Tinggi | Sedang | **Sangat Rendah** (Terikat fakta dokumen) | Sedang (Dapat menghafal data usang) |

### Keputusan Arsitektur:
* **Gunakan Few-Shot Context Injection** jika: Tugas membutuhkan format terstruktur yang tidak lazim, latensi pipeline masih dalam batas SLA (<1.5 detik), dan skema output sering dimodifikasi oleh tim produk.
* **Gunakan Fine-Tuning** jika: Skema data telah beku (*frozen*), throughput sangat tinggi (jutaan panggilan per hari di mana biaya token harus diminimalkan), dan latensi TTFT (*Time-to-First-Token*) krusial.

---

## 9. Best Practices & Standard Industri

1. **Adopsi Tag XML Terisolasi**: Gunakan struktur tag eksplisit (`<instruction>`, `<rules>`, `<context>`, `<input>`, `<output>`). Model modern secara spesifik dioptimasi untuk mengenali hierarki XML sebagai instruksi sistem level tinggi.
2. **Pemisahan Peran (Role Separation)**: Jangan pernah mencampurkan aturan sistem (*policy*) ke dalam peran `user`. Seluruh batasan keamanan, persona, dan instruksi penanganan data wajib berada di blok `system`.
3. **Penerapan Prompt Caching (Prefix Caching)**: Provider cloud AI terkemuka (Anthropic, OpenAI) mendukung penyimpanan status KV cache (*prompt caching*). Agar prompt cache efektif:
   * Bagian prompt yang **statis** (Instruksi Sistem, Skema Respon, Exemplar Kanonikal) **wajib ditempatkan di awal string prompt**.
   * Bagian yang **dinamis** (Grounding Context yang berubah-ubah, User Query) **wajib ditaruh di akhir**.
   * *Perubahan sekecil 1 karakter di awal prompt akan menghanguskan (invalidate) seluruh cache downstream.*
4. **Alokasi Budget Token Defensif**: Terapkan rumus alokasi konteks berbasis rasio:
   $$\text{Available Budget} = \text{Context Window} - (\text{Max Output Tokens} + \text{Safety Buffer})$$
   Alokasikan *safety buffer* minimum 10% untuk menangani variasi tokenisasi multi-bahasa.

---

## 10. Hands-on Lab Exercise

### Skenario:
Anda ditugaskan membangun sistem ekstraksi informasi transaksi finansial regulatori (*Anti-Money Laundering Entity Extraction*). Sistem harus mampu mengekstrak: *Nama Entitas*, *Jumlah Transaksi*, *Negara Asal*, dan *Tingkat Risiko AML*, dari dokumen teks bebas yang berantakan, serta mengembalikannya dalam bentuk JSON strictly valid sesuai skema yang ditentukan.

### Langkah-langkah Implementasi:

#### Langkah 1: Siapkan Lingkungan Virtual & Dependensi
```bash
python -m venv venv
source venv/bin/activate  # Di Windows: venv\Scripts\activate
pip install pydantic==2.6.1 tiktoken==0.6.0
```

#### Langkah 2: Buat Skrip `lab_aml_extractor.py`
Tuliskan implementasi berikut ke dalam file `lab_aml_extractor.py`:

```python
import json
from typing import List, Literal
from pydantic import BaseModel, Field, ValidationError
from core_prompt_engine import (
    ProductionPromptAssembler, 
    PromptBudgetConfig, 
    Exemplar
)

# 1. Definisikan Skema Validasi Output yang Diinginkan
class AMLExtractionResult(BaseModel):
    entity_name: str = Field(..., description="Nama individu atau organisasi")
    amount_usd: float = Field(..., description="Nominal transaksi dikonversi ke USD")
    origin_country: str = Field(..., description="ISO 3166-1 alpha-2 atau nama negara asal")
    risk_level: Literal["LOW", "MEDIUM", "SUSPICIOUS", "PROHIBITED"] = Field(
        ..., description="Kategori risiko transaksi AML"
    )

# 2. Definisikan Bank Demonstrasi (Few-Shot Exemplars)
aml_exemplars = [
    Exemplar(
        input_text="Laporan intelijen: Transfer $450,000 dari rekening Shell Corp di Cayman Islands ke Bank Sentral Jakarta tanpa faktur pendukung.",
        target_output=json.dumps({
            "entity_name": "Shell Corp",
            "amount_usd": 450000.0,
            "origin_country": "Cayman Islands",
            "risk_level": "SUSPICIOUS"
        }),
        task_category="aml_extraction"
    ),
    Exemplar(
        input_text="Pembelian rutin suku cadang mesin sebesar $12,500 dari Heidelberg Druckmaschinen AG, Jerman, via SWIFT resmi.",
        target_output=json.dumps({
            "entity_name": "Heidelberg Druckmaschinen AG",
            "amount_usd": 12500.0,
            "origin_country": "Germany",
            "risk_level": "LOW"
        }),
        task_category="aml_extraction"
    )
]

# 3. Setup Assembler
budget = PromptBudgetConfig(
    max_total_tokens=1500,
    max_system_tokens=200,
    max_grounding_tokens=500,
    max_exemplar_tokens=400,
    reserved_response_tokens=400
)

assembler = ProductionPromptAssembler(budget_config=budget, model_name="gpt-4")

# 4. Data Uji Runtime (Raw Unstructured Transaction)
raw_input = "Peringatan Transaksi: Diterima dana senilai USD 1,200,000 dari entitas Petrov Petrochemical LLC yang berlokasi di Moscow untuk pembayaran minyak mentah tanpa manifes perkapalan."

# 5. Rakit Prompt
assembled_messages = assembler.assemble(
    system_instructions="Anda adalah Regulatory AML Extraction Engine. Ekstrak data transaksi sesuai skema JSON target.",
    grounding_context="Daftar High Risk Jurisdictions terkini: North Korea, Iran, Russia (Sanctioned), Cayman Islands.",
    exemplars=aml_exemplars,
    runtime_input=raw_input,
    response_schema=json.dumps(AMLExtractionResult.model_json_schema())
)

print("HASIL PERAKITAN PROMPT SIAP PRODUKSI:\n")
for msg in assembled_messages:
    print(f"[{msg.role.upper()}]:")
    print(msg.content)
    print("\n" + "="*60 + "\n")

# 6. Simulasi Respon Model & Validasi Pydantic
simulated_llm_response = """{
    "entity_name": "Petrov Petrochemical LLC",
    "amount_usd": 1200000.0,
    "origin_country": "Russia",
    "risk_level": "PROHIBITED"
}"""

print("VALIDASI OUTPUT DARI SIMULASI MODEL:")
try:
    parsed_json = json.loads(simulated_llm_response)
    validated_result = AMLExtractionResult(**parsed_json)
    print(" Validasi Berhasil!")
    print(f"Output Tervalidasi:\n{validated_result.model_dump_json(indent=2)}")
except ValidationError as e:
    print(f" Validasi Gagal: {e}")
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan program di terminal:
```bash
python lab_aml_extractor.py
```

### Kriteria Keberhasilan Verifikasi:
1. Skrip berhasil menghasilkan blok pesan `[SYSTEM]` dan `[USER]` yang terisolasi dengan penanda XML (`<system_directives>`, `<reference_context>`, `<in_context_demonstrations>`, `<output_contract>`, `<runtime_task>`).
2. Perhitungan token tidak memicu exception pemotongan anggaran (*budget overflow*).
3. Payload respons simulasi berhasil melewati validasi `AMLExtractionResult` tanpa memicu `ValidationError`.