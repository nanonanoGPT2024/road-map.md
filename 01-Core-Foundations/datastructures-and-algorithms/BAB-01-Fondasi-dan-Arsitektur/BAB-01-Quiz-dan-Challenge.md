# BAB 01: Quiz, Challenge, & Knowledge Check
**Bab 01: Analisis Asimptotik, Kompleksitas Komputasi, & Fondasi Memori Sistem**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Batas Asimptotik Formal vs. Praktik Rekayasa Perangkat Lunak**  
   Jelaskan perbedaan matematis murni antara notasi $\mathcal{O}(g(n))$, $\Omega(g(n))$, dan $\Theta(g(n))$. Mengapa dalam evaluasi performa sistem produksi, klaim "algoritma kami memiliki performa $\mathcal{O}(N)$" sering kali tidak memadai untuk menjamin kepatuhan terhadap Service Level Objective (SLO) *p99 latency*, dan mengapa Anda membutuhkan analisis $\Theta$ atau worst-case bound yang ketat?

2. **Auxiliary Space vs. Total Space Complexity**  
   Diferensiasikan secara tegas antara *Auxiliary Space Complexity* dan *Total Space Complexity*. Berikan contoh konkret di mana suatu algoritma memiliki *Total Space* $\mathcal{O}(N)$ tetapi *Auxiliary Space* $\mathcal{O}(1)$, serta jelaskan bagaimana alokasi *stack frame* rekursif (termasuk *activation records*) dihitung dalam evaluasi ini.

3. **Mekanisme Amortized Analysis: Aggregate vs. Potential Method**  
   Pada struktur data larik dinamis (*dynamic array/vector*), operasi penambahan elemen rata-rata bernilai $\mathcal{O}(1)$ secara *amortized*, meskipun operasi *resizing* memakan waktu $\mathcal{O}(N)$. Buktikan dan bandingkan evaluasi kompleksitas ini menggunakan:
   - *Aggregate Method*
   - *Physicist’s (Potential) Method* ($\Phi(D_i) = 2 \cdot size - capacity$)  
   Mengapa *amortized complexity* yang baik tetap bisa menjadi risiko sistemik pada sistem *hard real-time*?

4. **Anomali Skala Kecil: Algoritma Sub-optimal Mengalahkan Asimptotik Unggul**  
   Mengapa algoritma dengan kompleksitas asimptotik $\mathcal{O}(N^2)$ (seperti *Insertion Sort*) secara konsisten mengungguli algoritma $\mathcal{O}(N \log N)$ (seperti *Quick Sort* atau *Merge Sort*) pada ukuran input kecil ($N \le 32$)? Jabarkan fenomena ini dari perspektif koefisien konstanta tersembunyi ($c \cdot g(n)$) dan *instruction cache locality*.

5. **Prinsip Space-Time Trade-off dan Arsitektur Hierarki Memori Modern**  
   Secara teoritis, *Space-Time Trade-off* menyatakan bahwa waktu eksekusi dapat dikurangi dengan mengorbankan konsumsi memori (misalnya dengan teknik memoization atau precomputed lookup tables). Namun, pada arsitektur CPU modern dengan hierarki memori L1/L2/L3 dan RAM, kapan peningkatan konsumsi memori justru secara drastis memperlambat kecepatan eksekusi (*wall-clock time*)? Hubungkan jawaban Anda dengan konsep *memory latency*, *cache line miss*, dan *page faults*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Hardware-Aware Complexity: Data-Oriented vs. Pointer-Chasing Traversal**  
   Dua implementasi traversal koleksi data berukuran $N = 10.000.000$ elemen primitif (64-bit integer) dieksekusi:
   - Kasus A: Flat array kontigu di memori.
   - Kasus B: Doubly Linked List dengan node dialokasikan secara acak di heap via `malloc`/`new`.  
   Keduanya memiliki kompleksitas teoritis waktu $\mathcal{O}(N)$. Mengapa dalam benchmark nyata Kasus A berjalan hingga 20-50x lebih cepat daripada Kasus B? Jelaskan apa yang terjadi pada *CPU Cache Line* (64 bytes), *Hardware Spatial Prefetcher*, dan *Translation Lookaside Buffer* (TLB).

2. **Root Cause Analysis: Integer Overflow pada Algoritma Binary Search**  
   Diberikan implementasi klasik penentuan titik tengah pada algoritma Binary Search:
   ```c
   int mid = (low + high) / 2;
   ```
   Jelaskan skenario matematis di mana baris kode di atas memicu *undefined behavior* atau *infinite loop* pada sistem berbasis arsitektur 32-bit maupun 64-bit. Tuliskan mitigasi tingkat rendahnya menggunakan:
   - Aljabar dasar tanpa potensi overflow.
   - Bitwise arithmetic (dan evaluasi prioritas operator bahasa tingkat rendah).

3. **Call-Stack Explosion & Tail-Call Optimization (TCO)**  
   Diberikan fungsi rekursif pemrosesan struktur data hierarkis. Pada pengujian skala $N = 100.000$, sistem mengalami terminasi abnormal (`SIGSEGV` atau `StackOverflowError`).
   ```text
   Frame size per rekursi: 64 bytes.
   Batas alokasi default thread stack: 1 MB (atau 8 MB di Linux).
   ```
   Hitung secara analitis batas kedalaman rekursi sebelum *stack overflow* terjadi. Bagaimana Anda mengonstruksi ulang algoritma tersebut menggunakan teknik *Tail Recursion*? Mengapa *Tail Call Optimization* (TCO) tidak dapat diandalkan sepenuhnya pada semua compiler/runtime (seperti Java HotSpot VM standar atau compiler C dengan flag optimasi `-O0`)?

4. **Branch Prediction Penalty pada Algoritma Komparasi**  
   Perhatikan eksperimen berikut: Sebuah array berisi $N = 1.000.000$ integer acak di-*filter* dengan kondisi `if (data[i] >= 128)`. Pada array yang telah diurutkan (*sorted array*), operasi filtering selesai dalam 2 ms. Namun, pada array yang tidak diurutkan (*unsorted array*), operasi yang sama persis membutuhkan 8 ms.  
   Jelaskan mengapa algoritma filtering yang identik ($\mathcal{O}(N)$) memiliki disparitas waktu hingga 400%. Bagaimana *CPU Branch Target Predictor* bekerja, apa dampak dari *pipeline flush/stall*, dan bagaimana merestrukturisasi komputasi tersebut menjadi *branchless code*?

5. **Evaluasi Titik Crossover Asimptotik (Break-even Point)**  
   Sistem Anda memiliki dua pilihan algoritma pemrosesan stream:
   - Algoritma Alpha: $T_A(N) = 2000 \cdot N \text{ siklus CPU}$
   - Algoritma Beta: $T_B(N) = 0.5 \cdot N^2 \text{ siklus CPU}$  
   Hitung nilai $N$ persis di mana Algoritma Alpha mulai lebih unggul daripada Algoritma Beta. Jika sistem Anda 95% memproses transaksi dengan batch size $N < 1000$, algoritma mana yang harus diimplementasikan pada *hot-path* produksi? Mengapa memilih algoritma berdasarkan notasi Big-O murni dalam kasus ini adalah kecacatan arsitektural?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike p99 saat Flash Sale pada Service Deduplikasi Order
*Konteks Insiden:*  
Saat kampanye Flash Sale, microservice transaksi menerima 100.000 request per detik. Service ini bertugas mendeteksi *idempotency key* transaksi dalam jendela waktu geser (*sliding window*) 5 menit. Implementasi awal menggunakan struktur data *in-memory* berupa array linear terurut yang di-scan setiap transaksi masuk, dipadukan dengan penghapusan elemen usang (*cleanup*) via loop bersarang yang memicu pergeseran memori (*array copying*).  
Akibatnya, latensi *p99* melonjak dari 5ms menjadi 12.000ms, memicu kegagalan transaksi berantai dan kehabisan alokasi thread pool (*thread pool exhaustion*).

*Tugas Diagnostik & Solusi:*
1. Identifikasi degradasi kompleksitas algoritma awal dalam skenario *worst-case* beban tinggi.
2. Rancang struktur data *in-memory* alternatif yang mampu menjamin operasi penyisipan, pengecekan duplikasi, dan *eviction* elemen usang dalam kompleksitas waktu rata-rata $\mathcal{O}(1)$ atau $\mathcal{O}(\log k)$ (di mana $k$ adalah jumlah elemen dalam jendela 5 menit).
3. Evaluasi *trade-off* penggunaan memori terhadap latensi CPU dari struktur data usulan Anda.

---

### Skenario B: False Sharing & Memory Contention pada Lock-Free Ring Buffer
*Konteks Insiden:*  
Sebuah sistem *high-frequency telemetry ingestor* dibangun menggunakan struktur data *Circular Ring Buffer* multi-thread yang diklaim memiliki kompleksitas waktu $\mathcal{O}(1)$ untuk setiap operasi `enqueue()` dan `dequeue()`. Pengujian unit pada single thread menghasilkan performa fantastis (50 juta ops/sec). Namun, ketika di-deploy ke server komputasi dengan 64 core CPU (dual-socket AMD EPYC), throughput anjlok drastis ke level 2 juta ops/sec, dengan utilisasi CPU mencapai 100% pada kernel space. Profiling dengan tool *perf* menunjukkan metrik CPU stall yang sangat tinggi akibat L3 Cache Invalidation.

*Tugas Diagnostik & Solusi:*
1. Mengapa struktur data $\mathcal{O}(1)$ mengalami degradasi performa ekstrem ketika dieksekusi secara konkuren pada sistem multi-core berskala besar?
2. Jelaskan mekanisme *False Sharing* yang terjadi antara pointer `head` dan `tail` dari Ring Buffer tersebut dalam kaitannya dengan ukuran *CPU Cache Line* (umumnya 64 bytes).
3. Berikan solusi struktural (pada tingkat representasi memori / alignment data) untuk mengeliminasi contention tersebut tanpa menambahkan locking mechanism (*mutex*).

---

### Skenario C: Dilema Arsitektur Database In-Memory: Vector-Scan vs Spatial Indexing
*Konteks Desain Sistem:*  
Anda adalah Lead Architect yang merancang sistem *ride-hailing* real-time. Sistem harus memproses lokasi 500.000 armada kendaraan aktif secara terus-menerus. Setiap 2 detik, setiap kendaraan mengirimkan koordinat latitude/longitude baru. Pada saat yang sama, ada 20.000 query pencarian "Cari 10 kendaraan terdekat dalam radius 2 km dari pengguna" per detik.
- Tim Junior mengusulkan: Simpan data di flat array terdistribusi, lakukan *flat vector scan* terparalelisasi penuh ($\mathcal{O}(N)$ scanning memanfaatkan SIMD instruction set).
- Tim Senior mengusulkan: Bangun struktur data hierarkis dinamis seperti *QuadTree* atau *R-Tree* di memori ($\mathcal{O}(\log N)$ per query).

*Tugas Diagnostik & Solusi:*
1. Analisis titik kegagalan (*bottleneck*) dari pendekatan QuadTree/R-Tree ketika dihadapkan pada frekuensi pembaruan koordinat 250.000 write ops/sec (evaluasi *tree rebalancing cost*, alokasi node pointer, dan lock contention).
2. Analisis batas komputasi dan memori bus (*memory bandwidth saturation*) dari pendekatan SIMD flat vector scan pada frekuensi read 20.000 query/sec terhadap 500.000 item.
3. Rekomendasikan pendekatan hibrida (*hybrid approach*) yang menyeimbangkan kompleksitas asimptotik algoritma dan efisiensi mekanika hardware (misalnya: *Geohash Spatial Bucketing / Grid Cell Partitioning*). Berikan argumen analisis kompleksitas waktu dan ruangnya.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Memory-Efficient Ring Buffer & Telemetry Allocator

#### Deskripsi Kasus
Rancang dan implementasikan struktur data **Bounded Lock-Free Ring Buffer** (Circular Queue) berbasis contiguous array dalam bahasa pemrograman tingkat sistem (disarankan: C, C++, Rust, atau Go/Java dengan manipulasi memori primitif yang ketat) untuk memproses data *telemetry event* secara real-time.

#### Requirements
1. **Zero-Allocation on Hot-Path:**  
   Setelah inisialisasi awal, struktur data dilarang keras melakukan alokasi heap (`malloc`, `new`, `alloc`) selama proses operasi pengiriman (`produce`) dan pembacaan (`consume`).
2. **Deterministic Time Complexity:**  
   Operasi penyisipan (`push`) dan pengambilan (`pop`) wajib beroperasi dalam batas atas asimptotik waktu worst-case $\mathcal{O}(1)$.
3. **Hardware-Cache Alignment:**  
   Variabel penunjuk state internal (misalnya `head` dan `tail`) harus diisolasi ke dalam cache line terpisah menggunakan teknik *cache padding* (64-byte alignment) untuk mencegah fenomena *False Sharing*.
4. **Power-of-Two Sizing:**  
   Kapasitas antrean harus dibatasi selalu berupa bilangan pangkat dua ($N = 2^k$) sehingga operasi modulasi indeks indeks-lingkar ($index \pmod N$) diubah sepenuhnya menjadi operasi bitwise AND ($index \ \& \ (N - 1)$) pada tingkat compiler.

#### Constraints
- Kapasitas antrean: Ditentukan pada saat runtime saat inisialisasi ($2^{16} = 65.536$ slot event).
- Ukuran tiap payload event: Struct/class tetap sebesar 128 bytes.
- Algoritma tidak boleh menggunakan global mutex/lock; gunakan atomic operation (minimal CAS / Load-Acquire & Store-Release semantics) untuk sinkronisasi state.
- Auxiliary Space Complexity: $\mathcal{O}(1)$ di luar array kontigu utama.

#### Expected Output
1. **Source Code Terstruktur:** Kode sumber implementasi Ring Buffer yang bersih, bebas bug memory leak, dan tervalidasi concurrency model-nya.
2. **Memory Layout Diagram:** Representasi visual/skematik struktur memori bagaimana buffer dan pointer dialokasikan, lengkap dengan skema padding-nya.
3. **Analisis Kompleksitas Tertulis:**  
   - Kompleksitas Waktu: *Best Case*, *Average Case*, *Worst Case* untuk setiap operasi.
   - Kompleksitas Ruang: Analisis detail ukuran memori total yang dialokasikan terhadap kapasitas $N$.
4. **Benchmark Proof:** Output log performa yang mendemonstrasikan throughput minimal $\ge 10.000.000$ operasi/detik tanpa degradasi latensi p99 akibat GC pause atau lock contention.

---

## 5. Knowledge Check & Checklist

Pastikan Anda memenuhi standar penguasaan modul fondasi ini sebelum melangkah ke bab struktur data lanjutan. Gunakan matriks evaluasi mandiri berikut:

### Saya harus memahami:
- [ ] Definisi formal dan relasi matematis asimptotik antara Big-$\mathcal{O}$, Big-$\Omega$, dan Big-$\Theta$.
- [ ] Batasan dari model komputasi teoritis (Turing/RAM Machine) ketika dieksekusi di atas arsitektur prosesor Von Neumann modern (hierarki register, L1/L2/L3 cache, RAM).
- [ ] Cara kerja CPU Cache Line (64-byte chunks), Spatial vs. Temporal Locality, dan konsekuensi cache miss terhadap instruction throughput.
- [ ] Dampak alokasi stack frame terhadap *Total Space Complexity* pada algoritma rekursif.
- [ ] Teori Amortized Analysis (metode Aggregate, Accounting/Banker's, dan Potential).
- [ ] Dampak False Sharing pada program multi-threaded dan pengaruh hardware memory barriers terhadap performa eksekusi.

### Saya tidak perlu menghafal:
- [ ] Rumus Master Theorem untuk kasus-kasus matematis langka di luar kasus standar divide-and-conquer ($T(n) = aT(n/b) + f(n)$).
- [ ] Nilai eksak latensi siklus CPU per instruksi assembly spesifik vendor (misalnya: latensi instruction cycle AMD Zen vs Intel Golden Cove). Cukup pahami rasio order of magnitude antar-tingkatan (Register < L1 < L2 < L3 < DRAM < NVMe/SSD < Jaringan).
- [ ] Sintaks mikro-arsitektur intrinsik spesifik assembly secara literal tanpa bantuan referensi dokumentasi arsitektur resmi.

### Saya harus bisa melakukan:
- [ ] Menghitung kompleksitas waktu dan ruang (*best, average, worst-case*) dari potongan kode non-trivial, termasuk loop bersarang non-linear dan relasi rekurensi.
- [ ] Mengidentifikasi masalah performa akibat *pointer chasing* dan merekayasa ulang algoritma menggunakan pola *Data-Oriented Design* (Contiguous Array Layout).
- [ ] Mencegah dan memitigasi bug *integer overflow* pada penanganan indeks array dan kalkulasi pointer.
- [ ] Menggunakan profiling tool (misalnya `perf`, `gprof`, visualVM, atau Go pprof) untuk memvalidasi apakah bottleneck performa berasal dari kompleksitas asimptotik algoritma atau hardware cache misses.
- [ ] Mengubah algoritma rekursif non-tail menjadi bentuk iteratif terkelola dengan *explicit stack* guna mengeliminasi risiko *stack overflow*.