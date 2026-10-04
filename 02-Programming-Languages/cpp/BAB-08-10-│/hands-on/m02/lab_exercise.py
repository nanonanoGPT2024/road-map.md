#!/usr/bin/env python3
"""
Lab Hands-on: C++ Object Model Internals (vtable, Multiple Inheritance & Move Semantics)
Modul: 08 - Advanced Systems & C++ Deep Dive
Deskripsi:
  Script ini mensimulasikan mekanisme internal runtime C++ pada arsitektur 64-bit (x86_64):
  1. Virtual Method Table (vtable) resolution dan vptr pointer injection.
  2. Memory layout calculation (data alignment, padding, multiple inheritance offsets).
  3. "this-pointer adjustment" (thunks) pada multiple inheritance call.
  4. Move semantics vs Deep Copy semantics simulasi transfer pointer heap buffer (RAII).
"""

import sys
import struct
from typing import Dict, List, Any, Callable, Optional, Tuple

# Terminal ANSI Color Formatting
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

def print_banner():
    banner = f"""
{BOLD}{CYAN}======================================================================
  C++ INTERNALS LAB: RUNTIME OBJECT MODEL & MEMORY LAYOUT SIMULATOR
  Modul 08 - Deep Dive: Virtual Dispatch, Multiple Inheritance & RAII
======================================================================{RESET}"""
    print(banner)

# ============================================================================
# Bagian 1: Simulasi RTTI dan Virtual Table (vtable)
# ============================================================================

class VTable:
    """
    Merepresentasikan Virtual Table (__vtbl) yang dibuat oleh compiler C++
    di segmen .rodata untuk setiap class polymorphic.
    """
    def __init__(self, class_name: str, rtti_type: str):
        self.class_name = class_name
        self.rtti_type = rtti_type
        # Slot vtable: index -> (method_name, function_pointer, this_adjustment_offset)
        self.slots: List[Tuple[str, Callable, int]] = []

    def add_entry(self, method_name: str, func: Callable, this_offset: int = 0):
        self.slots.append((method_name, func, this_offset))

    def dump(self, vtable_name: str):
        print(f"  {BOLD}{MAGENTA}[vtable for {vtable_name}]{RESET}")
        print(f"    offset-to-top : 0")
        print(f"    RTTI typeinfo : &typeinfo for {self.rtti_type}")
        for idx, (m_name, _, offset) in enumerate(self.slots):
            thunk_str = f" [this_adjust: {offset:+d}]" if offset != 0 else ""
            print(f"    slot [{idx}]     : {self.class_name}::{m_name}(){thunk_str}")
        print()


# ============================================================================
# Bagian 2: Simulasi Memory Layout & Multiple Inheritance
# ============================================================================

class SimulatedMemory:
    """
    Mensimulasikan byte-buffer mentah dari sebuah instance object C++ di Stack/Heap.
    Menerapkan alignment 8-byte untuk pointer arsitektur 64-bit.
    """
    def __init__(self, size: int):
        self.size = size
        self.buffer = bytearray(size)

    def write_ptr(self, offset: int, ptr_val: int):
        # Simpan 64-bit unsigned integer (pointer representation)
        struct.pack_into("<Q", self.buffer, offset, ptr_val)

    def read_ptr(self, offset: int) -> int:
        return struct.unpack_from("<Q", self.buffer, offset)[0]

    def write_int32(self, offset: int, val: int):
        struct.pack_into("<i", self.buffer, offset, val)

    def read_int32(self, offset: int) -> int:
        return struct.unpack_from("<i", self.buffer, offset)[0]

    def write_float(self, offset: int, val: float):
        struct.pack_into("<f", self.buffer, offset, val)

    def read_float(self, offset: int) -> float:
        return struct.unpack_from("<f", self.buffer, offset)[0]

    def hex_dump(self, title: str):
        print(f"{BOLD}{BLUE}--- Memory Hex Dump: {title} ({self.size} bytes) ---{RESET}")
        for i in range(0, self.size, 8):
            chunk = self.buffer[i:i+8]
            hex_bytes = " ".join(f"{b:02X}" for b in chunk)
            val_u64 = struct.unpack("<Q", chunk)[0]
            print(f"  0x{i:04X} | {hex_bytes} | u64: 0x{val_u64:016X}")
        print()


# ============================================================================
# Bagian 3: Hierarki Kelas & Thunk Adjustment
# ============================================================================
# Hierarki C++:
#   class ICamera   { virtual void capture() = 0; };
#   class IGps      { virtual void get_coordinates() = 0; };
#   class DroneNode : public ICamera, public IGps { ... };

# Registry alamat semu untuk vtable
VTABLE_ADDRESSES: Dict[int, VTable] = {}

def simulate_icamera_capture(instance_addr: int):
    print(f"    {GREEN}>> Call dispatched: ICamera::capture() on instance at 0x{instance_addr:X}{RESET}")

def simulate_drone_capture(instance_addr: int):
    print(f"    {GREEN}>> Call dispatched: DroneNode::capture() [OVERRIDDEN] on instance at 0x{instance_addr:X}{RESET}")

def simulate_igps_get_coord(instance_addr: int):
    print(f"    {GREEN}>> Call dispatched: IGps::get_coordinates() on instance at 0x{instance_addr:X}{RESET}")

def simulate_drone_get_coord(instance_addr: int):
    print(f"    {GREEN}>> Call dispatched: DroneNode::get_coordinates() [OVERRIDDEN] on instance at 0x{instance_addr:X}{RESET}")


def setup_vtables() -> Tuple[int, int, int]:
    """Menginisialisasi tabel vtable di memori global/read-only."""
    # 1. vtable untuk DroneNode primary base (ICamera interface)
    vt_drone_primary = VTable("DroneNode", "DroneNode")
    vt_drone_primary.add_entry("capture", simulate_drone_capture, this_offset=0)

    # 2. vtable untuk DroneNode secondary base (IGps interface)
    # Catatan: IGps berada di offset +16. Pemanggilan DroneNode::get_coordinates
    # lewat pointer IGps membutuhkan adjustor thunk: this = this - 16 bytes!
    vt_drone_secondary = VTable("DroneNode", "DroneNode")
    vt_drone_secondary.add_entry("get_coordinates", simulate_drone_get_coord, this_offset=-16)

    # Simpan pointer simulasi
    addr_primary = 0x0040A000
    addr_secondary = 0x0040A080

    VTABLE_ADDRESSES[addr_primary] = vt_drone_primary
    VTABLE_ADDRESSES[addr_secondary] = vt_drone_secondary

    print(f"{BOLD}[Compiler Assembly Phase: Emitting Virtual Tables in .rodata]{RESET}")
    vt_drone_primary.dump("DroneNode (Primary: ICamera)")
    vt_drone_secondary.dump("DroneNode (Secondary: IGps)")

    return addr_primary, addr_secondary, 0


# ============================================================================
# Bagian 4: Simulasi Memory Layout DroneNode Instance
# ============================================================================

class DroneNodeInstance:
    """
    Layout Objek dalam Memori (64-bit):
    Offset  0- 7: vptr_ICamera (8 bytes) -> Pointer ke vt_drone_primary
    Offset  8-11: camera_fov   (4 bytes - int32)
    Offset 12-15: [PADDING]    (4 bytes padding untuk align struct berikutnya ke 8 bytes)
    Offset 16-23: vptr_IGps    (8 bytes) -> Pointer ke vt_drone_secondary
    Offset 24-27: altitude_m   (4 bytes - float)
    Offset 28-31: [PADDING]    (4 bytes padding kelipatan total alignment)
    Total Size: 32 bytes
    """
    LAYOUT_SIZE = 32

    def __init__(self, obj_addr: int, vt_pri_addr: int, vt_sec_addr: int, fov: int, altitude: float):
        self.address = obj_addr
        self.mem = SimulatedMemory(self.LAYOUT_SIZE)

        # Inisialisasi vptr primary
        self.mem.write_ptr(0, vt_pri_addr)
        self.mem.write_int32(8, fov)

        # Inisialisasi vptr secondary
        self.mem.write_ptr(16, vt_sec_addr)
        self.mem.write_float(24, altitude)

    def print_layout(self):
        print(f"{BOLD}{WHITE}Object Layout: DroneNode at 0x{self.address:08X}{RESET}")
        print(f"  +0x00: vptr_ICamera  -> 0x{self.mem.read_ptr(0):08X}")
        print(f"  +0x08: camera_fov    = {self.mem.read_int32(8)} deg (int32)")
        print(f"  +0x0C: [PAD 4 bytes]")
        print(f"  +0x10: vptr_IGps     -> 0x{self.mem.read_ptr(16):08X} (Offset IGps base)")
        print(f"  +0x18: altitude_m    = {self.mem.read_float(24):.2f} m (float)")
        print(f"  +0x1C: [PAD 4 bytes]")
        print(f"  Total sizeof(DroneNode) = {self.LAYOUT_SIZE} bytes")
        self.mem.hex_dump("Instance Memory Representation")


# ============================================================================
# Bagian 5: Simulasi Dynamic Dispatch & Thunk Resolution
# ============================================================================

def virtual_call(interface_ptr: int, slot_idx: int):
    """
    Mensimulasikan instruksi mesin C++ dynamic call:
      mov rax, [rdi]        ; Ambil vptr dari offset 0 interface
      mov rax, [rax + slot] ; Ambil method pointer dari vtable slot
      call rax              ; Eksekusi dengan adjustment pointer `this`
    """
    # 1. Baca vptr dari objek
    # Dalam simulasi, kita map address ke vtable
    vtable = None
    target_offset = 0
    if interface_ptr == 0x00100000: # Base primary
        vtable = VTABLE_ADDRESSES[0x0040A000]
    elif interface_ptr == 0x00100010: # Base secondary (+16 bytes)
        vtable = VTABLE_ADDRESSES[0x0040A080]
        target_offset = 16
    else:
        raise ValueError("Invalid pointer dereference!")

    method_name, target_func, this_adjustment = vtable.slots[slot_idx]

    # Hitung adjusted this pointer
    adjusted_this = interface_ptr + this_adjustment

    print(f"  {YELLOW}[Virtual Dispatch Step]{RESET}")
    print(f"   Caller 'this' ptr     : 0x{interface_ptr:08X}")
    print(f"   VTable entry invoked  : {vtable.class_name}::{method_name}")
    print(f"   This-Adjustment Thunk : {this_adjustment:+d} bytes")
    print(f"   Final 'this' argument : 0x{adjusted_this:08X} (Matches complete DroneNode address!)")
    
    # Jalankan function
    target_func(adjusted_this)


# ============================================================================
# Bagian 6: Simulasi C++ Move Semantics vs Deep Copy (std::vector buffer)
# ============================================================================

class CppResourceVector:
    """
    Mensimulasikan buffer heap class C++ dengan Copy Constructor dan Move Constructor.
    """
    def __init__(self, name: str, size: int):
        self.name = name
        self.size = size
        self.heap_address = id(self) & 0xFFFFFFFF if size > 0 else 0
        self.data = list(range(size))

    @classmethod
    def deep_copy(cls, src: 'CppResourceVector', new_name: str) -> 'CppResourceVector':
        """Simulasi C++ Copy Constructor: T(const T& other)"""
        print(f"  {RED}[Copy Constructor]{RESET} Allocating NEW heap buffer for {new_name}...")
        clone = cls(new_name, src.size)
        clone.data = list(src.data)
        print(f"  Result: {src.name} [heap:0x{src.heap_address:X}] duplicated to {clone.name} [heap:0x{clone.heap_address:X}]")
        return clone

    @classmethod
    def move_constructor(cls, src: 'CppResourceVector', new_name: str) -> 'CppResourceVector':
        """Simulasi C++ Move Constructor: T(T&& other) noexcept"""
        print(f"  {GREEN}[Move Constructor]{RESET} Pilfering heap pointer (O(1) shallow steal) for {new_name}...")
        moved_obj = cls(new_name, 0)
        # Pilfer heap resources
        moved_obj.heap_address = src.heap_address
        moved_obj.size = src.size
        moved_obj.data = src.data

        # Nullify/Invalidate source object state (like std::move post-condition)
        src.heap_address = 0
        src.size = 0
        src.data = []
        print(f"  Result: {new_name} took ownership [heap:0x{moved_obj.heap_address:X}]. Source {src.name} set to nullptr/empty.")
        return moved_obj


# ============================================================================
# Main Execution Pipeline
# ============================================================================

def main():
    print_banner()

    # STEP 1: Membangun VTable
    print(f"{BOLD}[1] Initializing Runtime vtables & Layout Offsets{RESET}")
    vt_pri, vt_sec, _ = setup_vtables()

    # STEP 2: Instansiasi Objek C++ di Heap
    print(f"{BOLD}[2] Instantiating C++ polymorphic class: DroneNode{RESET}")
    drone_obj_addr = 0x00100000
    drone = DroneNodeInstance(
        obj_addr=drone_obj_addr,
        vt_pri_addr=vt_pri,
        vt_sec_addr=vt_sec,
        fov=120,
        altitude=45.5
    )
    drone.print_layout()

    # STEP 3: Multiple Inheritance Dynamic Dispatch & Thunk
    print(f"{BOLD}[3] Demonstrating Multiple Inheritance Virtual Dispatch & Thunks{RESET}")

    # Case A: Call via ICamera* (Base 1 - Offset 0)
    icamera_ptr = drone_obj_addr
    print(f"\n--- Scenario A: Calling via primary pointer: ICamera* ptr = 0x{icamera_ptr:08X} ---")
    virtual_call(icamera_ptr, slot_idx=0)

    # Case B: Call via IGps* (Base 2 - Offset +16)
    igps_ptr = drone_obj_addr + 16
    print(f"\n--- Scenario B: Upcasted to secondary pointer: IGps* ptr = 0x{igps_ptr:08X} ---")
    print(f"Notice: Function DroneNode::get_coordinates expects DroneNode*, so 'this' must be adjusted back by -16.")
    virtual_call(igps_ptr, slot_idx=0)

    # STEP 4: Move Semantics vs Copy Semantics Verification
    print(f"\n{BOLD}[4] RAII & Move Semantics Internals (rvalue references simulation){RESET}")
    res_a = CppResourceVector("HeavyTelemetryData_A", 1_000_000)
    print(f"Original Object: {res_a.name} holds buffer at 0x{res_a.heap_address:X} (Size: {res_a.size})")

    print("\n-- Executing Deep Copy: Telemetry_B(Telemetry_A) --")
    res_b = CppResourceVector.deep_copy(res_a, "HeavyTelemetryData_B")

    print("\n-- Executing Move: Telemetry_C(std::move(Telemetry_A)) --")
    res_c = CppResourceVector.move_constructor(res_a, "HeavyTelemetryData_C")

    # Verifikasi State Akhir
    print(f"\n{BOLD}{CYAN}Final Verification State:{RESET}")
    print(f"  {res_a.name:<25} -> heap_ptr: 0x{res_a.heap_address:08X}, elements: {len(res_a.data)}")
    print(f"  {res_b.name:<25} -> heap_ptr: 0x{res_b.heap_address:08X}, elements: {len(res_b.data)}")
    print(f"  {res_c.name:<25} -> heap_ptr: 0x{res_c.heap_address:08X}, elements: {len(res_c.data)}")

    assert res_a.heap_address == 0, "Source object must be invalidated after move!"
    assert res_c.size == 1_000_000, "Moved object must retain original size!"
    print(f"\n{GREEN}{BOLD}[SUCCESS] C++ Internals & Virtual Dispatch Simulation completed cleanly.{RESET}\n")

if __name__ == "__main__":
    main()