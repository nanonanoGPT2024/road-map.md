---
[⬅️ BAB 05 Quiz & Challenge](../BAB-05-Basis-Data-NoSQL-dan-NewSQL/BAB-05-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Redis Internals & Distributed Lock ➡️](./Module-02-Redis-Internals-Distributed-Lock-dan-Cache-Stampede.md)
---

# Module 01: Pola Caching & Algoritma Eviksi (LRU, LFU, ARC)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Memahami hierarki latensi memori (L1/L2 Cache, RAM vs SSD/NVMe vs Network/Database) dan nilai ekonomis caching.
- Menguasai 4 pola caching fundamental: **Cache-Aside (Lazy Loading)**, **Write-Through**, **Write-Back (Write-Behind)**, dan **Write-Around**.
- Menganalisis trade-off konsistensi data vs performa pada masing-masing pola caching.
- Memahami matematika dan struktur data di balik algoritma eviksi memori: **LRU (Least Recently Used)** dengan Doubly Linked List + Hash Map $O(1)$, **LFU (Least Frequently Used)**, **FIFO**, dan **ARC (Adaptive Replacement Cache)**.
- Menghitung rasio performa (*Cache Hit Ratio*) dan merancang strategi penentuan ukuran memori cache yang optimal.

---

## 2. Prerequisite
- Memahami struktur data dasar: Hash Map (Dictionary) dan Doubly Linked List (List Berkait Ganda).
- Memahami konsep latensi I/O disk vs RAM (Modul 02 BAB 02).
- Pemahaman dasar transaksi database dan konsistensi data (BAB 04).

---

## 3. Concept
Caching adalah mekanisme penyimpanan salinan data temporer pada media penyimpanan berkecepatan tinggi (biasanya RAM / In-Memory) agar pembacaan berikutnya dapat dilayani jauh lebih cepat daripada mengambilnya kembali dari media penyimpanan primer (Database RDBMS/NoSQL atau API eksternal).

Hukum Latensi Komputasi Modern:
- Akses CPU Register: ~1 nanodetik.
- Akses L1/L2 Cache: ~1 - 4 nanodetik.
- Akses RAM Fisik: ~100 nanodetik (0,1 mikrodetik).
- Baca SSD NVMe: ~10.000 nanodetik (10 - 50 mikrodetik).
- Query Database via Jaringan (TCP RTT + Disk I/O): ~5.000.000 - 50.000.000 nanodetik (5 - 50 milidetik).

Perbedaan kecepatan antara RAM dan Database adalah **10.000x hingga 100.000x lipat**. Caching adalah pertahanan utama arsitektur backend untuk melindungi database dari kehancuran akibat beban query berulang.

---

## 4. Why?
Tanpa caching:
1. **Database Overload:** Query kompleks yang melibatkan kalkulasi agregasi atau join multi-tabel akan dieksekusi berulang-ulang untuk ribuan pengguna yang meminta data yang persis sama.
2. **Latensi Tinggi:** Pengguna harus menunggu puluhan hingga ratusan milidetik untuk melihat konten yang jarang berubah (misal katalog produk, data user profile, trending topik).
3. **Biaya Infrastruktur Membengkak:** Menskalakan database SQL untuk melayani jutaan read-queries per detik membutuhkan instance raksasa (ribuan vCPU & Terabyte RAM) yang sangat mahal.
4. **Kerapuhan Terhadap Lonjakan Trafik (*Traffic Spikes*):** Lonjakan pengunjung secara tiba-tiba (misal event Flash Sale) dapat langsung membuat *Connection Pool* database kehabisan kuota dan mengalami downtime total (*Cascading Failure*).

---

## 5. What?
Komponen penting dalam strategi caching backend:
- **Cache Hit:** Data yang diminta ditemukan di dalam memori cache. Response langsung dikembalikan dengan latensi sub-milidetik.
- **Cache Miss:** Data tidak ditemukan di dalam cache. Backend harus melakukan *round-trip* ke database primer, menyimpan salinannya ke cache, lalu mengembalikannya ke pengguna.
- **Cache Eviction (Penggusuran):** Tindakan menghapus item data lama dari cache ketika kapasitas memori telah mencapai batas maksimum (RAM penuh) untuk memberi ruang bagi data baru.
- **TTL (Time-To-Live):** Masa kedaluwarsa suatu data di cache sebelum secara otomatis dihapus atau dianggap usang (*stale*).
- **Hit Ratio:** Metrik efektivitas cache yang dihitung dengan rumus:
  $$\text{Hit Ratio} = \frac{\text{Cache Hits}}{\text{Cache Hits} + \text{Cache Misses}} \times 100\%$$
  Sistem caching yang sehat di dunia produksi umumnya mempertahankan Hit Ratio $\ge 85\% - 98\%$.

---

## 6. How? (Arsitektur Pola Caching)

### A. Cache-Aside (Lazy Loading)
Aplikasi bertanggung jawab penuh membaca dan menulis ke cache dan database secara mandiri.
```
       [ Client Request ]
               │
               ▼
        [ Backend API ]
         /           \
   1. Get?           3. Save to Cache
       /               \
      ▼                 ▼
[ In-Memory Cache ]  [ In-Memory Cache ]
      │ (Miss)
   2. Read DB
      ▼
  [ Database ]
```
1. Backend memeriksa cache. Jika data ada (**Hit**), kembalikan langsung.
2. Jika tidak ada (**Miss**), backend membaca data dari database.
3. Backend menuliskan data tersebut ke cache (dengan TTL), lalu mengembalikannya ke client.
4. Ketika data diupdate: Backend memperbarui database, lalu menghapus (*invalidate/evict*) kunci tersebut dari cache.

### B. Write-Through Cache
Aplikasi selalu menulis data ke cache terlebih dahulu. Cache layer bertanggung jawab secara sinkron meneruskan data ke database utama sebelum mengembalikan respon sukses.
```
[ Backend API ] ──1. Write Data──▶ [ Cache Engine ] ──2. Sync Write──▶ [ Database ]
```
- **Kelebihan:** Data di cache selalu sinkron dan konsisten dengan database.
- **Kekurangan:** Latensi penulisan lebih lambat karena ada overhead 2 kali penulisan sekuensial.

### C. Write-Back (Write-Behind / Deferred Write)
Aplikasi menulis ke cache dan langsung mengembalikan sukses. Cache engine menyimpan data di memori dan secara asinkron (*batch/queue*) menulis data ke database di latar belakang.
```
[ Backend API ] ──1. Fast Write──▶ [ In-Memory Cache ] ──(Async Queue)──▶ [ Database ]
                                           │
                                  Ack Instan (< 1ms)
```
- **Kelebihan:** Latensi penulisan luar biasa cepat (sub-milidetik) dan mampu meredam lonjakan beban tulis database (*Write absorption*).
- **Kekurangan Risiko Bencana:** Jika server cache crash sebelum data tersinkronisasi ke disk database, data akan hilang permanen (*Data Loss*).

### D. Write-Around Cache
Aplikasi menulis data langsung ke database utama tanpa menyentuh cache. Data baru masuk ke cache hanya ketika pertama kali dibaca oleh user (melalui skema Cache-Aside).
- **Kelebihan:** Mencegah memori cache terbuang percuma (*Cache Pollution*) oleh data yang ditulis namun tidak pernah dibaca lagi (misal log audit, arsip berkas).

---

## 7. Analogy
Bayangkan Anda adalah seorang koki di restoran:
- **Database Utama** adalah gudang bahan makanan di lantai bawah tanah (perlu naik turun tangga 10 menit untuk mengambil bahan).
- **In-Memory Cache** adalah meja persiapan dapur tepat di depan Anda (bisa mengambil garam dan merica dalam waktu 1 detik).
- **Cache-Aside:** Anda melihat ke meja. Jika merica tidak ada, Anda lari ke gudang bawah tanah, mengambil sebungkus merica, meletakkannya di meja untuk pesanan berikutnya, lalu mulai memasak.
- **Eviction (Penggusuran):** Meja persiapan Anda sempit (hanya muat 10 toples bumbu). Jika meja penuh dan Anda butuh bumbu baru, Anda harus membuang atau memindahkan toples bumbu yang paling jarang dipakai (**LRU**) kembali ke gudang.

---

## 8. Diagram Algoritma Eviksi: LRU (Least Recently Used)

Untuk mengimplementasikan LRU dengan performa $O(1)$ mutlak untuk operasi `GET` dan `PUT`:
Kita memadukan **Hash Map** untuk pencarian instan berdasarkan kunci, dan **Doubly Linked List** untuk melacak urutan pemakaian dari *Most Recently Used (Head)* ke *Least Recently Used (Tail)*.

```
       Hash Map (O(1) Lookup)
   ┌─────────┬──────────────┐
   │  "key1" │  Pointer N1  │
   │  "key2" │  Pointer N2  │
   │  "key3" │  Pointer N3  │
   └─────────┴──────────────┘
               │
               ▼
   [HEAD] ◄──► [Node 2: key2] ◄──► [Node 1: key1] ◄──► [Node 3: key3] ◄──► [TAIL]
  (Paling baru diakses)                                (Paling lama / Eviction Target)
```
- Setiap kali data diakses (`GET`) atau diupdate (`PUT`), nodenya dipindahkan ke posisi terdepan (**HEAD**).
- Jika kapasitas memori penuh saat menambahkan kunci baru, node di posisi paling belakang (**TAIL**) dibuang seketika ($O(1)$), dan referensinya dihapus dari Hash Map.

---

## 9. Simple Example: LRU Cache Implementation (Node.js)

```javascript
class LRUNode {
  constructor(key, value) {
    this.key = key;
    this.value = value;
    this.prev = null;
    this.next = null;
  }
}

class LRUCache {
  constructor(capacity) {
    this.capacity = capacity;
    this.map = new Map();
    this.head = new LRUNode(null, null); // Dummy head
    this.tail = new LRUNode(null, null); // Dummy tail
    this.head.next = this.tail;
    this.tail.prev = this.head;
  }

  _remove(node) {
    node.prev.next = node.next;
    node.next.prev = node.prev;
  }

  _addToHead(node) {
    node.next = this.head.next;
    node.prev = this.head;
    this.head.next.prev = node;
    this.head.next = node;
  }

  get(key) {
    if (!this.map.has(key)) return null;
    const node = this.map.get(key);
    this._remove(node);
    this._addToHead(node); // Promosikan ke Head (Most Recently Used)
    return node.value;
  }

  put(key, value) {
    if (this.map.has(key)) {
      const node = this.map.get(key);
      node.value = value;
      this._remove(node);
      this._addToHead(node);
      return;
    }

    if (this.map.size >= this.capacity) {
      // Evict Tail (Least Recently Used)
      const lru = this.tail.prev;
      this._remove(lru);
      this.map.delete(lru.key);
    }

    const newNode = new LRUNode(key, value);
    this.map.set(key, newNode);
    this._addToHead(newNode);
  }
}
```

---

## 10. Practical Example: Cache-Aside Service dengan Invalidation

```javascript
class ProductService {
  constructor(databaseClient, cacheClient) {
    this.db = databaseClient;
    this.cache = cacheClient;
    this.CACHE_TTL_SECONDS = 300; // 5 Menit
  }

  async getProductById(productId) {
    const cacheKey = `product:${productId}`;

    // 1. Coba baca dari Cache
    const cachedData = await this.cache.get(cacheKey);
    if (cachedData) {
      return JSON.parse(cachedData); // Cache HIT
    }

    // 2. Cache MISS: Baca dari Database Primer
    const product = await this.db.query('SELECT * FROM products WHERE id = $1', [productId]);
    if (!product) return null;

    // 3. Simpan ke Cache dengan TTL terukur
    await this.cache.set(cacheKey, JSON.stringify(product), 'EX', this.CACHE_TTL_SECONDS);

    return product;
  }

  async updateProductPrice(productId, newPrice) {
    // 1. Update Database Primer terlebih dahulu (Single Source of Truth)
    await this.db.query('UPDATE products SET price = $1 WHERE id = $2', [newPrice, productId]);

    // 2. Invalidate Cache: Hapus kunci agar request berikutnya mengambil data teranyar
    const cacheKey = `product:${productId}`;
    await this.cache.del(cacheKey);
  }
}
```

---

## 11. Real World Example: Caching di Sistem E-Commerce Flash Sale

Pada event belanja 11.11, halaman produk unggulan (*Smartphone Flagship*) diakses oleh 500.000 user secara simultan dalam 5 detik pertama:
1. **Lapisan 1 (CDN Edge Cache):** Asset statis (gambar, CSS, JS) di-cache di Cloudflare/CloudFront di tepi jaringan terdekat dengan ISP user.
2. **Lapisan 2 (Reverse Proxy / Nginx Cache):** HTML markup dasar di-cache dengan *Micro-caching* (TTL 1 detik) untuk meredam jutaan request repetitif.
3. **Lapisan 3 (Application In-Memory Redis Cache):** Data inventaris stok dan harga dibaca dari Redis Cluster dengan strategi Cache-Aside dan penanganan *Distributed Mutex*. Database PostgreSQL hanya melayani transaksi checkout pembayaran resmi.

Hasil: Beban database turun dari 500.000 query/detik menjadi hanya 50 query/detik (**99.99% Database Offload**).

---

## 12. Trade-offs

| Aspek | Tanpa Caching | Cache-Aside | Write-Through | Write-Back |
|---|---|---|---|---|
| **Latensi Baca** | Lambat (Disk I/O) | Cepat (Sub-ms saat Hit) | Sangat Cepat | Sangat Cepat |
| **Latensi Tulis** | Normal (DB Write) | Normal (DB Write + Del) | Lebih Lambat (DB + Cache) | Super Cepat (Memori saja) |
| **Konsistensi Data** | Konsistensi Kuat (ACID) | Konsistensi Terkendali (Bisa Stale saat balapan) | Tinggi (Selalu sinkron) | Rendah (Bisa kehilangan data saat crash) |
| **Beban Database** | 100% Beban Ditanggung DB | Sangat Ringan untuk Read | Sedang | Sangat Ringan (Batch Write) |
| **Kompleksitas Kode** | Sederhana | Sedang | Tinggi | Sangat Tinggi |

---

## 13. When To Use
- **Read-Heavy Workloads:** Sistem dengan rasio baca banding tulis tinggi (misal: 80% Read vs 20% Write, seperti portal berita, katalog toko, media sosial).
- **Hasil Komputasi Mahal:** Data hasil kalkulasi matematis berat, agregasi reporting, atau hasil crawling API eksternal yang lambat.
- **Session State & Auth Tokens:** Data sesi login pengguna yang harus diverifikasi pada setiap request HTTP tanpa perlu membebani database auth.

---

## 14. When NOT To Use
- **Data Sangat Dinamis dengan Frekuensi Tulis Tinggi:** Jika data berubah setiap 100 milidetik dan jarang dibaca ulang (misal: koordinat GPS kendaraan otonom), caching hanya akan menghabiskan CPU dan RAM tanpa menghasilkan Cache Hit.
- **Sistem Transaksional Finansial Kritis:** Pengecekan saldo rekening bank atau verifikasi ledger akuntansi yang menuntut jaminan konsistensi serializable secara mutlak tidak boleh membaca data usang dari cache.
- **Data Dataset Terlalu Besar yang Jarang Diakses:** Menaruh data puluhan terabyte dengan pola akses acak (*Random Scan*) akan menghancurkan efisiensi algoritma eviksi (*Cache Thrashing*).

---

## 15. Common Mistakes
1. **Mengabaikan TTL (Time-To-Live):** Menyimpan data di cache tanpa batas kedaluwarsa. Jika mekanisme invalidasi gagal, data usang (*stale data*) akan tersimpan selamanya.
2. **Melakukan Update Cache alih-alih Delete (Invalidate):** Pada skema konkurensi tinggi, melakukan `cache.set(new_data)` saat update DB sering kali berakibat data basi menimpa data baru karena *race condition* urutan eksekusi antar-thread. Rekomendasi terbaik: **Selalu lakukan `cache.del(key)`!**
3. **Mengabaikan Cache Size & Eviction Strategy:** Menjalankan Redis dengan kapasitas tak terbatas hingga kehabisan RAM OS (*Out-Of-Memory / OOM Killer* mematikan proses database).
4. **Cache as Single Source of Truth:** Menggunakan cache in-memory tanpa persistensi atau replikasi untuk menyimpan data bisnis krusial.

---

## 16. Best Practices

### Must Have
- Selalu tetapkan **TTL** untuk setiap kunci yang disimpan di cache.
- Tentukan kebijakan eviksi yang eksplisit (misal: `maxmemory-policy allkeys-lru`).
- Gunakan struktur penamaan kunci (*Key Namespacing*) yang terstandarisasi, misalnya: `domain:entity:id:field` (contoh: `ecommerce:product:8841:inventory`).

### Recommended
- Implementasikan metrik observability: Pantau *Hit Ratio*, *Memory Fragmentation Ratio*, dan *Eviction Rate* via Prometheus & Grafana.
- Terapkan *Jitter* (variasi acak) pada TTL untuk mencegah fenomena *Cache Avalanche* (seluruh kunci kedaluwarsa serentak di waktu yang sama).

### Advanced
- Gabungkan dua lapisan cache: **Local In-Process Memory Cache** (misal Google Guava di Java atau `lru-cache` di Node.js untuk latensi 100 nanodetik) + **Distributed Remote Cache** (Redis/Memcached cluster untuk koordinasi multi-instance).

---

## 17. Troubleshooting

| Masalah | Kemungkinan Akar Masalah | Cara Diagnosa | Solusi Mitigasi |
|---|---|---|---|
| **Hit Ratio Tiba-Tiba Drop** | Pola query berubah, kunci ter-evict terlalu cepat, atau TTL terlalu singkat | Cek `INFO stats` di Redis: periksa rasio `keyspace_hits / (keyspace_hits + keyspace_misses)` | Tingkatkan alokasi RAM cache atau perpanjang durasi TTL data populer |
| **High Memory Usage (OOM)** | Kebocoran kunci (kunci tanpa TTL), fragmentasi memori | Jalankan `MEMORY USAGE <key>` atau periksa `used_memory_rss` | Aktifkan `activedefrag yes` di Redis, audit kunci tanpa TTL dengan scanner |
| **Data Antara DB dan Cache Tidak Konsisten** | Invalidation logic terlewati saat operasi database update/delete | Logging pada alur update, bandingkan isi cache dan query DB | Gunakan pola CDC (*Change Data Capture*) via Debezium atau pastikan `cache.del` selalu terpanggil |

---

## 18. Exercise
1. Tulis kode algoritma LRU Cache menggunakan Doubly Linked List murni dan Hash Map dalam bahasa pilihan Anda tanpa library eksternal.
2. Uji implementasi tersebut dengan kapasitas 3 elemen. Masukkan kunci 1, 2, 3. Akses kunci 1. Masukkan kunci 4. Buktikan bahwa kunci 2 yang tereliminasi (karena kunci 1 baru saja diakses).
3. Modifikasi kode agar setiap item memiliki atribut `expiresAt` (TTL) dan otomatis mengembalikan `null` jika waktu saat `get()` telah melampaui TTL.

---

## 19. Challenge
Rancang arsitektur caching untuk sistem feed media sosial (mirip Twitter / X) dengan 100 juta pengguna:
1. Analisis perbedaan strategi caching antara user reguler (memiliki 200 follower) vs selebritas (memiliki 50 juta follower - *The Celebrity Problem*).
2. Tentukan kapan harus menggunakan pendekatan *Fan-out-on-Write* (Push to Redis Timeline Cache) vs *Fan-out-on-Read* (Pull & Aggregate).
3. Hitung estimasi kebutuhan RAM Redis jika setiap user menyimpan 800 tweet ID terakhir di memori!

---

## 20. Summary
Caching adalah seni mengorbankan memori RAM dan jaminan konsistensi absolut demi mendapatkan latensi sub-milidetik dan melindungi stabilitas database primer. Dengan menguasai pola Cache-Aside dan prinsip matematis algoritma eviksi LRU, seorang arsitek backend mampu mengoptimalkan performa sistem hingga ribuan kali lipat secara ekonomis dan terukur.

---
[⬅️ BAB 05 Quiz & Challenge](../BAB-05-Basis-Data-NoSQL-dan-NewSQL/BAB-05-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Redis Internals & Distributed Lock ➡️](./Module-02-Redis-Internals-Distributed-Lock-dan-Cache-Stampede.md)
---
