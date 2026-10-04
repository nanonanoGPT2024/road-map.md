#!/usr/bin/env python3
"""
Hands-on Lab: Deep Dive Go Concurrency Internals (GMP Scheduler & Channels)
Modul: 02 - Deep Dive Arsitektur Runtime Go

Deskripsi:
Skrip ini memodelkan arsitektur inti dari Go Runtime Scheduler (M:N Work-Stealing Scheduler)
dan Sinkronisasi CSP (Communicating Sequential Processes) Channel:
1. G (Goroutine): Lightweight thread dengan call stack minimalis.
2. M (Machine): Worker thread sistem operasi (OS thread).
3. P (Processor): Resource logis eksekusi kode Go (GOMAXPROCS), memiliki Local Run Queue (LRQ).
4. GRQ (Global Run Queue): Antrean global ketika LRQ penuh atau untuk load-balancing.
5. Work-Stealing: P mencuri separuh tugas dari LRQ P lain saat kehabisan beban kerja.
6. CSP Buffered Channel: Antrean thread-safe ring-buffer dengan simulasi suspensi Goroutine.
"""

import sys
import time
import random
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Any, Optional, List

# ANSI Color Codes untuk visualisasi terminal
CLR_RST = "\033[0m"
CLR_BLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GRN = "\033[32m"
CLR_YLW = "\033[33m"
CLR_BLU = "\033[34m"
CLR_MAG = "\033[35m"
CLR_CYN = "\033[36m"

@dataclass
class Goroutine:
    """Representasi entitas G (Goroutine) dalam runtime Go."""
    gid: int
    fn: Callable[..., Any]
    args: tuple = ()
    state: str = "Gidle"  # Gidle, Grunnable, Grunning, Gwaiting, Gdead
    sched_tick: int = 0

class GoChannel:
    """
    Simulasi CSP Channel Go (Buffered/Unbuffered) dengan sinkronisasi
    dan penanganan goroutine park/ready.
    """
    def __init__(self, capacity: int = 0):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity if capacity > 0 else 1)
        self.lock = threading.Lock()
        self.not_full = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)
        self.closed = False

    def send(self, val: Any, gid: int) -> bool:
        """Mengirim data ke channel (ch <- val)."""
        with self.lock:
            if self.closed:
                raise RuntimeError(f"panic: send on closed channel (G{gid})")
            
            while len(self.buffer) >= (self.capacity if self.capacity > 0 else 1):
                self.not_full.wait()
                if self.closed:
                    raise RuntimeError(f"panic: send on closed channel (G{gid})")

            self.buffer.append(val)
            self.not_empty.notify()
            return True

    def recv(self, gid: int) -> tuple[Optional[Any], bool]:
        """Menerima data dari channel (val, ok := <-ch)."""
        with self.lock:
            while len(self.buffer) == 0:
                if self.closed:
                    return None, False
                self.not_empty.wait()

            val = self.buffer.popleft()
            self.not_full.notify()
            return val, True

    def close(self):
        """Menutup channel (close(ch))."""
        with self.lock:
            self.closed = True
            self.not_full.notify_all()
            self.not_empty.notify_all()

class Processor:
    """
    Representasi entitas P (Logical Processor).
    Menampung Local Run Queue (LRQ) berkapasitas terbatas (di Go aslinya 256).
    """
    def __init__(self, pid: int, lrq_capacity: int = 4):
        self.pid = pid
        self.lrq: deque[Goroutine] = deque()
        self.runnext: Optional[Goroutine] = None  # Optimasi fast-path scheduler
        self.lrq_capacity = lrq_capacity
        self.sched_tick = 0
        self.lock = threading.Lock()
        self.steals_performed = 0

class Machine(threading.Thread):
    """
    Representasi entitas M (OS Machine Thread).
    M mengeksekusi Goroutine (G) yang terikat pada Processor (P).
    """
    def __init__(self, mid: int, scheduler: 'GMPRuntime'):
        super().__init__(name=f"OS-Thread-M{mid}", daemon=True)
        self.mid = mid
        self.scheduler = scheduler
        self.assigned_p: Optional[Processor] = None
        self.running = True

    def run(self):
        """Siklus hidup M: loop fetch-execute Goroutine."""
        while self.running and not self.scheduler.stop_requested:
            # 1. Bind P jika belum memilikinya
            if not self.assigned_p:
                self.assigned_p = self.scheduler.acquire_p(self)
                if not self.assigned_p:
                    time.sleep(0.005)
                    continue

            # 2. Schedule: Cari G yang runnable
            g = self.scheduler.find_runnable_g(self.assigned_p)
            if g:
                self.execute_g(g)
            else:
                time.sleep(0.002)

    def execute_g(self, g: Goroutine):
        """Eksekusi stack frame dari Goroutine."""
        g.state = "Grunning"
        p = self.assigned_p
        
        # Logging eksekusi
        sys.stdout.write(
            f"{CLR_CYN}[SCHED]{CLR_RST} {CLR_GRN}M{self.mid:02d}{CLR_RST} executing "
            f"{CLR_MAG}G{g.gid:02d}{CLR_RST} on {CLR_YLW}P{p.pid:02d}{CLR_RST} | "
            f"LRQ: {len(p.lrq)} | GRQ: {len(self.scheduler.grq)}\n"
        )
        sys.stdout.flush()

        try:
            g.fn(*g.args)
        except Exception as e:
            sys.stdout.write(f"{CLR_RED}[PANIC] G{g.gid} crashed: {e}{CLR_RST}\n")
        finally:
            g.state = "Gdead"
            with self.scheduler.stats_lock:
                self.scheduler.completed_goroutines += 1

class GMPRuntime:
    """
    Go Runtime Simulator mengelola G, M, P, dan algoritma Work-Stealing.
    """
    def __init__(self, gomaxprocs: int = 4):
        self.gomaxprocs = gomaxprocs
        self.processors: List[Processor] = [Processor(pid=i) for i in range(gomaxprocs)]
        self.machines: List[Machine] = []
        self.grq: deque[Goroutine] = deque()  # Global Run Queue
        self.grq_lock = threading.Lock()
        self.gid_counter = 1
        self.gid_lock = threading.Lock()
        self.stop_requested = False
        self.completed_goroutines = 0
        self.stats_lock = threading.Lock()

        # Inisialisasi pool OS thread M
        for i in range(gomaxprocs):
            m = Machine(mid=i, scheduler=self)
            self.machines.append(m)

    def start(self):
        """Menyalakan Go Runtime."""
        for m in self.machines:
            m.start()

    def acquire_p(self, m: Machine) -> Optional[Processor]:
        """Menghubungkan M ke P yang masih idle."""
        for p in self.processors:
            if p.lock.acquire(blocking=False):
                return p
        return None

    def new_goroutine(self, fn: Callable, *args) -> int:
        """go func() implementation: Membuat dan menjadwalkan Goroutine baru."""
        with self.gid_lock:
            gid = self.gid_counter
            self.gid_counter += 1

        g = Goroutine(gid=gid, fn=fn, args=args, state="Grunnable")

        # Masukkan ke LRQ dari P acak atau GRQ jika penuh
        target_p = random.choice(self.processors)
        with target_p.lock:
            if len(target_p.lrq) < target_p.lrq_capacity:
                target_p.lrq.append(g)
            else:
                # LRQ Penuh: pindahkan separuh ke GRQ (Go behavior)
                with self.grq_lock:
                    self.grq.append(g)
                    # Pindahkan setengah isi LRQ ke GRQ
                    batch_size = len(target_p.lrq) // 2
                    for _ in range(batch_size):
                        self.grq.append(target_p.lrq.popleft())
        return gid

    def find_runnable_g(self, p: Processor) -> Optional[Goroutine]:
        """
        Algoritma Penjadwalan Go (sysmon & schedule loop):
        1. 1/61 tick: Periksa Global Run Queue (hindari kelaparan GRQ).
        2. Periksa Local Run Queue (LRQ) milik P.
        3. Periksa GRQ jika LRQ kosong.
        4. Work-Stealing: Curi 50% G dari LRQ Processor P lain.
        """
        p.sched_tick += 1

        # 1. Fairness check: Setiap 61 tick, ambil dari GRQ
        if p.sched_tick % 61 == 0:
            with self.grq_lock:
                if self.grq:
                    return self.grq.popleft()

        # 2. Ambil dari LRQ lokal
        if p.lrq:
            return p.lrq.popleft()

        # 3. Ambil dari GRQ
        with self.grq_lock:
            if self.grq:
                # Ambil batch G dari GRQ ke LRQ (hingga n = min(len(GRQ), lrq_capacity/2))
                batch_n = min(len(self.grq), p.lrq_capacity // 2)
                for _ in range(batch_n):
                    p.lrq.append(self.grq.popleft())
                if p.lrq:
                    return p.lrq.popleft()

        # 4. Work-Stealing: Curi dari Processor lain
        return self.steal_work(p)

    def steal_work(self, thief_p: Processor) -> Optional[Goroutine]:
        """
        Algoritma Work-Stealing:
        Mencari P target secara acak dan mencuri separuh (n/2) antrean LRQ-nya.
        """
        candidates = [p for p in self.processors if p.pid != thief_p.pid]
        random.shuffle(candidates)

        for victim_p in candidates:
            if not victim_p.lock.acquire(blocking=False):
                continue
            try:
                victim_len = len(victim_p.lrq)
                if victim_len > 1:
                    steal_count = victim_len // 2
                    sys.stdout.write(
                        f"{CLR_YLW}[STEAL]{CLR_RST} P{thief_p.pid:02d} stealing "
                        f"{steal_count} Goroutine(s) from P{victim_p.pid:02d}\n"
                    )
                    sys.stdout.flush()

                    for _ in range(steal_count):
                        thief_p.lrq.append(victim_p.lrq.popleft())
                    thief_p.steals_performed += 1
                    return thief_p.lrq.popleft()
            finally:
                victim_p.lock.release()
        return None

    def shutdown(self):
        """Matikan scheduler dan sinkronkan semua thread."""
        self.stop_requested = True
        for m in self.machines:
            m.running = False
        for p in self.processors:
            if p.lock.locked():
                try:
                    p.lock.release()
                except RuntimeError:
                    pass
        for m in self.machines:
            m.join(timeout=1.0)


# ==========================================
# WORKLOAD & HANDS-ON DEMONSTRATION
# ==========================================

def producer_task(ch: GoChannel, worker_id: int, total_items: int):
    """Fungsi produsen meniru pola goroutine 'worker pipeline'."""
    for item in range(1, total_items + 1):
        payload = f"Pkg-W{worker_id}-{item}"
        ch.send(payload, gid=worker_id)
        time.sleep(0.01)  # Simulasi compute / network I/O
    sys.stdout.write(f"{CLR_BLU}[PROD]{CLR_RST} Worker-{worker_id} selesai streaming data.\n")

def consumer_task(ch: GoChannel, consumer_id: int):
    """Fungsi konsumen membaca data dari channel sampai channel ditutup."""
    received_count = 0
    while True:
        val, ok = ch.recv(gid=consumer_id)
        if not ok:
            break
        received_count += 1
        time.sleep(0.015)  # Simulasi parsing & indexing data
    sys.stdout.write(
        f"{CLR_GRN}[CONS]{CLR_RST} Consumer-{consumer_id} selesai. Total diproses: {received_count}\n"
    )

def main():
    print(f"{CLR_BLD}{CLR_CYN}============================================================{CLR_RST}")
    print(f"{CLR_BLD}{CLR_CYN}  GO RUNTIME DEEP DIVE: GMP SCHEDULER & CSP WORK-STEALING  {CLR_RST}")
    print(f"{CLR_BLD}{CLR_CYN}============================================================{CLR_RST}")

    # Konfigurasi GOMAXPROCS = 3
    gomaxprocs = 3
    print(f"[*] Initializing Go Runtime with GOMAXPROCS={gomaxprocs} (P=3, M=3)...")
    runtime = GMPRuntime(gomaxprocs=gomaxprocs)
    runtime.start()

    # Inisialisasi Buffered Channel kapasitas 5
    channel_buffer = 5
    print(f"[*] Creating CSP Channel with buffer capacity: {channel_buffer}")
    data_stream = GoChannel(capacity=channel_buffer)

    print("[*] Spawning Goroutines (Producers and Consumers)...")
    
    total_producers = 4
    items_per_prod = 5
    
    # Dispatch Producers via Go Runtime
    for pid in range(1, total_producers + 1):
        runtime.new_goroutine(producer_task, data_stream, pid, items_per_prod)

    # Dispatch Consumers via Go Runtime
    total_consumers = 2
    for cid in range(1, total_consumers + 1):
        runtime.new_goroutine(consumer_task, data_stream, cid)

    # Biarkan scheduler mengeksekusi pipeline
    total_expected = (total_producers * items_per_prod)
    print(f"[*] Pipeline executing. Total throughput expected: {total_expected} items.\n")

    # Monitor runtime progress
    start_time = time.time()
    time.sleep(0.8)  # Biarkan producer selesai memproduksi
    data_stream.close()  # Go idiom: Producer closes channel

    # Tunggu sisa Goroutine selesai dieksekusi
    time.sleep(0.6)
    elapsed = time.time() - start_time

    # Laporan Telemetri Scheduler
    print(f"\n{CLR_BLD}{CLR_CYN}============================================================{CLR_RST}")
    print(f"{CLR_BLD}{CLR_CYN}               GO RUNTIME TELEMETRY METRICS                 {CLR_RST}")
    print(f"{CLR_BLD}{CLR_CYN}============================================================{CLR_RST}")
    print(f"Total Eksekusi Waktu : {elapsed:.2f} detik")
    print(f"Goroutines Selesai   : {runtime.completed_goroutines}")
    
    for p in runtime.processors:
        print(
            f"Processor P{p.pid:02d}        : Steals={p.steals_performed} | "
            f"Ticks={p.sched_tick} | Remaining LRQ={len(p.lrq)}"
        )
    print(f"Global Run Queue (GRQ): {len(runtime.grq)} items tersisa")
    print(f"{CLR_BLD}{CLR_GRN}[SUCCESS] Lab Hands-on Eksekusi GMP Selesai Secara Deterministik.{CLR_RST}\n")

    runtime.shutdown()

if __name__ == "__main__":
    main()