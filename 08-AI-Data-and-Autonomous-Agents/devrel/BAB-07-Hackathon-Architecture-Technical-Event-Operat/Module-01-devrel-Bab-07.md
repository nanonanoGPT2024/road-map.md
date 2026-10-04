# Bab 07: Hackathon Architecture & Technical Event Operations

## Module 01: Arsitektur Infrastruktur Hackathon AI, Virtualized Token Gateway, dan Sandbox Runtime

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Merancang dan Mengimplementasikan Token Virtualization Gateway**: Membangun reverse proxy performa tinggi untuk mendistribusikan *virtual API keys* kepada ratusan tim dengan *hard token budgeting*, *fine-grained rate limiting*, dan *dynamic failover routing* lintas penyedia LLM (OpenAI, Anthropic, OSS models via vLLM/Ollama).
2. **Membangun Runtime Eksekusi Sandbox Zero-Trust**: Mengonfigurasi lingkungan evaluasi berbasis container/microVM terisolasi untuk menjalankan dan menilai kode agen otonom secara aman tanpa risiko *sandbox escape*, *resource starvation*, atau eksfiltrasi data host.
3. **Mengoperasikan Arsitektur Event Telemetry & Observability**: Mengintegrasikan OpenTelemetry pipeline dan Prometheus/Grafana untuk memantau konsumsi token, *error rate*, latensi inferensi, dan anomali perilaku agen (*runaway recursive loops*) secara real-time.
4. **Merumuskan Mitigasi Kegagalan Tingkat Lanjut**: Menerapkan mekanisme mitigasi untuk skenario *upstream 429/5xx outage*, serangan *fork bomb* pada runtime, serta degradasi jaringan selama penjurian langsung (*live judging*).

---

### 2. Concept Overview

Mengelola operasional teknis untuk hackathon AI dan Autonomous Agents berbeda secara mendasar dari hackathon web/mobile konvensional. Kompleksitas utamanya terletak pada tiga pilar:

```
+-----------------------------------------------------------------------------------+
|                           HACKATHON AI RUNTIME DYNAMICS                           |
+-----------------------------------------------------------------------------------+
|  1. Non-Deterministic Load: Lonjakan eksponensial inferensi pada jam-jam akhir.   |
|  2. Asymmetric Cost: Satu loop agen tak terkendali dapat menghabiskan ribuan USD. |
|  3. Hostile Code Execution: Evaluasi submission agen melibatkan eksekusi kode     |
|     arbitrer yang memiliki akses shell, network, dan filesystem.                  |
+-----------------------------------------------------------------------------------+
```

#### Mental Model: The Insulated Funnel

Bayangkan infrastruktur hackathon AI sebagai sebuah *Insulated Funnel* (Corong Berisolasi):

```
Peserta (Tim 1..N) 
      │
      ▼ (Virtual API Keys)
[ Token Virtualization Gateway ] ──► Redis (Atomic Rate-limit / Budgeting via Lua)
      │
      ├─► Provider A (Primary)
      └─► Provider B (Fallback via Circuit Breaker)
      │
Submission Kode Agen
      │
      ▼
[ Ephemeral MicroVM / Sandbox Execution Engine ]
      ├── Network Namespace Isolation (Egress Filtering)
      ├── cgroups v2 (CPU/Memory Throttling)
      └── Ephemeral OverlayFS (Automated Teardown)
```

Infrastruktur ini bertindak sebagai peredam kejut antara peserta dan infrastruktur kritis (upstream LLM provider dan sistem internal juri). Tidak ada peserta yang memegang API key produksi langsung. Semua interaksi dimediasi melalui lapisan *stateful proxy* yang menegakkan kuota finansial dan batasan komputasi secara atomik.

---

### 3. Why It Matters

Di ranah enterprise dan Developer Relations (DevRel), kegagalan teknis saat hackathon berdampak langsung pada reputasi platform (*developer trust*) dan kerugian finansial langsung:

1. **Financial Blast Radius**: Agen otonom berbasis arsitektur ReAct (Reasoning + Acting) yang mengalami *infinite reflection loop* dapat membakar jutaan token dalam hitungan menit. Tanpa pembatasan tingkat proxy, tagihan cloud provider dapat melonjak tanpa batas.
2. **Upstream Rate-Limit Collapse**: Jika 500 peserta mengirimkan prompt secara bersamaan 10 menit sebelum batas waktu pengumpulan, API key upstream tunggal akan langsung terkena limitasi HTTP 429 (*Rate Limit Exceeded*). Hal ini menyebabkan sistem peserta gagal bekerja serentak bukan karena kesalahan logika mereka, melainkan akibat kegagalan orkestrasi DevRel.
3. **Sandbox Escape & Infrastructure Hijacking**: Penjurian submission AI agents sering kali membutuhkan eksekusi kode secara langsung untuk memvalidasi performa benchmark. Jika sistem penilaian mengeksekusi kode Python/Bash peserta di atas container docker default tanpa isolasi kernel (gVisor/Firecracker), peserta dapat membaca kredensial host, mengekstrak master token, atau mengubah data evaluasi tim lain.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur operasional hackathon dirancang dengan pemisahan domain yang ketat antara *Traffic Ingestion*, *Quota Governance*, dan *Evaluation Sandboxing*.

```
                                      HACKATHON EDGE
                                            │
               ┌────────────────────────────┴────────────────────────────┐
               ▼                                                         ▼
     [ Team Workstations ]                                     [ Automated Judging ]
               │                                                         │
               │ HTTP Authorization: Bearer vkey_team_xyz                │
               ▼                                                         ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                          TOKEN VIRTUALIZATION GATEWAY                           |
|                                                                                 |
|   ┌───────────────────────────┐           ┌─────────────────────────────────┐   |
|   |   FastAPI / Async Engine  |           |   Budget & Rate Limit Governor  |   |
|   |   - Auth & Virtual Key    |◄─────────►|   - Redis Cluster (Lua scripts) |   |
|   |   - Request Interception  |           |   - Token Bucket RPM/TPM        |   |
|   |   - Response Token Parser |           |   - USD Hard-cap Counter        |   |
|   └─────────────┬─────────────┘           └─────────────────────────────────┘   |
|                 │                                                               |
|                 ▼                                                               |
|   ┌─────────────────────────────────────────────────────────────────────────┐   |
|   | Dynamic Circuit Breaker & Provider Router                               |   |
|   |   ├─► Primary Pool: OpenAI Direct (gpt-4o, o3-mini)                    |   |
|   |   ├─► Fallback 1: Azure OpenAI Service                                 |   |
|   |   └─► Fallback 2: Anthropic Claude 3.5 Sonnet / Bedrock                 |   |
|   └─────────────────────────────────────────────────────────────────────────┘   |
+────────────────────────────────────────┬────────────────────────────────────────+
                                         │ Telemetry Event Stream (OTLP/gRPC)
                                         ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                         MONITORING & OBSERVABILITY TIER                         |
|   ┌───────────────────────┐ ┌───────────────────────┐ ┌─────────────────────┐   |
|   | Prometheus / Vector   | | Grafana Live Ops Dash | | Pager & Auto-Revoke |   |
|   └───────────────────────┘ └───────────────────────┘ └─────────────────────┘   |
+─────────────────────────────────────────────────────────────────────────────────+
                                         │ Submission Trigger
                                         ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                        AGENT EXECUTION SANDBOX RUNTIME                          |
|                                                                                 |
|   ┌─────────────────────────────────────────────────────────────────────────┐   |
|   | Sandbox Manager Daemon (gVisor / runsc + cgroups v2)                    |   |
|   |   ┌───────────────────────────┐       ┌─────────────────────────────┐   |   |
|   |   | Pod Team Alpha            |       | Pod Team Beta               |   |   |
|   |   |  - Ephemeral OverlayFS    |       |  - Ephemeral OverlayFS      |   |   |
|   |   |  - Network: Egress Whitelist      |  - Network: Isolated Egress |   |   |
|   |   |  - CPU: 2 Core, RAM: 4GB  |       |  - CPU: 2 Core, RAM: 4GB    |   |   |
|   |   |  - Max TTL Watchdog: 180s |       |  - Max TTL Watchdog: 180s   |   |   |
|   |   └───────────────────────────┘       └─────────────────────────────┘   |   |
|   └─────────────────────────────────────────────────────────────────────────┘   |
+─────────────────────────────────────────────────────────────────────────────────+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Virtual Token Key Lifecycle & Sliding Window Algorithm

Gateway mengabstraksi *Master Upstream API Key* menggunakan identitas sementara: `vkey_<team_id>_<hash>`. Setiap request diuji melalui algoritma *Sliding Window Counter* dan *Hard Budget Allocator* yang diimplementasikan di level Redis:

1. **Pre-Flight Validation**: Gateway membedah body permintaan JSON, menghitung estimasi token input menggunakan `tiktoken` (atau library tokenizer terkait).
2. **Atomic Quota Check**: Skrip Lua di Redis mengeksekusi pemeriksaan atomik:
   $$\text{Estimated Cost} = (\text{Input Tokens} \times \text{Rate}_{\text{in}}) + (\text{Max Output Tokens} \times \text{Rate}_{\text{out}})$$
   Jika $\text{Cumulative Spend} + \text{Estimated Cost} > \text{Hard Cap}$, gateway mengembalikan `402 Payment Required` dengan payload JSON terstruktur, memutus request sebelum menyentuh upstream.
3. **Upstream Forwarding & Streaming Parsing**: Request diarahkan ke provider upstream. Jika client menggunakan streaming (`stream=true`), gateway mengalirkan chunk Server-Sent Events (SSE) sembari mengagregasi teks untuk memvalidasi penggunaan token riil melalui header response atau chunk terminasi (`usage` field).
4. **Post-Flight Settlement**: Redis memperbarui saldo riil tim berdasarkan metrik konsumsi token resmi dari provider upstream.

#### B. Provider Fallback Matrix & Resiliency

Gateway menerapkan *State Machine* untuk menangani kegagalan upstream:

| Kondisi Upstream | Status Code | Tindakan Gateway |
| :--- | :--- | :--- |
| **Normal** | 200 OK | Meneruskan response ke client; update counter. |
| **Upstream Throttled** | 429 Too Many Requests | Naikkan *trip counter* circuit breaker; alihkan request secara otomatis ke Secondary Provider (misal: Azure OpenAI / Bedrock) dengan pemetaan model otomatis. |
| **Server Error** | 500, 502, 503 | Coba 1x retry lokal dengan jitter; jika gagal, alihkan ke fallback model pool. |
| **Timeout (> 30s)** | Client Timeout / Drop | Batalkan koneksi upstream secara instan (`cancellation token`) untuk mencegah pemborosan komputasi backend. |

#### C. Egress-Constrained Sandbox Architecture

Untuk mengevaluasi submission agen yang menjalankan kode berbahaya secara sengaja maupun tidak sengaja:
- Runtime mengandalkan container runtime berbasis kernel virtualization level-aplikasi, seperti **gVisor (`runsc`)**. Setiap submission dijalankan di atas sandbox terisolasi.
- **Egress Firewall Rules**: Sandbox memblokir akses ke subnet internal cloud infrastructure (misal: endpoint metadata AWS `169.254.169.254`, database VPC internal). Akses internet dibuka hanya ke domain yang di-whitelist (misalnya API gateway hackathon dan repository paket publik jika diperlukan).
- **Execution Watchdog**: Proses eksekusi kode agen dibatasi oleh *wall-clock timer* ketat (contoh: maksimal 3 menit). Jika agen macet dalam loop inferensi atau komputasi lokal, daemon sandbox mengirimkan sinyal `SIGKILL` tanpa toleransi dan mencatat evaluasi sebagai *Execution Timeout*.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Production-Ready Hackathon Gateway** berbasis asynchronous Python (`FastAPI`, `httpx`, `redis.asyncio`) yang menangani virtual key validation, Redis-based token rate limiting via Lua, dynamic routing, dan multi-provider fallback.

```python
"""
Hackathon AI Proxy Gateway - Production Core
Dependencies: fastapi, uvicorn, httpx, redis, pydantic, tiktoken
"""

import json
import time
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from contextlib import asynccontextmanager

import tiktoken
import httpx
from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import redis.asyncio as redis

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("HackathonGateway")

# Configurations
REDIS_URL = "redis://localhost:6379/0"
OPENAI_API_BASE = "https://api.openai.com/v1"
FALLBACK_API_BASE = "https://api.groq.com/openai/v1"  # Example high-speed fallback

UPSTREAM_KEYS = {
    "primary": "sk-mock-openai-primary-key",
    "fallback": "sk-mock-groq-fallback-key"
}

# Redis Lua Script for Atomic Rate Limiting and Budget Allocation
# Keys: [team_key, budget_key]
# Args: [max_rpm, window_size_sec, cost_estimate, budget_limit]
LUA_RATE_LIMITER = """
local rate_key = KEYS[1]
local budget_key = KEYS[2]

local max_rpm = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local cost_estimate = tonumber(ARGV[3])
local budget_limit = tonumber(ARGV[4])
local current_time = tonumber(ARGV[5])

-- 1. Check Lifetime Budget Limit
local current_spend = tonumber(redis.call('GET', budget_key) or "0")
if current_spend + cost_estimate > budget_limit then
    return {0, "BUDGET_EXCEEDED", current_spend}
end

-- 2. Sliding Window Rate Limiting (Requests Per Minute)
local clear_before = current_time - window
redis.call('ZREMRANGEBYSCORE', rate_key, 0, clear_before)
local current_req_count = redis.call('ZCARD', rate_key)

if current_req_count >= max_rpm then
    return {0, "RATE_LIMIT_EXCEEDED", current_req_count}
end

-- 3. Reserve Quota Temporarily (Optimistic Allocation)
redis.call('ZADD', rate_key, current_time, current_time)
redis.call('EXPIRE', rate_key, window * 2)
redis.call('INCRBYFLOAT', budget_key, cost_estimate)

return {1, "ALLOWED", current_spend + cost_estimate}
"""

class GatewayState:
    redis_client: Optional[redis.Redis] = None
    http_client: Optional[httpx.AsyncClient] = None
    lua_sha: Optional[str] = None
    tokenizer: Any = None

state = GatewayState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup setup
    state.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=10.0))
    state.lua_sha = await state.redis_client.script_load(LUA_RATE_LIMITER)
    state.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    # Preload mock team metadata for demonstration
    await state.redis_client.set("meta:vkey_team_alpha:budget_limit", "50.0")  # $50 USD
    await state.redis_client.set("meta:vkey_team_alpha:rpm_limit", "30")       # 30 RPM
    
    logger.info("Gateway engine started successfully.")
    yield
    # Graceful shutdown
    await state.http_client.aclose()
    await state.redis_client.close()
    logger.info("Gateway engine shutdown complete.")

app = FastAPI(title="Hackathon AI Token Gateway", lifespan=lifespan)

class VirtualKeyContext(BaseModel):
    team_id: str
    budget_limit: float
    max_rpm: int
    raw_key: str

async def authenticate_virtual_key(request: Request) -> VirtualKeyContext:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization Bearer token wajib disertakan."
        )
    
    vkey = auth_header.split(" ")[1].strip()
    
    # Check cache for team policy
    budget_limit = await state.redis_client.get(f"meta:{vkey}:budget_limit")
    max_rpm = await state.redis_client.get(f"meta:{vkey}:rpm_limit")
    
    if budget_limit is None or max_rpm is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Virtual API Key tidak valid atau telah dicabut oleh panitia."
        )
        
    return VirtualKeyContext(
        team_id=vkey.replace("vkey_", ""),
        budget_limit=float(budget_limit),
        max_rpm=int(max_rpm),
        raw_key=vkey
    )

def estimate_input_tokens(payload: Dict[str, Any]) -> int:
    """Estimasi jumlah token input menggunakan tiktoken secara aman."""
    total_tokens = 0
    messages = payload.get("messages", [])
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_tokens += len(state.tokenizer.encode(content))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total_tokens += len(state.tokenizer.encode(part.get("text", "")))
    return max(total_tokens, 1)

@app.post("/v1/chat/completions")
async def chat_completions_proxy(
    request: Request,
    auth_ctx: VirtualKeyContext = Depends(authenticate_virtual_key)
):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON body")

    # Hitung estimasi biaya awal ($0.005 / 1k token sebagai nilai konservatif)
    input_tokens = estimate_input_tokens(payload)
    estimated_cost = (input_tokens / 1000.0) * 0.005
    now = time.time()

    # Eksekusi Redis Lua Script untuk validasi atomik
    rate_key = f"rate:{auth_ctx.raw_key}"
    budget_key = f"spend:{auth_ctx.raw_key}"
    
    res = await state.redis_client.evalsha(
        state.lua_sha,
        2,
        rate_key,
        budget_key,
        str(auth_ctx.max_rpm),
        "60",
        str(estimated_cost),
        str(auth_ctx.budget_limit),
        str(now)
    )

    allowed, reason, val = res[0], res[1], res[2]
    if allowed == 0:
        if reason == "BUDGET_EXCEEDED":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Budget hackathon habis: Terpakai ${float(val):.4f} dari alokasi ${auth_ctx.budget_limit:.2f}"
            )
        elif reason == "RATE_LIMIT_EXCEEDED":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit terlampaui: Batas maksimal {auth_ctx.max_rpm} request per menit."
            )

    is_streaming = payload.get("stream", False)
    
    # Request forwarding dengan Dynamic Failover Routing
    async def forward_request(base_url: str, api_key: str):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        return await state.http_client.build_request(
            method="POST",
            url=f"{base_url}/chat/completions",
            headers=headers,
            json=payload
        ), headers

    # Coba Primary Provider
    upstream_url = OPENAI_API_BASE
    active_key = UPSTREAM_KEYS["primary"]
    
    req, headers = await forward_request(upstream_url, active_key)
    
    try:
        upstream_response = await state.http_client.send(req, stream=is_streaming)
        
        # Failover logic jika 429 atau 5xx dari provider utama
        if upstream_response.status_code in [429, 500, 502, 503]:
            logger.warning(f"Primary upstream fail ({upstream_response.status_code}). Rerouting ke Fallback.")
            await upstream_response.aclose()
            
            # Map fallback target
            upstream_url = FALLBACK_API_BASE
            active_key = UPSTREAM_KEYS["fallback"]
            # Timpa model ke model default fallback jika perlu
            payload["model"] = "llama-3.3-70b-versatile"
            
            fallback_req, _ = await forward_request(upstream_url, active_key)
            upstream_response = await state.http_client.send(fallback_req, stream=is_streaming)

    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error(f"Upstream provider connection error: {exc}. Mengalihkan ke Fallback.")
        upstream_url = FALLBACK_API_BASE
        active_key = UPSTREAM_KEYS["fallback"]
        payload["model"] = "llama-3.3-70b-versatile"
        
        fallback_req, _ = await forward_request(upstream_url, active_key)
        upstream_response = await state.http_client.send(fallback_req, stream=is_streaming)

    # Tangani Response Streaming
    if is_streaming:
        async def stream_generator() -> AsyncGenerator[bytes, None]:
            try:
                async for chunk in upstream_response.aiter_raw():
                    yield chunk
            finally:
                await upstream_response.aclose()
        
        return StreamingResponse(
            stream_generator(),
            status_code=upstream_response.status_code,
            headers={"Content-Type": "text/event-stream"}
        )
    
    # Tangani Non-Streaming Response
    else:
        body = await upstream_response.aread()
        await upstream_response.aclose()
        
        # Real Usage Settlement
        try:
            resp_json = json.loads(body)
            usage = resp_json.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            
            # Hitung biaya presisi dan koreksi estimasi awal
            actual_cost = (total_tokens / 1000.0) * 0.005
            cost_difference = actual_cost - estimated_cost
            if cost_difference != 0:
                await state.redis_client.incrbyfloat(budget_key, cost_difference)
        except Exception as e:
            logger.error(f"Gagal melakukan rekonsiliasi token riil: {e}")

        return JSONResponse(
            content=json.loads(body),
            status_code=upstream_response.status_code
        )

@app.get("/v1/telemetry/team-status")
async def get_team_status(auth_ctx: VirtualKeyContext = Depends(authenticate_virtual_key)):
    """Endpoint untuk peserta memantau sisa kuota dan kecepatan mereka."""
    spend = await state.redis_client.get(f"spend:{auth_ctx.raw_key}") or "0"
    current_spend = float(spend)
    return {
        "team_id": auth_ctx.team_id,
        "budget_limit_usd": auth_ctx.budget_limit,
        "current_spend_usd": round(current_spend, 4),
        "remaining_budget_usd": round(max(0.0, auth_ctx.budget_limit - current_spend), 4),
        "max_rpm": auth_ctx.max_rpm
    }
```

---

### 7. Edge Cases & Failure Modes

Setiap *event reliability engineer* wajib menyiapkan strategi mitigasi untuk empat kegagalan utama berikut:

#### 1. ReAct Agent Recursive Hallucination (Loop Tak Terhingga)
*   **Kasus**: Agen peserta memanggil tool secara iteratif untuk menyelesaikan tugas, namun prompt salah menginstruksikan terminasi, memicu ribuan iterasi per menit.
*   **Deteksi**: Gateway memantau frekuensi panggilan identik menggunakan sliding window hash: jika input payload identik dikirim lebih dari 5 kali berturut-turut dalam 10 detik.
*   **Pemulihan**: Inject artificial stopping exception ke body response JSON: `{"error": "Deterministic Loop Detected by Event Watchdog"}` dan blokir virtual key selama 60 detik (*cooldown period*).

#### 2. Sandbox Fork Bomb & Memory Exhaustion saat Evaluasi
*   **Kasus**: Kode submission peserta mengeksekusi subproses paralel yang membanjiri memory host (`os.fork()` loop atau *data loading* tanpa paging).
*   **Deteksi**: Container runtime mendeteksi pelanggaran OOM (*Out Of Memory*) atau PID exhaustion melalui cgroups v2 (`pids.current` mendekati `pids.max`).
*   **Pemulihan**: Konfigurasi `runsc` (gVisor) dengan isolasi tegas:
    ```bash
    # Potongan konfigurasi batas resource runtime
    --pids-limit 128
    --memory 4096m
    --memory-swap 4096m
    --cpu-quota 200000 # 2 Cores
    ```
    Jika threshold tercapai, runtime membunuh container tanpa memengaruhi host dan menandai submission dengan status `FAILED: OOM_OR_PID_BURST`.

#### 3. Upstream Provider Region Blackout (503 / DNS Failure)
*   **Kasus**: Terputusnya koneksi ke endpoint OpenAI `api.openai.com` di region tertentu saat hackathon berlangsung.
*   **Deteksi**: HTTP Client mendeteksi threshold 5xx beruntun via *Circuit Breaker Pattern* (misalnya: rasio error > 20% selama window 15 detik).
*   **Pemulihan**: Status sirkuit beralih ke `OPEN`. Semua request otomatis diarahkan ke model alternatif di region atau provider lain tanpa menunggu koneksi primary time-out.

#### 4. Participant Secret Exfiltration via Sandbox Output
*   **Kasus**: Peserta menyuntikkan instruksi jailbreak ke sistem evaluasi untuk membaca environment variable juri atau master key yang disuntikkan ke runtime.
*   **Mitigasi**: Master API Key tidak boleh disuntikkan ke dalam sandbox. Sandbox hanya diberikan *Single-Use Ephemeral Proxy Token* yang hanya valid selama masa evaluasi tugas tersebut (TTL: 180 detik) dan langsung dibatalkan setelah eksekusi selesai.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektur | Pilihan A: Centralized Gateway (Solusi Pilihan) | Pilihan B: Bring-Your-Own-Key (BYOK) via Voucher | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Kontrol Biaya Finansial** | **Tinggi**: Kuota token terkunci atomik di Redis; langsung terputus saat cap tercapai. | **Rendah**: Peserta menggunakan voucher individual. Risiko kehabisan saldo sebelum event berakhir tanpa kontrol panitia. | Pilihan A mencegah pembengkakan biaya tak terduga (*over-budgeting*) pada akun organisasi panitia. |
| **Kompleksitas Operasional** | **Tinggi**: Membutuhkan arsitektur proxy *highly-available* dengan latensi minimal (<15ms overhead). | **Sangat Rendah**: Panitia hanya mendistribusikan kode voucher fisik/digital kepada tiap tim. | Pilihan B mengeliminasi beban operasional infrastruktur namun menghilangkan visibilitas real-time terhadap performa dan penggunaan token. |
| **Resiliensi Upstream** | **Tinggi**: Gateway dapat mengalihkan rute secara dinamis (misal: dari OpenAI ke Azure/Anthropic) tanpa perubahan kode peserta. | **Nol**: Jika penyedia tunggal mengalami gangguan (down), seluruh event berhenti total. | Pilihan A sangat penting untuk live event berskala besar yang terikat jadwal ketat. |

| Model Isolasi Sandbox | Docker Engine Standar (`runc`) | gVisor Microkernel Sandboxing (`runsc`) | Firecracker MicroVMs |
| :--- | :--- | :--- | :--- |
| **Tingkat Isolasi** | Lemah (Shared Host Kernel). Rentan eksfiltrasi kernel via privilege escalation. | Tinggi (Application Kernel terisolasi yang mengintercept syscalls). | Sangat Tinggi (Isolasi berbasis hardware virtualization KVM penuh). |
| **Startup Overhead** | ~500ms | ~1000ms | ~150-300ms (membutuhkan host bare-metal dengan ekstensi virtualisasi). |
| **Kesesuaian Event** | Cocok untuk hackathon web development standar non-AI. | **Paling Seimbang**: Berjalan di atas instans cloud reguler tanpa kebutuhan hardware nested virtualization. | Terbaik jika infrastruktur dijalankan langsung di atas bare-metal instance (misal: AWS `.metal`). |

---

### 9. Best Practices & Standar Industri

1. **Deterministic Mock Fallback untuk Stress Testing**:
   Sebelum hackathon dimulai, lakukan uji beban sistem dengan traffic mock LLM menggunakan framework *k6* atau *Locust*. Pastikan cluster Redis dan gateway mampu memproses minimal 500 RPS dengan latensi internal p99 < 15ms.

2. **Scrubbing Logging untuk Privasi dan Kepatuhan Data**:
   Jangan mencatat (*log*) seluruh teks request/response ke dalam plain-text log disk. Simpan hanya metadata: `team_id`, `input_token_count`, `output_token_count`, `latency_ms`, dan `model_used`. Logging teks penuh hanya diizinkan untuk debugging error dan harus dibersihkan secara terjadwal.

3. **Multi-Region Failover Architecture**:
   Deploy gateway secara redundant di minimal dua *Availability Zone*. Gunakan database state (Redis) dengan arsitektur Master-Replica dengan automated failover untuk menghindari satu titik kegagalan (*Single Point of Failure*).

4. **Zero-Trust Egress Policy pada Sandbox Evaluasi**:
   Default action untuk seluruh outbound network dari sandbox adalah `DROP`. Buka akses hanya ke alamat host yang secara eksplisit diperlukan untuk submission menggunakan Linux `iptables` atau CNI network policy:
   ```bash
   iptables -A OUTPUT -d 10.0.0.0/8 -j DROP
   iptables -A OUTPUT -d 172.16.0.0/12 -j DROP
   iptables -A OUTPUT -d 192.168.0.0/16 -j DROP
   iptables -A OUTPUT -d 169.254.169.254/32 -j DROP # Block AWS Metadata
   ```

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertugas sebagai *Lead Infrastructure Architect* untuk *Agentic AI Hackathon*. Anda harus:
1. Menjalankan Mock Upstream Provider, Redis, dan Production Token Gateway.
2. Mengonfigurasi Virtual API Key dengan kuota $1.00 USD dan limit 5 Request Per Menit.
3. Mensimulasikan konsumsi agen hingga memicu *Rate Limit (429)* dan *Budget Depletion (402)*.
4. Memvalidasi mekanisme eksekusi terisolasi sandbox.

#### Panduan Langkah demi Langkah

##### Langkah 1: Siapkan Environment & Dependencies
Buat direktori proyek baru dan instal dependensi yang diperlukan:

```bash
mkdir hackathon-ops-lab && cd hackathon-ops-lab
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn httpx redis tiktoken pydantic
```

##### Langkah 2: Jalankan Redis Instance
Gunakan Docker untuk menjalankan instance Redis lokal:

```bash
docker run -d --name hackathon-redis -p 6379:6379 redis:7-alpine
```

##### Langkah 3: Simpan dan Jalankan Script Gateway
Simpan kode dari **Bagian 6 (Production-Ready Code Implementation)** ke dalam file bernama `gateway.py`. Jalankan gateway menggunakan `uvicorn`:

```bash
uvicorn gateway:app --host 0.0.0.0 --port 8000 --workers 2
```

##### Langkah 4: Uji Coba Virtual Key & Validasi Status Awal
Jalankan perintah cURL berikut untuk memeriksa status kuota tim:

```bash
curl -X GET http://localhost:8000/v1/telemetry/team-status \
  -H "Authorization: Bearer vkey_team_alpha"
```

*Ekspektasi Output*:
```json
{
  "team_id": "team_alpha",
  "budget_limit_usd": 50.0,
  "current_spend_usd": 0.0,
  "remaining_budget_usd": 50.0,
  "max_rpm": 30
}
```

##### Langkah 5: Simulasikan Serangan Loop Agen (Stress Test Rate Limiter)
Kirim request inferensi chat secara beruntun menggunakan script shell untuk memicu proteksi *Rate Limiting*:

```bash
for i in {1..35}; do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/v1/chat/completions \
    -H "Authorization: Bearer vkey_team_alpha" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "gpt-4o",
      "messages": [{"role": "user", "content": "Hello Autonomous World!"}],
      "stream": false
    }'
done
```

*Verifikasi Hasil*:
Terminal akan menampilkan respons status `200` atau upstream error, lalu berubah secara konsisten menjadi status `429` saat request melebihi limit 30 RPM yang dikonfigurasi pada skrip Redis Lua.

##### Langkah 6: Validasi Sandbox Isolation via Docker gVisor
Uji eksekusi kode agen pada sandbox terisolasi:

```bash
# Uji coba pembatasan memory dan egress isolation
docker run --rm \
  --net=none \
  --memory=256m \
  --pids-limit=32 \
  alpine:latest /bin/sh -c "echo 'Menguji isolasi sandbox...'; ping -c 1 8.8.8.8 || echo 'Network terblokir dengan benar (Egress Lockdown)'"
```

*Ekspektasi Output*:
Pesan kegagalan ping yang mengonfirmasi bahwa isolasi jaringan (*network isolation*) berjalan dengan benar dan runtime berhasil mencegah sandbox mengakses jaringan luar.