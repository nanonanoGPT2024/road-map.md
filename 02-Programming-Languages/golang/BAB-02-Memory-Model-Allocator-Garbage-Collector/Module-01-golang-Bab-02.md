# SEKSI 01 — IDENTITAS MODUL

| Metadata | Nilai |
| :--- | :--- |
| **Kode Modul** | `GOLANG-MOD-02-01` |
| **Kategori** | `02-Programming-Languages` |
| **Topik Pembelajaran** | *Memory Model, Allocator & Garbage Collector* |
| **Tingkat Kesulitan** | *Advanced / Deep Systems Engineering* |
| **Prasyarat** | Pemahaman konkurensi Go (*Goroutine*, *Channel*), Arsitektur Komputer (*Pointers, Registers, Cache Coherence*), *Data Types & Structs* |
| **Target Runtime** | Go 1.21+ (termasuk semantik `GOMEMLIMIT` dan *Concurrent Mark-Sweep Pacer*) |
| **Waktu Estimasi Pembelajaran** | 4-6 Jam Pembelajaran Mendalam + Lab Praktik |

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membuktikan Relasi *Happens-Before***: Mendefinisikan kepastian visibilitas memori antar-*goroutine* berdasarkan *Go Memory Model specification* tanpa mengandalkan *undefined behavior*.
2. **Mendekonstruksi Mekanisme Alokasi Memori Go Runtime**: Menjelaskan siklus hidup alokasi objek mulai dari *contigous stack allocation*, *escape analysis*, hingga *multi-level heap allocator* (`mcache`, `mcentral`, `mheap`, *size classes*).
3. **Membongkar Cara Kerja *Garbage Collector* (GC)**: Menguraikan algoritma *Concurrent Tri-color Mark-Sweep*, peran *Hybrid Write Barrier*, dan cara kerja *GC Pacer* dalam menentukan titik pemicu siklus GC.
4. **Menerapkan Teknik *Zero-Allocation & Memory Recycling***: Mendesain dan mengimplementasikan sistem berkinerja tinggi menggunakan teknik *memory reuse* (`sync.Pool`, *arena allocator* mental model, dan penataan *struct alignment*).
5. **Mendiagnosis dan Mengeliminasi *Latency Spikes***: Menggunakan perangkat observabilitas Go (`pprof`, `go tool trace`, `GODEBUG=gctrace=1`, `runtime/metrics`) untuk memitigasi *Stop-The-World* (STW) *pauses* dan *heap fragmentation*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model 1: Runtime Go sebagai Sistem Operasi Mikro
Saat menulis program Go, jangan memandang Go seperti C (yang menyerahkan sepenuhnya memori ke OS/pengembang) atau seperti Java (yang memiliki JVM tebal dengan banyak generasi memori). 
Go runtime adalah **sistem operasi tingkat pengguna (user-space micro-OS)**. Runtime ini memiliki:
- *Scheduler* sendiri ($M, P, G$).
- *Virtual Memory Manager* sendiri (mengambil blok besar dari OS kernel via `mmap` dan mempartisipasikannya sendiri).
- Mekanisme kooperatif *preemption* yang terintegrasi langsung ke pemanggilan fungsi untuk pemeriksaan stack dan alokasi.

### Mental Model 2: TCMalloc — Toko Grosir, Distributor Lokal, dan Kasir
Arsitektur Go Allocator diturunkan dari TCMalloc (*Thread-Caching Malloc*):
- **`mheap` (Pusat Distribusi Utama/Grosir)**: Memegang seluruh pool memori virtual aplikasi. Pengambilan memori di sini memerlukan penguncian global (*global mutex*).
- **`mcentral` (Distributor Wilayah)**: Mengelompokkan memori berdasarkan ukuran tetap (*span size classes*). Mengurangi granularitas *lock*.
- **`mcache` (Kasir Pribadi per Logical Processor `P`)**: Setiap prosesor logis `P` memiliki `mcache` independen. Alokasi memori berukuran kecil (*small object*) dilakukan di sini secara **lock-free** (tanpa mutex). Goroutine mengambil memori dari kasir lokalnya secepat kilat.

### Mental Model 3: Tri-color Garbage Collection sebagai Proses Audit
Bayangkan tim auditor memeriksa inventaris gudang dokumen yang sedang beroperasi penuh tanpa mematikan bisnis:
- **Objek Putih**: Dokumen belum diperiksa (calon sampah).
- **Objek Abu-abu**: Dokumen sedang dalam antrean verifikasi; referensi anak-anaknya belum dicek.
- **Objek Hitam**: Dokumen telah diverifikasi dan dipastikan valid bersama seluruh dokumen turunannya.
- **Write Barrier**: Petugas pengawas khusus yang menginterupsi seketika jika ada karyawan gudang yang memindahkan atau menyisipkan dokumen putih ke dokumen hitam di tengah audit berjalan, memastikan tidak ada data valid yang terhapus secara keliru.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Diagram Hirarki Memori Go Runtime (Allocator)

```
       +-------------------------------------------------------------+
       |                     OS Virtual Memory                       |
       |                (mmap / madvise: MADV_DONTNEED)              |
       +-------------------------------------------------------------+
                                      |
                                      v
       +-------------------------------------------------------------+
       |                           mheap                             |
       |  - Linear Page Allocator (radix tree / pageAlloc)           |
       |  - Global Lock Protected                                    |
       |  - Arenas (Chunks of 64MB chunks)                           |
       +-------------------------------------------------------------+
                     /                               \
                    /                                 \
                   v                                   v
       +-----------------------+           +-----------------------+
       |   mcentral (Class 1)  |   .....   |   mcentral (Class 67) |
       |   - Partial Spans     |           |   - Partial Spans     |
       |   - Full Spans        |           |   - Full Spans        |
       +-----------------------+           +-----------------------+
                    ^                                   ^
                    | (Refill saat kosong)              |
         +----------+-----------------------------------+----------+
         |                                                         |
+-----------------+                                       +-----------------+
|  mcache (for P0)|                                       |  mcache (for P1)|
|  - tiny alloc   |                                       |  - tiny alloc   |
|  - alloc[0..135]| (Span per size class)                 |  - alloc[0..135]|
+-----------------+                                       +-----------------+
         ^                                                         ^
         | Lock-free Alloc                                         | Lock-free Alloc
+-----------------+                                       +-----------------+
|   Goroutine G1  |                                       |   Goroutine G2  |
+-----------------+                                       +-----------------+
```

### 2. State Machine GC & Siklus Tri-Color

```
             [ GC OFF ]
                 |
                 | (Trigger: Memori mencapai target pacer / GOGC / GOMEMLIMIT)
                 v
   +-------------------------------+
   | 1. Sweep Termination (STW)    | -> Berhenti sejenak (<10-30us)
   |    - Pastikan sweep selesai   |
   |    - Aktifkan Write Barrier   |
   +-------------------------------+
                 |
                 v
   +-------------------------------+
   | 2. Concurrent Mark            | -> Berjalan paralel bersama mutator (aplikasi)
   |    - Scan Goroutine Roots     | -> Mark workers menyerap ~25% CPU (dedicated P)
   |    - White -> Grey -> Black   | -> Write Barrier mengintersepsi pointer mutasi
   +-------------------------------+
                 |
                 v
   +-------------------------------+
   | 3. Mark Termination (STW)     | -> Berhenti sejenak (<50us)
   |    - Selesaikan sisa abu-abu  |
   |    - Matikan Write Barrier    |
   +-------------------------------+
                 |
                 v
   +-------------------------------+
   | 4. Concurrent Sweep           | -> Memori bebas dikembalikan ke palloc/mcentral
   |    - Objek Putih dibebaskan   | -> Bertahap saat ada alokasi baru
   +-------------------------------+
                 |
                 +-----------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `mspan`: Satuan Dasar Alokasi
Struktur memori Go tidak mengalokasikan *byte* demi *byte* secara acak, melainkan menggunakan `mspan`. `mspan` adalah blok halaman memori fisik berurutan (*contiguous pages*, di mana 1 page Go = 8 KB).
- **Size Classes**: Go mendefinisikan 67 kelas ukuran objek (mulai dari 8 byte hingga 32 KB). Objek berukuran > 32 KB diperlakukan sebagai alokasi besar (*Large Object*) dan langsung dialokasikan dari `mheap`.
- **Span Attributes**: Menyimpan *bitmap* status bebas/terpakai (`allocBits`), penanda objek hidup saat penandaan GC (`gcmarkBits`), dan indeks elemen bebas berikutnya (`freeindex`).

### 2. Tiga Kategori Ukuran Alokasi
Runtime Go mengkategorikan ukuran alokasi menjadi tiga jenis:
1. **Tiny Allocation (< 16 Byte, tanpa pointer)**:
   - Dialokasikan ke dalam satu blok 16-byte bersama objek *tiny* lainnya via `tiny allocator` di dalam `mcache`. Sangat efisien untuk string kecil atau pointer tunggal.
2. **Small Allocation (16 Byte s.d. 32 KB)**:
   - Dibulatkan ke atas ke *size class* terdekat (misal: objek 24 byte dibulatkan ke kelas 32 byte).
   - Diambil dari `mcache.alloc[classID]` tanpa penguncian.
   - Jika `mcache` kehabisan slot kosong, ia meminta *span* baru ke `mcentral`.
3. **Large Allocation (> 32 KB)**:
   - Melewati `mcache` dan `mcentral`. Langsung meminta sejumlah *page* yang dibutuhkan ke `mheap` (memerlukan *lock* `mheap.lock`).

### 3. Dinamika Stack: *Contiguous Stacks*
Berbeda dengan C yang mengalokasikan ukuran *stack* tetap (biasanya 2 MB-8 MB per *thread*), Go mengalokasikan stack awal goroutine sebesar **2 KB**.
- Ketika ruang 2 KB ini hampir habis (dideteksi oleh instruksi prolog fungsi yang disisipkan kompilator), runtime menjalankan mekanisme `runtime.newstack`.
- Runtime mengalokasikan memori baru sebesar **2x lipat dari ukuran sebelumnya**, menyalin (*deep copy*) seluruh isi *stack* lama ke *stack* baru, menyesuaikan seluruh internal pointer yang menunjuk ke *stack* lama, lalu membebaskan *stack* lama.
- Stack Go dapat menyusut (*shrink*) kembali saat GC berlangsung jika utilisasi stack turun di bawah batas tertentu.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Go Memory Model: Semantik *Happens-Before*
Dalam sistem multiprosesor modern, *instruction reordering* oleh kompilator dan arsitektur *out-of-order execution* pada CPU (seperti CPU Store Buffers) dapat menyebabkan eksekusi instruksi terlihat terbalik oleh thread lain.

*Go Memory Model* mendefinisikan kondisi formal kapan pembacaan terhadap variabel `v` dijamin mengamati nilai yang ditulis oleh operasi penulisan lain terhadap `v`.

> **Relasi Dasar**:
> Jika kejadian $e_1$ *happens before* $e_2$, maka $e_2$ *happens after* $e_1$. Jika $e_1$ tidak *happens before* $e_2$ dan tidak *happens after* $e_2$, maka $e_1$ dan $e_2$ berlangsung secara konkuren (*concurrent*), yang berpotensi memicu *Data Race* jika melibatkan penulisan.

Aturan krusial *Happens-Before*:
- **Inisialisasi Package**: Inisialisasi package `main` terjadi setelah seluruh package yang di-*import* selesai diinisialisasi secara rekursif.
- **Goroutine Creation**: Pernyataan `go` yang membuat goroutine baru *happens before* eksekusi instruksi pertama dalam goroutine tersebut dimulai.
- **Channel Operations**:
  - Pengiriman (*send*) data pada channel *unbuffered* *happens before* penerimaan (*receive*) data selesai.
  - Penerimaan (*receive*) data pada channel *unbuffered* *happens before* proses pengiriman data selesai.
  - Penutupan (*close*) channel *happens before* penerimaan nilai nol (*zero value*) yang mengindikasikan channel tertutup selesai.
- **Locks (`sync.Mutex` / `sync.RWMutex`)**:
  - Pemanggilan `Unlock()` ke-$n$ *happens before* pemanggilan `Lock()` ke-$(n+1)$ berhasil kembali.

### 2. Mekanisme Escape Analysis
*Escape Analysis* adalah analisis statis yang dilakukan kompilator Go untuk menentukan apakah suatu objek dapat dialokasikan di *stack* fungsi lokal atau harus *escape* (lolos) ke *heap*.

Kriteria objek lolos (*escapes to heap*):
1. **Pointer Passing Outward**: Mengembalikan alamat referensi objek lokal ke luar dari scope fungsi pemanggil.
2. **Indirection via Interfaces**: Menyerahkan variabel konkret ke parameter bertipe `interface{}`. Kompilator sering kali tidak dapat menentukan tipe konkret secara mutlak saat *compile-time*, memaksa alokasi data konversi ke heap.
3. **Dynamic / Unbounded Sizing**: Mengalokasikan *slice* atau *array* yang ukurannya ditentukan oleh variabel dinamis saat *runtime* atau ukurannya terlalu besar untuk batas alokasi stack (misal: $> 64$ KB).
4. **Pointer to Pointer Assignment**: Menugaskan pointer ke variabel yang ditunjuk oleh pointer lain.

### 3. Hybrid Write Barrier (Go 1.8+)
Masalah mendasar *concurrent collector* adalah: Mutator (aplikasi) dapat mengubah pointer saat GC sedang berjalan. Jika mutator menyembunyikan pointer ke objek putih di dalam objek hitam, dan menghapus satu-satunya referensi dari objek abu-abu, objek putih tersebut tidak akan pernah di-*mark* dan terhapus secara ilegal.

Go menggunakan **Hybrid Write Barrier** (kombinasi Yuasa-style deletion barrier dan Dijkstra-style insertion barrier):
Setiap operasi penulisan pointer pada heap (`*slot = ptr`) saat GC aktif akan diintersepsi secara internal oleh runtime:

$$\text{writeBarrier}(slot, ptr) \implies \begin{cases} \text{shade}(*slot) & \text{// Tandai objek lama yang ditimpa (Yuasa)} \\ \text{shade}(ptr) & \text{// Tandai objek baru yang dimasukkan (Dijkstra)} \end{cases}$$

Keuntungan: Runtime **tidak perlu melakukan re-scan goroutine stacks** pada fase *Mark Termination*. Hal ini mereduksi durasi STW dari ratusan milidetik (pada versi lampau) menjadi **di bawah 1 milidetik**.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode yang memperagakan:
1. Escape analysis (*stack vs heap*).
2. Verifikasi perilaku memori menggunakan flag kompilasi.
3. Deteksi restrukturisasi *stack growth*.

```go
package main

import (
	"fmt"
	"runtime"
	"sync"
	"sync/atomic"
)

// InsecureData merepresentasikan struct untuk uji coba escape analysis
type InsecureData struct {
	ID    int64
	Value [128]byte
}

// 1. Fungsi yang TIDAK escape (tetap di stack)
func createOnStack() int64 {
	d := InsecureData{ID: 42}
	return d.ID // Hanya menyalin nilai primitif (pass-by-value)
}

// 2. Fungsi yang ESCAPE ke heap
//go:noinline
func createOnHeap() *InsecureData {
	d := InsecureData{ID: 100}
	return &d // Escape: alamat memori lokal dikembalikan ke luar stack frame
}

// 3. Demonstrasi Stack Growth
//go:noinline
func recursiveGrow(depth int, anchor *int) {
	var buffer [1024]byte // 1 KB frame
	buffer[0] = byte(depth)

	if depth > 0 {
		recursiveGrow(depth-1, anchor)
	} else {
		*anchor = int(buffer[0])
	}
}

func main() {
	// Demonstrasi 1: Escape Analysis
	val := createOnStack()
	ptr := createOnHeap()
	fmt.Printf("Stack Val: %d, Heap Ptr ID: %d\n", val, ptr.ID)

	// Demonstrasi 2: Stack Expansion
	var finalVal int
	recursiveGrow(10, &finalVal) // Akumulasi frame akan melebihi 2 KB, memaksa stack copy

	// Demonstrasi 3: Happens-Before dengan Atomic Store/Load
	var data int64 = 0
	var ready atomic.Bool
	var wg sync.WaitGroup

	wg.Add(2)

	// Producer
	go func() {
		defer wg.Done()
		data = 999999              // Menulis data
		ready.Store(true)           // Happens-before fence via atomic
	}()

	// Consumer
	go func() {
		defer wg.Done()
		for !ready.Load() {
			runtime.Gosched() // Cooperatively yield execution
		}
		// Dijamin secara spesifikasi memori: data bernilai 999999
		fmt.Printf("Consumer read data safely: %d\n", data)
	}()

	wg.Wait()
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Instruksi Kompilasi Analisis:
Jalankan perintah berikut untuk melihat hasil analisis statis kompilator:
```bash
go build -gcflags="-m -m" main.go
```

### Breakdown Kode:

1. **Baris 20 (`createOnStack`):**
   - Kompilator mendeteksi `d` dideklarasikan secara lokal dan langsung dievaluasi nilainya (`d.ID`). Variabel `d` tidak pernah diekspos ke luar batasan *stack frame*.
   - **Hasil Output Compiler**: `d does not escape`. Objek dialokasikan di stack dan otomatis musnah saat *function pointer register* bergeser kembali ke *caller*.

2. **Baris 27 (`createOnHeap`):**
   - `return &d`: Alamat memori lokal dikembalikan ke fungsi pemanggil. Jika variabel ini tetap berada di stack, data tersebut akan tertimpa (*corrupted*) saat fungsi selesai dieksekusi.
   - **Hasil Output Compiler**: `&d escapes to heap`, `moved to heap: d`. Kompilator memindahkan instruksi alokasi menjadi `runtime.newobject`.

3. **Baris 32 (`recursiveGrow`):**
   - `var buffer [1024]byte`: Setiap kedalaman rekursi membutuhkan alokasi frame sebesar minimal 1 KB.
   - Pada kedalaman $10$, akumulasi kebutuhan memori stack adalah $\approx 10 \times 1\text{ KB} = 10\text{ KB}$.
   - Ukuran awal stack goroutine adalah 2048 byte (2 KB). Saat mencapai kedalaman $\approx 2$, runtime mendeteksi *stack guard exhaustion*, memanggil `runtime.morestack`, lalu mengalokasikan stack baru (4 KB, lalu 8 KB, lalu 16 KB) dan memindahkan data frame secara mulus (*contiguous stack copy*).

4. **Baris 54-71 (Happens-Before via `atomic.Bool`):**
   - Baris 59: `data = 999999`. Ini adalah *plain non-atomic write*.
   - Baris 60: `ready.Store(true)`. Operasi atomik ini menciptakan relasi sinkronisasi implisit: seluruh operasi penulisan memori yang terjadi sebelum `Store` dijamin terlihat oleh goroutine lain yang membaca hasil `Store` tersebut melalui `Load()`.
   - Baris 66: `for !ready.Load()`. Begitu bernilai `true`, dijamin baris 70 tidak akan pernah membaca data *stale* (`0`), melainkan pasti membaca `999999`.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: *High-Frequency Financial Ingestion Engine*
- **Konteks**: Layanan microservice pemrosesan transaksi kripto memproses 120.000 transaksi JSON per detik (`req/sec`).
- **Gejala Masalah**:
  1. *CPU Utilization* mencapai 95%, namun pemrosesan logika bisnis hanya mengonsumsi 20% CPU. Sisa 75% habis di dalam fungsi `runtime.findrunnable`, `runtime.gcBgMarkWorker`, dan `runtime.mallocgc`.
  2. Latensi $P_{99.9}$ melesat hingga 850 milidetik secara periodik (setiap 3 detik), menyebabkan *client connection timeout*.
- **Akar Masalah (Root Cause Analysis)**:
  - Setiap request HTTP menginstansiasi *buffer payload* baru, melakukan *deserialization* ke dalam struct dinamis, lalu membungkus error ke dalam interface heap.
  - Alokasi masif objek berumur pendek (< 5 milidetik) membanjiri *heap allocator*, menyebabkan GC Pacer terpicu terus-menerus.
  - Karena memori bertambah sangat cepat, *Mark Worker* GC menyita kuota komputasi CPU aplikasi (*Mutator Assists* aktif), memperlambat eksekusi aplikasi secara dramatis.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah refaktor arsitektur dari *allocation-heavy* menjadi *zero-allocation engine* menggunakan `sync.Pool`, pengoptimalan *struct alignment*, dan *recycling patterns*.

```go
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"runtime"
	"sync"
	"time"
)

// Transaction adalah model data transaksi finansial.
// Perhatikan field alignment untuk menghindari memory padding alignment waste.
type Transaction struct {
	Timestamp int64   // 8 bytes (offset 0)
	Amount    float64 // 8 bytes (offset 8)
	ID        int64   // 8 bytes (offset 16)
	Valid     bool    // 1 byte  (offset 24)
	// Compiler menyisipkan 7 bytes padding di sini agar struct genap berukuran kelipatan 8
}

// TransactionProcessor mengelola ingestion pipeline dengan alokasi minimal.
type TransactionProcessor struct {
	// Pool untuk membungkus byte buffer guna eliminasi alokasi I/O
	bufPool sync.Pool
	// Pool untuk mendaur ulang struct Transaction
	txPool sync.Pool
}

func NewTransactionProcessor() *TransactionProcessor {
	return &TransactionProcessor{
		bufPool: sync.Pool{
			New: func() any {
				// Alokasikan buffer 2KB di awal agar tidak perlu resize saat parsing
				return bytes.NewBuffer(make([]byte, 0, 2048))
			},
		},
		txPool: sync.Pool{
			New: func() any {
				return new(Transaction)
			},
		},
	}
}

// ProcessPayload mengeksekusi parsing dan kalkulasi tanpa alokasi baru di heap mutator.
func (tp *TransactionProcessor) ProcessPayload(payload []byte) error {
	// 1. Ambil buffer dari pool
	buf := tp.bufPool.Get().(*bytes.Buffer)
	buf.Reset()
	defer tp.bufPool.Put(buf)

	buf.Write(payload)

	// 2. Ambil struct Transaction dari pool
	tx := tp.txPool.Get().(*Transaction)
	// Selalu inisialisasi ulang properti struct (sanitize state)
	tx.ID = 0
	tx.Amount = 0
	tx.Timestamp = 0
	tx.Valid = false
	defer tp.txPool.Put(tx)

	// 3. Gunakan streaming decoder berbasis buffer yang didaur ulang
	decoder := json.NewDecoder(buf)
	if err := decoder.Decode(tx); err != nil {
		return err
	}

	// 4. Logika Bisnis (Simulasi verifikasi instan tanpa escape)
	if tx.Amount <= 0 {
		return fmt.Errorf("invalid transaction amount")
	}
	tx.Valid = true

	return nil
}

func main() {
	processor := NewTransactionProcessor()
	sampleJSON := []byte(`{"ID": 987654321, "Amount": 1250.75, "Timestamp": 1700000000}`)

	// Jalankan benchmark sederhana dan pembuktian statistik alokasi
	var memStatsBefore, memStatsAfter runtime.MemStats
	runtime.GC()
	runtime.ReadMemStats(&memStatsBefore)

	startTime := time.Now()
	iterations := 1_000_000

	for i := 0; i < iterations; i++ {
		if err := processor.ProcessPayload(sampleJSON); err != nil {
			panic(err)
		}
	}

	elapsed := time.Since(startTime)
	runtime.ReadMemStats(&memStatsAfter)

	fmt.Println("=== HASIL BENCHMARK ZERO-ALLOC INGESTION ===")
	fmt.Printf("Total Operasi        : %d ops\n", iterations)
	fmt.Printf("Waktu Eksekusi       : %v\n", elapsed)
	fmt.Printf("Throughput           : %.2f ops/sec\n", float64(iterations)/elapsed.Seconds())
	fmt.Printf("Alokasi Total Heap   : %d Bytes\n", memStatsAfter.TotalAlloc-memStatsBefore.TotalAlloc)
	fmt.Printf("Frekuensi GC Siklus  : %d siklus\n", memStatsAfter.NumGC-memStatsBefore.NumGC)
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Stack Allocation vs Heap Allocation

| Dimensi Parameter | Alokasi Memori Stack | Alokasi Memori Heap |
| :--- | :--- | :--- |
| **Kecepatan Alokasi** | Sangat Cepat ($O(1)$) — Hanya modifikasi register SP (*Stack Pointer*). | Relatif Lebih Lambat ($O(1)$ amortized di `mcache`, hingga $O(N)$ jika lock `mheap`). |
| **Biaya Deallokasi** | Gratis ($0$ overhead CPU) — Terhapus saat stack frame *return*. | Mahal — Melibatkan siklus CPU pelacakan Tri-color GC & Sweep. |
| **Batas Ukuran** | Dinamis, tumbuh mulai 2 KB, dibatasi maksimal (umumnya 1 GB di 64-bit OS). | Dibatasi oleh kapasitas total RAM fisik + Virtual Memory OS. |
| **Lokasi Akses Cache** | Sangat ramah CPU L1/L2 Cache (*Hot cache locality*). | Berpotensi terjadi fragmentasi dan *Cache Miss* lebih tinggi. |

### 2. Tuning Garbage Collector: `GOGC` vs `GOMEMLIMIT`

| Strategi Tuning | Mekanisme Inti | Kelebihan | Risiko / Kekurangan |
| :--- | :--- | :--- | :--- |
| **Default (`GOGC=100`)** | GC terpicu saat heap tumbuh 100% dari ukuran heap hidup (*live heap*) terakhir. | Stabil untuk beban kerja komputasi standar dengan fluktuasi stabil. | Tidak peduli sisa memori fisik mesin; rentan OOM (*Out of Memory*) pada beban memori tinggi. |
| **Agresif Rendah (`GOGC=20-50`)** | GC berjalan lebih sering saat heap hanya tumbuh sedikit. | Jejak penggunaan RAM sangat kecil (*small footprint*). | **CPU Thrashing**: Mutator asistensi GC menyita CPU, latensi aplikasi memburuk drastis. |
| **`GOMEMLIMIT` (Go 1.19+)** | Menetapkan batas tegas penggunaan memori total runtime (misal: `GOMEMLIMIT=4GiB`). | Menghilangkan insiden *OOM Killer* di dalam container/Kubernetes Pods. | Jika live-set konstan mendekati limit, GC akan masuk kondisi panik (*thrashing cycle*). |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Memory Leak Akibat Sub-slicing pada Array/Slice Masif
Membuat sub-slice dari slice berukuran raksasa tetap menahan referensi array dasar (*backing array*) secara utuh di heap, meskipun hanya membutuhkan sebagian kecil elemen.

```go
// PITFALL: Backing array 10MB tertahan di heap selamanya
func getSubData() []byte {
    largeBuffer := make([]byte, 10*1024*1024) // 10 MB
    return largeBuffer[:4] // Mengembalikan 4 byte, tapi 10MB tidak bisa di-GC!
}

// MITIGASI: Salin data yang dibutuhkan ke slice independen
func getSubDataSafe() []byte {
    largeBuffer := make([]byte, 10*1024*1024)
    result := make([]byte, 4)
    copy(result, largeBuffer[:4])
    return result // largeBuffer aman dikoleksi oleh GC
}
```

### 2. Bahaya Penggunaan `runtime.SetFinalizer`
Penggunaan `runtime.SetFinalizer` dapat menimbulkan anomali siklus hidup objek:
- Menunda pembersihan objek minimal **2 siklus GC** (siklus 1: jalankan finalizer, siklus 2: deallokasi memori).
- Jika terdapat *circular reference* antar dua objek yang sama-sama memiliki finalizer, **kedua objek tersebut tidak akan pernah dibersihkan dari heap**, menciptakan *memory leak* permanen.

### 3. Goroutine Leak yang Menahan Memori
Objek apa pun yang dialokasikan di dalam goroutine yang mengalami *hang* (misal: membaca unbuffered channel tanpa ada pengirim) akan dianggap sebagai *reachable roots*. Seluruh rantai pointer objek tersebut tidak akan pernah disentuh oleh GC.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Interface Boxing pada Hot-Path
Memasukkan tipe primitif atau struct kecil ke dalam argumen bertipe `any` (`interface{}`) di loop throughput tinggi.

```go
// BURUK: Menyebabkan konversi runtime.convT64 (alokasi ke heap)
func BenchmarkBad(b *testing.B) {
    for i := 0; i < b.N; i++ {
        logInterface(i) // i (int) lolos ke heap karena parameter interface{}
    }
}
func logInterface(val any) {}

// BAIK: Gunakan concrete type atau generics untuk menahan alokasi di stack
func BenchmarkGood(b *testing.B) {
    for i := 0; i < b.N; i++ {
        logConcrete(i)
    }
}
func logConcrete(val int) {}
```

### Kesalahan 2: Ketidakteraturan Penataan Struct Field (Memory Padding Waste)
Kompilator mengurutkan alamat struct field berdasarkan batas alignment CPU (umumnya 8 byte untuk arsitektur 64-bit).

```go
// BURUK: Total ukuran 24 bytes (11 bytes terbuang percuma untuk padding)
type InefficientStruct struct {
    FlagA bool   // 1 byte
    // 7 bytes padding
    Data  int64  // 8 bytes
    FlagB bool   // 1 byte
    // 7 bytes padding
}

// BAIK: Total ukuran 16 bytes (Penghematan 33% memori per instans)
type OptimizedStruct struct {
    Data  int64  // 8 bytes
    FlagA bool   // 1 byte
    FlagB bool   // 1 byte
    // 6 bytes padding
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Konfigurasi Soft Limit di Lingkungan Kubernetes**:
   Selalu setel `GOMEMLIMIT` sebesar **80-85% dari batas Hard Memory Limit cgroup/Pod container**. Ini memberikan ruang bernapas 15-20% bagi Go runtime untuk menangani *execution overhead*, I/O buffer kernel, dan kompilasi profiler tanpa terkena ancaman OOM Killer SIGKILL.
2. **Reuse Buffer, Don't Reallocate**:
   Gunakan tipe data byte slicing yang dapat diperluas kembali tanpa membuang backing array (`slice = slice[:0]`).
3. **Analisis Escape Analysis dalam CI/CD**:
   Jalankan pengujian escape analysis statis pada hot-path modul menggunakan flag `-gcflags="-m"` dan pastikan alokasi kritis tidak mengalami regresi menjadi lolos ke heap.
4. **Waspadai Pola Pemakaian `sync.Pool`**:
   Jangan menyimpan pointer ke array yang ukurannya dapat membesar tanpa batas di dalam `sync.Pool`. Jika satu goroutine menaruh buffer 500 MB ke dalam pool, buffer tersebut akan terus bertahan di memori hingga terhapus oleh siklus GC periodik.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Evaluasi Performa: Pendekatan Berbasis Profiling Alokasi

Jalankan benchmark terukur untuk membuktikan efisiensi alokasi:

```bash
# Menjalankan unit benchmark dengan pelaporan alokasi memori
go test -bench=. -benchmem -memprofile=mem.pprof

# Menganalisis diagram interaktif heap
go tool pprof -http=:8080 mem.pprof
```

Contoh keluaran benchmark teroptimasi:
```text
BenchmarkProcessOld-8     200000     6120 ns/op    4210 B/op     48 allocs/op
BenchmarkProcessNew-8    2500000      480 ns/op       0 B/op      0 allocs/op
```
*Hasil optimasi: 0 B/op dan 0 allocs/op menandakan sistem beroperasi murni di stack dan memori yang didaur ulang.*

---

# SEKSI 16 — KEAMANAN & HARDENING

### Eksploitasi Titik Lemah Memory Safety via `unsafe.Pointer`
Go menjamin keamanan memori (*memory safety*) kecuali pengembang secara eksplisit menggunakan paket `unsafe`.

```go
package main

import (
	"fmt"
	"unsafe"
)

func main() {
	// Kerentanan Tipe: Mengabaikan type system Go
	var secretToken int64 = 0x5A5A5A5A
	
	// Konversi pointer tidak aman
	ptr := unsafe.Pointer(&secretToken)
	bytePtr := (*[8]byte)(ptr)

	// Pemaparan layout byte fisik di memori
	fmt.Printf("Memory bytes dump: %x\n", *bytePtr)

	// Bahaya: Mengarahkan pointer ke alamat liar (Wild Pointer)
	// Jika GC memindahkan stack atau mspan dilepas, pointer ini memicu Segmentation Fault
	// atau pembacaan rahasia memori proses lain (Information Disclosure).
	badPtr := uintptr(ptr) + 16 // Menghitung alamat pointer menggunakan integer
	danglingPtr := (*int64)(unsafe.Pointer(badPtr))
	
	_ = danglingPtr // Potensi Crash / Memory Leak / Arbitrary Read
}
```

### Hardening Guidelines:
1. **Larang Penggunaan `uintptr` sebagai Penampung Sementara**:
   Jangan pernah menyimpan `uintptr` ke variabel lokal dengan ekspektasi objek yang ditunjuk tidak akan digeser oleh GC. Garbage Collector **tidak memperlakukan `uintptr` sebagai pointer**. Objek dapat dibebaskan seketika, menyebabkan bug *use-after-free*.
2. **Sanitisasi Memori Rahasia (Zeroization)**:
   Objek yang menampung *Private Key*, token, atau sandi harus ditimpa dengan nilai nol (*zeroing bytes*) segera setelah digunakan:
   ```go
   func wipeSlice(buf []byte) {
       for i := range buf {
           buf[i] = 0
       }
   }
   ```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Diagnostik Runtime via `GODEBUG=gctrace=1`
Jalankan binary Go dengan environment variable:
```bash
GODEBUG=gctrace=1 ./my-service
```
Format keluaran GC Trace:
```text
gc 1 @0.038s 2%: 0.026+1.1+0.015 ms clock, 0.21+0.25/0.85/1.5+0.12 ms cpu, 4->4->2 MB, 5 MB goal, 0 MB stacks, 8 P
```
**Anatomi Output:**
- `gc 1`: Siklus GC pertama sejak program dimulai.
- `@0.038s`: Waktu program berjalan saat siklus ini terjadi (38 milidetik).
- `2%`: Persentase total waktu CPU yang dihabiskan oleh GC sejak program aktif.
- `0.026+1.1+0.015 ms clock`: Waktu riil fase GC: STW Sweep Term + Concurrent Mark + STW Mark Term.
- `4->4->2 MB`: Ukuran heap: Sebelum GC -> Saat Mark Selesai -> Objek Hidup Pasca Sweep.
- `8 P`: Jumlah logical processor yang aktif.

### 2. Observabilitas Programatik Menggunakan `runtime/metrics`
Gunakan API modern `runtime/metrics` yang jauh lebih efisien dibanding `runtime.ReadMemStats` (yang memicu penghentian singkat mutator):

```go
package main

import (
	"fmt"
	"runtime/metrics"
)

func PrintGCMetrics() {
	const (
		gcCyclesMetric = "/gc/cycles/total:gc-cycles"
		heapLiveMetric = "/memory/classes/heap/objects:bytes"
	)

	samples := []metrics.Sample{
		{Name: gcCyclesMetric},
		{Name: heapLiveMetric},
	}

	metrics.Read(samples)

	fmt.Printf("Total GC Selesai: %d\n", samples[0].Value.Uint64())
	fmt.Printf("Ukuran Heap Aktif : %d Bytes\n", samples[1].Value.Uint64())
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```text
========================================================================================
                      GO MEMORY & GC QUICK REFERENCE CHEAT SHEET
========================================================================================
KOMPONEN RUNTIME:
- mcache   : Cache memori per-P (Logical Thread). Bebas lock, zero concurrency contention.
- mcentral : Koleksi mspan global terbagi berdasarkan 67 size classes. Butuh lock per-class.
- mheap    : Alokator tingkat teratas. Mengelola virtual memory chunk (64MB) dari kernel OS.
- mspan    : Unit struktur blok memori berukuran n-page (1 page = 8KB).

SIKLUS GC (CONCURRENT TRI-COLOR MARK-SWEEP):
1. Sweep Termination (STW) -> Siapkan phase mark, nyalakan Write Barrier.
2. Concurrent Mark         -> Tandai objek hidup (Hitam/Abu-abu). Memakan ~25% kapasitas CPU.
3. Mark Termination (STW)  -> Matikan Write Barrier, finalisasi sisa antrean mark.
4. Concurrent Sweep        -> Bebaskan span blok putih ke allocator secara asinkron.

VARIABEL LINGKUNGAN PENTING:
- GOGC=off                 -> Matikan GC total (Hati-hati: Heap tumbuh tak terbatas).
- GOGC=100                 -> Default. Memicu GC saat heap tumbuh 100% dari live heap.
- GOMEMLIMIT=X(B/KiB/MiB)  -> Mengatur batasan tegas memori agar tidak dibunuh OOM Killer.
- GODEBUG=gctrace=1        -> Mencetak ringkasan diagnostik siklus GC ke stderr.
- GODEBUG=clobberfree=1    -> Menimpa memori yang dibebaskan dengan nilai sampah (Debugging).

ATURAN ESCAPE ANALYSIS:
- Return pointer lokal dari fungsi           ==> ESCAPE KE HEAP
- Masukkan nilai ke parameter interface{}    ==> SERING ESCAPE KE HEAP
- Ukuran slice dinamis / terlalu besar (>64K)==> ESCAPE KE HEAP
========================================================================================
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Berapa ukuran default memori stack awal untuk goroutine yang baru diinstansiasi di Go versi modern?**
   - A. 1 Megabyte
   - B. 2 Kilobyte
   - C. 8 Kilobyte
   - D. 4096 Byte
   *Kunci Jawaban: B. Alokasi awal stack Go adalah 2 KB (berbeda dari thread sistem operasi yang berukuran 1-8 MB).*

2. **Komponen alokator Go manakah yang menyediakan alokasi memori berukuran kecil tanpa memerlukan penguncian mutex sama sekali?**
   - A. `mheap`
   - B. `mcentral`
   - C. `mcache`
   - D. `arena`
   *Kunci Jawaban: C. `mcache` terikat langsung pada setiap prosesor logis `P`, sehingga pengalokasian berlangsung secara lokal tanpa data contention.*

3. **Kondisi manakah yang secara spesifikasi *Go Memory Model* TIDAK menjamin adanya relasi *happens-before*?**
   - A. Pembacaan variabel dari goroutine A yang ditulis oleh goroutine B tanpa sinkronisasi channel atau mutex.
   - B. Eksekusi fungsi pembentukan goroutine `go f()` terhadap instruksi awal fungsi `f()`.
   - C. Pengiriman data ke unbuffered channel terhadap selesainya penerimaan data di channel tersebut.
   - D. Pemanggilan `mu.Unlock()` terhadap pemanggilan `mu.Lock()` berikutnya pada instans mutex yang sama.
   *Kunci Jawaban: A. Tanpa sinkronisasi eksplisit, dua goroutine yang membaca/menulis memori yang sama berada dalam kondisi concurrent (berpotensi data race).*

4. **Warna apakah dalam algoritma Tri-color GC yang merepresentasikan objek yang telah diverifikasi hidup beserta seluruh referensi anaknya?**
   - A. Putih
   - B. Abu-abu
   - C. Hitam
   - D. Merah
   *Kunci Jawaban: C. Objek Hitam adalah objek yang dipastikan hidup dan tidak memiliki referensi tak terselesaikan ke objek putih.*

5. **Apa fungsi utama dari mekanisme *Write Barrier* pada Garbage Collector Go?**
   - A. Mencegah mutator memodifikasi data yang sedang dibaca oleh goroutine lain.
   - B. Mencegah objek putih terputus dari rantai penandaan saat mutator memanipulasi pointer di tengah fase Concurrent Mark.
   - C. Memaksa seluruh operasi tulis langsung masuk ke penyimpanan NVMe/Disk.
   - D. Mengunci sistem secara total hingga proses sweep selesai.
   *Kunci Jawaban: B. Write barrier mengintersepsi manipulasi pointer saat mark berjalan paralel agar objek yang masih digunakan tidak terhapus.*

---

### Soal Tingkat Lanjut (Intermediate)

6. **Mengapa konversi tipe konkret menjadi `interface{}` (boxing) di dalam fungsi yang dipanggil jutaan kali dapat memperburuk performa Garbage Collector?**
   - A. Interface memakan memori tetap sebesar 1 MB.
   - B. Kompilator sering tidak dapat membuktikan kepemilikan nilai di stack frame, memaksa alokasi wrapper ke heap dan membebani GC pacer.
   - C. Kompilator Go akan menghentikan seluruh goroutine setiap kali interface diinisialisasi.
   - D. Interface mengubah tipe data internal menjadi pointer C-style yang membingungkan OS kernel.
   *Kunci Jawaban: B. Indirection via interface sering menggagalkan escape analysis statis kompilator, memicu heap allocation dan menambah jumlah objek yang harus diinspeksi GC.*

7. **Perhatikan skenario: Aplikasi memiliki batas memori container 1 GB. GC disetel ke default (`GOGC=100`). Jika heap hidup bernilai 600 MB, apa yang akan terjadi saat aplikasi menerima burst alokasi data?**
   - A. GC akan langsung membersihkan memori tanpa jeda.
   - B. Runtime memicu GC saat heap mencapai 1200 MB, sehingga aplikasi dibunuh seketika oleh Kernel Linux (OOM Killer) sebelum GC sempat terpicu.
   - C. Heap Go akan otomatis dibatasi di 600 MB oleh kompilator.
   - D. Aplikasi melambat tetapi tidak akan pernah crash.
   *Kunci Jawaban: B. Dengan `GOGC=100`, GC baru akan terpicu di level target $600\text{ MB} + 100\% = 1200\text{ MB}$, yang melampaui batas batas cgroup 1 GB.*

8. **Bagaimana mekanisme *contiguous stack* mengatasi keterbatasan ruang stack lama ketika goroutine membutuhkan memori stack yang lebih besar?**
   - A. Runtime membuat linked-list stack chunk baru dan menghubungkannya dengan chunk lama (Split stack).
   - B. Runtime memindahkan goroutine ke thread OS baru dengan ukuran stack 8 MB.
   - C. Runtime mengalokasikan blok memori kontinu baru berukuran 2x lipat, menyalin stack lama, memperbarui referensi pointer internal, lalu melepaskan stack lama.
   - D. Runtime mengonversi variabel stack menjadi alokasi heap secara otomatis tanpa memindahkan frame.
   *Kunci Jawaban: C. Contiguous stack mengatasi masalah "hot split" dengan mengalokasikan blok kontinu ganda dan memindahkan seluruh frame secara rapi.*

9. **Apa perbedaan fungsional antara `GOMEMLIMIT` dan `GOGC` dalam mengendalikan frekuensi GC?**
   - A. `GOMEMLIMIT` menonaktifkan mark worker, sedangkan `GOGC` mengaktifkannya.
   - B. `GOGC` menetapkan rasio pertumbuhan relatif terhadap live heap, sedangkan `GOMEMLIMIT` menetapkan batas absolut yang memodulasi target pacer secara otomatis jika mendekati batas.
   - C. `GOMEMLIMIT` hanya bekerja di sistem operasi Linux, sedangkan `GOGC` bekerja di semua OS.
   - D. `GOMEMLIMIT` menghapus memori seketika menggunakan syscall free().
   *Kunci Jawaban: B. GOGC bersifat persentase relatif; GOMEMLIMIT menetapkan batas tegas total penggunaan memori yang secara adaptif memicu GC lebih awal jika batas tercapai.*

10. **Kapan alokasi memori dikategorikan sebagai *Tiny Allocation* oleh internal Go Allocator, dan bagaimana ia disimpan?**
    - A. Ukuran $< 16$ byte tanpa elemen pointer, digabungkan ke dalam satu blok memori 16-byte di `mcache`.
    - B. Ukuran $< 1$ Kilobyte, langsung disimpan di register CPU RAX.
    - C. Ukuran $< 32$ Kilobyte, disimpan langsung di `mheap`.
    - D. Seluruh tipe data `bool` dan `byte` yang dialokasikan di dalam channel.
    *Kunci Jawaban: A. Tiny allocator memadukan alokasi kecil bebas pointer (<16 bytes) ke dalam satu slot 16-byte guna meminimalkan fragmentasi memori internal.*

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Praktikum: *Building an Allocation-Free Circular Ring Buffer with Built-in GC Diagnostics*

### Deskripsi Masalah:
Rancang dan bangun sistem antrean pesan berkecepatan tinggi berbasis *Ring Buffer* memori sirkular dalam Go yang mampu memproses pertukaran data antar ribuan goroutine dengan kriteria performa ekstrem: **NOL alokasi memori pada fase produksi (0 B/op, 0 allocs/op)**.

### Spesifikasi Teknis:
1. **Zero-Allocation Core**:
   - Struktur antrean harus mengalokasikan seluruh slot memori di muka (*pre-allocated slice*) saat instansiasi awal.
   - Selama proses *enqueue* dan *dequeue*, tidak boleh ada pemanggilan ke `runtime.newobject`, pembungkusan interface boxing, maupun penambahan ukuran slice (`append`).
2. **Thread-Safe & Lock-Free / Low-Contention**:
   - Gunakan operasi atomik (`sync/atomic`) untuk manipulasi indeks *head* dan *tail*.
3. **Internal Diagnostic Monitor**:
   - Buat goroutine terpisah yang memantau performa menggunakan `runtime/metrics` setiap interval 1 detik.
   - Tampilkan informasi: Jumlah alokasi heap baru, durasi jeda GC (*pause time*), dan utilisasi memori aktual.

### Target Pengujian:
Jalankan pengujian benchmarking berikut dan buktikan target performa tercapai:
```bash
go test -bench=BenchmarkRingBuffer -benchmem
```
*Syarat Kelulusan Proyek: Laporan benchmark harus mencantumkan angka mutlak `0 B/op` dan `0 allocs/op` pada 5.000.000 iterasi transaksi konkurensi penuh.*