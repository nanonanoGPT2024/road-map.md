import os
import glob
import tempfile
import polars as pl
import numpy as np
from datetime import datetime, timedelta

def generate_production_mock_data(base_dir: str, num_files: int = 5, rows_per_file: int = 500_000):
    """Menghasilkan beberapa partisi file Parquet yang mensimulasikan log transaksi."""
    os.makedirs(base_dir, exist_ok=True)
    np.random.seed(1337)
    
    start_date = datetime(2026, 1, 1)
    
    for i in range(num_files):
        timestamps = [start_date + timedelta(seconds=int(x)) for x in np.random.randint(0, 86400 * 30, size=rows_per_file)]
        df_chunk = pl.DataFrame({
            "tx_hash": [f"0x{j:016x}" for j in np.random.randint(0, 10**12, size=rows_per_file)],
            "timestamp": timestamps,
            "user_id": np.random.randint(100_000, 200_000, size=rows_per_file),
            "merchant_id": np.random.randint(1_000, 5_000, size=rows_per_file),
            "amount": np.random.exponential(scale=150.0, size=rows_per_file),
            "is_flagged_fraud": np.random.choice([True, False], size=rows_per_file, p=[0.01, 0.99]),
            "device_os": np.random.choice(["Android", "iOS", "Web", "Unknown"], size=rows_per_file),
            # Kolom ekstra besar untuk mensimulasikan beban I/O
            "raw_payload": ["metadata_payload_token_string_simulation" for _ in range(rows_per_file)]
        })
        file_path = os.path.join(base_dir, f"partition_202601_{i}.parquet")
        df_chunk.write_parquet(file_path, compression="snappy")
    print(f"Data simulasi produksi berhasil dibuat di: {base_dir}")

def process_fraud_analytics_pipeline(input_glob: str, output_sink: str):
    """
    Pipeline Out-of-Core yang mengeksekusi agregasi risiko merchant 
    tanpa memuat metadata payload yang tidak diperlukan ke dalam RAM.
    """
    print(f"Memulai lazy scanning pada pattern: {input_glob}")
    
    # 1. SCAN DENGAN SKEMA EKSPILISIT DAN WILDCARDS
    lazy_source = pl.scan_parquet(input_glob)

    # 2. DEFINISI LOGICAL WORKFLOW
    # Menerapkan projection pushdown (hanya pilih kolom esensial)
    # Menerapkan filter predikat (pembatasan waktu dan status validitas)
    pipeline = (
        lazy_source
        .select([
            pl.col("timestamp"),
            pl.col("user_id"),
            pl.col("merchant_id"),
            pl.col("amount"),
            pl.col("is_flagged_fraud"),
            pl.col("device_os")
        ])
        .filter(pl.col("amount") > 5.0)  # Menghapus transaksi micro noise
        .with_columns([
            pl.col("timestamp").dt.date().alias("tx_date"),
            (pl.col("amount") * 1.05).alias("amount_with_surcharge") # Kalkulasi vectorized
        ])
        .group_by(["merchant_id", "device_os"])
        .agg([
            pl.len().alias("total_tx_count"),
            pl.col("amount").sum().alias("gross_volume"),
            pl.col("is_flagged_fraud").sum().alias("fraud_instances"),
            (pl.col("is_flagged_fraud").mean() * 100.0).alias("fraud_rate_percentage"),
            pl.col("user_id").n_unique().alias("unique_buyers")
        ])
        .filter(pl.col("total_tx_count") > 100) # Hanya merchant dengan volume memadai
        .sort(["fraud_rate_percentage", "gross_volume"], descending=[True, True])
    )

    # 3. STREAMING EXECUTION SINK KE DISK
    # Polars Streaming Engine memproses data secara out-of-core
    print("Mengeksekusi physical plan melalui Streaming Engine...")
    
    # Eksekusi streaming langsung ke Parquet sink tanpa load seluruh data ke RAM
    pipeline.sink_parquet(
        output_sink, 
        compression="zstd",
        maintain_order=False
    )
    print(f"Eksekusi pipeline selesai. Output disimpan di: {output_sink}")

if __name__ == "__main__":
    work_dir = tempfile.mkdtemp()
    data_dir = os.path.join(work_dir, "fraud_logs")
    output_file = os.path.join(work_dir, "merchant_risk_profile.parquet")
    
    try:
        generate_production_mock_data(data_dir, num_files=4, rows_per_file=250_000)
        process_fraud_analytics_pipeline(
            input_glob=os.path.join(data_dir, "*.parquet"),
            output_sink=output_file
        )
        
        # Validasi output sink
        validation_df = pl.read_parquet(output_file)
        print("\n=== PREVIEW MERCHANT RISK PROFILES ===")
        print(validation_df.head(10))
        
    finally:
        # Cleanup resource
        import shutil
        shutil.rmtree(work_dir)
        print("Direktori temporer dibersihkan.")
