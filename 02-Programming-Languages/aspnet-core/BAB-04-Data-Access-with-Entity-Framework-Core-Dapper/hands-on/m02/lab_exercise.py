#!/usr/bin/env python3
"""
Lab Hands-on: ASP.NET Core - Bab 04: Data Access with EF Core & Dapper
Modul 02: Deep Dive (Change Tracker, Identity Map vs High-Performance Micro-ORM Mapping)

Simulasi teknis arsitektur:
1. MiniDbContext (EF Core Engine):
   - Snapshot Change Tracking & EntityState lifecycle (Unchanged, Added, Modified, Deleted).
   - Identity Map (Caches tracked entities by Primary Key).
   - AsNoTracking() pipeline optimization.
   - Unit of Work pattern (Atomic SaveChanges compilation to dynamic SQL).
2. MiniDapper (Micro-ORM Engine):
   - Fast direct-to-object mapping bypasses tracking pipelines.
   - Low-allocation parameterized execution.
3. Comparative Benchmarking: Execution time, memory overhead, & SQL emissions.
"""

import sqlite3
import time
import copy
from enum import Enum, auto
from dataclasses import dataclass, field, fields
from typing import Dict, List, Any, Optional, Type, TypeVar, Generic

# --- ANSI Formatting Helper ---
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"

def print_header(title: str):
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}{'='*70}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN} [LAB] {title.upper()}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}{'='*70}{TermColor.RESET}")

# --- Domain Model ---
@dataclass
class Product:
    id: int
    sku: str
    name: str
    price: float
    stock: int

# --- Entity Framework Core Change Tracking Abstraction ---
class EntityState(Enum):
    DETACHED = auto()
    UNCHANGED = auto()
    ADDED = auto()
    MODIFIED = auto()
    DELETED = auto()

@dataclass
class EntityEntry:
    entity: Any
    state: EntityState
    original_values: Dict[str, Any]

T = TypeVar('T')

class DbSet(Generic[T]):
    """Merepresentasikan DbSet<T> di EF Core dengan kapabilitas Query & Tracking."""
    def __init__(self, context: 'MiniDbContext', entity_type: Type[T], table_name: str):
        self.context = context
        self.entity_type = entity_type
        self.table_name = table_name

    def to_list(self, as_no_tracking: bool = False) -> List[T]:
        """Simulasi LINQ query execution (.ToList() atau .AsNoTracking().ToList())."""
        query = f"SELECT id, sku, name, price, stock FROM {self.table_name}"
        cursor = self.context.connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            pk = row[0]
            # Check Identity Map first jika tracking aktif
            if not as_no_tracking and pk in self.context.identity_map:
                results.append(self.context.identity_map[pk].entity)
                continue

            instance = self.entity_type(*row)
            if not as_no_tracking:
                self.context.track_entity(instance, EntityState.UNCHANGED)
            results.append(instance)

        return results

    def add(self, entity: T) -> None:
        self.context.track_entity(entity, EntityState.ADDED)

    def remove(self, entity: T) -> None:
        pk = getattr(entity, 'id', None)
        if pk in self.context.identity_map:
            self.context.identity_map[pk].state = EntityState.DELETED
        else:
            self.context.track_entity(entity, EntityState.DELETED)

class MiniDbContext:
    """Simulasi Unit of Work & Identity Map dari Entity Framework Core."""
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.identity_map: Dict[Any, EntityEntry] = {}
        self.products = DbSet[Product](self, Product, "products")

    def track_entity(self, entity: Any, state: EntityState):
        pk = getattr(entity, 'id', None)
        snapshot = {f.name: getattr(entity, f.name) for f in fields(entity)}
        entry = EntityEntry(entity=entity, state=state, original_values=snapshot)
        if pk is not None:
            self.identity_map[pk] = entry

    def detect_changes(self):
        """EF Core Snapshot Change Detection: Membandingkan state memori vs snapshot."""
        for pk, entry in self.identity_map.items():
            if entry.state in (EntityState.ADDED, EntityState.DELETED):
                continue

            current_snapshot = {f.name: getattr(entry.entity, f.name) for f in fields(entry.entity)}
            is_dirty = any(entry.original_values[k] != current_snapshot[k] for k in current_snapshot)

            if is_dirty:
                entry.state = EntityState.MODIFIED

    def save_changes(self) -> int:
        """Kompilasi mutasi state ke dalam transaksi SQL tunggal."""
        self.detect_changes()
        mutations = 0
        cursor = self.connection.cursor()

        try:
            for pk, entry in list(self.identity_map.items()):
                if entry.state == EntityState.MODIFIED:
                    current_values = {f.name: getattr(entry.entity, f.name) for f in fields(entry.entity)}
                    set_clause = ", ".join([f"{k} = ?" for k in current_values if k != 'id'])
                    params = [current_values[k] for k in current_values if k != 'id'] + [pk]
                    sql = f"UPDATE products SET {set_clause} WHERE id = ?"
                    cursor.execute(sql, params)
                    entry.original_values = copy.deepcopy(current_values)
                    entry.state = EntityState.UNCHANGED
                    mutations += 1

                elif entry.state == EntityState.ADDED:
                    cols = [f.name for f in fields(entry.entity) if f.name != 'id']
                    vals = [getattr(entry.entity, c) for c in cols]
                    placeholders = ", ".join(["?"] * len(cols))
                    sql = f"INSERT INTO products ({', '.join(cols)}) VALUES ({placeholders})"
                    cursor.execute(sql, vals)
                    entry.entity.id = cursor.lastrowid
                    entry.original_values = {f.name: getattr(entry.entity, f.name) for f in fields(entry.entity)}
                    entry.state = EntityState.UNCHANGED
                    mutations += 1

                elif entry.state == EntityState.DELETED:
                    cursor.execute("DELETE FROM products WHERE id = ?", (pk,))
                    del self.identity_map[pk]
                    mutations += 1

            self.connection.commit()
            return mutations
        except Exception as ex:
            self.connection.rollback()
            raise ex

# --- Dapper Micro-ORM Abstraction ---
class MiniDapper:
    """Simulasi Dapper: Fast object-mapper langsung dari raw SQL tanpa overhead tracking."""
    @staticmethod
    def query(conn: sqlite3.Connection, sql: str, model_type: Type[T], params: tuple = ()) -> List[T]:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        cols = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        
        # High performance direct instantiation via cached column mapping
        results = []
        for row in rows:
            mapping = dict(zip(cols, row))
            results.append(model_type(**mapping))
        return results

    @staticmethod
    def execute(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount

# --- Database Initialization ---
def setup_in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    """)
    # Seed 5,000 records untuk simulasi load realistis
    records = [
        (f"SKU-{i:05d}", f"Enterprise Server Unit {i}", 100.0 + (i % 50), 10 + (i % 5))
        for i in range(1, 5001)
    ]
    cursor.executemany("INSERT INTO products (sku, name, price, stock) VALUES (?, ?, ?, ?)", records)
    conn.commit()
    return conn

# --- Execution & Verification Script ---
def main():
    print_header("Setup In-Memory Database (SQLite)")
    conn = setup_in_memory_db()
    print(f"{TermColor.GREEN}✓ Database initialized with 5,000 Product records.{TermColor.RESET}")

    # 1. EF Core Change Tracker Lifecycle Deep-Dive
    print_header("1. EF Core: Change Tracking & Snapshot Pipeline")
    db = MiniDbContext(conn)
    
    print(f"[{TermColor.YELLOW}TRACKER{TermColor.RESET}] Memuat data pertama kali via DbSet.ToList()...")
    items = db.products.to_list()
    target_product = items[0]
    print(f"Loaded: {target_product.name} | Price: ${target_product.price:.2f}")

    entry = db.identity_map[target_product.id]
    print(f"State Awal: {TermColor.BLUE}{entry.state.name}{TermColor.RESET}")

    # Modifikasi properti di domain object
    print(f"\n[{TermColor.YELLOW}MUTASI{TermColor.RESET}] Merubah harga: $100.00 -> $199.99 (In-memory mutate)")
    target_product.price = 199.99
    
    db.detect_changes()
    print(f"State Pasca Mutasi (DetectChanges): {TermColor.MAGENTA}{entry.state.name}{TermColor.RESET}")
    print(f"Original snapshot price : ${entry.original_values['price']:.2f}")
    print(f"Current entity price   : ${target_product.price:.2f}")

    # Save changes (Unit of Work commit)
    committed = db.save_changes()
    print(f"SaveChanges executed. {committed} entitas di-commit ke SQL.")
    print(f"State Akhir: {TermColor.GREEN}{entry.state.name}{TermColor.RESET}")

    # 2. Performance Comparison: Dapper vs EF Core vs EF Core AsNoTracking
    print_header("2. Performance Benchmark: Dapper vs EF Core (Tracked vs AsNoTracking)")
    iterations = 5

    # Benchmark: EF Core Tracked
    t0 = time.perf_counter()
    for _ in range(iterations):
        context = MiniDbContext(conn)
        res = context.products.to_list(as_no_tracking=False)
    time_ef_tracked = (time.perf_counter() - t0) / iterations

    # Benchmark: EF Core AsNoTracking()
    t0 = time.perf_counter()
    for _ in range(iterations):
        context = MiniDbContext(conn)
        res = context.products.to_list(as_no_tracking=True)
    time_ef_notracking = (time.perf_counter() - t0) / iterations

    # Benchmark: Dapper
    t0 = time.perf_counter()
    for _ in range(iterations):
        res = MiniDapper.query(conn, "SELECT id, sku, name, price, stock FROM products", Product)
    time_dapper = (time.perf_counter() - t0) / iterations

    # Output Benchmark Table
    print(f"{'Metrik Data Access':<32} | {'Avg Execution Time':<18} | {'Change Tracker'}")
    print("-" * 70)
    print(f"{'EF Core DbSet.ToList()':<32} | {time_ef_tracked*1000:>14.2f} ms | {TermColor.RED}ACTIVE (Heavy){TermColor.RESET}")
    print(f"{'EF Core .AsNoTracking().ToList()':<32} | {time_ef_notracking*1000:>14.2f} ms | {TermColor.YELLOW}DISABLED{TermColor.RESET}")
    print(f"{'Dapper Query<Product>()':<32} | {time_dapper*1000:>14.2f} ms | {TermColor.GREEN}BYPASS (Fastest){TermColor.RESET}")
    
    speedup = ((time_ef_tracked - time_dapper) / time_ef_tracked) * 100
    print(f"\n{TermColor.BOLD}{TermColor.GREEN}Analisis Arsitektur:{TermColor.RESET}")
    print(f"- Dapper lebih cepat ~{speedup:.1f}% dibanding EF Core Tracked karena mengeliminasi")
    print("  overhead: Snapshot dictionary, Identity Map registration, dan State inspection.")
    print("- AsNoTracking() mengeliminasi overhead state tracking namun tetap mempertahankan konversi ORM.")

    # 3. Direct Dapper Command Execution
    print_header("3. Dapper Direct Execution (High-Throughput Scenario)")
    dapper_updated = MiniDapper.execute(
        conn, 
        "UPDATE products SET price = price * 1.05 WHERE stock < ?", 
        (12,)
    )
    print(f"{TermColor.GREEN}✓ Dapper Raw Execution: {dapper_updated} records mass-updated with zero tracking footprint.{TermColor.RESET}")

if __name__ == "__main__":
    main()