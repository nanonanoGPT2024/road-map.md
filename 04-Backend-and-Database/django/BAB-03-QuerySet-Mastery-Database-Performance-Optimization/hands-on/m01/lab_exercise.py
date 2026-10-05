#!/usr/bin/env python3
"""
Lab Exercise M01: Django QuerySet Mastery & Database Performance Optimization
Simulasi Standalone: Evaluasi Lazy, N+1 Problem, select_related, prefetch_related, & Query Caching.
"""

import time
import sqlite3
from typing import List, Dict, Any, Optional

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class SQLQueryLogger:
    """Melacak eksekusi SQL mirip dengan django.db.connection.queries."""
    def __init__(self):
        self.queries: List[Dict[str, Any]] = []

    def log(self, sql: str, duration_ms: float):
        self.queries.append({"sql": sql.strip(), "time": duration_ms})
        print(f"  {DIM}[SQL LOG]{RESET} {MAGENTA}{sql.strip()}{RESET} ({YELLOW}{duration_ms:.2f}ms{RESET})")

    def reset(self):
        self.queries.clear()

    @property
    def count(self) -> int:
        return len(self.queries)

    @property
    def total_time(self) -> float:
        return sum(q["time"] for q in self.queries)


# Global logger instance
db_logger = SQLQueryLogger()


class DatabaseSetup:
    """Inisialisasi SQLite in-memory untuk simulasi relational Django."""
    @staticmethod
    def get_connection():
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        
        # Schema: Author -> Book (1:N), Book -> Tag (M:N via BookTags)
        cursor.execute("""
            CREATE TABLE authors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                country TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                price REAL NOT NULL,
                author_id INTEGER NOT NULL,
                FOREIGN KEY (author_id) REFERENCES authors (id)
            );
        """)
        cursor.execute("""
            CREATE TABLE tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE book_tags (
                book_id INTEGER,
                tag_id INTEGER,
                FOREIGN KEY (book_id) REFERENCES books (id),
                FOREIGN KEY (tag_id) REFERENCES tags (id)
            );
        """)

        # Seeding data
        authors_data = [
            ("Guido van Rossum", "Netherlands"),
            ("Adrian Holovaty", "USA"),
            ("Simon Willison", "UK"),
            ("Audrey Roy Greenfeld", "USA"),
        ]
        cursor.executemany("INSERT INTO authors (name, country) VALUES (?, ?);", authors_data)

        books_data = [
            ("Python internals Deep Dive", 45.0, 1),
            ("CPython Architecture Manual", 55.0, 1),
            ("Building Scalable Django Apps", 40.0, 2),
            ("Web Frameworks History", 30.0, 2),
            ("Datasette and SQLite Mastery", 38.0, 3),
            ("Two Scoops of Django", 48.0, 4),
        ]
        cursor.executemany("INSERT INTO books (title, price, author_id) VALUES (?, ?, ?);", books_data)

        tags_data = [("Python",), ("Django",), ("Architecture",), ("Database",)]
        cursor.executemany("INSERT INTO tags (name) VALUES (?);", tags_data)

        book_tags_data = [
            (1, 1), (1, 3),  # Python internals -> Python, Architecture
            (2, 1), (2, 4),  # CPython -> Python, Database
            (3, 2), (3, 3),  # Scalable Django -> Django, Architecture
            (4, 2),          # Web Frameworks -> Django
            (5, 1), (5, 4),  # Datasette -> Python, Database
            (6, 1), (6, 2),  # Two Scoops -> Python, Django
        ]
        cursor.executemany("INSERT INTO book_tags (book_id, tag_id) VALUES (?, ?);", book_tags_data)

        conn.commit()
        return conn


class MockQuerySet:
    """Simulasi Django QuerySet: Lazy Evaluation, Result Cache, Chaining."""
    def __init__(self, conn, model_name: str, filters: Optional[Dict[str, Any]] = None):
        self.conn = conn
        self.model_name = model_name
        self.filters = filters or {}
        self._result_cache: Optional[List[Dict[str, Any]]] = None

    def filter(self, **kwargs):
        new_filters = dict(self.filters)
        new_filters.update(kwargs)
        # QuerySet bersifat immutability saat chaining
        return MockQuerySet(self.conn, self.model_name, new_filters)

    def _fetch_all(self):
        if self._result_cache is None:
            t0 = time.perf_counter()
            cursor = self.conn.cursor()
            query = f"SELECT * FROM {self.model_name}"
            params = []
            if self.filters:
                clauses = [f"{k} = ?" for k in self.filters]
                query += " WHERE " + " AND ".join(clauses)
                params = list(self.filters.values())
            
            cursor.execute(query, params)
            cols = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            self._result_cache = [dict(zip(cols, row)) for row in rows]
            duration = (time.perf_counter() - t0) * 1000.0
            db_logger.log(f"{query} [PARAMS: {params}]", duration)

    def __iter__(self):
        self._fetch_all()
        return iter(self._result_cache)

    def __len__(self):
        self._fetch_all()
        return len(self._result_cache)

    def __getitem__(self, index):
        self._fetch_all()
        return self._result_cache[index]

    def is_evaluated(self) -> bool:
        return self._result_cache is not None


class PerformanceLabs:
    """Laboratorium Eksperimen Django ORM Query Optimization."""

    def __init__(self, conn):
        self.conn = conn

    def demo_lazy_evaluation(self):
        print(f"\n{BOLD}{CYAN}=== LAB 1: DEMO LAZY EVALUATION & RESULT CACHE ==={RESET}")
        db_logger.reset()

        print(f"{YELLOW}1. Mendefinisikan QuerySet (Belum dievaluasi ke Database)...{RESET}")
        qs = MockQuerySet(self.conn, "books")
        print(f"   Status Evaluasi: {RED}{qs.is_evaluated()}{RESET}")
        print(f"   Jumlah Query Database: {BOLD}{db_logger.count}{RESET}")

        print(f"\n{YELLOW}2. Melakukan filter chaining (Tetap Lazy)...{RESET}")
        qs_filtered = qs.filter(author_id=1)
        print(f"   Status Evaluasi qs_filtered: {RED}{qs_filtered.is_evaluated()}{RESET}")
        print(f"   Jumlah Query Database: {BOLD}{db_logger.count}{RESET}")

        print(f"\n{YELLOW}3. Trigger Evaluasi via iterasi (Pertama kali Query SQL dijalankan)...{RESET}")
        items = list(qs_filtered)
        print(f"   Data diambil: {len(items)} record(s).")
        print(f"   Status Evaluasi: {GREEN}{qs_filtered.is_evaluated()}{RESET}")
        print(f"   Jumlah Query Database: {BOLD}{db_logger.count}{RESET}")

        print(f"\n{YELLOW}4. Akses Ulang QuerySet yang Sama (Menggunakan Result Cache)...{RESET}")
        _ = [item["title"] for item in qs_filtered]
        print(f"   Jumlah Query Database setelah pembacaan kedua: {GREEN}{db_logger.count}{RESET} (0 query tambahan!)")

    def demo_n_plus_one_problem(self):
        print(f"\n{BOLD}{CYAN}=== LAB 2: THE INFAMOUS N+1 QUERY PROBLEM ==={RESET}")
        db_logger.reset()
        cursor = self.conn.cursor()

        print(f"{RED}[SKENARIO BURUK]{RESET} Iterasi buku, lalu mengambil data Author per record:")
        t0 = time.perf_counter()
        
        # 1 Query untuk ambil buku
        cursor.execute("SELECT id, title, author_id FROM books;")
        books = cursor.fetchall()
        db_logger.log("SELECT id, title, author_id FROM books;", (time.perf_counter() - t0) * 1000)

        # N Query untuk ambil author masing-masing buku
        results = []
        for b_id, title, author_id in books:
            t_sub = time.perf_counter()
            cursor.execute("SELECT name, country FROM authors WHERE id = ?;", (author_id,))
            author = cursor.fetchone()
            db_logger.log(f"SELECT name, country FROM authors WHERE id = {author_id};", (time.perf_counter() - t_sub) * 1000)
            results.append((title, author[0]))

        print(f"\n{RED}Hasil N+1 Problem:{RESET}")
        print(f"  Total Data: {len(results)} buku")
        print(f"  Total SQL Eksekusi: {RED}{db_logger.count} queries{RESET} (1 query books + {len(books)} query author)")
        print(f"  Total Execution Time: {YELLOW}{db_logger.total_time:.2f}ms{RESET}")

    def demo_select_related(self):
        print(f"\n{BOLD}{CYAN}=== LAB 3: OPTIMASI DENGAN select_related() (SQL JOIN) ==={RESET}")
        db_logger.reset()
        cursor = self.conn.cursor()

        print(f"{GREEN}[SOLUSI 1-to-1 / ForeignKey]{RESET} Menggunakan SQL INNER JOIN untuk 1 round-trip query tunggal:")
        t0 = time.perf_counter()
        query = """
            SELECT books.id, books.title, authors.name, authors.country
            FROM books
            INNER JOIN authors ON books.author_id = authors.id;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        duration = (time.perf_counter() - t0) * 1000
        db_logger.log(query, duration)

        print(f"\n{GREEN}Hasil Optimasi select_related():{RESET}")
        print(f"  Total Data Didapat: {len(rows)} record")
        for r in rows[:3]:
            print(f"    - Buku: {BOLD}{r[1]}{RESET} | Penulis: {CYAN}{r[2]}{RESET} ({r[3]})")
        print(f"    ... [{len(rows)-3} baris lainnya]")
        print(f"  Total SQL Eksekusi: {GREEN}{db_logger.count} query{RESET} (Turun dari 7 query menjadi 1 query!)")
        print(f"  Total Execution Time: {GREEN}{db_logger.total_time:.2f}ms{RESET}")

    def demo_prefetch_related(self):
        print(f"\n{BOLD}{CYAN}=== LAB 4: OPTIMASI DENGAN prefetch_related() (2 Queries M2M) ==={RESET}")
        db_logger.reset()
        cursor = self.conn.cursor()

        print(f"{GREEN}[SOLUSI Many-to-Many / Reverse FK]{RESET} 2 Query Terpisah + Python-side joining:")
        
        # Query 1: Ambil buku
        t1 = time.perf_counter()
        cursor.execute("SELECT id, title FROM books;")
        books = cursor.fetchall()
        db_logger.log("SELECT id, title FROM books;", (time.perf_counter() - t1) * 1000)

        book_ids = [b[0] for b in books]
        placeholders = ",".join("?" * len(book_ids))

        # Query 2: Ambil semua tags terkait sekaligus dengan operator SQL IN
        t2 = time.perf_counter()
        tag_query = f"""
            SELECT bt.book_id, t.name 
            FROM tags t
            INNER JOIN book_tags bt ON t.id = bt.tag_id
            WHERE bt.book_id IN ({placeholders});
        """
        cursor.execute(tag_query, book_ids)
        tag_rows = cursor.fetchall()
        db_logger.log(f"SELECT bt.book_id, t.name FROM tags ... WHERE bt.book_id IN ({','.join(map(str, book_ids))});", (time.perf_counter() - t2) * 1000)

        # Python-side In-memory mapping
        book_tags_map = {b[0]: [] for b in books}
        for book_id, tag_name in tag_rows:
            book_tags_map[book_id].append(tag_name)

        print(f"\n{GREEN}Hasil Optimasi prefetch_related():{RESET}")
        for b_id, title in books[:3]:
            tags_str = ", ".join(book_tags_map.get(b_id, []))
            print(f"    - Buku: {BOLD}{title}{RESET} -> Tags: [{MAGENTA}{tags_str}{RESET}]")
        print(f"    ... [{len(books)-3} baris lainnya]")
        print(f"  Total SQL Eksekusi: {GREEN}{db_logger.count} queries{RESET} (Pasti 2 queries terlepas dari jumlah tag/buku)")
        print(f"  Total Execution Time: {GREEN}{db_logger.total_time:.2f}ms{RESET}")

    def run_benchmark_comparison(self):
        print(f"\n{BOLD}{MAGENTA}=========================================================={RESET}")
        print(f"{BOLD}{MAGENTA}        KOMPARASI BENCHMARK PERFORMA ORM DJANGO           {RESET}")
        print(f"{BOLD}{MAGENTA}=========================================================={RESET}")
        
        # Simulasi Naive N+1 M2M
        db_logger.reset()
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, title FROM books;")
        books = cursor.fetchall()
        db_logger.log("SELECT id, title FROM books;", 0.01)
        for b_id, _ in books:
            cursor.execute("""
                SELECT t.name FROM tags t 
                JOIN book_tags bt ON t.id = bt.tag_id 
                WHERE bt.book_id = ?
            """, (b_id,))
            _ = cursor.fetchall()
            db_logger.log(f"SELECT t.name FROM tags ... WHERE bt.book_id = {b_id}", 0.01)
        naive_queries = db_logger.count

        print(f"| {BOLD}Metode Optimasi{RESET:<25} | {BOLD}Jumlah Query SQL{RESET:<18} | {BOLD}Status Efisiensi{RESET} |")
        print("|" + "-" * 27 + "|" + "-" * 20 + "|" + "-" * 18 + "|")
        print(f"| Naive FK (N+1)              | {RED}1 + N queries (7){RESET:<23} | {RED}Kritis (Slow){RESET}    |")
        print(f"| select_related() (JOIN)     | {GREEN}1 single query{RESET:<24} | {GREEN}Sangat Optimal{RESET}  |")
        print(f"| Naive M2M                   | {RED}1 + N queries ({naive_queries}){RESET:<23} | {RED}Kritis (Slow){RESET}    |")
        print(f"| prefetch_related() (IN)     | {GREEN}2 fixed queries{RESET:<24} | {GREEN}Sangat Optimal{RESET}  |")
        print("--------------------------------------------------------------------")


def interactive_menu():
    conn = DatabaseSetup.get_connection()
    labs = PerformanceLabs(conn)

    while True:
        print(f"\n{BOLD}{CYAN}=== DJANGO QUERYSET MASTERY: INTERACTIVE LAB ==={RESET}")
        print(f"1. {YELLOW}Demo Lazy Evaluation & Query Cache{RESET}")
        print(f"2. {RED}Simulasi Bencana N+1 Query Problem{RESET}")
        print(f"3. {GREEN}Solusi select_related() (SQL INNER JOIN){RESET}")
        print(f"4. {GREEN}Solusi prefetch_related() (M2M IN Clause){RESET}")
        print(f"5. {MAGENTA}Tampilkan Tabel Komparasi Benchmark{RESET}")
        print(f"6. {BOLD}Jalankan Semua Skenario Sekaligus{RESET}")
        print(f"0. Keluar")
        
        choice = input(f"\n{BOLD}Pilih opsi [0-6]: {RESET}").strip()
        if choice == "1":
            labs.demo_lazy_evaluation()
        elif choice == "2":
            labs.demo_n_plus_one_problem()
        elif choice == "3":
            labs.demo_select_related()
        elif choice == "4":
            labs.demo_prefetch_related()
        elif choice == "5":
            labs.run_benchmark_comparison()
        elif choice == "6":
            labs.demo_lazy_evaluation()
            labs.demo_n_plus_one_problem()
            labs.demo_select_related()
            labs.demo_prefetch_related()
            labs.run_benchmark_comparison()
        elif choice == "0":
            print(f"{GREEN}Lab selesai. Selamat mengoptimasi QuerySet Django!{RESET}")
            break
        else:
            print(f"{RED}Opsi tidak valid, silakan coba lagi.{RESET}")


if __name__ == "__main__":
    interactive_menu()
