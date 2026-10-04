#!/usr/bin/env python3
"""
Lab Hands-on: C++ Deep Dive - Memory Model, RAII, Smart Pointers & Virtual Dispatch
Bab 05: Modul 02 Deep Dive (C++ Internals Simulation)

Simulasi ini merekonstruksi mekanisme inti C++ pada level arsitektur:
1. Deterministic Destructor & RAII (Resource Acquisition Is Initialization).
2. Move Semantics (rvalue reference transfer & moved-from state).
3. std::unique_ptr, std::shared_ptr, and std::weak_ptr (Control Block mechanics).
4. Manual Virtual Method Table (vtable & vptr dynamic dispatch).
5. Heap Memory Allocation Tracking & Leak Detection.
"""

import sys
import time
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_MAGENTA = "\033[95m"

T = TypeVar("T")


class MemoryArena:
    """
    Simulasi Heap Memory Allocator C++.
    Melacak blok memori aktif dan mendeteksi memory leak.
    """
    allocated_bytes: int = 0
    active_objects: int = 0
    allocations: Dict[int, str] = {}

    @classmethod
    def allocate(cls, obj_id: int, size: int, desc: str) -> None:
        cls.allocated_bytes += size
        cls.active_objects += 1
        cls.allocations[obj_id] = f"{desc} ({size} bytes)"

    @classmethod
    def deallocate(cls, obj_id: int, size: int) -> None:
        if obj_id in cls.allocations:
            del cls.allocations[obj_id]
            cls.allocated_bytes -= size
            cls.active_objects -= 1

    @classmethod
    def report(cls) -> None:
        print(f"\n{CLR_BOLD}[HEAP MEMORY ARENA REPORT]{CLR_RESET}")
        print(f"Active Objects : {cls.active_objects}")
        print(f"Allocated Heap : {cls.allocated_bytes} bytes")
        if cls.allocations:
            print(f"{CLR_RED}Memory Leak Detected!{CLR_RESET}")
            for k, v in cls.allocations.items():
                print(f" - Addr 0x{k:08X}: {v}")
        else:
            print(f"{CLR_GREEN}Memory Clean: Zero memory leaks.{CLR_RESET}")


class NativeResource:
    """
    Representasi objek C++ kompleks di heap dengan simulasi konstruktor/destruktor.
    """
    def __init__(self, name: str, payload_size: int = 64):
        self.name = name
        self.payload_size = payload_size
        self.addr = id(self)
        self.alive = True
        MemoryArena.allocate(self.addr, self.payload_size, f"Resource::{self.name}")
        print(f"  {CLR_GREEN}[+] Resource ctor:{CLR_RESET} '{self.name}' @ 0x{self.addr:08X} ({self.payload_size} bytes)")

    def perform_work(self) -> None:
        if not self.alive:
            raise RuntimeError(f"Use-after-free error on 0x{self.addr:08X}!")
        print(f"  {CLR_CYAN}[*] Resource execute:{CLR_RESET} '{self.name}' [0x{self.addr:08X}]")

    def __del__(self):
        """Destruktor deterministic C++ saat ref-count mencapai nol."""
        if self.alive:
            self.alive = False
            MemoryArena.deallocate(self.addr, self.payload_size)
            print(f"  {CLR_RED}[-] Resource dtor:{CLR_RESET} '{self.name}' @ 0x{self.addr:08X}")


class UniquePtr(Generic[T]):
    """
    Simulasi std::unique_ptr<T>.
    Memiliki kepemilikan eksklusif atas resource.
    Dilarang copy, hanya mengizinkan move semantics.
    """
    def __init__(self, resource: Optional[T] = None):
        self._ptr: Optional[T] = resource

    def release(self) -> Optional[T]:
        res = self._ptr
        self._ptr = None
        return res

    def reset(self, new_resource: Optional[T] = None) -> None:
        if self._ptr is not None:
            # Deterministic destruction
            del self._ptr
        self._ptr = new_resource

    def move(self) -> "UniquePtr[T]":
        """Simulasi std::move(unique_ptr) - mentransfer ownership, mengosongkan donor."""
        new_holder = UniquePtr[T](self._ptr)
        self._ptr = None  # Moved-from state: pointer menjadi nullptr
        return new_holder

    @property
    def get(self) -> Optional[T]:
        return self._ptr

    def is_valid(self) -> bool:
        return self._ptr is not None

    def __del__(self):
        self.reset()


class ControlBlock(Generic[T]):
    """
    Control Block untuk std::shared_ptr dan std::weak_ptr.
    Menyimpan resource pointer, strong ref count, dan weak ref count.
    """
    def __init__(self, resource: T):
        self.ptr: Optional[T] = resource
        self.strong_count: int = 1
        self.weak_count: int = 0

    def add_strong(self) -> None:
        self.strong_count += 1

    def release_strong(self) -> None:
        self.strong_count -= 1
        if self.strong_count == 0:
            # Hancurkan resource C++, tetapi blok kontrol tetap ada jika weak_count > 0
            del self.ptr
            self.ptr = None
            print(f"    {CLR_YELLOW}[ControlBlock]{CLR_RESET} Strong count = 0. Resource deallocated.")
        if self.strong_count == 0 and self.weak_count == 0:
            print(f"    {CLR_YELLOW}[ControlBlock]{CLR_RESET} Strong & Weak count = 0. Control block freed.")

    def add_weak(self) -> None:
        self.weak_count += 1

    def release_weak(self) -> None:
        self.weak_count -= 1
        if self.strong_count == 0 and self.weak_count == 0:
            print(f"    {CLR_YELLOW}[ControlBlock]{CLR_RESET} Weak count = 0. Control block freed.")


class SharedPtr(Generic[T]):
    """Simulasi std::shared_ptr<T>."""
    def __init__(self, resource: Optional[T] = None, _ctrl: Optional[ControlBlock[T]] = None):
        if _ctrl is not None:
            self._ctrl: Optional[ControlBlock[T]] = _ctrl
            self._ctrl.add_strong()
        elif resource is not None:
            self._ctrl = ControlBlock[T](resource)
        else:
            self._ctrl = None

    def copy(self) -> "SharedPtr[T]":
        """Copy constructor: menaikkan strong ref-count."""
        if self._ctrl:
            return SharedPtr[T](_ctrl=self._ctrl)
        return SharedPtr[T]()

    def use_count(self) -> int:
        return self._ctrl.strong_count if self._ctrl else 0

    def get(self) -> Optional[T]:
        return self._ctrl.ptr if self._ctrl else None

    def reset(self) -> None:
        if self._ctrl:
            self._ctrl.release_strong()
            self._ctrl = None

    def __del__(self):
        self.reset()


class WeakPtr(Generic[T]):
    """Simulasi std::weak_ptr<T> untuk memutus circular references."""
    def __init__(self, shared: SharedPtr[T]):
        self._ctrl: Optional[ControlBlock[T]] = shared._ctrl
        if self._ctrl:
            self._ctrl.add_weak()

    def expired(self) -> bool:
        return self._ctrl is None or self._ctrl.strong_count == 0

    def lock(self) -> SharedPtr[T]:
        """Promosikan ke SharedPtr jika resource masih hidup."""
        if not self.expired() and self._ctrl is not None:
            return SharedPtr[T](_ctrl=self._ctrl)
        return SharedPtr[T]()

    def reset(self) -> None:
        if self._ctrl:
            self._ctrl.release_weak()
            self._ctrl = None

    def __del__(self):
        self.reset()


class VTable:
    """Simulasi C++ Virtual Method Table (vtable) per kelas."""
    def __init__(self, class_name: str, methods: Dict[str, Callable]):
        self.class_name = class_name
        self.methods = methods

    def dispatch(self, instance: Any, method_name: str, *args, **kwargs):
        if method_name not in self.methods:
            raise AttributeError(f"Pure virtual call or method '{method_name}' not implemented in vtable.")
        return self.methods[method_name](instance, *args, **kwargs)


def base_render(self) -> str:
    return f"[Base::render() -> Generic Wireframe of {self.name}]"


def base_serialize(self) -> str:
    return f"[Base::serialize() -> Standard Binary Payload]"


def derived_render(self) -> str:
    return f"[Derived::render() -> High-Detail Shaded Mesh of {self.name} (Overridden!)]"


# Static vtables created once per class hierarchy
BASE_VTABLE = VTable("BaseEntity", {"render": base_render, "serialize": base_serialize})
DERIVED_VTABLE = VTable("DerivedMesh", {"render": derived_render, "serialize": base_serialize})


class BaseEntity:
    """Simulasi C++ Base Class dengan vptr (pointer to vtable)."""
    def __init__(self, name: str):
        self.name = name
        self.vptr: VTable = BASE_VTABLE

    def call_virtual(self, method_name: str):
        # Indirection melalui vtable
        return self.vptr.dispatch(self, method_name)


class DerivedMesh(BaseEntity):
    """Simulasi C++ Derived Class yang meng-override vptr."""
    def __init__(self, name: str):
        super().__init__(name)
        self.vptr = DERIVED_VTABLE  # Override vptr menunjuk ke derived vtable


def run_lab_demonstrations():
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}    C++ DEEP DIVE: MEMORY, RAII, SMART POINTERS & VTABLE DISPATCH    {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")

    # ---------------------------------------------------------
    # SKENARIO 1: RAII & Move Semantics (std::unique_ptr)
    # ---------------------------------------------------------
    print(f"\n{CLR_BOLD}[1] SIMULASI: std::unique_ptr & Move Semantics (Ownership Transfer){CLR_RESET}")
    
    # Inisialisasi unique_ptr
    uptr1 = UniquePtr[NativeResource](NativeResource("GpuShaderBuffer", 128))
    if uptr1.is_valid():
        uptr1.get.perform_work()

    print(f"  Transfer ownership via {CLR_YELLOW}std::move(uptr1) -> uptr2{CLR_RESET}...")
    uptr2 = uptr1.move()

    print(f"  Validasi state:")
    print(f"   - uptr1 valid? {CLR_RED if not uptr1.is_valid() else CLR_GREEN}{uptr1.is_valid()}{CLR_RESET} (nullptr / moved-from)")
    print(f"   - uptr2 valid? {CLR_GREEN if uptr2.is_valid() else CLR_RED}{uptr2.is_valid()}{CLR_RESET} (owner)")
    uptr2.get.perform_work()

    print(f"  Scope exit untuk uptr2 (RAII explicit reset):")
    uptr2.reset()

    # ---------------------------------------------------------
    # SKENARIO 2: Shared & Weak Pointer Control Block
    # ---------------------------------------------------------
    print(f"\n{CLR_BOLD}[2] SIMULASI: std::shared_ptr, std::weak_ptr & Ref-Count Mechanics{CLR_RESET}")
    
    sp1 = SharedPtr[NativeResource](NativeResource("PhysicsWorld", 256))
    print(f"  sp1 created. Strong Count = {sp1.use_count()}")

    sp2 = sp1.copy()
    print(f"  sp2 copy-constructed from sp1. Strong Count = {sp1.use_count()}")

    # Buat Weak Pointer
    wp = WeakPtr[NativeResource](sp1)
    print(f"  wp (WeakPtr) created. Strong Count = {sp1.use_count()}, Weak Expired? {wp.expired()}")

    print("  Destroying sp1...")
    sp1.reset()
    print(f"  sp1 reset. sp2 Strong Count = {sp2.use_count()}")

    # Lock weak pointer
    print("  Locking weak pointer to obtain temporary shared_ptr (locked_sp)...")
    locked_sp = wp.lock()
    print(f"  locked_sp acquired! Strong Count = {locked_sp.use_count()}")
    locked_sp.get.perform_work()

    print("  Destroying sp2 & locked_sp...")
    sp2.reset()
    locked_sp.reset()

    print(f"  Checking weak pointer again. Expired? {CLR_RED if wp.expired() else CLR_GREEN}{wp.expired()}{CLR_RESET}")
    dead_lock = wp.lock()
    print(f"  Attempt lock on expired weak_ptr: {dead_lock.get} (nullptr)")
    wp.reset()

    # ---------------------------------------------------------
    # SKENARIO 3: Virtual Dispatch Melalui VTable & VPtr
    # ---------------------------------------------------------
    print(f"\n{CLR_BOLD}[3] SIMULASI: Polymorphism & C++ Virtual Method Table (vtable/vptr){CLR_RESET}")
    entities: list[BaseEntity] = [
        BaseEntity("Procedural_Terrain"),
        DerivedMesh("LOD_Dragon_Model")
    ]

    for ent in entities:
        print(f"  Object: {CLR_CYAN}{ent.name}{CLR_RESET} | Class: {ent.vptr.class_name} | vptr: 0x{id(ent.vptr):08X}")
        render_res = ent.call_virtual("render")
        serialize_res = ent.call_virtual("serialize")
        print(f"    vtable->render()    : {render_res}")
        print(f"    vtable->serialize() : {serialize_res}")

    # ---------------------------------------------------------
    # FINAL RECOVERY & HEAP AUDIT
    # ---------------------------------------------------------
    MemoryArena.report()
    print(f"{CLR_BOLD}{CLR_GREEN}Simulation completed successfully.{CLR_RESET}\n")


if __name__ == "__main__":
    run_lab_demonstrations()
    sys.exit(0)