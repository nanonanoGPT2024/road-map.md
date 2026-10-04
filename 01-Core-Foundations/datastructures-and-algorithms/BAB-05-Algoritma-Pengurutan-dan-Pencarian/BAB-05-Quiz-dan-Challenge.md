# BAB 05: Quiz, Challenge, & Knowledge Check
**Bab 05: Hash Tables, Hash Functions, & Collision Resolution Strategy**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Uniformity, Avalanching, dan Algoritma Hashing**  
   Jelaskan mengapa fungsi hash yang sekadar melakukan operasi *modulo* terhadap integer mentah ($h(k) = k \pmod M$) sangat rentan menghasilkan performa terburuk ($O(N)$) pada distribusi data dunia nyata (misalnya: pointer memori yang merupakan kelipatan 8, atau nomor port jaringan). Apa parameter matematis dan properti statistik (*avalanche effect*) yang harus dipenuhi oleh fungsi hash non-kriptografis modern (seperti MurmurHash3, CityHash, atau xxHash) agar meminimalkan deviasi standar dari kedalaman *bucket*?

2. **Dilema Arsitektur Memori: Separate Chaining vs Open Addressing**  
   Bandingkan resolusi tabrakan menggunakan *Separate Chaining* (Linked List/Tree pada setiap slot) dengan *Open Addressing* (khususnya *Linear Probing*) ditinjau dari hierarki memori CPU (*L1/L2/L3 cache lines*, *pointer chasing*, dan *spatial locality*). Pada densitas data seperti apa *Open Addressing* mulai kehilangan keunggulan cache-nya dan justru mengalami degradasi drastis dibanding *Separate Chaining*?

3. **Amortized Analysis dan Matematika Load Factor ($\alpha$)**  
   Secara empiris dan teoritis, mengapa ambang batas *load factor* ($\alpha = N/M$) pada sebagian besar runtime enterprise (misalnya Java `HashMap` atau Go `runtime.hmap`) diatur pada kisaran $0.70$ hingga $0.75$? Buktikan secara matematis mengapa ekspansi kapasitas harus bersifat geometrik (pengali faktor $2\times$) alih-alih aritmetika (misalnya menambah $K$ slot tetap) untuk mempertahankan kompleksitas waktu teramortisasi $O(1)$ pada operasi `insert`.

4. **Anatomi Tombstone pada Open Addressing**  
   Pada skema resolusi *Open Addressing*, mengapa operasi penghapusan (*deletion*) elemen tidak dapat dilakukan hanya dengan mengubah nilai slot menjadi `null` atau `empty`? Jelaskan konsep *tombstone* (*dummy marker* / *deleted flag*), dampak akumulasi *tombstone* terhadap kompleksitas probe pencarian elemen yang tidak ditemukan (*miss search*), dan mekanisme *tombstone compaction*.

5. **Primary vs Secondary Clustering pada Open Addressing**  
   Bedakan mekanisme terjadinya *Primary Clustering* pada *Linear Probing* dengan *Secondary Clustering* pada *Quadratic Probing*. Bagaimana teknik *Double Hashing* secara teoritis mengeliminasi kedua bentuk *clustering* tersebut, dan syarat matematis apa yang wajib dipenuhi oleh fungsi hash kedua ($h_2(k)$) terhadap ukuran tabel ($M$) agar seluruh ruang slot dapat dijelajahi (*full permutation*)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Hash-Flooding Attack & Algorithmic Complexity Vulnerability**  
   Sebuah API gateway publik mendadak mengalami lonjakan penggunaan CPU hingga 100% dan *request timeout* massal saat menerima payload JSON besar dari klien eksternal, meskipun volume request secara keseluruhan normal. Analisis bagaimana penyerang (*adversary*) dapat mengeksploitasi fungsi hash deterministik (seperti DJB2 atau SipHash dengan *seed* statis) untuk memicu degradasi dari $O(1)$ menjadi $O(N^2)$ pada parser tabel hash. Bagaimana bahasa modern memitigasi vektor serangan ini pada level runtime?

2. **Robin Hood Hashing: Invarian Probe Sequence Length (PSL)**  
   Jelaskan invarian utama dari algoritma *Robin Hood Hashing* ("*steal from the rich, give to the poor*"). Bagaimana pembandingan *Probe Sequence Length* (PSL) antara elemen yang sedang di-*insert* dengan elemen eksisting dalam slot dapat mereduksi varians pencarian terburuk (*worst-case probe variance*), dan bagaimana modifikasi ini mengubah logika operasi `lookup` untuk menghentikan probe lebih awal (*early termination*)?

3. **Latensi Stop-the-World pada Dynamic Resizing**  
   Tabel hash dengan ukuran gigabyte yang menyimpan 50 juta entri mengalami lonjakan latensi ekstrem (*latency spike* p99 > 2 detik) ketika mencapai *load factor threshold*. Bedah akar masalah arsitektural dari operasi alokasi array baru dan penataan ulang seluruh elemen (*rehashing*). Rancang skema *Incremental Rehashing* (sebagaimana diimplementasikan pada Redis `dict`) untuk mendistribusikan *cost* rehashing tersebut secara deterministik ke operasi I/O berikutnya.

4. **Bahaya Objek Mutable sebagai Hash Key**  
   Diberikan skenario pada bahasa seperti Java, Python, atau C# di mana sebuah instance objek kustom dijadikan *key* pada tabel hash. Setelah dimasukkan ke dalam map, salah satu field anggota objek tersebut diubah nilainya. Apa yang terjadi secara internal saat pemanggilan `map.containsKey(key)` atau `map.get(key)` dilakukan setelah mutasi tersebut? Analisis potensi kegagalan pencarian, korupsi struktur bucket, dan risiko *memory leak* terselubung yang ditimbulkannya.

5. **Treeification Threshold pada Buket Terkolisi (Java 8+ Paradigm)**  
   Java 8 mengonversi *bucket* linked list menjadi *Red-Black Tree* jika panjang rantai tabrakan mencapai 8, dan mengubahnya kembali menjadi linked list (*untreeify*) jika menyusut menjadi 6. Mengapa angka 8 dan 6 dipilih secara spesifik berdasarkan Distribusi Poisson? Mengapa arsitektur engine tidak langsung menggunakan *Red-Black Tree* sejak awal untuk semua slot tanpa menunggu degradasi linked list?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck p99 Latency pada In-Memory Matching Engine
Sebuah sistem *crypto-asset matching engine* berbasis C++ memproses rata-rata 250.000 transaksi per detik dengan SLA p99 < 15 mikrodetik. Data pesanan aktif disimpan dalam sebuah tabel hash berukuran besar. Saat volume transaksi mencapai puncaknya pada volatilitas pasar tinggi, telemetri menunjukkan bahwa p99 melonjak hingga 45 milidetik secara periodik setiap 10-15 menit sekali, menyebabkan *order execution lag* dan kerugian finansial.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda mengonfirmasi bahwa akar penyebab lonjakan latensi adalah *full table reallocation & rehashing* atau pembersihan *tombstone* pada struktur data tabel hash?
  2. Solusi struktur data hash apa yang dapat menjamin latensi deterministik tanpa alokasi memori dinamis di jalur kritis (*hot path*) produksi?

### Skenario B: Race Condition dan Korup Data pada Concurrent Map Lock-Striping
Sebuah tim backend mengimplementasikan tabel hash konkuren kustom menggunakan strategi *Lock Striping* (membagi tabel ke dalam $N$ buah mutex independen) untuk menghindari bottleneck global lock. Di bawah beban *concurrency* tinggi (ratusan worker goroutine/thread), sistem mengalami insiden korupsi data intermiten: nilai kunci terduplikasi pada slot berbeda, dan terkadang proses mengalami *infinite loop* saat melakukan traversal bucket.
* **Pertanyaan Diagnostik:**
  1. Identifikasi celah konkurensi (*race condition*) yang terjadi ketika operasi *read/write* dilakukan bersamaan dengan proses *resizing* tabel yang hanya mengunci sebagian stripe.
  2. Bagaimana arsitektur *fine-grained lock-free* berbasis atomic Compare-And-Swap (CAS) seperti pada `ConcurrentHashMap` Java atau *Split-Ordered Lists* menyelesaikan problem sinkronisasi ini tanpa memblokir seluruh bucket?

### Skenario C: Krisis Memory Overhead pada Skala Ratusan Juta Kunci (Swiss Table vs Chaining)
Sebuah klaster microservice pengumpul telemetri (*Distributed Tracing Collector*) mengalami *Out-Of-Memory* (OOM) terus-menerus. Analisis *heap dump* menunjukkan bahwa 70% memori habis hanya untuk memelihara struktur internal `std::unordered_map` (C++) / `java.util.HashMap` yang menampung 150 juta metrik per node, di mana ukuran payload aktual data (key-value) hanya sebesar 16 byte per entri, namun konsumsi riil memori mencapai 64–80 byte per entri.
* **Pertanyaan Diagnostik:**
  1. Uraikan pemborosan memori struktural (*overhead breakdown*) pada implementasi *Separate Chaining* (pointer overhead, memory alignment/padding, alokasi node allocator fragmentasi).
  2. Jelaskan bagaimana arsitektur *Swiss Table* (Google Abseil / Rust `hashbrown`) yang memanfaatkan *control bytes* (SIMD group matching) dan *flat array storage* mampu memangkas footprint memori secara dramatis sekaligus melipatgandakan throughput pencarian.

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Throughput Fixed-Size Cache with Robin Hood Probing & Tombstone Compaction**

### Problem Statement
Anda ditugaskan merancang modul internal *in-memory deduplication cache* untuk sistem ingestion log berkecepatan tinggi. Komponen ini harus memproses jutaan log hash per detik, menolak duplikasi dalam jendela waktu tertentu, dan tidak boleh memicu alokasi memori dinamis (*zero dynamic allocation*) setelah fase inisialisasi awal guna mencegah *Garbage Collection pause* atau fragmentasi heap.

### Requirements
1. **Implementasi Inti:** Bangun struktur data tabel hash berbasis *Open Addressing* dengan resolusi tabrakan *Robin Hood Hashing* pada bahasa pemrograman pilihan Anda (disarankan: C, C++, Rust, Go, atau Java tingkat lanjut menggunakan flat array / primitive type).
2. **Deterministic Layout:** Struktur data harus dialokasikan secara kontigu pada memori flat array tetap (*fixed capacity*, ukuran kelipatan $2^k$).
3. **Invarian PSL:** Saat terjadi tabrakan, terapkan displacement logic: entri dengan *Probe Sequence Length* (PSL) lebih rendah harus digeser demi entri baru yang memiliki PSL lebih tinggi.
4. **Mekanisme Deletion & Compaction:** Implementasikan operasi penghapusan entri kadaluarsa (*eviction/deletion*) menggunakan penanda *tombstone* atau algoritma *backward-shift deletion* (yang mengeliminasi kebutuhan tombstone sepenuhnya dengan menggeser mundur elemen tetangga yang memiliki $\text{PSL} > 0$).
5. **Metrik Diagnostik:** Sediakan API internal untuk mengekstrak metrik performa secara instan:
   - Max PSL saat ini.
   - Mean PSL (rata-rata probe length).
   - Load Factor saat ini.

### Constraints
* Dilarang menggunakan pustaka tabel hash bawaan (*built-in*) bahasa pemrograman (`std::unordered_map`, `java.util.HashMap`, Go `map`, dll.).
* Waktu eksekusi operasi `Insert`, `Lookup`, dan `Delete` harus beroperasi pada kompleksitas waktu rata-rata $O(1)$ dan varians waktu probe mendekati seragam.
* Batas alokasi memori: Maksimum 1 alokasi buffer kontinu di awal inisialisasi; dilarang melakukan `malloc`/`new` per node saat operasi `insert`.

### Expected Output
1. File source code modul hash table yang modular dan terdokumentasi rapi.
2. Unit tests yang memvalidasi:
   - Penanganan tabrakan hash ekstrem (*forced artificial collisions*).
   - Verifikasi bahwa invarian Robin Hood tetap terjaga setelah serangkaian operasi interleave (insert-delete-insert).
3. Benchmark report yang menunjukkan latensi probe operasi (rata-rata dan p99) pada load factor $50\%$, $75\%$, dan $90\%$.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara fungsi hash kriptografis (SHA-256) vs non-kriptografis performa tinggi (MurmurHash, xxHash, SipHash) dalam hal throughput instruksi per cycle dan resistansi terhadap tabrakan.
- [ ] Mekanisme matematis pemetaan hash index menggunakan *bitwise AND* ($h(k) \ \& \ (M - 1)$) dan syarat mutlak ukuran array bernilai pangkat dua ($M = 2^k$).
- [ ] Dampak hierarki CPU Cache (*Cache Misses* vs *Cache Hits*) terhadap trade-off antara *Separate Chaining* dan *Flat Array Open Addressing*.
- [ ] Konsekuensi operasional akumulasi *Tombstone* terhadap degradasi lookup pada *Linear Probing*.
- [ ] Strategi mitigasi *Rehashing Latency Spikes* melalui teknik *Progressive / Incremental Rehashing*.
- [ ] Prinsip kerja *Robin Hood Displacement* dalam meratakan distribusi probe sequence length.
- [ ] Vektor serangan *Hash Denial of Service* (HashDoS) dan pentingnya penyuntikan *randomized hash seed* per proses aplikasi.

### Saya tidak perlu menghafal:
- [ ] Konstanta numerik internal algoritma MurmurHash atau xxHash (misalnya: magic number pengali bitwise).
- [ ] Kode implementasi assembly SIMD instruksi spesifik (AVX2/NEON) pada pencarian metadata Swiss Table.
- [ ] Bukti matematis formal diferensial dari Distribusi Poisson untuk konversi bucket Red-Black Tree.

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan algoritma hashing berbasis *Open Addressing* lengkap dengan penanganan tabrakan (*Linear Probing*, *Quadratic Probing*, atau *Double Hashing*) dari nol (*from scratch*).
- [ ] Mendiagnosis dan memperbaiki degradasi latensi yang disebabkan oleh *hash collision clustering* pada sistem produksi menggunakan profiler CPU.
- [ ] Mengimplementasikan *Backward Shift Deletion* pada open addressing table untuk menghindari akumulasi *tombstone*.
- [ ] Memilih dan mengonfigurasi struktur data hash yang tepat sesuai batasan skenario: ketersediaan memori rendah, latensi deterministik tinggi, atau skalabilitas multi-threading.