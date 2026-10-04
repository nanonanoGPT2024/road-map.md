#!/usr/bin/env python3
"""
Lab Hands-on: Rust Fearless Concurrency Engine Simulator
Bab 05: Konkurensi Tanpa Rasa Takut (Fearless Concurrency) - Modul 02 Deep Dive

Skrip ini memodelkan dan memvalidasi primitif konkurensi inti Rust:
1. Ownership Transfer (Move Semantics across Thread Boundaries)
2. MPSC (Multi-Producer, Single-Consumer) Channel dengan Cloneable Sender
3. Arc<Mutex<T>> (Atomic Reference Counting + Mutex Guard Pattern)
4. Pencegahan Data Race terverifikasi secara matematis & konkuren
"""

import sys
import time
import threading
import queue
import hashlib
from typing import Generic, TypeVar, Optional, Any

# ANSI Color Codes untuk Visualisasi Terminal
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"

T = TypeVar("T")

# ==============================================================================
# 1. SIMULATOR OWNERSHIP & MOVE SEMANTICS KE THREAD LAIN
# ==============================================================================
class MoveError(Exception):
    """Dilemparkan ketika data yang telah di-'move' diakses kembali."""
    pass

class ScopedResource(Generic[T]):
    """
    Mensimulasikan variabel Rust dengan semantik kepemilikan (ownership).
    Setelah nilai di-'move' ke thread lain, akses lokal akan ditolak.
    """
    def __init__(self, name: str, value: T):
        self.name = name
        self._value: Optional[T] = value
        self._moved = False
        self._lock = threading.Lock()

    def move(self) -> T:
        """Mentransfer kepemilikan objek keluar (misal ke closure thread)."""
        with self._lock:
            if self._moved:
                raise MoveError(f"Borrow Checker Error: Nilai '{self.name}' telah di-move!")
            val = self._value
            self._value = None
            self._moved = True
            return val # type: ignore

    def read(self) -> T:
        """Membaca resource jika masih berstatus valid dalam scope."""
        with self._lock:
            if self._moved:
                raise MoveError(f"Compile-Time Safety Violation: '{self.name}' digunakan setelah di-move!")
            return self._value # type: ignore


# ==============================================================================
# 2. IMPLEMENTASI MPSC (MULTI-PRODUCER, SINGLE-CONSUMER) CHANNEL
# ==============================================================================
class Sender(Generic[T]):
    """Sisi Pengirim Channel MPSC. Mendukung metode .clone()."""
    def __init__(self, shared_queue: queue.Queue, ref_counter: list, lock: threading.Lock):
        self._queue = shared_queue
        self._ref_counter = ref_counter
        self._lock = lock
        with self._lock:
            self._ref_counter[0] += 1

    def send(self, item: T) -> None:
        """Mengirim data ke saluran buffer mpsc."""
        self._queue.put(item)

    def clone(self) -> "Sender[T]":
        """Membuat salinan pengirim (Multiple Producer)."""
        return Sender(self._queue, self._ref_counter, self._lock)

    def drop(self) -> None:
        """Menghancurkan satu instans sender (RAII drop simulation)."""
        with self._lock:
            self._ref_counter[0] -= 1
            if self._ref_counter[0] == 0:
                # Mengirim sentinel tanda semua sender telah tertutup
                self._queue.put(None)

class Receiver(Generic[T]):
    """Sisi Penerima Tunggal Channel MPSC (Single Consumer)."""
    def __init__(self, shared_queue: queue.Queue):
        self._queue = shared_queue

    def recv(self) -> Optional[T]:
        """Memblokir eksekusi sampai menerima data atau seluruh Sender ter-drop."""
        item = self._queue.get()
        if item is None:
            # Re-insert token sentinel untuk pemanggilan berulang jika diperlukan
            self._queue.put(None)
            return None
        return item

def channel() -> tuple[Sender[T], Receiver[T]]:
    """Membentuk pasangan (tx, rx) layaknya std::sync::mpsc::channel di Rust."""
    q: queue.Queue = queue.Queue()
    counter = [0]
    lock = threading.Lock()
    tx = Sender(q, counter, lock)
    rx = Receiver(q)
    return tx, rx


# ==============================================================================
# 3. IMPLEMENTASI Arc<Mutex<T>> (ATOMIC REFERENCE COUNTING + MUTEX)
# ==============================================================================
class MutexGuard(Generic[T]):
    """RAII Guard yang menjamin mutual exclusion selama masa pakai pointer."""
    def __init__(self, data_ref: list, lock: threading.Lock):
        self._data_ref = data_ref
        self._lock = lock

    def __enter__(self) -> list:
        return self._data_ref

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()

class Mutex(Generic[T]):
    """Mutex pembungkus internal state."""
    def __init__(self, data: T):
        self._data = [data]
        self._raw_lock = threading.Lock()

    def lock(self) -> MutexGuard[T]:
        """Mengakuisisi exclusive lock dan mengembalikan scoped guard."""
        self._raw_lock.acquire()
        return MutexGuard(self._data, self._raw_lock)

class Arc(Generic[T]):
    """
    Atomic Reference Counter (Arc) yang mengelola masa hidup data di heap lintas thread.
    """
    def __init__(self, mutex: Mutex[T]):
        self._mutex = mutex
        self._ref_count = [1]
        self._counter_lock = threading.Lock()

    def clone(self) -> "Arc[T]":
        """Meningkatkan reference count secara atomik saat dibagikan ke thread baru."""
        with self._counter_lock:
            self._ref_count[0] += 1
        return self

    def lock(self) -> MutexGuard[T]:
        """Mendelegasikan penguncian ke inner Mutex."""
        return self._mutex.lock()

    def strong_count(self) -> int:
        """Mengembalikan jumlah referensi aktif ke objek shared memory."""
        with self._counter_lock:
            return self._ref_count[0]

    def drop(self) -> None:
        """Mengurangi ref count saat scope thread berakhir."""
        with self._counter_lock:
            self._ref_count[0] -= 1


# ==============================================================================
# 4. HANDS-ON TEST BENCH & ENGINE EXECUTION
# ==============================================================================
def header(title: str):
    print(f"\n{CLR_BOLD}{CLR_BLUE}{'=' * 75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}{'=' * 75}{CLR_RESET}")

def test_move_semantics():
    header("1. Validasi Semantik Move & Ownership Thread Rust")
    print(f"{CLR_YELLOW}Mencoba mentransfer kepemilikan string ke thread pekerja...{CLR_RESET}")

    payload = ScopedResource("raw_payload", "DATA_KRIPTOGRAFI_RAHASIA")
    transferred_val = None

    def worker_thread(resource_val: str):
        time.sleep(0.05)
        digest = hashlib.sha256(resource_val.encode()).hexdigest()[:16]
        print(f"  {CLR_GREEN}Thread Pekerja:{CLR_RESET} Menerima nilai! Hash: {CLR_MAGENTA}{digest}{CLR_RESET}")

    # Simulasi `thread::spawn(move || { ... })`
    val = payload.move()
    t = threading.Thread(target=worker_thread, args=(val,))
    t.start()
    t.join()

    print(f"\n{CLR_YELLOW}Verifikasi Borrow Checker Lokal Pasca-Move:{CLR_RESET}")
    try:
        # Percobaan akses ilegal terhadap objek yang sudah berpindah kepemilikan
        _ = payload.read()
    except MoveError as e:
        print(f"  {CLR_RED}[DITOLAK SECARA AMAN]{CLR_RESET} {e}")
        print(f"  {CLR_GREEN}✓ Terbukti: Akses memori ganda terhindar melalui simulasi Move.{CLR_RESET}")

def test_mpsc_channels():
    header("2. Message Passing: Multi-Producer Single-Consumer (mpsc)")
    tx, rx = channel()
    num_producers = 3
    messages_per_producer = 4
    threads = []

    print(f"{CLR_YELLOW}Memulai {num_producers} produser independen menggunakan Sender::clone()...{CLR_RESET}")

    def producer_task(p_id: int, p_tx: Sender):
        for i in range(messages_per_producer):
            msg = f"Worker-{p_id} Paket-{i+1}"
            p_tx.send((p_id, msg))
            time.sleep(0.02)
        p_tx.drop() # Drop instance transmitter lokal

    for pid in range(1, num_producers + 1):
        # Setiap produser mendapatkan tx yang di-clone secara aman
        worker_tx = tx.clone()
        th = threading.Thread(target=producer_task, args=(pid, worker_tx))
        threads.append(th)
        th.start()

    # Drop transmitter utama yang dimiliki orchestrator agar Receiver bisa menutup loop
    tx.drop()

    print(f"{CLR_CYAN}Receiver Utama: Mengambil stream pesan sinkron...{CLR_RESET}")
    total_received = 0
    while True:
        data = rx.recv()
        if data is None:
            break
        pid, text = data
        total_received += 1
        print(f"  {CLR_GREEN}<- Diterima di RX:{CLR_RESET} [{CLR_MAGENTA}PID {pid}{CLR_RESET}] {text}")

    for th in threads:
        th.join()

    print(f"{CLR_GREEN}✓ MPSC Selesai: {total_received} pesan diproses tanpa locking manual pada consumer!{CLR_RESET}")

def test_arc_mutex_concurrency():
    header("3. Shared-State Concurrency: Arc<Mutex<T>> Race-Free Counter")
    shared_counter = Arc(Mutex(0))
    iterations = 250
    num_workers = 8
    threads = []

    print(f"{CLR_YELLOW}Memulai {num_workers} thread untuk memodifikasi counter bersama.{CLR_RESET}")
    print(f"{CLR_YELLOW}Target mutasi: {num_workers} x {iterations} = {num_workers * iterations} increment atomik.{CLR_RESET}")

    def worker_inc(arc_ref: Arc[int], w_id: int):
        for _ in range(iterations):
            # Simulasi Rust: let mut data = counter.lock().unwrap();
            with arc_ref.lock() as guard:
                guard[0] += 1
                # Operasi dummy mensimulasikan pekerjaan nyata dalam critical section
                _ = 2 ** 10
            time.sleep(0.0001)
        arc_ref.drop()

    for w_id in range(num_workers):
        worker_arc = shared_counter.clone()
        th = threading.Thread(target=worker_inc, args=(worker_arc, w_id))
        threads.append(th)
        th.start()

    print(f"  {CLR_CYAN}Current Arc Strong Count saat pekerja aktif: {shared_counter.strong_count()}{CLR_RESET}")

    for th in threads:
        th.join()

    final_val = shared_counter.lock()._data_ref[0]
    expected = num_workers * iterations

    print(f"\n{CLR_BOLD}Hasil Eksekusi Sinkronisasi:{CLR_RESET}")
    print(f"  Nilai Akhir Counter : {CLR_GREEN}{final_val}{CLR_RESET}")
    print(f"  Nilai Ekspektasi    : {CLR_GREEN}{expected}{CLR_RESET}")

    if final_val == expected:
        print(f"  {CLR_BOLD}{CLR_GREEN}✓ Uji Lolos:{CLR_RESET} Zero Data-Race tercapai via abstraksi MutexGuard & Arc.")
    else:
        print(f"  {CLR_BOLD}{CLR_RED}✗ Gagal:{CLR_RESET} Terdeteksi data race! ({final_val} != {expected})")

def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}")
    print("*" * 75)
    print("   RUST FEARLESS CONCURRENCY SIMULATION ENGINE (LAB 05 - DEEP DIVE)")
    print("   Mengeksplorasi Move Semantics, MPSC Channels, dan Arc<Mutex<T>>")
    print("*" * 75 + f"{CLR_RESET}")

    start_time = time.time()
    test_move_semantics()
    test_mpsc_channels()
    test_arc_mutex_concurrency()
    elapsed = time.time() - start_time

    print(f"\n{CLR_BOLD}{CLR_GREEN}Seluruh modul pengujian konkurensi selesai dalam {elapsed:.3f}s tanpa kesalahan!{CLR_RESET}\n")

if __name__ == "__main__":
    main()