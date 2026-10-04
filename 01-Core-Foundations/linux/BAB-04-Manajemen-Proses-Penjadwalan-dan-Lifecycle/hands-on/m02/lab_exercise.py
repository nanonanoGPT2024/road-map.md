#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive Arsitektur Penjadwalan Linux & Multithreading
Topik: 01-Core-Foundations / Bab 04 - Manajemen Proses, Penjadwalan, dan Threading

Skrip ini mendemonstrasikan:
1. Simulasi matematis Linux Completely Fair Scheduler (CFS) menggunakan red-black tree
   (dimodelkan via priority min-heap), virtual runtime (vruntime), bobot nice (-20 s/d 19),
   dan kalkulasi time-slice dinamis.
2. Benchmark konkurensi threading nyata untuk mengukur latensi context switching
   dan thread contention pada CPU core sistem saat ini.
"""

import os
import sys
import time
import heapq
import threading
from dataclasses import dataclass, field
from typing import List, Dict

# ANSI Terminal Colors
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_MAG    = "\033[35m"
CLR_CYAN   = "\033[36m"

# Linux Kernel 2.6+ sched/core.c weight array for nice levels [-20 .. 19]
# Default weight untuk nice 0 adalah 1024.
PRIO_TO_WEIGHT = [
    88761, 71755, 56483, 46273, 36291,  # -20 to -16
    29154, 23254, 18705, 14949, 11916,  # -15 to -11
     9548,  7620,  6100,  4904,  3906,  # -10 to -6
     3121,  2501,  1991,  1586,  1277,  # -5  to -1
     1024,   820,   655,   526,   423,  #  0  to  4
      335,   272,   215,   172,   137,  #  5  to  9
      110,    87,    70,    56,    45,  # 10  to 14
       36,    29,    23,    18,    15   # 15  to 19
]
NICE_0_LOAD = 1024


@dataclass(order=True)
class SchedEntity:
    """
    Representasi sched_entity pada Linux Kernel.
    Disortir otomatis berdasarkan vruntime terkecil di min-heap.
    """
    vruntime: float
    pid: int = field(compare=False)
    name: str = field(compare=False)
    nice: int = field(compare=False)
    weight: int = field(compare=False)
    remaining_burst_ms: float = field(compare=False)
    total_exec_ms: float = field(default=0.0, compare=False)
    switches_count: int = field(default=0, compare=False)


class CompletelyFairSchedulerSimulator:
    """
    Simulasi Completely Fair Scheduler (CFS) Linux Kernel.
    Menggunakan konsep virtual runtime (vruntime) dan targeting latency.
    """

    def __init__(self, sched_latency_ms: float = 48.0, min_granularity_ms: float = 6.0):
        # sysctl_sched_latency: target waktu agar semua runnable task mendapat giliran
        self.sched_latency_ms = sched_latency_ms
        # sysctl_sched_min_granularity: jatah waktu eksekusi minimum per dispatch
        self.min_granularity_ms = min_granularity_ms
        self.runqueue: List[SchedEntity] = []
        self.min_vruntime = 0.0

    @staticmethod
    def get_weight(nice: int) -> int:
        """Mengonversi nilai nice [-20 s/d 19] ke bobot kernel."""
        idx = max(-20, min(19, nice)) + 20
        return PRIO_TO_WEIGHT[idx]

    def enqueue_task(self, pid: int, name: str, nice: int, burst_ms: float):
        """Memasukkan proses ke CFS Runqueue."""
        weight = self.get_weight(nice)
        # Task baru diberi vruntime = min_vruntime runqueue agar tidak mendominasi CPU
        entity = SchedEntity(
            vruntime=self.min_vruntime,
            pid=pid,
            name=name,
            nice=nice,
            weight=weight,
            remaining_burst_ms=burst_ms
        )
        heapq.heappush(self.runqueue, entity)

    def calculate_timeslice(self, entity: SchedEntity, total_weight: int) -> float:
        """Menghitung time slice proporsional terhadap total bobot runqueue."""
        if total_weight <= 0:
            return self.min_granularity_ms
        raw_slice = (entity.weight / total_weight) * self.sched_latency_ms
        return max(raw_slice, self.min_granularity_ms)

    def run(self):
        """Menjalankan loop scheduling CFS sampai seluruh task selesai."""
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== FASE 1: SIMULASI LINUX COMPLETELY FAIR SCHEDULER (CFS) ==={CLR_RESET}")
        print(f"Target Latency: {self.sched_latency_ms} ms | Min Granularity: {self.min_granularity_ms} ms\n")
        print(f"{CLR_BOLD}{'Time(ms)':<10}{'PID':<6}{'Process':<12}{'Nice':<6}{'Weight':<8}{'Slice(ms)':<11}{'vRuntime':<12}{'Remaining':<10}{CLR_RESET}")
        print("-" * 75)

        global_time = 0.0

        while self.runqueue:
            total_weight = sum(task.weight for task in self.runqueue)
            # Ambil task dengan vruntime terkecil (paling 'terzalimi' menurut CFS)
            current = heapq.heappop(self.runqueue)

            time_slice = self.calculate_timeslice(current, total_weight)
            exec_time = min(time_slice, current.remaining_burst_ms)

            # Update metrik eksekusi
            current.remaining_burst_ms -= exec_time
            current.total_exec_ms += exec_time
            current.switches_count += 1

            # Rumus Kernel: delta_vruntime = delta_exec * (NICE_0_LOAD / weight)
            delta_vruntime = exec_time * (NICE_0_LOAD / current.weight)
            current.vruntime += delta_vruntime

            global_time += exec_time
            self.min_vruntime = min(current.vruntime, self.runqueue[0].vruntime if self.runqueue else current.vruntime)

            status_color = CLR_GREEN if current.remaining_burst_ms == 0 else CLR_YELLOW
            print(f"{global_time:<10.2f}{current.pid:<6}{current.name:<12}{current.nice:<6}{current.weight:<8}"
                  f"{exec_time:<11.2f}{current.vruntime:<12.2f}{status_color}{current.remaining_burst_ms:<10.2f}{CLR_RESET}")

            # Jika proses belum selesai, requeue kembali ke CFS min-heap (rbtree)
            if current.remaining_burst_ms > 0:
                heapq.heappush(self.runqueue, current)


class ThreadContextContentionBenchmark:
    """
    Benchmark nyata level sistem operasi untuk memicu Threading Contention
    dan mencatat latensi switching aktual serta lock starvation.
    """

    def __init__(self, num_threads: int = 4, iterations_per_thread: int = 150_000):
        self.num_threads = num_threads
        self.iterations = iterations_per_thread
        self.shared_counter = 0
        self.lock = threading.Lock()
        self.thread_stats: Dict[int, int] = {}

    def _worker(self, thread_idx: int):
        local_acquisitions = 0
        for _ in range(self.iterations):
            # Melakukan locking intensif untuk memicu OS thread descheduling
            with self.lock:
                self.shared_counter += 1
                local_acquisitions += 1
                # Mikro-yield untuk memancing kernel melakukan preemption/context switch
                if local_acquisitions % 25_000 == 0:
                    time.sleep(0.0001)

        self.thread_stats[thread_idx] = local_acquisitions

    def execute(self):
        """Menjalankan thread pool terorkestrasi dan mengukur durasi konkurensi."""
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== FASE 2: REAL-TIME THREAD CONTENTION & CONTEXT SWITCH BENCHMARK ==={CLR_RESET}")
        print(f"Cores Terdeteksi : {CLR_MAG}{os.cpu_count()}{CLR_RESET}")
        print(f"Thread Worker    : {self.num_threads} threads paralel")
        print(f"Total Iterasi    : {self.num_threads * self.iterations:,} critical section ops\n")

        threads: List[threading.Thread] = []
        t_start = time.perf_counter()

        for i in range(self.num_threads):
            t = threading.Thread(target=self._worker, args=(i,), name=f"Worker-{i}")
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        t_elapsed = time.perf_counter() - t_start
        ops_per_sec = (self.num_threads * self.iterations) / t_elapsed

        print(f"{CLR_BOLD}{'Thread ID':<15}{'Acquired Locks':<20}{'Status':<15}{CLR_RESET}")
        print("-" * 50)
        for tid, count in self.thread_stats.items():
            print(f"Worker-{tid:<8}{count:<20,}{CLR_GREEN}TERMINATED{CLR_RESET}")

        print(f"\nHasil Benchmark:")
        print(f"- Waktu Total     : {CLR_YELLOW}{t_elapsed:.4f} detik{CLR_RESET}")
        print(f"- Throughput      : {CLR_BOLD}{ops_per_sec:,.2f} ops/sec{CLR_RESET}")
        print(f"- Counter Final   : {self.shared_counter} (Expected: {self.num_threads * self.iterations})")


def print_system_inspection():
    """Membaca parameter penjadwalan kernel Linux aktual jika tersedia di /proc."""
    print(f"{CLR_BOLD}{CLR_CYAN}=== INFORMASI SUBSISTEM PENJADWALAN KERNEL HOST ==={CLR_RESET}")
    proc_paths = {
        "CFS Latency Target": "/proc/sys/kernel/sched_latency_ns",
        "CFS Min Granularity": "/proc/sys/kernel/sched_min_granularity_ns",
        "CFS Wakeup Granularity": "/proc/sys/kernel/sched_wakeup_granularity_ns"
    }

    found = False
    for label, path in proc_paths.items():
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    val = int(f.read().strip())
                    print(f"- {label:<24}: {CLR_GREEN}{val / 1_000_000:.2f} ms{CLR_RESET} ({val} ns)")
                    found = True
            except (PermissionError, OSError):
                pass

    if not found:
        print(f"{CLR_YELLOW}[Notice] /proc/sys/kernel scheduler files tidak dapat diakses langsung")
        print(f"         (Biasa terjadi pada runtime non-Linux atau container rootless).{CLR_RESET}")


def main():
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}   LAB DEEP DIVE: SISTEM PENJADWALAN KERNEL LINUX & THREAD CONCURRENCY{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")

    # Cek parameter internal OS
    print_system_inspection()

    # Inisialisasi simulator CFS
    cfs = CompletelyFairSchedulerSimulator(sched_latency_ms=24.0, min_granularity_ms=3.0)

    # Memuat Process Control Block (PCB) mock dengan beban dan variasi nice
    # Nice rendah = prioritas tinggi (bobot besar), Nice tinggi = prioritas rendah (bobot kecil)
    cfs.enqueue_task(pid=101, name="db_worker",   nice=-5, burst_ms=50.0)  # Prioritas tinggi
    cfs.enqueue_task(pid=102, name="web_server",  nice=0,  burst_ms=40.0)  # Prioritas standar
    cfs.enqueue_task(pid=103, name="log_sync",    nice=5,  burst_ms=30.0)  # Prioritas rendah
    cfs.enqueue_task(pid=104, name="batch_render",nice=10, burst_ms=25.0)  # Prioritas sangat rendah

    # Eksekusi algoritma CFS
    cfs.run()

    # Eksekusi benchmark lock contention dan OS scheduling aktual
    benchmark = ThreadContextContentionBenchmark(num_threads=4, iterations_per_thread=120_000)
    benchmark.execute()

    print(f"\n{CLR_GREEN}{CLR_BOLD}[OK] Hands-on Lab Selesai Tanpa Hambatan.{CLR_RESET}\n")


if __name__ == "__main__":
    main()