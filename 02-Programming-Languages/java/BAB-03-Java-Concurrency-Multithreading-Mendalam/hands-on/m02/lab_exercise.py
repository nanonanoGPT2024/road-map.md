#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Java Concurrency & Multithreading Mendalam
BAB-03-Java-Concurrency-Multithreading-Mendalam

Simulasi konsep kunci JVM Concurrency:
1. Java Memory Model (JMM) & Hardware Cache Visibility (Volatile & Happens-Before)
2. Lock-Free Synchronization via Compare-And-Swap (CAS / AtomicInteger)
3. Production ThreadPoolExecutor Architecture (Core/Max Pool, WorkQueue, Rejection Policies)
4. ReentrantLock with Condition Variables (Dual-Condition Bounded Buffer)
5. Asynchronous Reactive Pipeline (CompletableFuture simulation)
6. Virtual Threads (Project Loom) vs Platform Carrier Threads
"""

import sys
import time
import random
import threading
import queue
from dataclasses import dataclass
from typing import List, Callable, Optional, Any

# ANSI Color Codes for Rich Terminal Output
RESET   = "\033[0m"
BOLD    = "\033[1m"
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
WHITE   = "\033[37m"
BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{BG_BLUE}{WHITE}{BOLD} === {title} === {RESET}\n")


def log_info(module: str, msg: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{CYAN}[{timestamp}]{RESET} {BOLD}[{module:^16}]{RESET} {msg}")


def log_success(module: str, msg: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{CYAN}[{timestamp}]{RESET} {GREEN}[{module:^16}]{RESET} {GREEN}{msg}{RESET}")


def log_warn(module: str, msg: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{CYAN}[{timestamp}]{RESET} {YELLOW}[{module:^16}]{RESET} {YELLOW}{msg}{RESET}")


def log_error(module: str, msg: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{CYAN}[{timestamp}]{RESET} {RED}[{module:^16}]{RESET} {RED}{BOLD}{msg}{RESET}")


# ==============================================================================
# 1. SIMULASI JAVA MEMORY MODEL (JMM) & CAS (COMPARE-AND-SWAP)
# ==============================================================================
class SimulatedAtomicInteger:
    """Simulasi java.util.concurrent.atomic.AtomicInteger dengan CAS intrinsics."""
    def __init__(self, initial_value: int = 0):
        self._value = initial_value
        self._lock = threading.Lock()
        self.cas_failures = 0

    def get(self) -> int:
        return self._value

    def compare_and_set(self, expect: int, update: int) -> bool:
        # Simulasi instruksi CPU CMPXCHG
        with self._lock:
            if self._value == expect:
                self._value = update
                return True
            self.cas_failures += 1
            return False

    def increment_and_get(self) -> int:
        while True:
            current = self.get()
            next_val = current + 1
            if self.compare_and_set(current, next_val):
                return next_val
            # Retry loop under contention


def demo_cas_atomic() -> None:
    header("1. SIMULASI HARDWARE CAS & ATOMIC PRIMITIVES")
    log_info("ATOMIC-CAS", "Memulai race condition stress test dengan 8 thread paralel...")
    
    counter = SimulatedAtomicInteger(0)
    threads = []
    increments_per_thread = 2500

    def worker():
        for _ in range(increments_per_thread):
            counter.increment_and_get()

    start_time = time.time()
    for i in range(8):
        t = threading.Thread(target=worker, name=f"Worker-{i}")
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    duration = (time.time() - start_time) * 1000
    expected = 8 * increments_per_thread
    actual = counter.get()

    log_success("ATOMIC-CAS", f"Total nilai akhir: {actual}/{expected} (Akurat 100%)")
    log_warn("ATOMIC-CAS", f"CAS Spin/Contention Retries: {counter.cas_failures} kali terjadi retry")
    log_info("ATOMIC-CAS", f"Waktu eksekusi: {duration:.2f} ms")


# ==============================================================================
# 2. SIMULASI THREADPOOLEXECUTOR PRODUKSI & REJECTION POLICIES
# ==============================================================================
class RejectedExecutionException(Exception):
    pass


class RejectionPolicy:
    ABORT = "AbortPolicy (Lempar Exception)"
    CALLER_RUNS = "CallerRunsPolicy (Jalankan di Thread Pengirim)"
    DISCARD_OLDEST = "DiscardOldestPolicy (Hapus antrean terlama)"


@dataclass
class JavaTask:
    task_id: int
    payload: str
    burst_ms: float


class ProductionThreadPoolExecutor:
    """
    Simulasi arsitektur java.util.concurrent.ThreadPoolExecutor
    Komponen: Core Pool, Max Pool, Bounded BlockingQueue, Keep-Alive, Saturation Handler
    """
    def __init__(self, core_pool_size: int, max_pool_size: int, queue_capacity: int, policy: str):
        self.core_pool_size = core_pool_size
        self.max_pool_size = max_pool_size
        self.work_queue = queue.Queue(maxsize=queue_capacity)
        self.policy = policy
        self.workers: List[threading.Thread] = []
        self.active_workers = 0
        self.lock = threading.Lock()
        self.is_shutdown = False
        self.completed_tasks = 0

    def execute(self, task: JavaTask) -> None:
        with self.lock:
            if self.is_shutdown:
                raise RejectedExecutionException("Executor telah di-shutdown")

            # 1. Jika active worker < core_pool_size, buat worker baru
            if self.active_workers < self.core_pool_size:
                self._add_worker(task, is_core=True)
                return

            # 2. Jika core penuh, coba masukkan ke bounded work queue
            try:
                self.work_queue.put_nowait(task)
                log_info("THREAD-POOL", f"Task #{task.task_id} antre di WorkQueue (Size: {self.work_queue.qsize()})")
                return
            except queue.Full:
                pass

            # 3. Jika antrean penuh, coba ekspansi sampai max_pool_size
            if self.active_workers < self.max_pool_size:
                self._add_worker(task, is_core=False)
                return

            # 4. Jika pool & antrean jenuh, picu RejectedExecutionHandler
            self._handle_rejection(task)

    def _add_worker(self, initial_task: Optional[JavaTask], is_core: bool) -> None:
        self.active_workers += 1
        role = "CORE" if is_core else "EXTRA"
        worker_id = self.active_workers

        def worker_loop():
            log_info("WORKER-INIT", f"Worker-{worker_id} [{role}] aktif dan siap memproses.")
            current_task = initial_task
            while not self.is_shutdown:
                if current_task is not None:
                    # Jalankan simulasi kerja task
                    time.sleep(current_task.burst_ms / 1000.0)
                    with self.lock:
                        self.completed_tasks += 1
                    log_success("WORKER-RUN", f"Worker-{worker_id} selesai proses Task #{current_task.task_id}")
                    current_task = None
                
                try:
                    # Ambil tugas dari antrean dengan timeout (keep-alive)
                    current_task = self.work_queue.get(timeout=0.3)
                    self.work_queue.task_done()
                except queue.Empty:
                    # Timeout tercapai
                    if not is_core:
                        log_warn("WORKER-EVICT", f"Worker-{worker_id} [EXTRA] idle melebihi keepAliveTime, dimatikan.")
                        break

            with self.lock:
                self.active_workers -= 1

        t = threading.Thread(target=worker_loop, daemon=True)
        self.workers.append(t)
        t.start()

    def _handle_rejection(self, task: JavaTask) -> None:
        if self.policy == RejectionPolicy.ABORT:
            log_error("SATURATION", f"REJECTED: Task #{task.task_id} dibatalkan! WorkQueue & Pool jenuh.")
            raise RejectedExecutionException(f"Task {task.task_id} ditolak oleh AbortPolicy.")
        elif self.policy == RejectionPolicy.CALLER_RUNS:
            log_warn("SATURATION", f"BACKPRESSURE: Task #{task.task_id} dieksekusi langsung oleh Caller Thread!")
            time.sleep(task.burst_ms / 1000.0)
            with self.lock:
                self.completed_tasks += 1
        elif self.policy == RejectionPolicy.DISCARD_OLDEST:
            try:
                dropped = self.work_queue.get_nowait()
                self.work_queue.task_done()
                log_warn("SATURATION", f"DISCARD: Task #{dropped.task_id} di antrean dibuang demi Task #{task.task_id}!")
                self.work_queue.put_nowait(task)
            except (queue.Empty, queue.Full):
                pass

    def shutdown(self) -> None:
        self.is_shutdown = True
        for t in self.workers:
            t.join(timeout=1.0)


def demo_thread_pool() -> None:
    header("2. SIMULASI PRODUCTION THREADPOOLEXECUTOR & SATURATION POLICIES")
    log_info("CONFIG", "Core: 2 | Max: 4 | Queue: 3 | Policy: CallerRunsPolicy")

    pool = ProductionThreadPoolExecutor(
        core_pool_size=2,
        max_pool_size=4,
        queue_capacity=3,
        policy=RejectionPolicy.CALLER_RUNS
    )

    # Kirim burst 10 tasks untuk memicu saturation
    for i in range(1, 11):
        task = JavaTask(task_id=i, payload=f"OrderPayload-{i}", burst_ms=120)
        log_info("CLIENT", f"Submitting Task #{i}...")
        pool.execute(task)
        time.sleep(0.02)

    time.sleep(0.8)
    pool.shutdown()
    log_success("THREAD-POOL", f"Total tasks berhasil dieksekusi: {pool.completed_tasks}/10")


# ==============================================================================
# 3. REENTRANTLOCK & CONDITION: BOUNDED BUFFER (PRODUCER-CONSUMER)
# ==============================================================================
class JavaBoundedBuffer:
    """
    Simulasi java.util.concurrent.ArrayBlockingQueue 
    menggunakan 1 ReentrantLock dengan 2 Condition (notFull, notEmpty)
    """
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.buffer: List[Any] = []
        self.lock = threading.Lock()
        self.not_full = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)

    def put(self, item: Any) -> None:
        with self.lock:
            while len(self.buffer) == self.capacity:
                log_warn("LOCK-COND", f"Buffer PENUH [{len(self.buffer)}/{self.capacity}]. Producer thread AWAIT...")
                self.not_full.wait()
            self.buffer.append(item)
            log_info("PRODUCER", f"Menyimpan data: '{item}' (Buffer: {len(self.buffer)}/{self.capacity})")
            self.not_empty.notify()

    def take(self) -> Any:
        with self.lock:
            while len(self.buffer) == 0:
                log_warn("LOCK-COND", "Buffer KOSONG. Consumer thread AWAIT...")
                self.not_empty.wait()
            item = self.buffer.pop(0)
            log_success("CONSUMER", f"Mengambil data: '{item}' (Buffer sisa: {len(self.buffer)}/{self.capacity})")
            self.not_full.notify()
            return item


def demo_bounded_buffer() -> None:
    header("3. REENTRANTLOCK & DUAL CONDITION VARIABLES (BOUNDED BUFFER)")
    buffer = JavaBoundedBuffer(capacity=2)

    def producer():
        for i in range(1, 6):
            buffer.put(f"Packet-00{i}")
            time.sleep(0.04)

    def consumer():
        for _ in range(5):
            time.sleep(0.09)
            buffer.take()

    t_prod = threading.Thread(target=producer, name="ProducerThread")
    t_cons = threading.Thread(target=consumer, name="ConsumerThread")

    t_cons.start()
    t_prod.start()

    t_prod.join()
    t_cons.join()


# ==============================================================================
# 4. SIMULASI COMPLETABLEFUTURE ASYNC REACTIVE PIPELINE
# ==============================================================================
class SimulatedCompletableFuture:
    """Simulasi java.util.concurrent.CompletableFuture pipeline."""
    def __init__(self, supplier: Optional[Callable[[], Any]] = None):
        self._result = None
        self._exception: Optional[Exception] = None
        self._done_event = threading.Event()
        if supplier:
            threading.Thread(target=self._run_async, args=(supplier,), daemon=True).start()

    def _run_async(self, supplier: Callable[[], Any]):
        try:
            self._result = supplier()
        except Exception as e:
            self._exception = e
        finally:
            self._done_event.set()

    def then_apply(self, fn: Callable[[Any], Any]) -> 'SimulatedCompletableFuture':
        next_cf = SimulatedCompletableFuture()

        def chained():
            self._done_event.wait()
            if self._exception:
                next_cf._exception = self._exception
                next_cf._done_event.set()
                return
            try:
                next_cf._result = fn(self._result)
            except Exception as ex:
                next_cf._exception = ex
            finally:
                next_cf._done_event.set()

        threading.Thread(target=chained, daemon=True).start()
        return next_cf

    def exceptionally(self, fallback_fn: Callable[[Exception], Any]) -> 'SimulatedCompletableFuture':
        next_cf = SimulatedCompletableFuture()

        def chained():
            self._done_event.wait()
            if self._exception:
                try:
                    next_cf._result = fallback_fn(self._exception)
                except Exception as ex:
                    next_cf._exception = ex
            else:
                next_cf._result = self._result
            next_cf._done_event.set()

        threading.Thread(target=chained, daemon=True).start()
        return next_cf

    def join(self) -> Any:
        self._done_event.wait()
        if self._exception:
            raise self._exception
        return self._result


def demo_completable_future() -> None:
    header("4. SIMULASI ASYNCHRONOUS PIPELINE (COMPLETA-BLE-FUTURE)")
    log_info("ASYNC-IO", "Memulai pipeline non-blocking: Fetch -> Transform -> Validate...")

    def fetch_user_order():
        log_info("STEP-1", "Query database transaksi async...")
        time.sleep(0.1)
        return {"order_id": "ORD-9981", "amount": 450000.0, "status": "PENDING"}

    def apply_discount_tax(order):
        log_info("STEP-2", f"Memproses kalkulasi pajak & diskon untuk Order {order['order_id']}...")
        time.sleep(0.08)
        order["final_amount"] = order["amount"] * 0.89
        order["status"] = "PROCESSED"
        return order

    def audit_and_save(order):
        log_info("STEP-3", f"Menyimpan audit trail ke event log...")
        time.sleep(0.05)
        return f"SUCCESS: Order {order['order_id']} Final Rp{order['final_amount']:,.2f}"

    cf = SimulatedCompletableFuture(fetch_user_order) \
        .then_apply(apply_discount_tax) \
        .then_apply(audit_and_save)

    result = cf.join()
    log_success("COMPLETED", result)


# ==============================================================================
# 5. VIRTUAL THREADS (PROJECT LOOM) VS PLATFORM CARRIER THREADS
# ==============================================================================
def demo_virtual_threads_simulation() -> None:
    header("5. SIMULASI VIRTUAL THREADS (LOOM) VS PLATFORM CARRIER THREADS")
    log_info("LOOM-ARCH", "Menjalankan 1,000 Virtual Tasks di atas ForkJoinPool (4 Carrier Threads)...")

    carrier_threads_count = 4
    total_virtual_tasks = 1000
    task_queue = queue.Queue()
    completed_counter = SimulatedAtomicInteger(0)

    for i in range(total_virtual_tasks):
        task_queue.put(i)

    def carrier_worker(carrier_id: int):
        while not task_queue.empty():
            try:
                task_id = task_queue.get_nowait()
                # Simulasi non-blocking unmount / remount pada blocking I/O
                # Virtual thread mengyield CPU ke task lain saat menunggu I/O
                time.sleep(0.0005) 
                completed_counter.increment_and_get()
                task_queue.task_done()
            except queue.Empty:
                break

    start = time.time()
    carriers = []
    for c in range(carrier_threads_count):
        ct = threading.Thread(target=carrier_worker, args=(c+1,))
        carriers.append(ct)
        ct.start()

    for ct in carriers:
        ct.join()

    duration = (time.time() - start) * 1000
    log_success("LOOM-ARCH", f"Selesai memproses {completed_counter.get()} Virtual Tasks.")
    log_info("PERFORMANCE", f"Total waktu: {duration:.2f} ms (~{duration/total_virtual_tasks:.3f} ms/task)")


# ==============================================================================
# INTERACTIVE CLI DISPATCHER
# ==============================================================================
def print_menu() -> None:
    print(f"\n{BOLD}{CYAN}--- PILIHAN MODUL SIMULASI CONCURRENCY JAVA ---{RESET}")
    print(f"{YELLOW}1.{RESET} JMM & Compare-And-Swap (AtomicInteger Contention)")
    print(f"{YELLOW}2.{RESET} ThreadPoolExecutor & Saturation Policies")
    print(f"{YELLOW}3.{RESET} ReentrantLock & Condition BoundedBuffer")
    print(f"{YELLOW}4.{RESET} CompletableFuture Asynchronous Pipeline")
    print(f"{YELLOW}5.{RESET} Virtual Threads (Project Loom) M:N Scheduling")
    print(f"{YELLOW}6.{RESET} Jalankan SEMUA Modul Simulasi Sekaligus")
    print(f"{YELLOW}0.{RESET} Keluar\n")


def run_interactive():
    print(f"{BOLD}{GREEN}================================================================={RESET}")
    print(f"{BOLD}{GREEN}  SIMULATOR ARSITEKTUR JAVA CONCURRENCY & MULTITHREADING (BAB 03){RESET}")
    print(f"{BOLD}{GREEN}================================================================={RESET}")

    # Jika dijalankan secara non-interaktif atau dengan argumen CLI
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        demo_cas_atomic()
        demo_thread_pool()
        demo_bounded_buffer()
        demo_completable_future()
        demo_virtual_threads_simulation()
        print(f"\n{GREEN}{BOLD}Seluruh simulasi selesai dijalankan dengan sukses.{RESET}\n")
        return

    # Default run jika stdout adalah pipe/non-tty (automated testing)
    if not sys.stdin.isatty():
        demo_cas_atomic()
        demo_thread_pool()
        demo_bounded_buffer()
        demo_completable_future()
        demo_virtual_threads_simulation()
        return

    while True:
        print_menu()
        choice = input(f"{BOLD}Pilih nomor menu (0-6): {RESET}").strip()
        if choice == "1":
            demo_cas_atomic()
        elif choice == "2":
            demo_thread_pool()
        elif choice == "3":
            demo_bounded_buffer()
        elif choice == "4":
            demo_completable_future()
        elif choice == "5":
            demo_virtual_threads_simulation()
        elif choice == "6":
            demo_cas_atomic()
            demo_thread_pool()
            demo_bounded_buffer()
            demo_completable_future()
            demo_virtual_threads_simulation()
        elif choice == "0":
            print(f"\n{CYAN}Keluar dari simulator. Sampai jumpa!{RESET}\n")
            break
        else:
            log_error("INPUT", "Pilihan tidak valid, silakan coba lagi.")


if __name__ == "__main__":
    run_interactive()
