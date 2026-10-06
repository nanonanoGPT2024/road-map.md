#!/usr/bin/env python3
"""
Lab Exercise: Android Performance Profiling, Memory Leaks, & Benchmarking Simulator
BAB-09: Performance Profiling, Memory Leaks, dan Benchmarking
"""

import sys
import time
import math
import random
from typing import List, Dict, Optional, Any

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_DARK = "\033[40m"


class ActivityContext:
    """Simulates an Android Activity with allocated bitmap/view tree memory."""
    def __init__(self, name: str, retained_kb: int = 15360):
        self.name = name
        self.retained_kb = retained_kb
        self.is_destroyed = False
        self.views_allocated = ["DecorView", "ConstraintLayout", "RecyclerView", "ImageView"]

    def on_destroy(self) -> None:
        self.is_destroyed = True


class SingletonListenerRegistry:
    """Simulates a static/singleton registry causing memory leaks."""
    _hard_references: List[ActivityContext] = []
    _weak_references: List[Optional[ActivityContext]] = []

    @classmethod
    def register_leaky(cls, activity: ActivityContext) -> None:
        cls._hard_references.append(activity)

    @classmethod
    def register_safe(cls, activity: ActivityContext) -> None:
        cls._weak_references.append(activity)

    @classmethod
    def clear(cls) -> None:
        cls._hard_references.clear()
        cls._weak_references.clear()

    @classmethod
    def sweep_weak_references(cls) -> None:
        # Simulate Garbage Collector sweeping WeakReferences of destroyed activities
        cls._weak_references = [
            act for act in cls._weak_references if act is not None and not act.is_destroyed
        ]


def print_banner() -> None:
    print(f"{CYAN}{BOLD}========================================================================{RESET}")
    print(f"{CYAN}{BOLD}   ANDROID PERFORMANCE PROFILER & BENCHMARKING LAB (BAB-09)            {RESET}")
    print(f"{CYAN}{BOLD}   Memory Leaks, Choreographer Janks, & Macrobenchmark Harness          {RESET}")
    print(f"{CYAN}{BOLD}========================================================================{RESET}")


def simulate_memory_leak_lab() -> None:
    print(f"\n{YELLOW}{BOLD}[MODULE 1: MEMORY LEAKS & GC ROOT RETENTION SIMULATION]{RESET}")
    print(f"{DIM}Memeriksa jalur referensi GC Root (Static Reference vs WeakReference)...{RESET}\n")

    SingletonListenerRegistry.clear()
    activities = [
        ActivityContext("MainActivity", retained_kb=20480),
        ActivityContext("DetailActivity", retained_kb=35840),
        ActivityContext("GalleryActivity", retained_kb=61440),
    ]

    print(f"{BOLD}1. Mendaftarkan 3 Activity ke Leaky Singleton Listener (Strong Reference):{RESET}")
    for act in activities:
        SingletonListenerRegistry.register_leaky(act)
        print(f"   -> {act.name} registered. Retained Memory: {act.retained_kb / 1024:.1f} MB")

    print(f"\n{BOLD}2. Menghancurkan Activity (onDestroy lifecycle call):{RESET}")
    for act in activities:
        act.on_destroy()
        print(f"   -> {act.name}.onDestroy() executed. is_destroyed={act.is_destroyed}")

    print(f"\n{MAGENTA}{BOLD}3. Simulasi Trigger ART GC (Explicit System.gc()):{RESET}")
    time.sleep(0.4)
    leaked_memory_kb = sum(a.retained_kb for a in SingletonListenerRegistry._hard_references if a.is_destroyed)

    print(f"{RED}{BOLD}   [LeakCanary Alert] Ditemukan Leaked Activity Objects!{RESET}")
    for idx, leaked in enumerate(SingletonListenerRegistry._hard_references, 1):
        print(f"   {RED}* Leak #{idx}: {leaked.name} (Retained: {leaked.retained_kb/1024:.1f} MB){RESET}")
        print(f"     Path to GC Root: SingletonListenerRegistry._hard_references[] -> {leaked.name}")
    print(f"   {RED}{BOLD}Total Retained Heap Bloat: {leaked_memory_kb/1024:.2f} MB! OOM Risk: TINGGI.{RESET}")

    print(f"\n{GREEN}{BOLD}4. Menerapkan Solusi Rekayasa: WeakReference Pattern & Auto-Unsubscribe:{RESET}")
    SingletonListenerRegistry.clear()
    safe_activities = [
        ActivityContext("MainActivity", retained_kb=20480),
        ActivityContext("DetailActivity", retained_kb=35840),
        ActivityContext("GalleryActivity", retained_kb=61440),
    ]
    for act in safe_activities:
        SingletonListenerRegistry.register_safe(act)
        act.on_destroy()

    SingletonListenerRegistry.sweep_weak_references()
    active_retained = sum(a.retained_kb for a in SingletonListenerRegistry._weak_references if a is not None)
    print(f"   -> WeakReference dibersihkan oleh GC.")
    print(f"   {GREEN}{BOLD}   Retained Leaked Memory: {active_retained} KB (0 MB Leaked). STATUS: HEALTHY!{RESET}\n")


def simulate_choreographer_jank_profiler() -> None:
    print(f"\n{YELLOW}{BOLD}[MODULE 2: CHOREOGRAPHER & JANKSTATS PROFILER]{RESET}")
    print(f"{DIM}Mengukur render frame budget (Target: 60 FPS -> 16.6ms / frame, 120 FPS -> 8.3ms){RESET}\n")

    target_ms = 16.6
    frames_count = 30
    print(f"Menganalisis {frames_count} render frames saat pengguna melakukan scrolling RecyclerView...\n")

    jank_frames = 0
    total_time_ms = 0.0

    print(f"{WHITE}{BOLD}{'Frame ID':<10} | {'Duration (ms)':<15} | {'Budget State':<20} | {'Cause Diagnosa'}{RESET}")
    print("-" * 75)

    for i in range(1, frames_count + 1):
        # Introduce occasional heavy frames (IPC, DB query on main thread, complex layout measure)
        dice = random.random()
        if dice > 0.85:
            duration = random.uniform(32.0, 75.0)
            cause = "Disk I/O / JSON Parsing on Main Thread"
        elif dice > 0.70:
            duration = random.uniform(18.0, 28.0)
            cause = "Overdraw 3x / Unflattened View Hierarchy"
        else:
            duration = random.uniform(7.0, 15.5)
            cause = "Optimal UI Render"

        total_time_ms += duration
        is_jank = duration > target_ms

        if is_jank:
            jank_frames += 1
            state_str = f"{RED}{BOLD}JANK DROPPED{RESET}"
            dur_str = f"{RED}{duration:6.2f} ms{RESET}"
        else:
            state_str = f"{GREEN}ON TIME{RESET}"
            dur_str = f"{GREEN}{duration:6.2f} ms{RESET}"

        print(f"Frame #{i:<4} | {dur_str:<24} | {state_str:<29} | {DIM}{cause}{RESET}")
        time.sleep(0.04)

    jank_rate = (jank_frames / frames_count) * 100
    avg_frame = total_time_ms / frames_count

    print("-" * 75)
    print(f"{BOLD}Ringkasan JankStats:{RESET}")
    print(f" - Rata-rata Durasi Frame : {avg_frame:.2f} ms (Target < {target_ms} ms)")
    print(f" - Total Dropped / Janks  : {jank_frames} / {frames_count} frames")
    if jank_rate > 15.0:
        print(f" - Jank Rate             : {RED}{BOLD}{jank_rate:.1f}% (KRITIS: stuttering terlihat jelas){RESET}")
    else:
        print(f" - Jank Rate             : {GREEN}{BOLD}{jank_rate:.1f}% (SMOOTH: memenuhi standar Google Play Vitals){RESET}")


def run_benchmark_harness() -> None:
    print(f"\n{YELLOW}{BOLD}[MODULE 3: ANDROIDX MACROBENCHMARK & STARTUP TIMING HARNESS]{RESET}")
    print(f"{DIM}Menjalankan Cold Startup Benchmark (CompilationMode: SpeedProfile vs BaselineProfile vs None)...{RESET}\n")

    modes = {
        "CompilationMode.None (JIT Only)": {"mean_ms": 680.0, "jitter": 65.0},
        "CompilationMode.BaselineProfile": {"mean_ms": 320.0, "jitter": 25.0},
        "CompilationMode.Full (AOT Speed)": {"mean_ms": 275.0, "jitter": 15.0},
    }

    iterations = 5

    for mode_name, profile in modes.items():
        print(f"{CYAN}{BOLD}Testing {mode_name}:{RESET}")
        measurements: List[float] = []
        for it in range(1, iterations + 1):
            val = profile["mean_ms"] + random.uniform(-profile["jitter"], profile["jitter"])
            measurements.append(val)
            print(f"   Iteration #{it}: TimeToInitialDisplay = {val:6.1f} ms")
            time.sleep(0.06)

        measurements.sort()
        median = measurements[len(measurements) // 2]
        p95 = measurements[math.floor(len(measurements) * 0.90)]
        print(f"   {GREEN}==> Median: {median:.1f} ms | P95: {p95:.1f} ms{RESET}\n")

    improvement = ((680.0 - 320.0) / 680.0) * 100
    print(f"{BOLD}{WHITE}Evaluasi Baseline Profile:{RESET}")
    print(f"Penggunaan Baseline Profiles memotong cold startup time hingga {GREEN}{BOLD}{improvement:.1f}%{RESET} tanpa perlu AOT penuh.")


def interactive_menu() -> None:
    while True:
        print_banner()
        print(f"{BOLD}Pilih Skenario Hands-on Profiling:{RESET}")
        print(f"  {CYAN}1.{RESET} Simulasi Memory Leak & GC Root Detection (LeakCanary Engine)")
        print(f"  {CYAN}2.{RESET} Simulasi UI Thread Choreographer & Frame JankStats Profiler")
        print(f"  {CYAN}3.{RESET} Simulasi AndroidX Macrobenchmark Startup Time (Baseline Profiles)")
        print(f"  {CYAN}4.{RESET} Jalankan Seluruh Audit Diagnostik (Full Pipeline)")
        print(f"  {RED}0.{RESET} Keluar dari Lab")
        print(f"{CYAN}------------------------------------------------------------------------{RESET}")

        try:
            choice = input(f"{BOLD}Masukkan pilihan [0-4]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Menutup lab profiling.{RESET}")
            sys.exit(0)

        if choice == "1":
            simulate_memory_leak_lab()
        elif choice == "2":
            simulate_choreographer_jank_profiler()
        elif choice == "3":
            run_benchmark_harness()
        elif choice == "4":
            simulate_memory_leak_lab()
            simulate_choreographer_jank_profiler()
            run_benchmark_harness()
        elif choice == "0":
            print(f"\n{GREEN}Selesai. Evaluasi profiling performa selesai dengan baik.{RESET}")
            break
        else:
            print(f"\n{RED}Pilihan '{choice}' tidak valid. Silakan coba lagi.{RESET}\n")

        input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        print("\n" * 2)


if __name__ == "__main__":
    interactive_menu()
