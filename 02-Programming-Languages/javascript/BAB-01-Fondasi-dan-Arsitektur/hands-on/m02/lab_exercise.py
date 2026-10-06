#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Runtime & Engine JavaScript (V8 & Event Loop)
BAB-01: Fondasi dan Arsitektur JavaScript Tingkat Lanjut

Modul interaktif ini memodelkan:
1. V8 Engine Pipeline (Parser -> AST -> Ignition Bytecode -> TurboFan JIT Optimization)
2. Memory Heap & Garbage Collection (Scavenger / Minor GC vs Mark-Sweep / Major GC)
3. Call Stack, Microtask Queue (Promises, queueMicrotask), dan Macrotask Queue (setTimeout, I/O)
4. Event Loop Ticking Mechanism & Starvation Detection
"""

from __future__ import annotations
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Deque, Dict, List, Optional


class AnsiColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[48;5;236m"


class TaskType(Enum):
    SYNC = auto()
    MICROTASK = auto()
    MACROTASK = auto()


class CompilationTier(Enum):
    PARSED = "AST"
    BYTECODE = "Ignition (Bytecode)"
    OPTIMIZED = "TurboFan (Optimized Machine Code)"
    DEOPTIMIZED = "Bailout / Deopt"


@dataclass
class StackFrame:
    fn_name: str
    tier: CompilationTier = CompilationTier.BYTECODE
    execution_cost_ms: float = 1.0


@dataclass
class EventTask:
    name: str
    task_type: TaskType
    payload: str
    created_at: float = field(default_factory=time.time)


@dataclass
class HeapObject:
    obj_id: str
    size_kb: int
    generation: int = 0  # 0: Nursery/From-Space, 1: Old-Space
    marked: bool = False


class V8EngineSimulator:
    def __init__(self) -> None:
        self.call_stack: List[StackFrame] = []
        self.microtask_queue: Deque[EventTask] = deque()
        self.macrotask_queue: Deque[EventTask] = deque()
        self.heap: Dict[str, HeapObject] = {}
        self.next_obj_counter: int = 1
        self.gc_minor_count: int = 0
        self.gc_major_count: int = 0
        self.loop_tick_count: int = 0

    def print_banner(self) -> None:
        print(f"{AnsiColor.CYAN}{'=' * 72}{AnsiColor.RESET}")
        print(f"{AnsiColor.BOLD}{AnsiColor.GREEN}  SIMULATOR ARSITEKTUR RUNTIME JAVASCRIPT & V8 ENGINE INTERAKTIF{AnsiColor.RESET}")
        print(f"{AnsiColor.DIM}  Mendemonstrasikan Call Stack, Event Loop, Microtasks & V8 JIT Tiers{AnsiColor.RESET}")
        print(f"{AnsiColor.CYAN}{'=' * 72}{AnsiColor.RESET}\n")

    def allocate_heap(self, size_kb: int) -> str:
        obj_id = f"ref_{self.next_obj_counter:04d}"
        self.next_obj_counter += 1
        self.heap[obj_id] = HeapObject(obj_id=obj_id, size_kb=size_kb, generation=0)
        return obj_id

    def run_minor_gc(self) -> None:
        """Minor GC (Scavenger) mengolah Nursery / Semi-Space (Generational GC)."""
        self.gc_minor_count += 1
        promoted = 0
        freed_kb = 0
        for obj in list(self.heap.values()):
            if obj.generation == 0:
                if obj.marked:
                    obj.generation = 1
                    obj.marked = False
                    promoted += 1
                else:
                    freed_kb += obj.size_kb
                    del self.heap[obj.obj_id]

        print(f"{AnsiColor.YELLOW}[V8 Minor GC / Scavenger]{AnsiColor.RESET} "
              f"Membersihkan young generation: {freed_kb} KB dibebaskan, {promoted} objek dipromosikan ke Old-Space.")

    def run_major_gc(self) -> None:
        """Major GC (Mark-Sweep-Compact) untuk Old Space."""
        self.gc_major_count += 1
        freed_kb = 0
        for obj in list(self.heap.values()):
            if not obj.marked:
                freed_kb += obj.size_kb
                del self.heap[obj.obj_id]
            else:
                obj.marked = False

        print(f"{AnsiColor.MAGENTA}[V8 Major GC / Mark-Sweep]{AnsiColor.RESET} "
              f"Full sweep selesai: {freed_kb} KB dibebaskan dari Old-Space.")

    def render_state(self) -> None:
        print(f"\n{AnsiColor.BOLD}--- [STATUS RUNTIME ENGINE V8] ---{AnsiColor.RESET}")
        
        # Call Stack
        stack_repr = " -> ".join([f"{f.fn_name} ({f.tier.value})" for f in self.call_stack]) or "(Empty)"
        print(f"{AnsiColor.BLUE}Call Stack        :{AnsiColor.RESET} [{stack_repr}]")
        
        # Microtask Queue
        micro_repr = " | ".join([t.name for t in self.microtask_queue]) or "(Empty)"
        print(f"{AnsiColor.GREEN}Microtask Queue   :{AnsiColor.RESET} [{micro_repr}] (Promises / queueMicrotask)")
        
        # Macrotask Queue
        macro_repr = " | ".join([t.name for t in self.macrotask_queue]) or "(Empty)"
        print(f"{AnsiColor.YELLOW}Macrotask Queue   :{AnsiColor.RESET} [{macro_repr}] (setTimeout / I/O / setImmediate)")
        
        # Heap Memory
        total_kb = sum(o.size_kb for o in self.heap.values())
        print(f"{AnsiColor.WHITE}V8 Heap Memory    :{AnsiColor.RESET} {len(self.heap)} objek aktif ({total_kb} KB) | Minor GC: {self.gc_minor_count}, Major GC: {self.gc_major_count}")
        print(f"{AnsiColor.CYAN}Event Loop Ticks  :{AnsiColor.RESET} {self.loop_tick_count}")
        print("-" * 50)

    def push_call_stack(self, fn_name: str, tier: CompilationTier = CompilationTier.BYTECODE) -> None:
        print(f"{AnsiColor.BLUE}>> PUSH Call Stack:{AnsiColor.RESET} {fn_name} [{tier.value}]")
        self.call_stack.append(StackFrame(fn_name=fn_name, tier=tier))

    def pop_call_stack(self) -> Optional[StackFrame]:
        if self.call_stack:
            frame = self.call_stack.pop()
            print(f"{AnsiColor.BLUE}<< POP Call Stack :{AnsiColor.RESET} {frame.fn_name}")
            return frame
        return None

    def schedule_microtask(self, name: str, payload: str = "") -> None:
        print(f"{AnsiColor.GREEN}[+ Enqueue Microtask]:{AnsiColor.RESET} {name} (prioritas tinggi)")
        self.microtask_queue.append(EventTask(name=name, task_type=TaskType.MICROTASK, payload=payload))

    def schedule_macrotask(self, name: str, payload: str = "") -> None:
        print(f"{AnsiColor.YELLOW}[+ Enqueue Macrotask]:{AnsiColor.RESET} {name} (delegasi ke Libuv/WebAPI timer)")
        self.macrotask_queue.append(EventTask(name=name, task_type=TaskType.MACROTASK, payload=payload))

    def run_event_loop_tick(self) -> bool:
        """
        Menjalankan 1 Tick Siklus Event Loop:
        1. Eksekusi 1 macrotask terdepan jika Call Stack kosong
        2. DRAIN seluruh antrian Microtask sampai tuntas (microtask checkpoint)
        3. Render phase (jika ada peramban/UI)
        """
        self.loop_tick_count += 1
        print(f"\n{AnsiColor.BOLD}{AnsiColor.CYAN}=== EVENT LOOP TICK #{self.loop_tick_count} START ==={AnsiColor.RESET}")

        # Pastikan Call Stack synchronous selesai terlebih dahulu
        while self.call_stack:
            frame = self.pop_call_stack()
            time.sleep(0.05)

        # 1. Eksekusi 1 Macrotask jika ada
        if self.macrotask_queue:
            macro = self.macrotask_queue.popleft()
            print(f"{AnsiColor.YELLOW}--> Menjalankan Macrotask:{AnsiColor.RESET} {macro.name}")
            self.push_call_stack(f"exec_{macro.name}", CompilationTier.BYTECODE)
            self.pop_call_stack()
        else:
            print(f"{AnsiColor.DIM}--> Tidak ada Macrotask baru.{AnsiColor.RESET}")

        # 2. Microtask Checkpoint: Drain Microtask Queue
        if self.microtask_queue:
            print(f"{AnsiColor.GREEN}--> Memulai Microtask Checkpoint (Draining queue)...{AnsiColor.RESET}")
            micro_counter = 0
            while self.microtask_queue:
                micro = self.microtask_queue.popleft()
                micro_counter += 1
                print(f"    {AnsiColor.GREEN}* Microtask #{micro_counter}:{AnsiColor.RESET} {micro.name} (Resolved Promise callback)")
                self.push_call_stack(f"micro_{micro.name}", CompilationTier.OPTIMIZED)
                self.pop_call_stack()
                
                # Deteksi potensi microtask starvation jika looping tanpa henti
                if micro_counter > 15:
                    print(f"{AnsiColor.RED}[PERINGATAN]: Terdeteksi Microtask Starvation! Macrotasks terblokir.{AnsiColor.RESET}")
                    break
        else:
            print(f"{AnsiColor.DIM}--> Microtask queue bersih.{AnsiColor.RESET}")

        print(f"{AnsiColor.BOLD}{AnsiColor.CYAN}=== TICK #{self.loop_tick_count} COMPLETED ==={AnsiColor.RESET}\n")
        return bool(self.microtask_queue or self.macrotask_queue or self.call_stack)

    def run_preconfigured_scenario(self) -> None:
        """Simulasi kasus nyata: Promise vs setTimeout vs Sync execution."""
        print(f"\n{AnsiColor.BOLD}Memulai skenario simulasi asynchronous JavaScript:{AnsiColor.RESET}")
        print("""
  console.log('1: Synchronous start');
  setTimeout(() => console.log('2: setTimeout timer callback'), 0);
  Promise.resolve().then(() => console.log('3: Promise microtask 1'))
                   .then(() => console.log('4: Promise microtask 2'));
  console.log('5: Synchronous end');
        """)
        
        # Alokasikan beberapa closure di heap
        o1 = self.allocate_heap(32)
        o2 = self.allocate_heap(64)
        self.heap[o1].marked = True  # Dijadikan reachable

        # Step 1: Sync code
        self.push_call_stack("global_main", CompilationTier.BYTECODE)
        self.push_call_stack("console.log('1: Synchronous start')")
        self.pop_call_stack()

        # Step 2: setTimeout
        self.push_call_stack("setTimeout_call")
        self.schedule_macrotask("TimerCallback(2)", "setTimeout 0ms")
        self.pop_call_stack()

        # Step 3: Promise resolve
        self.push_call_stack("Promise.resolve")
        self.schedule_microtask("PromiseCallback(3)", "then chain 1")
        self.pop_call_stack()

        # Step 4: Sync end
        self.push_call_stack("console.log('5: Synchronous end')")
        self.pop_call_stack()
        self.pop_call_stack()  # pop global_main

        self.render_state()

        print(f"{AnsiColor.YELLOW}Menjalankan siklus Event Loop untuk mengosongkan antrian...{AnsiColor.RESET}")
        while self.run_event_loop_tick():
            self.render_state()
            time.sleep(0.1)

        # Demonstrasi Minor GC
        print(f"\n{AnsiColor.CYAN}Menjalankan uji siklus V8 Generational Garbage Collection:{AnsiColor.RESET}")
        self.run_minor_gc()
        self.render_state()


def interactive_cli() -> None:
    simulator = V8EngineSimulator()
    simulator.print_banner()

    menu = f"""
{AnsiColor.BOLD}PILIHAN OPERASI SIMULASI V8 RUNTIME:{AnsiColor.RESET}
  [1] Jalankan Skenario Standar (Sync -> Promise Microtask -> Macrotask)
  [2] Tambahkan Synchronous Function ke Call Stack
  [3] Jadwalkan Microtask (Promise callback / queueMicrotask)
  [4] Jadwalkan Macrotask (setTimeout / Libuv I/O)
  [5] Alokasikan Objek Heap V8 & Uji Minor/Major GC
  [6] Eksekusi 1 Tick Event Loop
  [7] Render Status Lengkap Engine
  [8] Bersihkan Engine / Reset
  [0] Keluar
"""

    while True:
        print(menu)
        try:
            choice = input(f"{AnsiColor.BOLD}Pilih opsi [0-8]: {AnsiColor.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSesi dihentikan.")
            break

        if choice == "1":
            simulator.run_preconfigured_scenario()
        elif choice == "2":
            fn = input("Nama fungsi (misal: calculateHash): ").strip() or "anonFunction"
            tier_in = input("JIT Tier (1: AST, 2: Ignition, 3: TurboFan) [default 2]: ").strip()
            tier = CompilationTier.OPTIMIZED if tier_in == "3" else (CompilationTier.PARSED if tier_in == "1" else CompilationTier.BYTECODE)
            simulator.push_call_stack(fn, tier)
            simulator.render_state()
        elif choice == "3":
            name = input("Label microtask (misal: Promise.then): ").strip() or "anonymousMicrotask"
            simulator.schedule_microtask(name)
            simulator.render_state()
        elif choice == "4":
            name = input("Label macrotask (misal: timer_50ms): ").strip() or "anonymousTimer"
            simulator.schedule_macrotask(name)
            simulator.render_state()
        elif choice == "5":
            try:
                size = int(input("Ukuran alokasi memori objek (KB) [default 48]: ").strip() or "48")
            except ValueError:
                size = 48
            ref = simulator.allocate_heap(size)
            print(f"Objek dibuat di Nursery Heap dengan ID: {ref}")
            gc_choice = input("Jalankan GC sekarang? (m: Minor GC, M: Major GC, n: Tidak) [n]: ").strip()
            if gc_choice == "m":
                simulator.run_minor_gc()
            elif gc_choice == "M":
                simulator.run_major_gc()
            simulator.render_state()
        elif choice == "6":
            simulator.run_event_loop_tick()
            simulator.render_state()
        elif choice == "7":
            simulator.render_state()
        elif choice == "8":
            simulator = V8EngineSimulator()
            print(f"{AnsiColor.GREEN}Engine direset ke state awal.{AnsiColor.RESET}")
            simulator.render_state()
        elif choice == "0":
            print(f"{AnsiColor.GREEN}Selesai. Selamat mempelajari arsitektur JavaScript!{AnsiColor.RESET}")
            break
        else:
            print(f"{AnsiColor.RED}Pilihan tidak valid.{AnsiColor.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        sim = V8EngineSimulator()
        sim.print_banner()
        sim.run_preconfigured_scenario()
    else:
        interactive_cli()
