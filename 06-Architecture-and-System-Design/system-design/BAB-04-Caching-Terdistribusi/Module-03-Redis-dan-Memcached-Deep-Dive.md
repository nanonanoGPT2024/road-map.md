# MODULE 03: In-Memory Datastores (Redis vs Memcached & Redis Cluster)

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Membandingkan secara teknis dan arsitektural antara **Redis** (Single-threaded event loop, rich data types, persistence) dan **Memcached** (Multi-threaded, pure key-value).
2. Memilih tipe data Redis yang tepat: **Strings, Hashes, Lists, Sets, Sorted Sets (ZSET), HyperLogLog, dan Bitmaps**.
3. Menganalisis trade-off persistensi data Redis: **RDB (Snapshotting)** vs **AOF (Append-Only File)**.
4. Menjelaskan arsitektur High Availability dan Skalabilitas: **Redis Sentinel (Automated Failover)** vs **Redis Cluster (16.384 Hash Slots Sharding)**.
5. Menghindari bahaya perintah pemblokir thread (seperti `KEYS *`) dan menerapkan teknik **Hash Tags `{...}`** untuk mencegah *Cross-Slot Error*.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 04 — Module 01: Caching Layers & Pola Akses Data](./Module-01-Caching-Layers-dan-Pola-Akses.md).
- Telah menyelesaikan [BAB 04 — Module 02: Eviction Policies & Mitigasi Anomali Caching](./Module-02-Eviction-Policies-dan-Mitigasi-Anomali.md).

---

## 3. Concept
Ketika aplikasi backend di-scale out menjadi puluhan server pod di Kubernetes, cache lokal di memori aplikasi (*local in-memory cache*) tidak lagi memadai karena setiap server memiliki salinan data yang terisolasi dan inkonsisten.

Sistem membutuhkan **Distributed In-Memory Datastore** terpusat yang dapat diakses oleh seluruh instance secara bersamaan dengan latensi sub-milidetik (< 1 ms). Dua teknologi paling dominan di dunia industri untuk kebutuhan ini adalah **Redis** dan **Memcached**.

---

## 4. Why? (Mengapa Redis Lebih Banyak Dipilih Daripada Memcached?)

### Mengapa Redis Sangat Cepat Meskipun "Single-Threaded"?
Banyak engineer terkejut mengetahui bahwa proses eksekusi perintah di core engine Redis hanya berjalan pada **1 thread CPU tunggal (single-threaded event loop)**. Mengapa Redis bisa mencapai lebih dari **100.000 QPS** per core?
1. **Penyimpanan Murni di RAM:** Semua data berada di memori utama; tidak ada disk seek atau pembacaan storage lambat saat pemrosesan query.
2. **I/O Multiplexing Non-Blocking (`epoll` / `kqueue`):** Satu thread mampu mengelola puluhan ribu koneksi socket jaringan secara bersamaan tanpa thread context-switching.
3. **Zero Lock Overhead:** Karena dieksekusi sekuensial oleh single-thread, Redis bebas dari locking, mutex contention, dan deadlock!

Namun, sifat single-threaded ini memiliki satu kelemahan fatal: **Satu perintah lambat ($O(N)$) akan memblokir SELURUH pengguna lain di seluruh dunia!**

---

## 5. What? (Tabel Perbandingan Lengkap: Redis vs Memcached)

| Fitur | Redis | Memcached |
|---|---|---|
| **Model Threading** | Single-threaded core (Multi-threaded I/O) | Multi-threaded (Sangat optimal untuk multi-core CPU) |
| **Struktur Data** | Strings, Hashes, Lists, Sets, ZSET, Streams, Geo | Pure Key-Value murni (String / Binary Blob saja) |
| **Persistensi ke Disk** | Ya (RDB Snapshot & AOF Log) | Tidak ada sama sekali (Volatile murni) |
| **Replikasi & HA** | Ya (Master-Replica + Redis Sentinel) | Tidak ada bawaan (Harus diatur di level client) |
| **Sharding Horizontal** | Native (Redis Cluster dengan 16.384 slots) | Client-side Consistent Hashing |
| **Maksimal Ukuran Nilai** | 512 MB per value | 1 MB per value (Default slab allocation) |
| **Use Case Terbaik** | Leaderboard, Session, Rate Limiter, Pub/Sub | Caching objek statis sederhana berskala raksasa |

---

## 6. How? (Struktur Data Redis & Arsitektur Klaster)

### A. Ragam Struktur Data Kunci Redis

```text
1. STRING: 
   SET user:100:token "xyz123" EX 3600
   (Session auth, caching JSON, atomic counter INCR / DECR)

2. HASH: 
   HSET user:100 name "Budi" email "budi@mail.com" tier "Gold"
   (Sangat hemat memori untuk merepresentasikan objek profil database)

3. LIST: 
   LPUSH task_queue "job_id_1" -> RPOP task_queue
   (Message queue FIFO sederhana, timeline log terbaru)

4. SET: 
   SADD tags:article:10 "tech" "system-design"
   (Koleksi nilai unik, operasi irisan SINTER, gabungan SUNION)

5. SORTED SET (ZSET): 
   ZADD leaderboard 5500 "PlayerA" 7200 "PlayerB"
   (Peringkat real-time berurutan berdasarkan Score, gaming leaderboard)

6. BITMAP: 
   SETBIT active_users:2026-09-11 99812 1
   (Menandai kehadiran/keaktifan 100 juta pengguna hanya dengan ~12 MB RAM!)
```

---

### B. Persistensi Data: RDB vs AOF

```text
[ REDIS DATA IN RAM ]
         │
         ├──▶ 1. RDB (Redis Database Snapshot):
         │       Setiap N menit (misal tiap 15 menit), Redis melakukan fork() 
         │       dan menulis snapshot binary memory dump ke file "dump.rdb".
         │       (Kelebihan: File sangat ringkas, restart cepat. Kekurangan: Data 15 menit terakhir bisa hilang jika crash).
         │
         └──▶ 2. AOF (Append-Only File):
                 Setiap kali ada perintah penulisan (SET, HSET), perintah tersebut 
                 dicatat ke log "appendonly.aof" secara berurutan.
                 (Kelebihan: Sangat aman, fsync tiap detik. Kekurangan: Ukuran file besar, recovery restart lebih lambat).
```
> **Rekomendasi Produksi:** Aktifkan **keduanya (RDB + AOF)** secara bersamaan untuk kombinasi pemulihan cepat dan ketahanan data maksimal.

---

### C. Sharding Redis Cluster: 16.384 Hash Slots & Hash Tags
Redis Cluster tidak menggunakan consistent hashing ring biasa, melainkan membagi ruang data menjadi **tepat 16.384 Hash Slots**:

$$\text{Slot ID} = \text{CRC16}(\text{Key}) \pmod{16384}$$

```text
[ REDIS CLUSTER ARCHITECTURE (3 MASTER, 3 REPLICA) ]

   Master Node 1                  Master Node 2                  Master Node 3
(Slot: 0 s/d 5460)            (Slot: 5461 s/d 10922)         (Slot: 10923 s/d 16383)
        │                              │                              │
        ▼                              ▼                              ▼
  Replica Node 1                 Replica Node 2                 Replica Node 3
```

#### Masalah "Cross-Slot Error" & Solusi Hash Tags `{...}`:
Pada Redis Cluster, operasi multi-kunci (seperti transaksi `MGET`, pipeline, atau operasi set `SINTER`) **wajib berada di node fisik yang sama**. Jika kunci A berada di Slot 200 (Node 1) dan kunci B berada di Slot 9000 (Node 2), Redis akan melempar error:
`CROSSSLOT Keys in request don't hash to the same slot`.

**Solusinya: Gunakan Hash Tags!**
Tambahkan kurung kurawal `{...}` pada kunci. Redis Cluster hanya akan menghitung hash pada bagian teks di dalam kurung kurawal:
```text
Key 1: {user:101}:profile  -> Hash dihitung dari "user:101" -> Slot 4321
Key 2: {user:101}:orders   -> Hash dihitung dari "user:101" -> Slot 4321 (Dijamin 1 Node!)
```

---

## 7. Analogy
- **Memcached:** Seperti **Loker Penitipan Barang Polos di Stasiun**. Setiap loker memiliki nomor. Anda hanya bisa memasukkan koper tertutup (string/blob) dan mengambilnya kembali. Sangat cepat, efisien, namun loker tidak peduli apa isi di dalam koper Anda.
- **Redis:** Seperti **Meja Kerja Mekanik Canggih Berisi Kotak Perkakas Lengkap**. Anda tidak hanya bisa menyimpan koper, tetapi ada laci khusus obeng berjejer rapi (*List*), papan klasifikasi kunci pas (*Set*), papan skor waktu kerja (*Sorted Set*), dan buku catatan agenda yang tersimpan otomatis di brankas (*Persistence*).

---

## 8. Diagram: Alur Failover Otomatis Redis Sentinel

```text
                  [ ARSITEKTUR REDIS SENTINEL ]

                     +---------------------+
                     |    SENTINEL QUORUM  |
                     | (3 Proses Pengawas) |
                     +----------+----------+
                                │ (Heartbeat PING setiap 1 detik)
            ┌───────────────────┴───────────────────┐
            ▼                                       ▼
    +---------------+                       +---------------+
    | MASTER NODE   |                       | REPLICA NODE  |
    | (Read / Write)| ~ ~ ~ Replikasi ~ ~ ~ | (Read Only)   |
    +---------------+                       +---------------+
           │
           ▼ (Master Mengalami Crash / Listrik Padam)
           
1. Tiga proses Sentinel sepakat bahwa Master mati (Subjective Down -> Objective Down).
2. Sentinel memilih Replica terbaik berdasarkan replication offset.
3. Sentinel mempromosikan Replica menjadi MASTER BARU.
4. Sentinel memberi tahu seluruh backend client IP Master yang baru.
```

---

## 9. Simple Example: Bahaya Perintah `KEYS *` di Produksi

```text
❌ FATAL DI PRODUKSI:
redis> KEYS user:*
(Jika terdapat 10 juta user, perintah ini memblokir event loop Redis selama 4 detik!
 Seluruh 100.000 request user lain di dunia akan mengalami timeout 504 Gateway Error!).

✅ CARA YANG BENAR (NON-BLOCKING CURSOR):
redis> SCAN 0 MATCH user:* COUNT 100
(Mengambil 100 item secara bertahap menggunakan kursor tanpa menghentikan thread utama).
```

---

## 10. Practical Code Example
Lihat demonstrasi sharding 16.384 slot, formula CRC16, grouping Hash Tags, dan simulasi cluster failover pada:
`System-Design/BAB-04-Caching-Terdistribusi/hands-on/m03/redis_cluster_sim.js`

---

## 11. Real World Example: Leaderboard Game Mobile & Twitter Timeline
- **Gaming Leaderboard (Mobile Legends / PUBG):** Menyimpan ranking 50 juta pemain berdasarkan skor bintang. Menggunakan **Redis Sorted Set (ZSET)**:
  `ZADD season_rank 2450 "player_andi"`  
  Mencari top 100 pemain dunia: `ZREVRANGE season_rank 0 99 WITHSCORES` hanya membutuhkan waktu **0.8 milidetik** berkat struktur data internal *SkipList* yang tertanam di Redis!
- **Twitter Home Timeline:** Twitter menyimpan 800 tweet ID terbaru untuk setiap pengguna aktif di dalam struktur **Redis List**. Saat Anda membuka aplikasi, Twitter cukup mengeksekusi `LRANGE timeline:user_id 0 20` untuk menampilkan 20 tweet teratas tanpa membebani database utama.

---

## 12. Trade-offs (RDB vs AOF Persistence)

| Parameter | RDB (Snapshotting) | AOF (Append-Only File) |
|---|---|---|
| **Ketahanan Data (*Durability*)** | Ada jeda 5-15 menit potensi kehilangan | Hampir nol (maksimal 1 detik jika `fsync everysec`) |
| **Ukuran File Storage** | Sangat kecil & terkompresi rapi | Besar (karena mencatat setiap query modifikasi) |
| **Kecepatan Restart Server** | Sangat Cepat (langsung load memori dump) | Lambat (harus memutar ulang seluruh log perintah) |
| **Dampak CPU saat Runtime** | Ada lonjakan CPU saat `fork()` proses | Ringan dan stabil |

---

## 13. When To Use What
- **Gunakan Memcached jika:** Anda hanya butuh caching key-value sederhana dengan beban traffic multi-core raksasa, dan Anda tidak butuh persistensi ke disk maupun struktur data canggih.
- **Gunakan Redis jika:** Anda membutuhkan salah satu dari: struktur data (ZSET, Hash, Set), session store persisten, distributed lock (*Redlock*), pub/sub message broker, atau rate limiting atomik.
- **Gunakan Redis Cluster jika:** Dataset in-memory Anda melebihi **32 GB - 64 GB**, sehingga wajib dipecah ke beberapa mesin fisik yang berbeda.

---

## 14. When NOT To Use Redis
- **Jangan jadikan Redis sebagai Primary Source of Truth Database:** Meskipun Redis memiliki persistensi RDB/AOF, Redis tidak didesain untuk transaksi relasional kompleks (*No foreign keys, limited ACID guarantees across sharded nodes*). Gunakan PostgreSQL/MySQL sebagai penyimpan data permanen primer.

---

## 15. Common Mistakes
1. **Menggunakan `KEYS *` di Server Produksi:** Kesalahan nomor satu developer pemula yang melumpuhkan sistem.
2. **Tidak Memasang Password / Bind All Interfaces (`0.0.0.0`):** Menjalankan Redis tanpa password di port 6379 publik. Ribuan server Redis di dunia terinfeksi malware penambang kripto (*cryptominer*) setiap hari karena kelalaian ini!
3. **Mengabaikan Memory Fragmentation Ratio:** Jika `used_memory_rss / used_memory > 1.5`, artinya 50% memori dialokasikan terfragmentasi oleh allocator sistem operasi. Server bisa kehabisan RAM fisik meskipun data Redis sebenarnya masih sedikit.

---

## 16. Best Practices

- **Must Have:**
  - Nonaktifkan atau rename perintah berbahaya di `redis.conf`: `rename-command KEYS ""` dan `rename-command FLUSHALL ""`.
  - Pasang autentikasi password yang kuat dan batasi akses jaringan hanya via private VPC subnet.
- **Recommended:**
  - Gunakan **Hash Tags `{tenant_id}:...`** pada penamaan kunci di Redis Cluster.
  - Setel `appendfsync everysec` pada konfigurasi AOF.
- **Advanced:**
  - Gunakan teknik **Client-Side Caching (Redis 6 Tracking API)**: Aplikasi backend menyimpan cache lokal di memori prosesnya sendiri, dan Redis server secara otomatis mengirimkan sinyal pembatalan (*invalidation message*) jika kunci tersebut diubah oleh instance lain.
- **Avoid / Overengineering:**
  - Mengonfigurasi Redis Cluster 12 node jika total data cache Anda hanya 2 Gigabyte.

---

## 17. Troubleshooting Guide
```text
Gejala: Response time Redis tiba-tiba melonjak dari 0.5ms menjadi 300ms.
----------------------------------------------------------------------
Penyebab:
1. Ada developer yang mengeksekusi perintah berat (seperti KEYS *, SMEMBERS pada set 1 juta item).
2. Server mengalami Memory Swapping (RAM habis, OS memindahkan memori Redis ke disk swap!).

Cara Diagnosa:
- Periksa perintah terlambat:
  redis-cli SLOWLOG GET 10
- Cek status swap:
  redis-cli INFO memory | grep swapped

Solusi:
- Matikan Linux swap untuk proses Redis.
- Ganti perintah O(N) ke O(1) atau gunakan SCAN.
```

---

## 18. Hands-on Lab: Simulator Redis 16.384 Hash Slots & Sharding Cluster

File lab sudah disiapkan di:
`System-Design/BAB-04-Caching-Terdistribusi/hands-on/m03/redis_cluster_sim.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-04-Caching-Terdistribusi/hands-on/m03/redis_cluster_sim.js
```

### Yang Ditampilkan Script Ini:
1. Menghitung pemetaan **Hash Slot** menggunakan formula standar industri **CRC16 % 16384**.
2. Membuktikan bagaimana kunci acak tersebar merata di antara 3 Master Node.
3. Membuktikan keampuhan **Hash Tags `{...}`** dalam memaksa data terkait (misal: profile, cart, orders milik user yang sama) mendarat di node fisik yang persis sama.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan 3 alasan mengapa Redis tetap mampu memproses ratusan ribu request per detik meskipun core engine-nya berjalan pada single-thread!

### Level 2 (Medium):
Jelaskan perbedaan mendasar antara mekanisme persistensi data **RDB (Snapshotting)** dan **AOF (Append-Only File)** pada Redis dalam hal keandalan data (*durability*) dan kecepatan restart server!

### Level 3 (Hard):
Pada arsitektur Redis Cluster yang memiliki 16.384 hash slots yang dibagi ke 3 Master Node:
1. Apa yang memicu error `CROSSSLOT Keys in request don't hash to the same slot` saat menjalankan perintah multi-key?
2. Bagaimana teknik **Hash Tags** memecahkan masalah tersebut secara matematis tanpa merusak distribusi sharding data lainnya?

---

## 20. Summary & Knowledge Check
- [ ] Memahami perbedaan arsitektural Redis vs Memcached.
- [ ] Menguasai 6 struktur data utama Redis dan use case idealnya.
- [ ] Memahami trade-off persistensi RDB vs AOF.
- [ ] Menguasai cara kerja Redis Sentinel (Failover) dan Redis Cluster (16.384 Hash Slots).
- [ ] Memahami bahaya perintah $O(N)$ (seperti `KEYS *`) dan solusi kursor `SCAN`.
