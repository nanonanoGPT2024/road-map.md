# Module 01: Desain Arsitektur — Distributed Rate Limiter

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Merancang arsitektur **Distributed Rate Limiter** berskala global yang melayani jutaan request per detik dengan latensi sub-milidetik.
- Menyelesaikan tantangan sinkronisasi state rate limit terdistribusi antar multi-datacenter/region.
- Mengatasi masalah konkurensi, race condition, dan latensi jaringan menggunakan Redis Cluster dengan atomic Lua scripts dan sliding window counter.
- Menentukan strategi fail-open vs fail-closed ketika kluster rate limiter mengalami gangguan.

## 2. Prerequisite
- Memahami konsep Rate Limiter (Token Bucket & Sliding Window) dari BAB 08 Module 01.
- Memahami Caching terdistribusi dan Redis dari BAB 04.

## 3. Concept
Mendesain rate limiter untuk satu server tunggal adalah masalah mudah: cukup simpan counter di memori lokal proses (`Map`). Namun, mendesain **Distributed Rate Limiter** yang melayani sistem raksasa dengan ratusan instance API Gateway di 5 benua menghadirkan tantangan terdistribusi yang berat:
1. **Consistency vs Latency**: Apakah setiap request harus melakukan round-trip jaringan ke Redis terpusat? Jika ya, latensi API akan melonjak 5-20ms.
2. **Race Condition**: Dua request dari user yang sama tiba di Gateway 1 dan Gateway 2 di milidetik yang sama. Keduanya membaca counter yang sama sebelum menaikkannya (*Check-Then-Set race condition*).
3. **Multi-Region Synchronization**: Bagaimana menyinkronkan kuota pengguna yang berpindah dari Region Asia ke Region Amerika?

## 4. Why?
Perusahaan seperti Cloudflare, Stripe, dan GitHub mengandalkan distributed rate limiter untuk:
- Melindungi jutaan backend server dari serangan DDoS volumetrik dan bot scraper.
- Memberlakukan kuota API berbayar (*Monetization & API Tiering*).
- Menjaga stabilitas ekosistem cloud publik multi-tenant dari *noisy neighbors*.

## 5. What?
### Komponen Arsitektur:
1. **Client / Edge Tier**: CDN / Reverse Proxy (Cloudflare / Envoy) yang melakukan filtering awal.
2. **API Gateway Nodes**: Server stateless yang mengeksekusi interceptor rate limit sebelum meneruskan request ke microservices.
3. **Local In-Memory Cache (L1)**: Menyimpan kuota sementara dengan batching lokal untuk menghemat round-trip.
4. **Distributed Cache Cluster (L2 - Redis Cluster)**: Penyimpanan state global yang menggunakan *Consistent Hashing* untuk mendistribusikan kunci pengguna secara merata.
5. **Rules Engine & Configuration Store**: Database relasional (PostgreSQL/etcd) untuk menyimpan aturan rate limit (misal: "VIP Tier = 5.000 req/menit"). Sinkronisasi aturan ke gateway via distributed pub/sub.

## 6. How?
### Alur Pemrosesan Request (End-to-End):
```text
[Client Request]
      │
      ▼
[API Gateway] ── 1. Ekstrak Identifier: UserID / API Key / IP
      │
      ├── 2. Ambil Aturan Rate Limit dari In-Memory Rules Cache (O(1))
      │
      ├── 3. Evaluasi Kuota via Redis Lua Script (Atomic Execution):
      │      - Key: "ratelimit:{user_id}:{window_timestamp}"
      │      - Cek batas & Increment secara atomik
      │
      ├── 4. Apakah Lolos?
             ├── TIDAK (Exceeded) ──> Kembalikan HTTP 429 + Retry-After (Stop!)
             │
             └── YA (Allowed) ─────> Teruskan Request ke Downstream Microservices
```

### Script Lua Redis (Atomic Sliding Window Counter):
```lua
-- KEYS[1]: User Rate Limit Key
-- ARGV[1]: Current Timestamp (ms)
-- ARGV[2]: Window Size (ms, misal 60000)
-- ARGV[3]: Max Limit (misal 100)

local current_time = tonumber(ARGV[1])
local window_size = tonumber(ARGV[2])
local max_limit = tonumber(ARGV[3])
local clear_before = current_time - window_size

-- 1. Hapus entri lama di luar jendela
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, clear_before)

-- 2. Hitung jumlah request di jendela aktif
local current_requests = redis.call('ZCARD', KEYS[1])

if current_requests < max_limit then
    -- 3. Izinkan: Tambahkan request baru dengan score timestamp
    redis.call('ZADD', KEYS[1], current_time, current_time)
    redis.call('EXPIRE', KEYS[1], math.ceil(window_size / 1000))
    return 1 -- Allowed
else
    return 0 -- Denied (429)
end
```

## 7. Analogy
- **Distributed Rate Limiter = Sistem Gerbang Tol Elektronik Otomatis (E-Toll)**: Ribuan mobil masuk di 50 gardu tol berbeda di seluruh provinsi secara simultan. Setiap gardu tol harus memastikan saldo kartu E-Toll Anda mencukupi secara instan tanpa mengizinkan Anda masuk di dua gardu tol berbeda sekaligus secara curang.

## 8. Diagram

```text
================ ARSITEKTUR DISTRIBUTED RATE LIMITER GLOBAL ================

[US Region Gateway] ──┐
[EU Region Gateway] ──┼──> [Distributed Redis Cluster (Consistent Hashing)]
[AP Region Gateway] ──┘                 │
                                        ├── Shard 1 (Users A - H)
                                        ├── Shard 2 (Users I - Q)
                                        └── Shard 3 (Users R - Z)
                                                ▲
                                                │ (Replikasi Asinkron)
                                        [Cross-Region Replica]
```

## 9. Simple Example: Batch Token Reservation (Optimasi Latensi)
Alih-alih menghubungi Redis setiap kali 1 request tiba (1.000 QPS = 1.000 round-trip ke Redis), API Gateway dapat meminjam token secara grosir (*Batch Reservation*):
- Gateway mengambil **50 token sekaligus** dari Redis untuk `User-123`.
- Gateway melayani 50 request berikutnya dari RAM lokalnya sendiri dalam 0.05ms!
- Setelah 50 token habis atau rentang waktu 2 detik berlalu, Gateway mengambil batch berikutnya.

## 10. Practical Example: Stripe Rate Limiting Engine
Stripe memproses miliaran dolar transaksi menggunakan arsitektur rate limiting 4 lapis:
1. **Request Rate Limiter**: Membatasi total request HTTP ke gateway (Token Bucket di Redis).
2. **Allocation Rate Limiter**: Membatasi transaksi dari merchant tertentu agar tidak memonopoli resource DB.
3. **Concurrent Request Limiter**: Membatasi jumlah koneksi aktif yang berjalan simultan (maksimal 100 concurrent requests).
4. **Fleet Usage Load Shedder**: Jika CPU backend mencapai 90%, gateway otomatis menolak request non-kritis (seperti search log) dan memprioritaskan request pembayaran baru (*critical payment path*).

## 11. Real World Example
- **Cloudflare**: Menjalankan distributed rate limiting di edge server di ratusan negara. Mereka menggunakan algoritma *Sliding Window Counter* yang disinkronkan secara agregat menggunakan protokol gossiping UDP multicast antar edge nodes terdekat untuk menghindari sentralisasi ke satu datacenter.

## 12. Trade-offs

| Pendekatan Desain | Latensi | Akurasi Kuota | Kompleksitas |
|---|---|---|---|
| **Centralized Redis Only** | Sedang (1-5ms network call) | 100% Sempurna (Atomic) | Rendah |
| **Local Memory + Async Sync**| Sangat Rendah (< 0.1ms) | Rendah (Bisa bocor saat traffic burst) | Sedang |
| **Batch Token Reservation**| **Rendah (< 0.5ms)** | **Tinggi (Toleransi deviasi kecil)** | Menengah |
| **Multi-Region Cross-Sync**| Bergantung jarak benua | Terkendala CAP Theorem (AP vs CP) | Sangat Tinggi |

## 13. When To Use
- API publik berskala besar dengan ratusan instance server.
- Platform SaaS multi-tenant dengan tier paket berlangganan.

## 14. When NOT To Use
- Aplikasi monolitik server tunggal (cukup gunakan memory lock lokal).

## 15. Common Mistakes
1. **Mengabaikan Kegagalan Kluster Redis (Fail-Closed Disaster)**: Jika Redis down dan rate limiter Anda memilih *Fail-Closed*, maka 100% traffic pengguna yang sah akan tertolak (`500/429`)! Dalam arsitektur enterprise, rate limiter wajib **Fail-Open** (izinkan traffic lewat jika sistem rate limiter error, sambil memicu alarm darurat ke engineer).
2. **Kunci Sharding Redis Terlalu Luas**: Menggunakan satu kunci global untuk satu IP address scraper yang menyerang jutaan endpoint berbeda dapat menciptakan *hotspot partition* di satu node Redis.

## 16. Best Practices
- **Fail-Open Strategy**: Lebih baik membiarkan sedikit traffic berlebih lolos selama 5 menit daripada mematikan seluruh bisnis aplikasi Anda karena Redis mengalami restart.
- **Standarisasi Response Header**: Selalu kirimkan header standar RFC: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, dan `X-RateLimit-Reset`.
- **Gunakan Consistent Hashing**: Pastikan penambahan node Redis baru tidak merusak pemetaan kunci pengguna yang sedang berjalan.

## 17. Troubleshooting
- **Masalah: CPU Redis melonjak hingga 100% saat terjadi Flash Sale**.
  - *Sebab*: Pemanggilan Lua script yang terlalu kompleks atau perintah `KEYS *` / scanning besar-besaran.
  - *Solusi*: Ganti struktur data Sorted Set (ZSET) dengan Sliding Window Counter berbasis 2 integer sederhana (Current Window + Previous Window).

## 18. Hands-on Practice
Mari kita buktikan implementasi nyata Distributed Rate Limiter service lengkap dengan atomisitas, batch reservation, dan fail-open fallback di `hands-on/m01/distributed_rate_limiter_service.js`.

## 19. Exercises & Challenge
- **Exercise**: Jika 10 instance API Gateway masing-masing meminjam batch 20 token untuk User A, berapa batas maksimum kelebihan kuota (*over-allocation*) yang mungkin terjadi jika kuota sebenarnya sudah habis? (Jawaban: $10 \times 20 = 200$ request berlebih sebelum sinkronisasi berikutnya).
- **Challenge**: Rancang skema rate limiter berbasis multi-region di mana kuota global 10.000 req/menit dibagi secara proporsional berdasarkan rasio traffic geografis pengguna (US 60%, EU 30%, AP 10%).

## 20. Summary
Mendesain Distributed Rate Limiter berskala global menuntut keseimbangan antara latensi ultra-cepat dan akurasi kuota terpusat. Melalui kombinasi **Redis Cluster Atomic Operations**, **Batch Token Reservation**, dan kebijakan **Fail-Open Resilience**, sistem dapat terlindungi dari beban berlebih tanpa memperlambat performa pengguna yang sah.
