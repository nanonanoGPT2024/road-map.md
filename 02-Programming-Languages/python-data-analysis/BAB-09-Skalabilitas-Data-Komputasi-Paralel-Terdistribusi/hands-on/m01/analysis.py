"""
Production Pipeline: Out-Of-Core Network Telemetry Analytics Engine.
Menggunakan Dask Distributed, Apache Arrow, dan Parquet Target Partitioning.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import dask.dataframe as dd
from dask.distributed import Client, LocalCluster


def generate_synthetic_telemetry_dataset(output_dir: Path, num_files: int = 8, rows_per_file: int = 150_000) -> None:
    """
    Generator dataset telemetri tiruan berskala multi-partisi ke format Parquet.
    Mensimulasikan data mentah yang melebihi buffer memori standar.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    device_pool = [f"dev-gw-{i:04d}" for i in range(1, 101)]
    region_pool = ["ap-southeast-1", "ap-southeast-2", "eu-central-1", "us-east-1"]

    print(f"[DataGen] Mengenerate {num_files} partisi data di: {output_dir} ...")
    
    np.random.seed(42)
    for file_idx in range(num_files):
        # Alokasi matriks data sintetik
        ts_start = pd.Timestamp("2026-03-30 00:00:00").value // 10**9
        ts_end = pd.Timestamp("2026-03-30 23:59:59").value // 10**9
        
        timestamps = pd.to_datetime(np.random.randint(ts_start, ts_end, size=rows_per_file), unit="s")
        devices = np.random.choice(device_pool, size=rows_per_file)
        regions = np.random.choice(region_pool, size=rows_per_file)
        bytes_sent = np.random.exponential(scale=5000, size=rows_per_file).astype(np.int32)
        bytes_recv = np.random.exponential(scale=8000, size=rows_per_file).astype(np.int32)
        packet_loss = np.random.uniform(0.0, 0.05, size=rows_per_file)
        
        # Injeksi anomali secara terkontrol (0.5% lonjakan kegagalan jaringan)
        anomaly_mask = np.random.rand(rows_per_file) < 0.005
        packet_loss[anomaly_mask] = np.random.uniform(0.25, 0.95, size=np.sum(anomaly_mask))

        df_partition = pd.DataFrame({
            "timestamp": timestamps,
            "device_id": devices,
            "region": regions,
            "bytes_sent": bytes_sent,
            "bytes_recv": bytes_recv,
            "packet_loss_rate": packet_loss
        })

        # Kompresi tingkat produksi via snappy
        file_path = output_dir / f"telemetry_part_{file_idx:03d}.parquet"
        df_partition.to_parquet(file_path, engine="pyarrow", compression="snappy", index=False)
        
    print("[DataGen] Penyiapan raw telemetry chunks selesai.")


def execute_scalable_pipeline(source_dir: Path, target_dir: Path) -> None:
    """
    Eksekusi alur pemrosesan data out-of-core terdistribusi.
    """
    # 1. Konfigurasi Kluster Lokal Terisolasi
    # Menetapkan 4 worker proses, masing-masing dibatasi 1 thread per proses
    # untuk menghindari thread contention dan isolasi memori strict 2GB.
    cluster = LocalCluster(
        n_workers=4,
        threads_per_worker=1,
        memory_limit="2GB",
        processes=True,
        dashboard_address=":8787",
        silence_logs=30
    )
    client = Client(cluster)
    print(f"[Orchestration] Distributed Cluster Berjalan: Dashboard di {client.dashboard_link}")

    try:
        # 2. Lazy Read Menggunakan PyArrow Dtypes Backend
        print("[Engine] Membaca Partisi Parquet secara Lazy via Apache Arrow...")
        telemetry_ddf = dd.read_parquet(
            source_dir / "*.parquet",
            engine="pyarrow",
            dtype_backend="pyarrow"
        )

        # 3. Validasi Metadata Partisi & Shape Inspeksi Lazy
        print(f"[DAG Plan] Jumlah Partisi Terbaca: {telemetry_ddf.npartitions}")
        print(f"[Schema Detection]\n{telemetry_ddf.dtypes}")

        # 4. Pipeline Transformasi & Filtering Out-of-Core
        # Mendeteksi event network latency kritis
        anomaly_ddf = telemetry_ddf[telemetry_ddf["packet_loss_rate"] > 0.15]

        # 5. Agregasi Terdistribusi Multi-Dimensi (Wide Dependency Shuffle)
        # Menghitung total volume transfer dan rata-rata packet loss per region dan device
        aggregated_metrics = (
            anomaly_ddf.groupby(["region", "device_id"])
            .agg(
                incident_count=("packet_loss_rate", "count"),
                avg_packet_loss=("packet_loss_rate", "mean"),
                total_bytes_sent=("bytes_sent", "sum"),
                total_bytes_recv=("bytes_recv", "sum")
            )
            .reset_index()
        )

        # Penambahan Feature Engineering Terkomputasi
        aggregated_metrics["total_network_traffic_mb"] = (
            aggregated_metrics["total_bytes_sent"] + aggregated_metrics["total_bytes_recv"]
        ) / (1024 * 1024)

        # 6. Materialisasi & Penulisan Terdistribusi ke Parquet Partisi Target
        print(f"[Materialization] Mengekspor hasil agregasi ke {target_dir}...")
        if target_dir.exists():
            shutil.rmtree(target_dir)

        # Tulis langsung partisi terdistribusi tanpa menarik seluruh data ke master driver RAM
        aggregated_metrics.to_parquet(
            target_dir,
            engine="pyarrow",
            compression="zstd",
            partition_on=["region"],
            write_index=False
        )
        print("[Materialization] Ekspor Parquet terdistribusi sukses.")

        # 7. Validasi Parsial Menggunakan Head (Hanya menarik representasi kecil ke Driver)
        sample_driver_view = aggregated_metrics.head(5)
        print("\n[Preview 5 Rekaman Teratas dari Graph Materialisasi]:")
        print(sample_driver_view)

    finally:
        # Graceful cleanup koneksi cluster
        client.close()
        cluster.close()
        print("[Orchestration] Distributed Cluster ditutup secara aman.")


if __name__ == "__main__":
    base_workspace = Path(tempfile.mkdtemp(prefix="distributed_scale_lab_"))
    raw_telemetry_path = base_workspace / "raw_telemetry"
    curated_analytics_path = base_workspace / "curated_network_metrics"

    try:
        generate_synthetic_telemetry_dataset(raw_telemetry_path, num_files=6, rows_per_file=100_000)
        execute_scalable_pipeline(raw_telemetry_path, curated_analytics_path)
    finally:
        # Hapus direktori sementara setelah simulasi tuntas
        shutil.rmtree(base_workspace, ignore_errors=True)
        print(f"[Cleanup] Direktori isolasi lab {base_workspace} berhasil dibersihkan.")
