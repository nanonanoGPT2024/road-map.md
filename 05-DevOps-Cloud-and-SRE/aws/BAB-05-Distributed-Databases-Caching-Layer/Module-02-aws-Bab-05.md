# Kurikulum Enterprise: AWS Cloud Infrastructure & Platform Engineering
## Kategori: 05-DevOps-Cloud-and-SRE
### Bab 05: Distributed Databases & Caching Layer
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membedah (Analyze & Deconstruct)** arsitektur internal Amazon DynamoDB (Storage Node, Paxos Group, Partition Routers, Request Router) dan Amazon ElastiCache for Redis (Cluster Mode, 16.384 Hash Slots, In-Memory Engine, Engine threads).
- **Mendesain dan Mengimplementasikan (Design & Implement)** topologi multi-region database aktif-aktif (DynamoDB Global Tables) dan multi-region caching layer dengan latensi sub-milidetik untuk beban kerja *Tier-0 mission-critical*.
- **Menerapkan (Implement)** mitigasi tingkat lanjut terhadap anomali sistem terdistribusi, seperti *Cache Stampede* (menggunakan algoritma *Probabilistic Early Expiration* / XFetch), *Hot Partitioning*, *Split-Brain scenarios*, dan replikasi *lag drift*.
- **Mengoptimalkan (Optimize)** rasio biaya terhadap performa (*Cost-to-Performance Ratio*) melalui strategi *storage tiering* (DynamoDB Standard vs Standard-IA), *data lifecycle*, *reserved nodes*, dan *memory optimization* pada ElastiCache Redis.

---

### 2. Prerequisite
Untuk mengikuti modul tingkat lanjut ini, peserta wajib menguasai:
- **Jaringan Cloud & AWS Core**: VPC Peering, Transit Gateway, PrivateLink, IAM Policies, Direct Connect, Security Groups.
- **Fundamental Basis Data Terdistribusi**: Teorema CAP, PACELC, Model Konsistensi (Eventual, Strong, Causal), Two-Phase Commit (2PC), Paxos/Raft Consensus.
- **Penguasaan Bahasa Pemrograman**: Go (Golang) tingkat menengah ke atas (Goroutine, Channels, Context, Memory Management) untuk implementasi sistem performa tinggi.
- **CLI & IaC Tooling**: AWS CLI v2, Terraform/OpenTofu (v1.5+), Docker.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Amazon DynamoDB Internal Architecture

DynamoDB bukan sekadar sistem *key-value/document store*, melainkan sistem terdistribusi multi-tenant terisolasi yang diatur oleh beberapa komponen decoupled:

```
[Client Application]
         │ (SigV4 Request over HTTPS/HTTP2)
         ▼
 ┌──────────────────────────────────────────────┐
 │             Request Router Layer             │
 │  - Authentication & Authorization            │
 │  - Partition Key Hashing (MD5 variant)       │
 │  - Storage Node Routing Directory            │
 └──────────────────────┬───────────────────────┘
                        │
                        ▼
 ┌──────────────────────────────────────────────┐
 │           Paxos Replica Group (Storage)      │
 │                                              │
 │   ┌──────────────┐      ┌──────────────┐     │
 │   │ Storage Node │      │ Storage Node │     │
 │   │  (Leader)    │◄────►│  (Follower)  │     │
 │   │   - WAL      │      │   - WAL      │     │
 │   │   - B-Tree   │      │   - B-Tree   │     │
 │   └──────┬───────┘      └──────────────┘     │
 │          │                                   │
 │          ▼                                   │
 │   ┌──────────────┐                           │
 │   │ Storage Node │                           │
 │   │  (Follower)  │                           │
 │   │   - WAL      │                           │
 │   │   - B-Tree   │                           │
 │   └──────────────┘                           │
 └──────────────────────┬───────────────────────┘
                        │ (Asynchronous Log Stream)
                        ▼
 ┌──────────────────────────────────────────────┐
 │    DynamoDB Streams & Global Table Engine    │
 └──────────────────────────────────────────────┘
```

1. **Request Router Layer**: 
   - Menerima request HTTP/2 terenkripsi SigV4.
   - Mengambil Partition Key (PK) dari payload, menjalankan fungsi hash internal untuk memetakan item ke *Partition Range*.
   - Mengonsultasikan *Partition Map Metadata Cache* internal untuk menemukan IP/identitas dari storage node yang memimpin (*Paxos Leader*) untuk partisi tersebut.
2. **Storage Nodes & Paxos Replica Group**:
   - Data fisik disimpan dalam partisi (maksimum 10 GB per partisi fisik, dibatasi hingga 1.000 WCU dan 3.000 RCU).
   - Setiap partisi fisik terdiri dari 3 replika penyimpanan yang tersebar di 3 Availability Zone (AZ) berbeda, membentuk satu **Paxos Replica Group**.
   - **Write Path**: Request tulis diarahkan ke Paxos Leader. Leader mencatat mutasi ke *Write-Ahead Log* (WAL) lokal, mengirim pesan Paxos Propose ke kedua Follower. Begitu salah satu Follower merespons (Quorum = 2 dari 3 node), transaksi dinyatakan *committed* dan di-flush ke SSD (menggunakan B-tree/LSM variant engine). Leader mengembalikan status 200 OK ke client.
   - **Read Path**: *Eventually Consistent Read* dapat dilayani oleh replika mana pun (Leader atau Follower). *Strongly Consistent Read* dijamin harus melayani data dari Paxos Leader (atau diverifikasi via quorum lease) untuk memastikan pembacaan state terbaru dari WAL.
3. **Adaptive Capacity & Global Secondary Indexes (GSI)**:
   - Jika satu partisi mengalami lonjakan trafik melebihi alokasi 1.000 WCU / 3.000 RCU, mekanisme **Adaptive Capacity** mendistribusikan kapasitas yang tidak terpakai dari partisi lain ke partisi panas tersebut tanpa memicu *throttling*, selama total throughput tabel tidak terlampaui.
   - GSI memiliki *Storage Node Group* independen. Pembaruan dari tabel utama dikirimkan secara *asynchronous* melalui internal log replication bus ke GSI. Jika GSI mengalami throttling, kapasitas penulisan tabel utama dapat terhambat (*backpressure*).

#### B. Amazon ElastiCache for Redis (Cluster Mode Enabled) Architecture

Arsitektur Redis Cluster mengandalkan pembagian ruang kunci terdesentralisasi:

```
Ruang Kunci Total: 16.384 Hash Slots
Hash Slot Formula: HASH_SLOT = CRC16(key) MOD 16384

  Shard 1: Slots [0 - 5460]
  ┌───────────────────────┐         Replication Stream (Async)
  │ Primary Node (AZ-a)   ├─────────────────────────────────────────┐
  └──────────┬────────────┘                                         │
             │                                                      ▼
             │ Cluster Bus (Port 16379, Gossip Protocol) ┌──────────────────────┐
             │ Heartbeats & Topology Updates             │ Replica Node (AZ-b)  │
             ▼                                           └──────────────────────┘
  Shard 2: Slots [5461 - 10922]
  ┌───────────────────────┐
  │ Primary Node (AZ-b)   ├──────────────────────────────┐
  └──────────┬────────────┘                              ▼
             │                                   ┌──────────────────────┐
             │                                   │ Replica Node (AZ-c)  │
             ▼                                   └──────────────────────┘
  Shard 3: Slots [10923 - 16383]
  ┌───────────────────────┐
  │ Primary Node (AZ-c)   ├──────────────────────────────┐
  └───────────────────────┘                              ▼
                                                 ┌──────────────────────┐
                                                 │ Replica Node (AZ-a)  │
                                                 └──────────────────────┘
```

1. **Hash Slots Distribution**: Ruang total 16.384 *hash slots* dibagi rata ke seluruh Primary Shards. Jika client ingin mengakses kunci `user:1000:session`, Redis client menghitung `CRC16("user:1000:session") % 16384`. Client pintar (*Cluster-aware Client*) menyimpan topologi slot di memori lokal. Jika terjadi perubahan topologi tanpa disadari client, node Redis merespons dengan `-MOVED <new_slot> <node_ip>`.
2. **Gossip Protocol**: Node saling berkomunikasi melalui port daemon terpisah (port Redis dasar + 10.000, misal 6379 + 10000 = 16379) untuk menyinkronkan status node, kegagalan partisi, dan mendeteksi kondisi failover secara otonom.
3. **Internal Memory Management**: Redis adalah *in-memory engine* yang mengeksekusi perintah berbasis single-threaded event loop untuk komputasi data (didukung multi-threading untuk I/O socket pada versi modern). Ketika batas `maxmemory` tercapai, algoritma eviksi bekerja (seperti `volatile-lru`, `allkeys-lru`, atau `volatile-lfu`). Pada ElastiCache, swap memory diatur pada OS level untuk mencegah *OOM Killer (Out Of Memory)* langsung mematikan proses, tetapi *thrashing* ke swap disk akan memicu degradasi latensi tinggi.

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik / Tradisional | Pendekatan Terdistribusi AWS Modern |
| :--- | :--- | :--- |
| **Penskalaan Database** | Vertikal (Scale-Up Instance Size), replika baca dengan write bottleneck pada 1 Primary. | Horizontal (Scale-Out Partisi Dinamis), DynamoDB membagi partisi fisik otomatis tanpa downtime. |
| **High Availability** | Active-Passive dengan failover 30-120 detik, potensi data loss (RPO > 0). | Multi-AZ Quorum (Paxos) dengan RPO = 0 untuk strong writes lokal, dan Multi-Region Global Tables. |
| **Caching Tier** | Redis Single Instance standalone, kegagalan node menghancurkan database sekunder (*Cache Avalanche*). | Redis Cluster Mode Enabled (Multi-Shard, Multi-Replica) dengan Auto-Failover via ElastiCache Service Engine. |
| **Manajemen State** | ACID kaku yang membatasi konkurensi global melintasi benua. | Model PACELC: Mengoptimalkan Trade-off Latensi vs Konsistensi tergantung kebutuhan endpoint bisnis. |

---

### 5. How (Workflow Detail)

Alur kerja operasional gabungan antara Caching Layer dan Distributed Database Layer:

```
[Client Application]
         │
         │ 1. Get User Profile: GET /user/42
         ▼
┌──────────────────┐       HIT (Return Data)
│ ElastiCache      │ ──────────────────────────────────────────────┐
│ Redis Cluster    │                                               │
└────────┬─────────┘                                               │
         │ MISS                                                    │
         ▼                                                         │
┌──────────────────┐                                               │
│ Check Early Exp? │ ─── YES ──► Trigger Async Worker ──┐          │
└────────┬─────────┘             to Refresh Cache       │          │
         │                                              │          │
         ▼                                              ▼          ▼
┌──────────────────┐                           ┌────────────────────────┐
│ Amazon DynamoDB  │                           │ Application Controller │
│ (Read Consistent)│                           └────────────────────────┘
└────────┬─────────┘                                               ▲
         │                                                         │
         │ 2. Data Retrieved                                       │
         ▼                                                         │
┌──────────────────┐                                               │
│ Populate Redis   │ ──────────────────────────────────────────────┘
│ with Jittered TTL│
└──────────────────┘
```

1. **Cache Interception**: Aplikasi mengeksekusi algoritma *Probabilistic Early Expiration* (XFetch). Jika key ditemukan dan belum mendekati masa kedaluwarsa probabilistik, data langsung dikembalikan (< 1ms).
2. **Cache Miss / Early Refresh Detection**:
   - Jika data tidak ada (*Cache Miss*), aplikasi mengambil data dari Amazon DynamoDB menggunakan *Strongly Consistent Read* (jika mutasi kritis) atau *Eventually Consistent Read* (jika analitik/profil non-finansial).
   - Data yang diambil dari DynamoDB segera diinjeksikan kembali ke ElastiCache Redis dengan menyertakan nilai TTL yang di-*jitter* (ditambahkan variansi acak) untuk mencegah *Cache Avalanche*.
3. **Write Pipeline**:
   - Aplikasi mengeksekusi operasi penulisan menggunakan `TransactWriteItems` pada DynamoDB.
   - Transaksi sukses diverifikasi oleh Paxos Quorum lokal.
   - Cache invalidation dilakukan secara eksplisit menggunakan pola *Cache-Aside Invalidation* atau pembaruan asinkronus menggunakan *DynamoDB Streams* yang memicu AWS Lambda untuk menghapus/memperbarui key di Redis cluster.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
- **DynamoDB Storage Nodes & Paxos**: Bayangkan ruang rapat dewan direksi beranggotakan 3 direktur (Replica Nodes). Setiap keputusan (Write item) tidak perlu menunggu semua orang setuju; selama pemimpin rapat (Paxos Leader) dan satu anggota lainnya sepakat (Quorum = 2), keputusan tersebut sah berkekuatan hukum dan dicatat permanen dalam notulen negara (WAL & Disk).
- **Redis Cluster Hash Slots**: Bayangkan kantor pos besar dengan 16.384 kotak surat (*slots*). Kantor pos memiliki 3 loket utama (*Primary Shards*). Loket 1 menangani kotak 0-5460, Loket 2 menangani 5461-10922, Loket 3 menangani 10923-16383. Surat Anda diberi stempel angka berbasis formula matematika nama penerima. Anda langsung tahu loket mana yang harus dituju tanpa bertanya ke resepsionis sentral.

#### Diagram Topologi Multi-Region Active-Active

```
                REGION 1 (ap-southeast-1)                            REGION 2 (ap-southeast-3)
      ┌───────────────────────────────────────────┐        ┌───────────────────────────────────────────┐
      │  VPC: 10.100.0.0/16                       │        │  VPC: 10.200.0.0/16                       │
      │                                           │        │                                           │
      │  ┌─────────────────────────────────────┐  │        │  ┌─────────────────────────────────────┐  │
      │  │ App Services (EKS / ECS / EC2)      │  │        │  │ App Services (EKS / ECS / EC2)      │  │
      │  └──────────┬──────────────────────────┘  │        │  └──────────┬──────────────────────────┘  │
      │             │                             │        │             │                             │
      │             ▼                             │        │             ▼                             │
      │  ┌─────────────────────────────────────┐  │        │  ┌─────────────────────────────────────┐  │
      │  │ ElastiCache Redis Cluster           │  │        │  │ ElastiCache Redis Cluster           │  │
      │  │ (Primary AZ-a, AZ-b, AZ-c)          │  │        │  │ (Primary AZ-a, AZ-b, AZ-c)          │  │
      │  └──────────┬──────────────────────────┘  │        │  └──────────┬──────────────────────────┘  │
      │             │                             │        │             │                             │
      │             ▼                             │        │             ▼                             │
      │  ┌─────────────────────────────────────┐  │        │  ┌─────────────────────────────────────┐  │
      │  │ DynamoDB Replica Table              │  │        │  │ DynamoDB Replica Table              │  │
      │  │ (Region: ap-southeast-1)            │  │        │  │ (Region: ap-southeast-3)            │  │
      │  └──────────────────┬──────────────────┘  │        │  └──────────────────┬──────────────────┘  │
      └─────────────────────┼─────────────────────┘        └─────────────────────┼─────────────────────┘
                            │                                                    │
                            └────────────── AWS Global Backbone ─────────────────┘
                                       DynamoDB Global Tables v2
                                (Asynchronous Active-Active Replication)
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Conditional Write di DynamoDB (Go v2 SDK)
Mencegah *race condition* saat pembaruan saldo akun tanpa *distributed lock*:

```go
package main

import (
	"context"
	"fmt"
	"log"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
)

func DeductBalance(ctx context.Context, client *dynamodb.Client, accountID string, amount int64) error {
	_, err := client.UpdateItem(ctx, &dynamodb.UpdateItemInput{
		TableName: aws.String("EnterpriseAccounts"),
		Key: map[string]types.AttributeValue{
			"PK": &types.AttributeValueMemberS{Value: fmt.Sprintf("ACC#%s", accountID)},
			"SK": &types.AttributeValueMemberS{Value: "BALANCE"},
		},
		UpdateExpression: aws.String("SET Balance = Balance - :amt, Version = Version + :one"),
		ConditionExpression: aws.String("Balance >= :amt AND attribute_exists(PK)"),
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":amt": &types.AttributeValueMemberN{Value: fmt.Sprintf("%d", amount)},
			":one": &types.AttributeValueMemberN{Value: "1"},
		},
	})
	if err != nil {
		return fmt.Errorf("gagal mendebit akun: %w (kemungkinan saldo tidak cukup atau data terkunci)", err)
	}
	return nil
}

func main() {
	cfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion("ap-southeast-1"))
	if err != nil {
		log.Fatalf("Gagal memuat konfigurasi AWS: %v", err)
	}
	client := dynamodb.NewFromConfig(cfg)

	err = DeductBalance(context.TODO(), client, "ACC-ID-99238", 50000)
	if err != nil {
		log.Println("Operasi dibatalkan:", err)
		return
	}
	log.Println("Berhasil mendebit saldo secara aman!")
}
```

#### Practical Example: Anti-Cache Stampede Menggunakan Algoritma Probabilistic Early Expiration (XFetch) & DynamoDB Fallback (Go)

```go
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"math/rand"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
	"github.com/redis/go-redis/v9"
)

type CachePayload struct {
	Value     string  `json:"val"`
	TTL       float64 `json:"ttl"`       // TTL awal dalam detik
	Delta     float64 `json:"delta"`     // Waktu komputasi fetch dalam detik
	CreatedAt int64   `json:"createdAt"` // Unix timestamp
}

type ProductService struct {
	rdb      *redis.ClusterClient
	ddb      *dynamodb.Client
	beta     float64
	muLocks  sync.Map
}

func NewProductService(rdb *redis.ClusterClient, ddb *dynamodb.Client) *ProductService {
	return &ProductService{
		rdb:  rdb,
		ddb:  ddb,
		beta: 1.0, // Beta > 1 artinya kalkulasi early recompute lebih agresif
	}
}

// XFetch implements: (time() - (delta * beta * ln(random()))) >= expiry
func (s *ProductService) shouldRecompute(payload *CachePayload) bool {
	now := float64(time.Now().Unix())
	expiry := float64(payload.CreatedAt) + payload.TTL
	
	// Jika rand.Float64() menghasilkan 0, gunakan fallback epsilon kecil
	r := rand.Float64()
	if r == 0 {
		r = 0.00001
	}

	xfetchThreshold := float64(now) - (payload.Delta * s.beta * math.Log(r))
	return xfetchThreshold >= expiry
}

func (s *ProductService) GetProductDescription(ctx context.Context, productID string) (string, error) {
	cacheKey := fmt.Sprintf("product:%s:desc", productID)
	
	val, err := s.rdb.Get(ctx, cacheKey).Result()
	if err == nil {
		var payload CachePayload
		if jsonErr := json.Unmarshal([]byte(val), &payload); jsonErr == nil {
			if !s.shouldRecompute(&payload) {
				// Cache HIT dan belum masuk probabilistic expiry window
				return payload.Value, nil
			}
			// Memerlukan refresh secara probabilistik untuk mencegah stampede massal
			go s.asyncBackgroundRecompute(productID, cacheKey)
			return payload.Value, nil
		}
	} else if !errors.Is(err, redis.Nil) {
		// Log error Redis, namun lanjutkan fallback ke Database primer
		fmt.Printf("[Cache Error] Gagal membaca Redis: %v\n", err)
	}

	// Cache MISS Mutlak: Fetch sinkronus ke DynamoDB
	return s.fetchAndPopulate(ctx, productID, cacheKey)
}

func (s *ProductService) asyncBackgroundRecompute(productID, cacheKey string) {
	// Memastikan hanya 1 background worker lokal yang bekerja untuk key tersebut
	if _, loaded := s.muLocks.LoadOrStore(cacheKey, true); loaded {
		return
	}
	defer s.muLocks.Delete(cacheKey)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, _ = s.fetchAndPopulate(ctx, productID, cacheKey)
}

func (s *ProductService) fetchAndPopulate(ctx context.Context, productID, cacheKey string) (string, error) {
	startTime := time.Now()

	// Ambil data langsung dari DynamoDB
	out, err := s.ddb.GetItem(ctx, &dynamodb.GetItemInput{
		TableName: aws.String("ProductionCatalog"),
		Key: map[string]types.AttributeValue{
			"PK": &types.AttributeValueMemberS{Value: fmt.Sprintf("PROD#%s", productID)},
			"SK": &types.AttributeValueMemberS{Value: "METADATA"},
		},
		ConsistentRead: aws.Bool(false),
	})
	if err != nil {
		return "", fmt.Errorf("dynamodb query failure: %w", err)
	}

	var description string
	if descAttr, exists := out.Item["Description"].(*types.AttributeValueMemberS); exists {
		description = descAttr.Value
	} else {
		return "", errors.New("deskripsi produk tidak ditemukan pada tabel")
	}

	computeDelta := time.Since(startTime).Seconds()
	ttlSeconds := 300.0 // TTL basis: 5 menit

	payload := CachePayload{
		Value:     description,
		TTL:       ttlSeconds,
		Delta:     computeDelta,
		CreatedAt: time.Now().Unix(),
	}

	payloadJSON, _ := json.Marshal(payload)
	// Set Redis dengan real physical TTL sedikit lebih lama dari TTL logis
	err = s.rdb.Set(ctx, cacheKey, payloadJSON, time.Duration(ttlSeconds*1.2)*time.Second).Err()
	if err != nil {
		fmt.Printf("[Cache Error] Gagal menyimpan ke Redis: %v\n", err)
	}

	return description, nil
}

func main() {
	// Bootstrap AWS Context
	cfg, err := config.LoadDefaultConfig(context.Background(), config.WithRegion("ap-southeast-1"))
	if err != nil {
		panic(err)
	}
	ddbClient := dynamodb.NewFromConfig(cfg)

	// Bootstrap Redis Cluster
	rdb := redis.NewClusterClient(&redis.ClusterOptions{
		Addrs: []string{"clustercfg.prod-cache.xxxxxx.apse1.cache.amazonaws.com:6379"},
	})
	defer rdb.Close()

	svc := NewProductService(rdb, ddbClient)
	desc, err := svc.GetProductDescription(context.Background(), "SKU-99011")
	if err != nil {
		fmt.Printf("Gagal mengeksekusi operasi: %v\n", err)
		return
	}
	fmt.Printf("Deskripsi Produk: %s\n", desc)
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Flash Sale Platform E-Commerce (150.000 TPS Peak)
- **Kondisi Awal**: Sebuah marketplace e-commerce Asia Tenggara menyelenggarakan agenda penjualan tahunan. Basis data relasional (Aurora PostgreSQL) mengalami *connection pool exhaustion*, replika mengalami *replication lag* hingga 45 detik, dan CPU menyentuh 100% saat ribuan pengguna memeriksa *Flash Sale Inventory Counter*.
- **Desain Transformasi Solusi Arsitektur**:
  1. **Tier Caching Layer**: Mengimplementasikan Amazon ElastiCache for Redis Cluster Mode Enabled dengan 6 shards (6 Primaries + 6 Read Replicas yang terdistribusi di 3 Availability Zone). Memisahkan cache pembacaan katalog dan penanganan atomic inventory.
  2. **Data Model Inventory**: Counter stok dipindahkan ke Redis menggunakan instruksi atomic `DECRBY` dan skrip Lua untuk memverifikasi apakah stok >= jumlah pembelian secara instan dalam memori (< 1ms).
  3. **Tier Basis Data Terdistribusi**: Mengubah penyimpanan order transaksi dari sistem relasional monolitik ke Amazon DynamoDB Global Tables dengan *On-Demand Capacity Mode* (yang telah di-pre-warm ke tingkat kebutuhan minimum 50.000 WCU). Partisi kunci (`PK`) menggunakan formula `ORDER#<UserID>` dan *Sort Key* (`SK`) berupa timestamp berurut terbalik (`TS#<Timestamp>`) untuk mencegah *hot partition clustering*.
  4. **Pencegahan Throttling GSI**: Untuk pelaporan dashboard internal, diterapkan teknik *Write Sharding* pada GSI. ID tanggal pesanan digabungkan dengan bilangan acak sufiks 0–19 (`2026-03-30.#N`) untuk mendistribusikan beban tulis GSI ke 20 partisi fisik DynamoDB yang terpisah.
- **Hasil Terukur (Post-Implementation Metrics)**:
  - Latensi P99 Read turun dari 680ms ke 1.8ms.
  - Latensi P99 Write tercatat di angka 8.2ms secara konsisten pada 154.000 TPS.
  - Zero-Downtime, hilangnya *Connection Timeout Exception* secara total.
  - Pemotongan biaya operasional infrastruktur sebesar 34% dibanding mempertahankan instans basis data relasional ukuran raksasa (misal: `db.r6g.16xlarge`).

---

### 9. Trade-offs

| Opsi Arsitektur | Keuntungan (*Pros*) | Kerugian / Risiko (*Cons*) | Rekomendasi Beban Kerja |
| :--- | :--- | :--- | :--- |
| **DynamoDB On-Demand Mode** | Bebas konfigurasi kapasitas, toleran terhadap lonjakan trafik instan yang tidak terprediksi, zero management. | Biaya per unit request ~7x lipat lebih mahal jika trafik stabil dan predictable. | Aplikasi dengan trafik *spiky* ekstrim, Flash Sales, startup fase eksplorasi. |
| **DynamoDB Provisioned + Autoscaling** | Jauh lebih hemat biaya dengan *Reserved Capacity* (diskon hingga 70%+). | Autoscaling butuh waktu beberapa menit untuk menaikkan kapasitas; rentan terhadap throttling jika lonjakan terlalu curam. | Aplikasi enterprise dengan baseline konstan (Core Banking, API Gateway Logs). |
| **ElastiCache Cluster Mode Enabled** | Skalabilitas data horizontal melampaui limit RAM satu instans (hingga ratusan TB), throughput jaringan terdistribusi. | Penulisan multi-key (`MGET`, `MSET`, `Transactions`) dibatasi dalam *Hash Slot* yang sama (wajib menggunakan `{hash tag}`). | Arsitektur berskala besar dengan footprint memori > 100 GB atau throughput > 100k TPS. |
| **ElastiCache Cluster Mode Disabled** | Sederhana, mendukung multi-key command tanpa komplikasi hash tag. | Terbatas pada limit kapasitas RAM node Primary tunggal (maksimum instans teratas: ~400 GB). Failover memakan waktu sedikit lebih lama. | Read-heavy caching layer berskala kecil hingga menengah (< 50k QPS). |
| **Strong Consistency (DynamoDB)** | Menjamin data yang dibaca adalah kondisi paling mutakhir dari state mesin Paxos Leader. | Mengonsumsi 2x lipat kapasitas RCU, berpotensi mengalami kenaikan latensi jika leader sedang sibuk. | Pembacaan saldo keuangan, validasi transaksi, otorisasi token. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Hot Partitioning pada DynamoDB
- **Gejala**: Metrik `ThrottledRequests` pada Amazon CloudWatch meningkat drastis, padahal total konsumsi kapasitas akun masih jauh di bawah target agregat yang dialokasikan.
- **Akar Masalah**: Pola *Partition Key* yang buruk, misalnya menggunakan format tanggal statis (`PK = "2026-03-30"`) atau field dengan kardinalitas rendah seperti `Status = "ACTIVE"`. Seluruh traffic tertumpu pada 1 partisi fisik (batas fisik 1.000 WCU / 3.000 RCU terlampaui).
- **Resolusi**:
  - Terapkan teknik *Synthetic Sharding*: Gabungkan PK dengan suffix acak atau hashing `PK = "2026-03-30." + (Murmur3(UserID) % 10)`.
  - Pisahkan data historis dingin dari data transaksional aktif.

#### 2. Redis Replication Buffer Overflow & Resynchronization Loop
- **Gejala**: Replica node sering terputus dari Primary, memicu *Full Synchronization* terus menerus (`SYNC` / `PSYNC`), menyebabkan CPU Primary melonjak dan latensi spike.
- **Akar Masalah**: Parameter `client-output-buffer-limit replica` terlalu rendah sementara laju penulisan (*write rate*) sangat tinggi. Aliran mutasi mengisi buffer replikasi lebih cepat daripada kapasitas replika untuk mengonsumsinya lewat jaringan.
- **Resolusi**:
  - Konfigurasikan ElastiCache Parameter Group: Tingkatkan memori alokasi `client-output-buffer-limit` untuk replika.
  - Upgrade tipe instans node ke generasi berfitur jaringan lebih besar (misal beralih dari tipe Burstable `t4g` ke Network Optimized `m6g` / `c6g`).

#### 3. Cache Stampede (Dogpiling Effect)
- **Gejala**: Database DynamoDB mengalami lonjakan beban tiba-tiba dan mengalami *throttling* parah tepat setelah sebuah key cache populer mencapai TTL kedaluwarsa.
- **Akar Masalah**: Ribuan thread aplikasi secara simultan membaca Redis, mendeteksi ketiadaan data (*Cache Miss*), dan serentak menembak database primer untuk menghitung nilai yang sama.
- **Resolusi**:
  - Implementasikan algoritma XFetch (Probabilistic Early Expiration) sebagaimana diilustrasikan di Seksi 7.
  - Terapkan *Distributed Locking* (menggunakan Redlock atau Mutex) agar hanya satu worker yang melakukan querying ke DB primer, sementara thread lainnya menunggu.

#### 4. GSI Throttling Mengakibatkan Write Rejection pada Base Table
- **Gejala**: Aplikasi menerima error `TransactionCanceledException` atau `ProvisionedThroughputExceededException` pada tabel utama, meskipun tabel utama berstatus On-Demand atau memiliki kuota WCU melimpah.
- **Akar Masalah**: GSI tidak memiliki alokasi kapasitas penulisan yang cukup untuk menampung mutasi dari tabel utama. Mekanisme internal DynamoDB menerapkan *backpressure* ke tabel utama guna menjaga agar perbedaan replikasi asinkronus ke GSI tidak melebar.
- **Resolusi**:
  - Pastikan metrik `WriteThrottleEvents` pada semua GSI dipantau.
  - Selalu samakan model kapasitas (On-Demand / Provisioned) antara GSI dan Base Table.

---

### 11. Best Practices (Production Checklist)

#### Network & Security
- [ ] Tempatkan ElastiCache dan VPC Endpoints untuk DynamoDB di Private Subnet tanpa akses langsung dari Internet Gateway.
- [ ] Aktifkan enkripsi ganda: *Encryption in-Transit* (TLS) dan *Encryption at-Rest* menggunakan AWS KMS Customer Managed Keys (CMK).
- [ ] Konfigurasikan Security Group ElastiCache hanya menerima *inbound traffic* dari Security Group khusus milik compute layer (EKS/ECS).

#### DynamoDB Configuration
- [ ] Aktifkan fitur *Point-In-Time Recovery (PITR)* untuk seluruh tabel produksi (mengizinkan continuous backup hingga 35 hari ke belakang).
- [ ] Atur lifecycle data menggunakan atribut native *Time to Live (TTL)* untuk pembersihan record usang tanpa mengonsumsi kuota WCU.
- [ ] Hindari operasi `Scan`. Terapkan operasi `Query` berbasis Partition Key dan Sort Key expression.
- [ ] Atur Retry Mechanism pada SDK dengan *Exponential Backoff* dan *Full Jitter*.

#### Redis Configuration
- [ ] Atur parameter `maxmemory-reserved-percent` minimal 25% (default 0% sering memicu kegagalan backup/failover akibat kehabisan memori OS).
- [ ] Setel strategi eviksi ke `volatile-lru` atau `volatile-lfu` jika Redis berfungsi murni sebagai cache, bukan store permanen.
- [ ] Jangan gunakan perintah berat dengan kompleksitas waktu $O(N)$ di lingkungan produksi: `KEYS *`, `FLUSHALL`, atau `SMEMBERS` pada himpunan data masif. Gunakan alternatif non-blocking: `SCAN`, `SSCAN`, `HSCAN`.

#### Monitoring & Observability
- [ ] Pasang alarm CloudWatch:
  - DynamoDB: `SystemErrors`, `ThrottledRequests`, `SuccessfulRequestLatency`.
  - ElastiCache: `CPUUtilization` (EngineCPUUtilization > 75%), `DatabaseMemoryUsagePercentage` > 80%, `SwapUsage` > 50MB, `CurrConnections`.

---

### 12. Hands-on Practice: Multi-Tier Distributed Storage Platform

Langkah praktikum detail untuk menginisiasi infrastruktur berbasis Terraform. Simpan kode berikut ke dalam direktori: `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── main.tf
├── variables.tf
├── outputs.tf
└── terraform.tfvars
```

#### File: `hands-on/m02/variables.tf`
```hcl
variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "vpc_id" {
  type        = string
  description = "Target VPC ID untuk ElastiCache deployment"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Daftar Subnet ID Private (Minimal 3 AZ)"
}
```

#### File: `hands-on/m02/main.tf`
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# -----------------------------------------------------------------------------
# 1. DynamoDB Tier-0 Global Table Pattern
# -----------------------------------------------------------------------------
resource "aws_dynamodb_table" "enterprise_orders" {
  name             = "EnterpriseOrders-${var.environment}"
  billing_mode     = "PAY_PER_REQUEST" # On-Demand untuk variabilitas tinggi
  hash_key         = "PK"
  range_key        = "SK"
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  attribute {
    name = "GSI1PK"
    type = "S"
  }

  attribute {
    name = "GSI1SK"
    type = "S"
  }

  global_secondary_index {
    name            = "GSI1"
    hash_key        = "GSI1PK"
    range_key       = "GSI1SK"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ExpirationTimestamp"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# -----------------------------------------------------------------------------
# 2. ElastiCache Redis Subnet Group & Security Group
# -----------------------------------------------------------------------------
resource "aws_elasticache_subnet_group" "redis_subnet_group" {
  name       = "redis-subnets-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis_sg" {
  name        = "redis-sg-${var.environment}"
  description = "Security Group pengamanan akses ke Redis Cluster"
  vpc_id      = var.vpc_id

  ingress {
    description = "Izinkan akses internal VPC ke port Redis engine"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "redis-sg-${var.environment}"
    Environment = var.environment
  }
}

# -----------------------------------------------------------------------------
# 3. ElastiCache Parameter Group (Production Tuning)
# -----------------------------------------------------------------------------
resource "aws_elasticache_parameter_group" "redis_params" {
  family = "redis7"
  name   = "enterprise-redis7-params-${var.environment}"

  parameter {
    name  = "maxmemory-reserved-percent"
    value = "25"
  }

  parameter {
    name  = "cluster-enabled"
    value = "yes"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }
}

# -----------------------------------------------------------------------------
# 4. ElastiCache Redis Cluster (Cluster Mode Enabled)
# -----------------------------------------------------------------------------
resource "aws_elasticache_replication_group" "redis_cluster" {
  replication_group_id = "prod-cache-cluster"
  description          = "Enterprise Redis Cluster Mode Enabled"
  node_type            = "cache.m6g.large"
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.redis_params.name
  subnet_group_name    = aws_elasticache_subnet_group.redis_subnet_group.name
  security_group_ids   = [aws_security_group.redis_sg.id]

  num_node_groups         = 3 # 3 Primary Shards
  replicas_per_node_group = 1 # 1 Replica per Primary Shard (Total 6 Node)

  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
```

#### File: `hands-on/m02/outputs.tf`
```hcl
output "dynamodb_table_name" {
  value       = aws_dynamodb_table.enterprise_orders.name
  description = "Nama tabel DynamoDB"
}

output "dynamodb_table_arn" {
  value       = aws_dynamodb_table.enterprise_orders.arn
  description = "ARN dari tabel DynamoDB"
}

output "redis_configuration_endpoint" {
  value       = aws_elasticache_replication_group.redis_cluster.configuration_endpoint_address
  description = "Alamat endpoint konfigurasi cluster Redis untuk client connection string"
}
```

#### Panduan Eksekusi Step-by-Step
1. **Navigasi ke direktori modul**:
   ```bash
   cd hands-on/m02/
   ```
2. **Siapkan environment parameter**:
   Buat file `terraform.tfvars`:
   ```hcl
   vpc_id             = "vpc-0123456789abcdef0"
   private_subnet_ids = ["subnet-0a1b2c3d", "subnet-0e1f2a3b", "subnet-0c1d2e3f"]
   environment        = "production"
   aws_region         = "ap-southeast-1"
   ```
3. **Inisialisasi & Apply Resource**:
   ```bash
   terraform init
   terraform plan -out=tfplan.binary
   terraform apply tfplan.binary
   ```
4. **Verifikasi Status Cluster**:
   ```bash
   aws elasticache describe-replication-groups \
     --replication-group-id prod-cache-cluster \
     --region ap-southeast-1 \
     --query "ReplicationGroups[0].Status"
   ```
5. **Verifikasi Fitur Table Point-In-Time Recovery**:
   ```bash
   aws dynamodb describe-continuous-backups \
     --table-name EnterpriseOrders-production \
     --region ap-southeast-1
   ```

---

### 13. Exercise

#### Level Easy
Tuliskan perintah AWS CLI untuk memperbarui skema DynamoDB tabel `EnterpriseOrders-production` guna menambahkan sebuah atribut TTL bernama `ArchivalDate`.
*Ekspektasi Solusi*: Eksekusi CLI `aws dynamodb update-time-to-live` dengan argumen yang valid dan verifikasi status aktifnya.

#### Level Medium
Sebuah aplikasi web melaporkan bahwa pembacaan data pelanggan menggunakan kunci `user:profile:8812` menghasilkan kesalahan parsing JSON secara sporadis di lingkungan Redis Cluster.
Selidiki penyebabnya, dan buat skrip Bash/Python otomatis yang memeriksa metrik CloudWatch `EngineCPUUtilization` serta memvalidasi keselarasan key distribution menggunakan perintah `redis-cli -c -h <endpoint> cluster keyslot <key>`.

#### Level Hard
Buat dokumen desain arsitektur (disertai blok HCL Terraform tambahan) untuk mengonfigurasi replika multi-region DynamoDB Global Tables melintasi kawasan `ap-southeast-1` (Singapura) dan `ap-southeast-3` (Jakarta), dilengkapi mekanisme failover berbasis latency routing AWS Route 53 Application Recovery Controller (ARC).

---

### 14. Challenge

**Skenario**: Anda adalah Principal Distributed Systems Architect di sebuah bank digital global. Perusahaan berencana meluncurkan sistem pembukuan terdistribusi (*distributed financial ledger*) yang berjalan secara aktif di 3 AWS Region berbeda (`us-east-1`, `eu-west-1`, `ap-southeast-1`).
Sistem wajib melayani:
- Kapasitas penulisan global serentak (Multi-Master Active-Active Writes).
- Persyaratan strict non-negotiable: **Tidak boleh ada *Negative Balance Double Spending*** (misal: Saldo awal $100 ditarik $100 secara bersamaan di region London dan Singapura pada milidetik yang sama).

**Tantangan**:
1. Mengapa DynamoDB Global Tables dengan arsitektur native *Last-Writer-Wins (LWW)* akan gagal mempertahankan integritas finansial ini? Analisis titik kegagalannya berdasarkan hukum fisika transmisi data transatlantik (Speed of Light across fiber) dan Teorema CAP!
2. Rancang arsitektur alternatif hybrid di AWS yang memadukan AWS Global Database, ElastiCache Redis, DynamoDB Transact, atau mekanisme Consensus Locking eksternal untuk menyelesaikan masalah konsistensi lintas benua ini dengan latensi tetap di bawah 250ms untuk skenario terburuk.

*(Tantangan ini tidak memiliki solusi instan tunggal. Anda diharapkan menyusun argumen formal, kalkulasi latensi RTT antar benua, rancangan state machine terdistribusi, dan pembagian isolasi region yang kokoh).*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Berapa batas kapasitas penyimpanan data dan batasan throughput (WCU/RCU) fisik untuk satu partisi tunggal pada Amazon DynamoDB?**
   - A. 50 GB, 5.000 WCU, 10.000 RCU
   - B. 10 GB, 1.000 WCU, 3.000 RCU
   - C. 1 GB, 500 WCU, 1.000 RCU
   - D. Tidak terbatas, kapasitas mengikuti ukuran instans
   - *Jawaban*: **B**. Setiap partisi fisik DynamoDB dibatasi secara fundamental pada batas 10 GB data, 1.000 WCU, dan 3.000 RCU.

2. **Berapa jumlah Hash Slot total yang dialokasikan pada ElastiCache Redis Cluster Mode Enabled?**
   - A. 1.024
   - B. 4.096
   - C. 16.384
   - D. 65.536
   - *Jawaban*: **C**. Ruang partisi Redis Cluster secara baku terbagi menjadi tepat 16.384 *hash slots*.

3. **Perintah Redis manakah yang SANGAT BERBAHAYA dijalankan di lingkungan produksi berkapasitas jutaan entri karena memblokir thread eksekusi utama?**
   - A. `SCAN`
   - B. `KEYS *`
   - C. `HGETALL`
   - D. `TTL`
   - *Jawaban*: **B**. `KEYS *` bersifat $O(N)$ dan memindai seluruh *keyspace*, menyebabkan thread pengeksekusi perintah Redis terblokir hingga pembacaan selesai, sehingga node tampak tidak responsif.

4. **Operasi baca konsisten DynamoDB tipe apakah yang mengonsumsi kapasitas Read Capacity Unit (RCU) paling hemat?**
   - A. Strongly Consistent Read
   - B. Transactional Read
   - C. Eventually Consistent Read
   - D. Global Table Cross-Region Read
   - *Jawaban*: **C**. *Eventually Consistent Read* mengonsumsi separuh (0.5 RCU per 4KB data) dibanding *Strongly Consistent Read* (1 RCU per 4KB data).

5. **Apa fungsi utama dari parameter `maxmemory-reserved-percent` pada Amazon ElastiCache for Redis?**
   - A. Mengalokasikan RAM khusus untuk menyimpan histori pesan Pub/Sub.
   - B. Menyisihkan memori cadangan bagi OS dan operasional internal background (seperti replikasi dan snapshotting) agar proses tidak dimatikan paksa oleh Linux OOM Killer.
   - C. Menentukan kapasitas maksimum partisi Swap disk.
   - D. Membatasi pemakaian RAM oleh koneksi client yang idle.
   - *Jawaban*: **B**. Parameter ini mencadangkan porsi memori non-data untuk overhead replikasi dan mekanisme failover agar mesin tetap stabil.

---

#### Intermediate (5 Pertanyaan)
6. **Dalam ElastiCache for Redis, jika sebuah aplikasi sering menjalankan perintah transaksi multi-key (`MGET` atau transaksi `MULTI/EXEC`), bagaimana cara memastikan seluruh key terkait berada di dalam satu Shard yang sama?**
   - A. Menggunakan Custom Parameter Group khusus transaksi.
   - B. Mematikan Cluster Mode dan menggunakan Read Replica tunggal.
   - C. Menggunakan notasi Hash Tag `{...}` pada kunci (contoh: `{user100}:profile` dan `{user100}:orders`).
   - D. Menjalankan skrip Lua tanpa batasan penamaan key.
   - *Jawaban*: **C**. String di dalam tanda kurung kurawal `{}` memaksa fungsi hashing CRC16 hanya menghitung teks di dalam tanda kurung tersebut, memastikan semua key jatuh pada *hash slot* yang sama.

7. **Bagaimana Amazon DynamoDB menangani skenario konflik penulisan konkuren pada Global Tables v2 yang menggunakan replikasi asinkronus multi-region?**
   - A. Two-Phase Commit (2PC) melintasi region.
   - B. Menggunakan algoritma *Last-Writer-Wins* (LWW) berbasis timestamp rekonsiliasi internal.
   - C. Menolak penulisan kedua dan melempar `ConcurrentModificationException`.
   - D. Mengubah status item menjadi *Divergent State* dan memicu intervensi manual operator.
   - *Jawaban*: **B**. DynamoDB Global Tables menerapkan resolusi konflik berbasis *Last-Writer-Wins* (LWW), di mana modifikasi dengan timestamp Paxos Leader paling akhir akan menimpa data sebelumnya.

8. **Apa dampak langsung yang terjadi jika Global Secondary Index (GSI) pada tabel DynamoDB kehabisan kapasitas tulis (mengalami throttling)?**
   - A. Base Table (tabel utama) tetap berjalan lancar, hanya data di GSI yang tertinggal permanen.
   - B. DynamoDB otomatis menghapus indeks GSI tersebut.
   - C. Base Table akan mengalami *backpressure throttling* dan menolak transaksi tulis baru demi menjaga agar replikasi data ke GSI tidak tertinggal terlalu jauh.
   - D. DynamoDB mengubah status kapasitas GSI menjadi Unlimited secara otomatis dan menagih biaya ganda.
   - *Jawaban*: **C**. Untuk mencegah inkonsistensi yang tidak terkendali antara tabel dasar dan GSI, sistem internal storage akan menahan dan mencekik throughput tulis pada tabel utama.

9. **Mengapa algoritma XFetch (Probabilistic Early Expiration) lebih unggul daripada sekadar menggunakan TTL statis yang ditambahkan angka acak (Jittered TTL) dalam menanggulangi Cache Stampede?**
   - A. Karena XFetch mengenkripsi data payload di dalam Redis.
   - B. Karena XFetch mempertimbangkan waktu komputasi query (*computation delta*) dan beban trafik aktual secara dinamis, sehingga refresh asinkronus terjadi tepat sebelum data kedaluwarsa sesuai probabilitas kebutuhan.
   - C. Karena XFetch menghilangkan kebutuhan koneksi jaringan ke database sekunder.
   - D. Karena XFetch mematikan fungsi eviksi memori bawaan Redis.
   - *Jawaban*: **B**. XFetch menggunakan rumus probabilitas variabel yang memperhitungkan durasi eksekusi data (`delta`) dan interval waktu tersisa, sehingga komputasi ulang dilakukan secara adaptif oleh salah satu worker tanpa memicu tabrakan massal.

10. **Ketika sebuah Redis Primary node mengalami hardware crash mendadak pada cluster Multi-AZ, proses internal apakah yang dijalankan oleh ElastiCache?**
    - A. Node langsung dinyalakan ulang (*hard restart*) tanpa mengubah topologi; traffic ditolak sampai proses boot selesai.
    - B. Node Replica dengan replication lag terendah dipromosikan menjadi Primary baru melalui pemilihan voting Gossip Protocol, dan endpoint konfigurasi diperbarui secara otomatis.
    - C. Shard tersebut dihapus permanen dari ruang 16.384 slot.
    - D. Seluruh data di shard lain dibekukan ke mode Read-Only untuk mencegah sinkronisasi parsial.
    - *Jawaban*: **B**. Mekanisme failover otonom mempromosikan replika yang paling mutakhir menjadi Primary, mendistribusikan informasi topologi baru ke cluster, dan mengarahkan DNS internal tanpa memerlukan konfigurasi ulang pada sisi aplikasi.

---

#### Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario**: Sistem deteksi fraud perbankan memproses 80.000 TPS transaksi kartu kredit. Setiap transaksi harus memeriksa riwayat IP dalam 10 detik terakhir di DynamoDB. Anda melihat alarm CloudWatch `ReadThrottleEvents` berkedip pada tabel DynamoDB, padahal tabel disetel pada *On-Demand Mode*. Latensi API melonjak dari 15ms ke 3.000ms.
    - **Analisis & Solusi**: Mengapa tabel On-Demand masih mengalami *throttling*, dan apa langkah mitigasi teknis tercepat yang harus Anda lakukan?
    - *Solusi Engineering*: DynamoDB On-Demand mentoleransi lonjakan instan hingga 2x lipat dari *peak traffic* yang pernah dicapai sebelumnya. Jika trafik melonjak >2x secara instan, atau jika lonjakan tersebut tertumpu pada satu partisi kunci (*Hot Partition*), kapasitas partisi fisik (3.000 RCU) tetap terlampaui. Mitigasi:
      1. Terapkan partisi ulang (*key re-hashing*) atau *Synthetic Sharding* pada partition key untuk mendistribusikan beban.
      2. Sisipkan lapisan ElastiCache for Redis di depan DynamoDB untuk melayani pola *read-intensive* berulang dengan latensi sub-milidetik.

12. **Skenario**: Di tengah migrasi ke ElastiCache Redis Cluster (Cluster Mode Enabled) dengan 4 shards, engineer Anda menjalankan batch worker yang mengeksekusi instruksi:
    `redisClient.Del(ctx, "orders:2026:january", "orders:2026:february", "customers:active")`
    Aplikasi seketika mengalami crash dengan error: `CROSSSLOT Keys in request don't hash to the same slot`.
    - **Analisis & Solusi**: Mengapa kesalahan ini muncul pada level protokol Redis, dan bagaimana perbaikan kode yang harus diterapkan oleh tim pengembang?
    - *Solusi Engineering*: Dalam mode Redis Cluster, operasi yang menerima argumen multi-key (`DEL`, `MGET`, `MSET`) mewajibkan semua parameter key tersebut berada dalam satu *hash slot* yang identik. Karena ketiga key tersebut menghasilkan nilai kalkulasi `CRC16(key) % 16384` yang berbeda-beda, perintah tersebut ditolak oleh cluster node. Solusi:
      1. Pisahkan pemanggilan menjadi perintah tunggal individual (menjalankan 3x `DEL` secara paralel melalui pipeline).
      2. Jika key tersebut memang wajib dihapus secara atomik bersamaan, gunakan *Hash Tag* yang seragam saat proses penulisan awal: `{orders}:2026:january`, `{orders}:2026:february`.

13. **Skenario**: Anda mendesain arsitektur basis data untuk sistem voting live TV streaming di AWS. Ada 5 kandidat. Pemirsa mengirimkan SMS/Vote secara bersamaan (diperkirakan 500.000 vote dalam kurun waktu 60 detik). Jika Anda langsung melakukan pembaruan counter `UpdateItem` ke 5 item kandidat di DynamoDB, tabel pasti mengalami *hot partition throttling* parah.
    - **Rancangan Solusi**: Bagaimana Anda merancang topologi penanganan counter terdistribusi menggunakan kombinasi Redis dan DynamoDB untuk menyerap beban ini secara akurat dan hemat biaya?
    - *Solusi Engineering*:
      1. **Layer 1 (Ingestion & Atomic Aggregation)**: Arahkan vote masuk ke cluster ElastiCache Redis. Gunakan perintah atomic `HINCRBY candidate_counter <candidate_id> 1`. Karena Redis mengeksekusi operasi in-memory pada skala jutaan IOPS, beban 500k vote dalam 60 detik (~8.300 TPS) dapat diserap dengan mudah oleh satu instans tanpa latency degradation.
      2. **Layer 2 (Decoupled Flushing)**: Pasang service terjadwal (misal: worker Go atau AWS Lambda yang dipicu EventBridge setiap 5 detik) untuk membaca counter terkumpul dari Redis menggunakan pola *Snapshot and Reset* atau skrip Lua atomik.
      3. **Layer 3 (DDB Persistence)**: Worker mengirimkan data akumulasi agregat berkala (misal: "Kandidat A: +25.000 suara") ke DynamoDB menggunakan satu panggilan `UpdateItem`. Hasilnya, DynamoDB hanya menerima puluhan write requests berukuran kecil, meniadakan risiko throttling sama sekali dan memangkas konsumsi WCU hingga 99.9%.

---

### 16. Summary

1. **DynamoDB Internal Mechanics**: DynamoDB mendistribusikan data ke partisi fisik (maksimal 10 GB, 1.000 WCU, 3.000 RCU) yang direplikasi ke 3 AZ menggunakan konsensus **Paxos**. Performa tinggi hanya dapat diraih jika skema tabel mendistribusikan akses kunci secara homogen untuk menghindari *Hot Partitions*.
2. **ElastiCache Redis Cluster Engine**: Redis Cluster membagi *keyspace* ke dalam **16.384 Hash Slots**. Untuk performa berskala masif, client wajib memahami topologi slot (*cluster-aware*) dan pengembang harus menggunakan teknik *Hash Tags* `{...}` jika membutuhkan koordinasi atomic multi-key.
3. **Resilience & Fault Tolerance**: Mengandalkan TTL konvensional pada caching layer membuka celah bencana *Cache Stampede*. Implementasi algoritma modern seperti **Probabilistic Early Expiration (XFetch)** dan penggunaan **Write-Sharding** pada GSI merupakan standar mutlak bagi keandalan sistem berstandar *Tier-0 Enterprise*.
4. **Active-Active Trade-offs**: DynamoDB Global Tables menyederhanakan replikasi antar kawasan secara multi-master, namun resolusi konflik asinkronus menggunakan **Last-Writer-Wins (LWW)** memerlukan desain aplikasi cermat jika diterapkan pada transaksi finansial yang sensitif terhadap anomali penulisan konkuren serentak.