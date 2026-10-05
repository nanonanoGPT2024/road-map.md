#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Mesin Elasticsearch
BAB 02: Inverted Index, Text Analysis Pipeline & Mapping Engine
"""

import sys
import re
import math
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Optional

# ANSI Color Codes
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


class ANSIHelper:
    @staticmethod
    def header(title: str) -> str:
        border = "=" * 65
        return f"\n{CYAN}{BOLD}{border}\n  {title}\n{border}{RESET}"

    @staticmethod
    def subheader(title: str) -> str:
        return f"\n{MAGENTA}{BOLD}>>> {title}{RESET}"

    @staticmethod
    def badge(label: str, color: str = BLUE) -> str:
        return f"{color}{BOLD}[{label}]{RESET}"


class CharacterFilter:
    """Simulasi Char Filters: membersihkan raw text sebelum tokenisasi."""
    @staticmethod
    def html_strip(text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text)

    @staticmethod
    def mapping_filter(text: str, replacements: Dict[str, str]) -> str:
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text


class Tokenizer:
    """Simulasi Tokenizer: memecah string menjadi aliran token."""
    @staticmethod
    def standard(text: str) -> List[Tuple[str, int, int]]:
        """Mengembalikan list tuple: (token_str, start_offset, end_offset)."""
        tokens = []
        for match in re.finditer(r"\b[\w\d]+\b", text):
            tokens.append((match.group(), match.start(), match.end()))
        return tokens

    @staticmethod
    def whitespace(text: str) -> List[Tuple[str, int, int]]:
        tokens = []
        for match in re.finditer(r"\S+", text):
            tokens.append((match.group(), match.start(), match.end()))
        return tokens


class TokenFilter:
    """Simulasi Token Filters: memodifikasi atau menyaring aliran token."""
    STOPWORDS = {
        "and", "the", "is", "in", "at", "of", "a", "an", "to", "for", "with",
        "dan", "di", "ke", "yang", "dari", "untuk", "pada", "adalah"
    }

    @staticmethod
    def lowercase(tokens: List[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
        return [(t[0].lower(), t[1], t[2]) for t in tokens]

    @classmethod
    def remove_stopwords(cls, tokens: List[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
        return [t for t in tokens if t[0].lower() not in cls.STOPWORDS]

    @staticmethod
    def simple_stemmer(tokens: List[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
        """Simulasi Porter Stemmer sederhana untuk suffix umum."""
        stemmed = []
        for word, start, end in tokens:
            w = word
            if w.endswith("ing") and len(w) > 5:
                w = w[:-3]
            elif w.endswith("es") and len(w) > 4:
                w = w[:-2]
            elif w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
                w = w[:-1]
            elif w.endswith("kan") and len(w) > 5:
                w = w[:-3]
            elif w.endswith("an") and len(w) > 4:
                w = w[:-2]
            stemmed.append((w, start, end))
        return stemmed


class Analyzer:
    """Menghubungkan Char Filter -> Tokenizer -> Token Filters."""
    def __init__(self, name: str = "standard_custom"):
        self.name = name

    def analyze(self, text: str) -> List[Dict[str, Any]]:
        # 1. Char Filter
        cleaned = CharacterFilter.html_strip(text)
        # 2. Tokenizer
        raw_tokens = Tokenizer.standard(cleaned)
        # 3. Token Filters
        lowercased = TokenFilter.lowercase(raw_tokens)
        no_stops = TokenFilter.remove_stopwords(lowercased)
        stemmed = TokenFilter.simple_stemmer(no_stops)

        analyzed_tokens = []
        for pos, (term, start, end) in enumerate(stemmed):
            analyzed_tokens.append({
                "token": term,
                "position": pos,
                "start_offset": start,
                "end_offset": end
            })
        return analyzed_tokens


class Posting:
    """Informasi Term dalam Dokumen (Term Frequency & Posisi)."""
    def __init__(self, doc_id: int):
        self.doc_id = doc_id
        self.term_freq = 0
        self.positions: List[int] = []

    def add_occurrence(self, position: int):
        self.term_freq += 1
        self.positions.append(position)


class MockMappingEngine:
    """Mendefinisikan schema type: text vs keyword."""
    def __init__(self, mapping_def: Dict[str, str]):
        self.mapping = mapping_def

    def get_field_type(self, field: str) -> str:
        return self.mapping.get(field, "keyword")


class MockInvertedIndex:
    """Simulasi Indexing & Search Engine berbasis Inverted Index & BM25."""
    def __init__(self, mapping_engine: MockMappingEngine):
        self.mapping_engine = mapping_engine
        self.analyzer = Analyzer()
        self.documents: Dict[int, Dict[str, Any]] = {}
        # index: field -> term -> List[Posting]
        self.index: Dict[str, Dict[str, List[Posting]]] = defaultdict(lambda: defaultdict(list))
        self.doc_lengths: Dict[str, Dict[int, int]] = defaultdict(dict)
        self.avg_doc_len: Dict[str, float] = defaultdict(float)

    def index_document(self, doc_id: int, doc_source: Dict[str, Any]):
        self.documents[doc_id] = doc_source
        for field, value in doc_source.items():
            field_type = self.mapping_engine.get_field_type(field)

            if field_type == "text":
                tokens = self.analyzer.analyze(str(value))
                self.doc_lengths[field][doc_id] = len(tokens)
                posting_map: Dict[str, Posting] = {}

                for token_meta in tokens:
                    term = token_meta["token"]
                    pos = token_meta["position"]
                    if term not in posting_map:
                        posting_map[term] = Posting(doc_id)
                    posting_map[term].add_occurrence(pos)

                for term, posting in posting_map.items():
                    self.index[field][term].append(posting)

            elif field_type == "keyword":
                # Keyword: EXACT string tanpa analisis teks
                exact_val = str(value)
                self.doc_lengths[field][doc_id] = 1
                p = Posting(doc_id)
                p.add_occurrence(0)
                self.index[field][exact_val].append(p)

        self._recompute_avg_doc_lengths()

    def _recompute_avg_doc_lengths(self):
        for field, lengths in self.doc_lengths.items():
            if lengths:
                self.avg_doc_len[field] = sum(lengths.values()) / len(lengths)

    def calculate_bm25(self, field: str, term: str, posting: Posting, k1: float = 1.2, b: float = 0.75) -> float:
        total_docs = len(self.documents)
        doc_freq = len(self.index[field].get(term, []))
        if doc_freq == 0:
            return 0.0

        # IDF calculation standard Lucene BM25
        idf = math.log(1.0 + (total_docs - doc_freq + 0.5) / (doc_freq + 0.5))
        doc_len = self.doc_lengths[field].get(posting.doc_id, 1)
        avg_dl = self.avg_doc_len[field] or 1.0

        # TF Normalization
        tf = posting.term_freq
        tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_dl)))
        return round(idf * tf_norm, 4)

    def search_match(self, field: str, query_str: str) -> List[Tuple[int, float, Dict[str, Any]]]:
        field_type = self.mapping_engine.get_field_type(field)
        scores: Dict[int, float] = defaultdict(float)

        if field_type == "keyword":
            # Exact match query
            postings = self.index[field].get(query_str, [])
            for p in postings:
                scores[p.doc_id] = 1.0
        else:
            # Full-text analyzed query
            query_tokens = self.analyzer.analyze(query_str)
            for q_tok in query_tokens:
                term = q_tok["token"]
                postings = self.index[field].get(term, [])
                for p in postings:
                    score = self.calculate_bm25(field, term, p)
                    scores[p.doc_id] += score

        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [(doc_id, score, self.documents[doc_id]) for doc_id, score in sorted_results]

    def print_inverted_index(self):
        print(ANSIHelper.subheader("Visualisasi Internal Inverted Index (Lucene Segment Simulation)"))
        for field, term_dict in self.index.items():
            print(f"\n{BOLD}Field: {YELLOW}{field}{RESET} ({self.mapping_engine.get_field_type(field)})")
            print(f"{DIM}{'-'*65}{RESET}")
            print(f"{'TERM':<18} | {'DOC FREQ':<9} | {'POSTINGS (DocID, TF, Positions)'}")
            print(f"{DIM}{'-'*65}{RESET}")
            for term in sorted(term_dict.keys()):
                postings = term_dict[term]
                posting_repr = ", ".join([f"[id:{p.doc_id}|tf:{p.term_freq}|pos:{p.positions}]" for p in postings])
                print(f"{GREEN}{term:<18}{RESET} | {len(postings):<9} | {CYAN}{posting_repr}{RESET}")


def run_interactive_simulation():
    print(ANSIHelper.header("ELASTICSEARCH DEEP ENGINE: INVERTED INDEX & ANALYSIS"))
    print(f"{DIM}Simulasi teknis Lucene-based inverted index, analyzer pipeline & dynamic mapping{RESET}\n")

    # 1. Definisi Mapping Engine
    mapping_spec = {
        "title": "text",
        "content": "text",
        "category": "keyword",
        "author": "keyword"
    }
    mapping_engine = MockMappingEngine(mapping_spec)
    engine = MockInvertedIndex(mapping_engine)

    # 2. Simulasi Dataset
    dataset = [
        {
            "id": 1,
            "title": "Pengantar Elasticsearch Engine",
            "content": "<p>Elasticsearch menggunakan <b>inverted index</b> untuk pencarian teks yang cepat.</p>",
            "category": "Database",
            "author": "Budi Santoso"
        },
        {
            "id": 2,
            "title": "Optimasi Lucene Indexing",
            "content": "Inverted index memetakan term kata ke daftar doc_id dan posisi token.",
            "category": "Database",
            "author": "Andi Wijaya"
        },
        {
            "id": 3,
            "title": "Arsitektur Distributed Search",
            "content": "Pencarian full-text membutuhkan analyzer pipeline, tokenization, dan scoring BM25.",
            "category": "Architecture",
            "author": "Budi Santoso"
        },
        {
            "id": 4,
            "title": "Text Analysis Deep Dive",
            "content": "Analyzer terdiri dari char filter, standard tokenizer, dan lowercase filter.",
            "category": "Search",
            "author": "Siti Rahma"
        }
    ]

    print(ANSIHelper.subheader("Tahap 1: Ingestion Dokumen & Text Analysis Pipeline"))
    analyzer = Analyzer()
    sample_text = dataset[0]["content"]
    print(f"Sample Input RAW Text: {YELLOW}{sample_text}{RESET}")
    analyzed_tokens = analyzer.analyze(sample_text)
    print(f"Tokens Hasil Pipeline Analisis (HTML Strip -> Tokenizer -> Lowercase -> Stopword -> Stemmer):")
    for t in analyzed_tokens:
        print(f"  {CYAN}•{RESET} Term: {GREEN}{t['token']:<12}{RESET} Pos: {t['position']:<2} Offset: [{t['start_offset']}:{t['end_offset']}]")

    # Indexing all documents
    for doc in dataset:
        engine.index_document(doc["id"], doc)
    print(f"\n{GREEN}{BOLD}✓ Berhasil mengindeks {len(dataset)} dokumen ke Inverted Index.{RESET}")

    # 3. Tampilkan Struktur Inverted Index
    engine.print_inverted_index()

    # 4. Demonstrasi Pencarian: Text (BM25) vs Keyword (Exact)
    print(ANSIHelper.subheader("Tahap 2: Eksekusi Search Query (BM25 & Mapping Test)"))

    queries = [
        ("content", "inverted index pencarian"),
        ("content", "analyzer tokenization"),
        ("category", "Database"),
        ("category", "database"),  # Case-sensitive test for keyword
        ("author", "Budi Santoso")
    ]

    for field, query_text in queries:
        field_type = mapping_engine.get_field_type(field)
        print(f"\n{BOLD}Query:{RESET} {WHITE}'{query_text}'{RESET} pada field {YELLOW}{field}{RESET} ({ANSIHelper.badge(field_type, BLUE)})")
        results = engine.search_match(field, query_text)

        if not results:
            print(f"  {RED}Tidak ditemukan match (0 hit).{RESET}")
        else:
            print(f"  {GREEN}Ditemukan {len(results)} dokumen match:{RESET}")
            for doc_id, score, doc_source in results:
                print(f"    {CYAN}Doc #{doc_id}{RESET} (Score: {YELLOW}{score:.4f}{RESET}) | Title: {WHITE}{doc_source['title']}{RESET} | Cat: {MAGENTA}{doc_source['category']}{RESET}")

    print(ANSIHelper.header("SIMULASI SELESAI"))
    print(f"{GREEN}{BOLD}Fondasi Inverted Index, Analisis Teks, dan Mapping berhasil disimulasikan.{RESET}\n")


if __name__ == "__main__":
    run_interactive_simulation()
