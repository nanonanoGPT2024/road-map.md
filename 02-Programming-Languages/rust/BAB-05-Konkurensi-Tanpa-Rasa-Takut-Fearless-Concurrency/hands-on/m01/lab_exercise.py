#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fearless Concurrency (Rust BAB-05) dalam Python 3
-----------------------------------------------------------------------
Modul ini mendemonstrasikan secara interaktif dan visual konsep-konsep inti:
  1. Thread Spawning & JoinHandle (`std::thread::spawn`)
  2. Message Passing dengan MPSC Channel (`std::sync::mpsc::channel`)
  3. Shared-State Concurrency dengan `Arc<Mutex<T>>`
  4. Invarian Sistem Tipe: `Send` dan `Sync` Marker Traits Validation
"""

import sys
import time
import threading
import queue
from typing import Any, Generic, TypeVar, Optional, List, Dict

# ANSI Terminal Color Codes
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

T = TypeVar("T")

# ----------------------------------------------------------------------
# 1. Simulasi Marker Traits: Send & Sync
# ----------------------------------------------------------------------
class RustTypeMeta:
    """Mewakili metadata tipe data Rust serta pemenuhan trait Send/Sync."""
    def __init__(self, name: str, is_send: bool, is_sync: bool, explanation: str):
        self.name = name
        self.is_send = is_send
        self.is_sync = is_sync
        self.explanation = explanation


TYPE_CATALOG: Dict[str, RustTypeMeta] = {
    "i32": RustTypeMeta("i32", True, True, "Primitif skalar; aman dipindah (Send) dan dibaca konkuren (Sync)."),
    "String": RustTypeMeta("String", True, True, "Memiliki alokasi heap unik; aman dipindah dan dibaca antar-thread."),
    "Arc<Mutex<T>>": RustTypeMeta("Arc<Mutex<T>>", True, True, "Atomic Reference Counting + Mutex; Send + Sync penuh."),
    "Rc<T>": RustTypeMeta("Rc<T>", False, False, "Non-atomic reference count; DITOLAK saat dipindah antar-thread!"),
    "RefCell<T>": RustTypeMeta("RefCell<T>", True, False, "Peminjaman runtime non-thread-safe; Send jika T:Send, BUKAN Sync!"),
}


def verify_send_sync_boundary(type_name: str, require_send: bool = True, require_sync: bool = False) -> bool:
    """Memvalidasi aturan kompilasi Rust untuk batas thread."""
    meta = TYPE_CATALOG.get(type_name)
    if not meta:
        print(f"{RED}[Rustc Error]{RESET} Unknown type `{type_name}`")
        return False

    print(f"\n{BOLD}{CYAN}=== Rustc Static Analysis: `{meta.name}` ==={RESET}")
    print(f"{DIM}Deskripsi: {meta.explanation}{RESET}")
    
    passed = True
    if require_send and not meta.is_send:
        print(f"  {RED}✖ COMPILE ERROR: `{meta.name}` does NOT implement `std::marker::Send`!{RESET}")
        print(f"    {YELLOW}Solusi Rust: Ganti `{meta.name}` dengan versi atomic atau bungkus dalam Mutex.{RESET}")
        passed = False
    elif require_send:
        print(f"  {GREEN}✔ Trait Check Passed: `{meta.name}`: Send{RESET}")

    if require_sync and not meta.is_sync:
        print(f"  {RED}✖ COMPILE ERROR: `{meta.name}` does NOT implement `std::marker::Sync`!{RESET}")
        passed = False
    elif require_sync:
        print(f"  {GREEN}✔ Trait Check Passed: `{meta.name}`: Sync{RESET}")

    return passed


# ----------------------------------------------------------------------
# 2. Simulasi MPSC Channel (`std::sync::mpsc::channel`)
# ----------------------------------------------------------------------
class Sender(Generic[T]):
    def __init__(self, q: queue.Queue, ref_counter: List[int], channel_id: int):
        self._queue = q
        self._ref = ref_counter
        self._channel_id = channel_id
        self._ref[0] += 1

    def send(self, val: T) -> None:
        self._queue.put(val)

    def clone(self) -> "Sender[T]":
        """Simulasi `tx.clone()` di Rust untuk multiple producers."""
        return Sender(self._queue, self._ref, self._channel_id)

    def drop(self) -> None:
        """Simulasi RAII drop pada Rust sender saat keluar dari scope."""
        self._ref[0] -= 1
        if self._ref[0] == 0:
            self._queue.put(StopIteration)


class Receiver(Generic[T]):
    def __init__(self, q: queue.Queue):
        self._queue = q

    def recv(self) -> Optional[T]:
        val = self._queue.get()
        if val is StopIteration:
            return None
        return val


def create_mpsc_channel() -> (Sender[T], Receiver[T]):
    q: queue.Queue = queue.Queue()
    ref = [0]
    tx = Sender(q, ref, channel_id=1)
    rx = Receiver(q)
    return tx, rx


# ----------------------------------------------------------------------
# 3. Simulasi Shared State (`Arc<Mutex<T>>`)
# ----------------------------------------------------------------------
class MutexGuard(Generic[T]):
    def __init__(self, mutex: "RustMutex[T]"):
        self._mutex = mutex

    @property
    def value(self) -> T:
        return self._mutex._data

    @value.setter
    def value(self, new_val: T) -> None:
        self._mutex._data = new_val

    def __enter__(self) -> "MutexGuard[T]":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._mutex._raw_lock.release()


class RustMutex(Generic[T]):
    """Simulasi `std::sync::Mutex<T>` dengan lock guard RAII."""
    def __init__(self, initial_value: T):
        self._data = initial_value
        self._raw_lock = threading.Lock()

    def lock(self) -> MutexGuard[T]:
        self._raw_lock.acquire()
        return MutexGuard(self)


class RustArc(Generic[T]):
    """Simulasi Atomic Reference Counting (`std::sync::Arc<T>`)."""
    def __init__(self, inner: T):
        self._inner = inner

    def clone(self) -> "RustArc[T]":
        return RustArc(self._inner)

    def get(self) -> T:
        return self._inner


# ----------------------------------------------------------------------
# 4. Modul Eksperimen / Skenario Praktis
# ----------------------------------------------------------------------
def demo_thread_spawn_and_join():
    print(f"\n{BOLD}{MAGENTA}--- [LAB 1] std::thread::spawn & JoinHandle ---{RESET}")
    print(f"{CYAN}Membuat 3 thread pekerja independen dan menunggu dengan `.join()`.{RESET}")
    
    results: List[str] = []
    lock = threading.Lock()

    def worker(worker_id: int):
        print(f"  {GREEN}[Thread #{worker_id}]{RESET} Dimulai. Melakukan komputasi...")
        time.sleep(0.08 * worker_id)
        with lock:
            results.append(f"Output-Worker-{worker_id}")
        print(f"  {GREEN}[Thread #{worker_id}]{RESET} Selesai & nilai siap diambil.")

    handles: List[threading.Thread] = []
    for i in range(1, 4):
        t = threading.Thread(target=worker, args=(i,))
        handles.append(t)
        t.start()

    print(f"{YELLOW}[Main Thread]{RESET} Melakukan `.join()` untuk memastikan tiada data race...")
    for h in handles:
        h.join()

    print(f"{BOLD}{GREEN}Semua JoinHandle selesai! Hasil: {results}{RESET}")


def demo_mpsc_channels():
    print(f"\n{BOLD}{MAGENTA}--- [LAB 2] Message Passing (mpsc::channel) ---{RESET}")
    print(f"{CYAN}Multiple Producers, Single Consumer (MPSC). Mengirim pesan ke single receiver.{RESET}")

    tx, rx = create_mpsc_channel()

    def producer(sender: Sender[str], producer_id: int, items: List[str]):
        for item in items:
            msg = f"[P#{producer_id}] {item}"
            sender.send(msg)
            print(f"  {CYAN}Producer {producer_id} mengirim:{RESET} {item}")
            time.sleep(0.04)
        sender.drop()

    # Kloning sender untuk multi-producer
    tx1 = tx.clone()
    tx2 = tx.clone()
    tx.drop()  # Drop transmitter utama asli

    t1 = threading.Thread(target=producer, args=(tx1, 1, ["Data Alpha", "Data Beta"]))
    t2 = threading.Thread(target=producer, args=(tx2, 2, ["Event Gamma", "Event Delta"]))

    t1.start()
    t2.start()

    print(f"{YELLOW}[Receiver Thread]{RESET} Membaca pesan dari saluran mpsc:")
    received_count = 0
    while True:
        msg = rx.recv()
        if msg is None:
            print(f"  {DIM}[Receiver] Saluran tertutup (semua Sender ter-drop). Selesai.{RESET}")
            break
        print(f"  {GREEN}➔ Diterima:{RESET} {msg}")
        received_count += 1

    t1.join()
    t2.join()
    print(f"{BOLD}{GREEN}MPSC Selesai! Total pesan diproses: {received_count}{RESET}")


def demo_arc_mutex_counter():
    print(f"\n{BOLD}{MAGENTA}--- [LAB 3] Shared-State Concurrency (Arc<Mutex<i32>>) ---{RESET}")
    print(f"{CYAN}10 thread secara konkuren menaikkan nilai counter bersama secara aman.{RESET}")

    counter_mutex = RustMutex(0)
    shared_counter = RustArc(counter_mutex)
    threads: List[threading.Thread] = []

    def incrementer(arc_ref: RustArc[RustMutex[int]], worker_id: int):
        mutex = arc_ref.get()
        # Scope block lock guard (RAII simulation)
        with mutex.lock() as guard:
            curr = guard.value
            time.sleep(0.01)  # Simulasi proses komputasi dalam critical section
            guard.value = curr + 1
            print(f"  {WHITE}Worker {worker_id:02d}{RESET} mengunci mutex: {curr} -> {guard.value}")

    for i in range(10):
        # Simulasi `Arc::clone(&shared_counter)`
        thread_arc = shared_counter.clone()
        t = threading.Thread(target=incrementer, args=(thread_arc, i + 1))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    final_val = shared_counter.get().lock().value
    print(f"{BOLD}{GREEN}Nilai akhir Counter: {final_val} (Ekspektasi: 10) - Tiada Data Race!{RESET}")


def demo_send_sync_type_safety():
    print(f"\n{BOLD}{MAGENTA}--- [LAB 4] Verifikasi Kompiler Rust: Send & Sync Traits ---{RESET}")
    print(f"{CYAN}Mengapa Rust menolak tipe non-thread-safe sebelum program dijalankan?{RESET}")

    # Uji 1: Mengirim Rc<T> antar-thread
    verify_send_sync_boundary("Rc<T>", require_send=True)

    # Uji 2: Mengirim Arc<Mutex<T>> antar-thread
    verify_send_sync_boundary("Arc<Mutex<T>>", require_send=True, require_sync=True)

    # Uji 3: Tipe primitif
    verify_send_sync_boundary("i32", require_send=True, require_sync=True)


def run_interactive_menu():
    print(f"{BOLD}{CYAN}================================================================{RESET}")
    print(f"{BOLD}{WHITE}  SIMULASI KONKURENSI TANPA RASA TAKUT (RUST FEARLESS CONCURRENCY){RESET}")
    print(f"{BOLD}{CYAN}================================================================{RESET}")
    print(f"{DIM}Hands-on Python Simulator untuk Konsep BAB-05 Concurrency di Rust.{RESET}\n")

    options = [
        ("1", "Simulasi `std::thread::spawn` dan `JoinHandle`", demo_thread_spawn_and_join),
        ("2", "Simulasi Message Passing MPSC (`std::sync::mpsc::channel`)", demo_mpsc_channels),
        ("3", "Simulasi Shared State (`Arc<Mutex<T>>`) Anti Data-Race", demo_arc_mutex_counter),
        ("4", "Simulasi Validasi Invarian Sistem Tipe (`Send` & `Sync`)", demo_send_sync_type_safety),
        ("5", "Jalankan Seluruh Skenario Secara Sekuensial", None),
        ("0", "Keluar dari Program", None),
    ]

    # Mode non-interaktif jika stdin di-redirect atau ada argumen CLI
    if not sys.stdin.isatty() or "--all" in sys.argv:
        print(f"{YELLOW}[Auto-Run Mode]{RESET} Menjalankan semua skenario lab secara lengkap...\n")
        demo_thread_spawn_and_join()
        demo_mpsc_channels()
        demo_arc_mutex_counter()
        demo_send_sync_type_safety()
        print(f"\n{BOLD}{GREEN}✔ Seluruh simulasi selesai dengan sukses.{RESET}")
        return

    while True:
        print(f"\n{BOLD}{WHITE}PILIH MENU SIMULASI:{RESET}")
        for key, desc, _ in options:
            print(f"  {BOLD}{CYAN}[{key}]{RESET} {desc}")

        try:
            choice = input(f"\n{BOLD}Ketik pilihan (0-5): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Program dihentikan.{RESET}")
            break

        if choice == "0":
            print(f"{GREEN}Terima kasih telah mempelajari Fearless Concurrency!{RESET}")
            break
        elif choice == "1":
            demo_thread_spawn_and_join()
        elif choice == "2":
            demo_mpsc_channels()
        elif choice == "3":
            demo_arc_mutex_counter()
        elif choice == "4":
            demo_send_sync_type_safety()
        elif choice == "5":
            demo_thread_spawn_and_join()
            demo_mpsc_channels()
            demo_arc_mutex_counter()
            demo_send_sync_type_safety()
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")


if __name__ == "__main__":
    run_interactive_menu()
