# MODULE 02: Eviction Policies & Mitigasi Anomali Caching

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Membandingkan algoritma penggusuran memori (*Eviction Policies*): **LRU (Least Recently Used)**, **LFU (Least Frequently Used)**, **FIFO**, dan **Random**.
2. Mengimplementasikan struktur data **LRU Cache $O(1)$** menggunakan kombinasi **Hash Map + Doubly Linked List**.
3. Mendiagnosa dan memitigasi 4 anomali mematikan pada sistem caching berskala besar:
   - **Cache Stampede / Dogpiling** (Badai penyerbuan database saat kunci hot kadaluwarsa).
   - **Cache Penetration** (Serangan query data yang tidak pernah ada di database).
   - **Cache Avalanche** (Runtuhnya ribuan kunci cache secara bersamaan pada detik yang sama).
   - **Cache Breakdown** (Satu data super-viral kadaluwarsa seketika).
4. Menerapkan teknik pertahanan: **Distributed Mutex Lock / Singleflight**, **Bloom Filter**, **Null Caching**, dan **TTL Jitter**.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 04 — Module 01: Caching Layers & Pola Akses Data](./Module-01-Caching-Layers-dan-Pola-Akses.md).
- Memahami struktur data dasar: Hash Map dan Pointer / Linked List.

---

## 3. Concept
Memori RAM pada server cache (seperti Redis atau Memcached) berukuran terbatas (misal 16 GB atau 64 GB), sedangkan total data di database Anda bisa mencapai Terabyte. 

Ketika kuota memori maksimum (*maxmemory limit*) tercapai, server cache harus memutuskan: **Data mana yang harus dibuang (*evicted*) dari RAM untuk memberi ruang bagi data baru yang masuk?** Kebijakan pembuangan ini disebut **Cache Eviction Policy**.

Selain keterbatasan ruang, sistem caching skala besar rentan terhadap fenomena ketidakstabilan traffic di mana kegagalan kecil pada layer cache dapat melipatgandakan beban ke database utama hingga menyebabkan *total system outage*.

---

## 4. Why? (Mengapa Eviction & Anomali Caching Sangat Berbahaya?)

### Bencana Cache Stampede (Dogpiling) pada Event Flash Sale
Bayangkan sebuah produk iPhone 16 diskon 90% di-cache di Redis dengan kunci `product:iphone16` dan TTL 10 menit.
- Ada **20.000 requests/detik** yang membaca kunci ini dari Redis.
- Pada detik ke-600, **kunci tersebut kadaluwarsa (expired)**.
- Dalam jendela waktu 200 milidetik saat backend sedang mencoba mengambil data baru ke database:
  **4.000 requests konkuren serentak mendapati Cache MISS!**
- Ke-4.000 request tersebut secara bersamaan menembakkan query SQL `SELECT * FROM products WHERE id = 'iphone16'` ke database PostgreSQL.
- Database PostgreSQL seketika kehabisan connection pool, CPU 100%, disk I/O terkunci, dan seluruh sistem e-commerce mati total (*Cascading Crash*).

---

## 5. What? (Eviction Policies & 4 Anomali Caching)

### A. Algoritma Eviction Policies

| Kebijakan | Cara Kerja | Kelebihan | Kelemahan |
|---|---|---|---|
| **LRU (Least Recently Used)** | Membuang data yang paling lama tidak diakses | Sangat adaptif terhadap perubahan tren data | Rentan terhadap scanning masif 1 kali |
| **LFU (Least Frequently Used)** | Membuang data yang total frekuensi hit-nya paling sedikit | Mempertahankan data populer jangka panjang | Data lama yang dulu viral susah terhapus |
| **FIFO (First In, First Out)** | Membuang data yang paling awal masuk | Sederhana, zero overhead tracking | Membuang data penting yang sering diakses |
| **Random Eviction** | Membuang data secara acak | Sangat ringan, tanpa struktur data tambahan | Tidak efisien untuk hit-ratio |

---

### B. 4 Anomali Caching Mematikan & Solusinya

```text
+---------------------+---------------------------------------+---------------------------------------+
| Fenomena Anomali    | Karakteristik Masalah                 | Solusi Arsitektural                   |
+---------------------+---------------------------------------+---------------------------------------+
| 1. Cache Stampede   | Kunci super-populer expired, ribuan   | Mutex Lock / Singleflight             |
|    (Dogpiling)      | request konkuren menembus ke DB.      | Probabilistic Early Expiration (XFetch)|
+---------------------+---------------------------------------+---------------------------------------+
| 2. Cache Penetration| User/Hacker me-request ID fiktif      | Bloom Filter di depan cache           |
|                     | yang tidak ada di DB, DB dihujani scan| Cache Null Value dengan short TTL     |
+---------------------+---------------------------------------+---------------------------------------+
| 3. Cache Avalanche  | Ribuan kunci cache disetel TTL sama   | Berikan TTL Jitter (variasi acak)     |
|                     | sehingga expired serentak detik yang  | Arsitektur High Availability Redis    |
|                     | sama, melumpuhkan database.           |                                       |
+---------------------+---------------------------------------+---------------------------------------+
| 4. Cache Breakdown  | Satu kunci hot spesifik tiba-tiba     | Mutex Lock pada key tersebut          |
|                     | lenyap atau expired.                  | Refresh-Ahead di background           |
+---------------------+---------------------------------------+---------------------------------------+
```

---

## 6. How? (Struktur Data LRU Cache $O(1)$ & Mutex Singleflight)

### 1. Struktur Data LRU Cache: Hash Map + Doubly Linked List
Untuk mencapai kompleksitas waktu **$O(1)$ pada operasi `get()` dan `put()`**:
- **Hash Map:** Menyediakan pencarian cepat dari `Key` ke `Node Pointer` dalam $O(1)$.
- **Doubly Linked List:** Memungkinkan pemindahan node ke posisi paling depan (*Most Recently Used / Head*) dan penghapusan node dari ujung paling belakang (*Least Recently Used / Tail*) dalam $O(1)$ tanpa menggeser array!

```text
            STRUKTUR DATA LRU CACHE O(1)

        Hash Map: { "A": NodeA, "B": NodeB, "C": NodeC }
                         │            │            │
                         ▼            ▼            ▼
     [ HEAD ] ◄───► [ Node A ] ◄───► [ Node B ] ◄───► [ Node C ] ◄───► [ TAIL ]
   (Paling Baru)                                                (Paling Lama /
                                                                 Kandidat Evict)
```

### 2. Mutex Lock / Singleflight (Pencegah Cache Stampede)
Hanya **satu thread pertama** yang diizinkan mengambil data ke database. Seluruh thread lain yang datang bersamaan dipaksa menunggu hingga thread pertama selesai mengisi cache:

```text
Request 1 (Datang pertama) ──▶ Ambil Mutex Lock ──▶ Query Database ──▶ Isi Cache ──▶ Lepas Lock
Request 2 (Datang detik +1ms)─▶ Gagal Ambil Lock ──▶ Menunggu (Sleep 20ms) ────────▶ Baca Cache HIT!
Request 3 (Datang detik +2ms)─▶ Gagal Ambil Lock ──▶ Menunggu (Sleep 20ms) ────────▶ Baca Cache HIT!
```

---

## 7. Analogy: Meja Prasmanan Restoran & Kertas Pesanan Kosong
- **Cache Stampede:** Panci sup iga di meja prasmanan tiba-tiba habis. Alih-alih satu pelayan yang pergi ke dapur untuk mengambil sepanci sup baru, 500 tamu restoran serentak menyerbu masuk ke dapur dan berteriak menuntut koki memasak sup seketika itu juga. Dapur langsung hancur berantakan.
- **Cache Penetration:** Pelanggan jahat memesan menu "Nasi Goreng Dinosaurus". Pelayan memeriksa meja saji (tidak ada), lalu masuk ke dapur mencari di lemari es (tidak ada). Pelanggan memesan lagi "Nasi Goreng Alien". Koki menghabiskan seluruh waktunya mencari bahan yang mustahil ada.
  - **Solusi Bloom Filter:** Satpam di pintu depan memegang daftar resmi seluruh menu restoran. Begitu pelanggan menyebut "Dinosaurus", satpam langsung berkata: *"Menu itu tidak ada di restoran kami, dilarang masuk!"*

---

## 8. Diagram: Alur Pertahanan Berlapis (Bloom Filter + Mutex)

```text
[ Request Masuk: GET /product/:id ]
                │
                ▼
       [ Bloom Filter ] ──(Pasti Tidak Ada di Database?)──▶ YA ──▶ Tolak 404 (DB Terlindungi!)
                │
                └── TIDAK (Mungkin Ada)
                        │
                        ▼
                 [ Cek Cache ] ──(Cache HIT?)──▶ YA ──▶ Kembalikan Data (RAM ~1ms)
                        │
                        └── CACHE MISS
                                │
                                ▼
                       [ Coba Ambil Mutex ]
                                │
                ┌───────────────┴───────────────┐
                ▼ (Sukses Dapat Lock)           ▼ (Gagal Dapat Lock / Thread Lain)
       [ Query ke Database ]              [ Tunggu 50ms & Cek Cache Ulang ]
                │
       [ Simpan ke Cache ]
                │
       [ Lepas Mutex Lock ]
```

---

## 9. Simple Example: Menambahkan TTL Jitter
Untuk mencegah **Cache Avalanche**, jangan pernah menyetel TTL konstan:
```javascript
// BURUK: Semua kunci expired serentak tepat 1 jam lagi!
const TTL = 3600;

// BAGUS: Berikan variasi acak (Jitter) antara 3600 s/d 4200 detik
const baseTTL = 3600;
const jitter = Math.floor(Math.random() * 600); // 0 s/d 10 menit
const safeTTL = baseTTL + jitter;

await redis.set(key, value, 'EX', safeTTL);
```

---

## 10. Practical Code Example
Lihat implementasi struktur data LRU Cache murni $O(1)$, simulator Cache Stampede vs Mutex Lock, dan Bloom Filter pada:
`System-Design/BAB-04-Caching-Terdistribusi/hands-on/m02/lru_cache_and_stampede.js`

---

## 11. Real World Example: Facebook Memcached Scaling Paper & Algoritma XFetch
- **Facebook Scaling Memcached (NSDI Paper):** Facebook mengoperasikan ribuan server Memcached yang melayani miliaran request/detik. Untuk mengatasi stampede, Facebook mematenkan penggunaan **Leases**: Memcached hanya memberikan satu "lease token" (hak query DB) ke 1 worker saat cache miss. Worker lain disuruh menunggu atau menyajikan data lama yang sudah kadaluwarsa (*stale value*) daripada menembus database.
- **Probabilistic Early Expiration (Algoritma XFetch):** Algoritma yang menghitung probabilitas untuk me-refresh cache di background sebelum TTL habis berdasarkan rumus:
  $$-\beta \times \delta \times \ln(\text{random}()) > \text{Sisa TTL}$$
  Semakin dekat sisa waktu TTL dan semakin lama waktu query database ($\delta$), semakin tinggi kemungkinan salah satu request pembacaan secara proaktif memperbarui cache di background tanpa pernah membiarkan cache kosong!

---

## 12. Trade-offs (LRU vs LFU)

| Dimensi | LRU (Least Recently Used) | LFU (Least Frequently Used) |
|---|---|---|
| **Struktur Data** | Hash Map + Doubly Linked List | Hash Map + Frequency List / Min-Heap |
| **Overhead Memori** | Rendah (hanya 2 pointer per node) | Sedang-Tinggi (butuh counter frekuensi) |
| **Sensitivitas Pola** | Sangat baik untuk tren data dinamis | Sangat baik untuk data stabil jangka panjang |
| **Kelemahan** | Cache burst (batch job) bisa menghapus data penting | Data yang dulu populer sulit terhapus (*Cache Pollution*) |

---

## 13. When To Use What
- **Gunakan LRU (`allkeys-lru` di Redis):** Untuk 90% aplikasi umum di mana data yang baru diakses kemungkinan besar akan diakses kembali.
- **Gunakan LFU (`allkeys-lfu` di Redis):** Untuk platform e-commerce katalog besar di mana 5% produk "Top Best Seller" harus selalu ada di RAM apapun yang terjadi.
- **Gunakan Mutex Lock:** Pada endpoint yang menghasilkan komputasi sangat berat (misal: query laporan analitik bulanan yang memakan waktu 5 detik di database).
- **Gunakan Bloom Filter:** Di depan public search API untuk memblokir bot yang mencoba melakukan enumeration ID (seperti ID pengguna fiktif).

---

## 14. When NOT To Use
- Jangan gunakan Mutex Lock pada request yang waktu query database-nya sangat cepat (< 2 ms) dengan traffic rendah, karena overhead akuisisi lock dan lock contention justru akan menambah latensi tanpa manfaat nyata.

---

## 15. Common Mistakes
1. **Mengabaikan Cache Penetration:** Mengira bahwa database akan aman karena sudah ada cache, padahal ribuan bot scraping terus menembakkan request ID yang tidak ada di database.
2. **Menyetel Memory Limit Redis Tanpa Eviction Policy:** Default konfigurasi Redis saat memori penuh adalah `noeviction` (Redis akan menolak seluruh perintah penulisan baru dan me-return error `OOM command not allowed`). Selalu setel `maxmemory-policy allkeys-lru`!
3. **Mengabaikan Lock Timeout:** Memasang mutex lock pada cache miss tanpa menyetel expiry/timeout pada lock tersebut. Jika thread yang memegang lock crash di tengah eksekusi query database, seluruh request lain akan mengalami deadlock selamanya!

---

## 16. Best Practices

- **Must Have:**
  - Konfigurasikan `maxmemory-policy allkeys-lru` pada Redis.
  - Terapkan **Cache Null Values** dengan TTL pendek (misal 30 detik) untuk menangkal Cache Penetration sederhana jika tidak menggunakan Bloom Filter.
- **Recommended:**
  - Tambahkan **TTL Jitter** acak pada setiap penulisan kunci cache.
  - Terapkan **Distributed Lock dengan Timeout (TTL Lock 5 detik)** untuk mencegah deadlock.
- **Advanced:**
  - Gunakan implementasi **Singleflight pattern** (standar di bahasa pemrograman Go) di layer aplikasi.
- **Avoid / Overengineering:**
  - Mengimplementasikan Bloom Filter rumit untuk aplikasi internal yang seluruh ID-nya sudah terlindungi oleh middleware otentikasi UUID.

---

## 17. Troubleshooting Guide
```text
Gejala: Redis sering crash dan me-return error "OOM command not allowed when used memory > 'maxmemory'".
-----------------------------------------------------------------------------------------------------
Penyebab:
1. maxmemory-policy masih berstatus default 'noeviction'.
2. Terdapat kunci-kunci besar yang tidak memiliki TTL (volatile-lru tidak bisa menghapusnya).

Solusi:
1. Di file redis.conf ubah:
   maxmemory-policy allkeys-lru
2. Jalankan audit kunci besar di terminal:
   redis-cli --bigkeys
```

---

## 18. Hands-on Lab: LRU Cache $O(1)$ & Simulasi Cache Stampede vs Mutex

File lab sudah disiapkan di:
`System-Design/BAB-04-Caching-Terdistribusi/hands-on/m02/lru_cache_and_stampede.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-04-Caching-Terdistribusi/hands-on/m02/lru_cache_and_stampede.js
```

### Yang Ditampilkan Script Ini:
1. Menguji implementasi murni struktur data **LRU Cache** dengan kapasitas 3 item: Membuktikan pembuangan item tertua secara otomatis dalam $O(1)$.
2. Mensimulasikan **Cache Stampede**: 10 request konkuren serentak mendapati cache expired tanpa proteksi (Database dihantam 10 kali secara redundan!).
3. Mensimulasikan mitigasi menggunakan **Mutex Singleflight**: Dari 10 request konkuren, hanya 1 request yang menembus database, sementara 9 request lainnya menunggu dan menerima hasil cache yang baru!

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan perbedaan mendasar antara fenomena *Cache Stampede* dan *Cache Penetration*!

### Level 2 (Medium):
Bagaimana kombinasi struktur data **Hash Map** dan **Doubly Linked List** memungkinkan operasi pembacaan dan pemindahan node pada LRU Cache berjalan dalam kompleksitas waktu $O(1)$? Mengapa Single Linked List atau Array biasa tidak bisa mencapai $O(1)$?

### Level 3 (Hard):
Sebuah botnet mengirimkan 50.000 requests/detik dengan parameter ID acak (`/user/uuid-fiktif-123`) yang tidak pernah terdaftar di database. Jelaskan bagaimana struktur data probabilistik **Bloom Filter** bekerja dengan serangkaian $k$ fungsi hash matematis untuk memblokir 100% request fiktif tersebut tanpa pernah melakukan query disk ke PostgreSQL! Jelaskan pula trade-off fenomena *False Positive* pada Bloom Filter!

---

## 20. Summary & Knowledge Check
- [ ] Memahami perbedaan cara kerja LRU, LFU, FIFO, dan Random Eviction.
- [ ] Menguasai implementasi struktur data LRU Cache $O(1)$ (Hash Map + Doubly Linked List).
- [ ] Menguasai 4 anomali caching: Stampede, Penetration, Avalanche, Breakdown.
- [ ] Mampu menerapkan Mutex Lock / Singleflight untuk meredam Cache Stampede.
- [ ] Memahami peran Bloom Filter dan Null Caching dalam menahan Cache Penetration.
