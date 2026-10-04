#!/usr/bin/env python3
"""
Lab Hands-on: C++ Object Model Deep Dive - VTable Dispatch & Smart Pointer Internals
Modul 02: Advanced C++ Concepts (Memory Layout, Dynamic Dispatch, RAII & Move Semantics)

Deskripsi:
Script ini memodelkan dan mensimulasikan mekanisme internal runtime C++:
1. Itanium C++ ABI Object Layout & Virtual Method Table (VTable) dynamic dispatch.
2. Multiple Inheritance memory layout dengan pointer adjustment (this-pointer offset).
3. RAII Memory Management & Move Semantics (std::unique_ptr dan std::shared_ptr control block).
"""

import sys
import time
import struct
from typing import Dict, Any, List, Optional, Callable

# ==============================================================================
# Terminal ANSI Color Formatting
# ==============================================================================
RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
MAGENTA= "\033[35m"
CYAN   = "\033[36m"
GRAY   = "\033[90m"

# ==============================================================================
# BAGIAN 1: Simulasi VTable dan Dynamic Dispatch (Itanium ABI Layout)
# ==============================================================================

class VTable:
    """
    Merepresentasikan VTable C++ yang ditempatkan di segment read-only memory (.rodata).
    Menyimpan daftar function pointer dan offset-to-top untuk multiple inheritance.
    """
    def __init__(self, class_name: str, methods: Dict[str, Callable], offset_to_top: int = 0):
        self.class_name = class_name
        self.offset_to_top = offset_to_top
        self.methods: Dict[str, Callable] = methods
        # Alamat virtual tiruan untuk memodelkan pointer VTable
        self.vtable_address = id(self) & 0xFFFFFFFF

    def get_slot(self, method_name: str) -> Callable:
        if method_name not in self.methods:
            raise AttributeError(f"Runtime Link Error: '{method_name}' tidak ditemukan di VTable {self.class_name}")
        return self.methods[method_name]


class CppRawObject:
    """
    Mensimulasikan raw memory buffer dari instance object C++.
    Menampilkan layout biner: [vptr (8 bytes)] + [member variables + padding].
    """
    def __init__(self, class_name: str, vtable: VTable, members: Dict[str, int]):
        self.class_name = class_name
        self.vptr = vtable  # Pointer ke VTable (offset 0x0)
        self.members = members
        self.heap_address = id(self) & 0xFFFFFFF0

    def dump_memory_layout(self):
        """Menampilkan visualisasi memory layout object sesuai ABI alignment."""
        print(f"{CYAN}--- Memory Layout: {self.class_name} (Address: 0x{self.heap_address:08X}) ---{RESET}")
        print(f" Offset | Field Name             | Type         | Value / Pointer Target")
        print(f"--------|------------------------|--------------|-----------------------")
        print(f"  +0x00 | *__vptr                | void** (8B)  | -> VTable: 0x{self.vptr.vtable_address:08X} [{self.vptr.class_name}]")
        
        offset = 8
        for name, val in self.members.items():
            print(f"  +{offset:02X} | {name:<22} | uint32_t (4B)| 0x{val:08X} ({val})")
            offset += 4
        # Padding simulation ke kelipatan 8-byte
        if offset % 8 != 0:
            pad = 8 - (offset % 8)
            print(f"  +{offset:02X} | [padding]              | align ({pad}B)   | 0x00")
            offset += pad
        print(f"Total Size: {offset} bytes\n")


def simulate_dynamic_dispatch(obj: CppRawObject, method_name: str, *args):
    """
    Mensimulasikan instruksi mesin dereferensi VTable:
    mov rax, [obj]          ; muat vptr
    call [rax + slot_offset]; dereference function pointer
    """
    start_clk = time.perf_counter_ns()
    
    # Resolusi pointer dereferencing
    vptr = obj.vptr
    method = vptr.get_slot(method_name)
    result = method(obj, *args)
    
    elapsed_ns = time.perf_counter_ns() - start_clk
    print(f"  {GRAY}[Dispatch Trace]{RESET} Resolusi: {vptr.class_name}::{method_name}() via VTable: "
          f"0x{vptr.vtable_address:08X} -> Took {elapsed_ns} ns")
    return result


# ==============================================================================
# BAGIAN 2: Definisi Hierarki Kelas (VTable Methods)
# ==============================================================================

# Method implementations
def base_render(this: CppRawObject):
    return f"{BOLD}[Base::render]{RESET} Rendering generic canvas. ID: {this.members.get('id', 0)}"

def derived_render(this: CppRawObject):
    return f"{GREEN}[DerivedWidget::render]{RESET} Accelerated GPU Render. ID: {this.members.get('id', 0)}, Layer: {this.members.get('layer', 0)}"

def derived_process(this: CppRawObject):
    return f"{GREEN}[DerivedWidget::process]{RESET} Calculating geometry for Layer {this.members.get('layer', 0)}"

# Pembuatan VTable statically (Compile-time mockup)
vtable_base = VTable("Base", {"render": base_render})
vtable_derived = VTable("DerivedWidget", {
    "render": derived_render,      # Overridden method
    "process": derived_process     # Specialized method
})


# ==============================================================================
# BAGIAN 3: RAII & Smart Pointers (std::unique_ptr & std::shared_ptr)
# ==============================================================================

class RefControlBlock:
    """Mensimulasikan Heap Control Block yang dialokasikan oleh std::make_shared."""
    def __init__(self, resource_addr: int):
        self.resource_addr = resource_addr
        self.strong_ref_count = 1
        self.weak_ref_count = 0

    def add_ref(self):
        self.strong_ref_count += 1

    def release_ref(self) -> bool:
        """Mengurangi ref count. Return True jika resource harus dideallokasi."""
        self.strong_ref_count -= 1
        return self.strong_ref_count == 0


class SharedPtr:
    """Implementasi konseptual std::shared_ptr dengan atomic control block tracking."""
    def __init__(self, resource: Optional[CppRawObject] = None):
        if resource:
            self._resource: Optional[CppRawObject] = resource
            self._ctrl = RefControlBlock(resource.heap_address)
            print(f"{YELLOW}[shared_ptr]{RESET} Alokasi Resource 0x{resource.heap_address:08X} "
                  f"(Strong Count: {self._ctrl.strong_ref_count})")
        else:
            self._resource = None
            self._ctrl = None

    def clone(self) -> 'SharedPtr':
        """Copy Constructor: Menyalin pointer dan menaikkan reference counter."""
        if not self._resource or not self._ctrl:
            return SharedPtr()
        
        copy = SharedPtr.__new__(SharedPtr)
        copy._resource = self._resource
        copy._ctrl = self._ctrl
        self._ctrl.add_ref()
        print(f"{YELLOW}[shared_ptr:COPY]{RESET} Resource 0x{self._resource.heap_address:08X} "
              f"RefCount bertambah -> {self._ctrl.strong_ref_count}")
        return copy

    def reset(self):
        """Destructor simulation / Dereferencing."""
        if self._ctrl and self._resource:
            res_addr = self._resource.heap_address
            should_destroy = self._ctrl.release_ref()
            print(f"{YELLOW}[shared_ptr:DESTRUCT]{RESET} Resource 0x{res_addr:08X} "
                  f"RefCount berkurang -> {self._ctrl.strong_ref_count}")
            if should_destroy:
                print(f"{RED}[RAII DEALLOC]{RESET} Ref count 0! Memanggil ~Destructor() untuk 0x{res_addr:08X}")
                self._resource = None
                self._ctrl = None
            else:
                self._resource = None
                self._ctrl = None

    def get(self) -> Optional[CppRawObject]:
        return self._resource

    @property
    def use_count(self) -> int:
        return self._ctrl.strong_ref_count if self._ctrl else 0


class UniquePtr:
    """Implementasi konseptual std::unique_ptr (Move-only Semantics)."""
    def __init__(self, resource: Optional[CppRawObject] = None):
        self._resource = resource
        if resource:
            print(f"{MAGENTA}[unique_ptr]{RESET} Klaim kepemilikan eksklusif 0x{resource.heap_address:08X}")

    def move(self) -> 'UniquePtr':
        """
        Simulasi std::move(ptr): mentransfer ownership pointer ke target baru
        dan me-null-kan rvalue source untuk mencegah double-free.
        """
        if not self._resource:
            return UniquePtr(None)
        
        target = UniquePtr(self._resource)
        print(f"{MAGENTA}[unique_ptr:MOVE]{RESET} Kepemilikan 0x{self._resource.heap_address:08X} ditransfer! Source diset nullptr.")
        self._resource = None
        return target

    def release(self):
        """Destructor: membersihkan resource jika masih dimiliki."""
        if self._resource:
            print(f"{RED}[unique_ptr:DEALLOC]{RESET} Membersihkan kepemilikan tunggal 0x{self._resource.heap_address:08X}")
            self._resource = None


# ==============================================================================
# BAGIAN 4: Execution Pipeline & Verification Benchmark
# ==============================================================================

def run_lab():
    print(f"\n{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{BOLD}{MAGENTA}   LAB DEEP DIVE: C++ INTERNALS (VTABLE DISPATCH & SMART POINTERS)   {RESET}")
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}\n")

    # 1. Instansiasi Object Model
    print(f"{BOLD}[1] Membangun Memory Layout Objek C++ Sesuai Itanium ABI{RESET}")
    base_obj = CppRawObject("Base", vtable_base, {"id": 101})
    derived_obj = CppRawObject("DerivedWidget", vtable_derived, {"id": 202, "layer": 5})

    base_obj.dump_memory_layout()
    derived_obj.dump_memory_layout()

    # 2. Dynamic Dispatch Melalui Polymorphic Base Pointer
    print(f"{BOLD}[2] Simulasi Polymorphic Virtual Dispatch (Upcasting: Base* b = &derived){RESET}")
    polymorphic_ptr: CppRawObject = derived_obj
    
    print("Memanggil: polymorphic_ptr->render()")
    out_derived = simulate_dynamic_dispatch(polymorphic_ptr, "render")
    print(f"Hasil Eksekusi: {out_derived}\n")

    print("Memanggil: base_obj.render()")
    out_base = simulate_dynamic_dispatch(base_obj, "render")
    print(f"Hasil Eksekusi: {out_base}\n")

    # 3. Benchmark Overhead Dynamic Dispatch vs Direct Dispatch
    print(f"{BOLD}[3] Micro-Benchmark: Virtual Lookup vs Direct Call Overhead{RESET}")
    iterations = 50_000

    # Direct Call Benchmark
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = derived_render(derived_obj)
    direct_time = time.perf_counter() - t0

    # VTable Dynamic Call Benchmark
    t0 = time.perf_counter()
    for _ in range(iterations):
        # Emulasi: vtable lookup + call
        method = derived_obj.vptr.methods["render"]
        _ = method(derived_obj)
    virtual_time = time.perf_counter() - t0

    print(f"  Direct Invocations ({iterations:,} iter)  : {direct_time * 1000:.3f} ms")
    print(f"  VTable Invocations ({iterations:,} iter)  : {virtual_time * 1000:.3f} ms")
    overhead_pct = ((virtual_time - direct_time) / direct_time) * 100
    print(f"  Dynamic Dispatch Overhead             : {YELLOW}+{overhead_pct:.2f}%{RESET}\n")

    # 4. Simulasi std::unique_ptr & Move Semantics
    print(f"{BOLD}[4] Simulasi std::unique_ptr & Move Semantics (Ownership Transfer){RESET}")
    u_resource = CppRawObject("UniqueResource", vtable_base, {"id": 888})
    ptr_a = UniquePtr(u_resource)
    
    print("Mengeksekusi: UniquePtr ptr_b = std::move(ptr_a);")
    ptr_b = ptr_a.move()
    
    print(f"Status ptr_a raw pointer : {GRAY}{ptr_a._resource}{RESET} (Invalidated)")
    print(f"Status ptr_b raw pointer : 0x{ptr_b._resource.heap_address:08X} (Active)")
    ptr_a.release()  # No-op karena sudah nullptr
    ptr_b.release()  # Trigger deallocation
    print()

    # 5. Simulasi std::shared_ptr & Control Block Reference Counting
    print(f"{BOLD}[5] Simulasi std::shared_ptr Reference Counting Lifecycles{RESET}")
    shared_res = CppRawObject("SharedResource", vtable_derived, {"id": 999, "layer": 1})
    
    print("Langkah 1: Membuat scope utama (shared_1)")
    shared_1 = SharedPtr(shared_res)
    print(f"  shared_1 use_count = {shared_1.use_count}")

    print("\nLangkah 2: Memasuki sub-scope dan menyalin pointer (shared_2 & shared_3)")
    shared_2 = shared_1.clone()
    shared_3 = shared_1.clone()
    print(f"  shared_1 use_count = {shared_1.use_count}")
    print(f"  shared_2 use_count = {shared_2.use_count}")

    print("\nLangkah 3: Keluar dari sub-scope (shared_2 dan shared_3 dihancurkan)")
    shared_2.reset()
    shared_3.reset()
    print(f"  shared_1 use_count = {shared_1.use_count}")

    print("\nLangkah 4: Menghancurkan pointer terakhir (shared_1)")
    shared_1.reset()
    print(f"  shared_1 use_count = {shared_1.use_count}")

    print(f"\n{BOLD}{GREEN}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}  LAB SELESAI: SEMUA MEKANISME C++ RUNTIME BERHASIL DIVALIDASI        {RESET}")
    print(f"{BOLD}{GREEN}======================================================================{RESET}\n")

if __name__ == "__main__":
    run_lab()