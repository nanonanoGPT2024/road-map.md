# BAB 05: Materi Lanjutan
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi: Concurrent & Cache-Conscious Data Structures

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** dampak hierarki memori hardware (L1/L2/L3 Cache, Cache Line, False Sharing) terhadap performa asimtotik data structure secara empiris.
- **Merancang dan mengimplementasikan** struktur data *lock-free* dan *cache-conscious* (khususnya Bounded Multi-Producer Multi-Consumer Ring Buffer / Disruptor Pattern) menggunakan operasi atomik hardware (*Compare-And-Swap* / CAS) dan *memory fences*.
- **Mengevaluasi trade-off** antara *throughput*, latensi *tail* (p99/p99.9), konsumsi memori, dan kompleksitas kode antara *lock-based* vs *lock-free concurrent data structures*.
- **Mendiagnosis dan memitigasi** masalah konkurensi tingkat rendah seperti *ABA Problem*, *Cache Line Bouncing*, dan *Memory Reordering* pada sistem terdistribusi/bare-metal berperforma tinggi.

---

### 2. Prerequisite
Peserta wajib memahami:
- Model memori CPU modern: Cache Lines (umumnya 64 bytes), Store Buffers, L1/L2/L3 Caches.
- Konsep dasar konkurensi: Mutex, Semaphore, Race Condition, Deadlock.
- Primitif atomik: Fetch-And-Add (FAA), Compare-And-Swap (CAS), Test-And-Set (TAS).
- Notasi Asimtotik (Big-O, Big-$\Omega$, Big-$\Theta$) dan amortisasi kompleksitas waktu.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi struktur data enterprise modern tidak hanya berurusan dengan kompleksitas algoritma teoritis $\mathcal{O}(1)$ atau $\mathcal{O}(\log n)$, melainkan konstrain fisik arsitektur von Neumann dan von Neumann bottleneck. 

```
+-------------------------------------------------------------------+
|                        CPU Core & Cache Hierarchy                 |
|                                                                   |
|  +--------------------+                   +--------------------+  |
|  |     CPU Core 0     |                   |     CPU Core 1     |  |
|  |  [Registers]       |                   |  [Registers]       |  |
|  |  [L1 Data (32KB)]  |                   |  [L1 Data (32KB)]  |  |
|  |     ~1 ns latency  |                   |     ~1 ns latency  |  |
|  +---------+----------+                   +---------+----------+  |
|            |                                        |             |
|  +---------+----------+                   +---------+----------+  |
|  |   L2 Cache (512KB) |                   |   L2 Cache (512KB) |  |
|  |     ~3-4 ns        |                   |     ~3-4 ns        |  |
|  +---------+----------+                   +---------+----------+  |
|            \                                        /             |
|             \                                      /              |
|              +---------------+--------------------+               |
|                              |                                    |
|                +-------------+-------------+                      |
|                |      Shared L3 Cache      |                      |
|                |         (16-64MB)         |                      |
|                |         ~10-20 ns         |                      |
|                +-------------+-------------+                      |
|                              |                                    |
+------------------------------|------------------------------------+
                               | Interconnect (QPI/UPI/Infinity Fabric)
                 +-------------+-------------+
                 |        Main Memory        |
                 |          (DRAM)           |
                 |         ~60-100 ns        |
                 +---------------------------+
```

#### A. The Latency Gap & Cache-Conscious Design
Akses register membutuhkan waktu $\sim 0.5\text{ ns}$, L1 Cache $\sim 1\text{ ns}$, sedangkan akses DRAM membutuhkan $\sim 60\text{--}100\text{ ns}$. Ini adalah perbedaan hingga dua orde magnitudo. Pointer-based structures seperti linked list atau unbalanced binary search tree menyebabkan *pointer chasing*: setiap dereferensi pointer memiliki probabilitas tinggi memicu L3 Cache Miss, memaksa CPU mengalami *stall cycles* selama ratusan siklus clock.

#### B. Cache Coherency & The MESI Protocol
Dalam arsitektur *multi-core*, setiap core CPU memiliki salinan lokal dari blok memori (Cache Line, ukuran standar: 64 bytes). Untuk menjaga konsistensi antar-core, hardware menerapkan protokol koherensi cache, umumnya turunan dari **MESI** (*Modified, Exclusive, Shared, Invalid*):
1. **Modified**: Cache line hanya ada di cache lokal core saat ini dan nilainya *dirty* (berbeda dari memori utama).
2. **Exclusive**: Cache line hanya ada di cache lokal, nilainya *clean* (sama dengan memori utama).
3. **Shared**: Cache line ada di cache lokal beberapa core secara simultan (*read-only*).
4. **Invalid**: Data dalam cache line tidak valid lagi karena core lain telah menulis ke alamat memori yang berada dalam cache line tersebut.

#### C. False Sharing (The Silent Throughput Killer)
*False Sharing* terjadi ketika dua thread yang berjalan pada core terpisah memodifikasi dua variabel independen yang secara kebetulan berada dalam **Cache Line 64-byte yang sama**.

```
Cache Line (64 Bytes)
+------------------------------------+------------------------------------+
|  Variable A (Core 0 writes here)   |  Variable B (Core 1 writes here)   |
|            8 Bytes                 |            8 Bytes                 |
+------------------------------------+------------------------------------+
                 |                                      |
         Core 0 invalidates                     Core 1 invalidates
       entire 64-byte line                     entire 64-byte line
       in Core 1's L1 cache                   in Core 0's L1 cache
                 \                                      /
                  +---> Ping-Pong Cache Line <---------+
                         (Bus Storm / High Latency)
```

Meskipun Core 0 tidak pernah membaca atau menulis ke `Variable B`, setiap penulisan oleh Core 0 ke `Variable A` akan menandai seluruh cache line di Core 1 menjadi **Invalid (I)** melalui bus snooping/interconnect. Akibatnya, Core 1 terpaksa melakukan reload cache line dari L3 atau RAM. Fenomena ini disebut *Cache Line Bouncing*, dan dapat menurunkan throughput sistem hingga 90-95%.

Mitigasinya adalah **Explicit Cache Line Padding**: menyisipkan byte dummy (biasanya 56 bytes jika variabel berukuran 8 byte) sehingga setiap variabel yang sering dimutasi menempati cache line independen.

#### D. Lock-Free Architecture & Memory Models
Struktur data *Lock-Based* (misal: `Mutex`) memindahkan manajemen konflik ke OS kernel. Ketika kontensi tinggi terjadi:
1. Thread masuk status blocking (*context switch* memakan waktu $1\text{--}3\text{ }\mu\text{s}$).
2. Penjadwalan kernel memicu *TLB flush* dan hilangnya data L1/L2 cache locality.
3. *Priority Inversion* dan *Convoying* dapat melumpuhkan p99.9 latency SLA.

Sebaliknya, *Lock-Free Data Structures* menjamin bahwa **setidaknya satu thread selalu membuat progress** dalam sejumlah operasi yang berhingga, tanpa pernah ditangguhkan oleh OS scheduler. Fondasi matematisnya bertumpu pada hardware CAS:
$$\text{CAS}(V, E, N) \implies \begin{cases} \text{if } V == E \implies V \leftarrow N, & \text{return } \text{true} \\ \text{if } V \neq E \implies & \text{return } \text{false} \end{cases}$$

---

### 4. Why & What
- **Why**: Dalam arsitektur microservices modern, financial execution venue (order matching), streaming pipelines (seperti internals Kafka/Flink), dan networking datapaths, *tail latency* (p99/p999) adalah metrik kunci. Mutex berbasis kernel lock menyebabkan jitter yang tidak dapat diprediksi saat throughput melampaui jutaan event per detik ($>1\text{M ops/sec}$).
- **What**: Modul ini berfokus pada **Cache-Aligned, Lock-Free Multi-Producer Multi-Consumer (MPMC) Bounded Queue** (implementasi varian dari algorithm *Dmitry Vyukov* dan *LMAX Disruptor*), yang menggabungkan:
  1. Ring buffer pre-allocated contiguous array (meniadakan GC/memory allocations saat runtime).
  2. Cache padding untuk indeks read/write guna membasmi *false sharing*.
  3. Turn-based slot sequence atomics untuk mengoordinasi producer dan consumer secara independen.

---

### 5. How (Workflow Detail)

Arsitektur MPMC Ring Buffer beroperasi menggunakan array berukuran eksak $2^k$ (power of two) untuk mengoptimasi operasi modulus: `index = sequence & (capacity - 1)`.

```
Slot State Lifecycle:
--------------------------------------------------------------------------
Slot Sequence Value:      K             K + 1             K + Capacity
Producer Actions:    [Checks Seq] ---> [Writes Data] ---> [Increments Seq]
Consumer Actions:                      [Checks Seq] ---> [Reads Data] ---> [Increments Seq]
--------------------------------------------------------------------------
```

#### Workflow Langkah-demi-Langkah:

1. **Inisialisasi**:
   - Array dialokasikan di awal (heap) dengan ukuran $N$ (di mana $N = 2^k$).
   - Setiap slot dalam array memiliki `sequence` atomic counter yang diinisialisasi ke nilai indeksnya: `slot[i].sequence = i`.
   - `head` (enqueue index) diinisialisasi ke `0`.
   - `tail` (dequeue index) diinisialisasi ke `0`.

2. **Enqueue Workflow (Producer)**:
   - **Step 2.1**: Producer membaca `head` saat ini: `pos = atomic.Load(&head)`.
   - **Step 2.2**: Mengambil referensi ke slot: `slot = &buffer[pos & mask]`.
   - **Step 2.3**: Membaca `seq = atomic.Load(&slot.sequence)`.
   - **Step 2.4**: Evaluasi kondisi:
     - Jika `seq == pos`: Slot kosong dan siap ditulis.
       - Coba klaim `head` menggunakan CAS: `atomic.CompareAndSwap(&head, pos, pos + 1)`.
       - Jika CAS berhasil: Tulis data ke payload slot, lalu secara atomik set sequence slot menjadi `pos + 1` via *store-release*. Selesai.
       - Jika CAS gagal: Thread lain mendahului; loop diulang (*retry*).
     - Jika `seq < pos`: Buffer penuh (*backpressure*). Producer harus spin-wait, yield thread, atau return `ErrQueueFull`.
     - Jika `seq > pos`: Producer tertinggal di belakang turn lain; reload `pos` dan loop ulang.

3. **Dequeue Workflow (Consumer)**:
   - **Step 3.1**: Consumer membaca `tail` saat ini: `pos = atomic.Load(&tail)`.
   - **Step 3.2**: Mengambil referensi ke slot: `slot = &buffer[pos & mask]`.
   - **Step 3.3**: Membaca `seq = atomic.Load(&slot.sequence)`.
   - **Step 3.4**: Evaluasi kondisi:
     - Jika `seq == pos + 1`: Slot memiliki data siap konsumsi.
       - Coba klaim `tail` menggunakan CAS: `atomic.CompareAndSwap(&tail, pos, pos + 1)`.
       - Jika CAS berhasil: Salin data dari payload slot, lalu secara atomik set sequence slot menjadi `pos + mask + 1` via *store-release* untuk menandakan slot siap diisi pada putaran berikutnya. Selesai.
       - Jika CAS gagal: Thread lain mendahului; loop diulang.
     - Jika `seq < pos + 1`: Buffer kosong. Consumer spin-wait, yield, atau return `ErrQueueEmpty`.
     - Jika `seq > pos + 1`: Consumer tertinggal; loop ulang.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Loket Pengambilan Tiket Kereta Berputar (Lazy Susan)
Bayangkan sebuah meja bundar berputar dengan $N$ kompartemen. Setiap kompartemen memiliki bendera bernomor putaran.
- Produser ingin meletakkan piring. Mereka hanya boleh meletakkan piring jika bendera kompartemen menunjukkan nomor giliran produser. Setelah meletakkan piring, nomor bendera dinaikkan 1 angka.
- Konsumen ingin mengambil piring. Mereka hanya boleh mengambil piring jika bendera kompartemen sudah dinaikkan 1 angka oleh produser. Setelah mengambil piring, konsumen memutar nomor bendera ke nomor siklus putaran berikutnya, memberi tanda kepada produser berikutnya bahwa piring sudah kosong.
- Produser dan konsumen tidak pernah saling mengunci (*no locks*); mereka hanya memverifikasi nomor bendera (Slot Sequence) dan nomor antrean tiket di tangan mereka (`head` dan `tail`).

#### Diagram ASCII: Memori Layout & False Sharing vs Cache-Padded Ring Buffer

```
UNPADDED STRUCT (Rawan False Sharing - BURUK):
[ L1 Cache Line 64 Bytes                                             ]
+--------------------+--------------------+--------------------------+
| head (uint64, 8B)  | tail (uint64, 8B)  | buffer ptr (8B) | Unused |
+--------------------+--------------------+--------------------------+
  ^                    ^
  Core 0 Enqueue       Core 1 Dequeue
  (Mutasi head)        (Mutasi tail)
  ===> SELESAI MUTASI: Seluruh Cache line di-invalidasi di kedua core!


CACHE-PADDED STRUCT (Production Grade - BAIK):
[ Cache Line 0 (64 Bytes)                                            ]
+--------------------+-----------------------------------------------+
| head (uint64, 8B)  | _pad0 [7]uint64 (56B)                         |
+--------------------+-----------------------------------------------+
  ^ Core 0 Enqueue memutasi ini secara eksklusif.

[ Cache Line 1 (64 Bytes)                                            ]
+--------------------+-----------------------------------------------+
| tail (uint64, 8B)  | _pad1 [7]uint64 (56B)                         |
+--------------------+-----------------------------------------------+
  ^ Core 1 Dequeue memutasi ini secara eksklusif. 
  TIDAK ADA interferensi koherensi cache antar-core!
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Demonstrasi Pengaruh Cache Locality (Row-Major vs Column-Major)
Kode ini membuktikan secara empiris perbedaan traversi memori sekuensial (memanfaatkan cache prefetcher) vs melompat (cache miss).

```go
package main

import (
	"fmt"
	"time"
)

const matrixDim = 8192

var matrix [matrixDim][matrixDim]int32

func rowMajorTraversal() time.Duration {
	start := time.Now()
	var sum int64 = 0
	for i := 0; i < matrixDim; i++ {
		for j := 0; j < matrixDim; j++ {
			sum += int64(matrix[i][j])
		}
	}
	_ = sum
	return time.Since(start)
}

func colMajorTraversal() time.Duration {
	start := time.Now()
	var sum int64 = 0
	for j := 0; j < matrixDim; j++ {
		for i := 0; i < matrixDim; i++ {
			sum += int64(matrix[i][j])
		}
	}
	_ = sum
	return time.Since(start)
}

func main() {
	// Warmup memory
	for i := 0; i < matrixDim; i++ {
		matrix[i][i] = 1
	}

	tRow := rowMajorTraversal()
	tCol := colMajorTraversal()

	fmt.Printf("Row-Major (Sequential / Cache-Friendly) : %v\n", tRow)
	fmt.Printf("Col-Major (Strided / Cache-Miss Heavy)   : %v\n", tCol)
	fmt.Printf("Slowdown Factor                         : %.2fx\n", float64(tCol)/float64(tRow))
}
```

---

#### B. Practical Example: Lock-Free Bounded MPMC Ring Buffer Standar Industri
Berikut implementasi MPMC queue dalam Go menggunakan algoritma Dmitry Vyukov dengan *explicit cache line padding* (64-byte alignment) untuk sistem throughput jutaan TPS.

```go
package mpmc

import (
	"errors"
	"runtime"
	"sync/atomic"
	"unsafe"
)

var (
	ErrQueueFull  = errors.New("queue is full")
	ErrQueueEmpty = errors.New("queue is empty")
)

// CacheLinePad mencegah false sharing antar variabel struktural.
// Ukuran cache line tipikal pada x86_64 dan ARM64 adalah 64 bytes.
type CacheLinePad [56]byte

type cell[T any] struct {
	sequence uint64
	value    T
}

// BoundedMPMCQueue mengimplementasikan Lock-Free Multi-Producer Multi-Consumer FIFO.
type BoundedMPMCQueue[T any] struct {
	_pad0 CacheLinePad
	head  uint64
	_pad1 CacheLinePad
	tail  uint64
	_pad2 CacheLinePad
	mask  uint64
	_pad3 CacheLinePad
	slots []cell[T]
}

// NewBoundedMPMCQueue mengalokasikan ring buffer dengan kapasitas berukuran power of two.
func NewBoundedMPMCQueue[T any](capacity uint64) *BoundedMPMCQueue[T] {
	if capacity < 2 || (capacity&(capacity-1)) != 0 {
		panic("kapasitas harus bilangan pangkat dua (power of two)")
	}

	q := &BoundedMPMCQueue[T]{
		mask:  capacity - 1,
		slots: make([]cell[T], capacity),
	}

	for i := uint64(0); i < capacity; i++ {
		// Set inisial sequence sama dengan index slot-nya
		atomic.StoreUint64(&q.slots[i].sequence, i)
	}

	return q
}

// Enqueue memasukkan elemen ke dalam antrean tanpa menggunakan mutex.
func (q *BoundedMPMCQueue[T]) Enqueue(val T) error {
	var currentCell *cell[T]
	pos := atomic.LoadUint64(&q.head)

	for {
		currentCell = &q.slots[pos&q.mask]
		seq := atomic.LoadUint64(&currentCell.sequence)
		diff := int64(seq) - int64(pos)

		if diff == 0 {
			// Slot siap ditulis. Coba klaim posisi head dengan CAS.
			if atomic.CompareAndSwapUint64(&q.head, pos, pos+1) {
				break
			}
			// CAS gagal, thread lain mendahului; retry dengan reload pos
			pos = atomic.LoadUint64(&q.head)
		} else if diff < 0 {
			// Buffer penuh
			return ErrQueueFull
		} else {
			// Head tertinggal dibanding rotasi slot
			pos = atomic.LoadUint64(&q.head)
		}
		runtime.Gosched() // Berikan CPU slice ke thread lain untuk meminimalkan spin contention
	}

	// Payload store (Data aman karena head sudah berhasil diklaim secara eksklusif)
	currentCell.value = val

	// Publikasikan ketersediaan slot ke consumer via store-release semantics
	atomic.StoreUint64(&currentCell.sequence, pos+1)
	return nil
}

// Dequeue mengambil elemen dari antrean secara non-blocking.
func (q *BoundedMPMCQueue[T]) Dequeue() (T, error) {
	var currentCell *cell[T]
	var zeroVal T
	pos := atomic.LoadUint64(&q.tail)

	for {
		currentCell = &q.slots[pos&q.mask]
		seq := atomic.LoadUint64(&currentCell.sequence)
		diff := int64(seq) - int64(pos+1)

		if diff == 0 {
			// Slot memiliki data valid. Coba klaim posisi tail dengan CAS.
			if atomic.CompareAndSwapUint64(&q.tail, pos, pos+1) {
				break
			}
			// CAS gagal; retry
			pos = atomic.LoadUint64(&q.tail)
		} else if diff < 0 {
			// Buffer kosong
			return zeroVal, ErrQueueEmpty
		} else {
			pos = atomic.LoadUint64(&q.tail)
		}
		runtime.Gosched()
	}

	// Payload read
	val := currentCell.value
	currentCell.value = zeroVal // Bersihkan pointer dari memory leak jika T adalah tipe referensi

	// Reset sequence untuk mengizinkan putaran producer berikutnya
	atomic.StoreUint64(&currentCell.sequence, pos+q.mask+1)
	return val, nil
}

// Size mengembalikan estimasi jumlah item yang ada dalam queue.
func (q *BoundedMPMCQueue[T]) Size() int64 {
	tail := atomic.LoadUint64(&q.tail)
	head := atomic.LoadUint64(&q.head)
	if head >= tail {
		return int64(head - tail)
	}
	return 0
}

// Static assertion ukuran cache line
const _ = unsafe.Sizeof(CacheLinePad{}) // 56 bytes
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Ultra-Low Latency Order Matching Engine (Fintech Exchange)
- **Problem Statement**: Sebuah bursa kripto tier-1 mengalami latensi spikes (p99 melonjak dari $800\text{ ns}$ ke $45\text{ ms}$) setiap kali volume transaksi melonjak drastis hingga 500.000 order/detik. Hasil profiling mengindikasikan bahwa `sync.RWMutex` pada core order-book engine mengalami kontensi ekstrem; ribuan goroutine mengantre pada sys-call `futex` OS kernel, memicu degradasi performa (*convoying*).
- **Architecture Solution**:
  1. Arsitektur berbasis *thread-per-core* menggantikan model multi-threaded bebas.
  2. Implementasi antrean transaksional diganti menggunakan **Lock-Free Cache-Padded Ring Buffer** berbasis Disruptor Pattern.
  3. Pre-alokasi ring buffer sebesar $2^{20}$ entri ($1.048.576$ order) saat start-up engine. Meniadakan alokasi memori dinamis di critical execution path.
  4. Penyematan (*Core Pinning/CPU Affinity*) goroutine ke isolated CPU cores (`isolcpus` pada Linux kernel) guna mencegah L1/L2 cache evictions akibat migrasi thread oleh OS scheduler.
- **Hasil Metrik Produksi**:
  - Throughput naik dari 120.000 TPS menjadi **3.200.000 TPS**.
  - Latensi p99 turun stabil ke **$\mathbf{850\text{ nanodetik}}$**, p99.9 di **$\mathbf{1.8\text{ mikrodetik}}$**.
  - Tidak ada lagi alokasi GC pause (`0 allocs/op`).

---

### 9. Trade-offs

| Dimensi | Mutex / Channel-Based Queue | Lock-Free MPMC Ring Buffer |
| :--- | :--- | :--- |
| **Throughput (High Contention)** | Rendah - Sedang ($< 1\text{M ops/sec}$) | Ekstrem ($10\text{M} - 40\text{M ops/sec}$) |
| **Tail Latency (p99/p99.9)** | Fluktuatif & Buruk (terdampak kernel scheduler) | Sangat Stabil & Deterministik (Sub-mikrodetik) |
| **CPU Utilization** | Rendah saat idle (Thread sleep/parking) | Tinggi jika menggunakan busy-spinning backoff |
| **Memory Footprint** | Dinamis (tumbuh sesuai kebutuhan) | Statis/Besar di awal (Pre-allocated contiguous buffer) |
| **Debugging & Maintenance** | Relatif Mudah (Race Detector bekerja optimal) | Sangat Sulit (Memory ordering bugs, Hardware quirks) |
| **Flexibility** | Unbounded atau dynamic resize | Bounded, ukuran mutlak fixed power of two |

---

### 10. Common Mistakes & Troubleshooting

1. **Mengabaikan The ABA Problem**:
   - *Issue*: Thread 1 membaca pointer A. Thread 2 mengubah A $\to$ B $\to$ A. Thread 1 mengeksekusi CAS dan berhasil, padahal struktur internal A mungkin sudah dimodifikasi atau di-*free*.
   - *Fix*: Gunakan *Double-Word Compare-And-Swap* (DWCAS) dengan versi counter tag (Tagged Pointer) atau manfaatkan epoch-based reclamation / hazard pointers jika mengimplementasikan dynamic node-based structures.
2. **Lupa Memberikan Cache Line Padding**:
   - *Issue*: Meletakkan `head` dan `tail` atomic counter bersebelahan di dalam struct.
   - *Symptom*: Latensi queue membengkak ketika thread producer dan consumer berjalan di core berbeda.
   - *Fix*: Tambahkan `[56]byte` (atau `[7]uint64`) padding di antara variabel-variabel tersebut untuk memastikannya berada pada cache line 64-byte yang berbeda.
3. **Busy Spinning Tanpa Backoff Strategy**:
   - *Issue*: Goroutine mengeksekusi infinite tight loop tanpa yield saat buffer penuh/kosong.
   - *Symptom*: CPU core mencapai 100%, konsumsi daya melompat, dan goroutine lain kelaparan (*starvation*).
   - *Fix*: Terapkan backoff berjenjang: Tight Spin (1-10 iterasi) $\to$ `runtime.Gosched()` / CPU pause $\to$ Exponential Sleep jika kontensi berlanjut.
4. **Memory Reordering Bugs pada Weak Memory Models (ARM/PowerPC)**:
   - *Issue*: Pada x86, store order terjaga secara hardware (TSO). Namun pada ARM/Apple Silicon, CPU dapat mereorder instruksi *store* dan *load* secara agresif.
   - *Fix*: Pastikan payload benar-benar sudah tersimpan sebelum sequence dipublikasikan. Gunakan fungsi atomik yang menjamin semantics *Acquire/Release* (di Go: `sync/atomic` menjamin *Sequential Consistency* secara default).

---

### 11. Best Practices (Production Checklist)

- [ ] **Kapasitas Power of Two**: Validasi bahwa kapasitas antrean selalu berukuran $2^k$. Ganti operasi modulo `%` yang lambat ($\sim 10\text{--}20\text{ cycles}$) dengan operasi bitwise AND `& (capacity - 1)` ($1\text{ cycle}$).
- [ ] **No Dynamic Allocations in Hot Path**: Pre-alokasikan seluruh memori array pada inisialisasi. Jangan alokasikan pointer baru di dalam method `Enqueue()` atau `Dequeue()`.
- [ ] **Explicit Struct Alignment**: Periksa alignment struct menggunakan tool audit memori seperti `fieldalignment` dari Go analysis toolkit (`golang.org/x/tools/go/analysis/passes/fieldalignment`).
- [ ] **Clear References to Prevent GC Leak**: Saat melakukan dequeue dari array berisikan objek referensi, timpa slot dengan `zero-value` agar GC dapat membersihkan memori yang tidak lagi dirujuk.
- [ ] **Benchmark Under Realistic Multi-Core Contention**: Jangan benchmark struktur data lock-free hanya pada single goroutine. Gunakan `-cpu 4,8,16,32` pada Go benchmark untuk memvalidasi performa di bawah tekanan koherensi bus memori multi-core.

---

### 12. Hands-on Practice

Buat repositori lokal untuk menguji perbedaan performa antara unpadded struct, padded struct, dan channel standar bawaan.

#### Langkah 1: Buat Direktori & File Pengujian
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
go mod init enterprise-m02
```

#### Langkah 2: Buat Implementasi & Benchmark Code (`queue_test.go`)
Simpan file berikut di `hands-on/m02/queue_test.go`:

```go
package main

import (
	"sync"
	"sync/atomic"
	"testing"
)

// Struktur tanpa padding (False Sharing prone)
type UnpaddedCounter struct {
	a uint64
	b uint64
}

// Struktur dengan padding eksplisit
type PaddedCounter struct {
	a    uint64
	_pad [7]uint64
	b    uint64
}

func BenchmarkFalseSharing(b *testing.B) {
	b.Run("FalseSharing_Unpadded", func(b *testing.B) {
		var c UnpaddedCounter
		b.RunParallel(func(pb *testing.PB) {
			for pb.Next() {
				// Dua operasi atomik berdekatan dalam satu cache line
				atomic.AddUint64(&c.a, 1)
				atomic.AddUint64(&c.b, 1)
			}
		})
	})

	b.Run("Mitigated_Padded", func(b *testing.B) {
		var c PaddedCounter
		b.RunParallel(func(pb *testing.PB) {
			for pb.Next() {
				// Terpisah oleh 56 byte padding (berada pada cache line berbeda)
				atomic.AddUint64(&c.a, 1)
				atomic.AddUint64(&c.b, 1)
			}
		})
	})
}

func BenchmarkMPMC_Vs_GoChannel(b *testing.B) {
	const queueSize = 65536
	b.Run("Standard_Go_Buffered_Channel", func(b *testing.B) {
		ch := make(chan int, queueSize)
		var wg sync.WaitGroup
		b.ResetTimer()

		for i := 0; i < b.N; i++ {
			wg.Add(2)
			go func() {
				defer wg.Done()
				for j := 0; j < 1000; j++ {
					ch <- j
				}
			}()
			go func() {
				defer wg.Done()
				for j := 0; j < 1000; j++ {
					<-ch
				}
			}()
			wg.Wait()
		}
	})
}
```

#### Langkah 3: Eksekusi Benchmark & Analisis Profiling
Jalankan benchmark dengan multi-core load:
```bash
go test -bench=BenchmarkFalseSharing -cpu=1,2,4,8 -benchmem
```

*Analisis*: Perhatikan bahwa pada CPU=1, performa keduanya hampir identik. Namun saat CPU $\ge 4$, versi `FalseSharing_Unpadded` akan mengalami regresi latensi masif akibat MESI Cache Invalidation protocol pada hardware level.

---

### 13. Exercise

#### Level Easy
- **Tugas**: Buat fungsi verifikasi alokasi memori `VerifyCacheAlignment(t *testing.T, ptr1, ptr2 unsafe.Pointer)` yang mengembalikan nilai boolean apakah dua alamat memori berada pada Cache Line 64-byte yang berbeda atau tidak.
- **Petunjuk**: Gunakan operasi aritmatika pointer: `uintptr(ptr1) / 64 != uintptr(ptr2) / 64`.

#### Level Medium
- **Tugas**: Implementasikan **Single-Producer Single-Consumer (SPSC) Ring Buffer** tanpa operasi CAS sama sekali (hanya menggunakan instruksi atomik load/store dengan acquire-release ordering atau `atomic.LoadUint64`/`StoreUint64`). Bandingkan throughput-nya dengan implementasi MPMC di atas.
- **Petunjuk**: Pada SPSC, producer adalah satu-satunya entitas yang menulis ke `head`, dan consumer adalah satu-satunya entitas yang menulis ke `tail`. Oleh karena itu, tabrakan writer tidak mungkin terjadi, sehingga CAS tidak diperlukan.

#### Level Hard
- **Tugas**: Buat modul **Lock-Free Dynamic Work-Stealing Deque** berbasis algoritma Chase-Lev (sering dipakai dalam Go Runtime Scheduler dan Java ForkJoinPool).
- **Karakteristik**:
  - Owner thread melakukan `PushBottom` dan `PopBottom` secara lock-free LIFO (stack behavior untuk cache locality).
  - Thief threads melakukan `Steal` dari `Top` secara lock-free FIFO menggunakan atomic CAS.
  - Implementasikan dynamic resizing array secara aman saat antrean penuh tanpa memblokir thief threads.

---

### 14. Challenge

**Skenario Kasus**:
Anda adalah Principal Infrastructure Engineer di sebuah perusahaan IoT global. Sistem Anda menerima telemetri log dari **1.000.000 perangkat secara concurrent** melalui koneksi TCP gRPC. Anda ditugaskan membangun pipeline pemrosesan in-memory dengan constraint:
1. **Throughput Target**: Minimal 5.000.000 message/detik pada satu mesin AWS c6i.16xlarge (64 vCPU, 128 GB RAM).
2. **SLA Latensi**: p99 $\le 10\text{ mikrodetik}$, zero GC pause spikes.
3. **Karakteristik Data**: Payload bervariasi antara 128 byte hingga 1 KB.

**Tantangan Arsitektur**:
Rancang arsitektur internal pipeline tersebut tanpa menggunakan database atau broker eksternal (Kafka/RabbitMQ) di node ingress:
- Bagaimana Anda mempartisi worker goroutines terhadap antrean? (Apakah satu MPMC Queue global atau banyak SPSC Queues dengan sharding hash?)
- Bagaimana Anda mendesain Memory Arena / Byte Buffer Reuse untuk memastikan **$0$ allocs/op** sepanjang umur hidup aplikasi?
- Tuliskan dokumen arsitektur dan kerangka implementasi kode modular lengkap untuk pipeline tersebut.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (5 Pertanyaan)
1. Berapakah ukuran tipikal satu cache line pada arsitektur prosesor x86_64 dan modern ARM64?
   - A. 16 Bytes
   - B. 32 Bytes
   - C. 64 Bytes
   - D. 128 Bytes
2. Mengapa struktur data array sekuensial umumnya memiliki performa traversi yang jauh lebih cepat dibanding linked list, meskipun keduanya memiliki kompleksitas algoritma $\mathcal{O}(n)$?
   - A. Linked list selalu dialokasikan di dalam stack.
   - B. Array memanfaatkan CPU spatial cache locality dan hardware prefetching secara efisien.
   - C. Linked list membutuhkan operasi modulus pada setiap node.
   - D. Array otomatis menghapus kebutuhan Garbage Collection.
3. Apa kepanjangan dari operasi atomik hardware "CAS"?
   - A. Check-And-Swap
   - B. Compare-And-Set / Compare-And-Swap
   - C. Clear-And-Sync
   - D. Concurrent-Access-State
4. Apa yang dimaksud dengan status 'I' (*Invalid*) pada protokol koherensi cache MESI?
   - A. Data pada cache line tersebut sudah kadaluarsa karena telah dimodifikasi oleh core lain.
   - B. Cache line tersebut rusak secara elektrik pada silicon die.
   - C. Data siap dituliskan ke DRAM secara asynchronous.
   - D. Cache line hanya bisa dibaca oleh core lokal.
5. Operasi modulus `pos % capacity` dapat dioptimasi menjadi operasi bitwise `pos & (capacity - 1)` hanya jika kapasitas memenuhi kondisi:
   - A. Bernilai bilangan ganjil.
   - B. Bernilai bilangan prima.
   - C. Bernilai bilangan pangkat dua ($2^k$).
   - D. Lebih besar dari 1024.

#### B. Intermediate (5 Pertanyaan)
6. Apa manifestasi teknis utama dari insiden *False Sharing* pada performa aplikasi multi-threaded?
   - A. Terjadinya crash memory access violation (SIGSEGV).
   - B. Terjadinya data corruption akibat balapan penulisan data.
   - C. Terjadinya penurunan throughput secara drastis akibat saling invalidasi cache line antar core (*cache bouncing*).
   - D. Thread mengalami deadlock permanen di level kernel OS.
7. Pada implementasi MPMC Ring Buffer Dmitry Vyukov, mengapa setiap slot memerlukan sequence counter terpisah?
   - A. Untuk mencegah alokasi garbage collection.
   - B. Untuk menandai tahapan siklus (turn) kepemilikan slot antara producer dan consumer secara independen tanpa locking global.
   - C. Hanya sebagai penanda ID transaksi audit log.
   - D. Untuk mendukung sequential consistency pada memory bus non-x86 saja.
8. Apa yang menyebabkan fenomena *convoying* pada concurrent systems yang menggunakan Kernel Mutex?
   - A. CPU pipeline branch predictor salah memprediksi branching instruksi.
   - B. Ketika thread pemegang lock ditangguhkan penjadwalannya oleh OS, seluruh thread lain ikut tertahan di antrean OS, melumpuhkan latensi.
   - C. Kompiler melakukan reordering instruksi secara agresif.
   - D. Terjadinya starvation pada L3 cache.
9. Mengapa tipe pointer generic pada Golang/Java dalam lock-free queue rentan menimbulkan memory leak jika slot sequence tidak diisi *zero-value* saat di-dequeue?
   - A. Pointer memory langsung di-corrupt oleh atomic hardware.
   - B. Slot array internal tetap mereferensikan objek tersebut di heap, mencegah GC membersihkannya meskipun data sudah selesai dikonsumsi.
   - C. Hardware register akan menahan alamat memori tersebut secara permanen.
   - D. Runtime mematikan GC saat instruksi atomik aktif.
10. Kapan Single-Producer Single-Consumer (SPSC) Queue lebih disukai dibanding Multi-Producer Multi-Consumer (MPMC) Queue?
    - A. Ketika memori sistem di bawah 512 MB.
    - B. Ketika pola pemrosesan data adalah partitioned/sharded stream di mana tepat satu worker thread memproses satu partisi aliran data secara dedicated.
    - C. Ketika data harus selalu disimpan di disk storage.
    - D. Ketika tidak ada akses ke CPU multi-core.

#### C. Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario 1**: Sebuah tim arsitek mengganti antrean berbasis mutex dengan queue lock-free tanpa bounded limit (unbounded dynamic linked-node CAS queue). Saat terjadi lonjakan traffic abnormal selama 15 menit, server crash dengan error `OOM (Out Of Memory)` atau latency p99.9 membengkak hingga puluhan detik. Apa akar masalah arsitektural dari implementasi ini?
12. **Skenario 2**: Profiling CPU menggunakan Linux `perf c2c` pada order matching system menunjukkan metrik `HITM` (Hit Modified Cache Line) yang sangat tinggi di sekitar variabel atomic struct antrean. Langkah struktural konkret apa yang wajib dilakukan pada level kode sumber untuk mengeliminasi metrik tersebut?
13. **Skenario 3**: Dalam sistem audit finansial real-time, producer mempublikasikan struct transaksi ke ring buffer tanpa memory barriers/atomic store pada payload data. Di mesin Intel x86 sistem berjalan normal, namun ketika dideploy ke AWS Graviton (prosesor ARM64), data transaksi yang dibaca oleh consumer seringkali bernilai kosong atau korup sebagian. Fenomena apa yang terjadi?

---

### Kunci Jawaban Quiz

#### A. Basic
1. **C** (Ukuran standar cache line pada arsitektur modern adalah 64 bytes).
2. **B** (Array memiliki kontiguitas memori, memaksimalkan cache prefetcher dan mengurangi cache miss).
3. **B** (Compare-And-Swap / Compare-And-Set).
4. **A** (Invalid menandakan cache line tidak valid lagi karena core lain telah memodifikasinya).
5. **C** (Hanya berlaku untuk bilangan eksak power-of-two, $2^k$).

#### B. Intermediate
6. **C** (False sharing memicu cache-bouncing yang membuang bandwidth bus memori).
7. **B** (Sequence counter per slot meregulasi koordinasi multi-turn produsen dan konsumen secara non-blocking).
8. **B** (Thread holding lock preemption oleh kernel scheduler menahan thread-thread lain).
9. **B** (Array slot memegang reference pointer di heap; harus di-nil kan agar GC bisa membebaskannya).
10. **B** (SPSC lebih optimal untuk arsitektur partisi/aktor karena meniadakan overhead CAS sama sekali).

#### C. Skenario Kasus
11. **Analisis Skenario 1**: Struktur *unbounded lock-free node-based queue* mengalokasikan node baru di heap pada setiap operasi enqueue (`malloc`/`runtime.newobject`). Ketika laju data ingress melebihi laju konsumsi, alokasi heap meledak tak terkendali, memicu kerja GC berlebih dan akhirnya OOM crash. Selain itu, traversi node-based memicu pointer chasing dan L3 cache misses masif. Solusi enterprise: Wajib menggunakan **Bounded Pre-allocated Array Ring Buffer** dengan kebijakan backpressure eksplisit.
12. **Analisis Skenario 2**: Metrik `HITM` yang tinggi menandakan terjadinya *Cache Line Bouncing* akibat **False Sharing**. Solusinya adalah menyisipkan padding memori sebesar 64 bytes (atau 56 bytes padding jika variabel bernilai 8 byte) menggunakan struct dummy padding (misal: `_pad [7]uint64` atau compiler attribute `alignas(64)`) di antara variabel-variabel atomic yang sering dimutasi oleh thread berbeda.
13. **Analisis Skenario 3**: Fenomena ini disebabkan oleh **Weak Memory Ordering Architecture** pada prosesor ARM. Prosesor x86 secara hardware memiliki model memori *Total Store Order (TSO)* di mana operasi penulisan (*store-store*) tidak pernah ditukar posisinya oleh CPU. Namun pada ARM64, CPU diizinkan mereorder penulisan memori. Akibatnya, flag penanda (sequence) terbit dan dibaca consumer sebelum penulisan payload transaksi selesai dikomit ke L1 cache. Solusinya: Gunakan instruksi dengan *Store-Release* dan *Load-Acquire* memory semantics / atomic barriers.

---

### 16. Summary

1. **Memory Wall & Latency Reality**: Efisiensi struktur data enterprise tidak hanya ditentukan oleh notasi $\mathcal{O}(N)$, melainkan oleh keramahannya terhadap hierarki cache CPU hardware. Cache miss ke DRAM membutuhkan biaya waktu hingga 100x lipat dibanding akses L1 cache.
2. **Eliminasi False Sharing**: Menempatkan variabel atomik independen yang sering dimutasi core berbeda ke dalam satu cache line 64-byte adalah anti-pattern fatal. Terapkan *explicit 64-byte cache line padding* pada arsitektur sistem tingkat rendah.
3. **Lock-Free Bounded Ring Buffer**: Menawarkan throughput luar biasa dan tail latency yang konsisten dengan menggantikan os-level mutex locks menggunakan hardware-supported primitive **CAS**, manipulasi bitwise masking power-of-two, dan pre-alokasi memori penuh saat startup.
4. **Hardware Architecture Awareness**: Rekayasa perangkat lunak modern untuk sistem bare-metal/high-throughput menuntut pemahaman arsitektur prosesor (TSO vs Weak Memory Ordering, MESI protocol, Store Buffers). Memastikan konsistensi penulisan data sebelum publikasi state adalah kunci stabilitas sistem di era prosesor multi-core heterogen.