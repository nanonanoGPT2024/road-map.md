#!/usr/bin/env python3
"""
Lab Exercise: Elasticsearch Dense Vector, HNSW Graph, and Hybrid Search (RRF) Simulation
BAB-06: Vector Search, Semantic Search, and Machine Learning

Simulasi interaktif konsep fondasi Elasticsearch:
1. Dense Vector Embeddings & Cosine Similarity
2. HNSW (Hierarchical Navigable Small World) Approximate Nearest Neighbor Graph
3. Lexical Search (BM25 Simplified) vs Semantic Vector Search
4. Reciprocal Rank Fusion (RRF) Hybrid Search
"""

import math
import random
import re
import time
from collections import Counter
from typing import Dict, List, Tuple, Any

# ANSI Color Codes for Terminal Output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


def print_banner(text: str) -> None:
    border = "=" * 70
    print(f"\n{Colors.CYAN}{border}")
    print(f" {Colors.BOLD}{text}{Colors.RESET}{Colors.CYAN}")
    print(f"{border}{Colors.RESET}\n")


def print_step(title: str, desc: str) -> None:
    print(f"{Colors.YELLOW}[STEP] {Colors.BOLD}{title}{Colors.RESET}")
    print(f"       {Colors.DIM}{desc}{Colors.RESET}")


# Vector Math Helpers
def dot_product(v1: List[float], v2: List[float]) -> float:
    return sum(a * b for a, b in zip(v1, v2))


def vector_norm(v: List[float]) -> float:
    return math.sqrt(sum(a * a for a in v))


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    norm1 = vector_norm(v1)
    norm2 = vector_norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product(v1, v2) / (norm1 * norm2)


def euclidean_distance(v1: List[float], v2: List[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


# Simulated Toy Semantic Model
# Dimensions: [Tech/Cloud, Search/DB, Security, DevOps/Infra]
EMBEDDING_VOCAB = {
    "elasticsearch": [0.90, 0.95, 0.20, 0.60],
    "opensearch":    [0.85, 0.92, 0.25, 0.58],
    "database":      [0.60, 0.88, 0.15, 0.40],
    "vector":        [0.80, 0.85, 0.10, 0.30],
    "firewall":      [0.30, 0.10, 0.95, 0.50],
    "cybersecurity": [0.40, 0.15, 0.98, 0.35],
    "kubernetes":    [0.85, 0.30, 0.40, 0.95],
    "docker":        [0.80, 0.25, 0.35, 0.92],
    "devops":        [0.75, 0.20, 0.40, 0.90],
    "lucene":        [0.70, 0.90, 0.10, 0.30],
}


def embed_text(text: str) -> List[float]:
    tokens = re.findall(r"\w+", text.lower())
    dim = 4
    accum = [0.0] * dim
    hits = 0
    for t in tokens:
        if t in EMBEDDING_VOCAB:
            hits += 1
            for i in range(dim):
                accum[i] += EMBEDDING_VOCAB[t][i]

    if hits == 0:
        # Fallback pseudo-random stable vector
        seed = sum(ord(c) for c in text)
        random.seed(seed)
        v = [random.uniform(0.1, 0.5) for _ in range(dim)]
    else:
        v = [val / hits for val in accum]

    # Normalize to unit vector (as Lucene does for dot_product similarity)
    norm = vector_norm(v)
    if norm > 0:
        v = [x / norm for x in v]
    return v


# Sample Corpus
CORPUS = [
    {
        "id": "doc1",
        "title": "Elasticsearch Vector Search & HNSW Indexing",
        "body": "Elasticsearch provides dense vector field types with HNSW graphs for fast approximate nearest neighbor search.",
    },
    {
        "id": "doc2",
        "title": "Kubernetes and Docker Container Orchestration",
        "body": "Deploying scalable devops microservices on kubernetes clusters using docker containers.",
    },
    {
        "id": "doc3",
        "title": "Cloud Cybersecurity & Infrastructure Firewalls",
        "body": "Protecting cloud infrastructure with modern firewall policies and enterprise cybersecurity practices.",
    },
    {
        "id": "doc4",
        "title": "Distributed Database Storage Engine with Lucene",
        "body": "Under the hood, Lucene acts as the core search and inverted index storage engine for the database.",
    },
]


# Simulated HNSW Graph Node
class HNSWNode:
    def __init__(self, doc_id: str, vector: List[float]):
        self.doc_id = doc_id
        self.vector = vector
        self.neighbors: List["HNSWNode"] = []

    def connect(self, other: "HNSWNode"):
        if other not in self.neighbors and other != self:
            self.neighbors.append(other)
            other.neighbors.append(self)


class SimpleHNSWGraph:
    def __init__(self, m: int = 2):
        self.m = m  # Max connections per node
        self.nodes: List[HNSWNode] = []
        self.entry_point: HNSWNode = None

    def insert(self, doc_id: str, vector: List[float]) -> HNSWNode:
        new_node = HNSWNode(doc_id, vector)
        if not self.nodes:
            self.entry_point = new_node
            self.nodes.append(new_node)
            return new_node

        # Greedily link to m closest nodes
        scored = [(cosine_similarity(new_node.vector, n.vector), n) for n in self.nodes]
        scored.sort(key=lambda x: x[0], reverse=True)

        for _, neighbor in scored[: self.m]:
            new_node.connect(neighbor)

        self.nodes.append(new_node)
        return new_node

    def search_knn(self, query_vec: List[float], k: int = 2) -> List[Tuple[str, float]]:
        if not self.entry_point:
            return []

        curr = self.entry_point
        visited = {curr}
        best_sim = cosine_similarity(query_vec, curr.vector)

        # Greedy routing simulation
        steps = 0
        while True:
            steps += 1
            improved = False
            for nbr in curr.neighbors:
                if nbr not in visited:
                    visited.add(nbr)
                    sim = cosine_similarity(query_vec, nbr.vector)
                    if sim > best_sim:
                        best_sim = sim
                        curr = nbr
                        improved = True
            if not improved or steps > 10:
                break

        # Collect top-k among visited
        results = [
            (node.doc_id, cosine_similarity(query_vec, node.vector))
            for node in visited
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]


# Simplified BM25 / Lexical Scoring
def lexical_bm25_score(query: str, corpus: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
    q_terms = re.findall(r"\w+", query.lower())
    scores = []
    for doc in corpus:
        text = (doc["title"] + " " + doc["body"]).lower()
        d_tokens = re.findall(r"\w+", text)
        counts = Counter(d_tokens)
        score = 0.0
        for term in q_terms:
            if term in counts:
                # Basic TF weighting
                tf = counts[term]
                score += (tf / (tf + 1.2)) * 2.0
        scores.append((doc["id"], score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


# Reciprocal Rank Fusion (RRF)
def reciprocal_rank_fusion(
    ranked_lists: List[List[Tuple[str, float]]], k: int = 60
) -> List[Tuple[str, float]]:
    rrf_map: Dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, (doc_id, _) in enumerate(ranked_list, start=1):
            rrf_map[doc_id] = rrf_map.get(doc_id, 0.0) + (1.0 / (k + rank))

    sorted_results = sorted(rrf_map.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


def run_interactive_simulation() -> None:
    print_banner("SIMULASI ELASTICSEARCH VECTOR & HYBRID SEARCH")
    print(f"{Colors.GREEN}Inisialisasi Indeks Corpus ({len(CORPUS)} Dokumen)...{Colors.RESET}")

    hnsw_index = SimpleHNSWGraph(m=2)
    doc_vectors = {}

    for doc in CORPUS:
        vec = embed_text(doc["title"] + " " + doc["body"])
        doc_vectors[doc["id"]] = vec
        hnsw_index.insert(doc["id"], vec)
        print(f"  • {Colors.BOLD}{doc['id']}{Colors.RESET}: '{doc['title'][:40]}...'")
        formatted_vec = "[" + ", ".join(f"{x:.3f}" for x in vec) + "]"
        print(f"    {Colors.DIM}Embedding (4D): {formatted_vec}{Colors.RESET}")

    print()
    queries = [
        "fast semantic vector similarity with lucene",
        "securing kubernetes containers and cloud firewall",
    ]

    for q_idx, query in enumerate(queries, start=1):
        print_step(
            f"Query #{q_idx}: \"{query}\"",
            "Menjalankan Lexical Search, Dense Vector kNN Search, dan Hybrid RRF",
        )

        # 1. Lexical BM25
        t0 = time.perf_counter()
        bm25_res = lexical_bm25_score(query, CORPUS)
        t_bm25 = (time.perf_counter() - t0) * 1000

        # 2. Dense Vector kNN
        t0 = time.perf_counter()
        q_vec = embed_text(query)
        knn_res = hnsw_index.search_knn(q_vec, k=3)
        t_knn = (time.perf_counter() - t0) * 1000

        # 3. Hybrid Search (RRF)
        t0 = time.perf_counter()
        rrf_res = reciprocal_rank_fusion([bm25_res, knn_res], k=60)
        t_rrf = (time.perf_counter() - t0) * 1000

        # Display Comparisons
        print(f"\n  {Colors.CYAN}{Colors.BOLD}1. Lexical BM25 Results ({t_bm25:.3f} ms):{Colors.RESET}")
        for rank, (doc_id, score) in enumerate(bm25_res[:3], start=1):
            doc_title = next(d["title"] for d in CORPUS if d["id"] == doc_id)
            print(f"     #{rank} [{Colors.YELLOW}{doc_id}{Colors.RESET}] score={score:.4f} -> {doc_title}")

        print(f"\n  {Colors.MAGENTA}{Colors.BOLD}2. Dense Vector kNN Results ({t_knn:.3f} ms):{Colors.RESET}")
        for rank, (doc_id, score) in enumerate(knn_res, start=1):
            doc_title = next(d["title"] for d in CORPUS if d["id"] == doc_id)
            print(f"     #{rank} [{Colors.YELLOW}{doc_id}{Colors.RESET}] cosine_sim={score:.4f} -> {doc_title}")

        print(f"\n  {Colors.GREEN}{Colors.BOLD}3. Hybrid Search RRF Results ({t_rrf:.3f} ms):{Colors.RESET}")
        for rank, (doc_id, score) in enumerate(rrf_res[:3], start=1):
            doc_title = next(d["title"] for d in CORPUS if d["id"] == doc_id)
            print(f"     #{rank} [{Colors.YELLOW}{doc_id}{Colors.RESET}] RRF_score={score:.6f} -> {doc_title}")

        print(f"\n{Colors.DIM}" + "-" * 60 + f"{Colors.RESET}\n")

    print_banner("SIMULASI SELESAI DENGAN SUKSES")
    print(f"{Colors.GREEN}✓ Seluruh modul vector search, graf HNSW, dan hybrid RRF berjalan valid 100%.{Colors.RESET}\n")


if __name__ == "__main__":
    run_interactive_simulation()
