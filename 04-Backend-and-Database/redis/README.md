# Kurikulum Rekayasa Sistem Redis: Dari Fondasi In-Memory hingga Distribusi Skala Petabyte

Selamat datang di silabus teknis komprehensif rekayasa Redis (*Remote Dictionary Server*). Kurikulum ini dirancang untuk mencetak *Staff Software Engineer*, *Distributed Systems Architect*, dan *Site Reliability Engineer* (SRE) yang mampu menguasai Redis secara mendalam—bukan sekadar sebagai *key-value cache* primitif, melainkan sebagai mesin komputasi *in-memory* deterministik dengan latensi sub-milidetik untuk infrastruktur data berkonkurensi masif.

---

## 1. Pandangan Umum Kursus & Pola Pikir (Course Overview & Mindset)

### Paradigma: Menembus Batas I/O dengan In-Memory Computing
Redis bekerja berdasarkan model eksekusi *single-threaded event loop* (multiplexing I/O berbasis `epoll`/`kqueue`) yang dikombinasikan dengan struktur data dalam memori yang sangat teroptimasi. Memahami Redis membutuhkan pergeseran paradigma dari *disk-bound database thinking* ke *memory-bound system engineering*:

1. **Efisiensi Alokasi & Mekanisme Cache CPU**: Setiap *byte* memori diperhitungkan. Memahami bagaimana *jemalloc*, *memory fragmentation*, representasi internal objek (`ziplist`, `listpack`, `intset`), dan *cache locality* memengaruhi performa throughput server.
2. **Deterministik Berbasis Kompleksitas Waktu**: Menghentikan ketergantungan pada *query-driven development*. Setiap interaksi dengan Redis harus diperhitungkan melalui analisis kompleksitas $O(1)$, $O(\log N)$, hingga $O(N)$. Pemilihan struktur data yang salah berpotensi memblokir *single-threaded engine* dan melumpuhkan seluruh kluster.
3. **Konkurensi & Konsistensi Terdistribusi**: Menguasai kompromi antara performa ekstrim dan jaminan durabilitas (CAP Theorem, PACELC). Redis bukan sekadar tempat menampung *cache temporary*, tetapi merupakan *state-store* kritis dalam pola transaksi atomik, *distributed locks*, *stream processing*, dan arsitektur *event-driven*.

### Prasyarat Teknis (Prerequisites)
* **Sistem Operasi & Jaringan**: Pemahaman mendalam tentang Linux OS primitives (TCP sockets, `epoll`, fork, memory paging, copy-on-write).
* **Struktur Data & Algoritma**: Penguasaan algoritma tingkat lanjut (Hash tables, Skip lists, Radix trees, B-Trees, Graph basics).
* **Arsitektur Sistem**: Pengalaman membangun aplikasi *backend microservices* multi-instance dan protokol komunikasi modern.

---

## 2. Peta Jalan Pembelajaran (Learning Roadmap)

```text
REDIS ARCHITECTURAL ROADMAP
├── [BAB 01] Fondasi In-Memory Computing & Arsitektur Internal Redis
├── [BAB 02] Struktur Data Inti & Optimasi Memory Layout
├── [BAB 03] Strategi Caching Lanjutan & Pola Mitigasi Anomali
├── [BAB 04] Konkurensi, Transaksi, & Eksekusi Server-Side Scripting
├── [BAB 05] Pub/Sub & Redis Streams untuk Event-Driven Architecture
├── [BAB 06] Ketahanan Data: Mekanisme Persistence, RDB, & AOF
├── [BAB 07] High Availability & Orkestrasi Failover dengan Redis Sentinel
├── [BAB 08] Skalabilitas Horizontal dengan Redis Cluster
├── [BAB 09] Tata Kelola Memori, Keamanan, Observabilitas, & Tuning Linux
└── [BAB 10] Ekosistem Redis Modern: Probabilistik, Vector Search, & JSON
```

---

## 3. Navigasi Kurikulum Detail (Bab 01 – Bab 10)

### [Bab 01: Fondasi In-Memory Computing & Arsitektur Internal Redis](bab-01-fondasi-arsitektur-redis/)
Membedah arsitektur internal Redis dari lapisan kernel hingga soket jaringan. Memahami bagaimana Redis mencapai ratusan ribu operasi per detik menggunakan model multiplexing I/O berbasis *event-loop*.

*   [Modul 01: Event Loop, Non-blocking I/O, & Threading Model](bab-01-fondasi-arsitektur-redis/modul-01-event-loop-dan-threading.md)
    *   *Topik*: Analisis arsitektur `ae.c`, `epoll`/`kqueue`/`select`, transisi arsitektur I/O Threads (Redis 6.0+), pemrosesan *single-threaded command execution*.
    *   *Target Capaian*: Mampu mendiagnosis *bottleneck* I/O vs CPU pada Redis instance ber-throughput tinggi.
*   [Modul 02: Redis Serialization Protocol (RESP2 & RESP3)](bab-01-fondasi-arsitektur-redis/modul-02-protokol-resp.md)
    *   *Topik*: Spesifikasi protokol RESP2 vs RESP3, struktur framing byte, parsing efisien, pipelining, pemanfaatan soket multiplexing secara raw.
    *   *Target Capaian*: Mampu membangun RESP parser performa tinggi atau mengoptimasi *client networking stack*.

---

### [Bab 02: Struktur Data Inti & Optimasi Memory Layout](bab-02-struktur-data-dan-memory-layout/)
Mengeksplorasi implementasi C internal dari struktur data Redis, representasi *encoding*, dan trade-off konsumsi RAM.

*   [Modul 01: Primitif Fundamental: Strings, Hashes, & Encoding Internal](bab-02-struktur-data-dan-memory-layout/modul-01-strings-hashes-encoding.md)
    *   *Topik*: `SDS` (Simple Dynamic Strings), `redisObject`, representasi `raw` vs `embstr`, evolusi dari `ziplist` ke `listpack`, optimasi efisiensi RAM pada Hash.
    *   *Target Capaian*: Mampu menekan konsumsi RAM hingga 60% menggunakan teknik pengkodean *memory-dense*.
*   [Modul 02: Koleksi Kompleks: Lists, Sets, Sorted Sets (ZSet)](bab-02-struktur-data-dan-memory-layout/modul-02-lists-sets-sorted-sets.md)
    *   *Topik*: `quicklist`, `intset`, `skiplist` + `dict` internal pada Sorted Sets, analisis kompleksitas $O(\log N)$ dan $O(1)$.
    *   *Target Capaian*: Mampu mendesain skema leaderboard skala jutaan user dengan pembaruan berlatensi rendah.
*   [Modul 03: Tipe Data Khusus: Bitmaps, Bitfields, & Geospatial](bab-02-struktur-data-dan-memory-layout/modul-03-bitmaps-bitfield-geospatial.md)
    *   *Topik*: Operasi manipulasi bitwise deterministik, arsitektur Geohash berbasis Sorted Sets, analitik real-time *daily active users* berbasis bit-level.
    *   *Target Capaian*: Mengimplementasikan tracking presensi masif dengan jejak memori minimal.

---

### [Bab 03: Strategi Caching Lanjutan & Pola Mitigasi Anomali](bab-03-caching-lanjutan-dan-mitigasi-anomali/)
Membangun pola caching tingkat lanjut dan merancang sistem yang kebal terhadap kegagalan mendadak pada layer database backend.

*   [Modul 01: Pola Arsitektur Cache-Aside, Write-Through, Write-Behind](bab-03-caching-lanjutan-dan-mitigasi-anomali/modul-01-pola-caching-arsitektur.md)
    *   *Topik*: Siklus hidup read/write data, strategi sinkronisasi asinkron, konsistensi data eventual, komputasi *dual-write race condition*.
    *   *Target Capaian*: Menerapkan integrasi cache-ke-database tanpa kehilangan data (*zero data loss*).
*   [Modul 02: Mitigasi Cache Stampede, Breakdown, Avalanche, & Penetration](bab-03-caching-lanjutan-dan-mitigasi-anomali/modul-02-mitigasi-stampede-avalanche.md)
    *   *Topik*: Algoritma XFetch (Probabilistic Early Expiration), Mutex locking pada miss cache, Bloom Filters untuk pencegahan penetrasi, jitter TTL.
    *   *Target Capaian*: Menghindari *thundering herd problem* saat terjadi *cache invalidation* mendadak.

---

### [Bab 04: Konkurensi, Transaksi, & Eksekusi Server-Side Scripting](bab-04-transaksi-lua-scripting/)
Menjamin atomisitas tingkat tinggi di atas Redis, menghindari kondisi balapan (*race conditions*), dan menjalankan komputasi dekat dengan data.

*   [Modul 01: Transaksi Redis: MULTI, EXEC, DISCARD, & WATCH](bab-04-transaksi-lua-scripting/modul-01-transaksi-multi-exec-watch.md)
    *   *Topik*: Model Optimistic Concurrency Control (OCC) menggunakan `WATCH`, isolasi eksekusi, penanganan kegagalan atomik.
    *   *Target Capaian*: Mampu mendesain alur transaksi deterministik murni tanpa *distributed deadlock*.
*   [Modul 02: Server-Side Logic dengan Lua Scripting & Redis Functions](bab-04-transaksi-lua-scripting/modul-02-lua-scripting-dan-functions.md)
    *   *Topik*: Eksekusi atomik skrip Lua, Redis 7 Functions library management, pemblokiran event-loop, debugging via `ldb`.
    *   *Target Capaian*: Mengimplementasikan algoritma kompleks (seperti sliding-window rate limiter) secara atomik dalam satu *round-trip*.
*   [Modul 03: Pola Distributed Locking Tingkat Lanjut (Redlock)](bab-04-transaksi-lua-scripting/modul-03-distributed-locking-redlock.md)
    *   *Topik*: Mekanisme penguncian terdistribusi primitif, algoritma Redlock, kritik Martin Kleppmann, validasi fencing tokens, crash-safety.
    *   *Target Capaian*: Menerapkan sistem kunci terdistribusi yang aman untuk alur transfer keuangan atau mutasi resource kritis.

---

### [Bab 05: Pub/Sub & Redis Streams untuk Event-Driven Architecture](bab-05-pubsub-dan-redis-streams/)
Membandingkan dan mengimplementasikan sistem *messaging* serta *event stream* performa tinggi menggunakan primitives Redis.

*   [Modul 01: Redis Pub/Sub: Pola Fire-and-Forget & Keterbatasannya](bab-05-pubsub-dan-redis-streams/modul-01-pubsub-karakteristik-limitasi.md)
    *   *Topik*: Fan-out messaging, arsitektur `SUBSCRIBE`/`PUBLISH`, pattern matching `PSUBSCRIBE`, ketiadaan buffer/durabilitas, buffer overflow client.
    *   *Target Capaian*: Mampu menentukan penggunaan Pub/Sub yang tepat (misal: invalidasi cache terdistribusi) tanpa risiko *message loss*.
*   [Modul 02: Redis Streams: Log Append-Only, Consumer Groups, & Pelacakan ACK](bab-05-pubsub-dan-redis-streams/modul-02-redis-streams-consumer-groups.md)
    *   *Topik*: Radix Tree internals, `XADD`, `XREADGROUP`, abstraksi Consumer Group, Pending Entries List (PEL), dead-letter handling, `XCLAIM`.
    *   *Target Capaian*: Membangun *event streaming pipeline* yang setara dengan Kafka ringan (*lightweight message broker*) berlatensi sub-milidetik.

---

### [Bab 06: Ketahanan Data: Mekanisme Persistence, RDB, & AOF](bab-06-persistence-rdb-aof/)
Memahami cara Redis mempertahankan data di disk tanpa mengorbankan performa *in-memory* secara signifikan.

*   [Modul 01: Redis Database Backup (RDB): Mekanisme Copy-on-Write (COW)](bab-06-persistence-rdb-aof/modul-01-rdb-snapshotting-cow.md)
    *   *Topik*: Mekanisme kerja `fork()`, OS Copy-on-Write, point-in-time snapshotting, overhead memori saat snapshotting masif, integritas file dump.
    *   *Target Capaian*: Mengonfigurasi automated snapshotting dengan parameter crash resilience yang terukur.
*   [Modul 02: Append-Only File (AOF): fsync Strategies & Background Rewrite](bab-06-persistence-rdb-aof/modul-02-aof-fsync-dan-rewriting.md)
    *   *Topik*: Kebijakan `fsync` (`always`, `everysec`, `no`), strategi `BGREWRITEAOF`, Multi-Part AOF (Redis 7.0+), penanganan disk I/O bottleneck.
    *   *Target Capaian*: Mampu menyeimbangkan antara Recovery Point Objective (RPO) mendekati nol dan performa penulisan disk.

---

### [Bab 07: High Availability & Orkestrasi Failover dengan Redis Sentinel](bab-07-redis-sentinel-high-availability/)
Membangun arsitektur replikasi primer-replika dan otomatisasi failover yang toleran terhadap *split-brain*.

*   [Modul 01: Replikasi Master-Replica Asinkron & PSYNC2 Protocol](bab-07-redis-sentinel-high-availability/modul-01-replikasi-master-replica-psync.md)
    *   *Topik*: Replikasi asinkron, replication backlog buffer, partial resynchronization (PSYNC), full resynchronization, risiko replikasi lag.
    *   *Target Capaian*: Mengonfigurasi topologi replikasi yang tahan terhadap disrupsi jaringan transien tanpa *full sync overhead*.
*   [Modul 02: Sentinel Quorum, Monitoring, & Orkestrasi Failover](bab-07-redis-sentinel-high-availability/modul-02-sentinel-failover-split-brain.md)
    *   *Topik*: Konsensus Sentinel, parameter `quorum`, deteksi kegagalan subjektif/objektif (`SDOWN` & `ODOWN`), mitigasi split-brain via `min-replicas-to-write`.
    *   *Target Capaian*: Menerapkan arsitektur Redis HA dengan Recovery Time Objective (RTO) < 10 detik.

---

### [Bab 08: Skalabilitas Horizontal dengan Redis Cluster](bab-08-redis-cluster-sharding/)
Mendesain sistem *partitioned data* skala besar yang terdistribusi ke puluhan simpul menggunakan konsep *hash slots*.

*   [Modul 01: Arsitektur Hash Slots, Skema Sharding, & Gossip Protocol](bab-08-redis-cluster-sharding/modul-01-hash-slots-gossip-protocol.md)
    *   *Topik*: Mekanisme CRC16 modulo 16384, komunikasi bus node internal (Gossip Protocol), penanganan multi-key via Hash Tags `{...}`.
    *   *Target Capaian*: Mampu mendesain arsitektur sharding terdistribusi tanpa menghasilkan slot skewing.
*   [Modul 02: Resharding, Redirects (MOVED vs ASK), & Kluster Failover](bab-08-redis-cluster-sharding/modul-02-resharding-redirects-failover.md)
    *   *Topik*: Resharding data dinamis tanpa downtime, protokol respons client `MOVED` dan `ASK`, node routing, otomatisasi promosi replica di cluster.
    *   *Target Capaian*: Mengoperasikan kluster berskala besar dengan kapasitas ratusan gigabyte memori dan zero downtime maintenance.

---

### [Bab 09: Tata Kelola Memori, Keamanan, Observabilitas, & Tuning Linux](bab-09-manajemen-memori-keamanan-observabilitas/)
Memastikan Redis beroperasi secara stabil pada level sistem operasi dan memproteksi instans dari eksploitasi keamanan.

*   [Modul 01: Kebijakan Eviksi, Fragmentasi Memori, & Tuning jemalloc](bab-09-manajemen-memori-keamanan-observabilitas/modul-01-eviction-policies-jemalloc.md)
    *   *Topik*: Algoritma eviksi (LRU vs LFU approksimasi), `maxmemory`, analisis rasio fragmentasi memori, teknik defragmentasi aktif secara online.
    *   *Target Capaian*: Menghindari *Out-of-Memory* (OOM) killer Linux pada server Redis berkapasitas kritis.
*   [Modul 02: Keamanan Redis: ACLs, TLS Encryption, & Hardening OS](bab-09-manajemen-memori-keamanan-observabilitas/modul-02-keamanan-acl-tls-hardening.md)
    *   *Topik*: Access Control Lists (ACL) granular, enkripsi komunikasi via mTLS, penonaktifan perintah berbahaya (`FLUSHALL`, `CONFIG`), pengamanan soket jaringan.
    *   *Target Capaian*: Mengamankan sistem Redis sesuai standar regulasi enterprise dan kepatuhan perbankan.
*   [Modul 03: Deep Observability: Analisis INFO, SLOWLOG, & Linux Kernel Tuning](bab-09-manajemen-memori-keamanan-observabilitas/modul-03-observabilitas-linux-kernel-tuning.md)
    *   *Topik*: Metrik vital `INFO` (instantaneous ops, instantaneous input/output, mem_fragmentation_ratio), integrasi Prometheus/Grafana, optimasi OS kernel (`vm.overcommit_memory`, Transparent Huge Pages disabling, TCP backlog setting).
    *   *Target Capaian*: Mampu mendeteksi latensi mikro (*latency spikes*) dan memaksimalkan performa Redis pada level OS.

---

### [Bab 10: Ekosistem Redis Modern: Probabilistik, Vector Search, & JSON](bab-10-redis-modern-modules-vector/)
Mengembangkan kapabilitas Redis di luar *key-value store* klasik dengan memanfaatkan fitur Redis Stack engine modern.

*   [Modul 01: Struktur Data Probabilistik: Bloom, Cuckoo, Count-Min Sketch, & Top-K](bab-10-redis-modern-modules-vector/modul-01-probabilistic-data-structures.md)
    *   *Topik*: Pengurangan jejak memori secara radikal, deteksi elemen set, aproksimasi frekuensi, pelacakan *heavy hitters* real-time.
    *   *Target Capaian*: Menyelesaikan masalah komputasi masif dengan tingkat akurasi terukur menggunakan memori berukuran kilobyte.
*   [Modul 02: RedisJSON & RediSearch: Mesin Dokumen & Indexing](bab-10-redis-modern-modules-vector/modul-02-redisjson-redisearch.md)
    *   *Topik*: Penyimpanan data JSON terstruktur via JSONPath, pembuatan indeks sekunder, query teks lengkap (*full-text search*), filtering numerik dan geospasial.
    *   *Target Capaian*: Menerapkan sistem penyimpanan dokumen real-time dengan kemampuan query multi-dimensi.
*   [Modul 03: Vector Search (HNSW/FLAT) untuk AI & Rekomendasi Real-Time](bab-10-redis-modern-modules-vector/modul-03-vector-search-ai.md)
    *   *Topik*: Vector embeddings, algoritma indeks HNSW (Hierarchical Navigable Small World) dan FLAT, cosine similarity, semantic search sub-milidetik.
    *   *Target Capaian*: Membangun layer inferensi Retrieval-Augmented Generation (RAG) atau rekomendasi bervolume tinggi berbasis Redis.

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Sistem
**"Distributed Ultra-Low Latency Flash-Sale Engine & Real-Time Fraud Shield"**

### Arsitektur & Lingkup Rekayasa
Siswa wajib membangun mesin backend terdistribusi untuk skenario *flash sale* berskala global yang menangani jutaan transaksi concurrent per menit dengan latensi P99 di bawah 5 milidetik, terintegrasi secara simultan dengan sistem *fraud detection* real-time.

```text
                                  +-------------------+
                                  |   Client Layer    |
                                  +---------+---------+
                                            |
                                            v (Traffic Spike)
                                  +---------+---------+
                                  |   API Gateway     |
                                  |  (Sliding Rate)   |
                                  +----+---------+----+
                                       |         |
                      Rate Limit OK    |         | Fraud Detected (Drop)
                                       v         v
    +------------------------------------+     +----------------------------------+
    | Redis Sentinel Cluster (Fraud Hub) |     | Blackhole / Audit Log Sink       |
    | - Bloom Filter (Blacklist Check)   |     +----------------------------------+
    | - Vector Search (Anomaly Matching) |
    +------------------+-----------------+
                       | Validated
                       v
    +------------------+-----------------+
    |   Redis Cluster (Inventory Engine) |
    |   - Hash-tagged Slots: {SKU_1001}  |
    |   - Lua Engine (Atomic Stock Decr) |
    +------------------+-----------------+
                       | Verified Purchase Event
                       v
    +------------------+-----------------+
    |   Redis Streams Pipeline           |
    |   - Consumer Group A (Ledger Sync) |
    |   - Consumer Group B (Audit Log)   |
    +------------------------------------+
```

### Komponen Teknis yang Wajib Diterapkan
1. **Flash-Sale Inventory Lock (Zero Oversell Guarantee)**:
   *   Menggunakan skrip Lua atomik untuk memvalidasi saldo, mengecek kuota pengguna, dan mengurangi stok inventaris secara real-time pada Redis Cluster yang menggunakan skema *hash-tagging* (`{item_id}`) untuk konsistensi slot.
2. **Multi-Tier Rate Limiting & Abuse Prevention**:
   *   *Sliding-Window Counter* berbasis Sorted Set dan Bitfield untuk membatasi frekuensi request per identitas/IP.
   *   Pemanfaatan *Bloom Filter* untuk memverifikasi blacklist ID pengguna miliaran data secara instan sebelum melakukan query database.
3. **Real-Time Anomaly & Fraud Detection**:
   *   Pemanfaatan *Vector Similarity Search* (HNSW) di dalam Redis untuk mencocokkan pola perilaku request transaksi terhadap vektor embedding aktivitas fraud historis secara sub-milidetik.
4. **Reliable Event Streaming & Asynchronous Write-Behind**:
   *   Penerbitan event pembelian ke *Redis Streams* (`XADD`).
   *   Konsumsi terdistribusi via *Consumer Groups* yang memiliki mekanisme pelacakan *Pending Entries List* (PEL) dan *auto-claim worker failure* untuk sinkronisasi mutasi ke relational database (RDBMS/PostgreSQL) secara eventual consistent.
5. **Production Hardening, HA & Disaster Recovery**:
   *   Kluster berjalan dengan konfigurasi TLS aktif, ACL terbatas (*least privilege*), tuning Linux OS (`sysctl`, memory overcommit, disabling THP).
   *   Konfigurasi *Hybrid Persistence* (AOF `everysec` + snapshotting RDB berkala) dengan skema automated failover Sentinel / Cluster tanpa kehilangan data transaksi yang telah di-*acknowledge*.

### Service Level Objectives (SLO) & Validasi Sistem
*   **Throughput**: Mampu melayani minimal 100.000 Request Per Second (RPS) pada benchmark load-testing terdistribusi (menggunakan `wrk` atau `locust`).
*   **Latency Profile**: P99 < 5ms, P99.9 < 15ms untuk seluruh operasi verifikasi inventaris dan *fraud score calculation*.
*   **Integrity Guarantee**: **0% oversell** pada 1.000 item yang diperebutkan oleh 100.000 simulated concurrent clients.
*   **Resilience & Recovery**: Waktu pemulihan saat node primary mendadak mati (kill -9) adalah RTO < 8 detik dan RPO = 0 untuk transaksi yang telah masuk status committed stream.

---
*Silabus ini merupakan panduan berstandar enterprise engineering. Setiap bab dirancang berurutan; penguasaan materi bab sebelumnya adalah prasyarat mutlak untuk melanjutkan ke bab berikutnya.*