# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Bab 09:** BAB-09-Materi-Lanjutan

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Mengimplementasikan Struktur Data Lanjutan untuk Skala Terdistribusi:** Menguasai mekanisme internal *Log-Structured Merge-Tree* (LSM-Tree), *Concurrent SkipList*, dan struktur data probabilistik (*Bloom Filter* dan *Count-Min Sketch*) dalam konteks sistem produksi berkinerja tinggi (*high-throughput, low-latency*).
2. **Merancang Struktur Data Bebas Kunci (*Lock-Free Data Structures*):** Mengeliminasi *lock contention* dan *deadlock* pada konkurensi tingkat tinggi menggunakan primitif CPU atomik seperti *Compare-And-Swap* (CAS), *Memory Barriers*, serta mitigasi fenomena *ABA Problem*.
3. **Mengoptimalkan *Cache Locality* dan Efisiensi Memori Tingkat Rendah (*Mechanical Sympathy*):** Merancang tata letak memori yang ramah perangkat keras (*Hardware Cache-Friendly Layout*), meminimalkan *cache misses* (L1/L2/L3), dan mencegah *false sharing* pada arsitektur multi-core (NUMA-aware).
4. **Mengevaluasi dan Menangani *Trade-offs* Arsitektural Ekstrem:** Mengukur secara matematis dan empiris *Write Amplification Factor* (WAF), *Read Amplification Factor* (RAF), dan *Space Amplification Factor* (SAF) untuk menentukan kompromi terbaik antara latensi P99, penggunaan disk I/O, serta konsumsi memori.

---

## 2. Prerequisite

Sebelum memulai modul ini, Anda diwajibkan telah menguasai:
* **Analisis Kompleksitas Algoritma Lanjutan:** Pemahaman mendalam terkait amortisasi ($O(1)$ amortized), Master Theorem, dan analisis probabilitas acak.
* **Primitif Sistem Operasi & Arsitektur Komputer:** *Virtual Memory*, *Paging*, *Memory-Mapped Files* (`mmap`), *TLB cache*, *CPU pipelines*, dan hierarki memori (Registers $\to$ L1/L2/L3 $\to$ RAM $\to$ NVMe SSD).
* **Konkurensi Tingkat Rendah:** Thread safety, *race conditions*, *mutex locks*, *read-write locks*, dan model memori (*Memory Consistency Models*: Sequential Consistency vs Acquire-Release semantics).
* **Bahasa Pemrograman Tingkat Sistem:** Kemampuan membaca dan menulis kode dalam bahasa yang mengekspos manajemen memori dan konkurensi eksplisit (contoh: Go, C++, atau Rust). Kode dalam modul ini menggunakan **Go** dengan primitif `sync/atomic` dan manipulasi *slice/pointer* tingkat lanjut.

---

## 3. Concept & Internal Architecture (Mendalam)

Implementasi struktur data pada skala enterprise menuntut pergeseran paradigma dari *pure algorithmic optimality* (hanya berfokus pada Big-O abstrak) menuju *hardware-mechanical efficiency* (bagaimana struktur data dieksekusi di atas silikon CPU, bus memori, dan storage controller).

```
+-----------------------------------------------------------------------------------+
|                         Enterprise In-Memory Engine Layer                         |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [Ingestion Layer]               [Lock-Free Concurrent Layer]                     |
|         │                                     │                                   |
|         ▼                                     ▼                                   |
|  +--------------+                   +--------------------+                        |
|  |  Write-Ahead | (Append-Only)     | Concurrent SkipList|                        |
|  |  Log (WAL)   | ═════════════════>| MemTable           | (O(log n) CAS-based)   |
|  +--------------+                   +--------------------+                        |
|                                               │                                   |
|                                      Flush via Compactor                          |
|                                               │                                   |
|  [Disk Storage Layer]                         ▼                                   |
|  +─────────────────────────────────────────────────────────────────────────────+  |
|  | SSTable (Sorted String Table) Format                                        |  |
|  |  +--------------------+--------------------------------+-----------------+  |  |
|  |  | Bloom Filter Block | Index Block (Sparse Index)     | Data Blocks     |  |  |
|  |  | (SIMD-accelerated) | (Offset / Key Ranges)          | (Compressed KV) |  |  |
|  |  +--------------------+--------------------------------+-----------------+  |  |
|  +─────────────────────────────────────────────────────────────────────────────+  |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### 3.1. Problem Penulisan Acak vs. Sekuensial pada Storage Subsystems
B-Tree standar (digunakan oleh PostgreSQL, MySQL InnoDB) memutasi blok data langsung di tempat (*in-place update*). Pada arsitektur NVMe SSD modern, operasi *random write* memicu fenomena internal *Flash Translation Layer* (FTL) bernama *Write Amplification*, menyebabkan *garbage collection* agresif di tingkat kontroler SSD, *tail latency* P999 melonjak, dan memperpendek umur pakai perangkat (*drive wear*).

Sebaliknya, **Log-Structured Merge-Tree (LSM-Tree)** mentransformasi semua operasi penulisan (*Write, Update, Delete*) menjadi penulisan sekuensial murni (*append-only*). 

### 3.2. Komponen Inti LSM-Tree Modern
1. **MemTable (In-Memory Buffer):** Struktur data dinamis terurut di dalam RAM. Pendekatan konvensional menggunakan Red-Black Tree yang dilindungi oleh `Mutex` atau `RWMutex`. Namun, pada throughput $\ge 1.000.000\text{ ops/sec}$, *lock contention* mendominasi siklus CPU. Solusi enterprise: **Concurrent Lock-Free SkipList** berbasis CAS.
2. **Write-Ahead Log (WAL):** Log penulisan sekuensial linear ke media non-volatile untuk menjamin *durability* (ACID properties) sebelum mutasi dimasukkan ke MemTable.
3. **Immutable MemTable:** Saat MemTable mencapai kapasitas kritis (misal: 64 MB), statusnya diubah menjadi *read-only*, dan MemTable baru dialokasikan untuk melayani penulisan baru secara mulus (*zero-downtime*).
4. **SSTable (Sorted String Table):** Representasi persisten di media disk. Terdiri dari *Data Blocks* berukuran tetap (misal: 4KB - 64KB), *Index Block* (indeks sparse untuk pencarian biner cepat), dan *Bloom Filter* tersemat untuk menyaring pembacaan kunci yang tidak eksis tanpa menyentuh disk I/O.
5. **Compaction Engine:** Proses asinkron di *background* yang menggabungkan (*merge-sort*) beberapa SSTable lama, menghapus duplikasi data historis, membuang data yang ditandai *tombstone* (dihapus), dan menata ulang level penyimpanan guna mengendalikan *Read Amplification*.

### 3.3. Algoritma Lock-Free Menggunakan Compare-And-Swap (CAS)
Operasi *lock-free* menjamin setidaknya satu *thread* mengalami kemajuan (*system-wide progress*) dalam sejumlah langkah terbatas tanpa memblokir thread lain.

Primitif atomik fundamental yang digunakan adalah instruksi mesin `CMPXCHG` pada arsitektur x86-64 atau `LDREX/STREX` (Load-Link/Store-Conditional) pada ARM64:
$$\text{CAS}(P, \text{oldValue}, \text{newValue}) \to \text{bool}$$
Jika nilai pada alamat memori $P$ sama dengan $\text{oldValue}$, perbarui menjadi $\text{newValue}$ dan kembalikan `true`. Jika tidak (terjadi interferensi oleh *thread* lain), batalkan operasi dan kembalikan `false`.

#### The ABA Problem
*Thread* 1 membaca nilai $A$. Penjadwal CPU beralih ke *Thread* 2 yang mengubah $A \to B \to A$. Saat *Thread* 1 melanjutkan, ia mengeksekusi $\text{CAS}(P, A, C)$ yang sukses, padahal struktur semantik internal telah berubah secara fundamental. 
**Mitigasi Produksi:** *Tagged Pointer* / *Versioned References* (mengikat pointer dengan versi integer inkremental 64-bit) atau strategi manajemen memori aman seperti *Hazard Pointers* dan *Epoch-Based Reclamation (EBR)*.

---

## 4. Why & What

| Dimensi | B-Tree (Tradisional) | LSM-Tree (Arsitektur Produksi Skala Luas) |
| :--- | :--- | :--- |
| **Pola Mutasi Disk** | *In-place Updates* (Penulisan Acak). | *Append-Only Logging* (Penulisan Sekuensial). |
| **Throughput Penulisan**| Rendah ke Menengah ($\approx 10^3 - 10^4$ IOPS per node pada drive mekanik/SSD). | Sangat Tinggi ($\approx 10^5 - 10^7$ IOPS via buffer terurut di RAM). |
| **Throughput Pembacaan** | Optimal ($O(\log N)$ langsung via 1-3 lompatan indeks). | Terdegradasi ($O(\log N)$ per level tanpa optimasi). |
| **Kebutuhan Akselerasi**| Tidak kritis (struktur *read-optimized* bawaan). | Wajib: *Bloom Filters* & *Sparse Indexes* untuk memangkas *disk reads*. |
| **Overhead Sistem** | *Buffer Pool Management* kompleks, *locking* halaman (*page latching*). | *Compaction threads* membutuhkan alokasi CPU dan I/O *bandwidth* tersendiri. |
| **Kasus Penggunaan Utama**| RDBMS (OLTP konvensional), sistem e-commerce standar. | Time-series, High-Frequency Trading, NoSQL (RocksDB, Cassandra, Bigtable). |

### Mengapa Membutuhkan Lock-Free SkipList Dibanding Red-Black Tree?
Menyeimbangkan kembali (*rebalancing*) Red-Black Tree (rotasi kiri/kanan) mengubah topologi beberapa node secara bersamaan. Mengisolasi operasi rotasi multi-node secara *lock-free* membutuhkan algoritma yang sangat kompleks dan tidak efisien. 

Sebaliknya, **SkipList** mendasarkan strukturnya pada prinsip probabilitas. Mutasi elemen hanya memengaruhi *node* lokal dan penunjuk (*pointer*) tetangga horizontalnya. Hal ini memungkinkan integrasi primitif atomik CAS secara efisien dengan latensi P99 yang stabil di bawah konkurensi ribuan *goroutines/threads*.

---

## 5. How (Workflow Detail)

Berikut adalah *state machine* dan alur eksekusi mutasi serta pembacaan data pada engine penyimpanan berbasis LSM-Tree modern:

### 5.1. Alur Operasi Penulisan (`Put / Delete`)
```
[Client Request]
       │
       ▼
1. Append to Write-Ahead Log (WAL) ── (fsync: periodic/strict)
       │
       ▼
2. CAS-insert into Concurrent SkipList (Active MemTable)
       │
       ├──[Ukuran MemTable < Threshold?] ──> Return Success
       │
       └──[Ukuran MemTable >= Threshold]
               │
               ▼
       3. Freeze Active MemTable ──> Mark as Immutable MemTable
       4. Allocate New Active MemTable & New WAL Segment
       5. Trigger Background Flusher
               │
               ▼
       6. Serialize Immutable MemTable into SSTable Level-0
          ├── Build In-Memory Bloom Filter Block
          ├── Construct Index Block
          └── Write Sequential Data Blocks to Disk
       7. Discard Old WAL Segment & Reclaim Memory
```

### 5.2. Alur Operasi Pembacaan (`Get`)
```
[Client Request: Key "user_98124"]
       │
       ▼
1. Query Active MemTable (Lock-Free SkipList)
   ├── [Ditemukan?] ──> Kembalikan Nilai
   └── [Tidak Ditemukan]
            │
            ▼
2. Query Immutable MemTables (jika ada antrean flush)
   ├── [Ditemukan?] ──> Kembalikan Nilai
   └── [Tidak Ditemukan]
            │
            ▼
3. Iterasi SSTables dari Level Terendah (L0) ke Level Tertinggi (Ln)
   ├── Evaluasi Bloom Filter untuk SSTable tersebut
   │     ├── [Negatif / Not Present] ──> LEWATI SSTable (Nol Disk I/O)
   │     └── [Positif / Maybe Present]
   │               │
   │               ▼
   ├── Buka Index Block (Binary Search di memori terindeks)
   │     └── Cari Data Block yang memuat kandidat Key
   │               │
   │               ▼
   ├── Baca Data Block dari disk / Block Cache
   └── [Key Ditemukan?]
         ├── Nilai adalah "Tombstone" ──> Return NotFound
         └── Nilai valid ──> Kembalikan Nilai
```

---

## 6. Analogy & Diagram ASCII

### Analogi Operasional: Kantor Notaris Modern
* **Write-Ahead Log (WAL):** Buku harian kasir. Setiap transaksi dicatat secara kronologis secepat kilat pada selembar kertas berurutan tanpa peduli urutan abjad nasabah.
* **MemTable (Concurrent SkipList):** Papan tulis magnetik pintar. Seorang asisten memindahkan nama-nama transaksi dari buku kasir ke papan tulis magnetik, menyusunnya rapi sesuai urutan abjad. Karena menggunakan penunjuk magnet individual, beberapa staf dapat menempelkan nama sekaligus tanpa saling menyenggol.
* **Immutable MemTable & Flushing:** Ketika papan tulis magnetik penuh, papan tersebut difoto dan dikunci (tidak boleh diubah lagi), lalu digantungkan papan baru.
* **SSTable:** Album arsip jilid tahunan di lemari besi. Isinya terurut rapi, dijilid mati (*immutable*).
* **Bloom Filter:** Daftar label ringkas di bagian luar sampul album: *"Album ini PASTI TIDAK memuat nasabah dengan awalan huruf Z"*. Notaris tidak perlu membuang energi membuka 500 halaman album hanya untuk mencari nama yang memang tidak ada.
* **Compaction:** Pada akhir kuartal, notaris menyatukan beberapa album tipis menjadi satu ensiklopedia besar yang padat, membuang catatan pembatalan (*tombstones*) dan duplikasi historis.

### Diagram Representasi Memori: Lock-Free SkipList Node Layout

```
Level 3:  [Head] ------------------------------> [Key: 25] ------------------------------> NIL
             │                                       │
Level 2:  [Head] -------------> [Key: 10] ------> [Key: 25] -------------> [Key: 42] -----> NIL
             │                     │                 │                       │
Level 1:  [Head] -> [Key: 05] -> [Key: 10] ------> [Key: 25] -> [Key: 30] -> [Key: 42] -----> NIL
             │         │           │                 │           │           │
Level 0:  [Head] -> [Key: 05] -> [Key: 10] -> [Key: 18] -> [Key: 25] -> [Key: 30] -> [Key: 42] -> NIL
             │
             ▼
        [Data Ptr] -> Pointer ke Payload Aktual (Value, Timestamp, Flags)
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Concept: Murmur3-Based Bloom Filter
Implementasi *Bloom Filter* menggunakan bitset dan *hashing* ganda (*double hashing*) Kirsch-Mitzenmacher: $g_i(x) = h_1(x) + i \cdot h_2(x) \pmod m$ untuk meminimalkan *hash calculation overhead*.

```go
package main

import (
	"encoding/binary"
	"fmt"
	"math"
)

// BloomFilter merepresentasikan struktur data probabilistik hemat memori.
type BloomFilter struct {
	bitset []uint64
	size   uint64 // Total bit
	k      uint8  // Jumlah hash function
}

// NewBloomFilter menginisialisasi filter dengan kapasitas elemen dan toleransi false positive.
func NewBloomFilter(expectedElements uint64, falsePositiveRate float64) *BloomFilter {
	// Formula matematis: m = - (n * ln(p)) / (ln(2)^2)
	m := uint64(math.Ceil(-float64(expectedElements) * math.Log(falsePositiveRate) / math.Pow(math.Log(2), 2)))
	// Formula: k = (m / n) * ln(2)
	k := uint8(math.Round(float64(m) / float64(expectedElements) * math.Log(2)))

	words := (m + 63) / 64
	return &BloomFilter{
		bitset: make([]uint64, words),
		size:   words * 64,
		k:      k,
	}
}

// hash memetakan byte payload menjadi dua representasi 64-bit menggunakan teknik FNV-1a basis ganda
func (bf *BloomFilter) hash(data []byte) (uint64, uint64) {
	const offset64 = 14695981039346656037
	const prime64 = 1099511628211

	h1 := uint64(offset64)
	for _, b := range data {
		h1 ^= uint64(b)
		h1 *= prime64
	}

	// Secondary hash derived via byte reversal & bit mixing
	h2 := (h1 >> 32) | (h1 << 32)
	h2 = h2*prime64 ^ offset64
	return h1, h2
}

// Add menyisipkan kunci ke dalam filter
func (bf *BloomFilter) Add(key []byte) {
	h1, h2 := bf.hash(key)
	for i := uint8(0); i < bf.k; i++ {
		combined := (h1 + uint64(i)*h2) % bf.size
		wordIdx := combined / 64
		bitIdx := combined % 64
		bf.bitset[wordIdx] |= (1 << bitIdx)
	}
}

// MayContain menguji probabilitas keberadaan kunci.
// Menjamin: False Negative = 0% (Jika false, elemen PASTI tidak ada).
func (bf *BloomFilter) MayContain(key []byte) bool {
	h1, h2 := bf.hash(key)
	for i := uint8(0); i < bf.k; i++ {
		combined := (h1 + uint64(i)*h2) % bf.size
		wordIdx := combined / 64
		bitIdx := combined % 64
		if (bf.bitset[wordIdx] & (1 << bitIdx)) == 0 {
			return false // Pasti tidak ada
		}
	}
	return true // Kemungkinan besar ada
}

func main() {
	bf := NewBloomFilter(1000000, 0.01) // 1 Juta elemen, 1% False Positive Target
	key := []byte("session_token:abc-9923-xyz")

	bf.Add(key)
	fmt.Printf("May contain key: %v\n", bf.MayContain(key))
	fmt.Printf("May contain nonexistent: %v\n", bf.MayContain([]byte("session_token:unknown")))
}
```

---

### 7.2. Practical Example: Lock-Free Concurrent SkipList MemTable
Implementasi *production-ready* memtable berbasis *atomic operations* (`sync/atomic`) yang mengimplementasikan CAS array pointer berjenjang (*level pointer slices*).

```go
package main

import (
	"bytes"
	"math/rand"
	"sync/atomic"
	"time"
	"unsafe"
)

const (
	MaxLevel    = 16
	Probability = 0.5
)

type Node struct {
	key       []byte
	value     unsafe.Pointer // *[]byte
	forward   []unsafe.Pointer // []*Node dipetakan secara atomic
	nodeLevel int
}

func newNode(key []byte, val []byte, level int) *Node {
	vPtr := unsafe.Pointer(&val)
	n := &Node{
		key:       key,
		value:     vPtr,
		forward:   make([]unsafe.Pointer, level),
		nodeLevel: level,
	}
	return n
}

func (n *Node) getForward(level int) *Node {
	return (*Node)(atomic.LoadPointer(&n.forward[level]))
}

func (n *Node) casForward(level int, oldNode, newNode *Node) bool {
	return atomic.CompareAndSwapPointer(
		&n.forward[level],
		unsafe.Pointer(oldNode),
		unsafe.Pointer(newNode),
	)
}

// ConcurrentSkipList merepresentasikan MemTable bebas kunci.
type ConcurrentSkipList struct {
	head  *Node
	level int64 // Atomic int64
	rnd   *rand.Rand
}

func NewConcurrentSkipList() *ConcurrentSkipList {
	head := newNode(nil, nil, MaxLevel)
	return &ConcurrentSkipList{
		head:  head,
		level: 1,
		rnd:   rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

func (s *ConcurrentSkipList) randomLevel() int {
	lvl := 1
	for lvl < MaxLevel && rand.Float64() < Probability {
		lvl++
	}
	return lvl
}

// Put melakukan mutasi tanpa alokasi Global Mutex.
func (s *ConcurrentSkipList) Put(key []byte, value []byte) bool {
	var update [MaxLevel]*Node
	current := s.head

	// Phase 1: Search predecessor nodes di setiap level
	for i := int(atomic.LoadInt64(&s.level)) - 1; i >= 0; i-- {
		for {
			next := current.getForward(i)
			if next == nil || bytes.Compare(next.key, key) >= 0 {
				break
			}
			current = next
		}
		update[i] = current
	}

	// Periksa apakah key sudah eksis di Level 0 (In-place Atomic Value Replacement)
	target := current.getForward(0)
	if target != nil && bytes.Equal(target.key, key) {
		valPtr := unsafe.Pointer(&value)
		for {
			oldVal := atomic.LoadPointer(&target.value)
			if atomic.CompareAndSwapPointer(&target.value, oldVal, valPtr) {
				return true
			}
		}
	}

	// Phase 2: Inserksi Node Baru
	lvl := s.randomLevel()
	currMaxLevel := int(atomic.LoadInt64(&s.level))
	if lvl > currMaxLevel {
		for i := currMaxLevel; i < lvl; i++ {
			update[i] = s.head
		}
		// Coba perbarui level struktur skip list secara atomic
		atomic.CompareAndSwapInt64(&s.level, int64(currMaxLevel), int64(lvl))
	}

	node := newNode(key, value, lvl)

	// Phase 3: CAS Splice Pointer dari level 0 ke atas
	for i := 0; i < lvl; i++ {
		for {
			pred := update[i]
			succ := pred.getForward(i)
			node.forward[i] = unsafe.Pointer(succ)

			// Upayakan atomic linking
			if pred.casForward(i, succ, node) {
				break // Link berhasil pada level ini, naik ke level selanjutnya
			}

			// Konflik terdeteksi: Re-scan predecessor untuk level 'i'
			current = s.head
			for {
				next := current.getForward(i)
				if next == nil || bytes.Compare(next.key, key) >= 0 {
					break
				}
				current = next
			}
			update[i] = current
		}
	}

	return true
}

// Get membaca key dengan zero-lock interference (Murni pointer-traversal).
func (s *ConcurrentSkipList) Get(key []byte) ([]byte, bool) {
	current := s.head
	for i := int(atomic.LoadInt64(&s.level)) - 1; i >= 0; i-- {
		for {
			next := current.getForward(i)
			if next == nil || bytes.Compare(next.key, key) > 0 {
				break
			}
			if bytes.Equal(next.key, key) {
				valPtr := atomic.LoadPointer(&next.value)
				if valPtr == nil {
					return nil, false
				}
				return *(*[]byte)(valPtr), true
			}
			current = next
		}
	}

	target := current.getForward(0)
	if target != nil && bytes.Equal(target.key, key) {
		valPtr := atomic.LoadPointer(&target.value)
		if valPtr == nil {
			return nil, false
		}
		return *(*[]byte)(valPtr), true
	}

	return nil, false
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Arsitektur Ultra-Low Latency Order Book (Fintech Tier-1)
* **Konteks:** Sistem perdagangan saham dan derivatif kripto dengan beban ingestion puncak $1.200.000\text{ matching events/detik}$ per cluster node.
* **Problem Statement:** Implementasi awal menggunakan penyimpanan berbasis Redis dan Postgres RDS menghasilkan lonjakan latensi P99 hingga $48\text{ ms}$ pada jam pembukaan pasar (*market opening*). Investigasi menemukan bahwa B-Tree disk write locks dan mekanisme sinkronisasi database relasional konvensional mengalami *buffer pool contention*.
* **Solusi Arsitektur Menggunakan Advanced Data Structures:**
  1. **Core Matching Engine:** Mengadopsi **Lock-Free Ring Buffer (LMAX Disruptor Pattern)** yang beroperasi langsung di atas CPU cache L3 dengan *cache-line padding* untuk mengeliminasi *false sharing*.
  2. **Audit Logging & Event Store:** Mengganti layer audit database dengan implementasi **LSM-Tree Custom Engine**.
     * Data mutasi divalidasi dan dicatat langsung ke NVMe drive menggunakan WAL (`O_DIRECT`, membypass Linux Page Cache).
     * MemTable dikelola menggunakan **Concurrent SkipList** yang dialokasikan di atas *HugePages* (halaman memori 2MB) guna mengeliminasi penalti *TLB Cache Misses*.
     * Pembacaan status posisi akun historis diakselerasi dengan **Blocked Bloom Filters (Cache-Sector Bloom Filters)** berukuran 64-byte yang selaras persis dengan ukuran CPU cache line x86.
* **Hasil Metrik Produksi:**
  * Throughput ingestion melonjak dari $85.000\text{ tx/s}$ menjadi $1.450.000\text{ tx/s}$.
  * Latensi P99 ditekan secara dramatis dari $48\text{ ms}$ menjadi $180\ \mu\text{s}$ (mikrodetik).
  * Degradasi penulisan SSD turun drastis (WAF ditekan dari $28.4$ menjadi $3.1$).

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

Dalam rekayasa sistem penyimpanan enterprise, setiap keputusan struktural dibatasi oleh **Teorema RUM Conjecture** (*Read, Update, Memory/Space Overhead Trade-off*):

```
                     Read Amplification (RAF)
                             ▲
                            / \
                           /   \
                          /     \
                         /  LSM  \
                        /  Space  \
                       /   Trade   \
                      /             \
                     /_______________\
Write Amplification (WAF)             Space Amplification (SAF)
```

1. **Write Amplification Factor (WAF):**
   * *Formula:* $\text{WAF} = \frac{\text{Total Bytes Written to Storage Media}}{\text{Total Bytes Ingested by Application}}$.
   * *Trade-off:* Memperkecil latensi tulis LSM-Tree meningkatkan WAF saat *Compaction* berjalan. Jika proses *Compaction* (Leveled Compaction) berjalan terlalu agresif demi mempertahankan kecepatan baca, WAF melonjak hingga $\times 30$, yang dapat mengikis bandwidth write I/O SSD secara permanen.
2. **Read Amplification Factor (RAF):**
   * *Trade-off:* LSM-Tree mengorbankan performa baca tunggal titik (*Point Lookup*) karena pencarian harus menelusuri MemTable dan beberapa layer SSTable. Tanpa alokasi RAM yang cukup untuk *Bloom Filters* dan *Block Cache*, RAF dapat mencapai nilai puluhan *disk seeks* per pembacaan.
3. **Space Amplification Factor (SAF):**
   * *Trade-off:* Selama proses *Size-Tiered Compaction*, sistem membutuhkan kapasitas disk cadangan hingga $100\%$ dari ukuran data aktual hanya untuk melakukan penggabungan sementara (*temporary merge space*).
4. **Alokasi Sumber Daya & Finansial (Cost Implications):**
   * Pilihan menggunakan struktur bebas kunci (*Lock-Free*) menurunkan latensi P99, namun meningkatkan utilisasi siklus CPU saat *high-contention* karena thread melakukan *CAS busy-spinning loop* alih-alih *sleeping* via OS scheduler primitives.

---

## 10. Common Mistakes & Troubleshooting

### 1. False Sharing pada Struktur Data Konkuren Multi-Core
* **Gejala:** Utilisasi CPU mendekati 100% pada sistem dengan 32+ core, namun throughput konkurensi stagnan atau justru turun secara signifikan dibanding eksekusi single-thread.
* **Penyebab:** Dua variabel berbeda yang dimutasi secara independen oleh dua CPU core terpisah berada pada baris cache (*cache line*) yang sama (biasanya berukuran 64 bytes). Setiap kali Core A menulis ke variabelnya, kontroler cache hardware memvalidasi ulang seluruh baris cache milik Core B melalui protokol *cache coherency* (MESI).
* **Solusi Produksi:** Gunakan *cache line padding* eksplisit.
  ```go
  type WorkerStats struct {
      SuccessCount uint64
      _pad1        [7]uint64 // 56 bytes padding to complete 64-byte cache line
      FailureCount uint64
      _pad2        [7]uint64 // Prevents adjacent cache line bouncing
  }
  ```

### 2. Memory Leak Akibat Tombstone Accumulation
* **Gejala:** Latensi operasi `Scan()` / *Range Queries* membengkak secara eksponensial; ukuran disk tidak berkurang meskipun aplikasi telah menghapus jutaan record.
* **Penyebab:** Pada arsitektur LSM-Tree, penghapusan (`Delete`) adalah operasi penulisan marker *Tombstone*. Jika *compaction* jarang dipicu pada level tertua, iterator harus membaca dan menolak jutaan marker *tombstone* ini satu per satu di dalam memori.
* **Solusi Produksi:** Terapkan konfigurasi *Tombstone-Aware Compaction* yang memprioritaskan pembersihan SSTable dengan rasio *tombstone-to-live-keys* tinggi.

---

## 11. Best Practices (Production Checklist)

Berikut adalah daftar periksa teknis sebelum merilis sistem berbasis struktur data tingkat lanjut ke lingkungan produksi:

- [ ] **Alignment & Padding:** Struktur data yang sering dimutasi konkruen telah diberi padding sebesar kelipatan 64-bit/64-byte untuk mencegah *False Sharing*.
- [ ] **Zero-Allocation Data Paths:** Alur kritis pemrosesan (*hot paths*) bebas dari alokasi memori dinamis (`malloc` / heap escapes) dengan memanfaatkan *Object Pools* (`sync.Pool`).
- [ ] **Memory-Mapped I/O Boundaries:** Akses disk file SSTable menggunakan batas `mmap` aman, dan proteksi sinyal `SIGBUS` ditangani jika media disk mengalami I/O failure.
- [ ] **Bloom Filter Tuning:** Ukuran bitset dan jumlah hash function dihitung spesifik menggunakan distribusi Poisson untuk menargetkan probabilitas False Positive $\le 1\%$.
- [ ] **Graceful Flush Lifecycles:** Mekanisme *backpressure* aktif secara otomatis jika laju ingestion MemTable melampaui kemampuan laju *Flush* dan *Compaction disk*.
- [ ] **Sanitizer Verification:** Kode konkuren telah lolos pengujian menggunakan `-race` detector (Go) atau *ThreadSanitizer (TSan)* di bawah beban integrasi minimum 10.000 thread acak.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah modul indeks memori performa tinggi berarsitektur LSM mini secara bertahap pada direktori repositori Anda.

### Persiapan Direktori
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
go mod init enterprise-storage-core
```

### Langkah 1: Buat Engine Sparse Indexer
Buat berkas `sparse_index.go`. Indeks ini bertugas memetakan offset file secara presisi setiap interval blok tertentu tanpa memuat seluruh key ke memori RAM:

```go
package main

import (
	"bytes"
	"errors"
)

type IndexEntry struct {
	Key    []byte
	Offset int64
}

type SparseIndex struct {
	entries []IndexEntry
}

func NewSparseIndex() *SparseIndex {
	return &SparseIndex{entries: make([]IndexEntry, 0)}
}

func (si *SparseIndex) Add(key []byte, offset int64) {
	si.entries = append(si.entries, IndexEntry{Key: key, Offset: offset})
}

// FindFloorEntry mencari rentang offset awal blok menggunakan pencarian biner
func (si *SparseIndex) FindFloorEntry(key []byte) (int64, error) {
	if len(si.entries) == 0 {
		return 0, errors.New("index is empty")
	}

	low, high := 0, len(si.entries)-1
	resultIdx := -1

	for low <= high {
		mid := low + (high-low)/2
		cmp := bytes.Compare(si.entries[mid].Key, key)

		if cmp <= 0 {
			resultIdx = mid
			low = mid + 1 // Coba cari yang lebih mendekati di sisi kanan
		} else {
			high = mid - 1
		}
	}

	if resultIdx == -1 {
		return si.entries[0].Offset, nil
	}
	return si.entries[resultIdx].Offset, nil
}
```

### Langkah 2: Verifikasi Fungsionalitas
Buat file `main.go` untuk menguji pemetaan binary indexing:

```go
package main

import "fmt"

func main() {
	idx := NewSparseIndex()
	idx.Add([]byte("apple"), 0)
	idx.Add([]byte("grape"), 4096)
	idx.Add([]byte("orange"), 8192)
	idx.Add([]byte("watermelon"), 12288)

	offset, err := idx.FindFloorEntry([]byte("mango"))
	if err != nil {
		panic(err)
	}

	// Mango berada di antara "grape" (4096) dan "orange" (8192)
	// Sparse Index harus mengarahkan pembacaan ke blok "grape" (offset 4096)
	fmt.Printf("Search Key: 'mango' -> Read target block offset: %d\n", offset)
}
```

Uji program Anda:
```bash
go run .
```

---

## 13. Exercise

### Level Easy: Probabilistic Hit Counter
Implementasikan struktur data **Count-Min Sketch** berukuran tetap yang menggunakan array 2D integer dengan 4 fungsi hash independen untuk menghitung perkiraan frekuensi kemunculan key pada stream data tanpa menyimpan key itu sendiri.
* *Constraint:* Memori maksimal dibatasi pada 16 KB.

### Level Medium: Lock-Free Stack (Treiber Stack) dengan ABA Hazard Mitigation
Rancang dan implementasikan struktur data **Treiber Stack** berbasis CAS atomik di Go.
* *Constraint:* Sediakan mitigasi mutlak terhadap fenomena *ABA problem* menggunakan modifikasi skema manipulasi bit `uintptr` (Packed Pointer + 32-bit Version Counter dalam satu kata mesin 64-bit).

### Level Hard: Dynamic SSTable Block Merger
Bangun sebuah algoritma penggabung (*K-Way Merge Engine*) yang menerima *array of file descriptors* dari 5 SSTable berbeda yang masing-masing berisi pasangan key-value terurut. 
* *Constraint:* Algoritma harus mengeksekusi merge-sort menggunakan **Min-Heap**, membuang key duplikat secara efisien (mengambil versi payload dengan timestamp terbaru), dan menulis output ke file baru secara streaming dengan alokasi heap RAM konstan $O(K)$, tanpa memuat seluruh isi file ke RAM.

---

## 14. Challenge

### Studi Kasus: High-Contention In-Memory Rate Limiter Engine
**Deskripsi Skenario Kasus Riil:**
Sebuah payment gateway internasional memproses otorisasi transaksi dengan SLA latensi API global $< 10\text{ ms}$. Anda ditugaskan membangun engine in-memory rate limiter terpusat per node mesin (skala bare-metal 128 core CPU, 512GB RAM) yang menangani identifikasi token API unik.

**Ketentuan & Batasan Teknis:**
1. Engine harus mampu melayani minimal $2.500.000\text{ lookup/updates per detik}$ untuk batas sliding window 1 menit.
2. Tidak diperbolehkan menggunakan mutex global maupun primitif `sync.RWMutex` sama sekali pada hot path pemrosesan transaksi. Mutex lock contention diidentifikasi akan menggagalkan SLA latensi tail P999.
3. Struktur data harus mempertahankan penggunaan memori yang stabil (tidak boleh terjadi *out-of-memory* akibat penumpukan data pelanggan lama yang sudah tidak aktif).
4. Buat arsitektur, pemilihan struktur data, dan analisis layout memori tingkat rendah untuk solusi tersebut.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (Basic)
1. Mengapa operasi penulisan sekuensial (*Sequential Write*) pada NVMe SSD modern memiliki kecepatan operasi dan daya tahan perangkat yang jauh lebih tinggi dibanding penulisan acak (*Random Write*)?
2. Berikan formula matematis standar untuk menghitung jumlah fungsi hash optimal ($k$) pada *Bloom Filter* berdasarkan ukuran bit ($m$) dan jumlah elemen yang diharapkan ($n$)!
3. Apa perbedaan karakteristik algoritmik mendasar antara *SkipList* dan *Red-Black Tree* dalam konteks implementasi konkurensi?
4. Apakah *Bloom Filter* mungkin menghasilkan evaluasi *False Negative*? Jelaskan alasan fundamentalnya!
5. Apa yang dimaksud dengan *Write Amplification Factor* (WAF) pada arsitektur sistem penyimpanan?

### Bagian B: Analisis Mendalam (Intermediate)
6. Jelaskan secara mendalam bagaimana fenomena instruksi CPU *Compare-And-Swap* (CAS) dapat memicu *livelock* atau lonjakan konsumsi daya CPU (*busy-spin saturation*) di bawah kondisi beban konkurensi tinggi!
7. Bagaimana arsitektur *LSM-Tree* menyelesaikan masalah inkonsistensi data ketika sistem operasi mengalami *crash* mendadak sebelum data di MemTable sempat disalin ke SSTable pada media disk?
8. Mengapa algoritma rotasi B-Tree dinilai sangat sulit dan tidak efisien untuk diimplementasikan menggunakan primitif konkurensi murni *Lock-Free*?
9. Jelaskan konsep arsitektur perangkat keras *False Sharing*, dan bagaimana compiler atau insinyur perangkat lunak dapat mencegahnya pada struktur data in-memory!
10. Dalam proses *Compaction* pada LSM-Tree, jelaskan trade-off performa antara strategi *Size-Tiered Compaction Strategy* (STCS) versus *Leveled Compaction Strategy* (LCS)!

### Bagian C: Skenario Kasus Produksi
11. **Skenario 1:** Sebuah sistem logging berbasis LSM-Tree mengalami lonjakan latensi baca (P99 Read Latency) dari $2\text{ ms}$ menjadi $850\text{ ms}$ secara tiba-tiba setelah berjalan selama 3 minggu tanpa henti. Pola penulisan stabil, kapasitas disk terpakai $40\%$, dan metrik utilisasi CPU normal. Analisis letak potensi kegagalan struktur data internalnya dan berikan 2 langkah remediasi konkret!
12. **Skenario 2:** Anda menemukan implementasi *Treiber Stack* (Lock-Free Stack) di lingkungan produksi mengalami *memory corruption* acak saat sistem dialihkan ke server komputasi arsitektur multi-socket multi-core baru. Indikasikan penyebab utama kerusakan data tersebut pada level instruksi mesin dan bagaimana mitigasinya!
13. **Skenario 3:** Tim Anda merancang implementasi *Bloom Filter* yang disematkan langsung di dalam *block header* SSTable disk file. Setelah diuji pada beban baca berskala 500K RPS, pembacaan disk IOPS melonjak tajam padahal kunci yang dicari sebagian besar tidak ada (*non-existent keys*). Apa kesalahan fatal dalam arsitektur penempatan memori Bloom Filter tersebut?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian A: Konsep Dasar
1. SSD menulis data dalam ukuran *Page* (misal 4KB-16KB) namun hanya dapat menghapus dalam ukuran *Block* (berisi ratusan Page). Penulisan acak memicu *Flash Translation Layer* (FTL) melakukan pemindahan blok berulang-ulang (*Garbage Collection Overhead*). Penulisan sekuensial mengisi seluruh *Block* secara linear, meminimalkan erosi sel silikon NAND dan menghilangkan penundaan siklus *erase-before-write*.
2. $k = \frac{m}{n} \ln 2 \approx 0.693 \cdot \frac{m}{n}$.
3. Red-Black Tree mengandalkan penyeimbangan deterministik kaku lewat rotasi pohon multi-node yang mempengaruhi pointer lokal dan global; SkipList menggunakan probabilitas acak geometris (*probabilistic height assignment*) di mana penambahan elemen hanya memodifikasi pointer traversal horizontal lokal yang dapat diisolasi secara atomik via instruksi CAS.
4. **Tidak mungkin.** Sifat matematis Bloom Filter: Jika elemen telah dimasukkan, semua bit pada indeks hash yang bersangkutan pasti telah diset menjadi 1. Evaluasi hanya bernilai negatif jika setidaknya satu bit bernilai 0, yang secara definitif membuktikan elemen tersebut belum pernah dimasukkan.
5. Rasio komparatif antara jumlah byte fisik aktual yang ditulis oleh sistem penyimpanan ke media persisten (SSD/HDD) terhadap jumlah byte logis penulisan yang dikirimkan oleh aplikasi pengguna.

#### Bagian B: Analisis Mendalam
6. Jika ratusan thread mencoba memperbarui pointer yang sama secara bersamaan, hanya 1 thread yang berhasil mengeksekusi instruksi CAS per siklus. Sisanya gagal dan dipaksa mengulang loop (*busy-waiting*). Akibatnya, alih-alih melepaskan inti CPU (*context switch*), CPU terus mengeksekusi instruksi perbandingan tanpa henti pada 100% kapasitas termal tanpa memajukan throughput sistem secara proporsional.
7. Menggunakan *Write-Ahead Log* (WAL). Setiap transaksi penulisan diserialisasi dan di-*flush* ke disk log sekuensial secara sinkron sebelum node SkipList di RAM dimutasi. Saat *crash recovery*, engine membaca ulang seluruh log WAL dari offset checkpoint terakhir dan merekonstruksi state MemTable secara deterministik.
8. Rebalancing B-Tree melibatkan operasi pemisahan halaman (*page splits*) atau penggabungan (*page merges*) yang memodifikasi node anak, node induk, dan mendistribusikan ulang kunci di antara tetangga. Mengamankan multi-pointer updates ini di memori secara atomik tanpa memblokir pembacaan concurrent membutuhkan abstraksi kompleks setingkat *Software Transactional Memory* (STM) yang menimbulkan *overhead* performa sangat besar.
9. *False Sharing* terjadi saat dua variabel pada thread berbeda dipetakan pada baris cache fisik CPU yang sama (64 byte). Protokol koherensi cache hardware (seperti MESI) memaksa invalidasi cache baris tersebut antar-core secara konstan (*cache line bouncing*). Pencegahannya adalah dengan menambahkan variabel padding buatan (*byte padding*) agar struktur data milik thread terpisah berada pada cache line yang terisolasi.
10. **STCS** menggabungkan SSTable berukuran setara; memiliki WAF rendah (bagus untuk write-heavy), namun memiliki SAF tinggi (butuh ruang disk sisa besar) dan RAF tinggi. **LCS** membagi penyimpanan menjadi level terpisah eksponensial di mana tiap level bebas tumpang-tindih kunci (*non-overlapping keys*); menawarkan performa baca luar biasa (RAF rendah) dan SAF rendah, namun dibayar dengan penalti WAF yang sangat tinggi akibat proses merge berulang-ulang di setiap level.

#### Bagian C: Skenario Kasus Produksi
11. **Akar Masalah:** Terjadi *Compaction Stalling* atau akumulasi masif marker penanda *Tombstone* yang tidak tereliminasi karena data jarang ditulis ulang. Iterator pencarian dipaksa membaca jutaan record non-aktif yang memperlambat traversi level SSTable.
    *Langkah Remediasi:*
    * Memicu manual *Major Compaction* terarah pada range partisi data yang bersangkutan.
    * Menurunkan rasio *Tombstone Garbage Collection threshold* dan mengaktifkan optimasi *Dynamic Level Base Byte Sizing* pada LSM engine.
12. **Akar Masalah:** Server baru memiliki arsitektur NUMA/multi-core yang mengekspos instruksi kelemahan konkurensi: *ABA Problem*. Pointer node yang di-*pop* dialokasikan ulang oleh sistem operasi pada alamat memori fisik yang identik sebelum thread lain menyelesaikan instruksi CAS, menyebabkan pointer stack lama merujuk ke data usang atau memori liar.
    *Mitigasi:* Terapkan skema *Pointer Tagging/Version Stamp* (memasukkan monotonic counter ke dalam pointer), atau adopsi algoritma pembersihan memori aman konkuren seperti *Hazard Pointers* atau *Epoch-Based Reclamation* (EBR).
13. **Akar Masalah:** Bloom Filter diletakkan di dalam media disk (header SSTable) dan tidak di-*cache* secara permanen di memori RAM utama.
    *Dampak:* Untuk memverifikasi apakah sebuah kunci **tidak ada** via Bloom Filter, engine terpaksa membaca blok dari media SSD terlebih dahulu. Ini menghilangkan tujuan fundamental Bloom Filter, yaitu memangkas operasi disk I/O.
    *Solusi:* Pindahkan seluruh struktur representasi Bloom Filter ke dalam unevictable *Kernel/Application In-Memory Region* (RAM) saat pertama kali file SSTable dibuka.

---

## 16. Summary

1. **Evolusi Algoritma Mengikuti Karakteristik Perangkat Keras:** Keunggulan performa pada arsitektur modern bergeser dari sekadar optimasi jumlah instruksi Big-O menuju desain yang memprioritaskan *Cache Locality*, akses memori sekuensial, dan penghapusan *Thread Contention*.
2. **LSM-Tree Mendominasi Kebutuhan Ingestion Masif:** Melalui pemisahan memori buffer (*Concurrent SkipList*) dan *append-only immutable storage* (SSTable), LSM-Tree mengoptimalkan penulisan data skala masif dengan meminimalkan *random write overhead* pada storage SSD modern.
3. **Struktur Data Probabilistik Adalah Kunci Efisiensi Skala:** Komponen deterministik murni tidak dapat diskalakan secara linier tanpa batas. *Bloom Filters* dan *Count-Min Sketches* menjadi filter utama yang mengeliminasi komputasi yang tidak perlu sebelum menyentuh layer I/O yang mahal.
4. **Primitif Lock-Free Menghilangkan Bottleneck Konkurensi:** Pemanfaatan operasi atomik CAS dan penataan tata letak data yang bebas dari *false sharing* memungkinkan pembuatan pipeline data throughput tinggi yang mampu menangani jutaan transaksi per detik dengan latensi konsisten pada persentil ekstrem (P99/P999).