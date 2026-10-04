# Kurikulum Enterprise: Technical Writer & Documentation Engineering
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB 10: Content Health, Doc Decay, Deprecation, dan Versioning
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Technical Writer, Documentation Engineer, dan AI Platform Engineer diharapkan mampu:
- **Menganalisis dan Memitigasi *Doc Decay* (Pembusukan Dokumentasi):** Mengidentifikasi degradasi sintaksis, semantik, dan kontekstual pada dokumentasi teknis sistem AI/LLM dan arsitektur *autonomous agent*.
- **Membangun Arsitektur *Continuous Content Verification* (CCV):** Merancang dan mengimplementasikan pipeline CI/CD yang memvalidasi integritas kode contoh (*doc-tested snippets*), skema API/SDK, dan spesifikasi *tool definition* agen AI secara otomatis menggunakan *Abstract Syntax Tree* (AST) parsing.
- **Mengelola *Multi-Version Life-Cycle Management*:** Mengorkestrasi strategi percabangan (*branching strategy*), rilis multi-versi (*SemVer* dan *CalVer*), serta otomatisasi pembuatan artefak dokumentasi terisolasi untuk API publik dan internal.
- **Mengimplementasikan Kerangka Kerja Deprekasi Terukur:** Merancang siklus hidup deprecation (dari *soft-deprecation* hingga *tombstoning*) yang terikat dengan telemetri penggunaan runtime, *RFC 8594 Sunset headers*, SEO canonicalization, dan sinkronisasi metadata bagi *agent tools*.

---

### 2. Prerequisite
Untuk menyerap materi ini secara maksimal, praktisi harus memiliki pemahaman mendalam tentang:
- **Git Internals & CI/CD Pipeline:** Mekanisme *branching*, *tagging*, *submodules*, serta implementasi *GitHub Actions* atau *GitLab CI*.
- **Static Site Generators (SSG) & Headless CMS:** Arsitektur Docusaurus, MkDocs Material, Astro, atau Nextra.
- **Abstract Syntax Trees (AST) & Code Parsing:** Konsep dasar *tree-sitter* atau modul Python `ast` untuk ekstraksi signature fungsi dan docstring.
- **API Specifications:** OpenAPI 3.1, JSON Schema Core, gRPC Protobuf, dan spesifikasi Function Calling (OpenAI/Anthropic tool formats).
- **Python / Node.js Runtime:** Kemampuan menulis skrip automasi pengujian dan parsing teks tingkat lanjut.

---

### 3. Concept & Internal Architecture

Dokumentasi dalam ekosistem *AI, Data, dan Autonomous Agents* bukan sekadar teks representasional statis, melainkan **kontrak fungsional (functional contract)**. Ketika API, parameter hiper-model, atau tanda tangan skema JSON pada *tool-calling agent* bermutasi tanpa sinkronisasi dokumentasi, terjadi kondisi **Semantic Drift** yang menyebabkan kegagalan eksekusi model (halusinasi parameter, *type mismatch*, atau kegagalan *runtime agent*).

```
+----------------------------------------------------------------------------------------------------+
|                               ARSIKTEKTUR KESEHATAN KONTEN & VERIFIKASI DOKUMEN                    |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
     ┌────────────────────────┐      ┌─────────────────────────┐      ┌────────────────────────┐
     │   Codebase / Agent     │      │   OpenAPI / Tool Spec   │      │ Documentation Source   │
     │      Repository        │      │       Repository        │      │    (Markdown/MDX)      │
     └───────────┬────────────┘      └────────────┬────────────┘      └───────────┬────────────┘
                 │ (Git Commit/Tag)               │ (Schema Hash)                 │ (PR Event)
                 ▼                                ▼                               ▼
     ┌─────────────────────────────────────────────────────────────────────────────────────────┐
     │                             CONTINUOUS CONTENT VERIFICATION CI                          │
     │                                                                                         │
     │  ┌───────────────────────┐   ┌──────────────────────────┐   ┌────────────────────────┐  │
     │  │ AST Snippet Extractor │   │ Schema Drift Detector    │   │ Markdown Link & Fresh  │  │
     │  │ (Python AST / Babel)  │   │ (OpenAPI diff vs Doc)    │   │ Engine (Git Log Decay) │  │
     │  └───────────┬───────────┘   └─────────────┬────────────┘   └────────────┬───────────┘  │
     └──────────────┼─────────────────────────────┼─────────────────────────────┼──────────────┘
                    │                             │                             │
                    ▼                             ▼                             ▼
     ┌─────────────────────────────────────────────────────────────────────────────────────────┐
     │                         DOC HEALTH ENGINE & DRIFT SCORING                               │
     │                                                                                         │
     │       Doc Decay Score (DDS) = (w1 * Age) + (w2 * DiffCode) + (w3 * TelemetryDrop)       │
     │                                                                                         │
     │  [DDS < 0.2: Healthy]     [0.2 <= DDS < 0.6: Stale Warning]     [DDS >= 0.6: Hard Block]│
     └────────────────────────────────────────────┬────────────────────────────────────────────┘
                                                  │
                                                  ▼
     ┌─────────────────────────────────────────────────────────────────────────────────────────┐
     │                         DEPLOYMENT & LIFECYCLE MANAGEMENT                               │
     │                                                                                         │
     │  ┌───────────────────────┐   ┌──────────────────────────┐   ┌────────────────────────┐  │
     │  │ Semantic Versioning   │   │ Deprecation Orchestrator │   │ SEO & Canonical Engine │  │
     │  │ Engine (/v1/, /v2/)   │   │ (RFC 8594 / Tombstone)   │   │ (rel="canonical" / 301)│  │
     │  └───────────────────────┘   └──────────────────────────┘   └────────────────────────┘  │
     └─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Komponen Internal Arsitektur:
1. **AST Snippet Extractor & Runner:** Modul yang mem-parsing dokumen MDX/Markdown, mengekstrak blok kode yang ditandai (misalnya, ````python doc-test`), lalu mengeksekusinya terhadap *mock sandbox* atau mencocokkan *signature*-nya secara statis dengan AST *codebase* target.
2. **Schema Drift Engine:** Menganalisis perbedaan (*diff*) struktural antara skema produksi (`openapi.json`, model Pydantic untuk tool-agent) dan blok skema yang didokumentasikan.
3. **Decay Scoring Algorithm:** Algoritma deterministik yang menghitung *Doc Decay Score* (DDS) berdasarkan metrik waktu perubahan terakhir Git, frekuensi perubahan kode yang direferensikan, dan telemetri penurunan trafik.
4. **Deprecation & Tombstoning Controller:** Subsistem yang menyuntikkan *warning banner* dinamis, menyisipkan metadata mesin (`x-deprecated`, `sunset`), dan mengonfigurasi header HTTP via edge proxy (Cloudflare Workers/Vercel Middleware).

---

### 4. Why & What

#### Why (Urgensi Bisnis & Arsitektural)
- **Kegagalan Determinisme LLM:** Autonomous agents membaca dokumentasi API sebagai *prompt context*. Dokumentasi yang usang menyebabkan LLM memanggil parameter yang sudah *deprecated*, memicu *infinite retry loops*, dan membengkakkan biaya token inferensi.
- **Customer Churn & Developer Friction:** Integrasi SDK yang gagal pada hari pertama akibat *quickstart guide* kadaluwarsa menurunkan *conversion rate* adopsi platform developer enterprise hingga 40%.
- **Regulatory & Compliance Risk:** Menjual layanan API berbasis AI di lingkungan teregulasi (HIPAA, PCI-DSS, EU AI Act) menuntut audit trail yang ketat terkait versi model mana yang didokumentasikan pada kurun waktu tertentu.

#### What (Definisi Inti)
- **Doc Decay (Pembusukan Dokumen):** Erosi progresif dari keakuratan, relevansi, dan fungsionalitas dokumentasi terhadap sistem perangkat lunak yang terus berevolusi secara asinkron.
- **Contract Testing for Documentation:** Paradigma pengujian yang memperlakukan dokumentasi teknis sebagai implementasi kontrak dari kode sumber.
- **Canonical Deprecation:** Protokol terstruktur untuk menghentikan dukungan dokumen/API tanpa memutus jejak audit web, merusak SEO, atau mematikan integrasi klien secara tiba-tiba.

---

### 5. How (Workflow Detail)

Alur kerja implementasi arsitektur kesehatan dokumen produksi:

1. **Instrumentation & Extraction Phase:**
   - Pre-commit hook atau CI trigger mengekstrak semua blok kode yang memiliki tag `doc-test` dari file Markdown.
   - Pustaka AST membaca berkas sumber SDK asli dan membandingkan *signature* (nama fungsi, tipe data parameter, nilai *return*).

2. **Schema Synchronization Phase:**
   - Menjalankan komparasi JSON Schema antara deklarasi tool agent (JSON schema) dengan representasi tabel Markdown di direktori docs.
   - Jika ada field baru pada schema yang belum tercatat di docs, pipeline melempar status `DriftDetectedError`.

3. **Decay Evaluation Phase:**
   - Pipeline menghitung delta commit git antara file implementasi dan file dokumentasi terkait:
     $$\Delta_{\text{commits}} = \text{Count}(\text{Commits}_{\text{code}}) - \text{Count}(\text{Commits}_{\text{doc}})$$
   - Menghitung metrik usia dokumen sejak verifikasi manual terakhir.

4. **Lifecycle & Deprecation Routing:**
   - Menginjeksi metadata frontmatter:
     ```yaml
     status: deprecated
     deprecated_at: "2024-01-15"
     sunset_date: "2024-12-31"
     replacement_url: "/v2/agents/tool-execution"
     ```
   - Build SSG secara otomatis menghasilkan *callout box*, menyematkan tag `rel="canonical"` ke rilis terbaru, dan mendaftarkan URL ke router edge untuk respons header `Sunset: Wed, 31 Dec 2024 23:59:59 GMT`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Inspeksi Jembatan dan Marka Jalan
Dokumentasi teknis seperti **marka jalan dan rambu lalu lintas**, sedangkan kode aplikasi adalah **konstruksi fisik jalan dan jembatan**.
- *Doc Decay* adalah kondisi di mana jembatan telah diubah menjadi jalan satu arah (perubahan kode), namun rambu masih menandakan dua arah (dokumen lama).
- *AST Contract Testing* adalah tim inspeksi berkala yang membawa cetak biru fisik dan mengukur lebar jalan secara mekanis; jika marka berbeda 1 cm saja dari kondisi aspal aktual, inspeksi memblokir jalan dari izin operasional (CI Build Failed).

#### Diagram Transisi Deprecation Lifecycle
```
 [Aktif / GA] 
      │
      │ (Fungsi/API baru dirilis / Desain lama usang)
      ▼
 [Soft Deprecated]  ───> Injeksi Warning Banner di Docs, Header: `Deprecation: @epoch`
      │
      │ (Tenggat migrasi tercapai / T - 90 hari Sunset)
      ▼
 [Hard Deprecated]  ───> Parameter ditandai `strike-through`, Header: `Sunset: @date`
      │
      │ (API Decommissioned / Runtime Error 410 Gone)
      ▼
 [Tombstoned]       ───> Konten dihapus dari Search Index (noindex), 
                         Halaman menyajikan Panduan Migrasi Permanen
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Menguji Cuplikan Kode Menggunakan Python AST
Skrip mandiri untuk memverifikasi apakah fungsi yang tertulis di dalam dokumentasi masih memiliki parameter yang valid dengan implementasi kode:

```python
import ast
import inspect

# Simulasi modul produksi yang terus berkembang
def execute_agent_tool(tool_name: str, payload: dict, timeout: int = 30) -> bool:
    """Eksekusi tool autonomous agent."""
    return True

# Simulasi cuplikan kode yang diambil dari file documentation.md
doc_snippet = """
execute_agent_tool(tool_name="web_search", payload={"query": "AI"}, debug=True)
"""

def validate_snippet(snippet: str, target_func: callable) -> None:
    tree = ast.parse(snippet)
    sig = inspect.signature(target_func)
    valid_params = set(sig.parameters.keys())

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Ekstraksi keyword argument dari doc snippet
            used_keywords = {kw.arg for kw in node.keywords if kw.arg is not None}
            invalid_calls = used_keywords - valid_params
            if invalid_calls:
                raise ValueError(
                    f"Doc Decay Terdeteksi! Snippet menggunakan parameter tidak valid: {invalid_calls}. "
                    f"Parameter yang valid: {valid_params}"
                )
    print("Validasi Berhasil: Cuplikan dokumentasi sinkron dengan fungsi aktual.")

validate_snippet(doc_snippet, execute_agent_tool)
```

#### Practical Example: Production-Ready DocOps Pipeline & Drift Engine

Struktur proyek:
```
docops-engine/
├── verify_docs.py
└── content/
    └── agents/
        └── run-tool.md
```

##### 1. Konten Markdown Terinstrumentasi (`content/agents/run-tool.md`)
```markdown
---
title: "Agent Tool Execution API"
version: "1.4.0"
deprecated: false
code_ref: "src.agent.engine:AgentRuntime.invoke"
---

# Agent Tool Execution

Gunakan API ini untuk memanggil tools dari model o1/Claude.

```python doc-test
from src.agent.engine import AgentRuntime

runtime = AgentRuntime(environment="production")
response = runtime.invoke(tool="search", query="latency metrics")
```
```

##### 2. Engine Verifikasi Berbasis AST (`verify_docs.py`)
```python
#!/usr/bin/env python3
"""
Production Documentation Health & Drift Engine.
Mengekstrak blok doc-test, memverifikasi AST terhadap signature aktual,
dan memeriksa status deprecation.
"""

from __future__ import annotations
import ast
import importlib
import re
import sys
from pathlib import Path
from typing import Dict, Any, List
import yaml

DOCS_DIR = Path("./content")
DOC_SNIPPET_REGEX = re.compile(r"```python doc-test\n(.*?)```", re.DOTALL)
FRONTMATTER_REGEX = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


class DocDriftVerifier:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.errors: List[str] = []

    def parse_frontmatter(self, content: str) -> Dict[str, Any]:
        match = FRONTMATTER_REGEX.match(content)
        if not match:
            return {}
        try:
            return yaml.safe_load(match.group(1))
        except yaml.YAMLError as err:
            self.errors.append(f"Invalid Frontmatter: {err}")
            return {}

    def extract_snippets(self, content: str) -> List[str]:
        return DOC_SNIPPET_REGEX.findall(content)

    def verify_call_node(self, node: ast.Call, target_func: Any, file_path: Path):
        sig = inspect_signature(target_func)
        if sig is None:
            return

        expected_args = set(sig.keys())
        provided_kwargs = {kw.arg for kw in node.keywords if kw.arg is not None}
        
        drift = provided_kwargs - expected_args
        if drift:
            self.errors.append(
                f"[{file_path}] Signature Drift! Argumen {drift} tidak ditemukan "
                f"pada implementasi kode. Argumen resmi: {expected_args}"
            )

    def process_file(self, file_path: Path):
        text = file_path.read_text(encoding="utf-8")
        meta = self.parse_frontmatter(text)

        if not meta:
            self.errors.append(f"[{file_path}] Frontmatter hilang atau rusak.")
            return

        # Validasi status deprecation metadata
        if meta.get("deprecated") is True and not meta.get("sunset_date"):
            self.errors.append(
                f"[{file_path}] Konten deprecated wajib menyertakan 'sunset_date'."
            )

        snippets = self.extract_snippets(text)
        if not snippets:
            return

        # Validasi AST Snippets
        for snippet in snippets:
            try:
                tree = ast.parse(snippet)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        # Dalam skenario riil, ekstrak module dari metadata atau import internal
                        pass 
            except SyntaxError as e:
                self.errors.append(f"[{file_path}] Syntax Error pada contoh kode: {e}")

    def run(self) -> int:
        for md_file in self.base_dir.rglob("*.md"):
            self.process_file(md_file)
        
        if self.errors:
            print(f"FAILED: Terdeteksi {len(self.errors)} masalah kesehatan dokumentasi:")
            for err in self.errors:
                print(f"  - {err}")
            return 1
            
        print("SUCCESS: Seluruh dokumentasi valid dan sinkron dengan codebase.")
        return 0


def inspect_signature(func: Any) -> Dict[str, Any] | None:
    try:
        import inspect
        return dict(inspect.signature(func).parameters)
    except Exception:
        return None


if __name__ == "__main__":
    verifier = DocDriftVerifier(DOCS_DIR)
    sys.exit(verifier.run())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Migrasi Tool Call LLM di Skala Enterprise (FinTech AI Platform)
* **Konteks:** Sebuah platform perbankan internasional mengelola 450 modul *autonomous agent* untuk pemrosesan transaksi. Setiap modul memiliki skema JSON Schema / Pydantic yang direferensikan dalam portal dokumentasi developer internal dan ribuan *system prompts*.
* **Insiden:** Tim Core Banking mengubah parameter skema `account_id` (string numerik) menjadi `account_urn` (RFC-2141 format) pada rilis v3.4. Portal dokumentasi terlambat diperbarui selama 4 hari. Akibatnya:
  - Agent autonomous internal tetap menggunakan model penalaran dari instruksi dokumentasi lama (`account_id`).
  - LLM menghasilkan *payload* cacat pada 12% total volume transaksi harian, memicu *runtime exception* dan *circuit-breaker trip*.
  - Biaya token terbuang senilai $64.000 akibat re-try loop tak berujung.
* **Solusi Arsitektur:**
  1. **Schema-to-Doc Continuous Ingestion:** Dokumentasi dimutasi dari Markdown statis murni menjadi sistem berbasis *Doc-Gen from Source of Truth*. Modul CI membaca langsung model Pydantic/OpenAPI spec dan merender tabel parameter MDX saat kompilasi static site.
  2. **Git Commit Decay Guard:** Jika developer merevisi field pada file Pydantic tanpa label decorator `@documented(version="...")`, PR otomatis terblokir.
  3. **Deprecation Shadowing:** Skema lama dipertahankan selama 90 hari dengan banner peringatan otomatis di dokumentasi internal dan telemetry log yang mendeteksi agen mana saja yang masih mengakses format lama.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian / Risiko | Biaya Operasional / Latensi |
| :--- | :--- | :--- | :--- |
| **Doc-test via Live Execution** (Menjalankan kode langsung di CI) | Menjamin fungsionalitas 100% end-to-end berjalan tanpa bug. | Waktu build CI membengkak drastis; butuh *mock server*, kredensial database sandbox, dan determinisme data. | Latensi build sangat tinggi; biaya komputasi CI/CD melonjak. |
| **AST-Based Static Analysis** (Parsing AST tanpa eksekusi langsung) | Sangat cepat; memvalidasi kompatibilitas parameter, nama fungsi, dan tipe data statis tanpa butuh sandbox runtime. | Tidak mendeteksi *logical runtime errors* atau kegagalan koneksi jaringan pihak ketiga. | Latensi rendah (milidetik); biaya infrastruktur CI minimal. |
| **Branch-per-Version Docs** (v1.x, v2.x via git branches) | Isolasi dokumen versi lama sangat bersih dan aman dari regresi versi baru. | *Cherry-picking* perbaikan typo atau security update ke dokumen lama sangat lambat dan rawan konflik merge. | Overhead kognitif tim dokumentasi tinggi; kapasitas penyimpanan repositori meningkat. |
| **Monorepo Directory Versioning** (`/docs/v1/`, `/docs/v2/`) | Mudah melakukan *global search & replace*, refactoring struktural serentak lintas versi. | Ukuran direktori membesar tak terbatas; build-time static site generator meningkat seiring banyaknya versi lama. | Waktu kompilasi SSG menjadi lambat secara eksponensial. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Broken Redirects Pasca-Deprekasi (Error 404 pada Mesin Pencari & Agent Retrieval)
* **Gejala:** URL lama dokumen yang di-sunset langsung dihapus dari repositori git.
* **Akar Masalah:** Developer/Writer menghapus berkas Markdown tanpa menyematkan mapping redirect di level edge router (Nginx/Cloudflare/Vercel).
* **Solusi:** Terapkan aturan ketat: Berkas usang tidak boleh langsung dihapus melainkan dialihkan (*301 Moved Permanently*) atau diubah statusnya menjadi halaman *Tombstone* dengan header `410 Gone` bagi endpoint yang benar-benar mati.

#### 2. False Positives pada Pemindaian Doc-Test AST
* **Gejala:** Pipeline CI memutus build PR secara keliru karena menganggap kode dokumentasi tidak valid.
* **Akar Masalah:** Contoh kode dokumentasi memuat pseudocode, elipsis (`...`), atau placeholder seperti `<YOUR_API_KEY>`.
* **Solusi:** Gunakan linter macro khusus untuk dokumentasi:
  ```python
  # docs-ignore-start
  API_KEY = "mock-key-for-ast"
  # docs-ignore-end
  client = AgentClient(api_key=API_KEY)
  ```

#### 3. Canonical Tag Drift yang Merusak SEO
* **Gejala:** Google dan Bing tetap mengindeks dokumentasi versi v1.0 yang sudah *deprecated*, menenggelamkan versi v2.0 terbaru di halaman pencarian.
* **Akar Masalah:** Halaman dokumentasi v1.0 tidak menyematkan tag `<link rel="canonical" href="https://docs.domain.com/v2/..." />`.
* **Solusi:** Pasang otomatisasi metadata pada SSG: Setiap rilis versi baru harus menurunkan canonical tag dari seluruh histori rilis sebelumnya ke rilis rujukan aktif terbaru (*latest/stable*).

---

### 11. Best Practices (Production Checklist)

- [ ] **Automated Linting & AST Checking:** Linter Markdown (misal: `markdownlint`) digabungkan dengan parser AST kode contoh pada setiap *Pull Request*.
- [ ] **SLA Waktu Decay:** Tidak ada dokumen panduan teknis (*guides*) yang tidak ditinjau lebih dari 180 hari; ditandai otomatis via GitHub Action alert.
- [ ] **RFC 8594 Sunset Compliance:** Seluruh endpoint dan panduan yang masuk tahap *deprecation* menyertakan header `Sunset` dan `Deprecation`.
- [ ] **Executable Documentation Snippets:** Minimal 90% dari blok kode *Quickstart* dieksekusi secara otomatis dalam build harian (*Nightly Doc Builds*).
- [ ] **Isolated Agent Tool Manifests:** Seluruh skema deklarasi fungsi agen dihasilkan langsung (*single source of truth*) dari codebase produksi menggunakan ekspor skema terprogram, bukan disalin secara manual.
- [ ] **Tombstone Strategy:** Halaman yang mencapai EOL (*End of Life*) memuat alasan pencabutan, alternatif modul pengganti, dan tombol salin script migrasi.

---

### 12. Hands-on Practice

Buat repositori mini untuk memverifikasi *doc-decay* di lingkungan lokal Anda. Simpan seluruh artefak ini pada direktori: `hands-on/m02/`.

#### Langkah 1: Siapkan Struktur Direktori
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/content hands-on/m02/src
cd hands-on/m02
```

#### Langkah 2: Buat Kode Implementasi SDK (`src/agent.py`)
```python
# hands-on/m02/src/agent.py
class AutonomousAgent:
    def __init__(self, agent_id: str, max_iterations: int = 10):
        self.agent_id = agent_id
        self.max_iterations = max_iterations

    def run_task(self, prompt: str, memory_window: int = 5) -> str:
        """Menjalankan tugas agen secara otonom."""
        return f"Agent {self.agent_id} executed: {prompt}"
```

#### Langkah 3: Buat File Dokumentasi yang Mengalami Decay (`content/agent-guide.md`)
Perhatikan bahwa dokumen ini menggunakan parameter fiktif `debug_mode` yang tidak ada di kode implementasi asli:
```markdown
# hands-on/m02/content/agent-guide.md
# Panduan Autonomous Agent

Inisialisasi agen Anda dengan parameter runtime:

```python doc-test
from src.agent import AutonomousAgent

agent = AutonomousAgent(agent_id="agent-007", max_iterations=20)
# BUG DOKUMENTASI: parameter 'debug_mode' tidak pernah ada di src/agent.py
agent.run_task(prompt="Analisis laporan", debug_mode=True)
```
```

#### Langkah 4: Tulis Skrip Pengujian Linting AST (`validate.py`)
```python
# hands-on/m02/validate.py
import ast
import inspect
import sys
from pathlib import Path
from src.agent import AutonomousAgent

def check_file(md_path: Path):
    content = md_path.read_text()
    import re
    blocks = re.findall(r"```python doc-test\n(.*?)```", content, re.DOTALL)
    
    agent_methods = {
        "run_task": set(inspect.signature(AutonomousAgent.run_task).parameters.keys())
    }

    for block in blocks:
        tree = ast.parse(block)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and hasattr(node.func, "attr"):
                method_name = node.func.attr
                if method_name in agent_methods:
                    used_args = {kw.arg for kw in node.keywords}
                    allowed = agent_methods[method_name]
                    drift = used_args - allowed
                    if drift:
                        print(f"[ERROR] Doc Decay terdeteksi di {md_path}!")
                        print(f"  Metode '{method_name}' memanggil argumen tidak valid: {drift}")
                        print(f"  Argumen yang diperbolehkan: {allowed}")
                        return False
    return True

if __name__ == "__main__":
    success = check_file(Path("content/agent-guide.md"))
    sys.exit(0 if success else 1)
```

#### Langkah 5: Eksekusi dan Verifikasi
Jalankan verifikasi dan amati kegagalan sistem mendeteksi degradasi dokumentasi:
```bash
python3 validate.py
echo $? # Output harus bernilai 1 (menandakan deteksi berhasil memblokir)
```

---

### 13. Exercise

#### Level Easy
Buat skrip Python sederhana yang membaca file `index.md` dan memvalidasi apakah semua URL eksternal (menggunakan `http://` atau `https://`) mengembalikan HTTP Status Code `200 OK`. Tangani kondisi URL `404 Not Found` dan cetak peringatannya ke konsol.

#### Level Medium
Buat parser Markdown yang membaca frontmatter semua file dalam sebuah repositori dokumen. Hitung metrik **Doc Decay Score (DDS)** berdasarkan formula:
$$\text{DDS} = (\text{Hari Sejak Terakhir Diperbarui} \times 0.005) + (1.0 \text{ jika belum di-update}>\text{90 hari, else } 0.0)$$
Tolak (*exit code 1*) jika ada dokumen yang memiliki $\text{DDS} \ge 1.0$.

#### Level Hard
Rancang modul Python yang terintegrasi dengan modul Pydantic `BaseModel`. Skrip harus membaca berkas Markdown API yang memuat tabel spesifikasi parameter, lalu membandingkannya dengan model Pydantic terkait:
- Validasi apakah setiap *attribute* Pydantic tercantum dalam tabel Markdown.
- Validasi apakah tipe datanya (*type hints*: `str`, `int`, `Optional[float]`) sesuai dengan kolom 'Type' pada tabel Markdown.
- Buat penanda otomatis yang memperbarui tabel Markdown secara *in-place* tanpa merusak teks deskriptif yang ditulis oleh technical writer.

---

### 14. Challenge

#### Skenario:
Platform AI Anda memiliki arsitektur multi-versi dengan 3 kanal aktif:
1. `v1.2` (Maintenance mode, Sunset dalam 60 hari)
2. `v2.0` (Stable, General Availability)
3. `v3.0-rc` (Release Candidate, Khusus internal developer)

Autonomous agent tool specifications berubah pada `v3.0-rc` di mana format pemanggilan *asynchronous tool* tidak lagi mengembalikan polling UUID melainkan Webhook SSE (Server-Sent Events).

#### Misi Tantangan:
Rancang arsitektur DocOps enterprise terdistribusi yang:
1. Menghasilkan sistem percabangan dokumen yang secara mandiri menyuntikkan *routing matrix* ke CDN Edge:
   - Permintaan ke dokumen `/v1.2/` otomatis menampilkan banner interaktif berisi sisa hitung mundur (countdown) hari sunset, dan otomatis menyertakan tag `<meta name="robots" content="noindex">`.
   - Mengalihkan referensi parameter usang langsung ke padanannya di `/v2.0/`.
2. Menyediakan sebuah tool CLI mandiri (`doc-contract-audit`) yang:
   - Menerapkan AST contract testing pada blok kode Python, TypeScript, dan cURL yang ada di semua versi dokumentasi secara paralel.
   - Menghentikan proses merge Git PR jika ada kontradiksi kontrak antara representasi tool spec di `v3.0-rc` dengan skema JSON schema agent platform.
3. Seluruh proses tidak boleh memperlambat total waktu eksekusi CI lebih dari 90 detik untuk repositori dokumentasi berisi 1.500 file.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara *Doc Decay* dan *Broken Link*?**
   * *Jawaban Singkat:* Broken link adalah kegagalan resolusi URL (HTTP 404), sedangkan Doc Decay adalah degradasi semantik di mana dokumen dapat diakses secara teknis namun informasi instruksional atau parameternya sudah tidak sesuai dengan perilaku kode aktual.
2. **Kapan suatu halaman dokumentasi harus ditandai dengan HTTP status `410 Gone` dibanding `301 Moved Permanently`?**
   * *Jawaban Singkat:* `301 Moved` digunakan saat fitur/halaman memiliki ekuivalen pengganti di alamat baru. `410 Gone` digunakan untuk halaman/fitur yang sudah dihentikan total (*tombstoned*) secara permanen tanpa ada pengganti langsung.
3. **Apa peran *Abstract Syntax Tree* (AST) dalam DocOps?**
   * *Jawaban Singkat:* AST membaca dan mengonversi struktur sintaksis kode pada dokumentasi menjadi representasi pohon objek, memungkinkan validasi penamaan fungsi, tipe parameter, dan argumen tanpa perlu mengeksekusi kode secara langsung.
4. **Mengapa tag `rel="canonical"` mutlak diperlukan dalam dokumentasi multi-versi?**
   * *Jawaban Singkat:* Untuk memberi tahu mesin pencari halaman mana yang merupakan versi utama (*single source of truth*) guna mencegah penalti *duplicate content* dan memastikan trafik pencarian diarahkan ke versi rilis yang paling mutakhir.
5. **Apa fungsi dari header HTTP `Sunset` berdasarkan RFC 8594?**
   * *Jawaban Singkat:* Memberi tahu klien secara formal tanggal dan waktu pasti di masa depan kapan suatu endpoint API atau sumber daya web akan dinonaktifkan sepenuhnya.

#### Intermediate (5 Pertanyaan)
6. **Bagaimana cara menangani contoh kode (*code snippet*) di dalam dokumen yang membutuhkan koneksi API key rahasia agar pipeline CI tidak bocor dan tidak gagal?**
   * *Jawaban Singkat:* Gunakan *mocking framework* atau AST parsing statis yang mengabaikan eksekusi jaringan, atau pisahkan token menggunakan environment injection khusus sandbox runner dengan peran akses baca terbatas (*read-only sandbox*).
7. **Dalam dokumentasi AI Autonomous Agent, mengapa inkonsistensi skema JSON pada tool definition berdampak lebih fatal dibanding dokumen REST API konvensional?**
   * *Jawaban Singkat:* Developer manusia dapat mengasumsikan dan memvalidasi tipe data yang keliru secara intuitif, sedangkan *autonomous agent* mem-parsing skema sebagai prompt instruksi langsung. Kesalahan tipe format skema memicu halusinasi pemanggilan fungsi (*hallucinatory tool calling*), looping tak hingga, atau crash saat proses eksekusi transaksi otonom.
8. **Jelaskan risiko penggunaan strategi *branch-per-version* pada static site generator dokumentasi saat timbul kebutuhan perbaikan massal (misalnya: kerentanan lisensi atau update footer legal)!**
   * *Jawaban Singkat:* Terjadinya biaya operasional tinggi karena perbaikan harus di-*backport* dan di-*cherry-pick* secara manual ke setiap git branch versi terdahulu, yang berpotensi memicu konflik Git dan inkonsistensi layout visual.
9. **Bagaimana cara mencegah bot mesin pencari mengindeks dokumentasi versi beta/nightly tanpa merusak visibilitas versi stable?**
   * *Jawaban Singkat:* Konfigurasikan header `X-Robots-Tag: noindex, nofollow` khusus pada route versi beta/nightly via server proxy/edge config, atau sematkan tag `<meta name="robots" content="noindex">` di layer komponen layout framework dokumentasi.
10. **Apa metrik terpenting dalam menyusun *Doc Decay Score* (DDS) secara objektif?**
    * *Jawaban Singkat:* Delta commit Git antara repositori kode dan repositori dokumentasi, umur absolut dokumen sejak review manual terakhir, serta rasio error telemetri/laporan komplain pengguna terhadap artikel tersebut.

#### Kasus Produksi (3 Skenario Kasus)

11. **Skenario 1:** *Platform AI Anda merilis API generasi embedding v2. API v1 menggunakan parameter `input_text: str`, sedangkan API v2 menggunakan `inputs: List[str]`. Setelah v2 diluncurkan, 30% pengembang baru di platform Anda mengeluh bahwa kode mereka mendapat error `422 Unprocessable Entity` saat mengikuti dokumentasi Quickstart.*
    * **Analisis & Solusi:** Telah terjadi inkonsistensi di mana halaman Quickstart belum diperbarui saat peluncuran v2. Solusi arsitektural: Pasang sistem integrasi contract test di CI di mana *Quickstart snippet* dieksekusi langsung terhadap endpoint mock sandbox. Jika endpoint v2 menolak struktur payload dari contoh Quickstart, build deployment portal dokumen dibatalkan otomatis.

12. **Skenario 2:** *Tim security menemukan bahwa dokumen internal arsitektur agent yang memuat diagram rahasia dan spesifikasi parameter audit v0.9 secara tidak sengaja diindeks oleh Googlebot karena situs dokumentasi internal dipublikasikan tanpa autentikasi.*
    * **Analisis & Solusi:** Lakukan tindakan berjenjang:
      1. Terapkan otentikasi di level reverse proxy / Identity-Aware Proxy (misalnya Cloudflare Access / OAuth).
      2. Jangan hanya menghapus halaman; kembalikan HTTP `410 Gone` atau sematkan header `X-Robots-Tag: noindex`.
      3. Ajukan *Urgent URL Removal* via Google Search Console untuk menghapus cache pencarian dalam hitungan jam.

13. **Skenario 3:** *Sebuah autonomous agent membaca spesifikasi OpenAPI yang di-embed pada dokumentasi web untuk memanggil endpoint `/refund`. OpenAPI di web masih mencatat skema lama tanpa parameter `approver_id`. Ketika agen memanggil endpoint tersebut di server produksi, transaksi digagalkan secara sistematis oleh backend karena ketiadaan `approver_id`.*
    * **Analisis & Solusi:** Akar persoalannya adalah segregasi manual (*manual duplication*) antara dokumentasi dan kode backend. Solusi: Hapus pendefinisian skema manual di Markdown. Terapkan pola *Single Source of Truth* (SSOT): Dokumentasi harus mengimpor file `openapi.json` yang digenerate langsung dari kode backend saat proses kompilasi rilis, memastikan agen dan manusia membaca kontrak data yang mutlak sama.

---

### 16. Summary

Kesehatan dokumentasi (*Content Health*) dalam rekayasa perangkat lunak modern dan ekosistem agen AI merupakan pilar keandalan sistem (*reliability engineering*), bukan sekadar pekerjaan administratif penyuntingan kata. *Doc Decay* adalah bentuk utang teknis (*technical debt*) yang dapat diukur, dicegah, dan diotomatisasi mitigasinya.

Dengan mengadopsi metodologi **Docs-as-Code** tingkat lanjut—termasuk validasi berbasis AST (*Abstract Syntax Tree*), pelacakan perbedaan skema secara kontinu, pengelolaan masa pakai deprecation yang berstandar RFC, serta penataan hierarki multi-versi yang terisolasi—organisasi dapat menjamin bahwa setiap artefak dokumentasi berfungsi sebagai kontrak teknis yang deterministik, andal, dan aman bagi pengguna manusia maupun *autonomous AI agent*.