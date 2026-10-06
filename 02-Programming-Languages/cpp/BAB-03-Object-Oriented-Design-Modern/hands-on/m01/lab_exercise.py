#!/usr/bin/env python3
"""
BAB-03: Object-Oriented Design & Modern C++ Concepts Simulator
==============================================================
Simulasi interaktif konsep OOP Modern C++:
1. Virtual Method Table (VTable & VPtr) Memory Layout Emulation
2. Rule of 5 & Move Semantics (Resource Acquisition Is Initialization - RAII)
3. Smart Pointer Simulation (std::unique_ptr vs std::shared_ptr ref-counting)
4. Curiously Recurring Template Pattern (CRTP - Static Polymorphism)
5. Interface Contracts (Virtual Pure, override, final semantics)
"""

import sys
import time
from typing import Dict, Any, Optional, List

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    banner = f"""{CYAN}{BOLD}
╔══════════════════════════════════════════════════════════════════╗
║        C++ MODERN OOP & INTERNALS SIMULATOR (BAB-03)             ║
║   RAII | Rule of 5 | VTable Emulation | Smart Pointers | CRTP    ║
╚══════════════════════════════════════════════════════════════════╝{RESET}"""
    print(banner)


# ==============================================================================
# 1. EMULASI VTABLE & DYNAMIC DISPATCH INTERNALS
# ==============================================================================
class VTable:
    """Emulasi Virtual Function Table milik runtime C++."""
    def __init__(self, class_name: str, function_ptrs: Dict[str, str]):
        self.class_name = class_name
        self.table = function_ptrs

    def dump(self):
        print(f"  {MAGENTA}┌─── [VTable: {self.class_name}] ───{RESET}")
        for slot_idx, (fn_name, addr) in enumerate(self.table.items()):
            print(f"  {MAGENTA}│ Slot {slot_idx}: {fn_name:12} -> {addr}{RESET}")
        print(f"  {MAGENTA}└──────────────────────────────────{RESET}")


class CppObjectMemoryLayout:
    """Emulasi layout memori objek dengan pointer vptr tersembunyi di offset 0."""
    def __init__(self, vtable: VTable, member_vars: Dict[str, Any]):
        self.vptr = vtable  # Offset 0x00 dalam memori objek 64-bit
        self.members = member_vars

    def inspect_memory(self, obj_name: str):
        print(f"{YELLOW}[Memory Layout for: {obj_name}]{RESET}")
        print(f"  0x0000: *vptr -> Points to VTable '{self.vptr.class_name}'")
        offset = 8
        for name, val in self.members.items():
            print(f"  0x{offset:04X}: member '{name}' = {val} ({type(val).__name__})")
            offset += 8


def demo_vtable_dispatch():
    print(f"\n{BOLD}{CYAN}=== 1. Emulasi VTable & Dynamic Dispatch Internals ==={RESET}")
    base_vtable = VTable("BaseEntity", {
        "draw()": "0x00401120 (BaseEntity::draw)",
        "serialize()": "0x00401180 (BaseEntity::serialize)",
        "~Base()": "0x004011F0 (virtual destructor)"
    })
    player_vtable = VTable("PlayerEntity (Derived)", {
        "draw()": "0x00402240 (PlayerEntity::draw) [OVERRIDDEN]",
        "serialize()": "0x00401180 (BaseEntity::serialize) [INHERITED]",
        "~Base()": "0x004022F0 (PlayerEntity::~PlayerEntity) [VIRTUAL DTOR]"
    })

    base_vtable.dump()
    player_vtable.dump()

    player_obj = CppObjectMemoryLayout(player_vtable, {"player_id": 1042, "health": 98.5})
    player_obj.inspect_memory("playerInstance")

    print(f"\n{GREEN}-> Memanggil entity->draw() via pointer BaseEntity*:{RESET}")
    resolved_fn = player_obj.vptr.table["draw()"]
    print(f"  Dereference *vptr[slot 0] -> Melompat ke: {BOLD}{resolved_fn}{RESET}")


# ==============================================================================
# 2. EMULASI RULE OF 5 & MOVE SEMANTICS
# ==============================================================================
class DynamicBufferResource:
    """Emulasi RAII Buffer C++ (Rule of 5)."""
    _counter = 0

    def __init__(self, name: str, size: int):
        DynamicBufferResource._counter += 1
        self.res_id = DynamicBufferResource._counter
        self.name = name
        self.size = size
        self.buffer_ptr: Optional[List[int]] = [0] * size
        print(f"{GREEN}[RAII Ctor]{RESET} Alokasi heap ({self.size} bytes) untuk '{self.name}' (ID: #{self.res_id})")

    def __del__(self):
        if self.buffer_ptr is not None:
            print(f"{RED}[RAII Dtor]{RESET} Deallokasi heap ({self.size} bytes) milik '{self.name}' (ID: #{self.res_id})")
        else:
            print(f"{MAGENTA}[RAII Dtor (Zombified)]{RESET} Objek '{self.name}' telah di-move! Tidak ada free heap double.")

    def copy(self, new_name: str) -> "DynamicBufferResource":
        """Emulasi Copy Constructor: Deep Copy biaya tinggi."""
        print(f"{YELLOW}[Copy Ctor]{RESET} Melakukan Deep Copy {self.size} bytes dari '{self.name}' ke '{new_name}'")
        copied = DynamicBufferResource(new_name, self.size)
        copied.buffer_ptr = list(self.buffer_ptr) if self.buffer_ptr else None
        return copied

    def move_to(self, target_name: str) -> "DynamicBufferResource":
        """Emulasi Move Constructor: Shallow pointer steal (zero allocation overhead)."""
        print(f"{CYAN}[Move Ctor (std::move)]{RESET} Mencuri heap pointer dari '{self.name}' ke '{target_name}' (O(1))")
        moved = DynamicBufferResource.__new__(DynamicBufferResource)
        DynamicBufferResource._counter += 1
        moved.res_id = DynamicBufferResource._counter
        moved.name = target_name
        moved.size = self.size
        # Transfer ownership
        moved.buffer_ptr = self.buffer_ptr
        # Nullify source pointer
        self.buffer_ptr = None
        return moved


def demo_rule_of_five():
    print(f"\n{BOLD}{CYAN}=== 2. Emulasi RAII, Deep Copy, vs Move Semantics (std::move) ==={RESET}")
    orig = DynamicBufferResource("OriginalBuffer", 1024)

    # Copy deep
    copied = orig.copy("ClonedBuffer")

    # Move cheap
    moved = orig.move_to("MovedTargetBuffer")

    print(f"Status buffer sumber setelah move: buffer_ptr={moved.buffer_ptr is not None} | orig.buffer_ptr={orig.buffer_ptr}")


# ==============================================================================
# 3. EMULASI SMART POINTERS (std::unique_ptr & std::shared_ptr)
# ==============================================================================
class SharedControlBlock:
    def __init__(self, managed_res: str):
        self.resource = managed_res
        self.strong_ref_count = 1
        print(f"{GREEN}[ControlBlock]{RESET} Created for '{self.resource}', strong_count = {self.strong_ref_count}")

    def retain(self):
        self.strong_ref_count += 1
        print(f"  {CYAN}+ Ref incremented:{RESET} count={self.strong_ref_count}")

    def release(self):
        self.strong_ref_count -= 1
        print(f"  {YELLOW}- Ref decremented:{RESET} count={self.strong_ref_count}")
        if self.strong_ref_count <= 0:
            print(f"  {RED}[ControlBlock Deletion]{RESET} strong_count reached 0! Destructing '{self.resource}'.")


class SharedPtr:
    def __init__(self, control_block: Optional[SharedControlBlock] = None):
        self._cb = control_block

    def clone(self) -> "SharedPtr":
        if self._cb:
            self._cb.retain()
        return SharedPtr(self._cb)

    def reset(self):
        if self._cb:
            self._cb.release()
            self._cb = None


def demo_smart_pointers():
    print(f"\n{BOLD}{CYAN}=== 3. Emulasi Smart Pointer: std::shared_ptr Reference Counting ==={RESET}")
    cb = SharedControlBlock("DatabaseConnectionPool")
    sp1 = SharedPtr(cb)

    print(f"\n{YELLOW}[Scope A] Cloning shared_ptr -> sp2 & sp3{RESET}")
    sp2 = sp1.clone()
    sp3 = sp1.clone()

    print(f"\n{YELLOW}[Scope B] Resetting sp3 & sp2{RESET}")
    sp3.reset()
    sp2.reset()

    print(f"\n{YELLOW}[Scope C] Resetting original sp1 (Last owner){RESET}")
    sp1.reset()


# ==============================================================================
# 4. CRTP (CURIOUSLY RECURRING TEMPLATE PATTERN) STATIC POLYMORPHISM
# ==============================================================================
class CRTPBase:
    """Emulasi static polymorphism template <typename Derived> class Base."""
    def execute_static_dispatch(self):
        # Pada compile time C++, this->actual_work() langsung di-inline tanpa VTable overhead!
        start = time.perf_counter_ns()
        res = self.actual_work()
        elapsed = time.perf_counter_ns() - start
        print(f"  {GREEN}[CRTP Zero-Cost Call]{RESET} Result: {res} (Direct Inlined: ~{elapsed} ns, 0 VPtr indirection)")

    def actual_work(self):
        raise NotImplementedError("CRTP contract violated!")


class FastMathEngine(CRTPBase):
    def actual_work(self):
        return sum(i * i for i in range(100))


def demo_crtp():
    print(f"\n{BOLD}{CYAN}=== 4. Emulasi CRTP (Static Compile-Time Polymorphism) ==={RESET}")
    print("Memanggil subclass melalui interface base tanpa lookup vtable...")
    engine = FastMathEngine()
    engine.execute_static_dispatch()


# ==============================================================================
# MAIN INTERACTIVE LOOP
# ==============================================================================
def run_interactive():
    print_banner()
    menu = f"""
{BOLD}Pilih modul simulasi untuk dijalankan:{RESET}
  1. Emulasi VTable & Virtual Method Dispatch Layout
  2. RAII, Rule of 5 & Move Semantics (Resource Stealing)
  3. Smart Pointer Ref-Count Engine (std::shared_ptr)
  4. CRTP vs Dynamic Polymorphism Bench Simulation
  5. Jalankan Semua Simulasi Lengkap
  0. Keluar

Ketik angka opsi [0-5]: """

    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        choice = sys.argv[1]
    else:
        try:
            choice = input(menu).strip()
        except EOFError:
            choice = "5"

    if choice == "1":
        demo_vtable_dispatch()
    elif choice == "2":
        demo_rule_of_five()
    elif choice == "3":
        demo_smart_pointers()
    elif choice == "4":
        demo_crtp()
    elif choice in ("5", ""):
        demo_vtable_dispatch()
        demo_rule_of_five()
        demo_smart_pointers()
        demo_crtp()
        print(f"\n{GREEN}{BOLD}[DONE] Seluruh simulasi konsep OOP Modern C++ berhasil dieksekusi.{RESET}")
    else:
        print("Keluar dari program.")


if __name__ == "__main__":
    run_interactive()
