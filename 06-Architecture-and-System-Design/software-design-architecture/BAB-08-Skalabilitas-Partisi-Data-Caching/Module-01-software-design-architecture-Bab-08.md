## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Software Design & Architecture
*   **Kategori:** 06-Architecture-and-System-Design
*   **Kode Modul:** SDA-06-08-01
*   **Judul Modul:** Skalabilitas, Partisi Data, & Strategi Caching: Vertical vs Horizontal Scaling, Database Read Replicas, Sharding, Multi-tier Caching (Local vs Distributed), Cache Invalidation
*   **Tingkat Kesulitan:** Advanced / Lanjutan
*   **Estimasi Waktu Penyelesaian:** 8 – 10 Jam Pembelajaran Mandiri + Praktik Lab
*   **Prasyarat:** 
    *   Pemahaman mendalam mengenai arsitektur sistem berbasis REST/gRPC.
    *   Dasar-dasar RDBMS (ACID, Indexing, Transaksi) dan NoSQL (Key-Value Store).
    *   Dasar-dasar konkurensi (Thread-safety, Mutex, Race Conditions).
    *   Pengalaman implementasi minimal satu bahasa backend sistem (Go, Java, atau Rust).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis & Mengukur Hambatan Skalabilitas (Scaling Bottlenecks):** Menghitung batas komputasi dan I/O pada arsitektur monolitik/vertikal serta memproyeksikan kapan sistem harus beralih ke penskalaan horizontal menggunakan *Amdahl’s Law* dan *Universal Scalability Law (USL)*.
2.  **Merancang Topologi Basis Data Terdistribusi:** Mengimplementasikan pola *Primary-Replica (Master-Slave)*, menghitung serta memitigasi dampak dari *Replication Lag* (*Eventual Consistency*), dan menerapkan strategi routing baca/tulis (*Read-Write Splitting*).
3.  **Mengarsitekturi Skema Database Sharding:** Mengembangkan algoritma partisi horizontal data menggunakan *Range-based*, *Hash-based*, dan *Consistent Hashing with Virtual Nodes* untuk menghindari *hotspots* data.
4.  **Membangun Arsitektur Multi-Tier Caching:** Menggabungkan *L1 In-Memory Local Cache* (Process Memory) dengan *L2 Distributed Cache* (Redis/KeyDB) secara koheren menggunakan protokol sinkronisasi berbasis *Pub/Sub*.
5.  **Mengatasi Anomali Caching Kritis:** Mengeliminasi masalah *Cache Stampede*, *Thundering Herd*, *Cache Penetration*, dan *Cache Avalanche* melalui teknik *SingleFlight*, *Probabilistic Early Expiration (XFetch)*, dan *Bloom Filters*.
6.  **Mengimplementasikan Pola Cache Invalidation:** Menerapkan strategi *Cache-Aside*, *Write-Through*, *Write-Behind (Write-Back)*, dan *Change Data Capture (CDC)* dengan menjamin integritas data yang konsisten.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [SISTEM SKALABILITAS TINGGI]
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
     [STRATEGI KOMPUTASI & DB]                             [STRATEGI DATA ACCESS]
             │                                                     │
   ┌─────────┴─────────┐                                 ┌─────────┴─────────┐
   ▼                   ▼                                 ▼                   ▼
[SCALING]          [PARTITIONING]                    [CACHING]         [CONSISTENCY]
   │                   │                                 │                   │
   ├─ Vertical         ├─ Read Replicas                  ├─ Multi-tier       ├─ Cache-Aside
   │  (Scale-Up)       │  (Master-Slave)                 │  (L1 Local vs     ├─ Write-Through
   │                   │  └─ Replication Lag             │   L2 Distributed) ├─ Write-Behind
   └─ Horizontal       │                                 │                   │
      (Scale-Out)      └─ Sharding                       ├─ Anomalies        └─ Invalidation
                          ├─ Range/Directory             │  ├─ Stampede         ├─ TTL / Jitter
                          ├─ Hash-based                  │  ├─ Penetration      ├─ Pub/Sub Purge
                          └─ Consistent Hashing          │  └─ Avalanche        └─ CDC (Debezium)
                             (Virtual Nodes)             └─ Algorithms (LRU, LFU, ARC)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada fase awal pengembangan perangkat lunak, sistem monolitik sederhana yang terhubung ke satu instans basis data relasional tunggal sudah mencukupi. Namun, seiring dengan lonjakan volume trafik pengguna dan eksponensialnya data yang disimpan, sistem akan membentur tembok performa (*performance wall*).

1.  **Keterbatasan Fisik Skalabilitas Vertikal:** Menambah CPU, RAM, dan NVMe SSD pada satu mesin (*scale-up*) memiliki batas fisis perangkat keras dan batas efisiensi biaya (*diminishing returns*). Mesin berkapasitas terbesar di penyedia cloud memiliki harga eksponensial per satuan performa dan tetap memiliki titik kegagalan tunggal (*Single Point of Failure* / SPOF).
2.  **I/O Bottleneck Basis Data:** Sebagian besar aplikasi modern bersifat *Read-Heavy* (rasio baca berbanding tulis dapat mencapai 9:1 atau 100:1). Mengarahkan seluruh query baca ke instans database yang sama yang memproses write locks dan transaksi ACID akan melumpuhkan *throughput* sistem.
3.  **Hukum Amdahl & USL:** Penambahan node komputasi tanpa membagi penyimpanan data secara paralel (*sharding*) akan menyebabkan antrean konkurensi pada basis data pusat. Partisi data dan replikasi adalah satu-satunya metode matematis untuk memperluas kapasitas *throughput* penulisan dan pembacaan.
4.  **Latensi Akses Memori vs Disk:** Mengambil data dari memori lokal (RAM) membutuhkan waktu ~100 nanodetik, dari Redis terdistribusi membutuhkan ~1 milidetik, sementara membaca dari NVMe SSD memakan waktu ~100 mikrodetik, dan disk seek tradisional membutuhkan ~10 milidetik. *Caching* yang dirancang secara tepat bukan sekadar optimasi mikro; ini adalah pembeda antara sistem yang mampu melayani 100.000 Requests Per Second (RPS) dengan latensi sub-10ms atau sistem yang mengalami *cascading failure* di bawah beban yang sama.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Vertical vs Horizontal Scaling
*   **Vertical Scaling (Scale-Up):** Meningkatkan kapasitas sumber daya komputasi (CPU cores, RAM, I/O bandwidth) pada sebuah node server tunggal. Arsitektur aplikasi tidak perlu berubah, namun dibatasi oleh batasan fisik hardware dan biaya yang tidak linier.
*   **Horizontal Scaling (Scale-Out):** Menambahkan node server baru ke dalam kelompok komputasi secara paralel. Membutuhkan *load balancer*, komunikasi jaringan antarnode, dan arsitektur aplikasi nir-status (*stateless*).

### 2. Database Read Replicas
Arsitektur di mana satu node database bertindak sebagai **Primary (Master)** yang menangani seluruh operasi mutasi data (`INSERT`, `UPDATE`, `DELETE`), dan menyebarkan log transaksi (*Write-Ahead Log* / WAL) ke satu atau lebih node **Replica (Slave)**. Node replica secara eksklusif melayani kueri baca (`SELECT`). Arsitektur ini memperkenalkan masalah intrinsik: **Replication Lag**, yang menyebabkan sistem berada dalam status *Eventual Consistency*.

### 3. Database Sharding
Pemisahan basis data secara horizontal dengan membagi baris-baris data dari sebuah tabel ke dalam beberapa basis data fisik yang berbeda (*shards*). Setiap shard memiliki skema yang identik namun hanya menyimpan himpunan data bagian (*subset*) yang unik berdasarkan sebuah **Shard Key**.
*   **Consistent Hashing:** Teknik pemetaan data ke *shard* menggunakan fungsi hash yang meminimalkan relokasi data saat ada penambahan atau pengurangan node secara dinamis.

### 4. Multi-tier Caching (Local vs Distributed)
*   **L1 Cache (In-Process/Local):** Data disimpan langsung di memori RAM proses aplikasi (misalnya: Go `sync.Map`, Java `Caffeine Cache`). Latensi: sub-mikrodetik, tanpa overhead serialisasi atau jaringan, namun data terisolasi per node dan berisiko inkonsisten.
*   **L2 Cache (Distributed):** Data disimpan dalam kluster terpusat di luar proses aplikasi (misalnya: Redis, Memcached). Latensi: 1–3 milidetik (overhead jaringan), namun menyediakan data terpadu yang dapat diakses oleh seluruh instans komputasi.

### 5. Cache Invalidation
Proses menghapus atau memperbarui entri cache ketika data master di basis data berubah. Sesuai ungkapan Phil Karlton: *"There are only two hard things in Computer Science: cache invalidation and naming things."* Kegagalan pada strategi ini menyebabkan *stale data* atau hilangnya integritas transaksional aplikasi.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Mekanisme Consistent Hashing dengan Virtual Nodes

Pada skema konvensional ($hash(key) \pmod N$), perubahan jumlah server $N$ akan menyebabkan mayoritas kunci terpetakan ke server yang salah, memicu *cache miss* massal secara simultan.

Consistent Hashing memetakan kunci dan server ke dalam lingkaran hash virtual (*Hash Ring*) berukuran integer 32-bit ($0$ sampai $2^{32}-1$):
1.  Setiap node fisik dialokasikan beberapa **Virtual Nodes** (misal: 100-250 token per node) pada rentang ring untuk menjamin distribusi beban yang seragam (*uniform distribution*).
2.  Kunci data di-hash menggunakan fungsi hash kriptografis atau non-kriptografis cepat (misalnya Murmur3 atau SHA-256) untuk menghasilkan posisi di ring.
3.  Pencarian shard dilakukan dengan berjalan searah jarum jam (*clockwise*) dari posisi hash kunci sampai menemukan virtual node pertama yang terdaftar (dieksekusi secara efisien menggunakan pencarian biner / Binary Search $O(\log M)$ di mana $M$ adalah total virtual nodes).

### 2. Multi-tier Cache Flow & Invalidation via Pub/Sub

```
[Write Request] ──> [Update DB Master] 
                          │
                          ├──> [Update/Invalidate Redis L2]
                          │
                          └──> [Publish Invalidate Message ke Redis Pub/Sub]
                                     │
             ┌───────────────────────┴───────────────────────┐
             ▼                                               ▼
   [Node A: Invalidate L1]                         [Node B: Invalidate L1]
```

1.  **Read Path:**
    *   Sistem memeriksa L1 Local Memory. Jika *Hit*, data langsung dikembalikan.
    *   Jika *Miss* di L1, sistem mengecek L2 (Redis). Jika *Hit*, data disalin ke L1 dengan konfigurasi TTL pendek (misal: 10-30 detik) guna membatasi risiko desinkronisasi, lalu dikembalikan ke klien.
    *   Jika *Miss* di L2, sistem mengeksekusi *Distributed Mutex* atau *SingleFlight* ke database untuk mencegah fenomena *Thundering Herd*. Hasil baca disimpan ke L2 dan L1.
2.  **Write Path:**
    *   Data ditulis ke DB Primary.
    *   Kunci di-invalidasi di L2 (Redis).
    *   Sinyal pembatalan (*invalidation event*) disiarkan via bus perpesanan (Redis Pub/Sub, Kafka) ke seluruh node komputasi untuk membersihkan kunci pada L1 masing-masing node secara serempak.

### 3. Mitigasi Replication Lag: Read-Your-Own-Writes Consistency

Ketika user melakukan pembaruan profil (tulis ke Primary), lalu seketika merefresh halaman (baca dari Replica), *replication lag* dapat menyebabkan data baru belum tereplikasi ke node Replica, memicu komplain user bahwa data tidak tersimpan.

**Solusi Algoritma (Session / Monotonic Read Token):**
1.  Setelah penulisan berhasil pada Primary, basis data mengembalikan nomor urut transaksi (*Log Sequence Number* / LSN atau timestamp modifikasi terkini).
2.  Klien menyimpan LSN/token ini di session cookie atau header respons.
3.  Pada permintaan baca berikutnya, klien menyertakan token LSN.
4.  Router kueri mengevaluasi:
    *   Jika `Replica_Current_LSN >= Client_LSN`: Kueri dialihkan ke Replica (Aman).
    *   Jika `Replica_Current_LSN < Client_LSN`: Kueri dipaksa rute ke Primary (*Fallback to Master*) atau menunda bacaan hingga replika sinkron.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Arsitektur End-to-End: Multi-Tier Cache, Consistent Hashing Shards, & DB Replicas

```
[ Client Application / Web / Mobile ]
                 │
                 ▼
     [ HTTP Load Balancer / API Gateway ]
                 │
  ┌──────────────┴──────────────┐
  ▼                             ▼
[ App Instance 1 ]            [ App Instance 2 ]
  │   ├── L1 Cache (In-Memory)  │   ├── L1 Cache (In-Memory)
  │   └── SingleFlight Group    │   └── SingleFlight Group
  │                             │
  └──────────────┬──────────────┘
                 │
                 ├──────────────────────────────┐
                 │                              │
                 ▼ (Read/Write L2)              ▼ (Subscribe Invalidate)
      [ Redis Cluster (L2 Cache) ] ◄──── [ Invalidation Pub/Sub Bus ]
                 │
                 ▼ (Cache Miss: Resolve Shard via Consistent Hash Ring)
     [ Data Shard Routing Layer ]
                 │
      ┌──────────┴──────────────────────────────┐
      │                                         │
      ▼ (Key Hash: 0x00000000 - 0x7FFFFFFF)     ▼ (Key Hash: 0x80000000 - 0xFFFFFFFF)
[ SHARD 01 ]                              [ SHARD 02 ]
  ├── Primary Node (Writes)                 ├── Primary Node (Writes)
  │     │                                   │     │
  │     ├─ Async/Semi-Sync WAL Stream       │     ├─ Async/Semi-Sync WAL Stream
  │     ▼                                   │     ▼
  ├── Replica 01 (Reads)                    ├── Replica 01 (Reads)
  └── Replica 02 (Reads)                    └── Replica 02 (Reads)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi minimal algoritma **Consistent Hashing** dalam bahasa pemrograman Go, yang mendasari mekanisme sharding dan partisi data terdistribusi tanpa pergeseran kunci masif.

```go
package main

import (
	"fmt"
	"hash/fnv"
	"sort"
	"strconv"
)

// ConsistentHash melacak ring hash dan virtual nodes
type ConsistentHash struct {
	virtualNodes int               // Jumlah vnodes per node fisik
	ring         []uint32          // Slice token hash terurut
	vnodeMap     map[uint32]string // Peta dari hash token ke ID Node Fisik
}

func NewConsistentHash(virtualNodes int) *ConsistentHash {
	return &ConsistentHash{
		virtualNodes: virtualNodes,
		vnodeMap:     make(map[uint32]string),
	}
}

func (c *ConsistentHash) hash(key string) uint32 {
	h := fnv.New32a()
	h.Write([]byte(key))
	return h.Sum32()
}

// AddNode menambahkan node fisik ke dalam ring dengan sejumlah virtual nodes
func (c *ConsistentHash) AddNode(nodeID string) {
	for i := 0; i < c.virtualNodes; i++ {
		vnodeKey := nodeID + "#VN" + strconv.Itoa(i)
		hashVal := c.hash(vnodeKey)
		c.ring = append(c.ring, hashVal)
		c.vnodeMap[hashVal] = nodeID
	}
	sort.Slice(c.ring, func(i, j int) bool {
		return c.ring[i] < c.ring[j]
	})
}

// GetNode mencari node fisik yang bertanggung jawab terhadap sebuah key
func (c *ConsistentHash) GetNode(key string) string {
	if len(c.ring) == 0 {
		return ""
	}
	hashVal := c.hash(key)

	// Binary search (Clockwise traversal pada hash ring)
	idx := sort.Search(len(c.ring), func(i int) bool {
		return c.ring[i] >= hashVal
	})

	// Jika melampaui elemen terakhir, wrap-around ke indeks 0
	if idx == len(c.ring) {
		idx = 0
	}

	return c.vnodeMap[c.ring[idx]]
}

func main() {
	ch := NewConsistentHash(3) // 3 Virtual nodes per server

	ch.AddNode("db-shard-us-east")
	ch.AddNode("db-shard-eu-central")
	ch.AddNode("db-shard-ap-southeast")

	users := []string{"usr_1001", "usr_1002", "usr_1003", "usr_2004", "usr_9999"}
	for _, u := range users {
		shard := ch.GetNode(u)
		fmt.Printf("User %s dialokasikan ke: %s\n", u, shard)
	}
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah arsitektur produksi yang mendemonstrasikan **Multi-tier Caching** (L1 Local Memory + L2 Redis) menggunakan mekanisme **SingleFlight** untuk mencegah *Cache Stampede / Thundering Herd* saat terjadi *Cache Miss*.

```go
package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"golang.org/x/sync/singleflight"
)

type UserProfile struct {
	ID    string
	Name  string
	Email string
}

type L1Item struct {
	Value      UserProfile
	Expiration time.Time
}

// MultiTierCacheManager mengelola L1 Local dan L2 Distributed Cache
type MultiTierCacheManager struct {
	l1Cache      sync.Map // In-process concurrent map
	l2Client     *redis.Client
	dbPrimary    *sql.DB
	dbReplica    *sql.DB
	requestGroup singleflight.Group
}

func NewMultiTierCacheManager(rdb *redis.Client, primary, replica *sql.DB) *MultiTierCacheManager {
	return &MultiTierCacheManager{
		l2Client:  rdb,
		dbPrimary: primary,
		dbReplica: replica,
	}
}

// GetUser melayani pola L1 -> L2 -> DB Read Replica dengan proteksi SingleFlight
func (m *MultiTierCacheManager) GetUser(ctx context.Context, userID string) (UserProfile, error) {
	cacheKey := fmt.Sprintf("user:%s", userID)

	// Tier 1: Check L1 Local In-Memory Cache
	if val, ok := m.l1Cache.Load(cacheKey); ok {
		item := val.(L1Item)
		if time.Now().Before(item.Expiration) {
			return item.Value, nil // L1 Cache Hit (<100ns)
		}
		m.l1Cache.Delete(cacheKey) // Evict expired L1
	}

	// Tier 2: Check L2 Redis Distributed Cache
	l2Val, err := m.l2Client.HGetAll(ctx, cacheKey).Result()
	if err == nil && len(l2Val) > 0 {
		profile := UserProfile{
			ID:    l2Val["id"],
			Name:  l2Val["name"],
			Email: l2Val["email"],
		}
		// Populate L1 (TTL pendek: 30 detik untuk mitigasi desinkronisasi lokal)
		m.l1Cache.Store(cacheKey, L1Item{
			Value:      profile,
			Expiration: time.Now().Add(30 * time.Second),
		})
		return profile, nil // L2 Cache Hit (~1ms)
	}

	// Tier 3: Database Read Replica (Mitigasi Thundering Herd via SingleFlight)
	// Hanya 1 request konkuren per userID yang mengeksekusi query database
	v, err, _ := m.requestGroup.Do(cacheKey, func() (interface{}, error) {
		// Mock query ke Database Read Replica
		profile, dbErr := m.queryUserFromReplica(ctx, userID)
		if dbErr != nil {
			return UserProfile{}, dbErr
		}

		// Update L2 Redis dengan TTL 10 Menit + Jitter (mencegah Cache Avalanche)
		pipe := m.l2Client.Pipeline()
		pipe.HSet(ctx, cacheKey, map[string]interface{}{
			"id":    profile.ID,
			"name":  profile.Name,
			"email": profile.Email,
		})
		pipe.Expire(ctx, cacheKey, 10*time.Minute)
		_, _ = pipe.Exec(ctx)

		// Update L1
		m.l1Cache.Store(cacheKey, L1Item{
			Value:      profile,
			Expiration: time.Now().Add(30 * time.Second),
		})

		return profile, nil
	})

	if err != nil {
		return UserProfile{}, err
	}
	return v.(UserProfile), nil
}

// InvalidateUser mengeksekusi Write-Through / Cache Eviction ke DB Primary dan Cache Tiers
func (m *MultiTierCacheManager) InvalidateUser(ctx context.Context, userID string) error {
	cacheKey := fmt.Sprintf("user:%s", userID)

	// 1. Evict L1 Local
	m.l1Cache.Delete(cacheKey)

	// 2. Invalidate L2 Distributed Redis
	if err := m.l2Client.Del(ctx, cacheKey).Err(); err != nil {
		return fmt.Errorf("redis eviction failed: %w", err)
	}

	// 3. Broadcast Invalidation Event ke L1 node lain melalui Redis Pub/Sub
	if err := m.l2Client.Publish(ctx, "cache:invalidate", cacheKey).Err(); err != nil {
		return fmt.Errorf("pubsub publish failed: %w", err)
	}

	return nil
}

// Simulasi DB fetch dari Replica
func (m *MultiTierCacheManager) queryUserFromReplica(ctx context.Context, userID string) (UserProfile, error) {
	if userID == "usr_404" {
		return UserProfile{}, errors.New("user not found")
	}
	// Simulasi I/O delay database
	time.Sleep(50 * time.Millisecond)
	return UserProfile{
		ID:    userID,
		Name:  "Technical Architect",
		Email: "architect@enterprise.io",
	}, nil
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Menerapkan partisi dan caching mendalam memperkenalkan kompromi arsitektural yang signifikan sesuai teorema CAP (*Consistency, Availability, Partition Tolerance*) dan PACELC (*Partition: Availability vs Consistency; Else: Latency vs Consistency*).

### 1. Primary-Replica: Throughput vs Replication Lag
*   **Keuntungan:** Kapasitas kueri baca meningkat secara linier dengan menambahkan replika; isolasi beban pelaporan/analitik dari transaksi utama.
*   **Trade-off:** Menghasilkan anomali baca *Stale Reads*. Dalam replikasi asinkron (*Asynchronous Replication*), jika Primary mengalami *crash* mendadak, data transaksi yang belum terkirim ke replica akan hilang (*Data Loss / RPO > 0*). Replikasi semi-sinkron menaikkan latensi penulisan Primary secara langsung.

### 2. Database Sharding: Scale-Out vs Arsitektur Kompleks
*   **Keuntungan:** Kapasitas penulisan (*Write Throughput*) dan volume penyimpanan disk tidak lagi terikat pada batasan mesin fisik tunggal.
*   **Trade-off:**
    *   **Kehilangan Foreign Keys:** Integritas referensial antar-tabel yang berada pada shard berbeda tidak lagi didukung oleh database engine; harus divalidasi manual di *Application Layer*.
    *   **Distributed Transactions (Cross-Shard Joins):** Operasi `JOIN` lintas-shard membutuhkan komunikasi jaringan masif (*scatter-gather*) yang sangat lambat, atau menuntut protokol transaksi dua fase (*Two-Phase Commit* / 2PC) yang merusak ketersediaan (*Availability*) dan performa sistem.

### 3. Local Cache (L1) vs Distributed Cache (L2)

| Parameter | L1 Local Cache (Process Memory) | L2 Distributed Cache (Redis/KeyDB) |
| :--- | :--- | :--- |
| **Latensi Akses** | Sangat Rendah (< 100ns) | Rendah (1ms – 5ms) |
| **Batas Kapasitas** | Terbatas pada RAM proses host | Sangat Besar (Dapat di-cluster secara horizontal) |
| **Overhead Serialisasi** | Nol (Menyimpan pointer objek bahasa) | Ada (JSON, Protobuf, atau MsgPack marshalling) |
| **Konsistensi Data** | Sulit dipertahankan seragam lintas server | Terpusat; seluruh node melihat satu *Single Source of Truth* |
| **Dampak App Restart** | Cache langsung musnah (*Cold Start*) | Data cache persisten, tidak terpengaruh siklus app |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan TTL Jittering (Pencegah Cache Avalanche):** Jangan pernah memberikan nilai TTL yang seragam untuk sekumpulan data besar. Tambahkan komponen acak (*jitter*), misal: `TTL = Base_TTL + Random(-30s, +30s)`. Hal ini mencegah jutaan kunci kedaluwarsa serentak di waktu yang sama.
2.  **Terapkan Pola SingleFlight / Cache Mutex:** Pastikan hanya ada 1 thread komputasi yang mengambil data dari database ketika terjadi *cache miss* untuk suatu kunci tertentu. Semua kueri konkuren lainnya harus menunggu hasil dari *thread* pertama tersebut.
3.  **Proteksi Cache Penetration dengan Bloom Filters atau Null Caching:** Jika sebuah resource tidak ada di database (misal: `user_id = 999999`), penyerang dapat mengeksploitasi celah ini dengan membombardir permintaan tersebut agar selalu tembus ke database. Solusinya: simpan kunci kosong tersebut di cache dengan TTL pendek (misal: 1 menit), atau gunakan *Bloom Filter* di depan cache layer.
4.  **Desain Shard Key Berdasarkan Pola Akses Kardinalitas Tinggi:** Hindari memilih shard key dengan kardinalitas rendah (misalnya: jenis kelamin atau status pesanan). Gunakan UUID atau kombinasi `TenantID + EntityID` untuk menjamin penyebaran data yang seragam pada hash ring.
5.  **Gunakan Change Data Capture (CDC) untuk Write-Heavy Invalidation:** Alih-alih mengeksekusi invalidasi cache manual di level aplikasi (yang rentan terhadap kegagalan jaringan di tengah jalan), gunakan engine CDC seperti Debezium yang membaca *Transaction Log/WAL* database secara langsung dan mengalirkan sinyal pembaruan secara asinkron ke Redis.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **Dual-Write Race Conditions:** Memperbarui database dan memperbarui cache secara langsung tanpa mekanisme kontrol konkurensi:
    *   *Skenario:* Transaksi A menulis DB -> Transaksi B menulis DB -> Transaksi B memperbarui Cache -> Transaksi A memperbarui Cache. Hasil akhir: Cache menyimpan data usang dari Transaksi A, sedangkan DB menyimpan data dari Transaksi B.
    *   *Solusi:* Selalu gunakan **Cache Eviction/Deletion** alih-alih pembaruan langsung (*Cache Mutation*), atau manfaatkan CDC.
2.  **Menaruh Seluruh Beban pada Write-Behind (Write-Back) Tanpa Redundansi:** Mengonfigurasi cache untuk menampung penulisan dan baru menuliskannya ke database secara terjadwal. Jika node Redis mengalami crash sebelum data tersiram (*flushed*) ke disk database, data bisnis hilang secara permanen.
3.  **Mengabaikan Replication Lag pada Alur Transaksional Kritis:** Mengarahkan pembacaan token autentikasi atau validasi saldo keuangan ke Database Read Replica segera setelah transaksi top-up selesai. Ini menyebabkan bug fatal di mana saldo pengguna belum ter-update.
4.  **Memilih Shard Key Monotonik (Auto-Increment / Sequential Timestamp):** Membagi shard menggunakan `id` auto-increment atau tanggal `created_at` menyebabkan seluruh penulisan data baru terkonsentrasi hanya pada satu shard aktif (*Hot Partition / Shard Imbalance*), sementara shard lama menjadi pasif.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Shard Routing Engine (Tingkat Menengah)
*   **Skenario:** Anda ditugaskan membangun lapisan proxy sharding internal tanpa ORM pihak ketiga.
*   **Tugas:**
    1.  Tuliskan algoritma sharding yang menerima struct `Order` (`OrderID string`, `CustomerID string`, `Amount float64`).
    2.  Petakan `Order` ke 4 instance database PostgreSQL virtual menggunakan fungsi Murmur3 hashing pada `CustomerID`.
    3.  Simulasikan eksekusi penulisan 10.000 data pesanan dan verifikasi deviasi distribusi data pada tiap instance shard (deviasi tidak boleh melebihi 10%).

### Latihan 2: Implementasi Cache Invalidation dengan Sinkronisasi L1/L2 (Tingkat Lanjutan)
*   **Skenario:** Kluster aplikasi microservices Anda memiliki 3 pod Kubernetes yang masing-masing menjalankan L1 Cache lokal di memori dan berbagi satu L2 Redis Cluster.
*   **Tugas:**
    1.  Kembangkan listener berbasis background goroutine/thread yang berlangganan (*subscribe*) ke Redis Pub/Sub channel `sys:invalidation`.
    2.  Ketika ada instruksi `UPDATE` pada entitas `ProductCatalog`, hapus kunci lokal di L1 Pod tersebut secara thread-safe menggunakan Mutex.
    3.  Buktikan melalui unit test konkurensi bahwa pembacaan data setelah event dipublikasikan tidak mengembalikan data basi (*stale data*).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Mengapa Cache Invalidation dengan metode menghapus kunci (*Delete*) lebih direkomendasikan daripada memperbarui isi kunci (*Update*) pada arsitektur terdistribusi multi-threaded?**
    *   a) Menghapus kunci lebih menghemat memori Redis daripada memperbarui nilainya.
    *   b) Menghapus kunci menghindari race condition di mana data lama menimpa data yang lebih baru akibat urutan eksekusi yang tidak teratur (*interleaved execution*).
    *   c) Redis tidak mendukung operasi update untuk data berbasis string atau hash.
    *   d) Menghapus kunci menjamin data langsung terbaca kembali dari database secara asinkron.
    *   *Jawaban yang benar:* **b**. Jika dua proses memperbarui cache secara konkuren, keterlambatan jaringan dapat membalik urutan pembaruan di cache, menghasilkan data basi permanen sampai TTL habis. Deletion bersifat idempoten dan memaksa pembacaan ulang data master yang valid.

2.  **Apa yang dimaksud dengan fenomena "Cache Stampede" (Thundering Herd)?**
    *   a) Kondisi di mana seluruh data di cache terhapus karena memori Redis penuh.
    *   b) Kondisi di mana jutaan kunci kedaluwarsa pada detik yang sama.
    *   c) Lonjakan trafik kueri yang masif secara serempak menembus langsung ke database master akibat satu kunci populer (*hot key*) kedaluwarsa secara tiba-tiba.
    *   d) Kegagalan replikasi antara Primary DB dan Read Replica akibat latensi jaringan.
    *   *Jawaban yang benar:* **c**. Cache Stampede terjadi saat hot-key kedaluwarsa dan ratusan/ribuan request bersamaan mendapati *cache miss*, lalu semuanya serempak mengeksekusi kueri berat ke database utama.

3.  **Pada Consistent Hashing, apa fungsi utama dari penambahan Virtual Nodes untuk setiap node fisik?**
    *   a) Mempercepat proses komputasi algoritma pencarian biner pada ring.
    *   b) Menjamin ketersediaan salinan data (*replica*) di memori.
    *   c) Meratakan distribusi kunci secara proporsional dan statistik di sepanjang ring guna mencegah ketimpangan beban (*hotspot/skewness*).
    *   d) Mengizinkan koneksi langsung via TLS ke setiap core CPU server database.
    *   *Jawaban yang benar:* **c**. Tanpa virtual nodes, sebaran node fisik pada ring 32-bit dapat menciptakan segmen ring yang terlalu besar untuk satu server dan terlalu kecil untuk server lain, menimbulkan ketidakseimbangan beban kerja yang masif.

4.  **Seorang pengguna menulis ulasan produk, namun setelah dialihkan ke halaman ulasan, ulasannya belum muncul. Namun setelah 3 detik ulasan tersebut tampil. Anomali apakah ini dan apa penyebab teknisnya?**
    *   a) Cache Avalanche; Redis sedang melakukan restart kluster.
    *   b) Replication Lag; Kueri baca diarahkan ke Read Replica yang belum selesai memproses WAL asinkron dari Primary DB.
    *   c) Split-Brain Syndrome; Primary DB kehilangan kuorum etcd.
    *   d) Deadlock; Transaksi baca menahan write lock pada tabel produk.
    *   *Jawaban yang benar:* **b**. Model *eventual consistency* pada asynchronous replication menghasilkan rentang waktu tunda (*lag*) sebelum data mutasi dari Primary diterapkan secara penuh di Read Replica.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Buku Referensi Standar Industri:**
    *   *Designing Data-Intensive Applications* oleh Martin Kleppmann (O'Reilly Media) — Wajib baca: Bab 5 (Replication), Bab 6 (Partitioning), dan Bab 7 (Transactions).
    *   *System Design Interview – An Insider's Guide: Volume 2* oleh Alex Xu & Sahn Lam — Bab khusus mengenai Distributed Cache dan Consistent Hashing.
    *   *Database Internals: A Deep Dive into How Distributed Data Systems Work* oleh Alex Petrov (O'Reilly Media).
*   **Paper Akademik Klasik:**
    *   *Dynamo: Amazon’s Highly Available Key-value Store* (DeCandia et al., 2007) — Fondasi desain Consistent Hashing dan Virtual Nodes di industri produksi.
    *   *Optimal Probabilistic Cache Stampede Prevention* (Vattani et al., VLDB 2015) — Algoritma matematis di balik fungsi eviksi probabilistik XFetch.
*   **Dokumentasi Resmi & Whitepaper:**
    *   Redis Architecture & Clustering Specification: https://redis.io/topics/cluster-spec
    *   PostgreSQL High Availability, Load Balancing, and Replication Manual.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Skalabilitas Horizontal Adalah Keniscayaan:** Penskalaan vertikal terikat hukum batas komputasi dan biaya eksponensial. Sistem berdaya tahan tinggi membagi tanggung jawab komputasi secara stateless dan memecah basis data secara terdistribusi.
2.  **Topologi Primary-Replica Memisahkan Beban I/O:** Membagi kueri mutasi (Write) ke Primary dan kueri pembacaan (Read) ke Replica melipatgandakan performa throughput sistem *read-heavy*, namun menuntut penanganan arsitektur terhadap konsekuensi *Eventual Consistency* dan *Replication Lag*.
3.  **Sharding Menyelesaikan Masalah Kapasitas Transaksional:** Menggunakan *Consistent Hashing dengan Virtual Nodes* adalah standar industri untuk mempartisi data ke berbagai node fisik tanpa risiko pergeseran data masif saat node ditambah atau dikurangi (*dynamic rebalancing*).
4.  **Multi-Tier Caching Menyediakan Keseimbangan Latensi & Konsistensi:** Mengombinasikan L1 (In-Memory) untuk kecepatan mikrodetik dan L2 (Distributed/Redis) untuk keseragaman status sistem.
5.  **Ketahanan Cache Membutuhkan Pola Defensif:** Mengamankan cache layer dari kehancuran fatal akibat *Cache Stampede* (gunakan *SingleFlight*), *Cache Avalanche* (gunakan *TTL Jittering*), dan *Cache Penetration* (gunakan *Bloom Filter* atau *Null Object Caching*).

---

## SEKSI 17 — GLOSARIUM

*   **Consistent Hashing:** Algoritma pemetaan data ke node menggunakan struktur cincin logika berderajat $2^{32}-1$ yang membatasi pergeseran data hanya sebesar $K/N$ saat terjadi perubahan node (di mana $K$ adalah jumlah data dan $N$ adalah jumlah node).
*   **Replication Lag:** Interval waktu (biasanya dalam milidetik/detik) keterlambatan node Replica dalam menerima dan menerapkan log transaksi (*WAL*) dari node Primary.
*   **SingleFlight:** Pola rekayasa perangkat lunak konkurensi di mana beberapa permintaan simultan untuk kunci yang sama ditekan menjadi satu eksekusi tunggal, dan hasilnya dibagikan ke seluruh pemanggil.
*   **Cache Stampede:** Kejadian lonjakan beban kueri komputasi berat ke penyimpanan primer yang terjadi seketika saat sebuah entri cache bernilai tinggi kedaluwarsa.
*   **Change Data Capture (CDC):** Pola integrasi sistem yang memantau, mendeteksi, dan menangkap setiap mutasi data pada tingkat log transaksi database secara realtime untuk dialirkan ke sistem hilir.
*   **Write-Ahead Log (WAL):** Struktur data append-only persisten di mana seluruh perubahan basis data wajib dicatat secara aman di disk sebelum diterapkan ke tabel data internal.
*   **Virtual Nodes (VNodes):** Titik replika token logis dari satu node server fisik pada sebuah cincin hash guna mendistribusikan kunci data secara merata.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Poin Penekanan Materi:**
    *   Pastikan siswa tidak menganggap *caching* sebagai jalan pintas untuk menyelesaikan masalah kueri database yang tidak terindeks (*bad indexing*). Evaluasi database index harus selalu mendahului implementasi layer caching.
    *   Tekankan bahwa membagi database (*sharding*) adalah keputusan arsitektur tingkat lanjut yang membawa kompleksitas operasional masif (monitoring cross-node, backup terdistribusi, re-sharding). Ajarkan siswa untuk memaksimalkan *Read Replicas*, *Partitioning internal PostgreSQL/MySQL*, dan *Distributed Caching* sebelum melompat ke *Manual Sharding*.
*   **Panduan Demonstrasi Lab:**
    *   Saat mendemonstrasikan SingleFlight, gunakan Apache Bench (`ab`) atau `k6` dengan 1.000 konkurensi tinggi untuk menembak endpoint tanpa L1 Cache dan tunjukkan log query database: buktikan bahwa DB Replica hanya menerima tepat **1 query** alih-alih 1.000 query.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Maret 2026)**
    *   Rilis modul komprehensif perdana.
    *   Penambahan implementasi algoritma Consistent Hashing dengan FNV-1a dan Virtual Nodes.
    *   Penyusunan kode produksi Multi-tier Caching dengan integrasi sync.Map, Redis, dan SingleFlight.
    *   Penambahan panduan mitigasi anomali caching (Stampede, Avalanche, Penetration).

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `SDA-06-07-02` — *Microservices Decomposition, Domain Boundaries, and Shared Data Management*
*   **Modul Saat Ini:** `SDA-06-08-01` — *Skalabilitas, Partisi Data, & Strategi Caching: Vertical vs Horizontal Scaling, Database Read Replicas, Sharding, Multi-tier Caching (Local vs Distributed), Cache Invalidation*
*   **Modul Berikutnya:** `SDA-06-08-02` — *High Availability, Fault Tolerance, Disaster Recovery, and Consensus Algorithms (Raft/Paxos)*