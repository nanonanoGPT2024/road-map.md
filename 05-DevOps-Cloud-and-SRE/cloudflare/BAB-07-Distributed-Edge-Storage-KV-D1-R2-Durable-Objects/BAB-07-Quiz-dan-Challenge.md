# BAB 07: Distributed Edge Storage & State Management - Evaluasi

## 1. Basic Questions (5 Soal)

**Soal 1:**
Manakah model konsistensi data yang secara inheren diterapkan oleh Workers KV di seluruh edge node global Cloudflare?
A. Strict Serializability  
B. Linearizable Consistency  
C. Eventual Consistency  
D. Strong Snapshot Isolation  

**Soal 2:**
Karakteristik finansial dan operasional paling signifikan dari Cloudflare R2 jika dibandingkan dengan Amazon AWS S3 konvensional adalah:
A. R2 tidak mendukung enkripsi rest data.  
B. R2 tidak mengenakan biaya transfer data keluar (*zero egress bandwidth fees*).  
C. R2 hanya bisa diakses via GraphQL API.  
D. R2 membatasi ukuran bucket maksimum 100 Megabytes.  

**Soal 3:**
Pada Cloudflare D1, bagaimana arsitektur database menangani operasi modifikasi penulisan (`INSERT`/`UPDATE`) yang dikirim dari edge node Tokyo sementara Primary Database disetel di region Western Europe?
A. D1 mengeksekusi penulisan secara lokal di Tokyo lalu melakukan master-master merge.  
B. D1 menolak penulisan karena Tokyo berada di luar region primary.  
C. Permintaan write secara transparan diforward ke Primary Database di Western Europe melalui internal backplane Cloudflare.  
D. Write disimpan di KV terlebih dahulu sebelum di-flush mingguan ke D1.  

**Soal 4:**
Berapa jumlah instance virtual Isolate aktif yang dijamin oleh runtime Cloudflare untuk satu ID unik Durable Object pada satu waktu di seluruh jaringan edge global?
A. Satu instance per PoP.  
B. Tepat satu instance secara global (*single-instance guarantee*).  
C. Tak terbatas, bergantung pada jumlah core CPU server fisik.  
D. Tiga instance untuk pembentukan kuorum Raft.  

**Soal 5:**
Algoritma indeks pencarian tetangga terdekat (*Approximate Nearest Neighbor*) standar yang diimplementasikan pada Cloudflare Vectorize untuk pencarian embedding adalah:
A. B-Tree Plus Index  
B. Linear Sequential Scan  
C. Hierarchical Navigable Small World (HNSW)  
D. Radix Trie Sort  

---

## 2. Intermediate Questions (5 Soal)

**Soal 1:**
Sebuah aplikasi absensi flash sale mengalami anomali di mana data saldo tiket bertambah atau berkurang secara acak saat ribuan pengguna menekan tombol "Klaim" secara bersamaan di berbagai negara. Aplikasi menggunakan Workers KV dengan pola: `const v = await KV.get(); await KV.put(v - 1);`. Mengapa bug ini terjadi secara arsitektural dan bagaimana cara memperbaikinya?
A. Terjadi DNS routing race; perbaiki dengan membeli dedicated IP.  
B. Terjadi Read-Modify-Write Race Condition karena KV tidak memiliki distributed lock; ganti primitif counter state tersebut menggunakan Durable Objects.  
C. Ukuran integer melebihi batas 512 bytes KV; perbaiki dengan mengonversi nilai menjadi format Hexadecimal.  
D. Cache TTL KV terlalu pendek; atur `expirationTtl` ke 86400 detik.  

**Soal 2:**
Mengapa Durable Objects membutuhkan pemanggilan method `this.state.blockConcurrencyWhile()` di dalam blok `constructor`-nya ketika memulihkan state dari storage persisten?
A. Untuk memblokir eksekusi thread sistem operasi host agar RAM server tidak meluap.  
B. Untuk memastikan incoming fetch requests/events ditahan (*queued*) sampai data inisialisasi selesai di-load ke memory, menghindari eksekusi logika bisnis dengan state kosong/usang.  
C. Untuk mengenkripsi disk storage Durable Objects menggunakan master key.  
D. Untuk memaksa isolate mematikan koneksi WebSockets yang menggantung.  

**Soal 3:**
Dalam mendesain query performa tinggi pada Cloudflare D1, mengapa pola eksekusi berulang `await db.prepare(...).run()` di dalam perulangan array JavaScript dianggap sebagai *anti-pattern*, dan apa alternatif terbaiknya?
A. Membakar limitasi memori Worker; gunakan dynamic string interpolation.  
B. Memicu multiple network round-trip overhead antara worker isolate dan primary/replica engine; gunakan metode `db.batch([...])` untuk eksekusi atomik dalam single network trip.  
C. SQLite tidak mengizinkan lebih dari satu query per worker execution cycle; gunakan Durable Objects sebagai wrapper D1.  
D. Perulangan JS memicu locking engine secara permanen; gunakan cron trigger untuk mengeksekusi satu per satu query.  

**Soal 4:**
Fitur *WebSocket Hibernation API* pada Cloudflare Durable Objects dirancang untuk mengatasi limitasi beban sistem apa?
A. Menghilangkan batasan ukuran pesan WebSocket yang awalnya 32 KB.  
B. Menjaga koneksi ribuan client tetap terbuka di edge tanpa membebankan durasi penagihan CPU Isolate Durable Object saat tidak ada transmisi data yang aktif.  
C. Mengubah pesan teks WebSocket menjadi protokol UDP binary secara otomatis.  
D. Mem-bypass firewall Layer 7 Cloudflare untuk inspeksi WebSocket payloads.  

**Soal 5:**
Seorang engineer ingin mengonfigurasi replikasi read pada Cloudflare D1. Pernyataan manakah yang paling akurat mengenai model konsistensi pembacaan (*Read Consistency*) dari sebuah replica D1?
A. Replica selalu strictly synchronous; write tidak akan diakui berhasil jika seluruh replica global belum commit data.  
B. Replica menerima pembaruan secara asinkron dari Primary WAL stream; pembacaan dari replica mungkin memiliki jeda replikasi mikro-detik (*replication lag*) terhadap penulisan terakhir di primary.  
C. D1 tidak mendukung konsep replica; semua operasi read langsung dilempar ke disk Primary Location.  
D. Replica hanya melayani data yang berumur lebih dari 24 jam.  

---

## 3. Scenario-Based Questions (3 Kasus Nyata)

### Skenario 1: The Black Friday Inventory Collapse
Sebuah unicorn e-commerce global meluncurkan program potongan harga 90% untuk 1.000 unit konsol game. Arsitek mereka memutuskan menaruh status inventaris di **Cloudflare D1** (`UPDATE items SET stock = stock - 1 WHERE id = 'ps5' AND stock > 0`). 
Ketika sale dimulai, 250.000 request per detik datang dari Edge PoP di seluruh dunia. Dalam 5 detik pertama:
1. Terjadi ribuan error `SQLITE_BUSY` (Database Locked).
2. Beberapa transaksi sukses ter-rollback.
3. Latensi penulisan melonjak drastis hingga terjadi Worker Execution Timeout (>30 detik).

**Pertanyaan Analisis:**
Identifikasi *root cause* arsitektural kegagalan sistem di atas. Rancang perbaikan arsitektur state management menggunakan kombinasi komponen ekosistem Cloudflare edge agar sistem dapat menahan 250.000 RPS dengan latensi <50ms dan mutlak tanpa *overselling*!

---

### Skenario 2: Global Real-Time Whiteboard & Document Collaboration
Perusahaan SaaS EdTech membangun aplikasi papan tulis kolaboratif interaktif (mirip Miro/Figma) yang digunakan secara real-time oleh ribuan kelas daring di seluruh dunia. Kebutuhan teknis:
- Sinkronisasi kursor dan bentuk objek secara instan antar partisipan dalam satu ruang kelas (<30ms latency).
- Ruang kelas harus persisten; jika semua murid disconnect dan login besok pagi, data canvas papan tulis harus kembali seperti semula.
- Menghemat biaya komputasi server sekecil mungkin ketika ruang kelas sedang istirahat (idle).

**Pertanyaan Arsitektur:**
Jelaskan blueprint arsitektur implementasi sistem ini menggunakan Cloudflare Edge Storage:
1. Primitif apa yang menjadi inti pengelola canvas per ruang kelas?
2. Bagaimana mekanisme penanganan koneksi real-time saat idle vs aktif?
3. Di mana dan kapan data snapshot canvas disimpan untuk cold-storage durability jangka panjang?

---

### Skenario 3: Cross-Continent Disaster Recovery & Jurisdictional Compliance
Sebuah institusi perbankan digital Uni Eropa (EU) diwajibkan oleh regulator mematuhi aturan GDPR:
1. Seluruh data identitas nasabah (PII) dan dokumen KYC (PDF/JPG) dilarang keras disimpan atau diproses di luar yurisdiksi teritorial Uni Eropa.
2. Nasabah yang sedang berlibur di Singapura atau New York harus tetap bisa login dan mengunduh riwayat rekening mereka secara cepat.

**Pertanyaan Kepatuhan & Implementasi:**
Konfigurasikan strategi penempatan data menggunakan Cloudflare Storage Stack:
1. Bagaimana mengonfigurasi batasan teritorial pada **Cloudflare R2** dan **Durable Objects** agar data PII tidak keluar dari region EU?
2. Komponen apa yang digunakan untuk mempercepat akses nasabah yang sedang berada di luar negeri tanpa melanggar regulasi retensi data teritorial EU?

---

## 4. Practical Chapter Challenge: Resilient Global Voting Engine

### Deskripsi Tantangan
Bangun dan uji sistem penghitungan suara (*Global Live Polling Engine*) berskala enterprise dengan spesifikasi ketat:

1. **State Isolation**: Sistem harus mampu menghitung voting pemilihan real-time untuk ribuan topik berbeda secara independen.
2. **Strict Consistency**: Tidak boleh ada *lost votes* akibat race condition ketika 10.000 voter mengirim suara di milidetik yang sama untuk topik yang sama.
3. **Data Durability & Reporting**:
   - Setiap suara yang masuk harus dicatat di audit log database relasional edge (**D1**).
   - Akumulasi total voting harus dapat dibaca secara publik oleh jutaan penonton dengan latensi <15ms melalui layer caching (**KV**).
   - Laporan visual akhir polling diexport ke format JSON statis dan diarsipkan di object storage (**R2**).
4. **Resilience & Edge Safety**:
   - Terapkan mekanisme proteksi rate limiting per-IP menggunakan in-memory state tracking.
   - Buat skrip simulasi beban konkurensi untuk membuktikan keandalan konsistensi data (Zero Discrepancy Test).

---

### Kunci Jawaban Evaluasi

#### Kunci Jawaban Bagian 1: Basic
1. **C** (Eventual Consistency. KV mengorbankan konsistensi seketika demi kecepatan baca ultra-tinggi di seluruh PoP edge global).
2. **B** (R2 membedakan diri secara radikal dari AWS S3 dengan menggratiskan seluruh biaya egress data transfer).
3. **C** (Cloudflare secara otomatis mem-forward perintah mutasi SQL ke node Primary data center di Western Europe melalui backbone privat Cloudflare).
4. **B** (Tepat satu instance isolate aktif di seluruh dunia berdasarkan string identitas/ID unik yang ditentukan).
5. **C** (Hierarchical Navigable Small World / HNSW).

#### Kunci Jawaban Bagian 2: Intermediate
1. **B** (Workers KV tidak memiliki atomic locking primitif; pembacaan dan penulisan terpisah menghasilkan race condition. Durable Objects menyediakan single-threaded isolate execution yang menjamin mutasi counter serial dan konsisten).
2. **B** (Method `blockConcurrencyWhile` menjamin antrean request HTTP/WebSocket ditahan sementara sampai asynchronous state load selesai, mencegah corrupt read/write logic).
3. **B** (Setiap `run()` mandiri memicu round-trip komunikasi internal. Mengelompokkannya dalam `db.batch()` mengeksekusi transaksi secara paralel/pipelined dalam 1 kali round-trip).
4. **B** (WebSocket Hibernation menidurkan memori CPU isolate saat tidak ada event pesan data, drastis memangkas biaya durasi eksekusi tanpa memutuskan socket client).
5. **B** (Replikasi D1 adalah asynchronous log streaming. Ada replication lag sangat kecil antara commit di primary dan refleksi commit di read-replica).

#### Panduan Jawaban Bagian 3: Scenario-Based
- **Skenario 1**:
  - *Root Cause*: D1 adalah single-primary relational SQLite. Memaksa 250k write TPS ke satu single instance database memicu locking contention (`SQLITE_BUSY`), starvation koneksi, dan kegagalan transaksi berantai.
  - *Solusi*: Terapkan **Durable Objects Sharding / Actor Tier**. Alokasikan Durable Object untuk unit stok tiket. Validasi pengurangan stok langsung di dalam in-memory state Durable Object (mampu menangani puluhan ribu ops/detik secara konsisten). Transaksi yang lolos validasi dimasukkan ke buffer antrean asinkron (Cloudflare Queues) untuk ditulis secara santai dan teratur ke database D1 tanpa membebani lock SQLite.
- **Skenario 2**:
  - *Arsitektur*:
    1. Tiap Whiteboard ID diikat ke 1 instance **Durable Object**.
    2. Hubungkan client via **WebSockets dengan Hibernation API**. Isolate bangun hanya saat client mengirim event gambar koordinat, melakukan broadcast ke room participants, dan tidur kembali saat tidak ada aktivitas.
    3. State kanvas disimpan secara linearizable di DO SQLite Storage.
    4. Periodik Alarm (`alarm()` API pada DO) dijalankan setiap 15 menit untuk mengompilasi snapshot binary kanvas dan mengunggahnya ke **Cloudflare R2** sebagai checkpoint jangka panjang.
- **Skenario 3**:
  - *Kepatuhan*:
    1. Buat R2 Bucket dengan opsi *Jurisdiction*: `jurisdiction: "eu"`.
    2. Buat ID Durable Object menggunakan Location Hint EU: `env.DO.newUniqueId({ jurisdiction: "eu" })`. Ini menjamin instansiasi isolate dan persistent storage-nya secara mutlak berlokasi fisik di data center teritorial Uni Eropa.
    3. Nasabah di luar negeri mengakses worker terdekat mereka, lalu worker tersebut membuat tunneling terenkripsi ke Durable Object di region EU. Data tidak pernah disimpan persisten di disk server luar EU; hanya respons terenkripsi sementara yang dihantarkan ke browser nasabah.

---