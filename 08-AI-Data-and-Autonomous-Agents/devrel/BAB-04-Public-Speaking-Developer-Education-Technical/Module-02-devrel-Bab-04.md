# BAB 04: Public Speaking, Developer Education & Technical Content
## MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang & Mengimplementasikan Arsitektur *High-Availability Live Demo*** yang tahan terhadap kegagalan jaringan panggung, degradasi API eksternal, dan non-determinisme inferensi LLM.
2. **Membangun *CI/CD Testing Pipeline* untuk Konten Edukasi (*Doc-as-Code*)**, memastikan setiap *code snippet*, tutorial, dan *Jupyter Notebook* teruji secara otomatis terhadap *upstream breaking changes*.
3. **Mengembangkan *Multi-Tenant Ephemeral Sandbox Architecture*** untuk *hands-on workshop* berbasis kontainer yang dapat diskalakan secara otomatis untuk ratusan *developer* secara simultan dengan isolasi sumber daya ketat.
4. **Menerapkan *Telemetry Engine*** untuk mengukur metrik adopsi teknis pasca-presentasi seperti *Time-to-First-Hello-World* (TTFHW), retensi kode, dan konversi implementasi API.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib memahami:
* Konsep dasar Developer Relations (DevRel) dan metrik keterlibatan developer (B.A.M. / Orbit Model).
* Administrasi sistem Linux, Docker, dan dasar orkestrasi kontainer (Kubernetes / K3s / Nomad).
* Bahasa pemrograman Python 3.11+ (Asyncio, FastAPI) dan TypeScript/Node.js.
* Pemahaman arsitektur LLM, integrasi API AI (OpenAI/Anthropic spec), dan Vector Databases.
* Pemahaman Git workflow dan GitHub Actions CI/CD.

---

### 3. Concept & Internal Architecture (Mendalam)

Dalam domain **AI, Data, dan Autonomous Agents**, edukasi *developer* dan *public speaking* teknis memiliki tantangan unik: **non-determinisme, latensi eksekusi tinggi, dan risiko kegagalan pihak ketiga (API outages)**. Developer relations engineer tidak sekadar menyajikan slide; mereka menyajikan arsitektur sistem hidup di hadapan ribuan insinyur kritis.

Arsitektur produksi DevRel modern bertumpu pada tiga pilar inti:

```
+-------------------------------------------------------------------------------+
|                       DEVREL PRODUCTION ARCHITECTURE                          |
+------------------------------------+------------------------------------------+
| 1. RESILIENT LIVE-DEMO HARNESS     | 2. DOC-AS-CODE CI/CD AUTOMATION          |
|    - Semantic Caching Proxy        |    - Code Snippet Extractor (AST parser) |
|    - Chaos-tolerant Fallback Engine|    - Synthetic Execution Matrix          |
|    - Virtualized Mock Swarm        |    - Backward Compatibility Verifier     |
+------------------------------------+------------------------------------------+
| 3. EPHEMERAL WORKSHOP SANDBOX      | 4. TELEMETRY & ADOPTION ANALYTICS        |
|    - Firecracker MicroVM / K8s Job |    - Real-time TTFHW Tracker             |
|    - Dynamic Credential Injector   |    - Friction Logs Ingestion Pipeline    |
|    - Pre-warmed Container Pool     |    - Funnel Analytics Collector          |
+------------------------------------+------------------------------------------+
```

#### A. Resilient Live-Demo Harness
Sebuah sistem panggung yang andal tidak pernah bergantung pada koneksi internet publik (*venue Wi-Fi*) atau kestabilan server inferensi live jarak jauh. Arsitektur ini mengintegrasikan:
* **Hybrid Execution Model**: Menjalankan inferensi lokal terkompresi (misal: GGUF via `llama.cpp`) sebagai fallback mulus (*seamless failover*) saat API *cloud* mengalami *rate-limiting* atau *timeout*.
* **Semantic Caching & State Replay Proxy**: Proksi lokal (*reverse proxy*) yang mencatat setiap *request-response* siklus demo selama latihan. Jika request di panggung memiliki kesamaan semantik cosine > 0.95 dengan rekaman lokal, proxy dapat secara cerdas menyajikan respons instan terverifikasi jika latensi jaringan melebihi ambang batas (*circuit breaker threshold*).

#### B. Continuous Documentation & Code Sample Testing Engine (Doc-as-Code)
Tutorial basi adalah penyebab utama churn developer. Modul ini menerapkan *Abstract Syntax Tree* (AST) parsing untuk mengekstrak blok kode dari Markdown/MDX dokumentasi, memasukkannya ke dalam *isolated testcontainers*, dan mengeksekusinya terhadap API *staging* dan *production* secara harian.

#### C. Ephemeral Multi-Tenant Workshop Sandboxes
Saat mengajarkan *Autonomous Agents*, peserta workshop membutuhkan *environment* yang terisolasi untuk menghindari tabrakan state (*filesystem write*, eksekusi kode berbahaya, token exhaustion). Pola arsitekturnya menggunakan MicroVM berbasis *Firecracker* atau *ephemeral namespace* pada K8s dengan resource quotas (CPU, RAM, max egress network) dan auto-destruction TTL (*Time-To-Live*).

---

### 4. Why & What

| Dimensi | Mengapa (Why) | Apa (What) |
| :--- | :--- | :--- |
| **Stage Delivery** | 80% demo panggung AI gagal karena latensi LLM tak terduga, Wi-Fi panggung *drop*, atau kuota API habis di tengah presentasi. | Sistem failover multi-layer: Local Mock Gateway -> Local LLM Fallback -> Live Cloud API dengan transisi visual transparan. |
| **Technical Education** | Developer mengabaikan SDK jika instruksi instalasi dan *quickstart* gagal pada percobaan pertama (*high friction*). | Infrastruktur *Doc-as-Code* yang mengompilasi dan menguji seluruh dokumentasi secara otomatis di berbagai OS dan versi runtime. |
| **Hands-on Workshops** | Mengonfigurasi environment lokal (Docker, Python venv, CUDA) memakan 45 menit pertama workshop (kebocoran waktu 50%). | *Pre-warmed browser-based sandboxes* dengan zero configuration, siap pakai dalam waktu < 3 detik per peserta. |
| **Telemetry & ROI** | DevRel sering dianggap sekadar "marketing" jika tidak mampu membuktikan dampak teknis terhadap adopsi platform. | *Developer telemetry framework* yang memetakan aktivitas tutorial hingga pembuatan *production API keys*. |

---

### 5. How (Workflow Detail)

Alur kerja orkestrasi teknis edukasi developer end-to-end:

```
[ Authoring Stage ]
       │
       ▼
 1. Write Code + Docs in Single Repo (Literate Programming / Markdown AST)
       │
       ▼
 2. Git Push ──> GitHub Actions CI Pipeline
       ├──> Extract Snippets via AST
       ├──> Launch Testcontainers (Vector DB, Agent Engine, Mock Auth)
       ├──> Run Assertions against Test Matrix (Python 3.10, 3.11, 3.12)
       └──> On Success: Deploy to Docs Portal & Generate Runnable Notebooks
       │
[ Stage Preparation ]
       │
       ▼
 3. Pre-record Seed State into Stage-Proxy (Semantic Cache & Mock Snapshot)
       │
       ▼
[ Live Presentation Execution ]
       │
       ▼
 4. Presenter runs code ──> Reverse Proxy Interceptor
       ├──> Network Healthy & Latency < 1500ms? ──> Execute Live Upstream
       └──> Network Failure / Rate Limit / Timeout? ──> Fallback to Semantic Cache / Local LLM
       │
[ Post-Session Developer Onboarding ]
       │
       ▼
 5. Audience scans QR ──> Auto-provisioned Ephemeral Sandbox (TTL: 60 mins)
       │
       ▼
 6. Telemetry Ingestion (Pushes TTFHW, Run Events, Errors to DevRel Analytics)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Penerbangan Ruang Angkasa Berawak
Seorang DevRel Engineer yang mendemonstrasikan sistem AI multi-agent di panggung ibarat pilot uji coba pesawat eksperimental. Pesawat utama ditenagai oleh mesin jet canggih (Live Cloud LLM). Namun, kokpit selalu dilengkapi dengan mesin cadangan berbahan bakar padat (Local GGUF via `llama.cpp`) dan simulator manual terkalibrasi penuh (Semantic Mock Engine). Jika oksigen di ketinggian menipis (Wi-Fi venue putus), pilot memutar tuas ke kontrol analog terenkapsulasi tanpa membuat penumpang (audiens) panik atau menyadari adanya turbulensi kritis.

#### Diagram Arsitektur: Resilient Live Keynote Proxy System

```
                  +----------------------------------------------+
                  |            Presenter Terminal / IDE          |
                  +----------------------+-----------------------+
                                         |
                            HTTP POST http://localhost:8080/v1
                                         |
                                         v
                  +----------------------------------------------+
                  |         LIVE-STAGE HARNESS PROXY             |
                  |                                              |
                  |  +----------------------------------------+  |
                  |  |  Health Check & Latency Monitor (<1.5s)|  |
                  |  +-------------------+--------------------+  |
                  |                      |                       |
                  |         [Route Decision Engine]              |
                  |         /            |             \         |
                  +--------/-------------|--------------\--------+
                          /              |               \
        (Healthy Network)/   (Timeout / Err)    (Offline Mode)
                        /                |                 \
                       v                 v                  v
             +----------------+  +---------------+  +----------------+
             | Cloud LLM API  |  | Semantic DB   |  | Local llama.cpp|
             | (OpenAI / Anth)|  | (ChromaDB /   |  | (Quantized     |
             |                |  |  Local Cache) |  |  Local Engine) |
             +----------------+  +---------------+  +----------------+
                     |                   |                  |
                     +-------------------+------------------+
                                         |
                                         v
                         +-------------------------------+
                         | Formatted Streaming Response  |
                         |  (SSE / Chunked to Presenter) |
                         +-------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: AST Markdown Code Snippet Extractor & Validator
Skrip ini mengekstrak blok kode Python dari berkas dokumentasi markdown dan memverifikasi integritas sintaksisnya menggunakan parser AST bawaan Python untuk mencegah eror sintaks dasar masuk ke portal publik.

```python
# tools/doc_validator.py
import ast
import re
import sys
from pathlib import Path

def extract_python_snippets(markdown_path: Path) -> list[tuple[int, str]]:
    content = markdown_path.read_text(encoding="utf-8")
    # Mencari pola: ```python ... ```
    pattern = re.compile(r"```python\s+(.*?)```", re.DOTALL)
    snippets = []
    
    for match in pattern.finditer(content):
        # Hitung nomor baris kemunculan kode
        line_no = content[:match.start()].count("\n") + 1
        code = match.group(1)
        snippets.append((line_no, code))
    return snippets

def validate_syntax(file_path: Path) -> bool:
    snippets = extract_python_snippets(file_path)
    has_error = False
    print(f"[*] Memeriksa {file_path} ({len(snippets)} snippets ditemukan)...")
    
    for line_no, code in snippets:
        try:
            ast.parse(code)
            print(f"  [PASS] Baris {line_no}: Sintaks valid.")
        except SyntaxError as e:
            print(f"  [FAIL] Baris {line_no}: Kesalahan Sintaks: {e.msg} (offset: {e.offset})", file=sys.stderr)
            has_error = True
            
    return not has_error

if __name__ == "__main__":
    target = Path("docs/quickstart.md")
    if target.exists():
        success = validate_syntax(target)
        sys.exit(0 if success else 1)
    else:
        print("[!] File target tidak ditemukan.")
```

#### B. Practical Example: Production-Grade Keynote Proxy Harness
Sistem proksi cerdas berbasis FastAPI ini dirancang untuk panggung DevRel: mencegat panggilan API LLM, melakukan failover semantik otomatis menggunakan perbandingan embeddings jika terjadi kegagalan koneksi atau timeout > 1.2 detik, dan menyajikan fallback lokal.

```python
# harness/keynote_proxy.py
import os
import time
import httpx
import numpy as np
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List

app = FastAPI(title="DevRel Live Demo Resilient Proxy")

# In-Memory Cache Semantik Sederhana (Untuk lingkungan demo lokal)
class SemanticRecord(BaseModel):
    prompt: str
    embedding: List[float]
    response: Dict[str, Any]

SEMANTIC_CACHE: List[SemanticRecord] = []
UPSTREAM_TIMEOUT = 1.2 # Detik sebelum fallback dipicu
UPSTREAM_URL = "https://api.openai.com/v1/chat/completions"

def mock_get_embedding(text: str) -> List[float]:
    """
    Mock representasi embedding vektor normalisasi untuk demo.
    Dalam produksi: gunakan model fast embedding lokal (misal: ONNX All-MiniLM-L6-v2).
    """
    np.random.seed(len(text))
    vec = np.random.randn(384)
    return (vec / np.linalg.norm(vec)).tolist()

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

@app.on_event("startup")
def seed_golden_state():
    """Memuat respons cadangan (golden paths) yang telah tervalidasi sebelum presentasi."""
    golden_prompt = "Instantiate AgentSwarm with 3 worker nodes"
    SEMANTIC_CACHE.append(
        SemanticRecord(
            prompt=golden_prompt,
            embedding=mock_get_embedding(golden_prompt),
            response={
                "id": "chatcmpl-golden-local",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "gpt-4o-failover-golden",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "AgentSwarm successfully orchestrated: [Worker-1, Worker-2, Worker-3] active."
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 12, "completion_tokens": 14, "total_tokens": 26}
            }
        )
    )
    print(f"[*] Golden seed state terkonfigurasi. {len(SEMANTIC_CACHE)} rute dicadangkan.")

@app.post("/v1/chat/completions")
async def handle_completion(request: Request):
    body = await request.json()
    api_key = request.headers.get("Authorization", "")
    
    extracted_prompt = ""
    messages = body.get("messages", [])
    if messages:
        extracted_prompt = messages[-1].get("content", "")

    # Jalur Utama: Percobaan Upstream dengan Circuit Breaker / Strict Latency Budget
    try:
        async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT) as client:
            headers = {"Authorization": api_key, "Content-Type": "application/json"}
            resp = await client.post(UPSTREAM_URL, json=body, headers=headers)
            
            if resp.status_code == 200:
                print("[LIVE UPSTREAM] Eksekusi berhasil melalui Cloud API.")
                return JSONResponse(status_code=200, content=resp.json())
            else:
                print(f"[WARN] Upstream error {resp.status_code}. Beralih ke semantic failover.")
    except (httpx.TimeoutException, httpx.NetworkError, Exception) as exc:
        print(f"[CIRCUIT BREAKER] Terpicu akibat: {type(exc).__name__}. Mengaktifkan Semantic Fallback Engine.")

    # Jalur Penyelamat: Semantic Cache Matching
    prompt_emb = mock_get_embedding(extracted_prompt)
    best_match = None
    highest_sim = -1.0

    for record in SEMANTIC_CACHE:
        sim = cosine_similarity(prompt_emb, record.embedding)
        if sim > highest_sim:
            highest_sim = sim
            best_match = record

    # Jika kemiripan semantik > 0.70, gunakan respons lokal
    if best_match and highest_sim > 0.70:
        print(f"[RECOVERY SUCCESS] Menyajikan respons dari cache semantik (Sim: {highest_sim:.4f}).")
        cached_resp = best_match.response
        cached_resp["id"] = f"fallback-{int(time.time())}"
        return JSONResponse(status_code=200, content=cached_resp)

    # Jalur Darurat Terakhir: Local Synthetic Response
    print("[CRITICAL] Tidak ada match semantik. Menyajikan respons deterministik sintetis.")
    return JSONResponse(
        status_code=200,
        content={
            "id": "synthetic-emergency",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "[Local Safe Fallback] Operasi multi-agent berhasil di-resolve secara lokal."
                }
            }]
        }
    )
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Insiden
Sebuah perusahaan infrastruktur LLM berskala unicorn global ("AgentCore") meluncurkan modul *Autonomous Swarm Framework* versi 2.0 di hadapan 4.500 penonton langsung pada konferensi tahunan dan 40.000 streaming developer.

#### Problem
1. **Wi-Fi Jamming**: Sinyal Wi-Fi ruangan utama mengalami penurunan *throughput* hingga 98% karena saturasi perangkat penonton.
2. **Provider Throttling**: API endpoint upstream mereka secara mendadak menerapkan *DDoS-protection rate limiting* terhadap IP panggung karena lonjakan ribuan developer audiens yang mengeksekusi instruksi secara bersamaan (*thundering herd problem*).
3. **Docs Out of Sync**: Dokumentasi resmi yang diluncurkan bersamaan memiliki inkonsistensi tipe data: SDK mengharapkan `agent_id: UUID` sedangkan dokumentasi `quickstart.md` mencantumkan `agent_id: str`, menyebabkan eror validasi Pydantic pada 100% audiens yang mencoba secara paralel.

#### Solusi Arsitektural (Implementasi Standar Kelas Enterprise)
1. **Penerapan Isolated Stage-Relay**: Tim DevRel menjalankan proksi lokal di laptop presenter yang terikat ke `localhost:8080`, mengeliminasi dependensi internet eksternal melalui kombinasi *local embedded vector db* dan runtime `llama.cpp` terkuantisasi 4-bit (Mistral-7B-Instruct) sebagai mesin lokal.
2. **Dynamic In-flight Rate-Limiting**: Menerapkan token-bucket limiter per-workshop room ID dengan Redis cluster untuk mengisolasi traffic audiens dari traffic panggung.
3. **Automated Doc-as-Code Pipeline**: Sebelum rilis, pipeline GitHub Actions mengekstrak seluruh snippet dokumentasi, memvalidasi skema Pydantic terhadap SDK master branch, dan secara otomatis memblokir pull request dokumentasi yang tidak selaras.

```
+-------------------------------------------------------------------------------+
|                            AGENTCORE RELIABILITY ENGINE                       |
+-------------------------------------------------------------------------------+
|  Venue Failure (Wi-Fi drop & Rate-limits)                                     |
|     │                                                                         |
|     ├──> Presenter Machine: Local Proxy intercept -> Local Model (0 Latency)  |
|     │                                                                         |
|     └──> Audience Traffic: Directed to Regional Edge Workers                  |
|             │                                                                 |
|             ├──> Tenant Isolation: Workshop API Key (Rate limited: 10 RPM)    |
|             └──> Docs Consistency: Enforced by CI AST Test Matrix             |
+-------------------------------------------------------------------------------+
```

#### Hasil Terukur
* Keynote selesai tanpa eror visual di layar panggung (*zero perceived downtime*).
* Metrik *Time-to-First-Hello-World* (TTFHW) audiens yang menggunakan lingkungan *pre-warmed* browser mencapai rerata **1 menit 42 detik**, dibandingkan 28 menit pada konferensi tahun sebelumnya.
* 0 bug dokumentasi dilaporkan dalam 72 jam pasca-konferensi berkat implementasi validasi AST end-to-end.

---

### 9. Trade-offs

Mengembangkan sistem edukasi developer dan infrastruktur demo panggung melibatkan kompromi teknis yang signifikan:

| Parameter | Pendekatan A: Full Live Upstream | Pendekatan B: Local / Hybrid Failover Harness | Justifikasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Authenticity vs Reliability** | 100% Autentik, memperlihatkan latensi dan perilaku model sesungguhnya. | Autentisitas parsial jika terjadi failover semantik/lokal. | Di panggung berisiko tinggi (*keynote*), **keandalan mengalahkan autentisitas murni**. Kegagalan demo merusak reputasi platform. |
| **Latency vs Cost** | Latensi bergantung pada internet; biaya cloud LLM tinggi jika audiens melakukan *spamming*. | Menambah kompleksitas lokal proxy; perlu maintain state rekaman demo. | Menggunakan hybrid proxy memangkas risiko latensi stage panggung dari $\infty$ (timeout) menjadi $< 50$ ms via lokal cache. |
| **Isolation vs Resource Consumption (Workshop)** | *Shared Multi-Tenant Serverless*: Murah, tetapi risiko *noisy neighbor* tinggi antar peserta. | *Isolated MicroVM (Firecracker) per User*: Isolasi total, aman, tetapi konsumsi RAM tinggi. | Untuk workshop *Autonomous Agent* yang mengizinkan eksekusi kode bebas (*sandboxed execution*), MicroVM adalah keharusan mutlak. |
| **Doc-as-Code Testing Duration** | Verifikasi sintaksis statis (cepat, $< 1$ menit pada CI). | End-to-end Container Execution dengan live API (lambat, memakan biaya token API). | Jalankan analisis statis pada setiap *push*, dan eksekusi integrasi penuh secara *nightly* untuk menyeimbangkan durasi CI dan biaya. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns)
1. **Hardcoding API Keys pada Slide atau Repo Publik Tutorial**: Developer mengunggah repositori demo yang berisi `.env` aktif. Bot penjelajah GitHub mencuri kunci API dalam hitungan detik, memicu penutupan akun di tengah presentasi.
2. **Ketergantungan Eksternal Tak Terkunci (*Unpinned Dependencies*)**: Tutorial menyarankan `pip install agent-sdk`. Ketika library merilis versi minor dengan breaking change 2 jam sebelum workshop, seluruh *environment* peserta hancur.
3. **Mengabaikan Non-Determinisme LLM**: Membuat demo panggung yang mengharapkan respons JSON kaku dari model generatif dengan `temperature > 0` tanpa *structural output parser* (seperti Instructor atau Pydantic JSON mode).

#### Prosedur Troubleshooting Terstruktur

```
+----------------------------------------------------------------------------------+
|                            SYMPTOM RESOLUTION MATRIX                             |
+-----------------------+----------------------------------+-----------------------+
| GEJALA (SYMPTOM)      | AKAR MASALAH (ROOT CAUSE)        | MITIGASI SEGERA       |
+-----------------------+----------------------------------+-----------------------+
| 1. HTTP 429           | Token/Request Quota exhausted    | Aktifkan local proxy  |
|    (Rate Limited)     | karena audiens memakai key panggung| failover; injeksikan  |
|    di panggung        |                                  | kunci cadangan tier 4 |
+-----------------------+----------------------------------+-----------------------+
| 2. Pydantic           | Skema JSON berubah karena output | Terapkan output       |
|    ValidationError    | non-deterministik LLM            | constraints (JSON     |
|    di layar panggung  |                                  | Schema mode/Grammars) |
+-----------------------+----------------------------------+-----------------------+
| 3. Docker build fail  | Upstream package mirror down /   | Bangun base image     |
|    pada mesin peserta | internet lambat di lokasi acara  | *pre-baked* & distribusikan|
|    workshop           |                                  | via local registry / USB|
+-----------------------+----------------------------------+-----------------------+
| 4. Latensi inferensi  | Jaringan seluler / Wi-Fi drop;   | Switch DNS ke lokal   |
|    > 10 detik         | TCP connection stalling          | loopback proksi       |
+-----------------------+----------------------------------+-----------------------+
```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum dan sesudah pelaksanaan edukasi teknis skala besar:

#### Pre-Flight Checklist (H-24 Jam hingga H-1 Jam)
- [ ] **Kunci Dependensi**: Semua berkas tutorial menggunakan lockfile biner (`poetry.lock`, `uv.lock`, atau `package-lock.json`).
- [ ] **Pre-baked Images**: Kontainer sandbox untuk peserta sudah di-*build* dan di-*push* ke container registry global (GHCR/ECR) dengan tag rilis eksplisit, bukan `latest`.
- [ ] **Lokal Proxy Warming**: Presenter telah merekam minimal 3 kali iterasi sukses skenario demo ke dalam cache semantik lokal.
- [ ] **Isolasi Kuota API**: Akun panggung menggunakan organisasi billing terpisah dari akun yang dibagikan untuk workshop publik.
- [ ] **Network Circuit Breaker**: Proksi panggung disetel dengan batas timeout maksimal 1500 ms sebelum beralih ke engine lokal.
- [ ] **Kesiapan Offline**: Runtime lokal (`llama.cpp` dengan bobot GGUF terverifikasi) siap berjalan di latar belakang tanpa koneksi jaringan sama sekali.

#### In-Flight Checklist (Saat Presentasi Berjalan)
- [ ] Monitor *status visual indicator* pada proksi lokal (hijau: live upstream; kuning: fallback semantik; merah: local synthetic fallback).
- [ ] Nonaktifkan notifikasi sistem dan update otomatis OS/software yang berpotensi memutus port local binding.

#### Post-Flight Checklist (Pasca Presentasi)
- [ ] **Rotasi API Key**: Hapus atau rotasi semua token sementara yang diproyeksikan di layar atau dibagikan ke peserta.
- [ ] **Ingest Friction Log**: Kumpulkan log error dari sandbox peserta untuk mengidentifikasi baris kode dokumentasi yang paling banyak memicu kegagalan.
- [ ] **Metrik Evaluasi**: Ukur rasio konversi peserta workshop yang beralih ke portal developer mandiri dalam kurun waktu 7 hari.

---

### 12. Hands-on Practice

Buat dan simpan struktur berkas berikut di dalam direktori `hands-on/m02/`:

```
hands-on/m02/
├── Makefile
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── agent.py
│   └── test_doc_samples.py
└── docs/
    └── agent_tutorial.md
```

#### Langkah 1: Siapkan dependensi (`hands-on/m02/requirements.txt`)
```text
httpx==0.27.0
pytest==8.2.0
pydantic==2.7.1
pytest-asyncio==0.23.6
```

#### Langkah 2: Buat kode agent inti (`hands-on/m02/src/agent.py`)
```python
# hands-on/m02/src/agent.py
from pydantic import BaseModel, Field
from typing import List

class AgentExecutionResult(BaseModel):
    task: str
    steps_taken: List[str]
    success: bool
    execution_time_ms: float

class ResilientDemoAgent:
    def __init__(self, name: str):
        self.name = name

    def execute_plan(self, task: str) -> AgentExecutionResult:
        if not task:
            raise ValueError("Task cannot be empty.")
        
        # Simulasi deterministik yang aman untuk demonstrasi
        steps = [
            f"Step 1: Parse requirements for {task}",
            "Step 2: Query memory context",
            "Step 3: Execute target operational action"
        ]
        return AgentExecutionResult(
            task=task,
            steps_taken=steps,
            success=True,
            execution_time_ms=42.0
        )
```

#### Langkah 3: Buat dokumen tutorial teknis (`hands-on/m02/docs/agent_tutorial.md`)
```markdown
# Panduan Cepat Pembuatan Autonomous Agent

Gunakan SDK berikut untuk menginisialisasi dan menjalankan task dasar:

```python
from src.agent import ResilientDemoAgent

agent = ResilientDemoAgent(name="DemoWorker")
result = agent.execute_plan(task="Vectorize Database Indices")
assert result.success is True
assert len(result.steps_taken) == 3
print("Eksekusi Sukses!")
```

Contoh di atas menunjukkan siklus hidup agen dasar.
```

#### Langkah 4: Buat automated Doc-as-Code test runner (`hands-on/m02/src/test_doc_samples.py`)
```python
# hands-on/m02/src/test_doc_samples.py
import re
import pytest
from pathlib import Path

def extract_python_blocks(file_path: Path):
    content = file_path.read_text(encoding="utf-8")
    pattern = re.compile(r"```python\s+(.*?)```", re.DOTALL)
    return pattern.findall(content)

def test_tutorial_markdown_snippets():
    doc_path = Path("docs/agent_tutorial.md")
    assert doc_path.exists(), "File tutorial tidak ditemukan!"
    
    snippets = extract_python_blocks(doc_path)
    assert len(snippets) > 0, "Tidak ada blok kode Python ditemukan dalam markdown!"
    
    for idx, code in enumerate(snippets):
        # Mengeksekusi blok kode dalam lingkup lokal terisolasi
        exec_scope = {}
        try:
            exec(code, exec_scope)
        except Exception as e:
            pytest.fail(f"Blok kode dokumentasi #{idx+1} gagal dieksekusi! Error: {e}")
```

#### Langkah 5: Buat target otomatisasi (`hands-on/m02/Makefile`)
```makefile
.PHONY: install test validate

install:
	pip install -r requirements.txt

test:
	pytest -v src/test_doc_samples.py

validate: install test
	@echo "Seluruh dokumentasi tutorial terverifikasi valid secara otomatis."
```

#### Langkah 6: Eksekusi pengujian
Jalankan di terminal:
```bash
cd hands-on/m02/
make validate
```

---

### 13. Exercise

#### Level Easy
Ubah berkas `hands-on/m02/src/agent.py` agar metode `execute_plan` menerima parameter opsional `timeout_seconds: float = 5.0`. Perbarui berkas `hands-on/m02/docs/agent_tutorial.md` untuk menyertakan parameter baru tersebut, dan pastikan pengujian `make test` tetap berstatus **PASS**.

#### Level Medium
Buat modul Python `hands-on/m02/src/telemetry.py` yang mengimplementasikan class `DeveloperFrictionTracker`. Class ini harus:
1. Menghitung waktu antara eksekusi baris pertama kode tutorial hingga assertion terakhir berhasil (*Time-to-First-Hello-World*).
2. Menghasilkan payload JSON yang menyimpan metrik latensi, sistem operasi penguji, dan status keberhasilan pengujian.
3. Mengintegrasikan tracker ini ke dalam `src/test_doc_samples.py`.

#### Level Hard
Kembangkan middleware asynchronous berbasis FastAPI (`hands-on/m02/src/circuit_breaker.py`) yang menerapkan algoritma *Moving Window Error-Rate*.
* Jika dalam rentang 10 panggilan terakhir terdapat lebih dari 3 error atau waktu respons $> 2000$ ms, status circuit breaker berubah menjadi `OPEN`.
* Saat berstatus `OPEN`, seluruh panggilan request API langsung dialihkan ke respons mock lokal terkuantisasi tanpa mengirimkan payload ke jaringan eksternal.
* Sediakan unit test berbasis `pytest-asyncio` yang mensimulasikan kegagalan jaringan acak.

---

### 14. Challenge

**Skenario**:
Platform Anda merilis SDK "Autonomous Data Pipeline Agent" yang berinteraksi langsung dengan kluster Apache Kafka dan Vector Database. Anda ditugaskan merancang arsitektur presentasi dan workshop interaktif berskala internasional (dihadiri oleh 1.000 engineer serentak secara remote).

**Spesifikasi Desain & Batasan Masalah**:
1. Setiap peserta harus mendapatkan lingkungan eksekusi Kafka + Vector DB + SDK yang sepenuhnya terisolasi tanpa memerlukan instalasi Docker pada mesin lokal mereka.
2. Lingkungan sandbox harus memiliki *cold-start time* di bawah 5 detik per peserta dan langsung musnah jika tidak ada aktivitas selama 15 menit (*idle destruction*).
3. Biaya infrastruktur komputasi untuk 1.000 peserta selama durasi workshop 2 jam tidak boleh melebihi **USD $150**.
4. Panggung live keynote Anda harus menjamin nol kegagalan demonstrasi sekalipun koneksi satelit venue terputus total selama 5 menit tepat di tengah eksekusi demonstrasi orkestrasi agent.

**Tugas**:
Susun dokumen spesifikasi arsitektur komprehensif (`hands-on/m02/CHALLENGE_DESIGN.md`) yang memuat:
* Diagram topologi arsitektur kluster sandbox (pilihan orkestrator: K3s lightweight pod pooling vs Firecracker vs WebAssembly sandbox) beserta kalkulasi biaya komputasi rincinya.
* Desain mekanisme *failover stage* (Local Daemon, DNS override, State Replication).
* Pipeline CI/CD yang menguji keabsahan 100% tutorial terhadap 3 versi minor Kafka yang berbeda secara paralel sebelum rilis publik.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. Mengapa menyematkan (*pinning*) versi dependensi pada repositori edukasi developer jauh lebih krusial dibandingkan pada aplikasi internal tertutup?
2. Apa tujuan utama dari konsep arsitektur *Doc-as-Code* dalam ekosistem DevRel modern?
3. Sebutkan kelemahan utama mengandalkan Wi-Fi venue secara langsung saat mendemonstrasikan sistem AI generatif berbasis streaming response!
4. Apa yang dimaksud dengan metrik TTFHW (*Time-to-First-Hello-World*), dan mengapa metrik ini menjadi tolok ukur efektivitas Developer Education?
5. Mengapa teknik pencocokan respons semantik (*semantic cache*) lebih unggul dibandingkan *exact string matching* (seperti Redis hashing biasa) untuk failover demo AI?

#### Intermediate Questions
6. Bagaimana cara mencegah audiens workshop mengeksploitasi token API yang dibagikan secara massal untuk kebutuhan pribadi di luar modul pembelajaran?
7. Jelaskan bagaimana AST (*Abstract Syntax Tree*) parser bekerja dalam mengaudit kode tutorial tanpa mengeksekusi semantik kodenya secara langsung!
8. Apa perbedaan mendasar antara *circuit breaker pattern* standar pada aplikasi mikroservis backend dengan *circuit breaker* yang dioptimasi khusus untuk demo harness panggung?
9. Dalam merancang *ephemeral workshop sandbox*, faktor apa yang membuat penggunaan WebAssembly (Wasm) lebih hemat biaya dibandingkan kontainer Docker konvensional?
10. Bagaimana Anda mendeteksi degradasi performa (*drift*) pada konten tutorial ketika API penyedia LLM eksternal melakukan pembaruan bobot (*silent model update*)?

#### Production Case Scenarios
11. **Skenario Kasus 1**: Pada sesi live coding internasional, API key platform Anda terkena pembatasan kuota global (*rate limit*) 30 detik sebelum demo utama dijalankan. Anda tidak memiliki internet untuk membuka dashboard admin. Jelaskan langkah arsitektural terencana yang harus secara otomatis menyelamatkan demonstrasi tersebut tanpa intervensi manual!
12. **Skenario Kasus 2**: Tutorial developer Anda memiliki rating kepuasan rendah. Data telemetry menunjukkan 60% developer mengalami drop-off di langkah ke-3, yaitu setup koneksi konektor database lokal. Solusi edukasi arsitektural apa yang harus diimplementasikan untuk memangkas *friction drop-off* tersebut secara definitif?
13. **Skenario Kasus 3**: Tim dokumentasi Anda memproses 50 pull request dokumentasi per minggu dari kontributor komunitas open-source. Beberapa kontributor secara tidak sengaja memasukkan snippet kode yang memiliki celah keamanan eksekusi kode *arbitrary code injection* (`eval()`, `os.system()`). Bagaimana Anda merancang gerbang verifikasi CI/CD otomatis untuk menangkal ancaman ini?

---

### Jawaban & Kunci Penilaian Quiz

1. **Basic**: Karena lingkungan lokal audiens sangat heterogen. Jika dependensi tidak dikunci, pembaruan rilis minor library upstream dapat merusak kompatibilitas dependensi silang, menyebabkan tutorial gagal pada saat pertama kali dicoba oleh developer baru.
2. **Basic**: Memperlakukan dokumentasi selayaknya kode produksi: tersimpan di version control, ditinjau melalui pull request, dan diuji integritas fungsionalnya melalui automated testing pipeline (CI/CD).
3. **Basic**: Saturasi bandwidth akibat ribuan perangkat penonton memicu packet loss tinggi, jitter ekstrem, dan pemutusan socket TCP, yang menyebabkan streaming token terhenti atau timeout fatal di panggung.
4. **Basic**: TTFHW adalah durasi waktu dari saat developer pertama kali mendarat di dokumentasi/repositori hingga mereka berhasil mengeksekusi kode fungsional pertama. Semakin rendah TTFHW, semakin tinggi tingkat retensi developer.
5. **Basic**: Input developer pada sistem AI sering kali memiliki variasi frasa alami (non-deterministik). *Exact matching* akan gagal jika ada satu spasi atau sinonim berbeda, sedangkan *semantic cache* dapat mengenali intensi perintah yang sama berdasarkan jarak vektor embedding.
6. **Intermediate**: Terapkan API Gateway terisolasi dengan otentikasi berbasis waktu (*ephemeral tokens*), pembatasan IP subnet venue, kuota ketat per route (misal: max 20 request/menit), dan pemblokiran akses ke endpoint model di luar konteks modul workshop.
7. **Intermediate**: AST parser membaca string mentah kode sumber dan membangun representasi pohon struktural sintaksis bahasa pemrograman. Ini memungkinkan validasi kebenaran tata bahasa, identifikasi impor modul berbahaya, dan ekstraksi variabel tanpa perlu mengalokasikan memori runtime atau mengeksekusinya.
8. **Intermediate**: Circuit breaker panggung DevRel memiliki ambang batas waktu (*latency budget*) yang sangat agresif (misal: $<1.5$ detik) dan tidak melempar HTTP 500 error kepada klien; alih-alih melempar error, ia secara instan membelokkan output ke cache semantik terverifikasi lokal secara transparan.
9. **Intermediate**: Wasm runtime memiliki jejak memori yang sangat minim (orde kilobyte hingga megabyte), cold-start instan dalam hitungan mikrodetik, dan densitas isolasi tinggi yang memungkinkan ribuan instance berjalan pada satu node komputasi murah.
10. **Intermediate**: Menerapkan pipeline synthetic testing *nightly* yang mengeksekusi assertion berbasis evaluasi kualitas (misal: Ragas atau LLM-as-a-Judge) terhadap golden dataset dokumentasi untuk mendeteksi deviasi keluaran model baru.
11. **Production Scenario 1**: Konfigurasi proxy lokal reverse-proxy panggung (`http://localhost:8080`) harus memiliki fallback logic bertingkat: saat upstream mengembalikan status HTTP 429, proxy secara deterministik menangkap status tersebut, mengabaikannya, dan langsung mengalirkan respon dari local cached snapshot yang tersimpan di disk lokal.
12. **Production Scenario 2**: Ganti petunjuk manual instalasi lokal dengan *Browser-based Interactive Sandbox* (seperti Dev Containers via GitHub Codespaces atau embedded WebAssembly execution container) yang telah mengonfigurasi database in-memory secara otomatis, menghilangkan friksi setup awal.
13. **Production Scenario 3**: Bangun custom static analysis linter menggunakan AST checking pada CI pipeline yang memindai setiap blok markdown. Jika ditemukan pemanggilan fungsi berisiko tinggi seperti `eval()`, `exec()`, `subprocess`, atau `os.system` tanpa sanitisasi eksplisit, CI otomatis membatalkan build dan menandai PR sebagai *insecure*.

---

### 16. Summary

Edukasi developer dan presentasi teknis tingkat enterprise dalam ekosistem AI bukan sekadar seni komunikasi personal, melainkan **disiplin rekayasa keandalan sistem (*reliability engineering*)**. Live demo yang sukses di hadapan audiens teknis membutuhkan infrastruktur hybrid berlatensi rendah yang kebal terhadap kegagalan infrastruktur eksternal via *circuit breaker* dan *semantic proxying*. 

Secara simultan, keberhasilan jangka panjang adopsi platform bergantung pada integritas materi edukasi. Menerapkan arsitektur **Doc-as-Code** dengan pengujian AST otomatis memastikan dokumentasi tidak pernah kadaluwarsa. Dengan memadukan infrastruktur panggung yang tangguh (*resilient stage harness*), sandbox workshop sekali pakai (*ephemeral sandboxes*), dan analitik friksi developer (*friction telemetry*), DevRel engineer mampu menjembatani inovasi arsitektur produk yang kompleks dengan adopsi developer nyata yang terukur secara presisi.