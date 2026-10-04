# BAB 10: Quiz, Challenge, & Knowledge Check
**Advanced Structures & Specialized Paradigms**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Fenwick Tree (BIT) vs. Segment Tree Trade-offs
Secara teoritis, Segment Tree dapat menyelesaikan semua masalah yang dapat diselesaikan oleh Binary Indexed Tree (Fenwick Tree), tetapi tidak berlaku sebaliknya.
* Jelaskan secara struktural mengapa Fenwick Tree memiliki batasan fungsional dibanding Segment Tree (khususnya terkait operasi *non-invertible* seperti Range Minimum Query tanpa batasan khusus).
* Mengapa Fenwick Tree tetap menjadi pilihan utama dalam lingkungan *high-frequency trading* atau sistem *low-latency* jika kedua struktur data tersebut memenuhi syarat operasi? Tinjau dari perspektif *cache locality*, *memory footprint*, dan *instruction pipelining*.

### Soal 1.2: Mekanisme Lazy Propagation pada Range Updates
Pada Segment Tree standar, pembaruan rentang (*range update*) $[L, R]$ secara naif membutuhkan waktu $O(N \log N)$ atau $O(N)$.
* Jelaskan invariansi (*invariants*) state yang harus dipertahankan saat menerapkan *Lazy Propagation* agar kompleksitas tetap berada pada $O(\log N)$.
* Kapan tepatnya nilai pada *lazy array/node* harus di-*push down* ke *child nodes*, dan apa konsekuensinya terhadap konsistensi data jika urutan operasi akumulasi pembaruan tertunda (*deferred updates*) tidak bersifat komutatif?

### Soal 1.3: Asimtotik Amortisasi Disjoint Set Union (DSU)
Kombinasi optimasi *Path Compression* dan *Union by Rank/Size* menghasilkan batas atas kompleksitas waktu operasi hampir-konstan $O(\alpha(N))$ per operasi, di mana $\alpha$ adalah *Inverse Ackermann Function*.
* Buktikan secara konseptual mengapa menggunakan *Path Compression* saja tanpa *Union by Rank* menghasilkan kompleksitas kasus terburuk $O(N \log N)$ atau bahkan $O(N^2)$ pada skenario degeneratif tertentu.
* Mengapa nilai rank tidak diperbarui (di-decrement) selama eksekusi rekursif *Path Compression*? Apakah hal ini merusak integritas batas atas kedalaman pohon? Jelaskan alasannya.

### Soal 1.4: Paradigma Meet-in-the-Middle
Pada masalah komputasi kombinatorial yang memiliki kompleksitas waktu eksponensial $O(2^N)$ (seperti *Subset Sum Problem* varian bounded):
* Jelaskan transisi matematis yang memungkinkan *Meet-in-the-Middle* mereduksi kompleksitas menjadi $O(2^{N/2} \cdot \frac{N}{2})$ atau $O(2^{N/2})$.
* Analisis trade-off ruang (*space-time trade-off*) yang terjadi. Pada batasan memori sebesar 256 MB, berapakah batas maksimal $N$ yang aman secara teoretis dan praktis untuk diproses menggunakan paradigma ini?

### Soal 1.5: Bitwise Trie untuk Operasi Prefix & XOR
Struktur data Bitwise Trie (biasanya berkedalaman konstan 32 atau 64 level) sering digunakan untuk menyelesaikan *Maximum XOR Subarray*.
* Jelaskan mekanika *greedy traversal* pada Bitwise Trie untuk menemukan nilai pasangan $X$ yang memaksimalkan $X \oplus Y$ dari sekumpulan elemen yang sudah tersimpan.
* Bagaimana Bitwise Trie dapat dimodifikasi untuk mendukung query *dynamic count of elements strictly smaller than $K$ after XOR with $V$* dalam waktu $O(B)$ di mana $B$ adalah jumlah bit representasi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Bit Manipulation Two’s Complement pada Fenwick Tree
Ekspresi `i & (-i)` adalah inti dari navigasi indeks pada Fenwick Tree.
* Buktikan secara matematis representasi biner bagaimana operasi `i & (-i)` berhasil mengekstrak *Least Significant Set Bit* (LSB) menggunakan representasi *two's complement*.
* Debugging kasus: Seorang insinyur mengimplementasikan Fenwick Tree berbasis 0-indexed dan menuliskan loop pembaruan:
  ```cpp
  void update(int i, int delta) {
      for (; i < n; i += (i & (-i))) tree[i] += delta;
  }
  ```
  Jelaskan secara tepat malfungsi yang terjadi saat fungsi ini dipanggil dengan parameter `i = 0`, dan bagaimana cara memetakan representasi 0-indexed ke 1-indexed secara matematis tanpa menimbulkan *infinite loop* atau alokasi memori berlebih.

### Soal 2.2: Memory Overhead & Cache Thrashing pada Segment Tree
Diberikan representasi Segment Tree array implisit konvensional berukuran $4N$.
* Turunkan pembuktian matematis mengapa alokasi $4N$ mutlak diperlukan untuk mencegah *buffer overflow* ketika $N$ bukan merupakan bilangan pangkat dua ($N \neq 2^k$).
* Pada sistem dengan arsitektur memori modern, struktur Segment Tree dengan alokasi pointer dinamis (`Node* left, *right`) kerap mengalami performa buruk (*throughput drop*) hingga 3x lipat dibanding array datar (*flat array*), meskipun kompleksitas $O(\log N)$-nya identik. Identifikasi akar masalah pada level arsitektur CPU (L1/L2 cache lines, TLB misses, memory fragmentation) dan jelaskan solusinya.

### Soal 2.3: Inkompatibilitas Path Compression pada Undoable/Rollback DSU
Dalam algoritma tingkat lanjut (misal: *Dynamic Graph Connectivity* via Divide and Conquer / CDQ Divide and Conquer), kita membutuhkan struktur data DSU yang mendukung operasi `rollback()` ke kondisi state waktu $T$ sebelumnya.
* Mengapa teknik *Path Compression* merusak kemampuan melakukan operasi *rollback* yang efisien secara riwayat mutasi (*history log*)?
* Bagaimana cara mengimplementasikan DSU yang sepenuhnya dapat di-*undo* dalam kompleksitas waktu $O(\log N)$ per operasi union/find dan $O(1)$ per rollback? Tinjau perubahan pada *call stack*, mutasi referensi pointer/indeks, dan batas kedalaman pohon.

### Soal 2.4: Dynamic Segment Tree vs Coordinate Compression pada Streaming Data
Diberikan rentang koordinat query $1 \le L \le R \le 10^9$, namun total query rentang yang masuk hanya berjumlah $Q = 10^5$.
* Bandingkan pendekatan *Coordinate Compression (Offline)* vs *Dynamic Segment Tree (Node Creation on-the-fly / Online)*.
* Pada skenario apa teknik *Coordinate Compression* mutlak gagal digunakan sehingga mewajibkan penggunaan *Dynamic Segment Tree* atau *Implicit Segment Tree*? Hitung batas alokasi memori maksimum untuk *Dynamic Segment Tree* dengan kedalaman $\approx 31$ level untuk $10^5$ kali mutasi titik.

### Soal 2.5: Bottleneck Analysis pada Mo’s Algorithm
Mo’s Algorithm mengurutkan query secara luring (*offline*) berdasarkan pasangan $(\lfloor L / B \rfloor, R)$.
* Buktikan mengapa pemilihan ukuran blok $B = \frac{N}{\sqrt{Q}}$ menghasilkan batas waktu optimal $O(N \sqrt{Q})$ untuk pergerakan pointer $[L, R]$.
* Tinjau kasus *cache thrashing*: Mengapa pengurutan standar Mo sering dioptimalkan dengan teknik *Hilbert Curve Ordering* atau pengurutan zigzag (parity sort pada $R$ di mana blok ganjil mengurutkan $R$ *ascending* dan blok genap *descending*)? Berapa besar reduksi pergerakan pointer konstan yang diperoleh secara empiris?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike pada Real-Time Telemetry Metrics Aggregator
Sebuah platform observabilitas memproses *stream* metrik finansial dengan volume transaksi mencapai 500.000 events/detik. Sistem wajib melayani API yang meminta agregasi dinamis: *“Hitung Weighted Moving Average, Nilai Ekstrem (Max/Min), dan Varians pada sembarang window interval waktu $[T_1, T_2]$ secara real-time”*. 

Awalnya tim engineering mengimplementasikan Segment Tree in-memory konvensional berbasis array. Namun, ketika rentang waktu diperluas dan pembaruan massal (*bulk backfill data*) terjadi via worker paralel, sistem mengalami degradasi drastis: latensi P99 melonjak dari 2ms menjadi 850ms, dan GC (*Garbage Collection*) pause melonjak tinggi.
* **Pertanyaan Diagnostik & Arsitektur:**
  1. Identifikasi penyebab kegagalan konkurensi dan latensi Segment Tree implisit saat berhadapan dengan mutasi konkuren dan read-heavy load berskala tinggi.
  2. Rancang arsitektur struktur data in-memory pengganti: Apakah Anda akan mendesain *Lock-Free/Concurrent Fenwick Tree*, *Persistent Segment Tree* yang *immutable*, atau kombinasi *Bucket-based Chunking (SQRT Decomposition)*? Berikan justifikasi teknis lengkap dengan membandingkan *write overhead* vs *read contention*.

### Skenario B: Race Condition & State Invalidation pada Distributed Lock Manager Topologi Jaringan
Sebuah *Distributed Orchestrator* mengelola graf dependensi mikroservis yang terdiri dari $10^5$ service nodes. Setiap service node dapat meminta penggabungan cluster atau isolasi jaringan secara runtime. Engine mendeteksi siklus dependensi dan partisi jaringan menggunakan implementasi DSU paralel berbasis shared memory. 

Dalam investigasi *post-mortem* pasca insiden *split-brain*, ditemukan bahwa dua worker thread mengeksekusi operasi `union(A, B)` dan `find(C)` secara simultan tanpa koordinasi sinkronisasi yang ketat, menyebabkan DSU membentuk siklus tak berhingga (*infinite loop*) pada node representatif, yang memicu CPU core 100% saturation dan kegagalan isolasi jaringan.
* **Pertanyaan Diagnostik & Arsitektur:**
  1. Bedah secara mekanistis bagaimana *Path Compression* yang tidak tersinkronisasi (*unsynchronized concurrent path compression*) dapat memicu *cyclic reference* (pohon himpunan berputar pada dirinya sendiri) pada pointer DSU.
  2. Rancang struktur DSU yang *thread-safe* dan *lock-free* menggunakan operasi atomik CPU (`std::atomic`, CAS/*Compare-And-Swap*). Bagaimana Anda menangani operasi *path halving* atau *path splitting* tanpa memblokir thread lain melalui *mutex lock*?

### Skenario C: High-Throughput CIDR Prefix Firewall & Dynamic Blacklisting Engine
Sebuah sistem Software-Defined Networking (SDN) pada Edge Router bertugas memfilter paket masuk berdasarkan aturan blacklist IP. Aturan IP diformat dalam notasi CIDR (misal: `192.168.1.0/24`, `10.0.0.0/8`, hingga `/32` spesifik) yang mencapai jutaan entri. Sistem harus mampu melakukan operasi berikut pada kecepatan kabel (*line-rate* 40 Gbps):
1. Menentukan apakah sebuah IP tujuan cocok dengan prefix terpanjang (*Longest Prefix Match*) yang ada di blacklist.
2. Menerima penambahan/penghapusan aturan CIDR secara dinamis tanpa downtime atau pemblokiran trafik paket (harus *sub-microsecond lookup*).

Pendekatan menggunakan Hash Table mengalami degradasi performa karena prefix mask bervariasi dari 0 hingga 32 bit (memerlukan 32 kali *hash lookup* terburuk), sementara standard Trie pointer memicu *memory bloat* dan *cache miss* masif.
* **Pertanyaan Diagnostik & Arsitektur:**
  1. Rancang arsitektur struktur data khusus berbasis Bitwise Trie (misal: *Radix Tree*, *Level-Compressed Trie (LC-Trie)*, atau *Popcount-indexed Bitwise Trie*) yang meminimalkan *pointer chasing* dan mengoptimasi *cache-line boundary* (64 bytes).
  2. Bagaimana strategi Anda mengelola mutasi dinamis (*concurrent read-write*) pada struktur data ini sehingga thread pemrosesan paket dapat membaca tanpa terkunci (*wait-free read*), sementara thread konfigurasi dapat memperbarui aturan CIDR secara aman?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance In-Memory Sliding-Window Order-Statistic & Volatility Engine

#### Problem Description
Di sebuah bursa terdesentralisasi (*Decentralized Exchange Engine*), Anda diminta membangun modul in-memory core bernama `OrderStatisticVolatilityTracker`. Modul ini bertugas melacak aliran harga transaksi (*trade stream*) secara real-time dan menjawab statistik rentang kuantil dinamis secara instan.

Setiap order memiliki `Timestamp` (monotonik naik) dan `Price` (integer desimal yang di-scale, misal: $1 \le \text{Price} \le 10^7$). Engine harus mampu menangani jutaan transaksi yang masuk dan menjawab metrik analitik pada rentang riwayat dinamis.

#### Detailed Requirements & API Specification
Anda diwajibkan mengimplementasikan struktur data dalam C++, Rust, atau Java/Go dengan performa tinggi tanpa menggunakan library struktur data eksternal (larang penggunaan `std::map`, `std::multiset`, atau `TreeMap` pada jalur kritis query rentang).

Struktur data harus menyediakan antarmuka berikut:

1. `void record_trade(uint64_t timestamp, uint32_t price)`
   * Menambahkan data transaksi baru ke dalam sistem.
   * Nilai timestamp selalu strictly greater than transaksi sebelumnya ($T_i > T_{i-1}$).

2. `void batch_adjust_prices(uint64_t start_time, uint64_t end_time, int32_t delta)`
   * Melakukan pembaruan massal (bisa positif atau negatif) terhadap harga semua transaksi yang berada pada rentang waktu `[start_time, end_time]`.
   * Operasi ini wajib berjalan efisien dan tidak boleh memperbarui elemen satu per satu ($O(N)$ dilarang).

3. `uint32_t query_rank_price(uint64_t start_time, uint64_t end_time, uint32_t k)`
   * Mengembalikan harga dari transaksi berperingkat ke-$k$ terkecil (*k-th smallest order-statistic*) yang dieksekusi dalam interval waktu $[start\_time, end\_time]$.
   * Jika jumlah transaksi dalam interval kurang dari $k$, kembalikan status error / sentinel value.

4. `double query_volatility(uint64_t start_time, uint64_t end_time)`
   * Mengembalikan standar deviasi populasi dari harga transaksi pada rentang waktu tersebut:
     $$\sigma = \sqrt{\frac{\sum (P_i - \mu)^2}{M}}$$
     di mana $M$ adalah total transaksi pada interval tersebut dan $\mu$ adalah rata-rata harga.

#### Constraints
* $N$ (Total pemanggilan gabungan `record_trade` dan `batch_adjust_prices`) $\le 200.000$.
* $Q$ (Total pemanggilan query) $\le 200.000$.
* Rentang waktu: $1 \le \text{timestamp} \le 10^{12}$ (sparse timestamps).
* Rentang harga: $1 \le \text{price} \le 10^7$.
* Batas Memori: **256 MB**.
* Batas Waktu Eksekusi: **< 1.5 detik** untuk seluruh eksekusi batch pengujian.
* *Algorithmic Expectation*: 
  * Wajib memanfaatkan perpaduan struktur data tingkat lanjut: **Implicit/Dynamic Segment Tree with Lazy Propagation**, **Merge-Sort Tree / Fenwick on Rank**, atau **Persistent Segment Tree / Treap / Order-Statistic Tree**.

#### Expected Output Deliverables
1. **Source Code Terstruktur**: Kode lengkap yang mengimplementasikan class/struct tersebut beserta driver pengujian sintetis.
2. **Kompleksitas Formal**: Penjelasan teoritis kompleksitas waktu untuk setiap operasi API dan kompleksitas ruang dari representasi memori.
3. **Analisis Invarian Data**: Penjelasan ringkas mengenai bagaimana operasi *Lazy Propagation* disinkronkan dengan kalkulasi agregasi varians ($\sum P_i$ dan $\sum P_i^2$).

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memvalidasi kesiapan Anda sebelum melangkah ke topik *Competitive Programming Elite Track* atau *Staff Systems Engineering Assessment*.

### Saya harus memahami:
- [ ] Mekanika aljabar biner dari operasi `x & (-x)` dan representasi virtual pohon implisit pada Fenwick Tree.
- [ ] Bukti matematis mengapa representasi array datar Segment Tree memerlukan alokasi memori hingga batas $4N$ untuk menangani skenario non-power-of-two.
- [ ] Alur kerja *Lazy Propagation*: kapan lazy tag harus diakumulasi (*merge tags*), kapan harus di-*push down* ke anak, dan dampaknya pada update non-komutatif (seperti kombinasi *range assignment* dan *range addition*).
- [ ] Struktur internal *Disjoint Set Union*: fungsi invers Ackermann $\alpha(N)$, mengapa *Path Compression* merusak struktur *Rollback DSU*, dan implementasi berbasis stack mutasi state.
- [ ] Perbedaan teknis dan domain penggunaan antara *Dynamic/Implicit Segment Tree*, *Persistent Segment Tree (Segment Tree fully persistent via node cloning)*, dan *Fenwick Tree*.
- [ ] Paradigma *Meet-in-the-Middle*: pemisahan ruang pencarian ($N \to N/2$), pembangkitan state, pengurutan, dan teknik penggabungan via *two-pointers* atau *binary search*.
- [ ] Bitwise Trie (Radix-2): aplikasi pada pencarian *Maximum XOR Subarray* dan representasi ruang sparse untuk IP prefix matching.
- [ ] Formulasi matematis optimasi Mo’s Algorithm ($B = N / \sqrt{Q}$) serta mitigasi *cache misses* menggunakan kurva fraktal (Hilbert Curve ordering).

### Saya tidak perlu menghafal:
- [ ] Bukti formal 20 halaman penurunan batas fungsi Ackermann $\alpha(N)$; cukup memahami bahwa nilainya $\le 4$ untuk semua input praktis ($N \le 10^{80}$).
- [ ] Template kode kaku implementasi Fenwick Tree/Segment Tree multi-dimensi; cukup menguasai dekomposisi logika dan penyesuaian invariansi batas array.
- [ ] Derivasi rumus pemetaan Hilbert Curve dari koordinat 2D ke 1D secara presisi di luar kepala; cukup memahami logika pergeseran zigzag untuk meminimalkan *travel distance* pointer.

### Saya harus bisa melakukan:
- [ ] Menulis implementasi Segment Tree dengan fitur *Range Update* dan *Range Query* bebas bug dalam waktu $\le 15$ menit tanpa bantuan referensi eksternal.
- [ ] Menemukan dan memperbaiki *concurrency bugs* pada DSU atau tree-based indices yang berjalan di sistem multi-core.
- [ ] Menghitung kebutuhan konsumsi memori (*memory footprint*) tepat hingga skala megabyte untuk *Dynamic Segment Tree* atau *Trie* sebelum menulis baris kode pertama guna menghindari insiden *Out of Memory (OOM)*.
- [ ] Melakukan dekomposisi masalah komputasi rentang offline menggunakan *Mo's Algorithm* atau *Square-Root Decomposition* saat pohon rentang reguler gagal menampung operasi non-associative.
- [ ] Mengimplementasikan *Bitwise Trie* dengan optimasi memori (misalnya pemanfaatan array primitif alih-alih alokasi heap pointer individual) untuk menjaga *cache locality*.