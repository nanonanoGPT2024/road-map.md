---
[⬅️ Module 02: Redis Internals & Distributed Lock](./Module-02-Redis-Internals-Distributed-Lock-dan-Cache-Stampede.md) | [📋 Silabus Induk](../README.md) | [BAB 07: Message Brokers & Async Processing ➡️](../BAB-07-Asynchronous-Processing-dan-Message-Brokers/Module-01-Message-Queues-vs-Event-Streaming-Kafka-RabbitMQ.md)
---

# BAB 06: Evaluasi Pemahaman, Quiz, & Tantangan Arsitektur Caching & In-Memory Stores

Selamat! Anda telah menyelesaikan seluruh modul pada **BAB 06: Strategi Caching & In-Memory Stores**. Dokumen ini menguji pemahaman menyeluruh Anda mengenai struktur data memori, algoritma eviksi, arsitektur Redis, serta mitigasi bencana sistem cache skala tinggi.

---

## 1. Pertanyaan Konseptual Fundamental (Basic)

1. **Jelaskan hierarki latensi komputasi dari CPU Cache L1, RAM, SSD NVMe, hingga Jaringan/Database!** Mengapa selisih latensi antara RAM dan database mencapai skala $10.000\times$ hingga $100.000\times$?
2. **Apa perbedaan mendasar antara pola Cache-Aside (Lazy Loading) dan Write-Through Cache?** Pada kondisi beban kerja (*workload*) seperti apa Write-Through lebih unggul dibanding Cache-Aside?
3. **Mengapa algoritma Least Recently Used (LRU) diimplementasikan menggunakan kombinasi Doubly Linked List dan Hash Map?** Mengapa linked list tunggal (*Singly Linked List*) tidak mampu mencapai kompleksitas $O(1)$ saat pemindahan node ke posisi Head?
4. **Mengapa eksekusi perintah di Redis bersifat Single-Threaded, namun tetap mampu memproses ratusan ribu request per detik?** Apa peran kernel I/O Multiplexing (`epoll`) di sini?
5. **Jelaskan perbedaan fungsi antara struktur data Redis Set dan Redis Sorted Set (ZSET)!** Struktur data internal apa yang digunakan Redis untuk menjamin kompleksitas $O(\log N)$ pada ZSET?

---

## 2. Pertanyaan Analisis & Rekayasa Sistem (Intermediate)

6. **Analisis Bahaya `KEYS *` vs `SCAN` di Redis:**
   Mengapa perintah `KEYS *` dilarang keras dijalankan pada server produksi berkapasitas jutaan kunci? Bagaimana perintah `SCAN` bekerja secara inkremental menggunakan *cursor* tanpa membekukan thread utama Redis?
7. **Distributed Lock Atomicity & Failsafe:**
   Mengapa perintah pelepasan kunci (*Unlock*) pada Redis Distributed Lock **wajib** menggunakan Lua Script yang memverifikasi kecocokan token UUID acak, dan tidak boleh hanya memanggil `DEL key` secara langsung?
8. **Dilema Write-Back (Write-Behind) Caching:**
   Jika sebuah arsitektur backend menggunakan pola Write-Back untuk meredam lonjakan penulisan ke database relasional, skenario kegagalan bencana (*Disaster Scenario*) apa yang paling berbahaya, dan strategi mitigasi apa yang wajib diterapkan?
9. **Kardinalitas Masif dengan HyperLogLog:**
   Sebuah portal e-commerce ingin menghitung jumlah pengunjung unik harian (*Daily Unique Visitors*) yang mencapai 50 juta user. Bandingkan efisiensi memori antara menyimpan ID user di Redis Set biasa vs Redis HyperLogLog (`PFADD` / `PFCOUNT`)!
10. **Redlock Algorithm vs Single-Instance Lock:**
    Apa yang membedakan implementasi Redlock pada cluster multi-master terdistribusi dibanding lock pada single Redis instance? Masalah sinkronisasi waktu (*Clock Drift*) dan pause garbage collection apa yang dikritisi oleh Martin Kleppmann terhadap Redlock?

---

## 3. Studi Kasus Skenario Produksi (Scenario-Based)

### Skenario A: Bencana Cache Breakdown pada Flash Sale Smartphone
Pada pukul 12:00:00, sebuah marketplace membuka penjualan flash sale smartphone seharga Rp 1.000. Data produk tersimpan di Redis dengan kunci `cache:product:flash_phone_01` dengan TTL tepat 1 jam (berakhir pukul 12:00:00).
Tepat saat penjualan dimulai, 100.000 request per detik masuk. Kunci tepat habis masa berlakunya. Seluruh 100.000 request mengalami *Cache Miss* serentak dan menyerang database PostgreSQL utama. Database langsung kehabisan koneksi (*Connection Pool Exhaustion*) dan mengalami crash total.
- **Identifikasi Bencana:** Jelaskan mengapa fenomena ini disebut *Cache Breakdown / Thundering Herd*!
- **Solusi Arsitektur:** Rancang solusi menggunakan kombinasi **Distributed Mutex Lock** dan algoritma **Probabilistic Early Expiration (XFetch)** agar data diperbarui secara halus di latar belakang tanpa ada user yang mengalami latensi database!

### Skenario B: Serangan Cache Penetration oleh Botnet
Sebuah platform perbankan mendeteksi lonjakan trafik anomali dari ribuan IP acak yang mengirimkan query pengecekan status transfer dengan format UUID yang di-generate secara acak (`GET /api/transfers/random-fake-uuid-9988`).
Karena ID tersebut tidak ada di Redis Cache, setiap request selalu berlanjut menjadi query `SELECT * FROM transfers WHERE uuid = ...` di database relasional, memicu utilisasi disk I/O 100%.
- **Analisis Kerentanan:** Mengapa strategi Cache-Aside standar tidak berdaya menghadapi serangan *Cache Penetration* ini?
- **Rancang Mitigasi Berlapis:** Bagaimana kombinasi **Bloom Filter** di lapisan gateway dan penyimpanan **Negative/Null Caching** (dengan TTL 30 detik) mampu menangkis 99.9% request palsu tersebut?

### Skenario C: Cache Avalanche Pasca Restart Cluster
Sebuah tim DevOps melakukan restart pada cluster Redis utama yang menampung 5 juta item cache. Karena seluruh skrip seeding memuat data dengan TTL seragam ($3600 \text{ detik}$ persis), tepat satu jam kemudian sistem mengalami degradasi performa ekstrem karena jutaan kunci kedaluwarsa di detik yang persis sama.
- **Identifikasi Masalah:** Apa yang membedakan *Cache Avalanche* dengan *Cache Breakdown*?
- **Solusi Implementasi:** Tuliskan formula penambahan **Random Jitter** pada penentuan nilai TTL di level aplikasi backend!

---

## 4. Chapter Challenge: High-Throughput Leaderboard & Rate-Limiter Engine

### Deskripsi Masalah
Anda ditunjuk sebagai Principal Backend Architect untuk game multiplayer online skala global dengan 5.000.000 pemain aktif harian:
1. **Fitur 1 - Real-time Global Leaderboard:**
   - Sistem harus menampilkan Top 100 pemain dengan skor tertinggi secara real-time.
   - Pemain dapat melihat peringkat (*Rank*) pribadi mereka di antara 5 juta pemain dalam waktu $< 5 \text{ ms}$.
   - Setiap kali pemain menyelesaikan pertandingan, skor mereka langsung diupdate.
2. **Fitur 2 - Sliding Window Rate Limiter:**
   - Setiap akun pemain dibatasi maksimal mengirimkan 100 aksi permainan per menit untuk mencegah bot cheat.
   - Algoritma harus presisi (*Sliding Window Log / Counter*), bukan *Fixed Window* yang rentan terhadap lonjakan batas tepi (*Boundary Burst*).

### Instruksi Pengerjaan
Rancang dokumen arsitektur dan spesifikasi teknis yang mencakup:
1. **Pilihan Struktur Data Redis:** Rancang perintah Redis spesifik (`ZADD`, `ZREVRANGE`, `ZREVRANK`, `ZREMRANGEBYSCORE`) untuk melayani kedua fitur di atas.
2. **Estimasi Kebutuhan RAM:** Hitung estimasi penggunaan RAM server Redis untuk menyimpan 5.000.000 record leaderboard dan data rate limiter pengguna aktif.
3. **Strategi Replikasi & Failover:** Rancang konfigurasi Redis Sentinel / Cluster untuk menjamin zero-downtime saat node master mengalami kegagalan hardware.

---

## 5. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Hierarki latensi komputasi dan dampak ekonomis caching terhadap database primer.
- [ ] 4 pola arsitektur caching: Cache-Aside, Write-Through, Write-Back, dan Write-Around.
- [ ] Struktur data $O(1)$ untuk implementasi algoritma eviksi LRU (Doubly Linked List + Hash Map).
- [ ] Arsitektur internal Redis: I/O Multiplexing single-threaded dan ragam struktur datanya.
- [ ] Pola Distributed Lock yang aman menggunakan token UUID dan eksekusi pelepasan via Lua Script.
- [ ] 4 bencana cache (Stampede, Penetration, Breakdown, Avalanche) serta penangkalnya masing-masing.

### Saya Tidak Perlu Menghafal:
- Seluruh 200+ perintah CLI Redis (cukup kuasai perintah inti untuk String, Hash, Set, ZSET, dan Stream).
- Formula konstanta internal Redis hash table resizing (`dict.c`).

### Saya Harus Bisa Melakukan:
- [ ] Menulis modul caching dengan penanganan invalidasi yang bebas dari *race condition*.
- [ ] Mengimplementasikan distributed mutex yang aman dengan batas sewa TTL (*Lease Timeout*).
- [ ] Menerapkan Bloom Filter atau negative caching untuk menghentikan serangan *Cache Penetration*.
- [ ] Menambahkan random jitter pada TTL untuk meniadakan risiko *Cache Avalanche*.

---
[⬅️ Module 02: Redis Internals & Distributed Lock](./Module-02-Redis-Internals-Distributed-Lock-dan-Cache-Stampede.md) | [📋 Silabus Induk](../README.md) | [BAB 07: Message Brokers & Async Processing ➡️](../BAB-07-Asynchronous-Processing-dan-Message-Brokers/Module-01-Message-Queues-vs-Event-Streaming-Kafka-RabbitMQ.md)
---
