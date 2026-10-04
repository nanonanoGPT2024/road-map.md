# Bab 04: LLM APIs, Tooling & Orkestrasi Model
## Module 01: Pondasi Pemanggilan LLM API Enterprise: Streaming, Structured Outputs, dan Resilient Orchestration Engine

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mengonfigurasi dan Mengorkestrasi Protokol Streaming SSE (Server-Sent Events)**: Mengimplementasikan konsumsi stream inferensi LLM asynchronous secara non-blocking dengan penanganan chunking malformed dan deteksi early termination.
2. **Menerapkan Strict Structured Outputs Menggunakan Constrained Decoding**: Memanfaatkan *Logit Bias Masking* dan *Context-Free Grammar (CFG)* untuk memastikan output model 100% patuh terhadap schema JSON (Pydantic V2) tanpa bergantung pada parsing berbasis prompt engineering.
3. **Membangun Resilient Client Architecture**: Merancang subsistem pemanggilan API dengan implementasi *Exponential Backoff with Full Jitter*, *Token Bucket Rate Limiting*, *Circuit Breaker*, dan *Dynamic Context Truncation Fallback*.
4. **Mengaudit Metrik dan Observabilitas Konsumsi Token**: Mengintegrasikan ekstraksi token usage akurat (prompt, completion, reasoning tokens) ke dalam pipeline OpenTelemetry untuk pelacakan *cost allocation* dan latensi *Time-to-First-Token (TTFT)*.

---

### 2. Concept Overview

Interaksi enterprise dengan model fondasi (Foundation Models) telah berevolusi dari sekadar eksperimentasi HTTP REST *synchronous* berbasis prompt sederhana menjadi integrasi sistem terdistribusi yang membutuhkan determinisme ketat, latensi terprediksi, dan toleransi kegagalan tinggi.

```
+-----------------------------------------------------------------------------------+
|                                  MENTAL MODEL                                     |
|                                                                                   |
|  Unstructured Prompt                      Constrained Sampler (Logit Mask)        |
|  +--------------------+                   +------------------------------------+  |
|  | Context + Task Req | ===(Inference)==> | Mask logits: P(token) = 0 if token |  |
|  +--------------------+                   | violates Context-Free Grammar      |  |
|                                           +------------------------------------+  |
|                                                             |                     |
|                                                             v                     |
|  Downstream Microservices                 Strict JSON Stream (Valid Pydantic Obj) |
|  +--------------------+                   +------------------------------------+  |
|  | DB / Transactional | <==(Validated)==  | {"order_id": 1029, "status": "OK"} |  |
|  | Execution Engine   |                   +------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

#### Komponen Kritis Interaksi API LLM:
1. **Transport Layer & Multiplexing**: LLM API modern berjalan di atas HTTP/2 untuk meminimalkan *handshake overhead*. Data streaming dikirim via protokol **Server-Sent Events (SSE)**, di mana server mempertahankan koneksi TCP persisten dan menyemburkan delta token (`text/event-stream`).
2. **Constrained Decoding Engine**: Alih-alih membiarkan model menggenerasi teks bebas lalu memparsingnya menggunakan Regex/JSON parser di layer aplikasi, mesin inferensi modern (seperti OpenAI Strict Mode, vLLM, llama.cpp Grammar) menyuntikkan *Finite State Machine (FSM)* langsung ke proses penarikan sampel token (*sampling step*). Setiap token kandidat diverifikasi terhadap skema formal. Logit probabilitas untuk token yang melanggar aturan skema disetel ke $-\infty$.
3. **Orchestration Resilience**: Memanggil LLM di level produksi berarti mengantisipasi *throttling* (HTTP 429), *gateway timeout* (HTTP 504), context window overflow, dan *silent non-deterministic dropouts*. Dibutuhkan arsitektur client transparan yang mengisolasi kegagalan model tanpa melumpuhkan aplikasi induk.

---

### 3. Why It Matters

Dalam implementasi skala besar, kegagalan menangani layer komunikasi LLM secara deterministik membawa konsekuensi fatal:

* **Integritas Transaksi Downstream**: Jika sebuah LLM bertugas mengekstraksi instruksi transfer dana perbankan dan mengembalikan JSON malformed seperti `{"amount": 1000000` (terpotong) atau tipe data tanggal yang salah, transaksi otomatis akan mengalami crash atau, lebih buruk lagi, mengeksekusi *state* yang korup.
* **Latensi dan User Experience (UX)**: Model frontier dengan ukuran parameter ratusan miliar membutuhkan waktu puluhan detik untuk menyelesaikan token reasoning dan completion panjang. Tanpa protokol streaming yang efisien, latensi aplikasi melonjak (*blocking request*), menyebabkan *timeout* pada load balancer (AWS ALB/Cloudflare memiliki timeout bawaan 60–100 detik). Streaming menurunkan metrik *Time-to-First-Token* (TTFT) ke level sub-detik.
* **FinOps dan Pelanggaran Kuota**: Tanpa *circuit breaker* dan *adaptive rate limiting*, kegagalan transient pada API provider dapat memicu *retry storm*, membakar limit TPM (*Tokens Per Minute*) dan RPM (*Requests Per Minute*), serta menghasilkan tagihan finansial membengkak tanpa menghasilkan output yang sukses.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur pemanggilan LLM end-to-end yang tangguh, dimulai dari Client Request hingga ke validasi schema Pydantic via constrained decoding engine dan stream processor.

```
+----------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE LLM GATEWAY ENGINE                                  |
|                                                                                                    |
|  +-----------------------+          +-------------------------+          +-----------------------+ |
|  |  Client Application   | -------> |  Resilience Controller  | -------> |  Token Bucket Limiter | |
|  |  (Payload + Schema)   |          |  (Circuit Breaker, EBO) |          |  (Rate/Quota Guard)   | |
|  +-----------------------+          +-------------------------+          +-----------------------+ |
|                                                                                      |             |
|                                                                                      v             |
|  +-----------------------------------------------------------------------------------------------+ |
|  | HTTP/2 Transport Client (httpx Async, Connection Pooling, Semantic Request Headers)            | |
|  +-----------------------------------------------------------------------------------------------+ |
|                                                  |                                                 |
+--------------------------------------------------|-------------------------------------------------+
                                                   | POST /v1/chat/completions
                                                   | (stream=true, response_format=JSON_SCHEMA)
                                                   v
+----------------------------------------------------------------------------------------------------+
|                                       LLM PROVIDER / RUNTIME ENGINE                                |
|                                                                                                    |
|  +-----------------------+          +-------------------------+          +-----------------------+ |
|  | Context Pre-fill &    | -------> | Logit Masking Engine    | -------> | SSE Token Streamer    | |
|  | KV Cache Optimization |          | (FSM Guided Sampling)   |          | (text/event-stream)   | |
|  +-----------------------+          +-------------------------+          +-----------------------+ |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   | SSE Chunks (data: {"delta": ...})
                                                   v
+----------------------------------------------------------------------------------------------------+
|                                     STREAM PARSING & VALIDATION ENGINE                             |
|                                                                                                    |
|  +-----------------------+          +-------------------------+          +-----------------------+ |
|  | Async SSE Line Buffer | -------> | Incremental Accumulator | -------> | Strict Schema Parser  | |
|  | (Frame Re-assembly)   |          | (& Cost Telemetry Hook) |          | (Pydantic V2 Base)    | |
|  +-----------------------+          +-------------------------+          +-----------------------+ |
|                                                                                      |             |
|                                                                                      v             |
|                                                                          +-----------------------+ |
|                                                                          | Validated Output DTO  | |
|                                                                          | to Business Logic     | |
|                                                                          +-----------------------+ |
+----------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Mekanisme Protokol Server-Sent Events (SSE)
SSE adalah protokol komunikasi satu arah (server-to-client) yang didefinisikan dalam spesifikasi HTML5, berjalan di atas protokol transport HTTP biasa.
* Paket data dikirimkan sebagai payload dengan MIME-type `text/event-stream`.
* Format framing wajib: Diawali field `data: `, diikuti payload JSON, diakhiri dengan dua karakter newline berturut-turut: `\n\n`.
* Penutupan stream diindikasikan oleh sentinel token khusus, umumnya berupa string: `data: [DONE]\n\n`.
* Setiap frame membawa delta teks atau objek parsing parsial. Client engine harus memiliki line-buffer internal untuk menangani *chunk fragmentation*, di mana satu paket frame TCP terpotong menjadi beberapa segment data yang tidak lengkap sebelum newline ganda tiba.

#### B. Logit Masking & Constrained Grammar Sampling
Struktur JSON yang valid tidak dijamin semata-mata dengan menuliskan `"respond in JSON"` pada system prompt. Mesin inferensi modern mengimplementasikan validasi deterministik di layer sampling token:

$$P(w_t = k \mid w_{<t}) = \frac{\exp(z_k + M_k)}{\sum_{j} \exp(z_j + M_j)}$$

Di mana $z$ adalah raw logits yang dihasilkan model untuk setiap token $k$ di dalam vocab, dan $M$ adalah *masking vector*:
$$M_k = \begin{cases} 0 & \text{jika token } k \text{ menghasilkan token yang valid menurut FSM Schema} \\ -\infty & \text{jika token } k \text{ melanggar aturan tata bahasa (grammar/schema)} \end{cases}$$

Ketika token pertama yang diekstrak harus berupa karakter `{`, masking vector akan menetapkan seluruh token alfabet, angka, dan whitespace non-struktural menjadi $-\infty$. LLM secara matematis dicegah mengembalikan karakter non-JSON.

#### C. Algoritma Resilience: Exponential Backoff dengan Full Jitter
Mengulang request gagal menggunakan interval statis menyebabkan fenomena *thundering herd* yang memperparah overload pada server provider. Solusi standar industri yang dipopulerkan oleh AWS Architecture Core adalah **Exponential Backoff with Full Jitter**:

$$T_{\text{sleep}} = \text{random}(0, \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}}))$$

Pendekatan ini menyebarkan distribusi pemanggilan ulang secara seragam (uniform distribution) pada kurva waktu, meredakan saturasi antrean pada LLM gateway.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi engine orkestrasi pemanggilan LLM modular berbasis Python 3.11+, menggunakan library async murni `httpx` dan `pydantic` V2 tanpa dependensi berat ke framework pihak ketiga.

```python
"""
Resilient Enterprise LLM Orchestration Engine
Implementasi Zero-Dependency Framework (Murni httpx + pydantic v2)
Menangani SSE Streaming, Strict JSON Schema Enforcement, Retry Jitter, & Metrik.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
)

import httpx
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMOrchestrationEngine")

T = TypeVar("T", bound=BaseModel)


# ============================================================================
# 1. DOMAIN MODELS & SCHEMAS
# ============================================================================

class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    time_to_first_token_ms: Optional[float] = None
    total_latency_ms: float = 0.0


class LLMResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    raw_content: str = ""
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: Optional[str] = None


class CustomerSupportIntent(BaseModel):
    """Schema produksi untuk klasifikasi tiket operasional."""
    ticket_id: str = Field(description="ID Tiket dalam format UUID/Alfa-numerik")
    category: str = Field(description="Kategori: BILLING, TECH_SUPPORT, ACC_ACCESS, atau FEATURE_REQ")
    urgency_score: int = Field(ge=1, le=5, description="Skor urgensi dari 1 (rendah) sampai 5 (kritis)")
    entities_extracted: List[str] = Field(default_factory=list, description="Entity penting seperti nama akun, invoice id")
    actionable_summary: str = Field(description="Ringkasan aksi konkret yang harus dieksekusi")


# ============================================================================
# 2. FAULT TOLERANCE & HTTP CLIENT
# ============================================================================

class LLMAPIException(Exception):
    """Basis exception untuk kegagalan komunikasi LLM API."""
    pass


class LLMRateLimitExceeded(LLMAPIException):
    pass


class LLMContextWindowExceeded(LLMAPIException):
    pass


class ResilientLLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        max_retries: int = 4,
        backoff_base_sec: float = 1.0,
        backoff_max_sec: float = 32.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.backoff_base_sec = backoff_base_sec
        self.backoff_max_sec = backoff_max_sec
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.timeout_policy),
                limits=httpx.Limits(max_keepalive_connections=50, max_connections=200),
            )
        return self._client

    @property
    def timeout_policy(self) -> httpx.Timeout:
        return httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=10.0)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _calculate_jittered_backoff(self, attempt: int) -> float:
        """Menghitung Full Jitter Exponential Backoff."""
        upper_bound = min(self.backoff_max_sec, self.backoff_base_sec * (2 ** attempt))
        return random.uniform(0, upper_bound)

    # ============================================================================
    # 3. STREAMING CORE IMPLEMENTATION (SSE)
    # ============================================================================

    async def generate_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
    ) -> AsyncGenerator[str, None]:
        """
        Konsumsi raw delta stream secara asynchronous menggunakan protokol Server-Sent Events.
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        }

        client = await self.get_client()

        for attempt in range(self.max_retries + 1):
            try:
                async with client.stream("POST", "/chat/completions", json=payload) as response:
                    if response.status_code == 429:
                        raise LLMRateLimitExceeded("API Quota/Rate Limit Exhausted.")
                    if response.status_code >= 500:
                        raise LLMAPIException(f"Provider Infrastructure Error: {response.status_code}")
                    if response.status_code != 200:
                        err_content = await response.aread()
                        raise LLMAPIException(f"API Client Error {response.status_code}: {err_content.decode()}")

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            token_data = line[6:]  # Hapus prefix 'data: '
                            if token_data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(token_data)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                logger.warning("Chunk parsing failure, malformed SSE frame: %s", line)
                                continue
                return  # Stream selesai dengan sukses

            except (httpx.RequestError, LLMRateLimitExceeded, LLMAPIException) as exc:
                if attempt == self.max_retries:
                    logger.error("Kelebihan kuota retry exhaustion. Transaksi dibatalkan.")
                    raise exc

                sleep_duration = self._calculate_jittered_backoff(attempt)
                logger.warning(
                    "Panggilan LLM gagal: %s. Melakukan retry ke-%d dalam %.2f detik...",
                    str(exc), attempt + 1, sleep_duration
                )
                await asyncio.sleep(sleep_duration)

    # ============================================================================
    # 4. STRUCTURED OUTPUT ENGINE (CONSTRAINED DECODING)
    # ============================================================================

    async def generate_structured(
        self,
        model: str,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        temperature: float = 0.0,
    ) -> LLMResponse[T]:
        """
        Memaksa model mengembalikan structured data sesuai Schema Pydantic 
        menggunakan strict JSON Schema native parameter (OpenAI/vLLM compliant).
        """
        json_schema = {
            "name": response_model.__name__,
            "strict": True,
            "schema": response_model.model_json_schema(),
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": json_schema,
            },
        }

        client = await self.get_client()
        start_time = time.perf_counter()

        for attempt in range(self.max_retries + 1):
            try:
                res = await client.post("/chat/completions", json=payload)

                if res.status_code == 429:
                    raise LLMRateLimitExceeded("Rate limit hit during structured output execution.")
                elif res.status_code >= 500:
                    raise LLMAPIException(f"Provider Error: {res.status_code}")
                elif res.status_code != 200:
                    raise LLMAPIException(f"Bad Request: {res.text}")

                duration_ms = (time.perf_counter() - start_time) * 1000.0
                raw_json = res.json()
                choice = raw_json["choices"][0]
                raw_text_content = choice["message"]["content"]

                # Pydantic Structural Validation
                try:
                    validated_obj = response_model.model_validate_json(raw_text_content)
                except ValidationError as ve:
                    logger.critical("Model constrained failure, data breaks schema: %s", ve)
                    raise LLMAPIException(f"Pydantic Validation Guard Rejected Output: {str(ve)}")

                raw_usage = raw_json.get("usage", {})
                usage = TokenUsage(
                    prompt_tokens=raw_usage.get("prompt_tokens", 0),
                    completion_tokens=raw_usage.get("completion_tokens", 0),
                    total_tokens=raw_usage.get("total_tokens", 0),
                    total_latency_ms=duration_ms,
                )

                return LLMResponse[T](
                    data=validated_obj,
                    raw_content=raw_text_content,
                    usage=usage,
                    finish_reason=choice.get("finish_reason"),
                )

            except (httpx.RequestError, LLMRateLimitExceeded, LLMAPIException) as exc:
                if attempt == self.max_retries:
                    raise exc
                backoff = self._calculate_jittered_backoff(attempt)
                await asyncio.sleep(backoff)

        raise LLMAPIException("Unexpected state: Loop retry selesai tanpa hasil.")
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Akar Masalah Arsitektur | Mekanisme Pemulihan / Mitigasi |
| :--- | :--- | :--- |
| **Max Tokens Truncation** (`finish_reason="length"`) | Output JSON terpotong di tengah stream sebelum penutupan bracket `}`, memicu parsing error fatal. | Lacak nilai `finish_reason`. Jika bernilai `length`, lempar `ContextWindowException` dan picu *fallback pattern* dengan menaikkan batas `max_tokens` atau merestrukturisasi request ke mode chunking atomik. |
| **Logit Masking Deadlock** | Terjadi jika skema JSON Pydantic terlalu restriktif atau mengandung rekursi tanpa dasar terminasi, menyebabkan sampler tidak menemukan token valid. | Hindari field `Any`, `Union` tanpa discriminator, dan skema rekursif tak berhingga pada Pydantic. Berikan skema deterministik bertipe *primitives*, *flat arrays*, dan *strict enums*. |
| **Silent SSE Connection Drop** | Load balancer memutus koneksi TCP idle tanpa mengirim flag TCP FIN/RST (koneksi menggantung). | Implementasikan *Read Timeout* non-blokir per frame (misal: 10 detik tanpa paket SSE baru mengaktifkan reset koneksi dan resume inferensi). |
| **Rate Limiter Cascading Failures (HTTP 429)** | Sekumpulan worker memicu inferensi secara bersamaan tanpa sinkronisasi terdistribusi. | Gabungkan *Exponential Backoff with Full Jitter* di layer client dengan *Distributed Redis Token Bucket* sebelum payload mencapai konektor LLM gateway. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap teknik ekstraksi data terstruktur memiliki konsekuensi operasional yang berbeda:

```
+----------------------------------------------------------------------------------------------------+
|                                    COMPARATIVE DECISION MATRIX                                     |
+----------------------+--------------------+--------------------+-----------------------------------+
| Parameter            | Prompt Injection   | Tool/Function      | Strict Constrained Decoding       |
|                      | ("Return JSON")    | Calling            | (JSON Schema / CFG)               |
+----------------------+--------------------+--------------------+-----------------------------------+
| Determinisme Sintaks | Rendah (70% - 90%) | Tinggi (98% - 99%) | Deterministik 100% (Matematis)    |
| Overhead Inferensi   | 0 ms               | 50 - 150 ms        | Ringan (Masking Engine overhead)  |
| Dependensi Framework | Nol (String parser)| Terikat Tool API   | Memerlukan engine pendukung FSM   |
| Kemudahan Fallback   | Sulit diprediksi   | Parsing Error Catch| Terjamin validasi Pydantic V2     |
| Dukungan Streaming   | Ya (raw chunks)    | Kompleks (args delta) Parsial (Tergantung Gateway Provider)|
+----------------------+--------------------+--------------------+-----------------------------------+
```

#### Alternatif Framework Orkestrasi:
* **Raw Async Client (Pendekatan di modul ini)**: Menghasilkan performa maksimum, zero *framework-churn*, kontrol penuh terhadap latensi dan jejak memori. Sangat direkomendasikan untuk microservices dengan throughput tinggi.
* **LiteLLM**: Baik untuk standardisasi multi-provider (mengubah skema payload Anthropic, Bedrock, dan OpenAI ke interface seragam), tetapi menyisipkan layer abstraksi tambahan di runtime.
* **LangChain / LlamaIndex**: Komprehensif untuk *rapid prototyping*, namun sering kali membawa *overhead* eksekusi berat (*deep abstraction stacks*), jejak dependensi masif, dan perilaku *swallowing exception* yang mempersulit debugging operasional enterprise.

---

### 9. Best Practices & Standard Industri

1. **Konfigurasi `temperature=0.0` untuk Ekstraksi Structured Data**: Menghilangkan variabilitas sampling stokastik dan memusatkan inferensi ke jalur probabilitas token dengan keyakinan (*confidence*) tertinggi.
2. **Kepatuhan OpenTelemetry GenAI Semantic Conventions**:
   * Setiap request LLM wajib melampirkan attribute spans: `gen_ai.system` (e.g., `"openai"`), `gen_ai.request.model`, `gen_ai.response.completion_tokens`, `gen_ai.response.prompt_tokens`.
   * Log tidak boleh menyimpan data raw prompt yang mengandung PII (*Personally Identifiable Information*). Gunakan hash data atau scrubbing filter sebelum tracing.
3. **Penyuntikan Unambiguous Enums**: Batasi pilihan kategori teks model menggunakan tipe data `Literal["A", "B", "C"]` atau `enum.Enum` bawaan Python. Hal ini secara instan mengurangi ruang eksplorasi token (*sampling search space*), menghemat biaya inferensi dan menekan latensi secara signifikan.
4. **Idempotency Keys**: Selalu injeksikan header `Idempotency-Key` (UUIDv4) pada request yang didukung oleh gateway provider untuk mencegah duplikasi penagihan token jika terjadi kegagalan jaringan setelah proses inferensi selesai dieksekusi oleh penyedia LLM.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab:
Anda ditugaskan membangun engine backend ingestor komplain finansial non-blokir. Sistem harus menerima teks keluhan nasabah mentah, mengalirkan progress klasifikasi secara real-time via SSE, dan menghasilkan objek data tervalidasi yang siap dieksekusi database menggunakan mode strict Pydantic V2.

#### Langkah-langkah Praktikum:

1. **Setup Environment**:
   ```bash
   mkdir llm-resilient-lab && cd llm-resilient-lab
   python3 -m venv venv
   source venv/bin/activate
   pip install httpx pydantic
   export OPENAI_API_KEY="sk-proj-YOUR_ACTUAL_API_KEY"
   ```

2. **Eksekusi Script Integrasi**:
   Buat file `main.py` dan jalankan kode di bawah ini:

```python
import asyncio
import os
from pydantic import BaseModel, Field
from typing import List, Literal

# Import orchestrator yang dibuat pada Section 6
from main_orchestrator import ResilientLLMClient

class FinancialActionItem(BaseModel):
    action_type: Literal["FREEZE_CARD", "REVERSE_FEE", "INITIATE_DISPUTE", "FORWARD_FRAUD"]
    reason: str
    target_amount: float = Field(ge=0.0)

class FinancialComplaintAnalysis(BaseModel):
    case_urgency: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    detected_account_ids: List[str]
    actions_required: List[FinancialActionItem]
    sentiment_index: float = Field(ge=-1.0, le=1.0)

async def main():
    api_key = os.getenv("OPENAI_API_KEY", "mock-key")
    client = ResilientLLMClient(api_key=api_key)

    unstructured_complaint = """
    Halo, kartu kredit saya dengan nomor akhir 8831 tiba-tiba didebit sebesar 
    Rp 1.450.000 pada tanggal 12 Mei untuk transaksi yang tidak pernah saya lakukan 
    di merchant Luar Negeri. Tolong segera blokir kartu saya dan batalkan tagihan 
    tersebut secepatnya! Saya merasa sistem keamanan Anda bocor!
    """

    messages = [
        {
            "role": "system",
            "content": "Anda adalah AI Analis Fraude & Operasional Finansial. Ekstraksi entitas dan aksi penanganan kasus perbankan secara deterministik."
        },
        {"role": "user", "content": unstructured_complaint}
    ]

    print("\n--- 1. TESTING RESILIENT SSE STREAMING ---")
    try:
        async for chunk in client.generate_stream(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Tuliskan 1 kalimat konfirmasi penerimaan laporan komplain."}]
        ):
            print(chunk, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"Streaming Error (Periksa API Key): {e}")

    print("\n--- 2. TESTING STRICT STRUCTURED OUTPUT (CONSTRAINED SCHEMA) ---")
    try:
        response = await client.generate_structured(
            model="gpt-4o-mini",
            messages=messages,
            response_model=FinancialComplaintAnalysis,
            temperature=0.0
        )
        
        print("Data DTO Sukses Divalidasi:")
        print(response.data.model_dump_json(indent=2))
        print("\nAudit Metrik Eksekusi:")
        print(f"- Total Latensi: {response.usage.total_latency_ms:.2f} ms")
        print(f"- Prompt Tokens: {response.usage.prompt_tokens}")
        print(f"- Completion Tokens: {response.usage.completion_tokens}")
        print(f"- Finish Reason: {response.finish_reason}")

    except Exception as e:
        print(f"Structured Generation Failure: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

#### Verifikasi dan Validasi Hasil Uji:
1. Pastikan stream teks delta tercetak ke terminal baris per baris tanpa terpotong (non-buffering delay).
2. Pastikan field `actions_required` pada output schema JSON terekstraksi ke dalam format list array objek bertipe `FinancialActionItem` secara akurat, mencakup enum `action_type: FREEZE_CARD` dan nominal `target_amount: 1450000.0`.
3. Verifikasi bahwa tidak ada validasi parsing manual berbasis regex yang gagal dijalankan, membuktikan kepatuhan strict logit masking engine pada level LLM API provider.