# Kurikulum Enterprise Data Engineering
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB-03: Object Storage Architecture & Distributed I/O
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Data Engineer level Enterprise diharapkan mampu:
1. **Menganalisis dan Mengoptimalkan Topologi I/O Terdistribusi:** Menguasai mekanisme internal *Erasure Coding* (Reed-Solomon $K+M$), *bit-rot protection*, dan *metadata consistency models* untuk merancang arsitektur penyimpanan skala petabyte tanpa *single point of failure* (SPOF).
2. **Mengatasi Bottleneck Throughput HTTP/REST API:** Merancang dan mengimplementasikan sistem transfer data terdistribusi berbasis *asynchronous concurrent multipart upload* dan *parallel byte-range GET* dengan throughput saturasi link $\ge 10\text{ Gbps}$.
3. **Mencegah API Throttling & Partition Imbalance:** Merekayasa struktur *namespace* objek (skema partisi *high-entropy prefixing*) guna menghindari batas I/O provider (seperti AWS S3 3.500 `PUT`/5.500 `GET` per detik per *prefix*).
4. **Membangun Pipeline Data Zero-Loss & Zero-Memory-Leak:** Mengintegrasikan validasi integritas data berbasis *end-to-end checksum* (CRC32C / MD5 / SHA-256) dan manajemen siklus hidup upload abortif guna mencegah *cost leakage* dan *silent data corruption*.
5. **Menerapkan Enkripsi dan Kontrol Akses Skala Tinggi:** Mengonfigurasi arsitektur keamanan *Envelope Encryption* via KMS, STS ephemeral delegation, serta optimasi rute via *PrivateLink/VPC Gateway Endpoints*.

---

### 2. Prerequisite

Sebelum mendalami modul ini, praktisi wajib menguasai:
* **Networking & Transport Layer:** Konsep TCP *windowing*, *socket pooling*, TLS handshake overhead, HTTP/1.1 *pipelining* vs. HTTP/2 *multiplexing*, serta DNS *round-robin resolution*.
* **Sistem Operasi & Storage:** POSIX I/O vs. Object Storage primitives, VFS, *page cache*, *file descriptor limits* (`nofile`), serta arsitektur I/O non-blocking (`epoll`).
* **Dasar Pemrograman Concurrency:** Menguasai coroutine asynchronous (`asyncio`), *thread pool execution*, *worker-pool patterns*, dan *backpressure mechanics* pada Python atau Go.
* **Module 01:** Pemahaman mendasar tentang konsep S3/GCS API, Object ID/Key-Value layout, dan *eventual consistency* vs. *strong consistency*.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Fisik & Virtual Object Storage Node
Tidak seperti sistem file POSIX tradisional yang mengalokasikan data ke dalam blok silinder melalui *inode table*, sistem *object storage* (seperti Ceph RGW, MinIO, atau AWS S3) memisahkan data biner (payload) sepenuhnya dari metadata.

```
+-------------------------------------------------------------------------------+
|                             CLIENT APPLICATION                                |
+-------------------------------------------------------------------------------+
       |                                                         ^
       | 1. HTTP PUT /bucket/prefix/file.parquet                 | 4. HTTP 200 OK
       v                                                         | (ETag/Checksum)
+-------------------------------------------------------------------------------+
|                       API ROUTER / LOAD BALANCER                              |
+-------------------------------------------------------------------------------+
       |
       v
+-------------------------------------------------------------------------------+
|                           METADATA SUBSYSTEM                                  |
|   - Namespace Indexing (Distributed LSM-Tree / RocksDB / CockroachDB Tier)    |
|   - IAM & Bucket Policy Validation Cache                                      |
|   - Inode-less Key-to-Object Mapper                                           |
+-------------------------------------------------------------------------------+
       |
       | 2. Scatter payload chunks (Reed-Solomon RS(8,4))
       v
+-------------------------------------------------------------------------------+
|                       STORAGE ENGINE / OBJECT DISK POOL                       |
|                                                                               |
|  +----------------+  +----------------+  +----------------+  +----------------+
|  | Drive 1 (Data) |  | Drive 2 (Data) |  | Drive 3 (Data) |  | Drive 4 (Data) |
|  +----------------+  +----------------+  +----------------+  +----------------+
|  | Drive 5 (Data) |  | Drive 6 (Data) |  | Drive 7 (Data) |  | Drive 8 (Data) |
|  +----------------+  +----------------+  +----------------+  +----------------+
|  | Drive 9(Parity)|  | Drive 10(Parity|  | Drive 11(Parity|  | Drive 12(Parity|
|  +----------------+  +----------------+  +----------------+  +----------------+
+-------------------------------------------------------------------------------+
```

1. **API Router Layer:** Menerima payload melalui HTTP POST/PUT. Mengakhiri sesi TLS, memvalidasi otentikasi via Signature Version 4 (SigV4), dan mengurai header HTTP.
2. **Metadata Subsystem:** Beroperasi di atas penyimpanan terdistribusi bertipe LSM-Tree (misalnya FoundationDB atau RocksDB) yang didukung konsensus multi-Paxos atau Raft. Layer ini menetapkan ID objek yang unik secara global dan mengunci status transaksi tulis.
3. **Storage Engine Layer:** Objek dipecah menjadi fragmen-fragmen data dan paritas, lalu disebar ke seluruh disk (melalui *erasure coding pool*) menggunakan arsitektur *non-blocking disk I/O*.

#### 3.2. Erasure Coding (EC) & Bit-Rot Protection
Dalam arsitektur enterprise skala besar, replikasi data 3 arah ($3\times\text{ Replication}$) memiliki *storage overhead* sebesar 200% (efisiensi 33%). Object storage modern menggantikannya dengan **Reed-Solomon Erasure Coding $RS(K, M)$**:
* $K$: Jumlah *Data Chunks*.
* $M$: Jumlah *Parity Chunks*.
* *Total chunks* = $N = K + M$.
* *Storage amplification* = $\frac{K + M}{K}$.
* Sistem mampu bertahan dari kegagalan serentak sebanyak $M$ disk tanpa kehilangan data sama sekali.

*Bit-Rot Protection* dieksekusi melalui hashing berlapis. Setiap blok data (biasanya berukuran 4 MB) dilindungi oleh *hashing algorithm* berkinerja tinggi (seperti HighwayHash atau CRC32C-SSE4.2) pada level penyimpanan fisik. Setiap operasi pembacaan memverifikasi checksum blok secara dinamis; jika ditemukan korupsi bit (*bit flip* akibat degradasi disk magnetik atau fluktuasi voltase SSD), blok yang rusak akan langsung direkonstruksi melalui kalkulasi aljabar linear Galois Field $GF(2^8)$ memanfaatkan sisa $K$ fragmen yang sehat.

#### 3.3. Strong Consistency Engine: Cara Kerja di Balik Layar
Sejak akhir tahun 2020, sistem seperti AWS S3 menyediakan *Read-After-Write Strong Consistency* untuk seluruh request `PUT`, `LIST`, dan `DELETE` tanpa penalti performa. Mekanisme ini dicapai dengan:
* Menghapus ketergantungan pada *eventual consistency caches*.
* Operasi `PUT` baru diakui (mengembalikan `HTTP 200`) hanya setelah metadata objek dituliskan ke dalam *atomic quorum write consensus* (misalnya $W \ge \lfloor N/2 \rfloor + 1$ node metadata).
* Replikasi metadata dilakukan secara sinkron lintas zona ketersediaan (*Availability Zones*), sementara pengunggahan blok data biner diselesaikan sebelum *commit phase* metadata berakhir.

#### 3.4. Distributed I/O Bottlenecks: Prefix & Partitioning
Setiap *prefix* (jalur folder logis dalam bucket S3) didukung oleh partisi metadata internal. Jika bucket melampaui batas *request rate* (misalnya 3.500 `PUT`/`POST`/`DELETE` atau 5.500 `GET` per detik per *prefix*), sistem penyimpanan akan memicu error `HTTP 503 SlowDown`. 

Secara internal, *auto-partitioning* memecah partisi metadata berdasarkan leksikografi kunci (*lexicographical key range*). Jika aplikasi menulis data menggunakan pola sekuensial (seperti stempel waktu `/year=2026/month=03/day=30/10-00-00.parquet`), seluruh operasi tulis akan menumpuk pada satu partisi disk fisik metadata yang sama (*hot partition*), sehingga menurunkan skalabilitas sistem secara drastis.

---

### 4. Why & What

| Dimensi | File System Tradisional (POSIX / NFS / HDFS) | Enterprise Object Storage (S3 / GCS / Ceph) |
| :--- | :--- | :--- |
| **Metode Akses Data** | Kernel System Calls (`open`, `seek`, `read`, `write`) | HTTP REST API / RPC (`GET`, `PUT`, `DELETE`, `HEAD`) |
| **Model Metadata** | Hierarkis (*Inode Tree*, Direktori, Penataan Lock Direktori) | Flat Namespace (*Key-Value Pair*, Metadata terindeks LSM-Tree) |
| **Skalabilitas Kapasitas** | Terbatas oleh kapasitas node/NameNode Memory (HDFS limit) | Skalabilitas horizontal tanpa batas (*exabyte-scale*) |
| **Modifikasi Data** | *In-place mutation* (dapat memperbarui byte di tengah file) | *Immutable Objects* (modifikasi memerlukan penulisan ulang seluruh file) |
| **Karakteristik I/O** | *Low latency*, *high random IOPS* | *High throughput*, *high latency per-request* (20-100 ms) |
| **Mekanisme Ketahanan** | Hardware RAID, Replikasi 3x (boros biaya) | *Reed-Solomon Erasure Coding* terdistribusi lintas rak/AZ |

Mengapa memahami arsitektur internal ini sangat krusial? Mesin pemrosesan analitik modern (seperti Apache Spark, Trino, DuckDB, dan ClickHouse) membaca data langsung dari object storage via koneksi HTTP. Tanpa optimasi I/O terdistribusi seperti teknik *parallel byte-range requests* dan *entropy key-prefix distribution*, *query engine* akan mengalami I/O starvation—menghabiskan 80% waktu siklus CPU hanya untuk menunggu *handshake* jaringan dan *throttled responses*.

---

### 5. How (Workflow Detail)

#### Pipeline Produksi: Zero-Copy Resilient Multipart Ingestion
Proses penulisan file berukuran masif (misal: 100 GB Parquet) ke dalam object storage wajib mengikuti alur kerja *state machine* terdistribusi berikut:

```
[Client Worker Pool]             [Load Balancer]          [Metadata Engine]       [Storage Nodes]
         |                              |                         |                      |
         |--- 1. CreateMultipartUpload ------------------------->|                      |
         |<-- 2. Return UploadId ---------------------------------|                      |
         |                              |                         |                      |
    [Chunk Allocation]                  |                         |                      |
    (Split 100GB -> 10000 x 10MB)       |                         |                      |
         |                              |                         |                      |
         |--- 3. UploadPart (Part 1, Payload, Checksum)---------->|                      |
         |    [Parallel Stream]         |                         |---> Write RS(8,4) -->|
         |<-- 4. HTTP 200 OK + ETag1 ---|                         |<--- ACK Quorum ------|
         |                              |                         |                      |
         |--- 5. UploadPart (Part 2, Payload, Checksum)---------->|                      |
         |    [Parallel Stream]         |                         |---> Write RS(8,4) -->|
         |<-- 6. HTTP 200 OK + ETag2 ---|                         |<--- ACK Quorum ------|
         |                              |                         |                      |
         |--- 7. CompleteMultipartUpload(UploadId, Parts List)--->|                      |
         |                              |                         |--- Consolidate Index |
         |<-- 8. HTTP 200 OK (Final ETag + Metadata Committed)----|                      |
```

1. **Handshake & Alokasi State:** Klien mengirimkan request `CreateMultipartUpload`. Mesin metadata mengalokasikan `UploadId` unik serta mencatatnya ke dalam tabel transaksi aktif.
2. **Chunking & Concurrency Control:** Objek dipotong menjadi partikel-partikel partisi seragam (minimal 5 MB, kecuali part terakhir). Klien mengatur *concurrency pool* (menggunakan *semaphore*) guna mencegah kehabisan memori (*out-of-memory*) pada container pengeksekusi.
3. **Hashing & Zero-Copy Streaming:** Setiap partisi di-stream langsung dari memori tanpa melalui disk lokal (*zero-disk I/O*). Checksum CRC32C dihitung secara dinamis saat payload mengalir ke soket TCP.
4. **Resilient Retry dengan Exponential Jitter Backoff:** Jika terjadi kegagalan jaringan atau pembatasan kuota (`HTTP 503`), hanya partisi yang terdampak yang diunggah ulang—tanpa membatalkan seluruh proses pengunggahan dari awal.
5. **Final Commit (Atomic Consolidation):** Klien mengirimkan daftar seluruh partisi beserta nilai ETag dan nomor partisi yang terurut melalui pemanggilan `CompleteMultipartUpload`. Mesin metadata menggabungkan indeks partisi dan memvalidasi kelengkapan data secara atomik. Objek kini tersedia secara instan untuk dibaca di seluruh dunia.
6. **Garbage Collection Abortif:** Jika terjadi kegagalan sistemik yang tidak dapat dipulihkan, klien atau kebijakan siklus hidup (*lifecycle rule*) mengeksekusi instruksi `AbortMultipartUpload` untuk membersihkan partisi yatim (*orphaned parts*) agar tidak membebani biaya tagihan penyimpanan.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional vs. Kantor Pos Konvensional
* **POSIX File System:** Seperti **Kantor Pos Konvensional**. Anda datang membawa dokumen, petugas membuka laci berkas, mencari folder fisik berdasarkan nama laci dan map, lalu menyelipkan dokumen ke dalamnya. Jika dua orang mencoba membuka map yang sama, salah satu harus mengantre menunggu map tersebut ditutup (*file locking*). Skala operasi ini terbatas oleh ukuran ruang dan kecepatan gerak petugas pos.
* **Object Storage Terdistribusi:** Seperti **Sistem Penanganan Kargo Petikemas Bandara**. Anda tidak peduli kontainer ditempatkan di hanggar mana. Anda menyerahkan 1.000 boks kargo yang masing-masing telah ditempeli barcode unik (*Object Key*). Kargo diangkut secara paralel oleh armada derek otomatis (*Distributed I/O*), dipotong dan disebar ke berbagai kapal pengangkut (*Erasure Coding*). Jika salah satu kapal karam, sistem kalkulasi matematis dapat merekonstruksi kargo Anda secara utuh dari kapal lainnya.

#### Diagram Arsitektur Pemrosesan Read I/O Terdistribusi (Columnar Pushdown)
Ketika *engine* query analitik (seperti DuckDB atau Trino) memproses file Parquet berukuran besar:

```
+---------------------------------------------------------------------------------------------------+
| TRINO / DUCKDB QUERY ENGINE                                                                       |
|  - Step 1: Request footer Parquet (Tail Byte-Range GET ~ 512 KB)                                  |
|  - Step 2: Parse Metadata, Offset Kamus & Kolom (misal: hanya kolom 'TransactionAmount')         |
+---------------------------------------------------------------------------------------------------+
       |                                                                     |
       | HTTP GET Range: bytes=104852000-104857600                           | HTTP GET Range: bytes=4096-81920
       v                                                                     v
+---------------------------------------------------------------------------------------------------+
| AWS S3 / MINIO HIGH-THROUGHPUT HTTP REST GATEWAY                                                 |
+---------------------------------------------------------------------------------------------------+
       |                                                                     |
       | Fast path (Direct Segment Read)                                     | Fast path (Direct Segment Read)
       v                                                                     v
+------------------------------------+                             +------------------------------------+
| DATA DISK SLICE A (RowGroup 1 Data)|                             | DATA DISK SLICE B (RowGroup 2 Data)|
+------------------------------------+                             +------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Manual Low-Level Multipart Upload (Boto3)
Contoh berikut mengilustrasikan mekanisme dasar penanganan `UploadId`, nomor partisi, dan finalisasi transaksi commit secara eksplisit tanpa menggunakan *high-level transfer manager*.

```python
import os
import boto3

s3_client = boto3.client("s3")
BUCKET_NAME = "enterprise-data-lake-prod"
OBJECT_KEY = "telemetry/raw/system_metrics.bin"
FILE_PATH = "/tmp/system_metrics.bin"
PART_SIZE = 10 * 1024 * 1024  # Ukuran partisi 10 MB

# 1. Inisialisasi Multipart Upload
init_response = s3_client.create_multipart_upload(
    Bucket=BUCKET_NAME,
    Key=OBJECT_KEY,
    ContentType="application/octet-stream"
)
upload_id = init_response["UploadId"]
parts = []

try:
    with open(FILE_PATH, "rb") as file_handle:
        part_number = 1
        while True:
            file_data = file_handle.read(PART_SIZE)
            if not file_data:
                break

            print(f"Mengunggah partisi {part_number}...")
            upload_part_response = s3_client.upload_part(
                Bucket=BUCKET_NAME,
                Key=OBJECT_KEY,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=file_data
            )
            # Simpan ETag dan nomor partisi untuk proses konsolidasi commit
            parts.append({
                "PartNumber": part_number,
                "ETag": upload_part_response["ETag"]
            })
            part_number += 1

    # 2. Finalisasi Commit Transaksi
    s3_client.complete_multipart_upload(
        Bucket=BUCKET_NAME,
        Key=OBJECT_KEY,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts}
    )
    print("Multipart upload berhasil diselesaikan secara atomik.")

except Exception as err:
    print(f"Terjadi kesalahan fatal: {err}. Membatalkan Multipart Upload...")
    s3_client.abort_multipart_upload(
        Bucket=BUCKET_NAME,
        Key=OBJECT_KEY,
        UploadId=upload_id
    )
    raise
```

#### 7.2. Practical Example: High-Throughput Asynchronous Chunk Streamer dengan Backpressure, CRC32C, dan Retry Jitter
Implementasi kelas produksi ini berjalan sepenuhnya *in-memory*, menggunakan mekanisme *asynchronous worker pool*, menghitung *end-to-end checksum*, serta menerapkan algoritma *full jitter exponential backoff*.

```python
import asyncio
import io
import math
import os
import random
from typing import List, Dict, Any
import aiobotocore.session
from botocore.exceptions import ClientError
from google_crc32c import Checksum  # Komputasi checksum perangkat keras yang optimal


class ProductionS3ChunkUploader:
    """High-Throughput In-Memory Multipart Ingestion Engine dengan Backpressure terkalibrasi."""

    def __init__(
        self,
        bucket: str,
        key: str,
        concurrency_limit: int = 16,
        part_size_mb: int = 15,
        max_retries: int = 5,
        base_backoff_sec: float = 0.5,
    ) -> None:
        self.bucket = bucket
        self.key = key
        self.part_size = part_size_mb * 1024 * 1024
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec
        self.session = aiobotocore.session.get_session()

    async def _upload_part_with_retry(
        self,
        client: Any,
        upload_id: str,
        part_number: int,
        data_chunk: bytes,
    ) -> Dict[str, Any]:
        """Mengunggah fragmen byte secara aman dengan toleransi kesalahan dan perhitungan CRC32C."""
        # Menghitung checksum CRC32C biner
        crc_calculator = Checksum()
        crc_calculator.update(data_chunk)
        crc32c_b64 = crc_calculator.digest()

        for attempt in range(1, self.max_retries + 1):
            try:
                async with self.semaphore:
                    # Header checksum native AWS S3 untuk verifikasi hardware disk
                    response = await client.upload_part(
                        Bucket=self.bucket,
                        Key=self.key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=data_chunk,
                        ChecksumCRC32C=crc32c_b64.hex(),
                    )
                    return {"PartNumber": part_number, "ETag": response["ETag"]}

            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "Unknown")
                if error_code in ["SlowDown", "503", "InternalError", "RequestTimeout"] and attempt < self.max_retries:
                    # Full Jitter Exponential Backoff: sleep = uniform(0, min(cap, base * 2 ** attempt))
                    jitter_sleep = random.uniform(0, min(10.0, self.base_backoff_sec * (2 ** attempt)))
                    await asyncio.sleep(jitter_sleep)
                else:
                    raise RuntimeError(
                        f"Gagal mengunggah partisi {part_number} setelah {attempt} percobaan: {str(exc)}"
                    ) from exc

        raise RuntimeError(f"Gagal mengunggah partisi {part_number}: Percobaan maksimal terlampaui.")

    async def stream_and_upload(self, data_stream: asyncio.StreamReader, total_size: int) -> str:
        """Memproses data stream masuk tanpa intermediate disk write, mendistribusikannya ke workers."""
        async with self.session.create_client("s3") as client:
            # 1. Menginisialisasi upload
            init_res = await client.create_multipart_upload(
                Bucket=self.bucket,
                Key=self.key,
                ServerSideEncryption="AES256"
            )
            upload_id = init_res["UploadId"]

            total_parts = math.ceil(total_size / self.part_size)
            tasks: List[asyncio.Task] = []
            part_number = 1

            try:
                while True:
                    # Membaca potongan byte langsung ke memori (zero intermediate file on disk)
                    chunk = await data_stream.readexactly(self.part_size)
                    if not chunk:
                        break

                    task = asyncio.create_task(
                        self._upload_part_with_retry(client, upload_id, part_number, chunk)
                    )
                    tasks.append(task)
                    part_number += 1

            except asyncio.IncompleteReadError as err:
                # Menangani sisa part terakhir (kurang dari part_size)
                if err.partial:
                    task = asyncio.create_task(
                        self._upload_part_with_retry(client, upload_id, part_number, err.partial)
                    )
                    tasks.append(task)
            except Exception as unhandled_err:
                # Membersihkan resource di remote storage jika stream lokal gagal
                await client.abort_multipart_upload(
                    Bucket=self.bucket, Key=self.key, UploadId=upload_id
                )
                raise unhandled_err

            try:
                # Menunggu penyelesaian seluruh chunk I/O terdistribusi
                completed_parts = await asyncio.gather(*tasks)
                # Menyusun partisi terurut secara ascending berdasarkan PartNumber
                sorted_parts = sorted(completed_parts, key=lambda x: x["PartNumber"])

                # 2. Mengunci transaksi commit di metadata layer
                complete_res = await client.complete_multipart_upload(
                    Bucket=self.bucket,
                    Key=self.key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": sorted_parts},
                )
                return complete_res["Location"]

            except Exception as finalization_err:
                await client.abort_multipart_upload(
                    Bucket=self.bucket, Key=self.key, UploadId=upload_id
                )
                raise finalization_err


# Simulasi eksekusi pipeline I/O
async def main() -> None:
    sample_size = 50 * 1024 * 1024  # 50 MB
    raw_dummy_payload = os.urandom(sample_size)
    mock_network_stream = asyncio.StreamReader()
    mock_network_stream.feed_data(raw_dummy_payload)
    mock_network_stream.feed_eof()

    uploader = ProductionS3ChunkUploader(
        bucket="enterprise-telemetry-lake",
        key="raw/year=2026/site=sg/edge_payload.bin",
        concurrency_limit=8,
        part_size_mb=10,
    )

    print("Menginisialisasi pemrosesan distributed parallel upload...")
    # Dalam skenario lokal, instruksi ini membutuhkan konfigurasi AWS/MinIO credentials yang valid
    # object_url = await uploader.stream_and_upload(mock_network_stream, sample_size)
    # print(f"Upload sukses: {object_url}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah platform AdTech multinasional mengumpulkan log tayangan iklan (*ad impressions*) sebanyak 80 TB per hari dari 12 wilayah global. Data dikirimkan dalam *micro-batch* setiap 10 detik dalam format Snappy Parquet. 

#### Insiden Produksi
Setiap hari pada jam sibuk (pukul 14:00 - 17:00 UTC), pipeline streaming berbasis Apache Flink memicu puluhan ribu exception: `HTTP 503 SlowDown: Please reduce your request rate`. Hal ini mengakibatkan penumpukan *backpressure* ekstrem pada Apache Kafka, melipatgandakan *lag* konsumen hingga lebih dari 4 jam, dan memicu denda pelanggaran SLA senilai puluhan ribu dolar.

```
ARSITEKTUR LAMA (PENYEBAB BOTTLENECK 503):
Kafka -> Flink -> s3://ad-logs-prod/events/dt=2026-03-30/hr=14/part-worker-XXX.parquet
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                  Prefix identik secara masif -> Melebihi batas 3.500 PUT/detik
```

#### Investigasi Akar Masalah (RCA)
1. **Pola Prefix Monotonik:** Flink menulis data menggunakan partisi berbasis direktori tanggal dan jam standar: `events/dt=YYYY-MM-DD/hr=HH/`.
2. **Keterbatasan Partisi Fisik Storage:** Seluruh *task worker* (total 1.200 instance) menulis ke satu *prefix* yang sama secara paralel. Kecepatan request melampaui 12.000 `PUT` per detik, jauh melampaui limit fisik S3 sebesar 3.500 `PUT` per detik per prefix.
3. **Partition Splitting Latency:** Mesin internal S3 memerlukan waktu 15 hingga 45 menit untuk mendeteksi *hot partition* dan memecah partisi metadata secara otomatis. Pada saat partisi baru selesai disiapkan, volume traffic telah berganti ke jam berikutnya (`hr=15`), sehingga siklus *throttling* terus berulang tanpa henti.

#### Solusi Rekayasa Arsitektur
Arsitek Data menerapkan **Deterministic Hash Prefixing** dikombinasikan dengan teknik **Reverse Timestamp Sharding**:

```
ARSITEKTUR BARU (HIGH-ENTROPY BALANCED PREFIXING):
Key Pattern: s3://ad-logs-prod/p_hash={murmur3_32(device_id) % 64}/dt=2026-03-30/hr=14/{uuid4}.parquet
             |----------------------------------------------------|
             Menyebarkan I/O ke 64 partisi fisik S3 yang independen sejak detik pertama!
```

* **Capacity Expansion:** Kapasitas tulis melonjak secara horizontal dari $3.500\text{ req/detik}$ menjadi:
  $$64 \times 3.500 = 224.000\text{ write requests per detik}$$
* **External Table Virtual Mapping:** Agar *query engine* (Trino/Athena) tetap dapat membaca data secara efisien tanpa degradasi performa, tabel eksternal dikonfigurasi menggunakan fitur *AWS Glue Partition Projection*. Fitur ini memetakan parameter `p_hash` secara virtual, sehingga data analyst tetap dapat melakukan kueri analitik berbasis tanggal (`WHERE dt = '2026-03-30'`) secara transparan tanpa perlu mengetahui keberadaan hash prefix tersebut.
* **Hasil:** Error `HTTP 503 SlowDown` turun hingga 0.00%, dan latensi pipeline kembali normal ke $<15\text{ detik}$.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

Ketika merancang layer I/O penyimpanan objek terdistribusi, setiap keputusan arsitektur memiliki konsekuensi yang saling bertolak belakang:

```
                          [THROUGHPUT TINGGI]
                                  / \
                                 /   \
                                /     \
   (Multipart Over-Concurrency)/       \(Aggressive Compaction)
                              /         \
                             /           \
  [EFISIENSI BIAYA (COST)] ---------------- [LATENSI RENDAH (LATENCY)]
                               (Raw Small Files)
```

| Trade-off Vector | Opsi A | Opsi B | Analisis Rekayasa Mendalam |
| :--- | :--- | :--- | :--- |
| **Ukuran Objek: Small Objects (1-5 MB) vs. Large Files (128-512 MB)** | Banyak file kecil: Latensi penulisan awal instan, tetapi memicu *Small File Problem*. | File besar: Membutuhkan *in-memory staging*, throughput analitik kueri naik 10x lipat. | Membaca jutaan file 1 MB membebani biaya API (`GET` calls cost \$0.0004 per 1.000 request) dan memperlambat scanning Parquet; file 256 MB memberikan rasio kompresi dan efisiensi metadata terbaik. |
| **Ketahanan: Erasure Coding RS(8,4) vs. Multi-Region Replication (CRR)** | RS(8,4) hemat kapasitas (1.5x amplification factor), tapi pemulihan node lintas jaringan memicu *CPU spikes*. | CRR menggandakan biaya penyimpanan (2x cost), namun menawarkan RTO/RPO nol jika seluruh Region Cloud padam. | Jika data bersifat transien atau dapat di-compute ulang (bronze/silver data lake), gunakan RS(8,4) single-region untuk memangkas budget infrastruktur hingga 50%. |
| **Enkripsi: SSE-S3 (AES-256) vs. SSE-KMS Customer Managed Key (CMK)** | SSE-S3 gratis dan tanpa batasan request rate. | SSE-KMS mengenakan biaya per dekripsi ($0.03 per 10k request) dan dibatasi limit kuota KMS regional. | Pipeline Spark berukuran masif dengan jutaan partisi file dapat melampaui kuota KMS (misal: 30.000 TPS KMS limit), menyebabkan kegagalan batch serentak. Gunakan *KMS Bucket Keys* untuk memotong request KMS hingga 99%. |
| **Transfer Engine: Direct POSIX Mount (S3FS/FUSE) vs. Native REST SDK (Async Boto3/Go SDK)** | S3FS menyediakan kemudahan migrasi aplikasi legacy yang membutuhkan path file `/mnt/s3`. | Native SDK memerlukan adaptasi kode, tetapi mendukung parallel streams terdistribusi. | FUSE layer menerjemahkan panggilan baca/tulis menjadi polling HTTP yang lambat dan memicu inkonsistensi locking POSIX; hindari penggunaan FUSE di lingkungan produksi mission-critical. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kebocoran Biaya Akibat Upload Multipart Abortif (*Uncleaned Incomplete Multipart Uploads*)
* **Gejala:** Tagihan penyimpanan melonjak tajam secara konstan, padahal volume data efektif yang terdaftar di catalog tabel analitik tidak bertambah secara signifikan.
* **Akar Masalah:** Jika proses pengunggahan *multipart* terhenti di tengah jalan karena kegagalan jaringan, fragmen partisi yang telah berhasil dikirim akan tetap tersimpan di storage disk secara permanen. Partisi-partisi ini tidak terlihat melalui request `ListObjectsV2` standar, namun biaya penyimpanannya tetap ditagihkan penuh per GB.
* **Penyelesaian Sistemik:** Terapkan aturan S3 Lifecycle Configuration wajib pada setiap bucket data lake untuk memusnahkan partisi yang menggantung secara otomatis:

```json
{
  "Rules": [
    {
      "ID": "PurgeIncompleteMultipartUploadsAfter7Days",
      "Status": "Enabled",
      "Filter": {},
      "AbortIncompleteMultipartUpload": {
        "DaysAfterInitiation": 7
      }
    }
  ]
}
```

#### 2. Bottleneck Partisi Metadata Akibat Penamaan Objek Monotonik
* **Gejala:** Aplikasi memicu exception masif berulang: `HTTP 503 SlowDown`.
* **Akar Masalah:** Menggunakan ID urut otomatis (*auto-increment*), stempel waktu (*timestamps*), atau prefix alfabetis statis di awal nama key (contoh: `logs/2026-03-30-00-01.parquet`). Partisi disk internal penyedia cloud kewalahan karena tidak memiliki variasi karakter di bagian awal key.
* **Troubleshooting Command:** Analisis distribusi sebaran key objek menggunakan AWS CLI:
```bash
aws s3api list-objects-v2 --bucket my-lakehouse-bucket --prefix logs/ --query "Contents[].Key" | \
awk -F'/' '{print $2}' | sort | uniq -c | sort -nr | head -n 10
```
* **Solusi:** Tambahkan prefix entropi tinggi (seperti hash MD5 atau Murmur3) pada tingkat folder utama jika aplikasi beroperasi pada skala $\ge 10.000$ transaksi per detik.

#### 3. Silent Data Corruption Akibat Pengecekan MD5 yang Menipu
* **Gejala:** File biner atau Parquet yang diunduh dari S3 mengalami error `Corrupted File Exception`, padahal proses transfer mengembalikan status `HTTP 200 OK`.
* **Akar Masalah:** Untuk objek yang diunggah via multipart upload, header `ETag` bukan merupakan representasi hash MD5 murni dari file utuh, melainkan gabungan dari hash MD5 setiap partisi individual yang diakhiri dengan penanda jumlah partisi (contoh: `d41d8cd98f00b204e9800998ecf8427e-42`). Melakukan validasi kesesuaian MD5 lokal secara konvensional terhadap nilai `ETag` ini akan selalu menghasilkan verifikasi yang salah (*false mismatch*).
* **Solusi:** Manfaatkan fitur native checksum terbaru (SHA-256 atau CRC32C) yang didukung di layer protokol:
```bash
aws s3api get-object-attributes \
    --bucket my-lakehouse-bucket \
    --key data.parquet \
    --object-attributes "Checksum"
```

---

### 11. Best Practices (Production Checklist)

#### Architecture & Layout Design
- [ ] Terapkan format penyimpanan kolumnar berbasis kompresi terbuka (*Apache Parquet* atau *ORC*) dengan target ukuran file optimal antara **128 MB hingga 512 MB**.
- [ ] Hindari skema *monotonic increasing prefixes* untuk workload ingest berkecepatan tinggi ($\ge 3.000\text{ req/sec}$).
- [ ] Isolasi lifecycle data ke dalam arsitektur medallion: `raw/` (bronze), `cleansed/` (silver), dan `curated/` (gold) dengan konfigurasi bucket terpisah guna menyederhanakan isolasi blast-radius akses IAM.

#### High-Throughput I/O & Networking
- [ ] Jalankan compute node pada VPC/Region yang sama dengan lokasi bucket, dan aktifkan **VPC Gateway Endpoints** untuk menghilangkan beban latensi gateway NAT publik dan mengeliminasi biaya transfer data egress.
- [ ] Gunakan ukuran minimum multipart chunk sebesar 8 MB – 16 MB. Jumlah partisi maksimal S3 adalah 10.000; pastikan ukuran chunk Anda mampu menampung batas ukuran file maksimum tanpa melanggar batasan partisi tersebut.
- [ ] Optimalkan kernel Linux pada node pengirim data untuk transfer skala tinggi:
  ```bash
  sysctl -w net.core.rmem_max=16777216
  sysctl -w net.core.wmem_max=16777216
  sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
  sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"
  ```

#### Security & Compliance
- [ ] Aktifkan opsi **Block Public Access (BPA)** di level bucket dan account secara menyeluruh.
- [ ] Terapkan prinsip hak akses minimum (*least privilege*) menggunakan AWS IAM Condition Keys, membatasi request hanya melalui jalur VPC Endpoint terverifikasi (`aws:sourceVpce`).
- [ ] Aktifkan fitur **S3 KMS Bucket Keys** untuk mereduksi frekuensi request KMS langsung ke AWS KMS hingga 99%, guna menghemat anggaran operasional secara substansial.

#### Cost & Garbage Collection
- [ ] Pasang aturan lifecycle penghapusan multipart yang tidak tuntas (*incomplete multipart uploads*) dengan rentang waktu maksimal **7 hari**.
- [ ] Konfigurasikan transisi otomatis kelas penyimpanan (misal: S3 Standard $\to$ S3 Infrequent Access pada hari ke-30 $\to$ S3 Glacier Flexible Retrieval pada hari ke-90) berdasarkan pola frekuensi akses kueri data lake.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan menyiapkan kluster MinIO 4-node lokal lengkap dengan konfigurasi *Erasure Coding* (simulasi proteksi level enterprise) menggunakan Docker Compose, lalu mengeksekusi script streaming paralel untuk memverifikasi proses failover disk secara langsung.

#### Langkah 1: Siapkan Lingkungan Kerja
Buat direktori kerja baru dan masuk ke dalamnya:
```bash
mkdir -p hands-on/m02/ && cd hands-on/m02/
```

#### Langkah 2: Buat Konfigurasi Docker Compose MinIO Distributed Multi-Drive
Simpan berkas konfigurasi berikut dengan nama `docker-compose.yml`. Konfigurasi ini mensimulasikan 1 node dengan 4 drive virtual terpisah untuk mengaktifkan fitur *Erasure Coding* $RS(2,2)$:

```yaml
version: '3.8'

services:
  minio-distributed:
    image: quay.io/minio/minio:RELEASE.2024-03-15T01-07-19Z
    container_name: minio-distributed-node
    volumes:
      - minio-data-1:/data1
      - minio-data-2:/data2
      - minio-data-3:/data3
      - minio-data-4:/data4
    environment:
      MINIO_ROOT_USER: enterprise_admin
      MINIO_ROOT_PASSWORD: PasswordEnterpriseSuperSecure2026!
    command: server /data1 /data2 /data3 /data4 --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  minio-data-1:
  minio-data-2:
  minio-data-3:
  minio-data-4:
```

Jalankan kluster lokal:
```bash
docker compose up -d
```

#### Langkah 3: Inisialisasi Bucket dan Script Resilient Streamer
Buat script verifikasi Python dengan nama `distributed_io_test.py`:

```python
import os
import boto3
from botocore.client import Config

ENDPOINT_URL = "http://localhost:9000"
ACCESS_KEY = "enterprise_admin"
SECRET_KEY = "PasswordEnterpriseSuperSecure2026!"
BUCKET = "telemetry-verification-bucket"

# Gunakan signature versi 4 secara eksplisit
s3_client = boto3.client(
    "s3",
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1"
)

# Buat bucket pengujian jika belum tersedia
try:
    s3_client.create_bucket(Bucket=BUCKET)
    print(f"Bucket {BUCKET} berhasil dikonfigurasi.")
except s3_client.exceptions.BucketAlreadyOwnedByYou:
    pass

# Buat berkas dummy biner berukuran 30 MB
PAYLOAD_SIZE = 30 * 1024 * 1024
DUMMY_FILE = "payload_sample.bin"
with open(DUMMY_FILE, "wb") as f:
    f.write(os.urandom(PAYLOAD_SIZE))

print(f"Mengunggah file {PAYLOAD_SIZE / (1024*1024)} MB ke kluster Erasure Coded...")

# Eksekusi Multipart Upload via High-Level Transfer Config
from boto3.s3.transfer import TransferConfig
config = TransferConfig(
    multipart_threshold=5 * 1024 * 1024,
    max_concurrency=4,
    multipart_chunksize=5 * 1024 * 1024,
    use_threads=True
)

s3_client.upload_file(
    DUMMY_FILE,
    BUCKET,
    "production/test_object.bin",
    Config=config
)
print("File berhasil diunggah dengan aman ke kluster penyimpanan terdistribusi.")

# Bersihkan artifact pengujian lokal
if os.path.exists(DUMMY_FILE):
    os.remove(DUMMY_FILE)
```

Jalankan script tersebut:
```bash
pip install boto3
python distributed_io_test.py
```

#### Langkah 4: Uji Simulasi Kerusakan Hardware (Disaster Injection)
Hancurkan salah satu disk volume penyimpanan MinIO saat operasi pembacaan berjalan:
```bash
# Periksa volume mount yang aktif di container
docker exec -it minio-distributed-node ls -la /data1 /data2 /data3 /data4

# Simulasikan kerusakan hardware: hapus seluruh isi dari drive data 1 secara paksa
docker exec -it minio-distributed-node rm -rf /data1/telemetry-verification-bucket

# Jalankan pengujian verifikasi data via Python:
python -c '
import boto3
from botocore.client import Config
s3 = boto3.client("s3", endpoint_url="http://localhost:9000", aws_access_key_id="enterprise_admin", aws_secret_access_key="PasswordEnterpriseSuperSecure2026!", config=Config(signature_version="s3v4"))
obj = s3.get_object(Bucket="telemetry-verification-bucket", Key="production/test_object.bin")
data = obj["Body"].read()
print(f"Data berhasil dibaca utuh dari sisa drive parity: Panjang {len(data)} bytes")
'
```

Amati bagaimana object storage berhasil merekonstruksi seluruh byte payload yang hilang secara instan dan transparan berkat implementasi Reed-Solomon Erasure Coding!

---

### 13. Exercise

#### Level Easy
Buat script utilitas Python yang memindai seluruh *Incomplete Multipart Uploads* yang menggantung lebih dari 24 jam pada suatu bucket, lalu membatalkan (`abort`) upload tersebut secara otomatis untuk menghindari pemborosan biaya.
* **Kriteria Keberhasilan:** Script mencetak daftar `UploadId` yang terdampak dan total estimasi storage yang berhasil diselamatkan.

#### Level Medium
Kembangkan modul *Byte-Range Column Reader* menggunakan `boto3`. Klien hanya boleh mengekstrak data dari byte ke-50.000 hingga byte ke-150.000 dari sebuah file Parquet sebesar 2 GB tanpa mengunduh keseluruhan berkas dari remote bucket.
* **Kriteria Keberhasilan:** Script memanfaatkan header HTTP `Range: bytes=start-end`, mengukur durasi transfer jaringan, dan memvalidasi bahwa memory footprint proses lokal tetap berada di bawah 2 MB.

#### Level Hard
Rancang dan implementasikan program CLI berkinerja tinggi menggunakan arsitektur concurrency non-blocking (*asyncio* atau *goroutines*) yang mampu membaca file arsip masif terkompresi (misal: 10 GB dump log), menghitung nilai hash CRC32C secara *on-the-fly*, dan melakukan streaming pengunggahan multipart ke object storage tanpa pernah menulis file sementara (*temporary file*) ke media disk lokal.
* **Kriteria Keberhasilan:** Skalabilitas transfer harus membatasi penggunaan alokasi RAM proses lokal stabil pada batas maksimal $\le 200\text{ MB}$ sepanjang keseluruhan durasi transfer.

---

### 14. Challenge

**Studi Kasus Arsitektur: Rekayasa Penyelamatan Lakehouse Skala Tinggi**

Anda direkrut sebagai Principal Data Architect di sebuah platform marketplace terkemuka. Sistem analitik saat ini memproses data dari armada pipeline micro-batching (10.000 micro-batches per jam) yang menuliskan data langsung ke AWS S3. 

Setiap micro-batch menghasilkan rata-rata 50 file Parquet kecil berukuran ~200 KB yang dituliskan ke direktori berbasis partisi:
`s3://company-datalake/transactions/order_created/year=2026/month=03/day=30/batch_<uuid>.parquet`

**Kondisi Kritis yang Muncul:**
1. Mesin analitik (Trino & Apache Spark) memerlukan waktu hingga 45 menit hanya untuk menyelesaikan query agregasi sederhana pada data satu hari terakhir. Analisis profil CPU menunjukkan bahwa 85% waktu eksekusi habis pada tahap penanganan metadata listing S3 dan network socket overhead.
2. Tim DevOps melaporkan bahwa tagihan API S3 melesat hingga \$35.000 per bulan murni akibat akumulasi lonjakan request `PUT` dan `GET`.
3. Sering terjadi kegagalan pemrosesan berantai akibat pembatasan `HTTP 503 SlowDown` dari S3 saat event flash-sale berlangsung.

**Misi Desain Rekayasa:**
Rancang cetak biru arsitektur komprehensif untuk merombak lapisan ingest dan storage layer ini:
1. Formulasikan strategi redistribusi *storage layout & prefix engineering* guna melenyapkan limitasi `HTTP 503 SlowDown` secara permanen.
2. Definisikan topologi pipeline perantara (*buffering/compaction engine*) yang bertugas mengonsolidasikan file-file kecil tersebut menjadi ukuran optimal tanpa menambah latensi ketersediaan data lake (*freshness SLA*) lebih dari 15 menit.
3. Rancang mekanisme transisi migrasi tabel analitik secara *zero-downtime* dengan memanfaatkan format tabel modern (*Apache Iceberg* atau *Delta Lake*). Tunjukkan bagaimana format tersebut meminimalisasi overhead pemanggilan REST API `LIST` melalui metadata file terpusat (*Avro manifest list*).

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Tingkat Basic (Pilihan Ganda)

1. Dalam arsitektur *Erasure Coding* dengan skema $RS(8, 4)$, berapa jumlah maksimal kegagalan disk serentak yang dapat ditoleransi sistem sebelum data mengalami kerusakan permanen?
   * A. 8 drive
   * B. 2 drive
   * C. 4 drive
   * D. 12 drive

2. Jika aplikasi Anda menerima pesan kesalahan `HTTP 503 SlowDown` dari AWS S3 saat melakukan penulisan data masif, apa penyebab utama dari kendala tersebut?
   * A. Kapasitas sisa penyimpanan fisik pada bucket S3 telah habis.
   * B. Aplikasi melampaui batas kecepatan request sebesar 3.500 `PUT` per detik pada satu prefix path tertentu.
   * C. Format file data yang diunggah tidak didukung secara native oleh protokol AWS S3.
   * D. Bucket S3 belum mengaktifkan enkripsi SSE-KMS dengan benar.

3. Karakteristik pembeda utama antara Object Storage terdistribusi dengan POSIX Network File System (NFS) konvensional adalah:
   * A. Object Storage tidak mendukung enkripsi payload saat data transit di jaringan.
   * B. Object Storage mengizinkan pembaruan data secara parsial di tengah-tengah file (*in-place partial modification*).
   * C. Object Storage memperlakukan seluruh entitas data sebagai objek statis yang tidak dapat diubah (*immutable*).
   * D. POSIX File System mengabaikan penggunaan sistem penomoran *inodes*.

4. Apa dampak finansial utama jika aplikasi gagal memanggil `AbortMultipartUpload` atau tidak memasang lifecycle rule pembersihan setelah terjadi error pada proses multipart upload?
   * A. Akun cloud Anda akan langsung dibekukan sementara oleh tim audit provider.
   * B. Bagian-bagian partisi file yang menggantung akan terus dikenai biaya penyimpanan penuh sesuai kapasitas gigabyte-nya.
   * C. Data lake akan mengalami penurunan throughput IOPS secara drastis sebesar 50%.
   * D. File yang diunggah otomatis terhapus dari katalog metadata dalam kurun waktu 1 jam.

5. Berapakah batas minimum ukuran potongan payload (*chunk size*) untuk setiap partisi dalam multipart upload S3 (kecuali untuk partisi terakhir)?
   * A. 128 KB
   * B. 5 MB
   * C. 64 MB
   * D. 1 GB

---

#### Pertanyaan Tingkat Intermediate (Pilihan Ganda)

6. Mengapa query engine modern seperti Trino atau DuckDB memanfaatkan HTTP *Byte-Range Requests* saat membaca file Apache Parquet dari object storage?
   * A. Untuk mengonversi format Parquet menjadi format teks CSV secara otomatis di level storage.
   * B. Untuk membaca bagian footer metadata dan kolom data tertentu yang ditargetkan tanpa harus mengunduh keseluruhan payload file.
   * C. Untuk mengompresi payload secara otomatis selama proses streaming transfer berlangsung.
   * D. Untuk menyamarkan isi konten data dari monitoring firewall jaringan publik.

7. Manakah di antara skema Object Key berikut yang paling efektif dalam mencegah munculnya fenomena *hot partition* pada sistem penulisan throughput tinggi ($\ge 50.000\text{ writes/sec}$)?
   * A. `telemetry/2026/03/30/node_01.json`
   * B. `telemetry/site_a/v1/0001.json`
   * C. `telemetry/d8f2a1b4/site_a/2026-03-30.json` (di mana `d8f2a1b4` adalah hash MD5 atau Murmur3)
   * D. `telemetry/increment_id=10002934.json`

8. Pada sistem penyimpanan objek modern berskala enterprise, bagaimana cara kerja fitur pendeteksi *Bit-Rot* secara internal?
   * A. Melakukan reboot berkala pada server storage setiap 24 jam sekali.
   * B. Memverifikasi hash checksum (seperti HighwayHash) di level blok secara berkala dan merekonstruksi blok data yang korup dari partisi erasure parity.
   * C. Menduplikasi seluruh isi disk ke region cloud lain secara harian.
   * D. Membatasi hak akses file hanya kepada pengguna level administrator sistem.

9. Apa fungsi arsitektural dari implementasi *AWS KMS Bucket Keys* dalam sistem penyimpanan berkecepatan tinggi?
   * A. Mematikan fitur enkripsi data lake secara permanen guna mendongkrak performa throughput.
   * B. Menghasilkan kunci simetris turunan lokal di dalam layer storage guna memangkas frekuensi pemanggilan API ke KMS secara drastis.
   * C. Menghubungkan bucket cloud storage langsung ke sistem hardware security module (HSM) on-premise.
   * D. Mengizinkan transfer payload antar bucket yang berbeda region secara gratis tanpa biaya data transfer.

10. Ketika mengunggah file masif melalui proses multipart upload di AWS S3, nilai `ETag` akhir yang dikembalikan setelah konsolidasi commit merepresentasikan:
    * A. Hash MD5 langsung dari seluruh isi berkas utuh dari awal sampai akhir.
    * B. Hash dari gabungan byte checksum setiap partisi individual, diikuti dengan tanda pemisah strip dan total partisi (`<checksum>-<part_count>`).
    * C. Tanda tangan digital kunci publik dari sertifikat SSL/TLS server gateway penerima.
    * D. Stempel waktu berbasis epoch Unix saat operasi `CompleteMultipartUpload` dieksekusi.

---

#### Skenario Kasus Produksi (Analisis Praktis)

11. **Skenario Kasus 1:**
Sebuah pipeline Spark Streaming memproses 20.000 file log transaksi per detik ke S3. Namun, sistem sering mengalami lonjakan response time jaringan yang sangat tinggi (p99 latency $> 10\text{ detik}$) dan timeout koneksi. Padahal, penggunaan utilisasi CPU dan memori pada node pekerja Spark masih berada di bawah 40%. Tim infrastruktur mengonfirmasi bahwa bandwidth pipa koneksi internet masih tersisa sangat luas. Analisis akar masalah jaringan terdistribusi apa yang paling mungkin memicu bottleneck ini, dan bagaimana solusi konfigurasinya?

12. **Skenario Kasus 2:**
Sebuah korporasi finansial tunduk pada aturan kepatuhan audit data: setiap rekaman analitik di object storage wajib dijamin tidak mengalami perubahan bit sekecil apa pun (*data tamper-proof*) dan terproteksi dari potensi penghapusan tidak disengaja oleh staf internal pemegang hak akses admin sekalipun. Pendekatan arsitektur storage enterprise apa yang wajib dikonfigurasi untuk memenuhi mandat audit tersebut secara mutlak?

13. **Skenario Kasus 3:**
Engine kueri Apache Iceberg pada data lakehouse Anda mengalami perlambatan performa listing file secara drastis setelah berjalan selama 6 bulan. Analisis awal menunjukkan bucket target memiliki jutaan file partisi Parquet lama yang telah dihapus melalui transaksi *logical drop*. Tindakan pembersihan distributed storage apa yang harus segera dieksekusi oleh Data Platform Engineer?

---

### Kunci Jawaban & Pembahasan Quiz

#### Tingkat Basic
1. **C. 4 drive.** Pada Reed-Solomon $RS(K, M)$, sistem mampu bertahan dari kehilangan maksimal hingga sejumlah $M$ drive paritas. Karena $M = 4$, jika 4 drive fisik mati serentak, seluruh data biner tetap dapat direkonstruksi 100% dari 8 drive data yang tersisa.
2. **B. Aplikasi melampaui batas kecepatan request sebesar 3.500 PUT per detik pada satu prefix path tertentu.** AWS S3 membatasi throughput setiap partisi metadata prefix tunggal maksimal 3.500 `PUT`/`POST`/`DELETE` atau 5.500 `GET` per detik sebelum mekanisme auto-split terpicu.
3. **C. Object Storage memperlakukan seluruh entitas data sebagai objek statis yang tidak dapat diubah (immutable).** Objek pada object storage bersifat *write-once-read-many*; pembaruan byte di tengah-tengah file tidak dimungkinkan tanpa mengunggah ulang seluruh objek secara penuh.
4. **B. Bagian-bagian partisi file yang menggantung akan terus dikenai biaya penyimpanan penuh sesuai kapasitas gigabyte-nya.** Partisi chunk dari proses upload multipart yang tidak di-commit atau tidak di-abort akan terus tersimpan dan ditagihkan oleh penyedia cloud storage.
5. **B. 5 MB.** S3 API memberlakukan batasan ukuran partisi multipart upload minimal sebesar 5 MB, kecuali untuk fragmen partisi terakhir (*last part*).

#### Tingkat Intermediate
6. **B. Untuk membaca bagian footer metadata dan kolom data tertentu yang ditargetkan tanpa harus mengunduh keseluruhan payload file.** Mesin kueri analitik memanfaatkan struktur Parquet yang menempatkan metadata pada posisi *tail* (footer) file, lalu menggunakan HTTP Range Request untuk hanya menarik rentang byte kolom yang dibutuhkan (*projection pushdown*).
7. **C. `telemetry/d8f2a1b4/site_a/2026-03-30.json`.** Menambahkan karakter hash dengan nilai entropi tinggi di bagian awal struktur key menyebarkan pemrosesan I/O secara merata ke puluhan partisi disk metadata fisik yang berbeda sejak hari pertama.
8. **B. Memverifikasi hash checksum di level blok secara berkala dan merekonstruksi blok data yang korup dari partisi erasure parity.** Proses *background scrubbing* membaca blok disk secara kontinyu, menghitung ulang nilai checksum matematis, dan memperbaiki kerusakan bit (*bit flip*) secara otomatis sebelum kerusakan meluas ke paritas lain.
9. **B. Menghasilkan kunci simetris turunan lokal di dalam layer storage guna memangkas frekuensi pemanggilan API ke KMS secara drastis.** KMS Bucket Key menurunkan frekuensi interaksi jaringan antara S3 dan KMS via mekanisme enkripsi tiket jangka pendek, menghemat biaya tagihan request API hingga 99%.
10. **B. Hash dari gabungan byte checksum setiap partisi individual, diikuti dengan tanda pemisah strip dan total partisi (`<checksum>-<part_count>`).** ETag untuk file multipart upload dihitung dengan menggabungkan hash biner dari masing-masing partisi, menghitung ulang hash dari gabungan tersebut, dan membubuhkan suffix jumlah partisi (contoh: `c3ab89...-12`).

#### Evaluasi Skenario Kasus Produksi
11. **Analisis Solusi Kasus 1:**
    * **Akar Masalah:** Kemungkinan besar terjadi akibat *TCP socket exhaustion* atau *connection pool starvation* pada JVM executor Spark yang menginisialisasi koneksi TLS/HTTP baru secara berulang untuk setiap penulisan file mikro, ditambah limitasi pembatasan throughput pada *NAT Gateway*.
    * **Solusi Arsitektur:** (1) Aktifkan *S3 VPC Gateway Endpoint* (gratis, bypassing NAT gateway langsung via backbone privat AWS). (2) Aktifkan *HTTP Keep-Alive* dan perbesar alokasi *connection pool* pada driver klien HTTP (misal: `fs.s3a.connection.maximum=1000`). (3) Terapkan teknik *micro-batch coalescing* di Spark (`.coalesce()` atau `.repartition()`) sebelum instruksi tulis dijalankan untuk menekan jumlah file kecil dan meminimalkan frekuensi jabat tangan TLS yang membebani TCP layer.
12. **Analisis Solusi Kasus 2:**
    * **Solusi Arsitektur:** Terapkan fitur **S3 Object Lock** dalam mode **Compliance Mode** (bukan *Governance Mode*). Dalam mode ini, tidak ada pengguna IAM mana pun—termasuk root account AWS—yang diizinkan menghapus atau menimpa objek sebelum rentang retensi (*retention period*) berakhir. Pastikan juga fitur *Bucket Versioning* dan *MFA Delete* diaktifkan secara ketat pada kontrol akses bucket tersebut untuk memenuhi persyaratan regulasi sekuritas FINRA/SEC.
13. **Analisis Solusi Kasus 3:**
    * **Akar Masalah:** Mesin metadata Apache Iceberg menyimpan histori snapshot dan file log manifest lama. Akumulasi snapshot yang terhapus secara logis masih meninggalkan jutaan *orphan files* dan struktur manifest usang di object storage layer, yang memperlambat proses *snapshot traversal*.
    * **Solusi Rekayasa:** Jalankan prosedur pemeliharaan berkala Iceberg secara terjadwal: (1) Eksekusi `expireSnapshots` untuk menghapus referensi snapshot lama di luar SLA retensi kueri. (2) Jalankan prosedur `remove_orphan_files` untuk menghapus sisa file Parquet fisik di storage bucket yang sudah tidak terikat pada manifest tabel mana pun. (3) Eksekusi `rewriteManifests` untuk mengonsolidasikan metadata manifest list menjadi file terstruktur yang kompak, sehingga operasi scanning kembali instan.

---

### 16. Summary

* **Pemrosesan Terdistribusi Berbasis Object Storage** menuntut pergeseran paradigma total dari paradigma filesystem POSIX konvensional: hilangkan asumsi ketersediaan direktori fisik hierarkis, hindari *file locking*, dan terapkan prinsip mutlak data *immutability*.
* **Reed-Solomon Erasure Coding** adalah fondasi ketahanan data skala petabyte modern, mengeliminasi inefisiensi biaya replikasi 3 arah tradisional sembari tetap menjamin proteksi matematis terhadap kegagalan multi-disk serentak dan fenomena degradasi fisik (*bit-rot*).
* **Throughput I/O Optimal** pada protokol HTTP REST dicapai secara eksklusif melalui teknik paralelisme terukur: pemanfaatan *concurrent multipart streaming* dengan alokasi backpressure memori yang presisi untuk penulisan, serta pemanfaatan *parallel byte-range requests* untuk pembacaan format kolumnar modern (Parquet/ORC).
* **Skalabilitas Prefix:** Kunci dari penghapusan limitasi performa S3 (`HTTP 503 SlowDown`) terletak pada pemahaman menyeluruh atas arsitektur *metadata partitioning*: hindari pengurutan kunci monotonik dan distribusikan beban I/O secara leksikografis menggunakan skema *high-entropy prefixing*.
* **Manajemen Siklus Hidup File:** Tanpa tata kelola konfigurasi yang disiplin—khususnya pembersihan otomatis sisa partisi upload multipart yang gagal serta konsolidasi *small files*—infrastruktur data lakehouse enterprise akan mengalami penurunan performa kueri secara eksponensial disertai ledakan pemborosan biaya penyimpanan yang tidak terkendali.