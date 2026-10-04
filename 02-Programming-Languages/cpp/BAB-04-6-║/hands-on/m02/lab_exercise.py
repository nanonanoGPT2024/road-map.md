#!/usr/bin/env python3
"""
Lab Hands-on: C++ Deep Dive - Runtime Semantics & Memory Internals Simulator
Bab 04 / Modul 02: Modern C++ Object Model, VTable Dispatch, and Smart Pointer Runtime

Simulasi ini memodelkan tiga pilar fundamental dari runtime C++ modern:
1. Struct Memory Layout & Padding/Alignment (Aturan ABI & optimalisasi cache line).
2. Dynamic Dispatch via Virtual Table (VTable & _vptr resolution).
3. RAII Control Block Semantics (std::shared_ptr & std::weak_ptr lifecycle).
"""

import sys
import time
from typing import Dict, List, Optional, Tuple, Any

# --- ANSI Terminal Styling ---
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_DARK = "\033[48;5;236m"

# ==============================================================================
# 1. C++ MEMORY LAYOUT & STRUCT ALIGNMENT SIMULATOR
# ==============================================================================
CPP_TYPE_SIZES = {
    "bool": (1, 1),
    "char": (1, 1),
    "short": (2, 2),
    "int": (4, 4),
    "float": (4, 4),
    "double": (8, 8),
    "int64_t": (8, 8),
    "pointer": (8, 8),  # 64-bit architecture
}

class StructLayoutAnalyzer:
    """
    Mensimulasikan bagaimana compiler C++ (Clang/GCC System V ABI)
    menata field struct di memori, menyisipkan padding, dan menghitung sizeof/alignof.
    """
    def __init__(self, struct_name: str, members: List[Tuple[str, str]]):
        self.struct_name = struct_name
        self.members = members  # List of (member_name, type_name)

    def analyze(self) -> Dict[str, Any]:
        offset = 0
        max_align = 1
        layout = []

        for name, type_name in self.members:
            size, align = CPP_TYPE_SIZES[type_name]
            max_align = max(max_align, align)

            # Hitung padding yang dibutuhkan untuk memenuhi memory alignment
            padding = (align - (offset % align)) % align
            if padding > 0:
                layout.append(("__padding__", padding, offset, True))
                offset += padding

            layout.append((name, size, offset, False))
            offset += size

        # Padding akhir agar total sizeof merupakan kelipatan dari max_align struct
        tail_padding = (max_align - (offset % max_align)) % max_align
        if tail_padding > 0:
            layout.append(("__tail_padding__", tail_padding, offset, True))
            offset += tail_padding

        return {
            "total_size": offset,
            "struct_alignment": max_align,
            "layout": layout
        }

    def optimize_layout(self) -> List[Tuple[str, str]]:
        """Menerapkan reordering field berdasarkan alignment descending untuk meminimalkan padding."""
        return sorted(self.members, key=lambda m: CPP_TYPE_SIZES[m[1]][1], reverse=True)


# ==============================================================================
# 2. VIRTUAL TABLE (VTABLE) & DYNAMIC DISPATCH ENGINE
# ==============================================================================
class VirtualMethodTable:
    """Representasi tabel vtable internal yang dihasilkan compiler untuk polimorfisme."""
    def __init__(self, class_name: str):
        self.class_name = class_name
        self.slots: Dict[str, Tuple[str, Any]] = {}  # slot_name -> (origin_class, function_ref)

    def register_method(self, slot_name: str, origin_class: str, func):
        self.slots[slot_name] = (origin_class, func)


class CppClassMetadata:
    """Metadata kelas C++ yang memiliki _vptr."""
    def __init__(self, name: str, base: Optional['CppClassMetadata'] = None):
        self.name = name
        self.base = base
        self.vtable = VirtualMethodTable(name)
        if base:
            # Mewarisi semua slot vtable dari base class (Salin vtable)
            self.vtable.slots = dict(base.vtable.slots)

    def add_virtual_method(self, name: str, func):
        self.vtable.register_method(name, self.name, func)

    def override_virtual_method(self, name: str, func):
        if name not in self.vtable.slots:
            raise RuntimeError(f"Semantic Error: Function '{name}' tidak ada di base class untuk di-override!")
        self.vtable.register_method(name, self.name, func)


class CppPolymorphicObject:
    """Instansi objek C++ di heap/stack yang membawa '_vptr' tersembunyi pada byte offset 0."""
    def __init__(self, metadata: CppClassMetadata, state: Dict[str, Any]):
        self._vptr = metadata.vtable
        self.state = state
        self.type_name = metadata.name

    def vcall(self, method_name: str, *args, **kwargs):
        """Resolusi panggilan virtual via dereferensi _vptr."""
        if method_name not in self._vptr.slots:
            raise AttributeError(f"Segmentation Fault: Method '{method_name}' tidak ditemukan di VTable!")
        
        origin_class, method = self._vptr.slots[method_name]
        return method(self, *args, **kwargs), origin_class


# ==============================================================================
# 3. SMART POINTER RUNTIME & RAII CONTROL BLOCK (std::shared_ptr & std::weak_ptr)
# ==============================================================================
class ControlBlock:
    """
    Control block heap-allocated yang dikelola bersama oleh std::shared_ptr dan std::weak_ptr.
    Berisi Strong Ref Count, Weak Ref Count, dan deleter.
    """
    def __init__(self, raw_resource: Any):
        self.raw_resource = raw_resource
        self.strong_count = 1
        self.weak_count = 0
        self.is_managed_object_alive = True

    def dispose_resource(self):
        """Destructor resource yang dipanggil ketika strong count mencapai nol."""
        if self.is_managed_object_alive:
            self.is_managed_object_alive = False
            freed = self.raw_resource
            self.raw_resource = None
            return freed
        return None


class SharedPtr:
    """Model C++ std::shared_ptr dengan copy/move semantics dan ref-counting."""
    def __init__(self, resource: Optional[Any] = None, _ctrl: Optional[ControlBlock] = None):
        if _ctrl is not None:
            self._cb = _ctrl
            self._cb.strong_count += 1
        elif resource is not None:
            self._cb = ControlBlock(resource)
        else:
            self._cb = None

    def use_count(self) -> int:
        return self._cb.strong_count if self._cb else 0

    def get(self) -> Optional[Any]:
        return self._cb.raw_resource if (self._cb and self._cb.is_managed_object_alive) else None

    def clone(self) -> 'SharedPtr':
        """Copy Constructor C++: shared_ptr(const shared_ptr& other)"""
        if not self._cb:
            return SharedPtr()
        return SharedPtr(_ctrl=self._cb)

    def release(self) -> Optional[str]:
        """Destructor RAII C++: ~shared_ptr()"""
        if not self._cb:
            return None
        self._cb.strong_count -= 1
        msg = f"Strong count decremented to {self._cb.strong_count}."
        if self._cb.strong_count == 0:
            freed = self._cb.dispose_resource()
            msg += f" -> [RAII DESTRUCTOR TRIGGERED] Resource '{freed}' dimusnahkan dari Heap!"
            if self._cb.weak_count == 0:
                self._cb = None
                msg += " Control block dibebaskan sepenuhnya."
        return msg


class WeakPtr:
    """Model C++ std::weak_ptr untuk memecahkan circular reference tanpa menambah strong count."""
    def __init__(self, shared: SharedPtr):
        self._cb = shared._cb
        if self._cb:
            self._cb.weak_count += 1

    def expired(self) -> bool:
        return self._cb is None or self._cb.strong_count == 0

    def lock(self) -> Optional[SharedPtr]:
        """Operasi atomik C++ weak_ptr::lock() menghasilkan shared_ptr jika belum expired."""
        if self.expired() or not self._cb:
            return None
        return SharedPtr(_ctrl=self._cb)

    def release(self):
        """Destructor RAII C++: ~weak_ptr()"""
        if self._cb:
            self._cb.weak_count -= 1
            if self._cb.strong_count == 0 and self._cb.weak_count == 0:
                self._cb = None


# ==============================================================================
# LAB TESTBENCH EXECUTION
# ==============================================================================
def display_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{YELLOW}>> {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}")


def run_struct_layout_demo():
    display_header("1. C++ MEMORY LAYOUT & STRUCTURE PADDING (ABI SIMULATION)")
    
    unoptimized_members = [
        ("flag_a", "bool"),        # 1 byte
        ("counter", "int64_t"),     # 8 bytes
        ("tag", "char"),            # 1 byte
        ("value", "int"),           # 4 bytes
        ("buffer_ptr", "pointer")   # 8 bytes
    ]

    analyzer = StructLayoutAnalyzer("TelemetryPacket", unoptimized_members)
    raw_res = analyzer.analyze()

    print(f"{BOLD}Analisis Struct Asli: struct {analyzer.struct_name}{RESET}")
    print(f"Alignof: {raw_res['struct_alignment']} bytes | Total Sizeof: {raw_res['total_size']} bytes\n")
    print(f"{'Offset':<8} {'Field Name':<20} {'Size':<8} {'Type/Note'}")
    print("-" * 55)
    for name, size, offset, is_pad in raw_res["layout"]:
        if is_pad:
            print(f"{RED}[0x{offset:02X}]   {name:<20} {size} byte(s) [UNINTENDED PADDING WASTED]{RESET}")
        else:
            print(f"{GREEN}[0x{offset:02X}]   {name:<20} {size} byte(s) Data field{RESET}")

    # Optimalisasi order
    opt_members = analyzer.optimize_layout()
    opt_analyzer = StructLayoutAnalyzer("TelemetryPacket_Optimized", opt_members)
    opt_res = opt_analyzer.analyze()

    savings = raw_res['total_size'] - opt_res['total_size']
    print(f"\n{BOLD}{MAGENTA}[OPTIMASI COMPILER/ENGINEER]{RESET}")
    print(f"Urutan field diatur ulang descending berdasarkan batasan alignment.")
    print(f"Ukuran baru: {BOLD}{opt_res['total_size']} bytes{RESET} (Penghematan: {GREEN}{savings} bytes / {savings/raw_res['total_size']*100:.1f}%{RESET})")


def run_vtable_dispatch_demo():
    display_header("2. C++ VTABLE INTERNALS & DYNAMIC DISPATCH SIMULATION")

    # Base Class: Entity
    base_class = CppClassMetadata("Entity")
    def entity_render(self): return f"Entity::render() pada ID {self.state.get('id')}"
    def entity_serialize(self): return f"Entity::serialize() hash={hash(self.state.get('id'))}"
    base_class.add_virtual_method("render", entity_render)
    base_class.add_virtual_method("serialize", entity_serialize)

    # Derived Class: Player (Overrides render, keeps base serialize)
    derived_class = CppClassMetadata("Player", base=base_class)
    def player_render(self): return f"Player::render() [Sprite: {self.state.get('skin')}, HP: {self.state.get('hp')}]"
    derived_class.override_virtual_method("render", player_render)

    # Derived Subclass: NetworkPlayer (Overrides serialize)
    net_derived_class = CppClassMetadata("NetworkPlayer", base=derived_class)
    def net_serialize(self): return f"NetworkPlayer::serialize() [Packet ID: {self.state.get('id')}, Ping: 12ms]"
    net_derived_class.override_virtual_method("serialize", net_serialize)

    objects: List[CppPolymorphicObject] = [
        CppPolymorphicObject(base_class, {"id": 100}),
        CppPolymorphicObject(derived_class, {"id": 101, "skin": "Warrior", "hp": 95}),
        CppPolymorphicObject(net_derived_class, {"id": 102, "skin": "Mage", "hp": 40})
    ]

    print(f"{'Obj Instance Type':<18} | {'Dispatch Method':<12} | {'Origin Class Slot':<18} | {'Resolved Execution'}")
    print("-" * 80)
    for obj in objects:
        for call in ["render", "serialize"]:
            res, origin = obj.vcall(call)
            print(f"{BLUE}{obj.type_name:<18}{RESET} | {YELLOW}{call:<12}{RESET} | {MAGENTA}{origin:<18}{RESET} | {res}")


def run_smart_pointers_demo():
    display_header("3. C++ RAII CONTROL BLOCK (std::shared_ptr & std::weak_ptr)")

    print(f"{BOLD}[LANGKAH 1] Alokasi Baru: auto sp1 = std::make_shared<Texture>('hero.png'){RESET}")
    sp1 = SharedPtr("Texture::hero.png")
    print(f"sp1 resource: {sp1.get()} | use_count: {sp1.use_count()}")

    print(f"\n{BOLD}[LANGKAH 2] Copy Semantics: auto sp2 = sp1; auto sp3 = sp1{RESET}")
    sp2 = sp1.clone()
    sp3 = sp1.clone()
    print(f"use_count setelah 2 copy dibuat: {sp1.use_count()}")

    print(f"\n{BOLD}[LANGKAH 3] Weak Pointer Observasi: std::weak_ptr wp(sp1){RESET}")
    wp = WeakPtr(sp1)
    print(f"wp.expired(): {wp.expired()} | Strong use_count: {sp1.use_count()} | ControlBlock.weak_count: {wp._cb.weak_count}")

    print(f"\n{BOLD}[LANGKAH 4] Pelepasan Scope (sp2 dan sp3 destroyed){RESET}")
    print("Release sp2 ->", sp2.release())
    print("Release sp3 ->", sp3.release())
    print(f"Sisa use_count: {sp1.use_count()}")

    print(f"\n{BOLD}[LANGKAH 5] weak_ptr::lock() sukses saat resource aktif{RESET}")
    locked_sp = wp.lock()
    if locked_sp:
        print(f"Lock Berhasil! Resource diakses: {locked_sp.get()} | Temp use_count: {locked_sp.use_count()}")
        locked_sp.release()

    print(f"\n{BOLD}[LANGKAH 6] Pelepasan Pointer Pemilik Terakhir: sp1.reset(){RESET}")
    destruction_log = sp1.release()
    print(destruction_log)

    print(f"\n{BOLD}[LANGKAH 7] Verifikasi Dangling Access via Weak Pointer{RESET}")
    print(f"wp.expired() pasca pemusnahan shared_ptr: {wp.expired()}")
    failed_lock = wp.lock()
    if failed_lock is None:
        print(f"{GREEN}Aman: wp.lock() mengembalikan nullptr. Menghindari Use-After-Free (UAF)!{RESET}")
    
    wp.release()


def main():
    start_time = time.time()
    print(f"{BOLD}{BG_DARK}=== C++ DEEP DIVE LAB: RUNTIME SEMANTICS SIMULATION ==={RESET}")
    print("Menjalankan verifikasi internal ABI, Dynamic Dispatch, dan Lifecycle RAII...")

    run_struct_layout_demo()
    run_vtable_dispatch_demo()
    run_smart_pointers_demo()

    elapsed = (time.time() - start_time) * 1000
    print(f"\n{BOLD}{GREEN}[LAB STATUS: OK]{RESET} Simulasi selesai secara deterministik dalam {elapsed:.2f} ms.")

if __name__ == "__main__":
    main()