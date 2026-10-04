# Kurikulum Enterprise: Data Structures & Algorithms
## Kategori: 01-Core-Foundations
### BAB 08: Materi Lanjutan
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis dan Memitigasi False Sharing & Cache Thrashing**: Mengidentifikasi degradasi throughput pada struktur data concurrent berbasis CPU cache line bouncing (L1/L2/L3) dan menerapkan teknik *cache-line padding* secara presisi.
- **Mengimplementasikan Struktur Data Lock-Free Berbasis Atomics**: Merancang antrean sekuensial nir-kunci (*lock-free circular ring buffer*) menggunakan *Compare-And-Swap* (CAS) dan *memory barriers/fences* untuk mencapai throughput jutaan operasi per detik (*ops/sec*) pada latensi sub-mikrodetik.
- **Mengevaluasi Memory Layout & Mechanical Sympathy**: Memilih antara layout *Array-of-Structures* (AoS) dan *Structure-of-Arrays* (SoA) guna memaksimalkan efisiensi perangkat keras melalui *hardware prefetching* dan vektorisasi SIMD.
- **Mendiagnosis Masalah Concurrency Lanjutan**: Mendeteksi dan mengatasi fenomena *ABA Problem*, *Memory Ordering violations*, dan *thread starvation* dalam runtime multi-threaded.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Arsitektur Komputer Dasar**: Memahami konsep register CPU, level cache (L1, L2, L3), RAM, serta siklus instruksi per clock (*IPC*).
- **Algoritma & Struktur Data Fundamental**: Paham kompleksitas asimtotik Big-O (waktu dan ruang), implementasi dasar array, pointer/reference, *linked list*, dan *circular queue*.
- **Konkurensi Dasar**: Familiar dengan konsep OS threads, *race conditions*, *deadlocks*, *mutexes/locks*, dan operasi primitif atomik dasar.
- **Tooling**: Terbiasa dengan runtime/compiler bertipe statis (Go, Rust, C++, atau Java) serta profiler CPU/Memory (seperti `pprof`, `perf`, atau `valgrind`).

---

### 3. Concept & Internal Architecture

#### 3.1 Mechanical Sympathy & Hirarki Memori Modern
Pada sistem terdistribusi dan sistem pemrosesan transaksi berkecepatan tinggi, faktor pembatas performa (*bottleneck*) bukan lagi kecepatan clock CPU, melainkan transfer data antara RAM dan CPU (*Memory Wall*). 

```
+-------------------------------------------------------------+
| CPU Core 0                  CPU Core 1                      |
| +-------------+             +-------------+                 |
| | Registers   | (< 1 cycle) | Registers   | (< 1 cycle)     |
| +-------------+             +-------------+                 |
| | L1 Data/Inst| (~1-2 ns)   | L1 Data/Inst| (~1-2 ns)       |
| +-------------+             +-------------+                 |
| | L2 Cache    | (~3-5 ns)   | L2 Cache    | (~3-5 ns)       |
| +-------------+             +-------------+                 |
+-------------------------------------------------------------+
| Shared L3 Cache (~10-15 ns)                                 |
+-------------------------------------------------------------+
| Interconnect Bus (QPI / UPI / Infinity Fabric)              |
+-------------------------------------------------------------+
| Main Memory (DRAM) (~60-100 ns)                             |
+-------------------------------------------------------------+
```

Data tidak pernah dimuat dari memori utama per *byte* atau per *word*, melainkan dalam blok berukuran tetap yang disebut **Cache Line** (umumnya 64 byte pada arsitektur x86_64 dan ARM64).

#### 3.2 Protokol Koherensi Cache (MESI/MOESI) & False Sharing
Ketika beberapa thread pada core CPU yang berbeda memanipulasi variabel independen yang secara fisik berada dalam satu *cache line* 64-byte yang sama, protokol koherensi cache (seperti MESI: *Modified, Exclusive, Shared, Invalid*) memaksa cache line tersebut di-invalidate secara bolak-balik di antara core. Peristiwa ini disebut **False Sharing**.
- Akibat: Throughput anjlok drastis (hingga 90%) karena bus saturasi dan core terus-menerus menunggu sinkronisasi L3/RAM (*cache bouncing*), meskipun secara logis tidak ada data yang bertabrakan.
- Solusi: Melakukan isolasi variabel menggunakan *cache-line padding* sebesar 64 byte (atau 128 byte pada arsitektur tertentu) untuk memastikan variabel yang sering diubah dialokasikan pada cache line eksklusif.

#### 3.3 Anatomi Lock-Free Bounded Ring Buffer
Struktur data *Lock-Free Ring Buffer* (seperti yang dipopulerkan oleh LMAX Disruptor) menghilangkan kebutuhan terhadap kernel-level locks (`pthread_mutex`, sync.Mutex) yang mahal karena context-switch (sekitar 1-3 mikrodetik). Struktur ini mengandalkan:
1. **Array Pra-alokasi Bounded**: Memori dialokasikan di awal secara kontigu untuk meminimalkan *garbage collection* dan memaksimalkan *hardware spatial prefetching*.
2. **Atomic Head & Tail Sequences**: Indeks penunjuk posisi baca (*read*) dan tulis (*write*) diperbarui menggunakan instruksi CPU atomic (`atomic.CompareAndSwap`, `atomic.Add`, `atomic.LoadAcquire`, `atomic.StoreRelease`).
3. **Power-of-Two Sizing**: Ukuran buffer $N$ selalu dipangkatkan dua ($N = 2^k$). Dengan karakteristik ini, operasi modulo index `index % N` dapat dioptimalkan menjadi operasi bitwise AND: `index & (N - 1)`.

---

### 4. Why & What

| Dimensi | Mutex-Based Blocking Queue | Lock-Free Concurrent Ring Buffer |
| :--- | :--- | :--- |
| **Mekanisme Sinkronisasi** | OS Syscall / Kernel Sleep / Futex | Atomic CAS / CPU Memory Barriers |
| **Context Switch Overhead** | Tinggi (1.000 - 3.000 ns per blocking event) | Nol (Thread tetap berada di user-space) |
| **Latensi (p99 / p99.9)** | Fluktuatif dan tinggi saat kontensi tinggi | Deterministik, sub-mikrodetik |
| **Throughput Maksimum** | ~1 - 5 juta pesan/detik | 20 - 100+ juta pesan/detik |
| **Kerentanan Deadlock** | Ada jika urutan penguncian salah | Bebas Deadlock (*Deadlock-free*) |
| **Kompleksitas Kode** | Rendah - Menengah | Sangat Tinggi (Raw memory management, memory fences) |

**Mengapa ini penting?**
Dalam sistem berskala enterprise seperti bursa efek (*algorithmic trading*), *real-time fraud detection*, dan *telemetry ingestion* yang memproses puluhan juta request per detik, jeda context switch dari mutex konvensional memperkenalkan ekor latensi (*tail latency* p99/p999) yang tidak dapat ditoleransi oleh SLA bisnis.

---

### 5. How: Alur Kerja Atomic State & Memory Ordering

Langkah-langkah operasional pada Lock-Free Multi-Producer Single-Consumer (MPSC) Ring Buffer:

```
[PRODUCER 1] --------+
                     |--> [Claim Tail via CAS] -> [Write Data to Slot] -> [Publish Sequence]
[PRODUCER 2] --------+                                                               |
                                                                                     v
[CONSUMER]   <--------------------------------------- [Read Data when Sequence Published]
```

1. **Reservation Phase**: Producer membaca atomic sequence penunjuk ekor (`tail`). Producer menghitung apakah kapasitas buffer mencukupi terhadap sequence kepala (`head`).
2. **Arbitration Phase (CAS)**: Producer mencoba menggeser `tail` menggunakan instruksi `Compare-And-Swap (CAS)`. Jika gagal (karena Producer lain telah mendahului), ia melakukan *spin-wait* atau *backoff* lalu mencoba kembali.
3. **Write Phase**: Producer yang berhasil memiliki hak eksklusif untuk menulis data pada slot array `tail & (capacity - 1)`. Slot ini tidak akan disentuh oleh Producer lain.
4. **Publication Phase**: Producer memperbarui sequence penanda bahwa data pada slot tersebut telah siap dikonsumsi. Operasi ini harus menggunakan semantik *Release Memory Ordering* untuk menjamin data pada payload telah tersimpan secara sempurna sebelum status ketersediaannya terlihat oleh core lain.
5. **Consumption Phase**: Consumer membaca data secara berurutan sesuai sequence yang telah dipublikasikan, memproses payload, lalu memperbarui pointer `head` menggunakan semantik *Acquire Memory Ordering*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Rel Kereta Relai Bersekat (False Sharing vs Padded)

Bayangkan dua petugas pos (Core 0 dan Core 1) yang menulis catatan di satu lembar buku tulis yang sama (Cache Line 64 Byte). Meskipun Core 0 menulis di pojok kiri atas dan Core 1 di pojok kanan bawah, aturan keamanan mewajibkan bahwa buku tulis tersebut hanya boleh dipegang oleh satu petugas pada satu waktu. Akibatnya, buku tulis terus berpindah tangan bolak-balik tanpa henti. Solusinya: Berikan dua buku tulis yang berbeda (Padding 64 Byte).

#### Diagram False Sharing & Memory Layout

```
KONDISI BURUK (FALSE SHARING TERJADI):
Memory Cache Line (64 Bytes)
+------------------------------------+------------------------------------+
| Core 0 Mutates: 'head' (8 Bytes)   | Core 1 Mutates: 'tail' (8 Bytes)   |
+------------------------------------+------------------------------------+
                   \                                /
                    \                              /
                     Cache Line Invalidation Bouncing
                         (Degradasi Performa Berat)

KONDISI IDEAL (DILENGKAPI CACHE-LINE PADDING):
Cache Line 0 (64 Bytes):
+------------------------------------+------------------------------------+
| Core 0: 'head' (8 Bytes)           | Padding / Unused (56 Bytes)        |
+------------------------------------+------------------------------------+
Cache Line 1 (64 Bytes):
+------------------------------------+------------------------------------+
| Core 1: 'tail' (8 Bytes)           | Padding / Unused (56 Bytes)        |
+------------------------------------+------------------------------------+
```

---

### 7. Implementasi Kode

Berikut adalah implementasi **Multi-Producer Single-Consumer (MPSC) Lock-Free Ring Buffer** performa tinggi menggunakan Golang standar industri, dilengkapi cache padding untuk mencegah false sharing.

#### 7.1 Struktur Data & Padding

```go
package ringbuffer

import (
	"runtime"
	"sync/atomic"
	"unsafe"
)

// CacheLinePad mencegah false sharing dengan mengisi cache line 64-byte.
type CacheLinePad struct {
	_ [7]uint64 // 56 bytes padding
}

// Slot merepresentasikan sel data pada circular buffer
type Slot[T any] struct {
	sequence uint64
	value    T
}

// MPSCRingBuffer adalah bounded queue lock-free untuk multi-producer dan single-consumer.
type MPSCRingBuffer[T any] struct {
	_        CacheLinePad
	head     uint64 // Hanya dikonsumsi/diubah oleh Consumer
	_        CacheLinePad
	tail     uint64 // Dimutasi secara atomic oleh Multi-Producer
	_        CacheLinePad
	mask     uint64
	capacity uint64
	buffer   []Slot[T]
}

// NewMPSCRingBuffer menginisialisasi ring buffer dengan kapasitas kelipatan dua.
func NewMPSCRingBuffer[T any](capacity uint64) *MPSCRingBuffer[T] {
	if capacity < 2 || (capacity&(capacity-1)) != 0 {
		panic("Kapasitas harus berupa bilangan positif pangkat dua (power-of-two)")
	}

	rb := &MPSCRingBuffer[T]{
		capacity: capacity,
		mask:     capacity - 1,
		buffer:   make([]Slot[T], capacity),
	}

	for i := uint64(0); i < capacity; i++ {
		// Inisialisasi sequence slot agar Producer dapat menulis di putaran pertama
		rb.buffer[i].sequence = i
	}

	return rb
}
```

#### 7.2 Enqueue (Multi-Producer CAS Logic)

```go
// Enqueue memasukkan elemen baru ke dalam ring buffer.
// Mengembalikan false jika antrean penuh (Non-blocking).
func (rb *MPSCRingBuffer[T]) Enqueue(val T) bool {
	var currentTail uint64
	var node *Slot[T]

	for {
		currentTail = atomic.LoadUint64(&rb.tail)
		node = &rb.buffer[currentTail&rb.mask]
		seq := atomic.LoadUint64(&node.sequence)
		diff := int64(seq) - int64(currentTail)

		if diff == 0 {
			// Slot siap untuk ditulis. Klaim posisi tail secara atomic.
			if atomic.CompareAndSwapUint64(&rb.tail, currentTail, currentTail+1) {
				break
			}
			// Gagal CAS: Producer lain mendahului, ulangi iterasi.
		} else if diff < 0 {
			// Buffer dalam kondisi penuh
			return false
		} else {
			// Tail tertinggal dari sequence, yield thread CPU
			runtime.Gosched()
		}
	}

	// Tulis payload data ke slot yang berhasil diklaim secara eksklusif
	node.value = val

	// Publikasikan bahwa penulisan selesai dengan menginkrementasi sequence.
	// Atomic store ini bertindak sebagai Memory Barrier (Release)
	atomic.StoreUint64(&node.sequence, currentTail+1)
	return true
}
```

#### 7.3 Dequeue (Single-Consumer Drain Logic)

```go
// Dequeue mengambil elemen terdepan dari ring buffer.
// Mengembalikan false jika buffer kosong (Non-blocking).
func (rb *MPSCRingBuffer[T]) Dequeue() (T, bool) {
	currentHead := rb.head
	node := &rb.buffer[currentHead&rb.mask]
	seq := atomic.LoadUint64(&node.sequence)
	diff := int64(seq) - int64(currentHead + 1)

	if diff == 0 {
		// Data telah dipublikasikan dan siap dibaca
		val := node.value
		
		// Bersihkan referensi untuk mencegah memory leak pada pointer types
		var zero T
		node.value = zero

		// Tandai sequence slot bahwa slot ini telah kosong untuk putaran berikutnya.
		// Nilai sequence dinaikkan sejauh (currentHead + mask + 1)
		atomic.StoreUint64(&node.sequence, currentHead+rb.mask+1)

		// Consumer bersifat single-thread, mutasi head cukup dilakukan secara terisolasi
		rb.head = currentHead + 1
		return val, true
	}

	var zero T
	return zero, false
}
```

---

### 8. Real World Case Study: Ultra-High Frequency Order Matching Engine

#### Konteks Masalah
Sebuah bursa kripto tier-1 mengalami lonjakan latensi order execution dari **50 mikrodetik** menjadi **48 milidetik** (kenaikan hampir 1000x lipat) pada kondisi pasar ekstrem dengan volume transaksi mencapai 850.000 order/detik.

#### Analisis Akar Masalah (Root-Cause Profiling)
Tim infrastruktur menjalankan Linux `perf` dan Golang `pprof`:
1. `perf record -e c2c`: Mengungkapkan fenomena **L3 Cache Line Bouncing** masif pada alamat memori `sync.Mutex` antrean utama *OrderBook*.
2. Profiler CPU menunjukkan 78% thread runtime menghabiskan waktu pada status `runtime.futex` dan `runtime.park` (blocking lock contention).
3. Terjadi alokasi pointer dynamic kecil di heap pada setiap order, memicu *Garbage Collection Stop-The-World* (STW) reguler.

```
SEBELUM OPTIMASI:
HTTP/WS Handlers (x64 Cores) -> [sync.Mutex Locked Queue] -> Order Matcher Engine
                                  ^ Context Switch Overhead: 78% CPU Burn

SETELAH OPTIMASI:
HTTP/WS Handlers (x64 Cores) -> [MPSC Lock-Free Padded RingBuffer] -> Thread-Pinned Matcher
                                  ^ CPU Cache Bouncing Tereliminasi: P99 < 800 Nanodetik
```

#### Arsitektur Solusi
1. Mengganti antrean berbasis kanal/mutex dengan **MPSC Lock-Free RingBuffer** berkapasitas $2^{20}$ slot terpadding.
2. Menggunakan **Pre-allocated Object Pools** untuk struct `Order` guna mencapai zero-heap allocation saat runtime.
3. Menjalankan thread konsumen pemroses *Matching Engine* pada core CPU khusus dengan **CPU Pinning / Thread Affinity** (`taskset` / `pthread_setaffinity_np`) untuk mencegah L1/L2 cache evictions akibat OS rescheduling.

#### Hasil Metrik Produksi
- **Throughput**: Naik dari 120.000 ops/sec menjadi 2.400.000 ops/sec.
- **Latency P99**: Turun secara permanen dari 48 ms ke 780 ns.
- **CPU System Space Utilization**: Turun dari 64% menjadi di bawah 4%.

---

### 9. Trade-offs

```
                  +--------------------------------+
                  |   Kompleksitas Implementasi    |
                  |          Tinggi                |
                  +---------------+----------------+
                                  |
                                  v
+------------------------+                 +------------------------+
| Lock-Free Concurrent   |                 | Traditional Mutex-Lock |
| Data Structures        |                 | Data Structures        |
+------------------------+                 +------------------------+
| (+) Sub-microsecond P99|                 | (+) Mudah dimengerti   |
| (+) Zero context-switch|                 | (+) Bebas busy-spin CPU|
| (-) Memory bound       |                 | (-) Tail latency buruk |
| (-) Sulit didebug      |                 | (-) Kontensi OS thread |
+------------------------+                 +------------------------+
```

| Parameter | Lock-Free Ring Buffer | Mutex-Protected Slice / Queue |
| :--- | :--- | :--- |
| **Throughput Under Load** | Eksponensial lebih tinggi | Turun drastis saat kontensi thread meningkat |
| **Penggunaan Resource CPU** | Lebih tinggi saat idle/spin-wait | Rendah saat thread idle (terparkir di OS futex) |
| **Kebutuhan Memori** | Tetap (Pre-allocated bounded) | Dinamis bertambah (Unbounded risk) |
| **Debuggability** | Ekstrem (Perlu analisis memory barrier) | Mudah (Standard stack trace inspection) |
| **Risiko Kegagalan** | Buffer overflow jika consumer macet | OOM (Out-of-Memory) jika unbounded queue |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Melupakan Garbage Collection Hazard pada Slot Ring Buffer
*Penyebab*: Saat menggunakan array of structs yang mengandung pointer (`*Payload`), ketika nilai dibaca oleh consumer, struct slot array lama tetap menyimpan pointer objek tersebut.
*Dampak*: Memory leak masif karena Garbage Collector mendeteksi objek masih dirujuk oleh array Ring Buffer.
*Troubleshooting*: Selalu set slot value ke `nil` atau zero value (`var zero T; node.value = zero`) seketika saat dequeue berhasil.

#### 2. ABA Problem pada Arsitektur Lock-Free Pointer
*Penyebab*: Thread A membaca pointer `A`, thread B memutasi pointer menjadi `B` lalu mengembalikannya lagi menjadi `A`. CAS pada Thread A mengira state tidak pernah berubah.
*Dampak*: Kerusakan integritas data struktur pointer seperti Treap, SkipList, atau Linked-Queue lock-free.
*Troubleshooting*: Gunakan penomoran versi (Versioned Pointer/Double-word CAS - `DCAS`) atau gunakan index sequence integer 64-bit yang selalu monotonik naik seperti pada algoritma Ring Buffer di atas.

#### 3. Spin-Wait Berlebihan Mengakibatkan CPU Burn 100%
*Penyebab*: Menggunakan loop `for {}` tanpa instruksi backoff saat antrean kosong atau penuh.
*Dampak*: Core CPU terbakar pada penggunaan 100%, menghasilkan panas tinggi dan mengurangi daya alokasi core lain.
*Troubleshooting*: Terapkan strategi adaptif backoff:
1. Iterasi 1 - 10: Spin no-op CPU instruction (`PAUSE`).
2. Iterasi 11 - 50: `runtime.Gosched()` / yield thread.
3. Iterasi > 50: `time.Sleep` mikrodetik atau sinkronisasi OS conditional variable.

---

### 11. Best Practices & Production Checklist

- [ ] **Power-of-Two Allocation**: Pastikan ukuran ring buffer selalu $2^n$ untuk mengganti operasi pembagian (`/` atau `%`) dengan bitwise AND (`& (n - 1)`).
- [ ] **Cache Line Alignment**: Pastikan struct state penunjuk `head` dan `tail` dipisahkan oleh padding setidaknya 64 byte (x86_64) atau 128 byte (Apple Silicon/ARM spesifik).
- [ ] **Zero-Allocation Execution Path**: Enqueue dan dequeue tidak boleh mengeksekusi instruksi alokasi memori heap runtime baru (`malloc`, `new`).
- [ ] **Monotonic Sequences**: Gunakan integer `uint64` untuk index internal sequences. Sequence tidak akan meluap (*overflow*) selama ratusan tahun meskipun memproses puluhan juta event per detik.
- [ ] **Graceful Consumer Shutdown**: Sediakan mekanisme *drain-out* yang memastikan consumer menghabiskan seluruh sisa data di buffer sebelum mematikan service engine.

---

### 12. Hands-on Practice: Hands-on M02

Mari kita bangun proyek praktikum untuk menguji keunggulan performa struktur data lock-free dengan padding melawan struktur antrean konvensional.

#### Langkah Praktikum

1. Siapkan direktori kerja:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init enterprise/m02-concurrency
```

2. Buat file `benchmark_test.go`:

```go
package main

import (
	"sync"
	"testing"
)

// Standard Mutex Queue
type MutexQueue struct {
	mu    sync.Mutex
	items []int
}

func (q *MutexQueue) Push(val int) {
	q.mu.Lock()
	q.items = append(q.items, val)
	q.mu.Unlock()
}

func (q *MutexQueue) Pop() (int, bool) {
	q.mu.Lock()
	defer q.mu.Unlock()
	if len(q.items) == 0 {
		return 0, false
	}
	val := q.items[0]
	q.items = q.items[1:]
	return val, true
}

// Jalankan benchmark kompetitif
func BenchmarkQueueContention(b *testing.B) {
	b.Run("Standard-Mutex-Queue", func(b *testing.B) {
		q := &MutexQueue{items: make([]int, 0, 1024)}
		b.ResetTimer()
		b.RunParallel(func(pb *testing.PB) {
			i := 0
			for pb.Next() {
				q.Push(i)
				q.Pop()
				i++
			}
		})
	})
}
```

3. Jalankan command benchmark dan profiler:
```bash
go test -bench=. -benchmem -cpuprofile=cpu.pprof
go tool pprof -http=:8080 cpu.pprof
```

---

### 13. Exercises

#### Level: Easy
Implementasikan fungsi helper `IsPowerOfTwo(n uint64) bool` menggunakan operasi bitwise tunggal $O(1)$ tanpa iterasi atau percabangan aritmetika.
*Clue:* Manfaatkan sifat bilangan basis 2 dalam representasi biner dan bitwise AND dengan komplemennya.

#### Level: Medium
Modifikasi implementasi `MPSCRingBuffer` di modul ini menjadi **SPSC (Single-Producer Single-Consumer)**. Hilangkan operasi atomic CAS pada penulisan `tail` dan ganti dengan atomic plain store/load murni, lalu ukur persentase kenaikan throughput-nya.

#### Level: Hard
Rancang **Dynamic Bounded Multi-Producer Multi-Consumer (MPMC) Queue** di mana Consumer tidak hanya membaca data secara berurutan, melainkan dapat membaca secara paralel (*competing consumers*) tanpa ada data yang terduplikasi atau terlewat. Gunakan mekanisme CAS ganda pada sequence slot dan `head`.

---

### 14. Challenge: High-Contention Tick Engine

**Kondisi Kasus:**
Anda adalah Principal Architect pada bursa derivatif real-time. Sistem menerima stream data order book tick dari 16 edge-gateway secara bersamaan.

**Misi Anda:**
1. Rancang algoritma buffer antrean concurrent yang menampung struct berukuran 128 byte (*Price, Volume, ClientID, Timestamp, Flags*).
2. Terapkan arsitektur di mana 16 producer dapat memasukkan data tanpa blocking, dan 4 worker thread analitik membagi beban kerja secara *lock-free batch drain*.
3. Sistem tidak boleh mengalokasikan memori sama sekali pada heap selama fase runtime setelah proses bootstrap selesai (0 B/op).
4. Buat tes ketahanan (*stress test*) untuk membuktikan bahwa tidak ada data race condition menggunakan `-race` detector, dan latensi p99 berada di bawah batas ambang 1.5 mikrodetik pada beban 2 juta events/detik.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa ukuran tipikal dari satu *cache line* pada arsitektur modern x86 dan ARM?
   - A. 8 Byte
   - B. 64 Byte
   - C. 512 Byte
   - D. 4 Kilobyte
   *Kunci: B*

2. Mengapa ukuran buffer pada circular ring buffer performa tinggi selalu dianjurkan bernilai kelipatan pangkat dua ($2^n$)?
   - A. Agar sesuai dengan ukuran page RAM di kernel.
   - B. Memungkinkan konversi operasi modulo (`%`) menjadi bitwise AND (`& (n-1)`).
   - C. Mencegah alokasi heap oleh garbage collector.
   - D. Menghindari overflow pada tipe data uint64.
   *Kunci: B*

3. Fenomena di mana dua thread memodifikasi variabel berbeda yang berada di dalam satu cache line fisik yang sama disebut...
   - A. Memory Leak
   - B. Deadlock
   - C. False Sharing
   - D. Cache Eviction
   *Kunci: C*

4. Instruksi CPU atomik apakah yang menjadi fondasi utama dalam perancangan algoritma sinkronisasi lock-free?
   - A. Compare-And-Swap (CAS)
   - B. Fetch-And-Forget (FAF)
   - C. Read-After-Write (RAW)
   - D. Mutex-Try-Lock (MTL)
   *Kunci: A*

5. Apa efek utama dari terjadinya False Sharing terhadap performa aplikasi?
   - A. Terjadinya crash aplikasi akibat SIGSEGV.
   - B. Penurunan drastis throughput akibat cache line bouncing antar-core CPU.
   - C. Nilai data menjadi korup karena race condition.
   - D. OS mematikan thread secara paksa karena out-of-memory.
   *Kunci: B*

#### 5 Pertanyaan Intermediate
6. Pada MPSC Ring Buffer yang kita rancang, mengapa consumer tidak memerlukan operasi atomik `CompareAndSwap` untuk menggeser indeks `head`?
   - A. Karena Consumer telah diproteksi oleh OS Mutex.
   - B. Karena Consumer hanya terdiri dari satu thread tunggal (*Single-Consumer*).
   - C. Karena indeks `head` otomatis diupdate oleh perangkat keras L1 cache.
   - D. Karena `head` tidak pernah dibaca oleh producer.
   *Kunci: B*

7. Mengapa array slot pada Ring Buffer harus di-clearing (`node.value = zero`) saat pembacaan dequeue selesai jika tipe `T` menyimpan referensi objek pointer?
   - A. Untuk memicu trigger CPU hardware interrupt.
   - B. Mencegah memory leak agar pointer lama dapat didaur ulang oleh GC.
   - C. Menjamin thread producer tidak mengalami panic nil pointer.
   - D. Memenuhi spesifikasi antarmuka POSIX queue.
   *Kunci: B*

8. Apa perbedaan perilaku mendasar antara operasi penguncian berbasis Mutex dengan Busy-Spin Loop atomik ketika sumber daya yang diperebutkan sedang tidak tersedia?
   - A. Mutex menempatkan thread pada status tidur (*parked*), sedangkan spin-loop terus mengeksekusi instruksi di CPU.
   - B. Spin-loop menggunakan alokasi heap, sedangkan mutex menggunakan alokasi stack.
   - C. Mutex menjamin latensi sub-nanodetik, sedangkan spin-loop tidak.
   - D. Spin-loop memicu pergantian kernel-space context switch secara konstan.
   *Kunci: A*

9. Bagaimana *Memory Barrier* (Fences) memengaruhi eksekusi instruksi pada CPU modern?
   - A. Menghentikan seluruh proses thread lain secara instan.
   - B. Mencegah CPU dan compiler melakukan penataan ulang (*reordering*) instruksi melewati batas barrier.
   - C. Menghapus seluruh data yang berada di L1 cache ke hard disk storage.
   - D. Mengubah akses memori non-volatile menjadi memori volatile.
   *Kunci: B*

10. Mengapa tipe data indeks sequence pada Ring Buffer berkecepatan tinggi dipilih menggunakan `uint64` dibandingkan `uint32`?
    - A. Arsitektur CPU 64-bit tidak dapat memproses integer 32-bit.
    - B. Nilai `uint32` akan mengalami integer overflow dalam kurun waktu beberapa menit/jam pada throughput puluhan juta pesan/detik.
    - C. Tipe data `uint64` otomatis mencegah false sharing.
    - D. Modulo bitwise hanya berfungsi pada tipe data berukuran 64-bit.
    *Kunci: B*

#### 3 Skenario Kasus Produksi
11. **Skenario A**: Tim Anda merilis aplikasi gateway WebSocket performa tinggi. Pada server 64-Core, pengujian beban menunjukkan bahwa saat client bertambah dari 1.000 menjadi 50.000, penggunaan CPU melonjak 100% pada mode *system space*, tetapi throughput request justru anjlok 80%. Alat profiling mendeteksi waktu CPU terkonsentrasi di `runtime.futex`.
    - *Diagnosis*: Apa yang terjadi dan langkah arsitektural apa yang wajib diambil?
    - *Jawaban Singkat*: Terjadi kontensi berat pada sinkronisasi thread blocking (*mutex lock contention*) yang memicu badai syscall context-switch di level OS kernel. Solusinya adalah memigrasikan saluran antrean bersama menjadi struktur lock-free ring buffer atau mempartisi antrean (*sharding*) per worker thread.

12. **Skenario B**: Seorang engineer menambahkan *cache padding* pada struct node antrean: `_ [64]byte`. Namun saat dilakukan benchmark, False Sharing tetap terdeteksi pada Core CPU i9 terbaru. Mengapa hal ini bisa terjadi?
    - *Diagnosis*: Arsitektur CPU modern tertentu memiliki unit *Spatial Prefetcher* yang memuat pasangan baris cache secara ganda (128-byte line prefetch), sehingga padding 64 byte masih memungkinkan variabel bersebelahan ditarik ke dalam unit koherensi yang sama. Solusinya: Naikkan ukuran padding menjadi 128 byte untuk arsitektur target tersebut.

13. **Skenario C**: Pada implementasi lock-free queue, sistem sesekali mencatat data corrupt di mana consumer membaca payload lama yang belum sepenuhnya ditulis oleh producer, meskipun flag status menunjukkan slot telah siap dibaca. Kesalahan implementasi fatal apa yang terjadi?
    - *Diagnosis*: Terjadi ketiadaan *Memory Ordering Barrier* (*Instruction Reordering*). Kompiler atau CPU mengeksekusi instruksi penyimpanan flag status mendahului instruksi penyimpanan payload (Write-After-Write reordering). Solusinya adalah menyisipkan operasi atomik dengan semantik *Release* saat menulis status, dan semantik *Acquire* saat membaca status.

---

### 16. Summary

1. **Mechanical Sympathy** adalah kunci performa sub-mikrodetik: Memahami batasan fisik perangkat keras (L1/L2/L3 cache, ukuran cache line 64/128-byte, memory bus) jauh lebih krusial daripada sekadar mengoptimalkan algoritma Big-O teoritis.
2. **False Sharing** adalah musuh tersembunyi pada concurrency: Variabel independen yang berada dalam satu cache line akan memicu pembatalan cache lintas core CPU secara konstan, membatasi skalabilitas vertikal multi-core.
3. **Penerapan Cache-line Padding** mengisolasi variabel aktif ke dalam batas blok memori fisik tersendiri, menjaga data tetap panas (*hot*) pada cache L1/L2 core lokal.
4. **Lock-Free Bounded Ring Buffers** menggantikan beban context-switch kernel OS yang mahal dengan instruksi CPU native (*Compare-And-Swap*, *Memory Barriers*), menghasilkan throughput ekstrim dengan variabilitas latensi (jitter) yang minimal.
5. **Zero-Allocation Architecture**: Pada sistem throughput tinggi, struktur data harus dialokasikan di awal (*pre-allocated*) dan menggunakan kembali sel memori yang telah ada guna mengeliminasi latensi acak akibat Garbage Collection.