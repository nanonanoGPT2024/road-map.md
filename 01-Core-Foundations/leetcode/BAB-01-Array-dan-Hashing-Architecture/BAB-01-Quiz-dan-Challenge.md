# BAB 01: Quiz, Challenge, & Knowledge Check
**Array & Hashing Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Memori Kontigu dan Kalkulasi Alamat Fisik:**  
   Jelaskan secara matematis dan arsitektural bagaimana CPU menghitung alamat memori elemen array multi-dimensi `A[i][j]` pada memori berarsitektur *row-major order*. Mengapa akses array kontigu menghasilkan performa *throughput* yang jauh lebih tinggi dibanding *linked structure* pada level L1/L2 data cache? Kaitkan dengan konsep *cache line* (64-byte) dan *spatial locality*.

2. **Dinamika Geometrik Dynamic Array:**  
   Buktikan secara matematis mengapa faktor pertumbuhan (*growth factor*) geometrik sebesar $2\times$ (atau $1.5\times$ seperti pada `std::vector` MSVC) menghasilkan kompleksitas waktu teramortisasi $O(1)$ untuk operasi `push_back`/`append`, sedangkan penambahan kapasitas secara konstan/aritmetika (misal: $+k$ elemen setiap kali penuh) mendegradasi kompleksitas teramortisasi menjadi $O(N)$.

3. **Collision Resolution Mechanics:**  
   Bandingkan arsitektur resolusi tabrakan (*collision resolution*) antara *Separate Chaining* (menggunakan linked list/red-black tree) dan *Open Addressing* (khususnya *Linear Probing* dan *Robin Hood Hashing*). Tinjau perbandingan ini dari aspek:
   * *Memory overhead* per elemen (pointer vs flat memory).
   * Perilaku *cache miss* (*pointer chasing* vs *sequential scanning*).
   * Batasan praktis dari nilai *load factor* ($\alpha$).

4. **Sifat Matematis Hash Function Ideal:**  
   Sebutkan dan elaborasi tiga properti matematis fundamental yang wajib dimiliki oleh fungsi hash non-kriptografis performa tinggi (seperti MurmurHash3, xxHash, atau SipHash) ketika diaplikasikan pada Hash Table produksi. Mengapa operator modulo terhadap bilangan prima ($h(k) \pmod p$) sering digunakan pada tabel konvensional, dan mengapa tabel modern beralih ke ukuran bertumbuh pangkat dua ($2^n$) dengan bitwise masking (`h(k) & (capacity - 1)`)?

5. **Penghapusan Data pada Open Addressing dan Fenomena Tombstone:**  
   Pada skema *Open Addressing* dengan *Linear Probing*, jelaskan mengapa kita tidak boleh langsung mengubah slot elemen yang dihapus menjadi `NULL`/kosong. Jelaskan mekanisme kerja penanda *Tombstone* (*soft delete*), dan analisis bagaimana akumulasi *tombstone* dapat mendegradasi operasi *search* yang berujung pada kompleksitas terburuk $O(N)$ meskipun *load factor* aktual tampak rendah.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Debugging Degenerate Hash Table (HashDoS):**  
   Sebuah microservice *ingestion engine* mengalami lonjakan utilisasi CPU hingga 100% dan latensi p99 meroket dari 2ms ke 4.500ms saat memproses payload JSON dengan 50.000 key unik dari klien eksternal. Profiling menunjukkan CPU *time* terkonsentrasi pada fungsi `find()` di internal hash map.  
   * **Diagnosa:** Fenomena apa yang terjadi pada *hash bucket* sistem?  
   * **Root Cause:** Celah apa pada pemilihan algoritma hash bawaan runtime yang memungkinkan eksploitasi ini?  
   * **Mitigasi:** Langkah mitigasi arsitektural apa yang wajib diimplementasikan pada level algoritma hash untuk mencegah vektor serangan ini secara permanen?

2. **Resize Thrashing & Latency Spikes:**  
   Sebuah *high-frequency ingestion buffer* berbasis dynamic array secara bergantian melakukan operasi `push` dan `pop` di sekitar batas kapasitas $N$ (kapasitas terisi $N \to N+1 \to N \to N+1$).  
   * Jika strategi deallokasi array langsung mengecilkan kapasitas (*shrink-to-fit*) ke $N$ saat elemen menjadi $N$, hitung kompleksitas *worst-case* per operasi dari rangkaian instruksi tersebut.  
   * Rancang arsitektur strategi ambang batas (*hysteresis*) deallokasi kapasitas yang benar untuk menjamin batas waktu teramortisasi tetap $O(1)$.

3. **Mutable Object as Hash Key Antipattern:**  
   Amati cuplikan konsep berikut: Sebuah objek kelas `Transaction` dijadikan *key* dalam struktur data `HashMap`. Di tengah eksekusi, salah satu atribut dari objek tersebut diubah nilainya secara in-place melalui *setter*.  
   * Apa yang terjadi secara internal saat pemanggilan `map.containsKey(tx)` dilakukan setelah mutasi tersebut?  
   * Mengapa situasi ini dapat memicu *silent memory leak* pada memory management runtime (seperti JVM Garbage Collector atau Go Runtime)?

4. **Debugging Cache-Conscious Traversal:**  
   Diberikan sebuah matriks integer dua dimensi berukuran $10.000 \times 10.000$.  
   Kode A membaca elemen dengan perulangan: `for i: for j: sum += matrix[i][j]`  
   Kode B membaca elemen dengan perulangan: `for j: for i: sum += matrix[i][j]`  
   Secara matematis, jumlah instruksi assembly pada level logika adalah identik ($10^8$ iterasi). Namun, pada eksekusi riil, Kode B berjalan 8 hingga 15 kali lebih lambat dibanding Kode A. Bedah apa yang terjadi pada Translation Lookaside Buffer (TLB), L1 Data Cache line loading, dan *hardware prefetcher* yang memicu disparitas performa ekstrem tersebut.

5. **Robin Hood Hashing Displacement Debugging:**  
   Pada struktur data *Robin Hood Hash Table*, setiap elemen menyimpan informasi *Distance to Initial Bucket* (DIB / PSL - *Probe Sequence Length*).  
   * Uraikan algoritma *insertion swap* saat elemen baru memiliki PSL lebih besar daripada PSL elemen yang sedang menempati slot tertentu.  
   * Bagaimana properti PSL ini dimanfaatkan untuk menghentikan pencarian (*early-exit lookup failure*) pada *key* yang tidak ada di dalam tabel, tanpa harus menelusuri seluruh *cluster* data?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bottleneck Latensi P99 pada Real-Time Order Matching Engine
**Konteks Sistem:**  
Anda adalah *Lead Core Architect* di sebuah bursa aset digital. Sistem *in-memory order book* memproses hingga 500.000 pesanan per detik (*orders/sec*). Arsitektur lama menggunakan struktur data hash map standar bawaan runtime untuk memetakan `OrderID (UUIDv4) -> Order Struct Pointer`.  
**Masalah:**  
Setiap rata-rata 45 detik, sistem mengalami *micro-freeze* selama 180ms hingga 320ms pada metrik latensi p99.9. Selama rentang waktu ini, *message broker buffer* meluap dan memicu pembatalan massal dari klien algoritmik.  
Analisis telemetry mengonfirmasi bahwa *freeze* terjadi bersamaan dengan alokasi memori internal map ketika kapasitas melampaui *load factor threshold* (0.75), yang memaksa proses *table rehashing* secara menyeluruh (*stop-the-world reallocation*).

* **Pertanyaan Diagnostik & Desain:**
  1. Mengapa alokasi ulang dan rehashing sinkron pada *load factor* 0.75 menjadi fatal bagi arsitektur komputasi deterministik latensi ultra-rendah (*ultra-low-latency*)?
  2. Rancang strategi **Incremental Rehashing** (atau *Progressive Rehashing*) untuk memecah beban alokasi memori tersebut sehingga latensi terdistribusi secara konstan ke setiap operasi mutasi tanpa menghentikan thread pemrosesan order.

---

### Skenario B: Race Condition dan Memory Corruption pada Concurrency Tinggi
**Konteks Sistem:**  
Sebuah platform analitik web memproses *heartbeat ping* dari jutaan pengguna simultan. Tim merekayasa modul *session tracking* in-memory dengan bahasa multi-threaded (misal C++ atau Go). Untuk mengejar efisiensi, modul tersebut menggunakan flat array hash map global yang dimutasi bersama oleh 32 worker thread tanpa locking penuh, hanya mengandalkan flag atomik `is_locked` primitif pada level bucket.  
**Masalah:**  
Pada kondisi beban puncak (*peak load*), terjadi insiden *segmentation fault* / *panic fatal* yang mematikan proses server seketika. Pada skenario lain di mana crash tidak terjadi, metrik menunjukkan hilangnya ratusan ribu sesi aktif (kunci valid tiba-tiba mengembalikan nilai `NULL` atau data tertukar antar user).

* **Pertanyaan Diagnostik & Desain:**
  1. Identifikasi secara tepat skenario urutan instruksi (*interleaving instruction sequences*) saat dua worker thread melakukan *resizing* secara paralel yang menyebabkan memori referensi *dangling pointer* atau hilangnya integritas *internal bucket array*.
  2. Evaluasi trade-off arsitektural antara:
     * *Global Read-Write Mutex (RWLock)*.
     * *Lock Striping* (Segmented Locks).
     * *Lock-Free Concurrent Hash Map* (menggunakan *Atomic CAS* dan penandaan pointer / split-ordered lists).  
     Manakah yang paling tepat untuk beban 90% Read dan 10% Write dengan throughput target $10^6$ QPS? Berikan justifikasi teknisnya.

---

### Skenario C: Trade-off Arsitektur Sistem Embedded / Edge Caching
**Konteks Sistem:**  
Anda merancang layer L1 Cache untuk router edge berbasis IoT dengan batasan hardware ketat: total alokasi memori heap untuk cache dibatasi maksimal 8 Megabyte, tanpa ketersediaan memori virtual (tanpa *swap*), dan prosesor berarsitektur ARM Cortex tanpa kapabilitas *branch predictor* yang canggih.  
Cache ini harus menyimpan *routing entry* berupa pasangan `uint32_t IP_Address` dan `uint16_t Interface_ID` (total ~6 byte data per record, dibulatkan menjadi 8-byte untuk memory alignment). Target utilisasi kapasitas adalah menyimpan hingga 800.000 entry.

* **Pertanyaan Diagnostik & Desain:**
  1. Jika arsitek junior mengusulkan penggunaan *Chained Hash Table* standar di mana setiap node adalah struct alokasi heap dinamis terpisah: `struct Node { uint32_t k; uint16_t v; Node* next; }`, buktikan secara kalkulasi matematis memori mengapa solusi ini akan mengalami *Out-Of-Memory (OOM)* seketika dan gagal beroperasi di bawah batasan 8 MB. (Asumsikan overhead alokator memori 64-bit/32-bit dan pointer alignment).
  2. Rancang arsitektur alternatif berbasis **Contiguous Flat-Array Hash Map** (misalnya *Linear Probed / Robin Hood Flat Array*) yang memenuhi syarat kapasitas 800.000 entry dan tetap berada di bawah batas ketat 8 MB memori fisik. Tentukan tipe layout datanya (*Array of Structures* vs *Structure of Arrays*) untuk meminimalkan *cache miss*.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance, Zero-Allocation Flat Hash Map (Robin Hood Probing)

Implementasikan atau rancang arsitektur engine hash map in-memory tingkat lanjut yang memenuhi parameter industri berikut:

* **Problem Statement:**  
  Rancang struktur data flat hash map berkinerja tinggi bernama `ZeroAllocRobinHoodMap` yang didesain khusus untuk throughput tinggi tanpa memicu alokasi memori heap dinamis setelah proses inisialisasi awal (*zero runtime allocations*). Struktur data ini ditujukan untuk lingkungan *real-time processing* di mana *latency jitter* yang disebabkan oleh *garbage collector* atau fragmentasi heap dilarang keras.

* **Architectural Requirements:**
  1. **Memory Topology:** Seluruh storage harus menggunakan satu blok array kontigu (*flat buffer* / continuous memory block). Dilarang keras menggunakan pointer chasing atau node berantai linked list.
  2. **Collision Resolution:** Gunakan algoritma *Robin Hood Hashing* dengan pelacakan *Probe Sequence Length (PSL)* untuk meminimalisasi *variance* pencarian (mengurangi latensi *worst-case*).
  3. **Deletion Strategy:** Implementasikan mekanisme **Backward Shift Deletion** alih-alih menggunakan *Tombstone*. Ketika sebuah elemen dihapus, geser elemen-elemen di probe sequence berikutnya ke belakang hingga mencapai elemen dengan PSL = 0 atau slot kosong. Hal ini menjamin penghapusan tidak meninggalkan jejak (*zero tombstone overhead*) dan lookup tidak terdegradasi seiring berjalannya waktu.
  4. **Growth Invalidation Policy:** Kapasitas array ditentukan di awal (*fixed-capacity* atau *pre-allocated buffer pool*). Operasi `insert` harus mengembalikan status error/flag kegagalan secara deterministik jika *load factor* melampaui target kapasitas aman ($\alpha > 0.85$), tanpa pernah mencoba mengalokasikan array baru secara transparan di tengah operasi traversal.

* **Constraints:**
  * Alokasi memori internal: Tepat 1 kali alokasi saat inisialisasi ($O(1)$ allocation throughout lifecycle).
  * Lookup Complexity: Rata-rata $O(1)$ time, Worst-case strictly bounded (PSL variance mendekati nol).
  * Memory Overhead: Tidak boleh lebih dari 1 byte overhead per slot untuk menyimpan metadata PSL.

* **Expected Output:**
  * Deskripsi tata letak memori byte-level (*memory layout layout diagram/struct definition*).
  * Algoritma pseudocode/implementasi presisi untuk:
    * `insert(key, value) -> bool` (dengan logika *PSL eviction and shift*).
    * `search(key) -> Value*` (dengan kondisi terminasi *early-exit* berbasis PSL).
    * `delete(key) -> bool` (dengan logika *backward shift* untuk pembersihan slot instan).
  * Analisis formal batas latensi operasi terburuk (*worst-case operations bound*).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Representasi fisik array di memori utama dan mekanisme kerja *Hardware Prefetcher* serta *CPU Cache Line* (Spatial vs Temporal Locality).
- [ ] Amortized Analysis: Perbedaan mendasar antara *worst-case guarantee* vs *amortized complexity* pada operasi mutasi array dan map.
- [ ] Vektor kerentanan *HashDoS* dan signifikansi penggunaan algoritma hash terproteksi (*cryptographically keyed hash* seperti SipHash) saat mengekspos endpoint ke publik.
- [ ] Trade-off fundamental performa traversal antara *Structure of Arrays (SoA)* dan *Array of Structures (AoS)* dalam konteks saturasi bandwidth bus memori.
- [ ] Mekanisme matematis konversi indeks hash berbasis modulus prima vs bitwise AND mask pangkat dua beserta konsekuensi sebaran bitnya (*bit distribution*).
- [ ] Dampak negatif de-alokasi naif (*resize thrashing*) pada sistem penanganan antrean berbasis dynamic buffer.

### Saya tidak perlu menghafal:
- [ ] Konstanta perkalian heksadesimal internal dari algoritma hash spesifik (seperti konstanta *FNV-prime* atau konstanta *xxHash*).
- [ ] Rumus matematika lengkap pembuktian *Chebyshev's inequality* untuk dispersi hash.
- [ ] Sintaks mikro implementasi instruksi assembly SIMD (AVX-512 / SSE4.2) untuk *vectorized probing* (cukup pahami konsep teoritisnya).

### Saya harus bisa melakukan:
- [ ] Menghitung kebutuhan konsumsi memori fisik riil (dalam Megabyte/Gigabyte) dari sebuah struktur data Array atau Hash Table berdasarkan ukuran struct, alignment padding, dan *load factor* target.
- [ ] Mendiagnosa dan membuktikan keberadaan degradasi performa Hash Table akibat benturan data (*clustering/collision*) menggunakan profiling tools (misal: Linux `perf`, flamegraph, heap profiler).
- [ ] Mengimplementasikan resolusi tabrakan *Linear Probing* atau *Robin Hood Hashing* lengkap dengan algoritma penghapusan data yang bebas dari *lookup broken chain*.
- [ ] Mengonversi kode algoritma berbasis *pointer-chasing* berkinerja buruk menjadi struktur data berbasis *contiguous flat array* yang ramah CPU cache.