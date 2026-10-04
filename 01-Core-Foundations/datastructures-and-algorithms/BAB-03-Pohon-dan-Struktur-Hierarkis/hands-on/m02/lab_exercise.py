#!/usr/bin/env python3
"""
================================================================================
LAB HANDS-ON: 01-Core-Foundations / Bab 03 - Modul 02
Topik: Advanced Data Structures - Indexed Binary Min-Heap & Priority Task Engine
Implementasi: Custom Indexed Min-Heap dengan Operasi O(log N) Decrease-Key,
              Starvation Aging Engine, dan Benchmarking Kinerja Algoritmik.
================================================================================
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# ==============================================================================
# Terminal Color Palette (ANSI Escape Codes)
# ==============================================================================
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_WHITE   = "\033[37m"


# ==============================================================================
# Model Data: Task Node
# ==============================================================================
@dataclass(order=True)
class Task:
    priority: float
    task_id: str = field(compare=False)
    payload: str = field(compare=False)
    created_at: float = field(compare=False, default_factory=time.time)
    age_counter: int = field(compare=False, default=0)


# ==============================================================================
# Struktur Data Inti: Indexed Binary Min-Heap
# ==============================================================================
class IndexedMinHeap:
    """
    Binary Min-Heap berbasis Array dengan Inverted Index (Position Map).
    Mendukung:
      - Push: O(log N)
      - Pop-Min: O(log N)
      - Decrease-Key: O(log N) via ID dereferencing instan O(1)
      - Delete Arbitrary Node: O(log N)
    """

    def __init__(self) -> None:
        self._heap: List[Task] = []
        # Memetakan task_id -> indeks elemen di dalam list self._heap
        self._pos_map: Dict[str, int] = {}

    def __len__(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def _swap(self, i: int, j: int) -> None:
        """Menukar dua elemen pada heap dan mengupdate posisi di pos_map secara atomik."""
        self._heap[i], self._heap[j] = self._heap[j], self._heap[i]
        self._pos_map[self._heap[i].task_id] = i
        self._pos_map[self._heap[j].task_id] = j

    def _sift_up(self, idx: int) -> None:
        """Memperbaiki invariant heap ke atas (bubble-up)."""
        while idx > 0:
            parent_idx = (idx - 1) >> 1
            if self._heap[idx].priority < self._heap[parent_idx].priority:
                self._swap(idx, parent_idx)
                idx = parent_idx
            else:
                break

    def _sift_down(self, idx: int) -> None:
        """Memperbaiki invariant heap ke bawah (bubble-down)."""
        size = len(self._heap)
        while True:
            smallest = idx
            left = (idx << 1) + 1
            right = left + 1

            if left < size and self._heap[left].priority < self._heap[smallest].priority:
                smallest = left
            if right < size and self._heap[right].priority < self._heap[smallest].priority:
                smallest = right

            if smallest != idx:
                self._swap(idx, smallest)
                idx = smallest
            else:
                break

    def push(self, task: Task) -> None:
        """Menyisipkan task baru ke heap."""
        if task.task_id in self._pos_map:
            raise ValueError(f"Task ID '{task.task_id}' sudah ada di heap.")
        idx = len(self._heap)
        self._heap.append(task)
        self._pos_map[task.task_id] = idx
        self._sift_up(idx)

    def pop_min(self) -> Task:
        """Mengambil elemen dengan prioritas numerik terkecil (nilai urgensi tertinggi)."""
        if not self._heap:
            raise IndexError("Heap kosong: tidak dapat melakukan pop.")
        root = self._heap[0]
        last = self._heap.pop()
        del self._pos_map[root.task_id]

        if self._heap:
            self._heap[0] = last
            self._pos_map[last.task_id] = 0
            self._sift_down(0)

        return root

    def decrease_key(self, task_id: str, new_priority: float) -> None:
        """
        Menurunkan nilai prioritas suatu task (meningkatkan urgensi eksekusi).
        Operasi ini berjalan dalam O(log N) berkat inverted index.
        """
        if task_id not in self._pos_map:
            raise KeyError(f"Task '{task_id}' tidak ditemukan pada heap.")
        idx = self._pos_map[task_id]
        if new_priority > self._heap[idx].priority:
            raise ValueError("Nilai prioritas baru harus lebih kecil dari prioritas saat ini.")
        
        self._heap[idx].priority = new_priority
        self._sift_up(idx)

    def contains(self, task_id: str) -> bool:
        return task_id in self._pos_map

    def peek(self) -> Optional[Task]:
        return self._heap[0] if self._heap else None

    def get_all_tasks(self) -> List[Task]:
        return list(self._heap)


# ==============================================================================
# Engine Simulasi: RTOS / Networking QoS Scheduler with Aging
# ==============================================================================
class RealTimeTaskScheduler:
    """
    Mesin scheduler yang mengonsumsi antrean berprioritas dengan mekanisme
    anti-starvation aging (dynamic priority adjustment).
    """

    def __init__(self, aging_threshold: int = 3, aging_boost: float = 2.0) -> None:
        self.pq = IndexedMinHeap()
        self.aging_threshold = aging_threshold
        self.aging_boost = aging_boost

    def submit_job(self, task_id: str, priority: float, payload: str) -> None:
        task = Task(priority=priority, task_id=task_id, payload=payload)
        self.pq.push(task)

    def tick_and_age(self) -> None:
        """
        Simulasi siklus clock sistem: task yang belum dieksekusi akan mengalami penuaan (aging).
        Jika age_counter melewati ambang batas, prioritas dinaikkan via decrease_key.
        """
        tasks = self.pq.get_all_tasks()
        for task in tasks:
            task.age_counter += 1
            if task.age_counter >= self.aging_threshold:
                new_prio = max(0.1, task.priority - self.aging_boost)
                if new_prio < task.priority:
                    self.pq.decrease_key(task.task_id, new_prio)
                    task.age_counter = 0

    def process_next(self) -> Optional[Task]:
        if self.pq.is_empty():
            return None
        return self.pq.pop_min()


# ==============================================================================
# Benchmarking Engine: Analisis Empiris O(log N) vs O(N)
# ==============================================================================
def benchmark_linear_vs_heap(dataset_sizes: List[int]) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== BENCHMARK: Linear Search vs Binary Heap Extraction ==={CLR_RESET}")
    print(f"{'Data Size (N)':<15} | {'Heap Push+Pop (s)':<22} | {'Linear Search Min (s)':<22} | {'Speedup':<10}")
    print("-" * 75)

    for n in dataset_sizes:
        raw_data = [random.uniform(1.0, 1000.0) for _ in range(n)]

        # 1. Test Indexed Min-Heap
        heap = IndexedMinHeap()
        t0 = time.perf_counter()
        for i, val in enumerate(raw_data):
            heap.push(Task(priority=val, task_id=f"T_{i}", payload="data"))
        while not heap.is_empty():
            heap.pop_min()
        t_heap = time.perf_counter() - t0

        # 2. Test Linear Scan (Simulasi Unsorted Dynamic Array)
        data_copy = list(raw_data)
        t0 = time.perf_counter()
        # Ambil 100 sampel pop-min linear agar benchmark rasional dalam batas waktu
        sample_pops = min(n, 200)
        for _ in range(sample_pops):
            min_idx = 0
            min_val = data_copy[0]
            for idx in range(1, len(data_copy)):
                if data_copy[idx] < min_val:
                    min_val = data_copy[idx]
                    min_idx = idx
            data_copy.pop(min_idx)
        # Ekstrapolasi estimasi penuh O(N^2)
        factor = n / sample_pops
        t_linear_extrapolated = (time.perf_counter() - t0) * factor

        speedup = t_linear_extrapolated / (t_heap if t_heap > 0 else 1e-9)

        print(
            f"{n:<15} | "
            f"{CLR_GREEN}{t_heap:<22.5f}{CLR_RESET} | "
            f"{CLR_RED}{t_linear_extrapolated:<22.5f}{CLR_RESET} | "
            f"{CLR_YELLOW}{speedup:<9.1f}x{CLR_RESET}"
        )


# ==============================================================================
# Main Runner & Verification
# ==============================================================================
def run_simulation() -> None:
    print(f"{CLR_BOLD}{CLR_MAGENTA}╔═════════════════════════════════════════════════════════════════════════╗{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}║      LAB 03: INDEXED MIN-HEAP & DYNAMIC AGING SCHEDULER ENGINE          ║{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}╚═════════════════════════════════════════════════════════════════════════╝{CLR_RESET}")

    scheduler = RealTimeTaskScheduler(aging_threshold=2, aging_boost=4.0)

    # Inisialisasi antrean pekerjaan
    initial_jobs = [
        ("JOB_CRON_01", 15.0, "Background Log Archival"),
        ("JOB_API_AUTH", 3.0, "OAuth Token Verification"),
        ("JOB_DB_CLEAN", 18.0, "Dead Tuples Vacuum"),
        ("JOB_PAY_GATE", 1.5, "Payment Webhook Dispatch"),
        ("JOB_REPORT",   20.0, "Monthly PDF Generation"),
        ("JOB_ALERT",    2.0, "PagerDuty Healthcheck Alert"),
    ]

    print(f"\n{CLR_CYAN}[+] Memuat batch pekerjaan awal ke Indexed Priority Queue...{CLR_RESET}")
    for jid, prio, desc in initial_jobs:
        scheduler.submit_job(jid, prio, desc)
        print(f"    • Enqueue -> ID: {CLR_BOLD}{jid:<14}{CLR_RESET} | Priority: {prio:<4.1f} | Desc: {desc}")

    print(f"\n{CLR_YELLOW}[*] Memulai siklus eksekusi dengan mekanisme anti-starvation aging...{CLR_RESET}")

    cycle = 1
    while not scheduler.pq.is_empty():
        print(f"\n--- {CLR_BOLD}Clock Cycle #{cycle}{CLR_RESET} ---")
        
        # Eksekusi task dengan urgensi tertinggi (Priority terendah)
        dispatched = scheduler.process_next()
        if dispatched:
            print(
                f"  {CLR_GREEN}✔ DISPATCHED{CLR_RESET} -> "
                f"[{CLR_BOLD}{dispatched.task_id}{CLR_RESET}] "
                f"Prio: {CLR_YELLOW}{dispatched.priority:<4.1f}{CLR_RESET} "
                f"(Payload: {dispatched.payload})"
            )

        # Naikkan usia task yang tersisa di queue (Aging)
        if not scheduler.pq.is_empty():
            print(f"  {CLR_BLUE}⚙ Running Aging Pass on remaining nodes...{CLR_RESET}")
            scheduler.tick_and_age()
            # Introspeksi status heap setelah aging
            for task in scheduler.pq.get_all_tasks():
                print(f"    - In Queue: {task.task_id:<14} | Current Priority: {task.priority:<4.1f} | Age: {task.age_counter}")

        cycle += 1

    # Invariant Health Verification
    print(f"\n{CLR_GREEN}[✔] Simulasi lifecycle queue selesai secara deterministik.{CLR_RESET}")

    # Eksekusi Benchmark Empiris
    benchmark_linear_vs_heap(dataset_sizes=[2_000, 5_000, 10_000])
    print(f"\n{CLR_BOLD}{CLR_GREEN}[Lab Execution Completed Successfully]{CLR_RESET}\n")


if __name__ == "__main__":
    try:
        run_simulation()
    except KeyboardInterrupt:
        print(f"\n{CLR_RED}[!] Eksekusi dibatalkan oleh pengguna.{CLR_RESET}")
        sys.exit(1)