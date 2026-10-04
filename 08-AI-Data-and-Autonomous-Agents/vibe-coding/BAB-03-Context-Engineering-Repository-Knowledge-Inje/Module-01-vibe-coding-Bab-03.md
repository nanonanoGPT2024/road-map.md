# Bab 03: Context Engineering & Repository Knowledge Injection (Module 01)
**Track:** 08-AI-Data-and-Autonomous-Agents  
**Sub-track:** Vibe-Coding & Agentic Software Development Environments

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Principal Engineer / Senior Architect diharapkan mampu:

1. **Mendesain Arsitektur Konteks Multi-Skala**: Mengonstruksi pipeline ekstraksi konteks repositori kode yang memisahkan *high-level topological maps* (arsitektur/skema) dari *low-level implementation details* (blok fungsi) untuk meminimalkan *token consumption* hingga $\ge 60\%$ tanpa kehilangan akurasi resolusi simbol.
2. **Mengimplementasikan AST-based Graph Retrieval**: Membangun *dependency graph* antar-berkas menggunakan *Abstract Syntax Tree* (AST) untuk mendeteksi dependensi panggilan (*call graph*), pewarisan (*inheritance*), dan antarmuka (*interface contracts*) secara deterministik, mengungguli *naive vector search* RAG.
3. **Mengeksekusi Dynamic Token Budgeting**: Mengembangkan alokator konteks berbasis algoritma *Knapsack/Greedy* terbobot untuk menginjeksi konteks ke *Large Language Model* (LLM) dengan latensi $< 150\text{ ms}$ pada context window $32\text{k} - 128\text{k}$ token.
4. **Mengeliminasi Halusinasi Relasional**: Mencegah fenomena *broken references* dan *hallucinated interfaces* saat agen melakukan *multi-file refactoring* atau *vibe-coding* pada basis kode berukuran $\ge 100.000\text{ LOC}$.

---

## 2. Concept Overview

Dalam paradigma *vibe-coding*, *engineer* bertindak sebagai konduktor tingkat tinggi yang mengarahkan intensi, sementara model otonom mengeksekusi sintaksis dan integrasi. Kelemahan terbesar dari alur kerja ini bukan pada kemampuan penalaran LLM, melainkan pada **kualitas, relevansi, dan kepadatan informasi konteks** yang diberikan (*Garbage In, Garbage Out*).

```
+-------------------------------------------------------------------------+
|                              MENTAL MODEL                               |
|                                                                         |
|  [Naive Vector RAG]           vs.    [Context Engineering Engine]       |
|                                                                         |
|  Query: "Fix user auth"              Query: "Fix user auth"             |
|         │                                    │                          |
|         ▼ (Cosine Sim)                       ▼ (Deterministic AST)      |
|  ┌──────────────┐                     ┌──────────────────────────────┐  |
|  │ Chunk A: 0.81│ -> auth_test.py     │ Topology Map: System Context │  |
|  │ Chunk B: 0.79│ -> user_model.py    │ Call Graph: Router -> AuthSvc│  |
|  │ Chunk C: 0.77│ -> readme.md        │ Interfaces: UserDTO, ISvc    │  |
|  └──────────────┘                     │ Git Diff: Head vs WorkingDir │  |
|  *Disjointed, missing caller chain,   └──────────────────────────────┘  |
|   hallucinates imports & signatures.  *Spatially and logically coherent,|
|                                        zero missing imports.            |
+-------------------------------------------------------------------------+
```

Konstruksi konteks repositori modern menolak pendekatan *chunking* berbasis teks biasa (*fixed-size token splitting*). *Code is not natural language*; kode adalah **Directed Acyclic Graph (DAG)** (atau graf siklik dalam dependensi modular) dengan semantik yang kaku. 

Context Engineering mengintegrasikan empat pilar utama:
1. **Structural Skeletons (Repo Maps)**: Representasi ringkas seluruh berkas kode yang hanya memuat tanda tangan tipe (*type signatures*), kelas, dan fungsi publik, yang diberi bobot menggunakan modifikasi algoritma *PageRank*.
2. **Determinism over Stochasticity**: Mengutamakan *compiler/AST analysis* untuk menemukan dependensi langsung sebelum beralih ke pencarian semantik (vektor/embedding).
3. **Budget Windowing**: Mengalokasikan kapasitas token secara dinamis antara *System Instructions*, *Active File Buffers*, *Upstream/Downstream Dependencies*, dan *Historical Feedback Loops*.
4. **Temporal Context**: Menginjeksi *git status*, modifikasi yang belum di-commit (*unstaged changes*), dan linting error langsung ke dalam runtime buffer LLM.

---

## 3. Why It Matters

Pendekatan *naive retrieval* (membaca seluruh file atau mengandalkan embeddings kosinus biasa) mengalami kegagalan sistemik di skala enterprise:

* **The "Lost in the Middle" Phenomenon**: Penelitian menunjukkan degradasi tajam dalam pemanggilan informasi ketika informasi penting terkubur di tengah konteks dokumen yang besar ($>32\text{k}$ token).
* **Cross-File Dependency Blindness**: Perubahan pada signature fungsi di `src/core/auth.py` mengharuskan agen mengetahui seluruh *callers* di `src/api/v1/endpoints/*.py`. Naive vector search gagal menarik *all callers* karena variasi semantik bahasa alami yang rendah di antara baris panggilan.
* **Context Pollution & Token Burn**: Memasukkan file mentah secara utuh menghabiskan token context window, meningkatkan latensi inferensi secara kuadratik pada arsitektur attention standar ($O(N^2)$), serta menaikkan biaya komputasi enterprise secara eksponensial.
* **Interface Drift**: Agen mengusulkan kode yang secara sintaksis benar namun secara arsitektural ilegal (memanggil *private methods*, menggunakan tipe usang, atau melanggar *clean architecture boundaries*).

Context Engineering menyediakan jembatan deterministik antara kode lokal dan *reasoning window* agen LLM.

---

## 4. Arsitektur & Diagram Komponen

Arsitektur pipeline *Repository Knowledge Injection Engine* beroperasi secara *real-time* atau *near-real-time* melalui skema berikut:

```
+─────────────────────────────────────────────────────────────────────────────────────────+
|                         CONTEXT ENGINEERING ENGINE PIPELINE                             |
+─────────────────────────────────────────────────────────────────────────────────────────+
                                             │
                                     [File System Watcher]
                                             │
                                             ▼
                       +─────────────────────────────────────────+
                       |           Tree-Sitter / AST Parser      |
                       +─────────────────────────────────────────+
                                    │               │
            (Symbols & Signatures)  │               │ (Imports & Calls)
                                    ▼               ▼
                        +────────────────+     +─────────────────+
                        | Skeletonizer   |     | Dependency Graph|
                        | (Class/Def Map)|     | (NetworkX DAG)  |
                        +────────────────+     +─────────────────+
                                    │               │
                                    │   ┌───────────┘
                                    ▼   ▼
                        +─────────────────────────+
                        | PageRank Symbol Ranker  |
                        +─────────────────────────+
                                    │
                                    │ (Ranked Symbols & Structures)
                                    ▼
+───────────────────────+   +─────────────────────────────────────────+
| Focus File / Prompt   |──>|      Dynamic Token Budget Manager       |
| (Active Edit Context) |   |    (Greedy Slicer & Context Inverter)   |
+───────────────────────+   +─────────────────────────────────────────+
                                    │
                                    ▼
                        +─────────────────────────+
                        | Formatted Context Block |
                        | (XML / Markdown Encoded)|
                        +─────────────────────────+
                                    │
                                    ▼
                        [LLM Context Window Input]
```

### Rincian Alur Data:
1. **AST Parser Engine**: Memetakan setiap file kode menjadi *Abstract Syntax Tree*. Mengekstraksi *identifiers*, *imports*, *function definitions*, *class inheritance*, dan *docstrings*.
2. **Code Graph Builder**: Mengaitkan dependensi antar simpul. Jika `FileA.ts` mengimpor `ServiceB` dari `FileB.ts`, dibuat tepi terarah `FileA -> FileB`.
3. **Symbol Ranker (PageRank-based)**: Simpul kode dengan *in-degree centrality* yang tinggi (misal: antarmuka inti, pustaka utilitas dasar) memiliki prioritas bobot lebih tinggi dalam *Repo Map*.
4. **Context Budget Allocator**: Menerima batas token (misal: 8.000 token untuk konteks kode repositori). Mengisi slot dengan prioritas:
   * Level 1: Berkas aktif saat ini (*full implementation*).
   * Level 2: Berkas antarmuka/tipe yang diimpor langsung oleh berkas aktif.
   * Level 3: Rangkuman *skeletal map* berskala repositori dari berkas berbobot tinggi.
   * Level 4: Hasil penelusuran semantik sekunder (jika sisa ruang tersedia).

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Syntax Tree Extraction vs. Token-based Chunking
Alih-alih mengiris file setiap $N$ token, AST parser memecah kode berdasarkan batas logika struktural:
* Node Lingkup Luar: `Module -> ClassDef -> FunctionDef`.
* Eliminasi Badan Fungsi: Implementasi internal `FunctionDef` dipotong (*stubbing*) menjadi `...` atau tanda tangan tipe murni untuk menghemat hingga 85% token per file, menyisakan *topological skeleton*.

### 5.2 Algoritma Peringkat Simbol (Repomap Scoring)
Untuk menentukan file mana yang berhak masuk ke dalam *budget window*, representasi graf dependensi repositori $G = (V, E)$ dihitung menggunakan algoritma *damping-factor PageRank*:

$$PR(u) = \frac{1-d}{|V|} + d \sum_{v \in B_u} \frac{PR(v)}{L(v)}$$

Di mana:
* $u$ adalah simbol/berkas tertentu.
* $B_u$ adalah kumpulan berkas yang mereferensikan/mengimpor $u$.
* $L(v)$ adalah jumlah *out-degree references* dari berkas $v$.
* $d$ adalah *damping factor* (biasanya ditetapkan pada $0.85$).

Dengan memberikan bobot referensi tambahan (*personalization vector*) pada file yang sedang dibuka oleh *engineer*, context engine menghasilkan representasi kontekstual lokal yang tajam.

### 5.3 Deterministic Context Packing
LLM rentan terhadap kegagalan inferensi jika format konteks ambigu. Pendekatan standar industri menggunakan pembungkus XML eksplisit seperti:

```xml
<repository_context>
  <file path="src/domain/user.py" relevance="direct_dependency">
    class User:
        id: UUID
        email: str
        def update_email(self, new_email: str) -> None: ...
  </file>
</repository_context>
```

XML tag memberikan batas struktural deterministik (*boundary markers*) yang dipahami secara optimal oleh model penalaran mutakhir (misal: Claude 3.5 Sonnet, GPT-4o).

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi Python 3.11+ tingkat produksi dari **Context Engineering & Knowledge Injection Engine**. Sistem ini mencakup *AST Skeletonizer*, *In-Memory Dependency Graph*, *Tiktoken Context Budgeting*, dan *Format XML Injection*.

```python
"""
Repository Knowledge Injection Engine for Agentic Coding Workflows.
Designed for high-performance AST parsing, symbol resolution, and context window optimization.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import tiktoken


class ContextPriority(Enum):
    ACTIVE_FILE = 1.0
    DIRECT_DEPENDENCY = 0.8
    CORE_INTERFACE = 0.6
    TOPOLOGICAL_SKELETON = 0.4
    SEMANTIC_FALLBACK = 0.2


@dataclass(frozen=True)
class CodeSymbol:
    name: str
    symbol_type: str  # 'class', 'function', 'import'
    line_number: int
    signature: str


@dataclass
class FileNode:
    path: Path
    relative_path: str
    raw_content: str
    tokens_count: int = 0
    symbols: List[CodeSymbol] = field(default_factory=list)
    imports: Set[str] = field(default_factory=set)
    skeleton: Optional[str] = None


class ASTSkeletonizer(ast.NodeTransformer):
    """
    Strips function and method bodies from Python AST, replacing them with Ellipsis (...)
    Preserves class definitions, method signatures, decorators, and type hints.
    """

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return self._truncate_body(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        return self._truncate_body(node)

    def _truncate_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
        # Menyimpan docstring jika ada, memotong implementasi internal
        docstring = ast.get_docstring(node)
        new_body: list[ast.stmt] = []
        
        if docstring:
            new_body.append(ast.Expr(value=ast.Constant(value=docstring)))
        
        new_body.append(ast.Expr(value=ast.Constant(value=...)))
        
        # Clone node tanpa modifikasi state aslinya
        return ast.copy_location(
            ast.FunctionDef(
                name=node.name,
                args=node.args,
                body=new_body,
                decorator_list=node.decorator_list,
                returns=node.returns,
                type_comment=node.type_comment,
            ),
            node,
        )


class RepositoryAnalyzer:
    """
    Menganalisis basis kode lokal, membangun dependensi impor, dan membuat skeletal map.
    """

    def __init__(self, root_dir: Path, encoding_name: str = "cl100k_base") -> None:
        self.root_dir = root_dir.resolve()
        self.tokenizer = tiktoken.get_encoding(encoding_name)
        self.nodes: Dict[str, FileNode] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, disallowed_special=()))

    def process_file(self, file_path: Path) -> Optional[FileNode]:
        try:
            rel_path = file_path.relative_to(self.root_dir).as_posix()
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as err:
            # Handle binary files, encoding errors, or access issues
            return None

        tree = None
        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError:
            # Berkas dengan sintaks tidak valid tetap dimasukkan secara mentah
            pass

        symbols: List[CodeSymbol] = []
        imports: Set[str] = field(default_factory=set)
        skeleton_code = content

        if tree:
            symbols = self._extract_symbols(tree)
            imports = self._extract_imports(tree)
            skeletonizer = ASTSkeletonizer()
            try:
                skeleton_tree = skeletonizer.visit(ast.parse(content))
                skeleton_code = ast.unparse(skeleton_tree)
            except Exception:
                skeleton_code = content

        node = FileNode(
            path=file_path,
            relative_path=rel_path,
            raw_content=content,
            tokens_count=self.count_tokens(content),
            symbols=symbols,
            imports=imports,
            skeleton=skeleton_code,
        )
        return node

    def _extract_symbols(self, tree: ast.AST) -> List[CodeSymbol]:
        extracted = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args_list = [arg.arg for arg in node.args.args]
                sig = f"{node.name}({', '.join(args_list)})"
                extracted.append(CodeSymbol(node.name, "function", node.lineno, sig))
            elif isinstance(node, ast.ClassDef):
                sig = f"class {node.name}"
                extracted.append(CodeSymbol(node.name, "class", node.lineno, sig))
        return extracted

    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        imported_modules: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module)
        return imported_modules

    def index_repository(self) -> None:
        """Scan repositori dan bentuk dependency map."""
        for path in self.root_dir.rglob("*.py"):
            if any(part.startswith((".", "venv", "__pycache__", "build")) for part in path.parts):
                continue
            node = self.process_file(path)
            if node:
                self.nodes[node.relative_path] = node

        # Resolusi ketergantungan graf sederhana
        for rel_path, node in self.nodes.items():
            self.dependency_graph[rel_path] = set()
            for imp in node.imports:
                imp_as_path = imp.replace(".", "/") + ".py"
                if imp_as_path in self.nodes:
                    self.dependency_graph[rel_path].add(imp_as_path)


class ContextBudgetManager:
    """
    Mengelola alokasi context window berdasarkan limit token yang ketat.
    Menggunakan algoritma prioritas berlapis untuk eliminasi token waste.
    """

    def __init__(self, analyzer: RepositoryAnalyzer, total_budget: int = 8192) -> None:
        self.analyzer = analyzer
        self.total_budget = total_budget

    def build_context(self, active_file_path: str) -> str:
        used_tokens = 0
        allocated_blocks: List[str] = []

        # 1. Alokasi Prioritas 1: Active File (Full Raw Content)
        active_node = self.analyzer.nodes.get(active_file_path)
        if not active_node:
            raise FileNotFoundError(f"Active file {active_file_path} tidak ditemukan di indeks.")

        active_file_tokens = active_node.tokens_count
        if active_file_tokens > self.total_budget:
            # Fallback jika file aktif lebih besar dari total context window
            return self._format_xml_block(
                active_node.relative_path,
                active_node.skeleton or active_node.raw_content[:self.total_budget * 3],
                "active_file_truncated"
            )

        allocated_blocks.append(
            self._format_xml_block(active_node.relative_path, active_node.raw_content, "active_focus")
        )
        used_tokens += active_file_tokens

        # 2. Alokasi Prioritas 2: Direct Dependencies (Skeletons/Signatures)
        direct_deps = self.analyzer.dependency_graph.get(active_file_path, set())
        for dep_path in direct_deps:
            dep_node = self.analyzer.nodes.get(dep_path)
            if not dep_node:
                continue

            content_to_inject = dep_node.skeleton if dep_node.skeleton else dep_node.raw_content
            dep_tokens = self.analyzer.count_tokens(content_to_inject)

            if used_tokens + dep_tokens <= self.total_budget:
                allocated_blocks.append(
                    self._format_xml_block(dep_node.relative_path, content_to_inject, "direct_dependency")
                )
                used_tokens += dep_tokens
            else:
                break

        # 3. Alokasi Prioritas 3: Topological High-Level Repo Map
        remaining_budget = self.total_budget - used_tokens
        if remaining_budget > 500:
            repo_map_block = self._generate_lightweight_repo_map(exclude={active_file_path} | direct_deps, token_limit=remaining_budget)
            if repo_map_block:
                allocated_blocks.append(repo_map_block)

        return "<injected_repository_context>\n" + "\n".join(allocated_blocks) + "\n</injected_repository_context>"

    def _generate_lightweight_repo_map(self, exclude: Set[str], token_limit: int) -> Optional[str]:
        map_lines: List[str] = ["<repository_symbol_index>"]
        current_cost = 20

        for rel_path, node in self.analyzer.nodes.items():
            if rel_path in exclude:
                continue

            symbols_str = ", ".join(s.signature for s in node.symbols[:5])
            line = f"  - {rel_path}: {symbols_str}"
            line_cost = self.analyzer.count_tokens(line)

            if current_cost + line_cost > token_limit - 10:
                break

            map_lines.append(line)
            current_cost += line_cost

        map_lines.append("</repository_symbol_index>")
        return "\n".join(map_lines) if len(map_lines) > 2 else None

    @staticmethod
    def _format_xml_block(path: str, content: str, scope: str) -> str:
        return f'<context_document path="{path}" scope="{scope}">\n{content}\n</context_document>'


# =====================================================================
# Pipeline Entry Point Execution Verification
# =====================================================================
if __name__ == "__main__":
    import tempfile

    # Setup dummy directory tree simulasi real project
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        
        # Buat core model
        user_mod = root / "models"
        user_mod.mkdir()
        (user_mod / "user.py").write_text(
            "class UserModel:\n    def __init__(self, name: str):\n        self.name = name\n    def save(self):\n        pass",
            encoding="utf-8"
        )
        
        # Buat service
        svc_mod = root / "services"
        svc_mod.mkdir()
        (svc_mod / "auth.py").write_text(
            "import models.user\n\nclass AuthService:\n    def login(self, username: str) -> bool:\n        u = models.user.UserModel(username)\n        return True",
            encoding="utf-8"
        )

        analyzer = RepositoryAnalyzer(root_dir=root)
        analyzer.index_repository()

        budget_engine = ContextBudgetManager(analyzer=analyzer, total_budget=4000)
        final_context = budget_engine.build_context("services/auth.py")

        print("=== INJECTED CONTEXT RESULT ===")
        print(final_context)
```

---

## 7. Edge Cases & Failure Modes

Pada level implementasi sistem produksi berskala multi-gigabyte, sejumlah skenario batas (*edge cases*) dan mode kegagalan kritis berikut harus ditangani secara deterministik:

1. **Circular Import Graphs**:
   * *Problem*: File A mengimpor File B, yang mengimpor File C, yang kembali mengimpor File A. Algoritma resolusi dependensi rekursif tanpa pelindung siklus akan memicu *Maximum Recursion Depth Exceeded*.
   * *Recovery*: Gunakan pelacakan *visited set* (Depth First Search dengan pewarnaan simpul graf) untuk langsung menghentikan transversal jika simpul yang sama ditemui dua kali.

2. **Dynamically Computed & Wildcard Imports**:
   * *Problem*: `from .plugins import *` atau pemanggilan dinamis via `importlib.import_module(var)`. AST Parser statis gagal menentukan resolusi nama secara langsung.
   * *Fallback*: Identifikasi kegagalan parsing statis dan picu *fallback* ke algoritma pencarian teks BM25 / Cosine Vector terdekat pada namespace direktori yang berkorespondensi.

3. **Massive Generated Files / Minified Bundles**:
   * *Problem*: Repositori memuat file seperti `schema.json`, `bundle.min.js`, atau artefak kompilasi protobuf yang berukuran $> 500\text{k}$ token.
   * *Mitigasi*: Validasi batas file sebelum membaca string: abaikan file dengan panjang rata-rata per baris $> 1.000$ karakter atau ukuran file $> 500\text{ KB}$, serta terapkan *exclusion rules* bawaan (`.gitignore`, `.cursorignore`, `.contextignore`).

4. **Slicing AST Syntax Breakdown**:
   * *Problem*: File yang sedang dimodifikasi secara aktif (*buffer in-memory*) sering kali memiliki kesalahan sintaksis sementara (*unterminated strings*, *missing colons*) yang memicu `SyntaxError` pada AST parser.
   * *Fallback Engine*: Ketika parsing AST gagal, beralihlah secara halus (*graceful degradation*) ke algoritma *regex-based structural indentation extraction* untuk mempertahankan ekstraksi tanda tangan blok.

---

## 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektural dalam perancangan *Context Injection* membawa konsekuensi yang harus dipertimbangkan secara matang:

| Pendekatan | Kompleksitas Rekayasa | Token Consumption | Presisi Pemanggilan Simbol | Latensi Pemrosesan |
| :--- | :--- | :--- | :--- | :--- |
| **Naive File Inclusion** (Dump whole files) | Rendah | Sangat Boros ($10\text{x}$) | Sangat Rendah (*Lost in Middle*) | Tercepat ($O(1)$) |
| **Vector DB Embedding (Dense RAG)** | Menengah | Terkontrol | Sedang (Sering luput pada refactoring lintas file) | Menengah ($100-300\text{ ms}$) |
| **Deterministic AST Graph + Skeletons (Terpilih)** | Tinggi | Sangat Efisien (Hemat $60-80\%$) | Sangat Tinggi (Deterministik) | Rendah-Menengah ($<150\text{ ms}$) |
| **Full GraphRAG (LLM-generated knowledge graph)** | Sangat Ekstrem | Boros saat pra-pemrosesan | Sangat Tinggi (Konteks semantik dalam) | Sangat Lambat (Detik hingga Menit) |

### Analisis Solusi Terpilih:
AST Graph Injection dipilih untuk siklus iterasi penulisan kode cepat (*vibe-coding*) karena **latensi pemrosesan yang sangat rendah** dan sifatnya yang **deterministik**. Berbeda dengan Natural Language RAG, kode tidak mentolerir ambiguitas probabilitas: impor modul bersifat biner (tersedia atau gagal/crash).

---

## 9. Best Practices & Standar Industri

1. **Struktur XML Tags Berstandar**: Gunakan tag XML tertutup seperti `<context>`, `<active_file>`, `<dependencies>`, dan `<system_instructions>`. Tag ini mencegah model mencampuradukkan instruksi tugas dengan basis data konteks (*prompt injection mitigation*).
2. **Context Budgets Allocation Ratio**:
   * **Active Buffer**: $35\%$ dari total jatah alokasi token.
   * **First-order Dependencies**: $35\%$ dari alokasi token.
   * **Global Repomap (Skeleton)**: $15\%$ dari alokasi token.
   * **Semantic Search / Vector Results**: $15\%$ dari sisa jatah token.
3. **Tiktoken Dynamic Verification**: Jangan pernah mengandalkan perkiraan jumlah karakter (seperti rasio $4 \text{ karakter} = 1 \text{ token}$). Selalu gunakan *encoder* native tokenizer yang sesuai dengan arsitektur model target secara *real-time*.
4. **Stripping Comments and Redundant Docstrings**: Untuk dependencies non-aktif, bersihkan komentar implementasi internal dan pertahankan hanya parameter type hint dan *return value specifications*.

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda ditugaskan mengintegrasikan konteks repositori mini yang terdiri dari 3 berkas (`payment_gateway.py`, `order_service.py`, `order_controller.py`) ke dalam prompt inferensi LLM. Anda harus membatasi konteks agar muat dalam **maksimum 500 token**, dengan fokus pengeditan pada `order_controller.py`.

### Langkah-langkah Praktik

#### Langkah 1: Siapkan Lingkungan Pengujian
Buat lingkungan virtual baru dan install dependency:
```bash
python3 -m venv venv
source venv/bin/activate
pip install tiktoken
```

#### Langkah 2: Buat File Struktur Repositori Uji Coba
Simpan kode berikut sebagai `setup_mock_repo.py` dan jalankan:
```python
from pathlib import Path

base = Path("./mock_repo")
base.mkdir(exist_ok=True)

(base / "payment_gateway.py").write_text("""
class PaymentGateway:
    def process_charge(self, amount_in_cents: int, token: str) -> bool:
        # Implementation hidden
        print(f"Charging {amount_in_cents}")
        return True
""", encoding="utf-8")

(base / "order_service.py").write_text("""
from payment_gateway import PaymentGateway

class OrderService:
    def __init__(self):
        self.gateway = PaymentGateway()

    def checkout(self, cart_id: str, amount: int) -> bool:
        return self.gateway.process_charge(amount, "token_abc")
""", encoding="utf-8")

(base / "order_controller.py").write_text("""
from order_service import OrderService

class OrderController:
    def __init__(self):
        self.service = OrderService()

    def handle_request(self, payload: dict):
        # Target for our vibe coding session: Implement checkout flow
        pass
""", encoding="utf-8")

print("Mock repository generated successfully.")
```

#### Langkah 3: Eksekusi Engine & Verifikasi Output Konteks
Jalankan modul context engine (dari implementasi Section 6 di atas) yang diarahkan ke file `./mock_repo` dengan fokus pada `order_controller.py`:

```python
from pathlib import Path
from context_engine import RepositoryAnalyzer, ContextBudgetManager

repo_dir = Path("./mock_repo")
analyzer = RepositoryAnalyzer(root_dir=repo_dir)
analyzer.index_repository()

# Batasi budget sangat ketat: 300 token saja!
manager = ContextBudgetManager(analyzer=analyzer, total_budget=300)
context_output = manager.build_context("order_controller.py")

print("\n--- OUTPUT PAYLOAD TERINJEKSI KE PROMPT ---")
print(context_output)
```

#### Kriteria Keberhasilan Verifikasi:
1. `order_controller.py` harus masuk ke dalam konteks secara utuh dengan cakupan `active_focus`.
2. `order_service.py` harus teridentifikasi sebagai dependensi langsung dan direduksi menjadi representasi skeleton (badan fungsi dipotong).
3. Total token dari output payload akhir tidak boleh melebihi 300 token (terverifikasi melalui kalkulasi `tiktoken`).
4. Output dibungkus secara rapi dalam struktur XML (`<injected_repository_context>`).