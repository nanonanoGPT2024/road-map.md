#!/usr/bin/env python3
"""
Lab Hands-on: Android Multi-Modular Architecture, Gradle Optimization, & CI/CD Pipeline Simulation
Category: 03-Frontend-and-Mobile | Chapter 10 - Modul 02 Deep Dive

Simulates:
1. Multi-Modular Project Dependency Graph (DAG) with Topological Resolution & Cycle Detection.
2. Gradle Optimization Engine: Build Cache (SHA-256 fingerprinting), Up-To-Date checking,
   Configuration Caching, and Parallel Worker Task Execution.
3. CI/CD Matrix Pipeline: Linting, Unit Testing, and Bundle Packaging.
"""

import sys
import time
import hashlib
import random
from enum import Enum
from collections import defaultdict, deque
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Set, Tuple, Optional

# ANSI Color formatting for CLI presentation
class TerminalColors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

class TaskOutcome(Enum):
    EXECUTED = "EXECUTED"
    FROM_CACHE = "FROM-CACHE"
    UP_TO_DATE = "UP-TO-DATE"
    SKIPPED = "SKIPPED"

class ModuleType(Enum):
    CORE_LIBRARY = "core-library"
    FEATURE_DYNAMIC = "feature-dynamic"
    FEATURE_ANDROID = "feature-android"
    APP_SHELL = "app-shell"

@dataclass
class AndroidModule:
    name: str
    mod_type: ModuleType
    dependencies: List[str] = field(default_factory=list)
    source_files: Dict[str, str] = field(default_factory=dict)
    
    def compute_input_hash(self) -> str:
        """Menghitung fingerprint SHA-256 dari seluruh source code modul."""
        hasher = hashlib.sha256()
        for filename in sorted(self.source_files.keys()):
            hasher.update(filename.encode('utf-8'))
            hasher.update(self.source_files[filename].encode('utf-8'))
        return hasher.hexdigest()[:16]

class DependencyGraph:
    """Mengelola DAG (Directed Acyclic Graph) antar modul Gradle."""
    def __init__(self, modules: Dict[str, AndroidModule]):
        self.modules = modules
        self.adj_list: Dict[str, List[str]] = defaultdict(list)
        self.in_degree: Dict[str, int] = {name: 0 for name in modules}
        self._build_graph()

    def _build_graph(self):
        for name, mod in self.modules.items():
            for dep in mod.dependencies:
                if dep not in self.modules:
                    raise ValueError(f"Dependensi '{dep}' tidak ditemukan dalam definisi modul.")
                # dep -> name (dep harus dikompilasi sebelum name)
                self.adj_list[dep].append(name)
                self.in_degree[name] += 1

    def detect_circular_dependencies(self) -> bool:
        """Mendeteksi apakah terdapat siklus modul dengan deteksi siklus DFS."""
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self.adj_list[node]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node in self.modules:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def get_execution_stages(self) -> List[List[str]]:
        """
        Menghasilkan level-by-level parallel stages via modifikasi Kahn's Algorithm.
        Modul dalam stage yang sama independen dan dapat dikompilasi bersamaan secara paralel.
        """
        if self.detect_circular_dependencies():
            raise RuntimeError("CRITICAL: Ditemukan Circular Dependency pada grafik proyek!")

        in_deg = self.in_degree.copy()
        current_layer = [m for m, deg in in_deg.items() if deg == 0]
        stages = []

        while current_layer:
            stages.append(current_layer)
            next_layer = []
            for node in current_layer:
                for neighbor in self.adj_list[node]:
                    in_deg[neighbor] -= 1
                    if in_deg[neighbor] == 0:
                        next_layer.append(neighbor)
            current_layer = next_layer

        return stages

class GradleBuildCache:
    """Mensimulasikan Local & Remote Gradle Build Cache."""
    def __init__(self):
        self.cache_storage: Dict[str, str] = {} # Input Hash -> Output Artifact Hash
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[str]:
        if key in self.cache_storage:
            self.hits += 1
            return self.cache_storage[key]
        self.misses += 1
        return None

    def put(self, key: str, value: str):
        self.cache_storage[key] = value

class GradleEngine:
    """
    Simulator Core Gradle Engine:
    - Configuration Cache
    - Worker API Paralelisasi
    - Task Avoidance Optimization
    """
    def __init__(self, graph: DependencyGraph, cache: GradleBuildCache):
        self.graph = graph
        self.cache = cache
        self.last_built_signatures: Dict[str, str] = {}

    def _execute_task(self, module_name: str, task_name: str) -> Tuple[str, TaskOutcome, float]:
        module = self.graph.modules[module_name]
        start = time.perf_counter()
        
        # 1. Hitung Task Inputs Fingerprint
        input_hash = module.compute_input_hash()
        task_key = f"{module_name}:{task_name}:{input_hash}"

        # 2. UP-TO-DATE check (In-memory daemon cache)
        if self.last_built_signatures.get(module_name) == input_hash:
            duration = time.perf_counter() - start
            return (f":{module_name}:{task_name}", TaskOutcome.UP_TO_DATE, duration)

        # 3. Build Cache check (Local/Remote Cache)
        cached_artifact = self.cache.get(task_key)
        if cached_artifact:
            self.last_built_signatures[module_name] = input_hash
            duration = time.perf_counter() - start + 0.015 # overhead dekompresi cache
            return (f":{module_name}:{task_name}", TaskOutcome.FROM_CACHE, duration)

        # 4. EXECUTED (Kompilasi source code nyata)
        # Simulasi kompleksitas kompilasi berdasarkan jenis modul
        work_time = 0.08 if module.mod_type == ModuleType.CORE_LIBRARY else 0.15
        time.sleep(work_time)
        
        artifact_hash = hashlib.sha256(f"{task_key}:compiled".encode()).hexdigest()[:12]
        self.cache.put(task_key, artifact_hash)
        self.last_built_signatures[module_name] = input_hash
        duration = time.perf_counter() - start

        return (f":{module_name}:{task_name}", TaskOutcome.EXECUTED, duration)

    def assemble(self, max_workers: int = 4) -> List[Tuple[str, TaskOutcome, float]]:
        stages = self.graph.get_execution_stages()
        all_results = []

        print(f"\n{TerminalColors.CYAN}--- Memulai Gradle Task Execution Graph (Workers: {max_workers}) ---{TerminalColors.RESET}")
        
        for stage_idx, stage_modules in enumerate(stages):
            print(f"{TerminalColors.DIM}>> Stage {stage_idx + 1}: Paralel memproses {stage_modules}{TerminalColors.RESET}")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(self._execute_task, mod, "compileKotlin") for mod in stage_modules]
                for f in futures:
                    all_results.append(f.result())

        return all_results

def print_build_results(results: List[Tuple[str, TaskOutcome, float]], total_wall_time: float):
    print(f"\n{TerminalColors.BOLD}Detail Status Eksekusi Task:{TerminalColors.RESET}")
    total_cpu_time = 0.0
    for task_path, outcome, dur in results:
        total_cpu_time += dur
        if outcome == TaskOutcome.EXECUTED:
            badge = f"{TerminalColors.RED}{outcome.value}{TerminalColors.RESET}"
        elif outcome == TaskOutcome.FROM_CACHE:
            badge = f"{TerminalColors.YELLOW}{outcome.value}{TerminalColors.RESET}"
        else:
            badge = f"{TerminalColors.GREEN}{outcome.value}{TerminalColors.RESET}"
        
        print(f"  {task_path:<38} [{badge}] {dur * 1000:>6.1f} ms")

    parallel_ratio = (total_cpu_time / total_wall_time) if total_wall_time > 0 else 1.0
    print(f"\n{TerminalColors.BOLD}Ringkasan Metrik Build:{TerminalColors.RESET}")
    print(f"  Total CPU Work Time : {total_cpu_time * 1000:.2f} ms")
    print(f"  Wall-clock Duration : {total_wall_time * 1000:.2f} ms")
    print(f"  Faktor Paralelisasi : {TerminalColors.CYAN}{parallel_ratio:.2f}x{TerminalColors.RESET}")

def run_ci_cd_simulation(engine: GradleEngine):
    """Simulasi pipeline CI/CD modern: Static Check, Test, dan APK/AAB Assembly."""
    print(f"\n{TerminalColors.HEADER}===================================================={TerminalColors.RESET}")
    print(f"{TerminalColors.HEADER}            CI/CD BUILD MATRIX EXECUTION             {TerminalColors.RESET}")
    print(f"{TerminalColors.HEADER}===================================================={TerminalColors.RESET}")

    steps = [
        ("Lint Analysis", [":core-network:lint", ":feature-auth:lint", ":app:lint"]),
        ("Unit Tests", [":core-database:testDebugUnitTest", ":feature-payment:testDebugUnitTest"]),
        ("Bundle Packaging", [":app:bundleRelease"])
    ]

    for stage_name, tasks in steps:
        sys.stdout.write(f"[{stage_name:<18}] Menjalankan tasks: {', '.join(tasks)}... ")
        sys.stdout.flush()
        time.sleep(0.12)
        # Simulasi verifikasi test berhasil
        sys.stdout.write(f"{TerminalColors.GREEN}PASSED ✓{TerminalColors.RESET}\n")

    artifact_name = "app-release.aab"
    checksum = hashlib.sha256(f"APK_ARTIFACT_{time.time()}".encode()).hexdigest()[:24]
    print(f"\n{TerminalColors.BOLD}Artefak CI/CD Dihasilkan:{TerminalColors.RESET}")
    print(f"  File     : {TerminalColors.GREEN}{artifact_name}{TerminalColors.RESET}")
    print(f"  SHA-256  : {checksum}")
    print(f"  Status   : SIAP DEPLOY KE GOOGLE PLAY CONSOLE INTERNAL TRACK")

def main():
    print(f"{TerminalColors.HEADER}{TerminalColors.BOLD}========================================================{TerminalColors.RESET}")
    print(f"{TerminalColors.HEADER}{TerminalColors.BOLD}   Android Multi-Modular Architecture & Gradle Lab Engine{TerminalColors.RESET}")
    print(f"{TerminalColors.HEADER}{TerminalColors.BOLD}========================================================{TerminalColors.RESET}")

    # 1. Definisi Arsitektur Multi-Modul Android
    modules = {
        "core-model": AndroidModule("core-model", ModuleType.CORE_LIBRARY, [], {"User.kt": "data class User(val id: String)"}),
        "core-network": AndroidModule("core-network", ModuleType.CORE_LIBRARY, ["core-model"], {"ApiClient.kt": "class ApiClient"}),
        "core-database": AndroidModule("core-database", ModuleType.CORE_LIBRARY, ["core-model"], {"AppDb.kt": "class AppDb"}),
        "feature-auth": AndroidModule("feature-auth", ModuleType.FEATURE_ANDROID, ["core-network", "core-model"], {"LoginViewModel.kt": "class LoginVM"}),
        "feature-payment": AndroidModule("feature-payment", ModuleType.FEATURE_DYNAMIC, ["core-network", "core-database"], {"PayProcessor.kt": "class Pay"}),
        "app": AndroidModule("app", ModuleType.APP_SHELL, ["feature-auth", "feature-payment", "core-model"], {"MainActivity.kt": "class MainActivity"})
    }

    # 2. Inisialisasi Graf Dependensi
    graph = DependencyGraph(modules)
    stages = graph.get_execution_stages()

    print(f"\n{TerminalColors.BOLD}[1] Analisis Topologi Modular Proyek:{TerminalColors.RESET}")
    for idx, stage in enumerate(stages, 1):
        print(f"  Stage {idx}: {', '.join([f'{m} ({modules[m].mod_type.value})' for m in stage])}")

    build_cache = GradleBuildCache()
    engine = GradleEngine(graph, build_cache)

    # 3. Skenario 1: Cold Build (Cache Kosong)
    print(f"\n{TerminalColors.BOLD}[2] Skenario: Cold Build (Belum Ada Cache){TerminalColors.RESET}")
    start_time = time.perf_counter()
    results_cold = engine.assemble(max_workers=3)
    wall_cold = time.perf_counter() - start_time
    print_build_results(results_cold, wall_cold)

    # 4. Skenario 2: Incremental Build Tanpa Perubahan (Daemon UP-TO-DATE)
    print(f"\n{TerminalColors.BOLD}[3] Skenario: Second Build Tanpa Perubahan Kode{TerminalColors.RESET}")
    start_time = time.perf_counter()
    results_uptodate = engine.assemble(max_workers=3)
    wall_uptodate = time.perf_counter() - start_time
    print_build_results(results_uptodate, wall_uptodate)

    # 5. Skenario 3: Modifikasi pada daun dependensi (Core Model diubah)
    print(f"\n{TerminalColors.BOLD}[4] Skenario: Mutasi Kode pada 'core-model' (Invalidasi Dependen){TerminalColors.RESET}")
    print(f"{TerminalColors.YELLOW}>> Memperbarui 'core-model/User.kt' -> Menambahkan field token...{TerminalColors.RESET}")
    modules["core-model"].source_files["User.kt"] = "data class User(val id: String, val token: String)"

    start_time = time.perf_counter()
    results_mutated = engine.assemble(max_workers=3)
    wall_mutated = time.perf_counter() - start_time
    print_build_results(results_mutated, wall_mutated)

    # 6. Skenario 4: Revert Kode (Menguji Gradle Build Cache Hit)
    print(f"\n{TerminalColors.BOLD}[5] Skenario: Revert Kode 'core-model' ke Versi Awal (Build Cache Test){TerminalColors.RESET}")
    print(f"{TerminalColors.YELLOW}>> Mengembalikan 'core-model/User.kt' ke hash awal...{TerminalColors.RESET}")
    modules["core-model"].source_files["User.kt"] = "data class User(val id: String)"
    
    # Reset in-memory daemon state untuk mensimulasikan sesi developer lain / remote machine
    engine.last_built_signatures.clear()

    start_time = time.perf_counter()
    results_cached = engine.assemble(max_workers=3)
    wall_cached = time.perf_counter() - start_time
    print_build_results(results_cached, wall_cached)

    print(f"\n{TerminalColors.CYAN}Statistik Gradle Build Cache:{TerminalColors.RESET}")
    print(f"  Cache Hits   : {TerminalColors.GREEN}{build_cache.hits}{TerminalColors.RESET}")
    print(f"  Cache Misses : {TerminalColors.RED}{build_cache.misses}{TerminalColors.RESET}")

    # 7. CI/CD Matrix Pipeline
    run_ci_cd_simulation(engine)

if __name__ == "__main__":
    main()