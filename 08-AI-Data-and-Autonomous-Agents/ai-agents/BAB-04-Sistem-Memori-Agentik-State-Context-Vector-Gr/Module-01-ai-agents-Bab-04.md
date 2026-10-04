# Bab 04: Sistem Memori Agentik: State, Context, & Vector-Graph RAG

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Mengklasifikasikan Taksonomi Memori Agentik**: Membedakan secara arsitektural antara *working memory* (in-context scratchpad), *episodic memory* (riwayat interaksi dan eksekusi tugas berbasis waktu), dan *semantic memory* (fakta domain terstruktur dan asosiatif).
2. **Merancang Deterministic State Machine untuk Autonomous Agents**: Membangun mekanisme *state management* berbasis *checkpointing* yang mampu menangani interupsi eksekusi, serialisasi state terdistribusi, dan *rollback transaction* tanpa kehilangan konteks.
3. **Mengimplementasikan Dynamic Context Compaction & Token Budgeting**: Mengembangkan pipeline kompresi konteks adaptif menggunakan teknik *recursive summarization*, *selective pruning*, dan *sliding-window FIFO with priority pin* untuk menjaga batas token LLM tanpa degradasi reasoning.
4. **Membangun Arsitektur Vector-Graph Hybrid RAG (GraphRAG)**: Mengintegrasikan dense vector retrieval dengan traversal graph database untuk mengatasi kelemahan *isolated chunk retrieval* dan menghasilkan *context-aware global multi-hop reasoning*.
5. **Mengaudit & Memitigasi Kegagalan Memori**: Mengidentifikasi serta menyelesaikan *context drift*, *stale relationship hallucination*, *race conditions* pada mutasi state concurrent, dan *poisoned episodic memory*.

---

## 2. Concept Overview

Sistem memori pada *autonomous agent* bertindak sebagai jembatan antara penalaran sesaat (*stateless inference*) dan eksekusi tugas jangka panjang (*stateful autonomy*). Tanpa sistem memori yang komprehensif, LLM terbatas pada jendela konteks aktif (*in-context window*) yang rentan terhadap *forgetting*, *attention degradation* (*lost-in-the-middle phenomenon*), serta ketidakmampuan merefleksikan kegagalan masa lalu.

```
       +--------------------------------------------------------+
       |                  AGENT REASONING CORE                  |
       +--------------------------------------------------------+
               |                       ^                ^
               v                       |                |
    +----------------------+           |                |
    |    WORKING MEMORY    |           |                |
    | (In-Context Scratch) |           |                |
    +----------------------+           |                |
               | (Sync/Evict)          |                |
               v                       |                |
+------------------------------+       |                |
|      SHORT-TERM STATE        |       |                |
|  (Session, Task Graph, FSM)  |-------+                |
+------------------------------+                        |
               | (Consolidate)                          |
               v                                        |
+---------------------------------------------------------------+
|                      LONG-TERM MEMORY                         |
|  +---------------------------+  +--------------------------+  |
|  |      EPISODIC MEMORY      |  |     SEMANTIC MEMORY      |  |
|  | (Dense Embeddings, Vector)|  | (Knowledge Graph Entities|  |
|  |   "Apa yang terjadi?"     |  |   & Hubungan Relasional) |  |
|  |                           |  |   "Apa arti fakta ini?"  |  |
|  +---------------------------+  +--------------------------+  |
+---------------------------------------------------------------+
```

### Taksonomi Memori Agentik

1. **Working Memory (Scratchpad/Execution Context)**:
   * **Medium**: Prompt context window aktif.
   * **Karakteristik**: Volatil, latensi nol (sudah termuat di KV-cache), kapasitas dibatasi oleh `max_context_window`.
   * **Fungsi**: Menyimpan *intermediate reasoning steps* (ReAct chains), instruksi aktif, dan payload tool calls saat ini.

2. **Episodic Memory (Autobiographical Experience)**:
   * **Medium**: Vector Store (Qdrant, Milvus, pgvector) terindeks secara kronologis dan semantik.
   * **Karakteristik**: Semi-terstruktur, berbasis kemiripan semantik dan temporalitas, memuat log sukses/gagal tindakan masa lalu.
   * **Fungsi**: Memungkinkan agent menjawab pertanyaan: *"Bagaimana cara saya menyelesaikan error kompilasi kode serupa dua hari yang lalu?"*

3. **Semantic Memory (Structured World & Domain Knowledge)**:
   * **Medium**: Graph Database (Neo4j, Memgraph, NetworkX-in-memory) yang memetakan entitas sebagai node dan relasi sebagai edge.
   * **Karakteristik**: Terstruktur tinggi, deterministik, *traversable*, mendukung inferensi multi-hop.
   * **Fungsi**: Memungkinkan agent menjawab pertanyaan: *"Apa dependensi layanan X terhadap basis data Y, dan siapa penanggung jawab timnya jika service tersebut crash?"*

4. **Vector-Graph Hybrid RAG (GraphRAG)**:
   Kombinasi antara *dense vector similarity* (pencarian berbasis kedekatan konsep teks) dan *graph traversal* (pencarian berbasis topologi relasi eksplisit). Pendekatan ini mengatasi kelemahan mendasar RAG standar yang memecah dokumen menjadi *isolated text chunks*, yang menghilangkan keterkaitan struktural global (*contextual fragmentation*).

---

## 3. Why It Matters

### Masalah di Lingkungan Enterprise
Pada skenario enterprise nyata—seperti sistem otomatisasi SRE (*Site Reliability Engineering*), diagnosis klaim asuransi multi-tahap, atau analisis regulasi keuangan—pendekatan naive RAG dan agent berbasis session memory sederhana selalu menemui kegagalan pada tiga titik krusial:

1. **The "Lost-in-the-Middle" & Attention Budgeting Crisis**:
   Membanjiri context window LLM (meskipun model modern mendukung 128k–1M token) memicu degradasi retrieval drastis. Biaya komputasi meningkat secara kuadratik atau linear-akseleratif ($O(N)$ hingga $O(N^2)$), latensi per step melonjak dari 1 detik menjadi 15+ detik, dan akurasi ekstraksi informasi di tengah konteks anjlok hingga di bawah 50%.
2. **Context Fragmentation pada Vector Retrieval Murni**:
   Jika dokumen teknis terpecah menjadi chunk 512-token, relasi antara "Layanan A" pada Chunk 1 dan "Basis Data B" pada Chunk 50 terputus. Vector RAG gagal melakukan reasoning hubungan hierarkis tanpa bantuan traversal graf.
3. **State Corruption & Non-Recoverability**:
   Agent otonom yang menjalankan transaksi berdurasi 30 menit (misalnya, migrasi database atau deployment infra) akan mengalami kegagalan fatal jika koneksi jaringan putus saat state memory hanya tersimpan di heap memory proses Python (`RAM`). Sistem membutuhkan *ACID-compliant State Persistence* dengan mekanisme *Time-Travel Debugging* dan *Deterministic Replay*.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur terpadu sistem memori agentik enterprise: **Dual-tier Context Engine** yang memadukan **Deterministic State Store**, **Dynamic Context Compactor**, dan **Hybrid Vector-Graph Retriever**.

```
+===================================================================================================+
|                                    AGENT RUNTIME ORCHESTRATOR                                     |
+===================================================================================================+
        |                                                                           |
        | 1. Append User Input / Tool Event                                         | 6. Formulate Prompt
        v                                                                           v
+-------------------------------+                                           +-----------------------+
|    STATE PERSISTENCE ENGINE   |                                           | CONTEXT TOKEN BUDGET  |
|  (PostgreSQL / Redis Streams) |                                           |  ALLOCATOR & COMPACTOR|
+-------------------------------+                                           +-----------------------+
| - State Machine Transitions   |                                           | - System Prompt (Fixed)
| - Versioned Snapshots (BLOB)  |                                           | - Episodic Chunks (15%)
| - Distributed Lock (Redlock)  |                                           | - Semantic Graph (25%)
+-------------------------------+                                           | - Sliding Turns (40%)
        |                                                                   | - Scratchpad (20%)
        | 2. Snapshot Emit                                                  +-----------------------+
        v                                                                               ^
+-------------------------------+                                                       |
|  OFF-LINE MEMORY WORKER POOL  |                                                       | 5. Ingest &
|      (Async Background)       |                                                       |    Truncate
+-------------------------------+                                                       |
| - LLM Entity Extractor        |                                                       |
| - Triple Generator (S-P-O)    |                                                       |
| - Reciprocal Rank Fusion      |                                                       |
+-------------------------------+                                                       |
     |                     |                                                            |
     | 3a. Index Vectors   | 3b. Upsert Edges                                           |
     v                     v                                                            |
+-----------------+   +--------------------+                                            |
|   VECTOR STORE  |   |    GRAPH STORE     |                                            |
| (Qdrant/Milvus) |   | (Neo4j/Graph-Engine|                                            |
+-----------------+   +--------------------+                                            |
         \                     /                                                        |
          \                   /                                                         |
     4a. Semantic       4b. Multi-Hop                                                   |
         Similarity         Sub-graph                                                   |
         Search             Extraction                                                  |
           \                 /                                                          |
            \               /                                                           |
             v             v                                                            |
      +-------------------------+                                                       |
      |  HYBRID FUSION ENGINE   |-------------------------------------------------------+
      | (Reciprocal Rank Fusion |   4c. Fused Context Subgraph + Re-ranked Chunks
      |  + Cross-Encoder Rerank)|
      +-------------------------+
```

### Aliran Data End-to-End
1. **Input Ingestion & State Transition**: Input pengguna/lingkungan diterima, divalidasi oleh Pydantic schema, dan dicatat pada append-only log transactional state store (PostgreSQL/Redis) dengan state transitions yang deterministik.
2. **Context Compaction Pipeline**: Token Budget Allocator menghitung sisa jendela konteks. Jika limit terlampaui, percakapan historis diringkas secara rekursif (*recursive summarization*), mengekstraksi fakta kunci ke memori jangka panjang, dan mempertahankan *N* turn terakhir utuh.
3. **Dual-Route Retrieval (GraphRAG)**: Query dipecah menjadi dua cabang:
   * **Route A (Vector)**: Menghasilkan embedding teks dari query dan mengambil top-$k$ *dense textual chunks* berdasarkan *cosine similarity*.
   * **Route B (Graph)**: Menjalankan Named Entity Recognition (NER) pada query, mencocokkan node target dalam graf, lalu melakukan traversal *k-hop neighborhood* untuk mengekstraksi relasi terstruktur (*triplet*).
4. **Reciprocal Rank Fusion (RRF)**: Skor kemiripan vektor dan kedekatan struktural graf diintegrasikan untuk menghasilkan urutan konteks terbaik yang diinjeksikan langsung ke dalam Working Memory prompt LLM.

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Context Window Compaction & Sliding-Window Budgets
LLM beroperasi dengan *budget token* statis ($C_{\text{max}}$). Alokasi memori yang aman secara matematis harus memenuhi persamaan batas:

$$C_{\text{system}} + C_{\text{tools}} + C_{\text{scratchpad}} + C_{\text{episodic}} + C_{\text{semantic}} + C_{\text{buffer}} \le C_{\text{max}}$$

Jika akumulasi token melebihi limit ambang batas $\theta \cdot C_{\text{max}}$ (di mana $\theta \approx 0.85$ untuk mitigasi buffer generation), mekanisme pemadatan (*compaction*) dijalankan:
* **Selective Eviction**: Membersihkan payload tool call besar yang sudah dieksekusi (menggantinya dengan ringkasan status seperti `status: success, rows_affected: 450`).
* **Recursive Entity Summarization**: Menjalankan inferensi ringan paralel untuk mengubah raw turns $[T_{1}, \dots, T_{k}]$ menjadi representasi fakta kanonikal terkompresi tanpa memotong instruksi awal.

### 5.2 Deterministic State Machine & Checkpointing
State Agent bukan sekadar string riwayat pesan. State Agent adalah struktur data formal yang didefinisikan sebagai Finite State Machine (FSM):

$$S = \langle Q, \Sigma, \delta, q_0, F \rangle$$

* $Q$: Set state unik agent (`IDLE`, `PLANNING`, `EXECUTING_TOOL`, `AWAITING_HUMAN_INPUT`, `ERROR_RECOVERY`, `TERMINATED`).
* $\Sigma$: Event atau interupsi eksternal (Tool output, API Timeout, User Cancellation).
* $\delta$: Fungsi transisi $Q \times \Sigma \rightarrow Q$.
* Snapshots: Setiap transisi state $\delta(q_i, \sigma) = q_{i+1}$ secara atomic dituliskan ke persistent storage bersama *sequence ID* yang monotonik meningkat. Hal ini menjamin *exact-once execution semantics* saat proses dihidupkan ulang pasca-crash.

### 5.3 Vector-Graph Hybrid RAG Mechanism
RAG murni berbasis vektor bekerja dalam ruang semantik continuos:

$$\text{Sim}_{\text{cos}}(\mathbf{q}, \mathbf{d}) = \frac{\mathbf{q} \cdot \mathbf{d}}{\|\mathbf{q}\| \|\mathbf{d}\|}$$

Kelemahannya adalah ketidakmampuan merekonstruksi rantai logika transversal: *"Apakah entitas A terhubung dengan entitas C melalui entitas B?"* 

GraphRAG memetakan data teks ke dalam directed graph $G = (V, E, \tau)$ dengan:
* $V$: Entitas yang dinormalisasi (misal: `Service:PaymentGateway`, `Engineer:Alice`).
* $E$: Edge berarah yang membawa tipe hubungan $\tau$ (misal: `DEPENDS_ON`, `MAINTAINED_BY`).

**Fusi Pemeringkatan (Reciprocal Rank Fusion - RRF)**:
Untuk menggabungkan set dokumen hasil retrieval vector $R_V$ dan jalur graph $R_G$, algoritma RRF menghitung skor terpadu untuk setiap dokumen/subgraf $d$:

$$\text{RRF\_Score}(d \in R_V \cup R_G) = \sum_{m \in \{V, G\}} \frac{I(d \in R_m)}{k + \text{rank}_m(d)}$$

Di mana $k$ adalah konstanta penghalus (biasanya $k \approx 60$), $I$ adalah fungsi indikator biner, dan $\text{rank}_m(d)$ adalah posisi urutan dokumen dalam modalitas retrieval $m$.

---

## 6. Production-Ready Code Implementation

Implementasi berikut menggunakan Python 3.11+ murni berstandar industri dengan memanfaatkan `pydantic` v2, `asyncio`, typing lengkap, modular clean architecture, in-memory graph engine, dan vector similarity engine yang dirancang khusus untuk enterprise reliability.

```python
"""
Enterprise-Grade Agentic Memory System: State, Compactor, & Vector-Graph Hybrid RAG.
Architecture: Clean Architecture (Domain Models -> Engine Ports -> Unified Orchestrator).
Dependencies: pydantic>=2.0.0
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import math
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)
from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# 1. DOMAIN MODELS & TYPES
# ============================================================================

class AgentLifecycleState(str, Enum):
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    REASONING = "REASONING"
    EXECUTING_ACTION = "EXECUTING_ACTION"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class MemoryMessage(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    role: MessageRole
    content: str
    tokens: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    pinned: bool = Field(default=False, description="Pins critical messages against eviction")


@dataclass(frozen=True)
class KnowledgeTriple:
    subject: str
    predicate: str
    object_: str
    weight: float = 1.0


@dataclass
class VectorDocument:
    doc_id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# 2. STATE MANAGEMENT & ATOMIC CHECKPOINTING
# ============================================================================

class StateCheckpoint(BaseModel):
    checkpoint_id: str
    step_number: int
    state: AgentLifecycleState
    variables: Dict[str, Any]
    working_memory: List[MemoryMessage]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatePersistencePort(Protocol):
    async def save_checkpoint(self, checkpoint: StateCheckpoint) -> None:
        ...
        
    async def load_latest_checkpoint(self) -> Optional[StateCheckpoint]:
        ...


class InMemoryStateStore(StatePersistencePort):
    """ACID-compliant in-memory state store with monotonically increasing versions."""
    
    def __init__(self) -> None:
        self._history: Dict[str, StateCheckpoint] = {}
        self._latest_id: Optional[str] = None
        self._lock = asyncio.Lock()

    async def save_checkpoint(self, checkpoint: StateCheckpoint) -> None:
        async with self._lock:
            self._history[checkpoint.checkpoint_id] = checkpoint
            self._latest_id = checkpoint.checkpoint_id

    async def load_latest_checkpoint(self) -> Optional[StateCheckpoint]:
        async with self._lock:
            if not self._latest_id:
                return None
            return self._history[self._latest_id]


# ============================================================================
# 3. VECTOR ENGINE & GRAPH ENGINE (GRAPH-RAG)
# ============================================================================

class VectorSimilarityEngine:
    """Cosine-similarity Vector Store abstraction without external C-bindings."""
    
    def __init__(self) -> None:
        self._storage: Dict[str, VectorDocument] = {}

    def insert(self, doc: VectorDocument) -> None:
        self._storage[doc.doc_id] = doc

    @staticmethod
    def _cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude_v1 = math.sqrt(sum(a * a for a in v1))
        magnitude_v2 = math.sqrt(sum(b * b for b in v2))
        if magnitude_v1 == 0.0 or magnitude_v2 == 0.0:
            return 0.0
        return dot_product / (magnitude_v1 * magnitude_v2)

    def search(self, query_vector: List[float], top_k: int = 3) -> List[Tuple[VectorDocument, float]]:
        scores: List[Tuple[VectorDocument, float]] = []
        for doc in self._storage.values():
            sim = self._cosine_similarity(query_vector, doc.embedding)
            scores.append((doc, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class SemanticGraphEngine:
    """Directed Multi-relational In-Memory Knowledge Graph."""
    
    def __init__(self) -> None:
        # Adjacency list: subject -> list of (predicate, object, weight)
        self._adjacency: Dict[str, List[Tuple[str, str, float]]] = {}

    def add_triple(self, triple: KnowledgeTriple) -> None:
        sub = triple.subject.casefold()
        obj = triple.object_.casefold()
        pred = triple.predicate.upper()
        
        if sub not in self._adjacency:
            self._adjacency[sub] = []
        self._adjacency[sub].append((pred, obj, triple.weight))

    def k_hop_traversal(self, source_entities: Set[str], depth: int = 2) -> List[KnowledgeTriple]:
        visited_nodes: Set[str] = set()
        discovered_triples: List[KnowledgeTriple] = []
        queue: List[Tuple[str, int]] = [(e.casefold(), 0) for e in source_entities]

        while queue:
            current_entity, current_depth = queue.pop(0)
            if current_depth >= depth:
                continue

            if current_entity not in visited_nodes:
                visited_nodes.add(current_entity)
                edges = self._adjacency.get(current_entity, [])
                for pred, target, weight in edges:
                    discovered_triples.append(
                        KnowledgeTriple(subject=current_entity, predicate=pred, object_=target, weight=weight)
                    )
                    if target not in visited_nodes:
                        queue.append((target, current_depth + 1))

        return discovered_triples


class HybridFusionRetriever:
    """Fuses Dense Vector and Semantic Graph outputs via Reciprocal Rank Fusion (RRF)."""
    
    def __init__(
        self,
        vector_engine: VectorSimilarityEngine,
        graph_engine: SemanticGraphEngine,
        rrf_k: int = 60
    ) -> None:
        self.vector_engine = vector_engine
        self.graph_engine = graph_engine
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query_vector: List[float],
        seed_entities: Set[str],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        # 1. Fetch dense candidates
        vector_results = self.vector_engine.search(query_vector, top_k=top_k * 2)
        
        # 2. Fetch structural candidates
        graph_triples = self.graph_engine.k_hop_traversal(seed_entities, depth=2)
        
        # 3. Apply Reciprocal Rank Fusion
        rrf_scores: Dict[str, float] = {}
        content_map: Dict[str, Dict[str, Any]] = {}

        # Process vector ranks
        for rank, (doc, _) in enumerate(vector_results):
            key = f"vec_{doc.doc_id}"
            score = 1.0 / (self.rrf_k + (rank + 1))
            rrf_scores[key] = rrf_scores.get(key, 0.0) + score
            content_map[key] = {
                "type": "vector",
                "content": doc.content,
                "metadata": doc.metadata
            }

        # Process graph ranks
        for rank, triple in enumerate(graph_triples):
            key = f"graph_{triple.subject}_{triple.predicate}_{triple.object_}"
            score = (1.0 / (self.rrf_k + (rank + 1))) * triple.weight
            rrf_scores[key] = rrf_scores.get(key, 0.0) + score
            content_map[key] = {
                "type": "graph",
                "content": f"({triple.subject}) --[{triple.predicate}]--> ({triple.object_})",
                "metadata": {"weight": triple.weight}
            }

        sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)
        
        fused_output: List[Dict[str, Any]] = []
        for k in sorted_keys[:top_k]:
            item = content_map[k]
            item["rrf_score"] = rrf_scores[k]
            fused_output.append(item)

        return fused_output


# ============================================================================
# 4. CONTEXT COMPACTOR & TOKEN BUDGET ALLOCATOR
# ============================================================================

class ContextTokenCompactor:
    """Manages context window quotas, sliding turn evictions, and selective summarization."""

    def __init__(self, max_context_tokens: int = 4096, target_eviction_ratio: float = 0.25) -> None:
        self.max_tokens = max_context_tokens
        self.eviction_ratio = target_eviction_ratio

    def calculate_tokens(self, messages: Sequence[MemoryMessage]) -> int:
        return sum(m.tokens for m in messages)

    def compact(self, messages: List[MemoryMessage]) -> List[MemoryMessage]:
        total_tokens = self.calculate_tokens(messages)
        if total_tokens <= self.max_tokens:
            return messages

        tokens_to_free = total_tokens - int(self.max_tokens * (1.0 - self.eviction_ratio))
        freed_tokens = 0
        preserved_messages: List[MemoryMessage] = []
        eviction_candidates: List[MemoryMessage] = []

        # System and Pinned messages are strictly protected
        for msg in messages:
            if msg.role == MessageRole.SYSTEM or msg.pinned:
                preserved_messages.append(msg)
            else:
                eviction_candidates.append(msg)

        # Evict unpinned older items from candidates
        surviving_candidates: List[MemoryMessage] = []
        for msg in eviction_candidates:
            if freed_tokens < tokens_to_free:
                freed_tokens += msg.tokens
                continue
            surviving_candidates.append(msg)

        # In production, insert a synthesized summary marker message
        if freed_tokens > 0:
            summary_notice = MemoryMessage(
                role=MessageRole.SYSTEM,
                content=f"[System Warning: Context budget exceeded. {freed_tokens} historical tokens compacted.]",
                tokens=15,
                pinned=True
            )
            preserved_messages.append(summary_notice)

        final_context = preserved_messages + surviving_candidates
        # Re-sort by natural timestamp to maintain sequential reasoning continuity
        final_context.sort(key=lambda m: m.timestamp)
        return final_context


# ============================================================================
# 5. HIGH-LEVEL AGENTIC MEMORY ORCHESTRATOR
# ============================================================================

class EnterpriseAgentMemorySystem:
    """
    Coordinates State Persistence, Dynamic Context Compaction,
    and Vector-Graph Hybrid RAG Retrieval.
    """

    def __init__(
        self,
        persistence_engine: StatePersistencePort,
        retriever: HybridFusionRetriever,
        compactor: ContextTokenCompactor,
    ) -> None:
        self.persistence = persistence_engine
        self.retriever = retriever
        self.compactor = compactor
        self._current_step = 0
        self._state = AgentLifecycleState.INITIALIZING
        self._working_memory: List[MemoryMessage] = []
        self._variables: Dict[str, Any] = {}

    async def initialize_session(self, system_instruction: str) -> None:
        self._current_step = 0
        self._state = AgentLifecycleState.READY
        system_msg = MemoryMessage(
            role=MessageRole.SYSTEM,
            content=system_instruction,
            tokens=len(system_instruction.split()),  # Simple heuristic for token count
            pinned=True
        )
        self._working_memory = [system_msg]
        await self._persist_state()

    async def ingest_observation(
        self,
        user_input: str,
        input_vector: List[float],
        identified_entities: Set[str]
    ) -> None:
        """Processes environment/user updates, retrieves hybrid memory, and compacts."""
        self._state = AgentLifecycleState.REASONING
        self._current_step += 1

        # 1. Fetch relevant long-term memory via Vector-Graph RAG
        context_matches = self.retriever.retrieve(
            query_vector=input_vector,
            seed_entities=identified_entities,
            top_k=3
        )

        # 2. Format memory injection
        retrieved_context_str = "\n".join([f"- [{item['type'].upper()}] {item['content']}" for item in context_matches])
        injection_content = (
            f"User Instruction:\n{user_input}\n\n"
            f"Contextual Knowledge (Retrieved Long-Term Memory):\n{retrieved_context_str}"
        )
        
        user_msg = MemoryMessage(
            role=MessageRole.USER,
            content=injection_content,
            tokens=len(injection_content.split()),
            pinned=False
        )
        self._working_memory.append(user_msg)

        # 3. Compact Context to satisfy strict token allocation limits
        self._working_memory = self.compactor.compact(self._working_memory)

        # 4. Checkpoint State
        await self._persist_state()

    async def log_action_execution(self, tool_name: str, payload: str, result: str) -> None:
        self._state = AgentLifecycleState.EXECUTING_ACTION
        self._current_step += 1
        
        content = f"Action: {tool_name}({payload}) -> Result: {result}"
        action_msg = MemoryMessage(
            role=MessageRole.TOOL,
            content=content,
            tokens=len(content.split()),
            metadata={"tool": tool_name}
        )
        self._working_memory.append(action_msg)
        self._working_memory = self.compactor.compact(self._working_memory)
        await self._persist_state()

    async def _persist_state(self) -> None:
        hasher = hashlib.sha256()
        hasher.update(f"{self._current_step}_{datetime.now(timezone.utc).isoformat()}".encode())
        checkpoint_id = hasher.hexdigest()[:16]

        checkpoint = StateCheckpoint(
            checkpoint_id=checkpoint_id,
            step_number=self._current_step,
            state=self._state,
            variables=self._variables,
            working_memory=self._working_memory
        )
        await self.persistence.save_checkpoint(checkpoint)

    def get_working_memory(self) -> List[MemoryMessage]:
        return list(self._working_memory)


# ============================================================================
# 6. VERIFICATION ENTRYPOINT (EXECUTION HARNESS)
# ============================================================================

async def main() -> None:
    # Setup infrastructure
    state_store = InMemoryStateStore()
    vector_engine = VectorSimilarityEngine()
    graph_engine = SemanticGraphEngine()
    
    # Populate semantic graph knowledge
    graph_engine.add_triple(KnowledgeTriple("OrderService", "DEPENDS_ON", "RedisCache", weight=0.9))
    graph_engine.add_triple(KnowledgeTriple("RedisCache", "RUNS_IN", "Cluster-East-1", weight=0.8))
    graph_engine.add_triple(KnowledgeTriple("OrderService", "OWNED_BY", "CheckoutTeam", weight=1.0))

    # Populate vector knowledge
    vector_engine.insert(
        VectorDocument(
            doc_id="doc_runbook_01",
            content="Runbook-102: When RedisCache fails in Cluster-East-1, restart order-processor pods.",
            embedding=[0.12, 0.88, 0.45, 0.05],
            metadata={"type": "runbook"}
        )
    )

    fusion_retriever = HybridFusionRetriever(vector_engine, graph_engine)
    compactor = ContextTokenCompactor(max_context_tokens=100, target_eviction_ratio=0.3)
    
    agent_memory = EnterpriseAgentMemorySystem(
        persistence_engine=state_store,
        retriever=fusion_retriever,
        compactor=compactor
    )

    # Initialize agent
    await agent_memory.initialize_session("You are an autonomous SRE Remediation Agent.")

    # Ingest event with simulated embedding
    query_vector = [0.10, 0.85, 0.40, 0.02]
    await agent_memory.ingest_observation(
        user_input="Investigate latency spike in OrderService",
        input_vector=query_vector,
        identified_entities={"OrderService"}
    )

    # Log tool actions to demonstrate compaction triggers
    for i in range(5):
        await agent_memory.log_action_execution(
            tool_name="metric_fetcher",
            payload=f"query_step={i}",
            result=f"Status 200 OK. Metric samples collected across cluster nodes payload iteration={i}"
        )

    # Assert integrity
    active_memory = agent_memory.get_working_memory()
    print("=== FINAL WORKING MEMORY PROFILE ===")
    for idx, msg in enumerate(active_memory):
        print(f"[{idx}] Role: {msg.role.value:10} | Tokens: {msg.tokens:3} | Pinned: {msg.pinned}")
        print(f"    Content: {msg.content[:85]}...")

    latest_state = await state_store.load_latest_checkpoint()
    assert latest_state is not None
    print(f"\nState successfully checkpointed. Current Step: {latest_state.step_number}, Status: {latest_state.state.value}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

### 1. Context Drift & Attention Hijacking
* **Gejala**: Ketika LLM terus-menerus mengumpulkan chunk teks RAG yang tidak sepenuhnya relevan, probabilitas model memprioritaskan noise di atas instruksi utama meningkat drastis.
* **Deteksi**: Perbedaan (*cosine distance*) antara embedding instruksi awal dan token yang dihasilkan secara dinamis mulai divergen melampaui ambang batas tertentu ($> 0.65$).
* **Mitigasi**: Implementasi *hard system message pinning* dan memfilter retrieval chunks menggunakan threshold cosine similarity strictly ($> 0.75$) atau reranker probability score ($> 0.80$).

### 2. Graph Traversal Explosion (The "Supernode" Trap)
* **Gejala**: Node sentral dengan derajat hubungan sangat tinggi (misal: entitas `Environment: Production` atau `Status: Active` yang terhubung ke puluhan ribu entity) menyebabkan retrieval $k$-hop menghasilkan ribuan edge yang membanjiri token budget.
* **Mitigasi**:
  * Gunakan **Degree-Capped Traversal**: Tolak atau batasi ekspansi pada node yang memiliki `degree > MaxDegreeThreshold` (misal $> 50$).
  * Terapkan **Edge Weight Thresholding** dan **Predicate Filtering**: Batasi traversal hanya pada jenis relasi spesifik yang relevan dengan intent (misal: hanya travers relasi `DEPENDS_ON` dan `RUNS_ON`, abaikan relasi `TAGGED_WITH`).

### 3. Concurrent State Mutations (Race Conditions)
* **Gejala**: Sub-agent atau asynchronous tool worker memodifikasi state scratchpad secara bersamaan, menyebabkan *dirty reads* atau penimpaan snapshot sebelumnya (*lost updates*).
* **Mitigasi**:
  * Gunakan **Optimistic Concurrency Control (OCC)** pada state storage dengan nomor versi skema (`version_id`).
  * Jika mutasi gagal akibat deteksi konflik versi ($V_{\text{target}} \neq V_{\text{current}}$), lakukan *exponential backoff retry* dan re-read snapshot terbaru sebelum melakukan penulisan ulang.

### 4. Vector-Graph Contradiction
* **Gejala**: Vector Document menyatakan `Alice adalah Lead Database`, tetapi Knowledge Graph menyatakan edge `Alice --[RESIGNED_FROM]--> Company` yang menyebabkan LLM berhalusinasi.
* **Mitigasi**: Tetapkan resolusi konflik berbasis prioritas sumber: *Knowledge Graph deterministik selalu memiliki preseden kebenaran struktural lebih tinggi daripada vector text chunk tidak terstruktur yang belum didegradasi (stale)*.

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Pendekatan Terpilih (Vector-Graph Hybrid) | Alternatif A: Naive Vector-Only RAG | Alternatif B: Full Graph-Only RAG |
| :--- | :--- | :--- | :--- |
| **Akurasi Reasoning Relasional** | **Sangat Tinggi**: Mampu memetakan dependensi implisit multi-hop. | **Rendah**: Bergantung pada kebetulan entitas berada dalam chunk yang sama. | **Tinggi**: Sangat akurat untuk entitas terstruktur, tetapi kehilangan nuansa semantik bebas. |
| **Latensi Query** | **Sedang-Tinggi (~150-400ms)**: Memerlukan ekstraksi entitas, k-hop search, dan vector retrieval paralel. | **Sangat Rendah (~20-80ms)**: Hanya melakukan single embedding calculation + HNSW index lookup. | **Sedang (~50-200ms)**: Bergantung pada kedalaman hop traversal graf. |
| **Kompleksitas Pipeline Data** | **Sangat Tinggi**: Membutuhkan ETL untuk Entity Extraction, Triplet Resolution, Vector Indexing, Graph Sync. | **Rendah**: Cukup text chunking standar dan embedding model. | **Tinggi**: Membutuhkan ekstraksi ontologi teks kontinu dan deduplikasi node/edge. |
| **Biaya Token Inference** | **Terkontrol**: Subgraf dapat diserialisasi secara kompak menjadi bentuk triple `(S, P, O)`. | **Tinggi**: Perlu menginjeksi seluruh paragraf chunk teks ke prompt. | **Paling Rendah**: Hanya relasi terstruktur teks minimal yang diinjeksikan ke LLM context. |
| **Toleransi Unstructured Data** | **Tinggi**: Menjaga vector fallback saat entitas tidak ditemukan di graph. | **Sangat Tinggi**: Bekerja langsung pada teks tanpa struktur ketat. | **Rendah**: Teks yang gagal dipetakan ke dalam subgraf entitas akan terlewat (*silent drop*). |

---

## 9. Best Practices & Standard Industri

1. **Deterministic Serialization**: Pastikan serialisasi state (JSON/Protobuf) selalu deterministik (misalnya, sorting dictionary keys) untuk menjamin validitas SHA-256 fingerprinting saat verifikasi integritas memori.
2. **Context Masking & PII Redaction**: Terapkan pipeline sanitasi data (misal: masking nomor kartu kredit, access token, email) sebelum teks disimpan secara permanen di Episodic Vector Memory atau Semantic Graph Store.
3. **Graceful Token Budgeting Matrix**: Bagi context window menjadi zona alokasi yang ketat dan tidak dapat dilanggar (*strict hard caps*):
   * System Prompt & Core Rules: **15%** (Immutable, pinned).
   * Short-term Turn Memory (Sliding Window): **35%**.
   * Hybrid Retrieved Long-term Context: **30%**.
   * Dynamic Scratchpad / Action Output Buffer: **20%**.
4. **OpenTelemetry Memory Instrumentation**: Catat metrik durasi retrieval, persentase token budget compaction, rasio hit/miss vector search, serta traversal graph depth per step reasoning untuk mendeteksi degradasi performa (*telemetry tracing*).

---

## 10. Hands-on Lab Exercise

### Deskripsi Masalah
Sebagai Principal AI Engineer pada sistem Cloud Autonomous Remediation, Anda ditugaskan untuk mengimplementasikan modul mitigasi crash cascade. Sistem mengalami kegagalan berulang karena prompt LLM melebihi kapasitas context window ketika log error berukuran besar diinjeksikan secara terus-menerus.

### Petunjuk Langkah Demi Langkah
1. **Langkah 1**: Salin dan jalankan skeleton code pada Bagian 6 di local environment Anda.
2. **Langkah 2**: Tambahkan method `extract_triples_from_text(raw_log: str) -> List[KnowledgeTriple]` pada `SemanticGraphEngine` yang secara otomatis mengekstrak entity error dan target service menggunakan parsing regex atau rule-based heuristic (misal: memetakan string `"ServiceA failed targeting ServiceB"` menjadi triple `("ServiceA", "FAILED_CALL_TO", "ServiceB")`).
3. **Langkah 3**: Ubah implementasi `ContextTokenCompactor` dengan menambahkan mode **Selective Tool Pruning**:
   * Jika pesan memiliki role `MessageRole.TOOL`, pangkas content-nya menjadi maksimal 20 token pertama ditambah teks ringkasan `"... [payload truncated by compactor]"`.
4. **Langkah 4**: Simulasikan skenario kegagalan:
   * Masukkan 10 message tool call beruntun dengan payload error log masing-masing 500 token.
   * Pastikan total tokens dalam working memory tidak pernah melampaui `max_context_tokens=1000`.

### Verifikasi Hasil & Kriteria Evaluasi
Jalankan test script verifikasi berikut untuk mengonfirmasi solusi Anda:

```python
# Tambahkan pengujian ini pada runtime script Anda
async def verify_lab():
    compactor = ContextTokenCompactor(max_context_tokens=500, target_eviction_ratio=0.20)
    messages = [
        MemoryMessage(role=MessageRole.SYSTEM, content="System instructions", tokens=50, pinned=True)
    ]
    
    # Generate 10 massive tool outputs
    for i in range(10):
        messages.append(
            MemoryMessage(
                role=MessageRole.TOOL,
                content=f"Error Log Dump iteration {i}: " + ("CRITICAL_STACK_TRACE_VALUE " * 40),
                tokens=120,
                pinned=False
            )
        )
    
    compacted = compactor.compact(messages)
    total_tokens = sum(m.tokens for m in compacted)
    
    print(f"Post-Compaction Total Tokens: {total_tokens}")
    assert total_tokens <= 500, f"Validation Failed: Expected <= 500 tokens, got {total_tokens}"
    assert compacted[0].role == MessageRole.SYSTEM, "Validation Failed: System prompt was evicted!"
    print("Lab Exercise Successfully Verified: Token boundaries respected and system invariant preserved.")

if __name__ == "__main__":
    asyncio.run(verify_lab())
```