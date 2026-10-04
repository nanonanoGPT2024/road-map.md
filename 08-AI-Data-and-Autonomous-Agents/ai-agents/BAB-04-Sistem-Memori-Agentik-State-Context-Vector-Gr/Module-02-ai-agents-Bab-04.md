# BAB 04: Sistem Memori Agentik (State, Context Window, Vector, & Graph)
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mendesain Arsitektur Memori Multi-Tier**: Mengintegrasikan *Working Memory* (in-context), *Episodic Memory* (vector-based temporal event streams), *Semantic Memory* (knowledge graph), dan *Procedural Memory* (action/skill repository) ke dalam arsitektur AI Agent enterprise.
2. **Mengimplementasikan Algoritma Konsolidasi & Eviksi Memori**: Membangun mekanisme *memory decay*, *recursive summarization*, dan *importance scoring* berbasis formula kognitif matematis untuk menjaga integritas *context budget*.
3. **Membangun Hybrid Retrieval Engine (Vector + Graph)**: Menggabungkan *dense vector embeddings* dengan *labeled property graphs* (GraphRAG) untuk menyelesaikan query *multi-hop reasoning* tanpa mengalami degradasi konteks (*needle-in-a-haystack decay*).
4. **Mencegah & Mengatasi State Inconsistency**: Menangani konkurensi mutasi state agent pada distributed environment menggunakan distributed locks, *event sourcing*, dan bi-temporal tracking.
5. **Menerapkan Standar Keamanan & Regulasi Memori**: Mengimplementasikan *data sanitization*, isolasi multi-tenant, dan kepatuhan GDPR (*Right to be Forgotten*) pada representasi vektor dan graf memori.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* **Vector Database & Embeddings**: Pemahaman mendalam mengenai HNSW, Cosine/Inner Product similarity, dense retrieval, dan indexing lifecycle.
* **Graph Databases**: Penguasaan konsep Property Graph, Cypher Query Language (Neo4j), dan relasi antar-entitas.
* **Concurrency & Distributed Systems**: Pola arsitektur berbasis event (Kafka/Redis Streams), distributed locking (Redlock), dan konsistensi data bertingkat (CAP/PACELC).
* **Advanced Python/Software Engineering**: Asyncio, Static Typing (`typing`, `pydantic v2`), Dependency Injection, dan testing framework (`pytest`, `pytest-asyncio`).
* **LLM Foundations**: Mekanisme self-attention, context window constraints, tokenization budget, dan KV-cache retention.

---

### 3. Concept & Internal Architecture (Mendalam)

Sistem memori pada AI Agent enterprise memecahkan limitasi mendasar model LLM: **statelessness** dan **bounded context window**. Ketika agent beroperasi secara otonom dalam durasi panjang, sekadar menumpuk riwayat obrolan (*naive sliding window*) akan menyebabkan *context saturation*, biaya inferensi melonjak secara kuadratik, serta memicu *in-context distraction/hallucination*.

Arsitektur memori modern mengadopsi taksonomi kognitif yang dipetakan ke dalam komponen infrastruktur data terdistribusi:

```
+-------------------------------------------------------------------------------+
|                             AI AGENT CORE ENGINE                              |
|                                                                               |
|  +-------------------------------------------------------------------------+  |
|  |             Context Window Orchestrator (Token Budget Manager)          |  |
|  +-------------------------------------------------------------------------+  |
+---------^-------------------^--------------------^-------------------^--------+
          |                   |                    |                   |
          v                   v                    v                   v
+------------------+ +------------------+ +------------------+ +----------------+
|  WORKING MEMORY  | | EPISODIC MEMORY  | | SEMANTIC MEMORY  | |  PROCEDURAL    |
| (Active Context) | | (Event Stream)   | | (Knowledge Graph)| |  (Skill Store) |
+------------------+ +------------------+ +------------------+ +----------------+
| - Scratchpad     | - Raw Dialogues    | - Entity-Relation  | - System Prompts |
| - Current Goal   | - Timestamped Logs | - Discovered Facts | - Validated Tool |
| - Local State    | - Vector DB + HNSW | - Graph DB (Neo4j) |   Execution Schemas
| - Redis KV/JSON  | - Decay Scoring    | - Triplet Extract  | - Code/Scripts   |
+------------------+ +------------------+ +------------------+ +----------------+
```

#### Taksonomi Memori Agentik

1. **Working Memory (Active State / Scratchpad)**:
   * **Substrat**: In-memory (Redis Cluster / RAM instance).
   * **Karakteristik**: Latensi sub-milidetik, volume kecil (< 128K token), mutasi konstan setiap *reasoning step*.
   * **Fungsi**: Menyimpan *immediate execution plan*, *intermediate tool outputs*, dan variabel lokal agent.
2. **Episodic Memory (Temporal Experience)**:
   * **Substrat**: Vector Store (Qdrant / Milvus) + Document Store (MongoDB / PostgreSQL).
   * **Karakteristik**: Bersifat kronologis dan autobiografis. Mengingat interaksi masa lalu secara spesifik terhadap waktu dan konteks.
   * **Fungsi**: "Apa yang dikatakan user X dua minggu lalu mengenai preferensi investasinya?"
3. **Semantic Memory (Structured Knowledge & World Model)**:
   * **Substrat**: Labeled Property Graph (Neo4j / Memgraph) terhubung dengan Vector Index.
   * **Karakteristik**: Non-temporal, faktual, relasional. Mengabstraksikan fakta dari episode menjadi proposisi universal.
   * **Fungsi**: "Perusahaan X adalah anak perusahaan Y, dipimpin oleh CEO Z yang memiliki profil risiko agresif."
4. **Procedural Memory (Implicit / Motor Skills)**:
   * **Substrat**: Git Versioned Registry / Database Schema Store.
   * **Karakteristik**: Statis atau semi-statis, berisi instruksi deterministik, template tindakan, dan program yang dapat dieksekusi.
   * **Fungsi**: Bagaimana cara mengeksekusi migrasi database, format payload API pembayaran, atau tahapan investigasi error log.

#### Dynamic Memory Lifecycle: Konsolidasi & Decay

Memori yang masuk tidak boleh disimpan begitu saja secara permanen. Diperlukan siklus hidup memori otomatis:
* **Ingestion**: Raw observation diterima melalui antarmuka agent.
* **Reflective Consolidation**: Proses latar belakang (asynchronous background workers) yang membaca episode mentah, mengekstrak entitas dan relasi baru, menyusun ringkasan, lalu menuliskannya ke Semantic Graph.
* **Importance Scoring & Temporal Decay**:
  Setiap *node* memori episodic dihitung nilainya menggunakan formula adaptasi dari kognisi manusia:

$$Score(m) = w_r \cdot Recency(m) + w_i \cdot Importance(m) + w_s \cdot Similarity(m, q)$$

Di mana fungsi peluruhan temporal (*Recency*) dievaluasi secara eksponensial:

$$Recency(t) = e^{-\lambda \cdot (t_{current} - t_{created})}$$

Parameter $\lambda$ merepresentasikan laju peluruhan (*decay rate*), sedangkan $Importance(m)$ dievaluasi saat ingest oleh LLM evaluator (skala 1-10) untuk menandai signifikansi informasi.

---

### 4. Why & What

| Dimensi | Pendekatan Naive (Stateless / Full Context Window) | Pendekatan Enterprise Tiered Memory |
| :--- | :--- | :--- |
| **Token Consumption** | Membengkak secara linier ($O(N)$) terhadap interaksi. Cepat mencapai batas konteks. | Konstan ($O(1)$) terhadap *context window*, scaling horizontal pada database backend. |
| **Biaya Operasional (API Cost)** | Biaya inferensi naik drastis setiap turn percakapan baru. | Biaya terprediksi dan efisien melalui seleksi konteks strictly bounded. |
| **Multi-Hop Reasoning** | Gagal menghubungkan fakta terdistribusi yang terpisah ratusan turn lalu. | Unggul melalui traversal relasi pada Knowledge Graph (*GraphRAG*). |
| **State Consistency** | Inkonsisten jika agent mengalami restart atau failover node infra. | ACID/Transactional compliance menggunakan state machine eksternal terpusat. |
| **Auditability & Compliance** | Data sensitif mengendap di raw context, melanggar hak privasi. | Fine-grained retention: penghapusan selektif pada vector ID dan entity node. |

---

### 5. How (Workflow Detail)

Alur eksekusi memori saat Agent menerima input query baru:

```
[User Input Request]
        |
        v
[1. Context Budget Allocator]
        |---> Menghitung sisa token budget LLM (misal: 8192 tokens)
        |---> Alokasi: System Prompt (20%), Working Memory (30%), Retrieved Context (50%)
        |
        v
[2. Parallel Retrieval Dispatcher]
        +-----------------------------------+-----------------------------------+
        | (Branch A: Episodic Retrieval)   | (Branch B: Semantic Retrieval)    |
        v                                   v
  Vector Store Hybrid Search          Knowledge Graph Traversal
  - Dense Vector (Cosine)             - Entity Extraction via LLM
  - Sparse BM25 / Keyword             - Cypher Query k-hop expansion
  - Decay & Importance Weighting       - Relational Triplet extraction
        +-----------------------------------+-----------------------------------+
        |
        v
[3. Context Ranker & Deduplicator]
        |---> Cross-encoder Re-ranking (Cohere / BGE-Reranker)
        |---> Hapus kontradiksi dan duplikasi informasi
        |
        v
[4. Context Injection & Model Inference]
        |---> Injeksi ke Prompt Context
        |---> LLM menghasilkan Action/Response
        |
        v
[5. Post-Execution Asynchronous Pipeline]
        |---> Perbarui Working Memory (Redis State)
        |---> Push Raw Event ke Kafka / Redis Stream
        v
[Background Worker: Memory Consolidation Engine]
        |---> Ekstraksi Entitas baru -> Upsert ke Graph DB
        |---> Recursive Summarization jika event queue melewati ambang batas (Threshold)
        |---> Garbage Collection: Eviksi memori dengan Score < Threshold
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Kognitif
Bayangkan seorang Analis Keuangan Senior:
* **Working Memory**: Kertas coret-coretan di meja kerjanya saat ini. Mencatat kalkulasi sementara yang sedang dihitung. Segera dibuang setelah task selesai.
* **Episodic Memory**: Buku harian interaksi. Berisi catatan: *"3 Mei 2024 pukul 14:00: Klien X panik karena suku bunga The Fed naik dan meminta portofolio dialihkan."*
* **Semantic Memory**: Pengetahuan konseptual di otaknya. Struktur logika abstrak: *"Kenaikan suku bunga -> Tekanan pada obligasi tenor panjang -> Emiten sektor teknologi rentan terdepresiasi."*
* **Procedural Memory**: Standard Operating Procedure (SOP) perusahaan. Formulir dan script compliance yang wajib dipatuhi langkah demi langkah tanpa boleh improvisasi liar.

#### Diagram Arsitektur Runtime Produksi

```
                      +----------------------------------+
                      |         API Gateway / App        |
                      +-----------------+----------------+
                                        |
                                        v
                 +--------------------------------------------+
                 |       Agent Orchestrator (LangGraph/Core)  |
                 +------+---------------+--------------+------+
                        |               |              |
         +--------------+               |              +--------------+
         | Read/Write State             | Fast Vector Search          | Cypher Traversal
         v                              v                             v
+------------------+         +--------------------+         +--------------------+
|   Redis Cluster  |         |   Qdrant / Milvus  |         |       Neo4j        |
|                  |         |                    |         |                    |
| [Working Memory] |         | [Episodic Memory]  |         | [Semantic Memory]  |
| - Session Cache  |         | - Timestamped Logs |         | - Entity Nodes     |
| - Locks (Redlock)|         | - Context Vectors  |         | - Semantic Edges   |
| - Call Stack     |         | - Importance Float |         | - Multi-hop Graph  |
+------------------+         +--------------------+         +--------------------+
         ^                              ^                             ^
         |                              |                             |
         +------------------------------+-----------------------------+
                                        |
                   +--------------------+--------------------+
                   | Asynchronous Memory Consolidation Engine|
                   | (Celery / Temporal.io / Kafka Consumer) |
                   +-----------------------------------------+
                   | - Entity Linker                         |
                   | - Decay Factor Recalculator             |
                   | - Recursive Context Compactor           |
                   +-----------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Sliding Window dengan Importance Decay
Contoh skrip sederhana untuk menghitung bobot retensi memori secara matematis.

```python
import math
import time
from dataclasses import dataclass

@dataclass
class MemoryRecord:
    content: str
    created_at: float
    importance: float  # Skala 1.0 - 10.0

def calculate_retention_score(
    record: MemoryRecord, 
    decay_lambda: float = 0.005, 
    current_time: float = None
) -> float:
    now = current_time if current_time else time.time()
    time_delta = now - record.created_at  # Selisih waktu dalam detik
    
    recency = math.exp(-decay_lambda * time_delta)
    # Normalisasi importance ke skala 0.0 - 1.0
    normalized_importance = record.importance / 10.0
    
    # Skoring akhir memori gabungan
    score = (0.4 * recency) + (0.6 * normalized_importance)
    return score

# Simulasi
now = time.time()
mem1 = MemoryRecord(content="User menyukai saham bluechip", created_at=now - 3600, importance=9.0)
mem2 = MemoryRecord(content="User bertanya cuaca hari ini", created_at=now - 60, importance=1.0)

print(f"Skor Memori 1 (1 jam lalu, sangat penting): {calculate_retention_score(mem1, current_time=now):.4f}")
print(f"Skor Memori 2 (1 menit lalu, tidak penting): {calculate_retention_score(mem2, current_time=now):.4f}")
```

---

#### B. Practical Enterprise Example: Hybrid Production Memory Engine

Implementasi tingkat enterprise di bawah ini mendemonstrasikan integrasi *Tiered Memory System*: Working Memory (in-memory state management), Episodic Memory (vector persistence dengan decay and importance), serta ekstraksi Semantic Triplet untuk memori relasional, lengkap dengan concurrency safety dan dynamic token budgeting.

```python
import asyncio
import time
import math
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import numpy as np

# =====================================================================
# Domain Models & Schemas
# =====================================================================

class MemoryType:
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"

class MemoryNode(BaseModel):
    id: str
    content: str
    memory_type: str
    created_at: float = Field(default_factory=time.time)
    last_accessed_at: float = Field(default_factory=time.time)
    importance_score: float = Field(default=5.0, ge=1.0, le=10.0)
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Triplet(BaseModel):
    subject: str
    predicate: str
    object_: str

class MemoryQuery(BaseModel):
    query_text: str
    query_vector: List[float]
    token_budget: int = 2048
    recency_weight: float = 0.3
    importance_weight: float = 0.3
    similarity_weight: float = 0.4
    decay_lambda: float = 0.0001

# =====================================================================
# Vector Utility Functions (Production Math Engine)
# =====================================================================

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    a = np.array(v1, dtype=np.float32)
    b = np.array(v2, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

# =====================================================================
# Enterprise Memory Store Implementation
# =====================================================================

class TieredMemoryEngine:
    def __init__(self, token_char_ratio: float = 4.0):
        # Simulasi Working Memory (Short-Term Key-Value Scratchpad)
        self._working_memory: Dict[str, Any] = {}
        # Simulasi Episodic Memory (Vector-Indexed Event Store)
        self._episodic_store: Dict[str, MemoryNode] = {}
        # Simulasi Semantic Graph Memory (Graph Triplet Store: Subject -> Predicate -> Object)
        self._semantic_graph: Dict[str, List[Dict[str, str]]] = {}
        # Mutex lock untuk distributed write safety (simulasi concurrency lock)
        self._lock = asyncio.Lock()
        self.char_per_token = token_char_ratio

    # -------------------------------------------------------------
    # 1. Working Memory Operations
    # -------------------------------------------------------------
    async def set_working_state(self, key: str, value: Any) -> None:
        async with self._lock:
            self._working_memory[key] = value

    async def get_working_state(self, key: str) -> Optional[Any]:
        return self._working_memory.get(key, None)

    # -------------------------------------------------------------
    # 2. Episodic Memory Operations
    # -------------------------------------------------------------
    async def ingest_episode(
        self, 
        node_id: str, 
        content: str, 
        embedding: List[float], 
        importance: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryNode:
        node = MemoryNode(
            id=node_id,
            content=content,
            memory_type=MemoryType.EPISODIC,
            importance_score=importance,
            embedding=embedding,
            metadata=metadata or {}
        )
        async with self._lock:
            self._episodic_store[node_id] = node
        return node

    # -------------------------------------------------------------
    # 3. Semantic Graph Operations
    # -------------------------------------------------------------
    async def ingest_triplet(self, triplet: Triplet) -> None:
        async with self._lock:
            subj = triplet.subject.lower()
            if subj not in self._semantic_graph:
                self._semantic_graph[subj] = []
            
            # Mencegah duplikasi edge
            edge_exists = any(
                e["predicate"] == triplet.predicate.lower() and e["object"] == triplet.object_.lower()
                for e in self._semantic_graph[subj]
            )
            if not edge_exists:
                self._semantic_graph[subj].append({
                    "predicate": triplet.predicate.lower(),
                    "object": triplet.object_.lower()
                })

    async def query_knowledge_graph(self, entities: List[str]) -> List[str]:
        results = []
        for ent in entities:
            normalized_ent = ent.lower()
            if normalized_ent in self._semantic_graph:
                for edge in self._semantic_graph[normalized_ent]:
                    results.append(f"Fact: {ent} {edge['predicate']} {edge['object']}")
        return results

    # -------------------------------------------------------------
    # 4. Context Budget Management & Hybrid Search
    # -------------------------------------------------------------
    async def retrieve_context(self, query: MemoryQuery, relevant_entities: List[str]) -> str:
        current_time = time.time()
        scored_memories = []

        # Step A: Hybrid Episodic Retrieval dengan Scoring Formula
        for node in self._episodic_store.values():
            if not node.embedding:
                continue

            # Recency calculation
            time_delta = current_time - node.created_at
            recency = math.exp(-query.decay_lambda * time_delta)

            # Importance calculation (1.0 to 10.0 scale normalized to 0.1 - 1.0)
            importance = node.importance_score / 10.0

            # Relevance / Similarity
            similarity = cosine_similarity(query.query_vector, node.embedding)

            # Unified Compound Memory Score
            total_score = (
                (query.recency_weight * recency) +
                (query.importance_weight * importance) +
                (query.similarity_weight * similarity)
            )

            scored_memories.append((total_score, node))

        # Sort descending berdasarkan compound score
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        # Step B: Retrieval Semantic Memory dari Knowledge Graph
        graph_facts = await self.query_knowledge_graph(relevant_entities)

        # Step C: Token Budget Packing & Context Assembly
        max_chars = int(query.token_budget * self.char_per_token)
        allocated_chars = 0
        final_context_blocks: List[str] = []

        # Prioritas 1: Inject Graph Facts (High precision, low token overhead)
        if graph_facts:
            graph_header = "### Verified Relational Facts:\n" + "\n".join(graph_facts)
            final_context_blocks.append(graph_header)
            allocated_chars += len(graph_header)

        # Prioritas 2: Inject Scored Episodic Memories sampai budget habis
        final_context_blocks.append("### Episodic Context:")
        for score, node in scored_memories:
            entry = f"[{time.strftime('%Y-%m-%d %H:%M', time.gmtime(node.created_at))}] (Relevance: {score:.2f}) {node.content}"
            entry_len = len(entry)

            if allocated_chars + entry_len > max_chars:
                # Context limit reached, hentikan injeksi
                break

            final_context_blocks.append(entry)
            allocated_chars += entry_len

            # Update last accessed time
            node.last_accessed_at = current_time

        return "\n".join(final_context_blocks)

# =====================================================================
# Execution & Test Pipeline
# =====================================================================

async def main():
    print("--- Inisialisasi Enterprise Tiered Memory Engine ---")
    engine = TieredMemoryEngine()

    # 1. Setup Working Memory
    await engine.set_working_state("current_task_id", "TASK-8921")
    await engine.set_working_state("agent_mode", "FINANCIAL_ADVISORY")

    # 2. Ingest Episodic Memories (Simulasi riwayat percakapan bertahap)
    # Embedding dummy 4 dimensi untuk demonstrasi
    now = time.time()
    
    # Memori A: Data 10 hari lalu (Decayed, namun relevansi tinggi)
    await engine.ingest_episode(
        node_id="ep_001",
        content="Nasabah menyatakan memiliki alokasi $500,000 untuk reksadana saham berisiko tinggi.",
        embedding=[0.88, 0.12, 0.45, 0.05],
        importance=8.5,
        metadata={"channel": "web_chat"}
    )
    # Modifikasi manual created_at untuk simulasi historis
    engine._episodic_store["ep_001"].created_at = now - (86400 * 10)

    # Memori B: Data 5 menit lalu (Sangat baru, tapi kepentingan rendah)
    await engine.ingest_episode(
        node_id="ep_002",
        content="Nasabah menanyakan apakah kantor cabang Jakarta Pusat buka di hari Sabtu.",
        embedding=[0.11, 0.05, 0.15, 0.92],
        importance=2.0,
        metadata={"channel": "mobile"}
    )

    # Memori C: Data 1 jam lalu (Baru, kepentingan tinggi, relevansi tinggi)
    await engine.ingest_episode(
        node_id="ep_003",
        content="Nasabah menegaskan profil risiko diubah menjadi Konservatif karena rencana pembelian rumah tahun depan.",
        embedding=[0.85, 0.15, 0.50, 0.10],
        importance=9.5,
        metadata={"channel": "mobile"}
    )

    # 3. Ingest Semantic Memory (Relational Graph)
    await engine.ingest_triplet(Triplet(subject="Nasabah", predicate="memiliki_target", object_="Pembelian Rumah 2025"))
    await engine.ingest_triplet(Triplet(subject="Nasabah", predicate="memiliki_entitas_usaha", object_="PT Maju Bersama"))

    # 4. Search Query Simulation
    # Query: "Apa rekomendasi alokasi aset yang sesuai dengan profil risiko terkini nasabah?"
    # Embedding query berkorelasi tinggi dengan topik keuangan/risiko
    query = MemoryQuery(
        query_text="Rekomendasi alokasi profil risiko nasabah",
        query_vector=[0.86, 0.14, 0.48, 0.08],
        token_budget=350,  # Membatasi token budget
        decay_lambda=0.00001  # Lambat meluruh untuk keperluan simulasi
    )

    context = await engine.retrieve_context(
        query=query, 
        relevant_entities=["Nasabah"]
    )

    print("\n[RESULT] Constructed Prompt Injection Context:\n")
    print(context)
    
    # Verifikasi status working memory
    task_id = await engine.get_working_state("current_task_id")
    print(f"\n[WORKING STATE] Current Active Task: {task_id}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Domain: Autonomous Wealth Management & Portfolio Rebalancing Agent
* **Skala Sistem**: Mengelola portofolio lebih dari 150.000 investor High-Net-Worth (HNW) dengan total AUM melampaui $4B.
* **Volume Transaksi**: Rata-rata 250 reasoning loop per agent per hari; 45 juta embedding vectors aktif; 12 juta entity triplets di Knowledge Graph.

#### Tantangan Masalah Arsitektur:
1. **The Amnesia-Distraction Dilemma**: Jika seluruh history chat nasabah selama 6 bulan terakhir diinjeksi, model mengalami *lost-in-the-middle* (abai terhadap mandat kepatuhan/compliance yang ditulis nasabah di masa lalu). Sebaliknya, jika riwayat dibatasi pada 5 turn terakhir, agent merekomendasikan instrumen agresif yang dilarang nasabah sebulan yang lalu.
2. **Race Conditions**: Ketika pasar mengalami fluktuasi tajam (volatilitas tinggi), beberapa sub-agent (Rebalancer Agent, Compliance Checker Agent, Notification Agent) mengakses dan memodifikasi *working memory* status portfolio nasabah secara bersamaan, memicu *phantom allocation*.

#### Solusi Arsitektur yang Diterapkan:
1. **Hybrid Hierarchical Memory Pipeline**:
   * **Working Memory**: Redis 7.2 Cluster dengan active distributed locks (`Redlock`) untuk mengunci ID portofolio nasabah saat rebalancing sedang dikalkulasi.
   * **Episodic Stream**: Apache Kafka menampung seluruh obrolan dan trigger pasar mentah. Konsumen Kafka mentransfer batch ke Qdrant Vector DB dengan dynamic HNSW indexing.
   * **Semantic Knowledge Graph**: Memgraph instance berlatensi rendah. Setiap kali nasabah membuat pernyataan legal (*"Saya tidak ingin memegang saham sektor tembakau"*), background microservice berbasis LangChain mengekstraksi triple: `(Client)-[:RESTRICTS]->(Sector:Tobacco)` dan memvalidasi edge tersebut dengan tanda tangan audit digital.
2. **Deterministic Context Allocation Budget**:
   Total Context Window LLM: 16.384 Token.
   * System & Core Guardrails: 2.000 Token.
   * Procedural Memory (API JSON Schemas): 1.500 Token.
   * Knowledge Graph Facts (Extracted Direct Constraints): 1.500 Token.
   * Episodic Memory (High scored historical events): 4.000 Token.
   * Working Memory / Active Conversation Scratchpad: 3.384 Token.
   * LLM Completion Generation Buffer: 4.000 Token.

#### Metrik Keberhasilan:
* Pengurangan token cost bulanan sebesar **68%** berkat deduplikasi dan komparasi graf dibanding naive sliding window.
* **0% violation** terhadap mandat batasan investasi nasabah (dibandingkan 14.2% error rate sebelum Knowledge Graph restriction memory diterapkan).
* Latensi retrieval kontekstual stabil pada **P99 < 120ms**.

---

### 9. Trade-offs

```
                                 [Vector Storage]
                                 /              \
                                /                \
           High Semantic Similarity               Fast Ephemeral Writes
           Low Relationship Depth                Zero Deep Reasoning
                             /                      \
                            /                        \
          [Knowledge Graph] ---------------------- [Redis Working Memory]
                           Rich Graph Traversal
                           High Mutation Overhead
```

| Parameter Arsitektur | Vector-Only Memory (HNSW / Flat) | Graph-Only Memory (Property Graph) | Hybrid Vector-Graph + Cache |
| :--- | :--- | :--- | :--- |
| **Retrieval Latency** | **Rendah (10-30ms)**. Cepat untuk approximate nearest neighbors. | **Tinggi (50-250ms)**. Sangat tergantung kompleksitas traversal depth ($k$-hop). | **Moderat (40-80ms)**. Memerlukan parallel dispatching dan result re-ranking. |
| **Reasoning Capability** | **Rendah**. Sulit menghubungkan relasi $A \to B \to C$ jika teks tidak berdampingan secara semantik. | **Sangat Tinggi**. Eksplisit mengekspresikan relasi struktural, hirarki, dan kepemilikan. | **Sangat Tinggi**. Menggabungkan kemiripan semantik alami dengan validitas relasi logis. |
| **Write/Indexing Cost** | **Rendah**. Hanya butuh token embedding generation sekali jalan. | **Sangat Tinggi**. Membutuhkan LLM information extraction untuk parsing entitas dan relasi. | **Tinggi**. Menuntut background workers asinkron untuk menjaga decoupling latensi. |
| **Scalability** | **Tinggi**. Partisi horizontal vector sharding sudah terbukti matang. | **Moderat**. Graph sharding lintas cluster distributed node kompleks dan mahal. | **Tinggi (Decoupled)**. Cache, Vector, dan Graph diskalakan secara independen. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Zombie / Stale Context Injection (Memori Kadaluarsa Menimpa Fakta Terkini)
* **Gejala**: Nasabah pindah alamat domisili atau mengganti profil risiko, namun agent tetap mengeksekusi instruksi berdasarkan data lama.
* **Akar Masalah**: Pure cosine similarity mengambil memori masa lalu karena kemiripan leksikal/semantik yang tinggi tanpa memperhitungkan variabel peluruhan waktu (*temporal decay*).
* **Solusi**: Terapkan *Bi-temporal Modeling* (`valid_from`, `valid_until` serta `transaction_time`). Jika fakta baru bertentangan secara relasional, perbarui status node lama pada Knowledge Graph menjadi `INVALIDATED`.

#### 2. Memory Contamination via Hallucination Feedback Loop
* **Gejala**: Agent berhalusinasi pada turn $N$. Jawaban halusinasi tersebut disimpan ke dalam episodic memory. Pada turn $N+5$, agent mengambil halusinasi lamanya sendiri sebagai referensi "fakta ground-truth".
* **Akar Masalah**: Tidak ada validasi atau *epistemic verification* sebelum penyimpanan memori dilakukan (*unsupervised memory ingestion*).
* **Solusi**: Pisahkan memory channel: `User-Generated`, `Tool-Verified`, dan `Model-Synthesized`. Hanya fakta berstatus `Tool-Verified` yang diizinkan masuk ke dalam Knowledge Graph dan Long-Term Core Episodic store.

#### 3. Context Window Fragmentation (Budget Overflow)
* **Gejala**: Request ke LLM provider melempar error `400 Bad Request: Context window exceeded` secara acak di tengah eksekusi panjang.
* **Akar Masalah**: Pengecekan ukuran memori dihitung berdasarkan panjang karakter string mentah (`len(text)`), bukan token BPE/WordPiece aktual yang diproses LLM tokenizer.
* **Solusi**: Integrasikan model tokenizer resmi (`tiktoken` untuk OpenAI, tokenizer HuggingFace untuk open-source model) langsung pada middleware *Context Allocator*.

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic Token Quota**: Tetapkan batas atas token yang kaku untuk masing-masing tier memori (Working, Episodic, Semantic). Jangan biarkan memory retrieval bersifat unbounded.
- [ ] **Background Asynchronous Consolidation**: Jangan pernah melakukan LLM Entity/Triplet Extraction di jalur kritis (*request-response path*) user. Gunakan message broker untuk komputasi asinkron di background.
- [ ] **Distributed Mutex Lock**: Bungkus seluruh mutasi Working State agent dengan distributed lock (misal: Redis Redlock) dengan timeout eksplisit untuk mencegah *split-brain execution*.
- [ ] **Bi-Temporal Edge Validation**: Pastikan setiap relasi fakta memiliki timestamp `asserted_at` dan `expired_at`.
- [ ] **Embeddings Re-indexing Pipeline**: Siapkan arsitektur zero-downtime re-indexing jika di masa depan arsitektur beralih ke model embedding yang lebih baru/besar.
- [ ] **Sanitization on Ingestion**: Jalankan sanitasi PII (Personally Identifiable Information) masking dan security injection scanning sebelum teks disimpan ke dalam episodic database.
- [ ] **Audit Trail & GDPR Eviction API**: Bangun endpoint administratif terverifikasi untuk menghapus node memori berdasarkan `user_id` di seluruh Vector Store, Graph DB, dan Cache secara atomik (*Right to be Forgotten*).

---

### 12. Hands-on Practice

Buat direktori proyek lokal berikut untuk latihan: `hands-on/m02/`

#### Task 1: Setup Lingkungan dan Dependensi
Buat file `requirements.txt`:
```txt
pydantic>=2.5.0
numpy>=1.26.0
tiktoken>=0.5.2
pytest>=7.4.0
pytest-asyncio>=0.21.0
```
Instal ke dalam virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Task 2: Implementasi Memory Compaction Worker
Buat file `hands-on/m02/compactor.py`. Anda wajib mengimplementasikan fungsi rekursif yang memadatkan 10 pesan percakapan lama menjadi 1 ringkasan padat ketika memori melewati batas ambang token tanpa membuang entity penting.

#### Task 3: Verifikasi Concurrency Safety
Buat script test `hands-on/m02/test_concurrency.py` yang menjalankan 50 async tasks memodifikasi state agent secara simultan untuk memastikan tidak ada *state corruption*.

---

### 13. Exercise

#### Level Easy
Modifikasi implementasi fungsi `calculate_retention_score` pada seksi 7A agar menerima parameter batas minimum kelayakan (*threshold*). Jika skor akhir berada di bawah `0.25`, tandai memori tersebut sebagai kandidat *Garbage Collection* (eviksi permanen). Tulis unit test untuk memvalidasi fungsi ini.

#### Level Medium
Kembangkan modul `hands-on/m02/token_budget_manager.py` menggunakan pustaka `tiktoken`. Buat class `TokenBudgetManager` yang mengalokasikan context window secara dinamis:
* Input: List string teks episodik yang diurutkan berdasarkan skor relevance.
* Limit: 500 token.
* Output: List string yang muat tepat di bawah batas 500 token tanpa memotong kata atau melempar exception out-of-context.

#### Level Hard
Rancang modul Python `ConflictResolver` yang menangani pertentangan fakta temporal pada Knowledge Graph.
* Kasus: Database memuat fakta lama: `(Budi)-[:BEKERJA_DI]->(Perusahaan A)`.
* Event baru masuk: *"Mulai bulan depan Budi resmi mengundurkan diri dan bergabung ke Perusahaan B."*
* Syarat: Sistem harus mendeteksi kontradiksi ini secara semantik, memberikan tag `status: deprecated` pada edge Perusahaan A dengan timestamp expired, dan membuat edge baru ke Perusahaan B dengan status `future_active`.

---

### 14. Challenge

**Skenario**: Anda adalah Principal AI Engineer di Bank Sentral yang memimpin pembangunan Multi-Agent System untuk mendeteksi kecurangan transaksi valas lintas negara.

**Tantangan**:
1. Agent harus beroperasi terus-menerus selama berbulan-bulan (*life-long persistent memory*).
2. Sistem memiliki regulasi ketat: Data perbankan transaksi sensitif (PII) wajib dihapus dalam kurun waktu 30 hari, namun **pola anomali (graph topological structure)** yang telah dipelajari dari transaksi tersebut **tidak boleh hilang** karena krusial untuk investigasi masa depan.
3. Rancang arsitektur data sistem memori yang dapat melakukan *anonymized structural retention*:
   * Pisahkan data node identitas nasabah dari data relasi topologi perilaku transaksi.
   * Rancang mekanisme *ticking eviction engine* yang menghapus data mentah di Vector Store tepat pada hari ke-30 tanpa merusak relasi keterhubungan clustering di Knowledge Graph.
   * Tuliskan dokumen arsitektur teknis lengkap (spesifikasi database, payload schema, strategi partitioning, dan algoritma pseudocode retention) ke dalam file `hands-on/m02/CHALLENGE_ARCH_SPEC.md`.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa teknik *naive sliding window* (memotong percakapan hanya berdasarkan $k$-turn terakhir) berbahaya bagi enterprise AI Agent?
2. Komponen memori manakah yang paling tepat untuk menyimpan aturan validasi skema JSON dari sebuah REST API tools: Episodic, Working, Semantic, atau Procedural Memory?
3. Apa peran matematis dari konstanta $\lambda$ pada formula *exponential decay* $e^{-\lambda \cdot \Delta t}$?
4. Mengapa representasi graf (*Knowledge Graph*) jauh lebih unggul daripada *Dense Vector Search* untuk menjawab pertanyaan relasi multi-entitas (*multi-hop reasoning*)?
5. Apa konsekuensi teknis jika kita menggunakan fungsi panjang karakter string (`len(text)`) sebagai proxy estimasi token budget LLM?

#### B. Pertanyaan Intermediate
1. Bagaimana arsitektur *Bi-temporal Data Modeling* mencegah memori kadaluarsa (zombie memory) menimpa fakta terkini di Knowledge Graph?
2. Jelaskan bahaya fenomena *Epistemic Contamination* (kontaminasi halusinasi balik) pada sistem memori agent dan bagaimana arsitektur ingestion memitigasinya!
3. Dalam kondisi apa dense vector search gagal menemukan konteks yang relevan meskipun teks jawaban persis ada di dalam database vektor?
4. Mengapa background worker untuk konsolidasi memori (seperti ekstraksi graf) harus dipisahkan secara asinkron dari inference request-response pipeline?
5. Bagaimana cara kerja distributed locking (seperti Redis Redlock) dalam mencegah inkonsistensi data pada *Working Memory* agent yang memiliki arsitektur sub-agent paralel?

#### C. Skenario Kasus Produksi
1. **Skenario 1**: Sebuah Customer Service Agent di platform e-commerce tiba-tiba memberikan diskon 90% kepada pengguna. Setelah diaudit, pengguna tersebut sebelumnya mengatakan *"Sistem Anda kemarin menjanjikan saya diskon 90% karena kompensasi barang rusak"*, dan informasi ini masuk ke episodic memory tanpa filter. Bagaimana Anda mendesain arsitektur memory ingestion pipeline untuk mencegah prompt injection berbasis memori palsu seperti ini?
2. **Skenario 2**: Agent internal analitik korporat mengalami lonjakan latensi dramatis dari 800ms menjadi 14 detik per respons setelah beroperasi selama 3 bulan tanpa henti. Database Vector dan Graph berjalan normal secara resource CPU/RAM. Apa kemungkinan bottleneck yang terjadi pada *Context Window Orchestrator* dan bagaimana langkah perbaikannya?
3. **Skenario 3**: Sebuah institusi medis menggunakan agent untuk memonitor riwayat resep pasien. Pasien menyatakan alergi antibiotik Penisilin 2 tahun lalu di Episode #12. Namun pada Episode #480 kemarin, dokter meresepkan turunan Penisilin karena catatan alergi tidak masuk ke dalam 5 vector chunk teratas. Bagaimana Anda mengonfigurasi skoring memori agar fakta krusial (kesehatan/keamanan) tidak tereliminasi oleh faktor recency decay?

---

#### Kunci Jawaban & Pembahasan Quiz

##### Jawaban Basic
1. *Naive sliding window* memotong konteks secara arbitrer berdasarkan urutan waktu. Informasi penting, persetujuan legal, atau batasan sistem yang terjadi di awal percakapan akan terbuang, menyebabkan agent mengalami "amnesia parsial" dan rentan mengulang kesalahan atau melanggar kesepakatan awal.
2. **Procedural Memory**, karena berisi spesifikasi instruksi deterministik, kontrak antarmuka eksekusi, dan pedoman operasional baku yang tidak berubah secara dinamis berdasarkan percakapan temporal.
3. $\lambda$ berfungsi sebagai parameter akselerasi peluruhan (*decay rate*). Semakin besar nilai $\lambda$, semakin cepat skor signifikansi memori masa lalu menyusut mendekati nol seiring berjalannya waktu.
4. Karena Dense Vector Search mencari kedekatan semantik global di ruang vektor (*surface level similarity*), bukan relasi logis formal. Knowledge Graph dapat menelusuri rantai relasi bertingkat secara deterministik ($A \to B \to C$) tanpa terdistorsi oleh noise kemiripan kata.
5. Rasio karakter terhadap token sangat fluktuatif tergantung bahasa, karakter khusus, kode, atau format JSON (dapat berkisar dari 1 token = 1 karakter hingga 1 token = 4 karakter). Menggunakan estimasi karakter dapat melampaui context window keras LLM dan memicu *runtime API crash*.

##### Jawaban Intermediate
1. *Bi-temporal Modeling* membedakan antara waktu terjadinya peristiwa di dunia nyata (*event time*) dan waktu fakta dicatat di sistem (*system assertion time*). Ditambah kolom `valid_until`, sistem dapat memfilter node fakta lama agar tidak dieksekusi pada query masa kini, tanpa menghapus jejak histori audit transaksi masa lalu.
2. *Epistemic Contamination* terjadi ketika halusinasi model tersimpan sebagai memori permanen dan diambil kembali di masa depan sebagai "kebenaran". Mitigasinya adalah memisahkan namespace penyimpanan: memori model yang belum diverifikasi tool/sistem diisolasi dan dilarang dikonsolidasikan ke Long-Term Semantic Graph.
3. Masalah *Vector Disconnection* atau *Out-of-Vocabulary Context*: Ketika query pengguna menggunakan terminologi leksikal spesifik (seperti ID transaksi, error code numerik, atau nama produk unik) yang tidak memiliki keterikatan semantik konseptual pada ruang embedding dense. Kasus ini memerlukan *Hybrid Search* (Dense Cosine + Sparse BM25).
4. Karena proses ekstraksi entitas dan relasi Knowledge Graph membutuhkan inferensi LLM tambahan yang memakan waktu ratusan hingga ribuan milidetik. Menaruhnya di jalur sinkron akan meningkatkan latensi respons ke user secara tidak dapat diterima.
5. Distributed lock memastikan bahwa hanya satu sub-agent yang dapat membaca, memodifikasi, dan menulis kembali state scratchpad agent pada satu waktu (*atomic execution*), menghindari bug *lost-update* atau *race condition* saat beberapa sub-agent mengevaluasi kondisi secara paralel.

##### Jawaban Skenario Kasus Produksi
1. **Solusi Skenario 1**: Implementasikan arsitektur *Dual-Channel Memory Ingestion with Truth Grounding*. Pisahkan penyimpanan: input percakapan pengguna hanya diklasifikasikan sebagai `UNVERIFIED_USER_CLAIM`. Agent dilarang mengambil klaim pengguna sebagai aksi kebijakan sebelum terverifikasi oleh *Tool Execution Event* (seperti query ke database tiket kompensasi resmi). Setiap entri memori harus memiliki metadata cryptographic hash dan sumber asal (`provenance`).
2. **Solusi Skenario 2**: Bottleneck terjadi karena volume memori episodik yang diambil (*retrieved chunks*) tidak dibatasi secara dinamis, sehingga Context Orchestrator mengirimkan payload token yang mendekati batas maksimal context window LLM. Hal ini menyebabkan lonjakan drastis pada proses inferensi LLM (*prefill / time-to-first-token* meningkat secara kuadratik seiring panjangnya token). Perbaikan: Pasang token budget manager yang ketat, lakukan cross-encoder re-ranking untuk hanya mengambil maksimal $k$ memori terbaik, serta terapkan *memory compaction* di level storage.
3. **Solusi Skenario 3**: Sesuaikan kalkulasi skoring memori. Berikan bobot absolut atau *infinite non-decay flag* untuk kategori memori dengan tingkat kritikalitas tinggi (`critical_tags: ["allergy", "fatal_risk"]`). Pada formula scoring, kondisi khusus ini mengabaikan fungsi peluruhan waktu: jika `node.importance == 10.0`, maka nilai $Recency$ dipaksa bernilai konstan $1.0$. Selain itu, data alergi harus diekstraksi ke level Knowledge Graph sebagai relasi permanen `(Patient)-[:ALLERGIC_TO]->(Substance)` yang dievaluasi melalui deterministic constraint check sebelum resep diproses.

---

### 16. Summary

Sistem Memori Agentik tingkat enterprise adalah fondasi yang membedakan skrip otomasi sederhana (*stateless LLM wrapper*) dengan AI Agent otonom skala industri. Memori bukan sekadar riwayat obrolan yang ditumpuk di context window, melainkan arsitektur data terdistribusi multi-tier:
1. **Working Memory** menangani eksekusi lokal latensi ultra-rendah dan konkurensi state.
2. **Episodic Memory** menyimpan riwayat peristiwa autobiografis dengan mempertimbangkan relevansi, kepentingan, dan peluruhan waktu matematis.
3. **Semantic Memory** menyusun peta dunia faktual yang kokoh menggunakan Knowledge Graph untuk inferensi multi-hop deterministik.
4. **Procedural Memory** menjamin integritas langkah kerja dan pemanggilan tools sesuai kontrak protokol.

Dengan menerapkan prinsip *decoupled background consolidation*, *deterministic token budget allocation*, serta sanitasi kepatuhan data yang ketat, arsitektur memori agentic mampu menjaga presisi reasoning, menekan biaya inferensi secara drastis, dan mencegah kegagalan fatal pada operasional mission-critical enterprise.