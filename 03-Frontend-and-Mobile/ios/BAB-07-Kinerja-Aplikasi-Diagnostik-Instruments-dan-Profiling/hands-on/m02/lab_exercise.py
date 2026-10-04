#!/usr/bin/env python3
"""
Lab Hands-on: iOS Performance Profiling & Instruments Diagnostic Engine
Topik: iOS (03-Frontend-and-Mobile)
Bab: 07 (Kinerja Aplikasi, Diagnostik Instruments, & Profiling) - Modul 02 Deep Dive

Simulasi komprehensif dari subsistem Apple Instruments:
1. Time Profiler Engine (Call-stack sampling, top-down call tree & weight calculation)
2. ARC Allocations & Leaks Instrument (Object graph traversal, strong reference cycle detection)
3. Core Animation Hitch Detector (VSync 60Hz/120Hz frame pacing, dropped frames & hitch ratio)
"""

import time
import random
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple

# --- ANSI Terminal Styling ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"
CLR_BG_DARK = "\033[100m"

# ============================================================================
# 1. ARC ALLOCATIONS & LEAKS INSTRUMENT SIMULATION
# ============================================================================

@dataclass
class HeapObject:
    """Merepresentasikan objek Objective-C / Swift heap dengan reference count."""
    address: str
    class_name: str
    size_bytes: int
    strong_references: Set[str] = field(default_factory=set)

class AllocationsAndLeaksEngine:
    """
    Mensimulasikan pelacakan memori ARC (Automatic Reference Counting)
    dan algoritma deteksi retain cycle menggunakan Directed Graph Cycle Detection.
    """
    def __init__(self):
        self.heap: Dict[str, HeapObject] = {}
        self.root_references: Set[str] = set()

    def allocate(self, address: str, class_name: str, size: int) -> None:
        self.heap[address] = HeapObject(address, class_name, size)

    def add_strong_reference(self, from_addr: str, to_addr: str) -> None:
        if from_addr in self.heap and to_addr in self.heap:
            self.heap[from_addr].strong_references.add(to_addr)

    def remove_strong_reference(self, from_addr: str, to_addr: str) -> None:
        if from_addr in self.heap:
            self.heap[from_addr].strong_references.discard(to_addr)

    def set_root(self, address: str, is_root: bool = True) -> None:
        if is_root:
            self.root_references.add(address)
        else:
            self.root_references.discard(address)

    def detect_leaks_and_retain_cycles(self) -> List[List[str]]:
        """
        Mendeteksi retain cycles: objek yang terisolasi dari UIWindow/Root
        tetapi memiliki referensi siklik kuat satu sama lain.
        """
        # Fase 1: Mark & Sweep reachability dari root objects
        reachable = set()
        queue = deque(self.root_references)
        while queue:
            curr = queue.popleft()
            if curr in self.heap and curr not in reachable:
                reachable.add(curr)
                for neighbor in self.heap[curr].strong_references:
                    if neighbor not in reachable:
                        queue.append(neighbor)

        unreachable = set(self.heap.keys()) - reachable

        # Fase 2: DFS untuk mendeteksi siklus pada unreached objects
        visited = set()
        rec_stack = []
        cycles = []

        def dfs(node: str, path: List[str]):
            visited.add(node)
            path.append(node)
            for neighbor in self.heap[node].strong_references:
                if neighbor in unreachable:
                    if neighbor in path:
                        cycle_start_idx = path.index(neighbor)
                        cycles.append(path[cycle_start_idx:] + [neighbor])
                    elif neighbor not in visited:
                        dfs(neighbor, path)
            path.pop()

        for node in unreachable:
            if node not in visited:
                dfs(node, [])

        return cycles

# ============================================================================
# 2. TIME PROFILER ENGINE (STACK SAMPLING)
# ============================================================================

@dataclass
class StackFrame:
    symbol: str
    library: str

class TimeProfilerEngine:
    """
    Mensimulasikan kernel-level sampling profiler (misal: 1ms interval)
    untuk membentuk Call Tree dan mengidentifikasi CPU Hotspots.
    """
    def __init__(self):
        self.samples: List[List[StackFrame]] = []
        self.total_samples = 0

    def record_sample(self, stack: List[StackFrame]) -> None:
        self.samples.append(stack)
        self.total_samples += 1

    def generate_call_tree(self) -> Dict[str, Dict]:
        """Agregasi sample menjadi Call Tree hierarkis dengan kalkulasi weight."""
        tree = {}
        for sample in self.samples:
            curr_level = tree
            for frame in sample:
                key = f"{frame.symbol} [{frame.library}]"
                if key not in curr_level:
                    curr_level[key] = {"_count": 0, "_children": {}}
                curr_level[key]["_count"] += 1
                curr_level = curr_level[key]["_children"]
        return tree

# ============================================================================
# 3. CORE ANIMATION & FRAME PACING ENGINE
# ============================================================================

@dataclass
class FramePacingEvent:
    frame_number: int
    target_budget_ms: float
    actual_duration_ms: float
    is_hitch: bool
    hitch_type: Optional[str] = None

class CoreAnimationMonitor:
    """
    Mensimulasikan CADisplayLink / Render Loop analysis untuk menghitung
    Hitch Time Ratio (ms/s) sesuai spesifikasi Apple HIG & WWDC.
    """
    def __init__(self, target_fps: int = 60):
        self.target_budget_ms = 1000.0 / target_fps
        self.frame_history: List[FramePacingEvent] = []

    def record_frame(self, frame_idx: int, duration_ms: float) -> FramePacingEvent:
        is_hitch = duration_ms > self.target_budget_ms
        hitch_type = None
        if is_hitch:
            if duration_ms > self.target_budget_ms * 2:
                hitch_type = "Severe Commit/Render Hitch"
            else:
                hitch_type = "Commit Hitch (Dropped VSync)"

        event = FramePacingEvent(
            frame_number=frame_idx,
            target_budget_ms=self.target_budget_ms,
            actual_duration_ms=duration_ms,
            is_hitch=is_hitch,
            hitch_type=hitch_type
        )
        self.frame_history.append(event)
        return event

    def compute_metrics(self) -> Dict[str, float]:
        total_time_ms = sum(f.actual_duration_ms for f in self.frame_history)
        hitch_duration_ms = sum(
            max(0.0, f.actual_duration_ms - f.target_budget_ms)
            for f in self.frame_history if f.is_hitch
        )
        total_seconds = total_time_ms / 1000.0 if total_time_ms > 0 else 1.0
        hitch_ratio = hitch_duration_ms / total_seconds  # ms per second

        return {
            "total_frames": len(self.frame_history),
            "hitches": sum(1 for f in self.frame_history if f.is_hitch),
            "total_time_ms": total_time_ms,
            "hitch_duration_ms": hitch_duration_ms,
            "hitch_ratio_ms_per_s": hitch_ratio
        }

# ============================================================================
# DIAGNOSTIC SESSION EXECUTION
# ============================================================================

def print_banner(text: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*80}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [INSTRUMENTS DIAGNOSTIC] {text.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*80}{CLR_RESET}")

def run_diagnostic_simulation():
    print_banner("Inisialisasi Tracing Target: FeedModule.app (iOS 17.4)")

    # 1. Alokasi Memori & Injeksi Retain Cycle
    alloc_engine = AllocationsAndLeaksEngine()
    print(f"{CLR_BLUE}[Allocations] Mengalokasikan node objek UI & ViewModel...{CLR_RESET}")

    alloc_engine.allocate("0x600001a1c", "RootNavigationController", 1024)
    alloc_engine.allocate("0x600001a40", "FeedViewController", 8192)
    alloc_engine.allocate("0x600001a88", "FeedViewModel", 2048)
    alloc_engine.allocate("0x600001ad0", "FeedCoordinator", 512)
    alloc_engine.allocate("0x600001b10", "NetworkService", 4096)
    alloc_engine.allocate("0x600001c00", "ImageCacheNode", 1048576) # 1 MB

    # Menghubungkan stack aktif (Root reachable)
    alloc_engine.set_root("0x600001a1c", True)
    alloc_engine.add_strong_reference("0x600001a1c", "0x600001a40") # Nav -> VC
    alloc_engine.add_strong_reference("0x600001a40", "0x600001a88") # VC -> VM
    alloc_engine.add_strong_reference("0x600001a88", "0x600001b10") # VM -> Network

    # Injeksi Retain Cycle: Closure capture kuat tanpa '[weak self]'
    alloc_engine.allocate("0x600002100", "ClosureCaptureContext", 256)
    alloc_engine.add_strong_reference("0x600001a88", "0x600002100") # VM -> Closure
    alloc_engine.add_strong_reference("0x600002100", "0x600001a40") # Closure -> VC (Cycle!)

    print(f"{CLR_GREEN}✓ Alokasi Objek & Dependency Graph terbentuk.{CLR_RESET}")

    # Simulasikan Pop ViewController dari Navigation Stack (Dealloc attempt)
    print(f"{CLR_YELLOW}[Navigation] User menekan 'Back': RootNavigationController memutus referensi FeedViewController.{CLR_RESET}")
    alloc_engine.remove_strong_reference("0x600001a1c", "0x600001a40")

    # Jalankan Leaks Detector
    leaks = alloc_engine.detect_leaks_and_retain_cycles()
    print_banner("Leaks & Allocations Instrument Report")
    if leaks:
        print(f"{CLR_RED}{CLR_BOLD}PERINGATAN: Ditemukan {len(leaks)} Retain Cycle(s)! Objek terisolasi dari Root tetap hidup di Heap:{CLR_RESET}\n")
        for idx, cycle in enumerate(leaks, 1):
            cycle_desc = " -> ".join([f"{alloc_engine.heap[addr].class_name} ({addr})" for addr in cycle])
            total_leak_bytes = sum(alloc_engine.heap[addr].size_bytes for addr in set(cycle))
            print(f" {CLR_RED}Cycle #{idx} (Total Leaked: {total_leak_bytes} bytes):{CLR_RESET}")
            print(f"   {CLR_YELLOW}Path:{CLR_RESET} {cycle_desc}")
            print(f"   {CLR_MAGENTA}Akar Masalah:{CLR_RESET} ClosureCaptureContext menahan referensi kuat balik ke FeedViewController.")
            print(f"   {CLR_GREEN}Rekomendasi Fix:{CLR_RESET} Gunakan '[weak self]' atau '[unowned self]' pada closure callback di FeedViewModel.\n")
    else:
        print(f"{CLR_GREEN}Status Bersih: Tidak ditemukan retain cycle.{CLR_RESET}")

    # 2. Time Profiler Simulation
    print_banner("Time Profiler Trace (Sampling Frekuensi: 1000 Hz / 1ms)")
    profiler = TimeProfilerEngine()

    call_patterns = [
        # Main Thread Smooth Run
        ([StackFrame("main", "UIKitCore"),
          StackFrame("UIApplicationMain", "UIKitCore"),
          StackFrame("CFRunLoopRunSpecific", "CoreFoundation"),
          StackFrame("__CFRunLoopDoSources0", "CoreFoundation"),
          StackFrame("layoutSubviews", "FeedModule")], 70),

        # CPU Hotspot 1: JSON Deserialization di Main Thread
        ([StackFrame("main", "UIKitCore"),
          StackFrame("UIApplicationMain", "UIKitCore"),
          StackFrame("CFRunLoopRunSpecific", "CoreFoundation"),
          StackFrame("tableView(_:cellForRowAt:)", "FeedModule"),
          StackFrame("JSONDecoder.decode", "Foundation"),
          StackFrame("_JSONKeyedDecodingContainer.decode", "Foundation")], 150),

        # CPU Hotspot 2: Regex parsing berulang tanpa caching
        ([StackFrame("main", "UIKitCore"),
          StackFrame("UIApplicationMain", "UIKitCore"),
          StackFrame("CFRunLoopRunSpecific", "CoreFoundation"),
          StackFrame("tableView(_:cellForRowAt:)", "FeedModule"),
          StackFrame("NSRegularExpression.matches", "Foundation"),
          StackFrame("uregex_matches", "libicucore.A.dylib")], 80),
    ]

    for stack, weight in call_patterns:
        for _ in range(weight):
            profiler.record_sample(stack)

    call_tree = profiler.generate_call_tree()

    def print_tree(node: Dict, depth: int = 0):
        for key, val in node.items():
            count = val["_count"]
            pct = (count / profiler.total_samples) * 100
            color = CLR_RED if pct > 30 else (CLR_YELLOW if pct > 10 else CLR_RESET)
            indent = "  " * depth
            print(f"{indent}├─ {color}{pct:5.1f}% [{count:3d} ms]{CLR_RESET} {key}")
            print_tree(val["_children"], depth + 1)

    print(f"{CLR_BOLD}Call Tree Hierarkis (Top-Down):{CLR_RESET}")
    print_tree(call_tree)
    print(f"\n{CLR_RED}{CLR_BOLD}Analisis Hotspot Time Profiler:{CLR_RESET}")
    print(f" - JSONDecoder.decode mengonsumsi {CLR_BOLD}50.0%{CLR_RESET} dari total thread execution time.")
    print(f" - NSRegularExpression mengonsumsi {CLR_BOLD}26.7%{CLR_RESET} karena inisialisasi berulang per cell.")
    print(f" {CLR_GREEN}Solusi:{CLR_RESET} Offload parsing ke `DispatchQueue.global(qos: .userInitiated)` dan cache compiled regex.")

    # 3. Core Animation & Hitch Detection
    print_banner("Core Animation Instrument (ProMotion 60Hz Target - Budget: 16.67ms)")
    ca_monitor = CoreAnimationMonitor(target_fps=60)

    # Mensimulasikan 12 frame scrolling list
    simulated_durations = [14.2, 15.1, 16.0, 34.5, 15.8, 14.9, 48.2, 16.2, 15.0, 14.8, 22.1, 15.5]

    print(f"{CLR_BOLD}{'Frame':<8} | {'Target (ms)':<12} | {'Actual (ms)':<12} | {'Delta (ms)':<12} | {'Status'}{CLR_RESET}")
    print("-" * 75)

    for idx, duration in enumerate(simulated_durations, start=1):
        event = ca_monitor.record_frame(idx, duration)
        delta = event.actual_duration_ms - event.target_budget_ms
        if event.is_hitch:
            status = f"{CLR_RED}{CLR_BOLD}HITCH DETECTED ({event.hitch_type}){CLR_RESET}"
            delta_str = f"{CLR_RED}+{delta:6.2f}{CLR_RESET}"
        else:
            status = f"{CLR_GREEN}PASSED{CLR_RESET}"
            delta_str = f"{CLR_GREEN}{delta:6.2f}{CLR_RESET}"

        print(f"#{event.frame_number:<7} | {event.target_budget_ms:<12.2f} | {event.actual_duration_ms:<12.2f} | {delta_str:<21} | {status}")

    metrics = ca_monitor.compute_metrics()
    hitch_ratio = metrics['hitch_ratio_ms_per_s']

    print(f"\n{CLR_BOLD}Metrik Hitch Core Animation (WWDC Metric):{CLR_RESET}")
    print(f" - Total Durasi Trace : {metrics['total_time_ms']:.2f} ms")
    print(f" - Total Frame Drop   : {metrics['hitches']} dari {metrics['total_frames']} frame")
    print(f" - Total Hitch Time   : {metrics['hitch_duration_ms']:.2f} ms")
    
    # Standar WWDC: < 5 ms/s = Good, 5-10 ms/s = Warning, > 10 ms/s = Critical
    rating_color = CLR_GREEN if hitch_ratio < 5 else (CLR_YELLOW if hitch_ratio <= 10 else CLR_RED)
    rating_label = "GOOD (Target Terpenuhi)" if hitch_ratio < 5 else ("WARNING" if hitch_ratio <= 10 else "CRITICAL (Scroll Stutter)")

    print(f" - Hitch Ratio        : {rating_color}{hitch_ratio:.2f} ms/s [{rating_label}]{CLR_RESET}")

    print_banner("Ringkasan Diagnostik & Action Item Engineering")
    print(f"""1. {CLR_RED}Memory Leak Fix:{CLR_RESET}
   Tambahkan `[weak self]` pada closure capture di FeedViewController.swift:line 84.
2. {CLR_YELLOW}Main Thread Starvation:{CLR_RESET}
   Pindahkan deserialisasi JSON ke background task menggunakan Swift Concurrency `Task.detached(priority: .userInitiated)`.
3. {CLR_CYAN}Rendering Optimization:{CLR_RESET}
   Hitch Frame #4 & #7 disebabkan oleh Offscreen Rendering. Pastikan `layer.masksToBounds = true` diganti dengan pre-rounded corner images.""")

if __name__ == "__main__":
    run_diagnostic_simulation()
    print(f"\n{CLR_BOLD}{CLR_GREEN}[✓] Diagnostik Instruments Selesai Tanpa Error.{CLR_RESET}\n")