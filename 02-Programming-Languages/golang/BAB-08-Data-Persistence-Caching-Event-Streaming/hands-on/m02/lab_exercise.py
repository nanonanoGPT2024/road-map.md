#!/usr/bin/env python3
"""
Lab Hands-on: Go Runtime Architecture Deep Dive (The GMP Model & Channel Internals)
Simulates Go's Concurrency Engine:
- Goroutine (G), Machine (M), Processor (P) Scheduling
- Work-Stealing Algorithm
- Hchan ring-buffer and Sudog wait-queues (CSP model)
"""

import sys
import time
import random
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Any

# ANSI Colors
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_BG_DARK = "\033[48;5;236m"

class GState(Enum):
    IDLE = "GIDLE"
    RUNNABLE = "GRUNNABLE"
    RUNNING = "GRUNNING"
    WAITING = "GWAITING"   # Blocked on channel/syscall
    DEAD = "GDEAD"

@dataclass
class Goroutine:
    gid: int
    task_name: str
    work_units: int
    state: GState = GState.RUNNABLE
    waiting_on: Optional[str] = None

    def __str__(self):
        return f"G{self.gid} [{self.task_name}]"

class Sudog:
    """Represents a waiting goroutine in a channel send/recv queue."""
    def __init__(self, g: Goroutine, value: Any = None):
        self.g = g
        self.value = value

class Hchan:
    """
    Simulation of Go's internal 'hchan' struct:
    - qcount: elements in ring buffer
    - dataqsiz: buffer capacity
    - buf: circular buffer
    - sendq / recvq: wait queues for blocked goroutines
    - lock: protects all fields
    """
    def __init__(self, capacity: int, name: str):
        self.name = name
        self.capacity = capacity
        self.buf = deque(maxlen=capacity if capacity > 0 else 1)
        self.sendq = deque()  # Queue of Sudog waiting to send
        self.recvq = deque()  # Queue of Sudog waiting to receive
        self.lock = threading.Lock()

    def send(self, g: Goroutine, val: Any) -> bool:
        """Emulates runtime.chansend()"""
        with self.lock:
            # Case 1: An receiver is already waiting
            if self.recvq:
                sg = self.recvq.popleft()
                sg.value = val
                sg.g.state = GState.RUNNABLE
                sg.g.waiting_on = None
                return True

            # Case 2: Buffer has space
            if len(self.buf) < self.capacity:
                self.buf.append(val)
                return True

            # Case 3: Must block
            g.state = GState.WAITING
            g.waiting_on = f"chan-send({self.name})"
            self.sendq.append(Sudog(g, val))
            return False

    def recv(self, g: Goroutine) -> tuple[bool, Any]:
        """Emulates runtime.chanrecv()"""
        with self.lock:
            # Case 1: Direct handoff from waiting sender
            if self.sendq:
                sg = self.sendq.popleft()
                val = sg.value
                sg.g.state = GState.RUNNABLE
                sg.g.waiting_on = None
                if self.capacity > 0:
                    self.buf.append(val)
                    val = self.buf.popleft()
                return True, val

            # Case 2: Buffer has items
            if len(self.buf) > 0:
                val = self.buf.popleft()
                return True, val

            # Case 3: Buffer empty, must block
            g.state = GState.WAITING
            g.waiting_on = f"chan-recv({self.name})"
            self.recvq.append(Sudog(g))
            return False, None

class Processor:
    """Logical Processor (P) managing local run queue (max 256 in real Go)."""
    def __init__(self, pid: int, scheduler):
        self.pid = pid
        self.sched = scheduler
        self.runq: deque[Goroutine] = deque()
        self.runq_lock = threading.Lock()
        self.sched_tick = 0

    def push_runq(self, g: Goroutine):
        with self.runq_lock:
            g.state = GState.RUNNABLE
            self.runq.append(g)

    def pop_runq(self) -> Optional[Goroutine]:
        with self.runq_lock:
            return self.runq.popleft() if self.runq else None

    def steal_work(self, victims: List['Processor']) -> Optional[Goroutine]:
        """Implements runtime.stealWork(): Steals half from another P's runq."""
        for victim in victims:
            if victim.pid == self.pid:
                continue
            with victim.runq_lock:
                half = len(victim.runq) // 2
                if half > 0:
                    stolen = [victim.runq.popleft() for _ in range(half)]
                    with self.runq_lock:
                        for g in stolen[1:]:
                            self.runq.append(g)
                    return stolen[0]
        return None

class Machine(threading.Thread):
    """OS Thread (M) executing Goroutines bound to a Processor (P)."""
    def __init__(self, mid: int, p: Processor, sched: 'RuntimeScheduler'):
        super().__init__(daemon=True)
        self.mid = mid
        self.p = p
        self.sched = sched
        self.active_g: Optional[Goroutine] = None
        self.total_executed = 0

    def run(self):
        while not self.sched.stop_event.is_set():
            g = self.find_runnable()
            if not g:
                time.sleep(0.005)
                continue

            self.active_g = g
            g.state = GState.RUNNING
            self.sched.log_state(f"{CLR_BLUE}M{self.mid}(P{self.p.pid}){CLR_RESET} running {CLR_GREEN}{g}{CLR_RESET}")

            # Simulate CPU execution slices
            while g.work_units > 0 and not self.sched.stop_event.is_set():
                time.sleep(0.01)
                g.work_units -= 1

                # Dynamic check: Channel sync tasks
                if "worker_sender" in g.task_name and g.work_units == 1:
                    sent = self.sched.data_ch.send(g, f"data_from_g{g.gid}")
                    if not sent:
                        self.sched.log_state(f"{CLR_MAGENTA}{g} blocked on Send -> GWAITING{CLR_RESET}")
                        break

                if "worker_receiver" in g.task_name and g.work_units == 2:
                    ok, val = self.sched.data_ch.recv(g)
                    if not ok:
                        self.sched.log_state(f"{CLR_YELLOW}{g} blocked on Recv -> GWAITING{CLR_RESET}")
                        break
                    else:
                        self.sched.log_state(f"{CLR_CYAN}{g} consumed: '{val}'{CLR_RESET}")

            if g.state == GState.WAITING:
                self.sched.record_blocked(g)
            elif g.work_units <= 0:
                g.state = GState.DEAD
                self.sched.log_state(f"{CLR_GREEN}✔ {g} completed execution (GDEAD){CLR_RESET}")
                self.total_executed += 1
            
            self.active_g = None

    def find_runnable(self) -> Optional[Goroutine]:
        """GMP FindRunnable loop: Local -> Global (every 61 ticks) -> Steal"""
        self.p.sched_tick += 1
        
        # 1. Check Global Queue periodically to avoid starvation
        if self.p.sched_tick % 61 == 0:
            g = self.sched.pop_global()
            if g: return g

        # 2. Local Run Queue
        g = self.p.pop_runq()
        if g: return g

        # 3. Global Run Queue fallback
        g = self.sched.pop_global()
        if g: return g

        # 4. Work Stealing from peer Ps
        stolen = self.p.steal_work(self.sched.processors)
        if stolen:
            self.sched.log_state(
                f"{CLR_YELLOW}⚡ M{self.mid}(P{self.p.pid}) stole {stolen} from peer P!{CLR_RESET}"
            )
            return stolen

        return None

class RuntimeScheduler:
    """Simulates the Go Runtime Management layer."""
    def __init__(self, gomaxprocs: int):
        self.gomaxprocs = gomaxprocs
        self.processors: List[Processor] = [Processor(i, self) for i in range(gomaxprocs)]
        self.global_runq: deque[Goroutine] = deque()
        self.global_lock = threading.Lock()
        self.machines: List[Machine] = []
        self.stop_event = threading.Event()
        self.blocked_pool: List[Goroutine] = []
        self.print_lock = threading.Lock()
        
        # Internal Go buffered channel simulation
        self.data_ch = Hchan(capacity=1, name="ch_buffer_1")

    def log_state(self, message: str):
        with self.print_lock:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] {message}")

    def pop_global(self) -> Optional[Goroutine]:
        with self.global_lock:
            return self.global_runq.popleft() if self.global_runq else None

    def push_global(self, g: Goroutine):
        with self.global_lock:
            g.state = GState.RUNNABLE
            self.global_runq.append(g)

    def record_blocked(self, g: Goroutine):
        with self.global_lock:
            self.blocked_pool.append(g)

    def wake_blocked(self):
        """Sysmon-like checker waking up unblocked goroutines."""
        with self.global_lock:
            resumed = [g for g in self.blocked_pool if g.state == GState.RUNNABLE]
            for g in resumed:
                self.blocked_pool.remove(g)
                # Dispatch back to P0
                self.processors[0].push_runq(g)
                self.log_state(f"{CLR_CYAN}↺ Sysmon unblocked {g}, reenqueued to P0{CLR_RESET}")

    def start(self):
        self.machines = [Machine(i, self.processors[i], self) for i in range(self.gomaxprocs)]
        for m in self.machines:
            m.start()

    def stop(self):
        self.stop_event.set()
        for m in self.machines:
            m.join()

def main():
    print(f"{CLR_BOLD}{CLR_BG_DARK}=== GO RUNTIME INTERNALS: GMP & CSP CHANNEL LAB ==={CLR_RESET}\n")
    print(f"Configuring Runtime: {CLR_CYAN}GOMAXPROCS = 2{CLR_RESET} (2 Processors, 2 OS Threads)")
    
    sched = RuntimeScheduler(gomaxprocs=2)
    sched.start()

    # Pre-populate P0 heavily to trigger Work-Stealing from P1
    print(f"\n{CLR_BOLD}[1] Injecting Goroutines into P0 Local RunQ...{CLR_RESET}")
    heavy_jobs = [
        Goroutine(gid=1, task_name="calc_hash", work_units=3),
        Goroutine(gid=2, task_name="compress_block", work_units=4),
        Goroutine(gid=3, task_name="parse_json", work_units=3),
        Goroutine(gid=4, task_name="render_template", work_units=2),
    ]
    for g in heavy_jobs:
        sched.processors[0].push_runq(g)

    # Let M0 and M1 execute; M1 will steal from M0 immediately
    time.sleep(0.12)

    # Inject Goroutines with Channel dependency
    print(f"\n{CLR_BOLD}[2] Injecting CSP Channel Producer/Consumer Goroutines...{CLR_RESET}")
    g_sender = Goroutine(gid=10, task_name="worker_sender", work_units=3)
    g_receiver = Goroutine(gid=11, task_name="worker_receiver", work_units=4)
    
    # Enqueue receiver first (will block on empty channel)
    sched.processors[1].push_runq(g_receiver)
    time.sleep(0.08)
    
    # Enqueue sender (will satisfy channel recv and resume G11)
    sched.processors[0].push_runq(g_sender)

    # Monitor loop
    for _ in range(15):
        sched.wake_blocked()
        time.sleep(0.05)

    sched.stop()

    print(f"\n{CLR_BOLD}=== RUNTIME BENCHMARK & METRICS SUMMARY ==={CLR_RESET}")
    for m in sched.machines:
        print(f"Thread M{m.mid} (attached to P{m.p.pid}): Processed {CLR_GREEN}{m.total_executed}{CLR_RESET} Goroutines")

    print(f"\nFinal Channel Status: '{sched.data_ch.name}'")
    print(f"- Buffered items left: {len(sched.data_ch.buf)}/{sched.data_ch.capacity}")
    print(f"- Blocked senders  (sendq): {len(sched.data_ch.sendq)}")
    print(f"- Blocked receivers (recvq): {len(sched.data_ch.recvq)}")
    print(f"\n{CLR_GREEN}Lab completed successfully.{CLR_RESET}")

if __name__ == "__main__":
    main()