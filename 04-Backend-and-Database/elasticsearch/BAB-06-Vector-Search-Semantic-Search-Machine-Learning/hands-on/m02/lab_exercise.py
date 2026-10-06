#!/usr/bin/env python3
"""
Lab Exercise: Production Elasticsearch Vector Search & Semantic Architecture Simulation
BAB-06: Vector Search, Semantic Search & Machine Learning Pipeline

Features:
- Dense Vector Indexing (HNSW simulation with cosine similarity)
- Lexical BM25 Search Engine
- Elastic 8.x+ Hybrid Search Engine (kNN + BM25)
- Reciprocal Rank Fusion (RRF: 1 / (k + rank)) & Linear Score Fusion
- Simulated ML Inference Pipeline & Cross-Encoder Semantic Reranker
- Interactive Terminal with ANSI color output & Explain Plans
"""

import sys
import math
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# --- ANSI Color Codes for Terminal UI ---
class Colors:
    HEADER    = '\033[95m'
    BLUE      = '\033[94m'
    CYAN      = '\033[96m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    RED       = '\033[91m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM       = '\033[2m'
    RESET     = '\033[0m'

def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Colors.RESET}"

# --- Domain Data Model & Document Definition ---
@dataclass
class Document:
    doc_id: str
    title: str
    body: str
    category: str
    tokens: List[str] = field(default_factory=list)
    dense_vector: List[float] = field(default_factory=list)

# --- Deterministic Semantic Embedding Generator ---
# Simulates a dense vector encoder (e.g., all-MiniLM-L6-v2, 8-dimensional projection for demonstration)
SEMANTIC_CLUSTERS = {
    "network":    [0.85, 0.72, 0.12, 0.05, 0.10, 0.02, 0.08, 0.15],
    "database":   [0.10, 0.15, 0.88, 0.79, 0.20, 0.10, 0.05, 0.02],
    "security":   [0.15, 0.20, 0.10, 0.05, 0.90, 0.82, 0.12, 0.08],
    "cloud":      [0.65, 0.55, 0.45, 0.35, 0.40, 0.30, 0.85, 0.78],
    "monitoring": [0.30, 0.40, 0.25, 0.30, 0.20, 0.15, 0.70, 0.88],
}

def tokenize(text: str) -> List[str]:
    import re
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    return [tok for tok in cleaned.split() if len(tok) > 2]

def generate_embedding(text: str) -> List[float]:
    tokens = tokenize(text)
    vector = [0.0] * 8
    weight_sum = 0.0

    for token in tokens:
        matched = False
        for category, proto_vec in SEMANTIC_CLUSTERS.items():
            if category in token or any(t in token for t in ["latency", "timeout", "packet", "dns", "ssl", "sql", "postgres", "auth", "firewall", "k8s", "cluster"]):
                if category == "network" and any(k in token for k in ["latency", "timeout", "packet", "dns", "connection"]):
                    w = 2.0
                elif category == "database" and any(k in token for k in ["sql", "postgres", "lock", "transaction", "query"]):
                    w = 2.0
                elif category == "security" and any(k in token for k in ["auth", "firewall", "token", "breach", "ssl", "cert"]):
                    w = 2.0
                elif category == "cloud" and any(k in token for k in ["k8s", "cluster", "node", "pod", "vpc"]):
                    w = 2.0
                elif category == "monitoring" and any(k in token for k in ["cpu", "memory", "alert", "metric", "threshold"]):
                    w = 2.0
                else:
                    w = 0.5
                for i in range(8):
                    vector[i] += proto_vec[i] * w
                weight_sum += w
                matched = True
                break
        if not matched:
            # Deterministic hash pseudo-random dimension activation
            h = abs(hash(token))
            idx = h % 8
            vector[idx] += 0.15
            weight_sum += 0.15

    if weight_sum > 0:
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            return [round(v / norm, 4) for v in vector]
    return [0.125] * 8

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot_product / (norm_a * norm_b)))

# --- BM25 Lexical Scoring Engine ---
class BM25Engine:
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: Dict[str, Document] = {}
        self.doc_lengths: Dict[str, int] = {}
        self.avg_doc_length: float = 0.0
        self.doc_freq: Dict[str, int] = {}
        self.total_docs: int = 0

    def index_document(self, doc: Document):
        self.docs[doc.doc_id] = doc
        tokens = doc.tokens
        self.doc_lengths[doc.doc_id] = len(tokens)
        self.total_docs += 1

        unique_tokens = set(tokens)
        for t in unique_tokens:
            self.doc_freq[t] = self.doc_freq.get(t, 0) + 1

        self.avg_doc_length = sum(self.doc_lengths.values()) / max(1, self.total_docs)

    def idf(self, term: str) -> float:
        df = self.doc_freq.get(term, 0)
        return math.log(1.0 + (self.total_docs - df + 0.5) / (df + 0.5))

    def score(self, query_tokens: List[str], doc_id: str) -> float:
        doc = self.docs.get(doc_id)
        if not doc:
            return 0.0
        doc_tokens = doc.tokens
        doc_len = self.doc_lengths[doc_id]
        total_score = 0.0

        for term in query_tokens:
            tf = doc_tokens.count(term)
            if tf == 0:
                continue
            term_idf = self.idf(term)
            numerator = tf * (self.k1 + 1.0)
            denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / max(1e-6, self.avg_doc_length)))
            total_score += term_idf * (numerator / denominator)

        return max(0.0, total_score)

# --- Elasticsearch Production Cluster Simulator ---
class ElasticsearchClusterSimulator:
    def __init__(self):
        self.bm25_engine = BM25Engine(k1=1.2, b=0.75)
        self.index_store: Dict[str, Document] = {}
        self.index_name = "incident_kb_vectors_v1"
        self._seed_kb_dataset()

    def _seed_kb_dataset(self):
        raw_documents = [
            ("DOC-101", "High TCP Connection Drops & Packet Retransmissions",
             "Network ingress load balancer encounters syn flooding and dropped packets under intense latency conditions.", "network"),
            ("DOC-102", "PostgreSQL Connection Pool Starvation & Lock Contention",
             "Database client requests timeout waiting for idle sessions. Long running transactions cause row-level locking.", "database"),
            ("DOC-103", "Kubernetes Pod Eviction due to OOMKilled Container",
             "Worker nodes terminate pods when memory consumption breaches hard limits during high batch traffic.", "cloud"),
            ("DOC-104", "Invalid OAuth2 Bearer Token & Expired SSL Handshake",
             "API gateway rejects requests with 401 Unauthorized due to clock skew or revoked security certificates.", "security"),
            ("DOC-105", "Prometheus High CPU Throttling and Scraping Timeouts",
             "Monitoring exporters cannot process scraping calls when agent process exceeds CFS quota limits.", "monitoring"),
            ("DOC-106", "Slow Database Queries during Replica Lag & WAL Spike",
             "Read operations against read replicas experience high latency while write-ahead logs sync across availability zones.", "database"),
            ("DOC-107", "DNS Resolution Latency inside Kubernetes CoreDNS Cluster",
             "Microservices suffer inter-service call delays due to unoptimized ndots configuration and dropped UDP packets.", "network"),
            ("DOC-108", "IAM Policy Misconfiguration Causing S3 Bucket Access Denied",
             "Applications fail to retrieve encrypted blobs when security roles lack appropriate KMS decrypt privileges.", "security")
        ]

        for doc_id, title, body, cat in raw_documents:
            combined_text = f"{title} {body}"
            tokens = tokenize(combined_text)
            vector = generate_embedding(combined_text)
            doc = Document(doc_id=doc_id, title=title, body=body, category=cat, tokens=tokens, dense_vector=vector)
            self.index_store[doc_id] = doc
            self.bm25_engine.index_document(doc)

    def print_index_mapping(self):
        mapping = {
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "standard"},
                    "body": {"type": "text"},
                    "category": {"type": "keyword"},
                    "incident_vector": {
                        "type": "dense_vector",
                        "dims": 8,
                        "index": True,
                        "similarity": "cosine",
                        "index_options": {
                            "type": "hnsw",
                            "m": 16,
                            "ef_construction": 100
                        }
                    }
                }
            }
        }
        print(colorize("\n[Elasticsearch Dynamic Mapping Definition (8.x+)]", Colors.CYAN + Colors.BOLD))
        print(colorize(json.dumps(mapping, indent=2), Colors.DIM))

    def search_lexical_bm25(self, query: str, top_k: int = 5) -> List[Tuple[Document, float]]:
        q_tokens = tokenize(query)
        scores = []
        for doc_id, doc in self.index_store.items():
            s = self.bm25_engine.score(q_tokens, doc_id)
            if s > 0.0:
                scores.append((doc, round(s, 4)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def search_dense_knn(self, query: str, top_k: int = 5) -> List[Tuple[Document, float]]:
        query_vector = generate_embedding(query)
        scores = []
        for doc in self.index_store.values():
            sim = cosine_similarity(query_vector, doc.dense_vector)
            scores.append((doc, round(sim, 4)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def search_hybrid_rrf(self, query: str, top_k: int = 5, rrf_k: int = 60) -> List[Dict]:
        """
        Elasticsearch 8.8+ Reciprocal Rank Fusion (RRF) Implementation
        Score = 1.0 / (rrf_k + rank_bm25) + 1.0 / (rrf_k + rank_knn)
        """
        lexical_results = self.search_lexical_bm25(query, top_k=len(self.index_store))
        knn_results = self.search_dense_knn(query, top_k=len(self.index_store))

        ranks_lexical = {doc.doc_id: idx + 1 for idx, (doc, _) in enumerate(lexical_results)}
        ranks_knn = {doc.doc_id: idx + 1 for idx, (doc, _) in enumerate(knn_results)}

        all_doc_ids = set(ranks_lexical.keys()).union(set(ranks_knn.keys()))
        fusion_scores = []

        for doc_id in all_doc_ids:
            doc = self.index_store[doc_id]
            r_lex = ranks_lexical.get(doc_id, None)
            r_knn = ranks_knn.get(doc_id, None)

            score_lex = (1.0 / (rrf_k + r_lex)) if r_lex else 0.0
            score_knn = (1.0 / (rrf_k + r_knn)) if r_knn else 0.0
            combined_score = score_lex + score_knn

            fusion_scores.append({
                "doc": doc,
                "rrf_score": round(combined_score, 6),
                "bm25_rank": r_lex,
                "knn_rank": r_knn,
                "component_lex": round(score_lex, 6),
                "component_knn": round(score_knn, 6)
            })

        fusion_scores.sort(key=lambda x: x["rrf_score"], reverse=True)
        return fusion_scores[:top_k]

    def ml_cross_encoder_rerank(self, query: str, candidate_docs: List[Dict]) -> List[Dict]:
        """
        Simulates an ML Cross-Encoder / Rerank Model running in Elasticsearch ML node.
        Computes joint attention / semantic cross-scoring between query and candidate text.
        """
        q_tokens = set(tokenize(query))
        reranked = []

        for candidate in candidate_docs:
            doc: Document = candidate["doc"]
            doc_tokens = set(doc.tokens)

            # Cross-encoder joint intersection & semantic affinity calculation
            overlap_ratio = len(q_tokens.intersection(doc_tokens)) / max(1, len(q_tokens))
            vector_sim = cosine_similarity(generate_embedding(query), doc.dense_vector)

            # Non-linear boost simulating multi-layer transformer score
            rerank_score = round((0.45 * overlap_ratio) + (0.55 * (vector_sim ** 1.5)), 4)

            entry = dict(candidate)
            entry["ml_rerank_score"] = rerank_score
            reranked.append(entry)

        reranked.sort(key=lambda x: x["ml_rerank_score"], reverse=True)
        return reranked

# --- Pretty Formatted CLI Display Functions ---
def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}================================================================================
   ELASTICSEARCH ADVANCED VECTOR & SEMANTIC SEARCH ENGINE (LAB SIMULATION)
   BAB-06: Vector Search, Semantic Search & Machine Learning Pipeline
================================================================================{Colors.RESET}
    """
    print(banner)

def render_comparison_table(query: str, cluster: ElasticsearchClusterSimulator):
    print(f"\n{Colors.BOLD}{Colors.YELLOW}>>> ANALYZING QUERY:{Colors.RESET} \"{colorize(query, Colors.BOLD + Colors.GREEN)}\"")
    t0 = time.perf_counter()

    # 1. Lexical BM25
    bm25_res = cluster.search_lexical_bm25(query, top_k=3)
    # 2. Dense Vector kNN
    knn_res = cluster.search_dense_knn(query, top_k=3)
    # 3. Hybrid RRF
    rrf_res = cluster.search_hybrid_rrf(query, top_k=3, rrf_k=60)
    # 4. ML Rerank
    ml_res = cluster.ml_cross_encoder_rerank(query, rrf_res)

    latency_ms = (time.perf_counter() - t0) * 1000

    print(f"\n{Colors.BOLD}{Colors.UNDERLINE}1. Lexical BM25 Search (Exact Keyword Match){Colors.RESET}")
    if not bm25_res:
        print(f"  {colorize('[EMPTY]', Colors.RED)} No lexical match (Term Mismatch Problem)")
    for rank, (doc, score) in enumerate(bm25_res, 1):
        print(f"  [{rank}] {colorize(doc.doc_id, Colors.CYAN)} (Score: {score:6.3f}) - {doc.title}")

    print(f"\n{Colors.BOLD}{Colors.UNDERLINE}2. Dense Vector kNN Search (Cosine Similarity HNSW){Colors.RESET}")
    for rank, (doc, score) in enumerate(knn_res, 1):
        print(f"  [{rank}] {colorize(doc.doc_id, Colors.BLUE)} (Cosine: {score:5.4f}) - {doc.title}")

    print(f"\n{Colors.BOLD}{Colors.UNDERLINE}3. Hybrid Search (RRF: Lexical + Dense Fusion){Colors.RESET}")
    for rank, item in enumerate(rrf_res, 1):
        d = item["doc"]
        score = item["rrf_score"]
        lex_r = item["bm25_rank"] if item["bm25_rank"] else "-"
        knn_r = item["knn_rank"] if item["knn_rank"] else "-"
        print(f"  [{rank}] {colorize(d.doc_id, Colors.GREEN)} (RRF: {score:7.5f} | BM25 Rank: {lex_r}, kNN Rank: {knn_r}) - {d.title}")

    print(f"\n{Colors.BOLD}{Colors.UNDERLINE}4. Machine Learning Inference Pipeline (Cross-Encoder Rerank){Colors.RESET}")
    for rank, item in enumerate(ml_res, 1):
        d = item["doc"]
        rerank_score = item["ml_rerank_score"]
        print(f"  [{rank}] {colorize(d.doc_id, Colors.HEADER)} (ML Score: {rerank_score:5.4f}) - {d.title}")

    print(colorize(f"\n[Execution Profiling] Query parsed, vectorized & fused across 4 pipelines in {latency_ms:.2f} ms", Colors.DIM))

def explain_rrf_mathematics():
    print(colorize("\n--- [Deep Dive: Reciprocal Rank Fusion Architecture in ES 8.x] ---", Colors.YELLOW + Colors.BOLD))
    print(f"""
In modern Elasticsearch, RRF solves the scale discrepancy between BM25 unbounded scores
and Cosine similarity [0..1] dense vector scores without manual normalization hyper-parameters.

{Colors.BOLD}Formula:{Colors.RESET}
  Score(d) = ∑ (weight_i / (k + rank_i(d)))
  where default 'k' (rank_constant) = 60

{Colors.BOLD}Example Calculation for Document DOC-102:{Colors.RESET}
  - BM25 Rank = 2  => 1.0 / (60 + 2) = 1.0 / 62 = 0.016129
  - kNN Rank  = 1  => 1.0 / (60 + 1) = 1.0 / 61 = 0.016393
  - Total RRF Score = 0.016129 + 0.016393 = {Colors.GREEN}0.032522{Colors.RESET}
    """)

# --- Interactive Main Loop ---
def main():
    print_banner()
    cluster = ElasticsearchClusterSimulator()

    sample_queries = [
        "high database latency and blocked sessions",
        "dropped packets and network delays",
        "container stopped unexpectedly memory exhausted",
        "security token denied access expired",
        "service unreachable due to DNS failures"
    ]

    while True:
        print(f"\n{Colors.BOLD}Available Actions:{Colors.RESET}")
        print("  [1] Run Sample Incident Queries Evaluation")
        print("  [2] Enter Custom Query (Interactive Semantic Testing)")
        print("  [3] Show Production Index Mapping (JSON)")
        print("  [4] Deep Dive: RRF Mathematical Explain Plan")
        print("  [0] Exit")

        choice = input(colorize("\nSelect an option [0-4]: ", Colors.CYAN)).strip()

        if choice == "1":
            for q in sample_queries:
                render_comparison_table(q, cluster)
                print(colorize("-" * 75, Colors.DIM))
        elif choice == "2":
            user_q = input(colorize("\nEnter your custom search query: ", Colors.YELLOW)).strip()
            if user_q:
                render_comparison_table(user_q, cluster)
        elif choice == "3":
            cluster.print_index_mapping()
        elif choice == "4":
            explain_rrf_mathematics()
        elif choice == "0":
            print(colorize("\nExiting Elasticsearch Vector Search Lab. Selesai!\n", Colors.GREEN))
            break
        else:
            print(colorize("Invalid option. Please choose between 0 and 4.", Colors.RED))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(colorize("\nExecution interrupted by user.", Colors.YELLOW))
        sys.exit(0)
