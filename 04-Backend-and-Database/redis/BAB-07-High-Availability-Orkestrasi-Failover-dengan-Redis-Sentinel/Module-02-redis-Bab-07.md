# Modul 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (BAB-07: High Availability & Orkestrasi Failover dengan Redis Sentinel)

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal Redis Sentinel, mekanisme deteksi kegagalan (*Subjective Down* vs *Objective Down*), serta konsensus pemilihan Leader Sentinel berbasis varian Raft.
- Mendiagnosis dan memitigasi anomali *split-brain* serta kehilangan data (*data loss*) pada lingkungan terdistribusi menggunakan parameter `min-replicas-to-write` dan `min-replicas-max-lag`.
- Mengonfigurasi topologi Sentinel *production-ready* yang tahan terhadap partisi jaringan lintas *Availability Zone* (AZ) atau *Rack*.
- Mengimplementasikan integrasi aplikasi tingkat lanjut (*Sentinel-aware client*) dengan strategi *connection pooling*, *automatic reconnection*, dan pemisahan beban *read-write splitting*.
- Melakukan prosedur *Disaster Recovery* (DR), *planned failover* zero-downtime, serta *chaos testing* untuk memvalidasi toleransi kesalahan kluster.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Redis Core Engine**: Siklus replikasi asinkronus Redis (Replication ID, Replication Offset, PSYNC2) dari Bab 06.
- **Networking & Protokol**: TCP/IP stack, Socket lifecycle, Address Translation (NAT/Docker network bridging), dan protokol RESP (REdis Serialization Protocol).
- **Distributed Systems Basics**: Teorema CAP, Split-Brain problem, Consensus Algorithm (Raft/Paxos primitives), dan Quorum calculation.
- **Sistem Operasi**: Linux process management, Systemd service unit, `sysctl` kernel network tuning, dan packet manipulation menggunakan `iptables`/`nftables`.

---

## 3. Concept & Internal Architecture

Redis Sentinel bukanlah sebuah *data proxy*, melainkan sistem pengawas terdistribusi (*distributed monitoring and orchestration system*) yang berjalan sebagai proses independen dengan *binary* Redis standar namun beroperasi dalam mode khusus (`redis-sentinel` atau `redis-server --sentinel`).

```
+-------------------------------------------------------------+
|                      REDIS SENTINEL                         |
|                                                             |
|  +--------------------+  +-------------------------------+  |
|  | Periodic Timer     |  | Internal State Machine        |  |
|  | - 100ms: PING      |  | - SDOWN Flag Check            |  |
|  | - 10s: INFO        |  | - ODOWN Quorum Evaluation     |  |
|  | - 2s: Pub/Sub Beat |  | - Leader Election Epoch       |  |
|  +--------------------+  +-------------------------------+  |
|            |                             |                  |
|  +-------------------------------------------------------+  |
|  | Networking Engine (RESP Engine over TCP)              |  |
|  | - Command Connection (Per Target Node)                |  |
|  | - Pub/Sub Connection (Sentinel Auto-Discovery)        |  |
|  +-------------------------------------------------------+  |
+-------------------------------------------------------------+
```

### A. Mekanisme Komunikasi Antar-Sentinel (Auto-Discovery)
Sentinel tidak memerlukan konfigurasi alamat Sentinel lain secara manual. Sentinel memanfaatkan fitur **Pub/Sub** bawaan Redis Primary:
1. Setiap Sentinel membuka dua koneksi TCP ke Primary dan seluruh Replica:
   - **Command Connection**: Untuk mengirimkan perintah administratif (`PING`, `INFO`, `SENTINEL get-master-addr-by-name`).
   - **Pub/Sub Connection**: Meng-subscribe kanal khusus `__sentinel__:hello`.
2. Setiap 2 detik, Sentinel mempublikasikan pesan broadcast ke kanal `__sentinel__:hello` pada Primary dengan format:
   ```text
   <sentinel_ip>,<sentinel_port>,<sentinel_runid>,<current_epoch>,<master_name>,<master_ip>,<master_port>,<master_config_epoch>
   ```
3. Melalui pesan ini, Sentinel lain mendeteksi keberadaan (*auto-discover*) Sentinel baru dan memperbarui *state* internal mereka.

### B. State Machine Deteksi Kegagalan: SDOWN vs ODOWN
Sentinel membedakan kegagalan menjadi dua fase untuk menghindari tindakan agresif akibat *network jitter* lokal:

```
                  +--------------------------------+
                  | Node Normal (Responding PING)  |
                  +--------------------------------+
                                  |
                                  | PING timeout > down-after-milliseconds
                                  v
                  +--------------------------------+
                  |      SDOWN (Subjective Down)   |
                  |     (Local Sentinel Context)   |
                  +--------------------------------+
                                  |
                                  | SENTINEL is-master-down-by-addr
                                  | Quorum reached within timeout?
                                  v
                  +--------------------------------+
                  |      ODOWN (Objective Down)    |
                  |     (Consensus Cluster State)  |
                  +--------------------------------+
                                  |
                                  v
                  +--------------------------------+
                  |  Leader Election & Failover    |
                  +--------------------------------+
```

1. **SDOWN (Subjective Down)**:
   - Terjadi ketika target (Primary/Replica) tidak merespons `PING` dengan balasan yang valid (`+PONG`, `-LOADING`, atau `-MASTERDOWN`) dalam rentang waktu `sentinel down-after-milliseconds`.
   - Ini merupakan kesimpulan sepihak (*local opinion*) dari satu node Sentinel.

2. **ODOWN (Objective Down)**:
   - Hanya berlaku untuk **Primary**.
   - Ketika Sentinel menandai Primary sebagai `SDOWN`, ia mengirimkan perintah `SENTINEL is-master-down-by-addr <master-ip> <master-port> <current-epoch> <runid>` ke seluruh Sentinel lain.
   - Jika jumlah konfirmasi `SDOWN` dari Sentinel lain mencapai nilai **Quorum**, status dinaikkan menjadi `ODOWN`.

### C. Epoch, Leader Election, dan Raft-Variant Consensus
Setelah Primary berstatus `ODOWN`, failover tidak langsung dieksekusi secara serentak oleh semua Sentinel. Kluster harus memilih satu **Leader Sentinel** melalui konsensus berbasis Raft:
1. **Epoch Increment**: Sentinel yang pertama kali mendeteksi ODOWN menaikkan `current_epoch` sebanyak 1 dan meminta dukungan Sentinel lain untuk menjadi Leader (*Vote Request*).
2. **First-Come, First-Served**: Sentinel memberikan suaranya (*voted_runid*) kepada kandidat pertama yang memintanya pada Epoch tersebut. Satu Sentinel hanya dapat memberikan satu suara per Epoch.
3. **Syarat Kemenangan**: Sebuah kandidat Sentinel dinyatakan sebagai Leader jika memperoleh suara:
   $$\text{Suara} \ge \text{Quorum} \quad \text{DAN} \quad \text{Suara} > \frac{N_{\text{total}}}{2} \ (\text{Majority})$$
   *Catatan Arsitektural*: Quorum saja **tidak cukup** untuk memenangkan pemilihan Leader jika nilai Quorum lebih kecil dari batas mayoritas kluster Sentinel ($N_{\text{total}}/2 + 1$).

### D. TILT Mode
Jika jam sistem (*system clock*) melompat secara tiba-tiba atau proses Sentinel terhenti (*freeze*) akibat starvation CPU atau *paging* memori lebih dari 2 detik, Sentinel memasuki **TILT Mode**:
- Dalam kondisi ini, penilaian waktu Sentinel dianggap tidak tepercaya.
- Semua aksi aktif (termasuk voting dan inisiasi failover) **dibekukan total**.
- Sentinel hanya memonitor secara pasif selama 30 detik hingga waktu kembali stabil sebelum keluar dari TILT mode.

---

## 4. Why & What

| Dimensi | Tanpa Redis Sentinel | Dengan Redis Sentinel |
| :--- | :--- | :--- |
| **Recovery Point Objective (RPO)** | Tinggi (Bisa kehilangan data menit-jam jika manual) | Rendah (Hanya data *in-flight replication lag*) |
| **Recovery Time Objective (RTO)** | Menit hingga Jam (Membutuhkan intervensi On-Call SRE) | Detik (Umumnya 5 - 15 detik secara otomatis) |
| **Discovery Alamat Master** | Hardcoded IP / Manual DNS update | Dynamic Service Discovery via Sentinel Client API |
| **Manajemen State Replikasi** | Manual `REPLICAOF NO ONE` dan reconfiguration | Terorkestrasi otomatis dengan Epoch versioning |
| **Integritas Kluster** | Rawan human error saat restrukturisasi | Konsensus terdistribusi mencegah reassignment ganda |

---

## 5. How (Workflow Orkestrasi Failover)

Berikut alur eksekusi saat Primary mengalami *unclean shutdown* atau kegagalan fatal:

```
[ Primary Crash ]
       │
       ▼
1. Sentinel mendeteksi failure via PING (SDOWN)
       │
       ▼
2. Sentinel broadcast is-master-down-by-addr ke Sentinel peers
       │
       ▼
3. Quorum tercapai -> State berubah menjadi ODOWN
       │
       ▼
4. Pemilihan Leader Sentinel (Raft Consensus, Majority Requirement)
       │
       ▼
5. Leader memilih Replica terbaik berdasarkan:
   a. replica-priority terkecil (0 = jangan pernah dipromosikan)
   b. replication offset terbesar (data paling mutakhir)
   c. RunID terkecil secara leksikografis (jika offset identik)
       │
       ▼
6. Leader mengirim: REPLICAOF NO ONE ke Replica terpilih -> Menjadi Primary baru
       │
       ▼
7. Leader mengirim: REPLICAOF <new_ip> <new_port> ke Replica lainnya
   (dibatasi oleh sentinel parallel-syncs)
       │
       ▼
8. Leader memperbarui internal config epoch & broadcast via Pub/Sub
       │
       ▼
9. Old Primary down -> Ketika hidup kembali, otomatis di-demote menjadi Replica
```

---

## 6. Analogi & Diagram Arsitektur

### Analogi
Bayangkan sebuah dewan juri (Sentinel Kluster) yang mengawasi seorang koki utama (*Primary Server*). Jika seorang juri melihat sang koki jatuh pingsan (*SDOWN*), ia tidak langsung mengangkat sous-chef (*Replica*). Ia bertanya kepada juri lainnya. Ketika mayoritas juri setuju koki utama pingsan (*ODOWN*), mereka melakukan voting memilih satu kepala dewan (*Leader Sentinel*). Kepala dewan tersebut kemudian memilih sous-chef yang kemampuannya paling mendekati koki utama (*highest replication offset*), memberikannya topi koki utama, dan memberi tahu pelayan restoran (*Client Applications*) ke mana pesanan baru harus dikirim.

### Diagram Partisi Jaringan & Split-Brain Mitigation

Tanpa mitigasi, pemisahan jaringan (*network partition*) dapat menciptakan dua Primary aktif yang menerima *write*, berujung pada kerusakan data permanen saat partisi pulih (*split-brain*).

```
          PARTISI NETWORK A                     PARTISI NETWORK B
      (Minority - Isolated)                 (Majority - Functional)
 +-----------------------------+       +-----------------------------+
 | +---------+     +---------+ |       | +---------+     +---------+ |
 | | Master  |     |Sentinel1| |       | |Replica 1|     |Sentinel2| |
 | | (Old)   |     +---------+ |       | +---------+     +---------+ |
 | +---------+                 |       |      |                      |
 |      |                      |  ===  |      | Promoted to Primary  |
 |   Isolated                  |  ===  |      v                      |
 |   Writes blocked via:       |  ===  | +---------+     +---------+ |
 |   min-replicas-to-write     |       | |Replica 2|     |Sentinel3| |
 |                             |       | +---------+     +---------+ |
 +-----------------------------+       +-----------------------------+
```

Untuk membatalkan penulisan data pada isolat minoritas:
```text
min-replicas-to-write 1
min-replicas-max-lag 10
```
Jika Master terisolasi dan tidak menerima *heartbeat acknowledge* dari minimal 1 replica selama 10 detik, Master otomatis menolak seluruh perintah penulisan (*read-only state*), mengeliminasi resiko data divergence.

---

## 7. Configuration & Implementation Pattern

### A. Konfigurasi Redis Sentinel Standar Produksi

File: `/etc/redis/sentinel.conf`
```conf
# Port default untuk Sentinel
port 26379

# Direktori kerja aman
dir /var/lib/redis/sentinel

# Monitoring instance: sentinel monitor <master-name> <ip> <port> <quorum>
sentinel monitor mymaster 10.0.1.10 6379 2

# Waktu deteksi SDOWN (3 detik untuk deteksi cepat di enterprise LAN)
sentinel down-after-milliseconds mymaster 3000

# Timeout seluruh failover workflow (18 detik)
sentinel failover-timeout mymaster 18000

# Jumlah replica yang re-sync secara paralel ke master baru (1 menjaga saturasi network)
sentinel parallel-syncs mymaster 1

# Otentikasi Primary & Replica
sentinel auth-pass mymaster SuperSecureRedisPasswd123!
sentinel sentinel-user redis-sentinel-operator
sentinel sentinel-pass SentinelInterCommPasswd456!

# Network Address Translation / Container Binding
# Wajib jika berjalan di Kubernetes, Docker bridge, atau AWS Private Subnet ber-NAT
sentinel announce-ip 10.0.1.100
sentinel announce-port 26379

# Proteksi Eksekusi Skrip Failover
protected-mode yes
```

### B. Konfigurasi Redis Primary Node

File: `/etc/redis/redis.conf`
```conf
bind 0.0.0.0
port 6379
protected-mode yes
requirepass SuperSecureRedisPasswd123!
masterauth SuperSecureRedisPasswd123!

# Mitigasi Split-Brain & Asynchronous Loss Protection
min-replicas-to-write 1
min-replicas-max-lag 10

# Memory management
maxmemory 16gb
maxmemory-policy allkeys-lru

# Persistence Engine
appendonly yes
appendfsync everysec
```

### C. Implementasi Sentinel-Aware Client (Go Idiomatik)

Implementasi menggunakan engine `go-redis/v9` yang menangani koneksi transparan ke Master dinamis melalui polling Sentinel.

```go
package main

import (
	"context"
	"errors"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

type RedisSentinelPool struct {
	client *redis.Client
}

func NewRedisSentinelPool() (*RedisSentinelPool, error) {
	// Inisialisasi FailoverClient (Sentinel-aware)
	rdb := redis.NewFailoverClient(&redis.FailoverOptions{
		MasterName: "mymaster",
		SentinelAddrs: []string{
			"10.0.1.100:26379",
			"10.0.1.101:26379",
			"10.0.1.102:26379",
		},
		SentinelPassword: "SentinelInterCommPasswd456!",
		Password:         "SuperSecureRedisPasswd123!",
		DB:               0,

		// Connection Pool Lifecycle Engine
		PoolSize:        100,
		MinIdleConns:    20,
		MaxIdleConns:    50,
		ConnMaxIdleTime: 5 * time.Minute,
		ConnMaxLifetime: 1 * time.Hour,

		// Timeout Tolerances
		DialTimeout:  2 * time.Second,
		ReadTimeout:  1 * time.Second,
		WriteTimeout: 1 * time.Second,

		// Circuit Breaker & Retry Strategy
		MaxRetries:      3,
		MinRetryBackoff: 100 * time.Millisecond,
		MaxRetryBackoff: 500 * time.Millisecond,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, err
	}

	return &RedisSentinelPool{client: rdb}, nil
}

func (r *RedisSentinelPool) ExecuteTransactionWithRetry(ctx context.Context, key string, val string) error {
	// Menjalankan operasi dengan mitigasi failover-in-progress (READONLY error handling)
	maxRetries := 5
	for i := 0; i < maxRetries; i++ {
		err := r.client.Set(ctx, key, val, 10*time.Minute).Err()
		if err == nil {
			return nil
		}

		// Jika failover sedang mengeksekusi transisi, Master lama melempar error READONLY
		if errors.Is(err, redis.ReadOnlyError) || err.Error() == "READONLY You can't write against a read only replica." {
			log.Printf("[WARN] Write dicegah: Kluster sedang failover. Retry ke-%d...", i+1)
			time.Sleep(time.Duration(200*(i+1)) * time.Millisecond)
			continue
		}

		return err
	}
	return errors.New("gagal mengeksekusi operasi penulisan: batas waktu failover terlampaui")
}

func main() {
	pool, err := NewRedisSentinelPool()
	if err != nil {
		log.Fatalf("Fatal: Gagal inisialisasi Redis Sentinel client: %v", err)
	}
	defer pool.client.Close()

	log.Println("Koneksi Redis Sentinel tersambung secara dinamis.")
}
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Skenario Kasus: Payment Processing Platform (50,000 TPS)
Sebuah *core gateway fintech* memproses lonjakan transaksi selama program *Flash Sale*. 

**Topologi Awal:**
- 1 Primary, 1 Replica di AWS Region `ap-southeast-1a`.
- 1 Sentinel di `ap-southeast-1a`, 1 Sentinel di `ap-southeast-1b`.

**Insiden Kegagalan (Post-Mortem Analysis):**
1. **Pemicu**: `ap-southeast-1a` mengalami penurunan jaringan lintas-AZ (*inter-AZ packet loss* 40%).
2. **Kondisi Failover Gagal**: Sentinel pada `ap-southeast-1b` mendeteksi Primary sebagai `SDOWN`. Namun, quorum yang didefinisikan adalah `2`. Total Sentinel yang hidup di sisi non-partisi hanya 1 (tidak memenuhi kuorum pemilihan Leader). Failover **macet permanen**.
3. **Split-Brain**: Aplikasi pada AZ `ap-southeast-1a` tetap mengirimkan *write* ke Primary lokal. Ketika koneksi dipulihkan, Sentinel di AZ `ap-southeast-1b` terlambat mengenali konsensus, melakukan promosi baru dan menurunkan Primary lama. Primary lama dipaksa melakukan `PSYNC` penuh, menyebabkan **seluruh transaksi pembayaran bernilai Rp 4,2 Miliar selama partisi 8 menit terhapus permanen (*data truncation*)**.

**Arsitektur Remedi Produksi:**
```
                     +---------------------------------------+
                     |        Cloud Load Balancer / App      |
                     +---------------------------------------+
                        |                 |                |
           AZ 1a        |        AZ 1b    |       AZ 1c    |
      +---------------+ |   +---------------+ |   +---------------+
      |  Sentinel 1   | |   |  Sentinel 2   | |   |  Sentinel 3   |
      +---------------+ |   +---------------+ |   +---------------+
      | Redis Primary | |   | Redis Replica | |   |  (Witness /   |
      |               |-+-->|               | |   |   Sentinel    |
      +---------------+     +---------------+ |   |   Only Node)  |
                                              |   +---------------+
```
1. **Distribusi 3-AZ**:
   - Menempatkan Sentinel ke-3 pada *Availability Zone* independen ke-3 (`ap-southeast-1c`). Total Sentinel = 3, Quorum = 2, Majority = 2.
2. **Penguncian Degradasi Data**:
   Mengaktifkan `min-replicas-to-write 1` dan `min-replicas-max-lag 3` pada Redis engine. Begitu Master terisolasi dari replica-nya lebih dari 3 detik, master menolak mutasi state dan mengembalikan status error ke client, mencegah data divergensi.

---

## 9. Trade-offs Architecture Matrix

| Komponen / Konfigurasi | Keuntungan (*Pros*) | Konsekuensi Negatif (*Cons*) | Rekomendasi Kasus |
| :--- | :--- | :--- | :--- |
| **Sentinel Architecture vs Redis Cluster** | Mendukung ACID transaksional multi-key (`WATCH`, `MULTI`/`EXEC`), arsitektur sederhana, overhead memory rendah. | Kapasitas penulisan terikat pada 1 *single node* Master (tidak ada horizontal sharding otomatis). | State store hingga 64GB RAM, token bucket, session, locks. |
| **`parallel-syncs 1`** | Utilisasi bandwidth jaringan rendah, Master baru tidak terbebani I/O *forking* serentak saat failover. | RTO kluster menjadi lambat jika memiliki 5+ replica (mereka antre untuk sync satu per satu). | Jaringan produksi dengan kapasitas I/O terbatas. |
| **`parallel-syncs N` (High Value)** | Waktu pemulihan kluster secara menyeluruh (*total convergence*) sangat cepat. | Master baru dapat mengalami lonjakan CPU/Network I/O drastis (*fork spike* & bandwidth exhaustion). | Lingkungan bare-metal dengan koneksi 10Gbps+ LAN. |
| **`min-replicas-to-write` Aktif** | Mencegah *split-brain data truncation* hampir hingga 0%. | Primary berubah menjadi *read-only* jika replikasi down, menolak seluruh penulisan (*Availability dropped*). | Sistem finansial, *ledgering*, inventory checkout (mengutamakan C daripada A di Teorema CAP). |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Sentinel Mengekspos Alamat IP Privat `127.0.0.1` ke Klien Eksternal
- **Gejala**: Sentinel bekerja normal, failover berjalan, tetapi aplikasi microservices melempar error `Dial tcp 127.0.0.1:6379: connect: connection refused`.
- **Akar Masalah**: Sentinel mendeteksi Primary menggunakan IP yang didaftarkan secara lokal. Pada Docker/K8s/NAT, Sentinel mengambil alamat internal container.
- **Solusi**: Definisikan konfigurasi wajib berikut di setiap `redis-sentinel.conf`:
  ```conf
  sentinel announce-ip <IP_ADDRESS_NODE_FISIK_ATAU_HOST>
  sentinel announce-port <PORT_FORWARD_HOST>
  ```

### Mistake 2: Formula Quorum yang Salah Paham Mengenai Majority
- **Gejala**: Dibuat 2 node Sentinel dengan konfigurasi `sentinel monitor mymaster IP PORT 1`. Ketika 1 Sentinel mati, failover tetap tidak berjalan.
- **Akar Masalah**: Quorum = 1 terpenuhi, namun Sentinel membutuhkan **Majority** ($\lfloor 2/2 \rfloor + 1 = 2$) dari total node yang terkonfigurasi untuk mengesahkan Leader Sentinel. Satu Sentinel tidak bisa membentuk mayoritas dari kluster dua node.
- **Aturan Baku**: Jumlah Sentinel **harus selalu bernilai ganjil**: minimal 3, idealnya 5 untuk multi-region setup.

### Prosedur Diagnostik & Triage Cepat
```bash
# 1. Periksa status Master dari sudut pandang Sentinel
redis-cli -p 26379 SENTINEL master mymaster

# 2. Cek integritas koneksi antar Sentinel
redis-cli -p 26379 SENTINEL sentinels mymaster

# 3. Paksa failover manual untuk testing operasional tanpa mematikan proses (Zero Loss)
redis-cli -p 26379 SENTINEL FAILOVER mymaster

# 4. Debug stream Pub/Sub event engine Sentinel secara live
redis-cli -p 26379
SUBSCRIBE +sdown -sdown +odown -odown +switch-master +tilt -tilt
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Ganjil & Terisolasi**: Kluster Sentinel memiliki minimal 3 node yang ditempatkan pada server/rack/AZ yang terpisah secara fisik.
- [ ] **Sentinel != Data Processing**: Jangan pernah menjalankan instance Sentinel pada server yang sama dengan Redis Master jika tidak memiliki alokasi resource vCPU yang diproteksi (*cgroups/cpuset*).
- [ ] **Synchronized Time**: Seluruh node menyinkronkan waktu sistem via `chrony` atau NTP. Drift > 2 detik memicu mode *TILT* yang merusak ketersediaan kluster.
- [ ] **Down-after-milliseconds Tuning**: Jangan diset terlalu agresif (< 1000ms). Rekomendasi produksi: `2000` - `5000` ms untuk mencegah flapping failover akibat network hiccup berkala.
- [ ] **Proteksi Otentikasi Simetris**: Password `requirepass` pada Primary dan Replica disamakan persis dengan konfigurasi `masterauth` dan `sentinel auth-pass`.
- [ ] **Static Hostnames**: Hindari penggunaan DNS name murni di `sentinel monitor` pada Redis versi lama (< 6.2); gunakan IP address statis atau konfigurasikan `sentinel resolve-hostnames yes` (Redis 6.2+).
- [ ] **Client Health Check**: Aplikasi client mengimplementasikan event listener pada kanal Sentinel Pub/Sub `+switch-master` untuk mengeksekusi refresh pool instan tanpa menunggu kegagalan query TCP.

---

## 12. Hands-on Practice: Simulasi Orkestrasi Failover & Chaos Injection

Praktikum ini mensimulasikan lingkungan terisolasi menggunakan Docker Compose: 1 Primary, 2 Replica, dan 3 Sentinel. Seluruh file disimpan di direktori `hands-on/m02/`.

### Struktur Direktori
```text
hands-on/m02/
├── docker-compose.yml
├── redis-primary.conf
├── redis-replica.conf
└── sentinel.conf
```

### File: `hands-on/m02/redis-primary.conf`
```conf
port 6379
protected-mode no
requirepass SecretPass123
masterauth SecretPass123
appendonly yes
min-replicas-to-write 1
min-replicas-max-lag 10
```

### File: `hands-on/m02/redis-replica.conf`
```conf
port 6379
protected-mode no
requirepass SecretPass123
masterauth SecretPass123
replicaof redis-primary 6379
appendonly yes
```

### File: `hands-on/m02/sentinel.conf`
```conf
port 26379
protected-mode no
sentinel monitor mymaster redis-primary 6379 2
sentinel down-after-milliseconds mymaster 3000
sentinel failover-timeout mymaster 10000
sentinel parallel-syncs mymaster 1
sentinel auth-pass mymaster SecretPass123
```

### File: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'

networks:
  sentinel-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16

services:
  redis-primary:
    image: redis:7.2-alpine
    container_name: redis-primary
    command: ["redis-server", "/etc/redis/redis.conf"]
    volumes:
      - ./redis-primary.conf:/etc/redis/redis.conf
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.10

  redis-replica-1:
    image: redis:7.2-alpine
    container_name: redis-replica-1
    command: ["redis-server", "/etc/redis/redis.conf"]
    volumes:
      - ./redis-replica.conf:/etc/redis/redis.conf
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.11
    depends_on:
      - redis-primary

  redis-replica-2:
    image: redis:7.2-alpine
    container_name: redis-replica-2
    command: ["redis-server", "/etc/redis/redis.conf"]
    volumes:
      - ./redis-replica.conf:/etc/redis/redis.conf
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.12
    depends_on:
      - redis-primary

  sentinel-1:
    image: redis:7.2-alpine
    container_name: sentinel-1
    command: ["redis-sentinel", "/etc/redis/sentinel.conf"]
    volumes:
      - ./sentinel.conf:/etc/redis/sentinel.conf
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.21
    depends_on:
      - redis-primary

  sentinel-2:
    image: redis:7.2-alpine
    container_name: sentinel-2
    command: ["redis-sentinel", "/etc/redis/sentinel.conf"]
    volumes:
      - ./sentinel.conf:/etc/redis/sentinel.conf
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.22
    depends_on:
      - redis-primary

  sentinel-3:
    image: redis:7.2-alpine
    container_name: sentinel-3
    command: ["redis-sentinel", "/etc/redis/sentinel.conf"]
    volumes:
      - ./sentinel.conf:/etc/redis/sentinel.conf
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.23
    depends_on:
      - redis-primary
```

### Langkah Instruksi Chaos Testing:

1. **Jalankan Seluruh Kluster**:
   ```bash
   cd hands-on/m02/
   docker compose up -d
   ```

2. **Validasi Kondisi Operasional Master Awal**:
   ```bash
   docker exec -it sentinel-1 redis-cli -p 26379 sentinel master mymaster
   # Perhatikan fields: "ip" bernilai 172.28.0.10, "num-slaves" bernilai 2, "flags" bernilai "master"
   ```

3. **Injeksi Kegagalan (Simulasi Crash Master)**:
   Hentikan proses pada Master tanpa proses cleanup graceful:
   ```bash
   docker pause redis-primary
   ```

4. **Monitor Realtime Transisi Failover melalui Log Sentinel**:
   ```bash
   docker logs -f sentinel-1
   ```
   *Amati urutan output:*
   - `+sdown master mymaster 172.28.0.10 6379`
   - `+odown master mymaster 172.28.0.10 6379 #quorum 2/2`
   - `+vote-for-leader ...`
   - `+failover-state-select-slave ...`
   - `+promoted-slave ...`
   - `+switch-master mymaster 172.28.0.10 6379 <IP_REPLICA_BARU> 6379`

5. **Pemulihan Node Lama (Recovery Validation)**:
   ```bash
   docker unpause redis-primary
   # Tunggu 5 detik, lalu cek info node lama:
   docker exec -it redis-primary redis-cli -a SecretPass123 INFO replication
   # Hasil: Node lama otomatis diturunkan menjadi "role:slave" dari Master yang baru
   ```

---

## 13. Exercises

### Level Easy
Verifikasi kluster Sentinel Anda melalui CLI: Ekstrak alamat IP dan port Master yang sedang aktif saat ini hanya dengan menggunakan satu perintah CLI Sentinel dari terminal host Anda.
- *Hint*: Gunakan sub-command `SENTINEL get-master-addr-by-name`.

### Level Medium
Simulasikan degradasi *network flapping*. Konfigurasikan aturan drop traffic menggunakan `iptables` pada container `redis-primary` untuk paket ICMP dan TCP tertentu ke Sentinel 2 saja selama 2 detik, lalu lepaskan kembali. Analisis apakah failover terpicu secara salah (*false-positive*). Jelaskan parameter mana yang mencegah hal tersebut.

### Level Hard
Buat script automasi (Bash / Python) yang mendengarkan event stream Pub/Sub Sentinel. Jika terdeteksi log event `+switch-master`, script harus mengekstrak Master IP baru dan melakukan pembaruan file konfigurasi reverse proxy (seperti HAProxy atau NGINX TCP stream) serta me-reload konfigurasi tersebut tanpa adanya *dropped connection*.

---

## 14. Challenges

**Studi Kasus: Multi-Region Asymmetric Latency Disaster.**

Sebuah platform memiliki arsitektur 3 Region:
- **Region 1 (Jakarta)**: Master Data Store + 1 Sentinel
- **Region 2 (Singapura)**: Replica 1 + 1 Sentinel
- **Region 3 (Tokyo)**: Replica 2 + 1 Sentinel

Kabel komunikasi bawah laut antara Jakarta dan Singapura terputus, namun Jakarta ke Tokyo serta Singapura ke Tokyo tetap terhubung dengan latensi tinggi (Jakarta-Tokyo: 90ms, Singapura-Tokyo: 75ms).

**Tantangan Arsitektur Anda:**
1. Rancang analisis kegagalan: Berapa Quorum yang harus dikonfigurasi? Mengapa penempatan ini rentan memicu pemilihan Leader Sentinel ganda (*split vote/flapping*)?
2. Bagaimana cara mengonfigurasi `sentinel down-after-milliseconds` dan `sentinel failover-timeout` untuk menangani disparitas latensi regional ini agar sistem tidak melakukan failover berkali-kali (*thrashing*)?
3. Modifikasi parameter replikasi pada Primary Jakarta agar jika Master Jakarta terisolasi dari Singapura, ia berhenti menerima *write traffic* guna mencegah akumulasi offset yang tidak dapat digabungkan kembali. Tuliskan blok konfigurasinya secara presisi.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda)
1. Perintah mana yang digunakan Sentinel untuk mendeteksi keberadaan Sentinel lain secara otomatis tanpa daftar IP statis?
   - A. `SENTINEL DISCOVER`
   - B. Pub/Sub pada kanal `__sentinel__:hello`
   - C. Broadcast UDP pada port 26379
   - D. PING sweep pada subnet yang sama

2. Apa perbedaan fundamental antara status `SDOWN` dan `ODOWN`?
   - A. `SDOWN` hanya untuk Sentinel, `ODOWN` untuk Redis Server.
   - B. `SDOWN` bersifat kesimpulan lokal 1 Sentinel; `ODOWN` memerlukan konsensus sejumlah Quorum.
   - C. `SDOWN` memicu failover seketika; `ODOWN` menghentikan write traffic.
   - D. `SDOWN` berarti node mati total; `ODOWN` berarti node mengalami disk overload.

3. Berapakah jumlah minimum proses Sentinel yang direkomendasikan untuk arsitektur *fault-tolerant* di lingkungan produksi?
   - A. 1
   - B. 2
   - C. 3
   - D. 4

4. Ketika proses Sentinel berada dalam "TILT Mode", aksi apa yang diambil oleh Sentinel terhadap failover?
   - A. Mempercepat failover dalam 500ms
   - B. Mematikan seluruh Replica secara otomatis
   - C. Memblokir sementara seluruh voting dan inisiasi failover
   - D. Menghapus file `sentinel.conf`

5. Sub-command mana yang digunakan oleh aplikasi client untuk mengambil alamat Master saat inisialisasi koneksi?
   - A. `SENTINEL master-ip mymaster`
   - B. `SENTINEL get-master-addr-by-name <master-name>`
   - C. `REDIS get-current-master`
   - D. `SENTINEL show-active-endpoint`

### Bagian B: Intermediate (Pilihan Ganda)
6. Sebuah kluster memiliki 5 node Sentinel dengan Quorum = 2. Jika 3 Sentinel mengalami crash akibat mati listrik di sebuah rack, apakah failover otomatis dapat terlaksana jika Master kemudian mati?
   - A. Ya, karena Quorum (2) masih terpenuhi oleh 2 Sentinel yang hidup.
   - B. Tidak, karena pemilihan Leader Sentinel mensyaratkan mayoritas dari total node ($\lfloor 5/2 \rfloor + 1 = 3$).
   - C. Ya, karena Quorum lebih tinggi dari jumlah Replica yang tersisa.
   - D. Tidak, karena Sentinel membutuhkan 100% konsensus untuk mengeksekusi failover.

7. Jika terdapat 2 Replica yang sama-sama sehat dan memenuhi syarat saat Master fail, kriteria apa yang menjadi prioritas utama Sentinel dalam menentukan Replica mana yang dipromosikan?
   - A. Process ID (PID) terkecil
   - B. Uptime koneksi terlama
   - C. `replica-priority` terendah (selama bukan 0)
   - D. Replication Offset terkecil

8. Apa fungsi langsung dari konfigurasi `sentinel parallel-syncs mymaster 1`?
   - A. Hanya mengizinkan 1 Sentinel yang memonitor Primary.
   - B. Membatasi agar hanya 1 Replica yang melakukan sinkronisasi ulang secara simultan ke Master baru pasca-failover.
   - C. Membatasi penulisan paralel dari client ke Master baru maksimal 1 koneksi.
   - D. Menjamin replikasi sinkronus penuh 1-ke-1.

9. Apa yang terjadi pada node Master lama yang mati setelah bangkit kembali pada kluster yang telah berhasil failover?
   - A. Master lama menolak bergabung dan mematikan dirinya (*self-terminate*).
   - B. Master lama langsung mengambil kembali status Master (*failback* paksa).
   - C. Leader Sentinel mendeteksi Master lama dan mengirim perintah `REPLICAOF` agar ia menjadi Replica dari Master baru.
   - D. Kluster masuk ke status Split-Brain permanen.

10. Parameter Redis Server apa yang paling efektif untuk memitigasi hilangnya data pada Master yang terisolasi dari jaringan (*isolated master*) saat partisi terjadi?
    - A. `appendfsync always`
    - B. `sentinel failover-timeout 0`
    - C. `min-replicas-to-write` digabungkan dengan `min-replicas-max-lag`
    - D. `save 60 1000`

### Bagian C: Skenario Kasus Produksi
11. **Kasus 1**: Tim DevOps Anda menjalankan kluster Redis Sentinel di Kubernetes menggunakan StatefulSet default. Saat node worker Kubernetes mengalami restart, pod Sentinel mendapatkan IP Pod baru. Sentinel cluster mendadak kehilangan jejak satu sama lain dan logging dipenuhi oleh pesan error timeout koneksi IP lama. Analisis penyebabnya dan berikan solusi konfigurasi Sentinel yang tepat!
12. **Kasus 2**: Kluster Redis e-commerce dengan konfigurasi 1 Master dan 2 Replica mengalami failover otomatis. Log menunjukkan Sentinel Leader sukses terpilih, tetapi failover dibatalkan dengan log error: `Failover state select-slave: No suitable replica found to promote`. Selidiki seluruh parameter kemungkinan yang menyebabkan seluruh Replica dinilai *unfit* (tidak layak dipromosikan)!
13. **Kasus 3**: Audit performa menemukan bahwa setiap kali Sentinel failover terjadi, aplikasi backend berbasis Java mengalami lonjakan *connection pool exhausted* selama 45 detik, padahal konfigurasi `failover-timeout` Sentinel diset pada 10 detik. Identifikasi lapisan arsitektur apa di level networking atau client configuration yang berpotensi menyebabkan disparitas durasi tersebut!

---

### Kunci Jawaban & Rubrik Evaluasi

#### Bagian A & B
1. **B** - Pub/Sub `__sentinel__:hello` adalah mekanisme auto-discovery internal antar Sentinel.
2. **B** - SDOWN adalah opini subjektif satu Sentinel; ODOWN adalah konsensus berbasis quorum.
3. **C** - Minimal 3 node untuk mempertahankan mayoritas ($\lfloor 3/2 \rfloor + 1 = 2$) jika 1 node crash.
4. **C** - Mode TILT mematikan seluruh aksi aktif failover untuk mencegah salah eksekusi akibat anomali jam sistem.
5. **B** - Command resmi RESP untuk Sentinel discovery adalah `SENTINEL get-master-addr-by-name`.
6. **B** - Leader election berbasis Raft mewajibkan quorum **dan** mayoritas dari total node yang terkonfigurasi. 2 suara dari 5 Sentinel tidak mencapai mayoritas (3).
7. **C** - `replica-priority` terendah dievaluasi pertama kali, baru kemudian replication offset tertinggi.
8. **B** - Membatasi jumlah replica yang melakukan re-sync serentak guna melindungi resource CPU/network Master baru.
9. **C** - Re-konfigurasi otomatis via Leader Sentinel mendemoted Master lama menjadi Replica.
10. **C** - `min-replicas-to-write` memaksa Master menolak operasi tulis jika replikasi gagal terkonfirmasi.

#### Bagian C (Pedoman Penilaian Kasus Produksi)
11. **Analisis Kasus 1**:
    - *Akar Masalah*: Konfigurasi `sentinel.conf` secara dinamis menulis ulang *discovered peers* menggunakan IP runtime container. Di Kubernetes, IP Pod bersifat ephemeral. Ketika Pod Sentinel restart, IP lama masih tersimpan di file config Sentinel lainnya.
    - *Solusi*: Gunakan StatefulSet Headless Service dengan DNS FQDN stabil, dan aktifkan pada Sentinel versi >= 6.2: `sentinel resolve-hostnames yes` serta `sentinel announce-hostnames yes`.
12. **Analisis Kasus 2**:
    Replica dinyatakan tidak valid dipromosikan (*unfit*) oleh Leader jika memenuhi salah satu dari kondisi ini:
    - Nilai `replica-priority` di `redis.conf` diset ke `0` (secara eksplisit melarang node menjadi master).
    - Status koneksi replica ke master lama terputus lebih lama dari `(node-timeout * 10)` milidetik, dianggap datanya terlalu usang (*stale*).
    - Status flag replica berada dalam kondisi `DISCONNECTED` atau `SDOWN`.
13. **Analisis Kasus 3**:
    Disparitas durasi (10 detik vs 45 detik) disebabkan oleh:
    - Driver client Java (misal: Lettuce/Jedis lama) tidak melakukan polling DNS/Sentinel Pub/Sub, melainkan mengandalkan kegagalan TCP socket timeout default Linux (TCP retransmission timeout = 15-30 detik) saat Master lama *unreachable* (blackhole IP).
    - Solusi: Aktifkan TCP KeepAlive level kernel lebih agresif (`net.ipv4.tcp_retries2 = 5`), setel Socket Connect Timeout pada connection pool client ke angka 1-2 detik, dan pastikan client meng-subscribe kanal Pub/Sub `+switch-master` untuk trigger invalidate pool instan.

---

## 16. Summary

Redis Sentinel merupakan solusi High Availability level enterprise yang mengorkestrasi *monitoring*, *notification*, *automatic failover*, dan *service discovery* untuk Redis tanpa memerlukan proxy terpusat. 

Keandalan sistem Sentinel tidak hanya bertumpu pada konfigurasi daemon Sentinel semata, melainkan pada sinergi tiga komponen krusial:
1. **Konsensus yang Benar**: Alokasi jumlah Sentinel ganjil (minimal 3) dengan batas Quorum dan Majority yang dihitung secara matematis.
2. **Proteksi Integritas Data**: Penerapan `min-replicas-to-write` dan `min-replicas-max-lag` pada engine Redis untuk mengeliminasi bahaya silent data-loss akibat split-brain.
3. **Resiliensi Lapisan Klien**: Penggunaan driver Sentinel-aware yang mengadopsi Pub/Sub reconnection hooks dan connection pool lifecycle management yang adaptif terhadap perubahan topologi instan.