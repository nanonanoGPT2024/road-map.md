# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**Kategori:** 01-Core-Foundations | **Bab 08:** BAB-08-Materi-Lanjutan | **Topik:** Algoritma Lanjutan ke Sistem Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Mentranslasikan** struktur data teoretis LeetCode (Graph, Heap, Trie, Segment Tree, Sliding Window) ke dalam komponen infrastruktur produksi berkemampuan konkurensi tinggi (*high-concurrency*) dan berlatensi rendah (*ultra-low latency*).
- **Menganalisis dan Memitigasi** *mechanical mismatch* antara kompleksitas asimtotik teoretis ($O(1)$, $O(\log N)$) dengan batasan arsitektur perangkat keras modern (*CPU cache lines, branch prediction, garbage collection overhead, false sharing*).
- **Mengimplementasikan** struktur data *lock-free*, *zero-allocation*, dan *cache-conscious* dalam bahasa pemrograman Go untuk lingkungan *real-time mission-critical*.
- **Mengevaluasi** rasio *trade-off* sistemik antara penggunaan memori, P99 latency, *throughput*, dan kompleksitas operasional pada sistem terdistribusi skala enterprise.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, engineer wajib menguasai:
- **Teori Kompleksitas Algoritma:** Analisis Big-O (Time, Space, Amortized) hingga batas asimtotik ekstrem.
- **Struktur Data Dasar & Menengah:** Hash Tables, Heaps/Priority Queues, Binary Search Trees, Graphs (Adjacency Matrix & List), Disjoint-Set Union (DSU).
- **Computer Systems & Architecture:** Model memori hardware (L1/L2/L3 cache, cache line 64-byte, TLB), virtual memory, dan instruksi atomik CPU (Compare-And-Swap/CAS).
- **Konkurensi & Sinkronisasi:** Race conditions, mutex, read-write locks, memory barriers, dan channels/goroutine scheduling di Go.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Transisi Algoritma Akademik ke Rekayasa Produksi

Pada platform kompetitif seperti LeetCode, algoritma dievaluasi dalam lingkungan terkontrol:
1. Input berukuran terbatas yang dimuat sekaligus ke memori (*batch execution*).
2. Algoritma berjalan *single-threaded*, mengecualikan efek perebutan sumber daya (*thread contention*).
3. Metrik keberhasilan absolut hanyalah *Execution Time* dan *Peak Memory Usage* tanpa interupsi *Garbage Collector* (GC).

Di lingkungan produksi enterprise:
- **Continuous Ingestion:** Data mengalir tanpa henti (*infinite streams*); struktur data tidak boleh mengalami kebocoran memori (*memory leak*) atau fragmentasi *heap*.
- **Mechanical Sympathy:** Algoritma $O(N)$ dengan *sequential memory access* (array datar) sering kali jauh mengungguli algoritma $O(\log N)$ yang berbasis *pointer-chasing* (seperti BST atau Linked List) akibat tingginya rasio *CPU Cache Misses*.
- **P99 & P99.9 Latency:** Rata-rata throughput tidak berarti jika *tail latency* rusak akibat *stop-the-world* GC pauses yang dipicu oleh alokasi objek kecil yang masif.

```
+-------------------------------------------------------------------------+
|                  CPU Core (Registers & Execution Units)                 |
+-------------------------------------------------------------------------+
       | ~1 ns
+------------------------------------+
| L1 Data Cache (32KB - 48KB, ~4-5c) |
+------------------------------------+
       | ~3-4 ns
+------------------------------------+
| L2 Cache (512KB - 1MB, ~12-14c)    |
+------------------------------------+
       | ~10-15 ns
+------------------------------------+
| L3 Shared Cache (16MB - 64MB, ~40c)|
+------------------------------------+
       | ~60-100 ns (Cache Miss: Pointer Chasing penalty)
+-------------------------------------------------------------------------+
|                       Main Memory (DRAM - DDR4/DDR5)                    |
+-------------------------------------------------------------------------+
```

### 3.2 Data-Oriented Design vs Object-Oriented Structures

Struktur data node klasik (Node-based Trie, Tree, Linked List):
```go
// Anti-pattern produksi: Pointer-heavy, fragmentasi heap, cache-unfriendly
type Node struct {
    val      int
    children []*Node
}
```
Setiap instansiasi `Node` memicu alokasi heap terpisah. Pointer berukuran 8 byte pada arsitektur 64-bit yang menunjuk ke lokasi memori acak (*scattered memory allocation*) merusak efisiensi L1/L2 *data cache lines* (64 bytes per fetch).

Sebagai gantinya, arsitektur produksi menggunakan pendekatan **Flat Arrays / Struct-of-Arrays (SoA)**:
```go
// Production Pattern: Cache-line packed, single heap allocation
type FlatTrie struct {
    nodes []CompactNode // dialokasikan secara kontinu
}
```

---

## 4. Why & What

| Dimensi | Algoritma LeetCode Klasik | Arsitektur Algoritma Produksi |
| :--- | :--- | :--- |
| **Model Memori** | Pointer references, recursive stack frames. | Flat continuous buffers, ring buffers, arena allocation. |
| **Eksekusi** | Single-threaded batch processing. | Concurrent, non-blocking / fine-grained lock synchronization. |
| **Manajemen Memori**| Mengandalkan GC otomatis. | Zero-allocation, object pooling (`sync.Pool`), memory reuse. |
| **Failure Mode** | Crash / Time Limit Exceeded (TLE). | Graceful degradation, backpressure, circuit breaking. |
| **Optimasi CPU** | Mengurangi operasi perbandingan matematika. | Mengurangi cache misses, SIMD vectorization, branchless logic. |

Mengapa ini penting? Sebuah implementasi algoritma *Sliding Window* atau *Priority Queue* di LeetCode hanya menangani $\approx 10^5$ item. Di sistem seperti Apache Kafka, Uber Dispatch Engine, atau Cloudflare Edge, algoritma yang sama harus menangani jutaan transaksi per detik (*RPS*) dengan latensi sub-milidetik.

---

## 5. How: Alur Perancangan Sistem Algoritmik Lanjutan

```
+------------------+      +-------------------+      +--------------------+
| Analisis Profil  | ---> | Reduksi Alokasi   | ---> | Akses Memori       |
| Latensi & Data   |      | Memori (Heap->0)  |      | Flat & Kontinu     |
+------------------+      +-------------------+      +--------------------+
         |                                                     |
         v                                                     v
+------------------+      +-------------------+      +--------------------+
| Penjadwalan &    | <--- | Mitigasi Kunci    | <--- | Optimasi Thread-   |
| Backpressure     |      | Lock-Free / Shard |      | Safety & Race Cond |
+------------------+      +-------------------+      +--------------------+
```

1. **Profiling Baseline:** Ukur alokasi memori per operasi (`ns/op`, `B/op`, `allocs/op`) menggunakan Go Benchmark dan pprof.
2. **Eliminasi Alokasi Heap:** Ganti alokasi dinamis berulang dengan *pre-allocated contiguous memory* atau `sync.Pool`.
3. **Restrukturisasi Memori untuk Cache Locality:** Konversikan relasi pointer menjadi pengindeksan array kontinu untuk meminimalkan *cache misses*.
4. **Desain Thread-Safety:** Gunakan partisi (*sharding*), atomic CAS primitives, atau ring buffers untuk menghilangkan contention pada *critical path*.
5. **Implementasi Backpressure:** Tambahkan mekanisme *circuit breaker* atau *ring buffer drop strategy* ketika beban melampaui kapasitas.

---

## 6. Analogi & Diagram ASCII

Bayangkan sistem memori CPU sebagai **Meja Kerja Mekanik (L1 Cache)** dan **Gudang Pusat (Main Memory/RAM)**.

### LeetCode (Pointer Chasing Linked-List):
Mekanik harus merakit sepeda motor, tetapi suku cadang ditempatkan di gudang pusat dalam kotak-kotak terpisah. Setiap kali mekanik memerlukan satu baut, ia harus berjalan ke gudang (100 ns) hanya untuk mengambil satu baut, lalu kembali ke meja kerja.

```
Meja Mekanik (L1)        Gudang Pusat (RAM)
+-------------+          +-------------+
| Butuh Node A| -------> | Ambil Node A| (Jalan 100ns)
| Butuh Node B| -------> | Ambil Node B| (Jalan 100ns, alamat memori beda)
| Butuh Node C| -------> | Ambil Node C| (Jalan 100ns, alamat acak)
+-------------+          +-------------+
Efisiensi: Sangat Rendah (99% Waktu habis berjalan ke gudang)
```

### Production (Contiguous Memory / Flat Buffer):
Mekanik mengambil satu kontainer besar (Cache Line 64 byte) yang langsung memuat 16 baut sekaligus ke atas meja kerjanya. Semua operasi berikutnya diselesaikan langsung di atas meja tanpa perlu meninggalkan posisinya.

```
Meja Mekanik (L1)                      Gudang Pusat (RAM)
+---------------------------------+    +-------------------------+
| [Baut 1, 2, 3, 4, 5, 6, 7, 8]   | <- | Ambil 1 Balok Sekaligus | (Jalan 1x, 100ns)
| Operasi 1-8 langsung di meja   |    +-------------------------+
+---------------------------------+
Efisiensi: Maksimum (Hardware Sympathy)
```

---

## 7. Simple & Practical Implementation

### 7.1 Simple Example: Algoritma Teoretis vs Flat Indexing Array

Berikut perbedaan implementasi struktur data Trie teoretis (LeetCode 208) vs flat array cache-friendly.

```go
package main

// Tipe 1: LeetCode Academic Approach (Pointer Chasing, High Allocations)
type AcademicTrieNode struct {
	Children [26]*AcademicTrieNode
	IsEnd    bool
}

// Tipe 2: Production Flat-Memory Representation (Zero Pointer Overhead)
type CompactTrieNode struct {
	ChildIndices [26]int32 // Menyimpan index flat array, -1 jika kosong
	IsEnd        bool
}

type ProductionTrie struct {
	nodes []CompactTrieNode
}

func NewProductionTrie(capacity int) *ProductionTrie {
	t := &ProductionTrie{
		nodes: make([]CompactTrieNode, 1, capacity),
	}
	// Inisialisasi root node
	for i := 0; i < 26; i++ {
		t.nodes[0].ChildIndices[i] = -1
	}
	return t
}

func (t *ProductionTrie) Insert(word string) {
	curr := int32(0)
	for i := 0; i < len(word); i++ {
		c := word[i] - 'a'
		childIdx := t.nodes[curr].ChildIndices[c]
		if childIdx == -1 {
			newNode := CompactTrieNode{}
			for j := 0; j < 26; j++ {
				newNode.ChildIndices[j] = -1
			}
			t.nodes = append(t.nodes, newNode)
			childIdx = int32(len(t.nodes) - 1)
			t.nodes[curr].ChildIndices[c] = childIdx
		}
		curr = childIdx
	}
	t.nodes[curr].IsEnd = true
}
```

### 7.2 Practical Example: High-Throughput Concurrent Ring-Buffer Sliding Window Rate Limiter

Mengadaptasi algoritma *LeetCode 362 (Design Hit Counter)* menjadi Rate Limiter berbasis Sliding Window berkemampuan jutaan hit per detik, thread-safe, dan *zero heap allocation*.

```go
package main

import (
	"sync/atomic"
	"time"
)

// MetricBucket menyimpan akumulasi counter pada 1 detik tertentu
type MetricBucket struct {
	timestamp int64 // Waktu detik epoch
	count     int64 // Counter request
}

// LockFreeSlidingWindowCounter mengimplementasikan lock-free ring buffer
type LockFreeSlidingWindowCounter struct {
	windowSize int64
	buckets    []MetricBucket
}

// NewLockFreeSlidingWindowCounter membuat counter thread-safe berlatensi rendah
func NewLockFreeSlidingWindowCounter(windowSizeSeconds int) *LockFreeSlidingWindowCounter {
	return &LockFreeSlidingWindowCounter{
		windowSize: int64(windowSizeSeconds),
		buckets:    make([]MetricBucket, windowSizeSeconds),
	}
}

// Increment menambah hit ke dalam window secara atomik tanpa mutex
func (c *LockFreeSlidingWindowCounter) Increment(now time.Time) {
	nowSec := now.Unix()
	idx := nowSec % c.windowSize

	for {
		bTimestamp := atomic.LoadInt64(&c.buckets[idx].timestamp)

		if bTimestamp == nowSec {
			// Bucket pada detik yang sama: langsung increment counter
			atomic.AddInt64(&c.buckets[idx].count, 1)
			return
		}

		if nowSec > bTimestamp {
			// Window telah berputar penuh: reset bucket untuk detik baru
			// Gunakan CAS untuk memastikan hanya 1 goroutine yang me-reset
			if atomic.CompareAndSwapInt64(&c.buckets[idx].timestamp, bTimestamp, nowSec) {
				// Berhasil klaim timestamp, set count langsung ke 1
				atomic.StoreInt64(&c.buckets[idx].count, 1)
				return
			}
			// Gagal CAS, goroutine lain sudah reset atau increment; loop berulang
			continue
		}

		// Jika nowSec < bTimestamp: request datang out-of-order/terlambat; buang atau abaikan
		return
	}
}

// Sum menghitung total request dalam window terakhir
func (c *LockFreeSlidingWindowCounter) Sum(now time.Time) int64 {
	nowSec := now.Unix()
	var total int64

	for i := int64(0); i < c.windowSize; i++ {
		bTimestamp := atomic.LoadInt64(&c.buckets[i].timestamp)
		// Hanya hitung jika data masih dalam range window [nowSec - windowSize + 1, nowSec]
		if nowSec-bTimestamp < c.windowSize && bTimestamp > 0 {
			total += atomic.LoadInt64(&c.buckets[i].count)
		}
	}
	return total
}
```

---

## 8. Real-World Case Study: In-Memory Low-Latency Top-K Order Execution Schedulers

### 8.1 Konteks Masalah
Sebuah platform pertukaran aset kripto memproses hingga 500.000 order per detik. Sistem membutuhkan *real-time match prioritizer* (Order Priority Queue) yang memproses order berdasarkan:
1. `Price` (Prioritas tertinggi untuk harga beli tertinggi atau harga jual terendah).
2. `Timestamp` (FIFO untuk harga yang identik).

### 8.2 Masalah Desain LeetCode (Heap Klasik / `container/heap`)
Pendekatan naif LeetCode menggunakan `container/heap` yang memicu boxing `interface{}` dan memicu alokasi heap saat *Push* dan *Pop*, menyebabkan beban kompilasi GC masif dan variasi *latency spike* hingga 80ms pada P99.9.

### 8.3 Solusi Produksi
1. Membangun Binary Min-Max Heap terspesialisasi berbasis array statis yang dipadatkan (64-bit word packing).
2. Menggunakan bitwise arithmetic untuk traversing child/parent index.
3. Pre-allocated memory array yang menolak GC traversal dengan menampung flat-struct bernilai primitif.

```go
package main

import (
	"errors"
	"sync"
)

type Order struct {
	OrderID   uint64
	Price     uint64
	Timestamp int64
}

// ProductionOrderHeap adalah Zero-Allocation Min-Heap berbasis fixed-capacity buffer
type ProductionOrderHeap struct {
	mu    sync.Mutex
	data  []Order
	size  int
	limit int
}

func NewProductionOrderHeap(capacity int) *ProductionOrderHeap {
	return &ProductionOrderHeap{
		data:  make([]Order, capacity),
		size:  0,
		limit: capacity,
	}
}

func (h *ProductionOrderHeap) Push(order Order) error {
	h.mu.Lock()
	defer h.mu.Unlock()

	if h.size >= h.limit {
		return errors.New("heap capacity exceeded: backpressure triggered")
	}

	// Insert pada daun terakhir
	i := h.size
	h.data[i] = order
	h.size++

	// Sift-Up inline tanpa boxing interface{}
	for i > 0 {
		parent := (i - 1) >> 1 // Setara dengan (i - 1) / 2
		if h.isHigherPriority(h.data[i], h.data[parent]) {
			h.data[i], h.data[parent] = h.data[parent], h.data[i]
			i = parent
		} else {
			break
		}
	}
	return nil
}

func (h *ProductionOrderHeap) Pop() (Order, error) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if h.size == 0 {
		return Order{}, errors.New("heap is empty")
	}

	root := h.data[0]
	h.size--

	if h.size > 0 {
		h.data[0] = h.data[h.size]
		// Sift-Down inline
		i := 0
		half := h.size >> 1
		for i < half {
			left := (i << 1) + 1
			right := left + 1
			best := left

			if right < h.size && h.isHigherPriority(h.data[right], h.data[left]) {
				best = right
			}

			if !h.isHigherPriority(h.data[best], h.data[i]) {
				break
			}

			h.data[i], h.data[best] = h.data[best], h.data[i]
			i = best
		}
	}

	return root, nil
}

// isHigherPriority mengurutkan Order: Price DESC (Max-Heap), jika Price sama, Timestamp ASC (FIFO)
func (h *ProductionOrderHeap) isHigherPriority(a, b Order) bool {
	if a.Price != b.Price {
		return a.Price > b.Price
	}
	return a.Timestamp < b.Timestamp
}
```

---

## 9. Trade-offs Architecture Matrix

| Parameter | LeetCode/Naive Implementation | Production Flat/Lock-Free Implementation |
| :--- | :--- | :--- |
| **P99.9 Latency** | Tinggi & Volatil (5ms - 100ms) akibat GC & Mutex Contention. | Deterministik & Rendah (< 50µs) karena Zero-Allocation. |
| **Throughput (Ops/sec)**| Terbatas (~100k - 300k ops/sec pada high-concurrency). | Sangat Tinggi (> 5M - 20M ops/sec). |
| **CPU Cache Miss Rate** | > 15-25% (Pointer Indirection L3 miss). | < 2% (Contiguous memory L1/L2 hits). |
| **Memory Footprint** | Rendah secara teoritis, besar secara heap metadata. | Tinggi di awal (*pre-allocated capacity reserved*). |
| **Complexity & Maintainability** | Kode ringkas, idiomatik, mudah dipahami. | Kompleks, rawan bug jika index out of bound, perlu audit konkurensi. |
| **Scale Flexibility** | Ukuran elastis dinamis tanpa batas konfigurasi awal. | Kapasitas bounded; butuh strategi eviksi dan backpressure. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 False Sharing pada Cache Lines
* **Penyebab:** Dua variabel berbeda diakses oleh thread berbeda secara independen namun berada di dalam *cache line* 64-byte yang sama. Operasi penulisan oleh Core 1 akan membatalkan cache line Core 2, memaksa pengambilan ulang memori DRAM.
* **Solusi:** Terapkan memory padding agar variabel yang sering dimodifikasi terisolasi dalam cache line independen.

```go
// BAD: Mengalami False Sharing
type ContendedCounters struct {
	CounterA uint64 // 8 byte
	CounterB uint64 // 8 byte (Berada di cache line yang sama dengan CounterA)
}

// GOOD: Memory Padded to 64 bytes
type PaddedCounter struct {
	CounterA uint64
	_        [56]byte // 8 + 56 = 64 bytes (1 cache line penuh)
	CounterB uint64
	_        [56]byte
}
```

### 10.2 Heap Escape melalui Interface Abstrak
* **Penyebab:** Menggunakan `interface{}` (seperti `container/heap`) memaksa Go runtime memindahkan alokasi data dari CPU Stack ke Heap (*escape analysis*).
* **Solusi:** Jalankan `go build -gcflags="-m"` untuk memverifikasi apakah alokasi lolos ke heap. Buat implementasi tipe konkret tanpa antarmuka dinamik pada *hot path*.

### 10.3 Unbounded Concurrency Memory Leak
* **Penyebab:** Membuka goroutine baru secara langsung per operasi tanpa pembatas (*worker pool*), membuat jutaan goroutine menumpuk saat downstream lambat.
* **Solusi:** Gunakan Bounded Buffer Ring Buffer dengan *drop policy* eksplisit.

---

## 11. Best Practices (Production Checklist)

- [ ] **Alokasi Heap Nol pada Jalur Kritis:** Verifikasi dengan `testing.AllocsPerRun` bernilai 0.
- [ ] **Memory Pre-allocation:** Seluruh buffer, slices, dan maps diinisialisasi dengan kapasitas maksimum yang telah dihitung sejak startup.
- [ ] **Cache Line Alignment:** Pastikan struct yang diakses atomik oleh banyak thread memiliki padding hingga batas 64 byte.
- [ ] **Ketiadaan Rekursi:** Konversikan seluruh fungsi rekursif (DFS, QuickSelect, Tree Traversal) menjadi loop iteratif untuk mencegah alokasi *stack expansion frame*.
- [ ] **Audit Race Condition:** Kode wajib lolos pengujian `go test -race -count=1000`.
- [ ] **Profil CPU dan Memori:** Lakukan stress-test beban puncak dan rekam data pprof (`pprof/profile` dan `pprof/heap`).

---

## 12. Hands-on Practice: Membangun Sharded Flat-Memory Trie

Praktikum ini mensimulasikan pembuatan rute routing prefix IP/Domain ultra-cepat untuk sistem API Gateway. Simpan seluruh file di direktori `hands-on/m02/`.

### Struktur Direktori:
```
hands-on/m02/
├── go.mod
├── routing_trie.go
└── routing_trie_test.go
```

### 12.1 `hands-on/m02/go.mod`
```go
module routing-engine

go 1.22
```

### 12.2 `hands-on/m02/routing_trie.go`
```go
package main

import (
	"errors"
	"sync"
)

const (
	AlphabetSize = 26
	RootIndex    = 0
)

type FlatNode struct {
	Next    [AlphabetSize]int32
	HandlerID int32
	IsEnd   bool
}

type FlatRoutingTrie struct {
	mu    sync.RWMutex
	nodes []FlatNode
}

func NewFlatRoutingTrie(initialCapacity int) *FlatRoutingTrie {
	trie := &FlatRoutingTrie{
		nodes: make([]FlatNode, 1, initialCapacity),
	}
	for i := 0; i < AlphabetSize; i++ {
		trie.nodes[RootIndex].Next[i] = -1
	}
	trie.nodes[RootIndex].HandlerID = -1
	return trie
}

func (t *FlatRoutingTrie) Insert(path string, handlerID int32) error {
	t.mu.Lock()
	defer t.mu.Unlock()

	curr := int32(RootIndex)
	for i := 0; i < len(path); i++ {
		char := path[i]
		if char < 'a' || char > 'z' {
			return errors.New("invalid character: only lowercase a-z allowed")
		}
		c := char - 'a'

		nextIdx := t.nodes[curr].Next[c]
		if nextIdx == -1 {
			var newNode FlatNode
			for j := 0; j < AlphabetSize; j++ {
				newNode.Next[j] = -1
			}
			newNode.HandlerID = -1

			t.nodes = append(t.nodes, newNode)
			nextIdx = int32(len(t.nodes) - 1)
			t.nodes[curr].Next[c] = nextIdx
		}
		curr = nextIdx
	}

	t.nodes[curr].IsEnd = true
	t.nodes[curr].HandlerID = handlerID
	return nil
}

func (t *FlatRoutingTrie) Match(path string) (int32, bool) {
	t.mu.RLock()
	defer t.mu.RUnlock()

	curr := int32(RootIndex)
	for i := 0; i < len(path); i++ {
		char := path[i]
		if char < 'a' || char > 'z' {
			return -1, false
		}
		c := char - 'a'

		nextIdx := t.nodes[curr].Next[c]
		if nextIdx == -1 {
			return -1, false
		}
		curr = nextIdx
	}

	if t.nodes[curr].IsEnd {
		return t.nodes[curr].HandlerID, true
	}
	return -1, false
}
```

### 12.3 `hands-on/m02/routing_trie_test.go`
```go
package main

import (
	"testing"
)

func BenchmarkTrieMatch(b *testing.B) {
	trie := NewFlatRoutingTrie(10000)
	routes := []string{"api", "apivone", "apivtwo", "auth", "checkout", "paymentgateway"}

	for i, r := range routes {
		_ = trie.Insert(r, int32(i))
	}

	b.ResetTimer()
	b.ReportAllocs()

	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			handler, found := trie.Match("paymentgateway")
			if !found || handler != 5 {
				b.Errorf("expected handler 5, got %d", handler)
			}
		}
	})
}
```

### 12.4 Langkah Eksekusi Benchmark
```bash
cd hands-on/m02/
go test -bench=. -benchmem -cpu=1,2,4,8
```
*Pastikan hasil alokasi menunjukkan `0 B/op` dan `0 allocs/op` pada baris benchmark.*

---

## 13. Exercises

### Level Easy: Branchless Binary Search
- **Konteks:** Binary search standar memiliki cabang `if/else` yang sering menyebabkan *CPU branch misprediction* jika array berisi data random.
- **Tugas:** Implementasikan branchless binary search dalam Go untuk slice integer terurut:
  $$\text{Target Index} = \text{BranchlessSearch}(arr, target)$$
- **Batasan:** Dilarang menggunakan percabangan kondisional (`if`) di dalam loop pencarian utama. Manfaatkan bitwise masking atau pointer increment berdasar perbandingan boolean.

### Level Medium: Cache-Aligned B-Tree Node Layout
- **Konteks:** Node B-Tree naif menyimpan pointer ke banyak anak.
- **Tugas:** Rancang sebuah struct `BTreeNode` yang tepat berukuran 64 byte (muat dalam 1 cache line CPU). 
- **Batasan:** Struct harus menampung maksimal keys (`int32`) dan offset index array untuk child node (`int32`), diselaraskan secara akurat hingga 64 byte tanpa padding tak terpakai.

### Level Hard: Lock-Free Flat Adjacency Graph Traversal
- **Konteks:** Sistem deteksi penipuan transaksi membutuhkan pembacaan graf relasi akun saat jutaan edge baru masuk secara paralel.
- **Tugas:** Buat struktur data Directed Graph berbasis flat array kontinu yang mendukung:
  1. `AddEdgeConcurrent(u, v int32)` secara lock-free menggunakan atomic operations.
  2. `HasPath(u, v int32) bool` yang dapat berjalan bersamaan dengan penulisan tanpa menahan Mutex global.

---

## 14. Complex Production Challenge (Tanpa Solusi Instan)

### Deskripsi Masalah:
Rancang arsitektur **Distributed Multi-Dimensional Sliding Log Throttle Engine** untuk proteksi Distributed Denial-of-Service (DDoS) di layer Reverse Proxy.

### Persyaratan Arsitektur & Kinerja:
1. **Multi-Dimensi:** Sistem harus memeriksa pembatasan laju (*rate-limiting*) pada 3 kunci hierarkis sekaligus dalam satu operasi tunggal:
   - Global Client IP (CIDR /24)
   - Tenant ID (API Key)
   - Route Path Pattern
2. **Kapasitas & Throughput:**
   - Mampu menangani $2.500.000$ evaluasi per detik per node.
   - P99.99 latensi evaluasi wajib berada di bawah $10\mu s$.
3. **Batasan Memori:**
   - Maksimum memori fisik per node dibatasi hingga $4\text{ GB}$.
   - Dilarang keras memicu alokasi heap baru selama evaluasi paket berlangsung (*0 Allocs/op*).
   - Penggunaan algoritma *Sliding Window Log* (bukan *Fixed Window*) untuk akurasi presisi tinggi tanpa fenomena *burst double-limit boundary*.
4. **Resiliensi:**
   - Desain mekanisme pelepasan beban (*load-shedding*) otomatis menggunakan ring-buffer saturasi saat sistem menghadapi lonjakan lalu lintas yang melampaui alokasi memori $4\text{ GB}$.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic Knowledge
1. Mengapa traversal pada array `[]int` contiguous jauh lebih cepat daripada traversal pada singly linked-list dengan jumlah elemen yang sama pada CPU modern?
2. Berapa ukuran tipikal satu cache line pada arsitektur prosesor x86-64 dan ARM64 modern?
3. Apa dampak negatif langsung dari operasi *escape to heap* terhadap latensi P99 pada runtime Go?
4. Apa yang dimaksud dengan *Branch Misprediction Penalty* dan bagaimana dampaknya terhadap komputasi algoritma?
5. Mengapa struktur data berbasis rekursif murni (seperti Merge Sort standar) dihindari dalam jalur kritis pemrosesan sistem berkapasitas tinggi?

### Bagian B: Intermediate Engineering
6. Bagaimana cara compiler Go menentukan apakah variabel dialokasikan di CPU Stack atau di Heap via escape analysis?
7. Jelaskan fenomena *False Sharing*. Pada kondisi konkurensi seperti apa fenomena ini terjadi, dan bagaimana solusinya?
8. Mengapa algoritma Priority Queue berbasis `container/heap` di Go standar tidak memenuhi standar *Zero-Allocation*?
9. Apa perbedaan mendasar antara implementasi algoritma Sliding Window berbasis `sync.Mutex` dengan pendekatan *Atomic Ring Buffer* dalam hal skalabilitas multithreading?
10. Dalam kasus pemrosesan string masif, mengapa Flat-Array Trie lebih diunggulkan dibanding Map terindeks `map[string]interface{}`?

### Bagian C: Production Scenarios
11. **Skenario 1:** Sebuah layanan pemroses order menunjukkan degradasi latensi P99 dari 2ms melonjak menjadi 150ms setiap 3 menit sekali. CPU utilization rata-rata hanya 30%. Analisis profil memori menunjukkan `runtime.gcBgMarkWorker` menyerap CPU spike saat lonjakan terjadi. Apa akar masalah algoritmik dari sistem ini dan bagaimana langkah perbaikannya?
12. **Skenario 2:** Anda mengimplementasikan lock-free queue menggunakan operasi atomic CAS (*Compare-And-Swap*). Saat diuji coba pada 64 core CPU dengan load masif, performanya anjlok hingga 80% lebih lambat daripada implementasi menggunakan mutex standar. Analisis mengapa algoritma lock-free tersebut justru mengalami degradasi parah.
13. **Skenario 3:** Tim Anda membangun in-memory geo-routing yang mengeksekusi algoritma Dijkstra pada graf jalan raya sebuah kota secara real-time. Graf disimpan menggunakan pointer node object. Setiap request pencarian rute mengalokasikan map `visited := make(map[int]bool)`. Sistem kehabisan memori (OOM) saat traffic mencapai 20.000 RPS. Ubah desain struktur data graf dan tracking state tersebut agar stabil di level produksi.

---

## 16. Summary

1. **Paradigma Hardware-First:** Efisiensi algoritma di lingkungan nyata ditentukan oleh kecocokan representasi memori dengan hierarki CPU cache (*L1/L2/L3 mechanical sympathy*), bukan semata kalkulasi Big-O di atas kertas.
2. **Eliminasi Pointer Chasing:** Mengganti struktur berbasis node-pointer dengan *Flat-Array Contiguous Storage* memangkas cache miss dari puluhan persen menjadi mendekati nol.
3. **Zero-Allocation Mindset:** Menjaga alokasi heap di level nol pada jalur kritis (*hot path*) adalah pertahanan paling efektif terhadap fluktuasi latensi P99/P99.9 akibat interupsi *Garbage Collector*.
4. **Isolasi Memori Konkuren:** Algoritma produksi mutakhir mengombinasikan struktur data *lock-free* atomik, *memory padding* anti-false sharing, dan teknik *sharding* guna mencapai skalabilitas linear lintas core prosesor.