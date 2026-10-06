#!/usr/bin/env python3
"""
Performance Engineering, Profiling & Telemetry Simulator (JavaScript Runtime Internals)
BAB-09: Hands-on Lab Exercise (Module 01)

Simulates key V8 engine and JS runtime performance mechanisms:
1. Hidden Classes (Shapes) & Inline Cache (IC) States (Monomorphic vs Megamorphic)
2. Generational Garbage Collection (Young Gen Scavenger & Old Gen Mark-Sweep)
3. Event Loop Lag Profiling, Task Budgets & Microtask Starvation
4. Call-Stack Sampling Profiler & ASCII Flamegraph Telemetry
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ANSI Terminal Styling
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[1;31m"
CLR_GREEN = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_BLUE = "\033[1;34m"
CLR_MAGENTA = "\033[1;35m"
CLR_CYAN = "\033[1;36m"
CLR_WHITE = "\033[1;37m"
BG_BLUE = "\033[44m"
BG_DARK = "\033[40m"


def header(title: str) -> None:
    line = "═" * 70
    print(f"\n{CLR_CYAN}{line}")
    print(f" {CLR_BOLD}{CLR_WHITE}⚡ {title}{CLR_RESET}")
    print(f"{CLR_CYAN}{line}{CLR_RESET}\n")


def status_badge(label: str, ok: bool) -> str:
    color = CLR_GREEN if ok else CLR_RED
    icon = "✓" if ok else "✗"
    return f"{color}[{icon} {label}]{CLR_RESET}"


# ==============================================================================
# 1. V8 HIDDEN CLASS (MAP/SHAPE) & INLINE CACHING SIMULATION
# ==============================================================================

@dataclass
class V8Shape:
    shape_id: str
    property_offsets: Dict[str, int] = field(default_factory=dict)
    transition_table: Dict[str, str] = field(default_factory=dict)


class V8Object:
    def __init__(self, shape: V8Shape):
        self.shape = shape
        self.properties: List[object] = []

    def set_property(self, key: str, value: object, engine: "V8Engine") -> None:
        if key in self.shape.property_offsets:
            offset = self.shape.property_offsets[key]
            self.properties[offset] = value
        else:
            # Transition to a new shape
            new_shape = engine.get_or_create_transition(self.shape, key)
            self.shape = new_shape
            self.properties.append(value)


class V8Engine:
    def __init__(self):
        self.root_shape = V8Shape(shape_id="Shape_Root", property_offsets={})
        self.shapes: Dict[str, V8Shape] = {"Shape_Root": self.root_shape}
        self.shape_counter = 0

    def get_or_create_transition(self, current: V8Shape, key: str) -> V8Shape:
        if key in current.transition_table:
            next_id = current.transition_table[key]
            return self.shapes[next_id]

        self.shape_counter += 1
        new_id = f"Shape_{self.shape_counter}_{key}"
        new_offsets = dict(current.property_offsets)
        new_offsets[key] = len(new_offsets)

        new_shape = V8Shape(shape_id=new_id, property_offsets=new_offsets)
        current.transition_table[key] = new_id
        self.shapes[new_id] = new_shape
        return new_shape


class InlineCacheSite:
    """Simulates JIT Inline Cache state: UNINITIALIZED -> MONO -> POLY -> MEGAMORPHIC"""
    def __init__(self, name: str):
        self.name = name
        self.state = "UNINITIALIZED"
        self.cached_shapes: List[str] = []
        self.hits = 0
        self.misses = 0

    def access(self, obj: V8Object, prop_name: str) -> Tuple[object, float]:
        start = time.perf_counter_ns()
        shape_id = obj.shape.shape_id

        if shape_id in self.cached_shapes:
            # Fast-path hit
            self.hits += 1
            offset = obj.shape.property_offsets[prop_name]
            val = obj.properties[offset]
            overhead_ns = (time.perf_counter_ns() - start) + random.uniform(1.0, 3.0)
            return val, overhead_ns

        # Cache Miss
        self.misses += 1
        if len(self.cached_shapes) == 0:
            self.cached_shapes.append(shape_id)
            self.state = "MONOMORPHIC"
        elif len(self.cached_shapes) < 4:
            self.cached_shapes.append(shape_id)
            self.state = f"POLYMORPHIC({len(self.cached_shapes)})"
        else:
            self.state = "MEGAMORPHIC"

        offset = obj.shape.property_offsets.get(prop_name, 0)
        val = obj.properties[offset] if offset < len(obj.properties) else None
        # Megamorphic hash table fallback penalty
        overhead_ns = (time.perf_counter_ns() - start) + (random.uniform(25.0, 45.0) if self.state == "MEGAMORPHIC" else random.uniform(8.0, 15.0))
        return val, overhead_ns


def run_v8_shape_and_ic_demo() -> None:
    header("Simulation 1: V8 Hidden Classes & Inline Cache (IC) Degradation")
    engine = V8Engine()
    ic = InlineCacheSite(name="fetchPropertyX")

    print(f"{CLR_YELLOW}[Case A] Predictable shape initialization (Optimized Monomorphic path){CLR_RESET}")
    monomorphic_objs: List[V8Object] = []
    for _ in range(500):
        o = V8Object(engine.root_shape)
        o.set_property("x", 42, engine)
        o.set_property("y", 100, engine)
        monomorphic_objs.append(o)

    mono_times = []
    for obj in monomorphic_objs:
        _, lat = ic.access(obj, "x")
        mono_times.append(lat)

    avg_mono = sum(mono_times) / len(mono_times)
    print(f"  Shape ID      : {CLR_GREEN}{monomorphic_objs[0].shape.shape_id}{CLR_RESET}")
    print(f"  IC State      : {CLR_GREEN}{ic.state}{CLR_RESET} (Hits: {ic.hits}, Misses: {ic.misses})")
    print(f"  Avg Access Lat: {CLR_GREEN}{avg_mono:.2f} ns{CLR_RESET}")

    print(f"\n{CLR_YELLOW}[Case B] De-optimized random property ordering (Megamorphic path){CLR_RESET}")
    # Induce shape explosion by altering property initialization order
    megamorphic_objs: List[V8Object] = []
    for i in range(100):
        o = V8Object(engine.root_shape)
        if i % 5 == 0:
            o.set_property("x", i, engine)
            o.set_property("y", i * 2, engine)
        elif i % 5 == 1:
            o.set_property("y", i * 2, engine)
            o.set_property("x", i, engine)
        elif i % 5 == 2:
            o.set_property("z", 999, engine)
            o.set_property("x", i, engine)
        elif i % 5 == 3:
            o.set_property("a", 1, engine)
            o.set_property("x", i, engine)
        else:
            o.set_property("temp", True, engine)
            o.set_property("x", i, engine)
        megamorphic_objs.append(o)

    mega_times = []
    for obj in megamorphic_objs:
        _, lat = ic.access(obj, "x")
        mega_times.append(lat)

    avg_mega = sum(mega_times) / len(mega_times)
    penalty_ratio = (avg_mega / avg_mono) if avg_mono > 0 else 1.0

    print(f"  Total Shapes  : {CLR_MAGENTA}{len(engine.shapes)}{CLR_RESET} active maps in V8 Isolate")
    print(f"  IC Final State: {CLR_RED}{ic.state}{CLR_RESET} (Deoptimized to generic stub)")
    print(f"  Avg Access Lat: {CLR_RED}{avg_mega:.2f} ns{CLR_RESET} ({CLR_BOLD}{penalty_ratio:.1f}x slower{CLR_RESET})")
    print(f"  Diagnosis     : {CLR_DIM}Hidden class transitions ruined inline caching; polymorphic IC overflowed into megamorphic dictionary.{CLR_RESET}")


# ==============================================================================
# 2. GENERATIONAL GARBAGE COLLECTION SIMULATION
# ==============================================================================

@dataclass
class HeapObject:
    obj_id: int
    size_kb: int
    age: int = 0
    is_reachable: bool = True


class GenerationalHeapSimulator:
    def __init__(self, young_capacity_kb: int = 1024, old_capacity_kb: int = 4096):
        self.young_capacity_kb = young_capacity_kb
        self.old_capacity_kb = old_capacity_kb
        self.nursery: List[HeapObject] = []
        self.old_gen: List[HeapObject] = []
        self.scavenge_count = 0
        self.mark_sweep_count = 0
        self.next_id = 1

    @property
    def young_used_kb(self) -> int:
        return sum(o.size_kb for o in self.nursery)

    @property
    def old_used_kb(self) -> int:
        return sum(o.size_kb for o in self.old_gen)

    def allocate(self, size_kb: int, is_reachable: bool = True) -> HeapObject:
        if self.young_used_kb + size_kb > self.young_capacity_kb:
            self.run_minor_gc_scavenge()

        obj = HeapObject(obj_id=self.next_id, size_kb=size_kb, is_reachable=is_reachable)
        self.next_id += 1
        self.nursery.append(obj)
        return obj

    def run_minor_gc_scavenge(self) -> None:
        """Minor GC: Cheney's copying scavenge algorithm for Young Generation."""
        self.scavenge_count += 1
        survivors: List[HeapObject] = []
        promoted: List[HeapObject] = []

        for obj in self.nursery:
            if obj.is_reachable:
                obj.age += 1
                if obj.age >= 2:  # Tenure threshold
                    promoted.append(obj)
                else:
                    survivors.append(obj)

        self.nursery = survivors
        self.old_gen.extend(promoted)

        # Trigger Major GC if Old Gen exceeds 80% threshold
        if self.old_used_kb > (self.old_capacity_kb * 0.8):
            self.run_major_gc_mark_sweep()

    def run_major_gc_mark_sweep(self) -> None:
        """Major GC: Mark-Sweep-Compact for Old Generation."""
        self.mark_sweep_count += 1
        # Reclaim unreachable old generation objects
        self.old_gen = [o for o in self.old_gen if o.is_reachable]


def run_gc_telemetry_demo() -> None:
    header("Simulation 2: V8 Generational Garbage Collection & Allocation Pressure")
    heap = GenerationalHeapSimulator(young_capacity_kb=512, old_capacity_kb=2048)

    print(f"{CLR_BLUE}Simulating dynamic web app workload (Request cycles, short-lived closures, memory retention)...{CLR_RESET}")

    # Generate 1500 short-lived objects (request buffers, temporary JSON strings)
    for cycle in range(25):
        # 90% ephemeral, 10% retained (e.g., caches, event listeners)
        for _ in range(40):
            is_leaked = random.random() < 0.12
            heap.allocate(size_kb=random.randint(10, 35), is_reachable=is_leaked)

    print(f"  Young Gen Used  : {CLR_CYAN}{heap.young_used_kb} KB{CLR_RESET} / {heap.young_capacity_kb} KB")
    print(f"  Old Gen Used    : {CLR_MAGENTA}{heap.old_used_kb} KB{CLR_RESET} / {heap.old_capacity_kb} KB")
    print(f"  Minor GC Count  : {CLR_GREEN}{heap.scavenge_count} Scavenger cycles{CLR_RESET}")
    print(f"  Major GC Count  : {CLR_YELLOW}{heap.mark_sweep_count} Mark-Sweep cycles{CLR_RESET}")

    old_pct = (heap.old_used_kb / heap.old_capacity_kb) * 100
    bar_width = 30
    filled = int((old_pct / 100) * bar_width)
    bar = f"{'█' * filled}{'░' * (bar_width - filled)}"
    print(f"  Old Gen Fill    : [{CLR_RED if old_pct > 75 else CLR_GREEN}{bar}{CLR_RESET}] {old_pct:.1f}%")

    if old_pct > 60:
        print(f"  Telemetry Alert : {CLR_RED}High Retained Heap Footprint! Investigate possible closure leak.{CLR_RESET}")
    else:
        print(f"  Telemetry Alert : {CLR_GREEN}Healthy generational churn with low tenured object count.{CLR_RESET}")


# ==============================================================================
# 3. EVENT LOOP LAG & LONG TASK BUDGET PROFILER
# ==============================================================================

@dataclass
class EventLoopTask:
    task_id: str
    task_type: str  # "macrotask", "microtask", "timer"
    duration_ms: float
    name: str


class EventLoopProfiler:
    def __init__(self, long_task_threshold_ms: float = 50.0):
        self.threshold = long_task_threshold_ms
        self.microtask_queue: List[EventLoopTask] = []
        self.macrotask_queue: List[EventLoopTask] = []
        self.telemetry_spans: List[Dict[str, object]] = []

    def enqueue(self, task: EventLoopTask) -> None:
        if task.task_type == "microtask":
            self.microtask_queue.append(task)
        else:
            self.macrotask_queue.append(task)

    def run_tick(self) -> Tuple[float, int, int]:
        total_time_ms = 0.0
        microtasks_run = 0
        macrotasks_run = 0

        # Execute 1 Macrotask if available
        if self.macrotask_queue:
            mt = self.macrotask_queue.pop(0)
            macrotasks_run += 1
            total_time_ms += mt.duration_ms
            is_long = mt.duration_ms > self.threshold
            self.telemetry_spans.append({
                "name": mt.name,
                "type": mt.task_type,
                "duration_ms": mt.duration_ms,
                "long_task": is_long
            })

        # Drain Microtask queue completely (microtask checkpoint)
        drain_start = total_time_ms
        while self.microtask_queue:
            ut = self.microtask_queue.pop(0)
            microtasks_run += 1
            total_time_ms += ut.duration_ms

        micro_time = total_time_ms - drain_start
        if micro_time > self.threshold:
            self.telemetry_spans.append({
                "name": "MicrotaskCheckpointStarvation",
                "type": "microtask_exhaustion",
                "duration_ms": micro_time,
                "long_task": True
            })

        return total_time_ms, macrotasks_run, microtasks_run


def run_event_loop_profiling_demo() -> None:
    header("Simulation 3: Event Loop Lag & W3C Long Task Profiling (50ms Budget)")
    profiler = EventLoopProfiler(long_task_threshold_ms=50.0)

    # Enqueue tasks representing DOM updates, network handlers, and CPU-intensive operations
    tasks = [
        EventLoopTask("T1", "macrotask", 12.5, "HTTP_Response_Parse"),
        EventLoopTask("T2", "microtask", 2.1, "Promise_Resolve_Auth"),
        EventLoopTask("T3", "microtask", 3.0, "Promise_State_Sync"),
        EventLoopTask("T4", "macrotask", 84.6, "Expensive_Synchronous_CryptoHash"),  # Long task!
        EventLoopTask("T5", "macrotask", 8.2, "RequestAnimationFrame_Render"),
    ]

    for t in tasks:
        profiler.enqueue(t)

    # Also simulate microtask starvation loop
    for i in range(18):
        profiler.enqueue(EventLoopTask(f"UT_Starve_{i}", "microtask", 3.5, f"Promise_Chain_Step_{i}"))

    print(f"{CLR_BLUE}Executing event loop ticks and recording performance trace spans...{CLR_RESET}\n")

    tick_num = 1
    while profiler.macrotask_queue or profiler.microtask_queue:
        elapsed, macs, micros = profiler.run_tick()
        status = status_badge("IN-BUDGET", True) if elapsed <= 50.0 else status_badge("LONG-TASK-LAG", False)
        print(f"  [Tick #{tick_num:02d}] Elapsed: {CLR_BOLD}{elapsed:6.2f}ms{CLR_RESET} (Macrotasks: {macs}, Microtasks: {micros:2d}) {status}")
        tick_num += 1

    print(f"\n{CLR_YELLOW}Telemetry Tracing Spans Captured:{CLR_RESET}")
    for span in profiler.telemetry_spans:
        flag = f"{CLR_RED}⚡ LONG TASK (>50ms){CLR_RESET}" if span["long_task"] else f"{CLR_GREEN}OK{CLR_RESET}"
        print(f"  • {span['name']:<35} ({span['duration_ms']:5.1f} ms) [{span['type']}] -> {flag}")


# ==============================================================================
# 4. SAMPLING PROFILER & ASCII FLAMEGRAPH VISUALIZER
# ==============================================================================

@dataclass
class StackSample:
    call_stack: List[str]
    weight: int = 1


def generate_flamegraph_demo() -> None:
    header("Simulation 4: CPU Call-Stack Sampling Profiler & ASCII Flamegraph")

    # Simulated sampling traces collected at 1000Hz (1ms intervals)
    raw_samples = [
        ["(root)", "node:server", "express:router", "jwt:verify", "crypto:pbkdf2Sync"],
        ["(root)", "node:server", "express:router", "jwt:verify", "crypto:pbkdf2Sync"],
        ["(root)", "node:server", "express:router", "jwt:verify", "crypto:pbkdf2Sync"],
        ["(root)", "node:server", "express:router", "jwt:verify"],
        ["(root)", "node:server", "express:router", "controller:getUser", "db:findQuery"],
        ["(root)", "node:server", "express:router", "controller:getUser", "db:findQuery"],
        ["(root)", "node:server", "express:router", "controller:getUser", "json:stringify"],
        ["(root)", "node:server", "express:router", "controller:getUser", "json:stringify"],
        ["(root)", "node:server", "v8:gc:scavenger"],
        ["(root)", "node:server", "v8:gc:scavenger"],
    ]

    total_samples = len(raw_samples)
    stack_counts: Dict[str, int] = {}
    for sample in raw_samples:
        frame_str = " > ".join(sample)
        stack_counts[frame_str] = stack_counts.get(frame_str, 0) + 1

    print(f"{CLR_WHITE}Total CPU Samples Collected: {CLR_BOLD}{total_samples} samples{CLR_RESET}")
    print(f"{CLR_DIM}Hot-spot Flame Tree Depth Projection:{CLR_RESET}\n")

    # ASCII Flamegraph Representation
    layers = [
        ("Layer 0 (Host)", "[===================== (root: 100%) =====================]", CLR_WHITE),
        ("Layer 1 (Runtime)", "[====== node:server (100%) ======]", CLR_CYAN),
        ("Layer 2 (Router)", "[ express:router (80%) ]  [ v8:gc:scavenge (20%) ]", CLR_BLUE),
        ("Layer 3 (Handler)", "[ jwt:verify (40%) ]  [ controller:getUser (40%) ]", CLR_YELLOW),
        ("Layer 4 (Bottleneck)", f"{CLR_RED}[ crypto:pbkdf2Sync (30%) ]{CLR_RESET} [ db:query (20%) ] [ json (20%) ]", CLR_RED),
    ]

    for label, visual, clr in layers:
        print(f"  {CLR_DIM}{label:<22}{CLR_RESET} {clr}{visual}{CLR_RESET}")

    print(f"\n{CLR_YELLOW}Root Cause Profiling Diagnostic:{CLR_RESET}")
    print(f"  1. {CLR_RED}crypto:pbkdf2Sync{CLR_RESET} blocks the main thread for 30% of entire sample window.")
    print(f"  2. Recommended remedy: Migrate to asynchronous Web Crypto API or `worker_threads`.")
    print(f"  3. Inline Caches and V8 Scavenger consume 20% CPU under rapid object allocation.")


# ==============================================================================
# INTERACTIVE CLI DISPATCHER
# ==============================================================================

def print_menu() -> None:
    print(f"\n{CLR_CYAN}{'='*60}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_WHITE}  V8 & JS PERFORMANCE ENGINEERING INTERACTIVE LAB{CLR_RESET}")
    print(f"{CLR_CYAN}{'='*60}{CLR_RESET}")
    print(f"  {CLR_GREEN}1.{CLR_RESET} Hidden Classes (Shapes) & Inline Cache (IC) Transition")
    print(f"  {CLR_GREEN}2.{CLR_RESET} Generational GC (Scavenger / Mark-Sweep) Simulation")
    print(f"  {CLR_GREEN}3.{CLR_RESET} Event Loop Lag & W3C Long Task Profiler (50ms)")
    print(f"  {CLR_GREEN}4.{CLR_RESET} CPU Sampling Profiler & ASCII Flamegraph")
    print(f"  {CLR_GREEN}5.{CLR_RESET} Run Complete Performance Benchmark Suite")
    print(f"  {CLR_RED}0.{CLR_RESET} Exit")
    print(f"{CLR_CYAN}{'-'*60}{CLR_RESET}")


def run_all() -> None:
    run_v8_shape_and_ic_demo()
    run_gc_telemetry_demo()
    run_event_loop_profiling_demo()
    generate_flamegraph_demo()
    header("Lab Complete: All Performance Subsystems Profiled Successfully")


def main() -> None:
    # If piped, run non-interactively or if argument passed
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "all"):
        run_all()
        return

    if not sys.stdin.isatty():
        # Running in headless / automated container test mode
        run_all()
        return

    while True:
        print_menu()
        try:
            choice = input(f"{CLR_BOLD}Select an option [0-5]: {CLR_RESET}").strip()
            if choice == "1":
                run_v8_shape_and_ic_demo()
            elif choice == "2":
                run_gc_telemetry_demo()
            elif choice == "3":
                run_event_loop_profiling_demo()
            elif choice == "4":
                generate_flamegraph_demo()
            elif choice == "5":
                run_all()
            elif choice in ("0", "q", "exit"):
                print(f"\n{CLR_CYAN}Exiting Performance Engineering Lab. Goodbye!{CLR_RESET}\n")
                break
            else:
                print(f"{CLR_RED}Invalid option! Please enter a number between 0 and 5.{CLR_RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{CLR_CYAN}Terminating gracefully.{CLR_RESET}")
            break


if __name__ == "__main__":
    main()
