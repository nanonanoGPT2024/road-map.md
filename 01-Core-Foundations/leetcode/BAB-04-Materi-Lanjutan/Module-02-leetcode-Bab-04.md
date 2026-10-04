# BAB 04: Materi Lanjutan
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, *Software Engineer* diharapkan mampu:
1. **Menganalisis & Mengonversi Algoritma Kompleks ke Sistem Produksi:** Mentransformasi struktur data abstrak LeetCode (seperti *Monotonic Queue*, *Segment Tree with Lazy Propagation*, dan *Disjoint Set Union*) menjadi komponen sistem berlatensi rendah (*low-latency*), *thread-safe*, dan siap produksi.
2. **Mengoptimasi Alokasi Memori & *Cache Locality*:** Menjelaskan dan mengatasi dampak alokasi memori heap, fragmentasi memori, serta *cache misses* (L1/L2/L3) pada implementasi struktur data berbasis *pointer* vs *array-contiguous*.
3. **Mendesain Engine Evaluasi Real-Time Berbasis Algoritma:** Mengimplementasikan pola sliding-window analitik dan evaluasi aturan multi-dimensi berskala jutaan *event per second* (EPS).
4. **Menerapkan Profiling & Benchmarking Terukur:** Mengidentifikasi *hotspot* performa menggunakan pprof/tracer, mengukur kompleksitas amortisasi empiris, dan menekan *tail latency* (P99/P99.9).

---

### 2. Prerequisite

Sebelum mendalami modul ini, peserta wajib menguasai:
* **Analisis Kompleksitas Lanjutan:** Notasi Asimtotik ($\mathcal{O}, \Omega, \Theta$), Analisis Amortisasi (*Accounting & Potential Method*).
* **Core Data Structures:** Binary Heap, Balanced BST (Red-Black / AVL Tree), Hash Map (resolusi collision & open addressing).
* **Dasar Konkurensi Sistem:** Memory models, race conditions, atomic operations, dan synchronization primitives (Mutex, Read-Write Locks).
* **Bahasa Pemrograman:** Go (versi 1.20+) atau C++20 dengan pemahaman mendalam tentang alokasi pointer, referensi memori, dan zero-copy paradigms.

---

### 3. Concept & Internal Architecture

Dalam ranah *competitive programming* (seperti LeetCode), fokus utama seringkali terbatas pada kelulusan batas waktu (Time Limit Exceeded - TLE) dan ruang memori (Memory Limit Exceeded - MLE). Namun, dalam **Arsitektur Produksi Enterprise**, algoritma teoritis yang efisien secara $\mathcal{O}(N \log N)$ dapat berkinerja lebih buruk daripada algoritma $\mathcal{O}(N^2)$ jika mengabaikan hierarki memori modern hardware dan karakteristik konkurensi.

```
+-------------------------------------------------------------------+
|                        CPU Core Pipeline                          |
|  +--------------------+  +--------------------+  +--------------+ |
|  | Fetch & Branch Pred|  | Out-of-Order Engine|  | ALU / Vector | |
|  +--------------------+  +--------------------+  +--------------+ |
+---------------------------------+---------------------------------+
                                  |
                   +--------------v--------------+
                   |  L1 Data Cache (32-64 KB)   | ~1 ns / ~4 cycles
                   +--------------+--------------+
                                  |
                   +--------------v--------------+
                   |     L2 Cache (512-1024 KB)  | ~3-4 ns / ~14 cycles
                   +--------------+--------------+
                                  |
                   +--------------v--------------+
                   |      L3 Cache (Shared)      | ~10-20 ns / ~40-60 cycles
                   +--------------+--------------+
                                  |
                   +--------------v--------------+
                   |      Main Memory (DRAM)     | ~60-100 ns / ~200+ cycles
                   +-----------------------------+
```

#### Struktur Data Teoretis vs Realitas Perangkat Keras
1. **Pointer-Chasing Anti-Pattern:**
   Pohon biner dinamis standar LeetCode (`TreeNode* left, right`) mengalokasikan node secara non-kontigu di heap. Saat menelusuri pohon, CPU mengalami *cache miss* berkali-kali karena setiap node berada di *cache line* (64-byte block) yang berbeda.
   *Solusi Produksi:* Ratakan struktur (*flatten*) ke dalam *flat memory layout* menggunakan array contiguous (misal: *implicit binary heap representation* di mana anak dari indeks $i$ berada di $2i+1$ dan $2i+2$).

2. **Monotonic Queue Engine:**
   Digunakan untuk memecahkan problem seperti *Sliding Window Maximum* (LeetCode 239). Dalam produksi, struktur ini menjadi tulang punggung *real-time rate-limiting*, *order book sliding aggregates*, dan *anomaly detection stream*.
   
   Secara matematis, operasi pada *Monotonic Deque* mempertahankan invarian:
   $$\forall j, k \in \text{Deque}, \quad j < k \implies \text{Value}(j) \ge \text{Value}(k)$$
   Kompleksitasnya diamortisasi menjadi $\mathcal{O}(1)$ per elemen melalui pembersihan elemen yang didominasi (*dominated elements*).

3. **Segment Tree dengan Lazy Propagation:**
   Solusi untuk query agregat rentang dinamis dengan pembaruan interval (*range updates*).
   * Kompleksitas Waktu: $\mathcal{O}(\log N)$ per update dan query.
   * *Lazy Propagation* menunda komputasi anak node sampai interval spesifik node tersebut diakses kembali, menurunkan kompleksitas update interval dari $\mathcal{O}(N)$ menjadi $\mathcal{O}(\log N)$.
   * Arsitektur Memori: Representasi berbasis array membutuhkan alokasi tepat $4N$ node, mengeliminasi overhead dynamic allocation runtime sepenuhnya.

---

### 4. Why & What

| Dimensi | LeetCode Context | Enterprise Production System Context |
| :--- | :--- | :--- |
| **Input Lifecycle** | Statis, array terbatas (disediakan sekali di memori). | Tak terbatas (Unbounded Streams), dinamis, konkruen, asinkron. |
| **Constraint Memori** | Batas total memori (misal: 256MB). | Alokasi per-request, Garbage Collection pauses, fragmentasi heap, cache misses. |
| **Error Handling** | Asumsi input selalu valid sesuai constraint soal. | Malformed packets, corrupted inputs, out-of-order data, graceful degradation. |
| **Thread-Safety** | Single-threaded execution model. | Skala multi-core, non-blocking data structures, write/read contention. |
| **Telemetry & Observability** | Output berupa Return Value atau Print to stdout. | Distributed Tracing, Metrics (Prometheus), Health Checks, P99 Latency Profiling. |

* **Why:** Memahami algoritma lanjutan tanpa memahami arsitektur internal runtime menyebabkan *catastrophic failure* di skala enterprise: lonjakan GC CPU, thread deadlocks, dan lonjakan P99 latency akibat *lock contention* dan *pointer eviction*.
* **What:** Modul ini membedah implementasi konkrit Monotonic Engine dan Segment Tree yang dimodifikasi untuk sistem berkinerja tinggi, thread-safe, dan hemat alokasi memori (*zero-allocation in fast-path*).

---

### 5. How (Workflow Detail)

Alur kerja transisi algoritma leetcode ke pipeline produksi *event-driven*:

```
[ Incoming Streaming Event ]
             │
             ▼
[ RingBuffer / Lock-free Ingestion ]
             │
             ▼
[ Monotonic Eviction / Pruning Mechanism ] ──> Hapus event kadaluarsa (T < Now - Window)
             │
             ▼
[ Contiguous State Storage (Vector/Slice) ] ──> Query agregasi tanpa heap allocation
             │
             ▼
[ Emit Window Aggregates to Consumer ]
```

1. **Ingestion:** Data masuk melalui *channel* atau *ring buffer* tanpa memicu *heap allocation*.
2. **Eviction:** Elemen di ujung ekor deque yang berada di luar jendela waktu dibersihkan secara amortisasi $\mathcal{O}(1)$.
3. **Monotonic Filtering:** Sebelum elemen baru disisipkan, elemen di ujung kepala yang bernilai lebih kecil dari elemen baru dibersihkan untuk mempertahankan order menurun.
4. **Read Execution:** Query status agregasi jendela membaca indeks terdepan (`deque.front()`) secara $\mathcal{O}(1)$ absolut.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Monotonic Deque sebagai Sistem Seleksi Antrean VIP
Bayangkan sebuah antrean di mana seorang tamu baru masuk dengan tingkat urgensi (*urgency score*) tertentu.
Jika tamu baru memiliki urgensi lebih tinggi daripada tamu-tamu yang sudah menunggu di depannya yang memiliki waktu kedatangan lebih lama, tamu-tamu lama tersebut **tidak akan pernah dipilih sebagai yang terpenting**. Oleh karena itu, tamu-tamu lama dikeluarkan dari belakang secara instan.

```
Kondisi Awal: Window Size = 3. Data stream nilai: [4, 2, 5]

Langkah 1: Masuk 4
Deque: [Index 0 (Val 4)]

Langkah 2: Masuk 2
Karena 2 < 4, 2 masih memiliki potensi menjadi maksimum saat 4 keluar jendela.
Deque: [Index 0 (Val 4), Index 1 (Val 2)]

Langkah 3: Masuk 5
5 > 2 -> Pop Back (Index 1 dihapus)
5 > 4 -> Pop Back (Index 0 dihapus)
Deque: [Index 2 (Val 5)]

Visual Mutasi Deque Kontigu:
+-------------------+-------------------+-------------------+
| Index: 2 (Val: 5) |       EMPTY       |       EMPTY       |
+-------------------+-------------------+-------------------+
  ^               ^
  |               |
 Head            Tail (Ring Buffer Bounds)
```

---

### 7. Simple Example & Practical Example

#### Simple Example: LeetCode #239 (Sliding Window Maximum) Idiomatic Go
Implementasi murni algoritma leetcode untuk referensi teoritis:

```go
package main

func maxSlidingWindow(nums []int, k int) []int {
	if len(nums) == 0 || k <= 0 {
		return []int{}
	}
	n := len(nums)
	result := make([]int, n-k+1)
	deque := make([]int, 0, k) // menyimpan indeks

	for i := 0; i < n; i++ {
		// 1. Hapus elemen di luar window saat ini
		if len(deque) > 0 && deque[0] < i-k+1 {
			deque = deque[1:]
		}

		// 2. Pertahankan sifat monotonik menurun
		for len(deque) > 0 && nums[deque[len(deque)-1]] < nums[i] {
			deque = deque[:len(deque)-1]
		}

		deque = append(deque, i)

		// 3. Catat nilai maksimum window
		if i >= k-1 {
			result[i-k+1] = nums[deque[0]]
		}
	}
	return result
}
```

#### Practical Example: Production-Grade Sliding Window Max Engine
Implementasi *thread-safe*, tanpa dynamic resizing di jalur cepat, mendukung observabilitas dan *time-based eviction* untuk metrik transaksi finansial.

```go
package engine

import (
	"errors"
	"sync"
	"time"
)

var (
	ErrBufferFull   = errors.New("engine: ring buffer capacity exhausted")
	ErrWindowEmpty  = errors.New("engine: sliding window contains no elements")
	ErrInvalidParam = errors.New("engine: invalid input parameters")
)

type Event struct {
	Timestamp time.Time
	Value     float64
}

// ProductionSlidingMaxEngine mengimplementasikan monotonic queue berkinerja tinggi
// menggunakan contiguous ring buffer untuk menghindari alokasi GC selama ingestion stream.
type ProductionSlidingMaxEngine struct {
	mu           sync.RWMutex
	windowSize   time.Duration
	capacity     int
	eventBuffer  []Event
	indexDeque   []int // Ring buffer untuk indeks monotonik
	dHead, dTail int
	dLen         int
	head, count  int
}

func NewProductionSlidingMaxEngine(windowSize time.Duration, capacity int) (*ProductionSlidingMaxEngine, error) {
	if capacity <= 0 || windowSize <= 0 {
		return nil, ErrInvalidParam
	}
	return &ProductionSlidingMaxEngine{
		windowSize:  windowSize,
		capacity:    capacity,
		eventBuffer: make([]Event, capacity),
		indexDeque:  make([]int, capacity),
	}, nil
}

// Ingest memasukkan data secara O(1) amortized, thread-safe, zero dynamic memory allocation.
func (e *ProductionSlidingMaxEngine) Ingest(val float64, ts time.Time) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	// 1. Purge event kedaluwarsa berdasarkan window waktu
	e.evictExpiredUnderLock(ts)

	if e.count >= e.capacity {
		return ErrBufferFull
	}

	// 2. Tentukan posisi penyisipan data pada ring buffer
	newIdx := (e.head + e.count) % e.capacity
	e.eventBuffer[newIdx] = Event{Timestamp: ts, Value: val}
	e.count++

	// 3. Pertahankan sifat monotonik menurun pada indexDeque
	for e.dLen > 0 {
		lastIdx := e.indexDeque[(e.dTail-1+e.capacity)%e.capacity]
		if e.eventBuffer[lastIdx].Value < val {
			// Pop Tail
			e.dTail = (e.dTail - 1 + e.capacity) % e.capacity
			e.dLen--
		} else {
			break
		}
	}

	// 4. Push Tail
	e.indexDeque[e.dTail] = newIdx
	e.dTail = (e.dTail + 1) % e.capacity
	e.dLen++

	return nil
}

// GetMax mengambil nilai terbesar saat ini dalam window tanpa alokasi memori heap.
func (e *ProductionSlidingMaxEngine) GetMax(now time.Time) (float64, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	e.evictExpiredUnderLock(now)

	if e.dLen == 0 {
		return 0, ErrWindowEmpty
	}

	maxIdx := e.indexDeque[e.dHead]
	return e.eventBuffer[maxIdx].Value, nil
}

func (e *ProductionSlidingMaxEngine) evictExpiredUnderLock(now time.Time) {
	threshold := now.Add(-e.windowSize)

	// Bersihkan buffer utama dari elemen kadaluwarsa
	for e.count > 0 {
		if e.eventBuffer[e.head].Timestamp.Before(threshold) {
			// Jika elemen tertua di deque adalah elemen yang kedaluwarsa ini, pop Head deque
			if e.dLen > 0 && e.indexDeque[e.dHead] == e.head {
				e.dHead = (e.dHead + 1) % e.capacity
				e.dLen--
			}
			e.head = (e.head + 1) % e.capacity
			e.count--
		} else {
			break
		}
	}

	// Double check head deque terhadap timestamp kadaluwarsa
	for e.dLen > 0 && e.eventBuffer[e.indexDeque[e.dHead]].Timestamp.Before(threshold) {
		e.dHead = (e.dHead + 1) % e.capacity
		e.dLen--
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Ultra Low-Latency Fraud Detection & Dynamic Risk Profiling
* **Klien/Domain:** Payment Processor Gateway (Skala: 150.000 Transaksi per Detik / TPS).
* **Masalah:** Sistem wajib mendeteksi anomali volume penarikan tertinggi per pengguna dalam jendela geser 5 menit terakhir untuk mencegah pembobolan rekening (*account takeover*). 
* **Kegagalan Solusi Naif:** Menggunakan Redis `ZADD` dan `ZREMRANGEBYSCORE` menghasilkan beban I/O jaringan 150k network calls/detik, menyebabkan latency P99 melonjak hingga 45ms dan Redis Sentinel mengalami *OOM crashes*.

```
[ Payment Terminal ]
         │
         ▼  (gRPC Streaming)
[ Microservice Ingestion Layer ]
         │
         ├── Sharded via UserID (Consistent Hashing)
         │
[ Stateful In-Memory Pod with Monotonic Engine ]
         │ (Zero-copy contiguous RingBuffer)
         ├── Query P99: 1.2 Mikrodetik
         └── Decision: ACCEPT / CHALLENGE / REJECT
```

* **Solusi Arsitektural Berbasis Algoritma:**
  1. Partisi data transaksi berdasarkan `UserID` menggunakan Consistent Hashing ke node stateful terdistribusi.
  2. Implementasikan *Monotonic Sliding Engine* berbasis in-memory ring-buffer pada masing-masing stateful pod.
  3. Mengeliminasi I/O jaringan internal per transaksi; pengecekan nilai puncak mutasi dilakukan lokal di core CPU via cache-aligned memory access.
* **Hasil:**
  * Penurunan latensi P99 dari **45 milidetik** ke **1.2 mikrodetik**.
  * Penghematan biaya infrastruktur Redis cluster sebesar 82%.
  * Sistem stabil tanpa menderita *stop-the-world* GC pause karena kapasitas dialokasikan secara statis di awal program (`pre-allocated pool`).

---

### 9. Trade-offs

| Pilihan Struktur Data | Kompleksitas Waktu | Alokasi Memori Heap | Latensi Cache (L1/L2) | Biaya Implementasi & Konkurensi |
| :--- | :--- | :--- | :--- | :--- |
| **Monotonic Deque (Contiguous Ring-Buffer)** | Amortized $\mathcal{O}(1)$ push/pop/query | $\mathcal{O}(1)$ (Zero-alloc pada runtime) | Optimal (Data berderet rapat di memory page) | Kompleksitas tinggi; boundary checks manual dan handling thread contention. |
| **Segment Tree (Flat Array)** | $\mathcal{O}(\log N)$ update/query | $\mathcal{O}(4N)$ dialokasikan sekali | Baik (Array traversal lokal) | Modifikasi range update butuh lazy array; tracing debugging sulit. |
| **Balanced BST (std::multiset / Red-Black Tree)** | $\mathcal{O}(\log N)$ push/pop/query | Tinggi (Heap per node; $\mathcal{O}(N)$ node alloc) | Buruk (Pointer chasing, fragmentasi heap memori) | Mudah digunakan secara out-of-the-box via library standar; overhead CPU besar. |
| **Redis Sorted Set (ZSET)** | $\mathcal{O}(\log N)$ per operasi | Jaringan RPC & Serialization overhead | Tidak relevan (Dibatasi overhead network stack) | Sangat mudah diskalakan secara distributed; trade-off latensi millisecond vs microsecond. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Slice Resizing Memory Leak (Go / Managed Memory)
* *Kesalahan:* Menggunakan pemotongan slice naif `deque = deque[1:]` untuk pop front.
* *Dampak:* Underlying array tidak pernah di-garbage collect karena kapasitas slice lama masih terikat referensinya ke root array.
* *Troubleshooting/Solusi:* Gunakan Circular Ring-Buffer berbasis array tetap (`index = (index + 1) % cap`), atau kosongkan elemen yang dihapus jika berisi pointer (`slice[i] = nil`).

#### 2. False Sharing pada Multi-threaded Processing
* *Kesalahan:* Menyimpan state dua worker thread pada struktur data ring buffer yang berdampingan di memory address yang sama.
* *Dampak:* CPU Core invalidasi L1 cache terus-menerus (*Cache line bouncing*) menurunkan throughput hingga 70%.
* *Troubleshooting/Solusi:* Berikan padding memori sebesar ukuran cache line (64 bytes pada arsitektur x86/ARM):
```go
type WorkerState struct {
    head uint64
    _    [56]byte // Cache line padding (64 - 8 bytes)
    tail uint64
    _    [56]byte // Mencegah false sharing dengan CPU core tetangga
}
```

#### 3. Off-By-One pada Time Boundary Eviction
* *Kesalahan:* Menggunakan pembanding `<=` bukan `<` saat memvalidasi durasi event: `now.Sub(event.Timestamp) <= windowSize`.
* *Dampak:* Menghapus elemen valid yang berada tepat pada batas interval sliding window, menyebabkan under-reporting pada evaluasi anomaly detection.
* *Troubleshooting:* Terapkan unit test deterministik menggunakan *mock clock* (seperti `time.Time` buatan) yang memvalidasi boundary nanosecond.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Pre-allocate Ring Buffer:** Seluruh slice/vektor internal wajib diinisialisasi dengan ukuran pasti saat startup (`make([]T, cap)`), hindari `append()` yang memicu realokasi dinamis.
2. [ ] **Cache Aligning:** Susun struct fields dari tipe data ukuran terbesar ke terkecil untuk meminimalisasi memory padding otomatis oleh compiler.
3. [ ] **Lock Granularity:** Hindari lock global jika throughput ingestion tinggi; partisi berdasarkan sharding key atau gunakan synchronization non-blocking (`atomic CAS`).
4. [ ] **Graceful Degradation:** Tentukan *drop policy* (misal: FIFO drop atau reject) saat buffer antrean internal penuh tanpa membuat service panik/crash.
5. [ ] **Metrics Export:** Lampirkan Prometheus counters untuk:
   * Evicted elements count.
   * Lock wait time (duration).
   * Buffer saturation ratio (`count / capacity`).
6. [ ] **Deterministic Benchmarks:** Jalankan benchmark dengan `-benchmem` dan flag `-race` untuk mendeteksi data race serta memory leaks.

---

### 12. Hands-on Practice

Buat dan jalankan modul praktikum ini pada direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Project
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
go mod init m02-advanced-structures
```

#### Langkah 2: Buat File Implementasi `segment_tree.go`
Pohon Segmen dinamis dengan representasi flat array teroptimasi cache untuk evaluasi metrik order book:

```go
package main

import (
	"errors"
	"fmt"
)

// SegmentTree merepresentasikan contiguous memory segment tree
type SegmentTree struct {
	tree []int64
	lazy []int64
	size int
}

func NewSegmentTree(n int) *SegmentTree {
	return &SegmentTree{
		tree: make([]int64, 4*n),
		lazy: make([]int64, 4*n),
		size: n,
	}
}

func (st *SegmentTree) updateRange(node, start, end, l, r int, val int64) {
	if st.lazy[node] != 0 {
		st.tree[node] += int64(end-start+1) * st.lazy[node]
		if start != end {
			st.lazy[2*node+1] += st.lazy[node]
			st.lazy[2*node+2] += st.lazy[node]
		}
		st.lazy[node] = 0
	}

	if start > end || start > r || end < l {
		return
	}

	if start >= l && end <= r {
		st.tree[node] += int64(end-start+1) * val
		if start != end {
			st.lazy[2*node+1] += val
			st.lazy[2*node+2] += val
		}
		return
	}

	mid := start + (end-start)/2
	st.updateRange(2*node+1, start, mid, l, r, val)
	st.updateRange(2*node+2, mid+1, end, l, r, val)
	st.tree[node] = st.tree[2*node+1] + st.tree[2*node+2]
}

func (st *SegmentTree) queryRange(node, start, end, l, r int) int64 {
	if start > end || start > r || end < l {
		return 0
	}

	if st.lazy[node] != 0 {
		st.tree[node] += int64(end-start+1) * st.lazy[node]
		if start != end {
			st.lazy[2*node+1] += st.lazy[node]
			st.lazy[2*node+2] += st.lazy[node]
		}
		st.lazy[node] = 0
	}

	if start >= l && end <= r {
		return st.tree[node]
	}

	mid := start + (end-start)/2
	p1 := st.queryRange(2*node+1, start, mid, l, r)
	p2 := st.queryRange(2*node+2, mid+1, end, l, r)
	return p1 + p2
}

func (st *SegmentTree) Update(l, r int, val int64) error {
	if l < 0 || r >= st.size || l > r {
		return errors.New("boundary out of range")
	}
	st.updateRange(0, 0, st.size-1, l, r, val)
	return nil
}

func (st *SegmentTree) Query(l, r int) (int64, error) {
	if l < 0 || r >= st.size || l > r {
		return 0, errors.New("boundary out of range")
	}
	return st.queryRange(0, 0, st.size-1, l, r), nil
}

func main() {
	size := 10
	st := NewSegmentTree(size)
	
	// Add 5 to index range [2, 7]
	st.Update(2, 7, 5)
	
	// Query sum of range [1, 3] -> indices 2 and 3 have value 5. Result: 10
	val, err := st.Query(1, 3)
	if err != nil {
		panic(err)
	}
	fmt.Printf("Range Query [1, 3] Result: %d\n", val)
}
```

#### Langkah 3: Buat Benchmark File `segment_tree_test.go`
```go
package main

import (
	"testing"
)

func BenchmarkSegmentTreeUpdateAndQuery(b *testing.B) {
	size := 100000
	st := NewSegmentTree(size)
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_ = st.Update(100, 5000, 10)
		_, _ = st.Query(150, 4500)
	}
}
```

#### Langkah 4: Eksekusi Benchmark
```bash
go test -bench=. -benchmem
```
*Pastikan alokasi menunjukkan `0 B/op` dan `0 allocs/op` di dalam loop utama.*

---

### 13. Exercise

#### Level Easy
* **Problem:** Ubah implementasi `SegmentTree` pada hands-on di atas menjadi query **Range Minimum Query (RMQ)** alih-alih Range Sum Query.
* **Output:** Method `QueryMin(l, r int) (int64, error)` dengan kompleksitas $\mathcal{O}(\log N)$.
* **Constraint:** Gunakan representasi flat slice tanpa struktur node pointer heap.

#### Level Medium
* **Problem:** Rancang struktur data **Lock-Free Monotonic Stack** berbasis single-writer multiple-reader untuk melacak harga saham terendah harian secara live streaming.
* **Constraint:** Gunakan atomic pointer swap untuk mempublikasikan snapshot monotonic stack ke reader threads tanpa mutex locks.

#### Level Hard
* **Problem:** Bangun sistem **2D Dynamic Range Aggregator** menggunakan 2D Segment Tree yang mampu menangani koordinat spasial grid $1000 \times 1000$ dengan dukungan update interval dan query sum interval secara konkuren.
* **Constraint:** Konsumsi memori tidak boleh melebihi $64 \text{ MB}$, zero dynamic allocation saat pemanggilan method `Query`.

---

### 14. Challenge

**Skenario Kasus:** Anda adalah Lead Architect pada sistem high-frequency trading (HFT) matching engine. Sistem Anda menerima feed transaksi dengan latensi sub-mikrodetik yang harus dievaluasi terhadap 10.000 limit rules berbasis ekspresi window temporal (misal: "Apakah total order volume user $X$ pada 200ms terakhir melebihi deviasi standar pasar?").

* **Tantangan:**
  1. Rancang arsitektur data engine in-memory yang mengawinkan prinsip **Monotonic Queue** dan **Lazy-Propagated Segment Tree**.
  2. Sistem wajib menggaransi latensi P99.99 berada di bawah **15 mikrodetik** pada beban 1.000.000 updates/detik.
  3. Memori harus terisolasi dari Stop-The-World (STW) Garbage Collection pauses (manfaatkan *off-heap memory*, sync.Pool statis, atau arena allocations).
  4. Susun *Technical Design Document (TDD)* yang mencakup mitigasi *memory fragmentation*, fallback strategy saat ring buffer overflow, dan formal mathematical proof bahwa kompleksitas update per transaksi tetap berada pada amortized $\mathcal{O}(\log N)$.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa struktur `TreeNode` dengan pointer traversal dinamis buruk untuk performa CPU cache jika dibandingkan dengan array-based tree?
2. Berapa total node yang harus dialokasikan dalam flat array untuk mengakomodasi Segment Tree dengan input array berukuran $N$?
3. Mengapa kompleksitas operasi Monotonic Queue dikatakan $\mathcal{O}(1)$ amortized padahal memiliki loop `for` di dalam operasi push?
4. Apa tujuan utama dari teknik *Lazy Propagation* pada Segment Tree?
5. Mengapa penggunaan slice Go naif `slice = slice[1:]` dapat menimbulkan memory leak jika dilakukan berulang kali dalam jangka panjang?

#### B. Pertanyaan Intermediate
6. Jelaskan fenomena *False Sharing* dalam arsitektur multi-core dan bagaimana cara mengatasinya pada implementasi concurrent queue!
7. Dalam kondisi streaming apa operasi Monotonic Deque mencapai kasus terburuk (*worst-case single operation*) $\mathcal{O}(N)$?
8. Bagaimana pengaruh Garbage Collector (GC) cycle terhadap latensi tail (P99/P99.9) pada implementasi struktur data heap dinamis berskala jutaan elemen?
9. Bagaimana cara kerja Segment Tree array indexing secara implisit untuk menentukan anak kiri dan anak kanan dari sebuah node pada indeks $i$?
10. Mengapa `sync.RWMutex` terkadang menghasilkan performa lebih buruk daripada `sync.Mutex` standar pada ingestion pipeline yang memiliki frekuensi penulisan (*write contention*) sangat tinggi?

#### C. Skenario Kasus Produksi
11. **Skenario 1:** Sistem sliding window Anda melaporkan terjadinya sudden latency spikes setiap 2 menit sekali, bertepatan dengan runtime GC execution. Profiler menunjukkan jutaan objek `Event` kecil di-collect. Langkah optimasi arsitektural apa yang wajib diambil?
12. **Skenario 2:** Sebuah node Segment Tree mengalami race condition ketika lazy flag belum dipropagasikan ke anak-anaknya secara atomik di tengah multi-threaded read/write queries. Bagaimana cara mengamankan state lazy propagation tanpa menggunakan *global exclusive lock* yang merusak performa throughput?
13. **Skenario 3:** Ring buffer monotonic Anda mengalami kondisi buffer overflow karena laju consumer downstream lebih lambat daripada ingestion producer. Jika sistem menangani data sensor telemetri medis yang tidak boleh terputus, *eviction policy* apa yang harus diterapkan dan bagaimana implementasinya pada level pointer ring-buffer?

---

#### Kunci Jawaban Quiz

##### Basic
1. Karena node pointer dialokasikan secara acak di heap, menghasilkan data yang terpencar di alamat fisik memori berbeda. Hal ini menyebabkan CPU sering mengalami *L1/L2 Cache Misses* (pointer-chasing) dibandingkan traversal contiguous array yang sejalan dengan mekanisme *CPU hardware prefetcher*.
2. Memerlukan ukuran array $4N$.
3. Karena setiap elemen hanya masuk (*pushed*) ke dalam deque tepat 1 kali dan dikeluarkan (*popped*) maksimal 1 kali di sepanjang siklus hidupnya. Total seluruh operasi pop untuk $N$ elemen dibatasi oleh $N$, sehingga rata-rata per elemen adalah $\frac{\mathcal{O}(N)}{N} = \mathcal{O}(1)$.
4. Menunda kalkulasi pembaruan node turunan (*child nodes*) hingga data pada interval tersebut benar-benar dibutuhkan oleh query berikutnya, menghindari kompleksitas $\mathcal{O}(N)$ pada range updates.
5. Pemotongan pointer slice tidak mengubah kapasitas array dasar (*underlying array*). Jika array dasar sangat besar dan hanya menyisakan sub-slice kecil, GC tidak dapat membebaskan array dasar tersebut karena referensi memorinya masih aktif.

##### Intermediate
6. *False Sharing* terjadi ketika dua core CPU memodifikasi variabel independen yang secara fisik berada di dalam satu *cache line* (64 byte) yang sama. Hal ini memicu *cache coherence protocol* (MESI) untuk terus membatalkan (*invalidate*) cache line di core tetangga. Solusinya adalah menyisipkan *cache padding* (dummy bytes) agar kedua variabel terisolasi pada cache line yang terpisah.
7. Saat stream data masuk dalam urutan menaik monotonik murni (*strictly increasing order*), di mana satu elemen baru yang bernilai ekstrem langsung mengeluarkan seluruh $N-1$ elemen sebelumnya dari belakang deque dalam satu operasi pemanggilan.
8. Objek heap dinamis yang masif memperpanjang durasi *Mark Phase* GC saat menelusuri pointer graph. Ini memicu *Stop-The-World (STW)* pause atau CPU *cycle-stealing*, menciptakan lonjakan tajam pada kurva P99/P99.9 latency.
9. Dengan konvensi 0-based indexing: Anak kiri berada di indeks $2i + 1$, dan anak kanan berada di indeks $2i + 2$. Node induk dari sembarang node $k$ berada di $\lfloor(k - 1) / 2\rfloor$.
10. `sync.RWMutex` memiliki overhead komputasi atomic operations yang lebih berat untuk melacak pembaca aktif. Jika rasio penulisan (*write ratio*) sangat dominan, overhead koordinasi internal reader-writer lock justru memperlambat eksekusi dibandingkan simple mutex spinlock.

##### Kasus Produksi
11. **Solusi:** Terapkan teknik *zero-allocation memory pooling*. Ubah representasi objek `Event` dari alokasi dinamis ke *pre-allocated contiguous flat ring-buffer* atau gunakan `sync.Pool`. Pastikan alokasi memory heap selama siklus ingestion stabil pada angka `0 B/op`.
12. **Solusi:** Gunakan teknik *Lock Striping* pada Segment Tree. Alih-alih satu lock global, petakan node ke beberapa segment mutex independen, atau gunakan algoritma *Hand-over-hand Locking* (Coupling) di mana traversal menuruni pohon mengunci node anak sebelum melepas node induk, memastikan propagasi lazy tuntas secara terisolasi.
13. **Solusi:** Terapkan *Overwrite-Oldest Ring-Buffer Policy* (Circular Drop-Tail). Saat buffer penuh, geser penunjuk `head` maju satu langkah secara atomik untuk membuang metrik tertua, lalu tuliskan data telemetri medis terbaru pada posisi `tail`. Hal ini mengutamakan data *freshness* real-time tanpa memicu error panik atau memory leak.

---

### 16. Summary

Menguasai algoritma lanjutan setingkat LeetCode merupakan fondasi penting, namun menerapkannya ke dalam arsitektur skala produksi membutuhkan pergeseran paradigma:
* Dari **kebenaran teoretis** menuju **efisiensi hardware-aware** (Cache locality, contiguous memory layouts).
* Dari **asumsi single-thread** menuju **state management thread-safe & zero-allocation**.
* Struktur data seperti **Monotonic Queue** dan **Segment Tree** jika diimplementasikan menggunakan flat contiguous arrays dan ring-buffers dapat melayani jutaan TPS dengan latensi sub-mikrodetik, menjadi fondasi bagi *matching engines*, *fraud detection streaming*, dan *telemetry aggregators*.