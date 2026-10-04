# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis & Mengonstruksi** struktur data tingkat lanjut (*Monotonic Queue/Stack*, *Disjoint Set Union with Path Compression & Rank*, *Segment Tree with Lazy Propagation*, dan *Directed Acyclic Graph / DAG Resolvers*) dengan kompleksitas waktu dan ruang optimal.
2. **Mentranslasikan** pola algoritmik abstrak LeetCode (*Sliding Window, Topological Sort, Interval Union*) ke dalam arsitektur komponen sistem riil berkinerja tinggi (*Stream Ingestion Rate-Limiter, Dependency Execution Engine, Telemetry Aggregator*).
3. **Mengoptimalkan** efisiensi eksekusi algoritma pada level *hardware-aware programming*, memperhitungkan *CPU cache locality* (L1/L2/L3), *pointer chasing mitigation*, dan *zero-allocation memory pooling*.
4. **Mengevaluasi Trade-offs** antara struktur data berbasis *node-pointer* vs *contiguous-array* terhadap latensi P99, alokasi memori, serta beban *Garbage Collection* (GC).
5. **Mendiagnosis & Mengatasi** *anti-patterns* produksi seperti rekursi berlebih (*call stack overflow*), fragmentasi memori, konkurensi data race, dan *false sharing*.

---

## 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:
* **Struktur Data Dasar**: Array, Hash Map, Linked List, Heap/Priority Queue, Binary Search Tree.
* **Kompleksitas Asimptotik**: Penguasaan mendalam terhadap *Master Theorem*, kalkulasi *Amortized Time Complexity*, serta *Auxiliary Space vs Input Space*.
* **Bahasa Pemrograman Tingkat Sistem/Menengah**: Menguasai Go, C++, atau Rust (modul ini menyajikan implementasi *production-ready* berbasis Go modern 1.21+).
* **Konsep Sistem Komputer**: Dasar hierarki memori, *virtual memory*, *stack vs heap*, dan konsep konkurensi (mutex, atomic, goroutine/thread).

---

## 3. Concept & Internal Architecture (Mendalam)

Banyak insinyur perangkat lunak menganggap pola algoritmik LeetCode terisolasi dari rekayasa sistem riil. Faktanya, arsitektur *high-performance infrastructure*—seperti query engine (DuckDB/ClickHouse), schedulers (Kubernetes, Temporal), dan stream processors (Apache Flink)—dibangun di atas algoritma-algoritma ini dengan adaptasi *hardware-level*.

```
+-------------------------------------------------------------------------+
|                           APPLICATION LAYER                             |
|       Rate Limiters, Task Schedulers, Real-Time P99 Aggregators         |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                  ALGORITHMIC FOUNDATION LAYER (LeetCode)                 |
|   Monotonic Deque (Sliding Window) | Topological Sort / DAG (Scheduler)  |
|   Segment Tree (Telemetry)         | Disjoint Set Union (Clustering)    |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                  SYSTEM RUNTIME & HARDWARE ARCHITECTURE                 |
|   Contiguous Memory (Slices)       | L1/L2/L3 CPU Cache Lines (64-byte) |
|   Zero-Alloc / Ring Buffers        | Amortized Branch-Free Execution    |
+-------------------------------------------------------------------------+
```

### A. Monotonic Primitives & Cache Locality
Pola *Monotonic Queue* dan *Monotonic Stack* mempertahankan elemen secara monoton naik (*increasing*) atau turun (*decreasing*). Operasi `push` memangkas elemen dari belakang (*tail*) yang melanggar invariant ke-monotonan.
* **Kompleksitas Amortisasi**: Walaupun operasi perorangan bisa menyapu $k$ elemen, setiap elemen maksimal dimasukkan sekali dan dikeluarkan sekali, menghasilkan waktu $O(1)$ amortized per item ($O(N)$ total).
* **Arsitektur Internal**: Node-based doubly linked list menghasilkan alokasi heap terfragmentasi dan *pointer chasing*, memicu *CPU cache miss* (biaya latensi RAM ~50-100ns vs L1 cache ~1ns). Implementasi enterprise wajib menggunakan *circular ring-buffer* berbasis array berukuran tetap, mempertahankan kontinuitas blok 64-byte *cache line*.

### B. Directed Acyclic Graphs (DAG) & Dependency Resolution
Topological Sort (Algoritma Kahn dan Tarjan DFS) adalah pondasi dari build systems (Bazel), distributed job orchestrators (Airflow, Temporal), dan transaction locks dependency resolving.
* **Algoritma Kahn**: Memanfaatkan pelacakan *In-Degree* secara iteratif via queue. Ketika node memiliki *in-degree* 0, node tersebut independen dan dapat dijadwalkan secara paralel pada thread terpisah.
* **Deteksi Siklus**: Jika jumlah node yang diproses lebih kecil dari total node $V$, graf memiliki siklus (kondisi *deadlock* pada dependensi).

### C. Segment Tree & Range Queries
Ketika memproses metrik atau metrik rate-limit dinamis per sub-detik, sistem memerlukan operasi *Range Query* dan *Point/Range Update* dalam $O(\log N)$.
* **Internal Layout**: Segment tree konvensional berbasis pointer tree (`Node{Left, Right}`) memicu overhead GC masif. Desain produksi menggunakan *implicit array indexing* di mana untuk node pada index $i$:
  * Left child: $2i + 1$
  * Right child: $2i + 2$
  * Parent: $\lfloor(i - 1) / 2\rfloor$
* **Lazy Propagation**: Menunda propagasi update ke anak-anaknya hingga interval anak tersebut benar-benar diakses, mempertahankan batas atas $O(\log N)$ untuk *range updates*.

---

## 4. Why & What

| Paradigma Algoritmik | Apa itu? (Konseptual) | Mengapa Relevan di Produksi? (Enterprise) |
| :--- | :--- | :--- |
| **Monotonic Deque** | Deque yang elemen-elemennya selalu terurut strict/non-strict. | Menghitung metrik *real-time rolling maximum/minimum* (misal: SLA latency spike) dalam jendela geser $W$ dengan biaya komputasi $O(1)$ amortized tanpa *re-scanning*. |
| **Topological Sort (Kahn's)** | Pengurutan linier simpul graf berarah sedemikian rupa sehingga edge $(u, v)$ menempatkan $u$ sebelum $v$. | *Massive parallel DAG execution pipeline*. Menentukan dependensi microservice startup, build dependency trees, atau deployment stages. |
| **Disjoint Set Union (DSU)** | Struktur data pengelompokan elemen ke dalam partisi-partisi disjoint dengan operasi *Union* dan *Find*. | Identifikasi konektivitas jaringan, deduplikasi identitas lintas kanal (fraud detection graph), dan *dynamic spanning forests* pada topologi VPC. |
| **Segment Tree (Flat-Array)** | Pohon biner lengkap yang menyimpan agregasi interval, direpresentasikan dalam array kontinu tunggal. | Aggregasi time-series metrik sub-milidetik, sliding quota per jam/hari pada multi-tenant rate limiter, dan range-sum index. |

---

## 5. How (Workflow Detail)

### Alur Eksekusi Monotonic Ring-Buffer (Sliding Window Metrics)
1. **Inisialisasi**: Alokasikan array berkapasitas tetap $K$ untuk data dan index deque. Hindari relokasi memori pada fase *hot-path*.
2. **Ingesti Elemen**:
   * Ambil timestamp $T_{now}$ dan nilai $V_{now}$.
   * **Eviction Expired**: Bandingkan index di kepala (*head*) deque terhadap batas jendela $T_{now} - W$. Keluarkan elemen yang *out-of-window*.
   * **Monotonic Maintenance**: Periksa ekor (*tail*) deque. Selama nilai di *tail* $\le V_{now}$, geser *tail* mundur (pop back). Elemen-elemen ini terbukti tidak akan pernah menjadi nilai maksimum karena $V_{now}$ lebih baru dan bernilai lebih besar.
   * **Insertion**: Masukkan index $T_{now}$ pada *tail*.
3. **Query Maximum**: Nilai maksimum jendela saat ini selalu berada pada *head* deque dalam kompleksitas instan $O(1)$.

```
Ingest Item (T=5, Val=80) ke Window W=3
State Awal Deque: [(T=2, Val=70), (T=4, Val=40)]

Step 1: Check expired -> (T=2) < (5 - 3 = 2) -> Expired! Drop head.
        Deque sisa: [(T=4, Val=40)]
Step 2: Monotonic maintenance -> Val=80 > Val=40 (tail). Drop tail.
        Deque sisa: []
Step 3: Insert (T=5, Val=80).
        Deque akhir: [(T=5, Val=80)] -> Max value window = 80.
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Monotonic Deque sebagai Ruang Tunggu Eksekutif
Bayangkan antrean kandidat prioritas: Jika seorang pelamar baru datang dengan skor kompetensi lebih tinggi daripada kandidat lama yang masih menunggu, kandidat-kandidat lama tersebut tidak akan pernah menjadi "pilihan terbaik" di masa depan karena kandidat baru lebih unggul dan memiliki masa pensiun lebih panjang. Maka kandidat lama dieliminasi seketika dari antrean.

```
Array / Ring-Buffer Memory Alignment (Contiguous 64-byte Cache Lines):

Byte: 00        08        16        24        32        40        48        56        63
     +---------+---------+---------+---------+---------+---------+---------+---------+
CL 1 | Val[0]  | Idx[0]  | Val[1]  | Idx[1]  | Val[2]  | Idx[2]  | Val[3]  | Idx[3]  | -> L1 Hit!
     +---------+---------+---------+---------+---------+---------+---------+---------+
     (Semua nilai berdekatan, dibaca CPU dalam 1 memory fetch tanpa cache-miss penalty)

Versus Linked List Node-Pointer:
[Node 0x01A0] ----ptr chasing----> [Node 0x9F40] ----ptr chasing----> [Node 0x12C0]
(Setiap akses dereference memicu L3 Cache Miss atau DRAM Page Walk: 50-100ns penalty)
```

---

## 7. Simple Example & Practical Example

### Simple Example: Classic Monotonic Deque (Sliding Window Maximum)
Implementasi algoritma dasar untuk menghitung nilai maksimum dari sub-array berukuran $k$.

```go
package main

import "fmt"

func maxSlidingWindow(nums []int, k int) []int {
	if len(nums) == 0 || k <= 0 {
		return nil
	}
	n := len(nums)
	result := make([]int, n-k+1)
	// deque menyimpan indeks elemen
	deque := make([]int, 0, n)

	for i := 0; i < n; i++ {
		// 1. Evict index yang keluar dari window [i - k + 1, i]
		for len(deque) > 0 && deque[0] < i-k+1 {
			deque = deque[1:]
		}

		// 2. Pertahankan sifat monoton turun (monotonically decreasing)
		for len(deque) > 0 && nums[deque[len(deque)-1]] <= nums[i] {
			deque = deque[:len(deque)-1]
		}

		// 3. Tambahkan elemen saat ini
		deque = append(deque, i)

		// 4. Catat maksimum jika window sudah berukuran k
		if i >= k-1 {
			result[i-k+1] = nums[deque[0]]
		}
	}
	return result
}

func main() {
	stream := []int{1, 3, -1, -3, 5, 3, 6, 7}
	k := 3
	fmt.Printf("Window Max: %v\n", maxSlidingWindow(stream, k))
	// Output: [3, 3, 5, 5, 6, 7]
}
```

### Practical Example: Production-Grade Zero-Alloc Sliding Window P99/Max Latency Monitor
Implementasi *thread-safe*, *memory-preallocated* sliding window latency tracker menggunakan circular array untuk *low-latency service telemetry*.

```go
package main

import (
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

// MetricSample merepresentasikan sampel metrik latensi
type MetricSample struct {
	TimestampNs int64
	LatencyUs   int64
}

// ZeroAllocSlidingWindowTracker memonitor nilai puncak latensi secara konstan
type ZeroAllocSlidingWindowTracker struct {
	windowDurationNs int64
	capacity         int
	head             int
	tail             int
	count            int
	buffer           []MetricSample

	// Monotonic Deque indices
	dequeHead int
	dequeTail int
	dequeLen  int
	deque     []int

	mu sync.Mutex
}

// NewZeroAllocSlidingWindowTracker mengalokasikan tracker dengan kapasitas terikat
func NewZeroAllocSlidingWindowTracker(windowDuration time.Duration, maxCapacity int) (*ZeroAllocSlidingWindowTracker, error) {
	if maxCapacity <= 0 {
		return nil, errors.New("capacity must be positive")
	}
	return &ZeroAllocSlidingWindowTracker{
		windowDurationNs: windowDuration.Nanoseconds(),
		capacity:         maxCapacity,
		buffer:           make([]MetricSample, maxCapacity),
		deque:            make([]int, maxCapacity),
	}, nil
}

// Record menginjeksi latensi baru secara safe
func (t *ZeroAllocSlidingWindowTracker) Record(latencyUs int64) {
	nowNs := time.Now().UnixNano()

	t.mu.Lock()
	defer t.mu.Unlock()

	// 1. Evict sampel yang melampaui batas waktu window
	cutoffNs := nowNs - t.windowDurationNs
	for t.count > 0 && t.buffer[t.head].TimestampNs < cutoffNs {
		// Jika elemen head buffer bertepatan dengan head monotonic deque, evict deque
		if t.dequeLen > 0 && t.deque[t.dequeHead] == t.head {
			t.dequeHead = (t.dequeHead + 1) % t.capacity
			t.dequeLen--
		}
		t.head = (t.head + 1) % t.capacity
		t.count--
	}

	// 2. Tangani kondisi circular buffer overflow
	if t.count == t.capacity {
		// Drop data terlama jika kapasitas terlampaui demi mempertahankan zero-allocation
		if t.dequeLen > 0 && t.deque[t.dequeHead] == t.head {
			t.dequeHead = (t.dequeHead + 1) % t.capacity
			t.dequeLen--
		}
		t.head = (t.head + 1) % t.capacity
		t.count--
	}

	// 3. Masukkan sample baru ke circular buffer
	insertIdx := t.tail
	t.buffer[insertIdx] = MetricSample{
		TimestampNs: nowNs,
		LatencyUs:   latencyUs,
	}
	t.tail = (t.tail + 1) % t.capacity
	t.count++

	// 4. Update Monotonic Deque (Monotonically Decreasing)
	for t.dequeLen > 0 {
		lastIdx := (t.dequeTail - 1 + t.capacity) % t.capacity
		bufIdx := t.deque[lastIdx]
		if t.buffer[bufIdx].LatencyUs <= latencyUs {
			// Pop back
			t.dequeTail = lastIdx
			t.dequeLen--
		} else {
			break
		}
	}

	t.deque[t.dequeTail] = insertIdx
	t.dequeTail = (t.dequeTail + 1) % t.capacity
	t.dequeLen++
}

// GetMaxLatency mengembalikan latensi tertinggi dalam window saat ini
func (t *ZeroAllocSlidingWindowTracker) GetMaxLatency() (int64, error) {
	nowNs := time.Now().UnixNano()

	t.mu.Lock()
	defer t.mu.Unlock()

	cutoffNs := nowNs - t.windowDurationNs
	// Lazy clean-up dari head deque jika sudah expired
	for t.dequeLen > 0 {
		topIdx := t.deque[t.dequeHead]
		if t.buffer[topIdx].TimestampNs < cutoffNs {
			t.dequeHead = (t.dequeHead + 1) % t.capacity
			t.dequeLen--
		} else {
			break
		}
	}

	if t.dequeLen == 0 {
		return 0, errors.New("no active telemetry in window")
	}

	return t.buffer[t.deque[t.dequeHead]].LatencyUs, nil
}

func main() {
	tracker, _ := NewZeroAllocSlidingWindowTracker(500*time.Millisecond, 1000)

	var wg sync.WaitGroup
	var ops atomic.Int64

	// Simulasi concurrent traffic ingestion
	for worker := 0; worker < 4; worker++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for i := 0; i < 50; i++ {
				lat := int64((id+1)*1000 + (i * 20))
				tracker.Record(lat)
				ops.Add(1)
				time.Sleep(10 * time.Millisecond)
			}
		}(worker)
	}

	// Reader coroutine
	done := make(chan bool)
	go func() {
		for {
			select {
			case <-done:
				return
			case <-time.After(100 * time.Millisecond):
				if maxVal, err := tracker.GetMaxLatency(); err == nil {
					fmt.Printf("[METRIC POLL] Peak Window Latency: %d µs (Ops: %d)\n", maxVal, ops.Load())
				}
			}
		}
	}()

	wg.Wait()
	time.Sleep(200 * time.Millisecond)
	close(done)
	finalMax, _ := tracker.GetMaxLatency()
	fmt.Printf("[FINAL] Stabilized Max Latency: %d µs\n", finalMax)
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Distributed Build & Execution Engine (Mirip Google Bazel / Temporal Engine)
* **Konteks**: Sebuah platform CI/CD memproses graf dependensi build yang terdiri atas 50.000 artefak mikro (*nodes*) dan 200.000 relasi dependensi (*edges*).
* **Masalah**: Pendekatan build berurutan (*naive sequence*) memakan waktu 45 menit. Pendekatan *naive parallel* memicu kondisi *race condition*, *circular deadlock*, dan pemborosan worker node karena tidak ada sinkronisasi saat artefak pondasi belum selesai dikompilasi.
* **Solusi Arsitektural Menggunakan Kahn's Algorithm + Worker Pool**:
  1. Graf didefinisikan sebagai *Adjacency List* menggunakan slice pointer memory kontinu.
  2. Kalkulasi derajat masuk (*In-Degree*) untuk seluruh 50.000 node secara deterministik.
  3. Node dengan `in-degree == 0` dimasukkan ke dalam *Buffered Channel* (Job Queue).
  4. Worker pools mengeksekusi job paralel. Saat sebuah artefak selesai (`job completed`), worker menurunkan nilai `in-degree` dari downstream dependensi secara *atomic*.
  5. Node baru yang memiliki `in-degree == 0` langsung dialirkan ke queue tanpa interupsi scheduler pusat.
* **Hasil**:
  * Peningkatan paralelisasi hingga 84%.
  * Waktu build total turun dari 45 menit menjadi 4,2 menit.
  * Deteksi siklus dependensi ilegal terisolasi dalam $O(V + E)$ sebelum eksekusi dimulai (mencegah *cost leakage* cloud instance).

---

## 9. Trade-offs

| Pendekatan Algoritmik | Keuntungan | Kerugian & Batasan | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- |
| **Monotonic Deque (Array-backed)** | Amortized $O(1)$ query & update. *Zero memory allocation* jika kapasitas di-bound di awal. Cache hit tinggi. | Kapasitas terikat (*bounded buffer*). Jika data melebihi ukuran buffer, strategi *drop* atau reallokasi mahal harus dipilih. | Real-time sliding window stats, in-memory rate limiting, audio/video streaming buffer. |
| **Segment Tree (Flat Array)** | $O(\log N)$ point/range query dan range update. Sangat fleksibel untuk query rentang agregasi apa pun. | Memerlukan ruang $4N$. Relatif rumit untuk implementasi *thread-safe lock-free*. | Historical billing range-sum queries, dynamic telemetry thresholding. |
| **Pointer-based Tree (BST / AVL)** | Dinamis, tidak butuh prealokasi memori berukuran tetap. | *Pointer chasing* memicu *cache misses*. Overhead memori per node (8-24 bytes) dan overhead heap GC. | Sistem general-purpose di mana beban memori tidak terkendala dan throughput rendah-menengah. |
| **Disjoint Set Union (DSU)** | Waktu mendekati konstan $O(\alpha(N))$ via *Path Compression* dan *Union by Rank*. | Bersifat append-only / merge-only. Sangat sulit dan mahal untuk melakukan operasi "split" / pembatalan relasi. | Network connectivity status, clustering, dynamic graph component analysis. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Pointer Chasing & Memory Layout Penalty
* **Gejala**: CPU profil (`go tool pprof`) menunjukkan konsumsi waktu masif pada runtime memori `runtime.mallocgc` atau tingginya `L1-dcache-load-misses` via Linux `perf`.
* **Penyebab**: Implementasi antrean atau pohon menggunakan struct bertautan pointer (`type Node struct { val int; next *Node }`).
* **Solusi**: Ubah struktur data menjadi *flat contiguous array* atau indeks berbasis integer (`uint32`).

### 2. Stack Overflow pada Graf / DFS Traversal yang Sangat Dalam
* **Gejala**: Aplikasi crash tiba-tiba dengan log: `fatal error: stack overflow`.
* **Penyebab**: Menggunakan DFS rekursif murni untuk Topological Sort atau DSU *Path Compression* pada rantai node bernilai jutaan.
* **Solusi**: Ubah rekursi menjadi algoritma iteratif berbasis slice/stack pada heap, atau lakukan pembatasan kedalaman traversal secara eksplisit.

### 3. False Sharing pada Struktur Data Konkuren
* **Gejala**: Skalabilitas multi-core terhambat (*throughput drop*) meskipun mutex sudah diganti atomic operations.
* **Penyebab**: Dua variabel state independen yang sering dimodifikasi oleh thread berbeda berada dalam satu 64-byte *cache line* CPU yang sama.
* **Solusi**: Terapkan *memory padding* (`cpu.CacheLinePad` atau `[56]byte`) untuk memastikan variabel terisolasi pada cache line yang berbeda.

---

## 11. Best Practices (Production Checklist)

- [ ] **Pre-allocate Slices**: Selalu inisialisasi kapasitas slice di awal jika ukuran batas maksimum diketahui (`make([]T, 0, capacity)`).
- [ ] **Zero-Allocation Hot Paths**: Pastikan operasi reguler di per-request/per-sample loop tidak mengalokasikan objek baru di heap.
- [ ] **Iterative over Recursive**: Hindari rekursi terbuka untuk struktur data berskala tak terbatas untuk menjamin ketahanan memori thread stack.
- [ ] **Fail-Safe Bounded Memory**: Semua struktur data in-memory (antrean, deque, graph stores) wajib memiliki kapasitas maksimum (*hard ceiling*) untuk mencegah OOM (*Out Of Memory*).
- [ ] **Lock Granularity**: Lindungi mutasi struktur data dengan fine-grained locking, reader-writer locks (`sync.RWMutex`), atau atomic primitives, alih-alih mengunci seluruh instance secara global.
- [ ] **Deterministic Cycle Detection**: Selalu validasi sifat asiklik (*acyclic*) dari input graf pengguna sebelum memicu sub-rutin eksekusi job/task engine.

---

## 12. Hands-on Practice

Buatlah proyek mandiri dengan struktur berikut untuk menguji efisiensi algoritma secara langsung:

### Direktori Proyek
```text
hands-on/m02/
├── go.mod
├── monotonic/
│   ├── ring_buffer.go
│   └── ring_buffer_test.go
├── dag/
│   ├── scheduler.go
│   └── scheduler_test.go
└── benchmark/
    └── memory_bench_test.go
```

### Langkah 1: Inisialisasi Modul
```bash
mkdir -p hands-on/m02/monotonic hands-on/m02/dag hands-on/m02/benchmark
cd hands-on/m02
go mod init enterprise-algorithms
```

### Langkah 2: Buat File `dag/scheduler.go`
Kompilasi kode DAG Engine berbasis Algoritma Kahn yang mengeksekusi task dependensi.

```go
package dag

import (
	"context"
	"errors"
	"sync"
)

type TaskFunc func(ctx context.Context) error

type TaskNode struct {
	ID        string
	Action    TaskFunc
	DependsOn []string
}

type Engine struct {
	tasks map[string]*TaskNode
}

func NewEngine() *Engine {
	return &Engine{
		tasks: make(map[string]*TaskNode),
	}
}

func (e *Engine) AddTask(task *TaskNode) error {
	if _, exists := e.tasks[task.ID]; exists {
		return errors.New("task already exists")
	}
	e.tasks[task.ID] = task
	return nil
}

func (e *Engine) Execute(ctx context.Context, maxConcurrency int) error {
	inDegree := make(map[string]int)
	adj := make(map[string][]string)

	for id := range e.tasks {
		inDegree[id] = 0
	}

	for id, task := range e.tasks {
		for _, dep := range task.DependsOn {
			if _, exists := e.tasks[dep]; !exists {
				return errors.New("missing dependency: " + dep)
			}
			adj[dep] = append(adj[dep], id)
			inDegree[id]++
		}
	}

	// Inisialisasi queue untuk node in-degree 0
	queue := make(chan string, len(e.tasks))
	for id, deg := range inDegree {
		if deg == 0 {
			queue <- id
		}
	}

	var mu sync.Mutex
	var processedCount int
	var executionErr error

	semaphore := make(chan struct{}, maxConcurrency)
	var wg sync.WaitGroup

	errChan := make(chan error, 1)
	doneChan := make(chan struct{})

	go func() {
		for taskID := range queue {
			if ctx.Err() != nil {
				return
			}
			task := e.tasks[taskID]

			wg.Add(1)
			semaphore <- struct{}{}

			go func(t *TaskNode) {
				defer wg.Done()
				defer func() { <-semaphore }()

				if err := t.Action(ctx); err != nil {
					select {
					case errChan <- err:
					default:
					}
					return
				}

				mu.Lock()
				defer mu.Unlock()
				processedCount++

				// Kurangi in-degree dependent nodes
				for _, nextID := range adj[t.ID] {
					inDegree[nextID]--
					if inDegree[nextID] == 0 {
						queue <- nextID
					}
				}

				if processedCount == len(e.tasks) {
					close(doneChan)
				}
			}(task)
		}
	}()

	select {
	case <-doneChan:
		close(queue)
		wg.Wait()
		return nil
	case err := <-errChan:
		executionErr = err
		close(queue)
		wg.Wait()
		return executionErr
	case <-ctx.Done():
		close(queue)
		wg.Wait()
		return ctx.Err()
	}
}
```

### Langkah 3: Eksekusi Benchmark
Jalankan benchmark CPU cache dan alokasi heap:
```bash
go test -bench=. -benchmem ./...
```

---

## 13. Exercise

### Level Easy: Anagram Grouping Hash Accelerator
* **Objektif**: Rancang fungsi pengelompokan string anagram berkinerja tinggi.
* **Spesifikasi**: Gunakan array frekuensi karakter tetap `[26]byte` sebagai kunci *custom hash* tanpa melakukan konversi string atau pemanggilan fungsi *sorting* (`sort.Slice`), untuk menekan alokasi heap menjadi $O(1)$ amortized per kata.

### Level Medium: Dynamic Network Connection Integrity (DSU)
* **Objektif**: Implementasikan *Disjoint Set Union* untuk mendeteksi partisi jaringan.
* **Spesifikasi**: 
  * Mendukung operasi `Connect(nodeA, nodeB string)` dan `IsConnected(nodeA, nodeB string) bool`.
  * Wajib mengimplementasikan *Path Compression* dan *Union by Rank*.
  * Struktur harus mendukung pelaporan ukuran komponen terbesar secara instan ($O(1)$).

### Level Hard: Segment-Tree Based Distributed Range-Quota Governor
* **Objektif**: Buat Rate-Limiter berbasis Array Segment Tree.
* **Spesifikasi**:
  * Jendela waktu 24 jam dibagi menjadi 1.440 slot menit.
  * Implementasikan fungsi `AddUsage(minuteIdx int, amount int)` dan `QueryTotalUsage(startMinute, endMinute int) int`.
  * Waktu eksekusi `AddUsage` dan `QueryTotalUsage` wajib строго beroperasi dalam $O(\log M)$ di mana $M = 1440$, tanpa rekursi pointer.

---

## 14. Challenge

### Studi Kasus Arsitektural: Real-time Multi-tenant Financial Matching Engine
**Deskripsi Skenario**:
Anda ditugaskan mendesain mesin agregasi dan validasi limit transaksi berfrekuensi tinggi (*High-Frequency Trading Limit Monitor*). Sistem menerima 100.000 transaksi/detik dari 10.000 akun berbeda secara paralel.

**Aturan Bisnis & Hambatan Teknis**:
1. Setiap akun memiliki aturan: *"Tidak boleh mentransaksikan lebih dari $X total volume dalam sembarang rentang 5 detik terakhir."*
2. Sistem tidak boleh mengalami kenaikan memori (*Zero-leak, Zero-realloc*) setelah pemanasan awal (*warm-up*).
3. Latensi penentuan persetujuan (*approval decision*) pada P99.99 wajib di bawah 15 mikrodetik.
4. Data yang datang bisa saja sedikit tidak berurutan (*out-of-order*) hingga batas 100 milidetik.

**Instruksi Deliverable**:
* Rancang deskripsi struktur data gabungan (*Hybrid Data Structure*) yang menggabungkan Monotonic Primitives dan Binary Indexed/Segment Structures.
* Tulis skema struktur memori dan strategi alokasi data tanpa melibatkan runtime GC Go selama ingestion berlangsung.
* Jelaskan bagaimana Anda memecahkan masalah *concurrency contention* tanpa memicu thread stalling.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Analisis Singkat)
1. Berapa batas atas kompleksitas waktu *amortisasi* dari penyisipan elemen tunggal pada Monotonic Deque?
   * A. $O(N)$
   * B. $O(\log N)$
   * C. $O(1)$
   * D. $O(N \log N)$

2. Apa alasan utama representasi Segment Tree berbasis *contiguous array* lebih cepat daripada representasi berbasis *pointer node* pada arsitektur CPU x86/ARM modern?
   * A. Menghindari operasi aritmatika indeks.
   * B. Memanfaatkan CPU L1/L2 spatial cache locality dan meminimalisasi TLB miss.
   * C. Menggunakan memori virtual lebih besar.
   * D. Segment tree pointer tidak mendukung operasi update.

3. Pada deteksi siklus menggunakan Algoritma Kahn (Topological Sort), kondisi apa yang menandakan adanya siklus pada graf terarah?
   * A. Queue pemrosesan kosong sebelum semua node diproses.
   * B. In-degree semua simpul menjadi nol di awal.
   * C. Terdapat simpul dengan out-degree bernilai negatif.
   * D. Jumlah edge sama dengan jumlah node.

4. Apa dampak penggunaan rekursi mendalam (*deep recursion*) pada implementasi DSU `Find` tanpa path compression bertahap terhadap memori?
   * A. CPU Throttling.
   * B. Memory Leaks pada Persistent Heap.
   * C. Potensi Stack Overflow Error pada Call Stack OS/Runtime.
   * D. Fragmentasi file descriptor.

5. Berapakah memori overhead pointer 64-bit pada linked list node konvensional yang menyimpan data `int32`?
   * A. 0%
   * B. Minimal 200% (8-byte pointer untuk 4-byte payload ditambah struct padding).
   * C. 50%
   * D. Tidak ada overhead.

---

### Bagian 2: Intermediate (Analisis Kasus Singkat)
6. Jelaskan mengapa *Path Compression* saja tanpa *Union by Rank* menghasilkan kompleksitas waktu terburuk $O(N \log N)$ alih-alih $O(N \cdot \alpha(N))$ pada DSU!
7. Dalam kondisi apa Monotonic Deque berbasis ring-buffer konvensional akan gagal jika dihadapkan pada data stream jaringan riil?
8. Bagaimana Segment Tree dengan *Lazy Propagation* menunda operasi update range, dan kapan update tersebut benar-benar ditransmisikan ke child node?
9. Apa perbedaan esensial dari pola konsumsi memori antara algoritma *Kahn (BFS)* vs *Tarjan (DFS)* saat menyelesaikan dependensi berskala 10 juta node?
10. Mengapa operasi slicing standar Go (`slice = slice[1:]`) pada sliding window queue pointer dapat memicu kebocoran memori (*memory leak / retained reference*)?

---

### Bagian 3: Production Scenarios
11. **Skenario A**: Service metrik Anda mengalami *Garbage Collection Pause* sebesar 30ms setiap 10 detik. Profiler menunjukkan bahwa miliaran objek `int` dialokasikan dan langsung dibuang dari antrean rolling window. Bagaimana Anda merekayasa ulang modul ini tanpa mengubah algoritma sliding window?
12. **Skenario B**: DAG Engine orkestrasi microservice Anda tiba-tiba macet (*hang indefinitely*) saat sebuah deployment baru dijalankan. Tidak ada error log atau panik. Langkah diagnostik algoritmik apa yang harus Anda pasang secara otomatis untuk mendeteksi *deadlock* ini?
13. **Skenario C**: Sebuah rate-limiter menggunakan sliding window berbasis Redis Sorted Set (`ZADD` + `ZREMRANGEBYSCORE`). Saat traffic mencapai 50.000 RPS, CPU instance Redis melonjak ke 100%. Struktur data alternatif apa yang dapat dipindahkan ke memori lokal instans aplikasi untuk mengeliminasi bottleneck Redis tersebut dengan kompleksitas amortisasi yang setara?

---

## 16. Summary

1. **Konvergensi Algoritma & Sistem**: Pola-pola algoritma klasik LeetCode (Monotonic Queue, DAG, DSU, Segment Tree) adalah blok pembangun internal dari perangkat lunak infrastruktur modern.
2. **Efisiensi Perangkat Keras**: Pemilihan struktur data yang mengabaikan *hardware architecture* (seperti *pointer chasing* vs *contiguous memory*) akan mengalami degradasi performa drastis akibat *cache miss* dan beban *Garbage Collector*, meskipun secara teoretis memiliki Big-O yang optimal.
3. **Deterministik & Bounded**: Sistem produksi menuntut prediktabilitas latensi dan memori. Menggunakan struktur data *fixed-capacity*, *zero-allocation loop*, dan eksekusi iteratif adalah standar absolut untuk mempertahankan SLA P99/P99.9 dalam skala enterprise.