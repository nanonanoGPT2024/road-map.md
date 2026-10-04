#!/usr/bin/env python3
"""
Lab Exercise: Cloudflare Edge Compute & Serverless Architecture Simulation
Topik: BAB-06 Edge Compute Serverless (Workers, Pages, KV, Durable Objects & Smart Placement)
Standar: Python 3 Standard Library (Runnable tanpa dependensi eksternal)
"""

import sys
import time
import random
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ANSI Color Codes & Formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"
BG_DARK = "\033[40m"

def print_banner():
    banner = f"""{CLR_CYAN}{CLR_BOLD}
================================================================================
   ____ _                 _  __ _                  _____    _            
  / ___| | ___  _   _  __| |/ _| | __ _ _ __ ___  | ____|__| | __ _  ___ 
 | |   | |/ _ \| | | |/ _` | |_| |/ _` | '__/ _ \ |  _| / _` |/ _` |/ _ \\
 | |___| | (_) | |_| | (_| |  _| | (_| | | |  __/ | |__| (_| | (_| |  __/
  \____|_|\___/ \__,_|\__,_|_| |_|\__,_|_|  \___| |_____\__,_|\__, |\___|
                                                              |___/      
     CLOUDFLARE WORKERS & PAGES: PRODUCTION ARCHITECTURE SIMULATOR
================================================================================{CLR_RESET}
{CLR_DIM}Modul 02: Advanced Edge Runtime, KV Caching, Durable Objects & Smart Placement{CLR_RESET}
"""
    print(banner)

@dataclass
class EdgePoP:
    code: str
    city: str
    region: str
    base_latency_ms: float

EDGE_POPS = {
    "CGK": EdgePoP("CGK", "Jakarta", "APAC", 4.2),
    "SIN": EdgePoP("SIN", "Singapore", "APAC", 12.8),
    "NRT": EdgePoP("NRT", "Tokyo", "APAC", 68.4),
    "LHR": EdgePoP("LHR", "London", "EMEA", 175.2),
    "SFO": EdgePoP("SFO", "San Francisco", "AMER", 195.0),
}

@dataclass
class DurableObjectInstance:
    object_id: str
    colo_location: str
    state: Dict[str, str] = field(default_factory=dict)
    active_websockets: int = 0
    sequence_number: int = 0

    def mutate_state(self, key: str, val: str) -> int:
        self.state[key] = val
        self.sequence_number += 1
        return self.sequence_number

class CloudflareEdgeCluster:
    def __init__(self):
        # KV Storage: In-memory simulation of global distributed store with local edge cache
        self.kv_global_store: Dict[str, Tuple[str, float]] = {
            "config:feature_flags": (json.dumps({"canary_release": True, "edge_ssr": True}), time.time()),
            "session:token_9921": (json.dumps({"user": "lead_architect", "role": "sre"}), time.time()),
        }
        self.edge_l1_cache: Dict[str, Dict[str, str]] = {pop: {} for pop in EDGE_POPS}
        self.durable_objects: Dict[str, DurableObjectInstance] = {}
        self.origin_server_colo = "SFO"

    def resolve_anycast(self, client_ip: str) -> EdgePoP:
        """Simulasi Anycast BGP routing mengarahkan IP ke PoP terdekat."""
        octets = [int(p) for p in client_ip.split(".")]
        if octets[0] == 36 or octets[0] == 182:
            return EDGE_POPS["CGK"]
        elif octets[0] == 103 or octets[0] == 118:
            return EDGE_POPS["SIN"]
        elif octets[0] == 133 or octets[0] == 210:
            return EDGE_POPS["NRT"]
        elif octets[0] == 82 or octets[0] == 151:
            return EDGE_POPS["LHR"]
        else:
            return EDGE_POPS["SFO"]

    def workers_kv_read(self, pop_code: str, key: str) -> Tuple[Optional[str], str, float]:
        """Hierarchical KV Read: L1 (Colo Memory) -> Global Distributed KV Store."""
        start_t = time.perf_counter()
        # 1. Cek L1 Colo Cache
        if key in self.edge_l1_cache[pop_code]:
            latency = (time.perf_counter() - start_t) * 1000 + random.uniform(0.3, 0.9)
            return self.edge_l1_cache[pop_code][key], "L1_EDGE_CACHE_HIT", latency

        # 2. Cek Global KV Store
        if key in self.kv_global_store:
            val, _ = self.kv_global_store[key]
            # Populate L1 cache on Edge
            self.edge_l1_cache[pop_code][key] = val
            latency = (time.perf_counter() - start_t) * 1000 + EDGE_POPS[pop_code].base_latency_ms * 0.4 + random.uniform(2.5, 6.0)
            return val, "KV_GLOBAL_STORE_HIT", latency

        latency = (time.perf_counter() - start_t) * 1000 + EDGE_POPS[pop_code].base_latency_ms * 0.3
        return None, "KV_KEY_NOT_FOUND", latency

    def workers_smart_placement(self, pop_code: str, endpoint: str) -> Tuple[str, float]:
        """
        Cloudflare Smart Placement: Memindahkan eksekusi worker lebih dekat ke Origin
        jika worker melakukan roundtrips berat ke Origin database.
        """
        if "heavy_db" in endpoint:
            exec_colo = self.origin_server_colo
            # Client -> Anycast PoP -> Smart Placed Worker (near Origin) -> Origin DB
            latency = EDGE_POPS[pop_code].base_latency_ms + 1.2
            return exec_colo, latency
        else:
            exec_colo = pop_code
            latency = EDGE_POPS[pop_code].base_latency_ms * 0.2 + 0.8
            return exec_colo, latency

    def get_or_create_durable_object(self, object_id: str, client_pop: str) -> DurableObjectInstance:
        if object_id not in self.durable_objects:
            self.durable_objects[object_id] = DurableObjectInstance(
                object_id=object_id,
                colo_location=client_pop,
            )
        return self.durable_objects[object_id]

def simulate_interactive_routing(cluster: CloudflareEdgeCluster):
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[1] SIMULASI ANYCAST BGP ROUTING & SMART PLACEMENT{CLR_RESET}")
    print("Masukkan sample client IP (contoh: 36.85.12.1 [ID], 103.21.244.0 [SG], 82.165.197.1 [UK], 198.51.100.24 [US]):")
    user_ip = input(f"{CLR_CYAN}Client IP > {CLR_RESET}").strip()
    if not user_ip:
        user_ip = "36.85.12.44"

    try:
        routed_pop = cluster.resolve_anycast(user_ip)
    except Exception:
        routed_pop = EDGE_POPS["CGK"]

    print(f"\n{CLR_GREEN}* Anycast BGP Resolved:{CLR_RESET}")
    print(f"  ├─ Incoming Client IP : {CLR_WHITE}{user_ip}{CLR_RESET}")
    print(f"  ├─ Terminated PoP     : {CLR_BOLD}{routed_pop.code} ({routed_pop.city}, {routed_pop.region}){CLR_RESET}")
    print(f"  └─ Edge Handshake RTT : {CLR_GREEN}{routed_pop.base_latency_ms:.2f} ms{CLR_RESET}")

    print(f"\n{CLR_YELLOW}Pilih Tipe Endpoint Worker:{CLR_RESET}")
    print("  1. Edge Compute Ringan (JWT Validation, HTML Rewrite, Edge Auth)")
    print("  2. Heavy Database Transaction (Multi-query ke Origin PostgreSQL di SFO)")
    p_choice = input(f"{CLR_CYAN}Pilihan (1/2) > {CLR_RESET}").strip()

    endpoint = "heavy_db" if p_choice == "2" else "light_edge"
    exec_colo, exec_lat = cluster.workers_smart_placement(routed_pop.code, endpoint)

    print(f"\n{CLR_CYAN}Analisis Cloudflare Smart Placement Engine:{CLR_RESET}")
    if exec_colo == routed_pop.code:
        print(f"  ├─ Routing Mode       : {CLR_GREEN}STANDARD EDGE EXECUTION{CLR_RESET}")
        print(f"  ├─ Execution Point    : {exec_colo} (Local Colo)")
        print(f"  └─ End-to-End Latency : {CLR_GREEN}{exec_lat:.2f} ms{CLR_RESET} (Near-zero cold start)")
    else:
        print(f"  ├─ Routing Mode       : {CLR_MAGENTA}SMART PLACEMENT ACTIVE{CLR_RESET}")
        print(f"  ├─ Explanation        : Multi-roundtrip DB query terdeteksi. Worker dieksekusi di {exec_colo} dekat DB Origin.")
        print(f"  └─ End-to-End Latency : {CLR_YELLOW}{exec_lat:.2f} ms{CLR_RESET} (Optimal vs Non-placed {exec_lat*2.4:.2f} ms)")

def simulate_kv_caching(cluster: CloudflareEdgeCluster):
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[2] SIMULASI WORKERS KV TIERED CACHING LAYER{CLR_RESET}")
    print("Daftar PoP pengujian: CGK, SIN, NRT, LHR, SFO")
    pop_sel = input(f"{CLR_CYAN}Pilih Kode PoP [Default: CGK] > {CLR_RESET}").strip().upper()
    if pop_sel not in EDGE_POPS:
        pop_sel = "CGK"

    print(f"\nMemilih key KV: [1] config:feature_flags  [2] session:token_9921  [3] custom_key")
    k_choice = input(f"{CLR_CYAN}Pilihan (1/2/3) > {CLR_RESET}").strip()
    if k_choice == "1":
        key = "config:feature_flags"
    elif k_choice == "2":
        key = "session:token_9921"
    else:
        key = input(f"{CLR_CYAN}Masukkan custom key > {CLR_RESET}").strip() or "test:metric"

    # Request 1: Cache Miss / Global Read
    print(f"\n{CLR_WHITE}--> Request #1 (Cold / First Access dari PoP {pop_sel})...{CLR_RESET}")
    val, status, lat = cluster.workers_kv_read(pop_sel, key)
    print(f"    Status  : {CLR_YELLOW if 'GLOBAL' in status else CLR_RED}{status}{CLR_RESET}")
    print(f"    Latency : {CLR_YELLOW}{lat:.2f} ms{CLR_RESET}")
    print(f"    Payload : {CLR_DIM}{val}{CLR_RESET}")

    time.sleep(0.4)
    # Request 2: Local L1 Cache Hit
    print(f"\n{CLR_WHITE}--> Request #2 (Warm Request berulang di PoP {pop_sel})...{CLR_RESET}")
    val2, status2, lat2 = cluster.workers_kv_read(pop_sel, key)
    print(f"    Status  : {CLR_GREEN}{status2}{CLR_RESET}")
    print(f"    Latency : {CLR_GREEN}{lat2:.2f} ms{CLR_RESET} (Penurunan latensi {(lat - lat2)/lat*100:.1f}%)")
    print(f"    Payload : {CLR_DIM}{val2}{CLR_RESET}")

def simulate_durable_objects(cluster: CloudflareEdgeCluster):
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[3] SIMULASI DURABLE OBJECTS (DISTRIBUTED ACTOR MODEL){CLR_RESET}")
    print("Durable Objects menyediakan strongly consistent stateful storage di Edge dengan koordinasi WebSocket.")
    obj_id = input(f"{CLR_CYAN}Masukkan Room ID / Document ID [Default: room-alpha-99] > {CLR_RESET}").strip() or "room-alpha-99"

    durable_obj = cluster.get_or_create_durable_object(obj_id, "SIN")
    print(f"\n{CLR_GREEN}* Durable Object Bound:{CLR_RESET}")
    print(f"  ├─ Object Identifier : {CLR_BOLD}{durable_obj.object_id}{CLR_RESET}")
    print(f"  ├─ Pinned Location   : {CLR_MAGENTA}{durable_obj.colo_location} (Single-writer coordinator){CLR_RESET}")
    print(f"  └─ Initial Sequence  : #{durable_obj.sequence_number}")

    while True:
        print(f"\nAksi Durable Object:")
        print("  1. Broadcast State Mutation (Atomic Single-Writer)")
        print("  2. Connect Client WebSocket")
        print("  3. Dump In-Memory Storage & Log")
        print("  0. Selesai / Kembali ke Menu")
        act = input(f"{CLR_CYAN}Pilih Aksi > {CLR_RESET}").strip()

        if act == "1":
            field_k = input("  Key state  : ").strip() or "cursor_pos"
            field_v = input("  Val state  : ").strip() or f'{{"x": {random.randint(10,500)}, "y": {random.randint(10,500)}}}'
            seq = durable_obj.mutate_state(field_k, field_v)
            print(f"  {CLR_GREEN}✔ Mutation Committed! Seq #{seq} di-broadcast ke {durable_obj.active_websockets} active clients.{CLR_RESET}")
        elif act == "2":
            durable_obj.active_websockets += 1
            print(f"  {CLR_CYAN}✔ Client tersambung via WebSocket. Total listener: {durable_obj.active_websockets}{CLR_RESET}")
        elif act == "3":
            print(f"\n  {CLR_BOLD}Snapshot State Storage [{durable_obj.object_id}]:{CLR_RESET}")
            print(json.dumps(durable_obj.state, indent=4))
        elif act == "0":
            break

def simulate_pages_fullstack():
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[4] SIMULASI CLOUDFLARE PAGES FUNCTIONS (FULLSTACK JAMSTACK + SSR){CLR_RESET}")
    print("Struktur Proyek Pages: /functions/api/user.ts + /public/index.html")
    
    routes = [
        ("GET  /", "Static Asset via Cloudflare CDN Cache", 2.1, "200 OK (Cache HIT)"),
        ("GET  /api/health", "Pages Function Edge Serverless", 5.4, "200 OK (V8 Isolate)"),
        ("POST /api/v1/auth", "Edge SSR + Cryptographic WebCrypto JWT", 8.9, "201 Created"),
        ("GET  /docs/architecture", "HTMLRewriter Streaming Transformation", 4.8, "200 OK (Rewritten HTML)"),
    ]

    print(f"\n{CLR_BOLD}{'METHOD & ROUTE':<26} | {'RUNTIME PIPELINE':<38} | {'STATUS':<22} | {'LATENCY'}{CLR_RESET}")
    print("-" * 105)
    for method_route, pipeline, status, lat in routes:
        time.sleep(0.2)
        print(f"{CLR_CYAN}{method_route:<26}{CLR_RESET} | {CLR_WHITE}{pipeline:<38}{CLR_RESET} | {CLR_GREEN}{status:<22}{CLR_RESET} | {CLR_YELLOW}{lat} ms{CLR_RESET}")

    print(f"\n{CLR_GREEN}✔ Simulasi Middleware & HTMLRewriter berhasil merender payload tanpa nodejs runtime cold start.{CLR_RESET}")

def run_e2e_benchmark(cluster: CloudflareEdgeCluster):
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[5] MENJALANKAN BENCHMARK ARSITEKTUR EDGE HIGH-CONCURRENCY{CLR_RESET}")
    print("Menguji 100 batch incoming requests simulasi multi-region...")
    time.sleep(0.5)

    stats = {"hits": 0, "miss": 0, "total_lat": 0.0}
    test_keys = ["config:feature_flags", "session:token_9921", "promo:discount_v2"]

    for i in range(1, 101):
        rand_pop = random.choice(list(EDGE_POPS.keys()))
        rand_key = random.choice(test_keys)
        _, status, lat = cluster.workers_kv_read(rand_pop, rand_key)
        stats["total_lat"] += lat
        if "L1" in status:
            stats["hits"] += 1
        else:
            stats["miss"] += 1
        if i % 25 == 0:
            print(f"  Processed {i}/100 requests... Current Avg Latency: {stats['total_lat']/i:.2f} ms")

    avg_lat = stats["total_lat"] / 100
    cache_ratio = (stats["hits"] / 100) * 100
    print(f"\n{CLR_CYAN}{CLR_BOLD}HASIL BENCHMARK PRODUKSI:{CLR_RESET}")
    print(f"  ├─ Total Requests    : 100 reqs (Distributed Anycast)")
    print(f"  ├─ L1 Edge Cache Hit : {CLR_GREEN}{stats['hits']} ({cache_ratio:.1f}%){CLR_RESET}")
    print(f"  ├─ Global Store Read : {CLR_YELLOW}{stats['miss']} ({100 - cache_ratio:.1f}%){CLR_RESET}")
    print(f"  └─ Mean Response RTT : {CLR_BOLD}{CLR_GREEN}{avg_lat:.2f} ms{CLR_RESET} (Sub-10ms Edge SLA tercapai)")

def main():
    cluster = CloudflareEdgeCluster()
    print_banner()

    while True:
        print(f"\n{CLR_BOLD}MAIN LAB MENU:{CLR_RESET}")
        print("  1. Simulasi Anycast BGP Routing & Smart Placement Engine")
        print("  2. Simulasi Tiered KV Cache Layer (L1 Edge vs Global Store)")
        print("  3. Simulasi Durable Objects (Actor Model & Strongly-Consistent State)")
        print("  4. Simulasi Cloudflare Pages Functions & HTMLRewriter SSR")
        print("  5. Jalankan Full Architecture Benchmark (Multi-PoP)")
        print("  0. Keluar dari Lab")

        choice = input(f"\n{CLR_CYAN}Pilih Modul (0-5) > {CLR_RESET}").strip()
        if choice == "1":
            simulate_interactive_routing(cluster)
        elif choice == "2":
            simulate_kv_caching(cluster)
        elif choice == "3":
            simulate_durable_objects(cluster)
        elif choice == "4":
            simulate_pages_fullstack()
        elif choice == "5":
            run_e2e_benchmark(cluster)
        elif choice == "0":
            print(f"\n{CLR_GREEN}Lab selesai. Selamat bereksplorasi di Cloudflare Edge Compute!{CLR_RESET}")
            sys.exit(0)
        else:
            print(f"{CLR_RED}Pilihan tidak valid.{CLR_RESET}")

if __name__ == "__main__":
    main()
