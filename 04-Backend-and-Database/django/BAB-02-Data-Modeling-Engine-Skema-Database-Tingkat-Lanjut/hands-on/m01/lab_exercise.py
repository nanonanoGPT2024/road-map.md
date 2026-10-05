#!/usr/bin/env python3
"""
Lab Exercise M01: Django Advanced Data Modeling & Database Schema Engine Simulation
BAB-02: Data Modeling Engine & Skema Database Tingkat Lanjut

Materi Inti:
1. Model Inheritance (Abstract Base Class vs Multi-Table vs Proxy Model)
2. Custom Model Field Lifecycle (to_python, get_prep_value, from_db_value)
3. Advanced Database Constraints (CheckConstraint, Partial UniqueConstraint)
4. Dynamic Database Router Simulation (Master/Replica Read-Write Splitting)
"""

import sys
import json
import zlib
import base64
import sqlite3
from typing import Any, Dict, List, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[1;32m"
CYAN = "\033[1;36m"
YELLOW = "\033[1;33m"
MAGENTA = "\033[1;35m"
RED = "\033[1;31m"
BLUE = "\033[1;34m"

def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{YELLOW}>> {title.upper()}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}")

def print_substep(step_name: str, desc: str) -> None:
    print(f"\n{BOLD}{MAGENTA}[+] {step_name}:{RESET} {desc}")

def print_sql(sql: str) -> None:
    print(f"{BLUE}[SQL DDL/DML]{RESET} \033[3m{sql.strip()}{RESET}")

def print_success(msg: str) -> None:
    print(f"{GREEN}[SUCCESS]{RESET} {msg}")

def print_warning(msg: str) -> None:
    print(f"{RED}[VALIDATION REJECTED]{RESET} {msg}")


# ==============================================================================
# 1. Custom Model Field Lifecycle Simulation
# ==============================================================================
class CompressedJSONField:
    """
    Simulasi siklus hidup Custom Field Django:
    - to_python(): konversi input raw / deserialized ke Python data structure.
    - get_prep_value(): persiapan nilai sebelum disimpan ke database (kompresi + serialize).
    - from_db_value(): konversi nilai raw dari database driver kembali ke Python object.
    """
    def __init__(self, name: str):
        self.name = name

    def to_python(self, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    def get_prep_value(self, value: Any) -> str:
        if value is None:
            return ""
        # 1. Serialize dict to json
        raw_json = json.dumps(value, separators=(',', ':'))
        # 2. Compress payload using zlib
        compressed = zlib.compress(raw_json.encode('utf-8'))
        # 3. Base64 encode for safe textual DB storage
        encoded = base64.b64encode(compressed).decode('ascii')
        return encoded

    def from_db_value(self, value: Optional[str]) -> Any:
        if not value:
            return {}
        # 1. Base64 decode
        compressed = base64.b64decode(value.encode('ascii'))
        # 2. Decompress zlib
        raw_json = zlib.decompress(compressed).decode('utf-8')
        # 3. Deserialize json to Python dict
        return json.loads(raw_json)


def demo_custom_field_lifecycle() -> None:
    print_header("Simulasi 1: Siklus Hidup Custom Field (CompressedJSONField)")
    print_substep("Definisi Field", "Menguji to_python, get_prep_value, dan from_db_value")

    field = CompressedJSONField("payload")
    sample_payload = {
        "user_id": 4092,
        "features": ["audit_trail", "vector_search", "partitioning"],
        "metadata": {"source": "k8s_worker", "attempts": 3, "score": 98.75}
    }

    raw_json_str = json.dumps(sample_payload)
    print(f"Original Python Object: {YELLOW}{sample_payload}{RESET}")
    print(f"Ukuran JSON mentah    : {len(raw_json_str)} bytes")

    # get_prep_value
    db_value = field.get_prep_value(sample_payload)
    print(f"Compressed & Encoded (DB Storage): {CYAN}{db_value}{RESET}")
    print(f"Ukuran tersimpan di DB: {len(db_value)} bytes")

    # from_db_value
    restored = field.from_db_value(db_value)
    print(f"Restored via from_db_value(): {GREEN}{restored}{RESET}")
    assert restored == sample_payload, "Data yang direstorasi tidak identik!"
    print_success("Verifikasi Custom Field Lifecycle tervalidasi 100% loss-less!")


# ==============================================================================
# 2. Model Inheritance & Schema Generation Engine
# ==============================================================================
class ModelMeta:
    def __init__(self, abstract: bool = False, proxy: bool = False, db_table: Optional[str] = None):
        self.abstract = abstract
        self.proxy = proxy
        self.db_table = db_table


def demo_model_inheritance() -> None:
    print_header("Simulasi 2: Pola Pewarisan Model Django (ABC vs MTI vs Proxy)")

    # 1. Abstract Base Class (ABC)
    print_substep("1. Abstract Base Classes (ABC)", "Field di-copy ke child, tabel parent TIDAK dibuat.")
    print_sql("""
    -- Child: Product (mewarisi TimestampedModel secara ABC)
    CREATE TABLE shop_product (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        name VARCHAR(150) NOT NULL,
        price DECIMAL(10, 2) NOT NULL
    );
    """)

    # 2. Multi-Table Inheritance (MTI)
    print_substep("2. Multi-Table Inheritance (MTI)", "Parent & Child punya tabel terpisah yang dihubungkan OneToOneField/Pointer.")
    print_sql("""
    -- Parent: Place
    CREATE TABLE shop_place (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        address VARCHAR(255) NOT NULL
    );

    -- Child: Restaurant (Pointer ke shop_place via OneToOne)
    CREATE TABLE shop_restaurant (
        place_ptr_id INTEGER PRIMARY KEY REFERENCES shop_place(id) ON DELETE CASCADE,
        serves_hot_dogs BOOLEAN NOT NULL,
        michelin_stars INTEGER DEFAULT 0
    );
    """)

    # 3. Proxy Model
    print_substep("3. Proxy Models", "Hanya mengubah perilaku Python (ordering, managers). TIDAK ADA DDL/tabel baru.")
    print(f"{BOLD}Proxy Class:{RESET} class OrderedRestaurant(Restaurant): Meta: proxy = True, ordering = ['-michelin_stars']")
    print(f"{YELLOW}Status DDL: Ditiadakan (Zero migration overhead). Menggunakan tabel shop_restaurant secara langsung.{RESET}")
    print_success("Skema Inheritance MTI & ABC berhasil dimodelkan dan dipisahkan secara struktural.")


# ==============================================================================
# 3. Advanced Database Constraints & SQL Integrity Enforcement
# ==============================================================================
def demo_advanced_constraints() -> None:
    print_header("Simulasi 3: Advanced DB Constraints (CheckConstraint & Partial UniqueConstraint)")
    print_substep("Setup In-Memory SQLite", "Menerapkan CheckConstraint dan UniqueConstraint bersyarat (Partial Index)")

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # DDL with CHECK & Partial UNIQUE Index
    ddl = """
    CREATE TABLE store_coupon (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code VARCHAR(30) NOT NULL,
        discount_pct INTEGER NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        CONSTRAINT check_discount_range CHECK (discount_pct >= 1 AND discount_pct <= 90)
    );

    -- Django: models.UniqueConstraint(fields=['code'], condition=Q(is_active=True), name='unique_active_coupon_code')
    CREATE UNIQUE INDEX uq_active_coupon ON store_coupon (code) WHERE is_active = 1;
    """
    cursor.executescript(ddl)
    conn.commit()
    print_sql(ddl)

    # Insert valid coupons
    cursor.execute("INSERT INTO store_coupon (code, discount_pct, is_active) VALUES ('PROMO2026', 20, 1)")
    cursor.execute("INSERT INTO store_coupon (code, discount_pct, is_active) VALUES ('EXPIRED50', 50, 0)")
    conn.commit()
    print_success("Data valid berhasil di-insert ke tabel store_coupon.")

    # Test CheckConstraint Failure
    print_substep("Pengujian CheckConstraint", "Mencoba insert diskon 99% (Batas valid: 1-90%)")
    try:
        cursor.execute("INSERT INTO store_coupon (code, discount_pct, is_active) VALUES ('ILLEGAL99', 99, 1)")
        conn.commit()
    except sqlite3.IntegrityError as e:
        print_warning(f"CheckConstraint Terpicu: {e}")

    # Test Partial Unique Constraint
    print_substep("Pengujian Partial UniqueConstraint", "Insert duplicate coupon code dengan is_active=1 vs is_active=0")
    # Kasus 1: Duplicate code pada kupon non-aktif (harus diperbolehkan oleh partial index)
    cursor.execute("INSERT INTO store_coupon (code, discount_pct, is_active) VALUES ('EXPIRED50', 30, 0)")
    conn.commit()
    print_success("Kupon non-aktif duplikat berhasil disimpan (tidak melanggar partial index).")

    # Kasus 2: Duplicate code pada kupon aktif (harus DITOLAK)
    try:
        cursor.execute("INSERT INTO store_coupon (code, discount_pct, is_active) VALUES ('PROMO2026', 25, 1)")
        conn.commit()
    except sqlite3.IntegrityError as e:
        print_warning(f"UniqueConstraint Bersyarat Terpicu: {e}")

    conn.close()


# ==============================================================================
# 4. Dynamic Database Router Simulation (Master / Replica Routing)
# ==============================================================================
class PrimaryReplicaRouter:
    """
    Simulasi django.db router:
    - db_for_read(): mengarahkan query read-only (SELECT) ke 'replica'
    - db_for_write(): mengarahkan query write (INSERT/UPDATE/DELETE) ke 'default' (primary/master)
    """
    def __init__(self, replica_pool: List[str]):
        self.replica_pool = replica_pool
        self._round_robin_idx = 0

    def db_for_read(self, model_name: str, hints: Optional[Dict[str, Any]] = None) -> str:
        # Jika instance di-hint langsung ke master
        if hints and hints.get("instance_master"):
            return "default"
        # Round robin replica selection
        replica = self.replica_pool[self._round_robin_idx % len(self.replica_pool)]
        self._round_robin_idx += 1
        return replica

    def db_for_write(self, model_name: str, hints: Optional[Dict[str, Any]] = None) -> str:
        return "default"

    def allow_relation(self, obj1_db: str, obj2_db: str) -> bool:
        # Allow relations if both are in cluster
        cluster = {"default"}.union(set(self.replica_pool))
        return obj1_db in cluster and obj2_db in cluster


def demo_database_router() -> None:
    print_header("Simulasi 4: Multi-DB Routing Engine (Read/Write Splitting)")
    router = PrimaryReplicaRouter(replica_pool=["replica_node_01", "replica_node_02"])

    operations = [
        ("write", "Order", None),
        ("read", "Order", None),
        ("read", "ProductCatalog", None),
        ("write", "PaymentAudit", None),
        ("read", "UserSession", {"instance_master": True}),
    ]

    print_substep("Audit Dispatch Router", "Evaluasi rute target database untuk operasi ORM")
    for op_type, model, hints in operations:
        if op_type == "read":
            target = router.db_for_read(model, hints)
            print(f"[{CYAN}READ {RESET}] Model: {model:<15} Hint: {str(hints):<24} -> Routed to: {BOLD}{target}{RESET}")
        else:
            target = router.db_for_write(model, hints)
            print(f"[{YELLOW}WRITE{RESET}] Model: {model:<15} Hint: {str(hints):<24} -> Routed to: {BOLD}{target}{RESET}")

    print_success("Semua query read-write telah terisolasi sesuai arsitektur database pool.")


# ==============================================================================
# Interactive CLI Menu
# ==============================================================================
def display_menu() -> None:
    print(f"\n{BOLD}{CYAN}=== DJANGO ADVANCED DATA MODELING ENGINE LAB ==={RESET}")
    print(f"{BOLD}1.{RESET} Custom Field Lifecycle (CompressedJSONField)")
    print(f"{BOLD}2.{RESET} Model Inheritance (ABC, MTI, Proxy Model Schema)")
    print(f"{BOLD}3.{RESET} Advanced Constraints (CheckConstraint & Partial Unique)")
    print(f"{BOLD}4.{RESET} Dynamic DB Router (Master/Replica Read-Write Splitting)")
    print(f"{BOLD}5.{RESET} Jalankan Semua Simulasi (Full Suite)")
    print(f"{BOLD}0.{RESET} Keluar")
    print(f"{CYAN}{'-' * 48}{RESET}")


def run_all() -> None:
    demo_custom_field_lifecycle()
    demo_model_inheritance()
    demo_advanced_constraints()
    demo_database_router()
    print_header("Laboratorium Selesai: Semua Modul Berhasil Dijalankan")


def main() -> None:
    # Auto-run mode if arguments provided or non-interactive
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "run"):
        run_all()
        return

    # Check if standard input is a terminal
    if not sys.stdin.isatty():
        run_all()
        return

    while True:
        display_menu()
        try:
            choice = input(f"{BOLD}Pilih opsi [0-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar...")
            break

        if choice == "1":
            demo_custom_field_lifecycle()
        elif choice == "2":
            demo_model_inheritance()
        elif choice == "3":
            demo_advanced_constraints()
        elif choice == "4":
            demo_database_router()
        elif choice == "5":
            run_all()
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menjalankan lab exercise.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan ulangi.{RESET}")


if __name__ == "__main__":
    main()
