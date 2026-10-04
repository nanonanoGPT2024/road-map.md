#!/usr/bin/env python3
"""
Lab Hands-on: C++ Runtime Internals & Object Model Simulation
Bab 10 - Modul 02 Deep Dive: VTable Dispatch, Object Memory Layout & RAII Smart Pointers

Deskripsi:
Script ini mensimulasikan mekanisme runtime C++ tingkat rendah (low-level):
1. Virtual Method Table (VTable) resolution dan Dynamic Dispatch (Polimorfisme Runtime).
2. Memory layout inspeksi: _vptr, member field offsets, dan padding alignment.
3. RAII & std::shared_ptr control block (strong/weak reference counting, custom deleter).
4. Micro-benchmark overhead perbandingan antara Direct Call vs VTable Dynamic Dispatch.
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


class TypeInfo:
    """Mensimulasikan RTTI (Run-Time Type Information) std::type_info di C++."""
    def __init__(self, type_name: str, size: int, align: int):
        self.type_name = type_name
        self.size = size
        self.alignment = align

    def __repr__(self) -> str:
        return f"type_info({self.type_name}, sizeof={self.size}, align={self.alignment})"


class VTable:
    """
    Mensimulasikan struktur Virtual Table (vtable) compiler C++.
    Berisi pointer ke RTTI dan array pointer fungsi virtual.
    """
    def __init__(self, class_name: str, type_info: TypeInfo):
        self.class_name = class_name
        self.type_info = type_info
        self.slots: Dict[str, Callable[..., Any]] = {}

    def bind_slot(self, method_name: str, func_ptr: Callable[..., Any]) -> None:
        self.slots[method_name] = func_ptr

    def get_slot(self, method_name: str) -> Callable[..., Any]:
        if method_name not in self.slots:
            raise AttributeError(f"Pure virtual function call or unresolved slot: {method_name}")
        return self.slots[method_name]


class CppObjectMemoryLayout:
    """
    Mensimulasikan tata letak memori objek C++ (Object Layout):
    Slot 0: _vptr (8-byte pointer ke VTable jika polimorfik)
    Slot N: Member variables dengan padding alignment.
    """
    def __init__(self, vtable: Optional[VTable], fields: Dict[str, tuple]):
        self._vptr = vtable
        self.fields = fields  # name -> (offset, size, value)
        self.simulated_address = hex(id(self))

    def dump_memory_layout(self) -> None:
        print(f"{Colors.CYAN}--- Memory Layout: {self._vptr.class_name if self._vptr else 'POD'} at {self.simulated_address} ---{Colors.RESET}")
        current_offset = 0
        if self._vptr:
            print(f"  [+0x{current_offset:02X}] _vptr -> {Colors.MAGENTA}&{self._vptr.class_name}::__vtable{Colors.RESET} (8 bytes)")
            current_offset += 8

        for name, (offset, size, val) in self.fields.items():
            padding = offset - current_offset
            if padding > 0:
                print(f"  [+0x{current_offset:02X}] {Colors.GRAY}<padding {padding} bytes>{Colors.RESET}")
                current_offset += padding
            print(f"  [+0x{offset:02X}] {name:<12} : {str(val):<15} ({size} bytes)")
            current_offset += size


class ControlBlock:
    """
    Mensimulasikan Control Block heap untuk std::shared_ptr:
    - strong_ref_count
    - weak_ref_count
    - custom deleter
    """
    def __init__(self, raw_ptr: Any, deleter: Optional[Callable[[Any], None]] = None):
        self.raw_ptr = raw_ptr
        self.strong_count = 1
        self.weak_count = 0
        self.deleter = deleter or (lambda p: print(f"{Colors.RED}[Deleter] Object at {hex(id(p))} free()'d.{Colors.RESET}"))

    def add_ref(self) -> None:
        self.strong_count += 1

    def release_ref(self) -> None:
        self.strong_count -= 1
        if self.strong_count == 0:
            if self.raw_ptr is not None:
                self.deleter(self.raw_ptr)
                self.raw_ptr = None


class SharedPtr:
    """
    Mensimulasikan semantik C++ std::shared_ptr (RAII, reference counter, copy constructor).
    """
    def __init__(self, raw_ptr: Optional[Any] = None, deleter: Optional[Callable[[Any], None]] = None):
        if raw_ptr is not None:
            self._ctrl = ControlBlock(raw_ptr, deleter)
        else:
            self._ctrl = None

    @classmethod
    def from_existing(cls, other: 'SharedPtr') -> 'SharedPtr':
        """Copy Constructor C++: SharedPtr(const SharedPtr& other)"""
        instance = cls()
        instance._ctrl = other._ctrl
        if instance._ctrl:
            instance._ctrl.add_ref()
        return instance

    def use_count(self) -> int:
        return self._ctrl.strong_count if self._ctrl else 0

    def get(self) -> Any:
        return self._ctrl.raw_ptr if self._ctrl else None

    def reset(self) -> None:
        if self._ctrl:
            self._ctrl.release_ref()
            self._ctrl = None

    def __del__(self) -> None:
        """Destructor RAII"""
        self.reset()


# --- Definisi Hierarki Polimorfik Simulasi (BaseEntity -> Soldier / Mage) ---

# RTTI TypeInfo metadata
TI_ENTITY = TypeInfo("BaseEntity", size=16, align=8)
TI_SOLDIER = TypeInfo("Soldier", size=24, align=8)
TI_MAGE = TypeInfo("Mage", size=32, align=8)

# Konstruksi VTable
vtable_BaseEntity = VTable("BaseEntity", TI_ENTITY)
vtable_Soldier = VTable("Soldier", TI_SOLDIER)
vtable_Mage = VTable("Mage", TI_MAGE)

# Fungsi-fungsi virtual implementations
def BaseEntity_update(instance: Any) -> str:
    return f"[BaseEntity::update] ID: {instance.fields['entity_id'][2]} tick."

def BaseEntity_render(instance: Any) -> str:
    return "[BaseEntity::render] Generic wireframe."

def Soldier_update(instance: Any) -> str:
    hp = instance.fields['hp'][2]
    return f"[Soldier::update] Soldier marching, current HP: {hp}"

def Soldier_render(instance: Any) -> str:
    return "[Soldier::render] Rendering heavy armored mesh."

def Mage_update(instance: Any) -> str:
    mana = instance.fields['mana'][2]
    return f"[Mage::update] Chanting spell with Mana: {mana}"

def Mage_render(instance: Any) -> str:
    return "[Mage::render] Rendering particle magic shield."

# Inisialisasi slot VTable
vtable_BaseEntity.bind_slot("update", BaseEntity_update)
vtable_BaseEntity.bind_slot("render", BaseEntity_render)

vtable_Soldier.bind_slot("update", Soldier_update)
vtable_Soldier.bind_slot("render", Soldier_render)

vtable_Mage.bind_slot("update", Mage_update)
vtable_Mage.bind_slot("render", Mage_render)


def dispatch_virtual(obj: CppObjectMemoryLayout, method_name: str) -> Any:
    """Simulasi Dynamic Dispatch: obj->_vptr->slots[method_name](obj)"""
    if not obj._vptr:
        raise RuntimeError("Non-polymorphic object lacks _vptr!")
    func_ptr = obj._vptr.get_slot(method_name)
    return func_ptr(obj)


def run_benchmark():
    """Membandingkan direct non-virtual dispatch vs virtual table indirection."""
    print(f"\n{Colors.BOLD}{Colors.YELLOW}=== BENCHMARK: Direct Call vs VTable Dynamic Dispatch ==={Colors.RESET}")
    iterations = 500_000

    # Objek target
    soldier_obj = CppObjectMemoryLayout(
        vtable=vtable_Soldier,
        fields={
            "entity_id": (8, 4, 101),
            "hp": (12, 4, 250),
            "armor": (16, 4, 85)
        }
    )

    # 1. Direct Call Benchmark (Devirtualized / Direct function pointer)
    t0 = time.perf_counter()
    direct_func = Soldier_update
    for _ in range(iterations):
        _ = direct_func(soldier_obj)
    t_direct = time.perf_counter() - t0

    # 2. Dynamic Virtual Dispatch Benchmark (_vptr resolution + slot lookup)
    t1 = time.perf_counter()
    for _ in range(iterations):
        _ = dispatch_virtual(soldier_obj, "update")
    t_virtual = time.perf_counter() - t1

    print(f"Iterations             : {iterations:,}")
    print(f"Direct Call Latency    : {Colors.GREEN}{t_direct:.4f}s{Colors.RESET}")
    print(f"Virtual Dispatch Latency: {Colors.RED}{t_virtual:.4f}s{Colors.RESET}")
    ratio = (t_virtual / t_direct) if t_direct > 0 else 1.0
    print(f"Overhead Dynamic Dispatch: {Colors.BOLD}{ratio:.2f}x{Colors.RESET} (Dereference & Lookup)")


def main():
    print(f"{Colors.BOLD}{Colors.CYAN}==============================================================")
    print("   LAB C++ DEEP DIVE: VTABLE, MEMORY LAYOUT & SMART POINTERS  ")
    print(f"=============================================================={Colors.RESET}\n")

    # 1. Memory Layout Inspection
    print(f"{Colors.BOLD}[1] C++ Object Memory Layout & Alignment Alignment Simulation{Colors.RESET}")
    soldier = CppObjectMemoryLayout(
        vtable=vtable_Soldier,
        fields={
            "entity_id": (8, 4, 1001),
            "hp": (12, 4, 100),
            "armor_val": (16, 8, 45.5)  # 64-bit double
        }
    )
    soldier.dump_memory_layout()

    mage = CppObjectMemoryLayout(
        vtable=vtable_Mage,
        fields={
            "entity_id": (8, 4, 2002),
            "mana": (12, 4, 500),
            "staff_ptr": (16, 8, 0x7FFEAA0012)
        }
    )
    print()
    mage.dump_memory_layout()

    # 2. Polymorphic Dynamic Dispatch
    print(f"\n{Colors.BOLD}[2] Runtime Polymorphic Dispatch via Virtual Table (_vptr){Colors.RESET}")
    entity_collection: List[CppObjectMemoryLayout] = [soldier, mage]
    for idx, ent in enumerate(entity_collection):
        res_update = dispatch_virtual(ent, "update")
        res_render = dispatch_virtual(ent, "render")
        print(f"Entity [{idx}] RTTI: {Colors.MAGENTA}{ent._vptr.type_info.type_name}{Colors.RESET}")
        print(f"  -> {res_update}")
        print(f"  -> {res_render}")

    # 3. RAII & Shared Pointer Reference Counting
    print(f"\n{Colors.BOLD}[3] RAII & std::shared_ptr Control Block Lifecycle{Colors.RESET}")
    print(f"{Colors.GRAY}Creating shared_ptr<Soldier> ptr1...{Colors.RESET}")
    ptr1 = SharedPtr(soldier)
    print(f"ptr1 use_count: {Colors.GREEN}{ptr1.use_count()}{Colors.RESET}")

    print(f"{Colors.GRAY}Copy-constructing ptr2 = ptr1...{Colors.RESET}")
    ptr2 = SharedPtr.from_existing(ptr1)
    print(f"ptr1 use_count: {Colors.GREEN}{ptr1.use_count()}{Colors.RESET}, ptr2 use_count: {Colors.GREEN}{ptr2.use_count()}{Colors.RESET}")

    print(f"{Colors.GRAY}Copy-constructing ptr3 = ptr2...{Colors.RESET}")
    ptr3 = SharedPtr.from_existing(ptr2)
    print(f"Strong references active: {Colors.GREEN}{ptr3.use_count()}{Colors.RESET}")

    print(f"{Colors.GRAY}Simulating scope exit for ptr1 and ptr2 (resetting)...{Colors.RESET}")
    ptr1.reset()
    ptr2.reset()
    print(f"After partial release: ptr3 use_count = {Colors.GREEN}{ptr3.use_count()}{Colors.RESET}")

    print(f"{Colors.GRAY}Releasing last reference ptr3.reset()...{Colors.RESET}")
    ptr3.reset()
    print(f"Final ptr3 use_count: {Colors.YELLOW}{ptr3.use_count()}{Colors.RESET}")

    # 4. Micro-benchmark
    run_benchmark()

    print(f"\n{Colors.GREEN}{Colors.BOLD}✔ Lab Hands-on C++ Runtime Internals Selesai dengan Sukses.{Colors.RESET}")


if __name__ == "__main__":
    main()