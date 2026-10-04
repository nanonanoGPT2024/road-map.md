#!/usr/bin/env python3
"""
Lab Hands-on: C++ Runtime Internals Deep Dive (Bab 09 - Modul 02)
Simulasi komprehensif mekanisme internal C++:
  1. Virtual Method Table (vtable & vptr dynamic dispatch)
  2. RAII Reference Counting (std::shared_ptr, std::weak_ptr, dan Control Block)
  3. Move Semantics & Rvalue Reference Ownership Transfer (std::move)
"""

import sys
import time
from typing import Any, Callable, Dict, Optional

# --- ANSI Formatting Helper ---
class Terminal:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"

    @staticmethod
    def header(title: str):
        print(f"\n{Terminal.BOLD}{Terminal.CYAN}{'='*65}")
        print(f" [LAB DEEP DIVE] {title}")
        print(f"{'='*65}{Terminal.RESET}")

    @staticmethod
    def step(name: str):
        print(f"\n{Terminal.BOLD}{Terminal.YELLOW}>> {name}{Terminal.RESET}")

    @staticmethod
    def info(msg: str):
        print(f"  {Terminal.BLUE}[INFO]{Terminal.RESET} {msg}")

    @staticmethod
    def success(msg: str):
        print(f"  {Terminal.GREEN}[OK]{Terminal.RESET} {msg}")

    @staticmethod
    def warn(msg: str):
        print(f"  {Terminal.RED}[DTOR/DEALLOC]{Terminal.RESET} {msg}")


# =====================================================================
# 1. Virtual Method Table (vtable) Simulation
# =====================================================================
class VTable:
    """Representasi tabel fungsi virtual untuk kelas C++."""
    def __init__(self, class_name: str, slots: Dict[str, Callable]):
        self.class_name = class_name
        self.slots = slots

    def dispatch(self, instance: "CppObject", slot_name: str, *args, **kwargs):
        if slot_name not in self.slots:
            raise AttributeError(f"VTable '{self.class_name}' does not implement slot '{slot_name}'")
        return self.slots[slot_name](instance, *args, **kwargs)


class CppObject:
    """Simulasi memory layout objek C++: Offset 0 selalu menyimpan __vptr."""
    def __init__(self, vtable: VTable):
        self.__vptr: VTable = vtable  # Pointer ke Virtual Method Table


# Definisi fungsi bebas yang setara dengan compiled function symbols
def base_render(obj: CppObject):
    return f"BaseEntity::render() [vptr: {id(obj._CppObject__vptr):x}]"

def base_get_id(obj: CppObject):
    return f"BaseEntity::getId() -> 1000"

def player_render(obj: CppObject):
    return f"PlayerEntity::render() [OVERRIDDEN] (Render character mesh & UI)"

def player_special_ability(obj: CppObject):
    return f"PlayerEntity::dash() [Derived Exclusive]"


# Inisialisasi vtable statis (analog dengan static rodata section)
VTABLE_BASE = VTable("BaseEntity", {
    "render": base_render,
    "getId": base_get_id
})

VTABLE_PLAYER = VTable("PlayerEntity", {
    "render": player_render,      # Override slot render
    "getId": base_get_id,         # Inherited slot
    "dash": player_special_ability
})


# =====================================================================
# 2. Memory Management: RAII & Shared Pointer Control Block
# =====================================================================
class ControlBlock:
    """Mengelola reference counting C++: strong count & weak count."""
    def __init__(self, resource: Any, deleter: Optional[Callable[[Any], None]] = None):
        self.resource = resource
        self.strong_count = 1
        self.weak_count = 0
        self.deleter = deleter or self._default_deleter

    def _default_deleter(self, res: Any):
        Terminal.warn(f"Invoking Destructor: Resource <{res}> physically destroyed from heap.")

    def release_strong(self):
        self.strong_count -= 1
        Terminal.info(f"Decrement strong_count: {self.strong_count}")
        if self.strong_count == 0:
            if self.resource is not None:
                self.deleter(self.resource)
                self.resource = None
            if self.weak_count == 0:
                Terminal.warn("Freeing ControlBlock metadata block.")

    def release_weak(self):
        self.weak_count -= 1
        Terminal.info(f"Decrement weak_count: {self.weak_count}")
        if self.weak_count == 0 and self.strong_count == 0:
            Terminal.warn("Freeing ControlBlock metadata block.")


class SharedPtr:
    """Simulasi std::shared_ptr<T> dengan RAII."""
    def __init__(self, resource: Any = None, _ctrl: Optional[ControlBlock] = None):
        if _ctrl is not None:
            self._ctrl = _ctrl
            self._ctrl.strong_count += 1
            Terminal.info(f"SharedPtr copy ctor: increment strong_count: {self._ctrl.strong_count}")
        elif resource is not None:
            self._ctrl = ControlBlock(resource)
            Terminal.info(f"Allocated std::shared_ptr managing resource <{resource}> (strong=1)")
        else:
            self._ctrl = None

    def get(self) -> Optional[Any]:
        return self._ctrl.resource if self._ctrl else None

    def use_count(self) -> int:
        return self._ctrl.strong_count if self._ctrl else 0

    def copy(self) -> "SharedPtr":
        if not self._ctrl:
            return SharedPtr()
        return SharedPtr(_ctrl=self._ctrl)

    def reset(self):
        if self._ctrl:
            ctrl = self._ctrl
            self._ctrl = None
            ctrl.release_strong()

    def __del__(self):
        self.reset()


class WeakPtr:
    """Simulasi std::weak_ptr<T> tanpa memperpanjang ownership."""
    def __init__(self, shared: SharedPtr):
        if shared._ctrl:
            self._ctrl: Optional[ControlBlock] = shared._ctrl
            self._ctrl.weak_count += 1
            Terminal.info(f"WeakPtr created from SharedPtr (weak_count: {self._ctrl.weak_count})")
        else:
            self._ctrl = None

    def expired(self) -> bool:
        return self._ctrl is None or self._ctrl.strong_count == 0

    def lock(self) -> Optional[SharedPtr]:
        """Menghasilkan SharedPtr baru jika resource belum dihancurkan."""
        if not self.expired() and self._ctrl:
            return SharedPtr(_ctrl=self._ctrl)
        Terminal.warn("Failed to lock WeakPtr: Target resource already expired!")
        return None

    def __del__(self):
        if self._ctrl:
            self._ctrl.release_weak()


# =====================================================================
# 3. Move Semantics & Ownership Transfer (std::move Simulation)
# =====================================================================
class DynamicBuffer:
    """Simulasi RAII Buffer C++ (Deep copy vs Zero-cost Move semantics)."""
    def __init__(self, name: str, size_bytes: int):
        self.name = name
        self.size_bytes = size_bytes
        self.data_ptr = list(range(size_bytes))  # Simulasi alokasi heap
        Terminal.info(f"Buffer [{self.name}] allocated: {self.size_bytes} bytes at ptr: {id(self.data_ptr):x}")

    def copy(self) -> "DynamicBuffer":
        """Copy Constructor: Deep copy yang lambat."""
        Terminal.info(f"Copy Constructor: Melakukan deep copy data {self.size_bytes} bytes...")
        cloned = DynamicBuffer(f"{self.name}_copy", 0)
        cloned.size_bytes = self.size_bytes
        cloned.data_ptr = list(self.data_ptr)  # Alokasi buffer baru
        return cloned

    def move_from(self, rvalue: "DynamicBuffer"):
        """Move Constructor: Transfer pointer, set sumber menjadi nullptr."""
        Terminal.info(f"Move Constructor: Menjalankan transfer ownership dari [{rvalue.name}]...")
        self.name = f"{rvalue.name}_moved"
        self.size_bytes = rvalue.size_bytes
        self.data_ptr = rvalue.data_ptr  # Steal internal pointer (zero allocation)

        # Invalidasi state asal (nullptr semantic)
        rvalue.data_ptr = None
        rvalue.size_bytes = 0
        rvalue.name = f"{rvalue.name}_EMPTY"
        Terminal.success("Ownership berhasil dipindahkan tanpa overhead alokasi!")

    def is_valid(self) -> bool:
        return self.data_ptr is not None


def cpp_move(obj: Any) -> Any:
    """Simulasi std::move: static_cast<T&&>(var)."""
    return obj


# =====================================================================
# Main Lab Runner
# =====================================================================
def main():
    Terminal.header("MODUL 02: C++ RUNTIME & SYSTEM SEMANTICS SIMULATOR")

    # --- Skenario 1: Virtual Dispatch & VTable ---
    Terminal.step("Eksperimen 1: VTable Lookup & Virtual Dynamic Dispatch")
    base_inst = CppObject(VTABLE_BASE)
    derived_inst = CppObject(VTABLE_PLAYER)

    Terminal.info("Polymorphic invocation: Calling render() via Base pointer")
    # Base dispatch
    res_base = base_inst._CppObject__vptr.dispatch(base_inst, "render")
    print(f"    Dispatch Result 1: {res_base}")

    # Derived dispatch (Runtime resolution via PlayerEntity vtable)
    res_derived = derived_inst._CppObject__vptr.dispatch(derived_inst, "render")
    print(f"    Dispatch Result 2: {res_derived}")

    # Inherited method lookup
    res_inherited = derived_inst._CppObject__vptr.dispatch(derived_inst, "getId")
    print(f"    Dispatch Result 3 (Inherited): {res_inherited}")
    Terminal.success("Dynamic dispatch vtable selesai dieksekusi secara deterministic.\n")

    # --- Skenario 2: RAII SharedPtr & WeakPtr ---
    Terminal.step("Eksperimen 2: Smart Pointers Lifecycle (std::shared_ptr & std::weak_ptr)")
    sp1 = SharedPtr("GPU_Mesh_Resource_Texture01")
    sp2 = sp1.copy()
    print(f"    Current strong count: {sp1.use_count()}")

    weak_ref = WeakPtr(sp1)
    print(f"    WeakPtr expired status: {weak_ref.expired()}")

    Terminal.info("Menghancurkan referensi sp1...")
    sp1.reset()
    print(f"    Current strong count: {sp2.use_count()}")

    Terminal.info("Mencoba me-lock WeakPtr saat sp2 masih memegang resource:")
    locked_sp = weak_ref.lock()
    if locked_sp:
        Terminal.success(f"Lock sukses! Membaca resource: '{locked_sp.get()}'")
        locked_sp.reset()

    Terminal.info("Menghancurkan sp2 (Strong count menuju 0):")
    sp2.reset()
    print(f"    WeakPtr expired status sekarang: {weak_ref.expired()}")

    Terminal.info("Mencoba me-lock WeakPtr setelah resource hancur:")
    dangling_access = weak_ref.lock()
    assert dangling_access is None, "Error: WeakPtr harus gagal jika resource sudah terhapus!"
    Terminal.success("Semantik pencegahan dangling pointer via weak_ptr valid.\n")

    # --- Skenario 3: Move Semantics & Benchmark Copy vs Move ---
    Terminal.step("Eksperimen 3: Move Semantics vs Deep Copy (Performance & Pointer Steal)")
    size = 2_000_000

    # Uji Deep Copy
    source_buf = DynamicBuffer("SourceHeavyBuffer", size)
    t0 = time.perf_counter()
    copied_buf = source_buf.copy()
    t_copy = (time.perf_counter() - t0) * 1000
    print(f"    [Benchmark] Deep Copy Latency: {t_copy:.3f} ms")

    # Uji Move Semantics
    moved_target = DynamicBuffer("TargetPlaceholder", 0)
    t0 = time.perf_counter()
    moved_target.move_from(cpp_move(source_buf))
    t_move = (time.perf_counter() - t0) * 1000
    print(f"    [Benchmark] Move Operation Latency: {t_move:.3f} ms")

    # Verifikasi post-condition state
    Terminal.info(f"State source buffer: valid={source_buf.is_valid()}, size={source_buf.size_bytes}")
    Terminal.info(f"State target buffer: valid={moved_target.is_valid()}, size={moved_target.size_bytes}")
    assert not source_buf.is_valid(), "Source buffer harus dalam keadaan moved-from (invalid/nullptr)!"
    assert moved_target.is_valid() and moved_target.size_bytes == size, "Target buffer harus memiliki data utuh!"

    speedup = t_copy / max(t_move, 0.0001)
    Terminal.success(f"Move semantics selesai: Peningkatan efisiensi sebesar {speedup:.1f}x lipat.")
    Terminal.header("LAB DEEP DIVE SELESAI DENGAN SUKSES")


if __name__ == "__main__":
    main()