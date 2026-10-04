#!/usr/bin/env python3
"""
Lab Exercise: Ruby MRI Performance Tuning & Production Engineering Deep Dive
Topic: Generational Garbage Collection (RGenGC) & GVL Concurrency Simulation

This script simulates low-level MRI Ruby runtime behavior:
1. RGenGC (Generational Mark & Sweep with Slot-based Allocation and Compaction).
2. Global VM Lock (GVL) contention behavior under CPU-bound vs IO-bound workloads.
3. Production telemetry: GC pause latency, heap fragmentation, and throughput.
"""

import time
import threading
import random
from dataclasses import dataclass
from typing import List, Optional

# --- ANSI Formatting Constants ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[1;31m"
CLR_GREEN  = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_CYAN   = "\033[1;36m"
CLR_WHITE  = "\033[1;37m"

@dataclass
class RubyRValue:
    """Represents an MRI 40-byte RVALUE slot in a heap page."""
    obj_id: int
    payload_type: str
    age: int = 0
    is_old: bool = False
    is_marked: bool = False
    live: bool = True

class RubyHeapManager:
    """
    Simulates MRI Ruby 2.1+ Generational Garbage Collector (RGenGC) with
    slot allocation, Minor GC (young generation), Major GC (mark & sweep),
    and compaction mechanics.
    """
    SLOT_SIZE = 40  # Bytes per RVALUE slot
    
    def __init__(self, page_slots: int = 408):
        self.page_slots = page_slots
        self.slots: List[Optional[RubyRValue]] = [None] * page_slots
        self.minor_gc_count = 0
        self.major_gc_count = 0
        self.pause_time_ms = 0.0
        self.allocation_counter = 0

    def allocate(self, payload_type: str, keep_alive: bool = False) -> int:
        """Simulates `rb_newobj_of()`: allocates an RVALUE in the young generation."""
        # Find free slot
        for idx in range(self.page_slots):
            if self.slots[idx] is None:
                self.allocation_counter += 1
                self.slots[idx] = RubyRValue(
                    obj_id=self.allocation_counter,
                    payload_type=payload_type,
                    live=keep_alive
                )
                return idx

        # If page full, trigger Minor GC
        self.run_minor_gc()
        
        # Retry allocation
        for idx in range(self.page_slots):
            if self.slots[idx] is None:
                self.allocation_counter += 1
                self.slots[idx] = RubyRValue(
                    obj_id=self.allocation_counter,
                    payload_type=payload_type,
                    live=keep_alive
                )
                return idx

        # If still full, trigger Major GC (full mark & sweep)
        self.run_major_gc()
        for idx in range(self.page_slots):
            if self.slots[idx] is None:
                self.allocation_counter += 1
                self.slots[idx] = RubyRValue(
                    obj_id=self.allocation_counter,
                    payload_type=payload_type,
                    live=keep_alive
                )
                return idx
        
        raise MemoryError("Ruby Heap Page Exhausted: No available slots.")

    def run_minor_gc(self):
        """Simulates Minor GC: inspects only young generation objects."""
        start_t = time.perf_counter()
        reclaimed = 0

        for idx, obj in enumerate(self.slots):
            if obj is not None and not obj.is_old:
                if not obj.live:
                    self.slots[idx] = None
                    reclaimed += 1
                else:
                    obj.age += 1
                    # Promotion threshold (oldgen promotion)
                    if obj.age >= 3:
                        obj.is_old = True

        duration = (time.perf_counter() - start_t) * 1000.0
        self.pause_time_ms += duration
        self.minor_gc_count += 1

    def run_major_gc(self):
        """Simulates Full GC (Major GC): marks roots and sweeps young + old gens."""
        start_t = time.perf_counter()
        reclaimed = 0

        # Sweep phase across all slots
        for idx, obj in enumerate(self.slots):
            if obj is not None:
                if not obj.live:
                    self.slots[idx] = None
                    reclaimed += 1
                else:
                    obj.is_marked = False

        duration = (time.perf_counter() - start_t) * 1000.0
        self.pause_time_ms += duration
        self.major_gc_count += 1

    def compact_heap(self) -> float:
        """Simulates Ruby GC.compact (Two-finger compaction algorithm)."""
        start_t = time.perf_counter()
        left = 0
        right = self.page_slots - 1

        while left < right:
            while left < right and self.slots[left] is not None:
                left += 1
            while left < right and self.slots[right] is None:
                right -= 1
            if left < right:
                self.slots[left] = self.slots[right]
                self.slots[right] = None
                left += 1
                right -= 1

        duration = (time.perf_counter() - start_t) * 1000.0
        self.pause_time_ms += duration
        return duration

    def fragmentation_ratio(self) -> float:
        """Calculates heap fragmentation based on scattered empty slots."""
        occupied = [i for i, slot in enumerate(self.slots) if slot is not None]
        if not occupied:
            return 0.0
        span = occupied[-1] - occupied[0] + 1
        return 1.0 - (len(occupied) / span)

class GVLContentionSimulator:
    """
    Simulates Ruby MRI's Global VM Lock (GVL) mechanism under concurrent loads.
    IO-bound operations release GVL via `rb_thread_call_without_gvl()`.
    CPU-bound operations hold GVL continuously.
    """
    def __init__(self):
        self.gvl_lock = threading.Lock()

    def cpu_bound_worker(self, iterations: int):
        """Holds GVL for the entire duration of computation."""
        with self.gvl_lock:
            acc = 0
            for i in range(iterations):
                acc += (i ^ 0x5A)

    def io_bound_worker(self, io_duration_s: float):
        """Releases GVL during IO wait simulation, reacquires for processing."""
        # Simulated pre-processing holding GVL
        with self.gvl_lock:
            _ = sum(range(100))

        # IO wait: Released GVL (rb_thread_call_without_gvl)
        time.sleep(io_duration_s)

        # Post-processing re-acquiring GVL
        with self.gvl_lock:
            _ = sum(range(100))

def main():
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_WHITE}  RUBY PRODUCTION ENGINEERING LAB: GC & GVL BENCHMARK HARNESS        {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}\n")

    # ---------------------------------------------------------
    # PART 1: Generational Garbage Collector (RGenGC) Simulation
    # ---------------------------------------------------------
    print(f"{CLR_YELLOW}[1/2] Simulating Ruby RGenGC Allocation & Compaction...{CLR_RESET}")
    heap = RubyHeapManager(page_slots=600)

    # Phase A: High churn short-lived object allocations (typical web request lifecycle)
    print(f"  -> Allocating transient objects (Rack env, params, short strings)...")
    for _ in range(1200):
        # 85% transient (dies after scope), 15% long-lived (memoized config/routes)
        is_sticky = random.random() < 0.15
        heap.allocate(payload_type="T_STRING", keep_alive=is_sticky)

    pre_compact_frag = heap.fragmentation_ratio()
    active_slots = sum(1 for s in heap.slots if s is not None)
    old_gen_slots = sum(1 for s in heap.slots if s is not None and s.is_old)

    print(f"  -> {CLR_GREEN}Allocation Cycle Complete.{CLR_RESET}")
    print(f"     Minor GC Runs : {heap.minor_gc_count}")
    print(f"     Major GC Runs : {heap.major_gc_count}")
    print(f"     Live Slots    : {active_slots} / {heap.page_slots} (OldGen: {old_gen_slots})")
    print(f"     Fragmentation : {pre_compact_frag * 100:.2f}%\n")

    # Phase B: Compaction (GC.compact)
    print(f"  -> Executing Ruby 3.x GC.compact...")
    compact_duration = heap.compact_heap()
    post_compact_frag = heap.fragmentation_ratio()
    print(f"     Compaction Time     : {compact_duration:.4f} ms")
    print(f"     Post-Compact Frag   : {post_compact_frag * 100:.2f}% (Reduced by {(pre_compact_frag - post_compact_frag) * 100:.2f}%)")
    print(f"     Accumulated GC Pause: {heap.pause_time_ms:.4f} ms\n")

    # ---------------------------------------------------------
    # PART 2: Global VM Lock (GVL) Contention Profiling
    # ---------------------------------------------------------
    print(f"{CLR_YELLOW}[2/2] Profiling MRI Global VM Lock (GVL) Threading Behavior...{CLR_RESET}")
    sim = GVLContentionSimulator()
    thread_count = 6

    # Test CPU-bound under GVL
    print(f"  -> Benchmarking {thread_count} concurrent CPU-bound workers (GVL lock contention)...")
    t0 = time.perf_counter()
    threads = [threading.Thread(target=sim.cpu_bound_worker, args=(600000,)) for _ in range(thread_count)]
    for t in threads: t.start()
    for t in threads: t.join()
    cpu_wall_time = (time.perf_counter() - t0) * 1000.0
    print(f"     Total Wall Time: {CLR_RED}{cpu_wall_time:.2f} ms{CLR_RESET} (Serialized via GVL)")

    # Test IO-bound under GVL
    print(f"  -> Benchmarking {thread_count} concurrent IO-bound workers (GVL released via nogvl)...")
    t0 = time.perf_counter()
    threads = [threading.Thread(target=sim.io_bound_worker, args=(0.04,)) for _ in range(thread_count)]
    for t in threads: t.start()
    for t in threads: t.join()
    io_wall_time = (time.perf_counter() - t0) * 1000.0
    print(f"     Total Wall Time: {CLR_GREEN}{io_wall_time:.2f} ms{CLR_RESET} (Concurrent IO wait)")

    # Production Summary
    print(f"\n{CLR_BOLD}{CLR_CYAN}================ PRODUCTION RUNTIME DIAGNOSTICS ====================={CLR_RESET}")
    print(f" Memory Efficiency Score  : {((1.0 - post_compact_frag) * 100):.1f}/100")
    print(f" GVL Parallelism Factor   : {(cpu_wall_time / io_wall_time):.2f}x (IO vs CPU scaling)")
    print(f" Recommended Worker Model : Multi-Process (Puma clustered / Unicorn pre-fork)")
    print(f" Optimal GC Tuning Flags  : RUBY_GC_HEAP_GROWTH_FACTOR=1.4")
    print(f"                            RUBY_GC_HEAP_FREE_SLOTS_MIN_RATIO=0.20")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")

if __name__ == "__main__":
    main()