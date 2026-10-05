#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi & Arsitektur Inti Elasticsearch
BAB-01: Fondasi dan Arsitektur Distributed Search Engine

Materi yang disimulasikan:
1. Inverted Indexing (Tokenization, Lowercasing, Postings List, Term Frequency)
2. Document Routing & Sharding (hash(_routing) % num_primary_shards)
3. Cluster Topology & Replica Placement Rules (High Availability)
4. Write Request Lifecycle (Coordinating Node -> Primary Shard -> Replica Sync)
"""

import hashlib
import json
import math
import os
import re
import sys
import time
from typing import Dict, List, Set, Tuple

# ANSI Escape Sequences untuk visualisasi terminal
class Style:
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
    BG_BLACK = "\033[40m"

def print_header(title: str):
    width = 75
    print("\n" + Style.CYAN + "=" * width + Style.RESET)
    print(f"{Style.BOLD}{Style.YELLOW} {title.center(width - 2)} {Style.RESET}")
    print(Style.CYAN + "=" * width + Style.RESET)

def print_section(title: str):
    print(f"\n{Style.BOLD}{Style.WHITE}>>> {title}{Style.RESET}")

# ------------------------------------------------------------------------------
# 1. SIMULATOR INVERTED INDEX (LUCENE CORE ENGINE)
# ------------------------------------------------------------------------------
class InvertedIndexEngine:
    def __init__(self):
        self.documents: Dict[str, str] = {}
        # index: term -> {doc_id: [positions]}
        self.index: Dict[str, Dict[str, List[int]]] = {}
        self.stop_words = {"dan", "di", "ke", "dari", "yang", "pada", "adalah", "ini", "itu", "the", "is", "at", "which", "on"}

    def tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        return cleaned.split()

    def add_document(self, doc_id: str, content: str):
        self.documents[doc_id] = content
        tokens = self.tokenize(content)
        
        for pos, term in enumerate(tokens):
            if term in self.stop_words:
                continue
            if term not in self.index:
                self.index[term] = {}
            if doc_id not in self.index[term]:
                self.index[term][doc_id] = []
            self.index[term][doc_id].append(pos)

    def display_dictionary(self):
        print(f"\n{Style.BOLD}{'Term (Token)':<18} | {'Doc Freq':<10} | {'Posting List (DocID: Positions)':<40}{Style.RESET}")
        print("-" * 75)
        for term in sorted(self.index.keys()):
            postings = self.index[term]
            doc_freq = len(postings)
            posting_repr = ", ".join([f"{doc_id}:{pos_list}" for doc_id, pos_list in postings.items()])
            print(f"{Style.GREEN}{term:<18}{Style.RESET} | {Style.YELLOW}{doc_freq:<10}{Style.RESET} | {Style.WHITE}{posting_repr}{Style.RESET}")

    def search(self, query: str) -> List[Tuple[str, float]]:
        query_terms = [t for t in self.tokenize(query) if t not in self.stop_words]
        if not query_terms:
            return []

        scores: Dict[str, float] = {doc_id: 0.0 for doc_id in self.documents}
        total_docs = len(self.documents)

        for term in query_terms:
            if term in self.index:
                postings = self.index[term]
                doc_freq = len(postings)
                idf = math.log((total_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
                for doc_id, positions in postings.items():
                    tf = len(positions)
                    # Simplified BM25 / TF-IDF scoring formula
                    scores[doc_id] += tf * idf

        ranked = sorted([(doc_id, score) for doc_id, score in scores.items() if score > 0], key=lambda x: x[1], reverse=True)
        return ranked

# ------------------------------------------------------------------------------
# 2. SIMULATOR SHARDING, ROUTING, & CLUSTER TOPOLOGY
# ------------------------------------------------------------------------------
class ClusterTopologySimulator:
    def __init__(self, node_names: List[str], num_primary_shards: int = 3, num_replicas: int = 1):
        self.node_names = node_names
        self.num_primary_shards = num_primary_shards
        self.num_replicas = num_replicas
        # Allocation: (shard_id, type) -> node_name
        self.shard_routing_table: Dict[str, str] = {}
        self._allocate_shards()

    def calculate_routing(self, doc_id: str, routing_val: str = None) -> int:
        """
        Rumus Elasticsearch Core:
        shard_num = murmur3_hash(routing) % number_of_primary_shards
        (Simulasi menggunakan MD5 hash untuk representasi deterministik)
        """
        key = routing_val if routing_val else doc_id
        hash_digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        hash_int = int(hash_digest, 16)
        shard_num = hash_int % self.num_primary_shards
        return shard_num

    def _allocate_shards(self):
        """
        Rule: Primary dan Replica shard dengan ID yang sama TIDAK boleh berada pada node yang sama!
        """
        num_nodes = len(self.node_names)
        for s_id in range(self.num_primary_shards):
            primary_node_idx = s_id % num_nodes
            primary_node = self.node_names[primary_node_idx]
            self.shard_routing_table[f"P{s_id}"] = primary_node

            # Tempatkan replika di node yang berbeda
            for r_id in range(self.num_replicas):
                replica_node_idx = (primary_node_idx + 1 + r_id) % num_nodes
                replica_node = self.node_names[replica_node_idx]
                self.shard_routing_table[f"R{s_id}_{r_id}"] = replica_node

    def display_cluster_state(self):
        print(f"\n{Style.BOLD}Konfigurasi Index:{Style.RESET} Primary={self.num_primary_shards} | Replicas={self.num_replicas}")
        print(f"{Style.BOLD}{'Node':<12} | {'Role':<18} | {'Allocated Shards':<35}{Style.RESET}")
        print("-" * 75)
        
        for idx, node in enumerate(self.node_names):
            role = "Master & Data" if idx == 0 else "Data Node"
            assigned_shards = [shard for shard, n in self.shard_routing_table.items() if n == node]
            shards_fmt = []
            for s in assigned_shards:
                if s.startswith("P"):
                    shards_fmt.append(f"{Style.GREEN}[{s}]{Style.RESET}")
                else:
                    shards_fmt.append(f"{Style.CYAN}[{s}]{Style.RESET}")
            
            print(f"{Style.BOLD}{node:<12}{Style.RESET} | {Style.MAGENTA}{role:<18}{Style.RESET} | {' '.join(shards_fmt)}")

    def simulate_write_request(self, doc_id: str, payload: dict, coordinating_node: str):
        print(f"\n{Style.YELLOW}Memulai Write Lifecycle untuk Doc ID:{Style.RESET} {Style.BOLD}'{doc_id}'{Style.RESET}")
        time.sleep(0.3)
        
        # Step 1: Coordinating Node menerima request
        target_shard = self.calculate_routing(doc_id)
        primary_key = f"P{target_shard}"
        primary_node = self.shard_routing_table[primary_key]
        
        print(f" 1. [Coordinating Node: {coordinating_node}] -> Hash routing:")
        print(f"    hash('{doc_id}') % {self.num_primary_shards} => {Style.BOLD}{Style.GREEN}Primary Shard {target_shard} ({primary_key}){Style.RESET}")
        time.sleep(0.3)

        # Step 2: Forward ke Primary Shard
        print(f" 2. [Network Hop] Forwarding document ke {Style.BOLD}{primary_node}{Style.RESET} pemegang {primary_key}...")
        print(f"    - Menulis ke In-memory Indexing Buffer...")
        print(f"    - Menulis append-only ke Translog (Write-Ahead Log) untuk durabilitas.")
        time.sleep(0.3)

        # Step 3: Replikasi ke Replica Shards
        replicas = [k for k in self.shard_routing_table.keys() if k.startswith(f"R{target_shard}")]
        for rep in replicas:
            rep_node = self.shard_routing_table[rep]
            print(f" 3. [Replication Hop] Primary {primary_key} paralel forward ke {Style.BOLD}{rep_node}{Style.RESET} ({rep})...")
            print(f"    - {rep} menulis ke buffer dan translog lokal.")
            time.sleep(0.2)

        # Step 4: Acknowledgment
        print(f" 4. {Style.GREEN}ACK: Semua active replica shards berhasil merespon.{Style.RESET}")
        print(f"    {coordinating_node} mengembalikan HTTP 201 Created kepada klien.")

# ------------------------------------------------------------------------------
# 3. INTERACTIVE CLI RUNNER
# ------------------------------------------------------------------------------
def run_interactive_lab():
    index_engine = InvertedIndexEngine()
    topology = ClusterTopologySimulator(
        node_names=["node-es-01", "node-es-02", "node-es-03"],
        num_primary_shards=3,
        num_replicas=1
    )

    # Seed data awal
    seed_docs = {
        "doc-101": "Elasticsearch adalah search engine terdistribusi berbasis Apache Lucene.",
        "doc-102": "Arsitektur Elasticsearch terdiri dari cluster, node, index, shard, dan replica.",
        "doc-103": "Inverted index memungkinkan pencarian full text berkecepatan tinggi dengan postings list.",
        "doc-104": "Lucene segment bersifat immutable, dibuat saat buffer di-refresh ke OS file system cache."
    }
    for d_id, text in seed_docs.items():
        index_engine.add_document(d_id, text)

    while True:
        print_header("LAB SIMULATOR: ELASTICSEARCH INTERNALS & ARCHITECTURE")
        print(f"{Style.BOLD}PILIHAN MODUL LAB:{Style.RESET}")
        print(" [1] Inspeksi Inverted Index (Dictionary & Postings List)")
        print(" [2] Uji Pencarian Full-Text Search (Scoring BM25/TF-IDF)")
        print(" [3] Tambah Dokumen Baru ke Inverted Index")
        print(" [4] Inspeksi Topologi Cluster, Routing Table & Shard Allocation")
        print(" [5] Simulasi Alur Write Request Lifecycle (Routing -> Primary -> Replica)")
        print(" [6] Jalankan Demo Komprehensif Otomatis")
        print(" [0] Keluar")
        
        try:
            choice = input(f"\n{Style.CYAN}Masukkan nomor modul [0-6]: {Style.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Style.YELLOW}Sesi lab diakhiri.{Style.RESET}")
            sys.exit(0)

        if choice == "1":
            print_section("INVERTED INDEX DICTIONARY")
            index_engine.display_dictionary()
            input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu...{Style.RESET}")

        elif choice == "2":
            print_section("PENCARIAN FULL-TEXT (LUCENE SCORING)")
            q = input(f"{Style.WHITE}Masukkan kata kunci pencarian: {Style.RESET}").strip()
            if q:
                results = index_engine.search(q)
                if not results:
                    print(f"{Style.RED}Tidak ada dokumen yang cocok dengan kata kunci '{q}'.{Style.RESET}")
                else:
                    print(f"\n{Style.BOLD}{'Rank':<6} | {'Doc ID':<10} | {'Score':<8} | {'Isi Dokumen':<50}{Style.RESET}")
                    print("-" * 75)
                    for rank, (doc_id, score) in enumerate(results, 1):
                        content = index_engine.documents[doc_id]
                        if len(content) > 47:
                            content = content[:44] + "..."
                        print(f"{rank:<6} | {Style.GREEN}{doc_id:<10}{Style.RESET} | {Style.YELLOW}{score:.4f}{Style.RESET}   | {content}")
            input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu...{Style.RESET}")

        elif choice == "3":
            print_section("INDEXING DOKUMEN BARU")
            new_id = input("Masukkan Doc ID (contoh: doc-105): ").strip()
            new_text = input("Masukkan isi dokumen: ").strip()
            if new_id and new_text:
                index_engine.add_document(new_id, new_text)
                print(f"{Style.GREEN}Dokumen '{new_id}' berhasil diindeks ke inverted index!{Style.RESET}")
            else:
                print(f"{Style.RED}ID atau isi dokumen tidak boleh kosong.{Style.RESET}")
            input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu...{Style.RESET}")

        elif choice == "4":
            print_section("TOPOLOGI CLUSTER & ALOKASI SHARD")
            topology.display_cluster_state()
            input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu...{Style.RESET}")

        elif choice == "5":
            print_section("SIMULASI WRITE REQUEST LIFECYCLE")
            sample_id = input("Masukkan Document ID yang akan di-write (default: doc-999): ").strip() or "doc-999"
            payload = {"message": "Test transaction event", "timestamp": time.time()}
            topology.simulate_write_request(sample_id, payload, coordinating_node="node-es-01")
            input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu...{Style.RESET}")

        elif choice == "6":
            print_section("MENJALANKAN DEMO KOMPREHENSIF")
            print(f"{Style.MAGENTA}1. Tampilan Inverted Index Awal:{Style.RESET}")
            index_engine.display_dictionary()
            
            print(f"\n{Style.MAGENTA}2. Test Search 'lucene segment':{Style.RESET}")
            res = index_engine.search("lucene segment")
            for r, (d, s) in enumerate(res, 1):
                print(f"   [{r}] {d} (Score: {s:.4f}) -> {index_engine.documents[d]}")
                
            print(f"\n{Style.MAGENTA}3. Cluster Topology Matrix:{Style.RESET}")
            topology.display_cluster_state()

            print(f"\n{Style.MAGENTA}4. Routing Calculation Test:{Style.RESET}")
            for test_id in ["order-1001", "order-1002", "order-1003", "user-alpha"]:
                shard = topology.calculate_routing(test_id)
                p_node = topology.shard_routing_table[f"P{shard}"]
                print(f"   Doc '{test_id:<12}' -> Primary Shard P{shard} di {p_node}")

            print(f"\n{Style.MAGENTA}5. Write Lifecycle Trace:{Style.RESET}")
            topology.simulate_write_request("order-8888", {"amount": 500000}, "node-es-03")
            print(f"\n{Style.GREEN}Demo komprehensif selesai.{Style.RESET}")
            input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu...{Style.RESET}")

        elif choice == "0":
            print(f"\n{Style.GREEN}Terima kasih telah menggunakan Lab Simulator Elasticsearch.{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan pilih 0-6.{Style.RESET}")

if __name__ == "__main__":
    run_interactive_lab()
