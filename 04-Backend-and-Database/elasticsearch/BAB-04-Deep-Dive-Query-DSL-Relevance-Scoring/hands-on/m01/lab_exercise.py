#!/usr/bin/env python3
"""
Lab Exercise: Elasticsearch Query DSL & BM25 Relevance Scoring Engine
BAB-04: Deep Dive Query DSL & Relevance Scoring

Simulasi mandiri fondasi Elasticsearch tanpa dependensi eksternal:
1. Inverted Index & Document Storage
2. Exact Lucene BM25 Relevance Calculation with Explain API
3. Leaf Queries: Term vs Match Query
4. Compound Queries: Bool Query (must, filter, should, must_not)
5. Interactive Terminal UI dengan ANSI color highlights
"""

import math
import re
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

# ANSI Escape Colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BG_BLUE = "\033[44m\033[37m"
BG_DARK = "\033[48;5;236m"


def banner(text: str) -> None:
    line = "=" * 70
    print(f"\n{BOLD}{CYAN}{line}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{line}{RESET}")


def section(title: str) -> None:
    print(f"\n{BOLD}{YELLOW}--- [ {title} ] ---{RESET}")


class Document:
    def __init__(self, doc_id: str, fields: Dict[str, Any]):
        self.doc_id = doc_id
        self.fields = fields

    def get(self, field: str, default=None):
        return self.fields.get(field, default)


class LuceneBM25Simulator:
    """
    Simulasi BM25 standar Elasticsearch / Apache Lucene:
    - k1: controls non-linear term frequency saturation (default: 1.2)
    - b: controls document length normalization (default: 0.75)
    """

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: Dict[str, Document] = {}
        # field -> term -> set of doc_ids
        self.inverted_index: Dict[str, Dict[str, Set[str]]] = {}
        # field -> doc_id -> list of tokens
        self.doc_tokens: Dict[str, Dict[str, List[str]]] = {}
        # field -> average document length
        self.avg_dl: Dict[str, float] = {}

    @staticmethod
    def analyze(text: str) -> List[str]:
        """Simulasi Standard Analyzer: lowercasing + regex word tokenization."""
        if not isinstance(text, str):
            return []
        cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
        tokens = [t.strip("-") for t in cleaned.split() if t.strip("-")]
        return tokens

    def index_doc(self, doc_id: str, fields: Dict[str, Any]) -> None:
        doc = Document(doc_id, fields)
        self.documents[doc_id] = doc

        for field_name, value in fields.items():
            if field_name not in self.inverted_index:
                self.inverted_index[field_name] = {}
                self.doc_tokens[field_name] = {}

            if isinstance(value, str):
                tokens = self.analyze(value)
                self.doc_tokens[field_name][doc_id] = tokens
                for token in tokens:
                    if token not in self.inverted_index[field_name]:
                        self.inverted_index[field_name][token] = set()
                    self.inverted_index[field_name][token].add(doc_id)
            elif isinstance(value, list) and all(isinstance(x, str) for x in value):
                # Tag-like / keyword array
                self.doc_tokens[field_name][doc_id] = [str(x) for x in value]
                for item in value:
                    token = item.lower()
                    if token not in self.inverted_index[field_name]:
                        self.inverted_index[field_name][token] = set()
                    self.inverted_index[field_name][token].add(doc_id)

        self._refresh_stats()

    def _refresh_stats(self) -> None:
        """Kalkulasi ulang rerata panjang dokumen per field (avgdl)."""
        for field, doc_map in self.doc_tokens.items():
            if not doc_map:
                self.avg_dl[field] = 0.0
                continue
            total_len = sum(len(tokens) for tokens in doc_map.values())
            self.avg_dl[field] = total_len / len(doc_map)

    def calculate_idf(self, field: str, term: str) -> Tuple[float, str]:
        """
        Lucene BM25 IDF Formula:
        IDF(q_i) = ln(1 + (N - n + 0.5) / (n + 0.5))
        """
        n_docs = len(self.documents)
        doc_freq = len(self.inverted_index.get(field, {}).get(term, set()))
        if n_docs == 0:
            return 0.0, "N=0"

        numerator = n_docs - doc_freq + 0.5
        denominator = doc_freq + 0.5
        idf = math.log(1.0 + (numerator / denominator))
        explanation = (
            f"ln(1 + ({n_docs} - {doc_freq} + 0.5) / ({doc_freq} + 0.5)) = {idf:.4f}"
        )
        return max(idf, 0.0), explanation

    def score_term_in_doc(
        self, field: str, term: str, doc_id: str
    ) -> Tuple[float, List[str]]:
        """
        Kalkulasi kontribusi skor BM25 term tertentu pada sebuah dokumen.
        TF factor = (f * (k1 + 1)) / (f + k1 * (1 - b + b * (dl / avgdl)))
        """
        tokens = self.doc_tokens.get(field, {}).get(doc_id, [])
        tf = tokens.count(term)
        dl = len(tokens)
        avgdl = self.avg_dl.get(field, 1.0)
        expl_lines = []

        if tf == 0:
            return 0.0, [f"Term '{term}' not present in field '{field}'"]

        idf, idf_expl = self.calculate_idf(field, term)
        expl_lines.append(f"  * IDF for '{term}': {idf:.4f} via {idf_expl}")

        # Length normalization factor
        len_norm = 1.0 - self.b + self.b * (dl / avgdl) if avgdl > 0 else 1.0
        # Saturation factor
        tf_norm = (tf * (self.k1 + 1.0)) / (tf + self.k1 * len_norm)
        expl_lines.append(
            f"  * TF component: tf={tf}, dl={dl}, avgdl={avgdl:.2f} -> "
            f"tf_norm = ({tf} * {self.k1 + 1:.2f}) / ({tf} + {self.k1} * {len_norm:.4f}) = {tf_norm:.4f}"
        )

        term_score = idf * tf_norm
        expl_lines.append(
            f"  * Subtotal for '{term}': {idf:.4f} * {tf_norm:.4f} = {term_score:.4f}"
        )
        return term_score, expl_lines

    # --- Query DSL Implementations ---

    def query_term(
        self, field: str, exact_value: Any
    ) -> Tuple[List[str], Dict[str, float]]:
        """
        Leaf Query: Term Query
        Exact matching, biasanya digunakan di filter context (tanpa scoring).
        """
        target = str(exact_value).strip()
        matched = []
        for doc_id, doc in self.documents.items():
            val = doc.get(field)
            if isinstance(val, list):
                if target in [str(x) for x in val]:
                    matched.append(doc_id)
            elif str(val) == target:
                matched.append(doc_id)
        # Term query secara default menghasilkan konstan score 1.0
        scores = {doc_id: 1.0 for doc_id in matched}
        return matched, scores

    def query_match(
        self, field: str, query_str: str
    ) -> Tuple[List[str], Dict[str, float], Dict[str, List[str]]]:
        """
        Leaf Query: Match Query
        Dianalisis menggunakan analyzer, skor dihitung dengan BM25.
        """
        query_terms = self.analyze(query_str)
        matched_docs: Set[str] = set()
        scores: Dict[str, float] = {}
        explanations: Dict[str, List[str]] = {}

        for term in query_terms:
            matched_docs.update(self.inverted_index.get(field, {}).get(term, set()))

        for doc_id in matched_docs:
            total_score = 0.0
            doc_expl = [f"Doc [{doc_id}] Match Query on field '{field}': '{query_str}'"]
            for term in query_terms:
                s, expl = self.score_term_in_doc(field, term, doc_id)
                if s > 0:
                    total_score += s
                    doc_expl.extend(expl)
            scores[doc_id] = total_score
            explanations[doc_id] = doc_expl

        sorted_docs = sorted(matched_docs, key=lambda d: scores[d], reverse=True)
        return sorted_docs, scores, explanations

    def query_bool(
        self,
        must: Optional[List[Dict[str, Any]]] = None,
        filter_clause: Optional[List[Dict[str, Any]]] = None,
        should: Optional[List[Dict[str, Any]]] = None,
        must_not: Optional[List[Dict[str, Any]]] = None,
        minimum_should_match: int = 1,
    ) -> Tuple[List[str], Dict[str, float], Dict[str, List[str]]]:
        """
        Compound Query: Bool Query
        Mendukung 4 klausa inti: must, filter, should, must_not.
        """
        all_doc_ids = set(self.documents.keys())
        active_candidates = set(all_doc_ids)
        scores: Dict[str, float] = {doc_id: 0.0 for doc_id in all_doc_ids}
        explanations: Dict[str, List[str]] = {doc_id: [] for doc_id in all_doc_ids}

        # 1. Filter Clause (Binary Yes/No, skor 0)
        if filter_clause:
            for clause in filter_clause:
                matched_set = set()
                c_type, params = list(clause.items())[0]
                if c_type == "term":
                    field, val = list(params.items())[0]
                    matched_list, _ = self.query_term(field, val)
                    matched_set = set(matched_list)
                elif c_type == "range":
                    field, conditions = list(params.items())[0]
                    matched_set = {
                        d_id
                        for d_id, doc in self.documents.items()
                        if self._eval_range(doc.get(field), conditions)
                    }
                active_candidates.intersection_update(matched_set)
                for d_id in all_doc_ids:
                    status = "MATCH" if d_id in matched_set else "DISQUALIFIED"
                    explanations[d_id].append(
                        f"  [filter] {c_type} on {params} -> {status} (score contribution: 0.0)"
                    )

        # 2. Must_Not Clause (Disqualifier)
        if must_not:
            for clause in must_not:
                c_type, params = list(clause.items())[0]
                bad_set = set()
                if c_type == "term":
                    field, val = list(params.items())[0]
                    bad_list, _ = self.query_term(field, val)
                    bad_set = set(bad_list)
                active_candidates.difference_update(bad_set)
                for d_id in all_doc_ids:
                    if d_id in bad_set:
                        explanations[d_id].append(
                            f"  [must_not] Disqualified by clause {c_type}:{params}"
                        )

        # 3. Must Clause (Contributes to score AND must match)
        if must:
            for clause in must:
                c_type, params = list(clause.items())[0]
                if c_type == "match":
                    field, qstr = list(params.items())[0]
                    m_docs, m_scores, m_expl = self.query_match(field, qstr)
                    active_candidates.intersection_update(set(m_docs))
                    for d_id in m_docs:
                        scores[d_id] += m_scores[d_id]
                        explanations[d_id].append(
                            f"  [must] match('{field}': '{qstr}') -> score +{m_scores[d_id]:.4f}"
                        )
                elif c_type == "term":
                    field, val = list(params.items())[0]
                    m_docs, m_scores = self.query_term(field, val)
                    active_candidates.intersection_update(set(m_docs))
                    for d_id in m_docs:
                        scores[d_id] += m_scores[d_id]
                        explanations[d_id].append(
                            f"  [must] term('{field}': '{val}') -> score +1.0"
                        )

        # 4. Should Clause (Boosts score, optional unless no must clause)
        if should:
            should_matches_per_doc: Dict[str, int] = {
                d_id: 0 for d_id in active_candidates
            }
            for clause in should:
                c_type, params = list(clause.items())[0]
                if c_type == "match":
                    field, qstr = list(params.items())[0]
                    m_docs, m_scores, _ = self.query_match(field, qstr)
                    for d_id in set(m_docs).intersection(active_candidates):
                        scores[d_id] += m_scores[d_id]
                        should_matches_per_doc[d_id] += 1
                        explanations[d_id].append(
                            f"  [should BOOST] match('{field}': '{qstr}') -> score +{m_scores[d_id]:.4f}"
                        )
                elif c_type == "term":
                    field, val = list(params.items())[0]
                    m_docs, _ = self.query_term(field, val)
                    for d_id in set(m_docs).intersection(active_candidates):
                        scores[d_id] += 1.0
                        should_matches_per_doc[d_id] += 1
                        explanations[d_id].append(
                            f"  [should BOOST] term('{field}': '{val}') -> score +1.0"
                        )

            # Jika tidak ada 'must', 'should' bertindak sebagai filter minimal
            if not must and should:
                qualified = {
                    d_id
                    for d_id, count in should_matches_per_doc.items()
                    if count >= minimum_should_match
                }
                active_candidates.intersection_update(qualified)

        result_docs = [d for d in active_candidates if scores[d] > 0 or filter_clause]
        result_docs.sort(key=lambda d: scores[d], reverse=True)
        return result_docs, scores, explanations

    @staticmethod
    def _eval_range(val: Any, conditions: Dict[str, Any]) -> bool:
        if val is None or not isinstance(val, (int, float)):
            return False
        if "gte" in conditions and val < conditions["gte"]:
            return False
        if "gt" in conditions and val <= conditions["gt"]:
            return False
        if "lte" in conditions and val > conditions["lte"]:
            return False
        if "lt" in conditions and val >= conditions["lt"]:
            return False
        return True


def setup_sample_corpus(engine: LuceneBM25Simulator) -> None:
    """Mengisi korpus sampel bertema Sistem Basis Data & Pencarian."""
    dataset = [
        {
            "id": "doc_1",
            "title": "Introduction to Elasticsearch and Lucene Search Engine",
            "content": (
                "Elasticsearch is a distributed, JSON-based search engine built on Apache Lucene. "
                "It provides horizontal scalability, high reliability, and deep full-text search."
            ),
            "category": "database",
            "status": "published",
            "price": 0,
            "tags": ["search", "distributed", "nosql"],
        },
        {
            "id": "doc_2",
            "title": "Deep Dive into BM25 Relevance Scoring Algorithm",
            "content": (
                "Okapi BM25 is the default scoring algorithm in Elasticsearch. It calculates relevance "
                "based on term frequency saturation and document length normalization."
            ),
            "category": "search-science",
            "status": "published",
            "price": 25,
            "tags": ["scoring", "bm25", "relevance"],
        },
        {
            "id": "doc_3",
            "title": "PostgreSQL Full Text Search vs Elasticsearch",
            "content": (
                "While PostgreSQL offers tsvector search, Elasticsearch excels at scale with "
                "sharding, inverted index distribution, and BM25 relevance scoring algorithms."
            ),
            "category": "database",
            "status": "published",
            "price": 15,
            "tags": ["comparison", "sql", "search"],
        },
        {
            "id": "doc_4",
            "title": "Draft Notes on Internal Vector Search and Transformers",
            "content": (
                "Preliminary draft for semantic search using kNN dense vectors and Lucene HNSW index. "
                "Draft document under internal technical review."
            ),
            "category": "search-science",
            "status": "draft",
            "price": 99,
            "tags": ["ai", "vectors", "draft"],
        },
        {
            "id": "doc_5",
            "title": "Quick Guide to Boolean Queries in Query DSL",
            "content": (
                "Query DSL uses bool queries combining must, filter, should, and must_not clauses. "
                "Filters run in filter context without scoring overhead and are heavily cached."
            ),
            "category": "database",
            "status": "published",
            "price": 10,
            "tags": ["query-dsl", "elasticsearch", "bool"],
        },
    ]

    for item in dataset:
        engine.index_doc(item["id"], item)


def demo_match_vs_term(engine: LuceneBM25Simulator) -> None:
    section("DEMO 1: Leaf Query - Match Query vs Term Query")
    print(
        f"{DIM}Membandingkan query yang dianalisis (Match) vs nilai eksak tanpa analisis (Term).{RESET}"
    )

    # 1. Match Query (Case-insensitive & stemmed/tokenized)
    q_match = "ELASTICSEARCH SEARCH"
    print(f"\n{BOLD}[1] Match Query:{RESET} field='title', query='{q_match}'")
    m_docs, m_scores, m_expl = engine.query_match("title", q_match)

    print(f"{GREEN}Ditemukan {len(m_docs)} dokumen:{RESET}")
    for rank, doc_id in enumerate(m_docs, 1):
        doc = engine.documents[doc_id]
        print(
            f"  {rank}. {BOLD}{doc_id}{RESET} (Score: {MAGENTA}{m_scores[doc_id]:.4f}{RESET}) -> {doc.get('title')}"
        )

    # 2. Term Query (Exact Match)
    target_cat = "database"
    print(
        f"\n{BOLD}[2] Term Query:{RESET} field='category', value='{target_cat}' (Exact Filter)"
    )
    t_docs, _ = engine.query_term("category", target_cat)
    print(f"{GREEN}Ditemukan {len(t_docs)} dokumen berstatus kategori 'database':{RESET}")
    for doc_id in t_docs:
        doc = engine.documents[doc_id]
        print(f"  * {BOLD}{doc_id}{RESET} [{doc.get('category')}] - {doc.get('title')}")


def demo_bm25_explain(engine: LuceneBM25Simulator) -> None:
    section("DEMO 2: Lucene BM25 _explain API Simulation")
    print(
        f"{DIM}Pembongkaran matematis skor BM25: Term Frequency Saturation & Doc Length Normalization.{RESET}"
    )

    query_str = "relevance scoring"
    field = "content"
    print(f"Menganalisis query: {BOLD}'{query_str}'{RESET} pada field '{field}'")
    docs, scores, explanations = engine.query_match(field, query_str)

    for doc_id in docs[:2]:  # Tampilkan top 2
        print(f"\n{BG_DARK}{BOLD}{CYAN} Dokumen: {doc_id} {RESET}")
        print(f"Judul: {engine.documents[doc_id].get('title')}")
        print(f"Total BM25 Score: {BOLD}{MAGENTA}{scores[doc_id]:.4f}{RESET}")
        print(f"{DIM}Log Kalkulasi Rinci (Explain):{RESET}")
        for line in explanations[doc_id]:
            print(f"  {line}")


def demo_compound_bool_query(engine: LuceneBM25Simulator) -> None:
    section("DEMO 3: Compound Query - Complex Bool Query")
    print(f"{DIM}Kombinasi must, filter, should, dan must_not dalam satu query DSL.{RESET}")

    # Query DSL Definition
    # must: match 'search engine' on content
    # filter: category == 'database' AND price <= 20
    # should: boost if title matches 'Elasticsearch'
    # must_not: status == 'draft'
    print(f"{BOLD}Spesifikasi Bool Query:{RESET}")
    print(f"  {GREEN}[must]{RESET}     match(content: 'search engine')")
    print(f"  {CYAN}[filter]{RESET}   term(category: 'database') AND range(price <= 20)")
    print(f"  {YELLOW}[should]{RESET}   match(title: 'Elasticsearch') [BOOST]")
    print(f"  {RED}[must_not]{RESET} term(status: 'draft')")

    results, scores, explanations = engine.query_bool(
        must=[{"match": {"content": "search engine"}}],
        filter_clause=[
            {"term": {"category": "database"}},
            {"range": {"price": {"lte": 20}}},
        ],
        should=[{"match": {"title": "Elasticsearch"}}],
        must_not=[{"term": {"status": "draft"}}],
    )

    print(
        f"\n{BOLD}{GREEN}=== Hasil Evaluasi Bool Query ({len(results)} Lolos) ==={RESET}"
    )
    for rank, doc_id in enumerate(results, 1):
        doc = engine.documents[doc_id]
        print(
            f"\n{rank}. {BOLD}{doc_id}{RESET} | Score: {BOLD}{MAGENTA}{scores[doc_id]:.4f}{RESET}"
        )
        print(f"   Judul    : {doc.get('title')}")
        print(
            f"   Kategori : {doc.get('category')} | Status: {doc.get('status')} | Harga: ${doc.get('price')}"
        )
        print(f"   {DIM}Alasan Penilaian (Query Execution Trace):{RESET}")
        for expl in explanations[doc_id]:
            print(f"   {expl}")


def demo_parameter_tuning(engine: LuceneBM25Simulator) -> None:
    section("DEMO 4: Eksperimen Tuning Parameter BM25 (k1 & b)")
    print(
        f"{DIM}Mengamati dampak parameter k1 (kejenuhan TF) dan b (hukuman panjang dokumen).{RESET}"
    )

    test_doc_short = {
        "id": "short_doc",
        "title": "Elasticsearch Guide",
        "content": "Elasticsearch search engine. Elasticsearch fast.",
    }
    test_doc_long = {
        "id": "long_doc",
        "title": "Comprehensive Big Data Encyclopedia",
        "content": (
            "This extensive encyclopedia discusses distributed architectures, database engines, "
            "data warehousing, transactional ACID guarantees, network topologies, storage tiers, "
            "and also mentions Elasticsearch search engine once in passing."
        ),
    }

    # Model 1: Default b=0.75 (Hukuman dokumen panjang normal)
    eng_normal = LuceneBM25Simulator(k1=1.2, b=0.75)
    eng_normal.index_doc(test_doc_short["id"], test_doc_short)
    eng_normal.index_doc(test_doc_long["id"], test_doc_long)

    # Model 2: b=0.0 (Tanpa hukuman panjang dokumen sama sekali)
    eng_no_len_penalty = LuceneBM25Simulator(k1=1.2, b=0.0)
    eng_no_len_penalty.index_doc(test_doc_short["id"], test_doc_short)
    eng_no_len_penalty.index_doc(test_doc_long["id"], test_doc_long)

    query = "elasticsearch"
    _, scores_normal, _ = eng_normal.query_match("content", query)
    _, scores_no_pen, _ = eng_no_len_penalty.query_match("content", query)

    print(f"\nQuery: '{query}'")
    print(
        f"{'Model':<25} | {'Short Doc Score':<18} | {'Long Doc Score':<18} | {'Pemenang'}"
    )
    print("-" * 75)
    winner_normal = (
        "Short Doc"
        if scores_normal["short_doc"] > scores_normal["long_doc"]
        else "Long Doc"
    )
    print(
        f"{'Standard (b=0.75)':<25} | {scores_normal['short_doc']:<18.4f} | {scores_normal['long_doc']:<18.4f} | {GREEN}{winner_normal}{RESET}"
    )

    winner_no_pen = (
        "Short Doc"
        if scores_no_pen["short_doc"] > scores_no_pen["long_doc"]
        else "Long Doc"
    )
    print(
        f"{'No-Norm (b=0.0)':<25} | {scores_no_pen['short_doc']:<18.4f} | {scores_no_pen['long_doc']:<18.4f} | {YELLOW}{winner_no_pen}{RESET}"
    )
    print(
        f"\n{CYAN}Insight:{RESET} Parameter 'b' mencegah dokumen ensiklopedia panjang "
        f"mendominasi hasil hanya karena kebetulan memuat lebih banyak kata."
    )


def interactive_menu(engine: LuceneBM25Simulator) -> None:
    banner("SIMULATOR ELASTICSEARCH QUERY DSL & RELEVANCE SCORING")
    print(f"Korpus terindeks: {BOLD}{len(engine.documents)}{RESET} dokumen teknis.")

    while True:
        print(f"\n{BOLD}Menu Pilihan Eksperimen:{RESET}")
        print(f"  {CYAN}1.{RESET} Demo Match Query vs Term Query (Analyzed vs Exact)")
        print(f"  {CYAN}2.{RESET} Demo BM25 _explain API (Dekomposisi Skor Rinci)")
        print(f"  {CYAN}3.{RESET} Demo Compound Bool Query (must, filter, should, must_not)")
        print(f"  {CYAN}4.{RESET} Demo Tuning Parameter k1 & b (Length Normalization)")
        print(f"  {CYAN}5.{RESET} Uji Coba Custom Match Query (Cari Bebas)")
        print(f"  {CYAN}6.{RESET} Tampilkan Seluruh Indeks Dokumen")
        print(f"  {RED}0.{RESET} Keluar (Exit)")

        try:
            choice = input(f"\n{BOLD}Pilih opsi [0-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            demo_match_vs_term(engine)
        elif choice == "2":
            demo_bm25_explain(engine)
        elif choice == "3":
            demo_compound_bool_query(engine)
        elif choice == "4":
            demo_parameter_tuning(engine)
        elif choice == "5":
            try:
                term_input = input(
                    f"{BOLD}Masukkan kata kunci pencarian:{RESET} "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if term_input:
                docs, scores, _ = engine.query_match("content", term_input)
                print(f"\n{GREEN}Hasil pencarian untuk '{term_input}':{RESET}")
                if not docs:
                    print(f"  {RED}Tidak ada dokumen yang cocok.{RESET}")
                for r, d_id in enumerate(docs, 1):
                    doc = engine.documents[d_id]
                    print(
                        f"  {r}. [{d_id}] Score: {MAGENTA}{scores[d_id]:.4f}{RESET} - {doc.get('title')}"
                    )
        elif choice == "6":
            section("Katalog Dokumen Terindeks")
            for doc_id, doc in engine.documents.items():
                print(f"ID: {BOLD}{doc_id}{RESET}")
                print(f"  Title   : {doc.get('title')}")
                print(f"  Category: {doc.get('category')} | Status: {doc.get('status')}")
                print(f"  Snippet : {doc.get('content')[:90]}...")
                print("-" * 50)
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menjalankan simulasi Query DSL & BM25!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan ulangi.{RESET}")


def main() -> None:
    engine = LuceneBM25Simulator(k1=1.2, b=0.75)
    setup_sample_corpus(engine)

    # Jika dipanggil tanpa argumen TTY interaktif (misal saat automated test / pipe), jalankan semua demo otomatis
    if not sys.stdin.isatty() or "--run-all" in sys.argv:
        banner("AUTOMATED RUN: ELASTICSEARCH QUERY DSL & RELEVANCE SCORING")
        demo_match_vs_term(engine)
        demo_bm25_explain(engine)
        demo_compound_bool_query(engine)
        demo_parameter_tuning(engine)
        print(f"\n{GREEN}Seluruh demonstrasi berhasil dieksekusi tanpa error.{RESET}")
    else:
        interactive_menu(engine)


if __name__ == "__main__":
    main()
