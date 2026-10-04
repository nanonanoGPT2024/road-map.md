#!/usr/bin/env python3
"""
Lab Hands-on: Arsitektur Actor & Konkurensi Asinkron (Model Akka/Pekko di Scala)
Mendemonstrasikan:
1. Actor State Encapsulation (Tanpa shared mutable state).
2. Mailbox & Message-Driven Asynchronous Processing (Pola Tell '!' & Ask '?').
3. Supervision Strategy & Fault Tolerance (Restart saat terjadi failure).
4. Dead Letter Queue untuk unhandled/dropped messages.
"""

import time
import queue
import threading
from typing import Any, Callable, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto

# ==============================================================================
# ANSI Color Formatting untuk Visualisasi Runtime Actor
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    CYAN    = "\033[36m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    RED     = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE    = "\033[34m"

def log_system(msg: str):
    print(f"{Color.CYAN}[SYSTEM]{Color.RESET} {msg}")

def log_actor(actor_name: str, msg: str, color=Color.GREEN):
    print(f"{color}[ACTOR: {actor_name}]{Color.RESET} {msg}")

def log_error(actor_name: str, msg: str):
    print(f"{Color.RED}{Color.BOLD}[FAILURE: {actor_name}]{Color.RESET} {msg}")

# ==============================================================================
# Model Protokol Pesan (Immutable Messages)
# ==============================================================================
class Message:
    """Basis seluruh pesan dalam sistem Actor."""
    pass

@dataclass(frozen=True)
class Deposit(Message):
    amount: float

@dataclass(frozen=True)
class Withdraw(Message):
    amount: float

@dataclass(frozen=True)
class GetBalance(Message):
    pass

@dataclass(frozen=True)
class BalanceResponse(Message):
    account_id: str
    balance: float

@dataclass(frozen=True)
class PoisonPill(Message):
    """Sinyal penghentian deterministik untuk Actor."""
    pass

@dataclass(frozen=True)
class InvalidOperation(Message):
    """Pesan simulasi kegagalan untuk memicu fault-tolerance."""
    reason: str

# Envelope pembungkus pesan dengan pengirim opsional
@dataclass
class Envelope:
    message: Message
    sender: Optional["ActorRef"] = None
    future_box: Optional[queue.Queue] = None

# ==============================================================================
# Actor Core Abstraction
# ==============================================================================
class Actor:
    """
    Kelas basis logika Actor.
    State internal Actor sepenuhnya privat dan hanya dimodifikasi
    secara sekuensial melalui loop pesan mailbox.
    """
    def __init__(self):
        self.context: Optional["ActorRef"] = None

    def pre_start(self):
        """Lifecycle hook sebelum mulai menerima pesan."""
        pass

    def post_stop(self):
        """Lifecycle hook setelah actor dimatikan."""
        pass

    def pre_restart(self, reason: Exception):
        """Lifecycle hook saat crash sebelum di-instansiasi ulang."""
        log_actor(self.context.name, f"Membersihkan state lama karena: {reason}", Color.YELLOW)
        self.post_stop()

    def receive(self, message: Message, sender: Optional["ActorRef"]) -> Any:
        """Handler pemrosesan pesan murni (harus di-override)."""
        raise NotImplementedError()


class ActorRef:
    """
    Handle referensi eksternal Actor. Memisahkan eksekusi thread internal
    dari antarmuka pemanggilan (enforce async message passing).
    """
    def __init__(self, name: str, actor_factory: Callable[[], Actor], system: "ActorSystem"):
        self.name = name
        self.actor_factory = actor_factory
        self.system = system
        self.mailbox: queue.Queue[Envelope] = queue.Queue()
        self.is_alive = True
        self.actor_instance: Actor = self._spawn_actor()
        self.worker_thread = threading.Thread(target=self._run_mailbox, name=f"Thread-{name}", daemon=True)
        self.worker_thread.start()

    def _spawn_actor(self) -> Actor:
        actor = self.actor_factory()
        actor.context = self
        actor.pre_start()
        return actor

    def tell(self, message: Message, sender: Optional["ActorRef"] = None):
        """Pola Tell ('!'): Asinkron tanpa memblokir pengirim (Fire-and-Forget)."""
        if not self.is_alive:
            self.system.dead_letters.put((self.name, message))
            return
        self.mailbox.put(Envelope(message=message, sender=sender))

    def ask(self, message: Message, timeout: float = 2.0) -> Any:
        """
        Pola Ask ('?'): Mengembalikan Future/Promise berbasis Channel lokal.
        Memblokir thread pemanggil sampai ada balasan atau batas waktu habis.
        """
        if not self.is_alive:
            raise RuntimeError(f"Actor {self.name} telah dihentikan.")
        box = queue.Queue(maxsize=1)
        self.mailbox.put(Envelope(message=message, sender=None, future_box=box))
        try:
            return box.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(f"Timeout meminta balasan dari Actor {self.name}")

    def _run_mailbox(self):
        """Loop dispatcher konsumsi Mailbox terisolasi per-actor."""
        while self.is_alive:
            try:
                envelope = self.mailbox.get()
                msg = envelope.message

                if isinstance(msg, PoisonPill):
                    self.actor_instance.post_stop()
                    self.is_alive = False
                    self.mailbox.task_done()
                    break

                # Eksekusi State Machine Actor
                try:
                    result = self.actor_instance.receive(msg, envelope.sender)
                    if envelope.future_box is not None:
                        envelope.future_box.put(result)
                except Exception as ex:
                    # Pola Supervision: One-For-One Strategy (Restart)
                    log_error(self.name, f"Exception tertangkap di mailbox loop: {str(ex)}")
                    self.actor_instance.pre_restart(ex)
                    self.actor_instance = self._spawn_actor()
                    if envelope.future_box is not None:
                        envelope.future_box.put(ex)

                self.mailbox.task_done()
            except Exception as system_err:
                log_system(f"Kesalahan internal dispatcher: {system_err}")

# ==============================================================================
# Actor System (Container & Lifecycle Manager)
# ==============================================================================
class ActorSystem:
    """Manajer siklus hidup actor dan registri sentral."""
    def __init__(self, name: str):
        self.name = name
        self.registry: Dict[str, ActorRef] = {}
        self.dead_letters: queue.Queue[Tuple[str, Message]] = queue.Queue()
        log_system(f"ActorSystem '{self.name}' diinisialisasi.")

    def actor_of(self, factory: Callable[[], Actor], name: str) -> ActorRef:
        if name in self.registry:
            raise ValueError(f"Actor dengan nama '{name}' sudah terdaftar.")
        ref = ActorRef(name, factory, self)
        self.registry[name] = ref
        return ref

    def stop(self, ref: ActorRef):
        ref.tell(PoisonPill())

    def terminate(self):
        log_system("Menghentikan sistem dan mengeringkan Mailbox...")
        for ref in self.registry.values():
            ref.tell(PoisonPill())
        for ref in self.registry.values():
            ref.worker_thread.join(timeout=1.0)
        log_system("Seluruh Actor telah berhenti dengan aman.")

# ==============================================================================
# Domain Logic: BankAccount Actor Implementation
# ==============================================================================
class BankAccountActor(Actor):
    """
    Contoh Domain: State Akun Bank.
    Variabel 'balance' tidak memiliki Lock/Mutex sama sekali, namun aman dari
    race condition karena concurrency dialihkan ke message-sequential queue.
    """
    def __init__(self, account_id: str, initial_balance: float = 0.0):
        super().__init__()
        self.account_id = account_id
        self.balance = initial_balance

    def pre_start(self):
        log_actor(self.context.name, f"Siap beroperasi. Saldo awal: Rp {self.balance:,.2f}")

    def post_stop(self):
        log_actor(self.context.name, f"Ditutup. Saldo akhir: Rp {self.balance:,.2f}", Color.MAGENTA)

    def receive(self, message: Message, sender: Optional[ActorRef]) -> Any:
        if isinstance(message, Deposit):
            if message.amount <= 0:
                raise ValueError("Jumlah deposit harus bernilai positif!")
            self.balance += message.amount
            log_actor(self.context.name, f"Deposit +Rp {message.amount:,.2f} -> Saldo: Rp {self.balance:,.2f}")
            return self.balance

        elif isinstance(message, Withdraw):
            if message.amount > self.balance:
                raise ValueError(f"Saldo tidak cukup: meminta {message.amount}, tersedia {self.balance}")
            self.balance -= message.amount
            log_actor(self.context.name, f"Tarik -Rp {message.amount:,.2f} -> Saldo: Rp {self.balance:,.2f}")
            return self.balance

        elif isinstance(message, GetBalance):
            log_actor(self.context.name, "Menerima inspeksi saldo.")
            response = BalanceResponse(self.account_id, self.balance)
            if sender:
                sender.tell(response, self.context)
            return response

        elif isinstance(message, InvalidOperation):
            # Memaksa crash tak terduga untuk memverifikasi Supervision restart
            raise ArithmeticError(f"Simulasi Crash Fatal: {message.reason}")

        else:
            log_actor(self.context.name, f"Unhandled message: {type(message).__name__}", Color.YELLOW)
            return None

# ==============================================================================
# Eksekusi Demonstrasi Lab
# ==============================================================================
def main():
    print(f"{Color.BOLD}=== SIMULASI KONKURANSI ASINKRON & ARSITEKTUR ACTOR (SCALA STYLE) ==={Color.RESET}\n")

    # 1. Inisialisasi Actor System
    system = ActorSystem("FintechBankingSystem")

    # 2. Spawning Actors (Pemisahan instance Actor dari referensinya)
    acc1_ref = system.actor_of(lambda: BankAccountActor("ACC-101", 1000.0), "Account-101")
    acc2_ref = system.actor_of(lambda: BankAccountActor("ACC-202", 500.0), "Account-202")

    time.sleep(0.1) # Sinkronisasi startup log
    print("\n--- [1] Mengirim Pesan Asinkron (Fire-and-Forget / Tell '!') ---")
    # Pengiriman massal asinkron, non-blocking
    acc1_ref.tell(Deposit(250.0))
    acc1_ref.tell(Deposit(150.0))
    acc2_ref.tell(Deposit(1000.0))
    acc1_ref.tell(Withdraw(300.0))

    time.sleep(0.2) # Memberikan giliran mailbox diproses
    print("\n--- [2] Mengambil Data Asinkron Menggunakan Request-Reply (Ask '?') ---")
    # Pola Ask memblokir thread eksekusi hingga menerima BalanceResponse
    try:
        res1: BalanceResponse = acc1_ref.ask(GetBalance(), timeout=1.0)
        print(f"{Color.BLUE}[HASIL ASK]{Color.RESET} {res1.account_id} memiliki Saldo Validasi: Rp {res1.balance:,.2f}")

        res2: BalanceResponse = acc2_ref.ask(GetBalance(), timeout=1.0)
        print(f"{Color.BLUE}[HASIL ASK]{Color.RESET} {res2.account_id} memiliki Saldo Validasi: Rp {res2.balance:,.2f}")
    except Exception as e:
        print(f"Error pada Ask: {e}")

    print("\n--- [3] Demonstrasi Fault-Tolerance & Supervision Strategy ---")
    log_system("Mengirim operasi ilegal ke Account-101 untuk memicu unhandled exception...")
    acc1_ref.tell(InvalidOperation("Korupsi memori simulasi pada worker"))

    # Jeda untuk memastikan siklus supervision restart berjalan
    time.sleep(0.2)

    log_system("Memverifikasi keandalan Actor pasca-restart...")
    # Actor telah me-restart state internalnya kembali ke constructor dasar
    acc1_ref.tell(Deposit(50.0))
    time.sleep(0.1)

    print("\n--- [4] Dead Letter Queue & Graceful Teardown ---")
    system.stop(acc2_ref)
    time.sleep(0.1)
    
    log_system("Mencoba mengirim pesan ke actor yang telah mati...")
    acc2_ref.tell(Deposit(9999.0)) # Seharusnya masuk ke DeadLetter

    if not system.dead_letters.empty():
        target, dropped_msg = system.dead_letters.get()
        print(f"{Color.MAGENTA}[DEAD LETTER]{Color.RESET} Pesan untuk '{target}' dibuang: {dropped_msg}")

    # Menghentikan ActorSystem seutuhnya
    system.terminate()
    print(f"\n{Color.BOLD}{Color.GREEN}Lab selesai. Model konkurensi Actor berhasil diverifikasi.{Color.RESET}")

if __name__ == "__main__":
    main()