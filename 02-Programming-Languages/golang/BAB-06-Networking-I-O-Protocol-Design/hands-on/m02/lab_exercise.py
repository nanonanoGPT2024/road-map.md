#!/usr/bin/env python3
"""
Lab Hands-on: Go Runtime Architecture Deep Dive (GMP Scheduler & CSP Channels)
Topik: Golang Concurrency Internals (Bab 06 - Modul 02 Deep Dive)

Skrip ini mengemulasikan secara presisi mekanisme runtime internal Go:
1. Model Scheduler M:N (GMP: Goroutine, Machine/Thread, Processor/Context).
2. Work-stealing queue algorithm (Local Run Queue vs Global Run Queue).
3. Mekanisme Starvation Prevention (pengecekan GRQ berkala setiap tick ke-61).
4. Primitif Komunikasi CSP (Go Channel) dengan antrean penantian (sendq & recvq).
"""

import sys
import time
import random
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, List, Optional

# ANSI Color formatting
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_CYAN = "\033[36m"


class GState(Enum):
    Gidle = auto()
    Grunnable = auto()
    Grunning = auto()
    Gwaiting = auto()
    Gdead = auto()


@dataclass
class Goroutine:
    gid: int
    fn: Callable[..., Any]
    args: tuple = ()
    state: GState = GState.Gidle
    bound_p: Optional[int] = None

    def execute(self) -> Any:
        self.state = GState.Grunning
        res = self.fn(*self.args)
        self.state = GState.Gdead
        return res


class GoChannel:
    """
    Simulasi CSP channel Go (`hchan`).
    Memiliki buffer lingkaran (circular buffer), sendq (sudog), dan recvq (sudog).
    """
    def __init__(self, capacity: int = 0):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity if capacity > 0 else None)
        self.lock = threading.Lock()
        self.not_full = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)
        self.closed = False

    def send(self, val: Any, gid: int) -> None:
        with self.lock:
            if self.closed:
                raise RuntimeError(f"panic: send on closed channel (G{gid})")
            
            if self.capacity == 0:
                # Unbuffered channel: hand-off sinkron
                while len(self.buffer) >= 1:
                    self.not_full.wait()
                self.buffer.append(val)
                self.not_empty.notify()
                while len(self.buffer) > 0 and not self.closed:
                    self.not_full.wait()
            else:
                # Buffered channel
                while len(self.buffer) >= self.capacity:
                    self.not_full.wait()
                self.buffer.append(val)
                self.not_empty.notify()

    def recv(self, gid: int) -> Optional[Any]:
        with self.lock:
            while len(self.buffer) == 0:
                if self.closed:
                    return None
                self.not_empty.wait()
            
            val = self.buffer.popleft()
            self.not_full.notify()
            return val

    def close(self) -> None:
        with self.lock:
            self.closed = True
            self.not_full.notify_all()
            self.not_empty.notify_all()


class Processor:
    """
    Abstraksi 'P' dalam GMP Go: Merepresentasikan logical context execution.
    Menangani Local Run Queue (LRQ) berkapasitas tetap (di Go asli max 256).
    """
    def __init__(self, pid: int, max_lrq: int = 4):
        self.pid = pid
        self.max_lrq = max_lrq
        self.lrq: deque[Goroutine] = deque()
        self.lock = threading.Lock()
        self.sched_ticks = 0

    def push_runq(self, g: Goroutine, grq_ref: deque, grq_lock: threading.Lock) -> bool:
        """Menambahkan G ke runq lokal; jika penuh, offload separuh ke GRQ."""
        with self.lock:
            if len(self.lrq) < self.max_lrq:
                g.state = GState.Grunnable
                g.bound_p = self.pid
                self.lrq.append(g)
                return True
        
        # Batch offload ke Global Run Queue (GRQ) saat LRQ overflow
        with grq_lock:
            with self.lock:
                half = len(self.lrq) // 2
                for _ in range(half):
                    offloaded_g = self.lrq.popleft()
                    grq_ref.append(offloaded_g)
                g.state = GState.Grunnable
                g.bound_p = None
                grq_ref.append(g)
        return False


class Machine(threading.Thread):
    """
    Abstraksi 'M' dalam GMP Go: Thread sistem operasi aktual yang mengeksekusi G.
    """
    def __init__(self, mid: int, sched: "GMPScheduler"):
        super().__init__(daemon=True)
        self.mid = mid
        self.sched = sched
        self.current_p: Optional[Processor] = None
        self.current_g: Optional[Goroutine] = None
        self.running = True

    def run(self) -> None:
        while self.running and not self.sched.stop_event.is_set():
            if self.current_p is None:
                self.current_p = self.sched.acquire_idle_p()
                if self.current_p is None:
                    time.sleep(0.005)
                    continue

            # Schedule: Cari G runnable
            g = self.sched.schedule(self.current_p)
            if g is not None:
                self.current_g = g
                try:
                    g.execute()
                except Exception as err:
                    print(f"{C_RED}[M{self.mid}] G{g.gid} Panic: {err}{C_RESET}")
                finally:
                    self.current_g = None
                    self.sched.notify_g_completed()
            else:
                # Tidak ada kerjaan, sleep sejenak
                time.sleep(0.002)

    def stop(self) -> None:
        self.running = False


class GMPScheduler:
    """
    Runtime Coordinator yang mengimplementasikan Go scheduler invariants:
    1. Local Run Queue check (priority).
    2. Periodic GRQ check (tick % 61 == 0) untuk mencegah starvation global tasks.
    3. Work-Stealing dari P lain jika LRQ kosong.
    """
    def __init__(self, num_p: int, num_m: int):
        self.num_p = num_p
        self.num_m = num_m
        self.processors = [Processor(pid=i) for i in range(num_p)]
        self.grq: deque[Goroutine] = deque()
        self.grq_lock = threading.Lock()
        self.idle_p_queue = deque(self.processors)
        self.p_lock = threading.Lock()
        self.machines: List[Machine] = []
        self.stop_event = threading.Event()
        self.active_g_count = 0
        self.g_counter = 0
        self.count_lock = threading.Lock()
        self.all_completed_cond = threading.Condition(self.count_lock)

    def acquire_idle_p(self) -> Optional[Processor]:
        with self.p_lock:
            if self.idle_p_queue:
                return self.idle_p_queue.popleft()
            return None

    def release_p(self, p: Processor) -> None:
        with self.p_lock:
            self.idle_p_queue.append(p)

    def spawn(self, fn: Callable, *args) -> Goroutine:
        with self.count_lock:
            self.g_counter += 1
            gid = self.g_counter
            self.active_g_count += 1
        
        g = Goroutine(gid=gid, fn=fn, args=args, state=GState.Grunnable)
        
        # Letakkan pada P yang paling tidak sibuk
        p_target = min(self.processors, key=lambda p: len(p.lrq))
        p_target.push_runq(g, self.grq, self.grq_lock)
        return g

    def notify_g_completed(self) -> None:
        with self.count_lock:
            self.active_g_count -= 1
            if self.active_g_count <= 0:
                self.all_completed_cond.notify_all()

    def schedule(self, p: Processor) -> Optional[Goroutine]:
        """Algoritma pencarian runnable Goroutine Go runtime."""
        p.sched_ticks += 1

        # 1. 1/61 chance: Cek GRQ untuk cegah starvation
        if p.sched_ticks % 61 == 0:
            with self.grq_lock:
                if self.grq:
                    g = self.grq.popleft()
                    return g

        # 2. Ambil dari LRQ lokal
        with p.lock:
            if p.lrq:
                return p.lrq.popleft()

        # 3. Ambil dari GRQ biasa jika LRQ lokal kosong
        with self.grq_lock:
            if self.grq:
                return self.grq.popleft()

        # 4. Work-Stealing: Curi 50% G dari LRQ Processor lain
        return self._steal_work(p)

    def _steal_work(self, active_p: Processor) -> Optional[Goroutine]:
        targets = [p for p in self.processors if p.pid != active_p.pid]
        random.shuffle(targets)

        for victim in targets:
            with victim.lock:
                victim_len = len(victim.lrq)
                if victim_len > 1:
                    # Curi separuh dari task victim
                    stolen_count = victim_len // 2
                    stolen_batch = [victim.lrq.popleft() for _ in range(stolen_count)]
                    print(f"{C_YELLOW}  [Work-Stealing]{C_RESET} P{active_p.pid} mencuri {stolen_count} G dari P{victim.pid}")
                    with active_p.lock:
                        for g in stolen_batch[1:]:
                            g.bound_p = active_p.pid
                            active_p.lrq.append(g)
                    g_to_run = stolen_batch[0]
                    g_to_run.bound_p = active_p.pid
                    return g_to_run
        return None

    def start(self) -> None:
        for i in range(self.num_m):
            m = Machine(mid=i, sched=self)
            self.machines.append(m)
            m.start()

    def wait_all(self, timeout: float = 5.0) -> None:
        with self.count_lock:
            if self.active_g_count > 0:
                self.all_completed_cond.wait(timeout=timeout)

    def shutdown(self) -> None:
        self.stop_event.set()
        for m in self.machines:
            m.stop()
        for m in self.machines:
            m.join(timeout=0.2)


# =====================================================================
# LAB EXERCISE EXECUTION WORKFLOW
# =====================================================================

def lab_worker_heavy(gid_tag: str, duration: float) -> None:
    """Simulasi computational goroutine."""
    t_start = time.time()
    # Emulasi beban CPU
    while time.time() - t_start < duration:
        _ = 42 * 42
    print(f"  {C_GREEN}✔{C_RESET} Goroutine [{gid_tag}] selesai ({duration*1000:.1f}ms).")


def lab_producer(ch: GoChannel, items: int) -> None:
    for i in range(items):
        time.sleep(0.005)
        ch.send(f"payload-{i}", gid=100)
    ch.close()


def lab_consumer(ch: GoChannel, cid: int) -> None:
    while True:
        val = ch.recv(gid=200 + cid)
        if val is None:
            break
        print(f"  {C_CYAN}⇄{C_RESET} Consumer {cid} memproses: {val}")


def main() -> None:
    print(f"{C_BOLD}{C_MAGENTA}==============================================================={C_RESET}")
    print(f"{C_BOLD}{C_MAGENTA}  LAB HANDS-ON: GO RUNTIME INTERNAL SIMULATION (GMP & CSP)     {C_RESET}")
    print(f"{C_BOLD}{C_MAGENTA}==============================================================={C_RESET}\n")

    num_p = 2
    num_m = 2
    print(f"{C_BLUE}[INIT]{C_RESET} Menginisialisasi Go Runtime Environment...")
    print(f"       GOMAXPROCS (P) = {num_p} | OS Threads (M) = {num_m}\n")

    scheduler = GMPScheduler(num_p=num_p, num_m=num_m)
    scheduler.start()

    print(f"{C_BOLD}--- SKENARIO 1: Work-Stealing Scheduling Invariant ---{C_RESET}")
    # Spawn tasks secara imbalance untuk memicu Work-Stealing
    for i in range(8):
        scheduler.spawn(lab_worker_heavy, f"Task-{i}", 0.02)

    scheduler.wait_all(timeout=2.0)
    print(f"{C_GREEN}[STATUS]{C_RESET} Skenario 1 Work-Stealing berhasil diuji.\n")

    print(f"{C_BOLD}--- SKENARIO 2: CSP Unbuffered/Buffered Channel Sync ---{C_RESET}")
    ch = GoChannel(capacity=2)
    # Spawn 1 Producer dan 2 Consumer concurrently
    scheduler.spawn(lab_producer, ch, 6)
    scheduler.spawn(lab_consumer, ch, 1)
    scheduler.spawn(lab_consumer, ch, 2)

    scheduler.wait_all(timeout=3.0)
    print(f"{C_GREEN}[STATUS]{C_RESET} Skenario 2 Channel Synchronization selesai dieksekusi.\n")

    # Metrics Summary
    print(f"{C_BOLD}--- RUNTIME SUMMARY ---{C_RESET}")
    for p in scheduler.processors:
        print(f"  P{p.pid} Total Sched Ticks: {p.sched_ticks} | Sisa LRQ: {len(p.lrq)}")
    print(f"  Global Run Queue (GRQ) Sisa: {len(scheduler.grq)}")

    print(f"\n{C_BLUE}[SHUTDOWN]{C_RESET} Menghentikan background Machine threads...")
    scheduler.shutdown()
    print(f"{C_GREEN}[COMPLETED]{C_RESET} Lab Runtime GMP Deep Dive selesai secara bersih.")


if __name__ == "__main__":
    main()