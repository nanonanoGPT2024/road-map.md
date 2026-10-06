#!/usr/bin/env python3
"""
Lab Exercise: Next.js Database Integration, Connection Pooling & Edge Storage Simulator
Module: BAB-08-Integrasi-Database-Connection-Pooling-dan-Edge-Storage (Modul 01)

Simulasi teknis konsep arsitektur database pada Next.js:
1. Singleton Client Pattern (Mencegah HMR Connection Leak pada development).
2. Serverless Function Spike vs PostgreSQL max_connections limit.
3. Connection Pooler (PgBouncer Transaction Pooling / Serverless Proxy).
4. Edge Runtime DB Access & Edge KV Storage Latency Benchmark.
"""

import sys
import time
import random
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# ANSI Terminal Colors
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
BG_GREEN = "\033[42m"
BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{CYAN}{'=' * 78}{RESET}")
    print(f"{BOLD}{WHITE}>>> {title}{RESET}")
    print(f"{CYAN}{'=' * 78}{RESET}")


def subheader(title: str) -> None:
    print(f"\n{BOLD}{YELLOW}[+] {title}{RESET}")


@dataclass
class DatabaseEngine:
    max_connections: int = 20
    active_connections: int = 0
    total_queries: int = 0
    rejected_connections: int = 0

    def connect(self) -> bool:
        if self.active_connections >= self.max_connections:
            self.rejected_connections += 1
            return False
        self.active_connections += 1
        return True

    def disconnect(self) -> None:
        if self.active_connections > 0:
            self.active_connections -= 1

    def execute_query(self, cost_ms: float = 25.0) -> None:
        self.total_queries += 1
        time.sleep(cost_ms / 1000.0)


# -----------------------------------------------------------------------------
# 1. Next.js HMR Singleton Client Demonstration
# -----------------------------------------------------------------------------
class NextDevHMRSimulation:
    def __init__(self, db: DatabaseEngine):
        self.db = db
        self.global_prisma_singleton: Optional[object] = None

    def reload_module_leaky(self) -> None:
        """Simulates module re-evaluation without globalThis singleton"""
        # Setiap file save/HMR membuat instance PrismaClient baru
        new_instance = object()
        if self.db.connect():
            pass

    def reload_module_safe(self) -> None:
        """Simulates Next.js globalThis.prisma pattern"""
        # globalThis.prisma = globalThis.prisma ?? new PrismaClient()
        if self.global_prisma_singleton is None:
            self.global_prisma_singleton = object()
            self.db.connect()


def run_hmr_leak_simulation() -> None:
    header("SKENARIO 1: Next.js Fast Refresh (HMR) & Connection Leak")
    print(
        f"{DIM}Pada 'next dev', setiap kali file Server Component / API Route disimpan,{RESET}\n"
        f"{DIM}modul dievaluasi ulang. Tanpa 'globalThis' singleton, koneksi baru terbentuk terus.{RESET}\n"
    )

    db_leak = DatabaseEngine(max_connections=10)
    sim_leak = NextDevHMRSimulation(db_leak)

    print(f"{BOLD}A. Menjalankan 15x Code Save (HMR) TANPA Singleton Pattern:{RESET}")
    for i in range(1, 16):
        prev = db_leak.active_connections
        sim_leak.reload_module_leaky()
        curr = db_leak.active_connections
        if curr > prev:
            print(
                f"  Save #{i:02d}: {GREEN}+1 new PrismaClient(){RESET} -> Pool: {curr}/{db_leak.max_connections}"
            )
        else:
            print(
                f"  Save #{i:02d}: {BG_RED}{WHITE} FATAL {RESET} {RED}Error: Too many connections! (max: {db_leak.max_connections}){RESET}"
            )
        time.sleep(0.04)

    print(
        f"\n  Hasil: Active Connections = {RED}{db_leak.active_connections}/{db_leak.max_connections}{RESET} "
        f"| Rejected Requests = {RED}{db_leak.rejected_connections}{RESET}"
    )

    db_safe = DatabaseEngine(max_connections=10)
    sim_safe = NextDevHMRSimulation(db_safe)

    print(
        f"\n{BOLD}B. Menjalankan 15x Code Save (HMR) DENGAN Singleton Pattern (globalThis):{RESET}"
    )
    for i in range(1, 16):
        sim_safe.reload_module_safe()
        print(
            f"  Save #{i:02d}: {CYAN}Re-used globalThis.prisma{RESET} -> Pool: {GREEN}{db_safe.active_connections}/{db_safe.max_connections}{RESET}"
        )
        time.sleep(0.02)

    print(
        f"\n{GREEN}[OK] Singleton pattern menjaga pool stabil pada 1 koneksi terlepas dari frekuensi HMR.{RESET}"
    )


# -----------------------------------------------------------------------------
# 2. Serverless Spikes vs Connection Pooler (PgBouncer)
# -----------------------------------------------------------------------------
async def simulate_serverless_request(
    req_id: int,
    db: DatabaseEngine,
    use_pooler: bool,
    metrics: Dict[str, int],
) -> None:
    # Simulasi cold start & lambda execution
    await asyncio.sleep(random.uniform(0.01, 0.05))

    if not use_pooler:
        # Direct DB Connection per Lambda
        connected = db.connect()
        if not connected:
            metrics["failed"] += 1
            return

        # Query execution
        await asyncio.sleep(0.06)
        db.disconnect()
        metrics["success"] += 1
    else:
        # PgBouncer Transaction Pooling Mode
        # Banyak lambdas antri di PgBouncer pool yang terkontrol
        retries = 3
        acquired = False
        for _ in range(retries):
            if db.connect():
                acquired = True
                break
            await asyncio.sleep(0.02)

        if not acquired:
            metrics["failed"] += 1
            return

        # Fast transaction query
        await asyncio.sleep(0.02)
        db.disconnect()
        metrics["success"] += 1


async def run_serverless_concurrency_bench(use_pooler: bool, total_lambdas: int = 50) -> None:
    pool_type = "PgBouncer / Accelerate (Pooling)" if use_pooler else "Direct PostgreSQL (No Pooler)"
    subheader(f"Simulasi 50 Konkuren Serverless Function: {pool_type}")

    db = DatabaseEngine(max_connections=15)
    metrics = {"success": 0, "failed": 0}

    start = time.perf_counter()
    tasks = [
        simulate_serverless_request(i, db, use_pooler, metrics)
        for i in range(total_lambdas)
    ]
    await asyncio.gather(*tasks)
    elapsed = (time.perf_counter() - start) * 1000.0

    success_rate = (metrics["success"] / total_lambdas) * 100.0
    color = GREEN if success_rate >= 90.0 else RED

    print(f"  Total Lambda Requests : {WHITE}{total_lambdas}{RESET}")
    print(f"  Postgres max_conn     : {WHITE}{db.max_connections}{RESET}")
    print(f"  Berhasil Dilayani     : {GREEN}{metrics['success']}{RESET}")
    print(f"  Gagal (Pool Exhausted): {RED}{metrics['failed']}{RESET}")
    print(f"  Success Rate          : {color}{success_rate:.1f}%{RESET}")
    print(f"  Total Duration        : {CYAN}{elapsed:.2f} ms{RESET}")


# -----------------------------------------------------------------------------
# 3. Edge Runtime vs Node.js Runtime Storage Latency
# -----------------------------------------------------------------------------
@dataclass
class LatencyProfile:
    source: str
    target: str
    network_latency_ms: float
    query_latency_ms: float

    @property
    def total_latency_ms(self) -> float:
        return self.network_latency_ms + self.query_latency_ms


def run_edge_storage_benchmark() -> None:
    header("SKENARIO 3: Next.js Edge Runtime Storage & Latency Benchmark")
    print(
        f"{DIM}Perbandingan arsitektur akses data dari user di Jakarta:{RESET}\n"
        f"1. Node.js SSR Server (US-East) -> Direct PostgreSQL (US-East)\n"
        f"2. Edge API Route (Sin-1 / CGK) -> Direct TCP Postgres (US-East) [Koneksi TCP jauh]\n"
        f"3. Edge API Route (Sin-1 / CGK) -> Edge KV / Redis Cache (Edge-Replicated)\n"
    )

    profiles = [
        LatencyProfile("Next.js Server (us-east-1)", "PostgreSQL (us-east-1)", 1.2, 14.5),
        LatencyProfile("Next.js Edge (Jakarta cgk1)", "PostgreSQL (us-east-1)", 218.4, 15.0),
        LatencyProfile("Next.js Edge (Jakarta cgk1)", "Vercel KV / Upstash (Global Edge)", 4.8, 1.8),
    ]

    print(
        f"{BOLD}{WHITE}{'Arsitektur Akses Data':<42} | {'Network RTT':<13} | {'Execution':<11} | {'Total Latency':<12}{RESET}"
    )
    print("-" * 88)

    for p in profiles:
        tot = p.total_latency_ms
        if tot < 20.0:
            badge = f"{BG_GREEN}{WHITE} FAST {RESET}"
            tot_str = f"{GREEN}{tot:6.2f} ms{RESET}"
        elif tot < 100.0:
            badge = f"{BG_BLUE}{WHITE} OK   {RESET}"
            tot_str = f"{YELLOW}{tot:6.2f} ms{RESET}"
        else:
            badge = f"{BG_RED}{WHITE} SLOW {RESET}"
            tot_str = f"{RED}{tot:6.2f} ms{RESET}"

        print(
            f"{p.source:<42} | {p.network_latency_ms:6.2f} ms    | {p.query_latency_ms:5.2f} ms    | {tot_str}  {badge}"
        )

    print(
        f"\n{YELLOW}[Insight Arsitektural Next.js]:{RESET}\n"
        f"- Edge Runtime tidak boleh query langsung ke database relational lintas benua tanpa connection pooler / read replica lokal.\n"
        f"- Gunakan Edge Storage (KV, Blob, Upstash) untuk data cache cepat di edge PoP terdekat dengan client.\n"
    )


# -----------------------------------------------------------------------------
# 4. Interactive Command-Line Menu Loop
# -----------------------------------------------------------------------------
def display_summary() -> None:
    print(f"\n{BOLD}{MAGENTA}=== KESIMPULAN KONSEP BAB-08 NEXT.JS DATABASE INTEGRATION ==={RESET}")
    print(f"1. {BOLD}Prisma/Drizzle Singleton:{RESET} Hindari kebocoran koneksi saat HMR dev mode.")
    print(f"2. {BOLD}Serverless Pooling:{RESET} Wajib gunakan PgBouncer / Neon Serverless Driver / Prisma Accelerate.")
    print(f"3. {BOLD}Edge Constraints:{RESET} Edge runtime tidak mendukung driver TCP raw standard; gunakan HTTP/WS proxy.")
    print(f"4. {BOLD}Edge Storage:{RESET} Simpan session dan read-heavy metadata pada Edge KV/Cache untuk ultra-low latency.")


def print_menu() -> None:
    print(f"\n{BOLD}{WHITE}--- Next.js Database & Edge Simulator ---{RESET}")
    print(f" [{CYAN}1{RESET}] Uji Fast Refresh (HMR) Connection Leaks (Leaky vs Singleton)")
    print(f" [{CYAN}2{RESET}] Uji Serverless Spike (50 Lambda Concurrent Requests vs Pooler)")
    print(f" [{CYAN}3{RESET}] Uji Edge Storage vs Cross-Continental DB Latency")
    print(f" [{CYAN}4{RESET}] Jalankan Semua Skenario Berurutan (Automated Full Lab)")
    print(f" [{CYAN}q{RESET}] Keluar dari Simulator")


def main() -> None:
    print(f"{BOLD}{BG_BLUE}{WHITE} NEXT.JS DATABASE, POOLING & EDGE STORAGE LAB SIMULATOR {RESET}")
    print(f"{DIM}Platform Pembelajaran Interaktif Arsitektur Backend Next.js App Router{RESET}")

    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_hmr_leak_simulation()
        asyncio.run(run_serverless_concurrency_bench(use_pooler=False))
        asyncio.run(run_serverless_concurrency_bench(use_pooler=True))
        run_edge_storage_benchmark()
        display_summary()
        return

    while True:
        print_menu()
        try:
            choice = input(f"\n{BOLD}Pilih opsi [1-4, q]: {RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Keluar dari program.{RESET}")
            break

        if choice == "1":
            run_hmr_leak_simulation()
        elif choice == "2":
            asyncio.run(run_serverless_concurrency_bench(use_pooler=False))
            asyncio.run(run_serverless_concurrency_bench(use_pooler=True))
        elif choice == "3":
            run_edge_storage_benchmark()
        elif choice == "4":
            run_hmr_leak_simulation()
            asyncio.run(run_serverless_concurrency_bench(use_pooler=False))
            asyncio.run(run_serverless_concurrency_bench(use_pooler=True))
            run_edge_storage_benchmark()
            display_summary()
        elif choice in ("q", "quit", "exit"):
            print(f"{GREEN}Terima kasih telah menjalankan lab Next.js Database Integration.{RESET}")
            break
        else:
            print(f"{RED}Opsi tidak valid. Silakan pilih 1, 2, 3, 4, atau q.{RESET}")


if __name__ == "__main__":
    main()
