# BAB 03: Quiz, Challenge, & Knowledge Check
**Monotonic Structures & Stack Execution**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Pembuktian Amortized Analysis pada Monotonic Stack
Secara kasat mata, algoritma yang menggunakan *monotonic stack* memiliki struktur *nested loop*: loop luar mengiterasi elemen array ($N$ kali), dan loop dalam (`while`) melakukan `pop` elemen stack berdasarkan kondisi monotonik. Buktikan secara matematis menggunakan *Aggregate Method* atau *Potential Method* ($\Phi$) mengapa kompleksitas waktu keseluruhan dari algoritma ini dijamin $O(N)$ dan bukan $O(N^2)$.

### Soal 1.2: Boundary Invariant: Strict vs Non-Strict Monotonicity
Jelaskan perbedaan struktural dan semantik komputasi antara *Strictly Increasing Stack* (`stack.top() < current`) dan *Non-Decreasing Stack* (`stack.top() <= current`). Berikan analisis skenario di mana kesalahan memilih salah satu relasi perbandingan di atas dapat memicu bug duplikasi perhitungan (*double counting*) atau *missed boundary* pada persoalan rentang nilai (*span/boundary evaluation*).

### Soal 1.3: Monotonic Stack vs Monotonic Deque
Kapan abstraksi *Monotonic Stack* (LIFO) tidak lagi mencukupi dan arsitektur data harus beralih ke *Monotonic Deque* (Double-Ended Queue)? Analisis bagaimana invarian pembersihan dari kedua ujung (*eviction from back* vs *invalidation from front*) bekerja secara simultan untuk menjaga integritas jendela geser (*sliding window*).

### Soal 1.4: Precedence, Associativity, dan Monotonic Invariant pada Parsing
Dalam algoritma *Shunting-Yard* (Dijkstra) untuk konversi Infix ke Postfix (Reverse Polish Notation), stack operator bertindak sebagai struktur monotonik tersamar (*pseudo-monotonic stack*). Bagaimana tingkat preseden (*precedence*) dan arah asosiatif (*left-to-right* vs *right-to-left*) operator diatur oleh mekanisme *pop-push invariant* pada operator stack tersebut?

### Soal 1.5: Nearest Extreme vs Global Dynamic Extreme
Jelaskan batasan fundamental mengapa struktur *monotonic stack* standar ideal untuk mencari *Nearest Greater/Smaller Element*, tetapi gagal jika digunakan untuk menjawab *Range Minimum/Maximum Queries* (RMQ) dinamis dengan rentang indeks yang arbitrer $[L, R]$. Struktur data apa yang menjadi penerus alamiahnya ketika batasan statis ini dilanggar?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Sentinel Insertion & Duplicate Handling pada Histogram Area
Pada persoalan *Largest Rectangle in Histogram*, kegagalan menangani elemen bernilai sama (*duplicate heights*) atau elemen terakhir dapat merusak batas ekspansi horizontal.
1. Mengapa teknik penambahan elemen artifisial (*sentinel/dummy zero-height nodes*) di awal dan akhir array dapat mengeliminasi *edge-case handling* pasca-iterasi?
2. Bagaimana representasi width $(i - \text{stack.top()} - 1)$ tetap valid secara matematis ketika elemen dengan nilai tinggi yang sama masuk ke dalam stack?

### Soal 2.2: Memory Hierarchy & Layout Overhead: `std::vector` vs Linked-List Stack
Banyak developer mengasumsikan implementasi stack menggunakan *doubly/singly linked list* (`std::list`) lebih superior dibanding dynamic array (`std::vector` / `ArrayList`) karena `push`/`pop` dijamin $O(1)$ *worst-case* tanpa biaya *dynamic resizing*. 
Analisis mengapa pada arsitektur CPU modern x86-64, implementasi stack berbasis linked list memiliki performa *throughput* yang jauh lebih buruk dibandingkan dynamic array pada pemrosesan monotonic stack masif (misal: $10^7$ elemen), ditinjau dari *L1/L2 cache lines*, *pointer chasing*, dan *TLB (Translation Lookaside Buffer) misses*.

### Soal 2.3: Stale Reference Memory Leak pada Window Streaming Deque
Perhatikan skenario implementasi *Sliding Window Maximum* untuk *infinite data stream*. Jika sebuah Monotonic Deque menyimpan objek atau pasangan `(Value, Timestamp)`, apa kelemahan fatal implementasi tersebut terhadap efisiensi memori jangka panjang jika dibandingkan dengan hanya menyimpan `Index` saja? Bagaimana Anda mencegah kondisi *stale reference* tanpa memicu dereferensi memori yang telah di-*evict*?

### Soal 2.4: Eliminasi Rekursi: Simulating Call Stack & Program Counter
Banyak algoritma traversal (misal: AST parsing atau Tree DFS) menghadapi risiko *Call Stack Overflow* saat memproses input degenerate (*deeply nested structure* berkedalaman $> 100.000$). 
Jelaskan secara mendalam bagaimana Anda mentransformasikan fungsi rekursif multi-cabang menjadi fungsi iteratif berbasis *explicit heap-allocated stack*. Data apa saja yang wajib disimpan dalam setiap *synthetic stack frame* untuk merepresentasikan State Machine dan Program Counter (PC) resume address?

### Soal 2.5: The Rainwater Trapping Duality
Persoalan *Trapping Rain Water* dapat diselesaikan menggunakan dua pendekatan berbeda:
1. *Monotonic Decreasing Stack* (evaluasi horizontal lapis demi lapis / bounded by left and right wall).
2. *Two-Pointer Dynamic Envelope* (evaluasi vertikal kolom demi kolom berdasarkan `min(max_left, max_right)`).
Bandingkan mekanika internal kedua metode tersebut. Pada skenario pola aliran data seperti apa Monotonic Stack lebih unggul, dan dalam skenario apa Two-Pointer lebih efisien dalam memori dan branch prediction?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike pada Real-Time Financial Limit Order Book (Scale/Bottleneck)
Sebuah sistem High-Frequency Trading (HFT) mengeksekusi analisis *Time-to-Execution* pada feed order book. Setiap detik, sistem memproses 500.000 order ticks dan menggunakan Monotonic Stack untuk melacak *Next Favorable Price Execution Event*. 

Pada kondisi pasar normal, latensi per tick berada pada p99 < 800 nanodetik. Namun, saat terjadi *market crash* (volatilitas ekstrem di mana harga anjlok drastis dan ribuan order baru masuk di level harga yang semakin rendah secara monotonik), latensi p99 melonjak hingga 45 milidetik, menyebabkan order execution tertunda dan kerugian finansial.

```
Normal Market:      [100, 102, 101, 103, 102, 104] -> Stack pops seimbang (~1-2 per event)
Crash Event:        [100, 99, 98, 97, 96, ..., 10]  -> Stack membesar tanpa batas
Correction Event:   [11] -> Memicu cascade pop masif terhadap 100.000 elemen sekaligus
```

**Pertanyaan Diagnostik:**
1. Mengapa karakteristik beban kerja *Crash-then-Correction* melanggar asumsi optimasi *average amortized time* pada arsitektur sistem real-time?
2. Bagaimana Anda mendesain ulang ingestion engine tersebut menggunakan teknik *bounded processing window*, *pre-allocated cyclic buffer*, atau *incremental popping* agar *worst-case latency* per-tick dapat dibatasi secara deterministik tanpa kehilangan akurasi analitik?

---

### Skenario B: Race Condition dan State Corruption pada Distributed Monotonic Aggregator (Concurrency)
Sebuah cluster pemrosesan log terdistribusi (16 worker nodes) menerima *metric event stream* (CPU utilization ticks) yang dikirim melalui Kafka. Karena partisi jaringan dan jitter, event dapat tiba sedikit tidak berurutan (*out-of-order within 2 seconds threshold*). 

Tim data engineering membangun *Stateful Streaming Worker* yang memelihara Monotonic Deque lokal per-mesin untuk mendeteksi *Sustained Spikes* (Sliding Window Maximum over 60 seconds). Untuk meningkatkan throughput, mereka mengimplementasikan konkurensi di mana Thread Ingestion memasukkan data ke Deque sementara Thread Eviction (Scheduler) membersihkan event kedaluwarsa secara asinkron.

Pasca deployment, metrik agregasi sering kali melaporkan nilai `NaN`, mendadak mengalami *deadlock*, atau melewatkan spike ekstrem yang terekam di log mentah.

**Pertanyaan Diagnostik:**
1. Identifikasi *race condition* dan *invalidation hazard* yang terjadi ketika Thread Ingestion melakukan *back-truncation* (membuang elemen dari ekor Deque yang lebih kecil dari elemen baru) sementara Thread Eviction melakukan *front-popping* (membuang elemen yang kedaluwarsa dari kepala Deque) tanpa koordinasi memori yang tepat.
2. Rancang arsitektur konkurensi yang aman (*thread-safe* atau *lock-free single-producer single-consumer*) yang menjamin integritas kondisi monotonik deque meskipun data tiba *out-of-order* dalam toleransi window tertentu.

---

### Skenario C: Sandboxed Dynamic Expression Parsing Engine (Architecture & Trade-offs)
Platform SaaS perbankan menyediakan fitur di mana pengguna korporat dapat mendefinisikan formula kalkulasi pajak dan bunga kustom berbasis teks, contoh:
`MAX(tax_rate * 1.15, BASE_FEE + (threshold ^ 2) / (total - discount))`

Engine kalkulasi ini dieksekusi di dalam container backend (Node.js/Go microservice). Implementasi awal menggunakan compiler berbasis AST rekursif standar. Namun, saat tim sekuritas melakukan penetration testing, mereka mengirim payload formula berukuran 50 KB yang berisi ekspresi tanda kurung bertingkat sangat dalam:
`((((((...(1 + 1)...))))))` (10.000 tingkat kurung buka-tutup).

Akibatnya, microservice mengalami fatal crash (*Segment Violation / Unrecoverable Call Stack Overflow*), melumpuhkan node worker seketika (*Denial of Service*).

**Pertanyaan Diagnostik:**
1. Mengapa validasi panjang teks input (*input length limitation*) saja tidak cukup untuk memitigasi serangan ini secara arsitektural?
2. Rancang arsitektur *Sandboxed Expression Evaluator* berbasis Stack Execution Engine (menggunakan variasi Shunting-Yard dan RPN Evaluator) yang aman. Komponen apa yang harus membatasi kedalaman evaluasi (*depth budget*), memori heap (*allocation cap*), dan siklus CPU (*step counter*) secara deterministik sebelum eksekusi dimulai?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Real-Time Volatility Surge Detector (Sliding Window Monotonic Engine)

#### Problem Description
Di bursa kripto/saham, deteksi lonjakan volatilitas harga (*volatility surge*) dalam jendela waktu geser (*sliding window*) adalah komponen krusial dari *circuit breaker*. Anda diminta membangun modul inti (*core algorithmic engine*) bernama `VolatilitySurgeDetector` yang memproses stream data harga tick-by-tick secara *in-memory*.

Sistem harus mampu melacak selisih antara nilai tertinggi (*Max Price*) dan nilai terendah (*Min Price*) dalam jendela waktu $W$ detik terakhir ($Spread = Max - Min$). Jika $Spread > Threshold$, sebuah alarm harus dipicu seketika (*zero-latency alert*).

#### Technical Requirements
1. **Algorithmic Constraints:**
   - Operasi `processTick(timestamp, price)` harus memiliki kompleksitas waktu **$O(1)$ amortized** dan **$O(1)$ space overhead per tick** (tidak boleh menduplikasi array mentah).
   - Window berbasis waktu (*time-based sliding window*), bukan berbasis jumlah tick statis ($N$). Elemen kedaluwarsa jika $tick.timestamp < current\_timestamp - W$.
2. **Zero Dynamic Allocation (Hot Path):**
   - Engine tidak boleh melakukan alokasi memori dinamis (`malloc`, `new`, dynamic array resizing) selama pemrosesan tick berlangsung. Seluruh struktur internal harus berbasis *fixed-capacity pre-allocated circular buffer*.
3. **Dual Monotonic Structures:**
   - Gunakan satu *Monotonic Decreasing Deque* untuk melacak Maximum Price.
   - Gunakan satu *Monotonic Increasing Deque* untuk melacak Minimum Price.
4. **Out-of-Order Grace Handling:**
   - Asumsikan timestamp monotonik meningkat secara lokal, namun engine harus membuang tick dengan timestamp masa lalu ($t < t_{latest}$) secara elegan tanpa merusak struktur deque.

#### API Contract & Specifications
Implementasikan modul dalam bahasa pilihan Anda (C++20, Rust, Go, atau Java) mengikuti blueprint berikut (contoh pseudocode/C++ signature):

```cpp
template <size_t MaxCapacity>
class VolatilitySurgeDetector {
public:
    // WindowSize dalam milidetik, maxSpreadThreshold adalah batas pemicu alarm
    VolatilitySurgeDetector(uint64_t windowSizeMs, double maxSpreadThreshold);

    struct SurgeAlert {
        bool triggered;
        double currentSpread;
        double maxPrice;
        double minPrice;
        uint64_t timestamp;
    };

    // Dipanggil setiap ada tick masuk
    SurgeAlert processTick(uint64_t timestampMs, double price);

    // Query status terkini tanpa memajukan timestamp
    double getCurrentSpread() const;
};
```

#### Constraints
- $MaxCapacity \le 1.000.000$ data points dalam pre-allocated memory.
- $W$ (Window Size): $1000 \text{ ms} \le W \le 86.400.000 \text{ ms}$ (1 detik hingga 24 jam).
- Throughput target: Minimal $5.000.000 \text{ ticks/second}$ pada single core core i7/modern Xeon.
- Space Complexity: $O(MaxCapacity)$ statis, $O(1)$ runtime dynamic heap allocation.

#### Expected Output Test Cases
```text
WindowSize: 5000 ms (5 detik), Threshold: 15.0

Tick 1: Time=1000, Price=100.0 -> Min=100.0, Max=100.0, Spread=0.0   (Alert: false)
Tick 2: Time=2000, Price=110.0 -> Min=100.0, Max=110.0, Spread=10.0  (Alert: false)
Tick 3: Time=3000, Price=98.0  -> Min=98.0,  Max=110.0, Spread=12.0  (Alert: false)
Tick 4: Time=4000, Price=114.0 -> Min=98.0,  Max=114.0, Spread=16.0  (Alert: true! Spread 16.0 > 15.0)
Tick 5: Time=7500, Price=105.0 -> Window aktif: [2500 - 7500]. Tick 1 & 2 kedaluwarsa!
                                   Min=98.0,  Max=114.0, Spread=16.0  (Alert: true)
Tick 6: Time=9500, Price=102.0 -> Window aktif: [4500 - 9500]. Tick 3 & 4 kedaluwarsa!
                                   Min=102.0, Max=105.0, Spread=3.0   (Alert: false)
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis sebelum melangkah ke topik struktur data tingkat lanjut berikutnya.

### Saya harus memahami:
- [ ] Bukti matematis mengapa Monotonic Stack dan Deque memiliki kompleksitas waktu amortisasi $O(N)$ meskipun terdapat `while` loop di dalam iterasi.
- [ ] Perbedaan invarian antara Monotonic Increasing (elemen naik ke atas stack, pop saat nilai baru lebih kecil) dan Monotonic Decreasing (elemen turun, pop saat nilai baru lebih besar).
- [ ] Kapan harus menyimpan `Value` vs `Index` pada stack/deque (aturan praktis: simpan `Index` jika memerlukan perhitungan jarak horizontal atau validasi kedaluwarsa window).
- [ ] Mekanisme pembersihan ganda pada Sliding Window Deque: pembersihan elemen usang dari *Front* (berdasarkan indeks/waktu) dan pembersihan elemen sub-optimal dari *Back* (berdasarkan invarian nilai).
- [ ] Cara kerja Shunting-Yard Algorithm dan bagaimana preseden operator dipertahankan oleh stack operator sebelum dieksekusi ke output queue.
- [ ] Mengapa algoritma rekursif yang dalam (*deep recursion*) berbahaya di lingkungan produksi dan bagaimana merekayasa explicit stack di heap untuk mencegah OS call stack overflow.
- [ ] Dampak layout memori kontigu (`std::vector`) terhadap efisiensi CPU cache line dibandingkan implementasi stack berbasis linked-node.

### Saya tidak perlu menghafal:
- [ ] Template kode untuk setiap variasi LeetCode (misal: menghafal baris per baris kode *Largest Rectangle in Histogram* tanpa memahami invarian batas kiri dan kanan).
- [ ] Tabel preseden lengkap seluruh operator bahasa C++/Java di luar operator aritmatika dan logika dasar (operator precedence table selalu dapat dirujuk melalui dokumentasi bahasa).
- [ ] Trik sintaksis mikroskopis bahasa pemrograman tertentu untuk memanipulasi pointer stack, selama memahami model memori fundamentalnya.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi secara instan apakah sebuah problem memerlukan Monotonic Stack (kata kunci: *Next Greater Element*, *Previous Smaller Element*, *Span*, *Histogram Boundary*, *Subarray Minimums Sum*).
- [ ] Mengimplementasikan *Monotonic Deque* dari nol (*from scratch*) menggunakan pre-allocated circular ring buffer tanpa bergantung pada library built-in (`std::deque` / `ArrayDeque`).
- [ ] Mentransformasikan kode DFS rekursif kompleks menjadi bentuk iteratif berbasis explicit stack frame dengan menyimpan state lokal secara manual.
- [ ] Menganalisis *edge case* nilai duplikat pada monotonic stack dan memutuskan secara tepat apakah operator pembanding harus menggunakan `<` versus `<=`.
- [ ] Melakukan profiling dan debugging pada sistem berbasis stack yang mengalami *worst-case latency spikes* akibat akumulasi operasi pop yang tertunda (*cascading eviction*).