#!/usr/bin/env python3
"""
Lab Exercise: M01 - Data Layer, ORMs & Serverless Databases
BAB-05: Data Layer, ORMs, and Serverless Databases

Simulasi Teknis Interaktif:
1. ORM vs Raw SQL Query Generator & N+1 Problem Visualizer
2. Serverless Connection Pooling (Cold Start vs HTTP Driver Proxy vs Exhaustion)
3. Schema Migration State Machine Simulation (Up/Down Transactions)
"""

import sys
import time
import random
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

# ANSI Color Codes for Terminal Output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

# ==========================================
# 1. ORM Simulation & N+1 Query Visualization
# ==========================================

@dataclass
class User:
    id: int
    name: str
    email: str

@dataclass
class Post:
    id: int
    user_id: int
    title: str

class MockDatabase:
    def __init__(self):
        self.users = [
            User(1, "Alice Wijaya", "alice@example.com"),
            User(2, "Budi Prakoso", "budi@example.com"),
            User(3, "Citra Lestari", "citra@example.com"),
            User(4, "Dewi Anggraini", "dewi@example.com"),
        ]
        self.posts = [
            Post(101, 1, "Tutorial Modern Full-Stack Architecture"),
            Post(102, 1, "Deep Dive Connection Pooling di Edge"),
            Post(103, 2, "Mengapa Serverless Postgres Butuh PgBouncer"),
            Post(104, 3, "Optimasi ORM Queries untuk Production"),
            Post(105, 4, "State Machine Migration Patterns"),
        ]

    def execute_sql(self, sql: str, duration_ms: float = 12.0) -> None:
        time.sleep(duration_ms / 1000.0)
        print(f"  {Colors.DIM}[SQL EXEC ({duration_ms:.1f}ms)]{Colors.RESET} {Colors.CYAN}{sql}{Colors.RESET}")

def simulate_n_plus_one_issue(db: MockDatabase) -> None:
    print(f"\n{Colors.BOLD}{Colors.YELLOW}=== Scenario A: Naive ORM Loop (The N+1 Query Problem) ==={Colors.RESET}")
    print(f"{Colors.DIM}Mengambil semua users (1 query), lalu untuk setiap user mengambil daftar posts (N query)...{Colors.RESET}\n")
    
    start_time = time.time()
    db.execute_sql("SELECT * FROM users;", duration_ms=15.0)
    users = db.users

    total_queries = 1
    for u in users:
        # N queries triggered lazily
        db.execute_sql(f"SELECT * FROM posts WHERE user_id = {u.id};", duration_ms=18.0)
        user_posts = [p for p in db.posts if p.user_id == u.id]
        total_queries += 1
        print(f"    -> User: {u.name} ({len(user_posts)} posts)")

    elapsed = (time.time() - start_time) * 1000.0
    print(f"\n{Colors.RED}[Problem Detected]{Colors.RESET} Total Queries: {total_queries} | Total Latency: {elapsed:.2f}ms")
    print(f"{Colors.YELLOW}Analisis: Latency membengkak linier seiring pertambahan baris database.{Colors.RESET}")

def simulate_eager_loading_solution(db: MockDatabase) -> None:
    print(f"\n{Colors.BOLD}{Colors.GREEN}=== Scenario B: Eager Loading / Single JOIN Query ==={Colors.RESET}")
    print(f"{Colors.DIM}Menggunakan JOIN atau 'WHERE IN' batch query dalam 1 atau 2 round-trips...{Colors.RESET}\n")

    start_time = time.time()
    db.execute_sql(
        "SELECT u.id, u.name, p.id AS post_id, p.title FROM users u "
        "LEFT JOIN posts p ON u.id = p.user_id;",
        duration_ms=16.5
    )

    # In-memory grouping
    posts_by_user: Dict[int, List[Post]] = {}
    for p in db.posts:
        posts_by_user.setdefault(p.user_id, []).append(p)

    for u in db.users:
        user_posts = posts_by_user.get(u.id, [])
        print(f"    -> User: {u.name} ({len(user_posts)} posts)")

    elapsed = (time.time() - start_time) * 1000.0
    print(f"\n{Colors.GREEN}[Optimal Solution]{Colors.RESET} Total Queries: 1 | Total Latency: {elapsed:.2f}ms")
    print(f"{Colors.CYAN}Efisiensi: Round-trip database terpangkas drastis!{Colors.RESET}")

# ==========================================
# 2. Serverless Connection Pooling Simulation
# ==========================================

class ServerlessPoolSimulator:
    def __init__(self, max_connections: int = 4):
        self.max_connections = max_connections
        self.active_connections = 0
        self.lock = threading.Lock()

    def invoke_traditional_lambda(self, client_id: int, results: List[bool]) -> None:
        """Traditional direct TCP connection per serverless function instance."""
        with self.lock:
            if self.active_connections >= self.max_connections:
                print(f"  {Colors.RED}[FAILED]{Colors.RESET} Client #{client_id:02d}: 'FATAL: sorry, too many clients already' (Exhaustion!)")
                results.append(False)
                return
            self.active_connections += 1
            print(f"  {Colors.YELLOW}[CONNECT]{Colors.RESET} Client #{client_id:02d} acquired TCP connection (Active: {self.active_connections}/{self.max_connections})")

        time.sleep(0.08) # simulate execution holding connection

        with self.lock:
            self.active_connections -= 1
            results.append(True)

    def invoke_http_serverless_driver(self, client_id: int, results: List[bool]) -> None:
        """Modern HTTP / WebSocket connection pooler (e.g., Neon/Hyperdrive/Prisma Accelerate)."""
        print(f"  {Colors.GREEN}[HTTP-PROXY]{Colors.RESET} Client #{client_id:02d} dispatched query via stateless HTTP API (Reused proxy pool)")
        time.sleep(0.02)
        results.append(True)

def run_connection_pool_simulation():
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== Simulasi Connection Pool: Traditional TCP vs Serverless Driver ==={Colors.RESET}")
    pool = ServerlessPoolSimulator(max_connections=4)
    incoming_requests = 8

    print(f"\n{Colors.BOLD}1. Arsitektur Tradisional (Direct TCP - Max Pool: 4, Concurrent Burst: {incoming_requests}):{Colors.RESET}")
    tcp_results: List[bool] = []
    threads = []
    for req_id in range(1, incoming_requests + 1):
        t = threading.Thread(target=pool.invoke_traditional_lambda, args=(req_id, tcp_results))
        threads.append(t)
        t.start()
        time.sleep(0.005) # slight burst jitter

    for t in threads:
        t.join()

    failures = tcp_results.count(False)
    print(f"Hasil: {Colors.RED}{failures} request gagal{Colors.RESET} karena connection limit Postgres terlampaui.")

    print(f"\n{Colors.BOLD}2. Arsitektur Modern Serverless Database (HTTP Tunneling / Pooling Proxy):{Colors.RESET}")
    http_results: List[bool] = []
    http_threads = []
    for req_id in range(1, incoming_requests + 1):
        t = threading.Thread(target=pool.invoke_http_serverless_driver, args=(req_id, http_results))
        http_threads.append(t)
        t.start()

    for t in http_threads:
        t.join()

    print(f"{Colors.GREEN}Hasil: 100% request ({len(http_results)}/{incoming_requests}) sukses tanpa connection exhaustion.{Colors.RESET}")

# ==========================================
# 3. Migration State Machine Simulation
# ==========================================

@dataclass
class MigrationStep:
    version: str
    name: str
    up_sql: str
    down_sql: str

class MigrationRunner:
    def __init__(self):
        self.current_version: Optional[str] = None
        self.history: List[str] = []
        self.available_migrations = [
            MigrationStep("20260101_01", "create_users_table", "CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT);", "DROP TABLE users;"),
            MigrationStep("20260102_02", "add_email_to_users", "ALTER TABLE users ADD COLUMN email TEXT UNIQUE;", "ALTER TABLE users DROP COLUMN email;"),
            MigrationStep("20260103_03", "create_posts_table", "CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INT, title TEXT);", "DROP TABLE posts;"),
        ]

    def migrate_up(self):
        print(f"\n{Colors.BOLD}{Colors.CYAN}--- Menjalankan Migrasi (UP) ---{Colors.RESET}")
        for step in self.available_migrations:
            if step.version not in self.history:
                print(f"  {Colors.GREEN}[APPLYING]{Colors.RESET} {step.version}_{step.name}")
                print(f"    SQL: {Colors.DIM}{step.up_sql}{Colors.RESET}")
                time.sleep(0.03)
                self.history.append(step.version)
                self.current_version = step.version
        print(f"{Colors.GREEN}[DONE]{Colors.RESET} Current Schema Version: {Colors.BOLD}{self.current_version}{Colors.RESET}")

    def rollback_down(self):
        print(f"\n{Colors.BOLD}{Colors.YELLOW}--- Menjalankan Rollback (DOWN) ---{Colors.RESET}")
        if not self.history:
            print(f"  {Colors.DIM}Tidak ada migrasi aktif untuk di-rollback.{Colors.RESET}")
            return
        
        last_version = self.history.pop()
        target_step = next(s for s in self.available_migrations if s.version == last_version)
        print(f"  {Colors.RED}[REVERTING]{Colors.RESET} {target_step.version}_{target_step.name}")
        print(f"    SQL: {Colors.DIM}{target_step.down_sql}{Colors.RESET}")
        self.current_version = self.history[-1] if self.history else None
        print(f"{Colors.YELLOW}[REVERTED]{Colors.RESET} Current Schema Version: {Colors.BOLD}{self.current_version or 'Initial State'}{Colors.RESET}")

# ==========================================
# Main Interactive Menu
# ==========================================

def display_menu():
    print(f"\n{Colors.BOLD}{Colors.CYAN}===================================================={Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.HEADER}  LAB EXERCISE: DATA LAYER, ORMS & SERVERLESS DB    {Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}===================================================={Colors.RESET}")
    print("1. Jalankan Simulasi N+1 Problem vs Eager Loading")
    print("2. Jalankan Simulasi Serverless Connection Pooling")
    print("3. Jalankan Simulasi Database Migration State Machine")
    print("4. Jalankan Semua Uji Validasi Otomatis")
    print("5. Keluar")
    print(f"{Colors.DIM}Pilih opsi [1-5]: {Colors.RESET}", end="")

def run_all_validation():
    print(f"\n{Colors.BOLD}{Colors.GREEN}=== Menjalankan Seluruh Suite Validasi Teknis ==={Colors.RESET}")
    db = MockDatabase()
    simulate_n_plus_one_issue(db)
    simulate_eager_loading_solution(db)
    run_connection_pool_simulation()
    
    migrator = MigrationRunner()
    migrator.migrate_up()
    migrator.rollback_down()
    print(f"\n{Colors.BOLD}{Colors.GREEN}[SUCCESS]{Colors.RESET} Seluruh simulasi konsep data layer selesai tanpa error.")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_all_validation()
        return

    db = MockDatabase()
    migrator = MigrationRunner()

    while True:
        display_menu()
        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}Keluar dari program.{Colors.RESET}")
            break

        if choice == "1":
            simulate_n_plus_one_issue(db)
            simulate_eager_loading_solution(db)
        elif choice == "2":
            run_connection_pool_simulation()
        elif choice == "3":
            migrator.migrate_up()
            migrator.rollback_down()
        elif choice == "4":
            run_all_validation()
        elif choice == "5":
            print(f"{Colors.GREEN}Terima kasih telah menyelesaikan Lab Exercise Data Layer!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan pilih 1-5.{Colors.RESET}")

if __name__ == "__main__":
    main()
