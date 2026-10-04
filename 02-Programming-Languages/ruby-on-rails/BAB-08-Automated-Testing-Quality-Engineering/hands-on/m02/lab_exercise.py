#!/usr/bin/env python3
"""
Lab Hands-on: Ruby on Rails - Automated Testing & Quality Engineering (Deep Dive)
Simulasi Internal Mesin Pengujian Rails (ActiveSupport::TestCase, RSpec/FactoryBot,
Transactional Fixtures, dan Assertion 'assert_difference').
"""

import sys
import time
import copy
import traceback
from typing import Callable, Any, Dict, List, Optional

# --- ANSI Terminal Styling ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

# ==============================================================================
# 1. DATABASE & TRANSACTIONAL FIXTURE EMULATOR
# ==============================================================================
class Database:
    """
    Simulasi layer database ActiveRecord dengan mekanisme savepoint / rollback
    untuk mendukung 'use_transactional_tests = true' pada Rails.
    """
    _instance = None

    def __init__(self):
        self.tables: Dict[str, Dict[int, Dict[str, Any]]] = {
            "users": {},
            "orders": {}
        }
        self.auto_increment: Dict[str, int] = {"users": 1, "orders": 1}
        self._snapshots: List[tuple] = []

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Database()
        return cls._instance

    def begin_transaction(self):
        """Membuat snapshot memori database (analog dengan SQL SAVEPOINT)."""
        snapshot = (copy.deepcopy(self.tables), copy.deepcopy(self.auto_increment))
        self._snapshots.append(snapshot)

    def rollback(self):
        """Mengembalikan kondisi DB ke snapshot terakhir (ROLLBACK TO SAVEPOINT)."""
        if self._snapshots:
            tables_copy, auto_inc_copy = self._snapshots.pop()
            self.tables = tables_copy
            self.auto_increment = auto_inc_copy

    def insert(self, table: str, attributes: Dict[str, Any]) -> int:
        record_id = self.auto_increment[table]
        self.auto_increment[table] += 1
        record = attributes.copy()
        record["id"] = record_id
        self.tables[table][record_id] = record
        return record_id

    def count(self, table: str) -> int:
        return len(self.tables[table])

# ==============================================================================
# 2. ACTIVEMODEL & FACTORYBOT EMULATOR
# ==============================================================================
class User:
    """Model ActiveRecord simulasi."""
    db = Database.get_instance()

    def __init__(self, **attributes):
        self.id = attributes.get("id")
        self.email = attributes.get("email", "")
        self.role = attributes.get("role", "member")
        self.active = attributes.get("active", True)

    def save(self) -> bool:
        # Validasi dasar ala Rails: validates :email, presence: true
        if not self.email or "@" not in self.email:
            return False
        self.id = self.db.insert("users", {"email": self.email, "role": self.role, "active": self.active})
        return True

    @classmethod
    def count(cls) -> int:
        return cls.db.count("users")


class FactoryBot:
    """Simulasi DSL FactoryBot untuk sintesis fixture data dinamis."""
    _sequences: Dict[str, int] = {}

    @classmethod
    def sequence(cls, name: str) -> int:
        cls._sequences[name] = cls._sequences.get(name, 0) + 1
        return cls._sequences[name]

    @classmethod
    def build(cls, model_type: str, **overrides) -> Any:
        if model_type == "user":
            seq = cls.sequence("user_email")
            defaults = {
                "email": f"developer_{seq}@rails-lab.internal",
                "role": "member",
                "active": True
            }
            defaults.update(overrides)
            return User(**defaults)
        raise ValueError(f"Factory untuk '{model_type}' tidak terdaftar.")

    @classmethod
    def create(cls, model_type: str, **overrides) -> Any:
        instance = cls.build(model_type, **overrides)
        if not instance.save():
            raise RuntimeError("Gagal memvalidasi atau menyimpan instance dari FactoryBot.")
        return instance

# ==============================================================================
# 3. RAILS TEST FRAMEWORK (ActiveSupport::TestCase)
# ==============================================================================
class AssertionFailure(Exception):
    """Exception yang dipicu jika assertion validasi gagal."""
    pass


class RailsTestCase:
    """Base class test case memodelkan ActiveSupport::TestCase."""

    def __init__(self):
        self.db = Database.get_instance()

    def setup(self):
        """Lifecycle hook: dieksekusi sebelum setiap method pengujian."""
        pass

    def teardown(self):
        """Lifecycle hook: dieksekusi setelah setiap method pengujian."""
        pass

    # --- Assertion Helpers ---
    def assert_true(self, expression: bool, message: str = "Diharapkan True, tetapi False"):
        if not expression:
            raise AssertionFailure(message)

    def assert_equal(self, expected: Any, actual: Any, message: str = ""):
        if expected != actual:
            msg = message or f"Diharapkan '{expected}', tetapi mendapatkan '{actual}'"
            raise AssertionFailure(msg)

    def assert_difference(self, expression_fn: Callable[[], int], difference: int, message: str = ""):
        """
        Kloning dari assertion Rails `assert_difference(expression, difference = 1)`.
        Memastikan mutasi metrik database/state tepat sesuai ekspektasi.
        """
        before_val = expression_fn()
        # Mengembalikan konteks manager sederhana untuk blok pengujian
        class DifferenceContext:
            def __init__(self, outer, expected_diff, before):
                self.outer = outer
                self.expected_diff = expected_diff
                self.before = before

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    return False  # Biarkan exception lain lewat
                after_val = expression_fn()
                actual_diff = after_val - self.before
                if actual_diff != self.expected_diff:
                    custom_msg = (message or 
                                  f"assert_difference gagal: perubahan tercatat {actual_diff}, "
                                  f"seharusnya {self.expected_diff} (Nilai: {self.before} -> {after_val})")
                    raise AssertionFailure(custom_msg)
                return True

        return DifferenceContext(self, difference, before_val)

# ==============================================================================
# 4. IMPLEMENTASI TEST SUITE AKTUAL
# ==============================================================================
class UserQualityTestSuite(RailsTestCase):
    """Kumpulan skenario pengujian kualitas model User."""

    def setup(self):
        # Dipanggil sebelum setiap 'test_*'
        pass

    def test_user_validation_success(self):
        """Validasi bahwa User dapat dibuat dengan email valid."""
        user = FactoryBot.build("user", email="valid_admin@test.org")
        self.assert_true(user.save(), "Model gagal disimpan dengan atribut yang valid.")
        self.assert_equal("valid_admin@test.org", user.email)

    def test_assert_difference_tracking(self):
        """Memverifikasi mutasi record DB menggunakan assert_difference."""
        with self.assert_difference(User.count, 2):
            FactoryBot.create("user")
            FactoryBot.create("user")

    def test_isolation_and_rollback_integrity(self):
        """
        Memastikan bahwa test sebelumnya tidak mencemari database saat ini.
        DB harus tetap bersih berkat transaksi rollback otomatis.
        """
        # Pada test terisolasi ini, tabel harus dimulai dari kondisi terisolasi
        initial_count = User.count()
        FactoryBot.create("user", role="superadmin")
        self.assert_equal(initial_count + 1, User.count())

    def test_validation_failure(self):
        """Memverifikasi penolakan penyimpanan jika email cacat format."""
        invalid_user = FactoryBot.build("user", email="bukan_email")
        self.assert_equal(False, invalid_user.save(), "Model berhasil disimpan padahal format email salah!")

    def test_simulated_edge_case_failure(self):
        """Simulasi kasus di mana assertion mendeteksi regresi kode nyata."""
        with self.assert_difference(User.count, 1):
            # Simulasi bug: Developer lupa memanggil .save() sehingga mutasi DB bernilai 0
            _ = FactoryBot.build("user")

# ==============================================================================
# 5. TEST RUNNER BERORIENTASI PRODUCTION
# ==============================================================================
class RailsTestRunner:
    """Test Runner yang mengontrol lifecycle, isolasi transaksi, dan reporting ANSI."""

    def __init__(self, test_case_class):
        self.test_case_class = test_case_class
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.reports = []

    def run(self):
        print(f"\n{BOLD}{CYAN}=== Rails Quality Engine: Test Runner Execution ==={RESET}")
        print(f"Target Test Suite: {BOLD}{self.test_case_class.__name__}{RESET}")
        print(f"Transactional Fixtures: {GREEN}ENABLED (Snapshot/Rollback per test){RESET}\n")

        methods = [m for m in dir(self.test_case_class) if m.startswith("test_")]
        start_time = time.perf_counter()

        for method_name in methods:
            instance = self.test_case_class()
            db = Database.get_instance()
            
            # 1. Mulai isolasi database
            db.begin_transaction()
            test_start = time.perf_counter()
            status = "PASS"
            detail = ""

            try:
                instance.setup()
                test_fn = getattr(instance, method_name)
                test_fn()
                instance.teardown()
                self.passed += 1
                sys.stdout.write(f"{GREEN}.{RESET}")
            except AssertionFailure as af:
                self.failed += 1
                status = "FAIL"
                detail = str(af)
                sys.stdout.write(f"{RED}F{RESET}")
            except Exception as ex:
                self.errors += 1
                status = "ERROR"
                detail = "".join(traceback.format_exception_only(type(ex), ex)).strip()
                sys.stdout.write(f"{YELLOW}E{RESET}")
            finally:
                # 2. Rollback mutasi transaksi test
                db.rollback()
                sys.stdout.flush()
                duration_ms = (time.perf_counter() - test_start) * 1000
                self.reports.append((method_name, status, duration_ms, detail))

        total_duration = time.perf_counter() - start_time
        self._print_summary(total_duration)

    def _print_summary(self, total_duration: float):
        print(f"\n\n{BOLD}Laporan Hasil Pengujian Kualitas:{RESET}")
        print("-" * 75)
        for name, status, duration_ms, detail in self.reports:
            if status == "PASS":
                color = GREEN
            elif status == "FAIL":
                color = RED
            else:
                color = YELLOW

            print(f"[{color}{status:5s}{RESET}] {name:<38} ({duration_ms:.2f} ms)")
            if detail:
                print(f"       └── {YELLOW}Penyebab: {detail}{RESET}")

        print("-" * 75)
        total_runs = self.passed + self.failed + self.errors
        print(f"Selesai dalam {total_duration:.4f} detik ({(total_runs/total_duration if total_duration > 0 else 0):.1f} runs/s)")
        print(f"{BOLD}Ringkasan:{RESET} {self.passed} lulus, "
              f"{RED}{self.failed} gagal{RESET}, "
              f"{YELLOW}{self.errors} error{RESET}.\n")


if __name__ == "__main__":
    runner = RailsTestRunner(UserQualityTestSuite)
    runner.run()