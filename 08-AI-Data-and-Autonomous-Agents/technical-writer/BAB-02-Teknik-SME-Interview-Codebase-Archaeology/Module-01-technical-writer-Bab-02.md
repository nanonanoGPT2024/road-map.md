# Bab 02: Teknik SME Interview & Codebase Archaeology

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

*   **Mengonstruksi Peta Topologi Kode Mandiri (Independent Code Topography Mapping):** Melakukan ekstraksi arsitektur, dependensi state, dan graph alur eksekusi dari codebase agen otonom dan pipeline AI (*multi-agent systems*, LLM orchestrator) menggunakan teknik static Abstract Syntax Tree (AST) analysis dan dynamic trace inspection tanpa bergantung pada dokumentasi awal.
*   **Melakukan Git Forensics & Blame Heatmap Analysis:** Mengidentifikasi Subject Matter Expert (SME) yang tepat melalui kuantifikasi metrik *code churn*, kepemilikan commit modular, dan riwayat resolusi *pull request* (PR) teknis tingkat rendah.
*   **Merancang Protokol Wawancara SME Berbasis Bukti (Evidence-Based SME Interviewing):** Mengembangkan instrumen wawancara semi-terstruktur yang berfokus pada *edge cases*, batasan stokastik, fallback deterministik, dan keputusan desain implisit menggunakan artefak kode sebagai jangkar diskusi (*anchor artifacts*).
*   **Merekonsiliasi Diskrepansi Mental Model vs. Implementasi Kode:** Mengidentifikasi dan memitigasi fenomena *hallucinated architecture*—situasi di mana pemahaman arsitektur oleh engineer/peneliti AI berbeda secara fundamental dari kode yang aktif berjalan di *production environment*.
*   **Memproduksi Architecture Decision Records (ADR) & Living Runbooks:** Mengonversi data mentah hasil arkeologi dan transkrip wawancara SME menjadi dokumentasi teknis sistematis, terverifikasi, dan siap audit enterprise.

---

## 2. Concept Overview

Dalam ekosistem rekayasa AI, Data, dan Autonomous Agents, kesenjangan antara apa yang didesain (mental model engineer) dan apa yang terpasang di *production* (implementasi kode aktual) bergerak lebih cepat dibandingkan domain rekayasa perangkat lunak tradisional. Sifat stokastik model fondasi (*foundation models*), orkestrasi dinamis berbasis agen (seperti LangGraph, AutoGen, CrewAI), serta runtime logic yang dieksekusi secara non-deterministik menuntut pendekatan dokumentasi tingkat lanjut: **Arkeologi Codebase (Codebase Archaeology)** yang dipadukan secara simbiotik dengan **Wawancara SME Berbasis Bukti (Evidence-Based SME Interviewing)**.

```
+-------------------------------------------------------------------------+
|                  THE ARCHAEOLOGIST-JOURNALIST DUAL LOOP                 |
+-------------------------------------------------------------------------+
|                                                                         |
|   PHASE 1: ARCHEOLOGY                     PHASE 2: SME INTERVIEW        |
|  +--------------------+                  +-----------------------+      |
|  | AST Analysis &     |                  | Question Formulation  |      |
|  | State Extraction   |                  | (Anchored to Lines)   |      |
|  +---------+----------+                  +-----------+-----------+      |
|            |                                         |                  |
|            v                                         v                  |
|  +--------------------+  Triangulation   +-----------------------+      |
|  | Git Forensics &    +----------------->| Semi-Structured       |      |
|  | Churn Analytics    |   Discrepancy    | Technical Interview   |      |
|  +---------+----------+      Search      +-----------+-----------+      |
|            |                                         |                  |
|            v                                         v                  |
|  +--------------------+                  +-----------------------+      |
|  | Dynamic Trace      |                  | Transcript Synthesis  |      |
|  | Inspection (Otel)  |                  | & Edge-Case Mapping   |      |
|  +--------------------+                  +-----------------------+      |
|            \                                        /                   |
|             \                                      /                    |
|              v                                    v                     |
|           +------------------------------------------+                  |
|           |   VERIFIED ENTERPRISE TECHNICAL SPEC     |                  |
|           +------------------------------------------+                  |
|                                                                         |
+-------------------------------------------------------------------------+
```

### Mental Model: The Archaeologist-Journalist Protocol

Technical Writer pada tier Principal/Staff tidak bertindak sebagai pencatat pasif (*stenographer*). Anda beroperasi dalam dua mode kognitif:
1.  **Arkeolog Perangkat Lunak:** Membedah lapisan stratum commit, repositori, dependensi library, file konfigurasi YAML, trace OpenTelemetry, dan AST dari kode sumber untuk merekonstruksi fakta fisik sistem. Arkeolog mempercayai kode di atas kata-kata, karena *code is the single source of truth for runtime behavior*.
2.  **Jurnalis Investigatif Teknis:** Menghadapi SME (AI Research Scientist, MLOps Platform Engineer, Distributed Systems Architect) bukan untuk bertanya *"Bagaimana sistem ini bekerja?"*, melainkan *"Mengapa state graph memilih conditional edge ke node fallback pada baris 142 ketika validasi schema Pydantic gagal, dan apa implikasinya terhadap context window overhead?"*.

### Dinamika SME dalam Rekayasa AI

SME di domain AI/Agentic systems menghadapi bias kognitif sistemik yang disebut *Curse of Knowledge*. Mereka sering mengasumsikan bahwa:
*   Mekanisme penanganan kegagalan (*failure modes*) seperti *context window saturation*, *tool call hallucination*, dan *infinite loop routing* adalah "pengetahuan umum".
*   Parameter hiper-kritis (seperti `temperature=0.0`, `max_tokens`, `frequency_penalty`, dan `retry_backoff_factor`) telah terkonfigurasi secara seragam di seluruh cluster, padahal sering kali di-override secara *ad-hoc* di sub-modul downstream.
*   Prompt chains dan tool-calling definitions yang terdaftar pada metadata dianggap selalu deterministik.

Misi Anda adalah mengekstrak realitas operasional implisit ini dan membawanya ke ranah eksplisit, terstruktur, dan terdokumentasi.

---

## 3. Why It Matters

Di lingkungan enterprise yang mengadopsi otonomi AI, dokumentasi yang salah atau tidak lengkap membawa risiko finansial, operasional, dan kepatuhan yang nyata:

1.  **Drift Arsitektur dan Cognitive Debt:** Ketika tim riset AI menyerahkan model atau agent loop ke tim engineering produksi tanpa dokumentasi yang membedah *state transitions*, tim operasional dipaksa memperlakukan sistem sebagai *black box*. Hal ini melipatgandakan *Mean Time To Detect (MTTD)* dan *Mean Time To Recover (MTTR)* ketika agentic loop terjebak dalam *infinite recursive tool invocation*.
2.  **Mitigasi Kegagalan Audit Kepatuhan (Compliance Failure):** Regulasi seperti *EU AI Act* dan standar *SOC2 Type II / ISO 42001* menuntut transparansi menyeluruh atas sistem pengambilan keputusan otonom. Dokumentasi teknis harus mampu merekonstruksi:
    *   Jalur eksekusi deterministik vs non-deterministik.
    *   Mekanisme isolasi *tool execution* (sandboxing).
    *   Struktur *system prompt injection mitigations*.
3.  **Efisiensi Kapasitas Engineering:** Waktu seorang Staff AI Engineer berkisar antara $250 - $450/jam. Menghabiskan waktu SME dengan pertanyaan mendasar seperti *"Bisa jelaskan arsitektur folder ini?"* adalah pemborosan modal enterprise. Codebase archaeology mereduksi waktu wawancara hingga 75%, menggeser interaksi menjadi validasi presisi tinggi selama 30 menit.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut memetakan alur kerja terpadu untuk melakukan arkeologi codebase agen otonom, analisis forensik kontributor, ekstraksi topologi state machine, hingga wawancara SME dan verifikasi final.

```
+---------------------------------------------------------------------------------------------------------+
| PIPELINE ARKEOLOGI CODEBASE & REKONSILIASI SME                                                         |
+---------------------------------------------------------------------------------------------------------+
                                                                                                           
 [Code Repository: AI Agentic Core]                                                                        
       |                                                                                                   
       +---> [Git Forensics Engine]                                                                        
       |        |-- Commit Churn Analysis (pygit2 / GitPython)                                             
       |        |-- Entropy Scoring per Module                                                             
       |        +-- Blame Heatmap Extraction ---> [Targeted SME Identity: Top 2 Engineers]                
       |                                                                                                   
       +---> [AST & Call Graph Engine]                                                                     
       |        |-- Pydantic Schema Parsing (State Model)                                                  
       |        |-- Decorator Identification (@tool, @agent)                                               
       |        +-- StateGraph Cyclic Route Detection ---> [Archaeological Graph Map]                     
       |                                                               |                                   
       +---> [Dynamic Observability Traces]                            |                                   
                |-- OTel Spans (Agent Execution Loop)                  v                                   
                +-- Token Consumption & Fallbacks ----> [Discrepancy Matrix: Code vs Docs]                 
                                                                       |                                   
                                                                       v                                   
                                                      +----------------------------------+                 
                                                      | SME Interview Preparation Pack   |                 
                                                      | - Line-Anchored Code Questions   |                 
                                                      | - Edge-Case Trace Scenarios      |                 
                                                      | - State Transition Discrepancies |                 
                                                      +----------------+-----------------+                 
                                                                       |                                   
                                                                       v                                   
                                                      +----------------------------------+                 
                                                      | SME Semi-Structured Interview    |                 
                                                      | (Evidence-Based Deep Dive)       |                 
                                                      +----------------+-----------------+                 
                                                                       |                                   
                                                                       v                                   
                                                      +----------------------------------+                 
                                                      | Triangulation & Verification     |                 
                                                      | - Code Patch Comparison          |                 
                                                      | - Error Boundary Re-test         |                 
                                                      +----------------+-----------------+                 
                                                                       |                                   
                                                                       v                                   
                                                      +----------------------------------+                 
                                                      | Output Deliverables:             |                 
                                                      | 1. Verified Architecture Spec    |                 
                                                      | 2. Agent State Graph Runbook     |                 
                                                      | 3. Architecture Decision Records |                 
                                                      +----------------------------------+                 
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Codebase Archaeology: Static AST & Semantic Inspection

Arkeologi kode dimulai dengan parsing statis menggunakan Abstract Syntax Tree (AST). Pada sistem agen modern (misalnya berbasis LangGraph, AutoGen, LlamaIndex), orkestrasi berpusat pada tiga komponen fisik kode:

1.  **State Schema Declaration:** Representasi status memori yang dialirkan antar node. Ini umumnya didefinisikan via `Pydantic` atau `typing.TypedDict`. Mengidentifikasi properti `Union`, `Optional`, dan mutasi state adalah kunci untuk memahami alur informasi.
2.  **Tool Definitions:** Fungsi yang didekorasi (`@tool`, `@kernel_function`). Arkeolog harus mengekstrak skema argumen, docstrings, dan apakah eksekusi memicu *I/O network calls* atau komputasi lokal.
3.  **Graph Routing Logic:** Identifikasi edge kondisional (*conditional edges*). Edge ini menentukan percabangan berbasis token output model. Analisis AST mengekstrak logika percabangan deterministik yang membungkus keputusan model stokastik.

### 5.2 Git Forensics: Churn vs. Ownership Heatmap

Menentukan SME tidak dapat dilakukan hanya dengan melihat siapa yang membuat commit pertama (*initial commit*). Tim enterprise menggunakan formula **Code Ownership Churn** untuk menghitung bobot relevansi kontributor:

$$\text{SME Score} = \sum_{c \in C} \left( \frac{\text{Lines Added}_c + \text{Lines Deleted}_c}{\Delta t_c + 1} \right) \times W_{\text{type}}$$

Dimana:
*   $C$ adalah himpunan commit pada modul agen tertentu dalam rentang waktu $T$ (misal: 90 hari terakhir).
*   $\Delta t_c$ adalah usia commit dalam bulan.
*   $W_{\text{type}}$ adalah bobot commit: commit logika agen inti memiliki bobot lebih tinggi ($W=1.0$) dibanding commit refaktor linting/formatting ($W=0.1$).

Engineer dengan skor tertinggi adalah SME utama untuk wawancara teknis tingkat lanjut, bukan manajer atau lead yang hanya me-review PR.

### 5.3 Evidence-Based SME Interview Protocol: The 4-Tier Querying System

Teknik wawancara terstruktur dibagi ke dalam 4 layer pertanyaan:

| Layer | Kategori | Fokus Kueri | Contoh Frasa Penyelidikan |
| :--- | :--- | :--- | :--- |
| **L1** | **Topologi & Invarian** | Batasan struktural yang tidak boleh dilanggar. | *"Saya melihat pada `AgentState` bahwa `memory_context` diinisialisasi sebagai append-only list. Apa kondisi yang memicu pemangkasan (pruning) array ini sebelum saturasi window tercapai?"* |
| **L2** | **Boundary & Failure Modes** | Penanganan kegagalan stokastik & deterministik. | *"Ketika LLM mengembalikan malformed JSON yang gagal di-parse oleh validator Pydantic pada baris 88, fallback mechanism langsung beralih ke `HumanInTheLoopNode` atau melakukan self-correction retry?"* |
| **L3** | **Degradasi & Concurrency** | Performa di bawah tekanan sistem terdistribusi. | *"Bagaimana locking mechanism menangani dua agent worker konkuren yang memodifikasi state graph session yang sama secara bersamaan?"* |
| **L4** | **Decisions & Trade-offs** | Alasan historis di balik desain kode tak lazim. | *"Terdapat implementasi custom LRU Cache untuk embeddings alih-alih memanfaatkan Redis di `retrieval_node.py`. Trade-off apa yang dipertimbangkan saat keputusan ini dibuat?"* |

---

## 6. Production-Ready Code Implementation

Berikut adalah script otomasi produksi menggunakan Python 3.11+ yang mengintegrasikan AST parsing dan Git forensics. Script ini mengekstrak definisi state, tools yang didekorasi, mendeteksi conditional routing, menganalisis git churn untuk menemukan SME modul, dan menghasilkan *SME Interview Briefing Dossier*.

```python
#!/usr/bin/env python3
"""
Agentic Codebase Archaeologist & SME Discovery Engine.
Analyzes Python repositories powering AI Agents to extract AST architecture,
detect routing mechanics, and identify module SMEs via Git forensics.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Archaeologist")


@dataclass
class ToolDefinition:
    name: str
    args: List[str]
    docstring: Optional[str]
    lineno: int
    is_async: bool


@dataclass
class StateDefinition:
    name: str
    fields: Dict[str, str]
    lineno: int


@dataclass
class SMEProfile:
    author_name: str
    author_email: str
    commit_count: int
    lines_changed: int
    last_active: datetime


@dataclass
class ModuleArcheologyReport:
    file_path: str
    states: List[StateDefinition] = field(default_factory=list)
    tools: List[ToolDefinition] = field(default_factory=list)
    conditional_edges: List[str] = field(default_factory=list)
    top_smes: List[SMEProfile] = field(default_factory=list)
    unhandled_exceptions: List[str] = field(default_factory=list)


class AgentASTVisitor(ast.NodeVisitor):
    """Parses Python AST for Agent components: State models, decorated tools, and routing."""

    def __init__(self) -> None:
        self.states: List[StateDefinition] = []
        self.tools: List[ToolDefinition] = []
        self.conditional_edges: List[str] = []
        self.unhandled_exceptions: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # Deteksi State Graph Schema (misal: Pydantic BaseModel atau TypedDict)
        is_state = any(
            (isinstance(b, ast.Name) and b.id in {"BaseModel", "TypedDict", "AgentState"})
            or (isinstance(b, ast.Attribute) and b.attr in {"BaseModel", "TypedDict"})
            for b in node.bases
        )

        if is_state:
            fields: Dict[str, str] = {}
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    type_str = ast.unparse(item.annotation)
                    fields[item.target.id] = type_str

            self.states.append(
                StateDefinition(
                    name=node.name,
                    fields=fields,
                    lineno=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._analyze_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._analyze_function(node, is_async=True)
        self.generic_visit(node)

    def _analyze_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        is_tool = False
        for decorator in node.decorator_list:
            dec_id = ""
            if isinstance(decorator, ast.Name):
                dec_id = decorator.id
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    dec_id = decorator.func.id
                elif isinstance(decorator.func, ast.Attribute):
                    dec_id = decorator.func.attr
            if "tool" in dec_id.lower() or "action" in dec_id.lower():
                is_tool = True
                break

        if is_tool:
            args = [arg.arg for arg in node.args.args if arg.arg != "self"]
            docstring = ast.get_docstring(node)
            self.tools.append(
                ToolDefinition(
                    name=node.name,
                    args=args,
                    docstring=docstring,
                    lineno=node.lineno,
                    is_async=is_async,
                )
            )

    def visit_Call(self, node: ast.Call) -> None:
        # Deteksi conditional edge registration (misal: add_conditional_edges)
        func_name = ""
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        if "conditional_edge" in func_name.lower():
            self.conditional_edges.append(f"Line {node.lineno}: {ast.unparse(node)}")

        self.generic_visit(node)


class GitForensicsEngine:
    """Executes Git analysis to locate real SMEs based on churn metrics."""

    @staticmethod
    def extract_module_smes(repo_path: Path, relative_file_path: str, max_history_days: int = 180) -> List[SMEProfile]:
        try:
            # Format: AuthorName|AuthorEmail|CommitDateUnix
            cmd = [
                "git",
                "-C",
                str(repo_path),
                "log",
                f"--since={max_history_days}.days",
                "--numstat",
                "--pretty=format:COMMIT|%an|%ae|%at",
                "--",
                relative_file_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error("Failed to execute git command on %s: %s", relative_file_path, e)
            return []

        author_stats: Dict[str, Dict[str, Any]] = {}

        current_author: Optional[str] = None
        current_email: Optional[str] = None
        current_timestamp: Optional[int] = None

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("COMMIT|"):
                parts = line.split("|")
                current_author = parts[1]
                current_email = parts[2]
                current_timestamp = int(parts[3])

                if current_email not in author_stats:
                    author_stats[current_email] = {
                        "name": current_author,
                        "email": current_email,
                        "commits": 0,
                        "lines_changed": 0,
                        "last_active": current_timestamp,
                    }
                author_stats[current_email]["commits"] += 1
                if current_timestamp > author_stats[current_email]["last_active"]:
                    author_stats[current_email]["last_active"] = current_timestamp

            elif current_email and line[0].isdigit():
                stats = line.split()
                if len(stats) >= 2 and stats[0].isdigit() and stats[1].isdigit():
                    added = int(stats[0])
                    deleted = int(stats[1])
                    author_stats[current_email]["lines_changed"] += (added + deleted)

        smes: List[SMEProfile] = []
        for email, data in author_stats.items():
            smes.append(
                SMEProfile(
                    author_name=data["name"],
                    author_email=email,
                    commit_count=data["commits"],
                    lines_changed=data["lines_changed"],
                    last_active=datetime.fromtimestamp(data["last_active"], tz=timezone.utc),
                )
            )

        # Urutkan berdasarkan weighted impact: lines_changed * 0.4 + commit_count * 0.6
        smes.sort(key=lambda s: (s.commit_count * 0.6) + (s.lines_changed * 0.4), reverse=True)
        return smes[:3]


class CodeArchaeologyPipeline:
    """Orchestrates AST parsing and Git Forensics to build SME interview briefs."""

    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Path {self.repo_path} is not a valid Git repository root.")

    def run_archeology(self, target_rel_path: str) -> ModuleArcheologyReport:
        absolute_path = self.repo_path / target_rel_path
        if not absolute_path.exists():
            raise FileNotFoundError(f"Source file {absolute_path} not found.")

        logger.info("Decompiling AST for: %s", target_rel_path)
        with open(absolute_path, "r", encoding="utf-8") as f:
            code_content = f.read()

        parsed_ast = ast.parse(code_content, filename=target_rel_path)
        visitor = AgentASTVisitor()
        visitor.visit(parsed_ast)

        logger.info("Extracting Git Forensics for: %s", target_rel_path)
        top_smes = GitForensicsEngine.extract_module_smes(self.repo_path, target_rel_path)

        return ModuleArcheologyReport(
            file_path=target_rel_path,
            states=visitor.states,
            tools=visitor.tools,
            conditional_edges=visitor.conditional_edges,
            top_smes=top_smes,
            unhandled_exceptions=visitor.unhandled_exceptions,
        )

    def generate_interview_brief(self, report: ModuleArcheologyReport) -> str:
        """Synthesizes technical brief and targeted question sheet for SME interview."""
        markdown_lines = [
            f"# Dossier Arkeologi Kode & Rencana Wawancara SME: `{report.file_path}`",
            f"*Dibuat secara otomatis pada: {datetime.now(timezone.utc).isoformat()}*",
            "\n## 1. Identifikasi Subject Matter Expert (Berdasarkan Git Churn)",
        ]

        if not report.top_smes:
            markdown_lines.append("> ⚠️ Peringatan: Tidak ada riwayat Git valid ditemukan dalam 180 hari terakhir.")
        else:
            for i, sme in enumerate(report.top_smes, 1):
                markdown_lines.append(
                    f"{i}. **{sme.author_name}** (`{sme.author_email}`) - "
                    f"Commits: {sme.commit_count}, Churn: {sme.lines_changed} baris, "
                    f"Aktivitas Terakhir: {sme.last_active.strftime('%Y-%m-%d')}"
                )

        markdown_lines.append("\n## 2. Peta Arsitektur Statis (State & Tools)")
        markdown_lines.append("### State Graph Definitions:")
        if not report.states:
            markdown_lines.append("_Tidak ada schema State eksplisit (Pydantic/TypedDict) terdeteksi._")
        else:
            for state in report.states:
                markdown_lines.append(f"- **State:** `{state.name}` (Baris {state.lineno})")
                for field_name, field_type in state.fields.items():
                    markdown_lines.append(f"  - `{field_name}`: `{field_type}`")

        markdown_lines.append("\n### Registered Agentic Tools:")
        if not report.tools:
            markdown_lines.append("_Tidak ada tools berbasis decorator (@tool) terdeteksi._")
        else:
            for tool in report.tools:
                async_tag = "async" if tool.is_async else "sync"
                markdown_lines.append(f"- **Tool:** `{tool.name}` ({async_tag}, Baris {tool.lineno})")
                markdown_lines.append(f"  - Arguments: `{', '.join(tool.args)}`")
                clean_doc = (tool.docstring or 'Tidak ada docstring').split('\n')[0]
                markdown_lines.append(f"  - Docstring Snippet: _{clean_doc}_")

        markdown_lines.append("\n### Dynamic Edge Routing:")
        if not report.conditional_edges:
            markdown_lines.append("_Tidak ada conditional edge terdeteksi._")
        else:
            for edge in report.conditional_edges:
                markdown_lines.append(f"- `{edge}`")

        markdown_lines.append("\n## 3. Pertanyaan Wawancara SME Berbasis Bukti (Targeted Anchor Questions)")
        markdown_lines.append("Gunakan pertanyaan-pertanyaan ini dalam sesi wawancara teknis 30 menit:\n")

        q_idx = 1
        for state in report.states:
            for field_name, field_type in state.fields.items():
                if "Optional" in field_type or "None" in field_type:
                    markdown_lines.append(
                        f"{q_idx}. **[Field Invariant]** Pada `{state.name}`, field `{field_name}` memiliki tipe `{field_type}`. "
                        f"Kondisi operasional apa yang menyebabkan field ini bernilai `None`, dan bagaimana downstream node "
                        f"menangani ketiadaan data ini tanpa memicu runtime KeyError?"
                    )
                    q_idx += 1

        for edge in report.conditional_edges:
            markdown_lines.append(
                f"{q_idx}. **[Stochastic Routing]** Ditemukan conditional edge pada `{edge}`. "
                f"Bagaimana sistem mengisolasi kegagalan jika LLM evaluator mengembalikan string routing yang tidak "
                f"terdaftar dalam mapping routing table?"
            )
            q_idx += 1

        for tool in report.tools:
            if not tool.docstring:
                markdown_lines.append(
                    f"{q_idx}. **[Missing Schema Contract]** Tool `{tool.name}` tidak memiliki docstring semantik. "
                    f"Bagaimana LLM engine memahami konteks dan dependensi input argumen `{', '.join(tool.args)}`?"
                )
                q_idx += 1

        return "\n".join(markdown_lines)


if __name__ == "__main__":
    # Smoke-test internal pipeline execution
    repo_root = Path(".").resolve()
    # Menguji terhadap diri sendiri sebagai fallback uji statis
    target_file = "sample_agent_module.py"

    # Buat file dummy target jika tidak ada untuk verifikasi mandiri
    dummy_code = '''
from typing import TypedDict, Optional
from pydantic import BaseModel

class AgentExecutionState(BaseModel):
    session_id: str
    token_usage: int
    error_trace: Optional[str]

def tool(func):
    return func

@tool
def execute_database_query(query: str, timeout: int = 30) -> str:
    """Executes SQL against production analytical database."""
    return "result"

def route_agent_flow():
    # add_conditional_edges(source="agent", path=evaluation_router)
    pass
'''
    dummy_path = repo_root / target_file
    with open(dummy_path, "w", encoding="utf-8") as dummy_f:
        dummy_f.write(dummy_code)

    try:
        pipeline = CodeArchaeologyPipeline(str(repo_root))
        report = pipeline.run_archeology(target_file)
        briefing = pipeline.generate_interview_brief(report)
        print(briefing)
    finally:
        if dummy_path.exists():
            dummy_path.unlink()
```

---

## 7. Edge Cases & Failure Modes

Arkeologi kode dan wawancara SME sering kali menghadapi anomali sistemik yang dapat mendistorsi dokumentasi:

### 1. Metaprogramming & Dynamic Tool Registration
*   **Mode Kegagalan:** AST statis gagal mendeteksi tool yang didaftarkan secara runtime melalui loop dinamis atau decorator terselubung (misal: `registry.register(importlib.import_module(...))`).
*   **Mitigasi:** Kombinasikan AST dengan analisis dynamic inspection pada runtime unit test menggunakan `dir()`, `getattr()`, atau inspeksi metadata orchestrator (misal: `agent.tools.keys()`). Catat batasan ini pada laporan arkeologi.

### 2. Disparitas "Ghost SME" (Developer Exit)
*   **Mode Kegagalan:** Git forensics mengidentifikasi bahwa kontributor 90% modul telah meninggalkan organisasi (*resigned*), dan maintainer saat ini hanya berstatus *rubber-stamp approver*.
*   **Mitigasi:** Turunkan rentang riwayat Git hingga 360 hari. Identifikasi engineer yang menangani *incident resolution* (cari di commit messages pola `Fixes #ISSUE` atau referensi Jira). Engineer yang memperbaiki insiden adalah SME operasional sekunder terbaik.

### 3. Divergensi "Say vs. Do" pada Wawancara SME
*   **Mode Kegagalan:** SME bersikeras bahwa agen melakukan validasi schema sebelum mengeksekusi tool database, padahal kode secara fisik menunjukkan pemanggilan fungsi langsung tanpa validasi Pydantic.
*   **Mitigasi:** Terapkan protokol **Blameless Code Anchoring**:
    ```text
    "Saya melihat di code `db_router.py` baris 45 pemanggilan terjadi langsung:
    `conn.execute(unvalidated_prompt)`.
    Apakah ada interceptor upstream di layer network/proxy yang melakukan sanitasi ini,
    atau apakah baris ini merepresentasikan tech debt yang perlu dicatat sebagai batasan sistem?"
    ```
    Hindari konfrontasi personal; fokuskan perbandingan pada teks kode dan trace runtime.

---

## 8. Trade-offs & Alternatif Solusi

Setiap metodologi ekstraksi informasi teknis memiliki trade-off komputasi, waktu, dan akurasi:

| Dimensi Pendekatan | Kelebihan | Kelemahan / Trade-offs | Skenario Penggunaan Optimal |
| :--- | :--- | :--- | :--- |
| **Static AST Analysis (Pendekatan Utama)** | Deterministik murni, sangat cepat (<1 detik), tidak butuh eksekusi runtime / API keys, aman dari security leak. | Gagal membaca runtime metaprogramming, dependency injection, atau konfigurasi dynamic prompt dari external CMS/S3. | Baseline analisis struktural awal, pemetaan state model, dan deteksi tool standar. |
| **Dynamic OpenTelemetry Tracing** | Menangkap runtime latency riil, exact prompt payloads, token exhaustion failures, dan cyclic routing dinamis. | Mahal (membutuhkan infrastruktur tracing berjalan), memproses data PII sensitif, bergantung pada traffic test coverage. | Analisis latensi, debugging routing non-deterministik, validasi fallback edge cases. |
| **LLM-Based Code Summarization (e.g., Code-to-Doc bots)** | Cepat menghasilkan teks naratif awal, mampu membaca multi-file sekaligus. | Berisiko halusinasi tinggi pada parameter kritis; mengasumsikan kode "bekerja sebagaimana mestinya"; tidak dapat memvalidasi mental model SME. | Draf ringkasan fungsi individual sebelum Technical Writer turun tangan melakukan inspeksi mendalam. |
| **Asynchronous RFC / Spec Review** | Tidak mengganggu jadwal SME, memberikan waktu engineer untuk mengecek fakta. | Waktu respons sangat lambat (bisa berminggu-minggu), sering kali diabaikan atau hanya direspons secara superfisial. | Validasi akhir dokumen arsitektur komprehensif setelah draf dibuat via wawancara sinkron. |

---

## 9. Best Practices & Standard Industri

Untuk memastikan hasil dokumentasi berstandar arsitektur enterprise:

1.  **Rasio 80/20 Code-to-Interview:** 80% dari total waktu investigasi dihabiskan untuk membaca kode, tracing log, dan commit history; hanya 20% yang dihabiskan di dalam sesi bersama SME. Wawancara tatap muka tidak boleh melebihi 45 menit per modul arsitektur.
2.  **Sesi Wawancara yang Terekam dan Ditranskrip Terindeks:** Selalu rekam sesi sinkron dengan persetujuan SME. Transkripkan menggunakan model speech-to-text lokal (misal: Whisper), lalu jalankan skrip pencocokan entitas teknis untuk memetakan nama method, variabel, dan file path secara tepat.
3.  **Metode Red-Line Spec Review:** Saat membagikan draf hasil wawancara kembali ke SME, tandai secara eksplisit dengan format status:
    *   `[VERIFIED VIA CODE]`: Dikonfirmasi melalui AST dan commit aktif.
    *   `[SME CLAIM - UNVERIFIED]`: Dinyatakan oleh SME dalam wawancara namun belum ditemukan bukti fisiknya di repositori.
    *   `[KNOWN TECH DEBT]`: Kegagalan penanganan error yang disepakati sebagai batasan sistem sementara.
4.  **Standarisasi Tool Arkeologi:** Integrasikan pipeline AST dan churn analytics ke dalam task runner repositori (misalnya `Makefile` atau `taskfile`), sehingga seluruh Technical Writer di organisasi menggunakan standarisasi ekstraksi data yang sama.

---

## 10. Hands-on Lab Exercise

### Konteks Skenario
Sebuah modul orkestrator multi-agen enterprise yang kritis, `autonomous_support_orchestrator.py`, mengalami *silent failures* di production. Log error menunjukkan agen terkadang memanggil database secara berulang-ulang tanpa menghasilkan jawaban ke pengguna. Repositori ini tidak memiliki dokumentasi fungsional, dan pengembang aslinya telah dipindahkan ke tim riset lain.

### Langkah Instruksi

#### Langkah 1: Persiapan Repositori Uji
Buat sebuah direktori lab dan inisialisasi repositori Git lokal:

```bash
mkdir -p /tmp/agent_archaeology_lab
cd /tmp/agent_archaeology_lab
git init
git config user.name "Lead AI Engineer"
git config user.email "lead_ai@enterprise.internal"
```

#### Langkah 2: Buat Modul Agen yang Bermasalah
Simpan kode berikut sebagai `autonomous_support_orchestrator.py`:

```python
"""
Legacy Autonomous Agent Mesh Node.
Architectural integrity: Unverified.
"""
from typing import TypedDict, List, Optional
import random

class RouterState(TypedDict):
    customer_id: str
    query_history: List[str]
    intent_detected: Optional[str]
    escalation_flag: bool
    retry_budget: int

def tool(fn):
    fn._is_tool = True
    return fn

@tool
def lookup_customer_account(customer_id: str) -> dict:
    """Fetches real-time financial balances and flags."""
    return {"balance": 1000.0, "status": "active"}

@tool
def trigger_human_escalation(reason: str) -> bool:
    """Hands over conversation context to support tier 2."""
    return True

def support_agent_evaluator(state: RouterState) -> str:
    # Fallback and routing simulation
    if state["retry_budget"] <= 0:
        return "escalate"
    if not state.get("intent_detected"):
        return "re-evaluate"
    return "resolve"
```

Commit modul ini untuk membangun riwayat Git lokal:
```bash
git add autonomous_support_orchestrator.py
git commit -m "feat(agent): deploy initial legacy support agent mesh"
```

Lakukan commit update sebagai engineer kedua untuk memicu data churn:
```bash
git config user.name "Secondary Maintainer"
git config user.email "sec_maintainer@enterprise.internal"
echo "# Patching retry budget constraints" >> autonomous_support_orchestrator.py
git commit -am "fix(agent): update edge comments on retry logic"
```

#### Langkah 3: Eksekusi Tool Arkeologi
Jalankan script Python dari **Bagian 6** terhadap repositori ini:
```bash
python /path/to/archaeologist_engine.py
```
*(Arahkan `repo_root` ke `/tmp/agent_archaeology_lab` dan target file ke `autonomous_support_orchestrator.py`)*.

#### Langkah 4: Evaluasi Analisis Output
Tinjau file markdown briefing yang dihasilkan. Identifikasi:
1.  Siapa SME primer yang harus dijadwalkan wawancara pertama kali?
2.  Field mana pada `RouterState` yang rentan menyebabkan *infinite loop* stokastik jika model LLM evaluator gagal mengisinya?
3.  Apakah tool `trigger_human_escalation` memiliki parameter untuk menerima context trace dari `query_history`?

#### Langkah 5: Deliverable Akhir Lab
Buat dokumen Architecture Decision Record (ADR) ringkas berformat markdown (`ADR-001-SUPPORT-AGENT-ROUTING.md`) yang merinci:
*   **Status:** Proposed / Accepted.
*   **Context:** Kondisi fisik kode saat ini dan diskrepansi yang ditemukan saat arkeologi.
*   **Decision:** Keputusan arsitektur yang disepakati untuk memperbaiki loop evaluasi (berdasarkan pertanyaan wawancara terarah).
*   **Consequences:** Dampak performa dan mitigasi risiko operasional downstream.