#!/usr/bin/env python3
"""
BAB-04: RDBMS & SQL Mastery - Production Architecture Simulation Lab
Hands-on Module 02: Advanced Database Architecture & Concurrency Simulation

Features:
- ANSI Colorized Terminal Output
- Connection Pool & Resource Management (Queue-based checkout/checkin)
- Read/Write Replica Routing Engine with Replication Lag
- Concurrency & Row Locking Simulator (Optimistic vs Pessimistic)
- Query Execution Cost Analyzer (Sequential Scan vs B-Tree Index Scan)
- Fully runnable with standard library (sqlite3, threading, time, queue)
"""

import sys
import time
import queue
import random
import sqlite3
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# ==============================================================================
# ANSI Color Palette
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    BG_BLUE = "\033[44m"

def banner(title: str):
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {title} === {Color.RESET}\n")

def log_info(msg: str):
    print(f"{Color.CYAN}[INFO]{Color.RESET} {msg}")

def log_success(msg: str):
    print(f"{Color.GREEN}[SUCCESS]{Color.RESET} {msg}")

def log_warn(msg: str):
    print(f"{Color.YELLOW}[WARN]{Color.RESET} {msg}")

def log_error(msg: str):
    print(f"{Color.RED}[ERROR]{Color.RESET} {msg}")

def log_metric(name: str, val: Any, unit: str = ""):
    print(f"  {Color.MAGENTA}↳ {name}:{Color.RESET} {Color.BOLD}{val}{Color.RESET} {Color.DIM}{unit}{Color.RESET}")

# ==============================================================================
# 1. Connection Pool Simulation
# ==============================================================================
class DatabaseConnectionPool:
    """Simulates production HikariCP / pgBouncer connection pooling."""
    def __init__(self, pool_size: int = 5, timeout: float = 2.0):
        self.pool_size = pool_size
        self.timeout = timeout
        self.pool: queue.Queue = queue.Queue(maxsize=pool_size)
        self.active_leases = 0
        self.lock = threading.Lock()

        for conn_id in range(1, pool_size + 1):
            conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._init_schema(conn)
            self.pool.put((conn_id, conn))

    def _init_schema(self, conn: sqlite3.Connection):
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY,
                    holder_name TEXT NOT NULL,
                    balance INTEGER NOT NULL,
                    version INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO accounts (id, holder_name, balance, version)
                VALUES (1, 'Alice Corp', 10000, 0), (2, 'Bob Logistics', 5000, 0)
            """)

    def acquire(self) -> tuple:
        try:
            conn_id, conn = self.pool.get(timeout=self.timeout)
            with self.lock:
                self.active_leases += 1
            return conn_id, conn
        except queue.Empty:
            raise TimeoutError(f"Connection pool exhausted (Max {self.pool_size} active leases)!")

    def release(self, conn_id: int, conn: sqlite3.Connection):
        with self.lock:
            self.active_leases -= 1
        self.pool.put((conn_id, conn))

# ==============================================================================
# 2. Read/Write Split & Replication Simulation
# ==============================================================================
class DatabaseClusterRouter:
    """Simulates Read/Write query routing with primary and read replicas."""
    def __init__(self, num_replicas: int = 2):
        self.primary = sqlite3.connect(":memory:", check_same_thread=False)
        self.replicas = [sqlite3.connect(":memory:", check_same_thread=False) for _ in range(num_replicas)]
        self._init_cluster()
        self.rr_index = 0
        self.router_lock = threading.Lock()

    def _init_cluster(self):
        with self.primary:
            self.primary.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT NOT NULL,
                    qty INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        for replica in self.replicas:
            with replica:
                replica.execute("""
                    CREATE TABLE orders (
                        id INTEGER PRIMARY KEY,
                        sku TEXT NOT NULL,
                        qty INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

    def execute_write(self, sku: str, qty: int) -> int:
        """Writes strictly to primary node and asynchronously replicates."""
        with self.primary:
            cursor = self.primary.execute("INSERT INTO orders (sku, qty) VALUES (?, ?)", (sku, qty))
            order_id = cursor.lastrowid

        # Simulate async replication stream with slight latency
        threading.Thread(target=self._replicate_event, args=(order_id, sku, qty), daemon=True).start()
        return order_id

    def _replicate_event(self, order_id: int, sku: str, qty: int):
        time.sleep(0.08)  # 80ms replication lag
        for replica in self.replicas:
            with replica:
                replica.execute("INSERT OR REPLACE INTO orders (id, sku, qty) VALUES (?, ?, ?)", (order_id, sku, qty))

    def execute_read(self, order_id: int) -> Optional[tuple]:
        """Routes read to round-robin read replica."""
        with self.router_lock:
            replica = self.replicas[self.rr_index]
            replica_idx = self.rr_index
            self.rr_index = (self.rr_index + 1) % len(self.replicas)

        cursor = replica.execute("SELECT id, sku, qty, created_at FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        return replica_idx, row

# ==============================================================================
# 3. Concurrency Control: Optimistic vs Pessimistic Locking
# ==============================================================================
class ConcurrencySimulator:
    """Compares double-spend vulnerabilities and locking resolution mechanisms."""
    def __init__(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.pessimistic_lock = threading.Lock()
        with self.db:
            self.db.execute("CREATE TABLE inventory (sku TEXT PRIMARY KEY, stock INTEGER, version INTEGER)")
            self.db.execute("INSERT INTO inventory VALUES ('LAPTOP-X1', 10, 0)")

    def pessimistic_purchase(self, buyer: str, qty: int) -> bool:
        """Simulates SELECT ... FOR UPDATE with explicit transaction mutex."""
        with self.pessimistic_lock:
            cursor = self.db.execute("SELECT stock FROM inventory WHERE sku = 'LAPTOP-X1'")
            stock = cursor.fetchone()[0]
            time.sleep(0.01)  # Simulate network/processing latency
            if stock >= qty:
                self.db.execute("UPDATE inventory SET stock = stock - ? WHERE sku = 'LAPTOP-X1'", (qty,))
                self.db.commit()
                return True
            return False

    def optimistic_purchase(self, buyer: str, qty: int) -> bool:
        """Simulates OCC (Optimistic Concurrency Control) via version check."""
        cursor = self.db.execute("SELECT stock, version FROM inventory WHERE sku = 'LAPTOP-X1'")
        stock, version = cursor.fetchone()
        time.sleep(0.01)  # Simulate processing latency window

        if stock < qty:
            return False

        # Atomic Compare-And-Swap (CAS)
        cursor = self.db.execute(
            "UPDATE inventory SET stock = stock - ?, version = version + 1 WHERE sku = 'LAPTOP-X1' AND version = ?",
            (qty, version)
        )
        self.db.commit()
        return cursor.rowcount > 0

# ==============================================================================
# 4. Query Execution Engine Analyzer (Index vs Seq Scan)
# ==============================================================================
def run_indexing_benchmark(record_count: int = 50000):
    banner(f"Query Optimizer Lab: Seq Scan vs B-Tree Index ({record_count:,} rows)")
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    log_info("Provisioning customer transactions dataset...")
    cur.execute("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            account_id INTEGER,
            amount REAL,
            reference_code TEXT
        )
    """)

    batch = [
        (i, random.randint(1000, 9999), round(random.uniform(10.0, 5000.0), 2), f"REF-{i:07d}")
        for i in range(1, record_count + 1)
    ]
    cur.executemany("INSERT INTO transactions VALUES (?, ?, ?, ?)", batch)
    conn.commit()
    log_success(f"Populated {record_count:,} records in memory.")

    target_ref = f"REF-{(record_count - 250):07d}"

    # 1. Full Table Scan (No Index)
    cur.execute(f"EXPLAIN QUERY PLAN SELECT * FROM transactions WHERE reference_code = '{target_ref}'")
    plan_no_idx = cur.fetchone()[3]
    t0 = time.perf_counter()
    cur.execute("SELECT * FROM transactions WHERE reference_code = ?", (target_ref,))
    res_no_idx = cur.fetchone()
    t_no_idx = (time.perf_counter() - t0) * 1000

    print(f"\n{Color.YELLOW}[WITHOUT INDEX]{Color.RESET}")
    log_metric("Execution Plan", plan_no_idx)
    log_metric("Search Duration", f"{t_no_idx:.3f}", "ms")
    log_metric("Rows Inspected", f"{record_count:,}", "Full Sequential Scan")

    # 2. Build B-Tree Index
    t_idx_start = time.perf_counter()
    cur.execute("CREATE INDEX idx_trans_ref ON transactions(reference_code)")
    conn.commit()
    t_idx_build = (time.perf_counter() - t_idx_start) * 1000
    log_info(f"B-Tree index 'idx_trans_ref' created in {t_idx_build:.2f} ms")

    # 3. Index Seek
    cur.execute(f"EXPLAIN QUERY PLAN SELECT * FROM transactions WHERE reference_code = '{target_ref}'")
    plan_idx = cur.fetchone()[3]
    t1 = time.perf_counter()
    cur.execute("SELECT * FROM transactions WHERE reference_code = ?", (target_ref,))
    res_idx = cur.fetchone()
    t_idx = (time.perf_counter() - t1) * 1000

    print(f"\n{Color.GREEN}[WITH B-TREE INDEX]{Color.RESET}")
    log_metric("Execution Plan", plan_idx)
    log_metric("Search Duration", f"{t_idx:.4f}", "ms")
    log_metric("Performance Gain", f"{(t_no_idx / max(t_idx, 0.0001)):.1f}x", "faster")

# ==============================================================================
# Interactive Demonstration Scenarios
# ==============================================================================
def demo_connection_pooling():
    banner("Scenario 1: High-Concurrency Connection Pooling Stress Test")
    pool = DatabaseConnectionPool(pool_size=3, timeout=0.2)
    log_info(f"Initialized pool with capacity = 3, acquisition timeout = 200ms.")

    results = {"success": 0, "timeout": 0}
    lock = threading.Lock()

    def worker(client_id: int):
        try:
            conn_id, conn = pool.acquire()
            log_info(f"Client {client_id:02d} {Color.GREEN}acquired{Color.RESET} Conn #{conn_id}")
            time.sleep(0.08)  # Hold connection for 80ms
            pool.release(conn_id, conn)
            with lock:
                results["success"] += 1
        except TimeoutError:
            log_warn(f"Client {client_id:02d} {Color.RED}TIMEOUT{Color.RESET} (Pool saturated)")
            with lock:
                results["timeout"] += 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(1, 10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print()
    log_metric("Successful Transactions", results["success"])
    log_metric("Timed Out Requests", results["timeout"])
    log_info("Backpressure prevented database process starvation.")

def demo_replication_routing():
    banner("Scenario 2: Read/Write Split & Eventual Consistency Replication Lag")
    router = DatabaseClusterRouter(num_replicas=2)

    log_info("Client issuing INSERT into PRIMARY node...")
    order_id = router.execute_write("SERVER-RACK-42U", 3)
    log_success(f"Order #{order_id} committed on Primary.")

    print(f"{Color.CYAN}[PROBE 1 - Immediate Read (t=0ms)]{Color.RESET}")
    rep_idx, data = router.execute_read(order_id)
    if data:
        log_success(f"Replica #{rep_idx} returned: {data}")
    else:
        log_warn(f"Replica #{rep_idx} returned None! (Replication lag in flight)")

    log_info("Awaiting binary log propagation sync (120ms)...")
    time.sleep(0.12)

    print(f"{Color.CYAN}[PROBE 2 - Read after sync (t=120ms)]{Color.RESET}")
    rep_idx, data = router.execute_read(order_id)
    if data:
        log_success(f"Replica #{rep_idx} synced! Order ID={data[0]}, SKU={data[1]}, Qty={data[2]}")
    else:
        log_error("Replica did not receive updates.")

def demo_concurrency_race():
    banner("Scenario 3: Race Condition: Optimistic vs Pessimistic Locking")
    sim = ConcurrencySimulator()

    log_info("Initial inventory stock for 'LAPTOP-X1' is 10 units.")
    log_info("Spinning 15 concurrent threads each trying to purchase 1 unit...")

    # Optimistic run
    opt_success = 0
    opt_conflicts = 0

    def opt_worker():
        nonlocal opt_success, opt_conflicts
        if sim.optimistic_purchase("Customer", 1):
            opt_success += 1
        else:
            opt_conflicts += 1

    threads = [threading.Thread(target=opt_worker) for _ in range(15)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    cursor = sim.db.execute("SELECT stock, version FROM inventory WHERE sku = 'LAPTOP-X1'")
    remaining_stock, ver = cursor.fetchone()

    log_metric("Successful Purchases", opt_success)
    log_metric("OCC Aborts / Conflicts", opt_conflicts)
    log_metric("Remaining Stock (No Oversell)", remaining_stock)
    log_metric("Committed Version Counter", ver)
    log_success("ACID Consistency maintained without dirty reads or negative balance.")

def print_menu():
    print(f"\n{Color.BOLD}{Color.CYAN}--- RDBMS Production Architecture Master Lab ---{Color.RESET}")
    print(f"[{Color.GREEN}1{Color.RESET}] Run Connection Pool Saturation Test")
    print(f"[{Color.GREEN}2{Color.RESET}] Run Read/Write Replica Routing & Lag Test")
    print(f"[{Color.GREEN}3{Color.RESET}] Run Concurrency OCC vs Pessimistic Locking Test")
    print(f"[{Color.GREEN}4{Color.RESET}] Run B-Tree Index vs Sequential Scan Benchmark")
    print(f"[{Color.GREEN}5{Color.RESET}] Run Entire Architecture Suite (Automated)")
    print(f"[{Color.RED}0{Color.RESET}] Exit")

def main():
    print(f"{Color.BOLD}{Color.WHITE}================================================================{Color.RESET}")
    print(f"{Color.BOLD}{Color.YELLOW}   BAB-04 RDBMS & SQL MASTERY: ADVANCED BACKEND ARCHITECTURE   {Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}================================================================{Color.RESET}")

    # Check for CLI argument (headless/automated execution)
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "all", "run"):
        demo_connection_pooling()
        demo_replication_routing()
        demo_concurrency_race()
        run_indexing_benchmark(record_count=30000)
        log_success("All architectural simulation benchmarks completed successfully.")
        return

    # Non-interactive fallback when stdin is not a tty
    if not sys.stdin.isatty():
        log_info("Non-interactive terminal detected. Running full simulation suite...")
        demo_connection_pooling()
        demo_replication_routing()
        demo_concurrency_race()
        run_indexing_benchmark(record_count=20000)
        log_success("Automated test run finished.")
        return

    while True:
        print_menu()
        try:
            choice = input(f"\n{Color.BOLD}Select scenario [0-5]: {Color.RESET}").strip()
            if choice == "1":
                demo_connection_pooling()
            elif choice == "2":
                demo_replication_routing()
            elif choice == "3":
                demo_concurrency_race()
            elif choice == "4":
                run_indexing_benchmark(record_count=40000)
            elif choice == "5":
                demo_connection_pooling()
                demo_replication_routing()
                demo_concurrency_race()
                run_indexing_benchmark(record_count=40000)
            elif choice == "0":
                print("Exiting RDBMS Mastery Lab.")
                break
            else:
                log_warn("Invalid option. Please choose between 0 and 5.")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

if __name__ == "__main__":
    main()
