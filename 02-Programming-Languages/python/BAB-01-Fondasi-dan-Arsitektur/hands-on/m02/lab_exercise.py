#!/usr/bin/env python3
"""
Lab Hands-on: CPython Runtime Internals & Architecture Deep Dive
Kategori: 02-Programming-Languages / Python / Bab 01 - Modul 02

Topik Eksplorasi:
1. PyObject Memory Layout (ob_refcnt, ob_type) via ctypes memory casting.
2. Singletons & Memory Optimization (Small Integer Cache & String Interning).
3. Tri-Color Generational Garbage Collection & Cyclic Reference Resolution.
4. CPython CEval Frame Stack Machine Simulation.
"""

import sys
import gc
import ctypes
import dis
from typing import Any, List, Tuple

# ANSI Terminal Styling
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_CYAN   = "\033[36m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED    = "\033[31m"
CLR_MAGENTA= "\033[35m"

def print_section(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}[LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")

# -------------------------------------------------------------------------
# SECTION 1: CPython PyObject Memory Layout Inspection
# -------------------------------------------------------------------------
class CPyObjectHeader(ctypes.Structure):
    """
    Representasi C-Level struct PyObject dari CPython:
    typedef struct _object {
        _PyObject_HEAD_EXTRA // kosong jika bukan Py_TRACE_REFS
        Py_ssize_t ob_refcnt;
        struct _typeobject *ob_type;
    } PyObject;
    """
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type", ctypes.c_void_p),
    ]

def inspect_pyobject(target: Any, label: str) -> None:
    """Membaca layout memori internal PyObject langsung dari address pointer."""
    mem_addr = id(target)
    header = CPyObjectHeader.from_address(mem_addr)
    type_ptr = ctypes.c_void_p.from_address(id(type(target)))
    
    print(f"{CLR_YELLOW}-> Target: {CLR_BOLD}{label}{CLR_RESET}")
    print(f"   Memory Address (id) : 0x{mem_addr:016X}")
    print(f"   Internal ob_refcnt  : {CLR_GREEN}{header.ob_refcnt}{CLR_RESET} (raw header)")
    print(f"   sys.getrefcount()   : {header.ob_refcnt} (termasuk argumen passing)")
    print(f"   ob_type Pointer     : 0x{header.ob_type:016X}")
    print(f"   Type Obj Match      : {CLR_GREEN if header.ob_type == type_ptr.value else CLR_RED}{header.ob_type == type_ptr.value}{CLR_RESET}")

# -------------------------------------------------------------------------
# SECTION 2: Singletons: Small Integer Cache & String Interning
# -------------------------------------------------------------------------
def test_cpython_optimizations() -> None:
    """Verifikasi batas Small Integer Cache [-5, 256] dan Interning mekanik."""
    print_section("CPython Memory Optimizations (Caches & Interning)")

    # 1. Integer Caching Boundary Test
    print(f"{CLR_BOLD}[*] Verifikasi Small Integer Cache (Batas: -5 s/d 256):{CLR_RESET}")
    sample_values = [-6, -5, 100, 256, 257]
    for val in sample_values:
        # Dynamic evaluation untuk mencegah compiler folder optimization
        a = int(str(val))
        b = int(str(val))
        is_same_obj = (a is b)
        color = CLR_GREEN if is_same_obj else CLR_RED
        print(f"   Value: {val:>4} | id(a): 0x{id(a):012X} | id(b): 0x{id(b):012X} | 'a is b': {color}{is_same_obj}{CLR_RESET}")

    # 2. String Interning Probe
    print(f"\n{CLR_BOLD}[*] Verifikasi String Interning:{CLR_RESET}")
    # String dengan karakter non-identifier biasanya tidak di-intern otomatis saat runtime
    s1 = "".join(["cpython", "_", "interning", "_", "probe"])
    s2 = "".join(["cpython", "_", "interning", "_", "probe"])
    print(f"   Dynamic String (Non-interned) -> 's1 is s2': {CLR_RED}{s1 is s2}{CLR_RESET}")
    
    s1_interned = sys.intern(s1)
    s2_interned = sys.intern(s2)
    print(f"   Setelah sys.intern()          -> 's1 is s2': {CLR_GREEN}{s1_interned is s2_interned}{CLR_RESET}")

# -------------------------------------------------------------------------
# SECTION 3: Cyclic Reference & Generational GC Mechanics
# -------------------------------------------------------------------------
class CyclicNode:
    def __init__(self, name: str):
        self.name = name
        self.partner = None

    def __repr__(self) -> str:
        return f"<Node {self.name}>"

def test_generational_gc() -> None:
    """Mendemonstrasikan isolasi cycle dan eksekusi Generational Garbage Collector."""
    print_section("Cyclic Garbage Collection Simulation")
    
    # Nonaktifkan automatic collection sementara agar siklus dapat dianalisis
    gc.disable()
    print("[-] GC otomatis dinonaktifkan sementara...")

    # Buat siklus sirkular yang tidak dapat diselesaikan oleh Reference Counting murni
    node_a = CyclicNode("Alfa")
    node_b = CyclicNode("Beta")
    node_a.partner = node_b
    node_b.partner = node_a

    addr_a = id(node_a)
    addr_b = id(node_b)

    print(f"   Node A created at 0x{addr_a:012X}, RefCount: {sys.getrefcount(node_a)-1}")
    print(f"   Node B created at 0x{addr_b:012X}, RefCount: {sys.getrefcount(node_b)-1}")

    # Hapus pointer di stack frame
    print(f"{CLR_YELLOW}[-] Menghapus referensi lokal node_a dan node_b (Del local scope)...{CLR_RESET}")
    del node_a
    del node_b

    # Verifikasi bahwa objek masih tertinggal di heap melalui header dump
    raw_a = CPyObjectHeader.from_address(addr_a)
    print(f"   Address 0x{addr_a:012X} ob_refcnt setelah local del: {CLR_RED}{raw_a.ob_refcnt}{CLR_RESET} (Cyclic Leak Terdeteksi!)")

    print(f"[*] Menjalankan gc.collect() manual...")
    unreachable_count = gc.collect()
    print(f"{CLR_GREEN}[+] GC Berhasil membebaskan {unreachable_count} objek unreachable.{CLR_RESET}")
    
    gc.enable()
    print("[+] GC otomatis diaktifkan kembali.")

# -------------------------------------------------------------------------
# SECTION 4: Virtual Machine - CEval Stack Machine Simulation
# -------------------------------------------------------------------------
class VirtualStackMachine:
    """
    Miniatur CPython Evaluation Loop (_PyEval_EvalFrameDefault).
    Mensimulasikan eksekusi bytecode berbasis Evaluation Stack.
    """
    def __init__(self, bytecode: List[Tuple[str, Any]]):
        self.bytecode = bytecode
        self.stack: List[Any] = []
        self.environment: dict = {}

    def run(self) -> Any:
        print_section("CPython CEval Frame Loop Simulation")
        print(f"{'IP':<4} | {'Instruction':<18} | {'Argument':<12} | {'Evaluation Stack'}")
        print("-" * 65)

        ip = 0
        while ip < len(self.bytecode):
            op, arg = self.bytecode[ip]
            
            if op == "LOAD_CONST":
                self.stack.append(arg)
            elif op == "STORE_FAST":
                self.environment[arg] = self.stack.pop()
            elif op == "LOAD_FAST":
                self.stack.append(self.environment[arg])
            elif op == "BINARY_ADD":
                right = self.stack.pop()
                left = self.stack.pop()
                self.stack.append(left + right)
            elif op == "BINARY_MULTIPLY":
                right = self.stack.pop()
                left = self.stack.pop()
                self.stack.append(left * right)
            elif op == "RETURN_VALUE":
                retval = self.stack.pop()
                print(f"{ip:<4} | {op:<18} | {str(arg):<12} | {str(self.stack)}")
                return retval
            else:
                raise RuntimeError(f"Unknown Opcode: {op}")

            stack_snapshot = str(self.stack)
            print(f"{ip:<4} | {op:<18} | {str(arg):<12} | {CLR_MAGENTA}{stack_snapshot}{CLR_RESET}")
            ip += 1

        return None

def target_computation(x: int, y: int) -> int:
    return (x + 10) * y

# -------------------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------------------
def main() -> None:
    print(f"{CLR_BOLD}SYSTEM LAB: CPYTHON RUNTIME & ARCHITECTURE INTERNALS{CLR_RESET}")
    print(f"Python Platform: {sys.implementation.name} {sys.version.split()[0]} on {sys.platform}\n")

    # 1. C-Struct Memory Inspection
    print_section("PyObject Layout Inspection")
    dummy_payload = {"framework": "cpython", "core_version": 3}
    inspect_pyobject(dummy_payload, "dictionary 'dummy_payload'")
    
    # 2. Caching optimizations
    test_cpython_optimizations()

    # 3. Cyclical References & Generational GC
    test_generational_gc()

    # 4. Bytecode & Stack Execution
    print_section("Real Python Function Bytecode Introspection")
    print(f"Target Function: def target_computation(x, y): return (x + 10) * y")
    dis.dis(target_computation)

    # 5. Run Custom CEval Engine simulation equivalent
    simulated_bytecode = [
        ("LOAD_FAST", "x"),
        ("LOAD_CONST", 10),
        ("BINARY_ADD", None),
        ("LOAD_FAST", "y"),
        ("BINARY_MULTIPLY", None),
        ("RETURN_VALUE", None),
    ]
    vm = VirtualStackMachine(simulated_bytecode)
    vm.environment["x"] = 5
    vm.environment["y"] = 4
    result = vm.run()
    
    print(f"\n{CLR_GREEN}{CLR_BOLD}VM Simulation Result : {result}{CLR_RESET}")
    print(f"Native Python Result : {target_computation(5, 4)}")
    assert result == target_computation(5, 4), "Engine simulation mismatch!"
    print(f"{CLR_CYAN}[+] Verifikasi Eksekusi Virtual Machine Berhasil 100%.{CLR_RESET}\n")

if __name__ == "__main__":
    main()