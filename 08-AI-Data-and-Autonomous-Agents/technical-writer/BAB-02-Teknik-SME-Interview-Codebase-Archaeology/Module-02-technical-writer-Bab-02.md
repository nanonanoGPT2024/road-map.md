# Kurikulum Enterprise: AI, Data, and Autonomous Agents
## Bab 02: Teknik SME Interview & Codebase Archaeology
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
*   Menganalisis sistem perangkat lunak legasi (*monolith* maupun *microservices*) berbasis agen otonom dan pipeline data AI menggunakan teknik *Static Code Analysis* dan *AST (Abstract Syntax Tree) parsing* untuk merekonstruksi topologi sistem tanpa bergantung penuh pada ketersediaan Subject Matter Expert (SME).
*   Mengekstraksi *blast radius*, dependensi runtime, dan riwayat mutasi arsitektural melalui *Git archaeology* kuantitatif (churn metrics, co-change coupling analysis).
*   Merancang dan memfasilitasi wawancara SME berbasis data (*Code-Driven Inquiry Framework*) yang meminimalkan beban kognitif Principal/Staff Engineer hingga kurang dari 45 menit per siklus rilis mayor.
*   Mengembangkan *automated archaeology pipeline* yang mengekstrak metadata kode sumber, skema IO agen, dan dependensi tersembunyi menjadi dokumentasi *System Architecture Evolution* yang siap audit.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta harus menguasai:
*   **Pemrograman Lanjutan**: Pemahaman parsing sintaksis (AST manipulation di Python/TypeScript), navigasi pointer/referensi objek, dan pemrosesan stream.
*   **Internal Sistem Git**: Pemahaman struktur objek Git (`blobs`, `trees`, `commits`, `tags`), manipulasi `git rev-list`, `git log --raw`, serta perhitungan *code churn*.
*   **Arsitektur Sistem Terdistribusi & AI**: Pola orkestrasi agen (StateGraph, ReAct loop, message brokers seperti Kafka/RabbitMQ), vector index traversal, dan async execution contexts.
*   **Socio-Technical Pattern Recognition**: Pemahaman Hukum Conway (*Conway's Law*), degradasi dokumentasi (*software entropy*), dan pola coupling modular.

---

### 3. Concept & Internal Architecture (Mendalam)

Codebase Archaeology bukan sekadar membaca kode baris demi baris, melainkan proses forensik terhadap artefak kode untuk merekonstruksi model mental arsitek terdahulu. Dalam sistem AI terdistribusi dan agen otonom, kompleksitas meningkat karena aliran eksekusi bersifat non-deterministik dan state orchestration sering kali didefinisikan secara dinamis melalui prompt chains atau dependency injection.

```
+-----------------------------------------------------------------------------------+
|                         CODEBASE ARCHAEOLOGY PIPELINE                             |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  +--------------------+      +--------------------+      +---------------------+  |
|  | Git Commit History |      | Source Files (AST) |      | Runtime Telemetry   |  |
|  | (Churn / Coupling) |      | (Call Graphs/Defs) |      | (OpenTelemetry/APM) |  |
|  +---------+----------+      +---------+----------+      +----------+----------+  |
|            |                           |                            |             |
|            v                           v                            v             |
|  +-----------------------------------------------------------------------------+  |
|  |                  STATIC-DYNAMIC EXTRACTION ENGINE                           |  |
|  |  - Hotspot Mining (Tornhill Algorithm)                                      |  |
|  |  - Abstract Syntax Tree (AST) Type & Dependency Resolver                    |  |
|  |  - State Transition Graph Reconstruction (Agentic Nodes & Edges)           |  |
|  +-------------------------------------+---------------------------------------+  |
|                                        |                                          |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  |                 INTERMEDIATE ARCHITECTURAL REPRESENTATION                   |  |
|  |  - Topological Sort of Components                                          |  |
|  |  - Knowledge Gap Index (Identifikasi Area Minim Tes & High Churn)           |  |
|  |  - Tacit Knowledge Hypotheses (Daftar asumsi validasi teknis)               |  |
|  +-------------------------------------+---------------------------------------+  |
|                                        |                                          |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  |                    STRUCTURED SME ENGAGEMENT MATRIX                         |  |
|  |  - "Show, Don't Ask" Interviews (Validasi visual, bukan eksplorasi terbuka) |  |
|  |  - Canonical Architecture Decision Record (ADR) Auto-Scaffolding            |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

#### Komponen Internal Forensik
1.  **Temporal Coupling Engine**: Mendeteksi file-file yang sering berubah bersamaan (*co-change graph*) meskipun tidak memiliki dependensi statis eksplisit. Jika `agent_orchestrator.py` selalu di-commit bersamaan dengan `memory_store_redis.py`, terdapat coupling temporal yang harus didokumentasikan.
2.  **AST Signature Resolver**: Mengidentifikasi titik invokasi agen, deklarasi tool LLM, dan schema validation layer (misal: Pydantic v2 schemas) untuk memetakan kontrak data implisit.
3.  **Cognitive Interview Decoupler**: Mengubah hasil trace statis menjadi *targeted inquiry artifacts*. SME tidak pernah diajak duduk dengan pertanyaan umum seperti "Jelaskan cara kerja sistem ini", melainkan diverifikasi dengan "AST menunjukkan `WorkerAgent` mengabaikan timeout pada Redis callback; apakah ini *intentional architectural tradeoff* atau *known technical debt*?"

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise Codebase Archaeology |
| :--- | :--- | :--- |
| **Sumber Kebenaran** | Meminta SME mendikte dokumentasi dari memori. | Mengekstrak realitas dari git tree dan AST kode sumber; SME hanya memverifikasi. |
| **Efisiensi Waktu SME** | Wawancara 3-5 jam yang melelahkan dan sering dijadwal ulang. | Sesi 30 menit terfokus berbasis diagram hasil rekonstruksi kode. |
| **Akurasi Data** | Sering kali out-of-date karena memori SME bias ke arsitektur *ideal*. | 100% akurat terhadap apa yang sebenarnya berjalan di server produksi. |
| **Penanganan Legasi** | "Kode ini black-box, jangan sentuh kalau jalan." | Rekonstruksi dependensi, identifikasi technical debt dan blast radius secara deterministik. |

#### Mengapa Wawancara Konvensional Gagal pada Sistem AI Modern
Sistem AI berbasis agen (*Agentic Runtimes*) memiliki ribuan jalur eksekusi dinamis (*dynamic branching*). Jika Technical Writer mewawancarai Software Engineer tanpa data awal:
*   **Hindsight Bias**: Engineer cenderung menjelaskan apa yang *seharusnya* terjadi, bukan apa yang *saat ini* terimplementasi (misalnya: lupa menyebutkan fallback prompt darurat di file `helpers/utils.py`).
*   **Context Exhaustion**: Engineer tingkat Staff/Principal menghabiskan waktu mereka pada insiden arsitektur kritis; mereka mengalami kelelahan kognitif jika harus membedah detail implementasi trivial.

---

### 5. How (Workflow Detail)

Alur kerja investigasi teknis terbagi menjadi empat fase ketat:

```
[Fase 1: Reconnaissance] -> [Fase 2: AST Extraction] -> [Fase 3: Hypothesis Synthesis] -> [Fase 4: Targeted SME Sync]
```

#### Fase 1: Reconnaissance (Git Mining)
1. Eksekusi analisis churn untuk 180 hari terakhir: hitung baris yang dimodifikasi, ditambahkan, dan dihapus per file.
2. Identifikasi *God Objects* dan *Hotspots* (file dengan kompleksitas tinggi sekaligus churn rate tinggi).
3. Buat adjacency matrix dari commit history untuk melihat co-change coupling.

#### Fase 2: AST Extraction (Syntactic Excavation)
1. Jalankan script parser berbasis pohon sintaksis untuk membedah:
   * Class hierarchy dan inheritance.
   * Method signatures, return types, dan runtime parameter types.
   * Agent State Graph definitions (e.g., node registration, edge transitions, conditional routings).
2. Petakan tool execution payload dan external API dependencies.

#### Fase 3: Hypothesis Synthesis
1. Susun draf awal State Machine Diagram menggunakan Mermaid.js langsung dari hasil parsing AST.
2. Catat *anomaly points*:
   * Exception handling yang mengembalikan default silent (e.g., `except Exception: pass`).
   * Adanya konfigurasi `max_iterations` atau `recursion_limit` yang dimodifikasi di runtime.
   * Modul yang memiliki churn tinggi namun minim unit test coverage.

#### Fase 4: Targeted SME Sync (Wawancara Terstruktur)
1. Kirim dokumen *pre-read* maksimal 2 halaman berisi: Diagram hasil ekstraksi, 5 pertanyaan terarah berbasis file/baris spesifik, dan daftar asumsi arsitektur.
2. Eksekusi sesi wawancara berdurasi 30-45 menit. Gunakan teknik **"Confirm or Deny"**, bukan open-ended brainstorming.
3. Catat keputusan arsitektur (ADR) dan justifikasi teknis di balik setiap anomali yang ditemukan.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arkeologi Lapangan vs. Cerita Rakyat Penduduk Lokal
Mewawancarai SME tanpa membedah kode sama seperti seorang sejarawan yang hanya bertanya pada tetua desa tentang struktur benteng kuno yang terkubur. Cerita tetua desa diwarnai nostalgia, mitos, dan penyederhanaan. 
Sebaliknya, **Codebase Archaeology** adalah proses ekskavasi lapisan tanah (Git commits), menganalisis fondasi batu kapur (AST), dan mengukur sisa karbon (Runtime Telemetry). Wawancara SME adalah langkah terakhir: membawa artefak temuan ke tetua desa dan bertanya, *"Kami menemukan fondasi ini bergeser 30 derajat ke utara pada abad ke-17; apakah ini dirancang untuk pertahanan meriam atau karena tanah longsor?"*

```
GIT HISTORICAL STRATA (Lapisan Waktu)
========================================================================
[Head: v2.4]   --- Agen Multi-Turn + RAG Memory Injection
                 | (Tinggi Churn: memory_manager.py, edge_router.py)
------------------------------------------------------------------------
[Commit: v1.8] --- Perubahan Drastis: Migrasi LangChain -> Custom Engine
                 | (Arsitektur patah: Legacy tools ditinggalkan)
------------------------------------------------------------------------
[Commit: v1.0] --- Monolith MVC Awal
                 | (Fondasi: db/connection.py, base_agent.py)
========================================================================
                                |
                                v (AST Parsing & Diff Analysis)
+----------------------------------------------------------------------+
|                       TOPOLOGI ARSITEKTUR SEJATI                      |
|                                                                      |
|  +--------------------+        evaluates         +----------------+  |
|  | OrchestratorNode   | -----------------------> | PolicyEngine   |  |
|  +---------+----------+                          +-------+--------+  |
|            |                                             |           |
|            | calls dynamically                           | fallback  |
|            v                                             v           |
|  +--------------------+                          +----------------+  |
|  | SubAgentExecution  |                          | Deterministic  |  |
|  | (Retry Loops: x3)  |                          | Rule Set       |  |
|  +--------------------+                          +----------------+  |
+----------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Practical Production Example: Mining Agent State Machines via Python AST & Git Log
Skrip enterprise-grade berikut digunakan oleh Technical Writer/Document Engineer untuk:
1. Membaca repositori Python berbasis agen.
2. Mengekstrak graf transisi *StateGraph* secara otomatis.
3. Menghitung churn rate file tersebut untuk mempersiapkan lembar wawancara SME.

```python
#!/usr/bin/env python3
"""
Production-grade Codebase Archaeology Tool
Mengurai Abstract Syntax Tree (AST) untuk merekonstruksi graf agen
dan menghitung volatilitas repositori melalui git churn.
"""

import ast
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


@dataclass
class AgentNode:
    name: str
    handlers: List[str] = field(default_factory=list)


@dataclass
class AgentTransition:
    source: str
    target: str
    condition: str = "direct"


class AgentASTArchaeologist(ast.NodeVisitor):
    def __init__(self):
        self.nodes: Dict[str, AgentNode] = {}
        self.transitions: List[AgentTransition] = []
        self.current_function = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = None

    def visit_Call(self, node: ast.Call):
        # Deteksi penambahan node: graph.add_node("agent_name", func_handler)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "add_node":
            if len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
                node_name = node.args[0].value
                handler_name = ""
                if isinstance(node.args[1], ast.Name):
                    handler_name = node.args[1].id
                elif isinstance(node.args[1], ast.Attribute):
                    handler_name = f"{node.args[1].value}.{node.args[1].attr}"
                self.nodes[node_name] = AgentNode(name=node_name, handlers=[handler_name])

        # Deteksi penambahan direct edge: graph.add_edge("source", "target")
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "add_edge":
            if len(node.args) >= 2 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[1], ast.Constant):
                self.transitions.append(
                    AgentTransition(source=node.args[0].value, target=node.args[1].value, condition="unconditional")
                )

        # Deteksi conditional edge: graph.add_conditional_edges("source", condition_func, {map})
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "add_conditional_edges":
            if len(node.args) >= 3 and isinstance(node.args[0], ast.Constant):
                source = node.args[0].value
                cond_func = node.args[1].id if isinstance(node.args[1], ast.Name) else "dynamic_eval"
                if isinstance(node.args[2], ast.Dict):
                    for key, val in zip(node.args[2].keys, node.args[2].values):
                        target = val.value if isinstance(val, ast.Constant) else "unknown"
                        branch_val = key.value if isinstance(key, ast.Constant) else "condition"
                        self.transitions.append(
                            AgentTransition(
                                source=source, target=target, condition=f"{cond_func} == '{branch_val}'"
                            )
                        )
        self.generic_visit(node)


def calculate_git_churn(file_path: Path, days: int = 90) -> Tuple[int, int]:
    """Menghitung baris code churn (insertions, deletions) dari file tertentu."""
    cmd = [
        "git",
        "log",
        f"--since={days}.days",
        "--numstat",
        "--pretty=tformat:",
        "--",
        str(file_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    insertions = 0
    deletions = 0
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            insertions += int(parts[0])
            deletions += int(parts[1])
    return insertions, deletions


def generate_mermaid_markdown(archaeologist: AgentASTArchaeologist) -> str:
    """Mengubah temuan AST menjadi diagram status Mermaid."""
    lines = ["```mermaid", "stateDiagram-v2"]
    for trans in archaeologist.transitions:
        if trans.condition == "unconditional":
            lines.append(f"    {trans.source} --> {trans.target}")
        else:
            lines.append(f"    {trans.source} --> {trans.target}: {trans.condition}")
    lines.append("```")
    return "\n".join(lines)


# Execution Harness
if __name__ == "__main__":
    import tempfile

    mock_agent_code = '''
from langgraph.graph import StateGraph

def create_agent():
    builder = StateGraph()
    builder.add_node("classifier", classify_intent)
    builder.add_node("rag_worker", retrieve_and_generate)
    builder.add_node("action_worker", execute_tool_call)
    builder.add_node("human_fallback", human_in_the_loop)
    
    builder.add_edge("classifier", "rag_worker")
    builder.add_conditional_edges(
        "rag_worker",
        confidence_check,
        {
            "high": "action_worker",
            "low": "human_fallback"
        }
    )
    return builder.compile()
'''
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(mock_agent_code)
        temp_path = Path(f.name)

    try:
        tree = ast.parse(temp_path.read_text())
        archaeologist = AgentASTArchaeologist()
        archaeologist.visit(tree)

        print("=== RECONSTRUCTED AGENT GRAPH ===")
        print(f"Nodes found: {list(archaeologist.nodes.keys())}")
        for t in archaeologist.transitions:
            print(f"Transition: {t.source} -> {t.target} via [{t.condition}]")

        print("\n=== GENERATED MERMAID ARTIFACT ===")
        print(generate_mermaid_markdown(archaeologist))

    finally:
        temp_path.unlink()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Restrukturisasi Sistem Agen AI FinTech "Nexus-Pay" (Tier-1 Core Banking)
*   **Konteks**: Nexus-Pay memiliki sistem *Fraud Autonomous Investigation* yang dikembangkan selama 4 tahun oleh tim engineering awal yang telah 80% hengkang (*turnover* tinggi). Tim arsitek saat ini hanya mengetahui bahwa agen memproses transaksi mencurigakan, tetapi tidak ada yang berani memvalidasi logika eksekusi dinamisnya.
*   **Masalah Dokumentasi**: Sistem dokumentasi di Confluence menyebutkan sistem menggunakan "Sequential Rules Engine", namun metrik log runtime mengindikasikan adanya pemanggilan model LLM asinkronus yang menyebabkan pembengkakan biaya token sebesar $45,000/bulan tanpa jejak terdokumentasi.
*   **Intervensi Arkeologis**:
    1.  **Mining Git Blame & Commit Strata**: Technical Writer menganalisis 1,400 commit pada repositori `nexus-fraud-core`. Ditemukan satu commit siluman 8 bulan lalu berjudul `hotfix: emergency circuit breaker` yang dibuat langsung oleh VP Engineering saat itu. Commit ini menyisipkan dynamic vector retrieval sebelum transaksi dibatalkan.
    2.  **AST Semantic Parsing**: Memetakan dependency graph secara statis. Ditemukan modul terisolasi `shadow_evaluator.py` yang dieksekusi melalui dynamic reflection (`getattr(module, class_name)`).
    3.  **The 30-Minute Targeted SME Interview**: Technical Writer menyusun sesi bersama Principal Architect Nexus-Pay dengan membawa *Visual Call Graph* dan *Git Historical Trace*. 

```
AGENDA WAWANCARA TERFOKUS (30 MENIT)
-----------------------------------------------------------------------------
Menit 00-05: Verifikasi diagram AST (Konfirmasi topologi state machine).
Menit 05-15: Bedah baris kode 'shadow_evaluator.py': Mengapa fallback diarahkan 
             ke unmonitored OpenAI instance, bukan on-prem model?
Menit 15-25: Validasi Concurrency Blast Radius: Menentukan ketiadaan lock pada 
             saldo nasabah saat status agen "IN_REVIEW".
Menit 25-30: Penandatanganan ADR (Architecture Decision Record) rekonsiliasi.
```

*   **Hasil**: Technical Writer menghasilkan **Production ADR-042** dan dokumentasi topologi akurat dalam waktu 48 jam. Penghematan biaya komputasi sebesar $45,000/bulan langsung tercapai setelah tim engineering mematikan shadow pipeline yang ditemukan lewat ekskavasi tersebut.

---

### 9. Trade-offs

| Pendekatan Forensik | Keuntungan (Pros) | Biaya & Konsekuensi (Cons) | Metrik Trade-off |
| :--- | :--- | :--- | :--- |
| **Pure AST Static Analysis** | Cepat dieksekusi, aman dijalankan di local, tidak membutuhkan environment runtime aktif, zero compute cost. | Gagal memetakan dynamic runtime imports, conditional reflection, dan runtime monkey-patching. | Cakupan kode statis 100%, tetapi akurasi runtime dynamic flow hanya ~60-70%. |
| **Git Churn / Coupling Analysis** | Mengidentifikasi arsitektur sosial (*Socio-technical architecture*) dan dependensi tersembunyi antar file tanpa memahami sintaksis. | Rentan false positive jika ada *mass formatting* (misal: Prettier/Black run) atau commit renaming besar-besaran. | Sinyal coupling tinggi, namun membutuhkan filter ketat terhadap commit non-logis (refactor/whitespace). |
| **Dynamic Runtime Tracing (e.g., eBPF, OpenTelemetry)** | Akurasi mutlak terhadap alur eksekusi data yang benar-benar terjadi di produksi. | Memerlukan setup infrastruktur yang kompleks, observability cost, dan potensi degradasi performa (*latency overhead*). | Akurasi rekonstruksi 100%, latensi trace overhead naik 2-5% di production. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Antipatterns)
1.  **The Open-Ended Interview Trap**: Bertanya kepada SME: *"Bisa ceritakan high-level architecture sistem ini?"*
    *   *Gejala*: SME menghabiskan 40 menit menggambarkan kotak-kotak abstrak di papan tulis yang sudah usang sejak rilis 2 tahun lalu.
    *   *Koreksi*: Buka file sumber dan diff commit: *"Di file `orchestrator.ts` line 140, agen melempar timeout setelah 5000ms. Namun di level gateway limitnya 3000ms. Apakah ini disengaja?"*
2.  **Mengabaikan `git diff` Mass Changes**: Menghitung *file churn* tanpa memfilter commit format otomatis (Black, Prettier, Linter auto-fix). File tampak seperti hotspot arsitektur kritis padahal hanya terkena pergantian spasi/tab.
    *   *Koreksi*: Gunakan flag `--ignore-all-space` dan filter file konfigurasi linting dari agregator churn.
3.  **AST Traversal Blindness**: Mengasumsikan sebuah sistem agen dibangun secara linear padahal memanfaatkan decoupled queues (e.g., Celery, Kafka).
    *   *Koreksi*: Lakukan cross-reference antara method call AST dengan payload subscriber broker.

#### Panduan Troubleshooting Ekstraksi Kode
*   *Isu*: Parser AST Python melempar `SyntaxError` saat membaca file legacy.
    *   *Solusi*: Periksa versi target Python. Gunakan modul parser multi-versi seperti `parso` atau lib standar `ast` dengan target `feature_version=(3, 8)`.
*   *Isu*: SME bersikap defensif saat ditanya mengenai dead-code atau bug arsitektural.
    *   *Solusi*: Gunakan teknik *Blameless Technical Inquest*. Jangan gunakan kata "Mengapa Anda menulis kode ini?", gunakan "Kondisi operasional apa yang memaksa arsitektur ini mengambil trade-off performa tersebut?"

---

### 11. Best Practices (Production Checklist)

#### Pre-Interview Archaeological Checklist
- [ ] Churn analysis dijalankan pada repositori target minimal periode 90 hari terakhir.
- [ ] 5 Hotspot files teratas telah diisolasi dan di-diff secara manual.
- [ ] AST parsing telah memetakan minimal: Titik masuk (Entrypoints), Objek Status Agen, dan External IO.
- [ ] Structural Diagram (Mermaid atau PlantUML) telah digenerate secara otomatis dari kode.
- [ ] Daftar "Tanya SME" dibatasi maksimal 5 pertanyaan biner atau resolusi konflik kode.

#### Post-Interview Documentation Standard
- [ ] ADR (Architecture Decision Record) terbit mencantumkan *Context, Decision, Status,* dan *Consequences*.
- [ ] Komponen legacy diberi label status: `Active`, `Deprecated`, atau `Volatile`.
- [ ] Link eksplisit antara commit hash fondasi dengan blok dokumentasi terkait.
- [ ] Logika fallback agen didokumentasikan dengan tabel failure modes dan mitigasinya.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

#### Langkah 1: Persiapan Environment
```bash
mkdir -p hands-on/m02/target_repo
cd hands-on/m02/
python3 -m venv venv
source venv/bin/activate
pip install gitpython tabulate
```

#### Langkah 2: Setup Mock Legacy Codebase
Buat file `hands-on/m02/setup_repo.sh` untuk mensimulasikan riwayat commit repositori agen:
```bash
#!/usr/bin/env bash
set -e
mkdir -p target_repo
cd target_repo
git init -b main

# Commit 1: Genesis
cat << 'EOF' > agent_core.py
class CoreAutonomousWorker:
    def __init__(self):
        self.state = "IDLE"

    def execute_task(self, task):
        print(f"Executing: {task}")
        self.state = "DONE"
EOF
git add .
git commit -m "feat: initial commit core agent"

# Commit 2: Architectural Hotfix (Technical Debt Injection)
cat << 'EOF' > agent_core.py
class CoreAutonomousWorker:
    def __init__(self):
        self.state = "IDLE"
        self.legacy_cache = {}

    def execute_task(self, task):
        # SME HOTFIX: Bypass validation under heavy load
        if len(task) > 10:
            self.legacy_cache[task] = True
            self.state = "FAST_TRACK"
            return
        print(f"Executing: {task}")
        self.state = "DONE"
EOF
git add .
git commit -m "fix(core): inject fast-track route for heavy tasks"
```
Eksekusi:
```bash
chmod +x setup_repo.sh
./setup_repo.sh
```

#### Langkah 3: Implementasi Excavator Script
Buat file `hands-on/m02/excavate.py`:
```python
#!/usr/bin/env python3
import ast
import os
import sys
from git import Repo
from tabulate import tabulate

def audit_file(repo_path, file_name):
    repo = Repo(repo_path)
    file_full_path = os.path.join(repo_path, file_name)
    
    print(f"\n[+] Excavating History for: {file_name}")
    commits = list(repo.iter_commits(paths=file_name))
    print(f"Total mutations (commits): {len(commits)}")
    
    with open(file_full_path, "r") as f:
        tree = ast.parse(f.read())
        
    methods_found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            methods_found.append([node.name, node.lineno, len(node.body)])
            
    print("\n[+] AST Structure (Discovered Components):")
    print(tabulate(methods_found, headers=["Method Name", "Start Line", "Statement Count"], tablefmt="github"))
    
    print("\n[+] Commit Strata Forensics:")
    history_table = [[c.hexsha[:7], c.author.name, c.message.strip()] for c in commits]
    print(tabulate(history_table, headers=["SHA", "Author", "Commit Message"], tablefmt="github"))

if __name__ == "__main__":
    audit_file("./target_repo", "agent_core.py")
```
Jalankan audit:
```bash
python excavate.py
```

---

### 13. Exercise

#### Level Easy
Ekstrak daftar dependensi pihak ketiga (`import` dan `from ... import ...`) dari file target Python menggunakan AST visitor, kemudian cetak daftar pustaka tersebut dalam bentuk Markdown checklist.

#### Level Medium
Buat skrip forensik Git yang mengekstrak metadata dari commit message:
*   Mendeteksi commit yang mengandung kata kunci darurat: `hotfix`, `revert`, `workaround`, `hack`.
*   Menghitung file mana saja yang paling sering terkena commit kategori ini untuk dijadikan kandidat utama wawancara SME.

#### Level Hard
Buat parser AST terintegrasi yang mampu mendeteksi panggilan fungsi recursive atau nested execution loops pada file definisi agen otonom. Skrip harus mengekstrak:
1. Nama fungsi/node agen.
2. Kondisi termination boundary (misalnya keberadaan check `iteration > MAX_LIMIT`).
3. Menghasilkan warning flag jika loop eksekusi tidak memiliki batas iterasi deterministik (potensi *infinite token burn bug*).

---

### 14. Challenge

#### Skenario Kasus Arkeologi Arsitektur Kompleks
Anda masuk ke dalam tim engineering yang mengelola platform multi-agen terdistribusi untuk diagnosis medis otomatis (*Autonomous Diagnostic Pipeline*). Arsitek utama telah meninggalkan perusahaan tanpa dokumentasi sama sekali.
*   **Kondisi Repositori**: Terdapat 4 service (`orchestrator`, `vision_agent`, `ehr_agent`, `billing_agent`), masing-masing di direktori mono-repo terpisah dengan total 280,000 baris kode.
*   **Isu Produksi**: Pasien dengan histori medis kompleks terkadang menerima tagihan ganda atau hasil review agen tertahan pada state `PENDING` selamanya.
*   **Tantangan**:
    1.  Rancang arsitektur pipeline otomatis (gunakan script bash/Python) untuk membedah seluruh event router di ke-4 service tersebut.
    2.  Petakan alur pertukaran pesan antar service tanpa mengeksekusi kode di cloud (hanya menggunakan static analysis pada schema event/Pydantic).
    3.  Tulis satu dokumen **Architectural Recovery Dossier** maksimal 3 halaman yang membuktikan secara teknis di baris file mana `PENDING deadlock` terjadi.
    4.  Siapkan matriks pertanyaan wawancara untuk Staff Engineer yang tersisa yang hanya memiliki slot waktu 20 menit pada kalendernya.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1.  Apa perbedaan mendasar antara representasi kode melalui Plain Text/Regex Search dibandingkan dengan memparsing melalui Abstract Syntax Tree (AST)?
2.  Mengapa metrik *code churn* lebih relevan dibandingkan metrik *Lines of Code (LoC)* dalam memprioritaskan area yang membutuhkan dokumentasi teknis mendalam?
3.  Apa yang dimaksud dengan *co-change coupling* dalam analisa temporal git history?
4.  Sebutkan dua alasan mengapa format pertanyaan open-ended (*"Bagaimana cara kerja modul ini?"*) tidak efektif saat mewawancarai Staff/Principal Engineer!
5.  Apa fungsi utama dari diagram transisi status (State Machine Diagram) dalam dokumentasi sistem AI berbasis agen otonom?

#### Intermediate Questions
1.  Bagaimana cara mendeteksi via AST ketika sebuah fungsi Python menggunakan *implicit dynamic execution* (reflection) yang berpotensi menyembunyikan dependensi arsitektur?
2.  Dalam konteks socio-technical pattern, apa arti dari sebuah file arsitektur inti (*core module*) yang memiliki frekuensi commit tinggi oleh lebih dari 15 developer berbeda dalam 30 hari?
3.  Bagaimana strategi merumuskan hipotesis arsitektur saat menemukan blok kode dengan exception handling pasif:
    ```python
    try:
        agent.dispatch_autonomous_event(context)
    except Exception:
        logger.debug("Dispatch failed, moving to silent fallback")
    ```
4.  Apa limitasi utama dari *Static Code Analysis* ketika diterapkan pada framework agen modern yang mengonstruksi alur kerjanya melalui DSL runtime (seperti file konfigurasi YAML atau Prompt template eksternal)?
5.  Sebutkan parameter apa saja yang harus ada dalam sebuah *Targeted Pre-Interview Dossier* agar wawancara SME tidak melebihi alokasi waktu 30 menit!

#### Skenario Kasus Produksi
1.  **Skenario A**: Tim Anda menemukan inkonsistensi data antara database Redis (Short-Term Agent Memory) dan PostgreSQL (Canonical Patient Record). Riwayat git commit menunjukkan file `memory_synchronizer.py` tidak pernah disentuh selama 14 bulan, namun issue tracking penuh dengan komplain data drift. Pendekatan arkeologi apa yang harus Anda lakukan untuk membongkar akar masalah sebelum menjadwalkan sinkronisasi dengan Tech Lead?
2.  **Skenario B**: Seorang Staff Engineer menolak hadir dalam sesi interview arsitektur dengan alasan: *"Kodenya sudah self-explanatory, baca saja sendiri di repo."* Bagaimana Anda mendemonstrasikan hasil ekskavasi teknis Anda untuk membalikkan penolakan tersebut menjadi sesi review tingkat tinggi yang produktif?
3.  **Skenario C**: Pada pipeline LLM multi-agen, AST analisis menunjukkan adanya siklus transisi siklik (*cyclic dependency graph*) antara `ValidationAgent` dan `RefinementAgent`. Namun di log produksi, agen tidak pernah crash melainkan mengalami termination tiba-tiba. Pertanyaan forensik spesifik apa yang harus Anda persiapkan untuk diajukan kepada Lead AI Engineer?

---

### 16. Summary

*   **Codebase Archaeology** adalah fondasi objektif dalam technical writing enterprise. Dokumentasi yang akurat tidak bersumber dari ingatan manusia yang bias, melainkan dari data konkret: Git metadata, pohon sintaksis (AST), dan kontrak antarmuka kode sumber.
*   Wawancara dengan SME bukan merupakan sarana eksplorasi awal, melainkan forum verifikasi tahap akhir. Dengan mengotomatisasi ekstraksi struktur via tooling statis, Technical Writer mentransformasikan interaksi bersama Principal Engineer dari sesi pengajaran yang melelahkan menjadi sesi peninjauan arsitektur terfokus dan bernilai tinggi.
*   Pemahaman mendalam terhadap trade-off implementasi, blast radius, dan teknik forensik repositori menjamin dokumentasi sistem AI otonom tetap relevan, tahan audit, dan mampu memandu keputusan rekayasa perangkat lunak jangka panjang.