#!/usr/bin/env python3
"""
Lab Hands-on: JavaScript Performance Engineering, Profiling & Telemetry
Topic: V8 Inline Caching (Shapes/Hidden Classes), Event Loop Delay & CPU Telemetry
Category: 02-Programming-Languages / Chapter 09 - Modul 02 Deep Dive

Simulasi ini merekonstruksi mekanisme performa internal JavaScript (V8 Engine):
1. Shapes (Hidden Classes) & Inline Cache (IC) State Transition (Monomorphic vs Megamorphic).
2. Event Loop Lag Monitoring & Long Task Detection (PerformanceObserver mock).
3. Telemetry Profiler: Histogram latensi mikro-task dan sampling GC pause.
"""

import time
import random
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ANSI Terminal Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"

# ============================================================================
# 1. SIMULASI V8 ENGINE: HIDDEN CLASSES (SHAPES) & INLINE CACHES (IC)
# ============================================================================

class Shape:
    """
    Merepresentasikan Hidden Class / Shape di V8.
    Menyimpan offset memori dari setiap properti objek secara transisional.
    """
    def __init__(self, parent: Optional['Shape'] = None, added_prop: Optional[str] = None):
        self.transitions: Dict[str, 'Shape'] = {}
        self.offsets: Dict[str, int] = dict(parent.offsets) if parent else {}
        if added_prop:
            self.offsets[added_prop] = len(self.offsets)

    def transition(self, prop: str) -> 'Shape':
        if prop not in self.transitions:
            self.transitions[prop] = Shape(parent=self, added_prop=prop)
        return self.transitions[prop]

ROOT_SHAPE = Shape()

class JSObject:
    """Objek JavaScript yang menyimpan referensi ke Shape dan slot penyimpanan properti."""
    def __init__(self):
        self.shape: Shape = ROOT_SHAPE
        self.slots: List[any] = []

    def set_property(self, prop: str, value: any):
        if prop not in self.shape.offsets:
            self.shape = self.shape.transition(prop)
            self.slots.append(value)
        else:
            self.slots[self.shape.offsets[prop]] = value

class InlineCache:
    """
    Simulasi Inline Cache (IC) pada titik eksekusi akses properti (obj.x).
    Status transisi: UNINITIALIZED -> MONOMORPHIC -> POLYMORPHIC -> MEGAMORPHIC
    """
    STATE_UNINITIALIZED = "UNINITIALIZED"
    STATE_MONOMORPHIC = "MONOMORPHIC"
    STATE_POLYMORPHIC = "POLYMORPHIC"
    STATE_MEGAMORPHIC = "MEGAMORPHIC"

    def __init__(self, prop_name: str):
        self.prop_name = prop_name
        self.state = self.STATE_UNINITIALIZED
        self.cached_shapes: Dict[Shape, int] = {}
        self.hits = 0
        self.misses = 0

    def load(self, obj: JSObject):
        # 1. Fast Path: Cache Hit
        if obj.shape in self.cached_shapes:
            self.hits += 1
            slot = self.cached_shapes[obj.shape]
            return obj.slots[slot]

        # 2. Slow Path: Cache Miss & IC State Machine Transition
        self.misses += 1
        if self.prop_name not in obj.shape.offsets:
            return None

        slot = obj.shape.offsets[self.prop_name]

        if self.state == self.STATE_UNINITIALIZED:
            self.cached_shapes[obj.shape] = slot
            self.state = self.STATE_MONOMORPHIC
        elif self.state == self.STATE_MONOMORPHIC:
            self.cached_shapes[obj.shape] = slot
            self.state = self.STATE_POLYMORPHIC
        elif self.state == self.STATE_POLYMORPHIC:
            if len(self.cached_shapes) >= 4:  # Threshold V8 sebelum deoptimisasi ke dictionary
                self.state = self.STATE_MEGAMORPHIC
                self.cached_shapes.clear()  # Megamorphic beralih ke global stub lookup
            else:
                self.cached_shapes[obj.shape] = slot

        # Megamorphic access menembus hash lookup tanpa cache lokal
        return obj.slots[slot]

# ============================================================================
# 2. SIMULASI EVENT LOOP, TELEMETRY & LONG TASK PROFILER
# ============================================================================

@dataclass
class PerformanceEntry:
    name: str
    entry_type: str
    start_time: float
    duration_ms: float

class EventLoopTelemetry:
    """
    Telemetry Collector yang memonitor Event Loop Lag dan Long Tasks (>50ms standard W3C).
    """
    def __init__(self, long_task_threshold_ms: float = 50.0):
        self.long_task_threshold_ms = long_task_threshold_ms
        self.entries: List[PerformanceEntry] = []
        self.lag_measurements: List[float] = []

    def record_task(self, name: str, duration_ms: float, start_time: float):
        entry_type = "longtask" if duration_ms >= self.long_task_threshold_ms else "task"
        entry = PerformanceEntry(name, entry_type, start_time, duration_ms)
        self.entries.append(entry)

    def record_lag(self, lag_ms: float):
        self.lag_measurements.append(lag_ms)

    def get_summary(self) -> Dict[str, float]:
        if not self.lag_measurements:
            return {}
        sorted_lag = sorted(self.lag_measurements)
        return {
            "p50": statistics.median(sorted_lag),
            "p95": sorted_lag[int(len(sorted_lag) * 0.95)],
            "p99": sorted_lag[int(len(sorted_lag) * 0.99)],
            "max": max(sorted_lag),
            "long_tasks": len([e for e in self.entries if e.entry_type == "longtask"])
        }

# ============================================================================
# 3. BENCHMARK & EXPERIMENT EXECUTION
# ============================================================================

def benchmark_inline_caching():
    """
    Menguji performa akses properti: Monomorphic vs Megamorphic IC.
    """
    print(f"\n{BOLD}{CYAN}=== EXPERIMENT 1: V8 Inline Caching (IC) Optimization ==={RESET}")
    
    # Skenario 1: Monomorphic (Objek memiliki bentuk/shape yang seragam)
    mono_objects = []
    for _ in range(100_000):
        o = JSObject()
        o.set_property("x", 10)
        o.set_property("y", 20)
        mono_objects.append(o)

    mono_ic = InlineCache("x")
    t0 = time.perf_counter()
    for obj in mono_objects:
        _ = mono_ic.load(obj)
    mono_time = (time.perf_counter() - t0) * 1000

    # Skenario 2: Megamorphic (Bentuk objek bervariasi secara liar / anti-pattern)
    mega_objects = []
    prop_names = ["a", "b", "c", "d", "e", "f", "g", "h"]
    for i in range(100_000):
        o = JSObject()
        # Randomisasi urutan definisi properti menciptakan Hidden Class unik
        chosen_props = random.sample(prop_names, 4)
        for p in chosen_props:
            o.set_property(p, 1)
        o.set_property("x", 99)  # Target properti
        mega_objects.append(o)

    mega_ic = InlineCache("x")
    t0 = time.perf_counter()
    for obj in mega_objects:
        _ = mega_ic.load(obj)
    mega_time = (time.perf_counter() - t0) * 1000

    # Hasil
    print(f"[{GREEN}MONOMORPHIC{RESET}] Shape count: {len(mono_ic.cached_shapes)} | "
          f"Status: {BOLD}{mono_ic.state}{RESET} | Durasi: {mono_time:.2f}ms | "
          f"Hit Ratio: {(mono_ic.hits / (mono_ic.hits + mono_ic.misses))*100:.2f}%")
    print(f"[{RED}MEGAMORPHIC{RESET}] Shape count: {len(mega_ic.cached_shapes)} | "
          f"Status: {BOLD}{mega_ic.state}{RESET} | Durasi: {mega_time:.2f}ms | "
          f"Hit Ratio: {(mega_ic.hits / (mega_ic.hits + mega_ic.misses))*100:.2f}%")
    
    overhead = ((mega_time - mono_time) / mono_time) * 100
    print(f"-> Degradasi Performa Megamorphic: {YELLOW}+{overhead:.2f}% overhead{RESET}")


def run_event_loop_telemetry_simulation():
    """
    Mensimulasikan Event Loop runtime yang memproses Microtasks, I/O Tasks,
    Garbage Collection pauses, dan mendeteksi Long Task Latency.
    """
    print(f"\n{BOLD}{CYAN}=== EXPERIMENT 2: Event Loop Lag & Telemetry Profiling ==={RESET}")
    telemetry = EventLoopTelemetry(long_task_threshold_ms=25.0)  # Skala simulasi (25ms)

    simulated_tasks = [
        ("API_Req_FetchUser", 3.2),
        ("JSON_Parse_Payload", 5.8),
        ("DOM_Render_Batch", 14.1),
        ("Sync_Crypto_Heavy", 48.7),    # Long Task (Blokir Event Loop)
        ("Promise_Resolve_Chain", 2.1),
        ("GC_Scavenge_Ephemeron", 8.4),
        ("GC_Full_Mark_Sweep", 62.3),    # Major GC Pause (Long Task)
        ("WebSocket_Frame_Dispatch", 4.0),
        ("Canvas_Matrix_Calc", 29.5)     # Long Task
    ]

    print(f"{BOLD}Simulasi 20 siklus Event Loop dengan variasi beban kerja...{RESET}")
    current_sim_time = 0.0

    for cycle in range(1, 21):
        task_name, duration = random.choice(simulated_tasks)
        
        # Sintesis fluktuasi jitter dan scheduling delay
        jitter = random.uniform(0.1, 2.5)
        total_duration = duration + jitter
        
        start_time = current_sim_time
        telemetry.record_task(task_name, total_duration, start_time)

        # Hitung simulated Event Loop Delay (lag akumulatif terhadap target interval)
        simulated_lag = total_duration * random.uniform(0.15, 0.45)
        telemetry.record_lag(simulated_lag)
        
        current_sim_time += total_duration

        # Logging Long Tasks secara real-time
        if total_duration >= telemetry.long_task_threshold_ms:
            print(f"  {RED}[WARN: LONG TASK]{RESET} Cycle {cycle:02d}: "
                  f"'{BOLD}{task_name}{RESET}' menyita loop selama {total_duration:.2f}ms!")

    # Analisis Telemetri
    summary = telemetry.get_summary()
    print(f"\n{BOLD}{MAGENTA}--- Ringkasan Telemetri Performa Runtime ---{RESET}")
    print(f"Total Tasks Terproses   : {len(telemetry.entries)}")
    print(f"Terdeteksi Long Tasks   : {RED}{summary['long_tasks']}{RESET}")
    print(f"Event Loop Delay (p50)  : {GREEN}{summary['p50']:.2f}ms{RESET}")
    print(f"Event Loop Delay (p95)  : {YELLOW}{summary['p95']:.2f}ms{RESET}")
    print(f"Event Loop Delay (p99)  : {RED}{summary['p99']:.2f}ms{RESET}")
    print(f"Max Lag Spike           : {BOLD}{RED}{summary['max']:.2f}ms{RESET}")


def main():
    print(f"{BOLD}{BLUE}==============================================================={RESET}")
    print(f"{BOLD}{BLUE}  ADVANCED JAVASCRIPT PERFORMANCE ENGINEERING & TELEMETRY LAB  {RESET}")
    print(f"{BOLD}{BLUE}==============================================================={RESET}")
    
    benchmark_inline_caching()
    run_event_loop_telemetry_simulation()
    
    print(f"\n{BOLD}{GREEN}Lab selesai. Semua metrik telemetri telah dikompilasi.{RESET}\n")

if __name__ == "__main__":
    main()