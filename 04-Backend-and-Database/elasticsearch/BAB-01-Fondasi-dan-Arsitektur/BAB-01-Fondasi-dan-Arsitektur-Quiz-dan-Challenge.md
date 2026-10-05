# BAB-01-Fondasi-dan-Arsitektur: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai evaluasi mandiri komprehensif untuk menguji pemahaman konseptual, arsitektural, dan operasional Elasticsearch tingkat produksi berdasarkan materi pada Modul 01 dan Modul 02.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Peran Node dan Quorum Master
**Pertanyaan:**
Pada kluster Elasticsearch multi-node modern (v7.x+), mengapa konfigurasi node dedicated master-eligible minimal berjumlah 3 node fisik/instance terpisah, bukan 2 node? Jelaskan mekanisme pemilihan master dan bagaimana quorum mencegah kondisi *split-brain*.

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

**Jawaban:**
Konfigurasi minimal 3 node master-eligible diperlukan untuk memenuhi formula konsensus quorum:
$$\text{Quorum} = \left\lfloor \frac{N}{2} \right\rfloor + 1$$
Di mana $N$ adalah jumlah node master-eligible. 
- Jika $N = 2$, quorum yang dibutuhkan adalah $\lfloor 2/2 \rfloor + 1 = 2$. Artinya, kedua node harus saling terhubung. Jika terjadi pemisahan jaringan (*network partition*), masing-masing partisi hanya memiliki 1 node ($1 < 2$), sehingga kluster lumpuh total (tidak ada partisi yang bisa membentuk quorum).
- Jika $N = 3$, quorum adalah $\lfloor 3/2 \rfloor + 1 = 2$. Jika terjadi partisi jaringan (misal partisi A berisi 2 node dan partisi B berisi 1 node), partisi A memiliki mayoritas suara (2 node) dan dapat memilih master baru secara sah serta terus melayani pembaruan *cluster state*, sementara partisi B mengisolasi diri.
- Hal ini mencegah *split-brain*, yaitu kondisi ketika dua node berbeda menganggap dirinya sebagai master aktif secara simultan dan menulis status kluster yang saling berlawanan, yang berakibat fatal pada kerusakan (*corruption*) data metadata dan routing.
</details>

---

### Soal 1.2: Anatomi Shard dan Mesin Lucene
**Pertanyaan:**
Apa hubungan struktural antara Index Elasticsearch, Shard, dan Lucene Index? Mengapa dokumen yang telah di-commit ke Lucene Segment bersifat *immutable* (tidak dapat diubah)?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

**Jawaban:**
1. **Hubungan Struktural:**
   - **Elasticsearch Index** adalah abstraksi logis (namespace) yang mengelompokkan data.
   - Index logis tersebut dipartisi secara horizontal menjadi satu atau lebih **Shards** (Primary & Replica).
   - Setiap individual shard di Elasticsearch adalah sebuah **instansi penuh Apache Lucene Index**.
   - Setiap Lucene Index terdiri dari kumpulan file biner yang disebut **Lucene Segments**.
2. **Alasan Immutability Lucene Segment:**
   - **Concurrency Control & Lock-Free Read:** Karena segment tidak pernah dimodifikasi di tempat (*in-place*), operasi pencarian tidak memerlukan penguncian memori (*locking*), sehingga throughput pembacaan sangat tinggi.
   - **Cache Friendliness:** OS filesystem cache dapat menampung data segment secara permanen tanpa risiko cache invalidation parsial.
   - **Inverted Index Compression:** Kompresi postings list (seperti FST - Finite State Transducers dan bit-packing) dapat dioptimalkan secara agresif karena struktur struktur data tidak akan bergeser.
   - Operasi *update* sebenarnya adalah operasi penandaan dokumen lama di file `.del` (soft delete) diikuti penulisan dokumen baru ke segment baru.
</details>

---

### Soal 1.3: Siklus Translog dan Refresh vs Flush
**Pertanyaan:**
Secara default, `refresh_interval` pada Elasticsearch adalah `1s`. Mengapa pencarian dokumen baru dapat dilakukan setelah *refresh*, namun data baru dijamin *durable* (aman dari crash proses JVM) setelah *flush*?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

**Jawaban:**
- **Refresh (`index.refresh_interval: 1s`):**
  Mengambil dokumen dari in-memory indexing buffer dan menulisnya ke Lucene Segment baru di filesystem cache OS (`write()`). Pada titik ini, segment baru sudah dibuka untuk pencarian oleh Lucene `IndexReader` (*searchable*), tetapi data belum dipaksa turun ke storage fisik (*fsync*). Jika node mati listrik, data di OS cache bisa hilang.
- **Translog (Transaction Log):**
  Setiap operasi penulisan (*indexing/delete*) dicatat secara bersamaan ke append-only translog. Default `index.translog.durability: request` menjamin `fsync` ke translog terjadi sebelum respon HTTP 200/201 dikembalikan ke klien.
- **Flush:**
  Operasi memicu `fsync()` penuh pada seluruh segment Lucene yang berada di filesystem cache ke disk fisik, menulis commit point baru, dan memangkas (*truncate*) translog lama. Setelah flush selesai, data sepenuhnya persisten dan aman dari kegagalan sistem tingkat hardware/OS.
</details>

---

### Soal 1.4: Rumus Shard Routing Elasticsearch
**Pertanyaan:**
Tuliskan rumus matematis default yang digunakan Elasticsearch untuk menentukan shard mana yang menyimpan suatu dokumen, dan jelaskan mengapa mengubah nilai `number_of_shards` pada index yang sudah ada dilarang keras tanpa reindexing!

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

**Jawaban:**
Rumus default shard routing:
$$\text{shard\_num} = \operatorname{hash}(\text{routing\_value}) \pmod{\text{primary\_shards}}$$
Secara default, `routing_value` adalah `_id` dokumen menggunakan algoritma Murmur3 hash.

**Mengapa `number_of_shards` tidak bisa diubah langsung:**
Jika jumlah primary shards berubah (misal dari 5 menjadi 6), hasil operasi modulo ($\pmod N$) untuk routing value yang sama akan menghasilkan indeks shard target yang berbeda. Akibatnya:
- Pencarian dokumen berdasarkan ID akan diarahkan ke shard yang salah, menyebabkan dokumen lama "hilang" (tidak ditemukan).
- Operasi update dokumen yang sama akan membuat duplikat di shard baru.
Oleh karena itu, penambahan kapasitas shard memerlukan proses Reindex API atau Split/Shrink Index API dengan aturan kelipatan integer tertentu.
</details>

---

### Soal 1.5: Status Kluster Green, Yellow, dan Red
**Pertanyaan:**
Jelaskan perbedaan mendasar antara status kesehatan kluster `GREEN`, `YELLOW`, dan `RED` dari perspektif alokasi shard dan ketersediaan layanan data!

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

**Jawaban:**
- **GREEN:** Seluruh *primary shard* dan seluruh *replica shard* telah dialokasikan dengan sukses ke node-node yang aktif di kluster. Toleransi kegagalan (*fault tolerance*) berada pada kondisi optimal.
- **YELLOW:** Semua *primary shard* berhasil dialokasikan dan melayani traffic pencarian maupun penulisan, tetapi terdapat minimal 1 *replica shard* yang berstatus `UNASSIGNED`. Kluster tetap berfungsi normal 100%, namun redundansi data berkurang (berisiko data loss jika node penampung primary mati). Sering terjadi pada single-node cluster dengan konfigurasi `number_of_replicas >= 1`.
- **RED:** Terdapat minimal 1 *primary shard* yang berstatus `UNASSIGNED`. Kluster berada dalam kondisi degradasi berat: penulisan dokumen ke index yang terdampak akan gagal (*rejected*), dan kueri pencarian akan menghasilkan data tidak lengkap (*partial results* / `_shards.failed > 0`).
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Perhitungan Memori Heap JVM dan Aturan 32 GB
**Pertanyaan:**
Pada server produksi dengan RAM fisik 128 GB, mengapa praktik terbaik alokasi heap JVM (`jvm.options`) merekomendasikan alokasi maksimal tidak melebihi ~31 GB (biasanya 30-31 GB), bukan 64 GB atau lebih? Jelaskan konsep *Compressed Ordinary Object Pointers* (Compressed OOPs) dan alokasi sisa RAM!

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

**Jawaban:**
1. **Compressed OOPs (32-bit Reference Limit):**
   - JVM pada arsitektur 64-bit menggunakan pointer 64-bit untuk menunjuk objek di heap.
   - JVM HotSpot memiliki fitur optimasi **Compressed OOPs** (`-XX:+UseCompressedOops`) yang memperlakukan pointer sebagai referensi 32-bit dengan pergeseran 3 bit (byte addressing kelipatan 8 byte), memungkinkan pengalamatan memori hingga:
     $$2^{32} \times 8 \text{ byte} = 32 \text{ GB}$$
   - Jika heap melampaui ambang batas ini (sering kali di kisaran 31.5 GB - 32 GB tergantung arsitektur CPU dan versi JDK), Compressed OOPs nonaktif dan JVM kembali menggunakan pointer 64-bit murni. Hal ini menyebabkan ukuran referensi objek membengkak 2x lipat, memboroskan memori, menurunkan throughput CPU cache L1/L2/L3, dan memperlambat Garbage Collection secara drastis. Heap 40 GB tanpa Compressed OOPs sering kali memiliki kapasitas efektif objek lebih kecil daripada heap 31 GB dengan Compressed OOPs.
2. **Pemanfaatan Sisa RAM (OS Filesystem Cache):**
   - Sisanya (~97 GB) dialokasikan untuk OS page cache. Lucene sangat bergantung pada filesystem cache untuk menyimpan inverted index, postings list, Doc Values (untuk sorting/aggregations), dan term dictionary agar pembacaan storage disk dihindari dan seluruh I/O berjalan langsung dari RAM fisik.
</details>

---

### Soal 2.2: Dual-Role Bottleneck (Master + Data Node)
**Pertanyaan:**
Apa risiko performa dan stabilitas yang timbul jika node yang sama dikonfigurasi sekaligus sebagai Master-eligible node dan Heavy Data Node (`node.roles: [master, data]`) pada beban transaksi indexing throughput tinggi (>50.000 docs/sec)?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

**Jawaban:**
- **JVM Garbage Collection Pauses:** Data node yang menerima throughput indexing masif akan menghasilkan jutaan objek sementara di memory (indexing buffer, transport buffers), memicu alokasi cepat dan siklus Major GC (Stop-the-World pauses) yang panjang (>10-30 detik).
- **Cluster State Heartbeat Timeout:** Jika master aktif mengalami GC pause atau CPU starvation akibat kompresi Lucene segment yang intensif, master tidak dapat membalas sinyal heartbeat antar-node (`cluster.heartbeat.timeout`).
- **Node Drop Palsu & Cascading Failure:** Node lain mengira master telah mati dan memulai pemilihan master baru (*election storm*). Sementara itu, master lama mengira node lain terputus dan mencoba mendistribusikan ulang (*reroute*) shard secara masif, membebani jaringan I/O dan membawa seluruh kluster ke kondisi unstable looping.
- **Pemisahan Peran:** Oleh karena itu, pada kluster produksi menengah-besar wajib memisahkan Dedicated Master Nodes (`node.roles: [master]`) yang ringan dan bebas dari beban agregasi/indexing data.
</details>

---

### Soal 2.3: Two-Phase Search Execution (Query-Then-Fetch)
**Pertanyaan:**
Jelaskan alur teknis dua tahap dari kueri pencarian default Elasticsearch (`query_then_fetch`) ketika sebuah kueri mencari 10 dokumen teratas (`size: 10, from: 0`) dari index dengan 5 primary shard!

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

**Jawaban:**
1. **Fase 1: Query Phase**
   - Klien mengirim request pencarian ke salah satu node di kluster (berperan sebagai **Coordinating Node**).
   - Coordinating node menyebarkan kueri ke satu salinan (baik primary maupun replica) dari ke-5 shard yang relevan.
   - Setiap shard mengeksekusi filter dan scoring secara independen di lokal Lucene Index masing-masing.
   - Setiap shard membangun priority queue berukuran `from + size` (yaitu $0 + 10 = 10$) yang hanya berisi Doc ID dan relevancy score (float), lalu mengirimkan daftar skor dan Doc ID tersebut kembali ke Coordinating Node. Data `_source` belum dibaca.
2. **Fase 2: Fetch Phase**
   - Coordinating node menggabungkan (*merge sort*) seluruh hasil dari ke-5 shard (maksimal $5 \times 10 = 50$ Doc ID) dan menentukan 10 Doc ID terbaik secara global.
   - Coordinating node mengirimkan multi-get request hanya untuk 10 Doc ID terpilih ke masing-masing shard penampung dokumen tersebut.
   - Setiap shard membaca data field mentah (`_source`) dari disk dan mengembalikannya ke Coordinating Node.
   - Coordinating node mengemas payload akhir dan mengembalikannya ke klien.
</details>

---

### Soal 2.4: Primary Terms, Sequence Numbers, dan Recovery
**Pertanyaan:**
Bagaimana Elasticsearch menggunakan `_primary_term` dan `_seq_no` untuk menyelesaikan konflik replikasi saat terjadi *failover* primary shard dan sinkronisasi shard replica?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

**Jawaban:**
- **`_primary_term`:** Integer counter yang bertambah secara monoton setiap kali terjadi pergantian atau pemilihan primary shard baru untuk suatu shard ID. Ini berfungsi sebagai penanda era kepemimpinan (fencing token) untuk mencegah primary shard lama yang terisolasi menulis data usang (*stale writes*).
- **`_seq_no`:** Nomor urut sekuensial yang diberikan untuk setiap operasi perubahan data (index, update, delete) pada level shard.
- **Mekanisme Recovery & Konflik:**
  - Setiap shard melacak **Global Checkpoint**, yaitu sequence number tertinggi di mana seluruh shard (primary dan in-sync replicas) telah menyetujui dan memproses operasi secara konsisten.
  - Ketika replica tertinggal atau node yang sempat mati hidup kembali, node tersebut tidak perlu menyalin seluruh file shard (puluhan GB). Sistem cukup membandingkan Local Checkpoint dengan Global Checkpoint primary, lalu menyinkronkan selisih sequence number dari translog/Lucene history retention leases (**Operations-based Recovery**).
  - Jika primary lama kembali aktif dengan sequence number yang berselisih pada primary term lama, operasi dengan primary term lebih rendah akan dibatalkan/di-truncate untuk memastikan konsistensi mutlak mengikuti primary term yang sah.
</details>

---

### Soal 2.5: Cost of Deep Pagination (`from + size` trap)
**Pertanyaan:**
Mengapa permintaan pencarian dengan `{"from": 100000, "size": 10}` sangat berbahaya bagi stabilitas memori kluster Elasticsearch? Apa solusi arsitektural yang tepat jika aplikasi membutuhkan navigasi data skala masif atau ekspor data?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

**Jawaban:**
1. **Bahaya `from + size` (The Deep Paging Trap):**
   - Pada `query_then_fetch`, jika index memiliki $N$ shard, setiap shard harus menghasilkan priority queue berukuran `from + size` = 100.010 dokumen di heap memory shard lokal.
   - Coordinating node kemudian harus mengumpulkan dan menampung $N \times 100.010$ objek di memori heap JVM, lalu melakukan sort global untuk membuang 100.000 item pertama dan hanya mengambil 10 item.
   - Kompleksitas memori dan CPU berskala $O(N \times (\text{from} + \text{size}))$. Permintaan paralel dari beberapa user dapat memicu seketika `OutOfMemoryError` (OOM) dan crash kluster. Secara default, Elasticsearch membatasi ini dengan `index.max_result_window: 10000`.
2. **Solusi Arsitektural:**
   - **`search_after`:** Menggunakan nilai urut unik (misal tie-breaker `timestamp` + `_id`) sebagai cursor. Heap memory per shard konstan ($O(\text{size})$) tanpa overhead akumulatif `from`. Solusi standar untuk pagination antarmuka pengguna modern (*infinite scroll*).
   - **Point in Time (PIT) + `search_after`:** Menyediakan snapshot view yang stabil selama pagination berlangsung di tengah indexing data baru.
   - **Scroll API:** Khusus untuk batch dump/ekspor data analitik offline dalam volume masif (tidak disarankan untuk interaksi user real-time).
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 3.1: Kluster Mengalami Status RED Pasca Restart Switch Jaringan Top-of-Rack
**Konteks Insiden:**
Setelah pemeliharaan switch jaringan di datacenter, kluster 12-node mengalami status `RED`. Index kritis transaksi logistik `shipments-2026.10` tidak bisa menerima penulisan data dan kueri dashboard monitoring error 500.

**Pemeriksaan Diagnostik Awal:**
Panggilan API `GET /_cluster/health` menunjukkan:
```json
{
  "status": "red",
  "number_of_nodes": 12,
  "unassigned_shards": 2,
  "active_primary_shards": 48
}
```

**Pertanyaan & Tugas Analisis:**
1. Perintah API apa yang wajib dieksekusi pertama kali untuk mengetahui *akar penyebab pasti* mengapa shard tersebut berstatus unassigned?
2. Jika output diagnostik menunjukkan alasan `ALLOCATION_FAILED` karena `disk threshold exceeded` atau kegagalan lock pada drive NVMe node tertentu, sebutkan langkah remediasi teknis yang aman tanpa kehilangan data!

<details>
<summary><b>Panduan Solusi Rekayasa Produksi</b></summary>

1. **Perintah Diagnostik Utama:**
   Gunakan Cluster Allocation Explain API:
   ```http
   POST /_cluster/allocation/explain
   {
     "index": "shipments-2026.10",
     "shard": 0,
     "primary": true
   }
   ```
   API ini memberikan penjelasan deterministik mengenai node mana yang diperiksa oleh master, mengapa alokasi ditolak (misal: *disk limit reached, shard lock failure, filter attribute mismatch*), dan riwayat kegagalan alokasi sebelumnya.

2. **Langkah Remediasi:**
   - **Jika Disk Watermark Exceeded:**
     Jika disk node melampaui `cluster.routing.allocation.disk.watermark.flood_stage` (default 95%), Elasticsearch mengunci index menjadi read-only (`read_only_allow_delete: true`).
     - Bersihkan disk atau tambahkan storage.
     - Lepaskan status read-only index:
       ```http
       PUT /shipments-2026.10/_settings
       {
         "index.blocks.read_only_allow_delete": null
       }
       ```
   - **Jika Shard Corrupt / Shard Max Allocation Retries Reached:**
     Jika engine menyerah setelah 5 kali gagal alokasi berturut-turut, picu alokasi ulang dengan:
     ```http
     POST /_cluster/reroute?retry_failed=true
     ```
   - **Sebagai Solusi Darurat Terakhir (Zero Primary Survival):**
     Hanya jika disk hardware benar-benar musnah dan replica shard masih tersedia namun primary hilang, administrator dapat menggunakan `allocate_stale_primary` melalui API `_cluster/reroute` (dengan kesadaran penuh potensi kehilangan data delta).
</details>

---

### Skenario 3.2: Insiden Garbage Collection Storm & Node Dropping Akibat Mapping Explosion
**Konteks Insiden:**
Sebuah aplikasi microservices mulai mengirimkan log berformat JSON mentah arbitrary dengan field yang berubah-ubah secara dinamis ke index harian `app-logs-2026.10.05` dengan dynamic mapping aktif. Dalam 3 jam, kluster mengalami:
- CPU utilization 100% pada semua node.
- Memory JVM Old Gen mencapai 99%, memicu GC Stop-the-World berulang kali selama 25 detik.
- Kluster kehilangan komunikasi antar-node (*node disconnected*).

**Pertanyaan & Tugas Analisis:**
1. Jelaskan fenomena **Mapping Explosion** dan mengapa hal ini menghancurkan kestabilan cluster state dan heap memory seluruh node!
2. Bagaimana cara menghentikan eskalasi insiden ini segera, dan konfigurasi pencegahan apa yang harus dipasang pada index template?

<details>
<summary><b>Panduan Solusi Rekayasa Produksi</b></summary>

1. **Mekanisme Kerusakan:**
   - Ketika dokumen JSON dengan ribuan key dinamis masuk ke index tanpa skema terdefinisi, Elasticsearch secara otomatis menambahkan metadata field baru ke index mapping.
   - Index mapping adalah bagian dari **Cluster State**.
   - Setiap kali mapping bertambah, master node harus memperbarui cluster state dan mem-broadcast seluruh cluster state baru tersebut ke *setiap* node di dalam kluster.
   - Ukuran cluster state yang membengkak (puluhan hingga ratusan megabyte string/metadata) harus ditampung di heap memory setiap node.
   - Pengecekan skema berulang membebani memory parser dan serialisasi transport layer, memicu siklus GC berkepanjangan pada seluruh node secara serentak.
2. **Langkah Mitigasi & Pencegahan:**
   - **Mitigasi Cepat:**
     Ubah dynamic mapping index bermasalah menjadi `false` atau `strict`:
     ```http
     PUT /app-logs-2026.10.05/_settings
     {
       "index.mapping.total_fields.limit": 1000
     }
     ```
     Atau tutup index sementara (`POST /app-logs-2026.10.05/_close`) jika heap JVM kolaps total.
   - **Solusi Arsitektural Permanen:**
     Buat Index Template dengan:
     1. `dynamic: false` pada root mapping (field baru di luar skema tetap disimpan di `_source` tetapi tidak diindeks ke inverted index).
     2. Gunakan tipe data `flattened` untuk payload JSON arbitrary/dinamis (misal field `metadata` atau `context`), yang mengindeks key-value arbitrary sebagai single keyword field tanpa memperluas cluster mapping:
        ```json
        {
          "mappings": {
            "properties": {
              "service_name": { "type": "keyword" },
              "timestamp": { "type": "date" },
              "payload": { "type": "flattened" }
            }
          }
        }
        ```
</details>

---

### Skenario 3.3: Degradasi Throughput Indexing Saat Bulk Ingestion Massal
**Konteks Insiden:**
Tim data engineer melakukan initial data load sebesar 500 juta dokumen dari Apache Kafka ke Elasticsearch index `ecommerce-products`. Pada awal proses, kecepatan penulisan mencapai 45.000 docs/detik, namun setelah 30 menit kecepatan anjlok ke 3.000 docs/detik dengan ratusan error HTTP 429 (`EsRejectedExecutionException` pada thread pool `write`).

**Pertanyaan & Tugas Analisis:**
1. Apa penyebab teknis di balik penolakan thread pool `write` dan degradasi I/O disk setelah proses berjalan lama?
2. Tuliskan resep konfigurasi index settings optimal yang wajib diterapkan sebelum memulai bulk ingestion masif, dan apa yang harus dilakukan setelah ingestion selesai!

<details>
<summary><b>Panduan Solusi Rekayasa Produksi</b></summary>

1. **Penyebab Teknis:**
   - **Segment Merging Bottleneck:** Indexing cepat menghasilkan ribuan segment Lucene berukuran kecil. Lucene background merge thread (TieredMergePolicy) bekerja keras menggabungkan segment-segment tersebut ke disk. Jika I/O disk storage (IOPS) tidak sanggup mengimbangi laju pembuatan segment baru, Elasticsearch secara otomatis menahan (*throttles*) thread indexing untuk mencegah penumpukan file descriptor tak terkendali.
   - **Thread Pool Queue Exhaustion:** Saat thread indexing di-throttle, antrean `write` thread pool (default 10.000 item) terisi penuh hingga kapasitas maksimum, sehingga request bulk berikutnya ditolak dengan status HTTP 429.
   - **Overhead Replikasi Real-time:** Setiap dokumen di-replicate secara synchronous ke replica shard pada setiap bulk request, memakan 2x lipat CPU dan Network I/O.
2. **Resep Optimasi Bulk Ingestion:**
   - **Sebelum Ingestion Dimulai:**
     Matikan replika dan perpanjang interval refresh:
     ```http
     PUT /ecommerce-products/_settings
     {
       "index": {
         "refresh_interval": "-1",
         "number_of_replicas": 0,
         "translog.durability": "async",
         "translog.sync_interval": "30s"
       }
     }
     ```
     - `refresh_interval: -1`: Menghentikan pembuatan segment-segment kecil setiap 1 detik.
     - `number_of_replicas: 0`: Menghilangkan beban sinkronisasi jaringan antar-node selama proses batching.
     - `translog.durability: async`: Mengurangi beban fsync disk per request (diterima untuk initial ingestion yang dapat di-replay).
   - **Setelah Ingestion Selesai:**
     Kembalikan toleransi fault tolerance dan rapikan struktur segment:
     ```http
     PUT /ecommerce-products/_settings
     {
       "index": {
         "refresh_interval": "1s",
         "number_of_replicas": 1,
         "translog.durability": "request"
       }
     }
     ```
     Lakukan Force Merge API untuk mengonsolidasi segment ke jumlah optimal (misal 1 segment per shard jika index read-only):
     ```http
     POST /ecommerce-products/_forcemerge?max_num_segments=1
     ```
</details>

---

## Bagian 4: Practical Chapter Challenge

### Tantangan Laboratorium Mandiri: Membangun Multi-Tier Cluster Architecture & Verifikasi Shard Routing

Tujuan dari challenge praktika ini adalah menguji kemampuan Anda membangun konfigurasi kluster berbasis code, memverifikasi failover secara langsung, dan membuktikan rumus shard allocation di terminal.

#### Spesifikasi Target Lab:
1. Menyiapkan topologi kluster 3-node lokal (Node-01, Node-02, Node-03) menggunakan Docker Compose.
2. Membuat Index Template dengan konfigurasi Custom Routing & Shard Allocation Awareness.
3. Melakukan simulasi crash node dan mengamati rebalancing shard secara realtime.

#### Langkah Eksekusi & Validasi:

##### Langkah 1: Buat Index dengan Spesifikasi Khusus
Buat index bernama `tenant-store-v1` dengan spesifikasi:
- 3 Primary Shards
- 1 Replica per Shard
- Refresh interval: `5s`

```bash
curl -X PUT "http://localhost:9200/tenant-store-v1" -H 'Content-Type: application/json' -d'
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "refresh_interval": "5s"
  },
  "mappings": {
    "_routing": {
      "required": true
    },
    "properties": {
      "tenant_id": { "type": "keyword" },
      "account_name": { "type": "text" },
      "balance": { "type": "double" }
    }
  }
}
'
```

##### Langkah 2: Verifikasi Penegakan Routing Wajib
Uji apakah aturan `_routing.required: true` bekerja dengan mencoba memasukkan dokumen tanpa parameter query `?routing=...`:
```bash
curl -i -X POST "http://localhost:9200/tenant-store-v1/_doc/acc-101" -H 'Content-Type: application/json' -d'
{
  "tenant_id": "tenant-alpha",
  "account_name": "Perusahaan ABC",
  "balance": 15000000.00
}
'
```
*Kriteria Sukses:* Elasticsearch wajib menolak request dengan status HTTP 400 (`routing_missing_exception`).

##### Langkah 3: Masukkan Data dengan Routing Eksplisit
Kirimkan dokumen dengan parameter routing yang valid:
```bash
curl -X POST "http://localhost:9200/tenant-store-v1/_doc/acc-101?routing=tenant-alpha" -H 'Content-Type: application/json' -d'
{
  "tenant_id": "tenant-alpha",
  "account_name": "Perusahaan ABC",
  "balance": 15000000.00
}
'
```

##### Langkah 4: Identifikasi Shard Penampung Melalui Search Shards API
Jalankan perintah berikut untuk mengonfirmasi bahwa kueri hanya menyentuh 1 shard tertentu (bukan broadcast ke semua 3 primary shards):
```bash
curl -X GET "http://localhost:9200/tenant-store-v1/_search_shards?routing=tenant-alpha"
```
*Kriteria Sukses:* Periksa array `shards`. Elasticsearch hanya boleh mengembalikan 1 pasangan shard (Primary & Replica untuk shard ID spesifik hasil Murmur3 hash dari string `tenant-alpha`).

##### Langkah 5: Uji Ketahanan Failover (Chaos Test)
1. Periksa alokasi node tempat primary shard berada menggunakan:
   ```bash
   curl -X GET "http://localhost:9200/_cat/shards/tenant-store-v1?v"
   ```
2. Hentikan container Docker node penampung primary shard tersebut (`docker stop es-node-xx`).
3. Pantau log kluster dan eksekusi:
   ```bash
   curl -X GET "http://localhost:9200/_cluster/health?pretty"
   ```
4. Catat berapa detik yang dibutuhkan kluster untuk mempromosikan replica shard menjadi primary baru, dan pastikan status kluster bertransisi dari `YELLOW` kembali ke `GREEN` setelah node dihidupkan ulang.

---

## Bagian 5: Checklist Pemahaman (Self-Assessment)

Gunakan daftar periksa berikut untuk mengevaluasi kesiapan Anda sebelum melangkah ke **BAB-02: Indexing, Mapping, dan Data Modeling**:

| Topik Fondasi & Arsitektur | Kriteria Evaluasi Mandiri | Status |
| :--- | :--- | :---: |
| **Node Roles** | Saya dapat membedakan fungsi serta batasan peran `master`, `data`, `ingest`, dan `coordinating-only` node. | [ ] |
| **Lucene Segments** | Saya memahami siklus hidup segment, konsep immutability, operasi append-only, dan mekanisme background merge. | [ ] |
| **Refresh vs Flush** | Saya dapat menjelaskan perbedaan alur in-memory index buffer -> OS page cache (refresh) vs OS page cache -> disk fsync (flush/translog). | [ ] |
| **Quorum Consensus** | Saya memahami cara kerja Raft-like cluster coordination Elasticsearch v7+ dan perhitungan minimum master node untuk mencegah split-brain. | [ ] |
| **Shard Distribution** | Saya menguasai rumus shard routing bawaan serta dampak pengabaian custom routing pada performa query throughput tinggi. | [ ] |
| **JVM & OS Memory** | Saya memahami alasan pembatasan JVM Heap maksimal ~31 GB dan peran vital 50% sisa RAM fisik untuk filesystem cache Lucene. | [ ] |
| **Cluster Diagnostik** | Saya mahir membaca output `_cluster/health`, `_cat/shards`, dan memanfaatkan `_cluster/allocation/explain` saat troubleshooting insiden RED/YELLOW. | [ ] |

---
*Selamat menyelesaikan kuis dan challenge BAB-01. Pastikan seluruh konsep di atas telah Anda kuasai sebelum melanjutkan perjalanan engineering Elasticsearch ke bab berikutnya.*
