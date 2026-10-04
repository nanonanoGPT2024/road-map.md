# Bab 02: Structured Outputs & Advanced Schema Engineering

## Module 01: Deterministic Extraction, Constrained Decoding, dan Schema Validation

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Mekanisme Inferensi Berbasis Batasan (Constrained Decoding):** Menguraikan secara matematis dan algoritmik bagaimana *Context-Free Grammars* (CFG), *Pushdown Automata*, dan *Logit Masking* bekerja pada level *sampling* token LLM untuk menjamin validitas sintaks output 100%.
2. **Merancang Skema Data Kompleks Berbasis Standar JSON Schema & Pydantic V2:** Membangun representasi data yang *type-safe*, mendukung tipe polimorfik (*tagged unions*), validasi rekursif, dan *strict constraints* untuk *enterprise agent tools*.
3. **Mengimplementasikan Pipeline Ekstraksi Deterministik Bertingkat Produksi:** Mengintegrasikan model LLM modern (seperti OpenAI Structured Outputs API atau *local runtime engine* seperti Outlines/llama.cpp) dengan penanganan kesalahan (*error handling*), *reflection loop*, dan strategi pemulihan kegagalan (*fallback mechanisms*).
4. **Mengidentifikasi dan Memitigasi Edge Cases Produksi:** Menangani pemotongan token akibat *context window exhaustion*, *schema drift*, dan halusinasi semantik pada tipe data enumerasi dan numerik.

---

### 2. Concept Overview

Secara fundamental, *Large Language Models* (LLM) adalah mesin probabilistik autoregresif yang memetakan urutan token input $X = (x_1, x_2, \dots, x_n)$ menjadi distribusi probabilitas atas ruang kosakata (vocabulary) $V$ untuk memprediksi token berikutnya $x_{n+1}$:

$$P(x_{n+1} \mid x_1, \dots, x_n) = \text{softmax}(z_{n+1})$$

Di mana $z_{n+1} \in \mathbb{R}^{|V|}$ adalah vektor *logits* yang belum dinormalisasi.

Secara default, proses sampling ini bersifat tak berstruktur (*unconstrained*), di mana probabilitas menghasilkan teks bebas (natural language) non-deterministik sangat tinggi. Dalam konteks sistem otonom (*Autonomous Agents*), ketidakpastian ini berpotensi fatal. Sistem komputasi deterministik (basis data SQL, API perbankan, aktuator industri) tidak dapat memproses data non-deterministik atau teks yang ambigu; sistem tersebut membutuhkan *Abstract Syntax Tree* (AST) yang valid secara sintaksis dan semantik.

```
+-----------------------------------------------------------------------+
|                             MENTAL MODEL                              |
|                                                                       |
|  Unconstrained Decoding:                                              |
|  [Prompt] ---> (LLM Logic) ---> Sampling over ALL V ---> Free Text    |
|                                                          (High Risk)  |
|                                                                       |
|  Constrained Decoding:                                                |
|  [Prompt] ---> (LLM Logic)                                            |
|                     |                                                 |
|                     v                                                 |
|            [Logits Mask: -inf] <--- [FSM / CFG State Engine]          |
|                     |                                                 |
|                     v                                                 |
|         Sampling over VALID V_t only ---> Deterministic Schema (JSON) |
+-----------------------------------------------------------------------+
```

Pendekatan rekayasa output terstruktur telah berevolusi melalui tiga paradigma utama:

1. **Prompt-based Zero-shot Extraction:** Menginstruksikan model melalui teks (*"Output must be valid JSON"*). Metode ini memiliki reliabilitas rendah (<85%), rentan terhadap *markdown formatting pollution* (contoh: ````json ... ````), dan rentan rusak jika konteks input bertambah panjang.
2. **Post-hoc Validation & Retries:** Mengurai teks menggunakan parser eksternal setelah token digenerasi, kemudian melakukan *prompt feedback* jika parsing gagal. Meskipun lebih aman, pendekatan ini boros latensi dan biaya token (*token overhead*).
3. **Logit-Level Constrained Decoding (State-of-the-Art):** Menggunakan *Finite State Machine* (FSM) atau *Context-Free Grammar* (CFG) yang dikompilasi langsung dari JSON Schema. Pada setiap langkah inferensi $t$, parser menghitung subset token $V_{\text{valid}} \subseteq V$ yang diizinkan oleh skema. Token di luar $V_{\text{valid}}$ diberikan masking bernilai $-\infty$ pada vektor logits sebelum layer softmax dieksekusi:

$$z_{t, i}' = \begin{cases} z_{t, i} & \text{jika } i \in V_{\text{valid}} \\ -\infty & \text{jika } i \notin V_{\text{valid}} \end{cases}$$

Hal ini secara matematis menjamin bahwa model tidak dapat mengeluarkan karakter yang melanggar spesifikasi tata bahasa yang telah ditetapkan.

---

### 3. Why It Matters

Dalam arsitektur *Autonomous Agent Enterprise*, agen bertindak sebagai jembatan kognitif antara bahasa manusia dan sistem eksekusi transaksional. Kegagalan skema output bukan sekadar masalah *formatting error*, melainkan ancaman integritas sistem:

* **Integritas Transaksional Finansial:** Kegagalan deserialisasi pada parameter `amount: float` vs `amount: string` atau kegagalan parsing mata uang dapat memicu kegagalan pemanggilan RPC, menghasilkan pembatalan sepihak, atau lebih buruk lagi: eksekusi nilai yang salah (*silent cast*).
* **Deterministic Tool Invocation:** Agen multi-langkah (*multi-step agents*) bergantung pada output langkah $N$ untuk menjadi input langkah $N+1$. Jika langkah $N$ menghasilkan JSON malformasi, keseluruhan siklus penalaran (*Reasoning Loop*) runtuh, memicu *infinite retry loop* yang mahal secara komputasi.
* **Security & Injection Surface:** Validasi skema yang ketat (*Strict Validation*) berfungsi sebagai batas pertahanan pertama (*first-line defense*) terhadap serangan *Indirect Prompt Injection*. Jika LLM mencoba menyuntikkan instruksi berbahaya ke dalam parameter sistem, kompilasi FSM yang kaku akan memblokir token tersebut jika tidak sesuai dengan tipe data primitif atau regex yang didefinisikan.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan siklus hidup eksekusi *Structured Outputs* tingkat produksi, mulai dari kompilasi skema Pydantic hingga tahap eksekusi deterministik dan *self-healing*.

```
+---------------------------------------------------------------------------------------------------+
|                        PRODUCTION STRUCTURED OUTPUT PIPELINE ARCHITECTURE                         |
+---------------------------------------------------------------------------------------------------+

     +-----------------------+
     |   Domain Developer    |
     +-----------------------+
                 |
                 v Define Model
     +-----------------------+
     |   Pydantic V2 Model   |
     +-----------------------+
                 |
                 v Compile via reflection
     +-----------------------------------------------+
     |  JSON Schema Compiler (Draft 2020-12 / Strict)|
     +-----------------------------------------------+
                 |
                 +-----------------------------------+
                 |                                   |
                 v                                   v
     +-----------------------+           +-----------------------+
     |   OpenAI/Claude API   |           |  Local Engine / CFG   |
     |   (response_format)   |           | (Outlines/llama.cpp)  |
     +-----------------------+           +-----------------------+
                 |                                   |
                 | [Remote Grammar Compilation]      | [Local Grammar Trie Construction]
                 |                                   |
                 +-----------------+-----------------+
                                   |
                                   v
             +-------------------------------------------+
             |    Constrained Token Generation Engine    |
             |  - Logit Masking: z_i = -inf for invalid  |
             |  - Guaranteed Syntax Validity             |
             +-------------------------------------------+
                                   |
                                   | Emits Raw Tokens (Strict JSON String)
                                   v
             +-------------------------------------------+
             |     Pydantic Core Deserialization Engine  |
             +-------------------------------------------+
                                   |
                        +----------+----------+
                        | Valid?              | Invalid? (Semantic/Type edge case)
                        v                     v
            +----------------------+  +---------------------------------+
            |   Target Business    |  | Self-Healing Reflection Engine  |
            |     Agent Action     |  +---------------------------------+
            |  (Execution Ready)   |                  |
            +----------------------+                  | Re-feed Error Context
                                                      v
                                      +---------------------------------+
                                      |   Targeted Schema Self-Repair   |
                                      +---------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 FSM-Driven Grammar Parsing & Logit Masking
Saat LLM menghasilkan token secara autoregresif, engine *constrained decoding* mempertahankan status internal (*state*) dari Finite State Machine (FSM) yang dikonstruksi dari skema JSON.

1. **Inisialisasi State:** FSM dimulai pada root state $S_0$ (misalnya, mengharapkan karakter awal `{`).
2. **Kalkulasi Next Token Mask:**
   Engine mengevaluasi kosakata tokenizer $V$. Untuk setiap token $v \in V$, engine mengecek apakah rangkaian karakter yang dibentuk oleh penambahan $v$ menghasilkan transisi status FSM yang valid: $\delta(S_t, v) \to S_{t+1}$.
3. **Masking:**
   Jika transisi tidak valid, logit untuk token $v$ disetel ke $-\infty$.
4. **Pembaruan State:**
   Token yang terpilih ditambahkan ke string keluaran, dan status internal FSM beralih ke $S_{t+1}$. Proses ini berulang hingga FSM mencapai *terminal accept state* dan model mengeluarkan token end-of-sequence (`<EOS>`).

#### 5.2 OpenAI Strict Mode vs. Post-hoc Function Calling
OpenAI Structured Outputs (menggunakan flag `strict: true` pada `response_format`) mengimplementasikan pra-kompilasi skema ke dalam grammar engine internal di sisi server mereka. Persyaratan ketat ini meliputi:
* Setiap atribut objek *harus* didefinisikan dalam array `required`.
* `additionalProperties: false` *harus* diaktifkan pada setiap objek.
* Nilai rekursif atau tipe data dinamis ekstrem (seperti `typing.Any`) dilarang keras.
* Polimorfisme hanya diizinkan melalui `anyOf` dengan pembeda eksplisit (*discriminator*).

#### 5.3 Pydantic V2 Internals
Pydantic V2 ditulis ulang sepenuhnya menggunakan basis Rust (`pydantic-core`). Proses validasi tidak lagi berjalan di layer Python VM yang lambat, melainkan mem-parsing string JSON mentah langsung ke struct internal Rust sebelum mengonversinya ke objek Python. Ini menghasilkan peningkatan performa 5x hingga 50x pada beban pemrosesan payload data agen berskala besar.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi referensi *production-grade* menggunakan Python 3.11+, Pydantic V2, dan OpenAI SDK resmi. Arsitektur ini mengimplementasikan skema domain terstruktur multi-level, *strict decoding*, serta *reflection-based healing loop*.

```python
"""
Module: structured_engine.py
Description: Production-ready Deterministic Schema Extraction Engine for Enterprise AI Agents.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Dict, List, Literal, Optional, Type, TypeVar, Union
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from openai import OpenAI, APIError
import tenacity
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("StructuredOutputEngine")

T = TypeVar("T", bound=BaseModel)

# ============================================================================
# 1. DOMAIN SCHEMAS (Advanced Pydantic V2 Patterns)
# ============================================================================

class BaseActionPayload(BaseModel):
    """Base strict configuration for all action payloads."""
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        populate_by_name=True
    )

class SQLQueryPayload(BaseActionPayload):
    action_type: Literal["sql_query"] = Field(
        default="sql_query", 
        description="Discriminator identifier for SQL query execution."
    )
    raw_query: str = Field(
        ..., 
        description="The parameterized read-only SQL query to execute."
    )
    database_target: Literal["analytics_replica", "audit_log"] = Field(
        ..., 
        description="Target database node for execution."
    )
    timeout_seconds: Annotated[int, Field(ge=1, le=30)] = Field(
        default=5, 
        description="Query execution timeout limit."
    )

    @field_validator("raw_query")
    @classmethod
    def validate_read_only(cls, value: str) -> str:
        prohibited_verbs = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
        normalized = value.strip().upper()
        if any(normalized.startswith(verb) for verb in prohibited_verbs):
            raise ValueError(f"Dangerous mutation query detected. Execution rejected: {value}")
        if not normalized.startswith("SELECT"):
            raise ValueError("Only SELECT operations are permitted on analytics nodes.")
        return value

class HTTPRestPayload(BaseActionPayload):
    action_type: Literal["http_rest"] = Field(
        default="http_rest",
        description="Discriminator identifier for external API calls."
    )
    endpoint_url: str = Field(..., description="Fully qualified HTTPS URL endpoint.")
    method: Literal["GET", "POST"] = Field(..., description="HTTP method.")
    payload: Dict[str, str] = Field(default_factory=dict, description="Key-value body mapping.")

    @field_validator("endpoint_url")
    @classmethod
    def enforce_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError(f"Insecure transport protocol: {value}. Agent requires HTTPS.")
        return value

# Tagged Union for Polymorphic Tool Call Execution
AgentActionPayload = Annotated[
    Union[SQLQueryPayload, HTTPRestPayload],
    Field(discriminator="action_type")
]

class AgentExecutionPlan(BaseModel):
    """Root plan emitted by the reasoning engine containing ordered operations."""
    model_config = ConfigDict(
        strict=True,
        extra="forbid"
    )
    correlation_id: str = Field(..., description="Unique UUID tracking the agent execution lineage.")
    rationale: str = Field(..., min_length=10, description="Internal Chain-of-Thought reasoning summary.")
    actions: List[AgentActionPayload] = Field(
        ..., 
        min_length=1, 
        max_length=5, 
        description="Ordered deterministic sequence of operations to perform."
    )

    @model_validator(mode="after")
    def verify_plan_coherence(self) -> AgentExecutionPlan:
        # Cross-field business logic validation
        if len(self.actions) > 3 and "critical" not in self.rationale.lower():
            logger.warning("Large action batch detected without explicit criticality rationale.")
        return self


# ============================================================================
# 2. DETERMINISTIC ENGINE ENGINE IMPLEMENTATION
# ============================================================================

class StructuredExtractionError(Exception):
    """Raised when structured decoding exhausts all recovery attempts."""
    pass

class DeterministicEngine:
    def __init__(self, client: OpenAI, default_model: str = "gpt-4o-mini"):
        self.client = client
        self.model = default_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((APIError,)),
        reraise=True
    )
    def _execute_api_call(self, messages: List[Dict[str, str]], schema: Type[T]) -> tuple[Optional[T], Optional[str]]:
        """
        Executes the low-level API call with OpenAI Strict Structured Outputs.
        Returns parsed object or the raw string response in case of API degradation.
        """
        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=schema,
                temperature=0.0, # Determinism optimization
            )
            parsed_message = completion.choices[0].message
            if parsed_message.refusal:
                raise StructuredExtractionError(f"Model refused generation: {parsed_message.refusal}")
            
            return parsed_message.parsed, None

        except Exception as exc:
            logger.error(f"Inference failure encountered: {str(exc)}")
            raise

    def extract_with_reflection(
        self, 
        user_prompt: str, 
        schema: Type[T], 
        max_reflections: int = 2
    ) -> T:
        """
        Robust high-level extractor. If standard extraction fails validation semantically,
        it feeds the Pydantic error diagnostics back to the LLM via an iterative reflection loop.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict deterministic execution agent. "
                    "Analyze the query and generate the execution payload in the exact target schema format."
                )
            },
            {"role": "user", "content": user_prompt}
        ]

        attempt = 0
        while attempt <= max_reflections:
            try:
                logger.info(f"Attempting deterministic extraction. Execution iteration: {attempt}")
                parsed_object, _ = self._execute_api_call(messages=messages, schema=schema)
                
                if parsed_object is not None:
                    return parsed_object
                
                raise StructuredExtractionError("Null response object yielded from API parsing.")

            except (ValidationError, ValueError) as val_err:
                attempt += 1
                logger.warning(f"Validation failure detected on iteration {attempt}: {str(val_err)}")
                
                if attempt > max_reflections:
                    logger.critical("Max reflection iterations exhausted. Throwing hard failure.")
                    raise StructuredExtractionError(
                        f"Failed to achieve schema conformance after {max_reflections} reflections: {str(val_err)}"
                    ) from val_err

                # Construct reflection context payload
                error_diagnostic = str(val_err)
                reflection_message = {
                    "role": "user",
                    "content": (
                        f"CRITICAL VALIDATION ERROR on previous execution output:\n"
                        f"{error_diagnostic}\n"
                        f"Carefully correct the attributes while fully complying with the schema rules."
                    )
                }
                messages.append(reflection_message)

        raise StructuredExtractionError("Unexpected loop termination in deterministic pipeline.")


# ============================================================================
# 3. VERIFICATION AND TESTING RUNNER
# ============================================================================

if __name__ == "__main__":
    # Inisialisasi Mock Client / Production Client
    # Memerlukan environment variable: OPENAI_API_KEY
    import os
    
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY environment variable not set. Running Schema Verification Tests Only.")
        
        # Unit-Test Model Serialization Mechanics
        try:
            invalid_sql = {
                "action_type": "sql_query",
                "raw_query": "DELETE FROM users WHERE id = 1;",
                "database_target": "analytics_replica",
                "timeout_seconds": 10
            }
            SQLQueryPayload(**invalid_sql)
        except ValueError as e:
            logger.info(f"Expected validation assertion caught successfully: {e}")

        # Unit-Test Polymorphic Discrimination Valid Case
        valid_plan_data = {
            "correlation_id": "c1f7a07b-839f-4318-971c-3b1239999a4e",
            "rationale": "Fetching read-only aggregated telemetry for routine analytical review.",
            "actions": [
                {
                    "action_type": "sql_query",
                    "raw_query": "SELECT * FROM daily_metrics LIMIT 100;",
                    "database_target": "analytics_replica",
                    "timeout_seconds": 5
                },
                {
                    "action_type": "http_rest",
                    "endpoint_url": "https://api.internal.network/v1/ping",
                    "method": "GET",
                    "payload": {}
                }
            ]
        }
        validated_plan = AgentExecutionPlan.model_validate(valid_plan_data)
        logger.info(f"Schema fully validated. Root Actions Compiled: {len(validated_plan.actions)}")
        print("\nJSON Schema generated for OpenAI strict mode:")
        print(json.dumps(AgentExecutionPlan.model_json_schema(), indent=2))
    else:
        client = OpenAI()
        engine = DeterministicEngine(client=client)

        query = (
            "Prepare an analytical execution batch to query the database table 'user_retention' "
            "on our analytics replica, but make sure to delete inactive accounts first, then send "
            "a confirmation GET call to https://internal.corp/status."
        )

        logger.info("Submitting query requiring dynamic validation and reflection...")
        try:
            result = engine.extract_with_reflection(
                user_prompt=query,
                schema=AgentExecutionPlan
            )
            print("\nSuccessfully parsed output plan:")
            print(result.model_dump_json(indent=2))
        except StructuredExtractionError as e:
            logger.error(f"Pipeline successfully caught unresolvable prompt instruction: {e}")
```

---

### 7. Edge Cases & Failure Modes

Berikut adalah ringkasan skenario kegagalan, implikasi, dan langkah mitigasinya:

| Failure Mode | Root Cause / Mekanisme | Implikasi Teknis | Strategi Mitigasi / Remediasi |
| :--- | :--- | :--- | :--- |
| **Context Length Truncation** | Token payload melebihi `max_tokens` atau batas context window model saat menulis properti JSON. | Terjadi kegagalan deserialisasi parser secara fatal (`Unterminated string / Unexpected EOF`). | Hitung budget output tokens; implementasikan *Defensive Parsing Buffer*; atur limit `max_tokens` minimal $1.5\times$ dari ekspektasi ukuran schema. |
| **Unsupported Schema Keywords** | Pydantic model menggunakan fitur yang dilarang di API Strict Mode (cth: `Pattern` / regex kompleks, tipe `Union` tanpa discriminator). | Model vendor API menolak request pada tahap pre-flight (`400 Bad Request`). | Terapkan unit test CI/CD yang mengompilasi semua skema agen via `model_json_schema()` dan memverifikasinya terhadap meta-schema vendor. |
| **Hallucinated Enum Values** | Nilai enum LLM meleset karena konteks prompt ambigu, atau model melakukan *casing mutation* (misal: `"get"` vs `"GET"`). | `ValidationError` pada layer desentralisasi Pydantic. | Gunakan normalisasi `@field_validator(mode='before')` untuk konversi huruf besar/kecil (*case-insensitive casting*) sebelum validasi inti. |
| **Semantic Drift / Empty Action Plans** | JSON sintaksis valid, namun list array esensial bernilai kosong (`actions: []`). | Eksekusi agen berakhir tanpa aksi (*silent no-op*), memicu stalled tasks. | Gunakan batasan skema eksplisit Pydantic V2 seperti `min_length=1` pada field berbasis array. |
| **Nested Polymorphism Depth Bottleneck** | Skema memiliki tingkat kedalaman (*nesting depth*) $> 5$ lapis turunan JSON Schema. | Penurunan latensi FSM kompilasi lokal drastis (OOM) atau kegagalan grammar compilation di vendor. | Ratakan skema (*Schema Flattening*); pisahkan skema besar menjadi sub-langkah eksekusi terdistribusi. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap pendekatan rekayasa skema memiliki parameter kompromi yang signifikan:

```
[Prompt Engineering] ------------ [Function Calling] ------------ [Strict Structured Outputs]
      |                                   |                                     |
   Fleksibel                           Seimbang                             Kaku & Aman
Latensi Cepat                      Latensi Moderat                       Latensi Tinggi Saat Init
Reliabilitas: ~75%                 Reliabilitas: ~95%                    Reliabilitas: 100%
```

#### Analisis Matriks Solusi

| Parameter | 1. Prompt-Only JSON | 2. Vendor Tool/Function Calling | 3. Native Strict Outputs (API Masked) | 4. Client-Side CFG (Outlines/llama.cpp) |
| :--- | :--- | :--- | :--- | :--- |
| **Determinisme Sintaks** | Rendah (~70-85%) | Moderat-Tinggi (~95-98%) | **100% (Guaranteed)** | **100% (Guaranteed)** |
| **First-Token Latency (FTL)**| Tercepat (0ms overhead) | Cepat (~50ms overhead) | Terkena overhead kompilasi FSM awal | Sangat lambat pada kompilasi regex/grammar trie awal |
| **Portabilitas Multi-Model** | Sangat Tinggi (Model agnostik)| Tinggi (OpenAI, Claude, Mistral) | Sedang (Tergantung integrasi vendor) | Terbatas pada model self-hosted / Open-Weights |
| **Beban Token Ekstra** | Sangat Tinggi (Contoh JSON di Prompt)| Rendah (Definisi terpisah di payload)| Nol token tambahan di prompt | Nol token tambahan di prompt |
| **Toleransi Skema Kompleks**| Sangat Rendah | Sedang | Sangat Tinggi (Sesuai subset JSON Schema) | Sangat Tinggi |

* **Gunakan Alternatif 1** hanya untuk eksperimen cepat atau model lokal skala kecil yang tidak memiliki kemampuan tool-use.
* **Gunakan Alternatif 2** untuk interaksi yang fleksibel di mana sistem dapat menoleransi kegagalan deserialisasi minor menggunakan loop pemulihan manual.
* **Gunakan Alternatif 3** untuk aplikasi sistem perbankan, eksekusi transaksi basis data, dan enterprise tool execution tingkat produksi.
* **Gunakan Alternatif 4** bila arsitektur agen berjalan *on-premise* menggunakan model open-weights (seperti Llama-3 atau Mistral) menggunakan server inferensi lokal.

---

### 9. Best Practices & Standard Industri

1. **Jadikan Schema Sebagai Prompt Documentation:**
   Manfaatkan atribut `description` di dalam Pydantic `Field(...)` secara agresif. Anggap metadata ini sebagai instruksi *few-shot prompting* mikro. Model menggunakan metadata field ini secara probabilistik untuk menentukan token isi yang sesuai.
2. **Aktifkan `extra="forbid"` secara Konsisten:**
   Secara default, Pydantic mengabaikan input kunci tak terduga. Untuk Structured Outputs tingkat produksi, terapkan `extra="forbid"` agar setiap kunci halusinasi langsung memicu error dan tidak lolos ke lapisan logika aplikasi.
3. **Immutability via `frozen=True`:**
   Jadikan payload data bersifat *immutable* setelah parsing selesai. Hal ini mencegah modifikasi state yang tidak diinginkan (*unintended mutation*) pada arsitektur pipeline pemrosesan paralel asinkron.
4. **Hindari Schema Nesting yang Terlalu Dalam:**
   Maksimumkan kedalaman nesting skema hingga batas 3 lapis. Nesting yang terlalu dalam memperbesar ruang status transisi FSM secara eksponensial, meningkatkan latensi TTFT (*Time-to-First-Token*), dan memicu resiko *context memory exhaustion*.
5. **Pisahkan Business Semantic Validation dari Structural Validation:**
   Validasi struktural (apakah ini int? apakah string ini ada?) harus ditangani oleh JSON Schema API / Constrained Decoding Engine. Validasi semantik bisnis (apakah ID pengguna terdaftar di SQL server?) harus tetap dieksekusi di lapisan domain service aplikasi, bukan dipaksakan masuk ke prompt sistem agen.

---

### 10. Hands-on Lab Exercise

#### Skenario Laboratorium
Anda ditugaskan merancang modul ekstraksi parameter untuk sistem automasi *Incident Response Platform*. Modul ini bertugas menerima teks peringatan darurat (*Incident Alert Message*) non-terstruktur dari *DevOps Slack Channels*, memvalidasi tingkat keparahan (*severity*), dan memancarkan aksi perbaikan terstruktur yang sepenuhnya deterministik.

#### Langkah 1: Persiapan Lingkungan
Instal dependensi yang diperlukan:
```bash
pip install pydantic==2.8.2 openai==1.40.0 tenacity==8.5.0
```

#### Langkah 2: Definisikan Skema Domain Terisolasi
Buat file `incident_schema.py`:
```python
from typing import List, Literal, Annotated
from pydantic import BaseModel, Field, ConfigDict

class RemediationAction(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    target_service: str = Field(..., description="Nama mikroservis target, e.g., 'auth-v2'")
    action_type: Literal["RESTART_POD", "SCALE_UP", "DRAIN_TRAFFIC"]
    intensity: Annotated[int, Field(ge=1, le=10, description="Tingkat eskalasi dari 1-10")]

class IncidentTriageReport(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    incident_id: str = Field(..., description="Format ID: INC-XXXXX")
    severity: Literal["SEV1", "SEV2", "SEV3", "SEV4"]
    root_cause_hypothesis: str = Field(..., min_length=20)
    mitigation_steps: List[RemediationAction] = Field(..., min_length=1, max_length=3)
```

#### Langkah 3: Eksekusi Deterministic Parsing Test
Buat skrip `run_triage_test.py`:
```python
import os
from openai import OpenAI
from incident_schema import IncidentTriageReport

client = OpenAI()

mock_incident_stream = (
    "URGENT ALERT: Auth-Service is throwing HTTP 500 across EU clusters. "
    "Incident INC-99421. Database connection pool exhausted. Memory utilization 98%. "
    "We need to drain traffic immediately and scale up the pods to double capacity."
)

response = client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are an automated Site Reliability Engineer parser."},
        {"role": "user", "content": mock_incident_stream}
    ],
    response_format=IncidentTriageReport,
    temperature=0.0
)

parsed_data: IncidentTriageReport = response.choices[0].message.parsed

# Langkah 4: Verifikasi Hasil Evaluasi
print(f"Parsed Incident ID   : {parsed_data.incident_id}")
print(f"Identified Severity  : {parsed_data.severity}")
print(f"Mitigation Actions   : {len(parsed_data.mitigation_steps)}")
for idx, action in enumerate(parsed_data.mitigation_steps, 1):
    print(f"  [{idx}] Type: {action.action_type} on {action.target_service} (Level: {action.intensity})")

# Assertions untuk CI/CD Validation Check
assert parsed_data.incident_id == "INC-99421", "Assertion Failure: Gagal mengekstrak ID insiden secara akurat."
assert len(parsed_data.mitigation_steps) >= 1, "Assertion Failure: Harus ada minimal 1 langkah perbaikan."
assert isinstance(parsed_data, IncidentTriageReport), "Output tidak sesuai tipe instance yang diharapkan."
print("\n[VERIFICATION SUCCESSFUL]: Skema divalidasi dan lolos parsing deterministik.")
```

#### Langkah 5: Jalankan Verifikasi
Jalankan skrip di terminal Anda:
```bash
python run_triage_test.py
```

Output terminal harus mengonfirmasi pemetaan skema yang tepat, tidak terpengaruh format teks input yang berantakan, serta memvalidasi kesesuaian seluruh *field restrictions*. Logika aplikasi Anda sekarang terlindungi oleh kontrak skema yang divalidasi secara matematis.