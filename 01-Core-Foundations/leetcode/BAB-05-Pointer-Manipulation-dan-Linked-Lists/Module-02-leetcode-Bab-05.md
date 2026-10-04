# BAB 05: Materi Lanjutan
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Algorithmic Foundations to Production Systems)

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta mampu:
1. **Mentransformasikan** algoritma abstrak bertaraf *LeetCode Hard* (seperti *Sliding Window Quantiles*, *Monotonic Data Structures*, dan *Topological Event Pipelines*) menjadi komponen perangkat lunak *production-ready* dengan latensi deterministik sub-milidetik.
2. **Menganalisis dan Memitigasi** *impedance mismatch* antara analisis asimtotik teoritis ($\mathcal{O}$-notation) dengan karakteristik perangkat keras modern (seperti *CPU cache locality*, *branch misprediction*, *false sharing*, dan *garbage collection thrashing*).
3. **Mendesain dan Mengimplementasikan** struktur data berkinerja tinggi (*concurrent*, *zero-allocation*, atau *lock-free*) untuk pemrosesan *stream* data bervolume jutaan operasi per detik (ops/sec).
4. **Mengevaluasi *Trade-off*** struktural antara efisiensi memori, skalabilitas konkurensi, kompleksitas pemeliharaan kode, dan kestabilan latensi (*P99/P99.9 jitter*).

---

### 2. Prerequisite

Sebelum mendalami modul ini, peserta wajib memahami:
* **Analisis Algoritma Lanjutan:** *Amortized analysis*, *master theorem*, *recurrence relations*, serta algoritma berbasis *Heaps*, *Segment Trees*, *Disjoint-Set Union (DSU)*, dan *Dynamic Programming*.
* **Sistem Komputer & Arsitektur Mesin:** Hirarki memori (L1/L2/L3 Cache, RAM, NUMA), *cache line size* (64 byte), *false sharing*, serta model konkurensi memori (*sequential consistency*, *acquire-release semantics*).
* **Pemrograman Konkuren & Sistem:** Kemahiran dalam bahasa berkinerja tinggi (Go, C++, atau Rust). Modul ini menggunakan **Go** dengan memanfaatkan idiom konkurensi tingkat lanjut (`sync`, `sync/atomic`, *unsafe memory patterns* bila diperlukan).
* **Observabilitas & Profiling:** Memahami penggunaan profiler sistem (seperti `pprof`, `perf`, *trace tooling*).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi algoritma di platform seperti LeetCode sering kali mengabaikan kendala perangkat keras dunia nyata. Dalam lingkungan produksi skala *enterprise*, faktor-faktor berikut menentukan performa aktual:

#### A. The Mechanical Sympathy of Algorithms
Dalam kalkulasi $\mathcal{O}(N \log N)$ menggunakan pohon biner seimbang (seperti Red-Black Tree atau AVL Tree pada `std::map` atau Java `TreeMap`), setiap traversal *node* merepresentasikan sebuah *pointer indirection*. Pada memori fisik, *pointer indirection* menyebabkan *cache miss* dengan latensi akses $\sim 50\text{–}100\text{ ns}$ (RAM) dibandingkan $\sim 1\text{ ns}$ (L1 Cache).

```
Traditional Node-based Tree:
[Node A] ---> (Pointer 0x10A0) ---> [Node B] ---> (Pointer 0x90F0) ---> [Node C]
(Setiap lompatan memicu L1/L2/L3 Cache Miss jika alokasi acak di heap)

Array-backed / Flat Memory (Cache-line Friendly):
[ Node A | Node B | Node C | Node D | Node E | Node F | Node G ]
|-------- 64-byte Cache Line --------| (Ditarik sekaligus ke L1 Cache)
```

Sebuah algoritma dengan kompleksitas teoritis lebih tinggi seperti $\mathcal{O}(N)$ pada *flat array* sering kali mengungguli algoritma $\mathcal{O}(\log N)$ berbasis *linked structure* jika ukuran dataset berada dalam batas ratusan elemen karena efisiensi *CPU prefetcher* dan vektorisasi SIMD.

#### B. Sliding Window & Streaming Quantiles Architecture
Salah satu pola klasik LeetCode adalah **Sliding Window Median (LeetCode 480)** atau **Sliding Window Maximum (LeetCode 239)**. Pada level produksi (misal: sistem monitoring Service Level Objective [SLO], *real-time dynamic rate-limiting*, dan deteksi anomali finansial), kita harus menghitung metrik seperti *Moving P99 Latency* atau *Rolling Moving Median* pada jendela geser waktu (misal: 60 detik terakhir) dengan jutaan metrik masuk setiap detiknya.

Implementasi standar dua *heap* (Max-Heap dan Min-Heap) dengan penghapusan malas (*lazy deletion* menggunakan hash map) memiliki kelemahan kritis:
1. **Alokasi Heap yang Masif:** Objek yang dihapus tetap tinggal di heap hingga puncak heap dieksekusi, menyebabkan kebocoran memori virtual terikat waktu (*temporary bloat*).
2. **Lock Contention:** Sinkronisasi multi-thread pada operasi mutasi heap global menjadi *bottleneck* skalar utama (*Amdahl's Law*).
3. **Rekonsiliasi Elemen Usang:** *Garbage collector* (GC) dipaksa memindai jutaan entri yang sudah tidak relevan.

Solusi arsitektur produksi menggunakan kombinasi **Ring Buffer berukuran tetap**, **SkipList / Segment Tree berbasis array**, dan pengindeksan waktu bucket (*Bucketed Sliding Windows*) untuk mencapai kompleksitas ruang $\mathcal{O}(K)$ yang konstan tanpa alokasi baru saat *runtime* (nol alokasi per transaksi).

---

### 4. Why & What

| Dimensi | Kode Algoritma Murni (LeetCode Context) | Arsitektur Algoritma Produksi (Enterprise Grade) |
| :--- | :--- | :--- |
| **Alokasi Memori** | Mengabaikan alokasi; `new`, pointer dinamis, dan auto-boxing digunakan bebas. | Meminimalkan atau mencapai *Zero-Allocation* di *critical path*; memori dialokasikan di awal (*pre-allocated/pooled*). |
| **Karakteristik Latensi** | Mengukur *execution time* total tunggal dari awal hingga akhir. | Fokus pada distribusi latensi: *Median*, P95, P99, P99.9, dan eliminasi *tail latency* (jitter). |
| **Model Eksekusi** | Single-threaded, *deterministic sequential inputs*. | Multi-core, konkuren, data berpotensi *out-of-order*, penanganan *backpressure*. |
| **Ketahanan Kegagalan** | Mengasumsikan masukan valid dan memori tidak terbatas. | Validasi defensif, proteksi kehabisan memori (OOM), mitigasi degradasi anggun (*graceful degradation*). |
| **Observabilitas** | `print()` atau *return values* terisolasi. | Metrik internal (Prometheus), pelacakan terdistribusi (*distributed tracing*), dan *debug counters*. |

---

### 5. How (Workflow Detail)

Workflow integrasi algoritma mutakhir ke dalam *data stream engine*:

```
[Ingestion Pipeline: Network I/O]
           │
           ▼
[Lock-Free / Ring Buffer Ingestion (LMAX Disruptor Pattern)]
           │  (Zero-Copy Data Transfer)
           ▼
[Window Partitioning & Bucket Mapping via Modular Arithmetic]
           │
           ├─── Element Masuk: Tambahkan ke Data Structure Terindeks
           │    (Update Fenwick/Segment Tree atau Balanced Structure)
           │
           └─── Element Usang (T - WindowSize): Hapus dari Struktur
                (Deterministic Eviction, Tidak Ada Heap Bloat)
           │
           ▼
[Real-Time State Query (P50, P90, P99, Max, Anomaly Score)]
           │  (Latensi Sub-mikrodetik)
           ▼
[Decision Engine: Rate Limiter / Circuit Breaker / Order Dispatch]
```

1. **Ingestion & Buffering:** Metrik atau event masuk melalui buffer antrean sirkular (*ring buffer*) berbasis array datar untuk menjaga integritas data dalam memori kontigu.
2. **Time-Partitioned State Maintenance:** Data dikelompokkan ke dalam granularitas waktu (misal: *tick* 100 ms). Eviksi data usang dilakukan secara *batch* atau bertahap tanpa rekursi dalam traversal memori.
3. **Zero-Allocation Upgrades:** Seluruh *node* atau entri didaur ulang (*object pooling*) atau dialokasikan dalam *arena memory block* tunggal saat inisialisasi aplikasi.
4. **Concurrent Access Coordination:** Memisahkan *thread* penulisan tunggal (*single-writer principle*) atau menggunakan mekanisme atomik (*atomic fetch-and-add*) untuk menghindari *lock contention* antar *worker threads*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Manual vs. Logistik Gudang Otomatis
* **LeetCode Standar (Dual-Heap Lazy Deletion):** Seperti perpustakaan di mana setiap buku yang dipinjam tidak langsung dikeluarkan dari katalog. Petugas menandai di secarik kertas catatan terpisah bahwa buku tersebut sudah dipinjam. Saat seseorang meminta buku teratas, petugas memeriksa catatan. Jika ternyata sudah dipinjam, buku tersebut dibuang, lalu petugas mengambil buku berikutnya. Jika banyak buku kadaluarsa menumpuk, meja petugas penuh sesak dengan tumpukan buku yang sebenarnya sudah tidak ada.
* **Arsitektur Produksi (Direct-Indexed Bounded Window):** Seperti sabuk konveyor otomatis di pabrik modern. Setiap kompartemen sabuk memiliki slot nomor urut tetap. Ketika barang berumur lebih dari 60 detik mencapai ujung sabuk, barang tersebut otomatis jatuh ke wadah daur ulang tanpa ada pengecekan manual, dan instrumen sensor selalu membaca isi slot aktif dalam waktu $\mathcal{O}(1)$ secara konstan.

```
       Dual-Heap dengan Lazy Deletion (Bloat & Pointer Chasing)
       ┌────────────────────────────────────────────────────────┐
       │ Min-Heap: [P1] -> [P2] -> [P3]  (Banyak pointer lepas)  │
       │ Map "Dihapus": {P2: true}                              │
       │ Saat Root == P2 -> Polling berulang kali -> Boros CPU  │
       └────────────────────────────────────────────────────────┘

       Production Architecture: Indexed Sliding Window (Ring Buffer)
       ┌───┬───┬───┬───┬───┬───┬───┬───┐
       │ 0 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │  <- Flat Memory (Contiguous Slice)
       └───┴───┴───┴───┴───┴───┴───┴───┘
         ▲                   ▲
         │ (Tail: Eviction)  │ (Head: Ingestion)
         └─────── Delta Waktu: WindowSize ───────┘
```

---

### 7. Simple Example & Practical Example

Berikut adalah implementasi sistem berstandar produksi di Go: **High-Throughput Concurrent Sliding Window Quantile Engine (P50/Median & P99)** yang diadaptasi dari problem LeetCode 480 (*Sliding Window Median*), dioptimasi untuk nol alokasi dinamis pada *hot-path* data ingestion, aman terhadap konkurensi, dan memiliki determinisme latensi.

Untuk menjaga efisiensi absolut dan menghindari kompleksitas alokasi dinamis *Self-Balancing Binary Search Tree*, kita menggunakan pendekatan **Bucketized Order-Statistic Vector (Discretized Value-Space)** yang memetakan rentang nilai metrik (misal: Latensi 0–10.000 ms) ke dalam struktur agregasi *Fenwick Tree* (Binary Indexed Tree) yang berada di atas *Ring Buffer*.

```go
package main

import (
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

// FenwickTree (Binary Indexed Tree) untuk pencarian frekuensi kumulatif
// Kompleksitas: Add: O(log M), Query: O(log M), Space: O(M) di mana M adalah rentang nilai diskrit.
type FenwickTree struct {
	tree []int64
	size int
}

func NewFenwickTree(maxVal int) *FenwickTree {
	return &FenwickTree{
		tree: make([]int64, maxVal+2),
		size: maxVal + 1,
	}
}

// Add menambahkan delta ke indeks val (1-based index)
func (f *FenwickTree) Add(val int, delta int64) {
	idx := val + 1 // konversi 0-indexed ke 1-indexed
	for idx <= f.size {
		f.tree[idx] += delta
		idx += idx & (-idx)
	}
}

// PrefixSum mengembalikan akumulasi count dari 0 sampai val
func (f *FenwickTree) PrefixSum(val int) int64 {
	idx := val + 1
	var sum int64
	for idx > 0 {
		sum += f.tree[idx]
		idx -= idx & (-idx)
	}
	return sum
}

// FindKth mengembalikan nilai terkecil dengan prefix sum >= k (Binary Lifting on BIT: O(log M))
func (f *FenwickTree) FindKth(k int64) int {
	var idx int
	// Cari pangkat 2 terbesar yang <= f.size
	var highestPower int = 1
	for (highestPower << 1) <= f.size {
		highestPower <<= 1
	}

	for step := highestPower; step > 0; step >>= 1 {
		nextIdx := idx + step
		if nextIdx <= f.size && f.tree[nextIdx] < k {
			idx = nextIdx
			k -= f.tree[idx]
		}
	}
	return idx // kembali ke 0-indexed representation
}

// SlidingWindowQuantileEngine mengelola data streaming dalam sliding window deterministik
type SlidingWindowQuantileEngine struct {
	mu           sync.RWMutex
	windowSize   int
	maxVal       int
	bufferValues []int     // Ring buffer nilai
	bufferValid  []bool    // Menandakan slot terisi
	bit          *FenwickTree
	head         int
	count        int64
	totalOps     uint64
}

// Config struktur konfigurasi engine
type Config struct {
	WindowCapacity int // Jumlah event maksimal dalam sliding window
	MaxValueRange  int // Nilai integer maksimum yang valid (misal: latensi dalam ms: 10000)
}

func NewSlidingWindowQuantileEngine(cfg Config) (*SlidingWindowQuantileEngine, error) {
	if cfg.WindowCapacity <= 0 || cfg.MaxValueRange <= 0 {
		return nil, errors.New("konfigurasi tidak valid: kapasitas dan range nilai harus > 0")
	}

	return &SlidingWindowQuantileEngine{
		windowSize:   cfg.WindowCapacity,
		maxVal:       cfg.MaxValueRange,
		bufferValues: make([]int, cfg.WindowCapacity),
		bufferValid:  make([]bool, cfg.WindowCapacity),
		bit:          NewFenwickTree(cfg.MaxValueRange),
		head:         0,
		count:        0,
	}, nil
}

// Observe mencatat data point baru secara O(log M). Zero dynamic allocations di path ini.
func (e *SlidingWindowQuantileEngine) Observe(val int) {
	if val < 0 {
		val = 0
	} else if val > e.maxVal {
		val = e.maxVal
	}

	e.mu.Lock()
	defer e.mu.Unlock()

	// 1. Eviksi elemen lama jika slot ring buffer sudah terisi
	if e.bufferValid[e.head] {
		oldVal := e.bufferValues[e.head]
		e.bit.Add(oldVal, -1)
		e.count--
	}

	// 2. Simpan nilai baru
	e.bufferValues[e.head] = val
	e.bufferValid[e.head] = true
	e.bit.Add(val, 1)
	e.count++

	// 3. Gerakkan pointer siklik
	e.head = (e.head + 1) % e.windowSize
	atomic.AddUint64(&e.totalOps, 1)
}

// QueryPercentile mengembalikan estimasi nilai pada persentil tertentu (0.0 < p <= 1.0)
// Menggunakan Binary Lifting pada BIT: Kompleksitas O(log M) tanpa sort!
func (e *SlidingWindowQuantileEngine) QueryPercentile(percentile float64) (int, error) {
	if percentile <= 0.0 || percentile > 1.0 {
		return 0, errors.New("persentil harus berada di antara (0.0, 1.0]")
	}

	e.mu.RLock()
	defer e.mu.RUnlock()

	if e.count == 0 {
		return 0, errors.New("tidak ada data dalam jendela observasi")
	}

	// Hitung posisi k (1-based ranking)
	targetK := int64(float64(e.count) * percentile)
	if targetK < 1 {
		targetK = 1
	}
	if targetK > e.count {
		targetK = e.count
	}

	val := e.bit.FindKth(targetK)
	return val, nil
}

func main() {
	// Inisialisasi engine: Jendela geser 10.000 event, range nilai latensi 0 - 5.000 ms
	cfg := Config{
		WindowCapacity: 10000,
		MaxValueRange:  5000,
	}
	engine, err := NewSlidingWindowQuantileEngine(cfg)
	if err != nil {
		panic(err)
	}

	// Simulasi aliran metrik (Latensi sistem)
	// Memasukkan variasi latensi dasar 50ms, dengan lonjakan acak
	start := time.Now()
	for i := 1; i <= 20000; i++ {
		lat := 40 + (i % 30) // Pola latensi periodik: 40ms - 69ms
		if i%500 == 0 {
			lat = 1500 // Spike outlier latensi
		}
		engine.Observe(lat)
	}

	p50, _ := engine.QueryPercentile(0.50)
	p90, _ := engine.QueryPercentile(0.90)
	p99, _ := engine.QueryPercentile(0.99)

	elapsed := time.Since(start)
	fmt.Printf("Status Engine: Selesai memproses 20.000 event dalam %v\n", elapsed)
	fmt.Printf("Window Active Count: %d event terakhir\n", engine.windowSize)
	fmt.Printf("Hasil Real-Time Percentile Calculation:\n")
	fmt.Printf("  Median (P50) : %d ms\n", p50)
	fmt.Printf("  Tail   (P90) : %d ms\n", p90)
	fmt.Printf("  Peak   (P99) : %d ms\n", p99)
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
*Platform Financial High-Frequency Order-Routing & Execution Matching Engine* yang menangani lebih dari 2.500.000 pesanan per detik dengan jaminan *SLA P99.99* di bawah 250 mikrodetik.

#### Masalah Produksi
Implementasi awal sistem monitoring latensi internal menggunakan pustaka open-source berbasis struktur *Dynamic SkipList* dan *Standard Two-Heap Tracking* (LeetCode 295/480). 

Gejala kegagalan arsitektur:
1. **GC Stop-the-World Jitter:** Setiap metrik mengalokasikan objek *node* kecil di Heap. Ketika sistem mencapai *peak load* (2,5 juta objek per detik masuk dan keluar jendela), *Go Garbage Collector* memicu fase *Mark Termination* yang memakan waktu hingga 15 milidetik. Hal ini melanggar batas SLA $250\ \mu\text{s}$ secara fatal.
2. **Cache Thrashing:** Penelusuran *SkipList* berbasis pointer menyebabkan *L3 cache miss* yang sangat tinggi (mencapai 38% berdasarkan analisis profil Linux `perf`).

#### Solusi Arsitektur
1. **Flat Ring Buffer + Fenwick Inversion:** Mengganti struktur berbasis pointer dengan *array* datar berukuran tetap yang dialokasikan sekali saja saat subsistem diinisialisasi (*boot-time pre-allocation*).
2. **Discretized Dynamic Bucketing:** Nilai latensi dipetakan ke dalam satuan integer (rentang $0\text{–}1.000.000$ mikrodetik dengan resolusi per mikrodetik). Nilai di atas 1 detik dicatat pada *overflow bucket*.
3. **Partitioned Striped Lock Engine:** Untuk menangani ratusan *core* server tanpa persaingan kunci (*lock contention*), metrik di-sharding menggunakan nomor ID CPU inti (`runtime.fastrand() % numPartitions`). Masing-masing partisi memelihara *Fenwick Ring Buffer* independen, dan agregasi kuantil membaca ke seluruh partisi secara paralel tanpa menghalangi *hot-path writer*.

#### Dampak Bisnis & Performa
* **GC Allocations:** Turun dari $2.500.000\ \text{allocs/sec}$ menjadi **0 allocs/sec** pada *hot-path*.
* **P99.99 Processing Latency:** Berkurang dari $18,4\text{ ms}$ (terkena dampak GC) menjadi **$42\ \mu\text{s}$** stabil.
* **CPU Core Utilization:** Penghematan $32\%$ total *CPU cycles* karena eliminasi *cache misses* dan penurunan siklus *scheduler goroutine*.

---

### 9. Trade-offs

Setiap keputusan struktur data algoritma pada tingkat sistem menuntut kompromi struktural:

```
+-----------------------------------------------------------------------------------------+
|                                ARSITEKTUR STRUKTUR DATA                                 |
+--------------------------+----------------------------+---------------------------------+
| Pendekatan               | Keunggulan                 | Kelemahan / Biaya               |
+--------------------------+----------------------------+---------------------------------+
| Dual-Heap (Lazy Delete)  | Sederhana, O(1) peek       | - Memory bloat akibat data usang|
|                          | memori O(N) fleksibel      | - Pointer chasing & GC overhead |
|                          |                            | - Lock contention tinggi        |
+--------------------------+----------------------------+---------------------------------+
| Flat-Array Fenwick Tree  | Zero-allocation runtime,   | - Domain nilai harus diskrit    |
| (Discretized Integer)    | O(log M) konstan, RAM      | - Butuh estimasi bound nilai    |
|                          | terlokalisasi, cache-line  |   maksimum di awal (pre-bound)  |
+--------------------------+----------------------------+---------------------------------+
| T-Digest / HdrHistogram  | Akurasi statistik tinggi   | - Kompleksitas kalkulasi kompresi|
|                          | rentang dinamis tanpa batas| - CPU overhead saat centroid    |
|                          | ukuran memori tetap O(1)   |   merging / rescaling           |
+--------------------------+----------------------------+---------------------------------+
| SkipList Berbasis Pointer| Fleksibel, mendukung range | - Non-contiguous memory         |
|                          | query nilai riil (float)   | - Cache invalidation konstan    |
|                          |                            | - Rawan race-condition          |
+--------------------------+----------------------------+---------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### 1. Pointer Indirection & False Sharing pada Struktur Ring Buffer
* **Kesalahan:** Menaruh status internal yang diakses oleh thread berbeda (misalnya variabel `head`, `tail`, dan `atomic counter`) bersebelahan langsung di dalam sebuah struct tanpa *padding*.
* **Dampak:** Terjadi **False Sharing**. Dua core prosesor yang berbeda memodifikasi variabel berbeda yang berada di dalam satu *cache line* (64-byte) yang sama, memaksa bus CPU melakukan invalidasi *cache L1/L2* secara berulang (*cache coherency traffic storm*).
* **Solusi/Mitigasi:** Terapkan pembatasan *cache line alignment* menggunakan *padding*:
  ```go
  type AlignedEngineWorker struct {
      head uint64
      _    [56]byte // 64 bytes - 8 bytes = 56 bytes padding
      tail uint64
      _    [56]byte // Mencegah tail dan head berada di cache line yang sama
  }
  ```

#### 2. Unbounded Memory Expansion pada LeetCode Lazy Deletion
* **Kesalahan:** Menerapkan pola `std::priority_queue` atau `container/heap` dengan menandai entri yang dihapus ke dalam `map[ID]bool` tanpa batasan ukuran (*eviction threshold*).
* **Gejala:** Memory leak sistematis (*slow memory leak*). Ketika pola data menghasilkan nilai baru yang selalu lebih kecil daripada elemen root, elemen root tidak pernah berganti, dan elemen usang di dalam heap tidak pernah terpicu untuk dibersihkan.
* **Troubleshooting:** Monitor rasio antara `actual_window_elements` vs `internal_heap_elements`. Jika rasionya $> 2.0$, lakukan *compactification* atau bangun ulang heap secara periodik, atau beralih ke *Ring-Buffer Indexed Storage*.

#### 3. Data Race pada Dual Heap Balancing
* **Kesalahan:** Melakukan operasi *rebalancing* antara Min-Heap dan Max-Heap menggunakan pembacaan *lock-free* atomik secara parsial.
* **Gejala:** *Silent data corruption*. Total count metrik tidak pernah konsisten, menghasilkan persentil yang berada di luar rentang matematis logis.
* **Solusi:** Mutasi struktural multi-kontainer tidak bisa dilakukan secara atomik parsial tanpa *Software Transactional Memory* (STM) atau *Exclusive Critical Section* (`sync.Mutex`). Gunakan struktur pohon tunggal terpadu jika ingin meminimalkan cakupan *locking*.

---

### 11. Best Practices (Production Checklist)

- [ ] **Alokasi Memori Statis:** Seluruh array penampung, buffer, dan node struktur data harus di-alokasi secara utuh pada fase inisialisasi aplikasi (`Init()` / `New()`). Tidak ada pemanggilan alokasi heap baru di dalam alur fungsi per-request/per-event.
- [ ] **CPU Cache Alignment:** Pastikan struct yang memiliki intensitas mutasi konkuren tinggi di-pad ke batas 64 byte untuk mencegah degradasi performa akibat *false sharing*.
- [ ] **Batas Domain Nilai Terdefinisi:** Jika menggunakan *direct indexing* (seperti Fenwick Tree atau Bucket Sort), pastikan batas maksimum nilai metrik memiliki skema *saturation* atau *overflow bin*, bukan membiarkan panic karena *slice out-of-bounds*.
- [ ] **Deadlock-Free Lock Hierarchy:** Jika menggunakan skema partisi kunci ganda (*multi-lock*), definisikan urutan akuisisi kunci yang deterministik berdasarkan alamat memori atau ID partisi terurut numerik.
- [ ] **Profiling Verifikasi Regresi:** Jalankan `go test -benchmem -bench=.` dan pastikan metrik **0 B/op** dan **0 allocs/op** tercapai pada seluruh metode *write path*.
- [ ] **Circuit Breaking State:** Sediakan mekanisme *fallback* komputasi jika thread pembaca menemukan anomali state internal (misal: mengembalikan data jendela sebelumnya alih-alih melempar panic).

---

### 12. Hands-on Practice

Buat dan jalankan modul praktikum ini di direktori: `hands-on/m02/`

#### Struktur Proyek
```
hands-on/m02/
├── go.mod
├── buffer.go
├── buffer_test.go
```

#### Langkah 1: Inisialisasi Proyek
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init m02-advanced-algo
```

#### Langkah 2: Implementasi Zero-Alloc Sliding Window Maximum (LeetCode 239 Production Engine)
Tulis kode berikut pada `hands-on/m02/buffer.go`. Implementasi ini mengonversi algoritma *Monotonic Deque* standar LeetCode menjadi mesin antrean deterministik zero-allocation berbasis *Circular Double-Ended Queue*:

```go
package m02

import (
	"errors"
	"sync"
)

// MonotonicRingDeque mengimplementasikan Double-Ended Queue berbasis Ring Buffer.
// Mencegah semua alokasi slice dynamic pada hot path.
type MonotonicRingDeque struct {
	data  []int // Menyimpan index dari elemen
	head  int
	tail  int
	count int
	cap   int
}

func NewMonotonicRingDeque(capacity int) *MonotonicRingDeque {
	return &MonotonicRingDeque{
		data:  make([]int, capacity),
		cap:   capacity,
		head:  0,
		tail:  0,
		count: 0,
	}
}

func (q *MonotonicRingDeque) IsEmpty() bool { return q.count == 0 }
func (q *MonotonicRingDeque) IsFull() bool  { return q.count == q.cap }
func (q *MonotonicRingDeque) Len() int      { return q.count }

func (q *MonotonicRingDeque) PushBack(val int) {
	if q.IsFull() {
		return
	}
	q.data[q.tail] = val
	q.tail = (q.tail + 1) % q.cap
	q.count++
}

func (q *MonotonicRingDeque) PopBack() (int, bool) {
	if q.IsEmpty() {
		return 0, false
	}
	q.tail = (q.tail - 1 + q.cap) % q.cap
	val := q.data[q.tail]
	q.count--
	return val, true
}

func (q *MonotonicRingDeque) PopFront() (int, bool) {
	if q.IsEmpty() {
		return 0, false
	}
	val := q.data[q.head]
	q.head = (q.head + 1) % q.cap
	q.count--
	return val, true
}

func (q *MonotonicRingDeque) Back() (int, bool) {
	if q.IsEmpty() {
		return 0, false
	}
	idx := (q.tail - 1 + q.cap) % q.cap
	return q.data[idx], true
}

func (q *MonotonicRingDeque) Front() (int, bool) {
	if q.IsEmpty() {
		return 0, false
	}
	return q.data[q.head], true
}

// ProductionSlidingMaxEngine menghitung nilai maksimum real-time dari stream data.
type ProductionSlidingMaxEngine struct {
	mu         sync.Mutex
	windowSize int
	deque      *MonotonicRingDeque
	history    []int // Circular storage untuk data aktual
	currentIndex int
}

func NewSlidingMaxEngine(windowSize int) (*ProductionSlidingMaxEngine, error) {
	if windowSize <= 0 {
		return nil, errors.New("windowSize harus > 0")
	}
	return &ProductionSlidingMaxEngine{
		windowSize: windowSize,
		deque:      NewMonotonicRingDeque(windowSize + 1),
		history:    make([]int, windowSize),
		currentIndex: 0,
	}, nil
}

// Push memproses elemen baru stream dan mengembalikan max nilai pada window saat ini.
// Kompleksitas: Amortized O(1), Memori: 0 Allocations.
func (e *ProductionSlidingMaxEngine) Push(val int) int {
	e.mu.Lock()
	defer e.mu.Unlock()

	idx := e.currentIndex
	slot := idx % e.windowSize
	e.history[slot] = val

	// 1. Eviksi elemen di luar jendela geser (idx - windowSize)
	for !e.deque.IsEmpty() {
		frontIdx, _ := e.deque.Front()
		if frontIdx <= idx-e.windowSize {
			e.deque.PopFront()
		} else {
			break
		}
	}

	// 2. Pertahankan sifat Monotonically Decreasing Deque
	for !e.deque.IsEmpty() {
		backIdx, _ := e.deque.Back()
		backVal := e.history[backIdx%e.windowSize]
		if backVal <= val {
			e.deque.PopBack()
		} else {
			break
		}
	}

	// 3. Masukkan index elemen saat ini
	e.deque.PushBack(idx)
	e.currentIndex++

	// 4. Return elemen maksimum (berada di front deque)
	maxIdx, _ := e.deque.Front()
	return e.history[maxIdx%e.windowSize]
}
```

#### Langkah 3: Benchmark & Validasi Zero-Allocation
Tulis kode uji performa pada `hands-on/m02/buffer_test.go`:

```go
package m02

import (
	"testing"
)

func TestSlidingMaxEngineLogic(t *testing.T) {
	engine, err := NewSlidingMaxEngine(3)
	if err != nil {
		t.Fatalf("Gagal inisialisasi: %v", err)
	}

	inputs := []int{1, 3, -1, -3, 5, 3, 6, 7}
	// Expected max window (size 3) setelah elemen ke-3:
	// [1, 3, -1] -> 3
	// [3, -1, -3] -> 3
	// [-1, -3, 5] -> 5
	// [-3, 5, 3] -> 5
	// [5, 3, 6] -> 6
	// [3, 6, 7] -> 7
	expected := []int{1, 3, 3, 3, 5, 5, 6, 7}

	for i, v := range inputs {
		res := engine.Push(v)
		if res != expected[i] {
			t.Errorf("Index %d: input %d menghasilkan max %d, ekspektasi %d", i, v, res, expected[i])
		}
	}
}

func BenchmarkSlidingMaxEngineZeroAlloc(b *testing.B) {
	engine, _ := NewSlidingMaxEngine(1000)
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_ = engine.Push(i % 500)
	}
}
```

#### Langkah 4: Eksekusi dan Verifikasi
Jalankan benchmark melalui terminal:
```bash
go test -v -bench=. -benchmem
```

**Output Ekspektasi:**
```text
=== RUN   TestSlidingMaxEngineLogic
--- PASS: TestSlidingMaxEngineLogic (0.00s)
goos: linux
goarch: amd64
pkg: m02-advanced-algo
BenchmarkSlidingMaxEngineZeroAlloc-8   35492108    33.8 ns/op     0 B/op     0 allocs/op
PASS
ok      m02-advanced-algo 1.245s
```
*Pastikan metrik menunjukkan **0 B/op** dan **0 allocs/op**.*

---

### 13. Exercise

#### Level Easy
* **Deskripsi:** Ubah implementasi `MonotonicRingDeque` agar mendukung operasi `GetMin()` selain `GetMax()` secara simultan dalam satu struktur gabungan (*Sliding Min-Max Engine*).
* **Syarat:** Tetap pertahankan kompleksitas waktu amortisasi $\mathcal{O}(1)$ dan alokasi memori $0\text{ B/op}$.

#### Level Medium
* **Deskripsi:** Rancang implementasi *Sliding Window Rate Limiter* berbasis *Leaky Bucket* dengan kemampuan membaca kuantil interval kedatangan *request* (*inter-arrival time jitter*) menggunakan algoritma *Rolling Fenwick Tree* dengan kapasitas tetap.
* **Syarat:** Handle konkurensi dari 100 *goroutine* bersamaan tanpa menghasilkan *race condition* (lulus uji `go test -race`).

#### Level Hard
* **Deskripsi:** Implementasikan *High-Throughput Order Book Matching Priority Queue* yang diadaptasi dari problem LeetCode 23 (*Merge k Sorted Lists*) dan LeetCode 295 (*Find Median from Data Stream*). Struktur harus mendukung:
  1. Penambahan pesanan *Limit Order* (Beli/Jual) secara real-time.
  2. Pembatalan pesanan berdasarkan ID secara deterministik dalam $\mathcal{O}(\log N)$.
  3. Mengembalikan harga eksekusi kliring (*Spread Median Crossing Price*) dalam $\mathcal{O}(1)$.
* **Syarat:** Sistem tidak boleh mengalokasikan objek baru pada siklus eksekusi pencocokan (*matching path*). Gunakan teknik *Free-list Array Pooling*.

---

### 14. Challenge (Tantangan Studi Kasus Nyata)

#### Latar Belakang Masalah
Anda adalah *Lead Core Systems Architect* pada bursa pertukaran kripto terdesentralisasi / tersentralisasi (*Hybrid Order-Book Exchange*). Sistem Anda menerima *firehose* berupa jutaan pembaruan order per detik melalui jaringan WebSocket terdistribusi.

#### Skenario Kasus
Setiap instrumen perdagangan harus mengeksekusi algoritma *Dynamic Volatility Circuit Breaker* berbasis **Sliding Window Exponential Moving Standard Deviation** dan **Order Book Imbalance (Top 100 Depth Levels)**.
* **Volume:** $5.000.000\ \text{events/sec}$ per node server.
* **Budget Hardware:** Mesin Bare-metal 64-Core AMD EPYC, 256GB RAM.
* **Constraint:** Latensi evaluasi *circuit breaker* harus berada di bawah $5\ \mu\text{s}$ pada persentil P99.9. Penggunaan *Standard Lock* (`sync.Mutex`) menyebabkan degradasi performa (*convoying phenomenon*) di mana *worker threads* saling menahan eksekusi pada level *kernel scheduler*.

#### Misi Rekayasa Anda
Rancang dan jelaskan cetak biru arsitektur lengkap:
1. **Model Memori & Algoritma:** Tentukan struktur data algoritma yang Anda pilih untuk menggantikan pencarian order konvensional tanpa mengorbankan ketepatan floating point.
2. **Koordinasi Konkurensi:** Bagaimana Anda mendesain skema *Single-Writer Principle* (misalnya mengadaptasi LMAX Disruptor) untuk mengeliminasi *mutex locks* secara total?
3. **Penanganan Memory Reordering & Hardware Barrier:** Bagaimana Anda memastikan instruksi penulisan terbaca secara konsisten oleh beberapa *reader cores* tanpa terkena penalti *cache-invalidation* global?

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Mengapa struktur data berbasis *pointer* seperti *Linked List* atau *Binary Search Tree* standar sering kali berkinerja lebih lambat dibandingkan *contiguous array* pada CPU modern, meskipun memiliki kompleksitas waktu $\mathcal{O}$ teoritis yang sama?
2. Apa yang dimaksud dengan *Lazy Deletion* pada struktur data *Heap*, dan apa dampaknya terhadap konsumsi memori dalam skenario *sliding window* jangka panjang?
3. Pada *Ring Buffer*, bagaimana ekspresi aritmatika modular `(tail + 1) % capacity` dapat dioptimalkan jika kapasitas buffer dijamin selalu bernilai pangkat dua ($2^k$)?
4. Jelaskan apa yang dimaksud dengan fenomena *False Sharing* pada arsitektur multi-core dan bagaimana cara mencegahnya pada level kode bahasa Go!
5. Apa perbedaan mendasar antara *Amortized Time Complexity* dengan *Worst-Case Latency Guarantee*, dan mengapa perbedaan ini krusial pada sistem *Real-Time*?

#### 5 Pertanyaan Intermediate
6. Bagaimana algoritma *Binary Lifting* memungkinkan pencarian nilai persentil pada sebuah *Fenwick Tree* (Binary Indexed Tree) dapat diselesaikan dalam kompleksitas waktu $\mathcal{O}(\log M)$, bukan $\mathcal{O}(\log^2 M)$?
7. Dalam kondisi konkurensi tinggi, apa konsekuensi mekanis dari penggunaan pola `sync.RWMutex` jika rasio operasi baca (*RLock*) dan operasi tulis (*Lock*) sangat condong ke arah penulisan (write-heavy workload)?
8. Bagaimana pengaruh *Garbage Collector Mark-and-Sweep* terhadap varians latensi (*jitter*) pada algoritma streaming yang mengalokasikan ribuan struct pendek per detik di heap?
9. Mengapa struktur data *Order-Statistic Tree* standar berbasis Red-Black Tree tidak thread-safe secara alami, dan mengapa membuat setiap operasinya sinkron melalui *Fine-grained Locking* justru sering memicu penurunan *throughput* yang drastis?
10. Sebutkan kelemahan representasi nilai metrik terdiskritisasi (*Discretized Bucket Indexing*) dan pada kondisi dataset seperti apa pendekatan ini menjadi tidak efisien secara memori (*sparse value catastrophe*)?

#### 3 Skenario Kasus Produksi
11. **Skenario A:** Tim Anda mendeteksi bahwa sistem agregasi metrik mengalami lonjakan P99 latency secara berkala setiap 2 menit. Analisis `pprof` menunjukkan bahwa 40% waktu CPU dihabiskan pada runtime `runtime.scanobject` dan `runtime.gcDrain`. Algoritma internal Anda menggunakan `map[int64]*MetricNode` sebagai cache sliding window. Langkah refactoring arsitektural apa yang harus diambil untuk mengeliminasi masalah ini tanpa mengubah fungsi fungsional sistem?
12. **Skenario B:** Pada implementasi antrean prioritas multi-thread untuk *job scheduler*, Anda mengganti `sync.Mutex` dengan algoritma *lock-free priority queue* berbasis *CAS (Compare-And-Swap)*. Namun, pada saat pengujian beban tinggi (load test), latensi transaksi justru meningkat tajam dan utilisasi core CPU mencapai 100% pada semua thread. Masalah konkurensi tingkat rendah apa yang sedang terjadi di level prosesor, dan bagaimana Anda mengatasinya?
13. **Skenario C:** Anda diminta merancang sistem deteksi *Distributed Denial of Service (DDoS)* pada level *packet gateway* yang harus menghitung frekuensi kedatangan paket per IP dalam jendela geser 10 detik terakhir untuk kapasitas hingga $50.000.000$ IP unik. Penggunaan memori dibatasi maksimal 512 MB. Mengapa algoritma persis LeetCode (seperti Hash Map + Doubly Linked List / LRU) tidak mungkin digunakan di sini, dan kombinasi algoritma probabilistik/pendekatan aproksimasi apa yang harus diterapkan?

---

### 16. Summary

Menguasai algoritma dan struktur data pada level pemecahan masalah teoritis (seperti LeetCode) hanyalah langkah awal dalam siklus rekayasa perangkat lunak. Pada arsitektur tingkat *enterprise* dan sistem berlatensi rendah:

1. **Efisiensi Hardware adalah Kunci:** Kompleksitas $\mathcal{O}(1)$ atau $\mathcal{O}(\log N)$ tidak ada artinya jika algoritma menghasilkan fragmentasi memori masif, *CPU cache misses*, dan *GC thrashing*. Penataan memori yang kontigu (*mechanical sympathy*) mengungguli abstraksi struktur data murni berbasis *pointer*.
2. **Zero-Allocation Mindset:** Pada *critical execution path*, alokasi memori dinamis harus dihilangkan melalui *pre-allocation*, penggunaan *flat arrays*, pemanfaatan *ring buffers*, dan daur ulang memori berbasis *object pools*.
3. **Optimasi Berbasis Domain Masalah:** Algoritma umum sering kali dapat digantikan oleh solusi berbasis domain yang jauh lebih cepat, seperti mengganti pencarian pohon dinamis dengan *Discretized Fenwick Trees* atau *Monotonic Structures* yang memberikan determinisme latensi pada sub-mikrodetik.