#!/usr/bin/env python3
"""
Laboratorium Mandiri: Fondasi Graf dan Algoritma Traversal (BFS & DFS)
Topik: Representasi Graf, Traversal Breadth-First Search, Depth-First Search,
       Deteksi Siklus, dan Penentuan Jalur Terpendek pada Graf Tanpa Bobot.

Mendukung eksekusi interaktif terminal dengan warna ANSI.
"""

from collections import deque
import sys
import time

# ==========================================
# ANSI Color Codes untuk visualisasi terminal
# ==========================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[31m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


class Graph:
    """
    Struktur data Graf menggunakan Representasi Adjacency List.
    Mendukung graf berarah (directed) maupun tak berarah (undirected).
    """

    def __init__(self, directed: bool = False):
        self.adj = {}
        self.directed = directed

    def add_vertex(self, u: str) -> None:
        if u not in self.adj:
            self.adj[u] = []

    def add_edge(self, u: str, v: str) -> None:
        self.add_vertex(u)
        self.add_vertex(v)
        if v not in self.adj[u]:
            self.adj[u].append(v)
        if not self.directed:
            if u not in self.adj[v]:
                self.adj[v].append(u)

    def display_adj_list(self) -> None:
        print(f"\n{BOLD}{CYAN}=== Representasi Adjacency List ==={RESET}")
        for vertex in sorted(self.adj.keys()):
            neighbors = ", ".join(f"{GREEN}{nbr}{RESET}" for nbr in self.adj[vertex])
            print(f"  {BOLD}{YELLOW}{vertex}{RESET} -> [{neighbors}]")
        print()

    def bfs(self, start_node: str, delay: float = 0.05) -> tuple[list[str], dict[str, int], dict[str, str | None]]:
        """
        Breadth-First Search (BFS) menggunakan Queue FIFO.
        Mengembalikan: (urutan_kunjungan, jarak_dari_start, parent_map)
        """
        if start_node not in self.adj:
            print(f"{RED}[Error] Simpul {start_node} tidak ditemukan dalam graf!{RESET}")
            return [], {}, {}

        visited = set([start_node])
        queue = deque([start_node])
        order = []
        distance = {start_node: 0}
        parent = {start_node: None}

        print(f"\n{BOLD}{BLUE}--- Memulai Breadth-First Search (BFS) dari '{start_node}' ---{RESET}")
        print(f"{DIM}Menggunakan antrean FIFO (First-In First-Out) untuk penjelajahan level per level.{RESET}\n")

        step = 1
        while queue:
            curr = queue.popleft()
            order.append(curr)

            q_state = "[" + ", ".join(f"{CYAN}{n}{RESET}" for n in queue) + "]"
            print(f"  {BOLD}Langkah {step:02d}:{RESET} Kunjungi {GREEN}{BOLD}{curr}{RESET} "
                  f"(Jarak: {distance[curr]}) | Antrean Sisa: {q_state}")

            for neighbor in sorted(self.adj[curr]):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = curr
                    distance[neighbor] = distance[curr] + 1
                    queue.append(neighbor)
                    print(f"    {DIM}--> Temukan tetangga belum dikunjungi: {YELLOW}{neighbor}{RESET}{DIM} "
                          f"(Enqueued, Jarak={distance[neighbor]}){RESET}")

            step += 1
            if delay > 0:
                time.sleep(delay)

        return order, distance, parent

    def dfs(self, start_node: str, delay: float = 0.05) -> list[str]:
        """
        Depth-First Search (DFS) menggunakan Stack (Rekursif).
        Menelusuri cabang sedalam mungkin sebelum backtracking.
        """
        if start_node not in self.adj:
            print(f"{RED}[Error] Simpul {start_node} tidak ditemukan dalam graf!{RESET}")
            return []

        visited = set()
        order = []
        entry_time = {}
        exit_time = {}
        timer = [0]

        print(f"\n{BOLD}{MAGENTA}--- Memulai Depth-First Search (DFS) dari '{start_node}' ---{RESET}")
        print(f"{DIM}Menelusuri setiap cabang hingga ujung terdalam sebelum melakukan backtrack.{RESET}\n")

        def _dfs_visit(u: str, depth: int = 0):
            timer[0] += 1
            entry_time[u] = timer[0]
            visited.add(u)
            order.append(u)

            indent = "  " * (depth + 1)
            print(f"{indent}{BOLD}-> Discover {MAGENTA}{u}{RESET} [t_masuk={entry_time[u]}]")
            if delay > 0:
                time.sleep(delay)

            for v in sorted(self.adj[u]):
                if v not in visited:
                    _dfs_visit(v, depth + 1)
                else:
                    if v != u and v not in exit_time:
                        print(f"{indent}  {YELLOW}[Back-Edge terdeteksi: {u} -> {v}]{RESET}")

            timer[0] += 1
            exit_time[u] = timer[0]
            print(f"{indent}{DIM}<- Backtrack dari {u} [t_selesai={exit_time[u]}]{RESET}")

        _dfs_visit(start_node)
        return order

    def find_shortest_path_bfs(self, start: str, target: str) -> list[str] | None:
        """
        Mencari rute/jalur terpendek (hop minimum) pada graf tanpa bobot via BFS.
        """
        _, _, parent = self.bfs(start, delay=0.0)
        if target not in parent and target != start:
            return None

        path = []
        curr = target
        while curr is not None:
            path.append(curr)
            curr = parent.get(curr)
        path.reverse()
        return path

    def detect_cycle_undirected(self) -> bool:
        """
        Mendeteksi keberadaan siklus pada graf tak-berarah menggunakan DFS traversal.
        """
        visited = set()

        def _has_cycle(u: str, p: str | None) -> bool:
            visited.add(u)
            for v in self.adj[u]:
                if v not in visited:
                    if _has_cycle(v, u):
                        return True
                elif v != p:
                    # Menemukan simpul tetangga yang sudah dikunjungi dan bukan parent
                    return True
            return False

        for node in self.adj:
            if node not in visited:
                if _has_cycle(node, None):
                    return True
        return False


def build_sample_network() -> Graph:
    """Membangun topologi graf contoh (Simulasi Jaringan Server Kampus)."""
    g = Graph(directed=False)
    edges = [
        ("Router-A", "Server-1"),
        ("Router-A", "Router-B"),
        ("Router-A", "Gateway"),
        ("Router-B", "Server-2"),
        ("Router-B", "Router-C"),
        ("Router-C", "Database"),
        ("Gateway", "Firewall"),
        ("Firewall", "Server-2"),
    ]
    for u, v in edges:
        g.add_edge(u, v)
    return g


def print_banner() -> None:
    print(f"{BOLD}{CYAN}=================================================================={RESET}")
    print(f"{BOLD}{BG_BLUE}{WHITE}  SIMULASI INTERAKTIF STRUKTUR DATA: GRAF & ALGORITMA TRAVERSAL  {RESET}")
    print(f"{BOLD}{CYAN}=================================================================={RESET}")
    print(f"{DIM}Materi: Adjacency List, BFS (Queue), DFS (Recursion), Cycle Detection{RESET}\n")


def print_menu() -> None:
    print(f"{BOLD}PILIHAN MENU PRAKTIKUM:{RESET}")
    print(f"  {YELLOW}1.{RESET} Tampilkan Representasi Graf (Adjacency List)")
    print(f"  {YELLOW}2.{RESET} Jalankan Traversal Breadth-First Search (BFS)")
    print(f"  {YELLOW}3.{RESET} Jalankan Traversal Depth-First Search (DFS)")
    print(f"  {YELLOW}4.{RESET} Cari Jalur Terpendek via BFS (Shortest Hop Path)")
    print(f"  {YELLOW}5.{RESET} Audit Deteksi Siklus (Cycle Detection)")
    print(f"  {YELLOW}6.{RESET} Tambah Simpul / Edge Kustom")
    print(f"  {YELLOW}7.{RESET} Jalankan Demo Lengkap Otomatis")
    print(f"  {YELLOW}0.{RESET} Keluar")


def run_full_demo(graph: Graph) -> None:
    print(f"\n{BOLD}{GREEN}>>> MENJALANKAN DEMO OTOMATIS LENGKAP <<<{RESET}\n")
    graph.display_adj_list()

    start_node = "Router-A"
    bfs_order, dist, _ = graph.bfs(start_node, delay=0.03)
    print(f"\n{BOLD}Hasil Urutan Kunjungan BFS:{RESET} " + " -> ".join(f"{CYAN}{n}{RESET}" for n in bfs_order))

    dfs_order = graph.dfs(start_node, delay=0.03)
    print(f"\n{BOLD}Hasil Urutan Kunjungan DFS:{RESET} " + " -> ".join(f"{MAGENTA}{n}{RESET}" for n in dfs_order))

    target_node = "Database"
    path = graph.find_shortest_path_bfs(start_node, target_node)
    if path:
        path_str = " -> ".join(f"{GREEN}{node}{RESET}" for node in path)
        print(f"\n{BOLD}Jalur Terpendek ({start_node} -> {target_node}):{RESET} {path_str} ({len(path)-1} hops)")

    has_cycle = graph.detect_cycle_undirected()
    status = f"{RED}Ya, Graf memiliki siklus/loop!{RESET}" if has_cycle else f"{GREEN}Tidak ada siklus (Acyclic).{RESET}"
    print(f"{BOLD}Status Siklus pada Graf:{RESET} {status}\n")


def interactive_loop() -> None:
    graph = build_sample_network()
    print_banner()

    # Jika dijalankan secara non-interaktif (piped atau scripted)
    if not sys.stdin.isatty():
        run_full_demo(graph)
        return

    while True:
        print_menu()
        try:
            choice = input(f"\n{BOLD}Masukkan nomor opsi [0-7]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Sesi ditutup.{RESET}")
            break

        if choice == "1":
            graph.display_adj_list()
        elif choice == "2":
            start = input(f"Masukkan simpul awal (default 'Router-A'): ").strip() or "Router-A"
            order, dist, _ = graph.bfs(start)
            print(f"\n{BOLD}Ringkasan Urutan BFS:{RESET} " + " -> ".join(f"{CYAN}{n}{RESET}" for n in order))
            print(f"{BOLD}Tabel Jarak Hop dari '{start}':{RESET}")
            for k, v in dist.items():
                print(f"  - {k}: {v} hop")
            print()
        elif choice == "3":
            start = input(f"Masukkan simpul awal (default 'Router-A'): ").strip() or "Router-A"
            order = graph.dfs(start)
            print(f"\n{BOLD}Ringkasan Urutan DFS:{RESET} " + " -> ".join(f"{MAGENTA}{n}{RESET}" for n in order))
            print()
        elif choice == "4":
            u = input("Masukkan simpul asal (misal 'Router-A'): ").strip() or "Router-A"
            v = input("Masukkan simpul tujuan (misal 'Database'): ").strip() or "Database"
            path = graph.find_shortest_path_bfs(u, v)
            if path:
                path_str = " -> ".join(f"{GREEN}{node}{RESET}" for node in path)
                print(f"\n{BOLD}Jalur Terpendek:{RESET} {path_str} ({len(path) - 1} hops)\n")
            else:
                print(f"\n{RED}Tidak ada jalur yang menghubungkan {u} dan {v}!{RESET}\n")
        elif choice == "5":
            has_cycle = graph.detect_cycle_undirected()
            if has_cycle:
                print(f"\n{RED}{BOLD}[HASIL] Siklus terdeteksi pada graf!{RESET}\n")
            else:
                print(f"\n{GREEN}{BOLD}[HASIL] Graf bebas dari siklus (Acyclic Tree).{RESET}\n")
        elif choice == "6":
            u = input("Simpul asal: ").strip()
            v = input("Simpul tujuan: ").strip()
            if u and v:
                graph.add_edge(u, v)
                print(f"{GREEN}Edge ({u} <-> {v}) berhasil ditambahkan!{RESET}\n")
        elif choice == "7":
            run_full_demo(graph)
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menggunakan simulator graf! Sampai jumpa.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}\n")


if __name__ == "__main__":
    interactive_loop()
