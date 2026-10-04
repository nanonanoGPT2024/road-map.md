#!/usr/bin/env python3
"""
Lab: Deep Dive into Modern Swift Language Foundations, Runtime, & Memory System
Focus: Copy-On-Write (COW), ARC (Strong/Weak/Unowned), and Method Dispatch Internals.
Category: 03-Frontend-and-Mobile / Topic: ios / Chapter: 01 / Module: 02
"""

import sys
import time
import uuid
import ctypes
from typing import Dict, Any, Optional, List

# --- Terminal ANSI Color Formatting ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"

def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN}>>> {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}")

def print_step(msg: str):
    print(f"{GREEN}[EXEC]{RESET} {msg}")

def print_info(label: str, val: Any):
    print(f"  {BLUE}•{RESET} {BOLD}{label}:{RESET} {val}")

def print_warn(msg: str):
    print(f"  {YELLOW}⚠ {msg}{RESET}")

def print_err(msg: str):
    print(f"  {RED}✖ {msg}{RESET}")


# ============================================================================
# 1. SWIFT MEMORY SEMANTICS: COPY-ON-WRITE (COW) SIMULATOR
# ============================================================================
class HeapBuffer:
    """
    Simulates Swift heap-allocated buffer backing value types (e.g., Array, String, Set).
    Maintains an explicit reference count to enable isKnownUniquelyReferenced checks.
    """
    def __init__(self, data: List[Any]):
        self.buffer_id = uuid.uuid4().hex[:8]
        self.data: List[Any] = list(data)
        self.ref_count: int = 1

    def retain(self):
        self.ref_count += 1

    def release(self):
        self.ref_count -= 1

    def is_uniquely_referenced(self) -> bool:
        # Analogous to Swift's isKnownUniquelyReferenced(&buffer)
        return self.ref_count == 1


class SwiftCOWArray:
    """
    Simulates a Swift struct with value semantics powered by heap storage and COW.
    """
    def __init__(self, initial_elements: Optional[List[Any]] = None):
        self._buffer = HeapBuffer(initial_elements or [])

    def __copy__(self):
        # Shallow copy of the struct retains the underlying heap buffer
        new_instance = SwiftCOWArray.__new__(SwiftCOWArray)
        new_instance._buffer = self._buffer
        self._buffer.retain()
        return new_instance

    def _ensure_unique_storage(self):
        """Swift internal COW check: clones storage only if shared."""
        if not self._buffer.is_uniquely_referenced():
            print_warn(f"Buffer {self._buffer.buffer_id} shared (refCount={self._buffer.ref_count}). Deep cloning storage...")
            self._buffer.release()
            self._buffer = HeapBuffer(self._buffer.data)
            print_step(f"New isolated buffer allocated: {self._buffer.buffer_id}")
        else:
            print_step(f"Buffer {self._buffer.buffer_id} is uniquely referenced. In-place mutation permitted.")

    def append(self, element: Any):
        self._ensure_unique_storage()
        self._buffer.data.append(element)

    def read(self) -> List[Any]:
        return list(self._buffer.data)

    @property
    def buffer_id(self) -> str:
        return self._buffer.buffer_id

    @property
    def ref_count(self) -> int:
        return self._buffer.ref_count


# ============================================================================
# 2. SWIFT ARC (AUTOMATIC REFERENCE COUNTING) & WEAK/UNOWNED SIMULATOR
# ============================================================================
class HeapObjectSideTable:
    """
    Swift 4+ ARC implementation stores weak reference counts and state in a SideTable
    when reference counts overflow or weak pointers are initialized.
    """
    def __init__(self, target_address: int):
        self.target_address = target_address
        self.strong_count = 1
        self.weak_count = 0
        self.unowned_count = 0
        self.is_deallocating = False


class SwiftRuntimeEngine:
    """
    Simulates the Swift Runtime Object Header, SideTable registration,
    zeroing-weak memory tracking, and unowned memory traps.
    """
    _side_tables: Dict[int, HeapObjectSideTable] = {}

    @classmethod
    def allocate(cls, obj: Any) -> int:
        addr = id(obj)
        cls._side_tables[addr] = HeapObjectSideTable(addr)
        return addr

    @classmethod
    def retain(cls, addr: int):
        if addr in cls._side_tables:
            cls._side_tables[addr].strong_count += 1

    @classmethod
    def release(cls, addr: int) -> bool:
        """Releases a strong reference. Returns True if object was deinitialized."""
        if addr not in cls._side_tables:
            return False
        
        entry = cls._side_tables[addr]
        entry.strong_count -= 1
        
        if entry.strong_count == 0:
            entry.is_deallocating = True
            # In Swift, strong=0 immediately deinitializes the object (deinit called)
            # Memory remains allocated if weak_count > 0 until all weak references drop.
            if entry.weak_count == 0 and entry.unowned_count == 0:
                del cls._side_tables[addr]
            return True
        return False

    @classmethod
    def register_weak(cls, addr: int):
        if addr in cls._side_tables:
            cls._side_tables[addr].weak_count += 1

    @classmethod
    def release_weak(cls, addr: int):
        if addr in cls._side_tables:
            cls._side_tables[addr].weak_count -= 1
            if cls._side_tables[addr].strong_count == 0 and cls._side_tables[addr].weak_count == 0:
                del cls._side_tables[addr]

    @classmethod
    def resolve_weak(cls, target_ref: Any, addr: int) -> Optional[Any]:
        """Simulates Swift runtime dynamic zeroing: returns nil if strong count == 0."""
        table = cls._side_tables.get(addr)
        if not table or table.is_deallocating or table.strong_count <= 0:
            return None
        return target_ref

    @classmethod
    def resolve_unowned(cls, target_ref: Any, addr: int) -> Any:
        """Simulates Swift unowned access: Traps if strong_count == 0."""
        table = cls._side_tables.get(addr)
        if not table or table.is_deallocating or table.strong_count <= 0:
            raise RuntimeError(
                f"{RED}Fatal error: Attempted to read dangling pointer via unowned reference at 0x{addr:X}! (Crash){RESET}"
            )
        return target_ref


class SwiftObject:
    def __init__(self, name: str):
        self.name = name
        self.heap_address = SwiftRuntimeEngine.allocate(self)
        print_step(f"Allocated {self.name} at 0x{self.heap_address:X}")

    def retain(self):
        SwiftRuntimeEngine.retain(self.heap_address)

    def release(self):
        addr = self.heap_address
        dead = SwiftRuntimeEngine.release(addr)
        if dead:
            print_step(f"Deinit executed: {self.name} freed from memory (strong == 0).")


class WeakReference:
    """Wraps a reference with Swift zeroing-weak semantics."""
    def __init__(self, target: SwiftObject):
        self._target = target
        self._addr = target.heap_address
        SwiftRuntimeEngine.register_weak(self._addr)

    def get(self) -> Optional[SwiftObject]:
        res = SwiftRuntimeEngine.resolve_weak(self._target, self._addr)
        return res


class UnownedReference:
    """Wraps a reference with Swift unowned semantics (assumes target always exists, traps if freed)."""
    def __init__(self, target: SwiftObject):
        self._target = target
        self._addr = target.heap_address

    def get(self) -> SwiftObject:
        return SwiftRuntimeEngine.resolve_unowned(self._target, self._addr)


# ============================================================================
# 3. SWIFT METHOD DISPATCH INTERNALS (DIRECT vs VTABLE vs MESSAGE)
# ============================================================================
class SwiftDirectStruct:
    """Structs and final classes use Direct Dispatch (compile-time inlined / bl instruction)."""
    def compute(self, x: int) -> int:
        return x * x


class SwiftVTableBase:
    """Class methods use dynamic table lookup (VTable / Witness Table)."""
    def __init__(self):
        # Emulating virtual method table array
        self._vtable = [self._compute_impl]

    def _compute_impl(self, x: int) -> int:
        return x * x

    def compute(self, x: int) -> int:
        # Function pointer dispatch via vtable slot 0
        return self._vtable[0](x)


class SwiftVTableSubclass(SwiftVTableBase):
    def __init__(self):
        super().__init__()
        # Overriding vtable slot 0
        self._vtable[0] = self._override_compute

    def _override_compute(self, x: int) -> int:
        return (x * x) + 1


class ObjCMessageRuntime:
    """Simulates Objective-C Runtime message dispatch (objc_msgSend / dynamic selector lookup)."""
    def __init__(self):
        self.method_cache: Dict[str, Any] = {}
        self.method_table: Dict[str, Any] = {
            "compute:": lambda x: x * x
        }

    def objc_msgSend(self, selector: str, *args):
        # 1. Fast path: Check selector cache
        impl = self.method_cache.get(selector)
        if impl:
            return impl(*args)

        # 2. Slow path: Method list lookup & cache insertion
        impl = self.method_table.get(selector)
        if impl:
            self.method_cache[selector] = impl
            return impl(*args)

        raise AttributeError(f"unrecognized selector sent to instance: {selector}")


def benchmark_dispatch_mechanisms(iterations: int = 150_000):
    print_header("Benchmarking Swift Dispatch Mechanisms")
    print_info("Iterations", f"{iterations:,}")

    direct_obj = SwiftDirectStruct()
    vtable_obj = SwiftVTableSubclass()
    msg_obj = ObjCMessageRuntime()

    # 1. Direct Dispatch
    t0 = time.perf_counter()
    for i in range(iterations):
        _ = direct_obj.compute(i)
    direct_duration = time.perf_counter() - t0

    # 2. Table / Witness Dispatch
    t0 = time.perf_counter()
    for i in range(iterations):
        _ = vtable_obj.compute(i)
    vtable_duration = time.perf_counter() - t0

    # 3. Message Dispatch (objc_msgSend)
    t0 = time.perf_counter()
    for i in range(iterations):
        _ = msg_obj.objc_msgSend("compute:", i)
    msg_duration = time.perf_counter() - t0

    print(f"\n{BOLD}{'Dispatch Mechanism':<28} | {'Elapsed Time (ms)':<18} | {'Relative Cost':<15}{RESET}")
    print("-" * 68)
    print(f"{GREEN}{'Direct Dispatch (Static)':<28}{RESET} | {direct_duration * 1000:<18.3f} | {BOLD}1.00x (Baseline){RESET}")
    print(f"{CYAN}{'VTable Dispatch (Class/VWT)':<28}{RESET} | {vtable_duration * 1000:<18.3f} | {vtable_duration / direct_duration:<15.2f}x")
    print(f"{MAGENTA}{'Message Dispatch (objc_msgSend)':<28}{RESET} | {msg_duration * 1000:<18.3f} | {msg_duration / direct_duration:<15.2f}x")


# ============================================================================
# MAIN EXECUTION PIPELINE
# ============================================================================
def main():
    print(f"{BOLD}{MAGENTA}==========================================================================={RESET}")
    print(f"{BOLD}{MAGENTA}  SWIFT RUNTIME ARCHITECTURE, COW, & ARC MEMORY DEEP DIVE SIMULATION      {RESET}")
    print(f"{BOLD}{MAGENTA}==========================================================================={RESET}")

    # ------------------------------------------------------------------------
    # LAB PART 1: Copy-On-Write (COW) Mechanics
    # ------------------------------------------------------------------------
    print_header("Part 1: Copy-On-Write (COW) in Swift Value Types")
    
    print_step("Creating Array 'A' with initial elements [10, 20, 30]...")
    array_a = SwiftCOWArray([10, 20, 30])
    print_info("Array A Buffer ID", array_a.buffer_id)
    print_info("Array A Buffer RefCount", array_a.ref_count)

    print_step("\nAssigning 'B = A' (Value assignment / Struct copy)...")
    array_b = array_a.__copy__()
    print_info("Array A Buffer ID", array_a.buffer_id)
    print_info("Array B Buffer ID", array_b.buffer_id)
    print_info("Shared Buffer RefCount", array_a.ref_count)

    print_step("\nReading Array B elements (No mutation)...")
    print_info("Array B Data", array_b.read())
    print_info("Are Buffers Identical?", array_a.buffer_id == array_b.buffer_id)

    print_step("\nMutating Array B: appending element 40...")
    array_b.append(40)
    print_info("Array A Data", array_a.read())
    print_info("Array B Data", array_b.read())
    print_info("Array A Buffer ID", array_a.buffer_id)
    print_info("Array B Buffer ID", array_b.buffer_id)
    print_info("Are Buffers Identical after mutation?", array_a.buffer_id == array_b.buffer_id)

    # ------------------------------------------------------------------------
    # LAB PART 2: ARC, Weak References & Zeroing Memory
    # ------------------------------------------------------------------------
    print_header("Part 2: Swift ARC Lifecycle & Zeroing Weak Pointers")
    
    view_controller = SwiftObject("UserProfileViewController")
    weak_vc = WeakReference(view_controller)

    print_info("Checking Weak Pointer resolution while Owner alive", weak_vc.get().name if weak_vc.get() else None)
    
    print_step("\nReleasing Strong Reference to ViewController...")
    view_controller.release()

    resolved = weak_vc.get()
    print_info("Resolving Weak Pointer after dealloc", f"{resolved} (Swift nil / Zeroed out)")

    # ------------------------------------------------------------------------
    # LAB PART 3: Swift Unowned Trap Verification
    # ------------------------------------------------------------------------
    print_header("Part 3: Swift Unowned Reference Trap Behavior")
    
    network_service = SwiftObject("HTTPService")
    unowned_service = UnownedReference(network_service)

    print_info("Reading Unowned Reference while Target is alive", unowned_service.get().name)
    
    print_step("Deallocating HTTPService...")
    network_service.release()

    print_step("Attempting to access deallocated unowned reference...")
    try:
        _ = unowned_service.get()
    except RuntimeError as ex:
        print_err(f"Trapped correctly: {ex}")

    # ------------------------------------------------------------------------
    # LAB PART 4: Retain Cycle & Resolution
    # ------------------------------------------------------------------------
    print_header("Part 4: Retain Cycle Leakage vs Weak Delegate Pattern")

    class LeakyNode:
        def __init__(self, name: str):
            self.name = name
            self.peer: Optional['LeakyNode'] = None
        def __repr__(self):
            return f"<LeakyNode {self.name}>"

    print_step("Creating Circular Strong References (A <-> B)...")
    node_a = LeakyNode("NodeA")
    node_b = LeakyNode("NodeB")
    node_a.peer = node_b
    node_b.peer = node_a
    
    print_warn(f"Retain cycle established between {node_a} and {node_b}.")
    print_info("NodeA refcount in CPython (simulating Swift Strong Cycle)", sys.getrefcount(node_a) - 1)

    print_step("\nSolving Retain Cycle using Weak Delegate simulation...")
    class SafeDelegateNode:
        def __init__(self, name: str):
            self.name = name
            self.delegate: Optional[WeakReference] = None

    parent = SwiftObject("ParentCoordinator")
    child = SafeDelegateNode("ChildPresenter")
    child.delegate = WeakReference(parent)

    print_info("Child successfully holds weak delegate to Parent", child.delegate.get().name)
    parent.release()
    print_info("Parent deallocated cleanly. Child delegate status", child.delegate.get())

    # ------------------------------------------------------------------------
    # LAB PART 5: Method Dispatch Microbenchmarking
    # ------------------------------------------------------------------------
    benchmark_dispatch_mechanisms(iterations=200_000)

    print(f"\n{BOLD}{GREEN}✓ Lab completed successfully. All Swift runtime models verified.{RESET}\n")

if __name__ == "__main__":
    main()