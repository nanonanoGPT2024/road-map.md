#!/usr/bin/env python3
"""
Lab Exercise M01: Elasticsearch Sharding, Scaling, and Routing Strategies
BAB 07 - Sharding, Scaling & Routing Strategies

Simulasi interaktif teknis arsitektur distributed Elasticsearch:
1. Primary vs Replica Shard Topology & Allocation Rules
2. Formula Hashing Murmur3: Math.floorMod(hash(routing), num_shards)
3. Default Routing (_id) vs Custom Routing (Tenant/User Co-location)
4. Scatter-Gather Query vs Targeted Single-Shard Query Cost
5. High Availability & Failover: Replica Promotion on Node Failure
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ANSI:
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
    BG_GREEN = "\033[42m"


class ShardType(Enum):
    PRIMARY = "PRIMARY"
    REPLICA = "REPLICA"


@dataclass
class Document:
    doc_id: str
    routing_key: str
    payload: dict
    target_shard: int = -1


@dataclass
class ShardCopy:
    shard_id: int
    shard_type: ShardType
    node_id: str
    documents: List[Document] = field(default_factory=list)


@dataclass
class Node:
    node_id: str
    node_name: str
    is_alive: bool = True
    shards: List[ShardCopy] = field(default_factory=list)


def murmur3_32(key: str, seed: int = 0) -> int:
    """Implementasi Murmur3 32-bit hash identik dengan implementasi Java di Elasticsearch."""
    data = key.encode("utf-8")
    length = len(data)
    nblocks = length // 4
    h1 = seed
    c1 = 0xCC9E2D51
    c2 = 0x1B873593

    for i in range(0, nblocks * 4, 4):
        k1 = (
            data[i]
            | (data[i + 1] << 8)
            | (data[i + 2] << 16)
            | (data[i + 3] << 24)
        )
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF

        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & 0xFFFFFFFF
        h1 = (h1 * 5 + 0xE6546B64) & 0xFFFFFFFF

    tail = data[nblocks * 4 :]
    k1 = 0
    tail_len = len(tail)
    if tail_len == 3:
        k1 ^= tail[2] << 16
    if tail_len >= 2:
        k1 ^= tail[1] << 8
    if tail_len >= 1:
        k1 ^= tail[0]
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    h1 ^= length
    h1 ^= h1 >> 16
    h1 = (h1 * 0x85EBCA6B) & 0xFFFFFFFF
    h1 ^= h1 >> 13
    h1 = (h1 * 0xC2B2AE35) & 0xFFFFFFFF
    h1 ^= h1 >> 16

    # Convert unsigned 32-bit int to signed 32-bit integer seperti Java
    if h1 >= 0x80000000:
        return h1 - 0x100000000
    return h1


class ESClusterSimulator:
    def __init__(self, index_name: str, num_primaries: int = 3, num_replicas: int = 1, num_nodes: int = 3):
        self.index_name = index_name
        self.num_primaries = num_primaries
        self.num_replicas = num_replicas
        self.num_nodes = num_nodes
        self.nodes: Dict[str, Node] = {}
        self.documents_index: Dict[str, Document] = {}
        self._init_nodes()
        self._allocate_shards()

    def _init_nodes(self):
        self.nodes.clear()
        for i in range(1, self.num_nodes + 1):
            node_id = f"node-{i}"
            self.nodes[node_id] = Node(node_id=node_id, node_name=f"es-data-node-{i}")

    def _allocate_shards(self):
        """Alokasi Primary dan Replica. Syarat Elasticsearch: Replica tidak boleh berada di node yang sama dengan Primarynya."""
        node_ids = list(self.nodes.keys())
        total_nodes = len(node_ids)

        for p_id in range(self.num_primaries):
            primary_node_idx = p_id % total_nodes
            p_node = self.nodes[node_ids[primary_node_idx]]
            p_node.shards.append(ShardCopy(shard_id=p_id, shard_type=ShardType.PRIMARY, node_id=p_node.node_id))

            for r_idx in range(self.num_replicas):
                replica_node_idx = (primary_node_idx + 1 + r_idx) % total_nodes
                r_node = self.nodes[node_ids[replica_node_idx]]
                r_node.shards.append(ShardCopy(shard_id=p_id, shard_type=ShardType.REPLICA, node_id=r_node.node_id))

    def calculate_shard(self, routing_key: str) -> Tuple[int, int]:
        """Formula: Math.floorMod(Murmur3Hash.hash(routing), number_of_primary_shards)"""
        raw_hash = murmur3_32(routing_key)
        target_shard = raw_hash % self.num_primaries
        return raw_hash, target_shard

    def index_document(self, doc_id: str, custom_routing: Optional[str], payload: dict) -> Tuple[int, int, str]:
        routing_key = custom_routing if custom_routing else doc_id
        raw_hash, shard_id = self.calculate_shard(routing_key)
        doc = Document(doc_id=doc_id, routing_key=routing_key, payload=payload, target_shard=shard_id)
        self.documents_index[doc_id] = doc

        # Tulis ke Primary dan replika aktif
        primary_node = None
        for node in self.nodes.values():
            if not node.is_alive:
                continue
            for shard in node.shards:
                if shard.shard_id == shard_id:
                    shard.documents.append(doc)
                    if shard.shard_type == ShardType.PRIMARY:
                        primary_node = node.node_id

        return raw_hash, shard_id, primary_node or "UNKNOWN"

    def print_cluster_topology(self):
        print(f"\n{ANSI.BOLD}{ANSI.CYAN}=== ELASTICSEARCH CLUSTER TOPOLOGY: [{self.index_name}] ==={ANSI.RESET}")
        print(f"Konfigurasi: {ANSI.YELLOW}number_of_shards = {self.num_primaries}{ANSI.RESET} | {ANSI.YELLOW}number_of_replicas = {self.num_replicas}{ANSI.RESET} | Total Node = {len(self.nodes)}\n")

        for node_id, node in sorted(self.nodes.items()):
            status = f"{ANSI.GREEN}[ONLINE]{ANSI.RESET}" if node.is_alive else f"{ANSI.RED}[OFFLINE / DOWN]{ANSI.RESET}"
            print(f"🖥️  {ANSI.BOLD}{node.node_name}{ANSI.RESET} ({node.node_id}) {status}")
            if not node.shards:
                print(f"    {ANSI.DIM}(Kosong - tidak ada shard dialokasikan){ANSI.RESET}")
            for shard in node.shards:
                type_badge = (
                    f"{ANSI.GREEN}{ANSI.BOLD}PRIMARY P{shard.shard_id}{ANSI.RESET}"
                    if shard.shard_type == ShardType.PRIMARY
                    else f"{ANSI.BLUE}REPLICA R{shard.shard_id}{ANSI.RESET}"
                )
                print(f"    ├─ [{type_badge}] -> {len(shard.documents)} dokumen tersimpan")
            print()

    def simulate_scatter_gather_search(self, term: str):
        print(f"\n{ANSI.BOLD}{ANSI.MAGENTA}--- SIMULASI QUERY: SCATTER-GATHER (Tanpa Routing Key) ---{ANSI.RESET}")
        print(f"{ANSI.DIM}Kueri dikirim ke coordinator node, lalu di-scatter ke SEMUA {self.num_primaries} primary shards:{ANSI.RESET}")
        
        start_time = time.perf_counter()
        shard_hits = {}
        total_inspected = 0
        total_hits = 0

        for shard_id in range(self.num_primaries):
            # Ambil salinan aktif pertama
            target_shard = None
            for node in self.nodes.values():
                if not node.is_alive:
                    continue
                for s in node.shards:
                    if s.shard_id == shard_id:
                        target_shard = s
                        break
                if target_shard:
                    break

            if target_shard:
                inspected = len(target_shard.documents)
                total_inspected += inspected
                matches = [d for d in target_shard.documents if term in str(d.payload.values()) or term in d.doc_id]
                total_hits += len(matches)
                shard_hits[shard_id] = len(matches)
                print(f"  {ANSI.YELLOW}→ Scatter ke Shard [{shard_id}] pada {target_shard.node_id}:{ANSI.RESET} Periksa {inspected} docs -> Match: {len(matches)}")
            else:
                print(f"  {ANSI.RED}→ Shard [{shard_id}] UNASSIGNED / Node Down! (Cluster RED/YELLOW){ANSI.RESET}")

        elapsed_ms = (time.perf_counter() - start_time) * 1000 + (self.num_primaries * 1.8)
        print(f"\n{ANSI.BOLD}Hasil Scatter-Gather:{ANSI.RESET}")
        print(f"  Total Network RTT Shard : {self.num_primaries} remote shard roundtrips")
        print(f"  Total Dokumen Diinspeksi: {total_inspected}")
        print(f"  Total Hits Ditemukan    : {ANSI.GREEN}{total_hits}{ANSI.RESET}")
        print(f"  Estimasi Waktu Eksekusi : {ANSI.YELLOW}{elapsed_ms:.2f} ms{ANSI.RESET}")

    def simulate_targeted_routing_search(self, routing_key: str, term: str):
        print(f"\n{ANSI.BOLD}{ANSI.CYAN}--- SIMULASI QUERY: TARGETED ROUTING (Dengan ?routing={routing_key}) ---{ANSI.RESET}")
        raw_hash, target_shard_id = self.calculate_shard(routing_key)
        print(f"{ANSI.DIM}Formula dihitung langsung di Coordinator Node: murmur3('{routing_key}') % {self.num_primaries} = Shard [{target_shard_id}]{ANSI.RESET}")
        print(f"{ANSI.GREEN}Hanya 1 shard yang dipanggil! Tidak ada scatter ke shard lain.{ANSI.RESET}")

        start_time = time.perf_counter()
        target_shard = None
        for node in self.nodes.values():
            if not node.is_alive:
                continue
            for s in node.shards:
                if s.shard_id == target_shard_id:
                    target_shard = s
                    break
            if target_shard:
                break

        if target_shard:
            inspected = len(target_shard.documents)
            matches = [d for d in target_shard.documents if term in str(d.payload.values()) or term in d.doc_id]
            elapsed_ms = (time.perf_counter() - start_time) * 1000 + 1.8
            print(f"  {ANSI.CYAN}→ Direct RPC ke Shard [{target_shard_id}] pada {target_shard.node_id}:{ANSI.RESET} Periksa {inspected} docs -> Match: {len(matches)}")
            print(f"\n{ANSI.BOLD}Hasil Targeted Routing:{ANSI.RESET}")
            print(f"  Total Network RTT Shard : {ANSI.GREEN}1 remote shard roundtrip (Hemat {(self.num_primaries - 1) * 100 // self.num_primaries}% network overhead){ANSI.RESET}")
            print(f"  Total Dokumen Diinspeksi: {inspected}")
            print(f"  Total Hits Ditemukan    : {ANSI.GREEN}{len(matches)}{ANSI.RESET}")
            print(f"  Estimasi Waktu Eksekusi : {ANSI.GREEN}{elapsed_ms:.2f} ms{ANSI.RESET}")
        else:
            print(f"  {ANSI.RED}Target Shard [{target_shard_id}] tidak dapat diakses!{ANSI.RESET}")

    def simulate_node_failover(self, failed_node_id: str):
        print(f"\n{ANSI.BOLD}{ANSI.RED}=== SIMULASI NODE FAILOVER: {failed_node_id} ==={ANSI.RESET}")
        if failed_node_id not in self.nodes or not self.nodes[failed_node_id].is_alive:
            print(f"{ANSI.YELLOW}Node {failed_node_id} sudah offline atau tidak ditemukan.{ANSI.RESET}")
            return

        self.nodes[failed_node_id].is_alive = False
        print(f"⚠️  {ANSI.RED}Heartbeat lost! Node {failed_node_id} mati secara mendadak.{ANSI.RESET}")

        lost_shards = self.nodes[failed_node_id].shards
        for s in lost_shards:
            print(f"   Terputus: Shard [{s.shard_type.value} {s.shard_id}] pada {failed_node_id}")

        print(f"\n{ANSI.BOLD}{ANSI.YELLOW}Master Node memulai proses Re-routing & Failover Promotion...{ANSI.RESET}")
        time.sleep(0.5)

        for s in lost_shards:
            if s.shard_type == ShardType.PRIMARY:
                promoted = False
                for n_id, node in self.nodes.items():
                    if node.is_alive:
                        for candidate in node.shards:
                            if candidate.shard_id == s.shard_id and candidate.shard_type == ShardType.REPLICA:
                                candidate.shard_type = ShardType.PRIMARY
                                print(f"  {ANSI.GREEN}✔ PROMOSI SUKSES:{ANSI.RESET} REPLICA R{s.shard_id} di {n_id} resmi dipromosikan menjadi {ANSI.BOLD}PRIMARY P{s.shard_id}{ANSI.RESET}")
                                promoted = True
                                break
                    if promoted:
                        break
                if not promoted:
                    print(f"  {ANSI.RED}✖ DATA LOSS / RED CLUSTER:{ANSI.RESET} Tidak ada replika tersisa untuk Primary P{s.shard_id}!")


def seed_sample_dataset(sim: ESClusterSimulator):
    samples = [
        ("doc-101", None, {"company": "Acme Corp", "user": "Alice", "country": "ID"}),
        ("doc-102", None, {"company": "Stark Ind", "user": "Tony", "country": "US"}),
        ("doc-103", None, {"company": "Wayne Ent", "user": "Bruce", "country": "US"}),
        ("doc-104", "tenant_alpha", {"company": "TenantAlpha", "role": "admin", "log": "login_success"}),
        ("doc-105", "tenant_alpha", {"company": "TenantAlpha", "role": "member", "log": "view_dashboard"}),
        ("doc-106", "tenant_alpha", {"company": "TenantAlpha", "role": "billing", "log": "invoice_paid"}),
        ("doc-107", "tenant_beta", {"company": "TenantBeta", "role": "admin", "log": "password_change"}),
        ("doc-108", "tenant_beta", {"company": "TenantBeta", "role": "guest", "log": "session_timeout"}),
        ("doc-109", None, {"company": "Cyberdyne", "user": "Skynet", "country": "JP"}),
    ]
    for doc_id, routing, payload in samples:
        sim.index_document(doc_id, routing, payload)


def run_interactive():
    print(f"{ANSI.BOLD}{ANSI.BG_BLUE}{ANSI.WHITE}  ELASTICSEARCH LAB: BAB 07 SHARDING & ROUTING  {ANSI.RESET}\n")
    sim = ESClusterSimulator(index_name="saas_analytics", num_primaries=3, num_replicas=1, num_nodes=3)
    seed_sample_dataset(sim)

    while True:
        print(f"\n{ANSI.BOLD}PILIHAN LAB INTERAKTIF:{ANSI.RESET}")
        print(f"  {ANSI.CYAN}1.{ANSI.RESET} Tampilkan Topologi Cluster & Distribusi Shard")
        print(f"  {ANSI.CYAN}2.{ANSI.RESET} Simulasi Indexing Dokumen & Rumus Hashing Routing")
        print(f"  {ANSI.CYAN}3.{ANSI.RESET} Benchmark: Scatter-Gather vs Targeted Routing Query")
        print(f"  {ANSI.CYAN}4.{ANSI.RESET} Simulasi Node Failure & Auto-Promotion Primary Shard")
        print(f"  {ANSI.CYAN}5.{ANSI.RESET} Demo Otomatis Lengkap (Self-Guided Tour)")
        print(f"  {ANSI.RED}0.{ANSI.RESET} Keluar")

        try:
            choice = input(f"\n{ANSI.BOLD}Pilih nomor modul [0-5]: {ANSI.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{ANSI.YELLOW}Keluar dari lab.{ANSI.RESET}")
            break

        if choice == "1":
            sim.print_cluster_topology()
        elif choice == "2":
            doc_id = input("Masukkan Document ID [default: order-999]: ").strip() or "order-999"
            custom_routing = input("Gunakan Custom Routing Key? (kosongkan untuk default _id): ").strip() or None
            raw_hash, shard_id, node_id = sim.index_document(doc_id, custom_routing, {"test": "data", "ts": time.time()})
            used_key = custom_routing if custom_routing else doc_id
            print(f"\n{ANSI.GREEN}Dokumen berhasil di-index!{ANSI.RESET}")
            print(f"  Routing Key Digunakan: '{used_key}'")
            print(f"  Murmur3 32-bit Hash  : {raw_hash}")
            print(f"  Rumus ES             : Math.floorMod({raw_hash}, {sim.num_primaries}) = Shard [{shard_id}]")
            print(f"  Primary Node Tujuan  : {node_id}")
        elif choice == "3":
            term = input("Masukkan kata kunci pencarian [default: TenantAlpha]: ").strip() or "TenantAlpha"
            sim.simulate_scatter_gather_search(term)
            sim.simulate_targeted_routing_search("tenant_alpha", term)
        elif choice == "4":
            print("Node yang tersedia:")
            for n_id, n in sim.nodes.items():
                status = "UP" if n.is_alive else "DOWN"
                print(f" - {n_id} ({status})")
            target = input("Pilih node yang ingin dimatikan [default: node-1]: ").strip() or "node-1"
            sim.simulate_node_failover(target)
            sim.print_cluster_topology()
        elif choice == "5":
            print(f"\n{ANSI.BOLD}{ANSI.YELLOW}=== MENJALANKAN SELF-GUIDED TOUR OTOMATIS ==={ANSI.RESET}")
            sim.print_cluster_topology()
            time.sleep(1)
            print(f"\n{ANSI.BOLD}[Step 1] Mengindeks dokumen dengan Custom Tenant Routing:{ANSI.RESET}")
            sim.index_document("doc-test-1", "tenant_xyz", {"data": "confidential"})
            h, s = sim.calculate_shard("tenant_xyz")
            print(f"  Murmur3('tenant_xyz') % 3 = Shard [{s}]")
            time.sleep(1)
            print(f"\n{ANSI.BOLD}[Step 2] Perbandingan Kinerja Kueri:{ANSI.RESET}")
            sim.simulate_scatter_gather_search("TenantAlpha")
            sim.simulate_targeted_routing_search("tenant_alpha", "TenantAlpha")
            time.sleep(1)
            print(f"\n{ANSI.BOLD}[Step 3] Chaos Engineering - Mematikan node-1:{ANSI.RESET}")
            sim.simulate_node_failover("node-1")
            sim.print_cluster_topology()
            print(f"\n{ANSI.BOLD}{ANSI.GREEN}✔ Demo Otomatis Selesai.{ANSI.RESET}")
        elif choice == "0":
            print(f"{ANSI.GREEN}Lab selesai. Selamat belajar arsitektur distributed Elasticsearch!{ANSI.RESET}")
            break
        else:
            print(f"{ANSI.RED}Pilihan tidak valid, silakan ulangi.{ANSI.RESET}")


if __name__ == "__main__":
    run_interactive()
