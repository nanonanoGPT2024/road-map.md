# BAB 08: Quiz, Challenge, & Knowledge Check
**Priority Queues, Heaps & Advanced Intervals**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Memori Kontigu vs. Pointer-Based Tree Representation
Mengapa implementasi standar Binary Heap hampir selalu menggunakan array kontigu (flat array dengan relasi indeks implisit $2i+1$ dan $2i+2$) daripada struktur *node-and-pointer* berbasis heap memory (seperti pada Binary Search Tree)? Analisis perbandingannya berdasarkan:
1. Overhead alokasi memori per elemen (metadata, pointer alignment, dan padding).
2. Efisiensi perangkat keras modern: *CPU cache locality* (L1/L2 data cache lines), *spatial locality*, dan *hardware prefetching*.
3. Mekanisme traversal: kalkulasi matematis berbasis bitwise/aritmatika vs. dereferensi pointer (*pointer chasing*).

### Soal 1.2: Asimptotik Bottom-Up Heapify vs. Top-Down Insertion
Buktikan secara matematis mengapa operasi *Bottom-Up Heap Construction* (`heapify`) pada array berukuran $N$ memiliki kompleksitas waktu $\mathcal{O}(N)$, sedangkan membangun heap secara naif dengan memanggil `insert` berturut-turut sebanyak $N$ kali membutuhkan $\mathcal{O}(N \log N)$. Tuliskan formulasi deret perhitungannya berdasarkan tinggi pohon ($h$) dan jumlah node pada tiap level.

### Soal 1.3: Invarian Struktural & Monotonisitas pada Dual-Heap Median Pattern
Pada pola "Two Heaps" untuk memelihara nilai median dinamis dari data stream tak terbatas (unbounded stream):
1. Definisikan dua invarian matematis absolut yang harus dipenuhi oleh Max-Heap (sisi kiri) dan Min-Heap (sisi kanan) pada setiap siklus transisi status (state transition).
2. Jelaskan mengapa strategi rebalancing harus mempertahankan relasi ukuran $|S_{\text{max}}| - |S_{\text{min}}| \in \{0, 1\}$.
3. Analisis kompleksitas waktu amortisasi operasi `insert` dan operasi `findMedian` bila terjadi skenario terburuk di mana input data terurut secara monotonik naik (*strictly increasing*).

### Soal 1.4: Paradigma Sweep-Line vs. Interval Trees/Segment Trees
Kapan Anda harus memilih algoritma berbasis *Sweep-Line Event Points* ($O(N \log N)$ sorting + sequential scan), dan kapan Anda wajib menggunakan struktur data spasial dinamis seperti *Interval Tree* atau *Segment Tree* ($O(\log N + K)$ query time)? Uraikan perbedaannya ditinjau dari karakteristik beban kerja (workload): **Static Offline Batch Processing** versus **Dynamic Online Point/Range Stabbing Queries**.

### Soal 1.5: Dijkstra, Decrease-Key, dan Strategi Lazy Deletion
Dalam implementasi Shortest Path (Dijkstra) atau Minimum Spanning Tree (Prim):
1. Mengapa operasi `decrease-key` sangat krusial, dan mengapa `std::priority_queue` bawaan C++ atau module `heapq` Python tidak menyediakan API native untuk `decrease-key` yang efisien ($\mathcal{O}(\log N)$)?
2. Bandingkan efisiensi ruang dan waktu antara implementasi **Addressable Priority Queue** (menggunakan indeks balik / hash-map node-to-index) versus pendekatan **Lazy Deletion** (memasukkan pasangan duplikat `(distance, node)` dan mengabaikannya saat diekstrak). Kapan pendekatan *Lazy Deletion* memicu degradasi memori yang fatal?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: $D$-ary Heaps: Trade-off Branching Factor pada Sistem Riil
Banyak sistem enterprise (seperti *OS CPU Schedulers* atau *External-Memory Graph Engines*) mengganti Binary Heap ($d=2$) dengan $D$-ary Heap ($d=4$ atau $d=8$).
1. Turunkan formula umum indeks anak ke-$k$ ($k \in [1, d]$) dan indeks *parent* untuk elemen pada indeks $i$ (berbasis array 0-indexed).
2. Mengapa peningkatan nilai $d$ menurunkan kedalaman pohon ($\log_d N$) namun meningkatkan jumlah perbandingan elemen pada saat operasi `sift-down`?
3. Jelaskan mengapa $d=4$ sering kali menghasilkan performa *wall-clock runtime* yang lebih cepat daripada $d=2$ pada CPU modern, meskipun jumlah instruksi komparasi matematisnya lebih tinggi.

### Soal 2.2: Memory Bloat & GC Thrashing pada Dynamic Min-Heap
Sebuah microservice analitik performa tinggi menulis antrean prioritas berbasis array dinamis di Go/Java yang menampung struct/objek pointer:
```go
type Event struct {
    ID        int64
    Timestamp int64
    Payload   []byte
}
```
Heap ini beroperasi stabil pada throughput 200.000 ops/detik (`Push` dan `Pop` konstan dengan rata-rata kapasitas 5.000.000 elemen). Namun, setelah 48 jam beroperasi, terjadi latensi lonjakan p99.9 (*stop-the-world GC pause*) dan memori residen (RSS) membengkak tanpa batas. 
- Analisis bagaimana fenomena *Memory Leak melalui Lapsed Listeners/Dangling Object References* terjadi di dalam slice/array internal heap saat elemen di-`Pop`.
- Tuliskan koreksi kode struktural untuk memutus referensi pointer agar GC dapat membersihkan memori secara deterministik.

### Soal 2.3: Strategi Tombstone Handling pada High-Cancellation Queues
Pada sistem antrean pemrosesan order bursa saham (*limit-order books*), pengguna sering kali membatalkan order (*cancellation*) sebelum order tersebut dieksekusi. Jika pembatalan dilakukan dengan menandai order sebagai *tombstone* (flag `is_cancelled = true`) di luar heap, lalu dibiarkan hingga mencapai root via `pop`:
- Apa yang terjadi jika rasio pembatalan mencapai 95% dari total $10^7$ transaksi yang masuk?
- Hitung degradasi kompleksitas ruang ($\mathcal{O}$ auxiliary memory) dan latensi operasi `extract-min` terburuk.
- Rancang arsitektur heap compaction atau periodic scavenging mechanism untuk menstabilkan overhead heap secara deterministik tanpa mengorbankan latensi p99.

### Soal 2.4: Edge-Case Pitfalls pada Sweep-Line Interval Merging
Diberikan himpunan interval tertutup $[s_i, e_i]$ di mana domain nilai adalah bilangan bulat 32-bit bertanda:
$$\{ [x, y] \mid x, y \in [\text{INT\_MIN}, \text{INT\_MAX}], x \le y \}$$
Sebutkan dan jelaskan secara teknis 3 potensi kegagalan (edge cases) kritis yang dapat merusak algoritma merging interval klasik:
1. Integer overflow saat menghitung panjang/durasi interval ($e_i - s_i + 1$).
2. Prioritas pengurutan (tie-breaking comparator) saat terjadi tabrakan titik: $e_A == s_B$ (apakah event penutupan interval diproses sebelum pembukaan interval, atau sebaliknya, untuk interval tertutup vs. interval setengah terbuka).
3. Interval degenerate/titik tunggal ($[x, x]$).

### Soal 2.5: Cache Thrashing pada $K$-Way Merge Ekstrem
Saat menggabungkan $K = 50.000$ sorted run logs berukuran total 1 TB dari disk ke disk menggunakan Min-Heap standar berukuran $K$:
1. Mengapa struktur standar Min-Heap menimbulkan *L1/L2 cache invalidation* masif pada setiap ekstraksi elemen?
2. Bagaimana struktur data alternatif **Loser Tree** (*Tournament Tree*) mengurangi separuh jumlah komparasi per `sift-down` dan meningkatkan *instruction-level parallelism* (ILP) dibandingkan Binary Heap konvensional?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Collapse pada Real-Time Top-K Stream Aggregator
Sebuah platform analitik IoT memproses 800.000 metrik per detik. Kebutuhan bisnis adalah menampilkan **Top-100 Perangkat Paling Aktif** per window geser 60 detik (*sliding window*). 

**Implementasi Saat Ini:**
Developer membuat global bounded Min-Heap berukuran $K=100$. Setiap kali ada event masuk dari Kafka consumer thread, thread tersebut mengambil mutex global, memeriksa nilai metrik terhadap root heap, melakukan `Push`/`Pop` jika metrik lebih besar, lalu melepas mutex.

**Gejala di Produksi:**
1. CPU utilization mencapai 100% pada node pemrosesan, namun throughput merosot drastis hingga hanya mampu memproses 40.000 event/detik (terjadi bottleneck masif).
2. Terjadi lonjakan thread contention (*lock thrashing*) yang memblokir semua worker consumer.

**Pertanyaan Diagnostik:**
1. Uraikan mengapa penggunaan *shared bounded min-heap* dengan *coarse-grained locking* adalah anti-pattern fatal pada throughput tinggi.
2. Rancang arsitektur alternatif yang menggabungkan:
   - Partisi lokal (*thread-local buffers* atau *hash-ring striping*).
   - Penggunaan algoritma probabilistic *Count-Min Sketch* atau *Space-Saving Algorithm* untuk pre-filtering.
   - Batch consolidation ke global Min-Heap.
3. Gambarkan diagram alir aliran data yang menjamin throughput stabil $\ge 800.000$ event/detik dengan latensi p99 $< 10$ ms.

---

### Skenario B: Race Condition & Double Allocation pada Autonomous Reservation Engine
Sebuah sistem cloud computing global mengalokasikan slot waktu GPU cluster untuk batch training. Pengguna memesan alokasi dalam format interval $[T_{\text{start}}, T_{\text{end}}]$ dengan kapasitas $C$ unit GPU. Total kapasitas GPU cluster adalah $C_{\text{max}} = 128$ unit.

**Arsitektur Alokasi:**
1. Sistem menyimpan reservasi aktif dalam array interval yang dilindungi oleh Reader-Writer Lock (`RWMutex`).
2. Saat ada request reservasi baru:
   - Request thread mengambil `RLock`.
   - Mengambil seluruh interval yang beririsan dari database in-memory.
   - Menggunakan algoritma *Sweep-Line Event Point* untuk menghitung konsumsi puncak GPU: jika $\max(\text{allocated\_gpu}) + C_{\text{req}} \le C_{\text{max}}$, sistem mengizinkan alokasi.
   - Request thread melepas `RLock`, mengambil `Lock` eksklusif, lalu menulis interval baru ke array in-memory.

**Insiden:**
Di bawah beban uji konkurensi tinggi (500 konkruen request per detik), sistem mengalami insiden alokasi ganda (*over-subscription*), di mana konsumsi aktual GPU melonjak hingga 180/128 unit, menyebabkan beberapa container diterminasikan secara paksa oleh kernel OOM-killer.

**Pertanyaan Diagnostik:**
1. Tunjukkan letak kerentanan konkurensi (*Time-of-Check to Time-of-Use* / TOCTOU vulnerability) pada arsitektur di atas.
2. Mengapa Reader-Writer Lock tidak memadai untuk transaksi alokasi berbasis interval?
3. Rancang ulang state machine alokasi kapasitas interval ini menggunakan struktur data berkinerja tinggi (misal: *Segment Tree dengan Lazy Propagation* atau antrean serial beralas *Optimistic Concurrency Control*) yang aman dari race condition tanpa menyebabkan thread starvation.

---

### Skenario C: Storage Engine Write-Amplification pada Dynamic Interval Merging
Sebuah platform pemantauan jaringan menyimpan riwayat status "Downtime Node" dalam format interval waktu:
$$\{[\text{NodeID}, T_{\text{down\_start}}, T_{\text{down\_end}}]\}$$
Karena pembaruan status terjadi setiap detik dari ribuan probe, probe mengirimkan interval pendek yang saling tumpang tindih (misal: $[10, 25]$, $[20, 30]$, $[28, 45]$).

**Arsitektur Saat Ini:**
Setiap kali ada pembaruan interval untuk Node X, engine membaca seluruh interval Node X dari storage layer (PostgreSQL), melakukan merge interval secara in-memory menggunakan algoritma pengurutan standard $\mathcal{O}(N \log N)$, menghapus seluruh record lama Node X, lalu menulis ulang seluruh interval yang telah dimampatkan (*merged*) kembali ke database.

**Insiden:**
Write-Amplification factor di tingkat database melonjak hingga 45x lipat dari payload asli data telemetry. Latensi query disk I/O kolaps ketika histori sebuah node mencapai lebih dari 50.000 interval.

**Pertanyaan Diagnostik:**
1. Analisis mengapa pendekatan *Fetch-Sort-Merge-Rewrite* menciptakan degradasi kuadratik seiring berjalannya waktu.
2. Rancang struktur data terdistribusi dan format penyimpanan interval log yang memanfaatkan pendekatan *Append-Only Log with Compaction Phase* atau *Interval Skip List*.
3. Jelaskan bagaimana Anda menangani query stabbing: *"Apakah Node X mengalami downtime pada timestamp $T$?"* secara efisien pada sistem rancangan baru Anda tanpa harus melakukan merge global setiap saat.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Event-Driven Auction Matching Engine dengan Dynamic Interval Order Validity

#### Deskripsi Sistem
Bangun sebuah engine pencocokan lelang internal (*In-Memory Double Auction Engine*) yang memproses dua sisi order book: **Bids (Beli)** dan **Asks (Jual)**, dengan validitas waktu interval dinamis dan aturan *Price-Time Priority*.

#### Spesifikasi Input & Order
Setiap order direpresentasikan dengan skema berikut:
```text
Order {
    order_id:       uint64,
    order_type:     enum { BID, ASK },
    price:          uint64,        // dalam satuan cents (misal: $10.50 -> 1050)
    quantity:       uint32,
    valid_interval: [uint64, uint64] // [start_epoch_ms, end_epoch_ms]
}
```

#### Aturan Bisnis Engine
1. **Price-Time Priority dengan Validitas Interval:**
   - BID dengan harga lebih tinggi memiliki prioritas lebih tinggi daripada BID dengan harga lebih rendah.
   - ASK dengan harga lebih rendah memiliki prioritas lebih tinggi daripada ASK dengan harga lebih tinggi.
   - Jika harga sama, prioritaskan order dengan `start_epoch_ms` lebih awal (FIFO).
2. **Kondisi Eksekusi Transaksi:**
   - Match terjadi ketika $\text{Highest BID.price} \ge \text{Lowest ASK.price}$.
   - Match HANYA sah jika kedua order beririsan secara valid pada waktu matching $T_{\text{current}}$:
     $$T_{\text{current}} \in \text{BID.valid\_interval} \quad \land \quad T_{\text{current}} \in \text{ASK.valid\_interval}$$
   - Transaksi terjadi pada harga order yang masuk lebih awal (*maker price*).
3. **Pembersihan Otomatis (Interval Expiration):**
   - Seiring majunya simulasi waktu ($T_{\text{current}}$ bertambah), setiap order yang memiliki `end_epoch_ms < T_current` harus secara otomatis dinyatakan *expired* dan diejeksi dari engine tanpa dialokasikan.

#### Requirements
1. Implementasikan struktur data prioritas ganda (*Dual Priority Queues*) yang dikombinasikan dengan mekanisme kedaluwarsa interval terefisien.
2. Anda **TIDAK DIIZINKAN** melakukan linear scan $\mathcal{O}(N)$ pada seluruh antrean untuk membersihkan order yang telah kedaluwarsa.
3. Desain harus mendukung 3 API utama:
   - `submit_order(order: Order, current_time: uint64) -> List[MatchResult]`
   - `advance_time(new_time: uint64) -> List[ExpiredOrder]`
   - `get_book_depth(current_time: uint64) -> DepthSnapshot` (menghitung total volume bid dan ask yang saat ini aktif).

#### Batasan Teknis (Constraints)
- $N$ (Total order yang masuk): hingga $1.000.000$ order.
- Time range ($T$): $0 \le T \le 2^{63}-1$.
- Latensi per `submit_order`: Maksimal $\mathcal{O}(M \log N)$ di mana $M$ adalah jumlah match yang terjadi.
- Latensi per `advance_time`: Maksimal $\mathcal{O}(E \log N)$ di mana $E$ adalah jumlah order yang kedaluwarsa pada siklus tersebut.
- Penggunaan memori: Maksimal $\mathcal{O}(N)$ memori aktif. Cegah memory leak akibat order yang tertinggal di level daun heap.

#### Expected Output
Implementasikan solusi dalam bahasa pemrograman yang dipilih (C++20, Rust, Go, atau Java) lengkap dengan:
1. Skema struktur data yang memetakan order book (bids, asks, dan expiration tracker).
2. Mekanisme sinkronisasi antara order book dan expiration queue (misal: via *Lazy Deletion with Unique ID Tracker* atau *Addressable Heap*).
3. Unit test komprehensif yang memvalidasi:
   - Skenario overlapping interval order match.
   - Skenario non-overlapping interval order rejection (meskipun harga cocok, interval tidak beririsan dengan waktu eksekusi).
   - Eksekusi parsial (*partial fills*) di mana satu BID besar mencocokkan beberapa ASK kecil secara berurutan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme heapify bottom-up $O(N)$ vs pengurutan naif $O(N \log N)$ serta derivasi deret Taylor/geometrinya.
- [ ] Transformasi matematis representasi complete binary tree ke dalam array 1 dimensi (parent, left child, right child).
- [ ] Mengapa algoritma Dijkstra membutuhkan bounded updates dan implikasi kinerja *lazy deletion* vs *indexable priority queue*.
- [ ] Pengaruh arsitektur memori modern (L1/L2 CPU cache lines, cache misses, branch mispredictions) terhadap efisiensi $D$-ary heaps vs Binary Heaps.
- [ ] Seluruh klasifikasi interval overlaps (6 relasi spasial interval Allen: *before, meets, overlaps, starts, during, finishes*).
- [ ] State management dalam algoritma Sweep-Line: transisi diferensial event point vs interval persistence.
- [ ] Mengapa Two-Heap pattern (Max-Heap dan Min-Heap) secara tepat merepresentasikan partisi kuantil/median dinamis.
- [ ] Perbedaan fundamental antara segment tree, interval tree, dan event-point sweep line untuk multidimensional stabbing queries.

### Saya tidak perlu menghafal:
- [ ] Rumus matematika penurunan asimptotik Fibonacci Heap untuk operasi *decrease-key* ($O(1)$ amortized) secara detail, selama memahami batasan praktisnya (overhead pointer konstan yang sangat tinggi pada memori riil).
- [ ] Kode implementasi mendalam dari kompleksitas Red-Black Tree atau AVL Tree yang mendasari struktur tree interval library standar.
- [ ] Trik representasi bitwise khusus bahasa pemrograman tertentu yang tidak portabel antar-arsitektur (misal: compiler-specific intrinsics untuk heap tracking).

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan Custom Binary Heap dari nol menggunakan fixed-size atau dynamically-resized continuous array dengan zero overhead abstraction.
- [ ] Menulis custom comparator yang deterministik dan anti-bug untuk multi-dimensional interval scheduling dengan skema tie-breaking yang ketat.
- [ ] Mendiagnosis dan mengeliminasi bug konkurensi (seperti TOCTOU) pada sistem reservasi berbasis interval waktu.
- [ ] Mendesain arsitektur *top-k streaming engine* yang mampu memitigasi thread contention dan memory bloat di bawah jutaan write throughput per detik.
- [ ] Menangani pembersihan memory (*resource deallocation*) pada struktur data berbasis heap agar terhindar dari *GC memory retention/leaks*.
- [ ] Memilih secara tepat antara Addressable Priority Queue, Tombstone Lazy Deletion, atau Loser Tree berdasarkan throughput karakteristik sistem produksi.