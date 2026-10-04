#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive Java Data Persistence, ORM & Database Tuning
Bab 05: Data Persistence, ORM & Database Performance Tuning
Modul 02: Arsitektur Internal JPA/Hibernate, L1 Cache, Dirty Checking, & Query Optimization

Deskripsi:
Script ini mensimulasikan mekanisme inti Hibernate/JPA engine:
1. First-Level Cache (L1 Cache / Identity Map) & Snapshot-based Dirty Checking.
2. The N+1 Select Problem vs. Query Fetch Tuning (JOIN / Batch In-Clause).
3. JDBC Write Batching Optimization vs. Single-statement execution.
Menggunakan SQLite in-memory dengan telemetri SQL Query Counter nyata.
"""

import sqlite3
import time
import copy
from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"

# ==============================================================================
# 1. DATABASE & TELEMETRY LAYER (Simulasi Driver JDBC & Database Server)
# ==============================================================================

class DatabaseDriver:
    """Wrapper SQLite untuk tracking statement round-trip ke DB engine."""
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()
        self.query_count = 0
        self.log_queries = True

    def execute(self, sql: str, params: Tuple = ()) -> sqlite3.Cursor:
        self.query_count += 1
        if self.log_queries:
            print(f"  {CLR_CYAN}[SQL Execute #{self.query_count}]{CLR_RESET} {sql} | Params: {params}")
        return self.cursor.execute(sql, params)

    def executemany(self, sql: str, param_list: List[Tuple]) -> sqlite3.Cursor:
        self.query_count += 1
        if self.log_queries:
            print(f"  {CLR_CYAN}[SQL Batch Execute #{self.query_count}]{CLR_RESET} {sql} | Batch Size: {len(param_list)}")
        return self.cursor.executemany(sql, param_list)

    def reset_counter(self):
        self.query_count = 0

    def init_schema(self):
        self.log_queries = False
        self.cursor.execute("""
            CREATE TABLE authors (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                country TEXT NOT NULL
            )
        """)
        self.cursor.execute("""
            CREATE TABLE books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author_id INTEGER,
                FOREIGN KEY (author_id) REFERENCES authors (id)
            )
        """)
        self.conn.commit()
        self.log_queries = True


# ==============================================================================
# 2. JPA / HIBERNATE DOMAIN MODELS
# ==============================================================================

@dataclass
class Book:
    id: int
    title: str
    author_id: int

@dataclass
class Author:
    id: int
    name: str
    country: str
    books: List[Book] = field(default_factory=list)


# ==============================================================================
# 3. ORM ENGINE: ENTITY MANAGER (L1 Cache & Dirty Checking Engine)
# ==============================================================================

class EntityManager:
    """
    Simulasi JPA EntityManager / Hibernate Session:
    - Persistence Context / L1 Cache
    - Snapshot Map (untuk Dirty Checking saat flush/commit)
    """
    def __init__(self, db: DatabaseDriver):
        self.db = db
        # L1 Cache: (EntityClass, PK) -> Entity Instance
        self.l1_cache: Dict[Tuple[type, Any], Any] = {}
        # Snapshot state: (EntityClass, PK) -> Dict representation
        self.entity_snapshots: Dict[Tuple[type, Any], Dict[str, Any]] = {}

    def find(self, entity_class: type, pk: Any) -> Optional[Any]:
        """Implementasi find() dengan L1 Cache lookup."""
        cache_key = (entity_class, pk)
        
        # 1. First-Level Cache Hit
        if cache_key in self.l1_cache:
            print(f"  {CLR_GREEN}[L1 CACHE HIT]{CLR_RESET} Entity {entity_class.__name__} ID={pk} diambil dari Session Memory.")
            return self.l1_cache[cache_key]

        # 2. Cache Miss -> Query Database
        print(f"  {CLR_YELLOW}[L1 CACHE MISS]{CLR_RESET} Query ke Database untuk {entity_class.__name__} ID={pk}...")
        if entity_class == Author:
            cur = self.db.execute("SELECT id, name, country FROM authors WHERE id = ?", (pk,))
            row = cur.fetchone()
            if not row:
                return None
            entity = Author(id=row[0], name=row[1], country=row[2])
        elif entity_class == Book:
            cur = self.db.execute("SELECT id, title, author_id FROM books WHERE id = ?", (pk,))
            row = cur.fetchone()
            if not row:
                return None
            entity = Book(id=row[0], title=row[1], author_id=row[2])
        else:
            raise NotImplementedError("Entity tidak didukung.")

        # Simpan di L1 Cache dan rekam snapshot
        self.l1_cache[cache_key] = entity
        self._record_snapshot(cache_key, entity)
        return entity

    def _record_snapshot(self, key: Tuple[type, Any], entity: Any):
        """Menyimpan snapshot murni dari atribut entity untuk dirty checking."""
        if isinstance(entity, Author):
            self.entity_snapshots[key] = {"id": entity.id, "name": entity.name, "country": entity.country}
        elif isinstance(entity, Book):
            self.entity_snapshots[key] = {"id": entity.id, "title": entity.title, "author_id": entity.author_id}

    def flush(self):
        """
        Simulasi Hibernate Flush Phase:
        Memeriksa setiap entity yang dikelola terhadap snapshot-nya (Dirty Checking).
        Jika ada perbedaan state, generate dan eksekusi UPDATE SQL otomatis.
        """
        print(f"{CLR_BOLD}--- Memulai Entity Manager Flush & Dirty Checking ---{CLR_RESET}")
        updates_detected = 0

        for key, entity in self.l1_cache.items():
            if key not in self.entity_snapshots:
                continue

            snapshot = self.entity_snapshots[key]
            entity_class, pk = key

            if entity_class == Author:
                current_state = {"id": entity.id, "name": entity.name, "country": entity.country}
                # Bandingkan snapshot dengan state saat ini
                if current_state != snapshot:
                    updates_detected += 1
                    print(f"  {CLR_YELLOW}[DIRTY CHECK DETECTED]{CLR_RESET} Author ID={pk} termodifikasi: "
                          f"{snapshot} -> {current_state}")
                    self.db.execute(
                        "UPDATE authors SET name = ?, country = ? WHERE id = ?",
                        (entity.name, entity.country, pk)
                    )
                    # Update snapshot terbaru
                    self.entity_snapshots[key] = copy.deepcopy(current_state)

        if updates_detected == 0:
            print(f"  {CLR_GREEN}[FLUSH COMPLETE]{CLR_RESET} Tidak ada managed entity yang kotor (Clean Session).")
        else:
            print(f"  {CLR_GREEN}[FLUSH COMPLETE]{CLR_RESET} {updates_detected} entity berhasil di-sinkronisasi ke DB.")

    def clear(self):
        """Menghapus context session (evict all)."""
        self.l1_cache.clear()
        self.entity_snapshots.clear()
        print(f"  {CLR_BLUE}[SESSION CLEARED]{CLR_RESET} L1 Cache & Snapshots dikosongkan.")


# ==============================================================================
# 4. BENCHMARK & DEMONSTRATION SUITES
# ==============================================================================

def seed_database(db: DatabaseDriver, num_authors: int = 5, books_per_author: int = 3):
    """Mengisi initial data ke tabel authors dan books."""
    db.log_queries = False
    for a_id in range(1, num_authors + 1):
        db.cursor.execute("INSERT INTO authors VALUES (?, ?, ?)",
                          (a_id, f"Author_{a_id}", f"Country_{a_id % 3}"))
        for b_id in range(1, books_per_author + 1):
            global_book_id = (a_id - 1) * books_per_author + b_id
            db.cursor.execute("INSERT INTO books VALUES (?, ?, ?)",
                              (global_book_id, f"High-Performance Java Vol {global_book_id}", a_id))
    db.conn.commit()
    db.log_queries = True

def run_lab_l1_and_dirty_checking(db: DatabaseDriver):
    """
    Lab 1: Membuktikan L1 Cache meniadakan redundant queries,
    dan Automatic Dirty Checking melakukan update tanpa manual update statement.
    """
    print(f"\n{CLR_BOLD}{CLR_BLUE}======================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}LAB 1: L1 CACHE & SNAPSHOT-BASED DIRTY CHECKING DEMO{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================{CLR_RESET}")
    
    em = EntityManager(db)
    db.reset_counter()

    # Step 1: First find triggers DB query
    print("\n[Langkah 1] Memanggil em.find(Author, 1):")
    author1 = em.find(Author, 1)

    # Step 2: Second find should hit L1 Cache (No SQL query)
    print("\n[Langkah 2] Memanggil kembali em.find(Author, 1) dalam session yang sama:")
    author1_again = em.find(Author, 1)
    assert author1 is author1_again, "Instance harus identical pointer!"
    print(f"  {CLR_GREEN}Verification: author1 is author1_again -> TRUE (Identical Reference){CLR_RESET}")

    # Step 3: Modifikasi atribut tanpa manual SQL update (Dirty State)
    print("\n[Langkah 3] Memodifikasi entity author1.name secara langsung di memori:")
    print(f"  Nama lama: '{author1.name}' -> Nama baru: 'Martin Kleppmann'")
    author1.name = "Martin Kleppmann"

    # Step 4: Flush transaction
    print("\n[Langkah 4] Melakukan em.flush() (Hibernate Commit Phase):")
    em.flush()

    # Step 5: Flush lagi tanpa modifikasi (Idempotent / No Query)
    print("\n[Langkah 5] Melakukan em.flush() kedua kali tanpa perubahan data:")
    em.flush()
    print(f"Total SQL dipicu selama Lab 1: {CLR_BOLD}{db.query_count}{CLR_RESET} queries.")


def run_lab_n_plus_one_problem(db: DatabaseDriver):
    """
    Lab 2: The Dreaded N+1 Problem
    Menampilkan query blast ketika lazy-loading dieksekusi dalam loop.
    """
    print(f"\n{CLR_BOLD}{CLR_RED}======================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_RED}LAB 2: THE N+1 QUERY PROBLEM (NAIVE LAZY LOADING){CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_RED}======================================================{CLR_RESET}")

    db.reset_counter()
    print("Skenario: Mengambil semua Author (1 query), lalu loop child books (N query)...\n")

    # 1 Query utama
    authors_cur = db.execute("SELECT id, name, country FROM authors")
    authors = [Author(id=r[0], name=r[1], country=r[2]) for r in authors_cur.fetchall()]

    # Loop pemicu N Queries (Lazy Loading simulation)
    for author in authors:
        books_cur = db.execute("SELECT id, title, author_id FROM books WHERE author_id = ?", (author.id,))
        author.books = [Book(id=b[0], title=b[1], author_id=b[2]) for b in books_cur.fetchall()]

    print(f"\n{CLR_RED}[N+1 ISSUE SUMMARY]{CLR_RESET}")
    print(f"Total Authors = {len(authors)} | Total SQL Round-trips = {db.query_count} (1 + {len(authors)})")


def run_lab_query_fetch_tuning(db: DatabaseDriver):
    """
    Lab 3: Solusi N+1 Menggunakan JOIN FETCH & IN-Clause Batch Fetching
    """
    print(f"\n{CLR_BOLD}{CLR_GREEN}======================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}LAB 3: QUERY TUNING (JOIN FETCH & BATCH IN-CLAUSE){CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}======================================================{CLR_RESET}")

    # Solusi A: JOIN FETCH (1 Query Total)
    print(f"\n{CLR_BOLD}Teknik A: Hibernate 'JOIN FETCH' Simulasi (1 Round-trip){CLR_RESET}")
    db.reset_counter()

    sql = """
        SELECT a.id, a.name, a.country, b.id, b.title, b.author_id
        FROM authors a
        LEFT JOIN books b ON a.id = b.author_id
    """
    cur = db.execute(sql)
    authors_map: Dict[int, Author] = {}

    for row in cur.fetchall():
        a_id, a_name, a_country, b_id, b_title, b_author_id = row
        if a_id not in authors_map:
            authors_map[a_id] = Author(id=a_id, name=a_name, country=a_country)
        if b_id is not None:
            authors_map[a_id].books.append(Book(id=b_id, title=b_title, author_id=b_author_id))

    print(f"  Hasil: Berhasil load {len(authors_map)} authors beserta buku-bukunya.")
    print(f"  {CLR_GREEN}Total SQL dipicu dengan JOIN FETCH: {db.query_count} query!{CLR_RESET}")

    # Solusi B: Batch Fetching @BatchSize(size = 5)
    print(f"\n{CLR_BOLD}Teknik B: Hibernate @BatchSize Optimization (2 Round-trips){CLR_RESET}")
    db.reset_counter()

    # 1. Load semua authors
    cur = db.execute("SELECT id, name, country FROM authors")
    authors_list = [Author(id=r[0], name=r[1], country=r[2]) for r in cur.fetchall()]
    author_ids = [a.id for a in authors_list]

    # 2. Fetch children sekaligus menggunakan `IN (?, ?, ...)`
    placeholders = ",".join("?" for _ in author_ids)
    sql_batch = f"SELECT id, title, author_id FROM books WHERE author_id IN ({placeholders})"
    b_cur = db.execute(sql_batch, tuple(author_ids))
    
    books_by_author: Dict[int, List[Book]] = {a_id: [] for a_id in author_ids}
    for row in b_cur.fetchall():
        books_by_author[row[2]].append(Book(id=row[0], title=row[1], author_id=row[2]))

    for a in authors_list:
        a.books = books_by_author[a.id]

    print(f"  Hasil: Berhasil mem-batch fetch child collections.")
    print(f"  {CLR_GREEN}Total SQL dipicu dengan BatchSize: {db.query_count} queries (1 author + 1 batch-book)!{CLR_RESET}")


def run_lab_batch_write_tuning(db: DatabaseDriver):
    """
    Lab 4: JDBC Statement Batching (hibernate.jdbc.batch_size).
    Membandingkan 500 Single Inserts vs. Batched Inserts.
    """
    print(f"\n{CLR_BOLD}{CLR_CYAN}======================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}LAB 4: JDBC BATCHING TUNING (WRITE OPTIMIZATION){CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================{CLR_RESET}")

    item_count = 500
    dataset = [(i + 1000, f"Bulk Book {i}", 1) for i in range(item_count)]

    # 1. Non-batched (1-by-1 insert)
    db.log_queries = False
    start_single = time.perf_counter()
    for row in dataset:
        db.cursor.execute("INSERT INTO books VALUES (?, ?, ?)", row)
    db.conn.commit()
    elapsed_single = time.perf_counter() - start_single

    # Cleanup dataset bulk
    db.cursor.execute("DELETE FROM books WHERE id >= 1000")
    db.conn.commit()

    # 2. Batched insert (JDBC executemany)
    start_batch = time.perf_counter()
    db.cursor.executemany("INSERT INTO books VALUES (?, ?, ?)", dataset)
    db.conn.commit()
    elapsed_batch = time.perf_counter() - start_batch
    db.log_queries = True

    print(f"Benchmark: Menyimpan {item_count} Records ke Database:")
    print(f"  1. Non-batched Insert: {CLR_RED}{elapsed_single*1000:.2f} ms{CLR_RESET}")
    print(f"  2. Batched Insert    : {CLR_GREEN}{elapsed_batch*1000:.2f} ms{CLR_RESET}")
    speedup = (elapsed_single / elapsed_batch) if elapsed_batch > 0 else 1.0
    print(f"  {CLR_YELLOW}Speedup Ratio: {speedup:.2f}x lebih cepat dengan statement batching.{CLR_RESET}")


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

def main():
    print(f"{CLR_BOLD}{CLR_CYAN}Starting Advanced Java Data Persistence & ORM Tuning Lab...{CLR_RESET}")
    
    # Inisialisasi Database In-Memory
    db = DatabaseDriver()
    db.init_schema()
    seed_database(db, num_authors=5, books_per_author=3)

    # Menjalankan modul-modul praktikum
    run_lab_l1_and_dirty_checking(db)
    run_lab_n_plus_one_problem(db)
    run_lab_query_fetch_tuning(db)
    run_lab_batch_write_tuning(db)

    print(f"\n{CLR_BOLD}{CLR_GREEN}Seluruh Modul Hands-on Lab Telah Selesai Dijalankan dengan Sukses.{CLR_RESET}")

if __name__ == "__main__":
    main()