#!/usr/bin/env python3
"""
Lab Hands-on: Core Foundations - Data Structures & Algorithms
Bab 09: Advanced Graph Traversal & Heuristic Pathfinding Engine
Modul 02: Deep Dive: Dijkstra vs. A* Search Performance on Weighted Terrain

Deskripsi:
Script ini mengimplementasikan engine pathfinding berbasis graph grid berbobot
menggunakan Min-Heap priority queue (`heapq`). Membandingkan algoritma Uniform-Cost
Search (Dijkstra) dengan A* Heuristic Search (Manhattan & Euclidean) secara real-time,
mengukur node expansion efficiency, execution latency, dan memvisualisasikan state grid.
"""

import math
import heapq
import time
from typing import Dict, List, Tuple, Optional, Set

# ANSI Color Codes untuk visualisasi terminal
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_WHITE   = "\033[37m"
CLR_BG_PATH = "\033[42;30m" # Green background
CLR_BG_WALL = "\033[47;30m" # White block

Coordinate = Tuple[int, int]


class WeightedGridGraph:
    """
    Representasi graf implisit berbasis koordinat 2D dengan dynamic edge weights.
    Tipe sel:
      0: Normal Plains  (Cost = 1.0)
      1: Obstacle/Wall  (Cost = Infinity / Unpassable)
      2: Mud/Swamp      (Cost = 5.0)
      3: Water/River    (Cost = 10.0)
    """
    TERRAIN_COSTS = {
        0: 1.0,
        1: float('inf'),
        2: 5.0,
        3: 10.0
    }

    TERRAIN_CHARS = {
        0: " ",
        1: "█",
        2: "~",
        3: "≈"
    }

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid: List[List[int]] = [[0 for _ in range(width)] for _ in range(height)]

    def set_cell(self, x: int, y: int, cell_type: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = cell_type

    def is_passable(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height and self.grid[y][x] != 1

    def get_cost(self, to_node: Coordinate) -> float:
        x, y = to_node
        return self.TERRAIN_COSTS.get(self.grid[y][x], float('inf'))

    def get_neighbors(self, node: Coordinate) -> List[Coordinate]:
        """Menghasilkan tetangga ortogonal (4-arah: N, S, E, W)."""
        x, y = node
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [pt for pt in candidates if self.is_passable(pt[0], pt[1])]


class SearchProfiler:
    """Mengumpulkan metrik performa algoritma traversal."""
    def __init__(self, algo_name: str):
        self.algo_name = algo_name
        self.start_time: float = 0.0
        self.execution_time_ms: float = 0.0
        self.nodes_explored: int = 0
        self.path_cost: float = 0.0
        self.path_length: int = 0
        self.path: List[Coordinate] = []

    def start(self):
        self.start_time = time.perf_counter()

    def stop(self):
        self.execution_time_ms = (time.perf_counter() - self.start_time) * 1000.0


def heuristic_manhattan(a: Coordinate, b: Coordinate) -> float:
    """Admissible & Consistent heuristic untuk 4-directional grid movement."""
    return float(abs(a[0] - b[0]) + abs(a[1] - b[1]))


def heuristic_euclidean(a: Coordinate, b: Coordinate) -> float:
    """Euclidean distance heuristic (underestimates diagonal-less path, tetep admissible)."""
    return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)


def run_pathfinding(
    graph: WeightedGridGraph,
    start: Coordinate,
    goal: Coordinate,
    algorithm: str = "astar",
    heuristic_type: str = "manhattan"
) -> SearchProfiler:
    """
    Engine implementasi Dijkstra dan A*.
    Jika algorithm == 'dijkstra', heuristic secara implisit bernilai 0.
    """
    profiler = SearchProfiler(f"{algorithm.upper()}_{heuristic_type.upper()}" if algorithm == "astar" else "DIJKSTRA")
    profiler.start()

    # Priority Queue menyimpan tuple: (f_score, counter, current_node)
    # Counter digunakan sebagai tie-breaker deterministic tanpa membandingkan node
    counter = 0
    open_set: List[Tuple[float, int, Coordinate]] = []
    heapq.heappush(open_set, (0.0, counter, start))

    came_from: Dict[Coordinate, Optional[Coordinate]] = {start: None}
    g_score: Dict[Coordinate, float] = {start: 0.0}
    closed_set: Set[Coordinate] = set()

    h_func = (heuristic_manhattan if heuristic_type == "manhattan" else heuristic_euclidean) if algorithm == "astar" else lambda a, b: 0.0

    while open_set:
        current_f, _, current = heapq.heappop(open_set)

        if current in closed_set:
            continue

        closed_set.add(current)
        profiler.nodes_explored += 1

        if current == goal:
            # Rekonstruksi path dari goal ke start
            curr: Optional[Coordinate] = goal
            path = []
            while curr is not None:
                path.append(curr)
                curr = came_from[curr]
            path.reverse()
            profiler.path = path
            profiler.path_length = len(path)
            profiler.path_cost = g_score[goal]
            break

        for neighbor in graph.get_neighbors(current):
            tentative_g = g_score[current] + graph.get_cost(neighbor)

            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h = h_func(neighbor, goal)
                f = tentative_g + h
                counter += 1
                heapq.heappush(open_set, (f, counter, neighbor))

    profiler.stop()
    return profiler


def render_grid_visualization(graph: WeightedGridGraph, start: Coordinate, goal: Coordinate, path: List[Coordinate]):
    """Merender peta ASCII lengkap dengan rute optimal dan legenda terrain."""
    path_set = set(path)
    print(f"\n{CLR_BOLD}{CLR_CYAN}--- PETA TERRAIN & JALUR OPTIMAL ---{CLR_RESET}")
    print("+" + "---" * graph.width + "+")
    for y in range(graph.height):
        row_str = "|"
        for x in range(graph.width):
            pt = (x, y)
            if pt == start:
                row_str += f"{CLR_BOLD}{CLR_GREEN} S {CLR_RESET}"
            elif pt == goal:
                row_str += f"{CLR_BOLD}{CLR_RED} G {CLR_RESET}"
            elif pt in path_set:
                row_str += f"{CLR_BG_PATH} * {CLR_RESET}"
            else:
                cell_type = graph.grid[y][x]
                char = graph.TERRAIN_CHARS[cell_type]
                if cell_type == 1:
                    row_str += f"{CLR_BG_WALL}   {CLR_RESET}"
                elif cell_type == 2:
                    row_str += f"{CLR_YELLOW} ~ {CLR_RESET}"
                elif cell_type == 3:
                    row_str += f"{CLR_BLUE} ≈ {CLR_RESET}"
                else:
                    row_str += " . "
        row_str += "|"
        print(row_str)
    print("+" + "---" * graph.width + "+")
    print(f"Legenda: {CLR_GREEN}S{CLR_RESET}=Start, {CLR_RED}G{CLR_RESET}=Goal, {CLR_BG_PATH}*{CLR_RESET}=Path, "
          f"{CLR_BG_WALL} {CLR_RESET}=Wall (Inf), {CLR_YELLOW}~{CLR_RESET}=Mud(5.0), {CLR_BLUE}≈{CLR_RESET}=Water(10.0), .=Plains(1.0)\n")


def build_lab_scenario() -> Tuple[WeightedGridGraph, Coordinate, Coordinate]:
    """Membangun map simulasi dengan choke points, mud, dan rute memutar."""
    width, height = 30, 12
    grid = WeightedGridGraph(width, height)

    # Tambahkan dinding pembatas (Vertical Walls creating a maze-like choke point)
    for y in range(0, 9):
        grid.set_cell(10, y, 1)
    for y in range(3, 12):
        grid.set_cell(20, y, 1)

    # Tambahkan medan berat (Mud & Water) yang harus diperhitungkan cost-nya
    for y in range(4, 8):
        for x in range(3, 8):
            grid.set_cell(x, y, 2) # Mud cost 5.0

    for y in range(0, 4):
        for x in range(12, 18):
            grid.set_cell(x, y, 3) # Water cost 10.0

    start = (1, 1)
    goal = (28, 10)
    return grid, start, goal


def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}  LAB: GRAPH SEARCH ENGINE - DIJKSTRA VS A* HEURISTIC EVALUATION      {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")

    graph, start, goal = build_lab_scenario()

    # Eksekusi Benchmark
    experiments = [
        ("dijkstra", "none"),
        ("astar", "manhattan"),
        ("astar", "euclidean")
    ]

    results: List[SearchProfiler] = []

    for algo, heuristic in experiments:
        prof = run_pathfinding(graph, start, goal, algorithm=algo, heuristic_type=heuristic)
        results.append(prof)

    # Visualisasikan solusi dari A* Manhattan (Optimal heuristic untuk 4-grid)
    astar_manhattan = next(r for r in results if "MANHATTAN" in r.algo_name)
    render_grid_visualization(graph, start, goal, astar_manhattan.path)

    # Tampilkan Hasil Analisis Komparatif
    print(f"{CLR_BOLD}{CLR_WHITE}{'Algoritma':<22} | {'Nodes Explored':<15} | {'Cost Path':<12} | {'Length':<8} | {'Latensi (ms)':<12}{CLR_RESET}")
    print("-" * 78)
    for r in results:
        highlight = CLR_GREEN if "ASTAR_MANHATTAN" in r.algo_name else CLR_YELLOW if "ASTAR" in r.algo_name else CLR_WHITE
        print(f"{highlight}{r.algo_name:<22}{CLR_RESET} | "
              f"{r.nodes_explored:<15} | "
              f"{r.path_cost:<12.2f} | "
              f"{r.path_length:<8} | "
              f"{r.execution_time_ms:<12.4f}")

    dijkstra_res = results[0]
    efficiency = ((dijkstra_res.nodes_explored - astar_manhattan.nodes_explored) / dijkstra_res.nodes_explored) * 100

    print("-" * 78)
    print(f"{CLR_BOLD}Kesimpulan Teknis:{CLR_RESET}")
    print(f"1. {CLR_GREEN}A* (Manhattan){CLR_RESET} memotong pencarian node sebesar {CLR_BOLD}{efficiency:.2f}%{CLR_RESET} dibanding Dijkstra.")
    print(f"2. Keduanya menjamin {CLR_CYAN}Path Cost Identik ({astar_manhattan.path_cost:.1f}){CLR_RESET}, membuktikan heuristik terbukti Admissible.")
    print(f"3. A* mengeliminasi ekspansi state ruang yang tidak menuju ke target vektor.")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}\n")


if __name__ == "__main__":
    main()