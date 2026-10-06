#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Inti Swift Concurrency (iOS)
Materi: BAB-04 - Pemrograman Asinkron Modern & Swift Concurrency

Skrip ini mereplikasi arsitektur dan semantik Swift Concurrency menggunakan asyncio Python:
1. async/await & Cooperative Thread Pool Task Suspension
2. Actor Model & Data Race Isolation (Swift Actor Reentrancy & Thread Safety)
3. Structured Concurrency (Task & TaskGroup Fan-out/Fan-in & Cancellation)
4. @MainActor UI Dispatching & Thread-Hopping Safety Check
"""

import asyncio
import time
import sys
import random
from typing import List, Dict, Any, Optional

# --- ANSI Terminal Color Palette ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_DIM     = "\033[2m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"
CLR_WHITE   = "\033[97m"
CLR_BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 65}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_WHITE}  {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 65}{CLR_RESET}")


def log_step(badge: str, color: str, msg: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{CLR_DIM}{timestamp}{CLR_RESET}] [{color}{CLR_BOLD}{badge:<12}{CLR_RESET}] {msg}")


# ============================================================================
# Modul 1: Swift Actor Model & State Isolation
# Mereplikasi: actor BankAccount { var balance: Double ... }
# ============================================================================
class SwiftActorAccount:
    """
    Simulasi Swift 'actor'.
    Di Swift, akses terhadap state mutable actor dilindungi oleh compiler
    dan antrean serial terisolasi, mencegah data race multi-thread.
    """
    def __init__(self, owner: str, initial_balance: float):
        self.owner = owner
        self._balance = initial_balance
        self._mailbox_lock = asyncio.Lock()  # Serial executor queue

    async def deposit(self, amount: float, origin_task: str) -> float:
        async with self._mailbox_lock:
            log_step("ACTOR_ENTER", CLR_GREEN, f"Task '{origin_task}' masuk isolasi Actor '{self.owner}'")
            # Replikasi potensi suspension point (await) di dalam actor
            await asyncio.sleep(0.05)
            self._balance += amount
            log_step("ACTOR_EXIT", CLR_GREEN, f"Deposit +${amount:0.2f} selesai. Saldo: ${self._balance:0.2f}")
            return self._balance

    async def withdraw(self, amount: float, origin_task: str) -> bool:
        async with self._mailbox_lock:
            log_step("ACTOR_ENTER", CLR_YELLOW, f"Task '{origin_task}' masuk isolasi Actor '{self.owner}'")
            await asyncio.sleep(0.08)
            if self._balance >= amount:
                self._balance -= amount
                log_step("ACTOR_EXIT", CLR_GREEN, f"Penarikan -${amount:0.2f} disetujui. Sisa: ${self._balance:0.2f}")
                return True
            else:
                log_step("ACTOR_DENIED", CLR_RED, f"Saldo tidak cukup (${self._balance:0.2f} < ${amount:0.2f})")
                return False

    async def get_balance(self) -> float:
        async with self._mailbox_lock:
            return self._balance


# ============================================================================
# Modul 2: @MainActor UI Dispatcher Simulation
# Mereplikasi isolasi UI thread UIKit/SwiftUI (@MainActor)
# ============================================================================
class SwiftMainActor:
    """
    Simulasi @MainActor di Swift.
    Semua modifikasi state UI harus dieksekusi pada main executor.
    """
    def __init__(self):
        self.active_ui_state: Dict[str, Any] = {"status": "Idle", "items_loaded": 0}
        self.main_queue_id = "main_ui_thread_01"

    async def mutate_ui(self, key: str, value: Any, caller_thread: str) -> None:
        log_step("DISPATCH_CHK", CLR_MAGENTA, f"Cek eksekutor pemanggil: '{caller_thread}'")
        if caller_thread != self.main_queue_id:
            log_step("HOPPING_REQ", CLR_YELLOW, f"Thread-hop diperlukan: '{caller_thread}' -> '@MainActor'")
            await asyncio.sleep(0.02)  # Hop context switch overhead
        
        self.active_ui_state[key] = value
        log_step("UI_RENDER", CLR_GREEN, f"@MainActor diperbarui: {key} = {value}")


# ============================================================================
# Modul 3: Task & Structured Concurrency (withTaskGroup)
# Mereplikasi async let dan withTaskGroup() dengan propagasi pembatalan
# ============================================================================
async def fetch_user_avatar(user_id: int) -> str:
    log_step("CHILD_TASK", CLR_BLUE, f"[Subtask {user_id}] Mengunduh avatar...")
    await asyncio.sleep(random.uniform(0.1, 0.25))
    return f"avatar_user_{user_id}.png"


async def fetch_user_posts(user_id: int) -> List[str]:
    log_step("CHILD_TASK", CLR_BLUE, f"[Subtask {user_id}] Mengambil feed posts...")
    await asyncio.sleep(random.uniform(0.15, 0.3))
    return [f"Post #1 by user {user_id}", f"Post #2 by user {user_id}"]


async def run_task_group_demo() -> None:
    header("DEMO 1: Swift Structured Concurrency (withTaskGroup)")
    print(f"{CLR_DIM}Memanggil fetch paralel avatar & post via TaskGroup terstruktur...{CLR_RESET}")
    
    start_time = time.perf_counter()
    user_id = 42

    # Structured scope: kedua child task harus selesai sebelum scope keluar
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(fetch_user_avatar(user_id))
        t2 = tg.create_task(fetch_user_posts(user_id))

    avatar_result = t1.result()
    posts_result = t2.result()
    elapsed = time.perf_counter() - start_time

    log_step("GROUP_DONE", CLR_CYAN, f"Fan-in hasil selesai dalam {elapsed*1000:0.1f}ms")
    print(f"  {CLR_WHITE}→ Avatar:{CLR_RESET} {avatar_result}")
    print(f"  {CLR_WHITE}→ Posts ({len(posts_result)}):{CLR_RESET} {posts_result}")


# ============================================================================
# Modul 4: Actor Isolation & Data Race Immunity
# Mereplikasi kompetisi concurrent task pada 1 resource bersama
# ============================================================================
async def run_actor_race_demo() -> None:
    header("DEMO 2: Swift Actor Data Race Protection")
    print(f"{CLR_DIM}10 transaksi concurrent simultan pada satu instance Actor...{CLR_RESET}")
    
    account = SwiftActorAccount("Satoshi Nakamoto", initial_balance=500.0)

    async def transaction_job(tx_id: int, is_deposit: bool, amount: float):
        task_name = f"TxWorker-{tx_id:02d}"
        if is_deposit:
            await account.deposit(amount, task_name)
        else:
            await account.withdraw(amount, task_name)

    # Launch 10 concurrent uncoordinated tasks
    tasks = []
    for i in range(1, 11):
        is_dep = (i % 2 == 0)
        amt = 100.0 if is_dep else 75.0
        tasks.append(transaction_job(i, is_dep, amt))

    await asyncio.gather(*tasks)
    final_balance = await account.get_balance()
    
    # Perhitungan teoretis: 500 + (5 * 100) - (5 * 75) = 500 + 500 - 375 = 625.0
    print(f"\n{CLR_BOLD}{CLR_GREEN}Hasil Audit Actor Isolation:{CLR_RESET}")
    print(f"  Saldo Akhir Terkunci: {CLR_BOLD}${final_balance:0.2f}{CLR_RESET} (Integritas Memory Aman 100%)")


# ============================================================================
# Modul 5: Cooperative Task Cancellation
# Mereplikasi: Task.isCancelled & Task.checkCancellation()
# ============================================================================
async def cancellable_stream_job(task_name: str) -> None:
    log_step("TASK_SPAWN", CLR_BLUE, f"Memulai background worker: '{task_name}'")
    try:
        for frame in range(1, 10):
            # Swift: try Task.checkCancellation()
            await asyncio.sleep(0.08)
            log_step("STREAMING", CLR_WHITE, f"Worker '{task_name}' memproses batch #{frame}...")
    except asyncio.CancelledError:
        log_step("CANCEL_ACK", CLR_RED, f"Swift Task '{task_name}' mendeteksi signal pembatalan!")
        log_step("CLEANUP", CLR_YELLOW, f"Membersihkan buffer memori '{task_name}' secara kooperatif...")
        raise


async def run_cancellation_demo() -> None:
    header("DEMO 3: Swift Cooperative Task Cancellation")
    print(f"{CLR_DIM}Menjalankan task asinkron lalu membatalkannya di tengah proses...{CLR_RESET}")
    
    task = asyncio.create_task(cancellable_stream_job("VideoFrameDownloader"))
    await asyncio.sleep(0.25)
    
    log_step("CALL_CANCEL", CLR_RED, "Trigger: task.cancel() dipanggil oleh UI ViewModel")
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        log_step("TASK_EXIT", CLR_CYAN, "Task berhasil dibatalkan secara bersih tanpa zombie thread.")


# ============================================================================
# Modul 6: Full Pipeline End-to-End (@MainActor + TaskGroup + Actor)
# ============================================================================
async def run_pipeline_demo() -> None:
    header("DEMO 4: End-to-End iOS Architecture Flow")
    print(f"{CLR_DIM}Simulasi fetch data background -> update model Actor -> dispatch @MainActor UI{CLR_RESET}")

    main_actor = SwiftMainActor()
    account = SwiftActorAccount("Developer", 1000.0)

    # 1. Background worker (Cooperative thread pool)
    worker_thread = "bg_cooperative_pool_thread_04"
    log_step("BG_WORK", CLR_BLUE, f"Memulai fetch data di: '{worker_thread}'")
    
    await account.deposit(250.0, "BackgroundPayrollJob")
    bal = await account.get_balance()

    # 2. Hop ke @MainActor untuk update antarmuka pengguna
    await main_actor.mutate_ui("balance_display", f"${bal:0.2f}", worker_thread)
    await main_actor.mutate_ui("status", "Synced to Cloud", main_actor.main_queue_id)


# ============================================================================
# Interactive CLI Menu
# ============================================================================
async def interactive_menu() -> None:
    banner = f"""{CLR_BOLD}{CLR_CYAN}
╔════════════════════════════════════════════════════════════════╗
║     SWIFT CONCURRENCY INTERACTIVE TECHNICAL SIMULATOR         ║
║     Modul: iOS Modern Asynchronous Programming Architecture    ║
╚════════════════════════════════════════════════════════════════╝{CLR_RESET}"""
    print(banner)

    menu_text = f"""
{CLR_BOLD}Pilih Skenario Pembelajaran Swift Concurrency:{CLR_RESET}
  {CLR_GREEN}[1]{CLR_RESET} Structured Concurrency (TaskGroup Fan-out & Fan-in)
  {CLR_GREEN}[2]{CLR_RESET} Actor State Isolation & Data Race Protection
  {CLR_GREEN}[3]{CLR_RESET} Cooperative Task Cancellation (Task.checkCancellation)
  {CLR_GREEN}[4]{CLR_RESET} End-to-End iOS Flow (@MainActor UI Thread-Hopping)
  {CLR_GREEN}[5]{CLR_RESET} Jalankan SEMUA Modul Berurutan (Automated Test Suite)
  {CLR_RED}[0]{CLR_RESET} Keluar
"""

    # If run in non-interactive / headless CI mode
    if not sys.stdin.isatty():
        print(f"{CLR_YELLOW}Mode non-interaktif terdeteksi: Menjalankan mode otomatis penuh.{CLR_RESET}")
        await run_task_group_demo()
        await run_actor_race_demo()
        await run_cancellation_demo()
        await run_pipeline_demo()
        print(f"\n{CLR_BOLD}{CLR_GREEN}✓ Seluruh modul simulasi Swift Concurrency berhasil diselesaikan!{CLR_RESET}\n")
        return

    while True:
        print(menu_text)
        try:
            choice = input(f"{CLR_BOLD}{CLR_WHITE}Pilihan [0-5]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{CLR_YELLOW}Keluar.{CLR_RESET}")
            break

        if choice == "1":
            await run_task_group_demo()
        elif choice == "2":
            await run_actor_race_demo()
        elif choice == "3":
            await run_cancellation_demo()
        elif choice == "4":
            await run_pipeline_demo()
        elif choice == "5":
            await run_task_group_demo()
            await run_actor_race_demo()
            await run_cancellation_demo()
            await run_pipeline_demo()
            print(f"\n{CLR_BOLD}{CLR_GREEN}✓ Seluruh simulasi selesai dengan sukses!{CLR_RESET}")
        elif choice == "0":
            print(f"\n{CLR_CYAN}Terima kasih telah mempelajari fondasi Swift Concurrency!{CLR_RESET}\n")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan pilih 0-5.{CLR_RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(interactive_menu())
    except KeyboardInterrupt:
        print(f"\n{CLR_RED}Eksekusi dihentikan oleh pengguna.{CLR_RESET}")
