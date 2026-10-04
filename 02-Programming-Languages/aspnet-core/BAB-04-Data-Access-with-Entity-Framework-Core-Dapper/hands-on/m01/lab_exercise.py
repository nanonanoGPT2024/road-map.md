#!/usr/bin/env python3
"""
Lab Exercise: Data Access with Entity Framework Core & Dapper Simulation
Repository: 02-Programming-Languages/aspnet-core/BAB-04-Data-Access-with-Entity-Framework-Core-Dapper
Pilar: Hands-on Lab Modul 01

Simulasi komparasi teknis:
1. EF Core DbContext & Change Tracker Lifecycle (State Management: Added, Modified, Unchanged, Deleted)
2. Eager Loading (.Include) vs N+1 Lazy Query Pitfall
3. Dapper Micro-ORM Direct Raw SQL & Fast Hydration Pattern
4. Micro-benchmark Eksekusi (EF Core Tracked vs AsNoTracking vs Dapper)
"""

import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

# --- ANSI Terminal Color Formatting ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


def header(title: str) -> None:
    print(f"\n{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} === {title.upper()} === {Style.RESET}")


def subheader(title: str) -> None:
    print(f"\n{Style.CYAN}{Style.BOLD}--- {title} ---{Style.RESET}")


def log_sql(sql: str) -> None:
    print(f"  {Style.YELLOW}[SQL EXECUTED]{Style.RESET} {sql}")


def log_info(msg: str) -> None:
    print(f"  {Style.GREEN}✔{Style.RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"  {Style.MAGENTA}⚡ [CHANGE TRACKER]{Style.RESET} {msg}")


# --- Domain Models ---
class EntityState(Enum):
    DETACHED = "Detached"
    UNCHANGED = "Unchanged"
    ADDED = "Added"
    MODIFIED = "Modified"
    DELETED = "Deleted"


@dataclass
class OrderItem:
    id: int
    product_name: str
    unit_price: float
    quantity: int
    order_id: int


@dataclass
class Customer:
    id: int
    name: str
    email: str


@dataclass
class Order:
    id: int
    customer_id: int
    order_date: str
    items: List[OrderItem] = field(default_factory=list)


# --- In-Memory Raw Database Engine ---
class DatabaseEngine:
    def __init__(self) -> None:
        self.customers: Dict[int, Dict[str, Any]] = {
            1: {"id": 1, "name": "Budi Santoso", "email": "budi@corporate.id"},
            2: {"id": 2, "name": "Siti Nurhaliza", "email": "siti@fintech.id"},
            3: {"id": 3, "name": "Dewi Sartika", "email": "dewi@enterprise.io"},
        }
        self.orders: Dict[int, Dict[str, Any]] = {
            101: {"id": 101, "customer_id": 1, "order_date": "2026-03-01"},
            102: {"id": 102, "customer_id": 1, "order_date": "2026-03-05"},
            103: {"id": 103, "customer_id": 2, "order_date": "2026-03-10"},
        }
        self.order_items: Dict[int, Dict[str, Any]] = {
            1: {"id": 1, "product_name": "SQL Server Core License", "unit_price": 450.0, "quantity": 2, "order_id": 101},
            2: {"id": 2, "product_name": "Azure DevOps Cloud Seat", "unit_price": 30.0, "quantity": 10, "order_id": 101},
            3: {"id": 3, "product_name": "Enterprise RedHat Subscription", "unit_price": 800.0, "quantity": 1, "order_id": 102},
            4: {"id": 4, "product_name": "PostgreSQL Managed Instance", "unit_price": 250.0, "quantity": 1, "order_id": 103},
        }
        self.query_count: int = 0

    def reset_query_counter(self) -> None:
        self.query_count = 0


# Global shared in-memory database
db_engine = DatabaseEngine()


# --- Entity Framework Core Simulated Change Tracker & DbContext ---
@dataclass
class EntityEntry:
    entity: Any
    state: EntityState
    original_values: Dict[str, Any]


class SimulatedDbContext:
    """Simulates EF Core DbContext with Change Tracker, Snapshot Tracking, and Unit of Work pattern."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self.change_tracker: Dict[int, EntityEntry] = {}
        self.next_customer_id = max(self.db.customers.keys()) + 1

    def find_customer(self, customer_id: int, as_no_tracking: bool = False) -> Optional[Customer]:
        self.db.query_count += 1
        log_sql(f"SELECT TOP(1) * FROM Customers WHERE Id = {customer_id}")
        row = self.db.customers.get(customer_id)
        if not row:
            return None

        customer = Customer(id=row["id"], name=row["name"], email=row["email"])
        if not as_no_tracking:
            self.change_tracker[id(customer)] = EntityEntry(
                entity=customer,
                state=EntityState.UNCHANGED,
                original_values={"name": row["name"], "email": row["email"]}
            )
            log_warn(f"Attached Customer #{customer.id} to ChangeTracker [State: {EntityState.UNCHANGED.value}]")
        else:
            log_warn(f"Customer #{customer.id} queried with .AsNoTracking() (Bypass Snapshot Memory Tracker)")

        return customer

    def add_customer(self, customer: Customer) -> None:
        if customer.id <= 0:
            customer.id = self.next_customer_id
            self.next_customer_id += 1
        self.change_tracker[id(customer)] = EntityEntry(
            entity=customer,
            state=EntityState.ADDED,
            original_values={}
        )
        log_warn(f"Customer '{customer.name}' marked as [State: {EntityState.ADDED.value}] in ChangeTracker")

    def remove_customer(self, customer: Customer) -> None:
        entry = self.change_tracker.get(id(customer))
        if entry:
            entry.state = EntityState.DELETED
            log_warn(f"Customer #{customer.id} state transitioned to [State: {EntityState.DELETED.value}]")
        else:
            self.change_tracker[id(customer)] = EntityEntry(
                entity=customer,
                state=EntityState.DELETED,
                original_values={"name": customer.name, "email": customer.email}
            )

    def detect_changes(self) -> None:
        for entry in self.change_tracker.values():
            if entry.state == EntityState.UNCHANGED:
                cust = entry.entity
                if cust.name != entry.original_values["name"] or cust.email != entry.original_values["email"]:
                    entry.state = EntityState.MODIFIED
                    log_warn(f"ChangeTracker.DetectChanges(): Detected mutation on Customer #{cust.id} -> [State: {EntityState.MODIFIED.value}]")

    def save_changes(self) -> int:
        self.detect_changes()
        affected_rows = 0
        print(f"\n  {Style.BOLD}--- EF Core SaveChanges() Transaction Began ---{Style.RESET}")

        for entry in list(self.change_tracker.values()):
            cust: Customer = entry.entity
            if entry.state == EntityState.ADDED:
                self.db.customers[cust.id] = {"id": cust.id, "name": cust.name, "email": cust.email}
                self.db.query_count += 1
                log_sql(f"INSERT INTO Customers (Id, Name, Email) VALUES ({cust.id}, '{cust.name}', '{cust.email}');")
                entry.state = EntityState.UNCHANGED
                entry.original_values = {"name": cust.name, "email": cust.email}
                affected_rows += 1
            elif entry.state == EntityState.MODIFIED:
                self.db.customers[cust.id] = {"id": cust.id, "name": cust.name, "email": cust.email}
                self.db.query_count += 1
                log_sql(f"UPDATE Customers SET Name = '{cust.name}', Email = '{cust.email}' WHERE Id = {cust.id};")
                entry.state = EntityState.UNCHANGED
                entry.original_values = {"name": cust.name, "email": cust.email}
                affected_rows += 1
            elif entry.state == EntityState.DELETED:
                if cust.id in self.db.customers:
                    del self.db.customers[cust.id]
                self.db.query_count += 1
                log_sql(f"DELETE FROM Customers WHERE Id = {cust.id};")
                entry.state = EntityState.DETACHED
                affected_rows += 1

        print(f"  {Style.BOLD}--- Transaction Committed (Total rows affected: {affected_rows}) ---{Style.RESET}\n")
        return affected_rows


# --- Dapper Micro-ORM Simulation Engine ---
class SimulatedDapper:
    """Simulates Dapper's lightweight parameterized raw-SQL mapping & direct POCO hydration."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    def query(self, sql: str, row_mapper: Callable[[Dict[str, Any]], Any], params: Optional[Dict[str, Any]] = None) -> List[Any]:
        self.db.query_count += 1
        log_sql(f"{sql} [Params: {params}]")
        results = []

        if "FROM Customers" in sql:
            for row in self.db.customers.values():
                if params and "Id" in params:
                    if row["id"] == params["Id"]:
                        results.append(row_mapper(row))
                else:
                    results.append(row_mapper(row))
        elif "FROM Orders" in sql:
            for row in self.db.orders.values():
                if params and "CustomerId" in params:
                    if row["customer_id"] == params["CustomerId"]:
                        results.append(row_mapper(row))
                else:
                    results.append(row_mapper(row))
        elif "FROM OrderItems" in sql:
            for row in self.db.order_items.values():
                if params and "OrderId" in params:
                    if row["order_id"] == params["OrderId"]:
                        results.append(row_mapper(row))
                else:
                    results.append(row_mapper(row))
        return results

    def execute(self, sql: str, params: Dict[str, Any]) -> int:
        self.db.query_count += 1
        log_sql(f"{sql} [Params: {params}]")
        if "UPDATE Customers" in sql:
            cid = params.get("Id")
            if cid in self.db.customers:
                self.db.customers[cid]["name"] = params["Name"]
                self.db.customers[cid]["email"] = params["Email"]
                return 1
        return 0


# --- Interactive Scenario Implementations ---
def demo_ef_change_tracker() -> None:
    header("Demonstrasi 1: EF Core DbContext & Change Tracking Lifecycle")
    context = SimulatedDbContext(db_engine)

    print(f"{Style.CYAN}Step 1: Mengambil Customer #1 dari database dengan tracking default...{Style.RESET}")
    customer = context.find_customer(1)
    if not customer:
        print("Customer tidak ditemukan!")
        return

    print(f"Data terbaca: {customer.name} ({customer.email})")

    print(f"\n{Style.CYAN}Step 2: Melakukan mutasi pada property entity di memori...{Style.RESET}")
    customer.name = "Budi Santoso, M.Kom (Updated)"
    customer.email = "budi.santoso@corporate.id"
    log_info("Properti entity lokal dimutasi. Database belum tersentuh!")

    print(f"\n{Style.CYAN}Step 3: Memanggil context.SaveChanges() (Unit of Work)...{Style.RESET}")
    rows = context.save_changes()
    log_info(f"Database terupdate otomatis melalui ChangeTracker snapshot comparison! Rows affected: {rows}")

    print(f"\n{Style.CYAN}Step 4: Menambahkan Customer baru ke dalam DbSet...{Style.RESET}")
    new_customer = Customer(id=0, name="Rian Pratama", email="rian@cloudnative.dev")
    context.add_customer(new_customer)
    context.save_changes()
    log_info(f"Customer baru tersimpan dengan ID: {new_customer.id}")


def demo_n_plus_one_vs_eager() -> None:
    header("Demonstrasi 2: N+1 Query Problem vs Eager Loading (.Include)")

    # Skenario A: N+1 Problem (Lazy-loading style)
    subheader("Skenario A: N+1 Pitfall (Naive loop query)")
    db_engine.reset_query_counter()

    log_sql("SELECT * FROM Customers; -- Initial query (1)")
    customers = [Customer(**c) for c in db_engine.customers.values()]
    db_engine.query_count += 1

    for cust in customers:
        log_sql(f"SELECT * FROM Orders WHERE CustomerId = {cust.id}; -- Query for Customer #{cust.id}")
        db_engine.query_count += 1
        orders = [o for o in db_engine.orders.values() if o["customer_id"] == cust.id]
        for o in orders:
            log_sql(f"SELECT * FROM OrderItems WHERE OrderId = {o['id']}; -- Sub-query items for Order #{o['id']}")
            db_engine.query_count += 1

    print(f"{Style.RED}{Style.BOLD}Total Queries Terbakar (N+1 Problem): {db_engine.query_count} Round-Trips ke Database!{Style.RESET}")

    # Skenario B: EF Core Eager Loading (.Include, .ThenInclude)
    subheader("Skenario B: EF Core Eager Loading (.Include & .ThenInclude)")
    db_engine.reset_query_counter()

    log_sql("""SELECT c.Id, c.Name, c.Email, o.Id, o.OrderDate, oi.Id, oi.ProductName, oi.UnitPrice, oi.Quantity
FROM Customers AS c
LEFT JOIN Orders AS o ON c.Id = o.CustomerId
LEFT JOIN OrderItems AS oi ON o.Id = oi.OrderId
ORDER BY c.Id, o.Id;""")
    db_engine.query_count = 1

    log_info("EF Core mengkompilasi expression tree menjadi single JOIN projection.")
    print(f"{Style.GREEN}{Style.BOLD}Total Queries Eager Loading: {db_engine.query_count} Round-Trip ke Database!{Style.RESET}")


def demo_dapper_raw_sql() -> None:
    header("Demonstrasi 3: Dapper Micro-ORM Raw SQL & High-Performance Mapping")
    dapper = SimulatedDapper(db_engine)

    print(f"{Style.CYAN}1. Eksekusi Dapper Query<Customer>() dengan Raw Parameterized SQL:{Style.RESET}")
    sql_query = "SELECT Id, Name, Email FROM Customers WHERE Id = @Id"
    customers = dapper.query(
        sql_query,
        lambda row: Customer(id=row["id"], name=row["name"], email=row["email"]),
        {"Id": 2}
    )
    for c in customers:
        log_info(f"Dapper Hydrated POCO directly: ID={c.id}, Name='{c.name}', Email='{c.email}'")

    print(f"\n{Style.CYAN}2. Eksekusi Dapper Execute() untuk Fast Update:{Style.RESET}")
    sql_update = "UPDATE Customers SET Name = @Name, Email = @Email WHERE Id = @Id"
    affected = dapper.execute(sql_update, {"Id": 2, "Name": "Siti Nurhaliza, ST", "Email": "siti.n@fintech.id"})
    log_info(f"Dapper direct Command Execute selesai. Rows affected: {affected}")


def demo_benchmark_comparison() -> None:
    header("Demonstrasi 4: Benchmark Simulasi Komparatif (1,000 Iterasi)")
    iterations = 1000

    print(f"Menjalankan benchmark throughput simulasi {iterations:,} pembacaan data...")

    # Benchmark 1: EF Core Tracking
    t0 = time.perf_counter()
    ctx_tracked = SimulatedDbContext(db_engine)
    for _ in range(iterations):
        _ = ctx_tracked.find_customer(1, as_no_tracking=False)
    t_ef_tracked = (time.perf_counter() - t0) * 1000

    # Benchmark 2: EF Core AsNoTracking
    t0 = time.perf_counter()
    ctx_untracked = SimulatedDbContext(db_engine)
    for _ in range(iterations):
        _ = ctx_untracked.find_customer(1, as_no_tracking=True)
    t_ef_notracking = (time.perf_counter() - t0) * 1000

    # Benchmark 3: Dapper Micro-ORM
    t0 = time.perf_counter()
    dapper = SimulatedDapper(db_engine)
    for _ in range(iterations):
        _ = dapper.query(
            "SELECT * FROM Customers WHERE Id = @Id",
            lambda r: Customer(r["id"], r["name"], r["email"]),
            {"Id": 1}
        )
    t_dapper = (time.perf_counter() - t0) * 1000

    print(f"\n{Style.BOLD}HASIL BENCHMARK RELATIF (Latency Total):{Style.RESET}")
    print(f"  1. EF Core (Full Change Tracking) : {Style.RED}{t_ef_tracked:.2f} ms{Style.RESET} (Tinggi overhead snapshot memori)")
    print(f"  2. EF Core (.AsNoTracking())      : {Style.YELLOW}{t_ef_notracking:.2f} ms{Style.RESET} (~35-45% lebih ringan, read-only optimized)")
    print(f"  3. Dapper Micro-ORM (Raw Mapper)  : {Style.GREEN}{t_dapper:.2f} ms{Style.RESET} (Tercepat, zero tracking overhead, ideal CQRS Read)")


def interactive_menu() -> None:
    while True:
        print(f"\n{Style.BOLD}{Style.WHITE}╔═══════════════════════════════════════════════════════════════╗{Style.RESET}")
        print(f"{Style.BOLD}{Style.WHITE}║     ASP.NET Core: EF Core vs Dapper Architecture Lab Lab     ║{Style.RESET}")
        print(f"{Style.BOLD}{Style.WHITE}╚═══════════════════════════════════════════════════════════════╝{Style.RESET}")
        print(f" [{Style.CYAN}1{Style.RESET}] EF Core DbContext & Change Tracking Lifecycle")
        print(f" [{Style.CYAN}2{Style.RESET}] N+1 Query Problem vs Eager Loading (.Include)")
        print(f" [{Style.CYAN}3{Style.RESET}] Dapper Micro-ORM Raw SQL & Fast Hydration")
        print(f" [{Style.CYAN}4{Style.RESET}] Benchmark Overhead: EF Core vs AsNoTracking vs Dapper")
        print(f" [{Style.CYAN}5{Style.RESET}] Jalankan Semua Simulasi Otomatis")
        print(f" [{Style.RED}0{Style.RESET}] Keluar")
        print("-" * 65)

        try:
            choice = input(f"{Style.BOLD}Pilih menu [0-5]: {Style.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting lab.")
            break

        if choice == "1":
            demo_ef_change_tracker()
        elif choice == "2":
            demo_n_plus_one_vs_eager()
        elif choice == "3":
            demo_dapper_raw_sql()
        elif choice == "4":
            demo_benchmark_comparison()
        elif choice == "5":
            demo_ef_change_tracker()
            demo_n_plus_one_vs_eager()
            demo_dapper_raw_sql()
            demo_benchmark_comparison()
            log_info("Semua demonstrasi teknis berhasil dieksekusi dengan sempurna.")
        elif choice == "0":
            print(f"{Style.GREEN}Terima kasih telah mempelajari arsitektur data access ASP.NET Core!{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid, silakan masukkan angka 0-5.{Style.RESET}")


if __name__ == "__main__":
    interactive_menu()
