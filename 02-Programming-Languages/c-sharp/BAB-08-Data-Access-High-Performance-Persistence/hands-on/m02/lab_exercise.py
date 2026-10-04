#!/usr/bin/env python3
"""
Lab Hands-on: C# Data Access & High-Performance Persistence Deep Dive
Simulasi Arsitektur: EF Core Change Tracker vs Micro-ORM (Dapper) & ADO.NET Connection Pooling.

Materi Teknis yang Dimodelkan:
1. EF Core Change Tracker Mechanics (Snapshotting, Dirty Checking, Unit of Work).
2. Dapper-style Fast Object Materialization (No-Tracking direct mapping).
3. ADO.NET Connection Pool Contention & High-Throughput Leasing.
4. Profiling: Throughput (ops/sec), Allocation overhead, dan State Transition cost.
"""

import sys
import time
import copy
import queue
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Any, Optional

# ==============================================================================
# ANSI Formatting Helper
# ==============================================================================
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    WHITE = "\033[37m"
    BG_DARK = "\033[48;5;235m"

# ==============================================================================
# Domain Model & Entity Tracking State (Mirip System.Data / EF Core)
# ==============================================================================
class EntityState(Enum):
    DETACHED = auto()
    UNCHANGED = auto()
    ADDED = auto()
    MODIFIED = auto()
    DELETED = auto()

@dataclass
class Account:
    id: int
    owner: str
    balance: float
    version: int = 1

    def clone(self) -> 'Account':
        return Account(self.id, self.owner, self.balance, self.version)

@dataclass
class EntityEntry:
    entity: Account
    state: EntityState
    original_values: Dict[str, Any]

# ==============================================================================
# Komponen 1: EF Core-Style DbContext & Change Tracker
# ==============================================================================
class MockDbContext:
    """
    Simulasi DbContext dengan ChangeTracker snapshot-based dirty checking.
    Setiap entity yang di-query akan di-snapshot (memori x2) untuk mendeteksi mutasi.
    """
    def __init__(self):
        self._entries: Dict[int, EntityEntry] = {}
        self.save_count = 0

    def attach_as_unchanged(self, entity: Account):
        # Snapshot state awal (representasi snapshotting di EF Core saat query dimuat)
        snapshot = {
            "owner": entity.owner,
            "balance": entity.balance,
            "version": entity.version
        }
        self._entries[entity.id] = EntityEntry(
            entity=entity,
            state=EntityState.UNCHANGED,
            original_values=snapshot
        )

    def detect_changes(self) -> int:
        """
        EF Core DetectChanges(): Membandingkan field entitas saat ini vs snapshot awal.
        Operasi ini berat secara komputasi O(N) dengan traversal memori tinggi.
        """
        dirty_count = 0
        for entry in self._entries.values():
            if entry.state == EntityState.UNCHANGED:
                e = entry.entity
                snap = entry.original_values
                if e.owner != snap["owner"] or e.balance != snap["balance"] or e.version != snap["version"]:
                    entry.state = EntityState.MODIFIED
                    dirty_count += 1
            elif entry.state == EntityState.MODIFIED:
                dirty_count += 1
        return dirty_count

    def save_changes(self) -> int:
        """Simulasi komit Unit of Work ke underlying persistent store."""
        mutated = self.detect_changes()
        for entry in self._entries.values():
            if entry.state == EntityState.MODIFIED:
                entry.original_values["owner"] = entry.entity.owner
                entry.original_values["balance"] = entry.entity.balance
                entry.original_values["version"] += 1
                entry.entity.version = entry.original_values["version"]
                entry.state = EntityState.UNCHANGED
                self.save_count += 1
        return mutated

# ==============================================================================
# Komponen 2: Dapper-Style Micro-ORM Engine
# ==============================================================================
class DapperMicroOrm:
    """
    Simulasi Micro-ORM Dapper: Menggunakan direct tuple-to-object materialization
    tanpa Change Tracker, tanpa snapshotting, meminimalkan alokasi memori.
    """
    @staticmethod
    def query(raw_rows: List[tuple]) -> List[Account]:
        # Fast path materialization mirip dynamic IL emission pada C# Dapper
        results = []
        for row in raw_rows:
            # Map index-based langsung tanpa alokasi overhead snapshot
            results.append(Account(id=row[0], owner=row[1], balance=row[2], version=row[3]))
        return results

    @staticmethod
    def execute_batch_update(accounts: List[Account], delta: float):
        # Direct batch update command tanpa dirty detection pass
        for acc in accounts:
            acc.balance += delta
            acc.version += 1

# ==============================================================================
# Komponen 3: ADO.NET High-Performance Connection Pool Simulator
# ==============================================================================
class MockDbConnection:
    def __init__(self, conn_id: int):
        self.conn_id = conn_id
        self.is_open = True

    def execute_scalar(self):
        # Simulasi network roundtrip / query processing latency (microseconds)
        time.sleep(0.0001)

class AdoNetConnectionPool:
    """
    Simulasi Connection Pool ADO.NET (Max Pool Size, Lease/Release, Blocking Queue).
    """
    def __init__(self, max_pool_size: int = 10, timeout: float = 1.0):
        self.max_pool_size = max_pool_size
        self.timeout = timeout
        self._pool = queue.Queue(maxsize=max_pool_size)
        self.active_count = 0
        self._lock = threading.Lock()

        for i in range(max_pool_size):
            self._pool.put(MockDbConnection(i + 1))

    def open_connection(self) -> MockDbConnection:
        try:
            conn = self._pool.get(block=True, timeout=self.timeout)
            with self._lock:
                self.active_count += 1
            return conn
        except queue.Empty:
            raise TimeoutError("Connection Pool Exhausted! (Timeout waiting for free connection)")

    def close_connection(self, conn: MockDbConnection):
        with self._lock:
            self.active_count -= 1
        self._pool.put(conn)

# ==============================================================================
# Benchmarks & Workload Simulation
# ==============================================================================
def generate_mock_tabular_data(record_count: int) -> List[tuple]:
    return [
        (i, f"Client_{i:05d}", 1000.0 + (i * 1.5), 1)
        for i in range(1, record_count + 1)
    ]

def run_orm_vs_micro_orm_lab():
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}=== LAB 1: EF Core Tracking vs Dapper Materialization Benchmarks ==={ANSI.RESET}")
    record_count = 50_000
    raw_data = generate_mock_tabular_data(record_count)
    print(f"Dataset Size: {ANSI.YELLOW}{record_count:,} records{ANSI.RESET} raw database rows.")

    # 1. Micro-ORM Materialization (Dapper Style)
    t0 = time.perf_counter()
    dapper_records = DapperMicroOrm.query(raw_data)
    dapper_time = (time.perf_counter() - t0) * 1000

    print(f"\n{ANSI.GREEN}[Dapper Micro-ORM (No Tracking)]{ANSI.RESET}")
    print(f"  • Materialization Time: {ANSI.BOLD}{dapper_time:.2f} ms{ANSI.RESET}")
    print(f"  • Memory Snapshot: {ANSI.YELLOW}None (Zero Tracking Overhead){ANSI.RESET}")

    # 2. EF Core Style Materialization with Tracking
    t0 = time.perf_counter()
    context = MockDbContext()
    for row in raw_data:
        acc = Account(id=row[0], owner=row[1], balance=row[2], version=row[3])
        context.attach_as_unchanged(acc)
    ef_time = (time.perf_counter() - t0) * 1000

    print(f"\n{ANSI.MAGENTA}[EF Core Tracking (Identity Map + Snapshot)]{ANSI.RESET}")
    print(f"  • Materialization + Tracking Time: {ANSI.BOLD}{ef_time:.2f} ms{ANSI.RESET}")
    print(f"  • Tracked Entities Count: {len(context._entries):,}")
    print(f"  • Tracking Overhead Ratio: {ANSI.RED}{ef_time / dapper_time:.2f}x lebih lambat{ANSI.RESET}")

    # 3. Mutate Entities & DetectChanges vs Direct Execution
    print(f"\n{ANSI.CYAN}--- Benchmark Mutasi 10,000 Records ---{ANSI.RESET}")
    # Modifikasi subset
    sample_size = 10_000
    for i in range(1, sample_size + 1):
        context._entries[i].entity.balance += 250.0

    t0 = time.perf_counter()
    mutated_detected = context.save_changes()
    save_time = (time.perf_counter() - t0) * 1000

    print(f"  • EF Core SaveChanges() Time: {ANSI.BOLD}{save_time:.2f} ms{ANSI.RESET}")
    print(f"  • Detected Dirty Entities: {ANSI.GREEN}{mutated_detected:,}{ANSI.RESET}")

    t0 = time.perf_counter()
    DapperMicroOrm.execute_batch_update(dapper_records[:sample_size], 250.0)
    dapper_update_time = (time.perf_counter() - t0) * 1000
    print(f"  • Direct Dapper Batch Execution: {ANSI.BOLD}{dapper_update_time:.2f} ms{ANSI.RESET}")
    print(f"  • Update Speedup: {ANSI.GREEN}{save_time / dapper_update_time:.2f}x lebih cepat{ANSI.RESET}")

def run_connection_pool_lab():
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}=== LAB 2: ADO.NET Connection Pool Contention Simulation ==={ANSI.RESET}")
    pool_size = 8
    worker_threads = 24
    operations_per_worker = 20
    pool = AdoNetConnectionPool(max_pool_size=pool_size, timeout=0.5)

    print(f"Pool Configuration: MaxPoolSize={ANSI.YELLOW}{pool_size}{ANSI.RESET}, Active Workers={ANSI.YELLOW}{worker_threads}{ANSI.RESET}")
    
    success_count = 0
    timeout_count = 0
    counter_lock = threading.Lock()

    def worker_job(worker_id: int):
        nonlocal success_count, timeout_count
        for _ in range(operations_per_worker):
            try:
                conn = pool.open_connection()
                try:
                    conn.execute_scalar()
                    with counter_lock:
                        success_count += 1
                finally:
                    pool.close_connection(conn)
            except TimeoutError:
                with counter_lock:
                    timeout_count += 1

    threads = []
    t0 = time.perf_counter()
    for w in range(worker_threads):
        t = threading.Thread(target=worker_job, args=(w,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    total_time = time.perf_counter() - t0

    total_ops = worker_threads * operations_per_worker
    throughput = total_ops / total_time

    print(f"\nHasil Eksekusi Concurrency:")
    print(f"  • Total Permintaan Koneksi: {total_ops:,}")
    print(f"  • Berhasil: {ANSI.GREEN}{success_count:,}{ANSI.RESET}")
    print(f"  • Timeout / Pool Exhaustion: {ANSI.RED}{timeout_count:,}{ANSI.RESET}")
    print(f"  • Total Waktu: {ANSI.BOLD}{total_time:.3f} s{ANSI.RESET}")
    print(f"  • Throughput: {ANSI.CYAN}{throughput:.2f} ops/sec{ANSI.RESET}")

# ==============================================================================
# Main Entry Point
# ==============================================================================
def main():
    print(f"{ANSI.BOLD}{ANSI.BG_DARK}{ANSI.WHITE} .NET C# HIGH-PERFORMANCE DATA PERSISTENCE LAB RUNNER {ANSI.RESET}")
    print("Memverifikasi arsitektur EF Core, Dapper Micro-ORM, dan ADO.NET Pooler...")

    try:
        run_orm_vs_micro_orm_lab()
        run_connection_pool_lab()
        print(f"\n{ANSI.BOLD}{ANSI.GREEN}✔ SEMUA LAB SELESAI DENGAN STATUS NORMAL (0 FAILURES){ANSI.RESET}\n")
    except Exception as exc:
        print(f"\n{ANSI.RED}Error Fatal: {exc}{ANSI.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()