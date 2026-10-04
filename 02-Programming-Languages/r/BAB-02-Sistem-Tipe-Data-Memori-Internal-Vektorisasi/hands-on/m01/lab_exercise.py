#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Internal Sistem Tipe Data, Memori SEXP, dan Vektorisasi R
BAB-02: Sistem Tipe Data, Memori Internal, dan Vektorisasi di R

Simulasi teknis independen menggunakan Python 3 untuk membedah arsitektur internal R:
1. SEXP (S-Expression) Structure & Header Overhead
2. Copy-on-Modify (CoM) & Reference Counter / NAMED mechanism
3. ALTREP (Alternative Representation) Memory Optimization
4. Vector Recycling Rule & Vectorized SIMD Simulation
"""

import sys
import time
import copy
from typing import List, Any, Tuple, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_DARK = "\033[40m"


def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}================================================================================
   SIMULASI INTERNAL R: TIPE DATA, MEMORI SEXP, ALTREP & VEKTORISASI (BAB-02)
================================================================================{CLR_RESET}
{CLR_YELLOW}Lab Interaktif Pemahaman Konsep Arsitektur R Internal (C-level Implementation){CLR_RESET}
"""
    print(banner)


class RAtomicType:
    LGLSXP = ("LGLSXP (Logical)", 4)
    INTSXP = ("INTSXP (Integer)", 4)
    REALSXP = ("REALSXP (Double/Real)", 8)
    CPLXSXP = ("CPLXSXP (Complex)", 16)
    STRSXP = ("STRSXP (Character Ptr)", 8)
    RAWSXP = ("RAWSXP (Raw Byte)", 1)


class SEXPVector:
    """
    Simulasi struktur internal SEXP (S-Expression) pada runtime GNU R.
    Header sxpinfo (gc, type, mark, named/refcnt) + attribut + payload.
    """
    _id_counter = 0x7fff0000

    def __init__(self, r_type: Tuple[str, int], data: List[Any], alt_rep: bool = False):
        SEXPVector._id_counter += 0x20
        self.address = hex(SEXPVector._id_counter)
        self.r_type, self.elem_size = r_type
        self.alt_rep = alt_rep
        self.refcnt = 1
        self.attributes = {}
        
        if self.alt_rep:
            # ALTREP: hanya menyimpan batas (start, step, length)
            self._alt_start = data[0] if len(data) > 0 else 0
            self._alt_step = 1
            self._alt_len = len(data)
            self._data = None  # Belum diexpand ke memory
        else:
            self._data = list(data)

    @property
    def length(self) -> int:
        return self._alt_len if self.alt_rep else len(self._data)

    def materialize(self) -> List[Any]:
        if self.alt_rep and self._data is None:
            self._data = [self._alt_start + i * self._alt_step for i in range(self._alt_len)]
        return self._data

    def memory_footprint_bytes(self) -> int:
        header_size = 48  # sxpinfo_struct overhead di 64-bit R (~48 bytes)
        if self.alt_rep:
            # Metadata class descriptor + metadata pointer (~64 bytes fixed)
            return header_size + 64
        else:
            return header_size + (self.length * self.elem_size)


class REnvironment:
    """Simulasi Environment R dan mekanika Copy-on-Modify."""
    def __init__(self):
        self.bindings = {}

    def assign(self, symbol: str, sexp: SEXPVector):
        self.bindings[symbol] = sexp

    def copy_symbol(self, src: str, dest: str):
        target = self.bindings[src]
        target.refcnt += 1
        self.bindings[dest] = target

    def modify_element(self, symbol: str, idx: int, new_val: Any) -> Tuple[bool, str]:
        sexp = self.bindings[symbol]
        prev_addr = sexp.address
        
        # Aturan Copy-on-Modify: jika refcnt > 1 atau ALTREP, lakukan kloning (duplikasi)
        if sexp.refcnt > 1 or sexp.alt_rep:
            data = sexp.materialize()
            new_data = list(data)
            new_data[idx] = new_val
            
            # Buat SEXP baru (duplikasi memori)
            new_sexp = SEXPVector((sexp.r_type, sexp.elem_size), new_data, alt_rep=False)
            new_sexp.refcnt = 1
            sexp.refcnt -= 1
            self.bindings[symbol] = new_sexp
            return (True, f"{CLR_RED}[COPY TRIGGERED]{CLR_RESET} Alamat berubah: {prev_addr} -> {new_sexp.address} (CoM)")
        else:
            # In-place modification jika refcnt == 1 dan bukan ALTREP
            sexp.materialize()[idx] = new_val
            return (False, f"{CLR_GREEN}[IN-PLACE]{CLR_RESET} Alamat tetap: {prev_addr} (refcnt = 1)")


def demo_sexp_memory():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}--- MODUL 1: Anatomi SEXP & Tipe Data Dasar ---{CLR_RESET}")
    print("Setiap objek di R diimplementasikan sebagai pointer ke struktur C `SEXPREC`.")
    print("Struktur ini memiliki header metadata (`sxpinfo_struct`) sebesar ~48 byte pada sistem 64-bit.\n")

    types_to_test = [
        (RAtomicType.LGLSXP, [True, False, True, True], "logical"),
        (RAtomicType.INTSXP, [10, 20, 30, 40], "integer"),
        (RAtomicType.REALSXP, [3.14, 2.71, 1.41, 1.73], "double"),
        (RAtomicType.CPLXSXP, [complex(1, 2), complex(3, 4)], "complex"),
        (RAtomicType.STRSXP, ["data", "science", "r-lang"], "character"),
        (RAtomicType.RAWSXP, [0x00, 0xFF, 0x7E], "raw")
    ]

    print(f"{'Tipe R (SEXP Type)':<25} | {'Panjang':<8} | {'Ukuran/Elemen':<14} | {'Total Memori Internal':<20}")
    print("-" * 75)
    for t_def, sample, name in types_to_test:
        sexp = SEXPVector(t_def, sample)
        mem = sexp.memory_footprint_bytes()
        print(f"{sexp.r_type:<25} | {sexp.length:<8} | {sexp.elem_size:>2} bytes       | {mem:>5} bytes (48B hdr + data)")


def demo_copy_on_modify():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}--- MODUL 2: Copy-on-Modify & Reference Counting (NAMED) ---{CLR_RESET}")
    print("Di R, objek bersifat immutable secara semantik. Kloning memori hanya dilakukan")
    print("saat modifikasi dipicu pada objek yang memiliki lebih dari satu referensi (refcnt > 1).\n")

    env = REnvironment()
    x_vec = SEXPVector(RAtomicType.INTSXP, [100, 200, 300, 400])
    env.assign("x", x_vec)

    print(f"{CLR_CYAN}Langkah 1:{CLR_RESET} x <- c(100L, 200L, 300L, 400L)")
    print(f" -> x memori: {env.bindings['x'].address}, refcnt: {env.bindings['x'].refcnt}")

    print(f"\n{CLR_CYAN}Langkah 2:{CLR_RESET} y <- x  (Aliasing tanpa duplikasi memori)")
    env.copy_symbol("x", "y")
    print(f" -> x memori: {env.bindings['x'].address}, refcnt: {env.bindings['x'].refcnt}")
    print(f" -> y memori: {env.bindings['y'].address}, refcnt: {env.bindings['y'].refcnt}")
    print(f" -> Status: {CLR_YELLOW}Pointer x dan y identik (Shared memory, O(1) allocation){CLR_RESET}")

    print(f"\n{CLR_CYAN}Langkah 3:{CLR_RESET} y[2] <- 999L  (Mutasi pada y memicu CoM)")
    copied, msg = env.modify_element("y", 1, 999)
    print(f" -> {msg}")
    print(f" -> x data: {env.bindings['x'].materialize()}, addr: {env.bindings['x'].address}, refcnt: {env.bindings['x'].refcnt}")
    print(f" -> y data: {env.bindings['y'].materialize()}, addr: {env.bindings['y'].address}, refcnt: {env.bindings['y'].refcnt}")

    print(f"\n{CLR_CYAN}Langkah 4:{CLR_RESET} y[2] <- 888L  (Mutasi lanjutan saat refcnt == 1)")
    copied, msg = env.modify_element("y", 1, 888)
    print(f" -> {msg}")
    print(f" -> y data: {env.bindings['y'].materialize()}, addr: {env.bindings['y'].address}, refcnt: {env.bindings['y'].refcnt}")


def demo_altrep():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}--- MODUL 3: ALTREP (Alternative Representation) di R >= 3.5.0 ---{CLR_RESET}")
    print("ALTREP memungkinkan vektor masif seperti `1:1e8` dialokasikan secara O(1) memori")
    print("tanpa mem-materialisasi array integer 400MB sebelum benar-benar dibutuhkan.\n")

    n = 10_000_000
    altrep_vec = SEXPVector(RAtomicType.INTSXP, list(range(n)), alt_rep=True)
    classic_size = 48 + (n * 4)
    altrep_size = altrep_vec.memory_footprint_bytes()

    print(f"Target Sequence: {CLR_BOLD}x <- 1:{n:,}L{CLR_RESET}")
    print(f" -> Ukuran jika dialokasikan utuh (Standard INTSXP) : {CLR_RED}{classic_size / (1024*1024):.2f} MB{CLR_RESET}")
    print(f" -> Ukuran dengan ALTREP (Compact sequence)         : {CLR_GREEN}{altrep_size} bytes (O(1)){CLR_RESET}")
    print(f" -> Rasio Penghematan RAM                          : {CLR_YELLOW}{(classic_size / altrep_size):,.1f}x lebih hemat{CLR_RESET}")


def demo_vector_recycling():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}--- MODUL 4: Vectorization & Vector Recycling Rule ---{CLR_RESET}")
    print("Ketika operasi biner dijalankan pada dua vektor dengan panjang berbeda, R mendaur ulang")
    print("(recycle) elemen vektor yang lebih pendek. Jika bukan kelipatan utuh, peringatan dipicu.\n")

    def r_recycle_add(v1: List[float], v2: List[float]) -> Tuple[List[float], Optional[str]]:
        l1, l2 = len(v1), len(v2)
        target_len = max(l1, l2)
        warning = None

        if target_len % min(l1, l2) != 0:
            warning = f"Warning message: longer object length is not a multiple of shorter object length"

        res = []
        for i in range(target_len):
            val1 = v1[i % l1]
            val2 = v2[i % l2]
            res.append(val1 + val2)
        return res, warning

    scenarios = [
        ([1, 2, 3, 4, 5, 6], [10, 20]),
        ([1, 2, 3, 4, 5], [10, 20])
    ]

    for v1, v2 in scenarios:
        res, warn = r_recycle_add(v1, v2)
        print(f"Vektor A: {v1}")
        print(f"Vektor B: {v2}")
        print(f"A + B   : {CLR_BOLD}{res}{CLR_RESET}")
        if warn:
            print(f"{CLR_RED} -> {warn}{CLR_RESET}")
        else:
            print(f"{CLR_GREEN} -> Sempurna (Kelipatan utuh, tidak ada warning){CLR_RESET}")
        print("-" * 50)


def interactive_sandbox():
    print(f"\n{CLR_CYAN}{CLR_BOLD}--- INTERACTIVE RECYCLING & TYPE CALCULATOR ---{CLR_RESET}")
    try:
        raw_a = input("Masukkan elemen vektor A (pisahkan koma, cth: 1, 2, 3, 4): ").strip()
        raw_b = input("Masukkan elemen vektor B (pisahkan koma, cth: 10, 20): ").strip()
        
        va = [float(x.strip()) for x in raw_a.split(",") if x.strip()]
        vb = [float(x.strip()) for x in raw_b.split(",") if x.strip()]
        
        if not va or not vb:
            print(f"{CLR_RED}Vektor tidak boleh kosong.{CLR_RESET}")
            return

        l1, l2 = len(va), len(vb)
        target = max(l1, l2)
        res = []
        for i in range(target):
            res.append(va[i % l1] + vb[i % l2])

        print(f"\n{CLR_GREEN}Hasil Vektorisasi Element-wise:{CLR_RESET} {res}")
        if target % min(l1, l2) != 0:
            print(f"{CLR_RED}Warning: longer object length ({target}) is not a multiple of shorter object length ({min(l1, l2)}){CLR_RESET}")
        else:
            print(f"{CLR_BLUE}Recycling harmonis tanpa sisa (Multiple matched).{CLR_RESET}")

    except Exception as e:
        print(f"{CLR_RED}Error input: {e}{CLR_RESET}")


def main():
    print_banner()
    demo_sexp_memory()
    demo_copy_on_modify()
    demo_altrep()
    demo_vector_recycling()

    print(f"\n{CLR_BOLD}Jalankan mode interaktif? (y/N): {CLR_RESET}", end="")
    try:
        # Non-blocking / non-interactive safe check
        if sys.stdin.isatty():
            ans = input().strip().lower()
            if ans == "y":
                interactive_sandbox()
        else:
            print("Auto-skip (headless environment).")
    except EOFError:
        pass

    print(f"\n{CLR_GREEN}{CLR_BOLD}Simulasi selesai. Laboratorium teknis siap diverifikasi!{CLR_RESET}\n")


if __name__ == "__main__":
    main()
