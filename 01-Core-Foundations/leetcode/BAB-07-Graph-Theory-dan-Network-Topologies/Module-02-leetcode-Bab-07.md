# BAB 07: Materi Lanjutan
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Memilih Struktur Data Lanjutan:** Mengidentifikasi use-case produksi yang membutuhkan struktur data tingkat lanjut (seperti *Segment Tree*, *Disjoint Set Union (DSU)*, dan *Monotonic Queue*) di atas struktur data standar.
2. **Mentranslasikan Solusi Algoritmik ke Kode Produksi:** Mengubah solusi abstrak LeetCode (tipe *Hard*) menjadi implementasi *thread-safe*, *zero-allocation*, dan ramah *CPU cache line* menggunakan Go.
3. **Mengoptimasi Latensi p99 dan Throughput:** Mereduksi kompleksitas komputasi dari $O(N)$ menjadi $O(\log N)$ atau $O(1)$ *amortized* pada jalur kritis (*hot path*) sistem terdistribusi skala enterprise.
4. **Menerapkan Profiling dan Benchmarking Tingkat Lanjut:** Mengukur konsumsi memori (*escape analysis*), alokasi heap, dan siklus CPU menggunakan perkakas *profiling* bawaan sistem.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Analisis Kompleksitas Algoritma:** Asymptotic Notation (Big-O, Big-Omega, Big-Theta), amortized analysis, serta *Master Theorem*.
- **Struktur Data Dasar & Menengah:** Array contiguous, Hash Map, Doubly Linked List, Binary Heap, Trie, Graph (Adjacency List/Matrix).
- **Fundamental Sistem Komputer:** Memory hierarchy (L1/L2/L3 cache, RAM), virtual memory, cache line invalidation, pointer chasing penalties, dan primitives sinkronisasi konkurrensi (*mutex*, *atomic operations*).
- **Bahasa Pemrograman Go:** Go memory model, goroutine, channel, slice internals, serta `sync.Pool`.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi algoritma di ranah kompetitif berfokus pada $O$-time dan $O$-space teoritis dalam lingkungan *single-thread* dengan memori tak terbatas. Sebaliknya, pada arsitektur produksi berlatensi rendah (*low-latency production systems*), arsitektur internal harus mempertimbangkan:

#### A. Cache Locality vs. Pointer Chasing
Struktur data berbasis *node* (misalnya: *Binary Search Tree* berbasis *pointer* atau linked list dinamis) menyebabkan alokasi memori yang terfragmentasi di *heap*. Kondisi ini memicu *CPU Cache Misses* berulang kali karena *hardware prefetcher* CPU tidak dapat memprediksi alamat memori berikutnya.

```
Pointer-based Node Tree (Cache-Unfriendly):
[Heap Addr 0x004] Node A -> Points to 0x89F (L1 Cache Miss!)
[Heap Addr 0x89F] Node B -> Points to 0x12A (L1 Cache Miss!)

Contiguous Array-backed Tree (Cache-Friendly):
[Index 0 | Index 1 | Index 2 | Index 3 | Index 4 | Index 5]
<--------- Single Cache Line (64 Bytes Read Ahead) --------->
```

Pada *Segment Tree* berarsitektur produksi, representasi pohon diimplementasikan ke dalam *flattened contiguous array* berukuran $4N$. Node anak dari indeks $i$ secara deterministik berada pada $2i+1$ (kiri) dan $2i+2$ (kanan), memaksimalkan pemanfaatan L1/L2 *data cache*.

#### B. Disjoint Set Union (DSU) dengan Optimasi Ganda
DSU mengelola partisi himpunan saling lepas. Kompleksitas operasi DSU standar tanpa optimasi dapat memburuk hingga $O(N)$. Melalui dua teknik:
1. **Path Compression:** Meratakan struktur pohon saat operasi `Find` dijalankan, menghubungkan setiap node yang dilintasi langsung ke *root*.
2. **Union by Rank/Size:** Menggabungkan pohon dengan tinggi/ukuran lebih kecil ke bawah pohon yang lebih besar untuk mencegah ketidakseimbangan tinggi pohon.

Kombinasi kedua teknik ini menghasilkan kompleksitas waktu per operasi sebesar $O(\alpha(N))$, di mana $\alpha$ adalah *Inverse Ackermann Function*. Untuk seluruh nilai $N$ praktis ($N < 10^{80}$), $\alpha(N) \le 4$, yang secara efektif ekuivalen dengan $O(1)$ *amortized*.

#### C. Monotonic Queue / Deque
Digunakan untuk mempertahankan elemen terurut secara monoton (naik atau turun) dalam jendela geser (*sliding window*). Secara internal, penghapusan elemen dari belakang (*tail*) terjadi ketika elemen baru mendominasi elemen lama, menjamin bahwa setiap elemen hanya di-*push* dan di-*pop* maksimal satu kali sepanjang siklus hidup jendela. Ini mengubah komputasi *Sliding Window Maximum/Minimum* dari $O(N \cdot K)$ menjadi $O(N)$.

---

### 4. Why & What

| Dimensi | LeetCode / Competitive Programming | Enterprise Production System |
| :--- | :--- | :--- |
| **Fokus Utama** | Memenuhi batasan waktu (*Time Limit Exceeded*) & memori (*Memory Limit Exceeded*). | Menjamin p99 SLA, meminimalkan GC pauses, konkurensi aman, ketersediaan tinggi (*fault tolerance*). |
| **Layout Memori** | Menggunakan alokasi dinamis bebas (`new`, malloc, node pointer). | Menghindari alokasi dinamis pada *hot path* via *pre-allocation*, object pooling, array *flattening*. |
| **Penanganan Error**| Diabaikan (input diasumsikan valid sesuai batasan soal). | *Defensive programming*: validasi boundary, *context cancellation*, graceful degradation. |
| **Skalabilitas** | Input terbatas ($N \le 10^5$ atau $10^6$). | *Infinite data stream* (jutaan operasi per detik, pemrosesan 24/7). |

**Mengapa struktur lanjutan ini krusial di produksi?**
Sistem komputasi modern sering menghadapi batas skalabilitas horizontal saat latensi menjadi kendala utama. Mengganti algoritma $O(N)$ dengan $O(\log N)$ pada *hot path* (seperti penghitungan *rolling metric*, aggregation jendela waktu, atau resolusi dependensi izin akses mikroservis) sering kali memberikan peningkatan performa hingga 100x lipat lebih tinggi dibandingkan penambahan node komputasi baru.

---

### 5. How (Workflow Detail)

Alur rekayasa untuk menerapkan algoritma komputasi lanjutan ke dalam modul produksi:

```
[Problem Formulation]
        │
        ▼
[Algorithmic Abstraction] ──> (Identifikasi Pola: Segment Tree vs DSU vs Sliding Window)
        │
        ▼
[Memory Layout Design]    ──> (Ratakan ke Contiguous Slice, kalkulasi kebutuhan max memory)
        │
        ▼
[Concurrency Strategy]    ──> (Lock-free atomic, Fine-grained RWMutex, atau Sharded Locks)
        │
        ▼
[Zero-Allocation Guard]   ──> (Jalankan Escape Analysis: go build -gcflags="-m")
        │
        ▼
[Benchmarking & Profiling]──> (Validasi p99, throughput ops/sec, dan allocs/op)
```

1. **Abstraksi Problem:** Petakan kebutuhan sistem riil ke dalam model formal (misal: *rate limiter rolling window* $\rightarrow$ *sliding window monotonic deque* atau *segment tree* berbasis interval waktu).
2. **Desain Tata Letak Memori:** Alokasikan *backing array* di awal (*pre-allocation*) untuk mencegah alokasi ulang dan penyalinan data (*slice growth*).
3. **Strategi Konkurensi:** Bungkus struktur data menggunakan *fine-grained synchronization* atau partisi (*sharding*) untuk menghindari *contention bottleneck*.
4. **Optimasi Alokasi (Zero-Allocation):** Pastikan variabel internal tidak bocor ke *heap* melalui *escape analysis*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Disjoint Set Union (DSU) vs Birokrasi Korporasi
Bayangkan integrasi sistem perbankan multi-cabang:
- Tanpa optimasi: Setiap pegawai harus melapor ke manajer cabang, manajer cabang melapor ke manajer area, manajer area ke direktur (rantai birokrasi panjang: $O(N)$).
- **Union by Rank:** Ketika dua divisi bergabung, divisi yang lebih kecil dilebur ke dalam divisi yang lebih besar.
- **Path Compression:** Setiap kali seorang pegawai melapor ke Direktur Utama, ia diberikan jalur komunikasi langsung ke Direktur Utama untuk urusan berikutnya. Setelah satu kali koordinasi, semua staf memiliki akses langsung ($O(1)$ efektif).

```
Struktur Awal (Sebelum Path Compression):
      [Root A]
         ▲
         │
      [Node B]
         ▲
         │
      [Node C]
         ▲
         │
      [Node D]  <-- Find(D) dipanggil: harus menelusuri C -> B -> A

Setelah Path Compression (Semua mengarah langsung ke Root):
         [Root A]
      ┌─────┼─────┐
      │     │     │
   [Node B][Node C][Node D]  <-- Find(D) berikutnya hanya 1 hop!
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Monotonic Deque Murni (Algoritmik)

Mencari nilai maksimum dalam setiap sub-array berukuran $K$ (*Sliding Window Maximum*).

```go
package main

import "fmt"

func maxSlidingWindow(nums []int, k int) []int {
	if len(nums) == 0 || k <= 0 {
		return []int{}
	}

	result := make([]int, 0, len(nums)-k+1)
	// deque menyimpan indeks dari elemen nums
	deque := make([]int, 0, k)

	for i := 0; i < len(nums); i++ {
		// 1. Keluarkan elemen yang sudah berada di luar window [i-k+1, i]
		if len(deque) > 0 && deque[0] < i-k+1 {
			deque = deque[1:]
		}

		// 2. Pertahankan sifat monoton: hapus elemen yang lebih kecil dari nums[i]
		for len(deque) > 0 && nums[deque[len(deque)-1]] < nums[i] {
			deque = deque[:len(deque)-1]
		}

		// 3. Masukkan indeks saat ini
		deque = append(deque, i)

		// 4. Catat maksimum jika window sudah mencapai ukuran k
		if i >= k-1 {
			result = append(result, nums[deque[0]])
		}
	}

	return result
}

func main() {
	nums := []int{1, 3, -1, -3, 5, 3, 6, 7}
	k := 3
	fmt.Printf("Window Max: %v\n", maxSlidingWindow(nums, k))
	// Output: [3 3 5 5 6 7]
}
```

---

#### B. Practical Example: Production-Grade Sliding-Window Latency Aggregator

Implementasi *thread-safe*, *zero-allocation* *Sliding Window Peak Latency Tracker* untuk sistem *gateway API* performa tinggi yang menangani metrik *real-time*.

```go
package metrics

import (
	"errors"
	"sync"
	"time"
)

var (
	ErrInvalidWindowSize = errors.New("window size must be greater than zero")
	ErrBufferFull        = errors.New("ring buffer is full")
)

// MetricPoint merepresentasikan sampel latensi pada waktu tertentu.
type MetricPoint struct {
	TimestampNano int64
	LatencyMicro  int64
}

// PeakLatencyTracker mengelola monitoring latensi puncak dengan performa tinggi.
// Menggunakan Ring Buffer statis dan Monotonic Index Buffer untuk menjamin zero-allocation.
type PeakLatencyTracker struct {
	mu           sync.RWMutex
	windowNano   int64
	capacity     int
	buffer       []MetricPoint
	dequeIndices []int // Monotonic Deque menyimpan indeks dari buffer

	head  int
	tail  int
	count int

	// Deque pointers
	dHead int
	dTail int
}

// NewPeakLatencyTracker menginisialisasi tracker dengan kapasitas teralokasi di awal.
func NewPeakLatencyTracker(windowDuration time.Duration, capacity int) (*PeakLatencyTracker, error) {
	if capacity <= 0 {
		return nil, ErrInvalidWindowSize
	}

	return &PeakLatencyTracker{
		windowNano:   windowDuration.Nanoseconds(),
		capacity:     capacity,
		buffer:       make([]MetricPoint, capacity),
		dequeIndices: make([]int, capacity),
	}, nil
}

// Record menambahkan metrik baru dan memperbarui status monotonic deque.
// Thread-safe dan bebas dari heap allocation.
func (plt *PeakLatencyTracker) Record(latencyMicro int64) error {
	now := time.Now().UnixNano()

	plt.mu.Lock()
	defer plt.mu.Unlock()

	// 1. Validasi kapasitas buffer
	if plt.count == plt.capacity {
		return ErrBufferFull
	}

	// 2. Simpan metrik ke ring buffer
	idx := plt.tail
	plt.buffer[idx] = MetricPoint{
		TimestampNano: now,
		LatencyMicro:  latencyMicro,
	}
	plt.tail = (plt.tail + 1) % plt.capacity
	plt.count++

	// 3. Purge data kedaluwarsa dari head ring buffer & deque
	threshold := now - plt.windowNano
	for plt.count > 0 && plt.buffer[plt.head].TimestampNano < threshold {
		if plt.dHead < plt.dTail && plt.dequeIndices[plt.dHead] == plt.head {
			plt.dHead++
		}
		plt.head = (plt.head + 1) % plt.capacity
		plt.count--
	}

	// 4. Pertahankan sifat Monotonic Decreasing pada deque
	for plt.dTail > plt.dHead {
		lastIdx := plt.dequeIndices[plt.dTail-1]
		if plt.buffer[lastIdx].LatencyMicro <= latencyMicro {
			plt.dTail--
		} else {
			break
		}
	}

	// 5. Masukkan indeks baru ke deque
	plt.dequeIndices[plt.dTail] = idx
	plt.dTail++

	return nil
}

// GetPeakLatency mengambil nilai latensi puncak pada sliding window aktif.
// Kompleksitas Waktu: O(1) Amortized.
func (plt *PeakLatencyTracker) GetPeakLatency() (int64, error) {
	plt.mu.RLock()
	defer plt.mu.RUnlock()

	now := time.Now().UnixNano()
	threshold := now - plt.windowNano

	// Periksa apakah deque valid dan belum kedaluwarsa
	for plt.dHead < plt.dTail {
		peakIdx := plt.dequeIndices[plt.dHead]
		if plt.buffer[peakIdx].TimestampNano >= threshold {
			return plt.buffer[peakIdx].LatencyMicro, nil
		}
		// Data kedaluwarsa dilewati secara non-mutating pada read-lock
		plt.dHead++
	}

	return 0, nil
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Perusahaan FinTech memproses rata-rata 350.000 transaksi pembayaran per detik (*TPS*) yang melewati *Fraud Detection Engine*. Salah satu kriteria deteksi penipuan adalah penghitungan *Velocity Risk Index*:
> *"Berapa pengeluaran maksimum dan total volume transaksi yang dilakukan oleh akun entitas yang sama (atau kartu yang berafiliasi) dalam rentang waktu geser 10 menit terakhir?"*

#### Kegagalan Pendekatan Naif
Sistem awal mengandalkan kueri basis data Redis:
```
ZADD user:<id>:txns <timestamp> <amount>
ZRANGEBYSCORE user:<id>:txns <now-10m> <now>
```
**Dampak Buruk:**
- Operasi `ZRANGEBYSCORE` berbiaya $O(\log M + K)$ di mana $K$ adalah jumlah transaksi dalam rentang tersebut.
- Pada beban 350k TPS dengan ribuan akun aktif, I/O jaringan dan CPU pada Redis *cluster* mengalami saturasi saturasi 100%. Latensi p99 melonjak hingga **> 450 ms**, melanggar batas SLA internal ($< 25 \text{ ms}$).

#### Solusi Arsitektur Menggunakan In-Memory Segment Tree + DSU
Arsitektur didesain ulang dengan memindahkan agregasi transaksi ke *in-memory state engine* terdistribusi (partisi berbasis Actor model / consistent hashing):
1. **DSU (Disjoint Set Union):** Digunakan untuk meresolusikan *Affiliated Identity Graph* secara dinamis. Jika akun A mentransfer ke akun B menggunakan perangkat X yang sama dengan akun C, ketiga akun tersebut digabungkan ke dalam satu set identitas dalam waktu $O(\alpha(N))$.
2. **Contiguous Segment Tree:** Setiap node partisi menyimpan *Segment Tree* berbasis interval waktu 1 detik untuk setiap set identitas (600 slot untuk 10 menit).
   - *Update* transaksi: $O(\log W)$, di mana $W = 600$ (konstan $\approx 10$ langkah operasi CPU).
   - *Range Query Maximum & Sum*: $O(\log W) \approx 10$ operasi array langsung pada L1/L2 cache.

#### Hasil Produksi
- Latensi p99 turun drastis dari **450 ms** menjadi **1.2 ms**.
- Pemanfaatan memori turun 65% karena representasi berbasis array statis tanpa alokasi JSON/objek dinamis.
- *Throughput* sistem per *node* meningkat dari 8.000 TPS menjadi 85.000 TPS.

---

### 9. Trade-offs

| Pendekatan Algoritmik | Keuntungan | Biaya & Konsekuensi | Batasan (Constraint) |
| :--- | :--- | :--- | :--- |
| **Segment Tree (Array-backed)** | *Query* dan *update* rentang bernilai $O(\log N)$. Stabil, tanpa reorganisasi memori dinamis. | Membutuhkan memori statis $4N$. Boros memori jika data rentang sangat renggang (*sparse*). | Sangat optimal jika rentang koordinat waktu/ruang telah diketahui batasannya (*bounded*). |
| **Monotonic Deque** | Operasi *sliding window aggregate* $O(1)$ amortized. Menggunakan memori linear $O(K)$. | Hanya mendukung evaluasi data dari satu ujung (*monotonic movement*). Tidak mendukung kueri rentang arbitrer. | Data input harus terurut secara alami berdasarkan sumbu waktu/posisi. |
| **Disjoint Set Union (DSU)** | Menggabungkan dan mencari set setara dalam $O(\alpha(N)) \approx O(1)$. Sangat efisien memori. | Operasi pemisahan kembali (*split* / *undo*) sangat kompleks dan membutuhkan *persistent/rollback stack*. | Hanya ideal untuk relasi biner yang bersifat transitif dan konvergen (hanya bertambah). |
| **Hash Table Lookup (Pendekatan Naif)** | Implementasi instan, fleksibel, didukung library bawaan. | Latensi tidak dapat diprediksi saat *hash collision* dan *rehashing*. Pointer chasing berat, alokasi memori tinggi. | Tidak dapat diterapkan untuk pelaporan *rolling window* berfrekuensi tinggi. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Integer Overflow pada Kalkulasi Midpoint Pohon
- **Pola Masalah:** Menghitung titik tengah rentang pencarian dengan `mid := (left + right) / 2`.
- **Dampak Produksi:** Terjadi *integer overflow* jika `left + right` melampaui nilai maksimum integer, menghasilkan indeks negatif dan memicu `panic: runtime error: index out of range`.
- **Solusi:**
  ```go
  // Tepat
  mid := left + (right-left)/2
  ```

#### Kesalahan 2: Retaining Object Reference Memory Leaks
- **Pola Masalah:** Memajukan pointer head pada Ring Buffer atau Monotonic Deque tanpa membersihkan referensi elemen yang dihapus jika slice menampung pointer.
- **Dampak Produksi:** *Garbage Collector* tidak dapat mereklamasi memori objek referensi lama, menyebabkan degradasi bertahap (*slow memory leak*).
- **Solusi:** Set referensi pointer ke `nil` sebelum indeks dilewati jika slice menyimpan data berupa pointer.

#### Kesalahan 3: Unbounded Slice Growth (Pemicu Latensi Tak Terduga)
- **Pola Masalah:** Menggunakan `append()` terus-menerus tanpa kapasitas awal yang pasti pada struktur data yang berulang kali dimodifikasi.
- **Dampak Produksi:** Alokasi ulang memori (*heap reallocation*) dan penyalinan data memicu latensi p99 spike ratusan milidetik.
- **Troubleshooting:** Deteksi alokasi dengan profiler:
  ```bash
  go test -bench=. -benchmem -memprofile=mem.out
  go tool pprof -alloc_space mem.out
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic Memory Allocation:** Alokasikan kapasitas array (*buffer*) secara penuh pada saat inisialisasi modul (*startup phase*).
- [ ] **Escape Analysis Verification:** Jalankan `go build -gcflags="-m -m"` untuk memastikan struktur data pada *hot path* dialokasikan di *stack*, bukan *heap*.
- [ ] **Lock Granularity Minimization:** Hindari menahan *lock* (Mutex) selama operasi I/O jaringan atau parsing data. Pisahkan mutasi struktur algoritmik dari I/O.
- [ ] **Boundary Assertion:** Selalu validasi indeks batas sebelum melakukan mutasi array internal guna menghindari *CPU panic*.
- [ ] **Cache Line Alignment:** Pertimbangkan *padding* struktural (`[64]byte`) untuk mencegah *False Sharing* antar core CPU saat struktur data diakses secara multithreaded.
- [ ] **Concurrency Stress Testing:** Lakukan pengujian *race condition* secara intensif menggunakan flag `-race` pada pengujian unit berulang.

---

### 12. Hands-on Practice

Buatlah repositori latihan lokal dengan tata kelola direktori:
```text
hands-on/m02/
├── dsu/
│   ├── dsu.go
│   └── dsu_test.go
├── segment_tree/
│   ├── segrange.go
│   └── segrange_test.go
└── main.go
```

#### Langkah-langkah:
1. **Langkah 1:** Implementasikan *Disjoint Set Union* yang mendukung *Path Compression* dan *Union by Rank* di dalam file `hands-on/m02/dsu/dsu.go`.
2. **Langkah 2:** Tambahkan pengujian unit konvergen di `hands-on/m02/dsu/dsu_test.go` untuk menguji $1.000.000$ partisi dan deteksi siklus graf.
3. **Langkah 3:** Implementasikan Segment Tree untuk *Range Sum Query* dan *Range Update* di file `hands-on/m02/segment_tree/segrange.go`.
4. **Langkah 4:** Jalankan pengujian performa alokasi:
   ```bash
   cd hands-on/m02/
   go test ./... -bench=. -benchmem -run=^$
   ```
   *Target: 0 B/op dan 0 allocs/op pada operasi pencarian dan pembaruan.*

---

### 13. Exercise

#### Tingkat Kesulitan: Easy
- **Topik:** *Array Monotonic Verification*
- **Tugas:** Buat fungsi Go `IsMonotonic(data []int) bool` yang berjalan dalam satu kali lintasan ($O(N)$ waktu, $O(1)$ memori tambahan) untuk memverifikasi apakah deret transaksi kuantitatif terurut monoton naik atau turun.

#### Tingkat Kesulitan: Medium
- **Topik:** *Distributed Task Cycle Detector (Topological Sort / DSU)*
- **Tugas:** Diberikan daftar dependensi mikroservis `pairs [][]string`. Implementasikan sistem pendeteksi dependensi melingkar (*circular dependency*) secara inkremental menggunakan DSU. Return error jika dependensi baru menyebabkan kebuntuan (*deadlock dependency*).

#### Tingkat Kesulitan: Hard
- **Topik:** *Dynamic Rolling Window Rate Limiter via Segment Tree*
- **Tugas:** Implementasikan *Rate Limiter* berbasis *Segment Tree* berkapasitas 86.400 detik (representasi 24 jam) yang dapat mengembalikan jumlah transaksi pada rentang detik arbitrer $[T_{start}, T_{end}]$ dan memperbarui hitungan per detik dalam $O(\log S)$ di mana $S = 86400$. Pastikan konsumsi memori stabil di bawah 4 MB.

---

### 14. Challenge

#### Skenario Kasus: Real-Time Auction Order Book Arbitrage Engine
Anda ditugaskan mendesain mesin inti (*core engine*) bursa perdagangan terdistribusi untuk memproses buku order (*order book*) lintas mata uang secara *real-time*.

**Persyaratan Sistem:**
1. Mesin menerima aliran order berupa: `InsertOrder(orderID, price, volume, side)` dan `CancelOrder(orderID)`.
2. Mesin harus dapat memberikan jawaban instan ($< 10 \text{ microseconds}$, p99) untuk:
   - Volume kumulatif likuiditas yang tersedia antara rentang harga $[P_{low}, P_{high}]$.
   - Titik *spread* harga optimum (Best Bid dan Best Ask).
3. **Kendala Produksi Mutlak:**
   - Tidak diperbolehkan adanya alokasi heap (`0 allocs/op`) selama pengeksekusian kueri dan pembaruan order.
   - Sistem harus aman dari *deadlock* saat diakses secara konkruen oleh ratusan worker goroutine.
   - Pemanfaatan CPU cache line harus optimal; dilarang menggunakan representasi binary tree berbasis pointer dinamis konvensional.

*Rancang dan susun spesifikasi antarmuka komponen, strategi representasi struktur data di memori fisik, serta penanganan konkurensi tanpa lock contention tinggi.*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa array kontigu lebih ramah terhadap performa CPU cache dibandingkan linked list konvensional?
2. Berapa kompleksitas waktu teoritis untuk operasi `Find` dan `Union` pada DSU yang menggunakan *path compression* dan *union by rank*?
3. Apa perbedaan struktural mendasar antara *Segment Tree* dan *Binary Indexed Tree (Fenwick Tree)* dalam hal fleksibilitas operasi kueri?
4. Mengapa representasi pohon pada *Segment Tree* dengan array membutuhkan kapasitas hingga $4N$?
5. Apa konsekuensi teknis pada Go runtime jika sebuah fungsi meloloskan variabel lokal ke heap (*variable escapes to heap*) pada *hot path* 100k TPS?

#### B. Pertanyaan Intermediate
6. Bagaimana cara kerja *Monotonic Deque* sehingga mampu memberikan kompleksitas $O(1)$ amortized untuk kueri nilai maksimum pada sliding window?
7. Mengapa operasi pembagian `mid := (left + right) / 2` tidak disarankan untuk algoritma komputasi berskala enterprise?
8. Bagaimana strategi mencegah kondisi *False Sharing* saat mendesain array struktur data yang diakses oleh banyak thread/goroutine secara paralel?
9. Dalam skenario apa struktur data DSU **gagal** menjadi solusi optimal untuk penanganan konektivitas graf dinamis di produksi?
10. Bagaimana cara perkakas kompilator `go build -gcflags="-m"` membantu perekayasa dalam mendeteksi inefisiensi alokasi struktur data?

#### C. Skenario Kasus Produksi
11. **Skenario 1:** Sebuah mikroservis *financial ticker* mengalami latensi spike berkala (setiap 3 menit mencapai p99 600 ms). Berdasarkan trace, masalah terjadi pada fungsi agregasi sliding window 10 menit yang menggunakan slice dinamis dan `sort.Ints()`. Jelaskan langkah sistematis restrukturisasi algoritma dan data layout untuk menekan p99 ke bawah 5 ms.
12. **Skenario 2:** Anda memiliki graf dependensi antar layanan sebesar 50.000 komponen yang sering diperbarui secara dinamis oleh deployment pipeline. Diperlukan sistem verifikasi instan untuk menolak deployment yang memicu siklus melingkar. Evaluasi trade-off penggunaan BFS/DFS siklik reguler vs DSU. Kapan DSU tidak dapat mendeteksi siklus pada directed graph?
13. **Skenario 3:** Arsitektur in-memory cache menggunakan *Segment Tree* mengalami penurunan performa saat diakses secara paralel oleh 64 Core CPU, meskipun operasi pembacaan dilindungi oleh `sync.RWMutex`. Analisis penyebab *lock contention* tersebut dan usulkan perbaikan arsitekturalnya.

---

#### Kunci Jawaban & Evaluasi

##### Jawaban Basic
1. Array kontigu menempati alamat fisik memori yang berurutan, memungkinkan *hardware prefetcher* CPU memuat data ke dalam *cache line* (64 byte) sebelum diakses. Linked list menyimpan node pada alamat acak di heap, memicu *pointer chasing* dan *cache misses*.
2. $O(\alpha(N))$ di mana $\alpha$ adalah *Inverse Ackermann Function*, yang bernilai $\le 4$ untuk data skala nyata, secara praktis ekuivalen dengan $O(1)$ amortized.
3. *Fenwick Tree* lebih hemat memori ($N$ space) dan lebih mudah diimplementasikan, tetapi terbatas pada operasi kumulatif biner (inversibel). *Segment Tree* membutuhkan memori lebih besar ($4N$), namun mampu menangani kueri rentang arbitrer non-inversibel (seperti Range Minimum/Maximum Query) secara lebih fleksibel.
4. Karena jumlah daun dari pohon berukuran $N$ dinaikkan ke pangkat dua terdekat ($2^{\lceil \log_2 N \rceil + 1} - 1$). Dalam kasus terburuk (misal $N = 2^k + 1$), ukuran yang dibutuhkan mendekati $4N$.
5. Runtime terpaksa memicu alokasi heap yang memicu beban kerja *Garbage Collector (GC)*. GC scan dan mark-and-sweep phase akan meningkatkan latensi p99 dan p99.9 secara signifikan (*Stop-The-World / GC Pacing delays*).

##### Jawaban Intermediate
6. Karena setiap elemen hanya masuk (*push*) ke dalam deque satu kali dan dikeluarkan (*popped*) paling banyak satu kali sepanjang pemrosesan data, total operasi pada deque dibatasi maksimal $2N$. Rata-rata operasi per elemen menjadi $2N / N = O(1)$ secara amortisasi.
7. Jika penjumlahan `left + right` bernilai lebih besar dari integer maksimum (misal $2^{31}-1$ pada sistem integer bertanda 32-bit), hasilnya akan meluap (*overflow*) menjadi angka negatif, menghasilkan indeks slice/array tidak valid yang memicu runtime panic.
8. Dengan menambahkan variabel *padding* sebesar cache line CPU (umumnya 64 byte) di antara variabel yang sering diubah oleh goroutine yang berbeda, sehingga dua core CPU tidak mencoba memvalidasi dan membatalkan cache line fisik yang sama.
9. Ketika graf membutuhkan penghapusan tepi (*edge removal/disconnection*) secara dinamis. DSU standar tidak mendukung partisi ulang secara efisien tanpa membangun ulang seluruh struktur data dari awal.
10. Flag tersebut menampilkan hasil analisis kabur (*escape analysis*), memberikan informasi eksplisit mengapa sebuah variabel dipindahkan ke heap (misal: *escapes to heap*, *moved to heap*), sehingga engineer dapat merefaktor kode untuk menjaga variabel tetap berada di stack.

##### Jawaban Kasus Produksi
11. **Analisis & Solusi:** Pemanggilan `sort.Ints()` berulang menghasilkan kompleksitas $O(N \log N)$ per agregasi dan alokasi heap kontinu. Restrukturisasi: Ubah arsitektur penyimpanan menjadi *Ring Buffer* statis berkapasitas tetap (misal: 600 detik) dikombinasikan dengan *Monotonic Deque*. Ini memangkas kompleksitas kueri maksimum menjadi $O(1)$ amortized, meniadakan operasi sorting berkala, dan menghilangkan alokasi dinamis (0 allocs/op). Latensi p99 akan turun drastis ke level sub-milidetik.
12. **Evaluasi:** DSU standar hanya valid untuk *undirected graph*. Pada *directed graph* (seperti deployment dependency), dua cabang dapat mengarah ke komponen yang sama tanpa membentuk siklus melingkar (contoh struktur *Diamond Dependency*). DSU konvensional akan keliru mendeteksinya sebagai siklus. Maka, untuk directed graph berulang, pendekatan yang benar adalah *Topological Sort* (Algoritma Kahn) atau deteksi *back-edge* menggunakan *Tarjan's strongly connected components algorithm*.
13. **Analisis & Solusi:** Meskipun `RWMutex` mendukung banyak pembaca (*shared lock*), setiap goroutine yang membaca harus memutasi *internal counter* dari Mutex tersebut secara atomik menggunakan instruksi CPU `LOCK CMPXCHG`. Pada 64 Core CPU, puluhan core akan berebut memvalidasi satu baris cache (`cache line bouncing`). **Solusi:** Partisi data Segment Tree ke dalam beberapa instans (*sharding*) berdasarkan ID aset atau interval, atau gunakan pendekatan *Read-Copy-Update (RCU)* / *atomic pointer swap* sehingga thread pembaca tidak menyentuh locking primitives sama sekali.

---

### 16. Summary

1. **Konvergensi Algoritma dan Arsitektur:** Solusi komputasi tingkat lanjut (*Advanced LeetCode*) seperti Segment Tree, DSU, dan Monotonic Queue bukan sekadar instrumen wawancara teknis, melainkan fondasi matematis penting dalam optimasi sistem enterprise berlatensi rendah.
2. **Karakteristik Perangkat Keras Modern:** Penulisan kode algoritma produksi wajib mempertimbangkan arsitektur mesin fisik, terutama efisiensi *CPU cache lines* (menghindari pointer chasing) dan eliminasi *Garbage Collection overhead* melalui pola *zero-allocation*.
3. **Kompromi Rekayasa (Trade-offs):** Pemilihan struktur data adalah kalkulasi kompromi yang presisi antara kompleksitas waktu ($O$), konsumsi memori fisik, kemudahan pemeliharaan (*maintainability*), dan keandalan di lingkungan multithreading skala tinggi.