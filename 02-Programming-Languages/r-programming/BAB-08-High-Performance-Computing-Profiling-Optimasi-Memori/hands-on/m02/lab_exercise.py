#!/usr/bin/env python3
"""
Lab Hands-on: High-Performance Computing, Profiling, & Memory Optimization (R Paradigm)
Bab 08 - Modul 02 Deep Dive

Skrip ini memodelkan dan mensimulasikan mekanisme internal R:
1. Semantik Copy-on-Write (CoW) dan pelacakan memori ala tracemem().
2. Penalti performa Modifikasi-in-Loop tanpa pra-alokasi vs Pra-alokasi memori.
3. Simulasi Profiler Eksekusi (Rprof) berbasis sampling interrupt.
4. Simulasi Vectorization vs Interpreted Loop Dispatch.
5. Pemrosesan paralel multi-worker chunking ala mclapply().
"""

import sys
import time
import random
import threading
import itertools
from concurrent.futures import ThreadPoolExecutor

# Konfigurasi Tampilan Terminal ANSI
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[1;31m"
CLR_GREEN  = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_BLUE   = "\033[1;34m"
CLR_CYAN   = "\033[1;36m"
CLR_GRAY   = "\033[90m"


class RObject:
    """
    Mensimulasikan SEXP (S-Expression) R dengan pelacakan Reference Count
    dan penandaan memori untuk mereplikasi Copy-on-Write (CoW).
    """
    _id_counter = 0x7ffd0000

    def __init__(self, data=None, name="anon"):
        RObject._id_counter += 0x100
        self.address = hex(RObject._id_counter)
        self.data = list(data) if data is not None else []
        self.ref_count = 1
        self.name = name
        self.traced = False

    def size_bytes(self):
        # Header SEXP (~40 bytes di GNU R) + 8 byte per elemen float/int
        return 40 + (len(self.data) * 8)


class RMemoryEngine:
    """
    Sub-sistem memori R: Mensimulasikan alokator memori GNU R dan tracemem().
    """
    def __init__(self):
        self.allocated_bytes = 0
        self.copies_triggered = 0
        self.history = []

    def tracemem(self, obj: RObject):
        obj.traced = True
        print(f"{CLR_CYAN}[tracemem]{CLR_RESET} Objek '{obj.name}' dipantau di memori: <{obj.address}>")

    def duplicate(self, obj: RObject, reason="CoW") -> RObject:
        """Menduplikasi objek jika ref_count > 1 saat mutasi terjadi (Copy-on-Write)."""
        self.copies_triggered += 1
        new_obj = RObject(obj.data, name=f"{obj.name}_copy")
        alloc_size = new_obj.size_bytes()
        self.allocated_bytes += alloc_size

        if obj.traced:
            print(f"{CLR_YELLOW}[tracemem -> DUPLIKASI]{CLR_RESET} "
                  f"<{obj.address}> diduplikasi ke <{new_obj.address}> | Pemicu: {reason} | Ukuran: {alloc_size} bytes")

        return new_obj

    def modify_element(self, obj: RObject, index: int, value: any) -> RObject:
        """Mensimulasikan assignment: vec[i] <- value di R."""
        target = obj
        if obj.ref_count > 1:
            # Sifat CoW GNU R: Jika direferensikan lebih dari 1 binding, duplikasi sebelum menulis
            target = self.duplicate(obj, reason="Modifikasi Elemen (NAMED > 1)")
            obj.ref_count -= 1
            target.ref_count = 1
        
        target.data[index] = value
        return target


class ExecutionProfiler:
    """
    Simulasi Rprof(): Profiling eksekusi berbasis statistical sampling timer.
    """
    def __init__(self, interval_ms=5):
        self.interval = interval_ms / 1000.0
        self.samples = []
        self._running = False
        self._thread = None
        self._current_tag = "idle"

    def set_tag(self, tag: str):
        self._current_tag = tag

    def _sample_loop(self):
        while self._running:
            self.samples.append(self._current_tag)
            time.sleep(self.interval)

    def start(self):
        self.samples.clear()
        self._running = True
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()

    def summary(self):
        total = len(self.samples)
        if total == 0:
            print(f"{CLR_GRAY}Profiler tidak menangkap sampel (eksekusi terlalu cepat).{CLR_RESET}")
            return
        
        counts = {}
        for tag in self.samples:
            counts[tag] = counts.get(tag, 0) + 1

        print(f"\n{CLR_BOLD}=== LAPORAN SUMMARY Rprof() (Sampling Profiler) ==={CLR_RESET}")
        print(f"{'Routine / Call Trace':<35} | {'Sampel':<8} | {'Self Time %':<12}")
        print("-" * 62)
        for tag, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total) * 100
            print(f"{tag:<35} | {count:<8} | {pct:>6.2f}%")


def benchmark_cow_and_preallocation():
    """
    Studi Kasus 1: Dampak Anti-Pattern Vector Append (v <- c(v, i)) vs Pra-alokasi.
    """
    print(f"\n{CLR_BOLD}{CLR_BLUE}--- 1. BENCHMARK MEMORI: ANTI-PATTERN vs PRA-ALOKASI (CoW) ---{CLR_RESET}")
    engine = RMemoryEngine()
    N = 2500

    # Model A: Naive Growing Vector (v <- c(v, x))
    print(f"\n{CLR_YELLOW}[Simulasi] Pendekatan Naive: Pertumbuhan Dinamis (Vector Expansion){CLR_RESET}")
    vec_naive = RObject([], name="naive_vec")
    engine.tracemem(vec_naive)
    
    t0 = time.perf_counter()
    for i in range(5):  # Cetak sampel beberapa alokasi pertama
        vec_naive = engine.duplicate(vec_naive, reason="Append c(vec, item)")
        vec_naive.data.append(i)
    
    # Lanjutkan iterasi tanpa logging penuh untuk menghemat stdout
    vec_naive.traced = False
    for i in range(5, N):
        vec_naive = engine.duplicate(vec_naive, reason="Append Loop")
        vec_naive.data.append(i)
    t_naive = time.perf_counter() - t0
    naive_copies = engine.copies_triggered

    # Model B: Pra-alokasi Memori (v <- numeric(N))
    print(f"\n{CLR_GREEN}[Simulasi] Pendekatan Optimal: Pra-alokasi Memori Terstruktur{CLR_RESET}")
    engine_prealloc = RMemoryEngine()
    vec_prealloc = RObject([0] * N, name="prealloc_vec")
    engine_prealloc.tracemem(vec_prealloc)

    t0 = time.perf_counter()
    # Modifikasi in-place karena ref_count = 1 (tidak memicu CoW)
    for i in range(N):
        vec_prealloc = engine_prealloc.modify_element(vec_prealloc, i, i * 2)
    t_prealloc = time.perf_counter() - t0

    print(f"\n{CLR_BOLD}Hasil Metrik Manajemen Memori & Waktu:{CLR_RESET}")
    print(f" - Naive Growing   : {t_naive:.5f}s | Duplikasi Memori Terjadi: {CLR_RED}{naive_copies} kali{CLR_RESET}")
    print(f" - Pre-allocated   : {t_prealloc:.5f}s | Duplikasi Memori Terjadi: {CLR_GREEN}{engine_prealloc.copies_triggered} kali{CLR_RESET}")
    speedup = t_naive / t_prealloc if t_prealloc > 0 else float('inf')
    print(f" - Indeks Efisiensi: {CLR_BOLD}{CLR_GREEN}{speedup:.1f}x lebih cepat{CLR_RESET}\n")


def benchmark_vectorization_vs_interpreter(profiler: ExecutionProfiler):
    """
    Studi Kasus 2: Vectorization C-level vs Interpreted Loop Dispatch Overhead.
    """
    print(f"{CLR_BOLD}{CLR_BLUE}--- 2. VECTORIZATION VS INTERPRETED LOOP RUNTIME ---{CLR_RESET}")
    N = 150_000
    dataset = [random.random() for _ in range(N)]

    # 1. Interpreted Loop (Simulasi overhead AST parsing & per-element dispatch di R)
    profiler.set_tag("eval_ast::interpreted_loop")
    t0 = time.perf_counter()
    res_loop = []
    for val in dataset:
        # Simulasi overhead dynamic type checking & scalar SEXP boxing di runtime R
        _type_chk = isinstance(val, float)
        res_loop.append((val * 2.5) ** 0.5)
    t_loop = time.perf_counter() - t0

    # 2. Vectorized SIMD/Batch Execution (Simulasi R primitive / C-internal)
    profiler.set_tag("c_builtin::vec_arithmetic")
    t0 = time.perf_counter()
    # Direct memory transformation tanpa overhead dynamic dispatch per elemen
    multiplier = 2.5
    res_vec = [ (v * multiplier) ** 0.5 for v in dataset ]
    t_vec = time.perf_counter() - t0

    print(f"{'Metode Eksekusi':<30} | {'Waktu (detik)':<15} | {'Throughput (ops/s)':<18}")
    print("-" * 68)
    print(f"{'Interpreted Loop (Scalar)':<30} | {t_loop:<15.5f} | {N/t_loop:>15,.0f}")
    print(f"{'Vectorized (Direct Batch)':<30} | {t_vec:<15.5f} | {N/t_vec:>15,.0f}")
    diff = (t_loop / t_vec) if t_vec > 0 else 0
    print(f"Status Optimasi: {CLR_GREEN}Peningkatan Kecepatan = {diff:.2f}x{CLR_RESET}\n")


def parallel_worker_task(chunk_id: int, data_chunk: list) -> float:
    """Simulasi fungsi heavy-computation yang dijalankan via parallel::mclapply."""
    accumulator = 0.0
    for item in data_chunk:
        # Simulasi kalkulasi kernel intensif CPU (misal: resampling / bootstrap)
        val = item
        for _ in range(25):
            val = (val * 1.0001) % 1000.0
        accumulator += val
    return accumulator


def benchmark_hpc_multicore(profiler: ExecutionProfiler):
    """
    Studi Kasus 3: High-Performance Computing via Fork/Thread Chunking (mclapply).
    """
    print(f"{CLR_BOLD}{CLR_BLUE}--- 3. HIGH PERFORMANCE COMPUTING: PARALELISASI MULTICORE ---{CLR_RESET}")
    total_records = 200_000
    num_cores = 4
    raw_data = [random.uniform(1.0, 100.0) for _ in range(total_records)]

    # Partisi Chunking Memori
    chunk_size = total_records // num_cores
    chunks = [raw_data[i * chunk_size : (i + 1) * chunk_size] for i in range(num_cores)]

    # Sekuensial (Single Core)
    profiler.set_tag("hpc::sequential_lapply")
    t0 = time.perf_counter()
    seq_results = [parallel_worker_task(0, raw_data)]
    t_seq = time.perf_counter() - t0

    # Multicore Chunking (mclapply)
    profiler.set_tag("hpc::parallel_mclapply")
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=num_cores) as executor:
        futures = [executor.submit(parallel_worker_task, idx, chunk) for idx, chunk in enumerate(chunks)]
        par_results = [f.result() for f in futures]
    t_par = time.perf_counter() - t0

    print(f"Ukuran Data: {total_records:,} entri | Pekerja Paralel (Workers): {num_cores}")
    print(f" - Sequential (lapply) execution : {CLR_RED}{t_seq:.4f} detik{CLR_RESET}")
    print(f" - Multicore  (mclapply) execution: {CLR_GREEN}{t_par:.4f} detik{CLR_RESET}")
    speedup = t_seq / t_par if t_par > 0 else 0
    efficiency = (speedup / num_cores) * 100
    print(f" - Multi-thread Speedup           : {CLR_BOLD}{speedup:.2f}x{CLR_RESET} (Efisiensi Inti: {efficiency:.1f}%)\n")


def main():
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}   HANDS-ON LAB: OPTIMASI MEMORI, PROFILING, & HPC DALAM ENGINE R    {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")

    profiler = ExecutionProfiler(interval_ms=2)
    profiler.start()

    try:
        # Menjalankan modul studi kasus teknis
        benchmark_cow_and_preallocation()
        benchmark_vectorization_vs_interpreter(profiler)
        benchmark_hpc_multicore(profiler)
    finally:
        profiler.set_tag("runtime::teardown")
        profiler.stop()

    # Ekstraksi diagnosa dari profiler internal
    profiler.summary()

    print(f"\n{CLR_GREEN}{CLR_BOLD}[VERIFIKASI LAB SELESAI]{CLR_RESET} Seluruh model HPC & optimasi memori sukses diuji.")


if __name__ == "__main__":
    main()