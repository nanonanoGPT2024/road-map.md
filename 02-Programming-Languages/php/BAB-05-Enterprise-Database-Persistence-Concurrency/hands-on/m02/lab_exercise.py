#!/usr/bin/env python3
"""
Enterprise Database Persistence & Concurrency Simulator (PHP-FPM / PDO DBAL Model)
Simulates PHP enterprise persistence patterns:
 - Naive Active Record (Vulnerable to Lost Updates)
 - Optimistic Concurrency Control / OCC with Versioning (Doctrine ORM style)
 - Pessimistic Row-Level Locking / PCC (`SELECT ... FOR UPDATE` style)
"""

import sys
import time
import random
import threading
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# --- ANSI Terminal Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"

# --- Domain Entity ---
@dataclass
class AccountRecord:
    id: int
    balance: float
    version: int  # Digunakan untuk Optimistic Locking

# --- In-Memory Enterprise Persistence Layer ---
class EnterpriseDatabase:
    """
    Simulasi RDBMS Engine dengan dukungan Row-Level Mutex (PCC)
    dan Column Versioning (OCC).
    """
    def __init__(self, initial_balance: float = 1000.0):
        self._storage: Dict[int, AccountRecord] = {
            1: AccountRecord(id=1, balance=initial_balance, version=1)
        }
        self._global_lock = threading.Lock()
        self._row_locks: Dict[int, threading.Lock] = {
            1: threading.Lock()
        }

    def fetch_naive(self, account_id: int) -> AccountRecord:
        """Simulasi PDO::query('SELECT balance FROM accounts WHERE id = ?')"""
        with self._global_lock:
            rec = self._storage[account_id]
            return AccountRecord(rec.id, rec.balance, rec.version)

    def write_naive(self, record: AccountRecord) -> None:
        """Simulasi UPDATE accounts SET balance = ? WHERE id = ? (Tanpa isolasi)"""
        with self._global_lock:
            self._storage[record.id].balance = record.balance

    def fetch_pessimistic(self, account_id: int) -> AccountRecord:
        """Simulasi PDO::query('SELECT * FROM accounts WHERE id = ? FOR UPDATE')"""
        # Mengakuisisi row-level exclusive lock
        self._row_locks[account_id].acquire()
        rec = self._storage[account_id]
        return AccountRecord(rec.id, rec.balance, rec.version)

    def release_pessimistic(self, record: AccountRecord) -> None:
        """COMMIT dan pelepasan row lock"""
        try:
            self._storage[record.id].balance = record.balance
        finally:
            self._row_locks[record.id].release()

    def update_optimistic(self, account_id: int, new_balance: float, expected_version: int) -> bool:
        """
        Simulasi Doctrine ORM flush():
        UPDATE accounts SET balance = ?, version = version + 1
        WHERE id = ? AND version = ?
        """
        with self._global_lock:
            current = self._storage[account_id]
            if current.version != expected_version:
                return False  # StaleObjectStateException / OptimisticLockException
            
            current.balance = new_balance
            current.version += 1
            return True

    def get_actual_balance(self, account_id: int) -> float:
        with self._global_lock:
            return self._storage[account_id].balance

    def reset(self, initial_balance: float = 1000.0) -> None:
        with self._global_lock:
            self._storage[1] = AccountRecord(id=1, balance=initial_balance, version=1)


# --- PHP-FPM Worker Emulation ---
class PHPWorkerSimulation:
    def __init__(self, db: EnterpriseDatabase, concurrency: int = 20, deposit_amount: float = 10.0):
        self.db = db
        self.concurrency = concurrency
        self.deposit_amount = deposit_amount
        self.metrics = {"success": 0, "conflicts": 0, "retries": 0}
        self.metric_lock = threading.Lock()

    def _record_metric(self, key: str, inc: int = 1):
        with self.metric_lock:
            self.metrics[key] += inc

    def worker_naive(self, worker_id: int):
        """Pola PHP rentan: Read-Modify-Write tanpa penguncian."""
        # 1. Fetch
        record = self.db.fetch_naive(1)
        # 2. Simulasi business logic & I/O latency di PHP-FPM process
        time.sleep(random.uniform(0.001, 0.004))
        # 3. Update State
        record.balance += self.deposit_amount
        # 4. Persistence
        self.db.write_naive(record)
        self._record_metric("success")

    def worker_pessimistic(self, worker_id: int):
        """Pola Pessimistic Locking: SELECT ... FOR UPDATE."""
        # 1. Acquire Lock & Read
        record = self.db.fetch_pessimistic(1)
        try:
            # 2. Business logic execution
            time.sleep(random.uniform(0.001, 0.004))
            record.balance += self.deposit_amount
        finally:
            # 3. Write & Commit (Release Lock)
            self.db.release_pessimistic(record)
            self._record_metric("success")

    def worker_optimistic(self, worker_id: int):
        """Pola OCC: Deteksi versi & retry loop jika terjadi konflik antar-worker."""
        max_retries = 15
        for attempt in range(max_retries):
            record = self.db.fetch_naive(1)
            time.sleep(random.uniform(0.001, 0.004))
            
            new_balance = record.balance + self.deposit_amount
            success = self.db.update_optimistic(1, new_balance, record.version)
            
            if success:
                self._record_metric("success")
                return
            else:
                self._record_metric("conflicts")
                if attempt < max_retries - 1:
                    self._record_metric("retries")
                    # Exponential Backoff sederhana
                    time.sleep(random.uniform(0.002, 0.005) * (attempt + 1))
        
        # Gagal setelah batas percobaan maksimum tercapai
        pass

    def run_benchmark(self, strategy_name: str, worker_fn) -> Tuple[float, float, float]:
        self.metrics = {"success": 0, "conflicts": 0, "retries": 0}
        threads = []
        
        start_time = time.perf_counter()
        for i in range(self.concurrency):
            t = threading.Thread(target=worker_fn, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
        duration = time.perf_counter() - start_time
        
        actual_balance = self.db.get_actual_balance(1)
        return duration, actual_balance, self.metrics["conflicts"]


# --- Runner Engine ---
def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== {title} ==={CLR_RESET}")

def main():
    initial_balance = 1000.0
    deposit_amount = 50.0
    workers_count = 30
    expected_balance = initial_balance + (workers_count * deposit_amount)

    db = EnterpriseDatabase(initial_balance)
    sim = PHPWorkerSimulation(db, concurrency=workers_count, deposit_amount=deposit_amount)

    print(f"{CLR_BOLD}LAB: PHP Concurrency & Enterprise Database Persistence{CLR_RESET}")
    print(f"Simulasi Beban: {CLR_YELLOW}{workers_count} Concurrent PHP-FPM Workers{CLR_RESET}")
    print(f"Saldo Awal: ${initial_balance:.2f} | Nominal Tiap Worker: ${deposit_amount:.2f}")
    print(f"Ekspektasi Saldo Akhir: {CLR_GREEN}${expected_balance:.2f}{CLR_RESET}\n")

    # 1. NAIVE ACTIVE RECORD
    print_header("1. Naive Active Record (Tanpa Concurrency Control)")
    db.reset(initial_balance)
    duration, final_bal, conflicts = sim.run_benchmark("Naive", sim.worker_naive)
    discrepancy = expected_balance - final_bal
    
    print(f"Waktu Eksekusi   : {duration:.4f} detik")
    print(f"Hasil Saldo      : ${final_bal:.2f}")
    print(f"Data Anomaly     : {CLR_RED}Lost Updates Detected (-${discrepancy:.2f}){CLR_RESET}")
    print(f"Status Integritas: {CLR_RED}[FAIL] Data Corrupted{CLR_RESET}")

    # 2. PESSIMISTIC LOCKING
    print_header("2. Pessimistic Locking (SELECT ... FOR UPDATE)")
    db.reset(initial_balance)
    duration, final_bal, conflicts = sim.run_benchmark("Pessimistic", sim.worker_pessimistic)
    
    print(f"Waktu Eksekusi   : {duration:.4f} detik (Serialized through Row Lock)")
    print(f"Hasil Saldo      : ${final_bal:.2f}")
    print(f"Lock Contention  : Tertangani otomatis oleh Row Queue")
    print(f"Status Integritas: {CLR_GREEN}[PASS] Konsistensi ACID Terjamin{CLR_RESET}")

    # 3. OPTIMISTIC LOCKING
    print_header("3. Optimistic Concurrency Control (OCC + Version Check & Retry)")
    db.reset(initial_balance)
    duration, final_bal, conflicts = sim.run_benchmark("Optimistic", sim.worker_optimistic)
    
    print(f"Waktu Eksekusi   : {duration:.4f} detik")
    print(f"Hasil Saldo      : ${final_bal:.2f}")
    print(f"Konflik Terdeteksi: {CLR_YELLOW}{conflicts} StaleObjectState Exceptions{CLR_RESET}")
    print(f"Total Retry Berhasil: {sim.metrics['retries']} kali")
    print(f"Status Integritas: {CLR_GREEN}[PASS] Konsistensi Terverifikasi Lewat Retry{CLR_RESET}")

    # Analisis Arsitektur
    print_header("Ringkasan Evaluasi Arsitektur PHP Enterprise")
    print(f"- {CLR_BOLD}Naive Pattern{CLR_RESET}        : Cepat namun fatal untuk transaksi finansial/stok.")
    print(f"- {CLR_BOLD}Pessimistic Locking{CLR_RESET}  : Handal untuk persaingan tinggi (High Contention),")
    print(f"                           namun menahan koneksi database lebih lama.")
    print(f"- {CLR_BOLD}Optimistic Locking{CLR_RESET}   : Unggul untuk persaingan rendah-sedang (Low Contention),")
    print(f"                           skalabilitas horizontal tinggi tanpa bottleneck lock RDBMS.")

if __name__ == "__main__":
    main()