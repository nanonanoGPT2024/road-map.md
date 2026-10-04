# BAB 08: Skalabilitas Horizontal dengan Redis Cluster
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal Redis Cluster, termasuk mekanika *Cluster Bus*, *Gossip Protocol*, dan state machine *failover*.
- Memahami formulasi partisi data berbasis 16.384 *hash slots*, implementasi *hash tags*, dan algoritma deteksi tabrakan slot.
- Menganalisis dan menangani respons pengalihan (*redirection*) `-MOVED` dan `-ASK` secara komprehensif pada level protokol maupun *smart client driver*.
- Menjalankan orkestrasi *online resharding* (migrasi slot tanpa *downtime*) dan mitigasi *state* inkonsisten (`MIGRATING` vs `IMPORTING`).
- Merancang topologi Redis Cluster kelas enterprise dengan toleransi kegagalan Multi-AZ (Availability Zone), memitigasi anomali *split-brain*, dan mengonfigurasi parameter *network-announce* pada lingkungan tervirtualisasi/kontainer.
- Mengidentifikasi, mengisolasi, dan merehabilitasi status kegagalan klaster (`CLUSTERDOWN`) melalui observabilitas metrik dan prosedur resolusi teknis.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib memahami:
- Konsep dasar replikasi Redis Master-Replica dan Redis Sentinel (Bab 07).
- Pemahaman protokol TCP/IP, model koneksi non-blocking I/O multiplexing, dan networking dasar (port binding, NAT, routing subnetwork).
- Pengalaman praktis menggunakan Redis CLI dan salah satu bahasa pemrograman backend tingkat menengah-lanjut (misal: Go, Java, atau Python).
- Pemahaman teori sistem terdistribusi: teorema CAP/PACELC, model konsensus kuorum, dan fenomena partisi jaringan (*network partition*).

---

### 3. Concept & Internal Architecture (Mendalam)

Redis Cluster mengimplementasikan sistem terdistribusi bertipe *share-nothing architecture*, di mana setiap *node* menyimpan sebagian subset data dan mengoordinasikan status klaster tanpa ketergantungan pada *orchestrator* eksternal seperti Apache ZooKeeper atau Consul.

```
+-------------------------------------------------------------------------+
|                              REDIS CLUSTER                              |
+-------------------------------------------------------------------------+
|  +------------------+     Cluster Bus (Gossip)    +------------------+  |
|  |   Master Node A  |<===========================>|   Master Node B  |  |
|  | Slots: 0 - 5460  |     Port: 16379 (TCP binary)| Slots: 5461-10922|  |
|  +------------------+                             +------------------+  |
|           |                                                |            |
|    Async Replication                                Async Replication   |
|           v                                                v            |
|  +------------------+                             +------------------+  |
|  |  Replica Node A1 |                             |  Replica Node B1 |  |
|  +------------------+                             +------------------+  |
+-------------------------------------------------------------------------+
```

#### A. Data Sharding & Algoritma Hash Slot
Ruang kunci Redis Cluster dibagi secara deterministik ke dalam $16.384$ ($2^{14}$) *logical hash slots*. Formula penentuan slot untuk sembarang *key* adalah:

$$\text{Slot} = \text{CRC16}(K) \pmod{16384}$$

Di mana $K$ adalah representasi biner dari kunci data, atau substring di dalam sepasang kurung kurawal pertama `{...}` jika *Hash Tag* disematkan. CRC16 yang digunakan mengimplementasikan standar polinomial $X^{16} + X^{12} + X^5 + 1$ (CRC-16/CCITT).

Setiap master node bertanggung jawab atas rentang slot tertentu. Peta penugasan slot (*Slot-to-Node mapping*) direpresentasikan dalam array bitmap sebesar $16.384$ bit (2048 byte):

```
+---+---+---+---+---+---+---+---+-----------------+
| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | ... 16383       |  -> 2048 Bytes Array
+---+---+---+---+---+---+---+---+-----------------+
| 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | ...             |  -> 1: Assigned, 0: Unassigned
+---+---+---+---+---+---+---+---+-----------------+
```

Penyimpanan bitmap ini memungkinkan transmisi topologi slot antar-node secara ringkas melalui Gossip Protocol tanpa membebani *overhead* jaringan.

#### B. Cluster Bus & Gossip Protocol
Setiap node Redis membuka dua port TCP secara bersamaan:
1. **Client Port** (default: `6379`): Melayani perintah dari klien menggunakan protokol RESP (*Redis Serialization Protocol*).
2. **Cluster Bus Port** (default: `16379` atau Client Port + `10000`): Kanal komunikasi node-ke-node menggunakan protokol biner proprietary yang teroptimasi untuk latency rendah.

Node saling bertukar informasi status menggunakan *Gossip Protocol*. Pesan-pesan Gossip mencakup:
- **`MEET`**: Memerintahkan node penerima untuk bergabung ke dalam klaster yang sudah ada.
- **`PING`**: Node secara periodik memilih acak beberapa node lain (termasuk node yang paling lama tidak mengirim ping) untuk mengirim status lokalnya beserta sebagian kecil tabel topologi node lain yang ia ketahui.
- **`PONG`**: Respons terhadap `PING` atau pengumuman *broadcast* konfigurasi baru pasca-failover.
- **`FAIL`**: Broadcast agresif ketika sebuah master mendeteksi master lain mengalami down dan telah divalidasi oleh mayoritas master.
- **`PUBLISH`**: Replikasi pesan Pub/Sub ke seluruh node dalam klaster.

#### C. Mekanisme Failover, Epoch, dan Voting Consensus
Redis Cluster menggunakan konsep **Epoch** (terinspirasi dari *Term* pada algoritma Raft) untuk menangani *versioning* konfigurasi dan mencegah pembaruan status yang usang (*stale updates*):
1. **Current Epoch**: Integer 64-bit yang merepresentasikan penghitung waktu logis (*logical clock*) klaster.
2. **Config Epoch**: Nilai unik yang diberikan pada master tertentu untuk mengklaim kepemilikan hash slot.

**Siklus Failover Otomatis:**
1. **Deteksi Suspect (`PFAIL` - Possible Fail):** Jika Master A tidak menerima `PONG` dari Master B selama durasi `cluster-node-timeout`, Master A menandai Master B sebagai `PFAIL`.
2. **Konfirmasi Fail (`FAIL`):** Melalui Gossip header, jika Master A mengumpulkan konfirmasi bahwa mayoritas master melihat Master B dalam status `PFAIL`, Master A mengubah status B menjadi `FAIL` dan mempublikasikan pesan `FAIL` ke seluruh klaster.
3. **Pemilihan Kandidat (Replica Failover Authorization):**
   - Replica dari Master B yang mengalami `FAIL` mendeteksi kondisi ketiadaan master.
   - Replica menunda inisiasi pemilihan berdasarkan *offset* replikasi data:
     $$\text{Delay} = 500\text{ms} + \text{random}(0, 500\text{ms}) + (\text{Master Offset} - \text{Replica Offset}) \times \text{Factor}$$
     Replica dengan data paling mutakhir (offset tertinggi) akan memulai *election* lebih awal.
4. **Voting:**
   - Replica menaikkan `currentEpoch` dan menyiarkan paket `FAILOVER_AUTH_REQUEST`.
   - Hanya master yang valid yang memiliki hak suara. Setiap master hanya dapat memberikan 1 suara per epoch (`FAILOVER_AUTH_ACK`).
   - Jika Replica mendapatkan suara dari $\lfloor N/2 \rfloor + 1$ master (kuorum mayoritas), Replica tersebut memenangkan pemilihan.
5. **Promosi & Klaim Slot:**
   - Replica terpilih mengubah perannya menjadi Master, menetapkan `configEpoch = currentEpoch`, mengambil alih slot milik master lama, dan menyiarkan pesan `PONG` broadcast untuk memperbarui cache topologi seluruh klaster.

---

### 4. Why & What

| Dimensi | Standalone Redis | Redis Sentinel | Redis Cluster |
| :--- | :--- | :--- | :--- |
| **Batas Memori** | Dibatasi oleh kapasitas RAM satu host fisik. | Dibatasi oleh kapasitas RAM satu master aktif. | Terdistribusi secara horizontal (skala Terabyte lintas ratusan node). |
| **Skalabilitas Tulis**| Skala vertikal (1 core utama via event-loop). | Skala vertikal (semua penulisan ke 1 master tunggal). | Skala horizontal (paralelisasi operasi tulis ke multi-master). |
| **Topologi Jaringan**| Titik tunggal (Single Point). | Sentralisasi via Sentinel Daemon eksternal. | *Decentralized peer-to-peer* (Gossip protocol). |
| **Operasi Multi-Key**| Didukung penuh tanpa restriksi. | Didukung penuh tanpa restriksi. | Terbatas pada kunci dalam satu hash slot (wajib Hash Tag). |
| **Kompleksitas Klien**| Rendah (koneksi standar TCP RESP). | Menengah (klien memantau Sentinel API). | Tinggi (*smart client* mengelola slot routing & redirection). |

**Kapan Harus Menggunakan Redis Cluster:**
- Total *working set memory* melampaui kemampuan RAM instance tunggal yang hemat biaya (biasanya > 64 GB/128 GB).
- *Throughput* penulisan aplikasi melampaui batas eksekusi *single-threaded* Redis engine (> 100.000 QPS penulisan intensif).
- Diperlukan arsitektur dengan isolasi kegagalan (*blast radius mitigation*): jika 1 master mati, hanya sebagian kecil slot yang terdampak sementara selama proses failover.

---

### 5. How (Workflow Detail)

#### A. Alur Pemrosesan Perintah & Pengalihan Klien (-MOVED vs -ASK)

```
[Client Application]
        |
   1. SET user:100 "data"  --> (Hash: Slot 12539)
        |
        +-----------------------------------> [Master Node A (Slots: 0 - 5460)]
                                                         |
                                       Evaluasi: Apakah Slot 12539 milik saya?
                                                         |
                                                       TIDAK
                                                         |
   2. <- Error: -MOVED 12539 10.0.1.2:6379 --------------+
        |
        |  (Smart Client memperbarui tabel internal Slot 12539 -> 10.0.1.2)
        |
   3. SET user:100 "data" -------------------------------------------------> [Master Node C (Slots: 10923 - 16383)]
                                                                                             |
                                                                               Status: Execution OK
                                                                                             |
   4. <- +OK --------------------------------------------------------------------------------+
```

1. **Kasus `-MOVED` (Permanent Redirection):**
   - Terjadi ketika klien mengirim perintah ke node yang bukan pemilik hash slot tersebut.
   - Respons: `-MOVED <slot_id> <target_ip>:<target_port>`.
   - Respons ini bersifat instruksional bagi *Smart Client* untuk memperbarui tabel routing in-memory miliknya secara permanen untuk slot tersebut.

2. **Kasus `-ASK` (Transient Redirection selama Resharding):**
   - Terjadi saat migrasi slot sedang berjalan dari Node Sumber ke Node Target. Kunci spesifik yang dicari belum atau sudah berpindah.
   - Jika kunci belum berada di target, node asal masih melayaninya. Namun, jika slot dalam status `MIGRATING` dan kunci tidak ditemukan secara lokal, node asal mengembalikan respons `-ASK <slot_id> <target_ip>:<target_port>`.
   - Klien **tidak boleh** memperbarui tabel mapping permanennya.
   - Klien wajib mengirim perintah `ASKING` terlebih dahulu ke target node sebelum mengeksekusi perintah asli, agar target node menerima query untuk slot yang statusnya masih `IMPORTING`.

```
[Client]                [Source Node (Migrating)]       [Target Node (Importing)]
   |                                |                               |
   |--- 1. GET key_in_slot_50 ----->|                               |
   |    (Key tidak ada di Source)   |                               |
   |<-- 2. -ASK 50 10.0.1.2:6379 ---|                               |
   |                                                                |
   |--- 3. ASKING ------------------------------------------------->|
   |<-- 4. +OK -----------------------------------------------------|
   |--- 5. GET key_in_slot_50 ------------------------------------->|
   |<-- 6. "value_data" --------------------------------------------|
```

#### B. Mekanisme Migrasi Slot (Online Resharding)
Migrasi slot $S$ dari Node A ke Node B berlangsung dalam status terkontrol:
1. Tandai Node B: `CLUSTER SETSLOT S IMPORTING <Node-A-ID>`
2. Tandai Node A: `CLUSTER SETSLOT S MIGRATING <Node-B-ID>`
3. Ambil data: Node A mengeksekusi `CLUSTER GETKEYSINSLOT S <count>`
4. Pindahkan data atomik per-key: `MIGRATE <Node-B-IP> <Node-B-Port> "" 0 <timeout> KEYS key1 key2 ...`
5. Setelah seluruh kunci dalam slot $S$ berpindah, sinkronisasikan status final ke seluruh klaster: `CLUSTER SETSLOT S NODE <Node-B-ID>`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kantor Pos Terdesentralisasi dengan Kotak Surat Berkode
Bayangkan sistem pos dengan 16.384 kotak pos yang dibagi ke 3 gedung sortir (Master Node):
- **Gedung A** memegang kotak 0 – 5460.
- **Gedung B** memegang kotak 5461 – 10922.
- **Gedung C** memegang kotak 10923 – 16383.

Kurir cerdas (*Smart Client*) membawa catatan lokal gedung mana yang memegang kotak nomor berapa.
- Jika pengguna ingin mengirim surat dengan alamat `user:999`, kurir menghitung nomor kotak dengan formula matematika CRC16 modulo 16384, ketemu nomor 8000.
- Kurir langsung pergi ke **Gedung B**.
- Jika kurir salah pergi ke **Gedung A**, petugas Gedung A tidak akan meneleponkan Gedung B, melainkan berteriak: *"Pindah ke Gedung B! Kode kotak ini milik Gedung B!"* (`-MOVED`). Kurir mencatat hal ini di buku petanya agar tidak salah lagi.
- Jika Gedung B sedang memindahkan kotak 8000 ke Gedung C (*Resharding*), petugas Gedung B berkata: *"Khusus surat ini, tanyakan ke Gedung C dengan izin khusus!"* (`-ASK`). Kurir mengetuk pintu Gedung C membawa izin (`ASKING`), lalu menyerahkan surat.

```
       [Slot Distribution Architecture Across Nodes]

       +-------------------------------------------------------+
       |                  16384 Hash Slots                     |
       +-------------------------------------------------------+
       |   0 ................. 5460   | Node Alpha (Master)    |
       |   5461 ............. 10922   | Node Beta  (Master)    |
       |   10923 ............ 16383   | Node Gamma (Master)    |
       +-------------------------------------------------------+

       Hash Tag Mechanism:
       Key: "orders:{tenant_99}:2026-A"  ===> Hash calculation applies
       Key: "invoices:{tenant_99}:9081"  ===> ONLY to "tenant_99"
                                              Guaranteed to reside in
                                              the EXACT SAME SLOT!
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Setup Klaster Sederhana & CLI Verification
```bash
# Membuat koneksi ke salah satu node cluster via redis-cli dengan flag '-c' (cluster mode)
redis-cli -c -h 127.0.0.1 -p 7000

# Cek penugasan cluster
127.0.0.1:7000> CLUSTER NODES
# Output menampilkan: <node-id> <ip:port> <flags> <master-id> <ping-sent> <pong-recv> <config-epoch> <link-state> <slots>

# Pengujian routing otomatis:
127.0.0.1:7000> SET alpha "world"
-> Redirected to slot 14592 located at 127.0.0.1:7002
OK

127.0.0.1:7002> GET alpha
"world"
```

#### Practical Example: Implementasi Smart Client Enterprise Tingkat Lanjut (Go)
Contoh berikut menggunakan library `go-redis/v9` dengan konfigurasi *connection pooling*, penanganan kegagalan klaster, dan penggunaan Hash Tag untuk transaksi multi-key yang aman:

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

type ClusterRepository struct {
	client *redis.ClusterClient
}

func NewClusterRepository(addrs []string) (*ClusterRepository, error) {
	// Konfigurasi Enterprise Cluster Client
	rdb := redis.NewClusterClient(&redis.ClusterOptions{
		Addrs:        addrs,
		MaxRedirects: 8, // Toleransi redirection -MOVED/-ASK saat resharding
		ReadOnly:     false, // True jika ingin membagi beban pembacaan ke Replica

		// Pool configuration
		PoolSize:        50,
		MinIdleConns:    10,
		ConnMaxIdleTime: 5 * time.Minute,
		ConnMaxLifetime: 1 * time.Hour,

		// Resiliency & Timeouts
		DialTimeout:  2 * time.Second,
		ReadTimeout:  500 * time.Millisecond,
		WriteTimeout: 500 * time.Millisecond,

		// Otomatis reload cluster topology saat terjadi failover/resharding
		RouteRandomly: false,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed connecting to redis cluster: %w", err)
	}

	return &ClusterRepository{client: rdb}, nil
}

// TransferBalance memindahkan saldo antar user dalam satu tenant menggunakan Hash Tags.
// Wajib berada di slot yang sama dengan syntax: {tenantID}
func (r *ClusterRepository) TransferBalance(ctx context.Context, tenantID string, fromUser, toUser string, amount int64) error {
	// Memastikan kedua key berada pada Hash Slot yang identik menggunakan Hash Tag {...}
	fromKey := fmt.Sprintf("{tenant:%s}:user:%s:balance", tenantID, fromUser)
	toKey := fmt.Sprintf("{tenant:%s}:user:%s:balance", tenantID, toUser)

	// Optimistic locking menggunakan WATCH
	txf := func(tx *redis.Tx) error {
		// Ambil saldo pengirim
		bal, err := tx.Get(ctx, fromKey).Int64()
		if err != nil && !errors.Is(err, redis.Nil) {
			return err
		}
		if bal < amount {
			return errors.New("insufficient balance")
		}

		// Eksekusi atomik mutasi kredit & debit
		_, err = tx.TxPipelined(ctx, func(pipe redis.Pipeliner) error {
			pipe.DecrBy(ctx, fromKey, amount)
			pipe.IncrBy(ctx, toKey, amount)
			return nil
		})
		return err
	}

	// Retry loop jika terjadi konflik WATCH (CAS concurrency failure)
	maxRetries := 3
	for i := 0; i < maxRetries; i++ {
		err := r.client.Watch(ctx, txf, fromKey, toKey)
		if err == nil {
			return nil // Transaksi sukses
		}
		if errors.Is(err, redis.TxFailedErr) {
			// Tabrakan konkurensi, lakukan loop ulang
			time.Sleep(10 * time.Millisecond)
			continue
		}
		return fmt.Errorf("transaction execution error: %w", err)
	}

	return errors.New("transaction failed: maximum retry limit exceeded")
}

func main() {
	clusterSeedNodes := []string{
		"10.0.10.1:6379",
		"10.0.10.2:6379",
		"10.0.10.3:6379",
	}

	repo, err := NewClusterRepository(clusterSeedNodes)
	if err != nil {
		log.Fatalf("Cluster init error: %v", err)
	}
	defer repo.client.Close()

	ctx := context.Background()
	tenant := "acme_corp"

	// Inisialisasi data saldo awal
	repo.client.Set(ctx, fmt.Sprintf("{tenant:%s}:user:alice:balance", tenant), 1000, 0)
	repo.client.Set(ctx, fmt.Sprintf("{tenant:%s}:user:bob:balance", tenant), 200, 0)

	// Eksekusi pemindahan dana atomik
	err = repo.TransferBalance(ctx, tenant, "alice", "bob", 250)
	if err != nil {
		log.Fatalf("Transfer failed: %v", err)
	}

	log.Println("Transfer berhasil dieksekusi dalam hash slot yang terisolasi.")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Tier-1 E-Commerce Flash Sale Architecture
- **Beban Puncak:** 1.200.000 QPS baca, 350.000 QPS tulis.
- **Topologi:** 36 Node Redis Cluster (18 Master, 18 Replica) terdistribusi di 3 AWS Availability Zones (AZ-a, AZ-b, AZ-c). Total memori 1,5 TB.
- **Masalah:** Saat kampanye Flash Sale dibuka, terjadi *traffic unbalance* ekstrem (*Hot Slot Bottleneck*). Kunci keranjang belanja dan *flash-sale product inventories* membanjiri satu master tunggal, memicu saturasi CPU 100% dan *Gossip heartbeat drop*, yang menyebabkan master tersebut dianggap `PFAIL` secara keliru.

#### Analisis Kegagalan & Solusi Arsitektural:

```
[KONDISI BURUK: Hot Slot Overload]
Semua transaksi mengarah ke {flash_sale}:item_99
  -> Hash Slot = 10452 (Berada di Master-5)
  -> Master-5 CPU: 100% | Master 1-4, 6-18 CPU: 5%
  -> Master-5 telat balas PING -> Klaster memicu Split-Brain / False Failover!

[SOLUSI ARSITEKTURAL: Key Salting + Asynchronous Drainage]
1. Read Optimization:
   Key "inventory:{flash_sale}:item_99" di-breakdown secara deterministik:
   -> "inventory:{flash_sale}:item_99:bucket_0" (Slot X -> Master 2)
   -> "inventory:{flash_sale}:item_99:bucket_1" (Slot Y -> Master 8)
   -> "inventory:{flash_sale}:item_99:bucket_2" (Slot Z -> Master 14)
   Aplikasi klien merandom pembacaan ke salah satu bucket (read-distribution).

2. Network Announce Fix (Multi-AZ K8s):
   Menghindari cross-AZ latency penalty saat Gossip Sync, parameter
   cluster-announce diatur via StatefulSet:
   cluster-announce-ip: <Pod_Host_IP>
   cluster-announce-port: 6379
   cluster-announce-bus-port: 16379
```

Dengan teknik *Bucket Partitioning*, throughput tulis dan baca berhasil didistribusikan secara rata ke 18 master node, menurunkan utilisasi CPU Master-5 dari 100% ke 18%, serta menghilangkan fenomena *false failover*.

---

### 9. Trade-offs

| Keuntungan | Konsekuensi / Kerugian |
| :--- | :--- |
| **Kapasitas Skala Horizontal Linier:** Dapat menampung data melampaui limitasi RAM satu server fisik secara transparan. | **Operasi Multi-Key Terbatas:** Operasi seperti `MGET`, `MSET`, `SUNION`, transaksi `MULTI/EXEC` memicu error `CROSSSLOT Keys in request don't hash to the same slot` kecuali semua key berbagi Hash Tag `{...}` yang sama. |
| **Failover Otomatis Tanpa Sentinel:** Tidak membutuhkan komponen orkestrator eksternal; node master secara internal melakukan konsensus kuorum untuk mempromosikan replica. | **Overhead Jaringan Gossip:** Pada klaster berskala sangat besar (> 400 node), paket data Gossip heartbeat dapat mengonsumsi bandwidth gigabit internal jika parameter timeout tidak disetel dengan benar. |
| **Toleransi Kegagalan Terisolasi:** Matinya salah satu master hanya mengunci 1/N fraksi slot selama jendela waktu failover (umumnya 1–3 detik). | **Konsistensi Data Lemah (Eventual Consistency):** Replikasi asinkron Redis Master-ke-Replica membuka celah hilangnya data (*data loss*) jika Master mati mendadak sebelum data sempat terkirim ke Replica. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: Error `CROSSSLOT Keys in request don't hash to the same slot`
- **Penyebab:** Eksekusi perintah multi-key (seperti `MGET key1 key2` atau transaksi Lua/Pipelining) di mana `key1` dan `key2` menghasilkan nilai CRC16 modulo 16384 yang berbeda, sehingga ditugaskan ke node yang berbeda.
- **Solusi:** Gunakan **Hash Tags**. Bungkus substring penentu sharding dengan kurung kurawal `{...}`.
  - *Salah:* `SET user:100:name "John"` dan `SET user:100:profile "Active"`
  - *Benar:* `SET {user:100}:name "John"` dan `SET {user:100}:profile "Active"`

#### 2. Masalah: Klaster Terkunci Menjadi Status `CLUSTERDOWN The cluster is down`
- **Penyebab:** Terjadi ketika ada satu atau lebih hash slot yang tidak terikat ke master aktif mana pun, dan konfigurasi klaster mengaktifkan `cluster-require-full-coverage yes` (default pada versi-versi lawas).
- **Solusi:**
  1. Setel pada `redis.conf`: `cluster-require-full-coverage no` agar klaster tetap melayani slot-slot yang sehat meskipun sebagian slot offline.
  2. Pulihkan slot yang hilang via CLI:
     ```bash
     redis-cli -h <active-node> -p 6379 cluster slots
     # Bind kembali slot yatim secara paksa (Hati-hati terhadap potensi data clash)
     redis-cli -h <active-node> -p 6379 CLUSTER ADDSLOTS <slot_id>
     ```

#### 3. Masalah: False Failover & Network Flapping di Lingkungan Container/Kubernetes
- **Penyebab:** Nilai `cluster-node-timeout` terlalu agresif (misal: default 15000ms diturunkan menjadi 1000ms) di lingkungan cloud dengan jitter jaringan atau pause Stop-the-World GC pada aplikasi pod tetangga.
- **Solusi:** Naikkan `cluster-node-timeout` ke rentang konservatif (15000ms – 30000ms). Tambahkan parameter proteksi:
  ```text
  cluster-replica-validity-factor 10
  cluster-migration-barrier 1
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Distribusi Node Lintas Availability Zone (Multi-AZ):** Pastikan Master A berada di AZ-1, sementara Replica A1 berada di AZ-2. Jangan pernah menempatkan Master dan Replicanya pada rak/server fisik yang sama.
- [ ] **Alokasi Core Jaringan Bus Terisolasi:** Pastikan port client (6379) dan cluster bus (16379) terbuka di firewall antar-node secara aman, tanpa diekspos ke publik internet.
- [ ] **Nonaktifkan Full Coverage Requirement:** Konfigurasikan `cluster-require-full-coverage no` untuk menjamin ketersediaan parsial sistem (*high availability of remaining slots*).
- [ ] **Atur Batas Proteksi Split-Brain:**
  ```text
  min-replicas-to-write 1
  min-replicas-max-lag 10
  ```
- [ ] **Konfigurasi Announce IP Eksplisit (Container/Docker/K8s Overlay):**
  ```text
  cluster-announce-ip <Node_Routable_IP>
  cluster-announce-port 6379
  cluster-announce-bus-port 16379
  ```
- [ ] **Smart Client Pool Sizing:** Hindari inisialisasi instance cluster client secara berulang dalam arsitektur serverless/FaaS karena membebani overhead handshake Gossip. Gunakan instance singleton.
- [ ] **Monitoring Slot Skewness:** Monitor metrik kapasitas RAM dan jumlah key per node menggunakan *Prometheus Redis Exporter* untuk mencegah ketimpangan beban (*data skew*).

---

### 12. Hands-on Practice

Praktikum ini akan membangun arsitektur Redis Cluster (3 Master, 3 Replica) secara lokal menggunakan Docker Compose, memverifikasi failover, dan mengeksekusi online slot migration. Simpan seluruh artefak kerja di `hands-on/m02/`.

#### Langkah 1: Buat Konfigurasi Lingkungan (`hands-on/m02/docker-compose.yml`)
```yaml
version: '3.8'

services:
  redis-node-1:
    image: redis:7.2-alpine
    container_name: redis-node-1
    command: ["redis-server", "--port", "7001", "--cluster-enabled", "yes", "--cluster-config-file", "nodes.conf", "--cluster-node-timeout", "5000", "--appendonly", "yes"]
    network_mode: "host"

  redis-node-2:
    image: redis:7.2-alpine
    container_name: redis-node-2
    command: ["redis-server", "--port", "7002", "--cluster-enabled", "yes", "--cluster-config-file", "nodes.conf", "--cluster-node-timeout", "5000", "--appendonly", "yes"]
    network_mode: "host"

  redis-node-3:
    image: redis:7.2-alpine
    container_name: redis-node-3
    command: ["redis-server", "--port", "7003", "--cluster-enabled", "yes", "--cluster-config-file", "nodes.conf", "--cluster-node-timeout", "5000", "--appendonly", "yes"]
    network_mode: "host"

  redis-node-4:
    image: redis:7.2-alpine
    container_name: redis-node-4
    command: ["redis-server", "--port", "7004", "--cluster-enabled", "yes", "--cluster-config-file", "nodes.conf", "--cluster-node-timeout", "5000", "--appendonly", "yes"]
    network_mode: "host"

  redis-node-5:
    image: redis:7.2-alpine
    container_name: redis-node-5
    command: ["redis-server", "--port", "7005", "--cluster-enabled", "yes", "--cluster-config-file", "nodes.conf", "--cluster-node-timeout", "5000", "--appendonly", "yes"]
    network_mode: "host"

  redis-node-6:
    image: redis:7.2-alpine
    container_name: redis-node-6
    command: ["redis-server", "--port", "7006", "--cluster-enabled", "yes", "--cluster-config-file", "nodes.conf", "--cluster-node-timeout", "5000", "--appendonly", "yes"]
    network_mode: "host"
```

#### Langkah 2: Jalankan Node dan Bootstrap Klaster
Buka terminal dan navigasikan ke direktori hands-on:
```bash
cd hands-on/m02/
docker compose up -d

# Verifikasi semua kontainer berjalan
docker compose ps

# Lakukan inisialisasi Klaster (3 Master, 3 Replica => --cluster-replicas 1)
docker run --rm -it --network host redis:7.2-alpine redis-cli --cluster create \
  127.0.0.1:7001 127.0.0.1:7002 127.0.0.1:7003 \
  127.0.0.1:7004 127.0.0.1:7005 127.0.0.1:7006 \
  --cluster-replicas 1 --cluster-yes
```

#### Langkah 3: Validasi Status dan Distribusi Slot
```bash
redis-cli -p 7001 cluster info
redis-cli -p 7001 cluster nodes
```
Perhatikan pembagian hash slot pada 3 master node:
- Master 1: 0 - 5460
- Master 2: 5461 - 10922
- Master 3: 10923 - 16383

#### Langkah 4: Simulasi Failover Terkendali
Uji ketangguhan klaster dengan mematikan salah satu master:
```bash
# Hentikan master pada port 7001
docker stop redis-node-1

# Pantau transisi failover pada node lain
redis-cli -p 7002 cluster nodes
```
*Observasi:* Salah satu replica (misal node pada port 7004) akan dipromosikan menggantikan 7001 menjadi master.

Hidupkan kembali `redis-node-1`:
```bash
docker start redis-node-1
redis-cli -p 7002 cluster nodes
```
*Observasi:* `redis-node-1` kembali bergabung ke klaster bukan sebagai master, melainkan terdegradasi menjadi replica baru bagi node yang menggantikannya.

#### Langkah 5: Eksekusi Online Resharding
Pindahkan 500 slot dari node 7002 ke node 7003 tanpa mematikan klaster:
```bash
docker run --rm -it --network host redis:7.2-alpine redis-cli --cluster reshard 127.0.0.1:7002
# Masukkan target node ID (ID dari 7003)
# Masukkan jumlah slot: 500
# Masukkan source node ID (ID dari 7002) atau ketik 'done'
```

---

### 13. Exercise

#### Level Easy
Eksekusi pengujian manual routing data menggunakan CLI:
1. Hubungkan `redis-cli` tanpa flag `-c` ke node port `7001`.
2. Lakukan operasi `SET user:john "active"`.
3. Jika slot tidak berada di port 7001, catat respons `-MOVED` mentah yang dimunculkan.
4. Hubungkan kembali dengan menyertakan flag `-c` dan ulangi perintah. Analisis perbedaannya.

#### Level Medium
Buat sebuah script bash/python untuk menganalisis keberadaan kunci:
1. Masukkan 1.000 pasang key-value acak ke klaster.
2. Gunakan perintah `CLUSTER KEYSLOT <key>` untuk memprediksi lokasi hash slot.
3. Bandingkan output prediksi algoritma lokal CRC16 Anda dengan lokasi aktual node yang melayani slot tersebut via `CLUSTER NODES`.

#### Level Hard
Simulasikan skenario *Split-Brain*:
1. Jalankan script penulisan data secara berkesinambungan (continuous loop write) ke klaster.
2. Isolasikan satu master secara jaringan menggunakan `iptables` (blokir port client dan bus) dari master-master lainnya, namun biarkan master tersebut tetap dapat diakses oleh script klien selama 10 detik.
3. Pulihkan kembali jaringan.
4. Hitung jumlah *dropped writes* (data yang hilang) akibat replikasi asinkron dan promosi master baru.

---

### 14. Challenge

**Skenario Tantangan:**
Perusahaan Fintech Anda sedang merancang ulang sistem manajemen sesi multi-regional. Terdapat 2 kriteria wajib yang kontradiktif:
1. Skalabilitas horizontal tinggi (> 2 TB session data) menggunakan Redis Cluster.
2. Fitur *Atomic User Invalidation*: Ketika user mengubah password, seluruh token sesi aktif milik user tersebut (yang disimpan dalam struktur data terpisah seperti hash token, list device ID, dan counter sesi) wajib dibersihkan secara atomik dalam satu batch transaksi.

**Tugas Arsitektur:**
1. Rancang skema penamaan kunci (*Key Space Design*) yang memungkinkan eksekusi transaksi atomik via Lua Script tanpa memicu error `CROSSSLOT`.
2. Jelaskan dampak skema Anda terhadap *data distribution balance* jika terdapat satu akun pengguna enterprise yang memiliki 100.000 perangkat IoT (potensi *Hot Hash Slot*).
3. Buat skema mitigasi teknis untuk mencegah degradasi performa pada node yang menampung *Hot Hash Slot* tersebut tanpa melanggar batasan arsitektur Redis Cluster.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Berapa jumlah total Hash Slot pada sebuah Redis Cluster?
2. Algoritma checksum apa yang digunakan untuk menghitung pemetaan hash slot dari sebuah string key?
3. Apa perbedaan port komunikasi antara *Client traffic* dan *Cluster Bus*?
4. Format penulisan apa yang harus digunakan pada key agar dua key berbeda dijamin masuk ke dalam hash slot yang sama?
5. Mengapa Redis Cluster tidak memerlukan Apache ZooKeeper atau Consul untuk mengelola koordinasi status node?

#### Bagian 2: Intermediate (5 Pertanyaan)
1. Jelaskan perbedaan mendasar antara respons `-MOVED` dan `-ASK`! Pada kondisi apa masing-masing respons dikeluarkan?
2. Mengapa perintah `ASKING` harus dikirimkan oleh klien sebelum menjalankan query ke node yang ditunjuk oleh redirection `-ASK`?
3. Kapan sebuah node master mengubah status node lain dari `PFAIL` (*Possible Fail*) menjadi `FAIL`?
4. Apa fungsi dari parameter `configEpoch` pada setiap master node saat terjadi penanganan konflik topologi?
5. Mengapa replikasi Redis Cluster tidak menjamin sifat konsistensi *Strong Consistency* (Linearizability)?

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
1. **Skenario 1:** Tim DevOps Anda memperbarui deployment Redis Cluster di Kubernetes. Tiba-tiba seluruh log microservice backend mencatat error: `CLUSTERDOWN Hash slot not served`. Namun, saat dicek, 6 dari 6 container Redis berstatus *Running*. Apa akar penyebab internalnya dan parameter konfigurasi apa yang memicu kondisi fatal ini?
2. **Skenario 2:** Anda menambahkan 2 master node baru ke dalam klaster yang sudah ada untuk menambah kapasitas RAM. Namun, utilisasi memory dan CPU pada node baru tetap bernilai 0% meskipun aplikasi terus menulis data baru. Langkah operasional apa yang belum dieksekusi?
3. **Skenario 3:** Sebuah aplikasi backend Go mencatat peningkatan latency dari 2ms menjadi 1500ms secara berkala setiap 10 detik setelah klaster di-scale-out menjadi 200 node. Jaringan fisik aman, utilisasi CPU master rendah. Apa bottleneck arsitektural yang kemungkinan besar sedang terjadi pada level Gossip communication?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Bagian 1 (Basic)
1. $16.384$ ($2^{14}$) slot, bernomor dari 0 sampai 16383.
2. Algoritma CRC16 (CRC-16/CCITT standard).
3. Port client melayani RESP (default: 6379), sedangkan Cluster Bus port menggunakan protokol biner berada pada offset +10000 (default: 16379) untuk pertukaran status internal Gossip.
4. *Hash Tag*, yaitu menyertakan substring di dalam tanda kurung kurawal, misalnya `{user:123}:profile` dan `{user:123}:settings`.
5. Karena Redis Cluster mengimplementasikan sistem terdesentralisasi berbasis *Gossip Protocol* dan variasi konsensus bergaya Raft/Paxos secara *built-in* antar-master node.

#### Jawaban Bagian 2 (Intermediate)
1. `-MOVED` berarti kepemilikan slot sudah berpindah permanen ke node lain; klien harus memperbarui routing table lokalnya. `-ASK` berarti slot sedang dalam proses transisi/migrasi (*resharding*); klien hanya mengarahkan satu perintah berikutnya ke target tanpa mengubah routing table lokal.
2. Karena target node masih menandai slot tersebut dengan flag `IMPORTING`. Tanpa diawali perintah `ASKING`, target node akan menolak query dan mengembalikan error `-MOVED` kembali ke source node, menciptakan *infinite redirection loop*.
3. Ketika sebuah master mendeteksi status `PFAIL` pada master target dan berhasil menerima konfirmasi status `PFAIL` yang sama dari mayoritas master aktif lainnya dalam jangka waktu `cluster-node-timeout`.
4. `configEpoch` bertindak sebagai versi kepemilikan konfigurasi. Node dengan `configEpoch` lebih tinggi akan selalu memenangkan konflik klaim kepemilikan hash slot terhadap node yang memiliki `configEpoch` lebih rendah.
5. Replikasi data dari master ke replica berlangsung secara asinkron (*asynchronous replication*). Master mengirim konfirmasi `+OK` ke klien sebelum perubahan data ditulis/diterima oleh replica. Jika master mati mendadak sebelum replikasi tuntas, data yang belum direplikasi akan hilang saat failover terjadi.

#### Jawaban Bagian 3 (Skenario Kasus Produksi)
1. **Analisis Skenario 1:** Kemungkinan besar salah satu node master mati atau tidak sengaja melepaskan binding slotnya saat restart Pod, sehingga ada minimal 1 slot dari 16384 slot yang tidak terlayani (*uncovered slot*). Jika `cluster-require-full-coverage` disetel ke `yes` (atau default pada engine tertentu), klaster akan memblokir 100% operasi baca-tulis di semua slot yang sehat. **Solusi:** Ubah konfigurasi menjadi `cluster-require-full-coverage no` dan eksekusi perbaikan penugasan slot via `CLUSTER ADDSLOTS` atau `redis-cli --cluster fix`.
2. **Analisis Skenario 2:** Menambahkan node baru (`CLUSTER MEET` atau `redis-cli --cluster add-node`) hanya meregistrasikan node ke dalam topologi, namun node baru tersebut memiliki alokasi 0 hash slot. **Solusi:** Wajib mengeksekusi proses **Online Resharding** (`redis-cli --cluster reshard`) untuk memindahkan subset slot dari master-master eksisting ke master baru.
3. **Analisis Skenario 3:** Fenomena *Gossip Storm*. Pada klaster besar dengan 200 node, jika `cluster-node-timeout` disetel terlalu rendah, setiap node akan sangat agresif mengirim paket `PING`/`PONG` Gossip biner melalui Cluster Bus. Ini memicu saturasi socket buffer, packet drop, dan serialization delay pada main event-loop thread. **Solusi:** Naikkan `cluster-node-timeout` (misal ke 15-30 detik) dan pastikan parameter `cluster-port-traffic` terkontrol.

---

### 16. Summary

- **Skalabilitas & Partisi:** Redis Cluster memecah keterbatasan memori dan throughput vertikal dengan membagi data ke dalam $16.384$ hash slot linier menggunakan fungsi `CRC16(key) mod 16384`.
- **Topologi Peer-to-Peer:** Mengeliminasi ketergantungan pada *failover controller* eksternal via kanal *Cluster Bus* (Port 16379) yang ditenagai *Gossip Protocol* untuk failure detection (`PFAIL` -> `FAIL`) dan negosiasi kuorum pemilihan Master (`configEpoch`).
- **Orkestrasi Klien Terdistribusi:** *Smart Client* wajib memetakan slot secara lokal, menangani pengalihan dinamis `-MOVED` (permanen) vs `-ASK` (sementara saat migrasi), serta membatasi operasi multi-key pada boundary slot tunggal menggunakan *Hash Tags* (`{...}`).
- **Resiliensi Produksi:** Penerapan arsitektur Redis Cluster yang tangguh memerlukan alokasi Multi-AZ yang tepat antara Master dan Replicanya, antisipasi *Split-Brain* melalui `min-replicas-to-write`, serta mitigasi *Hot Hash Slots* melalui pemecahan *key space* deterministik.