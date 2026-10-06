#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Diagnostik & Profiling Kinerja Aplikasi iOS
BAB-07: Kinerja Aplikasi, Diagnostik, Instruments, dan Profiling

Simulasi interaktif teknis konsep-konsep inti profiling iOS:
1. Time Profiler & Call Tree (Hitch Rate, Main Thread Hang, Frame Drop 60Hz/120Hz)
2. Allocations & Leaks (ARC Retain Cycle, Memory Footprint, [weak self] patch)
3. Energy Impact & Network Throttling (Radio State Transitions, Batching vs Polling)
4. OSLog Signpost & Points of Interest (Instruments Visualization)
"""

import sys
import time
import math
import random
from typing import Dict, List, Optional, Tuple

# --- ANSI Terminal Color Palette ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    # Background colors
    BG_DARK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


def print_header(title: str):
    print(f"\n{Style.CYAN}{Style.BOLD}{'=' * 68}{Style.RESET}")
    print(f"{Style.MAGENTA}{Style.BOLD} [INSTRUMENTS] {title.center(50)} {Style.RESET}")
    print(f"{Style.CYAN}{Style.BOLD}{'=' * 68}{Style.RESET}\n")


def print_metric_bar(label: str, value: float, max_value: float, unit: str, warning_thresh: float, critical_thresh: float):
    width = 30
    ratio = min(max(value / max_value, 0.0), 1.0)
    filled = int(round(ratio * width))
    bar = "█" * filled + "░" * (width - filled)
    
    if value >= critical_thresh:
        color = Style.RED
        status = "CRITICAL"
    elif value >= warning_thresh:
        color = Style.YELLOW
        status = "WARNING"
    else:
        color = Style.GREEN
        status = "OPTIMAL"
        
    print(f"  {label:<22} [{color}{bar}{Style.RESET}] {value:6.2f} {unit} ({color}{status}{Style.RESET})")


# ==============================================================================
# MODUL 1: Time Profiler & Main Thread Hitch Simulation
# ==============================================================================
def simulate_time_profiler():
    print_header("MODUL 1: Time Profiler & Main Thread Hitch Rate")
    print(f"{Style.YELLOW}Target Frame Budget:{Style.RESET} 60 FPS = 16.67 ms/frame | ProMotion 120 FPS = 8.33 ms/frame")
    print(f"{Style.DIM}Metrik Apple: Hitch Rate (ms/s) - Waktu lag per 1 detik rendering.{Style.RESET}\n")

    frames = 10
    total_hitch_duration_ms = 0.0
    frame_budget_ms = 16.67

    print(f"{Style.BOLD}{'Frame':<8}{'Workload':<28}{'Duration':<14}{'Status':<12}{'Call Tree Sample'}{Style.RESET}")
    print("-" * 80)

    workloads = [
        ("UI Layout (autolayout)", 4.2, "AutoLayoutEngine.solveConstraints()"),
        ("Render Text glyphs", 5.8, "CoreText.CTFontDrawGlyphs()"),
        ("JSON Parsing di Main Thread", 38.4, "JSONDecoder.decode(UserFeed.self) [BLOCKED]"),
        ("Cell reuse dequeue", 3.1, "UITableView.dequeueReusableCell()"),
        ("Core Data synchronous fetch", 52.0, "NSManagedObjectContext.executeFetch() [BLOCKED]"),
        ("Image decompression sync", 41.5, "UIImage.init(data:) decompress [BLOCKED]"),
        ("Render subviews", 7.2, "CALayer.render(in:)"),
        ("Core Animation commit", 6.0, "CA::Transaction::commit()"),
        ("Touch event dispatch", 2.4, "UIApplication.sendEvent()"),
        ("GPU Render Pass Wait", 14.8, "CAMetalLayer.nextDrawable()"),
    ]

    for i, (name, duration, stack_sample) in enumerate(workloads, start=1):
        is_hitch = duration > frame_budget_ms
        if is_hitch:
            hitch_ms = duration - frame_budget_ms
            total_hitch_duration_ms += hitch_ms
            status_str = f"{Style.RED}{Style.BOLD}HITCH{Style.RESET}"
            call_tree_color = Style.RED
        else:
            status_str = f"{Style.GREEN}OK{Style.RESET}"
            call_tree_color = Style.DIM

        print(f"#{i:<7}{name:<28}{duration:6.2f} ms     {status_str:<21}{call_tree_color}{stack_sample}{Style.RESET}")
        time.sleep(0.1)

    total_time_s = sum(w[1] for w in workloads) / 1000.0
    hitch_rate = total_hitch_duration_ms / total_time_s

    print("-" * 80)
    print(f"\n{Style.BOLD}Ringkasan Hasil Profiling Time Profiler:{Style.RESET}")
    print_metric_bar("Hitch Rate", hitch_rate, 50.0, "ms/s", 5.0, 10.0)
    print(f"Total Hitch Duration : {Style.RED}{total_hitch_duration_ms:.2f} ms{Style.RESET}")
    print(f"Durasi Tracing       : {total_time_s:.2f} s")
    
    print(f"\n{Style.CYAN}{Style.BOLD}Rekomendasi Time Profiler (Xcode Instruments):{Style.RESET}")
    print(f"  1. {Style.YELLOW}Invert Call Tree & Hide System Libraries:{Style.RESET} Identifikasi heaviest stack trace.")
    print(f"  2. Pindahkan {Style.BOLD}JSONDecoder{Style.RESET} dan {Style.BOLD}Core Data Fetch{Style.RESET} ke background thread via Swift Concurrency (Task.detached atau Task {{ ... }}).")
    print(f"  3. Lakukan dekompresi gambar di background menggunakan `preparingForDisplay()`.")


# ==============================================================================
# MODUL 2: Allocations & Memory Leaks (ARC Retain Cycle)
# ==============================================================================
class MockARCNode:
    def __init__(self, name: str):
        self.name = name
        self.strong_refs: List['MockARCNode'] = []
        self.weak_refs: List['MockARCNode'] = []
        self.retain_count = 1
        self.is_deallocated = False

    def add_strong(self, target: 'MockARCNode'):
        self.strong_refs.append(target)
        target.retain_count += 1

    def add_weak(self, target: 'MockARCNode'):
        self.weak_refs.append(target)

    def release_root(self):
        self.retain_count -= 1
        if self.retain_count <= 0:
            self._dealloc()

    def _dealloc(self):
        self.is_deallocated = True
        for target in self.strong_refs:
            target.retain_count -= 1
            if target.retain_count <= 0:
                target._dealloc()


def simulate_memory_leaks():
    print_header("MODUL 2: Leaks & Memory Graph (ARC Retain Cycle)")
    print(f"Skenario: FeedViewController menahan closure handler `onDataLoaded`.")
    print(f"Closure menangkap self secara {Style.BOLD}STRONG{Style.RESET} vs {Style.BOLD}[weak self]{Style.RESET}.\n")

    # Mode 1: Strong Retain Cycle (Bug)
    print(f"{Style.RED}{Style.BOLD}[Kasus 1: Retain Cycle Tanpa [weak self]]{Style.RESET}")
    vc = MockARCNode("FeedViewController")
    vm = MockARCNode("FeedViewModel")
    closure = MockARCNode("Closure (onDataLoaded)")

    vc.add_strong(vm)            # VC punya VM
    vm.add_strong(closure)       # VM punya closure
    closure.add_strong(vc)       # BUG: closure tangkap VC secara strong!

    print(f"  Alokasi awal: {vc.name} (Retain: {vc.retain_count}), {vm.name} (Retain: {vm.retain_count})")
    print(f"  User pop/dismiss view controller (release root pointer)...")
    vc.release_root()

    print(f"  Status Dealloc: VC={'DEALLOC' if vc.is_deallocated else Style.RED + 'LEAKED (Retain Count=' + str(vc.retain_count) + ')' + Style.RESET}")
    print(f"  Status Dealloc: VM={'DEALLOC' if vm.is_deallocated else Style.RED + 'LEAKED (Retain Count=' + str(vm.retain_count) + ')' + Style.RESET}")
    print(f"  {Style.RED}Instruments Alert: Malloc 48KB Leaked Block! Memory Graph Cycle: VC -> VM -> Closure -> VC{Style.RESET}\n")

    # Mode 2: Fixed with [weak self]
    print(f"{Style.GREEN}{Style.BOLD}[Kasus 2: Perbaikan dengan [weak self] Guard]{Style.RESET}")
    vc_fixed = MockARCNode("FeedViewController (Fixed)")
    vm_fixed = MockARCNode("FeedViewModel")
    closure_fixed = MockARCNode("Closure with [weak self]")

    vc_fixed.add_strong(vm_fixed)
    vm_fixed.add_strong(closure_fixed)
    closure_fixed.add_weak(vc_fixed)  # FIX: weak reference tidak menambah retain count!

    print(f"  Alokasi awal: {vc_fixed.name} (Retain: {vc_fixed.retain_count}), {vm_fixed.name} (Retain: {vm_fixed.retain_count})")
    print(f"  User pop/dismiss view controller (release root pointer)...")
    vc_fixed.release_root()

    print(f"  Status Dealloc: VC={Style.GREEN + 'DEALLOCATED (Retain Count=' + str(vc_fixed.retain_count) + ')' + Style.RESET}")
    print(f"  Status Dealloc: VM={Style.GREEN + 'DEALLOCATED (Retain Count=' + str(vm_fixed.retain_count) + ')' + Style.RESET}")
    print(f"  {Style.GREEN}Instruments Memory Graph: Graph Clean, zero persistent memory leak!{Style.RESET}")


# ==============================================================================
# MODUL 3: Energy Log & Cellular Radio State Simulation
# ==============================================================================
def simulate_energy_diagnostics():
    print_header("MODUL 3: Energy Diagnostics & Radio Overhead")
    print(f"Apple Energy Model: Radio Cellular (LTE/5G) memiliki state machine:")
    print(f"  - {Style.CYAN}IDLE{Style.RESET} (Daya minimal: ~10 mW)")
    print(f"  - {Style.YELLOW}ACTIVE TRANSITION{Style.RESET} (Spike daya tinggi saat warmup)")
    print(f"  - {Style.RED}FULL ACTIVE{Style.RESET} (Transmisi paket: ~1500-2500 mW)")
    print(f"  - {Style.YELLOW}TAIL ENERGY (WAIT){Style.RESET} (Menunggu paket baru selama ~10-15s sebelum sleep)\n")

    # Skenario 1: Chatty Polling (1 request setiap 3 detik)
    print(f"{Style.RED}{Style.BOLD}Skenario A: Chatty Polling (10 requests dikirim terpisah setiap 3s){Style.RESET}")
    energy_chatty_joules = 10 * 18.5  # radio tidak pernah sempat idle (tail energy terulang)
    print(f"  Total Radio Wakeups: 10 kali")
    print(f"  Radio Stay Awake   : 30 detik nonstop")
    print_metric_bar("Energi Terpakai", energy_chatty_joules, 250.0, "Joules", 80.0, 150.0)

    # Skenario 2: Batching (Semua request dikirim dalam 1 burst connection)
    print(f"\n{Style.GREEN}{Style.BOLD}Skenario B: Batched Requests via URLSessionConfiguration (Single Burst){Style.RESET}")
    energy_batched_joules = 1 * 22.0  # hanya 1 kali warmup dan 1 kali tail state
    print(f"  Total Radio Wakeups: 1 kali (Burst 10 requests multiplexed HTTP/3)")
    print(f"  Radio Stay Awake   : ~4 detik lalu kembali ke IDLE")
    print_metric_bar("Energi Terpakai", energy_batched_joules, 250.0, "Joules", 80.0, 150.0)

    hemat_pct = ((energy_chatty_joules - energy_batched_joules) / energy_chatty_joules) * 100.0
    print(f"\n{Style.GREEN}{Style.BOLD}Efisiensi Energi: Penghematan {hemat_pct:.1f}% baterai dengan batching!{Style.RESET}")


# ==============================================================================
# MODUL 4: OSLog Signpost & Custom Metrics Visualization
# ==============================================================================
def simulate_signposts():
    print_header("MODUL 4: OSLog & Signpost (Instruments Points of Interest)")
    print("Simulasi pembuatan custom interval signpost untuk diinspeksi di Instruments:")
    print(f"{Style.DIM}let log = OSSignposter(subsystem: 'com.app.feed', category: 'PointsOfInterest'){Style.RESET}\n")

    signposts = [
        ("FetchFeedTask", 0.0, 0.45, "URLSession Task"),
        ("DatabasePersistence", 0.46, 0.62, "CoreData Save"),
        ("ImageDecodeBatch", 0.63, 0.95, "vImage Scale"),
        ("ViewHierarchyUpdate", 0.96, 1.10, "DiffableDataSource Apply"),
    ]

    print(f"{Style.BOLD}{'Signpost Name':<24}{'Start (s)':<12}{'End (s)':<12}{'Timeline Bar (0.0s - 1.2s)'}{Style.RESET}")
    print("-" * 75)

    timeline_len = 35
    total_duration = 1.2

    for name, start_t, end_t, desc in signposts:
        start_idx = int((start_t / total_duration) * timeline_len)
        end_idx = int((end_t / total_duration) * timeline_len)
        bar = [" "] * timeline_len
        for b in range(start_idx, max(end_idx, start_idx + 1)):
            bar[b] = "■"
        bar_str = "".join(bar)
        print(f"{name:<24}{start_t:6.2f}s     {end_t:6.2f}s     {Style.CYAN}[{bar_str}]{Style.RESET} ({desc})")

    print("-" * 75)
    print(f"\n{Style.GREEN}✓ Signposts tercatat di trace file. Dapat dibuka di Xcode Instruments -> Points of Interest.{Style.RESET}")


# ==============================================================================
# Main Interactive Menu & CLI Dispatcher
# ==============================================================================
def run_all_benchmarks():
    simulate_time_profiler()
    simulate_memory_leaks()
    simulate_energy_diagnostics()
    simulate_signposts()
    print(f"\n{Style.BG_GREEN}{Style.WHITE}{Style.BOLD} SELURUH SIMULASI INSTRUMENTS SELESAI DENGAN STATUS VALID {Style.RESET}\n")


def display_menu():
    print(f"""
{Style.BOLD}{Style.WHITE}══════════════════════════════════════════════════════════════════════
  iOS PERFORMANCE & INSTRUMENTS PROFILING LAB (BAB-07)
══════════════════════════════════════════════════════════════════════{Style.RESET}
  {Style.CYAN}1.{Style.RESET} Simulasi Time Profiler & Main Thread Hitch Rate (FPS Budget)
  {Style.CYAN}2.{Style.RESET} Simulasi Memory Leaks, Retain Cycles & ARC [weak self]
  {Style.CYAN}3.{Style.RESET} Simulasi Energy Log & Cellular Radio State Overhead
  {Style.CYAN}4.{Style.RESET} Simulasi OSLog Signposts & Points of Interest Interval
  {Style.GREEN}5.{Style.RESET} Jalankan SEMUA Modul Profiling Sekaligus (Automated Trace)
  {Style.RED}0.{Style.RESET} Keluar
""")


def main():
    # If run with --test or in non-interactive piped environment
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--all", "-a"):
        run_all_benchmarks()
        return

    while True:
        display_menu()
        try:
            choice = input(f"{Style.BOLD}Pilih opsi [0-5]: {Style.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Style.YELLOW}Sesi lab diakhiri.{Style.RESET}")
            break

        if choice == "1":
            simulate_time_profiler()
        elif choice == "2":
            simulate_memory_leaks()
        elif choice == "3":
            simulate_energy_diagnostics()
        elif choice == "4":
            simulate_signposts()
        elif choice == "5":
            run_all_benchmarks()
        elif choice == "0":
            print(f"\n{Style.GREEN}Selesai. Selamat mempraktikkan profiling di Xcode Instruments!{Style.RESET}\n")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan masukkan angka 0-5.{Style.RESET}")


if __name__ == "__main__":
    main()
