#!/usr/bin/env python3
"""
=============================================================================
BAB 07: GRAPH THEORY & NETWORK TOPOLOGIES - LAB EXERCISE (MODUL 01)
Simulasi Interaktif Fondasi Graph: Traversal, Cycle Detection & Topo Sort
=============================================================================
"""

import sys
import time
import heapq
from collections import deque, defaultdict
from typing import Dict, List, Set, Tuple, Optional

# ANSI Color Codes for Rich Terminal Output
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"
BG_BLUE = "\033[44m"


class GraphSimulation:
    def __init__(self, directed: bool = False):
        self.directed = directed
        self.adj: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
        self.nodes: Set[str] = set()

    def add_edge(self, u: str, v: str, weight: int = 1) -> None:
        self.nodes.add(u)
        self.nodes.add(v)
        self.adj[u].append((v, weight))
        if not self.directed:
            self.adj[v].append((u, weight))

    def display_topology(self) -> None:
        print(f"\n{BOLD}{CYAN}=== STRUKTUR TOPOLOGI GRAPH ({'DIRECTED' if self.directed else 'UNDIRECTED'}) ==={RESET}")
        for node in sorted(self.nodes):
            neighbors = [f"{v}(w={w})" for v, w in self.adj[node]]
            neighbor_str = f"{YELLOW}, {RESET}".join(neighbors) if neighbors else f"{DIM}(isolated){RESET}"
            print(f"  {BOLD}{GREEN}[{node}]{RESET} -> {neighbor_str}")
        print()

    def simulate_bfs(self, start_node: str, delay: float = 0.05) -> List[str]:
        print(f"\n{BOLD}{BG_BLUE}{WHITE} SIMULASI: Breadth-First Search (BFS) dari Node '{start_node}' {RESET}\n")
        if start_node not in self.nodes:
            print(f"{RED}[ERROR] Node '{start_node}' tidak ditemukan dalam graph!{RESET}")
            return []

        visited: Set[str] = set([start_node])
        queue: deque = deque([(start_node, 0)])
        traversal_order: List[str] = []
        step = 1

        print(f"{DIM}{'Langkah':<8} | {'Queue Saat Ini':<25} | {'Node Aktif':<12} | {'Depth/Level':<10} | {'Visited Set'}{RESET}")
        print("-" * 80)

        while queue:
            q_repr = "[" + ", ".join(f"{n}(d={d})" for n, d in queue) + "]"
            curr, depth = queue.popleft()
            traversal_order.append(curr)

            print(f"{CYAN}{step:<8}{RESET} | {YELLOW}{q_repr:<25}{RESET} | {BOLD}{GREEN}{curr:<12}{RESET} | {depth:<10} | {list(visited)}")
            step += 1
            if delay > 0:
                time.sleep(delay)

            for neighbor, _ in self.adj[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        print(f"\n{BOLD}{GREEN}✓ BFS Selesai.{RESET} Urutan Eksplorasi: {BOLD}{' -> '.join(traversal_order)}{RESET}")
        return traversal_order

    def simulate_dfs(self, start_node: str, delay: float = 0.05) -> List[str]:
        print(f"\n{BOLD}{BG_BLUE}{WHITE} SIMULASI: Depth-First Search (DFS) dari Node '{start_node}' {RESET}\n")
        if start_node not in self.nodes:
            print(f"{RED}[ERROR] Node '{start_node}' tidak ditemukan dalam graph!{RESET}")
            return []

        visited: Set[str] = set()
        traversal_order: List[str] = []

        def _dfs_recursive(u: str, depth: int):
            visited.add(u)
            traversal_order.append(u)
            indent = "  " * depth
            print(f"{indent}{BOLD}{MAGENTA}↳ VISITING:{RESET} {BOLD}{GREEN}{u}{RESET} (Level {depth})")
            if delay > 0:
                time.sleep(delay)

            for v, _ in self.adj[u]:
                if v not in visited:
                    print(f"{indent}  {CYAN}Eksplorasi edge: {u} -> {v}{RESET}")
                    _dfs_recursive(v, depth + 1)
                else:
                    print(f"{indent}  {DIM}Back-edge/sudah dikunjungi: {u} -> {v}{RESET}")

        _dfs_recursive(start_node, 0)
        print(f"\n{BOLD}{GREEN}✓ DFS Selesai.{RESET} Urutan Kunjungan: {BOLD}{' -> '.join(traversal_order)}{RESET}")
        return traversal_order

    def simulate_kahn_topological_sort(self, delay: float = 0.05) -> List[str]:
        print(f"\n{BOLD}{BG_BLUE}{WHITE} SIMULASI: Kahn's Algorithm (Topological Sort / DAG) {RESET}\n")
        if not self.directed:
            print(f"{YELLOW}[WARN] Topo Sort hanya valid untuk Directed Acyclic Graph (DAG). Mengasumsikan directed.{RESET}")

        in_degree: Dict[str, int] = {node: 0 for node in self.nodes}
        for u in self.nodes:
            for v, _ in self.adj[u]:
                in_degree[v] += 1

        print(f"{BOLD}Derajat Masuk Awal (In-Degree Table):{RESET}")
        for node, deg in in_degree.items():
            print(f"  Node {BOLD}{node}{RESET}: in-degree = {YELLOW}{deg}{RESET}")

        zero_in_degree = deque([node for node, deg in in_degree.items() if deg == 0])
        topo_order: List[str] = []
        step = 1

        print(f"\n{'Step':<6} | {'Queue In-Degree=0':<25} | {'Node Diproses':<15} | {'In-Degree Update'}")
        print("-" * 80)

        while zero_in_degree:
            curr = zero_in_degree.popleft()
            topo_order.append(curr)

            updated = []
            for v, _ in self.adj[curr]:
                in_degree[v] -= 1
                updated.append(f"{v}->{in_degree[v]}")
                if in_degree[v] == 0:
                    zero_in_degree.append(v)

            update_str = ", ".join(updated) if updated else "none"
            q_str = "[" + ", ".join(zero_in_degree) + "]"
            print(f"{CYAN}{step:<6}{RESET} | {YELLOW}{q_str:<25}{RESET} | {BOLD}{GREEN}{curr:<15}{RESET} | {update_str}")
            step += 1
            if delay > 0:
                time.sleep(delay)

        if len(topo_order) == len(self.nodes):
            print(f"\n{BOLD}{GREEN}✓ Valid DAG! Urutan Topologi:{RESET} {BOLD}{' -> '.join(topo_order)}{RESET}")
        else:
            print(f"\n{BOLD}{RED}✗ Terdeteksi SIKLUS (Cycle Detected)! Topological sort tidak mungkin diselesaikan.{RESET}")
        return topo_order

    def detect_cycle_directed(self) -> bool:
        print(f"\n{BOLD}{BG_BLUE}{WHITE} SIMULASI: Deteksi Siklus (3-Color DFS State) {RESET}\n")
        # 0 = WHITE (unvisited), 1 = GRAY (processing/in current recursion stack), 2 = BLACK (visited)
        state: Dict[str, int] = {node: 0 for node in self.nodes}
        cycle_found = False

        def _dfs(u: str) -> bool:
            nonlocal cycle_found
            state[u] = 1 # GRAY
            print(f"  {YELLOW}State node '{u}' diubah ke GRAY (Active on stack){RESET}")

            for v, _ in self.adj[u]:
                if state[v] == 1:
                    print(f"  {BOLD}{RED}🚨 SIKLUS DITEMUKAN! Edge {u} -> {v} menunjuk ke node yang sedang aktif di stack!{RESET}")
                    cycle_found = True
                    return True
                elif state[v] == 0:
                    if _dfs(v):
                        return True

            state[u] = 2 # BLACK
            print(f"  {GREEN}State node '{u}' diubah ke BLACK (Selesai diproses){RESET}")
            return False

        for node in sorted(self.nodes):
            if state[node] == 0:
                if _dfs(node):
                    break

        print(f"\n{BOLD}Hasil Analisis Siklus:{RESET} {'Ada Siklus' if cycle_found else 'Acyclic (Tidak ada siklus)'}")
        return cycle_found

    def simulate_dijkstra(self, start_node: str, delay: float = 0.05) -> Dict[str, int]:
        print(f"\n{BOLD}{BG_BLUE}{WHITE} SIMULASI: Algoritma Dijkstra (Shortest Path) dari '{start_node}' {RESET}\n")
        distances: Dict[str, float] = {node: float('inf') for node in self.nodes}
        distances[start_node] = 0
        pq: List[Tuple[float, str]] = [(0, start_node)]
        predecessors: Dict[str, Optional[str]] = {node: None for node in self.nodes}

        print(f"{'Node Terpilih':<15} | {'Jarak Saat Ini':<15} | {'Relaksasi Tetangga':<35}")
        print("-" * 75)

        while pq:
            curr_dist, u = heapq.heappop(pq)
            if curr_dist > distances[u]:
                continue

            relaxed = []
            for v, weight in self.adj[u]:
                alt = curr_dist + weight
                if alt < distances[v]:
                    distances[v] = alt
                    predecessors[v] = u
                    heapq.heappush(pq, (alt, v))
                    relaxed.append(f"{v}(dist={alt})")

            relaxed_str = ", ".join(relaxed) if relaxed else "tidak ada update"
            print(f"{BOLD}{GREEN}{u:<15}{RESET} | {YELLOW}{curr_dist:<15}{RESET} | {CYAN}{relaxed_str}{RESET}")
            if delay > 0:
                time.sleep(delay)

        print(f"\n{BOLD}{GREEN}✓ Dijkstra Selesai.{RESET} Rangkuman Jarak Terpendek dari '{start_node}':")
        for node in sorted(self.nodes):
            dist = distances[node]
            path = []
            curr: Optional[str] = node
            while curr is not None:
                path.append(curr)
                curr = predecessors[curr]
            path_str = " -> ".join(reversed(path))
            print(f"  Target {BOLD}{node}{RESET}: Jarak = {BOLD}{YELLOW}{dist}{RESET} | Jalur: {path_str}")

        return {k: int(v) if v != float('inf') else -1 for k, v in distances.items()}


def create_sample_dag() -> GraphSimulation:
    dag = GraphSimulation(directed=True)
    # Course schedule / Task dependency DAG
    dag.add_edge("CS101", "CS201", 1)
    dag.add_edge("CS101", "MATH101", 1)
    dag.add_edge("CS201", "CS301", 1)
    dag.add_edge("MATH101", "CS301", 1)
    dag.add_edge("MATH101", "STAT201", 1)
    dag.add_edge("CS301", "THESIS", 1)
    dag.add_edge("STAT201", "THESIS", 1)
    return dag


def create_network_graph() -> GraphSimulation:
    net = GraphSimulation(directed=False)
    # Routing network topology with latency weights
    net.add_edge("Router_A", "Router_B", 4)
    net.add_edge("Router_A", "Router_C", 2)
    net.add_edge("Router_B", "Router_C", 1)
    net.add_edge("Router_B", "Router_D", 5)
    net.add_edge("Router_C", "Router_D", 8)
    net.add_edge("Router_C", "Router_E", 10)
    net.add_edge("Router_D", "Router_E", 2)
    net.add_edge("Router_D", "Router_F", 6)
    net.add_edge("Router_E", "Router_F", 3)
    return net


def create_cyclic_graph() -> GraphSimulation:
    cg = GraphSimulation(directed=True)
    cg.add_edge("A", "B", 1)
    cg.add_edge("B", "C", 1)
    cg.add_edge("C", "A", 1)  # creates cycle A->B->C->A
    cg.add_edge("C", "D", 1)
    return cg


def print_banner() -> None:
    print(f"{BOLD}{CYAN}" + "=" * 75)
    print(" 🌐 INTERACTIVE GRAPH THEORY & NETWORK TOPOLOGIES LAB (BAB 07)")
    print(" LeetCode Core Graph Foundations: BFS, DFS, TopoSort, Cycle, Dijkstra")
    print("=" * 75 + f"{RESET}\n")


def run_all_simulations(delay: float = 0.01) -> None:
    print_banner()

    print(f"{BOLD}{WHITE}--- SKENARIO 1: NETWORK TOPOLOGY (UNDIRECTED GRAPH) ---{RESET}")
    net = create_network_graph()
    net.display_topology()
    net.simulate_bfs("Router_A", delay=delay)
    net.simulate_dfs("Router_A", delay=delay)
    net.simulate_dijkstra("Router_A", delay=delay)

    print(f"\n{BOLD}{WHITE}--- SKENARIO 2: COURSE PREREQUISITES (DAG & KAHN'S ALGO) ---{RESET}")
    dag = create_sample_dag()
    dag.display_topology()
    dag.simulate_kahn_topological_sort(delay=delay)
    dag.detect_cycle_directed()

    print(f"\n{BOLD}{WHITE}--- SKENARIO 3: DEADLOCK DETECTION (CYCLIC GRAPH) ---{RESET}")
    cg = create_cyclic_graph()
    cg.display_topology()
    cg.detect_cycle_directed()
    cg.simulate_kahn_topological_sort(delay=delay)

    print(f"\n{BOLD}{GREEN}✓ Seluruh modul simulasi graph berhasil dieksekusi dengan sukses!{RESET}\n")


def main() -> None:
    # Support automated test / non-interactive CI run
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--demo", "--non-interactive"):
        run_all_simulations(delay=0.0)
        return

    # Check if stdin is a TTY for interactive mode
    if not sys.stdin.isatty():
        run_all_simulations(delay=0.0)
        return

    print_banner()
    while True:
        print(f"\n{BOLD}Menu Pilihan Simulasi:{RESET}")
        print("  1. Visualisasi Topologi & BFS Traversal")
        print("  2. Visualisasi Topologi & DFS Traversal (Recursive Tree)")
        print("  3. Shortest Path Network Routing (Dijkstra Min-Heap)")
        print("  4. Dependency Resolution / Topo Sort (Kahn's Algorithm)")
        print("  5. Deteksi Siklus Dependensi (Cycle Detection 3-Color)")
        print("  6. Jalankan Semua Skenario Sekaligus (Automated Walkthrough)")
        print("  0. Keluar")

        try:
            choice = input(f"\n{BOLD}{CYAN}Pilih opsi [0-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice == "0":
            print(f"{GREEN}Terima kasih telah bereksperimen di Graph Theory Lab!{RESET}")
            break
        elif choice == "1":
            net = create_network_graph()
            net.display_topology()
            net.simulate_bfs("Router_A", delay=0.1)
        elif choice == "2":
            net = create_network_graph()
            net.display_topology()
            net.simulate_dfs("Router_A", delay=0.1)
        elif choice == "3":
            net = create_network_graph()
            net.display_topology()
            net.simulate_dijkstra("Router_A", delay=0.08)
        elif choice == "4":
            dag = create_sample_dag()
            dag.display_topology()
            dag.simulate_kahn_topological_sort(delay=0.1)
        elif choice == "5":
            cg = create_cyclic_graph()
            cg.display_topology()
            cg.detect_cycle_directed()
        elif choice == "6":
            run_all_simulations(delay=0.03)
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")


if __name__ == "__main__":
    main()
