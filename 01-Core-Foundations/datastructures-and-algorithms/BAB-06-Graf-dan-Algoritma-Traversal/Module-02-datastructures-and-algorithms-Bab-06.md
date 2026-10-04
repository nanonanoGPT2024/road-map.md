# BAB-06: Materi Lanjutan
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis** dampak hierarki memori perangkat keras (*L1/L2/L3 cache*, *cache line invalidation*, dan *false sharing*) terhadap kinerja struktur data konkuren.
*   **Merancang dan Mengimplementasikan** struktur data *lock-free* berkemampuan tinggi (*High-Throughput Lock-Free Ring Buffer*) menggunakan operasi primitif atomik (*Compare-And-Swap*, *Acquire-Release memory ordering*) tanpa *mutual exclusion lock*.
*   **Mengintegrasikan** struktur data probabilistik tingkat lanjut (*Cuckoo Filter*) untuk filtrasi keanggotaan berskala besar dengan operasi penghapusan (*dynamic deletion*) dan efisiensi ruang optimal.
*   **Mendiagnosis dan Menanggulangi** anomali performa level sistem seperti *lock contention*, *ABA problem*, dan degradasi latensi p99/p999 pada sistem pemrosesan transaksi terdistribusi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
1.  **Model Konkurensi Dasar**: *Threads*, *Goroutines/Tasks*, Mutex, Read-Write Lock, Semaphore, dan kondisi *Race Condition*.
2.  **Operasi Bitwise**: Manipulasi bit (*masking*, *shifting*, operasi XOR, representasi komplemen dua).
3.  **Algoritma & Struktur Data Fundamental**: Array linier, antrean sirkular (*circular queue*), *hash table* dengan resolusi tabrakan, dan fungsi *hash* non-kriptografis (MurmurHash3, xxHash).
4.  **Arsitektur Komputer Dasar**: Siklus instruksi CPU, register atomik, dan konsep memori virtual.

---

### 3. Concept & Internal Architecture

Implementasi struktur data kelas produksi untuk beban kerja ekstrem (*ultra-low latency*, jutaan transaksi per detik) menuntut pemahaman menyeluruh tentang bagaimana kode berinteraksi langsung dengan perangkat keras (*bare-metal & CPU microarchitecture*).

#### 3.1. CPU Cache Hierarchy & False Sharing
CPU modern tidak membaca memori per bita (*byte*), melainkan dalam blok berukuran 64 bita yang disebut **Cache Line**.

```
+-----------------------------------------------------------------+
|                        CPU Core 0                               |
|  +--------------------+      +-------------------------------+  |
|  | Register           |      | L1 Data Cache (32KB, ~1ns)    |  |
|  +--------------------+      +-------------------------------+  |
+-----------------------------------------------------------------+
                                |
+-----------------------------------------------------------------+
|  L2 Cache (Unified, 512KB - 1MB, ~3-4ns)                        |
+-----------------------------------------------------------------+
                                |
+-----------------------------------------------------------------+
|  L3 Cache (Shared across cores, 16MB - 64MB, ~10-15ns)          |
+-----------------------------------------------------------------+
                                |
+-----------------------------------------------------------------+
|  Main Memory / DRAM (DDR4/DDR5, ~60-100ns)                      |
+-----------------------------------------------------------------+
```

Ketika Core 0 mengubah variabel yang terletak pada *cache line* yang sama dengan variabel yang dibaca/ditulis oleh Core 1, protokol koherensi *cache* (seperti **MESI** - *Modified, Exclusive, Shared, Invalid*) memaksa *cache line* pada Core 1 ditandai sebagai *Invalid*. Core 1 terpaksa menyinkronkan ulang data dari L3 atau DRAM, meskipun kedua core memanipulasi variabel logis yang berbeda secara independen. Fenomena ini disebut **False Sharing**.

Untuk mengatasinya, struktur data tingkat produksi wajib menerapkan **Cache-Line Padding** (menambahkan ruang kosong sebesar 64-byte atau 128-byte) di antara penunjuk kontrol (*head* dan *tail*) yang sering dimodifikasi.

#### 3.2. Memory Ordering & Barriers
CPU mengeksekusi instruksi secara tidak berurutan (*out-of-order execution*) untuk memaksimalkan *pipeline efficiency*. Compiler juga melakukan reorganisasi kode selama optimasi. Dalam konteks konkurensi:
*   **Sequential Consistency (SeqCst)**: Menjamin eksekusi terurut secara global, namun membebankan penalti performa terbesar karena menyisipkan instruksi pembatas (*memory fence/barrier*) penuh pada CPU bus.
*   **Acquire-Release Semantics**: 
    *   *Store-Release*: Menjamin semua operasi baca/tulis sebelumnya diselesaikan sebelum operasi tulis saat ini dipublikasikan ke memori.
    *   *Load-Acquire*: Menjamin semua operasi baca/tulis berikutnya tidak dapat dieksekusi sebelum operasi baca saat ini selesai.

#### 3.3. Struktur Data: Lock-Free Ring Buffer vs Cuckoo Filter

1.  **Lock-Free Ring Buffer (Disruptor Pattern)**:
    *   Menggunakan buffer berukuran eksak eksponensial dua ($2^n$). Operasi modulo digantikan oleh operasi bitwise: `index = sequence & (capacity - 1)`.
    *   Menghindari *locking primitives* berbasis kernel (`futex` di Linux) dengan memanfaatkan `atomic.CompareAndSwap` (CAS) atau manipulasi urutan (*monotonic sequence counters*) yang disinkronkan via *memory barriers*.
2.  **Cuckoo Filter**:
    *   Alternatif modern untuk *Bloom Filter*. Mendukung operasi penyisipan (*insert*), pengecekan keanggotaan (*lookup*), dan **penghapusan (*delete*)** tanpa menurunkan akurasi.
    *   Menyimpan representasi *fingerprint* kecil (misal: 8 bit) dari kunci, bukan kunci penuh.
    *   Menggunakan dua lokasi *bucket* alternatif untuk setiap item yang dihitung menggunakan *partial-key cuckoo hashing*:
        $$h_1(x) = \text{hash}(x)$$
        $$h_2(x) = h_1(x) \oplus \text{hash}(\text{fingerprint}(x))$$
    *   Jika kedua *bucket* penuh, algoritma melakukan *eviction* berantai (menendang elemen lama ke lokasi alternatifnya) hingga ruang kosong ditemukan.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Lock-Based / Traditional) | Pendekatan Lanjutan Produksi (Lock-Free / Cache-Aware) |
| :--- | :--- | :--- |
| **Mekanisme Sinkronisasi** | Mutex, Semaphore, Critical Section. | Primitif atomik, Memory Barriers, Lock-Free Sequencing. |
| **Overhead OS** | Tingkat tinggi: *Thread context switching*, interupsi kernel (`futex`), *priority inversion*. | Nol: Penjadwalan murni di tingkat *user-space*, instruksi atomik langsung CPU. |
| **Pemanfaatan Cache** | Tidak teratur; variabel terkumpul di satu segmen memori tanpa memperhitungkan *cache line*. | Dioptimasi; *cache line padding* eksplisit untuk meniadakan *false sharing*. |
| **Pengecekan Keanggotaan** | Bloom Filter statis: Mendukung *insert* & *query*, **tidak dapat menghapus data**. | Cuckoo Filter: Mendukung *insert*, *query*, dan *dynamic deletion* dengan *spatial locality* tinggi. |
| **Karakteristik Latensi** | Jitter tinggi pada beban puncak (p99/p999 spiking drastis akibat perebutan *lock*). | Terprediksi, stabil dengan p99 sub-mikrodetik (*zero syscall overhead*). |

---

### 5. How (Workflow Detail)

#### 5.1. Alur Kerja Lock-Free Ring Buffer (Single Producer - Single Consumer)
1.  **Inisialisasi**: Alokasikan array berukuran $2^n$. Setel `writeSequence = 0` dan `readSequence = 0` pada *cache line* terpisah.
2.  **Enqueue (Producer)**:
    *   Ambil nilai `currentTail = writeSequence.Load()`.
    *   Ambil nilai `currentHead = cachedReadSequence` (baca nilai lokal yang di-cache untuk mengurangi akses memori lintas core).
    *   Jika `currentTail - currentHead >= capacity`, baca `readSequence.Load()` aktual dari memori utama. Jika masih penuh, lakukan *backoff/spin*.
    *   Tulis data ke `buffer[currentTail & (capacity - 1)]`.
    *   Perbarui `writeSequence` menggunakan operasi *Store-Release* agar data terlihat oleh Core pembaca sebelum indeks bergeser.
3.  **Dequeue (Consumer)**:
    *   Ambil nilai `currentHead = readSequence.Load()`.
    *   Ambil nilai `currentTail = cachedWriteSequence`.
    *   Jika `currentHead >= currentTail`, baca `writeSequence.Load()` aktual. Jika kosong, return kondisi antrean kosong (*yield/spin*).
    *   Baca elemen dari `buffer[currentHead & (capacity - 1)]`.
    *   Perbarui `readSequence` menggunakan operasi *Store-Release*.

#### 5.2. Alur Kerja Cuckoo Filter Insertion
```
[Input Data] -> Hash(Data) -> Fingerprint (f), Index1 (i1)
      |
      v
Hitung Index2: i2 = i1 XOR Hash(f)
      |
      +---> Apakah Bucket[i1] memiliki slot kosong? --YES--> Simpan f di Bucket[i1] -> Selesai
      |
      +---> NO: Apakah Bucket[i2] memiliki slot kosong? --YES--> Simpan f di Bucket[i2] -> Selesai
      |
      +---> NO: Pilih secara acak indeks curr_idx = (i1 atau i2)
            Loop max_kicks (misal: 500 iterasi):
              Tukar (Swap) f dengan fingerprint yang ada di Bucket[curr_idx]
              curr_idx = curr_idx XOR Hash(f_lama)
              Jika Bucket[curr_idx] memiliki slot kosong:
                 Simpan f_lama -> Selesai
            Filter Penuh (Kapasitas Maksimal Tercapai -> Lakukan Resize)
```

---

### 6. Analogy & Diagram ASCII

#### 6.1. False Sharing vs Cache Line Padding
```
KONDISI 1: FALSE SHARING TERJADI (Degradasi Kinerja Berat)
[----------------------------- 64-Byte Cache Line -----------------------------]
[  Core 0 Menulis: Head (8B)  ] [  Core 1 Menulis: Tail (8B)  ] [ Sisa Data...  ]
              |                               |
       CPU 0 Mengubah Head            CPU 1 Mengubah Tail
              \                               /
           KESIMPULAN: Seluruh 64-Byte Line Dibatalkan!
           Core 0 dan Core 1 saling memblokir L1 Cache satu sama lain.

KONDISI 2: CACHE-LINE PADDING (Terisolasi Sempurna)
[----------------------------- Cache Line 1 (64 Bytes) ------------------------]
[ Head (8B) ] [ Padding Kosong / Unused Space (56 Bytes)                       ]
                                                                ^ Terpisah
[----------------------------- Cache Line 2 (64 Bytes) ---------|--------------]
[ Tail (8B) ] [ Padding Kosong / Unused Space (56 Bytes)        v              ]
```

#### 6.2. Ring Buffer Pointer Progression
```
Indeks Masking (Kapasitas = 8):
Index Mask = 8 - 1 = 7 (0b00000111)

Sequences: 0   1   2   3   4   5   6   7   8   9   10
Slots:    [0] [1] [2] [3] [4] [5] [6] [7] [0] [1] [2] ... (Wrap around mulus)
                                           ^
                     (Sequence 8 & 7) = Slot 0
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Mutex Bottleneck vs Atomic CAS
Contoh demonstrasi bagaimana *lock* tradisional menimbulkan *overhead* latensi dibandingkan operasi atomik.

```go
package main

import (
	"sync"
	"sync/atomic"
	"testing"
)

type MutexCounter struct {
	mu sync.Mutex
	v  uint64
}

func (c *MutexCounter) Inc() {
	c.mu.Lock()
	c.v++
	c.mu.Unlock()
}

type AtomicCounter struct {
	v atomic.Uint64
}

func (c *AtomicCounter) Inc() {
	c.v.Add(1)
}
```

#### 7.2. Practical Example: Lock-Free Single-Producer Single-Consumer (SPSC) Ring Buffer
Implementasi kelas produksi dalam Go dengan *cache-line padding* penuh (`[56]byte` / `[64]byte`), validasi *power-of-two*, dan manipulasi *atomic load-acquire/store-release*.

```go
package ringbuffer

import (
	"errors"
	"runtime"
	"sync/atomic"
	"unsafe"
)

var (
	ErrBufferFull  = errors.New("ring buffer is full")
	ErrBufferEmpty = errors.New("ring buffer is empty")
)

const (
	CacheLinePadSize = 64
)

// SPSCQueue adalah struktur antrean Lock-Free Single-Producer Single-Consumer
type SPSCQueue[T any] struct {
	// Cache line terisolasi untuk Producer
	_pad0        [CacheLinePadSize]byte
	tail         atomic.Uint64
	_pad1        [CacheLinePadSize - unsafe.Sizeof(atomic.Uint64{})]byte
	cachedHead   uint64
	_pad2        [CacheLinePadSize - 8]byte

	// Cache line terisolasi untuk Consumer
	head         atomic.Uint64
	_pad3        [CacheLinePadSize - unsafe.Sizeof(atomic.Uint64{})]byte
	cachedTail   uint64
	_pad4        [CacheLinePadSize - 8]byte

	// Buffer data yang diakses secara bersamaan
	buffer       []T
	mask         uint64
	capacity     uint64
	_pad5        [CacheLinePadSize]byte
}

// NewSPSCQueue membuat antrean dengan kapasitas pembulatan ke pangkat dua terdekat
func NewSPSCQueue[T any](capacity uint64) *SPSCQueue[T] {
	realCap := roundUpToPowerOfTwo(capacity)
	return &SPSCQueue[T]{
		buffer:   make([]T, realCap),
		capacity: realCap,
		mask:     realCap - 1,
	}
}

func roundUpToPowerOfTwo(v uint64) uint64 {
	if v == 0 {
		return 1
	}
	v--
	v |= v >> 1
	v |= v >> 2
	v |= v >> 4
	v |= v >> 8
	v |= v >> 16
	v |= v >> 32
	v++
	return v
}

// Enqueue memasukkan elemen ke buffer. Hanya boleh dipanggil oleh SATU Producer Goroutine.
func (q *SPSCQueue[T]) Enqueue(val T) error {
	tail := q.tail.Load()
	
	// Cek kapasitas menggunakan cachedHead lokal untuk menghindari bus saturation
	if tail-q.cachedHead >= q.capacity {
		q.cachedHead = q.head.Load()
		if tail-q.cachedHead >= q.capacity {
			return ErrBufferFull
		}
	}

	// Tulis item ke slot
	q.buffer[tail&q.mask] = val

	// Publikasikan tail dengan store release semantics
	q.tail.Store(tail + 1)
	return nil
}

// Dequeue mengambil elemen dari buffer. Hanya boleh dipanggil oleh SATU Consumer Goroutine.
func (q *SPSCQueue[T]) Dequeue() (T, error) {
	head := q.head.Load()

	// Cek ketersediaan menggunakan cachedTail lokal
	if head >= q.cachedTail {
		q.cachedTail = q.tail.Load()
		if head >= q.cachedTail {
			var zero T
			return zero, ErrBufferEmpty
		}
	}

	// Baca data dari slot
	val := q.buffer[head&q.mask]
	
	// Kosongkan referensi lama jika tipe data pointer untuk menghindari memory leak
	var zero T
	q.buffer[head&q.mask] = zero

	// Publikasikan head yang dimajukan
	q.head.Store(head + 1)
	return val, nil
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Ultra-Low Latency Order Routing Engine (Fintech)
*   **Profil Beban**: 5.000.000 pesanan per detik (*order events/sec*) pada jam pembukaan bursa.
*   **SLA**: Latensi pemrosesan internal *Order Matching Engine* p99 harus $< 2.5\ \mu\text{s}$ (mikrodetik).
*   **Masalah Arsitektur Awal**: Menggunakan *Go Standard Channel* (`chan OrderEvent`) dengan beberapa worker. Terjadi *lock contention* masif pada runtime channel lock internal Go, memicu lonjakan p999 hingga $45\ \text{ms}$ akibat *goroutine parking* dan *rescheduling* oleh OS thread.

```
ARSITEKTUR SEBELUMNYA (Bottleneck):
Multiple Ingestion Gateways ---> [ Shared Go Channel (Locks inside) ] ---> Order Engine (Latency Spikes)

ARSITEKTUR SETELAH REFACORING (LMAX Disruptor Pattern - Cache Aligned SPSC):
Ingestion Core 1 ---> [ Lock-Free SPSC Ring Buffer ] ---> Sequencer (Pinned Core)
Ingestion Core 2 ---> [ Lock-Free SPSC Ring Buffer ] --------^
                                                            |
                                        [ Zero-Allocation Ring Buffer ]
                                                            |
                                                            v
                                            [ Order Matching Engine Thread ]
```

#### Implementasi Solusi
1.  **Thread Pinning**: Mengunci *Sequencer* dan *Order Engine* ke Core CPU spesifik via OS affinities (`taskset` atau `sched_setaffinity`).
2.  **Dedicated SPSC Buffers**: Masing-masing *Ingestion Gateway* memiliki 1 *Ring Buffer* khusus menuju *Sequencer*. Menghilangkan kondisi *Multiple-Producer*.
3.  **Hasil Pengukuran Produksi**:
    *   **Throughput**: Meningkat dari 850.000 ops/detik menjadi 7.200.000 ops/detik per server.
    *   **Latensi p99**: Turun drastis dari $14.2\ \text{ms}$ ke $850\ \text{ns}$ ($0.85\ \mu\text{s}$).
    *   **GC Pauses**: Berkurang 98% karena eliminasi alokasi *heap* dinamis dalam antrean transaksi.

---

### 9. Trade-offs

```
+------------------------------------+---------------------------------------+
| SPSC Lock-Free Ring Buffer         | Mutex-Protected Blocking Queue        |
+------------------------------------+---------------------------------------+
| [+] Latensi sub-mikrodetik stabil. | [+] Desain API sederhana dan aman.    |
| [+] Zero kernel context switches.  | [+] Mendukung MPMC tanpa arsitektur   |
| [-] Konsumsi CPU 100% saat spin.   |     tambahan.                         |
| [-] Terbatas 1 Producer &          | [-] Biaya Context Switch (~1-3 us).   |
|     1 Consumer per instance.       | [-] Priority Inversion risk tinggi.   |
+------------------------------------+---------------------------------------+
| Cuckoo Filter                      | Standard Bloom Filter                 |
+------------------------------------+---------------------------------------+
| [+] Mendukung operasi penarikan    | [+] Implementasi sangat sederhana.    |
|     data (Deletion).               | [+] Operasi penyisipan tanpa resiko   |
| [+] Cache locality lebih baik.     |     kegagalan (tidak ada loop swap).  |
| [-] Kinerja insert degradasi jika  | [-] Tidak mendukung penghapusan       |
|     load factor > 90%.             |     elemen sama sekali.               |
| [-] Implementasi hashing kompleks. | [-] Spatial cache misses tinggi.      |
+------------------------------------+---------------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Common Mistakes
1.  **Lupa Cache Padding**: Meletakkan `head` dan `tail` atomic secara bersebelahan di dalam deklarasi `struct`. Ini menghasilkan *False Sharing* permanen yang membuat sistem bekerja lebih lambat daripada antrean berbasis mutex biasa.
2.  **Memory Ordering Neglect**: Pada arsitektur non-x86 (seperti ARM64 yang memiliki model *Weak Memory Ordering*), membaca data sebelum memvalidasi urutan atomik (*Relaxed loads*) akan memicu pembacaan data sampah (*stale/corrupted state*).
3.  **Busy-Waiting CPU Throttling**: Melakukan *tight infinite loop* (`for {}`) saat buffer kosong tanpa instruksi relaksasi CPU (`runtime.Gosched()` atau instruksi CPU `PAUSE`). Hal ini menyebabkan *thermal throttling* pada core CPU fisik.

#### 10.2. Troubleshooting Guide
*   **Gejala**: Latensi meningkat seiring bertambahnya Core CPU pada server skala besar (misal: 64 Core NUMA).
    *   *Deteksi*: Gunakan tool profiling perangkat keras: `perf c2c record -F 60000 -- ./aplikasi` dilanjutkan `perf c2c report`.
    *   *Analisis*: Cari metrik *HitM* (*Hit Modified Cache Line*). Tingginya persentase *HitM* menandakan adanya *False Sharing* antar core.
    *   *Solusi*: Terapkan isolasi *cache line* sebesar 64 atau 128 byte menggunakan *struct padding*.

---

### 11. Best Practices (Production Checklist)

- [ ] **Alokasi Pangkat Dua**: Pastikan ukuran buffer diverifikasi selalu bernilai $2^n$ untuk menjamin operasi `index & (size - 1)` bitwise valid.
- [ ] **Struktur Padding Lengkap**: Verifikasi ukuran padding struktural menggunakan `unsafe.Offsetof()` pada pengujian integrasi (`unit test`).
- [ ] **Backoff Strategy**: Terapkan strategi adaptif saat buffer kosong:
    1. Fase 1: *Spin* dengan instruksi `PAUSE` CPU (0 - 100 siklus).
    2. Fase 2: Panggil *thread yield* / `runtime.Gosched()`.
    3. Fase 3: *Sleep* pendek atau *Park* melalui sinyal OS jika menganggur > 10 ms.
- [ ] **Nilai Pointer Reset**: Untuk bahasa dengan *Garbage Collector*, pastikan slot buffer dibersihkan (`nil` atau nilai *zero*) saat di-*dequeue* untuk mencegah retensi memori tersembunyi (*loitering objects*).
- [ ] **Non-Blocking Fallback**: Selalu sediakan metrik metrik drop/reject jika antrean penuh dalam kondisi beban burst, jangan lakukan alokasi dinamis instan di jalur kritis (*hot path*).

---

### 12. Hands-on Practice

Buat seluruh file praktikum di direktori: `hands-on/m02/`.

#### Langkah 1: Siapkan Struktur Proyek
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init m02-advanced-dsa
```

#### Langkah 2: Buat Implementasi Ring Buffer
Tulis file `spsc_queue.go` yang berisi kode antrean dari **Bagian 7.2**.

#### Langkah 3: Buat Benchmark untuk Mendeteksi False Sharing
Buat file `queue_test.go`:
```go
package ringbuffer

import (
	"sync"
	"testing"
)

func BenchmarkSPSCQueue(b *testing.B) {
	q := NewSPSCQueue[uint64](65536)
	var wg sync.WaitGroup
	wg.Add(2)

	b.ResetTimer()

	// Producer
	go func() {
		defer wg.Done()
		for i := uint64(0); i < uint64(b.N); i++ {
			for q.Enqueue(i) != nil {
				// Spin
			}
		}
	}()

	// Consumer
	go func() {
		defer wg.Done()
		for i := uint64(0); i < uint64(b.N); i++ {
			for {
				if _, err := q.Dequeue(); err == nil {
					break
				}
			}
		}
	}()

	wg.Wait()
}
```

#### Langkah 4: Eksekusi dan Verifikasi
Jalankan benchmark dan analisis throughput:
```bash
go test -bench=. -benchtime=5s -cpu=2 -benchmem
```

---

### 13. Exercise

#### Level Easy
*   **Instruksi**: Tambahkan fungsi `Len() uint64` thread-safe pada `SPSCQueue` yang menghitung jumlah elemen yang belum diproses tanpa menggunakan mutex.
*   **Kriteria Keberhasilan**: Perhitungan harus mengembalikan selisih non-negatif antara `tail` dan `head`, menangani kemungkinan kondisi balapan saat `tail` diperbarui sebelum pembacaan `head`.

#### Level Medium
*   **Instruksi**: Ubah implementasi `SPSCQueue` menjadi **SPMC (Single Producer Multiple Consumer)** menggunakan operasi `atomic.CompareAndSwapUint64` pada bagian `head`.
*   **Kriteria Keberhasilan**: Lebih dari satu goroutine dapat mengonsumsi pesan secara bersamaan tanpa menimbulkan duplikasi konsumsi data ataupun *deadlock*.

#### Level Hard
*   **Instruksi**: Rancang dan implementasikan struktur data **Cuckoo Filter** ringkas yang mendukung 4-slot per bucket dan ukuran fingerprint 8-bit. Implementasikan fungsi `Insert(key []byte) bool`, `Lookup(key []byte) bool`, dan `Delete(key []byte) bool`.
*   **Kriteria Keberhasilan**: Implementasi mampu menangani *kicking loop* hingga batas 500 iterasi dengan benar dan memiliki akurasi penolakan *False Positive* $< 3\%$ dengan pemanfaatan memori konstan.

---

### 14. Challenge

**Skenario**: Sistem *Centralized Logging & Security Auditing* Anda menerima 1.000.000 pesan log audit keamanan per detik dari berbagai microservices. Setiap pesan memiliki tanda tangan unik berupa SHA-256 hash. Anda diminta membangun komponen *In-Memory Deduplicator* yang:
1.  Dapat mendeteksi dan membuang duplikasi pesan dalam jendela waktu geser (*sliding window*) 5 menit terakhir.
2.  Hanya dialokasikan memori RAM maksimal **128 Megabytes** (Sistem operasi akan mematikan proses via OOM Killer jika melebihi batas ini).
3.  Memiliki batas toleransi *False Positive* maksimal 0.1% (tidak boleh membuang pesan asli secara keliru lebih dari 1 dari 1.000 pesan unik).
4.  Wajib mendukung penghapusan jejak pesan secara dinamis saat pesan tersebut keluar dari jendela waktu 5 menit.

**Tugas Anda**: Buat proposal arsitektur struktur data, tentukan struktur data yang digunakan beserta kalkulasi matematis kapasitas memori, representasi *eviction scheme*, dan skema konkurensinya tanpa menggunakan *Global Lock*.

---

### 15. Quiz Evaluasi Pemahaman

#### 15.1. Pertanyaan Basic
1.  Berapa ukuran umum dari satu *CPU Cache Line* pada prosesor arsitektur modern (x86-64 / ARM64)?
2.  Mengapa kapasitas antrean sirkular *high-performance* hampir selalu diharuskan berupa angka eksponensial dua ($2^n$)?
3.  Apa yang dimaksud dengan kondisi *False Sharing*?
4.  Apa keunggulan fungsional utama dari *Cuckoo Filter* dibandingkan *Standard Bloom Filter*?
5.  Apa perbedaan mendasar antara instruksi CPU atomic biasa (*Atomic Store*) dengan *Store-Release Memory Barrier*?

#### 15.2. Pertanyaan Intermediate
6.  Pada antrean SPSC (Single Producer Single Consumer), mengapa penunjuk `readSequence` (head) tidak perlu diperbarui menggunakan instruksi CAS (*Compare-And-Swap*) melainkan cukup dengan *Store* atomik biasa?
7.  Bagaimana strategi *Local Sequence Caching* (seperti `cachedHead` pada Producer) mengurangi beban pada jalur komunikasi CPU bus (*System Bus Traffic*)?
8.  Jelaskan skenario mengapa operasi `Delete` pada Cuckoo Filter berpotensi menghapus elemen yang salah jika terjadi tabrakan *fingerprint*!
9.  Bagaimana cara kerja formula *Partial-Key Cuckoo Hashing* ($h_2 = h_1 \oplus \text{hash}(\text{fingerprint})$) memungkinkan kita menemukan kembali indeks alternatif tanpa perlu mengetahui data aslinya?
10. Apa yang dimaksud dengan *ABA Problem* dalam struktur data berbasis *Compare-And-Swap*, dan struktur data mana (Queue, Stack, Hash Table) yang paling rentan terhadap masalah ini?

#### 15.3. Skenario Kasus Produksi
11. **Skenario 1**: Aplikasi trading Anda mengalami lonjakan latensi p999 setiap kali *Garbage Collection* berjalan, meskipun alokasi objek per detik dalam status stabil. Hasil investigasi memori menunjukkan antrean antarmuka *Ring Buffer* memegang pointer lama dari objek yang sudah diproses. Analisis sumber masalah dan tuliskan perbaikan kodenya!
12. **Skenario 2**: Profiling performa pada server bare-metal berspesifikasi 128 Core CPU menunjukkan efisiensi antrean *Lock-Free* justru anjlok saat beban konkurensi diuji pada core ke-65 dan seterusnya. Server tersebut memiliki konfigurasi multi-socket (Dual Socket NUMA). Mengapa hal ini terjadi dan bagaimana Anda merestrukturisasi alokasi memori buffer?
13. **Skenario 3**: Sebuah Cuckoo Filter beroperasi di lingkungan produksi dengan *load factor* 94%. Tiba-tiba operasi `Insert` memicu lonjakan latensi dramatis yang berujung pada kegagalan alokasi. Apa penyebab langsung di tingkat algoritma internal, dan langkah pencegahan proaktif apa yang wajib diterapkan?

---

### 16. Summary

| Topik Utama | Rangkuman Esensial | Dampak Produksi |
| :--- | :--- | :--- |
| **CPU Cache Alignment** | Memisahkan variabel *state* baca/tulis ke *cache line* 64-byte mandiri via padding. | Mencegah *False Sharing*, menurunkan latensi p99 hingga orde mikrodetik. |
| **Bitwise Masking** | Menggunakan operasi bitwise AND (`seq & (size - 1)`) untuk pengganti modulo aritmatika. | Menghemat 10-20 siklus clock CPU pada setiap operasi manipulasi antrean. |
| **SPSC Lock-Free Pattern** | Koordinasi Producer-Consumer dengan status sequence atomik dan caching lokal. | Menghilangkan *kernel context switch*, mendongkrak *throughput* hingga jutaan ops/sec. |
| **Cuckoo Filtering** | Filtrasi probabilistik berbasis *swapping* fingerprint yang mendukung mutasi dinamis. | Penghematan RAM drastis pada jalur verifikasi data skala masif dengan kapabilitas *Delete*. |