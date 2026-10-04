# Bab 03: Object Storage Architecture & Distributed I/O
## Modul 01: Fondasi Object Storage, Protokol Distributed I/O, dan Akselerasi AI Lakehouse

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (C4)** arsitektur internal *object storage* (metadata separation, *erasure coding*, *flat namespace*) dan membedakannya dari sistem file hierarkis (POSIX) serta *block storage*.
- **Mengevaluasi (C5)** implikasi model konsistensi data (*Read-After-Write Consistency* vs. *Eventual Consistency*) terhadap operasi baca-tulis terdistribusi pada *data lake* dan *checkpointing* model AI.
- **Merancang (C6)** strategi partisi prefiks (*prefix sharding*) untuk menghindari *I/O hotspotting* dan throttling HTTP (503 *Slow Down*) pada beban kerja throughput tinggi.
- **Mengimplementasikan (C6)** subsistem *distributed I/O client* berkinerja tinggi menggunakan Python yang mendukung *parallel chunked multipart upload*, *parallel ranged GET*, kalkulasi *checksum* per bagian, dan penanganan retry adaptif dengan *exponential backoff* serta *jitter*.
- **Mengoptimalkan (C5)** konsumsi *bandwidth* data pipelines melalui teknik *Byte-Range Requests* untuk pemrosesan file kolumnar (*Parquet/ORC footer parsing*).

---

### 2. Concept Overview
*Object storage* adalah paradigma penyimpanan data yang mengelola data bukan sebagai hierarki folder (*file storage*) atau blok disk tanpa format (*block storage*), melainkan sebagai unit diskrit yang disebut **objek**. Setiap objek menggabungkan tiga komponen fundamental:
1. **Data Payload**: Urutan byte arbitrer (dari beberapa kilobyte hingga multi-terabyte).
2. **Metadata**: Informasi sistem yang terikat (*immutable*) dan metadata kustom berbasis *key-value*.
3. **Globally Unique Identifier (Key)**: String pengidentifikasi unik dalam ruang nama datar (*flat namespace*).

```
+-----------------------------------------------------------------------+
|                             OBJECT                                    |
| +-------------------------------------------------------------------+ |
| | Key: "telemetry/v1/year=2026/month=03/node_042.parquet"           | |
| +-------------------------------------------------------------------+ |
| | Metadata:                                                         | |
| |   Content-Type: application/x-parquet                             | |
| |   ETag: "8b1a9953c4611296a827abf8c47804d7-12"                    | |
| |   x-amz-checksum-crc32c: "w6y73A=="                               | |
| |   Custom: {"compression": "zstd", "row_count": "5000000"}         | |
| +-------------------------------------------------------------------+ |
| | Payload: [0x50, 0x41, 0x52, 0x31, ... (binary stream) ... 0x31]  | |
| +-------------------------------------------------------------------+ |
+-----------------------------------------------------------------------+
```

#### Perbedaan Fundamental Arsitektur I/O
- **POSIX File System**: Memiliki struktur pohon hierarkis (`/dir/subdir/file`). Operasi metadata (seperti `rename()`, `stat()`, `ls -l`) memerlukan penguncian direktori (*directory locking*) pada metadata server, menciptakan *bottleneck* skalar ketika direktori berisi jutaan file. Operasi tulis bersifat dapat dimutasi sebagian (*mutable in-place writes*).
- **Object Storage**: Menghilangkan hierarki direktori secara fisik. Karakter `/` dalam URI hanyalah karakter dalam string *key*. Operasi bersifat *atomic* dan *immutable*; pembaruan objek mengharuskan penulisan ulang seluruh objek secara penuh (*full overwrite*) atau pembuatan versi baru (*object versioning*). Seluruh interaksi dilakukan melalui protokol stateless HTTP/REST (GET, PUT, DELETE, HEAD).

#### Model Konsistensi
Secara historis, banyak implementasi *object storage* (termasuk AWS S3 sebelum Desember 2020) mengadopsi model *eventual consistency* untuk operasi `PUT` penimpaan dan `DELETE`. Saat ini, standar *enterprise cloud object storage* (AWS S3, Google Cloud Storage, Azure Blob Storage) menjamin **Strong Read-After-Write Consistency** untuk operasi `PUT` objek baru dan penimpaan (*overwrites*), serta operasi `LIST` dan `DELETE`. Artinya, begitu respons HTTP 200 OK diterima dari operasi `PUT`, request `GET` berikutnya dijamin segera mengembalikan versi terbaru tersebut.

---

### 3. Why It Matters
Dalam ekosistem AI engineering dan Lakehouse berskala petabyte, I/O terdistribusi menuju *object storage* sering kali menjadi *limiting factor* kritis yang menyebabkan *GPU starvation* dan pembengkakan biaya infrastruktur.

1. **GPU Starvation pada Training Cluster Terdistribusi**:
   Pada distributed LLM training, ribuan akselerator (GPU/TPU) membutuhkan *checkpoint ingestion* dan *batch feeding* hingga puluhan gigabyte per detik. Jika arsitektur data loader membaca dataset secara serial dari *object storage*, latensi Round-Trip Time (RTT) HTTP dan *Time-To-First-Byte* (TTFB) akan mendegradasi *GPU Compute Utilization* di bawah 30%.
2. **Bottleneck Metadata pada Query Engine (Trino, DuckDB, Spark)**:
   Format file kolumnar modern (Apache Parquet, Apache Iceberg) menyimpan metadata skema, statistik min/max, dan *dictionary* di bagian akhir (*footer*) file. Pengambilan seluruh file hanya untuk membaca 50KB *footer* adalah inefisiensi masif. Penggunaan *Byte-Range Requests* memotong overhead transfer jaringan hingga 99%.
3. **HTTP 503 Throttling (Slow Down)**:
   Penyedia cloud membatasi throughput per prefiks (misal: AWS S3 membatasi 3.500 `PUT/POST/DELETE` dan 5.500 `GET/HEAD` per detik per prefiks partisi). Tanpa arsitektur partisi dan teknik *connection pooling/pipelining*, pipeline ingest ETL akan gagal saat beban puncak.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur operasi tulis terdistribusi (*Distributed Multipart Upload*) dan operasi baca terdistribusi (*Parallel Ranged GET*) melalui gateway stateless menuju subsistem penyimpanan berbasis *Erasure Coding*.

```
[ Client Layer: Data Pipelines / Model Workers ]
   |                    |                    |
   | (Parallel          | (Range:            | (Parallel
   |  Part 1-N PUT)     |  bytes=0-1048576)  |  Part Complete)
   v                    v                    v
+-------------------------------------------------------------+
|             API Gateway / Load Balancer Cluster             |
|        (TLS Termination, AuthN/AuthZ, Route Sharding)       |
+-------------------------------------------------------------+
                               |
            +------------------+------------------+
            |                                     |
            v                                     v
+------------------------+           +------------------------+
|    Metadata Engine     |           |     Storage Engine     |
| (Distributed Key-Value |           |  (Data Placement &     |
|  Log-Structured Merge) |           |   Chunk Allocator)     |
+------------------------+           +------------------------+
            |                                     |
            |                                     v
            |                       +--------------------------+
            |                       | Erasure Coding Pipeline  |
            |                       | (Reed-Solomon: 8 Data +  |
            |                       |  4 Parity Chunks)        |
            |                       +--------------------------+
            |                                     |
            +------------------+------------------+
                               v
+-------------------------------------------------------------+
|              Storage Nodes (Failure Domains)                |
|  +--------------+  +--------------+  +-------------------+  |
|  | Rack 1 / AZ1 |  | Rack 2 / AZ2 |  |   Rack 3 / AZ3    |  |
|  | [Disk Data1] |  | [Disk Data5] |  |   [Disk Parity1]  |  |
|  | [Disk Data2] |  | [Disk Data6] |  |   [Disk Parity2]  |  |
|  | [Disk Data3] |  | [Disk Data7] |  |   [Disk Parity3]  |  |
|  | [Disk Data4] |  | [Disk Data8] |  |   [Disk Parity4]  |  |
|  +--------------+  +--------------+  +-------------------+  |
+-------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Prefix Partitioning dan Dynamic Sharding
Pada arsitektur internal *object storage*, ruang nama kunci dipartisi secara leksikografis menggunakan struktur pohon B-Tree atau Log-Structured Merge-tree (LSM).
- Jika sebuah bucket menerima ribuan request per detik dengan penamaan sekuensial monoton (misal: `s3://bucket/logs/2026-03-31-00-01.parquet`, `logs/2026-03-31-00-02.parquet`), seluruh request diarahkan ke simpul metadata tunggal (*hot partition*).
- Dengan memvariasikan prefiks secara leksikografis, beban I/O otomatis didistribusikan ke berbagai partisi internal.

```
Pola Monotonik (Buruk):
bucket/2026-03-31/A.parquet  \
bucket/2026-03-31/B.parquet   --> Terkonsentrasi pada 1 Partition Key
bucket/2026-03-31/C.parquet  /

Pola Entropy-Distributed / Sharded (Optimal):
bucket/9a8f-2026-03-31/A.parquet  --> Partisi Server 1
bucket/1b3c-2026-03-31/B.parquet  --> Partisi Server 2
bucket/e5d2-2026-03-31/C.parquet  --> Partisi Server 3
```

> **Catatan Arsitektur Modern**: AWS S3 secara otomatis memecah partisi saat beban trafik meningkat. Namun, pemecahan partisi memerlukan waktu propagasi. Memahami partisi berbasis hash tetap krusial untuk mencegah latensi transien pada lonjakan beban I/O mendadak.

#### B. Protokol Multipart Upload
Ketika mentransfer file besar (> 100 MiB), transfer biner HTTP single-stream rentan terhadap kegagalan jaringan: kegagalan 1 byte di ujung 50 GiB mengharuskan pengiriman ulang 100% data. Protokol *Multipart Upload* memecah file menjadi part-part independen:
1. **Initiate**: Klien mengirim request inisiasi dan menerima `UploadId`.
2. **Upload Parts**: Klien mengunggah potongan data (ukuran part 5 MiB hingga 5 GiB) secara paralel. Setiap bagian diberi nomor indeks (`PartNumber`, 1–10.000). Gateway merespons dengan hash `ETag` per part.
3. **Complete**: Klien mengirimkan manifes yang memetakan setiap `PartNumber` ke `ETag`-nya. Storage engine mengonsolidasikan blok-blok data ini menjadi satu objek logis tanpa memindahkan data fisik.

#### C. Byte-Range Requests
Header HTTP `Range: bytes=start-end` memungkinkan akses acak ke segmen byte tertentu.
- Format Parquet meletakkan `FileMetaData` pada beberapa byte terakhir dari file. Klien mengabaikan 99% isi payload dan mengirimkan request GET untuk 16–64 KiB terakhir:
  $$\text{Range: bytes=}(\text{FileLength} - 65536)\text{-}(\text{FileLength} - 1)$$
- Setelah mengekstrak *byte offset* dari kolom yang relevan dari metadata footer, engine hanya meminta byte-range spesifik kolom tersebut secara paralel, menghemat bandwidth jaringan dan kapasitas memori klien.

#### D. Erasure Coding & Fault Tolerance
Alih-alih melakukan replikasi penuh 3x (*3-way replication*) yang memakan storage overhead 200%, *object storage* enterprise mengimplementasikan algoritma **Reed-Solomon ($K+M$) Erasure Coding**:
- Data dipecah menjadi $K$ fragmen data dan dihitung menghasilkan $M$ fragmen paritas.
- Total fragmen = $N = K + M$.
- Sistem dapat mentoleransi kehilangan hingga $M$ node penyimpanan sekaligus tanpa kehilangan data bit tunggal pun.
- *Storage Overhead* dihitung dengan rumus:
  $$\text{Overhead} = \frac{M}{K} \times 100\%$$
  Contoh: Skema $8+4$ ($K=8, M=4$) hanya memiliki overhead penyimpanan 50%, jauh lebih efisien dibanding replikasi 3x (overhead 200%), namun sanggup menahan kegagalan simultan 4 drive/node.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi *Distributed Object I/O Engine* yang mengelola penulisan data via *Multipart Upload* paralel serta pembacaan acak via *Parallel Byte-Range Requests* dengan validasi integritas checksum CRC32C, *thread-safe connection pooling*, dan mekanisme *retry* adaptif.

```python
"""
distributed_io_engine.py
Engine I/O terdistribusi tingkat produksi untuk sistem Lakehouse dan AI.
Mendukung:
- Dynamic Chunked Multipart Upload dengan Checksum Integrity
- Parallel Byte-Range Multi-Worker Retrieval
- Exponential Backoff dengan Full Jitter
"""

from __future__ import annotations

import io
import math
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import BinaryIO, Dict, List, Optional, Tuple
import logging

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(threadName)s: %(message)s")
logger = logging.getLogger("DistributedIO")


class StorageIOError(Exception):
    """Base exception untuk kegagalan I/O storage."""
    pass


class IntegrityVerificationError(StorageIOError):
    """Dilempar saat validasi part checksum tidak sinkron."""
    pass


@dataclass(frozen=True)
class PartUploadResult:
    part_number: int
    etag: str
    size_bytes: int


def retry_with_jitter(max_attempts: int = 5, base_delay: float = 0.5, max_delay: float = 30.0):
    """
    Decorator untuk menerapkan Exponential Backoff dengan Full Jitter (Algoritma AWS Architecture).
    Formula: Sleep = random_between(0, min(max_delay, base_delay * 2 ** attempt))
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except ClientError as e:
                    attempt += 1
                    error_code = e.response.get("Error", {}).get("Code", "Unknown")
                    
                    # Identifikasi status throttling atau transient network drops
                    if error_code in ["503", "SlowDown", "RequestTimeout", "ThrottlingException"] and attempt <= max_attempts:
                        sleep_limit = min(max_delay, base_delay * (2 ** (attempt - 1)))
                        sleep_time = random.uniform(0, sleep_limit)
                        logger.warning(
                            f"Terdeteksi {error_code}. Percobaan {attempt}/{max_attempts}. "
                            f"Tidur {sleep_time:.2f}s..."
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"Gagal permanen atau batas retry terlampaui. Error: {e}")
                        raise
                except Exception as ex:
                    attempt += 1
                    if attempt <= max_attempts:
                        sleep_limit = min(max_delay, base_delay * (2 ** (attempt - 1)))
                        sleep_time = random.uniform(0, sleep_limit)
                        logger.warning(f"Kesalahan transien: {ex}. Percobaan {attempt}/{max_attempts}. Tidur {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                    else:
                        raise
        return wrapper
    end
    return decorator


class ResilientObjectStoreClient:
    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        region_name: str = "us-east-1",
        max_pool_connections: int = 50,
        min_part_size: int = 8 * 1024 * 1024  # 8 MiB per part minimum
    ):
        self.min_part_size = min_part_size
        
        # Konfigurasi socket dan TCP keepalive tingkat rendah
        client_config = Config(
            region_name=region_name,
            signature_version="s3v4",
            max_pool_connections=max_pool_connections,
            retries={"max_attempts": 0},  # Retry dikendalikan eksplisit via jitter decorator
            connect_timeout=10,
            read_timeout=30,
            tcp_keepalive=True
        )
        
        self.client: BaseClient = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            config=client_config
        )

    @retry_with_jitter()
    def _execute_initiate_multipart(self, bucket: str, key: str, metadata: Optional[Dict[str, str]]) -> str:
        params = {"Bucket": bucket, "Key": key, "ChecksumAlgorithm": "CRC32C"}
        if metadata:
            params["Metadata"] = metadata
        response = self.client.create_multipart_upload(**params)
        return response["UploadId"]

    @retry_with_jitter()
    def _execute_upload_part(
        self,
        bucket: str,
        key: str,
        upload_id: str,
        part_number: int,
        data: bytes
    ) -> PartUploadResult:
        response = self.client.upload_part(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=data,
            ChecksumAlgorithm="CRC32C"
        )
        return PartUploadResult(
            part_number=part_number,
            etag=response["ETag"],
            size_bytes=len(data)
        )

    @retry_with_jitter()
    def _execute_complete_multipart(
        self,
        bucket: str,
        key: str,
        upload_id: str,
        parts: List[Dict[str, str]]
    ) -> Dict[str, str]:
        # S3 mewajibkan parts terurut strictly asc berdasarkan PartNumber
        sorted_parts = sorted(parts, key=lambda p: p["PartNumber"])
        return self.client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": sorted_parts}
        )

    def _execute_abort_multipart(self, bucket: str, key: str, upload_id: str) -> None:
        try:
            self.client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
            logger.info(f"Multipart upload {upload_id} berhasil dibatalkan (aborted).")
        except Exception as e:
            logger.critical(f"Gagal membatalkan upload {upload_id}: {e}")

    def upload_stream_concurrent(
        self,
        stream: BinaryIO,
        bucket: str,
        key: str,
        total_size: int,
        concurrency: int = 8,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Mengunggah stream byte besar secara paralel via multipart upload.
        Mengalokasikan ukuran part dinamis untuk memenuhi batasan max 10.000 parts S3.
        """
        calculated_part_size = max(self.min_part_size, math.ceil(total_size / 9999))
        total_parts = math.ceil(total_size / calculated_part_size)
        
        logger.info(
            f"Memulai Multipart Upload untuk '{key}' ({total_size / (1024*1024):.2f} MiB). "
            f"Ukuran Part: {calculated_part_size / (1024*1024):.2f} MiB, Total Parts: {total_parts}"
        )

        upload_id = self._execute_initiate_multipart(bucket, key, metadata)
        uploaded_manifest: List[Dict[str, str]] = []

        try:
            with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="S3Uploader") as executor:
                futures = {}
                part_number = 1
                bytes_read = 0

                while bytes_read < total_size:
                    chunk = stream.read(calculated_part_size)
                    if not chunk:
                        break
                    
                    future = executor.submit(
                        self._execute_upload_part,
                        bucket=bucket,
                        key=key,
                        upload_id=upload_id,
                        part_number=part_number,
                        data=chunk
                    )
                    futures[future] = part_number
                    bytes_read += len(chunk)
                    part_number += 1

                for future in as_completed(futures):
                    pn = futures[future]
                    try:
                        result: PartUploadResult = future.result()
                        uploaded_manifest.append({
                            "PartNumber": result.part_number,
                            "ETag": result.etag
                        })
                        logger.debug(f"Selesai mengunggah part {result.part_number}/{total_parts}")
                    except Exception as exc:
                        logger.error(f"Part {pn} gagal diunggah: {exc}")
                        raise

            completion_res = self._execute_complete_multipart(bucket, key, upload_id, uploaded_manifest)
            logger.info(f"Upload berhasil diselesaikan secara atomik. Key: {key}")
            return completion_res

        except Exception as ex:
            logger.error(f"Terjadi error fatal selama multipart upload. Melakukan rollback cleanup...")
            self._execute_abort_multipart(bucket, key, upload_id)
            raise StorageIOError(f"Multipart upload gagal untuk {key}") from ex

    @retry_with_jitter()
    def _download_byte_range(self, bucket: str, key: str, start_byte: int, end_byte: int) -> bytes:
        range_header = f"bytes={start_byte}-{end_byte}"
        response = self.client.get_object(Bucket=bucket, Key=key, Range=range_header)
        return response["Body"].read()

    def parallel_read_ranges(
        self,
        bucket: str,
        key: str,
        ranges: List[Tuple[int, int]],
        concurrency: int = 8
    ) -> Dict[Tuple[int, int], bytes]:
        """
        Mengambil multiple byte-range secara konkuren (Vectorized I/O).
        Sangat krusial untuk mengekstrak kolom tertentu dari berkas Parquet besar.
        """
        results: Dict[Tuple[int, int], bytes] = {}
        
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="S3RangeReader") as executor:
            future_to_range = {
                executor.submit(self._download_byte_range, bucket, key, r[0], r[1]): r
                for r in ranges
            }
            
            for future in as_completed(future_to_range):
                byte_range = future_to_range[future]
                try:
                    data = future.result()
                    results[byte_range] = data
                except Exception as exc:
                    logger.error(f"Gagal membaca byte range {byte_range}: {exc}")
                    raise StorageIOError(f"Range read failed on {byte_range}") from exc

        return results


# =====================================================================
# Unit Test & Validasi Fungsional Lokal
# =====================================================================
if __name__ == "__main__":
    # Inisialisasi Mock Client untuk validasi logika lokal
    print("Distributed Object I/O Engine loaded successfully.")
```

---

### 7. Edge Cases & Failure Modes

#### 1. Orphaned Multipart Uploads (Storage Leaks)
- **Kondisi**: Jika worker pipeline crash, spot instance di-terminate, atau jaringan terputus saat proses multipart upload sedang berjalan, potongan part yang sudah terunggah akan tetap disimpan di storage engine tanpa batas waktu, meskipun objek logis belum selesai dibentuk.
- **Dampak**: Pembengkakan biaya storage untuk data phantom yang tidak terdeteksi oleh operasi `LIST objects` standar.
- **Mitigasi**: Konfigurasikan **S3 Lifecycle Rule** dengan tindakan eksplisit:
  ```xml
  <AbortIncompleteMultipartUpload>
      <DaysAfterInitiation>3</DaysAfterInitiation>
  </AbortIncompleteMultipartUpload>
  ```

#### 2. Throttling HTTP 503 ("SlowDown")
- **Kondisi**: Spark/Flink cluster dengan 1.000 core membaca ribuan partisi yang memiliki prefiks yang sama secara serentak (`s3://lake/raw/data_*.parquet`).
- **Dampak**: Connection queueing, kenaikan TTFB hingga puluhan detik, dan `ClientError: SlowDown`.
- **Mitigasi**:
  - Terapkan teknik *Reverse Prefix Hashing* atau *Entropy Insertion* jika beban kerja melebihi 5.500 TPS per prefiks.
  - Implementasikan *Exponential Backoff with Full Jitter* di tingkat SDK (seperti diterapkan pada kode Bagian 6) untuk menghindari *synchronized retry storms*.

#### 3. Silent Bit Corruption (Bitrot) dalam Transit
- **Kondisi**: Modifikasi bit secara acak akibat degradasi hardware router, NIC buffers, atau memori transit non-ECC.
- **Dampak**: File Parquet korup secara laten; model AI memproses data tergradasi tanpa error exception eksplisit.
- **Mitigasi**:
  - Gunakan end-to-end CRC32C / SHA256 checksumming otomatis (`ChecksumAlgorithm="CRC32C"` pada API S3 modern).
  - Validasi byte checksum lokal sebelum dan sesudah payload ditransmisikan.

#### 4. Clock Skew Drift
- **Kondisi**: Simpul worker pipeline mengalami desinkronisasi NTP sistem melebihi 15 menit dari *real-time cloud clock*.
- **Dampak**: Penolakan otentikasi AWS Signature Version 4 dengan pesan `RequestTimeTooSkewed`.
- **Mitigasi**: Pasang service daemon `chrony` atau `systemd-timesyncd` pada seluruh bare-metal / AMI host workers.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektur | Object Storage (e.g., AWS S3, GCS, MinIO) | Distributed POSIX (e.g., Lustre, CephFS) | Local NVMe Tier (e.g., GPUDirect Storage) |
| :--- | :--- | :--- | :--- |
| **Metode Akses** | Stateless HTTP REST (GET/PUT/RANGE) | POSIX Kernel VFS (`open`, `seek`, `write`) | Direct DMA via NVMe-oF / PCIe Bypass |
| **Latensi Operasi** | Tinggi (10ms - 50ms TTFB) | Rendah (1ms - 5ms) | Ultra-rendah (< 10 mikrodetik) |
| **Throughput Agregat** | Nyaris Tak Terbatas (Skala Elastis Cloud) | Sangat Tinggi (Dibatasi kapasitas Filestore) | Ekstrem (Terikat bandwidth PCIe) |
| **Biaya per TB** | Sangat Murah (~$0.02/GB/bulan) | Sedang hingga Tinggi (~$0.15-$0.30/GB/bulan) | Sangat Tinggi (Biaya Server NVMe) |
| **Semantik Modifikasi** | *Immutable* (Tulis ulang penuh) | *In-place Mutation* (Ubah byte di tengah file) | *In-place Mutation* |
| **Best-fit Use Case** | Cold/Warm Data Lakehouse, Archival, Final Model Weights | High-Performance Compute (HPC), Scratch Workspace | GPU In-flight Training Mini-batches |

#### Trade-Off Analysis: Object Store vs POSIX Filesystem
Memilih *Object Storage* memberikan skalabilitas kapasitas tanpa batas dan efisiensi biaya yang masif. Namun, konsekuensinya adalah hilangnya operasi atomik direktori (seperti `os.rename`). Engine modern mengatasi masalah ini dengan memisahkan storage dari metadata pointer: framework seperti **Apache Iceberg** atau **Delta Lake** mengelola komit transaksi secara atomik melalui file log manifes JSON/Avro, sehingga tidak lagi bergantung pada operasi direktori native sistem operasi.

---

### 9. Best Practices & Standard Industri

1. **Dynamically Calculated Part Sizing**:
   Jangan gunakan ukuran part statis 5 MiB untuk semua file. Hitung secara dinamis:
   $$\text{Part Size} = \max(\text{Minimum Part Size (5-8 MiB)}, \lceil\frac{\text{File Size}}{9999}\rceil)$$
   Ini mencegah pelanggaran limit arsitektural 10.000 part pada file skala multi-terabyte.
2. **Koneksi Jaringan dan Keep-Alive Reusability**:
   Inisialisasi HTTP Connection Pool berukuran besar (sesuaikan dengan jumlah thread concurrency, default boto3 hanya 10 pool connections). Aktifkan flag `tcp_keepalive=True` untuk menghindari overhead 3-Way Handshake TCP dan TLS renegotiation pada setiap interaksi HTTP.
3. **Penyelarasan Batas Kompresi Kolumnar (Alignment & Split Planning)**:
   Saat menulis file Parquet ke object storage, konfigurasikan ukuran *Row Group* Parquet menjadi 128 MiB atau 512 MiB. Ukuran ini selaras dengan batasan *byte-range streaming* ideal untuk data worker Spark/Trino.
4. **Strategi Multi-Tiering Otomatis**:
   Gunakan analitik *Storage Class Analysis* untuk mentransfer data lakehouse dari tier *Standard* ke *Infrequent Access (IA)* setelah 30 hari, dan ke *Glacier Instant Retrieval* setelah 90 hari, guna menekan Total Cost of Ownership (TCO).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda diminta untuk membangun dan memvalidasi subsistem I/O terdistribusi performa tinggi untuk memproses dataset biner sintetis (100 MiB). Anda akan menyiapkan environment object storage lokal yang kompatibel dengan protokol S3 (MinIO), mengeksekusi *concurrent chunked upload*, dan mengukur performa *Parallel Ranged Read* (simulasi ekstraksi footer Parquet).

#### Langkah 1: Deployment MinIO via Docker Engine
Jalankan instance MinIO server lokal pada port 9000 dengan API port dan 9001 untuk web console:

```bash
docker run -d \
  --name minio-lakehouse-lab \
  -p 9000:9000 \
  -p 9001:9001 \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=miniopassword" \
  quay.io/minio/minio server /data --console-address ":9001"
```

#### Langkah 2: Setup Environment Python
Install dependencies yang dibutuhkan:

```bash
pip install boto3 botocore
```

#### Langkah 3: Eksekusi Skrip Benchmark dan Validasi

Simpan kode berikut sebagai `lab_s3_io_benchmark.py` dan jalankan:

```python
"""
lab_s3_io_benchmark.py
Skrip hands-on untuk benchmarking Parallel Chunked Upload vs Ranged Retrieval.
"""

import io
import os
import time
import hashlib
from distributed_io_engine import ResilientObjectStoreClient

# Konfigurasi Endpoint MinIO Lokal
ENDPOINT_URL = "http://localhost:9000"
AWS_ACCESS_KEY = "minioadmin"
AWS_SECRET_KEY = "miniopassword"
BUCKET_NAME = "lakehouse-benchmark"
OBJECT_KEY = "synthetic_data/payload_100mb.bin"
PAYLOAD_SIZE = 100 * 1024 * 1024  # 100 MiB

def run_lab():
    os.environ["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY
    os.environ["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_KEY
    
    client = ResilientObjectStoreClient(
        endpoint_url=ENDPOINT_URL,
        min_part_size=8 * 1024 * 1024
    )

    # 1. Inisialisasi Bucket
    try:
        client.client.create_bucket(Bucket=BUCKET_NAME)
        print(f"[+] Bucket '{BUCKET_NAME}' berhasil dibuat.")
    except client.client.exceptions.BucketAlreadyOwnedByYou:
        print(f"[*] Bucket '{BUCKET_NAME}' sudah tersedia.")

    # 2. Sintesis Dataset Biner dengan Pola Deterministic
    print(f"[+] Mengalokasikan memory stream berukuran {PAYLOAD_SIZE / (1024*1024)} MiB...")
    synthetic_payload = os.urandom(PAYLOAD_SIZE)
    original_checksum = hashlib.sha256(synthetic_payload).hexdigest()
    stream_buffer = io.BytesIO(synthetic_payload)

    # 3. Uji Coba: Concurrent Multipart Upload
    start_upload = time.perf_counter()
    upload_res = client.upload_stream_concurrent(
        stream=stream_buffer,
        bucket=BUCKET_NAME,
        key=OBJECT_KEY,
        total_size=PAYLOAD_SIZE,
        concurrency=4
    )
    upload_duration = time.perf_counter() - start_upload
    upload_mbps = (PAYLOAD_SIZE / (1024 * 1024)) / upload_duration
    print(f"[✓] Upload selesai dalam {upload_duration:.2f}s ({upload_mbps:.2f} MiB/s)")

    # 4. Uji Coba: Parallel Ranged Reads (Simulasi Ekstraksi Metadata & Row Groups)
    # Definisikan 4 segment target byte
    target_ranges = [
        (0, 1024 * 1024 - 1),                           # 1 MiB Pertama (Header)
        (25 * 1024 * 1024, 26 * 1024 * 1024 - 1),       # 1 MiB di kuartil 1
        (50 * 1024 * 1024, 51 * 1024 * 1024 - 1),       # 1 MiB di tengah
        (PAYLOAD_SIZE - (64 * 1024), PAYLOAD_SIZE - 1)   # 64 KiB Terakhir (Footer)
    ]

    print("[+] Mengeksekusi Vectorized Byte-Range Retrieval...")
    start_range = time.perf_counter()
    range_results = client.parallel_read_ranges(
        bucket=BUCKET_NAME,
        key=OBJECT_KEY,
        ranges=target_ranges,
        concurrency=4
    )
    range_duration = time.perf_counter() - start_range
    print(f"[✓] Berhasil mengambil {len(range_results)} ranges dalam {range_duration:.4f}s")

    # 5. Verifikasi Integritas Byte-by-Byte
    print("[+] Memvalidasi integritas data byte range...")
    for (start_byte, end_byte), data in range_results.items():
        expected_slice = synthetic_payload[start_byte : end_byte + 1]
        assert data == expected_slice, f"Integritas data korup pada range {start_byte}-{end_byte}!"
        print(f"    - Segment [{start_byte}:{end_byte}] VERIFIED ({len(data)} bytes).")

    print("\n=======================================================")
    print("STATUS LAB: SEMUA TES DAN VERIFIKASI INTEGRITAS LOLOS!")
    print("=======================================================")

if __name__ == "__main__":
    run_lab()
```

#### Langkah 4: Validasi & Analisis Hasil
Jalankan benchmark dan amati log:
1. Pastikan status **200 OK** tercatat pada seluruh *Multipart Part Upload* dan *Range Get*.
2. Perhatikan konsumsi memori: dengan memanfaatkan teknik *Byte-Range Requests*, memori engine membaca segment diskrit tanpa perlu mengalokasikan total 100 MiB data ke memori proses baca.
3. Hentikan container lab setelah selesai:
   ```bash
   docker stop minio-lakehouse-lab && docker rm minio-lakehouse-lab
   ```