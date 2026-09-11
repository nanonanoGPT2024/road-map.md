# BAB 10 — Evaluasi, Quiz, & Chapter Challenge
## Studi Kasus Nyata & Desain Arsitektur End-to-End

---

## 🎯 Ringkasan Bab

Dalam Bab penutup ini, kita telah menggabungkan seluruh konsep fundamental (DNS, Load Balancing, Caching, Sharding, Streaming, Resiliensi, dan Observabilitas) ke dalam 4 studi kasus arsitektur sistem nyata paling terkenal di dunia:
1. **Distributed Rate Limiter**: Mendesain sistem proteksi traffic multi-region dengan Redis cluster, atomic Lua scripting, batch token reservation, dan kebijakan *Fail-Open*.
2. **URL Shortener Global (TinyURL)**: Mengatasi rasio Read-Heavy 100:1, encoding Base62 (3.5 triliun variasi), eliminasi tabrakan ID dengan *Key Generation Service (KGS)*, serta analisis trade-off redirect HTTP 301 vs 302.
3. **Real-Time Chat System (WhatsApp / Discord)**: Mengelola jutaan koneksi *stateful WebSocket*, tracking online presence via heartbeat timeout di Redis, serta membedakan *Fan-Out on Write* (grup kecil) vs *Fan-Out on Read* (server besar).
4. **Social Media Feed & Fan-Out Engine (Twitter / Instagram)**: Menaklukkan *The Celebrity Problem* menggunakan *Hybrid Fan-Out Architecture* yang menggabungkan pre-computed materialized timeline cache dengan on-the-fly multi-way merge sort.

---

## 🧠 Knowledge Check

### Saya Harus Memahami:
- [ ] Mengapa distributed rate limiter wajib mengadopsi prinsip *Fail-Open* daripada *Fail-Closed* saat cluster cache mengalami gangguan.
- [ ] Mengapa pendekatan *Key Generation Service (KGS)* lebih unggul daripada hashing MD5 dalam mencegah tabrakan ID pada URL shortener.
- [ ] Kapan menggunakan status redirect HTTP 301 (menghemat beban server) vs HTTP 302 (mencatat analitik klik secara akurat).
- [ ] Perbedaan arsitektur antara koneksi stateless (REST) dan stateful (WebSocket) saat di-scale di balik Load Balancer (kebutuhan Session Routing Table).
- [ ] Cara kerja arsitektur Hybrid Fan-Out dalam memisahkan jalur penulisan tweet selebritas dari pengguna reguler.

### Saya Tidak Perlu Menghafal:
- Kode biner protokol internal WhatsApp (Noise Protocol / Signal Protocol frame).
- Implementasi spesifik algoritma ML ranking EdgeRank lama Facebook.

### Saya Harus Bisa Melakukan:
- [ ] Menggambar diagram arsitektur end-to-end lengkap dari Client, CDN, LB, Gateway, Services, Message Bus, Cache, hingga Sharded Databases.
- [ ] Mempertahankan keputusan desain arsitektur dan trade-off-nya dalam wawancara System Design profesional.
- [ ] Menentukan database yang tepat (RDBMS vs NoSQL Key-Value vs Wide-Column) untuk masing-masing domain data.

---

## ❓ Quiz Evaluasi

### Bagian A: Pertanyaan Konseptual Fundamental (5 Soal)
1. **Mengapa algoritma Base62 (62 karakter) lebih cocok digunakan untuk URL Shortener daripada Base64?**
2. **Apa yang dimaksud dengan "The Celebrity Problem" pada sistem linimasa media sosial seperti Twitter?**
3. **Pada sistem chat real-time, mengapa database Wide-Column NoSQL seperti Apache Cassandra atau ScyllaDB lebih disukai untuk menyimpan riwayat pesan daripada MySQL tradisional?**
4. **Apa fungsi dari Session / Routing Registry (seperti Redis) dalam arsitektur multi-server WebSocket?**
5. **Dalam URL Shortener, mengapa status code HTTP 301 dapat merugikan platform yang mengandalkan monetisasi analitik klik iklan?**

### Bagian B: Analisis & Intermediate (5 Soal)
6. **Jelaskan bagaimana teknik "Batch Token Reservation" memangkas 90% traffic network round-trip antara API Gateway dan Redis Cluster pada Distributed Rate Limiter.**
7. **Jika Key Generation Service (KGS) mati mendadak, apakah URL yang sudah ada tetap bisa diakses dan dialihkan? Jelaskan alasannya.**
8. **Mengapa sistem chat Discord memilih strategi "Fan-Out on Read" untuk channel publik dengan 100.000 member alih-alih menduplikasi pesan ke inbox masing-masing user?**
9. **Bagaimana arsitektur Twitter menangani situasi ketika seorang pengguna baru saja me-refresh feed, lalu 2 detik kemudian salah satu temannya memposting tweet baru? (Polling vs WebSocket vs Pull-to-refresh).**
10. **Jelaskan bagaimana Presence Service mencegah jutaan query database yang tidak perlu saat mendeteksi status pengguna yang online menggunakan mekanisme TTL Redis.**

### Bagian C: Scenario-Based System Architecture (3 Soal)
11. **Skenario 1: Desain Sistem Pastebin / Gist Skala Global**  
   Pengguna dapat mengunggah blok kode/teks rahasia (maksimal 10 MB per paste) dan membagikan tautan pendeknya. Paste dapat memiliki opsi kedaluwarsa (1 hari, 1 bulan, atau selamanya).
   - Rancang arsitektur penyimpanan (di mana teks disimpan? S3 vs Database?).
   - Bagaimana mekanisme pembersihan otomatis data yang kedaluwarsa tanpa mengunci database utama?

12. **Skenario 2: Livestream Chat pada Konser Online 10 Juta Penonton**  
   Saat konser musik berlangsung, 10 juta penonton mengirim emoji dan pesan chat ke satu ruang obrolan yang sama (100.000 pesan per detik!).
   - Jika semua pesan dikirim ke semua penonton, layar ponsel dan bandwidth pengguna akan langsung hang.
   - Rancang strategi *Message Sampling / Throttling / Conflation* di level gateway untuk menyajikan chat stream yang nyaman dibaca manusia (maksimal 20-30 pesan per detik per layar).

13. **Skenario 3: Sistem E-Commerce Flash Sale iPhone Rp 1.000**  
   Tersedia 100 unit iPhone. Tepat pukul 00:00, sebanyak 2.000.000 pengguna menekan tombol "Beli".
   - Rancang arsitektur end-to-end lengkap dari Edge CDN, Token Bucket Rate Limiter, Virtual Waiting Room (Queue), Redis In-Memory Stock Decrement, hingga Asynchronous Order Processing Worker.
   - Tunjukkan bagaimana Anda menjamin bahwa stok tidak pernah oversold (terjual lebih dari 100 unit) di bawah persaingan konkurensi ekstrem.

---

## 🏆 Chapter Challenge: End-to-End Scalable Ride-Hailing Backend (Gojek / Grab / Uber)

### Problem Statement
Rancang arsitektur backend skala besar untuk layanan transportasi online (Ride-Hailing Platform):
- 1.000.000 Pengemudi aktif yang menyiarkan lokasi GPS (Latitude, Longitude) setiap 4 detik.
- 5.000.000 Penumpang yang mencari pengemudi terdekat dalam radius 3 km.
- Matching Engine yang memasangkan penumpang dengan pengemudi terdekat secara optimal.

### Deliverables:
1. **Location Ingestion Pipeline**:
   - Protokol transmisi lokasi dari aplikasi pengemudi ke backend (WebSocket vs HTTP/2 vs MQTT).
   - Ingestion buffer & Geospatial Indexing (Redis Geo / H3 Hexagonal Hierarchical Spatial Index / Uber H3).
2. **Matching & Dispatch Architecture**:
   - Algoritma pencarian radius geospasial efisien tanpa memindai seluruh database.
   - Lock atomik saat menawarkan order ke pengemudi (mencegah 1 pengemudi menerima 2 order sekaligus).
3. **Real-Time Ride Tracking**:
   - Bagaimana rute perjalanan pengemudi disiarkan secara real-time ke layar ponsel penumpang dengan mulus.
