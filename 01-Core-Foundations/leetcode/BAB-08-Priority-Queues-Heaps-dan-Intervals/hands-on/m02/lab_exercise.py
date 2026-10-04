#!/usr/bin/env python3
"""
Lab Hands-on: Priority Queues, Heaps & Advanced Intervals
Modul 02 Deep Dive - LeetCode Core Foundations (Chapter 08)

Topik Teknis:
1. Custom Priority Queue Engine dengan dynamic aging untuk mitigasi starvation.
2. Advanced Sweep-Line & Min-Heap Interval Allocator (Solusi optimal resource partitioning - LeetCode 2402 / 253).
3. Benchmark & Invariant Validator antara O(N log N) Heap Allocator vs O(N^2) Naive Scanner.
"""

import heapq
import time
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

# ANSI Color Codes untuk visualisasi terminal
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"


@dataclass(order=True)
class PriorityTask:
    """
    Task model untuk Priority Queue.
    Invarian heap: Tuple (effective_priority, arrival_time) menentukan urutan ekstraksi.
    Nilai effective_priority terendah diproses lebih dulu (Min-Heap behavior).
    """
    effective_priority: float
    task_id: str = field(compare=False)
    base_priority: int = field(compare=False)
    burst_time: int = field(compare=False)
    arrival_time: float = field(compare=False)


@dataclass
class Interval:
    """Interval kerja merepresentasikan alokasi runtime: [start_time, end_time)."""
    task_id: str
    start: int
    end: int
    resources_required: int = 1


class DynamicPriorityScheduler:
    """
    Priority Queue dengan Starvation-Prevention (Aging Algorithm).
    Heap standar rentan terhadap task starvation jika task berprioritas tinggi terus berdatangan.
    """

    def __init__(self, aging_rate: float = 0.5):
        self._heap: List[PriorityTask] = []
        self._aging_rate = aging_rate
        self._task_counter = 0

    def push(self, task_id: str, base_priority: int, burst_time: int, current_time: float) -> None:
        """Memasukkan task baru ke min-heap berdasarkan base priority."""
        self._task_counter += 1
        # Priority lebih kecil = urgensi lebih tinggi
        task = PriorityTask(
            effective_priority=float(base_priority),
            task_id=task_id,
            base_priority=base_priority,
            burst_time=burst_time,
            arrival_time=current_time
        )
        heapq.heappush(self._heap, task)

    def apply_aging(self, current_time: float) -> None:
        """
        O(N) in-place heap update untuk mendongkrak task yang lama tertahan (starvation mitigation).
        Setelah modifikasi nilai effective_priority, heapify dipanggil ulang untuk memulihkan invarian min-heap.
        """
        if not self._heap:
            return

        rebuilt = []
        for task in self._heap:
            wait_time = current_time - task.arrival_time
            # Effective priority berkurang (makin urgen) proporsional terhadap wait_time
            aged_priority = task.base_priority - (wait_time * self._aging_rate)
            task.effective_priority = max(0.0, aged_priority)
            rebuilt.append(task)

        self._heap = rebuilt
        heapq.heapify(self._heap)

    def pop(self) -> Optional[PriorityTask]:
        """Mengekstrak task dengan effective priority tertinggi (nilai terendah)."""
        if not self._heap:
            return None
        return heapq.heappop(self._heap)

    def __len__(self) -> int:
        return len(self._heap)


class AdvancedIntervalAllocator:
    """
    Sweep-Line & Dual-Heap Engine untuk optimasi alokasi mesin (Resource Partitioning).
    Menghitung room/worker minimum yang diperlukan dan mendistribusikan interval secara seimbang.
    """

    @staticmethod
    def min_resources_required(intervals: List[Interval]) -> int:
        """
        Algoritma Sweep-Line O(N log N) murni.
        Memecah interval menjadi events: (time, +1 untuk start, -1 untuk end).
        """
        events: List[Tuple[int, int]] = []
        for iv in intervals:
            events.append((iv.start, 1))   # Resource dialokasikan
            events.append((iv.end, -1))   # Resource dibebaskan

        # Sort: jika timestamp sama, event pelepasan (-1) dieksekusi sebelum alokasi (1)
        events.sort(key=lambda x: (x[0], x[1]))

        current_active = 0
        peak_resources = 0
        for _, delta in events:
            current_active += delta
            if current_active > peak_resources:
                peak_resources = current_active

        return peak_resources

    @staticmethod
    def assign_to_workers(intervals: List[Interval], total_workers: int) -> Tuple[Dict[int, List[Interval]], List[str]]:
        """
        Simulasi LeetCode 2402 (Meeting Rooms III).
        Menggunakan dua min-heap:
        1. `available_workers`: Menyimpan worker ID yang bebas [0, 1, ..., total_workers-1].
        2. `busy_workers`: Menyimpan (release_time, worker_id).
        """
        # Urutkan interval berdasarkan waktu mulai
        sorted_intervals = sorted(intervals, key=lambda x: (x.start, x.end))

        available_workers = list(range(total_workers))
        heapq.heapify(available_workers)

        # Heap elemen: (current_end_time, worker_id)
        busy_workers: List[Tuple[int, int]] = []

        allocations: Dict[int, List[Interval]] = {i: [] for i in range(total_workers)}
        delayed_logs: List[str] = []

        for iv in sorted_intervals:
            start, duration = iv.start, iv.end - iv.start

            # Bebaskan semua worker yang pekerjaannya selesai sebelum atau tepat pada start
            while busy_workers and busy_workers[0][0] <= start:
                _, released_worker_id = heapq.heappop(busy_workers)
                heapq.heappush(available_workers, released_worker_id)

            if available_workers:
                worker_id = heapq.heappop(available_workers)
                allocations[worker_id].append(iv)
                heapq.heappush(busy_workers, (iv.end, worker_id))
            else:
                # Semua worker sibuk: task mengalami penundaan (delay)
                earliest_finish, worker_id = heapq.heappop(busy_workers)
                delayed_start = earliest_finish
                delayed_end = delayed_start + duration
                delayed_logs.append(
                    f"Task {iv.task_id} terpaksa delay dari [{iv.start}, {iv.end}) "
                    f"ke [{delayed_start}, {delayed_end}) pada Worker-{worker_id}"
                )
                allocations[worker_id].append(
                    Interval(task_id=f"{iv.task_id}(delayed)", start=delayed_start, end=delayed_end)
                )
                heapq.heappush(busy_workers, (delayed_end, worker_id))

        return allocations, delayed_logs


def benchmark_intervals(num_intervals: int = 5000):
    """Membandingkan performa O(N log N) Heap Partitioning vs Simulasi Beban Kuadratik O(N^2)."""
    print(f"\n{CLR_BOLD}{CLR_CYAN}[BENCHMARK] Generating {num_intervals} synthetic task intervals...{CLR_RESET}")
    random.seed(42)
    intervals = []
    for i in range(num_intervals):
        s = random.randint(0, 100000)
        dur = random.randint(5, 500)
        intervals.append(Interval(task_id=f"T{i}", start=s, end=s + dur))

    # Eksekusi O(N log N)
    t0 = time.perf_counter()
    peak_sweep = AdvancedIntervalAllocator.min_resources_required(intervals)
    t_sweep = time.perf_counter() - t0

    print(f"{CLR_GREEN}✓ Sweep-Line O(N log N) selesai:{CLR_RESET} {t_sweep:.4f} detik (Peak Resources: {peak_sweep})")

    # Uji verifikasi Naive O(N^2) subset (hanya 500 data agar tidak freezing terminal)
    subset_size = 500
    subset = intervals[:subset_size]
    t0 = time.perf_counter()
    peak_naive = 0
    for i in range(len(subset)):
        concurrent = 0
        for j in range(len(subset)):
            # Cek overlap [start, end)
            if not (subset[j].end <= subset[i].start or subset[j].start >= subset[i].end):
                concurrent += 1
        peak_naive = max(peak_naive, concurrent)
    t_naive = time.perf_counter() - t0

    print(f"{CLR_YELLOW}✓ Naive O(N^2) (Sample subset {subset_size} items):{CLR_RESET} {t_naive:.4f} detik (Peak: {peak_naive})")


def run_laboratory():
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  ADVANCED HEAPS, PRIORITY QUEUES & INTERVAL SCHEDULING LAB (CH-08)  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")

    # ---------------------------------------------------------
    # SKENARIO 1: Dynamic Priority Queue & Starvation Aging
    # ---------------------------------------------------------
    print(f"\n{CLR_BOLD}--- Bagian 1: Priority Queue dengan Dynamic Starvation Aging ---{CLR_RESET}")
    scheduler = DynamicPriorityScheduler(aging_rate=1.5)

    # Tambahkan initial task: Low priority (base 10) dimasukkan di t=0
    scheduler.push(task_id="Batch-Analysis", base_priority=10, burst_time=20, current_time=0.0)
    print(f"{CLR_CYAN}[t=0s]{CLR_RESET} Push: Batch-Analysis (Base Priority: 10, Aging Rate: 1.5/s)")

    # Masuk high priority tasks di t=1, t=2
    scheduler.push(task_id="User-Checkout-1", base_priority=2, burst_time=5, current_time=1.0)
    scheduler.push(task_id="User-Checkout-2", base_priority=2, burst_time=5, current_time=2.0)
    print(f"{CLR_CYAN}[t=2s]{CLR_RESET} Push: User-Checkout-1 & 2 (Base Priority: 2)")

    # Simulasikan waktu melompat ke t=8s tanpa aging
    print(f"\n{CLR_YELLOW}Status Heap saat t=8s SEBELUM Aging:{CLR_RESET}")
    for item in sorted(scheduler._heap, key=lambda x: x.effective_priority):
        print(f"  * Task: {item.task_id:18} | Eff-Priority: {item.effective_priority:5.1f} | Base: {item.base_priority}")

    # Jalankan aging engine
    scheduler.apply_aging(current_time=8.0)
    print(f"\n{CLR_GREEN}Status Heap saat t=8s SETELAH Aging (wait_time: 8s x 1.5 = boost -12.0):{CLR_RESET}")
    for item in sorted(scheduler._heap, key=lambda x: x.effective_priority):
        print(f"  * Task: {item.task_id:18} | Eff-Priority: {item.effective_priority:5.1f} | Base: {item.base_priority}")

    top_task = scheduler.pop()
    print(f"\n{CLR_BOLD}Task yang dieksekusi pertama:{CLR_RESET} {CLR_GREEN}{top_task.task_id}{CLR_RESET} "
          f"(Effective Priority: {top_task.effective_priority:.1f})")

    # ---------------------------------------------------------
    # SKENARIO 2: Interval Resource Partitioning & Delay Log
    # ---------------------------------------------------------
    print(f"\n{CLR_BOLD}--- Bagian 2: Cluster Resource Allocator (Meeting Rooms III Sim) ---{CLR_RESET}")
    sample_intervals = [
        Interval("Job-A", 1, 8),
        Interval("Job-B", 2, 5),
        Interval("Job-C", 3, 7),
        Interval("Job-D", 5, 9),
        Interval("Job-E", 6, 11),
        Interval("Job-F", 10, 14),
    ]

    min_needed = AdvancedIntervalAllocator.min_resources_required(sample_intervals)
    print(f"Total Interval: {len(sample_intervals)}")
    print(f"Beban Bersamaan Maksimum (Peak Overlap): {CLR_BOLD}{CLR_RED}{min_needed} Worker Nodes{CLR_RESET}")

    # Uji alokasi dengan constrained capacity (hanya 2 worker tersedia, memaksa queue delay)
    constrained_workers = 2
    print(f"\nMengalokasikan ke {constrained_workers} Worker Nodes (Kapasitas Terbatas):")
    workers_table, delays = AdvancedIntervalAllocator.assign_to_workers(sample_intervals, constrained_workers)

    for worker_id, jobs in workers_table.items():
        jobs_repr = ", ".join([f"{j.task_id}[{j.start}-{j.end}]" for j in jobs])
        print(f"  {CLR_CYAN}Worker-{worker_id}:{CLR_RESET} {jobs_repr}")

    if delays:
        print(f"\n{CLR_YELLOW}[Resource Contention Logs]:{CLR_RESET}")
        for log in delays:
            print(f"  ! {log}")

    # ---------------------------------------------------------
    # SKENARIO 3: Algorithmic Verification & Complexity Scaling
    # ---------------------------------------------------------
    benchmark_intervals(num_intervals=5000)

    print(f"\n{CLR_BOLD}{CLR_GREEN}[STATUS] Seluruh modul verifikasi Heap & Interval berhasil dieksekusi.{CLR_RESET}\n")


if __name__ == "__main__":
    run_laboratory()