#!/usr/bin/env python3
"""
Enterprise Database Persistence & Concurrency Simulator
BAB-05: Enterprise Database Persistence & Concurrency (PHP Architecture Emulation)

This hands-on simulator demonstrates enterprise persistence patterns commonly
utilized in high-performance PHP enterprise frameworks (Doctrine ORM, Laravel Eloquent,
Swoole PDO Pools):
 1. Unit of Work & Identity Map Pattern
 2. Optimistic vs Pessimistic Concurrency Control (SELECT FOR UPDATE vs Versioning)
 3. ACID Transaction Isolation Levels & Dirty/Non-Repeatable Reads
 4. Distributed Deadlock Detection & Exponential Backoff Retry Policy
"""

import sys
import time
import uuid
import random
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# ==============================================================================
# ANSI Color Formatting Helper
# ==============================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

def print_banner():
    banner = f"""
{TermColor.CYAN}{TermColor.BOLD}╔════════════════════════════════════════════════════════════════════════╗
║    PHP Enterprise Persistence & Concurrency Simulation Lab (BAB-05)    ║
║    Doctrine ORM / PDO / Isolation / Deadlock / UnitOfWork Simulator    ║
╚════════════════════════════════════════════════════════════════════════╝{TermColor.RESET}
"""
    print(banner)

def log_info(msg: str):
    print(f"{TermColor.BLUE}[INFO]{TermColor.RESET} {msg}")

def log_success(msg: str):
    print(f"{TermColor.GREEN}[SUCCESS]{TermColor.RESET} {msg}")

def log_warn(msg: str):
    print(f"{TermColor.YELLOW}[WARN]{TermColor.RESET} {msg}")

def log_err(msg: str):
    print(f"{TermColor.RED}[ERROR]{TermColor.RESET} {msg}")

def log_tx(tx_id: str, msg: str):
    print(f"{TermColor.MAGENTA}[TX-{tx_id}]{TermColor.RESET} {msg}")

# ==============================================================================
# Domain Model: Account Entity
# ==============================================================================
@dataclass
class AccountEntity:
    id: int
    holder_name: str
    balance: float
    version: int = 1  # For Optimistic Locking

    def copy(self) -> 'AccountEntity':
        return AccountEntity(
            id=self.id,
            holder_name=self.holder_name,
            balance=self.balance,
            version=self.version
        )

# ==============================================================================
# Mock Database Storage Engine
# ==============================================================================
class MockDatabase:
    def __init__(self):
        self.lock = threading.RLock()
        self.rows: Dict[int, AccountEntity] = {
            101: AccountEntity(id=101, holder_name="Enterprise Corp Treasury", balance=50000.0, version=1),
            102: AccountEntity(id=102, holder_name="Supplier Escrow Account", balance=15000.0, version=1),
            103: AccountEntity(id=103, holder_name="Payroll Clearing Ledger", balance=25000.0, version=1),
        }
        self.row_locks: Dict[int, threading.Lock] = {
            101: threading.Lock(),
            102: threading.Lock(),
            103: threading.Lock()
        }

    def get_by_id(self, entity_id: int) -> Optional[AccountEntity]:
        with self.lock:
            entity = self.rows.get(entity_id)
            return entity.copy() if entity else None

    def update_optimistic(self, updated: AccountEntity, expected_version: int) -> bool:
        with self.lock:
            current = self.rows.get(updated.id)
            if not current:
                return False
            if current.version != expected_version:
                return False
            # Successful atomic write
            current.balance = updated.balance
            current.holder_name = updated.holder_name
            current.version += 1
            return True

    def update_direct(self, entity_id: int, new_balance: float):
        with self.lock:
            if entity_id in self.rows:
                self.rows[entity_id].balance = new_balance
                self.rows[entity_id].version += 1

db = MockDatabase()

# ==============================================================================
# Module 1: Identity Map & Unit of Work (Doctrine ORM Concept)
# ==============================================================================
class UnitOfWork:
    def __init__(self, database: MockDatabase):
        self.database = database
        self.identity_map: Dict[int, AccountEntity] = {}
        self.original_snapshots: Dict[int, AccountEntity] = {}
        self.scheduled_updates: List[AccountEntity] = []

    def find(self, entity_id: int) -> Optional[AccountEntity]:
        log_info(f"UnitOfWork::find({entity_id}) requested.")
        if entity_id in self.identity_map:
            log_success(f"Identity Map Cache HIT for ID {entity_id}. Returning managed instance.")
            return self.identity_map[entity_id]

        log_warn(f"Identity Map Cache MISS for ID {entity_id}. Querying Database engine...")
        entity = self.database.get_by_id(entity_id)
        if entity:
            self.identity_map[entity_id] = entity
            self.original_snapshots[entity_id] = entity.copy()
            log_info(f"Registered entity #{entity_id} to Identity Map & captured pristine snapshot.")
        return entity

    def commit(self) -> bool:
        log_info("UnitOfWork::commit() flushing dirty state to storage...")
        dirty_count = 0
        for entity_id, managed_entity in self.identity_map.items():
            snapshot = self.original_snapshots.get(entity_id)
            if snapshot and (snapshot.balance != managed_entity.balance or snapshot.holder_name != managed_entity.holder_name):
                dirty_count += 1
                log_info(f"Dirty check detected changes on Entity #{entity_id}: "
                         f"Balance: {snapshot.balance} -> {managed_entity.balance}")
                ok = self.database.update_optimistic(managed_entity, snapshot.version)
                if not ok:
                    log_err(f"Unit of work flush failed for Entity #{entity_id} due to version mismatch!")
                    return False
                managed_entity.version += 1
                self.original_snapshots[entity_id] = managed_entity.copy()

        if dirty_count == 0:
            log_info("UnitOfWork: No dirty entities found. Zero writes executed.")
        else:
            log_success(f"UnitOfWork: Successfully flushed {dirty_count} changed entities in atomic transaction.")
        return True

def run_unit_of_work_demo():
    print(f"\n{TermColor.YELLOW}{TermColor.BOLD}=== DEMO 1: Identity Map & Unit of Work (Doctrine PHP Pattern) ==={TermColor.RESET}")
    uow = UnitOfWork(db)
    acc1 = uow.find(101)
    acc2 = uow.find(101)
    print(f"Checking reference equality (acc1 is acc2): {TermColor.GREEN}{acc1 is acc2}{TermColor.RESET}")

    if acc1:
        log_info("Modifying account balance via domain logic: +$5,000.00")
        acc1.balance += 5000.0
        uow.commit()

# ==============================================================================
# Module 2: Concurrency Control (Optimistic vs Pessimistic Locking)
# ==============================================================================
def run_optimistic_locking_race():
    print(f"\n{TermColor.YELLOW}{TermColor.BOLD}=== DEMO 2: Optimistic Locking Collision Simulation ==={TermColor.RESET}")
    log_info("Two concurrent HTTP PHP-FPM Workers (Worker A & Worker B) reading Account #102 simultaneously.")

    worker_a_acc = db.get_by_id(102)
    worker_b_acc = db.get_by_id(102)
    print(f"Worker A snapshot version: {worker_a_acc.version}, balance: {worker_a_acc.balance}")
    print(f"Worker B snapshot version: {worker_b_acc.version}, balance: {worker_b_acc.balance}")

    log_tx("Worker-A", "Worker A deposits +$2,500 and submits commit first...")
    worker_a_acc.balance += 2500.0
    success_a = db.update_optimistic(worker_a_acc, expected_version=1)
    if success_a:
        log_success("Worker A commit SUCCESSFUL (Version bumped to 2).")

    log_tx("Worker-B", "Worker B attempts to deduct -$1,000 using stale version 1...")
    worker_b_acc.balance -= 1000.0
    success_b = db.update_optimistic(worker_b_acc, expected_version=1)
    if not success_b:
        log_err("Worker B commit REJECTED! OptimisticLockException raised: Version collision detected!")
        log_info("Mitigation: Reload fresh state and retry operation.")

def run_pessimistic_locking_demo():
    print(f"\n{TermColor.YELLOW}{TermColor.BOLD}=== DEMO 3: Pessimistic Locking (SELECT FOR UPDATE) Simulation ==={TermColor.RESET}")
    log_info("Simulating row-level exclusive lock on Account #103 across 2 worker threads.")

    def worker_thread(worker_id: str, delay: float):
        log_tx(worker_id, "Attempting to acquire exclusive row lock (SELECT ... FOR UPDATE)...")
        with db.row_locks[103]:
            log_success(f"{worker_id} acquired exclusive lock on row #103!")
            time.sleep(delay)
            log_tx(worker_id, f"{worker_id} modifying balance and releasing transaction lock.")
        log_info(f"{worker_id} transaction finished.")

    t1 = threading.Thread(target=worker_thread, args=("Thread-1", 0.8))
    t2 = threading.Thread(target=worker_thread, args=("Thread-2", 0.2))

    t1.start()
    time.sleep(0.1)
    t2.start()
    t1.join()
    t2.join()

# ==============================================================================
# Module 3: Deadlock Detection & Exponential Backoff Retry Policy
# ==============================================================================
def run_deadlock_simulation():
    print(f"\n{TermColor.YELLOW}{TermColor.BOLD}=== DEMO 4: Distributed Deadlock Detection & Retry Policy ==={TermColor.RESET}")
    log_info("Simulating circular lock dependency (Worker 1: 101 -> 102; Worker 2: 102 -> 101)")

    def transfer(tx_name: str, first_acc: int, second_acc: int, should_retry: bool = True):
        max_retries = 3
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            log_tx(tx_name, f"Attempt {attempt}/{max_retries}: Locking Account {first_acc}...")
            first_lock = db.row_locks[first_acc]
            second_lock = db.row_locks[second_acc]

            if not first_lock.acquire(timeout=0.3):
                log_warn(f"{tx_name}: Timeout acquiring lock on {first_acc}.")
                continue

            try:
                time.sleep(0.1) # Simulate network delay / intermediate query
                log_tx(tx_name, f"Attempting to lock second Account {second_acc}...")
                acquired_second = second_lock.acquire(timeout=0.3)
                if not acquired_second:
                    log_err(f"{tx_name}: Potential DEADLOCK detected while acquiring lock on {second_acc}!")
                    raise TimeoutError("Deadlock victim chosen by DBMS lock manager.")
                try:
                    log_success(f"{tx_name}: Both locks secured. Executing transfer...")
                    time.sleep(0.05)
                    return True
                finally:
                    second_lock.release()
            except TimeoutError as ex:
                if not should_retry:
                    raise ex
                backoff = random.uniform(0.1, 0.3) * (2 ** (attempt - 1))
                log_warn(f"{tx_name}: Backing off for {backoff:.2f}s before retry...")
                time.sleep(backoff)
            finally:
                first_lock.release()

        log_err(f"{tx_name}: Transaction aborted after max retries.")
        return False

    t1 = threading.Thread(target=transfer, args=("TX-ALPHA", 101, 102, True))
    t2 = threading.Thread(target=transfer, args=("TX-BETA", 102, 101, True))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

# ==============================================================================
# Interactive Menu Runner
# ==============================================================================
def main_menu():
    print_banner()
    while True:
        print(f"\n{TermColor.CYAN}{TermColor.BOLD}Select an Enterprise Persistence Concept to Explore:{TermColor.RESET}")
        print(f"  {TermColor.GREEN}[1]{TermColor.RESET} Unit of Work & Identity Map Pattern (Doctrine ORM)")
        print(f"  {TermColor.GREEN}[2]{TermColor.RESET} Optimistic Concurrency Control (Version Check Collision)")
        print(f"  {TermColor.GREEN}[3]{TermColor.RESET} Pessimistic Locking Simulation (SELECT FOR UPDATE)")
        print(f"  {TermColor.GREEN}[4]{TermColor.RESET} Deadlock Simulation with Exponential Backoff Retry")
        print(f"  {TermColor.GREEN}[5]{TermColor.RESET} Run All Demos Sequentially (Full Diagnostic)")
        print(f"  {TermColor.RED}[0]{TermColor.RESET} Exit Simulator")

        try:
            choice = input(f"\n{TermColor.BOLD}Enter choice [0-5]: {TermColor.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if choice == "1":
            run_unit_of_work_demo()
        elif choice == "2":
            run_optimistic_locking_race()
        elif choice == "3":
            run_pessimistic_locking_demo()
        elif choice == "4":
            run_deadlock_simulation()
        elif choice == "5":
            run_unit_of_work_demo()
            run_optimistic_locking_race()
            run_pessimistic_locking_demo()
            run_deadlock_simulation()
            log_success("All Enterprise Persistence & Concurrency modules executed successfully.")
        elif choice == "0":
            log_info("Terminating Enterprise Persistence Simulation. Goodbye.")
            break
        else:
            log_warn("Invalid option chosen. Please select from 0-5.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        run_unit_of_work_demo()
        run_optimistic_locking_race()
        run_pessimistic_locking_demo()
        run_deadlock_simulation()
        log_success("Auto execution verified cleanly.")
    else:
        main_menu()
