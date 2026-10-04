# KURIKULUM TINGKAT ENTERPRISE: AI-DATA & AUTONOMOUS AGENTS
## TOPIK: VIBE-CODING | KATEGORI: 08-AI-DATA-AND-AUTONOMOUS-AGENTS
### BAB 03: Context Engineering & Repository Knowledge Injection
### MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis & Mengatasi** fenomena *Context Degradation*, *Attention Dilution*, dan *Lost-in-the-Middle* pada Large Language Model (LLM) dengan *context window* skala besar (128k–1M token) saat mengeksekusi *vibe-coding* pada repositori enterprise.
- **Merancang & Mengimplementasikan** *hybrid code retrieval engine* berbasis Abstract Syntax Tree (AST), Language Server Protocol (LSP) / Source Code Intelligence Protocol (SCIP), dan *sparse-dense index fusion* (BM25 + Code Embeddings).
- **Membangun** pipeline *Context Assembler* deterministik dengan alokasi *token budgeting* dinamis, *dependency call graph traversal*, dan *cross-encoder re-ranking* untuk menyuplai *sub-graph context* paling relevan ke autonomous coding agent.
- **Mengoptimalkan** efisiensi cache (*prompt caching optimizations*) dan throughput indexing untuk repositori monorepo skala jutaan baris kode (Lines of Code / LoC).

---

### 2. Prerequisite
Untuk menyerap materi secara optimal, Anda wajib menguasai:
1. **Konsep Kompiler & Parsing**: Pemahaman operasional terhadap *Abstract Syntax Tree* (AST), *Concrete Syntax Tree* (CST), serta grammar formal (misalnya via Tree-sitter).
2. **Information Retrieval (IR)**: Konsep dasar vector similarity (Cosine, Dot Product), Vector Database (mis. Qdrant, Milvus), BM25 lexical search, dan Reciprocal Rank Fusion (RRF).
3. **Arsitektur LLM**: Mekanisme self-attention, rotary positional embeddings (RoPE), tokenization (Tiktoken/SentencePiece), dan degradasi performa pada *long-context reasoning*.
4. **Tooling & Bahasa**: Python 3.11+, Rust (opsional, untuk parser performa tinggi), Docker, dan dasar-dasar CLI Git tingkat lanjut.

---

### 3. Concept & Internal Architecture (Mendalam)

#### Arsitektur Context Engine dalam Vibe-Coding Skala Enterprise
Dalam paradigma *vibe-coding*, developer berinteraksi melalui instruksi intensi deklaratif (*natural language intent*). Agar model inferensi tidak menghasilkan halusinasi arsitektural atau *breaking changes*, engine membutuhkan sistem injeksi konteks yang melampaui RAG teks konvensional (chunking per baris/karakter). Kode adalah *directed cyclic graph* (DCG), bukan teks linier bebas.

Sistem injeksi konteks produksi membagi arsitektur ke dalam 4 lapisan fundamental:

```
[ Developer Intent / IDE Action ]
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 1. Structural Ingestion & Static Analysis Layer        │
│    - Tree-sitter AST Parser (Scope Extraction)         │
│    - LSP / SCIP Indexer (Def-Use, Cross-References)    │
│    - Git Working Tree Diff Engine                      │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 2. Hybrid Dual-Index Subsystem                         │
│    - Sparse Index (BM25 / SPLADE: Symbol & Identifier) │
│    - Dense Index (Code-specialized Embeddings)         │
│    - Graph Database / Adjacency Matrix (Call Graph)    │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 3. Context Pruning, Graph Walking & Ranking Layer      │
│    - Dynamic Depth-First / Breadth-First Call-Graph    │
│    - Reciprocal Rank Fusion (RRF) & Cross-Encoder      │
│    - Topological Sorter (Interface before Impl)       │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 4. Deterministic Context Assembler (Prompt Builder)   │
│    - Token Budget Allocator (System/Core/Periphery)    │
│    - KV Cache Alignment (Prefix-preserving structure)  │
│    - AST Interface Slicing (Skeletons/Signatures)     │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
     [ Model Ingestion Context ]
```

#### Komponen Internal
1. **Tree-sitter AST Chunking Engine**:
   - Memotong unit kode berdasarkan batas semantik gramatikal: class, function, struct, interface.
   - Mengabaikan whitespace arbitrari; mempertahankan metadata *parent-scope* (nama namespace, enclosure class).
2. **Code Property Graph (CPG) Traverser**:
   - Menghubungkan *Abstract Syntax Tree* (AST), *Control Flow Graph* (CFG), dan *Program Dependence Graph* (PDG).
   - Menjawab pertanyaan kritis: "Jika function `A()` dimodifikasi, siapa saja yang memanggilnya dan type apa yang di-passing?"
3. **KV-Cache Aware Assembler**:
   - Menyusun context dengan urutan: `System Core Definition` -> `Static Project Schema` -> `Repository Interfaces` -> `Dynamic Ephemeral Files` -> `Active Diff/User Intent`.
   - Menjaga prefix tetap statis untuk memaksimalkan *prompt cache hit rate* (Anthropic / OpenAI prefix caching), memangkas latensi TTFT (Time to First Token) hingga 80% dan biaya inferensi hingga 90%.

---

### 4. Why & What

| Dimensi | Naive Vector RAG (Text-based) | Enterprise Context Engineering (Code-Aware) |
| :--- | :--- | :--- |
| **Satuan Unit (Chunk)** | 500-1000 karakter linier (terpotong di tengah loop/fungsi). | Semantic AST Boundary (Node fungsi, class, type signature lengkap). |
| **Resolusi Simbol** | Bergantung kemiripan leksikal embedding. | Exact-match via LSP symbols + AST Scope Binding. |
| **Konektivitas Kode** | Terisolasi per chunk, dependensi luar hilang. | Relational Call Graph (Menarik definisi type/struct yang diimpor). |
| **Utilisasi Token** | Token terbuang untuk boilerplate/implementasi internal yang tidak relevan. | *Interface Slicing* (mengirimkan skeleton signature tanpa body fungsi periferal). |
| **Dampak Halusinasi** | Tinggi: Agent menebak parameter fungsi dan return type. | Sangat Rendah: Kontrak type dan skema diinjeksikan secara deterministik. |

---

### 5. How (Workflow Detail)

1. **Phase 1: Ingestion & Symbol Indexing**
   - File source code diparsing menggunakan Tree-sitter ke dalam Concrete Syntax Tree.
   - Ekstraksi *exported symbols*, *imports*, *class signatures*, dan *function declarations*.
   - Bangun indeks inverted leksikal (BM25) khusus identifier dan generate dense embedding pada semantic docstring + signature.

2. **Phase 2: Intent Analysis & Query Decomposition**
   - User memasukkan instruksi vibe-coding: *"Tambahkan validasi JWT dan rate-limiting middleware pada endpoint checkout"*.
   - Agent mengekstrak target file (`checkout.controller.ts`) dan simbol terkait (`AuthMiddleware`, `RateLimiter`, `Request`).

3. **Phase 3: Hybrid Retrieval & Graph Traversal**
   - Pencarian leksikal exact match pada identifier `RateLimiter` dan semantic search untuk "request throttling".
   - Mengambil simbol target dan melakukan *1-hop dependency walk* pada import graph: temukan interface tipe dependency injection.

4. **Phase 4: AST Slicing (Skeletization)**
   - Untuk dependensi level 2 (misal library internal `TokenService`), hilangkan blok implementasi (`body`) dan hanya sisakan *type signatures* untuk menghemat token budget.

5. **Phase 5: Context Assembly with Token Budget Enforcement**
   - Tetapkan batas hard budget (contoh: 32.000 token dari model window 128k untuk menyisakan ruang CoT dan generasi).
   - Injeksi urutan context secara deterministik, hitung token menggunakan tokenizer yang sesuai, dan kirimkan prompt ke LLM.

---

### 6. Analogy & Diagram ASCII

#### Analogi Meja Operasi Bedah
*Naive RAG* seperti membuang tumpukan 100 lembar rekam medis pasien acak ke meja operasi, di mana lembaran rekam jantung terpotong dua karena batas mesin fotokopi. Dokter bedah (LLM) harus membuang waktu menyatukan kertas dan membaca data yang tidak relevan.

*Context Engineering* adalah asisten bedah bersertifikasi yang hanya meletakkan:
1. Ringkasan alergi dan tanda vital mutakhir pasien (*System Context*).
2. Alat bedah yang relevan dengan organ target (*Exported Signatures*).
3. Diagram vaskular spesifik area insisi (*Call Graph Traversal*).

#### Diagram Alur Data Context Assembly
```
[User Intent] ──┐
                 ▼
    ┌─────────────────────────┐
    │  Query Symbol Extractor │
    └────────────┬────────────┘
                 │ (Symbols: 'CheckoutService', 'OrderPayload')
                 ├──────────────────────────────────────┐
                 ▼                                      ▼
      ┌──────────────────────┐              ┌──────────────────────┐
      │ BM25 / Sparse Index  │              │ Dense Vector Index   │
      └──────────┬───────────┘              └──────────┬───────────┘
                 │ (Ranked IDs)                        │ (Ranked IDs)
                 └───────────────┬──────────────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ Reciprocal Rank Fusion│
                     └───────────┬───────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ Graph Dependency Walk │ (LSP / AST Definitions)
                     └───────────┬───────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       [Primary Target Node]           [Peripheral Dependencies]
       (Full Implementation)           (AST Interface Skeleton Only)
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ Token Budget Packing  │ (Hard limit: e.g. 16K tok)
                     └───────────┬───────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ Prefix-Cache Assembler│
                     └───────────┬───────────┘
                                 ▼
                         [To Coding Agent]
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Ekstraksi AST Interface Slicing dengan Tree-sitter (Python)
Mekanisme dasar membuang body implementasi fungsi dan hanya menyisakan signature untuk menghemat context window.

```python
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)

source_code = b"""
class PaymentProcessor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._internal_cache = {}

    def process_transaction(self, amount: float, currency: str) -> bool:
        # Implementasi kompleks 50 baris yang memboroskan token
        print("Authenticating against gateway...")
        if amount <= 0:
            return False
        return True
"""

tree = parser.parse(source_code)

def extract_signatures(node, source_bytes):
    extracted = []
    for child in node.children:
        if child.type == 'class_definition':
            name_node = child.child_by_field_name('name')
            class_name = source_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8')
            extracted.append(f"class {class_name}:")
            body_node = child.child_by_field_name('body')
            for body_child in body_node.children:
                if body_child.type == 'function_definition':
                    fn_name = source_bytes[body_child.child_by_field_name('name').start_byte:body_child.child_by_field_name('name').end_byte].decode('utf-8')
                    params = source_bytes[body_child.child_by_field_name('parameters').start_byte:body_child.child_by_field_name('parameters').end_byte].decode('utf-8')
                    return_type = ""
                    ret_node = body_child.child_by_field_name('return_type')
                    if ret_node:
                        return_type = " -> " + source_bytes[ret_node.start_byte:ret_node.end_byte].decode('utf-8')
                    extracted.append(f"    def {fn_name}{params}{return_type}: ...")
    return "\n".join(extracted)

print(extract_signatures(tree.root_node, source_code))
# Output:
# class PaymentProcessor:
#     def __init__(self, api_key: str): ...
#     def process_transaction(self, amount: float, currency: str) -> bool: ...
```

---

#### Practical Example: Production-Grade Code Context Assembler Pipeline
Implementasi komprehensif orchestrator konteks yang menggabungkan Token Budgeting, Slicing, dan Mock LSP Dependency Resolver.

```python
#!/usr/bin/env python3
"""
Production-Ready Context Assembler for Autonomous Vibe-Coding Agents.
Menjalankan: Token Budgeting, AST Slicing, Dependency Resolution, dan Assembly.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
import tiktoken

class PriorityTier(Enum):
    CRITICAL_ACTIVE = 1    # Target file yang diedit langsung (Isi penuh)
    DEPENDENCY_DIRECT = 2  # Import langsung level-1 (AST Sliced Interface)
    PROJECT_MANIFEST = 3   # Skema DB, package.json, konfigurasi type
    HISTORICAL_GIT = 4     # Riwayat commit diff terakhir

@dataclass
class CodeArtifact:
    file_path: str
    content: str
    tier: PriorityTier
    is_sliced: bool = False
    token_count: int = 0

class ContextAssembler:
    def __init__(self, model_name: str = "gpt-4o", max_budget: int = 4096):
        self.tokenizer = tiktoken.encoding_for_model(model_name)
        self.max_budget = max_budget

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, disallowed_special=()))

    def slice_ast_interfaces(self, code: str) -> str:
        """
        Sederhana tapi deterministik: memotong body function untuk interface dependencies.
        Pada real-world, gunakan tree-sitter bindings secara penuh.
        """
        lines = code.splitlines()
        sliced_lines = []
        skip_body = False
        base_indent = 0

        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            if stripped.startswith("def ") or stripped.startswith("async def "):
                sliced_lines.append(line.rstrip())
                if stripped.endswith(":"):
                    sliced_lines.append(" " * (indent + 4) + "...")
                skip_body = True
                base_indent = indent
                continue
            
            if skip_body:
                if indent <= base_indent and stripped:
                    skip_body = False
                    sliced_lines.append(line)
                continue

            sliced_lines.append(line)

        return "\n".join(sliced_lines)

    def assemble(self, artifacts: List[CodeArtifact], developer_intent: str) -> str:
        # Pre-process token sizes
        for art in artifacts:
            if art.tier == PriorityTier.DEPENDENCY_DIRECT and not art.is_sliced:
                art.content = self.slice_ast_interfaces(art.content)
                art.is_sliced = True
            art.token_count = self.count_tokens(art.content)

        # Sort berdasarkan prioritas (Tier numerik terkecil = prioritas tertinggi)
        artifacts.sort(key=lambda x: x.tier.value)

        intent_tokens = self.count_tokens(developer_intent)
        current_tokens = intent_tokens + 150 # Cadangan system prompt overhead
        
        retained_artifacts: List[CodeArtifact] = []

        for art in artifacts:
            if current_tokens + art.token_count <= self.max_budget:
                retained_artifacts.append(art)
                current_tokens += art.token_count
            else:
                # Upaya mitigasi: jika CRITICAL_ACTIVE tidak muat, raise error
                if art.tier == PriorityTier.CRITICAL_ACTIVE:
                    raise ValueError(f"File target utama {art.file_path} melebihi token budget!")
                # Skip dependensi periferal yang melebihi batas budget
                continue

        # Format prompt deterministik yang menjaga prefix cache
        context_blocks = [
            "### SYSTEM: You are an elite software architect executing a precision vibe-coding patch.",
            f"### INTENT: {developer_intent}\n",
            "### REPOSITORY CONTEXT ARCHITECTURE:"
        ]

        for art in retained_artifacts:
            tag = "ACTIVE_EDIT_TARGET" if art.tier == PriorityTier.CRITICAL_ACTIVE else "INTERFACE_DEPENDENCY"
            context_blocks.append(f"\n--- BEGIN FILE: {art.file_path} [{tag}] ---")
            context_blocks.append(art.content)
            context_blocks.append(f"--- END FILE: {art.file_path} ---")

        return "\n".join(context_blocks)

# Verifikasi Operasional
if __name__ == "__main__":
    assembler = ContextAssembler(max_budget=600)

    target_code = """class OrderService:
    def __init__(self, repo: PaymentRepository):
        self.repo = repo

    def execute_order(self, order_id: str, amount: float):
        # Implementation to be patched by agent
        pass"""

    dependency_code = """class PaymentRepository:
    def connect_db(self):
        print("Connecting to secure cluster via TLS socket...")
        self.conn = True
        return self.conn

    def process_charge(self, token: str, amount: float) -> bool:
        # Very long execution logic that wastes context budget
        print("Validating balance...")
        print("Executing transaction...")
        return True"""

    artifacts = [
        CodeArtifact("src/services/order.py", target_code, PriorityTier.CRITICAL_ACTIVE),
        CodeArtifact("src/repos/payment.py", dependency_code, PriorityTier.DEPENDENCY_DIRECT)
    ]

    intent = "Inject retry mechanism with exponential backoff on execute_order if PaymentRepository fails."
    final_prompt = assembler.assemble(artifacts, intent)
    
    print(final_prompt)
    print(f"\nTotal Assembled Tokens: {assembler.count_tokens(final_prompt)}")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Tier-1 FinTech Core Banking Monorepo Migration
* **Skala Repositori**: 4.8 Juta LoC Go & Java, 8.500 microservices diatur dalam satu monorepo.
* **Tantangan**: Injeksi Autonomous Coding Agent (Vibe-Coding internal) untuk migrasi database layer dari legacy ORM ke sqlc/pgx native. Pendekatan naive retrieval menyebabkan *infinite hallucination loops* pada tipe pointer Go dan salah mereferensikan package interface internal.
* **Solusi Arsitektural**:
  1. **SCIP (Source Code Intelligence Protocol) Indexing**: Menjalankan scip-java dan scip-go di CI pipeline setiap ada commit baru ke branch utama, menghasilkan graph referensi simbolik deterministik tanpa parsing ulang LLM.
  2. **Multi-hop Subgraph Retrieval**: Saat user mengetikkan prompt migrasi, sistem menarik definition target struct, lalu memetakan pemanggilnya hingga 2 level ke atas (Upstream callers) dan tipe data model ke bawah (Downstream models).
  3. **Strict Token Budget Partitioning**:
     - Budget Total: 64k token.
     - Active Editing Target: Max 12k token (Full file).
     - Upstream Interface Skeletons: Max 10k token (Tree-sitter stripped).
     - Downstream Schemas (DDL / Protobuf): Max 10k token.
     - Dynamic Semantic Search Context: Max 8k token.
     - Model Output Headroom: 24k token.
* **Hasil Metrik**:
  - Penurunan tingkat *Compilation Error* pasca sintesis kode agen dari **64.2%** menjadi **4.1%**.
  - Waktu *first-pass acceptance rate* (PR langsung lolos CI tanpa manual rework) melonjak dari **18%** menjadi **73%**.
  - Biaya LLM bulanan per engineer turun **58%** berkat pemotongan implementasi body via AST interface slicing dan peningkatan prompt cache hits sebesar **82%**.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian & Batasan |
| :--- | :--- | :--- |
| **AST Interface Slicing** | Memangkas ukuran konteks hingga 70-85%; mengurangi noise implementasi internal. | Model kehilangan detail implisit di dalam body (misal: throw/panic runtime exceptions yang tidak dideklarasikan). |
| **SCIP / LSP Symbol Graph** | 100% deterministik, zero-hallucination pada lokasi deklarasi dan call hierarchy. | Membutuhkan proses kompilasi/indexing offline yang intensif; sensitif terhadap kode yang *broken/syntax error*. |
| **Hybrid Search (Dense + BM25 RRF)** | Seimbang menangani identifier teknis yang unik (`TX_ERR_INVALID_NONCE`) dan semantik konseptual. | Latensi retrieval bertambah (+150ms-400ms); perlu mengelola dua storage engine (misal: Qdrant + OpenSearch). |
| **Full File Context Injection** | Model memiliki konteks lengkap tanpa dependensi yang terputus (*global visibility*). | *Lost-in-the-Middle*: Atensi model drop drastis pada file besar (>3.000 baris); biaya token membengkak secara eksponensial. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Naive Character/Line Chunking pada Kode Program
* **Gejala**: Agent sering mengalami syntax error (*unterminated string*, *unmatched parenthesis*) atau salah menyimpulkan return type fungsi.
* **Akar Masalah**: Chunking berbasis karakter memutus class atau function di tengah blok logika.
* **Solusi**: Gunakan AST-aware chunker (seperti Tree-sitter) yang hanya memotong pada node boundaries (`function_item`, `method_declaration`).

#### 2. Cache Invalidation Akibat Dynamic Header Shuffling
* **Gejala**: Biaya inferensi melonjak dan TTFT (Time to First Token) lambat (>10 detik pada long context).
* **Akar Masalah**: Menaruh metadata dinamis (misalnya timestamp, user ID, atau active diff) di bagian paling atas (prefix) prompt, yang merusak *Prompt Caching* LLM provider.
* **Solusi**: Pindahkan semua artefak statis (System rules, static repository schemas, interface skeletons) ke urutan awal, dan letakkan dynamic user prompt/diff di bagian paling akhir prompt.

#### 3. Context Dilution ("Lost in the Middle")
* **Gejala**: Agent mengabaikan constraint kritis atau method signatures penting yang berada di tengah-tengah context payload 100k token.
* **Akar Masalah**: Kurva retensi transformer menurun tajam untuk data di kuadran tengah (20% - 80% range) context window.
* **Solusi**: Terapkan *Context Re-ordering*: Tempatkan file target utama dan instruksi kritis di 10% awal dan 10% akhir context window.

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic Grammar Parsing**: Pastikan parsing menggunakan grammar Tree-sitter yang dipin ke commit tag stabil, bukan regex parsing.
- [ ] **Strict Token Guardrails**: Alokasikan *token ceiling* kaku per segmen (Active Target, Interfaces, Project DDL) dengan enforcement tokenizer native sebelum payload dikirim ke API network.
- [ ] **Interface-Only Downstream Injection**: Jangan pernah menyuplai full implementation file dependensi pihak ketiga/internal; selalu potong menjadi TypeScript declaration (`.d.ts`), Go interfaces, atau Python protocols stub.
- [ ] **Deterministic Ordering for Prefix Caching**: Urutkan file berdasarkan path hash/alfabetis di dalam tier yang sama guna menjamin cache hit identik pada pemanggilan berturut-turut.
- [ ] **LSP Diagnostic Feedback Loop**: Sebelum menyajikan kode final ke developer, validasi hasil generate agent menggunakan `lsp diagnostic` secara headless di background container.

---

### 12. Hands-on Practice

Buat repositori hands-on lokal untuk membangun mini Context-Engine berbasis Tree-sitter dan dynamic assembler.

#### Setup Workspace
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
python3 -m venv .venv
source .venv/bin/activate
pip install tree-sitter==0.23.2 tree-sitter-python==0.23.2 tiktoken
```

#### Struktur Direktori
```
hands-on/m02/
├── .venv/
├── src/
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── ast_slicer.py
│   │   └── context_packer.py
│   └── main.py
└── test_repo/
    ├── core.py
    └── service.py
```

#### Langkah 1: Buat Dummy Repositori Target
File: `hands-on/m02/test_repo/core.py`
```python
class DatabaseSession:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._connected = True

    def query(self, sql: str, params: tuple = ()):
        print(f"Executing: {sql} with {params}")
        return [{"id": 1, "status": "active"}]

    def close(self):
        self._connected = False
```

File: `hands-on/m02/test_repo/service.py`
```python
from core import DatabaseSession

class UserService:
    def __init__(self, db: DatabaseSession):
        self.db = db

    def get_user_status(self, user_id: int) -> str:
        # TODO: Needs optimization and error handling
        records = self.db.query("SELECT status FROM users WHERE id = %s", (user_id,))
        return records[0]["status"]
```

#### Langkah 2: Buat AST Slicer Engine
File: `hands-on/m02/src/engine/ast_slicer.py`
```python
import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node

class ASTSlicer:
    def __init__(self):
        self.language = Language(tspython.language())
        self.parser = Parser(self.language)

    def slice_to_declarations(self, code: str) -> str:
        source_bytes = code.encode('utf-8')
        tree = self.parser.parse(source_bytes)
        
        output_lines = []
        
        def traverse(node: Node, depth: int = 0):
            indent = "    " * depth
            if node.type == 'class_definition':
                name = node.child_by_field_name('name')
                class_name = source_bytes[name.start_byte:name.end_byte].decode('utf-8')
                output_lines.append(f"{indent}class {class_name}:")
                body = node.child_by_field_name('body')
                for child in body.children:
                    traverse(child, depth + 1)
            elif node.type == 'function_definition':
                name = node.child_by_field_name('name')
                params = node.child_by_field_name('parameters')
                fn_name = source_bytes[name.start_byte:name.end_byte].decode('utf-8')
                fn_params = source_bytes[params.start_byte:params.end_byte].decode('utf-8')
                ret_node = node.child_by_field_name('return_type')
                ret_str = f" -> {source_bytes[ret_node.start_byte:ret_node.end_byte].decode('utf-8')}" if ret_node else ""
                output_lines.append(f"{indent}def {fn_name}{fn_params}{ret_str}: ...")

        for child in tree.root_node.children:
            traverse(child)

        return "\n".join(output_lines)
```

#### Langkah 3: Eksekusi Test Runner Pipeline
File: `hands-on/m02/src/main.py`
```python
from engine.ast_slicer import ASTSlicer

def main():
    slicer = ASTSlicer()
    with open("test_repo/core.py", "r") as f:
        core_raw = f.read()

    with open("test_repo/service.py", "r") as f:
        service_raw = f.read()

    print("[*] ORIGINAL CORE DEPENDENCY (TOKEN HEAVY):")
    print(core_raw)
    
    print("\n[*] SLICED CORE INTERFACE (TOKEN OPTIMIZED):")
    sliced_core = slicer.slice_to_declarations(core_raw)
    print(sliced_core)
    
    print("\n[*] FINAL ASSEMBLED CONTEXT FOR VIBE-CODING AGENT:")
    final_payload = f"""### CONTEXT SPECIFICATION
--- DEPENDENCY: test_repo/core.py (STUB) ---
{sliced_core}

--- ACTIVE TARGET: test_repo/service.py ---
{service_raw}
"""
    print(final_payload)

if __name__ == "__main__":
    main()
```
Jalankan verifikasi:
```bash
python3 src/main.py
```

---

### 13. Exercise

#### Level Easy
Modifikasi `ast_slicer.py` pada repositori latihan hands-on agar mampu mendeteksi dan mengekstraksi type alias serta modul level variable (contoh: `MAX_RETRIES: int = 5` atau `UserID = str`) tanpa membuang tipe datanya.

#### Level Medium
Buat module `dependency_graph.py` yang membaca baris `import ...` dan `from ... import ...` dari target file menggunakan Tree-sitter queries (bukan regex), lalu secara otomatis mereferensikan file yang bersangkutan di lokal disk untuk diserahkan ke `ASTSlicer`.

#### Level Hard
Implementasikan sebuah `DynamicBudgetPacker` yang:
1. Menerima input: N file target, token limit kaku (misal 1.000 token).
2. Menghitung embedding distance antara intent pengguna dengan docstring class/function di tiap file.
3. Secara adaptif memilih: Apakah menginjeksi full-file, sliced-file, atau hanya nama simbol dependensi saja berdasarkan nilai skor kesamaan (similarity score) dan sisa ruang token budget, memecahkan masalah ini menggunakan pendekatan varian *0/1 Knapsack Problem*.

---

### 14. Challenge

**Studi Kasus**: Rancang arsitektur context injection engine untuk enterprise distributed microservices monorepo yang mendukung cross-language call tracing (Go backend memanggil gRPC microservice di Rust, yang membaca event schema dari Apache Avro/Protobuf).

**Kebutuhan Sistem**:
1. Saat engineer meminta: *"Ubah response gRPC Auth microservice (Rust) untuk menyertakan field `device_trust_score`, lalu konsumsi field tersebut di API Gateway (Go)"*.
2. Context engine harus secara deterministik menemukan: Proto schema file, gRPC generated client di Go, dan struct handler di Rust.
3. Menjamin total context tidak melebihi 24.000 token dan tidak memuat artefak file binary compiler (`.a`, `.so`, proto binary).
4. Tuliskan dokumen desain arsitektur formal: Format representasi schema graph, mekanisme indexing, teknik deduplikasi tipe data gRPC, dan algoritma perakitan prompt akhir.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. **Mengapa naive text chunking (500 karakter bergeser) fatal jika diterapkan pada repository source code?**
   - *Jawaban*: Kode memiliki struktur hierarki sintaksis dan referensial. Chunking teks acak memotong deklarasi di tengah ekspresi, merusak konteks scope lokal, menghilangkan kurung penutup/indentasi, dan memisahkan tanda tangan method dari body logikanya, yang mengakibatkan model menghasilkan syntax error.

2. **Apa yang dimaksud dengan "Interface Slicing" dalam konteks AST?**
   - *Jawaban*: Teknik ekstraksi struktural menggunakan parser kompilator (seperti Tree-sitter) untuk membuang body implementasi fungsi/metode dan hanya mempertahankan class declaration, parameter signature, type annotations, dan return types guna menghemat ruang token window.

3. **Bagaimana urutan prioritas token yang ideal saat merakit context prompt?**
   - *Jawaban*: (1) Target file yang sedang diedit (Full), (2) Direct interfaces/dependencies (Sliced), (3) Project Data Schema/Config, (4) User Intent & Diff, dengan penempatan elemen statis di awal untuk efisiensi prefix caching.

4. **Apa fungsi utama Reciprocal Rank Fusion (RRF) dalam pencarian kode repositori?**
   - *Jawaban*: Menggabungkan hasil ranking pencarian leksikal (BM25 - unggul dalam mencari exact match nama fungsi/variabel) dan pencarian vektor semantik (Dense - unggul dalam menangkap maksud konseptual) tanpa memerlukan normalisasi skor absolut antar algoritma.

5. **Apa risiko menyertakan seluruh histori git (commit logs) ke dalam context window?**
   - *Jawaban*: Menyebabkan polusi konteks (*Context Dilution*), menghabiskan token budget secara sia-sia untuk kode usang (*dead/deprecated code*), dan memicu bias pada LLM untuk mengulangi bug lama yang pernah di-rollback.

---

#### Intermediate Questions
1. **Bagaimana mekanisme KV Cache Alignment bekerja dalam optimasi biaya API LLM pada proses vibe-coding berulang?**
   - *Jawaban*: LLM provider menyimpan state key-value attention dari prompt prefix yang identik. Dengan menyusun context assembler secara deterministik (System rules dan core type interfaces selalu berada pada token urutan 0 hingga N), request berulang hanya menghitung inferensi pada delta token baru di bagian akhir, memangkas Time to First Token (TTFT) dan biaya compute prompt token.

2. **Kapan hybrid search (Dense + Sparse) gagal dan bagaimana Language Server Protocol (LSP) menambal kegagalan tersebut?**
   - *Jawaban*: Gagal saat simbol yang dicari bersifat polimorfik, dinamik, atau memiliki nama umum (misal: `execute()` atau `handle()`). Search berbasis teks/vektor akan mengembalikan puluhan method serupa. LSP menambal ini dengan resolusi deterministik via *compiler-backed cross-referencing* (Go-to-Definition, Find References) yang memetakan relasi simbol secara pasti.

3. **Bagaimana fenomena "Lost-in-the-Middle" mempengaruhi LLM pada repositori dengan context window 1M token?**
   - *Jawaban*: LLM memiliki bias atensi berbentuk kurva U (U-shaped attention curve). Informasi di awal (prefix) dan akhir prompt mendapatkan bobot atensi tertinggi, sedangkan informasi di tengah (misal di range token ke-400.000 hingga 700.000) sering gagal diambil saat proses inferensi multidependensi yang rumit.

4. **Mengapa SCIP lebih disukai dibandingkan dump database SQLite buatan sendiri untuk menyimpan graph repositori di skala enterprise?**
   - *Jawaban*: SCIP (Source Code Intelligence Protocol) menyediakan skema standardized yang kompatibel lintas bahasa, mendukung streaming parsing, dirancang khusus untuk referensi simbolik kode monorepo berukuran gigabyte, dan terintegrasi dengan ekosistem Sourcegraph/LSP tanpa overhead translasi skema buatan sendiri.

5. **Bagaimana menangani token limit overflow secara elegan jika file target aktif yang HARUS diedit ukurannya melebihi batas token budget model?**
   - *Jawaban*: Memecah target file menggunakan dekomposisi semantik AST tingkat fungsi. Menyuplai hanya class skeleton dengan fungsi target yang hendak dimodifikasi dalam bentuk lengkap, sementara fungsi-fungsi tetangga di dalam file yang sama dipotong menggunakan interface slicing (*selective focal windowing*).

---

#### Scenario-Based Case Questions

##### Skenario 1: The Monorepo Poisoning
*Konteks*: Tim platform engineering mendapati bahwa Autonomous Coding Agent sering kali mengimpor module internal lama (`v1/auth`) padahal perusahaan sudah meluncurkan `v2/auth`. Kedua module masih eksis di repositori monorepo.
*Pertanyaan*: Rancang strategi context filtering deterministik pada lapisan retrieval pipeline untuk mencegah agent menggunakan modul deprecated tersebut tanpa perlu menghapus kodenya dari disk fisik!
*Solusi*: 
1. Terapkan *Metadata Tainting* pada AST parser engine. Saat file ingestion mendeteksi file atau direktori bertanda `@deprecated` atau jalur path `*/v1/*`, tandai flag node tersebut sebagai `unroutable`.
2. Pada tahap *Dependency Graph Traversal*, inject rule pemfilteran hard constraint: Abaikan seluruh simbol yang berasal dari modul dengan status tainted kecuali file target aktif secara eksplisit sudah mengimpornya.
3. Injeksi context directive singkat di level root schema: *"Deprecation Notice: For any authentication requirement, bind exclusively to v2/auth exported contracts."*

##### Skenario 2: Cache Miss Catastrophe
*Konteks*: Sebuah startup pengembang dev-tools mengeluhkan tagihan API Anthropic Claude 3.5 Sonnet melonjak $20,000 dalam sebulan. Setelah dievaluasi, prompt caching hit-rate mereka hanya sebesar 4%. Arsitektur prompt mereka menaruh Git Working Tree Diff aktif di baris pertama prompt untuk "memberi tahu model apa yang sedang terjadi".
*Pertanyaan*: Identifikasi kelemahan arsitektur ini dan susun ulang struktur prompt pipeline yang benar agar cache hit-rate melonjak di atas 80%!
*Solusi*:
1. **Analisis Masalah**: Cache prefix invalid seketika karakter pertama berbeda. Menaruh Git Diff (yang berubah setiap karakter diketik developer) di token urutan terdepan merusak total pembacaan cache dari baris ke-0 hingga akhir.
2. **Restrukturisasi Pipeline**:
   - `Segment 1 (Tokens 0 - 4000)`: System Prompt & Base Coding Standards (Statis 100%).
   - `Segment 2 (Tokens 4001 - 20000)`: Base Library Declarations, Core Data Schemas, Sliced Repository API Signatures (Statis 95% selama tidak ada perubahan skema global).
   - `Segment 3 (Tokens 20001 - 28000)`: File Skeletons dari modul terkait langsung.
   - `Segment 4 (Tokens 28001+)`: Dynamic Context (Active Git Diff, Intent Pengguna, Pesan Error Terminal).

##### Skenario 3: The Circular Dependency Trap
*Konteks*: Agent diminta memodifikasi microservice payment. Saat context builder melakukan dependency traversal secara rekursif untuk mengambil type signatures, proses assembly mengalami infinite loop dan memori server OOM (Out Of Memory) akibat file `OrderController` mengimpor `UserService`, yang mengimpor `PaymentService`, yang mengimpor kembali `OrderController`.
*Pertanyaan*: Tuliskan algoritma traversal aman yang harus diimplementasikan pada Graph Walker engine!
*Solusi*:
Gunakan traversal berbasis *Depth-First Search (DFS)* atau *Breadth-First Search (BFS)* yang dilengkapi dengan *Visited Set tracker* dan *Depth Limiting*:
```python
def traverse_dependency_graph(root_node: str, max_depth: int = 2) -> Set[str]:
    visited: Set[str] = set()
    queue: List[tuple[str, int]] = [(root_node, 0)]
    
    while queue:
        current_node, current_depth = queue.pop(0)
        
        if current_node in visited or current_depth > max_depth:
            continue
            
        visited.add(current_node)
        
        # Ambil dependensi langsung via AST import resolution
        dependencies = get_direct_imports(current_node)
        for dep in dependencies:
            if dep not in visited:
                queue.append((dep, current_depth + 1))
                
    return visited
```
Batasi depth traversal maksimal 2 hop untuk mengisolasi ledakan kompleksitas konteks.

---

### 16. Summary

Context Engineering pada paradigma *vibe-coding* enterprise membedakan antara mainan prototyping dengan sistem rekayasa perangkat lunak otonom kelas produksi. LLM mutakhir tidak kekurangan kapasitas penalaran (*reasoning*); kegagalan generasi kode hampir selalu berakar pada **kualitas, relevansi, dan struktur konteks yang diinjeksikan**. 

Dengan mengalihkan pendekatan dari *naive line-based retrieval* ke kombinasi deterministik dari **Tree-sitter AST Slicing**, **Compiler-level LSP/SCIP graph walking**, **Hybrid Dense-Sparse indexing**, dan **KV Cache Alignment**, arsitektur sistem mampu meminimalkan halusinasi model, memangkas latensi TTFT, serta menekan biaya inferensi secara signifikan pada monorepo skala enterprise. Context yang presisi menghasilkan sintesis kode deterministik yang siap rilis ke tahap produksi.