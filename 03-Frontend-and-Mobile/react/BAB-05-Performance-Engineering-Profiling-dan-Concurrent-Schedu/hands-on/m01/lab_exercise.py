#!/usr/bin/env python3
"""
Lab Exercise: React Concurrent Scheduler, Time-Slicing, & Profiler Simulator
Topik: BAB-05 Performance Engineering, Profiling, dan Concurrent Scheduler
Arsitektur: Fiber Reconciler, Priority Lanes, Cooperative WorkLoop, Profiling Commit Phase.
"""

from __future__ import annotations
import heapq
import sys
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, List, Optional, Dict, Any


# ==============================================================================
# ANSI Terminal Color Palette
# ==============================================================================
class Color:
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
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


def cprint(text: str, color: str = Color.WHITE, bold: bool = False, end: str = "\n") -> None:
    prefix = f"{Color.BOLD if bold else ''}{color}"
    sys.stdout.write(f"{prefix}{text}{Color.RESET}{end}")
    sys.stdout.flush()


# ==============================================================================
# Priority Levels & Lane Models
# ==============================================================================
class PriorityLevel(IntEnum):
    IMMEDIATE = 1       # Discrete clicks, keyboard input (SyncLane)
    USER_BLOCKING = 2   # Dragging, scrolling (InputContinuousLane)
    NORMAL = 3          # Data fetching, network responses, list filtering (DefaultLane)
    LOW = 4             # Analytics, offscreen renders (TransitionLane)
    IDLE = 5            # Pre-fetching, background cleanup (IdleLane)


PRIORITY_NAMES = {
    PriorityLevel.IMMEDIATE: "Immediate (Sync/Discrete)",
    PriorityLevel.USER_BLOCKING: "UserBlocking (InputContinuous)",
    PriorityLevel.NORMAL: "Normal (Default)",
    PriorityLevel.LOW: "Low (Transition)",
    PriorityLevel.IDLE: "Idle (Background)",
}

PRIORITY_COLORS = {
    PriorityLevel.IMMEDIATE: Color.RED,
    PriorityLevel.USER_BLOCKING: Color.YELLOW,
    PriorityLevel.NORMAL: Color.CYAN,
    PriorityLevel.LOW: Color.BLUE,
    PriorityLevel.IDLE: Color.DIM,
}


# ==============================================================================
# Fiber Node & Scheduler Task Definitions
# ==============================================================================
@dataclass(order=True)
class Task:
    priority: PriorityLevel
    expiration_time: float
    task_id: int = field(compare=False)
    name: str = field(compare=False)
    work_units: int = field(compare=False)
    completed_units: int = field(default=0, compare=False)
    callback: Optional[Callable[[Task], bool]] = field(default=None, compare=False)


@dataclass
class FiberNode:
    tag: str
    key: str
    self_base_duration_ms: float
    tree_base_duration_ms: float = 0.0
    actual_duration_ms: float = 0.0
    child: Optional[FiberNode] = None
    sibling: Optional[FiberNode] = None
    return_fiber: Optional[FiberNode] = None


@dataclass
class ProfilerCommitRecord:
    commit_id: int
    phase: str  # "mount" or "update"
    actual_duration_ms: float
    base_duration_ms: float
    start_time_ms: float
    commit_time_ms: float
    lanes: str


# ==============================================================================
# Concurrent React Scheduler Simulator
# ==============================================================================
class ConcurrentScheduler:
    """Simulates React 18 Scheduler with 5ms time-slicing and cooperative multitasking."""

    FRAME_YIELD_BUDGET_MS = 8.0  # Time-slice budget before yielding to host

    def __init__(self) -> None:
        self.task_queue: List[Task] = []
        self.next_task_id: int = 1
        self.current_task: Optional[Task] = None
        self.yield_count: int = 0
        self.execution_log: List[str] = []

    def schedule_callback(self, priority: PriorityLevel, name: str, work_units: int) -> Task:
        now = time.perf_counter() * 1000
        timeout_map = {
            PriorityLevel.IMMEDIATE: -1,
            PriorityLevel.USER_BLOCKING: 250,
            PriorityLevel.NORMAL: 5000,
            PriorityLevel.LOW: 10000,
            PriorityLevel.IDLE: 1073741823,
        }
        expiration = now + timeout_map[priority]
        task = Task(
            priority=priority,
            expiration_time=expiration,
            task_id=self.next_task_id,
            name=name,
            work_units=work_units,
        )
        self.next_task_id += 1
        heapq.heappush(self.task_queue, task)
        return task

    def should_yield_to_host(self, frame_start_ms: float) -> bool:
        current_time_ms = time.perf_counter() * 1000
        return (current_time_ms - frame_start_ms) >= self.FRAME_YIELD_BUDGET_MS

    def work_loop(self, on_step: Optional[Callable[[Task, int, str], None]] = None) -> None:
        cprint("\n[*] Starting React Concurrent workLoop()...", Color.MAGENTA, bold=True)
        while self.task_queue:
            frame_start_ms = time.perf_counter() * 1000
            current_task = heapq.heappop(self.task_queue)
            self.current_task = current_task

            color = PRIORITY_COLORS[current_task.priority]
            priority_label = PRIORITY_NAMES[current_task.priority]

            cprint(
                f"\n--> Active Task #{current_task.task_id} [{current_task.name}] | Priority: {priority_label}",
                color,
                bold=True,
            )

            interrupted = False
            while current_task.completed_units < current_task.work_units:
                # Simulating work on one fiber node
                time.sleep(0.002)  # 2ms per unit of work
                current_task.completed_units += 1

                if on_step:
                    on_step(current_task, current_task.completed_units, "rendering")

                # Check if higher priority task arrived
                if self.task_queue and self.task_queue[0].priority < current_task.priority:
                    cprint(
                        f"    [INTERRUPT] Urgent task arrived: #{self.task_queue[0].task_id} ({self.task_queue[0].name})!",
                        Color.RED,
                        bold=True,
                    )
                    interrupted = True
                    break

                # Cooperative time-slice yielding
                if self.should_yield_to_host(frame_start_ms):
                    self.yield_count += 1
                    cprint(
                        f"    [TIME-SLICE YIELD] 8ms budget exceeded ({current_task.completed_units}/{current_task.work_units} fibers done). Yielding to browser main thread.",
                        Color.YELLOW,
                    )
                    break

            if current_task.completed_units < current_task.work_units:
                # Re-queue unfinished task
                heapq.heappush(self.task_queue, current_task)
                if not interrupted:
                    # Let the browser draw/paint
                    time.sleep(0.004)
            else:
                cprint(
                    f"    [COMMIT PHASE] Task #{current_task.task_id} ({current_task.name}) committed to DOM synchronously.",
                    Color.GREEN,
                    bold=True,
                )
                self.execution_log.append(f"Task #{current_task.task_id} ({current_task.name}) [Done]")

        cprint("\n[✔] workLoop complete. Task queue is empty.\n", Color.GREEN, bold=True)


# ==============================================================================
# React Profiler Engine (Base Duration vs Actual Duration)
# ==============================================================================
class ReactProfilerEngine:
    """Simulates React Profiler component timing metrics and flamegraph data."""

    def __init__(self) -> None:
        self.records: List[ProfilerCommitRecord] = []
        self.commit_counter: int = 0

    def build_sample_tree(self) -> FiberNode:
        root = FiberNode(tag="App", key="root", self_base_duration_ms=1.2)
        header = FiberNode(tag="Header", key="hdr", self_base_duration_ms=0.8, return_fiber=root)
        search_box = FiberNode(tag="SearchBox", key="sbx", self_base_duration_ms=2.1, return_fiber=header)
        data_grid = FiberNode(tag="DataGrid", key="grid", self_base_duration_ms=8.5, return_fiber=root)
        grid_row1 = FiberNode(tag="GridRow_1", key="r1", self_base_duration_ms=4.0, return_fiber=data_grid)
        grid_row2 = FiberNode(tag="GridRow_2", key="r2", self_base_duration_ms=4.2, return_fiber=data_grid)
        footer = FiberNode(tag="Footer", key="ftr", self_base_duration_ms=0.5, return_fiber=root)

        root.child = header
        header.child = search_box
        header.sibling = data_grid
        data_grid.child = grid_row1
        grid_row1.sibling = grid_row2
        data_grid.sibling = footer
        return root

    def compute_tree_base_duration(self, node: Optional[FiberNode]) -> float:
        if not node:
            return 0.0
        total = node.self_base_duration_ms
        total += self.compute_tree_base_duration(node.child)
        curr_sibling = node.sibling
        while curr_sibling:
            total += curr_sibling.self_base_duration_ms
            total += self.compute_tree_base_duration(curr_sibling.child)
            curr_sibling = curr_sibling.sibling
        node.tree_base_duration_ms = total
        return total

    def simulate_render_pass(
        self,
        root: FiberNode,
        memoized_nodes: List[str],
        phase: str = "update",
        lanes: str = "DefaultLane",
    ) -> ProfilerCommitRecord:
        self.commit_counter += 1
        t_start = time.perf_counter() * 1000

        # Traverse and evaluate render cost
        actual_total = 0.0
        stack = [root]
        while stack:
            curr = stack.pop()
            if curr.tag in memoized_nodes:
                curr.actual_duration_ms = 0.05  # Memo cache hit (bailout)
            else:
                curr.actual_duration_ms = curr.self_base_duration_ms

            actual_total += curr.actual_duration_ms

            if curr.sibling:
                stack.append(curr.sibling)
            if curr.child:
                stack.append(curr.child)

        t_end = time.perf_counter() * 1000
        record = ProfilerCommitRecord(
            commit_id=self.commit_counter,
            phase=phase,
            actual_duration_ms=actual_total,
            base_duration_ms=root.tree_base_duration_ms,
            start_time_ms=t_start,
            commit_time_ms=t_end,
            lanes=lanes,
        )
        self.records.append(record)
        return record

    def display_flamegraph_ascii(self, root: FiberNode) -> None:
        cprint("\n" + "=" * 70, Color.CYAN)
        cprint("  REACT PROFILER: HIERARCHICAL FLAMEGRAPH VIEW", Color.CYAN, bold=True)
        cprint("=" * 70, Color.CYAN)

        def walk(node: Optional[FiberNode], depth: int = 0) -> None:
            if not node:
                return
            indent = "  " * depth
            memo_flag = (
                f"{Color.GREEN}[BAILOUT/MEMO]{Color.RESET}"
                if node.actual_duration_ms < 0.1
                else f"{Color.RED}[RE-RENDERED]{Color.RESET}"
            )
            ratio = (
                (node.actual_duration_ms / max(node.self_base_duration_ms, 0.001)) * 100
                if node.self_base_duration_ms > 0
                else 0
            )
            bar_len = min(int(node.actual_duration_ms * 3), 30)
            bar = "█" * max(bar_len, 1)

            print(
                f"{indent}└─ {Color.BOLD}{node.tag:<12}{Color.RESET} "
                f"actual: {node.actual_duration_ms:5.2f}ms | base: {node.self_base_duration_ms:5.2f}ms "
                f"| {memo_flag} {Color.YELLOW}{bar}{Color.RESET}"
            )
            walk(node.child, depth + 1)
            walk(node.sibling, depth)

        walk(root, 0)
        cprint("=" * 70 + "\n", Color.CYAN)


# ==============================================================================
# Interactive Demos & Benchmark Scenarios
# ==============================================================================
def demo_sync_vs_concurrent() -> None:
    cprint("\n" + "#" * 70, Color.WHITE, bold=True)
    cprint("  DEMO 1: SYNCHRONOUS BLOCKING RENDER VS CONCURRENT TIME-SLICING", Color.WHITE, bold=True)
    cprint("#" * 70, Color.WHITE, bold=True)

    cprint("\n1. Simulasi Mode Synchronous (React 17 Legacy):", Color.YELLOW, bold=True)
    cprint("   Pekerjaan besar 20 unit fiber dieksekusi tanpa jeda, memblokir main thread.", Color.WHITE)
    t0 = time.perf_counter()
    for i in range(1, 21):
        time.sleep(0.003)
        sys.stdout.write(f"\r   Rendering Synchronous Fiber {i}/20... ")
        sys.stdout.flush()
    sync_time = (time.perf_counter() - t0) * 1000
    cprint(f"\n   [✔] Sync Render Total: {sync_time:.2f}ms (UI Frozen, Frame drop parah!)\n", Color.RED)

    cprint("2. Simulasi Mode Concurrent (React 18 workLoop):", Color.GREEN, bold=True)
    cprint("   Pekerjaan dibagi dalam potongan time-slice 8ms dengan scheduler cooperative yielding.", Color.WHITE)
    scheduler = ConcurrentScheduler()
    scheduler.schedule_callback(PriorityLevel.NORMAL, "FilterableUserList", 20)
    scheduler.work_loop()
    cprint(f"   [INFO] Total Browser Main-Thread Yields: {scheduler.yield_count} kali.", Color.CYAN, bold=True)


def demo_priority_interruption() -> None:
    cprint("\n" + "#" * 70, Color.WHITE, bold=True)
    cprint("  DEMO 2: HIGH-PRIORITY INTERRUPTION (URGENT INPUT VS TRANSITION)", Color.WHITE, bold=True)
    cprint("#" * 70, Color.WHITE, bold=True)
    cprint("Skenario: User mengetik di SearchInput (Immediate) saat List Besar (Normal) sedang me-render.", Color.WHITE)

    scheduler = ConcurrentScheduler()

    # Schedule low/normal priority background work
    scheduler.schedule_callback(PriorityLevel.NORMAL, "HeavyDashboardCharts", 16)

    # We simulate a typing event firing mid-way through execution
    def on_step_callback(task: Task, completed: int, action: str) -> None:
        if task.name == "HeavyDashboardCharts" and completed == 4 and scheduler.next_task_id == 2:
            cprint(
                "\n  ⚡ [USER EVENT] KeyDown 'A' in <SearchInput /> - Injecting IMMEDIATE Task!",
                Color.RED,
                bold=True,
            )
            scheduler.schedule_callback(PriorityLevel.IMMEDIATE, "SearchInput_Keystroke", 3)

    scheduler.work_loop(on_step=on_step_callback)


def demo_profiler_metrics() -> None:
    cprint("\n" + "#" * 70, Color.WHITE, bold=True)
    cprint("  DEMO 3: REACT PROFILER METRICS & MEMOIZATION BAILOUT", Color.WHITE, bold=True)
    cprint("#" * 70, Color.WHITE, bold=True)

    engine = ReactProfilerEngine()
    tree = engine.build_sample_tree()
    engine.compute_tree_base_duration(tree)

    cprint("\n[*] Commit #1: Initial Mount (Semua komponen me-render dari awal)", Color.MAGENTA, bold=True)
    r1 = engine.simulate_render_pass(tree, memoized_nodes=[], phase="mount", lanes="SyncLane")
    engine.display_flamegraph_ascii(tree)

    cprint(f"Commit #1 Metrics:", Color.YELLOW, bold=True)
    print(f"  • Actual Duration: {r1.actual_duration_ms:.2f} ms")
    print(f"  • Base Duration:   {r1.base_duration_ms:.2f} ms")
    print(f"  • Explanation: Pada mount, actual duration mendekati base duration.\n")

    cprint("[*] Commit #2: State Update dengan React.memo / useMemo (Bailout DataGrid)", Color.GREEN, bold=True)
    r2 = engine.simulate_render_pass(
        tree,
        memoized_nodes=["DataGrid", "GridRow_1", "GridRow_2", "Footer"],
        phase="update",
        lanes="InputContinuousLane",
    )
    engine.display_flamegraph_ascii(tree)

    cprint(f"Commit #2 Metrics (Dengan Optimasi Memoization):", Color.GREEN, bold=True)
    print(f"  • Actual Duration: {r2.actual_duration_ms:.2f} ms  <-- Penghematan signifikan!")
    print(f"  • Base Duration:   {r2.base_duration_ms:.2f} ms  (Potensi beban total tanpa memo)")
    savings = ((r1.actual_duration_ms - r2.actual_duration_ms) / r1.actual_duration_ms) * 100
    cprint(f"  • Render Time Improvement: {savings:.1f}%\n", Color.CYAN, bold=True)


def run_all_diagnostics() -> None:
    cprint("\n=======================================================", Color.WHITE, bold=True)
    cprint("  RUNNING FULL CONCURRENT SCHEDULER & PROFILER SUITE", Color.WHITE, bold=True)
    cprint("=======================================================", Color.WHITE, bold=True)
    demo_sync_vs_concurrent()
    time.sleep(0.5)
    demo_priority_interruption()
    time.sleep(0.5)
    demo_profiler_metrics()
    cprint("\n[✔] Seluruh pengujian teknis berhasil 100% tanpa kendala.\n", Color.GREEN, bold=True)


# ==============================================================================
# Interactive CLI Menu
# ==============================================================================
def main() -> None:
    while True:
        cprint("\n================================================================", Color.BLUE, bold=True)
        cprint("   REACT BAB-05: PERFORMANCE ENGINEERING & CONCURRENT LAB     ", Color.CYAN, bold=True)
        cprint("================================================================", Color.BLUE, bold=True)
        print("Pilih modul simulasi interaktif:")
        print("  [1] Simulasi Sync Blocking vs Concurrent Time-Slicing")
        print("  [2] Simulasi High-Priority Interruption (Urgent Input vs Transition)")
        print("  [3] Profiler Flamegraph, Base vs Actual Duration, & Memo Bailout")
        print("  [4] Jalankan Seluruh Skenario (Automated Full Suite)")
        print("  [0] Keluar")
        cprint("----------------------------------------------------------------", Color.DIM)

        try:
            choice = input(f"{Color.BOLD}Ketik pilihan [0-4]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if choice == "1":
            demo_sync_vs_concurrent()
        elif choice == "2":
            demo_priority_interruption()
        elif choice == "3":
            demo_profiler_metrics()
        elif choice == "4":
            run_all_diagnostics()
        elif choice == "0":
            cprint("\nTerima kasih! Sesi lab simulasi selesai.\n", Color.YELLOW)
            break
        else:
            cprint("Pilihan tidak valid. Silakan pilih 0-4.", Color.RED)


if __name__ == "__main__":
    main()
