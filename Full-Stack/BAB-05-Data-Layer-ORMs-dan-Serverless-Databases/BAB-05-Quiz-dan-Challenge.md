---
[⬅️ Module 02: Serverless DB & Edge Caching](./Module-02-Serverless-DB-Edge-Caching-Zero-Downtime-Migration.md) | [📋 Silabus Induk](../README.md) | [BAB 06: Autentikasi Full-Stack & WebAuthn ➡️](../BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/Module-01-Authjs-Secure-Cookies-OAuth-Edge-Guards.md)
---

# BAB 05: Evaluasi Pembelajaran — Quiz, Challenge, & Knowledge Check

## 1. Uji Pemahaman Mandiri (Quiz)

### A. Soal Tingkat Dasar (Basic Questions)
1. **Mengapa ekosistem Serverless Functions (seperti Vercel atau AWS Lambda) rentan mengalami galat *Database Connection Exhaustion* jika langsung membuka koneksi ke PostgreSQL?**
2. **Apa perbedaan mendasar antara cara kerja Drizzle ORM yang berbasis *TypeScript SQL dialect* dengan Prisma ORM yang mengandalkan *Rust binary query engine*?**
3. **Bagaimana PgBouncer dalam *Transaction Pooling Mode* mampu melayani ribuan request serverless hanya dengan menggunakan 10–20 koneksi database fisik?**
4. **Apa yang dimaksud dengan *Autoscaling to Zero* pada database serverless seperti Neon, dan bagaimana dampaknya terhadap tagihan infrastruktur?**
5. **Mengapa kita tidak boleh sembarangan mengeksekusi `ALTER TABLE DROP COLUMN` secara langsung pada database produksi yang sedang melayani traffic aktif?**

---

### B. Soal Tingkat Menengah (Intermediate Questions)
6. **Jelaskan masalah yang terjadi ketika driver database mencoba mengeksekusi *Named Prepared Statements* melalui PgBouncer yang berjalan dalam mode transaksi! Bagaimana cara menanganinya?**
7. **Bagaimana fenomena *Read-Your-Own-Writes Consistency* terjadi pada arsitektur database multi-region dengan Read Replicas, dan bagaimana strategi *session pinning* mengatasinya?**
8. **Jelaskan perbedaan mendasar antara *Session Pooling*, *Transaction Pooling*, dan *Statement Pooling* pada PgBouncer! Mengapa mode transaksi adalah opsi paling ideal untuk aplikasi Next.js App Router?**
9. **Bagaimana Upstash Redis REST API memungkinkan Edge Workers (seperti Cloudflare Workers) melakukan caching berkecepatan tinggi tanpa terhalang oleh keterbatasan koneksi TCP murni?**
10. **Jelaskan secara berurutan kelima fase dalam metodologi *Expand-and-Contract Pattern* saat Anda ingin memecah satu kolom lama menjadi dua kolom baru!**

---

### C. Soal Berbasis Skenario Arsitektur (Scenario-Based Questions)
11. **Skenario Kasus — Flash Sale E-Commerce & Race Condition**:
    Sebuah toko online meluncurkan program penjualan terbatas untuk 100 unit smartphone dengan diskon 80%. Sebanyak 25.000 user menekan tombol beli dalam kurun waktu 3 detik. Jika menggunakan Drizzle ORM dan PostgreSQL, bagaimana Anda menyusun transaksi SQL yang aman dari *overselling* (stok terjual minus) tanpa memicu *table lock* yang membekukan seluruh sistem?
12. **Skenario Kasus — Multi-Branch Preview Database di Monorepo CI/CD**:
    Sebuah tim dengan 15 engineer aktif membuka rata-rata 30 Pull Request setiap hari. Masing-masing PR memerlukan pengujian end-to-end terhadap database berukuran 200GB. Jelaskan bagaimana arsitektur *Database Branching* (Copy-on-Write) milik Neon menghemat biaya penyimpanan dan mempercepat siklus pengujian dibandingkan membuat database snapshot manual di RDS!
13. **Skenario Kasus — Cache Stamping (Thundering Herd Problem)**:
    Katalog produk unggulan di-cache di Upstash Redis dengan TTL 10 menit. Tepat saat TTL kadaluwarsa pada pukul 12:00:00, datang 5.000 request bersamaan untuk produk tersebut. Apa yang akan terjadi pada database PostgreSQL Anda, dan bagaimana Anda mengimplementasikan pola *Probabilistic Early Expiration* atau *Distributed Lock* untuk melindungi database?

---

## 2. Chapter Challenge: Resilient Multi-Tier Cache & Database Gateway

### Deskripsi Tantangan
Anda diminta merancang sistem gerbang data (*Data Access Gateway*) untuk platform streaming media. Sistem harus melayani data profil kreator konten dengan kriteria ketat:
- **Tingkat Ketersediaan Tinggi (SLA 99.99%)**.
- **Latensi Rata-rata Pembacaan < 10ms**.
- **Kekebalan Mutlak Terhadap Connection Exhaustion**.

### Kebutuhan & Spesifikasi:
1. **L1 In-Memory LRU Cache (Node.js)**:
   Simpan 100 entri profil yang paling sering diakses di memori instan instance dengan TTL 60 detik.
2. **L2 Edge Cache (Upstash Redis Simulation)**:
   Jika L1 miss, cari di L2 Cache dengan TTL 10 menit.
3. **L3 Database Layer dengan Transaction Pooler**:
   Jika L1 dan L2 miss, baca dari Primary Database melalui pooler. Setelah data diambil, isi L2 dan L1 secara berjenjang (*Cache Warming*).
4. **Invalidation Pipeline**:
   Saat kreator memperbarui bio atau foto profilnya, gerbang harus mengosongkan L1 lokal dan L2 Redis, lalu menandai sesi kreator tersebut agar membaca langsung dari Primary DB selama 3 detik pasca-mutasi (*Read-Your-Own-Writes Protection*).

---

## 3. Knowledge Check & Mastery Checklist

### Yang Wajib Anda Pahami:
- [ ] Dampak arsitektur stateless serverless terhadap pool koneksi database relasional tradisional.
- [ ] Peran vital connection pooler (PgBouncer, Neon Pooler, RDS Proxy) dalam menjaga stabilitas database.
- [ ] Perbedaan trade-off arsitektur antara Drizzle ORM (ringan, edge-ready) dan Prisma ORM (abstraksi tinggi, engine binary).
- [ ] Metodologi migrasi skema *Expand and Contract* untuk menjaga uptime 100% pada sistem produksi.

### Yang Tidak Perlu Anda Hafal di Luar Kepala:
- Konfigurasi baris-per-baris file `pgbouncer.ini` (cukup pahami konsep `pool_mode = transaction` dan port koneksinya).
- Sintaks spesifik seluruh dialek DDL Postgres (seperti tipe data spesifik geom / postgis)—dapat dirujuk dari dokumentasi resmi Drizzle/Postgres sesuai kebutuhan.

### Yang Harus Bisa Anda Lakukan:
- [ ] Mendeklarasikan skema tabel relasional menggunakan Drizzle ORM lengkap dengan relasi, indeks, dan default value.
- [ ] Mengatur connection pooler pada Next.js App Router agar tidak bocor (*leak*) saat proses development hot-reload.
- [ ] Menerapkan pola Cache-Aside menggunakan Redis di environment serverless.
- [ ] Merancang dan mengeksekusi migrasi skema database tanpa downtime (*Zero-Downtime Migration*).

---

## 4. Ringkasan Bab (Chapter Summary)
Bab 05 telah mengungkap pilar krusial pengelolaan data dalam aplikasi web full-stack modern:
1. **Modern ORM & Query Builders** seperti Drizzle dan Kysely mengembalikan kendali query dan efisiensi memori kepada pengembang, menghilangkan beban *cold start* yang selama ini menjadi kendala utama engine biner di lingkungan serverless.
2. **Connection Pooling** adalah penyelamat utama arsitektur serverless, bertindak sebagai pengatur lalu lintas yang memultipleks ribuan request transien ke segelintir koneksi database fisik yang stabil.
3. **Serverless Database & Edge Caching** membebaskan komputasi dari penyimpanan, memungkinkan skalabilitas elastis dari nol dan distribusi data global berlatensi rendah.
4. **Expand and Contract Pattern** membuktikan bahwa evolusi skema database berskala besar tidak harus mengorbankan ketersediaan sistem dan kenyamanan pengguna.

Dengan data layer yang kokoh, cepat, dan aman, kini kita siap melangkah ke **BAB 06: Autentikasi & Sesi Full-Stack**, di mana kita akan membedah arsitektur Auth.js, proteksi cookie JWT di edge, serta standar keamanan masa depan: WebAuthn / Passkeys berbasis biometrik!

---
[⬅️ Module 02: Serverless DB & Edge Caching](./Module-02-Serverless-DB-Edge-Caching-Zero-Downtime-Migration.md) | [📋 Silabus Induk](../README.md) | [BAB 06: Autentikasi Full-Stack & WebAuthn ➡️](../BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/Module-01-Authjs-Secure-Cookies-OAuth-Edge-Guards.md)
---
