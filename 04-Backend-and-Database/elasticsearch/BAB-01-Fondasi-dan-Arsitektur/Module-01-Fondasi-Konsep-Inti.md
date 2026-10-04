# Module 01: Arsitektur Terdistribusi Elasticsearch & Anatomi Mesin Pencari Lucene

---

## 1. Metadata & Kurikulum Header

*   **Module ID**: `ES-B01M01`
*   **Path**: `elasticsearch/bab-01-fondasi-dan-arsitektur/01-anatomi-klaster-dan-lucene`
*   **Prasyarat**: 
    *   Pemahaman dasar arsitektur terdistribusi (Client-Server, konsistensi data, replikasi).
    *   Kemahiran menggunakan protokol HTTP/REST API dan manipulasi format JSON.
    *   Familiaritas dasar administrasi sistem Linux (POSIX signals, memory management, `sysctl`).
    *   Pemrograman dasar menggunakan Python 3.10+ atau manipulasi shell via `curl`.
*   **Target Skor Akhir**: Penguasaan teknis penuh terhadap mekanisme kerja internal Elasticsearch dan Apache Lucene, dibuktikan dengan skor asesmen mandiri minimal 85% serta kemampuan menganalisis layout shard dan segment lifecycle.
*   **Rekomendasi Alokasi Waktu**: 8 Jam Pembelajaran Mandiri / Praktikum Lab (3 Jam Teori Arsitektur, 3 Jam Eksekusi Praktikum & Inspeksi Cluster, 2 Jam Pemecahan Kasus & Edge Cases).

---

## 2. Executive Summary

Elasticsearch adalah distributed search and analytics engine yang dibangun di atas pustaka information retrieval open-source Apache Lucene. Sering kali terjadi miskonsepsi di mana Elasticsearch diperlakukan layaknya relational database management system (RDBMS) standar atau sekadar key-value document store. Perlakuan keliru ini berujung pada performa pencarian yang terdegradasi, konsumsi resource yang tidak terkendali, dan ketidakstabilan cluster. 

Modul ini membedah arsitektur dasar Elasticsearch dari layer paling dasar: struktur *Inverted Index* pada Apache Lucene, sifat *immutability* dari segment, transisi memory buffer ke disk storage (*refresh* vs *flush*), hingga mekanisme orkestrasi terdistribusi via *primary-replica shards* dan topologi *node roles*. Melalui modul ini, software engineer dan site reliability engineer (SRE) akan memahami secara deterministik bagaimana dokumen diindeks, disimpan, direplikasi, dan dicari secara *Near Real-Time* (NRT).

---

## 3. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik mampu:
1.  **Menganalisis** struktur internal Apache Lucene (Directory, Segment, Inverted Index, Term Dictionary, Postings List) untuk memprediksi karakteristik komputasi dan I/O dari query pencarian.
2.  **Mendemonstrasikan** alur data write path (Indexing) dan read path (Search) dari request HTTP yang diterima REST layer hingga tersimpan dan terbaca dari segment disk.
3.  **Merancang** topologi cluster dasar dengan pemisahan node roles yang optimal (Master-eligible, Data, Ingest, Coordinating-only) guna memitigasi single point of failure dan resource starvation.
4.  **Mengonfigurasi** dan mengoperasikan single-node/multi-node cluster melalui API internal untuk memvalidasi alokasi index, shard, dan replica secara terprogram.
5.  **Mendiagnosis** trade-off antara throughput penulisan (ingestion rate), konsumsi memori (JVM Heap vs OS Page Cache), dan latensi query (search latency).

---

## 4. Motivasi Teknis & Domain Problem

Basis data relasional konvensional (misalnya PostgreSQL atau MySQL) mengandalkan struktur indeks **B-Tree** atau variasinya (B+ Tree). Struktur ini bekerja optimal untuk operasi *point lookup* (`WHERE id = 12345`) dan *range queries* pada data terstruktur berdimensi rendah (`WHERE created_at >= '2023-01-01'`).

Namun, saat berhadapan dengan data tekstual berskala besar, analitik log semi-terstruktur, atau pencarian teks bebas (full-text search) multibahasa dengan operator fuzzy dan scoring relevansi, B-Tree mengalami degradasi komputasi:
*   Pola pencarian `WHERE content LIKE '%distributed system%'` memaksa engine melakukan **Full Table Scan**, membaca seluruh page disk secara sekuensial dengan kompleksitas $O(N)$.
*   B-Tree tidak dirancang untuk menangani variasi linguistik (stemming, lemmatization, stop words, synonym mapping).
*   B-Tree tidak memiliki native term weighting algorithms (seperti TF-IDF atau Okapi BM25) untuk mengukur relevansi semantik dokumen.

```
Pendekatan RDBMS Tradisional (B-Tree Scan):
Query: LIKE '%search%'
Row 1: [ "Elasticsearch cluster architecture" ] -> Scan Byte-by-Byte (Miss / Partial Match)
Row 2: [ "Apache Lucene core search engine" ]    -> Scan Byte-by-Byte (Match)
...
Row N: [ ... ]                                   -> Scan O(N) -> Disk I/O Bottleneck

Pendekatan Lucene Inverted Index:
Query: "search"
Index Lookup:
Term "search" -> Postings List: [Doc 1, Doc 2, Doc 50493, Doc 92011] -> Resolusi O(1) Term Lookup!
```

Elasticsearch menyelesaikan masalah ini dengan mendistribusikan pustaka Apache Lucene ke dalam arsitektur klaster horizontal. Mesin ini mengabstraksikan kompleksitas sharding, state consensus, replikasi data, dan agregasi analitik paralel, menyediakan latensi query sub-detik untuk miliaran data terdistribusi.

---

## 5. Konsep Dasar & Teori Inti

### 5.1 Struktur Data Lucene: The Inverted Index
Inti dari kapabilitas pencarian teks adalah **Inverted Index**. Alih-alih memetakan dokumen ke kata-kata yang dikandungnya (Forward Index), Inverted Index memetakan kata unik (**Term**) ke daftar dokumen di mana kata tersebut muncul (**Postings List**).

Sebuah Inverted Index tersusun atas:
1.  **Term Dictionary**: Koleksi berurutan dari semua kata unik yang telah melewati proses analisis teks (tokenization, lowercasing, stemming).
2.  **Term Index (FST - Finite State Transducer)**: Representasi graf terkompresi dari prefix Term Dictionary yang disimpan seluruhnya di memori (RAM) untuk mempercepat pencarian posisi offset term di disk tanpa melakukan binary search penuh pada disk.
3.  **Postings List**: Array ID dokumen (DocID) tempat term berada, beserta metadata tambahan seperti frekuensi kemunculan term dalam dokumen (Term Frequency), posisi kata (Position untuk Phrase Query), dan offset karakter (untuk Highlighting).

### 5.2 Konsep Immutability Segment
Lucene menulis data ke dalam unit penyimpanan independen bernama **Segment**. Segment bersifat **immutable** (tidak dapat diubah setelah ditulis ke disk).
*   **Konsekuensi Immutability**:
    *   Tidak diperlukan lock concurrency pada level file saat membaca, mengizinkan pembacaan paralel dengan throughput tinggi.
    *   OS Page Cache tetap bersih (*clean pages*) dan tidak perlu di-flush berulang kali ke disk jika tidak ada operasi penulisan pada segment tersebut.
    *   Operasi **Delete** tidak menghapus data secara langsung dari segment, melainkan mencatat DocID pada bitset file terpisah berkestensi `.del`. Dokumen tersebut difilter saat query dan baru dibersihkan secara fisik ketika terjadi **Segment Merge**.
    *   Operasi **Update** diimplementasikan sebagai operasi *delete* lama (penandaan pada file `.del`) diikuti dengan operasi *create* dokumen versi baru di segment baru.

### 5.3 Abstraksi Entitas Elasticsearch
*   **Document**: Unit data terkecil berupa JSON object yang memiliki identitas unik (`_id`).
*   **Index**: Namespace logis tempat dokumen bernaung (secara konseptual setara dengan Tabel pada RDBMS).
*   **Shard**: Partisi fisik dari sebuah Elasticsearch Index. **Satu Shard Elasticsearch secara struktural adalah satu instance Apache Lucene yang lengkap.**
    *   **Primary Shard**: Shard utama yang memvalidasi dan menulis data sebelum mereplikasikannya.
    *   **Replica Shard**: Salinan identik dari Primary Shard. Bertujuan untuk fault tolerance (failover jika node mati) dan meningkatkan read throughput.
*   **Cluster**: Kumpulan dari satu atau lebih node yang saling terhubung dan berbagi metadata yang sama (**Cluster State**).

---

## 6. Arsitektur & Cara Kerja

### 6.1 Topologi Klaster dan Node Roles
Elasticsearch menggunakan arsitektur multi-node di mana setiap node dapat dikonfigurasi secara spesifik menjalankan peran (*role*) tertentu:
*   `master`: Bertanggung jawab atas stabilitas klaster, modifikasi cluster state, pembuatan/penghapusan index, dan alokasi shard ke node. Hanya satu node yang bertindak sebagai *Active Master* pada satu waktu (dipilih via algoritma konsensus Raft-derived Zen Discovery v2).
*   `data`: Menyimpan shard data dan mengeksekusi operasi I/O intensif (query pencarian, agregasi data, segment merges).
*   `ingest`: Memproses pipeline transformasi data (pre-processing via Ingest Pipelines) sebelum dokumen diindeks secara permanen.
*   `coordinating-only`: Node tanpa role master/data yang bertindak murni sebagai smart load balancer: menerima HTTP request dari client, mendistribusikan query ke node data yang relevan, mengagregasi hasil dari berbagai shard, lalu mengembalikannya ke client.

### 6.2 The Write Path (Alur Pengindeksan Dokumen)
Ketika client mengirimkan request `POST /my-index/_doc/1`:

```
Client
  │ (1) POST /my-index/_doc/1
  ▼
Coordinating Node
  │ (2) Hitung Routing: Shard ID = Murmur3(_id) % Total_Primary_Shards
  ▼
Primary Shard (Node A)
  ├── (3) Tulis ke Translog (Disk - append only sequential)
  ├── (4) Tulis ke In-Memory Indexing Buffer
  │
  │ (5) Replikasi Paralel via Network RPC
  ▼
Replica Shard (Node B)
  ├── (6) Tulis ke Translog
  └── (7) Tulis ke In-Memory Indexing Buffer
```

1.  Client mengirim request ke node mana pun (**Coordinating Node**).
2.  Coordinating node menentukan shard tujuan menggunakan formula perutean konsisten:
    $$\text{Shard ID} = \text{hash}(\text{routing\_value}) \pmod{\text{number\_of\_primary\_shards}}$$
    Secara default, `routing_value` adalah `_id` dokumen.
3.  Request diteruskan ke node penampung **Primary Shard**.
4.  Primary Shard memproses penulisan:
    *   Dokumen ditulis ke file log transaksi sekuensial di disk yang disebut **Translog** (Transaction Log) untuk mengantisipasi crash/data loss.
    *   Dokumen di-parse dan ditulis ke **In-Memory Indexing Buffer**. Pada status ini, dokumen **belum bisa dicari**.
5.  Setelah sukses lokal, request replikasi dikirimkan secara paralel ke seluruh **Replica Shards**.
6.  Setelah primary dan quorum minimum replika berhasil menulis, response `201 Created` dikembalikan ke client.

### 6.3 Siklus Hidup Segment: Memory Buffer, Refresh, dan Flush
Bagaimana dokumen dari memory buffer menjadi segment disk yang searchable dan persistent?

```
[In-Memory Indexing Buffer]  ──( Refresh: ~1s )──>  [OS Page Cache (New Segment)]  <── Read-Searchable!
           │                                                       │
      (Translog)                                             (fsync Flush: ~30m)
           ▼                                                       ▼
[Translog on Disk (Durability)] ─────────────────────────>  [Permanent Segment on Disk]
```

*   **Refresh (`POST /index/_refresh`)**:
    *   Secara default terjadi otomatis setiap **1 detik** (`index.refresh_interval: 1s`).
    *   Data di *In-Memory Indexing Buffer* dikonversi menjadi Segment Lucene baru dan ditulis ke dalam **OS Page Cache** (memori kernel OS, belum di-fsync ke disk fisik).
    *   Saat segment berada di Page Cache, segment tersebut langsung dibuka untuk pembacaan. Inilah mekanisme **Near Real-Time (NRT)** Elasticsearch: latensi dokumen baru hingga bisa dicari adalah ~1 detik.
*   **Flush (`POST /index/_flush`)**:
    *   Terjadi berkala (default: ukuran translog mencapai 512MB atau interval waktu 30 menit).
    *   Semua segment yang masih berada di OS Page Cache dipaksa untuk ditulis permanen ke media fisik disk melalui operasi system call `fsync()`.
    *   Translog lama yang sudah ter-commit di-truncate dan dibuat translog kosong baru.

### 6.4 The Read Path (Alur Pencarian: Query Phase & Fetch Phase)
Pencarian teks terdistribusi diselesaikan dalam dua fase:
1.  **Query Phase**:
    *   Coordinating node menyebarkan query ke seluruh shard yang terlibat (bisa Primary atau Replica, dipilih via algoritma *adaptive replica selection*).
    *   Setiap shard mengeksekusi pencarian lokal terhadap segment-segment miliknya, menghitung skor relevansi (BM25), dan membangun local priority queue berukuran `from + size`.
    *   Setiap shard hanya mengembalikan metadata ringan ke coordinating node: **DocID** dan **Score**.
2.  **Fetch Phase**:
    *   Coordinating node menggabungkan (merge-sort) hasil dari semua shard untuk menentukan ranking global top-$K$.
    *   Coordinating node mengirimkan request pengambilan dokumen spesifik (berdasarkan DocID) hanya ke shard-shard pemilik dokumen teratas tersebut untuk mengekstrak payload `_source` asli.
    *   Coordinating node merangkai respons JSON utuh dan mengembalikannya ke client.

---

## 7. Diagram Arsitektur ASCII

```
+===================================================================================================+
|                                    ELASTICSEARCH CLUSTER                                          |
+===================================================================================================+
|                                                                                                   |
|  [ Coordinating Node ] <====== Client HTTP / REST Request (Search / Index)                        |
|           |                                                                                       |
|   +-------+-------------------------------------------------------+                               |
|   | Routing: Murmur3(_id) % Total_Primary_Shards                  |                               |
|   v                                                               v                               |
| +-----------------------------------------+   +-----------------------------------------+         |
| | NODE A (Data Node)                      |   | NODE B (Data Node)                      |         |
| |                                         |   |                                         |         |
| |  [ Primary Shard 0 ]                    |   |  [ Replica Shard 0 ]                    |         |
| |  +-----------------------------------+  |   |  +-----------------------------------+  |         |
| |  | Apache Lucene Instance            |  |   |  | Apache Lucene Instance            |  |         |
| |  |                                   |  |   |  |                                   |  |         |
| |  |  +-----------------------------+  |  |   |  |  +-----------------------------+  |  |         |
| |  |  | In-Memory Index Buffer      |  |  |   |  |  | In-Memory Index Buffer      |  |  |         |
| |  |  +-----------------------------+  |  |   |  |  +-----------------------------+  |  |         |
| |  |                 | (refresh ~1s)   |  |   |  |                 |                 |  |         |
| |  |                 v                 |  |   |  |                 v                 |  |         |
| |  |  +-----------------------------+  |  |   |  |  +-----------------------------+  |  |         |
| |  |  | OS Page Cache (Segments)    |  |  |   |  |  | OS Page Cache (Segments)    |  |  |         |
| |  |  +-----------------------------+  |  |   |  |  +-----------------------------+  |  |         |
| |  |                 | (fsync flush)   |  |   |  |                 |                 |  |         |
| |  |                 v                 |  |   |  |                 v                 |  |         |
| |  |  +-----------------------------+  |  |   |  |  +-----------------------------+  |  |         |
| |  |  | Disk Persistent Segments    |  |  |   |  |  | Disk Persistent Segments    |  |  |         |
| |  |  |  - Inverted Index           |  |  |   |  |  |  - Inverted Index           |  |  |         |
| |  |  |  - Doc Values (Columnar)    |  |  |   |  |  |  - Doc Values (Columnar)    |  |  |         |
| |  |  |  - Stored Fields (_source)  |  |  |   |  |  |  - Stored Fields (_source)  |  |  |         |
| |  |  +-----------------------------+  |  |   |  |  +-----------------------------+  |  |         |
| |  +-----------------------------------+  |   |  +-----------------------------------+  |         |
| |                                         |   |                                         |         |
| |  [ Translog (Write-Ahead Log Disk) ]    |   |  [ Translog (Write-Ahead Log Disk) ]    |         |
| +-----------------------------------------+   +-----------------------------------------+         |
|                                                                                                   |
+===================================================================================================+
|                                    INTERNAL LUCENE SEGMENT                                        |
+===================================================================================================+
|                                                                                                   |
|   TERM DICTIONARY                      POSTINGS LIST (Inverted Index)                             |
|  +-------------------+               +-------------------------------------------------------+    |
|  | Term              | ------------> | DocID  | Term Freq | Positions (Offsets)             |    |
|  +-------------------+               +-------------------------------------------------------+    |
|  | "arsitektur"      | ------------> | [101]  |    1      | [pos: 2]                        |    |
|  | "distributed"     | ------------> | [101]  |    2      | [pos: 1, pos: 5]                |    |
|  | "elasticsearch"   | ------------> | [101]  |    1      | [pos: 0]                        |    |
|  |                   | ------------> | [102]  |    1      | [pos: 0]                        |    |
|  | "lucene"          | ------------> | [102]  |    3      | [pos: 1, pos: 4, pos: 9]        |    |
|  +-------------------+               +-------------------------------------------------------+    |
|                                                                                                   |
+===================================================================================================+
```

---

## 8. Panduan Implementasi Bertahap

Langkah-langkah berikut memandu pembangunan cluster lokal node-tunggal untuk keperluan analisis internal data structure menggunakan Docker container dengan konfigurasi production-like (resource constraints eksplisit).

### Langkah 1: Konfigurasi Virtual Memory OS Host (Linux)
Elasticsearch menggunakan system call `mmapfs` direktori Lucene secara default untuk menyimpan index files. OS harus mengizinkan memory mapping count yang memadai.

```bash
# Set nilai vm.max_map_count secara realtime
sudo sysctl -w vm.max_map_count=262144

# Persistensikan ke sysctl.conf agar bertahan setelah reboot
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Langkah 2: Deploy Elasticsearch Single-Node via Docker Compose
Buat file `docker-compose.yml` untuk mematikan security TLS lokal secara sementara khusus untuk pembedahan arsitektur modul dasar ini:

```yaml
services:
  es-node01:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    container_name: es-node01
    environment:
      - node.name=es-node01
      - cluster.name=es-core-cluster
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=false
      - xpack.security.http.ssl.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data

volumes:
  es_data:
    driver: local
```

Jalankan container:
```bash
docker compose up -d
```

### Langkah 3: Verifikasi Status Cluster
Pastikan status node aktif via standard terminal curl:

```bash
curl -X GET "http://localhost:9200/_cluster/health?pretty"
```

---

## 9. Kode Contoh Sederhana

Berikut adalah contoh pembuatan index dengan pengaturan alokasi shard eksplisit, indexing dokumen sederhana, serta query term matching menggunakan interface HTTP standard.

### 9.1 Definisi Index dan Shard Allocations
```bash
# Membuat Index 'telemetry-events' dengan 2 Primary Shards dan 1 Replica
curl -X PUT "http://localhost:9200/telemetry-events" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "number_of_shards": 2,
      "number_of_replicas": 0,
      "index.refresh_interval": "1s"
    },
    "mappings": {
      "properties": {
        "service_name": { "type": "keyword" },
        "log_level":    { "type": "keyword" },
        "message":      { "type": "text" },
        "latency_ms":   { "type": "float" },
        "timestamp":    { "type": "date" }
      }
    }
  }'
```

### 9.2 Ingest Dokumen Tunggal
```bash
curl -X POST "http://localhost:9200/telemetry-events/_doc/trace-001" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "payment-gateway",
    "log_level": "ERROR",
    "message": "Connection timeout while connecting to database cluster",
    "latency_ms": 5002.4,
    "timestamp": "2024-03-30T10:15:30Z"
  }'
```

### 9.3 Full-Text BM25 Search Query
```bash
# Mencari kata 'timeout database' dalam field text 'message'
curl -X POST "http://localhost:9200/telemetry-events/_search?pretty" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "match": {
        "message": {
          "query": "timeout database",
          "operator": "and"
        }
      }
    }
  }'
```

---

## 10. Kode Contoh Dunia Nyata

Skrip Python berikut menunjukkan cara berinteraksi dengan Elasticsearch menggunakan *official high-level client* (`elasticsearch-py`). Skrip ini mengimplementasikan batch bulk indexing, eksplorasi shard allocation, verifikasi segment commit, dan error handling tangguh.

```python
#!/usr/bin/env python3
"""
ES Core Architecture Demonstration: Index Lifecycle, Bulk Ingestion & Shard Inspection
Standard: GEMINI Technical Module
"""

import sys
import logging
from typing import Dict, Any, List
from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import ApiError, ConnectionError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("es-architect")

INDEX_NAME = "enterprise-audit-logs"

def get_es_client(host: str = "http://localhost:9200") -> Elasticsearch:
    """Menginisialisasi klien Elasticsearch dengan verifikasi koneksi."""
    client = Elasticsearch(
        hosts=[host],
        request_timeout=10,
        max_retries=3,
        retry_on_status=(502, 503, 504)
    )
    if not client.ping():
        logger.error("Koneksi ke Elasticsearch Cluster gagal.")
        sys.exit(1)
    logger.info(f"Terhubung ke klaster: {client.info()['cluster_name']}")
    return client

def create_configured_index(es: Elasticsearch, name: str) -> None:
    """Mendefinisikan skema index lengkap dengan pengaturan shard dan analyzer mapping."""
    if es.indices.exists(index=name):
        logger.warning(f"Index '{name}' sudah ada. Melakukan purging...")
        es.indices.delete(index=name)

    index_body: Dict[str, Any] = {
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 0,  # 0 karena berjalan pada single-node cluster
            "index.refresh_interval": "5s",  # Optimasi ingestion throughput
            "index.translog.durability": "async",  # Async flushing translog ke disk
            "index.translog.sync_interval": "5s"
        },
        "mappings": {
            "dynamic": "strict",  # Cegah mapping explosion
            "properties": {
                "actor_id": {"type": "keyword"},
                "action": {"type": "keyword"},
                "status": {"type": "keyword"},
                "description": {
                    "type": "text",
                    "analyzer": "standard"
                },
                "execution_time_ms": {"type": "integer"},
                "@timestamp": {"type": "date"}
            }
        }
    }

    try:
        response = es.indices.create(index=name, body=index_body)
        logger.info(f"Index {name} berhasil dibuat: ack={response['acknowledged']}")
    except ApiError as exc:
        logger.error(f"Gagal membuat index: {exc.message}")
        raise exc

def generate_bulk_payload(count: int) -> List[Dict[str, Any]]:
    """Membuat dummy structured records untuk simulasi bulk payload."""
    import datetime
    payloads = []
    actions = ["USER_LOGIN", "TRANSFER_FUNDS", "PASSWORD_RESET", "EXPORT_REPORT"]
    statuses = ["SUCCESS", "FAILED", "PENDING"]

    for i in range(1, count + 1):
        payloads.append({
            "_index": INDEX_NAME,
            "_id": f"log-{i:06d}",
            "_source": {
                "actor_id": f"user_{(i % 50) + 1}",
                "action": actions[i % len(actions)],
                "status": statuses[i % len(statuses)],
                "description": f"Audited system event execution sequence #{i} executed on core-service",
                "execution_time_ms": (i * 7) % 350,
                "@timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        })
    return payloads

def bulk_insert(es: Elasticsearch, records: List[Dict[str, Any]]) -> None:
    """Mengeksekusi Bulk API ingestion dengan handling kegagalan parsial."""
    logger.info(f"Memulai proses bulk ingestion sebanyak {len(records)} dokumen...")
    try:
        success, failed = helpers.bulk(
            es,
            records,
            chunk_size=500,
            stats_only=False,
            raise_on_error=False
        )
        logger.info(f"Ingestion Selesai. Berhasil: {len(success)}, Gagal: {len(failed)}")
        if failed:
            logger.error(f"Detail kegagalan pertama: {failed[0]}")
    except Exception as exc:
        logger.critical(f"Bulk ingestion crash: {str(exc)}")
        raise exc

def inspect_segments(es: Elasticsearch, index_name: str) -> None:
    """Inspeksi layout Lucene segment level rendah dari index."""
    logger.info(f"Melakukan inspeksi Lucene Segments untuk index: {index_name}")
    # Force refresh agar data di memory buffer ditulis ke segment OS cache
    es.indices.refresh(index=index_name)
    
    segments_data = es.indices.segments(index=index_name)
    shards = segments_data["indices"][index_name]["shards"]
    
    for shard_id, shard_list in shards.items():
        for shard_info in shard_list:
            routing_state = "PRIMARY" if shard_info["routing"]["primary"] else "REPLICA"
            num_segments = shard_info["num_search_segments"]
            logger.info(f"Shard [{shard_id}] [{routing_state}] -> Searchable Segments: {num_segments}")
            for seg_name, seg_details in shard_info["segments"].items():
                logger.info(
                    f"  |- Segment: {seg_name} | Docs: {seg_details['num_docs']} | "
                    f"Deleted Docs: {seg_details['deleted_docs']} | "
                    f"Size: {seg_details['size_in_bytes']} bytes | "
                    f"Committed: {seg_details['committed']}"
                )

if __name__ == "__main__":
    client = get_es_client()
    try:
        create_configured_index(client, INDEX_NAME)
        dataset = generate_bulk_payload(2500)
        bulk_insert(client, dataset)
        inspect_segments(client, INDEX_NAME)
    finally:
        client.close()
```

---

## 11. Verifikasi & Pengujian

Berikut adalah serangkaian CLI command untuk memvalidasi dan memverifikasi arsitektur cluster pasca eksekusi skrip di atas:

### 11.1 Verifikasi Shard Allocation dan State
Gunakan Cat API untuk melihat bagaimana shard terdistribusi ke node fisik:
```bash
curl -X GET "http://localhost:9200/_cat/shards/enterprise-audit-logs?v=true&h=index,shard,prirep,state,docs,store,node"
```
**Ekspektasi Output:**
```text
index                  shard prirep state   docs store node
enterprise-audit-logs  0     p      STARTED 1250 145kb es-node01
enterprise-audit-logs  1     p      STARTED 1250 145kb es-node01
```

### 11.2 Evaluasi Recovery & Translog Retention
Validasi translog operation count untuk memastikan bahwa dokumen telah ter-flush dengan benar:
```bash
curl -X GET "http://localhost:9200/enterprise-audit-logs/_stats/translog,segments?pretty"
```
Periksa parameter:
*   `translog.operations`: Angka transaksi yang belum di-commit secara permanen.
*   `segments.count`: Jumlah file fisik Lucene segment yang aktif pada shard.

### 11.3 Uji Eksekusi Query Profile (Analisis Alur Eksekusi Internal)
Jalankan search API dengan flag `"profile": true` untuk membedah breakdown waktu eksekusi internal Lucene (weight creation, collector overhead):
```bash
curl -X POST "http://localhost:9200/enterprise-audit-logs/_search?pretty" \
  -H "Content-Type: application/json" \
  -d '{
    "profile": true,
    "query": {
      "term": {
        "action": "TRANSFER_FUNDS"
      }
    }
  }'
```

---

## 12. Edge Cases, Mitigasi & Common Pitfalls

### 12.1 Dynamic Mapping Explosion
*   **Kasus**: Sistem mengizinkan ingestion dokumen dengan arbitrary/uncontrolled keys JSON (misal payload log mentah dari dynamic payload).
*   **Dampak Fatal**: Setiap root key baru menghasilkan modifikasi pada **Cluster State**. Cluster state harus disinkronisasi ke seluruh node di cluster melalui master node. Ukuran cluster state yang membengkak (puluhan megabyte) memicu latensi sinkronisasi, JVM Heap exhaustion pada Master Node, dan akhirnya cluster freeze.
*   **Mitigasi**:
    *   Setel `"dynamic": "strict"` atau `"dynamic": false` pada template root index.
    *   Jika dynamic field tidak terhindarkan, batasi kedalaman dan jumlah total fields menggunakan dynamic index settings:
        ```json
        {
          "index.mapping.total_fields.limit": 1000,
          "index.mapping.depth.limit": 10
        }
        ```

### 12.2 Split-Brain Syndrome (Pemisahan Klaster Paralel)
*   **Kasus**: Terjadi pemisahan jaringan (*network partition*) antar rack/datacenter. Node master-eligible di kedua sisi partisi mengangkat dirinya sendiri menjadi Master aktif karena kehilangan kontak dengan belahan node lainnya.
*   **Dampak Fatal**: Data divergen! Node A menulis data versi A, Node B menulis data versi B. Ketika partisi jaringan pulih, data crash dan rekonsiliasi mustahil dilakukan tanpa data loss.
*   **Mitigasi**: Sejak Elasticsearch versi 7.x+, sistem discovery diganti menggunakan Raft-like algorithm (`cluster.initial_master_nodes`). Sistem menghitung kuorum secara otomatis ($\lfloor N/2 \rfloor + 1$). Pastikan master-eligible nodes berjumlah **ganjil** (minimal 3 node) pada klaster multi-node production.

### 12.3 High Deleted Documents & Segment Fragmentation
*   **Kasus**: Pola penggunaan update data dengan throughput tinggi.
*   **Dampak Fatal**: Karena segment bersifat immutable, update berulang kali membuat segment membengkak oleh dokumen "deleted" (tanda nisan). Memori Page Cache dan disk penuh oleh dokumen yang sudah tidak valid.
*   **Mitigasi**: Jadwalkan proses pembersihan manual berkala di jam sepi via Force Merge API:
    ```bash
    curl -X POST "http://localhost:9200/my-index/_forcemerge?max_num_segments=1"
    ```
    *Peringatan*: Jangan jalankan Force Merge pada index yang masih menerima write traffic tinggi karena operasi ini memakan throughput IOPS disk secara ekstrem.

---

## 13. Trade-offs & Analisis Perbandingan

| Dimensi Arsitektural | Elasticsearch (Lucene) | RDBMS (PostgreSQL B-Tree) | Log-Optimized (ClickHouse) |
| :--- | :--- | :--- | :--- |
| **Model Indeks Utama** | Inverted Index, FST, BKD Trees | B+ Tree, Hash Index | Sparse Primary Index, Columnar Partitions |
| **Pencarian Teks Bebas** | Sangat Cepat ($O(1)$ Term Lookup + BM25 Scoring) | Lambat ($O(N)$ Sequential Scan jika pakai `LIKE %..%`) | Menengah (Menggunakan tokenBF_v1 string bloom filter) |
| **Write Throughput** | Menengah (Tinggi jika bulk, ada overhead Inverted Index) | Rendah-Menengah (Write-heavy dibatasi locks & WAL B-tree) | **Ekstrem Tinggi** (Append-only MergeTree engine) |
| **Latensi Update Record** | Mahal (Delete + Re-index Segment baru) | **Murah / Efisien** (In-place tuple update / MVCC) | Sangat Mahal (Mutasi via asynchronous batch rewrite) |
| **Konsistensi Data** | **Eventual Consistency** (Near Real-Time ~1-5 detik) | **Immediate Consistency** (Strict ACID) | Eventual Consistency |
| **Penggunaan Memori** | Tinggi (Heap untuk FST/Query cache + OS Page Cache) | Menengah (Buffer Pool teralokasi fix) | Terkontrol (Vectorized Execution chunk) |

---

## 14. Best Practices & Anti-Patterns

### Best Practices
1.  **Gunakan Bulk API Selalu**: Jangan pernah mengindeks dokumen satu per satu secara individual melalui perulangan HTTP request sederhana. Kumpulkan dalam satu batch 1.000–5.000 dokumen atau ukuran payload total sekitar 5MB–15MB.
2.  **Explicit Mappings Over Schemaless**: Selalu definisikan mapping tipe data secara eksplisit sebelum ingestion dimulai. Tentukan secara akurat kapan sebuah string harus berupa `keyword` (exact match, aggregations, filtering) dan kapan harus berupa `text` (analyzed, tokenized, scoring full-text).
3.  **Tuning Shard Size**: Pertahankan ukuran individual shard antara **10GB hingga 50GB**. Shard di bawah 1GB menyebabkan overhead metadata (shard explosion), sedangkan shard di atas 50GB mempersulit recovery node saat terjadi perpindahan data via network.

### Anti-Patterns
1.  **Over-sharding**: Membuat 50 index dan setiap index memiliki 5 primary shard pada cluster 2 node. Shard adalah entitas Lucene yang memakan resource file descriptors, memory overhead, dan thread context switching.
2.  **Menggunakan Elasticsearch Sebagai Primary ACID Database**: Mempercayakan transaksi keuangan atau single-source-of-truth inventory tanpa backup RDBMS relasional di belakangnya adalah kesalahan arsitektur fatal. Elasticsearch tidak mendukung ACID distributed transactions across documents.
3.  **Menetapkan JVM Heap Terlalu Besar (>31 GB)**: Mengalokasikan JVM Heap di atas 32GB akan mematikan fitur JVM *Compressed Ordinary Object Pointers (Compressed OOPs)*. Akibatnya, pointer melonjak dari 32-bit ke 64-bit, membuang gigabytes RAM secara cuma-cuma dan menurunkan efisiensi CPU cache.

---

## 15. Pertimbangan Skalabilitas & Produksi

### 15.1 Formula JVM Heap dan OS Memory Sizing
Aturan mutlak dalam sizing memori node Elasticsearch:
$$\text{JVM Heap} = \min\left(31\,\text{GB},\, 50\% \times \text{Total Node Physical RAM}\right)$$

Mengapa menyisakan 50% RAM untuk OS?
Lucene **tidak menggunakan JVM Heap** untuk menyimpan struktur data Inverted Index di disk. Lucene sepenuhnya bergantung pada **OS Page Cache** (native memory kernel). Jika JVM Heap diset 90% dari total RAM, Page Cache akan kelaparan, memicu *disk thrashing* dan penurunan performa pembacaan secara masif.

```
Total Server RAM: 64 GB
+------------------------------------+------------------------------------+
|       JVM Heap (Max 31 GB)         |        OS Page Cache (~33 GB)      |
|  - Indexing Buffer                 |  - Lucene Inverted Index Segments  |
|  - Aggregation Buckets / Breakers  |  - Doc Values (Columnar Analytics) |
|  - Cluster State & Thread Pools    |  - Fast Direct Disk File Caching   |
+------------------------------------+------------------------------------+
```

### 15.2 Konfigurasi Kernel Linux Tingkat Produksi
Tambahkan parameter ini pada environment production host Linux:
```ini
# /etc/security/limits.conf
elasticsearch soft nofile 65535
elasticsearch hard nofile 65535
elasticsearch soft memlock unlimited
elasticsearch hard memlock unlimited

# /etc/sysctl.conf
# Mematikan swap secara agresif agar JVM tidak pernah di-swap out ke disk (menyebabkan freeze stop-the-world)
vm.swappiness = 1
# Batas alokasi memory map untuk segment Lucene
vm.max_map_count = 262144
```

---

## 16. Aspek Keamanan & Kepatuhan

1.  **Enkripsi Dalam Transit & Saat Diam (In-transit & At-rest)**:
    *   Transport layer (inter-node communication port 9300) dan HTTP layer (client communication port 9200) **wajib** diamankan dengan TLS v1.3.
    *   Autentikasi mutual TLS (mTLS) antar node mencegah node asing tak terotorisasi bergabung ke dalam klaster dan mencuri Cluster State.
2.  **Role-Based Access Control (RBAC)**:
    *   Jangan berikan akses user aplikasi menggunakan level credential `elastic` (super-admin). Buat peran terspesialisasi yang membatasi hak akses pada scope index dan aksi tertentu:
        ```json
        POST /_security/role/log_writer_role
        {
          "indices": [
            {
              "names": [ "audit-logs-*" ],
              "privileges": [ "create_doc", "create_index", "read" ]
            }
          ]
        }
        ```
3.  **Data Sanitization & PII Masking**:
    *   Manfaatkan Elasticsearch Ingest Pipeline dengan modul processor `grok` atau `script` untuk melakukan hashing / masking terhadap sensitive data (Nomor Kartu Kredit, NIK, Password) sebelum dokumen dikonversi menjadi segment Lucene permanen.

---

## 17. Ringkasan & Peta Konsep

### Mental Model Sederhana
*   **Cluster** = Data Center / Perusahaan.
*   **Node** = Gedung Fisik / Mesin Server.
*   **Index** = Namespace / Katalog Logis.
*   **Shard** = Satu unit kerja utuh mesin **Apache Lucene**.
*   **Segment** = File individual pembentuk Shard, immutable, berisi Term Dictionary, Inverted Index, dan Doc Values.

```
CLUSTER
 └── NODE (Role: Master/Data)
      └── SHARD (Instance Apache Lucene)
           ├── IN-MEMORY BUFFER (Menampung penulisan dokumen sebelum refresh)
           ├── TRANSLOG (Menjamin write durability sebelum fsync flush)
           └── SEGMENTS (Immutable lucene data files)
                ├── Term Index (FST - di memory)
                ├── Term Dictionary (Term diurutkan)
                └── Postings List (DocID, Freq, Position)
```

### Aturan Emas Arsitek Elasticsearch
*Dokumen di-refresh untuk membuatnya Searchable. Dokumen di-flush untuk membuatnya Persistent.*

---

## 18. Latihan Mandiri & Soal Tantangan

### Kasus Mudah (Skor: 20)
1.  Jalankan perintah HTTP API untuk mengubah konfigurasi `refresh_interval` index `enterprise-audit-logs` secara runtime menjadi `30s`. Analisis mengapa pengaturan ini meningkatkan kecepatan penulisan dokumen berskala besar.
2.  Jelaskan perbedaan mendasar fungsi pencarian antara field yang memiliki tipe data `text` dan tipe data `keyword`.

### Kasus Menengah (Skor: 40)
1.  Anda memiliki klaster dengan 3 node fisik. Anda membuat index baru dengan setting:
    ```json
    {
      "settings": {
        "number_of_shards": 4,
        "number_of_replicas": 2
      }
    }
    ```
    *   Berapa total shard (primary + replica) yang dibuat pada cluster?
    *   Bagaimana distribusinya pada masing-masing node?
    *   Jika 1 node mati secara tiba-tiba, apakah klaster mengalami data loss? Buktikan dengan kalkulasi ketersediaan shard.

### Kasus Kompleks (Skor: 40)
1.  **Root-Cause Analysis Task**: 
    Sebuah aplikasi e-commerce melaporkan bahwa lonjakan traffic penulisan log transaksi menyebabkan latensi pencarian katalog produk meningkat tajam dari 15ms menjadi 4200ms. SRE memeriksa metrik server dan menemukan bahwa:
    *   JVM Heap Node Data stabil pada kisaran 60% (tidak OutOfMemory).
    *   CPU Usage mencapai 98%.
    *   I/O Disk Utilization (iostat) mencapai 100% saturation.
    
    *Tugas Arsitek*: Berdasarkan alur **Write Path** (Memory Buffer, Translog, Refresh, Flush, dan Segment Merge) yang telah dipelajari, identifikasi 3 akar masalah yang memicu saturasi disk I/O dan susun proposal perubahan konfigurasi index untuk memitigasi bottleneck tersebut tanpa menambah node hardware baru.

---

## 19. Glosarium Istilah Teknis

1.  **Inverted Index**: Struktur data yang memetakan setiap kata unik ke daftar dokumen dan posisi di mana kata tersebut ditemukan.
2.  **Lucene Segment**: File internal Lucene yang berisi struktur indeks terbalik; bersifat *write-once, read-many* (immutable).
3.  **Translog (Transaction Log)**: Write-ahead log penyimpanan dokumen di level disk untuk menjamin durabilitas data sebelum proses `fsync` segment terjadi.
4.  **Refresh**: Operasi memindahkan dokumen dari in-memory indexing buffer ke OS page cache sebagai segment baru, membuat data siap dicari.
5.  **Flush**: Operasi melakukan `fsync` seluruh segment di OS page cache ke media penyimpanan disk fisik dan membersihkan translog.
6.  **Segment Merge**: Proses latar belakang (background thread) yang menggabungkan beberapa segment kecil menjadi satu segment besar dan membersihkan dokumen yang ditandai terhapus (`.del`).
7.  **Coordinating Node**: Node yang menerima HTTP request dari client, memecahnya ke shard-shard terkait, dan mengagregasi respons sebelum dikirim balik ke client.
8.  **Doc Values**: Struktur data columnar di disk yang dibangun saat indexing untuk mempercepat operasi aggregasi, sorting, dan scripting.
9.  **FST (Finite State Transducer)**: Representasi graf terkompresi dari term dictionary yang dimuat ke memori untuk navigasi term yang cepat.
10. **Cluster State**: Metadata global yang mencakup topologi node, pemetaan skema index, dan penempatan alokasi shard di seluruh cluster.

---

## 20. Referensi & Bacaan Lanjutan

1.  **Elasticsearch Reference Documentation**: *Cluster Architecture, Index Lifecycle, and Shard Allocation Management*. Official Elastic Guides (v8.x).
2.  **Apache Lucene Architecture Docs**: *Lucene's Inverted Index Geometry and Directory Implementations* (`org.apache.lucene.index`).
3.  **Brattevåg, K.** (2018). *Designing Data-Intensive Applications: The Principles Behind Distributed Search Engines*. O'Reilly Media.
4.  **Kuć, R., & Rogoziński, M.** (2016). *Mastering Elasticsearch - Second Edition: Deep-dive into internals of Lucene and Elasticsearch infrastructure*. Packt Publishing.
5.  **RFC 7230 / JSON Specifications**: Standar representasi data dan transfer layer interaksi REST API.