#!/usr/bin/env python3
"""
Lab Hands-on: Graph Theory & Network Topologies - Module 02 Deep Dive
Focus: Distributed Network Fault-Tolerance, Bridge Detection (Tarjan's Algorithm / LC 1192),
       and Optimal Routing with Min-Heap Dijkstra (Network Delay Time / LC 743).
"""

import sys
import time
import heapq
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional

# --- Terminal ANSI Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_BG_DARK = "\033[100m"


class NetworkTopology:
    """
    Represents an enterprise distributed network mesh.
    Supports fault-tolerance auditing, bridge detection, and deterministic routing.
    """

    def __init__(self) -> None:
        self.adj: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        self.nodes: Set[str] = set()

    def add_link(self, u: str, v: str, latency_ms: float, bidirectional: bool = True) -> None:
        """Menambahkan tautan transmisi antar node dengan bobot latensi."""
        self.adj[u].append((v, latency_ms))
        self.nodes.add(u)
        self.nodes.add(v)
        if bidirectional:
            self.adj[v].append((u, latency_ms))

    def remove_link(self, u: str, v: str) -> bool:
        """Menghapus tautan transmisi (simulasi link failure)."""
        removed = False
        if u in self.adj:
            orig_len = len(self.adj[u])
            self.adj[u] = [edge for edge in self.adj[u] if edge[0] != v]
            if len(self.adj[u]) < orig_len:
                removed = True
        if v in self.adj:
            self.adj[v] = [edge for edge in self.adj[v] if edge[0] != u]
        return removed

    def find_critical_links(self) -> List[Tuple[str, str]]:
        """
        Deteksi Single Point of Failure (SPOF) menggunakan Algoritma Tarjan (Bridges in Graph - LC 1192).
        Kompleksitas: O(V + E) waktu, O(V) memori stack & metadata.
        """
        discovery_time: Dict[str, int] = {}
        low_reach: Dict[str, int] = {}
        visited: Set[str] = set()
        bridges: List[Tuple[str, str]] = []
        timer = 0

        def dfs(curr: str, parent: Optional[str] = None) -> None:
            nonlocal timer
            visited.add(curr)
            discovery_time[curr] = low_reach[curr] = timer
            timer += 1

            for neighbor, _ in self.adj[curr]:
                if neighbor == parent:
                    continue

                if neighbor in visited:
                    # Back-edge ditemukan: update nilai reach terendah
                    low_reach[curr] = min(low_reach[curr], discovery_time[neighbor])
                else:
                    # Forward tree edge
                    dfs(neighbor, curr)
                    low_reach[curr] = min(low_reach[curr], low_reach[neighbor])
                    
                    # Kondisi bridge: tetangga tidak memiliki back-edge ke ancestor curr
                    if low_reach[neighbor] > discovery_time[curr]:
                        bridges.append((curr, neighbor))

        for node in list(self.nodes):
            if node not in visited:
                dfs(node, None)

        return bridges

    def route_dijkstra(self, source: str, destination: str) -> Tuple[float, List[str]]:
        """
        Kalkulasi jalur terpendek berbasis latensi menggunakan Min-Heap (LC 743).
        Kompleksitas: O(E log V).
        """
        if source not in self.nodes or destination not in self.nodes:
            return float("inf"), []

        # min_heap tuple: (accumulated_latency, current_node, path)
        pq: List[Tuple[float, str, List[str]]] = [(0.0, source, [source])]
        min_cost: Dict[str, float] = {node: float("inf") for node in self.nodes}
        min_cost[source] = 0.0

        while pq:
            curr_lat, curr_node, path = heapq.heappop(pq)

            if curr_node == destination:
                return curr_lat, path

            if curr_lat > min_cost[curr_node]:
                continue

            for neighbor, weight in self.adj[curr_node]:
                new_cost = curr_lat + weight
                if new_cost < min_cost[neighbor]:
                    min_cost[neighbor] = new_cost
                    heapq.heappush(pq, (new_cost, neighbor, path + [neighbor]))

        return float("inf"), []

    def compute_broadcast_convergence(self, source: str) -> Tuple[float, bool]:
        """
        Menghitung waktu propagasi paket ke seluruh node jaringan (Broadcast Delay).
        Mengembalikan (maksimum latensi, apakah seluruh node terjangkau).
        """
        distances: Dict[str, float] = {node: float("inf") for node in self.nodes}
        distances[source] = 0.0
        pq: List[Tuple[float, str]] = [(0.0, source)]

        while pq:
            d, u = heapq.heappop(pq)
            if d > distances[u]:
                continue
            for v, weight in self.adj[u]:
                if distances[u] + weight < distances[v]:
                    distances[v] = distances[u] + weight
                    heapq.heappush(pq, (distances[v], v))

        max_latency = max(distances.values())
        is_fully_connected = max_latency != float("inf")
        return max_latency, is_fully_connected


def print_banner() -> None:
    print(f"{CLR_CYAN}{CLR_BOLD}" + "=" * 78)
    print("  NETWORK TOPOLOGY DIAGNOSTICS & FAULT AUDIT (LEETCODE 1192 & 743 ENGINE)")
    print("=" * 78 + f"{CLR_RESET}")


def run_laboratory() -> None:
    print_banner()

    topo = NetworkTopology()

    # Inisialisasi Topologi Jaringan Multiregion
    links = [
        ("DC-US-EAST", "CORE-R1", 12.5),
        ("CORE-R1", "CORE-R2", 8.2),
        ("CORE-R2", "DC-US-WEST", 15.0),
        ("DC-US-EAST", "CORE-R2", 22.0),     # Redundant mesh loop
        ("CORE-R1", "TRANSIT-HUB", 35.0),    # Single bottleneck link
        ("TRANSIT-HUB", "EDGE-EU-1", 45.0),
        ("EDGE-EU-1", "DC-EU-CENTRAL", 10.1),
        ("TRANSIT-HUB", "EDGE-EU-2", 48.0),
        ("EDGE-EU-2", "DC-EU-CENTRAL", 9.8), # EU redundant loop
    ]

    print(f"\n{CLR_BOLD}[1] Membangun Topologi Mesh Multi-Region...{CLR_RESET}")
    start_t = time.perf_counter_ns()
    for u, v, lat in links:
        topo.add_link(u, v, lat)
    build_time = (time.perf_counter_ns() - start_t) / 1000.0

    print(f"    Total Nodes : {CLR_GREEN}{len(topo.nodes)}{CLR_RESET}")
    print(f"    Total Edges : {CLR_GREEN}{len(links)}{CLR_RESET}")
    print(f"    Build Time  : {CLR_YELLOW}{build_time:.2f} µs{CLR_RESET}")

    # Step 2: Deteksi Critical Connections (Bridges)
    print(f"\n{CLR_BOLD}[2] Menjalankan Analisis SPOF (Tarjan's Bridge Detection - LC 1192)...{CLR_RESET}")
    start_t = time.perf_counter_ns()
    bridges = topo.find_critical_links()
    tarjan_time = (time.perf_counter_ns() - start_t) / 1000.0

    if bridges:
        print(f"    {CLR_RED}PERINGATAN: Ditemukan {len(bridges)} Critical Link (Bridge)!{CLR_RESET}")
        for b_u, b_v in bridges:
            print(f"      -> [{CLR_YELLOW}{b_u}{CLR_RESET}] <===> [{CLR_YELLOW}{b_v}{CLR_RESET}] (Pemutusan link ini memecah topologi!)")
    else:
        print(f"    {CLR_GREEN}Topologi 2-Edge-Connected: Tidak ada SPOF.{CLR_RESET}")
    print(f"    Tarjan Exec Time: {CLR_CYAN}{tarjan_time:.2f} µs{CLR_RESET}")

    # Step 3: Dijkstra Shortest Path Latency Calculation (LC 743)
    src_node = "DC-US-EAST"
    dst_node = "DC-EU-CENTRAL"
    print(f"\n{CLR_BOLD}[3] Routing Optimal Jalur Kritis ({src_node} -> {dst_node})...{CLR_RESET}")
    
    latency, path = topo.route_dijkstra(src_node, dst_node)
    path_str = f" {CLR_CYAN}->{CLR_RESET} ".join(path)
    print(f"    Jalur Tercepat : {path_str}")
    print(f"    Total Latensi  : {CLR_GREEN}{latency:.2f} ms{CLR_RESET}")

    # Step 4: Broadcast Convergence Matrix
    max_lat, fully_conn = topo.compute_broadcast_convergence(src_node)
    print(f"\n{CLR_BOLD}[4] Simulasi Broadcast Convergence (Root: {src_node})...{CLR_RESET}")
    print(f"    Status Keterjangkauan: {'Lengkap' if fully_conn else 'Terisolasi'}")
    print(f"    Waktu Konvergensi    : {CLR_YELLOW}{max_lat:.2f} ms{CLR_RESET}")

    # Step 5: Simulasi Kegagalan Jaringan (Link Failure Injection)
    if bridges:
        crit_u, crit_v = bridges[0]
        print(f"\n{CLR_BOLD}[5] INJEKSI KEGAGALAN: Memutus Critical Link ({crit_u} -- {crit_v})...{CLR_RESET}")
        topo.remove_link(crit_u, crit_v)

        # Uji ulang routing
        new_latency, new_path = topo.route_dijkstra(src_node, dst_node)
        _, new_conn = topo.compute_broadcast_convergence(src_node)

        if new_latency == float("inf"):
            print(f"    Status Rute {src_node} -> {dst_node}: {CLR_RED}UNREACHABLE (Network Partitioned){CLR_RESET}")
        else:
            print(f"    Rute Alternatif Ditemukan: {' -> '.join(new_path)} ({new_latency} ms)")

        print(f"    Status Jaringan Keseluruhan : {CLR_RED if not new_conn else CLR_GREEN}"
              f"{'TERPARTISI (Subnet Terisolasi)' if not new_conn else 'Toleran'}{CLR_RESET}")

    print(f"\n{CLR_CYAN}{CLR_BOLD}" + "=" * 78)
    print("  SIMULASI DIAGNOSTIK SELESAI SECARA DETERMINISTIK.")
    print("=" * 78 + f"{CLR_RESET}\n")


if __name__ == "__main__":
    run_laboratory()