#!/usr/bin/env python3
"""
Lab Exercise: C++ Enterprise Architecture & Capstone Systems Simulation
BAB 10: Enterprise Architecture Capstone (C++ System Architecture)

Simulasi teknis prinsip-prinsip Enterprise C++:
1. Micro-kernel / Dynamic Plugin Architecture with Interface Contracts
2. Low-Latency Lock-Free SPSC Ring Buffer & Event Dispatcher
3. Arena / Bump Allocator Simulation with Memory Alignment & Budget Guards
4. RAII-style Scoped Telemetry & Distributed Tracing Spans
"""

import sys
import time
import math
import random
from typing import Dict, List, Optional, Any, Callable


class ANSI:
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
    BG_DARK = "\033[40m"


# ==============================================================================
# 1. CORE SUBSYSTEM: Arena / Bump Memory Allocator Simulation (C++ std::pmr)
# ==============================================================================

class MemoryArena:
    """Simulasi memory pool arena berbasis kontigu dengan byte alignment."""
    def __init__(self, capacity_bytes: int = 1024 * 64):
        self.capacity = capacity_bytes
        self.offset = 0
        self.allocations_count = 0
        self.high_water_mark = 0

    def allocate(self, size_bytes: int, alignment: int = 8) -> int:
        aligned_offset = (self.offset + (alignment - 1)) & ~(alignment - 1)
        if aligned_offset + size_bytes > self.capacity:
            raise MemoryError(f"Arena Out Of Memory! Request: {size_bytes}B, Sisa: {self.capacity - self.offset}B")
        
        assigned_ptr = aligned_offset
        self.offset = aligned_offset + size_bytes
        self.allocations_count += 1
        if self.offset > self.high_water_mark:
            self.high_water_mark = self.offset
        return assigned_ptr

    def reset(self):
        """O(1) destruction tanpa dealloc individual (Zero-overhead arena reset)."""
        self.offset = 0
        self.allocations_count = 0

    def stats(self) -> Dict[str, Any]:
        return {
            "capacity_kb": self.capacity / 1024,
            "used_bytes": self.offset,
            "peak_bytes": self.high_water_mark,
            "allocations": self.allocations_count,
            "utilization_pct": (self.offset / self.capacity) * 100
        }


# ==============================================================================
# 2. CORE SUBSYSTEM: Lock-Free SPSC Ring Buffer (C++ Cache-line Padded Queue)
# ==============================================================================

class RingBuffer:
    """Ring buffer 64-slot simulasi komunikasi inter-thread zero-allocation."""
    def __init__(self, capacity: int = 16):
        self.capacity = capacity
        self.buffer = [None] * capacity
        self.head = 0
        self.tail = 0
        self.count = 0

    def push(self, item: Any) -> bool:
        if self.count >= self.capacity:
            return False  # Buffer saturated
        self.buffer[self.tail] = item
        self.tail = (self.tail + 1) % self.capacity
        self.count += 1
        return True

    def pop(self) -> Optional[Any]:
        if self.count == 0:
            return None
        item = self.buffer[self.head]
        self.buffer[self.head] = None
        self.head = (self.head + 1) % self.capacity
        self.count -= 1
        return item


# ==============================================================================
# 3. CORE SUBSYSTEM: RAII-style Telemetry Tracer (C++ std::chrono & spans)
# ==============================================================================

class TraceSpan:
    def __init__(self, name: str, tracer: "Tracer"):
        self.name = name
        self.tracer = tracer
        self.start_ns = 0

    def __enter__(self):
        self.start_ns = time.perf_counter_ns()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_us = (time.perf_counter_ns() - self.start_ns) / 1000.0
        self.tracer.record_metric(self.name, duration_us)


class Tracer:
    def __init__(self):
        self.records: List[Dict[str, Any]] = []

    def span(self, name: str) -> TraceSpan:
        return TraceSpan(name, self)

    def record_metric(self, name: str, duration_us: float):
        self.records.append({
            "span": name,
            "duration_us": duration_us,
            "timestamp": time.time()
        })


# ==============================================================================
# 4. CAPSTONE MODULES: Microkernel Plugin Architecture
# ==============================================================================

class IPlugin:
    """Interface vtable C++ simulation."""
    def plugin_name(self) -> str:
        raise NotImplementedError

    def execute(self, arena: MemoryArena, queue: RingBuffer, tracer: Tracer) -> str:
        raise NotImplementedError


class OrderMatchingEnginePlugin(IPlugin):
    def plugin_name(self) -> str:
        return "LMAX-Style Ultra-Fast Order Matcher"

    def execute(self, arena: MemoryArena, queue: RingBuffer, tracer: Tracer) -> str:
        with tracer.span("OrderMatchingEngine::MatchBatch"):
            ptr = arena.allocate(size_bytes=128, alignment=16)
            orders = [
                {"id": 1001, "symbol": "BTC/USDT", "side": "BUY", "qty": 1.45, "price": 68420.0},
                {"id": 1002, "symbol": "BTC/USDT", "side": "SELL", "qty": 1.45, "price": 68418.5}
            ]
            for o in orders:
                queue.push(o)
            time.sleep(0.003)  # Simulasi compute tick
        return f"Matched 2 orders successfully at virtual ptr 0x{ptr:08X}."


class RiskManagementPlugin(IPlugin):
    def plugin_name(self) -> str:
        return "Real-Time VaR & Pre-Trade Risk Engine"

    def execute(self, arena: MemoryArena, queue: RingBuffer, tracer: Tracer) -> str:
        with tracer.span("RiskEngine::EvaluateMargin"):
            ptr = arena.allocate(size_bytes=64, alignment=8)
            time.sleep(0.002)
        return f"Pre-trade margin validated. Risk exposure 0.04% at virtual ptr 0x{ptr:08X}."


class MarketDataStreamerPlugin(IPlugin):
    def plugin_name(self) -> str:
        return "Sub-Microsecond FIX/FAST Market Data Streamer"

    def execute(self, arena: MemoryArena, queue: RingBuffer, tracer: Tracer) -> str:
        with tracer.span("MarketData::PublishMulticast"):
            ptr = arena.allocate(size_bytes=256, alignment=32)
            for _ in range(4):
                queue.push({"quote": "AAPL", "bid": 230.15, "ask": 230.18})
            time.sleep(0.001)
        return f"Multicast packet 4 quotes dispatched at virtual ptr 0x{ptr:08X}."


# ==============================================================================
# 5. ENTERPRISE KERNEL & INTERACTIVE CLI
# ==============================================================================

class EnterpriseEngineKernel:
    def __init__(self):
        self.arena = MemoryArena(capacity_bytes=1024 * 32)
        self.queue = RingBuffer(capacity=32)
        self.tracer = Tracer()
        self.plugins: Dict[str, IPlugin] = {
            "1": OrderMatchingEnginePlugin(),
            "2": RiskManagementPlugin(),
            "3": MarketDataStreamerPlugin()
        }

    def print_banner(self):
        print(f"{ANSI.CYAN}{ANSI.BOLD}")
        print("=" * 76)
        print("   ENTERPRISE C++ CAPSTONE ARCHITECTURE SIMULATOR (BAB 10)")
        print("   Clean Architecture, Memory Arenas, RingBuffer & Plugin Pipeline")
        print("=" * 76 + f"{ANSI.RESET}")

    def render_system_status(self):
        stats = self.arena.stats()
        bar_len = 24
        filled = int((stats["utilization_pct"] / 100) * bar_len)
        bar = f"{ANSI.GREEN}{'#' * filled}{ANSI.DIM}{'.' * (bar_len - filled)}{ANSI.RESET}"
        
        print(f"\n{ANSI.BOLD}[ SYSTEM HARDWARE & MEMORY BUS STATUS ]{ANSI.RESET}")
        print(f" * Arena Allocator  : [{bar}] {stats['utilization_pct']:.2f}% ({stats['used_bytes']}/{int(stats['capacity_kb']*1024)} bytes)")
        print(f" * SPSC Ring Buffer : {self.queue.count}/{self.queue.capacity} pending events")
        print(f" * High Water Mark  : {stats['peak_bytes']} bytes | Total Allocations: {stats['allocations']}")
        print(f" * Telemetry Spans  : {len(self.tracer.records)} traces recorded\n")

    def run_plugin(self, choice: str):
        plugin = self.plugins.get(choice)
        if not plugin:
            print(f"{ANSI.RED}[!] Plugin key {choice} tidak terdaftar!{ANSI.RESET}")
            return
        
        print(f"{ANSI.YELLOW}--> Executing Plugin: {ANSI.BOLD}{plugin.plugin_name()}{ANSI.RESET}...")
        try:
            msg = plugin.execute(self.arena, self.queue, self.tracer)
            print(f"    {ANSI.GREEN}[OK] Result: {msg}{ANSI.RESET}")
        except MemoryError as e:
            print(f"    {ANSI.RED}[MEMORY OVERFLOW] {e}{ANSI.RESET}")

    def drain_queue(self):
        print(f"{ANSI.MAGENTA}--> Draining SPSC Ring Buffer Queue...{ANSI.RESET}")
        drained = 0
        while True:
            item = self.queue.pop()
            if item is None:
                break
            drained += 1
            print(f"    {ANSI.CYAN}[EVENT #{drained}]{ANSI.RESET} Consumed: {item}")
        if drained == 0:
            print(f"    {ANSI.DIM}Queue kosong.{ANSI.RESET}")
        else:
            print(f"    {ANSI.GREEN}[OK] Successfully dispatched {drained} events without GC.{ANSI.RESET}")

    def show_telemetry_report(self):
        print(f"\n{ANSI.WHITE}{ANSI.BG_BLUE}{ANSI.BOLD} === DISTRIBUTED TRACING & PROFILING AUDIT === {ANSI.RESET}")
        if not self.tracer.records:
            print(f"{ANSI.DIM}Belum ada span trace yang terekam.{ANSI.RESET}")
            return
        
        for r in self.tracer.records[-10:]:
            span_color = ANSI.GREEN if r["duration_us"] < 2500 else ANSI.YELLOW
            print(f" {ANSI.BOLD}{r['span']:<36}{ANSI.RESET} | Latency: {span_color}{r['duration_us']:>8.2f} us{ANSI.RESET}")
        print("-" * 60)

    def run_benchmark(self):
        print(f"\n{ANSI.BOLD}{ANSI.CYAN}--> Running Micro-benchmark: 10,000 Arena Allocations & RingBuffer Pushes...{ANSI.RESET}")
        t0 = time.perf_counter_ns()
        bench_arena = MemoryArena(capacity_bytes=1024 * 1024)
        bench_queue = RingBuffer(capacity=1024)
        
        for i in range(10000):
            bench_arena.allocate(32, alignment=8)
            if i % 1000 == 0:
                bench_arena.reset()  # Fast arena recycling
            bench_queue.push(i)
            bench_queue.pop()
        
        t1 = time.perf_counter_ns()
        total_time_ms = (t1 - t0) / 1_000_000.0
        ops_per_sec = (10000 / (total_time_ms / 1000.0))
        print(f"    {ANSI.GREEN}[PASS] Time: {total_time_ms:.2f} ms | Throughput: {ops_per_sec:,.0f} ops/sec{ANSI.RESET}\n")

    def interactive_menu(self):
        while True:
            self.render_system_status()
            print(f"{ANSI.BOLD}PILIHAN OPERASI ENTERPRISE CAPSTONE:{ANSI.RESET}")
            print("  1. Jalankan Order Matching Engine (Dynamic Plugin #1)")
            print("  2. Jalankan Pre-Trade Risk Manager (Dynamic Plugin #2)")
            print("  3. Jalankan Market Data Streamer   (Dynamic Plugin #3)")
            print("  4. Drain & Dispatch SPSC Ring Buffer Queue")
            print("  5. Reset Memory Arena (Zero-Cost O(1) Buffer Reclaim)")
            print("  6. Tampilkan Laporan Telemetri & Latency Profiling")
            print("  7. Jalankan High-Throughput Stress Benchmark")
            print("  8. Jalankan Full Automated Architecture Tour")
            print("  0. Keluar")
            
            try:
                choice = input(f"\n{ANSI.BOLD}{ANSI.CYAN}Pilih opsi [0-8]: {ANSI.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{ANSI.YELLOW}Exiting engine safely.{ANSI.RESET}")
                break

            if choice == "0":
                print(f"{ANSI.GREEN}Enterprise Kernel shutdown safely.{ANSI.RESET}")
                break
            elif choice in ("1", "2", "3"):
                self.run_plugin(choice)
            elif choice == "4":
                self.drain_queue()
            elif choice == "5":
                self.arena.reset()
                print(f"{ANSI.GREEN}[OK] Memory Arena pointers reset to 0 without memory leaks.{ANSI.RESET}")
            elif choice == "6":
                self.show_telemetry_report()
            elif choice == "7":
                self.run_benchmark()
            elif choice == "8":
                self.run_automated_tour()
            else:
                print(f"{ANSI.RED}Pilihan tidak valid.{ANSI.RESET}")
            
            time.sleep(0.3)

    def run_automated_tour(self):
        print(f"\n{ANSI.BOLD}{ANSI.MAGENTA}=== Memulai Automated Architecture Tour ==={ANSI.RESET}")
        for p in ["1", "2", "3"]:
            self.run_plugin(p)
            time.sleep(0.1)
        self.drain_queue()
        self.run_benchmark()
        self.show_telemetry_report()
        print(f"{ANSI.GREEN}=== Architecture Tour Selesai ==={ANSI.RESET}\n")


def main():
    kernel = EnterpriseEngineKernel()
    kernel.print_banner()
    
    # Auto tour jika dijalankan non-interaktif
    if not sys.stdin.isatty() or "--non-interactive" in sys.argv:
        print(f"{ANSI.YELLOW}[INFO] Running in headless/non-interactive mode.{ANSI.RESET}")
        kernel.run_automated_tour()
    else:
        kernel.interactive_menu()


if __name__ == "__main__":
    main()
