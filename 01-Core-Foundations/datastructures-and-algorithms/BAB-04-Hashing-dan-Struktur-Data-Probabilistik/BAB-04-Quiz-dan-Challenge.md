# BAB 04: Quiz, Challenge, & Knowledge Check
**Bab 04: Stacks, Queues, Ring Buffers, dan Monotonic Data Structures**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Spatial Locality & Memory Layout:**
   Bandingkan implementasi Stack menggunakan Dynamic Array (vektor) dengan Doubly Linked List. Analisislah perbedaan keduanya dari sudut pandang *CPU L1/L2 cache prefetching*, fragmentasi memori heap, dan amortisasi alokasi memori saat elemen bertumbuh dari $N$ ke $2N$.

2. **Ring Buffer Mathematics & Bitwise Optimization:**
   Pada implementasi Circular Queue (Ring Buffer), operasi modular `(tail + 1) % capacity` sering digantikan dengan operasi bitwise AND `(tail + 1) & (capacity - 1)`. Buktikan kondisi matematis apa yang wajib dipenuhi oleh variabel `capacity` agar optimasi bitwise ini valid, dan jelaskan mengapa CPU memproses instruksi bitwise jauh lebih cepat daripada instruksi modulo/pembagian integer.

3. **Invarian Monotonic Stack:**
   Definisikan apa itu *Strictly Monotonically Decreasing Stack*. Jelaskan bagaimana cara kerja invarian tersebut dalam menyelesaikan masalah *Next Greater Element* secara amortized $O(N)$, padahal terdapat loop di dalam loop (`while` di dalam `for`).

4. **Two-Stack Queue Latency Trade-Off:**
   Queue dapat disimulasikan menggunakan dua Stack ($S_{in}$ dan $S_{out}$). Buktikan bahwa kompleksitas waktu teramortisasi (*amortized cost*) per operasi adalah $O(1)$. Mengapa struktur data ini berisiko jika diimplementasikan pada sistem *Hard Real-Time* dengan SLA ketat per transaksi, meskipun rata-rata performanya optimal?

5. **Call Stack vs Heap-Allocated Data Structure:**
   Jelaskan secara struktural perbedaan antara Call Stack pada level arsitektur komputer (Activation Record/Stack Frame, register ESP/EBP) dengan struktur data Stack abstrak yang dialokasikan pada memory heap. Mengapa rekursi yang terlalu dalam memicu `StackOverflowError` level OS/runtime, sedangkan Stack berbasis heap memicu `OutOfMemoryError`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Ring Buffer Ambiguity: Full vs Empty State:**
   Pada Ring Buffer berbasis array datar berukuran $N$ dengan pointer `head` dan `tail`, kondisi `head == tail` dapat merepresentasikan buffer yang **kosong sempurna** atau **penuh sempurna**. Rancang dan jelaskan dua pendekatan arsitektural berbeda untuk mendisambiguasi kedua kondisi ini tanpa menggunakan *atomic counter* tambahan!

2. **False Sharing pada Lock-Free SPSC Queue:**
   Diberikan struktur C++ berikut untuk Single-Producer Single-Consumer (SPSC) Queue:
   ```cpp
   template <typename T, size_t Cap>
   struct SPSCQueue {
       T buffer[Cap];
       std::atomic<size_t> head{0};
       std::atomic<size_t> tail{0};
   };
   ```
   Jelaskan mengapa kode di atas mengalami degradasi *throughput* drastis pada CPU multi-core modern akibat *False Sharing* pada protokol MESI cache coherence, dan tuliskan perbaikan strukturalnya.

3. **Memory Loitering/Leak pada Array-Based Queue:**
   Pada bahasa dengan Garbage Collector (seperti Go, Java, atau Node.js), sebuah custom bounded queue menggunakan array internal `items[capacity]`. Ketika operasi `dequeue()` hanya menggeser pointer `head = (head + 1) % capacity` tanpa mengosongkan referensi lama (`items[old_head] = null`), jelaskan dampak teknisnya terhadap siklus hidup objek di Young/Old Generation GC.

4. **Monotonic Deque Purging Logic:**
   Pada algoritma *Sliding Window Maximum* dengan window ukuran $K$, elemen kadaluwarsa harus dibersihkan dari *Monotonic Deque*. Mengapa kita hanya perlu membandingkan indeks elemen di posisi *front* deque dengan batas kiri window ($i - K$), dan mengapa elemen-elemen di tengah atau belakang deque dijamin tidak melanggar batas sliding window tersebut?

5. **Cache Thrashing: ArrayDeque vs LinkedList:**
   Dalam benchmark performa antrean FIFO intensif di runtime modern, `ArrayDeque` hampir secara konsisten mengalahkan `LinkedList` hingga 5–10x lipat dalam throughput, meskipun `LinkedList` memiliki kompleksitas teoretis murni $O(1)$ untuk `enqueue` dan `dequeue` tanpa alokasi resize. Bedah faktor *pointer chasing*, *memory overhead per node*, dan *cache line invalidation* yang menyebabkan disparitas performa ini.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Thread Pool Unbounded Queue Exhaustion (Out-of-Memory)
Sebuah payment gateway memproses puncak lonjakan transaksi *flash sale* (50.000 req/detik). Backend worker pool menggunakan Queue untuk menampung HTTP tasks sebelum dieksekusi oleh thread pekerja. 

Tim backend menggunakan konfigurasi bawaan `LinkedBlockingQueue` tanpa batas kapasitas (*unbounded*). Tiba-tiba database downstream mengalami latensi tinggi (respons melambat dari 20ms ke 2.500ms). Dalam hitungan detik, seluruh pod aplikasi mengalami restart bertubi-tubi akibat Kubernetes `OOMKilled` (Exit Code 137).
* **Pertanyaan Diagnostik:**
  1. Analisis cascading failure yang terjadi: mengapa unbounded queue menjadi antipattern mematikan dalam skenario *backpressure* ini?
  2. Jika queue diubah menjadi *Bounded Queue* (misal kapasitas 10.000 elemen), sebutkan dan evaluasi minimal 3 strategi mitigasi saat queue penuh (*Rejection Policies*: Drop, Caller-Runs, Dead-Letter Queue) dari sudut pandang integritas data transaksi perbankan.

### Skenario B: Race Condition & Reordering pada Ring Buffer Audio Streaming
Sebuah driver audio real-time memindahkan buffer PCM dari capture thread (Producer) ke network thread (Consumer) menggunakan Ring Buffer lock-free di arsitektur CPU ARM64. 

Pada pengujian internal di mesin Intel x86, sistem berjalan sempurna tanpa glitch. Namun, saat dideploy ke perangkat edge berbasis ARM64 (misal: Raspberry Pi / Apple Silicon), audio mengalami distorsi suara acak (*popping/crackling*) dan data korup meskipun pointer `head` dan `tail` tidak pernah melewati batas kapasitas.
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah perbedaan model memori (*Memory Consistency Model*) antara arsitektur Intel x86 (*Total Store Order - TSO*) dan ARM64 (*Weakly Ordered Memory*).
  2. Tunjukkan baris instruksi konseptual di mana compiler/hardware reordering merusak urutan penulisan payload vs update pointer `tail`, dan bagaimana menerapkan *Memory Barrier* (Acquire-Release Semantics) untuk memperbaikinya secara portabel.

### Skenario C: Sliding Window Latency Spike pada Real-Time Risk Engine
Sebuah High-Frequency Trading (HFT) risk management engine memproses aliran order book untuk menghitung metrik volatilitas: *"Mencari harga transaksi tertinggi dalam rentang 1 detik terakhir"* dengan throughput 500.000 event/detik. 

Implementasi awal menggunakan *Self-Balancing Binary Search Tree* (Red-Black Tree / `std::multiset`) untuk menyimpan harga dalam window 1 detik agar root/ujung kanan selalu bernilai maksimum. Pada saat order book bergerak liar, engine mengalami *latency spike* hingga melanggar batas SLA sub-milidetik.
* **Pertanyaan Diagnostik:**
  1. Mengapa struktur Balanced BST menghasilkan kompleksitas $O(\log K)$ yang memicu jitter performa tinggi akibat balancing/pointer rotations di volume data masif?
  2. Rekonstruksi solusi sistem tersebut menggunakan **Monotonic Deque**: jelaskan struktur data baru, invariant yang dijaga, dan buktikan bagaimana kompleksitasnya terpangkas menjadi $O(1)$ amortized per incoming trade tick.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Zero-Allocation Bounded SPSC Ring Buffer
Implementasikan sebuah struktur data antrean melingkar berbasis Single-Producer Single-Consumer (SPSC) yang dirancang untuk performa ultra-low-latency dalam bahasa pemrograman berorientasi performa (Rust, C++, Go, atau Java dengan unsafe/off-heap).

#### Requirements:
1. **Zero Allocation in Steady State:** Seluruh memori buffer dialokasikan saat inisialisasi (`Init(capacity)`). Operasi `Enqueue` dan `Dequeue` dilarang keras melakukan alokasi memori heap baru.
2. **Lock-Free Concurrency:** Tidak boleh menggunakan `mutex`, `semaphore`, synchronized lock, atau blocking kernel call lainnya. Sinkronisasi thread produsen dan konsumen hanya boleh menggunakan atomics.
3. **Cache-Line Alignment:** Variabel state `head` dan `tail` harus diproteksi dari *false sharing* dengan cache-line padding (misal: `alignas(64)` atau padding 64/128-byte).
4. **Power-of-Two Masking:** Kapasitas buffer harus otomatis di-bulatkan ke bilangan pangkat dua terdekat ($2^N$), dan operasi modulo harus diimplementasikan via bitwise AND mask.
5. **Memory Ordering Semantics:** Wajib menggunakan *Acquire-Release memory order* (jangan default ke *Sequential Consistency* yang lebih lambat, dan jangan menggunakan *Relaxed* yang membahayakan data races).

#### Constraints:
* **Throughput Target:** Minimal $\ge 20.000.000$ operasi enqueue-dequeue per detik pada mesin modern.
* **Storage Footprint:** Array berkapasitas tetap. Jika buffer penuh, `Enqueue` mengembalikan status `false` (Drop/Retry), dilarang melakukan block thread.

#### Expected Output:
* Kode implementasi modul lengkap (struktur data, enqueue, dequeue).
* Unit test atau benchmark code yang mendemonstrasikan Producer thread dan Consumer thread berkomunikasi secara konkuren tanpa kehilangan atau merusak 1 elemen pun dari total 10 juta bilangan integer yang dialirkan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara abstraksi antrean (Queue/Stack) dan struktur fisik memori (Array Contiguous vs Linked Nodes).
- [ ] Mekanisme matematika modular arithmetic pada Circular Buffer dan optimasi bitwise mask `(capacity - 1)`.
- [ ] Dampak arsitektur hardware terhadap antrean konkuren: Cache Lines (64-byte), Cache Coherence Protocols (MESI), dan mitigasi *False Sharing*.
- [ ] Mekanisme invariant pembersihan elemen pada Monotonic Stack dan Monotonic Deque.
- [ ] Perbedaan model memori koncurrency: Relaxed, Acquire-Release, dan Sequentially Consistent memory ordering dalam antrean multithreaded.
- [ ] Karakteristik *backpressure* dan bahaya fatal dari *unbounded queue* pada arsitektur microservices/backend pipelining.

### Saya tidak perlu menghafal:
- [ ] Sintaks mikro pustaka eksternal (misal: konfigurasi mendalam LMAX Disruptor atau Java Disruptor DSL).
- [ ] Bukti matematis formal mekanika kuantum semikonduktor CPU; cukup pahami konsekuensi logis instruksi mesin terhadap L1/L2 cache.
- [ ] Detail implementasi spesifik arsitektur assembly (cukup memahami abstraksi C++11/Rust atomic operations).

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan Ring Buffer yang thread-safe untuk skenario SPSC tanpa menggunakan OS mutex lock.
- [ ] Memecahkan masalah optimasi sliding window bernilai ekstrem (Min/Max) menggunakan Monotonic Deque dalam kompleksitas $O(N)$ waktu linear.
- [ ] Mendiagnosis dan memperbaiki bug *memory leak* (*loitering references*) pada custom data structure berbasis array di platform bermemori terkelola (GC).
- [ ] Mengonfigurasi thread pool executor dengan bounded queue dan strategi *rejection policy* yang tepat sesuai karakteristik sistem (Financial vs Non-critical telemetry).