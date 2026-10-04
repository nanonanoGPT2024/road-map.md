# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations  
**Topik:** Datastructures-and-Algorithms  
**Bab:** 07 - Materi Lanjutan  

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (C4)** interaksi antara struktur data lanjutan (khususnya *Concurrent Lock-Free Skip List* dan komponen internal *Log-Structured Merge-Tree/LSM-Tree*) dengan arsitektur perangkat keras modern (*CPU cache lines*, *MESI coherence protocol*, dan *memory ordering semantics*).
- **Mengevaluasi (C5)** trade-off performa, konkurensi, dan integritas memori antara struktur data *in-memory cache-conscious* vs. *storage-tiered structures* untuk beban kerja *write-heavy* dan *read-heavy*.
- **Mengimplementasikan (C6)** struktur data konkurensi tingkat lanjut menggunakan operasi atomik primitif (*Compare-And-Swap/CAS*, *Acquire-Release memory orderings*) yang bebas *data race*, terproteksi dari *false sharing*, dan kebal terhadap *ABA problem*.
- **Merancang (C6)** arsitektur sub-sistem storage engine mikro yang menggabungkan *MemTable (Skip List)*, *Write-Ahead Log (WAL)*, dan *SSTable (Sorted String Table)* dengan *Bloom Filter* terindeks untuk skala enterprise.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Arsitektur Komputer Dasar**: Hierarki memori (L1/L2/L3 cache, RAM, NVMe), konsep *Cache Line* (64-byte boundary), *Branch Predictor*, dan *Virtual Memory Paging*.
- **Sistem Operasi & Konkurensi**: Threads, context switching, mutex, deadlock, live-lock, thread starvation, serta konsep dasar memori atomik (*memory barriers/fences*).
- **Struktur Data Fundamental**: Binary Search Trees (BST), Balanced Trees (AVL, Red-Black), Hash Map, Heap, dan disk-oriented indexing (B+ Tree).
- **Kompleksitas Algoritma**: Notasi Big-O (Time & Space complexity), *amortized analysis*, serta batas komputasi $O(1)$, $O(\log N)$, dan $O(N)$.

---

## 3. Concept & Internal Architecture

### 3.1 Hardware-Aware Data Structure Design
Pada sistem perangkat lunak skala enterprise, kompleksitas teoretis $O(1)$ atau $O(\log N)$ sering kali dikalahkan oleh overhead perangkat keras jika struktur data mengabaikan hierarki CPU cache.

```
+--------------------------------------------------------+
|                     CPU Core                           |
|  [Registers] -> [L1 Cache: ~1ns] -> [L2 Cache: ~4ns]  |
+--------------------------------------------------------+
                           |
            [L3 Cache (Shared): ~10-20ns]
                           |
            [Main Memory (DRAM): ~60-100ns]
                           |
            [NVMe SSD Storage: ~10,000-50,000ns]
```

Ketika prosesor membaca alamat memori 8-byte, CPU tidak mengambil 8 byte tersebut secara terisolasi, melainkan menarik satu blok berukuran **64 byte** yang disebut **Cache Line**.
1. **False Sharing**: Terjadi ketika dua thread pada core berbeda memodifikasi variabel independen yang berada pada baris cache 64-byte yang sama. Protokol koherensi cache (seperti MESI: *Modified, Exclusive, Shared, Invalid*) memaksa cache line di-invalidasi antar-core secara terus-menerus (*cache line bouncing*), menghancurkan throughput pemrosesan paralel.
2. **Cache-Conscious Node Alignment**: Struktur data nodus (seperti nodus tree atau linked list) harus dirancang agar pas dalam batasan kelipatan 64-byte menggunakan *explicit memory padding* atau struktur berbasis larik (*unrolled structures*).

### 3.2 Lock-Free Primitives & Memory Model
Sinkronisasi berbasis *mutual exclusion (mutex)* memicu *system call* ke kernel ketika terjadi kontensi, mengakibatkan *thread unscheduling*, pembuangan register (*context switch*), dan latensi hingga satuan mikrodetik. Pemrograman *Lock-Free* menghindari blokade thread dengan memanfaatkan instruksi CPU tingkat mesin:

- **Compare-And-Swap (CAS)**: Operasi atomik instruksi tunggal (misal `CMPXCHG` pada x86-64) yang membandingkan nilai pada lokasi memori dengan nilai yang diharapkan; jika cocok, lokasi tersebut diperbarui ke nilai baru.
- **Memory Consistency Models**:
  - **Sequential Consistency (`SeqCst`)**: Menjamin total urutan eksekusi instruksi global di semua core. Memiliki overhead paling mahal karena memicu *full memory fence*.
  - **Acquire-Release (`Acq/Rel`)**: 
    - Operasi *Store-Release* memastikan semua penulisan memori sebelum instruksi ini terlihat oleh core lain yang melakukan *Load-Acquire*.
    - Operasi *Load-Acquire* memastikan pembacaan memori setelah instruksi ini tidak dapat di-*reorder* mendahului instruksi load itu sendiri.
  - **Relaxed**: Hanya menjamin atomisitas modifikasi variabel itu sendiri, tanpa sinkronisasi urutan memori antar-thread.

### 3.3 Struktur Data Produksi: Concurrent Skip List & LSM Engine
Modul ini membedah dua pilar struktur data modern:
1. **Concurrent Skip List**: Alternatif probabilistik terhadap Red-Black Tree yang sangat ramah terhadap komputasi tanpa kunci (*lock-free*). Operasi rotasi pada Red-Black Tree membutuhkan penguncian multi-nodus yang kompleks, sedangkan Skip List hanya memodifikasi pointer maju (*forward pointers*) yang dapat diselesaikan dengan CAS bertingkat.
2. **Log-Structured Merge-Tree (LSM-Tree)**: Mengubah operasi penulisan acak (*random writes*) disk/SSD menjadi penulisan berurutan (*sequential writes*) dengan memisahkan struktur menjadi:
   - **MemTable**: Buffer in-memory berbasis Skip List.
   - **WAL (Write-Ahead Log)**: Append-only log pada disk untuk durabilitas (*crash recovery*).
   - **Immutable MemTable**: Nodus beku yang siap di-flush ke storage.
   - **SSTable (Sorted String Table)**: File penyimpanan terurut berstruktur blok, dilengkapi indeks jarang (*sparse index*) dan *Bloom Filter* berkinerja tinggi.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (B-Tree / Mutex Guarded) | Pendekatan Enterprise (Lock-Free Skip List / LSM) |
| :--- | :--- | :--- |
| **Pola I/O Disk** | Random Reads & Random In-place Overwrites. Mengakibatkan fragmentasi tinggi pada SSD. | Sequential Appends (WAL & SSTable Compaction). Memaksimalkan write endurance & bandwidth storage. |
| **Skalabilitas Thread** | Terbatas pada kontensi lock (*lock thrashing*) saat concurrency tinggi ($>64$ core). | Mendekati linier. Thread pembaca (*reader*) tidak pernah terblokir oleh thread penulis (*writer*). |
| **Overhead Metadata** | Node pointers pada tree tradisional memicu fragmentasi heap dan *pointer chasing*. | Skip list teroptimasi dan SSTable terkompresi menghemat ruang memori dan meminimalisasi *cache miss*. |
| **Handling Kontensi** | Thread tidur (*yield/sleep*), memicu latensi $P_{99}$ membengkak akibat context switch OS. | Algoritma *Lock-Free CAS retry loop* menjaga CPU tetap aktif pada *user-space* tanpa interupsi OS. |

---

## 5. How: Workflow Detail

### 5.1 Alur Kerja Operasi Lock-Free CAS Insertion
```
[Start Insert(Key, Value)]
         |
         v
[Cari lintasan nodus pendahulu (Predecessors) & suksesor (Successors) dari Level N down-to Level 0]
         |
         v
[Tentukan tinggi level nodus baru secara probabilitas (P=0.5)]
         |
         v
[Alokasikan Nodus Baru: NewNode(Key, Value, Height)]
         |
+------->[Loop CAS Level 0]
|        |
|        v
|  [Apakah Pred[0]->Next == Succ[0]?] 
|        |                  |
|     (Tidak)              (Ya)
|        |                  |
|  [Refresh Succ/Pred]      v
|        |           [Lakukan CAS: Pred[0]->Next diubah dari Succ[0] ke NewNode]
|        |                  |
|        |            (CAS Berhasil?)
|        |             /          \
+--------+          (Tidak)       (Ya)
                       |            |
                       v            v
                 [Looping Ulang]  [Secara Atomik Tautkan Level 1 s.d Height-1 via CAS]
                                    |
                                    v
                               [Selesai (Insert Berhasil)]
```

### 5.2 Alur Kerja LSM-Tree Ingestion Engine
1. **Write Request Masuk**:
   - Tulis payload ke **Write-Ahead Log (WAL)** via sekuensial direct I/O (append-only).
   - Masukkan pasangan key-value ke **Active MemTable** (Concurrent Skip List) secara in-memory.
2. **Threshold Saturation**:
   - Jika kapasitas Active MemTable melampaui batas (misal: 64MB), status MemTable diubah menjadi **Immutable MemTable**.
   - Alokasikan instance MemTable baru yang kosong untuk menerima penulisan berikutnya tanpa jeda (*zero stall*).
3. **Flushing & Compaction Worker**:
   - Background thread membaca Immutable MemTable secara sekuensial.
   - Konstruksi **Bloom Filter** dari himpunan key pada MemTable tersebut.
   - Buat blok-blok data berukuran terkompresi (misal: 4KB per block) beserta file **Sparse Index**.
   - Tulis struktur menjadi berkas **SSTable Level-0** ke disk.
   - Hapus WAL lama yang transaksinya telah persisten di SSTable.

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi Skip List
Bayangkan sebuah jalan tol dengan jalur bertingkat:
- **Level 0 (Jalan Lokal)**: Berhenti di setiap rumah/persimpangan ($1, 2, 3, 4, 5, 6, 7, 8$).
- **Level 1 (Jalur Arteri)**: Hanya memiliki pintu keluar di nomor ganjil/tertentu ($1, 3, 5, 7$).
- **Level 2 (Jalur Tol Ekspres)**: Hanya berhenti di interchange utama ($1, 5$).

Pencarian nilai $7$ melesat di Level 2 hingga menemukan $5$, melihat bahwa target ($7$) berada sebelum $8$ (atau tak hingga), turun ke Level 1 pada posisi $5$, lalu lompat ke $7$ dengan kecepatan tinggi tanpa menyentuh $2, 3, 4,$ atau $6$.

### 6.2 Layout Memori dan Diagram ASCII

#### A. Multi-Level Skip List Memory Structure
```
Level 3:  [Head] -----------------------------------------------------> [Node 12] -> NIL
           |                                                                |
Level 2:  [Head] ------------------------> [Node 6] -------------------> [Node 12] -> NIL
           |                                  |                             |
Level 1:  [Head] ---------> [Node 3] -----> [Node 6] -----> [Node 9] ---> [Node 12] -> NIL
           |                  |               |               |             |
Level 0:  [Head] -> [N 1] -> [Node 3] -> [N4] [Node 6] -> [N8][Node 9] -> [Node 12] -> NIL
```

#### B. Cache-Conscious Node Packing (64-byte boundary)
```
+-------------------------------------------------------------------------+
|                  Hardware Cache Line (64 Bytes)                         |
+--------------------+-------------------+--------------------+-----------+
| Key (int64)        | ValuePtr (uint64) | Height (uint32)    | Pad(12B)  |
| 8 Bytes            | 8 Bytes           | 4 Bytes            | 12 Bytes  |
+--------------------+-------------------+--------------------+-----------+
| Forward Pointer Level 0 (uint64)       | Forward Pointer Level 1 (uint64)|
| 8 Bytes                                | 8 Bytes                         |
+----------------------------------------+---------------------------------+
| Forward Pointer Level 2 (uint64)       | Forward Pointer Level 3 (uint64)|
| 8 Bytes                                | 8 Bytes                         |
+-------------------------------------------------------------------------+
Total Size = 64 Bytes (Pas 1 Baris Cache Line -> Tidak ada split line fetch!)
```

---

## 7. Implementasi Kode

Berikut adalah implementasi **Concurrent-Safe MemTable Skip List** berstandar produksi dalam bahasa Go, memanfaatkan operasi atomik `unsafe.Pointer`, penataan bit memori, pemrosesan bebas *lock thrashing*, serta proteksi terhadap kontensi tinggi.

### 7.1 Implementasi Skip List Berbasis CAS

```go
// File: skiplist.go
package main

import (
	"bytes"
	"fmt"
	"math/bits"
	"math/rand"
	"sync/atomic"
	"time"
	"unsafe"
)

const (
	MaxHeight = 16
	Branching = 4
)

// ValueNode merepresentasikan payload data terisolasi untuk atomic swapping.
type ValueNode struct {
	Value     []byte
	Timestamp int64
}

// Node merepresentasikan elemen pada Skip List yang di-align ke boundary cache memory.
type Node struct {
	Key     []byte
	Value   unsafe.Pointer // *ValueNode
	Height  int
	Forward [MaxHeight]unsafe.Pointer // *Node
}

// ConcurrentSkipList menyediakan operasi thread-safe lock-free search dan atomic CAS write.
type ConcurrentSkipList struct {
	Head   *Node
	Height int64 // Atomic int64
	Length int64 // Atomic int64
}

// NewNode mengalokasikan memori untuk nodus baru.
func NewNode(key []byte, val []byte, height int) *Node {
	vn := &ValueNode{
		Value:     val,
		Timestamp: time.Now().UnixNano(),
	}
	n := &Node{
		Key:    key,
		Height: height,
	}
	atomic.StorePointer(&n.Value, unsafe.Pointer(vn))
	return n
}

// NewConcurrentSkipList menginisialisasi skip list baru dengan sentinel head node.
func NewConcurrentSkipList() *ConcurrentSkipList {
	head := NewNode(nil, nil, MaxHeight)
	return &ConcurrentSkipList{
		Head:   head,
		Height: 1,
	}
}

// generateRandomHeight menghasilkan tinggi nodus secara probabilistik (p = 1/Branching).
func (s *ConcurrentSkipList) generateRandomHeight() int {
	// Menggunakan bit-counting dari pseudorandom generator untuk efisiensi CPU
	rnd := rand.Uint32()
	h := 1
	for h < MaxHeight && (rnd&(Branching-1)) == 0 {
		h++
		rnd >>= 2
	}
	return h
}

// findSplice mencari lintasan suksesor dan predesesor dari level tertinggi hingga level 0.
func (s *ConcurrentSkipList) findSplice(key []byte, preds *[MaxHeight]*Node, succs *[MaxHeight]*Node) {
	curr := s.Head
	for level := int(atomic.LoadInt64(&s.Height)) - 1; level >= 0; level-- {
		nextPtr := atomic.LoadPointer(&curr.Forward[level])
		next := (*Node)(nextPtr)

		for next != nil && bytes.Compare(next.Key, key) < 0 {
			curr = next
			nextPtr = atomic.LoadPointer(&curr.Forward[level])
			next = (*Node)(nextPtr)
		}

		preds[level] = curr
		succs[level] = next
	}
}

// Get mengeksekusi lock-free sequential search tanpa alokasi memori.
func (s *ConcurrentSkipList) Get(key []byte) ([]byte, bool) {
	curr := s.Head
	for level := int(atomic.LoadInt64(&s.Height)) - 1; level >= 0; level-- {
		nextPtr := atomic.LoadPointer(&curr.Forward[level])
		next := (*Node)(nextPtr)

		for next != nil {
			cmp := bytes.Compare(next.Key, key)
			if cmp == 0 {
				vn := (*ValueNode)(atomic.LoadPointer(&next.Value))
				if vn == nil {
					return nil, false // Secara logis telah terhapus (Tombstone)
				}
				return vn.Value, true
			}
			if cmp > 0 {
				break
			}
			curr = next
			nextPtr = atomic.LoadPointer(&curr.Forward[level])
			next = (*Node)(nextPtr)
		}
	}
	return nil, false
}

// Put memasukkan pasangan Key-Value menggunakan CAS loop pada Level 0 dan linking bertingkat.
func (s *ConcurrentSkipList) Put(key []byte, val []byte) {
	var preds [MaxHeight]*Node
	var succs [MaxHeight]*Node

	for {
		s.findSplice(key, &preds, &succs)

		// Kasus 1: Key sudah ada, lakukan atomic CAS swap pada pointer Value (In-place update)
		if succs[0] != nil && bytes.Compare(succs[0].Key, key) == 0 {
			targetNode := succs[0]
			newValNode := &ValueNode{
				Value:     val,
				Timestamp: time.Now().UnixNano(),
			}
			oldValPtr := atomic.LoadPointer(&targetNode.Value)
			if atomic.CompareAndSwapPointer(&targetNode.Value, oldValPtr, unsafe.Pointer(newValNode)) {
				return
			}
			// Kontensi CAS gagal; ulangi dari awal
			continue
		}

		// Kasus 2: Key belum ada, alokasikan Node baru
		nodeHeight := s.generateRandomHeight()
		currentListHeight := int(atomic.LoadInt64(&s.Height))

		for nodeHeight > currentListHeight {
			if atomic.CompareAndSwapInt64(&s.Height, int64(currentListHeight), int64(nodeHeight)) {
				break
			}
			currentListHeight = int(atomic.LoadInt64(&s.Height))
		}

		newNode := NewNode(key, val, nodeHeight)

		// Hubungkan Level 0 terlebih dahulu via CAS
		atomic.StorePointer(&newNode.Forward[0], unsafe.Pointer(succs[0]))
		if !atomic.CompareAndSwapPointer(&preds[0].Forward[0], unsafe.Pointer(succs[0]), unsafe.Pointer(newNode)) {
			// Preds[0] telah dimodifikasi oleh thread paralel lain; retry seluruh loop
			continue
		}

		// Level 0 terhubung secara sah. Tautkan level atas secara bertahap
		for level := 1; level < nodeHeight; level++ {
			for {
				pred := preds[level]
				succ := succs[level]

				// Validasi pred/succ jika terjadi modifikasi concurrent
				if pred == nil {
					pred = s.Head
				}
				atomic.StorePointer(&newNode.Forward[level], unsafe.Pointer(succ))
				if atomic.CompareAndSwapPointer(&pred.Forward[level], unsafe.Pointer(succ), unsafe.Pointer(newNode)) {
					break // Berhasil menautkan level ini, lanjutkan ke level di atasnya
				}

				// Jika gagal, re-scan splice khusus untuk level ini
				s.findSplice(key, &preds, &succs)
			}
		}

		atomic.AddInt64(&s.Length, 1)
		return
	}
}

// Size mengembalikan jumlah data terindeks.
func (s *ConcurrentSkipList) Size() int64 {
	return atomic.LoadInt64(&s.Length)
}

func main() {
	sl := NewConcurrentSkipList()

	start := time.Now()
	totalOps := 100000

	// Simulasi concurrent writer
	done := make(chan bool)
	workers := 8

	for w := 0; w < workers; w++ {
		go func(workerID int) {
			for i := 0; i < totalOps/workers; i++ {
				k := []byte(fmt.Sprintf("key-%08d", (i*workers)+workerID))
				v := []byte(fmt.Sprintf("val-%08d", (i*workers)+workerID))
				sl.Put(k, v)
			}
			done <- true
		}(w)
	}

	for w := 0; w < workers; w++ {
		<-done
	}

	fmt.Printf("Elapsed Ingestion Time: %v for %d items\n", time.Since(start), sl.Size())

	// Verifikasi Pembacaan
	testVal, ok := sl.Get([]byte("key-00000042"))
	if ok {
		fmt.Printf("Query Verification: key-00000042 => %s\n", string(testVal))
	} else {
		fmt.Println("Query Verification: Key Not Found!")
	}
}
```

---

## 8. Real World Case Study: High-Throughput Matching Engine Ingestion Tier

### Skenario
Sebuah bursa kripto tier-1 memproses lonjakan order perdagangan (*order spikes*) hingga **1.200.000 requests/detik** per instans saat terjadi volatilitas pasar ekstrem. Arsitektur sebelumnya yang berbasis *RDBMS write-ahead tables* kolaps di bawah tekanan latensi disk I/O, menghasilkan $P_{99} > 850\text{ ms}$ dan thread starvation.

### Solusi Arsitektur
Engine dirancang ulang menggunakan pola **In-Memory Lock-Free MemTable (Skip List)** dengan amortisasi penulisan disk via **Zero-Allocation Ring-Buffer WAL**:
1. Tiap event order divalidasi langsung di *user-space* dan diserialisasi ke dalam memori berstruktur *Skip List concurrent*.
2. MemTable tidak pernah mengalokasikan ulang memori secara global: pointer diperbarui menggunakan siklus atomik CAS.
3. Thread pemroses pembaca (*matching worker*) membaca *Order Book* secara non-blocking (*zero lock contention*).
4. Ketika snapshot Skip List menyentuh kuota 128 MB, thread background menembakkan operasi *Zero-Copy SSTable flush* ke local NVMe arrays menggunakan *kernel bypass* (`io_uring`).

```
Clients (WebSocket)
      │
      ▼
Gateway API Worker (Pinned to CPU Core 0-3)
      │
      ├───────────────────────┐ (Sequential Direct-I/O)
      ▼                       ▼
MemTable (Skip List)      WAL Storage Buffer (NVMe)
(Lock-Free In-Memory)
      │ (Flush threshold reached: 128MB)
      ▼
Immutable MemTable Copy
      │
      ▼ (Background Worker via io_uring)
SSTable Block Storage (Level-0 Data + Bloom Filter + Sparse Index)
```

### Metrik Dampak
- Latensi $P_{99}$ merosot dari **850 ms** menjadi **1.8 ms**.
- Pemanfaatan Core CPU stabil di angka 85% tanpa lonjakan *System Wait Time* (kernel context switch berkurang 94%).
- Write amplification berkurang dari 18x menjadi 2.4x.

---

## 9. Trade-offs

| Parameter | Mutex-Guarded Red-Black Tree | Lock-Free Concurrent Skip List | B+ Tree (Disk Optimized) | Log-Structured Merge (LSM) Tree |
| :--- | :--- | :--- | :--- | :--- |
| **Write Throughput** | Rendah (Tergantung lock) | Sangat Tinggi ($>10^6$ ops/s) | Menengah (Random I/O bound) | Ekstrem (Sequential write bound) |
| **Read Latency (Point)** | $O(\log N)$ (Terhalang writer) | $O(\log N)$ (Non-blocking reader) | $O(\log_B N)$ (Sangat cepat via cache) | $O(\text{layers} \times \log N)$ (Perlu filter/index) |
| **Range Queries** | Cepat (Iterator traversal) | Cepat (Linear level-0 forward) | Sangat Optimal (Linked leaf) | Lambat (Merge multi-SSTable iterators) |
| **CPU Cache Efficiency**| Buruk (*Pointer Chasing*) | Sedang (*Probabilistic Jump*) | Sangat Tinggi (Array-packed nodes) | Tinggi (Contiguous memory blocks) |
| **Konsumsi Memori** | Rendah (2 pointer per nodus) | Tinggi ($\sim 1.33-2$ pointer/nodus)| Sedang | Menengah-Tinggi (Tombstone overhead) |
| **Kompleksitas Kode** | Rendah (Tersedia built-in) | Ekstrem (Atomic/CAS hazard) | Tinggi | Sangat Ekstrem (Compaction + Compaction filters) |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 The ABA Problem pada CAS Pointer
- **Deskripsi Masalah**: Thread $T_1$ membaca pointer $A$. Thread $T_2$ melakukan preemption, menghapus $A$, mengalokasikan nodus baru di alamat memori yang persis sama ($A$), lalu mengubahnya ke $B$, dan mengembalikannya lagi ke $A$. Thread $T_1$ terbangun, melakukan `CAS(&ptr, A, C)`. CAS berhasil karena alamat memorinya identik, padahal struktur internal data $A$ sudah berubah secara fundamental.
- **Solusi**: Gunakan teknik **Tagged Pointers** (mengemas counter versi ke dalam sisa bit pointer 64-bit yang tidak terpakai/x86-64 sign extension bits) atau terapkan protokol **Epoch-Based Reclamation (EBR)** / **Hazard Pointers** sebelum mendealokasikan memori.

### 10.2 False Sharing pada Multi-Core Index Tracking
- **Deskripsi Masalah**: Nodus Head atau struct status ukuran Skip List (`Length`, `Height`) dideklarasikan bersebelahan di memori. Dua thread pada core berlainan yang satu membaca `Height` dan yang lain menulis `Length` akan memaksa L1/L2 cache invalidation pada kedua core tersebut.
- **Pendeteksian**: Jalankan profiling hardware menggunakan Linux `perf`:
  ```bash
  perf c2c record ./engine_binary
  perf c2c report --stdio
  ```
  Cari metrik `HITM` (*Hit Modified Cache Line*). Nilai HITM yang tinggi menandakan terjadinya false sharing parah.
- **Solusi**: Sisipkan padding eksplisit berukuran 64-byte:
  ```go
  type ConcurrentSkipList struct {
      Head       *Node
      _pad0      [56]byte // 64 - 8 bytes Head pointer
      Height     int64
      _pad1      [56]byte // Menjamin Height dan Length berada pada Cache Line terpisah
      Length     int64
      _pad2      [56]byte
  }
  ```

---

## 11. Best Practices (Production Checklist)

1. [ ] **Hardware Alignment**: Verifikasi seluruh struct inti data diselaraskan dengan batas kelipatan 64 byte menggunakan `unsafe.Alignof` atau padding eksplisit.
2. [ ] **Memory Fences**: Pastikan penulisan payload nodus baru diselesaikan (*Store-Release*) sebelum pointer forward disambungkan ke dalam list aktif (*Publishing*).
3. [ ] **Pre-allocated Arena Memory**: Hindari eksekusi alokasi memori runtime Go (`runtime.newobject` / `malloc`) di dalam critical write path. Gunakan *Buffer Arena Pool* berbasis byte array statis.
4. [ ] **Probabilistic Balance Tuning**: Gunakan basis probabilitas tinggi $p=0.25$ (1 banding 4) alih-alih $p=0.5$ untuk menghemat konsumsi pointer rata-rata dari 2 pointer per nodus menjadi 1.33 pointer per nodus tanpa mendegradasi performa pencarian.
5. [ ] **Tombstone Compaction Lifecycle**: Terapkan masa kedaluwarsa (*TTL*) dan interval sweep otomatis untuk nodus bertanda *tombstone* (data terhapus) agar tidak terjadi memory leak terselubung.
6. [ ] **Zero-Allocation Comparators**: Serialisasi kunci (keys) sedemikian rupa sehingga perbandingan kunci dapat dilakukan menggunakan `bytes.Compare` atau `uint64` primitives, mencegah escape analysis mengalihkan variabel ke heap.

---

## 12. Hands-on Practice

Buat dan jalankan modul praktikum ini di direktori kerja: `hands-on/m02/`

### Langkah 1: Setup Workdir dan Benchmark Engine
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init m02-advanced-structures
```

### Langkah 2: Buat File Implementasi Skip List
Salin source code dari **Seksi 7** ke dalam file bernama `skiplist.go`.

### Langkah 3: Buat Benchmark File
Buat file `skiplist_test.go`:
```go
// File: skiplist_test.go
package main

import (
	"fmt"
	"sync"
	"testing"
)

func BenchmarkConcurrentSkipList_Put(b *testing.B) {
	sl := NewConcurrentSkipList()
	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			k := []byte(fmt.Sprintf("bench-key-%010d", i))
			v := []byte("bench-value-payload")
			sl.Put(k, v)
			i++
		}
	})
}

func BenchmarkConcurrentSkipList_Get(b *testing.B) {
	sl := NewConcurrentSkipList()
	total := 100000
	for i := 0; i < total; i++ {
		sl.Put([]byte(fmt.Sprintf("bench-key-%010d", i)), []byte("bench-value-payload"))
	}

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			sl.Get([]byte(fmt.Sprintf("bench-key-%010d", i%total)))
			i++
		}
	})
}
```

### Langkah 4: Jalankan Pengujian Race Detector dan Benchmark
```bash
# Uji Data Race Concurrency
go test -race -v -run=^$ -bench=.

# Uji Profiling CPU dan Alokasi Memori
go test -benchmem -run=^$ -bench=BenchmarkConcurrentSkipList_Put -cpuprofile=cpu.prof -memprofile=mem.prof
```

---

## 13. Exercises

### Tingkat: Easy
- **Tugas**: Tambahkan method `Contains(key []byte) bool` pada implementasi `ConcurrentSkipList` yang berjalan secara non-blocking dan tidak mengembalikan payload value, melainkan hanya boolean.
- **Kriteria Keberhasilan**: Lolos unit test, mengembalikan `false` jika key ditandai oleh *tombstone*, dan zero-allocations terverifikasi via `testing.AllocsPerRun`.

### Tingkat: Medium
- **Tugas**: Implementasikan mekanisme **Soft Delete (Tombstone)** atomik pada Skip List melalui fungsi `Delete(key []byte) bool`.
- **Kriteria Keberhasilan**: Fungsi tidak boleh memutus link forward secara langsung (karena berisiko merusak traversing reader thread lain), melainkan melakukan atomik CAS swap pointer `Value` menjadi pointer `nil`. Operasi `Get` harus mengembalikan `false` setelah operasi delete berhasil.

### Tingkat: Hard
- **Tugas**: Modifikasi alokasi nodus Skip List agar menggunakan custom **Memory Arena** berbasis byte slice besar yang dialokasikan di awal (*pre-allocated slab*). Hindari semua panggilan `new(Node)`.
- **Kriteria Keberhasilan**: Uji benchmark `BenchmarkConcurrentSkipList_Put` menunjukkan **0 B/op** dan **0 allocs/op** pada output `-benchmem`.

---

## 14. Challenge: Production-Ready Bloom Filter & SSTable Block Encoder

Rancang modul *storage layer* lengkap tanpa dependensi eksternal (hanya library standar Go) yang bertugas mengeksekusi flush dari Skip List ke disk:
1. **Spesifikasi Teknis**:
   - Terima snapshot data dari Skip List berukuran 100.000 entitas.
   - Buat file SSTable berstruktur:
     - **Header Block**: Magic Byte, Versi, Total Records.
     - **Data Block**: Kumpulan record key-value yang di-pack padat dengan format *Length-Prefixed Byte Array*.
     - **Index Block (Sparse Index)**: Menyimpan key pertama dari setiap blok 4KB beserta byte offset posisinya.
     - **Bloom Filter Block**: Bit array berukuran dinamis dengan $k$ kalkulasi hash independen (gunakan MurmurHash3 atau FNV-1a) dengan batas toleransi kesalahan (*false positive rate*) $\le 1\%$.
2. **Kriteria Evaluasi**:
   - Reader program dapat mencari key acak langsung dari file SSTable disk dalam waktu $< 250\text{ mikrodetik}$ tanpa men-load seluruh file ke dalam RAM.
   - Penolakan key yang tidak eksis harus ditangkis oleh *Bloom Filter block* sebelum disk block scan dieksekusi.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Mengapa sequential I/O jauh lebih cepat dibandingkan random I/O pada perangkat penyimpanan solid-state (NVMe SSD)?
2. Berapa ukuran tipikal CPU Cache Line pada prosesor modern x86 dan ARM64, dan apa hubungannya dengan penataan data pointer?
3. Apa perbedaan operasi atomik `StorePointer` biasa dengan operasi `CompareAndSwapPointer`?
4. Apa kelemahan utama struktur data seimbang Red-Black Tree jika diimplementasikan pada lingkungan *high-concurrency multithreaded*?
5. Mengapa Skip List disebut sebagai struktur data probabilistik?

### 15.2 Pertanyaan Intermediate
6. Jelaskan fenomena *False Sharing*, bagaimana mekanismenya merusak performa aplikasi concurrent, dan bagaimana cara mendeteksinya pada level Linux kernel!
7. Apa yang dimaksud dengan *Acquire-Release Memory Ordering Semantics* dan mengapa arsitektur ARM memerlukannya sementara x86 memiliki model memori yang lebih ketat (*strongly-ordered*)?
8. Bagaimana LSM-Tree menangani modifikasi penghapusan (*Delete*) data secara efisien tanpa melakukan in-place seek pada file storage di disk?
9. Apa yang dimaksud dengan *ABA Problem* dalam algoritma lock-free berbasis pointer, dan sebutkan dua strategi standar industri untuk menanggulanginya!
10. Mengapa Skip List di-flush ke disk dalam bentuk file SSTable yang terurut, bukan langsung dikonversi menjadi B+ Tree?

### 15.3 Skenario Kasus Produksi
11. **Skenario 1**: Database LSM engine Anda mengalami lonjakan latensi baca (*Read Latency Spike*) yang sangat masif setiap 30 menit sekali, sementara throughput penulisan tetap normal. Selama spike ini, I/O disk utilization menyentuh 100%. Apa diagnosa akar masalah pada arsitektur engine Anda dan bagaimana mitigasi strukturalnya?
12. **Skenario 2**: Profiler CPU aplikasi Go Anda menunjukkan bahwa 40% siklus CPU dihabiskan pada runtime internal function `runtime.gcBgMarkWorker` dan `runtime.scanobject` di dalam modul MemTable berbasis Skip List berkapasitas 500 juta record. Bagaimana Anda mendesain ulang layout memori struktur data tersebut untuk mengeliminasi beban garbage collector tersebut secara total?
13. **Skenario 3**: Sebuah antrean data Lock-Free Single-Producer Single-Consumer (SPSC) Ring Buffer menghasilkan korupsi data intermiten (data terbaca sebelum selesai ditulis secara utuh) ketika dijalankan pada server prosesor ARM64 (AWS Graviton), namun berjalan mulus tanpa bug sama sekali pada server x86-64 Intel Xeon. Analisis akar masalah perbedaan arsitektural ini dan berikan solusinya!

---

### Kunci Jawaban & Technical Explanations Quiz

#### Evaluasi Basic
1. **Penjelasan**: NVMe SSD tersusun atas block-block memori NAND flash. Sequential write memungkinkan data ditulis terus menerus pada blok erase yang bersih secara kontigu, mengeliminasi kebutuhan internal controller SSD untuk mengeksekusi operasi baca-modifikasi-tulis (*read-modify-write*) dan algoritma *Garbage Collection (GC)* internal SSD yang memicu *Write Amplification*.
2. **Penjelasan**: Ukuran standar adalah **64 bytes**. Jika nodus struktur data melintasi batas (*boundary*) 64 byte, CPU terpaksa melakukan dua kali pembacaan cache line secara serial (*split cache fetch*) untuk mengambil satu nodus memori, menggandakan latensi akses hardware.
3. **Penjelasan**: `StorePointer` menulis alamat memori secara atomik tanpa memedulikan nilai memori sebelumnya (eksekusi buta). `CompareAndSwapPointer` bersifat kondisional: instruksi hanya memperbarui nilai jika nilai saat ini identik dengan parameter `old` yang diberikan, memungkinkan sinkronisasi non-blocking yang aman dari modifikasi liar thread paralel lain.
4. **Penjelasan**: Operasi self-balancing pada Red-Black Tree melibatkan *Tree Rotations* yang mengubah posisi relasional banyak parent dan children nodes sekaligus. Mengunci (*locking*) sub-tree besar secara eksklusif agar aman dari race condition memicu kontensi lock yang sangat tinggi (*lock thrashing*) yang mematikan skalabilitas thread.
5. **Penjelasan**: Karena penyeimbangan tinggi hierarki nodus tidak diatur menggunakan aturan restrukturisasi deterministik (seperti rotasi AVL/RBT), melainkan ditentukan secara acak menggunakan lemparan koin (*coin flip/pseudorandom bit distribution*) saat inisialisasi nodus.

#### Evaluasi Intermediate
6. **Penjelasan**: *False Sharing* terjadi ketika variabel-variabel independen yang dimodifikasi oleh core-core berbeda berada pada satu blok 64-byte cache line yang sama. Protokol koherensi hardware (MESI) menandai cache line tersebut sebagai *Invalid* di core tetangga begitu satu core menulis, memicu sinkronisasi bus interconnect yang membuang ribuan siklus komputasi. Dideteksi via Linux `perf c2c` (Cache-to-Cache) dengan mengamati lonjakan hit rate level HITM (*Hit Modified*).
7. **Penjelasan**: *Acquire* menjamin pembacaan instruksi setelah fence tidak di-reorder mendahuluinya; *Release* menjamin penulisan data sebelum fence telah persisten dan terlihat sebelum instruksi release dilewati. x86 adalah arsitektur *strongly ordered* (mayoritas load/store memiliki acquire/release implicit), sedangkan ARM64 adalah *weakly ordered memory model* di mana compiler dan CPU bebas mengatur ulang urutan instruksi memori kecuali jika dipasangi instruksi hardware barrier (`DMB`/`LDAR`/`STLR`).
8. **Penjelasan**: LSM-Tree tidak menghapus data secara in-place. Modifikasi `Delete` diselesaikan dengan menulis record penanda khusus yang disebut **Tombstone** ke Active MemTable dan WAL. Saat proses background *Compaction* berlangsung, file-file SSTable digabung (*merge-sort*); nodus lama yang tertimpa tombstone ini akan dieliminasi dari disk secara final.
9. **Penjelasan**: Masalah modifikasi tersembunyi pada alamat pointer identik. Mitigasi: (1) **Tagged Pointer / Versioning**: Menyisipkan integer increment (stamp) pada pointer payload; (2) **Hazard Pointer / Epoch-Based Reclamation (EBR)**: Thread mendaftarkan pointer yang sedang aktif dibaca; memori nodus fisik dilarang dialokasikan ulang atau dibebaskan sampai seluruh thread melewati epoch tersebut.
10. **Penjelasan**: Skip List dapat di-traverse dari Level 0 secara linier berurutan ($O(N)$). Mengonversinya menjadi SSTable hanya membutuhkan operasi sequential merge-sort write yang padat dan berkecepatan tinggi, menghasilkan susunan blok storage tanpa fragmentasi ruang kosong (*zero-slack space*).

#### Evaluasi Skenario Kasus Produksi
11. **Diagnosa & Mitigasi**: 
    - *Akar Masalah*: Terjadi fenomena **Compaction Stall**. Background compaction thread tidak mampu mengejar laju penulisan, menyebabkan tumpukan berkas SSTable pada Level 0 (L0) melampaui ambang batas (*threshold*). Karena file pada L0 memiliki cakupan range key yang saling tumpang tindih (*overlapping keys*), operasi pembacaan terpaksa membuka dan memeriksa seluruh file L0 satu per satu via random I/O, melumpuhkan disk bandwidth.
    - *Mitigasi Arsitektur*: (1) Terapkan *Tiered Compaction* alih-alih *Leveled Compaction* untuk L0; (2) Tingkatkan alokasi I/O bandwidth compaction thread menggunakan rate-limiter; (3) Integrasikan *Partitioned Skip List MemTable* yang membatasi ukuran L0; (4) Pasang dynamic write stall (perlambat sedikit laju penulisan MemTable sebelum batas L0 kritis tersentuh).
12. **Diagnosa & Mitigasi**: 
    - *Akar Masalah*: Go Garbage Collector melakukan traversing (*heap scanning*) terhadap setiap pointer memori yang ada pada heap. Struktur data linked-list/tree klasik dengan ratusan juta nodus dan pointer menghasilkan ratusan juta objek terisolasi yang harus dipindai oleh GC mark worker pada setiap siklus GC, menghabiskan waktu CPU secara sia-sia.
    - *Solusi Rekayasa*: Buat **Off-Heap Storage** atau gunakan **Monolithic Byte Slice Arena**. Alokasikan memori dalam satu potongan byte array masif (`arena []byte`). Ganti representasi pointer Go (`*Node`) dengan **relational integer offset** (`uint32` index) dari basis alamat array arena tersebut. Karena slice byte murni tidak mengandung pointer internal yang dikenali runtime Go, GC mengabaikan seluruh blok memori ratusan gigabyte tersebut dalam 0 milidetik (*GC scan overhead turun ke 0%*).
13. **Diagnosa & Mitigasi**:
    - *Akar Masalah*: Pada server x86-64, urutan Store-Store tidak pernah di-reorder oleh hardware (arsitektur memori TSO: *Total Store Order*). Namun, arsitektur ARM64 adalah *Weak Memory Model*. Tanpa instruksi sinkronisasi eksplisit, compiler atau prosesor ARM64 menukar urutan penulisan payload data dengan penulisan status flag ketersediaan buffer (*write pointer*). Akibatnya, thread Consumer membaca flag buffer "tersedia", padahal payload data fisiknya masih tertahan di register/store-buffer core Producer.
    - *Solusi Rekayasa*: Gunakan operasi atomik dengan semantik memory fence yang ketat: Produser wajib menggunakan `atomic.Store` dengan *Release semantics* saat mempublikasikan head index, dan Consumer wajib menggunakan `atomic.Load` dengan *Acquire semantics* saat menarik status index tersebut.

---

## 16. Summary
- Struktur data enterprise modern menjembatani kesenjangan antara teori algoritma murni dengan realitas fisik perangkat keras (*Hardware-Software Symbiosis*).
- Kompleksitas $O(\log N)$ pada Skip List memberikan karakteristik performa yang setara dengan self-balancing tree, namun jauh lebih unggul dalam sistem pemrosesan paralel masif karena eliminasi rotasi global dan kompatibilitas tinggi dengan operasi atomik Compare-And-Swap (CAS).
- Arsitektur berbasis LSM-Tree mengoptimalkan hierarki I/O secara ekstrem: penulisan data diakselerasi via *Sequential Logging* (WAL) dan *In-Memory Indexing* (Skip List MemTable), sementara durabilitas permanen didelegasikan ke SSTable berbasis blok pada level storage, dipercepat oleh verifikasi probabilistik *Bloom Filter*.
- Menulis kode berskala produksi menuntut pemahaman menyeluruh terhadap efek samping tingkat rendah: *false sharing*, batas *cache line 64-byte*, pemodelan memori (*Acquire-Release* vs. *Sequential Consistency*), serta pencegahan bahaya pointer *ABA problem*. Pengetahuan ini membedakan rekayasa perangkat lunak amatir dari perancangan sistem terdistribusi berkinerja tinggi.