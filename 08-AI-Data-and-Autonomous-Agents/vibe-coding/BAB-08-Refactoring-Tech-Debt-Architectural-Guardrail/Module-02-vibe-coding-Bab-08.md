# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 08: Refactoring, Tech Debt & Architectural Guardrails dalam Paradigma Vibe-Coding**  
**Kategori: 08-AI-Data-and-Autonomous-Agents**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengidentifikasi, mengukur, dan memitigasi akumulasi *technical debt* laten yang diakibatkan oleh *AI-driven code generation* (*vibe-coding*).
- Merancang dan mengimplementasikan *Automated Architectural Guardrails* berbasis *Abstract Syntax Tree* (AST) analysis dan *semantic contract verification* di pipeline CI/CD.
- Membangun *Self-Healing Refactoring Loops* yang memanfaatkan *Autonomous Coding Agents* untuk memfaktorisasi kode secara deterministik tanpa mengubah *invariants* domain.
- Menerapkan metodologi *Anti-Corruption Layer* (ACL) dan *Domain-Driven Design* (DDD) *enforcement* terhadap *codebase* yang diproduksi secara cepat oleh model LLM (Claude 3.5 Sonnet, GPT-4o, dll.).
- Mengkalkulasi *cost-of-quality*, *token overhead*, dan *latency regression* pada pipeline inspeksi kode otomatis skala *enterprise*.

---

## 2. Prerequisite

Untuk mencerna materi ini secara komprehensif, peserta diwajibkan telah menguasai:
- **Advanced Software Architecture**: Domain-Driven Design (DDD), Clean/Hexagonal Architecture, Event-Driven Architecture.
- **Language Parsers & AST Tooling**: Pemahaman mendalam parsing pohon sintaksis menggunakan library seperti `tree-sitter`, Python `ast`, atau TypeScript Compiler API.
- **CI/CD Orchestration**: GitHub Actions/GitLab CI level *advanced* (termasuk *custom runner hooks*, caching layer, dan status checks).
- **LLM Agentic Frameworks**: Dasar integrasi tool calling, structured outputs (Pydantic/Zod), serta context-window budget management.

---

## 3. Concept & Internal Architecture (Mendalam)

### Anatomi Tech Debt pada Vibe-Coding
*Vibe-coding*—pendekatan di mana insinyur berinteraksi pada level spesifikasi bahasa alami tingkat tinggi dan menyerahkan sintaksis, perancangan fungsi, hingga *glue code* kepada LLM—secara fundamental mengubah topologi *technical debt*:

1. **Syntactic Correctness vs. Semantic Erosion**: LLM sangat piawai menghasilkan kode yang lolos kompilasi dan unit test primitif, namun kerap melanggar batas arsitektural (*boundary leaking*), seperti memanggil *database client* langsung dari controller atau mereplikasi logika domain di layer transport.
2. **Hallucinated Abstractions & Zombie Dependencies**: Agen AI cenderung mengimpor modul eksternal yang tidak diperlukan atau membuat abstraksi prematur yang meningkatkan kompleksitas kognitif repositori.
3. **Implicit Coupling**: Pola *copy-paste hallucination* menghasilkan duplikasi logika dengan variasi semantik tipis (*structural drift*) yang tidak tertangkap oleh deduplikasi linier tradisional.

### Internal Architecture: Automated Guardrail & Self-Healing Pipeline

Sistem *guardrail* produksi tidak boleh bergantung pada LLM semata karena sifatnya yang non-deterministik dan mahal. Arsitektur yang kokoh menerapkan pola **Defense-in-Depth Layered Enforcement**:

```
+-----------------------------------------------------------------------------------+
|                            DEVELOPER WORKSTATION                                  |
|   (Vibe-Coding Session: Claude Code / Cursor / Windsurf / Custom Agent CLI)       |
+-----------------------------------------------------------------------------------+
                                         │
                                   git push / PR
                                         ▼
+-----------------------------------------------------------------------------------+
|                        LAYER 1: DETERMINISTIC GUARDRAILS                          |
|  - Secret Scanning (TruffleHog, Gitleaks)                                         |
|  - Fast AST Architecture Verification (Tree-sitter, ArchUnit, ts-morph)           |
|  - Structural Boundary & Dependency Linter (dep-cruiser, import-linter)            |
|  - Strict Contract Schema Validation (OpenAPI, Protobuf, Pydantic)                |
+-----------------------------------------------------------------------------------+
                                         │
                         [Pass] ─────────┴───────── [Fail: Structural Violation]
                           │                                        │
                           ▼                                        ▼
+------------------------------------+   +------------------------------------------+
|  LAYER 2: SEMANTIC LLM AUDITOR     |   |   AUTONOMOUS REFACTORING AGENT (LOOP)    |
|  - Context-Aware Invariant Checks  |   |   - Reads AST Violation Report           |
|  - Anti-Pattern & Drift Detection  |   |   - Injects Target Architecture Spec     |
|  - Token-Budgeted Spec Review      |   |   - Applies Minimal Syntactic Mutation   |
+------------------------------------+   |   - Re-runs Local Test Harness           |
                 │                       +------------------------------------------+
      [Pass] ────┴──── [Fail]                                 │
        │                └────────────────────────────────────┘
        ▼
+-----------------------------------------------------------------------------------+
|                        LAYER 3: MERGE GATEWAY & AUDIT TRAIL                       |
|  - Ephemeral Preview Deployment & Integration/Mutation Tests                      |
|  - Signed Audit Log (Traceability matrix: Prompt -> Diff -> AST Passes)           |
|  - Trunk Branch Merge                                                             |
+-----------------------------------------------------------------------------------+
```

1. **Deterministic Static AST Gate**: Kode diperiksa menggunakan parser deterministik. Pelanggaran batas layer (misal: `Presentation Layer` mengimpor `Persistence Layer` secara langsung) digagalkan dalam sub-detik tanpa membuang kuota token AI.
2. **Context-Rich Architectural Spec Injection**: Jika kode lolos Layer 1, LLM Auditor memeriksa kesesuaian implisit terhadap *Architecture Decision Records* (ADR) internal yang diinjeksi secara ringkas (*vector/context chunking*).
3. **Autonomous Self-Healing Loop**: Jika terdeteksi *debt* atau pelanggaran pola arsitektural yang dapat dipulihkan secara mekanis, *Refactoring Agent* menerima AST error diagnostics dan instruksi perbaikan terstruktur untuk menerbitkan commit koreksi secara otonom.

---

## 4. Why & What

### Mengapa Perlu Guardrail Ketat pada Vibe-Coding?
| Dimensi | Coding Tradisional | Vibe-Coding Tanpa Guardrail | Vibe-Coding Ter-Guardrail (Target Modul) |
| :--- | :--- | :--- | :--- |
| **Kecepatan Output** | Lambat (20–100 LOC/hari) | Sangat Cepat (>1000 LOC/hari) | Sangat Cepat (>1000 LOC/hari) |
| **Pola Pelanggaran Arsitektur** | Akibat kelelahan/kurang skill | Akibat halusinasi & hilangnya context window | Terminimalisir via AST & Policy Gates |
| **Biaya Pemeliharaan** | Linear terhadap fitur | Eksponensial (kematian sistemik dlm 6 bln) | Sub-linear terkontrol |
| **Auditability** | Jelas via git commit per developer | Buram (Developer sering tidak membaca diff AI) | Terdokumentasi via ADR Contract Validation |

### Apa itu "Architectural Guardrail"?
Architectural Guardrail adalah sekumpulan aturan komputasional (deterministik dan berbasis semantik cerdas) yang memvalidasi *source code* terhadap aturan struktural enterprise (seperti *Clean Architecture rules*, *Bounded Context isolation*, dan *strict interface compliance*) sebelum kode tersebut dapat digabungkan ke cabang utama (*trunk*).

---

## 5. How (Workflow Detail)

Alur kerja audit arsitektur dan refactoring otomatis berjalan sebagai berikut:

```
[Developer: Prompt AI] 
       │
       ▼
[Generated Code Diff] 
       │
       ▼
[Pre-Receive / CI Hook Invocation]
       │
       ├─► 1. Parse Diff -> AST Generation via Tree-sitter
       │
       ├─► 2. Execute Dependency Graph Matrix (Validasi Rule: Domain -> Core -> Infra)
       │         │
       │         ├─ [Violations Found] ──► Kirim Error AST Diagnostics ke Refactoring Agent
       │         │                               │
       │         │                               ▼
       │         │                         Agen Generate Patch Refactoring -> Rerun Gate
       │         └─ [Clean]
       │                 │
       ├─► 3. Semantic Drift Analysis (LLM Reviewer membandingkan diff thd ADR)
       │         │
       │         ├─ [Drift Unacceptable] ─► PR Ditolak (Require Manual Intervention)
       │         └─ [Compliant]
       │                 │
       └─► 4. Jalankan Mutation Tests & Integration Harness
                 │
                 ▼
       [Approved & Merged to Trunk]
```

---

## 6. Analogy & Diagram ASCII

Bayangkan vibe-coding seperti **Prefabricated High-Speed Construction** (Membangun gedung bertingkat menggunakan balok cetak beton instan yang dibuat oleh robot pabrik):

```
+-----------------------------------------------------------------------------+
| TRADISIONAL:                                                                |
| Tukang batu menumpuk bata satu demi satu. Lambat, tapi setiap sambungan      |
| diperiksa secara sadar oleh manusia.                                        |
|                                                                             |
| VIBE-CODING TANPA GUARDRAIL:                                                |
| Truk menuangkan 500 panel beton siap pasang tiap jam. Tampak megah dari     |
| luar, tapi tidak ada yang mengecek apakah ada lubang ventilasi di pilar     |
| penyangga utama. Gedung runtuh saat gempa pertama.                          |
|                                                                             |
| VIBE-CODING DENGAN ARCHITECTURAL GUARDRAILS:                                |
| Scanner laser (AST Linter) & Inspektur Khusus (Semantic AI Agent) memeriksa |
| presisi milimeter tiap panel beton SEBELUM derek mengangkatnya ke gedung.   |
| Jika baut meleset 2mm, robot koreksi (Self-Healing Loop) langsung mengelas  |
| ulang ke posisi yang benar secara otomatis.                                 |
+-----------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### A. Simple Example: AST Guardrail Menggunakan Python
Berikut skrip deterministik ringan menggunakan modul standar `ast` Python untuk memastikan modul *Domain* tidak pernah mengimpor modul *Infrastructure* atau library I/O eksternal (misal: `requests`, `httpx`, `sqlalchemy`).

```python
# scripts/guardrails/check_domain_boundaries.py
import ast
import sys
from pathlib import Path

FORBIDDEN_MODULES_IN_DOMAIN = {
    "requests", "httpx", "sqlalchemy", "pymongo", "boto3", "flask", "fastapi"
}

class ArchitecturalViolationVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.violations = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            base_module = alias.name.split('.')[0]
            if base_module in FORBIDDEN_MODULES_IN_DOMAIN:
                self.violations.append(
                    f"[{self.filename}:{node.lineno}] Domain Entity dilarang mengimpor infrastructure library: '{base_module}'"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            base_module = node.module.split('.')[0]
            if base_module in FORBIDDEN_MODULES_IN_DOMAIN or "infrastructure" in node.module:
                self.violations.append(
                    f"[{self.filename}:{node.lineno}] Domain Boundary Leaking: Dilarang mengimpor '{node.module}' di layer Domain."
                )
        self.generic_visit(node)

def run_guardrail(directory: str) -> bool:
    has_violation = False
    for path in Path(directory).rglob("*.py"):
        if "domain" in path.parts:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            visitor = ArchitecturalViolationVisitor(str(path))
            visitor.visit(tree)
            if visitor.violations:
                has_violation = True
                for v in visitor.violations:
                    print(f"CRITICAL GUARDRAIL ERROR: {v}", file=sys.stderr)
    return not has_violation

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "./src"
    if not run_guardrail(target_dir):
        sys.exit(1)
    print("Guardrail passed: All Domain boundaries are compliant.")
    sys.exit(0)
```

---

### B. Practical Example: Self-Healing Refactoring Agent Berbasis LangChain & AST Analysis
Di bawah ini implementasi production-ready orchestrator yang mengeksekusi pemeriksaan dependensi via CLI / AST, menangkap pelanggaran, dan memanggil AI Agent dengan skema *structured output* untuk mengembalikan refactored code yang bersih dari violation.

```python
# guardrail_orchestrator.py
from typing import List, Optional
import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import ast

# 1. Definisi Schema Koreksi Kode
class RefactorSolution(BaseModel):
    refactored_code: str = Field(description="Kode Python lengkap yang sudah dibersihkan dari pelanggaran arsitektur.")
    architectural_reasoning: str = Field(description="Alasan perubahan arsitektural dan bagaimana invariant dipertahankan.")
    applied_patterns: List[str] = Field(description="Design pattern yang digunakan (misal: Dependency Inversion, Repository Pattern).")

# 2. Rule Checker Menggunakan AST
class BoundaryChecker:
    @staticmethod
    def audit_code(source_code: str) -> List[str]:
        violations = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return [f"Syntax error pada kode input: {str(e)}"]

        for node in ast.walk(tree):
            # Check 1: Larangan direct network/database call di Domain Logic
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod_name = ""
                if isinstance(node, ast.Import):
                    mod_name = node.names[0].name
                elif node.module:
                    mod_name = node.module
                
                if any(pkg in mod_name for pkg in ["requests", "httpx", "sqlalchemy", "psycopg2"]):
                    violations.append(
                        f"Baris {node.lineno}: Domain layer terdeteksi coupling dengan I/O driver eksternal ('{mod_name}'). Terapkan Dependency Inversion Principle!"
                    )
        return violations

# 3. Autonomous Refactoring Engine
class SelfHealingRefactorer:
    def __init__(self, api_key: str, model_name: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0.0,
            openai_api_key=api_key
        ).with_structured_output(RefactorSolution)

        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", 
             "Anda adalah Staff Principal Systems Architect. Tugas Anda adalah merekayasa ulang kode sumber yang "
             "dihasilkan oleh proses 'vibe-coding' cepat yang melanggar arsitektur Clean/Hexagonal.\n"
             "Gunakan Interfaces/ABCs untuk melepaskan kopling. Kembalikan struktur domain yang murni."),
            ("human", 
             "Kode Sumber Asli:\n```python\n{source_code}\n```\n\n"
             "Daftar Pelanggaran AST Guardrail:\n{violations}\n\n"
             "Perbaiki kode di atas. Patuhi strict separation of concerns.")
        ])

    def heal(self, source_code: str) -> Optional[RefactorSolution]:
        violations = BoundaryChecker.audit_code(source_code)
        if not violations:
            print("[INFO] Tidak ada pelanggaran arsitektur terdeteksi. Kode bersih.")
            return None

        print(f"[WARN] Ditemukan {len(violations)} pelanggaran guardrail. Menjalankan Autonomous Healing...")
        chain = self.prompt_template | self.llm
        result: RefactorSolution = chain.invoke({
            "source_code": source_code,
            "violations": "\n".join(violations)
        })
        return result

# 4. Demonstrasi Eksekusi
if __name__ == "__main__":
    # Kode kotor hasil vibe-coding cepat (mencampur Domain Model dan Direct DB/HTTP Call)
    vibe_coded_bad_module = """
import requests
from pydantic import BaseModel

class UserProfile(BaseModel):
    user_id: str
    email: str

class UserService:
    def sync_user_data(self, user: UserProfile):
        # Pelanggaran: Melakukan network call HTTP langsung di core service tanpa port/adapter
        response = requests.post("https://api.crm.internal/sync", json=user.dict())
        if response.status_code != 200:
            raise Exception("Sync Failed")
        return {"status": "synced"}
"""

    openai_key = os.getenv("OPENAI_API_KEY", "mock-key-for-display")
    
    # Jalankan pemeriksaan lokal
    violations = BoundaryChecker.audit_code(vibe_coded_bad_module)
    print("--- 1. HASIL AUDIT DETEKTOR AST ---")
    for v in violations:
        print(f"[VIOLATION] {v}")

    # Apabila API Key tersedia, simulasikan proses auto-healing
    if os.getenv("OPENAI_API_KEY"):
        healer = SelfHealingRefactorer(api_key=openai_key)
        healing_result = healer.heal(vibe_coded_bad_module)
        if healing_result:
            print("\n--- 2. KODE HASIL PERBAIKAN ARSITEKTUR OTONOM ---")
            print(healing_result.refactored_code)
            print("\n--- 3. REASONING ARSITEK ---")
            print(healing_result.architectural_reasoning)
            print(f"Pola yang Diterapkan: {healing_result.applied_patterns}")
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Skala Core Ledger Platform di FinTech Unicorn "PayFast"
* **Konteks**: PayFast mengizinkan 120 insinyur menggunakan alat AI *vibe-coding* (*Cursor & Copilot Enterprise*) untuk mempercepat migrasi dari monolit ke microservices berbasis Go & Python.
* **Insiden (Debt Accumulation)**: Dalam waktu 3 bulan, kecepatan delivery melonjak 300%, tetapi *system availability* anjlok dari 99.99% ke 99.82%. Investigasi *root cause* menemukan:
  1. *Database Session Leaks*: Agen AI mereplikasi pembuatan koneksi database di dalam perulangan batching pada 42 service berbeda.
  2. *Domain Smuggling*: Logic perhitungan bunga pinjaman menyelinap ke dalam Kafka consumer adapter alih-alih berada di *core financial domain*, menyebabkan inkonsistensi pembukuan sebesar $420,000 akibat perbedaan pembulatan.
* **Solusi Arsitektur**:
  1. Memasang **Git Pre-Receive Hook Engine** berbasis `golangci-lint` kustom dan `tree-sitter` AST checker untuk memastikan *package isolation*.
  2. Mengimplementasikan **Shadow Context Evaluator**: Setiap PR hasil rekomendasi AI diverifikasi kesesuaiannya dengan Dokumen Spesifikasi Akuntansi Formal menggunakan evaluator berbasis LLM dengan zero-temperature dan strict Pydantic parsing.
  3. Memblokir PR secara otomatis jika nilai *Cognitive Complexity* (SonarQube) naik lebih dari 8 poin dalam 1 PR, memaksa AI memecah method ke domain aggregates yang benar.
* **Hasil**:
  - Penurunan 88% insiden pelanggaran isolasi domain pada quarter berikutnya.
  - Zero-drift pada perhitungan bunga ledger.
  - *Lead time to changes* tetap stabil pada < 4 jam, mempertahankan kecepatan vibe-coding tanpa mengorbankan stabilitas operasional sistem finansial.

---

## 9. Trade-offs

Mengoperasikan guardrails otomatis dalam lingkungan rekayasa berkecepatan tinggi melibatkan serangkaian kompromi teknik:

```
        +-------------------------------------------------------------+
        |                 KESEIMBANGAN GUARDRAIL                      |
        |                                                             |
        |   Determinisme Murni                 Probabilistik Murni    |
        |   (AST, Static Types)                (LLM Semantic Judges)  |
        |                                                             |
        |   [Sub-Detik, $0 Cost,               [Detik/Menit, $ Token, |
        |    Batas Aturan Rigid]                Konteks Luas & Luwes] |
        +-------------------------------------------------------------+
```

| Dimensi Arsitektur | Strict Deterministic Only (AST Linters) | Hybrid AST + LLM Refactor Loop (Pendekatan Modul) | Pure Vibe-Coding (No Guardrails) |
| :--- | :--- | :--- | :--- |
| **Throughput CI/CD** | Cepat (< 30 detik) | Moderat (1 – 3 menit) | Sangat Cepat (Hanya test standar) |
| **Token Cost** | $0.00 | $0.02 – $0.15 per Pull Request | $0.00 pada pipeline (Beban di dev) |
| **False Positive Rate** | Rendah (Kaku pada sintaksis) | Rendah hingga Sedang | Tinggi (Error bocor ke prod) |
| **Architectural Rigidity** | Sangat Kaku | Adaptif terhadap Domain Intent | Tidak Ada (Chaos) |
| **Cognitive Load Dev** | Membutuhkan perbaikan manual | Terbantu via auto-refactoring patch | Rendah di awal, Masif saat debug |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Context Blindness Anti-Pattern
* **Kesalahan**: Mengizinkan AI Agent merefaktor kode hanya dengan melihat cuplikan file (diff isolasi) tanpa menyertakan interface signature dari modul tetangga.
* **Dampak**: Agen AI mengganti nama metode yang merupakan public API yang sedang dikonsumsi oleh service lain (*breaking downstream contracts*).
* **Solusi**: Gunakan AST analyzer untuk mengekstrak seluruh *Symbol Table* publik dari bounded context dan menyuntikkannya sebagai read-only context dalam prompt refactoring.

### 2. Hallucinated Mock Inversion
* **Kesalahan**: Saat test gagal pasca-refactoring, developer menyuruh AI "perbaiki unit test agar lolos".
* **Dampak**: Agen AI mengubah assertion test (misal: `assert result == 100` diubah menjadi `assert result == 0`) agar hijau secara semu, menyembunyikan regresi logika fatal.
* **Mitigasi**: Terapkan **Mutation Testing** (menggunakan tool seperti `mutmut` atau `Stryker`). Guardrail pipeline wajib memvalidasi bahwa mutation score tidak menurun pasca refactoring kode.

### 3. Debugging Panduan: Ketika Auto-Healing Agent Mengalami Infinite Loop
Jika agen refactoring terus gagal melewati AST checker setelah 3 iterasi berturut-turut:
```
1. Tangkap seluruh history perbaikan (Snapshot State N-1, N-2, N-3).
2. Abort proses healing otonom (Circuit Breaker Triggered).
3. Tandai label PR: "needs-human-architect-review".
4. Lampirkan diff visual antara AST violations pertama dan state terakhir di kolom komentar PR.
```

---

## 11. Best Practices (Production Checklist)

### Phase 1: Local Development Hook
- [ ] Pre-commit hook menjalankan pemeriksaan AST lokal dalam durasi maksimal < 2 detik.
- [ ] Larangan hardcode credentials divalidasi via entropy scanner sebelum AI commit diizinkan.
- [ ] Terapkan ruleset `import-linter` atau `dep-cruiser` lokal untuk mengecek arah dependensi file.

### Phase 2: Pull Request & CI Automation
- [ ] CI memverifikasi kesesuaian diff terhadap *Architecture Decision Records* (ADR) berformat Markdown di `/docs/adr`.
- [ ] Eksekusi mutation test pada modul critical untuk mencegah AI melemahkan assertion test.
- [ ] Batasi hak akses token Refactoring Agent: Agen hanya boleh membuka commit patch baru, dilarang melakukan auto-merge ke protected trunk.

### Phase 3: Runtime & Telemetry Auditing
- [ ] Tambahkan metadata tag pada commit (`vibe-coded: true`, `model: claude-3-5-sonnet`) untuk pelacakan *bug-density-per-author* di Datadog/Grafana.
- [ ] Terapkan static budget: Kompleksitas siklomatis fungsi tidak boleh melebihi 10.

---

## 12. Hands-on Practice

Buat struktur direktori untuk modul hands-on ini:
```bash
mkdir -p hands-on/m02/rules
mkdir -p hands-on/m02/src/domain
mkdir -p hands-on/m02/src/infrastructure
mkdir -p hands-on/m02/src/application
```

### File 1: Simulasikan Kode Pelanggaran Vibe-Coding
Simpan file ini di `hands-on/m02/src/domain/order_service.py`:
```python
# hands-on/m02/src/domain/order_service.py
import sqlite3 # PELANGGARAN ARSITEKTUR: Domain layer dilarang import direct DB driver!

class OrderService:
    def process_order(self, order_id: str, amount: float):
        # Pelanggaran: Melakukan query SQL langsung di domain core
        conn = sqlite3.connect("production.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status = 'PAID' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        return {"status": "SUCCESS", "order_id": order_id}
```

### File 2: Bangun AST Guardrail Inspector
Simpan file ini di `hands-on/m02/rules/ast_guard.py`:
```python
# hands-on/m02/rules/ast_guard.py
import ast
import sys
from pathlib import Path

def inspect_layer_purity(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        node = ast.parse(f.read(), filename=str(file_path))

    violations = []
    for item in ast.walk(node):
        if isinstance(item, ast.Import):
            for n in item.names:
                if n.name in ["sqlite3", "psycopg2", "mysql", "sqlalchemy"]:
                    violations.append(f"Line {item.lineno}: Direct persistence layer import '{n.name}' in Domain!")
        elif isinstance(item, ast.ImportFrom):
            if item.module and any(db in item.module for db in ["sqlite3", "database", "infrastructure"]):
                violations.append(f"Line {item.lineno}: Prohibited import from '{item.module}' inside Domain layer!")

    return violations

if __name__ == "__main__":
    target = Path("hands-on/m02/src/domain/order_service.py")
    issues = inspect_layer_purity(target)
    if issues:
        print("[FAIL] Architectural Guardrail Violations Found:")
        for issue in issues:
            print(f"  -> {issue}")
        sys.exit(1)
    else:
        print("[SUCCESS] All layer purity checks passed.")
        sys.exit(0)
```

### File 3: Eksekusi Langkah Praktikum
Jalankan instruksi berikut di terminal Anda:
```bash
# 1. Jalankan AST Guardrail pada file yang melanggar
python hands-on/m02/rules/ast_guard.py

# Anda akan melihat output exit code 1 dan deteksi pelanggaran sqlite3.

# 2. Lakukan Refactoring Manual/Agentic:
# Pisahkan interface DB ke Domain Port (Abstract Base Class), 
# dan pindahkan implementasi sqlite3 ke hands-on/m02/src/infrastructure/sqlite_order_repo.py

# 3. Validasi Ulang
python hands-on/m02/rules/ast_guard.py
# Pastikan menghasilkan output: [SUCCESS] All layer purity checks passed.
```

---

## 13. Exercise

### Level Easy
Tuliskan AST visitor Python sederhana yang membatasi panjang baris suatu fungsi maksimal 50 baris dan mendeteksi apakah ada penggunaan kata kunci `eval()` atau `exec()` dalam file source code yang dihasilkan oleh agen AI.

### Level Medium
Bangun pre-commit hook bash script yang membaca `git diff --cached` dan secara otomatis memblokir file jika terdapat import sirkular (*circular dependency*) antar-package lokal menggunakan modul analyzer open-source.

### Level Hard
Rancang arsitektur pipeline GitHub Action lengkap yang:
1. Mengekstrak file yang berubah pada sebuah PR.
2. Memeriksa pelanggaran *Hexagonal Architecture*.
3. Jika ditemukan pelanggaran, memanggil OpenRouter/OpenAI API dengan temperature 0 untuk membuat patch `.diff`.
4. Mengunggah patch tersebut kembali ke branch PR sebagai commit baru bertanda `[bot-refactored]` dan memicu re-run test runner secara otomatis.

---

## 14. Challenge

### Studi Kasus: "The Distributed Monolith Trap"
**Konteks Masalah**: Perusahaan Anda memiliki monorepo dengan 20 microservices. Para engineer menggunakan AI coding tools secara agresif untuk mempercepat implementasi integrasi event-driven. Dalam 4 minggu, tim menemukan bahwa alih-alih menggunakan schema registry (Protobuf/Avro) secara konsisten, agen AI sering melakukan deserialisasi payload JSON secara *loose typed* langsung ke arbitrary dictionary atau map (`Map<String, Object>` / `dict[str, Any]`), mengabaikan schema validation.

**Tantangan**:
Rancang spesifikasi arsitektur teknis menyeluruh (lengkap dengan diagram komponen ASCII dan strategi AST validation engine) untuk mendeteksi dan menghentikan seluruh injeksi kode yang mengabaikan Schema Validation Registry tanpa memperlambat cycle time engineer. Solusi Anda harus mampu menangani 2 bahasa target (*Go* dan *TypeScript*) secara bersamaan di monorepo.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. **Apa perbedaan mendasar antara *syntactic correctness* dan *architectural compliance* pada kode yang dihasilkan AI?**  
   a. Syntactic correctness hanya untuk bahasa interpreter, arsitektur untuk bahasa kompilasi.  
   b. Syntactic correctness memastikan kode valid secara bahasa, architectural compliance memastikan batas modularitas dan aturan domain tidak dilanggar.  
   c. Syntactic correctness selalu memerlukan LLM, architectural compliance cukup menggunakan linter regular expression.  
   d. Tidak ada perbedaan semantik.

2. **Mengapa regex string matching tidak memadai untuk enforce architectural guardrail skala enterprise?**  
   a. Regex terlalu cepat sehingga membebani CPU runner.  
   b. Regex tidak memetakan konteks struktural (AST), seperti komentar kode, nested scope, atau variable shadowing.  
   c. Regex tidak didukung di sistem operasi Linux modern.  
   d. Format regex memakan token LLM terlalu besar.

3. **Komponen mana yang paling efisien diletakkan pada tier pertama (Layer 1) dalam guardrail pipeline?**  
   a. Autonomous LLM Agent dengan model multi-modal.  
   b. Manual Peer Review oleh Enterprise Architect.  
   c. Deterministic AST Linters & Static Boundary Checkers.  
   d. End-to-End Cypress integration test suites.

4. **Apa yang dimaksud dengan "Architectural Drift" dalam konteks Vibe-Coding?**  
   a. Kecepatan transfer data database yang menurun seiring waktu.  
   b. Erosi struktur desain sistem secara perlahan akibat ribuan baris kode AI yang di-merge tanpa memperhatikan keselarasan domain.  
   c. Ketidakcocokan versi driver CUDA pada mesin GPU inference.  
   d. Error timeout saat pemanggilan remote API.

5. **Apa fungsi utama dari Mutation Testing dalam guardrail refactoring otomatis?**  
   a. Menghapus kode yang tidak terpakai secara acak.  
   b. Menguji apakah test suite mampu mendeteksi mutasi logika buatan, mencegah agen AI melemahkan test assertion secara palsu.  
   c. Mempercepat kompilasi program dengan mengubah tipe data.  
   d. Mengenkripsi kode sebelum dikirim ke GitHub.

---

### Bagian 2: Intermediate (Pilihan Ganda)
6. **Dalam implementasi Clean Architecture, manakah dari statement import berikut yang merupakan pelanggaran kritis di layer Domain?**  
   a. `from abc import ABC, abstractmethod`  
   b. `from typing import Optional, List`  
   c. `from infrastructure.repositories.postgres import PostgresOrderRepository`  
   d. `from domain.entities.user import User`

7. **Kapan *Autonomous Self-Healing Loop* sebaiknya dihentikan oleh circuit breaker untuk mencegah kerugian finansial/operasional?**  
   a. Ketika waktu eksekusi melewati 500ms.  
   b. Setelah 2–3 iterasi berulang tanpa penyelesaian AST violations, atau jika token budget yang dialokasikan terlampaui.  
   c. Setiap kali compiler memberikan warning deprecation.  
   d. Ketika unit test menghasilkan coverage di atas 90%.

8. **Pendekatan manakah yang paling ideal untuk memberi konteks arsitektur sistem enterprise kepada Refactoring LLM Agent tanpa melampaui context window?**  
   a. Mengirimkan seluruh codebase monorepo (.zip) dalam setiap prompt.  
   b. RAG/AST extraction: Hanya menyuntikkan ADR relevan, symbol interface contracts yang terdampak, dan AST violation logs.  
   c. Menghapus semua unit test dari prompt agar prompt menjadi ringkas.  
   d. Meminta LLM menebak sendiri arsitekturnya tanpa petunjuk konteks.

9. **Apa risiko arsitektur terbesar jika developer melakukan *vibe-coding* dengan zero-touch review pada *Entity-Relationship Layer*?**  
   a. Ukuran font pada schema diagram menjadi tidak konsisten.  
   b. Munculnya antipola N+1 queries, unindexed foreign keys, dan hilangnya transactional boundaries.  
   c. Git commit history menjadi terlalu rapi.  
   d. Tidak ada risiko selama model LLM memiliki parameter di atas 70B.

10. **Metrik kuantitatif mana yang paling relevan dipantau di dashboard enterprise untuk mengukur akumulasi tech-debt hasil vibe-coding?**  
    a. Jumlah bintang (stars) repositori di GitHub.  
    b. Perubahan Cognitive Complexity per PR, Mutation Score, dan Churn Rate di Core Bounded Contexts.  
    c. Kecepatan mengetik developer (WPM) pada IDE.  
    d. Rasio file gambar PNG terhadap JPG dalam repositori.

---

### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus 1: Kontaminasi Data Access Object (DAO)**  
    Tim backend melaporkan bahwa selama 2 minggu sprint vibe-coding, 15 endpoint FastAPI baru yang di-generate AI langsung mengeksekusi RAW SQL strings di dalam router file, memotong Application Service Layer sepenuhnya. Bagaimana langkah remediation sistematis Anda tanpa menghentikan sprint feature development?
12. **Skenario Kasus 2: Dependency Inversion Hallucination**  
    Sebuah AI Coding Agent mencoba memperbaiki violation boundary dengan membuat interface abstraction dummy di dalam folder `/infrastructure`, kemudian mengimpor interface tersebut ke `/domain`. Analisis mengapa perbaikan ini salah secara arsitektural dan bagaimana merancang rule AST untuk mencegahnya!
13. **Skenario Kasus 3: Flaky Auto-Healing Loops**  
    Pipeline autonomous healing Anda menghasilkan infinite loop di PR #892: Model A memisahkan method menjadi 2 kelas baru untuk mengurangi kompleksitas, namun Model B (pada pipeline test berikutnya) menggabungkannya kembali karena menganggapnya premature abstraction. Bagaimana mekanisme anchoring rule-based yang harus dipasang untuk memutus loop determinasi ini?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Bagian 1 & 2
1. **b** | 2. **b** | 3. **c** | 4. **b** | 5. **b**  
6. **c** | 7. **b** | 8. **b** | 9. **b** | 10. **b**

#### Panduan Jawaban Kasus Produksi
11. **Solusi Skenario 1**:
    - **Step 1**: Pasang git pre-commit hook AST parser yang melarang modul `sqlite3`, `databases`, `psycopg2`, atau pemanggilan `.execute()` langsung di layer `/presentation` atau `/routers`.
    - **Step 2**: Jadikan pipeline fail-closed untuk PR baru yang melanggar.
    - **Step 3**: Untuk 15 endpoint existing, buat tiket refactoring otonom (batching): Jalankan Refactoring Agent dengan instruksi memisahkan RAW SQL ke dalam repository adapters di `/infrastructure` dan daftarkan kontrak antarmuka di `/domain`, dieksekusi secara otomatis per 3 endpoint per batch PR.
12. **Solusi Skenario 2**:
    - **Analisis**: Arah ketergantungan Clean Architecture adalah *Source Code Dependency* selalu mengarah ke dalam (menuju Domain). Jika domain mengimpor interface dari infrastructure, kontrol arsitektur terbalik dan domain tetap terikat pada lifecycle infrastructure. Interface (*Port*) WAJIB dimiliki dan berada di dalam layer Domain.
    - **Solusi AST Rule**: Buat aturan linting: *Layer Domain hanya boleh mengimpor modul dari Domain itu sendiri atau built-in primitives. Tidak ada file di path `/src/domain/*` yang diizinkan memiliki baris `from src.infrastructure.* import ...`*.
13. **Solusi Skenario 3**:
    - **Penyebab**: Fluktuasi evaluasi heuristik antar-model akibat ketiadaan *Canonical Architectural Benchmark*.
    - **Mekanisme Anchoring**:
      1. Terapkan metrik numerik kaku menggunakan tool deterministik (misal: Cognitive Complexity SonarQube < 10, Line of Code per method < 35 baris).
      2. LLM diinstruksikan hanya mengeksekusi refactoring ketika metrik deterministik terbukti merah.
      3. Jangan gunakan multi-agent LLM yang berbeda untuk saling mengoreksi gaya; jadikan linters deterministik sebagai *single source of truth* (judge akhir).

---

## 16. Summary

- **Vibe-coding** secara drastis meningkatkan kecepatan penulisan kode awal, tetapi berisiko melipatgandakan *technical debt* laten melalui erosi struktur arsitektur, kebocoran isolasi domain (*domain leaking*), dan pelemahan assertion testing.
- **Architectural Guardrails** tingkat produksi menerapkan filosofi pertahanan berlapis: memadukan kecepatan dan determinisme **AST Linters** di pre-commit/CI layer dengan kecerdasan semantik **Autonomous AI Agents** untuk pemulihan mandiri (*self-healing*).
- **Domain-Driven Design (DDD)** dan **Clean Architecture** adalah kompas utama vibe-coding: batas layer tidak boleh dikompromikan oleh kenyamanan integrasi instan model AI.
- Penggunaan alat otomatis harus selalu dilengkapi dengan mekanisme pengaman (*circuit breakers*, budget token limit, mutation testing verification) guna mencegah terciptanya *distributed monolith* dan regresi tak terdeteksi pada sistem skala enterprise.