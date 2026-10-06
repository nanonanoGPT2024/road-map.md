#!/usr/bin/env python3
"""
React Native Performance & Memory Profiler Simulator
BAB 09: Profiling, Memory Leaks, dan Performance Optimization

Simulasi teknis konsep fondasi:
1. JS Thread vs UI (Main) Thread Frame Drops (16.67ms frame budget)
2. Memory Leaks (Retained closures, dangling event listeners, unmounted state updates)
3. Hermes Heap Allocation & Retained Size Analysis
4. Component Re-render Storm vs Memoization (useMemo, useCallback, React.memo)
"""

import sys
import time
import math
import random
from typing import Dict, List, Any, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 70}{RESET}")
    print(f"{BOLD}{CYAN} [PROFILER] {title.center(56)} {RESET}")
    print(f"{BOLD}{CYAN}{'=' * 70}{RESET}")


def subheader(title: str) -> None:
    print(f"\n{BOLD}{YELLOW}>>> {title}{RESET}")


def progress_bar(iteration: int, total: int, prefix: str = '', suffix: str = '', length: int = 35) -> None:
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_len = int(length * iteration // total)
    bar = f"{GREEN}█{RESET}" * filled_len + f"{DIM}░{RESET}" * (length - filled_len)
    print(f"\r  {prefix} |{bar}| {percent}% {suffix}", end="\r")
    if iteration == total:
        print()


class FrameBudgetSimulator:
    """Simulates 60 FPS / 120 FPS frame budgeting on JS & UI Threads."""

    @staticmethod
    def run():
        header("SIMULASI 1: JS THREAD STARVATION & FRAME DROPS")
        print(f"{WHITE}Target Frame Budget: {BOLD}16.67ms (60 FPS){RESET}")
        print(f"{DIM}Bridge/JSI bottleneck happens when heavy calculations block the JS Event Loop.{RESET}\n")

        scenarios = [
            ("Unoptimized: Synchronous JSON serialization & massive list filter", 120000, False),
            ("Optimized: Chunked interactionManager / Web Worker / C++ TurboModule", 120000, True),
        ]

        for desc, items_count, is_optimized in scenarios:
            subheader(desc)
            frames = 30
            dropped_frames = 0
            total_duration = 0.0

            print(f"  Memproses {items_count:,} data records dalam 30 frame...")

            for f in range(1, frames + 1):
                start = time.perf_counter()
                if not is_optimized:
                    # Simulasi heavy blocking computation pada JS Thread
                    _ = [math.sqrt(i) for i in range(items_count // 35)]
                    time.sleep(random.uniform(0.012, 0.028))
                else:
                    # Simulasi slice processing / async batching
                    _ = [math.sqrt(i) for i in range(items_count // 250)]
                    time.sleep(random.uniform(0.004, 0.011))

                frame_time = (time.perf_counter() - start) * 1000
                total_duration += frame_time

                if frame_time > 16.67:
                    dropped_frames += 1
                    status = f"{RED}{BOLD}DROPPED ({frame_time:.1f}ms){RESET}"
                else:
                    status = f"{GREEN}OK ({frame_time:.1f}ms){RESET}"

                print(f"    Frame #{f:02d}: {status}")

            avg_frame_time = total_duration / frames
            fps = min(60.0, 1000.0 / avg_frame_time) if avg_frame_time > 0 else 60.0

            print(f"\n  {BOLD}Ringkasan Metrik:{RESET}")
            print(f"    - Avg Frame Execution: {BOLD}{avg_frame_time:.2f} ms{RESET}")
            print(f"    - Dropped Frames      : {RED if dropped_frames > 5 else GREEN}{dropped_frames}/{frames}{RESET}")
            print(f"    - Estimated FPS       : {RED if fps < 45 else GREEN}{fps:.1f} FPS{RESET}")


class MemoryLeakSimulator:
    """Simulates React Native dangling subscriptions & closures."""

    @staticmethod
    def run():
        header("SIMULASI 2: DETEKSI MEMORY LEAKS PADA REACT HOOKS")
        print(f"{WHITE}Penyebab utama memory leak di React Native:{RESET}")
        print(f"  1. `useEffect` tanpa cleanup function (DeviceEventEmitter, AppState, setInterval)")
        print(f"  2. Retained closure references yang mengikat pointer root komponen unmounted.\n")

        class LeakyEventEmitter:
            def __init__(self):
                self.listeners = []

            def subscribe(self, callback):
                self.listeners.append(callback)
                return lambda: self.listeners.remove(callback)

        emitter = LeakyEventEmitter()
        heap_allocated_kb = 1200.0  # Base RN Runtime heap

        subheader("Skenario A: Komponen Navigasi DIBUKA & DITUTUP (Tanpa Cleanup)")
        for cycle in range(1, 6):
            # Simulasi komponen Screen mounted dengan 2MB closure
            large_closure = bytearray(2 * 1024 * 1024)  # 2MB
            callback = lambda data, c=large_closure: len(c) + len(data)
            # BUG: Tidak menyimpan unsubscribe handler
            emitter.subscribe(callback)
            heap_allocated_kb += 2048.0
            print(f"  [Cycle {cycle}] Screen Mount -> Unmount: Heap Naik -> {RED}{heap_allocated_kb/1024:.2f} MB{RESET} (Listeners: {len(emitter.listeners)})")
            time.sleep(0.1)

        print(f"  {RED}{BOLD}ALERT: Terdeteksi 5 uncleaned event listeners! Garbage Collector gagal me-reclaim memory.{RESET}")

        subheader("Skenario B: Komponen Navigasi DIBUKA & DITUTUP (DENGAN Cleanup Return)")
        emitter_clean = LeakyEventEmitter()
        heap_allocated_kb = 1200.0

        for cycle in range(1, 6):
            large_closure = bytearray(2 * 1024 * 1024)
            callback = lambda data, c=large_closure: len(c) + len(data)
            unsubscribe = emitter_clean.subscribe(callback)
            heap_allocated_kb += 2048.0
            # Cleanup dijalankan saat unmount
            unsubscribe()
            del large_closure
            heap_allocated_kb -= 2048.0
            print(f"  [Cycle {cycle}] Screen Mount -> Unmount: Heap Stabil -> {GREEN}{heap_allocated_kb/1024:.2f} MB{RESET} (Listeners: {len(emitter_clean.listeners)})")
            time.sleep(0.1)

        print(f"  {GREEN}{BOLD}PASS: Cleaned up properly. Zero memory leaks detected.{RESET}")


class HermesHeapProfiler:
    """Simulates Hermes Engine GC & Memory Allocation Snapshots."""

    @staticmethod
    def run():
        header("SIMULASI 3: HERMES SAMPLING PROFILER & HEAP SNAPSHOT")
        print(f"{WHITE}Hermes VM Heap Analyzer:{RESET} Memeriksa Shallow Size vs Retained Size objek.")

        objects_in_heap = [
            {"type": "HermesBytecode", "shallow_kb": 340, "retained_kb": 340, "count": 1},
            {"type": "RCTUIManager ShadowNodes", "shallow_kb": 850, "retained_kb": 2400, "count": 320},
            {"type": "ReactFiberTree (Virtual DOM)", "shallow_kb": 1200, "retained_kb": 5600, "count": 1250},
            {"type": "FastImage Cached Bitmaps", "shallow_kb": 14200, "retained_kb": 14200, "count": 18},
            {"type": "Dangling Redux Action Subscriptions", "shallow_kb": 45, "retained_kb": 8900, "count": 42},
        ]

        print(f"\n{'Object Type':<35} | {'Count':<8} | {'Shallow Size':<14} | {'Retained Size':<14}")
        print("-" * 78)

        total_retained = 0
        for obj in objects_in_heap:
            shallow_str = f"{obj['shallow_kb']} KB"
            retained_str = f"{obj['retained_kb']} KB"
            total_retained += obj['retained_kb']

            is_warning = obj['retained_kb'] > 5000
            color = RED if is_warning else GREEN
            print(f"{color}{obj['type']:<35}{RESET} | {obj['count']:<8} | {shallow_str:<14} | {color}{retained_str:<14}{RESET}")

        print("-" * 78)
        print(f"{BOLD}Total Retained Heap Footprint: {total_retained / 1024:.2f} MB{RESET}")
        print(f"\n{YELLOW}{BOLD}Hermes GC Recommendation:{RESET}")
        print(f"  [!] 'Dangling Redux Action Subscriptions' menahan {RED}8.9 MB{RESET} memory lewat retained closures.")
        print(f"  [!] Periksa FastImage cache limits untuk mencegah OOM (Out Of Memory) crash di perangkat low-end (Android 2GB RAM).")


class ReRenderBenchmark:
    """Simulates Re-render Cascade vs React.memo / useMemo."""

    @staticmethod
    def run():
        header("SIMULASI 4: RE-RENDER CASCADE BENCHMARK")
        print(f"{WHITE}Mengukur waktu rendering pohon komponen FlatList (1,000 item).{RESET}\n")

        item_count = 1000

        # Kasus 1: Tanpa React.memo & Anonymous Inline Callbacks
        subheader("Case 1: Without React.memo + Inline Objects & Callbacks (renderItem=()=>...)")
        start = time.perf_counter()
        re_rendered_items = 0
        for _ in range(item_count):
            re_rendered_items += 1
            # Simulasi overhead reconciler & diffing
            _ = [x ** 2 for x in range(120)]
        dur_unopt = (time.perf_counter() - start) * 1000
        print(f"  - Re-rendered Items : {RED}{re_rendered_items}/{item_count} items{RESET}")
        print(f"  - Commit Time       : {RED}{dur_unopt:.2f} ms{RESET} (Pemicu micro-stutter / dropped frame)")

        # Kasus 2: Menggunakan React.memo + useCallback + getItemLayout
        subheader("Case 2: With React.memo + useCallback + FlatList getItemLayout")
        start = time.perf_counter()
        re_rendered_items = 0
        # Hanya 5 item yang valuenya berubah yang di-render ulang
        for i in range(item_count):
            if i in [12, 45, 88, 120, 340]:
                re_rendered_items += 1
                _ = [x ** 2 for x in range(120)]
        dur_opt = (time.perf_counter() - start) * 1000
        print(f"  - Re-rendered Items : {GREEN}{re_rendered_items}/{item_count} items{RESET} (Hanya item yang prop-nya dirty)")
        print(f"  - Commit Time       : {GREEN}{dur_opt:.2f} ms{RESET} (Super smooth, < 16.6ms)")

        improvement = ((dur_unopt - dur_opt) / dur_unopt) * 100 if dur_unopt > 0 else 0
        print(f"\n  {BOLD}{CYAN}Speedup / Efisiensi: +{improvement:.1f}% pengurangan beban JS thread!{RESET}")


def interactive_menu():
    while True:
        print(f"\n{BOLD}{MAGENTA}=================================================================={RESET}")
        print(f"{BOLD}{MAGENTA}   REACT NATIVE PROFILING & OPTIMIZATION DIAGNOSTIC LAB           {RESET}")
        print(f"{BOLD}{MAGENTA}=================================================================={RESET}")
        print("  [1] Simulasi JS Thread Starvation & Frame Budget (16.67ms)")
        print("  [2] Simulasi Deteksi Memory Leak pada React Hooks & Event Listeners")
        print("  [3] Hermes Engine Heap Analyzer & Retained Memory Map")
        print("  [4] Re-render Cascade Benchmark (React.memo vs Inline Props)")
        print("  [5] Jalankan SEMUA Modul Profiling Secara Sekuensial")
        print("  [0] Keluar")
        print(f"{DIM}------------------------------------------------------------------{RESET}")

        try:
            choice = input(f"{BOLD}{WHITE}Pilih menu [0-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari profiler simulator.")
            break

        if choice == "1":
            FrameBudgetSimulator.run()
        elif choice == "2":
            MemoryLeakSimulator.run()
        elif choice == "3":
            HermesHeapProfiler.run()
        elif choice == "4":
            ReRenderBenchmark.run()
        elif choice == "5":
            FrameBudgetSimulator.run()
            MemoryLeakSimulator.run()
            HermesHeapProfiler.run()
            ReRenderBenchmark.run()
            print(f"\n{BG_GREEN}{WHITE}{BOLD} [SELESAI] Seluruh modul profiling berhasil dijalankan! {RESET}\n")
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menggunakan Profiling Lab.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 0-5.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["--all", "--auto", "-a"]:
        FrameBudgetSimulator.run()
        MemoryLeakSimulator.run()
        HermesHeapProfiler.run()
        ReRenderBenchmark.run()
        print(f"\n{BG_GREEN}{WHITE}{BOLD} [AUTO RUN COMPLETE] All checks passed. {RESET}\n")
    else:
        interactive_menu()
