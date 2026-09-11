# Module 02: Desain Arsitektur — URL Shortener Skala Global (TinyURL / Bitly)

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Merancang arsitektur end-to-end untuk layanan pemendek tautan berskala global (**URL Shortener**) seperti TinyURL atau Bitly.
- Melakukan estimasi kapasitas sistem *Read-Heavy* (rasio 100:1).
- Memilih algoritma encoding yang tepat: **Base62 Encoding** vs **Hashing (MD5/SHA-256)**.
- Menyelesaikan masalah *ID Collision* menggunakan arsitektur **Key Generation Service (KGS)**.
- Menganalisis trade-off pemilihan status HTTP: **301 Moved Permanently** vs **302 Found**.

## 2. Prerequisite
- Memahami konsep Back-of-the-Envelope Estimation dari BAB 09.
- Memahami Caching Layer (Cache-Aside) dari BAB 04 dan Relational/NoSQL Database Sharding dari BAB 05.

## 3. Concept
Layanan URL Shortener bertugas menerima URL panjang (misal: `https://www.example.com/products/electronics/phones/galaxy-s24?ref=newsletter_september_promo_2026`) dan menghasilkan URL pendek ringkas (misal: `https://tiny.url/aB7xK9`). Ketika pengguna mengeklik URL pendek tersebut, sistem mengarahkan (*redirect*) browser pengguna kembali ke URL asli secepat kilat (< 10ms).

Karakteristik fundamental sistem ini:
- **Ekstrem Read-Heavy**: Satu tautan dibuat satu kali, tetapi dapat diklik ratusan ribu kali di media sosial.
- **High Availability & Low Latency**: Jika layanan shortener lambat atau down, seluruh link di Twitter, WhatsApp, dan email promosi di seluruh dunia akan rusak.

## 4. Why?
- Menghemat batasan karakter teks pada SMS dan postingan media sosial.
- Pelacakan analitik pemasaran (*marketing click tracking*): dari negara mana pengguna berasal, perangkat apa yang digunakan, jam berapa diklik.
- Menyamarkan link afiliasi yang panjang dan rumit.

## 5. What?
### 1. Estimasi Kapasitas Matematis:
- **Asumsi Beban**:
  - Penulisan link baru (Write): **100 Juta URL baru per bulan**.
  - Rasio Read terhadap Write: **100 : 1** (10 Miliar redirect per bulan).
- **Throughput QPS**:
  - Write QPS: $\frac{100.000.000}{30 \times 86.400} \approx 40 \text{ URLs/detik}$.
  - Read QPS: $40 \times 100 = 4.000 \text{ Redirects/detik}$ (Peak Read QPS: $\approx 10.000 \text{ QPS}$).
- **Storage 5 Tahun**:
  - 1 URL Record: `short_key` (7 byte) + `long_url` (500 byte) + `created_at` (8 byte) + `user_id` (8 byte) $\approx 550 \text{ bytes}$.
  - Total 5 Tahun: $100.000.000 \times 12 \times 5 \times 550 \text{ bytes} \approx 3.3 \text{ Terabyte}$ (Sangat manageable!).
- **Cache Memory (Prinsip Pareto 80/20)**:
  - Total Read harian: $\frac{10 \text{ Miliar}}{30} \approx 330 \text{ Juta redirects/hari}$.
  - Ukuran cache 20% data harian:
    $$0.2 \times (330.000.000 \times 550 \text{ bytes}) \approx 36 \text{ GB RAM}$$ (Muat dalam 1 server Redis 64 GB!).

### 2. Matematika Base62 Encoding:
Karakter yang diizinkan untuk short URL:
- Angka `0-9` (10 karakter)
- Huruf kecil `a-z` (26 karakter)
- Huruf besar `A-Z` (26 karakter)
- Total variasi: $10 + 26 + 26 = 62$ karakter (**Base62**).

Berapa panjang karakter short key yang ideal?
- $62^6 \approx 56.8 \text{ Miliar kombinasi}$ (Mungkin habis dalam 30 tahun).
- $62^7 \approx 3.52 \text{ Triliun kombinasi}$!
**Keputusan Arsitektur**: Gunakan string **7 Karakter** (`62^7`) — cukup untuk ribuan tahun pemakaian global.

## 6. How?
### Mengapa Pendekatan Hash (MD5/SHA256) Bermasalah?
Jika kita me-hash URL asli: `MD5(long_url)` $\rightarrow$ menghasilkan 128-bit hash (32 hex characters). Jika kita memotong 7 karakter pertama, kemungkinan terjadinya tabrakan hash (**collision**) sangat tinggi! Jika terjadi collision, kita harus me-looping menambahkan salt: `MD5(long_url + salt)`, yang memboroskan query database (*expensive collision resolution*).

### Solusi Terbaik: Key Generation Service (KGS)
KGS adalah microservice mandiri yang bertugas **menghasilkan short key 7-karakter unik di awal (pre-generated)** dan menyimpannya di antrian memori:
1. KGS menghasilkan jutaan key Base62 acak terlebih dahulu dan menyimpannya di tabel database: `keys (key_str, is_used)`.
2. KGS memuat sejumlah key (misal 50.000 key) ke RAM lokalnya.
3. Saat Web Server membutuhkan key baru untuk user, Web Server cukup mengambil 1 key dari RAM KGS dalam **0.01 milidetik**!
4. **Nol Collision, Nol Hashing, Zero Latency**!

### Perdebatan Status Code: 301 vs 302
- **HTTP 301 Moved Permanently**:
  - Browser menyimpan (*cache*) URL tujuan akhir secara permanen di browser lokal pengguna.
  - Klik berikutnya langsung membuka URL tujuan tanpa pernah menghubungi server shortener lagi.
  - *Trade-off*: Menghemat beban server backend secara drastis, TETAPI Anda **kehilangan kemampuan melacak analitik klik pengguna**!
- **HTTP 302 Found (Temporary Redirect)**:
  - Browser **wajib selalu menghubungi server shortener** setiap kali tautan diklik.
  - *Trade-off*: Beban server lebih tinggi, TETAPI Anda dapat **mencatat 100% analitik pengguna** (referrer, device, IP, lokasi, timestamp) secara akurat.
  - **Rekomendasi Industri**: Gunakan **HTTP 302** (atau 307) jika analitik klik adalah model bisnis utama produk Anda.

## 7. Analogy
- **URL Shortener = Nomor Antrian di Restoran**: Pelayan tidak mencatat: *"Bapak Budi berbaju merah dengan sepatu kulit cokelat yang memesan nasi goreng pedas tanpa acar..."* di papan panggil. Pelayan cukup memberikan nomor token mini: `B-42`. Saat nomor `B-42` dipanggil di kasir, kasir langsung mencocokkan ke struk pesanan lengkap di komputernya.

## 8. Diagram

```text
================ ALUR KERJA SISTEM TINYURL LENGKAP ================

1. ALUR PEMBUATAN (WRITE PATH):
[User / Creator] ──> POST /api/shorten { url: "https://..." }
                           │
                           ▼
                    [API Gateway]
                           │
                           ▼
                 [Shortener Web Service]
                           │
                           ├── 1. Ambil 1 Key Unik dari [Key Generation Service (KGS)]
                           │      (Pre-allocated dari RAM KGS: "x7Kb9Q")
                           │
                           ├── 2. Simpan Pemetaan ke Database:
                           │      INSERT INTO urls (short_key, long_url, created_at)
                           │
                           └── 3. Kembalikan ke Client: "https://tiny.url/x7Kb9Q"


2. ALUR PENGALIHAN (READ PATH - 4000+ QPS):
[User / Visitor] ──> GET /x7Kb9Q
                           │
                           ▼
                    [API Gateway]
                           │
                           ▼
                 [Shortener Web Service]
                           │
                           ├── 1. Cek [Redis Cache Cluster] (Hit Ratio ~80-90%)
                           │      ├── HIT  ──> Ambil Long URL dari RAM
                           │      └── MISS ──> Query Database -> Simpan ke Redis Cache
                           │
                           ├── 2. Asynchronously Kirim Event Klik ke Kafka (Analitik)
                           │      Topic: 'link_clicks' ──> [Analytics Pipeline]
                           │
                           └── 3. Kembalikan HTTP 302 Redirect (Header: Location: https://...)
```

## 9. Simple Example: Konversi Angka Auto-Increment ke Base62
```javascript
const BASE62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

function idToBase62(num) {
  let str = "";
  while (num > 0) {
    str = BASE62_CHARS[num % 62] + str;
    num = Math.floor(num / 62);
  }
  return str.padStart(7, "0");
}

console.log(idToBase62(1000000000)); // Menghasilkan "0015FTG" (7 Karakter Unik)
```

## 10. Practical Example: Skema Database (NoSQL vs Relational)
Tabel URL Shortener memiliki struktur data yang sangat sederhana dan tidak memiliki relasi kompleks:
```sql
CREATE TABLE urls (
    short_key VARCHAR(7) PRIMARY KEY,
    long_url VARCHAR(2048) NOT NULL,
    user_id BIGINT,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP
);
CREATE INDEX idx_user_id ON urls(user_id);
```
Karena pola aksesnya murni *Key-Value lookup* (`SELECT long_url FROM urls WHERE short_key = ?`), database NoSQL Key-Value / Wide-Column seperti **Amazon DynamoDB** atau **Apache Cassandra** sangat ideal untuk melakukan sharding otomatis berdasarkan partisi hash dari `short_key`.

## 11. Real World Example
- **Bitly**: Memproses lebih dari 6 Miliar klik tautan setiap bulan. Menggunakan Redis cache di layer depan untuk menyerap 90% read traffic, dan DynamoDB sebagai persistent datastore dengan replikasi multi-region global.

## 12. Trade-offs

| Aspek | Key Generation Service (KGS) | Hashing + Collision Loop | Auto-Increment + Base62 |
|---|---|---|---|
| **Collision Risk** | **Nol (0% Collision)** | Tinggi pada dataset besar | Nol |
| **Latensi Write** | Sub-milidetik (Ambil dari pool) | Lambat jika terjadi collision | Cepat (Tergantung DB sequence) |
| **Keamanan Key** | Kunci acak (Sulit ditebak bot) | Acak | **Bisa ditebak / Scrapeable!** (ID 1, 2, 3...) |
| **Kompleksitas** | Butuh microservice KGS terpisah | Rendah | Rendah |

## 13. When To Use
- Layanan pemendek URL, pembuatan voucher/kupon diskon unik, pelacakan barcode logistik, deep linking mobile apps.

## 14. When NOT To Use
- Sistem yang URL-nya bersifat rahasia dan sensitif (Token reset password sebaiknya menggunakan token kriptografis 256-bit acak, bukan short URL 7-karakter yang bisa di-brute force).

## 15. Common Mistakes
1. **Menggunakan Auto-Increment ID Mentah untuk URL Publik**: Jika link Anda adalah `tiny.url/000001`, `tiny.url/000002`, bot pesaing dapat dengan mudah men-scrape seluruh database link Anda secara berurutan. KGS harus mengacak (*shuffle*) urutan ID sebelum di-encode!
2. **Lupa Memberikan TTL / Expiration**: Database akan membengkak dengan tautan usang yang tidak pernah diklik lagi selama 5 tahun. Tetapkan expiration date default (misal 2 tahun) dan jalankan batch cleanup worker.

## 16. Best Practices
- **Sharding Berdasarkan Hash dari Short Key**: Gunakan consistent hashing pada partisi database agar tidak terjadi *hot shard*.
- **Cache Pre-Warming**: Segera setelah short URL berhasil dibuat di Write Path, langsung masukkan ke Redis cache karena URL yang baru dibuat di media sosial biasanya langsung diklik dalam hitungan menit pertama.

## 17. Troubleshooting
- **Masalah: KGS mengalami crash, dan semua server web gagal membuat link baru**.
  - *Sebab*: KGS adalah Single Point of Failure (SPOF) jika hanya berjalan 1 instance.
  - *Solusi*: Jalankan KGS dengan arsitektur Active-Standby atau alokasikan rentang key yang berbeda ke beberapa node KGS independen (Node 1 memegang range 1 - 100M, Node 2 memegang 100M - 200M).

## 18. Hands-on Practice
Mari kita buktikan implementasi nyata TinyURL Service lengkap dengan Base62 generator, KGS in-memory pre-allocation, Redis-style Cache-Aside layer, dan counter analitik di `hands-on/m02/tinyurl_service.js`.

## 19. Exercises & Challenge
- **Exercise**: Hitung berapa ukuran memori RAM yang dibutuhkan untuk menyimpan 10 juta key pre-generated di KGS jika 1 key berukuran 7 bytes string + 8 bytes pointer metadata. (Jawaban: $10.000.000 \times 15\text{ bytes} \approx 150\text{ MB RAM}$, sangat kecil!).
- **Challenge**: Rancang fitur *Custom Alias* (misal: pengguna ingin membuat URL khusus `tiny.url/diskon-ramadhan`). Bagaimana arsitektur menangani validasi ketersediaan alias dan benturan dengan key Base62 bawaan sistem?

## 20. Summary
URL Shortener adalah studi kasus klasik System Design yang mengajarkan seni menyeimbangkan throughput baca yang sangat masif (*Read-Heavy*). Melalui kombinasi **Base62 Encoding**, **Key Generation Service (KGS)** untuk mengeliminasi tabrakan ID, dan **Cache-Aside Layer (Redis)**, sistem mampu menyajikan pengalihan tautan global dalam waktu < 10 milidetik.
