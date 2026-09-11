# Module 01: Rate Limiting & Traffic Shaping

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Memahami fungsi protektif **Rate Limiter** dan **Traffic Shaper** dalam melindungi resource backend dari overload, DoS, brute-force, dan web scraping.
- Membedakan cara kerja 5 algoritma rate limiting utama: *Token Bucket*, *Leaky Bucket*, *Fixed Window Counter*, *Sliding Window Log*, dan *Sliding Window Counter*.
- Menganalisis trade-off performa, kompleksitas komputasi, dan overhead memori antar algoritma.
- Merancang distributed rate limiting menggunakan Redis atomic operations (INCR, EVAL script Lua).

## 2. Prerequisite
- Memahami konsep Reverse Proxy dan API Gateway dari BAB 03.
- Konsep dasar in-memory key-value stores (Redis) dari BAB 04.

## 3. Concept
Dalam dunia nyata, resource komputasi sistem (CPU, RAM, database connections, third-party API budget) bersifat terbatas. Jika seorang pengguna, web crawler nakal, atau attacker mengirim jutaan request per detik, seluruh sistem dapat lumpuh bagi pengguna lain yang sah (*Denial of Service*).

**Rate Limiting** adalah mekanisme pembatasan jumlah request yang diizinkan oleh sistem dalam jangka waktu tertentu (misal: "Maksimal 100 request per menit per User ID"). Jika batas terlampaui, request berlebih akan ditolak seketika dengan kode status HTTP `429 Too Many Requests` beserta header `Retry-After`.

## 4. Why?
- **Mencegah Resource Starvation (DDoS / Brute Force)**: Membatasi percobaan login untuk mencegah serangan password cracking.
- **Biaya & Kontrol Finansial**: Layanan LLM (OpenAI) atau SMS Gateway (Twilio) menagih per request. Rate limiting mencegah pembengkakan tagihan jutaan dolar akibat loop tak sengaja dari developer client.
- **Fair Use Policy**: Memastikan satu tenant dalam arsitektur multi-tenant tidak memonopoli seluruh kapasitas server (*noisy neighbor problem*).

## 5. What?
### 5 Algoritma Rate Limiting Utama:
1. **Token Bucket**:
   - Bucket memiliki kapasitas $C$ token.
   - Token diisi ulang (*refill*) dengan laju konstan $r$ token per detik.
   - Setiap request memakan 1 token. Jika bucket kosong, request di-drop (`429`).
   - **Kelebihan**: Mengizinkan lonjakan traffic sesaat (*traffic burst*) hingga batas kapasitas bucket. Sangat populer (digunakan oleh AWS, Stripe).
2. **Leaky Bucket (Traffic Shaping)**:
   - Request masuk ditampung dalam antrian FIFO dengan kapasitas tetap.
   - Request dikeluarkan dan diproses dengan **laju kecepatan konstan** (seperti tetesan air yang bocor perlahan dari dasar ember berlubang).
   - Jika antrian penuh, request baru tumpah (*dropped*).
   - **Kelebihan**: Menghasilkan aliran output yang sangat halus (*smooth constant rate*).
3. **Fixed Window Counter**:
   - Waktu dibagi menjadi jendela statis (misal 1 menit: 10:00 - 10:01).
   - Setiap request menaikkan counter. Jika counter > limit, tolak request.
   - **Kelemahan Fatal**: Kerentanan lonjakan di batas jendela (*boundary burst*). Pengguna bisa mengirim 100 request di detik 10:00:59 dan 100 request di detik 10:01:01, sehingga ada 200 request dalam interval 2 detik!
4. **Sliding Window Log**:
   - Menyimpan timestamp setiap request dalam Sorted Set (misal Redis ZSET).
   - Saat request baru masuk, hapus timestamp yang lebih lama dari $(t - \text{window})$.
   - Hitung sisa elemen. Jika sisa elemen < limit, simpan timestamp baru dan izinkan.
   - **Kelebihan**: Akurasi 100% sempurna.
   - **Kelemahan**: Menghabiskan banyak memori RAM untuk menyimpan jutaan timestamp.
5. **Sliding Window Counter (Approximation)**:
   - Menggabungkan kesederhanaan Fixed Window dengan akurasi Sliding Window menggunakan rumus aproksimasi berbobot:
     $$\text{Current Requests} = \text{Requests in Current Window} + (\text{Requests in Previous Window} \times (1 - \text{Overlap %}))$$
   - Menawarkan akurasi ~99% dengan konsumsi memori yang sangat hemat (hanya menyimpan 2 angka counter).

## 6. How?
### Implementasi Header Standar HTTP Rate Limiting (IETF RFC 6585):
Ketika server merespons request, server menyertakan header proteksi:
- `X-RateLimit-Limit`: Jumlah maksimum request yang diizinkan (misal: `100`).
- `X-RateLimit-Remaining`: Sisa kuota request yang tersisa di jendela saat ini (misal: `24`).
- `X-RateLimit-Reset`: Waktu Unix Epoch kapan kuota akan terisi penuh kembali (misal: `1789098900`).
- Jika limit habis, server mengirimkan HTTP `429 Too Many Requests` dengan header:
  `Retry-After: 30` (tunggu 30 detik sebelum mencoba lagi).

## 7. Analogy
- **Token Bucket = Arcade Game Pass**: Anda memiliki dompet koin game. Setiap menit pengelola menambahkan 5 koin gratis (refill). Anda bisa langsung menghabiskan 10 koin sekaligus dalam 5 detik jika dompet Anda penuh, tetapi jika dompet kosong Anda harus menunggu pengelola memberikan koin baru.
- **Leaky Bucket = Corong Pompa Minyak**: Tidak peduli seberapa cepat Anda menuangkan minyak ke corong atas, minyak hanya keluar dari ujung bawah dengan debit konstan satu tetes demi satu tetes.
- **Fixed Window = Kuota Kupon Bioskop Per Jam**: Jam 09:00 - 10:00 ada 50 tiket. Jika ada 50 orang beli di 09:59 dan 50 orang lagi beli di 10:01, dalam 2 menit ada 100 orang berjejalan di pintu masuk.

## 8. Diagram

```text
================ TOKEN BUCKET ALGORITHM ================
        Refill Rate: r tokens / sec
                   │
                   ▼
         ┌───────────────────┐
         │  o   o   o   o    │  Bucket Capacity: C tokens
         │    o   o   o      │
         └─────────┬─────────┘
                   │
Request Masuk ─────┼─── Ada token? ──>[ Ya: Ambil 1 token -> Izinkan Request ]
                   │
                   └─── Bucket Kosong? ──>[ Tidak: Tolak Request (HTTP 429) ]

================ BOUNDARY BURST ISSUE PADA FIXED WINDOW ================
Window 1 (12:00 - 12:01)      Window 2 (12:01 - 12:02)
Limit: 100 req/min            Limit: 100 req/min
             100 req                       100 req
           [12:00:59]                    [12:01:01]
               │                              │
               └──────────────┬───────────────┘
                     Rentang 2 Detik = 200 Requests! (2x Limit!)
```

## 9. Simple Example
Implementasi Token Bucket Sederhana (Lazy Refill Formula):
Alih-alih menjalankan timer background `setInterval` yang boros resource untuk mengisi token setiap detik, kita menghitung penambahan token secara dinamis saat request datang (*lazy calculation*):
$$\Delta \text{Tokens} = (\text{Current Time} - \text{Last Request Time}) \times \text{Refill Rate}$$
$$\text{New Tokens} = \min(\text{Capacity}, \text{Current Tokens} + \Delta \text{Tokens})$$

## 10. Practical Example: Distributed Rate Limiter dengan Redis Lua Script
Dalam sistem multi-server (10 instance API Gateway), menyimpan state counter di memory lokal NodeJS akan membuat limit bocor 10 kali lipat.
Kita menggunakan script Redis Lua untuk menjamin eksekusi atomik tanpa race condition:
```lua
-- Lua script di Redis (Atomic Execution)
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local current = tonumber(redis.call('get', key) or "0")

if current + 1 > limit then
    return 0 -- Ditolak
else
    redis.call("INCRBY", key, 1)
    if current == 0 then
        redis.call("EXPIRE", key, 60)
    end
    return 1 -- Diizinkan
end
```

## 11. Real World Example
- **GitHub API**: Memberikan limit 5.000 request per jam untuk authenticated user (berdasarkan Personal Access Token), dan 60 request per jam untuk unauthenticated IP address.
- **Stripe**: Menggunakan Token Bucket dengan Redis untuk membedakan kategori request: Read requests memiliki limit lebih tinggi daripada Write requests (POST charges).

## 12. Trade-offs

| Algoritma | Penggunaan Memori | Kompleksitas Komputasi | Mendukung Burst? | Akurasi |
|---|---|---|---|---|
| **Fixed Window** | O(1) - Sangat hemat (1 integer) | O(1) | Tidak (Double burst di batas) | Rendah |
| **Token Bucket** | O(1) - (Counter + Timestamp) | O(1) | **Ya (Sesuai kapasitas bucket)**| Tinggi |
| **Leaky Bucket** | O(N) - Buffer antrian | O(1) | Tidak (Laju konstan ketat) | Sangat Tinggi |
| **Sliding Window Log** | **O(N) - Tinggi (Simpan tiap TS)**| O(log N) - Prune timestamps | Ya | Sempurna (100%) |
| **Sliding Window Counter**| O(1) - (2 window counter) | O(1) | Ya | Sangat Tinggi (~99%) |

## 13. When To Use
- **Token Bucket**: Pilihan default terbaik untuk API Publik dan Microservices Gateway yang ingin memperbolehkan lonjakan sesaat pengguna tanpa membuat server crash.
- **Leaky Bucket**: Sangat cocok saat meneruskan tugas ke database atau payment processor downstream yang membutuhkan kestabilan laju eksekusi konstan (*traffic shaping*).
- **Sliding Window Counter**: Pilihan ideal untuk distributed rate limiting berkecepatan tinggi di Redis.

## 14. When NOT To Use
- Jangan memasang rate limiting di internal loop inter-service yang terisolasi dalam private VPC berkepercayaan penuh jika latensi mikrodetik adalah prioritas utama (gunakan Circuit Breaker sebagai gantinya).

## 15. Common Mistakes
1. **Rate Limiting Hanya Berdasarkan IP Address**: Ribuan pengguna kantor atau universitas seringkali berbagi satu Public NAT IP. Memblokir IP ini akan membuat seluruh kantor terkunci. Kombinasikan IP + User ID + Device ID!
2. **Race Condition di Distributed Cache (Check-Then-Set)**: Melakukan `GET key` lalu `SET key key+1` di Redis dari dua server bersamaan menghasilkan race condition. Wajib gunakan `INCR` atomik atau Redis Lua script!
3. **Tidak Mengembalikan Header Informasi**: Mengirim status 429 tanpa header `Retry-After` membuat aplikasi client bingung dan melakukan retry brutal (*aggressive polling*).

## 16. Best Practices
- **Graceful Rejection**: Kembalikan pesan JSON yang informatif saat limit habis, sertakan `Retry-After` dalam satuan detik.
- **Multi-Tier Rate Limiting**: Terapkan limit bertingkat:
  - Tier 1: Per detik (misal: 10 req/detik untuk mencegah burst tajam).
  - Tier 2: Per hari (misal: 50.000 req/hari untuk kontrol kuota bulanan).
- **Whitelist untuk Service Internal & Healthchecks**: Pastikan endpoint `/healthz` dari Kubernetes liveness probe dikecualikan dari rate limiting agar pod tidak di-restart sembarangan.

## 17. Troubleshooting
- **Masalah: User mengeluh tiba-tiba terkena blokir 429 padahal baru membuka website**.
  - *Sebab*: Single Page Application (SPA) memuat 40 file asset (CSS, JS, SVG, WebP) secara bersamaan ke domain API yang sama.
  - *Solusi*: Pisahkan domain static asset ke CDN pihak ketiga (misal: `cdn.example.com`), dan batasi rate limit hanya pada API endpoints dinamis (`api.example.com/v1/*`).

## 18. Hands-on Practice
Mari kita buktikan secara empiris perbedaan algoritma Token Bucket (mengizinkan burst terkontrol) vs Fixed Window (bocor pada window boundary) melalui simulasi interaktif di `hands-on/m01/rate_limiter_algorithms.js`.

## 19. Exercises & Challenge
- **Exercise**: Dengan formula Sliding Window Counter, jika Window sebelumnya (menit ke-1) memiliki 100 request, Window saat ini (menit ke-2) berjalan pada detik ke-15 (25% window), dan sudah ada 10 request baru. Berapa perkiraan request saat ini? Apakah lolos jika limit adalah 80 request/menit?
  *(Perhitungan: $10 + (100 \times 0.75) = 85$ request $\rightarrow$ Melebihi limit 80, request ditolak!)*
- **Challenge**: Rancang skema rate limiter adaptif (*Dynamic / Congestion-Based Rate Limiting*) yang otomatis menurunkan limit jika CPU server melebihi 85%.

## 20. Summary
Rate Limiting adalah dinding pertahanan pertama sistem terdistribusi. Memahami karakteristik Token Bucket vs Leaky Bucket vs Sliding Window memungkinkan arsitek sistem melindungi stabilitas infrastruktur dari serangan DoS maupun ketidaksengajaan bug client tanpa mengorbankan pengalaman pengguna yang sah.
