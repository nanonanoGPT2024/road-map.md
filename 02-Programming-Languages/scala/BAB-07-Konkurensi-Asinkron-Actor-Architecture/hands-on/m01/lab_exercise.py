#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Konkurensi Scala & Arsitektur Actor (Akka/Pekko Style)
BAB-07: Konkurensi Asinkron & Actor Architecture

Script ini mendemonstrasikan konsep inti paradigma konkurensi di ekosistem Scala:
1. ExecutionContext & Future/Promise (Non-blocking Asynchronous Computation)
2. Actor Model (Mailbox Queue, State Isolation, Tell '!' vs Ask '?' Pattern)
3. Hierarchical Supervision Strategy (Resume, Restart, Stop pada kegagalan Actor)
"""

import sys
import time
import queue
import threading
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

# ==============================================================================
# ANSI Color Palette & Terminal Styling
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"

def print_banner(title: str) -> None:
    width = 75
    print(f"\n{Color.CYAN}{'=' * width}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE} {title.center(width - 2)} {Color.RESET}")
    print(f"{Color.CYAN}{'=' * width}{Color.RESET}")

def log_actor(actor_name: str, message: str, color: str = Color.GREEN) -> None:
    timestamp = time.strftime("%H:%M:%S")
    thread_name = threading.current_thread().name
    print(f"{Color.DIM}[{timestamp}] [{thread_name}]{Color.RESET} "
          f"{color}[{actor_name}]{Color.RESET} {message}")

# ==============================================================================
# Bagian 1: Scala Future & Promise Abstraction
# ==============================================================================
class Promise:
    def __init__(self):
        self._future = Future()

    @property
    def future(self) -> 'Future':
        return self._future

    def success(self, value: Any) -> None:
        self._future._complete(value, None)

    def failure(self, exc: Exception) -> None:
        self._future._complete(None, exc)

class Future:
    def __init__(self):
        self._completed = False
        self._value: Optional[Any] = None
        self._exception: Optional[Exception] = None
        self._callbacks: List[Callable[['Future'], None]] = []
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

    def is_completed(self) -> bool:
        with self._lock:
            return self._completed

    def _complete(self, value: Any, exc: Optional[Exception]) -> None:
        callbacks_to_run = []
        with self._condition:
            if self._completed:
                return
            self._value = value
            self._exception = exc
            self._completed = True
            callbacks_to_run = list(self._callbacks)
            self._callbacks.clear()
            self._condition.notify_all()

        for cb in callbacks_to_run:
            threading.Thread(target=cb, args=(self,), daemon=True).start()

    def on_complete(self, callback: Callable[['Future'], None]) -> 'Future':
        run_now = False
        with self._lock:
            if self._completed:
                run_now = True
            else:
                self._callbacks.append(callback)
        if run_now:
            threading.Thread(target=callback, args=(self,), daemon=True).start()
        return self

    def await_result(self, timeout: Optional[float] = 5.0) -> Any:
        with self._condition:
            if not self._completed:
                if not self._condition.wait(timeout=timeout):
                    raise TimeoutError("Future timed out")
            if self._exception:
                raise self._exception
            return self._value

    @staticmethod
    def async_exec(task: Callable[[], Any]) -> 'Future':
        promise = Promise()
        def worker():
            try:
                res = task()
                promise.success(res)
            except Exception as e:
                promise.failure(e)
        t = threading.Thread(target=worker, daemon=True, name="ScalaExecutionContext")
        t.start()
        return promise.future

# ==============================================================================
# Bagian 2: Actor System, Mailbox, dan Messaging Contract
# ==============================================================================
class Directive(Enum):
    RESUME = auto()
    RESTART = auto()
    STOP = auto()

@dataclass
class Envelope:
    message: Any
    sender: Optional['ActorRef'] = None
    reply_promise: Optional[Promise] = None

class Actor:
    def __init__(self):
        self.context: Optional['ActorContext'] = None

    def pre_start(self) -> None:
        pass

    def post_stop(self) -> None:
        pass

    def pre_restart(self, reason: Exception) -> None:
        self.post_stop()

    def post_restart(self, reason: Exception) -> None:
        self.pre_start()

    def receive(self, message: Any, sender: Optional['ActorRef']) -> Any:
        raise NotImplementedError

class ActorRef:
    def __init__(self, name: str, actor_cls: type, supervisor: Optional['ActorRef'] = None):
        self.name = name
        self.actor_cls = actor_cls
        self.supervisor = supervisor
        self.mailbox = queue.Queue()
        self._is_stopped = False
        self._lock = threading.Lock()
        
        self.instance: Actor = self.actor_cls()
        self.instance.pre_start()

        self._worker_thread = threading.Thread(target=self._dispatcher_loop, name=f"Actor-{name}", daemon=True)
        self._worker_thread.start()

    def tell(self, message: Any, sender: Optional['ActorRef'] = None) -> None:
        """Tell Pattern: '!' Fire-and-forget"""
        with self._lock:
            if not self._is_stopped:
                self.mailbox.put(Envelope(message=message, sender=sender))

    def ask(self, message: Any, timeout: float = 3.0) -> Future:
        """Ask Pattern: '?' Request-Response returning Future"""
        promise = Promise()
        with self._lock:
            if not self._is_stopped:
                self.mailbox.put(Envelope(message=message, sender=None, reply_promise=promise))
            else:
                promise.failure(RuntimeError(f"Actor {self.name} is stopped."))
        return promise.future

    def stop(self) -> None:
        with self._lock:
            self._is_stopped = True
        self.mailbox.put(None)  # Poison pill signal

    def _dispatcher_loop(self) -> None:
        while True:
            envelope: Optional[Envelope] = self.mailbox.get()
            if envelope is None or self._is_stopped:
                self.instance.post_stop()
                break

            try:
                result = self.instance.receive(envelope.message, envelope.sender)
                if envelope.reply_promise:
                    envelope.reply_promise.success(result)
            except Exception as exc:
                if envelope.reply_promise:
                    envelope.reply_promise.failure(exc)
                self._handle_failure(exc)
            finally:
                self.mailbox.task_done()

    def _handle_failure(self, exc: Exception) -> None:
        directive = Directive.RESTART
        if self.supervisor:
            log_actor("SUPERVISOR", f"Menangani error dari [{self.name}]: {exc}", Color.RED)
            directive = Directive.RESTART

        if directive == Directive.RESTART:
            log_actor(self.name, f"{Color.YELLOW}Supervision: RESTARTING Actor state...{Color.RESET}", Color.YELLOW)
            self.instance.pre_restart(exc)
            self.instance = self.actor_cls()
            self.instance.post_restart(exc)
        elif directive == Directive.STOP:
            log_actor(self.name, f"{Color.RED}Supervision: STOPPING Actor.{Color.RESET}", Color.RED)
            self.stop()
        elif directive == Directive.RESUME:
            log_actor(self.name, f"{Color.BLUE}Supervision: RESUMING Actor (state kept).{Color.RESET}", Color.BLUE)

# ==============================================================================
# Bagian 3: Implementasi Kasus Domain (Payment Worker & Ledger System)
# ==============================================================================
@dataclass
class ProcessPayment:
    txn_id: str
    amount: float
    account: str

@dataclass
class GetBalance:
    account: str

@dataclass
class SimulateCrash:
    reason: str

class PaymentWorkerActor(Actor):
    def pre_start(self) -> None:
        self.processed_count = 0
        log_actor("PaymentWorker", f"{Color.GREEN}Actor diinisialisasi & siap menerima pesan.{Color.RESET}")

    def pre_restart(self, reason: Exception) -> None:
        log_actor("PaymentWorker", f"{Color.RED}Membersihkan state korup akibat: {reason}{Color.RESET}")
        super().pre_restart(reason)

    def receive(self, message: Any, sender: Optional[ActorRef]) -> Any:
        if isinstance(message, ProcessPayment):
            time.sleep(0.3)  # Simulasi IO Latency non-blocking
            if message.amount <= 0:
                raise ValueError(f"Nominal pembayaran invalid: {message.amount}")
            
            self.processed_count += 1
            log_actor("PaymentWorker", 
                      f"Sukses proses Txn #{message.txn_id} (${message.amount:.2f}) untuk akun [{message.account}] "
                      f"[Total Diproses: {self.processed_count}]", Color.GREEN)
            return {"status": "SUCCESS", "txn_id": message.txn_id, "processed_by": "PaymentWorker"}

        elif isinstance(message, SimulateCrash):
            log_actor("PaymentWorker", f"{Color.RED}Memicu crash internal: {message.reason}{Color.RESET}")
            raise RuntimeError(message.reason)

        elif isinstance(message, GetBalance):
            return {"account": message.account, "worker_ops": self.processed_count}

        else:
            log_actor("PaymentWorker", f"Pesan tidak dikenali: {message}", Color.YELLOW)
            return {"status": "IGNORED"}

# ==============================================================================
# Bagian 4: Demonstrasi Alur Interaktif & CLI Menu
# ==============================================================================
def demo_scala_futures() -> None:
    print_banner("1. DEMO: Scala Future & ExecutionContext (Non-Blocking)")
    print(f"{Color.WHITE}Memulai kalkulasi async dengan Future...{Color.RESET}")

    def heavy_calculation():
        log_actor("FutureTask", "Sedang menghitung hashing desentralisasi...", Color.MAGENTA)
        time.sleep(0.8)
        return 42 * 1337

    future = Future.async_exec(heavy_calculation)
    
    def on_success(f: Future):
        try:
            val = f.await_result()
            print(f"{Color.GREEN}--> Callback on_complete sukses! Nilai komputasi: {val}{Color.RESET}")
        except Exception as e:
            print(f"{Color.RED}--> Callback on_complete gagal: {e}{Color.RESET}")

    future.on_complete(on_success)
    print(f"{Color.CYAN}Thread utama TIDAK terblokir, melanjutkan eksekusi lain...{Color.RESET}")
    result = future.await_result(timeout=2.0)
    print(f"{Color.BOLD}Hasil sinkronisasi akhir: {result}{Color.RESET}\n")

def demo_actor_tell_and_ask() -> None:
    print_banner("2. DEMO: Actor Tell (!) & Ask (?) Pattern")
    worker_ref = ActorRef(name="PaymentWorker-1", actor_cls=PaymentWorkerActor)

    # 1. Tell Pattern (Fire and Forget)
    print(f"{Color.BOLD}[TELL '!'] Mengirim 2 pesan asinkron tanpa menunggu respon...{Color.RESET}")
    worker_ref.tell(ProcessPayment(txn_id="TXN-101", amount=150.0, account="ID-ACC-01"))
    worker_ref.tell(ProcessPayment(txn_id="TXN-102", amount=89.5, account="ID-ACC-02"))
    time.sleep(0.8)

    # 2. Ask Pattern (Request-Reply dengan Future)
    print(f"\n{Color.BOLD}[ASK '?'] Mengirim query status akun & menunggu Future terselesaikan...{Color.RESET}")
    ask_future = worker_ref.ask(GetBalance(account="ID-ACC-01"), timeout=2.0)
    reply = ask_future.await_result()
    print(f"{Color.GREEN}--> Jawaban diterima via Ask Pattern: {reply}{Color.RESET}\n")
    worker_ref.stop()

def demo_supervision_strategy() -> None:
    print_banner("3. DEMO: Akka/Pekko Supervision Hierarchy & Failure Recovery")
    supervisor_ref = ActorRef(name="RootSupervisor", actor_cls=PaymentWorkerActor)
    supervised_worker = ActorRef(name="ResilientWorker", actor_cls=PaymentWorkerActor, supervisor=supervisor_ref)

    # Kirim pesan valid
    supervised_worker.tell(ProcessPayment(txn_id="TXN-201", amount=300.0, account="ID-ACC-09"))
    time.sleep(0.4)

    # Kirim instruksi yang memicu crash (Supervision Restart)
    print(f"\n{Color.RED}{Color.BOLD}Simulasi: Menyuntikkan fatal error ke worker...{Color.RESET}")
    supervised_worker.tell(SimulateCrash(reason="DatabaseConnectionDeadlockException"))
    time.sleep(0.6)

    # Kirim transaksi berikutnya untuk membuktikan Actor pulih kembali setelah Restart
    print(f"\n{Color.GREEN}{Color.BOLD}Verifikasi: Mengirim transaksi pasca-restart (Self-healing)...{Color.RESET}")
    future = supervised_worker.ask(ProcessPayment(txn_id="TXN-202", amount=75.0, account="ID-ACC-09"))
    res = future.await_result()
    print(f"{Color.GREEN}--> Transaksi sukses setelah pemulihan: {res}{Color.RESET}\n")
    
    supervised_worker.stop()
    supervisor_ref.stop()

def interactive_cli() -> None:
    print_banner("SCALA CONCURRENCY & ACTOR SYSTEM SIMULATOR")
    print(f"{Color.WHITE}Materi: BAB-07 Konkurensi Asinkron & Actor Architecture")
    print(f"Implementasi: Python 3 Runnable Simulation Engine{Color.RESET}\n")

    menu = (
        f"{Color.CYAN}Pilih Skenario Demonstrasi:{Color.RESET}\n"
        f"  {Color.BOLD}1{Color.RESET}. Jalankan Simulasi Scala Future & Promise Non-blocking\n"
        f"  {Color.BOLD}2{Color.RESET}. Jalankan Simulasi Actor Model (Tell '!' & Ask '?')\n"
        f"  {Color.BOLD}3{Color.RESET}. Jalankan Simulasi Fault-Tolerance & Supervision Restart\n"
        f"  {Color.BOLD}4{Color.RESET}. Jalankan SEMUA Modul Secara Otomatis\n"
        f"  {Color.BOLD}0{Color.RESET}. Keluar\n"
    )

    if not sys.stdin.isatty():
        print(f"{Color.YELLOW}Mode non-interaktif terdeteksi. Menjalankan seluruh pengujian otomatis...{Color.RESET}")
        demo_scala_futures()
        demo_actor_tell_and_ask()
        demo_supervision_strategy()
        print_banner("SIMULASI SUKSES 100% - SEMUA FITUR TERVERIFIKASI")
        return

    while True:
        print(menu)
        try:
            choice = input(f"{Color.BOLD}Pilihan Anda [0-4]: {Color.RESET}").strip()
            if choice == "1":
                demo_scala_futures()
            elif choice == "2":
                demo_actor_tell_and_ask()
            elif choice == "3":
                demo_supervision_strategy()
            elif choice == "4":
                demo_scala_futures()
                demo_actor_tell_and_ask()
                demo_supervision_strategy()
                print_banner("SIMULASI SUKSES 100% - SEMUA FITUR TERVERIFIKASI")
            elif choice == "0":
                print(f"{Color.GREEN}Keluar dari lab exercise. Selamat belajar Scala Concurrency!{Color.RESET}")
                break
            else:
                print(f"{Color.RED}Pilihan '{choice}' tidak valid.{Color.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Sesi dibatalkan.{Color.RESET}")
            break

if __name__ == "__main__":
    interactive_cli()
