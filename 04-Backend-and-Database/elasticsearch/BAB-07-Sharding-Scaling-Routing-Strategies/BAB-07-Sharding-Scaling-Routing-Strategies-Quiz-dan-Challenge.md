# BAB-07-Sharding-Scaling-Routing-Strategies: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang untuk menguji, memvalidasi, dan memperdalam pemahaman arsitektur terdistribusi Elasticsearch, khususnya mekanisme sharding, replikasi, strategi custom routing, penanganan shard sizing, mitigasi hotspotting, serta teknik cluster rebalancing dan scaling.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Formula Dasar Penentuan Shard Tujuan
**Pertanyaan:**  
Jelaskan formula bawaan Elasticsearch untuk menentukan primary shard tujuan saat sebuah dokumen diindeks! Mengapa jumlah primary shard pada sebuah index tidak dapat diubah secara langsung secara in-place tanpa reindexing atau split API?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Formula Routing Bawaan:**
```text
shard_num = murmur3(routing_value) % number_of_primary_shards
```
Secara default, `routing_value` adalah `_id` dari dokumen.

**Alasan Tidak Bisa Diubah In-place:**  
Operasi modulo (`% number_of_primary_shards`) sangat bergantung pada nilai pembagi tetap (`number_of_primary_shards`). Jika jumlah primary shard diubah secara sembarangan di tempat (misalnya dari 5 menjadi 6), maka hasil hash modulo untuk dokumen yang sama akan berubah drastis:
- Dokumen dengan ID `X` yang awalnya jatuh di Shard 2 mungkin akan jatuh di Shard 4 setelah jumlah shard berubah.
- Akibatnya, Elasticsearch tidak akan dapat menemukan dokumen lama berdasarkan ID saat operasi `GET` atau `UPDATE`, memicu duplikasi data dan korupsi konsistensi pencarian.
- Untuk mengubah jumlah primary shard, indeks harus di-reindex ke indeks baru, atau menggunakan `_split` API (yang mensyaratkan kelipatan faktor faktorisasi) atau `_shrink` API.
</details>

---

### Soal 1.2: Perbedaan Primary Shard vs Replica Shard
**Pertanyaan:**  
Apa perbedaan mendasar peran primary shard dan replica shard dalam lifecycle penulisan (*indexing*) dan pembacaan (*search/read*) di Elasticsearch?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

- **Proses Penulisan (Indexing):**
  - Primary shard bertindak sebagai koordinator lokal yang memvalidasi struktur dokumen, menghasilkan versi dokumen (`_version` / `_seq_no`), mengeksekusi operasi secara lokal ke Lucene index dan translog.
  - Setelah berhasil di primary, operasi direplikasi secara paralel ke semua active replica shard (dalam in-sync replica set). Replica hanya mengeksekusi instruksi yang telah divalidasi oleh primary.
- **Proses Pembacaan (Search/Read):**
  - Search request dapat dilayani secara seimbang (round-robin) oleh primary shard maupun replica shard.
  - Replica shard secara linier meningkatkan read throughput (QPS/IOPS) dan menyediakan failover otomatis jika node host primary mengalami crash atau unreachability (High Availability).
</details>

---

### Soal 1.3: Rekomendasi Shard Size
**Pertanyaan:**  
Berapa ukuran shard (*shard size*) yang direkomendasikan secara resmi oleh Elastic untuk beban kerja logging/time-series vs transactional/search query-intensive? Apa dampak teknis jika ukuran shard terlalu kecil (< beberapa ratus MB) atau terlalu besar (> 60-80 GB)?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Rekomendasi Ukuran:**
- **Time-series / Logs / Metrics:** 30 GB hingga 50 GB per shard.
- **General Search / E-Commerce / Low Latency Queries:** 10 GB hingga 30 GB per shard.

**Dampak Shard Terlalu Kecil (Oversharding):**
- Overhead metadata cluster state di Master node membengkak karena setiap shard memiliki footprint memori (Lucene segment metadata, file handles, buffer).
- Eksekusi search query terfragmentasi ke ribuan thread queue kecil, menyebabkan context switching dan CPU overhead tinggi di node koordinator.

**Dampak Shard Terlalu Besar (> 60-80 GB):**
- Waktu cluster recovery dan node rebalancing sangat lama saat node fail (resyncing puluhan GB melalui jaringan).
- Operasi merge segment besar Lucene membutuhkan I/O tinggi dan rentan throttling.
- Heap memory Lucene field data and filter cache mudah exhausted, memperbesar risiko OutOfMemory (OOM).
</details>

---

### Soal 1.4: Definisi Custom Routing
**Pertanyaan:**  
Apa yang dimaksud dengan custom routing (`?routing=...`) pada Elasticsearch, dan bagaimana pengaruhnya terhadap eksekusi search request dibandingkan standard routing?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Definisi:**  
Custom routing adalah mekanisme override nilai masukan fungsi hash routing menggunakan nilai atribut tertentu (misalnya `tenant_id`, `user_id`, atau `country_code`) alih-alih nilai default `_id`.

**Perbedaan Eksekusi Query:**
- **Standard Routing (Scatter-Gather):** Query tanpa routing harus dikirim ke **semua shard** (atau minimal satu copy dari setiap shard primary/replica) dalam index. Node koordinator mengirim search request ke N shard, mengumpulkan hasilnya, menggabungkannya, lalu menyortirnya.
- **Custom Routing (Direct Shard Execution):** Koordinator menghitung hash routing dan mengarahkan search request **hanya ke 1 shard tunggal** tempat data entitas tersebut berada. Ini mengeliminasi 80-95% network round-trip dan query execution thread pool across cluster.
</details>

---

### Soal 1.5: Shard Allocation Awareness
**Pertanyaan:**  
Apa fungsi konfigurasi `cluster.routing.allocation.awareness.attributes` di Elasticsearch dan arsitektur apa yang diuntungkannya?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Fungsi:**  
Fitur ini memberitahu master node mengenai topologi fisik hardware/infrastruktur tempat instance Elasticsearch berjalan (misalnya rack ID, server room, atau availability zone / cloud region).

**Keuntungan:**
- Mencegah primary shard dan replica-nya dialokasikan pada rack atau Availability Zone (AZ) yang sama.
- Jika satu rack atau AZ mengalami pemadaman total (power outage / network split), replica shard di rack/AZ lain tetap tersedia, menjaga ketersediaan cluster 100% tanpa data loss.
- Mendukung zone-aware search routing (`cluster.routing.allocation.awareness.force`) untuk meminimalkan cross-AZ data egress latency and cost.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Menghitung Target Primary Shards untuk Write-Heavy Time-Series
**Pertanyaan:**  
Sebuah aplikasi perbankan memproduksi log transaksi audit sebesar 1,2 TB per hari (uncompressed raw data di Lucene). Index dibuat harian (*daily indices*) dengan konfigurasi 1 replica. Berapa jumlah primary shard dan replica shard yang ideal untuk index setiap harinya? Jelaskan perhitungannya!

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Perhitungan:**
1. **Target Ukuran Shard:** Untuk beban time-series/logging, ukuran ideal shard adalah 30 GB - 50 GB. Kita gunakan target median **40 GB per primary shard**.
2. **Kalkulasi Primary Shards:**
   $$\text{Primary Shards} = \frac{\text{Total Volume Harian}}{\text{Target Shard Size}} = \frac{1200\text{ GB}}{40\text{ GB}} = 30\text{ primary shards}$$
3. **Kalkulasi Replicas:**
   - Ditentukan 1 replica (`number_of_replicas: 1`).
   - Berarti ada 30 replica shards tambahan.
   - Total shards per hari = 30 primary + 30 replica = 60 shards.
4. **Total Disk Footprint:**
   $$1200\text{ GB} \times (1 + 1\text{ replica}) = 2400\text{ GB} = 2,4\text{ TB/hari}$$
5. **Kesimpulan Arsitektur:** Set index settings harian ke `number_of_shards: 30` dan `number_of_replicas: 1`. Pastikan kapasitas node data memadai untuk menampung minimal 60 shards per hari retention window.
</details>

---

### Soal 2.2: Fenomena Hotspotting Akibat Custom Routing
**Pertanyaan:**  
Mengapa penggunaan custom routing berbasis `tenant_id` pada sistem SaaS multi-tenant berisiko tinggi menyebabkan *hotspotting*, dan strategi apa yang dapat diterapkan untuk memitigasinya tanpa meninggalkan custom routing sepenuhnya?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Penyebab Hotspotting:**  
Dalam model SaaS, volume data per tenant mengikuti distribusi *Power Law* (Pareto 80/20). Jika Tenant Enterprise raksasa (misal: 10 juta events/hari) dan ribuan Tenant UMKM (misal: 100 events/hari) di-route murni berdasarkan `tenant_id`:
- Shard tempat Tenant Enterprise berada akan menerima beban CPU write/read dan disk storage 100x lebih besar daripada shard lain.
- Node yang menampung shard tersebut menjadi bottleneck (*hot node*), sementara node lain menganggur (*idle*).

**Strategi Mitigasi:**
1. **Routing Key Partitioning (`index.routing_partition_size`):**  
   Elasticsearch menyediakan setting `routing_partition_size`. Jika di-set misalnya `3`, hash routing tidak lagi menunjuk ke 1 shard tunggal, melainkan disebar merata ke subset 3 shard:
   $$\text{shard} = (\text{hash}(\text{routing}) + \text{hash}(\text{id}) \% \text{partition\_size}) \% \text{num\_shards}$$
2. **Dedicated Index Tiering:** Pisahkan tenant raksasa ke index tersendiri (*Tier 1 Index*) dengan kapasitas shard lebih besar, sementara tenant long-tail disatukan dalam shared multi-tenant index.
3. **Compound Routing Key:** Gabungkan tenant dengan dimensi waktu atau sub-entitas (misal: `tenant123_2026_w14`).
</details>

---

### Soal 2.3: Shrink API vs Split API Internal Mechanics
**Pertanyaan:**  
Jelaskan prasyarat teknis dan mekanisme internal sebelum indeks dapat dioperasikan menggunakan `_shrink` API atau `_split` API!

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**A. Prasyarat `_shrink` API (Mengecilkan jumlah shard, misal dari 15 ke 3):**
1. Jumlah target shard harus merupakan faktor pembagi dari jumlah shard asal (misal 15 -> 5, 3, atau 1).
2. Indeks harus diset ke mode read-only: `index.blocks.write: true`.
3. Seluruh salinan primary shard atau replica shard dari indeks tersebut harus direlokasi ke **satu node fisik yang sama** (`index.routing.allocation.require._name`).
4. Indeks shrink memanfaatkan *hard-links* pada filesystem level OS Linux, sehingga pembuatan indeks baru terjadi dalam hitungan detik tanpa duplikasi data byte mentah.

**B. Prasyarat `_split` API (Membesarkan jumlah shard, misal dari 3 ke 9):**
1. Indeks asal sejak awal dibuat harus memiliki setting `index.number_of_routing_shards` (faktor kelipatan split).
2. Jumlah shard target harus merupakan kelipatan eksak dari shard awal (misal 3 -> 6, 9, 12).
3. Indeks harus diset ke mode read-only: `index.blocks.write: true`.
4. Sama seperti shrink, split memanfaatkan hard links Lucene segments dan memilah doc term internal berdasarkan bit routing shards.
</details>

---

### Soal 2.4: Mekanisme Search Request: Query Phase vs Fetch Phase
**Pertanyaan:**  
Jelaskan langkah-langkah detail alur eksekusi pencarian pada standard search (scatter-gather) dalam tahap *Query Phase* dan *Fetch Phase*! Mengapa parameter `size: 1000` dengan `from: 50000` (deep pagination) sangat merusak performa cluster?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Alur Kerja 2-Phase:**
1. **Query Phase:**
   - Node koordinator menerima request pencarian.
   - Koordinator memancarkan query ke 1 copy shard (primary atau replica) dari setiap shard group.
   - Setiap shard mengeksekusi query lokal, membangun priority queue lokal berukuran `from + size` (hanya doc ID dan score sorting, tanpa `_source`).
   - Setiap shard mengembalikan list sort/score doc ID tersebut ke node koordinator.
2. **Fetch Phase:**
   - Koordinator menggabungkan (*merge-sort*) semua priority queue dari shard-shard tadi, lalu memilih top `size` dokumen final.
   - Koordinator mengirim request fetch dokumen (`_source`) spesifik hanya ke shard-shard yang memegang dokumen pemenang.
   - Dokumen dikembalikan ke koordinator, disusun, dan dikirim ke client.

**Bahaya Deep Pagination (`from: 50000, size: 1000`):**
- Jika index memiliki 10 shard, setiap shard harus mengalokasikan priority queue di heap memory sebanyak $50000 + 1000 = 51000$ dokumen.
- Total $51000 \times 10 = 510000$ entri ditransmisikan عبر internal network ke koordinator.
- Koordinator harus memproses dan menyortir setengah juta entri di memory hanya untuk membuang 50.000 pertama dan mengembalikan 1.000 dokumen. Ini berisiko tinggi memicu High GC pause dan Out of Memory (OOM). Solusi yang benar adalah menggunakan `search_after` atau `point_in_time` (PIT).
</details>

---

### Soal 2.5: Cluster Balancing dan Throttling Settings
**Pertanyaan:**  
Ketika satu node baru ditambahkan ke cluster produksi, Elasticsearch secara otomatis menjalankan auto-rebalancing. Parameter setting apa saja yang mengontrol agresi pergerakan shard antar node agar tidak mengganggu query latency aplikasi yang sedang berjalan?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

Parameter kunci untuk mengontrol rebalancing concurrency dan throughput I/O:
1. `cluster.routing.allocation.cluster_concurrent_rebalance`:  
   Menentukan batas maksimum shard relokasi concurrent across cluster secara keseluruhan (default biasanya 2).
2. `cluster.routing.allocation.node_concurrent_incoming_recoveries`:  
   Batas shard recovery yang dapat masuk (*inbound*) secara paralel pada satu target node.
3. `cluster.routing.allocation.node_concurrent_outgoing_recoveries`:  
   Batas shard recovery yang dapat dikirim (*outbound*) secara paralel dari satu source node.
4. `indices.recovery.max_bytes_per_sec`:  
   Rate limiter bandwidth transfer network/disk I/O untuk proses pemindahan shard (misal dibatasi ke `100mb` atau `250mb` pada jaringan 10GbE agar tidak menghabiskan total link capacity).
5. Bobot kalkulasi rebalance diatur oleh:
   - `cluster.routing.allocation.balance.shard` (faktor jumlah shard per node).
   - `cluster.routing.allocation.balance.index` (faktor jumlah shard dari index yang sama per node).
   - `cluster.routing.allocation.balance.threshold` (toleransi deviasi minimum sebelum rebalancing terpicu).
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 3.1: "Cluster Red Alert: Massive Unassigned Shards Saat Peak Traffic"

#### Latar Belakang Masalah
Tim platform engineering marketplace tiba-tiba menerima alert PagerDuty jam 14:00 saat flash sale. Status cluster Elasticsearch berubah menjadi **RED**. Analisis awal menunjukkan 42 unassigned primary shards pada indeks transaksi harian. CPU usage pada 3 data node melonjak ke 98%, dan search query response time melambat dari 40ms menjadi 12.000ms.

```text
Cluster Health: RED
Active Primary Shards: 210
Unassigned Shards: 84 (42 Primary, 42 Replica)
Node Status: data-node-04 & data-node-07 status DEAD / DISCONNECTED
```

#### Analisis Akar Masalah (Root Cause)
1. **Oversharding & Heap Exhaustion:** Indeks transaksi flash sale dikonfigurasi dengan 60 primary shards dan 2 replica pada 8 data nodes (masing-masing 32 GB RAM, 16 GB JVM Heap).
2. **GC Pause Spiral:** Beban write request masif memicu concurrent segment merge besar. Node `data-node-04` dan `07` mengalami Stop-the-World garbage collection pause > 35 detik.
3. **Node Ejection:** Master node menganggap node yang mengalami pause panjang tersebut mati karena gagal heartbeat (`discovery.zen.fd.ping_timeout` / transport keepalive breached). Master mencoret node tersebut dan mencoba melakukan failover/rebalancing massal.
4. **Cascading Failure:** Pemindahan 84 shard secara simultan membebani node lain dengan transfer I/O masif, menyebabkan node-node yang tersisa ikut mengalami throttling dan spike latency.

#### Solusi Langkah Demi Langkah & Mitigasi

**Langkah 1: Menstabilkan Cluster Segera (Pencegahan Throttling Relokasi Shard)**
Turunkan konkurensi alokasi dinamis sementara melalui Cluster Update Settings API agar node yang hidup tidak tumbang:
```json
PUT /_cluster/settings
{
  "transient": {
    "cluster.routing.allocation.enable": "primaries",
    "cluster.routing.allocation.node_concurrent_incoming_recoveries": 1,
    "cluster.routing.allocation.node_concurrent_outgoing_recoveries": 1,
    "indices.recovery.max_bytes_per_sec": "40mb"
  }
}
```

**Langkah 2: Investigasi Alasan Unassigned Shard**
Gunakan Allocation Explain API untuk melihat penyebab pasti penolakan alokasi:
```json
GET /_cluster/allocation/explain
{
  "index": "transactions-2026-10-06",
  "shard": 3,
  "primary": true
}
```

**Langkah 3: Pulihkan Node Terputus Tanpa Re-sync Data Penuh**
Jika disk pada node 04 dan 07 masih utuh, restart service Elasticsearch pada kedua node tersebut dengan GC tuning optimal (atau alokasi memory swap disable: `bootstrap.memory_lock: true`). Begitu node bergabung kembali, master akan menemukan data shard lokal dan mengaktifkannya via fast recovery tanpa copy lintas jaringan.

**Langkah 4: Normalisasi dan Mitigasi Jangka Panjang**
- Ubah kembali alokasi ke normal:
  ```json
  PUT /_cluster/settings
  {
    "transient": {
      "cluster.routing.allocation.enable": "all"
    }
  }
  ```
- Evaluasi sizing: Turunkan jumlah primary shard untuk indeks harian berikutnya menjadi 12 shard (sesuai volume real data), bukan 60 shard.

---

### Skenario 3.2: "Search Latency Anomaly: The Noisy Neighbor Tenant"

#### Latar Belakang Masalah
Platform B2B CRM mengindeks 50.000 tenant ke dalam single multi-tenant index `crm-leads` (30 primary shards). Seluruh query menggunakan custom routing `?routing={tenant_id}`.  
Secara periodik setiap pagi jam 09:00, tenant-tenant kecil mengeluhkan search timeout. Namun, metrik monitoring menunjukkan bahwa dari 10 data nodes, hanya **1 node (data-node-02)** yang mengalami disk read queue 100% dan CPU saturation, sementara 9 node lainnya memiliki utilisasi CPU di bawah 15%.

#### Analisis Akar Masalah (Root Cause)
1. **Analisis Distribusi Data Shard:**
   Dilakukan inspeksi dokumen per shard:
   ```text
   Shard 0: 420.000 docs
   Shard 1: 390.000 docs
   Shard 2 (di data-node-02): 18.500.000 docs  <--- HOT SHARD
   Shard 3: 410.000 docs
   ...
   ```
2. **Karakteristik Tenant:**  
   Tenant ID `tenant_megacorp` (klien enterprise terbesar) dan `tenant_bigbank` ternyata kebetulan menghasilkan hash modulo yang sama (`murmur3(tenant_id) % 30 = 2`).
3. Akibatnya, kedua raksasa tersebut tinggal di Shard 2 pada `data-node-02`. Saat kedua perusahaan menjalankan cron job sinkronisasi lead di pagi hari, shard 2 dihantam ratusan query berat bersamaan, melumpuhkan seluruh tenant kecil lain yang kebetulan dialokasikan ke Shard 2.

#### Solusi Solutif Arsitektur

**Solusi 1: Partisi Routing Keys (`index.routing_partition_size`)**
Untuk indeks baru, aktifkan partisi routing sehingga 1 tenant disebar ke subset shard, bukan 1 shard tunggal:
```json
PUT /crm-leads-v2
{
  "settings": {
    "number_of_shards": 30,
    "number_of_replicas": 1,
    "index.routing_partition_size": 3
  }
}
```

**Solusi 2: Index Isolasi untuk Large Enterprise Tenant (Tenant VIP Segregation)**
1. Buat dedicated index untuk tenant raksasa: `crm-leads-tenant-megacorp` dengan shard sizing khusus (misal 5 primary shards terpisah).
2. Buat index alias abstraksi pada level aplikasi:
   - Tenant kecil query ke alias: `crm-leads-general` dengan `?routing={tenant_id}`.
   - Tenant enterprise query ke alias: `crm-leads-vip-megacorp` yang mengarah langsung ke dedicated index.
3. Node Allocation Filtering: Pin tenant enterprise index ke pool server berkinerja tinggi (NVMe storage) menggunakan shard allocation filtering:
   ```json
   PUT /crm-leads-tenant-megacorp/_settings
   {
     "index.routing.allocation.include.node_tier": "vip-nodes"
   }
   ```

---

### Skenario 3.3: "Disk Skew & Watermark Crisis Saat Migrasi Data"

#### Latar Belakang Masalah
Sebuah cluster 5 node sedang menerima migrasi historical dataset 4 TB. Menjelang 70% proses migrasi, master node tiba-tiba menolak write index operations pada seluruh node (`ClusterBlockException[blocked by: [FORBIDDEN/12/index read-only / allow delete (api)]]`).  
Inspeksi storage menunjukkan:
- `node-01`: 85% disk used
- `node-02`: 83% disk used
- `node-03`: **95.2% disk used** (Trigger flood-stage watermark!)
- `node-04`: 62% disk used
- `node-05`: 59% disk used

#### Analisis Akar Masalah (Root Cause)
1. **Pemicu Read-Only Lock:**  
   Default disk watermarks Elasticsearch:
   - Low Watermark (85%): Berhenti mengalokasikan shard baru ke node ini.
   - High Watermark (90%): Mencoba merelokasi shard dari node ini ke node lain.
   - Flood Stage Watermark (95%): Mengubah seluruh index yang memiliki shard di node tersebut menjadi **READ-ONLY** untuk melindungi integritas sistem operasi dan mencegah korupsi database.
2. **Penyebab Disk Skew:**
   - Shard allocation balancer sebelumnya hanya memperhitungkan *jumlah shard* per node (`balance.shard`), bukan *bobot ukuran disk* masing-masing shard.
   - Beberapa shard berukuran 75 GB terkonsentrasi di `node-03`, sedangkan `node-04` dan `node-05` hanya menampung shard-shard kecil berukuran 5 GB.

#### Solusi Pemulihan & Penyeimbangan Kembali

**Langkah 1: Nonaktifkan Read-Only Block Secara Darurat**
Bebaskan ruang sementara (jika memungkinkan) atau naikkan flood stage threshold sementara jika sisa disk fisik absolut masih aman:
```json
PUT /_cluster/settings
{
  "transient": {
    "cluster.routing.allocation.disk.watermark.low": "88%",
    "cluster.routing.allocation.disk.watermark.high": "93%",
    "cluster.routing.allocation.disk.watermark.flood_stage": "96%"
  }
}
```
Lepaskan read-only block pada index yang terkunci:
```json
PUT /*/_settings
{
  "index.blocks.read_only_allow_delete": null
}
```

**Langkah 2: Relokasi Shard Raksasa Secara Manual dari Node Penuh**
Pindahkan shard terbesar dari `node-03` ke `node-05`:
```json
POST /_cluster/reroute
{
  "commands": [
    {
      "move": {
        "index": "historical-data-2024",
        "shard": 4,
        "from_node": "node-03",
        "to_node": "node-05"
      }
    }
  ]
}
```

**Langkah 3: Mitigasi Permanen Berbasis Ukuran Disk**
Aktifkan perhitungan alokasi berbasis disk space dan atur watermark berbasis kapasitas gigabyte absolut (lebih aman untuk disk multi-terabyte):
```json
PUT /_cluster/settings
{
  "persistent": {
    "cluster.routing.allocation.disk.threshold_enabled": true,
    "cluster.routing.allocation.disk.watermark.low": "150gb",
    "cluster.routing.allocation.disk.watermark.high": "80gb",
    "cluster.routing.allocation.disk.watermark.flood_stage": "30gb"
  }
}
```

---

## Bagian 4: Practical Chapter Challenge

### Tantangan Laboratorium: Multi-Tenant Sharding, Custom Routing, dan Shrink Optimization

Anda diminta menyimulasikan siklus penuh pengelolaan indeks multi-tenant e-commerce dengan custom routing, menguji scatter-gather vs direct shard routing, lalu mengecilkan indeks tersebut menggunakan `_shrink` API.

#### Persyaratan Challenge:
1. Buat index template bernama `ecommerce_orders_template` untuk indeks `orders-*`.
2. Atur mapping agar field `merchant_id` dijadikan routing mandatory (`_routing: { "required": true }`).
3. Buat indeks `orders-2026.10` dengan 4 primary shards dan 1 replica.
4. Masukkan 4 dokumen transaksi dengan 2 `merchant_id` berbeda (`merchant_alpha` dan `merchant_beta`).
5. Lakukan verifikasi routing menggunakan query `_search` dengan parameter `explain: true` dan profile API untuk memverifikasi jumlah shard yang dilibatkan.
6. Jalankan prosedur Shrink Index untuk mereduksi indeks `orders-2026.10` dari 4 primary shard menjadi 2 primary shard (`orders-2026.10-shrunk`).

---

### Solusi & Jawaban Langkah-demi-Langkah

#### Langkah 1: Pembuatan Index Template dengan Mandatory Routing
```json
PUT /_index_template/ecommerce_orders_template
{
  "index_patterns": ["orders-*"],
  "template": {
    "settings": {
      "number_of_shards": 4,
      "number_of_replicas": 1
    },
    "mappings": {
      "_routing": {
        "required": true
      },
      "properties": {
        "order_id": { "type": "keyword" },
        "merchant_id": { "type": "keyword" },
        "total_amount": { "type": "double" },
        "created_at": { "type": "date" }
      }
    }
  }
}
```

#### Langkah 2: Inisialisasi Indeks dan Ingest Data dengan Routing
```bash
# Ingest Dokumen 1 (Merchant Alpha)
PUT /orders-2026.10/_doc/ord-101?routing=merchant_alpha
{
  "order_id": "ord-101",
  "merchant_id": "merchant_alpha",
  "total_amount": 250000.0,
  "created_at": "2026-10-06T10:00:00Z"
}

# Ingest Dokumen 2 (Merchant Alpha)
PUT /orders-2026.10/_doc/ord-102?routing=merchant_alpha
{
  "order_id": "ord-102",
  "merchant_id": "merchant_alpha",
  "total_amount": 175000.0,
  "created_at": "2026-10-06T10:15:00Z"
}

# Ingest Dokumen 3 (Merchant Beta)
PUT /orders-2026.10/_doc/ord-201?routing=merchant_beta
{
  "order_id": "ord-201",
  "merchant_id": "merchant_beta",
  "total_amount": 540000.0,
  "created_at": "2026-10-06T10:30:00Z"
}

# Ingest Dokumen 4 (Merchant Beta)
PUT /orders-2026.10/_doc/ord-202?routing=merchant_beta
{
  "order_id": "ord-202",
  "merchant_id": "merchant_beta",
  "total_amount": 90000.0,
  "created_at": "2026-10-06T11:00:00Z"
}
```

*Catatan:* Jika Anda mencoba melakukan PUT tanpa parameter `?routing=...`, Elasticsearch akan menolak request dengan status `400 Bad Request: routing is required for [orders-2026.10]`.

#### Langkah 3: Eksekusi Direct Routing Query & Observasi Shard Hit
Jalankan search request khusus untuk `merchant_alpha`:
```json
GET /orders-2026.10/_search?routing=merchant_alpha
{
  "query": {
    "match_all": {}
  }
}
```

**Hasil Response Payload:**
```json
{
  "_shards": {
    "total": 1,
    "successful": 1,
    "skipped": 0,
    "failed": 0
  },
  "hits": {
    "total": {
      "value": 2,
      "relation": "eq"
    },
    "hits": [ ... ]
  }
}
```
*Perhatikan:* Pada bagian `_shards.total`, nilainya adalah **1**, membuktikan bahwa query langsung tertuju pada shard tempat data `merchant_alpha` disimpan, tanpa membuang siklus resource pada 3 shard lainnya.

#### Langkah 4: Prosedur Shrinking Index Menjadi 2 Primary Shards

**4a. Persiapkan index menjadi read-only dan relokasikan salinan shard ke 1 node:**
```json
PUT /orders-2026.10/_settings
{
  "settings": {
    "index.blocks.write": true,
    "index.routing.allocation.require._name": "data-node-01"
  }
}
```

**4b. Tunggu hingga status relokasi green:**
```json
GET /_cluster/health/orders-2026.10?wait_for_no_relocating_shards=true
```

**4c. Eksekusi Shrink API ke indeks baru dengan 2 shards:**
```json
POST /orders-2026.10/_shrink/orders-2026.10-shrunk
{
  "settings": {
    "index.number_of_shards": 2,
    "index.number_of_replicas": 1,
    "index.routing.allocation.require._name": null,
    "index.blocks.write": null
  }
}
```

**4d. Verifikasi Shard Count Index Baru:**
```json
GET /_cat/shards/orders-2026.10-shrunk?v&h=index,shard,prirep,state,docs,store,node
```
Output akan menunjukkan indeks `orders-2026.10-shrunk` kini memiliki shard `0` dan `1` (masing-masing 1 primary dan 1 replica) dengan seluruh data 4 dokumen tetap utuh tanpa data loss.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar centang berikut untuk mengukur kesiapan Anda dalam arsitektur sharding dan scaling Elasticsearch di tingkat produksi:

- [ ] **Formula Routing & Algoritma:** Memahami cara kerja hash `murmur3(routing) % primary_shards` dan mengapa primary shards tidak bisa bertambah/berkurang sembarangan secara dinamis.
- [ ] **Kapasitas Sizing Ideal:** Mampu menentukan kalkulasi shard size (30-50 GB untuk logging, 10-30 GB untuk search OLTP) dan menghindari jebakan oversharding.
- [ ] **Scatter-Gather vs Targeted Search:** Mengetahui perbedaan performa internal (network hop, queue serialization, heap memory) antara standard query vs custom routing query.
- [ ] **Mitigasi Skew Data:** Memahami implementasi `index.routing_partition_size` dan arsitektur tiering khusus untuk tenant high-volume.
- [ ] **Shrink, Split, dan Rollover Lifecycle:** Menguasai syarat teknis `_shrink` (read-only, co-located copy di single node) dan `_split` API (`number_of_routing_shards`).
- [ ] **Cluster Watermark Safeguard:** Memahami ambang batas Low (85%), High (90%), dan Flood Stage (95%), serta cara melepas lock `read_only_allow_delete`.
- [ ] **Zone & Rack Awareness:** Mampu merancang konfigurasi cluster multi-AZ menggunakan `cluster.routing.allocation.awareness.attributes` agar cluster tahan terhadap bencana fisik hardware.
- [ ] **Rebalancing Controls:** Mampu mengonfigurasi `indices.recovery.max_bytes_per_sec` dan batas concurrent recoveries agar rebalance tidak mengorbankan Service Level Objective (SLO) aplikasi.
