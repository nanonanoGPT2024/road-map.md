#!/usr/bin/env python3
"""
Lab Exercise M02: Django QuerySet Mastery & Database Performance Optimization
Arsitektur Simulasi Produksi Lanjutan (Self-contained Runnable Engine).
"""

import sys
import time
import random
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# ANSI Color Codes & Formatting
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_DARK = "\033[40m"


class QueryInspector:
    """Simulasi Django connection.queries & DB Profiler di environment produksi."""
    def __init__(self):
        self.queries: List[Dict[str, Any]] = []

    def log(self, sql: str, duration_ms: float, rows_affected: int = 0):
        self.queries.append({
            "sql": sql.strip(),
            "time_ms": duration_ms,
            "rows": rows_affected
        })

    def reset(self):
        self.queries.clear()

    @property
    def total_time(self) -> float:
        return sum(q["time_ms"] for q in self.queries)

    @property
    def count(self) -> int:
        return len(self.queries)

    def print_summary(self, title: str):
        print(f"\n{BOLD}{CYAN}=== [PROFILER REPORT: {title}] ==={RESET}")
        print(f"Total Database Queries Executed : {BOLD}{RED if self.count > 10 else GREEN}{self.count}{RESET}")
        print(f"Cumulative DB Latency (Simulated): {BOLD}{YELLOW}{self.total_time:.3f} ms{RESET}")
        print(f"{DIM}Daftar query SQL yang tertangkap di database connection logger:{RESET}")
        for idx, q in enumerate(self.queries, 1):
            color = RED if "WHERE author_id =" in q["sql"] or "WHERE customer_id =" in q["sql"] else BLUE
            print(f"  {DIM}[{idx:02d}]{RESET} {color}{q['sql']}{RESET} {DIM}({q['time_ms']:.2f}ms | {q['rows']} rows){RESET}")
        print(f"{CYAN}{'=' * 50}{RESET}\n")


inspector = QueryInspector()


class DatabaseEngine:
    """In-memory SQLite Engine yang mensimulasikan Django ORM QuerySet Internals."""
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._seed_data()

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                membership_tier TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                order_code TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            );

            CREATE INDEX idx_orders_customer ON orders(customer_id);
            CREATE INDEX idx_order_items_order ON order_items(order_id);
        """)
        self.conn.commit()

    def _seed_data(self):
        cur = self.conn.cursor()
        tiers = ["BRONZE", "SILVER", "GOLD", "PLATINUM"]
        statuses = ["COMPLETED", "PENDING", "CANCELLED", "REFUNDED"]

        # Seed 25 Customers
        for i in range(1, 26):
            cur.execute(
                "INSERT INTO customers (name, membership_tier) VALUES (?, ?)",
                (f"Customer_{i:02d}", random.choice(tiers))
            )

        # Seed 100 Orders
        for i in range(1, 101):
            cust_id = random.randint(1, 25)
            amount = round(random.uniform(50_000, 2_500_000), 2)
            cur.execute(
                "INSERT INTO orders (customer_id, order_code, amount, status) VALUES (?, ?, ?, ?)",
                (cust_id, f"ORD-{1000 + i}", amount, random.choice(statuses))
            )
            order_id = cur.lastrowid
            
            # Seed 2-4 items per order
            for j in range(random.randint(2, 4)):
                cur.execute(
                    "INSERT INTO order_items (order_id, product_name, quantity, price) VALUES (?, ?, ?, ?)",
                    (order_id, f"SKU-{random.randint(100, 999)}", random.randint(1, 5), round(amount / 3, 2))
                )

        self.conn.commit()

    def execute_logged(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        start = time.perf_counter()
        cur = self.conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        duration = (time.perf_counter() - start) * 1000.0
        # Tambahkan latensi overhead simulasi network I/O
        simulated_latency = duration + random.uniform(0.8, 1.8)
        inspector.log(sql, simulated_latency, len(rows))
        return rows


db = DatabaseEngine()


# ==============================================================================
# SCENARIO 1: N+1 Problem vs select_related & prefetch_related
# ==============================================================================
def run_scenario_n_plus_one():
    print(f"\n{BOLD}{MAGENTA}[SCENARIO 1: N+1 Query Anti-Pattern vs Eager Loading]{RESET}")
    print("Memproses 15 order terbaru berserta detail profil customer dan item-itemnya.\n")

    # A. Anti-Pattern (Naive Django QuerySet Iteration)
    print(f"{YELLOW}--> Menjalankan Simulasi [A]: Naive ORM Loop (Memicu N+1 Query)...{RESET}")
    inspector.reset()
    start_cpu = time.perf_counter()

    naive_orders = db.execute_logged("SELECT id, customer_id, order_code, amount FROM orders LIMIT 15")
    for ord_row in naive_orders:
        # Query tambahan untuk relasi Foreign Key (customer)
        cust_row = db.execute_logged("SELECT id, name, membership_tier FROM customers WHERE id = ?", (ord_row["customer_id"],))
        # Query tambahan untuk relasi Many-To-One (order_items)
        item_rows = db.execute_logged("SELECT product_name, quantity FROM order_items WHERE order_id = ?", (ord_row["id"],))

    naive_elapsed = (time.perf_counter() - start_cpu) * 1000.0
    inspector.print_summary("Naive ORM (N+1 Query Explosion)")

    # B. Production Pattern: select_related & prefetch_related
    print(f"{GREEN}--> Menjalankan Simulasi [B]: Django Optimized (select_related + prefetch_related)...{RESET}")
    inspector.reset()
    start_cpu = time.perf_counter()

    # Simulasi 1: select_related('customer') -> 1 Single SQL JOIN
    joined_orders = db.execute_logged("""
        SELECT o.id, o.order_code, o.amount, c.id AS customer_id, c.name AS customer_name, c.membership_tier
        FROM orders o
        INNER JOIN customers c ON o.customer_id = c.id
        LIMIT 15
    """)
    order_ids = [str(r["id"]) for r in joined_orders]

    # Simulasi 2: prefetch_related('items') -> 1 Batched IN (...) Query
    id_list_str = ",".join(order_ids)
    all_items = db.execute_logged(f"""
        SELECT order_id, product_name, quantity
        FROM order_items
        WHERE order_id IN ({id_list_str})
    """)

    # In-memory mapping (Prefetch cache di Django ORM)
    items_by_order: Dict[int, list] = {}
    for it in all_items:
        items_by_order.setdefault(it["order_id"], []).append(it)

    optimized_elapsed = (time.perf_counter() - start_cpu) * 1000.0
    inspector.print_summary("Optimized (select_related & prefetch_related)")

    print(f"{BOLD}{GREEN}HASIL ANALISIS:{RESET}")
    print(f"  Penghematan Query: Dari {BOLD}{RED}31 queries{RESET} menjadi {BOLD}{GREEN}2 queries{RESET}!")
    print(f"  Peningkatan Throughput: Database round-trip berkurang ~93.5%.\n")


# ==============================================================================
# SCENARIO 2: Conditional Aggregation & Case/When vs Multiple Filters
# ==============================================================================
def run_scenario_conditional_aggregation():
    print(f"\n{BOLD}{MAGENTA}[SCENARIO 2: Conditional Aggregation (Case/When) vs Query Multiplier]{RESET}")
    print("Menghitung metrik analitik omzet per kategori status (COMPLETED, REFUNDED, CANCELLED).\n")

    # A. Anti-Pattern: Multiple Query Round-Trips
    print(f"{YELLOW}--> Menjalankan Simulasi [A]: Separate ORM Filter().aggregate() calls...{RESET}")
    inspector.reset()
    for st in ["COMPLETED", "REFUNDED", "CANCELLED"]:
        db.execute_logged("SELECT SUM(amount), COUNT(*) FROM orders WHERE status = ?", (st,))
    inspector.print_summary("Separate ORM .aggregate() Calls")

    # B. Production Pattern: Single Query Conditional Aggregation
    print(f"{GREEN}--> Menjalankan Simulasi [B]: Django Case/When + Sum() Filter Annotation...{RESET}")
    inspector.reset()
    db.execute_logged("""
        SELECT
            COUNT(*) AS total_orders,
            SUM(CASE WHEN status = 'COMPLETED' THEN amount ELSE 0 END) AS revenue_completed,
            SUM(CASE WHEN status = 'REFUNDED' THEN amount ELSE 0 END) AS loss_refunded,
            SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) AS count_cancelled
        FROM orders
    """)
    inspector.print_summary("Single Conditional Aggregation (Django annotate/aggregate)")


# ==============================================================================
# SCENARIO 3: Subquery & OuterRef vs In-Memory Mapping
# ==============================================================================
def run_scenario_subquery_outerref():
    print(f"\n{BOLD}{MAGENTA}[SCENARIO 3: Django Subquery & OuterRef Optimization]{RESET}")
    print("Mengambil profil customer dengan anotasi pesanan terakhir (latest_order_code).\n")

    inspector.reset()
    # Menggunakan SQL Subquery terkorelasi (mencerminkan Subquery(OuterRef('pk')))
    sql = """
        SELECT
            c.id,
            c.name,
            c.membership_tier,
            (
                SELECT o.order_code
                FROM orders o
                WHERE o.customer_id = c.id
                ORDER BY o.id DESC
                LIMIT 1
            ) AS latest_order_code,
            (
                SELECT COUNT(*)
                FROM orders o
                WHERE o.customer_id = c.id
            ) AS total_orders_placed
        FROM customers c
        WHERE c.is_active = 1
        LIMIT 10
    """
    rows = db.execute_logged(sql)
    inspector.print_summary("Subquery(OuterRef()) Single-pass Fetch")

    print(f"{BOLD}{CYAN}Preview Anotasi Data:{RESET}")
    for r in rows[:5]:
        print(f"  - {BOLD}{r['name']}{RESET} [{r['membership_tier']}] -> Latest: {GREEN}{r['latest_order_code']}{RESET} (Total: {r['total_orders_placed']} orders)")


# ==============================================================================
# SCENARIO 4: Bulk Operations vs Individual Save/Insert Loops
# ==============================================================================
def run_scenario_bulk_operations():
    print(f"\n{BOLD}{MAGENTA}[SCENARIO 4: Bulk Batch Operations (bulk_create / bulk_update)]{RESET}")
    print("Menyisipkan 200 log transaksi audit baru ke dalam database.\n")

    # A. Anti-Pattern: Loop save()
    print(f"{YELLOW}--> Menjalankan Simulasi [A]: Individual save() dalam perulangan Python...{RESET}")
    inspector.reset()
    start_t = time.perf_counter()
    # Simulasikan 30 iterasi loop save agar cepat namun memperlihatkan overhead
    for i in range(30):
        db.execute_logged(
            "INSERT INTO orders (customer_id, order_code, amount, status) VALUES (?, ?, ?, ?)",
            (1, f"LOOP-SAV-{i}", 150000.0, "PENDING")
        )
    inspector.print_summary("Django loop model.save() - 30 Roundtrips")

    # B. Production Pattern: bulk_create with batch_size
    print(f"{GREEN}--> Menjalankan Simulasi [B]: bulk_create(objects, batch_size=100)...{RESET}")
    inspector.reset()
    batch_records = [(1, f"BULK-SAV-{i}", 150000.0, "PENDING") for i in range(100)]
    
    # SQLite batch insert parameter generation
    placeholders = ",".join(["(?, ?, ?, ?)"] * len(batch_records))
    flat_params = [val for rec in batch_records for val in rec]
    sql_bulk = f"INSERT INTO orders (customer_id, order_code, amount, status) VALUES {placeholders}"
    
    db.execute_logged(sql_bulk, tuple(flat_params))
    inspector.print_summary("Django bulk_create(batch_size=100) - 1 Roundtrip")


# ==============================================================================
# Interactive Terminal Loop
# ==============================================================================
def display_menu():
    print(f"\n{BOLD}{BLUE}================================================================{RESET}")
    print(f"{BOLD}{GREEN}  DJANGO QUERYSET MASTERY & PERFORMANCE LAB ENGINE (BAB 03)  {RESET}")
    print(f"{BOLD}{BLUE}================================================================{RESET}")
    print(f" {BOLD}1.{RESET} Jalankan Lab 1: N+1 Problem vs select_related & prefetch_related")
    print(f" {BOLD}2.{RESET} Jalankan Lab 2: Conditional Aggregation (Case/When) vs Multi-Query")
    print(f" {BOLD}3.{RESET} Jalankan Lab 3: Subquery & OuterRef In-Database Annotation")
    print(f" {BOLD}4.{RESET} Jalankan Lab 4: Bulk Operations vs Individual Save Loop")
    print(f" {BOLD}5.{RESET} Jalankan Seluruh Skenario Benchmark (Full Suite)")
    print(f" {BOLD}0.{RESET} Keluar (Exit)")
    print(f"{BLUE}----------------------------------------------------------------{RESET}")


def main():
    # If run in non-interactive / automated environment or with args
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a"):
        run_scenario_n_plus_one()
        run_scenario_conditional_aggregation()
        run_scenario_subquery_outerref()
        run_scenario_bulk_operations()
        print(f"\n{BOLD}{GREEN}[V] Seluruh benchmark performa QuerySet selesai dijalankan dengan sukses.{RESET}")
        return

    # Interactive CLI Mode
    while True:
        display_menu()
        try:
            choice = input(f"{BOLD}{CYAN}Pilih opsi menu (0-5) [default 5]: {RESET}").strip()
            if not choice:
                choice = "5"

            if choice == "1":
                run_scenario_n_plus_one()
            elif choice == "2":
                run_scenario_conditional_aggregation()
            elif choice == "3":
                run_scenario_subquery_outerref()
            elif choice == "4":
                run_scenario_bulk_operations()
            elif choice == "5":
                run_scenario_n_plus_one()
                run_scenario_conditional_aggregation()
                run_scenario_subquery_outerref()
                run_scenario_bulk_operations()
            elif choice in ("0", "q", "exit"):
                print(f"{GREEN}Lab exercise selesai. Terima kasih.{RESET}")
                break
            else:
                print(f"{RED}Pilihan tidak valid. Silakan masukkan angka 0 sampai 5.{RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Menutup sesi lab...{RESET}")
            break


if __name__ == "__main__":
    main()
