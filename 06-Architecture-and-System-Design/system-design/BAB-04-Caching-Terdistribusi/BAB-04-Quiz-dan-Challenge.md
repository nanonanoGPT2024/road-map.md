# EVALUASI BAB 04: Caching Terdistribusi & Strategi Optimasi Data

Dokumen evaluasi ini berisi ringkasan materi, kuis pemahaman, dan tantangan arsitektur sistem caching untuk menguji kesiapan Anda sebelum masuk ke **BAB 05: Arsitektur Basis Data & Skalabilitas Data**.

---

## 📌 Chapter Summary (Rangkuman BAB 04)

Sepanjang BAB 04, Anda telah mempelajari strategi dan arsitektur caching dari level mikro hingga cluster terdistribusi:
1. **Module 01 (Caching Layers & Pola Akses Data):**
   - Hierarki latensi RAM (100 ns) vs Disk SSD (150 μs) vs Jaringan (30 ms).
   - 4 Pola akses: **Cache-Aside (Lazy Loading)**, **Read-Through**, **Write-Through**, dan **Write-Behind (Write-Back)**.
   - Aturan emas invalidasi: *Write to Database first, then Delete from Cache* untuk mencegah race condition.
2. **Module 02 (Eviction Policies & Mitigasi Anomali Caching):**
   - Kebijakan penggusuran memori: LRU, LFU, FIFO, dan Random.
   - Struktur data LRU Cache $O(1)$ (Hash Map + Doubly Linked List).
   - 4 Anomali mematikan: Cache Stampede (Dogpiling), Cache Penetration, Cache Avalanche, dan Cache Breakdown.
   - Teknik pertahanan: Mutex Singleflight, Bloom Filter, Null Caching, dan TTL Jitter.
3. **Module 03 (In-Memory Datastores: Redis vs Memcached & Cluster):**
   - Arsitektur single-threaded event loop Redis vs multi-threaded Memcached.
   - 6 Tipe data unggulan: String, Hash, List, Set, Sorted Set (ZSET), Bitmap.
   - Persistensi data: Snapshotting RDB vs Logging AOF.
   - Skalabilitas horizontal: 16.384 Hash Slots, CRC16 Sharding, dan Hash Tags `{...}` untuk mencegah Cross-Slot Error.

---

## 📝 BAB 04 QUIZ (Uji Pemahaman)

### Bagian A: Soal Fundamental (Basic)
1. Berapa perkiraan perbandingan kecepatan pembacaan data dari RAM dibandingkan SSD dan Hard Disk magnetik?
2. Mengapa dalam pola *Cache-Aside*, saat aplikasi memperbarui data di database, langkah terbaik adalah **MENGHAPUS (Delete)** kunci cache terkait, bukan meng-update isinya?
3. Apa perbedaan utama antara kebijakan penggusuran memori *LRU (Least Recently Used)* dan *LFU (Least Frequently Used)*?
4. Apa yang dimaksud dengan anomali *Cache Avalanche*, dan bagaimana cara mencegahnya menggunakan *TTL Jitter*?
5. Mengapa perintah `KEYS *` dilarang keras dieksekusi di server Redis produksi? Perintah non-blocking apa yang wajib digunakan sebagai penggantinya?

### Bagian B: Soal Menengah (Intermediate)
6. Jelaskan risiko terbesar dari pola **Write-Behind (Write-Back) Cache**, dan pada jenis use-case apa pola ini sangat layak digunakan!
7. Bagaimana struktur data **Bloom Filter** mampu mencegah anomali **Cache Penetration** tanpa perlu menyimpan seluruh nilai data di memori?
8. Bagaimana teknik **Mutex Lock / Singleflight** mampu mengeliminasi ribuan query redundan saat terjadi fenomena **Cache Stampede (Dogpiling)**?
9. Jelaskan perbedaan mendasar antara persistensi **RDB (Snapshot)** dan **AOF (Append-Only File)** pada Redis dalam hal risiko kehilangan data (*data durability*) dan kecepatan restart!
10. Pada Redis Cluster yang memiliki 16.384 hash slots, apa fungsi dari sintaks **Hash Tag `{...}`** (misal: `{user:101}:cart` dan `{user:101}:orders`)?

### Bagian C: Scenario-Based Questions (Studi Kasus Arsitektur)
11. **Skenario 1 (Serangan Bot Penetrasi ID Fiktif):**  
    Sebuah API publik `/api/v1/users/:id` dihujani 30.000 requests/detik oleh script hacker yang mengirimkan ID acak seperti `user-uuid-999999-fake`. Server Redis memiliki Cache Miss Ratio 100% dan database PostgreSQL mengalami CPU 100% karena melakukan jutaan pencarian record yang tidak pernah ada. Rancang arsitektur 2 lapis untuk memblokir serangan ini seketika!
12. **Skenario 2 (Leaderboard Game Skala 10 Juta Pemain):**  
    Game online mobile memiliki 10 juta pemain aktif. Pemain menuntut fitur papan peringkat real-time (*Top 100 Global Players*) yang diperbarui setiap detik. Jelaskan mengapa query SQL relasional `SELECT * FROM players ORDER BY score DESC LIMIT 100` akan melumpuhkan database, dan bagaimana struktur data **Redis Sorted Set (ZSET)** memecahkan masalah ini dengan kompleksitas $O(\log N)$!
13. **Skenario 3 (Out of Memory Crash di Redis):**  
    Sebuah server Redis 16 GB tiba-tiba menolak seluruh perintah penulisan aplikasi dengan error `OOM command not allowed when used memory > 'maxmemory'`. Setelah dicek, parameter `maxmemory-policy` masih bernilai default `noeviction` dan ribuan kunci di-set tanpa TTL. Langkah darurat apa yang harus dilakukan di level konfigurasi untuk memulihkan layanan tanpa me-restart server?

---

## 🏆 CHAPTER CHALLENGE: Merancang Caching Tier Flash Sale 11.11

### Misi Arsitek:
Rancang arsitektur tier caching terdistribusi untuk melayani halaman produk Flash Sale e-commerce yang menerima **100.000 requests/detik** pada satu produk diskon terbatas:

### Syarat & Batasan Desain:
1. **Pencegahan Stampede:**  
   Rancang arsitektur agar saat kunci cache produk kadaluwarsa, database utama hanya menerima maksimal 1 query per detik (*Singleflight Protection*).
2. **Atomic Inventory Reservation:**  
   Gunakan struktur data Redis untuk mencatat sisa kuota stok (misal: 100 unit barang) secara atomik tanpa risiko *overselling* / *race condition*.
3. **Write-Behind Analytics:**  
   Rancang pencatatan log klik dan view produk (100.000 views/detik) menggunakan Redis Buffer yang di-flush secara berkala ke database analitik.
4. **Cluster Sharding:**  
   Pastikan data cart, order draft, dan profil user yang bertransaksi menggunakan Hash Tags `{user_id}` agar tidak memicu Cross-Slot Error pada Redis Cluster.

---

## ✅ Knowledge Checklist BAB 04

- [ ] Memahami nomor latensi perangkat keras (L1, RAM, SSD, HDD, Network).
- [ ] Menguasai 4 pola caching: Cache-Aside, Read-Through, Write-Through, Write-Behind.
- [ ] Mampu menerapkan aturan invalidasi *Delete on Write*.
- [ ] Menguasai algoritma penggusuran LRU dan implementasinya dalam $O(1)$.
- [ ] Mampu mendiagnosa dan menangkal Stampede, Penetration, Avalanche, Breakdown.
- [ ] Memahami single-threaded event loop Redis dan 6 struktur data utamanya.
- [ ] Menguasai komparasi persistensi RDB vs AOF.
- [ ] Menguasai sharding Redis Cluster (16.384 Hash Slots) dan Hash Tags.
