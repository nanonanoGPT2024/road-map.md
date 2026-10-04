# Kurikulum Enterprise Rekayasa Perangkat Lunak
## Topik: LeetCode & Algoritma Lanjutan (Kategori: 01-Core-Foundations)
## BAB 03: Materi Lanjutan
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Menjembatani kesenjangan antara algoritma abstrak kelas *LeetCode Hard* (Monotonic Queue, Segment Tree, Bitmask DP) dengan implementasi sistem skala enterprise.
- Mendesain dan mengimplementasikan struktur data *range query* dan *sliding window aggregation* dengan karakteristik zero-allocation ($0\text{ allocs/op}$) dan *sub-millisecond latency*.
- Mengoptimalkan struktur data berbasis pointer menjadi representasi *contiguous memory* (array-backed) guna memaksimalkan efisiensi CPU cache locality ($L1/L2/L3$).
- Menganalisis trade-off algoritma terhadap batasan *hardware concurrency*, *memory footprint*, dan *lock contention* pada arsitektur terdistribusi real-time.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, engineer wajib menguasai:
- **Foundational Algorithmic Complexity**: Notasi Big-O, amortized analysis, Master Theorem.
- **Data Structures**: Binary Heap, Binary Search Tree, Ring Buffer, dan Disjoint Set Union (DSU).
- **Computer Systems & Architecture**: Konsep CPU cache hierarchy ($L1/L2/L3$), cache lines (umumnya 64 bytes), *cache invalidation*, *branch prediction*, dan *memory alignment*.
- **Bahasa Pemrograman**: Kemahiran tingkat menengah-lanjut dalam bahasa sistem atau backend berperforma tinggi (Go, C++, Rust, atau Java Modern). Modul ini menggunakan **Go** sebagai bahasa implementasi standar enterprise.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi algoritma di level industri tidak hanya berfokus pada asimptotik waktu teoritis ($O(N)$ vs $O(N \log N)$), melainkan pada interaksi algoritma dengan *hardware execution model*. Dua kategori algoritma lanjutan yang sering diaplikasikan dalam engine performa tinggi adalah:

#### 3.1. Monotonic Queue / Deque Engine
Secara matematis, *Sliding Window Maximum/Minimum* (LeetCode 239) diselesaikan menggunakan Monotonic Deque dengan kompleksitas amortisasi $O(N)$. 

**Internal Invariant:**
- Elemen di dalam deque selalu tersusun secara strictly monotonic (menaik atau menurun).
- Deque menyimpan pasangan `(index, value)` atau hanya `index` jika underlying array dapat diakses langsung.
- Setiap kali elemen baru masuk:
  1. *Purge Phase*: Semua elemen di ekor deque yang melanggar invarian monotonik di-pop dari belakang ($O(1)$ amortized).
  2. *Push Phase*: Elemen baru dimasukkan ke ekor deque.
  3. *Evict Phase*: Elemen di kepala deque yang berada di luar rentang window aktif ($i - W + 1$) di-pop dari depan.

**Arsitektur Memori:**
Implementasi standar akademis menggunakan doubly-linked list (`std::list` di C++ atau `container/list` di Go). Struktur ini menghasilkan *pointer chasing* dan fragmentasi heap yang memicu tingginya tingkat *L1 data cache miss*. Di tingkat enterprise, Monotonic Deque wajib dibangun di atas **Circular Ring Buffer** beralokasi statis (flat array) dengan ukuran tetap $K$ (ukuran window).

```
Structure Ring Buffer:
[Index 0 | Index 1 | Index 2 | ... | Index K-1]
   ^                     ^
  Head                  Tail
```

#### 3.2. Array-Backed Segment Tree
Untuk permasalahan *Dynamic Range Minimum/Sum Queries* dengan mutasi data titik maupun interval (LeetCode 307), Segment Tree menyediakan kompleksitas waktu $O(\log N)$ untuk operasi *Query* dan *Update*.

**Representasi Kontigu (Contiguous Layout):**
Pohon biner linear di-flatten ke dalam array berukuran $4N$ (atau $2^{\lceil \log_2 N \rceil + 1}$).
- Node $P$ berada pada indeks $p$.
- Anak kiri: $2p$ (dihitung via bitwise shift: `p << 1`).
- Anak kanan: $2p + 1$ (dihitung via: `(p << 1) | 1`).
- Node Induk: $\lfloor p/2 \rfloor$ (dihitung via: `p >> 1`).

**Hardware Affinity:**
Dengan mengeliminasi pointer (`*Node{left, right}`), traversal Segment Tree memanfaatkan *spatial locality*. Ketika sebuah node diakses, CPU prefetcher menarik seluruh cache line (64 bytes), yang secara implisit memuat node anak dan tetangganya ke dalam L1 Data Cache.

---

### 4. Why & What

| Dimensi | Implementasi Naif (Algoritma Standar LeetCode) | Implementasi Enterprise Production |
| :--- | :--- | :--- |
| **Alokasi Memori** | Menggunakan Heap allocation per-operasi (`new`, dynamic slices). | Zero dynamic allocation via pre-allocated arrays, pooling, atau flat buffers. |
| **Data Locality** | Node-based tree / Linked-list (pointer chasing, non-contiguous). | Cache-friendly flat arrays, sequential memory layout. |
| **Concurrency Safety** | Thread-unsafe atau menggunakan global coarse-grained mutex. | Lock-free atomics, ring buffers partitioned per-core/thread (sharded). |
| **Boundary Protection** | Mengabaikan potensi integer overflow (`int32` vs `int64`). | Safe bounds checking, dynamic wrap-around handling, overflow assertions. |
| **Observabilitas** | Return value langsung tanpa metrik. | Integrasi OpenTelemetry, metrik latensi p99, tracing counters. |

**Mengapa ini penting di Enterprise?**
Pada throughput 1.000.000 request per detik (RPS), algoritma $O(N)$ naif dengan alokasi heap akan memicu siklus *Garbage Collection (GC) Stop-the-World* atau memory fragmentation, meningkatkan tail latency p99 dari $500\mu s$ ke $>50ms$, mendegradasi Service Level Objective (SLO).

---

### 5. How (Workflow Detail)

Alur kerja pemeliharaan status pada High-Performance Sliding Window Engine:

```
[Incoming Telemetry Event]
            │
            ▼
┌─────────────────────────┐
│ Validasi & Penyelarasan │ (Normalisasi timestamp ke epoch bucket)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│       Evict Phase       │ (Hapus indeks kadaluarsa dari Head Ring Buffer)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│       Purge Phase       │ (Hapus elemen ekor jika data baru >= Tail.Value)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│       Push Phase        │ (Sisipkan event baru ke Tail Ring Buffer)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│      Query Phase        │ (Nilai maksimum window instan tersedia di Head)
└─────────────────────────┘
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Monotonic Queue:
Bayangkan antrean promosi jabatan di militer. Ketika seorang perwira muda yang jauh lebih berprestasi (nilai lebih tinggi) masuk ke dalam unit kerja, seluruh perwira senior yang pangkatnya lebih rendah dan prestasinya lebih buruk di barisan belakang (tail) langsung gugur dari daftar prioritas promosi karena mereka tidak akan pernah menjadi kandidat terbaik selama perwira baru ini masih berada di unit kerja tersebut (window).

#### ASCII: Memory Layout Monotonic Ring Buffer vs Pointer-Based Deque

```
POINTER-BASED DEQUE (Heap Fragmentation & Pointer Chasing):
[ Node A ] ──0x8FA1──> [ Node B ] ──0x12C0──> [ Node C ]
 (Addr: 0x10A0)         (Addr: 0x8FA1)         (Addr: 0x12C0)
 * Setiap dereference pointer memicu potensi L1/L2 Cache Miss.

FLAT ARRAY MONOTONIC RING BUFFER (Cache-Line Friendly):
Memory Block: [ 0x00 ][ 0x08 ][ 0x10 ][ 0x18 ][ 0x20 ][ 0x28 ][ 0x30 ][ 0x38 ]
Values:       [ Val 0 | Val 1 | Val 2 | Val 3 | Val 4 | Val 5 | Val 6 | Val 7 ]
Cache Line:   [══════════════════ Single 64-Byte Cache Line ══════════════════]
 * Sekali fetch dari memori langsung memuat seluruh buffer ke dalam L1 Cache!
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Monotonic Deque Teoretis (Versi Algoritmik Naif)
```go
package simple

// SlidingWindowMaxNaif menyelesaikan LeetCode 239 via dynamic slice reallocation
func SlidingWindowMaxNaif(nums []int, k int) []int {
	if len(nums) == 0 || k <= 0 {
		return nil
	}
	deque := make([]int, 0) // dynamic allocation
	res := make([]int, 0, len(nums)-k+1)

	for i, n := range nums {
		// Evict out-of-bound
		for len(deque) > 0 && deque[0] <= i-k {
			deque = deque[1:]
		}
		// Purge suboptimal
		for len(deque) > 0 && nums[deque[len(deque)-1]] <= n {
			deque = deque[:len(deque)-1]
		}
		deque = append(deque, i)
		if i >= k-1 {
			res = append(res, nums[deque[0]])
		}
	}
	return res
}
```

#### 7.2. Practical Example: Enterprise Zero-Alloc Circular Monotonic Buffer
Komponen ini dioptimalkan untuk sliding window metrics pada financial rate limiter atau telemetry engine, tanpa heap allocation pada loop utama.

```go
package advanced

import (
	"errors"
	"fmt"
)

var (
	ErrBufferEmpty = errors.New("buffer is empty")
	ErrBufferFull  = errors.New("buffer capacity exceeded")
)

// MonotonicItem merepresentasikan data titik waktu
type MonotonicItem struct {
	Index uint64
	Value float64
}

// FlatMonotonicRingBuffer mengimplementasikan monotonic deque di atas array kontigu
type FlatMonotonicRingBuffer struct {
	buffer   []MonotonicItem
	capacity uint32
	mask     uint32
	head     uint32
	tail     uint32
	count    uint32
}

// NewFlatMonotonicRingBuffer membuat buffer dengan ukuran power-of-two untuk efisiensi bitwise masking
func NewFlatMonotonicRingBuffer(sizePowerOfTwo uint32) (*FlatMonotonicRingBuffer, error) {
	if sizePowerOfTwo == 0 || (sizePowerOfTwo&(sizePowerOfTwo-1)) != 0 {
		return nil, fmt.Errorf("size must be a positive power of two, got: %d", sizePowerOfTwo)
	}
	return &FlatMonotonicRingBuffer{
		buffer:   make([]MonotonicItem, sizePowerOfTwo),
		capacity: sizePowerOfTwo,
		mask:     sizePowerOfTwo - 1,
		head:     0,
		tail:     0,
		count:    0,
	}, nil
}

// Reset mengosongkan state buffer tanpa alokasi ulang memori
func (rb *FlatMonotonicRingBuffer) Reset() {
	rb.head = 0
	rb.tail = 0
	rb.count = 0
}

// Push memelihara invarian decreasing monotonic deque secara inline
func (rb *FlatMonotonicRingBuffer) Push(idx uint64, val float64, windowSize uint64) {
	// 1. Evict: Hapus elemen di Head yang sudah melewati window boundaries
	for rb.count > 0 {
		headItem := rb.buffer[rb.head]
		if idx >= windowSize && headItem.Index <= (idx-windowSize) {
			rb.head = (rb.head + 1) & rb.mask
			rb.count--
		} else {
			break
		}
	}

	// 2. Purge: Hapus elemen di Tail yang nilainya lebih kecil atau sama (invarian decreasing)
	for rb.count > 0 {
		prevTailIdx := (rb.tail - 1) & rb.mask
		if rb.buffer[prevTailIdx].Value <= val {
			rb.tail = prevTailIdx
			rb.count--
		} else {
			break
		}
	}

	// 3. Insert elemen baru ke Tail
	rb.buffer[rb.tail] = MonotonicItem{Index: idx, Value: val}
	rb.tail = (rb.tail + 1) & rb.mask
	rb.count++
}

// PeekMax mengambil nilai maksimum saat ini dalam window dalam O(1)
func (rb *FlatMonotonicRingBuffer) PeekMax() (float64, error) {
	if rb.count == 0 {
		return 0, ErrBufferEmpty
	}
	return rb.buffer[rb.head].Value, nil
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Real-Time Fraud & Slippage Spike Detector pada High-Frequency Trading (HFT)
* **Problem Statement**: Sistem payment processing memproses order placement dengan kecepatan 500.000 transaksi per detik. Diperlukan deteksi lonjakan (*spike*) volume transaksi maksimum dalam rentang geser 10 detik ($W = 10.000\text{ ms}$) per merchant.
* **Bottleneck Algoritmik Naif**:
  Menggunakan pendekatan binary heap (`container/heap` di Go) memerlukan pemeliharaan heap per-update berbiaya $O(\log K)$ serta kompleksitas memori $O(K)$. Pada $500\text{k RPS}$, alokasi heap pointer-based memicu GC thrashing, dengan latensi p99 melebihi $12\text{ms}$ (SLA mensyaratkan $< 1\text{ms}$).
* **Solusi Arsitektur**:
  1. Menggunakan **Sharded Monotonic Ring Buffer** berbasis hash tenant/merchant.
  2. Implementasi array beralokasi statis dengan *bitmask indexing* (`capacity` berukuran pangkat 2).
  3. Mengganti locking sistem dengan per-shard atomic synchronization atau lock-free partition execution.
* **Hasil**:
  - Amortized Time Complexity: Turun dari $O(\log K)$ ke **$O(1)$ amortized**.
  - Alokasi Memori: **$0\text{ B/op}$** (bebas GC overhead).
  - P99 Latency: Turun drastis dari **$14.2\text{ms}$** menjadi **$120\mu\text{s}$** pada beban puncak 650.000 RPS.

---

### 9. Trade-offs

| Pendekatan Algoritmik | Latensi Time Complexity | Kompleksitas Memori | CPU Cache Hit Ratio | Kapan Digunakan |
| :--- | :--- | :--- | :--- | :--- |
| **Segment Tree (Array-backed)** | $O(\log N)$ Query, $O(\log N)$ Update | $O(4N)$ flat contiguous array | Tinggi (Sequential memory) | Ketika ukuran window dinamis, atau range yang di-query bersifat arbitrary $[L, R]$. |
| **Monotonic Deque (Ring Buffer)**| $O(1)$ Amortized Update & Query | $O(K)$ di mana $K$ adalah window size | Sangat Tinggi (Fixed localized cache lines) | Sliding window dengan ukuran interval tetap ($K$) bergerak searah. |
| **Fenwick Tree (Binary Indexed)** | $O(\log N)$ Query/Update | $O(N)$ flat array | Sangat Tinggi | Hanya mendukung operasi invertible (seperti Sum), tidak efisien untuk arbitrary Range Max/Min. |
| **Sparse Table** | $O(1)$ Query, $O(N \log N)$ Build | $O(N \log N)$ matrix | Sangat Tinggi | Static range queries tanpa adanya mutasi data sama sekali (Read-Only). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal Segment Tree Memory Sizing ($4N$ Rule)
```go
// ANTI-PATTERN: Alokasi 2*N sering memicu index out of bounds runtime panic
tree := make([]int, 2*n) 

// PRODUCTION-PATTERN: Alokasi minimum 4*N menjamin kapasitas full binary tree
tree := make([]int, 4*n)
```
*Sebab*: Segment tree yang tidak di-pad ke pangkat dua berikutnya membutuhkan node internal hingga $2^{\lceil \log_2 N \rceil + 1} - 1 \approx 4N$.

#### 10.2. Off-by-One pada Window Eviction
*Kesalahan*: Menggunakan kondisi `idx - item.Index > windowSize` saat sistem bekerja dengan boundary inklusif.
*Solusi*: Buat unit test formal dengan batas window eksplisit:
$$\text{Window Aktif} = [i - W + 1, i]$$
Elemen di head harus di-evict jika $\text{head.Index} < i - W + 1$.

#### 10.3. False Sharing pada Arsitektur Multi-Core
*Masalah*: Dua buah Monotonic Queue berbeda dialokasikan secara berdampingan di heap memori, sehingga menempati satu cache line 64-byte yang sama. Dua CPU core terpisah saling memodifikasi queuenya masing-masing, memicu fenomena *Cache Line Invalidation Bouncing*.
*Solusi*: Terapkan CPU Cache-line Padding:
```go
type PaddedMonotonicBuffer struct {
	FlatMonotonicRingBuffer
	_ [64 - (unsafe.Sizeof(FlatMonotonicRingBuffer{}) % 64)]byte // Padding ke multiple 64-byte
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Zero Heap Allocation**: Profiling via `go test -benchmem -memprofile` memastikan alokasi loop utama $0\text{ allocs/op}$.
- [ ] **Power-of-Two Buffer Sizing**: Gunakan ukuran ring buffer $2^M$ agar operasi modulus `% cap` dapat diganti dengan bitwise AND `& (cap - 1)`, menghemat siklus CPU division.
- [ ] **Contiguous Backing Arrays**: Hindari referensi node heap `type Node struct { Left, Right *Node }`. Gunakan index flattening array `2*i` dan `2*i + 1`.
- [ ] **Integer Overflow Sanitization**: Indeks urutan berbasis `uint64` untuk mencegah overflow pembacaan interval pada sistem yang menyala puluhan tahun ($2^{64}$ ticks).
- [ ] **Defensive Bounds Assertions**: Selalu lindungi slicing internal dengan validasi guard rails untuk menghindari runtime panic saat edge conditions.

---

### 12. Hands-on Practice

Buatlah direktori dan struktur file berikut di repository lokal Anda:
`hands-on/m02/`

```
hands-on/m02/
├── segment_tree.go
├── segment_tree_test.go
└── go.mod
```

#### Langkah 1: Inisialisasi Modul
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init enterprise/advanced-dsa
```

#### Langkah 2: Buat File `segment_tree.go`
Implementasikan Segment Tree kontigu dengan kapabilitas Range Minimum Query (RMQ) dan Point Update:

```go
package main

import (
	"errors"
	"math"
)

type SegmentTree struct {
	tree []int64
	size int
}

func NewSegmentTree(data []int64) *SegmentTree {
	n := len(data)
	if n == 0 {
		return &SegmentTree{}
	}
	st := &SegmentTree{
		tree: make([]int64, 4*n),
		size: n,
	}
	st.build(data, 1, 0, n-1)
	return st
}

func (st *SegmentTree) build(data []int64, node, start, end int) {
	if start == end {
		st.tree[node] = data[start]
		return
	}
	mid := start + (end-start)/2
	leftNode := node << 1
	rightNode := (node << 1) | 1

	st.build(data, leftNode, start, mid)
	st.build(data, rightNode, mid+1, end)
	st.tree[node] = min(st.tree[leftNode], st.tree[rightNode])
}

func (st *SegmentTree) Update(idx int, val int64) error {
	if idx < 0 || idx >= st.size {
		return errors.New("index out of range")
	}
	st.update(1, 0, st.size-1, idx, val)
	return nil
}

func (st *SegmentTree) update(node, start, end, idx int, val int64) {
	if start == end {
		st.tree[node] = val
		return
	}
	mid := start + (end-start)/2
	leftNode := node << 1
	rightNode := (node << 1) | 1

	if idx <= mid {
		st.update(leftNode, start, mid, idx, val)
	} else {
		st.update(rightNode, mid+1, end, idx, val)
	}
	st.tree[node] = min(st.tree[leftNode], st.tree[rightNode])
}

func (st *SegmentTree) QueryMin(l, r int) (int64, error) {
	if l < 0 || r >= st.size || l > r {
		return 0, errors.New("invalid query range")
	}
	return st.query(1, 0, st.size-1, l, r), nil
}

func (st *SegmentTree) query(node, start, end, l, r int) int64 {
	if r < start || end < l {
		return math.MaxInt64
	}
	if l <= start && end <= r {
		return st.tree[node]
	}
	mid := start + (end-start)/2
	leftNode := node << 1
	rightNode := (node << 1) | 1

	leftMin := st.query(leftNode, start, mid, l, r)
	rightMin := st.query(rightNode, mid+1, end, l, r)
	return min(leftMin, rightMin)
}

func min(a, b int64) int64 {
	if a < b {
		return a
	}
	return b
}
```

#### Langkah 3: Eksekusi Benchmark di `segment_tree_test.go`
Jalankan benchmark verifikasi alokasi:
```bash
go test -bench=. -benchmem
```
*Target*: Query dan Update harus berada di kisaran latency sub-mikrodetik ($< 100\text{ns}$) dan mencatatkan `0 B/op` serta `0 allocs/op`.

---

### 13. Exercise

#### Level Easy
- **Problem**: Implementasikan Circular Queue berbasis slice statis dengan penanda `head`, `tail`, dan `size` tanpa memanggil method `append()`.
- **Constraint**: Kapasitas array $1024$, seluruh operasi (`Enqueue`, `Dequeue`, `Front`, `IsEmpty`) wajib beroperasi dalam $O(1)$ time complexity dan zero alokasi.

#### Level Medium
- **Problem**: Rancang *Sliding Window Median Engine* (LeetCode 480).
- **Constraint**: Window size $K \le 50.000$, throughput stream input $N \le 1.000.000$. Gunakan pendekatan kombinasi dua array-backed balanced priority queues atau segment tree diskritisasi dengan operasi $O(\log K)$ per update point.

#### Level Hard
- **Problem**: Bangun dynamic range query engine dengan **Lazy Propagation** pada Segment Tree untuk mendukung operasi *Range Add* dan *Range Minimum Query*.
- **Constraint**: Panjang stream $N \le 10^6$, kompleksitas waktu $O(\log N)$ worst-case untuk update interval $[L, R]$, konsumsi memori contiguous tidak boleh melebihi $64\text{ MB}$.

---

### 14. Challenge

> **Tantangan Rekayasa Sistem: Distributed Global Rate Limiter Telemetry Kernel**
>
> **Konteks**: Anda adalah Principal Infrastructure Engineer pada payment gateway terdistribusi global.
> **Problem Statement**:
> 1. Sistem menerima jutaan event transaksi acak per detik dari node terdistribusi di multi-region. Setiap event berisi struct:
>    `Transaction { TenantID: string, Timestamp: int64, Amount: uint64 }`
> 2. Anda diwajibkan menghitung secara presisi: **"Peak Amount transaksi individual dalam rentang sliding window geser 60 detik terakhir per TenantID"**.
> 3. Latensi pengambilan data (query) oleh fraud service harus diselesaikan dalam **p99.99 < 500 nanodetik** di local memory.
>
> **Batasan Ketat & Non-Functional Requirements**:
> - Tidak diizinkan menggunakan external datastore (Redis, Memcached, Postgres). Seluruh kalkulasi wajib *in-memory* pada local container engine.
> - Alokasi memori pada fase ingest event transaksi: Mutlak **0 B/op** (Zero Heap Allocations).
> - Garbage Collection Pause overhead tidak boleh meningkat lebih dari $1\%$ saat engine dihantam beban 1.000.000 transaksi/detik.
> - Susun dokumen arsitektur dan model matematis layout memori untuk membuktikan bagaimana algoritma Anda mengeliminasi CPU *branch misprediction* dan *cache invalidation penalty*.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa alokasi memori $4N$ dibutuhkan pada Segment Tree yang di-flatten ke array linear?**
   - *Jawaban*: Karena jika $N$ bukan pangkat dua, Segment Tree membentuk incomplete binary tree. Level paling bawah dari balanced binary tree dengan $N$ leaves membutuhkan array seukuran $2^{\lceil \log_2 N \rceil + 1} - 1$, yang batas atasnya secara matematis mendekati $4N$.
2. **Berapa amortized time complexity operasi push pada Monotonic Deque?**
   - *Jawaban*: $O(1)$. Meskipun satu pemanggilan push dapat melakukan purge loop sebanyak $k$ kali, setiap elemen maksimal dimasukkan satu kali dan dikeluarkan satu kali sepanjang siklus hidup eksekusi.
3. **Mengapa flattening tree structure ke contiguous array menghasilkan performa traversal lebih tinggi dibanding linked nodes?**
   - *Jawaban*: Mengeliminasi pointer-chasing dan memanfaatkan CPU spatial cache locality; data contiguous ditarik bersamaan dalam 64-byte cache line ke cache L1/L2, mereduksi L1 data cache misses.
4. **Apa fungsi operasi bitwise `(idx - 1) & mask` pada implementasi circular ring buffer?**
   - *Jawaban*: Menghitung indeks circular decrement (bergerak mundur) secara aman dan instan tanpa modulus branching, asalkan kapasitas buffer merupakan kelipatan pangkat 2 ($2^M$).
5. **Kapan Sparse Table lebih unggul secara mutlak dibandingkan Segment Tree?**
   - *Jawaban*: Pada skenario data statis (tanpa adanya pembaruan/mutasi), di mana Range Minimum/Maximum Query (RMQ) dapat diselesaikan dalam $O(1)$ time complexity konstan menggunakan Sparse Table, berbanding $O(\log N)$ pada Segment Tree.

#### Bagian 2: Intermediate (5 Pertanyaan)
1. **Bagaimana cara mencegah False Sharing pada data struktur buffer konkuren?**
   - *Jawaban*: Melakukan memory alignment dan struct padding (menambahkan byte pengisi hingga batas 64 byte atau 128 byte) sehingga variable yang dimodifikasi oleh CPU core berbeda berada pada cache line yang terpisah.
2. **Pada Segment Tree, operasi apa yang memerlukan teknik Lazy Propagation?**
   - *Jawaban*: Operasi pembaruan rentang (*Range Update/Interval Update*). Lazy Propagation menunda update ke anak node hingga node tersebut diakses, menjaga kompleksitas range update tetap $O(\log N)$ dan bukan $O(N \log N)$.
3. **Apa perbedaan mendasar antara Fenwick Tree (Binary Indexed Tree) dan Segment Tree?**
   - *Jawaban*: Fenwick Tree mengonsumsi memori lebih hemat ($O(N)$) dan implementasinya sangat ringkas, namun terbatas pada fungsi asosiatif dan invertible (seperti penjumlahan prefix). Segment Tree ($O(4N)$) jauh lebih fleksibel untuk arbitrary range query, non-invertible operators (seperti Range Min/Max), dan interval mutations.
4. **Apa risiko penggunaan `uint32` untuk index tracking pada long-running streaming monotonic queue?**
   - *Jawaban*: *Integer overflow / wrap-around*. Jika throughput 100.000 event/detik, `uint32` ($~4.29 \times 10^9$) akan meluap (overflow) dalam waktu sekitar 11.9 jam, memicu kerusakan logika invarian window. Wajib menggunakan `uint64`.
5. **Mengapa operasi `n & (n - 1) == 0` sering digunakan pada inisialisasi high-performance ring buffer?**
   - *Jawaban*: Untuk memvalidasi secara matematis bahwa ukuran integer $n$ adalah bilangan pangkat 2 (power of two), prasyarat mutlak untuk penggunaan bitwise mask `idx & (n - 1)`.

#### Bagian 3: Skenario Kasus Produksi (3 Kasus)
1. **Skenario 1**: Layanan ingest metrik Anda mengalami *Spike Latency p99* setiap 3 menit sekali. Profiling CPU menunjukkan `runtime.gcDrain` menyita 45% siklus CPU. Kode Anda menggunakan Monotonic Deque dengan slice `deque = append(deque, item)` dan `deque = deque[1:]`. Apa akar masalah dan solusinya?
   - *Solusi*: Sub-slice `deque[1:]` tidak membebaskan memori underlying array, melainkan memicu alokasi heap baru saat kapasitas bertambah via `append()`, menghasilkan memory churn dan GC overhead masif. Solusi: Refactor menjadi Circular Ring Buffer statis beralokasi tunggal di fase inisialisasi (`0 allocs/op`).
2. **Skenario 2**: Engine limit order book financial exchange menggunakan Segment Tree untuk mencocokkan harga terbaik. Saat volume transaksi meningkat drastis, terdeteksi *CPU instruction pipeline stalls* yang tinggi. Analisis menunjukkan compiler gagal melakukan *branch prediction* pada evaluasi traversal recursive query. Bagaimana langkah mitigasinya?
   - *Solusi*: Ubah implementasi Segment Tree dari model rekursif *top-down* menjadi model iterative *bottom-up* (Z-Tree/Segment tree iteratif). Pendekatan iteratif menggunakan loop linear tanpa stack frame call overhead dan memiliki alur branch yang mudah diprediksi oleh Branch Target Buffer (BTB) CPU.
3. **Skenario 3**: Sebuah distributed monitoring agent melaporkan memory footprint membengkak dari 100MB menjadi 4GB setelah runtime berjalan 48 jam, meskipun jumlah item dalam sliding window konstan sebesar 10.000 item. Struktur data menggunakan heap node pointer. Bagaimana menginvestigasi dan menyelesaikan memory leak/fragmentasi ini?
   - *Solusi*: Ini merupakan kasus fragmentasi memori heap akibat alokasi dan dealokasi jutaan pointer node kecil dalam siklus hidup panjang (*heap fragmentation* membuat allocator OS tidak bisa mereclaim memory pages). Solusi: Ganti struktur heap berbasis pointer ke implementasi flat memory pool (arena allocation) atau pre-allocated continuous array buffer.

---

### 16. Summary

1. **Jembatan Algoritma ke Produksi**: Algoritma teoritis kelas *LeetCode Hard* seperti Monotonic Queue dan Segment Tree adalah fondasi vital bagi sistem backend berkecepatan tinggi, dengan syarat implementasi diselaraskan terhadap karakteristik hardware modern.
2. **Hardware-Aware Engineering**: Menghindari pointer-chasing, memaksimalkan CPU L1/L2 cache spatial locality melalui contiguous flat arrays, dan memanfaatkan bitwise operations adalah pembeda utama antara kode fungsional naif dan engine enterprise kelas produksi.
3. **Zero Allocation Principle**: Pada arsitektur pemrosesan data real-time masif, pemeliharaan state harus berkarakteristik zero heap allocation guna menekan pause overhead Garbage Collection dan menjamin stabilitas latensi p99/p99.9.