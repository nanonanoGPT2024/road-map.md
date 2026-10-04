# BAB 05 - Quiz, Challenge, & Knowledge Check: Distributed Databases & Caching Layer di AWS

## 🧠 Quiz: Test Your Knowledge

Berikut adalah daftar pertanyaan untuk menguji pemahaman Anda mengenai Distributed Databases dan Caching Layer di ekosistem AWS. Coba jawab tanpa melihat dokumentasi terlebih dahulu.

### Basic Level (Konsep Inti)
1. **Perbandingan Layanan:** Apa perbedaan mendasar antara **Amazon RDS** dan **Amazon DynamoDB** dari sisi model data dan kasus penggunaannya?
2. **Caching:** Mengapa menambahkan *caching layer* sangat penting untuk aplikasi dengan trafik baca (read-heavy) yang tinggi?
3. **ElastiCache:** Sebutkan dua *engine* utama yang didukung secara *native* oleh layanan **Amazon ElastiCache** dan apa perbedaan utamanya secara singkat!
4. **Skalabilitas RDS:** Apa fungsi utama dari **Read Replica** pada Amazon RDS, dan bagaimana hal tersebut berbeda dengan **Multi-AZ Deployment**?
5. **Ketersediaan Tinggi:** Apa yang dimaksud dengan arsitektur *Multi-AZ* pada layanan database AWS?

### Intermediate Level (Mekanisme Internal & Troubleshooting)
1. **DynamoDB DAX:** Bagaimana cara kerja **DynamoDB Accelerator (DAX)** dalam menurunkan latensi *read* dari single-digit milidetik menjadi mikromilidetik? Kapan kita harus menggunakannya?
2. **Aurora Architecture:** Jelaskan mengapa arsitektur storage **Amazon Aurora** lebih cepat dan fault-tolerant dibandingkan arsitektur Amazon RDS tradisional.
3. **Caching Strategies:** Jelaskan perbedaan pola caching **Cache-Aside (Lazy Loading)** dan **Write-Through**. Apa kelebihan dan kelemahan masing-masing?
4. **DynamoDB Partitioning:** Bagaimana *Partition Key* dan *Sort Key* memengaruhi distribusi data fisik di dalam arsitektur DynamoDB? Mengapa penting memilih *Partition Key* dengan kardinalitas tinggi?
5. **Cache Eviction & Stampede:** Apa yang dimaksud dengan *Cache Stampede* (Thundering Herd)? Bagaimana strategi mitigasi yang bisa dilakukan saat menggunakan Redis?

### Scenario-Based Questions (Kasus Nyata Produksi)
1. **Skenario Flash Sale:** 
   Sebuah aplikasi e-commerce menggunakan Amazon RDS PostgreSQL. Saat event flash sale, database hampir kolaps karena *CPU Utilization* mencapai 99% akibat ribuan *query read* katalog produk per detik. Bagaimana merancang *caching layer* yang efisien untuk mengatasi masalah ini tanpa mengubah struktur database utama?
   
2. **Skenario Leaderboard Game:**
   Anda mengembangkan *backend* untuk mobile game global dengan puluhan juta pengguna aktif harian. Anda membutuhkan fitur *real-time leaderboard* yang selalu ter-update dan memiliki tingkat latensi (read/write) di bawah 5 milidetik. Arsitektur AWS database/caching seperti apa yang paling optimal?

3. **Skenario Disaster Recovery Finansial:**
   Sebuah institusi finansial membutuhkan database relasional (SQL) *mission-critical*. Syarat mutlaknya adalah memiliki tingkat *failover* lintas wilayah geografis (*Cross-Region*) dengan RPO (*Recovery Point Objective*) kurang dari 1 detik dan RTO (*Recovery Time Objective*) di bawah 1 menit. Solusi arsitektur database apa di AWS yang tepat untuk kebutuhan ini?

---

## 🚀 Chapter Challenge

**Tantangan Kasus: Desain Arsitektur Sistem Ride-Hailing Skala Global**

Anda diminta untuk mendesain lapisan arsitektur database dan *caching* untuk aplikasi *ride-hailing* (seperti Uber/Grab) yang melayani jutaan transaksi setiap hari di beberapa negara bagian.

**Kebutuhan (Requirements):**
1. **Lokasi Real-Time Driver:** Perlu menyimpan koordinat GPS terbaru dari driver yang diupdate setiap 3 detik.
2. **Riwayat Perjalanan (Trip History):** Menyimpan log transaksi historis setiap trip yang sudah selesai untuk keperluan audit dan analitik bulan lalu. Relasional antar entitas (User, Driver, Payment) sangat penting.
3. **Sistem Profil & Session User:** Latensi otentikasi dan pengecekan profil harus sangat cepat.
4. **Sistem Pencocokan (Matchmaking):** Membutuhkan query yang cepat berdasarkan jarak *geospatial*.

**Instruksi Tantangan:**
Tanpa memberikan solusi instan, gambarkan secara arsitektur (di atas kertas atau diagram):
- Komponen AWS apa saja (RDS/Aurora/DynamoDB/ElastiCache/DocumentDB/dsb.) yang akan digunakan untuk memenuhi **keempat kebutuhan di atas**.
- Bagaimana arsitektur ini akan menoleransi kegagalan satu Availability Zone (*AZ*).
- Pola interaksi antar layanan (Misalnya: Aplikasi -> ElastiCache -> RDS).

*(Diskusikan hasil perancangan ini dengan mentor atau tim Anda).*

---

## ✅ Knowledge Check & Checklist

### Saya harus memahami:
- Perbedaan model Relational (RDS, Aurora) vs NoSQL (DynamoDB).
- Cara kerja dan alasan penggunaan *Caching Layer* (ElastiCache, DAX).
- Konsep dasar ketersediaan tinggi: Multi-AZ vs Read Replica.
- Strategi Caching: *Lazy Loading*, *Write-Through*, dan *TTL* (Time-To-Live).

### Saya tidak perlu menghafal:
- Limitasi persis jumlah maksimum node dalam ElastiCache (karena dapat berubah seiring waktu sesuai update AWS), cukup tahu limitasi desain dasarnya.
- Detail implementasi internal protocol replikasi Aurora, cukup paham konsep log-based storage-nya.

### Saya harus bisa melakukan:
- Memilih layanan AWS Database yang tepat (RDS vs Aurora vs DynamoDB) berdasarkan studi kasus.
- Mendesain arsitektur *Caching* untuk mereduksi beban database.
- Melakukan troubleshooting dasar jika performa baca/tulis (*read/write*) mengalami hambatan (bottleneck).

### 📋 Checklist Modul 05
- [ ] Memahami konsep Relational dan NoSQL Database di AWS.
- [ ] Memahami cara kerja Amazon RDS dan Amazon Aurora.
- [ ] Memahami cara kerja Amazon DynamoDB dan DynamoDB DAX.
- [ ] Memahami peran Amazon ElastiCache (Redis & Memcached).
- [ ] Bisa membedakan berbagai Caching Strategy.
- [ ] Bisa merancang arsitektur data terdistribusi sederhana.
- [ ] Mampu menganalisis trade-off dari setiap layanan database AWS.