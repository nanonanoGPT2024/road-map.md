import os
import shutil
import structlog
import pandas as pd
import pandera as pa
from pandera.typing import Series
from datetime import datetime, timezone
import pyarrow as pa_arrow
import pyarrow.parquet as pq

# Konfigurasi Structured Logging
logger = structlog.get_logger()

# ---------------------------------------------------------
# 1. Definisi Kontrak Data Transaksi
# ---------------------------------------------------------
class ProductionTransactionContract(pa.DataFrameModel):
    transaction_id: Series[str] = pa.Field(
        nullable=False,
        unique=True,
        regex=r"^TXN-[A-Z0-9]{8}$"
    )
    merchant_id: Series[str] = pa.Field(nullable=False, regex=r"^MCH-[0-9]{4}$")
    user_id: Series[int] = pa.Field(nullable=False, ge=1)
    amount_cents: Series[int] = pa.Field(nullable=False, gt=0, le=500_000_000)
    currency: Series[str] = pa.Field(nullable=False, isin=["IDR", "USD"])
    created_at: Series[pd.Timestamp] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = True


# ---------------------------------------------------------
# 2. Pipeline Engine Berbasis Isolasi Data
# ---------------------------------------------------------
class ResilientIngestionPipeline:
    def __init__(self, failure_threshold_pct: float = 5.0):
        self.failure_threshold_pct = failure_threshold_pct
        self.clean_dir = "./data_lake/silver/transactions"
        self.dlq_dir = "./data_lake/quarantine/dlq_transactions"
        self._ensure_storage()

    def _ensure_storage(self):
        os.makedirs(self.clean_dir, exist_ok=True)
        os.makedirs(self.dlq_dir, exist_ok=True)

    def process_batch(self, raw_df: pd.DataFrame, batch_id: str) -> dict:
        total_records = len(raw_df)
        logger.info("memulai_pemrosesan_batch", batch_id=batch_id, total_records=total_records)

        if total_records == 0:
            logger.warn("batch_kosong", batch_id=batch_id)
            return {"status": "SKIPPED", "clean": 0, "quarantine": 0}

        try:
            # Validasi Skema Menyeluruh
            clean_df = ProductionTransactionContract.validate(raw_df, lazy=True)
            # Jika lolos tanpa exception, seluruh baris valid
            self._write_clean_data(clean_df, batch_id)
            logger.info("batch_valid_penuh", batch_id=batch_id, count=len(clean_df))
            return {"status": "SUCCESS", "clean": len(clean_df), "quarantine": 0}

        except pa.errors.SchemaErrors as ex:
            # Ambil indeks baris yang mengalami error data-level
            data_error_indices = set()
            for err in ex.schema_errors:
                if err.reason_code == pa.errors.SchemaErrorReason.DATAFRAME_CHECK:
                    # Menangkap kegagalan level DataFrame
                    pass
            
            # Ekstraksi indeks yang gagal dari tabel failure_cases
            failure_df = ex.failure_cases
            if "index" in failure_df.columns:
                failed_indices = failure_df["index"].dropna().astype(int).unique().tolist()
                data_error_indices.update(failed_indices)

            # Hitung rasio kegagalan
            error_count = len(data_error_indices)
            error_rate = (error_count / total_records) * 100.0

            logger.error(
                "validasi_kontrak_gagal",
                batch_id=batch_id,
                error_records=error_count,
                error_rate=f"{error_rate:.2f}%",
                threshold=f"{self.failure_threshold_pct}%"
            )

            # Circuit Breaker Logic
            if error_rate > self.failure_threshold_pct:
                logger.critical(
                    "circuit_breaker_diaktifkan",
                    batch_id=batch_id,
                    message="Rasio data korup melebihi ambang batas aman. Ingestion dihentikan!"
                )
                raise RuntimeError(f"Circuit Breaker Triggered: {error_rate:.2f}% errors exceed limit.")

            # Splitting Data: Clean vs Corrupt
            corrupt_df = raw_df.loc[list(data_error_indices)].copy()
            clean_df = raw_df.drop(index=list(data_error_indices)).copy()

            # Melakukan coerce & validasi ulang pada subset yang bersih
            validated_clean_df = ProductionTransactionContract.validate(clean_df, lazy=False)

            # Persistensi Data
            self._write_clean_data(validated_clean_df, batch_id)
            self._write_quarantine_data(corrupt_df, failure_df, batch_id)

            return {
                "status": "PARTIAL_SUCCESS",
                "clean": len(validated_clean_df),
                "quarantine": len(corrupt_df)
            }

    def _write_clean_data(self, df: pd.DataFrame, batch_id: str):
        file_path = os.path.join(self.clean_dir, f"clean_{batch_id}.parquet")
        table = pa_arrow.Table.from_pandas(df)
        pq.write_table(table, file_path)
        logger.info("clean_data_persisted", path=file_path, rows=len(df))

    def _write_quarantine_data(self, corrupt_df: pd.DataFrame, error_report: pd.DataFrame, batch_id: str):
        corrupt_path = os.path.join(self.dlq_dir, f"dlq_{batch_id}.parquet")
        err_meta_path = os.path.join(self.dlq_dir, f"dlq_meta_{batch_id}.parquet")
        
        # Tambahkan metadata ingest pada DLQ
        corrupt_df["_ingested_at"] = datetime.now(timezone.utc)
        corrupt_df["_batch_id"] = batch_id

        corrupt_table = pa_arrow.Table.from_pandas(corrupt_df)
        pq.write_table(corrupt_table, corrupt_path)

        meta_table = pa_arrow.Table.from_pandas(error_report)
        pq.write_table(meta_table, err_meta_path)
        
        logger.info("dlq_data_persisted", path=corrupt_path, meta_path=err_meta_path)


# ---------------------------------------------------------
# 3. Simulasi Eksekusi Pipeline
# ---------------------------------------------------------
if __name__ == "__main__":
    # Setup data simulasi (10 baris: 9 valid, 1 korup -> 10% error)
    data = {
        "transaction_id": [f"TXN-ABC0000{i}" for i in range(1, 10)] + ["TXN-INVALID_ID"],
        "merchant_id": [f"MCH-{1000 + i}" for i in range(1, 10)] + ["MCH-9999"],
        "user_id": [100 + i for i in range(1, 10)] + [-1], # -1 melanggar ge=1
        "amount_cents": [50000 * i for i in range(1, 10)] + [0], # 0 melanggar gt=0
        "currency": ["IDR"] * 9 + ["YEN"], # YEN melanggar isin
        "created_at": [datetime.now(timezone.utc).isoformat()] * 10
    }
    batch_df = pd.DataFrame(data)

    # Inisialisasi pipeline dengan threshold toleransi 15%
    pipeline = ResilientIngestionPipeline(failure_threshold_pct=15.0)
    
    print("\n--- Eksekusi Batch Pertama (Toleransi 15%) ---")
    result = pipeline.process_batch(batch_df, batch_id="BATCH_20260330_01")
    print("Hasil Pemrosesan:", result)

    print("\n--- Eksekusi Batch Kedua (Ambang Batas Ketat 5% -> Memicu Circuit Breaker) ---")
    strict_pipeline = ResilientIngestionPipeline(failure_threshold_pct=5.0)
    try:
        strict_pipeline.process_batch(batch_df, batch_id="BATCH_20260330_02")
    except RuntimeError as e:
        print("Pipeline berhasil mengaktifkan Circuit Breaker secara aman:")
        print(e)
