#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive Fondasi Runtime & Arsitektur Ruby Core (MRI/YARV)
Kategori: 02-Programming-Languages | Bab 01: Modul 02

Script ini memodelkan dan merekayasa balik (reverse-engineer) komponen kunci
runtime Ruby MRI (CRuby):
1. Sistem VALUE & Bit-Tagging (Immediate Values vs Heap RVALUEs).
2. Layout Memori Objek Heap (RBasic, RObject, Flonum, Fixnum).
3. YARV (Yet Another Ruby VM) Virtual Stack Machine.
4. Monomorphic Call Cache / Inline Cache (rb_call_cache).
5. Simulasi Penjadwalan Thread & Siklus GVL (Global VM Lock).
"""

import sys
import time
import struct
import threading
from typing import Any, Dict, List, Optional, Tuple

# --- ANSI Terminal Color Palette ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_WHITE   = "\033[37m"
CLR_BG_DARK = "\033[40m"

# ==============================================================================
# BAGIAN 1: MRI VALUE ENCODING & IMMEDIATE OBJECT REPRESENTATION
# ==============================================================================
# Di CRuby 64-bit, setiap objek adalah tipe primitif uintptr_t (VALUE).
# Trik bit-tagging LSB (Least Significant Bit) menghindari alokasi heap:
# - Fixnum (Integer)  : bit-0 == 1 -> VALUE = (n << 1) | 0x01
# - Special Consts    : bit-0 == 0, bit-1 == 0 -> Qfalse=0x00, Qnil=0x08, Qtrue=0x14
# - Symbol            : LSBs == 0x0e
# - Heap Pointer      : LSBs == 0x00 (aligned memory 8-byte boundary)

RUBY_FIXNUM_FLAG = 0x01
RUBY_SYMBOL_FLAG = 0x0E
RUBY_Qfalse      = 0x00
RUBY_Qnil        = 0x08
RUBY_Qtrue       = 0x14
RUBY_Qundef      = 0x34

class RubyValueEngine:
    """Simulasi encoding bitwise sistem VALUE pada MRI 64-bit."""

    @staticmethod
    def encode_fixnum(val: int) -> int:
        """Membuat immediate Fixnum VALUE via bit shift 1 bit ke kiri + flag."""
        return (val << 1) | RUBY_FIXNUM_FLAG

    @staticmethod
    def decode_fixnum(ruby_val: int) -> int:
        """Mengekstrak integer Python asli dari immediate Fixnum."""
        return ruby_val >> 1

    @staticmethod
    def is_fixnum(ruby_val: int) -> bool:
        return (ruby_val & 0x01) == RUBY_FIXNUM_FLAG

    @staticmethod
    def is_immediate(ruby_val: int) -> bool:
        """Mendeteksi apakah VALUE tidak membutuhkan referensi memori heap."""
        if ruby_val in (RUBY_Qfalse, RUBY_Qnil, RUBY_Qtrue, RUBY_Qundef):
            return True
        if RubyValueEngine.is_fixnum(ruby_val):
            return True
        if (ruby_val & 0xFF) == RUBY_SYMBOL_FLAG:
            return True
        return False

# ==============================================================================
# BAGIAN 2: HEAP SLOTS & RVALUE MEMORY LAYOUT (40-BYTE SLOT MODEL)
# ==============================================================================
class RBasic:
    """Struktur dasar C `struct RBasic` yang ada di setiap RVALUE Ruby."""
    def __init__(self, flags: int, klass_name: str):
        self.flags = flags          # Bitmask tipe data (T_STRING, T_ARRAY, dsb.)
        self.klass_name = klass_name  # Pointer ke Class object

class RObject:
    """
    Model representasi `RVALUE` (40 byte di 64-bit MRI).
    Terdiri dari RBasic + union data internal.
    """
    def __init__(self, obj_id: int, klass_name: str, payload: Any):
        self.address = obj_id * 40 + 0x7FFF00000000  # Simulasi pointer 8-byte aligned
        self.basic = RBasic(flags=0x20, klass_name=klass_name)
        self.payload = payload

    def inspect_memory(self) -> str:
        """Dump byte representasi struktural menyerupai memori C runtime."""
        addr_hex = f"0x{self.address:012X}"
        flags_hex = f"0x{self.basic.flags:08X}"
        return f"[ADDR: {addr_hex}] | FLAGS: {flags_hex} | KLASS: {self.basic.klass_name:<10} | DATA: {str(self.payload)}"

# ==============================================================================
# BAGIAN 3: CALL CACHE & METHOD DISPATCH (INLINE CACHING)
# ==============================================================================
class CallCache:
    """
    Simulasi `struct rb_call_cache` di YARV.
    Menyimpan cache kelas penerima dan method pointer untuk menghindari
    resolusi tabel metode yang berulang secara dinamis.
    """
    def __init__(self):
        self.cached_class: Optional[str] = None
        self.cached_method: Optional[str] = None
        self.hit_count = 0
        self.miss_count = 0

    def resolve(self, receiver_klass: str, method_name: str, method_table: Dict[str, Dict[str, Any]]) -> Tuple[Any, bool]:
        if self.cached_class == receiver_klass and self.cached_method == method_name:
            self.hit_count += 1
            return method_table[receiver_klass][method_name], True

        # Cache Miss: Dynamic method resolution
        self.miss_count += 1
        self.cached_class = receiver_klass
        self.cached_method = method_name
        resolved_method = method_table.get(receiver_klass, {}).get(method_name)
        return resolved_method, False

# ==============================================================================
# BAGIAN 4: YARV STACK MACHINE VM & BYTECODE EXECUTOR
# ==============================================================================
class YARVInstruction:
    def __init__(self, op: str, *args):
        self.op = op
        self.args = args

    def __repr__(self):
        args_str = ", ".join(repr(a) for a in self.args)
        return f"{self.op:<16} {args_str}"

class YARVVirtualMachine:
    """
    Implementasi Stack-Based Virtual Machine YARV.
    Mengeksekusi instruksi primitif: putobject, opt_plus, opt_lt, branchif,
    getlocal, setlocal, opt_send_without_block, dan leave.
    """
    def __init__(self):
        self.stack: List[int] = []  # Stack VM berisikan Ruby VALUE
        self.locals: Dict[int, int] = {}
        self.call_cache = CallCache()
        self.method_table = {
            "Integer": {
                "+": lambda a, b: a + b,
                "-": lambda a, b: a - b,
                "*": lambda a, b: a * b,
            },
            "String": {
                "length": lambda s: len(s)
            }
        }

    def execute_sequence(self, instructions: List[YARVInstruction], verbose: bool = True) -> int:
        pc = 0
        total_insns = len(instructions)

        if verbose:
            print(f"{CLR_CYAN}--- Memulai Eksekusi Bytecode YARV ---{CLR_RESET}")

        while pc < total_insns:
            insn = instructions[pc]
            op = insn.op
            args = insn.args

            if verbose:
                stack_preview = [
                    f"Fixnum({RubyValueEngine.decode_fixnum(v)})" if RubyValueEngine.is_fixnum(v) else hex(v)
                    for v in self.stack[-3:]
                ]
                print(f" PC={pc:03d} | {CLR_YELLOW}{insn!s:<26}{CLR_RESET} | Stack: {stack_preview}")

            if op == "putobject":
                # Mengubah primitif Python ke representasi VALUE Ruby
                raw_val = args[0]
                if isinstance(raw_val, int):
                    ruby_val = RubyValueEngine.encode_fixnum(raw_val)
                elif raw_val is True:
                    ruby_val = RUBY_Qtrue
                elif raw_val is False:
                    ruby_val = RUBY_Qfalse
                elif raw_val is None:
                    ruby_val = RUBY_Qnil
                else:
                    ruby_val = id(raw_val)  # Pointer heap tiruan
                self.stack.append(ruby_val)
                pc += 1

            elif op == "setlocal":
                slot = args[0]
                self.locals[slot] = self.stack.pop()
                pc += 1

            elif op == "getlocal":
                slot = args[0]
                self.stack.append(self.locals[slot])
                pc += 1

            elif op == "opt_plus":
                b_val = self.stack.pop()
                a_val = self.stack.pop()
                # Fast path jika keduanya adalah immediate Fixnum
                if RubyValueEngine.is_fixnum(a_val) and RubyValueEngine.is_fixnum(b_val):
                    res = RubyValueEngine.decode_fixnum(a_val) + RubyValueEngine.decode_fixnum(b_val)
                    self.stack.append(RubyValueEngine.encode_fixnum(res))
                else:
                    raise TypeError("Operasi non-Fixnum di luar fast path opt_plus!")
                pc += 1

            elif op == "opt_send_without_block":
                method_name = args[0]
                recv_val = self.stack.pop()
                arg_val = self.stack.pop() if len(args) > 1 and args[1] > 0 else None

                klass = "Integer" if RubyValueEngine.is_fixnum(recv_val) else "Object"
                fn, hit = self.call_cache.resolve(klass, method_name, self.method_table)

                if fn:
                    raw_a = RubyValueEngine.decode_fixnum(recv_val)
                    raw_b = RubyValueEngine.decode_fixnum(arg_val)
                    res_raw = fn(raw_a, raw_b)
                    self.stack.append(RubyValueEngine.encode_fixnum(res_raw))
                pc += 1

            elif op == "opt_lt":
                # Operator Less Than: a < b
                b_val = self.stack.pop()
                a_val = self.stack.pop()
                a = RubyValueEngine.decode_fixnum(a_val)
                b = RubyValueEngine.decode_fixnum(b_val)
                self.stack.append(RUBY_Qtrue if a < b else RUBY_Qfalse)
                pc += 1

            elif op == "branchif":
                target_pc = args[0]
                cond = self.stack.pop()
                # Di Ruby, hanya Qfalse dan Qnil yang bernilai falsy
                if cond != RUBY_Qfalse and cond != RUBY_Qnil:
                    pc = target_pc
                else:
                    pc += 1

            elif op == "leave":
                break
            else:
                raise NotImplementedError(f"Instruksi YARV {op} tidak dikenal.")

        result_val = self.stack[-1] if self.stack else RUBY_Qnil
        return result_val

# ==============================================================================
# BAGIAN 5: GVL (GLOBAL VM LOCK) THREAD CONTROLLER SIMULATION
# ==============================================================================
class GVLContext:
    """
    Simulasi cara kerja Global VM Lock pada MRI.
    Hanya satu Ruby Thread yang dapat mengeksekusi instruksi YARV pada satu waktu,
    walaupun thread OS native berjalan secara konkuren.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.active_thread_id = None
        self.preemption_ticks = 0

    def acquire_gvl(self, worker_name: str):
        self.lock.acquire()
        self.active_thread_id = worker_name

    def release_gvl(self):
        self.active_thread_id = None
        self.lock.release()

def simulated_ruby_thread_worker(worker_id: str, iterations: int, gvl: GVLContext, stats: Dict[str, int]):
    vm = YARVVirtualMachine()
    # Program simulasi: Loop penjumlahan n kali
    # Eksekusi dilakukan per-chunk instruksi untuk merefleksikan preemption tick
    for i in range(iterations):
        gvl.acquire_gvl(worker_id)
        try:
            # Memproses 1 cycle komputasi Ruby
            instructions = [
                YARVInstruction("putobject", i),
                YARVInstruction("putobject", 1),
                YARVInstruction("opt_plus"),
                YARVInstruction("leave")
            ]
            vm.execute_sequence(instructions, verbose=False)
            stats[worker_id] += 1
            # Simulasi timeslice/preemption (RUBY_VM_CHECK_INTS)
            time.sleep(0.0005)
        finally:
            gvl.release_gvl()
            # Berikan waktu sistem OS berpindah context thread
            time.sleep(0.0001)

# ==============================================================================
# ENTRY POINT / LAB EXECUTION RUNNER
# ==============================================================================
def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_WHITE} LAB PENELITIAN RUNTIME: MRI / YARV CORE ARCHITECTURE & INTERNALS {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}\n")

    # --------------------------------------------------------------------------
    # MODUL A: Validasi Immediate Values (VALUE Tagging)
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}{CLR_GREEN}[FASE 1] Bedah Arsitektur VALUE & Immediate Bit-Tagging{CLR_RESET}")
    test_integers = [0, 1, 42, 1024, 2**30 - 1]
    for num in test_integers:
        tagged = RubyValueEngine.encode_fixnum(num)
        bin_rep = f"{tagged:016b}"
        decoded = RubyValueEngine.decode_fixnum(tagged)
        print(f"  Fixnum: {num:<10} -> VALUE: 0x{tagged:08X} (Bin: ...{bin_rep[-8:]}) -> Decoded: {decoded}")

    print(f"\n  Special Constants:")
    print(f"  Qfalse -> 0x{RUBY_Qfalse:02X} | Is Immediate: {RubyValueEngine.is_immediate(RUBY_Qfalse)}")
    print(f"  Qnil   -> 0x{RUBY_Qnil:02X} | Is Immediate: {RubyValueEngine.is_immediate(RUBY_Qnil)}")
    print(f"  Qtrue  -> 0x{RUBY_Qtrue:02X} | Is Immediate: {RubyValueEngine.is_immediate(RUBY_Qtrue)}")
    print(f"  Qundef -> 0x{RUBY_Qundef:02X} | Is Immediate: {RubyValueEngine.is_immediate(RUBY_Qundef)}")

    # --------------------------------------------------------------------------
    # MODUL B: Struktur RVALUE Heap Memory Slot
    # --------------------------------------------------------------------------
    print(f"\n{CLR_BOLD}{CLR_GREEN}[FASE 2] Analisis RVALUE & Heap Object Slot Layout (40 Bytes){CLR_RESET}")
    heap_objects = [
        RObject(1, "String", "Hello YARV Core!"),
        RObject(2, "Array", [1, 2, 3, 4]),
        RObject(3, "Hash", {"mri": "cruby", "jit": "mjit"})
    ]
    for obj in heap_objects:
        print(f"  {obj.inspect_memory()}")

    # --------------------------------------------------------------------------
    # MODUL C: Eksekusi Kompilasi & Virtual Stack Machine YARV
    # --------------------------------------------------------------------------
    print(f"\n{CLR_BOLD}{CLR_GREEN}[FASE 3] YARV Instruction Dispatcher: Komputasi Fibonacci Sederhana{CLR_RESET}")
    # Source Ruby Equivalen:
    # a = 10
    # b = 20
    # res = a + b
    program = [
        YARVInstruction("putobject", 10),
        YARVInstruction("setlocal", 0),      # local[0] = 10 (a)
        YARVInstruction("putobject", 20),
        YARVInstruction("setlocal", 1),      # local[1] = 20 (b)
        YARVInstruction("getlocal", 0),      # Push 'a'
        YARVInstruction("getlocal", 1),      # Push 'b'
        YARVInstruction("opt_plus"),         # YARV Specialized arithmetic
        YARVInstruction("setlocal", 2),      # local[2] = res
        YARVInstruction("getlocal", 2),
        YARVInstruction("leave")
    ]

    vm = YARVVirtualMachine()
    raw_result = vm.execute_sequence(program, verbose=True)
    final_int = RubyValueEngine.decode_fixnum(raw_result)
    print(f"{CLR_CYAN}Hasil Eksekusi YARV:{CLR_RESET} {final_int} (Ruby VALUE: 0x{raw_result:X})\n")

    # --------------------------------------------------------------------------
    # MODUL D: Uji Coba Inline Cache (Call Cache Hit/Miss Benchmarking)
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}{CLR_GREEN}[FASE 4] Inline Cache Efficiency Verification{CLR_RESET}")
    ic_test_program = [
        YARVInstruction("putobject", 5),
        YARVInstruction("putobject", 5),
        YARVInstruction("opt_send_without_block", "+", 1),
        YARVInstruction("leave")
    ]

    # Eksekusi berulang untuk membuktikan transisi Miss -> Hits pada rb_call_cache
    for run in range(1, 6):
        vm.stack.clear()
        vm.execute_sequence(ic_test_program, verbose=False)
        print(f"  Iterasi #{run}: Cache Hits: {vm.call_cache.hit_count} | Cache Misses: {vm.call_cache.miss_count}")

    # --------------------------------------------------------------------------
    # MODUL E: Simulasi Preemption Thread di Bawah GVL (Global VM Lock)
    # --------------------------------------------------------------------------
    print(f"\n{CLR_BOLD}{CLR_GREEN}[FASE 5] Simulasi Kontensi Preemption Thread pada GVL (CRuby Model){CLR_RESET}")
    gvl = GVLContext()
    stats = {"Ruby-Worker-1": 0, "Ruby-Worker-2": 0}

    t1 = threading.Thread(target=simulated_ruby_thread_worker, args=("Ruby-Worker-1", 100, gvl, stats))
    t2 = threading.Thread(target=simulated_ruby_thread_worker, args=("Ruby-Worker-2", 100, gvl, stats))

    print(f"  {CLR_YELLOW}Menjalankan 2 native threads bersaing memperebutkan 1 GVL...{CLR_RESET}")
    t0 = time.time()
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    elapsed = time.time() - t0

    print(f"  {CLR_GREEN}Eksekusi Berakhir dalam {elapsed:.4f} detik!{CLR_RESET}")
    print(f"  Metrik Penyelesaian Instruksi:")
    for worker, count in stats.items():
        print(f"    - {worker:<15} : {count} iterasi YARV terselesaikan")
    print(f"  Semua thread terbukti dieksekusi secara serialized (interleaved lock).")

    print(f"\n{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}Lab Eksplorasi Arsitektur Ruby Core (MRI/YARV) Selesai dengan Sukses.{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")

if __name__ == "__main__":
    main()