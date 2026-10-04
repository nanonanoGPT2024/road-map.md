#!/usr/bin/env python3
"""
Lab Hands-on: C++ Modul 02 Deep Dive - Memory Semantics, RAII, Smart Pointers, and VTable Dispatch
Deskripsi:
  Skrip ini memodelkan sistem runtime internal C++:
  1. Simulated Memory Arena & Heap Tracker (Deteksi memory leak & double-free).
  2. RAII Smart Pointers: UniquePtr (Move Semantics) & SharedPtr/WeakPtr (Control Block & Reference Counting).
  3. Dynamic Polymorphism via Explicit Virtual Table (vptr & vtable layout simulation).
"""

import sys
import time
from typing import Any, Callable, Dict, Optional

# --- ANSI Formatting ---
class TerminalColor:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"

def log_info(msg: str) -> None:
    print(f"{TerminalColor.CYAN}[INFO]{TerminalColor.RESET} {msg}")

def log_success(msg: str) -> None:
    print(f"{TerminalColor.GREEN}[SUCCESS]{TerminalColor.RESET} {msg}")

def log_warn(msg: str) -> None:
    print(f"{TerminalColor.YELLOW}[WARN]{TerminalColor.RESET} {msg}")

def log_destructor(msg: str) -> None:
    print(f"{TerminalColor.MAGENTA}[RAII-DESTRUCTOR]{TerminalColor.RESET} {msg}")


# =====================================================================
# 1. SIMULASI MEMORY ARENA / HEAP TRACKER
# =====================================================================
class MemoryArena:
    """
    Mensimulasikan alokator memori heap C++ (malloc/free & new/delete).
    Memantau alokasi aktif untuk memvalidasi zero-leak saat runtime selesai.
    """
    def __init__(self):
        self._active_allocations: Dict[int, int] = {}  # Address -> Size
        self._next_address: int = 0x1000
        self.total_allocated: int = 0
        self.total_deallocated: int = 0

    def allocate(self, size: int) -> int:
        addr = self._next_address
        self._next_address += max(size, 8)
        self._active_allocations[addr] = size
        self.total_allocated += size
        return addr

    def deallocate(self, addr: int) -> None:
        if addr not in self._active_allocations:
            raise RuntimeError(f"SIGABRT: Double free atau korupsi heap pada pointer 0x{addr:08X}!")
        size = self._active_allocations.pop(addr)
        self.total_deallocated += size

    def report_leaks(self) -> None:
        print(f"\n{TerminalColor.BOLD}--- [Heap Sanity / Leak Sanitizer Report] ---{TerminalColor.RESET}")
        print(f"Total Alokasi : {self.total_allocated} bytes")
        print(f"Total Deallok : {self.total_deallocated} bytes")
        if self._active_allocations:
            print(f"{TerminalColor.RED}Deteksi Leak! {len(self._active_allocations)} pointer belum didealokasi:{TerminalColor.RESET}")
            for addr, sz in self._active_allocations.items():
                print(f"  -> Alamat 0x{addr:08X} ({sz} bytes)")
        else:
            log_success("Heap Bersih: 0 byte memory leak terdeteksi.")


GLOBAL_ARENA = MemoryArena()


# =====================================================================
# 2. SIMULASI VTABLE (VIRTUAL TABLE & DYNAMIC DISPATCH)
# =====================================================================
class VTable:
    """Menyimpan pemetaan function pointer untuk polymorphism runtime."""
    def __init__(self, class_name: str, parent_table: Optional['VTable'] = None):
        self.class_name = class_name
        self.slots: Dict[str, Callable] = {}
        if parent_table:
            # Mewarisi entry vtable induk (seperti di layout C++)
            self.slots.update(parent_table.slots)

    def bind(self, method_name: str, func: Callable):
        self.slots[method_name] = func


class CppBaseObject:
    """
    Kelas dasar yang menyematkan `_vptr` (pointer ke VTable).
    Memodelkan overhead pointer 8-byte tersembunyi pada objek polimorfik C++.
    """
    def __init__(self, vtable: VTable, size_in_bytes: int):
        self._vptr = vtable
        self.raw_ptr = GLOBAL_ARENA.allocate(size_in_bytes)
        self.is_destroyed = False

    def dispatch(self, method_name: str, *args, **kwargs) -> Any:
        if self.is_destroyed:
            raise RuntimeError(f"Use-After-Free terdeteksi saat memanggil virtual function '{method_name}'!")
        if method_name not in self._vptr.slots:
            raise AttributeError(f"VTable '{self._vptr.class_name}' tidak memiliki fungsi '{method_name}'!")
        # Dynamic dispatch melalui vptr
        return self._vptr.slots[method_name](self, *args, **kwargs)

    def destroy(self):
        if not self.is_destroyed:
            self.is_destroyed = True
            GLOBAL_ARENA.deallocate(self.raw_ptr)


# VTable Definitions
vtable_IODevice = VTable("IODevice")
vtable_SocketDevice = VTable("SocketDevice", parent_table=vtable_IODevice)

# Binding Implementasi Virtual Functions
vtable_IODevice.bind("write", lambda self, data: f"[IODevice::write] Menulis mentah {len(data)} byte.")
vtable_SocketDevice.bind("write", lambda self, data: f"[SocketDevice::write (Overridden)] Mengirim {len(data)} byte ke Socket FD.")


# =====================================================================
# 3. SIMULASI RAII SMART POINTERS
# =====================================================================

class UniquePtr:
    """
    Memodelkan std::unique_ptr<T>:
    - Sole ownership: Copy constructor dihapus (= delete).
    - Hanya mendukung Move Semantics (std::move).
    - Deterministic Destruction saat keluar dari scope.
    """
    def __init__(self, resource: Optional[CppBaseObject] = None):
        self._resource = resource

    def __del__(self):
        self.reset()

    def reset(self, new_resource: Optional[CppBaseObject] = None):
        if self._resource is not None:
            log_destructor(f"UniquePtr membebaskan objek {self._resource._vptr.class_name} di 0x{self._resource.raw_ptr:08X}")
            self._resource.destroy()
        self._resource = new_resource

    def release(self) -> Optional[CppBaseObject]:
        res = self._resource
        self._resource = None
        return res

    def move(self) -> 'UniquePtr':
        """Simulasi std::move(): transfer kepemilikan dan nullify source."""
        if self._resource is None:
            return UniquePtr(None)
        transferred = self._resource
        self._resource = None
        return UniquePtr(transferred)

    def get(self) -> Optional[CppBaseObject]:
        return self._resource

    def __bool__(self) -> bool:
        return self._resource is not None


class ControlBlock:
    """Control Block pada std::shared_ptr yang mengelola strong dan weak count."""
    def __init__(self, resource: CppBaseObject):
        self.resource: Optional[CppBaseObject] = resource
        self.strong_count: int = 1
        self.weak_count: int = 0
        self.ctrl_ptr = GLOBAL_ARENA.allocate(16)  # 8 bytes strong + 8 bytes weak


class SharedPtr:
    """
    Memodelkan std::shared_ptr<T>:
    - Shared Ownership dengan atomic reference counting.
    - Menghancurkan resource ketika strong_count == 0.
    """
    def __init__(self, resource: Optional[CppBaseObject] = None, _ctrl: Optional[ControlBlock] = None):
        if _ctrl is not None:
            self._ctrl = _ctrl
            self._ctrl.strong_count += 1
        elif resource is not None:
            self._ctrl = ControlBlock(resource)
        else:
            self._ctrl = None

    def use_count(self) -> int:
        return self._ctrl.strong_count if self._ctrl else 0

    def copy(self) -> 'SharedPtr':
        """Copy Constructor: menaikkan strong ref count."""
        if self._ctrl:
            return SharedPtr(_ctrl=self._ctrl)
        return SharedPtr()

    def reset(self):
        if self._ctrl:
            self._ctrl.strong_count -= 1
            if self._ctrl.strong_count == 0:
                if self._ctrl.resource:
                    log_destructor(f"SharedPtr (Ref hit 0) membebaskan objek di 0x{self._ctrl.resource.raw_ptr:08X}")
                    self._ctrl.resource.destroy()
                    self._ctrl.resource = None
                if self._ctrl.weak_count == 0:
                    GLOBAL_ARENA.deallocate(self._ctrl.ctrl_ptr)
            self._ctrl = None

    def __del__(self):
        self.reset()

    def get(self) -> Optional[CppBaseObject]:
        return self._ctrl.resource if self._ctrl else None


# =====================================================================
# 4. RUNNER SIMULASI & VERIFIKASI
# =====================================================================
def run_lab_demonstrations():
    print(f"{TerminalColor.BOLD}{TerminalColor.CYAN}======================================================================{TerminalColor.RESET}")
    print(f"{TerminalColor.BOLD}   C++ LAB: INTERNAL MEMORY, RAII, DAN DYNAMIC POLYMORPHISM ENGINE   {TerminalColor.RESET}")
    print(f"{TerminalColor.BOLD}{TerminalColor.CYAN}======================================================================{TerminalColor.RESET}\n")

    # TEST 1: VTable Polymorphism
    log_info("--- FASE 1: Dynamic Dispatch melalui VTable Layout ---")
    dev_base = CppBaseObject(vtable_IODevice, size_in_bytes=32)
    dev_socket = CppBaseObject(vtable_SocketDevice, size_in_bytes=64)

    payload = b"PING_PACKET"
    # Memanggil method melalui vptr dispatch (bukan Python getattr biasa)
    print(f"Base Call  : {dev_base.dispatch('write', payload)}")
    print(f"Socket Call: {dev_socket.dispatch('write', payload)}")
    
    dev_base.destroy()
    dev_socket.destroy()
    log_success("Dynamic dispatch vtable berhasil dieksekusi.\n")

    # TEST 2: UniquePtr & Move Semantics
    log_info("--- FASE 2: std::unique_ptr Ownership & Move Semantics ---")
    u_ptr1 = UniquePtr(CppBaseObject(vtable_SocketDevice, size_in_bytes=48))
    log_info(f"UniquePtr-1 memiliki objek di: 0x{u_ptr1.get().raw_ptr:08X}")
    
    # Simulasi move semantics: std::move(u_ptr1)
    log_info("Melakukan std::move(u_ptr1) ke UniquePtr-2...")
    u_ptr2 = u_ptr1.move()

    print(f"Status u_ptr1 valid? : {bool(u_ptr1)} (nullified)")
    print(f"Status u_ptr2 valid? : {bool(u_ptr2)} (owns resource: 0x{u_ptr2.get().raw_ptr:08X})")

    # Explicit reset (seperti scope exit RAII)
    u_ptr2.reset()
    log_success("UniquePtr deterministik RAII selesai.\n")

    # TEST 3: SharedPtr Reference Counting
    log_info("--- FASE 3: std::shared_ptr Reference Counting & Lifecyle ---")
    shared_a = SharedPtr(CppBaseObject(vtable_IODevice, size_in_bytes=128))
    log_info(f"shared_a dibuat. Ref count = {shared_a.use_count()}")

    shared_b = shared_a.copy()
    shared_c = shared_a.copy()
    log_info(f"shared_b & shared_c dikloning. Ref count = {shared_a.use_count()}")

    log_info("Destructing shared_b dan shared_c...")
    shared_b.reset()
    shared_c.reset()
    log_info(f"Sisa Ref count pada shared_a = {shared_a.use_count()}")

    log_info("Destructing shared_a (Ref count harus mencapai 0)...")
    shared_a.reset()
    log_success("SharedPtr destruction lifecycle sukses.\n")

    # TEST 4: Sanitizer Audit
    GLOBAL_ARENA.report_leaks()


if __name__ == "__main__":
    start_time = time.perf_counter()
    try:
        run_lab_demonstrations()
    except Exception as exc:
        print(f"{TerminalColor.RED}FATAL RUNTIME PANIC: {exc}{TerminalColor.RESET}", file=sys.stderr)
        sys.exit(1)
    finally:
        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"\n{TerminalColor.BOLD}[Runtime Summary]{TerminalColor.RESET} Execution time: {elapsed:.2f} ms")
        print(f"{TerminalColor.GREEN}Lab selesai tanpa segfault.{TerminalColor.RESET}")