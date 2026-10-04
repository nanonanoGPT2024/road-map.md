# Bab 06: Advanced RAG Optimasi, Evaluasi & Production Pipeline
## Module 01: Arsitektur Advanced RAG, Hybrid Retrieval, Reranking, dan Evaluasi Berkelanjutan

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Keterbatasan Naive RAG**: Mengidentifikasi titik kegagalan (*failure modes*) arsitektur *Naive Retrieval-Augmented Generation* (RAG) pada beban kerja enterprise, khususnya *semantic drift*, *lost-in-the-middle phenomenon*, serta *low precision/recall* pada data leksikal terstruktur.
2. **Merancang Pipeline Hybrid Retrieval**: Mengintegrasikan pencarian berbasis leksikal (*sparse* / BM25) dan semantik (*dense vector embeddings*) menggunakan algoritma *Reciprocal Rank Fusion* (RRF) dengan parameter tuning optimal.
3. **Mengimplementasikan Post-Retrieval Reranking**: Mengonfigurasi dan mendeploy model *Cross-Encoder* dua arah (*bidirectional attention*) untuk memvalidasi relevansi dokumen hasil retrieval awal, menekan rasio *noise* sebelum konteks disalurkan ke *Large Language Model* (LLM).
4. **Membangun Sistem Contextual Compression & Chunk Routing**: Menerapkan pola *Parent-Document Retrieval* (Hierarchical Chunking) guna memitigasi fragmentasi konteks dan memaksimalkan *signal-to-noise ratio* (SNR) pada *prompt context window*.
5. **Mengukur Metrik RAG Triad**: Mengotomatisasi evaluasi kualitas pipeline RAG menggunakan framework evaluasi terstandarisasi untuk mengukur *Context Precision*, *Context Recall*, *Faithfulness* (Groundedness), dan *Answer Relevance*.

---

### 2. Concept Overview

Arsitektur RAG modern telah berevolusi dari pola sekuensial sederhana (*Retrieve $\rightarrow$ Augment $\rightarrow$ Generate*) menuju arsitektur multi-tahap non-linear yang dilengkapi mekanisme koreksi kesalahan dinamis. *Naive RAG* memiliki ketergantungan fatal pada model embedding bi-encoder: model ini mengompresi dokumen ke dalam vektor titik tunggal pada ruang laten berdimensi tinggi ($d$-dimensional space), yang rentan kehilangan detail granular seperti nomor model, tanggal, atau sinonim spesifik industri.

```
       Naive RAG: Query ──> [Bi-Encoder Embedding] ──> [Vector DB] ──> [Top-k Docs] ──> [LLM]
                                                                                       ▲
                                                           Tinggi Risiko Noise & Halusinasi ──┘
```

Untuk memecahkan masalah ini, **Advanced RAG** memperkenalkan tiga pilar utama:
1. **Pre-Retrieval Optimization**: Normalisasi query, *Hypothetical Document Embeddings* (HyDE), dan ekspansi sinonim.
2. **Retrieval Optimization**: *Hybrid Search* yang menggabungkan kekuatan pemetaan kata kunci eksak dari *Sparse Retrievers* (misalnya BM25 atau SPLADE) dengan pemahaman konseptual dari *Dense Retrievers* (misalnya text-embedding-3, BGE-large), disintesiskan melalui *Reciprocal Rank Fusion* (RRF).
3. **Post-Retrieval Optimization**: *Contextual Reranking* menggunakan *Cross-Encoder* yang memproses pasangan *query-document* secara simultan via mekanisme *full cross-attention*, diikuti penataan ulang konteks untuk menghindari degradasi *attention* LLM di bagian tengah teks (*Lost-in-the-middle phenomenon*).

---

### 3. Why It Matters

Dalam lingkungan enterprise, kegagalan sistem RAG berdampak langsung pada liabilitas hukum, finansial, dan reputasi:
- **Halusinasi Akibat Unretrieved Documents**: Jika retriever gagal menarik pasal pembatalan spesifik pada kontrak hukum 200 halaman karena batasan kemiripan kosinus (*cosine similarity*), LLM akan mengekstrapolasi jawaban berdasarkan bias bobot parametriknya, menghasilkan jawaban salah yang tampak meyakinkan.
- **Biaya Komputasi dan Latensi Context Window**: Memasukkan 20 *chunks* mentah berukuran masing-masing 512 token langsung ke context window model frontier (seperti GPT-4 atau Claude 3.5 Sonnet) meningkatkan latensi hingga ratusan milidetik dan memperbesar tagihan token inference secara signifikan, sementara 70% dari teks tersebut sering kali adalah *noise* non-kritis.
- **SLA Keandalan Produksi**: Naive RAG rata-rata hanya mencapai akurasi faktual berkisar antara 60-70% pada domain teknis kompleks. Pipeline Advanced RAG yang dioptimalkan dengan Hybrid Search dan Reranking terbukti meningkatkan *Context Precision* hingga >92%, memenuhi kriteria *Service Level Agreement* (SLA) perbankan dan kesehatan.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur produksi Advanced RAG dari mulai ingestion multi-tahap hingga evaluasi runtime:

```
[ INGESTION PIPELINE ]
Raw Documents (.pdf/.docx/.md)
      │
      ▼
Hierarchical Chunking
 ├── Parent Chunks (2048 tokens) ───────────────► Storage: Relational/Doc Store (Postgres/Redis)
 └── Child Chunks (256-512 tokens)
          ├──► Sparse Encoder (BM25 Index / Token Inverted Index)
          └──► Dense Encoder (Bi-Encoder Embedding Model) ──► Vector Index (HNSW/IVFFlat)

─────────────────────────────────────────────────────────────────────────────────────────────

[ RUNTIME RETRIEVAL & GENERATION PIPELINE ]
User Query
      │
      ▼
[ Query Rewriter / HyDE Generator ]
      │
      ├────────────────────────────────┬───────────────────────────────┐
      │ (Lexical Search)               │ (Vector Search)               │ (Metadata Filter)
      ▼                                ▼                               ▼
[BM25 Sparse Retrieval]        [Dense Vector Retrieval]     [Payload/Tenant Filter]
 Top-N (BM25 Hits)              Top-N (Vector Cosine Hits)              │
      │                                │                                │
      └─────────────────┬──────────────┘                                │
                        ▼                                               │
           [Reciprocal Rank Fusion (RRF)] ◄─────────────────────────────┘
                        │
                        ▼ Top-K Fused Candidates
           [Cross-Encoder Reranker]
            (Computes Score(q, d_i) via Full Attention)
                        │
                        ▼ Top-M Reranked Docs
           [Context Synthesizer & Compressor]
            - Parent-Document Lookup (Fetch Parent from Doc Store)
            - Lost-in-the-Middle Reordering (Best chunks at start & end)
                        │
                        ▼ Optimized Context
           [LLM Inference (Generation)]
                        │
                        ├───► Final Response to User
                        │
                        ▼
[ ASYNCHRONOUS EVALUATION ENGINE (Ragas / TruLens Pattern) ]
 ├── Context Precision
 ├── Context Recall
 ├── Faithfulness (LLM-as-a-Judge)
 └── Answer Relevance
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Hybrid Search & Reciprocal Rank Fusion (RRF)
Metode pencarian leksikal (BM25) unggul dalam menangkap istilah presisi (seperti UUID, kode kesalahan, terminologi medis unik), tetapi gagal total jika pengguna menggunakan parafrase atau analogi. Sebaliknya, pencarian vektor *dense* unggul dalam sinonim dan pemahaman konseptual, namun memiliki ambiguitas tinggi saat membedakan kata dengan leksikal serupa yang memiliki arti berlawanan.

Untuk menggabungkan skor dari ruang metrik yang berbeda (skor BM25 tidak terbatas, sedangkan kemiripan kosinus bernilai $[-1, 1]$), kita menggunakan **Reciprocal Rank Fusion (RRF)**:

$$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$

Di mana:
- $M$ adalah himpunan sistem retrieval (misal: `{BM25, DenseVector}`).
- $r_m(d)$ adalah posisi peringkat dokumen $d$ pada sistem retrieval $m$ (dimulai dari 1).
- $k$ adalah konstanta perataan (*smoothing constant*), umumnya disetel ke $60$. Parameter ini mencegah peringkat teratas dari satu sistem mendominasi hasil akhir secara berlebihan.

#### B. Cross-Encoder Reranking
*Bi-encoder* (seperti OpenAI embeddings) memproses query $q$ dan dokumen $d$ secara terisolasi menjadi vektor independen:

$$s_{bi} = \langle \mathbf{u}_q, \mathbf{v}_d \rangle = \mathbf{u}_q \cdot \mathbf{v}_d$$

Kelemahannya adalah tidak ada interaksi langsung antar-token antara query dan dokumen selama proses representasi.

*Cross-Encoder* memproses pasangan query dan dokumen secara simultan ke dalam transformer:

$$s_{cross} = \text{Softmax}(\mathbf{W} \cdot \text{Transformer}([CLS] \circ q \circ [SEP] \circ d \circ [SEP]))$$

Setiap token pada $q$ dapat memberikan bobot *attention* terhadap setiap token pada $d$. Hal ini memberikan akurasi penentuan relevansi yang jauh lebih tinggi dengan konsekuensi latensi komputasi $O(N)$ di mana $N$ adalah jumlah dokumen kandidat. Karena itu, Cross-Encoder hanya digunakan sebagai *reranker* tahap kedua (*second-stage reranker*) pada subset kecil dokumen terbaik ($top\text{-}k \approx 20\text{--}50$).

#### C. Lost-in-the-Middle Mitigation
Studi empiris (Liu et al., 2023) menunjukkan bahwa LLM memiliki bias perhatian berbentuk busur U (*U-shaped attention curve*): LLM paling efektif mengekstrak informasi yang berada di awal (*primacy effect*) dan di akhir (*recency effect*) dari konteks prompt yang panjang. Informasi yang berada di tengah-tengah rentan diabaikan. Pipeline Advanced RAG harus menyortir dokumen hasil reranking secara zigzag:
- Peringkat 1 $\rightarrow$ Awal konteks
- Peringkat 2 $\rightarrow$ Akhir konteks
- Peringkat 3 $\rightarrow$ Posisi ke-2 dari awal
- Peringkat 4 $\rightarrow$ Posisi ke-2 dari akhir, dan seterusnya.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi referensi pipeline Advanced RAG lengkap, mencakup:
- Pydantic models untuk validasi data
- BM25 Sparse Search + Cosine Dense Vector Search
- Reciprocal Rank Fusion (RRF)
- Cross-Encoder Reranking
- Lost-in-the-middle context reordering
- Fallback circuit-breaker untuk resiliensi operasional

```python
# advanced_rag_pipeline.py
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AdvancedRAG")


# ==========================================
# Domain Models (Pydantic v2)
# ==========================================
class DocumentChunk(BaseModel):
    id: str = Field(description="Unique identifier chunk")
    parent_id: Optional[str] = Field(default=None, description="Identifier dokumen induk")
    content: str = Field(description="Teks chunk aktual")
    dense_vector: Optional[List[float]] = Field(default=None, description="Vektor embedding")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata pendukung")


class ScoredChunk(BaseModel):
    chunk: DocumentChunk
    score: float = Field(description="Skor relevansi hasil retrieval/rerank")


# ==========================================
# Abstraksi Interface
# ==========================================
class EmbedderClient(Protocol):
    async def embed_query(self, text: str) -> List[float]:
        ...


class CrossEncoderClient(Protocol):
    async def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        ...


# ==========================================
# In-Memory Search Engine Implementation
# (BM25 + Dense Vector Engine)
# ==========================================
class SimpleBM25:
    """Implementasi murni BM25 Okapi untuk demonstrasi sparse retrieval."""

    def __init__(self, corpus: Sequence[DocumentChunk], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.doc_len = [len(doc.content.lower().split()) for doc in corpus]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0
        self.df: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_freqs: List[Dict[str, int]] = []
        self._initialize()

    def _initialize(self) -> None:
        for doc in self.corpus:
            frequencies: Dict[str, int] = {}
            for word in doc.content.lower().split():
                frequencies[word] = frequencies.get(word, 0) + 1
            self.doc_freqs.append(frequencies)
            for word in frequencies.keys():
                self.df[word] = self.df.get(word, 0) + 1

        for word, freq in self.df.items():
            # Standard Lucene/BM25 IDF formula
            self.idf[word] = math.log(1 + (len(self.corpus) - freq + 0.5) / (freq + 0.5))

    def search(self, query: str, top_k: int = 10) -> List[ScoredChunk]:
        query_terms = query.lower().split()
        scores: List[float] = [0.0] * len(self.corpus)

        for i, doc_freq in enumerate(self.doc_freqs):
            score = 0.0
            for term in query_terms:
                if term not in doc_freq:
                    continue
                tf = doc_freq[term]
                idf = self.idf.get(term, 0.0)
                numerator = idf * tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (self.doc_len[i] / self.avgdl))
                score += numerator / denominator
            scores[i] = score

        ranked_indices = np.argsort(scores)[::-1][:top_k]
        return [
            ScoredChunk(chunk=self.corpus[idx], score=float(scores[idx]))
            for idx in ranked_indices
            if scores[idx] > 0.0
        ]


# ==========================================
# Core Advanced RAG Orchestrator
# ==========================================
class AdvancedRetriever:
    def __init__(
        self,
        corpus: List[DocumentChunk],
        embedder: EmbedderClient,
        cross_encoder: Optional[CrossEncoderClient] = None,
        rrf_k: int = 60,
    ):
        self.corpus = corpus
        self.embedder = embedder
        self.cross_encoder = cross_encoder
        self.rrf_k = rrf_k
        self.bm25_index = SimpleBM25(corpus)

    def _cosine_similarity(self, vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    async def _dense_search(self, query_vector: List[float], top_k: int) -> List[ScoredChunk]:
        scores: List[Tuple[DocumentChunk, float]] = []
        for doc in self.corpus:
            if doc.dense_vector is None:
                continue
            sim = self._cosine_similarity(query_vector, doc.dense_vector)
            scores.append((doc, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [ScoredChunk(chunk=doc, score=score) for doc, score in scores[:top_k]]

    def _reciprocal_rank_fusion(
        self,
        ranked_lists: List[List[ScoredChunk]],
        top_k: int,
    ) -> List[ScoredChunk]:
        """Penggabungan peringkat deterministik menggunakan parameter smoothing rrf_k."""
        fused_scores: Dict[str, float] = {}
        chunk_lookup: Dict[str, DocumentChunk] = {}

        for rank_list in ranked_lists:
            for rank, scored_chunk in enumerate(rank_list, start=1):
                chunk_id = scored_chunk.chunk.id
                chunk_lookup[chunk_id] = scored_chunk.chunk
                if chunk_id not in fused_scores:
                    fused_scores[chunk_id] = 0.0
                fused_scores[chunk_id] += 1.0 / (self.rrf_k + rank)

        sorted_items = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        return [
            ScoredChunk(chunk=chunk_lookup[chunk_id], score=score)
            for chunk_id, score in sorted_items[:top_k]
        ]

    def _reorder_lost_in_the_middle(self, chunks: List[ScoredChunk]) -> List[ScoredChunk]:
        """
        Menata ulang chunks untuk menghindari fenomena Lost-in-the-Middle.
        Dokumen paling relevan ditaruh di awal dan akhir list.
        """
        if len(chunks) <= 2:
            return chunks

        reordered: List[Optional[ScoredChunk]] = [None] * len(chunks)
        left = 0
        right = len(chunks) - 1

        for i, item in enumerate(chunks):
            if i % 2 == 0:
                reordered[left] = item
                left += 1
            else:
                reordered[right] = item
                right -= 1

        return [c for c in reordered if c is not None]

    async def retrieve(
        self,
        query: str,
        top_candidates: int = 15,
        final_top_k: int = 5,
    ) -> List[ScoredChunk]:
        try:
            logger.info("Memulai Hybrid Retrieval untuk query: '%s'", query)

            # 1. Jalankan Dense Retrieval & Sparse Retrieval paralel
            query_vector = await self.embedder.embed_query(query)
            dense_task = asyncio.create_task(self._dense_search(query_vector, top_k=top_candidates))
            sparse_hits = self.bm25_index.search(query, top_k=top_candidates)
            dense_hits = await dense_task

            # 2. Fuse hasil via RRF
            fused_candidates = self._reciprocal_rank_fusion(
                [sparse_hits, dense_hits],
                top_k=top_candidates,
            )

            if not fused_candidates:
                logger.warning("Tidak ditemukan kandidat dokumen untuk query.")
                return []

            # 3. Post-Retrieval Reranking (Cross-Encoder)
            reranked_chunks: List[ScoredChunk] = []
            if self.cross_encoder is not None:
                logger.info("Menjalankan Cross-Encoder Reranking pada %d kandidat...", len(fused_candidates))
                try:
                    pairs = [(query, c.chunk.content) for c in fused_candidates]
                    rerank_scores = await self.cross_encoder.predict(pairs)
                    for item, r_score in zip(fused_candidates, rerank_scores):
                        reranked_chunks.append(ScoredChunk(chunk=item.chunk, score=r_score))
                    reranked_chunks.sort(key=lambda x: x.score, reverse=True)
                    reranked_chunks = reranked_chunks[:final_top_k]
                except Exception as ex:
                    logger.error("Reranker gagal dieksekusi: %s. Melakukan fallback ke skor RRF.", str(ex))
                    reranked_chunks = fused_candidates[:final_top_k]
            else:
                reranked_chunks = fused_candidates[:final_top_k]

            # 4. Context Optimization: Lost-in-the-Middle Mitigation
            optimized_context = self._reorder_lost_in_the_middle(reranked_chunks)
            logger.info("Berhasil mengembalikan %d dokumen teroptimasi.", len(optimized_context))
            return optimized_context

        except Exception as e:
            logger.critical("Critical failure pada AdvancedRetriever: %s", str(e), exc_info=True)
            raise RuntimeError(f"Retrieval pipeline gagal: {e}") from e


# ==========================================
# Verification & Mock Testbed
# ==========================================
class DummyEmbedder:
    async def embed_query(self, text: str) -> List[float]:
        # Return arbitrary deterministic vector berdimensi 3
        # Dimensi 0 merepresentasikan intensitas leksikal 'alpha'
        return [float("alpha" in text.lower()), 0.5, 0.2]


class DummyCrossEncoder:
    async def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        scores = []
        for q, c in pairs:
            # Berikan skor tinggi jika kata pertama query ada dalam dokumen
            q_first = q.split()[0].lower() if q.split() else ""
            score = 0.95 if q_first in c.lower() else 0.15
            scores.append(score)
        return scores


async def main() -> None:
    corpus = [
        DocumentChunk(
            id="doc-1",
            content="Instruksi implementasi protokol enkripsi Alpha-9 pada server enterprise.",
            dense_vector=[1.0, 0.4, 0.1],
        ),
        DocumentChunk(
            id="doc-2",
            content="Panduan reset password dan otentikasi multi-faktor Active Directory.",
            dense_vector=[0.0, 0.9, 0.8],
        ),
        DocumentChunk(
            id="doc-3",
            content="Sistem pemantauan Alpha-9 mendeteksi anomali pada port 8080.",
            dense_vector=[0.9, 0.5, 0.3],
        ),
        DocumentChunk(
            id="doc-4",
            content="Standar Operasional Prosedur manajemen data center dan pendingin udara.",
            dense_vector=[0.1, 0.2, 0.9],
        ),
    ]

    retriever = AdvancedRetriever(
        corpus=corpus,
        embedder=DummyEmbedder(),
        cross_encoder=DummyCrossEncoder(),
        rrf_k=60,
    )

    query = "Alpha-9 protokol error"
    results = await retriever.retrieve(query=query, top_candidates=3, final_top_k=2)

    print("\n=== FINAL RANKED & REORDERED CONTEXT ===")
    for rank, res in enumerate(results, 1):
        print(f"[{rank}] ID: {res.chunk.id} | Score: {res.score:.4f} | Text: {res.chunk.content}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

Berikut adalah rincian potensi kegagalan pipeline produksi dan mitigasinya:

| Failure Mode | Mekanisme Penyebab | Dampak Operasional | Solusi / Mitigasi Teknis |
| :--- | :--- | :--- | :--- |
| **Out-of-Vocabulary (OOV) Embedding Collapse** | Simbol unik, ID transaksi hexadesimal, atau regex syntax diabaikan oleh Bi-Encoder tokenizer. | Nilai cosine similarity seragam/rendah, retrieval menghasilkan dokumen acak. | Wajib menggunakan BM25/Splade sebagai fallback sparse dengan normalisasi regex tokenizer. |
| **Cross-Encoder Latency Spike** | Mengirimkan kandidat dokumen terlalu banyak ($top\text{-}k > 50$) ke transformer Cross-Encoder. | P99 latency melonjak drastis (>3 detik), menyebabkan timeout pada gateway HTTP. | Batasi input Cross-Encoder pada rentang $15 \leq top\text{-}k \leq 30$, gunakan arsitektur *distilled* (misal: `bge-reranker-base` atau MiniLM-L6). |
| **Information Density Mismatch** | Dokumen chunk terlalu besar (>1000 token) sehingga detail spesifik larut dalam representasi vektor. | *Signal-to-Noise Ratio* turun drastis, precision runtuh. | Terapkan *Parent-Document Pattern*: cari chunk anak berukuran 200 token, lalu inject chunk induk 1000 token ke prompt LLM. |
| **Context Redundancy & Near-Duplicates** | Dokumen sumber memiliki banyak versi revisi yang hampir identik. | Context window penuh dengan teks duplikat, mengurangi keragaman fakta. | Terapkan *Maximal Marginal Relevance* (MMR) atau klastering semantik berbasis cosine distance sebelum tahap reranking. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur dalam Advanced RAG membawa kompromi yang perlu dipertimbangkan:

```
                Biaya Komputasi Rendah, Latensi Rendah
                                ▲
                                │   [Naive RAG]
                                │   (Bi-Encoder Vector Only)
                                │
                                │             [Advanced Hybrid RAG]
                                │             (BM25 + Dense + Cross-Encoder)
                                │
                                │                          [Agentic / GraphRAG]
                                │                          (Entity-Graph + Multi-Hop)
                                ▼
               Biaya Komputasi Tinggi, Latensi Tinggi
       ◄──────────────────────────────────────────────────────►
   Akurasi Leksikal Rendah                       Akurasi Relasional Tinggi
```

#### Perbandingan Pendekatan Retrieval

1. **Dense Retrieval Murni (Bi-Encoder)**:
   - *Pros*: Sangat cepat (sub-10ms via HNSW), memetakan kesamaan konseptual dengan sangat baik.
   - *Cons*: Buruk pada kata kunci eksak, akronim, SKU barang, dan kode error.
2. **Hybrid Retrieval (BM25 + Dense) dengan RRF**:
   - *Pros*: Ketahanan tinggi terhadap ragam format query tanpa perlu hyperparameter tuning skor manual.
   - *Cons*: Membutuhkan pemeliharaan dua indeks terpisah (misal OpenSearch untuk inverted index + Qdrant/Pinecone untuk HNSW).
3. **GraphRAG (Knowledge Graphs + Vector)**:
   - *Pros*: Menyelesaikan *multi-hop reasoning* kompleks di mana hubungan antar-entitas terpisah jauh di dokumen berbeda.
   - *Cons*: Biaya *indexing* sangat mahal (memerlukan ekstraksi LLM untuk node & edge), query latency tinggi.

---

### 9. Best Practices & Standard Industri

Untuk memastikan kesiapan level produksi (Enterprise-Grade SLA):

1. **Dynamic Chunking over Fixed Window**: Hindari chunking statis berbasis karakter murni tanpa memperhatikan batas sintaksis. Gunakan *Markdown/Code Chunking* atau *Semantic Chunking* (memutus teks pada perubahan tajam gradien *cosine similarity* antar-kalimat).
2. **Deterministic Context Formatting**: Bungkus setiap konteks dokumen dalam boundary XML/Markdown yang ketat guna mencegah serangan *prompt injection* tidak langsung (*Indirect Prompt Injection*):
   ```xml
   <context>
     <document id="doc-123" source="hr_policy.pdf">
       [Isi teks chunk]
     </document>
   </context>
   ```
3. **Semantic Caching**: Pasang lapisan *cache semantik* (misal Redis VL atau GPTCache) di depan pipeline. Jika query baru memiliki kemiripan $\geq 0.96$ dengan query yang sudah tersimpan, langsung sajikan respons LLM sebelumnya untuk memangkas latensi menjadi <50ms dan memotong biaya API LLM.
4. **Automated Evaluation Telemetry**: Pasang telemetry berbasis framework evaluasi seperti Ragas. Setiap sampel respons dari pipeline produksi harus dicatat secara asinkron ke analitik store (misalnya ClickHouse/Arize Phoenix) untuk mengukur metrik berikut:
   - **Context Precision**: Apakah semua konteks yang ditarik relevan?
   - **Faithfulness**: Apakah respons turunan sepenuhnya dapat dibuktikan dari konteks (*grounded*) tanpa halusinasi parametrik?

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertugas membangun sistem tanya-jawab internal untuk dokumen kepatuhan perbankan (*Core Banking Incident Runbook*). Data berisi kode error kritis, UUID sistem, dan prosedur manual. Anda harus membuktikan bahwa Hybrid Search + Cross-Encoder Reranking mengungguli Dense Search konvensional.

#### Langkah 1: Persiapan Lingkungan
Jalankan perintah berikut di terminal:
```bash
python3 -m venv rag_env
source rag_env/bin/activate
pip install numpy pydantic sentence-transformers ragas datasets
```

#### Langkah 2: Buat File `lab_hybrid_rag.py`
Tuliskan implementasi eksperimen yang membandingkan performa retrieval:

```python
import asyncio
from sentence_transformers import CrossEncoder, SentenceTransformer
from advanced_rag_pipeline import AdvancedRetriever, DocumentChunk

# 1. Definisi Corpus Domain Spesifik
BANKING_CORPUS = [
    DocumentChunk(
        id="RUNBOOK-4041",
        content="Kode Error ERR-SYS-8012: Kegagalan koneksi database core banking. Lakukan failover ke DR Cluster Jakarta dalam kurun waktu 5 menit.",
        metadata={"priority": "CRITICAL"}
    ),
    DocumentChunk(
        id="RUNBOOK-4042",
        content="Kode Error ERR-SYS-8013: Sinkronisasi batch transfer interbank tertunda. Verifikasi status antrean di Message Broker RabbitMQ.",
        metadata={"priority": "HIGH"}
    ),
    DocumentChunk(
        id="POLICY-1001",
        content="Kebijakan batas waktu toleransi RTO (Recovery Time Objective) untuk sistem pembayaran adalah 15 menit semenjak insiden terkonfirmasi.",
        metadata={"priority": "MEDIUM"}
    )
]

# 2. Wrapper Real Transformers Client
class LocalSentenceTransformerEmbedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    async def embed_query(self, text: str):
        return self.model.encode(text).tolist()

    def embed_corpus(self, docs):
        contents = [d.content for d in docs]
        vectors = self.model.encode(contents).tolist()
        for doc, vec in zip(docs, vectors):
            doc.dense_vector = vec

class LocalCrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    async def predict(self, pairs):
        # Jalankan prediksi secara sinkronus di background threadpool jika di lingkungan produksi
        scores = self.model.predict(pairs)
        return scores.tolist()

async def run_experiment():
    print("Menginisialisasi Embedder & Cross-Encoder...")
    embedder = LocalSentenceTransformerEmbedder()
    embedder.embed_corpus(BANKING_CORPUS)
    reranker = LocalCrossEncoderReranker()

    retriever = AdvancedRetriever(
        corpus=BANKING_CORPUS,
        embedder=embedder,
        cross_encoder=reranker,
        rrf_k=60
    )

    # Query menguji kata kunci spesifik dan konsep
    test_query = "Bagaimana prosedur penanganan kode error ERR-SYS-8012 database?"
    print(f"\nMenjalankan Retrieval untuk: '{test_query}'")

    results = await retriever.retrieve(query=test_query, top_candidates=3, final_top_k=2)

    print("\nHASIL EVALUASI RETRIEVAL TERPILIH:")
    for i, res in enumerate(results, 1):
        print(f"[{i}] ID: {res.chunk.id} | Score Reranker: {res.score:.4f}")
        print(f"    Konten: {res.chunk.content}")

if __name__ == "__main__":
    asyncio.run(run_experiment())
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan eksperimen melalui shell:
```bash
python lab_hybrid_rag.py
```

**Kriteria Keberhasilan Validasi**:
1. Output posisi pertama `[1]` **harus** mengembalikan `RUNBOOK-4041` dengan skor Cross-Encoder tertinggi, karena dokumen tersebut memuat kode leksikal tepat `ERR-SYS-8012` sekaligus relevansi semantik tentang *database*.
2. Dokumen `RUNBOOK-4042` harus tergeser ke bawah atau tereliminasi karena tidak sesuai dengan parameter kegagalan database, memvalidasi eliminasi *false-positive* leksikal.