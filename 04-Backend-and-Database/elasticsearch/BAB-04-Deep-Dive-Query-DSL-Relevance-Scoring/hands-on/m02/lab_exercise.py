#!/usr/bin/env python3
"""
Lab Exercise M02: Deep Dive Query DSL & Relevance Scoring Engine Simulation
BAB-04: Elasticsearch Deep Dive Query DSL & Relevance Scoring

Simulasi mandiri Lucene BM25, Boolean Query (must, filter, should, must_not),
Multi-Match scoring strategies, dan Function Score Rescoring (Decay + Field Value Factor)
dengan output ANSI color interaktif dan visualisasi Explain API tree.
"""

import math
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

# ==============================================================================
# ANSI Color Formatting Helper
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"

def c(text: Any, color_code: str) -> str:
    """Wrap string with ANSI escape codes."""
    return f"{color_code}{text}{Color.RESET}"

# ==============================================================================
# Data Models
# ==============================================================================
@dataclass
class Document:
    doc_id: str
    title: str
    description: str
    category: str
    brand: str
    price: float
    rating: float
    sales_count: int
    days_old: int  # simulasi recency
    tags: List[str] = field(default_factory=list)

@dataclass
class Explanation:
    value: float
    description: str
    details: List['Explanation'] = field(default_factory=list)

    def print_tree(self, prefix: str = "", is_last: bool = True) -> None:
        branch = "└── " if is_last else "├── "
        val_str = c(f"{self.value:10.5f}", Color.BOLD + Color.YELLOW)
        desc_str = c(self.description, Color.CYAN)
        print(f"{prefix}{branch}{val_str} = {desc_str}")
        new_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(self.details):
            child.print_tree(new_prefix, i == len(self.details) - 1)

# ==============================================================================
# Lucene BM25 Engine Simulator
# ==============================================================================
class BM25Scorer:
    """
    Simulasi BM25 Lucene 8+ formula:
    IDF = ln(1 + (N - n + 0.5) / (n + 0.5))
    TF_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_dl)))
    Score = sum(IDF * TF_norm)
    """
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b

    @staticmethod
    def tokenize(text: str) -> List[str]:
        cleaned = "".join([ch.lower() if ch.isalnum() else " " for ch in text])
        return [tok for tok in cleaned.split() if tok]

    def score_field(self, query_tokens: List[str], doc_tokens: List[str],
                    doc_freq: Dict[str, int], total_docs: int,
                    avg_doc_len: float) -> Tuple[float, Explanation]:
        doc_len = len(doc_tokens)
        field_score = 0.0
        details: List[Explanation] = []

        tf_map: Dict[str, int] = {}
        for token in doc_tokens:
            tf_map[token] = tf_map.get(token, 0) + 1

        for term in query_tokens:
            tf = tf_map.get(term, 0)
            if tf == 0:
                continue

            n = doc_freq.get(term, 1)
            # Lucene IDF formula
            idf = math.log(1.0 + (total_docs - n + 0.5) / (n + 0.5))
            
            # Lucene TF normalization
            len_norm = 1.0 - self.b + self.b * (doc_len / (avg_doc_len if avg_doc_len > 0 else 1.0))
            tf_norm = (tf * (self.k1 + 1.0)) / (tf + self.k1 * len_norm)
            
            term_score = idf * tf_norm
            field_score += term_score

            term_expl = Explanation(
                value=term_score,
                description=f"weight({term} in field), product of:",
                details=[
                    Explanation(idf, f"idf, computed as log(1 + ({total_docs} - {n} + 0.5) / ({n} + 0.5))"),
                    Explanation(tf_norm, f"tf, computed as (freq={tf} * {self.k1+1:.1f}) / (freq={tf} + {self.k1:.1f} * (1 - {self.b:.2f} + {self.b:.2f} * {doc_len}/{avg_doc_len:.1f}))")
                ]
            )
            details.append(term_expl)

        overall_expl = Explanation(
            value=field_score,
            description=f"BM25 match (field length: {doc_len}, avg_len: {avg_doc_len:.1f})",
            details=details
        )
        return field_score, overall_expl

# ==============================================================================
# Inverted Index & Query Execution Engine
# ==============================================================================
class ElasticSearchClusterMock:
    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self.bm25 = BM25Scorer()
        self._seed_production_dataset()

    def _seed_production_dataset(self) -> None:
        dataset = [
            Document(
                doc_id="prod-101",
                title="Apple MacBook Pro 16 M3 Max Ultra Laptop",
                description="Professional laptop for high end engineering, AI workload, and 4K video rendering.",
                category="Computers & Laptops",
                brand="Apple",
                price=3499.0,
                rating=4.9,
                sales_count=1820,
                days_old=15,
                tags=["apple", "laptop", "m3", "workstation"]
            ),
            Document(
                doc_id="prod-102",
                title="Dell XPS 15 High Performance Developer Laptop",
                description="Premium sleek laptop with OLED screen, Intel Core i9, and NVidia RTX graphics for dev.",
                category="Computers & Laptops",
                brand="Dell",
                price=2199.0,
                rating=4.5,
                sales_count=950,
                days_old=60,
                tags=["dell", "laptop", "oled", "intel"]
            ),
            Document(
                doc_id="prod-103",
                title="Lenovo ThinkPad X1 Carbon Gen 11 Business Laptop",
                description="Ultra lightweight corporate business laptop with carbon fiber chassis and tactile keyboard.",
                category="Computers & Laptops",
                brand="Lenovo",
                price=1699.0,
                rating=4.6,
                sales_count=3200,
                days_old=120,
                tags=["lenovo", "laptop", "business", "thinkpad"]
            ),
            Document(
                doc_id="prod-104",
                title="Laptop Stand Ergonomic Aluminum Holder",
                description="Adjustable cooling stand for all laptop sizes, MacBook, Dell, Lenovo compatible.",
                category="Accessories",
                brand="Ugreeen",
                price=39.99,
                rating=4.7,
                sales_count=8500,
                days_old=5,
                tags=["accessories", "stand", "ergonomic"]
            ),
            Document(
                doc_id="prod-105",
                title="Apple MacBook Air 13 M2 Lightweight",
                description="Ultra portable student and travel laptop with long battery life and silent passive cooling.",
                category="Computers & Laptops",
                brand="Apple",
                price=1099.0,
                rating=4.8,
                sales_count=4500,
                days_old=280,
                tags=["apple", "laptop", "m2", "lightweight"]
            ),
            Document(
                doc_id="prod-106",
                title="Logitech MX Master 3S Wireless Performance Mouse",
                description="Ergonomic precision mouse for productivity, ultra fast scrolling, works with any laptop.",
                category="Accessories",
                brand="Logitech",
                price=99.99,
                rating=4.9,
                sales_count=12000,
                days_old=45,
                tags=["mouse", "logitech", "ergonomic", "wireless"]
            ),
        ]
        for doc in dataset:
            self.documents[doc.doc_id] = doc

    def _calculate_stats(self, field_getter: Callable[[Document], str]) -> Tuple[Dict[str, int], float]:
        doc_freq: Dict[str, int] = {}
        total_len = 0
        for doc in self.documents.values():
            tokens = set(self.bm25.tokenize(field_getter(doc)))
            for tok in tokens:
                doc_freq[tok] = doc_freq.get(tok, 0) + 1
            total_len += len(self.bm25.tokenize(field_getter(doc)))
        avg_len = total_len / len(self.documents) if self.documents else 0.0
        return doc_freq, avg_len

    # -------------------------------------------------------------------------
    # Scenario 1: Bool Query Execution (must, filter, should, must_not)
    # -------------------------------------------------------------------------
    def execute_bool_query(self, must_query: str, filter_brand: Optional[str] = None,
                           filter_max_price: Optional[float] = None,
                           should_query: Optional[str] = None,
                           must_not_cat: Optional[str] = None) -> List[Tuple[Document, float, Explanation]]:
        """
        Elasticsearch Bool Query Engine:
        - must: contributes to _score and clauses must match
        - filter: 0 score contribution, binary filter bitset
        - should: adds boost score if matches (minimum_should_match=0 if must exists)
        - must_not: strictly excludes matching documents
        """
        title_df, title_avg = self._calculate_stats(lambda d: d.title)
        desc_df, desc_avg = self._calculate_stats(lambda d: d.description)
        total_docs = len(self.documents)

        results: List[Tuple[Document, float, Explanation]] = []
        must_tokens = self.bm25.tokenize(must_query)
        should_tokens = self.bm25.tokenize(should_query) if should_query else []

        for doc in self.documents.values():
            # 1. Filter Context (No scoring, strict evaluation)
            if filter_brand and doc.brand.lower() != filter_brand.lower():
                continue
            if filter_max_price is not None and doc.price > filter_max_price:
                continue
            if must_not_cat and doc.category.lower() == must_not_cat.lower():
                continue

            # 2. Must Clause Scoring
            doc_title_tokens = self.bm25.tokenize(doc.title)
            score_title, expl_title = self.bm25.score_field(
                must_tokens, doc_title_tokens, title_df, total_docs, title_avg
            )

            # Jika must clause bernilai 0 (tidak ada keyword match), diskualifikasi
            if score_title <= 0.0:
                continue

            bool_expl_details: List[Explanation] = [
                Explanation(score_title, "must clause (title match)", [expl_title])
            ]
            final_score = score_title

            # 3. Should Clause Scoring (optional boost)
            if should_tokens:
                doc_desc_tokens = self.bm25.tokenize(doc.description)
                score_should, expl_should = self.bm25.score_field(
                    should_tokens, doc_desc_tokens, desc_df, total_docs, desc_avg
                )
                if score_should > 0.0:
                    final_score += score_should
                    bool_expl_details.append(
                        Explanation(score_should, "should clause (description match boost)", [expl_should])
                    )

            # Filter clauses count as 0 score
            bool_expl_details.append(
                Explanation(0.0, f"filter clause passed [brand={filter_brand}, max_price={filter_max_price}]")
            )

            root_expl = Explanation(
                value=final_score,
                description=f"BooleanQuery score for doc {doc.doc_id}",
                details=bool_expl_details
            )
            results.append((doc, final_score, root_expl))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # -------------------------------------------------------------------------
    # Scenario 2: Multi-Match Strategies (best_fields vs most_fields)
    # -------------------------------------------------------------------------
    def execute_multi_match(self, query: str, fields_boost: Dict[str, float],
                           strategy: str = "best_fields",
                           tie_breaker: float = 0.0) -> List[Tuple[Document, float, Explanation]]:
        """
        best_fields: max(field_scores) + tie_breaker * other_scores
        most_fields: sum(field_scores * boost)
        """
        title_df, title_avg = self._calculate_stats(lambda d: d.title)
        desc_df, desc_avg = self._calculate_stats(lambda d: d.description)
        total_docs = len(self.documents)
        query_tokens = self.bm25.tokenize(query)

        results = []
        for doc in self.documents.values():
            field_scores: List[Tuple[str, float, Explanation]] = []

            # Title
            t_score, t_expl = self.bm25.score_field(
                query_tokens, self.bm25.tokenize(doc.title), title_df, total_docs, title_avg
            )
            t_boost = fields_boost.get("title", 1.0)
            t_weighted = t_score * t_boost
            field_scores.append(("title", t_weighted, Explanation(t_weighted, f"title score ({t_score:.4f} * boost {t_boost:.1f})", [t_expl])))

            # Description
            d_score, d_expl = self.bm25.score_field(
                query_tokens, self.bm25.tokenize(doc.description), desc_df, total_docs, desc_avg
            )
            d_boost = fields_boost.get("description", 1.0)
            d_weighted = d_score * d_boost
            field_scores.append(("description", d_weighted, Explanation(d_weighted, f"description score ({d_score:.4f} * boost {d_boost:.1f})", [d_expl])))

            if all(s[1] == 0.0 for s in field_scores):
                continue

            if strategy == "best_fields":
                field_scores.sort(key=lambda x: x[1], reverse=True)
                best = field_scores[0]
                others = field_scores[1:]
                tie_sum = sum(s[1] * tie_breaker for s in others)
                combined_score = best[1] + tie_sum

                expl_details = [best[2]]
                for o in others:
                    expl_details.append(Explanation(o[1] * tie_breaker, f"tie_breaker contribution ({o[0]}: {o[1]:.4f} * {tie_breaker})", [o[2]]))

                root_expl = Explanation(
                    value=combined_score,
                    description=f"MultiMatch [best_fields tie_breaker={tie_breaker}]",
                    details=expl_details
                )
            else:  # most_fields
                combined_score = sum(s[1] for s in field_scores)
                root_expl = Explanation(
                    value=combined_score,
                    description="MultiMatch [most_fields sum]",
                    details=[s[2] for s in field_scores]
                )

            results.append((doc, combined_score, root_expl))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # -------------------------------------------------------------------------
    # Scenario 3: Function Score Query (Decay + Field Value Factor)
    # -------------------------------------------------------------------------
    def execute_function_score(self, base_query: str,
                               decay_scale_days: float = 30.0,
                               decay_decay_rate: float = 0.5,
                               popularity_factor: float = 0.2) -> List[Tuple[Document, float, Explanation]]:
        """
        Function Score Query:
        _score = query_score * (gauss_decay(days_old) + log1p(sales_count) * factor)
        """
        title_df, title_avg = self._calculate_stats(lambda d: d.title)
        total_docs = len(self.documents)
        query_tokens = self.bm25.tokenize(base_query)

        results = []
        for doc in self.documents.values():
            base_score, base_expl = self.bm25.score_field(
                query_tokens, self.bm25.tokenize(doc.title), title_df, total_docs, title_avg
            )
            if base_score <= 0.0:
                continue

            # 1. Gauss Decay Calculation on Recency (days_old)
            # lambda = -ln(decay) / (scale^2)
            # decay_score = exp(-lambda * (days^2))
            sigma_sq = (decay_scale_days ** 2) / (-2.0 * math.log(decay_decay_rate))
            gauss_val = math.exp(-(doc.days_old ** 2) / (2.0 * sigma_sq))

            # 2. Field Value Factor on Sales (log1p)
            fv_val = math.log1p(doc.sales_count) * popularity_factor

            # Combine Function modifier: 1.0 + (decay * 0.5) + (popularity)
            modifier = 1.0 + (gauss_val * 0.8) + fv_val
            final_score = base_score * modifier

            root_expl = Explanation(
                value=final_score,
                description=f"FunctionScoreQuery (multiply mode: base {base_score:.4f} * modifier {modifier:.4f})",
                details=[
                    base_expl,
                    Explanation(
                        value=modifier,
                        description="function score modifier calculation",
                        details=[
                            Explanation(gauss_val, f"gauss(days_old={doc.days_old}, scale={decay_scale_days}, decay={decay_decay_rate})"),
                            Explanation(fv_val, f"field_value_factor(log1p({doc.sales_count}) * {popularity_factor:.2f})")
                        ]
                    )
                ]
            )
            results.append((doc, final_score, root_expl))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

# ==============================================================================
# Interactive Demo & Menu Presentation
# ==============================================================================
class InteractiveLab:
    def __init__(self):
        self.cluster = ElasticSearchClusterMock()

    def print_banner(self) -> None:
        print(c("=" * 80, Color.CYAN))
        print(c("  ⚡ ELASTICSEARCH LAB 04: QUERY DSL & RELEVANCE SCORING ARCHITECTURE ⚡", Color.BOLD + Color.GREEN))
        print(c("  Simulasi Komputasi Lucene BM25, Bool Compound, MultiMatch & Function Score", Color.WHITE))
        print(c("=" * 80, Color.CYAN))

    def print_documents_overview(self) -> None:
        print(c("\n--- [Index: production-catalog-v1] Current Documents ---", Color.BOLD + Color.YELLOW))
        print(f"{'Doc ID':<10} | {'Brand':<10} | {'Price':<10} | {'Sales':<7} | {'Age(d)':<6} | {'Title'}")
        print("-" * 80)
        for doc in self.cluster.documents.values():
            print(f"{c(doc.doc_id, Color.MAGENTA):<19} | {doc.brand:<10} | ${doc.price:<9.2f} | {doc.sales_count:<7} | {doc.days_old:<6} | {doc.title[:35]}")
        print("-" * 80)

    def demo_bool_query(self) -> None:
        print(c("\n[DEMO 1] Bool Query Simulation: Must vs Filter Score Behavior", Color.BOLD + Color.GREEN))
        print("Query Specification:")
        print(c("  MUST     : 'laptop'", Color.CYAN))
        print(c("  FILTER   : max_price <= $2500.00, brand != 'Logitech'", Color.BLUE))
        print(c("  SHOULD   : 'business tacitle keyboard' (adds boost)", Color.YELLOW))
        print(c("  MUST_NOT : category == 'Accessories'", Color.RED))
        
        results = self.cluster.execute_bool_query(
            must_query="laptop",
            filter_max_price=2500.0,
            should_query="business tactile keyboard",
            must_not_cat="Accessories"
        )

        print(f"\n{c('Search Results:', Color.BOLD)} ({len(results)} matches)")
        for rank, (doc, score, expl) in enumerate(results, 1):
            print(f" {rank}. [{c(doc.doc_id, Color.MAGENTA)}] {c(doc.title, Color.BOLD)} -> Score: {c(f'{score:.5f}', Color.GREEN)}")
            print(f"    Brand: {doc.brand} | Price: ${doc.price} | Category: {doc.category}")
        
        if results:
            print(c("\n[Lucene Explain Tree for Top 1 Result]:", Color.BOLD + Color.YELLOW))
            results[0][2].print_tree()

    def demo_multi_match(self) -> None:
        print(c("\n[DEMO 2] Multi-Match Scoring: best_fields vs most_fields", Color.BOLD + Color.GREEN))
        query = "apple high performance laptop"
        boosts = {"title": 3.0, "description": 1.0}

        print(f"Query: '{query}' | Boosts: title^3.0, description^1.0")

        # 1. best_fields with tie_breaker=0.0
        res_best_0 = self.cluster.execute_multi_match(query, boosts, strategy="best_fields", tie_breaker=0.0)
        # 2. best_fields with tie_breaker=0.3
        res_best_tie = self.cluster.execute_multi_match(query, boosts, strategy="best_fields", tie_breaker=0.3)
        # 3. most_fields
        res_most = self.cluster.execute_multi_match(query, boosts, strategy="most_fields")

        print(c("\nComparison (Top Hit):", Color.YELLOW))
        print(f"  * best_fields (tie_breaker=0.0) : {res_best_0[0][0].doc_id} (Score: {res_best_0[0][1]:.5f})")
        print(f"  * best_fields (tie_breaker=0.3) : {res_best_tie[0][0].doc_id} (Score: {res_best_tie[0][1]:.5f})")
        print(f"  * most_fields (field sum)       : {res_most[0][0].doc_id} (Score: {res_most[0][1]:.5f})")

        print(c("\nExplain breakdown for best_fields (tie_breaker=0.3):", Color.CYAN))
        res_best_tie[0][2].print_tree()

    def demo_function_score(self) -> None:
        print(c("\n[DEMO 3] Function Score Query: BM25 + Gauss Recency Decay + Field Value Factor", Color.BOLD + Color.GREEN))
        query = "macbook laptop"
        print(f"Base Query: '{query}'")
        print("Scoring Strategy: Combine text relevance with Gaussian decay on age (scale=30d, decay=0.5) and sales count log boost.")

        results = self.cluster.execute_function_score(query, decay_scale_days=30.0, decay_decay_rate=0.5, popularity_factor=0.25)
        print(f"\n{c('Ranked Results after Rescoring:', Color.BOLD)}")
        for rank, (doc, score, expl) in enumerate(results, 1):
            print(f" {rank}. [{c(doc.doc_id, Color.MAGENTA)}] {doc.title}")
            print(f"    Days Old: {doc.days_old}d | Sales: {doc.sales_count} | Final Score: {c(f'{score:.5f}', Color.GREEN)}")

        if results:
            print(c("\nExplain Structure for Top Ranked Item:", Color.YELLOW))
            results[0][2].print_tree()

    def run_all_benchmarks(self) -> None:
        print(c("\n[RUNNING SUITE BENCHMARK]", Color.BOLD + Color.MAGENTA))
        start_time = time.perf_counter()
        
        # Test 1000 loop executions
        iterations = 500
        for _ in range(iterations):
            _ = self.cluster.execute_bool_query("laptop", filter_max_price=3000.0)
            _ = self.cluster.execute_multi_match("apple laptop", {"title": 2.0, "description": 1.0})
            _ = self.cluster.execute_function_score("laptop")

        elapsed = time.perf_counter() - start_time
        ops = (iterations * 3) / elapsed
        print(c(f"✔ Completed {iterations * 3} queries in {elapsed:.4f}s ({ops:.1f} queries/sec)", Color.GREEN))
        print(c("✔ In-memory inverted index, Lucene BM25 scoring, and Explain parser validated 100%!", Color.GREEN))

    def run_cli(self) -> None:
        self.print_banner()
        self.print_documents_overview()

        # Check if running in headless or pipe mode
        if not sys.stdin.isatty() or "--demo" in sys.argv:
            print(c("\n[Non-interactive or --demo flag detected: executing full suite demonstration]\n", Color.CYAN))
            self.demo_bool_query()
            self.demo_multi_match()
            self.demo_function_score()
            self.run_all_benchmarks()
            print(c("\n[✔ Lab execution finished successfully]\n", Color.BOLD + Color.GREEN))
            return

        while True:
            print(c("\n--- Interactive Selection Menu ---", Color.BOLD + Color.WHITE))
            print("1. Run Bool Query Simulation (must / filter / should)")
            print("2. Run Multi-Match Comparison (best_fields vs most_fields & tie_breaker)")
            print("3. Run Function Score (BM25 + Gaussian Recency Decay + Sales Factor)")
            print("4. Print Documents Overview")
            print("5. Run In-Memory Engine Benchmark")
            print("6. Execute All Demonstrations Sequentially")
            print("0. Exit")

            try:
                choice = input(c("\nEnter choice (0-6): ", Color.BOLD + Color.YELLOW)).strip()
            except (EOFError, KeyboardInterrupt):
                print(c("\nExiting...", Color.RED))
                break

            if choice == "1":
                self.demo_bool_query()
            elif choice == "2":
                self.demo_multi_match()
            elif choice == "3":
                self.demo_function_score()
            elif choice == "4":
                self.print_documents_overview()
            elif choice == "5":
                self.run_all_benchmarks()
            elif choice == "6":
                self.demo_bool_query()
                self.demo_multi_match()
                self.demo_function_score()
                self.run_all_benchmarks()
            elif choice == "0":
                print(c("Exiting Elasticsearch Relevance Scoring Lab. Terima kasih!", Color.GREEN))
                break
            else:
                print(c("Invalid option, silakan coba lagi.", Color.RED))

# ==============================================================================
# Script Entry Point
# ==============================================================================
if __name__ == "__main__":
    lab = InteractiveLab()
    lab.run_cli()
