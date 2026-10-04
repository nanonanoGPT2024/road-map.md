# Bab 05: Apache Kafka Internals & Distributed Log Architecture
## Module 01: Storage Engine Internals, Zero-Copy Data Transfer, dan Konsensus KRaft

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis (C4)** arsitektur penyimpanan fisik Apache Kafka hingga level *segment files*, *sparse index*, dan format biner *RecordBatch*.
- **Mengevaluasi (C5)** mekanisme I/O tingkat kernel sistem operasi (*OS Page Cache* vs *JVM Heap*, *system call `sendfile`*, dan transfer data *Zero-Copy*) yang memungkinkan Kafka mencapai *throughput* multi-gigabit per detik.
- **Mengonfigurasi (C3)** metadata quorum berbasis KRaft (*Kafka Raft Metadata Mode*) untuk menggantikan Apache ZooKeeper dengan latensi pemulihan *failover* deterministik.
- **Mendiagnosis (C4)** anomali replikasi partisi melalui metrik *High Watermark* (HW), *Log End Offset* (LEO), dan status *In-Sync Replicas* (ISR).
- **Mengimplementasikan (C6)** producer dan consumer berkinerja tinggi dalam bahasa Python dengan jaminan semantik pengiriman *exactly-once* (EOS) dan penanganan kegagalan tingkat produksi.

---

### 2. Concept Overview
Secara fundamental, Apache Kafka bukanlah sebuah *message queue* tradisional berbasis *in-memory broker* (seperti RabbitMQ dengan model AMQP). Kafka adalah sebuah **distributed, append-only, ordered commit log**. 

```
Mental Model: Distributed Commit Log
[Offset 0][Offset 1][Offset 2][Offset 3][Offset 4] ... [Offset N] -> APPEND ONLY
      ^                                               ^
Consumer Group A (Offset 1)                   Consumer Group B (Offset 4)
```

Prinsip fundamental arsitektur log terdistribusi Kafka:
1. **Append-Only Immutability**: Data hanya dapat ditambahkan di akhir log (*sequential append*). Tidak ada operasi pembaruan (*in-place update*) atau penghapusan acak (*random delete*). Mutabilitas dihindari untuk mengeliminasi kebutuhan *lock contention* tingkat baris.
2. **Sequential Disk I/O vs. Random Memory Access**: Throughput I/O disk linier pada media penyimpanan modern (NVMe/Enterprise SSD maupun SAS HDD 7200 RPM) mendekati atau bahkan melampaui performa akses memori acak (*random RAM access*). Kafka mengeksploitasi karakteristik ini dengan memaksimalkan pola akses linier.
3. **Abstraction of Queues via Consumer Offsets**: Kafka tidak melacak status keterbacaan pesan per-consumer di dalam struktur antrean data itu sendiri. Consumer bertanggung jawab memelihara pointer posisinya sendiri (*offset*). Hal ini mengubah kompleksitas pembacaan pesan dari $O(\log N)$ atau $O(N)$ menjadi $O(1)$.
4. **Metadata via Event-Driven Consensus (KRaft)**: Sejak Kafka 3.3+, metadata cluster dikelola langsung di dalam Kafka menggunakan protokol konsensus Raft yang terspesialisasi (KRaft), menghilangkan ketergantungan eksternal terhadap ZooKeeper dan memangkas waktu propagasi metadata partisi dari beberapa menit menjadi beberapa milidetik.

---

### 3. Why It Matters
Dalam skala enterprise dan arsitektur data modern (AI platform, Lakehouse ingestion, dan event-driven microservices), kegagalan memahami internal Kafka dapat memicu degradasi sistem katastropik:

- **Eliminasi Latensi GC (Garbage Collection)**: Menempatkan payload data bernilai puluhan gigabyte ke dalam JVM Heap akan menyebabkan *stop-the-world* GC pause hingga puluhan detik. Kafka mendesain mesin penyimpanannya di luar JVM (*off-heap*), menyerahkan manajemen cache data sepenuhnya ke OS Page Cache.
- **Efisiensi Biaya Komputasi & Jaringan**: Tanpa *Zero-Copy*, data disalin 4 kali antara konteks kernel dan user-space sebelum mencapai Network Interface Card (NIC). Pada aliran data $10\text{ Gbps}$, CPU akan tersaturasi hanya untuk operasi *memory copying*. Zero-copy menurunkan utilisasi CPU hingga 80%.
- **Integritas AI Pipeline & RAG Streaming**: Arsitektur Autonomous Agent dan Real-Time Feature Store membutuhkan data terurut tanpa duplikasi (*exactly-once*). Memahami interaksi antara producer batching, broker log segments, dan consumer rebalance mencegah hilangnya konteks atau timbulnya data ganda pada inferensi model machine learning.

---

### 4. Arsitektur & Diagram Komponen

#### 4.1 Broker Storage Layout & Segment Anatomy
Setiap Topic dipecah menjadi beberapa Partition. Setiap Partition direpresentasikan sebagai direktori fisik di dalam disk broker (`<topic_name>-<partition_index>/`). Direktori ini terdiri dari kumpulan berkas yang disebut **Log Segments**.

```
Disk Directory: /var/lib/kafka/data/telemetry-events-0/
│
├── 00000000000000000000.log         <-- Data biner terkompresi (RecordBatches)
├── 00000000000000000000.index       <-- Sparse Offset-to-Physical Position Index
├── 00000000000000000000.timeindex   <-- Timestamp-to-Offset Index
├── 00000000000001054392.log         <-- Segment baru hasil rotasi (Active Segment)
├── 00000000000001054392.index
├── 00000000000001054392.timeindex
└── leader-epoch-checkpoint          <-- Pemetaan Leader Epoch ke Start Offset
```

#### 4.2 Data Path: Traditional vs Zero-Copy (`sendfile`)

```
========================= TRADITIONAL DATA PATH =========================
[ Disk ] --(DMA Copy)--> [ OS Page Cache ] --(CPU Copy)--> [ JVM Heap ]
                                                                  │
[ NIC Buffer ] <--(DMA Copy)-- [ Socket Buffer ] <--(CPU Copy)───┘
Context Switches: 4 | Data Copies: 4 (2 DMA, 2 CPU)

========================= KAFKA ZERO-COPY PATH ==========================
[ Disk ] --(DMA Copy)--> [ OS Page Cache ] ──┐ (sendfile / splice)
                                            │
                                 (DMA Gather / Direct Copy)
                                            │
                                            v
                                     [ NIC Buffer ]
Context Switches: 2 | Data Copies: 2 (2 DMA, 0 CPU Copy)
```

#### 4.3 KRaft Consensus Topology

```
+-------------------------------------------------------------+
|                  KRaft Controller Quorum                    |
|                                                             |
|  +-----------------+  +-----------------+  +-------------+  |
|  | Controller 1    |  | Controller 2    |  | Controller 3|  |
|  | (ACTIVE LEADER) |<==> (FOLLOWER)     |<==> (FOLLOWER) |  |
|  | Metadata Log:   |  | Metadata Log:   |  | Metadata Log|  |
|  | @metadata-0     |  | @metadata-0     |  | @metadata-0 |  |
|  +--------+--------+  +-----------------+  +-------------+  |
+-----------|-------------------------------------------------+
            | Metadata RPC (Replication of metadata records)
            v
+-------------------------------------------------------------+
|                       Broker Cluster                        |
|                                                             |
|  +------------------+                    +----------------+ |
|  | Broker 101       |                    | Broker 102     | |
|  | Metadata Cache   |                    | Metadata Cache | |
|  | (In-Memory Image)|                    | (In-Memory Img)| |
|  +------------------+                    +----------------+ |
+-------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Log Segment File Formats & Sparse Indexing
Kafka tidak mencatat indeks lokasi untuk setiap pesan. Menyimpan indeks per record membutuhkan memori yang besar ($O(N)$). Sebaliknya, Kafka menggunakan **Sparse Indexing** ($O(\log K)$ di mana $K = N / \text{index\_interval}$).

1. **`.log` File**: Berisi kumpulan `RecordBatch`. Setiap batch membungkus array record terkompresi (LZ4, Zstandard, Snappy, atau GZIP).
2. **`.index` File**: Berisi entri berukuran tetap (8 byte per entri):
   - **Relative Offset** (4 byte): `Offset - BaseOffset` dari segmen tersebut.
   - **Physical Position** (4 byte): Posisi biner byte dalam file `.log`.
3. **Pencarian Data (Read Path)**:
   - Kafka menerima permintaan baca untuk Offset `1054450`.
   - Menggunakan binary search pada array segmen untuk menemukan file segmen yang menampung offset tersebut.
   - Melakukan binary search pada file `.index` yang dipetakan ke memori (*memory-mapped* via `mmap`) untuk menemukan *Relative Offset* terbesar yang $\le$ target offset.
   - Mengambil *Physical Position* dari index tersebut, lalu melompat langsung (*direct seek*) ke posisi byte di file `.log`.
   - Melakukan *sequential scan* pada `.log` dari posisi tersebut hingga menemukan record dengan offset presisi.

```
Offset Lookup Process:
Target Offset: 1054402 (Base Offset: 1054392) -> Relative Offset: 10

.index File (Memory-Mapped)          .log File (On-Disk/Page Cache)
+-----------------+---------------+  +------------------------------------+
| Relative Offset | Position Byte |  | Physical Bytes                     |
+-----------------+---------------+  +------------------------------------+
| 0               | 0             |  | Pos 0: Batch 1 (Offset 1054392-395)|
| 4               | 4096          |->| Pos 4096: Batch 2 (Off 1054396-401)|
| 12              | 9216          |  | Pos 7120: Batch 3 (Off 1054402-408)|<-- Match!
+-----------------+---------------+  +------------------------------------+
* Index melompat ke Pos 4096, scan berlanjut linier ke Pos 7120.
```

#### 5.2 Zero-Copy via OS Page Cache
Aplikasi berbasis JVM konvensional membaca data dari disk ke *kernel page cache*, mentransfernya ke *buffer JVM memory*, lalu menulisnya kembali ke *socket buffer* sistem operasi. Proses ini melibatkan:
- 4 pergantian konteks (*context switches*) antara user space dan kernel space.
- 4 penyalinan data di memori (*memory copies*).
- Tekanan alokasi memori pada JVM Garbage Collector.

Kafka memotong jalur ini menggunakan *Java NIO* `FileChannel.transferTo()`, yang di tingkat kernel Linux memanggil *system call* `sendfile(2)`:
1. Data dibaca dari media penyimpanan fisik ke OS Page Cache menggunakan mesin DMA (*Direct Memory Access*).
2. Broker JVM menerbitkan instruksi `sendfile` tanpa menyalin payload ke memori JVM.
3. Mesin DMA menyalin data langsung dari OS Page Cache ke *NIC Buffer* (didukung oleh *Scatter-Gather DMA* via soket descriptor).
4. Penanganan paket jaringan diselesaikan sepenuhnya di ruang kernel.

#### 5.3 KRaft (Kafka Raft Metadata Mode)
Sebelum era KRaft, ZooKeeper menyimpan metadata cluster secara eksternal. Apabila sebuah cluster memiliki 500.000 partisi dan ZooKeeper mengalami kegagalan, Controller harus memuat ulang metadata seluruh partisi secara sinkron, memakan waktu hingga puluhan menit.

KRaft mengatasi masalah ini dengan:
- Menjadikan metadata cluster sebagai topik internal berpartisi tunggal bernama `@metadata`.
- Menggunakan log replikasi deterministik berbasis Raft yang dikelola oleh broker berstatus controller.
- State metadata disimpan dalam bentuk *in-memory image* yang diperbarui secara berkesinambungan melalui streaming event record.
- **Failover Controller**: Ketika Active Controller mati, Follower Controller baru dapat mengambil alih secara instan ($<100\text{ ms}$) karena state metadata telah terproyeksikan di memorinya secara *real-time*.

#### 5.4 Replikasi, High Watermark (HW), dan Log End Offset (LEO)
Konsistensi partisi multi-broker diatur melalui koordinasi Leader dan Follower:
- **LEO (Log End Offset)**: Offset dari pesan berikutnya yang akan ditulis ke dalam log lokal sebuah replika.
- **HW (High Watermark)**: Offset pesan tertinggi yang telah berhasil disalin oleh seluruh replika yang terdaftar dalam ISR (*In-Sync Replicas*). Consumer hanya diizinkan membaca data hingga batas HW untuk mencegah *dirty read* atas data yang belum terduplikasi penuh.
- Replikasi digerakkan oleh inisiatif Follower yang secara berkala mengirimkan request `Fetch` ke Leader membawa nilai LEO terkini mereka.

---

### 6. Production-Ready Code Implementation

Berikut implementasi ingestion engine data berbasis Python berkinerja tinggi menggunakan pustaka `confluent-kafka` (binding C ke `librdkafka`), mengonfigurasi semantik *Idempotent Producer*, jaminan *Exactly-Once*, *graceful shutdown*, dan kompensasi kegagalan transmisi.

```python
"""
Kafka Engine: High-Throughput Resilient Producer Engine
Menggunakan C-based librdkafka abstraction layer untuk optimasi OS Page Cache write.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional
from confluent_kafka import KafkaError, KafkaException, Producer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("kafka-internals-producer")


@dataclass(frozen=True)
class ProducerMetrics:
    total_delivered: int
    total_failed: int


class ResilientLogProducer:
    def __init__(self, bootstrap_servers: str, client_id: str) -> None:
        self._shutdown_requested: bool = False
        self._delivered_count: int = 0
        self._failure_count: int = 0

        # Konfigurasi low-level librdkafka yang menyasar performa & jaminan ketat
        producer_config: Dict[str, str | int | bool] = {
            # Core Network Target
            "bootstrap.servers": bootstrap_servers,
            "client.id": client_id,
            
            # --- RELIABILITY & INTEGRITY CONFIGURATION ---
            # Menjamin broker menunggu seluruh ISR melakukan write commit log ke Page Cache
            "acks": "all",
            # Mengaktifkan Idempotence: mencegah duplikasi pada network retry (PID + Sequence Number)
            "enable.idempotence": True,
            "retries": 10000000,
            "max.in.flight.requests.per.connection": 5,  # Nilai aman <= 5 jika idempotence=True
            
            # --- PERFORMANCE & THROUGHPUT OPTIMIZATION ---
            # Mengizinkan batching lokal di level memori producer sebelum flush ke network
            "linger.ms": 20,                          # Menunggu pembentukan batch hingga 20ms
            "batch.size": 65536,                      # 64 KB memory buffer per batch
            "compression.type": "zstd",               # Kompresi Zstandard (rasio tinggi, hemat CPU)
            "queue.buffering.max.messages": 100000,   # Off-heap queue limit
            
            # Connection health monitoring
            "socket.keepalive.enable": True,
            "metadata.max.age.ms": 300000,            # Refresh metadata setiap 5 menit
        }

        try:
            self._producer: Producer = Producer(producer_config)
            logger.info("ResilientLogProducer berhasil diinisialisasi.")
        except KafkaException as ex:
            logger.critical(f"Inisialisasi Producer gagal: {str(ex)}")
            raise

        self._register_signals()

    def _register_signals(self) -> None:
        """Menangani sinyal OS untuk graceful shutdown guna mengosongkan local buffer."""
        signal.signal(signal.SIGINT, self._handle_termination)
        signal.signal(signal.SIGTERM, self._handle_termination)

    def _handle_termination(self, signum: int, frame: object) -> None:
        logger.warning(f"Sinyal terminasi [{signum}] diterima! Memulai proses pembersihan.")
        self._shutdown_requested = True

    def _delivery_report(self, err: Optional[KafkaError], msg: object) -> None:
        """
        Callback yang dieksekusi di background thread oleh librdkafka
        ketika broker mengembalikan Ack atau terjadi disk error permanen.
        """
        if err is not None:
            self._failure_count += 1
            logger.error(f"Kegagalan penulisan log: {err.str()} [Topic: {msg.topic()}]")
        else:
            self._delivered_count += 1
            # Komentar debug: Aktifkan hanya jika tracing individual message dibutuhkan
            # logger.debug(f"Offset committed: {msg.offset()} on partition {msg.partition()}")

    def publish_event(
        self, topic: str, key: str, payload: bytes, headers: Optional[Dict[str, bytes]] = None
    ) -> bool:
        """
        Mempublikasikan data biner ke segmen log broker secara non-blocking.
        """
        if self._shutdown_requested:
            logger.warning("Producer sedang shutdown. Menolak payload baru.")
            return False

        while True:
            try:
                # Producer.produce bersifat non-blocking: menaruh record di local batch buffer
                self._producer.produce(
                    topic=topic,
                    key=key.encode("utf-8"),
                    value=payload,
                    headers=headers,
                    on_delivery=self._delivery_report,
                )
                break
            except BufferError:
                # Local buffer Producer tersaturasi karena throughput melebihi kapasitas network
                logger.warning("Local produce queue tersaturasi. Melakukan backpressure polling...")
                self._producer.poll(0.1)  # Berikan kesempatan C-thread mengirim data ke socket
            except KafkaException as k_err:
                logger.error(f"Non-recoverable produce error: {str(k_err)}")
                self._failure_count += 1
                return False

        # Melayani delivery callbacks di background tanpa memblokir pipeline utama
        self._producer.poll(0)
        return True

    def close(self, timeout_sec: float = 30.0) -> ProducerMetrics:
        """
        Memastikan seluruh sisa data di memory buffer terkirim dan diakui broker.
        """
        logger.info(f"Mengosongkan buffer memory (flush timeout: {timeout_sec}s)...")
        remaining_events = self._producer.flush(timeout=timeout_sec)
        
        if remaining_events > 0:
            logger.error(f"{remaining_events} event hilang (drop) karena timeout pada shutdown.")
            self._failure_count += remaining_events
        else:
            logger.info("Seluruh buffer log berhasil dipetakan ke Broker Page Cache.")

        return ProducerMetrics(
            total_delivered=self._delivered_count,
            total_failed=self._failure_count,
        )


if __name__ == "__main__":
    # Smoke test eksekusi lokal (membutuhkan broker lokal pada port 9092)
    BROKER_ADDR = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    TOPIC = "telemetry-internal-stream"

    producer = ResilientLogProducer(bootstrap_servers=BROKER_ADDR, client_id="engine-core-prod-01")

    logger.info("Memulai simulasi streaming throughput tinggi...")
    for idx in range(1000):
        if producer._shutdown_requested:
            break
        key_str = f"sensor-node-{idx % 10}"
        # Simulasi payload biner
        payload_data = f'{{"timestamp": {time.time()}, "reading": {idx * 1.5}}}'.encode("utf-8")
        producer.publish_event(topic=TOPIC, key=key_str, payload=payload_data)

    metrics = producer.close()
    logger.info(f"Selesai. Terkirim: {metrics.total_delivered}, Gagal: {metrics.total_failed}")
```

---

### 7. Edge Cases & Failure Modes

#### 7.1 Under-Replicated Partitions (URP) & Network Partitioning
- **Penyebab**: Broker Follower gagal melakukan `Fetch` ke Leader dalam jangka waktu `replica.lag.time.max.ms` (umumnya terjadi akibat degradasi performa I/O disk, GC pause, atau network flap).
- **Mekanisme Kegagalan**: Broker follower dikeluarkan dari list ISR (*In-Sync Replicas*). Jika opsi konfigurasi broker `min.insync.replicas` diatur ke nilai `2`, dan ISR menyusut ke angka 1 saat producer menggunakan `acks=all`, setiap penulisan data baru akan ditolak dengan error `NotEnoughReplicasException`.
- **Mitigasi**: Pastikan `min.insync.replicas = (replication_factor - 1)`. Monitor metrik JMX `kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions`.

#### 7.2 OS Page Cache Thrashing & Dirty Page Eviction Latency
- **Penyebab**: Aktivitas pembacaan consumer lama (*cold reads* / historical reprocessing) mengakses segmen lama yang sudah terlempar dari RAM.
- **Mekanisme Kegagalan**: Kernel terpaksa melakukan pembacaan acak ke disk fisik untuk memuat segmen lama ke Page Cache. Hal ini menggusur (*evict*) data segmen baru (*active segment*) dari memori. Akibatnya, *real-time consumers* yang sebelumnya menikmati pembacaan latensi sub-milidetik dari RAM terdegradasi mengikuti latensi disk fisik (peningkatan latensi dari mikrodetik ke ratusan milidetik).
- **Mitigasi**: Pisahkan consumer data historis ke instance dedicated replica menggunakan fitur *Read Replica Isolation* atau atur `posix_fadvise` untuk mencegah *polluting* pada Page Cache sistem operasi.

#### 7.3 Poison Pill Messages & Corrupt Record Batches
- **Penyebab**: Aliran data biner korup akibat malfungsi hardware network card atau serialisasi data yang cacat.
- **Mekanisme Kegagalan**: Broker menolak payload melalui kegagalan kalkulasi CRC32. Jika data terlanjur lolos ke log broker, consumer runtime akan mengalami *infinite deserialization crash loop*.
- **Mitigasi**: Penerapan skema validasi ketat (Apache Avro / Protobuf) terintegrasi dengan Confluent Schema Registry. Terapkan Dead Letter Queue (DLQ) dengan batas batas maksimum retry berbasis interceptor.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi | Apache Kafka (KRaft) | Redpanda | Apache Pulsar | RabbitMQ |
| :--- | :--- | :--- | :--- | :--- |
| **Arsitektur Inti** | Distributed Commit Log | Thread-per-core Log (C++) | Segmented Log (BookKeeper) | AMQP Traditional Queue |
| **Runtime & Memori** | JVM + OS Page Cache | Native C++ (Direct I/O) | JVM + Netty Direct Memory | Erlang BEAM VM |
| **Konsensus Metadata** | KRaft (Internal Raft) | Raft Native Internal | Apache BookKeeper + ZK | Mnesia / Khepri Quorum |
| **Pola Konsumsi** | Read from Page Cache via `sendfile` | Bypass Cache (O_DIRECT DMA) | Tiered Cache via Broker Mem | In-Memory Queue Pointer |
| **Throughput Multi-GB** | Sangat Tinggi (Batching) | Ekstrem (Low Latency) | Tinggi (Horizontally Scalable)| Sedang ($<100\text{k msg/s}$) |
| **Kompleksitas Operasi**| Menengah | Rendah (Single Binary) | Sangat Tinggi (Broker + Bookie)| Rendah |

#### Kapan Menggunakan Kafka:
- Menjadi tulang punggung *backbone* data terpadu berskala enterprise dengan throughput jutaan event per detik.
- Kebutuhan pemrosesan ulang data historis (*replayability*) hingga berminggu-minggu ke belakang.
- Ekosistem ekstensif (Kafka Connect, Flink, Spark Streaming, Delta Lake).

#### Kapan Menggunakan Alternatif:
- **Redpanda**: Jika latensi P99 di bawah 5 milidetik merupakan syarat mati (*hard requirement*) dan tim ingin menghindari manajemen JVM tuning.
- **Apache Pulsar**: Ketika arsitektur memerlukan isolasi multi-tenant yang ketat dan pemisahan kapasitas penyimpanan vs komputasi secara independen (*Tiered Storage-first*).
- **RabbitMQ**: Untuk routing pesan kompleks berbasis *topic exchange* dinamis dengan volume pesan moderat tanpa kebutuhan *replayability*.

---

### 9. Best Practices & Standar Industri

#### 9.1 Konfigurasi Kernel Linux Tingkat Produksi
Tambahkan entri berikut pada `/etc/sysctl.conf` untuk server Kafka Broker:

```ini
# Menghindari swapout memori proses JVM ke disk swap
vm.swappiness = 1

# Meningkatkan rasio memori kotor (dirty pages) sebelum flush latar belakang dimulai
# Menjaga proses flush disk tetap stabil tanpa latency spike
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10

# Memperbesar buffer alokasi jaringan TCP sistem operasi
net.core.rmem_default = 262144
net.core.wmem_default = 262144
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Memaksimalkan batas file descriptor (Kafka memetakan banyak socket & log index)
fs.file-max = 1000000
```

#### 9.2 JVM Heap vs. OS Page Cache Sizing Rules
Sebuah kesalahan fatal arsitektur adalah mengalokasikan RAM fisik sebesar mungkin untuk JVM Heap Broker.
- **Rekomendasi Kapasitas**: Dari total server RAM 128 GB, alokasikan **hanya 16 GB - 32 GB untuk JVM Heap** (`-Xms32g -Xmx32g`).
- **Sisa RAM (96 GB+)**: Harus dibiarkan sepenuhnya bebas (*unreserved*) agar dimanfaatkan oleh Linux Kernel sebagai **OS Page Cache**. Hal ini memastikan seluruh baca-tulis pesan aktif tidak pernah menyentuh disk fisik.

#### 9.3 File System & Storage Media
- Format disk penyimpanan data broker selalu menggunakan **XFS** (bukan EXT4), karena XFS memiliki efisiensi alokasi disk sequential kontigu (*pre-allocation*) yang jauh lebih tinggi dalam menangani file sparse berskala besar.
- Mount XFS options: `noatime,nodiratime,nobarrier,logbufs=8`.

---

### 10. Hands-on Lab Exercise: Inspecting Kafka Internals

#### Skenario Lab
Anda bertindak sebagai Principal Data Engineer yang sedang melakukan audit integritas sistem storage broker. Anda akan:
1. Menjalankan Kafka single-node berbasis **KRaft** murni (tanpa ZooKeeper).
2. Memproduksi record ke dalam partisi.
3. Membedah langsung struktur file biner `.log`, `.index`, dan `.timeindex` menggunakan Kafka Storage Diagnostics Utility.

#### Langkah 1: Siapkan Environment KRaft (Docker Compose)
Simpan konfigurasi berikut sebagai `docker-compose.yml`:

```yaml
version: '3.8'
services:
  kafka-kraft:
    image: confluentinc/cp-kafka:7.5.0
    container_name: kafka-kraft-lab
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://kafka-kraft:29092,PLAINTEXT_HOST://localhost:9092'
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka-kraft:29093'
      KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:29092,CONTROLLER://0.0.0.0:29093,PLAINTEXT_HOST://0.0.0.0:9092'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_LOG_DIRS: '/tmp/kraft-combined-logs'
      CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'
```

Jalankan container:
```bash
docker compose up -d
```

#### Langkah 2: Buat Topic dengan Segment Sizing Miniatur
Kita kecilkan ukuran segmen log menjadi 512 KB agar terjadi *log rolling* secara cepat untuk diamati:

```bash
docker exec -it kafka-kraft-lab kafka-topics --bootstrap-server localhost:9092 \
  --create --topic internal-audit-topic \
  --partitions 1 \
  --replication-factor 1 \
  --config segment.bytes=524288 \
  --config index.interval.bytes=1024
```

#### Langkah 3: Generate Dataset Uji
Kirimkan rangkaian payload event menggunakan producer konsol bawaan:

```bash
docker exec -it kafka-kraft-lab bash -c '
for i in {1..2000}; do
  echo "key-$i:payload-event-telemetry-internals-testing-sequence-$i"
done | kafka-console-producer --bootstrap-server localhost:9092 \
  --topic internal-audit-topic \
  --property "parse.key=true" \
  --property "key.separator=:"
'
```

#### Langkah 4: Bedah Struktur Binary Storage Menggunakan `DumpLogSegments`
Periksa file-file yang terbuat di direktori partisi:

```bash
docker exec -it kafka-kraft-lab ls -la /tmp/kraft-combined-logs/internal-audit-topic-0/
```

Jalankan utility `DumpLogSegments` untuk membaca record header biner dari file `.log`:

```bash
docker exec -it kafka-kraft-lab kafka-run-class kafka.tools.DumpLogSegments \
  --files /tmp/kraft-combined-logs/internal-audit-topic-0/00000000000000000000.log \
  --print-data-log \
  --deep-iteration
```

*Output Verifikasi Lab yang Diharapkan:*
```text
Dumping /tmp/kraft-combined-logs/internal-audit-topic-0/00000000000000000000.log
Starting offset: 0
baseOffset: 0 lastOffset: 48 baseSequence: 0 lastSequence: 48 producerId: -1 producerEpoch: -1 partitionLeaderEpoch: 0 isTransactional: false isControl: false position: 0 CreateTime: 1710000000000 size: 3120 magic: 2 compresscodec: NONE crc: 21948194 payload: ...
```

Bedah file sparse index (`.index`) untuk melihat pemetaan offset-to-physical address:

```bash
docker exec -it kafka-kraft-lab kafka-run-class kafka.tools.DumpLogSegments \
  --files /tmp/kraft-combined-logs/internal-audit-topic-0/00000000000000000000.index \
  --verify-index-only
```

Analisis output log dump: Perhatikan korelasi antara parameter `position` pada output `.index` dengan file offset fisik pada file `.log`. Ini membuktikan mekanisme pencarian log Kafka tidak pernah bergantung pada pemindaian linier menyeluruh (full table scan), melainkan kombinasi *binary search* sparse index dan *sequential direct-read* pada OS Page Cache.