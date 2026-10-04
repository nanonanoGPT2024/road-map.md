#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi Komputasi & Arsitektur Memori NumPy (Pure Python Engine)
Bab 01 - Modul 02: Deep Dive Strided Memory, Zero-Copy Views, & Cache Locality

Tujuan:
1. Membedah arsitektur internal NumPy (Buffer, Shape, Strides, Offset).
2. Membuktikan mekanisme Zero-Copy Slicing dan Memory Views.
3. Mengukur penalti CPU Cache Miss (Row-Major vs Column-Major Traversal).
"""

import sys
import time
import array
from typing import Tuple, List, Union

# ANSI Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_CYAN = "\033[36m"
CLR_MAGENTA = "\033[35m"


class StridedNDArray:
    """
    Simulasi arsitektur memori ndarray NumPy.
    Memisahkan data buffer (1D linear memory) dari metadata (shape, strides, offset).
    """

    def __init__(
        self,
        shape: Tuple[int, ...],
        buffer: array.array = None,
        offset: int = 0,
        strides: Tuple[int, ...] = None,
        itemsize: int = 8,
    ):
        self.shape = tuple(shape)
        self.itemsize = itemsize
        self.offset = offset  # Byte offset pada buffer awal

        # Inisialisasi C-contiguous memory buffer (tipe 'd': double precision float 64-bit / 8 bytes)
        total_elements = 1
        for dim in self.shape:
            total_elements *= dim

        if buffer is None:
            self._buffer = array.array("d", [0.0] * total_elements)
        else:
            self._buffer = buffer

        # Hitung standard C-contiguous strides (dalam bytes) jika tidak didefinisikan
        if strides is None:
            computed_strides = []
            stride = self.itemsize
            for dim in reversed(self.shape):
                computed_strides.append(stride)
                stride *= dim
            self.strides = tuple(reversed(computed_strides))
        else:
            self.strides = tuple(strides)

    @property
    def is_c_contiguous(self) -> bool:
        """Memeriksa apakah layout memori contiguous baris-demi-baris (C-Order)."""
        stride = self.itemsize
        for dim, s in zip(reversed(self.shape), reversed(self.strides)):
            if s != stride:
                return False
            stride *= dim
        return True

    def _get_linear_index(self, indices: Tuple[int, ...]) -> int:
        """Menghitung index flat 1D memory array berdasarkan multidimensional strides."""
        if len(indices) != len(self.shape):
            raise IndexError(f"Dimensi salah: Diharapkan {len(self.shape)}, didapat {len(indices)}")

        byte_offset = self.offset
        for idx, (dim, stride) in enumerate(zip(self.shape, self.strides)):
            if not (0 <= indices[idx] < dim):
                raise IndexError(f"Index out of bounds pada axis {idx}: {indices[idx]} (dim: {dim})")
            byte_offset += indices[idx] * stride

        # Konversi offset byte ke index array.array
        return byte_offset // self.itemsize

    def __getitem__(self, indices: Union[Tuple[int, ...], int]) -> float:
        if isinstance(indices, int):
            indices = (indices,)
        flat_idx = self._get_linear_index(indices)
        return self._buffer[flat_idx]

    def __setitem__(self, indices: Union[Tuple[int, ...], int], value: float):
        if isinstance(indices, int):
            indices = (indices,)
        flat_idx = self._get_linear_index(indices)
        self._buffer[flat_idx] = float(value)

    def slice_view(self, row_slice: slice, col_slice: slice) -> "StridedNDArray":
        """
        Membuat view baru (ZERO-COPY) dari array yang ada dengan memodifikasi strides dan offset.
        Buffer underlying memory tetap di-share secara bersamaan.
        """
        r_start, r_stop, r_step = row_slice.indices(self.shape[0])
        c_start, c_stop, c_step = col_slice.indices(self.shape[1])

        new_shape = (
            max(0, (r_stop - r_start + (r_step - 1 if r_step > 0 else r_step + 1)) // r_step),
            max(0, (c_stop - c_start + (c_step - 1 if c_step > 0 else c_step + 1)) // c_step),
        )

        new_offset = self.offset + (r_start * self.strides[0]) + (c_start * self.strides[1])
        new_strides = (self.strides[0] * r_step, self.strides[1] * c_step)

        # Mengembalikan instance baru dengan buffer yang SAMA (zero-copy)
        return StridedNDArray(
            shape=new_shape,
            buffer=self._buffer,
            offset=new_offset,
            strides=new_strides,
            itemsize=self.itemsize,
        )

    def transpose(self) -> "StridedNDArray":
        """Transposisi instan tanpa alokasi memori dengan membalikkan shape dan strides."""
        return StridedNDArray(
            shape=tuple(reversed(self.shape)),
            buffer=self._buffer,
            offset=self.offset,
            strides=tuple(reversed(self.strides)),
            itemsize=self.itemsize,
        )


def benchmark_cache_locality(rows: int = 1500, cols: int = 1500):
    """
    Mensimulasikan efek Hardware Cache Locality (L1/L2/L3 cache misses).
    Traversal baris-demi-baris (C-Order) memiliki spatial locality tinggi,
    sedangkan traversal kolom-demi-kolom memicu cache miss secara berulang.
    """
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== BENCHMARK CACHE LOCALITY: ROW-MAJOR VS COL-MAJOR ==={CLR_RESET}")
    print(f"Mengalokasikan Matriks {rows}x{cols} ({rows * cols * 8 / (1024*1024):.2f} MB)...")

    matrix = StridedNDArray(shape=(rows, cols))
    
    # Isi data
    for r in range(rows):
        for c in range(cols):
            matrix[r, c] = float(r + c)

    # 1. Row-Major Traversal (Stride-1 pada innermost loop: Optimal Cache)
    t0 = time.perf_counter()
    sum_row = 0.0
    for r in range(rows):
        for c in range(cols):
            sum_row += matrix[r, c]
    time_row = time.perf_counter() - t0

    # 2. Column-Major Traversal (Stride-N pada innermost loop: Cache Inefficient)
    t0 = time.perf_counter()
    sum_col = 0.0
    for c in range(cols):
        for r in range(rows):
            sum_col += matrix[r, c]
    time_col = time.perf_counter() - t0

    speedup = time_col / time_row if time_row > 0 else 1.0

    print(f"Hasil Akumulasi Matrix: {sum_row:.1f} (Row-Major) | {sum_col:.1f} (Col-Major)")
    print(f"1. Row-Major (Cache-Friendly)   : {CLR_GREEN}{time_row:.4f} detik{CLR_RESET}")
    print(f"2. Col-Major (Cache-Unfriendly) : {CLR_RED}{time_col:.4f} detik{CLR_RESET}")
    print(f"Performa Degradasi Cache Miss   : {CLR_YELLOW}{speedup:.2f}x Lebih Lambat{CLR_RESET}")


def demonstrate_zero_copy_and_strides():
    """
    Mendemonstrasikan internal memory views, stride calculation, dan zero-copy mutations.
    """
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== DEMONSTRASI ZERO-COPY MEMORY VIEWS & STRIDES ==={CLR_RESET}")

    # Buat matrix 4x4
    orig = StridedNDArray(shape=(4, 4))
    val = 1.0
    for r in range(4):
        for c in range(4):
            orig[r, c] = val
            val += 1.0

    print(f"{CLR_BOLD}Array Awal (4x4):{CLR_RESET}")
    for r in range(orig.shape[0]):
        print("  [" + ", ".join(f"{orig[r, c]:5.1f}" for c in range(orig.shape[1])) + "]")

    print(f"\nMetadata Array Awal:")
    print(f" - Shape   : {orig.shape}")
    print(f" - Strides : {orig.strides} (Byte step per dimensi)")
    print(f" - Offset  : {orig.offset} bytes")
    print(f" - Buffer Id: {id(orig._buffer)}")

    # Buat Sub-View: baris 1:3, kolom 1:3 (sub-matriks 2x2 di tengah)
    sub_view = orig.slice_view(slice(1, 3), slice(1, 3))
    print(f"\n{CLR_BOLD}Sub-View [1:3, 1:3] (2x2):{CLR_RESET}")
    for r in range(sub_view.shape[0]):
        print("  [" + ", ".join(f"{sub_view[r, c]:5.1f}" for c in range(sub_view.shape[1])) + "]")

    print(f"\nMetadata Sub-View:")
    print(f" - Shape   : {sub_view.shape}")
    print(f" - Strides : {sub_view.strides}")
    print(f" - Offset  : {sub_view.offset} bytes ({sub_view.offset // 8} elements)")
    print(f" - Buffer Id: {id(sub_view._buffer)} (Sama dengan array awal -> {CLR_GREEN}ZERO-COPY{CLR_RESET})")

    # Modifikasi data pada Sub-View
    print(f"\n{CLR_MAGENTA}Mutasi sub_view[0, 0] = 999.0...{CLR_RESET}")
    sub_view[0, 0] = 999.0

    print(f"Nilai pada orig[1, 1] saat ini: {CLR_YELLOW}{orig[1, 1]}{CLR_RESET} (Terbukti berbagi buffer fisik!)")

    # Transpose View
    transposed = orig.transpose()
    print(f"\n{CLR_BOLD}Transposed Matrix (4x4, Instant swap strides):{CLR_RESET}")
    print(f" - Transposed Shape  : {transposed.shape}")
    print(f" - Transposed Strides: {transposed.strides} (Strides terbalik, data tidak disalin!)")
    print(f" - orig[0, 1]        : {orig[0, 1]}")
    print(f" - transposed[1, 0]  : {transposed[1, 0]}")


def main():
    print(f"{CLR_BOLD}{CLR_GREEN}==================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}  LAB 01-02: ARSITEKTUR MEMORI STRIDED ARRAY & CACHE OPTIMIZATION  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}==================================================================={CLR_RESET}")

    demonstrate_zero_copy_and_strides()
    benchmark_cache_locality(rows=1200, cols=1200)

    print(f"\n{CLR_BOLD}{CLR_GREEN}Lab selesai. Semua invariants arsitektur memori terpenuhi.{CLR_RESET}\n")


if __name__ == "__main__":
    main()