#!/usr/bin/env python3
"""
Lab Hands-on: JS Memory Lifecycle, Garbage Collection & Low-Level Primitives
Simulates V8 engine memory internals:
  1. Low-level ArrayBuffer & DataView binary layout (IEEE-754, Endianness).
  2. Heap Object Graph with root sets and pointer tracing.
  3. Reference Counting GC failure on circular dependencies.
  4. Tracing Mark-and-Sweep GC resolution.
"""

import sys
import struct
import time
from typing import Dict, List, Set, Optional

# --- Terminal ANSI Styling ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_CYAN   = "\033[36m"
CLR_WHITE  = "\033[37m"

def log_header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== {title} ==={CLR_RESET}")

def log_info(msg: str) -> None:
    print(f"{CLR_CYAN}[INFO]{CLR_RESET} {msg}")

def log_success(msg: str) -> None:
    print(f"{CLR_GREEN}[SUCCESS]{CLR_RESET} {msg}")

def log_warn(msg: str) -> None:
    print(f"{CLR_YELLOW}[WARN]{CLR_RESET} {msg}")

def log_error(msg: str) -> None:
    print(f"{CLR_RED}[ERROR]{CLR_RESET} {msg}")


# ============================================================================
# 1. LOW-LEVEL PRIMITIVES: ArrayBuffer & DataView Emulation
# ============================================================================

class ArrayBuffer:
    """Emulates ECMAScript ArrayBuffer: fixed-length contiguous binary memory block."""
    def __init__(self, byte_length: int):
        self.byte_length = byte_length
        self._buffer = bytearray(byte_length)

    def __len__(self):
        return self.byte_length


class DataView:
    """Emulates ECMAScript DataView: heterogeneous low-level byte reader/writer."""
    def __init__(self, buffer: ArrayBuffer, byte_offset: int = 0, byte_length: Optional[int] = None):
        if byte_offset < 0 or byte_offset > buffer.byte_length:
            raise IndexError("Offset out of bounds.")
        self.buffer = buffer
        self.byte_offset = byte_offset
        self.byte_length = (buffer.byte_length - byte_offset) if byte_length is None else byte_length
        if self.byte_offset + self.byte_length > buffer.byte_length:
            raise IndexError("DataView range exceeds buffer bounds.")

    def set_uint8(self, offset: int, value: int) -> None:
        idx = self.byte_offset + offset
        struct.pack_into("<B", self.buffer._buffer, idx, value & 0xFF)

    def set_uint16(self, offset: int, value: int, little_endian: bool = True) -> None:
        fmt = "<H" if little_endian else ">H"
        idx = self.byte_offset + offset
        struct.pack_into(fmt, self.buffer._buffer, idx, value & 0xFFFF)

    def set_float64(self, offset: int, value: float, little_endian: bool = True) -> None:
        fmt = "<d" if little_endian else ">d"
        idx = self.byte_offset + offset
        struct.pack_into(fmt, self.buffer._buffer, idx, value)

    def get_float64(self, offset: int, little_endian: bool = True) -> float:
        fmt = "<d" if little_endian else ">d"
        idx = self.byte_offset + offset
        return struct.unpack_from(fmt, self.buffer._buffer, idx)[0]

    def hex_dump(self) -> str:
        segment = self.buffer._buffer[self.byte_offset : self.byte_offset + self.byte_length]
        return " ".join(f"{b:02X}" for b in segment)


# ============================================================================
# 2. V8-LIKE HEAP & GARBAGE COLLECTOR EMULATOR
# ============================================================================

class HeapObject:
    """Represents an allocated object inside JavaScript Virtual Machine Heap."""
    _auto_id = 1

    def __init__(self, name: str, payload_size: int = 64):
        self.id = HeapObject._auto_id
        HeapObject._auto_id += 1
        self.name = name
        self.size = payload_size
        self.pointers: Set[int] = set() # Outgoing references (Target Object IDs)
        self.ref_count: int = 0         # Used for Naive Reference Counting
        self.marked: bool = False       # Used for Mark-and-Sweep

    def __repr__(self):
        return f"<Obj {self.name} (id:{self.id}, size:{self.size}B)>"


class V8GarbageCollector:
    """Simulates Root Set tracking, Reference Counting, and Tracing Mark-and-Sweep."""
    def __init__(self):
        self.heap: Dict[int, HeapObject] = {}
        self.root_set: Set[int] = set() # Global scope, Execution Stack variables

    def allocate(self, name: str, size: int = 64) -> HeapObject:
        obj = HeapObject(name, size)
        self.heap[obj.id] = obj
        return obj

    def add_reference(self, from_obj: HeapObject, to_obj: HeapObject) -> None:
        if to_obj.id not in from_obj.pointers:
            from_obj.pointers.add(to_obj.id)
            to_obj.ref_count += 1

    def remove_reference(self, from_obj: HeapObject, to_obj: HeapObject) -> None:
        if to_obj.id in from_obj.pointers:
            from_obj.pointers.remove(to_obj.id)
            to_obj.ref_count -= 1

    def add_root(self, obj: HeapObject) -> None:
        if obj.id not in self.root_set:
            self.root_set.add(obj.id)
            obj.ref_count += 1

    def remove_root(self, obj: HeapObject) -> None:
        if obj.id in self.root_set:
            self.root_set.remove(obj.id)
            obj.ref_count -= 1

    def get_heap_memory_usage(self) -> int:
        return sum(obj.size for obj in self.heap.values())

    def simulate_reference_counting_gc(self) -> int:
        """Naive Ref Counting: collect objects whose ref_count drops to zero.
        Cannot collect isolated cyclic islands."""
        reclaimed_bytes = 0
        changed = True

        while changed:
            changed = False
            zero_refs = [obj for obj in self.heap.values() if obj.ref_count <= 0]
            for dead in zero_refs:
                # Release outgoing references
                for child_id in dead.pointers:
                    if child_id in self.heap:
                        self.heap[child_id].ref_count -= 1
                reclaimed_bytes += dead.size
                del self.heap[dead.id]
                changed = True

        return reclaimed_bytes

    def simulate_mark_and_sweep_gc(self) -> int:
        """Tracing GC: Root-directed Depth First Search marking, then sweep unreachable."""
        # 1. MARK PHASE
        for obj in self.heap.values():
            obj.marked = False

        traversal_stack: List[int] = list(self.root_set)
        marked_count = 0

        while traversal_stack:
            curr_id = traversal_stack.pop()
            if curr_id in self.heap:
                curr_obj = self.heap[curr_id]
                if not curr_obj.marked:
                    curr_obj.marked = True
                    marked_count += 1
                    for child_id in curr_obj.pointers:
                        if child_id in self.heap and not self.heap[child_id].marked:
                            traversal_stack.append(child_id)

        # 2. SWEEP PHASE
        reclaimed_bytes = 0
        dead_ids = [obj_id for obj_id, obj in self.heap.items() if not obj.marked]
        
        for dead_id in dead_ids:
            reclaimed_bytes += self.heap[dead_id].size
            del self.heap[dead_id]

        return reclaimed_bytes


# ============================================================================
# 3. INTERACTIVE LAB BENCHMARK & DEMONSTRATION
# ============================================================================

def run_low_level_primitives_demo():
    log_header("STEP 1: Low-Level Primitives (ArrayBuffer & DataView)")
    
    # 16-byte raw allocation
    buffer = ArrayBuffer(16)
    view = DataView(buffer)
    
    log_info(f"Allocated raw ArrayBuffer: {buffer.byte_length} bytes.")
    
    # Pack values: Uint8 at offset 0, Uint16 at offset 1, Float64 at offset 4
    view.set_uint8(0, 0xAA)
    view.set_uint16(1, 0xBEEF, little_endian=True)
    pi_val = 3.141592653589793
    view.set_float64(4, pi_val, little_endian=True)
    
    print(f"  {CLR_WHITE}Byte Memory Dump:{CLR_RESET} [ {view.hex_dump()} ]")
    
    read_back = view.get_float64(4, little_endian=True)
    log_success(f"Decoded Float64 (IEEE-754 LE) at offset 4: {read_back:.15f}")


def run_cyclic_gc_lab():
    log_header("STEP 2: Heap Graph, Circular Reference & GC Simulation")
    gc = V8GarbageCollector()

    # Step A: Allocate objects and establish dependencies
    log_info("Simulating execution context frame...")
    window_scope = gc.allocate("globalThis", 128)
    gc.add_root(window_scope)

    cache_obj = gc.allocate("CacheMap", 256)
    gc.add_reference(window_scope, cache_obj)

    # Isolated circular island (e.g. Closure retaining DOM node & node retaining closure)
    dom_node = gc.allocate("HTMLDivElement", 512)
    event_handler = gc.allocate("EventListenerClosure", 512)
    
    # Link to global temporarily
    gc.add_reference(window_scope, dom_node)
    
    # Form circular dependency: dom_node <---> event_handler
    gc.add_reference(dom_node, event_handler)
    gc.add_reference(event_handler, dom_node)
    
    log_info(f"Heap allocated with 4 objects. Total Heap: {gc.get_heap_memory_usage()} Bytes.")
    print(f"  Graph: globalThis -> CacheMap")
    print(f"  Graph: globalThis -> HTMLDivElement <---> EventListenerClosure")

    # Step B: Remove link to dom_node, making the circular pair orphaned
    log_warn("Detaching DOM node from root scope (simulating element removal from DOM tree)...")
    gc.remove_reference(window_scope, dom_node)

    print(f"  Current Heap Status: {len(gc.heap)} objects active.")
    print(f"  dom_node refCount: {dom_node.ref_count} | event_handler refCount: {event_handler.ref_count}")

    # Step C: Run Naive Reference Counting
    log_header("STEP 3: Executing Reference Counting GC")
    start = time.perf_counter()
    reclaimed = gc.simulate_reference_counting_gc()
    elapsed = (time.perf_counter() - start) * 1000
    
    log_error(f"Ref Counting reclaimed: {reclaimed} Bytes ({elapsed:.3f} ms).")
    if dom_node.id in gc.heap and event_handler.id in gc.heap:
        log_error("MEMORY LEAK CONFIRMED: Circular reference island survived Reference Counting!")
        print(f"  Leaked Objects in Heap: {[obj.name for obj in gc.heap.values()]}")
        print(f"  Retained Heap Size: {gc.get_heap_memory_usage()} Bytes")

    # Step D: Run Tracing Mark-and-Sweep
    log_header("STEP 4: Executing Tracing Mark-and-Sweep (V8 Major GC Pattern)")
    start = time.perf_counter()
    reclaimed = gc.simulate_mark_and_sweep_gc()
    elapsed = (time.perf_counter() - start) * 1000

    log_success(f"Mark-and-Sweep reclaimed: {reclaimed} Bytes ({elapsed:.3f} ms).")
    print(f"  Heap Objects Surviving: {[obj.name for obj in gc.heap.values()]}")
    print(f"  Active Heap Memory after Tracing GC: {gc.get_heap_memory_usage()} Bytes")
    
    assert dom_node.id not in gc.heap, "DOM Node must be cleared"
    assert event_handler.id not in gc.heap, "Event Handler closure must be cleared"
    log_success("Cycles successfully collected! Mark-and-Sweep visited only reachable roots.")


if __name__ == "__main__":
    print(f"{CLR_BOLD}{CLR_GREEN}=== JAVASCRIPT MEMORY LIFECYCLE & GC LAB ==={CLR_RESET}")
    print(f"Python Runtime: {sys.version.split()[0]} | Architecture: {struct.calcsize('P') * 8}-bit")
    run_low_level_primitives_demo()
    run_cyclic_gc_lab()
    print(f"\n{CLR_BOLD}{CLR_GREEN}[LAB COMPLETE] All primitives and GC mechanics verified.{CLR_RESET}")