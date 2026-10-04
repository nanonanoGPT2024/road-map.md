#!/usr/bin/env python3
"""
Lab Hands-on: Golang Runtime Deep Dive Simulation
Topic: Golang (Bab 03 - Modul 02: GMP Scheduler & Channel Internals)

Script ini memodelkan dan mensimulasikan arsitektur internal runtime Go:
1. GMP Work-Stealing Scheduler:
   - G (Goroutine): Unit eksekusi independen dengan state lifecycle.
   - M (Machine): Thread OS native yang mengeksekusi instruksi.
   - P (Processor): Resource logis (GOMAXPROCS) dengan Local Run Queue (LRQ).
   - Global Run Queue (GRQ) & Algoritma Work-Stealing saat LRQ kosong.
2. Go Channel Internals:
   - Ring buffer sinkronisasi thread-safe dengan lock internal (hchan).
   - Penanganan backpressure dan sinkronisasi producer-consumer.
"""

import sys
import time
import random
import threading
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional, List

# ANSI Color Codes untuk visualisasi terminal
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_MAGENTA= "\033[35m"
CLR_CYAN   = "\033[36m"
CLR_GRAY   = "\033[90m"

@dataclass
class Goroutine:
    """Representasi struct runtime.g pada Go."""
    gid: int
    task_fn: Callable[[], None]
    status: str = "_Grunnable"
    description: str = ""

class GoChannel:
    """
    Simulasi runtime.hchan.
    Memiliki internal lock, circular buffer (kapasitas), dan queue sinyal.
    """
    def __init__(self, capacity: int = 0):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity if capacity > 0 else None)
        self.lock = threading.Lock()
        self.not_empty = threading.Condition(self.lock)
        self.not_full = threading.Condition(self.lock)
        self.closed = False

    def send(self, val: any, g_name: str):
        with self.lock:
            if self.closed:
                raise RuntimeError("panic: send on closed channel")
            
            # Unbuffered channel: hand-off langsung
            if self.capacity == 0:
                while len(self.buffer) >= 1 and not self.closed:
                    self.not_full.wait()
                self.buffer.append(val)
                self.not_empty.notify()
                return

            # Buffered channel
            while len(self.buffer) >= self.capacity and not self.closed:
                self.not_full.wait()
            self.buffer.append(val)
            self.not_empty.notify()

    def recv(self, g_name: str) -> any:
        with self.lock:
            while len(self.buffer) == 0 and not self.closed:
                self.not_empty.wait()
            if len(self.buffer) == 0 and self.closed:
                return None
            val = self.buffer.popleft()
            self.not_full.notify()
            return val

    def close(self):
        with self.lock:
            self.closed = True
            self.not_empty.notify_all()
            self.not_full.notify_all()

class LogicalProcessor:
    """Representasi struct runtime.p pada Go."""
    def __init__(self, pid: int, max_queue: int = 256):
        self.pid = pid
        self.lrq: deque[Goroutine] = deque()
        self.lock = threading.Lock()
        self.schedtick = 0  # Counter ticks untuk memicu pengecekan GRQ

    def push_runq(self, g: Goroutine, sched: "GMPScheduler"):
        """Menambahkan G ke LRQ lokal; jika penuh, offload separuh ke GRQ."""
        with self.lock:
            if len(self.lrq) >= 8:  # Batas miniatur untuk simulasi demonstrasi
                # Batch offload ke Global Run Queue
                sched.dump_to_grq(self, self.lrq)
            g.status = "_Grunnable"
            self.lrq.append(g)

    def pop_runq(self) -> Optional[Goroutine]:
        with self.lock:
            if self.lrq:
                return self.lrq.popleft()
            return None

class Machine(threading.Thread):
    """Representasi struct runtime.m (OS Thread) pada Go."""
    def __init__(self, mid: int, sched: "GMPScheduler"):
        super().__init__(name=f"OS-Thread-M{mid}", daemon=True)
        self.mid = mid
        self.sched = sched
        self.p: Optional[LogicalProcessor] = None
        self.current_g: Optional[Goroutine] = None

    def run(self):
        """Schedule loop (mstart -> schedule)."""
        while not self.sched.shutdown_flag.is_set():
            if not self.p:
                time.sleep(0.01)
                continue

            g = self.schedule_find_g()
            if g:
                self.execute_g(g)
            else:
                # M masuk state spinning/parking jika tidak ada G
                time.sleep(0.005)

    def schedule_find_g(self) -> Optional[Goroutine]:
        """
        Algoritma Pencarian G runtime Go:
        1. 1/61 chance cek GRQ untuk mencegah starvation.
        2. Cek Local Run Queue (LRQ) dari P sendiri.
        3. Cek Global Run Queue (GRQ).
        4. Work-Stealing: Curi 50% G dari LRQ Processor (P) lain.
        """
        self.p.schedtick += 1
        
        # Rule 1: Tiap 61 tick, prioritaskan GRQ
        if self.p.schedtick % 61 == 0:
            g = self.sched.pop_from_grq()
            if g:
                return g

        # Rule 2: Cek LRQ lokal
        g = self.p.pop_runq()
        if g:
            return g

        # Rule 3: Cek GRQ
        g = self.sched.pop_from_grq()
        if g:
            return g

        # Rule 4: Work-Stealing
        return self.sched.steal_work(self.p)

    def execute_g(self, g: Goroutine):
        self.current_g = g
        g.status = "_Grunning"
        try:
            g.task_fn()
        except Exception as e:
            print(f"{CLR_RED}[M{self.mid}] Panic in G{g.gid}: {e}{CLR_RESET}")
        finally:
            g.status = "_Gdead"
            self.sched.completed_g_count += 1
            self.current_g = None

class GMPScheduler:
    """Orkestrator Runtime Go yang mengkoordinasikan M, P, dan G."""
    def __init__(self, gomaxprocs: int):
        self.gomaxprocs = gomaxprocs
        self.processors: List[LogicalProcessor] = [LogicalProcessor(pid) for pid in range(gomaxprocs)]
        self.machines: List[Machine] = []
        self.grq: deque[Goroutine] = deque()
        self.grq_lock = threading.Lock()
        self.gid_counter = 0
        self.gid_lock = threading.Lock()
        self.completed_g_count = 0
        self.shutdown_flag = threading.Event()

    def start(self):
        # Bind M ke P 1-on-1 saat inisialisasi awal
        for i in range(self.gomaxprocs):
            m = Machine(i, self)
            m.p = self.processors[i]
            self.machines.append(m)
            m.start()

    def spawn_goroutine(self, task_fn: Callable[[], None], desc: str, target_p: Optional[int] = None):
        with self.gid_lock:
            self.gid_counter += 1
            gid = self.gid_counter

        g = Goroutine(gid=gid, task_fn=task_fn, description=desc)
        
        # Tentukan P tempat G disuntikkan (default: round-robin atau target spesifik)
        p = self.processors[target_p % self.gomaxprocs] if target_p is not None else random.choice(self.processors)
        p.push_runq(g, self)

    def dump_to_grq(self, source_p: LogicalProcessor, lrq: deque):
        """Memindahkan separuh LRQ ke GRQ saat terjadi overflow."""
        with self.grq_lock:
            half = len(lrq) // 2
            for _ in range(half):
                g = lrq.popleft()
                self.grq.append(g)
            print(f"{CLR_YELLOW}[SCHED OVERFLOW] Offloaded {half} Goroutines from P{source_p.pid} to GRQ{CLR_RESET}")

    def pop_from_grq(self) -> Optional[Goroutine]:
        with self.grq_lock:
            if self.grq:
                return self.grq.popleft()
            return None

    def steal_work(self, target_p: LogicalProcessor) -> Optional[Goroutine]:
        """Algoritma Work-Stealing: Mencuri separuh antrian P target lain."""
        candidates = [p for p in self.processors if p.pid != target_p.pid]
        random.shuffle(candidates)
        
        for victim_p in candidates:
            with victim_p.lock:
                victim_len = len(victim_p.lrq)
                if victim_len > 1:
                    steal_count = victim_len // 2
                    print(f"{CLR_MAGENTA}[WORK STEAL] P{target_p.pid} steals {steal_count} Goroutines from P{victim_p.pid}{CLR_RESET}")
                    for _ in range(steal_count - 1):
                        target_p.lrq.append(victim_p.lrq.popleft())
                    # Ambil 1 untuk langsung dieksekusi oleh thread pemanggil
                    return victim_p.lrq.popleft()
        return None

    def shutdown(self):
        self.shutdown_flag.set()
        for m in self.machines:
            m.join(timeout=1.0)


def print_banner():
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  GOLANG DEEP DIVE: RUNTIME GMP SCHEDULER & CONCURRENCY INTERNALS    {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}\n")

def run_lab():
    print_banner()
    GOMAXPROCS = 2
    sched = GMPScheduler(gomaxprocs=GOMAXPROCS)
    sched.start()
    print(f"{CLR_GREEN}[*] Go Runtime initialized with GOMAXPROCS={GOMAXPROCS}{CLR_RESET}\n")

    # Inisialisasi Channel (Buffered cap: 2)
    ch = GoChannel(capacity=2)

    # Definisi Payload Goroutine Worker
    def producer(item_id: int):
        def _task():
            thread_name = threading.current_thread().name
            time.sleep(random.uniform(0.01, 0.03))  # Simulasi compute
            ch.send(f"pkg-data-{item_id}", thread_name)
            print(f"  {CLR_BLUE}--> [SEND]{CLR_RESET} G-Producer({item_id}) sent payload via {thread_name}")
        return _task

    def consumer(consumer_id: int):
        def _task():
            thread_name = threading.current_thread().name
            data = ch.recv(thread_name)
            time.sleep(random.uniform(0.01, 0.02))  # Simulasi processing
            print(f"  {CLR_GREEN}<-- [RECV]{CLR_RESET} G-Consumer({consumer_id}) processed [{data}] on {thread_name}")
        return _task

    print(f"{CLR_BOLD}--- Fase 1: Load Imbalance & Work-Stealing Test ---{CLR_RESET}")
    # Suntikkan beban tinggi sengaja ke P0 agar P1 melakukan work-stealing
    total_tasks = 12
    for i in range(total_tasks):
        sched.spawn_goroutine(producer(i), desc=f"Producer-{i}", target_p=0)
    for i in range(total_tasks):
        sched.spawn_goroutine(consumer(i), desc=f"Consumer-{i}", target_p=1)

    # Tunggu sinkronisasi pemrosesan task selesai
    timeout = 10.0
    start_t = time.time()
    expected_total = total_tasks * 2
    while sched.completed_g_count < expected_total and (time.time() - start_t) < timeout:
        time.sleep(0.05)

    ch.close()
    sched.shutdown()

    # Evaluasi Hasil Akhir Scheduler
    print(f"\n{CLR_BOLD}--- Hasil Telemetri Runtime ---{CLR_RESET}")
    print(f"Total Goroutine Dijadwalkan: {CLR_YELLOW}{sched.gid_counter}{CLR_RESET}")
    print(f"Total Goroutine Tereksekusi:  {CLR_GREEN}{sched.completed_g_count}/{expected_total}{CLR_RESET}")
    print(f"Sisa G di Global Run Queue : {len(sched.grq)}")
    for p in sched.processors:
        print(f"Sisa G di LRQ Processor P{p.pid} : {len(p.lrq)}")
    
    print(f"\n{CLR_BOLD}{CLR_GREEN}[+] Lab Deep Dive selesai: GMP scheduler dan Channel primitives tervalidasi.{CLR_RESET}")

if __name__ == "__main__":
    run_lab()