#!/usr/bin/env python3
"""
Lab Exercise: Simulasi R Data Import, Storage I/O, & Interoperabilitas
BAB-04: Data Import, Storage I/O, dan Interoperabilitas R
"""

import sys
import time
import os
import json
import sqlite3
import tempfile
from typing import Dict, List, Any

# ANSI Color Codes
BOLD = "\033[1m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


def print_step(step_num: int, description: str) -> None:
    print(f"\n{BOLD}{YELLOW}[Langkah {step_num}]{RESET} {description}")


def simulate_r_csv_parsers():
    """Simulasi perbandingan reader: read.csv (base) vs readr::read_csv vs data.table::fread."""
    print_header("Simulasi 1: Benchmark Parser I/O (base vs readr vs data.table)")
    print(f"{DIM}Menguji 500,000 baris sintetis transaksi data...{RESET}")

    datasets = [
        {"engine": "utils::read.csv (Base R)", "overhead_factor": 1.0, "type_inference": "Single-thread, Factor coercion slow"},
        {"engine": "readr::read_csv (vroom)", "overhead_factor": 0.28, "type_inference": "Multi-threaded C++, Tibble output"},
        {"engine": "data.table::fread (C-level)", "overhead_factor": 0.12, "type_inference": "Memory-mapped, SIMD parallel"}
    ]

    base_delay = 0.45
    for item in datasets:
        engine_name = item["engine"]
        delay = base_delay * item["overhead_factor"]
        print(f"\n{BOLD}Menjalankan parser: {MAGENTA}{engine_name}{RESET}...")
        start = time.perf_counter()
        time.sleep(delay)
        elapsed = time.perf_counter() - start

        # Kalkulasi throughput simulasi
        rows = 500_000
        throughput = rows / elapsed
        print(f"  -> Durasi Parse: {GREEN}{elapsed:.4f} detik{RESET}")
        print(f"  -> Throughput  : {BOLD}{throughput:,.0f} rows/detik{RESET}")
        print(f"  -> Karakteristik: {DIM}{item['type_inference']}{RESET}")


def simulate_storage_formats():
    """Simulasi perbandingan format persistensi: RDS vs RData vs Feather vs Apache Parquet."""
    print_header("Simulasi 2: Serialization & Storage Architecture")
    
    records = [
        {"format": ".rds (saveRDS/readRDS)", "compression": "gzip/xz", "size_mb": 42.5, "write_sec": 1.45, "read_sec": 0.62, "type": "Single R object"},
        {"format": ".RData (save/load)", "compression": "gzip", "size_mb": 45.1, "write_sec": 1.52, "read_sec": 0.70, "type": "Multi-object workspace"},
        {"format": ".feather (arrow::write_feather)", "compression": "lz4", "size_mb": 58.2, "write_sec": 0.18, "read_sec": 0.08, "type": "Zero-copy IPC, Arrow memory"},
        {"format": ".parquet (arrow::write_parquet)", "compression": "snappy/zstd", "size_mb": 18.4, "write_sec": 0.35, "read_sec": 0.12, "type": "Columnar, pushdown predicates"}
    ]

    print(f"{'Format':<35} {'Kompresi':<14} {'Ukuran File':<12} {'Write (s)':<10} {'Read (s)':<10}")
    print(f"{'-' * 81}")

    for rec in records:
        print(f"{BOLD}{rec['format']:<35}{RESET} {rec['compression']:<14} {rec['size_mb']:>6.1f} MB     {rec['write_sec']:>6.2f}s    {rec['read_sec']:>6.2f}s")
    
    print(f"\n{GREEN}[Insight Kinerja]{RESET} Format Parquet memberikan rasio kompresi terbaik (~60% lebih hemat dari RDS) dengan query filter cepat via Arrow pushdown.")


def simulate_dbi_sqlite_workflow():
    """Simulasi alur DBI & RSQLite: Koneksi, transaksi, chunking read, dan parameterized queries."""
    print_header("Simulasi 3: R DBI Database Layer & Chunking I/O")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "telemetri_r.sqlite")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        print_step(1, "Inisialisasi koneksi SQLite (mirip dbConnect(RSQLite::SQLite(), ...))")
        cur.execute("""
            CREATE TABLE sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                station_id TEXT,
                metric_value REAL
            )
        """)
        conn.commit()
        print(f"  {GREEN}✓{RESET} Tabel `sensor_readings` berhasil dibuat.")

        print_step(2, "Batch insertion aman dengan parameterized query (dbBind / dbExecute)")
        sample_data = [
            ("2026-10-05T04:00:00Z", f"STATION-{i % 5:02d}", 20.0 + (i * 0.15))
            for i in range(1, 101)
        ]
        cur.executemany("INSERT INTO sensor_readings (timestamp, station_id, metric_value) VALUES (?, ?, ?)", sample_data)
        conn.commit()
        print(f"  {GREEN}✓{RESET} Disisipkan {BOLD}{len(sample_data)}{RESET} baris secara atomik.")

        print_step(3, "Streaming fetch dengan chunking (mirip dbSendQuery + dbFetch(n = 25))")
        cur.execute("SELECT station_id, AVG(metric_value), COUNT(*) FROM sensor_readings GROUP BY station_id")
        
        chunk_idx = 1
        while True:
            rows = cur.fetchmany(2)
            if not rows:
                break
            print(f"  {MAGENTA}Chunk #{chunk_idx}:{RESET}")
            for station, avg_val, count in rows:
                print(f"    - Stasiun: {station} | Rata-rata: {avg_val:.2f} | Sampel: {count}")
            chunk_idx += 1

        conn.close()
        print(f"\n  {GREEN}✓{RESET} Koneksi database ditutup secara bersih (dbDisconnect).")


def simulate_interoperability_pipeline():
    """Simulasi R Interoperabilitas: reticulate (Python) & Rcpp (C++ shared memory)."""
    print_header("Simulasi 4: Interoperabilitas R (reticulate & Rcpp / Arrow C Data Interface)")

    print_step(1, "Simulasi reticulate: Konversi objek R DataFrame <-> Python Pandas / PyArrow")
    r_matrix = {
        "features": ["gene_a", "gene_b", "gene_c"],
        "counts": [1420, 895, 3120],
        "normalized": [0.45, 0.28, 0.99]
    }
    print(f"  Data Asal (R environment S3 data.frame):")
    print(f"  {DIM}{json.dumps(r_matrix, indent=4)}{RESET}")

    print(f"\n  {YELLOW}Menerapkan zero-copy PyCapsule transfer ke Python context...{RESET}")
    time.sleep(0.2)
    py_view = {k: tuple(v) for k, v in r_matrix.items()}
    print(f"  {GREEN}✓{RESET} Objek terbaca di Python engine tanpa serialize disk overhead!")
    print(f"  Memory address reference: {hex(id(py_view))}")

    print_step(2, "Simulasi Rcpp: Kompilasi C++ inline via cppFunction()")
    cpp_code = """
    // [[Rcpp::export]]
    double fast_accumulate(NumericVector x) {
        double total = 0;
        for(int i = 0; i < x.size(); ++i) { total += x[i]; }
        return total;
    }
    """
    print(f"{DIM}{cpp_code.strip()}{RESET}")
    print(f"  {GREEN}✓{RESET} Rcpp abstraction layer: loop native C++ mengeksekusi O(n) tanpa garbage collection penalti.")


def show_menu():
    print(f"\n{BOLD}{MAGENTA}=== LAB HANDS-ON BAB 04: R DATA I/O & INTEROPERABILITAS ==={RESET}")
    print("1. Benchmark Parser CSV (read.csv vs readr vs data.table)")
    print("2. Analisis Storage & Kompresi (RDS, RData, Feather, Parquet)")
    print("3. Database I/O & Stream Chunking (DBI / RSQLite Pattern)")
    print("4. Interoperabilitas (reticulate zero-copy & Rcpp architecture)")
    print("5. Jalankan Seluruh Modul Uji Sekaligus")
    print("0. Keluar")
    print(f"{DIM}Pilih opsi menu (0-5):{RESET} ", end="")


def main():
    print(f"{BOLD}{GREEN}Memulai Hands-on Lab Exercise: R-Programming Data I/O Engine{RESET}")
    
    # Jika dijalankan non-interaktif dalam automated pipeline
    if not sys.stdin.isatty():
        simulate_r_csv_parsers()
        simulate_storage_formats()
        simulate_dbi_sqlite_workflow()
        simulate_interoperability_pipeline()
        print(f"\n{BOLD}{GREEN}Automated pipeline selesai dengan sukses.{RESET}\n")
        return

    while True:
        try:
            show_menu()
            choice = input().strip()
            if choice == "1":
                simulate_r_csv_parsers()
            elif choice == "2":
                simulate_storage_formats()
            elif choice == "3":
                simulate_dbi_sqlite_workflow()
            elif choice == "4":
                simulate_interoperability_pipeline()
            elif choice == "5":
                simulate_r_csv_parsers()
                simulate_storage_formats()
                simulate_dbi_sqlite_workflow()
                simulate_interoperability_pipeline()
            elif choice == "0":
                print(f"\n{GREEN}Selesai. Terimakasih telah menyelesaikan Lab Modul 01 BAB-04.{RESET}\n")
                break
            else:
                print(f"{RED}Pilihan tidak valid. Silakan masukkan angka 0-5.{RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{YELLOW}Sesi lab dihentikan oleh pengguna.{RESET}\n")
            break


if __name__ == "__main__":
    main()
