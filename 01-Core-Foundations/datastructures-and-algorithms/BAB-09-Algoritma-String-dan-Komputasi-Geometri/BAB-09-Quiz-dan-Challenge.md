# BAB 09: Quiz, Challenge, & Knowledge Check
**Bab 09: Algoritma Pengurutan & Pencarian Lanjutan (Advanced Sorting, Quickselect, & External Sort)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Information-Theoretic Lower Bound pada Algoritma Sorting**
   Buktikan secara matematis mengapa seluruh algoritma sorting berbasis perbandingan (*comparison-based sorting*) memiliki batas bawah kompleksitas waktu terburuk $\Omega(N \log N)$. Jelaskan bagaimana struktur *decision tree* memodelkan permutasi elemen, dan mengapa algoritma non-komparatif seperti *Counting Sort* atau *Radix Sort* dapat mencapai kompleksitas linear $O(N)$ tanpa melanggar teorema batas bawah tersebut.

2. **Dinamika dan Formalitas Stability pada Sorting**
   Definisikan sifat *stability* dalam pengurutan data secara formal matematis. Analisis mekanisme internal mengapa *Quicksort* standar bersifat *unstable*, sedangkan *Merge Sort* standar bersifat *stable*. Berikan contoh arsitektur nyata di mana penggunaan algoritma pengurutan *unstable* akan merusak integritas *state* downstream consumer.

3. **Mekanika Partisi: Lomuto vs. Hoare Partitioning Scheme**
   Bandingkan skema partisi Lomuto dan Hoare pada *Quicksort*. Analisis keduanya berdasarkan:
   - Jumlah perbandingan (*comparisons*) dan pertukaran (*swaps*).
   - Perilaku algoritma saat menangani array dengan semua elemen bernilai identik.
   - Dampak pola pemilihan pivot terhadap kedalaman tumpukan rekursi (*recursion stack depth*).

4. **Merge Sort: Cache Locality vs. Memory Overhead**
   Meskipun *Merge Sort* menjamin performa waktu terburuk $O(N \log N)$, mengapa implementasi standar *Merge Sort* pada array kontigu kerap kali kalah performa riil dibandingkan *In-place Quicksort* pada sistem komputer modern? Tinjau fenomena ini dari sudut pandang *CPU cache hierarchy* (L1/L2/L3), *cache lines*, dan *auxiliary memory allocation* $O(N)$.

5. **Invarian Loop dan Aritmetika Presisi pada Binary Search**
   Jelaskan secara formal konsep *loop invariant* yang menjamin konvergensi algoritma *Binary Search*. Mengapa penulisan indeks tengah menggunakan `mid = (low + high) / 2` rentan menghasilkan *bug* fatal pada bahasa pemrograman berbasis *fixed-width integer* (seperti C/C++ dan Java), dan bagaimana ekspresi `mid = low + ((high - low) >> 1)` memitigasi risiko tersebut sekaligus mengoptimalkan instruksi CPU?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Analisis Kerusakan Invarian Stack pada Timsort (JDK-8072920)**
   Algoritma *Timsort* menggunakan stack untuk melacak ukuran run yang tertunda (*pending runs*) dengan menjaga dua invarian:
   1. $W > X + Y$
   2. $X > Y$
   Jelaskan bagaimana kegagalan pembuktian invarian ini pada implementasi awal Java Standard Library dapat menyebabkan `ArrayIndexOutOfBoundsException` pada array berukuran sangat besar. Bagaimana perbaikan formal (*corrected invariant*) diterapkan untuk memulihkan batas logaritmik stack?

2. **Branch Misprediction Penalty pada Binary Search vs. Branchless Binary Search**
   Pada CPU modern berskala superscalar dengan *pipeline* instruksi yang dalam, instruksi percabangan bersyarat (`if (arr[mid] < target)`) pada Binary Search konvensional menghasilkan *branch misprediction rate* mendekati 50% ketika ruang pencarian acak. Jelaskan bagaimana Anda merekayasa *Branchless Binary Search* (misalnya menggunakan instruksi *conditional move* `cmov` atau operasi bitwise), dan jelaskan pada kondisi ukuran array berapakah optimasi ini berhenti memberikan peningkatan performa akibat batas latensi DRAM (*cache miss*).

3. **Mitigasi Worst-Case Quickselect: Anatomi Introselect**
   *Quickselect* memiliki performa rata-rata $O(N)$, namun dapat terdegradasi menjadi $O(N^2)$ pada skenario data terburuk (*adversarial input*). Jelaskan mekanisme arsitektur algoritma *Introselect* (sebagaimana diimplementasikan pada `std::nth_element` di C++ STL) yang mengombinasikan Quickselect, *Median-of-Medians*, dan *Heapsort* untuk memastikan batas atas deterministik $O(N)$ pada kasus terburuk tanpa mengorbankan performa rata-rata.

4. **Timsort Galloping Mode: Algoritma dan Trade-Off Threshold**
   Jelaskan secara rinci bagaimana mekanisme *Galloping Mode* bekerja pada fase *merging* di *Timsort*. Kapan algoritma memutuskan untuk beralih dari penggabungan linear biasa ke mode *galloping*, bagaimana interval pencarian diekspansi secara eksponensial ($2^0, 2^1, 2^2, \dots$), dan apa penalti performa yang harus dibayar jika data input ternyata berselang-seling acak (*ping-pong behavior*)?

5. **External Merge Sort: Buffer Sizing, Fan-In, dan Run Generation**
   Dalam merancang sistem *External Merge Sort* untuk data yang jauh melampaui kapasitas RAM ($N \gg M$):
   - Bagaimana formula optimal untuk menentukan ukuran *I/O block buffer* guna meminimalkan latensi *disk seek*?
   - Jelaskan bagaimana teknik *Replacement Selection* menggunakan Min-Heap memungkinkan panjang rata-rata setiap *run* terurut mencapai $2M$ alih-alih hanya $M$.
   - Jelaskan konsep *Double Buffering* berbasis *asynchronous I/O* untuk melakukan *overlapping* antara komputasi CPU dan transfer data disk.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck I/O dan Degradasi Performa Multi-Terabyte Log Sorting
Sebuah platform observabilitas terdistribusi harus mengurutkan berkas log *crash dump* berukuran 4 Terabyte berdasarkan timestamp presisi nanodetik pada satu mesin analitik *bare-metal* dengan spesifikasi: RAM 16 GB, CPU 32 Cores, dan NVMe SSD 8 TB. Implementasi awal *External Sort* menggunakan pustaka bawaan mengalami degradasi performa ekstrem: *throughput* baca/tulis anjlok di bawah 50 MB/s, utilisasi CPU < 5%, dan metrik *I/O Wait* (iowait) melonjak hingga 92%.
- **Pertanyaan Diagnostik:**
  1. Identifikasi faktor penyebab utama degradasi performa sistem di atas dengan mempertimbangkan *I/O fan-in*, pola alokasi buffer blok NVMe, dan konkurensi CPU.
  2. Rancang arsitektur pipeline *External Merge Sort* yang memisahkan thread pool komputasi internal sort dengan *asynchronous multi-queue direct I/O* (menggunakan `io_uring` pada Linux). Bagaimana rasio pemotongan *initial run* dan *merge factor* ($K$-way) harus dikonfigurasi agar *throughput* NVMe termanfaatkan secara saturatif (~3 GB/s)?

### Skenario B: "Flapping" dan Duplikasi Data pada API Pagination E-Commerce
Layanan katalog produk pada platform e-commerce skala besar menyediakan API dengan pagination berbasis offset/limit: `/api/v1/products?sort=created_at:desc&limit=20&offset=40`. Pengguna melaporkan anomali kritis: saat berpindah dari halaman 2 ke halaman 3, terdapat beberapa produk yang muncul kembali (duplikat), sementara produk lain tidak pernah tampil sama sekali. Sistem backend menggunakan *microservices* Go yang mengambil data dari replika database terdistribusi, lalu memproses penyaringan sekunder dan pengurutan ulang di *memory tier* menggunakan algoritma `sort.Slice` bawaan.
- **Pertanyaan Diagnostik:**
  1. Buktikan secara teknis bagaimana penggunaan algoritma pengurutan *unstable* (seperti Quicksort atau Pattern-Defeating Quicksort) atau data dengan atribut pengurutan non-unik (`created_at` yang memiliki nilai identik pada milidetik yang sama) dapat memicu fenomena fluktuasi indeks (*flapping*) antar-halaman.
  2. Berikan solusi struktural komprehensif pada level skema query dan algoritma *in-memory* untuk memastikan determinisme pagination tanpa mengorbankan kompleksitas waktu $O(N \log N)$ dan jejak memori.

### Skenario C: Pelacakan P99.9 Latency Sistem Pembayaran Real-Time
Engine gateway pembayaran memproses 500.000 transaksi per detik. Komite arsitektur mewajibkan perhitungan metrik latensi P50, P99, dan P99.9 secara *rolling window* (tiap interval 10 detik). Pendekatan naive dengan mengumpulkan 5.000.000 data latensi ke dalam array lalu menjalankan `Arrays.sort()` setiap 10 detik memicu *stop-the-world GC pause* parah dan lonjakan latensi eksekusi (*latency spike*) yang melanggar SLA.
- **Pertanyaan Diagnostik:**
  1. Mengapa pengurutan penuh (*full sort*) merupakan antipola arsitektur untuk kalkulasi rank/persentil tertentu?
  2. Bandingkan trade-off arsitektural antara penggunaan algoritma **Introselect / Quickselect in-place** pada buffer sirkular statis versus struktur data perkiraan sketsa probabilistik (**T-Digest** atau **HdrHistogram**). Manakah yang harus dipilih jika batas toleransi *relative error* adalah $< 0.1\%$ dan *memory footprint* harus di bawah 500 KB?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance In-Memory & External Sort Engine dengan Memory-Budget Ketat

#### Problem Statement
Anda diminta untuk membangun sebuah utilitas mesin pengurutan biner (*High-Performance Binary Sort Engine*) yang mampu mengurutkan berkas biner besar berisi pasangan data fixed-size:
`Record = { uint64_t key; uint8_t payload[56]; }` (Ukuran tepat: 64 byte per record).
Mesin harus mampu memproses berkas input berukuran hingga **2 GiB** (~33.554.432 record) pada lingkungan yang dibatasi oleh limit memori fisik RAM ketat sebesar **64 MiB**.

#### Requirements & System Constraints
1. **Memory Budget Limit:** Total alokasi memori heap runtime (termasuk buffer baca/tulis, internal heap nodes, dan stack) **tidak boleh melebihi 64 MiB** kapan pun selama siklus hidup program. Melebihi batas ini (diukur melalui OS cgroups atau custom memory allocator) dianggap *fail*.
2. **Phase 1 - Run Generation (Replacement Selection):**
   - Implementasikan *Replacement Selection* menggunakan struktur data *Min-Heap* internal yang dialokasikan di dalam batas memori 64 MiB untuk menghasilkan *runs* awal yang sudah terurut.
   - Panjang rata-rata setiap *run* terurut harus mendekati $2 \times \text{kapasitas elemen RAM}$ untuk data input acak.
3. **Phase 2 - Multi-Way Merge:**
   - Implementasikan $K$-way Merge menggunakan struktur data *Tournament Tree* (*Winner Tree* atau *Loser Tree*) untuk meminimalkan jumlah komparasi per elemen saat penggabungan.
   - Tentukan nilai $K$ yang optimal berdasarkan batas memori yang tersisa untuk buffer pembacaan berkas sementara (*temporary run files*) dan buffer penulisan (*output buffer*).
4. **Zero-Copy & I/O Alignment:**
   - Baca dan tulis data menggunakan I/O berbasis blok terbuffer (misal: 64 KiB per blok I/O) yang selaras dengan batas memori halaman sistem (*page boundary aligned*).
5. **Determinisme dan Verifikasi:**
   - Hasil akhir pada berkas keluaran harus terurut secara monotonik naik: $\text{Record}[i].\text{key} \le \text{Record}[i+1].\text{key}$.

#### Expected Output
1. Program CLI fungsional (ditulis dalam C, C++, Rust, atau Go dengan custom memory profile) yang menerima flag:
   `./extsort --input raw.bin --output sorted.bin --mem-limit 64MB`
2. Metrik telemetri yang dicetak ke `stdout`:
   - Ukuran input & total record.
   - Jumlah *initial runs* yang dihasilkan.
   - Panjang rata-rata *run* (dalam MiB).
   - Jumlah fase *merge pass*.
   - Total waktu eksekusi (dibagi menjadi *Phase 1 Time* dan *Phase 2 Time*).
   - Peak memory usage (harus diverifikasi $\le 64$ MiB).
3. Kode verifikator (*integrity checker*) yang memindai berkas keluaran secara sekuensial sekali jalan (*single-pass stream*) untuk memverifikasi keurutan data dan kesamaan checksum terhadap data asal.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Bukti matematis Decision Tree Model untuk batas bawah komparasi pengurutan $\Omega(N \log N)$.
- [ ] Kondisi matematis dan struktural yang membedakan skema partisi Lomuto, Hoare, dan Dutch National Flag (3-way partitioning).
- [ ] Algoritma Timsort secara komprehensif: deteksi natural run, minrun calculation, stack invariant, dan galloping mode.
- [ ] Arsitektur External Sort: kalkulasi Fan-In/Fan-Out, Replacement Selection, dan optimalisasi blok transfer disk I/O.
- [ ] Kompleksitas asimtotik kasus terbaik, rata-rata, dan terburuk untuk Quicksort, Mergesort, Heapsort, Radix Sort, dan Quickselect.
- [ ] Teorema Invarian Loop pada Binary Search serta mekanika pergeseran pointer pada boundary condition (`low <= high` vs `low < high`).
- [ ] Penalti arsitektur perangkat keras: cache misses, TLB thrashing, dan CPU branch mispredictions pada algoritma pengurutan dan pencarian.

### Saya tidak perlu menghafal:
- [ ] Bukti matematis formal konvergensi konstanta deviasi T-Digest secara kalkulus lanjut.
- [ ] Angka persis konstanta `MIN_MERGE` (32 atau 64) atau implementasi bit-level assembly Timsort di kode sumber OpenJDK.
- [ ] Seluruh tabel perbandingan micro-benchmark arsitektur CPU spesifik terhadap varian partisi Quicksort.

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan *Branchless Binary Search* menggunakan operasi aritmetika/bitwise tanpa percabangan bersyarat (`if-else`).
- [ ] Menulis algoritma *Quickselect* yang tahan terhadap degenerasi kasus terburuk (*Introspective selection* fallback).
- [ ] Merancang dan mengeksekusi strategi pagination deterministik berbasis *keyset pagination* (seek method) pada database/dataset bernilai duplikat tinggi.
- [ ] Menghitung kebutuhan kapasitas RAM, jumlah file descriptor, dan ukuran buffer I/O untuk memproses dataset multi-terabyte menggunakan External Merge Sort.
- [ ] Mendeteksi dan memperbaiki bug *off-by-one* serta *integer overflow* pada kode pencarian rentang (lower-bound dan upper-bound searching).