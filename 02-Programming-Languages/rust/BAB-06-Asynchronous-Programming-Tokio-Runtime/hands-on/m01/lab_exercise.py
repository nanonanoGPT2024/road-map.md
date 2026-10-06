#!/usr/bin/env python3
"""
lab_exercise.py - Hands-on Lab: Simulasi Konsep Fondasi Rust Async & Tokio Runtime

Modul ini mendemonstrasikan cara kerja internal Rust Asynchronous Programming:
1. Future Trait State Machine: Polling (`Poll::Ready` vs `Poll::Pending`)
2. Waker Mechanism: Bangunkan task saat I/O / timer siap (`cx.waker().wake()`)
3. Tokio Work-Stealing Executor: Multi-worker scheduler dengan task stealing
4. Async Concurrency Primitives: Simulasi `join!` dan `select!` (cancellation on drop)
"""

import sys
import time
import random
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional
from collections import deque


# ==============================================================================
# ANSI Terminal Color Palette
# ==============================================================================
class Color:
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


def header(title: str) -> None:
    line = "=" * 65
    print(f"\n{Color.CYAN}{Color.BOLD}{line}")
    print(f" {title.center(63)} ")
    print(f"{line}{Color.RESET}\n")


def log_step(component: str, message: str, color: str = Color.WHITE) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{Color.DIM}[{timestamp}]{Color.RESET} {Color.BOLD}[{component:14}]{Color.RESET} {color}{message}{Color.RESET}")


# ==============================================================================
# 1. Rust Future & Poll State Machine Abstraction
# ==============================================================================
class PollState(Enum):
    PENDING = auto()
    READY = auto()


class PollResult:
    def __init__(self, state: PollState, value: Any = None):
        self.state = state
        self.value = value

    @staticmethod
    def pending() -> "PollResult":
        return PollResult(PollState.PENDING)

    @staticmethod
    def ready(val: Any) -> "PollResult":
        return PollResult(PollState.READY, val)

    def is_ready(self) -> bool:
        return self.state == PollState.READY


class Waker:
    """
    Simulasi std::task::Waker pada Rust.
    Menghubungkan event source (Reactor) kembali ke Task queue di Executor.
    """
    def __init__(self, task_id: int, wake_callback: Callable[[int], None]):
        self.task_id = task_id
        self._wake_callback = wake_callback

    def wake(self) -> None:
        log_step("WAKER", f"wake() dipanggil untuk Task #{self.task_id} -> Re-enqueue ke Executor!", Color.MAGENTA)
        self._wake_callback(self.task_id)


class SimulatedRustFuture:
    """
    Kontrak trait Future di Rust:
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
    """
    def __init__(self, name: str, required_steps: int = 3, result_val: Any = "OK"):
        self.name = name
        self.current_step = 0
        self.required_steps = required_steps
        self.result_val = result_val
        self.cancelled = False

    def poll(self, waker: Waker) -> PollResult:
        if self.cancelled:
            log_step("FUTURE", f"Future '{self.name}' telah di-drop / cancel!", Color.RED)
            return PollResult.pending()

        self.current_step += 1
        if self.current_step >= self.required_steps:
            log_step("POLL::READY", f"Future '{self.name}' SELESAI (Step {self.current_step}/{self.required_steps}) -> {self.result_val}", Color.GREEN)
            return PollResult.ready(self.result_val)

        log_step("POLL::PENDING", f"Future '{self.name}' belum siap (Step {self.current_step}/{self.required_steps}) -> Registrasi Waker", Color.YELLOW)
        # Simulasi Reactor async background yang akan memanggil wake()
        waker.wake()
        return PollResult.pending()


# ==============================================================================
# 2. Tokio Runtime: Work-Stealing Multi-Worker Executor
# ==============================================================================
class Task:
    def __init__(self, task_id: int, future: SimulatedRustFuture):
        self.task_id = task_id
        self.future = future


class TokioWorker:
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.local_queue: deque[Task] = deque()
        self.processed_count = 0

    def push(self, task: Task) -> None:
        self.local_queue.append(task)

    def pop(self) -> Optional[Task]:
        return self.local_queue.popleft() if self.local_queue else None

    def steal(self) -> Optional[Task]:
        """Tokio work-stealing algorithm: mencuri task dari worker lain yang sibuk"""
        if len(self.local_queue) > 1:
            stolen = self.local_queue.pop()
            return stolen
        return None


class TokioRuntimeSimulator:
    def __init__(self, num_workers: int = 2):
        self.num_workers = num_workers
        self.workers = [TokioWorker(i) for i in range(num_workers)]
        self.tasks: Dict[int, Task] = {}
        self.next_task_id = 1
        self.ready_queue: deque[int] = deque()

    def spawn(self, future: SimulatedRustFuture) -> int:
        task_id = self.next_task_id
        self.next_task_id += 1
        task = Task(task_id, future)
        self.tasks[task_id] = task

        # Tokio default: assign ke round-robin worker local queue
        target_worker = self.workers[task_id % self.num_workers]
        target_worker.push(task)
        log_step("TOKIO::SPAWN", f"Task #{task_id} ('{future.name}') di-spawn ke Worker #{target_worker.worker_id}", Color.CYAN)
        return task_id

    def wake_task(self, task_id: int) -> None:
        if task_id in self.tasks and task_id not in self.ready_queue:
            self.ready_queue.append(task_id)

    def run(self, max_ticks: int = 15) -> None:
        log_step("RUNTIME", f"Memulai Tokio Event Loop ({self.num_workers} Workers)...", Color.BOLD)
        tick = 0

        while tick < max_ticks and (any(w.local_queue for w in self.workers) or self.ready_queue or self.tasks):
            tick += 1
            all_empty = True

            # 1. Dispatch re-woken tasks
            while self.ready_queue:
                t_id = self.ready_queue.popleft()
                if t_id in self.tasks:
                    worker = self.workers[t_id % self.num_workers]
                    worker.push(self.tasks[t_id])

            # 2. Iterate each worker thread
            for worker in self.workers:
                task = worker.pop()

                # Work-stealing logic jika local queue worker kosong
                if not task:
                    for victim in self.workers:
                        if victim.worker_id != worker.worker_id:
                            stolen = victim.steal()
                            if stolen:
                                log_step("WORK-STEAL", f"Worker #{worker.worker_id} mencuri Task #{stolen.task_id} dari Worker #{victim.worker_id}!", Color.MAGENTA)
                                task = stolen
                                break

                if task:
                    all_empty = False
                    waker = Waker(task.task_id, self.wake_task)
                    log_step(f"WORKER #{worker.worker_id}", f"Polling Task #{task.task_id} ('{task.future.name}')", Color.BLUE)
                    res = task.future.poll(waker)
                    worker.processed_count += 1

                    if res.is_ready():
                        log_step("TOKIO::DROP", f"Task #{task.task_id} selesai -> deallocating frame", Color.GREEN)
                        if task.task_id in self.tasks:
                            del self.tasks[task.task_id]

            if all_empty and not self.tasks:
                break
            time.sleep(0.04)

        log_step("RUNTIME", f"Semua tasks selesai dalam {tick} ticks runtime.", Color.GREEN)


# ==============================================================================
# 3. Async Concurrency Primitives: join! vs select!
# ==============================================================================
def demo_join_macro() -> None:
    header("Simulasi tokio::join!(fut1, fut2, fut3)")
    print(f"{Color.WHITE}tokio::join! menunggu SEMUA future selesai secara konkuren.")
    print(f"Polling dilakukan bergantian dalam thread/worker yang sama tanpa blocking OS thread.{Color.RESET}\n")

    f1 = SimulatedRustFuture("fetch_user_db()", required_steps=2, result_val={"user": "Alice"})
    f2 = SimulatedRustFuture("query_cache_redis()", required_steps=3, result_val={"hit": True})
    f3 = SimulatedRustFuture("read_config_file()", required_steps=1, result_val={"port": 8080})

    futures = [f1, f2, f3]
    results: Dict[str, Any] = {}
    step = 0

    dummy_waker = Waker(0, lambda _: None)

    while len(results) < len(futures):
        step += 1
        print(f"\n{Color.BOLD}--- Polling Cycle #{step} ---{Color.RESET}")
        for fut in futures:
            if fut.name not in results:
                res = fut.poll(dummy_waker)
                if res.is_ready():
                    results[fut.name] = res.value

    print(f"\n{Color.GREEN}{Color.BOLD}[JOIN RESULT]: Semua Future Selesai!{Color.RESET}")
    for name, val in results.items():
        print(f"  * {Color.CYAN}{name}{Color.RESET} -> {Color.YELLOW}{val}{Color.RESET}")


def demo_select_macro() -> None:
    header("Simulasi tokio::select! dengan Cancellation on Drop")
    print(f"{Color.WHITE}tokio::select! membalap (race) beberapa future.")
    print(f"Future yang PERTAMA KALI menghasilkan Poll::Ready akan menang,")
    print(f"dan cabang branch lain AKAN DI-DROP (cancellation).{Color.RESET}\n")

    f_api = SimulatedRustFuture("fast_http_response()", required_steps=2, result_val="HTTP 200 OK")
    f_timeout = SimulatedRustFuture("tokio::time::sleep(5s)", required_steps=4, result_val="TIMEOUT ERROR")

    dummy_waker = Waker(99, lambda _: None)
    winner: Optional[str] = None
    res_val: Any = None

    for cycle in range(1, 6):
        print(f"\n{Color.BOLD}--- Race Cycle #{cycle} ---{Color.RESET}")
        # Poll Branch 1
        res1 = f_api.poll(dummy_waker)
        if res1.is_ready():
            winner = f_api.name
            res_val = res1.value
            f_timeout.cancelled = True
            log_step("SELECT!", f"Branch '{f_api.name}' MENANG!", Color.GREEN)
            log_step("DROP", f"Branch '{f_timeout.name}' di-drop seketika!", Color.RED)
            break

        # Poll Branch 2
        res2 = f_timeout.poll(dummy_waker)
        if res2.is_ready():
            winner = f_timeout.name
            res_val = res2.value
            f_api.cancelled = True
            log_step("SELECT!", f"Branch '{f_timeout.name}' MENANG!", Color.GREEN)
            log_step("DROP", f"Branch '{f_api.name}' di-drop seketika!", Color.RED)
            break

    print(f"\n{Color.GREEN}{Color.BOLD}[SELECT RESULT]:{Color.RESET} Pemenang = {winner} ({res_val})")


def demo_tokio_work_stealing() -> None:
    header("Simulasi Tokio Work-Stealing Multi-Worker Engine")
    runtime = TokioRuntimeSimulator(num_workers=2)

    runtime.spawn(SimulatedRustFuture("parse_incoming_tcp_stream()", required_steps=3, result_val="Payload[1024b]"))
    runtime.spawn(SimulatedRustFuture("tls_handshake_crypto()", required_steps=4, result_val="TLS_ECDHE_RSA"))
    runtime.spawn(SimulatedRustFuture("jwt_signature_verify()", required_steps=2, result_val="ClaimsValid(user_id=42)"))
    runtime.spawn(SimulatedRustFuture("db_connection_pool_acquire()", required_steps=3, result_val="ConnPoolId(7)"))

    runtime.run(max_ticks=20)

    print(f"\n{Color.BOLD}Statistik Worker Thread:{Color.RESET}")
    for w in runtime.workers:
        print(f"  Worker #{w.worker_id}: {Color.GREEN}{w.processed_count} poll invocations{Color.RESET}")


# ==============================================================================
# Interactive CLI Menu Interface
# ==============================================================================
def print_menu() -> None:
    header("RUST ASYNC & TOKIO RUNTIME FOUNDATION LAB")
    print(f"{Color.BOLD}Pilih mode simulasi teknis:{Color.RESET}")
    print(f"  {Color.CYAN}[1]{Color.RESET} Polling State Machine & Waker Trait Simulation")
    print(f"  {Color.CYAN}[2]{Color.RESET} Tokio Work-Stealing Multi-Threaded Runtime")
    print(f"  {Color.CYAN}[3]{Color.RESET} Concurrency Macro: tokio::join! (Semua Cabang)")
    print(f"  {Color.CYAN}[4]{Color.RESET} Concurrency Macro: tokio::select! (Race & Drop Cancel)")
    print(f"  {Color.CYAN}[5]{Color.RESET} Jalankan SEMUA Modul Simulasi (Full Suite)")
    print(f"  {Color.RED}[0]{Color.RESET} Keluar (Exit)")
    print(f"{Color.CYAN}{'-' * 65}{Color.RESET}")


def run_single_future_demo() -> None:
    header("Simulasi Dasar Future::poll & Waker")
    print("Melihat transisi Poll::Pending -> Waker::wake -> Poll::Ready secara bertahap:\n")
    fut = SimulatedRustFuture("async fn download_telemetry()", required_steps=3, result_val="Bytes<2048>")
    waker = Waker(1, lambda tid: print(f"    -> [Reactor Event]: IO socket fd siap, memanggil waker Task #{tid}"))

    step = 0
    while True:
        step += 1
        print(f"{Color.BOLD}Iterasi Loop #{step}:{Color.RESET}")
        res = fut.poll(waker)
        if res.is_ready():
            print(f"{Color.GREEN}Hasil Akhir: {res.value}{Color.RESET}\n")
            break
        time.sleep(0.05)


def run_interactive() -> None:
    # Auto-run jika dijalankan di environment non-interactive/pipe
    if not sys.stdin.isatty() or len(sys.argv) > 1 and sys.argv[1] in ("--auto", "--test"):
        print(f"{Color.YELLOW}[Non-interactive / Auto Mode Detected: Menjalankan Full Suite]{Color.RESET}")
        run_single_future_demo()
        demo_tokio_work_stealing()
        demo_join_macro()
        demo_select_macro()
        return

    while True:
        print_menu()
        try:
            choice = input(f"{Color.BOLD}Masukkan pilihan [0-5]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar.")
            break

        if choice == "1":
            run_single_future_demo()
        elif choice == "2":
            demo_tokio_work_stealing()
        elif choice == "3":
            demo_join_macro()
        elif choice == "4":
            demo_select_macro()
        elif choice == "5":
            run_single_future_demo()
            demo_tokio_work_stealing()
            demo_join_macro()
            demo_select_macro()
        elif choice == "0":
            print(f"\n{Color.GREEN}Terima kasih telah mempelajari fondasi Rust Async & Tokio Runtime!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")

        input(f"\n{Color.DIM}Tekan [Enter] untuk melanjutkan...{Color.RESET}")


if __name__ == "__main__":
    run_interactive()
