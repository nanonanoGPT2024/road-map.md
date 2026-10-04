#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi dan Arsitektur Runtime JavaScript (V8 Engine Model)
BAB-01: Fondasi dan Arsitektur JavaScript

Materi yang Disimulasikan:
1. Memory Heap & Garbage Collection Basics (Primitive vs Reference Allocation)
2. Call Stack & Execution Context (Creation & Execution Phase, LIFO)
3. Event Loop, Microtask Queue (Promise.then/queueMicrotask), dan Macrotask Queue (setTimeout/I/O)
"""

import sys
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Color:
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
    BG_MAGENTA = "\033[45m"


class TaskType(Enum):
    MICROTASK = "Microtask (Promise/queueMicrotask)"
    MACROTASK = "Macrotask (setTimeout/setInterval/IO)"


@dataclass
class Task:
    name: str
    task_type: TaskType
    callback_payload: str
    delay_ms: int = 0


@dataclass
class StackFrame:
    function_name: str
    scope_variables: Dict[str, Any] = field(default_factory=dict)
    line_number: int = 1


class JSRuntimeSimulator:
    def __init__(self):
        self.call_stack: List[StackFrame] = []
        self.microtask_queue: deque[Task] = deque()
        self.macrotask_queue: deque[Task] = deque()
        self.memory_heap: Dict[str, Any] = {}
        self.heap_address_counter = 0x1000

    def print_header(self, title: str):
        print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {title} === {Color.RESET}")

    def log(self, tag: str, msg: str, color: str = Color.WHITE):
        print(f"{Color.DIM}[{time.strftime('%H:%M:%S')}]{Color.RESET} {color}[{tag}]{Color.RESET} {msg}")

    # --- 1. MEMORY MANAGEMENT (HEAP & STACK) ---
    def allocate_variable(self, var_name: str, value: Any, is_reference: bool = False):
        if is_reference:
            addr = f"0x{self.heap_address_counter:04X}"
            self.heap_address_counter += 4
            self.memory_heap[addr] = value
            stored_val = f"<Ref: {addr}>"
            self.log(
                "HEAP ALLOC",
                f"Objek dialokasikan di Heap {Color.CYAN}{addr}{Color.RESET} -> {value}",
                Color.CYAN,
            )
        else:
            stored_val = value
            self.log("STACK ALLOC", f"Primitive dialokasikan di Stack: {var_name} = {value}", Color.GREEN)

        if self.call_stack:
            self.call_stack[-1].scope_variables[var_name] = stored_val
        else:
            self.log("GLOBAL", f"Variabel {var_name} masuk ke Global Execution Context", Color.YELLOW)

    # --- 2. CALL STACK & EXECUTION CONTEXT ---
    def push_call_stack(self, fn_name: str, args: Dict[str, Any]):
        frame = StackFrame(function_name=fn_name, scope_variables=args)
        self.call_stack.append(frame)
        self.log(
            "CALL STACK",
            f"{Color.BOLD}PUSH{Color.RESET} -> {Color.MAGENTA}{fn_name}(){Color.RESET} "
            f"(Kedalaman Stack: {len(self.call_stack)})",
            Color.MAGENTA,
        )
        self.render_runtime_state()

    def pop_call_stack(self):
        if self.call_stack:
            popped = self.call_stack.pop()
            self.log(
                "CALL STACK",
                f"{Color.BOLD}POP{Color.RESET}  <- {Color.MAGENTA}{popped.function_name}(){Color.RESET} "
                f"(Sisa Frame: {len(self.call_stack)})",
                Color.MAGENTA,
            )
            self.render_runtime_state()
            return popped
        return None

    # --- 3. WEB API / ASYNC QUEUES ---
    def queue_async_task(self, task: Task):
        if task.task_type == TaskType.MICROTASK:
            self.microtask_queue.append(task)
            self.log(
                "WEB API -> MICRO",
                f"Menjadwalkan {Color.YELLOW}{task.name}{Color.RESET} ke Microtask Queue",
                Color.YELLOW,
            )
        else:
            self.macrotask_queue.append(task)
            self.log(
                "WEB API -> MACRO",
                f"Timer selesai, memasukkan {Color.RED}{task.name}{Color.RESET} ke Macrotask Queue",
                Color.RED,
            )

    # --- 4. EVENT LOOP TICK ENGINE ---
    def run_event_loop_tick(self):
        self.log("EVENT LOOP", "Memeriksa Call Stack...", Color.BLUE)

        # Aturan JS: Event loop hanya mengambil task saat Call Stack benar-benar kosong!
        if len(self.call_stack) > 0:
            self.log("EVENT LOOP", "Call stack masih sibuk (Synchronous code berjalan). Menunggu...", Color.YELLOW)
            return

        # Prioritas 1: Kuras seluruh Microtask Queue terlebih dahulu (Starvation risk)
        if self.microtask_queue:
            self.log("EVENT LOOP", f"{Color.BOLD}Menguras Microtask Queue!{Color.RESET}", Color.YELLOW)
            while self.microtask_queue:
                task = self.microtask_queue.popleft()
                self.log("EXECUTE MICRO", f"Menjalankan microtask: {task.name}", Color.YELLOW)
                self.push_call_stack(f"cb_{task.name}", {"detail": task.callback_payload})
                time.sleep(0.3)
                self.pop_call_stack()
            return

        # Prioritas 2: Ambil TEPAT SATU Macrotask, lalu beri kesempatan render/microtask baru
        if self.macrotask_queue:
            task = self.macrotask_queue.popleft()
            self.log("EXECUTE MACRO", f"Menjalankan macrotask: {task.name}", Color.RED)
            self.push_call_stack(f"cb_{task.name}", {"detail": task.callback_payload})
            time.sleep(0.3)
            self.pop_call_stack()
            return

        self.log("EVENT LOOP", "Idle: Tidak ada task tersisa di queue.", Color.GREEN)

    # --- 5. VISUAL INSPECTION DASHBOARD ---
    def render_runtime_state(self):
        print(f"\n{Color.CYAN}{'─' * 60}{Color.RESET}")
        print(f"{Color.BOLD}STATUS RUNTIME JAVASCRIPT:{Color.RESET}")

        # Visual Call Stack
        stack_str = " | ".join(f"[{f.function_name}]" for f in reversed(self.call_stack)) or "[ EMPTY ]"
        print(f" {Color.MAGENTA}Call Stack (Top -> Bottom):{Color.RESET} {stack_str}")

        # Visual Microtask Queue
        micro_str = " -> ".join(f"[{t.name}]" for t in self.microtask_queue) or "[ Empty ]"
        print(f" {Color.YELLOW}Microtask Queue (FIFO)   :{Color.RESET} {micro_str}")

        # Visual Macrotask Queue
        macro_str = " -> ".join(f"[{t.name}]" for t in self.macrotask_queue) or "[ Empty ]"
        print(f" {Color.RED}Macrotask Queue (FIFO)   :{Color.RESET} {macro_str}")

        # Visual Heap
        print(f" {Color.BLUE}Memory Heap Entries       :{Color.RESET} {len(self.memory_heap)} objek")
        for addr, val in self.memory_heap.items():
            print(f"    {Color.DIM}{addr}:{Color.RESET} {val}")
        print(f"{Color.CYAN}{'─' * 60}{Color.RESET}\n")


def demo_simulation():
    engine = JSRuntimeSimulator()
    engine.print_header("SIMULASI 1: Eksekusi Kode Synchronous vs Asynchronous")

    code_snippet = """
    console.log("1. Script Start");
    setTimeout(() => console.log("2. setTimeout (Macro)"), 0);
    Promise.resolve().then(() => console.log("3. Promise Microtask 1"));
    queueMicrotask(() => console.log("4. queueMicrotask 2"));
    console.log("5. Script End");
    """
    print(f"{Color.WHITE}{code_snippet}{Color.RESET}")

    # Langkah 1: Script Start (Global Context)
    engine.push_call_stack("global_main", {})
    engine.allocate_variable("sessionUser", {"name": "Budi", "role": "Engineer"}, is_reference=True)
    engine.allocate_variable("counter", 42, is_reference=False)

    print(f"{Color.GREEN}>>> Output JS: '1. Script Start'{Color.RESET}")
    time.sleep(0.4)

    # Langkah 2: setTimeout dipanggil (Web API menaruh ke Macrotask Queue)
    engine.push_call_stack("setTimeout", {"delay": 0})
    engine.queue_async_task(Task("setTimeout_CB", TaskType.MACROTASK, "Output: '2. setTimeout (Macro)'"))
    engine.pop_call_stack()
    time.sleep(0.4)

    # Langkah 3: Promise resolve (Menaruh ke Microtask Queue)
    engine.push_call_stack("Promise.resolve().then", {})
    engine.queue_async_task(Task("Promise_CB_1", TaskType.MICROTASK, "Output: '3. Promise Microtask 1'"))
    engine.pop_call_stack()
    time.sleep(0.4)

    # Langkah 4: queueMicrotask dipanggil
    engine.push_call_stack("queueMicrotask", {})
    engine.queue_async_task(Task("Microtask_CB_2", TaskType.MICROTASK, "Output: '4. queueMicrotask 2'"))
    engine.pop_call_stack()
    time.sleep(0.4)

    # Langkah 5: Script End
    print(f"{Color.GREEN}>>> Output JS: '5. Script End'{Color.RESET}")
    engine.pop_call_stack()  # Global Execution Context selesai!

    engine.print_header("FASE EVENT LOOP AKTIF")
    print(f"{Color.YELLOW}Call Stack kini kosong! Event loop mulai memproses antrean asynchronous...{Color.RESET}")

    while engine.microtask_queue or engine.macrotask_queue:
        engine.run_event_loop_tick()
        time.sleep(0.5)

    engine.print_header("KESIMPULAN EKSEKUSI RUNTIME")
    print(f"""
{Color.GREEN}Urutan Output Nyata JavaScript:{Color.RESET}
  1. Script Start            {Color.DIM}(Sync di Call Stack){Color.RESET}
  2. Script End              {Color.DIM}(Sync di Call Stack){Color.RESET}
  3. Promise Microtask 1     {Color.YELLOW}(Microtask Queue diprioritaskan){Color.RESET}
  4. queueMicrotask 2        {Color.YELLOW}(Microtask Queue dikuras habis){Color.RESET}
  5. setTimeout (Macro)      {Color.RED}(Macrotask Queue dieksekusi setelah microtask kosong){Color.RESET}
    """)


def interactive_menu():
    engine = JSRuntimeSimulator()
    while True:
        print(f"\n{Color.BOLD}{Color.CYAN}--- JS ENGINE INTERACTIVE SIMULATOR (BAB 01) ---{Color.RESET}")
        print("1. Jalankan Skrip Demo Lengkap (Call Stack + Event Loop)")
        print("2. Simulasikan Alokasi Memory (Stack vs Heap)")
        print("3. Simulasikan Push/Pop Call Stack (Stack Overflow Demo)")
        print("4. Keluar")
        choice = input(f"{Color.YELLOW}Pilih menu (1-4): {Color.RESET}").strip()

        if choice == "1":
            demo_simulation()
        elif choice == "2":
            engine.print_header("Simulasi Memory Heap vs Stack")
            var_name = input("Masukkan nama variabel (misal: user / count): ").strip() or "testVar"
            is_ref = input("Tipe data reference/objek? (y/n): ").strip().lower() == "y"
            val = {"sample": "object"} if is_ref else 100
            engine.allocate_variable(var_name, val, is_reference=is_ref)
            engine.render_runtime_state()
        elif choice == "3":
            engine.print_header("Call Stack Overflow Guard Simulation")
            depth = input("Masukkan kedalaman rekursi fungsi (misal: 5): ").strip()
            try:
                d = int(depth)
                for i in range(1, d + 1):
                    engine.push_call_stack(f"recursiveFunction_{i}", {"depth": i})
                    time.sleep(0.1)
                for _ in range(d):
                    engine.pop_call_stack()
                    time.sleep(0.1)
            except ValueError:
                print(f"{Color.RED}Input angka tidak valid.{Color.RESET}")
        elif choice == "4":
            print(f"{Color.GREEN}Terima kasih telah mempelajari Arsitektur JavaScript V8!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid.{Color.RESET}")


if __name__ == "__main__":
    # Jika dijalankan secara non-interaktif atau dengan argumen --demo
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo_simulation()
    elif not sys.stdin.isatty():
        # Fallback otomatis saat piping atau automated test runner
        demo_simulation()
    else:
        interactive_menu()
