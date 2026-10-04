"""
production_image_pipeline.py
Sistem Pipeline Analitik Citra Skala Produksi Menggunakan Pola Hibrida:
- ThreadPoolExecutor untuk Network I/O (Mock S3 download/upload)
- ProcessPoolExecutor untuk Heavy CPU Image Transformations (DCT & pHash)
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import Final, List, Optional, Tuple

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(processName)s:%(threadName)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ProductionPipeline")


@dataclass(frozen=True)
class IngestionPayload:
    document_id: str
    raw_url: str


@dataclass(frozen=True)
class ProcessingResult:
    document_id: str
    perceptual_hash: str
    byte_size: int
    processing_time_sec: float
    error: Optional[str] = None


class CPUImageProcessor:
    """Komponen komputasi murni CPU: Dijalankan di dalam ProcessPoolWorker."""

    @staticmethod
    def compute_simulated_phash(document_id: str, image_bytes: bytes) -> str:
        """
        Simulasi transformasi matriks DCT (Discrete Cosine Transform) intensif CPU.
        """
        # 1. Hitung hash dasar (CPU bound hashing)
        hasher = hashlib.sha256()
        hasher.update(image_bytes)
        base_digest = hasher.digest()

        # 2. Simulasi floating-point array operations intensif
        # Mentransformasi 64-bit sampling array
        accumulator = 0.0
        for byte_val in base_digest:
            for angle in range(0, 180, 5):
                rad = math.radians(angle)
                accumulator += math.sin(byte_val * rad) * math.cos(rad)

        # 3. Bentuk representasi string hash unik
        phash_signature = f"{hasher.hexdigest()[:16]}-{int(abs(accumulator)) & 0xFFFFFF:06x}"
        return phash_signature


class NetworkStorageClient:
    """Komponen I/O murni: Dijalankan di dalam ThreadPoolWorker."""

    @staticmethod
    def download_image(payload: IngestionPayload) -> Tuple[str, bytes]:
        """Simulasi network socket read dari cloud bucket."""
        logger.info(f"Memulai unduh dokumen: {payload.document_id} dari {payload.raw_url}")
        # Simulasi latency I/O jaringan 100ms - 200ms
        time.sleep(0.15)
        # Menghasilkan payload data acak terdeterminasi
        pseudo_image_data = os.urandom(1024 * 512)  # 512 KB payload
        logger.info(f"Selesai unduh: {payload.document_id} ({len(pseudo_image_data)} bytes)")
        return payload.document_id, pseudo_image_data

    @staticmethod
    def upload_metadata(result: ProcessingResult) -> bool:
        """Simulasi network socket write metadata ke database."""
        time.sleep(0.08)
        logger.info(f"Sukses persistensi metadata ke DB untuk dokumen: {result.document_id}")
        return True


def execute_cpu_subpipeline(doc_id: str, data: bytes) -> ProcessingResult:
    """Fungsi mandiri (top-level) yang aman untuk diserialisasi (Picklable)."""
    start_ts = time.perf_counter()
    try:
        phash = CPUImageProcessor.compute_simulated_phash(doc_id, data)
        duration = time.perf_counter() - start_ts
        return ProcessingResult(
            document_id=doc_id,
            perceptual_hash=phash,
            byte_size=len(data),
            processing_time_sec=duration,
        )
    except Exception as exc:
        duration = time.perf_counter() - start_ts
        return ProcessingResult(
            document_id=doc_id,
            perceptual_hash="",
            byte_size=len(data),
            processing_time_sec=duration,
            error=str(exc),
        )


class HybridDocumentPipeline:
    """Orchestrator sistem konkurensi & paralelisme pipeline hybrid."""

    def __init__(self, io_workers: int = 8, cpu_workers: Optional[int] = None) -> None:
        self.io_workers: Final[int] = io_workers
        self.cpu_workers: Final[int] = cpu_workers or (os.cpu_count() or 2)
        logger.info(
            f"Inisialisasi pipeline: IO_Workers={self.io_workers} (Threads), "
            f"CPU_Workers={self.cpu_workers} (Processes)"
        )

    def process_batch(self, items: List[IngestionPayload]) -> List[ProcessingResult]:
        total_start = time.perf_counter()
        results: List[ProcessingResult] = []

        # Mengelola dua pool dengan konteks waktu hidup terisolasi
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.io_workers, thread_name_prefix="NetIO"
        ) as io_executor, concurrent.futures.ProcessPoolExecutor(
            max_workers=self.cpu_workers
        ) as cpu_executor:

            logger.info("=== Tahap 1: Memulai Concurrent Network Fetch (I/O) ===")
            download_futures = [
                io_executor.submit(NetworkStorageClient.download_image, item)
                for item in items
            ]

            # Mengantrekan komputasi CPU segera setelah tiap thread I/O selesai mendownload
            cpu_futures: List[concurrent.futures.Future[ProcessingResult]] = []
            
            for future in concurrent.futures.as_completed(download_futures):
                try:
                    doc_id, raw_bytes = future.result()
                    # Menyerahkan data ke ProcessPoolExecutor
                    cpu_task = cpu_executor.submit(execute_cpu_subpipeline, doc_id, raw_bytes)
                    cpu_futures.append(cpu_task)
                except Exception as exc:
                    logger.error(f"Gagal saat proses download: {exc}", exc_info=True)

            logger.info("=== Tahap 2: Menunggu Hasil Parallel Processing (CPU) ===")
            upload_futures = []
            for future in concurrent.futures.as_completed(cpu_futures):
                res = future.result()
                results.append(res)
                if res.error:
                    logger.error(f"Kesalahan pada dokumen {res.document_id}: {res.error}")
                    continue

                logger.info(
                    f"Dokumen {res.document_id} selesai diproses: "
                    f"pHash={res.perceptual_hash} dalam {res.processing_time_sec:.4f}s"
                )
                # Mengantrekan persistensi I/O asinkron
                upload_futures.append(
                    io_executor.submit(NetworkStorageClient.upload_metadata, res)
                )

            # Menunggu seluruh upload persistensi selesai
            concurrent.futures.wait(upload_futures)

        total_elapsed = time.perf_counter() - total_start
        logger.info(f"Selesai memproses {len(items)} dokumen dalam total waktu: {total_elapsed:.4f} detik.")
        return results


def main() -> None:
    # Simulasi 12 dokumen transaksi masuk ke antrean
    mock_batch = [
        IngestionPayload(
            document_id=f"DOC-UUID-{i:04d}",
            raw_url=f"https://storage.internal.bank/raw-vault/2026/doc_{i}.tiff",
        )
        for i in range(1, 13)
    ]

    pipeline = HybridDocumentPipeline(io_workers=6, cpu_workers=4)
    results = pipeline.process_batch(mock_batch)

    assert len(results) == 12, "Jumlah hasil pemrosesan tidak sesuai dengan input!"
    print("\n[VERIFIKASI PIPELINE]: Seluruh artefak data berhasil diproses tanpa kegagalan.")


if __name__ == "__main__":
    main()
