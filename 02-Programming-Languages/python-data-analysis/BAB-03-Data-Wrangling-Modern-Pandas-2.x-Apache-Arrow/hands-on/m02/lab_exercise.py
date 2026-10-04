#!/usr/bin/env python3
"""
Lab Hands-on: Modern Data Wrangling - Architecture Deep Dive
Topic: Pandas 2.x & Apache Arrow Memory Backend Simulation
Category: 02-Programming-Languages (Chapter 03, Module 02)

Deskripsi:
Script mandiri ini memodelkan perbedaan arsitektur internal antara:
1. Traditional Object-Pointer Model (NumPy/Pandas 1.x `object` dtype)
2. Contiguous Arrow Columnar Format (Pandas 2.x Arrow backend)

Fitur Simulasi Teknis:
- Memory Bitmaps: Null-tracking menggunakan 1-bit flags (Arrow validity mask).
- Contiguous Buffers: Offset array + Raw Data buffer untuk string variabel-lebar.
- Zero-Copy Slicing: Pembuatan slice view tanpa alokasi ulang memory buffer.
- Benchmarking: Memory footprint, null filtering, dan slice throughput.
"""

import sys
import time
import array
import struct
from typing import List, Optional, Tuple, Any

# ANSI Color Codes untuk visualisasi CLI
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_CYAN    = "\033[36m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_RED     = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE    = "\033[34m"


class TraditionalObjectSeries:
    """
    Memodelkan Pandas 1.x / NumPy object-backend.
    Setiap elemen string merupakan PyObject heap-allocated mandiri dengan 
    array of pointers yang menyebabkan memory fragmentation dan pointer chasing.
    """
    def __init__(self, data: List[Optional[str]]):
        self.data: List[Optional[str]] = list(data)
        self.length: int = len(data)

    def total_memory_bytes(self) -> int:
        """Menghitung footprint memori: List container + pointer slots + PyObject strings."""
        # Ukuran list wrapper dan pointer array (8 bytes per pointer pada 64-bit)
        size = sys.getsizeof(self.data)
        # Menghitung ukuran sesungguhnya dari masing-masing string di heap
        for item in self.data:
            if item is not None:
                size += sys.getsizeof(item)
            else:
                size += sys.getsizeof(None)
        return size

    def slice_data(self, start: int, end: int) -> 'TraditionalObjectSeries':
        """Slicing membutuhkan shallow copy dari array pointer (alokasi list baru)."""
        return TraditionalObjectSeries(self.data[start:end])

    def count_nulls(self) -> int:
        """Null check via pointer dereference inspection."""
        return sum(1 for x in self.data if x is None)


class ArrowStringArray:
    """
    Memodelkan Apache Arrow Columnar Format untuk Utf8 / LargeUtf8:
    1. Validity Bitmap: 1 bit per value (0 = null, 1 = valid).
    2. Offsets Buffer: Array int32 berurutan yang menandai offset byte data.
    3. Values Buffer: Single contiguous bytearray yang menyimpan semua raw string.
    Mendukung True Zero-Copy Slicing via buffer sharing & offset windowing.
    """
    def __init__(self, length: int, null_count: int, validity_bitmap: bytearray,
                 offsets: array.array, values: bytearray,
                 slice_offset: int = 0):
        self.length = length
        self.null_count = null_count
        self.validity_bitmap = validity_bitmap  # Bit array (1-bit per cell)
        self.offsets = offsets                  # int32 contiguous array
        self.values = values                    # Contiguous bytearray
        self.slice_offset = slice_offset        # Zero-copy base offset pointer

    @classmethod
    def from_iterable(cls, data: List[Optional[str]]) -> 'ArrowStringArray':
        """Encoder: Mengonversi iterable menjadi contiguous layout standar Apache Arrow."""
        length = len(data)
        bitmap_bytes = (length + 7) // 8
        validity = bytearray(bitmap_bytes)
        offsets = array.array('i', [0])  # Signed 32-bit integer array
        values = bytearray()
        null_count = 0

        current_byte_len = 0
        for idx, item in enumerate(data):
            byte_idx = idx // 8
            bit_idx = idx % 8

            if item is not None:
                # Set validity bit ke 1
                validity[byte_idx] |= (1 << bit_idx)
                encoded = item.encode('utf-8')
                values.extend(encoded)
                current_byte_len += len(encoded)
            else:
                null_count += 1
                # Bit tetap 0 (Null)
            
            offsets.append(current_byte_len)

        return cls(length, null_count, validity, offsets, values)

    def total_memory_bytes(self) -> int:
        """Menghitung total footprint memori buffer contiguous murni tanpa overhead pointer list."""
        return (
            sys.getsizeof(self.validity_bitmap) +
            self.offsets.buffer_info()[1] * self.offsets.itemsize +
            sys.getsizeof(self.values)
        )

    def zero_copy_slice(self, start: int, end: int) -> 'ArrowStringArray':
        """
        Zero-Copy Slice:
        Hanya menggeser windowing (offset dan length), tidak ada alokasi data buffer baru.
        Buffer underlying dibagi bersama (shared memory semantics).
        """
        if start < 0 or end > self.length or start > end:
            raise IndexError("Index slice di luar jangkauan valid.")
        
        new_length = end - start
        # Recomputing slice null_count secara cepat menggunakan bit-masking
        # Untuk demonstrasi zero-copy, buffer offsets & values tetap di-pass as reference
        return ArrowStringArray(
            length=new_length,
            null_count=-1, # Lazy evaluation
            validity_bitmap=self.validity_bitmap,
            offsets=self.offsets,
            values=self.values,
            slice_offset=self.slice_offset + start
        )

    def get_value(self, index: int) -> Optional[str]:
        """Akses data O(1) via offset direct addressing."""
        if index < 0 or index >= self.length:
            raise IndexError("Index array out of bounds")

        actual_idx = self.slice_offset + index
        byte_idx = actual_idx // 8
        bit_idx = actual_idx % 8

        # Cek validity bit
        is_valid = (self.validity_bitmap[byte_idx] & (1 << bit_idx)) != 0
        if not is_valid:
            return None

        start_byte = self.offsets[actual_idx]
        end_byte = self.offsets[actual_idx + 1]
        raw_slice = self.values[start_byte:end_byte]
        return raw_slice.decode('utf-8')

    def count_nulls_bitwise(self) -> int:
        """
        Arrow SIMD-friendly null counter:
        Menghitung null menggunakan popcount bitwise tanpa pointer chasing.
        """
        total_valid = 0
        # Hitung bit 1 pada full bytes
        full_bytes = self.length // 8
        for i in range(full_bytes):
            total_valid += bin(self.validity_bitmap[i]).count('1')
        
        # Hitung bit pada sisa byte terakhir
        remaining_bits = self.length % 8
        if remaining_bits > 0:
            last_byte = self.validity_bitmap[full_bytes]
            mask = (1 << remaining_bits) - 1
            total_valid += bin(last_byte & mask).count('1')

        return self.length - total_valid


def print_header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [LAB] {title.upper()} {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*75}{CLR_RESET}")


def run_benchmark():
    print_header("Arsitektur Internal: Pandas Traditional vs Apache Arrow")
    print(f"{CLR_YELLOW}Menyiapkan dataset sintetis enterprise (50,000 record string + variasi nulls)...{CLR_RESET}")

    # Dataset Generator
    domains = ["finance.corp", "datacenter.internal", "analytics.cloud", "infra.node"]
    base_data: List[Optional[str]] = []
    
    for i in range(50000):
        if i % 7 == 0:
            base_data.append(None)  # Menyisipkan ~14.2% Nulls
        else:
            base_data.append(f"node-{i:06d}.cluster-{i % 32}.{domains[i % 4]}")

    print(f"{CLR_GREEN}Dataset berhasil dibuat: {len(base_data):,} baris.{CLR_RESET}\n")

    # 1. Alokasi Tradisional (NumPy/Pandas 1.x Object Pointer Layout)
    t0 = time.perf_counter()
    trad_series = TraditionalObjectSeries(base_data)
    trad_init_time = (time.perf_counter() - t0) * 1000
    trad_mem = trad_series.total_memory_bytes()

    # 2. Alokasi Apache Arrow (Pandas 2.x Contiguous Columnar Layout)
    t0 = time.perf_counter()
    arrow_array = ArrowStringArray.from_iterable(base_data)
    arrow_init_time = (time.perf_counter() - t0) * 1000
    arrow_mem = arrow_array.total_memory_bytes()

    # Memory Comparison Report
    print(f"{CLR_BOLD}{CLR_MAGENTA}--- 1. ANALISIS STRUKTUR & EFISIENSI MEMORI ---{CLR_RESET}")
    print(f"NumPy Object Model Memory : {CLR_RED}{trad_mem / (1024*1024):.2f} MB{CLR_RESET} "
          f"({trad_mem:,} bytes)")
    print(f"Arrow Columnar Memory     : {CLR_GREEN}{arrow_mem / (1024*1024):.2f} MB{CLR_RESET} "
          f"({arrow_mem:,} bytes)")
    
    saving_pct = ((trad_mem - arrow_mem) / trad_mem) * 100
    print(f"Efisiensi Ruang Memori    : {CLR_BOLD}{CLR_GREEN}{saving_pct:.2f}% Lebih Ringkas!{CLR_RESET}")
    print(f"Waktu Encoding Arrow      : {arrow_init_time:.2f} ms")

    # 2. Slicing Benchmark (Zero-Copy vs New Pointer Array)
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}--- 2. BENCHMARK ZERO-COPY SLICING (10,000 operasi) ---{CLR_RESET}")
    iterations = 10000
    slice_start, slice_end = 5000, 25000

    # Benchmark Traditional Slice
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = trad_series.slice_data(slice_start, slice_end)
    trad_slice_duration = (time.perf_counter() - t0) * 1000

    # Benchmark Arrow Zero-Copy Slice
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = arrow_array.zero_copy_slice(slice_start, slice_end)
    arrow_slice_duration = (time.perf_counter() - t0) * 1000

    speedup = trad_slice_duration / arrow_slice_duration if arrow_slice_duration > 0 else 1.0
    print(f"NumPy Pointer Slicing     : {CLR_RED}{trad_slice_duration:.2f} ms{CLR_RESET}")
    print(f"Arrow Zero-Copy Slicing   : {CLR_GREEN}{arrow_slice_duration:.2f} ms{CLR_RESET}")
    print(f"Peningkatan Kecepatan     : {CLR_BOLD}{CLR_GREEN}{speedup:.2f}x Lebih Cepat{CLR_RESET}")

    # 3. Validity Bitmap Inspection & Bitwise Null Count
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}--- 3. BITMAP NULL-TRACKING & VERIFIKASI MEMORI ---{CLR_RESET}")
    
    t0 = time.perf_counter()
    nulls_trad = trad_series.count_nulls()
    time_trad_nulls = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    nulls_arrow = arrow_array.count_nulls_bitwise()
    time_arrow_nulls = (time.perf_counter() - t0) * 1000

    print(f"Total Null Terhitung      : Traditional = {nulls_trad:,} | Arrow = {nulls_arrow:,}")
    assert nulls_trad == nulls_arrow, "Inkonsistensi deteksi null antar backend!"
    print(f"Waktu Bitmap Popcount     : {CLR_GREEN}{time_arrow_nulls:.4f} ms{CLR_RESET} "
          f"vs Traditional Pointer Traversal: {CLR_RED}{time_trad_nulls:.4f} ms{CLR_RESET}")

    # Visualisasi Binary Buffer Layout
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}--- 4. INSPEKSI FISIK MEMORI ARROW BUFFER (5 Elemen Pertama) ---{CLR_RESET}")
    print(f"{'Idx':<5} | {'Bit State':<10} | {'Status':<8} | {'Offset Window':<15} | {'Payload Terdecode'}")
    print("-" * 75)
    for i in range(5):
        bit_val = (arrow_array.validity_bitmap[i // 8] >> (i % 8)) & 1
        status = f"{CLR_GREEN}VALID{CLR_RESET}" if bit_val else f"{CLR_RED}NULL{CLR_RESET}"
        off_window = f"[{arrow_array.offsets[i]} -> {arrow_array.offsets[i+1]}]"
        val = arrow_array.get_value(i)
        display_val = f'"{val}"' if val is not None else "None (<NA> Arrow)"
        print(f"{i:<5} | 0b{bit_val:<8} | {status:<17} | {off_window:<15} | {display_val}")

    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}SIMULASI SELESAI: Arsitektur Pandas 2.x Arrow terbukti menghilangkan overhead pointer!{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*75}{CLR_RESET}\n")


if __name__ == "__main__":
    run_benchmark()