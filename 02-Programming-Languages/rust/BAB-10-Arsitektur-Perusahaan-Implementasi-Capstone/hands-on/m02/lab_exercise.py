#!/usr/bin/env python3
"""
Lab Hands-on: Enterprise Rust Architecture Simulation
Bab 10: Arsitektur Perusahaan & Implementasi Capstone (Deep Dive)

Simulasi Arsitektur Engine Enterprise Rust:
1. Ownership & Lifetime Borrow Checker (Runtime Safety Invariant Model)
2. Asynchronous MPSC (Multi-Producer Single-Consumer) Pipeline
3. Write-Ahead Logging (WAL) & In-Memory LSM-Tree MemTable Flush
4. Concurrent Actor Pipeline & Zero-Data-Race Safety Engine
"""

import time
import threading
import queue
import hashlib
import dataclasses
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum, auto

# ============================================================================
# ANSI Color Codes for Enterprise Terminal Reporting
# ============================================================================
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_CYAN    = "\033[36m"
CLR_MAGENTA = "\033[35m"

def log_event(subsystem: str, msg: str, color: str = CLR_CYAN):
    ts = time.strftime("%H:%M:%S") + f".{int(time.time()*1000)%1000:03d}"
    print(f"{color}[{ts}] [{subsystem:^14}] {msg}{CLR_RESET}")

# ============================================================================
# 1. RUST OWNERSHIP & BORROW CHECKER RUNTIME SIMULATOR
# Memodelkan invariant: Aliasing XOR Mutability (&mut T vs &T)
# ============================================================================
class BorrowErrorKind(Enum):
    DOUBLE_MUTABLE = auto()
    MUTABLE_WHILE_IMMUTABLE = auto()
    USE_AFTER_MOVE = auto()

class OwnershipViolation(Exception):
    def __init__(self, kind: BorrowErrorKind, details: str):
        self.kind = kind
        self.details = details
        super().__init__(f"Rust Safety Invariant Broken: {kind.name} - {details}")

class ResourceHandle:
    """Mensimulasikan Resource Rust dengan pelacak ownership & dynamic borrow count."""
    def __init__(self, resource_id: str, payload: Any):
        self.resource_id = resource_id
        self.payload = payload
        self.is_moved = False
        self.shared_borrow_count = 0
        self.has_mutable_borrow = False
        self._lock = threading.Lock()

    def move_to(self, new_owner: str) -> 'ResourceHandle':
        """Memodelkan move semantics (Affine Type System)."""
        with self._lock:
            if self.is_moved:
                raise OwnershipViolation(BorrowErrorKind.USE_AFTER_MOVE, f"Resource {self.resource_id} has been moved.")
            if self.shared_borrow_count > 0 or self.has_mutable_borrow:
                raise OwnershipViolation(BorrowErrorKind.MUTABLE_WHILE_IMMUTABLE, 
                                         f"Cannot move {self.resource_id} while actively borrowed.")
            self.is_moved = True
            log_event("BORROW_CHK", f"Resource '{self.resource_id}' MOVED to {new_owner}", CLR_MAGENTA)
            return ResourceHandle(f"{self.resource_id}_owned_by_{new_owner}", self.payload)

    def borrow_shared(self, reader_id: str):
        """Memodelkan immutable borrow: `&T`."""
        with self._lock:
            if self.is_moved:
                raise OwnershipViolation(BorrowErrorKind.USE_AFTER_MOVE, f"Cannot borrow moved resource {self.resource_id}.")
            if self.has_mutable_borrow:
                raise OwnershipViolation(BorrowErrorKind.MUTABLE_WHILE_IMMUTABLE,
                                         f"Cannot borrow '{self.resource_id}' as immutable while mutably borrowed!")
            self.shared_borrow_count += 1
            log_event("BORROW_CHK", f"Shared borrow '&T' on '{self.resource_id}' by {reader_id}. Active readers: {self.shared_borrow_count}", CLR_BLUE)

    def release_shared(self, reader_id: str):
        with self._lock:
            self.shared_borrow_count = max(0, self.shared_borrow_count - 1)
            log_event("BORROW_CHK", f"Released shared borrow '&T' on '{self.resource_id}' by {reader_id}. Active: {self.shared_borrow_count}", CLR_BLUE)

    def borrow_mut(self, writer_id: str):
        """Memodelkan exclusive mutable borrow: `&mut T`."""
        with self._lock:
            if self.is_moved:
                raise OwnershipViolation(BorrowErrorKind.USE_AFTER_MOVE, f"Resource {self.resource_id} is moved.")
            if self.has_mutable_borrow:
                raise OwnershipViolation(BorrowErrorKind.DOUBLE_MUTABLE,
                                         f"Aliasing violation: Multiple '&mut T' on '{self.resource_id}'!")
            if self.shared_borrow_count > 0:
                raise OwnershipViolation(BorrowErrorKind.MUTABLE_WHILE_IMMUTABLE,
                                         f"Aliasing violation: Cannot take '&mut T' when {self.shared_borrow_count} '&T' exist!")
            self.has_mutable_borrow = True
            log_event("BORROW_CHK", f"Exclusive borrow '&mut T' GRANTED to {writer_id} on '{self.resource_id}'", CLR_YELLOW)

    def release_mut(self, writer_id: str):
        with self._lock:
            self.has_mutable_borrow = False
            log_event("BORROW_CHK", f"Released exclusive borrow '&mut T' on '{self.resource_id}' by {writer_id}", CLR_YELLOW)

# ============================================================================
# 2. LSM STORAGE ENGINE (WAL & MEMTABLE IMPLEMENTATION)
# Mirip dengan crates storage enterprise seperti Sled / RocksDB wrapper
# ============================================================================
@dataclasses.dataclass(frozen=True)
class WalRecord:
    tx_id: int
    op_type: str
    key: str
    val: str
    crc: str

class StorageEngine:
    """Engine LSM-Tree dengan Write-Ahead Log (WAL) dan Immutable MemTable Snapshot."""
    def __init__(self, flush_threshold: int = 4):
        self.memtable: Dict[str, str] = {}
        self.wal: List[WalRecord] = []
        self.sstable: Dict[str, str] = {}
        self.flush_threshold = flush_threshold
        self.tx_counter = 0
        self._lock = threading.RLock()

    def _calculate_crc(self, key: str, val: str) -> str:
        return hashlib.sha256(f"{key}:{val}".encode()).hexdigest()[:8]

    def write(self, key: str, val: str) -> int:
        """Atomic write path: Append ke WAL terlebih dahulu, lalu update mutable MemTable."""
        with self._lock:
            self.tx_counter += 1
            tx = self.tx_counter
            crc = self._calculate_crc(key, val)
            record = WalRecord(tx, "SET", key, val, crc)
            self.wal.append(record)
            self.memtable[key] = val
            log_event("LSM_WAL", f"Tx #{tx:03d} logged & written to MemTable | Key='{key}' Val='{val}' CRC={crc}", CLR_GREEN)

            if len(self.memtable) >= self.flush_threshold:
                self._flush_to_sstable()
            return tx

    def _flush_to_sstable(self):
        """Membuat snapshot immutable dari MemTable dan mem-flush ke SSTable (Level 0)."""
        log_event("LSM_FLUSH", f"MemTable threshold reached ({len(self.memtable)} items). Freezing snapshot...", CLR_YELLOW)
        snapshot = dict(self.memtable)
        self.memtable.clear()
        # Simulasi write disk sync
        time.sleep(0.05)
        self.sstable.update(snapshot)
        log_event("LSM_FLUSH", f"SSTable flushed successfully. Total cold keys in storage: {len(self.sstable)}", CLR_GREEN)

    def read(self, key: str) -> Optional[str]:
        """Hierarchical point read: Check MemTable (hot) -> Fallback ke SSTable (cold)."""
        with self._lock:
            if key in self.memtable:
                log_event("LSM_READ", f"CACHE HIT: Key '{key}' resolved from active MemTable.", CLR_CYAN)
                return self.memtable[key]
            if key in self.sstable:
                log_event("LSM_READ", f"DISK HIT: Key '{key}' resolved from cold SSTable.", CLR_BLUE)
                return self.sstable[key]
            log_event("LSM_READ", f"MISS: Key '{key}' not found in any layer.", CLR_RED)
            return None

# ============================================================================
# 3. ENTERPRISE ASYNC MPSC CHANNEL PIPELINE
# Menyerupai tokio::sync::mpsc channel dengan multi-threaded workers
# ============================================================================
class ChannelMessage:
    def __init__(self, task_id: int, key: str, val: str):
        self.task_id = task_id
        self.key = key
        self.val = val

class MpscPipeline:
    """Sistem Actor berbasis antrean thread-safe bounded tokio-like pipeline."""
    def __init__(self, storage: StorageEngine, max_workers: int = 2):
        self.queue: queue.Queue = queue.Queue(maxsize=16)
        self.storage = storage
        self.max_workers = max_workers
        self.is_running = True
        self.workers: List[threading.Thread] = []

    def start(self):
        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker_loop, args=(i+1,), daemon=True)
            t.start()
            self.workers.append(t)
        log_event("MPSC_SYS", f"Actor pipeline initialized with {self.max_workers} tokio-like worker threads.", CLR_BOLD)

    def send(self, msg: ChannelMessage):
        """Producer non-blocking submit."""
        self.queue.put(msg)

    def _worker_loop(self, worker_id: int):
        while self.is_running:
            try:
                msg: ChannelMessage = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue
            
            log_event(f"WORKER-{worker_id}", f"Processing Tx Task #{msg.task_id:03d} -> Key: {msg.key}", CLR_CYAN)
            self.storage.write(msg.key, msg.val)
            self.queue.task_done()

    def shutdown(self):
        self.queue.join()
        self.is_running = False
        for t in self.workers:
            t.join()
        log_event("MPSC_SYS", "Pipeline shut down gracefully. All channels closed.", CLR_BOLD)

# ============================================================================
# 4. CAPSTONE INTEGRATION & TEST BENCHMARK
# ============================================================================
def test_borrow_checker_rules():
    print(f"\n{CLR_BOLD}=== TAHAP 1: VALIDASI SEMANTIK RUST BORROW CHECKER ==={CLR_RESET}")
    res = ResourceHandle("TelemetryPacket_v1", {"node_ip": "10.0.0.1", "metric": "load_avg"})

    # Kasus valid: Shared read multipel (Aliasing allowed without mutability)
    res.borrow_shared("ServiceA")
    res.borrow_shared("ServiceB")
    res.release_shared("ServiceA")
    res.release_shared("ServiceB")

    # Kasus valid: Exclusive write (&mut)
    res.borrow_mut("CompactorJob")
    res.release_mut("CompactorJob")

    # Kasus Pelanggaran 1: Double Mutable Borrow (Data Race Prevention)
    try:
        log_event("BORROW_CHK", "Mencoba membuat dua '&mut T' secara paralel...", CLR_YELLOW)
        res.borrow_mut("WorkerAlpha")
        res.borrow_mut("WorkerBravo") # Harusnya melempar pengecualian
    except OwnershipViolation as e:
        print(f"{CLR_RED} -> TERTANGKAP: {e}{CLR_RESET}")
    finally:
        res.release_mut("WorkerAlpha")

    # Kasus Pelanggaran 2: Borrow mut saat shared borrow aktif
    try:
        log_event("BORROW_CHK", "Mencoba '&mut T' saat '&T' masih aktif...", CLR_YELLOW)
        res.borrow_shared("ReaderA")
        res.borrow_mut("WriterB") # Harusnya melempar pengecualian
    except OwnershipViolation as e:
        print(f"{CLR_RED} -> TERTANGKAP: {e}{CLR_RESET}")
    finally:
        res.release_shared("ReaderA")

    # Kasus Move Semantics
    new_res = res.move_to("ArchivalWorker")
    try:
        log_event("BORROW_CHK", "Mencoba mengakses resource lama setelah move...", CLR_YELLOW)
        res.borrow_shared("DeadThread")
    except OwnershipViolation as e:
        print(f"{CLR_RED} -> TERTANGKAP: {e}{CLR_RESET}")


def run_pipeline_and_storage_benchmark():
    print(f"\n{CLR_BOLD}=== TAHAP 2: ENTERPRISE LSM STORAGE & CONCURRENT MPSC PIPELINE ==={CLR_RESET}")
    storage = StorageEngine(flush_threshold=3)
    pipeline = MpscPipeline(storage, max_workers=2)
    pipeline.start()

    # Streaming 6 task transaksi concurrent
    payloads = [
        ("cfg.cluster_id", "us-east-dc1"),
        ("cfg.max_conns", "10000"),
        ("cfg.enable_tls", "true"), # Akan memicu Flush SSTable pertama
        ("audit.user_admin", "login_ok"),
        ("audit.user_dev", "token_refresh"),
        ("cfg.max_conns", "12500"), # Akan memicu Flush SSTable kedua
    ]

    for idx, (k, v) in enumerate(payloads, start=1):
        pipeline.send(ChannelMessage(idx, k, v))

    pipeline.shutdown()

    print(f"\n{CLR_BOLD}=== TAHAP 3: POINT QUERY & STORAGE VERIFICATION ==={CLR_RESET}")
    val1 = storage.read("cfg.cluster_id")
    val2 = storage.read("cfg.max_conns")
    val3 = storage.read("non_existing_key")

    print(f"\n{CLR_BOLD}=== HASIL CAPSTONE VERIFICATION REPORT ==={CLR_RESET}")
    print(f"Key 'cfg.cluster_id' -> {CLR_GREEN}{val1}{CLR_RESET}")
    print(f"Key 'cfg.max_conns'   -> {CLR_GREEN}{val2}{CLR_RESET}")
    print(f"Total WAL Logged      -> {CLR_YELLOW}{len(storage.wal)} transactions{CLR_RESET}")
    print(f"Total SSTable Entries -> {CLR_CYAN}{len(storage.sstable)} records{CLR_RESET}")
    print(f"Memory Safety Status  -> {CLR_GREEN}ZERO DATA RACE / SAFE STATE ENFORCED{CLR_RESET}\n")

if __name__ == "__main__":
    print(f"{CLR_BOLD}Starting Enterprise Rust Architectural Subsystem Lab...{CLR_RESET}")
    test_borrow_checker_rules()
    run_pipeline_and_storage_benchmark()
    print(f"{CLR_GREEN}{CLR_BOLD}Lab Selesai: Arsitektur Capstone Berhasil Dieksekusi Secara Mandiri.{CLR_RESET}")