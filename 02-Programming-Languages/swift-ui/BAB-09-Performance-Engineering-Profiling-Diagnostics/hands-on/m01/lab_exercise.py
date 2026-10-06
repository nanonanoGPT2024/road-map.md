#!/usr/bin/env python3
"""
SwiftUI Performance Engineering, Profiling & Diagnostics Simulator
BAB-09: Hands-on Lab Exercise (Module 01)

Simulates SwiftUI view lifecycle, identity diffing, dependency invalidation,
_printChanges() diagnostics, frame hitch rate analysis, and lazy layout virtualization.
"""

import sys
import time
import random
from typing import List, Dict, Any, Optional

# ANSI Terminal Colors
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
BG_DARK = "\033[40m"


class ANSI:
    @staticmethod
    def header(title: str) -> str:
        return f"\n{BOLD}{CYAN}{'=' * 65}\n  {title}\n{'=' * 65}{RESET}"

    @staticmethod
    def subheader(title: str) -> str:
        return f"\n{BOLD}{MAGENTA}--- [ {title} ] ---{RESET}"

    @staticmethod
    def success(msg: str) -> str:
        return f"{GREEN}[✓ PASS] {msg}{RESET}"

    @staticmethod
    def warning(msg: str) -> str:
        return f"{YELLOW}[⚠ WARN] {msg}{RESET}"

    @staticmethod
    def alert(msg: str) -> str:
        return f"{RED}[✗ HITCH/ALERT] {msg}{RESET}"

    @staticmethod
    def info(msg: str) -> str:
        return f"{BLUE}[ℹ INFO] {msg}{RESET}"

    @staticmethod
    def metric(label: str, val: Any, unit: str = "") -> str:
        return f"  {WHITE}{label:<32}: {BOLD}{YELLOW}{val}{RESET} {DIM}{unit}{RESET}"


class SimulatedView:
    """Represents a SwiftUI View node with structural identity, dependencies, and body calculation."""

    def __init__(self, name: str, explicit_id: Optional[str] = None, is_equatable: bool = False):
        self.name = name
        self.explicit_id = explicit_id  # Explicit identity vs structural identity
        self.is_equatable = is_equatable
        self.last_props: Dict[str, Any] = {}
        self.body_eval_count = 0
        self.total_body_time_ms = 0.0

    def evaluate_body(self, props: Dict[str, Any], artificial_cost_ms: float = 0.5) -> bool:
        """
        Simulates SwiftUI body execution.
        Returns True if body was executed, False if skipped due to Equatable memoization.
        """
        if self.is_equatable and self.last_props == props:
            return False  # Memoized: skipped re-eval

        t_start = time.perf_counter()
        # Simulated expensive computation in body (e.g. DateFormatter, filter/sort inside body)
        time.sleep(artificial_cost_ms / 1000.0)
        elapsed_ms = (time.perf_counter() - t_start) * 1000.0

        self.last_props = props.copy()
        self.body_eval_count += 1
        self.total_body_time_ms += elapsed_ms
        return True


class SwiftUIProfilerDiagnostics:
    """Simulates Self._printChanges() and Frame Hitch Rate analysis."""

    def __init__(self, target_hz: int = 120):
        self.target_hz = target_hz
        self.frame_budget_ms = 1000.0 / target_hz  # 8.33ms for 120Hz ProMotion, 16.67ms for 60Hz
        self.recorded_frames: List[float] = []

    def print_changes(self, view_name: str, changed_inputs: List[str]):
        """Simulates LLDB / SwiftUI internal Self._printChanges() diagnostics."""
        print(f"{DIM}[Self._printChanges]{RESET} {BOLD}{view_name}{RESET}: "
              f"{CYAN}{', '.join(f'@_change: {inp}' for inp in changed_inputs)}{RESET}")

    def record_frame(self, duration_ms: float):
        self.recorded_frames.append(duration_ms)

    def print_hitch_report(self):
        total_frames = len(self.recorded_frames)
        if total_frames == 0:
            return

        hitched_frames = [f for f in self.recorded_frames if f > self.frame_budget_ms]
        hitch_rate_pct = (len(hitched_frames) / total_frames) * 100.0
        avg_frame_time = sum(self.recorded_frames) / total_frames
        max_frame_time = max(self.recorded_frames)

        print(ANSI.subheader(f"Instruments Hitch & Frame Analysis ({self.target_hz}Hz Target)"))
        print(ANSI.metric("Target Frame Budget", f"{self.frame_budget_ms:.2f}", "ms"))
        print(ANSI.metric("Total Profiled Frames", total_frames))
        print(ANSI.metric("Average Frame Time", f"{avg_frame_time:.2f}", "ms"))
        print(ANSI.metric("Worst Hitch (Max Duration)", f"{max_frame_time:.2f}", "ms"))
        print(ANSI.metric("Hitch Ratio", f"{hitch_rate_pct:.1f}%"))

        if hitch_rate_pct > 5.0:
            print(ANSI.alert(f"Critical Hitch Rate ({hitch_rate_pct:.1f}% > 5%)! User interaction will stutter."))
        else:
            print(ANSI.success("Frame rendering is buttery smooth within target V-Sync boundaries."))


def run_identity_invalidation_lab():
    """Scenario 1: Structural vs Explicit Identity and Unstable id() traps."""
    print(ANSI.header("SCENARIO 1: View Identity & Structural Diffing Invalidation"))
    print(f"{DIM}SwiftUI computes body invalidations by tracking Structural & Explicit Identities.")
    print(f"Assigning unstable UUIDs in ForEach(items, id: \\.id) forces full graph destruction.{RESET}\n")

    # Bad Pattern: Random UUID recreated every parent render
    print(f"{BOLD}[Mode A: Anti-Pattern - Unstable Explicit Identity (UUID() in body)]{RESET}")
    profiler = SwiftUIProfilerDiagnostics(target_hz=60)
    items = ["Post #1", "Post #2", "Post #3"]

    for cycle in range(1, 4):
        print(f"\n{YELLOW}--- Render Cycle {cycle} (Parent State Changed) ---{RESET}")
        profiler.print_changes("FeedListView", ["@State selectedFilter"])
        for idx, item in enumerate(items):
            unstable_id = f"random-uuid-{random.randint(1000, 9999)}"
            row_view = SimulatedView(f"FeedRow[{idx}]", explicit_id=unstable_id, is_equatable=False)
            executed = row_view.evaluate_body({"title": item, "id": unstable_id}, artificial_cost_ms=6.0)
            print(f"  {RED}↳ Identity Destroyed & Rebuilt:{RESET} {row_view.name} (id: {unstable_id}) -> body evaluated: {executed}")
            profiler.record_frame(row_view.total_body_time_ms)

    # Good Pattern: Stable persistent model identity
    print(f"\n{BOLD}[Mode B: Optimized Pattern - Stable Domain Identity & Equatable Row]{RESET}")
    stable_rows = [SimulatedView(f"StableRow[{idx}]", explicit_id=f"model-stable-id-{idx}", is_equatable=True)
                   for idx in range(len(items))]

    for cycle in range(1, 4):
        print(f"\n{GREEN}--- Render Cycle {cycle} (Parent State Changed, Unrelated Input) ---{RESET}")
        profiler.print_changes("FeedListView", ["@State selectedFilter"])
        for idx, row in enumerate(stable_rows):
            executed = row.evaluate_body({"title": items[idx], "id": row.explicit_id}, artificial_cost_ms=6.0)
            if executed:
                print(f"  {YELLOW}↳ Identity Kept:{RESET} {row.name} -> Body Re-evaluated")
            else:
                print(f"  {GREEN}↳ Identity Kept & Equatable Skipped:{RESET} {row.name} -> Body evaluation bypassed! (0.00ms)")
            profiler.record_frame(0.1 if not executed else row.total_body_time_ms)

    profiler.print_hitch_report()


def run_observation_fine_grained_lab():
    """Scenario 2: @ObservedObject (Combine) vs Swift 5.9+ @Observable Fine-Grained Tracking."""
    print(ANSI.header("SCENARIO 2: Observation Granularity (@ObservedObject vs @Observable)"))
    print(f"{DIM}With Combine ObservableObject, any @Published emission invalidates ALL observing views.")
    print(f"With @Observable (Observation macro), SwiftUI only tracks accessed property dependencies.{RESET}\n")

    fields = ["username", "follower_count", "avatar_url"]
    
    print(f"{BOLD}[1. Combine @ObservedObject Simulation]{RESET}")
    print(f"{CYAN}Action: Updating 'follower_count' in ProfileViewModel...{RESET}")
    print(ANSI.info("ObservedObject emits objectWillChange -> All subviews re-evaluate regardless of property used!"))
    
    views_combine = {
        "ProfileHeader": {"uses": "username", "evaluated": True},
        "FollowerBadge": {"uses": "follower_count", "evaluated": True},
        "AvatarImage":   {"uses": "avatar_url", "evaluated": True}
    }
    for view_name, meta in views_combine.items():
        print(f"  {YELLOW}[Self._printChanges]{RESET} {view_name}: {RED}@_change: ProfileViewModel changed{RESET} -> {ANSI.alert('Re-rendered')}")

    print(f"\n{BOLD}[2. Swift 5.9+ @Observable Simulation]{RESET}")
    print(f"{CYAN}Action: Updating 'follower_count' with fine-grained tracking...{RESET}")
    views_observable = {
        "ProfileHeader": {"uses": "username", "evaluated": False},
        "FollowerBadge": {"uses": "follower_count", "evaluated": True},
        "AvatarImage":   {"uses": "avatar_url", "evaluated": False}
    }
    for view_name, meta in views_observable.items():
        if meta["evaluated"]:
            print(f"  {DIM}[Self._printChanges]{RESET} {view_name}: {GREEN}@_change: \\ProfileModel.follower_count{RESET} -> {ANSI.warning('Re-rendered (Targeted)')}")
        else:
            print(f"  {DIM}[Self._printChanges]{RESET} {view_name}: {DIM}No dependency change detected -> {GREEN}[BYPASS / NO-OP]{RESET}")


def run_virtualization_benchmark_lab():
    """Scenario 3: Layout Virtualization (VStack vs LazyVStack)."""
    print(ANSI.header("SCENARIO 3: Layout Virtualization & Memory Allocations"))
    print(f"{DIM}VStack evaluates and materializes all child view bodies upon parent render.")
    print(f"LazyVStack only instantiates and evaluates items visible inside the viewport.{RESET}\n")

    total_items = 2500
    viewport_items = 12

    print(f"Dataset Size: {BOLD}{total_items} items{RESET} | Viewport visible: {BOLD}{viewport_items} items{RESET}\n")

    # VStack Simulation
    t0 = time.perf_counter()
    vstack_allocated = total_items
    vstack_body_evals = total_items
    mem_vstack_kb = total_items * 1.8  # ~1.8KB per view instance in memory
    t_vstack_ms = (time.perf_counter() - t0) * 1000.0 + (total_items * 0.008)

    print(f"{BOLD}{RED}Eager VStack Execution:{RESET}")
    print(ANSI.metric("Instantiated View Structs", vstack_allocated))
    print(ANSI.metric("Body Invocations", vstack_body_evals))
    print(ANSI.metric("Estimated Memory Footprint", f"{mem_vstack_kb / 1024:.2f}", "MB"))
    print(ANSI.metric("Initial Render Latency", f"{t_vstack_ms:.2f}", "ms"))
    if t_vstack_ms > 16.67:
        print(f"  {ANSI.alert('Dropped initial frames during push transition! Severe UI freeze.')}")

    # LazyVStack Simulation
    t1 = time.perf_counter()
    lazy_allocated = viewport_items + 4  # Viewport + small prefetch buffer
    lazy_body_evals = lazy_allocated
    mem_lazy_kb = lazy_allocated * 1.8
    t_lazy_ms = (time.perf_counter() - t1) * 1000.0 + (lazy_allocated * 0.008)

    print(f"\n{BOLD}{GREEN}LazyVStack Execution:{RESET}")
    print(ANSI.metric("Instantiated View Structs", lazy_allocated))
    print(ANSI.metric("Body Invocations", lazy_body_evals))
    print(ANSI.metric("Estimated Memory Footprint", f"{mem_lazy_kb:.2f}", "KB"))
    print(ANSI.metric("Initial Render Latency", f"{t_lazy_ms:.2f}", "ms"))
    print(f"  {ANSI.success('Zero dropped frames. Instantaneous viewport presentation.')}")


def run_interactive_profiler_quiz():
    """Interactive diagnostic challenge testing performance optimization intuition."""
    print(ANSI.header("INTERACTIVE PROFILING DIAGNOSTICS CHALLENGE"))
    questions = [
        {
            "q": "Di dalam Instruments Time Profiler, View Body terdeteksi memakan waktu 45ms per render.\n   Penyebab paling umum di SwiftUI body adalah:",
            "options": [
                "1. Terlalu banyak menggunakan modifier .padding()",
                "2. Menginisialisasi DateFormatter / NumberFormatter langsung di dalam `var body: some View`",
                "3. Menggunakan struct alih-alih class untuk View",
                "4. Memecah subview menjadi computed property terpisah"
            ],
            "answer": "2",
            "explanation": "DateFormatter sangat mahal untuk diinisialisasi. Instansiasi di dalam body yang dievaluasi berulang menyebabkan hitch tinggi."
        },
        {
            "q": "Perintah apa yang bisa disematkan di dalam body untuk debugging runtime alasan view dirender ulang?",
            "options": [
                "1. Self._printChanges()",
                "2. SwiftUI.dumpMemoryGraph()",
                "3. print(self.debugDescription)",
                "4. Instruments.markCurrentFrame()"
            ],
            "answer": "1",
            "explanation": "Self._printChanges() mencetak input/state mana yang memicu evaluasi ulang view body tersebut ke console LLDB."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"\n{BOLD}{CYAN}Pertanyaan {idx}:{RESET} {item['q']}")
        for opt in item["options"]:
            print(f"   {opt}")

        choice = input(f"\n{BOLD}Pilih jawaban (1-4) atau [Enter] untuk lewati: {RESET}").strip()
        if choice == item["answer"]:
            print(f"{GREEN}✓ BENAR! {item['explanation']}{RESET}")
            score += 1
        elif choice == "":
            print(f"{YELLOW}Dilewati. Kunci Jawaban: {item['answer']}. {item['explanation']}{RESET}")
        else:
            print(f"{RED}✗ KURANG TEPAT. Jawaban yang benar adalah {item['answer']}. {item['explanation']}{RESET}")

    print(f"\n{BOLD}Skor Evaluasi: {score}/{len(questions)}{RESET}")


def main_menu():
    """Main interactive driver."""
    while True:
        print(ANSI.header("SWIFTUI PERFORMANCE ENGINEERING & PROFILING LAB (BAB 09)"))
        print("Pilih modul simulasi diagnostik:")
        print(f"  {BOLD}1{RESET}. Simulasi Identity, Diffing & Unstable ID Traps")
        print(f"  {BOLD}2{RESET}. Simulasi Granularitas Re-render (@ObservedObject vs @Observable)")
        print(f"  {BOLD}3{RESET}. Benchmark Virtualisasi Memori & Latensi (VStack vs LazyVStack)")
        print(f"  {BOLD}4{RESET}. Kuis Diagnostik & Optimasi Arsitektur SwiftUI")
        print(f"  {BOLD}5{RESET}. Jalankan Seluruh Rangkaian Benchmark Otomatis")
        print(f"  {BOLD}0{RESET}. Keluar")

        try:
            choice = input(f"\n{BOLD}Pilih opsi [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulator.")
            sys.exit(0)

        if choice == "1":
            run_identity_invalidation_lab()
        elif choice == "2":
            run_observation_fine_grained_lab()
        elif choice == "3":
            run_virtualization_benchmark_lab()
        elif choice == "4":
            run_interactive_profiler_quiz()
        elif choice == "5":
            run_identity_invalidation_lab()
            run_observation_fine_grained_lab()
            run_virtualization_benchmark_lab()
            print(f"\n{GREEN}Seluruh benchmark performa selesai dijalankan.{RESET}")
        elif choice == "0":
            print(f"{CYAN}Sesi Lab Selesai.{RESET}")
            break
        else:
            print(ANSI.warning("Pilihan tidak valid, silakan ulangi."))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_identity_invalidation_lab()
        run_observation_fine_grained_lab()
        run_virtualization_benchmark_lab()
        print(f"\n{GREEN}Mode headless otomatis selesai tanpa error.{RESET}")
    else:
        main_menu()
