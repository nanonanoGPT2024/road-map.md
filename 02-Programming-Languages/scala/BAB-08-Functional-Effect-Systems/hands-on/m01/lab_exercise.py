#!/usr/bin/env python3
"""
Hands-on Lab: BAB-08 Functional Effect Systems (Scala - Cats Effect / ZIO Concept Simulator)
Simulasi komputasi murni (Pure Effect Description) vs Eksekusi Runtime (Unsafe Run).
"""

from __future__ import annotations
import sys
import time
import threading
from typing import Callable, Generic, TypeVar, Any, Optional

T = TypeVar("T")
U = TypeVar("U")

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


class Fiber(Generic[T]):
    """Simulasi Fiber / Green Thread Cats Effect / ZIO."""
    def __init__(self, thread: threading.Thread, result_box: list[Any]):
        self._thread = thread
        self._result_box = result_box

    def join(self) -> T:
        self._thread.join()
        res = self._result_box[0]
        if isinstance(res, Exception):
            raise res
        return res


class IO(Generic[T]):
    """
    Abstraksi Functional Effect IO[T]:
    Representasi data murni (deskripsi efek) tanpa langsung mengeksekusi side-effect.
    """
    def __init__(self, thunk: Callable[[], T]):
        self._thunk = thunk

    @staticmethod
    def pure(value: T) -> IO[T]:
        """Konstruktor IO murni yang bernilai konstan."""
        return IO(lambda: value)

    @staticmethod
    def delay(effect: Callable[[], T]) -> IO[T]:
        """Membungkus side-effect imperatif ke dalam deskripsi IO yang lazy."""
        return IO(effect)

    @staticmethod
    def raise_error(err: Exception) -> IO[T]:
        """Membungkus error dalam deskripsi IO."""
        def failed():
            raise err
        return IO(failed)

    def map(self, fn: Callable[[T], U]) -> IO[U]:
        """Functor mapping: IO[T] -> (T -> U) -> IO[U]."""
        return IO(lambda: fn(self.unsafe_run_sync()))

    def flat_map(self, fn: Callable[[T], IO[U]]) -> IO[U]:
        """Monadic bind: IO[T] -> (T -> IO[U]) -> IO[U]."""
        return IO(lambda: fn(self.unsafe_run_sync()).unsafe_run_sync())

    def attempt(self) -> IO[tuple[Optional[Exception], Optional[T]]]:
        """Menangkap error dan mengubahnya menjadi nilai tuple (error, value)."""
        def run_attempt():
            try:
                val = self.unsafe_run_sync()
                return (None, val)
            except Exception as ex:
                return (ex, None)
        return IO(run_attempt)

    def handle_error_with(self, handler: Callable[[Exception], IO[T]]) -> IO[T]:
        """Pemulihan error fungsional."""
        def run_fallback():
            try:
                return self.unsafe_run_sync()
            except Exception as ex:
                return handler(ex).unsafe_run_sync()
        return IO(run_fallback)

    def guarantee(self, finalizer: IO[Any]) -> IO[T]:
        """Memastikan finalizer selalu dieksekusi (pola Resource/Bracket Cats Effect)."""
        def run_guaranteed():
            try:
                return self.unsafe_run_sync()
            finally:
                finalizer.unsafe_run_sync()
        return IO(run_guaranteed)

    def start(self) -> IO[Fiber[T]]:
        """Forking efek ke fiber/thread terpisah."""
        def run_fork():
            box: list[Any] = [None]
            def worker():
                try:
                    box[0] = self.unsafe_run_sync()
                except Exception as ex:
                    box[0] = ex
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            return Fiber(t, box)
        return IO(run_fork)

    def unsafe_run_sync(self) -> T:
        """Pintu gerbang runtime IO: mengeksekusi deskripsi program fungsional."""
        return self._thunk()


# Simulasi Operasi I/O
def console_log(msg: str, color: str = CYAN) -> IO[None]:
    return IO.delay(lambda: print(f"{color}{msg}{RESET}"))


def simulate_db_query(query_id: str) -> IO[dict[str, Any]]:
    def run_query():
        print(f"  {YELLOW}→ [DB Query] Mengambil data entitas '{query_id}'...{RESET}")
        time.sleep(0.3)
        if query_id == "invalid":
            raise ValueError(f"Entitas id '{query_id}' tidak valid!")
        return {"id": query_id, "balance": 750000, "status": "ACTIVE"}
    return IO.delay(run_query)


def simulate_payment(account: dict[str, Any], amount: int) -> IO[dict[str, Any]]:
    def run_pay():
        print(f"  {YELLOW}→ [Payment Gateway] Memproses transfer Rp {amount:,}...{RESET}")
        time.sleep(0.2)
        if amount > account["balance"]:
            raise RuntimeError(f"Saldo Rp {account['balance']:,} tidak mencukupi untuk transfer Rp {amount:,}!")
        account["balance"] -= amount
        return {"status": "SUCCESS", "remaining_balance": account["balance"]}
    return IO.delay(run_pay)


def demo_lazy_evaluation():
    print(f"\n{BOLD}{CYAN}=== 1. DEMO: PURE DESCRIPTION VS RUNTIME EXECUTION ==={RESET}")
    print(f"{MAGENTA}[Info] Membangun deskripsi program (IO graph)... Belum ada side-effect yang berjalan.{RESET}")

    executed_flag = False

    def effect():
        nonlocal executed_flag
        executed_flag = True
        return 42

    program = IO.delay(effect).map(lambda x: x * 2)

    print(f"  Status sebelum unsafe_run_sync: executed = {executed_flag} (Benar-benar Lazy)")
    result = program.unsafe_run_sync()
    print(f"  Status setelah unsafe_run_sync : executed = {executed_flag}, result = {GREEN}{result}{RESET}")


def demo_resource_safety():
    print(f"\n{BOLD}{CYAN}=== 2. DEMO: RESOURCE SAFETY & BRACKET PATTERN ==={RESET}")
    acquire = console_log("  [Acquire] Membuka koneksi file lock / socket...", YELLOW)
    release = console_log("  [Release] Menutup koneksi & membersihkan memori (Guaranteed!).", GREEN)

    def flaky_work():
        print(f"  {RED}  [Worker] Terjadi kegagalan kritis di tengah proses!{RESET}")
        raise ConnectionResetError("Koneksi TCP terputus mendadak.")

    unsafe_task = IO.delay(flaky_work)
    safe_program = unsafe_task.guarantee(release)

    full_workflow = acquire.flat_map(lambda _: safe_program)

    try:
        full_workflow.unsafe_run_sync()
    except ConnectionResetError as e:
        print(f"  {MAGENTA}[Catched] Program menangkap error di runtime: {e}{RESET}")


def demo_fiber_concurrency():
    print(f"\n{BOLD}{CYAN}=== 3. DEMO: LIGHTWEIGHT FIBER FORK & JOIN ==={RESET}")

    def background_task(name: str, delay_sec: float) -> str:
        print(f"  {YELLOW}→ Fiber [{name}] mulai bekerja di latar belakang...{RESET}")
        time.sleep(delay_sec)
        print(f"  {GREEN}✓ Fiber [{name}] selesai.{RESET}")
        return f"Hasil dari {name}"

    io_task1 = IO.delay(lambda: background_task("Fiber-Alpha", 0.4))
    io_task2 = IO.delay(lambda: background_task("Fiber-Beta", 0.2))

    concurrent_prog = (
        io_task1.start().flat_map(
            lambda fiber1: io_task2.start().flat_map(
                lambda fiber2: IO.delay(lambda: (fiber1.join(), fiber2.join()))
            )
        )
    )

    t0 = time.time()
    res1, res2 = concurrent_prog.unsafe_run_sync()
    elapsed = time.time() - t0
    print(f"  {GREEN}Hasil join fiber: {res1} & {res2} (Waktu: {elapsed:.2f} detik){RESET}")


def demo_monadic_composition(account_id: str, amount: int):
    print(f"\n{BOLD}{CYAN}=== 4. DEMO: MONADIC PIPELINE TRANSFER TRANSAKSI ==={RESET}")

    pipeline = (
        simulate_db_query(account_id)
        .flat_map(lambda acc: simulate_payment(acc, amount))
        .handle_error_with(lambda err: IO.pure({"status": "FAILED", "reason": str(err)}))
    )

    result = pipeline.unsafe_run_sync()
    if result["status"] == "SUCCESS":
        print(f"  {GREEN}✓ Transaksi Sukses! Sisa Saldo: Rp {result['remaining_balance']:,}{RESET}")
    else:
        print(f"  {RED}✗ Transaksi Gagal! Alasan: {result['reason']}{RESET}")


def main():
    print(f"{BOLD}{GREEN}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}   SCALA BAB-08: FUNCTIONAL EFFECT SYSTEMS (CATS EFFECT / ZIO) LAB   {RESET}")
    print(f"{BOLD}{GREEN}======================================================================{RESET}")

    demo_lazy_evaluation()
    demo_resource_safety()
    demo_fiber_concurrency()

    # Skenario Sukses & Gagal
    demo_monadic_composition("user-101", 250000)
    demo_monadic_composition("user-101", 900000)
    demo_monadic_composition("invalid", 50000)

    print(f"\n{BOLD}{GREEN}=== SELURUH SIMULASI EFFECT SYSTEM SELESAI DIEKSEKUSI SECARA VALID ==={RESET}\n")


if __name__ == "__main__":
    main()
