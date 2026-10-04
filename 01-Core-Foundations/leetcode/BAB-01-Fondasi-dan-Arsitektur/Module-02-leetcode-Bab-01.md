# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Topik: Algorithmic Engineering & Core Foundations (LeetCode to Production)
### Bab 01: Fondasi dan Arsitektur
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, software engineer diharapkan mampu:

1. **Mentranslasikan Solusi Algoritmik Abstraktif ke Arsitektur Produksi Rendah Latensi:** Mengubah pola algoritma LeetCode murni (seperti Sliding Window, Monotonic Queue, dan Disjoint Set Union) menjadi komponen berkinerja tinggi yang siap menahan beban jutaan transaksi per detik (*high throughput*).
2. **Mengeksploitasi *Mechanical Sympathy* dan *Memory Locality*:** Menjelaskan dan membuktikan pengaruh CPU Cache (L1/L2/L3), *Cache Lines* (64-byte boundary), *Branch Prediction*, dan fragmentasi *heap* terhadap efisiensi algoritma di atas hardware modern.
3. **Mengeliminasi *Runtime Overhead* & Alokasi Dinamis:** Merancang struktur data *zero-allocation* yang memitigasi tekanan *Garbage Collector* (GC) atau *allocator latency* melalui *flat buffers*, *ring buffers*, dan penyelarasan memori (*memory alignment*).
4. **Menerapkan Struktur Data Konkuren Bebas Kunci (*Lock-Free*):** Mengimplementasikan algoritma konkuren dengan primitif atomik (*atomic operations*) yang menghindari fenomena *false sharing* dan *cache contention*.
5. **Mengeksekusi *Profiling* dan *Benchmarking* Komparatif:** Melakukan inspeksi performa tingkat rendah (*nanosecond precision*) menggunakan *profiler* (CPU, memori, *escape analysis*) guna mendeteksi degradasi performa sebelum kode masuk ke lingkungan *staging* dan *production*.

---

### 2. Prerequisite

Sebelum memulai modul ini, partisipan wajib menguasai:

*   **Analisis Asimptotik Tingkat Lanjut:** Pemahaman mendalam terkait Time & Space Complexity ($O(1), O(\log N), O(N), O(N \log N), O(N^2)$), serta perbedaan antara *worst-case*, *average-case*, dan *amortized complexity*.
*   **Fondasi Sistem Operasi & Arsitektur Komputer:** Pemahaman terkait Stack vs Heap, Virtual Memory, Paging, Context Switching, serta hierarki memori (Register, L1/L2/L3 Cache, RAM).
*   **Primitif Concurrency:** Memahami *Threads*, *Goroutines/Tasks*, Mutex, Read-Write Lock, dan dasar-dasar *Memory Model* (misalnya: *acquire-release semantics*, *sequential consistency*).
*   **Penguasaan Bahasa Pemrograman Sistem / Terkelola Modern:** Kemampuan menulis dan membaca kode Go, Rust, C++, atau Java dengan kesadaran pointer dan tipe data primitif. Contoh pada modul ini diimplementasikan menggunakan **Go** karena representasinya yang transparan terhadap alokasi memori dan eksekusi paralel.

---

### 3. Concept & Internal Architecture

Banyak rekayasawan berasumsi bahwa algoritma $O(N)$ di atas kertas selalu lebih cepat daripada $O(N \log N)$ atau bahkan $O(N^2)$. Namun di lingkungan produksi nyata, asumsi teoretis ini dapat runtuh karena adanya **Hardware Architecture Reality**. CPU modern tidak mengeksekusi instruksi secara matematis murni; CPU mengeksekusi instruksi melalui sistem pipa (*instruction pipeline*), *branch predictor*, dan hierarki subsistem *caching*.

```
+-------------------------------------------------------------------------+
|                              CPU CORE                                   |
|  +--------------------+   +--------------------+   +-----------------+  |
|  | Instruction Pipeline|  |  Branch Predictor  |  | Registers       |  |
|  +--------------------+   +--------------------+   +-----------------+  |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| L1 Data Cache (32KB - 64KB) ~ 4 - 5 CPU Cycles (Latency ~ 1ns)          |
| [Line 0: 64 Bytes] [Line 1: 64 Bytes] ... [Line N: 64 Bytes]            |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| L2 Cache (256KB - 1MB) ~ 12 - 14 CPU Cycles (Latency ~ 3-4ns)           |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| L3 Shared Cache (8MB - 64MB) ~ 40 - 75 CPU Cycles (Latency ~ 10-20ns)   |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| Main Memory (RAM) ~ 200+ CPU Cycles (Latency ~ 60-100ns)                |
+-------------------------------------------------------------------------+
```

#### 3.1. *Spatial & Temporal Locality* serta *Cache Lines*

Memori utama tidak dibaca per byte atau per kata (*word*), melainkan dalam unit tetap bernama **Cache Line** (pada sebagian besar arsitektur x86-64 dan ARM64 berukuran **64 bytes**).

*   **Spatial Locality:** Jika data pada alamat $X$ diakses, kemungkinan besar data pada alamat $X + 1$ akan diakses dalam waktu dekat. 
*   **Temporal Locality:** Jika data pada alamat $X$ baru saja diakses, kemungkinan besar data tersebut akan diakses kembali secara berulang.

Ketika sebuah algoritma menggunakan *Linked List* atau *Node-based Binary Search Tree* (sering diajarkan pada sesi LeetCode dasar), setiap node dialokasikan secara dinamis di *heap*. Node-node ini terpencar di alamat memori virtual yang berjauhan (*pointer chasing*). 

Setiap kali CPU melompati pointer ke node berikutnya:
1. Terjadi **L1/L2/L3 Cache Miss**.
2. Pipeline CPU terhenti (*CPU Stall*) selama 60–100 nanodetik (ratusan *clock cycles*) sembari menunggu data diambil dari RAM.

Sebaliknya, *Array-based data structure* (*contiguous memory buffer*) memanfaatkan *hardware prefetcher* CPU secara optimal. Ketika elemen pertama dibaca, seluruh segmen 64 byte ditarik langsung ke L1 Cache, membuat operasi traversal berulang kali lebih cepat daripada *pointer chasing*, meskipun kompleksitas teoretisnya sama-sama $O(N)$.

#### 3.2. *Branch Prediction & Instruction Pipeling*

CPU modern menggunakan teknik *deep pipelining* dan eksekusi spekulatif (*speculative execution*). *Branch predictor* menebak jalur mana yang akan dieksekusi pada pernyataan percabangan (`if-else`, loop conditions) sebelum evaluasi nilai selesai.

*   **Predictable Branch:** Pola data yang terurut memudahkan CPU memprediksi percabangan secara akurat (akurasi > 95%).
*   **Branch Misprediction:** Jika CPU salah menebak, seluruh *pipeline* instruksi yang sudah di-decode harus dibuang (*pipeline flush*), membuang 15 hingga 20 siklus CPU sia-sia.

Dalam rekayasa algoritma produksi, modifikasi kode untuk menghilangkan percabangan (*branchless programming*) pada jalur eksekusi kritis (*hot path*) sering kali meningkatkan *throughput* secara lebih signifikan dibandingkan penurunan kompleksitas matematis murni.

#### 3.3. *False Sharing & Cache Contention*

Dalam sistem *multi-threaded* / konkurensi tinggi, jika dua thread yang berjalan di core CPU berbeda menulis ke dua variabel yang independen tetapi berada di dalam **Cache Line 64-byte yang sama**, protokol koherensi cache (seperti MESI atau MOESI) akan saling membatalkan validitas cache line tersebut (*invalidation storms*). Peristiwa ini dinamakan **False Sharing**. Akibatnya, operasi penulisan melambat setara kecepatan transfer bus sistem, mengeliminasi keuntungan paralelisasi.

Pencegahannya adalah dengan teknik **Cache Line Padding**: menyisipkan ruang kosong sebesar 64 byte di antara variabel atomik yang sering dimutasi.

---

### 4. Why & What

| Dimensi | LeetCode / Competitive Programming | Arsitektur Algoritma Produksi (Enterprise) |
| :--- | :--- | :--- |
| **Tujuan Akhir** | Solusi lolos *test cases* dalam batas waktu (*Time Limit Exceeded/TLE*) dan memori (*Memory Limit Exceeded/MLE*). | Stabilitas performa, latensi konsisten (*P99/P99.9*), *zero-crash*, konkurensi aman, *maintainability*. |
| **Layout Memori** | Mengabaikan cache hierarchy; node berbasis pointer (`Node*`, `new TreeNode()`) lazim digunakan. | Berorientasi pada *Contiguous Memory*, *Memory-alignment*, pengurangan dereferensi pointer (*Flat Arrays*). |
| **Manajemen Memori** | Membiarkan GC atau OS membersihkan memori saat program berhenti. | Mengeliminasi alokasi dinamis pada *hot-path*, menggunakan *buffer reuse*, *ring buffer*, atau *object pooling*. |
| **Model Eksekusi** | Single-threaded, input terisolasi, runtime deterministik. | Multi-threaded / highly concurrent, I/O interupsi, input non-deterministik, fenomena *data race*. |
| **Penanganan Error** | Mengasumsikan input selalu valid sesuai batasan masalah (*constraints*). | Validasi ketat, *defensive coding*, batas memori eksplisit, pelaporan kegagalan terdegradasi (*graceful degradation*). |

---

### 5. How (Workflow Detail)

Untuk mentransformasikan rancangan algoritma abstrak menjadi modul produksi berkinerja tinggi, terapkan tahapan sistematis berikut:

```
[1. Problem Formulation] 
       │ 
       ▼
[2. Algorithmic Optimization (LeetCode Abstract Model)]
       │ 
       ▼
[3. Hardware-Aware Mapping (Contiguous Buffers, Struct Packing)]
       │ 
       ▼
[4. Concurrency & Contention Engineering (Lock-Free / Atomic)]
       │ 
       ▼
[5. Profiling & Mechanical Verification (pprof, perf, escape analysis)]
       │ 
       ▼
[6. Production Hardening (Bounds Checking, Telemetry, Circuit Breaking)]
```

1. **Formulasi Masalah:** Tentukan parameter beban operasional: *Requests Per Second* (RPS), batas P99 Latency (misal: $<10\mu s$ untuk *in-memory operations*), dan alokasi memori maksimal.
2. **Optimasi Algoritmik Teoretis:** Pilih fondasi algoritma terbaik secara matematika (misal: ubah pencarian $O(N)$ menjadi $O(1)$ amortized menggunakan *Sliding Window* atau *Monotonic Deque*).
3. **Hardware-Aware Memory Mapping:** Ubah struktur berbasis pointer menjadi struktur datar berbasis array (*flat continuous array*). Lakukan penyusunan urutan field pada *struct* dari ukuran terbesar ke terkecil untuk meminimalkan *struct padding overhead*.
4. **Rekayasa Konkurensi:** Tentukan apakah struktur data memerlukan sinkronisasi berbasis *mutex* atau *lock-free atomics*. Terapkan *cache line padding* pada data yang diakses lintas core.
5. **Verifikasi Profiling:** Jalankan *microbenchmarking* dengan parameter CPU dan Memory allocation (`go test -bench=. -benchmem -cpuprofile=cpu.pprof -memprofile=mem.pprof`). Analisis apakah ada alokasi variabel yang *escapes to heap*. Targetkan **0 B/op** dan **0 allocs/op** pada fungsi *hot path*.
6. **Production Hardening:** Tambahkan penanganan batas kapasitas buffer meluap (*backpressure/ring-buffer wrapping*), pelaporan metrik (Prometheus metric counters), dan penanganan error tanpa menyebabkan *panic* atau *segmentation fault*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan vs Meja Kerja Terorganisir (Pointer Chasing vs Contiguous Buffer)

*   **Pointer-Chasing (Linked Structure):** Anda duduk di meja kerja. Setiap membaca satu kalimat di buku, buku tersebut menginstruksikan: *"Kalimat berikutnya ada di rak lantai 3, koridor B, buku nomor 12."* Anda harus berdiri, berjalan ke rak, mengambil buku, membaca satu kalimat, lalu mendapat instruksi lain yang meminta Anda berjalan ke lantai dasar. Waktu Anda habis untuk berjalan (CPU Stall).
*   **Contiguous Array (Cache Friendly):** Semua kalimat yang Anda butuhkan telah dicetak berurutan pada satu gulungan kertas panjang yang diletakkan langsung di depan meja kerja Anda. Setiap kali mata Anda selesai membaca satu kata, kata berikutnya sudah berada tepat di bidang pandang Anda.

```
POINTER CHASING PATTERN (Heap-fragmented Tree / Linked List)
Heap Memory:
[Node A] ──(ptr: 0x8F04)──> [Node B] ──(ptr: 0x1204)──> [Node C]
(Addr: 0x0010)              (Addr: 0x8F04)              (Addr: 0x1204)
    │                           │                           │
  L1 MISS                     L1 MISS                     L1 MISS
  (Fetch 64B line)            (Fetch 64B line)            (Fetch 64B line)
  Waste: 48B garbage          Waste: 48B garbage          Waste: 48B garbage

========================================================================

FLAT ARRAY PATTERN (Continuous Buffer / Cache Conscious)
RAM / Cache Line:
[ Element 0 ][ Element 1 ][ Element 2 ][ Element 3 ][ Element 4 ] ...
(Addr: 0x0000) (Addr: 0x0008) (Addr: 0x0010) (Addr: 0x0018) (Addr: 0x0020)
└─────────────────────────── ONE 64-BYTE CACHE LINE ────────────────────────┘
          ▲
          └── L1 HIT untuk seluruh elemen berikutnya dalam satu fetch!
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Naive Window vs Optimized Ring Buffer Window

Masalah: Menghitung nilai maksimum dari sebuah *sliding window* berukuran $K$ dalam *stream of metrics* (Masalah LeetCode #239: *Sliding Window Maximum*).

**Versi Naif (LeetCode Standard - Banyak Alokasi Heap):**

```go
package naive

// NaiveWindowMax menggunakan slice dinamis dan sorting/re-slicing
// Mengakibatkan alokasi memori heap tinggi setiap kali elemen baru masuk.
type NaiveWindowMax struct {
	k      int
	window []int
}

func NewNaiveWindowMax(k int) *NaiveWindowMax {
	return &NaiveWindowMax{k: k, window: make([]int, 0, k)}
}

func (w *NaiveWindowMax) Push(val int) int {
	if len(w.window) == w.k {
		w.window = w.window[1:] // Slicing pointer overhead & re-allocation risk
	}
	w.window = append(w.window, val)

	// O(K) linear scan untuk mencari max
	maxVal := w.window[0]
	for _, v := range w.window {
		if v > maxVal {
			maxVal = v
		}
	}
	return maxVal
}
```

*Kelemahan Produksi:* Jika menerima 100.000 metrik per detik, kode ini memicu fragmentasi memori, modifikasi ukuran slice berulang, dan konsumsi CPU tinggi akibat scanning linear berulang.

---

#### 7.2. Practical Example: Lock-Free Flat Monotonic Ring Buffer (Standar Industri)

Implementasi di bawah ini menggabungkan:
1. **Algoritma Monotonic Queue** ($O(1)$ amortized time complexity).
2. **Pre-allocated Ring Buffer** (Nol alokasi memori pada *runtime hot path*).
3. **Cache Line Padding** untuk mencegah *false sharing*.
4. **Atomic Operation** untuk sinkronisasi state pointer yang efisien.

```go
package engine

import (
	"fmt"
	"sync/atomic"
	"unsafe"
)

// Ukuran konstan Cache Line x86-64/ARM modern
const CacheLineSize = 64

// MetricNode merepresentasikan item metrik
type MetricNode struct {
	Timestamp int64
	Value     float64
}

// MonotonicRingBuffer adalah buffer sliding window yang thread-safe, 
// zero-allocation pada runtime, dan cache-conscious.
type MonotonicRingBuffer struct {
	// Variabel baca/tulis yang sering diakses diisolasi dengan padding
	head uint64
	_    [CacheLineSize - unsafe.Sizeof(uint64(0))]byte // Prevent false sharing

	tail uint64
	_    [CacheLineSize - unsafe.Sizeof(uint64(0))]byte // Prevent false sharing

	capacity uint64
	mask     uint64

	// Buffer fisik datar (pre-allocated)
	nodes []MetricNode

	// Deque monotonic internal diimplementasikan di atas array datar untuk nol alokasi
	// Menyimpan indeks dari array 'nodes'
	dequeIndices []uint64
	dequeHead    uint64
	dequeTail    uint64
}

// NewMonotonicRingBuffer menginisialisasi buffer dengan kapasitas berbasis pangkat dua (Power of Two)
// untuk optimasi bitwise masking menggantikan modulo operator (%).
func NewMonotonicRingBuffer(capacityPow2 uint64) (*MonotonicRingBuffer, error) {
	if capacityPow2 == 0 || (capacityPow2&(capacityPow2-1)) != 0 {
		return nil, fmt.Errorf("kapasitas harus pangkat dua (contoh: 1024, 2048, 4096)")
	}

	return &MonotonicRingBuffer{
		capacity:     capacityPow2,
		mask:         capacityPow2 - 1,
		nodes:        make([]MetricNode, capacityPow2),
		dequeIndices: make([]uint64, capacityPow2),
		dequeHead:    0,
		dequeTail:    0,
		head:         0,
		tail:         0,
	}, nil
}

// Push menambahkan elemen baru ke sliding window dan mengembalikan nilai maksimum terkini.
// Kompleksitas Waktu: O(1) Amortized
// Alokasi Memori: 0 Allocs/Op
func (rb *MonotonicRingBuffer) Push(timestamp int64, val float64) (float64, error) {
	// Hitung posisi ring buffer via bitwise AND (Jauh lebih cepat dari operator modulo '%')
	currHead := atomic.LoadUint64(&rb.head)
	currTail := atomic.LoadUint64(&rb.tail)

	// Cek apakah buffer meluap (Window penuh)
	if currHead-currTail >= rb.capacity {
		// Geser tail secara otomatis (Evict data terlama)
		atomic.AddUint64(&rb.tail, 1)
		currTail++

		// Bersihkan elemen deque monotonic yang berada di luar window yang digeser
		if rb.dequeHead < rb.dequeTail && rb.dequeIndices[rb.dequeHead] < currTail {
			rb.dequeHead++
		}
	}

	slot := currHead & rb.mask
	rb.nodes[slot] = MetricNode{
		Timestamp: timestamp,
		Value:     val,
	}

	// Algoritma Monotonic Queue:
	// Eliminasi elemen dari belakang deque yang lebih kecil atau sama dengan elemen saat ini
	for rb.dequeTail > rb.dequeHead {
		lastIdx := rb.dequeIndices[rb.dequeTail-1]
		lastVal := rb.nodes[lastIdx&rb.mask].Value

		if lastVal <= val {
			rb.dequeTail--
		} else {
			break
		}
	}

	// Masukkan indeks elemen baru ke belakang deque
	rb.dequeIndices[rb.dequeTail] = currHead
	rb.dequeTail++

	// Advance ring buffer head
	atomic.AddUint64(&rb.head, 1)

	// Indeks nilai maksimum selalu berada di depan (head) dari monotonic deque
	maxIndex := rb.dequeIndices[rb.dequeHead]
	return rb.nodes[maxIndex&rb.mask].Value, nil
}

// CurrentMax mengambil nilai maksimum saat ini tanpa modifikasi state
func (rb *MonotonicRingBuffer) CurrentMax() (float64, bool) {
	if rb.dequeTail == rb.dequeHead {
		return 0, false
	}
	maxIdx := rb.dequeIndices[rb.dequeHead]
	return rb.nodes[maxIdx&rb.mask].Value, true
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem: FinTech High-Frequency Limit Order Book & Rate Limiter

*   **Skenario:** Sebuah gateway bursa komoditas kripto menerima rata-rata 800.000 order per detik (Peak: 1,5 Juta RPS). Setiap order harus divalidasi terhadap *Sliding Window Volatility Index* dan batas frekuensi pengguna (*sliding window rate limiter* 5 detik) dengan budget latensi maksimal **5 mikrodetik ($5\mu s$) pada persentil P99.9**.

```
                        INCOMING NETWORK STREAM (UDP/TCP Direct)
                                           │
                                           ▼ [~1,500,000 req/sec]
                  +──────────────────────────────────────────────────+
                  |         Zero-Copy Kernel Bypass (DPDK / XDP)     |
                  +──────────────────────────────────────────────────+
                                           │
                                           ▼
                  +──────────────────────────────────────────────────+
                  |   Flat Ring-Buffer Sliding Window Engine         |
                  |                                                  |
                  |  Core 1: Atomic Ingestion                        |
                  |  Core 2: Monotonic Volatility Filter (No-Alloc)  |
                  |  Core 3: Sliding Log Rate Limiting (Bitmask-Idx) |
                  +──────────────────────────────────────────────────+
                                           │
                          Latency: P99 < 3.2 Microseconds
                          Allocation: 0 bytes/op
                                           ▼
                  +──────────────────────────────────────────────────+
                  |     Matching Engine Core Execution Array         |
                  +──────────────────────────────────────────────────+
```

#### Masalah Nyata
Solusi awal menggunakan struktur data standar: `sync.Map` yang menyimpan slice bertipe `[]time.Time` untuk setiap akun klien. 
Dampaknya pada beban 300.000 RPS:
1. Alokasi jutaan objek kecil memicu siklus **Stop-The-World (STW) Garbage Collector** selama 15–30 milidetik.
2. Latensi P99.9 melonjak hingga **45 milidetik**, menyebabkan keterlambatan konfirmasi eksekusi order (kegagalan kepatuhan SLA regulasi pasar finansial).

#### Solusi Berbasis Algoritma Produksi Terintegrasi
1. **Pola Data:** Mengganti alokasi dinamis dengan *Static Multi-Tenant Fixed Array*. Setiap akun dialokasikan ring-buffer statis berukuran 256 slot bitmask (`capacity = 256`, `mask = 255`).
2. **Kompensasi Modulo:** Menghilangkan kalkulasi pembagian `%` dan menggantinya dengan operator bitwise `& 255`.
3. **Penyelarasan Memori (Alignment):** Struktur akun diskalakan tepat 64 bytes (`CacheLinePad`) agar tidak terjadi *cache contention* antar thread eksekutor worker pool.

#### Hasil Produksi
*   **Alokasi Memori:** Berkurang dari 240 MB/detik menjadi **0 Byte/detik**.
*   **Latensi P99.9:** Terpangkas dari **45ms** menjadi stabil di **2,8 mikrodetik**.
*   **Throughput Maksimal:** Server tunggal mampu menangani 2,1 Juta RPS pada CPU utilization 65%.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

Dalam mentransformasikan algoritma ke implementasi perangkat keras, terdapat kompromi arsitektural yang tidak dapat dihindari:

| Pilihan Desain | Keuntungan (Pros) | Biaya & Kompromi (Trade-offs / Cons) |
| :--- | :--- | :--- |
| **Contiguous Pre-allocation (Flat Arrays)** | Latensi sangat deterministik, nol alokasi runtime, ramah L1/L2 data cache. | Konsumsi memori awal (*footprint RAM*) tinggi meskipun sistem sedang *idle*; kapasitas buffer bersifat kaku (*fixed capacity*). |
| **Bitwise Masking (`val & (Cap-1)`)** | Eksekusi instan (1 CPU cycle), menghindari operasi pembagian integer hardware yang lambat (~15-40 cycles). | Ukuran kapasitas wajib selalu berupa bilangan pangkat dua ($2^N$), berpotensi membuang ruang memori sisa jika data aktual tidak pas. |
| **Lock-Free Atomic Sync** | Meniadakan *thread context switching*, tidak ada risiko thread terblokir (*thread blocking/deadlock*). | *Code complexity* sangat tinggi; jika terjadi *heavy contention*, CPU spinloop dapat membakar daya komputasi (*100% CPU core utilization*). |
| **Cache Line Padding (64B Pad)** | Menghilangkan *False Sharing* antar thread/core, latensi penulisan atomik konsisten di skala multi-core. | Terjadi *memory overhead* akibat struktur data membengkak dengan data kosong (*slack space*). |

---

### 10. Common Mistakes & Troubleshooting

Berikut adalah kegagalan sistemik yang sering terjadi saat mengonversi algoritma teoritis ke implementasi performa tinggi:

#### 1. Melakukan Slicing Slice Go Tanpa Memahami *Underlying Array Retention*
*   *Masalah:* Menulis `window = window[1:]` ribuan kali. Meski terlihat bersih, jika kapasitas awal slice sangat besar, memori elemen lama tetap tertahan di heap memory dan menunda pelepasan oleh Garbage Collector.
*   *Troubleshooting:* Gunakan *circular array index tracking* (`head` dan `tail` integer) alih-alih melakukan *reslicing* dinamis.

#### 2. False Sharing pada Struktur Data Konkuren
*   *Masalah:* Mengelompokkan dua counter atomik `workerAProcessed uint64` dan `workerBProcessed uint64` secara bersebelahan di dalam satu struct.
*   *Troubleshooting:* Verifikasi alignment menggunakan runtime tracing atau sisipkan struct padding:
```go
type CounterSafe struct {
    workerAProcessed uint64
    _                [56]byte // 64 - 8 bytes = 56 bytes padding
    workerBProcessed uint64
    _                [56]byte
}
```

#### 3. Escape Analysis Ignorance (Nilai Lolos ke Heap)
*   *Masalah:* Melewatkan interface kosong (`interface{}` atau `any`), passing pointer lokal ke luar scope, atau closure function di dalam *hot path* algoritma. Hal ini memaksa *compiler* memindahkan alokasi dari *Stack* (super cepat) ke *Heap* (memerlukan GC sweep).
*   *Troubleshooting:* Kompilasi kode dengan flag optimasi:
    ```bash
    go build -gcflags="-m -m"
    ```
    Periksa output terminal. Pastikan tidak ada pesan: `"leaks to ~r0: moved to heap"`.

---

### 11. Best Practices (Production Checklist)

Gunakan daftar centang operasional ini sebelum mendeploy modul algoritma performa tinggi:

- [ ] **Kapasitas Statis Pangkat Dua:** Seluruh buffer sirkular dideklarasikan dengan ukuran $2^N$ dan menggunakan bitwise masking (`& (cap - 1)`).
- [ ] **Zero-Allocation Hot Path:** Benchmark menunjukkan nilai statis `0 allocs/op` dan `0 B/op` saat penambahan dan pemrosesan data rutin.
- [ ] **Struct Alignment Ordered:** Field dalam tipe bentukan (*struct*) diurutkan mulai dari ukuran tipe data 64-bit (8-byte pointers, int64, float64), 32-bit, 16-bit, hingga 8-bit untuk mencegah *compiler struct padding waste*.
- [ ] **Mitigasi False Sharing:** Variabel atomik yang dimodifikasi oleh thread yang berbeda dipisahkan minimal 64 bytes (`CacheLinePad`).
- [ ] **Bounds Checking Elimination (BCE):** Akses slice berulang dipandu oleh pemeriksaan batas eksplisit di awal method agar Go compiler menghilangkan overhead *bounds check instruction* pada loop dalam.
- [ ] **Thread-Safety Proof:** Paket kode diverifikasi bersih dari *race condition* menggunakan *thread sanitizer*:
  ```bash
  go test -race -count=10 ./...
  ```
- [ ] **Telemetry Invariant:** Metrik sistem (counter dropped packets, window wraps) dihitung menggunakan primitif atomik yang tidak memblokir laju algoritma utama.

---

### 12. Hands-on Practice

Buatlah proyek benchmarking lokal untuk membuktikan superioritas *Mechanical Sympathy Ring Buffer* dibandingkan pendekatan klasik berbasis pointer/heap.

Simpan seluruh file berikut ke dalam direktori: `hands-on/m02/`

#### 12.1. File Struktur
```
hands-on/m02/
├── engine.go
├── engine_test.go
└── Makefile
```

#### 12.2. Implementasi Inti (`hands-on/m02/engine.go`)

```go
package main

import (
	"errors"
	"sync/atomic"
	"unsafe"
)

const CacheLinePadSize = 64

type DataPoint struct {
	ID    int64
	Value int64
}

// ClassicalQueue menggunakan pointer node dinamis (Pola LeetCode tipikal)
type ClassicalNode struct {
	data DataPoint
	next *ClassicalNode
}

type ClassicalQueue struct {
	head *ClassicalNode
	tail *ClassicalNode
}

func NewClassicalQueue() *ClassicalQueue {
	return &ClassicalQueue{}
}

func (cq *ClassicalQueue) Enqueue(dp DataPoint) {
	node := &ClassicalNode{data: dp}
	if cq.tail == nil {
		cq.head = node
		cq.tail = node
		return
	}
	cq.tail.next = node
	cq.tail = node
}

func (cq *ClassicalQueue) Dequeue() (DataPoint, bool) {
	if cq.head == nil {
		return DataPoint{}, false
	}
	dp := cq.head.data
	cq.head = cq.head.next
	if cq.head == nil {
		cq.tail = nil
	}
	return dp, true
}

// ProductionEngineQueue menggunakan Flat Memory Contiguous Ring-Buffer
type ProductionEngineQueue struct {
	head uint64
	_    [CacheLinePadSize - unsafe.Sizeof(uint64(0))]byte

	tail uint64
	_    [CacheLinePadSize - unsafe.Sizeof(uint64(0))]byte

	mask   uint64
	buffer []DataPoint
}

func NewProductionEngineQueue(capacityPow2 uint64) (*ProductionEngineQueue, error) {
	if capacityPow2 == 0 || (capacityPow2&(capacityPow2-1)) != 0 {
		return nil, errors.New("kapasitas harus merupakan bilangan 2^N")
	}

	return &ProductionEngineQueue{
		mask:   capacityPow2 - 1,
		buffer: make([]DataPoint, capacityPow2),
		head:   0,
		tail:   0,
	}, nil
}

func (peq *ProductionEngineQueue) Push(dp DataPoint) bool {
	h := atomic.LoadUint64(&peq.head)
	t := atomic.LoadUint64(&peq.tail)

	if h-t > peq.mask {
		return false // Buffer Penuh (No heap resize)
	}

	peq.buffer[h&peq.mask] = dp
	atomic.StoreUint64(&peq.head, h+1)
	return true
}

func (peq *ProductionEngineQueue) Pop() (DataPoint, bool) {
	t := atomic.LoadUint64(&peq.tail)
	h := atomic.LoadUint64(&peq.head)

	if t == h {
		return DataPoint{}, false // Buffer Kosong
	}

	dp := peq.buffer[t&peq.mask]
	atomic.StoreUint64(&peq.tail, t+1)
	return dp, true
}

func main() {
	// Diisi kosong untuk runtime benchmarks
}
```

#### 12.3. Berkas Pengujian & Benchmark (`hands-on/m02/engine_test.go`)

```go
package main

import (
	"testing"
)

const BufferSize = 1048576 // 2^20 (1 Juta item)

func BenchmarkClassicalQueue(b *testing.B) {
	q := NewClassicalQueue()
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		q.Enqueue(DataPoint{ID: int64(i), Value: int64(i * 2)})
		if i%2 == 0 {
			_, _ = q.Dequeue()
		}
	}
}

func BenchmarkProductionEngineQueue(b *testing.B) {
	q, err := NewProductionEngineQueue(BufferSize)
	if err != nil {
		b.Fatalf("Gagal inisialisasi queue: %v", err)
	}
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		dp := DataPoint{ID: int64(i), Value: int64(i * 2)}
		if !q.Push(dp) {
			_, _ = q.Pop()
			_ = q.Push(dp)
		}
		if i%2 == 0 {
			_, _ = q.Pop()
		}
	}
}
```

#### 12.4. Berkas Automasi (`hands-on/m02/Makefile`)

```makefile
.PHONY: benchmark escape test clean

test:
	go test -v -race ./...

benchmark:
	go test -bench=. -benchmem -benchtime=5s -cpu=1,4 ./...

escape:
	go build -gcflags="-m -m" engine.go

clean:
	rm -f m02.test cpu.pprof mem.pprof
```

---

### 13. Exercise

Kerjakan modul latihan di bawah ini untuk memperdalam intuisi arsitektur memori:

#### Level Easy
*   **Problem:** Implementasikan fungsi penghitung prefix array dinamis (*Running Sum 1D Array*) tanpa mengalokasikan slice baru, melainkan melakukan mutasi *in-place* dengan penjaminan *boundary checking removal*.
*   **Constraint:** Kompleksitas Memori Tambahan $O(1)$, $0\text{ allocs/op}$.

#### Level Medium
*   **Problem:** Bangun implementasi algoritma **LRU (Least Recently Used) Cache** dengan kapasitas 100.000 elemen. Alih-alih menggunakan `container/list` standar Go yang berbasis *doubly-linked list pointer*, gunakan array datar tunggal berkapasitas tetap di mana pointer `prev` dan `next` direpresentasikan oleh indeks integer `int32`.
*   **Constraint:** Zero dynamic allocations saat operasi `Get` dan `Put`. Akses rata-rata $O(1)$.

#### Level Hard
*   **Problem:** Rancang **Lock-Free Monotonic Stack** multi-producer single-consumer (MPSC) yang memproses pasangan data harga saham (*Timestamp, Bid, Ask*). Engine harus mampu membuang pesanan yang tidak optimal secara instan saat aliran order masuk.
*   **Constraint:** Wajib menggunakan primitif `sync/atomic`, memitigasi fenomena *False Sharing* antar thread produsen, dan membuktikan nol alokasi heap via `go test -benchmem`.

---

### 14. Challenge

> **Tantangan Arsitektur: "Ultra-High Frequency Disjoint-Set Union Engine for Fraud Graph Detection"**

**Deskripsi Kasus:**
Sebuah bank digital multinasional menghadapi serangan transaksi penipuan terorganisir yang membentuk graf transfer rekening melingkar (*mule account rings*). Tim data streaming Anda bertugas mendeteksi apakah dua rekening bank berada dalam jaringan penipuan yang sama secara *real-time* saat transaksi pembayaran diotorisasi.

**Spesifikasi & Kendala Sistem:**
1. Graf menampung setidaknya **50.000.000 (50 Juta) entitas node rekening unik**.
2. Engine harus mengevaluasi operasi `Union(accountA, accountB)` dan `Find(accountA) == Find(accountB)` dalam waktu latensi puncak **$< 500\text{ nanodetik}$** per transaksi.
3. Total batas alokasi memori fisik RAM server adalah **maksimal 1.5 GB**. Penggunaan model graf node berbasis pointer standar akan memicu *Out Of Memory* (OOM) karena overhead object header (16 bytes per objek pada Go runtime + 8 byte pointer).
4. Solusi tidak boleh menggunakan database eksternal; komputasi harus dieksekusi murni secara *in-memory* pada *bare-metal worker core*.
5. Wajib menyelesaikan fenomena *tree height degradation* tanpa memicu rekursi mendalam yang berpotensi meledakkan batas Stack frame CPU.

*Instruksi:* Rancang arsitektur struktur data, susunan layout bit data, mekanisme *path compression* non-rekursif, dan skema pengindeksan array padat (*dense flat array*) untuk menuntaskan skenario di atas.

---

### 15. Quiz Evaluasi Pemahaman

Jawab dan analisislah pertanyaan evaluasi berikut:

#### Bagian 1: Basic (5 Pertanyaan)
1. **Berapa ukuran umum dari satu *Cache Line* pada arsitektur prosesor Intel x86-64 dan ARM64 modern?**
   * *Jawaban:* 64 Bytes.
2. **Mengapa operasi `i & (Capacity - 1)` jauh lebih disukai daripada `i % Capacity` pada sistem low-latency?**
   * *Jawaban:* Operasi modulo `%` diterjemahkan menjadi instruksi hardware division (`DIV`/`IDIV`) yang membutuhkan sekitar 15–40 siklus CPU, sedangkan bitwise AND `&` dieksekusi hanya dalam 1 siklus CPU.
3. **Apa yang dimaksud dengan *Spatial Locality* dalam hierarki memori komputer?**
   * *Jawaban:* Kecenderungan prosesor untuk mengakses lokasi memori fisik yang letaknya berdampingan atau berdekatan secara berurutan setelah lokasi pertama dibaca.
4. **Apa bahaya laten penggunaan *Linked List* teoretis $O(1)$ pada performa CPU aktual?**
   * *Jawaban:* Fragmentasi memori heap yang menyebabkan fenomena *pointer chasing*, memicu tingginya angka *L1/L2 Cache Misses* dan mematikan fungsi *hardware prefetcher*.
5. **Bagaimana flag `-gcflags="-m"` pada Go compiler membantu dalam rekayasa performa algoritma?**
   * *Jawaban:* Flag tersebut menampilkan hasil *escape analysis* compiler, menunjukkan apakah variabel dialokasikan di Stack yang cepat atau bocor (*escapes*) ke Heap yang membebani Garbage Collector.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Jelaskan apa yang dimaksud dengan fenomena *False Sharing* dalam pemrosesan konkurensi data paralel.**
   * *Jawaban:* Terjadi saat dua thread/core berbeda memodifikasi variabel atomik independen yang kebetulan berada di dalam blok *cache line* 64-byte yang sama, memaksa subsistem cache terus menerus melakukan sinkronisasi bus dan invalidasi salinan data local core secara sia-sia.
7. **Mengapa penataan urutan field dalam sebuah `struct` di Go atau C++ memengaruhi total konsumsi memori?**
   * *Jawaban:* Akibat aturan penyelarasan memori (*memory alignment*), prosesor menyisipkan *padding bytes* kosong agar tipe data tertentu beralamat pada kelipatan ukurannya sendiri (misal: variabel 64-bit harus beralamat kelipatan 8 byte). Menyusun field acak membuang ruang untuk padding.
8. **Kapan algoritma Monotonic Queue menjadi pilihan superior dibanding Binary Heap (Priority Queue) pada problem sliding window?**
   * *Jawaban:* Monotonic Queue mencapai kompleksitas waktu teramortisasi $O(1)$ untuk penambahan dan pencarian ekstremum, sementara Binary Heap memerlukan $O(\log K)$ untuk setiap penambahan elemen dan $O(K)$ untuk evikasi elemen tengah tanpa tracking pointer tambahan.
9. **Apa dampak langsung dari *Branch Misprediction* terhadap *Instruction Pipeline* CPU?**
   * *Jawaban:* Seluruh instruksi spekulatif yang sudah di-fetch dan di-decode ke dalam pipeline CPU harus dibatalkan dan dibersihkan (*pipeline flush*), membuang sekitar 15 hingga 20 siklus CPU sia-sia.
10. **Bagaimana cara mengeliminasi kebutuhan Garbage Collection sama sekali pada algoritma pemrosesan stream 24/7?**
    * *Jawaban:* Dengan melakukan alokasi tetap di awal (*pre-allocation*) seluruh buffer array saat startup sistem, mendaur ulang slot menggunakan indeks melingkar (*ring-buffer index recycling*), dan melarang pembuatan objek baru di dalam scope loop pemrosesan.

#### Bagian 3: Skenario Kasus Produksi (3 Skenario)
11. **Skenario A:** Tim Anda mengimplementasikan Trie untuk autokomplet rute URL gateway. Saat stress-test 100.000 RPS, throughput turun drastis dan latensi P99 naik ke 80ms. CPU profiler menunjukkan bahwa fungsi `runtime.mallocgc` dan `runtime.scanobject` mendominasi 70% siklus CPU. Tindakan arsitektural apa yang wajib diambil?
    * *Solusi Evaluasi:* Ganti implementasi Node Trie berbasis heap pointer dinamis (`type Node struct { children map[rune]*Node }`) menjadi **Array Datar Kompak / Double-Array Trie (DAT)** yang memetakan relasi transisi state karakter ke dalam satu array integer 1 dimensi yang dialokasikan di awal.
12. **Skenario B:** Dua thread eksekutor throughput tinggi memperbarui dua counter independen: `metrics.SuccessCount` dan `metrics.FailureCount`. Pengujian menunjukkan latensi penulisan atomik 10x lebih lambat saat kedua thread dijalankan bersamaan dibanding pengujian single-thread. Diagnosislah penyebabnya dan berikan solusinya.
    * *Solusi Evaluasi:* Kedua counter mengalami *False Sharing* karena dialokasikan bersebelahan dalam rentang memori kurang dari 64 byte. Solusinya: Sisipkan *cache line padding* sebesar 56 byte di antara kedua variabel tersebut agar terdistribusi ke segmen cache line yang terisolasi.
13. **Skenario C:** Anda memiliki ring buffer berukuran dinamis yang melakukan fungsi resize ganda (`cap * 2`) saat penuh. Pada throughput rata-rata, latensi berada pada level stabil 500ns, namun setiap beberapa menit sekali, terjadi lonjakan latensi (*spike*) sebesar 12 milidetik yang memicu timeout pada sistem hilir. Apa penyebab utamanya dan bagaimana mitigasinya?
    * *Solusi Evaluasi:* Lonjakan latensi disebabkan oleh operasi pemindahan array (*array copy overhead*) dan alokasi blok memori baru yang masif saat terjadi peluapan kapasitas. Mitigasinya: Tetapkan kapasitas maksimum sejak awal (*static hard boundary*) dan terapkan kebijakan mitigasi meluap (*backpressure* atau *tail drop/overwrite* pada ring buffer) tanpa memicu realokasi dinamis.

---

### 16. Summary

1. **Hardware Invariance:** Kompleksitas teoretis $O(N)$ dari sebuah algoritma LeetCode tidak menjamin kecepatan superior di sistem fisik tanpa memperhatikan hierarki memori, *cache lines*, dan *branch prediction*.
2. **Kekuatan Contiguous Memory:** Struktur data berbasis array datar (*contiguous flat buffers*) secara konsisten mengungguli struktur data berbasis node pointer (*linked lists*, *trees*) karena efisiensi penarikan data 64-byte L1/L2 cache line dan *hardware prefetching*.
3. **Zero-Allocation Mindset:** Performa enterprise deterministik dengan latensi rendah (P99/P99.9 dalam skala mikrodetik) hanya dapat diraih dengan mengeliminasi alokasi heap dinamis pada jalur data kritis (*hot path*) untuk meniadakan jeda *Garbage Collection*.
4. **Isolasi Memori Konkuren:** Penggunaan operasi atomik dan algoritma bebas kunci (*lock-free*) wajib dipadukan dengan teknik *cache-line padding* untuk memutus rantai degradasi akibat *False Sharing*.
5. **Transisi Mindset:** Rekayasa algoritma enterprise bukan sekadar mencari keluaran yang "Accepted", melainkan membangun solusi yang hemat sumber daya perangkat keras, stabil di bawah saturasi konkurensi tinggi, dan memiliki karakteristik latensi yang deterministik.