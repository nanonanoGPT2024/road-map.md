#!/usr/bin/env python3
"""
Lab Exercise M01: Java Data Persistence, ORM & Database Performance Tuning Simulator
Fokus Pembelajaran:
1. HikariCP Connection Pool Simulation (Borrow, Return, Leak Detection)
2. JPA/Hibernate EntityManager & First-Level Cache (Persistence Context, Dirty Checking)
3. N+1 Select Problem vs JOIN FETCH / Batch Fetching Optimization
4. Query Execution Plan (Index Scan vs Full Table Scan) & Execution Metrics
"""

import sys
import time
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 72}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}>>> {title.upper()} <<<{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 72}{CLR_RESET}")


def sub_header(subtitle: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_YELLOW}--- {subtitle} ---{CLR_RESET}")


def success_msg(msg: str) -> None:
    print(f"{CLR_GREEN}[+] {msg}{CLR_RESET}")


def info_msg(msg: str) -> None:
    print(f"{CLR_BLUE}[*] {msg}{CLR_RESET}")


def warn_msg(msg: str) -> None:
    print(f"{CLR_YELLOW}[!] {msg}{CLR_RESET}")


def alert_msg(msg: str) -> None:
    print(f"{CLR_RED}[!] {msg}{CLR_RESET}")


# ==============================================================================
# 1. HIKARICP CONNECTION POOL SIMULATOR
# ==============================================================================
class MockConnection:
    def __init__(self, conn_id: int):
        self.conn_id = conn_id
        self.in_use = False
        self.borrowed_at = 0.0

    def query(self, sql: str) -> str:
        return f"Executing on Conn-{self.conn_id}: {sql}"


class HikariPoolSimulator:
    def __init__(self, max_size: int = 3, leak_detection_ms: float = 500.0):
        self.max_size = max_size
        self.leak_detection_ms = leak_detection_ms
        self.pool: List[MockConnection] = [MockConnection(i + 1) for i in range(max_size)]
        self.borrow_counter = 0

    def get_connection(self) -> Optional[MockConnection]:
        for conn in self.pool:
            if not conn.in_use:
                conn.in_use = True
                conn.borrowed_at = time.time() * 1000
                self.borrow_counter += 1
                success_msg(f"Pool: Connection #{conn.conn_id} dipinjam (Active: {self.get_active_count()}/{self.max_size})")
                return conn
        alert_msg("Pool Exceeded! HikariPool-1 - Connection is not available, request timed out after 30000ms.")
        return None

    def release_connection(self, conn: MockConnection) -> None:
        elapsed = (time.time() * 1000) - conn.borrowed_at
        conn.in_use = False
        if elapsed > self.leak_detection_ms:
            warn_msg(f"Apparent connection leak detected on Conn-{conn.conn_id}! Held for {elapsed:.1f}ms (> threshold {self.leak_detection_ms}ms)")
        info_msg(f"Pool: Connection #{conn.conn_id} dikembalikan ke pool.")

    def get_active_count(self) -> int:
        return sum(1 for c in self.pool if c.in_use)


# ==============================================================================
# 2. JPA PERSISTENCE CONTEXT & FIRST-LEVEL CACHE SIMULATOR
# ==============================================================================
@dataclass
class CustomerEntity:
    id: int
    name: str
    email: str
    tier: str


class PersistenceContext:
    def __init__(self):
        # First-Level Cache (Identity Map)
        self.cache: Dict[int, CustomerEntity] = {}
        # Snapshot for Dirty Checking
        self.snapshot: Dict[int, Dict[str, Any]] = {}

    def find(self, entity_id: int) -> Optional[CustomerEntity]:
        if entity_id in self.cache:
            info_msg(f"L1 Cache HIT: Entity Customer #{entity_id} ditemukan dalam Persistence Context (Tanpa SQL SELECT).")
            return self.cache[entity_id]

        info_msg(f"L1 Cache MISS: Melakukan SQL query 'SELECT * FROM customers WHERE id = {entity_id}'")
        # Simulasi database load
        loaded = CustomerEntity(id=entity_id, name="Budi Santoso", email="budi@example.com", tier="GOLD")
        self.cache[entity_id] = loaded
        self.snapshot[entity_id] = {"name": loaded.name, "email": loaded.email, "tier": loaded.tier}
        return loaded

    def flush(self) -> None:
        sub_header("JPA Session Flush & Dirty Checking Engine")
        dirt_found = False
        for entity_id, entity in self.cache.items():
            snap = self.snapshot.get(entity_id)
            if snap:
                changed_fields = []
                if entity.name != snap["name"]:
                    changed_fields.append(f"name='{entity.name}'")
                if entity.email != snap["email"]:
                    changed_fields.append(f"email='{entity.email}'")
                if entity.tier != snap["tier"]:
                    changed_fields.append(f"tier='{entity.tier}'")

                if changed_fields:
                    dirt_found = True
                    warn_msg(f"Dirty detected on Customer #{entity_id}! Auto-generating SQL UPDATE...")
                    print(f"   {CLR_MAGENTA}SQL>> UPDATE customers SET {', '.join(changed_fields)} WHERE id = {entity_id};{CLR_RESET}")
                    # Perbarui snapshot setelah sinkronisasi
                    self.snapshot[entity_id] = {"name": entity.name, "email": entity.email, "tier": entity.tier}

        if not dirt_found:
            info_msg("No entity state changes detected. 0 SQL UPDATE emitted.")


# ==============================================================================
# 3. N+1 QUERY PROBLEM VS JOIN FETCH BENCHMARK
# ==============================================================================
def setup_benchmark_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT);")
    cur.execute("CREATE TABLE books (id INTEGER PRIMARY KEY, author_id INTEGER, title TEXT);")

    # Insert sample data: 5 authors, masing-masing punya 3 buku
    authors_data = [(1, "Robert C. Martin"), (2, "Martin Fowler"), (3, "Joshua Bloch"), (4, "Kent Beck"), (5, "Erich Gamma")]
    cur.executemany("INSERT INTO authors VALUES (?, ?);", authors_data)

    books_data = []
    book_id = 1
    for author_id in range(1, 6):
        for b in range(1, 4):
            books_data.append((book_id, author_id, f"Software Engineering Volume {author_id}-{b}"))
            book_id += 1
    cur.executemany("INSERT INTO books VALUES (?, ?, ?);", books_data)
    conn.commit()
    return conn


def simulate_n_plus_one(conn: sqlite3.Connection) -> None:
    sub_header("Skenario 1: ORM Default Lazy Fetching (N+1 Query Problem)")
    cur = conn.cursor()

    query_count = 0
    start = time.perf_counter()

    # Query 1: Mengambil semua authors
    cur.execute("SELECT id, name FROM authors;")
    authors = cur.fetchall()
    query_count += 1
    print(f" {CLR_RED}[Query #{query_count}]{CLR_RESET} SELECT * FROM authors;")

    total_books = 0
    # Query N: Untuk setiap author, ORM menembak relasi buku secara individual
    for a_id, a_name in authors:
        cur.execute("SELECT id, title FROM books WHERE author_id = ?;", (a_id,))
        books = cur.fetchall()
        query_count += 1
        total_books += len(books)
        print(f" {CLR_RED}[Query #{query_count} (Lazy)]{CLR_RESET} SELECT * FROM books WHERE author_id = {a_id}; -> found {len(books)} books")

    duration = (time.perf_counter() - start) * 1000
    alert_msg(f"Hasil N+1 Problem: Total Queries = {query_count} | Retrieved Books = {total_books} | Duration: {duration:.3f}ms")


def simulate_join_fetch(conn: sqlite3.Connection) -> None:
    sub_header("Skenario 2: Hibernate Optimization (JOIN FETCH / Eager Batch)")
    cur = conn.cursor()

    start = time.perf_counter()
    sql = """
    SELECT a.id, a.name, b.id, b.title
    FROM authors a
    LEFT JOIN books b ON a.id = b.author_id;
    """
    cur.execute(sql)
    rows = cur.fetchall()
    duration = (time.perf_counter() - start) * 1000

    print(f" {CLR_GREEN}[Optimized Query #1]{CLR_RESET} SELECT a.*, b.* FROM authors a LEFT JOIN books b ON a.id = b.author_id;")
    success_msg(f"Hasil JOIN FETCH: Total Queries = 1 | Loaded Rows = {len(rows)} | Duration: {duration:.3f}ms")


# ==============================================================================
# 4. DATABASE QUERY PERFORMANCE & INDEX EXPLAIN PLAN
# ==============================================================================
def simulate_query_tuning(conn: sqlite3.Connection) -> None:
    sub_header("Skenario 3: Database Query Plan & Index Scan Tuning")
    cur = conn.cursor()

    # Create large dummy table for orders
    cur.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_uuid TEXT, total_amount REAL);")
    sample_orders = [(i, f"CUST-{'%04d' % (i % 200)}", 150.0 + (i % 50)) for i in range(1, 2001)]
    cur.executemany("INSERT INTO orders VALUES (?, ?, ?);", sample_orders)
    conn.commit()

    info_msg("Menganalisis Query TANPA Index (Full Table Scan):")
    cur.execute("EXPLAIN QUERY PLAN SELECT * FROM orders WHERE customer_uuid = 'CUST-0042';")
    plan_no_index = cur.fetchall()
    for step in plan_no_index:
        warn_msg(f"Plan Detail: {step[3]}")

    info_msg("Menambahkan B-Tree Index: CREATE INDEX idx_orders_cust ON orders(customer_uuid);")
    cur.execute("CREATE INDEX idx_orders_cust ON orders(customer_uuid);")
    conn.commit()

    info_msg("Menganalisis Query SETELAH Index Dibuat (Covering / Index Search):")
    cur.execute("EXPLAIN QUERY PLAN SELECT * FROM orders WHERE customer_uuid = 'CUST-0042';")
    plan_indexed = cur.fetchall()
    for step in plan_indexed:
        success_msg(f"Optimized Plan: {step[3]}")


# ==============================================================================
# MAIN INTERACTIVE DEMO RUNNER
# ==============================================================================
def run_all_simulations() -> None:
    header("Simulasi Fondasi Data Persistence & ORM Performance Tuning (Java BAB-05)")

    # 1. HikariCP Pool Demo
    sub_header("1. HikariCP Connection Pooling Lifecycle & Leak Detection")
    pool = HikariPoolSimulator(max_size=2, leak_detection_ms=100.0)
    c1 = pool.get_connection()
    c2 = pool.get_connection()
    _ = pool.get_connection()  # Will exhaust pool

    if c1:
        time.sleep(0.12)  # Trigger simulated leak threshold
        pool.release_connection(c1)
    if c2:
        pool.release_connection(c2)

    # 2. JPA First Level Cache & Dirty Checking
    sub_header("2. JPA EntityManager First-Level Cache (Identity Map) & Dirty Checking")
    em = PersistenceContext()
    cust1 = em.find(101)  # Cache Miss -> SQL
    cust2 = em.find(101)  # Cache Hit -> InMemory

    if cust1:
        info_msg(f"Memodifikasi objek entity di memori: tier diubah dari '{cust1.tier}' ke 'PLATINUM'...")
        cust1.tier = "PLATINUM"

    em.flush()

    # 3. N+1 Problem vs JOIN FETCH
    db_conn = setup_benchmark_db()
    simulate_n_plus_one(db_conn)
    simulate_join_fetch(db_conn)

    # 4. Index & Query Tuning
    simulate_query_tuning(db_conn)
    db_conn.close()

    header("Simulasi Selesai dengan Sukses")
    success_msg("Semua konsep arsitektur JPA, Hibernate, Connection Pool, dan Indexing berhasil disimulasikan.")


if __name__ == "__main__":
    run_all_simulations()
