#!/usr/bin/env python3
"""
Simulasi Teknis Interaktif: Go Profiling, Tracing, & Performance Engineering
Topik: BAB-05-Profiling-Tracing-Performance-Engineering
Menyimulasikan mekanisme internal runtime Go:
- pprof CPU Sampling & Call-Stack Aggregation
- Heap Profiler & Escape Analysis (Stack vs Heap Allocation)
- Go Execution Tracer (M:N Scheduler & GC Stop-The-World Phases)
- Mutex / Block Contention Profiling & sync.Pool Benchmark
"""

import time
import random
import sys
from dataclasses import dataclass, field
from typing import List, Dict

# ANSI Terminal Colors
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
RESET = "\033[0m"
DIM = "\033[2m"

def print_header(title: str):
    print("\n" + "=" * 65)
    print(f"{BOLD}{CYAN}>>> {title} <<<{RESET}")
    print("=" * 65)

def print_sub(title: str):
    print(f"\n{BOLD}{YELLOW}--- {title} ---{RESET}")

@dataclass
class StackSample:
    func_name: str
    flat_time_ms: float
    cum_time_ms: float
    samples_count: int

class CpuProfilerSimulator:
    """Simulasi pprof CPU Sampling (100Hz default di Go runtime)."""
    def __init__(self, sample_rate_hz: int = 100):
        self.sample_rate_hz = sample_rate_hz
        self.samples: Dict[str, StackSample] = {}

    def run_profiling(self, duration_sec: float = 1.0):
        print(f"{DIM}[Runtime] SIGPROF handler aktif pada rate {self.sample_rate_hz}Hz (interval {1000/self.sample_rate_hz:.1f}ms)...{RESET}")
        functions = [
            ("runtime.mallocgc", 0.35, 0.40),
            ("main.processData", 0.30, 0.75),
            ("crypto/sha256.block", 0.20, 0.20),
            ("net/http.(*conn).serve", 0.05, 0.95),
            ("runtime.findrunnable", 0.10, 0.10),
        ]
        
        total_ticks = int(duration_sec * self.sample_rate_hz)
        for _ in range(total_ticks):
            fn, flat_w, cum_w = random.choice(functions)
            if fn not in self.samples:
                self.samples[fn] = StackSample(func_name=fn, flat_time_ms=0.0, cum_time_ms=0.0, samples_count=0)
            self.samples[fn].samples_count += 1
            self.samples[fn].flat_time_ms += flat_w * (1000 / self.sample_rate_hz)
            self.samples[fn].cum_time_ms += cum_w * (1000 / self.sample_rate_hz)

    def display_top(self):
        print_header("go tool pprof: (top10 -cum)")
        print(f"{'Showing nodes accounting for sample time in Go runtime':<60}")
        print(f"{BOLD}{'Flat(ms)':>10} {'Flat%':>8} {'Cum(ms)':>10} {'Cum%':>8}  {'Function':<30}{RESET}")
        print("-" * 70)
        
        total_flat = sum(s.flat_time_ms for s in self.samples.values()) or 1.0
        sorted_samples = sorted(self.samples.values(), key=lambda s: s.cum_time_ms, reverse=True)
        
        for s in sorted_samples:
            flat_pct = (s.flat_time_ms / total_flat) * 100
            cum_pct = (s.cum_time_ms / total_flat) * 100
            color = RED if flat_pct > 25 else (YELLOW if flat_pct > 10 else GREEN)
            print(f"{color}{s.flat_time_ms:10.2f} {flat_pct:7.2f}% {s.cum_time_ms:10.2f} {cum_pct:7.2f}%{RESET}  {s.func_name:<30}")

class EscapeAnalysisSimulator:
    """Simulasi Go Compiler Escape Analysis (`go build -gcflags='-m'`)."""
    def run(self):
        print_header("Go Compiler: Escape Analysis Simulation (-gcflags='-m')")
        cases = [
            ("make([]byte, 64)", "Stack", "Ukuran kecil (<64KB) & tidak lolos pointer referensi ke luar scope", False),
            ("make([]byte, 128*1024)", "Heap", "Ukuran melebihi stack frame limit (128KB > 64KB threshold)", True),
            ("&User{ID: 101, Name: 'Gopher'}", "Heap", "Pointer dikembalikan ke luar caller stack (escapes to heap)", True),
            ("fmt.Println(val)", "Heap", "Parameter diformat ke interface{} kosong (any) -> runtime escape", True),
            ("buf := [32]byte{}; buf[0]=1", "Stack", "Fixed-size array, alamat memori tidak bocor", False),
        ]
        
        for expr, dest, reason, escapes in cases:
            badge = f"{RED}[ESCAPES TO HEAP]{RESET}" if escapes else f"{GREEN}[STAYS ON STACK]{RESET}"
            print(f"{BOLD}Ekspresi:{RESET} {CYAN}{expr}{RESET}")
            print(f"  Lokasi: {badge} -> Alokasi di: {BOLD}{dest}{RESET}")
            print(f"  Analisis: {DIM}{reason}{RESET}\n")

class ExecutionTracerSimulator:
    """Simulasi Go Execution Tracer (`go tool trace`)."""
    def run(self):
        print_header("go tool trace: Goroutine & GC Scheduler Timeline")
        procs = 4  # GOMAXPROCS
        print(f"{BOLD}Status: GOMAXPROCS = {procs}{RESET}")
        timeline_events = [
            (0.0, "P0", "G1 (main.worker)", "Running", GREEN),
            (0.5, "P1", "G2 (net/http.read)", "Waiting on Syscall", YELLOW),
            (1.2, "GC", "MARK WORK PHASE", "STW: Mark Termination (28µs)", RED),
            (1.8, "P2", "G3 (sync.WaitGroup)", "Runnable -> Running", CYAN),
            (2.4, "P3", "G4 (json.Unmarshal)", "Blocked on Mutex", MAGENTA),
            (3.0, "GC", "SWEEP PHASE", "Concurrent Sweep Worker active", BLUE),
        ]
        
        print(f"{BOLD}{'Timestamp':<12} {'Proc/Unit':<10} {'Entity':<24} {'Event Status'}{RESET}")
        print("-" * 65)
        for ts, p, entity, event, col in timeline_events:
            time.sleep(0.05)
            print(f"{ts:>6.2f}ms     {BOLD}{p:<10}{RESET} {entity:<24} {col}{event}{RESET}")
        
        print(f"\n{BOLD}Diagnostik Tracer:{RESET}")
        print(f" - Latensi STW (Stop The World): {GREEN}28 µs (Low GC Overhead){RESET}")
        print(f" - Processor Utilization: {CYAN}84.2% across 4 P (Sched optimal){RESET}")

class MutexContentionSimulator:
    """Simulasi Block & Mutex Profiler (runtime.SetMutexProfileFraction)."""
    def run(self):
        print_header("Mutex Contention Profiler: sync.Mutex vs sync.RWMutex")
        print(f"{DIM}Mengukur waktu goroutine tidur (sleep/block) menunggu lock release...{RESET}")
        
        scenarios = [
            ("sync.Mutex (Unoptimized)", 1000, 42.5, "Serialisasi ketat pada read-heavy workload"),
            ("sync.RWMutex (Read-optimized)", 1000, 3.8, "Shared lock untuk concurrent readers"),
            ("sync.Pool (Zero-alloc reuse)", 1000, 0.4, "Menghilangkan alokasi lock dan pointer GC contention"),
        ]
        
        print(f"{BOLD}{'Strategi Sinkronisasi':<32} {'Ops/sec':<10} {'Wait Delay (ms)':<18} {'Catatan':<20}{RESET}")
        print("-" * 85)
        for name, ops, delay, note in scenarios:
            color = RED if delay > 20 else (YELLOW if delay > 1 else GREEN)
            print(f"{CYAN}{name:<32}{RESET} {ops:<10} {color}{delay:>10.2f} ms{RESET}     {DIM}{note}{RESET}")

def main_menu():
    cpu_prof = CpuProfilerSimulator()
    escape_sim = EscapeAnalysisSimulator()
    trace_sim = ExecutionTracerSimulator()
    mutex_sim = MutexContentionSimulator()

    while True:
        print("\n" + "=" * 65)
        print(f"{BOLD}{MAGENTA}   LAB PRAKTIKUM GOLANG PERFORMANCE ENGINEERING (BAB 05){RESET}")
        print("=" * 65)
        print(f" {BOLD}1.{RESET} Simulasi pprof CPU Profiler (Sampling Call-Stacks)")
        print(f" {BOLD}2.{RESET} Simulasi Compiler Escape Analysis (Stack vs Heap)")
        print(f" {BOLD}3.{RESET} Simulasi Execution Tracer (M:N Sched & GC STW)")
        print(f" {BOLD}4.{RESET} Simulasi Mutex & Block Contention Profiler")
        print(f" {BOLD}5.{RESET} Jalankan Seluruh Demonstrasi (Benchmark Lengkap)")
        print(f" {BOLD}6.{RESET} Keluar (Exit)")
        print("-" * 65)
        
        choice = input(f"{BOLD}{CYAN}Pilih opsi [1-6]: {RESET}").strip()
        
        if choice == "1":
            cpu_prof.run_profiling(duration_sec=0.5)
            cpu_prof.display_top()
        elif choice == "2":
            escape_sim.run()
        elif choice == "3":
            trace_sim.run()
        elif choice == "4":
            mutex_sim.run()
        elif choice == "5":
            print(f"\n{BOLD}{GREEN}>>> MENJALANKAN PIPELINE LENGKAP PROFILING & BENCHMARK <<<{RESET}")
            cpu_prof.run_profiling(duration_sec=0.5)
            cpu_prof.display_top()
            escape_sim.run()
            trace_sim.run()
            mutex_sim.run()
            print(f"\n{BOLD}{GREEN}[PASS] Semua modul profiling berhasil disimulasikan secara konsisten.{RESET}")
        elif choice == "6" or choice.lower() in ("q", "exit"):
            print(f"{GREEN}Lab selesai. Selamat belajar performance engineering!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan ulangi.{RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Mode non-interaktif untuk CI/automated test
        sim = CpuProfilerSimulator()
        sim.run_profiling(0.2)
        sim.display_top()
        EscapeAnalysisSimulator().run()
        ExecutionTracerSimulator().run()
        MutexContentionSimulator().run()
    else:
        try:
            main_menu()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Sesi dihentikan pengguna.{RESET}")
