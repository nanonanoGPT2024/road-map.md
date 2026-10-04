#!/usr/bin/env python3
"""
Lab Hands-on: Go Runtime Internal Scheduler (GMP Model) & Work-Stealing Simulator
Modul: 02 Deep Dive - Bab 07 (Golang Runtime Architecture)

Deskripsi:
Skrip ini memodelkan runtime engine Go (Go 1.5+ M:N Scheduler):
1. G (Goroutine): Unit eksekusi independen dengan dynamic stack & state tracker.
2. M (Machine): Abstraksi thread OS yang mengeksekusi instruksi.
3. P (Processor): Resource logis (GOMAXPROCS) yang memiliki Local Run Queue (LRQ).
4. Global Run Queue (GRQ) & Work-Stealing Algorithm (mencuri 50% beban dari P lain).
5. Channel Synchronization & G-Parking (Wait/Ready) state transition.
"""

import sys
import time
import random
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# --- ANSI Terminal Colors ---
CLR_RST = "\033[0m"
CLR_RED = "\033[91m"
CLR_GRN = "\033[92m"
CLR_YLW = "\033[93m"
CLR_BLU = "\033[94m"
CLR_MAG = "\033[95m"
CLR_CYN = "\033[96m"
CLR_BOLD = "\033[1m"


class GState(Enum):
    IDLE = "Gidle"
    RUNNABLE = "Grunnable"
    RUNNING = "Grunning"
    WAITING = "Gwaiting"
    DEAD = "Gdead"


@dataclass
class Goroutine:
    gid: int
    task_fn: Callable[..., Any]
    args: tuple = field(default_factory=tuple)
    state: GState = GState.IDLE
    stack_size_kb: int = 2  # Default minimum stack in modern Go (2KB)
    result: Any = None
    wait_channel: Optional[str] = None

    def __repr__(self) -> str:
        return f"G{self.gid:02d}[{self.state.value}]"


class GoChannel:
    """Simulasi channel Go terkoordinasi (hchan) dengan internal waitq."""
    def __init__(self, name: str, capacity: int = 0):
        self.name = name
        self.capacity = capacity
        self.buffer = deque()
        self.lock = threading.Lock()
        self.recv_waitq: deque[Goroutine] = deque()
        self.send_waitq: deque[tuple[Goroutine, Any]] = deque()

    def send(self, g: Goroutine, val: Any) -> bool:
        """Mengirim data ke channel. Mengembalikan True jika berhasil tanpa parkir, False jika G diparkir."""
        with self.lock:
            # 1. Jika ada receiver yang parkir di waitq, kirim langsung (direct copy)
            if self.recv_waitq:
                receiver = self.recv_waitq.popleft()
                receiver.result = val
                receiver.state = GState.RUNNABLE
                receiver.wait_channel = None
                return True

            # 2. Jika buffer masih muat
            if len(self.buffer) < self.capacity:
                self.buffer.append(val)
                return True

            # 3. Buffer penuh / unbuffered tanpa receiver -> G masuk send_waitq dan WAITING
            g.state = GState.WAITING
            g.wait_channel = self.name
            self.send_waitq.append((g, val))
            return False

    def recv(self, g: Goroutine) -> tuple[bool, Any]:
        """Menerima data dari channel. Return (success, value). False jika G diparkir."""
        with self.lock:
            # 1. Jika buffer memiliki elemen
            if self.buffer:
                val = self.buffer.popleft()
                if self.send_waitq:
                    sender, send_val = self.send_waitq.popleft()
                    self.buffer.append(send_val)
                    sender.state = GState.RUNNABLE
                    sender.wait_channel = None
                return True, val

            # 2. Jika ada sender yang menunggu langsung di sendq (unbuffered case)
            if self.send_waitq:
                sender, val = self.send_waitq.popleft()
                sender.state = GState.RUNNABLE
                sender.wait_channel = None
                return True, val

            # 3. Buffer kosong -> G masuk recv_waitq dan WAITING
            g.state = GState.WAITING
            g.wait_channel = self.name
            self.recv_waitq.append(g)
            return False, None


class Processor:
    """Representasi 'P' dalam model GMP (Context/Logical Core)."""
    def __init__(self, pid: int, max_lrq: int = 8):
        self.pid = pid
        self.max_lrq = max_lrq
        self.lrq: deque[Goroutine] = deque()  # Local Run Queue
        self.lock = threading.Lock()
        self.m_assigned: Optional[int] = None
        self.executed_tasks = 0
        self.stolen_tasks = 0

    def push_runnable(self, g: Goroutine) -> bool:
        """Memasukkan G ke LRQ. Return False jika LRQ overflow (harus offload ke GRQ)."""
        with self.lock:
            if len(self.lrq) < self.max_lrq:
                g.state = GState.RUNNABLE
                self.lrq.append(g)
                return True
            return False

    def pop_runnable(self) -> Optional[Goroutine]:
        with self.lock:
            if self.lrq:
                g = self.lrq.popleft()
                return g
            return None

    def steal_half_from(self, victim: 'Processor') -> List[Goroutine]:
        """Algoritma Work-Stealing: Mencuri setengah tugas dari target LRQ."""
        stolen = []
        if victim.lock.acquire(blocking=False):
            try:
                victim_len = len(victim.lrq)
                if victim_len > 1:
                    num_to_steal = victim_len // 2
                    for _ in range(num_to_steal):
                        stolen.append(victim.lrq.pop())
            finally:
                victim.lock.release()
        return stolen


class GMPScheduler:
    """Koordinator runtime Go: mengelola Pool P, Thread M, dan GRQ."""
    def __init__(self, gomaxprocs: int):
        self.gomaxprocs = gomaxprocs
        self.processors: List[Processor] = [Processor(i) for i in range(gomaxprocs)]
        self.grq: deque[Goroutine] = deque()  # Global Run Queue
        self.grq_lock = threading.Lock()
        self.gid_counter = 1
        self.active_machines: List[threading.Thread] = []
        self.running = True
        self.channels: Dict[str, GoChannel] = {}

    def new_goroutine(self, fn: Callable, *args) -> Goroutine:
        g = Goroutine(gid=self.gid_counter, task_fn=fn, args=args, state=GState.RUNNABLE)
        self.gid_counter += 1

        # Coba masukkan ke target P acak; jika LRQ penuh, kirim ke GRQ
        target_p = random.choice(self.processors)
        if not target_p.push_runnable(g):
            with self.grq_lock:
                self.grq.append(g)
        return g

    def create_channel(self, name: str, capacity: int = 0) -> GoChannel:
        ch = GoChannel(name, capacity)
        self.channels[name] = ch
        return ch

    def _find_runnable_g(self, p: Processor, tick_count: int) -> Optional[Goroutine]:
        """
        Siklus penjadwalan Go:
        1. Setiap 61 tick, cek GRQ untuk mencegah kelaparan (starvation).
        2. Cek Local Run Queue (LRQ).
        3. Cek GRQ jika LRQ kosong.
        4. Work-Stealing: Curi dari P lain secara random.
        """
        # Rule 61: Cek GRQ periodik
        if tick_count % 61 == 0:
            with self.grq_lock:
                if self.grq:
                    return self.grq.popleft()

        # Cek LRQ
        g = p.pop_runnable()
        if g:
            return g

        # Cek GRQ
        with self.grq_lock:
            if self.grq:
                return self.grq.popleft()

        # Work Stealing
        other_ps = [other for other in self.processors if other.pid != p.pid]
        random.shuffle(other_ps)
        for victim in other_ps:
            stolen = p.steal_half_from(victim)
            if stolen:
                p.stolen_tasks += len(stolen)
                with p.lock:
                    first = stolen.pop(0)
                    p.lrq.extend(stolen)
                    return first
        return None

    def _m_worker_loop(self, m_id: int):
        """Loop eksekusi mesin thread OS (M). Terikat ke satu Processor P."""
        p = self.processors[m_id % self.gomaxprocs]
        p.m_assigned = m_id
        ticks = 0

        while self.running:
            ticks += 1
            g = self._find_runnable_g(p, ticks)

            if not g:
                time.sleep(0.01)
                continue

            # Context Switch ke Goroutine
            g.state = GState.RUNNING
            try:
                # Eksekusi task
                res = g.task_fn(self, g, *g.args)
                g.result = res
                if g.state == GState.RUNNING:
                    g.state = GState.DEAD
                    p.executed_tasks += 1
            except Exception as e:
                print(f"{CLR_RED}[M{m_id:02d}] G{g.gid:02d} Panic: {e}{CLR_RST}")
                g.state = GState.DEAD

            # Re-enqueue jika G masih runnable (misal cooperative yield)
            if g.state == GState.RUNNABLE:
                if not p.push_runnable(g):
                    with self.grq_lock:
                        self.grq.append(g)

    def start(self):
        print(f"{CLR_CYN}=== Inisialisasi Go Runtime GMP Scheduler (GOMAXPROCS={self.gomaxprocs}) ==={CLR_RST}")
        for i in range(self.gomaxprocs):
            m_thread = threading.Thread(target=self._m_worker_loop, args=(i + 1,), daemon=True)
            self.active_machines.append(m_thread)
            m_thread.start()

    def shutdown(self):
        self.running = False
        for m in self.active_machines:
            m.join(timeout=0.2)


# --- Workload Simulasi ---

def worker_cpu_bound(sched: GMPScheduler, g: Goroutine, job_id: int, iterations: int):
    """Simulasi goroutine komputasi murni dengan simulasi stack expansion."""
    acc = 0
    for i in range(iterations):
        acc += (i * 3) ^ (i % 7)
    # Stack split trigger
    if iterations > 300_000:
        g.stack_size_kb *= 2
    return acc


def channel_producer(sched: GMPScheduler, g: Goroutine, ch_name: str, values: List[int]):
    """Simulasi channel transmitter."""
    ch = sched.channels[ch_name]
    for val in values:
        while not ch.send(g, val):
            # Jika buffer penuh, terparkir. Saat bangun kembali, ulangi push
            time.sleep(0.005)
        print(f"{CLR_GRN}  -> [TX] G{g.gid:02d} mengirim: {val} via '{ch_name}'{CLR_RST}")
        time.sleep(0.002)
    return "PROD_DONE"


def channel_consumer(sched: GMPScheduler, g: Goroutine, ch_name: str, count: int):
    """Simulasi channel receiver yang reaktif terhadap unblocking."""
    ch = sched.channels[ch_name]
    received = []
    for _ in range(count):
        success = False
        val = None
        while not success:
            success, val = ch.recv(g)
            if not success:
                time.sleep(0.005)
        received.append(val)
        print(f"{CLR_YLW}  <- [RX] G{g.gid:02d} menerima: {val} dari '{ch_name}'{CLR_RST}")
        time.sleep(0.002)
    return received


def print_dashboard(sched: GMPScheduler):
    """Visualisasi status internal GMP secara tabular."""
    print("\n" + "=" * 70)
    print(f"{CLR_BOLD}DASHBOARD STATUS RUNTIME GOLANG (GMP METRICS){CLR_RST}")
    print("=" * 70)

    with sched.grq_lock:
        grq_snapshot = list(sched.grq)
    print(f"{CLR_MAG}Global Run Queue (GRQ) [{len(grq_snapshot)} items]: {grq_snapshot}{CLR_RST}")

    print("-" * 70)
    for p in sched.processors:
        with p.lock:
            q_snap = list(p.lrq)
        print(
            f"{CLR_BLU}P{p.pid:02d} (Bound ke M{p.m_assigned:02d}){CLR_RST} | "
            f"LRQ ({len(q_snap)}/{p.max_lrq}): {q_snap} | "
            f"Done: {CLR_GRN}{p.executed_tasks:02d}{CLR_RST} | "
            f"Stolen: {CLR_YLW}{p.stolen_tasks:02d}{CLR_RST}"
        )
    print("=" * 70)


def main():
    # Menjalankan runtime dengan 3 logical processor P
    sched = GMPScheduler(gomaxprocs=3)
    sched.start()

    # 1. Pembuatan Channel
    shared_chan = sched.create_channel("data_pipe", capacity=2)

    # 2. Spawning Goroutines (Heavy & Channel Tasks)
    print(f"\n{CLR_CYN}[*] Melakukan Spawning Goroutines ke Scheduler...{CLR_RST}")

    # Spawning CPU tasks untuk menumpuk workload (memicu Work-Stealing)
    for i in range(12):
        sched.new_goroutine(worker_cpu_bound, i + 1, 200_000 + (i * 30_000))

    # Spawning Channel Producer & Consumer
    sched.new_goroutine(channel_producer, "data_pipe", [101, 102, 103, 104, 105])
    sched.new_goroutine(channel_consumer, "data_pipe", 5)

    # 3. Observasi real-time siklus eksekusi
    for step in range(4):
        time.sleep(0.04)
        print_dashboard(sched)

    # Tunggu runtime menyelesaikan task
    time.sleep(0.1)
    sched.shutdown()

    print(f"\n{CLR_GRN}[✓] Simulasi Berhasil. Scheduler Go dihentikan dengan aman.{CLR_RST}")


if __name__ == "__main__":
    main()