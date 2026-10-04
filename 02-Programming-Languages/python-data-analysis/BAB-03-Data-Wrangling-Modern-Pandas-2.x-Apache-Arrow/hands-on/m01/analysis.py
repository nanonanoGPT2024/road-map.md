import os
import gc
import uuid
import hashlib
import tempfile
import tracemalloc
import time
from typing import Tuple
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Konfigurasi Lingkungan Produksi
pd.options.mode.copy_on_write = True

def generate_mock_csv(file_path: str, n_rows: int = 1_000_000) -> None:
    """Menghasilkan dataset log fin-tech dummy dalam format CSV."""
    print(f"[*] Menghasilkan {n_rows:,} baris synthetic dataset ke: {file_path}...")
    merchant_pool = [f"MERCHANT_{i:04d}" for i in range(500)]
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("transaction_id,merchant_code,response_code,payload_signature,latency_ms\n")
        for i in range(n_rows):
            t_id = str(uuid.uuid4())
            m_code = merchant_pool[i % 500]
            # Injeksi missing values pada response_code (15% nulls)
            resp = "" if i % 7 == 0 else str(200 if i % 2 == 0 else 500)
            sig = hashlib.sha256(f"{t_id}-{m_code}".encode()).hexdigest()
            lat = str(10 + (i % 250))
            f.write(f"{t_id},{m_code},{resp},{sig},{lat}\n")
    print("[*] Generasi file CSV selesai.")

def execute_pipeline_legacy(file_path: str) -> Tuple[pd.DataFrame, float, float]:
    """Eksekusi pipeline analitik menggunakan Pandas 1.x Legacy Style (NumPy backend)."""
    gc.collect()
    tracemalloc.start()
    t_start = time.perf_counter()

    # Ingestion konvensional
    df = pd.read_csv(file_path)

    # Transformasi & Agregasi
    # Filter transaksi sukses
    df_filtered = df[df["response_code"] == 200].copy()
    
    # Operasi teks: ekstraksi substring dari signature
    df_filtered["sig_prefix"] = df_filtered["payload_signature"].str.slice(0, 8)
    
    # Agregasi performa per merchant
    agg_result = df_filtered.groupby("merchant_code").agg(
        total_volume=("transaction_id", "count"),
        mean_latency=("latency_ms", "mean")
    ).reset_index()

    t_duration = time.perf_counter() - t_start
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    peak_mb = peak_memory / (1024 * 1024)
    return agg_result, t_duration, peak_mb

def execute_pipeline_modern(file_path: str) -> Tuple[pd.DataFrame, float, float]:
    """Eksekusi pipeline analitik menggunakan Pandas 2.x & PyArrow engine."""
    gc.collect()
    tracemalloc.start()
    t_start = time.perf_counter()

    # Ingestion modern: Arrow engine & PyArrow backend dtypes
    df = pd.read_csv(
        file_path, 
        engine="pyarrow", 
        dtype_backend="pyarrow"
    )

    # Transformasi & Agregasi: Vektor Arrow SIMD
    df_filtered = df[df["response_code"] == 200]
    
    # Zero-copy string slicing menggunakan engine PyArrow
    df_filtered["sig_prefix"] = df_filtered["payload_signature"].str.slice(0, 8)
    
    agg_result = df_filtered.groupby("merchant_code").agg(
        total_volume=("transaction_id", "count"),
        mean_latency=("latency_ms", "mean")
    ).reset_index()

    t_duration = time.perf_counter() - t_start
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    peak_mb = peak_memory / (1024 * 1024)
    return agg_result, t_duration, peak_mb

def main():
    temp_dir = tempfile.mkdtemp()
    csv_path = os.path.join(temp_dir, "fintech_tx_stream.csv")
    
    try:
        # 1. Bangun Data Mentah (1 Juta Baris untuk Menguji Alokasi Memori Signifikan)
        generate_mock_csv(csv_path, n_rows=1_000_000)

        # 2. Jalankan Pipeline Legacy
        print("\n[+] Menjalankan Pipeline Legacy (NumPy Engine)...")
        res_legacy, time_legacy, mem_legacy = execute_pipeline_legacy(csv_path)
        print(f"    - Waktu Eksekusi : {time_legacy:.2f} detik")
        print(f"    - Penggunaan RAM : {mem_legacy:.2f} MB")

        # 3. Jalankan Pipeline Modern
        print("\n[+] Menjalankan Pipeline Modern (Pandas 2.x + PyArrow Engine)...")
        res_modern, time_modern, mem_modern = execute_pipeline_modern(csv_path)
        print(f"    - Waktu Eksekusi : {time_modern:.2f} detik")
        print(f"    - Penggunaan RAM : {mem_modern:.2f} MB")

        # 4. Validasi Ekuivalensi Numerik
        pd.testing.assert_frame_equal(
            res_legacy.sort_values("merchant_code").reset_index(drop=True),
            res_modern.astype({"total_volume": "int64", "mean_latency": "float64"})
                      .sort_values("merchant_code").reset_index(drop=True),
            check_dtype=False
        )
        print("\n[V] Validasi Ekuivalensi: Hasil agregasi kedua mesin 100% identik secara numerik.")

        # 5. Laporan Metrik Efisiensi
        print("\n" + "="*50)
        print("RINGKASAN EFISIENSI ARSITEKTUR ARROW")
        print("="*50)
        print(f"Efisiensi Pengurangan Memori : {((mem_legacy - mem_modern) / mem_legacy) * 100:.2f}%")
        print(f"Akselerasi Pemrosesan Total  : {time_legacy / time_modern:.2f}x lebih cepat")
        print("="*50)

    finally:
        # Pembersihan Artifact
        if os.path.exists(csv_path):
            os.remove(csv_path)
        os.rmdir(temp_dir)
        print("[*] Pembersihan file temporer berhasil.")

if __name__ == "__main__":
    main()
