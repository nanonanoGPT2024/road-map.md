---
[⬅️ Module 01: Pola Caching & Algoritma Eviksi](./Module-01-Pola-Caching-dan-Algoritma-Eviksi-LRU-LFU.md) | [📋 Silabus Induk](../README.md) | [BAB 06 Quiz & Challenge ➡️](./BAB-06-Quiz-dan-Challenge.md)
---

# Module 02: Redis Internals, Distributed Locks, & Mitigasi Bencana Cache

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Memahami arsitektur internal Redis: model eksekusi *Single-Threaded Event Loop* dengan *I/O Multiplexing* (`epoll`/`kqueue`) dan mengapa Redis mampu memproses 100.000+ request per detik per core.
- Menguasai pemilihan struktur data native Redis: **Strings**, **Hashes**, **Sets**, **Sorted Sets (ZSET)**, **HyperLogLog**, dan **Streams**.
- Mengimplementasikan **Distributed Lock** yang aman menggunakan atomic primitives `SET key token NX PX 30000` dan pelepasan kunci berbasis **Lua Script**.
- Menganalisis batasan dan algoritma **Redlock** pada cluster multi-master.
- Mengidentifikasi dan memitigasi 4 bencana mematikan pada sistem cache skala besar: **Cache Stampede (Thundering Herd)**, **Cache Penetration**, **Cache Breakdown**, dan **Cache Avalanche**.
- Menerapkan algoritma **Probabilistic Early Expiration (XFetch)** untuk memusnahkan cache stampede selamanya.

---

## 2. Prerequisite
- Memahami konsep Pola Caching (Cache-Aside) & Algoritma Eviksi (Modul 01).
- Pemahaman operasi concurrency, race conditions, dan mutual exclusion (Mutex).
- Dasar jaringan socket TCP non-blocking dan event loop.

---

## 3. Concept
Redis (*Remote Dictionary Server*) adalah in-memory data structure store open-source yang digunakan sebagai database, cache, message broker, dan streaming engine.

Meskipun dieksekusi secara in-memory, Redis bukanlah sekadar key-value store biasa (seperti Memcached). Redis mendukung struktur data kaya yang dimanipulasi melalui operasi atomik di level server tanpa perlu *read-modify-write cycle* yang memicu race condition.

Mengapa Redis begitu cepat (~0.1 - 0.5 milidetik latensi)?
1. **In-Memory Storage:** Seluruh dataset berada di RAM fisik utama. Tidak ada overhead translasi struktur data ke format blok disk sekuensial.
2. **Non-Blocking I/O Multiplexing:** Menggunakan mekanisme kernel OS (`epoll` di Linux, `kqueue` di BSD/macOS) untuk mendengarkan puluhan ribu koneksi TCP secara simultan dalam satu thread tunggal tanpa overhead *thread context switching*.
3. **Single-Threaded Core Command Execution:** Setiap perintah yang dieksekusi dijamin atomik dan bebas dari *deadlock* atau persaingan *locking thread*.

---

## 4. Why?
Tanpa pemahaman mendalam tentang Redis internals dan pola mitigasi cache:
- **Locking Fatal / Deadlock:** Developer membuat distributed lock amatir menggunakan `GET` dan `SET` terpisah yang berujung pada hilangnya eksklusivitas data dan saldo keuangan ganda.
- **Cache Stampede:** Kunci data viral kedaluwarsa, memicu 50.000 thread backend menyerang database SQL dalam milidetik yang sama hingga database tumbang.
- **Cache Penetration:** Serangan hacker mengirim jutaan request untuk ID yang tidak pernah ada (`id: -99999`), membuat cache selalu miss dan seluruh beban menghantam database.
- **Salah Memilih Tipe Data:** Menggunakan JSON string raksasa di dalam String key untuk array yang diupdate sebagian, memboroskan bandwidth jaringan dan alokasi memori puluhan kali lipat.

---

## 5. What? (Katalog Struktur Data Redis & Use Cases)

| Struktur Data | Deskripsi Teknis | Kompleksitas Waktu | Skenario Penggunaan Utama |
|---|---|---|---|
| **String** | Teks biner-aman (JSON, integer, bitmap) hingga 512 MB | $O(1)$ untuk GET/SET/INCR | Caching objek sederhana, counter atomik (`INCR`), Distributed Mutex |
| **Hash** | Field-value pairs mirip objek JSON / Dictionary | $O(1)$ untuk HGET/HSET | Profil pengguna (`user:101 -> name, email, tier`), parsial update |
| **List** | Linked List elemen string berurut | $O(1)$ untuk LPUSH/RPOP | Antrean pesan (*Task Queue* sederhana), log aktivitas terbaru |
| **Set** | Koleksi string unik tak berurut | $O(1)$ untuk SADD/SISMEMBER | Tagging sistem, daftar user online, operasi irisan (`SINTER`) |
| **Sorted Set (ZSET)**| Set unik di mana tiap elemen memiliki bobot numerik (*Score*)| $O(\log N)$ (Skip List) | Leaderboard game, Sliding Window Rate Limiter, Priority Queue |
| **HyperLogLog**| Struktur probabilistik untuk estimasi kardinalitas data masif | $O(1)$ memori konstan (12 KB)| Menghitung *Unique Daily Active Users* (DAU) dengan akurasi 99.19% |
| **Stream**| Append-only log mirip Apache Kafka dengan consumer groups | $O(1)$ tambah, $O(\log N)$ baca| Event streaming, audit trail transaksi, CDC processing |

---

## 6. How? (Distributed Lock Pattern)

### Mengapa Distributed Lock Diperlukan?
Ketika aplikasi Anda di-deploy menjadi 20 instance pod Kubernetes di balik Load Balancer, mutex lokal di memori aplikasi (`sync.Mutex` di Go atau semaphore di Java) hanya melindungi thread di dalam pod yang sama. Untuk melindungi resource bersama (misal: proses debit saldo user atau reservasi kursi konser), kita membutuhkan **Distributed Lock** eksternal yang diakui oleh seluruh pod.

### Pola Distributed Lock yang Benar (Single Redis Instance)

#### 1. Mengakuisisi Kunci (Acquire Lock)
```bash
SET lock:order:101 "uuid-random-worker-A" NX PX 30000
```
- `NX`: *Not eXists* — Hanya berhasil jika kunci belum ada. Jika kunci sudah dipegang pod lain, perintah gagal ($O(1)$).
- `PX 30000`: Set TTL kedaluwarsa otomatis 30.000 ms (30 detik). Kunci akan rilis otomatis jika pod pembeli mengalami crash/mati mendadak (*Failsafe deadman switch*).
- `uuid-random-worker-A`: Identitas rahasia pemilik lock agar tidak ada worker lain yang sembarangan menghapus kunci milik orang lain.

#### 2. Melepaskan Kunci secara Atomik (Release Lock via Lua Script)
Jangan gunakan perintah `DEL lock:order:101` biasa! Jika durasi kerja melebihi TTL dan lock terlanjur diambil oleh Worker B, pemanggilan `DEL` oleh Worker A akan secara tidak sengaja menghapus lock milik Worker B!

Pelepasan wajib menggunakan **Lua Script** yang dieksekusi secara atomik oleh Redis:
```lua
-- KEYS[1]: Nama kunci lock (contoh: lock:order:101)
-- ARGV[1]: UUID unik pemilik lock (contoh: uuid-random-worker-A)
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
```

---

## 7. Analogy
Bayangkan sebuah bilik telepon umum di pusat kota:
- **Distributed Lock:** Bilik tersebut memiliki slot koin. Orang yang memasukkan koin unik berhak mengunci pintu dari dalam (**NX**).
- **TTL (Lease Expiration):** Di dalam bilik terdapat timer 5 menit. Jika orang di dalam pingsan (aplikasi crash), pintu otomatis terbuka sendiri agar orang lain tidak tertahan selamanya.
- **Release Lock via UUID:** Saat Anda keluar, Anda harus mencocokkan sidik jari Anda dengan sensor pintu. Ini mencegah orang yang baru lewat di luar pintu merebut atau mematikan timer orang lain.

---

## 8. Diagram: 4 Bencana Cache & Mitigasi Arsitektural

```
1. CACHE PENETRATION (Request data yang TIDAK PERNAH ADA di DB)
   [ Client ] ──Query ID -9999──▶ [ Cache (MISS) ] ──▶ [ Database (NOT FOUND) ]
   Mitigasi: Pasang Bloom Filter di depan Cache atau Cache nilai null dengan TTL singkat (60s).

2. CACHE BREAKDOWN (Satu Kunci HOT kedaluwarsa saat trafik tinggi)
   [ 10.000 Requests ] ──▶ [ Cache (EXPIRED!) ] ──Banjir Serentak──▶ [ Database COLLAPSE! ]
   Mitigasi: Distributed Mutex Locking atau Algoritma XFetch (Probabilistic Early Refresh).

3. CACHE AVALANCHE (Ratusan ribu kunci kedaluwarsa BERSAMAAN)
   [ Cache Ring ] ──Semua kunci diset TTL 1 Jam──▶ [ 13:00:00: KUNCI EXPIRED MASSAL ] ──▶ [ DB DOWN ]
   Mitigasi: Tambahkan Random Jitter pada TTL: TTL = Base_TTL + Random(1..300s).

4. CACHE STAMPEDE / THUNDERING HERD
   Beban komputasi kalkulasi data ulang yang sangat mahal dieksekusi serentak oleh puluhan worker.
```

---

## 9. Simple Example: Sliding Window Rate Limiter dengan Redis ZSET

```javascript
/**
 * Membatasi maksimal 10 request per 60 detik per IP user
 */
async function isRateLimited(redis, userIp) {
  const key = `ratelimit:${userIp}`;
  const now = Date.now();
  const windowSizeMs = 60 * 1000;
  const limit = 10;

  // Multi-Exec Pipeline untuk eksekusi atomik
  const pipeline = redis.multi();
  // 1. Hapus request yang sudah berada di luar window waktu
  pipeline.zremrangebyscore(key, 0, now - windowSizeMs);
  // 2. Tambahkan timestamp request saat ini ke ZSET
  pipeline.zadd(key, now, `${now}-${Math.random()}`);
  // 3. Hitung jumlah request di dalam window aktif
  pipeline.zcard(key);
  // 4. Perpanjang TTL kunci
  pipeline.expire(key, 60);

  const results = await pipeline.exec();
  const currentCount = results[2][1];

  return currentCount > limit; // true jika melampaui kuota
}
```

---

## 10. Practical Example: Implementasi Safe Distributed Lock (Node.js)

```javascript
const crypto = require('crypto');

class DistributedLock {
  constructor(redisClient) {
    this.redis = redisClient;
    this.UNLOCK_LUA = `
      if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
      else
        return 0
      end
    `;
  }

  async acquire(resourceKey, ttlMs = 10000, retryTimes = 3, retryDelayMs = 200) {
    const lockKey = `lock:${resourceKey}`;
    const token = crypto.randomUUID(); // Identitas unik worker

    for (let attempt = 0; attempt < retryTimes; attempt++) {
      // SET resourceKey token NX PX ttlMs
      const result = await this.redis.set(lockKey, token, 'NX', 'PX', ttlMs);
      if (result === 'OK') {
        return { acquired: true, token, lockKey };
      }
      // Tunggu dengan random jitter sebelum mencoba lagi
      await new Promise(r => setTimeout(r, retryDelayMs + Math.random() * 50));
    }

    return { acquired: false, token: null, lockKey: null };
  }

  async release(lockKey, token) {
    if (!lockKey || !token) return false;
    // Eksekusi pelepasan aman via Lua script atomik
    const result = await this.redis.eval(this.UNLOCK_LUA, 1, lockKey, token);
    return result === 1;
  }
}
```

---

## 11. Real World Example: Tiket Konser & Flash Sale E-Commerce

Pada penjualan tiket konser Coldplay di Jakarta:
- Ratusan ribu orang mengklik tombol "Beli Tiket" pada detik 10:00:00.
- Database relasional PostgreSQL tidak akan sanggup menahan 150.000 konkurensi update baris tabel `seats`.
- Solusi Arsitektur:
  1. Kuota kursi disimpan di Redis String Counter: `seat_available:CAT1 = 5000`.
  2. Saat user checkout, backend memanggil perintah atomik `DECR seat_available:CAT1`.
  3. Jika nilai balikan $\ge 0$, user diizinkan masuk ke antrean pembayaran. Jika nilai $< 0$, sistem langsung merespons "Tiket Habis" dalam waktu **0,4 milidetik**.
  4. Backend mengakuisisi Distributed Lock `lock:seat:CAT1:row12` untuk mencegah double-booking kursi spesifik.

---

## 12. Trade-offs

| Aspek | Local In-Memory Cache | Redis Standalone | Redis Cluster (Sharded) |
|---|---|---|---|
| **Latensi Akses** | ~100 nanodetik (Ekstrem) | ~0.5 - 2 milidetik (Jaringan) | ~1 - 3 milidetik (Jaringan + Routing) |
| **Kapasitas Penyimpanan**| Terbatas pada RAM pod lokal | Dibatasi oleh RAM 1 Server fisik | Terdistribusi (Multi-Terabyte) |
| **Konsistensi Lintas Pod**| Lemah (Setiap pod punya data beda)| Tinggi (Single Source of Cache) | *Eventual Consistency* saat replikasi master-slave |
| **Kompleksitas Operasional**| Nol (Tanpa server eksternal) | Menengah | Sangat Tinggi (Failover, Hash slots, Rebalancing) |
| **Ketahanan Kegagalan** | Data hilang saat pod restart | RDB / AOF snapshot ke disk | Otomatis failover via Redis Sentinel / Cluster |

---

## 13. When To Use
- **Real-Time Leaderboards:** Menghitung peringkat skor jutaan pemain game secara live menggunakan Redis Sorted Sets ($O(\log N)$).
- **Distributed Session Storage:** Menyimpan session token OAuth / JWT refresh tokens lintas ratusan instance backend.
- **High-Throughput Distributed Locking:** Menjamin mutual exclusion untuk proses batching atau alokasi resource terbatas.
- **Publisher/Subscriber & Real-Time Event Notification:** Menyiarkan event WebSocket antar pod server.

---

## 14. When NOT To Use
- **Primary Source of Record untuk Transaksi Finansial Kompleks:** Redis memiliki mekanisme persistensi (AOF & RDB), namun replikasi master-replica Redis secara default adalah asinkron (*Asynchronous Replication*). Jika node master mati sebelum data tersinkron ke slave, data transaksi dapat hilang.
- **Relational Data dengan Query Ad-hoc Multi-Filter:** Melakukan query kompleks dengan filter 5 atribut berbeda sangat tidak efisien di Redis dibanding SQL indexing.
- **Data Dataset Dingin (*Cold Storage*):** Menyimpan data arsip 50 Terabyte yang hanya dibaca sekali setahun di RAM Redis adalah pemborosan biaya infrastruktur yang ekstrem.

---

## 15. Common Mistakes
1. **Menggunakan `KEYS *` di Server Produksi:** Perintah `KEYS *` memindai seluruh memori Redis. Karena Redis bersifat single-threaded, perintah ini akan membekukan (*block*) seluruh request aplikasi selama bermenit-menit hingga terjadi downtime global. **Gunakan `SCAN` sekuensial!**
2. **Distributed Lock Tanpa TTL:** Mengunci resource tanpa parameter `PX/EX`. Saat worker pemegang kunci mati mendadak, sistem akan mengalami *Deadlock Abadi*.
3. **Mengabaikan BigKeys:** Menyimpan list atau hash dengan jutaan elemen dalam satu kunci. Operasi penghapusan (`DEL`) pada kunci raksasa dapat memicu latensi spike puluhan detik.
4. **Tidak Menggunakan Pipeline untuk Batch Command:** Mengirim 1.000 perintah Redis satu per satu secara sekuensial melalui jaringan (menghabiskan 1.000 x RTT jaringan), alih-alih membungkusnya dalam satu *Pipeline Batch*.

---

## 16. Best Practices

### Must Have
- Haramkan penggunaan perintah berbahaya di file konfigurasi `redis.conf`: `rename-command KEYS ""` dan `rename-command FLUSHALL ""`.
- Selalu sertakan identitas unik (UUID token) dan evaluasi via Lua script pada setiap implementasi Distributed Lock.
- Terapkan **Random Jitter** pada seluruh TTL cache untuk menghindari Cache Avalanche.

### Recommended
- Gunakan arsitektur Redis Sentinel atau Redis Cluster untuk menjamin *High Availability (HA)* otomatis saat node master down.
- Gunakan algoritma **Probabilistic Early Expiration (XFetch)** untuk kunci data populer dengan biaya komputasi tinggi.

### Advanced
- Atur parameter persistensi `appendfsync everysec` untuk menyeimbangkan performa I/O disk dengan keamanan retensi data (maksimal data loss 1 detik saat bencana fisik server).

---

## 17. Troubleshooting

| Gejala Masalah | Indikasi Akar Masalah | Langkah Investigasi | Solusi Perbaikan |
|---|---|---|---|
| **Redis Server Latency Spikes (Perintah Lambat)** | Eksekusi perintah ber-kompleksitas $O(N)$ atau BigKey deletion | Jalankan `SLOWLOG GET 10` dan `redis-cli --bigkeys` | Ganti `KEYS` dengan `SCAN`, pecah struktur data besar menjadi sub-keys |
| **Koneksi Ditolak: `OOM command not allowed`** | Penggunaan memori melampaui batas `maxmemory` dan policy `noeviction` aktif | Cek `INFO memory` -> `used_memory` vs `maxmemory` | Ubah policy ke `allkeys-lru` atau perbesar RAM instance |
| **Distributed Lock Bocor (Dua Worker Jalan Serentak)** | Durasi eksekusi worker melebihi TTL lock sebelum selesai | Analisis durasi pekerjaan vs TTL, periksa clock drift | Naikkan TTL dan implementasikan daemon *Lock Heartbeat / Auto-Renewal (Watchdog)* |

---

## 18. Exercise
1. Tulis skrip simulasi distributed lock dengan Node.js atau Python.
2. Simulasikan 5 worker konkuren yang mencoba mengakuisisi lock yang sama. Buktikan hanya 1 worker yang berhasil dan 4 lainnya masuk ke antrean retry.
3. Simulasikan skenario worker crash di tengah pekerjaan, dan buktikan mekanisme TTL otomatis membebaskan lock untuk worker berikutnya setelah batas waktu berakhir.

---

## 19. Challenge
Rancang arsitektur mitigasi **Cache Breakdown** pada sistem live score pertandingan sepak bola piala dunia (10.000.000 penonton melihat skor pertandingan yang sama):
1. Rancang implementasi algoritma **XFetch** (Probabilistic Early Expiration) dengan formula:
   $$\Delta t - \beta \times \ln(\text{rand}()) \times \text{computation\_time} > \text{expiry}$$
2. Jelaskan bagaimana satu thread background me-refresh data skor beberapa detik sebelum kunci kedaluwarsa secara probabilistik tanpa memicu lonjakan query ganda ke database SQL!

---

## 20. Summary
Redis adalah pilar utama infrastruktur backend modern yang menggabungkan kecepatan in-memory dengan fleksibilitas struktur data tingkat lanjut. Penguasaan pola atomik, Distributed Lock berbasis Lua, serta mitigasi arsitektur terhadap Cache Stampede dan Avalanche menjadi pembeda utama antara engineer pemula dengan Senior Backend Architect yang mampu mengelola jutaan transaksi per detik dengan stabilitas absolut.

---
[⬅️ Module 01: Pola Caching & Algoritma Eviksi](./Module-01-Pola-Caching-dan-Algoritma-Eviksi-LRU-LFU.md) | [📋 Silabus Induk](../README.md) | [BAB 06 Quiz & Challenge ➡️](./BAB-06-Quiz-dan-Challenge.md)
---
