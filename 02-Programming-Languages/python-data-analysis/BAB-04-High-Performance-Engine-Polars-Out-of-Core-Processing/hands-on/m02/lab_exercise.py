#!/usr/bin/env python3
"""
Lab Hands-on: Out-of-Core Columnar Processing Engine
Bab 04: High-Performance Engine (Polars & Out-of-Core Processing) - Modul 02 Deep Dive

Deskripsi:
Skrip ini mengimplementasikan simulasi arsitektur low-level dari mesin eksekusi 
data kolumnar out-of-core (seperti Polars engine). Mensimulasikan format penyimpanan
Arrow-like columnar, query planner (predicate pushdown & projection pushdown),
dan pipeline eksekusi streaming berbasis chunk dengan bounded memory.
"""

import os
import sys
import time
import struct
import tempfile
from typing import List, Dict, Generator, Tuple, Any
from collections import defaultdict

# ANSI Terminal Styling
CLR_RESET = "\033[0m"
CLR_BOLD  = "\033[1m"
CLR_RED   = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW= "\033[93m"
CLR_BLUE  = "\033[94m"
CLR_CYAN  = "\033[96m"

# Palet Kategori Simulasi
CATEGORIES = ["ELECTRONICS", "GROCERY", "CLOTHING", "HOME", "AUTOMOTIVE"]

# ==============================================================================
# 1. STORAGE LAYER: MOCK COLUMNAR FILE FORMAT (SIMULASI APACHE ARROW/FEATHER)
# ==============================================================================

class ColumnarChunkWriter:
    """
    Menulis chunk data ke disk menggunakan layout kolumnar biner.
    Kolom disimpan secara independen untuk memungkinkan selective I/O (projection pushdown).
    """
    @staticmethod
    def write_chunk(file_path: str, user_ids: List[int], cat_ids: List[int], 
                    amounts: List[float], payloads: List[bytes]) -> int:
        count = len(user_ids)
        bytes_written = 0
        with open(file_path, "wb") as f:
            # Header: [Row Count: uint32]
            f.write(struct.pack("<I", count))
            bytes_written += 4

            # Simpan offset pointer untuk setiap kolom (Metadata block)
            # Offset tabel: 4 kolom x uint64 = 32 bytes
            offset_table_pos = f.tell()
            f.write(b"\x00" * 32)
            bytes_written += 32

            offsets = []

            # Col 0: user_id (int32)
            offsets.append(f.tell())
            data_uid = struct.pack(f"<{count}i", *user_ids)
            f.write(data_uid)
            bytes_written += len(data_uid)

            # Col 1: cat_id (uint8)
            offsets.append(f.tell())
            data_cat = struct.pack(f"<{count}B", *cat_ids)
            f.write(data_cat)
            bytes_written += len(data_cat)

            # Col 2: amount (float32)
            offsets.append(f.tell())
            data_amt = struct.pack(f"<{count}f", *amounts)
            f.write(data_amt)
            bytes_written += len(data_amt)

            # Col 3: payload (heavy text metadata - fixed 64 bytes per row)
            offsets.append(f.tell())
            for p in payloads:
                p_pad = p[:64].ljust(64, b" ")
                f.write(p_pad)
                bytes_written += 64

            # Patch offset header
            f.seek(offset_table_pos)
            f.write(struct.pack("<4Q", *offsets))

        return bytes_written


class ColumnarChunkReader:
    """
    Membaca data dari disk dengan kemampuan skip kolom yang tidak diminta (Projection Pushdown).
    """
    def __init__(self, file_path: str):
        self.file_path = file_path
        with open(self.file_path, "rb") as f:
            self.row_count = struct.unpack("<I", f.read(4))[0]
            self.offsets = list(struct.unpack("<4Q", f.read(32)))

    def scan_columns(self, requested_cols: List[str]) -> Dict[str, Any]:
        """
        Melakukan selective seek & read hanya pada byte stream kolom yang dibutuhkan.
        """
        results = {"row_count": self.row_count}
        with open(self.file_path, "rb") as f:
            if "user_id" in requested_cols:
                f.seek(self.offsets[0])
                raw = f.read(self.row_count * 4)
                results["user_id"] = struct.unpack(f"<{self.row_count}i", raw)

            if "cat_id" in requested_cols:
                f.seek(self.offsets[1])
                raw = f.read(self.row_count * 1)
                results["cat_id"] = struct.unpack(f"<{self.row_count}B", raw)

            if "amount" in requested_cols:
                f.seek(self.offsets[2])
                raw = f.read(self.row_count * 4)
                results["amount"] = struct.unpack(f"<{self.row_count}f", raw)

            if "payload" in requested_cols:
                f.seek(self.offsets[3])
                raw = f.read(self.row_count * 64)
                # Parsing string array
                results["payload"] = [raw[i*64:(i+1)*64].decode("utf-8", "ignore").strip() 
                                      for i in range(self.row_count)]

        return results


# ==============================================================================
# 2. QUERY OPTIMIZER & OUT-OF-CORE ENGINE
# ==============================================================================

class QueryEngine:
    """
    Simulasi Out-of-Core Execution Engine:
    - Streaming batch pipeline (Memory bounds dijaga)
    - Predicate Pushdown (Filter sedini mungkin)
    - Projection Pushdown (Hanya load kolom yang direferensikan)
    """
    def __init__(self, chunk_files: List[str]):
        self.chunk_files = chunk_files

    def run_eager_naive(self, min_amount: float) -> Tuple[Dict[str, float], float, int]:
        """
        Model Naive (Row-oriented / Eager):
        Memuat SEMUA kolom dan baris ke memori sekaligus sebelum agregasi.
        """
        start = time.perf_counter()
        total_bytes_loaded = 0
        in_memory_records = []

        # Load seluruh isi dataset (termasuk kolom payload berat)
        for cf in self.chunk_files:
            file_size = os.path.getsize(cf)
            total_bytes_loaded += file_size
            reader = ColumnarChunkReader(cf)
            # Naive: minta semua kolom
            data = reader.scan_columns(["user_id", "cat_id", "amount", "payload"])
            
            # Konversi kolumnar ke format baris (row tuples) di RAM
            for i in range(data["row_count"]):
                in_memory_records.append((
                    data["user_id"][i],
                    data["cat_id"][i],
                    data["amount"][i],
                    data["payload"][i]
                ))

        # Filter & Agregasi di RAM
        aggregates = defaultdict(float)
        for uid, cid, amt, payload in in_memory_records:
            if amt >= min_amount:
                cat_name = CATEGORIES[cid]
                aggregates[cat_name] += amt

        elapsed = time.perf_counter() - start
        return dict(aggregates), elapsed, total_bytes_loaded

    def run_streaming_optimized(self, min_amount: float) -> Tuple[Dict[str, float], float, int]:
        """
        Model Out-of-Core Columnar (Polars-like):
        - Projection pushdown: hanya load 'amount' dan 'cat_id'
        - Predicate pushdown: filter dilakukan vectorized pada level buffer per-chunk
        - Streaming accumulator: RAM footprint dibatasi konstan per chunk
        """
        start = time.perf_counter()
        total_bytes_loaded = 0
        aggregates = defaultdict(float)

        for cf in self.chunk_files:
            reader = ColumnarChunkReader(cf)
            
            # PROJECTION PUSHDOWN: Skip 'user_id' dan 'payload' (menghemat ~85% I/O)
            required_cols = ["cat_id", "amount"]
            data = reader.scan_columns(required_cols)
            
            # Hitung I/O aktual yang dibaca
            # Header (36B) + cat_id (1B * N) + amount (4B * N)
            chunk_io = 36 + (data["row_count"] * 1) + (data["row_count"] * 4)
            total_bytes_loaded += chunk_io

            cat_ids = data["cat_id"]
            amounts = data["amount"]

            # VECTORIZED / STREAMING ACCUMULATION
            # Predicate pushdown diaplikasikan saat streaming chunk aktif
            for i in range(data["row_count"]):
                amt = amounts[i]
                if amt >= min_amount:
                    aggregates[CATEGORIES[cat_ids[i]]] += amt

            # Explicit de-allocation buffer per chunk
            del data
            del cat_ids
            del amounts

        elapsed = time.perf_counter() - start
        return dict(aggregates), elapsed, total_bytes_loaded


# ==============================================================================
# 3. LAB BENCHMARK & ORCHESTRATION
# ==============================================================================

def generate_mock_warehouse(temp_dir: str, num_chunks: int, rows_per_chunk: int) -> Tuple[List[str], int]:
    """Menghasilkan file chunk biner sintetis untuk mensimulasikan partisi data."""
    chunk_paths = []
    total_records = num_chunks * rows_per_chunk
    print(f"{CLR_CYAN}[SETUP]{CLR_RESET} Menghasilkan {num_chunks} chunk kolumnar ({total_records:,} total transaksi)...")

    # Pseudo-random LCG deterministik tanpa overhead modul random
    seed = 1337
    def fast_rand():
        nonlocal seed
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        return seed

    total_disk_bytes = 0
    for chunk_idx in range(num_chunks):
        user_ids = []
        cat_ids = []
        amounts = []
        payloads = []

        for r in range(rows_per_chunk):
            r_val = fast_rand()
            user_ids.append(r_val % 50000)
            cat_ids.append((r_val >> 8) % len(CATEGORIES))
            # Amount berkisar antara 5.0 s/d 505.0
            amounts.append(5.0 + float((r_val >> 16) % 50000) / 100.0)
            # Simulasi metadata transaksi (heavy payload)
            payloads.append(f"TX_META_CHUNK_{chunk_idx}_ROW_{r}_HASH_{r_val:x}".encode("ascii"))

        chunk_path = os.path.join(temp_dir, f"partition_{chunk_idx:03d}.col")
        written = ColumnarChunkWriter.write_chunk(chunk_path, user_ids, cat_ids, amounts, payloads)
        total_disk_bytes += written
        chunk_paths.append(chunk_path)

    print(f"{CLR_GREEN}✔ Dataset tersimpan di disk:{CLR_RESET} {total_disk_bytes / (1024 * 1024):.2f} MB")
    return chunk_paths, total_records


def main():
    print(f"{CLR_BOLD}{CLR_BLUE}================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} LAB: POLARS & OUT-OF-CORE COLUMNAR ENGINE (INTERNAL ARCHITECTURE){CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}================================================================={CLR_RESET}\n")

    # Konfigurasi simulasi
    NUM_CHUNKS = 10
    ROWS_PER_CHUNK = 25_000 # Total 250,000 records
    MIN_AMOUNT_FILTER = 250.0 # Predicate: amount >= 250.0

    with tempfile.TemporaryDirectory() as temp_dir:
        chunk_files, total_rows = generate_mock_warehouse(temp_dir, NUM_CHUNKS, ROWS_PER_CHUNK)
        engine = QueryEngine(chunk_files)

        print(f"\n{CLR_YELLOW}Query Logical Plan:{CLR_RESET}")
        print(f"  SCAN (Dataset)")
        print(f"  └── FILTER (amount >= {MIN_AMOUNT_FILTER})")
        print(f"      └── PROJECT [category, amount]")
        print(f"          └── AGGREGATE sum(amount) GROUP BY category\n")

        # -------------------------------------------------------------
        # Test 1: Eager / In-Memory (Naive)
        # -------------------------------------------------------------
        print(f"{CLR_BOLD}[1] Mengeksekusi Pendekatan Eager (Naive Row-Oriented)...{CLR_RESET}")
        res_eager, time_eager, io_eager = engine.run_eager_naive(MIN_AMOUNT_FILTER)
        print(f"    Waktu Eksekusi : {CLR_RED}{time_eager:.4f} detik{CLR_RESET}")
        print(f"    I/O Read Volume: {CLR_RED}{io_eager / (1024 * 1024):.2f} MB{CLR_RESET}")

        # -------------------------------------------------------------
        # Test 2: Out-of-Core Columnar Streaming
        # -------------------------------------------------------------
        print(f"\n{CLR_BOLD}[2] Mengeksekusi Out-of-Core Columnar Engine (Pushdown + Stream)...{CLR_RESET}")
        res_opt, time_opt, io_opt = engine.run_streaming_optimized(MIN_AMOUNT_FILTER)
        print(f"    Waktu Eksekusi : {CLR_GREEN}{time_opt:.4f} detik{CLR_RESET}")
        print(f"    I/O Read Volume: {CLR_GREEN}{io_opt / (1024 * 1024):.2f} MB{CLR_RESET}")

        # -------------------------------------------------------------
        # Verifikasi Kebenaran & Telemetri
        # -------------------------------------------------------------
        print(f"\n{CLR_BOLD}{CLR_CYAN}Verifikasi Konsistensi Hasil Agregasi:{CLR_RESET}")
        is_identical = True
        for cat in CATEGORIES:
            val_eager = res_eager.get(cat, 0.0)
            val_opt = res_opt.get(cat, 0.0)
            # Toleransi float32 precision
            diff = abs(val_eager - val_opt)
            status = f"{CLR_GREEN}VALID{CLR_RESET}" if diff < 0.1 else f"{CLR_RED}MISMATCH{CLR_RESET}"
            print(f"  - {cat:<12}: Eager=${val_eager:11.2f} | OutOfCore=${val_opt:11.2f} [{status}]")
            if diff >= 0.1:
                is_identical = False

        assert is_identical, "Hasil komputasi tidak konsisten!"

        # -------------------------------------------------------------
        # Metrik Performa
        # -------------------------------------------------------------
        speedup = (time_eager / time_opt) if time_opt > 0 else 0
        io_reduction = ((io_eager - io_opt) / io_eager) * 100

        print(f"\n{CLR_BOLD}{CLR_BLUE}================================================================={CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_GREEN}                  ANALISIS EFISIENSI ENGINE                      {CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_BLUE}================================================================={CLR_RESET}")
        print(f"  • Total Record Diproses : {CLR_BOLD}{total_rows:,}{CLR_RESET}")
        print(f"  • Akselerasi Kecepatan  : {CLR_GREEN}{speedup:.2f}x lebih cepat{CLR_RESET}")
        print(f"  • Reduksi Disk I/O      : {CLR_GREEN}{io_reduction:.2f}% byte bandwidth dihemat{CLR_RESET}")
        print(f"  • Karakteristik Memori  : {CLR_CYAN}Bounded per chunk (O(chunk_size) vs O(N)){CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_BLUE}================================================================={CLR_RESET}\n")

if __name__ == "__main__":
    main()