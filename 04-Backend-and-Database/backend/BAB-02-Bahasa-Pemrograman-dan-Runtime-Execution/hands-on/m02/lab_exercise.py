#!/usr/bin/env python3
"""
================================================================================
LAB EXERCISE: RUNTIME EXECUTION & CONCURRENCY ARCHITECTURE SIMULATOR
BAB-02: Bahasa Pemrograman dan Runtime Execution
================================================================================
Simulasi tingkat lanjut mengenai karakteristik runtime execution backend:
1. Compiled vs JIT vs Interpreted Bytecode (Execution overhead)
2. Concurrency Models: Thread-per-Request vs Event-Loop vs M:N Green Threads
3. Memory Management: Reference Counting, Generational GC, dan Tri-Color Marking
4. Garbage Collection Pause (Stop-The-World vs Concurrent Sweep)
================================================================================
"""

import sys
import time
import math
import random
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

# --- ANSI Terminal Styling ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_DARK = "\033[100m"

def print_header(title: str):
    print(f"\n{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} ❯❯❯ {title.upper()} {Style.RESET}\n")

def print_sub(title: str):
    print(f"{Style.CYAN}{Style.BOLD}─── {title} ───{Style.RESET}")

def print_badge(label: str, val: str, color: str = Style.GREEN):
    print(f"  {Style.BOLD}[{label}]{Style.RESET} {color}{val}{Style.RESET}")

# --- Data Structures ---
@dataclass
class RuntimeMetrics:
    name: str
    runtime_type: str
    total_requests: int
    throughput_rps: float
    avg_latency_ms: float
    p99_latency_ms: float
    gc_pause_total_ms: float
    context_switch_cost_ms: float
    peak_memory_mb: float

# --- Runtime Engine Profiles ---
class RuntimeModel:
    def __init__(self, name: str, rtype: str, jit: bool, gc_type: str, concurrency_model: str):
        self.name = name
        self.rtype = rtype
        self.jit = jit
        self.gc_type = gc_type
        self.concurrency_model = concurrency_model

    def simulate_workload(self, num_requests: int, cpu_intensity: float, io_wait_ms: float) -> RuntimeMetrics:
        # Base latency based on compilation model
        if self.rtype == "Interpreted (CPython)":
            base_cpu_time = 0.85 * (1.0 + cpu_intensity * 3.5)
            gc_pause_prob = 0.04
            gc_pause_dur = random.uniform(2.0, 8.0)
            mem_overhead_per_req = 0.08
            ctx_switch_penalty = 0.05
        elif self.rtype == "JIT-Compiled (V8/Node.js)":
            base_cpu_time = 0.22 * (1.0 + cpu_intensity * 1.8)
            gc_pause_prob = 0.02
            gc_pause_dur = random.uniform(1.0, 4.0)
            mem_overhead_per_req = 0.05
            ctx_switch_penalty = 0.008  # single-thread event loop
        elif self.rtype == "Ahead-Of-Time (Go Runtime)":
            base_cpu_time = 0.07 * (1.0 + cpu_intensity * 0.9)
            gc_pause_prob = 0.008
            gc_pause_dur = random.uniform(0.1, 0.8) # sub-millisecond tri-color GC
            mem_overhead_per_req = 0.015
            ctx_switch_penalty = 0.002  # lightweight M:N goroutine switch
        else:
            base_cpu_time = 0.5
            gc_pause_prob = 0.02
            gc_pause_dur = 1.0
            mem_overhead_per_req = 0.03
            ctx_switch_penalty = 0.01

        latencies = []
        total_gc_pause = 0.0
        total_ctx_cost = 0.0

        for _ in range(num_requests):
            # Request processing time calculation
            req_latency = base_cpu_time + io_wait_ms + random.gauss(0.1, 0.05)
            
            # Context switch cost
            ctx_cost = ctx_switch_penalty * random.uniform(0.8, 1.2)
            req_latency += ctx_cost
            total_ctx_cost += ctx_cost

            # Stop-the-world or incremental GC pause simulation
            if random.random() < gc_pause_prob:
                pause = gc_pause_dur * random.uniform(0.9, 1.5)
                req_latency += pause
                total_gc_pause += pause

            latencies.append(max(0.1, req_latency))

        latencies.sort()
        avg_lat = sum(latencies) / len(latencies)
        p99_idx = int(len(latencies) * 0.99)
        p99_lat = latencies[p99_idx]
        
        # Concurrency throughput derivation (Little's Law approximation)
        concurrency_factor = 200.0 if "M:N" in self.concurrency_model else (120.0 if "Event" in self.concurrency_model else 35.0)
        throughput = (concurrency_factor / (avg_lat / 1000.0)) * random.uniform(0.92, 1.05)
        peak_mem = 45.0 + (num_requests * mem_overhead_per_req * random.uniform(0.7, 1.1))

        return RuntimeMetrics(
            name=self.name,
            runtime_type=self.rtype,
            total_requests=num_requests,
            throughput_rps=round(throughput, 1),
            avg_latency_ms=round(avg_lat, 2),
            p99_latency_ms=round(p99_lat, 2),
            gc_pause_total_ms=round(total_gc_pause, 2),
            context_switch_cost_ms=round(total_ctx_cost, 2),
            peak_memory_mb=round(peak_mem, 1)
        )

# --- Visualization Utilities ---
def render_bar(val: float, max_val: float, width: int = 30, color: str = Style.GREEN) -> str:
    filled = int(min(1.0, val / max_val if max_val > 0 else 0) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{color}{bar}{Style.RESET}"

def render_comparison_table(metrics_list: List[RuntimeMetrics]):
    max_tps = max(m.throughput_rps for m in metrics_list)
    max_p99 = max(m.p99_latency_ms for m in metrics_list)
    max_mem = max(m.peak_memory_mb for m in metrics_list)

    print(f"\n{Style.BOLD}{'Runtime Engine':<24} {'Throughput (RPS)':<20} {'Avg / P99 (ms)':<18} {'Total GC (ms)':<15} {'Memory':<10}{Style.RESET}")
    print(f"{Style.DIM}{'─' * 88}{Style.RESET}")

    for m in metrics_list:
        color = Style.GREEN if "Go" in m.name else (Style.YELLOW if "V8" in m.name else Style.CYAN)
        tps_str = f"{m.throughput_rps:,.0f} req/s"
        lat_str = f"{m.avg_latency_ms:.1f} / {m.p99_latency_ms:.1f} ms"
        gc_str = f"{m.gc_pause_total_ms:.1f} ms"
        mem_str = f"{m.peak_memory_mb:.1f} MB"
        print(f"{color}{Style.BOLD}{m.name:<24}{Style.RESET} {tps_str:<20} {lat_str:<18} {gc_str:<15} {mem_str:<10}")
        print(f"  {Style.DIM}TPS:{Style.RESET} {render_bar(m.throughput_rps, max_tps, 24, color)}  {Style.DIM}P99:{Style.RESET} {render_bar(m.p99_latency_ms, max_p99, 18, Style.RED)}")

# --- Interactive Modules ---
def module_benchmark_comparison():
    print_header("Simulasi Komparasi Runtime Engine Produksi")
    print("Menganalisis performa 3 model arsitektur runtime backend dengan 5,000 concurrent requests:\n")
    print(f"  1. {Style.CYAN}CPython 3.12{Style.RESET}: Interpreted Bytecode + GIL + Ref Count & Gen GC (OS Threads)")
    print(f"  2. {Style.YELLOW}V8 (Node.js 20){Style.RESET}: JIT Compilation + Single-thread Event Loop + Generational GC")
    print(f"  3. {Style.GREEN}Go Runtime 1.22{Style.RESET}: Native Machine Code + M:N Work-stealing Scheduler + Concurrent Tri-Color GC\n")

    runtimes = [
        RuntimeModel("CPython 3.12", "Interpreted (CPython)", jit=False, gc_type="Ref Count + Gen 0/1/2", concurrency_model="1:1 OS Thread"),
        RuntimeModel("V8 / Node.js 20", "JIT-Compiled (V8/Node.js)", jit=True, gc_type="Scavenger + Mark-Sweep", concurrency_model="Single-thread Event Loop"),
        RuntimeModel("Go Runtime 1.22", "Ahead-Of-Time (Go Runtime)", jit=False, gc_type="Concurrent Tri-color Mark/Sweep", concurrency_model="M:N Green Threads")
    ]

    print(f"{Style.DIM}Melakukan simulasi beban kerja (CPU mixed with I/O wait 3.5ms)...{Style.RESET}")
    for _ in range(12):
        sys.stdout.write(f"{Style.MAGENTA}▓{Style.RESET}")
        sys.stdout.flush()
        time.sleep(0.04)
    print(" [Selesai!]\n")

    results = [rt.simulate_workload(num_requests=5000, cpu_intensity=0.6, io_wait_ms=3.5) for rt in runtimes]
    render_comparison_table(results)

def module_gc_deep_dive():
    print_header("Deep-Dive: Garbage Collector & Stop-The-World (STW) Pauses")
    print("Perbandingan perilaku alokasi objek heap dan jeda GC saat memori melonjak:\n")

    phases = [
        ("CPython Generational GC", [
            ("Gen 0 Allocation (Threshold reached)", 1.2, Style.YELLOW),
            ("Gen 1 Promotion & Collection", 3.8, Style.MAGENTA),
            ("Gen 2 Full Collection (Stop-The-World)", 14.5, Style.RED)
        ]),
        ("V8 Oilpan & Orinoco (Node.js)", [
            ("Scavenger Young Generation Minor GC", 0.8, Style.GREEN),
            ("Concurrent Marking (Background thread)", 0.2, Style.CYAN),
            ("Incremental Major Mark-Sweep-Compact", 2.4, Style.YELLOW)
        ]),
        ("Go Tri-Color Concurrent GC", [
            ("Mark Setup (STW < 20 microseconds)", 0.02, Style.GREEN),
            ("Concurrent Mark Phase (Mutator Assist)", 0.15, Style.GREEN),
            ("Mark Termination (STW < 25 microseconds)", 0.03, Style.GREEN)
        ])
    ]

    for engine, steps in phases:
        print_sub(engine)
        for step_name, latency_ms, color in steps:
            bar = render_bar(latency_ms, 15.0, 30, color)
            print(f"  {step_name:<45} {color}{latency_ms:>6.2f} ms{Style.RESET} {bar}")
        print()

def module_scheduler_simulation():
    print_header("Visualisasi Concurrency Runtime Scheduler (M:N Work-Stealing)")
    print("Melihat bagaimana Go Runtime memetakan Goroutines (G) ke OS Threads (M) via Logical Processors (P):\n")

    num_processors = 4
    goroutines = [f"G-{random.randint(100, 999)}" for _ in range(16)]
    
    print(f"{Style.BOLD}Logical Processors (P = GOMAXPROCS = {num_processors}):{Style.RESET}")
    for p_id in range(num_processors):
        assigned_g = [goroutines[i] for i in range(p_id, len(goroutines), num_processors)]
        q_visual = " ➜ ".join([f"{Style.GREEN}{g}{Style.RESET}" for g in assigned_g])
        print(f"  {Style.CYAN}P{p_id}{Style.RESET} (Bound to M{p_id} OS-Thread): [Local Run Queue] {q_visual}")
    
    print(f"\n{Style.YELLOW}Simulasi Work-Stealing Event:{Style.RESET}")
    print(f"  • P1 menyelesaikan semua antrian lokal (Starvation detected).")
    print(f"  • P1 melakukan sysmon probe dan mencuri 50% G dari antrian P3: {Style.BOLD}Work-Stealing Success!{Style.RESET}")
    print(f"  • Hasil: Utilisasi CPU core merata tanpa overhead kernel context switch.\n")

def run_all_interactive():
    print(f"{Style.BOLD}{Style.MAGENTA}===================================================================={Style.RESET}")
    print(f"{Style.BOLD}{Style.WHITE}   BAB-02: RUNTIME EXECUTION & CONCURRENCY LAB EXERCISE SIMULATOR   {Style.RESET}")
    print(f"{Style.BOLD}{Style.MAGENTA}===================================================================={Style.RESET}")
    print(f"{Style.DIM}Platform Environment: Python {sys.version.split()[0]} on {sys.platform}{Style.RESET}\n")

    menu_options = [
        ("1", "Jalankan Benchmark Komparasi Lengkap (CPython vs V8 vs Go Runtime)"),
        ("2", "Simulasi Analisis Garbage Collection & Stop-The-World Latency"),
        ("3", "Visualisasi Concurrency M:N Scheduler & Work-Stealing Algorithm"),
        ("4", "Jalankan Semua Modul (Comprehensive Executive Summary)"),
        ("5", "Keluar (Exit)")
    ]

    # Non-interactive fallback check
    if not sys.stdin.isatty():
        print(f"{Style.YELLOW}Non-interactive terminal detected. Menjalankan Comprehensive Executive Summary otomatis...{Style.RESET}\n")
        module_benchmark_comparison()
        module_gc_deep_dive()
        module_scheduler_simulation()
        print(f"{Style.GREEN}{Style.BOLD}✔ Simulasi Arsitektur Runtime Selesai dengan Sukses.{Style.RESET}\n")
        return

    while True:
        print_sub("Main Menu Pilihan Lab")
        for key, desc in menu_options:
            print(f"  {Style.BOLD}{key}.{Style.RESET} {desc}")
        
        try:
            choice = input(f"\n{Style.BOLD}Pilih opsi [1-5]: {Style.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari program.")
            break

        if choice == "1":
            module_benchmark_comparison()
        elif choice == "2":
            module_gc_deep_dive()
        elif choice == "3":
            module_scheduler_simulation()
        elif choice == "4":
            module_benchmark_comparison()
            module_gc_deep_dive()
            module_scheduler_simulation()
            print(f"{Style.GREEN}{Style.BOLD}✔ Seluruh skenario telah dieksekusi.{Style.RESET}\n")
        elif choice == "5":
            print(f"\n{Style.CYAN}Terima kasih! Sampai jumpa di lab exercise berikutnya.{Style.RESET}\n")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan coba lagi.{Style.RESET}\n")

if __name__ == "__main__":
    run_all_interactive()
