#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Elasticsearch Sharding, Scaling, dan Custom Routing Strategies
Materi: BAB-07 Sharding, Scaling, and Routing Strategies
Tingkat: Arsitektur Produksi Tingkat Lanjut (Production Architecture Simulation)
"""

import sys
import time
import zlib
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# ANSI Terminal Color Configuration
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    FG_RED = "\033[91m"
    FG_GREEN = "\033[92m"
    FG_YELLOW = "\033[93m"
    FG_BLUE = "\033[94m"
    FG_MAGENTA = "\033[95m"
    FG_CYAN = "\033[96m"
    FG_WHITE = "\033[97m"
    
    # Background
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[100m"

def cprint(text: str, color: str = Color.RESET, bold: bool = False, end: str = "\n"):
    style = f"{Color.BOLD if bold else ''}{color}"
    print(f"{style}{text}{Color.RESET}", end=end)

# ==============================================================================
# Pure Python Murmur3 Implementation (Mirrors Elasticsearch Default Routing)
# ==============================================================================
def murmur3_32(key: str, seed: int = 0) -> int:
    """Implementasi 32-bit MurmurHash3 yang identik dengan Elasticsearch routing hash."""
    data = key.encode("utf-8")
    length = len(data)
    h1 = seed
    c1 = 0xCC9E2D51
    c2 = 0x1B873593

    # Process blocks of 4 bytes
    nblocks = length // 4
    for i in range(nblocks):
        idx = i * 4
        k1 = (data[idx] & 0xFF) | \
             ((data[idx + 1] & 0xFF) << 8) | \
             ((data[idx + 2] & 0xFF) << 16) | \
             ((data[idx + 3] & 0xFF) << 24)

        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF

        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & 0xFFFFFFFF
        h1 = (h1 * 5 + 0xE6546B64) & 0xFFFFFFFF

    # Process tail bytes
    tail_idx = nblocks * 4
    k1 = 0
    rem = length & 3
    if rem >= 3:
        k1 ^= (data[tail_idx + 2] & 0xFF) << 16
    if rem >= 2:
        k1 ^= (data[tail_idx + 1] & 0xFF) << 8
    if rem >= 1:
        k1 ^= (data[tail_idx] & 0xFF)
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    # Finalization
    h1 ^= length
    h1 ^= (h1 >> 16)
    h1 = (h1 * 0x85EBCA6B) & 0xFFFFFFFF
    h1 ^= (h1 >> 13)
    h1 = (h1 * 0xC2B2AE35) & 0xFFFFFFFF
    h1 ^= (h1 >> 16)

    return h1

# ==============================================================================
# Model Entities: Document, Shard, Data Node, Cluster
# ==============================================================================
@dataclass
class Document:
    doc_id: str
    tenant_id: str
    payload: str
    custom_routing: Optional[str] = None

@dataclass
class Shard:
    shard_id: int
    is_primary: bool
    index_name: str
    docs: List[Document] = field(default_factory=list)
    disk_usage_mb: float = 0.0

@dataclass
class Node:
    node_id: str
    name: str
    zone: str
    tier: str  # 'hot', 'warm', 'cold'
    allocated_shards: List[Shard] = field(default_factory=list)

    @property
    def total_docs(self) -> int:
        return sum(len(s.docs) for s in self.allocated_shards)

    @property
    def total_storage_mb(self) -> float:
        return sum(s.disk_usage_mb for s in self.allocated_shards)

class ESClusterSimulator:
    def __init__(self, primary_shards: int = 5, replica_factor: int = 1):
        self.primary_shards_count = primary_shards
        self.replica_factor = replica_factor
        self.nodes: Dict[str, Node] = {}
        self.routing_cache: Dict[str, int] = {}
        self._init_topology()

    def _init_topology(self):
        """Membuat topologi 3 zona ketersediaan (AZ-A, AZ-B, AZ-C) dengan multi-tier node."""
        self.nodes = {
            "node-hot-1": Node("node-hot-1", "hot-node-az1", zone="zone-a", tier="hot"),
            "node-hot-2": Node("node-hot-2", "hot-node-az2", zone="zone-b", tier="hot"),
            "node-hot-3": Node("node-hot-3", "hot-node-az3", zone="zone-c", tier="hot"),
            "node-warm-1": Node("node-warm-1", "warm-node-az1", zone="zone-a", tier="warm"),
            "node-warm-2": Node("node-warm-2", "warm-node-az2", zone="zone-b", tier="warm"),
        }
        self.allocate_shards()

    def allocate_shards(self):
        """Alokasi Primary dan Replica shard dengan aturan Zone Awareness (Anti-Affinity)."""
        hot_nodes = [n for n in self.nodes.values() if n.tier == "hot"]
        for node in hot_nodes:
            node.allocated_shards.clear()

        # Alokasi Primaries
        for s_id in range(self.primary_shards_count):
            target_node = hot_nodes[s_id % len(hot_nodes)]
            primary_shard = Shard(shard_id=s_id, is_primary=True, index_name="enterprise-logs")
            target_node.allocated_shards.append(primary_shard)

        # Alokasi Replicas pada zona berbeda (High Availability Protection)
        for s_id in range(self.primary_shards_count):
            primary_node = next(n for n in hot_nodes if any(s.shard_id == s_id and s.is_primary for s in n.allocated_shards))
            eligible_nodes = [n for n in hot_nodes if n.zone != primary_node.zone]
            if not eligible_nodes:
                eligible_nodes = [n for n in hot_nodes if n.node_id != primary_node.node_id]

            for r_idx in range(self.replica_factor):
                rep_node = eligible_nodes[r_idx % len(eligible_nodes)]
                replica_shard = Shard(shard_id=s_id, is_primary=False, index_name="enterprise-logs")
                rep_node.allocated_shards.append(replica_shard)

    def calculate_shard(self, routing_key: str) -> Tuple[int, int]:
        """
        Rumus Elasticsearch Default:
        shard = (murmur3(routing) & 0x7FFFFFFF) % number_of_primary_shards
        """
        raw_hash = murmur3_32(routing_key)
        positive_hash = raw_hash & 0x7FFFFFFF
        shard_id = positive_hash % self.primary_shards_count
        return positive_hash, shard_id

    def index_document(self, doc: Document) -> Tuple[int, str]:
        """Index dokumen ke shard target dan sinkronisasi ke seluruh replica."""
        routing_key = doc.custom_routing if doc.custom_routing else doc.doc_id
        _, target_shard_id = self.calculate_shard(routing_key)

        primary_node_name = "UNKNOWN"
        for node in self.nodes.values():
            for shard in node.allocated_shards:
                if shard.shard_id == target_shard_id:
                    shard.docs.append(doc)
                    shard.disk_usage_mb += round(random.uniform(1.2, 3.5), 2)
                    if shard.is_primary:
                        primary_node_name = node.name

        return target_shard_id, primary_node_name

    def query_scatter_gather(self, query_term: str) -> Dict[str, any]:
        """Simulasi Scatter-Gather Query: wajib menghubungi seluruh primary shards."""
        start_time = time.perf_counter()
        visited_shards = set()
        matched_docs = []

        hot_nodes = [n for n in self.nodes.values() if n.tier == "hot"]
        for node in hot_nodes:
            for shard in node.allocated_shards:
                if shard.is_primary:
                    visited_shards.add(shard.shard_id)
                    for doc in shard.docs:
                        if query_term in doc.payload or query_term == "*":
                            matched_docs.append(doc)

        elapsed_ms = (time.perf_counter() - start_time) * 1000 + (len(visited_shards) * 1.8)
        return {
            "strategy": "Scatter-Gather (Non-Routed)",
            "visited_shards": sorted(list(visited_shards)),
            "shards_queried_count": len(visited_shards),
            "total_matches": len(matched_docs),
            "simulated_latency_ms": round(elapsed_ms, 2),
            "network_hops": len(visited_shards) * 2
        }

    def query_routed(self, routing_key: str, query_term: str) -> Dict[str, any]:
        """Simulasi Targeted Routed Query: langsung ke shard spesifik."""
        start_time = time.perf_counter()
        _, target_shard_id = self.calculate_shard(routing_key)
        matched_docs = []

        hot_nodes = [n for n in self.nodes.values() if n.tier == "hot"]
        target_shard = None
        for node in hot_nodes:
            for shard in node.allocated_shards:
                if shard.shard_id == target_shard_id and shard.is_primary:
                    target_shard = shard
                    break
            if target_shard:
                break

        if target_shard:
            for doc in target_shard.docs:
                if query_term in doc.payload or query_term == "*":
                    matched_docs.append(doc)

        elapsed_ms = (time.perf_counter() - start_time) * 1000 + 1.2
        return {
            "strategy": f"Custom-Routed [routing={routing_key}]",
            "visited_shards": [target_shard_id],
            "shards_queried_count": 1,
            "total_matches": len(matched_docs),
            "simulated_latency_ms": round(elapsed_ms, 2),
            "network_hops": 2
        }

# ==============================================================================
# Visualization and Terminal UI Helpers
# ==============================================================================
def print_header(title: str):
    print("\n" + "=" * 80)
    cprint(f" {title.center(78)} ", Color.BG_BLUE + Color.FG_WHITE, bold=True)
    print("=" * 80)

def render_cluster_topology(cluster: ESClusterSimulator):
    print("\n" + Color.BOLD + "=== ES CLUSTER TOPOLOGY & SHARD ALLOCATION MATRIX ===" + Color.RESET)
    print(f"{'Node Name':<18} | {'Zone':<8} | {'Tier':<6} | {'Storage':<10} | {'Shards (P=Primary, R=Replica)'}")
    print("-" * 80)

    for node in cluster.nodes.values():
        shard_tags = []
        for s in node.allocated_shards:
            tag = f"[P{s.shard_id}]" if s.is_primary else f"[R{s.shard_id}]"
            color = Color.FG_GREEN if s.is_primary else Color.FG_CYAN
            shard_tags.append(f"{color}{tag}{Color.RESET}({len(s.docs)}d)")

        shards_str = " ".join(shard_tags) if shard_tags else f"{Color.DIM}<Empty>{Color.RESET}"
        storage_str = f"{node.total_storage_mb:.1f} MB"
        print(f"{node.name:<18} | {node.zone:<8} | {node.tier:<6} | {storage_str:<10} | {shards_str}")
    print("-" * 80)

# ==============================================================================
# Interactive Scenarios
# ==============================================================================
def scenario_1_routing_math(cluster: ESClusterSimulator):
    print_header("SKENARIO 1: MATEMATIKA ROUTING & FORMULA SHARD TARGET")
    cprint("Menghitung rute dokumen menggunakan Elasticsearch Murmur3 formula:", Color.FG_YELLOW)
    cprint("Formula: shard_num = (murmur3_32(routing_key) & 0x7FFFFFFF) % num_primary_shards\n", Color.DIM)

    sample_keys = ["user_1001", "tenant_tokopedia", "tenant_shopee", "user_9921", "tenant_grab"]
    print(f"{'Routing Key':<20} | {'Murmur3 Hash (Hex)':<18} | {'Positive Int':<12} | {'Target Shard'}")
    print("-" * 70)

    for key in sample_keys:
        pos_hash, shard_id = cluster.calculate_shard(key)
        hex_hash = f"0x{pos_hash:08X}"
        cprint(f"{key:<20} | {hex_hash:<18} | {pos_hash:<12} | ", Color.FG_WHITE, end="")
        cprint(f"Shard #{shard_id}", Color.FG_GREEN, bold=True)
    print("-" * 70)

def scenario_2_ingestion_and_skew_check(cluster: ESClusterSimulator):
    print_header("SKENARIO 2: BULK INGESTION DENGAN CUSTOM ROUTING (MULTI-TENANCY)")
    cprint("Menginjeksi 120 dokumen dengan dua strategi routing:", Color.FG_YELLOW)
    cprint(" - Tenant Alpha (50 docs) -> Routed by 'tenant-alpha'", Color.FG_CYAN)
    cprint(" - Tenant Beta  (40 docs) -> Routed by 'tenant-beta'", Color.FG_CYAN)
    cprint(" - Tenant Gamma (30 docs) -> Non-routed (Default round-hash by doc_id)", Color.FG_MAGENTA)

    # Ingest Tenant Alpha (Colocated)
    for i in range(50):
        doc = Document(doc_id=f"alpha_{i:03d}", tenant_id="alpha", payload=f"Transaction log payment record {i}", custom_routing="tenant-alpha")
        cluster.index_document(doc)

    # Ingest Tenant Beta (Colocated)
    for i in range(40):
        doc = Document(doc_id=f"beta_{i:03d}", tenant_id="beta", payload=f"Inventory check item order {i}", custom_routing="tenant-beta")
        cluster.index_document(doc)

    # Ingest Tenant Gamma (Scatter across shards)
    for i in range(30):
        doc = Document(doc_id=f"gamma_{i:03d}", tenant_id="gamma", payload=f"Telemetry metric sensor data {i}", custom_routing=None)
        cluster.index_document(doc)

    render_cluster_topology(cluster)
    cprint("\n[ANALISIS DETEKSI SHARD SKEW / HOTSPOT]", Color.FG_YELLOW, bold=True)
    cprint("Custom routing mengonsolidasikan seluruh data Tenant Alpha ke 1 shard tunggal.", Color.FG_WHITE)
    cprint("Keuntungan: Query tenant sangat cepat (O(1) shard target).", Color.FG_GREEN)
    cprint("Risiko: Shard hotspot jika ukuran tenant membesar secara eksponensial.", Color.FG_RED)

def scenario_3_benchmark_query(cluster: ESClusterSimulator):
    print_header("SKENARIO 3: BENCHMARK KINERJA (SCATTER-GATHER VS CUSTOM-ROUTED)")

    cprint("1. Melakukan Query Multi-Shard (Scatter-Gather):", Color.FG_YELLOW, bold=True)
    res_sg = cluster.query_scatter_gather("Transaction")
    print(f"   * Shards Terlibat : {res_sg['visited_shards']} (Total: {res_sg['shards_queried_count']} shards)")
    print(f"   * Network Hops    : {res_sg['network_hops']} roundtrips antar node")
    print(f"   * Latensi Simulasi: {Color.FG_RED}{res_sg['simulated_latency_ms']} ms{Color.RESET}")

    cprint("\n2. Melakukan Query Single-Shard (Custom-Routed):", Color.FG_YELLOW, bold=True)
    res_rt = cluster.query_routed("tenant-alpha", "Transaction")
    print(f"   * Shards Terlibat : {res_rt['visited_shards']} (Target Spesifik)")
    print(f"   * Network Hops    : {res_rt['network_hops']} roundtrips (Langsung ke Shard Primari)")
    print(f"   * Latensi Simulasi: {Color.FG_GREEN}{res_rt['simulated_latency_ms']} ms{Color.RESET}")

    improvement = ((res_sg['simulated_latency_ms'] - res_rt['simulated_latency_ms']) / res_sg['simulated_latency_ms']) * 100
    print("\n" + "-" * 70)
    cprint(f"[HASIL EFISIENSI] Reduksi Beban I/O & Shard Overhead: ~{improvement:.1f}% Lebih Efisien!", Color.FG_GREEN, bold=True)
    print("-" * 70)

def scenario_4_oversharding_calculator():
    print_header("SKENARIO 4: AUDITOR SHARD SIZING & OVERSHARDING ANTI-PATTERN")
    cprint("Menghitung efisiensi indeks berdasarkan best-practice Elastic (20GB - 50GB per Shard):\n", Color.FG_YELLOW)

    test_cases = [
        {"name": "ecommerce-logs", "size_gb": 4.5, "primaries": 10, "replicas": 1},
        {"name": "user-profiles", "size_gb": 120.0, "primaries": 3, "replicas": 2},
        {"name": "clickstream-raw", "size_gb": 450.0, "primaries": 5, "replicas": 1},
    ]

    print(f"{'Index Name':<18} | {'Total Data':<10} | {'P / R':<6} | {'Avg Shard':<10} | {'Status Kesehatan Sharding'}")
    print("-" * 80)

    for tc in test_cases:
        avg_shard_gb = tc["size_gb"] / tc["primaries"]
        total_shards = tc["primaries"] * (1 + tc["replicas"])

        if avg_shard_gb < 10.0:
            status = f"{Color.FG_RED}[CRITICAL] Oversharding! Shard <10GB membebani heap JVM.{Color.RESET}"
        elif 20.0 <= avg_shard_gb <= 50.0:
            status = f"{Color.FG_GREEN}[OPTIMAL] Sweet Spot (20-50GB/shard).{Color.RESET}"
        elif avg_shard_gb > 65.0:
            status = f"{Color.FG_YELLOW}[WARNING] Shard >65GB memperlambat recovery & merge.{Color.RESET}"
        else:
            status = f"{Color.FG_CYAN}[ACCEPTABLE] Ukuran shard wajar.{Color.RESET}"

        print(f"{tc['name']:<18} | {tc['size_gb']:>6.1f} GB | {tc['primaries']}P/{tc['replicas']}R  | {avg_shard_gb:>6.1f} GB  | {status}")
    print("-" * 80)

# ==============================================================================
# Main Interactive Runner & Automated Demo
# ==============================================================================
def run_all_scenarios():
    cluster = ESClusterSimulator(primary_shards=5, replica_factor=1)
    render_cluster_topology(cluster)
    scenario_1_routing_math(cluster)
    scenario_2_ingestion_and_skew_check(cluster)
    scenario_3_benchmark_query(cluster)
    scenario_4_oversharding_calculator()
    cprint("\n[OK] Seluruh simulasi arsitektur produksi Sharding & Routing selesai dijalankan.", Color.FG_GREEN, bold=True)

def interactive_cli():
    cluster = ESClusterSimulator(primary_shards=5, replica_factor=1)
    while True:
        print_header("ELASTICSEARCH ARCHITECTURE LAB: SHARDING & ROUTING (BAB-07)")
        print("Pilih simulasi yang ingin dijalankan:")
        print("  1. Tampilkan Topologi Cluster & Matriks Shard Allocation (Zone Awareness)")
        print("  2. Skenario 1: Bedah Matematika Murmur3 & Routing Formula")
        print("  3. Skenario 2: Ingest Multi-Tenant & Deteksi Hotspot Sharding")
        print("  4. Skenario 3: Benchmark Performa Scatter-Gather vs Custom-Routing")
        print("  5. Skenario 4: Evaluasi Oversharding & Heap Memory Sizing")
        print("  6. Jalankan Semua Skenario Sekaligus (Automated Full Lab Run)")
        print("  0. Keluar")
        print("-" * 80)

        try:
            choice = input(f"{Color.BOLD}Masukkan opsi [0-6]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            render_cluster_topology(cluster)
        elif choice == "2":
            scenario_1_routing_math(cluster)
        elif choice == "3":
            scenario_2_ingestion_and_skew_check(cluster)
        elif choice == "4":
            scenario_3_benchmark_query(cluster)
        elif choice == "5":
            scenario_4_oversharding_calculator()
        elif choice == "6":
            run_all_scenarios()
        elif choice == "0":
            cprint("Terima kasih telah menggunakan ES Sharding Lab Simulator!", Color.FG_GREEN)
            break
        else:
            cprint("Opsi tidak valid. Silakan pilih 0 - 6.", Color.FG_RED)

        input(f"\n{Color.DIM}Tekan [Enter] untuk melanjutkan...{Color.RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "--run-all", "-a"):
        run_all_scenarios()
    elif not sys.stdin.isatty():
        # Fallback automated run if executed in non-interactive environment (CI / pipe)
        run_all_scenarios()
    else:
        interactive_cli()
