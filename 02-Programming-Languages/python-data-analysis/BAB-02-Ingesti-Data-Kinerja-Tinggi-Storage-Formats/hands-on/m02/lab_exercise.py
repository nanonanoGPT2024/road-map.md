#!/usr/bin/env python3
"""
Lab Hands-on: Ingesti Data Kinerja Tinggi & Storage Formats
Kategori: 02-Programming-Languages / Topik: python-data-analysis (Bab 02)

Deskripsi:
Skrip mandiri ini memodelkan perbedaan performa antara row-oriented storage (CSV)
dan custom binary columnar storage (mirip fondasi internal Apache Parquet/Arrow).
Mendemonstrasikan konsep Column Projection & Block Skipping dalam I/O analitik.
"""

import os
import sys
import time
import array
import struct
import csv
import random
from typing import List, Tuple

# ANSI Escape Sequences untuk Terminal Formatting
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_BLUE = "\033[34m"

RECORD_COUNT = 150_000
CSV_FILE = "telemetry_data.csv"
COL_FILE = "telemetry_data.pcol"


def generate_synthetic_telemetry(n: int) -> List[Tuple[int, int, float, float]]:
    """
    Menghasilkan data telemetri sintetis:
    Schema: (timestamp: uint32, device_id: uint16, cpu_load: float32, mem_load: float32)
    """
    print(f"{C_CYAN}[1/4] Membangkitkan {n:,} baris data sintetis di memori...{C_RESET}")
    base_ts = 1700000000
    data = []
    for i in range(n):
        ts = base_ts + i
        dev_id = random.randint(1, 1024)
        cpu = round(random.uniform(5.0, 99.0), 2)
        mem = round(random.uniform(20.0, 85.0), 2)
        data.append((ts, dev_id, cpu, mem))
    return data


def serialize_to_csv(data: List[Tuple[int, int, float, float]], filename: str) -> float:
    """
    Menulis data ke format Row-Oriented Text (CSV).
    Kelemahan teknis: CPU overhead tinggi untuk serialisasi string & delimiter parsing.
    """
    start_time = time.perf_counter()
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "device_id", "cpu_load", "mem_load"])
        for row in data:
            writer.writerow(row)
    duration = time.perf_counter() - start_time
    return duration


def serialize_to_columnar(data: List[Tuple[int, int, float, float]], filename: str) -> float:
    """
    Menulis data ke format Custom Binary Columnar (.pcol).
    
    Layout File:
    - Header: Magic (4B: 'PCOL') | Record Count (uint32)
    - Metadata Offset: 4 x (Offset: uint64, ByteLength: uint64)
    - Column Payloads:
        Col 0: Timestamps (uint32 array)
        Col 1: Device IDs (uint16 array)
        Col 2: CPU Loads  (float32 array)
        Col 3: Mem Loads  (float32 array)
    """
    start_time = time.perf_counter()
    n = len(data)

    # Transformasi Row -> Columnar Arrays menggunakan array native Python
    col_ts = array.array("I", (row[0] for row in data))
    col_dev = array.array("H", (row[1] for row in data))
    col_cpu = array.array("f", (row[2] for row in data))
    col_mem = array.array("f", (row[3] for row in data))

    ts_bytes = col_ts.tobytes()
    dev_bytes = col_dev.tobytes()
    cpu_bytes = col_cpu.tobytes()
    mem_bytes = col_mem.tobytes()

    header_magic = b"PCOL"
    header_count = struct.pack("<I", n)
    
    # Hitung offset: Header(8B) + Table of Contents (4 kolom * 16B = 64B) = 72B
    toc_offset = 8
    toc_size = 4 * 16
    data_start = toc_offset + toc_size

    offsets = [
        data_start,
        data_start + len(ts_bytes),
        data_start + len(ts_bytes) + len(dev_bytes),
        data_start + len(ts_bytes) + len(dev_bytes) + len(cpu_bytes),
    ]
    lengths = [len(ts_bytes), len(dev_bytes), len(cpu_bytes), len(mem_bytes)]

    with open(filename, "wb") as f:
        f.write(header_magic)
        f.write(header_count)
        for off, length in zip(offsets, lengths):
            f.write(struct.pack("<QQ", off, length))
        # Zero-copy buffer write
        f.write(ts_bytes)
        f.write(dev_bytes)
        f.write(cpu_bytes)
        f.write(mem_bytes)

    duration = time.perf_counter() - start_time
    return duration


def query_avg_cpu_csv(filename: str) -> Tuple[float, float, int]:
    """
    Analytic Query (Row Store): Hitung rata-rata cpu_load.
    Kelemahan: Harus membaca seluruh baris (timestamp, device_id, mem_load) dari disk
    dan melakukan tokenizing + float cast pada setiap baris.
    """
    start_time = time.perf_counter()
    total_cpu = 0.0
    count = 0
    bytes_read = os.path.getsize(filename)

    with open(filename, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            total_cpu += float(row[2])
            count += 1

    avg_cpu = total_cpu / count if count else 0.0
    duration = time.perf_counter() - start_time
    return avg_cpu, duration, bytes_read


def query_avg_cpu_columnar(filename: str) -> Tuple[float, float, int]:
    """
    Analytic Query (Column Store / Projection Pushdown):
    Keunggulan: Melompati (seek) data timestamp, device_id, dan mem_load.
    Hanya membaca payload kolom cpu_load langsung ke native memory buffer.
    """
    start_time = time.perf_counter()
    
    with open(filename, "rb") as f:
        magic = f.read(4)
        if magic != b"PCOL":
            raise ValueError("Bukan format binary PCOL yang valid!")
        
        record_count = struct.unpack("<I", f.read(4))[0]
        
        # CPU load adalah kolom indeks ke-2 (0-indexed). Lewati Col 0 & Col 1 metadata (2 * 16B)
        f.seek(8 + (2 * 16))
        cpu_offset, cpu_length = struct.unpack("<QQ", f.read(16))
        
        # Seek langsung ke offset data kolom CPU dan ingest hanya kolom tersebut
        f.seek(cpu_offset)
        cpu_buffer = f.read(cpu_length)
        
        # Deserialisasi langsung ke native array float32 tanpa per-row overhead
        cpu_array = array.array("f")
        cpu_array.frombytes(cpu_buffer)
        
        total_cpu = sum(cpu_array)
        avg_cpu = total_cpu / record_count if record_count else 0.0

    duration = time.perf_counter() - start_time
    actual_bytes_read = 8 + 64 + cpu_length  # Header + TOC + Kolom CPU
    return avg_cpu, duration, actual_bytes_read


def run_benchmark():
    print(f"{C_BOLD}{C_BLUE}=== HIGH-PERFORMANCE DATA INGESTION & STORAGE FORMATS BENCHMARK ==={C_RESET}\n")

    # Inisialisasi Data
    raw_data = generate_synthetic_telemetry(RECORD_COUNT)

    try:
        # Benchmark Write
        print(f"\n{C_CYAN}[2/4] Menjalankan Pengujian Serialisasi Disk...{C_RESET}")
        t_write_csv = serialize_to_csv(raw_data, CSV_FILE)
        size_csv = os.path.getsize(CSV_FILE)
        print(f"  • Row-CSV     : {t_write_csv:.4f}s | File Size: {size_csv / 1024 / 1024:.2f} MB")

        t_write_col = serialize_to_columnar(raw_data, COL_FILE)
        size_col = os.path.getsize(COL_FILE)
        print(f"  • Col-Binary  : {t_write_col:.4f}s | File Size: {size_col / 1024 / 1024:.2f} MB")
        print(f"  {C_GREEN}→ Storage Footprint Reduction: {(1 - size_col / size_csv) * 100:.1f}%{C_RESET}")

        # Benchmark Analytical Ingestion (Column Projection)
        print(f"\n{C_CYAN}[3/4] Menjalankan Analytical Query: AVG(cpu_load)...{C_RESET}")
        avg_csv, t_read_csv, bytes_csv = query_avg_cpu_csv(CSV_FILE)
        print(f"  • Row-CSV     : Hasil = {avg_csv:.4f} | Waktu = {t_read_csv:.4f}s | I/O = {bytes_csv / 1024 / 1024:.2f} MB")

        avg_col, t_read_col, bytes_col = query_avg_cpu_columnar(COL_FILE)
        print(f"  • Col-Binary  : Hasil = {avg_col:.4f} | Waktu = {t_read_col:.4f}s | I/O = {bytes_col / 1024 / 1024:.2f} MB")

        # Analisis Komparatif
        speedup_write = t_write_csv / t_write_col if t_write_col else 1.0
        speedup_query = t_read_csv / t_read_col if t_read_col else 1.0
        io_efficiency = bytes_csv / bytes_col if bytes_col else 1.0

        print(f"\n{C_CYAN}[4/4] Rangkuman Metrik & Evaluasi Performa Engine{C_RESET}")
        print("-" * 70)
        print(f"{'Metrik':<28} | {'Row Format (CSV)':<18} | {'Columnar Binary':<18}")
        print("-" * 70)
        print(f"{'Ukuran File':<28} | {size_csv / 1024 / 1024:>14.2f} MB | {size_col / 1024 / 1024:>14.2f} MB")
        print(f"{'Waktu Serialisasi (Write)':<28} | {t_write_csv:>15.4f}s | {t_write_col:>15.4f}s")
        print(f"{'Waktu Query (Single Col)':<28} | {t_read_csv:>15.4f}s | {t_read_col:>15.4f}s")
        print(f"{'Volume I/O Dibaca':<28} | {bytes_csv / 1024 / 1024:>14.2f} MB | {bytes_col / 1024 / 1024:>14.2f} MB")
        print("-" * 70)

        print(f"\n{C_BOLD}Insight Teknis Arsitektur Storage:{C_RESET}")
        print(f"  1. {C_GREEN}Write Acceleration:{C_RESET} Format columnar binary {speedup_write:.1f}x lebih cepat saat penulisan.")
        print(f"  2. {C_GREEN}Analytical Ingestion:{C_RESET} Query engine melompati byte tak relevan (Projection Pushdown),")
        print(f"     menghasilkan percepatan {C_BOLD}{speedup_query:.1f}x{C_RESET} dan efisiensi throughput disk {C_BOLD}{io_efficiency:.1f}x{C_RESET}.")

    finally:
        # Cleanup file eksperimen
        for path in (CSV_FILE, COL_FILE):
            if os.path.exists(path):
                os.remove(path)
        print(f"\n{C_YELLOW}[Cleanup] File pengujian sementara berhasil dihapus.{C_RESET}")


if __name__ == "__main__":
    run_benchmark()