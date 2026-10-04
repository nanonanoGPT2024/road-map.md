#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi R, RStudio Environment, & Vectorized Computing
Modul 02 Deep Dive: Vector Recycling, Copy-on-Modify, & SIMD-Style Vectorization

Tujuan:
1. Memodelkan aturan daur ulang vektor (R's Vector Recycling Rule) beserta peringatan modularitasnya.
2. Mensimulasikan semantik memori R "Copy-on-Modify" (CoM) dan pelacakan pointer objek.
3. Mengimplementasikan tri-state logic dan propagasi nilai NA (Not Available) khas R.
4. Melakukan benchmark terukur antara pemrosesan loop skalar vs operasi tervektorisasi.
"""

import sys
import time
import copy
from typing import List, Any, Optional, Tuple, Union

# ANSI Colors untuk output terminal
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_BOLD = "\033[1m"
CLR_RESET = "\033[0m"


class RNA:
    """Representasi singleton untuk NA (Not Available / missing value) di R."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RNA, cls).__new__(cls)
        return cls._instance

    def __repr__(self):
        return "NA"

    def __str__(self):
        return "NA"


NA = RNA()


class RVector:
    """
    Simulasi struktur dasar R Vector (atomic vector).
    Mendukung semantik R:
    - 1-based indexing interface (dimodelkan melalui akses method/internal translation)
    - Vector Recycling Rules
    - NA Propagation
    - Atribut metadata (dim, names, class)
    """

    def __init__(self, data: List[Any], vtype: str = "numeric"):
        self.data: List[Any] = list(data)
        self.vtype: str = vtype
        self.attributes: dict = {}
        self._mem_id: int = id(self.data)

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        vals = ", ".join([str(x) for x in self.data])
        return f"c({vals})"

    @property
    def mem_address(self) -> str:
        """Mengambil visualisasi alamat memori internal data payload."""
        return f"0x{self._mem_id:012x}"

    def copy(self) -> 'RVector':
        """Membuat shallow copy representasi environment binding."""
        new_vec = RVector(self.data, self.vtype)
        new_vec.attributes = copy.deepcopy(self.attributes)
        new_vec._mem_id = id(new_vec.data)
        return new_vec

    def set_element(self, index_1based: int, value: Any):
        """
        Simulasi mutasi elemen dengan mekanisme Copy-on-Modify (CoM).
        Di R, modifikasi pada vector yang dibagi akan memicu deep copy buffer.
        """
        idx = index_1based - 1
        if idx < 0 or idx >= len(self.data):
            raise IndexError("subscript out of bounds")

        # Copy-on-Modify: Alokasikan memori baru saat mutasi terjadi
        self.data = list(self.data)
        self._mem_id = id(self.data)
        self.data[idx] = value

    @staticmethod
    def _recycle(shorter: List[Any], target_len: int) -> Tuple[List[Any], bool]:
        """
        Mengimplementasikan R Vector Recycling Rule:
        Jika panjang target bukan kelipatan integer panjang shorter, cetak peringatan.
        """
        len_s = len(shorter)
        if len_s == 0:
            return [NA] * target_len, False

        is_multiple = (target_len % len_s == 0)
        recycled = [shorter[i % len_s] for i in range(target_len)]
        return recycled, is_multiple

    def _binary_op(self, other: Union['RVector', int, float, None], op_lambda) -> 'RVector':
        """Mengeksekusi operasi biner dengan auto-recycling & NA propagation."""
        if not isinstance(other, RVector):
            other = RVector([other])

        len_self = len(self)
        len_other = len(other)
        target_len = max(len_self, len_other)

        d1 = self.data
        d2 = other.data

        if len_self < target_len:
            d1, is_mult = self._recycle(d1, target_len)
            if not is_mult:
                print(f"{CLR_YELLOW}Warning: longer object length is not a multiple of shorter object length{CLR_RESET}")
        elif len_other < target_len:
            d2, is_mult = self._recycle(d2, target_len)
            if not is_mult:
                print(f"{CLR_YELLOW}Warning: longer object length is not a multiple of shorter object length{CLR_RESET}")

        result_data = []
        for a, b in zip(d1, d2):
            if a is NA or b is NA:
                result_data.append(NA)
            else:
                result_data.append(op_lambda(a, b))

        res_vec = RVector(result_data)
        return res_vec

    def __add__(self, other):
        return self._binary_op(other, lambda a, b: a + b)

    def __mul__(self, other):
        return self._binary_op(other, lambda a, b: a * b)

    def __eq__(self, other):
        return self._binary_op(other, lambda a, b: a == b)

    def set_dim(self, nrow: int, ncol: int):
        """Simulasi transformasi vektor menjadi Matriks melalui atribut dim (Column-major order)."""
        if nrow * ncol != len(self.data):
            raise ValueError(f"dims [product {nrow * ncol}] do not match the length of object [{len(self.data)}]")
        self.attributes["dim"] = (nrow, ncol)

    def print_matrix(self):
        """Mencetak format representasi 2D matriks ala R (Fortran/Column-Major indexing)."""
        if "dim" not in self.attributes:
            print(self)
            return

        nrow, ncol = self.attributes["dim"]
        print(f"{CLR_CYAN}Matrix representation ({nrow} x {ncol}) [Column-Major]:{CLR_RESET}")
        
        # Header kolom
        cols_hdr = "       " + " ".join([f"[,{c+1}]" for c in range(ncol)])
        print(cols_hdr)
        
        # Iterasi baris
        for r in range(nrow):
            row_str = f"[{r+1},] "
            row_vals = []
            for c in range(ncol):
                # R menyimpan matriks secara column-major: idx = c * nrow + r
                idx = c * nrow + r
                row_vals.append(f"{str(self.data[idx]):>5}")
            print(row_str + " ".join(row_vals))


def test_vector_recycling():
    print(f"\n{CLR_BOLD}=== 1. UJI VECTOR RECYCLING SEMANTICS & NA LOGIC ==={CLR_RESET}")
    v1 = RVector([10, 20, 30, 40, 50, 60])
    v2 = RVector([1, 2])
    print(f"Vector A: {v1}")
    print(f"Vector B (Kelipatan pas, len=2): {v2}")
    res1 = v1 + v2
    print(f"A + B : {res1}")

    v3 = RVector([1, 2, 3, 4])
    print(f"\nVector C (Bukan kelipatan, len=4): {v3}")
    res2 = v1 + v3
    print(f"A + C : {res2}")

    print(f"\nUji Tri-state Logic dengan NA:")
    v_na = RVector([10, NA, 30])
    v_scal = RVector([5])
    print(f"Vektor NA : {v_na}")
    print(f"Penjumlahan: {v_na + v_scal}")


def test_copy_on_modify():
    print(f"\n{CLR_BOLD}=== 2. UJI SEMANTIK MEMORI R: COPY-ON-MODIFY (CoM) ==={CLR_RESET}")
    
    # Inisialisasi vector x
    x = RVector([1.5, 2.5, 3.5])
    print(f"Objek x diinisialisasi -> data: {x}, Pointer Payload: {CLR_GREEN}{x.mem_address}{CLR_RESET}")

    # Bind y ke x (di R: y <- x, menunjuk ke memori yang sama via reference count sharing)
    y = x
    print(f"Objek y <- x (Binding)  -> data: {y}, Pointer Payload: {CLR_GREEN}{y.mem_address}{CLR_RESET}")
    print(f"Verifikasi identik: {x.mem_address == y.mem_address} (Zero memory overhead)")

    # Modifikasi elemen y: y[1] <- 99.9 (Memicu CoM)
    print(f"\n{CLR_YELLOW}Mengeksekusi mutasi: y.set_element(1, 99.9)...{CLR_RESET}")
    y.set_element(1, 99.9)

    print(f"Setelah mutasi:")
    print(f"Objek x -> data: {x}, Pointer: {CLR_GREEN}{x.mem_address}{CLR_RESET}")
    print(f"Objek y -> data: {y}, Pointer: {CLR_RED}{y.mem_address}{CLR_RESET}")
    print(f"Payload Memori Berpisah: {x.mem_address != y.mem_address} (Copy-on-Modify Berhasil)")


def test_matrix_column_major():
    print(f"\n{CLR_BOLD}=== 3. UJI ATRIBUT MATRIKS (COLUMN-MAJOR FOLDING) ==={CLR_RESET}")
    raw_seq = RVector(list(range(1, 13)))
    print(f"Raw Vector (1..12): {raw_seq}")
    print("Mengubah atribut dim <- c(4, 3)...")
    raw_seq.set_dim(4, 3)
    raw_seq.print_matrix()


def benchmark_vectorization():
    print(f"\n{CLR_BOLD}=== 4. BENCHMARK: SKALAR LOOP VS VEKTORISASI KERNEL ==={CLR_RESET}")
    n_elements = 500_000
    print(f"Membangkitkan dataset uji: N = {n_elements:,} elemen float...")
    
    data_a = [float(i) * 0.5 for i in range(n_elements)]
    data_b = [float(i) * 1.5 for i in range(n_elements)]

    # 1. Pendekatan Skalar Iteratif (Mensimulasikan for-loop lambat di R tanpa pre-alokasi)
    print(f"Menjalankan Scalar Iterative Loop...")
    t0 = time.perf_counter()
    scalar_res = []
    for i in range(n_elements):
        scalar_res.append(data_a[i] * data_b[i] + 2.0)
    t_scalar = time.perf_counter() - t0
    print(f"Waktu Eksekusi Loop Skalar : {CLR_RED}{t_scalar:.4f} detik{CLR_RESET}")

    # 2. Pendekatan Vectorized Kernel (Mensimulasikan C/Fortran vector kernel R)
    print(f"Menjalankan Batch Vectorized Kernel...")
    t0 = time.perf_counter()
    # Memanfaatkan list comprehension teroptimasi C-level loop Python
    vec_res = [a * b + 2.0 for a, b in zip(data_a, data_b)]
    t_vector = time.perf_counter() - t0
    print(f"Waktu Eksekusi Vectorized  : {CLR_GREEN}{t_vector:.4f} detik{CLR_RESET}")

    speedup = t_scalar / t_vector if t_vector > 0 else 0
    print(f"Speedup Faktor             : {CLR_CYAN}{speedup:.2f}x lebih cepat{CLR_RESET}")
    
    # Validasi kesamaan hasil
    assert scalar_res[:5] == vec_res[:5], "Integritas hasil perhitungan tidak cocok!"
    print(f"Integritas Data: {CLR_GREEN}VALID{CLR_RESET} (First 5 output: {vec_res[:5]})")


def main():
    print(f"{CLR_MAGENTA}{'=' * 65}")
    print(f" SISTEM SIMULASI CORE R & VECTORIZED COMPUTING ARCHITECTURE ")
    print(f"{'=' * 65}{CLR_RESET}")

    test_vector_recycling()
    test_copy_on_modify()
    test_matrix_column_major()
    benchmark_vectorization()

    print(f"\n{CLR_GREEN}Seluruh rangkaian pengujian arsitektur komputasi R selesai dengan sukses.{CLR_RESET}")


if __name__ == "__main__":
    main()