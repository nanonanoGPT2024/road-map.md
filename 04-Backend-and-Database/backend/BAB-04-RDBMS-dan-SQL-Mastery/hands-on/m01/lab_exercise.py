#!/usr/bin/env python3
"""
Lab Exercise: RDBMS & SQL Mastery Hands-on Simulator
BAB-04: RDBMS dan SQL Mastery (Fondasi Inti Backend)

Simulasi mandiri konsep inti RDBMS:
1. DDL & Integritas Relasional (PK, FK, CHECK Constraint, Cascades)
2. Transaksi ACID (Atomicity, Consistency, Isolation, Rollback & Commit)
3. Query Planner & Index Optimization (SCAN vs SEARCH INDEX via EXPLAIN QUERY PLAN)
4. Agregasi Kompleks, Relasi Multi-Tabel, dan Window Functions
"""

import os
import sys
import sqlite3
import time
from typing import List, Tuple, Any

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"

def print_header(title: str) -> None:
    line = "=" * 70
    print(f"\n{Colors.CYAN}{line}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.HEADER}>>> {title} <<<{Colors.RESET}")
    print(f"{Colors.CYAN}{line}{Colors.RESET}")

def print_success(msg: str) -> None:
    print(f"{Colors.GREEN}[+] {msg}{Colors.RESET}")

def print_info(msg: str) -> None:
    print(f"{Colors.BLUE}[*] {msg}{Colors.RESET}")

def print_warning(msg: str) -> None:
    print(f"{Colors.YELLOW}[!] {msg}{Colors.RESET}")

def print_error(msg: str) -> None:
    print(f"{Colors.RED}[-] {msg}{Colors.RESET}")

def print_table(columns: List[str], rows: List[Tuple[Any, ...]]) -> None:
    if not rows:
        print(f"{Colors.YELLOW}(Empty result set){Colors.RESET}")
        return
    col_widths = [len(col) for col in columns]
    for row in rows:
        for idx, val in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(val)))

    header_str = " | ".join(f"{col.ljust(col_widths[i])}" for i, col in enumerate(columns))
    separator = "-+-".join("-" * col_widths[i] for i in range(len(columns)))

    print(f"{Colors.BOLD}{header_str}{Colors.RESET}")
    print(f"{Colors.CYAN}{separator}{Colors.RESET}")
    for row in rows:
        row_str = " | ".join(f"{str(val).ljust(col_widths[i])}" for i, val in enumerate(row))
        print(row_str)

class RdbmsSimulator:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        # Enable Foreign Key enforcement in SQLite
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()

    def demo_ddl_and_constraints(self) -> None:
        print_header("MODUL 1: Relational Schema, Constraints & Referential Integrity")
        cursor = self.conn.cursor()

        print_info("Membuat tabel 'departments' dan 'employees' dengan Foreign Key & CHECK constraint...")
        cursor.execute("DROP TABLE IF EXISTS employees;")
        cursor.execute("DROP TABLE IF EXISTS departments;")

        cursor.execute("""
            CREATE TABLE departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code VARCHAR(10) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                salary NUMERIC(12, 2) CHECK(salary >= 3000000),
                dept_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (dept_id) REFERENCES departments(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()
        print_success("Tabel departments & employees berhasil dibuat.")

        # Insert seed data
        cursor.executemany(
            "INSERT INTO departments (code, name) VALUES (?, ?);",
            [("ENG", "Engineering"), ("PRD", "Product Management"), ("FIN", "Finance")]
        )
        cursor.executemany(
            "INSERT INTO employees (name, email, salary, dept_id) VALUES (?, ?, ?, ?);",
            [
                ("Alice Pratama", "alice@corp.id", 15000000.0, 1),
                ("Budi Santoso", "budi@corp.id", 12500000.0, 1),
                ("Citra Dewi", "citra@corp.id", 14000000.0, 2),
                ("Denny Kurnia", "denny@corp.id", 9500000.0, 3),
            ]
        )
        self.conn.commit()
        print_success("Data seed berhasil disisipkan.")

        # Test CHECK Constraint Violation
        print_info("Menguji integritas data: Mencoba INSERT salary di bawah UMR (CHECK constraint salary >= 3000000)...")
        try:
            cursor.execute(
                "INSERT INTO employees (name, email, salary, dept_id) VALUES (?, ?, ?, ?);",
                ("Eko Murahan", "eko@corp.id", 2000000.0, 1)
            )
            self.conn.commit()
        except sqlite3.IntegrityError as err:
            print_error(f"Ditolak RDBMS (Integritas terjaga): {err}")

        # Test Foreign Key Violation
        print_info("Menguji referential integrity: Mencoba INSERT employee dengan dept_id fiktif (dept_id = 999)...")
        try:
            cursor.execute(
                "INSERT INTO employees (name, email, salary, dept_id) VALUES (?, ?, ?, ?);",
                ("Fajar Palsu", "fajar@corp.id", 8000000.0, 999)
            )
            self.conn.commit()
        except sqlite3.IntegrityError as err:
            print_error(f"Ditolak RDBMS (Foreign Key Constraint Fail): {err}")

    def demo_acid_transactions(self) -> None:
        print_header("MODUL 2: Transaksi ACID (Simulasi Atomic Bank Transfer)")
        cursor = self.conn.cursor()

        cursor.execute("DROP TABLE IF EXISTS bank_accounts;")
        cursor.execute("""
            CREATE TABLE bank_accounts (
                account_no VARCHAR(20) PRIMARY KEY,
                owner_name VARCHAR(100) NOT NULL,
                balance NUMERIC(14, 2) NOT NULL CHECK(balance >= 0)
            );
        """)
        cursor.executemany(
            "INSERT INTO bank_accounts (account_no, owner_name, balance) VALUES (?, ?, ?);",
            [("ACC-101", "PT Alpha Tech", 50000000.0), ("ACC-102", "Vendor Cloud Indo", 1000000.0)]
        )
        self.conn.commit()

        print_info("Saldo Awal:")
        cursor.execute("SELECT account_no, owner_name, balance FROM bank_accounts;")
        print_table(["Account No", "Owner", "Balance (IDR)"], cursor.fetchall())

        transfer_amount = 20000000.0
        print_info(f"Skenario Transaksi: Transfer Rp {transfer_amount:,.2f} dari ACC-101 ke ACC-102 (Harus Sukses)...")

        # Atomic Execution with manual transaction control
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("UPDATE bank_accounts SET balance = balance - ? WHERE account_no = ?;", (transfer_amount, "ACC-101"))
            cursor.execute("UPDATE bank_accounts SET balance = balance + ? WHERE account_no = ?;", (transfer_amount, "ACC-102"))
            self.conn.commit()
            print_success("COMMIT Berhasil! Seluruh langkah transfer telah dieksekusi secara atomic.")
        except Exception as e:
            self.conn.rollback()
            print_error(f"Transaksi gagal, ROLLBACK dieksekusi: {e}")

        cursor.execute("SELECT account_no, owner_name, balance FROM bank_accounts;")
        print_table(["Account No", "Owner", "Balance (IDR)"], cursor.fetchall())

        # Failure & Rollback Scenario
        overdraft_amount = 60000000.0
        print_warning(f"Skenario Gagal: Transfer Rp {overdraft_amount:,.2f} dari ACC-101 (Saldo tersisa tidak cukup, memicu CHECK balance >= 0)...")
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("UPDATE bank_accounts SET balance = balance - ? WHERE account_no = ?;", (overdraft_amount, "ACC-101"))
            cursor.execute("UPDATE bank_accounts SET balance = balance + ? WHERE account_no = ?;", (overdraft_amount, "ACC-102"))
            self.conn.commit()
        except sqlite3.IntegrityError as err:
            self.conn.rollback()
            print_error(f"Integritas CHECK terlanggar! Transaksi di-ROLLBACK otomatis: {err}")

        print_info("Verifikasi Saldo Pasca-Rollback (Saldo tidak boleh berkurang sebagian/inkonsisten):")
        cursor.execute("SELECT account_no, owner_name, balance FROM bank_accounts;")
        print_table(["Account No", "Owner", "Balance (IDR)"], cursor.fetchall())

    def demo_indexing_and_planner(self) -> None:
        print_header("MODUL 3: Indeks B-Tree & Query Planner (EXPLAIN QUERY PLAN)")
        cursor = self.conn.cursor()

        cursor.execute("DROP TABLE IF EXISTS orders;")
        cursor.execute("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                order_code VARCHAR(36) NOT NULL,
                total_price NUMERIC(10, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        print_info("Men-generate 10,000 data dummy orders untuk demonstrasi query cost...")
        start_time = time.time()
        dummy_rows = [
            (i % 500 + 1, f"ORD-2026-X{i:06d}", (i * 17) % 500000 + 50000)
            for i in range(1, 10001)
        ]
        cursor.executemany("INSERT INTO orders (customer_id, order_code, total_price) VALUES (?, ?, ?);", dummy_rows)
        self.conn.commit()
        elapsed = time.time() - start_time
        print_success(f"10,000 records berhasil dimasukkan dalam {elapsed:.3f} detik.")

        target_code = "ORD-2026-X007890"

        # 1. Tanpa Index (Full Table Scan)
        print_info("1. Menjalankan EXPLAIN QUERY PLAN tanpa indeks:")
        cursor.execute(f"EXPLAIN QUERY PLAN SELECT * FROM orders WHERE order_code = '{target_code}';")
        plan_without_index = cursor.fetchall()
        for row in plan_without_index:
            print_warning(f"   [PLAN] {row[3]}")

        # 2. Tambahkan B-Tree Index
        print_info("2. Membuat B-Tree Index: CREATE INDEX idx_orders_order_code ON orders(order_code);")
        cursor.execute("CREATE INDEX idx_orders_order_code ON orders(order_code);")
        self.conn.commit()
        print_success("Index B-Tree selesai dibuat.")

        # 3. Dengan Index (Index Seek)
        print_info("3. Menjalankan EXPLAIN QUERY PLAN dengan B-Tree index:")
        cursor.execute(f"EXPLAIN QUERY PLAN SELECT * FROM orders WHERE order_code = '{target_code}';")
        plan_with_index = cursor.fetchall()
        for row in plan_with_index:
            print_success(f"   [PLAN] {row[3]}")

    def demo_advanced_sql(self) -> None:
        print_header("MODUL 4: Advanced SQL (JOINs, Aggregation, and Window Functions)")
        cursor = self.conn.cursor()

        print_info("Menjalankan Query: Agregasi per Departemen + Gaji Tertinggi & Rata-rata:")
        query_agg = """
            SELECT 
                d.name AS department_name,
                COUNT(e.id) AS total_employees,
                COALESCE(SUM(e.salary), 0) AS total_payroll,
                ROUND(COALESCE(AVG(e.salary), 0), 2) AS avg_salary,
                COALESCE(MAX(e.salary), 0) AS max_salary
            FROM departments d
            LEFT JOIN employees e ON d.id = e.dept_id
            GROUP BY d.id, d.name
            ORDER BY total_payroll DESC;
        """
        cursor.execute(query_agg)
        print_table(
            ["Department", "Staff Count", "Payroll (IDR)", "Avg Salary", "Max Salary"],
            cursor.fetchall()
        )

        print_info("Menjalankan Query: Window Function (DENSE_RANK gaji dalam tiap departemen):")
        query_window = """
            SELECT 
                e.name,
                d.name AS department,
                e.salary,
                DENSE_RANK() OVER (PARTITION BY e.dept_id ORDER BY e.salary DESC) as salary_rank
            FROM employees e
            JOIN departments d ON e.dept_id = d.id;
        """
        cursor.execute(query_window)
        print_table(["Employee Name", "Department", "Salary (IDR)", "Dept Rank"], cursor.fetchall())

def main() -> None:
    print(f"{Colors.BOLD}{Colors.GREEN}")
    print("=" * 70)
    print("   RDBMS & SQL MASTERY: INTERACTIVE HANDS-ON LAB SIMULATOR")
    print("   Fondasi Database Relasional, ACID, Indexing & Query Optimasi")
    print("=" * 70)
    print(f"{Colors.RESET}")

    sim = RdbmsSimulator()
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--auto":
            sim.demo_ddl_and_constraints()
            sim.demo_acid_transactions()
            sim.demo_indexing_and_planner()
            sim.demo_advanced_sql()
            print_success("\nSeluruh modul laboratorium selesai dieksekusi dengan sukses.")
            return

        while True:
            print("\nSilakan pilih demonstrasi modul:")
            print("  1. DDL, Constraints & Referential Integrity (PK/FK/CHECK)")
            print("  2. ACID Transaction & Concurrency Isolation (Transfer & Rollback)")
            print("  3. Indexing & Query Planner (B-Tree vs Full Table Scan)")
            print("  4. Advanced SQL (JOINs, GROUP BY, Window Functions)")
            print("  5. Jalankan Semua Modul Sekaligus")
            print("  q. Keluar")

            choice = input(f"\n{Colors.BOLD}Masukkan pilihan (1-5/q): {Colors.RESET}").strip().lower()
            if choice == "1":
                sim.demo_ddl_and_constraints()
            elif choice == "2":
                sim.demo_acid_transactions()
            elif choice == "3":
                sim.demo_indexing_and_planner()
            elif choice == "4":
                sim.demo_advanced_sql()
            elif choice == "5":
                sim.demo_ddl_and_constraints()
                sim.demo_acid_transactions()
                sim.demo_indexing_and_planner()
                sim.demo_advanced_sql()
            elif choice in ("q", "quit", "exit"):
                print_info("Menutup sesi database simulator. Selesai.")
                break
            else:
                print_warning("Pilihan tidak valid. Silakan coba lagi.")
    finally:
        sim.close()

if __name__ == "__main__":
    main()
