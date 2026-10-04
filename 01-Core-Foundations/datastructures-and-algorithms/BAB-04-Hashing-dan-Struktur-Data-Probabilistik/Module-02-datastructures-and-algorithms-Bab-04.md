# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Bab 04: Materi Lanjutan
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Topik Inti**: *Lock-Free Data Structures, Cache-Conscious Memory Layouts, dan High-Throughput Storage Engines (LSM-Tree vs. B+Tree)*

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** dampak arsitektur mikroprosesor modern (*CPU cache lines*, *MESI cache coherency protocol*, *memory ordering*) terhadap efisiensi struktur data konkuren.
- **Mengeliminasi** *false sharing* dan *contention overhead* melalui perancangan struktur data yang memanfaatkan *memory padding* dan *cache-line alignment*.
- **Merancang dan Mengimplementasikan** struktur data *lock-free* dan *wait-free* berkinerja tinggi (seperti SPSC/MPMC *Ring Buffer*) menggunakan primitif atomik (*Compare-And-Swap*, *Atomic Load-Acquire*, dan *Atomic Store-Release*).
- **Mengevaluasi dan Menentukan** arsitektur *storage engine* (*B+Tree* vs. *Log-Structured Merge-Tree*) untuk sistem terdistribusi berbasis karakteristik *workload* (Read-Heavy vs. Write-Heavy).
- **Mendiagnosis** anomali performa tingkat rendah seperti degradasi akibat *garbage collection pressure*, *ABA problem*, dan *unbounded write stalls*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta diwajibkan telah menguasai:
1. **Dasar Struktur Data**: Tree traversal, Hash Table resizing, Linked List, dan Binary Heap.
2. **Sistem Komputer & OS**: Virtual memory, Paging, Context switching, Thread lifecycle, dan Mutex/Semaphore.
3. **Kompleksitas Algoritma**: Notasi Big-O, Amortized Time Complexity, dan Space Complexity.
4. **Bahasa Pemrograman Tingkat Sistem**: Pemahaman pointer, alokasi heap vs. stack, dan model memori pada level bahasa (Go, C++, atau Rust).

---

### 3. Concept & Internal Architecture

#### 3.1. Simetri Hardware Modern dan Struktur Data
Perangkat keras modern tidak mengakses memori byte per byte; pemrosesan berlangsung dalam granularitas blok:
- **Cache Line**: Satuan terkecil data yang dimuat ke dalam L1/L2/L3 cache (umumnya 64 byte pada arsitektur x86_64 dan ARM64).
- **Spatial Locality**: Data yang berdekatan secara memori fisik akan dimuat ke cache secara bersamaan (*contiguous arrays* vs *node-based linked lists*).
- **False Sharing**: Dua core independen memodifikasi dua variabel berbeda yang berada di dalam satu *cache line* 64-byte yang sama, memaksa bus invalidasi data antar-core melalui protokol MESI (*Modified, Exclusive, Shared, Invalid*), menurunkan throughput hingga 90%.

```
Cache Line (64 Bytes)
+-----------------------------------+-----------------------------------+
| Thread A memodifikasi Variable X  | Thread B memodifikasi Variable Y  |
| (Offset 0x00 - 0x07)              | (Offset 0x08 - 0x0F)              |
+-----------------------------------+-----------------------------------+
Result: Core 1 & Core 2 saling me-retract L1 Cache via protokol MESI!
```

#### 3.2. Taksonomi Struktur Data Konkuren
1. **Lock-Based (Blocking)**:
   - Menggunakan OS Mutex / Spinlock.
   - Risiko: *Priority Inversion*, *Deadlock*, dan *High Context-Switch Latency* (~1.5–5 mikrosekon per switch).
2. **Lock-Free**:
   - Menjamin bahwa **setidaknya satu thread** membuat progres dalam rentang waktu terhingga, terlepas dari starvation pada thread lain. Menggunakan loop `CAS` (*Compare-And-Swap*).
3. **Wait-Free**:
   - Menjamin bahwa **setiap thread** selalu membuat progres dalam sejumlah langkah terhingga. Sangat sulit diimplementasikan, umumnya digunakan pada sistem *Hard Real-Time*.

#### 3.3. Dualitas Storage Engine: B+Tree vs. LSM-Tree
| Dimensi | B+Tree | LSM-Tree (Log-Structured Merge-Tree) |
| :--- | :--- | :--- |
| **Arsitektur Utama** | In-place update, balance n-ary tree di disk | Append-only log, out-of-place update |
| **Pola I/O Tulis** | Random I/O (Dirty page flushing) | Sequential I/O (WAL + MemTable flush) |
| **Write Amplification**| Sangat tinggi (Modifikasi 10 byte menulis 4-16KB block) | Terkendali secara periodik via Compaction |
| **Read Amplification** | Rendah ($O(\log_B N)$ disk reads) | Tinggi (Cek MemTable, Immutable MemTable, L0..LN SSTables) |
| **Penggunaan Ideal** | OLTP Read-intensive (PostgreSQL, MySQL InnoDB) | High-throughput ingestion (Cassandra, RocksDB, ScyllaDB) |

---

### 4. Why & What
- **Why**: Pada beban jutaan transaksi per detik (*High-Frequency Trading*, *Telemetri IoT*, *Payment Gateway*), penguncian berbasis kernel (*mutex*) menjadi *bottleneck* utama. Begitu pula I/O berbasis disk: menulis secara *random* mengakibatkan *I/O serialization queue saturation*.
- **What**:
  - **Lock-Free Ring Buffer**: Buffer melingkar nir-kunci berukuran tetap yang mengeksploitasi operasi aritmatika modular berbasis *bitwise mask* ($2^N$) dan instruksi atomik `Load/Store` dengan semantik *Acquire/Release*.
  - **Cache-Padded Nodes**: Struktur data yang disisipi byte kosong (*padding*) guna memastikan kepala baca (*read pointer*) dan kepala tulis (*write pointer*) tidak berada pada *cache line* yang sama.

---

### 5. How (Workflow Detail)

#### Siklus Eksekusi Single-Producer Single-Consumer (SPSC) Ring Buffer
1. **Inisialisasi**:
   - Alokasi buffer dengan kapasitas berukuran pangkat dua ($N = 2^k$).
   - Hitung mask: `mask = N - 1`.
   - Pisahkan indeks `head` (producer) dan `tail` (consumer) ke dalam cache line terpisah menggunakan padding 56–64 byte.
2. **Operasi Push (Producer)**:
   - Baca `tail` via `atomic.LoadAcquire`.
   - Hitung kapasitas tersisa: `head - tail`.
   - Jika buffer penuh: return `ErrQueueFull`.
   - Tulis elemen pada slot: `buffer[head & mask]`.
   - Update `head` menggunakan `atomic.StoreRelease(head + 1)`.
3. **Operasi Pop (Consumer)**:
   - Baca `head` via `atomic.LoadAcquire`.
   - Hitung ketersediaan data: `head - tail`.
   - Jika buffer kosong: return `ErrQueueEmpty`.
   - Baca elemen dari slot: `val = buffer[tail & mask]`.
   - Update `tail` menggunakan `atomic.StoreRelease(tail + 1)`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Rel Transmisi Pabrik Otomatis
Bayangkan sebuah konveyor sabuk putar (*Ring Buffer*) di mana **Pekerja Masuk (Producer)** meletakkan kotak dan **Pekerja Keluar (Consumer)** mengambil kotak.
- Jika keduanya berdiri bersebelahan pada meja yang sama (*False Sharing*), siku mereka saling membentur saat bekerja.
- Dengan memanjangkan meja sejauh 2 meter (*Cache Line Padding*), keduanya bekerja paralel tanpa saling mengganggu, hanya saling memantau nomor urut papan tulis (*Atomic Sequence Counter*).

```
Arsitektur Memori SPSC Lock-Free Ring Buffer:

   Cache Line 1 (64 bytes)              Cache Line 2 (64 bytes)
+---------------------------+        +---------------------------+
| Producer Head Index (u64) |        | Consumer Tail Index (u64) |
| 8 Bytes                   |        | 8 Bytes                   |
+---------------------------+        +---------------------------+
| Padding Space             |        | Padding Space             |
| 56 Bytes                  |        | 56 Bytes                  |
+---------------------------+        +---------------------------+
              \                                    /
               \                                  /
                v                                v
+======+======+======+======+======+======+======+======+
| [0]  | [1]  | [2]  | [3]  | [4]  | [5]  | [6]  | [7]  |  Ring Buffer Slots
+======+======+======+======+======+======+======+======+  (Contiguous Array)
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Demonstrasi Efek False Sharing vs Padding (Go)
```go
package main

import (
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

// Struktur tanpa padding: rentan terhadap False Sharing
type ContendedCounter struct {
	a uint64
	b uint64
}

// Struktur dengan cache line padding (64 byte cache line x86_64)
type PaddedCounter struct {
	a uint64
	_ [7]uint64 // 56 bytes padding -> a + padding = 64 bytes
	b uint64
	_ [7]uint64 // 56 bytes padding -> b + padding = 64 bytes
}

func benchmarkContention() {
	const iterations = 100_000_000

	// 1. Uji Kasus False Sharing
	var cc ContendedCounter
	var wg1 sync.WaitGroup
	wg1.Add(2)

	start := time.Now()
	go func() {
		for i := 0; i < iterations; i++ {
			atomic.AddUint64(&cc.a, 1)
		}
		wg1.Done()
	}()
	go func() {
		for i := 0; i < iterations; i++ {
			atomic.AddUint64(&cc.b, 1)
		}
		wg1.Done()
	}()
	wg1.Wait()
	contendedDuration := time.Since(start)

	// 2. Uji Kasus Padded
	var pc PaddedCounter
	var wg2 sync.WaitGroup
	wg2.Add(2)

	start = time.Now()
	go func() {
		for i := 0; i < iterations; i++ {
			atomic.AddUint64(&pc.a, 1)
		}
		wg2.Done()
	}()
	go func() {
		for i := 0; i < iterations; i++ {
			atomic.AddUint64(&pc.b, 1)
		}
		wg2.Done()
	}()
	wg2.Wait()
	paddedDuration := time.Since(start)

	fmt.Printf("Contended Duration: %v\n", contendedDuration)
	fmt.Printf("Padded Duration:    %v\n", paddedDuration)
	fmt.Printf("Performa Padded:    %.2fx lebih cepat\n", float64(contendedDuration)/float64(paddedDuration))
}

func main() {
	benchmarkContention()
}
```

#### 7.2. Practical Example: Production-Grade SPSC Lock-Free Ring Buffer (Go)
```go
package ringbuffer

import (
	"errors"
	"runtime"
	"sync/atomic"
)

var (
	ErrQueueFull  = errors.New("lock-free ring buffer: queue is full")
	ErrQueueEmpty = errors.New("lock-free ring buffer: queue is empty")
)

// CacheLinePad mencegah false sharing antar core
type CacheLinePad [7]uint64

// SPSCRingBuffer adalah struktur Single-Producer Single-Consumer Lock-Free FIFO queue
type SPSCRingBuffer[T any] struct {
	_prePad CacheLinePad
	head    uint64 // Dimodifikasi oleh Producer
	_pad1   CacheLinePad

	tail  uint64 // Dimodifikasi oleh Consumer
	_pad2 CacheLinePad

	mask     uint64
	capacity uint64
	storage  []T
}

// NewSPSC menginisialisasi buffer dengan kapasitas pangkat 2
func NewSPSC[T any](size uint64) *SPSCRingBuffer[T] {
	if size < 2 || (size&(size-1)) != 0 {
		// Normalisasi ke eksponen 2 terdekat
		size = nextPowerOfTwo(size)
	}

	return &SPSCRingBuffer[T]{
		capacity: size,
		mask:     size - 1,
		storage:  make([]T, size),
	}
}

func nextPowerOfTwo(n uint64) uint64 {
	n--
	n |= n >> 1
	n |= n >> 2
	n |= n >> 4
	n |= n >> 8
	n |= n >> 16
	n |= n >> 32
	n++
	return n
}

// Push memasukkan elemen ke antrean. HANYA boleh dipanggil oleh thread/goroutine tunggal (Producer).
func (rb *SPSCRingBuffer[T]) Push(item T) error {
	currentHead := atomic.LoadUint64(&rb.head)
	currentTail := atomic.LoadUint64(&rb.tail)

	if (currentHead - currentTail) >= rb.capacity {
		return ErrQueueFull
	}

	rb.storage[currentHead&rb.mask] = item

	// StoreRelease mempublikasikan penulisan data ke storage sebelum indeks head diubah
	atomic.StoreUint64(&rb.head, currentHead+1)
	return nil
}

// Pop mengambil elemen dari antrean. HANYA boleh dipanggil oleh thread/goroutine tunggal (Consumer).
func (rb *SPSCRingBuffer[T]) Pop() (T, error) {
	currentTail := atomic.LoadUint64(&rb.tail)
	currentHead := atomic.LoadUint64(&rb.head)

	if currentTail == currentHead {
		var zero T
		return zero, ErrQueueEmpty
	}

	item := rb.storage[currentTail&rb.mask]

	// Membersihkan pointer lama untuk mencegah memory leak jika T adalah pointer
	var zero T
	rb.storage[currentTail&rb.mask] = zero

	// StoreRelease memperbarui tail, membebaskan slot untuk producer
	atomic.StoreUint64(&rb.tail, currentTail+1)
	return item, nil
}

// PushWait melakukan spin-lock adaptif jika buffer penuh
func (rb *SPSCRingBuffer[T]) PushWait(item T) {
	counter := 0
	for {
		if err := rb.Push(item); err == nil {
			return
		}
		counter++
		if counter < 10 {
			// Fast-path spin
			continue
		} else if counter < 50 {
			// CPU pause/yield instruction
			runtime.Gosched()
		} else {
			// Slow-path fallback
			runtime.Gosched()
		}
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Ultra-Low Latency Order Routing Engine (Bursa Keuangan / HFT)
- **Konteks**: Sistem pencocokan order (*matching engine*) wajib memproses hingga 5.000.000 order per detik dengan batas latensi P99 < 1 mikrodetik (1000 ns).
- **Arsitektur Awal**: Menggunakan Go Channel standar (`chan Order`, buffer 65.536) yang diakses oleh 1 Producer (Network Ingestion Goroutine) dan 1 Consumer (Core Matching Engine).
- **Bottleneck yang Muncul**:
  - `chan` secara internal menggunakan `sync.Mutex`, memicu pemanggilan *scheduler* `runtime.park` dan `runtime.goready`.
  - Latensi P99 melonjak hingga 45 mikrodetik akibat *lock contention* dan *context switching*.
  - Terjadi fluktuasi cache miss L3 mencapai 34% akibat struktur data internal runtime Go `hchan`.
- **Solusi Rekayasa**:
  1. Mengganti Go Channel dengan *Lock-Free SPSC Ring Buffer* berukuran statis $2^{20}$ slot (~1 juta slot).
  2. Menerapkan *Memory Pre-allocation* dengan slot array statis (Zero Heap Allocation pada critical path).
  3. Mengisolasi core thread matching engine menggunakan OS CPU affinity (*thread pinning*).
  4. Menyisipkan *cache-line padding* pada head dan tail pointer.
- **Hasil Pengujian Produksi**:
  - **P99 Latency**: Turun drastis dari 45µs menjadi **120 nanodetik**.
  - **Throughput**: Meningkat dari 1.2M ops/s menjadi **14.8M ops/s** pada hardware x86_64 server 3.2 GHz yang sama.
  - **GC Overhead**: Zero GC time karena memori dialokasikan penuh di awal (*boot time pre-allocated buffers*).

---

### 9. Trade-offs

```
                       LATENCY & THROUGHPUT SPECTRUM
High Latency / Safe                                        Low Latency / Complex
+----------------------+--------------------+--------------------+---------------+
| OS Mutex (Kernel)    | CAS Spinlock       | Lock-Free SPSC/MPMC| Hardware HW   |
| (pthreads, Go Mutex) | (atomic.CAS loop)  | (Memory Fences)    | Acceleration  |
+----------------------+--------------------+--------------------+---------------+
* Aman dari OOM         * Risiko High CPU    * Kerumitan kodifikasi* Vendor lock-in
* Context switch drop   * Starvation hazard  * Sulit di-debug      * Biaya tinggi
```

| Tipe Struktur Data | Throughput | Latensi (P99) | CPU Overhead | Kompleksitas Rekayasa |
| :--- | :--- | :--- | :--- | :--- |
| **Mutex-Protected Queue** | Rendah (~1-2M ops/s) | Buruk (Mikrosekon) | Rendah (Thread sleep) | Sangat Rendah |
| **Atomic CAS MPMC Queue** | Sedang (~5-8M ops/s) | Cukup (Sub-mikro) | Sangat Tinggi (Spinning) | Tinggi (ABA Problem) |
| **Lock-Free SPSC Ring Buffer**| Maksimum (>15M ops/s)| Luar Biasa (<100ns) | Efisien (Zero contention)| Menengah |
| **LSM-Tree Storage** | Write: Sangat Tinggi | Write: Stabil, Read: Variatif | Tinggi (Compaction bg) | Sangat Tinggi |
| **B+Tree Storage** | Write: Sedang (I/O) | Konsisten untuk Read| Rendah (Page in-place) | Tinggi |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. ABA Problem pada Struktur Data Lock-Free Berbasis Pointer
- **Deskripsi**: Thread 1 membaca pointer A. Thread 2 memodifikasi pointer A ke B, lalu memodifikasinya kembali ke A. Thread 1 mengeksekusi `atomic.CompareAndSwapPointer` dan berasumsi kondisi memori tidak berubah, padahal data internal state-nya sudah korup.
- **Deteksi**: Crash *segmentation fault* acak pada sistem dengan konkurensi tinggi yang menggunakan *node reuse memory pool*.
- **Solusi**: Gunakan teknik *Tagged Pointers* (menyimpan versi revisi bersama alamat memori) atau *Epoch-Based Reclamation* (EBR) / *Hazard Pointers*.

#### 10.2. Lupa Membersihkan Nilai Array Slot pada Garbage-Collected Runtimes
- **Deskripsi**: Pada Go atau Java, setelah indeks ring buffer digeser oleh consumer, referensi objek yang disimpan dalam array slot tidak di-*nil*-kan.
- **Dampak**: *Memory Leak* parah (*Lapsed Listener Problem*) karena pointer tetap valid dan menahan alokasi memori GC meskipun secara semantik item sudah "dihapus".
- **Solusi**: Selalu setel `storage[index] = zeroValue` saat proses `Pop()`.

#### 10.3. Unbounded Write Stalls pada LSM-Tree
- **Deskripsi**: Laju *ingestion* producer melampaui kemampuan *disk subsystem* untuk melakukan background compaction SSTable (Level 0 ke Level 1).
- **Dampak**: Level 0 membengkak, read latency hancur, engine membekukan seluruh operasi tulis (*complete write stall*).
- **Solusi**: Implementasikan *dynamic backpressure* dan *adaptive rate limiting* berdasarkan jumlah file L0 yang pending.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Kapasitas Ukuran Berpangkat Dua ($2^N$)**: Selalu pastikan ukuran buffer berukuran $2^N$ agar operasi modulasi indeks CPU dapat digantikan oleh operasi bitwise AND (`index & (capacity - 1)`).
2. [ ] **Verifikasi False Sharing via Benchmark**: Jalankan profil memori CPU via `perf c2c` di Linux untuk memeriksa frekuensi *cache hit on modified lines*.
3. [ ] **Struktur Data Terisolasi Padding**: Sisipkan padding eksplisit berukuran 64 byte (atau 128 byte untuk platform ARM Neoverse modern) di antara field kontrol yang diakses thread berbeda.
4. [ ] **Hindari Alokasi Dinamis pada Path Kritis**: Semua node atau slot buffer wajib dialokasikan di awal (*pre-allocated pool*).
5. [ ] **Pemberian Sinyal CPU Pause**: Saat membuat algoritma *busy-wait/spinning*, sisipkan instruksi pereda konsumsi bus seperti `runtime.Gosched()` (Go) atau `_mm_pause()` (x86 C/C++) guna menghemat daya dan meningkatkan *instruction pipeline efficiency*.
6. [ ] **SSTable Bloom Filters**: Untuk LSM Tree, pastikan *Bloom Filter* dikonfigurasi dengan alokasi minimal 10 bit per key untuk menekan *read amplification* di bawah 1% false positive.

---

### 12. Hands-on Practice
Praktikum ini merancang dan menguji mikro-benchmark performa antara struktur SPSC Lock-Free vs Mutex Channel.

#### Langkah 1: Buat Direktori Kerja
Simpan seluruh file pada folder: `hands-on/m02/`

```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init m02-advanced-dsa
```

#### Langkah 2: Buat Implementasi Ring Buffer
Tulis file `ring_buffer.go` menggunakan kode produksi pada Bagian 7.2.

#### Langkah 3: Buat Benchmark File
Buat file `ring_buffer_test.go`:
```go
package ringbuffer

import (
	"sync"
	"testing"
)

func BenchmarkSPSC_LockFree(b *testing.B) {
	rb := NewSPSC[uint64](1024 * 1024)
	b.ResetTimer()

	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		for i := 0; i < b.N; i++ {
			rb.PushWait(uint64(i))
		}
	}()

	go func() {
		defer wg.Done()
		for i := 0; i < b.N; i++ {
			for {
				if _, err := rb.Pop(); err == nil {
					break
				}
			}
		}
	}()

	wg.Wait()
}

func BenchmarkGoChannel(b *testing.B) {
	ch := make(chan uint64, 1024*1024)
	b.ResetTimer()

	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		for i := 0; i < b.N; i++ {
			ch <- uint64(i)
		}
		close(ch)
	}()

	go func() {
		defer wg.Done()
		for range ch {
		}
	}()

	wg.Wait()
}
```

#### Langkah 4: Eksekusi Benchmark
```bash
go test -bench=. -benchmem -cpu 2
```
*Amati metrik: `ns/op`, alokasi memori `B/op`, dan `allocs/op`.*

---

### 13. Exercise

#### Level: Easy
- **Tugas**: Modifikasi implementasi SPSC Ring Buffer agar memiliki fungsi `Len() uint64` yang mengembalikan jumlah elemen yang saat ini ada di dalam buffer secara aman dan atomik tanpa menghentikan producer atau consumer.
- **Input**: Operasi berkelanjutan.
- **Output yang Diharapkan**: Nilai `head - tail` yang akurat terhadap ordering memori.

#### Level: Medium
- **Tugas**: Implementasikan struktur data **Two-Lock Concurrent Queue** (Michael-Scott algorithm varian locked) di mana operasi `Enqueue` dan `Dequeue` menggunakan dua mutex terpisah (`headLock` dan `tailLock`), memungkinkan operasi push dan pop berjalan paralel secara simultan.

#### Level: Hard
- **Tugas**: Perluas SPSC Ring Buffer menjadi **MPMC (Multi-Producer Multi-Consumer)** Ring Buffer berbasis siklus sequence atomik pada setiap slot (gaya LMAX Disruptor / Dmitry Vyukov MPMC Array).
- **Syarat**: Menggunakan `atomic.CompareAndSwapUint64` pada counter per slot, memitigasi thread race condition, dan menjamin zero deadlock.

---

### 14. Challenge
**Studi Kasus**: *Ultra-High Throughput Financial Ledger Streamer*
- Anda diminta merancang sub-sistem ingestion transaksi internal bank yang harus menerima 20.000.000 log transaksi per detik dari 8 core jaringan masuk (Producers) dan menulisnya ke 1 SSD Engine (Consumer).
- **Ketentuan Sistem**:
  1. Penggunaan mutex dilarang keras pada jalur transmisi data.
  2. Alokasi memori heap baru saat running dilarang keras (Zero Dynamic Allocations; GC pauses harus 0 ms).
  3. Apabila consumer lambat, sistem tidak boleh crash karena OOM; sistem harus menerapkan strategi backpressure bertingkat (Drop policy / Yield cycle / Retry token).
  4. Rancang skema *batch flushing* di mana consumer mengambil data dalam chunk terkuantisasi (misal 512 transaksi per batch) menggunakan instruksi atomik tunggal.
- **Deliverable**: Buat arsitektur lengkap beserta kode implementasi modul MPSC Ring Buffer yang mampu lulus stress testing konkurensi tanpa data corruption atau lost updates.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Berapakah ukuran tipikal dari CPU cache line pada prosesor modern x86_64?
   - A. 8 Byte
   - B. 32 Byte
   - C. 64 Byte
   - D. 128 Byte
   - *Kunci*: C
   - *Penjelasan*: Arsitektur modern x86_64 menggunakan 64 byte per cache line untuk menyeimbangkan spatial locality dan latensi pengisian bus data.

2. Masalah apa yang dipecahkan oleh *Memory Padding* pada struktur data konkuren?
   - A. Memory Leak
   - B. False Sharing
   - C. Deadlock
   - D. Out of Memory
   - *Kunci*: B
   - *Penjelasan*: Memory padding memisahkan dua variabel yang sering diakses oleh thread berbeda ke cache line yang berlainan, mencegah invalidasi cache terus-menerus.

3. Apa keuntungan utama dari kapasitas Ring Buffer yang didefinisikan dalam kelipatan pangkat 2 ($2^N$)?
   - A. Menghemat memori RAM hingga 50%
   - B. Mempercepat inisialisasi compiler
   - C. Memungkinkan penggantian operasi modulo (`%`) dengan bitwise AND (`&`)
   - D. Menjamin thread safety otomatis
   - *Kunci*: C
   - *Penjelasan*: Operasi modulo pada CPU memerlukan siklus clock relatif lambat (~10-20 cycle), sedangkan bitwise AND hanya membutuhkan 1 CPU cycle.

4. Mengapa LSM-Tree memiliki performa penulisan (*write performance*) yang jauh lebih tinggi daripada B+Tree pada media disk tradisional?
   - A. LSM-Tree tidak pernah melakukan update data
   - B. LSM-Tree mengubah random write menjadi sequential append-only log
   - C. LSM-Tree berjalan murni di memori RAM
   - D. LSM-Tree tidak memerlukan indeks
   - *Kunci*: B
   - *Penjelasan*: Penulisan berurutan (*sequential I/O*) mengeksploitasi bandwidth disk secara optimal dibandingkan modifikasi acak di banyak blok file.

5. Apa fungsi dari primitif instruksi `atomic.StoreRelease`?
   - A. Menghentikan semua thread lain secara paksa
   - B. Menjamin semua penulisan memori sebelumnya selesai terlihat oleh core lain sebelum operasi store ini dipublikasikan
   - C. Mengunci pointer ke dalam L1 cache
   - D. Menghapus referensi memori untuk GC
   - *Kunci*: B
   - *Penjelasan*: Semantik release memastikan *store buffer* di-*flush* dan membatasi *instruction reordering* oleh CPU/compiler.

#### 5 Pertanyaan Intermediate
6. Pada struktur data lock-free, apakah kelemahan utama dari pendekatan CAS (*Compare-And-Swap*) loop jika sistem mengalami konkurensi sangat tinggi (*high contention*)?
   - A. Menyebabkan deadlock permanen
   - B. Terjadi lonjakan konsumsi CPU akibat spinning dan livelock starvation pada thread yang gagal
   - C. Memori heap membengkak eksponensial
   - D. Menghasilkan race condition pada kernel level
   - *Kunci*: B
   - *Penjelasan*: Saat puluhan thread mencoba CAS pada alamat yang sama, hanya satu yang berhasil; sisanya melakukan loop spinning, membakar siklus CPU secara sia-sia.

7. Perhatikan potongan kode berikut:
   ```go
   type Node struct {
       value int64
       next  *Node
   }
   ```
   Dalam konteks lock-free stack (Treiber Stack), anomali fatal apa yang dapat terjadi jika node yang telah di-pop langsung dialokasikan kembali via memory pool?
   - A. False Sharing
   - B. ABA Problem
   - C. Priority Inversion
   - D. Buffer Overflow
   - *Kunci*: B
   - *Penjelasan*: Penggunaan kembali alamat pointer lama menyebabkan validasi CAS berhasil padahal pointer telah beralih status secara siklis (A -> B -> A).

8. Mengapa LSM-Tree memerlukan struktur data bantuan seperti *Bloom Filter* pada setiap komponen SSTable?
   - A. Menjaga data agar tetap terurut
   - B. Mempercepat proses write
   - C. Mengurangi *Read Amplification* dengan menghindari pembacaan file SSTable di disk jika key terbukti tidak ada
   - D. Menggantikan proses Compaction
   - *Kunci*: C
   - *Penjelasan*: Bloom filter dengan cepat menentukan apakah sebuah key pasti tidak ada di dalam SSTable tanpa perlu melakukan seek disk fisik.

9. Manakah protokol koherensi cache yang paling luas digunakan pada CPU multicore modern yang melandasi isu False Sharing?
   - A. TCP/IP
   - B. Raft
   - C. MESI / MOESI
   - D. Paxos
   - *Kunci*: C
   - *Penjelasan*: Protokol MESI (Modified, Exclusive, Shared, Invalid) mengatur status setiap baris cache line di seluruh core CPU.

10. Apa trade-off utama dari proses *Compaction* (misal Leveled Compaction) pada LSM-Tree?
    - A. Mempercepat penulisan saat ini dengan mengorbankan memori RAM
    - B. Meningkatkan latensi pembacaan
    - C. Mengakibatkan *Write Amplification* tinggi dan potensi *I/O latency spike* akibat pembacaan dan penulisan ulang data ke disk
    - D. Menghilangkan redundansi data secara permanen
    - *Kunci*: C
    - *Penjelasan*: Compaction membaca data dari beberapa SSTable, menyortir, dan menulis ulang berkas baru, memakai resource disk I/O secara masif.

#### 3 Skenario Kasus Produksi
11. **Skenario**: Sistem telemetri Anda memproses aliran event metrik menggunakan ring buffer konkuren. Saat diuji pada mesin 64-core, utilisasi CPU mencapai 100%, namun throughput data aktual hanya 500k ops/sec. Profiling menunjukkan persentase waktu CPU terbesar dihabiskan pada instruksi perbandingan nilai variabel atomik. Apa akar masalah dan solusinya?
    - A. Memory leak pada Go runtime; restart aplikasi secara terjadwal.
    - B. High contention CAS spinlock pada arsitektur multi-producer; ubah arsitektur menjadi *sharded single-producer queues* atau terapkan *exponential backoff* dan CPU relax pauses.
    - C. Mutex sleep starvation; ganti dengan semafor kernel.
    - D. OS swapping; matikan swap memori di tingkat kernel Linux.
    - *Kunci*: B
    - *Penjelasan*: Kontensi tinggi pada CAS loop membuang siklus CPU; membagi antrean berdasarkan ID producer (*sharding*) mengeliminasi perebutan atomik.

12. **Skenario**: Basis data LSM-Tree Anda mengalami anomali *P99.9 write latency* yang melonjak dari 1 ms menjadi 5 detik setiap 15 menit sekali. Operasi pembacaan juga ikut terdegradasi parah selama jendela waktu tersebut. Apa diagnosis yang paling presisi?
    - A. Database mengalami *deadlock* transaksi.
    - B. L0 SSTables menumpuk karena kecepatan *write* melebihi *background compaction rate*, memicu *Write Stall* protektif dari engine.
    - C. Bloom filter kehabisan memori dan melakukan flushing ke hard disk.
    - D. Log append-only (WAL) korup dan sedang di-*rebuilt* dari awal.
    - *Kunci*: B
    - *Penjelasan*: Saat background compaction tertinggal jauh di belakang incoming write rate, engine LSM sengaja menahan/memperlambat operasi tulis (*stall*) agar read performance tidak hancur total akibat L0 file overflow.

13. **Skenario**: Sebuah aplikasi pembayaran *low-latency* mengalami segmentasi memori sporadis (*memory corruption*) setelah berjalan 3 hari nonstop. Struktur data antrean yang digunakan adalah lock-free queue modifikasi internal yang mengimplementasikan *object pooling*. Tidak ada data balikan `err` dari operasi push maupun pop. Pemeriksaan *core dump* mengindikasikan node menunjuk ke referensi memori yang telah dibebaskan. Masalah apa yang sedang dihadapi tim engineering?
    - A. Memory leakage dari heap OS.
    - B. Masalah *ABA* yang memicu pembebasan memori premature atau akses pointer liar (*use-after-free*).
    - C. Kegagalan fungsi hashing hash map.
    - D. Context switch timeout dari goroutine scheduler.
    - *Kunci*: B
    - *Penjelasan*: Dalam lock-free pooling tanpa mekanisme *safe memory reclamation* (seperti Hazard Pointers atau Epoch-Based Reclamation), fenomena ABA menyebabkan thread mengakses memori yang sudah dilepas/dipakai oleh entitas lain.

---

### 16. Summary
1. **Hardware-Software Mechanical Sympathy**: Memahami batasan fisik prosesor modern—seperti *cache line boundary* (64 bytes), *cache coherency*, dan *memory ordering*—adalah prasyarat mutlak dalam merancang struktur data berkinerja ekstrem.
2. **Kekuatan Lock-Free Data Structures**: Menghilangkan *lock contention* dan *kernel context switches* menggunakan primitif atomik (`CAS`, `StoreRelease`, `LoadAcquire`) mampu meningkatkan throughput sistem dari ratusan ribu hingga puluhan juta operasi per detik.
3. **Penyelarasan Arsitektur Memori**: Struktur data berkecepatan tinggi wajib menggunakan teknik seperti *cache line padding* untuk mencegah *False Sharing*, serta memanfaatkan ukuran berbasis $2^N$ guna mengoptimalkan instruksi CPU via bitwise arithmetic.
4. **Strategi Pemilihan Storage Engine**:
   - Pilih **B+Tree** untuk sistem database yang berorientasi pada pencarian titik (*point lookup*) cepat dan beban *Read-Heavy* (OLTP standar).
   - Pilih **LSM-Tree** untuk sistem yang menghadapi beban *Write-Heavy* berlatensi konstan, dengan mengonversi operasi penulisan *random I/O* menjadi *sequential append-only stream* yang terkelola.