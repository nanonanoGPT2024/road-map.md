# Kurikulum Rekayasa DevRel Enterprise: Friction Engineering & Arsitektur DX

**Domain:** `08-AI-Data-and-Autonomous-Agents`  
**Bab 02:** `BAB-02-Developer-Experience-Product-Friction-Engineering`  
**Modul 02:** `Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi`

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mendiagnosis dan Mengkuantifikasi Developer Friction** pada platform AI/Agentic API menggunakan metrik terstandarisasi: *Time-to-First-Hello-World* (TTFHW), *Time-to-First-Token* (TTFT) drop-off, dan *Error Recovery Latency* (ERL).
2. **Merancang dan Mengimplementasikan Arsitektur Telemetri DX SDK** berbasis OpenTelemetry Semantic Conventions untuk AI/LLM tanpa mengekspos PII (*Personally Identifiable Information*) atau payload rahasia.
3. **Membangun Pipeline Otomasi Validasi Lintas Bahasa (*Multi-Language SDK Generation & Matrix Testing*)** yang memverifikasi kompatibilitas tipe (*type safety*), penanganan error streaming SSE (*Server-Sent Events*), dan *client-side retry backoff* secara deterministik.
4. **Mengintegrasikan Sistem Umpan Balik Tertutup (*Closed-Loop Friction Mitigation*)** yang mentransformasi kegagalan runtime pengembang menjadi perbaikan dokumentasi dinamis (*Dynamic Contextual Error Hints*) dan tiket investigasi otomatis.

---

## 2. Prerequisite

Untuk menyerap materi ini secara optimal, peserta wajib menguasai:

* **Sistem Terdistribusi & Jaringan:** Pemahaman protokol HTTP/2, gRPC, WebSocket, dan *Server-Sent Events* (SSE) pada streaming LLM.
* **Observabilitas:** Konsep dasar distributed tracing, OpenTelemetry (Traces, Metrics, Logs), dan arsitektur database analitik berbasis kolom (misal: ClickHouse).
* **Software Engineering Multi-Bahasa:** Pengetahuan tingkat menengah pada TypeScript/Node.js dan Python (async/await, metaprogramming/decorators, context managers).
* **CI/CD & Code Generation:** Pengalaman menggunakan GitHub Actions, OpenAPI/Spectral linter, serta engine generator SDK (misal: Stainless, Fern, atau OpenAPI Generator).

---

## 3. Concept & Internal Architecture

Dalam rekayasa platform AI dan Autonomous Agents, *Developer Experience* (DX) bukan sekadar persoalan dokumentasi yang rapi, melainkan sebuah **disiplin rekayasa keandalan interaksi pengembang (*Interaction Reliability Engineering*)**. Platform AI memiliki sifat non-deterministik: payload besar, latensi token bervariasi, potensi *hallucination*, serta error kompleks seperti *context window exhaustion* dan *rate limiting* berbasis TPM (*Tokens Per Minute*).

### Arsitektur Telemetri DX & Closed-Loop Friction Remediation

```
+-----------------------------------------------------------------------------------+
| CLIENT-SIDE SDK RUNTIME (Python, TypeScript, Go)                                  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Developer Application Code                                                  |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | SDK Core Client (Middleware Pipeline)                                       |  |
|  |  +------------------------+  +-------------------+  +--------------------+  |  |
|  |  | Type & Schema Validator|->| Retry & Backoff   |->| Token Stream Parser|  |  |
|  |  +------------------------+  +-------------------+  +--------------------+  |  |
|  +-----------------------------------------------------------------------------+  |
|           |                                                      |                |
|           | (Intercept Metrics & Spans)                          | (Raw HTTP)     |
|           v                                                      v                |
|  +---------------------------------------+             +-----------------------+  |
|  | Zero-PII DX Telemetry Interceptor     |             | AI Platform Gateway   |  |
|  | - Scrub Prompts / Keys / Embeddings   |             | (Envoy / Cloudflare)  |  |
|  | - Capture: TTFHW, Status, Error Codes |             +-----------------------+  |
|  | - Client Perf: Stream Jitter, Latency |                         |              |
|  +---------------------------------------+                         |              |
+----------------------|---------------------------------------------|--------------+
                       |                                             |
                       | OTLP / Protobuf (Async Batch)               |
                       v                                             v
+-----------------------------------------------------------------------------------+
| CONTROL PLANE / OBSERVABILITY INGESTION PIPELINE                                  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | OpenTelemetry Collector Cluster                                             |  |
|  |   - Processors: batch, memory_limiter, attributes/filter                    |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | Event Stream Ingestion (Apache Kafka / Redpanda)                            |  |
|  +-----------------------------------------------------------------------------+  |
|                      |                                       |                    |
|                      v                                       v                    |
|  +----------------------------------------+   +--------------------------------+  |
|  | Real-Time Stream Processor (Apache     |   | Columnar Store (ClickHouse)    |  |
|  | Flink / Vector Engine)                 |   | - Aggregated DX Metrics        |  |
|  | - Sliding Window Friction Anomaly      |   | - Error Distribution by SDK    |  |
|  | - High-Drop-Off SDK Version Detection  |   |   Version & Model              |  |
|  +----------------------------------------+   +--------------------------------+  |
|                      |                                       |                    |
+----------------------|---------------------------------------|--------------------+
                       |                                       |
                       v                                       v
+-----------------------------------------------------------------------------------+
| AUTOMATED ACTION ENGINE (DEVREL AUTOMATION)                                       |
|                                                                                   |
|  +-------------------------------------+   +------------------------------------+ |
|  | Dynamic Error Hint Dispatcher       |   | Friction Issue Tracker Worker      | |
|  | - Returns remediation URLs & docs   |   | - Auto-opens GitHub issue on SDK   | |
|  |   snippets directly in API error    |   |   repos when p95 error rate > 5%   | |
|  +-------------------------------------+   +------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

### Mekanisme Internal Interceptor & Sanitasi Zero-PII

Setiap SDK menyematkan lapisan interceptor non-blocking yang mengeksekusi operasi berikut:

1. **Context Initialization:** Mengidentifikasi metadata sesi pengembang secara anonim (*hashed machine-id*, versi runtime OS, versi SDK, dan identifier *sandbox* vs *production*).
2. **Execution Timing:** Menghitung `T_request_start`, `T_first_chunk` (untuk respons streaming), dan `T_stream_end`.
3. **Differential Scrubbing:** Mencegah kebocoran data sensitif dengan aturan ketat:
   * Prompt teks dan embeddings dibuang (*dropped*).
   * Nilai header `Authorization` disamarkan (*masked*).
   * Parameter arsitektur model (`model_name`, `max_tokens`, `temperature`, `stream=True/False`) dipertahankan sebagai dimensi analitik.
4. **Error Taxonomy Mapping:** Mengonversi kegagalan jaringan atau HTTP status code ke dalam taksonomi error standar:
   * `ERR_AUTH_CREDENTIAL_INVALID`
   * `ERR_CONTEXT_WINDOW_EXCEEDED`
   * `ERR_TPM_QUOTA_DEPLETED`
   * `ERR_STREAM_CONNECTION_ABORTED`
   * `ERR_DESERIALIZATION_FAILURE`

---

## 4. Why & What

### Mengapa APM Tradisional Gagal untuk Developer Relations?

Application Performance Monitoring (APM) standar (seperti Datadog atau New Relic) berfokus pada infrastruktur internal penyedia layanan: utilitas CPU, p99 latensi mikroservis backend, dan alokasi memori pod. 

Dalam konteks DevRel Engineering:
* **APM tidak melihat kode pengembang:** Ketika pengembang gagal menginisialisasi client SDK karena bug deserialisasi skema JSON di Python 3.12, backend Anda hanya melihat koneksi TCP ditutup sepihak (*TCP Reset* atau *Empty Request*).
* **Blind Spot pada Error Sisi Klien (*Client-Side SDK Failures*):** Jika validasi parameter lokal gagal di SDK, request tidak pernah mencapai gateway backend. Tanpa telemetri SDK, metrik ketersediaan backend Anda tercatat 99.99%, sementara kepuasan pengembang anjlok ke 0%.
* **Time-to-First-Hello-World (TTFHW) adalah Indikator Kelangsungan Hidup Bisnis:** Pada platform berbasis AI, jika seorang developer gagal mengeksekusi panggilan LLM inferensi pertama dalam waktu < 5 menit, rasio konversi pendaftaran ke implementasi produksi turun hingga lebih dari 60%.

### Apa itu Closed-Loop Friction Engineering?

Closed-Loop Friction Engineering adalah integrasi sistemik antara runtime SDK, monitoring error terdistribusi, dan otomatisasi developer workflow. Tujuannya adalah mendeteksi di mana pengembang mengalami hambatan integrasi (*friction point*), mengklasifikasikan penyebabnya secara terprogram, dan memberikan resolusi kontekstual langsung di konsol terminal mereka tanpa mengharuskan mereka membuka tiket support manual.

---

## 5. How (Workflow Detail)

Berikut alur pemrosesan friction dari saat pengembang menjalankan kode hingga otomatisasi remediasi aktif:

```
[ Developer Local Env ]
         |
         | 1. Instansiasi Client & Panggilan API (misal: client.chat.completions.create)
         v
+------------------------------------------------------------------------------------+
| SDK Client Pipeline                                                                |
|                                                                                    |
| [Validation Layer] ---> [Transport Layer] ---> [Streaming Chunk Processor]         |
|         |                      |                              |                    |
|         +-- (Jika gagal)       +-- (Jika timeout/429)         +-- (Jika putus)     |
|         |                      |                              |                    |
|         +----------------------+------------------------------+                    |
|                                |                                                   |
|                                v                                                   |
|                 [DX Instrumentation Interceptor]                                   |
+------------------------------------------------------------------------------------+
         |
         | 2. Emit OTLP Span + Custom Error Taxonomy Attribute
         v
+------------------------------------------------------------------------------------+
| Edge Ingestion Gateway (OTel Collector)                                            |
|                                                                                    |
| - Filter PII, Batching, Sanitasi Tag                                               |
| - Export ke ClickHouse Buffer                                                      |
+------------------------------------------------------------------------------------+
         |
         | 3. Query Stream Aggregation (Interval 1 Menit)
         v
+------------------------------------------------------------------------------------+
| DX Friction Engine                                                                 |
|                                                                                    |
| If (Count(ERR_CONTEXT_WINDOW_EXCEEDED, sdk="python", v="1.2.0") > Threshold)       |
|                                                                                    |
| [Action 1] Dynamic Docs Hint: Update payload error JSON dengan referensi link       |
|            spesifik cara kalkulasi token menggunakan tiktoken / tokenizers.        |
|                                                                                    |
| [Action 2] Incident Trigger: Buka issue GitHub otomatis ke repo SDK dengan stack   |
|            trace representatif yang telah disanitasi.                              |
+------------------------------------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi Jalan Tol vs. Rute Off-road Berbatu

Bayangkan API Anda adalah sebuah destinasi kota baru.
* **Backend Tanpa DX Engineering (Rute Off-road):** Anda membangun gedung pencakar langit berteknologi tinggi di kota tersebut (model LLM canggih, throughput tinggi). Namun, jalan menuju ke sana penuh lubang tanpa penunjuk arah. Pengembang yang bannya pecah (mengalami error skema JSON) terdampar di tengah malam tanpa ada yang tahu. Anda mengklaim fasilitas kota berjalan 100%, tetapi kota tetap kosong.
* **Platform dengan Friction Engineering (Jalan Tol Cerdas):** Jalan dilengkapi sensor beban di setiap kilometer. Jika sebuah mobil mogok karena salah bahan bakar (konfigurasi API key salah), sistem derek otomatis mengirim instruksi tepat ke dashboard pengemudi: *"Bahan bakar Anda tidak sesuai standar OIDC, gunakan solar tipe X di SPBU terdekat"* disertai tautan panduan langsung.

---

## 7. Simple Example & Practical Example

### A. Simple Example: Client-Side Interceptor untuk Error Taxonomy (TypeScript)

Contoh dasar penangkapan dan augmentasi error sebelum dilempar ke pengembang:

```typescript
// simple-interceptor.ts
export type FrictionCategory = 
  | 'AUTH_MISCONFIG'
  | 'SCHEMA_MISMATCH'
  | 'RATE_LIMIT_EXHAUSTED'
  | 'RUNTIME_NETWORK_ERROR'
  | 'UNKNOWN';

export class SDKError extends Error {
  constructor(
    message: string,
    public readonly category: FrictionCategory,
    public readonly remediationUrl?: string,
    public readonly originalError?: unknown
  ) {
    super(message);
    this.name = 'SDKError';
  }
}

export function handleSDKError(err: any): never {
  let category: FrictionCategory = 'UNKNOWN';
  let hint = 'https://docs.enterprise-ai.internal/troubleshooting/unknown';

  if (err.status === 401 || err.status === 403) {
    category = 'AUTH_MISCONFIG';
    hint = 'https://docs.enterprise-ai.internal/auth/rotate-api-keys';
  } else if (err.status === 429) {
    category = 'RATE_LIMIT_EXHAUSTED';
    hint = 'https://docs.enterprise-ai.internal/limits/managing-token-quotas';
  } else if (err.name === 'ZodError' || err.status === 422) {
    category = 'SCHEMA_MISMATCH';
    hint = 'https://docs.enterprise-ai.internal/sdk/models-schema-reference';
  }

  throw new SDKError(
    `[${category}] ${err.message} -> Petunjuk Remediasi: ${hint}`,
    category,
    hint,
    err
  );
}
```

---

### B. Practical Example: Production-Grade Telemetry Interceptor & Agent Instrumentation (Python)

Implementasi tingkat produksi menggunakan OpenTelemetry Tracing, Zero-PII filtering, kalkulasi metrik streaming token, dan integrasi error remediation dinamis.

Simpan file ini untuk referensi hands-on:

```python
# telemetry_engine.py
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import sys
import time
from typing import Any, AsyncGenerator, Callable, Dict, Optional
from dataclasses import dataclass, asdict

# Import OpenTelemetry Tracing API & SDK
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Setup Telemetry Provider secara terkontrol
_provider = TracerProvider()
# Pada produksi, gunakan OTLPSpanExporter ke OTel Collector
_processor = BatchSpanProcessor(ConsoleSpanExporter())
_provider.add_span_processor(_processor)
trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("enterprise-ai-dx-telemetry", "2.4.0")

logger = logging.getLogger("EnterpriseAI.DX")
logging.basicConfig(level=logging.INFO)


@dataclass(frozen=True)
class FrictionContext:
    session_hash: str
    python_version: str
    os_name: str
    sdk_version: str
    is_interactive_shell: bool


def resolve_friction_context() -> FrictionContext:
    """Mendeteksi konteks environment developer tanpa mengambil data rahasia."""
    raw_identifier = f"{platform.node()}-{os.getlogin() if hasattr(os, 'getlogin') else 'unknown'}"
    session_hash = hashlib.sha256(raw_identifier.encode("utf-8")).hexdigest()[:16]
    is_interactive = bool(getattr(sys, "ps1", sys.flags.interactive))

    return FrictionContext(
        session_hash=session_hash,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        os_name=platform.system(),
        sdk_version="2.4.0",
        is_interactive_shell=is_interactive,
    )


class DXFrictionException(Exception):
    """Exception terstandarisasi untuk error yang dihadapi pengembang."""
    def __init__(
        self,
        message: str,
        error_code: str,
        http_status: Optional[int] = None,
        docs_link: Optional[str] = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.http_status = http_status
        self.docs_link = docs_link or "https://docs.enterprise-ai.internal"

    def __str__(self) -> str:
        return (
            f"\n=======================================================\n"
            f"[DX-ERROR] Kode: {self.error_code} (Status HTTP: {self.http_status})\n"
            f"Pesan    : {super().__str__()}\n"
            f"Tindakan : Kunjungi tautan berikut untuk solusi teknis:\n"
            f"           {self.docs_link}\n"
            f"======================================================="
        )


class LLMAgentInstrumentedClient:
    """Mock Agent Client yang merepresentasikan antarmuka SDK enterprise."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ENTERPRISE_AI_KEY")
        self.context = resolve_friction_context()

    async def stream_chat_completion(
        self,
        model: str,
        messages: list[Dict[str, str]],
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat completion dengan pelacakan latensi TTFT (Time-to-First-Token)
        serta sanitasi Zero-PII telemetri.
        """
        span_name = "LLMAgent.stream_chat_completion"
        with tracer.start_as_current_span(span_name) as span:
            # 1. Pendaftaran Dimensi Non-PII
            span.set_attribute("devrel.sdk.language", "python")
            span.set_attribute("devrel.sdk.version", self.context.sdk_version)
            span.set_attribute("devrel.env.os", self.context.os_name)
            span.set_attribute("devrel.env.python_version", self.context.python_version)
            span.set_attribute("devrel.session.hash", self.context.session_hash)
            span.set_attribute("ai.model.target", model)
            span.set_attribute("ai.request.max_tokens", max_tokens)
            span.set_attribute("ai.request.message_count", len(messages))

            start_time = time.perf_counter()
            first_token_received = False

            # 2. Validasi Kredensial Awal
            if not self.api_key or not self.api_key.startswith("eai_live_"):
                span.set_status(Status(StatusCode.ERROR, "AUTH_KEY_INVALID"))
                span.set_attribute("devrel.friction.category", "AUTHENTICATION")
                span.set_attribute("devrel.friction.code", "ERR_KEY_MALFORMED")

                raise DXFrictionException(
                    message="API Key tidak ditemukan atau tidak valid. Gunakan format prefiks 'eai_live_...'.",
                    error_code="ERR_KEY_MALFORMED",
                    http_status=401,
                    docs_link="https://docs.enterprise-ai.internal/getting-started/authentication",
                )

            # 3. Simulasi Interaksi Jaringan & Streaming Token
            try:
                # Simulasi latensi gateway jaringan
                await self._simulate_network_handshake()

                # Simulasi response streaming
                simulated_chunks = [
                    "Halo! ", "Saya ", "adalah ", "Autonomous ", "Agent ", "Enterprise."
                ]

                for index, chunk in enumerate(simulated_chunks):
                    # Simulasi TTFT (Time to First Token)
                    if not first_token_received:
                        ttft_duration = time.perf_counter() - start_time
                        span.set_attribute("ai.perf.ttft_seconds", ttft_duration)
                        span.add_event("first_token_emitted", {"ttft": ttft_duration})
                        first_token_received = True

                    # Simulasi Context Window Overflow saat token ke-4
                    if index == 4 and max_tokens < 100:
                        raise DXFrictionException(
                            message=f"Model '{model}' melebihi kuota context window.",
                            error_code="ERR_CONTEXT_WINDOW_EXCEEDED",
                            http_status=400,
                            docs_link="https://docs.enterprise-ai.internal/models/context-limits#mitigation",
                        )

                    yield chunk

                span.set_status(Status(StatusCode.OK))
                span.set_attribute("ai.perf.total_duration_seconds", time.perf_counter() - start_time)

            except DXFrictionException as dx_err:
                span.set_status(Status(StatusCode.ERROR, dx_err.error_code))
                span.set_attribute("devrel.friction.category", "RUNTIME_API_ERROR")
                span.set_attribute("devrel.friction.code", dx_err.error_code)
                span.record_exception(dx_err)
                raise dx_err

            except Exception as unhandled:
                span.set_status(Status(StatusCode.ERROR, "UNHANDLED_EXCEPTION"))
                span.set_attribute("devrel.friction.category", "SYSTEM_UNHANDLED")
                span.record_exception(unhandled)
                raise DXFrictionException(
                    message=f"Kesalahan sistem tak terduga: {str(unhandled)}",
                    error_code="ERR_UNEXPECTED_CORE",
                    http_status=500,
                    docs_link="https://docs.enterprise-ai.internal/support/escalation",
                ) from unhandled

    async def _simulate_network_handshake(self):
        import asyncio
        await asyncio.sleep(0.05)  # 50ms latency
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Re-platforming SDK Agentic LLM di "CognitiveScale Inc."

* **Skala Sistem:** 45.000 pengembang aktif, 1,2 miliar token requests/hari, 4 bahasa resmi (Python, TypeScript, Go, Java).
* **Masalah Awal:** 
  * Waktu rata-rata aktivasi pengembang baru (*Time-to-First-Hello-World*) mencapai 45 menit.
  * Tingkat drop-off pengguna baru mencapai 52% pada sesi pertama pendaftaran.
  * Tim Developer Relations kebanjiran 1.200 tiket manual per minggu terkait masalah: format skema function calling/tool calling yang salah dan timeout streaming pada koneksi HTTP/1.1 proxies.
* **Solusi Terapan:**
  1. **Generasi SDK Deterministik:** Mengadopsi OpenAPI 3.1 + generator type-safe yang memvalidasi *tool definition schema* di memori klien sebelum request dikirim ke wire protokol.
  2. **Intersepsi Telemetri SDK Zero-PII:** Implementasi interceptor OTel dengan pelaporan otomatis kegagalan koneksi proxy SSE dan skema function call.
  3. **Contextual In-Console Resolution:** Jika gateway mengembalikan HTTP 400 akibat skema tool call invalid, payload JSON gateway diurai oleh interceptor SDK untuk menampilkan letak kesalahan baris dan kolom JSON di konsol terminal, lengkap dengan cuplikan perbaikan.
* **Hasil:**
  * TTFHW turun drastis dari 45 menit menjadi 3,5 menit.
  * Drop-off berkurang dari 52% menjadi 14%.
  * Volume tiket support terkait konfigurasi awal berkurang 78% dalam kurun 60 hari.

---

## 9. Trade-offs

Setiap keputusan arsitektur pada Developer Experience membawa konsekuensi teknis. Berikut matriks komparasi desain sistem DX:

| Pendekatan Desain | Keuntungan (Pros) | Biaya & Kompensasi (Cons/Risks) | Solusi Mitigasi |
| :--- | :--- | :--- | :--- |
| **Comprehensive SDK Telemetry (OTel)** | Visibilitas total terhadap kegagalan lokal, versi runtime, dan metrik latensi streaming di sisi developer. | Menambah latensi inisialisasi SDK, dependensi library membengkak (*bloated dependencies*), risiko kebocoran data. | Gunakan Batch Asynchronous Queue non-blocking; isolasi modul telemetri tanpa library eksternal berat; patuhi Zero-PII scrubbing ketat. |
| **Client-Side Heavy Schema Validation** | Mencegah panggilan jaringan yang mubazir ke LLM gateway jika skema function/tools tidak valid. | Waktu eksekusi lokal meningkat pada perangkat low-end; ukuran package SDK meningkat drastis. | Gunakan kompilasi schema ringan berbasis micro-validator (misal: JSON Schema via Rust FFI atau validator zero-dependency native). |
| **Dynamic In-Console Docs Hint Injection** | Developer langsung mengetahui solusi tanpa meninggalkan terminal/IDE mereka; mengurangi beban support. | Ketergantungan pada stabilitas URL dokumentasi; payload error HTTP dari gateway menjadi lebih besar. | Gunakan CDN redirector pendek permanen (misal: `https://err.ai/e/1042`); batasi ukuran metadata hints maksimum 512 bytes. |
| **Deterministic Synthetic Multi-OS CI Testing** | Menangkap kompatibilitas bug di berbagai OS (Linux, macOS, Windows) dan runtime (Node.js 18-22, Python 3.9-3.12). | Durasi build CI/CD menjadi lambat (30+ menit); biaya komputasi GitHub Actions / Runner meningkat tajam. | Implementasi caching agresif layer environment dan matrix testing selektif berbasis file diff path (*path filtering*). |

---

## 10. Common Mistakes & Troubleshooting

### 1. Kebocoran PII dan Rahasia dalam Error Logging
* **Kesalahan:** Mencetak seluruh respons atau prompt input pengembang saat request mengalami error HTTP 400/500 ke terminal atau backend telemetri.
* **Identifikasi:** String API Key (`eai_live_...`) atau prompt teks rahasia developer muncul di span attributes OTel Collector.
* **Perbaikan:** Implementasikan sanitasi sanitization parser berbasis regex pada interceptor paling bawah sebelum data keluar dari proses:
  ```python
  def scrub_sensitive_attributes(payload: dict) -> dict:
      clean = {}
      for k, v in payload.items():
          if k.lower() in ("authorization", "prompt", "api_key", "embedding"):
              clean[k] = "[REDACTED]"
          else:
              clean[k] = v
      return clean
  ```

### 2. Blocking Network Call saat Telemetri Gagal Terkirim
* **Kesalahan:** Mengirim metrik atau span DX menggunakan synchronous HTTP request di dalam method SDK utama. Ketika collector telemetri down, aplikasi developer menjadi hang atau crash.
* **Perbaikan:** Alokasikan daemon thread / background task independen dengan ring buffer terbatas. Jika buffer penuh, buang data telemetri (*drop metrics*) demi menjaga performa aplikasi utama.

### 3. Asumsi Determinisme Jaringan pada SSE (Server-Sent Events)
* **Kesalahan:** Menganggap setiap chunk LLM streaming tiba tepat waktu tanpa handling *half-open TCP connections*.
* **Identifikasi:** Developer mengeluh proses script mereka menggantung (*infinite hanging*) tanpa melempar exception saat koneksi internet terputus di tengah token generation.
* **Perbaikan:** Pasang mekanisme timeout read-inactivity pada SDK client: jika tidak ada chunk SSE baru yang diterima dalam 15 detik, paksa lempar `ERR_STREAM_CONNECTION_ABORTED`.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis versi SDK atau API publik baru:

- [ ] **Zero PII Guarantee:** Verifikasi bahwa tidak ada prompt, completion text, token otentikasi, atau path direktori file lokal yang dikirim ke endpoint telemetri.
- [ ] **Opt-Out Mechanism:** Sediakan konfigurasi env flag global bagi pengembang untuk mematikan telemetri (misal: `ENTERPRISE_AI_TELEMETRY_OPTOUT=1`).
- [ ] **Idempotent Error Taxonomies:** Seluruh error SDK dipetakan ke kode string deterministik (misal: `ERR_RATE_LIMIT`, bukan varian teks deskriptif yang berubah-ubah).
- [ ] **Actionable Remediation Links:** Setiap error yang dilempar SDK memiliki atribut referensi ke dokumentasi teknis atau langkah mitigasi.
- [ ] **Cross-Platform Matrix Verification:** SDK lulus uji di minimal 3 versi OS utama (Ubuntu, macOS, Windows) dan seluruh versi runtime LTS aktif.
- [ ] **Timeout & Keep-Alive Policy:** Transport layer memiliki default timeouts yang masuk akal: Connect timeout = 5s, Read/Streaming chunk timeout = 30s.
- [ ] **Fail-Safe Logging:** Kegagalan internal pada library SDK DX Telemetry tidak boleh melempar unhandled exception ke runtime aplikasi pengembang.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sistem monitoring DX berbasis Docker Compose yang terdiri dari OpenTelemetry Collector dan skrip klien yang menguji berbagai skenario developer friction.

### Struktur Proyek

Pastikan seluruh artefak latihan berada di direktori `hands-on/m02/`:

```
hands-on/m02/
├── docker-compose.yml
├── otel-collector-config.yaml
├── pyproject.toml
└── test_developer_friction.py
```

### Langkah 1: Buat Konfigurasi OTel Collector

Buat file `hands-on/m02/otel-collector-config.yaml`:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 10
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 20

exporters:
  logging:
    loglevel: debug

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [logging]
```

### Langkah 2: Buat Docker Compose File

Buat file `hands-on/m02/docker-compose.yml`:

```yaml
version: '3.8'

services:
  otel-collector:
    image: otel/opentelemetry-collector:0.96.0
    container_name: dx-otel-collector
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317" # OTLP gRPC
      - "4318:4318" # OTLP HTTP
    environment:
      - LOG_LEVEL=debug
```

### Langkah 3: Skrip Pengujian Skenario Friction

Buat file `hands-on/m02/test_developer_friction.py`:

```python
import asyncio
import os
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from telemetry_engine import LLMAgentInstrumentedClient, DXFrictionException, tracer, _provider

# Hubungkan SDK ke Local OTel Collector
otlp_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

async def run_scenarios():
    print("=== SKENARIO 1: Pengembang Menggunakan Format Key Salah ===")
    bad_auth_client = LLMAgentInstrumentedClient(api_key="sk-invalid-random-token")
    try:
        async for chunk in bad_auth_client.stream_chat_completion(
            model="agent-core-v1",
            messages=[{"role": "user", "content": "Halo"}]
        ):
            print(chunk, end="")
    except DXFrictionException as e:
        print(f"Ekspektasi Error Tertangkap: {e.error_code}\n")

    print("\n=== SKENARIO 2: Pengembang Menyetel Token Terlalu Rendah (Context Exceeded) ===")
    valid_client = LLMAgentInstrumentedClient(api_key="eai_live_secret123456789")
    try:
        async for chunk in valid_client.stream_chat_completion(
            model="agent-core-v1",
            messages=[{"role": "user", "content": "Halo"}],
            max_tokens=50 # Akan memicu limit saat chunk 4
        ):
            print(chunk, end="")
    except DXFrictionException as e:
        print(f"Ekspektasi Error Tertangkap: {e.error_code}\n")

    print("\n=== SKENARIO 3: Skenario Sukses ===")
    try:
        async for chunk in valid_client.stream_chat_completion(
            model="agent-core-v1",
            messages=[{"role": "user", "content": "Halo"}],
            max_tokens=2048
        ):
            print(chunk, end="", flush=True)
        print("\n\nSkenario sukses berhasil diselesaikan.")
    except Exception as e:
        print(f"Unexpected error: {e}")

    # Tunggu flushing telemetry spans
    await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(run_scenarios())
```

### Langkah 4: Instruksi Eksekusi

Jalankan perintah berikut di terminal:

```bash
# 1. Navigasi ke direktori hands-on
cd hands-on/m02/

# 2. Jalankan OTel Collector
docker-compose up -d

# 3. Pastikan dependensi terpasang
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp

# 4. Jalankan script uji friction
python test_developer_friction.py

# 5. Periksa log collector untuk memvalidasi atribut spans yang ditangkap tanpa kebocoran PII
docker-compose logs otel-collector | grep "devrel.friction"
```

---

## 13. Exercise

### Level Easy
Modifikasi kelas `DXFrictionException` pada `telemetry_engine.py` agar mengembalikan kode error baru `ERR_TIMEOUT_NETWORK` saat waktu koneksi melebihi 2 detik. Pastikan span status diubah menjadi `ERROR` dengan atribut `devrel.friction.code = "ERR_TIMEOUT_NETWORK"`.

### Level Medium
Buat sebuah middleware interceptor di Node.js/TypeScript yang membungkus pemanggilan fetch API streaming SSE. Jika stream ditutup secara abnormal (*abrupt close*) sebelum karakter terminator `[DONE]` diterima, interceptor wajib mengkalkulasi selang durasi sejak token terakhir dan membungkus error menjadi `ERR_STREAM_EARLY_TERMINATION`.

### Level Hard
Rancang arsitektur pipeline pemrosesan *ClickHouse Materialized View* yang membaca event span OTel dari Kafka. Pipeline tersebut harus mengagregasi data per 5 menit untuk menghitung:
* Rasio error per SDK language & version.
* Distribusi latensi p95 TTFT.
* Drop-off rate (developer yang mendapatkan error HTTP 401 dan tidak pernah membuat request sukses dalam kurun waktu 1 jam berikutnya).

Tuliskan schema DDL SQL ClickHouse untuk `raw_spans` dan `materialized_view_dx_summary`.

---

## 14. Challenge

Anda adalah Principal DevRel Architect di sebuah penyedia fondasi model AI. Tim Anda baru saja meluncurkan SDK versi `3.0.0-beta`. 

Dalam waktu 3 jam setelah rilis, dashboard analitik mendeteksi anomali:
* Angka komplain di Discord meningkat tajam.
* Metrik backend menunjukkan gateway menerima HTTP 400 dari 35% panggilan SDK TypeScript versi `3.0.0-beta`.
* Di saat yang sama, metrik backend Python SDK berjalan normal tanpa error.
* Log backend gateway hanya mencatat error generik: `400 Bad Request: Missing or malformed body`.

**Misi Anda:**
1. Rancang hipotesis teknis dan metode investigasi tanpa harus meminta data prompt pengembang.
2. Buat skrip simulasi reproduksi bug otomatis (*harness verification script*) yang memvalidasi serialisasi payload tools/function calling antara Python dan TypeScript runtime.
3. Rancang rencana mitigasi (*Zero-Downtime Hotfix Strategy*) untuk menyebarkan patch SDK dan memperbarui dynamic documentation hint agar pengembang yang terkena dampak langsung mendapatkan instruksi rollback/upgrade seketika di console mereka.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda)

1. **Apa definisi yang paling tepat untuk Time-to-First-Hello-World (TTFHW) dalam Friction Engineering?**
   * A. Waktu yang dibutuhkan compiler untuk membangun biner SDK dari source code.
   * B. Durasi sejak developer mendaftar akun/mengunduh SDK hingga eksekusi panggilan API fungsional pertama yang berhasil.
   * C. Total waktu pemrosesan token pertama di cluster server GPU model inference.
   * D. Waktu respons DNS saat developer melakukan resolve domain gateway.

2. **Mengapa data teks prompt developer tidak boleh dikirim ke sistem telemetri DX?**
   * A. Menghabiskan bandwidth jaringan client.
   * B. Membuat database analitik menjadi lambat saat indexing teks panjang.
   * C. Melanggar prinsip privasi data, kepatuhan GDPR/SOC2, dan berisiko membocorkan rahasia/PII pengguna.
   * D. Format data OTLP Spans tidak mendukung tipe data string.

3. **Komponen mana pada arsitektur OpenTelemetry yang bertanggung jawab membersihkan atau mengubah atribut sebelum diekspor ke storage?**
   * A. Receiver
   * B. Processor
   * C. Exporter
   * D. Connector

4. **Metrik apa yang paling krusial untuk mengukur responsivitas interaksi developer saat menggunakan model streaming LLM?**
   * A. Disk IOPS pada server database.
   * B. Time-to-First-Token (TTFT) di level klien.
   * C. Rasio kompresi header HTTP/2.
   * D. Durasi cold-start kontainer backend.

5. **Apa fungsi utama dari Error Taxonomy dalam SDK Platform AI?**
   * A. Mengganti semua pesan error dengan kode angka biner.
   * B. Mengubah seluruh error 500 menjadi 200 OK agar monitoring terlihat stabil.
   * C. Mengelompokkan kegagalan ke dalam kategori actionable deterministik agar developer dan sistem otomasi dapat mengambil langkah resolusi yang tepat.
   * D. Menyembunyikan stack trace asli dari pengembang.

---

### Bagian B: Intermediate (Analisis Singkat)

6. Jelaskan perbedaan mendasar antara *Infrastructure Observability* (APM) dan *Developer Experience (DX) Observability*.
7. Mengapa pengiriman data telemetri SDK wajib dirancang dengan pola *asynchronous non-blocking* dan *fail-silent*?
8. Bagaimana implementasi *Client-Side Exponential Backoff with Jitter* membantu mengurangi friksi pengembang saat terjadi error *HTTP 429 Rate Limit (TPM/RPM)*?
9. Apa risiko terbesar menggunakan pendekatan *Dynamic In-Console Error Hints* yang bergantung pada query API secara synchronous ketika aplikasi pengembang mengalami crash?
10. Sebutkan 3 dimensi data anonim yang aman dikumpulkan dari environment lokal pengembang untuk membantu debugging SDK lintas platform!

---

### Bagian C: Skenario Kasus Produksi

11. **Skenario 1:** Sebuah tim pengembang melaporkan bahwa aplikasi agen AI mereka mengalami *freeze* (macet) secara acak setelah menjalankan streaming selama 2 menit pada lingkungan serverless (AWS Lambda). Di dashboard server backend, status tercatat `HTTP 200 OK Chunked`. Komponen SDK apa yang kemungkinan besar tidak diimplementasikan dengan benar pada transport layer, dan bagaimana cara memvalidasinya menggunakan telemetri DX?
12. **Skenario 2:** Setelah merilis model penalaran baru (*Reasoning Model*), volume keluhan developer meningkat karena latensi token pertama mencapai 12 detik. Developer mengira SDK mengalami crash/hang dan membatalkan proses secara manual (*SIGINT*). Bagaimana Anda mendesain ulang arsitektur DX SDK untuk mengelola ekspektasi pengembang selama fase "thinking/reasoning" tanpa mengubah model backend?
13. **Skenario 3:** Platform Anda melayani integrasi autonomous agents yang berjalan dalam workflow multi-turn (100+ putaran iterasi). Banyak pengembang mengalami kegagalan di tengah eksekusi karena akumulasi history token melebihi limit model. Rancang strategi arsitektur SDK *Local Context Pruning Warning* yang mampu memitigasi kegagalan ini sebelum panggilan HTTP dieksekusi.

---

### Kunci Jawaban & Panduan Penilaian Quiz

#### Bagian A
1. **B** — TTFHW mengukur journey end-to-end developer dari akuisisi hingga eksekusi berhasil pertama kali.
2. **C** — Masalah privasi, kepatuhan regulasi, dan perlindungan kerahasiaan data developer adalah prioritas mutlak (*Zero-PII*).
3. **B** — Processor (misalnya `attributesprocessor` atau `filterprocessor`) berfungsi memanipulasi data span/metrik sebelum dikirim ke exporter.
4. **B** — TTFT mengukur jeda waktu riil yang dirasakan developer/klien antara pengiriman request hingga chunk token pertama muncul.
5. **C** — Taksonomi error mengonversi error mentah menjadi kategori terstruktur untuk memudahkan resolusi manual maupun terprogram.

#### Bagian B
6. APM berfokus pada kesehatan server/infrastruktur (CPU, pod, DB query). DX Observability berfokus pada perjalanan developer (keberhasilan eksekusi kode klien, TTFHW, utilisasi fitur SDK, kejelasan penanganan error lokal).
7. Jika telemetri berjalan synchronous, latensi pengembang akan terdegradasi. Jika telemetri melempar exception saat collector down (*fail-loud*), aplikasi developer akan rusak hanya karena sistem analitik internal bermasalah.
8. Exponential backoff mencegah penumpukan request beruntun (*thundering herd problem*), sementara penambahan random jitter mencegah ribuan SDK klien mencoba kembali (*retry*) di milidetik yang sama secara serentak.
9. Jika API dynamic hints mengalami downtime atau lambat saat developer sedang down, aplikasi developer akan mengalami double-fault latency atau hang sekunder di exception handling block.
10. Tiga dimensi aman: (1) Versi runtime bahasa (e.g., Python 3.11.4), (2) Nama/Arsitektur OS (e.g., Linux x86_64), (3) Versi library SDK klien (e.g., v2.4.0).

#### Bagian C (Rubrik Penilaian Skenario)
11. **Analisis Solusi:** Penyebab utama adalah ketiadaan penanganan *keep-alive / heartbeat chunks* atau buffer read timeout pada transport layer HTTP stream di environment yang membatasi durasi execution context seperti Lambda. Validasi telemetri DX dilakukan dengan memeriksa span event: ketiadaan event `chunk_received` selama interval waktu tertentu diikuti span status `ABORT` membuktikan TCP connection mati tanpa graceful termination handling.
12. **Analisis Solusi:** Mengimplementasikan *Heartbeat/Thinking State Event Stream*. SDK klien diubah agar saat backend masuk dalam fase reasoning, backend mengirimkan event SSE khusus (misal: `event: ping` atau `event: thought_delta`). SDK mendengarkan event ini dan mengekspos callback `onThinking(progress)` ke developer, sehingga terminal/UI developer menampilkan status interaktif (indikator progres) dan mencegah asumsi bahwa proses crash.
13. **Analisis Solusi:** Implementasi pre-flight tokenizer di SDK. SDK menyematkan local tokenizer engine (misal berbasis tiktoken/BPE) yang menghitung token count sebelum request dikirim. Jika kalkulasi mendekati ambang batas tertentu (misal 90% dari window limit model target), SDK secara otomatis memicu event interceptor `devrel.friction.context_warning`, mengeluarkan log peringatan yang dapat ditindaklanjuti, dan secara opsional menyediakan strategi reduksi riwayat (*sliding window summary*) sesuai opsi konfigurasi developer.

---

## 16. Summary

* **Developer Relations adalah Rekayasa Sistem:** Platform engineering modern tidak lagi memisahkan dokumentasi dari runtime kode. Pengalaman pengembang dapat diukur, diinstrumentasi, dan dioptimalkan menggunakan teknik keandalan sistem terdistribusi.
* **Prinsip Zero-PII:** Kunci utama observabilitas SDK adalah pemisahan ketat antara metadata performa/eksekusi dan data payload sensitif milik pengembang.
* **Closed-Loop Friction Automation:** Deteksi error SDK secara otomatis yang terhubung ke perbaikan dokumentasi real-time dan issue tracker internal menurunkan biaya retensi developer secara signifikan pada platform AI/Agentic.