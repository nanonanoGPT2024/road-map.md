#!/usr/bin/env python3
"""
Lab Hands-on: Inti Bahasa JavaScript (ECMAScript Modern) - Eksekusi & Data
Simulasi Engine JavaScript V8/SpiderMonkey Sederhana:
1. Heap Memory Allocation & Value vs Reference Semantics.
2. Execution Context, Call Stack & Lexical Environment (Scope Chain & Closures).
3. Concurrency Model: Event Loop (Call Stack, Microtask Queue, Macrotask Queue).
"""

import sys
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

# ANSI Color Codes untuk visualisasi terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[40m"


class HeapObject:
    """Representasi object di JavaScript Heap Memory dengan pointer identity."""
    def __init__(self, data: dict):
        self.data = data
        self.address = f"0x{id(self):x}"

    def __repr__(self):
        return f"<HeapObject @ {self.address} {self.data}>"


class LexicalEnvironment:
    """
    Representasi Lexical Environment ECMAScript:
    Terdiri dari Environment Record (bindings) dan pointer ke Outer Environment (Scope Chain).
    """
    def __init__(self, name: str, outer: Optional['LexicalEnvironment'] = None):
        self.name = name
        self.record: Dict[str, Any] = {}
        self.outer = outer

    def declare(self, key: str, value: Any):
        """Deklarasi variabel (let / const / var model)."""
        self.record[key] = value

    def resolve(self, key: str) -> Any:
        """Scope Chain Lookup: mencari variabel dari inner ke outer scope."""
        if key in self.record:
            return self.record[key]
        if self.outer is not None:
            return self.outer.resolve(key)
        raise NameError(f"ReferenceError: '{key}' is not defined")

    def mutate(self, key: str, value: Any):
        """Mutasi variabel pada scope tempat variabel tersebut dideklarasikan."""
        if key in self.record:
            self.record[key] = value
        elif self.outer is not None:
            self.outer.mutate(key, value)
        else:
            raise NameError(f"ReferenceError: Cannot assign to undeclared variable '{key}'")


class ExecutionContext:
    """Representasi Stack Frame pada Call Stack."""
    def __init__(self, name: str, env: LexicalEnvironment):
        self.name = name
        self.env = env


class JSEngineRuntime:
    """
    Mesin virtual runtime yang memodelkan Call Stack,
    Heap, Microtask Queue (Promise), dan Macrotask Queue (setTimeout/IO).
    """
    def __init__(self):
        self.heap: Dict[str, HeapObject] = {}
        self.call_stack: List[ExecutionContext] = []
        self.microtask_queue: deque = deque()
        self.macrotask_queue: deque = deque()
        self.global_env = LexicalEnvironment("GlobalScope")
        self.push_context("GlobalContext", self.global_env)

    def allocate_object(self, initial_data: dict) -> HeapObject:
        """Alokasi memori objek ke Heap (Reference Type)."""
        obj = HeapObject(initial_data.copy())
        self.heap[obj.address] = obj
        return obj

    def push_context(self, name: str, env: LexicalEnvironment):
        """Push frame ke Call Stack."""
        ctx = ExecutionContext(name, env)
        self.call_stack.append(ctx)

    def pop_context(self):
        """Pop frame dari Call Stack setelah fungsi return."""
        if self.call_stack:
            return self.call_stack.pop()
        return None

    def current_context(self) -> ExecutionContext:
        return self.call_stack[-1]

    def queue_microtask(self, name: str, task: Callable[[], None]):
        """Menambahkan callback Promise.then() / queueMicrotask ke Microtask Queue."""
        self.microtask_queue.append((name, task))

    def set_timeout(self, name: str, delay_ms: int, callback: Callable[[], None]):
        """Menambahkan timer/macrotask callback ke Macrotask Queue."""
        # Dalam engine sungguhan, delay diproses oleh Web API host environment
        self.macrotask_queue.append((name, delay_ms, callback))

    def run_event_loop(self):
        """
        Siklus Event Loop JavaScript:
        1. Jalankan synchronous frame pada Call Stack sampai kosong.
        2. DRAIN seluruh Microtask Queue (Promise callbacks).
        3. Ambil SATU Macrotask teratas, jalankan ke Call Stack.
        4. Ulangi Microtask drain, lalu lanjut ke frame berikutnya.
        """
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== MEMULAI EVENT LOOP SIMULATOR ==={CLR_RESET}")
        
        step = 1
        while self.call_stack or self.microtask_queue or self.macrotask_queue:
            print(f"\n{CLR_YELLOW}[Tick {step}]{CLR_RESET}")
            
            # 1. Habiskan Call Stack (Synchronous frames)
            while len(self.call_stack) > 1: # Sisakan global context
                frame = self.pop_context()
                print(f"  {CLR_RED}Call Stack Pop:{CLR_RESET} Keluar dari {frame.name}")

            # 2. Drain ALL Microtasks
            if self.microtask_queue:
                print(f"  {CLR_MAGENTA}Microtask Queue Draining ({len(self.microtask_queue)} task)...{CLR_RESET}")
                while self.microtask_queue:
                    name, task = self.microtask_queue.popleft()
                    print(f"    -> Eksekusi Microtask: {CLR_BOLD}{name}{CLR_RESET}")
                    task()
                continue

            # 3. Process exactly ONE Macrotask
            if self.macrotask_queue:
                name, delay, task = self.macrotask_queue.popleft()
                print(f"  {CLR_BLUE}Macrotask Dipilih (delay ~{delay}ms): {CLR_BOLD}{name}{CLR_RESET}")
                task()
                step += 1
                continue

            # Jika tersisa hanya Global Context dan tidak ada queue
            if len(self.call_stack) == 1 and not self.microtask_queue and not self.macrotask_queue:
                self.pop_context()
                print(f"  {CLR_RED}Call Stack Pop:{CLR_RESET} Selesai Global Context. Runtime idle.")
                break


def demo_value_vs_reference(runtime: JSEngineRuntime):
    """
    Eksperimen 1: Value vs Reference Semantics
    Menunjukkan perbedaan mutasi tipe primitif vs tipe referensi di memori.
    """
    print(f"\n{CLR_BOLD}{CLR_GREEN}[EXPERIMENT 1] Value Semantics (Primitive) vs Reference Semantics (Object){CLR_RESET}")
    env = runtime.current_context().env

    # 1. Primitive: Copy by value
    a = 42
    b = a
    b += 10
    env.declare("a", a)
    env.declare("b", b)
    print(f"  Primitive: let a = {a}; let b = a; b += 10;")
    print(f"  Hasil di stack: a = {env.resolve('a')}, b = {env.resolve('b')} (Terisolasi)")

    # 2. Reference: Copy pointer
    user_obj = runtime.allocate_object({"id": 101, "role": "developer"})
    env.declare("user1", user_obj)
    
    # user2 mengarah ke memory heap pointer yang sama
    env.declare("user2", user_obj)
    
    # Mutasi via referensi user2
    ref_target: HeapObject = env.resolve("user2")
    ref_target.data["role"] = "tech-lead"

    resolved_user1: HeapObject = env.resolve("user1")
    print(f"  Heap Object: let user1 = {{role: 'developer'}}; let user2 = user1;")
    print(f"  Mutasi: user2.role = 'tech-lead';")
    print(f"  Hasil Lookup user1.role: {resolved_user1.data['role']}")
    print(f"  Pointer Identity: user1({user_obj.address}) === user2({resolved_user1.address}) => True")


def demo_scope_chain_and_closure(runtime: JSEngineRuntime):
    """
    Eksperimen 2: Scope Chain Resolution & Closure
    Fungsi menyimpan referensi lexical environment induk meskipun induk sudah selesai dipanggil.
    """
    print(f"\n{CLR_BOLD}{CLR_GREEN}[EXPERIMENT 2] Scope Chain & Closure Simulation{CLR_RESET}")
    
    # Outer Function: create_counter(start)
    def create_counter(start_val: int):
        # Lexical env baru untuk create_counter
        counter_env = LexicalEnvironment("create_counter_env", runtime.current_context().env)
        counter_env.declare("count", start_val)
        runtime.push_context("create_counter()", counter_env)

        # Inner Function: increment() -> Closure mempertahankan counter_env
        closure_captured_env = counter_env

        def increment_fn():
            inc_env = LexicalEnvironment("increment_env", closure_captured_env)
            runtime.push_context("increment()", inc_env)
            
            # Lookup & mutate via lexical scope chain
            current = inc_env.resolve("count")
            inc_env.mutate("count", current + 1)
            print(f"    Closure call: 'count' dinaikkan menjadi {inc_env.resolve('count')}")
            runtime.pop_context()

        runtime.pop_context()
        return increment_fn

    print("  Mengeksekusi create_counter(10)...")
    counter_a = create_counter(10)
    print("  Frame create_counter() sudah di-pop dari stack! Menjalankan instance closure:")
    counter_a()
    counter_a()
    counter_a()


def demo_event_loop_concurrency(runtime: JSEngineRuntime):
    """
    Eksperimen 3: Event Loop (Synchronous vs Microtask vs Macrotask)
    Simulasi eksekusi kode:
      console.log('1. Sync Start');
      setTimeout(() => console.log('2. Macrotask Timer'), 0);
      Promise.resolve().then(() => console.log('3. Microtask Promise'));
      console.log('4. Sync End');
    """
    print(f"\n{CLR_BOLD}{CLR_GREEN}[EXPERIMENT 3] Event Loop Scheduling Order{CLR_RESET}")

    # Synchronous 1
    print("  [SYNC] 1. Main Script Synchronous Start")

    # Macrotask: setTimeout
    runtime.set_timeout("setTimeout_Callback_1", delay_ms=0, callback=lambda: (
        print("  [MACROTASK] -> Executed: setTimeout callback 1")
    ))

    # Microtask: Promise.resolve().then()
    runtime.queue_microtask("Promise_Callback_1", lambda: (
        print("  [MICROTASK] -> Executed: Promise.then callback 1")
    ))

    # Enqueue microtask berantai di dalam microtask untuk membuktikan microtask starvation prevention
    def nested_microtask():
        print("  [MICROTASK] -> Executed: Promise.then callback 2 (Nested)")
    
    runtime.queue_microtask("Promise_Callback_Chain", lambda: (
        print("  [MICROTASK] -> Executed: Promise.then callback root"),
        runtime.queue_microtask("Nested_Promise_Callback", nested_microtask)
    ))

    # Macrotask kedua
    runtime.set_timeout("setTimeout_Callback_2", delay_ms=10, callback=lambda: (
        print("  [MACROTASK] -> Executed: setTimeout callback 2")
    ))

    # Synchronous 2
    print("  [SYNC] 4. Main Script Synchronous End")


def main():
    print(f"{CLR_BG_DARK}{CLR_BOLD}{CLR_CYAN}================================================================={CLR_RESET}")
    print(f"{CLR_BG_DARK}{CLR_BOLD}{CLR_CYAN}     LAB: JS ENGINE INTERNALS (EXECUTION, DATA & EVENT LOOP)     {CLR_RESET}")
    print(f"{CLR_BG_DARK}{CLR_BOLD}{CLR_CYAN}================================================================={CLR_RESET}")

    engine = JSEngineRuntime()

    # Jalankan serangkaian eksperimen teknik dasar engine JS
    demo_value_vs_reference(engine)
    demo_scope_chain_and_closure(engine)
    demo_event_loop_concurrency(engine)

    # Proses semua asynchronous queue yang terbentuk sesuai algoritma Event Loop HTML5 / ECMAScript
    engine.run_event_loop()

    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ Lab Run Berhasil: Semua tahapan eksekusi dan memori terverifikasi!{CLR_RESET}\n")


if __name__ == "__main__":
    main()