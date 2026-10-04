# Bab 02: Developer Experience & Product Friction Engineering
## Module 01: Architecting Zero-Friction Developer Workflows for AI Agent Platforms: Local-First Simulation, Deterministic Sandboxing, and Telemetry-Driven Friction Auditing

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mendiagnosis dan Mengukur Friction Metric**: Mengidentifikasi titik friksi kognitif dan teknis dalam siklus adopsi SDK agen AI, serta mengimplementasikan metrik *Time-to-First-Token* (TTFT), *Time-to-First-Agent-Resolution* (TTFAR), dan *Error Cascade Rate* pada pipeline analitik Developer Experience (DX).
2. **Merancang Deterministic Mock/Replay Engine**: Mengembangkan *middleware proxy* lokal berbasis Python untuk merekam (*record*), menyaring (*sanitize*), dan memutar ulang (*replay*) interaksi streaming LLM multi-turn dan eksekusi tool calling tanpa dependensi jaringan eksternal.
3. **Mengeliminasi Non-Deterministik pada Testing Loop**: Membangun mekanisme *semantic caching* dan *virtual clock sandboxing* untuk menguji logika reaktif autonomous agent secara independen dari latensi penyedia model dan fluktuasi biaya API.
4. **Mengimplementasikan Ergonomi Error Handling Otomatis**: Merekayasa SDK parser yang mengubah HTTP status error generik dari model gateway (e.g., 429, 500, 503) dan JSON parsing failure dari LLM output menjadi pesan diagnostik yang terstruktur, dapat ditindaklanjuti (*actionable remediation hints*), dan terintegrasi dengan CLI tooling.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Developer Experience (DX) pada ekosistem *AI Data & Autonomous Agents* berada pada titik temu antara *Systems Engineering*, *Human-Computer Interaction (HCI)*, dan *Stochastic Computing*. Tidak seperti rekayasa perangkat lunak tradisional di mana antarmuka API bersifat deterministik dan biner (sukses atau gagal), integrasi model AI memperkenalkan dimensi ketidakpastian (*stochasticity*), latensi arbitrer, dan biaya per pemanggilan (*cost-per-execution*).

```
   TRADITIONAL DX FEEDBACK LOOP
   [Code] ---> [Compile/Lint] ---> [Local Unit Test] ---> [Instant Pass/Fail] (Latency: < 500ms)

   AI/AGENT DX FEEDBACK LOOP (WITHOUT INTERVENTION)
   [Prompt/Code] ---> [Network Call] ---> [LLM Gen (Stochastic)] ---> [Tool Call] ---> [Eval Parser]
        ^                                                                                    |
        |----------------------- Latency: 5s - 45s (Cost: $$$) -----------------------------|
```

Ketika *friction* ini tidak ditangani, pengembang mengalami degradasi *flow state*. Terdapat tiga pilar friksi utama dalam rekayasa agen otonom:

1. **Environmental Friction**: Kompleksitas konfigurasi awal (kredensial API eksternal, limit kuota/rate limits, dependensi vector store lokal, dan runtime runtime Python/Node yang rapuh).
2. **Execution Non-Determinism Friction**: Pengujian unit menjadi *flaky* karena respons model berubah-ubah, menyebabkan pengembang kesulitan membedakan antara bug pada logika agen mereka versus variasi sampling temperatur model.
3. **Diagnostic Invisibility Friction**: Pesan kesalahan model yang ambigu (misalnya respons JSON yang terpotong di tengah stream tanpa jejak token usage) memaksa developer melakukan debugging manual melalui console logging parsial.

**Mental Model: The "Zero-Stochasticity Local Loop"**
Prinsip dasar modul ini adalah memisahkan logika orkestrasi agen dari penyedia inferensi selama fase pengembangan aktif (*inner loop development*). Dengan mengisolasi interaksi inferensi ke dalam *sandbox replay layer* deterministik, loop umpan balik dipangkas dari hitungan menit menjadi milidetik, sementara biaya pengujian ditekan menjadi nol.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada skala enterprise, friksi pengembang bukan sekadar masalah kenyamanan; ini adalah beban finansial dan risiko operasional langsung:

* **Eksplosi Biaya Cloud Dev-Loop**: Sebuah tim yang beranggotakan 50 insinyur yang menguji loop multi-agent (misal: AutoGen, CrewAI, LangGraph) secara langsung terhadap GPT-4o dapat menghabiskan ribuan dolar per hari hanya untuk verifikasi sintaks lokal dan eksekusi integrasi dasar.
* **Onboarding Drag**: Rata-rata *Time-to-First-Working-Agent* di industri sering kali melampaui 4 jam akibat manajemen secret yang rumit, dependensi C++ native pada vector store binding, dan dokumentasi API yang tidak sinkron. Enterprise membutuhkan onboarding time di bawah 10 menit (*Golden Path*).
* **CI/CD Flakiness**: Pipeline continuous integration yang memanggil endpoint model publik rentan terhadap *rate-limiting (HTTP 429)*, degradasi performa penyedia cloud (p99 latency spikes), dan kegagalan assertions acak, yang menyebabkan pipeline deployment sering diblokir (*false positives*).
* **Kebocoran Data Sensitif Developer**: Pengembang yang frustrasi sering kali menonaktifkan validasi keamanan atau menempelkan API key production ke konfigurasi lokal mereka demi mempercepat debugging.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur DX engine ini mengintersepsi semua komunikasi jaringan antara Agent Core Runtime dan Provider Model eksternal menggunakan arsitektur *Local Proxy with Dynamic Mode Switching* (Record, Replay, Live Passthrough).

```
+---------------------------------------------------------------------------------------+
|                                    DEVELOPER WORKSPACE                                |
|                                                                                       |
|   +-----------------------+           HTTP / gRPC            +--------------------+   |
|   |                       | -------------------------------> |                    |   |
|   |  Autonomous Agent     |                                  |  DX Engine Proxy   |   |
|   |  Framework (LangGraph | <------------------------------- |  (AgentDevProxy)   |   |
|   |  / LlamaIndex / Raw)  |    Deterministic SSE Stream      |                    |   |
|   +-----------------------+                                  +---------+----------+   |
|                                                                        |              |
+------------------------------------------------------------------------|--------------+
                                                                         |
                      +--------------------------------------------------+
                      |
                      v Mode Decision
         +------------+------------+
         |                         |
    [MODE: REPLAY]           [MODE: RECORD / PASSTHROUGH]
         |                         |
         v                         v
+------------------+     +--------------------+
|  Deterministic   |     | Redaction & Token  |
|  Cassette Store  |     | Normalizer Engine  |
|  (Local SQLite / |     +---------+----------+
|   JSONL Cache)   |               |
+------------------+               v
                         +--------------------+       WAN        +------------------+
                         | Upstream Transport | ---------------> | Remote Model API |
                         | (HTTPX/Streaming)  | <--------------- | (OpenAI/Anthropic|
                         +--------------------+    Raw Events    |  /Bedrock Engine)|
                                   |                             +------------------+
                                   v
                         +--------------------+
                         | Friction Telemetry |
                         | Collector (OTel)   |
                         +--------------------+
```

#### Komponen Utama:
1. **AgentDevProxy**: Proxy HTTP lokal berbasis ASGI yang mengarahkan panggilan API model berdasarkan status cache (`RECORD`, `REPLAY`, `PASSTHROUGH`).
2. **Redaction & Normalizer Engine**: Mengidentifikasi dan menyamarkan data rahasia (API Keys, PII) sebelum disimpan ke disk, serta menormalkan timestamps dan chunk ID agar respons replay bersifat deterministik.
3. **Deterministic Cassette Store**: Penyimpanan berbasis hash dari payload input (prompt, system message, tools definition, model parameters) untuk pencarian respons instan ($O(1)$) tanpa latensi jaringan.
4. **Friction Telemetry Collector**: Mengukur metrik internal (latensi sintesis, kegagalan decoding, format payload yang tidak valid) dan mengekspornya ke format trace OpenTelemetry lokal.

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Mekanisme Deterministic Semantic Replay
Untuk menjamin determinisme dalam streaming LLM:
1. **Fingerprinting**: Input yang dikirimkan oleh agen di-serialisasi secara kanonikal. Urutan keys pada JSON distandarisasi, whitespace dinormalisasi, dan hyperparameter yang mempengaruhi output (seperti `seed`, `temperature`, `top_p`) diikutsertakan dalam pembentukan *Request Signature Hash* (SHA-256).
2. **Cassette Generation**: Pada mode `RECORD`, respon SSE (*Server-Sent Events*) ditangkap chunk-per-chunk bersama dengan inter-chunk delay metrics. Cassette menyimpan seluruh deret token stream.
3. **Virtual Latency Injection**: Pada mode `REPLAY`, proxy dapat memutar kembali stream secara instan (untuk unit test) atau dengan menyuntikkan *virtual simulated latency* (untuk menguji UI loader dan penanganan timeout agen di sisi klien).

#### B. Ergonomi SDK & Remediasi Kesalahan Proaktif
Pendekatan konvensional mengekspos error API mentah langsung ke developer:
```json
{"error": {"message": "Invalid schema for function 'execute_sql': ...", "type": "invalid_request_error"}}
```
Arsitektur DX modern mengimplementasikan middleware parsing yang menganalisis konteks eksekusi dan menyajikan solusi yang dapat dieksekusi (*actionable diagnostic*):
1. **Context Extraction**: Melacak skema fungsi yang didaftarkan versus ekspektasi parameter model.
2. **Diff Synthesis**: Mengkalkulasi Levenshtein distance atau JSON-schema diff antara output yang diantisipasi dan output yang dihasilkan.
3. **Terminal Rendering**: Menyajikan terminal callout box yang berisi instruksi perbaikan konkret, tautan dokumentasi lokal, dan koreksi parameter otomatis.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistematis dari proxy DX lokal deterministik dan friction tracer menggunakan Python 3.11+, `httpx`, `pydantic`, dan antarmuka ASGI berbasis `starlette`.

#### Struktur Berkas:
```
dx_engine/
├── core/
│   ├── __init__.py
│   ├── hasher.py
│   └── telemetry.py
├── storage/
│   └── cassette.py
└── proxy/
    └── server.py
```

#### `dx_engine/core/hasher.py`
```python
"""
Hash canonicalization module for deterministic LLM payload identification.
"""

from __future__ import annotations
import hashlib
import json
from typing import Any, Dict


class PayloadCanonicalizer:
    @staticmethod
    def canonicalize(data: Dict[str, Any]) -> str:
        """
        Transforms an arbitrary dictionary into a deterministic JSON string.
        Strips non-deterministic variables (e.g., dynamic request IDs).
        """
        def _sort_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: _sort_recursive(v) for k, v in sorted(obj.items())}
            if isinstance(obj, list):
                return [_sort_recursive(item) for item in obj]
            return obj

        clean_data = {k: v for k, v in data.items() if k not in ("client_timestamp", "request_id")}
        sorted_data = _sort_recursive(clean_data)
        return json.dumps(sorted_data, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def generate_fingerprint(cls, payload: Dict[str, Any]) -> str:
        """Generates an immutable SHA-256 hash from a canonicalized payload."""
        canonical_str = cls.canonicalize(payload)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
```

#### `dx_engine/core/telemetry.py`
```python
"""
Developer Friction Telemetry tracking and metrics aggregation.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DiagnosticEvent:
    timestamp: float
    error_code: str
    remediation_hint: str
    traceback_context: Optional[str] = None


@dataclass
class FrictionMetrics:
    time_to_first_chunk_ms: float = 0.0
    total_duration_ms: float = 0.0
    token_count: int = 0
    replay_hit: bool = False
    diagnostics: List[DiagnosticEvent] = field(default_factory=list)


class DeveloperMetricsTracker:
    def __init__(self) -> None:
        self.start_time: float = 0.0
        self.first_token_time: Optional[float] = None
        self.metrics = FrictionMetrics()

    def mark_start(self) -> None:
        self.start_time = time.perf_counter()

    def mark_first_chunk(self) -> None:
        if self.first_token_time is None:
            self.first_token_time = time.perf_counter()
            self.metrics.time_to_first_chunk_ms = (self.first_token_time - self.start_time) * 1000

    def mark_completion(self, token_count: int, replay_hit: bool) -> FrictionMetrics:
        end_time = time.perf_counter()
        self.metrics.total_duration_ms = (end_time - self.start_time) * 1000
        self.metrics.token_count = token_count
        self.metrics.replay_hit = replay_hit
        return self.metrics

    def record_friction_point(self, error_code: str, hint: str, context: Optional[str] = None) -> None:
        self.metrics.diagnostics.append(
            DiagnosticEvent(
                timestamp=time.time(),
                error_code=error_code,
                remediation_hint=hint,
                traceback_context=context,
            )
        )
```

#### `dx_engine/storage/cassette.py`
```python
"""
Local deterministic cassette persistence storage.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class CassetteStore:
    def __init__(self, storage_dir: str = ".agent_cassettes") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, fingerprint: str) -> Path:
        return self.storage_dir / f"{fingerprint}.json"

    def exists(self, fingerprint: str) -> bool:
        return self._get_path(fingerprint).is_file()

    def save(self, fingerprint: str, request_payload: Dict[str, Any], chunks: List[str]) -> None:
        """Saves interaction chunks without exposing API secrets."""
        file_path = self._get_path(fingerprint)
        sanitized_payload = self._sanitize(request_payload)
        data = {
            "fingerprint": fingerprint,
            "request": sanitized_payload,
            "response_chunks": chunks,
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, fingerprint: str) -> Optional[List[str]]:
        file_path = self._get_path(fingerprint)
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("response_chunks", [])

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redacts sensitive credentials from recorded fixtures."""
        sanitized = data.copy()
        if "headers" in sanitized:
            headers = sanitized["headers"].copy()
            for auth_key in ("authorization", "x-api-key", "api-key"):
                if auth_key in headers:
                    headers[auth_key] = "[REDACTED_DEV_KEY]"
            sanitized["headers"] = headers
        return sanitized
```

#### `dx_engine/proxy/server.py`
```python
"""
ASGI Proxy Implementation for Deterministic Agent Local Testing.
"""

from __future__ import annotations
import asyncio
import json
import logging
from enum import Enum
from typing import AsyncGenerator

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from dx_engine.core.hasher import PayloadCanonicalizer
from dx_engine.core.telemetry import DeveloperMetricsTracker
from dx_engine.storage.cassette import CassetteStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DXEngineProxy")


class EngineMode(str, Enum):
    RECORD = "RECORD"
    REPLAY = "REPLAY"
    PASSTHROUGH = "PASSTHROUGH"


class AgentDevProxyServer:
    def __init__(
        self,
        upstream_url: str = "https://api.openai.com",
        mode: EngineMode = EngineMode.REPLAY,
        simulate_network_delay: bool = False,
    ) -> None:
        self.upstream_url = upstream_url.rstrip("/")
        self.mode = mode
        self.simulate_network_delay = simulate_network_delay
        self.cassette_store = CassetteStore()
        self.app = Starlette(
            routes=[
                Route("/v1/chat/completions", endpoint=self.handle_completions, methods=["POST"]),
                Route("/healthz", endpoint=self.health_check, methods=["GET"]),
            ]
        )

    async def health_check(self, _: Request) -> JSONResponse:
        return JSONResponse({"status": "active", "mode": self.mode.value})

    async def handle_completions(self, request: Request) -> Response:
        tracker = DeveloperMetricsTracker()
        tracker.mark_start()

        try:
            body_bytes = await request.body()
            body_json = json.loads(body_bytes.decode("utf-8"))
        except json.JSONDecodeError as err:
            tracker.record_friction_point(
                error_code="ERR_DX_INVALID_JSON",
                hint="Check client serialization. Body must be well-formed JSON.",
                context=str(err),
            )
            return JSONResponse(
                {
                    "error": {
                        "message": "DX Proxy: Malformed JSON payload received.",
                        "type": "developer_experience_error",
                        "hint": "Verify your SDK serializer configurations.",
                    }
                },
                status_code=400,
            )

        fingerprint = PayloadCanonicalizer.generate_fingerprint(body_json)
        logger.info(f"Target Fingerprint: {fingerprint} | Mode: {self.mode.value}")

        if self.mode == EngineMode.REPLAY:
            if not self.cassette_store.exists(fingerprint):
                error_msg = f"Cassette missing for hash {fingerprint}. Run in RECORD mode first."
                tracker.record_friction_point("ERR_DX_CACHE_MISS", error_msg)
                return JSONResponse(
                    {
                        "error": {
                            "message": error_msg,
                            "type": "replay_miss_exception",
                            "resolution": "Set DX_PROXY_MODE=RECORD and execute workflow once.",
                        }
                    },
                    status_code=412,
                )
            return self._stream_replay(fingerprint, tracker)

        if self.mode in (EngineMode.RECORD, EngineMode.PASSTHROUGH):
            return await self._execute_upstream(request, body_json, fingerprint, tracker)

        return JSONResponse({"error": {"message": "Invalid proxy operational mode."}}, status_code=500)

    def _stream_replay(self, fingerprint: str, tracker: DeveloperMetricsTracker) -> StreamingResponse:
        chunks = self.cassette_store.load(fingerprint) or []

        async def generator() -> AsyncGenerator[bytes, None]:
            token_count = 0
            for idx, chunk in enumerate(chunks):
                if idx == 0:
                    tracker.mark_first_chunk()
                if self.simulate_network_delay:
                    await asyncio.sleep(0.01)  # Simulate 10ms network frame
                token_count += 1
                yield chunk.encode("utf-8")
            metrics = tracker.mark_completion(token_count=token_count, replay_hit=True)
            logger.info(f"Replay complete: {metrics.token_count} chunks in {metrics.total_duration_ms:.2f}ms")

        return StreamingResponse(generator(), media_type="text/event-stream")

    async def _execute_upstream(
        self,
        original_request: Request,
        body_json: dict,
        fingerprint: str,
        tracker: DeveloperMetricsTracker,
    ) -> Response:
        target_url = f"{self.upstream_url}/v1/chat/completions"
        headers = dict(original_request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)

        client = httpx.AsyncClient(timeout=60.0)
        chunks_recorded: list[str] = []

        try:
            req = client.build_request("POST", target_url, headers=headers, json=body_json)
            res = await client.send(req, stream=True)

            if res.status_code != 200:
                error_content = await res.aread()
                await res.aclose()
                await client.aclose()
                tracker.record_friction_point(
                    error_code=f"UPSTREAM_ERR_{res.status_code}",
                    hint="Check upstream API status and credentials.",
                    context=error_content.decode("utf-8", errors="ignore"),
                )
                return Response(
                    content=error_content,
                    status_code=res.status_code,
                    media_type=res.headers.get("content-type", "application/json"),
                )

            async def stream_recorder() -> AsyncGenerator[bytes, None]:
                token_count = 0
                try:
                    async for chunk in res.aiter_text():
                        if token_count == 0:
                            tracker.mark_first_chunk()
                        token_count += 1
                        chunks_recorded.append(chunk)
                        yield chunk.encode("utf-8")
                finally:
                    await res.aclose()
                    await client.aclose()
                    metrics = tracker.mark_completion(token_count=token_count, replay_hit=False)
                    if self.mode == EngineMode.RECORD:
                        self.cassette_store.save(
                            fingerprint=fingerprint,
                            request_payload={"headers": headers, "body": body_json},
                            chunks=chunks_recorded,
                        )
                        logger.info(f"Recorded {len(chunks_recorded)} chunks to cache. Latency: {metrics.total_duration_ms:.2f}ms")

            return StreamingResponse(
                stream_recorder(),
                media_type=res.headers.get("content-type", "text/event-stream"),
            )

        except Exception as exc:
            await client.aclose()
            tracker.record_friction_point("ERR_UPSTREAM_FAILURE", str(exc))
            return JSONResponse(
                {"error": {"message": f"Transport layer error: {str(exc)}", "type": "gateway_timeout"}},
                status_code=504,
            )
```

---

### 7. Edge Cases & Failure Modes

Pada implementasi proxy deterministik dan sandboxing agen, sejumlah edge case teknis harus ditangani:

| Skenario Edge Case | Potensi Kegagalan | Strategi Mitigasi / Penanganan |
| :--- | :--- | :--- |
| **Token Streaming Truncation** | Klien menutup koneksi HTTP sebelum generator stream upstream selesai memancarkan data (misal: developer menekan `Ctrl+C`). | Implementasikan blok `try...finally` pada generator asynchronous untuk mencegah penyimpanan cassette parsial (*corrupted cache*). Simpan hanya jika frame `[DONE]` diterima. |
| **Volatile Field Injection** | Framework agen secara otomatis menyertakan `timestamp`, `session_uuid`, atau dynamic variable ke dalam system prompt. | Proxy harus mengeksekusi normalisasi payload dengan *Regex Regex Stripping* atau JSON path exclusion khusus untuk mengidentifikasi dan membersihkan dynamic runtime tokens sebelum fingerprinting SHA-256. |
| **Large Payload Memory Exhaustion** | Model konteks besar (e.g., 128k - 1M token) membanjiri buffer RAM proxy selama operasi recording stream. | Gunakan buffer disk berbasis temporary chunk streaming alih-alih list memory murni (`collections.deque` dengan sliding limit atau flush berkala ke intermediate tempfiles). |
| **Secret Leakage in Artifacts** | API Key yang dikirimkan via custom header atau bearer token terekam dalam file rekaman lokal dan terunggah ke remote repository git. | Filter secara ketat header dan metadata payload dengan `_sanitize()` routine sebelum persistensi disk, serta sediakan berkas template `.gitignore` secara default yang memblokir folder `.agent_cassettes/`. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan desain dalam rekayasa Developer Experience memiliki trade-off performa, biaya, dan kemudahan penggunaan:

```
[Simulasi Murni / Mocking] <---------> [Deterministic Replay] <---------> [Live Local Models (Ollama)]
         |                                     |                                     |
   Ultra Cepat (<5ms)                  Presisi Tinggi (1:1)                  Otonom Penuh Offline
   Tidak Realistis                     Perlu Perekaman Awal                  Konsumsi CPU/VRAM Berat
```

#### Evaluasi Komparatif Arsitektur DX:

1. **Deterministic Replay Proxy (Pilihan Implementasi Ini)**
   * **Pros**: Menghasilkan respon 100% identik dengan provider kelas industri (e.g., Claude 3.5 Sonnet, GPT-4o) tanpa fluktuasi; nol pemakaian CPU/GPU lokal; latency nol; biaya $0 pada iterasi berikutnya.
   * **Cons**: Membutuhkan satu kali cold run melalui internet untuk setiap variasi prompt/state baru.

2. **Local SLM In-the-Loop (e.g., Ollama / Llama.cpp)**
   * **Pros**: Tidak memerlukan koneksi jaringan luar sama sekali sejak awal; dapat merespons skenario dinamis baru di luar set rekaman.
   * **Cons**: Kebutuhan resource komputasi lokal tinggi (RAM/VRAM); kapasitas penalaran (*reasoning*) model lokal kecil sering gagal memenuhi format structured JSON/tool-calling yang kompleks dari agen enterprise, menimbulkan friksi debugging palsu.

3. **In-Memory Static Stubs (Unit Mocking)**
   * **Pros**: Paling sederhana; tidak memerlukan proxy server tambahan.
   * **Cons**: Rapuh terhadap perubahan kontrak skema provider; gagal mensimulasikan chunk frame delays, SSE lifecycle events, dan transient failure modes.

---

### 9. Best Practices & Standard Industri

Mengacu pada arsitektur sistem pengembang modern (seperti standar implementasi internal GitHub, Stripe, dan OpenAI):

* **Fail Early with Prescriptive Errors**: Error message tidak boleh hanya memberi tahu *apa* yang salah, tetapi harus menyertakan *tindakan langsung untuk memperbaikinya*. Sertakan flag CLI atau command string yang dapat di-copy-paste langsung oleh developer.
* **Hermetic Local Sandboxing**: Siklus pengujian lokal developer (*inner dev loop*) tidak boleh bergantung pada status jaringan publik. Penerapan *ephemeral cassette stores* menjamin pipeline CI/CD deterministik tanpa flakiness.
* **PII & Credential Redaction Protocol**: Semua rekaman jaringan lokal harus dianggap sebagai artefak yang berpotensi terekspos. Lakukan zeroization pada field sensitif (`Bearer ey...`, `sk-ant-...`) sebelum menyentuh storage persistence layer.
* **Standardized Telemetry Schema**: Pancarkan metrik DX menggunakan semantik OpenTelemetry dengan attributes:
  * `dev.session.id`: UUID unik dari sesi pengembangan lokal.
  * `ai.provider.model`: Model yang disimulasikan.
  * `dx.friction.error_code`: Kode error spesifik untuk tracking friction rate tim.
  * `dx.latency.first_token_ms`: Waktu respons awal stream.

---

### 10. Hands-on Lab Exercise

Tujuan lab ini: Menyiapkan proxy lokal, merekam satu alur eksekusi agen (tool call + final answer), dan memutarnya kembali secara deterministik dengan pemutusan total akses jaringan luar.

#### Langkah 1: Inisialisasi Environment
Buat environment terisolasi dan pasang dependensi:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install httpx starlette uvicorn pydantic
```

#### Langkah 2: Buat Skrip Bootstrapping Proxy
Simpan kode proxy dari Bagian 6 ke dalam direktori kerja Anda, lalu buat launcher `run_proxy.py`:
```python
# run_proxy.py
import os
import uvicorn
from dx_engine.proxy.server import AgentDevProxyServer, EngineMode

mode_str = os.getenv("DX_MODE", "RECORD").upper()
proxy_server = AgentDevProxyServer(
    upstream_url="https://api.openai.com",
    mode=EngineMode(mode_str),
    simulate_network_delay=True
)

if __name__ == "__main__":
    uvicorn.run(proxy_server.app, host="127.0.0.1", port=8080, log_level="warning")
```

#### Langkah 3: Eksekusi Mode Perekaman (Record Mode)
1. Ekspor API key asli dan jalankan server pada terminal pertama:
   ```bash
   export OPENAI_API_KEY="sk-proj-YOUR_ACTUAL_API_KEY_HERE"
   export DX_MODE="RECORD"
   python run_proxy.py
   ```
2. Pada terminal kedua, jalankan pemanggilan inferensi sederhana melalui proxy:
   ```bash
   curl -X POST http://127.0.0.1:8080/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $OPENAI_API_KEY" \
     -d '{
       "model": "gpt-4o",
       "messages": [{"role": "user", "content": "Explain Developer Friction in 5 words."}],
       "temperature": 0.0,
       "stream": true
     }'
   ```
3. Amati keluaran terminal: Proxy akan merekam seluruh response chunks ke dalam subdirektori `.agent_cassettes/`.

#### Langkah 4: Eksekusi Mode Deterministic Replay (Offline Test)
1. Matikan koneksi internet Anda atau gunakan invalid API key.
2. Hentikan proxy (`Ctrl+C`), ubah mode ke `REPLAY`, lalu jalankan kembali:
   ```bash
   export OPENAI_API_KEY="sk-dummy-invalid-key"
   export DX_MODE="REPLAY"
   python run_proxy.py
   ```
3. Eksekusi kembali perintah `curl` yang persis sama pada Terminal 2:
   ```bash
   curl -X POST http://127.0.0.1:8080/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $OPENAI_API_KEY" \
     -d '{
       "model": "gpt-4o",
       "messages": [{"role": "user", "content": "Explain Developer Friction in 5 words."}],
       "temperature": 0.0,
       "stream": true
     }'
   ```

#### Indikator Keberhasilan:
* Payload streaming kembali secara instan tanpa melakukan koneksi jaringan eksternal ke upstream OpenAI.
* Authorization header palsu (`sk-dummy-invalid-key`) tidak ditolak oleh proxy selama fingerprint payload request identik dengan rekaman yang ada di `.agent_cassettes/`.
* Waktu eksekusi drop dari rata-rata >1500ms menjadi <50ms. Metrik latensi tercetak dengan rapi pada terminal proxy.