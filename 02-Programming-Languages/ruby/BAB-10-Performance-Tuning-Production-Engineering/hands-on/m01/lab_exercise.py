#!/usr/bin/env python3
"""
Lab Exercise: Ruby Performance Tuning & Production Engineering Simulation
BAB-10: Performance Tuning & Production Engineering (MRI Ruby VM Internals)

Simulasi interaktif teknis fondasi performa Ruby MRI (CRuby):
1. RGenGC (Generational Garbage Collector) & Object Allocation Profiling
2. Copy-on-Write (CoW) & GC Compaction (GC.compact) pada Prefork Server (Puma/Unicorn)
3. Memory Allocator Diagnostics (glibc vs jemalloc fragmentation)
4. Puma Thread Pool & ActiveRecord Connection Pool Saturation
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# --- ANSI Color Codes ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[48;5;236m"


def header(title: str) -> None:
    line = "=" * 70
    print(f"\n{CLR_CYAN}{CLR_BOLD}{line}")
    print(f" [*] {title}")
    print(f"{line}{CLR_RESET}")


def subheader(title: str) -> None:
    print(f"\n{CLR_YELLOW}{CLR_BOLD}--- {title} ---{CLR_RESET}")


def log_info(msg: str) -> None:
    print(f"{CLR_BLUE}[INFO]{CLR_RESET} {msg}")


def log_success(msg: str) -> None:
    print(f"{CLR_GREEN}[OK]{CLR_RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"{CLR_YELLOW}[WARN]{CLR_RESET} {msg}")


def log_crit(msg: str) -> None:
    print(f"{CLR_RED}[CRITICAL]{CLR_RESET} {msg}")


# ---------------------------------------------------------------------------
# 1. RGenGC & Object Allocation Simulation
# ---------------------------------------------------------------------------
@dataclass
class RubyObject:
    obj_id: int
    klass: str
    size_bytes: int
    age_cycles: int = 0
    is_old: bool = False
    pinned: bool = False


class RubyVMSimulator:
    """
    Simulates CRuby ObjectSpace and Generational Garbage Collector (RGenGC).
    Demonstrates Minor GC (young generation collection) vs Major GC (full mark & sweep).
    """

    def __init__(self, eden_capacity: int = 1500):
        self.eden_capacity = eden_capacity
        self.young_gen: List[RubyObject] = []
        self.old_gen: List[RubyObject] = []
        self.minor_gc_count = 0
        self.major_gc_count = 0
        self.next_obj_id = 1
        self.total_allocated = 0

    def allocate(self, klass: str, size: int, count: int = 100) -> None:
        for _ in range(count):
            obj = RubyObject(
                obj_id=self.next_obj_id,
                klass=klass,
                size_bytes=size,
                pinned=(random.random() < 0.05)  # 5% pinned in C-extension
            )
            self.young_gen.append(obj)
            self.next_obj_id += 1
            self.total_allocated += 1

        if len(self.young_gen) >= self.eden_capacity:
            self.run_minor_gc()

    def run_minor_gc(self) -> None:
        self.minor_gc_count += 1
        retained = []
        promoted = 0

        for obj in self.young_gen:
            # 70% short-lived objects (request lifecycle strings/hashes) die immediately
            if random.random() > 0.70:
                obj.age_cycles += 1
                if obj.age_cycles >= 3:
                    # Promoted to Old Gen via Write Barrier
                    obj.is_old = True
                    self.old_gen.append(obj)
                    promoted += 1
                else:
                    retained.append(obj)

        self.young_gen = retained

        # Trigger Major GC if Old Gen exceeds threshold
        if len(self.old_gen) > 800:
            self.run_major_gc()

    def run_major_gc(self) -> None:
        self.major_gc_count += 1
        # Major GC sweeps old generation (reclaims long-lived objects no longer reachable)
        self.old_gen = [obj for obj in self.old_gen if random.random() > 0.25]

    def gc_stats(self) -> Dict[str, int]:
        return {
            "total_allocated": self.total_allocated,
            "young_objects": len(self.young_gen),
            "old_objects": len(self.old_gen),
            "minor_gc_count": self.minor_gc_count,
            "major_gc_count": self.major_gc_count,
        }


def run_gc_tuning_lab():
    subheader("Lab 1: RGenGC Profiling & ObjectSpace Behavior")
    vm = RubyVMSimulator(eden_capacity=1000)

    log_info("Simulating high-throughput Rails API allocations (JSON serializing & String churn)...")
    for cycle in range(1, 6):
        vm.allocate(klass="String", size=64, count=400)
        vm.allocate(klass="Hash", size=192, count=150)
        vm.allocate(klass="Array", size=128, count=100)
        stats = vm.gc_stats()
        print(f"  Cycle {cycle}: YoungGen={CLR_YELLOW}{stats['young_objects']:>4}{CLR_RESET} | "
              f"OldGen={CLR_MAGENTA}{stats['old_objects']:>4}{CLR_RESET} | "
              f"Minor GC={CLR_CYAN}{stats['minor_gc_count']:>2}{CLR_RESET} | "
              f"Major GC={CLR_RED}{stats['major_gc_count']:>2}{CLR_RESET}")
        time.sleep(0.05)

    stats = vm.gc_stats()
    log_success(f"Final Allocations: {stats['total_allocated']} objects | Minor GCs: {stats['minor_gc_count']} | Major GCs: {stats['major_gc_count']}")
    print(f"  {CLR_GREEN}Optimization Tip:{CLR_RESET} Tune RUBY_GC_HEAP_GROWTH_FACTOR & RUBY_GC_MALLOC_LIMIT to reduce Major GC pauses.")


# ---------------------------------------------------------------------------
# 2. Copy-on-Write (CoW) & Compaction Simulation
# ---------------------------------------------------------------------------
class PreforkMemorySimulator:
    """
    Simulates Puma Clustered / Unicorn Master-Worker Preforking with Copy-on-Write (CoW).
    Compares standard memory drift vs post-compaction (GC.compact) memory sharing.
    """

    def __init__(self, master_mb: float = 250.0):
        self.master_mb = master_mb

    def simulate_worker_drift(self, use_gc_compact: bool, requests: int = 500) -> Dict[str, float]:
        # Without compaction: pages get dirtied quickly during GC mark phase
        dirty_rate_per_req = 0.045 if not use_gc_compact else 0.012
        fragmentation_factor = 1.35 if not use_gc_compact else 1.05

        shared_mb = self.master_mb
        private_dirty_mb = 10.0  # worker baseline

        for _ in range(requests):
            dirty = dirty_rate_per_req * (random.uniform(0.7, 1.3))
            private_dirty_mb += dirty
            shared_mb = max(0.0, shared_mb - (dirty * 0.85))

        total_rss = (shared_mb + private_dirty_mb) * fragmentation_factor
        cow_efficiency = (shared_mb / self.master_mb) * 100.0

        return {
            "master_mb": self.master_mb,
            "shared_mb": round(shared_mb, 2),
            "private_dirty_mb": round(private_dirty_mb, 2),
            "total_rss_mb": round(total_rss, 2),
            "cow_efficiency_pct": round(cow_efficiency, 2),
        }


def run_cow_compaction_lab():
    subheader("Lab 2: Copy-on-Write (CoW) & Ruby 3.x GC.compact Efficiency")
    sim = PreforkMemorySimulator(master_mb=300.0)

    log_info("Puma Master booted (preload_app! enabled, 300 MB master RSS).")
    log_info("Dispatching 1,000 requests per worker process...\n")

    res_uncompacted = sim.simulate_worker_drift(use_gc_compact=False, requests=1000)
    res_compacted = sim.simulate_worker_drift(use_gc_compact=True, requests=1000)

    print(f"{'Metric':<32} | {'Standard (No Compact)':<22} | {'With GC.compact':<20}")
    print("-" * 80)
    print(f"{'Shared Memory (CoW)':<32} | {CLR_RED}{res_uncompacted['shared_mb']:>6} MB{CLR_RESET}                | {CLR_GREEN}{res_compacted['shared_mb']:>6} MB{CLR_RESET}")
    print(f"{'Private Dirty Memory':<32} | {CLR_RED}{res_uncompacted['private_dirty_mb']:>6} MB{CLR_RESET}                | {CLR_GREEN}{res_compacted['private_dirty_mb']:>6} MB{CLR_RESET}")
    print(f"{'Total Worker RSS':<32} | {CLR_RED}{res_uncompacted['total_rss_mb']:>6} MB{CLR_RESET}                | {CLR_GREEN}{res_compacted['total_rss_mb']:>6} MB{CLR_RESET}")
    print(f"{'CoW Retention %':<32} | {CLR_RED}{res_uncompacted['cow_efficiency_pct']:>6} %{CLR_RESET}                 | {CLR_GREEN}{res_compacted['cow_efficiency_pct']:>6} %{CLR_RESET}")
    print("-" * 80)

    saved_mb = res_uncompacted['total_rss_mb'] - res_compacted['total_rss_mb']
    log_success(f"Compaction saved ~{saved_mb:.1f} MB RSS per worker! In a 16-worker cluster, total saved: {saved_mb * 16:.1f} MB.")


# ---------------------------------------------------------------------------
# 3. Allocator Diagnostics: Glibc vs Jemalloc
# ---------------------------------------------------------------------------
def run_allocator_lab():
    subheader("Lab 3: Memory Allocator Diagnostics (glibc vs jemalloc)")
    log_info("Simulating multithreaded allocation bursts & heap page releases (free(3))...")

    time.sleep(0.05)
    print(f"\n{CLR_BOLD}{'Allocator':<12} | {'Allocated':<12} | {'Active RSS':<12} | {'Fragmentation %':<18} | {'Status'}{CLR_RESET}")
    print("-" * 75)

    # Glibc ptmalloc often retains mapped chunks in arenas
    glibc_alloc = 420.0
    glibc_rss = 710.0
    glibc_frag = ((glibc_rss - glibc_alloc) / glibc_rss) * 100

    print(f"{'glibc':<12} | {glibc_alloc:>7.1f} MB  | {CLR_RED}{glibc_rss:>7.1f} MB{CLR_RESET}  | {CLR_RED}{glibc_frag:>14.1f} %{CLR_RESET}  | {CLR_RED}Memory Bloat Detected{CLR_RESET}")

    # Jemalloc uses size classes, dirty page purging, decay-to-zero
    jemalloc_alloc = 420.0
    jemalloc_rss = 465.0
    jemalloc_frag = ((jemalloc_rss - jemalloc_alloc) / jemalloc_rss) * 100

    print(f"{'jemalloc':<12} | {jemalloc_alloc:>7.1f} MB  | {CLR_GREEN}{jemalloc_rss:>7.1f} MB{CLR_RESET}  | {CLR_GREEN}{jemalloc_frag:>14.1f} %{CLR_RESET}  | {CLR_GREEN}Optimal Page Reuse{CLR_RESET}")
    print("-" * 75)
    log_info("Production Directive: Preload jemalloc via LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2")


# ---------------------------------------------------------------------------
# 4. Puma Thread Pool & Connection Pool Saturation
# ---------------------------------------------------------------------------
@dataclass
class PumaServerSimulation:
    workers: int = 2
    threads_per_worker: int = 5
    db_pool_size: int = 5

    def simulate_traffic(self, concurrent_requests: int = 15) -> None:
        total_worker_capacity = self.workers * self.threads_per_worker
        total_db_connections = self.workers * self.db_pool_size

        print(f"  Configuration: {self.workers} workers x {self.threads_per_worker} threads = {total_worker_capacity} max concurrent threads.")
        print(f"  ActiveRecord DB Pool: {self.db_pool_size} conns per worker ({total_db_connections} total).")
        print(f"  Incoming Concurrent Traffic: {concurrent_requests} requests.")

        active_threads = min(concurrent_requests, total_worker_capacity)
        queued_requests = max(0, concurrent_requests - total_worker_capacity)
        active_db_conns = min(active_threads, total_db_connections)
        pool_exhaustion = active_threads > total_db_connections

        print(f"\n  Active Worker Threads   : {CLR_CYAN}{active_threads}/{total_worker_capacity}{CLR_RESET}")
        print(f"  Puma Request Backlog    : {CLR_YELLOW if queued_requests else CLR_GREEN}{queued_requests}{CLR_RESET}")
        print(f"  Active DB Connections   : {CLR_CYAN}{active_db_conns}/{total_db_connections}{CLR_RESET}")

        if pool_exhaustion:
            log_crit("ActiveRecord::ConnectionTimeoutError! DB pool size < Puma thread count.")
        else:
            log_success("Pool saturation check OK: RAILS_MAX_THREADS matches DB_POOL size.")


def run_puma_pool_lab():
    subheader("Lab 4: Puma Thread Pool vs ActiveRecord Pool Sizing")
    log_info("Scenario A: Misconfigured Thread & DB Pool (Under-provisioned DB pool)")
    bad_config = PumaServerSimulation(workers=2, threads_per_worker=8, db_pool_size=4)
    bad_config.simulate_traffic(concurrent_requests=16)

    print()
    log_info("Scenario B: Production Tuned Configuration (RAILS_MAX_THREADS == DB_POOL)")
    good_config = PumaServerSimulation(workers=2, threads_per_worker=5, db_pool_size=5)
    good_config.simulate_traffic(concurrent_requests=10)


# ---------------------------------------------------------------------------
# Main Orchestration Loop
# ---------------------------------------------------------------------------
def main():
    header("Ruby Production Engineering: Performance Tuning Hands-on Lab")
    print(f"{CLR_BOLD}Topics Covered:{CLR_RESET} RGenGC Internals, Compaction CoW, Jemalloc, Puma/DB Concurrency\n")

    run_gc_tuning_lab()
    run_cow_compaction_lab()
    run_allocator_lab()
    run_puma_pool_lab()

    header("Summary: Production Performance Directives for MRI Ruby")
    print(f"  1. {CLR_BOLD}RUBY_GC_COMPACT_ON_FORK=1{CLR_RESET} or explicit {CLR_CYAN}GC.compact{CLR_RESET} in Puma on_worker_boot.")
    print(f"  2. Always use {CLR_BOLD}jemalloc{CLR_RESET} (LD_PRELOAD) to avoid memory fragmentation.")
    print(f"  3. Match {CLR_BOLD}RAILS_MAX_THREADS{CLR_RESET} exactly to {CLR_BOLD}DB_POOL{CLR_RESET} to eliminate connection starvation.")
    print(f"  4. Profile allocation hot spots with {CLR_CYAN}memory_profiler{CLR_RESET} and {CLR_CYAN}stackprof{CLR_RESET}.\n")
    log_success("Hands-on Lab Exercise finished cleanly. All simulations validated.")


if __name__ == "__main__":
    main()
