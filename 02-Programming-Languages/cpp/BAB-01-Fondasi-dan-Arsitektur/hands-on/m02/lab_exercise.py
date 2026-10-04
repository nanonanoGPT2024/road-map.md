#!/usr/bin/env python3
"""
Lab Hands-on: C++ Object Model, VTable Dispatch, and RAII Mechanics
Topic: C++ Internals Simulation (Memory Layout, Virtual Tables, Smart Pointers)
Category: 02-Programming-Languages / Bab 01 - Modul 02 Deep Dive

Simulates:
1. Low-level object memory layout (vptr, padding, field alignments).
2. Dynamic polymorphism via simulated Virtual Method Table (vtable).
3. RAII and Smart Pointer ownership semantics (UniquePtr and SharedPtr with Control Block).
"""

import sys
import struct
import typing

# --- ANSI Terminal Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"

def print_section(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 70}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}[LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 70}{CLR_RESET}")

def print_sub(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_YELLOW}>>> {title}{CLR_RESET}")


# ============================================================================
# 1. SIMULATED C++ HEAP ARENA & MEMORY ALIGNMENT
# ============================================================================
class SimulatedHeap:
    """
    Simulates raw heap memory with word-aligned allocations (64-bit / 8 bytes).
    Tracks allocations and deallocations to detect leaks or double-frees.
    """
    def __init__(self, size: int = 1024):
        self.size = size
        self.arena = bytearray(size)
        self.allocations: typing.Dict[int, int] = {}
        self.current_offset = 0

    def allocate(self, num_bytes: int, alignment: int = 8) -> int:
        """Emulates malloc / operator new with byte-boundary alignment."""
        padding = (alignment - (self.current_offset % alignment)) % alignment
        start_addr = self.current_offset + padding
        end_addr = start_addr + num_bytes

        if end_addr > self.size:
            raise MemoryError("std::bad_alloc: Simulated heap out of memory")

        self.current_offset = end_addr
        self.allocations[start_addr] = num_bytes
        return start_addr

    def deallocate(self, address: int) -> None:
        """Emulates free / operator delete."""
        if address not in self.allocations:
            raise RuntimeError(f"{CLR_RED}Heap corruption: Invalid or double free at 0x{address:04X}{CLR_RESET}")
        
        # Zero-out released memory block
        length = self.allocations[address]
        self.arena[address:address + length] = b"\x00" * length
        del self.allocations[address]

    def hex_dump(self, address: int, length: int) -> str:
        """Generates a hex dump representing raw byte memory layout."""
        raw = self.arena[address:address + length]
        hex_str = " ".join(f"{b:02X}" for b in raw)
        return f"0x{address:04X}: [ {hex_str} ]"


GLOBAL_HEAP = SimulatedHeap(2048)


# ============================================================================
# 2. C++ OBJECT MODEL & VIRTUAL DISPATCH (VTABLE SIMULATION)
# ============================================================================
class VTable:
    """Represents a static virtual method table constructed at compile time."""
    def __init__(self, class_name: str, methods: typing.Dict[str, typing.Callable]):
        self.class_name = class_name
        self.methods = methods

    def dispatch(self, method_name: str, instance: "CppObject", *args):
        if method_name not in self.methods:
            raise AttributeError(f"Abstract or undefined virtual method: {method_name}")
        return self.methods[method_name](instance, *args)


class CppObject:
    """
    Base representation of a C++ class instance with an explicit virtual pointer (_vptr)
    placed at memory offset 0, followed by member variable layouts.
    """
    def __init__(self, vtable: VTable, data_size: int):
        self.vtable = vtable
        # 8 bytes for _vptr + data_size
        self.total_size = 8 + data_size
        self.heap_address = GLOBAL_HEAP.allocate(self.total_size, alignment=8)
        
        # Write mock 64-bit vptr address into the first 8 bytes of the object instance
        vptr_mock = id(self.vtable) & 0xFFFFFFFFFFFFFFFF
        GLOBAL_HEAP.arena[self.heap_address:self.heap_address + 8] = struct.pack("<Q", vptr_mock)

    def invoke_virtual(self, method_name: str, *args):
        """Simulates: this->_vptr->function_table[idx](this, args)"""
        return self.vtable.dispatch(method_name, self, *args)

    def destroy(self):
        """Virtual destructor invocation."""
        self.vtable.dispatch("~destructor", self)
        GLOBAL_HEAP.deallocate(self.heap_address)


# --- Class Hierarchy Definitions ---

def shape_destructor(obj):
    print(f"  {CLR_MAGENTA}[~Shape()]{CLR_RESET} Base destructor called for address 0x{obj.heap_address:04X}")

def circle_destructor(obj):
    print(f"  {CLR_MAGENTA}[~Circle()]{CLR_RESET} Destroying Circle instance at 0x{obj.heap_address:04X}")
    shape_destructor(obj)

def rectangle_destructor(obj):
    print(f"  {CLR_MAGENTA}[~Rectangle()]{CLR_RESET} Destroying Rectangle instance at 0x{obj.heap_address:04X}")
    shape_destructor(obj)

def circle_draw(obj):
    # Reads radius (float, 4 bytes) from offset 8
    radius = struct.unpack("<f", GLOBAL_HEAP.arena[obj.heap_address + 8:obj.heap_address + 12])[0]
    return f"Drawing Circle (radius = {radius:.2f})"

def circle_area(obj):
    radius = struct.unpack("<f", GLOBAL_HEAP.arena[obj.heap_address + 8:obj.heap_address + 12])[0]
    return 3.1415926535 * (radius ** 2)

def rectangle_draw(obj):
    # Reads width and height (float, float) from offset 8 and 12
    w, h = struct.unpack("<ff", GLOBAL_HEAP.arena[obj.heap_address + 8:obj.heap_address + 16])
    return f"Drawing Rectangle (w = {w:.2f}, h = {h:.2f})"

def rectangle_area(obj):
    w, h = struct.unpack("<ff", GLOBAL_HEAP.arena[obj.heap_address + 8:obj.heap_address + 16])
    return w * h

# Static VTables
VTABLE_CIRCLE = VTable("Circle", {
    "draw": circle_draw,
    "area": circle_area,
    "~destructor": circle_destructor
})

VTABLE_RECTANGLE = VTable("Rectangle", {
    "draw": rectangle_draw,
    "area": rectangle_area,
    "~destructor": rectangle_destructor
})


class Circle(CppObject):
    def __init__(self, radius: float):
        # 8 bytes _vptr + 4 bytes float radius + 4 bytes padding = 16 bytes total
        super().__init__(VTABLE_CIRCLE, data_size=8)
        # Pack float into offset 8
        GLOBAL_HEAP.arena[self.heap_address + 8:self.heap_address + 12] = struct.pack("<f", radius)


class Rectangle(CppObject):
    def __init__(self, width: float, height: float):
        # 8 bytes _vptr + 4 bytes w + 4 bytes h = 16 bytes total
        super().__init__(VTABLE_RECTANGLE, data_size=8)
        GLOBAL_HEAP.arena[self.heap_address + 8:self.heap_address + 16] = struct.pack("<ff", width, height)


# ============================================================================
# 3. RAII & SMART POINTER ENGINE (std::unique_ptr & std::shared_ptr)
# ============================================================================
class UniquePtr(typing.Generic[typing.TypeVar("T")]):
    """
    Simulates std::unique_ptr<T>
    Exclusive ownership model: Non-copyable, Move-constructible, Auto-destructing on scope exit.
    """
    def __init__(self, raw_ptr: typing.Optional[CppObject] = None):
        self._ptr = raw_ptr

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.reset()

    def get(self) -> typing.Optional[CppObject]:
        return self._ptr

    def release(self) -> typing.Optional[CppObject]:
        """Relinquishes ownership and returns raw pointer without calling destructor."""
        temp = self._ptr
        self._ptr = None
        return temp

    def reset(self, new_ptr: typing.Optional[CppObject] = None) -> None:
        """Destroys current owned resource and optionally takes new ownership."""
        if self._ptr is not None:
            self._ptr.destroy()
        self._ptr = new_ptr

    def move(self) -> "UniquePtr":
        """Simulates std::move(unique_ptr)."""
        if self._ptr is None:
            return UniquePtr(None)
        transferred_ptr = self.release()
        return UniquePtr(transferred_ptr)


class ControlBlock:
    """Heap-allocated control block for std::shared_ptr tracking reference counts."""
    def __init__(self, raw_ptr: CppObject):
        self.raw_ptr = raw_ptr
        self.strong_ref_count = 1


class SharedPtr:
    """
    Simulates std::shared_ptr<T>
    Shared ownership model: Reference-counted lifetime management.
    """
    def __init__(self, raw_ptr: typing.Optional[CppObject] = None):
        if raw_ptr is not None:
            self._control_block = ControlBlock(raw_ptr)
        else:
            self._control_block = None

    @classmethod
    def from_existing(cls, existing: "SharedPtr") -> "SharedPtr":
        """Copy Constructor: Increments reference count."""
        instance = cls()
        if existing._control_block is not None:
            instance._control_block = existing._control_block
            instance._control_block.strong_ref_count += 1
        return instance

    def use_count(self) -> int:
        return self._control_block.strong_ref_count if self._control_block else 0

    def get(self) -> typing.Optional[CppObject]:
        return self._control_block.raw_ptr if self._control_block else None

    def release(self) -> None:
        """Simulates destructor/decrement reference."""
        if self._control_block is not None:
            self._control_block.strong_ref_count -= 1
            ref = self._control_block.strong_ref_count
            print(f"  {CLR_BLUE}[SharedPtr Decrement]{CLR_RESET} Current use_count: {ref}")
            if ref == 0:
                print(f"  {CLR_RED}[SharedPtr Trigger]{CLR_RESET} Ref count 0, calling destructor...")
                self._control_block.raw_ptr.destroy()
                self._control_block = None


# ============================================================================
# 4. EXECUTION AND VERIFICATION PIPELINE
# ============================================================================
def main() -> None:
    print(f"{CLR_BOLD}{CLR_GREEN}Initiating C++ Internals & Deep Dive Lab Environment...{CLR_RESET}")

    # STEP 1: Memory Layout & VTable Dispatch Inspection
    print_section("1. Object Memory Layout & VTable Dynamic Dispatch")
    
    circle = Circle(radius=5.5)
    rect = Rectangle(width=4.0, height=7.5)

    print(f"Instantiated Circle at Address: 0x{circle.heap_address:04X}, Size: {circle.total_size} bytes")
    print(f"Memory Hex Dump: {GLOBAL_HEAP.hex_dump(circle.heap_address, circle.total_size)}")
    
    print(f"Instantiated Rectangle at Address: 0x{rect.heap_address:04X}, Size: {rect.total_size} bytes")
    print(f"Memory Hex Dump: {GLOBAL_HEAP.hex_dump(rect.heap_address, rect.total_size)}")

    print_sub("Virtual Method Resolution (Polymorphism via _vptr)")
    polymorphic_shapes: typing.List[CppObject] = [circle, rect]
    
    for idx, shape in enumerate(polymorphic_shapes):
        draw_output = shape.invoke_virtual("draw")
        area_output = shape.invoke_virtual("area")
        print(f"Shape[{idx}] (Class: {shape.vtable.class_name}) ->")
        print(f"   vptr points to: {shape.vtable.class_name}_VTable")
        print(f"   draw(): {draw_output}")
        print(f"   area(): {area_output:.4f}")

    # Manually clean polymorphic instances
    print_sub("Explicit Destruction of Stack Instances")
    circle.destroy()
    rect.destroy()

    # STEP 2: RAII with std::unique_ptr and Move Semantics
    print_section("2. RAII & std::unique_ptr Move Semantics")

    print("Entering scope with std::unique_ptr<Circle>...")
    with UniquePtr(Circle(12.0)) as uptr1:
        ptr = uptr1.get()
        print(f"  uptr1 holds object at: 0x{ptr.heap_address:04X}")
        print(f"  Dynamic Area Call: {ptr.invoke_virtual('area'):.2f}")

        print_sub("Move Semantics Emulation: std::move(uptr1) -> uptr2")
        uptr2 = uptr1.move()
        print(f"  uptr1.get() is now: {uptr1.get()}")
        print(f"  uptr2 holds object at: 0x{uptr2.get().heap_address:04X}")
        
        # Explicit reset of uptr2
        print_sub("Explicit uptr2.reset() before scope exit")
        uptr2.reset()

    print("Scope exited safely without memory leaks.")

    # STEP 3: Reference Counting with std::shared_ptr
    print_section("3. Control Block & Reference Counting (std::shared_ptr)")
    
    print("Creating primary shared_ptr owning Rectangle(10.0, 2.0)...")
    sp1 = SharedPtr(Rectangle(10.0, 2.0))
    print(f"sp1 use_count: {sp1.use_count()} | Target Addr: 0x{sp1.get().heap_address:04X}")

    print_sub("Creating sp2 via Copy Constructor (sp2 = sp1)")
    sp2 = SharedPtr.from_existing(sp1)
    print(f"sp1 use_count: {sp1.use_count()} | sp2 use_count: {sp2.use_count()}")

    print_sub("Creating sp3 via Copy Constructor (sp3 = sp2)")
    sp3 = SharedPtr.from_existing(sp2)
    print(f"sp1: {sp1.use_count()}, sp2: {sp2.use_count()}, sp3: {sp3.use_count()}")

    print_sub("Releasing instances progressively (Simulating Out-Of-Scope exits)")
    print("Release sp1:")
    sp1.release()
    print(f"sp2 use_count: {sp2.use_count()}")

    print("Release sp2:")
    sp2.release()
    print(f"sp3 use_count: {sp3.use_count()}")

    print("Release sp3 (Final Reference -> triggers destruction):")
    sp3.release()

    # STEP 4: Memory Leak Verification
    print_section("4. Global Heap Allocation & Leak Audit")
    remaining_allocs = len(GLOBAL_HEAP.allocations)
    if remaining_allocs == 0:
        print(f"{CLR_BOLD}{CLR_GREEN}[PASS] Memory Audit: 0 leaks detected. All C++ instances properly destroyed.{CLR_RESET}")
    else:
        print(f"{CLR_BOLD}{CLR_RED}[FAIL] Memory Audit: {remaining_allocs} unmanaged allocations remain on heap!{CLR_RESET}")
        for addr, sz in GLOBAL_HEAP.allocations.items():
            print(f"  Leak at 0x{addr:04X} ({sz} bytes)")
        sys.exit(1)


if __name__ == "__main__":
    main()