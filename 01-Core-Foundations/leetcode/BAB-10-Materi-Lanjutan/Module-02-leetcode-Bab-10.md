# Modul 02: Deep Dive Algoritma ke Arsitektur Produksi: Memory Layout, Cache Locality, dan Zero-Allocation Data Structures

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonversi algoritma teoritis (*LeetCode-style*) menjadi komponen runtime berperforma tinggi dengan mempertimbangkan *Mechanical Sympathy* (L1/L2/L3 CPU cache, branch predictor, dan memori virtual).
- Mengeliminasi *Pointer Chasing* dan *Cache Misses* melalui paradigma *Data-Oriented Design* (DOD) dan struktur data berjejer (*flat memory layouts*).
- Mengimplementasikan struktur data *Zero-Allocation* di lingkungan bahasa terkelola (*managed memory*) guna memitigasi latensi *Stop-The-World* Garbage Collection (GC).
- Merancang struktur data konkuren non-pemblokir (*lock-free*) atau *partition-striped* yang tahan terhadap masalah *False Sharing* dan *Contention Overhead*.
- Mendiagnosis dan mengoptimalkan performa algoritma produksi menggunakan *profiling primitives* (`perf`, pprof, hardware counters).

---

## 2. Prerequisite

Sebelum menempuh modul ini, pastikan Anda telah menguasai:
- **Analisis Kompleksitas Asimptotik Tingkat Lanjut**: Notasi Big-O, Big-$\Omega$, Big-$\Theta$, serta *amortized analysis* (Akuntansi/Metode Potensial).
- **Struktur Data Klasik**: Heaps, Balanced Binary Search Trees (AVL, Red-Black), Hash Tables, Disjoint Set Union (DSU), Trie.
- **Arsitektur Komputer Dasar**: Hierarki memori (Register, L1d/L1i, L2, L3 Cache, RAM, Virtual Memory Paging, TLB).
- **Sistem Operasi**: Thread scheduling, context switching, memory alignment, memory barrier/fence, dan model konkurensi memory consistency.
- **Bahasa Pemrograman**: Kemampuan membaca dan menulis Go/C++ tingkat menengah hingga lanjut (memahami pointer, struct alignment, memory allocation primitives).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Teori vs. Realitas Hardware: The Von Neumann Bottleneck
Dalam platform LeetCode, algoritma dievaluasi di atas *Random Access Machine (RAM) model*, di mana setiap operasi akses memori diasumsikan memiliki cost konstan ($O(1)$ time). Pada hardware modern, asumsi ini tidak valid.

```
+-----------------------------------------------------------+
|                    CPU Core (Registers)                   |
|                  Siklus Akses: ~0.5 - 1 ns                |
+-----------------------------------------------------------+
                             |
                             v
+-----------------------------------------------------------+
|                     L1 Data Cache (32-64 KB)              |
|              Latency: ~1-1.5 ns (3-4 clock cycles)        |
+-----------------------------------------------------------+
                             |
                             v
+-----------------------------------------------------------+
|                        L2 Cache (512KB - 1MB)             |
|              Latency: ~3-4 ns (12-14 clock cycles)        |
+-----------------------------------------------------------+
                             |
                             v
+-----------------------------------------------------------+
|                    L3 Cache (Shared, 16-64 MB)            |
|              Latency: ~10-20 ns (40-60 clock cycles)      |
+-----------------------------------------------------------+
                             |
                             v
+-----------------------------------------------------------+
|                 Main Memory (DRAM, DDR4/DDR5)             |
|            Latency: ~60-100 ns (200-300 clock cycles)     |
+-----------------------------------------------------------+
```

Jika algoritma melakukan *random memory jump* (misalnya penelusuran pointer pada `LinkedList` atau node `BinarySearchTree`), CPU akan mengalami *stall* ratusan siklus menunggu data ditarik dari DRAM ke cache line (standar 64 byte). 

Secara teoritis:
- Binary Search Tree Search: $O(\log N)$
- Hash Map Search: $O(1)$
- Flat Array Linear Scan (SIMD vectorized): $O(N)$

Secara empiris, untuk $N < 1.000$, *linear scan* pada array contiguous (kontigu) dapat mengalahkan BST dan Hash Map berkat *spatial locality* dan *hardware prefetcher*.

### 3.2 False Sharing dan Cache Line Invalidation
Pada arsitektur multi-core, setiap *core* memiliki L1/L2 cache independen yang dijaga konsistensinya melalui protokol *Cache Coherency* (misalnya MESI atau MOESI). Unit pertukaran data terkecil antara memori dan cache adalah **Cache Line** (umumnya 64 byte).

Jika Thread A pada Core 1 memodifikasi variabel `X`, dan Thread B pada Core 2 membaca/menulis variabel `Y`, tetapi `X` dan `Y` berada dalam blok 64-byte yang sama di RAM:
1. Core 1 menandai baris cache tersebut sebagai *Modified*.
2. Seluruh baris cache di L1/L2 Core 2 diinvalidsasi (*Invalid*).
3. Core 2 terpaksa mengambil ulang baris cache tersebut melalui L3 atau DRAM, meskipun Thread B tidak pernah menyentuh variabel `X`.

Fenomena ini disebut **False Sharing**, yang dapat mendegradasi skalabilitas paralel hingga 90% pada algoritma konkuren throughput tinggi. Solusinya adalah *Memory Padding* ke batas kelipatan 64 byte (atau `cpu.CacheLinePad`).

```
[ Cache Line: 64 Bytes                                                ]
+-------------------------------+-------------------------------------+
| Variable A (8B) [Used by T1]  | Variable B (8B) [Used by T2]        |  <-- FALSE SHARING!
+-------------------------------+-------------------------------------+

[ Cache Line 1 (64 Bytes)       ] [ Cache Line 2 (64 Bytes)           ]
+----------------+--------------+ +----------------+------------------+
| Variable A(8B) | Padding (56B)| | Variable B(8B) | Padding (56B)    |  <-- ISOLATED
+----------------+--------------+ +----------------+------------------+
```

### 3.3 Zero-Allocation Paradigm & Memory Layout Engineering
Pada runtime dengan Garbage Collector (seperti Go, Java, C#), setiap alokasi heap (`malloc` / `new`) membawa konsekuensi:
1. **Metadata Overhead**: Alokasi kecil menyertakan header chunk memori (8–16 byte per objek).
2. **Memory Fragmentation**: Memicu fragmentasi heap, menurunkan efisiensi caching dan alokator halaman OS (tcmalloc, jemalloc, Go runtime allocator).
3. **GC Mark-Sweep Latency**: GC harus menelusuri setiap pointer aktif di heap. Jika pohon struktur data Anda memiliki $10.000.000$ pointer terpisah, fase *GC Mark* akan memicu latensi tinggi dan mendominasi CPU utilization.

Arsitektur produksi memitigasi hal ini melalui teknik:
- **Struct of Arrays (SoA)** vs **Array of Structures (AoS)** untuk memaksimalkan vectorization SIMD.
- **Pre-allocated Slab / Arena Allocators**: Alokasikan 1 blok byte array besar, lalu bangun struktur data di atas offset flat slice tersebut tanpa pointer terfragmentasi.

---

## 4. Why & What

| Dimensi | LeetCode / Algoritma Teoretis | Produksi / Enterprise Engineering |
| :--- | :--- | :--- |
| **Metrik Sukses** | Time Complexity ($O$), Space Complexity ($O$). | P99/P99.9 Latency (nanodetik/mikrodetik), GC pause time, L3 Cache Miss Rate, Throughput (ops/sec). |
| **Struktur Objek** | Node berbasis pointer terisolasi (`type Node struct { Next *Node; Val int }`). | Flat Array / Ring Buffer / Index-addressed Pool (`type NodePool []Node`). |
| **Manajemen Memori** | Alokasi per node saat runtime dinamis via operator `new`. | Pre-allocation, Memory Arenas, Zero-Allocation pada *hot path*. |
| **Model Eksekusi** | Single-threaded, input deterministik. | Highly concurrent, non-blocking / fine-grained locked, input spike tak terbatas. |
| **Keandalan** | Berhenti saat program selesai mengeksekusi test suite. | Berjalan stabil 24/7/365 tanpa memory leak, thread starvation, atau *GC thrashing*. |

---

## 5. How (Workflow Detail)

Untuk mentransformasikan struktur data berbasis leetcode menjadi komponen siap produksi, jalankan tahapan sistematis berikut:

```
[ Algoritma Teoretis (Node & Pointer Based) ]
                       |
                       v
[ Profiling Baseline: Ukur Latensi P99, Alokasi Heap/op, L1-D Miss ]
                       |
                       v
[ Refactoring ke Flat Memory Layout (Slab Allocation / Array-Indexed) ]
                       |
                       v
[ Eliminasi Alokasi di Hot-Path (Object Recycling / Arena) ]
                       |
                       v
[ Isolasi Hardware: Cache Line Alignment & Padding (Anti-False Sharing) ]
                       |
                       v
[ Concurrency Hardening: Striping / Sharding / Lock-Free Atomics ]
                       |
                       v
[ Validasi Produksi: Microbenchmark, Race Detection, Stress Test Under Saturation ]
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Perpustakaan Kota vs Meja Kerja
- **Pointer Chasing (Struktur Pohon LeetCode Biasa)**: Anda ingin membaca bab buku. Bab 1 memberi secarik kertas bertuliskan: *"Bab 2 ada di Rak C, Lantai 3, Lemari 4"*. Anda berjalan ke sana, mengambil Bab 2, yang berkata: *"Bab 3 ada di Basement, Kotak 12"*. Anda menghabiskan 95% waktu berjalan bolak-balik (Cache Miss/Memory Stall), bukan membaca.
- **Flat Array (Data-Oriented Cache Line Friendly)**: Seluruh buku dijilid rapi di satu meja kerja persis di hadapan Anda. Saat Anda membaca halaman 1, mata dan tangan Anda secara instan sudah menyentuh halaman 2 hingga 8 dalam satu jangkauan pandangan (Prefetch L1 Cache Line).

```
POINTER CHASING (Node Bertebaran di Virtual Memory Heap):
[Node A (0x1000)] ---> (Pointer miss) ---> [Node B (0xA500)] ---> (Pointer miss) ---> [Node C (0x2100)]
      |                                           |                                           |
  Fetch DRAM (~70ns)                          Fetch DRAM (~70ns)                          Fetch DRAM (~70ns)

FLAT MEMORY CONSECUTIVE LAYOUT:
[ Node A | Node B | Node C | Node D | Node E | Node F | Node G | Node H ]
|<------------ Cache Line 1 (64 Bytes) ------------>|<------------ Cache Line 2 ------------>|
  Fetch L1 Cache Line (~1ns) -> Seluruh Node A-D terbaca otomatis ke CPU Register!
```

---

## 7. Simple Example & Practical Example (Standar Industri)

Kita akan mengimplementasikan **Priority Queue Berkinerja Tinggi (High-Performance Min-Heap)**:
- **Pendekatan Biasa**: Menggunakan slice pointer `[]*Item` dengan alokasi objek dinamis (menyebabkan overhead GC dan pointer indirection).
- **Pendekatan Produksi**: *Zero-Allocation Flat-Memory Min-Heap* dengan pre-allocated arena dan contiguous memory block.

### Kode Produksi: Zero-Allocation Contiguous Min-Heap (Go)

```go
package fastheap

import (
	"errors"
	"math"
	"sync/atomic"
	"unsafe"
)

// Hardware cache line padding constant for x86_64 and ARM64
const CacheLineBytes = 64

var (
	ErrHeapFull  = errors.New("heap capacity saturated")
	ErrHeapEmpty = errors.New("heap is empty")
)

// Task merepresentasikan data flat 16-byte tanpa sub-pointer.
// Sangat ramah CPU Cache Line (4 struct Task muat dalam 1 baris cache 64-byte).
type Task struct {
	Priority int64
	TaskID   uint64
}

// FlatFastHeap adalah struktur Priority Queue heap-based yang beroperasi 
// di atas memori teralokasi flat kontigu tanpa alokasi heap saat runtime.
type FlatFastHeap struct {
	// Memisahkan metadata control dari data array untuk isolasi false-sharing jika diakses konkuren
	count    uint64
	capacity uint64
	_pad0    [CacheLineBytes - 16]byte // Padding cache line

	// Contiguous data arena
	data []Task
}

// NewFlatFastHeap mengalokasikan seluruh memori yang dibutuhkan di awal (pre-allocation).
func NewFlatFastHeap(capacity uint64) *FlatFastHeap {
	if capacity == 0 {
		capacity = 1024
	}
	return &FlatFastHeap{
		count:    0,
		capacity: capacity,
		data:     make([]Task, capacity),
	}
}

// Push memasukkan Task baru tanpa memicu escape analysis ke heap allocator (Zero-Allocation).
// Mengembalikan pointer error jika kapasitas penuh.
func (h *FlatFastHeap) Push(task Task) error {
	if h.count >= h.capacity {
		return ErrHeapFull
	}

	curr := h.count
	h.data[curr] = task
	h.count++

	h.siftUp(curr)
	return nil
}

// Pop mengambil elemen dengan prioritas terendah (Min-Heap root).
func (h *FlatFastHeap) Pop() (Task, error) {
	if h.count == 0 {
		return Task{}, ErrHeapEmpty
	}

	root := h.data[0]
	lastIdx := h.count - 1
	h.data[0] = h.data[lastIdx]
	h.count--

	if h.count > 0 {
		h.siftDown(0)
	}

	return root, nil
}

// Peek mengintip elemen root tanpa menghapusnya.
func (h *FlatFastHeap) Peek() (Task, error) {
	if h.count == 0 {
		return Task{}, ErrHeapEmpty
	}
	return h.data[0], nil
}

// Reset me-reset pointer counter instan tanpa membebaskan buffer (reusable buffer).
func (h *FlatFastHeap) Reset() {
	h.count = 0
}

func (h *FlatFastHeap) Len() uint64 {
	return h.count
}

// siftUp menjaga heap property invariant: O(log N) dengan contiguous sequential memory access.
func (h *FlatFastHeap) siftUp(idx uint64) {
	for idx > 0 {
		parent := (idx - 1) >> 1 // Bitwise shift lebih murah dari pembagian integer
		if h.data[idx].Priority >= h.data[parent].Priority {
			break
		}
		// Swap elemen in-place tanpa alokasi
		h.data[idx], h.data[parent] = h.data[parent], h.data[idx]
		idx = parent
	}
}

// siftDown mereorganisasi heap ke bawah: O(log N).
func (h *FlatFastHeap) siftDown(idx uint64) {
	half := h.count >> 1
	for idx < half {
		left := (idx << 1) + 1
		right := left + 1
		best := left

		if right < h.count && h.data[right].Priority < h.data[left].Priority {
			best = right
		}

		if h.data[idx].Priority <= h.data[best].Priority {
			break
		}

		h.data[idx], h.data[best] = h.data[best], h.data[idx]
		idx = best
	}
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: High-Frequency Limit Order Book (LOB) Engine
- **Skala Beban**: 500.000 transaksi/detik pada bursa crypto/equities tier-1.
- **SLA**: P99 Latency di bawah 2 mikrodetik; deviasi jitter maksimal 500 nanodetik; Zero GC-pause triggers.

### Masalah Desain Klasik LeetCode:
Solusi LeetCode tipikal untuk Order Book adalah menggunakan Map + Doubly Linked List per Price Level:
```go
// ANTI-PATTERN PRODUKSI:
type PriceLevel struct {
    Price  float64
    Orders *list.List // Mengandung ratusan pointer Node terpisah
}
type OrderBook struct {
    Bids map[float64]*PriceLevel // Dynamic bucket hashing, non-thread safe
    Asks map[float64]*PriceLevel
}
```
Ketika 500.000 order masuk per detik:
1. Alokasi `list.Element` dan penghapusan order memicu ribuan siklus GC minor per menit, menyebabkan latency spike hingga 15 milidetik (*SLA violation*).
2. Pointer traversal pada doubly linked list menyebabkan 70% siklus CPU terbuang untuk DRAM memory stall.

### Solusi Arsitektur Engine Enterprise:
1. **Contiguous Ring Buffer + Slot Indexing**: Seluruh order disimpan di array flat berukuran tetap yang dialokasikan saat inisialisasi boot kernel service.
2. **Dense Array Price Ladders**: Menggunakan representasi array integer berindeks cent (misal $100.50 direpresentasikan sebagai int `10050`) untuk akses harga langsung $O(1)$ tanpa hash map.
3. **Double Buffering / Single-Writer Principle**: Menghilangkan mutex locks. Eksekusi matching engine dilakukan oleh satu single-thread CPU yang di-pin via *Core Affinity* (`sched_setaffinity`), berkomunikasi melalui lock-free SPSC (Single Producer Single Consumer) queue ber-padding cache line.

---

## 9. Trade-offs

```
                       [ Latensi Rendah / Kecepatan Ekstrem ]
                                      / \
                                     /   \
                                    /     \
                                   /       \
  [ Fleksibilitas Struktur Data ] /_________\ [ Kompleksitas Kode & Memory Footprint ]
```

| Desain | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Pointer-based Dynamic Alloc** (e.g., LeetCode BST/List) | Kode sederhana, fleksibel, mudah menampung ukuran data tanpa batas tertentu. | Trashing CPU Cache, membebani GC, fragmentasi RAM, latensi P99 tidak stabil. |
| **Contiguous Flat Allocations** (DOD / Arena / Ring Buffer) | Zero GC pressure, latensi P99 sangat deterministik, optimalisasi SIMD dan Cache Line. | Memori awal harus di-*reserve* di awal (*higher memory baseline*), implementasi *re-sizing* kompleks. |
| **Coarse-Grained Lock Mutex** | Sederhana, menjamin konsistensi thread mutlak. | Kontensi tinggi saat core berskala banyak; throughput turun drastis. |
| **Lock-Free / Cache-Padded Atomic Structures** | Tidak ada thread suspension/context switch; throughput maksimum. | Sangat rawan bug ABA, sulit di-debug, konsumsi kode jauh lebih kompleks, memakan byte tambahan untuk padding. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Pointer Escape Analysis Failure
*Kesalahan*: Menganggap variabel lokal tetap berada di stack, padahal runtime memindahkannya (*escape*) ke heap karena dilewatkan via interface kosong atau referensi pointer keluar function.
```go
// BUG PERFORMA: Escape ke Heap!
func (h *FlatFastHeap) ProcessElement(val Task) *Task {
    res := val // Dialokasikan di stack
    return &res // ESCAPE! Memaksa runtime melakukan heap alloc!
}
```
*Solusi*: Terapkan *In-Place Mutation* atau *Value Receiver Passing*:
```go
func (h *FlatFastHeap) ProcessElement(val Task, out *Task) {
    *out = val // Zero allocation, caller memiliki lifecycle memori
}
```
Gunakan flag compiler untuk memverifikasi escape analysis:
```bash
go build -gcflags="-m -m" ./...
```

### 10.2 False Sharing pada Counter Konkuren
*Kesalahan*: Menaruh beberapa `atomic.Uint64` berdampingan dalam satu struct statistik.
```go
// BUG PERFORMA: Terletak di satu Cache Line (16 byte < 64 byte)
type Metrics struct {
    IngressCount uint64 // Digunakan Core 1
    EgressCount  uint64 // Digunakan Core 2
}
```
*Solusi*: Tambahkan padding selebar Cache Line:
```go
type Metrics struct {
    IngressCount uint64
    _pad0        [56]byte // 8 + 56 = 64 byte isolasi penuh
    EgressCount  uint64
    _pad1        [56]byte
}
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Data Layout Alignment**: Seluruh field dalam struct telah diurutkan dari tipe terbesar (8 byte) ke terkecil (1 byte) untuk meminimalkan padding tersembunyi antar-field.
- [ ] **Zero Hot-Path Allocations**: Jalankan benchmark dengan opsi `-benchmem`. Nilai `allocs/op` pada fungsi kritis wajib bernilai `0`.
- [ ] **Pre-Sizing Capacities**: Seluruh slices, maps, atau flat arrays dialokasikan dengan parameter kapasitas awal (`cap`) yang terdefinisi sejak boot-up.
- [ ] **Hardware Concurrency Isolation**: Variabel paralel yang sering dimutasi oleh core berbeda telah di-pad dengan batasan baris cache (64-byte minimum).
- [ ] **Core Pinning**: Thread atau worker pool yang mengelola loop kalkulasi kritis telah dipertimbangkan untuk thread-affinity pinning (`runtime.LockOSThread()` pada Go).
- [ ] **P99 & Max Jitter Validation**: Testing performa tidak hanya mengukur metrik rata-rata (*mean*), tetapi wajib merekam P99, P99.9, dan latensi maksimum di bawah beban jenuh (*saturation testing*).

---

## 12. Hands-on Practice

Buat dan operasikan project praktikum berikut pada direktori kerja: `hands-on/m02/`.

### Struktur Direktori
```text
hands-on/m02/
├── go.mod
├── buffer.go
├── buffer_test.go
└── main.go
```

### Langkah 1: Inisialisasi Modul
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init enterprise/m02
```

### Langkah 2: Implementasikan `buffer.go`
Ketikkan circular ring-buffer lock-free untuk komunikasi antar-goroutine berkinerja tinggi:

```go
package main

import (
	"errors"
	"sync/atomic"
	"unsafe"
)

const CacheLine = 64

var ErrRingFull = errors.New("ring buffer is full")
var ErrRingEmpty = errors.New("ring buffer is empty")

type RingBuffer struct {
	_pad0 [CacheLine]byte
	head  uint64
	_pad1 [CacheLine - 8]byte
	tail  uint64
	_pad2 [CacheLine - 8]byte
	mask  uint64
	nodes []uint64
}

func NewRingBuffer(powerOfTwoSize uint64) *RingBuffer {
	// Pastikan ukuran merupakan pangkat dua untuk optimasi bitwise masking
	if powerOfTwoSize < 2 || (powerOfTwoSize&(powerOfTwoSize-1)) != 0 {
		powerOfTwoSize = 1024
	}
	return &RingBuffer{
		head:  0,
		tail:  0,
		mask:  powerOfTwoSize - 1,
		nodes: make([]uint64, powerOfTwoSize),
	}
}

func (rb *RingBuffer) Offer(val uint64) error {
	tail := atomic.LoadUint64(&rb.tail)
	head := atomic.LoadUint64(&rb.head)

	if (tail - head) > rb.mask {
		return ErrRingFull
	}

	rb.nodes[tail&rb.mask] = val
	atomic.StoreUint64(&rb.tail, tail+1)
	return nil
}

func (rb *RingBuffer) Poll() (uint64, error) {
	head := atomic.LoadUint64(&rb.head)
	tail := atomic.LoadUint64(&rb.tail)

	if head == tail {
		return 0, ErrRingEmpty
	}

	val := rb.nodes[head&rb.mask]
	atomic.StoreUint64(&rb.head, head+1)
	return val, nil
}
```

### Langkah 3: Implementasikan Benchmark & Test `buffer_test.go`
```go
package main

import (
	"testing"
)

func BenchmarkRingBuffer_Throughput(b *testing.B) {
	rb := NewRingBuffer(65536)
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_ = rb.Offer(uint64(i))
		_, _ = rb.Poll()
	}
}
```

### Langkah 4: Jalankan Benchmark
```bash
go test -bench=. -benchmem -cpuprofile=cpu.pprof -memprofile=mem.pprof
```
Pastikan hasil benchmark menunjukkan `0 B/op` dan `0 allocs/op`.

---

## 13. Exercise

### Level Easy: Struct Alignment Optimization
Diberikan struct unoptimized berikut:
```go
type UnoptimizedData struct {
    FlagA    bool   // 1 byte
    ID       int64  // 8 byte
    FlagB    bool   // 1 byte
    Val      int32  // 4 byte
}
```
- **Tugas**: Analisis ukuran struct asli dengan `unsafe.Sizeof()`. Susun ulang field-field struct tersebut untuk meminimalkan *padding holes* memory. Buktikan pengurangan footprint memori menggunakan unit test Go.

### Level Medium: Cache-Conscious Binary Search
Implementasikan algoritma Binary Search klasik LeetCode (`Search in Rotated Sorted Array` atau standard `Binary Search`) ke dalam bentuk **Eytzinger Layout** (Breadth-First Array Layout).
- **Tugas**: Ubah layout data array terurut menjadi tree array berbasis indeks $1$ di mana anak kiri ada di indeks $2i$ dan anak kanan di $2i+1$. Lakukan benchmark perbandingan latensi antara pencarian binary search standar vs Eytzinger layout pada array berukuran $10^7$ elemen.

### Level Hard: Striped Partitioned Cache (High-Concurrency LFU)
Rancang struktur data **LFU (Least Frequently Used) Cache** dengan kapasitas 1.000.000 entri yang mampu menangani beban baca/tulis dari 64 concurrent goroutines:
- **Batasan**: Dilarang menggunakan global `sync.Mutex` tunggal.
- **Tugas**: Terapkan teknik *Hash Partitioning / Striping* ke dalam 64 internal bucket mandiri berpadding baris cache. Pastikan eviksi LFU berjalan $O(1)$ flat allocation tanpa pointer link reallocation pada hot path.

---

## 14. Challenge

### Studi Kasus: Ultra-Low Latency Sliding Window Moving Median
Rancanglah sebuah engine komputasi streaming **Real-Time Moving Median Engine** dengan sliding window $K = 65.535$ data point terbaru:
- **Input Feed**: Aliran data network streaming via UDP dengan rate 2.000.000 event/detik (tiap data point berupa signed integer 32-bit).
- **Kebutuhan Sistem**: Setiap kali data point baru masuk, sistem harus mengembalikan nilai median saat itu juga secara deterministik.
- **Batasan Teknis Ekstrem**:
  1. **Zero Dynamic Allocation**: Setelah startup loop, runtime heap allocations harus absolut `0 allocs/op`.
  2. **Sub-Microsecond P99.9**: Pengambilan median dan mutasi window harus selesai dalam waktu kurang dari 400 nanodetik pada P99.9.
  3. **No External Libraries**: Bangun seluruh struktur data inti secara in-house (misal: modifikasi 2-Heap atau Flat Fenwick/Order-Statistic Tree).
  4. **Fault Tolerance**: Jika ada burst spike hingga 5.000.000 event/detik, engine tidak boleh crash akibat OOM (*Out of Memory*), melainkan harus memiliki strategi backpressure atau bounded degradation yang telah ditentukan secara matematis.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. Berapa ukuran umum standar satu Cache Line pada arsitektur prosesor x86-64 dan ARM64 modern?
2. Mengapa sequential array traversal jauh lebih cepat dibanding linked list traversal pada ukuran data total yang sama?
3. Apa implikasi struktural jika nilai field-field di dalam sebuah struct tidak diurutkan berdasarkan byte alignment?
4. Apakah algoritma dengan kompleksitas $O(1)$ selalu lebih cepat dibanding algoritma $O(\log N)$ di hardware nyata? Jelaskan singkat alasannya!
5. Apa yang dimaksud dengan escape analysis pada compiler bahasa dengan GC seperti Go?

### Bagian 2: Intermediate (5 Soal)
6. Jelaskan fenomena *False Sharing* dan bagaimana mekanisme protokol *Cache Coherency* menyebabkan degradasi performa pada aplikasi multi-core!
7. Mengapa array bertipe `[]Task` (value) menghasilkan beban GC mark-phase yang jauh lebih kecil dibandingkan `[]*Task` (pointer)?
8. Kapan pengalokasian memori berbasis Arena atau Slab lebih unggul dibandingkan mengandalkan OS default page allocator?
9. Apa fungsi compiler directive atau teknik padding `_ [CacheLineBytes]byte` pada implementasi concurrent queue?
10. Bagaimana branching yang tidak terprediksi (*branch misprediction*) mempengaruhi instruksi pipeline CPU pada algoritma traversing tree?

### Bagian 3: Skenario Kasus Produksi (3 Soal)
11. **Skenario A**: Tim Anda memproduksi microservice penentu rate-limit berbasis Sliding Window Log (LeetCode 362). Ketika traffic mencapai 80.000 RPS, CPU load mencapai 95% dan P99 latency meledak menjadi 350 milidetik. Profiling menunjukkan 65% CPU time dihabiskan pada fungsi `runtime.gcDrain` dan `runtime.mallocgc`. Langkah apa yang harus diambil untuk merombak algoritma tersebut?
12. **Skenario B**: Anda memiliki Hash Table konkuren yang diproteksi oleh `sync.RWMutex`. Pengujian benchmarking pada mesin 4-core menunjukkan skala linier yang baik, namun saat dideploy pada cloud compute instance dengan 64 core, performa turun 80% meskipun rasio read:write adalah 95%:5%. Analisis akar masalah arsitektural hardware yang terjadi!
13. **Skenario C**: Sebuah sistem matching engine order book mengalami jitter latensi periodik setiap 2 menit sekali selama rentang waktu 2 milidetik. Setelah diinvestigasi, tidak ada alokasi baru di stack trace hot-path. Hal sistemik/hardware apa di luar kode aplikasi (OS/Memory) yang dapat memicu fenomena ini pada runtime level?

---

## Kunci Jawaban & Panduan Solusi Quiz

### Bagian 1: Basic
1. **64 Byte**. Seluruh transfer data antara memori utama dan L1/L2/L3 cache dipaketkan dalam blok 64 byte.
2. Karena **Spatial Locality** dan **Hardware Prefetcher**. Mengakses elemen sequential di array secara otomatis memicu prefetch data berikutnya ke dalam L1 cache, menghindari latency stall DRAM. Linked list memiliki node yang terfragmentasi di berbagai virtual address acak.
3. Menghasilkan **Memory Padding Holes**. Compiler terpaksa menyisipkan byte kosong tak terpakai di antara field demi memenuhi batasan alignment arsitektur (misal int64 harus berada di alamat memori kelipatan 8), sehingga ukuran struct membesar secara sia-sia.
4. **Tidak selalu**. Konstanta riil pada $O(1)$ yang melibatkan cache miss, pointer indirection, atau hash computation yang rumit bisa membutuhkan ratusan siklus CPU, sedangkan $O(\log N)$ dengan branch prediction dan data contiguous di cache line dapat selesai dalam hitungan nanodetik.
5. Proses statis yang dijalankan compiler untuk menentukan apakah suatu variabel memori dapat dialokasikan dengan aman di **Stack frame** atau harus "kabur" dialokasikan di **Heap**.

### Bagian 2: Intermediate
6. False Sharing terjadi ketika dua thread pada core berbeda memodifikasi variabel berbeda yang kebetulan berbagi Cache Line 64-byte yang sama. Protokol MESI/MOESI terpaksa terus-menerus membatalkan (*invalidate*) cache line di core rival, menyebabkan memory-stall konstan seolah-olah terjadi perebutan lock.
7. `[]Task` adalah satu blok memori flat tanpa referensi objek internal, sehingga GC hanya melihatnya sebagai **satu objek utuh**. Sebaliknya, `[]*Task` berisi ribuan pointer yang masing-masing harus di-dereference dan ditelusuri (*mark phase*) oleh GC satu demi satu, melipatgandakan waktu pause GC.
8. Ketika aplikasi melakukan alokasi dan dealokasi jutaan objek kecil dengan lifecycle pendek secara berulang-ulang, Arena/Slab mengeliminasi alokasi sistemik berulang dan meniadakan fragmentasi memori heap.
9. Memisahkan variabel state yang dimutasi oleh core berbeda ke batas cache line yang berbeda (memaksa address offset berjarak minimal 64 byte), secara total mencegah fenomena *False Sharing*.
10. CPU menerapkan *Instruction Pipelining* dan *Speculative Execution*. Ketika branch predictor gagal menebak arah lompatan algoritma (misal pada traversal tree dengan kondisi node acak), seluruh pipeline instruksi yang telah dieksekusi harus dibatalkan (*pipeline flush*), menyebabkan penundaan 15–20 siklus CPU per tebakan meleset.

### Bagian 3: Skenario Kasus Produksi
11. **Solusi Skenario A**: Ganti struktur data linked-list/slice pointer individual dengan **Circular Flat Array (Ring Buffer) dengan Sliding Bucket / Bitwise Histogram** yang di-pre-alokasikan di awal. Simpan timestamp dalam flat primitive array (`[]int64`), hilangkan alokasi objek per-request, dan gunakan sliding window counter dengan bucket beresolusi 1 detik sehingga `allocs/op = 0`.
12. **Solusi Skenario B**: Terjadi **Cache Line Bouncing** pada read-lock counter `sync.RWMutex`. Meskipun pembaca tidak memodifikasi data bisnis, setiap kali `RLock()` dipanggil, thread harus memperbarui counter atomic pembaca internal mutex. Pada 64 core, operasi atomik ini memicu perebutan baris cache atomic secara masif di bus CPU. Solusinya: Ubah arsitektur menggunakan **Read-Copy-Update (RCU)** atau **Concurrent Hash Striping (64+ shard independen)** agar thread pembaca tidak memutasi counter di cache line yang sama.
13. **Solusi Skenario C**: Kemungkinan akar masalah:
    - **OS Transparent Huge Pages (THP) Compaction**: Kernel OS melakukan defragmentasi alokasi halaman memori 2MB di background.
    - **Kernel Page Faults / Memory Ballooning** pada lingkungan virtualisasi/container.
    - **CPU Thermal Throttling** atau context switching dari background daemon OS yang tidak diisolasi.
    *Mitigasi*: Matikan THP (`echo never > /sys/kernel/mm/transparent_hugepage/enabled`), atur CPU Governor ke mode `performance`, dan isolasi core CPU untuk container/proses tersebut via `cpuset cgroups`.

---

## 16. Summary

Menguasai algoritma di atas kertas atau platform pengujian seperti LeetCode adalah fondasi mutlak penalaran computational complexity. Namun, untuk membangun sistem berskala enterprise yang menangani jutaan transaksi per detik dengan latensi konsisten sub-milidetik, seorang *Senior Software Engineer* wajib memahami batasan fisik hardware tempat algoritma tersebut dieksekusi.

Transisi dari **Teori Komputasi** ke **Sistem Produksi Berperforma Tinggi** bertumpu pada tiga pilar inti:
1. **Mechanical Sympathy**: Menata layout data secara sequential/flat untuk mengoptimalkan L1/L2/L3 CPU Caching dan instruction prefetching.
2. **Zero-Allocation Mindset**: Menekan alokasi heap dinamis pada hot path untuk membebaskan sistem dari latensi *Stop-The-World* Garbage Collector.
3. **Hardware-Aware Concurrency**: Memitigasi *False Sharing* via cache padding, memecah kontensi lock via partitioning, dan memanfaatkan operasi atomik secara bijak.