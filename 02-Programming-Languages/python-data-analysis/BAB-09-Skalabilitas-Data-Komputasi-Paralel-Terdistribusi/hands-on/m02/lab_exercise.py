#!/usr/bin/env python3
"""
Lab Hands-on: Skalabilitas Data & Komputasi Paralel Terdistribusi (Dask & Ray Architecture)
Bab 09 - Modul 02: Deep Dive Simulating DAG Scheduler & In-Memory Object Store

Deskripsi:
Script ini mengimplementasikan miniatur engine komputasi terdistribusi yang
menggabungkan konsep inti dari Apache Arrow Plasma/Ray Object Store (in-memory immutability)
dan Dask Distributed Scheduler (Dynamic DAG execution via in-degree tracking & futures).
"""

import time
import uuid
import threading
import concurrent.futures
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Set, Tuple

# --- ANSI Color Codes for Rich Terminal Output ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_CYAN   = "\033[36m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_MAGENTA= "\033[35m"
CLR_RED    = "\033[31m"


@dataclass(frozen=True)
class ObjectID:
    """Representasi handle unik untuk data terdistribusi (mirip Ray ObjectID)."""
    uid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def __repr__(self) -> str:
        return f"Obj({self.uid})"


class DistributedObjectStore:
    """
    Simulasi In-Memory Object Store (mirip Apache Arrow Plasma / Ray Shared Memory).
    Menjamin data bersifat 'immutable' setelah ditulis (put), serta melacak
    alokasi memori dan akses konkuren secara thread-safe.
    """
    def __init__(self):
        self._store: Dict[ObjectID, Any] = {}
        self._lock = threading.Lock()
        self._total_bytes: int = 0

    def put(self, value: Any) -> ObjectID:
        oid = ObjectID()
        # Estimasi representasi ukuran memori primitif
        val_size = len(str(value).encode('utf-8'))
        with self._lock:
            self._store[oid] = value
            self._total_bytes += val_size
        return oid

    def get(self, oid: ObjectID) -> Any:
        with self._lock:
            if oid not in self._store:
                raise KeyError(f"ObjectID {oid} tidak ditemukan di Object Store.")
            return self._store[oid]

    def get_stats(self) -> Tuple[int, int]:
        with self._lock:
            return len(self._store), self._total_bytes


@dataclass
class TaskNode:
    """Representasi node komputasi dalam Directed Acyclic Graph (DAG)."""
    task_id: str
    func: Callable
    args: Tuple[Any, ...]
    output_oid: ObjectID
    dependencies: Set[str] = field(default_factory=set)


class DistributedDAGScheduler:
    """
    Scheduler berbasis Task Graph Dependency (seperti Dask Distributed Scheduler).
    Menghitung derajat masuk (in-degree) tiap node dan mengeksekusi worker secara
    non-blocking paralel saat dependensi suatu node terpenuhi (in-degree == 0).
    """
    def __init__(self, object_store: DistributedObjectStore, max_workers: int = 4):
        self.store = object_store
        self.max_workers = max_workers
        self.graph: Dict[str, TaskNode] = {}
        self.dependents: Dict[str, Set[str]] = {}
        self.in_degree: Dict[str, int] = {}
        self._lock = threading.Lock()

    def submit(self, task_id: str, func: Callable, *args) -> ObjectID:
        """
        Mendaftarkan komputasi ke DAG (Lazy evaluation / Dask Delayed model).
        Memeriksa apakah argumen mengandung ObjectID dari task pendahulu.
        """
        output_oid = ObjectID()
        deps: Set[str] = set()

        for arg in args:
            if isinstance(arg, ObjectID):
                # Cari task mana yang memproduksi ObjectID ini
                for tid, node in self.graph.items():
                    if node.output_oid == arg:
                        deps.add(tid)

        node = TaskNode(task_id, func, args, output_oid, deps)
        self.graph[task_id] = node
        self.dependents[task_id] = set()
        self.in_degree[task_id] = len(deps)

        for dep in deps:
            self.dependents[dep].add(task_id)

        return output_oid

    def compute(self):
        """Mengeksekusi DAG secara paralel menggunakan Worker Pool terkoordinasi."""
        ready_queue: List[str] = []
        for tid, deg in self.in_degree.items():
            if deg == 0:
                ready_queue.append(tid)

        print(f"{CLR_CYAN}[DAG Engine]{CLR_RESET} Graph dikompilasi. Total tasks: {len(self.graph)}.")
        print(f"{CLR_CYAN}[DAG Engine]{CLR_RESET} Memulai eksekusi dengan {self.max_workers} worker threads.\n")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            active_futures: Dict[concurrent.futures.Future, str] = {}

            # Dispatch task awal yang tidak punya dependensi
            for tid in ready_queue:
                f = executor.submit(self._execute_task, self.graph[tid])
                active_futures[f] = tid

            while active_futures:
                # Menunggu task tercepat selesai (event-driven execution)
                done, _ = concurrent.futures.wait(
                    active_futures.keys(),
                    return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    completed_tid = active_futures.pop(future)
                    try:
                        res_oid, elapsed = future.result()
                        worker_name = threading.current_thread().name
                        print(f" {CLR_GREEN}✔ COMPLETED{CLR_RESET} Task: {CLR_BOLD}{completed_tid:<18}{CLR_RESET} "
                              f"| Output: {CLR_MAGENTA}{res_oid}{CLR_RESET} "
                              f"| Durasi: {elapsed*1000:6.2f}ms")

                        # Resolve dependensi hilir (Downstream Consumers)
                        with self._lock:
                            for consumer_tid in self.dependents[completed_tid]:
                                self.in_degree[consumer_tid] -= 1
                                if self.in_degree[consumer_tid] == 0:
                                    # Semua dependensi siap, dispatch ke worker pool
                                    nf = executor.submit(self._execute_task, self.graph[consumer_tid])
                                    active_futures[nf] = consumer_tid

                    except Exception as e:
                        print(f" {CLR_RED}✖ FAILED{CLR_RESET} Task {completed_tid}: {e}")
                        raise e

    def _execute_task(self, node: TaskNode) -> Tuple[ObjectID, float]:
        """Eksekusi kernel task oleh worker: dereferensi ObjectID -> eksekusi -> store balik."""
        t_start = time.perf_counter()

        # Materialisasi argumen: Resolve ObjectID menjadi data riil dari ObjectStore
        resolved_args = []
        for arg in node.args:
            if isinstance(arg, ObjectID):
                resolved_args.append(self.store.get(arg))
            else:
                resolved_args.append(arg)

        # Eksekusi fungsi pengguna
        result = node.func(*resolved_args)

        # Simpan kembali hasil komputasi ke distributed store (zero-copy buffer abstraction)
        self.store.put(result)
        # Kaitkan hasil ke node output_oid yang telah direservasi saat submit
        with self.store._lock:
            self.store._store[node.output_oid] = result

        t_elapsed = time.perf_counter() - t_start
        return node.output_oid, t_elapsed


# =====================================================================
# SIMULASI PIPELINE ANALISIS DATA SKALA BESAR (ETL & PENGURANGAN PARALEL)
# =====================================================================

def task_extract_partition(partition_id: int, size: int) -> List[int]:
    """Simulasi membaca partisi dataset mentah (mirip Dask read_parquet chunk)."""
    time.sleep(0.08)  # Simulasi I/O latency
    base = partition_id * size
    return [base + i for i in range(size)]

def task_transform_filter(records: List[int], modulo: int) -> List[int]:
    """Simulasi filter paralel dan pembersihan data (Map phase)."""
    time.sleep(0.05)  # Simulasi compute transform
    return [x for x in records if x % modulo == 0]

def task_compute_stats(chunk: List[int]) -> Dict[str, float]:
    """Simulasi agregasi lokal per-partisi."""
    time.sleep(0.04)
    if not chunk:
        return {"sum": 0, "count": 0, "max": 0}
    return {
        "sum": sum(chunk),
        "count": len(chunk),
        "max": max(chunk)
    }

def task_global_reduction(stat_a: Dict[str, float], stat_b: Dict[str, float]) -> Dict[str, float]:
    """Simulasi reduksi hierarkis (Tree-Reduction Pattern pada Dask/Ray)."""
    time.sleep(0.03)
    return {
        "sum": stat_a["sum"] + stat_b["sum"],
        "count": stat_a["count"] + stat_b["count"],
        "max": max(stat_a["max"], stat_b["max"])
    }


def main():
    print(f"\n{CLR_BOLD}{CLR_BLUE}=================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}  HANDS-ON LAB: DISTRIBUTED RUNTIME SIMULATOR (DASK & RAY PARADIGM){CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}=================================================================={CLR_RESET}\n")

    store = DistributedObjectStore()
    scheduler = DistributedDAGScheduler(object_store=store, max_workers=4)

    print(f"{CLR_YELLOW}[Inisialisasi]{CLR_RESET} Menyusun Task Dependency Graph (Lazy Delayed Builder)...")

    NUM_PARTITIONS = 4
    PARTITION_SIZE = 50_000

    extract_oids = []
    # 1. Bangun Stage 1: Parallel Ingestion / Partition Extract
    for p in range(NUM_PARTITIONS):
        oid = scheduler.submit(f"Extract_Part_{p}", task_extract_partition, p, PARTITION_SIZE)
        extract_oids.append(oid)

    # 2. Bangun Stage 2: Transformasi & Filter (Tergantung pada Stage 1)
    filter_oids = []
    for p in range(NUM_PARTITIONS):
        oid = scheduler.submit(f"Transform_Filter_{p}", task_transform_filter, extract_oids[p], 3)
        filter_oids.append(oid)

    # 3. Bangun Stage 3: Agregasi Lokal per Partisi (Tergantung pada Stage 2)
    stat_oids = []
    for p in range(NUM_PARTITIONS):
        oid = scheduler.submit(f"Local_Stats_{p}", task_compute_stats, filter_oids[p])
        stat_oids.append(oid)

    # 4. Bangun Stage 4: Tree Reduction Global (Menggabungkan Partisi)
    # Binary Reduction Tree: ((P0 + P1) + (P2 + P3))
    red_left = scheduler.submit("Reduce_P0_P1", task_global_reduction, stat_oids[0], stat_oids[1])
    red_right = scheduler.submit("Reduce_P2_P3", task_global_reduction, stat_oids[2], stat_oids[3])
    final_result_oid = scheduler.submit("Global_Aggregate", task_global_reduction, red_left, red_right)

    # 5. Jalankan Eksekusi Graph Terjadwal
    start_time = time.perf_counter()
    scheduler.compute()
    total_duration = time.perf_counter() - start_time

    # 6. Mengambil Hasil Akhir dari Object Store
    final_output = store.get(final_result_oid)
    num_objects, mem_bytes = store.get_stats()

    print(f"\n{CLR_BOLD}{CLR_BLUE}---------------------- EXECUTION REPORT ----------------------{CLR_RESET}")
    print(f" Total Waktu Eksekusi   : {CLR_BOLD}{total_duration:.4f} detik{CLR_RESET}")
    print(f" Item di Object Store   : {CLR_CYAN}{num_objects} objek terdaftar{CLR_RESET}")
    print(f" Estimasi Buffer Memory : {CLR_CYAN}{mem_bytes:,} bytes{CLR_RESET}")
    print(f" Total Elemen Divalidasi: {CLR_GREEN}{int(final_output['count']):,} records{CLR_RESET}")
    print(f" Akumulasi Nilai (Sum)  : {CLR_GREEN}{int(final_output['sum']):,}{CLR_RESET}")
    print(f" Nilai Maksimum Global  : {CLR_GREEN}{final_output['max']}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}=================================================================={CLR_RESET}\n")

if __name__ == "__main__":
    main()