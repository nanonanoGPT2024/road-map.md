#!/usr/bin/env python3
"""
Lab Hands-on: JVM Deep Dive & Fondasi Java Modern
Modul 02: Arsitektur Eksekusi JVM, Generational Garbage Collection, & JIT Compilation

Skrip ini mensimulasikan komponen runtime internal JVM:
1. JVM Bytecode Stack Machine (Eksekutor frame & operand stack)
2. Generational Heap Memory Manager (Eden, Survivor S0/S1, Tenured/Old Gen)
3. Stop-The-World (STW) Minor & Major Garbage Collector (Copying & Mark-Sweep)
4. Tiered JIT Compilation Engine (Tier 0: Interpreter -> Tier 1: C1 -> Tier 2: C2)
"""

import sys
import time
import random
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field

# --- ANSI Formatting Helper ---
class TerminalColor:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    BG_DARK = "\033[40m"


@dataclass
class JavaObject:
    """Representasi object instance di Java Heap."""
    oid: int
    size_bytes: int
    age: int = 0
    references: List[int] = field(default_factory=list)
    alive: bool = True


class GenerationalHeap:
    """
    Simulasi memori heap JVM Generational (HotSpot-style):
    - Young Generation: Eden Space, Survivor 0 (From), Survivor 1 (To)
    - Old Generation: Tenured Space
    """
    def __init__(self, eden_cap: int = 256, survivor_cap: int = 64, tenured_cap: int = 512, tenuring_threshold: int = 3):
        self.eden_cap = eden_cap
        self.survivor_cap = survivor_cap
        self.tenured_cap = tenured_cap
        self.tenuring_threshold = tenuring_threshold

        self.eden: Dict[int, JavaObject] = {}
        self.s0: Dict[int, JavaObject] = {}
        self.s1: Dict[int, JavaObject] = {}
        self.tenured: Dict[int, JavaObject] = {}

        self.from_space = self.s0
        self.to_space = self.s1

        self.gc_count_minor = 0
        self.gc_count_major = 0
        self.total_stw_ms = 0.0

    def current_eden_used(self) -> int:
        return sum(obj.size_bytes for obj in self.eden.values())

    def current_tenured_used(self) -> int:
        return sum(obj.size_bytes for obj in self.tenured.values())

    def allocate(self, obj: JavaObject, gc_roots: Set[int]) -> bool:
        """Alokasi objek ke Eden. Melakukan Minor GC jika Eden penuh."""
        if self.current_eden_used() + obj.size_bytes > self.eden_cap:
            self._trigger_minor_gc(gc_roots)

        # Jika masih penuh setelah GC, alokasi langsung ke Old Gen (Humongous/Fallback)
        if self.current_eden_used() + obj.size_bytes > self.eden_cap:
            return self._allocate_tenured(obj, gc_roots)

        self.eden[obj.oid] = obj
        return True

    def _allocate_tenured(self, obj: JavaObject, gc_roots: Set[int]) -> bool:
        if self.current_tenured_used() + obj.size_bytes > self.tenured_cap:
            self._trigger_major_gc(gc_roots)
            if self.current_tenured_used() + obj.size_bytes > self.tenured_cap:
                print(f"{TerminalColor.RED}[OOM] java.lang.OutOfMemoryError: Java heap space{TerminalColor.RESET}")
                return False
        self.tenured[obj.oid] = obj
        return True

    def _trigger_minor_gc(self, gc_roots: Set[int]):
        """Minor GC: Copying collector dari Eden + From-Space ke To-Space / Tenured."""
        start_time = time.perf_counter()
        self.gc_count_minor += 1
        before_used = self.current_eden_used()

        survivors_promoted = 0
        survivors_copied = 0

        # Mark & Copy live objects from Eden & From-Space
        sources = list(self.eden.values()) + list(self.from_space.values())
        for obj in sources:
            if obj.oid in gc_roots and obj.alive:
                obj.age += 1
                if obj.age >= self.tenuring_threshold:
                    # Promosi ke Tenured/Old Gen
                    self.tenured[obj.oid] = obj
                    survivors_promoted += 1
                else:
                    self.to_space[obj.oid] = obj
                    survivors_copied += 1

        self.eden.clear()
        self.from_space.clear()
        # Swap survivor spaces
        self.from_space, self.to_space = self.to_space, self.from_space

        duration_ms = (time.perf_counter() - start_time) * 1000 + random.uniform(1.2, 3.5)
        self.total_stw_ms += duration_ms

        print(f"{TerminalColor.YELLOW}[GC (Young Pause) #{self.gc_count_minor}] "
              f"Freed: {before_used - self.current_eden_used()}B | "
              f"Promoted: {survivors_promoted} | Copied: {survivors_copied} | "
              f"STW Pause: {duration_ms:.2f}ms{TerminalColor.RESET}")

    def _trigger_major_gc(self, gc_roots: Set[int]):
        """Major GC (Full GC): Mark-Sweep-Compact pada Tenured space."""
        start_time = time.perf_counter()
        self.gc_count_major += 1
        before_used = self.current_tenured_used()

        # Mark phase & Sweep dead objects
        dead_keys = [oid for oid, obj in self.tenured.items() if oid not in gc_roots or not obj.alive]
        for oid in dead_keys:
            del self.tenured[oid]

        duration_ms = (time.perf_counter() - start_time) * 1000 + random.uniform(8.0, 18.0)
        self.total_stw_ms += duration_ms

        print(f"{TerminalColor.MAGENTA}[Full GC (Ergonomics) #{self.gc_count_major}] "
              f"Tenured: {before_used}B -> {self.current_tenured_used()}B | "
              f"STW Pause: {duration_ms:.2f}ms{TerminalColor.RESET}")


class JITEngine:
    """
    Simulasi Tiered Compilation JVM:
    - Tier 0: Bytecode Interpreter (Sangat lambat, mengumpulkan counter)
    - Tier 1: C1 Compiler (Client JIT, optimasi cepat tanpa profiling berat)
    - Tier 2: C2 Compiler (Server JIT, profiling agresif, inlining, escape analysis)
    """
    TIER_0_INTERPRETER = 0
    TIER_1_C1          = 1
    TIER_2_C2          = 2

    def __init__(self, c1_threshold: int = 15, c2_threshold: int = 50):
        self.c1_threshold = c1_threshold
        self.c2_threshold = c2_threshold
        self.call_counters: Dict[str, int] = {}
        self.compiled_tier: Dict[str, int] = {}

    def record_call(self, method_name: str) -> int:
        count = self.call_counters.get(method_name, 0) + 1
        self.call_counters[method_name] = count
        current_tier = self.compiled_tier.get(method_name, self.TIER_0_INTERPRETER)

        if count >= self.c2_threshold and current_tier < self.TIER_2_C2:
            self.compiled_tier[method_name] = self.TIER_2_C2
            print(f"{TerminalColor.CYAN}[JIT: C2 Optimized] {method_name}() promoted to Tier-2 Server Compiler "
                  f"(Inlining & Loop Vectorization applied at call #{count}){TerminalColor.RESET}")
        elif count >= self.c1_threshold and current_tier < self.TIER_1_C1:
            self.compiled_tier[method_name] = self.TIER_1_C1
            print(f"{TerminalColor.BLUE}[JIT: C1 Compiled]  {method_name}() promoted to Tier-1 Client Compiler "
                  f"(Native code emitted at call #{count}){TerminalColor.RESET}")

        return self.compiled_tier.get(method_name, self.TIER_0_INTERPRETER)


class BytecodeExecutor:
    """
    Simulasi Stack Machine JVM untuk eksekusi instruksi Java Bytecode sederhana.
    """
    def __init__(self, jit: JITEngine):
        self.jit = jit

    def execute_method(self, method_name: str, instructions: List[tuple], local_vars: Dict[int, int]) -> int:
        tier = self.jit.record_call(method_name)

        # Jika sudah di Tier-2 C2 JIT, eksekusi native di-bypass secara efisien
        if tier == JITEngine.TIER_2_C2:
            # Native path simulation
            return local_vars.get(0, 0) + local_vars.get(1, 0)

        # Interpreter / Tier-1 Stack Machine Evaluation
        stack: List[int] = []
        for opcode, *args in instructions:
            if opcode == "ICONST":
                stack.append(args[0])
            elif opcode == "ILOAD":
                stack.append(local_vars.get(args[0], 0))
            elif opcode == "ISTORE":
                local_vars[args[0]] = stack.pop()
            elif opcode == "IADD":
                val2 = stack.pop()
                val1 = stack.pop()
                stack.append(val1 + val2)
            elif opcode == "IMUL":
                val2 = stack.pop()
                val1 = stack.pop()
                stack.append(val1 * val2)
            elif opcode == "IRETURN":
                return stack.pop() if stack else 0
        return 0


def render_dashboard(heap: GenerationalHeap, step: int, total_steps: int):
    """Menampilkan visualisasi utilisasi memori JVM per epoch."""
    eden_pct = (heap.current_eden_used() / heap.eden_cap) * 100
    tenured_pct = (heap.current_tenured_used() / heap.tenured_cap) * 100
    
    eden_bar = "█" * int(eden_pct // 5) + "-" * (20 - int(eden_pct // 5))
    tenured_bar = "█" * int(tenured_pct // 5) + "-" * (20 - int(tenured_pct // 5))

    print(f"\n{TerminalColor.BOLD}--- [JVM Runtime Inspection - Cycle {step}/{total_steps}] ---{TerminalColor.RESET}")
    print(f" Eden Space     [{eden_bar}] {eden_pct:5.1f}% ({heap.current_eden_used():3d}/{heap.eden_cap} B)")
    print(f" From Survivor  (Objects: {len(heap.from_space)})")
    print(f" Tenured (Old)  [{tenured_bar}] {tenured_pct:5.1f}% ({heap.current_tenured_used():3d}/{heap.tenured_cap} B)")
    print(f" Statistics     : Minor GC: {heap.gc_count_minor} | Full GC: {heap.gc_count_major} | Cumulated STW: {heap.total_stw_ms:.2f} ms")


def main():
    print(f"{TerminalColor.GREEN}{TerminalColor.BOLD}================================================================={TerminalColor.RESET}")
    print(f"{TerminalColor.GREEN}{TerminalColor.BOLD}   JVM Deep Dive: Bytecode Execution, Heap & JIT Simulation     {TerminalColor.RESET}")
    print(f"{TerminalColor.GREEN}{TerminalColor.BOLD}================================================================={TerminalColor.RESET}\n")

    heap = GenerationalHeap(eden_cap=300, survivor_cap=80, tenured_cap=600, tenuring_threshold=3)
    jit = JITEngine(c1_threshold=10, c2_threshold=30)
    executor = BytecodeExecutor(jit)

    # Definisi bytecode representasi:
    # int calculate(int a, int b) { return (a + b) * 2; }
    bytecode_program = [
        ("ILOAD", 0),      # Load param a
        ("ILOAD", 1),      # Load param b
        ("IADD",),         # a + b
        ("ICONST", 2),     # Push const 2
        ("IMUL",),         # (a + b) * 2
        ("IRETURN",)       # Return result
    ]

    gc_roots: Set[int] = set()
    object_id_counter = 1000
    total_cycles = 45

    for cycle in range(1, total_cycles + 1):
        # 1. Bytecode execution & JIT Hotspot monitoring
        calc_result = executor.execute_method("calculateSum", bytecode_program, {0: cycle, 1: 5})

        # 2. Simulasi alokasi objek Java di Heap
        obj_size = random.randint(30, 80)
        obj = JavaObject(oid=object_id_counter, size_bytes=obj_size)
        object_id_counter += 1

        # Menentukan apakah objek masuk GC Roots (Live references)
        # 70% objek adalah temporary (Short-lived, representasi Weak Generational Hypothesis)
        is_retained = (random.random() < 0.30)
        if is_retained:
            gc_roots.add(obj.oid)

        allocated = heap.allocate(obj, gc_roots)
        if not allocated:
            print(f"{TerminalColor.RED}[ABORT] JVM out of memory condition occurred.{TerminalColor.RESET}")
            break

        # Simulasi dereferensi berkala untuk objek lama
        if cycle % 7 == 0 and gc_roots:
            dereferenced_oid = random.choice(list(gc_roots))
            gc_roots.remove(dereferenced_oid)

        # 3. Cetak telemetri setiap interval siklus
        if cycle % 10 == 0 or cycle == total_cycles:
            render_dashboard(heap, cycle, total_cycles)
            time.sleep(0.3)

    print(f"\n{TerminalColor.GREEN}{TerminalColor.BOLD}>>> JVM Simulation Complete <<<{TerminalColor.RESET}")
    print(f"Final GC Telemetry: Young GCs={heap.gc_count_minor}, Full GCs={heap.gc_count_major}, Total STW Pause Time={heap.total_stw_ms:.2f}ms")
    print(f"JIT Compilation Status: {jit.compiled_tier}")


if __name__ == "__main__":
    main()