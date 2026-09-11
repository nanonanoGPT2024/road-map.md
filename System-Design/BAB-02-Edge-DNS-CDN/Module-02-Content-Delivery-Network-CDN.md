# MODULE 02: Content Delivery Network (CDN)

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Menjelaskan arsitektur **Content Delivery Network (CDN)**, termasuk peran **Edge Servers / Points of Presence (PoP)** dan **Origin Shield**.
2. Membedakan secara arsitektural dan operasional antara **Push CDN** dan **Pull CDN**.
3. Mengonfigurasi header HTTP caching modern: `Cache-Control`, `s-maxage`, `ETag`, `If-None-Match`, dan pola `stale-while-revalidate`.
4. Menerapkan strategi **Cache Invalidation** yang aman: Purge by URL, Cache Tags (*Surrogate-Keys*), dan teknik **Cache Busting / Content Hashing**.
5. Menjalankan simulasi performa CDN (*Cache Hit* vs *Cache Miss*) menggunakan script hands-on interaktif.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 02 — Module 01: DNS & Global Traffic Management](./Module-01-DNS-dan-Global-Traffic-Management.md).
- Memahami konsep HTTP Headers dan status code (200 OK, 304 Not Modified).

---

## 3. Concept
**Content Delivery Network (CDN)** adalah jaringan server proxy terdistribusi secara geografis di seluruh dunia (*Points of Presence / PoP*) yang berfungsi menyimpan salinan konten statis maupun dinamis (gambar, video, CSS, JavaScript, HTML, API response) sedekat mungkin dengan lokasi fisik pengguna akhir.

Tujuan utama CDN adalah:
1. **Memangkas Latensi Jaringan:** Memperpendek jarak fisik transmisi data (*Round-Trip Time / RTT*).
2. **Mengurangi Beban Origin Server (*Offloading*):** Menyerap hingga 85% - 98% traffic agar tidak langsung membebani database dan server backend utama Anda.

---

## 4. Why? (Mengapa CDN Wajib Ada di Setiap Sistem Modern?)

### Batasan Kecepatan Cahaya di Kabel Serat Optik
Kecepatan cahaya di dalam kabel serat optik adalah sekitar $200.000 \text{ km/detik}$.
- Jarak bolak-balik (RTT) kabel bawah laut dari Jakarta ke server di Virginia (AS) adalah sekitar $30.000 \text{ km}$.
- Latensi fisik murni (belum termasuk overhead router dan server) = minimal **150 ms - 220 ms** per request!
- Sebuah halaman web rata-rata memuat **60 file aset** (gambar produk, icon, font, bundle script JS). Jika setiap file harus diambil langsung ke server di AS, waktu pemuatan halaman (*Page Load Time*) bisa mencapai **6 hingga 10 detik**!

Dengan CDN: Seluruh aset tersebut disimpan di Edge Server PoP Jakarta. Latensi terpangkas menjadi **< 10 ms**.

---

## 5. What? (Pilar Arsitektur CDN & Strategi Ingestion)

### A. Komponen Utama Arsitektur CDN
1. **Origin Server:** Server backend utama Anda (tempat kode API, database, atau S3 bucket asli berada).
2. **PoP (Point of Presence):** Data center mini milik provider CDN (Cloudflare, CloudFront, Akamai, Fastly) yang tersebar di ratusan kota dunia.
3. **Edge Server:** Mesin server fisik di dalam PoP yang menerima request langsung dari browser pengguna.
4. **Origin Shield:** Lapisan proxy caching perantara antara Edge Server dan Origin Server untuk mencegah *Cache Stampede* jika ratusan PoP serentak melakukan fetch ke Origin.

### B. Push CDN vs Pull CDN

```text
       [ PUSH CDN ]                                    [ PULL CDN ]
Content Creator / CI/CD                         Pengguna Request Aset
         │                                                │
         ▼ (Upload Proaktif Manual)                       ▼
[ Push ke Seluruh PoP Edge ]                    [ Edge Server PoP ]
(Data sudah standby sebelum ada request)                  │
                                           (Cache Miss?)  ├──▶ Tarik dari Origin
                                           (Cache Hit?)   └──▶ Langsung kirim ke User
```

| Dimensi | Push CDN | Pull CDN (Reverse Proxy Cache) |
|---|---|---|
| **Cara Kerja** | Developer meng-upload konten secara proaktif ke CDN | CDN menarik data dari Origin secara reaktif saat ada request pertama |
| **Penyimpanan Storage** | Memakan kuota storage CDN (biaya storage per GB) | Hanya menyimpan data yang sering diakses (LRU eviction) |
| **Kesesuaian Kasus** | File besar yang jarang berubah (Software installer, Video game patch) | Web app, e-commerce, gambar katalog produk, file JS/CSS |
| **Traffic ke Origin** | Nol setelah proses push sukses | Ada lonjakan (*cache miss penalty*) saat aset pertama kali dirilis |

---

## 6. How? (Alur Request CDN & HTTP Header Caching)

```text
[ Browser Pengguna ]
        │
        ▼ 1. Request: GET /assets/app.v1.js
[ Edge Server PoP (Terdekat) ]
        │
        ├──▶ 2. Apakah file ada di disk/RAM Edge dan belum expired?
        │       │
        │       ├── [ YA: CACHE HIT ] ──▶ Kirim langsung (Latensi ~5ms, Status: 200 OK / CF-Cache-Status: HIT)
        │       │
        │       └── [ TIDAK: CACHE MISS ]
        │                 │
        │                 ▼ 3. Tarik data ke [ Origin Server ] (Latensi ~180ms)
        │                 │    Origin merespon dengan Header:
        │                 │    Cache-Control: public, max-age=31536000, immutable
        │                 │
        │                 ▼ 4. Simpan salinan di cache Edge Server
        │                 │
        └─────────────────┴───── Kirim aset ke Browser (CF-Cache-Status: MISS)
```

### Panduan Header HTTP Caching:
```http
Cache-Control: public, max-age=3600, s-maxage=86400, stale-while-revalidate=60
```
- `public`: Respon boleh di-cache oleh browser client DAN intermediate CDN edge proxy.
- `private`: Hanya boleh di-cache oleh browser client individu (dilarang di-cache oleh CDN, misal: halaman `/dashboard` user).
- `max-age=3600`: Umur cache di browser client adalah 3.600 detik (1 jam).
- `s-maxage=86400`: (*Shared Max Age*) Umur cache di CDN Edge Server adalah 86.400 detik (24 jam).
- `stale-while-revalidate=60`: Jika cache expired, CDN boleh menyajikan data basi (*stale data*) seketika ke pengguna, sambil secara asinkron mengambil data baru di background dari origin.

---

## 7. Analogy: Gudang Distribusi E-Commerce
- **Origin Server:** Pabrik pusat manufaktur sepatu di Surabaya.
- **Pengguna:** Pembeli sepatu di Medan.
- **Tanpa CDN:** Setiap ada pesanan dari Medan, pabrik Surabaya harus membungkus barang dan mengirimkannya menggunakan kapal laut (butuh 5 hari pengiriman).
- **Dengan CDN (Pull Model):** E-commerce menyewa gudang fulfillment mini di Medan. Pesanan pertama membutuhkan waktu karena gudang Medan harus mengambil stok dari Surabaya. Namun untuk 1.000 pembeli berikutnya di Medan, sepatu langsung dikirim dari gudang Medan hari itu juga dalam 1 jam!

---

## 8. Diagram: Cache Invalidation & Pola Cache Busting

Salah satu pepatah paling terkenal dalam ilmu komputer:
> *"There are only two hard things in Computer Science: cache invalidation and naming things."* — Phil Karlton

Jika Anda mengganti file CSS di server, bagaimana memastikan seluruh pengguna di dunia langsung mendapatkan tampilan baru tanpa menunggu TTL 1 tahun habis?

### Strategi 1: Cache Busting / Content Hashing (Rekomendasi Utama)
Ubah nama file berdasarkan hash isi konten file tersebut saat proses build (Webpack/Vite):
```text
Versi Lama : /assets/main.4a8b1c.css  (Cache-Control: max-age=31536000, immutable)
Versi Baru : /assets/main.9f2e7d.css  (URL baru! CDN otomatis memperlakukan sebagai aset baru)
```
Karena URL-nya berbeda, Anda tidak perlu repot melakukan purge manual pada CDN!

### Strategi 2: Surrogate-Keys / Cache-Tags (Untuk Halaman Dinamis)
Origin mengirimkan header penanda tag pada setiap respon:
```http
Surrogate-Key: product-1234 category-electronics
```
Ketika admin mengupdate harga produk #1234 di database, backend cukup mengirimkan instruksi API ke CDN: `PURGE TAG product-1234`. Seluruh edge server di dunia akan menghapus cache produk tersebut dalam < 150 ms!

---

## 9. Simple Example: Validasi ETag (Conditional Request)
Jika file tidak diberi content-hash, browser dapat melakukan validasi apakah file telah berubah:
1. Request pertama: Server mengembalikan file dengan header `ETag: "v1-hash-abc"`.
2. Request kedua: Browser mengirim `If-None-Match: "v1-hash-abc"`.
3. Jika file di server belum berubah, server cukup merespon dengan **HTTP 304 Not Modified** tanpa mengirimkan body file (menghemat 99% bandwidth!).

---

## 10. Practical Code Example
Lihat simulasi siklus lengkap CDN: Cache Miss -> Cache Hit -> Purge Invalidation -> Re-fetch pada:
`System-Design/BAB-02-Edge-DNS-CDN/hands-on/m02/cdn_simulator.js`

---

## 11. Real World Example: Netflix Open Connect & Streaming Piala Dunia
- **Netflix Open Connect Appliance (OCA):** Alih-alih menyewa CDN publik pihak ketiga, Netflix membuat hardware server CDN khusus (OCA) berkapasitas ratusan Terabyte SSD dan menaruhnya langsung di dalam ruang data center ISP lokal (Telkomsel, Indosat, Comcast). Saat Anda memutar film Stranger Things, video streaming tersebut tidak keluar ke jaringan internet internasional, melainkan langsung ditarik dari rak server di ISP Anda sendiri!
- **Fastly & The Super Bowl:** Layanan streaming olahraga menyajikan jutaan penonton bersamaan. Dengan memanfaatkan *Origin Shield*, jutaan request streaming live video diserap oleh edge server Fastly dengan rasio *Cache Hit Ratio* mencapai **99.2%**. Server origin backend video hanya menerima 0.8% request!

---

## 12. Trade-offs (Pull CDN vs Push CDN)

| Aspek | Pull CDN | Push CDN |
|---|---|---|
| **Otomasi Pembaruan** | Otomatis (on-demand saat diakses) | Manual/Scripted (harus dipicu pipeline CI/CD) |
| **Cold Start Latency** | Pengguna pertama mengalami latensi origin | Pengguna pertama langsung merasakan kecepatan edge |
| **Penyimpanan Storage** | Efisien (data yang jarang diakses terhapus otomatis) | Boros (seluruh file tersimpan permanen di cloud storage) |
| **Kesesuaian Konten Dinamis** | Sangat baik dengan micro-caching | Tidak cocok sama sekali |

---

## 13. When To Use What
- **Gunakan Pull CDN:** Untuk 95% arsitektur web modern (frontend React/Vue/Next.js assets, gambar e-commerce, file audio, REST API read-heavy).
- **Gunakan Push CDN:** Untuk file software installer raksasa (.exe, .dmg, .iso 2GB+) atau patch game update di mana origin server tidak sanggup melayani lonjakan download massal saat hari pertama rilis.

---

## 14. When NOT To Use CDN
- **Dilarang keras meletakkan CDN caching pada endpoint yang menghasilkan data personal user:**
  - `/api/user/me`
  - `/api/cart/checkout`
  - `/api/account/balance`
  Jika Anda salah menyetel `Cache-Control: public` pada endpoint ini, Pengguna B yang login bisa melihat saldo dan nama akun milik Pengguna A!

---

## 15. Common Mistakes
1. **Caching Respon Error (HTTP 500 / 502):** Backend server Anda sempat down selama 5 detik dan merespon 500. Jika CDN meng-cache respon 500 tersebut selama 1 jam, maka pengguna akan melihat website error selama 1 jam ke depan meskipun server backend Anda sudah sembuh 5 detik kemudian!
2. **Tidak Memasang Origin Shield:** Menggunakan 200 PoP Edge. Saat ada event promosi dan cache expired serentak, 200 PoP tersebut secara bersamaan menembak Origin Server, menyebabkan origin server mati mendadak (*Thundering Herd Problem*).
3. **Mengabaikan Header CORS pada Font / Assets:** File web font (`.woff2`) di-cache di CDN tanpa header `Access-Control-Allow-Origin: *`, menyebabkan browser memblokir font karena kebijakan CORS.

---

## 16. Best Practices

- **Must Have:**
  - Terapkan **Cache-Control: no-store, private** pada seluruh API response yang memuat otentikasi / session cookies.
  - Terapkan **Content-Hashing** (`style.[hash].css`) untuk aset statis frontend dengan `max-age=31536000, immutable`.
- **Recommended:**
  - Aktifkan fitur kompresi modern di CDN: **Brotli (`br`)** yang lebih hemat 20% bandwidth dibandingkan Gzip standar.
  - Pasang **Origin Shield** di depan origin server Anda.
- **Advanced:**
  - Terapkan pola **Stale-While-Revalidate** untuk konten katalog yang toleran terhadap data berusia beberapa detik demi menjamin p99 latensi tetap < 20 ms.
- **Avoid / Overengineering:**
  - Melakukan purge global seluruh zona (`Purge Everything`) di jam sibuk produksi. Ini akan melumpuhkan origin server Anda dalam sekejap!

---

## 17. Troubleshooting Guide
```text
Gejala: Pengguna mengeluh tampilan web berantakan (CSS lama bercampur HTML baru).
---------------------------------------------------------------------------------
Kemungkinan Akar Masalah:
1. File index.html di-cache terlalu lama di CDN (sehingga browser merujuk ke hash file CSS lama yang sudah dihapus di origin).

Solusi Arsitektur:
- Konfigurasi aturan cache ketat:
  - File HTML (index.html): Cache-Control: no-cache, no-store, must-revalidate (Selalu cek ke origin).
  - File Bundle JS/CSS (bertanda hash): Cache-Control: public, max-age=31536000, immutable (Aman di-cache selamanya!).
```

---

## 18. Hands-on Lab: Simulator CDN Cache Hit/Miss & Surrogate-Key Invalidation

File lab sudah disiapkan di:
`System-Design/BAB-02-Edge-DNS-CDN/hands-on/m02/cdn_simulator.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-02-Edge-DNS-CDN/hands-on/m02/cdn_simulator.js
```

### Yang Ditampilkan Script Ini:
1. Simulasi request pertama ke file gambar produk: **Cold Cache Miss** (menarik dari origin, latensi ~150 ms).
2. Simulasi 5 request berikutnya dari pengguna lain di kota yang sama: **Hot Cache Hit** (latensi ~4 ms).
3. Melakukan eksekusi **Purge Invalidation by Cache-Tag**, lalu mengamati bagaimana CDN menarik kembali data terbaru dari origin secara mulus.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan perbedaan mendasar antara direktif `Cache-Control: no-cache` dan `Cache-Control: no-store`!

### Level 2 (Medium):
Sebuah file JavaScript berukuran 2 MB (`bundle.js`) disimpan di origin server di Singapura. Pengguna di London mengunduh file tersebut.
1. Jika tanpa CDN, perkiraan waktu download = 1.200 ms.
2. Jika menggunakan CDN dengan Cache Hit di Edge London, waktu download = 60 ms.
Hitung persentase reduksi latensi dan jelaskan mengapa teknik *Content Hashing* wajib diterapkan untuk file ini!

### Level 3 (Hard):
Jelaskan fenomena **Thundering Herd Problem (Cache Stampede)** pada CDN yang memiliki 300 Edge PoP di seluruh dunia ketika cache sebuah artikel berita viral kadaluwarsa pada detik yang sama! Bagaimana peran **Origin Shield** dan teknik **Request Collapsing** dalam menyelamatkan origin server dari kehancuran?

---

## 20. Summary & Knowledge Check
- [ ] Memahami topologi arsitektur CDN (Edge Server, PoP, Origin Server, Origin Shield).
- [ ] Memahami perbedaan strategi **Push CDN** vs **Pull CDN**.
- [ ] Menguasai konfigurasi header `Cache-Control` (`public`, `private`, `max-age`, `s-maxage`, `stale-while-revalidate`).
- [ ] Menguasai strategi invalidasi: *Cache Busting via Content Hash* vs *Purge by Surrogate-Key*.
- [ ] Mampu mendiagnosa masalah kebocoran data pribadi akibat kesalahan caching CDN.
