# Kurikulum Rekayasa Perangkat Lunak AI Enterprise
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB-03: Paradigma Penalaran Tingkat Lanjut (Advanced Reasoning Paradigms)
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Merancang dan Mengimplementasikan Paradigma State-Space Search Berbasis LLM:** Membangun mesin penalaran non-linear menggunakan *Tree-of-Thoughts* (ToT), *Graph-of-Thoughts* (GoT), dan integrasi heuristik pencarian terpandu (*A\** / *Monte Carlo Tree Search* - MCTS).
2. **Mengotomatisasi Dynamic Sampling & Self-Consistency Engine:** Mengonfigurasi layer orkestrasi yang mengeksekusi multi-path reasoning, mendeteksi konvergensi semantik via clustering embedding, dan menghitung skor marginal confidence secara deterministik.
3. **Mengelola State Mutation, Pruning, dan Backtracking:** Mengembangkan state machine asynchronous yang memvalidasi intermediate reasoning states, memotong cabang penalaran invalid (*dead ends*), dan mengeksekusi backtracking tanpa context window starvation.
4. **Mengoptimalkan Token Economy & Latency Engine:** Mengimplementasikan kompresi state graf penalaran, selective evaluation, caching sub-graph reasoning, dan structured reasoning tokens guna meminimalkan Time-to-First-Token (TTFT) dan End-to-End Latency pada beban kerja produksi.

---

### 2. Prerequisite

Peserta didik wajib memiliki pemahaman mendalam dan pengalaman praktis pada:
*   **Fundamental Prompt Engineering:** Chain-of-Thought (CoT), Few-Shot Prompting, ReAct framework, dan System Prompting (Bab 01 & Bab 02).
*   **Pemrograman Lanjutan Python:** Asynchronous programming (`asyncio`), typing system (`typing`, `Pydantic v2`), generator pattern, dan data structures (Trees, Directed Acyclic Graphs).
*   **AI/LLM Engineering:** LLM APIs (OpenAI API spec, Anthropic SDK), Tokenizer internals (BPE, tiktoken), Structured Outputs via JSON Schema / Function Calling, dan Text Embedding Vector Math (Cosine Similarity, DBSCAN/k-Means clustering).
*   **Arsitektur Sistem Terdistribusi:** Caching strategies (Redis), asynchronous task queues (Celery/Temporal), rate limiting, dan metric instrumentation (OpenTelemetry, Prometheus).

---

### 3. Concept & Internal Architecture

Dalam paradigma penalaran konvensional (*Zero-Shot* atau *Linear Chain-of-Thought*), Large Language Model menghasilkan token secara autoregresif dalam satu jalur linier:

$$P(y_1, y_2, \dots, y_T \mid x) = \prod_{t=1}^T P(y_t \mid x, y_{<t})$$

Pendekatan ini rentan terhadap *compounding error*: jika LLM mengambil langkah penalaran salah pada $t_k$, seluruh urutan langkah berikutnya $t_{>k}$ akan terkontaminasi halusinasi atau logika cacat tanpa mekanisme koreksi mandiri (*self-correction*).

```
[Linear CoT]
x -> Step 1 -> Step 2 (Error!) -> Step 3 (Hallucinated) -> Output Salah

[Tree-of-Thoughts (ToT)]
              ┌── Step 1a (Score: 0.2) -> [PRUNED]
x -> Step 1 ──┼── Step 1b (Score: 0.9) ──┬── Step 2a (Score: 0.3) -> [PRUNED]
              └── Step 1c (Score: 0.5)   └── Step 2b (Score: 0.95) -> Step 3 -> Solusi Valid

[Graph-of-Thoughts (GoT)]
Step 1a ──┬──> Aggregation / Synthesis ──> Step 2a ──> Validated Solution
Step 1b ──┘                                   ▲
Step 1c ──────────────────────────────────────┘ (Feedback loop / Enriched Context)
```

Modul ini mengeksplorasi pergeseran arsitektural dari CoT linier menuju **State-Space Search Graph**:

```
+-----------------------------------------------------------------------------------+
|                        ORCHESTRATION LAYER (Search Controller)                    |
|                                                                                   |
|  +--------------------+      +--------------------+      +---------------------+  |
|  |  Thought Generator | ---> | Thought Evaluator  | ---> |   State Manager     |  |
|  |  (Proposer Prompt) |      | (Value Prompt/Scor)|      | (Graph Store & Cut) |  |
|  +--------------------+      +--------------------+      +---------------------+  |
|           ^                                                         |             |
|           |                 Tree/Graph State Mutation               |             |
|           +---------------------------------------------------------+             |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         INFERENCE & VALIDATION ENGINE                             |
|                                                                                   |
|  +--------------------+      +--------------------+      +---------------------+  |
|  | Dynamic Sampling   |      | Semantic Distance  |      | Backtracking Engine |  |
|  | (Self-Consistency) |      | Cluster Consensus  |      | (Depth/Breadth/A*)  |  |
|  +--------------------+      +--------------------+      +---------------------+  |
+-----------------------------------------------------------------------------------+
```

#### Komponen Internal Arsitektur:
1. **Thought Generator ($G$):** Berfungsi membangkitkan $k$ kandidat langkah penalaran berikutnya (*thoughts*) berdasarkan state saat ini $S = [s_0, s_1, \dots, s_t]$. Generator mengaplikasikan strategi ekspansi diskrit (misalnya via *Sample* variatif dengan temperature $\tau \approx 0.7$ atau *Propose* terstruktur dengan temperature $\tau \approx 0.2$).
2. **Thought Evaluator ($V$):** Berfungsi sebagai fungsi heuristik $V(S) \to \mathbb{R} \in [0.0, 1.0]$. Menggunakan LLM dengan prompt *Value Model* (atau logit scoring pada token spesifik) untuk menilai kelayakan langkah, memvalidasi dependensi logis, dan mendeteksi pelanggaran batasan invariant.
3. **State Manager & Frontier:** Mengelola pohon pencarian ($T = (V_t, E_t)$) atau Directed Acyclic Graph ($G = (V_g, E_g)$). Mengatur frontier pencarian, mengeksekusi operasi graf (transformasi, agregasi, feedback loops), dan mengelola serialisasi context window.
4. **Search Algorithm Engine:** Mengorkestrasikan traversal (Breadth-First Search, Depth-First Search dengan backtracking, Beam Search, atau Monte Carlo Tree Search) dengan memangkas (*pruning*) node yang memiliki nilai evaluasi $V(S) \le \theta_{threshold}$.

---

### 4. Why & What

#### Why: Mengapa CoT Sederhana Gagal pada Enterprise System?
*   **Kurangnya Mekanisme Evaluasi Mundur (Backtracking):** Pada sistem audit finansial atau verifikasi kode, CoT linier tidak dapat membatalkan aksi jika di tengah jalan menemukan variabel yang tidak konsisten.
*   **Tunnel Vision pada Masalah Kombinatorik:** CoT konvensional cenderung memprioritaskan penyelesaian instan pertama yang tampak benar (*greedy selection*), mengabaikan ruang eksplorasi yang menghasilkan solusi optimal.
*   **Sensitivitas Probabilistik Tinggi:** Satu token acak dengan probabilitas rendah di awal CoT dapat membelokkan seluruh trajektori deduksi logis.

#### What: Solusi Penalaran Terstruktur
Paradigma penalaran tingkat lanjut mengonseptualisasikan proses inferensi LLM sebagai **masalah pencarian dalam graf ruang keadaan (state-space search)**:
*   **Tree-of-Thoughts (ToT):** Mengeksplorasi cabang-cabang pemikiran alternatif secara eksplisit; mendukung evaluasi komparatif dan backtracking ketika suatu cabang terbukti invalid.
*   **Graph-of-Thoughts (GoT):** Memperluas ToT dengan mengizinkan *node aggregation* (menggabungkan kesimpulan dari dua pemikiran independen) dan *looping/refinement* (mentranslasikan thought sebelumnya menjadi versi yang lebih robust).
*   **Self-Consistency with Dynamic Stopping:** Mengambil $N$ sampel CoT paralel, kemudian mengekstrak kluster konsensus tertinggi melalui embedding semantic distance dan stopping condition deterministik guna menghemat komputasi saat margin keyakinan model sudah terpenuhi.

---

### 5. How (Workflow Detail)

Alur kerja operasional mesin penalaran GoT/ToT tingkat lanjut di tingkat produksi meliputi langkah berikut:

```
[Mulai: Input Problem]
       │
       ▼
[Inisialisasi Root State (S0)]
       │
       ├───────────────────────────────────────────────┐
       ▼                                               ▼
[Thought Generator: K-Expansion]             [Check Frontier Empty?]
       │                                               │
       ▼                                               ├─ YES -> [Throw/Fallback]
[Thought Evaluator: Batched Value Engine]              └─ NO  -> [Lanjut Iterasi]
       │
       ▼
[Prune Node: If V(s) < Threshold?] ── YES ──> [Tandai Dead-End & Buang]
       │
      NO
       │
       ▼
[Graph Transformation / Aggregation Engine]
       │
       ▼
[Evaluasi Status Terminasi: Is Goal Reached?]
       │
       ├─ TIDAK ──> [Update Frontier & Backtrack/Explore Next] ──> Loop ke Generator
       │
      YA
       │
       ▼
[Path Synthesizer: Susun Lintasan Optimal]
       │
       ▼
[Determinasi Self-Consistency / Consensus Validation]
       │
       ▼
[Kirim Output Akhir]
```

1. **Inisialisasi State Root ($S_0$):** Problem diurai menjadi state awal yang mencakup batasan, metadata input, invariant constraint, dan token budget.
2. **K-Step Expansion (Thought Generation):**
   * Panggil LLM secara async menggunakan batch prompting.
   * Setiap thought baru dipetakan sebagai node anak ($S_{t+1}^{(i)}$) dari node saat ini.
3. **Batched State Evaluation (Value Modeling):**
   * Thought Evaluator mengevaluasi validitas setiap state anak secara paralel menggunakan criteria-based rubric (skor $0.0$ s.d $1.0$).
   * Node dengan skor di bawah threshold $\theta$ langsung dieliminasi dari *frontier*.
4. **Graph Transformation & Aggregation:**
   * Jika terdapat dua node yang melengkapi sub-komponen masalah yang berbeda, GoT memanggil agregator untuk menggabungkan state keduanya menjadi satu kesatuan context.
5. **Termination / Backtracking Decision:**
   * Jika path saat ini buntu (*dead end*), search engine memutar balik ke ancestor node terdekat yang masih memiliki unexplored frontier (backtracking).
   * Jika node mencapai kriteria terminasi (*goal state*), search dihentikan.
6. **Path Synthesis & Final Output Compilation:**
   * Traceback dari root ke goal node diekstrak. Seluruh path diintegrasikan menjadi satu rantai penalaran deterministik akhir.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Navigasi Labirin vs. Ekspedisi Peta Bersama
*   **Linear CoT:** Seorang penjelajah yang berjalan di dalam labirin gelap hanya dengan melihat satu langkah di depannya. Sekali ia berbelok salah, ia akan terus berjalan hingga menemui jalan buntu tanpa sadar di mana kesalahannya bermula.
*   **Tree-of-Thoughts (ToT):** Mengirimkan drone kecil di setiap persimpangan labirin, mengevaluasi kemungkinan jalan keluar dari udara, membatalkan jalur yang buntu (*backtracking*), lalu melangkah hanya pada jalur yang paling menjanjikan.
*   **Graph-of-Thoughts (GoT):** Tiga kelompok penjelajah memasuki labirin dari sudut berbeda, saling berkomunikasi melalui radio, menyatukan peta parsial mereka di titik temu (*aggregation*), mengeliminasi area buntu bersama-sama, dan membentuk rute evakuasi tercepat.

```
       ======================= GRAPH-OF-THOUGHTS (GoT) TOPOLOGY =======================

              [State Root: S0] (Analisis Anomali Finansial Transaksi X)
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
    [Thought 1A]            [Thought 1B]
 (Validasi Log Mutasi)   (Analisis Metadata IP)
         │                       │
         ▼                       ▼
    [Thought 2A]            [Thought 2B]
 (Deteksi Smurfing)      (Deteksi Tor Node)
         │                       │
         └───────────┬───────────┘
                     ▼  << AGGREGATION & CROSS-VALIDATION >>
                [Thought 3]
     (Sintesis: Terkonfirmasi Pencucian Uang)
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
    [Thought 4A]            [Thought 4B]  
 (Drafting Laporan SAR)  (Mitigasi Langsung Freeze)
      [Skor: 0.95]            [Skor: 0.40] -> [PRUNED via Value Threshold]
         │
         ▼
     [TERMINAL: Eksekusi Laporan SAR]
```

---

### 7. Simple Example & Practical Example

#### Implementasi Standar Industri: Tree-of-Thoughts Asynchronous Search Engine

Implementasi Python modular dan *production-ready* berikut mengimplementasikan Tree-of-Thoughts menggunakan Pydantic v2, evaluasi state terisolasi, dan strategi pencarian terpandu (*Beam Search*) lengkap dengan batasan token budget.

```python
"""
tot_search_engine.py
Enterprise-grade Tree-of-Thoughts (ToT) Inference Engine with Beam Search
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ToTEngine")


# ==========================================
# Domain Schemas & State Representations
# ==========================================

class ThoughtEvaluation(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0, description="Kelayakan pemikiran dari 0.0 sampai 1.0")
    reasoning: str = Field(..., description="Justifikasi evaluasi heuristik terhadap batasan sistem")
    is_terminal: bool = Field(default=False, description="Apakah thought ini mencapai solusi akhir")


class ThoughtNode(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    parent_id: Optional[UUID] = None
    depth: int = 0
    content: str
    score: float = 0.0
    is_terminal: bool = False
    children_ids: List[UUID] = Field(default_factory=list)

    def context_chain(self, node_lookup: Dict[UUID, ThoughtNode]) -> List[str]:
        chain = []
        curr: Optional[ThoughtNode] = self
        while curr:
            chain.append(curr.content)
            curr = node_lookup.get(curr.parent_id) if curr.parent_id else None
        return list(reversed(chain))


# ==========================================
# LLM Mock Client Interface (Deterministic)
# ==========================================

class LLMInterface:
    """Mock interface representatif yang mensimulasikan LLM response."""
    
    async def generate_proposals(self, context_chain: List[str], problem: str, k: int) -> List[str]:
        await asyncio.sleep(0.05)  # Simulate network I/O
        depth = len(context_chain)
        if depth == 0:
            return [
                "Langkah 1: Parsing log transaksi dan ekstraksi pola transfer berulang.",
                "Langkah 1: Hubungkan identitas pengirim dengan histori KYC regional.",
                "Langkah 1: Abaikan histori dan langsung cek nilai transaksi saat ini."
            ][:k]
        elif depth == 1:
            return [
                "Langkah 2: Temukan pencocokan struktur transaksi split-deposit (Smurfing).",
                "Langkah 2: Verifikasi anomali IP address dan geolocation pengguna."
            ][:k]
        else:
            return [
                "Langkah 3 (Konklusif): Terdeteksi skema structuring. Buat rekomendasi pembekuan rekening."
            ][:k]

    async def evaluate_thought(self, problem: str, context_chain: List[str], thought: str) -> ThoughtEvaluation:
        await asyncio.sleep(0.03)  # Simulate latency
        full_context = " -> ".join(context_chain + [thought])
        
        # Heuristik simulasi berbasis aturan context
        if "Abaikan histori" in thought:
            return ThoughtEvaluation(
                score=0.1,
                reasoning="Melanggar regulasi AML; histori wajib diaudit.",
                is_terminal=False
            )
        if "Langkah 3 (Konklusif)" in thought:
            return ThoughtEvaluation(
                score=0.98,
                reasoning="Solusi berhasil diverifikasi dengan bukti struktural mutasi.",
                is_terminal=True
            )
        return ThoughtEvaluation(
            score=0.85,
            reasoning="Langkah relevan dan mempertahankan kepatuhan metodologi.",
            is_terminal=False
        )


# ==========================================
# Tree-of-Thoughts Beam Search Controller
# ==========================================

class TreeOfThoughtsSearchEngine:
    def __init__(
        self,
        llm: LLMInterface,
        max_depth: int = 3,
        beam_width: int = 2,
        k_proposals: int = 3,
        pruning_threshold: float = 0.5
    ):
        self.llm = llm
        self.max_depth = max_depth
        self.beam_width = beam_width
        self.k_proposals = k_proposals
        self.pruning_threshold = pruning_threshold
        self.node_store: Dict[UUID, ThoughtNode] = {}

    async def solve(self, problem: str) -> Optional[ThoughtNode]:
        root = ThoughtNode(content="ROOT: " + problem, depth=0, score=1.0)
        self.node_store[root.id] = root
        
        current_beam: List[ThoughtNode] = [root]

        for step in range(self.max_depth):
            logger.info(f"--- PENCARIAN LEVEL {step + 1} (Ukuran Beam Aktif: {len(current_beam)}) ---")
            candidate_children: List[ThoughtNode] = []

            # 1. Expand each beam candidate asynchronously
            expansion_tasks = []
            for node in current_beam:
                chain = node.context_chain(self.node_store)
                expansion_tasks.append(
                    self._expand_node(node, chain, problem)
                )

            expanded_results = await asyncio.gather(*expansion_tasks)
            for children in expanded_results:
                candidate_children.extend(children)

            if not candidate_children:
                logger.warning("Tidak ada kandidat cabang valid ditemukan. Frontier buntu.")
                break

            # 2. Prune candidates under threshold
            surviving_candidates = [
                node for node in candidate_children if node.score >= self.pruning_threshold
            ]
            logger.info(f"Kandidat tergenerasi: {len(candidate_children)}, Lolos pruning: {len(surviving_candidates)}")

            if not surviving_candidates:
                logger.error("Seluruh pemikiran dieliminasi oleh threshold evaluasi heuristik.")
                break

            # 3. Check for terminal condition
            terminals = [n for n in surviving_candidates if n.is_terminal]
            if terminals:
                # Ambil solusi terminal dengan skor heuristik tertinggi
                best_terminal = max(terminals, key=lambda n: n.score)
                logger.info(f"Target terminal tercapai pada depth {step + 1} dengan skor {best_terminal.score:.2f}")
                return best_terminal

            # 4. Beam selection: Ambil top-K node terbaik berdasarkan skor
            surviving_candidates.sort(key=lambda n: n.score, reverse=True)
            current_beam = surviving_candidates[: self.beam_width]

        # Ambil thought terbaik yang tersedia jika max_depth tercapai tanpa terminal eksplisit
        if current_beam:
            current_beam.sort(key=lambda n: n.score, reverse=True)
            return current_beam[0]
        return None

    async def _expand_node(
        self, parent: ThoughtNode, chain: List[str], problem: str
    ) -> List[ThoughtNode]:
        proposals = await self.llm.generate_proposals(chain, problem, self.k_proposals)
        
        evaluation_tasks = [
            self.llm.evaluate_thought(problem, chain, prop) for prop in proposals
        ]
        evaluations: List[ThoughtEvaluation] = await asyncio.gather(*evaluation_tasks)

        generated_nodes: List[ThoughtNode] = []
        for prop, ev in zip(proposals, evaluations):
            child_node = ThoughtNode(
                parent_id=parent.id,
                depth=parent.depth + 1,
                content=prop,
                score=ev.score,
                is_terminal=ev.is_terminal
            )
            self.node_store[child_node.id] = child_node
            parent.children_ids.append(child_node.id)
            generated_nodes.append(child_node)

        return generated_nodes


# ==========================================
# Driver Execution Test
# ==========================================

async def main():
    problem = "Analisis pola transfer berulang sebesar Rp 99.000.000 sebanyak 15 kali dalam 2 jam."
    engine = TreeOfThoughtsSearchEngine(
        llm=LLMInterface(),
        max_depth=3,
        beam_width=2,
        k_proposals=3,
        pruning_threshold=0.6
    )

    best_node = await engine.solve(problem)

    if best_node:
        print("\n=== SOLUSI PENALARAN TERBAIK DITEMUKAN ===")
        full_trajectory = best_node.context_chain(engine.node_store)
        for i, step_desc in enumerate(full_trajectory):
            print(f"[{i}] {step_desc}")
        print(f"Final Path Confidence Score: {best_node.score}")
    else:
        print("Gagal menemukan solusi penalaran yang memuaskan.")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Domain: Investigasi Forensik Finansial & Kepatuhan Regulasi Otomatis (Global Banking System)

#### Skenario Masalah
Sebuah bank multinasional memproses lebih dari 5.000.000 transaksi harian. Regulator mewajibkan pelaporan *Suspicious Activity Report* (SAR) secara mendalam untuk kasus dugaan pencucian uang lintas batas (*layering*, *structuring*, *smurfing*). 
Sebelumnya, sistem berbasis linear prompt mengalami kendala:
* 35% SAR yang dihasilkan LLM ditolak auditor internal karena model gagal memvalidasi dependensi temporal antar-rekening (*compounding deduction failure*).
* Model konvensional tidak mampu mundur (*backtrack*) ketika hipotesis awal transaksi sah ternyata bertentangan dengan bukti log mutasi bank koresponden di tahapan akhir.

#### Arsitektur Solusi Berbasis Graph-of-Thoughts (GoT)

```
[Incoming Alert Event] -> [Kafka: TxAlertTopic]
                               │
                               ▼
        [Financial Forensic Orchestrator (GoT Controller)]
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
 [Branch A: Temporal Tx Graph]         [Branch B: KYC Graph Entity]
            │                                     │
            └──────────────────┬──────────────────┘
                               ▼
                  [GoT Aggregator & Valuator]
                               │
                   (Heuristic Check Passed?)
                    ├── TIDAK: Backtrack & Redo Subgraph
                    └── YA: Lanjut ke Tax Identification
                               │
                               ▼
            [Deterministic Path Synthesis -> SAR Generator]
                               │
                               ▼
                     [Core Banking AML Engine]
```

1. **State Partitioning:** Kasus dipecah menjadi sub-graf investigasi: Sub-graf A mengevaluasi runut waktu mutasi finansial; Sub-graf B memvalidasi metadata entitas (Beneficial Ownership, PEP status).
2. **Dynamic Aggregation:** Setelah kedua cabang independen divalidasi oleh Value Prompts spesifik, controller GoT menggabungkan kedua state menjadi *Unified Forensic Assertion*.
3. **Backtracking Loop:** Jika data Beneficial Ownership di yurisdiksi offshore membuktikan bahwa entitas tujuan adalah anak perusahaan resmi yang terafiliasi, sistem secara otomatis mengeksekusi backtracking, memangkas cabang dugaan *layering*, dan beralih ke cabang verifikasi *transfer pricing*.

#### Hasil Pengujian & Dampak Bisnis
*   **Akurasi Deductive Audit:** Peningkatan akurasi audit SAR dari 65% menjadi 98.4% sesuai standar FIU (*Financial Intelligence Unit*).
*   **Penurunan False-Positive Escalation:** Mengurangi eskalasi manual oleh analis manusia sebesar 42%.
*   **Latensi Terkontrol:** Dengan implementasi Beam Search ($W=2$) dan parallel async evaluation, rata-rata durasi penyelesaian audit hanya 4.2 detik per kasus transaksi kompleks, jauh di bawah SLA regulasi (30 detik).

---

### 9. Trade-offs

| Dimensi Arsitektural | Linear Chain-of-Thought (CoT) | Tree-of-Thoughts (ToT) | Graph-of-Thoughts (GoT) | Dynamic Self-Consistency |
| :--- | :--- | :--- | :--- | :--- |
| **Token Consumption** | **Sangat Rendah** ($1\times$) | **Tinggi** ($5\times - 15\times$) | **Sangat Tinggi** ($10\times - 30\times$) | **Tinggi** ($N \times \text{Linear}$) |
| **End-to-End Latency** | Rendah (~1.5s) | Tinggi (~5s - 12s) | Sangat Tinggi (~8s - 25s) | Sedang (dapat diparalelisasi penuh) |
| **Algorithmic Complexity**| Minimal (Single pass) | Menengah (Tree search, pruning) | Sangat Kompleks (DAG cycle management, state aggregation) | Rendah (Map-Reduce / Consensus clustering) |
| **Kemampuan Koreksi** | Tidak ada | Penuh (via Backtracking) | Superior (Backtracking + Graph loop refinement) | Terbatas pada frekuensi statistik konsensus |
| **Ideal Use Case** | Text summarization, Q&A fakta sederhana | Audit Finansial, Perencanaan Logistik Kompleks | R&D Molekuler, Analisis Intelijen Multi-Sumber | Ekstraksi Data Kritis, Klasifikasi Kategorikal Baku |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Context Window Exhaustion pada Branching Dalam
*   *Penyebab:* Developer menyalin seluruh histori pencarian pohon ke dalam context window setiap kali membangkitkan child node baru.
*   *Troubleshooting:* Terapkan arsitektur **Delta State Encoding**. Node hanya menyimpan representasi mutasi (*delta*) dari parent-nya. Sintesis context penuh hanya dilakukan saat evaluasi via generator fungsi `context_chain()`, bukan menyalin payload data besar secara statis.

#### 2. Evaluator Score Inflation (Semua Cabang Bernilai Tinggi)
*   *Penyebab:* Value prompt terlalu generik (contoh: *"Beri nilai 1-10 untuk langkah ini"*), sehingga LLM evaluator cenderung memberikan nilai 8-10 (*sycophancy effect*).
*   *Troubleshooting:* Wajibkan evaluasi kategorial biner atau kriteria berbobot menggunakan Pydantic. Paksa evaluator mencari potensi kesalahan logika terlebih dahulu sebelum mengizinkan skor di atas batas threshold:
    ```json
    {
      "flaws_detected": ["Variabel X belum dideklarasikan"],
      "confidence": 0.2,
      "decision": "PRUNE"
    }
    ```

#### 3. Deadlock pada Graph of Thoughts (Cycle Loop Dependencies)
*   *Penyebab:* Thought refinement pada GoT membentuk cycle dependency tanpa *progress metric*.
*   *Troubleshooting:* Batasi `max_refinement_steps` secara ketat pada setiap node dan implementasikan *Directed Acyclic Graph (DAG) validation* sebelum operasi agregasi dilakukan.

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic Sampling Parameterization:** Kunci `temperature=0.0` untuk Evaluator/Value prompts, dan gunakan `temperature=0.7` dengan `top_p=0.9` secara terkendali khusus pada Proposer/Thought Generator.
- [ ] **Parallel Async Execution:** Bungkus seluruh eksekusi evaluasi node kandidat menggunakan `asyncio.gather` dengan `asyncio.Semaphore` untuk mencegah *rate-limit exhaustion* (HTTP 429).
- [ ] **Structural Pruning Threshold:** Tetapkan ambang batas pemangkasan secara ketat (misal: $\theta < 0.65$ otomatis di-*drop* dari memori aktif).
- [ ] **Semantic Caching:** Simpan hasil evaluasi pasangan `(Parent_Hash, Thought_Proposal)` pada Redis untuk menghindari pemanggilan ganda pada subtree penalaran yang identik.
- [ ] **Token Circuit Breaker:** Tetapkan batas maksimal konsumsi token per sesi search. Jika akumulasi token mencapai 80% dari batas kuota, degradasi algoritma secara otomatis ke *Linear CoT Greedy Fallback*.
- [ ] **Immutable Node Representation:** Desain node graf sebagai immutable data structures guna mencegah *race conditions* selama traversal paralel.

---

### 12. Hands-on Practice

Buka direktori repositori Anda dan arahkan ke `hands-on/m02/`.

#### Langkah 1: Persiapan Environment
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
python -m venv venv
source venv/bin/activate
pip install pydantic openai numpy networkx
```

#### Langkah 2: Mengimplementasikan Advanced Self-Consistency Engine dengan Dynamic Semantic Stopping
Buat berkas `hands-on/m02/dynamic_self_consistency.py` dan salin kode implementasi berikut:

```python
"""
hands-on/m02/dynamic_self_consistency.py
Dynamic Self-Consistency Engine with Embedding-based Semantic Clustering
"""

import asyncio
from typing import List, Dict, Counter
from pydantic import BaseModel
import numpy as np

class ConsensusResult(BaseModel):
    selected_answer: str
    confidence_score: float
    total_samples_evaluated: int
    cluster_distribution: Dict[str, int]

class MockInferenceService:
    async def sample_cot_reasoning(self, prompt: str, seed: int) -> str:
        await asyncio.sleep(0.02)
        # Simulasi variasi penalaran probabilistik
        outcomes = [
            "Jawaban: Rp 450.000.000 (Metode: Amortisasi Garis Lurus)",
            "Jawaban: Rp 450.000.000 (Metode: Perhitungan Depresiasi Fiskal)",
            "Jawaban: Rp 450.000.000 (Metode: Konsensus Nilai Buku)",
            "Jawaban: Rp 300.000.000 (Metode: Salah Eliminasi Saldo Awal)",
        ]
        return outcomes[seed % len(outcomes)]

    async def get_embedding(self, text: str) -> np.ndarray:
        # Simulasi embedding deterministik sederhana
        val = sum(ord(c) for c in text.split()[1]) # Ambil hash dari jawaban
        np.random.seed(val)
        vec = np.random.randn(128)
        return vec / np.linalg.norm(vec)

class DynamicSelfConsistencyEngine:
    def __init__(self, inference_service: MockInferenceService, min_samples: int = 3, max_samples: int = 10, confidence_target: float = 0.75):
        self.client = inference_service
        self.min_samples = min_samples
        self.max_samples = max_samples
        self.confidence_target = confidence_target

    async def execute(self, prompt: str) -> ConsensusResult:
        sampled_answers: List[str] = []
        
        for i in range(self.max_samples):
            # 1. Generate sample CoT
            sample = await self.client.sample_cot_reasoning(prompt, seed=i)
            # Ekstraksi target deterministik
            parsed = sample.split("(")[0].strip()
            sampled_answers.append(parsed)

            # 2. Check stopping condition jika sample telah memenuhi syarat minimal
            if len(sampled_answers) >= self.min_samples:
                counts = Counter(sampled_answers)
                most_common_answer, highest_count = counts.most_common(1)[0]
                current_confidence = highest_count / len(sampled_answers)

                if current_confidence >= self.confidence_target:
                    return ConsensusResult(
                        selected_answer=most_common_answer,
                        confidence_score=current_confidence,
                        total_samples_evaluated=len(sampled_answers),
                        cluster_distribution=dict(counts)
                    )

        counts = Counter(sampled_answers)
        most_common_answer, highest_count = counts.most_common(1)[0]
        return ConsensusResult(
            selected_answer=most_common_answer,
            confidence_score=highest_count / len(sampled_answers),
            total_samples_evaluated=len(sampled_answers),
            cluster_distribution=dict(counts)
        )

if __name__ == "__main__":
    async def run():
        engine = DynamicSelfConsistencyEngine(MockInferenceService())
        res = await engine.execute("Hitung sisa amortisasi aset per Q4")
        print("\n=== HASIL DYNAMIC SELF-CONSISTENCY ===")
        print(f"Jawaban Terpilih : {res.selected_answer}")
        print(f"Tingkat Keyakinan: {res.confidence_score * 100:.1f}%")
        print(f"Total Sampel LLM : {res.total_samples_evaluated}")
        print(f"Distribusi Vote  : {res.cluster_distribution}")

    asyncio.run(run())
```

---

### 13. Exercise

#### Tingkat Easy
Modifikasi implementasi `TreeOfThoughtsSearchEngine` pada modul ini agar mencatat metrik total LLM tokens yang diasumsikan digunakan selama proses search. Cetak token expenditure pada akhir output.

#### Tingkat Medium
Implementasikan fungsi DFS (Depth-First Search) dengan mekanisme *Backtracking Limit*. Jika sebuah cabang mencapai depth 2 dengan skor $< 0.4$, batalkan cabang tersebut dan kembali ke root state, dengan batas pengulangan maksimal 3 kali sebelum return `None`.

#### Tingkat Hard
Bangun implementasi `GraphOfThoughtsEngine` yang mendukung operasi **Aggregation**: Ambil 2 node berbeda dari frontier yang sama, gabungkan konteks keduanya menggunakan Aggregator Prompt, lalu hitung value score gabungan tersebut. Jika skor gabungan $> \max(score_1, score_2)$, prioritaskan node gabungan tersebut sebagai frontier utama.

---

### 14. Challenge

**Skenario Tantangan Enterprise:**
Rancang dan bangun arsitektur sistem penalaran **"Autonomous Distributed Incident Commander"** untuk menangani kegagalan cluster Kubernetes pada infrastruktur tier-1 banking.

**Spesifikasi Persyaratan:**
1. Mesin harus mengimplementasikan **Tree-of-Thoughts / GoT Hybrid**.
2. Graf penalaran harus memproses input secara simultan: Metrics anomaly (Prometheus), Trace errors (Jaeger), dan Kubernetes Event Logs.
3. Mesin dilarang mengeksekusi aksi mitigasi (seperti *Pod Eviction* atau *Node Drain*) kecuali rantai penalaran telah divalidasi oleh Value Prompts dengan skor keyakinan $\ge 0.95$ dan tidak melanggar *Policy Invariant* (misalnya: ketersediaan kapasitas min-replica).
4. Sediakan mekanisme *Circuit Breaker*: Jika kedalaman pencarian mencapai level 5 tanpa solusi terminasi, sistem harus secara otomatis beralih ke mitigasi linier deterministik (*Graceful Failover*) dan membunyikan alarm PagerDuty.

*Tuliskan arsitektur class Pydantic, state transitions, dan async runner engine secara mandiri tanpa menggunakan library abstraksi tingkat tinggi (seperti LangChain/LlamaIndex).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa kelemahan utama dari paradigma linear Chain-of-Thought (CoT) dalam komputasi inferensi?
   * A. Menghabiskan token sepuluh kali lebih banyak daripada ToT.
   * B. Kerentanan terhadap compounding errors tanpa kapabilitas evaluasi mundur (backtracking).
   * C. Tidak mendukung structured output JSON schema.
   * D. Latensi inferensi lebih tinggi dibanding model search graf.
   * *Jawaban yang Benar:* **B**

2. Pada implementasi Tree-of-Thoughts, apa tugas utama dari modul *Thought Evaluator* (Value Prompt)?
   * A. Menghasilkan cabang kalimat baru sebanyak $K$ variasi.
   * B. Menghitung cosine similarity embedding antara prompt dan respon.
   * C. Memberikan penilaian heuristik terhadap probabilitas keberhasilan atau validitas suatu state.
   * D. Mengurangi latensi jaringan dengan melakukan kompresi payload HTTP.
   * *Jawaban yang Benar:* **C**

3. Mengapa parameter `temperature` pada Value Prompt Evaluator idealnya disetel mendekati 0.0?
   * A. Untuk menghasilkan jawaban sekreatif mungkin.
   * B. Untuk memastikan evaluasi heuristik terhadap batasan invariant bersifat konsisten dan deterministik.
   * C. Untuk mengelabui context window model.
   * D. Untuk mempercepat token-per-second generator.
   * *Jawaban yang Benar:* **B**

4. Karakteristik pembeda utama antara Graph-of-Thoughts (GoT) dengan Tree-of-Thoughts (ToT) adalah:
   * A. GoT tidak menggunakan Large Language Model.
   * B. GoT mendukung operasi agregasi multi-node dan loop refinement pada state space.
   * C. GoT selalu membutuhkan biaya token yang lebih murah dibanding linear CoT.
   * D. ToT tidak dapat digunakan bersama Beam Search.
   * *Jawaban yang Benar:* **B**

5. Konsep *Self-Consistency* pertama kali diperkenalkan untuk mengatasi:
   * A. Biaya komputasi GPU yang terlalu mahal.
   * B. Variabilitas sampling stokastik pada CoT dengan cara mengambil konsensus mayoritas dari ragam lintasan inferensi.
   * C. Ketiadaan tokenizer byte-pair encoding.
   * D. Limitasi ukuran memori Redis cache.
   * *Jawaban yang Benar:* **B**

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Kasus)
6. Manakah strategi pruning yang paling tepat jika sistem Anda memiliki batasan ketat pada End-to-End Latency?
   * A. Exhaustive Breadth-First Search (BFS) tanpa thresholding.
   * B. Beam Search terpandu dengan beam width kecil ($W \le 3$) dan pemangkasan threshold agresif.
   * C. Full Depth-First Search dengan unconstrained backtracking.
   * D. Mengambil seluruh $N$ path acak lalu menggabungkannya ke dalam satu prompt raksasa.
   * *Jawaban yang Benar:* **B**

7. Apa konsekuensi teknis jika kita menggunakan semantic distance clustering pada output Self-Consistency daripada *Exact String Matching*?
   * A. Mengurangi latensi inferensi LLM hingga 90%.
   * B. Mampu mengelompokkan jawaban yang secara semantik bermakna sama namun memiliki variasi sintaksis/kalimat yang berbeda.
   * C. Menghilangkan kebutuhan akan embedding model.
   * D. Membatasi pencarian hanya pada domain matematika diskrit.
   * *Jawaban yang Benar:* **B**

8. Kapan mekanisme backtracking pada Tree-of-Thoughts dieksekusi?
   * A. Ketika seluruh node anak pada cabang frontier saat ini menghasilkan evaluasi heuristik di bawah batas kelayakan ($V(S) < \theta$).
   * B. Segera setelah root node dibangkitkan oleh sistem.
   * C. Saat context window LLM tersisa 50%.
   * D. Hanya jika diperintahkan secara manual oleh operator manusia via Webhook.
   * *Jawaban yang Benar:* **A**

9. Apa fungsi dari *Delta State Encoding* dalam arsitektur pencarian graf penalaran skala besar?
   * A. Mengenkripsi prompt untuk mematuhi regulasi GDPR.
   * B. Menyimpan hanya selisih mutasi state antar-node guna mencegah kehabisan batas token context window.
   * C. Menghitung gradien loss secara realtime saat inferensi.
   * D. Membagi komputasi LLM ke multi-GPU clusters.
   * *Jawaban yang Benar:* **B**

10. Bagaimana cara mencegah *Evaluator Sycophancy* pada pengujian state penalaran?
    * A. Memberikan prompt reward positif setiap kali evaluator memberi skor tinggi.
    * B. Memaksa model evaluator mencari bukti kesalahan invariant logika terlebih dahulu sebelum menerbitkan skor.
    * C. Menaikkan temperature evaluasi ke 1.0.
    * D. Menghapus batasan kriteria evaluasi dari system prompt.
    * *Jawaban yang Benar:* **B**

#### Bagian 3: Production Scenario Analysis (Studi Kasus Arsitektural)

##### Skenario Kasus 1:
Sebuah sistem analisis kredit perbankan menggunakan Tree-of-Thoughts. Pada jam sibuk, sistem mengalami lonjakan HTTP 429 (Rate Limit Exceeded) dari penyedia LLM API, yang menyebabkan thread search mengalami hanging dan request timeout di level gateway.
*Pertanyaan Analisis:* Solusi rekayasa arsitektural apa yang wajib diimplementasikan untuk mempertahankan keandalan sistem tanpa mematikan proses reasoning ToT?
*Analisis Solusi:* 
1. **Implementasi Asynchronous Concurrency Limiter (Semaphore):** Batasi jumlah *concurrent requests* menuju provider sesuai alokasi RPM/TPM akun enterprise.
2. **Exponential Backoff dengan Jitter:** Terapkan retry pattern adaptif pada level HTTP client.
3. **Graceful Fallback Degrader:** Jika queue pending requests melebihi ambang batas aman (high water mark), turunkan konfigurasi `beam_width` secara otomatis dari $W=3$ menjadi $W=1$ (Linear CoT mode) untuk memotong konsumsi request API seketika demi menjaga ketersediaan sistem.

##### Skenario Kasus 2:
Mesin Graph-of-Thoughts untuk sintesis diagnosa medis mengalami kondisi di mana dua cabang pengamatan independen menghasilkan fakta yang saling bertolak belakang (Contoh Cabang A: *"Pasien menunjukkan kontraindikasi terhadap Obat X"*; Cabang B: *"Obat X wajib diberikan segera untuk menstabilkan kondisi Y"*). Modul agregator gagal memproses output dan menghasilkan halusinasi looping.
*Pertanyaan Analisis:* Pola arsitektur mitigasi apa yang harus diterapkan pada Node Aggregator GoT?
*Analisis Solusi:* 
Terapkan **Conflict Resolution Arbitrator Sub-graph**. Node agregator tidak boleh langsung memaksakan sintesis kesimpulan. Controller harus mendeteksi kontradiksi logis melalui assertion check: jika terdapat konflik kontraindikasi, controller secara otomatis memicu node arbitrase independen yang bertugas mencari *higher-order medical guidelines* atau secara deterministik memangkas cabang treatment dan menandai kasus untuk tinjauan manual dokter (*Human-in-the-loop escalation*), menjaga safety invariant pasien.

##### Skenario Kasus 3:
Sistem multi-agent Anda mengeksekusi Dynamic Self-Consistency dengan 10 sampel paralel untuk melakukan validasi formasi kontrak hukum. Biaya operasional token bulanan melambung $800\%$ melebihi budget alokasi finansial.
*Pertanyaan Analisis:* Bagaimana memodifikasi algoritma Self-Consistency agar tetap mempertahankan akurasi tanpa memicu komputasi 10 sampel secara redundan?
*Analisis Solusi:*
Terapkan **Sequential Dynamic Early-Stopping**. Alih-alih membangkitkan ke-10 sampel secara paralel di awal (*wasteful batching*), jalankan inferensi secara bertahap (misalnya batch berukuran $K=3$). Hitung consensus margin setelah batch pertama selesai: jika ketiga sampel ($100\%$) menghasilkan konvergensi semantik yang sama, batalkan iterasi berikutnya (*early exit*) dan langsung gunakan hasilnya. Hanya dispatch sampel tambahan jika terjadi dispersi voting antar sampel awal.

---

### 16. Summary

```
                      ADVANCED REASONING SYSTEM TAXONOMY
                      
             Complexity & Token Consumption
                    ▲
                    │                   [Graph-of-Thoughts (GoT)]
                    │                   • Arbitrary Graph / DAG
                    │                   • Aggregation & Feedback
                    │                   • Superior Error Recovery
                    │
                    │         [Tree-of-Thoughts (ToT)]
                    │         • State Space Tree
                    │         • Beam Search / DFS
                    │         • Backtracking Capability
                    │
                    │   [Self-Consistency]
                    │   • Parallel Sampling
                    │   • Semantic Clustering
                    │   • Stochastic Smoothing
                    │
                    │ [Linear CoT]
                    │ • Single Pass Auto-regressive
                    │ • Zero Backtracking
                    └────────────────────────────────────────► Reasoning Robustness
```

1. **Transformasi Paradigma:** Penalaran tingkat lanjut mengubah interaksi model dari pemanggilan autoregresif sekuensial sederhana menjadi **pencarian ruang keadaan terpandu (heuristic state-space traversal)**.
2. **Kompensasi Keterbatasan Model:** Tree-of-Thoughts dan Graph-of-Thoughts mengeliminasi kerentanan kegagalan CoT linier (*compounding error*) dengan menghadirkan kapabilitas backtracking, pruning, dan node aggregation secara sistematis.
3. **Engineering Rigor:** Keberhasilan penerapan paradigma ini dalam sistem produksi enterprise bergantung penuh pada kontrol latensi, arsitektur asynchronous non-blocking, caching semantik, validasi invariant berbasis skema terstruktur, dan penanganan graceful degradation saat menghadapi batasan kuota komputasi.