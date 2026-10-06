# BAB-08-Data-Tiering-Index-Lifecycle-Management: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi teknis, pengujian pemahaman arsitektural, serta panduan hands-on challenge mandiri untuk Chapter 08: Data Tiering & Index Lifecycle Management (ILM) pada Elasticsearch cluster modern.

---

## Bagian 1: Basic Questions (5 Soal & Kunci Jawaban Lengkap)

### Soal 1.1: Apa fungsi utama dari arsitektur Data Tiering (`hot`, `warm`, `cold`, `frozen`) pada Elasticsearch dan bagaimana node attributes dialokasikan?
**Kunci Jawaban & Analisis Teknis:**
Data Tiering membagi node-node dalam cluster Elasticsearch ke dalam tingkatan storage dan compute berdasarkan karakteristik akses data seiring berjalannya waktu:
1. **Hot Tier:** Menangani proses ingestion berkecapatan tinggi (write-heavy) serta query terkini yang sangat intensif (read-heavy). Node hot memerlukan CPU tinggi dan storage berbasis NVMe/SSD cepat.
2. **Warm Tier:** Menangani data time-series yang sudah tidak lagi menerima operasi penulisan (read-only), namun masih di-query secara berkala. Menjalankan optimasi seperti `forcemerge` ke single segment dan replika yang dapat dikurangi.
3. **Cold Tier:** Menampung data yang jarang di-query. Menggunakan node berbiaya storage lebih rendah atau memanfaatkan Searchable Snapshots (tipe full copy / shallow snapshot cache) guna menghemat compute.
4. **Frozen Tier:** Menyimpan data arsip dengan pemanfaatan Searchable Snapshots langsung dari object storage (S3, GCS, MinIO). Node hanya menyediakan cache lokal minimal; index di-mount secara read-only tanpa alokasi persistent disk besar.

Alokasi node dilakukan melalui setting `node.roles` pada `elasticsearch.yml`, contohnya:
```yaml
node.roles: [ data_hot, data_content ]
# atau untuk warm tier:
node.roles: [ data_warm ]
# atau untuk cold tier:
node.roles: [ data_cold ]
# atau untuk frozen tier:
node.roles: [ data_frozen ]
```
Routing shard diatur otomatis oleh Elasticsearch menggunakan setting indeks `index.routing.allocation.include._tier_preference: "data_hot,data_warm,data_cold"`.

---

### Soal 1.2: Apa perbedaan fundamental antara Data Streams dan Index Alias konvensional pada penanganan data append-only time-series?
**Kunci Jawaban & Analisis Teknis:**
- **Index Alias:** Membutuhkan definisi manual untuk write index (`is_write_index: true`) dan satu atau lebih backing indices. Pengelolaan rolling index name (misal: `logs-000001`, `logs-000002`) serta penempatan alias harus didefinisikan secara eksplisit oleh administrator melalui index templates atau alias API.
- **Data Streams:** Abstraksi tingkat tinggi bawaan Elasticsearch khusus untuk data time-series append-only.
  - Setiap dokumen yang diindeks ke data stream **wajib** memiliki field `@timestamp`.
  - Data stream secara otomatis membuat dan mengelola *hidden backing indices* berformat `.ds-<data-stream-name>-<creation-date>-<generation-number>`.
  - Dokumen baru secara otomatis dialihkan ke backing index generasi terbaru sebagai write index.
  - Operasi update dan delete dokumen individual tidak diperbolehkan secara direct document API (harus via `_update_by_query` atau `_delete_by_query`).

---

### Soal 1.3: Bagaimana mekanisme kerja `indices.lifecycle.poll_interval` pada siklus evaluasi ILM?
**Kunci Jawaban & Analisis Teknis:**
ILM dijalankan oleh periodic background task di dalam master node. Setting `indices.lifecycle.poll_interval` (default: `10m` atau 10 menit) menentukan seberapa sering Elasticsearch memeriksa apakah index-index yang diatur oleh lifecycle policy telah memenuhi syarat untuk pindah phase atau menjalankan action berikutnya (misal: memeriksa apakah index size sudah mencapai limit rollover).

Jika dalam pengujian lab atau debugging ingin mempercepat evaluasi trigger rollover/transition, setting ini dapat diturunkan secara dinamis:
```json
PUT _cluster/settings
{
  "transient": {
    "indices.lifecycle.poll_interval": "5s"
  }
}
```
*Catatan Produksi:* Jangan gunakan interval terlalu rendah (seperti `5s`) pada cluster produksi berskala ratusan node dan ribuan index karena akan membebani master node thread pool dan CPU dengan audit metadata cluster state yang konstan.

---

### Soal 1.4: Mengapa action `forcemerge` pada ILM biasanya dipasangkan dengan indeks yang sudah `read-only`?
**Kunci Jawaban & Analisis Teknis:**
`forcemerge` memaksa penggabungan beberapa segment Lucene menjadi sejumlah segment yang lebih sedikit (biasanya `max_num_segments: 1`).
1. **Pembersihan Deleted Documents:** Menghapus dokumen bertanda delete tombstone secara permanen dari segment, sehingga melepaskan disk space dan mengecilkan index memory footprint.
2. **Efisiensi Search:** Mengurangi overhead pencarian karena term dictionary dan query execution hanya perlu menelusuri 1 segment.
3. **Risiko jika Index Writable:** Jika index masih aktif ditulis, indexing baru akan terus memproduksi segment-segment kecil baru, sehingga proses force merge yang memakan I/O disk dan CPU intensif menjadi sia-sia dan memicu penurunan performa cluster drastis. Karena itu, ILM selalu mengeksekusi action `read_only` sebelum `forcemerge`.

---

### Soal 1.5: Apa kegunaan action `shrink` dan batasan shard count yang dapat dikonfigurasi?
**Kunci Jawaban & Analisis Teknis:**
Action `shrink` mengurangi jumlah primary shards dari sebuah index menjadi jumlah yang merupakan faktor pembagi dari jumlah primary shard awal (misal: dari 6 shards menjadi 3, 2, atau 1 shard; atau dari 8 shards menjadi 4, 2, atau 1 shard).
- **Tujuan:** Mengurangi overhead metadata shard per-node pada data lama (over-sharding prevention) dan mengoptimalkan performa I/O.
- **Prasyarat Eksekusi:** Seluruh salinan primary shard atau replika dari index tersebut harus dialokasikan ke tepat satu node terlebih dahulu (`index.routing.allocation.require._name`) dan index dalam keadaan `read_only: true`. ILM menangani alokasi ini secara otomatis sebelum memicu proses shrink.

---

## Bagian 2: Intermediate Questions (5 Soal & Kunci Jawaban Lengkap)

### Soal 2.1: Jelaskan alur eksekusi detail ketika action `rollover` dievaluasi pada sebuah Data Stream!
**Kunci Jawaban & Analisis Teknis:**
Ketika ILM mengevaluasi action `rollover` pada Data Stream:
1. **Evaluasi Threshold:** Master node membandingkan kondisi rollover (`max_primary_shard_size`, `max_age`, `max_docs`, `max_size`) terhadap backing index aktif (`write index`).
2. **Generasi Backing Index Baru:** Jika salah satu ambang batas terpenuhi:
   - Dibuat hidden index baru dengan nama increment generation berikutnya: `.ds-<stream-name>-<timestamp>-<00000x+1>`.
   - Konfigurasi index template dan component templates yang relevan diaplikasikan ke backing index baru ini.
3. **Pengalihan Write Pointer:** Data stream memperbarui referensi internalnya sehingga index baru menjadi penampung eksklusif dokumen masuk baru (`write_index: true`).
4. **Transisi Status Backing Index Lama:** Backing index sebelumnya dicopot dari status write index, statusnya menjadi read-only untuk ingest langsung, dan index tersebut beralih dari status `hot` rollover ke action berikutnya dalam fase hot (atau langsung masuk antrean transisi ke fase `warm` berdasarkan parameter `min_age`).

---

### Soal 2.2: Apa perbedaan fungsional antara `index.lifecycle.origination_date` dan `index.lifecycle.parse_origination_date`? Kapan parameter ini wajib digunakan?
**Kunci Jawaban & Analisis Teknis:**
Secara default, transisi antar fase ILM dihitung berdasarkan waktu pembuatan indeks (`index.creation_date`). Hal ini menimbulkan masalah kritis saat melakukan reindex data historis atau migrasi cluster lama ke cluster baru: indeks log dari 2 tahun lalu yang baru di-reindex hari ini akan dianggap berumur "0 hari" dan tertahan di Hot tier selama berbulan-bulan.
- `index.lifecycle.origination_date`: Digunakan untuk menetapkan timestamp eksplisit (epoch millis) sebagai titik awal kalkulasi umur indeks untuk transisi fase ILM.
- `index.lifecycle.parse_origination_date`: Memberitahu Elasticsearch untuk mengekstrak tanggal asal langsung dari nama indeks berdasarkan format pola penanggalan (misal nama indeks: `logs-2023.01.15-000001`).
- **Kapan Wajib Digunakan:** Wajib digunakan pada skenario reindexing log/metrics historis, pemulihan backup snapshot masa lalu, atau bulk import data arsip, agar ILM langsung memindahkan indeks tersebut ke fase `cold` atau `delete` sesuai tanggal aktual kejadian log, bukan tanggal reindex.

---

### Soal 2.3: Jelaskan arsitektur Searchable Snapshots pada Cold Tier vs Frozen Tier!
**Kunci Jawaban & Analisis Teknis:**
Searchable Snapshots memungkinkan node Elasticsearch membaca data index langsung dari Snapshot Repository (Object Storage seperti AWS S3, GCS, Azure Blob, atau Ceph/MinIO):
1. **Cold Tier (Fully Mounted / Partially Mounted):**
   - Menggunakan mount type `partially_mounted` (default pada ILM cold phase) atau `fully_mounted`.
   - Node cold mengunduh metadata dan sebagian data aktif ke disk cache lokal.
   - Primary shard tetap disinkronkan, namun replika tidak lagi membutuhkan disk terpisah karena snapshot repository bertindak sebagai sumber data pemulihan jika terjadi kegagalan hardware, memangkas storage hingga 50%.
2. **Frozen Tier (Directly Mounted from Blob Storage):**
   - Menggunakan mode `direct` mount index (`partially_mounted` dengan aggressive eviction cache).
   - Node frozen tidak menyimpan copy penuh index pada persistent disk; hanya block index yang sedang disentuh query yang di-cache di storage lokal.
   - Sangat hemat biaya (skalabilitas petabyte storage dengan rasio RAM:Disk hingga 1:1000+), namun memiliki query latency yang lebih tinggi (cold queries memerlukan fetch network dari S3).

---

### Soal 2.4: Bagaimana cara menganalisis dan memperbaiki index yang mengalami status `ILM step [check-rollover-ready] failed` atau `waiting-for-shard-relocation`?
**Kunci Jawaban & Analisis Teknis:**
1. **Diagnosis:**
   Gunakan API ILM Explain untuk melihat state error:
   ```json
   GET <index-name>/_ilm/explain?human=true
   ```
   Cari field `step_info`, `failed_step`, dan `step`.
2. **Akar Masalah Umum:**
   - `check-rollover-ready failed`: Index tidak memiliki alias aktif dengan `is_write_index: true`, atau nama index tidak berakhiran pola numerik 6 digit (`-000001`).
   - `waiting-for-shard-relocation`: Terjadi saat fase warm/cold karena ILM menerapkan `index.routing.allocation.require._tier_preference: "data_warm"`, namun cluster tidak memiliki node bertipe role `data_warm`, atau disk pada node tujuan sudah melampaui `cluster.routing.allocation.disk.watermark.high`.
3. **Remediasi:**
   - Perbaiki kapasitas disk atau tambahkan node tier terkait.
   - Perbaiki alokasi tier atau policy yang salah konfigurasi via `PUT _ilm/policy/<policy-name>`.
   - Picu kembali proses ILM yang macet dengan API retry:
   ```json
   POST <index-name>/_ilm/retry
   ```

---

### Soal 2.5: Mengapa `min_age` pada fase ILM dihitung relatif terhadap waktu rollover dan bukan waktu pembuatan index saat rollover aktif?
**Kunci Jawaban & Analisis Teknis:**
Ketika sebuah index diatur dengan action `rollover` pada fase Hot, siklus hidup index tersebut baru "selesai" di-ingest saat rollover terjadi. 
- Jika `min_age` di fase Warm dikonfigurasi sebesar `7d` dan dihitung dari *creation date*, sebuah index bervolume rendah yang membutuhkan waktu 6 hari untuk mencapai target size rollover akan langsung dipindahkan ke warm tier 1 hari setelah rollover.
- Oleh karena itu, Elasticsearch secara default menghitung `min_age` fase-fase berikutnya (`warm`, `cold`, `frozen`, `delete`) relatif terhadap **rollover date** (tanggal rollover berhasil terjadi), kecuali jika `origination_date` diatur secara manual. Hal ini memastikan data tetap berada di warm tier selama durasi penuh yang diinginkan setelah masa aktif penulisan selesai.

---

## Bagian 3: Skenario Kasus Nyata Produksi (Real-World Production Scenarios)

### Kasus 1: "Master Node OOM & Out of Shards Limit saat Lonjakan Log Security"
* **Latar Belakang:** Tim Security Ops mengalirkan 4 TB log audit/hari dengan 15 microservices berbeda. Setiap service menulis ke Data Stream tersendiri tanpa ILM rollover policy yang tepat (setiap hari dibuat indeks baru dengan 10 primary shard + 1 replika). Dalam 3 bulan, cluster memiliki lebih dari 9.000 shard aktif. Master node mengalami Java Garbage Collection pause parah (>30 detik) dan berujung Out Of Memory (OOM).
* **Root Cause Analysis (RCA):** Over-sharding akut. Ribuan shard berukuran kecil (<1 GB) membebani cluster state metadata di JVM Heap Master Node. Setiap shard Lucene mengonsumsi heap untuk term dictionary, doc values, dan segment headers terlepas dari apakah data tersebut aktif dicari atau tidak.
* **Solusi & Langkah Remediasi Teknis:**
  1. Terapkan ILM Policy berbasis kapasitas shard, bukan berbasis harian statis:
     ```json
     PUT _ilm/policy/security_audit_ilm_policy
     {
       "policy": {
        "phases": {
          "hot": {
            "actions": {
              "rollover": {
                "max_primary_shard_size": "40gb",
                "max_age": "3d"
              }
            }
          },
          "warm": {
            "min_age": "7d",
            "actions": {
              "shrink": { "number_of_shards": 1 },
              "forcemerge": { "max_num_segments": 1 }
            }
          },
          "delete": {
            "min_age": "90d",
            "actions": { "delete": {} }
          }
        }
       }
     }
     ```
  2. Modifikasi template agar primary shard awal cukup 1 atau 2 shard per service.
  3. Lakukan emergency shrink dan merge pada indeks-indeks lampau untuk memotong shard count cluster dari 9.000 menjadi di bawah 1.500 shard.

---

### Kasus 2: "Disk Hot Node 98% (High Disk Watermark Exceeded) Karena ILM Macet"
* **Latar Belakang:** Pada cluster E-Commerce, tim DevOps menerima alert `ClusterBlockException: index [logs-app-000214] blocked by: [TOO_MANY_REQUESTS/12/disk usage exceeded flood-stage watermark]`. Penulisan terhenti total. Padahal, ILM policy sudah diatur untuk memindahkan data ke node warm setelah 2 hari.
* **Root Cause Analysis (RCA):**
  - Ditemukan bahwa ILM step execution pada `logs-app-000214` berstatus `ERROR`.
  - Step yang gagal adalah `forcemerge`. Analisis `_ilm/explain` menunjukkan force merge gagal karena disk hot node sudah menyentuh 90% saat force merge mencoba membuat segment baru sementara segment lama belum dihapus (force merge membutuhkan disk overhead sementara hingga 2x ukuran segment).
  - Karena step `forcemerge` gagal, ILM berhenti di fase hot dan tidak pernah mengeksekusi routing allocation ke warm tier.
* **Solusi & Langkah Remediasi Teknis:**
  1. Nonaktifkan sementara flood-stage block pada cluster:
     ```json
     PUT */_settings
     {
       "index.blocks.read_only_allow_delete": null
     }
     ```
  2. Pindahkan action `forcemerge` ke fase **Warm**, bukan di fase Hot. Biarkan data bermigrasi ke node Warm terlebih dahulu (yang memiliki disk lebih besar dan I/O terisolasi dari proses ingest).
  3. Ubah urutan action pada policy ILM:
     - Hot: Hanya lakukan `rollover`.
     - Warm: Eksekusi `allocate` ke `data_warm`, jalankan `read_only`, lalu jalankan `forcemerge`.
  4. Jalankan `POST logs-app-000214/_ilm/retry` untuk melanjutkan proses migrasi index ke node warm.

---

### Kasus 3: "Biaya Cloud Storage Membengkak 400% Akibat Retensi Log Kepatuhan 1 Tahun"
* **Latar Belakang:** Perusahaan fintech wajib menyimpan transaksi dan log akses selama 365 hari untuk audit PCI-DSS. Semua node Elasticsearch menggunakan SSD AWS EBS gp3 pada Data Hot dan Warm nodes. Biaya disk storage bulanan melonjak tajam hingga puluhan ribu dolar, sementara utilisasi query untuk data di atas 30 hari adalah kurang dari 0.05%.
* **Root Cause Analysis (RCA):** Desain arsitektur penyimpanan homogen. Menyimpan log dingin (cold/frozen) di EBS gp3 aktif dengan alokasi 1 replika ganda (2x storage cost) adalah anti-pattern finansial.
* **Solusi & Langkah Remediasi Teknis:**
  1. Registrasikan Snapshot Repository yang terhubung ke AWS S3 (Standard atau Glacier Instant Retrieval via S3 connector).
  2. Implementasikan Searchable Snapshots pada Cold dan Frozen tier:
     ```json
     PUT _ilm/policy/pci_dss_compliance_policy
     {
       "policy": {
         "phases": {
           "hot": {
             "actions": {
               "rollover": { "max_primary_shard_size": "50gb", "max_age": "7d" }
             }
           },
           "warm": {
             "min_age": "14d",
             "actions": {
               "forcemerge": { "max_num_segments": 1 },
               "allocate": { "number_of_replicas": 1 }
             }
           },
           "cold": {
             "min_age": "30d",
             "actions": {
               "searchable_snapshot": {
                 "snapshot_repository": "my_s3_repository",
                 "force": false
               },
               "allocate": { "number_of_replicas": 0 }
             }
           },
           "frozen": {
             "min_age": "90d",
             "actions": {
               "searchable_snapshot": {
                 "snapshot_repository": "my_s3_repository"
               }
             }
           },
           "delete": {
             "min_age": "365d",
             "actions": { "delete": {} }
           }
         }
       }
     }
     ```
  3. Dampak: Biaya storage terpangkas lebih dari 70% karena data di atas 30 hari tidak memerlukan replika EBS lokal, dan data di atas 90 hari sepenuhnya beroperasi via S3 object storage berbasis query cache.

---

## Bagian 4: Practical Chapter Challenge (Lab Mandiri Komprehensif)

### Skenario Uji Coba:
Anda bertindak sebagai Lead Data Platform Engineer yang bertugas mendesain pipeline retensi data stream transaksi finansial bernama `payment-audit`. Data stream ini harus memiliki ketahanan tinggi, otomatisasi tiering dari Hot ke Warm, penghematan disk melalui shrink & force merge, dan eliminasi otomatis setelah data berumur 30 hari.

### Langkah-Langkah Pengerjaan Hands-On:

#### Langkah 1: Konfigurasi Snapshot Repository Simulasi (fs repository)
Pastikan path `/tmp/es-backup` terdaftar di `path.repo` pada node Elasticsearch, atau gunakan repository mock:
```json
PUT _snapshot/lab_local_backup
{
  "type": "fs",
  "settings": {
    "location": "/tmp/es-backup"
  }
}
```

#### Langkah 2: Buat ILM Lifecycle Policy Terpadu
Konfigurasikan ILM Policy bernama `payment_audit_lifecycle` dengan spesifikasi:
- **Hot Phase:** Rollover jika ukuran primary shard mencapai `100mb` ATAU dokumen berjumlah `5000` ATAU umur mencapai `1d`.
- **Warm Phase:** Aktif `1m` (1 menit untuk simulasi lab) setelah rollover:
  - Read-only diaktifkan.
  - Primary shard di-shrink dari 2 menjadi 1 shard.
  - Force merge ke 1 segment.
  - Alokasikan ke tier `data_warm` atau node attr warm.
- **Delete Phase:** Aktif `5m` setelah rollover, data dihapus permanen.

```json
PUT _ilm/policy/payment_audit_lifecycle
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_primary_shard_size": "100mb",
            "max_docs": 5000,
            "max_age": "1d"
          }
        }
      },
      "warm": {
        "min_age": "1m",
        "actions": {
          "readonly": {},
          "shrink": {
            "number_of_shards": 1
          },
          "forcemerge": {
            "max_num_segments": 1
          }
        }
      },
      "delete": {
        "min_age": "5m",
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

#### Langkah 3: Buat Component Templates & Index Template untuk Data Stream
Buat Component Template untuk mapping dan settings:
```json
PUT _component_template/payment_audit_mappings
{
  "template": {
    "mappings": {
      "properties": {
        "@timestamp": { "type": "date" },
        "transaction_id": { "type": "keyword" },
        "account_id": { "type": "keyword" },
        "amount": { "type": "scaled_float", "scaling_factor": 100 },
        "status": { "type": "keyword" }
      }
    }
  }
}

PUT _component_template/payment_audit_settings
{
  "template": {
    "settings": {
      "index.lifecycle.name": "payment_audit_lifecycle",
      "index.number_of_shards": 2,
      "index.number_of_replicas": 0,
      "index.routing.allocation.include._tier_preference": "data_hot"
    }
  }
}

PUT _index_template/payment_audit_template
{
  "index_patterns": ["payment-audit*"],
  "data_stream": {},
  "composed_of": [
    "payment_audit_mappings",
    "payment_audit_settings"
  ],
  "priority": 500
}
```

#### Langkah 4: Ingestion Data & Validasi State
1. Masukkan dokumen sampel untuk menginisialisasi Data Stream:
```json
POST payment-audit/_doc
{
  "@timestamp": "2026-10-06T05:00:00Z",
  "transaction_id": "TX-990123",
  "account_id": "ACC-7721",
  "amount": 150000.50,
  "status": "SUCCESS"
}
```

2. Periksa backing index yang dibuat:
```json
GET _data_stream/payment-audit
```

3. Simulasikan paksa rollover untuk menguji fase warm:
```json
POST payment-audit/_rollover
```

4. Verifikasi status lifecycle dan step execution secara realtime:
```json
GET .ds-payment-audit-*/_ilm/explain?human=true
```

---

## Bagian 5: Checklist Pemahaman Mandiri (Self-Assessment)

Gunakan checklist evaluasi berikut untuk mengukur kesiapan operasional Anda terkait Data Tiering dan ILM:

- [ ] **Konseptual Roles & Tiers:** Saya memahami perbedaan node roles (`data_hot`, `data_warm`, `data_cold`, `data_frozen`, `data_content`) dan bagaimana routing allocation tier preference bekerja (`index.routing.allocation.include._tier_preference`).
- [ ] **Mekanisme Data Streams:** Saya memahami cara kerja data stream, backing indices berawalan `.ds-`, keharusan field `@timestamp`, serta manipulasi dokumen pada write index vs historical indices.
- [ ] **ILM Phases & Actions Matrix:** Saya mengetahui action apa saja yang legal dan valid di setiap fase:
  - Hot: `rollover`, `searchable_snapshot`, `unfollow`.
  - Warm: `allocate`, `forcemerge`, `readonly`, `shrink`, `migrate`, `downsample`.
  - Cold: `searchable_snapshot`, `allocate`, `readonly`, `migrate`.
  - Frozen: `searchable_snapshot`.
  - Delete: `delete`, `wait_for_snapshot`.
- [ ] **Troubleshooting ILM:** Saya menguasai penggunaan `GET <index>/_ilm/explain`, mengidentifikasi `failed_step`, membaca `step_info`, serta menggunakan command `POST <index>/_ilm/retry`.
- [ ] **Cost & Capacity Engineering:** Saya mampu mengkalkulasi penghematan storage melalui kombinasi *shrunk shards*, *single segment force merge*, dan *Searchable Snapshots* berbasis Object Storage (AWS S3/GCS/MinIO).
