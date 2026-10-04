import os
import shutil
import psutil
import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq
import pyarrow.compute as pc

class HighPerformanceIngestionEngine:
    """
    Mesin ingesti data berkinerja tinggi yang mengalirkan file teks berukuran besar
    ke dalam penyimpanan Apache Parquet teroptimasi dengan batas memori ketat.
    """
    def __init__(self, target_base_dir: str):
        self.target_base_dir = target_base_dir
        os.makedirs(self.target_base_dir, exist_ok=True)
        
        # Mendefinisikan Canonical Target Schema untuk keamanan tipe
        self.canonical_schema = pa.schema([
            pa.field("txn_id", pa.string(), nullable=False),
            pa.field("user_id", pa.int64(), nullable=False),
            pa.field("event_time", pa.timestamp('ms'), nullable=False),
            pa.field("status", pa.dictionary(pa.int8(), pa.string()), nullable=False), # Cardinality Optimization
            pa.field("amount", pa.float64(), nullable=False),
            pa.field("region", pa.string(), nullable=False),
        ])

    def _get_process_memory_mb(self) -> float:
        """Mengambil metrik jejak alokasi RSS (Resident Set Size) proses saat ini."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)

    def process_large_csv_stream(
        self, 
        source_csv_path: str, 
        block_size_bytes: int = 64 * 1024 * 1024  # Chunk parsing 64MB
    ) -> None:
        """
        Membaca CSV dalam potongan biner, menegakkan skema kanonikal,
        dan menuliskan Row Groups Parquet secara efisien ke disk.
        """
        print(f"[*] Memulai streaming ingesti: {source_csv_path}")
        print(f"[*] Baseline Memori Awal: {self._get_process_memory_mb():.2f} MB")

        # Konfigurasi Parsing Parser CSV
        read_options = pcsv.ReadOptions(
            block_size=block_size_bytes,
            use_threads=True
        )
        
        # Konfigurasi konversi awal (semua dibaca mentah sebelum validasi lanjutan)
        convert_options = pcsv.ConvertOptions(
            column_types={
                "txn_id": pa.string(),
                "user_id": pa.int64(),
                "event_time": pa.timestamp('ms'),
                "status": pa.string(),
                "amount": pa.float64(),
                "region": pa.string(),
            }
        )

        output_parquet_file = os.path.join(self.target_base_dir, "optimized_transactions.parquet")

        writer = None
        total_rows_processed = 0

        try:
            # Membuka Streaming CSV Reader
            with pcsv.open_csv(source_csv_path, read_options=read_options, convert_options=convert_options) as reader:
                for chunk_idx, record_batch in enumerate(reader):
                    # 1. Transformasi & Validasi In-Memory
                    # Mengubah kolom 'status' menjadi Dictionary Encoded secara efisien
                    dict_status = pc.dictionary_encode(record_batch.column("status"))
                    
                    # Rekonstruksi batch terverifikasi menggunakan Arrow Tables
                    transformed_arrays = [
                        record_batch.column("txn_id"),
                        record_batch.column("user_id"),
                        record_batch.column("event_time"),
                        dict_status,
                        record_batch.column("amount"),
                        record_batch.column("region")
                    ]
                    
                    validated_batch = pa.RecordBatch.from_arrays(
                        transformed_arrays, 
                        schema=self.canonical_schema
                    )

                    # 2. Inisialisasi Parquet Writer jika iterasi pertama
                    if writer is None:
                        parquet_writer_props = pq.ParquetWriter(
                            output_parquet_file,
                            schema=self.canonical_schema,
                            compression="ZSTD",
                            compression_level=6,
                            use_dictionary=True,
                            data_page_size=1024 * 1024, # 1MB Page Size optimal untuk L2/L3 cache
                        )
                        writer = parquet_writer_props

                    # 3. Menulis batch langsung sebagai Parquet Row Group/Table
                    table_chunk = pa.Table.from_batches([validated_batch])
                    writer.write_table(table_chunk)
                    
                    total_rows_processed += validated_batch.num_rows
                    
                    if chunk_idx % 5 == 0:
                        print(
                            f" -> Batch {chunk_idx:03d} Diproses | "
                            f"Total Baris: {total_rows_processed:,} | "
                            f"Memori Proses: {self._get_process_memory_mb():.2f} MB"
                        )

        finally:
            if writer is not None:
                writer.close()
                print("[*] Parquet Writer ditutup secara aman.")

        print(f"[*] Ingesti Berhasil Selesai!")
        print(f"[*] Total Baris Ditulis : {total_rows_processed:,}")
        print(f"[*] Peak Memory Stabil  : {self._get_process_memory_mb():.2f} MB")
        print(f"[*] File Tersimpan Di   : {output_parquet_file}")


# --- KODE HARNESS UNTUK PENGUJIAN PRODUKSI ---
if __name__ == "__main__":
    TEST_DIR = "./fintech_data_landing"
    SOURCE_CSV = os.path.join(TEST_DIR, "raw_incoming_transactions.csv")
    
    # 1. Bersihkan direktori pengujian
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)

    # 2. Menghasilkan Mock Data CSV Berukuran Menengah-Besar (~500,000 Baris)
    print("[*] Mempersiapkan mock data CSV...")
    import csv
    with open(SOURCE_CSV, mode="w", newline="", encoding="utf-8") as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(["txn_id", "user_id", "event_time", "status", "amount", "region"])
        
        statuses = ["SETTLED", "REVERSED", "PENDING", "FAILED"]
        regions = ["APAC", "EMEA", "LATAM", "NA"]
        
        for i in range(500_000):
            csv_writer.writerow([
                f"TX-{i:09d}",
                10000 + (i % 5000),
                "2026-03-30 08:30:00",
                statuses[i % len(statuses)],
                round(float((i * 1.5) % 10000), 2),
                regions[i % len(regions)]
            ])

    print(f"[*] Mock Data Dibuat: {os.path.getsize(SOURCE_CSV) / (1024*1024):.2f} MB")

    # 3. Jalankan Engine Ingesti
    engine = HighPerformanceIngestionEngine(target_base_dir="./fintech_optimized_lake")
    engine.process_large_csv_stream(source_csv_path=SOURCE_CSV, block_size_bytes=16 * 1024 * 1024)
