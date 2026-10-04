# Module 04: Desain Arsitektur — Social Media Feed & Fan-Out Engine (Twitter / Instagram)

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Merancang arsitektur sistem linimasa media sosial (**News Feed System**) berskala ratusan juta pengguna harian.
- Memahami dilema komputasi terbesar dalam arsitektur sosial: **Fan-Out on Write (Push Model)** vs **Fan-Out on Read (Pull Model)**.
- Menyelesaikan fenomena **The Celebrity Problem** (masalah akun dengan puluhan juta pengikut seperti selebritas atau presiden) menggunakan **Hybrid Fan-Out Architecture**.
- Merancang struktur cache memori terdistribusi (Redis Sorted Sets) untuk menghasilkan feed dengan latensi < 50 milidetik.

## 2. Prerequisite
- Memahami Caching terdistribusi dari BAB 04.
- Memahami Message Brokers asinkron dari BAB 07.
- Memahami Back-of-the-Envelope capacity estimation dari BAB 09.

## 3. Concept
News Feed adalah aliran postingan, foto, dan video yang terus diperbarui dari orang-orang, halaman, atau topik yang Anda ikuti (*friends & followings*). Pada skala ratusan juta pengguna aktif, membuat feed bukanlah sekadar menjalankan query database sederhana:
`SELECT * FROM posts WHERE author_id IN (SELECT following_id FROM follows WHERE user_id = 1) ORDER BY created_at DESC LIMIT 20;`

Query di atas akan **membunuh database seketika** jika dieksekusi oleh 100.000 pengguna per detik yang masing-masing mengikuti 1.000 orang!  
Arsitektur News Feed modern dibangun di atas prinsip **Pre-computed Caching (Materialized Timelines)** di mana linimasa pengguna sudah dihitung dan disiapkan terlebih dahulu di RAM sebelum pengguna membuka aplikasi.

## 4. Why?
- **User Experience (Instant Load)**: Pengguna ponsel mengharapkan feed terbuka seketika (< 100ms) saat aplikasi diluncurkan.
- **Extreme Asymmetry**: Rasio pembacaan feed terhadap pembuatan postingan baru adalah sekitar **100 : 1** atau **500 : 1** (jauh lebih banyak pembaca pasif daripada kreator aktif).

## 5. What?
### Tiga Paradigma Fan-Out:
1. **Fan-Out on Write (Push Model)**:
   - Saat pengguna membuat postingan baru, server mencari seluruh followers pengguna tersebut.
   - Server menyuntikkan ID postingan baru langsung ke dalam **Timeline Cache di Redis milik masing-masing follower**.
   - **Kelebihan**: Waktu baca (*Read Path*) sangat cepat ($O(1)$) karena feed sudah tersusun rapi di cache memori.
   - **Kelemahan Fatal**: *The Celebrity Problem*. Jika seorang selebritas dengan 100 juta followers mem-posting tweet, server harus melakukan 100 juta operasi penulisan cache ke Redis dalam hitungan detik!
2. **Fan-Out on Read (Pull Model)**:
   - Saat pengguna mem-posting tweet, data hanya ditulis satu kali ke tabel postingannya sendiri ($O(1)$ write).
   - Saat follower membuka aplikasi, sistem membaca postingan terbaru dari semua orang yang diikutinya, lalu menggabungkan dan mengurutkannya (*multi-way merge sort*).
   - **Kelebihan**: Pembuatan postingan sangat cepat dan murah.
   - **Kelemahan**: Memuat feed menjadi sangat lambat ($O(N)$ query) dan membebani server backend setiap kali pengguna me-refresh halaman.
3. **Hybrid Fan-Out Model (Solusi Twitter / Instagram)**:
   - **Pengguna Reguler (< 25.000 followers)**: Gunakan **Fan-Out on Write**. Postingan mereka di-push langsung ke timeline teman-temannya.
   - **Selebritas / Akun VIP (> 25.000 followers)**: **JANGAN di-fan-out saat menulis**. Simpan postingan selebritas di cache terpisah. Saat follower membuka feed, gabungkan (*merge on-the-fly*) timeline reguler dari Redis dengan beberapa postingan selebritas terbaru.

## 6. How?
### Alur Hybrid Feed Engine:
```text
ALUR PENULISAN (WRITE PATH):
[User Post Tweet] ──> [Post Service] ──> [Database & Kafka]
                             │
                             ▼
                     [Fan-Out Workers]
                             │
                 Apakah User adalah Selebritas?
                 ├── YA  (> 25k followers) ──> Simpan hanya di [Celebrity Post Cache] (Stop!)
                 │
                 └── TIDAK (Reguler) ────────> Query Followers ──> Push ke [User Timeline Caches]
                                                                        (Redis ZSET)

ALUR PEMBACAAN (READ PATH):
[User Buka Aplikasi] ──> [Feed Service]
                               │
                               ├── 1. Ambil 50 Tweet dari [User Timeline Cache] (Redis ZSET)
                               │
                               ├── 2. Cek apakah User mengikuti Selebritas?
                               │      └── Ambil Tweet terbaru Selebritas dari [Celebrity Cache]
                               │
                               ├── 3. Merge & Sort berdasarkan Timestamp (atau ML Ranker)
                               │
                               └── 4. Kembalikan 20 Tweet Teratas ke Mobile App (< 50ms)
```

## 7. Analogy
- **Fan-Out on Write = Mengantar Koran Pagi ke Kotak Surat Setiap Rumah**: Setiap pagi kurir memasukkan koran ke kotak surat 100 pelanggan. Saat pelanggan bangun tidur, mereka cukup membuka kotak surat di depan pintu rumahnya dan langsung membaca tanpa menunggu.
- **The Celebrity Problem = Presiden Berpidato**: Jika presiden harus mengirim surat fisik ke 270 juta warga negara tiap kali berbicara, kantor pos akan bangkrut. Solusinya: presiden berbicara di stasiun TV nasional (Pull Model), dan warga cukup menyalakan TV mereka untuk mendengar pidato tersebut saat mereka ingin menonton.

## 8. Diagram

```text
================ STRUCTURE TIMELINE CACHE DI REDIS (ZSET) ================
Key: "timeline:user_99" (Redis Sorted Set)
Score: Unix Timestamp (ms) | Value: PostID

Score: 1789099900  ──>  Value: "POST_8812" (Tweet Teman A)
Score: 1789099850  ──>  Value: "POST_7719" (Tweet Teman B)
Score: 1789099700  ──>  Value: "POST_6601" (Tweet Teman C)

Query Cepat (Ambil 20 Tweet Terbaru):
ZREVRANGEBYSCORE timeline:user_99 +inf -inf LIMIT 0 20
(Eksekusi sub-milidetik di RAM!)
```

## 9. Simple Example: Struktur Penyimpanan Cache Feed
Setiap pengguna aktif di sistem hanya menyimpan daftar referensi `post_id` (misal 800 tweet terakhir) di Redis, bukan seluruh teks postingan atau gambar:
- Ukuran 1 record: 8 byte integer.
- 800 tweet per user: $800 \times 8 \text{ byte} = 6.4 \text{ KB RAM per user}$.
- 100 Juta Pengguna Aktif: $100.000.000 \times 6.4 \text{ KB} \approx 640 \text{ GB RAM}$.
Sebuah kluster Redis kecil sudah mampu menampung linimasa ratusan juta pengguna! Saat ID diambil, API Gateway melakukan *Hydration* (mengambil teks dan avatar dari cache produk/user).

## 10. Practical Example: Menghemat Resource untuk Pengguna Tidak Aktif
Jangan lakukan fan-out ke pengguna yang tidak pernah membuka aplikasi selama 30 hari!  
**Pola Optimasi Arsitektur**:
Fan-out worker memeriksa status login terakhir: jika follower sudah tidak aktif lebih dari 14 hari, abaikan pembaruan cache untuknya. Jika suatu hari dia login kembali, sistem akan membangun ulang linimasanya secara malas (*lazy rebuild*).

## 11. Real World Example
- **Twitter (X)**: Membangun arsitektur *Timelines* berbasis Redis (*Timeline Service*) yang menerapkan strategi hybrid fan-out secara ketat untuk menangani akun dengan puluhan juta pengikut tanpa menimbulkan lonjakan latensi di message broker.
- **Instagram**: Menggunakan arsitektur multi-layer ranking di mana feed kronologis awal disaring kembali oleh model Machine Learning (Distillation Engine) untuk mengurutkan foto berdasarkan relevansi interaksi (Like, Comment, Watch Time).

## 12. Trade-offs

| Parameter | Fan-Out on Write (Push) | Fan-Out on Read (Pull) | Hybrid Architecture |
|---|---|---|---|
| **Latensi Baca Feed** | Sangat Cepat (< 10ms) | Lambat (100 - 500ms) | **Cepat (< 30ms)** |
| **Beban Tulis Postingan**| Sangat Berat jika ada selebritas | Sangat Ringan | Seimbang |
| **Kebutuhan RAM Cache** | Tinggi (Simpan timeline per user)| Sangat Hemat | Menengah |
| **Kompleksitas Kode** | Rendah | Rendah | Sedang - Tinggi |

## 13. When To Use
- Aplikasi linimasa sosial (Twitter, Facebook, LinkedIn, Threads, Instagram).
- Activity stream pada aplikasi kolaborasi (GitHub feed, Jira activity log).

## 14. When NOT To Use
- Aplikasi pencarian berbasis katalog statis (e-commerce catalog search).

## 15. Common Mistakes
1. **Melakukan Fan-Out Sinkron**: Menjalankan loop pengiriman ke 50.000 followers secara sinkron di thread HTTP request pembuat postingan. Request HTTP akan mengalami timeout! Selalu delegasikan fan-out ke background message broker (Kafka/RabbitMQ).
2. **Menyimpan Blob Data Utuh di Redis Feed**: Menyimpan teks caption, metadata, dan URL foto di dalam setiap list timeline user akan memboroskan memori ratusan Terabyte. Simpan hanya `post_id` di timeline cache!

## 16. Best Practices
- **Batasi Ukuran Timeline Cache**: Batasi daftar feed maksimal 500 hingga 1.000 postingan per pengguna (`LTRIM` atau `ZREMRANGEBYRANK`). Pengguna jarang sekali melakukan scroll mundur hingga postingan ke-1.000.
- **Pagination Berbasis Cursor**: Dilarang menggunakan `OFFSET` SQL untuk pagination feed. Gunakan `cursor` berbasis `created_at` timestamp atau `post_id` untuk mencegah pergeseran duplikasi saat ada postingan baru (*feed shifting*).

## 17. Troubleshooting
- **Masalah: Message Broker tertinggal jutaan antrian (*Consumer Lag*) setiap kali selebritas memposting foto**.
  - *Sebab*: Akun selebritas belum ditandai dalam VIP List, sehingga fan-out worker mencoba melakukan jutaan penulisan cache.
  - *Solusi*: Otomatiskan penandaan status selebritas di database jika jumlah pengikut melampaui ambang batas 25.000 orang.

## 18. Hands-on Practice
Mari kita buktikan arsitektur Hybrid Fan-Out Engine nyata: mendeteksi akun selebritas vs reguler, push ke timeline Redis follower, dan on-the-fly merge sort saat pembacaan feed di `hands-on/m04/social_feed_engine.js`.

## 19. Exercises & Challenge
- **Exercise**: Jika Akun A memiliki 5.000 followers, Akun B memiliki 2.000.000 followers, dan sistem memiliki ambang batas selebritas 25.000 followers:
  1. Strategi apa yang digunakan saat Akun A memposting tweet? (Jawaban: Fan-Out on Write / Push ke 5.000 follower).
  2. Strategi apa yang digunakan saat Akun B memposting tweet? (Jawaban: Pull Model / Disimpan di Celebrity cache).
- **Challenge**: Rancang skema *Unfollow / Block* pengguna: jika User X meng-unfollow User Y, bagaimana cara membersihkan postingan User Y dari timeline cache User X secara efisien tanpa scan memori besar?

## 20. Summary
Sistem linimasa sosial berskala raksasa tidak dapat dibangun hanya dengan mengandalkan query database relasional dinamis. Dengan menerapkan **Pre-computed Materialized Views** di Redis, membatasi payload hanya pada pointer ID, dan menerapkan **Hybrid Fan-Out Architecture** untuk menaklukkan *Celebrity Problem*, sistem linimasa mampu menyajikan miliaran postingan dengan kecepatan sub-detik.
