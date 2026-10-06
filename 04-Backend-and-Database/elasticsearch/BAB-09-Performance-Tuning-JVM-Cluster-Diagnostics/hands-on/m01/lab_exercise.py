#!/usr/bin/env python3
"""
Elasticsearch Performance Tuning, JVM & Cluster Diagnostics Lab Exercise
========================================================================
Modul: BAB-09-Performance-Tuning-JVM-Cluster-Diagnostics (Hands-on M01)

Simulasi mandiri interaktif untuk mendemonstrasikan:
1. Aturan 50% Heap Allocation & Ambang Batas 32GB Compressed OOPs
2. Dinamika Memory Circuit Breakers (Parent, Fielddata, Request)
3. Saturasi Thread Pool (Write/Search queues) & Error 429 EsRejectedExecutionException
4. Siklus JVM Garbage Collection (Young Gen Eden/Survivor vs Old Gen CMS/G1GC)
5. Cluster Health State Machine (GREEN / YELLOW / RED) & Root Cause Diagnostics
"""

import sys
import time
import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ==============================================================================
# ANSI Color Codes & Terminal Helpers
# ==============================================================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_RED = "\033[41m"
BG_YELLOW = "\033[43m"
BG_GREEN = "\033[42m"
BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 78}{RESET}")
    print(f"{BOLD}{WHITE}  {title.center(74)}  {RESET}")
    print(f"{BOLD}{CYAN}{'=' * 78}{RESET}\n")


def status_badge(state: str) -> str:
    if state == "GREEN":
        return f"{BG_GREEN}{BOLD}{WHITE}  GREEN   {RESET}"
    elif state == "YELLOW":
        return f"{BG_YELLOW}{BOLD}{WHITE}  YELLOW  {RESET}"
    elif state == "RED":
        return f"{BG_RED}{BOLD}{WHITE}   RED    {RESET}"
    return f"{WHITE}[{state}]{RESET}"


def progress_bar(val: float, max_val: float, length: int = 30, color: str = GREEN) -> str:
    ratio = min(1.0, max(0.0, val / max_val if max_val > 0 else 0.0))
    filled = int(ratio * length)
    bar = "█" * filled + "░" * (length - filled)
    percent = ratio * 100.0
    return f"{color}[{bar}]{RESET} {percent:5.1f}%"


# ==============================================================================
# Model & Simulation Engines
# ==============================================================================

@dataclass
class JVMHeapConfig:
    total_ram_gb: float
    allocated_heap_gb: float

    def analyze(self) -> Dict[str, str]:
        ratio = self.allocated_heap_gb / self.total_ram_gb if self.total_ram_gb > 0 else 0
        lucenes_cache = self.total_ram_gb - self.allocated_heap_gb

        # Check compressed OOPs threshold (typically around 30.5GB - 32GB)
        compressed_oops = self.allocated_heap_gb <= 30.5
        zero_based_oops = self.allocated_heap_gb <= 26.0

        if self.allocated_heap_gb > 32.0:
            oops_status = f"{RED}CRITICAL: Compressed OOPs disabled! 64-bit pointers active (+40-50% memory bloat){RESET}"
            recommendation = "Turunkan heap ke maksimal 30.5 GB (atau <= 31 GB) untuk mengaktifkan kembali 32-bit pointer."
        elif not zero_based_oops:
            oops_status = f"{YELLOW}WARN: Zero-based Compressed OOPs non-aktif, tapi Compressed OOPs aktif.{RESET}"
            recommendation = "Pertimbangkan menurunkan ke <= 26 GB jika ingin optimasi nol offset zero-based."
        else:
            oops_status = f"{GREEN}OPTIMAL: Zero-based Compressed OOPs aktif (efisiensi pointer maksimal).{RESET}"
            recommendation = "Ukuran heap ramah terhadap pointer compression."

        if ratio > 0.55:
            ratio_status = f"{YELLOW}RISK: Alokasi heap ({ratio*100:.1f}%) melebihi rekomendasi 50% RAM.{RESET}"
            ratio_tip = "Lucene FS/Page cache kekurangan memori untuk file segment dan Doc Values."
        elif ratio < 0.40:
            ratio_status = f"{CYAN}CONSERVATIVE: Heap di bawah 50% ({ratio*100:.1f}%).{RESET}"
            ratio_tip = "FS Cache sangat lapang, tetapi pastikan query agregasi besar tidak memicu OOM."
        else:
            ratio_status = f"{GREEN}IDEAL: Heap seimbang (50/50 Rule) dengan FS Cache.{RESET}"
            ratio_tip = "Lucene Page Cache dan JVM Heap memiliki rasio pembagian seimbang."

        return {
            "ratio_status": ratio_status,
            "ratio_tip": ratio_tip,
            "oops_status": oops_status,
            "recommendation": recommendation,
            "lucene_ram_gb": f"{lucenes_cache:.1f} GB"
        }


@dataclass
class CircuitBreaker:
    name: str
    limit_pct: float
    overhead: float
    current_used_mb: float = 0.0

    def check(self, allocated_heap_mb: float, delta_mb: float) -> bool:
        max_allowed_mb = allocated_heap_mb * (self.limit_pct / 100.0)
        projected = (self.current_used_mb + delta_mb) * self.overhead
        if projected > max_allowed_mb:
            return False  # Tripped
        self.current_used_mb += delta_mb
        return True


@dataclass
class ThreadPoolState:
    name: str
    threads: int
    queue_capacity: int
    active_threads: int = 0
    queued_tasks: int = 0
    rejected_count: int = 0

    def dispatch(self, incoming: int) -> int:
        accepted = 0
        for _ in range(incoming):
            if self.active_threads < self.threads:
                self.active_threads += 1
                accepted += 1
            elif self.queued_tasks < self.queue_capacity:
                self.queued_tasks += 1
                accepted += 1
            else:
                self.rejected_count += 1
        return accepted

    def drain(self, completed: int) -> None:
        finished = min(self.active_threads, completed)
        self.active_threads -= finished
        # Promote from queue
        from_queue = min(self.queued_tasks, self.threads - self.active_threads)
        self.queued_tasks -= from_queue
        self.active_threads += from_queue


# ==============================================================================
# Simulation Scenarios
# ==============================================================================

def sim_heap_sizing_interactive():
    header("SIMULASI 1: JVM HEAP SIZING & COMPRESSED OOPS CALCULATOR")
    print(f"{WHITE}Formula Fundamental Elasticsearch:{RESET}")
    print(f"  1. {BOLD}Aturan 50% RAM:{RESET} Maksimal 50% fisik RAM untuk Heap, 50% untuk OS Page Cache (Lucene).")
    print(f"  2. {BOLD}Ambang Batas 32GB:{RESET} Hindari alokasi di atas 30.5GB - 31GB agar Compressed OOPs tetap aktif.\n")

    try:
        ram_input = input(f"{YELLOW}Masukkan Total RAM Server Fisik (GB) [default: 64]: {RESET}").strip()
        ram_gb = float(ram_input) if ram_input else 64.0

        suggested_heap = min(30.5, ram_gb * 0.5)
        print(f"{DIM}Rekomendasi default untuk {ram_gb} GB RAM: {suggested_heap:.1f} GB Heap{RESET}")

        heap_input = input(f"{YELLOW}Masukkan Ukuran JVM Heap yang Diuji (GB) [default: {suggested_heap:.1f}]: {RESET}").strip()
        heap_gb = float(heap_input) if heap_input else suggested_heap
    except ValueError:
        print(f"{RED}Input tidak valid. Menggunakan RAM=64GB, Heap=31GB.{RESET}")
        ram_gb, heap_gb = 64.0, 31.0

    config = JVMHeapConfig(total_ram_gb=ram_gb, allocated_heap_gb=heap_gb)
    res = config.analyze()

    print(f"\n{BOLD}HASIL DIAGNOSIS KONFIGURASI HEAP:{RESET}")
    print(f"  • Total Server RAM        : {WHITE}{config.total_ram_gb:.1f} GB{RESET}")
    print(f"  • JVM Heap (-Xms/-Xmx)    : {WHITE}{config.allocated_heap_gb:.1f} GB ({config.allocated_heap_gb/config.total_ram_gb*100:.1f}%){RESET}")
    print(f"  • Lucene Page Cache       : {WHITE}{res['lucene_ram_gb']}{RESET}")
    print(f"  • Status Rasio 50/50      : {res['ratio_status']}")
    print(f"    └─ Detail               : {DIM}{res['ratio_tip']}{RESET}")
    print(f"  • Status Compressed OOPs  : {res['oops_status']}")
    print(f"    └─ Rekomendasi          : {BOLD}{res['recommendation']}{RESET}")

    if heap_gb > 32:
        penalty_ram = heap_gb * 0.4
        print(f"\n{BG_RED}{WHITE}{BOLD} [PENALTY SIMULASI] {RESET}")
        print(f"  Dengan 64-bit uncompressed pointers, Anda kehilangan efektif {penalty_ram:.1f} GB")
        print(f"  akibat ukuran pointer membengkak dari 4 byte menjadi 8 byte pada setiap object header!")


def sim_threadpool_rejections():
    header("SIMULASI 2: BULK WRITE THREAD POOL SATURATION & 429 REJECTION")
    print(f"{WHITE}Simulasi traffic burst pada Write Thread Pool Elasticsearch:{RESET}")
    print(f"  • Thread Pool Size: Cores + 1 (misal 8 cores = 9 threads)")
    print(f"  • Queue Capacity: 1000 tasks (default ES)")
    print(f"  • Efek: Jika antrean penuh, worker melempar {BOLD}EsRejectedExecutionException (HTTP 429){RESET}\n")

    cores = 8
    threads = cores + 1
    queue_cap = 200  # Skala mini untuk observasi cepat
    pool = ThreadPoolState(name="write", threads=threads, queue_capacity=queue_cap)

    print(f"{CYAN}Spesifikasi Node Simulator:{RESET} {cores} CPU Cores | {threads} Threads | Queue Cap: {queue_cap} tasks\n")
    print(f"{'BATCH':<8}{'INCOMING':<10}{'ACTIVE THREADS':<20}{'QUEUE STATUS':<24}{'REJECTED (429)':<15}")
    print("-" * 78)

    random.seed(42)
    total_rejected = 0

    for step in range(1, 11):
        incoming_burst = random.randint(40, 90) if step in [3, 4, 5, 7] else random.randint(10, 30)
        accepted = pool.dispatch(incoming_burst)
        
        # Format status
        q_color = GREEN if pool.queued_tasks < (queue_cap * 0.5) else (YELLOW if pool.queued_tasks < (queue_cap * 0.85) else RED)
        t_str = f"{pool.active_threads}/{pool.threads} " + progress_bar(pool.active_threads, pool.threads, length=8, color=CYAN)
        q_str = f"{pool.queued_tasks}/{pool.queue_capacity} " + progress_bar(pool.queued_tasks, pool.queue_capacity, length=8, color=q_color)
        rej_str = f"{RED}{pool.rejected_count}{RESET}" if pool.rejected_count > 0 else f"{GREEN}0{RESET}"

        print(f"#{step:<7}{incoming_burst:<10}{t_str:<29}{q_str:<33}{rej_str}")

        # Simulate task completion
        completed_rate = random.randint(15, 30)
        pool.drain(completed_rate)
        time.sleep(0.2)

    print("-" * 78)
    if pool.rejected_count > 0:
        print(f"\n{BG_RED}{WHITE}{BOLD} HASIL DIAGNOSIS THREAD POOL: {RESET}")
        print(f"  Total Rejections (HTTP 429) : {RED}{pool.rejected_count} requests{RESET}")
        print(f"  Solusi SRE / Production:")
        print(f"   1. {BOLD}Client-side Backoff:{RESET} Implementasikan Exponential Backoff & Jitter pada client.")
        print(f"   2. {BOLD}Bulk Sizing:{RESET} Kurangi ukuran dokumen per bulk request (rekomendasi: 5MB-15MB per bulk).")
        print(f"   3. {BOLD}Scaling:{RESET} Tambah dedicated ingest/data node atau perbaiki disk I/O (iops bottleneck).")
    else:
        print(f"\n{GREEN}Status Thread Pool Optimal. Tidak ada penolakan antrean 429.{RESET}")


def sim_circuit_breakers_and_gc():
    header("SIMULASI 3: GC OLD-GEN PRESSURE & CIRCUIT BREAKER TRIPPING")
    print(f"{WHITE}Memantau Parent Circuit Breaker (95%) dan Fielddata Circuit Breaker (40%):{RESET}")
    print(f"  Circuit breaker mencegah Node mengalami OutOfMemoryError (OOM Crash)")
    print(f"  dengan membatalkan eksekusi query sebelum heap meluap.\n")

    heap_size_mb = 16384.0  # 16 GB Heap
    parent_breaker = CircuitBreaker("parent", limit_pct=95.0, overhead=1.0)
    fielddata_breaker = CircuitBreaker("fielddata", limit_pct=40.0, overhead=1.03)

    print(f"Simulasi Heap: {BOLD}{heap_size_mb / 1024:.1f} GB{RESET} | Parent Limit: 95% ({heap_size_mb * 0.95 / 1024:.1f} GB)")

    queries = [
        ("Term Query (Cached)", 150.0),
        ("Date Histogram Aggregation (Buckets)", 2200.0),
        ("Unindexed Text Fielddata Sort", 4800.0),
        ("Terms Aggregation Cardinality High", 5100.0),
        ("Heavy Parent-Child Join Query", 3900.0),
        ("Deep Pagination Scroll Request", 2800.0),
    ]

    current_heap_mb = 3500.0  # Baseline runtime objects

    for idx, (q_name, memory_req) in enumerate(queries, 1):
        print(f"\n[{idx}] Mengeksekusi Query: {BOLD}{WHITE}{q_name}{RESET} (Perkiraan Alokasi: {memory_req:.0f} MB)")
        
        # Test Fielddata / Agg limit if applicable
        if "Fielddata" in q_name or "Aggregation" in q_name:
            if not fielddata_breaker.check(heap_size_mb, memory_req):
                print(f"  {BG_YELLOW}{WHITE} [CIRCUIT BREAKER TRIGGERED] {RESET} {YELLOW}Data too large [{fielddata_breaker.name}]{RESET}")
                print(f"  Fielddata breaker tripped! Memory used: {fielddata_breaker.current_used_mb:.1f}MB melampaui 40% Heap.")
                print(f"  {RED}Query dibatalkan dengan aman.{RESET} Node tetap selamat dari JVM crash.")
                continue

        # Test Parent Breaker
        if (current_heap_mb + memory_req) > (heap_size_mb * 0.95):
            print(f"  {BG_RED}{WHITE} [PARENT CIRCUIT BREAKER TRIPPED] {RESET}")
            print(f"  Total projected memory {current_heap_mb + memory_req:.0f} MB > 95% Parent Limit ({heap_size_mb * 0.95:.0f} MB).")
            print(f"  {RED}Elasticsearch status: [parent] Data too large [circuit_breaking_exception].{RESET}")
            break
        else:
            current_heap_mb += memory_req
            fielddata_breaker.current_used_mb += memory_req * 0.4
            used_pct = (current_heap_mb / heap_size_mb) * 100
            bar = progress_bar(current_heap_mb, heap_size_mb, length=25, color=GREEN if used_pct < 75 else RED)
            print(f"  Query sukses. Heap Terpakai: {current_heap_mb:.0f}/{heap_size_mb:.0f} MB {bar}")

        # Simulate Young GC cycle
        if current_heap_mb > 10000.0:
            freed = current_heap_mb * 0.35
            current_heap_mb -= freed
            print(f"  {CYAN}⚡ [Young Gen / G1 Minor GC Occurred]{RESET} Membersihkan objek transien, -{freed:.0f} MB Heap.")


def sim_cluster_diagnostics():
    header("SIMULASI 4: CLUSTER ALLOCATION EXPLAIN & HOT THREADS")
    print(f"{WHITE}Penyelidikan Akar Masalah Status Cluster (Green -> Yellow -> Red):{RESET}\n")

    cluster_states = [
        {
            "status": "GREEN",
            "primaries": 10,
            "replicas": 10,
            "unassigned": 0,
            "cause": "Semua primary shard dan replica shard sukses dialokasikan pada data nodes.",
            "action": "Kondisi sehat normal. Pantau index rate dan disk watermark."
        },
        {
            "status": "YELLOW",
            "primaries": 10,
            "replicas": 7,
            "unassigned": 3,
            "cause": "Primary shards aktif, tetapi 3 replica shard UNASSIGNED karena cluster hanya memiliki 1 Data Node.",
            "action": "Jalankan: GET /_cluster/allocation/explain. Tambahkan node kedua atau turunkan number_of_replicas ke 0."
        },
        {
            "status": "RED",
            "primaries": 8,
            "replicas": 5,
            "unassigned": 4,
            "cause": "2 Primary shards berstatus UNASSIGNED akibat Node failure atau disk melebihi Flood Stage Watermark (95%).",
            "action": "CRITICAL: Segera bebaskan disk space atau restore shard dari snapshot. Index dalam read-only mode!"
        }
    ]

    for item in cluster_states:
        badge = status_badge(item["status"])
        print(f"Status Cluster : {badge}")
        print(f"  • Primary Shards   : {GREEN}{item['primaries']}{RESET}")
        print(f"  • Replica Shards   : {CYAN}{item['replicas']}{RESET}")
        print(f"  • Unassigned Shards: {RED if item['unassigned'] > 0 else GREEN}{item['unassigned']}{RESET}")
        print(f"  • Akar Masalah     : {WHITE}{item['cause']}{RESET}")
        print(f"  • Tindakan Medis   : {BOLD}{YELLOW}{item['action']}{RESET}\n")

    print(f"{BOLD}Simulasi Output API `GET /_nodes/hot_threads`:{RESET}")
    print(f"{DIM}::: {{{{'node-data-01'}}}} {{cpu=94.2%}} [elasticsearch[node-data-01][search][T#4]]{RESET}")
    print(f"{DIM}   org.apache.lucene.index.SegmentCoreReaders.<init>(SegmentCoreReaders.java:120){RESET}")
    print(f"{DIM}   org.apache.lucene.search.IndexSearcher.search(IndexSearcher.java:490){RESET}")
    print(f"  {YELLOW}Diagnosis:{RESET} Terdeteksi pembacaan disk intensif pada segment Lucene. Periksa Page Cache.")


# ==============================================================================
# Interactive CLI Menu
# ==============================================================================

def main():
    while True:
        header("ELASTICSEARCH PERFORMANCE TUNING & DIAGNOSTICS LAB")
        print(f"{WHITE}Pilih modul hands-on yang ingin Anda jalankan:{RESET}")
        print(f"  {BOLD}1.{RESET} Heap Sizing & Compressed OOPs (Aturan 50% & Batas 32GB)")
        print(f"  {BOLD}2.{RESET} Thread Pool Saturation & HTTP 429 Rejection Analysis")
        print(f"  {BOLD}3.{RESET} Memory Circuit Breakers & GC Pressure Simulation")
        print(f"  {BOLD}4.{RESET} Cluster State Diagnostics & Allocation Explain")
        print(f"  {BOLD}5.{RESET} Jalankan Seluruh Pengujian Secara Sekuensial (Full Suite)")
        print(f"  {BOLD}0.{RESET} Keluar (Exit)")

        try:
            choice = input(f"\n{BOLD}{MAGENTA}Masukkan opsi [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{CYAN}Lab dihentikan. Sampai jumpa!{RESET}")
            sys.exit(0)

        if choice == "1":
            sim_heap_sizing_interactive()
        elif choice == "2":
            sim_threadpool_rejections()
        elif choice == "3":
            sim_circuit_breakers_and_gc()
        elif choice == "4":
            sim_cluster_diagnostics()
        elif choice == "5":
            sim_heap_sizing_interactive()
            time.sleep(0.5)
            sim_threadpool_rejections()
            time.sleep(0.5)
            sim_circuit_breakers_and_gc()
            time.sleep(0.5)
            sim_cluster_diagnostics()
        elif choice == "0":
            print(f"{GREEN}Menutup Lab Exercise. Sukses selalu untuk optimasi cluster Anda!{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}Opsi tidak dikenali. Silakan masukkan angka 0 sampai 5.{RESET}")

        input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu utama...{RESET}")


if __name__ == "__main__":
    main()
