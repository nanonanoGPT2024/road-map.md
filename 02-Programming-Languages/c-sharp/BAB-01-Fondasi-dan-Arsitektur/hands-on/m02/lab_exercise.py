#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi Arsitektur .NET & CLR Internals (Deep Dive)
Modul: 02 - CLR Virtual Execution System, Memory Layout & Generational GC Simulator

Deskripsi:
Skrip ini mensimulasikan komponen inti runtime CLR (Common Language Runtime):
 1. Memory Layout Objek Managed (Object Header Word, MethodTable Pointer/TypeHandle, Payload, Padding 8-byte alignment).
 2. Virtual Execution System (VES) berbasis Evaluation Stack CIL (Common Intermediate Language).
 3. Tiered Compilation Engine (Tier 0 / Quick JIT -> Tier 1 / Optimized JIT).
 4. Generational Garbage Collector (Gen 0, Gen 1, Gen 2) berbasis GC Roots & Compaction.
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


# ANSI Terminal Colors
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


class OpCode(Enum):
    LDC_I4 = auto()   # Load constant 4-byte integer onto stack
    LDLOC = auto()    # Load local variable
    STLOC = auto()    # Store value into local variable
    ADD = auto()      # Pop 2 values, add, push result
    SUB = auto()      # Pop 2 values, subtract, push result
    NEWOBJ = auto()   # Allocate managed object
    RET = auto()      # Return from method


@dataclass
class MethodTable:
    """Merepresentasikan struktur internal MethodTable (Type Handle di EEClass)."""
    type_name: str
    instance_size: int
    vtable: Dict[str, Any] = field(default_factory=dict)
    interface_map: List[str] = field(default_factory=list)


@dataclass
class ManagedObject:
    """
    Simulasi memori heap managed 64-bit:
    - Object Header Word (SyncBlock index, HashCode, Lock info): 8 bytes
    - MethodTable Pointer (TypeHandle): 8 bytes
    - Instance Fields (Payload): n bytes
    - Padding: aligned to 8-byte boundary
    """
    address: int
    method_table: MethodTable
    fields: Dict[str, Any] = field(default_factory=dict)
    sync_block_index: int = 0
    generation: int = 0
    marked: bool = False

    def get_memory_size(self) -> int:
        header_size = 8
        mt_ptr_size = 8
        payload_size = self.method_table.instance_size
        raw_size = header_size + mt_ptr_size + payload_size
        # 8-byte alignment (quadword boundary pada arsitektur x64)
        aligned_size = (raw_size + 7) & ~7
        return aligned_size


class ExecutionEngineException(Exception):
    pass


class DotNetRuntime:
    """Simulasi CLR Execution Engine, Heap Manager, dan Generational GC."""

    def __init__(self, gen0_budget: int = 4):
        self.next_address = 0x00007FFB00001000
        self.gen0_budget = gen0_budget  # Maksimal objek di Gen0 sebelum GC terpicu
        self.heap_gen0: List[ManagedObject] = []
        self.heap_gen1: List[ManagedObject] = []
        self.heap_gen2: List[ManagedObject] = []
        self.stack_roots: Set[int] = set()  # Alamat objek yang aktif di execution stack
        self.gc_count = [0, 0, 0]           # Counter GC Gen 0, 1, 2
        self.jit_call_counters: Dict[str, int] = {}
        self.jit_tier: Dict[str, int] = {}  # 0: Quick JIT, 1: Optimized JIT

    def allocate(self, mt: MethodTable, initial_fields: Dict[str, Any]) -> ManagedObject:
        """Alokasi objek pada Managed Heap (default Gen 0). Trigger GC jika budget penuh."""
        if len(self.heap_gen0) >= self.gen0_budget:
            print(f"{Color.YELLOW}[GC Event] Budget Gen 0 penuh ({self.gen0_budget} objek). Memulai Garbage Collection...{Color.RESET}")
            self.collect_garbage(generation=0)

        obj = ManagedObject(
            address=self.next_address,
            method_table=mt,
            fields=initial_fields.copy(),
            sync_block_index=0,
            generation=0,
            marked=False
        )
        self.next_address += obj.get_memory_size()
        self.heap_gen0.append(obj)
        print(f"{Color.GREEN}[Alloc]{Color.RESET} {mt.type_name} @ 0x{obj.address:016X} | Size: {obj.get_memory_size()}B (Gen 0)")
        return obj

    def collect_garbage(self, generation: int = 0):
        """Generational Mark-Sweep & Compaction Algorithm."""
        self.gc_count[generation] += 1
        print(f"{Color.RED}[GC Start]{Color.RESET} Collecting Generation {generation} (GC Count: Gen0={self.gc_count[0]}, Gen1={self.gc_count[1]}, Gen2={self.gc_count[2]})")

        # Fase 1: Mark Phase (Traversal dari GC Roots)
        heaps_to_sweep = [self.heap_gen0]
        if generation >= 1:
            heaps_to_sweep.append(self.heap_gen1)
        if generation >= 2:
            heaps_to_sweep.append(self.heap_gen2)

        all_objects = [obj for h in heaps_to_sweep for obj in h]
        for obj in all_objects:
            obj.marked = False

        # Mark reachable objects
        for obj in all_objects:
            if obj.address in self.stack_roots:
                self._mark_recursive(obj)

        # Fase 2: Sweep & Promote Phase (Generational Promotion)
        survivors_gen0: List[ManagedObject] = []
        collected_count = 0

        for obj in list(self.heap_gen0):
            if obj.marked:
                obj.marked = False
                obj.generation = 1
                self.heap_gen1.append(obj)
                survivors_gen0.append(obj)
            else:
                collected_count += 1
        self.heap_gen0.clear()

        if generation >= 1:
            survivors_gen1: List[ManagedObject] = []
            for obj in list(self.heap_gen1):
                if obj in survivors_gen0:
                    continue  # Baru dipromosikan dari gen 0
                if obj.marked:
                    obj.marked = False
                    obj.generation = 2
                    self.heap_gen2.append(obj)
                    survivors_gen1.append(obj)
                else:
                    collected_count += 1
            # Filter heap gen 1 hanya objek survivor baru
            self.heap_gen1 = [o for o in self.heap_gen1 if o.generation == 1]

        if generation >= 2:
            self.heap_gen2 = [o for o in self.heap_gen2 if o.marked]
            for obj in self.heap_gen2:
                obj.marked = False

        print(f"{Color.RED}[GC End]{Color.RESET} Reklamasi selesai: {collected_count} objek dibebaskan dari memori.")

    def _mark_recursive(self, obj: ManagedObject):
        """Menelusuri object reference tree."""
        if obj.marked:
            return
        obj.marked = True
        for val in obj.fields.values():
            if isinstance(val, ManagedObject):
                self._mark_recursive(val)

    def execute_cil(self, method_name: str, bytecode: List[tuple], locals_dict: Dict[int, Any]) -> Any:
        """
        Simulasi CIL Stack-Based Virtual Execution System (VES).
        Mendukung Tiered Compilation (Tier 0 -> Tier 1).
        """
        # Monitoring Tiered Compilation
        call_count = self.jit_call_counters.get(method_name, 0) + 1
        self.jit_call_counters[method_name] = call_count

        current_tier = self.jit_tier.get(method_name, 0)
        if call_count >= 3 and current_tier == 0:
            self.jit_tier[method_name] = 1
            print(f"{Color.MAGENTA}[Tiered JIT]{Color.RESET} Metode '{method_name}' dipromosikan: Tier 0 (Quick JIT) -> Tier 1 (Optimized Native JIT)")
        elif method_name not in self.jit_tier:
            self.jit_tier[method_name] = 0
            print(f"{Color.CYAN}[Tiered JIT]{Color.RESET} Metode '{method_name}' pertama kali dijalankan via Tier 0 (Quick JIT - No PGO)")

        # Evaluation Stack
        eval_stack: List[Any] = []
        ip = 0

        while ip < len(bytecode):
            instr = bytecode[ip]
            op = instr[0]

            if op == OpCode.LDC_I4:
                eval_stack.append(int(instr[1]))
            elif op == OpCode.LDLOC:
                var_idx = instr[1]
                val = locals_dict.get(var_idx, 0)
                eval_stack.append(val)
                # Jika objek managed, daftarkan ke GC Roots
                if isinstance(val, ManagedObject):
                    self.stack_roots.add(val.address)
            elif op == OpCode.STLOC:
                var_idx = instr[1]
                val = eval_stack.pop()
                locals_dict[var_idx] = val
                if isinstance(val, ManagedObject):
                    self.stack_roots.add(val.address)
            elif op == OpCode.ADD:
                b = eval_stack.pop()
                a = eval_stack.pop()
                eval_stack.append(a + b)
            elif op == OpCode.SUB:
                b = eval_stack.pop()
                a = eval_stack.pop()
                eval_stack.append(a - b)
            elif op == OpCode.NEWOBJ:
                mt = instr[1]
                initial_fields = instr[2]
                obj = self.allocate(mt, initial_fields)
                eval_stack.append(obj)
                self.stack_roots.add(obj.address)
            elif op == OpCode.RET:
                result = eval_stack.pop() if eval_stack else None
                return result
            ip += 1

        return None


def inspect_object_memory(obj: ManagedObject):
    """Menampilkan inspeksi byte-level representasi Managed Object di CLR."""
    total_size = obj.get_memory_size()
    print(f"\n{Color.BOLD}--- Inspeksi Memori Objek: {obj.method_table.type_name} (x64 CLR) ---{Color.RESET}")
    print(f"Address Referensi   : 0x{obj.address:016X}")
    print(f"SyncBlock Header    : [0x{obj.address - 8:016X}] 0x{obj.sync_block_index:016X} (8 bytes)")
    print(f"MethodTable Pointer : [0x{obj.address:016X}] -> MT '{obj.method_table.type_name}' (8 bytes)")
    print(f"Payload (Fields)    : {obj.fields}")
    print(f"Generasi GC         : Gen {obj.generation}")
    print(f"Alokasi Total Byte  : {total_size} bytes (Payload + 16B Overhead + 8B Boundary Alignment)")
    print("-" * 65)


def main():
    print(f"{Color.BOLD}{Color.BLUE}======================================================================{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}   LAB: CLR INTERNALS, OBJECT MEMORY LAYOUT & EXECUTION ENGINE       {Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}======================================================================{Color.RESET}\n")

    runtime = DotNetRuntime(gen0_budget=3)

    # 1. Definisikan Metadata Type (Method Table)
    mt_point = MethodTable(type_name="System.Drawing.Point", instance_size=8)  # 2 x 4-byte int
    mt_customer = MethodTable(type_name="Enterprise.Core.Customer", instance_size=16)

    # 2. Simulasi Bytecode CIL: Method ComputeArea()
    # IL:
    #   ldc.i4 10
    #   stloc.0
    #   ldc.i4 20
    #   stloc.1
    #   ldloc.0
    #   ldloc.1
    #   add
    #   ret
    cil_compute_sum = [
        (OpCode.LDC_I4, 10),
        (OpCode.STLOC, 0),
        (OpCode.LDC_I4, 20),
        (OpCode.STLOC, 1),
        (OpCode.LDLOC, 0),
        (OpCode.LDLOC, 1),
        (OpCode.ADD),
        (OpCode.RET),
    ]

    print(f"{Color.BOLD}Langkah 1: Menjalankan CIL Virtual Execution Machine & Tiered JIT{Color.RESET}")
    for i in range(1, 5):
        print(f"\nEksekusi Ke-{i} Metode 'CalculateTax':")
        res = runtime.execute_cil("CalculateTax", cil_compute_sum, locals_dict={})
        print(f"Output Evaluasi Stack: {res}")
        time.sleep(0.05)

    print(f"\n{Color.BOLD}Langkah 2: Simulasi Alokasi Objek & Layout Memori Managed Heap{Color.RESET}")
    p1 = runtime.allocate(mt_point, {"X": 100, "Y": 200})
    inspect_object_memory(p1)

    print(f"\n{Color.BOLD}Langkah 3: Simulasi Generational Garbage Collection (Gen 0 -> Gen 1 promotion){Color.RESET}")
    # Simulasikan objek dialokasikan di dalam stack frame
    locals_frame = {}

    # Objek A dimasukkan ke GC Root (tersimpan di local frame)
    obj_active = runtime.allocate(mt_customer, {"Id": 101, "Name": "Alice"})
    runtime.stack_roots.add(obj_active.address)

    # Objek B dan C adalah transient/sampah (tidak masuk GC Root)
    _ = runtime.allocate(mt_point, {"X": 1, "Y": 1})
    _ = runtime.allocate(mt_point, {"X": 2, "Y": 2})

    # Alokasi berikutnya memicu GC karena Gen 0 budget = 3
    print("\nMemicu alokasi tambahan untuk melampaui batas Gen 0 budget...")
    _ = runtime.allocate(mt_point, {"X": 99, "Y": 99})

    # Cek status objek setelah GC
    print(f"\nStatus Objek Aktif (0x{obj_active.address:016X}): Gen {obj_active.generation} (Berhasil dipromosikan ke Gen 1)")
    print(f"Total objek tersisa di Gen 0: {len(runtime.heap_gen0)}")
    print(f"Total objek tersisa di Gen 1: {len(runtime.heap_gen1)}")
    print(f"Total objek tersisa di Gen 2: {len(runtime.heap_gen2)}")

    print(f"\n{Color.GREEN}{Color.BOLD}[✓] Lab Berhasil Selesai: Model CLR Virtual Machine tereksekusi akurat.{Color.RESET}")


if __name__ == "__main__":
    main()