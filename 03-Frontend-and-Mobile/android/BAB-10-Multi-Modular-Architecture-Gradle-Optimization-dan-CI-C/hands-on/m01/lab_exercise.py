#!/usr/bin/env python3
"""
Lab Exercise M01: Multi-Modular Architecture, Gradle Optimization & CI/CD Pipeline
Simulasi teknis interaktif arsitektur multi-modul Android, evaluasi DAG (Directed Acyclic Graph),
Gradle Build Cache & Configuration Avoidance, serta eksekusi pipeline CI/CD.
"""

import sys
import time
import hashlib
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional

# ANSI Color Codes for Terminal Output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


class GradleModule:
    def __init__(self, name: str, module_type: str, build_time_ms: int):
        self.name = name
        self.module_type = module_type  # 'app', 'feature', 'core'
        self.build_time_ms = build_time_ms
        self.dependencies: Set[str] = set()
        self.cache_key: Optional[str] = None

    def add_dependency(self, dep_name: str) -> None:
        self.dependencies.add(dep_name)

    def calculate_cache_key(self, source_hash: str) -> str:
        data = f"{self.name}:{self.module_type}:{source_hash}:{sorted(list(self.dependencies))}"
        self.cache_key = hashlib.sha256(data.encode()).hexdigest()[:12]
        return self.cache_key


class MultiModuleDependencyGraph:
    def __init__(self):
        self.modules: Dict[str, GradleModule] = {}

    def add_module(self, name: str, module_type: str, build_time_ms: int) -> GradleModule:
        mod = GradleModule(name, module_type, build_time_ms)
        self.modules[name] = mod
        return mod

    def add_edge(self, from_mod: str, to_mod: str) -> None:
        if from_mod in self.modules and to_mod in self.modules:
            self.modules[from_mod].add_dependency(to_mod)

    def detect_cycles(self) -> List[List[str]]:
        """Mendeteksi apakah terdapat circular dependency menggunakan DFS."""
        visited: Dict[str, int] = {name: 0 for name in self.modules}  # 0: unvisited, 1: visiting, 2: visited
        cycles: List[List[str]] = []
        path: List[str] = []

        def dfs(node: str):
            visited[node] = 1
            path.append(node)

            for neighbor in self.modules[node].dependencies:
                if visited[neighbor] == 1:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif visited[neighbor] == 0:
                    dfs(neighbor)

            path.pop()
            visited[node] = 2

        for mod_name in self.modules:
            if visited[mod_name] == 0:
                dfs(mod_name)
        return cycles

    def compute_compilation_order(self) -> List[List[str]]:
        """Topological sort level-by-level untuk kompilasi paralel."""
        in_degree: Dict[str, int] = {m: 0 for m in self.modules}
        reverse_graph = defaultdict(list)

        for name, mod in self.modules.items():
            for dep in mod.dependencies:
                reverse_graph[dep].append(name)
                in_degree[name] += 1

        queue = deque([m for m, deg in in_degree.items() if deg == 0])
        levels: List[List[str]] = []

        while queue:
            current_level = []
            for _ in range(len(queue)):
                curr = queue.popleft()
                current_level.append(curr)
                for dependent in reverse_graph[curr]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
            levels.append(current_level)

        return levels


class GradleSimulator:
    def __init__(self, graph: MultiModuleDependencyGraph):
        self.graph = graph
        self.remote_cache: Dict[str, str] = {}
        self.local_cache: Dict[str, str] = {}

    def simulate_build(self, source_changes: Dict[str, str], use_remote_cache: bool = True) -> None:
        print(f"\n{Colors.BOLD}{Colors.CYAN}--- Memulai Gradle Build Execution ---{Colors.RESET}")
        print(f"{Colors.DIM}Settings: org.gradle.caching=true | org.gradle.parallel=true{Colors.RESET}\n")

        levels = self.graph.compute_compilation_order()
        total_time_ms = 0
        cache_hits = 0
        tasks_executed = 0

        for level_idx, level in enumerate(levels):
            print(f"{Colors.YELLOW}► Build Layer {level_idx + 1} (Parallel Execution Batch):{Colors.RESET} {', '.join(level)}")
            for mod_name in level:
                mod = self.graph.modules[mod_name]
                src_hash = source_changes.get(mod_name, "default_v1.0")
                key = mod.calculate_cache_key(src_hash)

                if key in self.local_cache:
                    status = f"{Colors.GREEN}[FROM-CACHE (LOCAL)]{Colors.RESET}"
                    exec_time = 12
                    cache_hits += 1
                elif use_remote_cache and key in self.remote_cache:
                    status = f"{Colors.CYAN}[FROM-CACHE (REMOTE)]{Colors.RESET}"
                    self.local_cache[key] = f"artifact_{key}"
                    exec_time = 45
                    cache_hits += 1
                else:
                    status = f"{Colors.RED}[EXECUTED]{Colors.RESET}"
                    exec_time = mod.build_time_ms
                    self.local_cache[key] = f"artifact_{key}"
                    if use_remote_cache:
                        self.remote_cache[key] = f"artifact_{key}"
                    tasks_executed += 1

                total_time_ms += exec_time
                print(f"  ├─ {mod.name:<22} {status} {Colors.DIM}(Hash: {key} | {exec_time}ms){Colors.RESET}")

        print(f"\n{Colors.BOLD}{Colors.GREEN}✔ BUILD SUCCESSFUL{Colors.RESET}")
        print(f"Total Wall Clock Simulation Time : {Colors.BOLD}{total_time_ms} ms{Colors.RESET}")
        print(f"Cache Hit Ratio                  : {Colors.BOLD}{(cache_hits / (cache_hits + tasks_executed) * 100):.1f}%{Colors.RESET}")


class CIPipelineRunner:
    def __init__(self):
        self.steps = [
            ("Gradle Wrapper Verification", 150, True),
            ("ktlint & Detekt Static Analysis", 320, True),
            ("Unit Tests (:core & :feature)", 680, True),
            ("R8/Proguard Shrinking Check", 450, True),
            ("AssembleRelease & AAB Signing", 520, True),
            ("APK Size & Dependency Drift Guard", 180, True),
        ]

    def execute_pipeline(self) -> bool:
        print(f"\n{Colors.BOLD}{Colors.BLUE}===================================================={Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}     ANDROID CI/CD RUNNER (GitHub Actions / CI)     {Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}===================================================={Colors.RESET}")

        for step_name, duration_ms, will_pass in self.steps:
            print(f"\n{Colors.CYAN}⟳ Menjalankan job:{Colors.RESET} {Colors.BOLD}{step_name}{Colors.RESET}...")
            time.sleep(0.1)  # Simulasi proses
            if will_pass:
                print(f"  {Colors.GREEN}✔ Status: PASSED{Colors.RESET} {Colors.DIM}(took {duration_ms}ms){Colors.RESET}")
            else:
                print(f"  {Colors.RED}✖ Status: FAILED{Colors.RESET}")
                return False

        print(f"\n{Colors.BOLD}{Colors.GREEN}🎉 SEMUA PIPELINE GATES VALID! Artefak siap dideploy ke Play Console Internal Track.{Colors.RESET}\n")
        return True


def setup_standard_project() -> MultiModuleDependencyGraph:
    graph = MultiModuleDependencyGraph()
    # Core Layer
    graph.add_module(":core:model", "core", 120)
    graph.add_module(":core:network", "core", 250)
    graph.add_module(":core:database", "core", 280)
    graph.add_module(":core:designsystem", "core", 190)

    # Feature Layer
    graph.add_module(":feature:auth", "feature", 420)
    graph.add_module(":feature:feed", "feature", 510)
    graph.add_module(":feature:profile", "feature", 390)

    # App Layer
    graph.add_module(":app", "app", 650)

    # Wire Dependencies (Clean Architecture & Inverted Dependencies)
    graph.add_edge(":core:network", ":core:model")
    graph.add_edge(":core:database", ":core:model")

    graph.add_edge(":feature:auth", ":core:network")
    graph.add_edge(":feature:auth", ":core:designsystem")

    graph.add_edge(":feature:feed", ":core:network")
    graph.add_edge(":feature:feed", ":core:database")
    graph.add_edge(":feature:feed", ":core:designsystem")

    graph.add_edge(":feature:profile", ":core:network")
    graph.add_edge(":feature:profile", ":core:designsystem")

    graph.add_edge(":app", ":feature:auth")
    graph.add_edge(":app", ":feature:feed")
    graph.add_edge(":app", ":feature:profile")

    return graph


def print_architecture_map(graph: MultiModuleDependencyGraph) -> None:
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== ARSITEKTUR MULTI-MODUL ANDROID (DAG Dependency Map) ==={Colors.RESET}")
    for name, mod in sorted(graph.modules.items()):
        dep_str = ", ".join(sorted(list(mod.dependencies))) if mod.dependencies else f"{Colors.DIM}(root level){Colors.RESET}"
        type_badge = f"{Colors.CYAN}[{mod.module_type.upper()}]{Colors.RESET}"
        print(f"  • {mod.name:<24} {type_badge:<18} ──► depends on: {dep_str}")


def interactive_menu() -> None:
    graph = setup_standard_project()
    simulator = GradleSimulator(graph)
    ci_runner = CIPipelineRunner()

    source_state: Dict[str, str] = {name: "v1.0" for name in graph.modules}

    while True:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}===================================================={Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW}   LAB EXERCISE M01: ANDROID MODULAR & GRADLE LAB   {Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW}===================================================={Colors.RESET}")
        print("1. Tampilkan Visualisasi Directed Acyclic Graph (DAG) Modul")
        print("2. Uji Deteksi Circular Dependency Guard")
        print("3. Jalankan Gradle Cold Build (Cache Miss / First Run)")
        print("4. Ubah Source Code di :core:network & Uji Incremental Build")
        print("5. Jalankan Kembali Build (100% Cache Hit Verification)")
        print("6. Simulasikan GitHub Actions CI/CD Quality Pipeline")
        print("7. Keluar (Exit)")
        choice = input(f"\n{Colors.BOLD}Pilih opsi [1-7]: {Colors.RESET}").strip()

        if choice == "1":
            print_architecture_map(graph)
            levels = graph.compute_compilation_order()
            print(f"\n{Colors.BOLD}Jalur Kompilasi Paralel (Compilation Layers):{Colors.RESET}")
            for idx, lvl in enumerate(levels, 1):
                print(f"  Level {idx}: {lvl}")
        elif choice == "2":
            print(f"\n{Colors.CYAN}Menguji skenario circular dependency: Menambahkan :core:model ──► :app{Colors.RESET}")
            temp_graph = setup_standard_project()
            temp_graph.add_edge(":core:model", ":app")
            cycles = temp_graph.detect_cycles()
            if cycles:
                print(f"{Colors.RED}{Colors.BOLD}✖ ERROR: Terdeteksi Circular Dependency Violation!{Colors.RESET}")
                for cycle in cycles:
                    print(f"  {Colors.YELLOW}Siklus:{Colors.RESET} {' ──► '.join(cycle)}")
            else:
                print(f"{Colors.GREEN}✔ Graf bersih dari circular dependencies.{Colors.RESET}")
        elif choice == "3":
            simulator.simulate_build(source_state, use_remote_cache=False)
        elif choice == "4":
            print(f"\n{Colors.YELLOW}► Mengubah source code pada ':core:network' (misal: retrofit interceptor update)...{Colors.RESET}")
            source_state[":core:network"] = f"v2.{int(time.time())}"
            simulator.simulate_build(source_state, use_remote_cache=True)
        elif choice == "5":
            print(f"\n{Colors.CYAN}► Menjalankan build tanpa perubahan source code...{Colors.RESET}")
            simulator.simulate_build(source_state, use_remote_cache=True)
        elif choice == "6":
            ci_runner.execute_pipeline()
        elif choice == "7":
            print(f"\n{Colors.GREEN}Lab selesai. Terima kasih telah mengeksplorasi Gradle Multi-Module & CI/CD!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan coba lagi.{Colors.RESET}")


if __name__ == "__main__":
    try:
        interactive_menu()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n{Colors.YELLOW}Sesi lab dihentikan oleh user. Sampai jumpa!{Colors.RESET}")
        sys.exit(0)
