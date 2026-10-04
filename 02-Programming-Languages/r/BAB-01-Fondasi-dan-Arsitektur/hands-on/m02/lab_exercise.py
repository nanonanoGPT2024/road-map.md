#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi Sistem & Arsitektur Runtime R
Modul: 02 - Deep Dive: SEXP, Copy-on-Modify, Promise Objects, dan Envs
Deskripsi:
  Script mandiri ini memodelkan arsitektur internal runtime GNU R (C-level internals):
  1. Struktur SEXP (S-Expression Pointer) & Tag Header.
  2. Semantik 'Copy-on-Modify' (CoW) menggunakan pelacakan Reference Count (REFCNT).
  3. Mekanisme Lazy Evaluation via PROMSXP (Promise Objects: expr, env, value).
  4. Rangkaian Environment Lexical (ENVSXP) untuk scope lookup resolution.
"""

from __future__ import annotations
import sys
import time
import copy
from enum import Enum, auto
from typing import Any, Callable, Dict, Optional, List

# --- ANSI Formatting Constants ---
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    CYAN    = "\033[36m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    RED     = "\033[31m"
    MAGENTA = "\033[35m"
    DIM     = "\033[2m"

# --- R Runtime Type Definitions (SEXPTYPE) ---
class SEXPTYPE(Enum):
    NILSXP  = auto()  # NULL
    INTSXP  = auto()  # Integer Vector
    REALSXP = auto()  # Numeric Vector (double)
    VECSXP  = auto()  # Generic List
    ENVSXP  = auto()  # Environment
    PROMSXP = auto()  # Promise Object

class MemoryManager:
    """Simulasi R Vector Heap & Node Allocator."""
    def __init__(self):
        self._next_addr = 0x7FFF0000
        self.allocated_nodes: int = 0
        self.total_duplications: int = 0

    def allocate_address(self) -> str:
        addr = f"0x{self._next_addr:08X}"
        self._next_addr += 0x00000040
        self.allocated_nodes += 1
        return addr

MM = MemoryManager()

# --- SEXP Core Modeling ---
class SEXP:
    """
    Representasi dari struct SEXPREC (GNU R C source).
    Setiap objek R di-wrap dalam pointer SEXP dengan metadata header.
    """
    def __init__(self, type_: SEXPTYPE, data: Any):
        self.address: str = MM.allocate_address()
        self.type: SEXPTYPE = type_
        self.data: Any = data
        # Di R 3.1.0+, NAMED diganti dengan refcnt yang lebih akurat
        self.refcnt: int = 1

    def retain(self) -> SEXP:
        """Menambah counter referensi saat di-bind ke simbol baru."""
        self.refcnt += 1
        return self

    def release(self):
        """Mengurangi counter referensi saat simbol keluar dari scope."""
        if self.refcnt > 0:
            self.refcnt -= 1

    def duplicate(self) -> SEXP:
        """
        Emulasi fungsi duplicate() di C-level R.
        Melakukan deep copy dan mengalokasikan memori baru di heap.
        """
        MM.total_duplications += 1
        new_data = copy.deepcopy(self.data)
        new_sexp = SEXP(self.type, new_data)
        new_sexp.refcnt = 1
        return new_sexp

    def __repr__(self) -> str:
        return f"<{self.type.name} @ {self.address} | REFCNT={self.refcnt} | Val={self.data}>"

# --- Environment Modeling (ENVSXP) ---
class Environment:
    """
    Representasi dari ENVSXP.
    Terdiri dari frame (symbol-value map) dan pointer ke parent environment (enclos).
    """
    def __init__(self, name: str, parent: Optional[Environment] = None):
        self.name: str = name
        self.parent: Optional[Environment] = parent
        self.frame: Dict[str, SEXP] = {}
        self.address: str = MM.allocate_address()

    def assign(self, symbol: str, val: SEXP):
        """Membuat binding symbol -> SEXP."""
        if symbol in self.frame:
            self.frame[symbol].release()
        self.frame[symbol] = val.retain()

    def get(self, symbol: str) -> Optional[SEXP]:
        """Pencarian leksikal menelusuri rantai parent environment."""
        curr = self
        while curr:
            if symbol in curr.frame:
                return curr.frame[symbol]
            curr = curr.parent
        return None

# --- Promise Modeling (PROMSXP) ---
class Promise:
    """
    Representasi PROMSXP untuk Lazy Evaluation R.
    - PRCODE: Kode/ekspresi yang belum dievaluasi (AST).
    - PRENV: Environment di mana ekspresi tersebut dipanggil.
    - PRVALUE: Cache hasil evaluasi (NULL sampai dievaluasi pertama kali).
    """
    def __init__(self, expr_fn: Callable[[], Any], env: Environment, expr_str: str):
        self.expr_fn: Callable[[], Any] = expr_fn
        self.env: Environment = env
        self.expr_str: str = expr_str
        self.prvalue: Optional[SEXP] = None
        self.evaluated: bool = False
        self.address: str = MM.allocate_address()

    def eval(self) -> SEXP:
        """Memaksa evaluasi (forcing the promise). Memoized setelah run pertama."""
        if not self.evaluated:
            print(f"    {Color.YELLOW}[PROMSXP Forced]{Color.RESET} Mengevaluasi '{self.expr_str}' di {self.env.name}...")
            raw_res = self.expr_fn()
            # Wrap Python result to SEXP
            if isinstance(raw_res, list):
                self.prvalue = SEXP(SEXPTYPE.INTSXP, raw_res)
            elif isinstance(raw_res, (int, float)):
                self.prvalue = SEXP(SEXPTYPE.REALSXP, [raw_res])
            else:
                self.prvalue = SEXP(SEXPTYPE.VECSXP, [raw_res])
            self.evaluated = True
        else:
            print(f"    {Color.DIM}[PROMSXP Cache Hit]{Color.RESET} Mengambil nilai dari cache memoized.")
        return self.prvalue

# --- Engine Core Operations ---
def r_modify_vector(vec: SEXP, index: int, new_val: Any) -> SEXP:
    """
    Mensimulasikan semantik Copy-on-Modify (CoW) runtime R.
    Jika REFCNT > 1, lakukan duplicate() sebelum mutasi.
    """
    print(f"  {Color.BOLD}-> Memeriksa status mutasi objek di {vec.address}...{Color.RESET}")
    if vec.refcnt > 1:
        print(f"    {Color.RED}[CoW Triggered]{Color.RESET} REFCNT = {vec.refcnt} (> 1). Memori diproteksi.")
        print(f"    {Color.RED}[C duplicate()]{Color.RESET} Mengalokasikan block SEXP baru...")
        # Kurangi refcnt lama
        vec.release()
        # Buat clone independen
        new_vec = vec.duplicate()
        new_vec.data[index] = new_val
        print(f"    {Color.GREEN}[Allocated]{Color.RESET} Objek baru dibuat di {new_vec.address} (REFCNT=1)")
        return new_vec
    else:
        print(f"    {Color.GREEN}[In-Place Mutation]{Color.RESET} REFCNT = {vec.refcnt} (== 1). Mutasi langsung di buffer asal.")
        vec.data[index] = new_val
        return vec

# --- Lab Demonstrasi ---
def main():
    print(f"{Color.CYAN}{Color.BOLD}======================================================================{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}   SIMULATOR INTERNAL RUNTIME R (SEXP, COW, PROMISES & ENVIRONMENTS)  {Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}======================================================================{Color.RESET}\n")

    # Inisialisasi Root Environment (R_GlobalEnv)
    global_env = Environment(name="R_GlobalEnv")
    print(f"{Color.BOLD}[1] Inisialisasi R_GlobalEnv @ {global_env.address}{Color.RESET}")

    # Step 1: Alokasi Vektor Asli (x <- c(10, 20, 30))
    print(f"\n{Color.BOLD}[2] Alokasi SEXP Awal: x <- c(10, 20, 30){Color.RESET}")
    x_val = SEXP(SEXPTYPE.INTSXP, [10, 20, 30])
    global_env.assign("x", x_val)
    print(f"  Binding 'x' -> {global_env.get('x')}")

    # Step 2: Shared Reference Binding (y <- x)
    print(f"\n{Color.BOLD}[3] Assignment Referensi: y <- x (Tanpa Duplikasi Alokasi){Color.RESET}")
    y_val = global_env.get("x")
    assert y_val is not None
    global_env.assign("y", y_val)
    print(f"  Binding 'x' -> {global_env.get('x')}")
    print(f"  Binding 'y' -> {global_env.get('y')}")
    print(f"  {Color.DIM}Verifikasi Memori: x dan y menunjuk ke alamat fisik yang sama!{Color.RESET}")

    # Step 3: Trigger Copy-on-Modify (y[1] <- 99)
    print(f"\n{Color.BOLD}[4] Operasi Mutasi: y[0] <- 99 (Demonstrasi Copy-on-Modify){Color.RESET}")
    mutated_y = r_modify_vector(global_env.get("y"), 0, 99)
    # Re-assign y ke hasil modifikasi
    global_env.frame["y"] = mutated_y

    print(f"\n  Kondisi Pasca-Mutasi:")
    print(f"  Symbol 'x': {global_env.get('x')} (Data utuh, alamat tetap)")
    print(f"  Symbol 'y': {global_env.get('y')} (Data termutasi di buffer baru)")

    # Step 4: Mutasi In-Place (REFCNT == 1)
    print(f"\n{Color.BOLD}[5] Mutasi Sekunder: y[1] <- 88 (REFCNT = 1){Color.RESET}")
    in_place_y = r_modify_vector(global_env.get("y"), 1, 88)
    global_env.frame["y"] = in_place_y
    print(f"  Symbol 'y': {global_env.get('y')} (Alamat tetap sama)")

    # Step 5: Lazy Evaluation via PROMSXP
    print(f"\n{Color.BOLD}[6] Simulasi PROMSXP (Lazy Evaluation pada Argumen Fungsi){Color.RESET}")
    
    # Fungsi tiruan: my_function(a, b) { if(TRUE) return(a) else return(b) }
    def expensive_computation():
        time.sleep(0.05)
        return [100, 200, 300]

    def failing_computation():
        raise RuntimeError("Evaluasi Gagal: Argumen ini tidak boleh dievaluasi!")

    # Buat promises untuk argumen
    prom_a = Promise(lambda: expensive_computation(), global_env, "expensive_computation()")
    prom_b = Promise(lambda: failing_computation(), global_env, "1 / 0 (failing)")

    print(f"  Promise 'a' terbuat: {prom_a.expr_str} @ {prom_a.address}")
    print(f"  Promise 'b' terbuat: {prom_b.expr_str} @ {prom_b.address}")
    print("  Memanggil fungsi simulasi: run_analysis(a, b) -> hanya membaca 'a'")

    # Evaluasi a (Lazy Triggered)
    result_a = prom_a.eval()
    print(f"  Hasil evaluasi 'a': {result_a}")
    
    # Evaluasi a kedua kali (Cache Verification)
    print("  Membaca 'a' kedua kalinya di dalam fungsi:")
    result_a_cached = prom_a.eval()
    print(f"  Hasil memoized 'a': {result_a_cached}")

    print(f"  {Color.GREEN}Argumen 'b' TIDAK PERNAH dievaluasi (Zero Overhead, No Crash).{Color.RESET}")

    # Summary Statistics
    print(f"\n{Color.CYAN}======================================================================{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}   METRIK RUNTIME R-ENGINE                                            {Color.RESET}")
    print(f"{Color.CYAN}======================================================================{Color.RESET}")
    print(f"  Total Alokasi Node SEXP       : {Color.BOLD}{MM.allocated_nodes}{Color.RESET}")
    print(f"  Total Operasi duplicate() CoW : {Color.BOLD}{MM.total_duplications}{Color.RESET}")
    print(f"  Status Memori Akhir           : Cleanly tracked, zero leaks simulated.")
    print(f"{Color.CYAN}======================================================================{Color.RESET}")

if __name__ == "__main__":
    main()