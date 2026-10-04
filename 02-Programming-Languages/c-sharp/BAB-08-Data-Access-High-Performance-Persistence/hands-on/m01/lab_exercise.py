#!/usr/bin/env python3
"""
Lab Exercise: High-Performance Data Access & Persistence in C# / .NET
Simulasi Arsitektur: ADO.NET vs Dapper vs EF Core (Change Tracker & AsNoTracking)

Konsep C# yang disimulasikan:
1. DbConnection & Connection Pool Management (Min/Max Pool Size, Lease/Release)
2. EF Core Change Tracker State Machine (Detached, Unchanged, Modified, Added)
3. Overhead Query: ADO.NET (Raw) vs Dapper (Micro-ORM) vs EF Core (Full vs AsNoTracking)
4. Batching & Network Round-Trip Reduction (EF Core Batching vs Sequential)
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_BLUE = "\033[94m"
CLR_BG_DARK = "\033[100m"

@dataclass
class OrderEntity:
    id: int
    customer_name: str
    total_amount: float
    status: str
    version: int = 1

@dataclass
class ChangeTrackerEntry:
    entity: OrderEntity
    original_values: Dict[str, any]
    state: str  # Detached, Unchanged, Modified, Added, Deleted

class MockConnectionPool:
    def __init__(self, max_pool_size: int = 5):
        self.max_pool_size = max_pool_size
        self.active_connections = 0
        self.pool: List[int] = list(range(1, max_pool_size + 1))
        self.stats = {"opened": 0, "reused": 0, "waited": 0}

    def open_connection(self) -> int:
        self.stats["opened"] += 1
        if self.pool:
            conn_id = self.pool.pop(0)
            self.active_connections += 1
            self.stats["reused"] += 1
            return conn_id
        else:
            self.stats["waited"] += 1
            # Simulasi pool starvation / wait timeout
            time.sleep(0.04)
            return -1

    def release_connection(self, conn_id: int):
        if conn_id != -1 and conn_id not in self.pool:
            self.pool.append(conn_id)
            self.active_connections = max(0, self.active_connections - 1)

class MockEFDbContext:
    def __init__(self):
        self.change_tracker: Dict[int, ChangeTrackerEntry] = {}

    def attach(self, entity: OrderEntity, state: str = "Unchanged"):
        self.change_tracker[entity.id] = ChangeTrackerEntry(
            entity=entity,
            original_values={"status": entity.status, "total_amount": entity.total_amount},
            state=state
        )

    def detect_changes(self):
        for entry in self.change_tracker.values():
            if entry.state == "Unchanged":
                if (entry.entity.status != entry.original_values["status"] or 
                    entry.entity.total_amount != entry.original_values["total_amount"]):
                    entry.state = "Modified"

    def save_changes(self) -> int:
        self.detect_changes()
        modified_count = 0
        for entry in list(self.change_tracker.values()):
            if entry.state in ("Modified", "Added"):
                modified_count += 1
                entry.state = "Unchanged"
                entry.original_values["status"] = entry.entity.status
                entry.original_values["total_amount"] = entry.entity.total_amount
        return modified_count

def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== {title} ==={CLR_RESET}")

def simulate_data_access_latency():
    print_header("1. BENCHMARK: ADO.NET vs Dapper vs EF Core")
    record_count = 500
    print(f"{CLR_BLUE}Simulasi pembacaan {record_count} entitas Order dari database...{CLR_RESET}\n")

    # 1. ADO.NET (Raw DbDataReader - Zero Materialization Magic, direct ordinals)
    t0 = time.perf_counter()
    time.sleep(0.015)  # Database wire latency
    # Manual while (reader.Read())
    _ = [OrderEntity(i, f"Cust_{i}", 150.0 + (i % 50), "Completed") for i in range(record_count)]
    t_adonet = (time.perf_counter() - t0) * 1000

    # 2. Dapper (Fast Micro-ORM - Cached Dynamic IL Deserializer)
    t0 = time.perf_counter()
    time.sleep(0.015)
    # IL emitted mapper overhead minimal (~1.1x ADO.NET)
    time.sleep(0.003)
    _ = [OrderEntity(i, f"Cust_{i}", 150.0 + (i % 50), "Completed") for i in range(record_count)]
    t_dapper = (time.perf_counter() - t0) * 1000

    # 3. EF Core Full Tracking (DbSet.ToList() + Snapshot & Identity Map)
    t0 = time.perf_counter()
    time.sleep(0.015)
    time.sleep(0.022)  # Change tracker snapshot creation & navigation graph
    _ = [OrderEntity(i, f"Cust_{i}", 150.0 + (i % 50), "Completed") for i in range(record_count)]
    t_ef_tracked = (time.perf_counter() - t0) * 1000

    # 4. EF Core AsNoTracking (Bypass Change Tracker pipeline)
    t0 = time.perf_counter()
    time.sleep(0.015)
    time.sleep(0.006)  # Minimal expression translation overhead
    _ = [OrderEntity(i, f"Cust_{i}", 150.0 + (i % 50), "Completed") for i in range(record_count)]
    t_ef_notracking = (time.perf_counter() - t0) * 1000

    # Print results table
    print(f"{CLR_BOLD}{'Data Access Strategy':<30} | {'Latency (ms)':<15} | {'Heap Allocation':<18} | {'Change Tracker'}{CLR_RESET}")
    print("-" * 82)
    print(f"{CLR_GREEN}{'ADO.NET (DbDataReader)':<30}{CLR_RESET} | {t_adonet:12.2f} ms | {'~120 KB (Baseline)':<18} | {CLR_RED}None{CLR_RESET}")
    print(f"{CLR_GREEN}{'Dapper (Micro-ORM)':<30}{CLR_RESET} | {t_dapper:12.2f} ms | {'~145 KB (+20%)':<18} | {CLR_RED}None{CLR_RESET}")
    print(f"{CLR_MAGENTA}{'EF Core (AsNoTracking)':<30}{CLR_RESET} | {t_ef_notracking:12.2f} ms | {'~210 KB (+75%)':<18} | {CLR_YELLOW}Bypassed{CLR_RESET}")
    print(f"{CLR_YELLOW}{'EF Core (Full Change Tracking)':<30}{CLR_RESET} | {t_ef_tracked:12.2f} ms | {'~580 KB (+380%)':<18} | {CLR_GREEN}Active (Snapshot){CLR_RESET}")

    print(f"\n{CLR_CYAN}Insight Arsitektur C#:{CLR_RESET}")
    print(f" - Gunakan {CLR_BOLD}AsNoTracking(){CLR_RESET} untuk read-only endpoint (CQRS Query side) guna menghemat alokasi memori hingga >60%.")
    print(f" - Gunakan {CLR_BOLD}Dapper{CLR_RESET} untuk latency-critical high-throughput OLTP query.")

def simulate_change_tracker_lifecycle():
    print_header("2. EF CORE CHANGE TRACKER STATE MACHINE")
    context = MockEFDbContext()

    print(f"{CLR_BLUE}Langkah 1: Query entity dari database dan attach ke DbContext (State: Unchanged){CLR_RESET}")
    order = OrderEntity(id=101, customer_name="Alice Smith", total_amount=250.0, status="Pending")
    context.attach(order, state="Unchanged")
    entry = context.change_tracker[order.id]
    print(f" -> Order #{order.id} | Status: {order.status} | EntityState: {CLR_GREEN}{entry.state}{CLR_RESET}")

    print(f"\n{CLR_BLUE}Langkah 2: Mutasi properti secara in-memory (order.status = 'Processing'){CLR_RESET}")
    order.status = "Processing"
    context.detect_changes()
    print(f" -> Change Tracker mendeteksi perbedaan snapshot original vs current values!")
    print(f" -> Order #{order.id} | Original: '{entry.original_values['status']}' -> Current: '{order.status}'")
    print(f" -> EntityState berubah menjadi: {CLR_YELLOW}{entry.state}{CLR_RESET}")

    print(f"\n{CLR_BLUE}Langkah 3: Pemanggilan context.SaveChanges() (Generating UPDATE SQL Statement){CLR_RESET}")
    affected = context.save_changes()
    print(f" -> SQL Generated: {CLR_MAGENTA}UPDATE Orders SET Status = @p0 WHERE Id = @p1;{CLR_RESET}")
    print(f" -> Rows affected: {affected}")
    print(f" -> EntityState kembali ke: {CLR_GREEN}{entry.state}{CLR_RESET}")

def simulate_batching_and_pooling():
    print_header("3. CONNECTION POOLING & BATCHING DISPATCH")
    pool = MockConnectionPool(max_pool_size=3)

    print(f"{CLR_BLUE}Simulasi 5 request bersamaan meminta DbConnection (Max Pool Size = 3):{CLR_RESET}")
    leased_conns = []
    for req_id in range(1, 6):
        cid = pool.open_connection()
        if cid != -1:
            print(f" Request #{req_id}: Mendapatkan Connection ID {CLR_GREEN}#{cid}{CLR_RESET} dari Pool.")
            leased_conns.append(cid)
        else:
            print(f" Request #{req_id}: {CLR_RED}Pool Exhausted! Thread mengalami Block/Wait (Connection Timeout risk){CLR_RESET}")

    print(f"\n{CLR_YELLOW}Mengembalikan koneksi kembali ke Pool (Dispose / using statement)...{CLR_RESET}")
    for cid in leased_conns:
        pool.release_connection(cid)
    print(f"Status Pool: {len(pool.pool)} koneksi siap pakai kembali.")

    print(f"\n{CLR_CYAN}Batching Simulation (EF Core 7+ ExecuteUpdate vs N Sequential Roundtrips):{CLR_RESET}")
    items_count = 100
    # Sequential
    t0 = time.perf_counter()
    time.sleep(0.0003 * items_count)  # latency per roundtrip
    seq_time = (time.perf_counter() - t0) * 1000

    # Batching
    t0 = time.perf_counter()
    time.sleep(0.003)  # single combined batch roundtrip
    batch_time = (time.perf_counter() - t0) * 1000

    print(f" - Sequential (N x Roundtrip): {seq_time:.2f} ms ({items_count} network round-trips)")
    print(f" - Batching (Single Multi-SQL): {batch_time:.2f} ms ({CLR_GREEN}Peningkatan ~{seq_time/max(batch_time, 0.001):.1f}x{CLR_RESET})")

def main():
    while True:
        print(f"\n{CLR_BOLD}{CLR_CYAN}=============================================================={CLR_RESET}")
        print(f"{CLR_BOLD}  .NET / C# DATA ACCESS & PERSISTENCE SIMULATOR (BAB-08)     {CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_CYAN}=============================================================={CLR_RESET}")
        print(f" {CLR_GREEN}1.{CLR_RESET} Benchmark ADO.NET vs Dapper vs EF Core (Tracking/No-Tracking)")
        print(f" {CLR_GREEN}2.{CLR_RESET} EF Core Change Tracker Lifecycle & Snapshot Demo")
        print(f" {CLR_GREEN}3.{CLR_RESET} DbConnection Pooling & SQL Batching Optimization")
        print(f" {CLR_GREEN}4.{CLR_RESET} Jalankan Semua Simulasi Sekaligus")
        print(f" {CLR_RED}5.{CLR_RESET} Keluar")
        print(f"{CLR_CYAN}--------------------------------------------------------------{CLR_RESET}")

        try:
            choice = input(f"{CLR_BOLD}Pilih menu (1-5): {CLR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{CLR_YELLOW}Keluar dari simulasi.{CLR_RESET}")
            break

        if choice == "1":
            simulate_data_access_latency()
        elif choice == "2":
            simulate_change_tracker_lifecycle()
        elif choice == "3":
            simulate_batching_and_pooling()
        elif choice == "4":
            simulate_data_access_latency()
            simulate_change_tracker_lifecycle()
            simulate_batching_and_pooling()
        elif choice == "5":
            print(f"{CLR_GREEN}Terima kasih telah menjalankan simulasi Persistence C#!{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid, silakan coba lagi.{CLR_RESET}")

if __name__ == "__main__":
    main()
