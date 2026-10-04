# BAB 08: Data Tiering & Index Lifecycle Management (ILM)
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Memahami dan mengonfigurasi arsitektur **Data Tiering berbasis Node Roles modern** (`data_hot`, `data_warm`, `data_cold`, `data_frozen`, `data_content`) menggantikan arsitektur legacy berbasis atribut routing (`node.attr.box_type`).
- Menguasai **Internal State Machine Index Lifecycle Management (ILM)**: transisi fase (*Phase* $\rightarrow$ *Action* $\rightarrow$ *Step*), mekanisme *error retry*, dan parameter internal `indices.lifecycle.poll_interval`.
- Merancang dan mengimplementasikan **Searchable Snapshots** pada tier *Cold* (*fully mounted index*) dan *Frozen* (*partially mounted index*) menggunakan Object Storage (AWS S3, MinIO, atau GCS) untuk reduksi TCO (*Total Cost of Ownership*) hingga >70%.
- Mengintegrasikan **Data Streams** dengan composable index templates dan ILM policies untuk automasi penanganan data deret waktu (*time-series data*) pada skala terabyte/petabyte per hari.
- Mendiagnosis dan menyelesaikan kegagalan eksekusi ILM (*stuck phases*, *watermark allocation collision*, kegagalan *force merge*, dan fragmentasi *shard snapshot cache*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta harus telah menguasai:
- **Arsitektur Dasar Elasticsearch**: Node, Primary Shard, Replica Shard, Cluster State, dan Distributed Consensus (Raft-based master election).
- **Lucene Core Concepts**: Immutability segment, Segment Merging, Deleted Documents, dan Inverted Index.
- **BAB 08 - Modul 01**: Dasar-dasar ILM, pembuatan index template dasar, dan lifecycle API sederhana.
- **Infrastruktur Dasar**: Konfigurasi storage (NVMe vs SSD vs HDD vs S3/Object Storage), RAM sizing (JVM Heap vs Lucene File System Cache), dan Docker Compose/Kubernetes primitives.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Node Roles Architecture vs. Legacy Attribute Routing
Pada Elasticsearch versi legacy (< 7.10), data tiering diimplementasikan menggunakan custom node attributes (`node.attr.data_tier: hot`) dikombinasikan dengan shard routing allocation filters (`index.routing.allocation.require.data_tier`). Pendekatan ini memiliki kelemahan: master node tidak memahami semantik lifecycle secara natif, sehingga kalkulasi shard balance sering kali sub-optimal.

Sejak Elasticsearch 7.10+, arsitektur beralih ke **Tiers via Node Roles natif**:
- `data_content`: Menyimpan data persistens reguler non-time-series yang tidak mengalami lifecycle rollover (misal: katalog produk, data master entitas).
- `data_hot`: Menampung data time-series ingestion aktif. Memerlukan resource I/O komputasi dan write tertinggi (NVMe SSD, high CPU, high memory).
- `data_warm`: Query intensitas rendah-sedang, write non-aktif (read-only), optimized for cost-to-performance. Shard biasanya di-shrink dan segmen di-merge.
- `data_cold`: Query sangat jarang. Indeks dapat diubah menjadi regular read-only index atau *Fully Mounted Searchable Snapshot* (mengambil salinan dari snapshot repository lokal/remote).
- `data_frozen`: Query ad-hoc/historis. Menggunakan arsitektur *Partially Mounted Searchable Snapshot*. Shard data tidak disimpan penuh di disk lokal, melainkan di-stream secara on-demand via cache lokal terbatas dari Object Storage (S3).

```
[ Ingest Pipeline / Logstash / Beats ]
                 │
                 ▼ (High Write IOPS)
       ┌───────────────────┐
       │   HOT TIER        │  Node Role: [ data_hot ]
       │ (Local NVMe SSD)  │  Write: Aktif | Read: Realtime Analytics
       └─────────┬─────────┘
                 │ (Rollover Trigger: Size > 50GB / Age > 1d)
                 ▼
       ┌───────────────────┐
       │   WARM TIER       │  Node Role: [ data_warm ]
       │ (SATA SSD / HDD)  │  Write: Blocked | Read: Dashboarding / Search
       │                   │  Action: Read-Only, Shrink Shard, Force Merge (1 seg)
       └─────────┬─────────┘
                 │ (Age > 7d)
                 ▼
       ┌───────────────────┐
       │   COLD TIER       │  Node Role: [ data_cold ]
       │ (Network Attached/│  Read: Occasional / Forensics
       │  Searchable Snap) │  Action: Fully Mounted Index (from S3)
       └─────────┬─────────┘
                 │ (Age > 30d)
                 ▼
       ┌───────────────────┐
       │  FROZEN TIER      │  Node Role: [ data_frozen ]
       │ (Object Storage + │  Read: Rare Ad-Hoc Audit Queries
       │  Local LRU Cache) │  Action: Partially Mounted Index (Zero Local Primaries)
       └─────────┬─────────┘
                 │ (Age > 365d)
                 ▼
       ┌───────────────────┐
       │   DELETE TIER     │  Indices / Snapshots purged from storage
       └───────────────────┘
```

#### B. Internal ILM State Machine Execution Engine
ILM bekerja di dalam thread context Master Node melalui background service:
1. **Poll Engine**: ILM service mengeksekusi poll secara periodik (default: `indices.lifecycle.poll_interval: 10m`).
2. **Phase Definition**: `hot` $\rightarrow$ `warm` $\rightarrow$ `cold` $\rightarrow$ `frozen` $\rightarrow$ `delete`. Indeks dievaluasi apakah kriteria umur (`min_age`) telah terpenuhi. Catatan teknis: `min_age` dihitung secara default sejak **waktu rollover**, bukan tanggal pembuatan indeks asli (dapat diubah via `origination_date`).
3. **Action Execution**: Tiap fase memiliki aksi spesifik (`rollover`, `shrink`, `forcemerge`, `read_only`, `allocate`, `searchable_snapshot`).
4. **Step Breakdown**: Setiap action dipecah menjadi atom-atom state yang disebut **Step**:
   - `Pre-flight steps`: Memvalidasi kelayakan indeks (misal: verifikasi cluster health, disk watermark).
   - `Async action steps`: Memulai operasi asynchronous (misal: memulai task `_forcemerge` atau `snapshot`).
   - `Wait steps`: Polling status dari async task hingga selesai (`check-action-complete`).

Jika sebuah step gagal (misal: target node warm out-of-disk), ILM beralih ke status `ERROR`. Master node akan menghentikan eksekusi ILM pada indeks tersebut hingga intervensi manual atau auto-retry terpicu via `POST <index>/_ilm/retry`.

#### C. Searchable Snapshots: Fully Mounted vs. Partially Mounted
Searchable Snapshots adalah inovasi fundamental yang memisahkan storage tier dari compute tier.
- **Fully Mounted (Cold Tier)**:
  Elasticsearch me-mount shard langsung dari snapshot repository, namun **seluruh metadata Lucene dan full copy dari data file dicache penuh** ke disk lokal node `data_cold`. Jika node mati, shard dialokasikan ke node lain dengan mendownload ulang file dari snapshot repository.
- **Partially Mounted (Frozen Tier)**:
  Shard diperlakukan sebagai virtual dataset. Node `data_frozen` **hanya mendownload file indeks yang relevan dengan eksekusi query aktif** (misal: `terms dictionary`, `doc_values` tertentu) ke dalam disk cache lokal berbasis LRU (*Least Recently Used*). Disk requirement di frozen node hanya berkisar 1-10% dari total size indeks di snapshot.

---

### 4. Why & What

#### Mengapa Tidak Menggunakan Single Tier Storage?
1. **Economic Feasibility**: Menyimpan 100 TB data log/audit per bulan di NVMe SSD kelas enterprise (Tier Hot) membutuhkan biaya infrastruktur yang sangat masif.
2. **Lucene Resource Contention**: Segment merging dan I/O intensif pada data historis mengganggu ingestion throughput data baru yang masuk.
3. **Memory Pressure**: JVM Heap terbatas pada 31-32 GB (Compressed OOP limit). Shard yang tidak aktif tetap mengonsumsi memory heap untuk index overhead jika tidak di-tiering dan dioptimasi.

#### Apa yang Dicapai oleh Data Tiering Modern?
- **SLA Ingestion Konsisten**: Node *Hot* didedikasikan murni untuk parallel ingestion dan query realtime (0-24 jam).
- **Optimalisasi Densitas Data**: Menggunakan *force-merge* ke single segment pada fase *Warm* secara dramatis mengurangi overhead doc values dan inverted index.
- **Cost Reduction Ekstrem**: Dengan memindahkan data >30 hari ke Object Storage (S3 Standard/Infrequent Access) melalui *Frozen Tier*, biaya storage per gigabyte turun drastis hingga lebih dari 70-85%.

---

### 5. How (Workflow Detail)

Alur kerja transisi indeks melalui ILM dan Data Tiering:

```
[Ingest]
   │
   ▼
[1. HOT PHASE]
   │  - Auto-routing ke node: [data_hot]
   │  - Evaluasi berkala: bytes index >= 50GB ATAU age >= 1 hari?
   │
   ├─► (Syarat terpenuhi) -> TRIGGER ACTION: ROLLOVER
   │      ├─ Shard baru dibuat: data-stream-000002 (menerima data tulis)
   │      └─ Shard lama (000001) dialihkan menjadi target ILM selanjutnya
   ▼
[2. WARM PHASE (min_age: 1d setelah rollover)]
   │  - Action: Set Read-Only
   │  - Action: Migrate Shard routing ke node: [data_warm]
   │  - Action: Shrink Shard (jika diaktifkan, kurangi primary shard)
   │  - Action: Force Merge (`max_num_segments: 1`) -> Purge deleted docs
   ▼
[3. COLD PHASE (min_age: 7d)]
   │  - Action: Migrate Shard routing ke node: [data_cold]
   │  - Action Alt: Searchable Snapshot (Fully Mounted) -> Snap ke S3, mount ke cold node
   ▼
[4. FROZEN PHASE (min_age: 30d)]
   │  - Action: Searchable Snapshot (Partially Mounted)
   │  - Target node: [data_frozen]
   │  - Index primary shard dialihkan ke virtual reference snapshot S3
   │  - Alokasi disk lokal hanya sebagai Shared LRU Cache
   ▼
[5. DELETE PHASE (min_age: 365d)]
   │  - Action: Delete Snapshot / Delete Index
   │  - Resource purging & Lucene clean up
   ▼
[End of Life]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsip Rekam Medis Rumah Sakit
1. **Hot Tier (Ruang UGD / Meja Dokter)**: Pasien yang sedang ditangani saat ini. Rekam medis diletakkan di atas meja (NVMe SSD), dapat ditulis langsung, diakses instan. Kapasitas meja kecil, biaya meja per meter persegi sangat mahal.
2. **Warm Tier (Lemari Arsip Ruang Administrasi)**: Pasien yang baru keluar rumah sakit kemarin/minggu ini. Berkas dikelompokkan, dijilid rapi/disatukan (*force merge*), tidak boleh dicoret-coret lagi (*read-only*), disimpan di lemari kantor (SATA SSD).
3. **Cold Tier (Gudang Arsip Basement Rumah Sakit)**: Rekam medis bulan lalu. Berkas dibungkus kardus bersegel (*snapshot*). Jika butuh membaca, petugas mengambil kardus tersebut dan membukanya seutuhnya di atas meja gudang (*fully mounted*).
4. **Frozen Tier (Arsip Eksternal Remote Berbayar)**: Berkas 5-10 tahun lalu disimpan di fasilitas sewa luar kota (Amazon S3). Pasien tidak lagi dipegang berkas fisiknya. Ketika auditor datang mencari halaman tertentu, kurir hanya mengambil dan memfotokopi halaman spesifik yang diminta (*partially mounted on-demand caching*).
5. **Delete Tier (Mesin Penghancur Kertas)**: Setelah 10 tahun, berkas dihancurkan demi kepatuhan regulasi dan efisiensi ruang.

---

### 7. Simple Example & Practical Example

#### Implementasi Lengkap Standar Industri
Berikut implementasi konfigurasi production yang memadukan Composable Index Template, ILM Policy multi-tiering (Hot $\rightarrow$ Warm $\rightarrow$ Cold $\rightarrow$ Frozen $\rightarrow$ Delete), dan Data Streams.

##### Langkah 1: Registrasi Snapshot Repository (Prasyarat Searchable Snapshots)
```json
PUT _snapshot/corporate_s3_repository
{
  "type": "s3",
  "settings": {
    "bucket": "corp-telemetry-elasticsearch-cold-archive",
    "region": "ap-southeast-1",
    "base_path": "ilm-searchable-snapshots",
    "compress": true,
    "max_restore_bytes_per_sec": "100mb"
  }
}
```

##### Langkah 2: Pembuatan ILM Policy Enterprise Multi-Tier
```json
PUT _ilm/policy/telemetry_data_lifecycle_policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_primary_shard_size": "50gb",
            "max_age": "1d",
            "max_docs": 100000000
          },
          "set_priority": {
            "priority": 100
          }
        }
      },
      "warm": {
        "min_age": "1d",
        "actions": {
          "set_priority": {
            "priority": 50
          },
          "allocate": {
            "number_of_replicas": 1
          },
          "readonly": {},
          "forcemerge": {
            "max_num_segments": 1
          }
        }
      },
      "cold": {
        "min_age": "7d",
        "actions": {
          "set_priority": {
            "priority": 20
          },
          "searchable_snapshot": {
            "snapshot_repository": "corporate_s3_repository",
            "force_merge_previous_phase": false
          },
          "allocate": {
            "number_of_replicas": 0
          }
        }
      },
      "frozen": {
        "min_age": "30d",
        "actions": {
          "searchable_snapshot": {
            "snapshot_repository": "corporate_s3_repository"
          }
        }
      },
      "delete": {
        "min_age": "365d",
        "actions": {
          "delete": {
            "delete_searchable_snapshot": true
          }
        }
      }
    }
  }
}
```

##### Langkah 3: Membuat Component Template (Settings & Mappings)
```json
PUT _component_template/telemetry_settings
{
  "template": {
    "settings": {
      "number_of_shards": 2,
      "number_of_replicas": 1,
      "index.lifecycle.name": "telemetry_data_lifecycle_policy",
      "index.codec": "best_compression",
      "index.routing.allocation.total_shards_per_node": 3
    }
  }
}

PUT _component_template/telemetry_mapping
{
  "template": {
    "mappings": {
      "properties": {
        "@timestamp": {
          "type": "date"
        },
        "service_name": {
          "type": "keyword"
        },
        "http": {
          "properties": {
            "request_method": { "type": "keyword" },
            "response_status_code": { "type": "short" }
          }
        },
        "latency_ms": {
          "type": "float"
        },
        "message": {
          "type": "text"
        }
      }
    }
  }
}
```

##### Langkah 4: Membuat Composable Index Template Menggunakan Data Stream
```json
PUT _index_template/telemetry_template
{
  "index_patterns": ["telemetry-service-*"],
  "data_stream": {},
  "composed_of": ["telemetry_settings", "telemetry_mapping"],
  "priority": 500,
  "_meta": {
    "description": "Production Data Stream template for telemetry logging with multi-tiering"
  }
}
```

##### Langkah 5: Ingest Event Pertama ke Data Stream
```json
POST telemetry-service-prod/_doc
{
  "@timestamp": "2026-03-30T10:00:00Z",
  "service_name": "payment-gateway",
  "http": {
    "request_method": "POST",
    "response_status_code": 200
  },
  "latency_ms": 142.5,
  "message": "Transaction authorization successful"
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Arsitektur Audit Finansial Perbankan (50 TB/Hari)
Sebuah bank digital memproses miliaran transaksi finansial yang menghasilkan **50 TB audit events per hari**. 
- **Regulasi**: Data 30 hari harus instan untuk operational analytics (fraud detection). Data 1 tahun hingga 7 tahun wajib disimpan dan dapat dicari sewaktu-waktu jika ada audit investigasi dari regulator (OJK/BI).
- **Problem**: Jika 50 TB/hari disimpan di NVMe SSD selama 1 tahun:
  $50\text{ TB} \times 365 = 18.25\text{ PB}$ storage lokal (belum termasuk replikasi). Biaya provisioning storage & server tidak realistis.

#### Solusi Arsitektur
1. **Tier Hot (Day 0 - Day 3)**:
   - 30 node dedicated `data_hot` (masing-masing 8 TB NVMe, 64 GB RAM).
   - Dynamic Shard Routing: Target 40 primary shards per index harian, shard size dijaga pada $\approx 45\text{ GB}$.
   - Storage Codec: `default` (LZ4) untuk efisiensi CPU pada saat write tinggi.
2. **Tier Warm (Day 3 - Day 14)**:
   - 20 node dedicated `data_warm` (masing-masing 24 TB SATA SSD).
   - Trigger: Rollover tercapai. Indeks dibuat `read-only`, shard dilakukan `forcemerge` ke single segment (`best_compression` / Deflate). Menghemat storage sebesar 38%.
3. **Tier Cold (Day 14 - Day 90)**:
   - 10 node dedicated `data_cold`.
   - ILM memicu Searchable Snapshot ke S3. Node Cold me-mount snapshot dengan disk lokal cache.
4. **Tier Frozen (Day 90 - Day 365+)**:
   - 6 node dedicated `data_frozen` (Node memory tinggi, disk NVMe cache kecil: 2 TB per node).
   - Menggunakan Partially Mounted Index via S3. Rata-rata response time audit historis: 3 - 8 detik (masih dalam batas SLA audit legal).
5. **Hasil / Impact**:
   - TCO infrastruktur berkurang sebesar **74.3%**.
   - JVM GC Pause di node Hot turun dari rata-rata 1200ms ke under 80ms karena node Hot terbebas dari query berat histori lama dan I/O *force merge*.

---

### 9. Trade-offs

| Parameter | Hot Tier | Warm Tier | Cold Tier (Searchable Snapshot) | Frozen Tier (Partially Mounted) |
| :--- | :--- | :--- | :--- | :--- |
| **Storage Type** | High-performance NVMe | SATA SSD / Fast HDD | Object Storage + Local SSD Cache | Object Storage + Minimal LRU Cache |
| **Write/Ingest** | Write-Heavy | Read-Only (No Writes) | Read-Only (Mounted) | Read-Only (Mounted) |
| **Query Latency** | Ultra Low (< 50ms) | Low (< 200ms) | Moderate (200ms - 2s) | High (2s - 15s+) |
| **Compute Cost** | Sangat Mahal | Sedang | Rendah | Sangat Murah |
| **Storage Cost/GB** | $0.25 - $0.40 | $0.08 - $0.12 | $0.023 (S3 Standard) | $0.0125 (S3 Infrequent Access) |
| **Memory Overhead** | Heap tinggi (indexing) | Heap sedang (merging) | Heap sangat rendah | Heap ultra rendah (cache off-heap) |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Force Merge Dieksekusi Pada Indeks yang Masih Ditulis
- **Gejala**: CPU spike 100% pada node Hot, JVM crash (OOM), write rejection (`429 Too Many Requests`).
- **Penyebab**: Menempatkan action `forcemerge` di fase `hot` sebelum aksi `rollover` tuntas. Segmen baru yang terus masuk bercampur dengan segment merge intensif.
- **Solusi**: Hanya jalankan `forcemerge` pada indeks yang telah melewati `rollover` dan diproteksi oleh action `readonly` di fase `warm`.

#### Mistake 2: ILM Policy Error: "index.lifecycle.rollover_alias does not point to index"
- **Gejala**: ILM macet pada step `check-rollover-ready`.
- **Penyebab**: Menggunakan index alias tradisional tanpa konfigurasi write index (`is_write_index: true`), atau memigrasikan data stream tanpa composable template yang benar.
- **Pemeriksaan & Solusi**:
  ```json
  GET /_ilm/explain?only_errors=true
  ```
  Jika terjadi error, verifikasi bahwa index memiliki pointing alias:
  ```json
  POST /_aliases
  {
    "actions": [
      {
        "add": {
          "index": "logs-service-000001",
          "alias": "logs-service-write",
          "is_write_index": true
        }
      }
    ]
  }
  ```
  Kemudian lakukan trigger manual:
  ```json
  POST logs-service-000001/_ilm/retry
  ```

#### Mistake 3: Shard Terjebak di Unassigned State Akibat Disk Watermark Conflict
- **Gejala**: Shard allocation gagal saat transisi dari fase Hot ke Warm.
- **Penyebab**: Node `data_warm` telah melewati batas `cluster.routing.allocation.disk.watermark.high` (default: 90%).
- **Solusi**:
  1. Periksa alokasi via Allocation Explain API:
     ```json
     GET _cluster/allocation/explain
     {
       "index": ".ds-telemetry-service-prod-2026.03.30-000001",
       "shard": 0,
       "primary": true
     }
     ```
  2. Naikkan threshold secara sementara jika kapasitas darurat tersedia:
     ```json
     PUT _cluster/settings
     {
       "persistent": {
         "cluster.routing.allocation.disk.watermark.high": "95%"
       }
     }
     ```
  3. Lakukan provisioning node `data_warm` tambahan.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Data Streams**: Gunakan data streams untuk data deret waktu alih-alih me-manage index alias secara manual.
- [ ] **Gunakan Node Roles Eksplisit**: Konfigurasikan file `elasticsearch.yml` dengan role terisolasi. Jangan campur `data_hot` dengan `data_warm` di instance yang sama.
- [ ] **Atur Shard Size Optimal**: Jaga ukuran primary shard antara **30 GB hingga 50 GB**. Shard < 10 GB menimbulkan overhead cluster state; shard > 65 GB memperlambat recovery jaringan dan force merge.
- [ ] **Satu Segmen pada Warm Phase**: Selalu jalankan `forcemerge` dengan `max_num_segments: 1` di Warm phase untuk menghapus bitvector dokumen yang telah terhapus (*tombstones*) dan memadatkan inverted index.
- [ ] **Kurangi Replikasi di Tier Bawah**: Turunkan `number_of_replicas` menjadi `0` atau `1` saat beralih ke Searchable Snapshot di Cold/Frozen tier karena daya tahan (*durability*) data dijamin oleh storage backend (S3 menjamin 99.999999999% durability).
- [ ] **Atur Poll Interval Terukur**: Nilai default `indices.lifecycle.poll_interval` adalah `10m`. Jangan turunkan ke nilai di bawah `1m` di cluster production skala besar untuk mencegah excessive master node load.
- [ ] **Monitor Snapshot Cache**: Pantau metric `elasticsearch.searchable_snapshots.cache_fetch_latencies` dan pastikan disk cache lokal pada node Frozen memiliki IOPS yang memadai (gunakan Enterprise SSD untuk cache tier).

---

### 12. Hands-on Practice

Simulasi lab multi-tiering menggunakan Docker Compose: 1 Master Node, 1 Ingest/Hot Node, 1 Warm Node, dan MinIO (S3 Compatible Storage).

#### Direktori Kerja: `hands-on/m02/`

##### File 1: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'

services:
  es-master:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    container_name: es-master
    environment:
      - node.name=es-master
      - cluster.name=tiering-lab
      - node.roles=master
      - discovery.seed_hosts=es-master,es-hot,es-warm
      - cluster.initial_master_nodes=es-master
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - xpack.security.enabled=false
      - indices.lifecycle.poll_interval=10s
    ulimits:
      memlock:
        soft: -1
        hard: -1
    networks:
      - elk-tiering

  es-hot:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    container_name: es-hot
    environment:
      - node.name=es-hot
      - cluster.name=tiering-lab
      - node.roles=data_hot,data_content,ingest
      - discovery.seed_hosts=es-master,es-hot,es-warm
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
    ports:
      - "9200:9200"
    networks:
      - elk-tiering

  es-warm:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    container_name: es-warm
    environment:
      - node.name=es-warm
      - cluster.name=tiering-lab
      - node.roles=data_warm
      - discovery.seed_hosts=es-master,es-hot,es-warm
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
    networks:
      - elk-tiering

networks:
  elk-tiering:
    driver: bridge
```

##### File 2: `hands-on/m02/run_lab.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> 1. Menjalankan Cluster Elasticsearch Multi-Tier..."
docker compose up -d

echo "==> 2. Menunggu Elasticsearch Cluster Siap..."
until curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green"\|"status":"yellow"'; do
    sleep 3
    echo "Sedang menunggu node online..."
done

echo "==> 3. Memasang ILM Policy dengan Fast Rollover (Lab Condition)..."
curl -X PUT "http://localhost:9200/_ilm/policy/lab_fast_ilm_policy" \
     -H 'Content-Type: application/json' -d'
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_docs": 5
          }
        }
      },
      "warm": {
        "min_age": "5s",
        "actions": {
          "allocate": {
            "number_of_replicas": 0
          },
          "forcemerge": {
            "max_num_segments": 1
          }
        }
      },
      "delete": {
        "min_age": "120s",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}'

echo -e "\n==> 4. Membuat Index Template berbasis Data Stream..."
curl -X PUT "http://localhost:9200/_index_template/lab_logs_template" \
     -H 'Content-Type: application/json' -d'
{
  "index_patterns": ["lab-logs-*"],
  "data_stream": {},
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0,
      "index.lifecycle.name": "lab_fast_ilm_policy"
    }
  }
}'

echo -e "\n==> 5. Melakukan Ingest Data Melebihi Threshold Rollover (6 Docs)..."
for i in {1..6}; do
  curl -s -X POST "http://localhost:9200/lab-logs-app/_doc" \
       -H 'Content-Type: application/json' -d "{\"@timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\", \"message\": \"Test event number $i\"}" > /dev/null
  echo "Ingested doc $i"
done

echo -e "\n==> 6. Data berhasil di-ingest. Observasi status ILM Generation 000001:"
sleep 2
curl -s -X GET "http://localhost:9200/lab-logs-app/_ilm/explain" | grep -E '(step|phase|action)'

echo -e "\n\nLab berhasil dikonfigurasi. Jalankan pengamatan real-time dengan command:"
echo "watch -n 2 'curl -s http://localhost:9200/_cat/shards/lab-logs*?v=true&h=index,shard,prirep,state,node,docs.count'"
```

---

### 13. Exercise

#### Level Easy
1. Ubah parameter `lab_fast_ilm_policy` untuk memodifikasi batas `rollover` agar terpicu saat shard size mencapai `100mb` atau dokumen berjumlah `1000`. Eksekusi API call yang relevan.
2. Buat query pencarian menggunakan Dev Tools untuk mencari status indeks yang mengalami error pada ILM.

#### Level Medium
1. Simulasikan skenario kegagalan: Ubah ILM policy pada fase warm untuk meminta alokasi replica `number_of_replicas: 2`. Amati apa yang terjadi pada cluster lab (karena hanya ada 1 node warm).
2. Periksa status error menggunakan `GET <index>/_ilm/explain`. Selesaikan masalah tersebut tanpa me-restart container Elasticsearch.

#### Level Hard
1. Buat pipeline yang mengonversi index statis yang sudah ada (misal: `legacy-syslog-2025.12`) menjadi terkelola penuh oleh ILM, dialokasikan langsung ke node `data_warm`, dan di-force merge ke 1 segmen dengan kompresi `best_compression`, tanpa memicu fase `hot` rollover.

---

### 14. Challenge

**Studi Kasus Multi-Tenant Elastic Cloud Provider**:
Sebuah platform SaaS menyediakan logging infrastructure untuk 500 enterprise tenants. 
- Tenant Tier Platinum: Retensi Hot 7 hari, Warm 30 hari, Cold 90 hari, Searchable Snapshot Frozen 365 hari.
- Tenant Tier Bronze: Retensi Hot 1 hari, Warm 3 hari, langsung Delete pada hari ke-7 (tidak ada Cold/Frozen).

**Objektif Anda**:
Rancang arsitektur automation end-to-end:
1. Skema penamaan Data Stream dan pemetaan template terisolasi antar tenant.
2. Mekanisme dinamis yang mencegah *noisy neighbor problem* saat 50 tenant Platinum mengeksekusi `forcemerge` secara simultan pada pergantian hari (midnight UTC).
3. Penanganan skenario saat Object Storage (S3) mengalami outage parsial (HTTP 503 Slow Down / Network Partition) agar ingestion pipeline di Tier Hot tidak mengalami *backpressure* maupun cascade cluster crash.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa perbedaan mendasar antara node role `data_hot` dan `data_content`?
2. Mengapa action `forcemerge` sangat tidak disarankan untuk dijalankan pada fase Hot?
3. Parameter cluster apa yang menentukan seberapa sering master node mengevaluasi ILM policies?
4. Apa yang terjadi pada index yang sedang berada di bawah manajemen Data Stream saat dilakukan rollover?
5. Mengapa replikasi shard pada Searchable Snapshots (Cold/Frozen Tier) dapat dikurangi hingga 0 tanpa mengorbankan durabilitas data?

#### B. Pertanyaan Intermediate
6. Bagaimana cara ILM menghitung umur sebuah indeks (`min_age`) jika indeks tersebut telah mengalami rollover? Dari titik waktu mana perhitungan dimulai?
7. Jelaskan perbedaan cara kerja eksekusi query pada *Fully Mounted Searchable Snapshot* dibanding *Partially Mounted Searchable Snapshot*!
8. Apa yang menyebabkan sebuah indeks masuk ke dalam step `ERROR` pada ILM explain API, dan langkah apa yang harus dilakukan pertama kali untuk memperbaikinya?
9. Bagaimana cara kerja internal cache pada node `data_frozen` ketika melayani query aggregate data historis berukuran besar?
10. Jika Anda menetapkan `shrink` action pada fase Warm, apa prasyarat mutlak yang harus dipenuhi oleh shard allocation index tersebut sebelum operasi shrink dapat berjalan?

#### C. Skenario Kasus Produksi
11. **Kasus 1**: Pada cluster produksi berukuran 50 node, master node mengalami saturasi memory JVM (Garbage Collection thrashing) setiap kali ILM poll interval dieksekusi. Ditemukan terdapat 25.000 indeks aktif di cluster. Bagaimana Anda merestrukturisasi policy ILM dan segment architecture untuk menstabilkan cluster?
12. **Kasus 2**: Tim security melaporkan bahwa query forensik pada indeks 6 bulan lalu (Frozen Tier) membutuhkan waktu 45 detik untuk selesai pada eksekusi pertama, namun hanya 1.2 detik pada eksekusi kedua untuk query yang sama. Jelaskan fenomena internal yang terjadi di node `data_frozen`!
13. **Kasus 3**: Shard data stream Anda berukuran 120 GB di fase Hot, padahal di ILM policy sudah diset `max_primary_shard_size: 50gb`. Setelah dicek, rollover tidak pernah terpicu. Sebutkan 3 kemungkinan akar masalah dan bagaimana cara Anda memverifikasinya melalui Elasticsearch REST API!

---

### Kunci Jawaban Singkat Quiz

#### Jawaban Basic:
1. `data_hot` dirancang spesifik untuk time-series data yang terus masuk dan diatur oleh ILM, sedangkan `data_content` dirancang untuk data reguler yang persistens (seperti indeks relasional, katalog, e-commerce products) yang tidak memiliki konsep waktu/lifecycle rollover.
2. Karena `forcemerge` adalah operasi I/O dan CPU intensif (menulis ulang seluruh segmen). Jika dijalankan di Hot node yang sedang melayani ribuan write operations per detik, operasi ini akan menghabiskan I/O bandwidth disk dan memory, menyebabkan disk saturation, request timeout, dan ingest drops.
3. Parameter `indices.lifecycle.poll_interval` (default bernilai 10 menit).
4. Indeks lama diubah statusnya menjadi write-blocked (bukan lagi write index), nomor generasi bertambah (`.ds-<name>-000002`), dan indeks baru dibuat serta ditandai sebagai `is_write_index: true`.
5. Karena replika data sesungguhnya sudah terjamin oleh durabilitas object storage (seperti Amazon S3 / Google Cloud Storage yang memiliki SLA durability 99.999999999%). Jika node yang me-mount shard mati, shard baru dapat segera di-mount ulang pada node lain dari source storage yang sama.

#### Jawaban Intermediate:
6. Secara default, jika rollover telah terjadi, `min_age` dihitung dari **waktu saat rollover selesai** (`index.lifecycle.rollover_date`), bukan saat indeks pertama kali dibuat.
7. Pada *Fully Mounted*, seluruh copy Lucene segment didownload penuh ke persistent storage lokal node Cold saat mounting; query dieksekusi murni terhadap disk lokal. Pada *Partially Mounted*, file indeks tetap berada di Object Storage; node Frozen hanya mendownload bagian-bagian file yang diakses query via LRU local cache.
8. Indeks masuk step `ERROR` jika ada dependensi action yang gagal diselesaikan (misalnya snapshot repo tidak tersedia, disk penuh melebihi high watermark, atau node target role tidak ditemukan). Perbaikan: Jalankan `GET <index>/_ilm/explain` untuk melihat `failed_step` dan `step_info`, perbaiki akar masalah infrastruktur/setting, lalu jalankan `POST <index>/_ilm/retry`.
9. Node `data_frozen` menggunakan block-level cache lokal. Ketika query aggregate berjalan, node membaca chunk index langsung dari object storage via parallel range-request, memprosesnya ke JVM heap, dan menyimpan blok-blok tersebut ke SSD cache lokal dengan mekanisme eviction berbasis LRU jika cache penuh.
10. Seluruh primary shard atau replica shard dari index tersebut harus dialokasikan secara penuh ke **satu node yang sama** (`index.routing.allocation.require._name`), dan index harus dalam kondisi `read_only`.

#### Jawaban Skenario Kasus:
11. **Solusi Kasus 1**: Kurangi total indeks dengan mengkonsolidasikan data stream, perpanjang `indices.lifecycle.poll_interval` dari default 10 menit ke 30-60 menit sementara waktu, hapus indeks kosong (*zero-doc indices*), dan konversikan ribuan shard kecil menjadi ukuran 30-50 GB via Shrink/Rollover optimization agar master state size mengecil drastis.
12. **Solusi Kasus 2**: Ini adalah perilaku normal *Partially Mounted Snapshot*. Pada eksekusi pertama (cold execution), node `data_frozen` harus mengambil segment dictionary dan doc values via jaringan internet/intranet dari Object Storage (S3 latency). Pada eksekusi kedua (warm execution), blok-blok indeks tersebut sudah berada di dalam local SSD cache node, sehingga dieksekusi secara lokal secepat disk I/O.
13. **Solusi Kasus 3**:
    - *Penyebab 1*: ILM poll interval belum berjalan sejak threshold tercapai (tunggu hingga cycle poll berikutnya).
    - *Penyebab 2*: Penulisan data bypass data stream / write alias (misal: langsung menembak ke backing index tertentu). Verifikasi via `GET _cat/indices` dan `GET _data_stream`.
    - *Penyebab 3*: ILM Policy mengalami error/unrecognized mapping pada index template. Verifikasi status policy via `GET <index>/_ilm/explain`.

---

### 16. Summary

Implementasi Data Tiering dan Index Lifecycle Management (ILM) pada Elasticsearch modern bukan sekadar konfigurasi cron job pembersihan data, melainkan pilar utama rekayasa arsitektur data terdistribusi berskala besar.

Dengan memanfaatkan **Node Roles natif** (`data_hot`, `data_warm`, `data_cold`, `data_frozen`), software engineer dapat memisahkan secara tegas antara sistem throughput I/O tinggi untuk ingestion, komputasi analitik terpadat, hingga pengarsipan dingin. 

Teknologi **Searchable Snapshots** yang diaplikasikan pada tier Cold dan Frozen membawa lompatan efisiensi: memutus korelasi linear antara volume data yang disimpan dengan kebutuhan server fisik lokal. Hasil akhirnya adalah arsitektur Elasticsearch yang tangguh, hemat biaya secara radikal, taat regulasi retensi, dan tahan terhadap degradasi performa seiring bertambahnya data dari gigabyte menuju petabyte.