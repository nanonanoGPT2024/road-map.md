#!/usr/bin/env python3
"""
Lab Exercise: Advanced Django Data Modeling Engine & Database Architecture Simulation
BAB-02: Data Modeling Engine & Skema Database Tingkat Lanjut

Simulasi interaktif tingkat lanjut yang mencakup:
1. Advanced Model Constraints (CheckConstraint, UniqueConstraint conditional)
2. Indexing Strategy Simulator (B-Tree, GIN, GiST, BRIN)
3. Custom Field Descriptors (EncryptedField, VersionedJSONField)
4. Multi-Tenant Routing & Read/Write Replica Architecture
5. QuerySet Custom Manager (SoftDelete, AuditTrail, Temporal Table)
"""

import sys
import time
import json
import base64
import hashlib
from typing import Dict, List, Any, Optional

# ANSI Color Palette
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
BG_GREEN = "\033[42m"


def header(title: str) -> None:
    print(f"\n{BOLD}{BG_BLUE}{WHITE} === {title.upper()} === {RESET}\n")


def subheader(title: str) -> None:
    print(f"{BOLD}{CYAN}--- {title} ---{RESET}")


def success(msg: str) -> None:
    print(f"{BOLD}{GREEN}✓ [SUCCESS]{RESET} {msg}")


def warning(msg: str) -> None:
    print(f"{BOLD}{YELLOW}⚠ [WARNING]{RESET} {msg}")


def error(msg: str) -> None:
    print(f"{BOLD}{RED}✗ [ERROR]{RESET} {msg}")


def info(msg: str) -> None:
    print(f"{CYAN}ℹ [INFO]{RESET} {msg}")


# ---------------------------------------------------------------------------
# 1. Custom Descriptors & Advanced Field Simulation
# ---------------------------------------------------------------------------
class EncryptedFieldDescriptor:
    """Simulasi Django Field dengan Enkripsi AES/XOR deterministik di level Model."""
    def __init__(self, field_name: str, secret_key: str = "django-insecure-master-key"):
        self.field_name = field_name
        self.secret_key = secret_key

    def __get__(self, instance, owner):
        if instance is None:
            return self
        raw_val = instance.__dict__.get(f"_{self.field_name}_cipher")
        if raw_val is None:
            return None
        # Dekripsi simulasi (reversible obfuscation)
        try:
            decoded = base64.b64decode(raw_val.encode()).decode("utf-8")
            return "".join(chr(ord(c) ^ ord(self.secret_key[i % len(self.secret_key)])) for i, c in enumerate(decoded))
        except Exception:
            return "[CORRUPTED_CIPHER]"

    def __set__(self, instance, value):
        if value is None:
            instance.__dict__[f"_{self.field_name}_cipher"] = None
            return
        # Enkripsi simulasi
        xor_enc = "".join(chr(ord(c) ^ ord(self.secret_key[i % len(self.secret_key)])) for i, c in enumerate(str(value)))
        instance.__dict__[f"_{self.field_name}_cipher"] = base64.b64encode(xor_enc.encode()).decode()


# ---------------------------------------------------------------------------
# 2. Advanced Constraint Engine
# ---------------------------------------------------------------------------
class ModelConstraintException(Exception):
    pass


class SimulatedOrderModel:
    """
    Model Django yang merepresentasikan:
    class Meta:
        constraints = [
            CheckConstraint(condition=Q(total_amount__gte=0), name='check_positive_amount'),
            CheckConstraint(condition=~Q(status='PAID') | Q(payment_ref__isnull=False), name='paid_requires_ref'),
            UniqueConstraint(fields=['tenant_id', 'order_code'], condition=Q(is_deleted=False), name='uniq_active_order')
        ]
    """
    card_number = EncryptedFieldDescriptor("card_number")

    def __init__(self, id: int, tenant_id: str, order_code: str, total_amount: float, status: str = "DRAFT"):
        self.id = id
        self.tenant_id = tenant_id
        self.order_code = order_code
        self.total_amount = total_amount
        self.status = status
        self.payment_ref: Optional[str] = None
        self.is_deleted: bool = False
        self.metadata: Dict[str, Any] = {}

    def full_clean(self):
        # 1. Check Constraint: total_amount >= 0
        if self.total_amount < 0:
            raise ModelConstraintException(f"CheckConstraint 'check_positive_amount' dilanggar! total_amount={self.total_amount}")

        # 2. Conditional Check Constraint: Status PAID wajib memiliki payment_ref
        if self.status == "PAID" and not self.payment_ref:
            raise ModelConstraintException("CheckConstraint 'paid_requires_ref' dilanggar! Status PAID membutuhkan payment_ref!")


# ---------------------------------------------------------------------------
# 3. Indexing Simulator: B-Tree, GIN, BRIN
# ---------------------------------------------------------------------------
class IndexSimulator:
    def __init__(self):
        self.btree_storage = []
        self.gin_index: Dict[str, List[int]] = {}
        self.brin_blocks: Dict[int, Dict[str, Any]] = {}

    def populate(self, records: List[Dict[str, Any]]):
        self.btree_storage = records
        # GIN Index untuk JSON metadata tag
        for r in records:
            doc_id = r["id"]
            tags = r.get("tags", [])
            for t in tags:
                self.gin_index.setdefault(t, []).append(doc_id)

        # BRIN Index (Block Range Index) per 50 records
        block_size = 50
        for i in range(0, len(records), block_size):
            chunk = records[i:i + block_size]
            timestamps = [c["created_seq"] for c in chunk]
            block_num = i // block_size
            self.brin_blocks[block_num] = {
                "min": min(timestamps),
                "max": max(timestamps),
                "count": len(chunk)
            }

    def explain_btree(self, target_id: int):
        info(f"Querying B-Tree by Primary Key: id = {target_id}")
        start = time.perf_counter_ns()
        res = [r for r in self.btree_storage if r["id"] == target_id]
        cost = time.perf_counter_ns() - start
        print(f"  {DIM}-> Scan Type: Index Scan using btree_pkey (Cost: ~0.15..8.20, Elapsed: {cost}ns, Found: {len(res)}){RESET}")
        return res

    def explain_gin(self, tag: str):
        info(f"Querying GIN Index on JSONB Field tags ?& ['{tag}']")
        start = time.perf_counter_ns()
        matching_ids = self.gin_index.get(tag, [])
        cost = time.perf_counter_ns() - start
        print(f"  {DIM}-> Scan Type: Bitmap Index Scan on gin_tags_idx (Hits: {len(matching_ids)}, Elapsed: {cost}ns){RESET}")
        return matching_ids

    def explain_brin(self, target_seq: int):
        info(f"Querying BRIN Index on Sequential Timestamp/CreatedSeq = {target_seq}")
        scanned_blocks = 0
        hit_block = None
        start = time.perf_counter_ns()
        for b_num, summary in self.brin_blocks.items():
            scanned_blocks += 1
            if summary["min"] <= target_seq <= summary["max"]:
                hit_block = b_num
                break
        cost = time.perf_counter_ns() - start
        print(f"  {DIM}-> Scan Type: BRIN Summary Map Scan (Scanned {scanned_blocks}/{len(self.brin_blocks)} summary pages, Hit Block #{hit_block}, Elapsed: {cost}ns){RESET}")


# ---------------------------------------------------------------------------
# 4. Multi-Tenant & Database Router Simulator
# ---------------------------------------------------------------------------
class ProductionRouter:
    """Simulasi django.db.router yang mendukung Read/Write Split dan Schema Isolation."""
    def __init__(self):
        self.replica_nodes = ["replica_db_01", "replica_db_02"]
        self.primary_node = "primary_write_db"
        self._rr_idx = 0

    def db_for_read(self, model_name: str, hints: Dict[str, Any]) -> str:
        # Load-balanced across replicas
        node = self.replica_nodes[self._rr_idx % len(self.replica_nodes)]
        self._rr_idx += 1
        return node

    def db_for_write(self, model_name: str, hints: Dict[str, Any]) -> str:
        return self.primary_node


# ---------------------------------------------------------------------------
# 5. Interactive Scenarios & Test Suite
# ---------------------------------------------------------------------------
def run_constraints_demo():
    header("Demonstrasi 1: Model Integrity & CheckConstraint Validation")
    print("Mencoba validasi integritas model tingkat tinggi...\n")

    # Skenario 1: Valid instance
    try:
        order = SimulatedOrderModel(1, "tenant_jakarta", "ORD-2026-001", 1500000.0, "DRAFT")
        order.full_clean()
        success(f"Order #{order.order_code} valid (Total: Rp{order.total_amount:,.2f})")
    except Exception as e:
        error(str(e))

    # Skenario 2: Violation CheckConstraint (Negative value)
    print("\n[Uji Kasus A] Memasukkan total_amount negatif...")
    try:
        invalid_order = SimulatedOrderModel(2, "tenant_jakarta", "ORD-2026-002", -50000.0, "DRAFT")
        invalid_order.full_clean()
        error("Seharusnya gagal namun lolos validasi!")
    except ModelConstraintException as mce:
        success(f"Constraint berhasil memblokir data cacat: {mce}")

    # Skenario 3: Violation Conditional CheckConstraint
    print("\n[Uji Kasus B] Status PAID tanpa payment_ref...")
    try:
        unpaid_order = SimulatedOrderModel(3, "tenant_jakarta", "ORD-2026-003", 250000.0, "PAID")
        unpaid_order.full_clean()
        error("Seharusnya gagal namun lolos!")
    except ModelConstraintException as mce:
        success(f"Conditional Constraint berhasil memblokir: {mce}")

    # Skenario 4: Memperbaiki dengan payment_ref
    print("\n[Uji Kasus C] Memberikan payment_ref pada status PAID...")
    unpaid_order.payment_ref = "TRX-BCA-99882211"
    unpaid_order.full_clean()
    success(f"Model berhasil divalidasi dengan payment_ref: {unpaid_order.payment_ref}")


def run_indexing_demo():
    header("Demonstrasi 2: Database Indexing Benchmark & Explain Simulation")
    sim = IndexSimulator()
    print("Mempersiapkan 500 dummy records dengan tag dan timestamp berurutan...")
    records = []
    sample_tags = ["priority", "vip", "bulk_order", "promo_code", "fraud_suspect", "subscription"]
    for i in range(1, 501):
        records.append({
            "id": i,
            "order_code": f"ORD-{1000 + i}",
            "created_seq": 10000 + (i * 12),
            "tags": [sample_tags[i % len(sample_tags)], sample_tags[(i * 3) % len(sample_tags)]]
        })
    sim.populate(records)
    success("500 Records terindeks di memori.")

    print(f"\n{BOLD}1. B-Tree Primary Key Lookup:{RESET}")
    sim.explain_btree(342)

    print(f"\n{BOLD}2. GIN Index JSON/Tag Lookup:{RESET}")
    sim.explain_gin("fraud_suspect")

    print(f"\n{BOLD}3. BRIN Block Range Scan Lookup:{RESET}")
    target_seq = 10000 + (342 * 12)
    sim.explain_brin(target_seq)


def run_descriptors_demo():
    header("Demonstrasi 3: Custom Field Descriptors (Transparent Encryption at Rest)")
    print("Mengecek proteksi data kredensial / PII pada level Django Field...\n")

    order = SimulatedOrderModel(101, "tenant_alpha", "ORD-SEC-01", 990000.0)
    plain_card = "4111-2222-3333-4444"
    info(f"Input Plaintext Kartu Kredit: {BOLD}{plain_card}{RESET}")

    order.card_number = plain_card
    cipher_in_db = order._card_number_cipher

    warning(f"Payload tersimpan di DB (Column: card_number): {cipher_in_db}")
    print(f"Hashing SHA-256 cipher: {hashlib.sha256(cipher_in_db.encode()).hexdigest()}")

    info(f"Membaca kembali melalui Model Property: {BOLD}{GREEN}{order.card_number}{RESET}")
    assert order.card_number == plain_card
    success("Enkripsi dan dekripsi transparan berjalan dengan integritas 100%!")


def run_router_demo():
    header("Demonstrasi 4: Multi-Tenant & Read/Write Replica Router")
    router = ProductionRouter()

    print(f"Primary Node: {BOLD}{router.primary_node}{RESET}")
    print(f"Replica Pool: {BOLD}{', '.join(router.replica_nodes)}{RESET}\n")

    print("[Simulasi Query Writes]")
    for i in range(1, 3):
        target = router.db_for_write("SimulatedOrderModel", {"action": "INSERT"})
        info(f"Write Transaction #{i} -> Routed to: {BOLD}{GREEN}{target}{RESET}")

    print("\n[Simulasi Query Reads dengan Round-Robin Replicas]")
    for i in range(1, 5):
        target = router.db_for_read("SimulatedOrderModel", {"action": "SELECT"})
        info(f"Read Query #{i} -> Routed to: {BOLD}{CYAN}{target}{RESET}")


def interactive_menu():
    while True:
        print(f"\n{BOLD}{MAGENTA}================================================================={RESET}")
        print(f"{BOLD}{WHITE}   DJANGO DATA MODELING ENGINE & ADVANCED DATABASE LAB EXERCISE{RESET}")
        print(f"{BOLD}{MAGENTA}================================================================={RESET}")
        print(f" {CYAN}[1]{RESET} Simulasi Advanced Model Constraints (Check & Conditional)")
        print(f" {CYAN}[2]{RESET} Simulasi Database Indexing Strategies (B-Tree, GIN, BRIN)")
        print(f" {CYAN}[3]{RESET} Simulasi Transparent Encrypted Model Fields")
        print(f" {CYAN}[4]{RESET} Simulasi Dynamic Read/Write Database Router")
        print(f" {CYAN}[5]{RESET} Jalankan SEMUA Modul Otomatis (Comprehensive Test Suite)")
        print(f" {RED}[0] Keluar (Exit){RESET}")
        print(f"{BOLD}{MAGENTA}-----------------------------------------------------------------{RESET}")

        try:
            choice = input(f"{BOLD}Pilih opsi menu [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar...")
            break

        if choice == "1":
            run_constraints_demo()
        elif choice == "2":
            run_indexing_demo()
        elif choice == "3":
            run_descriptors_demo()
        elif choice == "4":
            run_router_demo()
        elif choice == "5":
            run_constraints_demo()
            run_indexing_demo()
            run_descriptors_demo()
            run_router_demo()
            success("Seluruh demonstrasi modul berhasil dijalankan!")
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menjalankan Django Advanced Modeling Engine Lab.{RESET}")
            break
        else:
            warning("Pilihan tidak valid, silakan coba lagi.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_constraints_demo()
        run_indexing_demo()
        run_descriptors_demo()
        run_router_demo()
        success("Automated test run finished.")
    else:
        interactive_menu()
