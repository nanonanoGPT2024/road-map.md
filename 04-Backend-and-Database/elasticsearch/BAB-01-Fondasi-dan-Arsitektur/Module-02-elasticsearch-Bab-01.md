# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Principal/Lead Engineer diharapkan mampu:

1. **Menganalisis Anatomi Internal Apache Lucene**: Menguraikan struktur fisik *segment*, *inverted index*, *Finite State Transducer* (FST), *Posting List* (dengan algoritma kompresi PForDelta/Roaring Bitmaps), serta mekanisme *Doc Values* berbasis kolom.
2. **Merekayasa Siklus Hidup Transaksi Data (Write & Read Path)**: Mengonfigurasi dan memvalidasi alur *indexing* (Memory Buffer, Translog, Refresh, Flush, dan Segment Merging) serta alur pencarian dua tahap (*Query-then-Fetch*).
3. **Mengoptimasi Konfigurasi Sistem Operasi & JVM Runtime**: Menetapkan parameter kernel Linux (`vm.max_map_count`, swap, ulimit) dan mengalokasikan JVM heap secara presisi dengan ambang batas *Compressed Ordinary Object Pointers* (Compressed OOPs).
4. **Mendesain Arsitektur Data Berjenjang (*Data Tiers*) & ILM**: Membangun topologi Hot-Warm-Cold-Frozen menggunakan *Index Lifecycle Management* (ILM) terotomatisasi untuk klaster berskala *terabyte-ke-petabyte*.
5. **Menyelidiki dan Memulihkan Kerusakan Klaster (*Diagnostic Troubleshooting*)**: Mengidentifikasi akar masalah dari *CircuitBreakerException*, *unassigned shards*, *split-brain scenario*, serta *hotspotting* menggunakan API diagnostik tingkat rendah.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:
* Fondasi arsitektur dasar Elasticsearch: Peran Node, Shard Primer, Shard Replika, dan konsep *Clustering* (Modul 01).
* Pemahaman fundamental sistem operasi POSIX: *Virtual Memory*, *Page Cache*, *File Descriptors*, *Kernel System Calls* (`fsync`, `mmap`).
* Pemahaman dasar arsitektur JVM: *Garbage Collection mechanics* (G1GC), alokasi Heap vs Off-Heap memory.
* Penguasaan RESTful API dan sintaks manipulasi data JSON via cURL atau HTTP clients.

---

## 3. Concept & Internal Architecture

Elasticsearch bukan sekadar sistem penyimpanan JSON terdistribusi; melainkan sebuah *abstraction and orchestration layer* di atas pustaka *search engine* Apache Lucene.

```
+-----------------------------------------------------------------------+
| Elasticsearch Coordination & Routing Engine                           |
+-----------------------------------------------------------------------+
  |                                                  |
  v                                                  v
+-----------------------------+                    +--------------------+
| Lucene Index (Shard Primer) |                    | Lucene Index (Rep) |
+-----------------------------+                    +--------------------+
  |--> Segment 1 (Immutable)                          |--> Segment 1
  |--> Segment 2 (Immutable)                          |--> Segment 2
  +--> In-Memory Index Buffer                         +--> ...
```

### 3.1. Anatomi Fisik Lucene Segment

Sebuah Shard pada Elasticsearch adalah sebuah instansi index Lucene yang berdiri sendiri. Index Lucene terbagi menjadi unit-unit penyimpanan yang lebih kecil dan bersifat *immutable* (tidak dapat diubah) bernama **Segments**. Setiap segment menyimpan data dalam beberapa struktur terpisah:

```
Segment Filesystem Layout
├── Inverted Index
│   ├── .tim (Term Dictionary - FST Mapping)
│   ├── .tip (Term Index - Trie-based prefix tree di RAM)
│   └── .doc / .pos / .pay (Posting Lists, Term Frequencies, Positions, Offsets)
├── Columnar Store
│   ├── .dvd (Doc Values Data - Kolom numerik, keyword, date)
│   └── .dvm (Doc Values Metadata)
├── Stored Fields & Source
│   ├── .fdt (Field Data - Menyimpan field raw _source)
│   └── .fdx (Field Index - Pointer offset blok fdt)
└── Point Values (BKD Trees)
    ├── .kdd / .kdi (Struktur data multi-dimensi numerik, geo & IP)
```

1. **Inverted Index Engine**:
   * **Term Index (`.tip`)**: Struktur data FST (*Finite State Transducer*) yang berada di dalam memory (OS Page Cache/Heap). Berfungsi sebagai index pencarian cepat untuk melompat langsung ke blok target di dalam *Term Dictionary*.
   * **Term Dictionary (`.tim`)**: Berisi daftar kata yang telah diurutkan secara leksikografis beserta statistik frekuensi dokumen (*Document Frequency*).
   * **Posting List (`.doc`)**: Senarai ID dokumen (`docID`) yang memuat *term* tersebut. Menggunakan algoritma kompresi SIMD-PFor (Packed Frame of Reference) atau Roaring Bitmaps untuk meminimalkan jejak I/O.
2. **Doc Values (`.dvd` & `.dvm`)**:
   * Struktur data berorientasi kolom (*columnar storage*) yang dibangun saat proses *indexing*.
   * Berada di luar heap (diserahkan sepenuhnya ke *OS Page Cache* melalui `mmap`).
   * Dirancang khusus untuk operasi agregasi (`aggregations`), pengurutan (`sort`), dan pemrosesan *painless script*. Doc Values menghindarkan engine dari operasi *un-inverting the inverted index* yang membutuhkan memori sangat besar.
3. **Stored Fields (`.fdt` dan `.fdx`)**:
   * Menyimpan dokumen JSON asli (blok metadata `_source`). Data dikompresi menggunakan LZ4 secara *default* atau DEFLATE (opsi `best_compression`).

---

## 4. Why & What

### Mengapa Lucene Menggunakan Segment yang Bersifat Immutable?

* **Peniadaan Lock Konkurensi**: Karena segment tidak pernah dimodifikasi di tempat (*no in-place updates*), operasi pembacaan tidak membutuhkan mekanisme *locking* primitif (`read/write locks`). Hal ini memungkinkan pemrosesan query konkuren berjalan dengan skalabilitas tinggi.
* **Efisiensi OS Page Cache**: Sekali OS memuat segment file ke dalam *Page Cache*, file tersebut akan tetap bersih (*clean pages*), tidak pernah berstatus *dirty pages*, sehingga tidak perlu ditulis ulang ke disk kecuali saat sinkronisasi translog.
* **Kompresi Data Ekstrem**: Data yang statis memungkinkan penerapan skema kompresi beruntun (*block-level compression*) seperti Bit-packing dan Elias-Fano, yang mustahil diterapkan secara efisien pada struktur data dinamis yang sering mengalami mutasi.

### Apa Konsekuensi Arsitekturnya?
* **Mekanisme Delete/Update**: Proses update dilakukan melalui pendekatan *Soft Delete*. Operasi mutasi menulis dokumen baru ke segment baru, sementara dokumen lama ditandai sebagai *deleted* di dalam berkas bitmap berukuran kecil (`.del`).
* **Segment Merging**: Menumpuknya berkas segment akibat mutasi data akan menurunkan performa pencarian. Engine menjalankan proses latar belakang (*TieredMergePolicy*) untuk menggabungkan beberapa segment kecil menjadi segment besar, sembari membersihkan dokumen yang berada dalam status *deleted*.

---

## 5. How: Transaction Workflows

### 5.1. Alur Penulisan Dokumen (Write Path)

```
[Client]
   │
   ▼
[Coordinating Node] ──────── (Hash routing: shard = hash(_id) % primary_shards)
   │
   ▼
[Primary Shard]
   ├─► 1. Tulis ke In-Memory Indexing Buffer (Tidak bisa dicari)
   ├─► 2. Tulis ke Translog di Disk (fsync default setiap 5 detik / batasan request)
   │
   ├── (Kirim operasi paralel via IPC)
   ▼
[Replica Shards] ───► Tulis ke Index Buffer & Translog masing-masing
   │
   ▼ (Ack diterima dari replica sesuai quorum 'wait_for_active_shards')
[Coordinating Node kirim respon sukses ke Client]

(Siklus Latar Belakang)
───────────────────────────────────────────────────────────────────────────
Index Buffer ───[REFRESH (1s)]───► OS Page Cache (Segment Baru, Read-Enabled)
Translog ───────[FLUSH (30m)]────► FSYNC ke Disk & Segment Permanen Terbentuk
```

1. **Routing**: Klien mengirim payload dokumen ke *Coordinating Node*. Node ini menghitung shard target:
   $$\text{Shard ID} = |\text{MurmurHash3}(\text{routing})| \pmod{\text{Total Primary Shards}}$$
2. **Buffer Ingestion**: Shard primer mengeksekusi pipeline *ingest* (jika didefinisikan), memvalidasi pemetaan schema (*mapping*), dan menulis data secara simultan ke:
   * **In-memory Index Buffer**: Tempat dokumen di-tokenisasi dan diubah ke struktur segment Lucene. Data di sini **belum** dapat dicari (*unsearchable*).
   * **Transaction Log (Translog)**: Log append-only persisten di disk untuk menjamin durabilitas ACID (komponen atomisitas & durabilitas crash recovery).
3. **Replication**: Setelah dieksekusi di Shard Primer, instruksi penulisan dikirim secara paralel ke semua Shard Replika yang aktif. Respons `HTTP 201 Created` dikirim ke klien hanya setelah ambang batas replikasi terpenuhi (`wait_for_active_shards`).
4. **The Refresh Operation**:
   * Dieksekusi secara berkala (standar: setiap `1s`, atau melalui API POST `/_refresh`).
   * Konten dalam *Index Buffer* ditulis ke segment baru di dalam **OS Page Cache** (struktur segment file dibentuk di RAM, belum di-`fsync` ke disk fisik).
   * Titik pencarian (*Searcher point*) dibuka kembali. Dokumen kini resmi berstatus **Near-Real-Time (NRT)** dan dapat dicari.
   * *Index Buffer* dikosongkan.
5. **The Flush Operation**:
   * Terpicu ketika Translog mencapai batas ukuran (standar `512MB`) atau batas waktu (standar `30 menit`).
   * Menulis *commit point* permanen ke disk fisik (`fsync` seluruh data di *OS Page Cache*).
   * Berkas segment Lucene dijamin persisten di media penyimpanan.
   * Translog lama dihapus, dan Translog baru yang kosong diinisiasi.

---

### 5.2. Alur Pencarian Dua Tahap (Query-then-Fetch)

Elasticsearch memecah eksekusi distributed search menjadi dua fase untuk menekan konsumsi bandwidth jaringan:

```
[Coordinating Node]               [Data Node (Shard 1)]     [Data Node (Shard 2)]
        │                                   │                         │
        │── Phase 1: Query (Scatter) ──────►│                         │
        │───────────────────────────────────┼────────────────────────►│
        │                                   │                         │
        │   Eksekusi Match, Scoring,        │                         │
        │   Ambil PriorityQueue (Top N)     │                         │
        │                                   │                         │
        │◄── Kirim [DocID + Sort Value] ────│                         │
        │◄── Kirim [DocID + Sort Value] ────┼─────────────────────────│
        │                                   │                         │
   Merge Sorting & Build Global Top N       │                         │
        │                                   │                         │
        │── Phase 2: Fetch (Docs Details) ─►│ (Hanya Doc ID terpilih) │
        │───────────────────────────────────┼────────────────────────►│
        │                                   │                         │
        │◄── Kirim _source lengkap ─────────│                         │
        │◄── Kirim _source lengkap ─────────┼─────────────────────────│
        │                                   │                         │
  Rakit Hasil Akhir & Berikan ke Client     │                         │
```

1. **Fase Query (Scatter)**:
   * Coordinating node mendistribusikan query ke seluruh shard yang relevan (bisa shard primer atau replika).
   * Tiap shard mengeksekusi pencarian lokal melalui Inverted Index, menghitung relevansi score (BM25), dan membangun antrean prioritas berukuran $From + Size$ yang hanya berisi pasang metadata: `DocID` dan `Sort Value`.
   * Tiap shard mengembalikan metadata tersebut ke Coordinating Node. Data `_source` belum diekstrak pada tahap ini.
2. **Fase Fetch (Gather)**:
   * Coordinating Node menggabungkan (*merge-sort*) hasil dari setiap shard untuk menentukan dokumen yang benar-benar masuk ke peringkat Top-$N$ global.
   * Coordinating Node mengirimkan permintaan langsung (*Doc-ID specific GET*) ke shard pemilik dokumen terpilih untuk menarik payload penuh `_source` beserta data *highlighting*.
   * Menggabungkan payload tersebut menjadi response Elasticsearch dan mengirimkannya ke klien.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem: Percetakan Perpustakaan Modern

Bayangkan sebuah sistem dokumentasi arsip raksasa:
* **Index Buffer**: Meja kerja kurator. Arsip baru ditata di atas meja, belum dijilid. Pengunjung perpustakaan belum bisa membaca dokumen ini.
* **Segment**: Bundel buku cetak berhalaman paten (bersifat permanen, tidak bisa disisipkan halaman baru).
* **Refresh**: Kurator memfotokopi draf di meja kerja dan menaruhnya di ruang baca sementara (*Page Cache*). Pengunjung sudah bisa membaca tulisan tersebut (*searchable*), meski buku resminya belum masuk brankas anti-kebakaran.
* **Translog**: Kamera CCTV resolusi tinggi yang merekam setiap coretan kurator di meja kerja secara real-time. Jika gedung terbakar sebelum berkas dicetak, catatan di meja direkonstruksi dari rekaman ini.
* **Flush**: Buku-buku sementara secara fisik dipindahkan ke dalam brankas baja tahan api (*fsync to physical disk*), lalu rekaman CCTV lama dibersihkan.
* **Segment Merge**: Ruang perpustakaan penuh dengan ratusan buklet tipis (*small segments*). Di malam hari, kurator menjilid 10 buklet kecil menjadi 1 ensiklopedia tebal (*merged segment*), sambil merobek halaman-halaman usang yang sudah dicap batil (*deleted tombstones*).

---

## 7. Implementation Examples

### 7.1. Anti-Pattern: Pemetaan Standar (Dynamic Mapping)
Konfigurasi ceroboh membiarkan Elasticsearch membuat tipe data secara otomatis:

```json
// Buruk: Mengakibatkan fenomena Mapping Explosion
POST /invoices_bad/_doc/1
{
  "invoice_id": "INV-2023-001",
  "total_amount": 1500000.50,
  "transaction_date": "2023-10-27T10:00:00Z",
  "notes": "Pembayaran lunas via transfer",
  "metadata": {
    "ip": "192.168.1.1",
    "retries": 2
  }
}
```
*Dampak buruk:* Field `notes` dan `invoice_id` akan diindex ganda sebagai `text` (membuat Inverted Index) DAN `keyword` (membuat Doc Values). Nilai `total_amount` menjadi `float` standar yang boros alokasi, memboroskan ruang disk hingga 60%.

### 7.2. Production Pattern: Template Enterprise & Strict Mapping

Konfigurasi kelas produksi dengan optimasi tipe data, pemadaman *doc_values* yang tidak diperlukan, serta parameter engine tingkat lanjut.

```json
PUT /_index_template/ecommerce_invoices_v1
{
  "index_patterns": ["invoices-*"],
  "template": {
    "settings": {
      "index.number_of_shards": 3,
      "index.number_of_replicas": 1,
      "index.refresh_interval": "30s",
      "index.codec": "best_compression",
      "index.translog.durability": "async",
      "index.translog.sync_interval": "10s",
      "index.translog.flush_threshold_size": "1gb",
      "index.routing.allocation.total_shards_per_node": 2
    },
    "mappings": {
      "dynamic": "strict",
      "_source": {
        "enabled": true
      },
      "properties": {
        "invoice_id": {
          "type": "keyword",
          "doc_values": true,
          "ignore_above": 64
        },
        "customer_id": {
          "type": "keyword",
          "doc_values": true
        },
        "total_amount": {
          "type": "scaled_float",
          "scaling_factor": 100
        },
        "currency": {
          "type": "keyword",
          "doc_values": false
        },
        "description": {
          "type": "text",
          "analyzer": "standard",
          "norms": false,
          "index_options": "docs"
        },
        "created_at": {
          "type": "date",
          "format": "strict_date_optional_time||epoch_millis"
        },
        "ip_address": {
          "type": "ip"
        },
        "status": {
          "type": "keyword"
        }
      }
    }
  },
  "priority": 500
}
```

**Analisis Rekayasa:**
* `dynamic: strict`: Menolak dokumen baru yang mencoba menyuntikkan field liar tak terdefinisi. Mencegah *Cluster State Explosion*.
* `index.refresh_interval: 30s`: Menunda segment creation, menaikkan *write throughput* hingga 400% dibanding nilai standar (`1s`).
* `index.translog.durability: async`: Translog di-`fsync` tiap interval `10s`, menukar jaminan durabilitas mikro demi performa I/O masif (diterima pada arsitektur log streaming atau data transaksi yang memiliki buffer Kafka).
* `scaled_float`: Menyimpan nilai desimal mata uang sebagai integer 64-bit yang dikalikan 100, menekan konsumsi disk dibanding tipe `double`.
* `norms: false` & `index_options: docs`: Menghilangkan kalkulasi scoring kompleks (*field-length norm* dan frekuensi kata) pada field `description` yang hanya membutuhkan verifikasi eksistensi term teks.

---

## 8. Real World Case Study: Financial Transaction Platform

### Skenario Masalah
Sebuah platform *Payment Gateway* memproses 80 juta record mutasi ledger per hari (sekitar 1.000 - 3.500 write ops/sec konsisten). 
**Kendala Klaster Lama:**
1. CPU Data Node menyentuh angka 95% secara reguler.
2. Sering terjadi `EsRejectedExecutionException` (antrean penulisan threadpool penuh).
3. Query analitik fraud audit yang menyaring data 3 bulan terakhir menghasilkan latency p99 > 45 detik, menyebabkan timeout internal.
4. Storage cluster membengkak hingga 85TB padahal volume JSON mentah berkisar 25TB.

### Solusi Arsitektural yang Diterapkan
1. **Penerapan Hot-Warm-Cold Tiering Berbasis Node Roles**:
   * **Hot Nodes** (6 node): CPU tinggi (AMD EPYC 32 core), NVMe SSD, RAM 64GB. Mengelola ingest data hari berjalan sampai 7 hari terakhir.
   * **Warm Nodes** (4 node): CPU moderat, Enterprise SAS SSD, RAM 64GB. Menangani data 8-30 hari lalu.
   * **Cold Nodes** (4 node): CPU rendah, High-density HDD, RAM 32GB. Menangani data 31-90 hari lalu. Menggunakan *searchable snapshots* yang terhubung ke Object Storage (S3/MinIO).
2. **Definisi Policy ILM (Index Lifecycle Management)**:

```json
PUT /_ilm/policy/financial_ledger_policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_primary_shard_size": "45gb",
            "max_age": "1d"
          },
          "set_priority": {
            "priority": 100
          }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "forcemerge": {
            "max_num_segments": 1
          },
          "allocate": {
            "number_of_replicas": 1,
            "require": {
              "data": "warm"
            }
          },
          "set_priority": {
            "priority": 50
          }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "allocate": {
            "number_of_replicas": 0,
            "require": {
              "data": "cold"
            }
          },
          "set_priority": {
            "priority": 0
          }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

3. **Optimasi Segment Merge**:
   Pada fase Warm, pipeline mengeksekusi `forcemerge` menjadi `1` segment tunggal per shard. Operasi ini mengompilasi posting list, membersihkan *soft-deleted data* dari storage, dan mengoptimalkan struktur *doc_values*.

### Hasil Konkret (Metrik Produksi)
* Ingest throughput meningkat dari ~2.500 docs/sec menjadi ~11.000 docs/sec per node.
* Ukuran storage turun dari 85TB menjadi 31TB (penghematan efisiensi disk sebesar 63.5%) berkat codec `best_compression` dan `forcemerge`.
* Audit Query p99 terpangkas drastis dari 45 detik ke 1.8 detik karena pencarian tidak lagi memindai puluhan segment kecil yang terfragmentasi.

---

## 9. Trade-offs Architecture Matrix

| Parameter / Fitur | Keuntungan | Kerugian Teknis (*Trade-off*) | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- |
| **Refresh Interval: 1s** | Data mendekati *real-time* (Near-Real-Time SLA ketat). | Segment creation sangat tinggi; merge overhead tinggi; throughput penulisan drop drastis. | Searching dashboard e-commerce, real-time alert system. |
| **Refresh Interval: 30s-60s** | Peningkatan write-throughput hingga 3-5x lipat; jejak I/O disk minim. | Data yang baru masuk baru bisa dicari setelah jeda interval konfigurasi. | Logging tersentralisasi, ingest metrik sensor, data ledger. |
| **Shard Size: 10GB** | Relokasi shard dan *rebalancing* kilat antar node; alokasi memori pulih cepat. | Risiko *Over-sharding*; memboroskan JVM heap (overhead per-shard metadata pada memory master node). | Data ingest bervolume rendah; kluster multi-tenant terisolasi. |
| **Shard Size: 45GB - 50GB** | Efisiensi memori kluster tinggi; konsolidasi inverted index maksimal. | Waktu pemulihan (recovery time) dan relokasi shard عبر jala-jala jaringan membutuhkan waktu lama jika node tumbang. | Enterprise Log analytics, Time-series metric store, Big data warehouse. |
| **Translog: request (`fsync`)** | Jaminan durabilitas mutlak (Nol data loss saat OS crash). | Menghantam batas IOPS storage; latensi penulisan klien meningkat secara signifikan. | Transaksi perbankan, mutasi saldo dompet digital. |
| **Translog: async** | Write latency sangat rendah (I/O non-blocking). | Potensi kehilangan data (maksimal rentang `sync_interval`) jika OS node mengalami *power loss*. | Observability platform, distributed tracing, clickstream metrics. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal Alokasi JVM Heap: Fenomena 32GB

* **Kesalahan**: Mengalokasikan memory heap sebesar-besarnya (misal: 48GB dari 64GB RAM fisik) dengan asumsi Elasticsearch akan berjalan lebih cepat.
* **Mekanisme Kegagalan**: Arsitektur JVM menggunakan *Ordinary Object Pointers* (OOPs). Jika heap dialokasikan tepat di bawah ambang batas (sekitar ~31GB - 31.5GB tergantung CPU architecture), JVM menggunakan **Compressed OOPs** (pointer 32-bit untuk mereferensikan memori hingga 32GB). Begitu heap menembus ambang ini (misal 32GB atau 33GB), pointer dipaksa menjadi pointer murni 64-bit.
* **Dampak**: 
  1. Pointer 64-bit memakan ruang memori 2x lipat lebih boros, sehingga heap 33GB menyimpan data efektif lebih sedikit dibanding heap 31GB.
  2. Beban kerja *Garbage Collector* meningkat pesat, memicu *Long Stop-The-World (STW) Pauses*.
  3. Mengurangi sisa RAM fisik yang seharusnya dialokasikan penuh untuk **OS Page Cache** (tempat Lucene menyimpan segment files dan Doc Values).
* **Solusi**: Alokasikan selalu maksimal `50%` dari RAM fisik host, dan pastikan nilainya **di bawah 31GB** (biasanya direkomendasikan `30GB` atau `31800MB`).

Verifikasi di terminal node:
```bash
java -XX:+PrintFlagsFinal -version | grep UseCompressedOops
# Wajib menghasilkan: bool UseCompressedOops = true
```

### 10.2. Root Cause Analysis: Unassigned Shards

Jika klaster berubah status menjadi `RED` atau `YELLOW`, segera isolasi shard yang gagal dialokasikan:

```bash
# 1. Periksa alasan detail penolakan shard oleh allocation decider
GET /_cluster/allocation/explain
{
  "index": "invoices-2023.10.27",
  "shard": 0,
  "primary": true
}
```

**Output Diagnosis Umum:**
* `ALLOCATION_FAILED`: Shard gagal dimuat akibat berkas Lucene *corrupted*.
* `DISKWATERMARK_HIGH`: Kapasitas disk menembus ambang batas (default: 85% untuk low, 90% untuk high, 95% untuk flood-stage).
* `SAME_HOST_RULE`: Tidak bisa menempatkan shard primer dan replika pada hardware fisik yang sama.

**Langkah Pemulihan Disk Watermark:**
```bash
# Buka proteksi index read-only darurat akibat flood-stage
PUT /invoices-*/_settings
{
  "index.blocks.read_only_allow_delete": null
}

# Modifikasi ambang batas disk secara runtime (solusi sementara)
PUT /_cluster/settings
{
  "persistent": {
    "cluster.routing.allocation.disk.watermark.low": "88%",
    "cluster.routing.allocation.disk.watermark.high": "93%",
    "cluster.routing.allocation.disk.watermark.flood_stage": "96%"
  }
}
```

### 10.3. CircuitBreakerException (Parent / Data Circuit Breaker)
* **Penyebab**: Terjadi saat user mengeksekusi aggregasi masif pada high-cardinality data menggunakan script `Painless` atau mencoba agregasi pada field `text` tanpa sengaja (memicu pemuatan *Fielddata* ke dalam JVM Heap).
* **Solusi Perbaikan**:
  * Hindari agregasi field `text`. Gunakan tipe `keyword` murni yang memanfaatkan *Doc Values* (off-heap).
  * Batasi batas memori pemutus arus (*circuit breaker*) agar node tidak mati akibat `OutOfMemoryError` (OOM):
```json
PUT /_cluster/settings
{
  "persistent": {
    "indices.breaker.total.use_real_memory": true,
    "indices.breaker.total.limit": "75%",
    "indices.breaker.fielddata.limit": "20%"
  }
}
```

---

## 11. Best Practices & Production Checklist

### Checklist Konfigurasi Host Operating System (Linux)

- [ ] **Swap Memory Dimatikan Mutlak**: Swap menyebabkan operasi paging internal Lucene terhenti, merusak mekanisme NRT cluster.
  ```bash
  sudo swapoff -a
  # Edit /etc/fstab dan remark semua entri swap secara permanen
  ```
- [ ] **Tingkatkan Memory Mapping (`vm.max_map_count`)**: Lucene menggunakan `mmapfs` secara ekstensif untuk memetakan index segment ke alamat virtual process.
  ```bash
  echo "vm.max_map_count=262144" >> /etc/sysctl.conf
  sudo sysctl -p
  ```
- [ ] **Konfigurasi Resource Limits (`limits.conf`)**:
  ```text
  elasticsearch soft nofile 65535
  elasticsearch hard nofile 65535
  elasticsearch soft memlock unlimited
  elasticsearch hard memlock unlimited
  ```
- [ ] **Aktifkan Bootstrap Memory Lock**: Mencegah kernel memindahkan memory Elasticsearch ke swap.
  Edit `elasticsearch.yml`:
  ```yaml
  bootstrap.memory_lock: true
  ```

### Checklist Elasticsearch Cluster Topology

- [ ] Pisahkan peran node secara dedicated: **Dedicated Master Nodes** (minimal 3 node independen tanpa data) dan **Dedicated Data Nodes**.
- [ ] Nonaktifkan flag ingest dan koordinasi pada Data Node performa tinggi jika throughput ingest sangat ekstrem.
- [ ] Tetapkan quorum master election secara modern (Elasticsearch 7.x+):
  ```yaml
  cluster.initial_master_nodes: ["master-node-01", "master-node-02", "master-node-03"]
  ```

---

## 12. Hands-on Practice

Buat direktori kerja lokal: `hands-on/m02/`

### 12.1. File `docker-compose.yml`
Menjalankan simulasi cluster multi-node (Dedicated Master + Dedicated Hot Node + Dedicated Warm Node) lengkap dengan kontrol kernel dan limit resource:

```yaml
version: '3.8'

services:
  es-master:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: es-master
    environment:
      - node.name=es-master
      - cluster.name=enterprise-cluster
      - cluster.initial_master_nodes=es-master
      - discovery.seed_hosts=es-hot,es-warm
      - node.roles=master
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - xpack.security.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65535
        hard: 65535
    ports:
      - "9200:9200"
    networks:
      - es-net

  es-hot:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: es-hot
    environment:
      - node.name=es-hot
      - cluster.name=enterprise-cluster
      - discovery.seed_hosts=es-master
      - node.roles=data_hot,data_content,ingest
      - node.attr.data=hot
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65535
        hard: 65535
    networks:
      - es-net

  es-warm:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: es-warm
    environment:
      - node.name=es-warm
      - cluster.name=enterprise-cluster
      - discovery.seed_hosts=es-master
      - node.roles=data_warm
      - node.attr.data=warm
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65535
        hard: 65535
    networks:
      - es-net

networks:
  es-net:
    driver: bridge
```

### 12.2. Eksekusi Skrip Setup & Migrasi Tingkat Lanjut (`setup.sh`)

```bash
#!/usr/bin/env bash
set -e

echo "Menunggu Cluster Ready..."
until curl -s http://localhost:9200/_cat/health?h=status | grep -qE "green|yellow"; do
  sleep 2
done

echo "Cluster online. Mendaftarkan ILM Policy..."
curl -X PUT "http://localhost:9200/_ilm/policy/hot_warm_demo_policy" -H 'Content-Type: application/json' -d'
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_docs": 5
          }
        }
      },
      "warm": {
        "min_age": "10s",
        "actions": {
          "allocate": {
            "require": {
              "data": "warm"
            }
          },
          "forcemerge": {
            "max_num_segments": 1
          }
        }
      }
    }
  }
}'

echo -e "\nMendaftarkan Index Template..."
curl -X PUT "http://localhost:9200/_index_template/audit_template" -H 'Content-Type: application/json' -d'
{
  "index_patterns": ["audit-logs-*"],
  "template": {
    "settings": {
      "index.lifecycle.name": "hot_warm_demo_policy",
      "index.lifecycle.rollover_alias": "audit-logs",
      "index.routing.allocation.require.data": "hot",
      "index.number_of_shards": 1,
      "index.number_of_replicas": 0
    },
    "mappings": {
      "properties": {
        "event_name": { "type": "keyword" },
        "timestamp": { "type": "date" }
      }
    }
  }
}'

echo -e "\nMembentuk Index Pertama via Bootstrap..."
curl -X PUT "http://localhost:9200/audit-logs-000001" -H 'Content-Type: application/json' -d'
{
  "aliases": {
    "audit-logs": {
      "is_write_index": true
    }
  }
}'

echo -e "\nInjecting 6 Dokumen untuk Trigger Rollover..."
for i in {1..6}; do
  curl -s -X POST "http://localhost:9200/audit-logs/_doc" -H 'Content-Type: application/json' -d"
  {
    \"event_name\": \"USER_LOGIN_$i\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"
  }"
done

echo -e "\nTrigger ILM Execution Engine poll secara manual..."
curl -X POST "http://localhost:9200/_ilm/start"

echo -e "\nSelesai! Periksa status shards:"
curl -X GET "http://localhost:9200/_cat/shards/audit-logs*?v&h=index,shard,prirep,state,node"
```

---

## 13. Exercises

### Level Easy
1. Ubah parameter `refresh_interval` pada index `audit-logs-000001` menjadi `-1` (dinonaktifkan total).
2. Tulis satu dokumen baru via REST API.
3. Eksekusi pencarian dokumen tersebut menggunakan Match Query biasa. Analisis mengapa dokumen tersebut tidak ditemukan padahal status response pengiriman bernilai `201 Created`.
4. Jalankan perintah `POST /audit-logs-000001/_refresh` dan verifikasi kembali status pembacaan dokumen.

### Level Medium
1. Bangun sebuah Custom Analyzer dengan nama `code_symbol_analyzer` yang memisahkan teks berdasarkan delimiter karakter titik (`.`), underscore (`_`), dan strip (`-`), lalu mengubah seluruh karakter menjadi lowercase.
2. Buat mapping eksplisit untuk memetakan nama file paket kompilasi (misal: `org.apache.lucene.analysis.TokenStream`) menggunakan analyzer ini.
3. Buktikan hasil pencarian term `analysis` dapat menghasilkan skor kecocokan tinggi tanpa menggunakan fitur wildcard query yang boros performa.

### Level Hard
1. Eksekusi kondisi buatan di mana sebuah primary shard berada dalam status `UNASSIGNED` dengan mematikan node data penampung shard tersebut dan memaksa alokasi shard baru ke node yang tersisa menggunakan disk allocator setting `cluster.routing.allocation.enable: none`.
2. Gunakan `POST /_cluster/reroute` untuk mengatasi masalah alokasi tersebut secara manual tanpa merusak kesinambungan translog cluster.

---

## 14. Challenge: Zero-Downtime E-Commerce Reindex

### Latar Belakang Masalah
Sistem katalog marketplace Anda memiliki index produk berukuran 800GB bernama `ecommerce_catalog_v1` dengan 6 primary shard. 
Terdapat cacat desain teknis pada index tersebut:
* Field `sku_id` awalnya dipetakan secara implisit sebagai `long`. Akibatnya, format SKU baru yang mengandung kombinasi huruf (misal: `SKU-A99882`) ditolak oleh engine.
* Parameter `index.codec` belum menggunakan `best_compression`, menyebabkan pemborosan biaya storage AWS EBS.

### Misi Arsitek Sistem
Rancang dan eksekusi dokumen panduan arsitektur (*runbook*) lengkap tanpa menyebabkan *downtime* sistem (aplikasi klien tidak boleh menerima galat HTTP 5xx atau penurunan performa baca/tulis selama proses modifikasi berlangsung):

1. **Abstraksi Alias**: Alihkan seluruh akses API read/write ke sebuah alias transparan `ecommerce_catalog`.
2. **Skema Target**: Rancang `ecommerce_catalog_v2` dengan tipe `keyword` untuk `sku_id`, codec `best_compression`, dan tentukan jumlah shard optimal baru berdasarkan throughput query (bukan sekadar meniru konfigurasi lama).
3. **Reindex Pipeline Berkecepatan Tinggi**: Jalankan API `_reindex` dengan optimasi performa:
   * Matikan replika sementara pada index v2.
   * Tingkatkan interval refresh index v2 ke tak terhingga (`-1`).
   * Gunakan slice paralel (`slices: auto`) untuk membagi proses reindex ke beberapa thread worker.
4. **Sinkronisasi Selisih Mutasi (Delta Sync)**: Lakukan penanganan terhadap mutasi data yang masuk ke v1 saat proses background reindex sedang berjalan.
5. **Switch Traffic Atomik**: Alihkan pointer alias dari v1 ke v2 dalam satu operasi HTTP atomik tunggal via `_aliases`.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Pilihan Ganda (Basic)

1. Struktur data Lucene manakah yang dimuat ke dalam OS Page Cache/Heap untuk memetakan lokasi kata ke posisi posting list pada disk?
   * A) Doc Values
   * B) Finite State Transducer (FST)
   * C) Stored Fields (.fdt)
   * D) Translog (.tlog)
   * *Jawaban*: **B**. FST menyimpan kamus prefix term secara memori-kompak untuk melompat ke offset `Term Dictionary` tanpa melakukan I/O acak ke disk.

2. Mengapa segment Lucene didesain bersifat *immutable*?
   * A) Untuk mencegah pembacaan data historis.
   * B) Menghilangkan kebutuhan locking saat pencarian konkuren dan memaksimalkan efisiensi OS Page Cache.
   * C) Memaksa pengguna mengalokasikan RAM lebih dari 32GB.
   * D) Agar Translog tidak perlu ditulis ke dalam media disk fisik.
   * *Jawaban*: **B**. Immutability mengeliminasi *concurrency lock contention* pada tingkat pembacaan segment dan membuat cache data di level sistem operasi tidak berstatus dirty.

3. Apa konsekuensi teknis mengalokasikan JVM Heap sebesar 34GB pada Elasticsearch?
   * A) Mempercepat proses indexing dokumen sebesar 200%.
   * B) JVM menonaktifkan Compressed OOPs, pointer membesar jadi 64-bit, memboroskan memori, dan memicu garbage collection pause yang lebih masif.
   * C) Elasticsearch menolak menyala secara permanen.
   * D) Fitur Doc Values akan otomatis dimatikan oleh kernel OS.
   * *Jawaban*: **B**. Melewati batas ambang ~31-32GB memaksa JVM beralih dari referensi 32-bit ke 64-bit murni (*uncompressed*), memakan lebih banyak memori hanya untuk representasi overhead pointer pointer dasar objek.

4. Operasi internal apakah yang secara resmi mengubah status dokumen di memory buffer menjadi dapat dicari (*searchable*)?
   * A) Flush
   * B) Refresh
   * C) Fsync
   * D) Force Merge
   * *Jawaban*: **B**. Refresh menulis in-memory buffer ke segment baru di OS Page Cache dan membuka instance searcher baru (*Near-Real-Time point*).

5. Di mana letak penyimpanan struktur *Doc Values* di level sistem operasi?
   * A) Di dalam JVM Garbage Collection Young Generation.
   * B) Di dalam JVM Eden Space.
   * C) Di luar JVM Heap Memory (Off-Heap) melalui perantara OS Page Cache / `mmap`.
   * D) Di dalam antrean Write Thread Pool.
   * *Jawaban*: **C**. Doc Values dirancang *off-heap* dan diserahkan ke *OS Page Cache* untuk menjaga stabilitas heap dari beban kerja berat aggregasi/sorting.

---

### Bagian B: Analisis Arsitektur (Intermediate)

6. Jelaskan apa yang terjadi di disk dan memori ketika dokumen dengan ID yang sudah ada dikirimkan kembali menggunakan perintah `PUT /index/_doc/1`!
   * *Kunci Jawaban*: Dokumen lama **tidak di-overwrite di tempat**. Dokumen versi baru ditulis ke segment baru di *Memory Buffer* dan *Translog*. Nomor versi dokumen (`_version`) dinaikkan. Dokumen lama di segment aslinya tidak dihapus seketika, melainkan nomor internal DocID-nya didaftarkan ke berkas penghapusan `.del` (Soft-deleted). Dokumen lama baru akan musnah secara fisik dari storage saat proses *Segment Merge* (*TieredMergePolicy*) berjalan.

7. Mengapa pencarian teks panjang (deskripsi) sebaiknya menonaktifkan parameter `norms` jika field tersebut hanya digunakan untuk exact filtering bukan untuk menghitung skor BM25?
   * *Kunci Jawaban*: `norms` memakan alokasi 1 byte memory per dokumen per field di RAM/Disk untuk merekam enkripsi panjang dokumen (*field length normalization*). Mematikan norms (`"norms": false`) menghemat konsumsi storage dan memori secara masif jika relevansi tingkat kecocokan panjang karakter dokumen tidak diperhitungkan.

8. Terangkan alur kerja fase **Fetch** pada distributed query Elasticsearch!
   * *Kunci Jawaban*: Setelah fase **Query** menghasilkan daftar Top-N global gabungan yang berisi pasangan `DocID` dan metadata shard asal, Coordinating Node mengirim panggilan spesifik ke masing-masing Shard pemegang dokumen untuk menarik raw source dokumen (`_source`), field metadata tambahan, dan fragmen highlighting. Koordinasi ini mencegah pengiriman payload JSON besar lintas node secara sia-sia di fase awal.

9. Apa perbedaan esensial dari aksi *flush* dan *refresh* terkait dependensi durabilitas data terhadap kegagalan hardware (mati lampu tiba-tiba)?
   * *Kunci Jawaban*: *Refresh* hanya menjamin data bisa **dicari** dengan memindahkannya dari *Buffer* ke *OS Page Cache*; data ini rentan musnah jika mesin padam total mendadak (kecuali dipulihkan dari translog). Sedangkan *Flush* menjamin **durabilitas fisik mutlak** dengan memaksa pemanggilan fungsi kernel `fsync` ke media storage fisik dan memotong *checkpoint* Translog.

10. Kapan Anda harus memutuskan untuk menggunakan arsitektur *Searchable Snapshots* di fase Cold/Frozen?
    * *Kunci Jawaban*: Ketika volume data sangat masif (arsip tahunan/regulatory audit), jarang dicari, dan biaya penyediaan media penyimpanan blok (NVMe/SSD) node klaster sudah melewati batas efisiensi anggaran. *Searchable Snapshots* memungkinkan kita me-mount shard langsung dari Object Storage (misal AWS S3) hanya dengan memanfaatkan caching blok lokal kecil di Data Node saat pencarian dijalankan.

---

### Bagian C: Troubleshooting Kasus Produksi Tingkat Lanjut

#### Kasus 1: Write Rejection Cascade
*Skenario:* Pada event kilat belanja tanggal kembar, sistem ingest Anda mendadak mengalami error masif `429 Too Many Requests` disertai log `EsRejectedExecutionException [executor=write, queue_capacity=10000]`. Penggunaan CPU pada Data Node berada di level 99%.
*Tugas Anda:* Analisis akar masalah internal Lucene yang memicu penuhnya antrean `write threadpool` dan berikan solusi mitigasi darurat!
* *Kunci Analisis & Solusi*:
  1. *Akar Masalah:* Frekuensi refresh terlalu rapat (`1s` standar) memaksa penulisan ribuan segment mikro per detik, memicu badai *Segment Merging*. Segment Merging yang tak terkendali mengonsumsi seluruh siklus CPU dan bandwidth I/O disk, memperlambat pemrosesan thread `write`, sehingga antrean threadpool (`10000`) meluap dan request baru ditolak (*cascading rejection*).
  2. *Mitigasi Darurat Runtime:*
     * Naikkan interval refresh seluruh index yang aktif: `PUT /*/_settings {"index.refresh_interval": "60s"}`.
     * Ubah durabilitas translog ke async: `PUT /*/_settings {"index.translog.durability": "async"}`.
     * Nonaktifkan replika shard primer sementara ke angka `0` untuk memotong separuh overhead I/O, lalu aktifkan kembali saat traffic normal.

#### Kasus 2: Split-Brain Isolation pasca Network Partition
*Skenario:* Di dalam sebuah data center hybrid, 2 dari 5 node yang berperan ganda (*master-eligible*) mengalami isolasi jaringan sementara selama 40 detik. Sebelum Elasticsearch 7.x, hal ini kerap memicu klaster terbelah menjadi dua entitas independen yang sama-sama mempromosikan shard primer baru (*Split-Brain*).
*Tugas Anda:* Jelaskan secara ilmiah algoritma konsensus apa yang digunakan Elasticsearch versi modern (7.x ke atas) untuk meniadakan Split-Brain, dan parameter apa yang menguncinya secara deterministik!
* *Kunci Analisis & Solusi*:
  1. Elasticsearch 7.x+ meninggalkan mekanisme Zen Discovery lama berbasis `discovery.zen.minimum_master_nodes` dan mengadopsi varian algoritma konsensus berbasis **Raft** (*Voting Configuration*).
  2. Engine mempertahankan *cluster state* menggunakan kuorum suara pemilihan master mayoritas formal. Master Node baru hanya dapat diangkat jika disetujui oleh $\lfloor N/2 \rfloor + 1$ node dari konfigurasi voting yang sah.
  3. Node yang terisolasi di sisi minoritas (2 node) secara otomatis melepaskan jabatannya (*step down*) dan menolak pemrosesan mutasi baru karena gagal mengumpulkan kuorum master dari total 5 node. Parameter penentu awal adalah `cluster.initial_master_nodes`.

#### Kasus 3: Mapping Explosion Bencana OOM
*Skenario:* Tim aplikasi analitik mengarahkan output log aplikasi berformat unstructured JSON secara sembarangan ke index Elasticsearch produksi. Dalam 4 jam, ukuran heap memory di Master Node naik curam hingga menyentuh 100% dan terjadi OOM Crash berulang kali, walaupun volume total dokumen baru hanya 200MB.
*Tugas Anda:* Bedah mekanisme teknis di balik ambruknya klaster akibat data ukuran sekecil 200MB tersebut!
* *Kunci Analisis & Solusi*:
  1. *Mekanisme Kerusakan:* Terjadi **Mapping Explosion**. Log menyuntikkan ribuan field dinamis berbeda (misal: JSON memuat key UUID acak: `{"e73b-41a2-...": "value"}`).
  2. Master Node bertugas menyimpan salinan metadata arsitektur (*Cluster State*) yang mencakup definisi skema mapping seluruh index secara terpusat di dalam Heap Memory-nya.
  3. Setiap penambahan field baru memicu mutasi *Cluster State*, yang harus disebarkan (*broadcast*) ke seluruh node di klaster. Ribuan field baru yang dibuat setiap detik membludak di memori Master Node hingga memicu *Garbage Collection Thrashing* dan diakhiri dengan crash `java.lang.OutOfMemoryError: Java heap space`.
  4. *Solusi*: Selalu aktifkan batasan keras skema:
     `PUT /_cluster/settings {"persistent": {"indices.mapping.total_fields.limit": 1000}}` serta kunci skema index data ingestion menggunakan `"dynamic": "strict"` atau `"dynamic": false`.

---

## 16. Summary

```
Elasticsearch Performance & Resiliency Foundation
├── 1. Memory Tiering
│   ├── JVM Heap (Ideal: <= 30GB)  ──► In-memory Buffer, In-Flight Aggregations, FST
│   └── OS Page Cache (Off-Heap)   ──► Segment Files, Lucene Doc Values, Stored Fields
├── 2. Ingestion Mechanics
│   ├── Buffer Ingestion           ──► Cepat, volatile, belum searchable
│   ├── Refresh (e.g. 30s)         ──► Menghasilkan Immutable Segment (Near-Real-Time)
│   ├── Translog Sync              ──► Jaminan Crash Durability (ACID layer)
│   └── Flush (e.g. 512MB/30m)     ──► Fsync segment ke disk fisik & pembersihan Translog
├── 3. Retrieval Optimization
│   ├── Inverted Index             ──► Text Search (BM25 scoring, postings lists)
│   ├── Doc Values (Columnar)      ──► Sorting, Aggregations, Scripting
│   └── Query-then-Fetch           ──► Mengurangi saturasi bandwidth jaringan cluster
└── 4. Lifecycle Automation
    └── ILM (Hot -> Warm -> Cold)  ──► Efisiensi storage berjenjang via rollover & forcemerge
```

Memahami Elasticsearch pada skala enterprise menuntut pergeseran paradigma dari memperlakukannya sebagai "database NoSQL biasa" menuju pemahaman mendalam atas mekanika internal **Apache Lucene**. 

Keberhasilan stabilitas klaster dengan volume data multiterabyte tidak ditentukan oleh besarnya kapasitas memori atau core CPU yang Anda sediakan, melainkan oleh presisi konfigurasi: **desain mapping yang ketat (*strict mappings*)**, penghapusan overhead scoring yang tidak terpakai, pemanfaatan **Doc Values *off-heap*** secara optimal, serta pemilihan interval **Refresh, Flush, dan Segment Merge** yang seimbang dengan batas toleransi durabilitas bisnis Anda.