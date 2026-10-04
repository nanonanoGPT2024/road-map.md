#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Data Structures & Algorithms
Bab 07 - Modul 02: Network Routing & Pathfinding Engine (Dijkstra vs. A*)
Implementasi mandiri algoritma graf dengan optimasi Min-Heap, deteksi rute,
dan benchmarking metrik eksplorasi ruang keadaan (state space).
"""

import heapq
import math
import time
import random
from typing import Dict, List, Tuple, Optional, Set

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_BG_DARK = "\033[100m"

Point = Tuple[int, int]


class GridGraph:
    """
    Representasi Topologi Jaringan Grid 2D dengan bobot dinamis
    (simulasi latency dan packet loss).
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.weights: Dict[Point, float] = {}
        self.obstacles: Set[Point] = set()

    def in_bounds(self, p: Point) -> bool:
        return 0 <= p[0] < self.width and 0 <= p[1] < self.height

    def is_passable(self, p: Point) -> bool:
        return p not in self.obstacles

    def neighbors(self, p: Point) -> List[Point]:
        """Menghasilkan tetangga orthogonal (von Neumann neighborhood)."""
        x, y = p
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [nxt for nxt in candidates if self.in_bounds(nxt) and self.is_passable(nxt)]

    def cost(self, to_node: Point) -> float:
        """Mengembalikan latency/biaya traversal ke node tujuan."""
        return self.weights.get(to_node, 1.0)


def heuristic(a: Point, b: Point) -> float:
    """Fungsi heuristik Manhattan Distance yang admissible dan consistent."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def dijkstra_search(
    graph: GridGraph, start: Point, goal: Point
) -> Tuple[Optional[List[Point]], float, int]:
    """
    Algoritma Dijkstra: Pencarian jalur terpendek berbasis Uniform-Cost Search.
    Eksplorasi seragam ke seluruh arah tanpa estimasi arah tujuan.
    """
    frontier: List[Tuple[float, Point]] = []
    heapq.heappush(frontier, (0.0, start))
    came_from: Dict[Point, Optional[Point]] = {start: None}
    cost_so_far: Dict[Point, float] = {start: 0.0}
    nodes_expanded = 0

    while frontier:
        current_cost, current = heapq.heappop(frontier)
        nodes_expanded += 1

        if current == goal:
            break

        # Pruning lazy heap nodes
        if current_cost > cost_so_far[current]:
            continue

        for nxt in graph.neighbors(current):
            new_cost = cost_so_far[current] + graph.cost(nxt)
            if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                cost_so_far[nxt] = new_cost
                heapq.heappush(frontier, (new_cost, nxt))
                came_from[nxt] = current

    if goal not in came_from:
        return None, float("inf"), nodes_expanded

    # Rekonstruksi jalur
    path: List[Point] = []
    curr: Optional[Point] = goal
    while curr is not None:
        path.append(curr)
        curr = came_from[curr]
    path.reverse()

    return path, cost_so_far[goal], nodes_expanded


def astar_search(
    graph: GridGraph, start: Point, goal: Point
) -> Tuple[Optional[List[Point]], float, int]:
    """
    Algoritma A*: Pathfinding berbasis heuristik f(n) = g(n) + h(n).
    Memprioritaskan node yang mendekati target secara geometris.
    """
    frontier: List[Tuple[float, Point]] = []
    heapq.heappush(frontier, (0.0, start))
    came_from: Dict[Point, Optional[Point]] = {start: None}
    cost_so_far: Dict[Point, float] = {start: 0.0}
    nodes_expanded = 0

    while frontier:
        _, current = heapq.heappop(frontier)
        nodes_expanded += 1

        if current == goal:
            break

        for nxt in graph.neighbors(current):
            new_cost = cost_so_far[current] + graph.cost(nxt)
            if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                cost_so_far[nxt] = new_cost
                priority = new_cost + heuristic(nxt, goal)
                heapq.heappush(frontier, (priority, nxt))
                came_from[nxt] = current

    if goal not in came_from:
        return None, float("inf"), nodes_expanded

    path: List[Point] = []
    curr: Optional[Point] = goal
    while curr is not None:
        path.append(curr)
        curr = came_from[curr]
    path.reverse()

    return path, cost_so_far[goal], nodes_expanded


def render_grid(
    graph: GridGraph,
    start: Point,
    goal: Point,
    path: Optional[List[Point]] = None,
) -> None:
    """Menampilkan representasi visual ASCII dari grid jaringan."""
    path_set = set(path) if path else set()

    print(f"\n{CLR_BOLD}[Visualisasi Topologi Jaringan & Jalur Terpilih]{CLR_RESET}")
    print("+" + "---" * graph.width + "+")
    for y in range(graph.height):
        row_str = "|"
        for x in range(graph.width):
            pt = (x, y)
            if pt == start:
                row_str += f"{CLR_GREEN}{CLR_BOLD} S {CLR_RESET}"
            elif pt == goal:
                row_str += f"{CLR_RED}{CLR_BOLD} E {CLR_RESET}"
            elif pt in path_set:
                row_str += f"{CLR_CYAN}{CLR_BOLD} * {CLR_RESET}"
            elif pt in graph.obstacles:
                row_str += f"{CLR_BG_DARK} # {CLR_RESET}"
            elif graph.cost(pt) > 1.0:
                row_str += f"{CLR_YELLOW} ~ {CLR_RESET}"  # Zona latency tinggi
            else:
                row_str += " . "
        row_str += "|"
        print(row_str)
    print("+" + "---" * graph.width + "+")
    print(
        f"Keterangan: {CLR_GREEN}S{CLR_RESET}=Start, "
        f"{CLR_RED}E{CLR_RESET}=End, "
        f"{CLR_CYAN}*{CLR_RESET}=Path, "
        f"{CLR_BG_DARK}#{CLR_RESET}=Obstacle, "
        f"{CLR_YELLOW}~{CLR_RESET}=High Latency (Weight 5.0)\n"
    )


def run_benchmark():
    """Eksekutor pengujian beban dan verifikasi performa algoritma."""
    width, height = 30, 15
    graph = GridGraph(width, height)
    random.seed(42)

    # Tambahkan rintangan acak (cluster network congestion / dead routers)
    for _ in range(80):
        ox = random.randint(0, width - 1)
        oy = random.randint(0, height - 1)
        graph.obstacles.add((ox, oy))

    # Tambahkan zona latency tinggi (simulasi jalur bandwidth padat)
    for _ in range(40):
        wx = random.randint(0, width - 1)
        wy = random.randint(0, height - 1)
        if (wx, wy) not in graph.obstacles:
            graph.weights[(wx, wy)] = 5.0

    start = (1, 1)
    goal = (width - 2, height - 2)

    # Pastikan start dan goal tidak tertutup obstacle
    graph.obstacles.discard(start)
    graph.obstacles.discard(goal)

    print(f"{CLR_CYAN}{CLR_BOLD}========================================================")
    print("  DSA LAB: SHORTEST PATH & HEURISTIC ENGINE BENCHMARK")
    print(f"========================================================{CLR_RESET}")
    print(f"Dimensi Grid   : {width} x {height} ({width * height} Nodes)")
    print(f"Titik Awal (S) : {start}")
    print(f"Titik Akhir (E): {goal}")
    print(f"Total Kendala  : {len(graph.obstacles)} node non-passable")

    # Benchmarking Dijkstra
    t0 = time.perf_counter_ns()
    dijkstra_path, dijkstra_cost, dijkstra_exp = dijkstra_search(graph, start, goal)
    t1 = time.perf_counter_ns()
    dijkstra_time_ms = (t1 - t0) / 1_000_000.0

    # Benchmarking A*
    t2 = time.perf_counter_ns()
    astar_path, astar_cost, astar_exp = astar_search(graph, start, goal)
    t3 = time.perf_counter_ns()
    astar_time_ms = (t3 - t2) / 1_000_000.0

    # Render Visualisasi A* Path
    render_grid(graph, start, goal, astar_path)

    # Validasi Ekuivalensi Bobot Terpendek
    valid = math.isclose(dijkstra_cost, astar_cost, rel_tol=1e-5)

    print(f"{CLR_BOLD}Hasil Komparasi Kinerja Algoritma:{CLR_RESET}")
    header = f"{'Metrik':<24} | {'Dijkstra (UCS)':<18} | {'A* Heuristic':<18}"
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    print(
        f"{'Total Biaya Jalur':<24} | {dijkstra_cost:<18.2f} | {astar_cost:<18.2f}"
    )
    print(
        f"{'Node Dieksplorasi':<24} | {dijkstra_exp:<18} | {astar_exp:<18}"
    )
    print(
        f"{'Panjang Rute (Langkah)':<24} | "
        f"{len(dijkstra_path) if dijkstra_path else 0:<18} | "
        f"{len(astar_path) if astar_path else 0:<18}"
    )
    print(
        f"{'Waktu Eksekusi':<24} | {dijkstra_time_ms:<15.4f} ms | {astar_time_ms:<15.4f} ms"
    )
    print("-" * len(header))

    if dijkstra_exp > 0:
        reduksi_eksplorasi = (
            (dijkstra_exp - astar_exp) / dijkstra_exp
        ) * 100.0
        print(
            f"\n{CLR_GREEN}{CLR_BOLD}[OK]{CLR_RESET} Reduksi ruang pencarian A*: "
            f"{CLR_BOLD}{reduksi_eksplorasi:.2f}%{CLR_RESET} lebih efisien dibandingkan Dijkstra."
        )

    if valid:
        print(
            f"{CLR_GREEN}{CLR_BOLD}[VERIFIED]{CLR_RESET} Kedua algoritma mencapai kondisi optimalitas global yang identik.\n"
        )
    else:
        print(
            f"{CLR_RED}{CLR_BOLD}[FAIL]{CLR_RESET} Biaya tidak konsisten antara Dijkstra dan A*!\n"
        )


if __name__ == "__main__":
    run_benchmark()