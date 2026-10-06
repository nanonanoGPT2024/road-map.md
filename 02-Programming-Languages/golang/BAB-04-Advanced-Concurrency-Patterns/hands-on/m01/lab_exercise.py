#!/usr/bin/env python3
"""
Lab Exercise: Advanced Concurrency Patterns (Go Concurrency Emulation in Python)
BAB-04: Advanced Concurrency Patterns

Simulasi interaktif konsep konkurensi tingkat lanjut dari Go:
1. Worker Pool Pattern (Channel & WaitGroup semantics)
2. Fan-Out / Fan-In Pattern (Parallel processing & multiplexing)
3. Pipeline Pattern dengan Context Cancellation & Done Channel
4. Bounded Concurrency (Rate Limiting via Buffered Channel / Semaphore)
"""

import sys
import time
import random
import threading
import queue
from typing import List, Any

# ANSI Color Codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

def log_event(worker_id: str, message: str, color: str = Color.WHITE) -> None:
    now = time.strftime("%H:%M:%S")
    print(f"{Color.BOLD}[{now}]{Color.RESET} {color}[{worker_id}]{Color.RESET} {message}")


# ----------------------------------------------------------------------
# 1. WORKER POOL PATTERN (Go Channels & sync.WaitGroup equivalent)
# ----------------------------------------------------------------------
def demo_worker_pool() -> None:
    print(f"\n{Color.CYAN}{'='*60}")
    print(f" DEMO 1: WORKER POOL PATTERN (Go sync.WaitGroup & Jobs/Results)")
    print(f"{'='*60}{Color.RESET}")

    num_workers = 3
    num_jobs = 6
    jobs_queue: queue.Queue = queue.Queue()
    results_queue: queue.Queue = queue.Queue()

    def worker(worker_id: int) -> None:
        name = f"Worker-{worker_id}"
        log_event(name, "Goroutine dimulai, menunggu jobs...", Color.YELLOW)
        while True:
            try:
                job = jobs_queue.get(timeout=0.5)
            except queue.Empty:
                break
            
            log_event(name, f"Memproses Task #{job}...", Color.YELLOW)
            duration = random.uniform(0.2, 0.4)
            time.sleep(duration)
            result = f"Task #{job} selesai diproses oleh {name} ({duration*1000:.1f}ms)"
            results_queue.put(result)
            jobs_queue.task_done()
        
        log_event(name, "Goroutine selesai (wg.Done())", Color.GREEN)

    # Enqueue jobs
    for i in range(1, num_jobs + 1):
        jobs_queue.put(i)

    threads = []
    for wid in range(1, num_workers + 1):
        t = threading.Thread(target=worker, args=(wid,))
        t.start()
        threads.append(t)

    # Wait for all threads (Go sync.WaitGroup.Wait)
    for t in threads:
        t.join()

    print(f"\n{Color.BOLD}Hasil Worker Pool:{Color.RESET}")
    while not results_queue.empty():
        print(f"  -> {results_queue.get()}")


# ----------------------------------------------------------------------
# 2. FAN-OUT / FAN-IN PATTERN
# ----------------------------------------------------------------------
def demo_fan_out_fan_in() -> None:
    print(f"\n{Color.MAGENTA}{'='*60}")
    print(f" DEMO 2: FAN-OUT / FAN-IN PATTERN (Multiplexing Result Streams)")
    print(f"{'='*60}{Color.RESET}")

    numbers = [2, 3, 4, 5, 6, 7, 8, 9]
    input_chan: queue.Queue = queue.Queue()
    output_chan: queue.Queue = queue.Queue()

    for n in numbers:
        input_chan.put(n)

    def square_stage(stage_id: int) -> None:
        name = f"FanOut-Stage-{stage_id}"
        while True:
            try:
                num = input_chan.get(timeout=0.2)
            except queue.Empty:
                break
            time.sleep(random.uniform(0.1, 0.2))
            res = (num, num * num)
            log_event(name, f"Hitung kuadrat: {num}^2 = {num * num}", Color.MAGENTA)
            output_chan.put(res)
            input_chan.task_done()

    # Fan-Out: Pecah beban kerja ke 3 goroutines paralel
    fan_out_threads = [threading.Thread(target=square_stage, args=(i,)) for i in range(1, 4)]
    for t in fan_out_threads:
        t.start()

    # Fan-In: Kumpulkan hasil dari stream output ke satu consumer
    for t in fan_out_threads:
        t.join()

    results: List[Any] = []
    while not output_chan.empty():
        results.append(output_chan.get())

    print(f"\n{Color.BOLD}Hasil Fan-In Aggregation:{Color.RESET}")
    for original, sq in sorted(results, key=lambda x: x[0]):
        print(f"  -> Input: {original:<2} => Kuadrat: {sq:<3}")


# ----------------------------------------------------------------------
# 3. PIPELINE WITH CONTEXT CANCELLATION (Done Channel / context.Context)
# ----------------------------------------------------------------------
def demo_context_cancellation() -> None:
    print(f"\n{Color.RED}{'='*60}")
    print(f" DEMO 3: PIPELINE WITH CONTEXT CANCELLATION (ctx.Done())")
    print(f"{'='*60}{Color.RESET}")

    done_event = threading.Event()

    def generator_stage() -> None:
        val = 1
        while not done_event.is_set():
            log_event("Generator", f"Emisi data stream #{val}", Color.CYAN)
            time.sleep(0.15)
            val += 1
        log_event("Generator", "Menerima sinyal ctx.Done(), berhenti gracefully!", Color.RED)

    def worker_consumer() -> None:
        log_event("Supervisor", "Memantau pipeline selama 0.5 detik...", Color.WHITE)
        time.sleep(0.5)
        log_event("Supervisor", "TRIGGER: Batalkan konteks operasi (cancel())!", Color.RED)
        done_event.set()

    gen_thread = threading.Thread(target=generator_stage)
    sup_thread = threading.Thread(target=worker_consumer)

    gen_thread.start()
    sup_thread.start()

    sup_thread.join()
    gen_thread.join()
    print(f"{Color.GREEN}Pipeline ditutup bersih tanpa goroutine leak!{Color.RESET}")


# ----------------------------------------------------------------------
# 4. BOUNDED CONCURRENCY & RATE LIMITER (Buffered Channel / Semaphore)
# ----------------------------------------------------------------------
def demo_bounded_semaphore() -> None:
    print(f"\n{Color.BLUE}{'='*60}")
    print(f" DEMO 4: BOUNDED CONCURRENCY (Buffered Channel Semaphore - Max 2)")
    print(f"{'='*60}{Color.RESET}")

    max_concurrent = 2
    sem = threading.Semaphore(max_concurrent)

    def request_handler(req_id: int) -> None:
        name = f"Req-{req_id}"
        log_event(name, "Menunggu slot channel buffered...", Color.BLUE)
        with sem:
            log_event(name, f"Masuk critical section! (Slot terisi)", Color.GREEN)
            time.sleep(0.3)
            log_event(name, "Selesai, lepaskan slot token channel.", Color.YELLOW)

    req_threads = [threading.Thread(target=request_handler, args=(i,)) for i in range(1, 6)]
    for t in req_threads:
        t.start()
    for t in req_threads:
        t.join()


# ----------------------------------------------------------------------
# CLI MENU RUNNER
# ----------------------------------------------------------------------
def main() -> None:
    while True:
        print(f"\n{Color.BOLD}{Color.GREEN}=== GO ADVANCED CONCURRENCY LAB SIMULATOR (PYTHON 3) ==={Color.RESET}")
        print("1. Worker Pool Pattern (sync.WaitGroup)")
        print("2. Fan-Out / Fan-In Pattern")
        print("3. Pipeline & Context Cancellation (ctx.Done())")
        print("4. Bounded Concurrency Semaphore (Rate Limiting)")
        print("5. Jalankan Semua Skenario Sekaligus")
        print("6. Keluar")
        
        try:
            choice = input(f"{Color.CYAN}Pilih opsi [1-6]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            demo_worker_pool()
        elif choice == "2":
            demo_fan_out_fan_in()
        elif choice == "3":
            demo_context_cancellation()
        elif choice == "4":
            demo_bounded_semaphore()
        elif choice == "5":
            demo_worker_pool()
            demo_fan_out_fan_in()
            demo_context_cancellation()
            demo_bounded_semaphore()
        elif choice == "6":
            print(f"{Color.GREEN}Terima kasih telah menggunakan lab simulator concurrency.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}")

if __name__ == "__main__":
    # If run in non-interactive / automated check mode
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        demo_worker_pool()
        demo_fan_out_fan_in()
        demo_context_cancellation()
        demo_bounded_semaphore()
    else:
        main()
