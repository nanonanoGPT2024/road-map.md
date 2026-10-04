# Kurikulum Enterprise Data Engineering
## Bab 05: Apache Kafka Internals & Distributed Log Architecture
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Menganalisis Mekanisme Low-Level Storage Engine**: Membedah struktur internal log segment (`.log`, `.index`, `.timeindex`), cara kerja memory-mapped files (`mmap`), serta peran Linux Page Cache dan syscall `sendfile(2)` (Zero-Copy) dalam mencapai throughput jutaan event per detik.
*   **Mengonfigurasi Konsistensi & Durabilitas Terdistribusi**: Menguasai interaksi antara Log End Offset (LEO), High Watermark (HW), In-Sync Replicas (ISR), dan Leader Epoch untuk mencegah data loss dan truncation anomalies saat leader failure.
*   **Mengimplementasikan Exactly-Once Semantics (EOS v2)**: Membangun pipeline transactional producer-consumer berbasis Two-Phase Commit melalui `__transaction_state` topic dan transactional coordinator.
*   **Mengoptimalkan Consumer Group Coordination**: Mengonfigurasi *Incremental Cooperative Rebalance* untuk meminimalkan *stop-the-world rebalance pauses* pada kluster berskala ribuan consumer.
*   **Mendiagnosis dan Melakukan Tuning Produksi**: Mengidentifikasi bottleneck pada I/O kernel, mendiagnosis consumer lag, memitigasi disk skew, serta melakukan sizing partisi dan JVM heap secara presisi untuk beban kerja enterprise.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
*   Dasar arsitektur publish-subscribe dan konsep Apache Kafka tingkat dasar (Broker, Topic, Partition, Offset, Consumer Group).
*   Dasar sistem operasi Linux: Virtual Memory, Page Cache, System Calls (`read`, `write`, `sendfile`), File Descriptors, dan TCP Socket Buffer.
*   Pemrograman konkuren dan jaringan tingkat menengah menggunakan Java, Scala, Go, atau Python.
*   Konsep konsistensi sistem terdistribusi (CAP Theorem, PACELC, Split-Brain, Consensus Models).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Anatomy of a Kafka Log Segment & Zero-Copy I/O
Kafka tidak menyimpan data dalam basis data relasional atau B-Tree terstruktur biasa. Data disimpan dalam bentuk append-only log terdistribusi yang dibagi ke dalam segmen-segmen file di disk.

```
/var/lib/kafka/data/telemetry-events-0/
│
├── 00000000000000000000.log             <-- Raw byte records payload
├── 00000000000000000000.index           <-- Sparse index: Offset -> Physical File Position
├── 00000000000000000000.timeindex       <-- Sparse index: Timestamp -> Offset
├── 00000000000010543201.snapshot        <-- Producer State (PID, Sequence Number)
└── leader-epoch-checkpoint              <-- Mapping Leader Epoch -> Start Offset
```

1.  **Append-Only Sequential Writes**: Penulisan sekuensial ke media penyimpanan (bahkan pada spinning HDD konvensional) mencapai performa mendekati memori bus (`~600-800 MB/s`), menghindari operasi random seek pada struktur tree.
2.  **Sparse Indexing**: Kafka tidak memetakan setiap offset secara individual ke disk. Melalui konfigurasi `index.interval.bytes` (default: 4096 bytes), Kafka menambahkan entri index setiap 4 KB payload log. Ketika membaca offset target, Kafka melakukan *binary search* pada file `.index` yang berada di RAM (`mmap`), kemudian membaca sekuensial dari posisi fisik byte terdekat di file `.log`.
3.  **Kernel Page Cache vs. JVM Heap**: Broker Kafka didesain berjalan dengan JVM heap kecil (umumnya 6 GB – 8 GB) meskipun server memiliki 128 GB RAM. Sisa RAM dimanfaatkan sepenuhnya oleh Linux OS sebagai **Page Cache**. Hal ini meminimalkan overhead Garbage Collection (GC) pauses dan mempertahankan cache data log tetap hidup meskipun proses broker Kafka di-restart.
4.  **Zero-Copy Network Transfer (`sendfile`)**:
    *   *Traditional read path*: Disk $\rightarrow$ OS Page Cache $\rightarrow$ User Space JVM Buffer $\rightarrow$ Socket Buffer (Kernel) $\rightarrow$ NIC Buffer. (4 Context switches, 3 copy data).
    *   *Kafka Zero-Copy path*: Menggunakan system call `sendfile(2)`. Disk $\rightarrow$ OS Page Cache $\rightarrow$ Langsung via DMA (Direct Memory Access) ke NIC Buffer. (2 Context switches, 0 copy data di CPU/User Space).

#### B. Replication Protocol: LEO, High Watermark, dan Leader Epoch
Replikasi Kafka menjaga konsistensi partisi melalui mekanisme ISR (In-Sync Replicas):

*   **Log End Offset (LEO)**: Offset berikutnya yang akan ditulis ke dalam log broker (baik leader maupun follower).
*   **High Watermark (HW)**: Offset tertinggi yang telah direplikasi secara sukses ke seluruh node di dalam ISR list. Data di bawah HW dinyatakan *committed* dan aman untuk dibaca oleh consumer.
*   **Leader Epoch Mechanism**: Sebelum Kafka 0.11, pemulihan pasca-kegagalan hanya bergantung pada High Watermark, yang dapat menimbulkan *truncation loop anomaly* (replika memotong log yang valid saat restart) atau *log divergence*. Leader Epoch memperkenalkan integer monolitik yang dinaikkan setiap kali terjadi pergantian leader. Setiap broker mencatat pasangan `(Epoch, StartOffset)`. Ketika follower mengalami crash dan recover, ia memvalidasi checkpoint epoch-nya langsung ke leader untuk menentukan titik potong log yang tepat, mencegah data hilang saat crash beruntun.

```
Partition 0 (ISR: [Broker-1 (Leader), Broker-2 (Follower)])

Broker-1 (Leader)
Log:    [E0: Off 0] [E0: Off 1] [E1: Off 2] [E1: Off 3] | (LEO = 4)
                                            ^
                                        HW = 3

Broker-2 (Follower)
Log:    [E0: Off 0] [E0: Off 1] [E1: Off 2]             | (LEO = 3, HW = 3)
```

#### C. KRaft: Event-Driven Distributed Metadata Engine
Pada arsitektur modern (Kafka 3.3+ GA), ZooKeeper dieliminasi dan digantikan oleh **KRaft (Kafka Raft Metadata Mode)**:
*   Status kluster direpresentasikan sebagai topic internal bernama `@metadata`.
*   Broker yang bertindak sebagai Controller Quorum mengelola log metadata menggunakan konsensus varian Raft.
*   Perubahan metadata dipropagasikan secara real-time ke semua broker via streaming replication, meniadakan latensi sinkronisasi O(N) yang sebelumnya terjadi pada ZooKeeper saat terjadi failover kluster berskala besar (ratusan ribu partisi).

#### D. Exactly-Once Semantics (EOS v2) & Transaction Internals
Untuk mencapai pemrosesan end-to-end atomic (Read-Process-Write) tanpa duplikasi atau kehilangan data:
1.  **Idempotent Producer**: Menggunakan kombinasi `Producer ID (PID)` (diberikan oleh broker) dan monotonik `Sequence Number (SN)` per partisi. Broker menolak pesan duplikat jika $SN_{incoming} \le SN_{last\_committed}$.
2.  **Transaction Coordinator**: Broker yang mengelola state machine transaksi melalui topic internal `__transaction_state`.
3.  **Two-Phase Commit Sequence**:
    *   Producer mendaftarkan partisi ke Coordinator (`AddPartitionsToTxnRequest`).
    *   Data dikirim ke target log dengan status uncommitted.
    *   Producer mengirim offset konsumsi ke consumer group coordinator via transactional context (`AddOffsetsToTxnRequest`).
    *   Coordinator menulis status `PREPARE_COMMIT` ke `__transaction_state`.
    *   Coordinator menulis *Commit Markers* khusus langsung ke topic target dan consumer offsets topic.
    *   Coordinator menandai transaksi sebagai `COMMITTED`.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Message Broker / DB) | Kafka Internal Distributed Log |
| :--- | :--- | :--- |
| **Model Antrean vs Log** | Pesan dihapus seketika setelah di-acknowledge oleh consumer (*destructive reads*). | Append-only immutable log. Multi-consumer dapat membaca data secara independen pada offset berbeda. |
| **Indexing Data** | B-Tree Index berat, disk fragmentation tinggi saat write throughput melonjak. | Sequential write tanpa random updates, sparse index hemat memori. |
| **I/O & Memory Management** | Aplikasi me-manage cache memory sendiri di User Space; GC pressure tinggi. | Offload memory caching ke kernel OS (Linux Page Cache) dan transfer via Zero-Copy (`sendfile`). |
| **Skalabilitas Metadata** | Menggunakan shared database eksternal (misal: Apache ZooKeeper) yang bottleneck pada jutaan partisi. | Metadata terdistribusi KRaft terintegrasi sebagai log internal broker, recovery sub-detik. |

---

### 5. How (Workflow Detail)

#### Pipeline Transaksi End-to-End (Read - Process - Write Atomic)

```
[Upstream Topic] 
       │ 
       ▼ (1) consumer.poll()
[Transaction Consumer / Processor] 
       │ 
       ├── (2) producer.beginTransaction()
       │
       ├── (3) Koordinasi: AddPartitionsToTxnRequest ──> [Transaction Coordinator]
       │                                                         │ (Tulis ke __transaction_state)
       ├── (4) producer.send(Downstream Topic)                    ▼
       │       └── Payload ditulis ke Broker Log (Belum Committed)
       │
       ├── (5) producer.sendOffsetsToTransaction(offsets, group_id)
       │       └── Koordinasi Commit Offset Konsumsi via Transaksi
       │
       ├── (6) producer.commitTransaction()
       │       └── Transaction Coordinator menulis PREPARE_COMMIT ke __transaction_state
       │       └── Coordinator broadcast "Commit Marker" ke Topic Partisi & __consumer_offsets
       │       └── Transaction Coordinator menulis COMMITTED
       ▼
[Downstream Topic] (Data kini terlihat oleh Consumer dengan `read_committed`)
```

1.  **Inisialisasi**: Aplikasi producer menginisialisasi `transactional.id` statis melalui `producer.initTransactions()`. Broker memastikan instance zombie lama dengan transactional ID yang sama dihentikan (Epoch fencing).
2.  **Message Fetch**: Consumer membaca pesan dari upstream topic dengan isolasi level `read_committed`.
3.  **Transaction Begin**: `producer.beginTransaction()` membuka konteks transaksi lokal.
4.  **Registering Partitions**: Saat pesan diproduksi ke partisi tujuan baru, producer mendaftarkan partisi tersebut ke Transaction Coordinator.
5.  **Produce & Consumer Offset Binding**: Pesan dikirim ke broker target. Offset dari consumer upstream diikat ke transaksi menggunakan `sendOffsetsToTransaction`.
6.  **Two-Phase Commit**:
    *   Coordinator menerima instruksi commit.
    *   Log status transaksi di-commit ke `__transaction_state`.
    *   Write *Control Batch* (Commit Marker) ke partisi log downstream dan `__consumer_offsets`.
    *   Consumer downstream yang diset dengan `isolation.level = read_committed` memajukan Last Stable Offset (LSO) dan memproses payload.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Buku Besar Notaris Terbuka
Bayangkan sebuah kantor notaris:
*   **Log File**: Notaris menulis setiap transaksi pada sebuah buku folio besar tanpa pernah menghapus baris lama. Tulisan dibuat hanya di baris paling bawah secara terus-menerus (Append-Only Log).
*   **Sparse Index**: Notaris menaruh sticky note kecil setiap kelipatan 100 halaman (Sparse Index) yang mencatat "Halaman 100 ada di Offset Transaksi #5000", sehingga ketika mencari Transaksi #5230, notaris langsung membuka halaman 100 lalu membaca sekilas ke bawah, bukan memeriksa dari halaman 1.
*   **Zero-Copy**: Notaris tidak menyalin ulang dokumen dengan tangan ke kertas draf miliknya lalu memfotokopi dan mengirimkannya. Notaris langsung memasukkan dokumen asli ke tabung transmisi pneumatik khusus (DMA) menuju ruangan klien secara langsung.

#### Diagram Arsitektur Internal Broker Storage Engine

```
+-----------------------------------------------------------------------------------+
| KAFKA BROKER STORAGE ENGINE & LINUX OS LAYER                                      |
|                                                                                   |
|  +--------------------+         sendfile(2)           +------------------------+  |
|  |  Linux Page Cache  | ----------------------------> | NIC / Network Card     |  |
|  |  (Dirty/Clean RAM) | (Direct Memory Access - Zero) | (Socket Buffer to Net) |  |
|  +--------------------+                               +------------------------+  |
|            ^                                                       |              |
|            | OS Flush (pdflush/flush thread)                       v              |
|            v                                              Kafka Consumer Engine   |
|  +----------------------------------------------------+                           |
|  | DISK PERSISTENCE LAYER: LOG SEGMENT DIRECTORY      |                           |
|  |                                                    |                           |
|  |  [00000000000000000000.index]                      |                           |
|  |  +--------------------------+                      |                           |
|  |  | Rel Offset | Byte Offset | (Memory Mapped File) |                           |
|  |  |------------|-------------|                      |                           |
|  |  | 0          | 0           |                      |                           |
|  |  | 4          | 4096        |                      |                           |
|  |  | 9          | 9214        |                      |                           |
|  |  +--------------------------+                      |                           |
|  |               |                                    |                           |
|  |               v (Direct Pointer Jump)              |                           |
|  |  [00000000000000000000.log]                        |                           |
|  |  +----------------------------------------------+  |                           |
|  |  | CRC | Magic | Timestamp | Size | Key | Payload |  |                           |
|  |  |----------------------------------------------|  |                           |
|  |  | Pos: 0      | Size: 1024 bytes               |  |                           |
|  |  | Pos: 4096   | Size: 2048 bytes               |  |                           |
|  |  | Pos: 9214   | Size: 4096 bytes               |  |                           |
|  |  +----------------------------------------------+  |                           |
|  +----------------------------------------------------+                           |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Low-Level Log Segment Inspection
Gunakan script bawaan Kafka untuk membedah binary storage log dan index secara langsung.

```bash
# Dump isi sparse index file untuk melihat mapping offset ke posisi fisik byte
kafka-run-class.sh kafka.tools.DumpLogSegments \
  --files /var/lib/kafka/data/payment-events-0/00000000000000000000.index \
  --verify-index-only

# Output Analisis:
# offset: 104 position: 4096
# offset: 215 position: 8192
# offset: 320 position: 12288

# Dump isi binary log data payload lengkap dengan metadata Leader Epoch
kafka-run-class.sh kafka.tools.DumpLogSegments \
  --files /var/lib/kafka/data/payment-events-0/00000000000000000000.log \
  --print-data-log \
  --deep-iteration

# Perhatikan parameter: baseOffset, payload size, sequence, producerId, leaderEpoch
```

#### B. Practical Example: Production-Grade Transactional Pipeline (Java)
Aplikasi pemrosesan stream finansial: Membaca dari topic input, mengubah payload, dan menulis ke topic output secara atomik (Exactly-Once Semantics).

```java
package com.enterprise.kafka.pipeline;

import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.KafkaException;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.errors.ProducerFencedException;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.*;

public class TransactionalEventProcessor {
    private static final Logger log = LoggerFactory.getLogger(TransactionalEventProcessor.class);
    private static final String INPUT_TOPIC = "orders.raw";
    private static final String OUTPUT_TOPIC = "orders.processed";
    private static final String CONSUMER_GROUP = "order-processor-group";

    public static void main(String[] args) {
        String bootstrapServers = "broker1:9092,broker2:9092,broker3:9092";
        String transactionalId = "order-processor-tx-node-01";

        // 1. Konfigurasi Producer Transaksional
        Properties producerProps = new Properties();
        producerProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        producerProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, transactionalId);
        producerProps.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, "true");
        producerProps.put(ProducerConfig.ACKS_CONFIG, "all");
        producerProps.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, "5");
        producerProps.put(ProducerConfig.RETRIES_CONFIG, Integer.toString(Integer.MAX_VALUE));

        // 2. Konfigurasi Consumer Berbasis Read-Committed
        Properties consumerProps = new Properties();
        consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, CONSUMER_GROUP);
        consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName