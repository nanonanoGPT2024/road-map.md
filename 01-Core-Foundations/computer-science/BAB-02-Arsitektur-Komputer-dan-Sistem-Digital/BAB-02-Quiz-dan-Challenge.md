# BAB 02: Quiz, Challenge, & Knowledge Check
**Bab 02: Arsitektur Komputer Modern, Pipeline CPU, Hierarki Memori, & Representasi Data Rendah**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Von Neumann Bottleneck & Splitting Cache L1**:
   Jelaskan secara arsitektural mengapa ketergantungan pada *shared bus* tunggal antara CPU dan memori dalam arsitektur von Neumann murni menciptakan *throughput bottleneck*. Bagaimana mikroarsitektur CPU modern memitigasi hal ini pada level L1 cache menggunakan modifikasi prinsip Arsitektur Harvard (*split instruction cache* / L1i dan *data cache* / L1d)?

2. **Representasi Bilangan Negatif & Batas Presisi Floating-Point**:
   Mengapa sistem komputasi modern universal mengadopsi representasi *Two's Complement* untuk bilangan bertanda (*signed integer*) dibandingkan *Sign-and-Magnitude* atau *Ones' Complement* dalam perancangan sirkuit ALU? Hubungkan penjelasan ini dengan fenomena hilangnya sifat asosiatif pada operasi aritmatika pecahan IEEE 754 (`(a + b) + c != a + (b + c)`).

3. **Anatomi Pipeline CPU & Pipeline Hazards**:
   Pada model pipeline 5-tahap RISC klasik (*Instruction Fetch, Instruction Decode, Execute, Memory Access, Write-back*), jelaskan perbedaan mendasar antara *Structural Hazard*, *Data Hazard (Read-After-Write)*, dan *Control Hazard*. Bagaimana CPU menyelesaikannya tanpa membatalkan (*flushing*) seluruh tahapan eksekusi secara naif?

4. **Prinsip *Locality of Reference* & Latensi Hierarki Memori**:
   Uraikan disparitas performa (dalam orde magnitudo siklus CPU) antara akses register, Cache L1, L2, L3, dan *Main Memory* (DRAM). Bedakan secara teknis antara *Temporal Locality* dan *Spatial Locality*, serta jelaskan bagaimana unit *Hardware Prefetcher* memanfaatkan *spatial locality* untuk meminimalkan *cache miss stall*.

5. **Endianness & Integritas Serialisasi Tingkat Rendah**:
   Jelaskan representasi biner dari integer 32-bit `0x12345678` saat disimpan di memori fisik oleh arsitektur *Little-Endian* (seperti x86_64) dibandingkan dengan *Big-Endian* (arsitektur jaringan TCP/IP standar). Apa konsekuensi komputasional dan bug konkurensi laten jika *type-punning* pointer (`uint32_t*` di-*cast* ke `uint8_t*`) dieksekusi lintas platform tanpa normalisasi *byte-swapping*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Cache Coherency & Dampak Protokol MESI Terhadap Interconnect Bus**:
   Jelaskan siklus hidup *cache line* (64 byte) melalui empat status protokol MESI (*Modified, Exclusive, Shared, Invalid*). Apa yang terjadi pada level perangkat keras (*bus snooping* / *broadcast invalidation traffic*) ketika dua core CPU berbeda secara berulang mengeksekusi operasi penulisan (*write*) pada dua variabel independen yang kebetulan berada dalam satu *cache line* yang sama (*False Sharing*)?

2. **Branch Prediction, Speculative Execution, & Biaya Pipeline Flush**:
   Bagaimana mekanisme *Two-Level Adaptive Branch Predictor* menggunakan *Branch History Table* (BHT) dan *Branch Target Buffer* (BTB)? Analisis apa yang terjadi di dalam pipeline *out-of-order* CPU ketika terjadi *branch misprediction* pada loop berfrekuensi tinggi, dan mengapa *speculative execution* dapat dieksploitasi untuk membocorkan bit memori melalui saluran samping (*cache side-channel attacks* seperti Spectre)?

3. **Memory Alignment, Struct Padding, & Hardware Penalty**:
   Mengapa arsitektur prosesor 64-bit memaksakan batasan *memory alignment* (misalnya alamat memori tipe data 64-bit harus merupakan kelipatan 8)? Jika sebuah `struct` diorganisir sebagai:
   ```c
   struct Data {
       uint8_t  a;
       uint64_t b;
       uint32_t c;
   };
   ```
   Berapa ukuran total memori yang dialokasikan oleh kompiler (asumsi x86_64 ABI standar), bagaimana urutan *padding byte* disisipkan, dan bagaimana Anda mereorganisasi deklarasi field tersebut untuk meminimalkan *footprint* memori tanpa memicu *unaligned access exception* atau penalti multi-cycle bus cycle?

4. **Memory Barriers (Fences) & CPU Memory Ordering Model**:
   Prosesor modern (seperti x86 TSO vs ARM weakly-ordered) mengimplementasikan *Out-of-Order Execution* dan *Store Buffers*, yang memungkinkan *Store-Load reordering*. Jelaskan bagaimana kode berikut dapat menghasilkan kondisi di mana kedua thread membaca nilai `0` pada register lokal secara bersamaan, dan bagaimana instruksi *memory barrier* (`mfence`, `dmb`, atau semantik *Acquire-Release*) mencegah reordering instruksi di level CPU:
   ```
   // Inisialisasi: x = 0, y = 0
   Thread 1:           Thread 2:
   x = 1;              y = 1;
   r1 = y;             r2 = x;
   ```

5. **TLB (Translation Lookaside Buffer), Page Walk, & Biaya Page Fault**:
   Jelaskan proses resolusi alamat virtual menjadi alamat fisik oleh *Memory Management Unit* (MMU). Apa perbedaan mendasar antara *TLB Hit*, *TLB Miss* (yang memicu perangkat keras melakukan *multilevel page table walk* traversal 4-level/5-level), *Minor Page Fault*, dan *Major Page Fault* (I/O disk stall)? Kapan penggunaan *Huge Pages* (2MB/1GB) secara arsitektural menguntungkan sistem alokasi memori berukuran gigabyte?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Degradasi Throughput Skala Besar Akibat Interconnect Bus Saturation
Sebuah engine *In-Memory Key-Value Store* berbasis C++ dengan performa tinggi dideploy pada server Dual-Socket AMD EPYC (total 128 physical cores, 2 NUMA nodes). Engine ini menggunakan model *lock-free ring buffer* global untuk membagikan antrean tugas ke seluruh *worker threads*. 
Selama pengujian skala kecil (1 socket, 8 thread), engine mencapai 15 juta RPS. Namun, saat diskalakan ke 128 thread lintas NUMA node, throughput anjlok drastis ke 1.8 juta RPS, dan pemantauan perangkat keras via `perf` menunjukkan metrik:
*   `cycles per instruction (CPI)` melonjak dari 0.45 menjadi 3.2.
*   `L1/L2 cache misses` tidak berubah signifikan.
*   `NUMA remote access` dan transaksi UPI/Infinity Fabric link saturation mencapai 98% kapasitas maksimal.
*   Tingkat stall siklus instruksi didominasi oleh peristiwa `RESOURCE_STALLS.SB` (Store Buffer full).

**Pertanyaan Diagnostik:**
1. Apa akar penyebab degradasi performa mikroarsitektur ini ditinjau dari protokol koherensi cache dan arsitektur bus NUMA?
2. Bagaimana Anda membuktikan bahwa *lock-free ring buffer* global tersebut mengalami *cache-line bouncing* intensif?
3. Langkah perombakan struktur data dan afinitas memori/thread (NUMA-aware design) apa yang wajib diimplementasikan untuk mengeliminasi bottleneck tersebut?

---

### Skenario B: Race Condition & Memory Corruption Silang Platform (x86_64 vs ARM64)
Sebuah sistem *high-frequency trading order matching engine* ditulis menggunakan C++11 dengan implementasi algoritma antrean *Single-Producer Single-Consumer* (SPSC) tanpa kunci (*lockless*). Kode diuji secara ekstensif pada server pengembangan berarsitektur Intel Xeon (x86_64) selama berbulan-bulan tanpa ada kesalahan konsistensi data.
Namun, ketika modul yang sama di-compile dan di-deploy ke server komputasi berbasis ARM64 (AWS Graviton3) untuk efisiensi biaya, sistem mulai mengalami kerusakan payload pesan (*corrupted state/partial write reads*) secara intermiten pada throughput di atas 500.000 transaksi per detik:
```cpp
// SPSC Shared Queue State
struct Queue {
    Data buffer[CAPACITY];
    std::atomic<size_t> tail{0};
    std::atomic<size_t> head{0};
};

void push(const Data& item) {
    auto current_tail = tail.load(std::memory_order_relaxed);
    buffer[current_tail] = item; // Penulisan payload
    tail.store(current_tail + 1, std::memory_order_relaxed); // Publikasi index
}

Data pop() {
    auto current_head = head.load(std::memory_order_relaxed);
    // Menunggu hingga tail > current_head...
    Data item = buffer[current_head]; // Pembacaan payload
    head.store(current_head + 1, std::memory_order_relaxed);
    return item;
}
```

**Pertanyaan Diagnostik:**
1. Mengapa cacat logika ini tidak pernah terjadi saat engine berjalan di arsitektur x86_64, namun langsung merusak data ketika dieksekusi di arsitektur ARM64? Jelaskan dari sisi *Hardware Memory Model* masing-masing arsitektur.
2. Analisis bagaimana instruksi *store* dan *load* pada `buffer` dan `tail/head` dapat diurutkan ulang (*reordered*) oleh CPU ARM64.
3. Ubah deklarasi `memory_order` pada operasi `.load()` dan `.store()` di atas ke tingkat semantik atomik paling optimal (kinerja maksimum tanpa kompromi integritas data) untuk memperbaiki bug tersebut secara definitif.

---

### Skenario C: Bottleneck Memory Bandwidth pada Pemrosesan Array Besar (AoS vs SoA)
Sebuah sistem analitik geospatial memproses 100 juta titik koordinat per detik dalam kalkulasi simulasi cuaca. Implementasi eksisting menggunakan paradigma *Object-Oriented* murni dengan format *Array-of-Structures* (AoS):
```cpp
struct GeoPoint {
    double latitude;      // 8 bytes
    double longitude;     // 8 bytes
    double altitude;      // 8 bytes
    float  temperature;   // 4 bytes
    float  pressure;      // 4 bytes
    char   sensor_id[16]; // 16 bytes
    // Total: 48 bytes per point
};
GeoPoint points[100'000'000];
```
Tugas rutin kalkulasi adalah menghitung rata-rata `temperature` dan `pressure` yang memenuhi kriteria `altitude > 10000.0`. Profiling CPU menunjukkan pemanfaatan kapasitas execution port ALU SIMD sangat rendah, sementara *Memory Bus Bandwidth Utilisation* konstan berada di batas 100%, menghasilkan CPU stall yang masif.

**Pertanyaan Diagnostik:**
1. Hitung berapa persentase byte dari setiap *cache line* (64 bytes) yang terbuang percuma saat prosesor menarik data dari memori untuk kalkulasi spesifik tersebut dalam format AoS.
2. Jelaskan bagaimana transisi ke format *Structure-of-Arrays* (SoA) atau *Array-of-Structures-of-Arrays* (AoSoA) merestrukturisasi layout memori untuk memaksimalkan *Spatial Locality* dan utilisasi bandwidth bus.
3. Bagaimana restrukturisasi layout memori tersebut membuka kemampuan *SIMD Vectorization* (seperti AVX-512 atau ARM NEON) pada loop kalkulasi, dan apa trade-off arsitekturalnya jika aplikasi juga harus sering mengeksekusi operasi mutasi individual per koordinat secara acak (*random point update*)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Hardware-Conscious Memory Traversal & False Sharing Profiler
Bangun program benchmarking tingkat rendah berbasis sistem (menggunakan C, C++, atau Rust) yang secara mandiri memverifikasi, mendemonstrasikan, dan mengukur efek arsitektur CPU nyata terhadap latensi eksekusi.

#### Problem:
Banyak software engineer menulis kode yang secara matematis optimal dalam kompleksitas algoritma Big-O ($O(N)$), namun secara drastis lambat saat berjalan di hardware modern karena melanggar batasan arsitektur mikroprosesor: *cache miss*, *false sharing*, dan *stride access penalty*. Anda ditantang untuk membuktikan fenomena mikroarsitektur ini melalui kode benchmarking empiris.

#### Requirements:
1. **Modul 1: Matrix Locality Benchmark (Spatial Locality vs Cache Stride)**
   * Alokasikan matriks dua dimensi berukuran besar (minimal $16384 \times 16384$ elemen `uint32_t` dalam heap linear).
   * Implementasikan fungsi traversal penjumlahan nilai elemen:
     * *Algoritma A*: Traversal *Row-Major* (akses elemen berurutan `matrix[i][j]`).
     * *Algoritma B*: Traversal *Column-Major* (akses elemen melompat `matrix[j][i]`).
   * Ukur dan tampilkan waktu eksekusi presisi tinggi (nanodetik) dan kalkulasikan *bandwidth throughput* (GB/s).
2. **Modul 2: False Sharing Elimination Harness**
   * Buat alokasi array yang diakses secara konkuren oleh $N$ thread independen ($N = \text{jumlah core fisik CPU}$).
   * *Uji Kasus 1 (Unpadded)*: Setiap thread $T_i$ memperbarui variabel counter `uint64_t` miliknya yang ditempatkan bersebelahan di array tanpa padding (`counter[i]++` sebanyak $10^8$ iterasi).
   * *Uji Kasus 2 (Cache-Line Padded / Aligned)*: Setiap thread $T_i$ memperbarui variabel counter yang dialokasikan dengan padding eksplisit atau tipe terisolasi 64-byte (`alignas(64)`), mengisolasi setiap counter ke dalam *cache line* terpisah.
   * Ukur degradasi performa akibat *cache coherency traffic* pada Kasus 1 dibandingkan Kasus 2.
3. **Modul 3: Hardware Diagnostics Measurement**
   * Integrasikan pembacaan instruksi siklus hardware langsung (misalnya `__rdtsc()` pada x86_64 atau register clock cycle setara di ARM) untuk mengukur rata-rata siklus eksekusi per akses memori pada setiap kasus uji.

#### Constraints:
* Program harus ditulis secara *bare-metal* tanpa dependensi pustaka benchmark pihak ketiga (seperti Google Benchmark).
* Hindari eliminasi loop akibat optimasi kompiler (*dead code elimination*) dengan menandai akumulator sebagai `volatile` atau menggunakan trik assembly inline (*compiler memory barrier* seperti `asm volatile("" : "+r"(val))` atau `std::atomic_signal_fence`).
* Alokasi heap memori wajib dilakukan dengan menjaga *memory alignment* menggunakan `posix_memalign`, `aligned_alloc`, atau API setara.

#### Expected Output:
Program menghasilkan laporan terformat pada konsol yang menampilkan:
* Metrik perbandingan Row-Major vs Column-Major: Latensi total, rasio perlambatan (*slowdown factor*, biasanya $5\times - 20\times$), dan estimasi *cache miss penalty*.
* Metrik False Sharing: Total waktu eksekusi unpadded vs padded, rasio kecepatan eksekusi per thread (*speedup multiplier*, biasanya $3\times - 8\times$ pada kasus padded), dan estimasi siklus CPU per penulisan.
* Analisis output teks singkat yang menerjemahkan angka metrik tersebut berdasarkan arsitektur CPU mesin host (ukuran L1d cache line, clock speed CPU, dan latency cycle).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan model Von Neumann dan peran krusial hierarki memori (Register, L1, L2, L3, RAM) dalam menyembunyikan latensi interkoneksi bus.
- [ ] Representasi data biner pada hardware: representasi bilangan bulat Two's Complement, format floating-point IEEE 754 (Sign, Exponent, Mantissa), dan bias/presisi desimal.
- [ ] Mekanisme pemrosesan instruksi pipeline CPU, klasifikasi hazard (Structural, Data, Control), dan logika kerja Branch Prediction.
- [ ] Protokol koherensi cache (seperti MESI/MOESI) dan dampak fenomena False Sharing terhadap interconnect bus perangkat keras.
- [ ] Perbedaan model memori perangkat keras (*Strong Memory Ordering* x86 vs *Weak Memory Ordering* ARM) dan relevansi instruksi atomik serta *memory barriers*.
- [ ] Cara kerja MMU dan OS dalam virtual memory management: Page Table, TLB hit/miss, serta degradasi sistem akibat Page Fault.
- [ ] Dampak compiler structure padding terhadap utilisasi memori dan arsitektur akses berbasis *data-oriented design* (AoS vs SoA).

### Saya tidak perlu menghafal:
- [ ] Opcode numerik heksadesimal spesifik untuk setiap instruksi assembly x86 atau ARM.
- [ ] Konfigurasi sirkuit logika gerbang NAND/NOR level silikon transistor pada ALU fisik.
- [ ] Nilai presisi numerik tabel eksponen floating-point IEEE 754 di luar pemahaman strukturnya (32-bit vs 64-bit).
- [ ] Urutan pinout perangkat keras bus memori DDR4/DDR5.

### Saya harus bisa melakukan:
- [ ] Menghitung manual alokasi memori dan ukuran padding byte dari suatu `struct` bahasa C/C++/Rust serta merombaknya ke ukuran paling minimal.
- [ ] Mengidentifikasi dan merefaktor kode yang rentan terhadap degradasi performa akibat *False Sharing* menggunakan alignment/padding 64-byte.
- [ ] Menganalisis algoritma manipulasi memori intensif untuk mengubah pola akses dari non-contiguous stride menjadi *cache-friendly contiguous access*.
- [ ] Menentukan penggunaan semantik *Memory Ordering* yang tepat (`memory_order_relaxed`, `acquire`, `release`, `seq_cst`) pada kode multi-threaded konkuren tingkat rendah.
- [ ] Menggunakan alat profiling sistem (seperti Linux `perf`, `valgrind --tool=cachegrind`, atau counter hardware CPU) untuk memvalidasi metrik *cache-misses*, *branch-misses*, dan *CPI*.