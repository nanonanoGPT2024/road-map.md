# BAB 10: Building, Scaling, and Leading a DevRel Organization
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan DevRel Telemetry Pipeline**: Membangun arsitektur data terdistribusi untuk melacak *Developer Journey*, mulai dari *Time-to-First-Hello-World* (TTFW), adopsi SDK, hingga drop-off rate pada endpoint API berbasis AI/Autonomous Agents.
2. **Membangun Sistem Automated Docs-as-Code Verification Harness**: Mengembangkan sistem CI/CD mutakhir yang secara otomatis mengekstraksi, menguji, dan memvalidasi seluruh cuplikan kode (*code snippets*) dan *agentic tools schema* di dalam repositori dokumentasi ke dalam isolated sandbox microVM.
3. **Mengorkestrasi Autonomous Community Triage Engine**: Mengimplementasikan arsitektur *event-driven autonomous agent* yang mampu menganalisis issue GitHub, thread Discord/Discourse, memproduksi *reproducible test cases* secara mandiri, dan mengklasifikasikan tiket berdasarkan urgensi teknis serta dampak pada ekosistem pengembang.
4. **Mengelola Skalabilitas dan Keamanan Ekosistem DevRel**: Menangani tantangan isolasi kode eksekusi acak dari pihak ketiga (developer community), *rate limiting*, *token budget allocation*, dan atribusi pipeline bisnis tanpa merusak integritas *open-source developer trust*.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut:
* **Pemrograman Backend**: Kemahiran tingkat lanjut dalam Python 3.11+ (AsyncIO, Pydantic v2, FastAPI) dan TypeScript/Node.js.
* **Arsitektur Sistem Terdistribusi**: Pemahaman mendalam mengenai Message Broker (Apache Kafka, RabbitMQ, atau AWS EventBridge), Docker Engine API, serta OpenTelemetry standard.
* **Autonomous Agents & LLM Infrastructure**: Pemahaman arsitektur LLM orchestration (Function Calling, Tool Use, LangChain/LlamaIndex atau *native API clients* Anthropic/OpenAI), dan konsep *sandboxed execution* (Docker, Firecracker, atau E2B).
* **GitOps & CI/CD**: Pengalaman mendalam membangun GitHub Actions, containerized workflow, dan Docs-as-Code (Docusaurus, Mintlify, atau MkDocs).

---

### 3. Concept & Internal Architecture (Mendalam)

Membangun organisasi Developer Relations (DevRel) pada domain **AI, Data, and Autonomous Agents** membutuhkan pergeseran paradigma dari *advocacy berbasis relasi* murni menjadi *engineering-driven enablement*. Produk berbasis Agentic AI (seperti SDK orchestration, framework autonomous agent, vector database, dan semantic router) memiliki tingkat kegagalan non-deterministik yang tinggi. DevRel modern harus bertindak sebagai *first-line distributed systems engineer*.

Arsitektur produksi DevRel Engineering Platform terdiri dari empat subsistem utama:

```
[ Developer Touchpoints ]
(GitHub / Discord / Discourse / API Gateways / IDE Plugins)
                           │ (Webhooks & Telemetry Events)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Ingestion & Event-Driven Processing Engine                   │
│    - API Gateway & Webhook Normalizer (FastAPI)                 │
│    - Streaming Buffer (Kafka / Redpanda Cluster)                │
└──────────────────┬──────────────────────────────────────────────┘
                   │
         ┌─────────┴───────────────────────┐
         ▼                                 ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│ 2. Telemetry & Analytics Hub  │ │ 3. Automated Dev-Sandbox &    │
│    - OpenTelemetry Collector  │ │    Triage Agent               │
│    - TTFW & Drop-off Tracker  │ │    - MicroVM/Docker Runner    │
│    - ClickHouse / TimescaleDB │ │    - LLM Triage & Root Cause  │
│    - Developer Health Matrix  │ │    - Dynamic Issue Generator  │
└───────────────────────────────┘ └───────────────┬───────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Continuous Docs-as-Code & Codebase Validation                │
│    - AST (Abstract Syntax Tree) Parser for Markdown/MDX         │
│    - Multi-SDK Matrix Runner (Python, TS, Go)                   │
│    - Regression & Deprecation Alerter                           │
└─────────────────────────────────────────────────────────────────┘
```

#### Komponen Internal Arsitektur:

1. **Event Ingestion & Normalization Layer**:
   Menerima payload heterogen dari GitHub Webhooks (Issues, PRs, Discussions), Discord Bot Gateway (Message Create, Reaction), dan API Gateway Analytics (Kong/Envoy via OpenTelemetry traces). Normalizer mengonversi payload tersebut ke dalam schema seragam berbasis CloudEvents v1.0.

2. **Telemetry & Funnel Engine (DX Observability)**:
   Melacak *Time to First "Hello World"* (TTFW). Metrik dihitung dari timestamp registrasi akun / instalasi SDK hingga keberhasilan pemanggilan API endpoint pertama dengan status kode `200 OK` dan latensi inferensi di bawah SLA. Data dialirkan ke ClickHouse untuk analisis *cohort developer retention*.

3. **Autonomous Community Triage & Execution Engine**:
   Ketika pengembang melaporkan *bug* agentic loop di GitHub atau Discord (misalnya: `"Tool calling loop exceeds recursion limit when calling database tool"`), sistem secara otomatis:
   * Melakukan ekstraksi *code snippet* dan *trace log* menggunakan LLM Structured Outputs.
   * Menginstansiasi container isolasi (*ephemeral sandbox*) via Docker SDK atau microVM.
   * Menjalankan kode tersebut untuk memverifikasi apakah terjadi *true positive bug* pada SDK inti atau kesalahan konfigurasi (*developer error*).
   * Menghasilkan laporan diagnostik lengkap beserta tautan repositori yang diperbaiki.

4. **Continuous Documentation Verification Harness**:
   Dokumentasi AI SDK sering usang akibat pembaruan model dasar (foundation model) atau perubahan skema API parameters. Pipeline ini memindai setiap file markdown dalam repositori dokumentasi, mengekstrak blok kode Python/TypeScript via Abstract Syntax Tree (AST), menjalankan blok kode tersebut terhadap cluster pengujian terisolasi (mocking AI inference endpoints untuk efisiensi biaya), dan memblokir *merge* PR jika terdapat dokumentasi yang *broken*.

---

### 4. Why & What

| Dimensi | Pendekatan DevRel Tradisional | Enterprise Platform-Driven DevRel (AI/Data) |
| :--- | :--- | :--- |
| **Operasional Utama** | Kehadiran konferensi, sponsorship, penulisan artikel manual secara sporadis. | *Developer Infrastructure Engineering*, pembuatan SDK otomatis, monitoring metrik DX end-to-end. |
| **Penyelesaian Masalah** | Dev Advocate membaca issue secara manual dan membalas rata-rata dalam 24-48 jam. | *Autonomous Triage Engine* memvalidasi dan mereproduksi issue di sandbox dalam < 5 menit. |
| **Verifikasi Dokumentasi** | Diuji manual saat ada komplain dari komunitas di forum publik. | *Docs-as-Code CI/CD Harness* mengeksekusi 100% sampel kode pada setiap commit secara deterministik. |
| **Metrik Keberhasilan** | Vanity metrics: Impressions Twitter, views blog post, attendance hackathon. | Actionable metrics: P95 TTFW, Developer Churn Rate per SDK Version, Error Resolution Latency. |

*Why does this matter for Autonomous Agents?*
Sistem Autonomous Agent sangat sensitif terhadap *breaking changes* kontraktual (seperti token payload formatting, model context window drift, dan skema JSON-schema validation). Tanpa infrastruktur otomatis, organisasi DevRel akan tenggelam dalam *technical support debt*, menyebabkan pengembang meninggalkan ekosistem Anda dan beralih ke alternatif kompetitor.

---

### 5. How (Workflow Detail)

Alur kerja operasional otomatisasi penanganan ekosistem pengembang:

```
[Developer Menemukan Masalah pada SDK Agent]
                  │
                  ▼
[Submit GitHub Issue / Discord Error Log]
                  │
                  ▼
[Webhook Receiver memvalidasi Signature & Payload]
                  │
                  ▼
[Ekstraksi Cuplikan Kode & Konfigurasi Lingkungan via LLM Parser]
                  │
                  ▼
[Inisiasi Ephemeral Container Sandbox (Network-Restricted)]
                  │
                  ├── Error Terbukti? ──(TIDAK)──> [Kirim Solusi Konfigurasi ke Pengembang via Bot]
                  │
                 (YA)
                  ▼
[Identifikasi Bug di Internal Engine]
                  │
                  ▼
[Buat Reproducible Test Case (Pytest / Vitest)]
                  │
                  ▼
[Auto-assign Issue ke Core Engineering Team dengan Label P0/P1]
```

Tahapan Verifikasi Dokumentasi Otomatis (Docs-as-Code Pipeline):
1. **Source Parsing**: Ekstraksi semua blok kode berlabel ````python ... ```` atau ````typescript ... ```` dari pohon direktori dokumentasi.
2. **Context Synthesis**: Injeksi dependensi, mock environment variables (seperti dummy API Key), dan mock LLM responses untuk memastikan tes tidak mengonsumsi kredit LLM berlebih.
3. **Sandbox Execution**: Eksekusi paralel di dalam isolasi container dengan timeout ketat (maksimal 30 detik per sampel).
4. **Failure Interception**: Jika terjadi *failure*, laporkan nomor baris tepat pada file markdown terkait, deskripsi *exception trace*, dan buat PR otomatis perbaikan skema API jika terdeteksi *outdated signature*.

---

### 6. Analogy & Diagram ASCII

#### Analogi:
Bayangkan sistem DevRel Enterprise seperti **Sistem Kendali Umpan Balik Tertutup (Closed-Loop Feedback Control System)** pada roket luar angkasa:
* **Sensor**: OpenTelemetry traces di API Gateway dan Webhook GitHub/Discord yang mengukur *friksi* yang dialami astronaut (developer).
* **Controller**: Autonomous Triage Engine yang menganalisis telemetri dan menentukan koreksi arah tanpa perlu menunggu rapat operasional manual.
* **Actuator**: Docs-as-Code runner dan PR generator otomatis yang memperbaiki kode rusak dan rute dokumentasi secara *real-time*.

#### Arsitektur Aliran Data (ASCII Diagram):

```
+-------------------------------------------------------------------------------+
|                        DEVELOPER EXPERIENCE ENGINE                            |
+-------------------------------------------------------------------------------+
       |                                                 |
[Dev Submits Snippet]                             [Docs Repo Commit]
       |                                                 |
       v                                                 v
+-----------------------+                         +-----------------------+
|  GitHub/Discord Hook  |                         |  GitHub Actions PR    |
+-----------------------+                         +-----------------------+
       |                                                 |
       v                                                 v
+-----------------------+                         +-----------------------+
| FastAPI Webhook Svc   |                         | Markdown AST Parser   |
+-----------------------+                         +-----------------------+
       |                                                 |
       |  (Extract Snippet via AST / LLM)                | (Extract Snippets)
       +-----------------------+ ------------------------+
                               |
                               v
               +-------------------------------+
               |    Sandbox Execution Host     |
               | (Docker API / Isolated cgroups)|
               +-------------------------------+
                               |
               +---------------+---------------+
               |                               |
       [Success: Exit 0]               [Failure: Exit 1]
               |                               |
               v                               v
       +---------------+               +-------------------------------+
       | Cache Result  |               | Autonomous Diagnostic Engine  |
       | & Log Metrics |               | (LLM Root Cause Analyzer)     |
       +---------------+               +-------------------------------+
                                               |
                                               v
                                       +-------------------------------+
                                       | Automated GitHub Comment / PR |
                                       | & PagerDuty Alert Trigger     |
                                       +-------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Local Markdown Code Extractor & Validator
Skrip Python mandiri untuk mengekstraksi dan mengecek sintaksis blok kode Python dari satu file markdown menggunakan *Abstract Syntax Tree* (AST).

```python
import ast
import re
import sys
from pathlib import Path

def validate_markdown_python_snippets(file_path: str) -> bool:
    content = Path(file_path).read_text(encoding="utf-8")
    # Regex untuk mendeteksi blok kode python
    code_blocks = re.findall(r"```python\n(.*?)\n```", content, re.DOTALL)
    
    if not code_blocks:
        print(f"[INFO] Tidak ada blok kode Python ditemukan di {file_path}")
        return True

    all_passed = True
    for index, code in enumerate(code_blocks, start=1):
        try:
            ast.parse(code)
            print(f"[SUCCESS] Snippet #{index} di {file_path} valid secara sintaksis.")
        except SyntaxError as e:
            print(f"[ERROR] Snippet #{index} di {file_path} GAGAL: {e.msg} (Baris {e.lineno})")
            all_passed = False
            
    return all_passed

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Penggunaan: python simple_validator.py <path_to_markdown>")
        sys.exit(1)
        
    success = validate_markdown_python_snippets(sys.argv[1])
    sys.exit(0 if success else 1)
```

#### B. Practical Enterprise Example: Ephemeral Sandbox Verification & Diagnostic Service
Sistem berbasis FastAPI dan Docker SDK untuk mengeksekusi kode developer/dokumentasi secara aman di dalam sandbox container terisolasi, lengkap dengan isolasi resource (CPU, Memory, Network) dan penanganan timeout.

```python
# app/sandbox_engine.py
import asyncio
import os
import shutil
import tempfile
import uuid
from typing import Dict, Any, Optional
import docker
from docker.errors import ContainerError, ImageNotFound, APIError
from pydantic import BaseModel, Field

class ExecutionRequest(BaseModel):
    code: str = Field(..., description="Kode Python SDK yang akan dieksekusi")
    dependencies: list[str] = Field(default_factory=list, description="Daftar library tambahan pip")
    timeout_seconds: int = Field(default=15, ge=1, le=60)
    mock_env_vars: Dict[str, str] = Field(default_factory=dict)

class ExecutionResult(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    error_diagnostic: Optional[str] = None

class EphemeralSandboxManager:
    def __init__(self, base_image: str = "python:3.11-slim"):
        self.base_image = base_image
        self.client = docker.from_env()
        self._ensure_image()

    def _ensure_image(self):
        try:
            self.client.images.get(self.base_image)
        except ImageNotFound:
            print(f"Mengunduh base image {self.base_image}...")
            self.client.images.pull(self.base_image)

    async def execute_code_safely(self, request: ExecutionRequest) -> ExecutionResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run_blocking_sandbox, request)

    def _run_blocking_sandbox(self, request: ExecutionRequest) -> ExecutionResult:
        temp_dir = tempfile.mkdtemp(prefix="devrel_sandbox_")
        script_file_path = os.path.join(temp_dir, "run_target.py")
        
        # Penulisan skrip pengembang ke file terisolasi
        with open(script_file_path, "w", encoding="utf-8") as f:
            f.write(request.code)

        # Siapkan perintah eksekusi
        install_cmd = ""
        if request.dependencies:
            sanitized_deps = [dep.replace(";", "").replace("&", "") for dep in request.dependencies]
            install_cmd = f"pip install --no-cache-dir {' '.join(sanitized_deps)} && "

        container_cmd = f"/bin/sh -c '{install_cmd}python /workspace/run_target.py'"
        
        # Konfigurasi keamanan container
        container_env = {**request.mock_env_vars, "PYTHONUNBUFFERED": "1"}
        
        start_time = asyncio.get_event_loop().time()
        container = None
        try:
            container = self.client.containers.create(
                image=self.base_image,
                command=container_cmd,
                volumes={temp_dir: {"bind": "/workspace", "mode": "ro"}},
                environment=container_env,
                network_mode="bridge",  # Di lingkungan ultra-secure gunakan "none" jika tidak perlu internet
                mem_limit="512m",        # Hard memory limit
                nano_cpus=1000000000,    # Alokasi maks 1 CPU Core
                user="1000:1000",        # Jalankan sebagai non-root
                working_dir="/workspace"
            )

            container.start()
            
            # Polling status dengan timeout
            timed_out = False
            try:
                result = container.wait(timeout=request.timeout_seconds)
                exit_code = result.get("StatusCode", -1)
            except Exception:
                timed_out = True
                exit_code = -1
                container.kill()

            end_time = asyncio.get_event_loop().time()
            execution_time = (end_time - start_time) * 1000

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            if timed_out:
                stderr += f"\n[CRITICAL TIMEOUT] Eksekusi melebihi batas {request.timeout_seconds} detik."
                return ExecutionResult(
                    success=False,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code,
                    execution_time_ms=execution_time,
                    error_diagnostic="Execution Timed Out: Possible infinite loop in Agent orchestration code."
                )

            is_success = (exit_code == 0)
            diagnostic = None if is_success else self._derive_diagnostic(stderr)

            return ExecutionResult(
                success=is_success,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time_ms=execution_time,
                error_diagnostic=diagnostic
            )

        except APIError as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                execution_time_ms=0,
                error_diagnostic=f"Docker Infrastructure Error: {str(e)}"
            )
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _derive_diagnostic(self, stderr: str) -> str:
        if "AuthenticationError" in stderr or "APIKeyMissing" in stderr:
            return "Kredensial atau Token API tidak ditemukan atau formatnya salah."
        if "RateLimitError" in stderr:
            return "Eksekusi terkena batas kuota API Rate Limiter upstream."
        if "ModuleNotFoundError" in stderr:
            return "Library eksternal yang diimpor tidak terdaftar di konfigurasi dependensi."
        return "Runtime exception terjadi selama eksekusi SDK loop."

# Inisialisasi FastAPI API
from fastapi import FastAPI, HTTPException

app = FastAPI(title="DevRel Verification & Diagnostics Platform")
sandbox_manager = EphemeralSandboxManager()

@app.post("/api/v1/verify-snippet", response_model=ExecutionResult)
async def verify_snippet_endpoint(request: ExecutionRequest):
    try:
        result = await sandbox_manager.execute_code_safely(request)
        return result
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Internal Execution Failure: {str(ex)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: NexusAI Inc. (Penyedia Framework Multi-Agent & LLM Gateway)
* **Skala Sistem**:
  * 120.000 pengembang aktif bulanan (MAU).
  * 400+ file dokumentasi teknis dengan total 1.800+ *live code snippets*.
  * Rata-rata 250 GitHub Issues dan 1.200 pertanyaan teknis Discord per minggu.

* **Permasalahan Utama (Incident)**:
  NexusAI merilis SDK v3.0 yang mengalihkan struktur payload agen dari *sync execution* ke *event-driven stream*. Rilis ini menyebabkan 65% cuplikan kode di dokumentasi resmi rusak (*deprecated syntax*). Tingkat *Time-to-First-Hello-World* (TTFW) melonjak dari 6 menit menjadi 48 menit. Drop-off rate pada registrasi developer baru melonjak ke angka 58%. Tim DevRel manual (6 orang) kewalahan menangani antrean tiket yang membengkak hingga 800+ issue aktif.

* **Solusi Arsitektur yang Diterapkan**:
  1. **Deployment Autonomous Docs Verification CI/CD**:
     Membangun pipeline GitHub Actions yang memvalidasi seluruh 1.800 cuplikan kode di setiap Pull Request. Cuplikan diuji secara terisolasi menggunakan runner k8s terdistribusi.
  2. **Community Agent Triage Daemon**:
     Mengintegrasikan bot Discord/GitHub yang mengisolasi laporan bug pengembang. Jika pengembang mengirimkan error stack trace, bot merekonstruksi skrip tersebut di MicroVM, memeriksa apakah terjadi pada core engine atau user code, dan memberikan perbaikan kode (*patch diff*) secara instan.
  3. **DX Telemetry Tracking**:
     Mengintegrasikan OpenTelemetry collector pada quickstart project templates untuk mendeteksi step mana yang sering mengalami *unhandled rejection* oleh pengembang.

* **Hasil Metrik Bisnis & Rekayasa**:
  * TTFW kembali ditekan menjadi rata-rata **4,2 menit**.
  * Developer drop-off rate turun drastis ke level **11%**.
  * Waktu respons pertama (First Response Time) issue GitHub turun dari **36 jam** menjadi **8 menit**.
  * 78% cuplikan kode dokumentasi yang usang diperbaiki secara otomatis oleh PR generator dalam 48 jam pasca-rilis.

---

### 9. Trade-offs

Mengembangkan sistem internal DevRel Engineering melibatkan pertimbangan arsitektur dan trade-off kritis:

| Pendekatan / Keputusan | Keuntungan | Biaya / Risiko | Mitigasi Trade-off |
| :--- | :--- | :--- | :--- |
| **Isolasi Penuh via MicroVM (Firecracker/E2B) vs Docker Standard** | Keamanan eksekusi kode acak komunitas sangat tinggi (mencegah *container escape*). | Latensi *cold start* lebih tinggi; biaya komputasi infrastruktur meningkat 3-4x lipat. | Gunakan Docker standard untuk internal Docs CI, gunakan Firecracker/gVisor untuk mengeksekusi kode publik dari issue developer. |
| **Mocking LLM Endpoint vs Live LLM Inference pada CI/CD** | Biaya tes $0, deterministik, tidak rentan terhadap fluktuasi latensi API model provider. | Tidak dapat mendeteksi kegagalan parsing jika output LLM mengalami *semantic drift* aktual. | Skema *Hybrid CI*: 95% run menggunakan Mocking (VCR.py / wiremock), 5% run terjadwal (Nightly Run) memukul live model. |
| **Autonomous Issue Auto-Reply vs Human-Only Reply** | Skalabilitas 24/7 tak terbatas; developer mendapatkan resolusi teknis instan. | Risiko halusinasi agentic reply yang dapat merusak kredibilitas profesional DevRel. | Batasi bot hanya untuk *verifikasi eksekusi reproduksi kode*, bukan memberikan opini bebas tanpa bukti lolos sandbox test. |
| **Granular Client-Side SDK Telemetry vs Developer Privacy** | Pemahaman mendalam pada fungsi mana pengembang sering mengalami error. | Penolakan komunitas (*backlash*) terkait transmisi data pribadi atau potensi kebocoran payload/prompts. | SDK Telemetry harus bersifat *strict opt-in*, hanya mentransmisikan metadata error trace (anonim) tanpa payload teks prompt. |

---

### 10. Common Mistakes & Troubleshooting

#### Anti-Pattern 1: Menyimpan Hardcoded API Keys di Dokumentasi / Tests
* **Gejala**: API Key bocor ke repositori publik saat bot memvalidasi dokumentasi.
* **Akar Masalah**: Penulis dokumentasi mencantumkan skrip operasional lengkap tanpa placeholder dinamis.
* **Solusi**: Terapkan *pre-commit hook* dengan `trufflehog` atau `gitleaks`, dan gunakan sistem injeksi environment mock (`DUMMY_KEY_FOR_DOC_TESTS`) pada runner verification.

#### Anti-Pattern 2: Dynamic Snippet Extraction Failure akibat Non-Standard Markdown
* **Gejala**: Runner melewati blok kode karena tagging bahasa yang bervariasi (`py`, `python`, `python3`, `python console`).
* **Solusi**: Standardisasi linter markdown (misalnya menggunakan custom plugin `markdownlint`) yang mewajibkan metadata info string yang seragam pada blok kode:
  ```markdown
  ```python test="true" env="sandbox"
  from nexus_agent import Agent
  agent = Agent()
  ...
  ```
  ```

#### Anti-Pattern 3: Unbounded Resource Exhaustion di Sandbox Worker
* **Gejala**: Sandbox runner hang karena kode pengembang mengeksekusi `while True:` loop atau *fork bomb*.
* **Solusi**: Atur limitasi tegas pada level Linux kernel via cgroups:
  * Memory: `--memory="512m"`
  * CPU: `--cpus="1.0"`
  * PIDs: `--pids-limit=64`
  * Process Timeout: Kill container secara paksa menggunakan sinyal `SIGKILL` tepat pada detik ke-15.

---

### 11. Best Practices (Production Checklist)

#### Keamanan Sandbox:
- [ ] Runner tidak berjalan dengan user `root` (gunakan non-root UID:GID).
- [ ] Pembatasan akses jaringan: Gunakan network isolation jika kode tidak memerlukan akses eksternal.
- [ ] File system sementara dimount sebagai *Read-Only* kecuali direktori `/tmp` atau scratchpad kerja.
- [ ] Penggunaan *drop-capabilities* (`--cap-drop=ALL`) pada instance container.

#### Telemetri & Observability DX:
- [ ] Pengukuran P50, P90, dan P99 dari *Time to First Hello World* (TTFW) terdokumentasi di dashboard grafana.
- [ ] Segmentasi telemetri berdasarkan bahasa SDK (Python, TypeScript, Go) dan sistem operasi.
- [ ] Pelacakan otomatis error code upstream (4xx Client Errors vs 5xx Infrastructure Errors).

#### Integrasi Docs-as-Code:
- [ ] 100% sampel kode di repositori dokumentasi dieksekusi secara otomatis pada setiap PR.
- [ ] Dokumentasi yang menyertakan payload JSON divalidasi terhadap JSON Schema v7 / Pydantic definition API terbaru.
- [ ] Perbedaan versi dokumentasi (misal v1 vs v2) terikat pada snapshot SDK version yang spesifik.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun pipeline verifikasi cuplikan kode dokumentasi secara menyeluruh.

#### Struktur Direktori Target:
```
hands-on/m02/
├── docs/
│   ├── quickstart.md
│   └── agent_loop.md
├── src/
│   ├── __init__.py
│   ├── extractor.py
│   └── runner.py
├── tests/
│   └── test_docs_runner.py
├── requirements.txt
└── run_verifier.py
```

#### Langkah-langkah Praktikum:

**Langkah 1: Setup dependencies**
Buat file `hands-on/m02/requirements.txt`:
```text
docker>=7.0.0
pydantic>=2.5.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

**Langkah 2: Buat Dokumentasi Sampel**
Buat file `hands-on/m02/docs/quickstart.md`:
````markdown
# Quickstart Guide

Jalankan agen sederhana ini untuk memulai:

```python
# Sample 1: Valid Code
def init_agent():
    return {"status": "ready", "agent_id": "nexus-001"}

state = init_agent()
assert state["status"] == "ready"
print(f"Agent online: {state['agent_id']}")
```

Dan ini contoh loop yang memanggil tools:

```python
# Sample 2: Valid Logic
items = [1, 2, 3]
squared = [x ** 2 for x in items]
assert squared == [1, 4, 9]
print("Compute finished successfully.")
```
````

Buat file dokumentasi bermasalah `hands-on/m02/docs/agent_loop.md`:
````markdown
# Broken Guide

Contoh ini sengaja mengandung syntax error:

```python
# Sample 3: Broken Syntax
def broken_process(
    print("Missing closing bracket"
```
````

**Langkah 3: Implementasikan Modul Extractor**
Buat file `hands-on/m02/src/extractor.py`:
```python
import re
from pathlib import Path
from pydantic import BaseModel

class CodeSnippet(BaseModel):
    source_file: str
    index: int
    code: str
    language: str

class MarkdownExtractor:
    @staticmethod
    def extract_snippets_from_file(file_path: Path) -> list[CodeSnippet]:
        content = file_path.read_text(encoding="utf-8")
        pattern = r"```([a-zA-Z0-9_-]+)\n(.*?)\n```"
        matches = re.finditer(pattern, content, re.DOTALL)
        
        snippets = []
        for idx, match in enumerate(matches, start=1):
            lang = match.group(1).lower()
            code = match.group(2)
            if lang in ["python", "py"]:
                snippets.append(CodeSnippet(
                    source_file=str(file_path),
                    index=idx,
                    code=code,
                    language=lang
                ))
        return snippets
```

**Langkah 4: Implementasikan Runner Orchestrator**
Buat file `hands-on/m02/run_verifier.py`:
```python
import sys
from pathlib import Path
from src.extractor import MarkdownExtractor
import ast

def verify_all_documentation(docs_dir: str) -> bool:
    docs_path = Path(docs_dir)
    markdown_files = list(docs_path.glob("**/*.md"))
    
    total_snippets = 0
    passed_snippets = 0
    failures = []

    print(f"Memindai direktori: {docs_dir}")
    print(f"Ditemukan {len(markdown_files)} file markdown.\n" + "="*50)

    for md_file in markdown_files:
        snippets = MarkdownExtractor.extract_snippets_from_file(md_file)
        for snippet in snippets:
            total_snippets += 1
            try:
                # Validasi sintaks lokal via AST
                ast.parse(snippet.code)
                passed_snippets += 1
                print(f"[OK] {snippet.source_file} (Snippet #{snippet.index})")
            except SyntaxError as e:
                err_msg = f"{snippet.source_file} (Snippet #{snippet.index}): {e.msg} di baris {e.lineno}"
                failures.append(err_msg)
                print(f"[FAIL] {err_msg}")

    print("="*50)
    print(f"Hasil: {passed_snippets}/{total_snippets} lolos validasi.")
    if failures:
        print("\nDetail Kegagalan:")
        for failure in failures:
            print(f"  - {failure}")
        return False
    return True

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "docs"
    success = verify_all_documentation(target_dir)
    sys.exit(0 if success else 1)
```

**Langkah 5: Eksekusi dan Verifikasi**
Jalankan verifier pada folder dokumentasi:
```bash
python run_verifier.py docs
```
Pastikan sistem menangkap error pada `agent_loop.md` dan mengembalikan exit code non-zero (`1`). Perbaiki file `agent_loop.md` hingga seluruh validasi lolos (`0`).

---

### 13. Exercise

#### Level Easy:
Tulis skrip Python untuk memfilter kata-kata terlarang (*deprecated symbols*) pada seluruh file markdown. Jika pengembang menggunakan `v1.legacy_agent()`, skrip harus menandai baris tersebut dan memberikan saran pengganti `v2.ModernAgent()`.

#### Level Medium:
Perluas `src/extractor.py` untuk mendukung tag parsing berbasis anotasi blok kode, contohnya:
````markdown
```python sandbox="skip"
# Kode ini harus diabaikan oleh runner
```
````
Pastikan extractor hanya menyaring snippet yang memiliki status `sandbox="run"` atau tidak memiliki flag skip.

#### Level Hard:
Rancang dan implementasikan sebuah *Mock API Ingestion Webhook* menggunakan FastAPI yang menerima *GitHub Webhook payload* event `issues.opened`. Ekstrak cuplikan kode dari teks issue (`issue.body`), operasionalkan `EphemeralSandboxManager` (dari Section 7.B) untuk memverifikasi apakah snippet tersebut melempar `Exception`, dan kembalikan response JSON berupa rekomendasi perbaikan berbasis AST error parser.

---

### 14. Challenge

**Skenario**:
Perusahaan Anda meluncurkan protokol komunikasi agen terdistribusi yang bekerja secara asinkron (*Agent-to-Agent Protocol / AAP*). Protokol ini menuntut interaksi multi-agen yang melibatkan minimal 2 container yang saling berkomunikasi via TCP/gRPC port internal.

**Tantangan Arsitektur**:
Rancang arsitektur sistem pengujian dokumentasi DevRel terisolasi (*Multi-Node Ephemeral Harness*) yang:
1. Mampu menginstansiasi *Docker compose network ephemeral* secara dinamis untuk satu file markdown yang membutuhkan setup dua agen (Node Pengirim dan Node Penerima).
2. Mengekstrak 2 blok kode berbeda dari file dokumentasi yang sama (Node A dan Node B), menjalankan keduanya dalam dua container terpisah pada subnet yang sama, dan memvalidasi bahwa handshaking selesai dalam waktu kurang dari 10 detik.
3. Menyediakan jaminan pembersihan sumber daya (*garbage collection*) 100% jika terjadi fatal crash atau hanging lock pada salah satu agen, tanpa meninggalkan zombie containers pada host runner.

*Buat dokumen spesifikasi teknis dan blueprint kode Python untuk mengorkestrasi scenario multi-container sandbox ini.*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (Pilihan Ganda & Konseptual Singkat)
1. **Apa perbedaan utama antara metric TTFW (Time-to-First-Hello-World) dan First Response Time pada DevRel?**
   * *Jawaban*: TTFW mengukur waktu yang dibutuhkan pengembang untuk berhasil menjalankan instruksi kode pertama kali dari registrasi/instalasi, sedangkan First Response Time mengukur latensi waktu tim DevRel dalam merespons pertanyaan/tiket pertama kali.
2. **Mengapa Abstract Syntax Tree (AST) parsing lebih disukai daripada eksekusi Regex saja saat memvalidasi kode di dokumentasi?**
   * *Jawaban*: Regex hanya mencocokkan pola string tekstual, sedangkan AST menganalisis struktur hierarki bahasa pemrograman yang sebenarnya, sehingga dapat mendeteksi invalid syntax, struktur token, dan namespace secara definitif sebelum kode dieksekusi.
3. **Sebutkan minimal 2 pembatasan resource Linux kernel yang wajib diterapkan saat mengeksekusi kode developer dari forum komunitas!**
   * *Jawaban*: Batas memori (`mem_limit` / cgroups memory) dan batas kuota komputasi CPU (`nano_cpus` / CPU quota), serta pembatasan jumlah proses (`pids-limit`).
4. **Apa risiko arsitektur jika verifikasi dokumentasi CI/CD selalu mengeksekusi live production LLM endpoints?**
   * *Jawaban*: Biaya token LLM yang melonjak tidak terkendali (*budget leakage*), latensi pengujian yang tinggi dan non-deterministik, serta potensi kegagalan CI/CD yang disebabkan oleh outage provider eksternal.
5. **Dalam format CloudEvents, mengapa normalisasi payload webhook GitHub dan Discord diperlukan oleh tim DevRel Platform?**
   * *Jawaban*: Agar sistem downstream (analytics, data warehouse, autonomous triage) memiliki kontrak skema event yang seragam (*single contract*) tanpa harus mengadaptasi struktur payload masing-masing platform secara terpisah.

#### B. Pertanyaan Intermediate
1. **Bagaimana cara mengisolasi sampel kode dokumentasi yang membutuhkan kredensial API tanpa mengekspos API Key produksi ke runtime CI?**
   * *Jawaban*: Menggunakan *environment virtualization mocking*. Runner menginjeksi environment variable dummy, sementara network layer diarahkan ke mock server lokal (misalnya menggunakan WireMock atau HTTP mock proxy) yang mensimulasikan respons 200 OK dari upstream server.
2. **Jelaskan trade-off antara menggunakan Docker standard vs Firecracker MicroVMs untuk sistem Autonomous Issue Reproduction!**
   * *Jawaban*: Docker standard memiliki startup time yang sangat cepat (~millisecond) dan konsumsi resource rendah, namun batas keamanannya lebih rapuh terhadap eksploitasi kernel host (*container escape*). Firecracker menyediakan isolasi hypervisor tingkat perangkat keras (*hardware virtualization*) dengan keamanan setara VM penuh, namun membutuhkan konfigurasi KVM pada host dan manajemen disk storage yang lebih rumit.
3. **Mengapa metrik vanity seperti "GitHub Stars" dapat menyesatkan dalam evaluasi kesehatan ekosistem developer AI?**
   * *Jawaban*: GitHub Stars sering kali mencerminkan antusiasme pemasaran atau tren sesaat tanpa korelasi langsung terhadap adopsi teknis. Developer aktif yang terdistribusi pada metrik retensi bulanan, adopsi SDK riil, integrasi produksi, dan keberhasilan panggilan API jauh lebih mencerminkan *product-market fit* developer.
4. **Bagaimana arsitektur Docs-as-Code menangani cuplikan kode yang bersifat non-deterministik (misalnya output text sampling LLM)?**
   * *Jawaban*: Dengan menerapkan evaluasi kontraktual (*assertion testing* berbasis format/skema). Tes tidak memeriksa kecocokan string teks output secara absolut, melainkan memvalidasi bahwa response output memenuhi JSON Schema yang ditentukan, memiliki tipe data yang benar, atau lolos uji heuristik (misalnya `len(response) > 0`).
5. **Apa fungsi cgroups `pids_limit` saat mengeksekusi kode agen dari komunitas yang tidak tepercaya?**
   * *Jawaban*: Mencegah serangan *fork bomb* atau loop pembuatan thread tak terbatas yang dapat menghabiskan seluruh alokasi Process Table ID (PID) pada host operating system, yang dapat menyebabkan seluruh server mengalami kernel panic/crash.

#### C. Skenario Kasus Produksi

**Skenario 1: The Token Depletion Storm**
Sebuah tim DevRel mengintegrasikan bot Discord yang otomatis menjalankan *tool calling loop* setiap kali ada user yang menanyakan *"mengapa kode ini error?"*. Dalam 3 jam, kuota $5,000 API tim habis karena ada anggota komunitas yang secara sengaja mengirimkan prompt recursif tak hingga (*infinite multi-step tool call*).
* *Tindakan Remediasi*:
  1. Hentikan eksekusi bot secara instan (*kill switch*).
  2. Implementasikan *token ceiling guardrail* dan *maximum recursion limit* yang ketat (misalnya hard limit maks 3 turn) pada runtime bot triage.
  3. Tempatkan bot di balik sistem *rate-limiting* per-user (maksimal 2 request per 10 menit per Discord ID).
  4. Ganti model penilai triage awal dengan model lokal berbiaya rendah (misalnya model SLM open-source ter-host lokal) sebelum meneruskannya ke reasoning model berbayar.

**Skenario 2: The Silent Docs Poisoning**
Perubahan minor pada core SDK Python mengubah argumen fungsi `create_agent(name: str, memory_backend: str)` menjadi `create_agent(name: str, memory: MemoryConfig)`. Seluruh tes unit di repositori core lulus karena tes internal diperbarui, namun 40 file markdown di repositori dokumentasi publik masih menggunakan signature lama.
* *Tindakan Remediasi*:
  1. Integrasikan repositori dokumentasi ke dalam matrix CI core repository: Setiap PR pada core SDK yang mengubah signature fungsi public wajib memicu downstream verification di repositori docs.
  2. Terapkan AST Type Checker (seperti `mypy` atau `pyright`) pada runner ekstraksi markdown untuk mendeteksi *type mismatch* dan *signature mismatch* secara statis.
  3. Konfigurasikan bot pengoreksi otomatis (*auto-patcher bot*) yang mengajukan PR koreksi skema ke repositori dokumentasi secara atomik bersamaan dengan rilis SDK baru.

**Skenario 3: The Untracked SDK Dropout**
Data API Gateway menunjukkan bahwa 70% pengembang yang mengunduh SDK Python v2.4 tidak pernah melakukan pemanggilan API kedua setelah 24 jam pertama. Log di server menunjukkan response `400 Bad Request` yang sangat tinggi pada endpoint `/v1/agents/run`.
* *Tindakan Remediasi*:
  1. Telusuri korelasi *OpenTelemetry Traces* dari developer API key yang gagal: Identifikasi field payload spesifik yang memicu response `400`.
  2. Ditemukan bahwa quickstart tutorial di dokumentasi merekomendasikan penggunaan parameter yang sudah di-*deprecated* oleh Gateway API.
  3. DevRel Platform harus mereplikasi issue tersebut di sandbox, memverifikasi kegagalan, menerbitkan *hotfix documentation*, dan menyiarkan peringatan integrasi (*integration notification*) ke developer cohort yang terdampak via email teknis atau status bulletin.

---

### 16. Summary

1. **DevRel sebagai Disiplin Rekayasa**: Pada domain AI, Data, dan Autonomous Agents, Developer Relations bukan sekadar aktivitas *outreach*, melainkan fungsi *engineering* strategis yang bertugas memperkecil friksi adopsi teknis melalui perangkat lunak, otomatisasi, dan observabilitas.
2. **Docs-as-Code adalah Production Software**: Dokumentasi teknis dan cuplikan kodenya harus diperlakukan setara dengan kode produksi. Seluruh contoh kode wajib diverifikasi secara berkala melalui pipeline CI/CD berbasis AST parsing dan execution sandbox.
3. **Keamanan Eksekusi adalah Prioritas**: Memvalidasi kode eksternal dari developer community menuntut arsitektur isolasi yang ketat menggunakan Linux cgroups, non-root user, limits CPU/Memory, network sandboxing, dan proteksi timeout.
4. **Metrik DX Berbasis Bukti**: Keberhasilan ekosistem diukur melalui metrik deterministik seperti P95 *Time-to-First-Hello-World* (TTFW), tingkat retensi SDK cohort bulanan, dan *First Response Time* berbasis autonomous diagnostic, bukan vanity metrics.