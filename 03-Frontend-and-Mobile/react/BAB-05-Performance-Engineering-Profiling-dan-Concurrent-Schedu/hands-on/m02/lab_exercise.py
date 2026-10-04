#!/usr/bin/env python3
"""
LAB EXERCISE: React Concurrent Scheduler & Performance Engineering Simulation
BAB-05: Performance Engineering, Profiling, dan Concurrent Scheduler

Simulasi mendalam arsitektur React Fiber Reconciler, Cooperative Multitasking Scheduler,
Lanes Priority System, dan Profiler Metrics Engine.
"""

import sys
import time
import heapq
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
from enum import IntEnum

# ANSI Color Palette for Terminal UI
class Color:
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
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"

# React Lane Priority Architecture (Bitmask-inspired Priority Levels)
class LanePriority(IntEnum):
    SYNC_LANE = 1             # Immediate Priority (Clicks, discrete user input)
    INPUT_CONTINUOUS = 2      # High Priority (Drag, scroll, continuous input)
    DEFAULT_LANE = 3          # Normal Priority (Data fetch, state updates)
    TRANSITION_LANE = 4       # Low Priority (startTransition, route transitions)
    IDLE_LANE = 5             # Idle Priority (Offscreen pre-rendering, background work)

LANE_NAMES = {
    LanePriority.SYNC_LANE: "SyncLane (Immediate)",
    LanePriority.INPUT_CONTINUOUS: "InputContinuousLane (UserBlocking)",
    LanePriority.DEFAULT_LANE: "DefaultLane (Normal)",
    LanePriority.TRANSITION_LANE: "TransitionLane (Non-Urgent)",
    LanePriority.IDLE_LANE: "IdleLane (Offscreen/Background)"
}

LANE_TIMEOUTS = {
    LanePriority.SYNC_LANE: -1,        # Immediate, already expired
    LanePriority.INPUT_CONTINUOUS: 250, # 250ms
    LanePriority.DEFAULT_LANE: 5000,    # 5,000ms
    LanePriority.TRANSITION_LANE: 10000,# 10,000ms
    LanePriority.IDLE_LANE: 1073741823 # Max timeout
}

@dataclass(order=True)
class FiberTask:
    priority: int
    expiration_time: float
    task_id: int = field(compare=False)
    component_name: str = field(compare=False)
    fiber_depth: int = field(compare=False)
    work_units: int = field(compare=False)
    completed_units: int = field(default=0, compare=False)
    memoized_props: Dict[str, Any] = field(default_factory=dict, compare=False)
    next_props: Dict[str, Any] = field(default_factory=dict, compare=False)
    base_duration_ms: float = field(default=0.0, compare=False)
    actual_duration_ms: float = field(default=0.0, compare=False)

    @property
    def is_completed(self) -> bool:
        return self.completed_units >= self.work_units

class ReactScheduler:
    """
    Simulasi React 18 Scheduler dengan Cooperative Time Slicing (5ms Frame Deadline)
    dan Dynamic Yielding to Host Event Loop.
    """
    FRAME_DEADLINE_MS = 5.0  # React 5ms time slice budget per frame

    def __init__(self):
        self.task_queue: List[FiberTask] = []
        self.task_counter = 0
        self.is_performing_work = False

    def schedule_callback(self, priority: LanePriority, component_name: str, 
                          work_units: int, depth: int = 1, 
                          memoized_props: Optional[Dict] = None,
                          next_props: Optional[Dict] = None) -> FiberTask:
        now = time.perf_counter() * 1000.0
        timeout = LANE_TIMEOUTS[priority]
        expiration_time = now if timeout < 0 else now + timeout

        self.task_counter += 1
        task = FiberTask(
            priority=priority.value,
            expiration_time=expiration_time,
            task_id=self.task_counter,
            component_name=component_name,
            fiber_depth=depth,
            work_units=work_units,
            memoized_props=memoized_props or {},
            next_props=next_props or {},
            base_duration_ms=work_units * 1.5
        )
        heapq.heappush(self.task_queue, task)
        return task

    def should_yield_to_host(self, frame_start_ms: float) -> bool:
        now_ms = time.perf_counter() * 1000.0
        return (now_ms - frame_start_ms) >= self.FRAME_DEADLINE_MS

class ReactProfilerCollector:
    """
    Profiler Metrics Engine: mengukur Actual Duration, Base Duration,
    Bailout Ratios, dan Frame Drop Frequency.
    """
    def __init__(self):
        self.commit_records = []
        self.total_jank_frames = 0
        self.bailout_count = 0
        self.total_rendered_components = 0

    def record_commit(self, phase: str, actual_duration: float, 
                      base_duration: float, fibers: List[FiberTask]):
        self.commit_records.append({
            "phase": phase,
            "actual_duration_ms": actual_duration,
            "base_duration_ms": base_duration,
            "fiber_count": len(fibers),
            "timestamp": time.time()
        })
        self.total_rendered_components += len(fibers)

    def print_flamegraph_summary(self):
        print(f"\n{Color.BOLD}{Color.BG_MAGENTA} ⚛ REACT PROFILER COMMIT REPORT ⚛ {Color.RESET}")
        print(f"{'Phase':<15} | {'Actual (ms)':<12} | {'Base (ms)':<12} | {'Savings':<10} | {'Fibers':<8}")
        print("-" * 65)

        total_actual = 0.0
        total_base = 0.0
        for rec in self.commit_records:
            savings = max(0.0, rec['base_duration_ms'] - rec['actual_duration_ms'])
            savings_pct = (savings / rec['base_duration_ms'] * 100) if rec['base_duration_ms'] > 0 else 0
            print(f"{rec['phase']:<15} | {rec['actual_duration_ms']:>10.2f}ms | {rec['base_duration_ms']:>10.2f}ms | {savings_pct:>8.1f}% | {rec['fiber_count']:<8}")
            total_actual += rec['actual_duration_ms']
            total_base += rec['base_duration_ms']

        print("-" * 65)
        print(f"{Color.CYAN}Total Work Time:{Color.RESET} {total_actual:.2f}ms vs Base: {total_base:.2f}ms")
        print(f"{Color.GREEN}Bailout / Memoized skips:{Color.RESET} {self.bailout_count} nodes")
        print(f"{Color.YELLOW}Dropped Frames (Jank > 16.6ms):{Color.RESET} {self.total_jank_frames} frames\n")

class FiberReconcilerEngine:
    """
    Core Reconciler: Mendemonstrasikan Render Phase (Interruptible) vs
    Commit Phase (Synchronous DOM Mutation simulation).
    """
    def __init__(self, scheduler: ReactScheduler, profiler: ReactProfilerCollector):
        self.scheduler = scheduler
        self.profiler = profiler

    def work_loop_concurrent(self, on_frame_callback: Optional[Callable[[int, float], None]] = None):
        """
        Concurrent Work Loop: Menjalankan Fiber task dengan time-slicing 5ms.
        Bila waktu habis, menyerahkan kontrol ke host (browser paint).
        """
        frame_index = 0
        in_progress_fibers = []

        print(f"{Color.CYAN}[Fiber Engine]{Color.RESET} Memulai Concurrent Work Loop...")

        while self.scheduler.task_queue:
            frame_index += 1
            frame_start = time.perf_counter() * 1000.0
            slice_work_done = 0

            print(f"\n{Color.BOLD}{Color.BLUE}--- Frame #{frame_index} (5ms Budget Window) ---{Color.RESET}")

            while self.scheduler.task_queue and not self.scheduler.should_yield_to_host(frame_start):
                current_task = heapq.heappop(self.scheduler.task_queue)
                
                # Check React.memo / Bailout Optimization
                if (current_task.memoized_props and current_task.next_props and 
                    current_task.memoized_props == current_task.next_props):
                    self.profiler.bailout_count += 1
                    print(f"  {Color.GREEN}⚡ [BAILOUT]{Color.RESET} <{current_task.component_name} /> props identical. Skipping render tree!")
                    current_task.completed_units = current_task.work_units
                    in_progress_fibers.append(current_task)
                    continue

                # Execute incremental atomic Fiber work unit
                work_step_start = time.perf_counter() * 1000.0
                time.sleep(0.0012) # Simulasikan kalkulasi JS V8 diffing (1.2ms)
                current_task.completed_units += 1
                slice_work_done += 1
                
                unit_time = (time.perf_counter() * 1000.0) - work_step_start
                current_task.actual_duration_ms += unit_time

                priority_name = LANE_NAMES.get(LanePriority(current_task.priority), "Unknown")
                print(f"  {Color.MAGENTA}🔨 [WORK]{Color.RESET} <{current_task.component_name} /> "
                      f"Progress: {current_task.completed_units}/{current_task.work_units} "
                      f"Lane: {Color.YELLOW}{priority_name}{Color.RESET}")

                if not current_task.is_completed:
                    # Belum selesai, kembalikan ke Priority Queue
                    heapq.heappush(self.scheduler.task_queue, current_task)
                else:
                    in_progress_fibers.append(current_task)

            elapsed_frame = (time.perf_counter() * 1000.0) - frame_start
            if elapsed_frame > 16.67:
                self.profiler.total_jank_frames += 1
                print(f"  {Color.RED}⚠ [JANK WARNING]{Color.RESET} Frame melebih batas 16.6ms! ({elapsed_frame:.2f}ms)")
            else:
                print(f"  {Color.GREEN}✔ [YIELD TO HOST]{Color.RESET} Menyerahkan thread ke browser ({elapsed_frame:.2f}ms terpakai). Frame FPS terjaga.")

            if on_frame_callback:
                on_frame_callback(frame_index, elapsed_frame)

            # Simulasi Browser Paint & Event Polling
            time.sleep(0.005)

        # Commit Phase (Synchronous & Non-Interruptible)
        self._commit_root(in_progress_fibers)

    def _commit_root(self, completed_fibers: List[FiberTask]):
        print(f"\n{Color.BOLD}{Color.BG_BLUE} ⚛ COMMIT PHASE: MUTATING DOM TREE (SYNCHRONOUS) ⚛ {Color.RESET}")
        commit_start = time.perf_counter() * 1000.0

        total_base = sum(f.base_duration_ms for f in completed_fibers)
        total_actual = sum(f.actual_duration_ms for f in completed_fibers)

        for f in completed_fibers:
            indent = "  " * f.fiber_depth
            print(f"{indent}📌 DOM Mutation Applied: <{f.component_name} /> [Lane: {f.priority}]")

        commit_duration = (time.perf_counter() * 1000.0) - commit_start
        print(f"{Color.CYAN}Commit Phase Selesai dalam {commit_duration:.2f}ms.{Color.RESET}")
        self.profiler.record_commit("Render & Commit Root", total_actual + commit_duration, total_base, completed_fibers)

def demo_synchronous_blocking_render():
    """
    Demo 1: Render Klasik (Stack Reconciler / React <=15)
    Memblokir main thread secara total selama 80ms+.
    """
    print(f"\n{Color.BOLD}{Color.RED}===================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.RED} SKENARIO 1: SYNCHRONOUS BLOCKING RENDER (REACT <=15) {Color.RESET}")
    print(f"{Color.BOLD}{Color.RED}===================================================={Color.RESET}")
    print("Main thread akan diblokir tanpa time-slicing. Perhatikan tidak ada yielding.")
    
    start = time.perf_counter() * 1000.0
    for i in range(1, 16):
        time.sleep(0.004) # 4ms per node
        print(f"  [Stack Reconciler] Rendering Node #{i:02d} - Main thread FREEZING...")
    
    total = (time.perf_counter() * 1000.0) - start
    print(f"{Color.RED}✖ Selesai dalam {total:.2f}ms. Main thread membeku total, user input drop!{Color.RESET}\n")

def demo_concurrent_time_sliced_render():
    """
    Demo 2: Concurrent Scheduler Time Slicing (React 18)
    Membagi kerja menjadi irisan 5ms dan yield ke host.
    """
    print(f"\n{Color.BOLD}{Color.GREEN}===================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.GREEN} SKENARIO 2: CONCURRENT TIME SLICING (REACT 18)     {Color.RESET}")
    print(f"{Color.BOLD}{Color.GREEN}===================================================={Color.RESET}")
    
    scheduler = ReactScheduler()
    profiler = ReactProfilerCollector()
    reconciler = FiberReconcilerEngine(scheduler, profiler)

    # Buat komponen hierarki berat
    scheduler.schedule_callback(LanePriority.DEFAULT_LANE, "AppRoot", work_units=2, depth=1)
    scheduler.schedule_callback(LanePriority.DEFAULT_LANE, "DataGridTable", work_units=6, depth=2)
    scheduler.schedule_callback(LanePriority.DEFAULT_LANE, "AnalyticsChart", work_units=5, depth=3)
    scheduler.schedule_callback(LanePriority.DEFAULT_LANE, "SidebarNav", work_units=2, depth=2)
    scheduler.schedule_callback(LanePriority.DEFAULT_LANE, "FooterWidget", work_units=1, depth=2)

    reconciler.work_loop_concurrent()
    profiler.print_flamegraph_summary()

def demo_priority_preemption_simulation():
    """
    Demo 3: Preemption / Interruption oleh Urgent Input
    Saat render transisi lambat sedang berlangsung, user mengetik (SyncLane)
    yang menyela kerja transisi non-urgent.
    """
    print(f"\n{Color.BOLD}{Color.YELLOW}===================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.YELLOW} SKENARIO 3: HIGH PRIORITY INTERRUPT / PREEMPTION  {Color.RESET}")
    print(f"{Color.BOLD}{Color.YELLOW}===================================================={Color.RESET}")
    print("Mendaftarkan heavy transition (startTransition) lalu menyela dengan Keyboard Input (SyncLane).\n")

    scheduler = ReactScheduler()
    profiler = ReactProfilerCollector()
    reconciler = FiberReconcilerEngine(scheduler, profiler)

    # Tugas low priority (Transition)
    scheduler.schedule_callback(
        LanePriority.TRANSITION_LANE, "HeavyDataFilterList", 
        work_units=8, depth=2, 
        memoized_props={"query": "alpha"}, next_props={"query": "beta"}
    )

    # Frame 1 callback akan menyisipkan SyncLane di tengah jalan
    def on_frame_hook(frame_idx: int, duration_ms: float):
        if frame_idx == 1:
            print(f"\n  {Color.RED}{Color.BOLD}⚡ [USER EVENT DETECTED]{Color.RESET} User mengetik di <SearchInput />!")
            print(f"  {Color.YELLOW}--> Menyuntikkan SyncLane Task langsung ke prioritas antrean terdepan!{Color.RESET}")
            scheduler.schedule_callback(
                LanePriority.SYNC_LANE, "SearchInputFeedback", 
                work_units=1, depth=1,
                memoized_props={"value": "a"}, next_props={"value": "ab"}
            )

    reconciler.work_loop_concurrent(on_frame_callback=on_frame_hook)
    profiler.print_flamegraph_summary()

def demo_memoization_bailout():
    """
    Demo 4: Optimasi Memoization & Bailout Subtree
    Menunjukkan bagaimana props equality comparison mencegah reconciler mengeksekusi render tree.
    """
    print(f"\n{Color.BOLD}{Color.CYAN}===================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} SKENARIO 4: REACT.MEMO & SELECTOR BAILOUTS         {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}===================================================={Color.RESET}")

    scheduler = ReactScheduler()
    profiler = ReactProfilerCollector()
    reconciler = FiberReconcilerEngine(scheduler, profiler)

    # Node dengan identical props (Bailout)
    scheduler.schedule_callback(
        LanePriority.DEFAULT_LANE, "ExpensiveNavigationMenu",
        work_units=4, depth=1,
        memoized_props={"theme": "dark", "locale": "id"},
        next_props={"theme": "dark", "locale": "id"}
    )

    # Node dengan props baru (Must Render)
    scheduler.schedule_callback(
        LanePriority.DEFAULT_LANE, "DynamicLiveFeed",
        work_units=3, depth=1,
        memoized_props={"items": [1, 2]},
        next_props={"items": [1, 2, 3]}
    )

    # Node child yang juga identical (Bailout)
    scheduler.schedule_callback(
        LanePriority.DEFAULT_LANE, "StaticFooterLegal",
        work_units=2, depth=2,
        memoized_props={"version": "2.4"},
        next_props={"version": "2.4"}
    )

    reconciler.work_loop_concurrent()
    profiler.print_flamegraph_summary()

def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}╔═══════════════════════════════════════════════════════════════════════╗
║   ⚛  REACT CONCURRENT SCHEDULER & FIBER PROFILING LAB EXERCISE   ⚛   ║
║      BAB-05: Performance Engineering, Profiling & Concurrent Sched    ║
╚═══════════════════════════════════════════════════════════════════════╝{Color.RESET}
"""
    print(banner)

def main_menu():
    print_banner()
    while True:
        print(f"{Color.BOLD}PILIH SKENARIO SIMULASI:{Color.RESET}")
        print(f"  {Color.WHITE}[1]{Color.RESET} Run Synchronous Blocking Render (React <=15 Stack Engine)")
        print(f"  {Color.WHITE}[2]{Color.RESET} Run Concurrent Time-Slicing Loop (5ms Slices & Yielding)")
        print(f"  {Color.WHITE}[3]{Color.RESET} Run Priority Interruption Demo (SyncLane Preempting Transition)")
        print(f"  {Color.WHITE}[4]{Color.RESET} Run React.memo / Bailout Optimization Engine")
        print(f"  {Color.WHITE}[5]{Color.RESET} Jalankan Seluruh Skenario Secara Sekuensial (Full Suite)")
        print(f"  {Color.WHITE}[q]{Color.RESET} Keluar")
        
        choice = input(f"\n{Color.CYAN}Masukkan pilihan (1-5/q): {Color.RESET}").strip().lower()
        if choice == "1":
            demo_synchronous_blocking_render()
        elif choice == "2":
            demo_concurrent_time_sliced_render()
        elif choice == "3":
            demo_priority_preemption_simulation()
        elif choice == "4":
            demo_memoization_bailout()
        elif choice == "5":
            demo_synchronous_blocking_render()
            demo_concurrent_time_sliced_render()
            demo_priority_preemption_simulation()
            demo_memoization_bailout()
            print(f"{Color.GREEN}{Color.BOLD}Seluruh simulasi arsitektur React Concurrent berhasil dijalankan!{Color.RESET}\n")
        elif choice in ("q", "quit", "exit"):
            print(f"{Color.MAGENTA}Menutup lab exercise. Selesai.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan coba lagi.{Color.RESET}\n")

if __name__ == "__main__":
    # If run in non-interactive or automated environment, execute full suite
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        demo_synchronous_blocking_render()
        demo_concurrent_time_sliced_render()
        demo_priority_preemption_simulation()
        demo_memoization_bailout()
    else:
        try:
            main_menu()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Program dihentikan oleh user.{Color.RESET}")
            sys.exit(0)
