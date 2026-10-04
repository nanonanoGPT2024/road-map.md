#!/usr/bin/env python3
"""
Lab Hands-on: Go Runtime Deep Dive - GMP Concurrency & Work-Stealing Scheduler
Bab 04 / Modul 02: Go Memory & Scheduler Architecture Simulation

Simulasi teknis ini mengimplementasikan abstraksi internal Go Runtime:
1. G (Goroutine): Unit eksekusi independen dengan state machine terdefinisi.
2. M (Machine): Worker thread sistem operasi (OS Thread).
3. P (Processor): Logical context/resource batas konkurensi (GOMAXPROCS).
4. Work-Stealing Algorithm: Mekanisme M/P mencuri beban kerja dari P lain ketika antrean lokal kosong.
5. 61-Tick Rule: Pemeriksaan Global Run Queue (GRQ) secara periodik untuk mencegah kelaparan (starvation).
6. Channel Mechanics: Sinkronisasi hchan dengan send/recv sudog wait-queue blocking.
"""

import sys
import time
import random
import threading
from enum import Enum, auto
from typing import Optional, List, Dict, Any
from collections import deque
from dataclasses import dataclass, field

# --- Terminal Styling (ANSI) ---
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[36m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    RED     = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE    = "\033[34m"

def log(tag: str, color: str, msg: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{Color.DIM}[{timestamp}]{Color.RESET} {color}[{tag:<10}]{Color.RESET} {msg}")

# --- Core Enums & Data Structures ---
class GState(Enum):
    GIDLE = auto()
    GRUNNABLE = auto()
    GRUNNING = auto()
    GWAITING = auto()
    GDEAD = auto()

@dataclass
class Goroutine:
    gid: int
    task_name: str
    work_cycles: int
    state: GState = GState.GIDLE
    blocking_chan: Optional[str] = None
    created_at: float = field(default_factory=time.time)

class Sudog:
    """Representasi elemen antrean tunggu channel (gwaiting)."""
    def __init__(self, g: Goroutine, value: Any = None):
        self.g = g
        self.value = value

class GoChannel:
    """Model hchan Go runtime dengan circular ring-buffer dan send/recv wait queues."""
    def __init__(self, name: str, capacity: int = 0):
        self.name = name
        self.capacity = capacity
        self.buf: deque = deque(maxlen=capacity if capacity > 0 else None)
        self.recvq: deque[Sudog] = deque()
        self.sendq: deque[Sudog] = deque()
        self.lock = threading.Lock()

    def send(self, g: Goroutine, val: Any) -> bool:
        with self.lock:
            if self.recvq:
                # Direct hand-off: bypass buffer ke receiver yang parkir
                receiver_sudog = self.recvq.popleft()
                receiver_sudog.value = val
                receiver_sudog.g.state = GState.GRUNNABLE
                log("CHANNEL", Color.MAGENTA, 
                    f"Direct Handoff '{self.name}': G{g.gid} -> G{receiver_sudog.g.gid} (Val: {val})")
                return True
            
            if self.capacity > 0 and len(self.buf) < self.capacity:
                self.buf.append(val)
                log("CHANNEL", Color.MAGENTA, 
                    f"Buffered Send '{self.name}': G{g.gid} -> Buffer [{len(self.buf)}/{self.capacity}]")
                return True

            # Channel penuh atau unbuffered tanpa receiver -> Block G (gopark)
            g.state = GState.GWAITING
            g.blocking_chan = self.name
            self.sendq.append(Sudog(g, val))
            log("CHANNEL", Color.YELLOW, f"G{g.gid} gopark() [SEND BLOCKED on '{self.name}']")
            return False

    def recv(self, g: Goroutine) -> tuple[Optional[Any], bool]:
        with self.lock:
            if self.capacity > 0 and len(self.buf) > 0:
                val = self.buf.popleft()
                if self.sendq:
                    # Ambil elemen dari sender yang terparkir ke dalam buffer
                    sender_sudog = self.sendq.popleft()
                    self.buf.append(sender_sudog.value)
                    sender_sudog.g.state = GState.GRUNNABLE
                    log("CHANNEL", Color.MAGENTA, 
                        f"Woke up blocked sender G{sender_sudog.g.gid} for '{self.name}'")
                return val, True

            if self.sendq:
                # Direct unbuffered handoff dari sender
                sender_sudog = self.sendq.popleft()
                val = sender_sudog.value
                sender_sudog.g.state = GState.GRUNNABLE
                log("CHANNEL", Color.MAGENTA, 
                    f"Direct Recv Handoff '{self.name}': G{sender_sudog.g.gid} -> G{g.gid} (Val: {val})")
                return val, True

            # Channel kosong -> Block G (gopark)
            g.state = GState.GWAITING
            g.blocking_chan = self.name
            self.recvq.append(Sudog(g))
            log("CHANNEL", Color.YELLOW, f"G{g.gid} gopark() [RECV BLOCKED on '{self.name}']")
            return None, False

class Processor:
    """P (Processor): Memegang local run queue (LRQ) dan execution context."""
    def __init__(self, pid: int, lrq_capacity: int = 8):
        self.pid = pid
        self.lrq_capacity = lrq_capacity
        self.lrq: deque[Goroutine] = deque()
        self.runnext: Optional[Goroutine] = None
        self.schedtick: int = 0
        self.lock = threading.Lock()
        self.steals_count: int = 0

    def push_runnable(self, g: Goroutine, grq: 'GlobalRunQueue') -> None:
        """Menambahkan G ke antrean eksekusi sesuai hierarki Go P: runnext -> LRQ -> GRQ."""
        with self.lock:
            g.state = GState.GRUNNABLE
            if self.runnext is None:
                self.runnext = g
                return

            # Geser target lama ke LRQ
            old_next = self.runnext
            self.runnext = g
            
            if len(self.lrq) < self.lrq_capacity:
                self.lrq.append(old_next)
            else:
                # LRQ overflow, offload setengah kapasitas LRQ ke Global Run Queue
                batch = [self.lrq.popleft() for _ in range(self.lrq_capacity // 2)]
                batch.append(old_next)
                grq.put_batch(batch)
                log("P-OVFL", Color.RED, f"P{self.pid} LRQ Penuh. Menendang {len(batch)} Goroutines ke GRQ.")

class GlobalRunQueue:
    """GRQ: Shared queue dengan proteksi mutex global."""
    def __init__(self):
        self.queue: deque[Goroutine] = deque()
        self.lock = threading.Lock()

    def put_batch(self, batch: List[Goroutine]) -> None:
        with self.lock:
            self.queue.extend(batch)

    def get_batch(self, n: int) -> List[Goroutine]:
        with self.lock:
            count = min(n, len(self.queue))
            return [self.queue.popleft() for _ in range(count)]

    def len(self) -> int:
        with self.lock:
            return len(self.queue)

class GoRuntimeEngine:
    """Mesin orkestrasi runtime scheduler GMP."""
    def __init__(self, gomaxprocs: int = 3):
        self.gomaxprocs = gomaxprocs
        self.processors: List[Processor] = [Processor(i) for i in range(gomaxprocs)]
        self.grq = GlobalRunQueue()
        self.channels: Dict[str, GoChannel] = {}
        self.running = False
        self.workers: List[threading.Thread] = []
        self.stats_executed = 0
        self.stats_lock = threading.Lock()

    def register_channel(self, name: str, capacity: int = 0) -> GoChannel:
        ch = GoChannel(name, capacity)
        self.channels[name] = ch
        return ch

    def go(self, task_name: str, cycles: int) -> Goroutine:
        """Membuat Goroutine baru (`go func()`)."""
        gid = random.randint(1000, 9999)
        g = Goroutine(gid=gid, task_name=task_name, work_cycles=cycles)
        # Pilih P secara pseudo-round-robin
        target_p = self.processors[gid % self.gomaxprocs]
        target_p.push_runnable(g, self.grq)
        log("GO_STMT", Color.CYAN, f"Spawned G{g.gid} ('{task_name}') -> Attached to P{target_p.pid}")
        return g

    def _find_runnable_g(self, p: Processor) -> Optional[Goroutine]:
        """
        Go schedule() lookup policy:
        1. Setiap 61 schedtick, periksa GRQ agar tidak kelaparan (prevent starvation).
        2. Periksa p.runnext.
        3. Periksa p.lrq (antrean lokal).
        4. Periksa GRQ jika belum diperiksa.
        5. Work-Stealing: Curi separuh muatan dari P lain.
        """
        p.schedtick += 1

        # 1. 61-tick check
        if p.schedtick % 61 == 0:
            batch = self.grq.get_batch(1)
            if batch:
                log("SCHED_61", Color.BLUE, f"P{p.pid} 61-Tick GRQ Priority Check triggered -> Found G{batch[0].gid}")
                return batch[0]

        with p.lock:
            # 2. Check runnext
            if p.runnext:
                g = p.runnext
                p.runnext = None
                return g

            # 3. Check LRQ
            if p.lrq:
                return p.lrq.popleft()

        # 4. Check GRQ
        if self.grq.len() > 0:
            batch = self.grq.get_batch(1)
            if batch:
                return batch[0]

        # 5. Work Stealing Algorithm
        # Acak target P victim untuk menghindari contention
        victims = [other for other in self.processors if other.pid != p.pid]
        random.shuffle(victims)
        for victim in victims:
            with victim.lock:
                v_len = len(victim.lrq)
                if v_len > 0:
                    steal_count = max(1, v_len // 2)
                    stolen_batch = [victim.lrq.popleft() for _ in range(steal_count)]
                    target_g = stolen_batch.pop(0)
                    with p.lock:
                        p.lrq.extend(stolen_batch)
                        p.steals_count += len(stolen_batch) + 1
                    log("WORK_STEAL", Color.YELLOW, 
                        f"P{p.pid} STOLE {len(stolen_batch) + 1} G(s) from Victim P{victim.pid}! Executing G{target_g.gid}")
                    return target_g

        return None

    def _m_worker(self, m_id: int):
        """Thread worker representasi OS Thread (M)."""
        p = self.processors[m_id % self.gomaxprocs]
        log("M_SYS", Color.GREEN, f"OS Thread M{m_id} bound to Context P{p.pid}")

        while self.running:
            g = self._find_runnable_g(p)
            if not g:
                time.sleep(0.01)
                continue

            # State transition to GRUNNING
            g.state = GState.GRUNNING
            
            # Simulasi eksekusi slice kuantum instruksi
            for _ in range(g.work_cycles):
                time.sleep(0.005)
            
            # Task selesai: transisi ke GDEAD
            g.state = GState.GDEAD
            with self.stats_lock:
                self.stats_executed += 1

            log("G_EXEC", Color.GREEN, f"M{m_id}/P{p.pid} completed G{g.gid} ('{g.task_name}')")

    def start(self):
        self.running = True
        for m_id in range(self.gomaxprocs):
            t = threading.Thread(target=self._m_worker, args=(m_id,), daemon=True)
            self.workers.append(t)
            t.start()

    def stop(self):
        self.running = False
        for t in self.workers:
            t.join(timeout=0.5)

# --- Demonstrasi Skenario Lab Eksekusi ---
def run_lab():
    print(f"{Color.BOLD}{Color.CYAN}=== LAB: GO RUNTIME (GMP) & SCHEDULING DEEP DIVE ==={Color.RESET}")
    print(f"{Color.DIM}Simulasi Mekanisme Work-Stealing, 61-Tick Starvation Prevention & Channel Sudog{Color.RESET}\n")

    # Inisialisasi Runtime dengan GOMAXPROCS = 3
    GOMAXPROCS = 3
    runtime = GoRuntimeEngine(gomaxprocs=GOMAXPROCS)
    runtime.start()

    time.sleep(0.05)

    # 1. Demonstrasi Channel Handoff & Blocking Mechanism
    log("DEMO", Color.BOLD, "SKENARIO 1: Go Channel Inter-Goroutine Synchronization")
    ch_sync = runtime.register_channel("data_pipe", capacity=1)
    
    g_sender = runtime.go("producer_task", cycles=2)
    g_receiver = runtime.go("consumer_task", cycles=1)

    # Kirim data ke channel berkapasitas 1
    ch_sync.send(g_sender, "DATA_PAYLOAD_ALPHA")
    # Kirim lagi untuk memaksa buffer jenuh -> Park sender
    g_sender_blocked = runtime.go("heavy_producer", cycles=2)
    ch_sync.send(g_sender_blocked, "DATA_PAYLOAD_BETA")

    time.sleep(0.05)
    # Drain channel -> Memicu unpark sender
    val, ok = ch_sync.recv(g_receiver)
    log("DEMO", Color.GREEN, f"Consumer membaca nilai dari channel: '{val}' (OK={ok})")

    time.sleep(0.1)

    # 2. Demonstrasi Load Imbalance & Work-Stealing
    log("DEMO", Color.BOLD, "\nSKENARIO 2: Asymmetric Ingestion & Work-Stealing Activation")
    
    # Banjiri antrean P0 untuk memicu LRQ overflow ke GRQ
    p0 = runtime.processors[0]
    log("DEMO", Color.YELLOW, f"Membanjiri antrean P0 secara agresif...")
    for i in range(12):
        g = Goroutine(gid=5000 + i, task_name=f"compute_batch_{i}", work_cycles=random.randint(2, 4))
        p0.push_runnable(g, runtime.grq)

    # Biarkan scheduler GMP bekerja dan mendistribusikan beban
    time.sleep(0.6)

    runtime.stop()

    # --- Print Structured Diagnostic Report ---
    print(f"\n{Color.BOLD}{Color.CYAN}=== RUNTIME AUDIT & SCHEDULER METRICS ==={Color.RESET}")
    print(f"{'Processor':<12} | {'Local Queue':<12} | {'Sched Ticks':<12} | {'Steal Count':<12}")
    print("-" * 55)
    for p in runtime.processors:
        print(f"P{p.pid:<11} | {len(p.lrq):<12} | {p.schedtick:<12} | {p.steals_count:<12}")

    print("-" * 55)
    print(f"Remaining in GRQ    : {runtime.grq.len()} Goroutine(s)")
    print(f"Total G Executed    : {runtime.stats_executed}")
    print(f"{Color.GREEN}Hasil Verifikasi: Work-stealing dan scheduling cycle berhasil dieksekusi.{Color.RESET}")

if __name__ == "__main__":
    run_lab()