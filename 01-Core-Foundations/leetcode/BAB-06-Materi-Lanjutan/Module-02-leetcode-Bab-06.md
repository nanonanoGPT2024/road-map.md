# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Topik:** LeetCode & Algoritma Tingkat Lanjut | **Bab:** BAB-06-Materi-Lanjutan

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mentransformasi Solusi Algoritmik Teoretis ke Arsitektur Produksi:** Mengonversi algoritma LeetCode tingkat *Medium/Hard* (khususnya *Graph Dependency Resolution*, *Monotonic State Engines*, dan *Range Query Primitives*) menjadi layanan *backend* berkinerja tinggi, nir-alokasi (*zero-allocation* jika memungkinkan), dan aman terhadap konkurensi (*thread-safe*).
2. **Menganalisis Overhead Hardware & Runtime:** Mengidentifikasi degradasi performa yang diakibatkan oleh *CPU cache misses*, *pointer chasing*, *recursion stack overflow*, dan *Garbage Collection (GC) pressure* pada implementasi algoritma naive.
3. **Mendesain Engine Eksekusi DAG (Directed Acyclic Graph) Skala Enterprise:** Mengimplementasikan variasi algoritma Kahn dan Tarjan (*Strongly Connected Components*) untuk mendeteksi siklus dependensi terdistribusi dan menjadwalkan pekerjaan konkuren (*parallel task orchestrator*).
4. **Mengimplementasikan Struktur Data Lanjutan untuk Data Streaming:** Membangun *Monotonic Deque* dan *Segment Tree* dengan *Lazy Propagation* yang dioptimalkan untuk latensi sub-milidetik pada agregasi *sliding window* bervolume jutaan *event* per detik.

---

## 2. Prerequisite

Untuk mencerna materi ini secara komprehensif, Anda wajib memiliki pemahaman mendalam tentang:
- **Kompleksitas Asimtotik (Big-O notation):** Analisis *Time*, *Space*, dan *Amortized Complexity*.
- **Struktur Data Dasar & Menengah:** Array, Hash Map, Doubly Linked List, Binary Heap, Disjoint-Set Union (DSU).
- **Rekursi & Memory Stack:** Pemahaman *stack frame layout*, batas kedalaman rekursi OS (*OS default stack size limit* biasanya 8MB pada Linux), dan teknik eliminasi rekursi (iteratif dengan *explicit stack*).
- **Dasar Konkurensi & Sinkronisasi:** Mutex, Atomic operations, Read-Write locks, serta model memori bahasa pemrograman modern (Go/C++/Rust/Java).

---

## 3. Concept & Internal Architecture

### 3.1 Kesenjangan Antara "Accepted" LeetCode dan "Production-Ready"
Dalam platform kompetitif seperti LeetCode, metrik keberhasilan didasarkan pada *Time Limit Exceeded* (TLE) dan *Memory Limit Exceeded* (MLE) dalam lingkungan terisolasi dengan siklus hidup proses singkat. Solusi yang mendapatkan status **"Accepted"** sering kali langsung kolaps saat dideploy ke produksi karena:

1. **Pointer Chasing vs. CPU Cache Locality:**
   Struktur data berbasis node (seperti `struct Node { Val int; Next *Node; Children []*Node }`) menyebarkan alokasi memori ke seluruh *heap*. Akibatnya, CPU mengalami *L1/L2/L3 cache misses* masif. Arsitektur produksi menuntut representasi berbasis *flat array* atau *Data-Oriented Design* (DOD), misalnya *Compressed Sparse Row* (CSR) untuk graph.

2. **Stack Overflow pada Skala Besar:**
   Algoritma graf seperti DFS rekursif rentan mengalami *stack exhaustion* jika memproses graf berbentuk *deep linked-list* dengan kedalaman $V \ge 10^5$. Lingkungan produksi mengharuskan penggunaan struktur iteratif berbasis *heap-allocated stack* atau BFS berbasis antrean cincin (*ring buffer*).

3. **Garbage Collection Churn:**
   Instansiasi jutaan objek sementara (*transient objects*) selama traversal memicu siklus *Stop-the-World* (STW) pada runtime yang menggunakan GC (seperti Go atau Java). Hal ini mendegradasi metrik latensi p99 dan p99.9.

```
Pendekatan Node-Based (LeetCode Standard):
[Node A] ---> Heap Addr 0x00F4 ---> [Node B] ---> Heap Addr 0x8A10 ---> [Node C]
(Setiap akses memicu cache miss karena memori terfragmentasi)

Pendekatan Flat Memory Layout (Production Standard):
Offset:  0   1   2   3   4   5
Index:  [A | B | C | D | E | F] -> Tersimpan linear di L1/L2 Data Cache!
```

---

### 3.2 Deep Dive 1: Dependency Resolution Engine (Topological Sort + Tarjan's SCC)
Dalam sistem orkestrasi microservices atau *build systems* (seperti Bazel, Airflow, atau Temporal), dependensi antar tugas dimodelkan sebagai graf berarah (*Directed Graph*).

* **Algoritma Kahn:** Berbasis *In-Degree array* dan *FIFO Queue*. Sangat optimal untuk eksekusi paralel karena simpul dengan *in-degree* bernilai 0 dapat langsung dijadwalkan secara serentak ke *worker pool*.
* **Algoritma Tarjan (Strongly Connected Components):** Menemukan siklus dalam graf berarah menggunakan DFS tunggal dengan melacak *discovery time* dan *low-link values*. Dalam produksi, deteksi siklus wajib mengisolasi simpul-simpul yang menyebabkan *circular deadlock* untuk dilaporkan ke administrator sistem sebelum eksekusi dimulai.

```
Matriks State Tarjan:
dfn[u]      : Waktu pertama kali simpul u dikunjungi.
low[u]      : Dfn terkecil yang dapat dijangkau dari sub-tree u melalui back-edges.
onStack[u]  : Boolean bitset/array yang menandai apakah u saat ini ada di recursion stack.
```

---

### 3.3 Deep Dive 2: Monotonic Structures untuk Streaming & Telemetri
*Monotonic Queue* (atau *Monotonic Deque*) menjaga elemennya selalu terurut secara monoton naik (*strictly increasing*) atau turun (*strictly decreasing*).
* Digunakan untuk memecahkan *Sliding Window Extremum Problem* dalam kompleksitas $O(N)$ teramortisasi, bukan $O(N \log K)$ via Heap.
* Pada arsitektur produksi, struktur ini menjadi tulang punggung *real-time rate limiters*, deteksi anomali latensi (*sliding window 95th percentile tracking*), dan pemrosesan order book finansial berkecepatan tinggi.

---

## 4. Why & What

### Mengapa Pendekatan Naive Gagal di Produksi?
Pertimbangkan sistem yang harus memvalidasi dependensi dari 50.000 microservice atau paket software. 
* Solusi naive dengan Adjacency Matrix membutuhkan memori $O(V^2) = 50.000^2 \times 4 \text{ bytes} \approx 10 \text{ GB}$, langsung memicu OOM (Out Of Memory).
* Solusi naive rekursif Tarjan akan mengalokasikan $50.000$ stack frame. Jika satu frame berukuran 1 KB (akibat variabel lokal dan konteks eksekusi), kebutuhan stack mencapai $\approx 50 \text{ MB}$, jauh melampaui limit stack default Linux (8 MB) dan memicu crash seketika (`SIGSEGV`).

### Apa yang Kita Bangun?
Kita membangun:
1. **Enterprise Task Execution Graph (DAG Engine):** Menggunakan representasi Adjacency List terindeks integer, deteksi siklus adaptif via Tarjan/Kahn, dan eksekusi konkuren berbasis *Worker Pool*.
2. **High-Throughput Monotonic Sliding Window Processor:** Struktur data nir-alokasi berbasis *Circular Ring Buffer* untuk agregasi data telemetri streaming dengan overhead latensi mendekati nol.

---

## 5. How (Workflow Detail)

### Alur Kerja Mesin Orkestrasi Berbasis DAG:
```
[Registrasi Dependensi]
       │
       ▼
[Kompilasi Graf: String ID -> Compact Dense Integer Index]
       │
       ▼
[Deteksi Siklus: Tarjan's SCC] ──(Ada Siklus?)──► [Return Error: Circular Dependency Detected + Cycle Path]
       │ (Graf Valid: Acyclic)
       ▼
[Hitung In-Degree Simpul & Ekstrak Root Simpul (In-Degree == 0)]
       │
       ▼
[Enqueue Root Nodes ke Concurrency Dispatcher]
       │
  ┌────┴────────────────────────┐
  ▼                             ▼
[Worker 1: Exec Task]       [Worker 2: Exec Task]
  │                             │
  └────┬────────────────────────┘
       ▼
[Atomic Decrement In-Degree dari Dependen]
       │
[Simpul dengan In-Degree == 0 Dimasukkan ke Queue Eksekusi]
       │
       ▼
[Ulangi hingga Semua Simpul Selesai]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Monotonic Deque: Jalur Antrean VIP di Bandara
Bayangkan barisan penumpang yang masuk ke pemeriksaan imigrasi. Setiap kali seseorang yang memiliki pangkat/prioritas lebih tinggi (angka lebih besar) datang, semua orang di depannya yang memiliki prioritas lebih rendah dan datang lebih awal akan dikeluarkan dari antrean karena mereka tidak akan pernah menjadi kandidat "penumpang berprioritas tertinggi berikutnya" selama penumpang baru ini masih berada dalam antrean.

```
Kondisi Deque (Monoton Menurun):
Elemen Baru Masuk: 8

Sebelum:
Front -> [10] -> [7] -> [4] -> [2] <- Rear
Elemen 8 masuk dari Rear:
- Bandingkan 8 dengan 2: 8 > 2 -> Evict 2
- Bandingkan 8 dengan 4: 8 > 4 -> Evict 4
- Bandingkan 8 dengan 7: 8 > 7 -> Evict 7
- Bandingkan 8 dengan 10: 8 < 10 -> Stop! Masukkan 8.

Sesudah:
Front -> [10] -> [8] <- Rear
Semua operasi evict teramortisasi O(1) karena tiap elemen dimasukkan dan dihapus maksimal 1 kali!
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example (LeetCode 239 - Sliding Window Maximum - Naive vs Idiomatic)
Implementasi algoritma murni sering kali menggunakan slice dinamis yang menyebabkan alokasi memori berulang.

### 7.2 Practical Example (Enterprise-Grade Concurrent DAG Execution Engine)
Berikut adalah implementasi Go tingkat produksi untuk graf orkestrasi dependensi menggunakan Algoritma Kahn termodifikasi yang mendukung eksekusi paralel nir-deadlock dengan kendali konkurensi:

```go
package dagengine

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
)

var (
	ErrCycleDetected = errors.New("cyclic dependency detected in execution graph")
	ErrTaskFailed    = errors.New("task execution failed")
)

type TaskFunc func(ctx context.Context) error

type NodeID int

type TaskNode struct {
	ID       NodeID
	Name     string
	Execute  TaskFunc
	Children []NodeID
}

type GraphEngine struct {
	nodes    []TaskNode
	inDegree []int32
	totalNodes int
}

func NewGraphEngine(capacity int) *GraphEngine {
	return &GraphEngine{
		nodes:    make([]TaskNode, 0, capacity),
		inDegree: make([]int32, 0, capacity),
	}
}

func (g *GraphEngine) AddNode(name string, fn TaskFunc) NodeID {
	id := NodeID(len(g.nodes))
	g.nodes = append(g.nodes, TaskNode{
		ID:       id,
		Name:     name,
		Execute:  fn,
		Children: make([]NodeID, 0, 4),
	})
	g.inDegree = append(g.inDegree, 0)
	g.totalNodes++
	return id
}

func (g *GraphEngine) AddDependency(from, to NodeID) {
	// from must complete before to starts (from -> to)
	g.nodes[from].Children = append(g.nodes[from].Children, to)
	g.inDegree[to]++
}

// ExecuteGraph menjalankan tugas dalam DAG secara konkuren berbasis in-degree
func (g *GraphEngine) ExecuteGraph(ctx context.Context, concurrencyLimit int) error {
	inDegreeCopy := make([]int32, g.totalNodes)
	copy(inDegreeCopy, g.inDegree)

	taskQueue := make(chan NodeID, g.totalNodes)
	var processedCount int64

	// Temukan simpul akar (in-degree == 0)
	for i := 0; i < g.totalNodes; i++ {
		if inDegreeCopy[i] == 0 {
			taskQueue <- NodeID(i)
		}
	}

	var wg sync.WaitGroup
	errChan := make(chan error, g.totalNodes)
	workerSem := make(chan struct{}, concurrencyLimit)

	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case taskID, ok := <-taskQueue:
			if !ok {
				goto WaitPhase
			}

			atomic.AddInt64(&processedCount, 1)
			wg.Add(1)

			go func(id NodeID) {
				defer wg.Done()

				// Concurrency throttling
				select {
				case workerSem <- struct{}{}:
					defer func() { <-workerSem }()
				case <-ctx.Done():
					return
				}

				// Execute task
				if err := g.nodes[id].Execute(ctx); err != nil {
					select {
					case errChan <- fmt.Errorf("task %s (ID %d) failed: %w", g.nodes[id].Name, id, err):
					default:
					}
					cancel()
					return
				}

				// Decrement in-degree untuk semua anak simpul secara atomic
				for _, childID := range g.nodes[id].Children {
					remaining := atomic.AddInt32(&inDegreeCopy[childID], -1)
					if remaining == 0 {
						taskQueue <- childID
					}
				}
			}(taskID)

		default:
			// Jika queue kosong tapi belum semua diproses, tunggu worker yang sedang berjalan
			if atomic.LoadInt64(&processedCount) == int64(g.totalNodes) {
				close(taskQueue)
			} else {
				// Prevent CPU spinning
				// Menggunakan sinkronisasi wait phase
				goto WaitPhase
			}
		}
	}

WaitPhase:
	wg.Wait()
	close(errChan)

	if err, exists := <-errChan; exists {
		return err
	}

	if atomic.LoadInt64(&processedCount) != int64(g.totalNodes) {
		return ErrCycleDetected
	}

	return nil
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Real-Time Stream Fraud Detection Engine (Volume: 500.000 Events/detik)
* **Problem:** Tim Fraud Engineering di sebuah payment gateway tier-1 perlu mendeteksi apakah jumlah transaksi dari sebuah akun dalam jendela geser (*sliding window*) 10 menit melebihi deviasi batas normal, sekaligus melacak transaksi terbesar (*Max Transaction Amount*) dalam rentang waktu tersebut secara *real-time*.
* **Pendekatan Awal (Redis ZSET):**
  Menggunakan `ZADD` dan `ZREMRANGEBYSCORE` ke Redis cluster.
  * *Bottleneck:* CPU saturasi pada Redis cluster akibat serialization, network I/O, dan kompleksitas $O(\log N + M)$ pada ZSET. Latensi p99 membengkak ke 85ms pada jam sibuk.
* **Solusi Algoritmik Tingkat Produksi:**
  In-memory processing engine berbasis **Circular Monotonic Deque** yang diimplementasikan di layer servis Go:
  - Alokasi memori statis (*Fixed-size ring buffer*) sebesar 600 slot (resolusi 1 detik untuk jendela 10 menit).
  - Mengeliminasi alokasi heap saat *runtime*.
  - Monotonic property memastikan nilai maksimum selalu berada di simpul depan (*head*) dalam kompleksitas $O(1)$.
* **Hasil:**
  Latensi p99 terpangkas dari **85ms menjadi 0,38ms**. Pemakaian CPU kluster menurun drastis sebesar 72%.

---

## 9. Trade-offs

| Aspek | Pointer-Chasing Graph (LeetCode Naive) | Flat-Array / Contiguous Graph (Production) | Segment Tree (Range Query) | Monotonic Deque (Sliding Window) |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput** | Rendah (Cache miss masif) | Sangat Tinggi (L1/L2 cache prefetching) | Tinggi ($O(\log N)$) | Sangat Tinggi ($O(1)$ amortized) |
| **Latensi (p99)** | Fluktuatif (GC spikes) | Stabil (Zero runtime allocation) | Terprediksi ($O(\log N)$) | Paling Rendah (Nol alokasi dinamik) |
| **Konsumsi Memori** | Tinggi (Overhead pointer per node) | Minimal (Array terpadat) | $4 \times N$ ukuran array dasar | $O(K)$ sesuai kapasitas window |
| **Fleksibilitas** | Dinamis (Mudah tambah simpul) | Statis (Perlu rekalkulasi / realloc) | Rentang dinamis & point-update | Hanya berlaku untuk sliding window |
| **Kompleksitas Kode** | Rendah (Sederhana diimplementasikan) | Tinggi (Butuh kalkulasi manual offset) | Tinggi (Butuh logika tree indexing) | Menengah (Manajemen invariant ketat) |

---

## 10. Common Mistakes & Troubleshooting

### 1. Stack Overflow akibat Traversal DFS Rekursif
* **Gejala:** Aplikasi tiba-tiba crash dengan pesan `runtime: goroutine stack exceeds 1000000000-byte limit` atau `fatal error: stack overflow`.
* **Root Cause:** Struktur graf memiliki lintasan lurus (*path graph*) yang sangat panjang ($V > 100.000$).
* **Mitigasi:** Ubah algoritma rekursif menjadi iteratif menggunakan explicit slice sebagai stack yang dialokasikan di heap:
  ```go
  // Buruk: DFS Rekursif
  func dfs(u int) { for _, v := range adj[u] { dfs(v) } }

  // Baik: Iteratif dengan Heap Stack
  stack := make([]int, 0, initialCapacity)
  stack = append(stack, root)
  for len(stack) > 0 {
      curr := stack[len(stack)-1]
      stack = stack[:len(stack)-1]
      // proses curr dan append tetangga
  }
  ```

### 2. Deadlock pada Concurrency DAG
* **Gejala:** Engine orkestrasi menggantung (*hangs*) permanen tanpa menghabiskan CPU.
* **Root Cause:** Kegagalan atomisitas saat pengurangan nilai *in-degree* di lingkungan multi-thread, atau kanal antrean (*channel*) penuh akibat ukuran *buffer* yang tidak proporsional dengan jumlah *in-degree 0 nodes*.
* **Mitigasi:** Gunakan operasi `sync/atomic.AddInt32` untuk mutasi derajat simpul dan rancang kapasitas antrean minimum setara dengan total simpul $|V|$.

---

## 11. Best Practices (Production Checklist)

- [ ] **Zero-Allocation Hot-Path:** Struktur data inti tidak boleh melakukan `malloc` atau membuat slice baru di dalam loop pemrosesan event. Gunakan *pre-allocated buffer* atau `sync.Pool`.
- [ ] **Iteration Over Recursion:** Seluruh operasi traversal graf atau tree wajib menggunakan pendekatan iteratif untuk menjamin imunitas terhadap *stack overflow*.
- [ ] **Context Propagation & Timeout:** Setiap eksekusi simpul graf wajib membawa `context.Context` untuk memastikan eksekusi dapat dibatalkan seketika jika terjadi pelanggaran batas SLA (*timeout*).
- [ ] **Explicit Cycle Guard:** Jangan berasumsi data input selalu *acyclic*. Jalankan validasi invariant topologi sebelum mengeksekusi *side-effects* eksternal.
- [ ] **Cache Line Alignment:** Pastikan struct yang sering dimutasi oleh beberapa *core* prosesor terpisah tidak berada pada *cache line* 64-byte yang sama untuk menghindari degradasi performa akibat *False Sharing*.

---

## 12. Hands-on Practice

Buatlah direktori lokal dan ikuti langkah-langkah praktikum berikut untuk menguji efisiensi memori antara implementasi standar vs optimasi produksi:

### Struktur File:
```
hands-on/m02/
├── ring_buffer.go
├── ring_buffer_test.go
└── go.mod
```

### 1. Inisialisasi Project:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init m02-advanced-algo
```

### 2. Implementasi `ring_buffer.go`:
```go
package main

// MonotonicQueue mengimplementasikan sliding window maximum nir-alokasi
type MonotonicQueue struct {
	data []int
	head int
	tail int
	size int
	cap  int
}

func NewMonotonicQueue(capacity int) *MonotonicQueue {
	return &MonotonicQueue{
		data: make([]int, capacity),
		cap:  capacity,
	}
}

func (mq *MonotonicQueue) Push(val int) {
	// Buang elemen yang lebih kecil dari belakang (Monoton Menurun)
	for mq.size > 0 {
		lastIdx := (mq.tail - 1 + mq.cap) % mq.cap
		if mq.data[lastIdx] < val {
			mq.tail = lastIdx
			mq.size--
		} else {
			break
		}
	}
	mq.data[mq.tail] = val
	mq.tail = (mq.tail + 1) % mq.cap
	mq.size++
}

func (mq *MonotonicQueue) Pop(val int) {
	if mq.size > 0 && mq.data[mq.head] == val {
		mq.head = (mq.head + 1) % mq.cap
		mq.size--
	}
}

func (mq *MonotonicQueue) Max() int {
	return mq.data[mq.head]
}
```

### 3. Implementasi Benchmark `ring_buffer_test.go`:
```go
package main

import "testing"

func BenchmarkMonotonicQueue(b *testing.B) {
	mq := NewMonotonicQueue(1000)
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		mq.Push(i % 500)
		if i >= 1000 {
			mq.Pop((i - 1000) % 500)
		}
		_ = mq.Max()
	}
}
```

### 4. Eksekusi Validasi:
```bash
go test -bench=. -benchmem
```
*Pastikan hasil alokasi memori menunjukkan: `0 B/op` dan `0 allocs/op`.*

---

## 13. Exercise

### Level Easy: Circular Ring Buffer Metrics Collector
* **Soal:** Rancang struktur data `LatencyRecorder` berbasis *fixed-array* berukuran $N$. Buat method `Record(lat int)` dan `GetMin() int` yang berjalan dalam kompleksitas waktu $O(1)$ amortized tanpa melakukan alokasi memori heap baru.
* **Target Kontrak:** `0 allocs/op` pada pengujian benchmark.

### Level Medium: Thread-Safe Dynamic Dependency Resolver
* **Soal:** Diberikan sejumlah microservice dengan dependensi dinamis yang dapat berubah saat *runtime*. Buat sebuah service yang mampu memvalidasi apakah penambahan dependensi baru `(Service A -> Service B)` akan menyebabkan siklus dependensi atau tidak, secara konkuren dan *thread-safe*.
* **Batasan:** Maksimum $V \le 20.000$, response time validasi harus di bawah 5 milidetik pada p99.

### Level Hard: Distributed Segment Tree dengan Lazy Propagation
* **Soal:** Buat modul *in-memory transactional ledger* yang melacak saldo minimum rekening bank dalam berbagai rentang waktu historis.
* **Persyaratan:**
  - Operasi `UpdateRange(startTick, endTick, deltaBalance)`: Menambahkan nilai `delta` ke seluruh tick dalam rentang waktu tersebut secara efisien ($O(\log N)$).
  - Operasi `QueryMin(startTick, endTick)`: Mengembalikan nilai minimum dalam rentang waktu tersebut untuk mendeteksi apakah saldo pernah turun di bawah batas insolvensi ($O(\log N)$).

---

## 14. Challenge

### Studi Kasus: High-Throughput Deadlock Detection Engine pada Distributed Transaction Manager

**Skenario Kompleks:**
Anda adalah Principal Architect pada sistem database terdistribusi. Sistem Anda menggunakan arsitektur *two-phase locking* (2PL) terdistribusi di mana ribuan transaksi yang tersebar di ratusan node bersaing mendapatkan *exclusive locks* pada baris data.

Ketika terjadi *deadlock* (misal: Transaksi 1 menunggu Transaksi 2, Transaksi 2 menunggu Transaksi 3, Transaksi 3 menunggu Transaksi 1), salah satu transaksi harus dibatalkan (*victim abort*) untuk membuka kebuntuan.

**Instruksi Tantangan:**
1. Desain algoritma *Global Wait-For Graph* (WFG) yang menerima feed transaksi asinkron via streaming (misal: event `TX_ACQUIRE_LOCK`, `TX_WAIT_LOCK`, `TX_RELEASE_LOCK`).
2. Rancang mekanisme deteksi siklus terdistribusi yang meminimalisir pembatalan transaksi berbiaya tinggi (*cost-effective victim selection* berdasarkan metrik lamanya transaksi berjalan dan bobot operasi).
3. Tangani skenario *split-brain* di mana partisi jaringan memotong informasi topologi graf, tanpa menghasilkan *false positive abort* yang merusak integritas data ACID.
4. Sajikan rancangan arsitektur dan invariant matematis/state machine yang membuktikan sistem terbebas dari *livelock*.

*(Tantangan ini tidak memiliki solusi trivial satu file. Buat arsitektur dokumen teknis dan prototipe modul inti untuk mengatasi masalah ini).*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa kompleksitas waktu Algoritma Kahn untuk Topological Sort adalah $O(V + E)$? Jelaskan peran in-degree di dalamnya!**
   * *Jawaban Singkat:* Algoritma memproses setiap simpul tepat satu kali saat in-degree mencapai 0 ($V$) dan memeriksa serta mengurangi bobot setiap sisi berarah (*edge*) tepat satu kali ($E$).

2. **Apa yang menyebabkan implementasi rekursif DFS rentan terhadap crash pada sistem produksi skala besar?**
   * *Jawaban Singkat:* Pertumbuhan stack frame yang linear terhadap kedalaman graf ($O(V)$) dapat melampaui alokasi memori stack thread sistem operasi yang terbatas (misal 8MB), memicu *stack overflow exception*.

3. **Berapa alokasi memori amortized dari operasi `Push` pada Monotonic Deque jika diimplementasikan menggunakan circular array tetap?**
   * *Jawaban Singkat:* $O(1)$ time complexity amortized dan $0$ bytes dynamic allocation overhead per operasi.

4. **Kapan struktur data Disjoint-Set Union (DSU) lebih diutamakan dibandingkan Algoritma Tarjan?**
   * *Jawaban Singkat:* DSU unggul pada graf tak berarah (*undirected graph*) untuk *connected components* dan operasi dinamis (*incremental union*), sedangkan Tarjan dirancang khusus untuk graf berarah (*directed graph*) guna menemukan *Strongly Connected Components*.

5. **Apa dampak fenomena "False Sharing" pada struktur data graf yang diakses oleh thread paralel?**
   * *Jawaban Singkat:* Penurunan performa drastis akibat beberapa CPU core memvalidasi ulang (invalidation) baris *L1/L2 cache* (64-byte) yang sama secara berulang-ulang, meskipun thread mengakses variabel/elemen array yang berbeda namun bertetangga.

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Dalam Algoritma Tarjan, apa arti dari kondisi `low[v] >= dfn[u]` ketika `v` adalah tetangga dari `u`?**
   * *Jawaban Singkat:* Menandakan bahwa sub-pohon yang berakar di `v` tidak memiliki jalur lintas balik (*back-edge*) ke leluhur dari `u`. Ini menunjukkan bahwa `u` adalah *articulation point* (simpul genting) yang jika dihapus akan memutus konektivitas graf.

7. **Mengapa Priority Queue (Heap) suboptimal untuk sliding window maximum jika dibandingkan dengan Monotonic Queue?**
   * *Jawaban Singkat:* Priority Queue memiliki kompleksitas waktu $O(\log K)$ untuk setiap penambahan/penghapusan elemen dan kesulitan menghapus elemen yang kadaluarsa di luar rentang window secara instan, sedangkan Monotonic Deque memberikan waktu amortisasi $O(1)$ untuk semua operasi.

8. **Bagaimana Segment Tree dengan "Lazy Propagation" meningkatkan efisiensi operasi pembaruan rentang (*range update*)?**
   * *Jawaban Singkat:* Menunda pembaruan pada node-node anak dan menyimpannya sebagai penanda (*lazy flag*) di node induk. Pembaruan ke bawah hanya dieksekusi saat node anak tersebut benar-benar diakses oleh query berikutnya, mereduksi kompleksitas pembaruan dari $O(N)$ menjadi $O(\log N)$.

9. **Jika sebuah graf dependensi tugas memiliki siklus, apa status akhir dari himpunan in-degree pada Algoritma Kahn?**
   * *Jawaban Singkat:* Jumlah simpul yang berhasil diproses akan lebih sedikit dari total simpul $|V|$, dan simpul-simpul yang terjebak dalam siklus akan selalu memiliki nilai in-degree $> 0$.

10. **Jelaskan perbedaan mendasar antara representasi graf Adjacency List dan Compressed Sparse Row (CSR) dalam konteks pemanfaatan CPU cache hardware!**
    * *Jawaban Singkat:* Adjacency List menyimpan data melalui array of pointers yang menyebabkan fragmentasi memori (*cache misses*), sementara CSR meratakan seluruh tetangga ke dalam satu array kontigu linear, memaksimalkan mekanisme *spatial locality* dan *hardware prefetcher* CPU.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Berbobot)
11. **Skenario 1:**
    Sebuah microservice routing jaringan menerima grafik topologi dengan 1.000.000 simpul dan 2.000.000 sisi setiap 5 menit. Engine routing mengalami latency spike hingga 10 detik saat melakukan deteksi siklus. Profiling CPU menunjukkan penggunaan waktu 70% dihabiskan pada `runtime.mallocgc`. 
    *Pertanyaan:* Perubahan arsitektur apa yang harus Anda lakukan pada representasi graf tersebut untuk memangkas latensi hingga di bawah 500ms?
    * *Solusi Arsitektural:* Ganti Adjacency List berbasis pointer/slice terpisah dengan representasi flat array 1 dimensi (*Compressed Sparse Row* atau Flat CSR). Pra-alokasikan memori graf di awal siklus proses menggunakan buffer statis yang dipakai ulang (*reusable arena memory*) untuk mereduksi alokasi objek heap ke nol dan mengeliminasi kerja Garbage Collector secara total.

12. **Skenario 2:**
    Sistem antrean pesan terdistribusi Anda mengeksekusi pesan yang saling bergantung (*dependent jobs*). Terkadang terjadi kondisi balapan (*race condition*) di mana Task B (yang bergantung pada Task A) masuk ke antrean eksekusi sebelum Task A selesai, dikarenakan Task A tertahan oleh jeda GC (GC pause) sesaat.
    *Pertanyaan:* Mekanisme koordinasi deterministik apa berbasis primitif konkurensi graf yang dapat mencegah eksekusi Task B sebelum Task A benar-benar tuntas tanpa polling database?
    * *Solusi Arsitektural:* Implementasikan *Stateful In-Degree Barrier* menggunakan operasi komputasi atomik terdistribusi (misal via Redis/etcd atomic decrement atau state machine konsensus Raft). Task B didaftarkan dengan in-degree = 1. Hanya saat Task A memancarkan sinyal penyelesaian transaksi yang secara atomik mendeskritkan in-degree Task B menjadi 0, barulah trigger publikasi Task B ke broker eksekusi ditembakkan.

13. **Skenario 3:**
    Sistem metrik finansial frekuensi tinggi (HFT) melacak harga saham tertinggi dalam jendela geser 5 detik. Volume data mencapai 2.000.000 tick/detik. Implementasi Monotonic Deque menggunakan linked list berbasis node memicu kegagalan SLA latensi.
    *Pertanyaan:* Bagaimana Anda merekayasa struktur data tersebut agar beroperasi konsisten pada latensi sub-mikrodetik tanpa alokasi dinamis?
    * *Solusi Arsitektural:* Implementasikan Monotonic Deque di atas *Contiguous Ring Buffer* berukuran tetap (*power of two* untuk optimalisasi bitwise modulo `idx & (capacity - 1)`). Gunakan struct-of-arrays alih-alih array-of-structs untuk data harga dan timestamp agar memaksimalkan vectorization (SIMD) dan menjamin seluruh operasi pop/push terlokalisasi di L1/L2 cache CPU.

---

## 16. Summary

Menguasai algoritma pada platform seperti LeetCode hanyalah tahap pertama dari rekayasa perangkat lunak inti. Untuk membangun sistem komersial berskala masif:
1. **Kompleksitas Asimtotik Teoritis ($O$) Harus Selaras dengan Karakteristik Hardware:** Eksekusi $O(N)$ yang ramah CPU cache sering kali mengungguli algoritma $O(\log N)$ yang sarat *pointer-chasing*.
2. **Eliminasi Overhead Runtime:** Rekursi tanpa batas, fragmentasi memori, alokasi heap berlebih, dan *false sharing* adalah faktor utama kegagalan algoritma teori di lingkungan produksi.
3. **Robustness & Determinism:** Arsitektur algoritma enterprise harus memiliki *circuit breaker*, penanganan *timeout*, pencegahan *deadlock*, dan visibilitas error yang jelas terhadap anomali data (seperti siklus dependensi) sebelum menimbulkan dampak sistemik.