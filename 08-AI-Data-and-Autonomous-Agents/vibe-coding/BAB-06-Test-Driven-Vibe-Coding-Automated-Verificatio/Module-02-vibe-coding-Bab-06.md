# BAB 06: Test-Driven Vibe-Coding & Automated Verification
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur Self-Healing Code Synthesis** menggunakan siklus *Actor-Critic* berbasis umpan balik uji otomatis (*automated test feedback loop*).
2. **Mengintegrasikan Property-Based Testing (PBT)** ke dalam *vibe-coding agent* untuk menemukan *edge cases* yang gagal diantisipasi oleh LLM (*Large Language Model*).
3. **Membangun Runtime Verification Sandbox** terisolasi menggunakan kontainerisasi tingkat kernel (gVisor/Docker SDK) guna mengeksekusi kode hasil sintesis secara deterministik dan aman.
4. **Menerapkan Mutation Testing Terautomasi** sebagai metrik kualitas objektif untuk memvalidasi bahwa *test suite* yang dibuat agen AI tidak mengalami *tautological assertion* (palsu/lemah).
5. **Mengelola Trade-off Arsitektural** antara konsumsi token, latensi eksekusi CI/CD, dan kedalaman verifikasi formal pada skala enterprise.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, pembaca wajib menguasai:
* Pemrograman Python tingkat lanjut (AsyncIO, AST module, Typing, Context Managers).
* Konsep inti Test-Driven Development (TDD: Red-Green-Refactor) dan Property-Based Testing (Hypothesis/fast-check).
* Docker Engine API / container runtime internals (cgroups, namespaces, seccomp).
* Mekanika LLM API (Structured Output, Function Calling, System Prompting, Context Caching).

---

### 3. Concept & Internal Architecture

*Test-Driven Vibe-Coding* (TDVC) tingkat produksi mentransformasi proses rekayasa perangkat lunak berbasis AI dari paradigma **Probabilistic Code Generation** (berharap LLM menghasilkan kode yang benar pada *single shot*) menjadi **Deterministic Convergence Verification** (memaksa ruang probabilitas LLM mengerucut pada implementasi yang secara matematis dan fungsional lolos serangkaian gerbang verifikasi).

#### Arsitektur Inti: Dual-Agent Verification Engine

Arsitektur produksi TDVC memisahkan tanggung jawab menjadi dua agen otonom yang bekerja secara adversarial:

```
+---------------------------------------------------------------------------------------+
|                             TDVC Orchestration Engine                                 |
|                                                                                       |
|  1. Invariant Specification (Human Input / RFC / OpenAPI)                             |
|                           |                                                           |
|                           v                                                           |
|       +---------------------------------------+                                       |
|       |       Adversarial Tester Agent        |                                       |
|       |  (Synthesizes Unit, Property & Fuzz)  |                                       |
|       +---------------------------------------+                                       |
|                           |                                                           |
|                           | Produces: Invariant Test Suite (.py)                      |
|                           v                                                           |
|               +=======================+                                               |
|               |  Ephemeral MicroVM /  | <================================+            |
|               |  Docker Sandbox       |                                  |            |
|               +=======================+                                  |            |
|                           ^                                              |            |
|                           | Executes inside Sandbox                      |            |
|                           |                                              |            |
|       +---------------------------------------+                          |            |
|       |         Coder / Synthesis Agent       |                          |            |
|       | (Writes & Iteratively Patches Code)   |                          |            |
|       +---------------------------------------+                          |            |
|                           ^                                              |            |
|                           | Structured Telemetry (STDOUT, STDERR, AST)   |            |
|                           +----------------------------------------------+            |
|                                                                                       |
|  Convergence Gate:                                                                    |
|  - All Unit Tests Pass (Green)                                                        |
|  - Property Tests Pass (>1000 examples)                                               |
|  - Mutation Score >= 85%                                                              |
|  - AST Complexity & Security Lint Pass                                                |
+---------------------------------------------------------------------------------------+
```

#### Mekanisme Sub-Sistem:
1. **Invariant Parser & Test Synthesizer:** Agen spesialis yang memecah spesifikasi sistem menjadi assertions formal, mencakup pre-conditions, post-conditions, dan state invariants.
2. **Actor-Critic Convergence Loop:** Coder Agent bertindak sebagai *Actor* yang menghasilkan state solusi baru. Sandbox runtime bertindak sebagai *Environment*. Engine mengevaluasi hasil eksekusi dan mengekstrak *structured diagnostic payload* (Traceback, Exit Code, AST Diff) sebagai feedback bagi *Actor*.
3. **Mutation Gate:** Mencegah Coder Agent melakukan "kecurangan" (seperti mengosongkan fungsi uji atau me-*mock* fungsionalitas inti tanpa implementasi nyata). Sistem menginjeksikan mutan ke dalam kode yang lolos uji; jika *test suite* gagal mendeteksi mutan, status ditolak (*kill failure*).

---

### 4. Why & What

| Dimensi | Vanilla Vibe-Coding | Production Test-Driven Vibe-Coding |
| :--- | :--- | :--- |
| **Paradigma** | *Optimistic synthesis* (Asumsi output benar sampai ditemukan bug manual). | *Pessimistic verification* (Kode dianggap cacat sampai terbukti lolos validasi formal). |
| **Loop Kendali** | Human-in-the-loop manual testing (Copy-paste kode ke IDE, run, inspect). | Closed-loop automated feedback (Orchestrator menguji, mendiagnosis, dan me-remediasi sendiri). |
| **Kualitas Pengujian**| Happy path unit tests generated by the same prompt context. | Adversarial Property-Based & Mutation Testing terisolasi. |
| **Keamanan Eksekusi**| Eksekusi langsung di mesin lokal pengembang. | Ephemeral containerized sandbox dengan network isolation & resource limits. |
| **Toleransi Regresi**| Sangat tinggi (LLM kerap merusak fungsi lama saat memperbaiki fungsi baru). | Nol (Full-suite continuous regression gate per iterasi). |

---

### 5. How: Alur Kerja Terperinci (Execution Lifecycle)

Siklus eksekusi TDVC diatur dalam 6 tahapan state machine:

```
[Spec Ingestion] 
       │
       ▼
[Stage 1: Generate Test Contract (PBT + Unit)]
       │
       ▼
[Stage 2: Execute Sandbox Test on Empty Impl (Assert FAIL/Red)]
       │
       ├─► (Jika Lolos: Abort! Indikasi tautology / false positive test)
       │
       ▼
[Stage 3: Coder Agent Synthesizes Implementation]
       │
       ▼
[Stage 4: Run Test Suite in Isolated Runtime]
       │
       ├─► [FAIL] ──► Extract Stack Trace & AST ──► Feedback to Coder Agent ──┐
       │     ▲                                                                │
       │     └──────────────────────── (Max Retries: N) ──────────────────────┘
       ▼
     [PASS]
       │
       ▼
[Stage 5: Run Mutation Testing & Security Auditing (Bandit/AST)]
       │
       ├─► [Score < Threshold] ──► Inject Mutation Misses to Critic ──┐
       │     ▲                                                       │
       │     └───────────────────────────────────────────────────────┘
       ▼
[Stage 6: Artifact Emit & Version Control Push]
```

---

### 6. Analogi & Diagram ASCII

#### Analogi Rekayasa: Pengujian Terowongan Angin Dirgantara
Bayangkan Anda mendesain jet tempur supersonik.
* **Vanilla Vibe-Coding:** Anda meminta AI membuat model badan pesawat 3D berdasarkan gambar sketsa, lalu Anda langsung memproduksinya dan menugaskan pilot uji untuk terbang. Jika sayap patah di udara, pilot mati.
* **Test-Driven Vibe-Coding:** Sebelum membuat badan pesawat, Anda memprogram instrumen sensor terowongan angin (*wind tunnel sensors*) dengan batas toleransi aerodinamika ekstrem (kecepatan Mach 3, beban 9G). Anda memasukkan model AI ke dalam terowongan angin virtual. Setiap kali struktur sayap bergetar melebihi batas atau patah, sensor mengirim data telemetri tegangan material kembali ke sistem manufaktur untuk merevisi ketebalan serat karbon secara iteratif hingga tahan di segala simulasi cuaca. Tidak ada pesawat yang keluar dari fasilitas sebelum lulus uji terowongan angin tanpa cela.

#### Diagram Interaksi Detail:
```
Coder Agent               Sandbox Runtime                 Mutation Engine
     │                           │                               │
     │ 1. Synthesize Impl        │                               │
     ├──────────────────────────►│                               │
     │                           │ 2. Run Invariant Tests        │
     │                           ├──────────────┐                │
     │                           │              │                │
     │                           │<─────────────┘                │
     │ 3. Exit 1: ZeroDivision   │                               │
     │<──────────────────────────┤                               │
     │                           │                               │
     │ 4. Patch Impl (Guard Zero)│                               │
     ├──────────────────────────►│                               │
     │                           │ 5. Run Invariant Tests        │
     │                           │    (All Tests Pass: Exit 0)   │
     │                           │                               │
     │                           ├──────────────────────────────►│
     │                           │    Trigger Mutation Run       │ 6. Inject AST Mutants
     │                           │                               │    (e.g., '>' to '>=')
     │                           │                               ├──────────────┐
     │                           │                               │              │
     │                           │<──────────────────────────────┤<─────────────┘
     │                           │ 7. Return Mutation Score: 60% │
     │ 8. Mutation Alert:        │    (KILLED: 3, SURVIVED: 2)   │
     │    Survived off-by-one    │                               │
     │<──────────────────────────┤                               │
     │                           │                               │
     │ 9. Synthesize Strict Edge │                               │
     ├──────────────────────────►│                               │
     │                           │ 10. Re-verify & Mutate        │
     │                           │     Score: 100%               │
     │                           ├──────────────────────────────►│
     │ 11. Artifact Certified    │                               │
     │<──────────────────────────┤                               │
```

---

### 7. Implementasi Kode Standar Industri

Berikut adalah sistem orchestrator TDVC modular siap produksi yang memanfaatkan Docker SDK untuk isolasi proses, framework *Hypothesis* untuk Property-Based Testing, dan siklus self-healing otomatis berbasis telemetri diagnostik.

#### Struktur File:
```
tdvc-engine/
├── core/
│   ├── __init__.py
│   ├── agent.py         # Interaksi LLM dengan Structured Outputs
│   ├── orchestrator.py  # State Machine & Actor-Critic loop
│   └── sandbox.py       # Docker Isolation Runtime
└── tests/
    └── sample_spec.py
```

#### 1. Sandbox Runtime Manager (`core/sandbox.py`)
```python
import docker
import tarfile
import io
import os
from typing import Dict, Any, Tuple

class EphemeralSandbox:
    def __init__(self, image: str = "python:3.11-slim"):
        self.client = docker.from_env()
        self.image = image
        self.container = None

    def __enter__(self):
        # Jalankan kontainer dengan batasan resource ketat dan tanpa akses jaringan eksternal
        self.container = self.client.containers.run(
            image=self.image,
            command="tail -f /dev/null",
            detach=True,
            network_mode="none",  # Isolasi jaringan penuh demi keamanan
            mem_limit="512m",     # Maksimum 512 MB RAM
            nano_cpus=1000000000, # Maksimum 1 vCPU
            cap_drop=["ALL"],     # Drop all Linux capabilities
            security_opt=["no-new-privileges:true"],
            read_only=False
        )
        # Install dependencies minimal di dalam container
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.container:
            try:
                self.container.remove(force=True)
            except Exception:
                pass

    def inject_files(self, files: Dict[str, str]) -> None:
        """Menyuntikkan payload file kode dan tes ke dalam sandbox."""
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            for filename, content in files.items():
                data = content.encode('utf-8')
                tar_info = tarfile.TarInfo(name=filename)
                tar_info.size = len(data)
                tar.addfile(tar_info, io.BytesIO(data))
        tar_stream.seek(0)
        self.container.put_archive(path="/tmp", data=tar_stream)

    def execute_command(self, cmd: str) -> Tuple[int, str, str]:
        """Mengeksekusi perintah di dalam sandbox dan mengembalikan exit code beserta output."""
        exec_result = self.container.exec_run(
            cmd=f"bash -c '{cmd}'",
            workdir="/tmp",
            demux=True
        )
        exit_code = exec_result.exit_code
        stdout_raw, stderr_raw = exec_result.output
        stdout = stdout_raw.decode('utf-8', errors='replace') if stdout_raw else ""
        stderr = stderr_raw.decode('utf-8', errors='replace') if stderr_raw else ""
        return exit_code, stdout, stderr
```

#### 2. Agent Interfacing Protocol (`core/agent.py`)
```python
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import openai

class CodePatchResponse(BaseModel):
    rationale: str = Field(description="Analisis kegagalan dan akar masalah")
    implementation_code: str = Field(description="Kode Python lengkap yang siap dieksekusi")

class LLMInterface:
    def __init__(self, model: str = "gpt-4o"):
        self.client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = model

    def request_implementation(self, specification: str, test_code: str, previous_error: Optional[str] = None) -> CodePatchResponse:
        system_prompt = (
            "Anda adalah Senior Staff Software Engineer spesialis High-Reliability Systems.\n"
            "Tugas Anda: Menghasilkan implementasi kode Python produksi yang lolos seluruh uji deterministik dan Property-Based Testing.\n"
            "ATURAN MUTLAK:\n"
            "1. Hasilkan KODE LENGKAP tanpa elipsis (...) atau placeholder.\n"
            "2. Tangani seluruh edge-case batas numerik, string sanitization, dan null safety.\n"
            "3. Format respons WAJIB mengikuti skema JSON yang ditentukan."
        )

        user_content = f"### SPESIFIKASI PERSYARATAN:\n{specification}\n\n### SUITE PENGUJIAN INVARIAN:\n{test_code}\n"
        if previous_error:
            user_content += f"\n### TELEMETRI KEGAGALAN DARI ITERASI SEBELUMNYA:\n{previous_error}\nPerbaiki kode di atas agar kegagalan ini teratasi secara tuntas."

        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format=CodePatchResponse,
            temperature=0.1 # Suhu rendah untuk memaksimalkan kepatuhan logis dan determinisme
        )
        return completion.choices[0].message.parsed
```

#### 3. Core TDVC Orchestrator Loop (`core/orchestrator.py`)
```python
import sys
import logging
from core.sandbox import EphemeralSandbox
from core.agent import LLMInterface

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class TDVCOrchestrator:
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.llm = LLMInterface()

    def run_synthesis_loop(self, specification: str, test_suite_code: str) -> str:
        logging.info("Memulai Test-Driven Vibe-Coding convergence engine...")
        
        current_error: str | None = None
        last_working_code: str | None = None

        with EphemeralSandbox() as sandbox:
            # Install pytest dan hypothesis di sandbox
            logging.info("Menyiapkan sandbox dependencies...")
            _, _, err = sandbox.execute_command("pip install --no-cache-dir pytest hypothesis")
            
            for iteration in range(1, self.max_iterations + 1):
                logging.info(f"--- Iterasi Sintesis #{iteration} ---")
                
                # 1. Minta implementasi baru/patch dari LLM
                response = self.llm.request_implementation(specification, test_suite_code, current_error)
                logging.info(f"Analisis Agen: {response.rationale}")
                
                # 2. Inject ke container
                sandbox.inject_files({
                    "solution.py": response.implementation_code,
                    "test_solution.py": test_suite_code
                })
                
                # 3. Eksekusi pengujian di container
                exit_code, stdout, stderr = sandbox.execute_command("pytest test_solution.py -v")
                
                if exit_code == 0:
                    logging.info(f"VERIFIKASI BERHASIL pada iterasi #{iteration}. Seluruh invarian terpenuhi.")
                    last_working_code = response.implementation_code
                    return last_working_code
                else:
                    logging.warning(f"Uji coba gagal (Exit Code: {exit_code}). Menyiapkan payload diagnostik...")
                    current_error = f"PYTEST STDOUT:\n{stdout}\nPYTEST STDERR:\n{stderr}"
                    logging.debug(current_error)

        raise RuntimeError(f"Gagal melakukan konvergensi kode setelah {self.max_iterations} iterasi. Skenario ditolak.")

if __name__ == "__main__":
    # Demo Eksekusi: Spesifikasi Token Bucket Rate Limiter
    spec = """
    Implementasikan class `TokenBucketRateLimiter` di modul solution.py.
    Konstruktor: `__init__(self, capacity: int, refill_rate_per_sec: float)`
    Metode: `allow_request(self, tokens: int = 1, current_timestamp: float) -> bool`
    Aturan:
    - Tidak boleh menerima capacity <= 0 atau refill_rate <= 0 (raise ValueError).
    - Konsumsi token harus thread-safe atau state-consistent.
    - Timestamp diasumsikan monotonik naik; jika timestamp menurun, reject request (raise ValueError).
    - State token tidak boleh pernah melebihi capacity.
    """

    # Invariant Tests menggunakan Hypothesis untuk Property-Based Testing
    tests = """
import pytest
from hypothesis import given, strategies as st
from solution import TokenBucketRateLimiter

def test_initialization_validation():
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(capacity=0, refill_rate_per_sec=1.0)
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(capacity=10, refill_rate_per_sec=-0.5)

@given(
    capacity=st.integers(min_value=1, max_value=1000),
    refill_rate=st.floats(min_value=0.1, max_value=100.0),
    tokens_to_consume=st.integers(min_value=1, max_value=2000)
)
def test_capacity_boundaries(capacity, refill_rate, tokens_to_consume):
    limiter = TokenBucketRateLimiter(capacity=capacity, refill_rate_per_sec=refill_rate)
    
    # Konsumsi awal tidak boleh melebihi kapasitas
    allowed = limiter.allow_request(tokens=tokens_to_consume, current_timestamp=0.0)
    if tokens_to_consume <= capacity:
        assert allowed is True
    else:
        assert allowed is False

def test_time_regression_rejection():
    limiter = TokenBucketRateLimiter(capacity=10, refill_rate_per_sec=1.0)
    assert limiter.allow_request(tokens=1, current_timestamp=10.0) is True
    with pytest.raises(ValueError):
        limiter.allow_request(tokens=1, current_timestamp=9.0)
"""

    orchestrator = TDVCOrchestrator(max_iterations=4)
    try:
        final_code = orchestrator.run_synthesis_loop(spec, tests)
        print("\n=== KODE TERVERIFIKASI FINAL ===")
        print(final_code)
    except Exception as e:
        print(f"Orchestration Error: {e}", file=sys.stderr)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Modernisasi Core Settlement Engine pada Platform FinTech Tier-1
* **Latar Belakang:** Perusahaan pemrosesan pembayaran menangani 14.000 transaksi/detik. Sistem warisan (*legacy*) berbasis SQL Stored Procedure setebal 45.000 baris yang rapuh harus dimigrasikan ke microservices Python/FastAPI murni tanpa *downtime* dan tanpa toleransi deviasi pembulatan mata uang (*zero rounding variance*).
* **Solusi TDVC:**
  1. **Shadow Traffic Harness:** Rekaman 2.000.000 payload transaksi historis riil dijadikan basis data *differential oracle*.
  2. **Adversarial PBT Loop:** Tim arsitek menulis 84 properti invarian finansial (misal: "Jumlah debit wajib presisi hingga 8 digit desimal setara dengan total kredit + fee jaringan").
  3. Agen TDVC mengeksekusi generasi kode microservice menggunakan model terisolasi di Kubernetes worker nodes.
  4. Ketika ada transaksi dengan *floating-point arithmetic precision issue*, orchestrator mendeteksi `Decimal` precision leak via assertion failure dan menyuntikkan trace kembali ke LLM.
* **Hasil:**
  * Waktu migrasi terpangkas dari estimasi manual 9 bulan menjadi 14 hari kerja tim engineering.
  * Mutasi testing mencapai skor 94.2%.
  * Zero regression defects ditemukan saat *canary deployment* 100% dialihkan ke sistem baru.

---

### 9. Trade-offs Architecture Matrix

| Parameter Arsitektur | Low-Latency / Shallow Verification | High-Assurance TDVC (Produksi Rekomendasi) | Formal Mathematical Verification |
| :--- | :--- | :--- | :--- |
| **Konsumsi Token LLM**| Rendah (1.000 – 3.000 token per task) | Sedang - Tinggi (15.000 – 60.000 token per task) | Ekstrem (>100.000 token) |
| **Waktu Siklus CI/CD** | 10 – 30 detik | 2 – 6 menit (Running PBT & Mutation) | 30 – 120 menit (Z3 Solver / TLA+) |
| **Deteksi Edge Case** | Rendah (Hanya happy path & explicit mocks) | Sangat Tinggi (Property exploration membongkar 99% logic bugs) | Absolut (100% mathematically proven) |
| **Biaya Komputasi** | Rendah (Standard Docker run) | Sedang (Dedicated container runtimes / cgroups) | Sangat Tinggi (High memory solvers) |
| **Kebutuhan SDM** | Reviewer manusia harus membaca tiap baris kode. | Reviewer fokus mengaudit invarian/kontrak tes saja. | Membutuhkan insinyur metode formal terspesialisasi. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. The Tautological Assertion Trap (Tes Bohong)
* **Gejala:** Coder Agent memodifikasi file tes atau menghasilkan assertions yang selalu bernilai `True` (misal: `assert response is not None` alih-alih memvalidasi isi internal state).
* **Solusi/Pencegahan:** Kunci file pengujian dengan sistem berkas read-only di level container OS (`chmod 444 test_*.py`). Pastikan agen kode *hanya* memiliki hak tulis ke file implementasi target.

#### 2. Hallucination Infinite Loop (Oscillation Failures)
* **Gejala:** Iterasi 1 gagal di Error A, agen memperbaiki Error A tapi memunculkan Error B. Pada Iterasi 3, agen memperbaiki Error B dan kembali memunculkan Error A.
* **Solusi/Pencegahan:** Pertahankan histori diff dan log error dari seluruh iterasi sebelumnya di prompt context, gunakan *context window pruning* yang menyertakan "Negative Examples: Jangan kembali ke implementasi X karena memicu Error A".

#### 3. Sandbox Escape via Python Builtins
* **Gejala:** Kode yang dihasilkan LLM mengeksekusi `os.system("rm -rf /")` atau mencoba port scanning dari dalam sandbox.
* **Solusi/Pencegahan:** Selalu gunakan Docker network isolation (`network_mode="none"`), *drop capabilities* kernel Linux (`cap_drop=["ALL"]`), dan jangan pernah mem-mount socket Docker host (`/var/run/docker.sock`) ke dalam container worker.

---

### 11. Best Practices (Production Checklist)

- [ ] **Separation of Concerns:** Prompt tester adversarial dipisahkan secara runtime dari prompt coder synthesizer. Keduanya tidak boleh berbagi konteks percakapan langsung selain melalui file kontrak interface.
- [ ] **Property-Based Testing Prioritized:** Minimal 50% dari pengujian wajib menggunakan strategi generasi data acak terikat (*Hypothesis/QuickCheck*), bukan sekadar nilai statis *hardcoded*.
- [ ] **Strict Isolation Enforcement:** Menjalankan eksekusi kode sintesis pada ephemeral microVM (seperti Firecracker) atau gVisor container runtime (`runsc`) untuk memitigasi risiko keamanan zero-day exploit.
- [ ] **Mutation Testing Threshold:** Menolak integrasi kode secara otomatis (PR rejected) jika skor mutasi di bawah 85%.
- [ ] **Telemetry Serialization:** Seluruh kegagalan eksekusi wajib diurai menjadi format terstruktur (JSON: Stack Trace, Line Number, Locals Context, AST Node) sebelum diumpankan kembali ke prompt kritik.

---

### 12. Hands-on Practice

Buatlah direktori praktikum berikut di lingkungan kerja Anda: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/engine
cd hands-on/m02
```

#### Langkah 1: Persiapan Environment
Pasang virtual environment lokal dan dependensi:
```bash
python3 -m venv venv
source venv/bin/activate
pip install docker openai pydantic pytest hypothesis mutmut
```

#### Langkah 2: Buat Pipeline Verifikasi Mandiri
Simpan file script `engine/verify_pipeline.py` yang mengintegrasikan mutmut untuk melakukan verifikasi kekebalan tes secara otomatis:

```python
# hands-on/m02/engine/verify_pipeline.py
import subprocess
import sys

def run_mutation_check():
    print("[1/2] Menjalankan Test Suite Baseline...")
    res = subprocess.run(["pytest", "test_target.py"], capture_output=True, text=True)
    if res.returncode != 0:
        print("Test suite baseline gagal! Perbaiki kode implementasi terlebih dahulu.")
        print(res.stdout)
        sys.exit(1)
        
    print("[2/2] Menjalankan Mutation Engine (mutmut)...")
    mut_res = subprocess.run(["mutmut", "run", "--paths-to-mutate=target.py"], capture_output=True, text=True)
    print(mut_res.stdout)
    
    # Cek hasil mutasi
    results = subprocess.run(["mutmut", "results"], capture_output=True, text=True)
    print("Hasil Mutasi:\n", results.stdout)

if __name__ == "__main__":
    run_mutation_check()
```

#### Langkah 3: Eksekusi Praktikum
Tuliskan kontrak pengujian ketat di `test_target.py`, biarkan Coder Agent mengisi `target.py`, dan jalankan `verify_pipeline.py` untuk mengukur resistensi logika kode secara langsung.

---

### 13. Exercise

#### Tingkat: Easy
* **Tugas:** Buat skrip Python sederhana yang menggunakan modul `ast` bawaan untuk memvalidasi bahwa kode sintesis LLM tidak memanggil fungsi berbahaya (`eval`, `exec`, `__import__`).
* **Kriteria Validasi:** Skrip mengembalikan error non-zero jika ditemukan AST node `ast.Call` dengan nama fungsi terlarang tersebut.

#### Tingkat: Medium
* **Tugas:** Modifikasi `EphemeralSandbox` pada materi bagian 7 agar menangani timeout eksekusi jika LLM menghasilkan algoritma dengan *infinite loop* (misal: `while True:` tanpa exit condition).
* **Kriteria Validasi:** Container otomatis menghentikan proses eksekusi tepat pada ambang batas waktu 5 detik dan mengirimkan payload diagnostik `"TIMEOUT_ERROR: Execution exceeded SLA limit"` ke LLM.

#### Tingkat: Hard
* **Tugas:** Bangun orchestrator yang mendukung *Multi-Language Dual Sandbox* (Python dan Node.js/TypeScript). Sistem menerima interface TypeScript, mentranslasikannya ke Python, menghasilkan implementasi di kedua bahasa secara independen, lalu memvalidasi keduanya menggunakan *cross-language differential fuzzing* via stdin/stdout pipe.
* **Kriteria Validasi:** Kedua implementasi (Python dan TypeScript) menghasilkan respons byte-for-byte identik atas 5.000 input acak ekstrem.

---

### 14. Challenge

**Studi Kasus Ekstrem: Autonomous Raft Consensus State-Machine Builder**

* **Deskripsi Masalah:** Anda ditugaskan membangun sistem TDVC yang harus menghasilkan implementasi algoritma konsensus *Raft Node* (Role: Leader, Follower, Candidate) yang mampu menangani network partition, split-brain, dan log replication failure.
* **Kondisi Tanpa Bantuan Manusia:**
  1. Spesifikasi didefinisikan murni menggunakan invarian safety formal Raft (misal: "Hanya satu leader valid per Term", "Leader tidak pernah menimpa log miliknya sendiri").
  2. Sandbox harus menyimulasikan network layer virtual yang menginjeksi paket *drop*, *delay*, dan *reordering* (Chaos Network Simulation).
  3. Coder Agent dilarang menggunakan pustaka eksternal pihak ketiga (pure standard library).
* **Tantangan:** Rancang arsitektur loop TDVC yang mampu menuntun LLM mengonvergensikan kode state-machine Raft dari nol hingga lolos uji Jepsen-style chaos testing tanpa campur tangan koreksi manusia secara manual.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pemahaman Konseptual (Basic)
1. **Mengapa *single-shot code generation* tanpa umpan balik tes dianggap anti-pattern pada lingkungan produksi perbankan/finansial?**
2. **Apa peran utama dari *Property-Based Testing* (seperti Hypothesis) dibandingkan pengujian unit konvensional dalam paradigma TDVC?**
3. **Mengapa Coder Agent dilarang keras memiliki izin tulis (*write permission*) terhadap berkas pengujian (*test files*)?**
4. **Apa fungsi isolasi `network_mode="none"` pada sandbox container saat mengeksekusi kode hasil sintesis AI?**
5. **Jelaskan apa yang dimaksud dengan *Mutation Score* dan bagaimana metrik ini mengukur kualitas pengujian!**

#### Bagian B: Pemahaman Penerapan (Intermediate)
6. **Bagaimana cara mencegah Coder Agent mengalami *infinite oscillation* (memperbaiki bug A namun memunculkan bug B secara bergantian terus-menerus)?**
7. **Jika eksekusi tes di sandbox mengembalikan Exit Code 137, apa penyebab struktural pada level infrastruktur container dan bagaimana orchestrator harus meresponsnya?**
8. **Mengapa *temperature* LLM disetel sangat rendah (mendekati 0.0 - 0.1) dalam proses penulisan kode perbaikan pada siklus self-healing?**
9. **Bagaimana Anda mendeteksi bahwa sebuah implementasi kode melakukan manipulasi tautologi terhadap mock object daripada mengimplementasikan logika nyata?**
10. **Jelaskan perbedaan mendasar antara Actor-Critic Architecture pada Reinforcement Learning murni dengan penerapannya pada TDVC berbasis LLM!**

#### Bagian C: Analisis Skenario Kasus Produksi
11. **Skenario 1:** Sebuah tim menggunakan TDVC untuk membangun microservice otentikasi JWT. Agen AI menghasilkan implementasi yang lolos 100% dari 20 unit tests yang dibuat. Namun saat audit keamanan penetration test dilakukan, ditemukan kerentanan *Algorithm Confusion Attack* (token dengan algoritma `'none'` tetap divalidasi). Analisis di subsistem mana kegagalan TDVC ini bersumber dan rancang invarian uji yang seharusnya mencegah hal tersebut!
12. **Skenario 2:** Pipeline TDVC enterprise Anda mengalami pembengkakan tagihan token LLM hingga $8,000 dalam sepekan akibat Coder Agent kerap terjebak pada iterasi maksimal (5 retries) pada 40% task perbaikan kecil. Rancang strategi optimasi token tanpa menurunkan standar keamanan uji!
13. **Skenario 3:** Sandbox container Docker SDK Anda mulai mengalami perlambatan drastis (latensi eksekusi naik dari 1 detik menjadi 45 detik per test suite) setelah menjalankan 200 iterasi sintesis secara beruntun di satu host mesin CI runner. Identifikasi akar masalah resource OS (*operating system bottleneck*) dan berikan solusi arsitekturalnya!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian A
1. *Single-shot generation bersifat probabilistik nondeterministik; tanpa verifikasi formal, kode berisiko tinggi mengandung silent hallucination, precision leaks, dan celah keamanan fatal.*
2. *PBT menghasilkan ratusan hingga ribuan kombinasi input acak ekstrem secara otomatis untuk membuktikan invariant logika sistem, bukan sekadar memvalidasi contoh statis yang ditebak manusia/AI.*
3. *Untuk menghindari Tautological Tampering di mana agen AI memodifikasi atau menghapus assertion tes yang gagal agar status eksekusi berubah menjadi hijau (lolos).*
4. *Mencegah kode AI yang berpotensi berbahaya (eksploitasi/malware) melakukan Remote Code Execution (RCE), data exfiltration, atau penyerangan lateral ke jaringan internal host.*
5. *Persentase mutan sintaksis (kode yang dirusak secara sengaja) yang berhasil dideteksi dan digagalkan oleh test suite. Menunjukkan ketajaman dan kekebalan assertion pengujian.*

#### Bagian B
6. *Dengan mempertahankan histori diff perubahan dan kegagalan pada iterasi-iterasi sebelumnya sebagai "Negative Constraints" dalam context window prompt agar ruang probabilitas LLM tidak kembali ke state gagal yang sama.*
7. *Exit Code 137 menandakan proses di-kill paksa oleh OOM (Out Of Memory) Killer Linux (SIGKILL). Orchestrator harus mengidentifikasi memory leak struktural pada algoritma atau menaikkan limit RAM container jika beban komputasi terbukti sah.*
8. *Untuk menurunkan entropi probabilitas distribusi token, menghasilkan respons yang paling logis, stabil, minim halusinasi, dan patuh secara ketat pada aturan sintaks.*
9. *Melalui integrasi Mutation Testing. Jika implementasi hanya mengembalikan mock statis tanpa dependensi komputasi, mutan yang disuntikkan pada kode tidak akan mengubah hasil output, sehingga nilai Mutation Score menjadi rendah (banyak mutan survived).*
10. *Pada TDVC, Actor (LLM) dan Critic (Sandbox/Test Runner) tidak memperbarui weight matriks neural network secara real-time via gradient descent, melainkan memperbarui context state prompt via structured in-context feedback.*

#### Bagian C
11. *Kegagalan bersumber pada subsistem Tester Agent yang hanya menguji kasus happy-path (valid asymmetric signature) tanpa menyusun adversarial negative invariants. Invarian yang harus ditambahkan: `def test_reject_none_algorithm(): with pytest.raises(SecurityException): decode_token(tampered_token_with_alg_none)`.*
12. *Terapkan Tiered Feedback & Context Pruning: (a) Jangan kirim keseluruhan codebase, hanya kirim AST chunk fungsi terkait dan concise stack trace, (b) Gunakan LLM kelas lebih kecil (misal gpt-4o-mini / Haiku) untuk iterasi 1-2, dan eskalasikan ke LLM penalaran tingkat tinggi (o1/Sonnet) hanya jika iterasi awal gagal.*
13. *Akar masalah: Penumpukan Zombie Containers, tarfile streams uncollected memory leaks, atau exhaustion namespace cgroups/storage overlay2 driver pada Docker host. Solusi: Gunakan pool kontainer persisten yang di-reset state-nya (`tmpfs` in-memory mounts), hindari destroy-recreate kontainer dari nol per tes, dan terapkan pembersihan berkala volume sampah via daemon.*

---

### 16. Summary

*Test-Driven Vibe-Coding* (TDVC) adalah evolusi rekayasa perangkat lunak modern yang mendisiplinkan daya cipta generatif LLM di bawah aturan pembuktian deterministik. Keandalan produksi tidak dicapai dengan berharap AI tidak membuat kesalahan, melainkan dengan merancang lingkungan pengujian (sandbox, property-based testing, dan mutation testing) yang mustahil ditembus oleh kode yang cacat. Menguasai arsitektur TDVC memungkinkan insinyur perangkat lunak enterprise bertransformasi dari sekadar "penulis sintaksis" menjadi "arsitek invariant sistem" yang memimpin orkestrasi agen otonom berkinerja tinggi.