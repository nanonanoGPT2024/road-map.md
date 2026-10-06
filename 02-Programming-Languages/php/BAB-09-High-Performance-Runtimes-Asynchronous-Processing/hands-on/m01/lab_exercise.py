#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Arsitektur PHP High-Performance Runtime & Asynchronous Processing
Topik: BAB-09 High-Performance Runtimes & Asynchronous Processing

Fitur Simulasi:
1. PHP-FPM (Share-Nothing Model) vs Persistent Runtime (RoadRunner / Swoole)
2. Cooperative Multitasking / Fiber Event Loop Simulator (PHP 8.1+ Fibers / Amp / ReactPHP)
3. Memory Leak Hazard Simulator pada Long-Running PHP Worker
4. Worker Pool & IPC (Inter-Process Communication) Request Dispatcher
"""

import sys
import time
import random
import dataclasses
from typing import List, Dict, Generator, Any

# ANSI Color Codes untuk visualisasi terminal
class Colors:
    HEADER    = '\033[95m'
    BLUE      = '\033[94m'
    CYAN      = '\033[96m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    RED       = '\033[91m'
    BOLD      = '\033[1m'
    DIM       = '\033[2m'
    UNDERLINE = '\033[4m'
    RESET     = '\033[0m'

def print_header(title: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN} {title} {Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.RESET}")

def print_step(step: str, desc: str) -> None:
    print(f"{Colors.BOLD}{Colors.YELLOW}[+] {step}:{Colors.RESET} {desc}")

# -----------------------------------------------------------------------------
# 1. SIMULASI: PHP-FPM (Share-Nothing) vs Persistent Runtime (Swoole / RoadRunner)
# -----------------------------------------------------------------------------
def simulate_runtimes_comparison():
    print_header("SIMULASI 1: Siklus Hidup PHP-FPM vs Persistent Runtime (RoadRunner/Swoole)")
    print(f"{Colors.DIM}Membandingkan lifecycle bootstrap framework (misal Laravel/Symfony) per-request.{Colors.RESET}\n")

    requests = [f"/api/v1/orders/{i}" for i in range(1, 5)]

    # --- Skenario A: PHP-FPM ---
    print(f"{Colors.BOLD}{Colors.RED}--- Mode 1: Traditional PHP-FPM (Share-Nothing Architecture) ---{Colors.RESET}")
    total_fpm_time = 0.0

    for req in requests:
        start_req = time.perf_counter()
        print(f"  {Colors.BOLD}Incoming HTTP:{Colors.RESET} {req}")
        
        # PHP-FPM: Init Zend Engine & opcode cache check
        time.sleep(0.02)
        print(f"    {Colors.DIM}[FPM]{Colors.RESET} 1. Bootstrap Kernel & Load 300+ Composer classes...")
        
        # Inisialisasi Service Container, DB Pool baru
        time.sleep(0.03)
        print(f"    {Colors.DIM}[FPM]{Colors.RESET} 2. Connect DB (Handshake TCP), Load Config...")
        
        # Eksekusi Controller / Business Logic
        time.sleep(0.01)
        print(f"    {Colors.DIM}[FPM]{Colors.RESET} 3. Execute Controller & Render Response HTTP 200")
        
        # Tear-down & Destroy Everything
        time.sleep(0.01)
        print(f"    {Colors.DIM}[FPM]{Colors.RESET} 4. Zend Engine cleanup: Destroy global state, free all RAM")
        
        req_duration = (time.perf_counter() - start_req) * 1000
        total_fpm_time += req_duration
        print(f"    {Colors.YELLOW}-> Request Latency: {req_duration:.2f} ms (Overhead Bootstrap: ~70%){Colors.RESET}\n")

    # --- Skenario B: Persistent Runtime ---
    print(f"{Colors.BOLD}{Colors.GREEN}--- Mode 2: Persistent Worker Runtime (Swoole / RoadRunner / FrankenPHP) ---{Colors.RESET}")
    print(f"  {Colors.GREEN}[Worker Startup]{Colors.RESET} Bootstrap Framework 1x saat CLI boot...")
    time.sleep(0.05)
    print(f"  {Colors.GREEN}[Worker Startup]{Colors.RESET} Pre-warm In-memory Cache & Persistent DB Connection Pool ready.\n")
    
    total_persistent_time = 0.0
    for req in requests:
        start_req = time.perf_counter()
        print(f"  {Colors.BOLD}Incoming HTTP:{Colors.RESET} {req}")
        
        # No re-bootstrap, memory state persistent, hanya handle request payload
        time.sleep(0.01)
        print(f"    {Colors.CYAN}[Worker]{Colors.RESET} Direct Event Dispatch -> Controller -> HTTP 200")
        print(f"    {Colors.CYAN}[Worker]{Colors.RESET} Reset Request-Scoped Container (Worker tetap aktif di RAM)")
        
        req_duration = (time.perf_counter() - start_req) * 1000
        total_persistent_time += req_duration
        print(f"    {Colors.GREEN}-> Request Latency: {req_duration:.2f} ms (Pure Business Logic!){Colors.RESET}\n")

    speedup = total_fpm_time / max(total_persistent_time, 0.001)
    print(f"{Colors.BOLD}Summary Performance:{Colors.RESET}")
    print(f"  PHP-FPM Cumulative Time   : {Colors.RED}{total_fpm_time:.2f} ms{Colors.RESET}")
    print(f"  Persistent Cumulative Time: {Colors.GREEN}{total_persistent_time:.2f} ms{Colors.RESET}")
    print(f"  Throughput Efficiency Gain: {Colors.BOLD}{Colors.GREEN}{speedup:.2f}x lebih cepat{Colors.RESET}\n")

# -----------------------------------------------------------------------------
# 2. SIMULASI: PHP 8.1+ Fibers & Cooperative Event-Loop Coroutines
# -----------------------------------------------------------------------------
@dataclasses.dataclass
class SimulatedFiber:
    id: int
    name: str
    generator: Generator[str, None, None]
    finished: bool = False

def simulate_fibers_event_loop():
    print_header("SIMULASI 2: Cooperative Multitasking dengan Fiber / Coroutine")
    print(f"{Colors.DIM}Simulasi mekanisme Fiber::suspend() dan Fiber::resume() dalam Single-Threaded Event Loop.{Colors.RESET}\n")

    def async_http_call(task_name: str, delay_ticks: int):
        yield f"Mulai HTTP I/O non-blocking ke {task_name}"
        for i in range(1, delay_ticks + 1):
            # Fiber::suspend() melepaskan eksekusi CPU ke event loop sambil menunggu socket
            yield f"Waiting socket I/O ({i}/{delay_ticks}) -> Fiber::suspend()"
        yield f"Socket data siap, parsing response -> Fiber selesai."

    # Membuat daftar Fiber
    tasks = [
        SimulatedFiber(1, "Payment Gateway API", async_http_call("PaymentAPI", 3)),
        SimulatedFiber(2, "Inventory Service API", async_http_call("InventoryAPI", 2)),
        SimulatedFiber(3, "Notification Webhook", async_http_call("WebhookNotify", 4)),
    ]

    print(f"{Colors.BOLD}{Colors.CYAN}Event Loop Dijalankan (Single Thread, Cooperative Multiplexing):{Colors.RESET}")
    cycle = 1
    while any(not t.finished for t in tasks):
        print(f"\n{Colors.BOLD}[Tick Loop {cycle}]{Colors.RESET}")
        for task in tasks:
            if not task.finished:
                try:
                    state = next(task.generator)
                    print(f"  [{Colors.GREEN}Fiber-{task.id} {task.name}{Colors.RESET}] -> {state}")
                except StopIteration:
                    task.finished = True
                    print(f"  [{Colors.BLUE}Fiber-{task.id} {task.name}{Colors.RESET}] -> {Colors.BOLD}COMPLETED (Terminated){Colors.RESET}")
        cycle += 1
        time.sleep(0.04)

    print(f"\n{Colors.GREEN}[✓] Semua Fiber berhasil dieksekusi secara non-blocking tanpa thread pool overhead!{Colors.RESET}\n")

# -----------------------------------------------------------------------------
# 3. SIMULASI: Bahaya Memory Leak pada Long-Running PHP Worker
# -----------------------------------------------------------------------------
def simulate_memory_leak_hazard():
    print_header("SIMULASI 3: Analisis Bahaya Memory Leak (Static State Retention)")
    print(f"{Colors.DIM}Pada PHP-FPM, memory_get_usage() selalu bersih per-request.{Colors.RESET}")
    print(f"{Colors.DIM}Pada Worker runtime, singleton/static property yang lupa dibersihkan menyebabkan OOM.{Colors.RESET}\n")

    class VulnerableRuntimeContext:
        def __init__(self):
            # Simulasi static array yang lupa di-reset per request
            self.static_registry: List[Dict[str, Any]] = []
            self.base_memory_mb = 28.0

        def handle_request(self, req_id: int) -> float:
            # Bug umum: mencatat user session ke static memory tanpa batas TTL/cleanup
            mock_payload = {
                "id": req_id,
                "session_data": "x" * 1024 * 512, # 512 KB per request
                "timestamp": time.time()
            }
            self.static_registry.append(mock_payload)
            current_mem = self.base_memory_mb + (len(self.static_registry) * 0.512)
            return current_mem

    runtime = VulnerableRuntimeContext()
    max_limit_mb = 35.0

    print(f"{Colors.BOLD}Memulai simulasi 15 request berulang ke 1 persistent worker:{Colors.RESET}")
    print(f"Memory Limit Worker (php.ini): {Colors.RED}{max_limit_mb:.1f} MB{Colors.RESET}\n")

    for req_id in range(1, 16):
        mem = runtime.handle_request(req_id)
        pct = min(100, int((mem / max_limit_mb) * 100))
        bar_len = 25
        filled = int((pct / 100) * bar_len)
        bar = f"{'█' * filled}{'-' * (bar_len - filled)}"

        status_color = Colors.GREEN if pct < 70 else (Colors.YELLOW if pct < 90 else Colors.RED)
        print(f"Request #{req_id:02d} | RAM: {mem:.2f} MB [{status_color}{bar}{Colors.RESET}] {pct}%")

        if mem >= max_limit_mb:
            print(f"\n{Colors.BOLD}{Colors.RED}[FATAL ERROR]: Allowed memory size of {max_limit_mb} MB exhausted!{Colors.RESET}")
            print(f"{Colors.YELLOW}[Mitigasi Arsitektur]:{Colors.RESET}")
            print(f"  1. Hindari stateful static property di Controller/Services.")
            print(f"  2. Konfigurasikan max_requests / worker recycle limit (misal RoadRunner 'max_jobs: 1000').")
            print(f"  3. Panggil garbage collector explisit dan reset RequestScope container.")
            return

        time.sleep(0.03)

# -----------------------------------------------------------------------------
# 4. MENU UTAMA INTERAKTIF
# -----------------------------------------------------------------------------
def display_menu():
    print(f"\n{Colors.BOLD}{Colors.CYAN}--- PILIHAN MODUL HANDS-ON BAB 09 ---{Colors.RESET}")
    print(f"  {Colors.BOLD}1.{Colors.RESET} Jalankan Perbandingan Lifecycle (PHP-FPM vs RoadRunner/Swoole)")
    print(f"  {Colors.BOLD}2.{Colors.RESET} Jalankan Simulasi Event Loop & Fiber Non-Blocking I/O")
    print(f"  {Colors.BOLD}3.{Colors.RESET} Jalankan Eksperimen Memory Leak & Worker Exhaustion")
    print(f"  {Colors.BOLD}4.{Colors.RESET} Jalankan Seluruh Demonstrasi Secara Sekuensial")
    print(f"  {Colors.BOLD}0.{Colors.RESET} Keluar (Exit)")

def main():
    print_header("KURSUS PHP LANJUTAN: ARSITEKTUR RUNTIME & ASYNC PROCESSING")
    print(f"{Colors.BOLD}Modul 01: Fondasi Teknis PHP High-Performance & Asynchronous Engine{Colors.RESET}")

    # Mode non-interaktif otomatis jika dieksekusi via automation test/pipe
    if not sys.stdin.isatty():
        print(f"\n{Colors.DIM}[Auto-Run Mode detected: Menjalankan seluruh simulasi]{Colors.RESET}")
        simulate_runtimes_comparison()
        simulate_fibers_event_loop()
        simulate_memory_leak_hazard()
        print(f"\n{Colors.GREEN}{Colors.BOLD}Semua skenario simulasi sukses dijalankan!{Colors.RESET}\n")
        return

    while True:
        display_menu()
        try:
            choice = input(f"\n{Colors.BOLD}Pilih nomor skenario (0-4): {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}Keluar dari lab.{Colors.RESET}")
            break

        if choice == '1':
            simulate_runtimes_comparison()
        elif choice == '2':
            simulate_fibers_event_loop()
        elif choice == '3':
            simulate_memory_leak_hazard()
        elif choice == '4':
            simulate_runtimes_comparison()
            simulate_fibers_event_loop()
            simulate_memory_leak_hazard()
        elif choice in ('0', 'q', 'exit'):
            print(f"{Colors.GREEN}Sesi lab selesai. Terima kasih.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan pilih 0-4.{Colors.RESET}")

if __name__ == '__main__':
    main()
