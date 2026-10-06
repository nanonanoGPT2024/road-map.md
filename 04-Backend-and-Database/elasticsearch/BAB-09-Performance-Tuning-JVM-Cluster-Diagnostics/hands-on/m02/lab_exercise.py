#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Elasticsearch Bab 09 Modul 02
Topik: Performance Tuning, JVM Profiling & Advanced Cluster Diagnostics
Lingkungan: Standalone Simulator Interaktif dengan ANSI Terminal UI (Python 3)
"""

import sys
import time
import random
import dataclasses
from typing import List, Dict, Optional

# ==============================================================================
# Terminal Color & Formatting Definitions
# ==============================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    BG_DARK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


# ==============================================================================
# Model & State Definitions
# ==============================================================================
@dataclasses.dataclass
class NodeState:
    name: str
    role: str
    host_ram_gb: int
    heap_configured_gb: float
    heap_used_pct: float
    jvm_gc_old_count: int
    jvm_gc_old_time_ms: int
    young_gen_pct: float
    old_gen_pct: float
    write_threads_active: int
    write_threads_queue: int
    write_threads_rejected: int
    search_threads_active: int
    search_threads_queue: int
    search_threads_rejected: int
    circuit_breaker_tripped: bool
    status: str = "GREEN"


class ClusterSimulator:
    def __init__(self):
        self.nodes: Dict[str, NodeState] = {
            "es-hot-01": NodeState(
                name="es-hot-01",
                role="data_hot,ingest",
                host_ram_gb=64,
                heap_configured_gb=30.5,
                heap_used_pct=62.0,
                jvm_gc_old_count=12,
                jvm_gc_old_time_ms=1450,
                young_gen_pct=45.0,
                old_gen_pct=68.0,
                write_threads_active=16,
                write_threads_queue=12,
                write_threads_rejected=0,
                search_threads_active=8,
                search_threads_queue=0,
                search_threads_rejected=0,
                circuit_breaker_tripped=False,
                status="GREEN",
            ),
            "es-hot-02": NodeState(
                name="es-hot-02",
                role="data_hot,ingest",
                host_ram_gb=64,
                heap_configured_gb=30.5,
                heap_used_pct=88.5,
                jvm_gc_old_count=48,
                jvm_gc_old_time_ms=8920,
                young_gen_pct=92.0,
                old_gen_pct=87.5,
                write_threads_active=32,
                write_threads_queue=1024,
                write_threads_rejected=142,
                search_threads_active=24,
                search_threads_queue=15,
                search_threads_rejected=3,
                circuit_breaker_tripped=False,
                status="YELLOW",
            ),
            "es-warm-01": NodeState(
                name="es-warm-01",
                role="data_warm",
                host_ram_gb=64,
                heap_configured_gb=31.0,
                heap_used_pct=54.0,
                jvm_gc_old_count=6,
                jvm_gc_old_time_ms=450,
                young_gen_pct=30.0,
                old_gen_pct=58.0,
                write_threads_active=2,
                write_threads_queue=0,
                write_threads_rejected=0,
                search_threads_active=12,
                search_threads_queue=0,
                search_threads_rejected=0,
                circuit_breaker_tripped=False,
                status="GREEN",
            ),
            "es-cold-01": NodeState(
                name="es-cold-01",
                role="data_cold",
                host_ram_gb=32,
                heap_configured_gb=15.5,
                heap_used_pct=42.0,
                jvm_gc_old_count=2,
                jvm_gc_old_time_ms=180,
                young_gen_pct=20.0,
                old_gen_pct=45.0,
                write_threads_active=0,
                write_threads_queue=0,
                write_threads_rejected=0,
                search_threads_active=4,
                search_threads_queue=0,
                search_threads_rejected=0,
                circuit_breaker_tripped=False,
                status="GREEN",
            ),
            "es-master-01": NodeState(
                name="es-master-01",
                role="master",
                host_ram_gb=16,
                heap_configured_gb=8.0,
                heap_used_pct=35.0,
                jvm_gc_old_count=1,
                jvm_gc_old_time_ms=90,
                young_gen_pct=15.0,
                old_gen_pct=38.0,
                write_threads_active=0,
                write_threads_queue=0,
                write_threads_rejected=0,
                search_threads_active=0,
                search_threads_queue=0,
                search_threads_rejected=0,
                circuit_breaker_tripped=False,
                status="GREEN",
            ),
        }


# ==============================================================================
# UI Formatting Helpers
# ==============================================================================
def print_header(title: str) -> None:
    line = "=" * 76
    print(f"\n{TermColor.BRIGHT_CYAN}{TermColor.BOLD}{line}{TermColor.RESET}")
    print(f"{TermColor.BRIGHT_WHITE}{TermColor.BOLD}   {title.upper()}{TermColor.RESET}")
    print(f"{TermColor.BRIGHT_CYAN}{TermColor.BOLD}{line}{TermColor.RESET}\n")


def print_subheader(title: str) -> None:
    print(f"\n{TermColor.BRIGHT_YELLOW}{TermColor.BOLD}--- [ {title} ] ---{TermColor.RESET}")


def print_info(label: str, value: str) -> None:
    print(f"  {TermColor.BOLD}{label:<32}:{TermColor.RESET} {TermColor.CYAN}{value}{TermColor.RESET}")


def print_metric(label: str, val: float, unit: str = "%", warn_thresh: float = 75.0, crit_thresh: float = 85.0) -> None:
    if val >= crit_thresh:
        color = TermColor.BRIGHT_RED + TermColor.BOLD
        tag = "[CRITICAL]"
    elif val >= warn_thresh:
        color = TermColor.BRIGHT_YELLOW
        tag = "[WARNING]"
    else:
        color = TermColor.BRIGHT_GREEN
        tag = "[HEALTHY]"

    bar_len = 24
    filled = int((min(val, 100.0) / 100.0) * bar_len)
    bar = "=" * filled + "-" * (bar_len - filled)
    print(f"  {label:<26}: {color}[{bar}] {val:5.1f}{unit} {tag}{TermColor.RESET}")


def badge_status(status: str) -> str:
    if status == "GREEN":
        return f"{TermColor.BG_GREEN}{TermColor.WHITE}{TermColor.BOLD} GREEN {TermColor.RESET}"
    elif status == "YELLOW":
        return f"{TermColor.BG_YELLOW}{TermColor.BLACK}{TermColor.BOLD} YELLOW {TermColor.RESET}"
    else:
        return f"{TermColor.BG_RED}{TermColor.WHITE}{TermColor.BOLD} RED {TermColor.RESET}"


def simulate_delay(sec: float = 0.5) -> None:
    time.sleep(sec)


# ==============================================================================
# Scenario 1: JVM Heap Sizing & Compressed OOPs Boundary
# ==============================================================================
def lab_jvm_heap_sizing() -> None:
    print_header("LAB 1: Analisis JVM Heap, Compressed OOPs & 50% RAM Rule")
    print(f"{TermColor.ITALIC}Memeriksa konfigurasi alokasi JVM Heap vs Off-Heap OS Page Cache dan threshold 32GB.{TermColor.RESET}\n")

    scenarios = [
        {"ram": 16, "heap": 8.0, "desc": "Dedicated Master Node"},
        {"ram": 64, "heap": 30.5, "desc": "Hot Data Node (Optimal - Zero-based Compressed OOPs)"},
        {"ram": 64, "heap": 32.5, "desc": "Kesalahan Arsitektur: Melewati threshold 32GB"},
        {"ram": 128, "heap": 64.0, "desc": "Kesalahan Fatal: Heap 64GB (Penyebab Full GC STW masif)"},
        {"ram": 64, "heap": 58.0, "desc": "Starvation: Off-heap memory untuk Lucene diabaikan"},
    ]

    for sc in scenarios:
        ram = sc["ram"]
        heap = sc["heap"]
        desc = sc["desc"]

        print(f"{TermColor.BOLD}Skenario:{TermColor.RESET} {TermColor.WHITE}{desc}{TermColor.RESET}")
        print(f"  Host RAM: {ram} GB | Heap Disetel: {heap} GB")

        # Evaluasi Compressed OOPs
        if heap < 32.0:
            oops_status = f"{TermColor.BRIGHT_GREEN}ENABLED (32-bit reference via Compressed OOPs - Hemat RAM 50%){TermColor.RESET}"
        else:
            oops_status = f"{TermColor.BRIGHT_RED}DISABLED (Pointer membesar ke 64-bit murni. Boros RAM 40-50%){TermColor.RESET}"

        # Evaluasi Rasio 50%
        ratio = (heap / ram) * 100
        if ratio > 55.0:
            cache_status = f"{TermColor.BRIGHT_RED}FAIL ({ratio:.1f}% RAM dipakai Heap. Lucene Page Cache tercekik!){TermColor.RESET}"
        elif ratio < 45.0 and ram >= 32:
            cache_status = f"{TermColor.BRIGHT_YELLOW}SUB-OPTIMAL (Heap terlalu kecil untuk node data intensif){TermColor.RESET}"
        else:
            cache_status = f"{TermColor.BRIGHT_GREEN}OPTIMAL (~50% RAM sisa untuk Lucene I/O OS Cache){TermColor.RESET}"

        print(f"  -> Compressed OOPs : {oops_status}")
        print(f"  -> Lucene Cache    : {cache_status}")
        print("-" * 76)
        simulate_delay(0.3)

    print(f"\n{TermColor.BRIGHT_GREEN}{TermColor.BOLD}[Rekomendasi Arsitektur Produksi]:{TermColor.RESET}")
    print("  1. Jangan pernah menyetel JVM Heap > 31GB (Batas aman JVM Compressed OOPs).")
    print("  2. Patuhi aturan 50/50: Maksimal 50% RAM fisik untuk JVM, 50% sisanya untuk OS File System Cache.")
    print("  3. Kunci memory dengan `bootstrap.memory_lock: true` agar OS tidak melakukan swap memory.")


# ==============================================================================
# Scenario 2: JVM Garbage Collection (G1GC vs GC Pauses)
# ==============================================================================
def lab_jvm_gc_profiling(cluster: ClusterSimulator) -> None:
    print_header("LAB 2: Diagnostik JVM Garbage Collection & GC Pause Profiler")
    print(f"{TermColor.ITALIC}Memantau frekuensi Young Gen vs Old Gen GC dan deteksi Stop-The-World (STW) spikes.{TermColor.RESET}\n")

    print(f"{TermColor.BOLD}{'Node Name':<14} {'Heap Used':<12} {'Old Gen %':<12} {'Old GC Count':<14} {'Old GC Time':<14} {'Kondisi JVM'}{TermColor.RESET}")
    print("-" * 76)

    for node in cluster.nodes.values():
        if node.old_gen_pct >= 85.0 or node.jvm_gc_old_time_ms > 5000:
            cond = f"{TermColor.BRIGHT_RED}{TermColor.BOLD}STW RISK / GC THRASHING{TermColor.RESET}"
        elif node.old_gen_pct >= 75.0:
            cond = f"{TermColor.BRIGHT_YELLOW}ELEVATED PRESSURE{TermColor.RESET}"
        else:
            cond = f"{TermColor.BRIGHT_GREEN}STABLE (G1GC Nominal){TermColor.RESET}"

        print(f"{node.name:<14} {node.heap_used_pct:5.1f}%       {node.old_gen_pct:5.1f}%       {node.jvm_gc_old_count:<14} {node.jvm_gc_old_time_ms:<10} ms {cond}")

    print("\n" + "=" * 76)
    print(f"{TermColor.BRIGHT_YELLOW}{TermColor.BOLD}Analisis Mendalam Node: es-hot-02{TermColor.RESET}")
    target = cluster.nodes["es-hot-02"]
    print_metric("Heap Utilization", target.heap_used_pct, "%", 75.0, 85.0)
    print_metric("Old Generation Occupancy", target.old_gen_pct, "%", 75.0, 85.0)
    print_metric("Young Generation Occupancy", target.young_gen_pct, "%", 75.0, 85.0)

    print(f"\n{TermColor.RED}{TermColor.BOLD}[TEMUAN DIAGNOSTIK]:{TermColor.RESET}")
    print(f"  Total Waktu Old GC STW: {TermColor.BRIGHT_RED}{target.jvm_gc_old_time_ms} ms{TermColor.RESET} dalam {target.jvm_gc_old_count} siklus.")
    print("  Penyebab: Agregasi bucket besar atau batch indexing berukuran jumbo menahan objek di Old Gen.")
    print(f"  Dampak: Node berisiko terlempar dari quorum cluster jika STW GC > discovery.zen.fd.ping_timeout (biasanya 30 detik)!")


# ==============================================================================
# Scenario 3: Thread Pool Saturation & Rejections Diagnostics
# ==============================================================================
def lab_threadpool_diagnostics(cluster: ClusterSimulator) -> None:
    print_header("LAB 3: Thread Pool Saturation & EsRejectedExecutionException")
    print(f"{TermColor.ITALIC}Mendiagnosis antrean Write (Indexing) dan Search Thread Pool beserta rejeksi tugas.{TermColor.RESET}\n")

    print(f"{TermColor.BOLD}{'Node Name':<14} {'Write Active':<14} {'Write Queue':<14} {'Write Rejected':<16} {'Status Rejeksi'}{TermColor.RESET}")
    print("-" * 76)

    for node in cluster.nodes.values():
        rej_count = node.write_threads_rejected
        if rej_count > 0:
            rej_status = f"{TermColor.BRIGHT_RED}{TermColor.BOLD}REJECTING REQUESTS!{TermColor.RESET}"
        elif node.write_threads_queue > 500:
            rej_status = f"{TermColor.BRIGHT_YELLOW}QUEUE SATURATION{TermColor.RESET}"
        else:
            rej_status = f"{TermColor.BRIGHT_GREEN}OPTIMAL{TermColor.RESET}"

        print(f"{node.name:<14} {node.write_threads_active:<14} {node.write_threads_queue:<14} {rej_count:<16} {rej_status}")

    print("\n" + "=" * 76)
    print(f"{TermColor.BRIGHT_CYAN}{TermColor.BOLD}Simulasi Lonjakan Beban Tulis (Bulk Ingestion Spike):{TermColor.RESET}")
    print("  Klien mengirim 5,000 dokumen/detik ke `es-hot-02` tanpa exponential backoff...")
    simulate_delay(0.4)

    print(f"\n{TermColor.BRIGHT_RED}{TermColor.BOLD}[LOG ERROR SIMULASI PADA CLIENT]:{TermColor.RESET}")
    err_msg = (
        'org.elasticsearch.common.util.concurrent.EsRejectedExecutionException: '
        'rejected execution of processing of [bulk] on QueueResizingEsThreadPoolExecutor['
        'name = es-hot-02/write, queue capacity = 1024, active count = 32, completed = 948128, rejected = 142]'
    )
    print(f"{TermColor.DIM}{err_msg}{TermColor.RESET}\n")

    print(f"{TermColor.BRIGHT_GREEN}{TermColor.BOLD}[Solusi Engineering & Mitigasi]:{TermColor.RESET}")
    print("  1. JANGAN menaikkan `thread_pool.write.queue_size` secara sembarangan (menyebabkan OOM).")
    print("  2. Implementasikan exponential backoff retry di sisi application ingest client.")
    print("  3. Periksa disk I/O bottleneck (iowait) yang memperlambat fsync flush ke Lucene commit point.")


# ==============================================================================
# Scenario 4: Circuit Breaker Diagnostics & Memory Protection
# ==============================================================================
def lab_circuit_breaker_diagnostics(cluster: ClusterSimulator) -> None:
    print_header("LAB 4: Circuit Breaker Hierarchy & Real Memory Protection")
    print(f"{TermColor.ITALIC}Simulasi batas Parent, Fielddata, Request, dan In-Flight Circuit Breakers.{TermColor.RESET}\n")

    breakers = [
        {"name": "Parent Breaker", "setting": "indices.breaker.total.use_real_memory", "limit": "95% Heap", "used": "89%", "tripped": False},
        {"name": "Fielddata Breaker", "setting": "indices.breaker.fielddata.limit", "limit": "40% Heap", "used": "22%", "tripped": False},
        {"name": "Request Breaker", "setting": "indices.breaker.request.limit", "limit": "60% Heap", "used": "58%", "tripped": False},
        {"name": "In-Flight Breaker", "setting": "network.breaker.inflight_requests.limit", "limit": "100% Heap", "used": "31%", "tripped": False},
        {"name": "Accounting Breaker", "setting": "indices.breaker.accounting.limit", "limit": "100% Heap", "used": "44%", "tripped": False},
    ]

    for b in breakers:
        print_info(b["name"], f"Limit: {b['limit']} | Setting: {b['setting']}")
        print(f"    Penggunaan Saat Ini : {TermColor.CYAN}{b['used']}{TermColor.RESET}")
        print(f"    Status Proteksi     : {TermColor.BRIGHT_GREEN}ARMED & ACTIVE{TermColor.RESET}\n")

    print(f"{TermColor.BRIGHT_YELLOW}{TermColor.BOLD}Uji Coba: Menjalankan High-Cardinality Terms Aggregation pada Field 'raw_user_agent'{TermColor.RESET}")
    print("  Menghitung estimasi alokasi memory request...")
    simulate_delay(0.5)

    print(f"\n{TermColor.BRIGHT_RED}{TermColor.BOLD}[CIRCUIT BREAKER TRIPPED!]:{TermColor.RESET}")
    print(f"{TermColor.RED}org.elasticsearch.common.breaker.CircuitBreakingException: [parent] Data too large, "
          f"data for [<reused_arrays>] would be [30921852000/28.7gb], which is larger than the threshold of [30601641984/28.5gb]{TermColor.RESET}")

    print(f"\n{TermColor.BRIGHT_GREEN}{TermColor.BOLD}[Poin Penting Arsitektur]:{TermColor.RESET}")
    print("  Circuit Breaker BUKAN kegagalan, melainkan sistem penyelamat yang sengaja membatalkan")
    print("  query berat sebelum Elasticsearch tumbang akibat Java OutOfMemoryError (OOM Crash).")


# ==============================================================================
# Scenario 5: Full Automated Cluster Health & Tuning Remediation
# ==============================================================================
def lab_automated_remediation(cluster: ClusterSimulator) -> None:
    print_header("LAB 5: Automated Cluster Diagnostic & Self-Healing Remediation")
    print(f"{TermColor.ITALIC}Menjalankan prosedur audit otomatis dan menerapkan tuning parameter.{TermColor.RESET}\n")

    steps = [
        "1. Memeriksa status unassigned shards & disk watermarks...",
        "2. Menyesuaikan refresh_interval dari 1s ke 30s untuk indeks ingest besar...",
        "3. Mengaktifkan adaptive replica selection (cluster.routing.use_adaptive_replica_selection: true)...",
        "4. Menjalankan warm segment merge (forcemerge max_num_segments=1) pada indeks read-only...",
        "5. Mengatur routing index tiering (hot -> warm -> cold lifecycle)...",
    ]

    for step in steps:
        print(f"{TermColor.CYAN}{step}{TermColor.RESET}")
        simulate_delay(0.3)
        print(f"   {TermColor.BRIGHT_GREEN}[SUCCESS] Konfigurasi terverifikasi.{TermColor.RESET}")

    # Update state simulasi
    target = cluster.nodes["es-hot-02"]
    target.write_threads_queue = 45
    target.write_threads_rejected = 0
    target.heap_used_pct = 68.0
    target.old_gen_pct = 65.0
    target.status = "GREEN"

    print(f"\n{TermColor.BRIGHT_GREEN}{TermColor.BOLD}HASIL DIAGNOSTIK AKHIR:{TermColor.RESET}")
    print(f"  Cluster Health : {badge_status('GREEN')}")
    print(f"  Node es-hot-02 : {badge_status('GREEN')} (Heap turun ke 68.0%, Queue 45, Rejection = 0)")


# ==============================================================================
# Main Interactive Menu & CLI Entrypoint
# ==============================================================================
def print_banner() -> None:
    banner = f"""{TermColor.BRIGHT_CYAN}{TermColor.BOLD}
  ============================================================================
  *  ELASTICSEARCH HIGH PERFORMANCE & CLUSTER DIAGNOSTICS LAB (BAB 09)      *
  *  Penyusun: Cloud & Big Data Infrastructure Architecture Series           *
  ============================================================================{TermColor.RESET}"""
    print(banner)


def show_menu() -> None:
    print(f"\n{TermColor.BRIGHT_WHITE}{TermColor.BOLD}PILIHAN MODUL DIAGNOSTIK & SIMULASI INTERAKTIF:{TermColor.RESET}")
    print(f"  {TermColor.BRIGHT_CYAN}[1]{TermColor.RESET} JVM Heap Sizing, Compressed OOPs & 50% RAM Rule")
    print(f"  {TermColor.BRIGHT_CYAN}[2]{TermColor.RESET} Garbage Collection (G1GC) & Stop-The-World (STW) Pause Profiler")
    print(f"  {TermColor.BRIGHT_CYAN}[3]{TermColor.RESET} Thread Pool Saturation & EsRejectedExecutionException")
    print(f"  {TermColor.BRIGHT_CYAN}[4]{TermColor.RESET} Circuit Breaker Tripping & Real Memory Protection")
    print(f"  {TermColor.BRIGHT_CYAN}[5]{TermColor.RESET} Jalankan Audit & Remediasi Cluster Otomatis (Full Suite)")
    print(f"  {TermColor.BRIGHT_CYAN}[6]{TermColor.RESET} Tampilkan Ringkasan Status Node Cluster Saat Ini")
    print(f"  {TermColor.BRIGHT_RED}[0]{TermColor.RESET} Keluar (Exit Lab)")


def display_cluster_summary(cluster: ClusterSimulator) -> None:
    print_header("Ringkasan Status Node & Alokasi Resource Cluster")
    print(f"{TermColor.BOLD}{'Node Name':<14} {'Role':<18} {'RAM':<8} {'Heap':<8} {'Heap %':<10} {'Status'}{TermColor.RESET}")
    print("-" * 76)
    for n in cluster.nodes.values():
        print(f"{n.name:<14} {n.role:<18} {n.host_ram_gb:<2}GB    {n.heap_configured_gb:<4.1f}GB  {n.heap_used_pct:<5.1f}%    {badge_status(n.status)}")


def run_interactive():
    cluster = ClusterSimulator()
    print_banner()

    # Jika berjalan dalam mode non-interaktif (piped/CI/test), jalankan semua pengujian secara berurutan
    if not sys.stdin.isatty():
        print(f"\n{TermColor.BRIGHT_YELLOW}[Non-Interactive Terminal Terdeteksi]: Menjalankan Semua Skenario Otomatis...{TermColor.RESET}")
        display_cluster_summary(cluster)
        lab_jvm_heap_sizing()
        lab_jvm_gc_profiling(cluster)
        lab_threadpool_diagnostics(cluster)
        lab_circuit_breaker_diagnostics(cluster)
        lab_automated_remediation(cluster)
        print(f"\n{TermColor.BRIGHT_GREEN}[LAB FINISHED]: Semua pengujian performa selesai dengan sukses.{TermColor.RESET}\n")
        return

    while True:
        show_menu()
        try:
            choice = input(f"\n{TermColor.BRIGHT_WHITE}Pilih modul [0-6]: {TermColor.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{TermColor.YELLOW}Sesi lab dihentikan oleh pengguna.{TermColor.RESET}")
            break

        if choice == "1":
            lab_jvm_heap_sizing()
        elif choice == "2":
            lab_jvm_gc_profiling(cluster)
        elif choice == "3":
            lab_threadpool_diagnostics(cluster)
        elif choice == "4":
            lab_circuit_breaker_diagnostics(cluster)
        elif choice == "5":
            lab_automated_remediation(cluster)
        elif choice == "6":
            display_cluster_summary(cluster)
        elif choice == "0":
            print(f"\n{TermColor.BRIGHT_GREEN}Terima kasih telah menyelesaikan Lab Performance Tuning Elasticsearch!{TermColor.RESET}\n")
            break
        else:
            print(f"{TermColor.BRIGHT_RED}Pilihan tidak valid. Silakan masukkan angka 0 sampai 6.{TermColor.RESET}")


if __name__ == "__main__":
    run_interactive()
