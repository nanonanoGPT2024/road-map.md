#!/usr/bin/env python3
"""
Lab Exercise: Production-Grade Elasticsearch Inverted Index & Text Analysis Simulation
BAB 02: Inverted Index, Text Analysis Pipeline, and Mapping Engine
Self-contained, runnable Python 3 script with interactive terminal visualization.
"""

import sys
import math
import re
from typing import List, Dict, Any, Set, Tuple, Optional
from collections import defaultdict


# ============================================================================
# ANSI Color Codes for Production Terminal UX
# ============================================================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Background colors
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[100m"


# ============================================================================
# Component 1: Text Analysis Pipeline (Char Filter -> Tokenizer -> Token Filters)
# ============================================================================
class Token:
    def __init__(self, term: str, position: int, start_offset: int, end_offset: int, token_type: str = "<ALPHANUM>"):
        self.term = term
        self.position = position
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.token_type = token_type

    def __repr__(self):
        return f"Token('{self.term}', pos={self.position}, span=[{self.start_offset}:{self.end_offset}])"


class TextAnalyzer:
    """
    Simulates Elasticsearch Lucene Analysis Pipeline:
    Input Text -> Char Filters -> Tokenizer -> Token Filters -> Output Stream
    """

    STOPWORDS = {
        "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with",
        "is", "are", "was", "were", "it", "this", "that", "by", "of", "from"
    }

    STEM_RULES = [
        (r"sses$", "ss"),
        (r"ies$", "i"),
        (r"ss$", "ss"),
        (r"s$", ""),
        (r"eed$", "ee"),
        (r"ing$", ""),
        (r"ed$", ""),
        (r"ational$", "ate"),
        (r"tional$", "tion"),
        (r"izer$", "ize"),
    ]

    def __init__(self, name: str = "custom_production_analyzer"):
        self.name = name

    def char_filter(self, text: str) -> str:
        """HTML strip & symbol normalization"""
        clean_text = re.sub(r"<[^>]+>", " ", text)
        clean_text = clean_text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        return clean_text

    def tokenize(self, text: str) -> List[Tuple[str, int, int]]:
        """Standard whitespace/punctuation tokenizer keeping offsets"""
        tokens = []
        pattern = re.compile(r"\b[\w\-']+\b")
        for match in pattern.finditer(text):
            tokens.append((match.group(0), match.start(), match.end()))
        return tokens

    def token_filters(self, raw_tokens: List[Tuple[str, int, int]]) -> List[Token]:
        """Lowercase, Stopwords filter, Porter-like stemming"""
        processed_tokens: List[Token] = []
        pos = 1

        for raw_term, start_pos, end_pos in raw_tokens:
            # 1. Lowercase filter
            lowered = raw_term.lower()

            # 2. Stopwords filter
            if lowered in self.STOPWORDS:
                continue

            # 3. Simple Stemmer filter
            stemmed = lowered
            for rule_pattern, replacement in self.STEM_RULES:
                if re.search(rule_pattern, stemmed):
                    stemmed = re.sub(rule_pattern, replacement, stemmed)
                    break

            if stemmed:
                processed_tokens.append(Token(
                    term=stemmed,
                    position=pos,
                    start_offset=start_pos,
                    end_offset=end_pos
                ))
                pos += 1

        return processed_tokens

    def analyze(self, text: str) -> List[Token]:
        filtered_text = self.char_filter(text)
        token_tuples = self.tokenize(filtered_text)
        return self.token_filters(token_tuples)


# ============================================================================
# Component 2: Mapping Engine (Field Types & Schema Enforcement)
# ============================================================================
class MappingEngine:
    """
    Simulates Elasticsearch Schema & Field Type Definition.
    Supports 'text', 'keyword', 'integer', and 'boolean'.
    """

    def __init__(self):
        self.properties: Dict[str, Dict[str, Any]] = {}
        self.dynamic: str = "strict"  # options: true, false, strict

    def define_field(self, field_name: str, field_type: str, analyzer: Optional[str] = None, doc_values: bool = True):
        self.properties[field_name] = {
            "type": field_type,
            "analyzer": analyzer if field_type == "text" else None,
            "doc_values": doc_values if field_type in ("keyword", "integer", "boolean") else False
        }

    def validate_and_parse(self, doc_id: int, source: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        validated = {}
        errors = []

        for field, value in source.items():
            if field not in self.properties:
                if self.dynamic == "strict":
                    errors.append(f"Field [{field}] is not defined in strict mapping schema!")
                    continue
                else:
                    # Dynamic mapping detection
                    detected_type = "text" if isinstance(value, str) else "integer" if isinstance(value, int) else "keyword"
                    self.properties[field] = {"type": detected_type, "doc_values": True}

            field_type = self.properties[field]["type"]
            try:
                if field_type == "text":
                    validated[field] = str(value)
                elif field_type == "keyword":
                    validated[field] = str(value)
                elif field_type == "integer":
                    validated[field] = int(value)
                elif field_type == "boolean":
                    validated[field] = bool(value)
                else:
                    validated[field] = value
            except (ValueError, TypeError):
                errors.append(f"Doc {doc_id}: Invalid value '{value}' for field '{field}' of type '{field_type}'")

        return validated, errors


# ============================================================================
# Component 3: Lucene Inverted Index & Columnar Doc Values Engine
# ============================================================================
class Posting:
    def __init__(self, doc_id: int):
        self.doc_id = doc_id
        self.term_freq: int = 0
        self.positions: List[int] = []
        self.offsets: List[Tuple[int, int]] = []

    def add_occurrence(self, position: int, start: int, end: int):
        self.term_freq += 1
        self.positions.append(position)
        self.offsets.append((start, end))

    def __repr__(self):
        return f"[DocID:{self.doc_id} | TF:{self.term_freq} | Pos:{self.positions}]"


class InvertedIndexShard:
    """
    Simulates Lucene Inverted Index segment storage:
    - Postings Lists with Term Frequency & Positions for full-text search.
    - Doc Values (columnar storage) for fast aggregations, sorting, and filtering.
    """

    def __init__(self, shard_id: int = 0):
        self.shard_id = shard_id
        self.analyzer = TextAnalyzer()
        self.mapping = MappingEngine()

        # Inverted index: field -> term -> List[Posting]
        self.inverted_index: Dict[str, Dict[str, Dict[int, Posting]]] = defaultdict(lambda: defaultdict(dict))

        # Doc Values (Columnar Store): field -> doc_id -> value
        self.doc_values: Dict[str, Dict[int, Any]] = defaultdict(dict)

        # Raw document source store (_source)
        self.document_store: Dict[int, Dict[str, Any]] = {}

        # Lucene document length tracking for BM25 calculation
        self.doc_lengths: Dict[str, Dict[int, int]] = defaultdict(dict)
        self.avg_doc_length: Dict[str, float] = defaultdict(float)

    def index_document(self, doc_id: int, source: Dict[str, Any]):
        validated_doc, errors = self.mapping.validate_and_parse(doc_id, source)
        if errors:
            raise ValueError(f"Mapping Schema Violation: {', '.join(errors)}")

        self.document_store[doc_id] = validated_doc

        for field, value in validated_doc.items():
            field_def = self.mapping.properties[field]
            field_type = field_def["type"]

            if field_type == "text":
                tokens = self.analyzer.analyze(str(value))
                self.doc_lengths[field][doc_id] = len(tokens)

                for token in tokens:
                    postings_dict = self.inverted_index[field][token.term]
                    if doc_id not in postings_dict:
                        postings_dict[doc_id] = Posting(doc_id)
                    postings_dict[doc_id].add_occurrence(token.position, token.start_offset, token.end_offset)

            elif field_type == "keyword":
                # Keyword: exact value without tokenization
                term = str(value)
                postings_dict = self.inverted_index[field][term]
                if doc_id not in postings_dict:
                    postings_dict[doc_id] = Posting(doc_id)
                postings_dict[doc_id].add_occurrence(1, 0, len(term))

            # Store in Doc Values if enabled (for sorting/aggregations)
            if field_def.get("doc_values", False):
                self.doc_values[field][doc_id] = value

        # Re-compute average document length for BM25
        for field, doc_lens in self.doc_lengths.items():
            if doc_lens:
                self.avg_doc_length[field] = sum(doc_lens.values()) / len(doc_lens)

    def search_bm25(self, field: str, query_text: str, k1: float = 1.2, b: float = 0.75) -> List[Dict[str, Any]]:
        """
        Calculates Okapi BM25 relevance score for search queries:
        Score(D, Q) = sum( IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * (|D| / avgdl))) )
        """
        query_tokens = self.analyzer.analyze(query_text)
        total_docs = len(self.document_store)
        if total_docs == 0:
            return []

        doc_scores: Dict[int, float] = defaultdict(float)
        term_debug: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

        for q_token in query_tokens:
            term = q_token.term
            if term not in self.inverted_index[field]:
                continue

            postings = self.inverted_index[field][term]
            doc_freq = len(postings)

            # Standard Lucene/BM25 IDF with smoothing
            idf = math.log(1.0 + (total_docs - doc_freq + 0.5) / (doc_freq + 0.5))
            if idf < 0:
                idf = 0.0

            avg_dl = self.avg_doc_length[field] or 1.0

            for doc_id, posting in postings.items():
                tf = posting.term_freq
                doc_len = self.doc_lengths[field].get(doc_id, 1)

                numerator = tf * (k1 + 1.0)
                denominator = tf + k1 * (1.0 - b + b * (doc_len / avg_dl))
                term_score = idf * (numerator / denominator)

                doc_scores[doc_id] += term_score
                term_debug[doc_id].append({
                    "term": term,
                    "tf": tf,
                    "idf": round(idf, 4),
                    "score": round(term_score, 4)
                })

        ranked_results = []
        for doc_id, total_score in sorted(doc_scores.items(), key=lambda item: item[1], reverse=True):
            ranked_results.append({
                "doc_id": doc_id,
                "score": round(total_score, 4),
                "source": self.document_store[doc_id],
                "explanation": term_debug[doc_id]
            })

        return ranked_results


# ============================================================================
# Interactive CLI & Visualization Engine
# ============================================================================
class ElasticsearchSimulatorApp:
    def __init__(self):
        self.shard = InvertedIndexShard(shard_id=1)
        self.setup_production_schema()
        self.seed_sample_cluster_data()

    def setup_production_schema(self):
        """Define explicit mapping schema"""
        self.shard.mapping.define_field("title", "text", analyzer="custom_production_analyzer")
        self.shard.mapping.define_field("content", "text", analyzer="custom_production_analyzer")
        self.shard.mapping.define_field("category", "keyword", doc_values=True)
        self.shard.mapping.define_field("likes", "integer", doc_values=True)
        self.shard.mapping.define_field("is_published", "boolean", doc_values=True)

    def seed_sample_cluster_data(self):
        sample_corpus = [
            {
                "id": 1,
                "title": "Elasticsearch Architecture and Sharding Strategy",
                "content": "<p>Understanding inverted indexes and Lucene segment merging helps in designing resilient scalable clusters.</p>",
                "category": "distributed-systems",
                "likes": 1280,
                "is_published": True
            },
            {
                "id": 2,
                "title": "Deep Dive into Text Analysis and Tokenization",
                "content": "Text analysis converts unstructured text strings into indexed tokens using character filters and token filters.",
                "category": "search-engine",
                "likes": 840,
                "is_published": True
            },
            {
                "id": 3,
                "title": "Optimizing Query Performance with Doc Values",
                "content": "Doc values provide columnar disk-backed data structures for aggregations and sorting while avoiding heap overhead.",
                "category": "performance",
                "likes": 2150,
                "is_published": True
            },
            {
                "id": 4,
                "title": "Handling Multilingual Search with N-grams and Stemmers",
                "content": "Stemming algorithms reduce inflected words to root form, allowing search engines to match queries accurately.",
                "category": "search-engine",
                "likes": 620,
                "is_published": False
            }
        ]

        for doc in sample_corpus:
            doc_id = doc.pop("id")
            self.shard.index_document(doc_id, doc)

    def print_banner(self):
        print(f"\n{Style.CYAN}{Style.BOLD}" + "=" * 80)
        print("  ELASTICSEARCH INTERNALS: INVERTED INDEX & TEXT ANALYSIS ENGINE")
        print("  BAB-02 Architecture Lab: Mapping, Tokens, Postings List & BM25 Scoring")
        print("=" * 80 + f"{Style.RESET}\n")

    def run_analyze_api_demo(self, raw_input_text: str):
        print(f"\n{Style.MAGENTA}{Style.BOLD}[_analyze API Simulation]{Style.RESET}")
        print(f"Input: {Style.WHITE}'{raw_input_text}'{Style.RESET}\n")

        analyzer = self.shard.analyzer
        char_filtered = analyzer.char_filter(raw_input_text)
        print(f"  {Style.BLUE}1. Char Filtered :{Style.RESET} '{char_filtered}'")

        raw_tokens = analyzer.tokenize(char_filtered)
        print(f"  {Style.BLUE}2. Tokenized     :{Style.RESET} {[t[0] for t in raw_tokens]}")

        final_tokens = analyzer.token_filters(raw_tokens)
        print(f"  {Style.GREEN}3. Final Pipeline Output ({len(final_tokens)} tokens):{Style.RESET}")

        print(f"\n  {'TERM':<16} | {'POS':<5} | {'START':<6} | {'END':<5} | {'TYPE'}")
        print("  " + "-" * 55)
        for token in final_tokens:
            print(f"  {Style.YELLOW}{token.term:<16}{Style.RESET} | {token.position:<5} | {token.start_offset:<6} | {token.end_offset:<5} | {token.token_type}")
        print()

    def view_inverted_index(self, field_name: str = "content"):
        print(f"\n{Style.CYAN}{Style.BOLD}[Lucene Inverted Index Segment: Field '{field_name}']{Style.RESET}")
        postings_map = self.shard.inverted_index[field_name]

        if not postings_map:
            print(f"{Style.RED}No index entries found for field '{field_name}'!{Style.RESET}")
            return

        sorted_terms = sorted(postings_map.keys())
        print(f"Total Unique Terms (Dictionary Size): {len(sorted_terms)}\n")
        print(f"  {'TERM':<18} | {'DF':<4} | {'POSTINGS LIST (DocID, TF, Positions)'}")
        print("  " + "-" * 75)

        for term in sorted_terms:
            doc_postings = postings_map[term]
            postings_str = " -> ".join([str(p) for p in doc_postings.values()])
            print(f"  {Style.GREEN}{term:<18}{Style.RESET} | {len(doc_postings):<4} | {postings_str}")
        print()

    def view_doc_values(self):
        print(f"\n{Style.YELLOW}{Style.BOLD}[Columnar Storage: Lucene Doc Values (_doc_values)]{Style.RESET}")
        print(f"Used for high-throughput Sorting, Fast Filtering, and Metric Aggregations\n")

        fields = ["category", "likes", "is_published"]
        doc_ids = sorted(self.shard.document_store.keys())

        header = f"  {'DocID':<6} | " + " | ".join([f"{f:<15}" for f in fields])
        print(header)
        print("  " + "-" * (len(header) + 4))

        for doc_id in doc_ids:
            row_items = []
            for f in fields:
                val = self.shard.doc_values[f].get(doc_id, "N/A")
                row_items.append(f"{str(val):<15}")
            print(f"  {Style.WHITE}{doc_id:<6}{Style.RESET} | " + " | ".join(row_items))
        print()

    def execute_search_query(self, query_phrase: str, search_field: str = "content"):
        print(f"\n{Style.CYAN}{Style.BOLD}[_search Query Execution]{Style.RESET}")
        print(f"Field: '{search_field}' | Query: '{query_phrase}'\n")

        results = self.shard.search_bm25(search_field, query_phrase)

        if not results:
            print(f"  {Style.RED}0 hits found. No documents match the query terms.{Style.RESET}\n")
            return

        print(f"  {Style.GREEN}Found {len(results)} hit(s) sorted by Okapi BM25 relevance score:{Style.RESET}\n")
        for rank, hit in enumerate(results, 1):
            src = hit["source"]
            print(f"  {Style.BOLD}Hit #{rank}:{Style.RESET} [Doc ID: {hit['doc_id']}] - Score: {Style.YELLOW}{hit['score']}{Style.RESET}")
            print(f"    {Style.WHITE}Title   :{Style.RESET} {src.get('title')}")
            print(f"    {Style.WHITE}Category:{Style.RESET} {src.get('category')} | Likes: {src.get('likes')}")
            print(f"    {Style.DIM}Relevance Breakdown:{Style.RESET}")
            for term_exp in hit["explanation"]:
                print(f"      - Term '{Style.CYAN}{term_exp['term']}{Style.RESET}' -> TF={term_exp['tf']}, IDF={term_exp['idf']}, TermScore={term_exp['score']}")
            print()

    def interactive_menu(self):
        while True:
            self.print_banner()
            print("Pilihan Menu Simulasi:")
            print(f"  {Style.GREEN}[1]{Style.RESET} Test _analyze API (Lihat Char Filter, Tokenizer & Stemming)")
            print(f"  {Style.GREEN}[2]{Style.RESET} Inspeksi Struktur Inverted Index (Postings List, TF, Positions)")
            print(f"  {Style.GREEN}[3]{Style.RESET} Inspeksi Doc Values (Columnar Store untuk Aggs/Sort)")
            print(f"  {Style.GREEN}[4]{Style.RESET} Eksekusi BM25 Search Query (Full-Text Relevance Ranking)")
            print(f"  {Style.GREEN}[5]{Style.RESET} Index Dokumen Baru (Uji Strict Mapping Schema)")
            print(f"  {Style.RED}[0]{Style.RESET} Keluar")

            choice = input(f"\n{Style.BOLD}Masukkan pilihan (0-5) [Enter = Run Auto Demo]: {Style.RESET}").strip()

            if choice == "0":
                print(f"\n{Style.GREEN}Simulasi selesai. Terima kasih.{Style.RESET}\n")
                break
            elif choice == "1":
                default_text = "<p>Elasticsearch cluster scaling and indexing optimized data.</p>"
                inp = input(f"Masukkan teks untuk dianalisis (Default: '{default_text}'): ").strip() or default_text
                self.run_analyze_api_demo(inp)
                input(f"{Style.DIM}Tekan Enter untuk lanjut...{Style.RESET}")
            elif choice == "2":
                f_name = input("Field yang ingin diinspeksi ('title' atau 'content', Default: 'content'): ").strip() or "content"
                self.view_inverted_index(f_name)
                input(f"{Style.DIM}Tekan Enter untuk lanjut...{Style.RESET}")
            elif choice == "3":
                self.view_doc_values()
                input(f"{Style.DIM}Tekan Enter untuk lanjut...{Style.RESET}")
            elif choice == "4":
                default_q = "indexing tokens and search"
                q = input(f"Masukkan query pencarian (Default: '{default_q}'): ").strip() or default_q
                self.execute_search_query(q, "content")
                input(f"{Style.DIM}Tekan Enter untuk lanjut...{Style.RESET}")
            elif choice == "5":
                print(f"\n{Style.CYAN}Membuat Dokumen Baru ke Shard:{Style.RESET}")
                try:
                    new_id = len(self.shard.document_store) + 1
                    t = input("Title: ") or "Realtime Lucene Analysis"
                    c = input("Content: ") or "High performance inverted index search engines."
                    cat = input("Category: ") or "search-engine"
                    likes = int(input("Likes (integer): ") or "950")
                    self.shard.index_document(new_id, {
                        "title": t,
                        "content": c,
                        "category": cat,
                        "likes": likes,
                        "is_published": True
                    })
                    print(f"{Style.GREEN}Dokumen {new_id} sukses diindeks ke Inverted Index & Doc Values!{Style.RESET}")
                except Exception as e:
                    print(f"{Style.RED}Indexing Gagal: {e}{Style.RESET}")
                input(f"{Style.DIM}Tekan Enter untuk lanjut...{Style.RESET}")
            else:
                # Default non-interactive auto demo walk-through
                print(f"\n{Style.YELLOW}Menjalankan Full Automated Tour...{Style.RESET}")
                self.run_analyze_api_demo("<p>Analyzing distributed elasticsearch clusters &amp; indexes!</p>")
                self.view_inverted_index("content")
                self.view_doc_values()
                self.execute_search_query("scalable cluster indexing", "content")
                print(f"{Style.GREEN}Automated Demo Selesai!{Style.RESET}\n")
                break


# ============================================================================
# Main Entry Point
# ============================================================================
if __name__ == "__main__":
    app = ElasticsearchSimulatorApp()
    # If standard input is not a terminal (e.g. CI/script pipe), run headless demo
    if not sys.stdin.isatty():
        app.run_analyze_api_demo("<p>Running in CI/automated environment with inverted indexes.</p>")
        app.view_inverted_index("content")
        app.view_doc_values()
        app.execute_search_query("inverted index scalable", "content")
    else:
        app.interactive_menu()
