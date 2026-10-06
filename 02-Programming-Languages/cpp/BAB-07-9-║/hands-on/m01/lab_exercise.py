#!/usr/bin/env python3
"""
=============================================================================
LAB EXERCISE: Simulasi Fondasi Inti C++ (Memory Model, RAII, VTable, Move)
BAB-07-9-║ : Hands-on Technical Interactive Simulation
=============================================================================
Skrip ini mensimulasikan mekanisme internal runtime C++ pada terminal:
1. Memory Model: Stack Frame & Heap Allocation (Hex addresses & alignment)
2. RAII & Smart Pointers: std::unique_ptr & std::shared_ptr reference counting
3. Polymorphism & VTable: Memory layout vptr & dynamic dispatch resolution
4. Move Semantics: rvalue references, resource theft vs deep-copy overhead
=============================================================================
"""

import sys
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# ANSI Color Codes for Rich Terminal Output
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    GRAY    = "\033[90m"
    BG_BLUE = "\033[44m"


def print_banner(title: str) -> None:
    border = "=" * 70
    print(f"\n{Color.CYAN}{Color.BOLD}{border}")
    print(f" {title.center(68)} ")
    print(f"{border}{Color.RESET}\n")


# ============================================================================
# 1. SIMULASI MEMORY MODEL: STACK VS HEAP
# ============================================================================
@dataclass
class StackVariable:
    name: str
    var_type: str
    value: Any
    address: int
    size_bytes: int


class StackFrame:
    def __init__(self, function_name: str, base_addr: int):
        self.function_name = function_name
        self.base_addr = base_addr
        self.variables: List[StackVariable] = []
        self._current_offset = 0

    def allocate_var(self, name: str, var_type: str, value: Any, size_bytes: int) -> StackVariable:
        # Stack grows downwards in traditional x86_64 ABI
        self._current_offset += size_bytes
        addr = self.base_addr - self._current_offset
        var = StackVariable(name, var_type, value, addr, size_bytes)
        self.variables.append(var)
        return var


class CppMemorySimulator:
    def __init__(self):
        self.stack_top = 0x7FFE_FFFF_E000
        self.heap_top = 0x0000_5555_A000
        self.call_stack: List[StackFrame] = []
        self.heap_blocks: Dict[int, Dict[str, Any]] = {}

    def push_frame(self, func_name: str) -> StackFrame:
        base = self.stack_top - (len(self.call_stack) * 0x1000)
        frame = StackFrame(func_name, base)
        self.call_stack.append(frame)
        return frame

    def pop_frame(self) -> Optional[StackFrame]:
        if self.call_stack:
            return self.call_stack.pop()
        return None

    def heap_alloc(self, size_bytes: int, tag: str) -> int:
        addr = self.heap_top
        self.heap_top += ((size_bytes + 15) // 16) * 16  # 16-byte alignment
        self.heap_blocks[addr] = {"size": size_bytes, "tag": tag, "alive": True}
        return addr

    def heap_free(self, addr: int) -> bool:
        if addr in self.heap_blocks and self.heap_blocks[addr]["alive"]:
            self.heap_blocks[addr]["alive"] = False
            return True
        return False

    def render_memory_map(self) -> None:
        print(f"{Color.YELLOW}[VIRTUAL MEMORY LAYOUT SIMULATION]{Color.RESET}")
        print(f"{Color.GRAY}High Memory (0x7FFF_FFFF_FFFF){Color.RESET}")
        print(f"  |  {Color.RED}[STACK REGION (Grows Downwards \u2193)]{Color.RESET}")
        
        for frame in reversed(self.call_stack):
            print(f"  |  +-- Frame: {Color.BOLD}{frame.function_name}(){Color.RESET} (Base: 0x{frame.base_addr:012X})")
            for var in frame.variables:
                val_repr = f"0x{var.value:012X}" if isinstance(var.value, int) and var.value > 0xFFFF else repr(var.value)
                print(f"  |      |- [0x{var.address:012X}] {var.var_type} {Color.GREEN}{var.name}{Color.RESET} = {val_repr} ({var.size_bytes}B)")

        print("  |      :")
        print("  |  (Unmapped Memory Gap / Guard Page)")
        print("  |      :")
        print(f"  |  {Color.BLUE}[HEAP REGION (Grows Upwards \u2191)]{Color.RESET}")
        for addr, meta in self.heap_blocks.items():
            status = f"{Color.GREEN}ALIVE{Color.RESET}" if meta["alive"] else f"{Color.RED}FREED{Color.RESET}"
            print(f"  |  +-- [0x{addr:012X}] {meta['tag']:<20} Size={meta['size']:>3}B  [{status}]")
        print(f"{Color.GRAY}Low Memory  (0x0000_0000_0000){Color.RESET}\n")


# ============================================================================
# 2. SIMULASI RAII & SMART POINTERS
# ============================================================================
class SimulatedUniquePtr:
    def __init__(self, resource_name: str, memory_sim: CppMemorySimulator, size: int = 64):
        self.sim = memory_sim
        self.resource_name = resource_name
        self.size = size
        self.addr = self.sim.heap_alloc(size, f"unique_ptr<{resource_name}>")
        print(f"  {Color.GREEN}[RAII Ctor]{Color.RESET} Resource '{self.resource_name}' allocated at 0x{self.addr:012X}")

    def release(self) -> int:
        addr = self.addr
        self.addr = 0
        return addr

    def is_valid(self) -> bool:
        return self.addr != 0

    def __del__(self):
        if self.addr != 0:
            self.sim.heap_free(self.addr)
            print(f"  {Color.RED}[RAII Dtor]{Color.RESET} Resource '{self.resource_name}' automatically freed at 0x{self.addr:012X}")


class ControlBlock:
    def __init__(self, addr: int, name: str):
        self.addr = addr
        self.name = name
        self.strong_ref_count = 1
        self.weak_ref_count = 0


class SimulatedSharedPtr:
    def __init__(self, name: str, memory_sim: CppMemorySimulator, existing_cb: Optional[ControlBlock] = None):
        self.sim = memory_sim
        if existing_cb is None:
            addr = self.sim.heap_alloc(128, f"shared_ptr<{name}>")
            self.cb = ControlBlock(addr, name)
            print(f"  {Color.GREEN}[SharedPtr Ctor]{Color.RESET} Created control block for '{name}'. Strong ref = 1 (Addr: 0x{addr:012X})")
        else:
            self.cb = existing_cb
            self.cb.strong_ref_count += 1
            print(f"  {Color.CYAN}[SharedPtr Copy]{Color.RESET} Cloned '{self.cb.name}'. Strong ref = {self.cb.strong_ref_count}")

    def clone(self) -> 'SimulatedSharedPtr':
        return SimulatedSharedPtr(self.cb.name, self.sim, self.cb)

    def release(self) -> None:
        if self.cb is None:
            return
        self.cb.strong_ref_count -= 1
        print(f"  {Color.YELLOW}[SharedPtr Release]{Color.RESET} Strong ref '{self.cb.name}' decremented to {self.cb.strong_ref_count}")
        if self.cb.strong_ref_count == 0:
            self.sim.heap_free(self.cb.addr)
            print(f"  {Color.RED}[SharedPtr Cleanup]{Color.RESET} Ref count 0! Freed managed object at 0x{self.cb.addr:012X}")
        self.cb = None


# ============================================================================
# 3. SIMULASI VIRTUAL TABLE (VTABLE) & DYNAMIC DISPATCH
# ============================================================================
class VTable:
    def __init__(self, class_name: str, methods: Dict[str, str]):
        self.class_name = class_name
        self.methods = methods
        self.vtable_address = 0x0000_5555_F000 + (hash(class_name) % 0x0FFF)

    def resolve(self, method_name: str) -> str:
        return self.methods.get(method_name, "NULL")


class BaseClassSim:
    vtable = VTable("Base", {
        "speak()": "Base::speak() -> 'Hello from Base'",
        "type()":  "Base::type()  -> 'Generic Base Object'",
    })

    def __init__(self, name: str):
        self.vptr = BaseClassSim.vtable
        self.name = name

    def call_virtual(self, method_name: str) -> str:
        impl = self.vptr.resolve(method_name)
        return f"Dynamic Dispatch via vptr (0x{self.vptr.vtable_address:08X}) -> {impl}"


class DerivedClassSim(BaseClassSim):
    vtable = VTable("Derived", {
        "speak()": "Derived::speak() -> 'Overridden: Specialized Derived Greeting!'",
        "type()":  "Derived::type()  -> 'Derived Concrete Object'",
    })

    def __init__(self, name: str, extra_payload: str):
        super().__init__(name)
        self.vptr = DerivedClassSim.vtable  # vptr adjusted in Derived ctor
        self.extra_payload = extra_payload


# ============================================================================
# 4. SIMULASI MOVE SEMANTICS & RVALUE REFERENCES (std::move)
# ============================================================================
class HeapBuffer:
    def __init__(self, tag: str, capacity: int, sim: CppMemorySimulator):
        self.tag = tag
        self.capacity = capacity
        self.sim = sim
        self.buffer_addr = self.sim.heap_alloc(capacity, f"Buffer({tag})")
        print(f"    {Color.GREEN}[Alloc Buffer]{Color.RESET} {tag} allocated {capacity} bytes at 0x{self.buffer_addr:012X}")

    def copy_from(self, other: 'HeapBuffer') -> None:
        """Deep Copy Simulation (Copy Constructor/Assignment)"""
        start = time.perf_counter()
        # Simulate byte duplication latency
        time.sleep(0.005)
        print(f"    {Color.YELLOW}[Deep Copy Overhead]{Color.RESET} Duplicating {other.capacity} bytes from 0x{other.buffer_addr:012X} to new address 0x{self.buffer_addr:012X}")

    def move_from(self, other: 'HeapBuffer') -> None:
        """Move Semantics Simulation (Move Constructor/Assignment)"""
        print(f"    {Color.MAGENTA}[Move Ownership]{Color.RESET} Stealing pointer 0x{other.buffer_addr:012X} directly!")
        # Free own current buffer if any
        if self.buffer_addr:
            self.sim.heap_free(self.buffer_addr)
        # Pilfer pointer from donor
        self.buffer_addr = other.buffer_addr
        self.capacity = other.capacity
        # Reset donor to valid but empty state
        other.buffer_addr = 0
        other.capacity = 0
        print(f"    {Color.GRAY}[Donor State]{Color.RESET} Donor '{other.tag}' pointer set to nullptr (0x0)")


# ============================================================================
# INTERACTIVE DEMO RUNNER
# ============================================================================
def run_memory_demo(sim: CppMemorySimulator):
    print_banner("1. DEMO: STACK FRAMES & HEAP LIFETIME")
    frame_main = sim.push_frame("main")
    var_a = frame_main.allocate_var("local_count", "int32_t", 42, 4)
    var_b = frame_main.allocate_var("ratio", "double", 3.14159, 8)
    
    # Simulate heap pointer on stack
    heap_ptr = sim.heap_alloc(256, "dynamic_cache_buffer")
    frame_main.allocate_var("p_cache", "uint8_t*", heap_ptr, 8)

    # Push nested function frame
    frame_compute = sim.push_frame("compute_payload")
    frame_compute.allocate_var("iteration", "int32_t", 1, 4)
    frame_compute.allocate_var("temp_flag", "bool", True, 1)

    sim.render_memory_map()
    print(f"{Color.GREEN}\u2714 Function 'compute_payload' returns -> Popping stack frame...{Color.RESET}")
    sim.pop_frame()
    sim.render_memory_map()


def run_raii_demo(sim: CppMemorySimulator):
    print_banner("2. DEMO: RAII & SMART POINTERS (unique_ptr vs shared_ptr)")
    print(f"{Color.BOLD}--- Step A: std::unique_ptr Exclusive Ownership ---{Color.RESET}")
    u1 = SimulatedUniquePtr("DatabaseConnection", sim, 128)
    print(f"  u1 owns pointer: 0x{u1.addr:012X}")
    print("  Transferring ownership via std::move...")
    raw_addr = u1.release()
    print(f"  u1 after move: valid={u1.is_valid()} (nullptr)")
    sim.heap_free(raw_addr)
    print(f"  Manually settled transferred resource.\n")

    print(f"{Color.BOLD}--- Step B: std::shared_ptr Reference Counting ---{Color.RESET}")
    sp1 = SimulatedSharedPtr("SessionToken", sim)
    sp2 = sp1.clone()
    sp3 = sp2.clone()
    print(f"\n  Releasing shared instances one by one:")
    sp1.release()
    sp2.release()
    sp3.release()


def run_vtable_demo():
    print_banner("3. DEMO: VIRTUAL METHOD TABLE (vptr & Dynamic Dispatch)")
    base_obj = BaseClassSim("base_instance")
    derived_obj = DerivedClassSim("derived_instance", "SecretPayload123")

    print(f"Class '{BaseClassSim.vtable.class_name}' VTable Addr: 0x{BaseClassSim.vtable.vtable_address:08X}")
    for sig, impl in BaseClassSim.vtable.methods.items():
        print(f"  |-- Slot: {sig:<12} -> {impl}")

    print(f"\nClass '{DerivedClassSim.vtable.class_name}' VTable Addr: 0x{DerivedClassSim.vtable.vtable_address:08X}")
    for sig, impl in DerivedClassSim.vtable.methods.items():
        print(f"  |-- Slot: {sig:<12} -> {impl}")

    print(f"\n{Color.CYAN}Simulating Base Pointer Polymorphism:{Color.RESET}")
    polymorphic_ptrs: List[BaseClassSim] = [base_obj, derived_obj]
    for idx, ptr in enumerate(polymorphic_ptrs):
        print(f"\n[Ptr #{idx + 1}] Target Name: {ptr.name}")
        print(f"  -> Calling virtual speak(): {ptr.call_virtual('speak()')}")
        print(f"  -> Calling virtual type() : {ptr.call_virtual('type()')}")


def run_move_demo(sim: CppMemorySimulator):
    print_banner("4. DEMO: MOVE SEMANTICS & RVALUE REFERENCES")
    print(f"{Color.BOLD}Scenario 1: Expensive Deep Copy (C++98){Color.RESET}")
    buf_source = HeapBuffer("SourceBufferA", 1024 * 1024, sim)
    buf_copy = HeapBuffer("CopyTargetB", 1024 * 1024, sim)
    buf_copy.copy_from(buf_source)

    print(f"\n{Color.BOLD}Scenario 2: Zero-Cost Move Semantics (C++11/Modern){Color.RESET}")
    buf_donor = HeapBuffer("HeavyDonorC", 8 * 1024 * 1024, sim)
    buf_stealer = HeapBuffer("StealerD", 0, sim)
    buf_stealer.move_from(buf_donor)
    print(f"  Result: Stealer now has address 0x{buf_stealer.buffer_addr:012X} with 0 overhead bytes copied!")


def main():
    sim = CppMemorySimulator()
    print_banner("C++ CORE FOUNDATIONS SIMULATOR (BAB-07-9-║)")
    print(f"{Color.YELLOW}Running comprehensive automated walkthrough of low-level C++ mechanics...{Color.RESET}\n")

    run_memory_demo(sim)
    run_raii_demo(sim)
    run_vtable_demo()
    run_move_demo(sim)

    print_banner("SIMULATION COMPLETED SUCCESSFULLY (\u2714 100% RUNNABLE)")


if __name__ == "__main__":
    main()
