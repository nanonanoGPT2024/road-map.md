# Kurikulum Arsitektur Perangkat Lunak Enterprise
## Kategori: 06-Architecture-and-System-Design
### BAB-05: Distributed Data Architecture & Storage
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Architect / Lead Engineer diharapkan mampu:
1. **Menganalisis dan Memilih Engine Penyimpanan Tingkat Rendah:** Mengoperasikan dan mengoptimasi *Storage Engine Internals* (LSM-Tree vs B-Tree) dengan konfigurasi memory budget, Bloom Filter sizing, serta strategi pemadatan (*compaction*) terukur.
2. **Merancang Sistem Replikasi Berorientasi Toleransi Kegagalan:** Mengimplementasikan topologi replikasi terdistribusi (*Leaderless / Dynamo-style* vs *Consensus-backed Multi-Paxos/Raft*) lengkap dengan perhitungan matematis *Quorum Consistency* ($R + W > N$).
3. **Membangun Partisi Data Berkelanjutan:** Mendesain sistem *Consistent Hashing* dengan *Virtual Nodes* (vnodes) dinamis yang mampu menangani *heterogeneous hardware capacity*, mencegah kaskade kegagalan (*cascading failures*), dan mengeliminasi *hot-spotting*.
4. **Mengimplementasikan Strategi Anti-Entropy dan Pemulihan Data:** Menerapkan struktur data *Merkle Trees*, *Sloppy Quorum*, dan *Hinted Handoff* untuk memulihkan partisi jaringan (*network partition*) tanpa degradasi *availability*.
5. **Mengelola Transaksi Terdistribusi Skala Global:** Mengevaluasi kompromi antara *Two-Phase Commit* (2PC), *Percolator Transaction Model*, dan *Saga Pattern* dalam kaitannya dengan anomali konkurensi (Phantom Reads, Write Skew).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* Fundamental CAP Theorem, PACELC Theorem, dan Jaringan Terdistribusi (Fischer-Lynch-Paterson Impossibility, Unreliable Networks, Clock Skew / NTP drift).
* Arsitektur konkurensi tingkat lanjut (Goroutines/Channels di Go, Memory Model, Mutex, CAS / Compare-And-Swap).
* Struktur data dasar: B-Tree, Binary Search Tree, Hash Ring, Hashing Function (MurmurHash3, SHA-256).
* Pemahaman mendalam mengenai disk I/O: Karakteristik Sequential Read/Write vs Random Read/Write pada NVMe SSD dan kernel page cache (`fsync`, direct I/O).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Anatomik Mesin Penyimpanan: B-Tree vs LSM-Tree
Penyimpanan modern terdistribusi berakar pada dua filosofi utama perlakuan disk I/O:

```
              ┌─────────────────────────────────────────────────────────┐
              │                   DISK ACCESS PARADIGM                  │
              └────────────────────────────┬────────────────────────────┘
                                           │
                  ┌────────────────────────┴────────────────────────┐
                  ▼                                                 ▼
      ┌───────────────────────┐                         ┌───────────────────────┐
      │        B-TREE         │                         │       LSM-TREE        │
      │  (In-Place Updates)   │                         │  (Append-Only / WAL)  │
      └───────────┬───────────┘                         └───────────┬───────────┘
                  │                                                 │
     Optimasi: Random Access Reads                     Optimasi: Sequential Write Thpt
     Karakteristik: Update In-Place                    Karakteristik: Immutable SSTables
     Overhead: High Write Amplification                Overhead: Compaction, Read Ampl.
     Contoh: Postgres, InnoDB, Spanner                 Contoh: RocksDB, Cassandra, Scylla
```

1. **B-Tree (In-Place Updates):**
   * Menyimpan struktur hierarki halaman berukuran tetap (*fixed-size pages*, mis. 4KB-16KB).
   * Modifikasi data mengubah halaman secara in-place di disk. Memerlukan *Write-Ahead Logging* (WAL) untuk menjamin durabilitas transaksi sebelum modifikasi halaman dialirkan ke disk.
   * **Write Amplification Factor (WAF):** Mengubah baris 100 byte dapat memaksa penulisan ulang seluruh blok 16KB ke disk ($WAF \approx 160$).

2. **LSM-Tree (Log-Structured Merge-Tree):**
   * **MemTable:** Buffer berbasis RAM (biasanya diimplementasikan via *SkipList* atau *Red-Black Tree*). Semua mutasi (Write/Update/Delete via *Tombstone*) ditulis ke MemTable dan di-append ke WAL secara berurutan (*sequential*).
   * **SSTable (Sorted String Table):** Saat MemTable penuh, ia di-freeze menjadi *immutable MemTable* dan di-flush ke disk secara sekuensial sebagai SSTable. SSTable terdiri dari Data Blocks, Index Blocks, dan Bloom Filter.
   * **Compaction Mechanics:**
     * *Size-Tiered Compaction Strategy (STCS):* Menggabungkan SSTable dengan ukuran setara. Efisien untuk beban kerja tinggi tulis, namun membutuhkan *free disk space* hingga 50% untuk operasi penggabungan.
     * *Leveled Compaction Strategy (LCS):* Membagi data ke dalam level-level berlipat ganda ($L_1, L_2, \dots, L_k$ di mana $Size(L_{k}) = 10 \times Size(L_{k-1})$). $L_0$ memiliki *overlapping keys*, sedangkan $L_1$ dan seterusnya bersifat *strictly non-overlapping*. LCS mengoptimasi *Read Amplification* (RAF) dengan bayaran *Write Amplification* yang lebih tinggi.

#### 3.2 Leaderless Replication & Dynamical Quorums (Dynamo Anatomy)
Model replikasi tanpa pemimpin tunggal (*leaderless*) menghilangkan *single point of failure* (SPOF) pada saat *write operations*. 

* **Konfigurasi Quorum:** Didefinisikan dengan tuple $(N, R, W)$
  * $N$: Faktor Replikasi (jumlah replika target).
  * $W$: Jumlah replika yang harus mengonfirmasi penulisan sebelum dianggap sukses.
  * $R$: Jumlah replika yang harus merespons pembacaan data.
  * **Strict Quorum:** $R + W > N$. Menjamin bahwa himpunan replika baca dan himpunan replika tulis bersinggungan secara matematis ($\{Nodes_R\} \cap \{Nodes_W\} \neq \emptyset$), memastikan setidaknya satu node mengembalikan versi data terbaru (ditentukan via monotonic version vector / hybrid logical clock).
  * **Weak / Sloppy Quorum:** Ketika node utama tidak dapat diakses akibat *network partition*, sistem menuliskan data ke node cadangan di luar cincin replikasi langsung (*hinted handoff*) guna menjaga *availability* ($A$ di CAP).

#### 3.3 Dynamic Partitioning & Consistent Hashing
Untuk mendistribusikan beban secara merata melintasi ratusan node, teknik *modulo hashing* ($hash(key) \pmod N$) tidak dapat digunakan karena penambahan atau pengurangan node tunggal akan menyebabkan perpindahan data masif ($O(K)$ di mana $K$ adalah total data).

* **Hash Ring:** Ruang token melingkar berukuran $[0, 2^{32}-1]$ atau $[0, 2^{64}-1]$.
* **Virtual Nodes (vnodes):** Node fisik memiliki alokasi banyak token acak atau terdistribusi merata di sepanjang cincin. 
  $$\text{vnodes per node} = \alpha \times \text{Bobot Kapasitas Node}$$
  Dengan vnodes, pembebanan seragam tercapai ($variance \approx O(1/\sqrt{V})$ di mana $V$ adalah jumlah virtual nodes), dan ketika node mati, beban kerjanya didistribusikan secara proporsional ke semua node yang tersisa, menghindari *thundering herd* ke satu tetangga fisik.

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik Relasional | Arsitektur Penyimpanan Terdistribusi |
| :--- | :--- | :--- |
| **Penyimpanan Data** | Terikat kapasitas vertikal disk tunggal/RAID. | Terdistribusi horizontal melintasi klaster komoditas. |
| **Bottleneck Tulis** | I/O bus, locks, latensi sync WAL disk tunggal. | Terdistribusi via partisi paralel (*partitioning*). |
| **Ketersediaan** | Failover active-passive (potensi *downtime* deteksi). | Multi-master / Leaderless dengan failover transparan. |
| **Model Konsistensi** | ACID Ketat (Serializability). | Dapat dikonfigurasi per-request (Eventual s.d. Linearizable). |
| **Mitigasi Hardware Fail**| Redundansi level infrastruktur (SAN, UPS, dual-NIC). | Redundansi level aplikasi (Replication factor, self-healing). |

---

### 5. How (Workflow Detail)

Alur kerja operasi mutasi (*write*) dan pembacaan (*read*) pada penyimpanan terdistribusi Dynamo-style modern:

```
[Write Request] ──> [Coordinator Node]
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
[Replica 1]          [Replica 2]        [Replica 3]
  ├── Append WAL       ├── Append WAL     ├── (Down/Unreachable)
  ├── MemTable Put     └── MemTable Put   └── Store Hint on
  └── ACK                └── ACK               Coordinator Node
       │                  │                    (Hinted Handoff)
       └─────────┬────────┘
                 │ (W=2 acknowledged >= Required Quorum)
                 ▼
          [Return Success to Client]
```

```
[Read Request] ──> [Coordinator Node]
                         │
       ┌─────────────────┴─────────────────┐
       ▼                                   ▼
[Replica 1]                           [Replica 2]
  ├── Evaluate Bloom Filter             ├── Evaluate Bloom Filter
  ├── Probe Block Cache                 ├── Probe Block Cache
  ├── Scan MemTable & SSTable           ├── Scan MemTable & SSTable
  └── Return (Value_A, Clock_T2)        └── Return (Value_A, Clock_T1)
       │                                   │
       └─────────────────┬─────────────────┘
                         │
             Compare Vector Clocks
             Version T2 > T1
                         │
       ┌─────────────────┴─────────────────┐
       ▼                                   ▼
[Return Value_A to Client]         [Trigger Background Task]
                                   └── Read-Repair to Replica 2
```

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi Logistik Perpustakaan (LSM-Tree)
Bayangkan perpustakaan raksasa:
* **MemTable:** Meja kerja pustakawan. Setiap buku baru diletakkan langsung di atas meja dan dicatat secara kronologis di buku harian (*WAL*). Meja ini sangat cepat diakses, tetapi kapasitasnya terbatas.
* **SSTable Flush:** Saat meja penuh, pustakawan menyortir semua buku di meja berdasarkan abjad, mengikatnya dalam kardus bertanda (*immutable*), lalu menyimpannya di gudang (Disk). Pustakawan tidak pernah menyisipkan buku baru ke dalam kardus lama secara langsung.
* **Compaction:** Pada malam hari, pustakawan menggabungkan beberapa kardus berantakan yang memiliki kategori abjad beririsan menjadi satu set kardus baru yang rapi, membuang catatan buku yang sudah ditarik (*Tombstones*).

#### 6.2 Visualisasi Hash Ring dengan Virtual Nodes
```
                         Token 0
                    Node_A-vnode1 [0x000]
                 .         |         .
             .             |             .
        .                  |                  .
 Node_C-vnode2 [0xC00]     |             Node_B-vnode1 [0x300]
      \                    |                    /
       \                   |                   /
        \                  |                  /
         \                 +                 /
          \                                 /
     Node_B-vnode2 [0x900]             Node_A-vnode2 [0x600]
           .                               .
              .                         .
                   .        |        .
                      Node_C-vnode1 [0x800]
```
Data dengan kunci `K` di-hash. Kunci bergerak searah jarum jam (*clockwise*) hingga menemukan token pertama yang nilainya $\ge hash(K)$. Node pemilik token tersebut adalah koordinator dan replika pertama dari data tersebut.

---

### 7. Simple Example & Practical Example

Implementasi referensi berikut dibangun menggunakan **Go (v1.21+)** tanpa dependensi eksternal, mengimplementasikan algoritma **Consistent Hash Ring dengan Virtual Nodes** dan **Storage Engine LSM-Tree In-Memory Minimalist**.

#### File: `storage/ring.go`
```go
package storage

import (
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"sort"
	"strconv"
	"sync"
)

// Ring represents a distributed consistent hash ring.
type Ring struct {
	sync.RWMutex
	vnodesFactor int               // Number of virtual nodes per physical node
	ring         []uint32          // Sorted list of token hashes
	nodeMap      map[uint32]string // Token hash -> Physical Node Identifier
	nodes        map[string]bool   // Set of physical nodes
}

func NewRing(vnodesFactor int) *Ring {
	return &Ring{
		vnodesFactor: vnodesFactor,
		ring:         make([]uint32, 0),
		nodeMap:      make(map[uint32]string),
		nodes:        make(map[string]bool),
	}
}

func (r *Ring) hash(val string) uint32 {
	hasher := sha256.New()
	hasher.Write([]byte(val))
	digest := hasher.Sum(nil)
	return binary.BigEndian.Uint32(digest[0:4])
}

func (r *Ring) AddNode(node string) {
	r.Lock()
	defer r.Unlock()

	if r.nodes[node] {
		return
	}
	r.nodes[node] = true

	for i := 0; i < r.vnodesFactor; i++ {
		vnodeKey := node + "#" + strconv.Itoa(i)
		token := r.hash(vnodeKey)
		r.ring = append(r.ring, token)
		r.nodeMap[token] = node
	}
	sort.Slice(r.ring, func(i, j int) bool {
		return r.ring[i] < r.ring[j]
	})
}

func (r *Ring) RemoveNode(node string) {
	r.Lock()
	defer r.Unlock()

	if !r.nodes[node] {
		return
	}
	delete(r.nodes, node)

	newRing := make([]uint32, 0, len(r.ring)-(r.vnodesFactor))
	for _, token := range r.ring {
		if r.nodeMap[token] == node {
			delete(r.nodeMap, token)
		} else {
			newRing = append(newRing, token)
		}
	}
	r.ring = newRing
}

// GetPreferenceList returns the N unique physical nodes responsible for a key.
func (r *Ring) GetPreferenceList(key string, n int) ([]string, error) {
	r.RLock()
	defer r.RUnlock()

	if len(r.nodes) == 0 {
		return nil, fmt.Errorf("empty hash ring")
	}
	if n > len(r.nodes) {
		n = len(r.nodes)
	}

	token := r.hash(key)
	idx := sort.Search(len(r.ring), func(i int) bool {
		return r.ring[i] >= token
	})

	if idx == len(r.ring) {
		idx = 0 // Wrap around to the beginning of the ring
	}

	result := make([]string, 0, n)
	seen := make(map[string]bool)

	for len(result) < n {
		physicalNode := r.nodeMap[r.ring[idx]]
		if !seen[physicalNode] {
			seen[physicalNode] = true
			result = append(result, physicalNode)
		}
		idx = (idx + 1) % len(r.ring)
	}

	return result, nil
}
```

#### File: `storage/lsm_core.go`
```go
package storage

import (
	"bytes"
	"errors"
	"sync"
	"time"
)

var ErrKeyNotFound = errors.New("key does not exist or has been deleted")

// DataEntry represents a single mutable record with tombstone support.
type DataEntry struct {
	Key       string
	Value     []byte
	Timestamp int64
	IsDeleted bool
}

// MemTable is an in-memory concurrent storage structure.
type MemTable struct {
	sync.RWMutex
	data map[string]DataEntry
	size int
}

func NewMemTable() *MemTable {
	return &MemTable{
		data: make(map[string]DataEntry),
	}
}

func (m *MemTable) Put(key string, value []byte) {
	m.Lock()
	defer m.Unlock()

	entry := DataEntry{
		Key:       key,
		Value:     value,
		Timestamp: time.Now().UnixNano(),
		IsDeleted: false,
	}
	m.size += len(key) + len(value)
	m.data[key] = entry
}

func (m *MemTable) Delete(key string) {
	m.Lock()
	defer m.Unlock()

	entry := DataEntry{
		Key:       key,
		Value:     nil,
		Timestamp: time.Now().UnixNano(),
		IsDeleted: true,
	}
	m.size += len(key)
	m.data[key] = entry
}

func (m *MemTable) Get(key string) (DataEntry, bool) {
	m.RLock()
	defer m.RUnlock()

	val, exists := m.data[key]
	return val, exists
}

// BloomFilter provides fast negative membership tests for storage keys.
type BloomFilter struct {
	bitset []bool
	size   uint
}

func NewBloomFilter(size uint) *BloomFilter {
	return &BloomFilter{
		bitset: make([]bool, size),
		size:   size,
	}
}

func (bf *BloomFilter) hash(key string, seed uint) uint {
	var h uint = seed
	for i := 0; i < len(key); i++ {
		h = (h * 31) + uint(key[i])
	}
	return h % bf.size
}

func (bf *BloomFilter) Add(key string) {
	bf.bitset[bf.hash(key, 7)] = true
	bf.bitset[bf.hash(key, 31)] = true
	bf.bitset[bf.hash(key, 127)] = true
}

func (bf *BloomFilter) MayContain(key string) bool {
	return bf.bitset[bf.hash(key, 7)] &&
		bf.bitset[bf.hash(key, 31)] &&
		bf.bitset[bf.hash(key, 127)]
}

// ImmutableSSTable represents a flushed read-only table on disk.
type ImmutableSSTable struct {
	Filter *BloomFilter
	Data   []DataEntry
}

// StorageNode mimics a production distributed storage node engine.
type StorageNode struct {
	sync.RWMutex
	MemTable  *MemTable
	SSTables  []*ImmutableSSTable
	threshold int
}

func NewStorageNode(flushThresholdBytes int) *StorageNode {
	return &StorageNode{
		MemTable:  NewMemTable(),
		SSTables:  make([]*ImmutableSSTable, 0),
		threshold: flushThresholdBytes,
	}
}

func (sn *StorageNode) Write(key string, val []byte) {
	sn.Lock()
	defer sn.Unlock()

	sn.MemTable.Put(key, val)
	if sn.MemTable.size >= sn.threshold {
		sn.flushUnsafe()
	}
}

func (sn *StorageNode) Delete(key string) {
	sn.Lock()
	defer sn.Unlock()

	sn.MemTable.Delete(key)
	if sn.MemTable.size >= sn.threshold {
		sn.flushUnsafe()
	}
}

// flushUnsafe dumps active MemTable into an immutable SSTable. Caller must hold write lock.
func (sn *StorageNode) flushUnsafe() {
	bf := NewBloomFilter(1024)
	entries := make([]DataEntry, 0, len(sn.MemTable.data))

	for k, v := range sn.MemTable.data {
		bf.Add(k)
		entries = append(entries, v)
	}

	sstable := &ImmutableSSTable{
		Filter: bf,
		Data:   entries,
	}

	// Prepend so newer SSTables are evaluated first
	sn.SSTables = append([]*ImmutableSSTable{sstable}, sn.SSTables...)
	sn.MemTable = NewMemTable()
}

func (sn *StorageNode) Read(key string) ([]byte, error) {
	sn.RLock()
	defer sn.RUnlock()

	// 1. Check active MemTable
	if entry, found := sn.MemTable.Get(key); found {
		if entry.IsDeleted {
			return nil, ErrKeyNotFound
		}
		return entry.Value, nil
	}

	// 2. Fall-through: Traverse SSTables from newest to oldest
	for _, sstable := range sn.SSTables {
		if !sstable.Filter.MayContain(key) {
			continue // Bloom filter saved disk/block search
		}

		for _, entry := range sstable.Data {
			if entry.Key == key {
				if entry.IsDeleted {
					return nil, ErrKeyNotFound
				}
				return entry.Value, nil
			}
		}
	}

	return nil, ErrKeyNotFound
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Migrasi Klaster Cassandra Tier-1 Financial Core Banking
* **Konteks:** Sebuah bank digital multinasional memproses $120.000$ transaksi/detik pada puncaknya. Klaster Apache Cassandra (250 Node) mengalami penurunan drastis pada SLA latency $p99$ dari $15\text{ms}$ melonjak ke $1800\text{ms}$.
* **Akar Masalah (Root Cause Failure Analysis):**
  1. *Tombstone Overload:* Pola penulisan event streaming menggunakan sistem mutasi status dengan flag delete tinggi. Pembacaan range query memicu pembacaan lebih dari $100.000$ tombstone cell per request, mengakibatkan JVM GC Pause mencapai 8 detik (*stop-the-world*).
  2. *Hotspotting Token Range:* Skema pengacakan UUID v1 berkorelasi dengan node waktu yang sama, memusatkan alokasi partisi pada rentang token sempit.
  3. *STCS Resource Exhaution:* Pemadatan Size-Tiered memakan $48\%$ disk cadangan, memicu kegagalan partisi OS saat compacting file berukuran 400GB.
* **Arsitektur Solusi & Resolusi Rekayasa:**
  * **Pola Transisi Compaction:** Berpindah dari STCS ke *Leveled Compaction Strategy* (LCS). Membatasi ukuran SSTable stabil pada 160MB, membatasi disk I/O amplification dan overhead GC.
  * **Optimasi Partisi:** Merestrukturisasi partition key menjadi `(account_id, bucket_epoch_day)` untuk membatasi ukuran partisi maksimal $\le 50\text{MB}$.
  * **Tuning Parameter Engine:**
    ```yaml
    # cassandra.yaml (Enterprise Production Tuned)
    tombstone_failure_threshold: 50000
    tombstone_warn_threshold: 1000
    gc_grace_seconds: 86400 # Turun dari 10 hari ke 1 hari untuk cluster tanpa node mati berkepanjangan
    memtable_allocation_type: offheap_objects
    concurrent_compactors: 8
    compaction_throughput_mb_per_sec: 128
    ```
  * **Hasil:** Latensi $p99$ kembali stabil pada $8.2\text{ms}$, beban I/O turun sebesar $42\%$, dan insiden OOM akibat GC pause tereliminasi secara menyeluruh.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter Desain | Pilihan A | Pilihan B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Storage Engine** | **B-Tree** | **LSM-Tree** | B-Tree: Baca acak sangat cepat ($O(\log N)$), Write latency tinggi karena random write dan WAF tinggi. LSM-Tree: Write throughput luar biasa tinggi ($O(1)$ amortized), Read query overhead lebih tinggi ($RAF > 1$), background compaction membebani CPU & Disk I/O. |
| **Consistency Mode** | **Linearizable (Paxos/Raft)** | **Eventual (Dynamo $R+W \le N$)** | Consensus: Mencegah *stale reads* dan inkonsistensi mutlak, namun latensi tulis dibatasi RTT antar-node mayoritas; ketersediaan hang saat partisi $> (N-1)/2$. Eventual: Ketersediaan mutlak, latensi minimal, namun memerlukan resolusi konflik kompleks (LWW, CRDTs). |
| **Compaction Strategy** | **Size-Tiered (STCS)** | **Leveled (LCS)** | STCS: Write I/O rendah selama ingestion awal; overhead disk ganda, read latency buruk. LCS: Read queries terisolasi pada sedikit SSTable ($O(1)$ lookup level), ukuran disk stabil; Write amplification meningkat tajam, IOPS NVMe terkuras. |
| **Topology Resolution** | **Strict Quorum ($R+W=N+1$)** | **Sloppy Quorum + Handoff** | Strict Quorum: Menjamin *Read-Your-Writes*, tetapi menolak request jika replika utama down. Sloppy Quorum: Tetap menerima transaksi meski jaringan pecah, namun menunda linearitas data hingga hinted handoff selesai dikirim. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Anti-Pattern: Mengabaikan Akumulasi Tombstone
* *Gejala:* Latensi query `SELECT ... WHERE ...` meningkat linier terhadap waktu meski total data aktif statis.
* *Diagnosa:* Eksekusi `nodetool cfstats` atau setara; perhatikan rasio `tombstone cells scanned per query`. Jika rasio $> 100$, query engine membuang CPU untuk membaca data yang sudah mati.
* *Solusi:* Kurangi `gc_grace_seconds` pada data yang tidak memerlukan perbaikan replikasi lama, atau ubah desain data dari skema delete/update ke skema time-to-live (*TTL partition rotation* via dropped tables).

#### 10.2 Jebakan LWW (Last-Write-Wins) dengan System Clock Drift
* *Gejala:* Data yang diperbarui belakangan hilang secara misterius (*silent data loss*), digantikan oleh data lama.
* *Diagnosa:* NTP drift di server melampaui toleransi ($>50\text{ms}$). Node A dengan clock lambat menulis data dengan timestamp lebih kecil dari node B yang clock-nya cepat.
* *Solusi:* Jangan gunakan `System.currentTimeMillis()` untuk LWW. Terapkan *Hybrid Logical Clocks* (HLC) atau delegasikan resolusi konflik menggunakan *Conflict-Free Replicated Data Types* (CRDTs).

#### 10.3 Failure Mode: Split-Brain pada Quorum Storage
* *Gejala:* Dua node merasa memiliki mandat sebagai leader master, menerima penulisan berbeda dari dua segmen klien jaringan yang terisolasi.
* *Mitigasi:*
  1. Enforce konfigurasi node ganjil ($N = 2F + 1$).
  2. Implementasikan *Epoch Ticketing* atau *Fencing Tokens*: Setiap kali node baru mengklaim kepemimpinan, ia menerbitkan nomor generasi monotonic yang harus diverifikasi oleh storage driver. Modifikasi dari generasi lama ditolak.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Storage Partition Alignment:** Pastikan alokasi ukuran data pada satu partisi logis tidak melebihi ambang batas $100\text{MB}$.
2. [ ] **Direct I/O Tuning:** Bypass kernel OS page cache untuk aplikasi basis data yang mengelola buffer pool sendiri (misalnya InnoDB) guna menghindari *double buffering*.
3. [ ] **Bloom Filter Sizing:** Tentukan false positive probability ($p$) yang realistis (misalnya $1\%$). Hitung kebutuhan memori:
   $$m = -\frac{n \ln p}{(\ln 2)^2}$$
4. [ ] **Read Repair Rate Control:** Batasi eksekusi *read-repair* sinkronus menjadi asinkronus dengan sampling rate terukur (misal $10\%$) untuk memangkas latensi tail $p99.9$.
5. [ ] **Hardware Isolation:** Pisahkan drive fisik NVMe untuk WAL/CommitLog (Latency-critical Sequential Write) dengan drive SSTable/Data Files (Throughput-critical Random/Compaction I/O).
6. [ ] **Disk Space Watermark:** Tetapkan threshold alarm monitoring disk pada batas maksimum $70\%$. Compaction LSM-Tree membutuhkan ruang kerja dinamis yang besar.

---

### 12. Hands-on Practice

Buka terminal dan bangun lingkungan implementasi terdistribusi sederhana di direktori `hands-on/m02/`.

#### Langkah 1: Setup Workspace & Struktur Direktori
```bash
mkdir -p hands-on/m02/distributed-storage
cd hands-on/m02/distributed-storage
go mod init enterprise/distributed-storage
```

#### Langkah 2: Salin File Source Code
Letakkan berkas `ring.go` dan `lsm_core.go` ke dalam folder bernama `engine/`.

#### Langkah 3: Implementasikan Entry Point Pengujian Terdistribusi
Buat file `main.go`:
```go
package main

import (
	"enterprise/distributed-storage/storage"
	"fmt"
	"log"
)

func main() {
	fmt.Println("[+] Inisialisasi Consistent Hash Ring...")
	ring := storage.NewRing(100) // 100 Virtual Nodes per Node

	// Menambahkan 3 Node Penyimpanan Fisik
	ring.AddNode("node-alpha")
	ring.AddNode("node-bravo")
	ring.AddNode("node-charlie")

	// Peta instansiasi Node Engine lokal (In-Memory LSM)
	clusterNodes := map[string]*storage.StorageNode{
		"node-alpha":   storage.NewStorageNode(4096),
		"node-bravo":   storage.NewStorageNode(4096),
		"node-charlie": storage.NewStorageNode(4096),
	}

	keys := []string{
		"usr_account_101",
		"usr_account_102",
		"usr_account_103",
		"usr_account_104",
		"usr_account_105",
	}

	replicationFactor := 2

	// Simulasi Penulisan Data dengan Replikasi
	fmt.Println("\n[+] Menjalankan Ingestion Data (Quorum Replikasi)...")
	for _, key := range keys {
		replicas, err := ring.GetPreferenceList(key, replicationFactor)
		if err != nil {
			log.Fatalf("Gagal memetakan ring: %v", err)
		}

		payload := []byte(fmt.Sprintf("payload-data-for-%s", key))
		fmt.Printf("Kunci: %-16s dialokasikan ke Node: %v\n", key, replicas)

		for _, targetNode := range replicas {
			clusterNodes[targetNode].Write(key, payload)
		}
	}

	// Verifikasi Pembacaan Data
	fmt.Println("\n[+] Memverifikasi Konsistensi Data dari Replika Target...")
	for _, key := range keys {
		replicas, _ := ring.GetPreferenceList(key, replicationFactor)
		targetNode := replicas[0] // Membaca dari replika pertama

		val, err := clusterNodes[targetNode].Read(key)
		if err != nil {
			log.Fatalf("Error membaca kunci %s di node %s: %v", key, targetNode, err)
		}
		fmt.Printf("Sukses Read [%s] dari %-12s: Nilai = %s\n", key, targetNode, string(val))
	}

	// Simulasi Penghapusan dan Tombstone Propagation
	fmt.Println("\n[+] Menjalankan Operasi Hapus (Tombstone)...")
	delKey := "usr_account_103"
	replicas, _ := ring.GetPreferenceList(delKey, replicationFactor)
	for _, targetNode := range replicas {
		clusterNodes[targetNode].Delete(delKey)
	}

	// Baca Kembali Data yang Dihapus
	_, err := clusterNodes[replicas[0]].Read(delKey)
	if err == storage.ErrKeyNotFound {
		fmt.Printf("Verifikasi Berhasil: Kunci '%s' ditandai sebagai terhapus (Tombstone divalidasi).\n", delKey)
	} else {
		log.Fatalf("Kegagalan penanganan tombstone! Return: %v", err)
	}
}
```

#### Langkah 4: Eksekusi dan Amati Hasil
```bash
go run main.go
```

Pastikan output mencerminkan distribusi token merata dan konfirmasi pembacaan data konsisten antar node.

---

### 13. Exercise

#### Level: Easy
Ubah implementasi `storage/ring.go` agar fungsi `hash` menggunakan algoritma **FNV-1a** alih-alih `SHA-256`. Ukur rasio disparitas (standar deviasi) pemetaan 10.000 key ke 5 node fisik antara kedua fungsi hash tersebut.

#### Level: Medium
Tambahkan mekanisme **Version Vector (Vector Clock)** pada struct `DataEntry` di `storage/lsm_core.go`. Saat fungsi `Read` dipanggil pada koordinator yang membaca dari beberapa replika, buat logika pembanding yang mendeteksi:
1. Mana data yang mendominasi (*causally newer*).
2. Jika terjadi *concurrent update conflict*, gabungkan atau kembalikan array kedua versi ke client.

#### Level: Hard
Kembangkan subsistem **SSTable Compaction Thread Worker** yang berjalan di background. Ketika total SSTable mencapai 4 file:
1. Baca seluruh iterasi data SSTable secara streaming (Mirip *Merge Sort* $K$-Way).
2. Buang duplikasi kunci dan pertahankan data dengan timestamp terbaru.
3. Hapus baris yang memiliki tanda `IsDeleted == true` (Purge Tombstones).
4. Tulis hasil akhir ke file SSTable konsolidasi baru dan secara atomik swap slice SSTable lama.

---

### 14. Challenge

**Skenario Sistem:** Anda adalah Lead Architect pada platform pembayaran global yang memproses miliaran transaksi pertukaran valuta asing. Platform ini tidak boleh mengalami *downtime* (Zero Downtime SLA 99.999%), tidak boleh mentoleransi *double-spending* atau *data lost*, namun harus beroperasi lintas 3 region cloud yang berbeda (misalnya: Frankfurt, Singapore, Virginia). Latensi RTT antar-region adalah $180\text{ms}$.

**Tugas Anda:**
1. Rancang arsitektur penyimpanan hybrid multi-region yang mengombinasikan penyimpanan stateful lokal (LSM-Tree engine) dengan lapisan konsensus terdistribusi.
2. Selesaikan dilema pembagian jaringan (*Network Partition*) antara Singapore dan Frankfurt: Saat link komunikasi antarbenua terputus total selama 20 menit, tentukan region mana yang berhak menerima mutasi balance, bagaimana mekanisme fencing-nya, dan bagaimana sistem menyelesaikan rekonsiliasi state (*anti-entropy synchronization*) tanpa merusak integritas ledger keuangan ketika partisi pulih.
3. Tuliskan blueprint arsitektur berupa spesifikasi dokumen teknis lengkap, meliputi data model, routing table token ring, dan pseudocode algoritma resolusi ledger.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konseptual Fundamental (Basic)
1. Mengapa LSM-Tree memiliki performa penulisan (*write throughput*) yang jauh lebih tinggi dibandingkan B-Tree tradisional pada media disk NVMe/HDD?
2. Dalam rumus Quorum $R + W > N$, apa implikasi sistematis jika sebuah arsitektur dikonfigurasi dengan $N=3, W=1, R=1$?
3. Apa fungsi utama *Bloom Filter* pada sebuah file SSTable yang disimpan di disk?
4. Mengapa operasi penghapusan (*delete*) pada basis data terdistribusi seperti Cassandra tidak langsung membuang data dari disk melainkan menulis *Tombstone*?
5. Apa permasalahan utama yang muncul jika kita hanya menggunakan *Consistent Hashing Ring* polos tanpa menerapkan *Virtual Nodes* (vnodes)?

#### Bagian B: Analisis Arsitektur (Intermediate)
6. Jelaskan fenomena *Write Amplification* pada LSM-Tree. Faktor arsitektural apa yang paling dominan menyumbang kenaikan angka WAF pada strategi Leveled Compaction?
7. Bagaimana cara kerja mekanisme *Hinted Handoff* saat sebuah node target replikasi mengalami kegagalan jaringan sementara? Apa risiko yang mungkin terjadi terhadap konsistensi pembacaan?
8. Mengapa NTP drift (*clock skew*) dapat merusak integritas data pada sistem penyimpanan yang mengandalkan resolusi konflik *Last-Write-Wins* (LWW)?
9. Dalam skenario apa *Size-Tiered Compaction Strategy* (STCS) lebih disukai daripada *Leveled Compaction Strategy* (LCS), dan apa bahaya terbesarnya terkait alokasi kapasitas storage (*disk headroom*)?
10. Bagaimana struktur data *Merkle Tree* meminimalkan konsumsi bandwidth jaringan selama proses sinkronisasi background (*Anti-Entropy Repair*) antar dua replika data?

#### Bagian C: Pemecahan Masalah Produksi (Skenario Kasus)
11. **Skenario Kasus 1:**
    Sebuah klaster penyimpanan basis data 5-node terdistribusi ($N=5, W=3, R=3$) mengalami partisi jaringan: Node 1 dan Node 2 terisolasi di Partisi A, sedangkan Node 3, Node 4, dan Node 5 terisolasi di Partisi B. Klien A terhubung ke Partisi A dan Klien B terhubung ke Partisi B. Jelaskan secara teknis apa yang dialami oleh Klien A dan Klien B ketika masing-masing mencoba melakukan operasi penulisan (*write*)!
12. **Skenario Kasus 2:**
    Tim SRE melaporkan bahwa query pencarian individual (*Point Lookup*) pada basis data LSM-Tree tiba-tiba melonjak latensinya dari $2\text{ms}$ ke $150\text{ms}$ setelah operasi batch delete massal sebesar 50 juta record selesai dijalankan. Namun metrik CPU dan Memori klaster terpantau rendah. Apa akar masalah internal pada storage engine, dan langkah remediasi apa yang harus diambil tanpa merestart node?
13. **Skenario Kasus 3:**
    Dalam evaluasi arsitektur multi-DC, Anda mendapati bahwa pembacaan data dengan level konsistensi kuorum lokal (*LOCAL_QUORUM*) sering kali mengembalikan data stale (versi lama) beberapa detik setelah klien menerima respons penulisan sukses dari DC yang berbeda. Jelaskan anomali arsitektur apa yang terjadi di lapisan koordinasi dan replikasi antar-DC tersebut!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian A: Basic
1. **LSM-Tree** mengubah semua mutasi (insert, update, delete) menjadi operasi tulis sekuensial (*sequential append*) ke WAL dan MemTable di memori, menghindari *random disk I/O*. B-Tree memerlukan pencarian lokasi halaman fisik dan melakukan pembaruan di tempat (*in-place updates*), memicu penulisan acak dan penulisan ulang seluruh blok halaman (*write amplification*).
2. Jika $R=1, W=1, N=3$, maka $R + W = 2 \ngtr 3$. Kuorum tidak terpenuhi. Ada risiko tinggi terjadinya *stale read* (klien membaca data usang) dan potensi *conflict update* karena replika baca belum tentu mencakup node yang baru saja menerima data tulis.
3. Menghindari operasi pembacaan disk yang tidak perlu (*unnecessary disk I/O*). Bloom filter secara deterministik dapat memastikan apakah suatu kunci **pasti tidak ada** di dalam SSTable. Jika dipastikan tidak ada, pembacaan file SSTable tersebut diabaikan sepenuhnya.
4. Karena file SSTable bersifat *immutable* (tidak dapat diubah setelah ditulis). Menghapus data secara langsung membutuhkan penulisan ulang seluruh file SSTable di disk yang sangat mahal. Tombstone ditulis sebagai penanda mutasi baru bahwa record tersebut sudah tidak valid. Data lama baru akan dibuang secara fisik ketika proses *Compaction* berlangsung.
5. Node fisik dapat terdistribusi secara tidak merata pada cincin token, menyebabkan pembagian beban yang timpang (*heterogeneity & non-uniform load*). Sebagian node menjadi *hotspot* (menerima beban sangat tinggi) sementara node lain menganggur. Vnodes memecah setiap node menjadi ratusan titik virtual untuk meratakan distribusi data secara statistik.

#### Bagian B: Intermediate
6. WAF terjadi karena satu byte data ditulis berulang kali ke storage selama siklus hidupnya (WAL $\to$ Flushed SSTable $\to$ Compaction berkali-kali). Pada Leveled Compaction, data di level $L_k$ harus digabungkan dan ditulis ulang bersama file-file yang bertumpukan di level $L_{k+1}$ (yang berukuran $10\times$ lebih besar), sehingga WAF dapat melonjak hingga angka 10–30x.
7. Node koordinator menyimpan mutasi data secara lokal di buffer khusus (*hint*) ketika node replika tujuan down/unreachable. Begitu node replika kembali online, koordinator mengirimkan hint tersebut. Risikonya: Jika klien membaca data dari node replika yang baru pulih sebelum hinted handoff selesai dikirim, pembacaan tersebut dapat mengembalikan data basi (*stale read*) jika konsistensi pembacaan tidak menggunakan *Strict Quorum*.
8. LWW memutuskan versi data terbaru hanya berdasarkan nilai timestamp mentah. Jika NTP drift membuat jam di Server A tertinggal 100ms dari Server B, penulisan di Server A yang secara riil terjadi belakangan (*later in physical time*) akan memiliki timestamp lebih rendah dan dibuang (*silently dropped*) oleh resolusi konflik, menyebabkan hilangnya data pembaruan yang sah.
9. STCS ideal untuk sistem yang didominasi oleh operasi tulis massal secara serial (*append-heavy logging / telemetry*). Bahaya terbesarnya adalah *Disk Headroom Exhaustion*: Pada file SSTable yang sangat besar, STCS memerlukan ruang disk bebas setidaknya $50\%$ dari kapasitas total untuk dapat menuntaskan proses penggabungan SSTable berukuran raksasa.
10. Merkle Tree adalah pohon hash di mana daun adalah hash dari data kunci individual, dan simpul induk adalah hash dari gabungan anak-anaknya. Dua node replika cukup membandingkan hash simpul akar (*root hash*). Jika sama, seluruh data identik (cukup 1 transmisi data kecil via jaringan). Jika berbeda, replika menelusuri cabang pohon ke bawah untuk mengisolasi rentang data yang berbeda secara presisi tanpa perlu mentransfer seluruh dataset.

#### Bagian C: Kasus Produksi
11. **Analisis Partisi Jaringan:**
    * **Klien A (Partisi A, Node 1 & 2):** Menghadapi kegagalan penulisan (*Write Failure*). Node yang tersedia hanya 2, sedangkan konfigurasi mensyaratkan kuorum tulis $W=3$. Partisi A tidak dapat membentuk kuorum mayoritas.
    * **Klien B (Partisi B, Node 3, 4 & 5):** Berhasil melakukan penulisan (*Write Success*). Jumlah node aktif adalah 3, memenuhi kuorum $W=3$ dari total $N=5$. Partisi B adalah partisi mayoritas (*majority partition*) yang sah.
12. **Akar Masalah & Remediasi Tombstone:**
    * *Root Cause:* Operasi delete massal menciptakan 50 juta *tombstone records*. Point lookup harus membaca dan memvalidasi puluhan ribu record tombstone sebelum menentukan status kunci terbaru. Indeks cache tidak efektif karena filter harus memindai rentang logikal data mati.
    * *Remediasi Tanpa Restart:* Picu operasi pemadatan paksa pada level yang terdampak (*Forced Major Compaction*) secara bertahap via command console (misalnya `nodetool compact <keyspace> <table>`). Turunkan parameter `gc_grace_seconds` secara dinamis ke 0 untuk sementara waktu pada sesi perbaikan agar compaction langsung memusnahkan tombstone tanpa menunggu masa tenggang retensi.
13. **Anomali Replikasi Multi-DC:**
    * *Akar Masalah:* Operasi tulis dieksekusi dengan level konsistensi lokal (misalnya `LOCAL_QUORUM`) di DC-1. Node koordinator di DC-1 mengonfirmasi status sukses ke klien segera setelah kuorum node lokal terpenuhi, lalu mengirimkan pembaruan ke DC-2 secara **asinkronus**. Ketika klien lain membaca data di DC-2 menggunakan level `LOCAL_QUORUM` sebelum replikasi asinkronus lintas benua selesai tiba, terjadi pembacaan data lama (*cross-datacenter stale read*).
    * *Solusi Arsitektur:* Jika use case memerlukan read-your-writes lintas DC, arsitektur harus mengalihkan konsistensi menjadi `EACH_QUORUM` (tulis menunggu kuorum di setiap DC, latensi bertambah) atau mengarahkan pembacaan klien ke DC tempat penulisan awal berlangsung menggunakan *Sticky Session Routing* berbasis token partisi.

---

### 16. Summary

1. **Storage Engine Foundations:** Pemilihan antara LSM-Tree dan B-Tree adalah determinan paling fundamental dalam performa penyimpanan terdistribusi. LSM-Tree mengorbankan read amplification dan utilisasi disk background (compaction) untuk memperoleh write throughput maksimal, sedangkan B-Tree memprioritaskan read latency yang stabil dengan konsekuensi write amplification tinggi.
2. **Dynamo Consistency Paradigm:** Replikasi tanpa pemimpin (*Leaderless*) mengandalkan pembuktian matematis Quorum ($R + W > N$). Penyesuaian konfigurasi ini menentukan trade-off langsung antara ketersediaan (*Availability*) dan konsistensi data (*Consistency*) di bawah tekanan partisi jaringan.
3. **Partition Scalability:** *Consistent Hashing* yang dipadukan dengan *Virtual Nodes* (vnodes) adalah standar de-facto untuk mencegah fenomena data skews dan cascading node failures dalam klaster berskala ribuan node komoditas.
4. **Resiliency & Self-Healing:** Mekanisme anti-entropy modern seperti *Merkle Trees*, *Read Repair*, dan *Hinted Handoff* memungkinkan basis data terdistribusi memulihkan integritas state secara otonom dari kegagalan jaringan temporer (*transient network partitions*) tanpa intervensi manual.