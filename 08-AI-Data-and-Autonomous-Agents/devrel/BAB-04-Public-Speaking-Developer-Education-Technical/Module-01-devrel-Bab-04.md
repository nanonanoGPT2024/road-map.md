# Bab 04: Public Speaking, Developer Education & Technical Demos
## Modul 01: Arsitektur Demo Teknis Deterministik & Resilien untuk Sistem AI dan Autonomous Agents

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Live Demo Multi-Tier:** Membangun harness demo teknis untuk sistem *autonomous agent* yang kebal terhadap kegagalan jaringan panggung, lonjakan latensi inferensi, dan limitasi kuota API (*rate-limiting*).
- **Mengimplementasikan Deterministic Replay Engine (VCR Pattern untuk AI):** Menerapkan mekanisme interceptor I/O asinkron yang mampu beralih secara transparan (*zero-downtime failover*) antara inferensi model *live* dan rekaman eksekusi deterministik ketika anomali terdeteksi.
- **Membangun Pipeline Visualisasi Telemetri Kognitif:** Mengembangkan antarmuka streaming berbasis Server-Sent Events (SSE) atau WebSockets untuk mengekspos *reasoning loop*, pemanggilan *tool/function*, dan state transisi *agent* secara *real-time* guna mengurangi *cognitive load* audiens.
- **Mengeksekusi Pedagogical Live-Coding Scaffolding:** Menerapkan metodologi reduksi kode bertingkat (*progressive disclosure*) untuk mendemonstrasikan orkestrasi agentik yang kompleks dalam durasi presentasi 15–45 menit tanpa mengorbankan integritas arsitektural.

---

### 2. Concept Overview

Mempresentasikan sistem berbasis kecerdasan buatan dan *autonomous agents* kepada audiens teknis (insinyur perangkat lunak, arsitek sistem, data scientist) menghadirkan paradoks fundamental: **sifat non-deterministik model AI bertentangan langsung dengan kebutuhan determinisme presentasi langsung (*live demo*)**.

```
       [ Live AI / Agent Demo Paradox ]
       
   Ekspektasi Audiens                Realitas Sistem AI
┌─────────────────────────┐        ┌─────────────────────────┐
│ • Hasil cepat (<2s)     │   VS   │ • Latensi tinggi (>10s) │
│ • Hasil konsisten       │        │ • Output probabilistik  │
│ • Zero failure rate     │        │ • Hallucination/429/500 │
│ • Struktur jelas/linear │        │ • Tool loops rekursif   │
└─────────────────────────┘        └─────────────────────────┘
```

Untuk menjembatani jurang ini, Developer Relations (DevRel) Engineer spesialisasi AI/Agentic Systems harus menerapkan **Mental Model Tiga Lapis Ketahanan Demo (Three-Tier Demo Reliability Pipeline)**:

1. **Tier 1 (The Live Wire):** Eksekusi langsung ke penyedia Foundation Model (OpenAI, Anthropic, OSS local via vLLM/Ollama). Menghadirkan otentisitas maksimal namun memiliki tingkat kerentanan tertinggi terhadap kegagalan jaringan panggung dan kehabisan kuota (*rate limits*).
2. **Tier 2 (The Semantic Cache & Shadow Replay):** Lapisan proksi transparan lokal yang mencocokkan input teks/payload secara semantik atau berbasis *hash deterministik*. Jika latensi Tier 1 melampaui batas toleransi (*SLA breach*), sistem melakukan *degradation* ke cache respons tervalidasi tanpa menginterupsi alur narasi.
3. **Tier 3 (The Synthetic Isolation Fallback):** *In-memory mock state machine* lokal yang menjamin simulasi *tool execution* dan *streaming generation* tetap berjalan 100% luring (*fully offline*) jika terjadi pemutusan total koneksi internet *venue*.

Dari perspektif pedagogi, modul ini mengadopsi **Cognitive Load Theory (Sweller)** dan **Dual-Coding Theory (Paivio)**. Audiens developer tidak dapat membaca terminal log teks berukuran 10 baris/detik sekaligus memahami narasi pembicara. Oleh karena itu, demo arsitektur agentic harus memisahkan *data path* (eksekusi model) dari *telemetry path* (visualisasi state mental agen) secara modular.

---

### 3. Why It Matters

Di lingkungan enterprise dan konferensi teknologi tier-1 (misal: AWS re:Invent, Google I/O, KubeCon, PyCon):
- **Biaya Kegagalan Panggung Sangat Tinggi:** *Outage* demo selama 60 detik di panggung keynote membunuh momentum produk, merusak reputasi keandalan platform, dan menurunkan rasio adopsi developer secara instan.
- **Ketidakpercayaan Developer terhadap "Smoke and Mirrors":** Audiens insinyur senior sangat skeptis terhadap video demo rekaman atau demo UI fiktif. Mereka menuntut live terminal, inspeksi payload jaringan, dan kode nyata. Jika terjadi error dan pembicara panik tanpa fallback sistematis, kredibilitas teknis runtuh.
- **Kompleksitas Debugging Agen:** Autonomous agents dapat terjebak dalam *infinite recursive tool execution loops* jika model gagal melakukan *early termination*. Mengandalkan API murni tanpa guardrail di panggung berisiko menampilkan agen yang membakar ribuan token tanpa memberikan jawaban akhir.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur **Resilient Live-Demo Harness** untuk Autonomous Agent yang memisahkan *Presenter Workspace*, *Local Resilient Proxy*, *External AI Infrastructure*, dan *Audience Visualizer UI*.

```
+---------------------------------------------------------------------------------------+
| PRESENTER ENVIRONMENT (MacBook / Linux Laptop)                                        |
|                                                                                       |
|   +-----------------------+           Tool Invocation          +------------------+   |
|   | Presenter CLI Script  | ---------------------------------> | Mock/Real Target |   |
|   | (Live-Coding Harness) |                                    | Environment      |   |
|   +-----------------------+                                    | (Docker / Local) |   |
|               |                                                +------------------+   |
|               | LLM Inference Requests (HTTP/SSE)                                     |
|               v                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   | RESILIENT DEMO PROXY (Port: 8080)                                             |   |
|   |                                                                               |   |
|   |   +------------------+      +-------------------+     +-------------------+   |   |
|   |   | Request Analyzer | ---> | Circuit Breaker & | --> | VCR Replay Engine |   |   |
|   |   | & Fingerprinter  |      | Latency Monitor   |     | (Cassette Cache)  |   |   |
|   |   +------------------+      +-------------------+     +-------------------+   |   |
|   |                                       |                         |             |   |
|   +---------------------------------------|-------------------------|-------------+   |
|                                           |                         |                 |
|                                           | Fallback to             | Cache Hit /     |
|                                           | Local Replay            | Offline Mode    |
|                                           v                         v                 |
+-------------------------------------------+-------------------------+-----------------+
      | (Live Stream via Internet)          |                         |
      v                                     v                         v
+-------------------------------+   +-----------------------------------------------+
| UPSTREAM AI PROVIDERS         |   | AUDIENCE VISUALIZER (Web UI / Terminal Split) |
| (OpenAI / Anthropic / Groq)   |   |                                               |
|                               |   | +-------------------------------------------+ |
|   - 429 Rate Limits?          |   | | Token Streaming Display (Real-time SSE)   | |
|   - Captive Portal Drop?      |   | +-------------------------------------------+ |
|   - High Inference Latency?   |   | | Agent Thought / Tool Execution Graph      | |
|                               |   | +-------------------------------------------+ |
|                               |   | | Network Health & Latency Telemetry Gauge  | |
+-------------------------------+   +-----------------------------------------------+
```

#### Alur Eksekusi Data:
1. Skrip demo presenter mengirimkan *prompt* atau *action payload* ke `Resilient Demo Proxy` lokal.
2. Proxy mengevaluasi konektivitas upstream dan kuota via *Circuit Breaker*.
3. Jika kondisi normal (`State: CLOSED`), request dialirkan langsung ke Upstream AI Provider, sembari merekam chunk respons secara asinkron ke *Cassette Storage*.
4. Jika latency upstream melewati ambang batas (`TIMEOUT > 3.0s`) atau menerima HTTP 429/5xx (`State: OPEN`), sistem secara transparan mengalihkan output ke *VCR Replay Engine*.
5. Seluruh tahapan inferensi (apakah itu live maupun replay) dialirkan ke antarmuka audiens via Server-Sent Events (SSE) dengan meta-tag penanda integritas untuk transparansi edukasional.

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Deterministic Replay & The VCR Interceptor
Pola VCR (*Video Cassette Recorder*) merekam interaksi HTTP/gRPC ke disk (biasanya serialisasi JSON/YAML) selama sesi latihan (*dry run*). Pada live demo, interceptor menghitung SHA-256 hash dari gabungan:
$$\text{Signature} = \text{SHA256}(\text{System Prompt} + \text{User Input} + \text{Tool Schemas} + \text{Temperature})$$
Jika hash tersebut cocok dengan data rekaman, dan flag `--demo-mode=hybrid` atau `--demo-mode=offline` aktif, proxy menyimulasikan transmisi chunk token demi token dengan latensi buatan (*artificial jitter*) berdistribusi normal, sehingga audiens tetap melihat efek pengetikan streaming alami (*natural typing cadence*).

#### B. Recursive Loop Guards pada Autonomous Agents
Autonomous agents yang menggunakan pola *ReAct* (Reasoning + Acting) rentan mengalami perulangan (*infinite loop*) saat model gagal memparsing keluaran JSON tool. Dalam skenario live demo, loop guard interceptor harus:
1. Membatasi kedalaman eksekusi (*max iterations*) secara mutlak (misal: $N=3$).
2. Menyediakan *deterministic escape hatch*: jika iterasi ke-3 gagal, engine langsung menyuntikkan pesan status yang telah disiapkan secara sintetik ke context window model untuk memaksanya menghasilkan jawaban akhir (*final answer*).

#### C. Progressive Disclosure dalam Live-Coding
Untuk meminimalkan *cognitive overload* saat mendemonstrasikan kode agen:
- **Level 1 (The Skeleton):** Menampilkan arsitektur tingkat tinggi dalam bentuk class dan typed interface.
- **Level 2 (The Hook):** Menuliskan satu fungsi logika inti secara langsung (misal: fungsi kalkulasi reward atau seleksi tool).
- **Level 3 (The Orchestration):** Mengimpor modul boilerplate (konektor database, telemetry exporter) yang sudah disiapkan sebelumnya via template git branch (`git checkout step-02`).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Resilient Demo Gateway & Telemetry Harness** menggunakan Python 3.11+ dengan FastAPI, `httpx`, dan `asyncio`. Harness ini bertindak sebagai proksi transparan cerdas antara skrip presenter dan upstream AI, mendukung *live streaming*, *transparent caching*, *fallback replay*, dan *real-time visualizer streaming*.

```python
#!/usr/bin/env python3
"""
Resilient Live-Demo Proxy & Replay Engine for AI Agents.
Designed for high-reliability technical public speaking and developer education.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from collections.abc import AsyncGenerator
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Setup granular logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [DemoHarness] %(message)s",
)
logger = logging.getLogger("DemoHarness")

# Enums & Data Structures
class ExecutionMode(str, Enum):
    LIVE = "LIVE"          # Always direct upstream
    RECORD = "RECORD"      # Run live and save responses
    REPLAY = "REPLAY"      # Pure offline, deterministic playback
    HYBRID = "HYBRID"      # Try live, fallback to replay on error/timeout


@dataclass(frozen=True)
class CircuitBreakerConfig:
    failure_threshold: int = 2
    recovery_time_sec: float = 10.0
    timeout_sec: float = 4.0


@dataclass
class TelemetryEvent:
    event_type: str
    payload: dict[str, Any]
    timestamp: float = time.time()

    def to_sse(self) -> str:
        data = json.dumps(asdict(self))
        return f"event: {self.event_type}\ndata: {data}\n\n"


# Storage Layer for VCR Cassettes
class CassetteRepository:
    def __init__(self, base_path: Path = Path("./demo_cassettes")) -> None:
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _hash_payload(self, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def exists(self, payload: dict[str, Any]) -> bool:
        key = self._hash_payload(payload)
        return (self.base_path / f"{key}.json").is_file()

    def save(self, payload: dict[str, Any], chunks: list[str]) -> None:
        key = self._hash_payload(payload)
        cassette_file = self.base_path / f"{key}.json"
        with open(cassette_file, "w", encoding="utf-8") as f:
            json.dump({"payload": payload, "chunks": chunks}, f, indent=2)
        logger.info("Cassette berhasil disimpan: %s", key)

    def load(self, payload: dict[str, Any]) -> list[str]:
        key = self._hash_payload(payload)
        cassette_file = self.base_path / f"{key}.json"
        if not cassette_file.is_file():
            raise FileNotFoundError(f"Cassette {key} tidak ditemukan.")
        with open(cassette_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return list(data["chunks"])


# Core Resilience Gateway
class ResilientGateway:
    def __init__(
        self,
        upstream_url: str,
        api_key: str,
        mode: ExecutionMode = ExecutionMode.HYBRID,
        config: CircuitBreakerConfig = CircuitBreakerConfig(),
    ) -> None:
        self.upstream_url = upstream_url
        self.api_key = api_key
        self.mode = mode
        self.config = config
        self.cassette_repo = CassetteRepository()
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.is_open = False
        self.telemetry_subscribers: list[asyncio.Queue[TelemetryEvent]] = []

    def register_telemetry(self) -> asyncio.Queue[TelemetryEvent]:
        q: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
        self.telemetry_subscribers.append(q)
        return q

    async def broadcast(self, event: TelemetryEvent) -> None:
        for subscriber in self.telemetry_subscribers:
            await subscriber.put(event)

    def _trip_circuit(self) -> None:
        self.is_open = True
        self.last_failure_time = time.time()
        logger.warning("Circuit breaker TRIP! Mengalihkan ke mode Replay.")

    def _check_circuit(self) -> None:
        if self.is_open:
            if time.time() - self.last_failure_time > self.config.recovery_time_sec:
                self.is_open = False
                self.failure_count = 0
                logger.info("Circuit breaker RESET ke status Half-Open/Closed.")
            else:
                logger.warning("Circuit breaker MASIH AKTIF. Force Fallback.")

    async def execute_stream(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        self._check_circuit()
        should_fallback = (
            self.mode == ExecutionMode.REPLAY
            or self.is_open
            or (self.mode == ExecutionMode.HYBRID and not self._is_upstream_healthy())
        )

        if not should_fallback:
            try:
                recorded_chunks: list[str] = []
                async for chunk in self._stream_upstream(payload):
                    recorded_chunks.append(chunk)
                    yield chunk

                if self.mode == ExecutionMode.RECORD:
                    self.cassette_repo.save(payload, recorded_chunks)
                return

            except (httpx.RequestError, httpx.HTTPStatusError, asyncio.TimeoutError) as exc:
                logger.error("Upstream gagal dieksekusi: %s", str(exc))
                self.failure_count += 1
                if self.failure_count >= self.config.failure_threshold:
                    self._trip_circuit()

                if self.mode != ExecutionMode.HYBRID:
                    raise HTTPException(
                        status_code=502, detail="Upstream Failure in non-hybrid mode"
                    ) from exc

                logger.info("Memulai fallback degradasi transparan (VCR Engine)...")

        # Fallback Replay Phase
        async for chunk in self._stream_replay(payload):
            yield chunk

    def _is_upstream_healthy(self) -> bool:
        # Pre-flight quick health evaluation
        return not self.is_open

    async def _stream_upstream(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        start_time = time.time()
        await self.broadcast(
            TelemetryEvent("METRICS", {"status": "CONNECTING_UPSTREAM"})
        )

        async with httpx.AsyncClient(timeout=self.config.timeout_sec) as client:
            async with client.stream(
                "POST", self.upstream_url, json=payload, headers=headers
            ) as response:
                if response.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"Status: {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                await self.broadcast(
                    TelemetryEvent(
                        "METRICS",
                        {
                            "status": "UPSTREAM_STREAMING",
                            "ttft_ms": (time.time() - start_time) * 1000,
                        },
                    )
                )

                async for line in response.aiter_lines():
                    if line:
                        await self.broadcast(
                            TelemetryEvent("TOKEN_CHUNK", {"chunk": line})
                        )
                        yield f"{line}\n\n"

    async def _stream_replay(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        await self.broadcast(
            TelemetryEvent(
                "FALLBACK_ENGAGED",
                {"reason": "Circuit breaker active or offline mode forced"},
            )
        )

        if not self.cassette_repo.exists(payload):
            # Synthetic offline emergency injection if no exact cassette exists
            synthetic_fallback = [
                'data: {"choices":[{"delta":{"content":"[FALLBACK] Sistem mendeteksi gangguan jaringan panggung. "}}]}\n\n',
                'data: {"choices":[{"delta":{"content":"Eksekusi dialihkan ke Local Deterministic Cache secara otomatis."}}]}\n\n',
                "data: [DONE]\n\n",
            ]
            for chunk in synthetic_fallback:
                await asyncio.sleep(0.05)  # Simulate realistic typing speed
                yield chunk
            return

        chunks = self.cassette_repo.load(payload)
        for chunk in chunks:
            # Emulasikan natural latency token streaming (20-40ms per chunk)
            await asyncio.sleep(0.03)
            await self.broadcast(
                TelemetryEvent("TOKEN_CHUNK_REPLAY", {"chunk": chunk})
            )
            yield f"{chunk}\n\n"


# Presentation API Service Definition
app = FastAPI(title="DevRel AI Live Demo Harness")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GATEWAY = ResilientGateway(
    upstream_url=os.getenv("AI_UPSTREAM_URL", "https://api.openai.com/v1/chat/completions"),
    api_key=os.getenv("AI_API_KEY", "mock-token"),
    mode=ExecutionMode(os.getenv("DEMO_MODE", ExecutionMode.HYBRID.value)),
)


@app.post("/v1/chat/completions")
async def chat_completions_proxy(request: Request) -> StreamingResponse:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON Payload") from exc

    return StreamingResponse(
        GATEWAY.execute_stream(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Demo-Resilience": "active",
        },
    )


@app.get("/telemetry/stream")
async def telemetry_stream() -> StreamingResponse:
    """Endpoint untuk visualizer web yang diproyeksikan pada layar kedua audiens."""
    queue = GATEWAY.register_telemetry()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                event = await queue.get()
                yield event.to_sse()
        except asyncio.CancelledError:
            GATEWAY.telemetry_subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    logger.info("Memulai Live Demo Resilience Harness pada port 8080...")
    uvicorn.run(app, host="127.0.0.1", port=8080, access_log=False)
```

---

### 7. Edge Cases & Failure Modes

| Kondisi Kegagalan Panggung | Gejala Sistem | Mitigasi Otomatis (Harness Level) | Tindakan Presenter (Stage Strategy) |
|---|---|---|---|
| **Wi-Fi Venue Disconnect** | DNS resolution error, packet dropped. | Circuit Breaker langsung membuka status (`OPEN`). Gateway menyuntikkan cached cassette. | Jelaskan: *"Sistem beralih ke local fallback cache tanpa menghentikan streaming token."* |
| **HTTP 429: API Quota Depleted** | Upstream provider melempar status `insufficient_quota` / `rate_limit_exceeded`. | Proxy menangkap respons `429`, tidak meneruskannya ke terminal presenter, dan memutar *shadow recording*. | Transparan: Tunjukkan perbandingan log *live rate-limit vs resilience design* sebagai poin pembelajaran. |
| **Hallucinatory Tool Recursion** | Agen terjebak dalam pemanggilan tools berulang-ulang tanpa konvergensi. | `Recursive Loop Guard` memotong eksekusi pada `depth >= 3` dan menyuntikkan instruksi terminasi sintetik. | Tunjukkan telemetry visualizer yang mendeteksi anomali iterasi secara visual kepada audiens. |
| **High TTFT (Time-To-First-Token) > 10 Detik** | Jeda keheningan panggung (*stage silence*) yang merusak ritme presentasi. | Timeout gateway disetel ketat pada `3.0s`. Jika token pertama tidak sampai, fallback diaktifkan instan. | Jangan biarkan panggung hening: isi gap awal dengan arsitektur slide sebelum teks muncul. |

---

### 8. Trade-offs & Alternatif Solusi

```
                      Trade-Off Matrix Demo AI Architecture

      Otentisitas Penuh                             Ketahanan Absolut
     (100% Live Streaming)                        (100% Mock / Rekaman)
             │                                              │
             ▼                                              ▼
   [ Upstream Langsung ]   <-- [ RESILIENT HYBRID ] -->   [ Pre-recorded Video ]
   • Risiko Crash: TINGGI        • Risiko Crash: NOL        • Risiko Crash: NOL
   • Latensi: Fluktuatif         • Latensi: Terkontrol      • Latensi: Fixed
   • Kredibilitas: Maksimal      • Kredibilitas: Terjaga    • Kredibilitas: Sangat Rendah
```

#### Komparasi Desain:
1. **Pure Live via Cloud LLM API:**
   - *Kelebihan:* Menunjukkan model bekerja apa adanya, interaksi prompt spontan dari audiens dapat dieksekusi langsung.
   - *Kekurangan:* Rentan kegagalan fatal pada venue berskala besar dengan ratusan koneksi nirkabel konkuren.
2. **Local Model (Ollama / vLLM pada Laptop Presenter):**
   - *Kelebihan:* Sepenuhnya independen dari Wi-Fi panggung.
   - *Kekurangan:* Bergantung pada GPU/VRAM laptop (MacBook Apple Silicon). Menguras daya baterai dengan cepat dan menaikkan suhu perangkat, memicu CPU throttling yang justru memperlambat demo.
3. **Resilient Hybrid Gateway (Pola Terpilih):**
   - *Kelebihan:* Memadukan keaslian interaksi dinamis dengan safety net deterministik. Menyajikan nilai edukasi tinggi tentang *fault tolerance* pada distributed AI systems.
   - *Kekurangan:* Menuntut setup arsitektur lokal sebelum presentasi dimulai (overhead konfigurasi proxy).

---

### 9. Best Practices & Standar Industri

#### A. Setup Workspace & Visual Ergonomics
- **Ukuran Font Terminal:** Minimal 18pt–22pt (Monospace, e.g., JetBrains Mono). Gunakan skema warna kontras tinggi (latar belakang gelap pekat `#000000` dengan font putih/kuning terang, hindari warna biru gelap yang tidak terbaca proyektor lama).
- **Resolusi Display:** Paksa resolusi eksternal laptop menjadi `1920x1080` (1080p). Jangan gunakan 4K scaling native panggung karena rendering font pada viewer streaming/layar proyektor akan mengecil.
- **Isolasi Lingkungan Presentasi:**
  - Nonaktifkan semua notifikasi sistem (*Do Not Disturb / Focus Mode*).
  - Matikan sinkronisasi background: Docker cloud sync, Google Drive, iCloud, Slack, Telegram.
  - Sediakan Dedicated 4G/5G Hardware MiFi tethering USB kabel (jangan bergantung pada Wi-Fi laptop).

#### B. Pedagogi Demonstrasi Kode
- **Atomic Git Checkpoints:** Siapkan skrip bash untuk melompat antar checkpoint demonstrasi secara mulus:
  ```bash
  # demo-step.sh
  step() {
    git checkout -f "step-$1"
    clear
    cat .step_metadata
  }
  ```
- **Live-Coding Guardrails:** Jangan mengetik kode kompleks dari nol (*never type complex boilerplate live*). Manfaatkan snippet IDE (misal: VS Code User Snippets) yang dipicu dengan kata kunci singkat, lalu jelaskan logika intinya.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab:
Anda ditugaskan membawakan demo live 30 menit di konferensi internasional tentang: *"Membangun Autonomous Agent untuk Audit Keamanan SQL Menggunakan Tool Calling"*. Bangun sistem mitigasi lokal dan eksekusi skrip demo yang tahan terhadap pemutusan koneksi internet manual.

#### Langkah-Langkah:

1. **Inisialisasi Lingkungan & Cassette Recording:**
   Jalankan gateway dalam mode `RECORD` pada terminal pertama untuk membuat rekaman baseline:
   ```bash
   export DEMO_MODE="RECORD"
   export AI_UPSTREAM_URL="https://api.openai.com/v1/chat/completions"
   export AI_API_KEY="sk-valid-key-anda"
   python resilient_gateway.py
   ```

2. **Eksekusi Dry-Run Client Script:**
   Pada terminal kedua, jalankan script agent client yang menargetkan proxy lokal:
   ```bash
   curl -X POST http://127.0.0.1:8080/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "gpt-4o",
       "messages": [
         {"role": "system", "content": "You are a deterministic SQL auditor agent."},
         {"role": "user", "content": "Audit query: SELECT * FROM users WHERE id = '\'' OR '\''1'\''='\''1'\''"}
       ],
       "stream": true
     }'
   ```
   *Verifikasi bahwa file cassette JSON telah terbuat di direktori `./demo_cassettes/`.*

3. **Simulasi Bencana Panggung (Stage Wi-Fi Kill):**
   - Matikan koneksi internet laptop Anda sepenuhnya (Putuskan Wi-Fi / cabut kabel LAN).
   - Ubah mode gateway menjadi `HYBRID`:
     ```bash
     export DEMO_MODE="HYBRID"
     python resilient_gateway.py
     ```

4. **Eksekusi Verifikasi Fallback Transparan:**
   Kirimkan payload yang sama melalui client script.
   ```bash
   curl -N -X POST http://127.0.0.1:8080/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "gpt-4o",
       "messages": [
         {"role": "system", "content": "You are a deterministic SQL auditor agent."},
         {"role": "user", "content": "Audit query: SELECT * FROM users WHERE id = '\'' OR '\''1'\''='\''1'\''"}
       ],
       "stream": true
     }'
   ```

#### Kriteria Keberhasilan:
- [ ] Terminal menampilkan respons streaming teks secara bertahap tanpa delay `Connection Refused` atau crash unhandled exception.
- [ ] Endpoint `/telemetry/stream` memancarkan event `FALLBACK_ENGAGED` yang memverifikasi bahwa harness mengalihkan data path secara tepat.
- [ ] Sistem menyelesaikan tugas presentasi dengan total kegagalan teknis audiens sebesar **0%**.