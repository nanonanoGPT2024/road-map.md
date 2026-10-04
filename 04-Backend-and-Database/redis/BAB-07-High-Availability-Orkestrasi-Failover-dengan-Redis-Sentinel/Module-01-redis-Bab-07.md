# Bab 07 Module 01: High Availability & Orkestrasi Failover dengan Redis Sentinel

---

## 01. Identitas Modul
* **Track:** Backend & Database Architecture
* **Kategori:** 04-Backend-and-Database
* **Topik:** Redis Distributed Systems & High Availability
* **Modul:** Bab 07 Module 01: High Availability & Orkestrasi Failover dengan Redis Sentinel
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat:** Pemahaman mendalam tentang Replikasi Redis Asinkron, TCP/IP Networking, Protokol RESP (REdis Serialization Protocol), dan Arsitektur Distributed Consensus Dasar (Raft/Paxos).

---

## 02. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Membedah arsitektur internal Redis Sentinel, termasuk protokol gossip, mekanisme deteksi kegagalan (`SDOWN` vs `ODOWN`), dan proses pemilihan *Leader* berbasis varian Paxos/Raft.
2. Merancang topologi Redis Sentinel berkeandalan tinggi dengan mitigasi terhadap risiko *Split-Brain* dan kehilangan data akibat *failover* asinkron.
3. Mengonfigurasi dan mengorkestrasi *cluster* Redis Master-Replica yang diawasi oleh *quorum* Sentinel secara *declarative* menggunakan Docker Compose dan konfigurasi bare-metal.
4. Mengimplementasikan integrasi *client-side* berbasis koneksi adaptif (Node.js/Go) yang merespons event Sentinel (`+switch-master`, `+sdown`, `+odown`) secara instan tanpa *downtime* aplikasi.
5. Mengeksekusi prosedur *chaos engineering* untuk memvalidasi toleransi kesalahan, mengukur *Recovery Time Objective* (RTO) dan *Recovery Point Objective* (RPO).

---

## 03. Concept Map Diagram ASCII

```
+=============================================================================+
|                        TOPOLOGI REDIS SENTINEL CLUSTER                      |
+=============================================================================+
                                                                               
                        +----------------------+                               
                        |     CLIENT APP       |                               
                        +----------+-----------+                               
                                   | 1. Query Master Addr                      
                                   v                                           
        +--------------------------+--------------------------+                
        |                          |                          |                
        v                          v                          v                
+---------------+          +---------------+          +---------------+        
|  Sentinel 1   |<========>|  Sentinel 2   |<========>|  Sentinel 3   |        
|  Port: 26379  |  Gossip  |  Port: 26379  |  Gossip  |  Port: 26379  |        
+-------+-------+  (PubSub)+-------+-------+  (PubSub)+-------+-------+        
        |                          |                          |                
        | Heartbeat (PING)         | Heartbeat (PING)         | Heartbeat (PING)
        | & Monitoring             | & Monitoring             | & Monitoring   
        +--------------------------+--------------------------+                
                                   |                                           
            +----------------------+----------------------+                    
            |                                             |                    
            v                                             v                    
  +-------------------+      Asynchronous Repl   +-------------------+         
  |   REDIS MASTER    |=========================>|   REDIS REPLICA   |         
  |   Port: 6379      |      (Replication Stream)|   Port: 6379      |         
  +-------------------+                          +-------------------+         
            |                                             ^                    
            |                                             |                    
            +---------------- (Failover Promotion) -------+                    
```

---

## 04. Mengapa Relevan
Dalam arsitektur *backend* terdistribusi, kegagalan node (*node failure*) adalah sebuah kepastian statistik, bukan anomali. Standalone Redis instance merupakan *Single Point of Failure* (SPOF). Jika master *crash*, seluruh operasi penulisan (*writes*) terhenti dan *cache layer* menjadi dingin (*cache stampede*), berpotensi melumpuhkan basis data relasional di belakangnya.

Redis Sentinel hadir sebagai orkestrator terdistribusi standar industri yang menyediakan:
1. **Monitoring:** Terus-menerus memeriksa kesehatan node master dan replica.
2. **Notification:** Memancarkan alert melalui antarmuka Pub/Sub ketika terjadi anomali.
3. **Automatic Failover:** Memilih replica terbaik dan mempromosikannya menjadi master baru jika master aktif gagal.
4. **Configuration Provider:** Bertindak sebagai *service discovery* otoritatif bagi klien aplikasi.

---

## 05. Anatomi Konsep Inti

### 1. Deteksi Kegagalan: `SDOWN` vs `ODOWN`
Sentinel membedakan kegagalan instance ke dalam dua status:
*   **Subjectively Down (`SDOWN`):** Terjadi ketika sebuah instance Redis tidak merespons perintah `PING` dari *satu* node Sentinel spesifik selama interval waktu yang ditentukan oleh direktif `sentinel down-after-milliseconds`.
*   **Objectively Down (`ODOWN`):** Terjadi ketika node Sentinel yang mendeteksi `SDOWN` meminta konfirmasi dari Sentinel lain menggunakan perintah `SENTINEL is-master-down-by-addr`. Jika jumlah Sentinel yang menyetujui mencapai batas **Quorum** yang dikonfigurasi, status dinaikkan menjadi `ODOWN`. *Hanya status Master yang dapat dinaikkan ke `ODOWN`.*

### 2. Quorum vs Sentinel Majority
*   **Quorum:** Ambang batas minimum Sentinel yang harus menyatakan master tidak dapat dijangkau agar status `ODOWN` terpenuhi.
*   **Majority:** Jumlah Sentinel minimum yang diperlukan untuk memilih *Leader Sentinel* yang akan mengeksekusi failover. Formula *Majority*: $\lfloor N/2 \rfloor + 1$ (di mana $N$ adalah total node Sentinel).
*   *Penting:* Jika $N=3$, Quorum bisa diatur 2, dan Majority adalah $\lfloor 3/2 \rfloor + 1 = 2$. Failover **tidak dapat terjadi** jika jumlah Sentinel yang aktif kurang dari Majority, meskipun Quorum tercapai.

### 3. Pemilihan Leader Sentinel (Raft-like Consensus)
Saat master mencapai status `ODOWN`, Sentinel memulai proses pemilihan *Leader*:
1. Sentinel yang mendeteksi `ODOWN` menominasikan dirinya sebagai Leader dengan mengirimkan pesan `SENTINEL is-master-down-by-addr` yang menyertakan Run ID miliknya.
2. Sentinel lain memberikan suara (*vote*) kepada kandidat pertama yang memintanya dalam era (*epoch*) tertentu.
3. Kandidat yang memperoleh suara $\ge \text{Majority}$ memenangkan pemilu dan mengeksekusi *Failover State Machine*.

### 4. Algoritma Pemilihan Replika Baru
Leader Sentinel memilih replika yang akan dipromosikan berdasarkan kriteria prioritas terurut (*deterministic evaluation*):
1. **Replica Priority:** Nilai `replica-priority` terkecil di konfigurasi `redis.conf` (nilai `0` = tidak akan pernah dipromosikan).
2. **Replication Offset:** Memilih replika dengan `master_repl_offset` paling mutakhir (data paling sedikit hilang).
3. **Run ID Lexicographical:** Jika offset sama, dipilih Run ID dengan urutan ASCII terendah sebagai penentu akhir (*tie-breaker*).

### 5. Pencegahan Split-Brain & Data Loss
Replikasi Redis bersifat asinkron. Jika jaringan terisolasi (*network partition*), master lama dapat tetap menerima penulisan sementara Sentinel mengangkat master baru. Hal ini dimitigasi pada level Redis Master menggunakan dua konfigurasi kunci:
*   `min-replicas-to-write <count>`: Master menolak penulisan jika jumlah replika sehat kurang dari nilai ini.
*   `min-replicas-max-lag <seconds>`: Batas latensi maksimum *heartbeat* replika ke master.

---

## 06. Panduan Implementasi Step-by-Step

Berikut langkah membangun klaster Redis Sentinel (1 Master, 2 Replica, 3 Sentinel) pada sebuah *environment*:

### Langkah 1: Siapkan Konfigurasi Redis Master (`redis-master.conf`)
```ini
port 6379
bind 0.0.0.0
protected-mode no
daemonize no

# Persistence
appendonly yes
appendfsync everysec

# Security
requirepass SuperSecretAuth123!
masterauth SuperSecretAuth123!

# Split-brain protection
min-replicas-to-write 1
min-replicas-max-lag 10
```

### Langkah 2: Siapkan Konfigurasi Redis Replica (`redis-replica-1.conf` & `2`)
```ini
port 6379
bind 0.0.0.0
protected-mode no
daemonize no

# Replikasi diarahkan ke DNS/IP master awal
replicaof redis-master 6379

appendonly yes
appendfsync everysec

requirepass SuperSecretAuth123!
masterauth SuperSecretAuth123!
```

### Langkah 3: Siapkan Konfigurasi Sentinel (`sentinel-1.conf`, `2`, `3`)
*Sentinel akan menulis ulang file ini secara otomatis saat runtime. Pastikan izin write tersedia.*
```ini
port 26379
bind 0.0.0.0
protected-mode no

# Monitor target: <master-name> <ip> <port> <quorum>
sentinel monitor mymaster redis-master 6379 2

# Konfigurasi otentikasi master
sentinel auth-pass mymaster SuperSecretAuth123!

# 5 detik tanpa respon = SDOWN
sentinel down-after-milliseconds mymaster 5000

# Waktu tunggu failover sebelum dianggap gagal
sentinel failover-timeout mymaster 60000

# Jumlah replika yang dapat sinkronisasi paralel dengan master baru
sentinel parallel-syncs mymaster 1
```

---

## 07. Contoh Kasus Sederhana: Manual Sentinel Query CLI

Perintah operasional CLI untuk memantau status konsensus dan discovery master baru:

```bash
# Menghubungi Sentinel via redis-cli
redis-cli -p 26379

# 1. Dapatkan alamat Master yang aktif saat ini
127.0.0.1:26379> SENTINEL get-master-addr-by-name mymaster
1) "172.28.0.2"
2) "6379"

# 2. Dapatkan status metadata master
127.0.0.1:26379> SENTINEL master mymaster
 1) "name"
 2) "mymaster"
 3) "ip"
 4) "172.28.0.2"
 5) "flags"
 6) "master"
 ...
31) "num-slaves"
32) "2"
33) "num-other-sentinels"
34) "2"
35) "quorum"
36) "2"

# 3. Simulasi Manual Triggered Failover (Force Failover)
127.0.0.1:26379> SENTINEL failover mymaster
OK
```

---

## 08. Implementasi Production-Grade Lengkap Kode

### 1. Orkestrasi Docker Compose (`docker-compose.yml`)

```yaml
version: '3.8'

networks:
  sentinel-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16

services:
  redis-master:
    image: redis:7.2-alpine
    container_name: redis-master
    command: >
      redis-server 
      --requirepass SuperSecretAuth123! 
      --masterauth SuperSecretAuth123! 
      --appendonly yes 
      --min-replicas-to-write 1 
      --min-replicas-max-lag 10
    ports:
      - "6379:6379"
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.2

  redis-replica-1:
    image: redis:7.2-alpine
    container_name: redis-replica-1
    command: >
      redis-server 
      --replicaof 172.28.0.2 6379 
      --requirepass SuperSecretAuth123! 
      --masterauth SuperSecretAuth123! 
      --appendonly yes
    depends_on:
      - redis-master
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.3

  redis-replica-2:
    image: redis:7.2-alpine
    container_name: redis-replica-2
    command: >
      redis-server 
      --replicaof 172.28.0.2 6379 
      --requirepass SuperSecretAuth123! 
      --masterauth SuperSecretAuth123! 
      --appendonly yes
    depends_on:
      - redis-master
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.4

  sentinel-1:
    image: redis:7.2-alpine
    container_name: sentinel-1
    command: >
      sh -c "echo 'port 26379' > /tmp/sentinel.conf &&
             echo 'sentinel monitor mymaster 172.28.0.2 6379 2' >> /tmp/sentinel.conf &&
             echo 'sentinel auth-pass mymaster SuperSecretAuth123!' >> /tmp/sentinel.conf &&
             echo 'sentinel down-after-milliseconds mymaster 4000' >> /tmp/sentinel.conf &&
             echo 'sentinel failover-timeout mymaster 30000' >> /tmp/sentinel.conf &&
             echo 'sentinel parallel-syncs mymaster 1' >> /tmp/sentinel.conf &&
             redis-sentinel /tmp/sentinel.conf"
    depends_on:
      - redis-master
      - redis-replica-1
      - redis-replica-2
    ports:
      - "26379:26379"
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.11

  sentinel-2:
    image: redis:7.2-alpine
    container_name: sentinel-2
    command: >
      sh -c "echo 'port 26379' > /tmp/sentinel.conf &&
             echo 'sentinel monitor mymaster 172.28.0.2 6379 2' >> /tmp/sentinel.conf &&
             echo 'sentinel auth-pass mymaster SuperSecretAuth123!' >> /tmp/sentinel.conf &&
             echo 'sentinel down-after-milliseconds mymaster 4000' >> /tmp/sentinel.conf &&
             echo 'sentinel failover-timeout mymaster 30000' >> /tmp/sentinel.conf &&
             echo 'sentinel parallel-syncs mymaster 1' >> /tmp/sentinel.conf &&
             redis-sentinel /tmp/sentinel.conf"
    depends_on:
      - redis-master
    ports:
      - "26380:26379"
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.12

  sentinel-3:
    image: redis:7.2-alpine
    container_name: sentinel-3
    command: >
      sh -c "echo 'port 26379' > /tmp/sentinel.conf &&
             echo 'sentinel monitor mymaster 172.28.0.2 6379 2' >> /tmp/sentinel.conf &&
             echo 'sentinel auth-pass mymaster SuperSecretAuth123!' >> /tmp/sentinel.conf &&
             echo 'sentinel down-after-milliseconds mymaster 4000' >> /tmp/sentinel.conf &&
             echo 'sentinel failover-timeout mymaster 30000' >> /tmp/sentinel.conf &&
             echo 'sentinel parallel-syncs mymaster 1' >> /tmp/sentinel.conf &&
             redis-sentinel /tmp/sentinel.conf"
    depends_on:
      - redis-master
    ports:
      - "26381:26379"
    networks:
      sentinel-net:
        ipv4_address: 172.28.0.13
```

### 2. Client-Side Implementation: Go (Production Resilient Client)

Klien ini secara transparan mendengarkan topologi cluster melalui Sentinel pool dan menangani rekoneksi secara otomatis saat failover terjadi:

```go
package main

import (
	"context"
	"fmt"
	"log"
	"sync/atomic"
	"time"

	"github.com/redis/go-redis/v9"
)

type RedisSentinelClient struct {
	rdb *redis.Client
	ctx context.Context
}

func NewRedisSentinelClient(sentinelAddrs []string, masterName, password string) *RedisSentinelClient {
	ctx := context.Background()

	// Inisialisasi FailoverClient (Sentinel-aware)
	rdb := redis.NewFailoverClient(&redis.FailoverOptions{
		MasterName:    masterName,
		SentinelAddrs: sentinelAddrs,
		Password:      password,
		
		// Parameter Connection Pool
		PoolSize:        50,
		MinIdleConns:    10,
		MaxRetries:      5,
		MinRetryBackoff: 100 * time.Millisecond,
		MaxRetryBackoff: 1 * time.Second,
		
		// Timeout
		DialTimeout:  5 * time.Second,
		ReadTimeout:  2 * time.Second,
		WriteTimeout: 2 * time.Second,
	})

	return &RedisSentinelClient{
		rdb: rdb,
		ctx: ctx,
	}
}

func (c *RedisSentinelClient) StartResilientWorker() {
	var counter uint64

	for {
		atomic.AddUint64(&counter, 1)
		key := fmt.Sprintf("metric:device:%d", counter%100)
		val := fmt.Sprintf("payload-timestamp-%d", time.Now().UnixNano())

		// Eksekusi Write ke Master
		err := c.rdb.Set(c.ctx, key, val, 10*time.Minute).Err()
		if err != nil {
			log.Printf("[WRITE ERROR] Failed to write key %s: %v (Failover in progress?)", key, err)
		} else {
			log.Printf("[SUCCESS] Write OK -> %s = %s", key, val)
		}

		time.Sleep(500 * time.Millisecond)
	}
}

func main() {
	sentinels := []string{
		"127.0.0.1:26379",
		"127.0.0.1:26380",
		"127.0.0.1:26381",
	}
	masterGroup := "mymaster"
	authPassword := "SuperSecretAuth123!"

	client := NewRedisSentinelClient(sentinels, masterGroup, authPassword)
	defer client.rdb.Close()

	// Ping cluster
	status, err := client.rdb.Ping(context.Background()).Result()
	if err != nil {
		log.Fatalf("Fatal: Cannot connect to Redis cluster via Sentinel: %v", err)
	}
	log.Printf("Cluster Connected successfully: Status %s", status)

	// Jalankan continuous worker loop
	client.StartResilientWorker()
}
```

---

## 09. Diagram Alur Kerja Failover Otomatis (ASCII)

```
[ Master ]            [ Replica 1 ]         [ Sentinel 1 ]         [ Sentinel 2 ]         [ Sentinel 3 ]
    |                      |                      |                      |                      |
    X (CRASH/ISOLATED)     |                      |                      |                      |
                           |                      |-- PING ------------->X                      |
                           |                      |-- (No response) ---->|                      |
                           |                      |                      |                      |
                           |                      |-- (Mark SDOWN) ----->|                      |
                           |                      |                      |                      |
                           |                      |-- is-master-down? -->|                      |
                           |                      |<-- Yes (Ack SDOWN) --|                      |
                           |                      |-- is-master-down? ------------------------->|
                           |                      |<-- Yes (Ack SDOWN) -------------------------|
                           |                      |                                             |
                           |                      +== Master set to ODOWN (Quorum met: 3/3) ====+
                           |                      |                                             |
                           |                      |-- Solicit Votes (Epoch + 1) --------------->|
                           |                      |<-- Voted For S1 ----------------------------|
                           |                      |-- Solicit Votes (Epoch + 1) ---------------->
                           |                      |<-- Voted For S1 ----------------------------|
                           |                      |                                             |
                           |                      +== Sentinel 1 Elected LEADER (Majority: 3/3)+
                           |                      |                                             |
                           |                      |-- SLAVEOF NO ONE --->|                      |
                           |<-- RECONFIG (PROMOTED)                      |                      |
                           |                      |                      |                      |
                           |                      |-- Publish +switch-master ------------------>|
                           |                      |-- Inform Replica 2 to follow new master --->|
                           |                      |                                             |
                     [ NEW MASTER ]               +================= FAILOVER COMPLETE =========+
```

---

## 10. Analisis Trade-offs

| Dimensi Arsitektur | Redis Sentinel (HA Active-Passive) | Redis Cluster (HA + Sharding) | Standalone + Persisted Disk |
| :--- | :--- | :--- | :--- |
| **Batas Kapasitas RAM** | Dibatasi oleh RAM 1 Node Master (Scale-up) | Didistribusikan ke ratusan node (Scale-out) | Dibatasi oleh 1 Mesin |
| **Kompleksitas Operasional** | Menengah (Perlu memelihara node Sentinel terpisah) | Sangat Tinggi (Slot allocation, resharding) | Sangat Rendah |
| **Multi-Key Operations** | Penuh (Mendukung transaksi `MULTI`/`EXEC`, `LUA`) | Terbatas (Hanya jika hash-slot sama / `{hash-tag}`) | Penuh |
| **Data Consistency** | *Eventual Consistency* (Potensi kehilangan data saat failover) | *Eventual Consistency* (Sama) | *Stronger* (Jika `appendfsync always`), SPOF |
| **Latensi Jaringan Klien** | Nol overhead routing (Langsung ke Master IP) | Ada overhead `MOVED`/`ASK` redirects | Terendah (Langsung) |

---

## 11. Best Practices & Antipatterns

### ✅ Best Practices
1. **Ganjilkan Jumlah Sentinel:** Selalu gunakan minimal **3 Sentinel** di node/AZ fisik yang berbeda untuk menghindari *split-brain quorum deadlock*.
2. **Standardisasi Port dan IP Static:** Di production/container orchestration, berikan IP statis pada node Sentinel atau pastikan DNS routing tidak berganti secara dinamis tanpa restart Sentinel.
3. **Konfigurasi `min-replicas-to-write`:** Wajib diterapkan untuk menghentikan penerimaan data pada Master yang terisolasi dari replikanya sebelum status failover selesai.
4. **Proteksi Password Simetris:** Konfigurasikan `requirepass` dan `masterauth` dengan string password yang identik di seluruh Master dan Replika.

### ❌ Antipatterns
1. **Menjalankan 2 Sentinel Saja:** Jika 1 node Sentinel mati, Majority Requirement ($\lfloor 2/2 \rfloor + 1 = 2$) tidak akan pernah terpenuhi saat master crash $\rightarrow$ HA Lumpuh.
2. **Sentinel Ditempatkan di Host yang Sama dengan Redis Node:** Jika host fisik mati, Sentinel dan Redis Master/Replica mati bersamaan.
3. **Hardcoded Master IP di Client App:** Menghubungkan aplikasi langsung ke port 6379 tanpa Sentinel SDK. Ketika failover terjadi, aplikasi akan terus menulis ke master yang sudah demoted (read-only).

---

## 12. Security Hardening

Sentinel secara default dapat menjadi celah keamanan jika tidak dikeraskan.

### 1. Sentinel Authentication (Redis 6+)
Mulai Redis 6.0+, Sentinel mendukung ACL dan autentikasi eksplisit antar Sentinel:
```ini
# sentinel.conf
sentinel sentinel-user admin
sentinel sentinel-pass UltraSecureSentinelPass987!
requirepass UltraSecureSentinelPass987!
```

### 2. Network Isolation & TLS Encrypted Transport
Enkapsulasi seluruh lalu lintas replikasi dan sentinel monitoring dengan TLS:
```ini
# redis.conf & sentinel.conf
tls-port 26379
port 0
tls-cert-file /etc/redis/tls/redis.crt
tls-key-file /etc/redis/tls/redis.key
tls-ca-cert-file /etc/redis/tls/ca.crt
tls-auth-clients yes
tls-replication yes
```

### 3. Binding & Protected Mode
Hindari Sentinel binding ke `0.0.0.0` di server publik:
```ini
bind 10.0.10.15
protected-mode yes
```

---

## 13. Observabilitas & Debugging

### 1. Metrik Sentinel Kunci (Prometheus / CLI)
Eksekusi: `redis-cli -p 26379 INFO sentinel`

```text
# Sentinel
sentinel_masters:1
sentinel_tilt:0                 <-- HARUS 0. Jika 1, Sentinel mendeteksi clock desync parah
sentinel_running_scripts:0
sentinel_scripts_queue_length:0
master0:name=mymaster,status=ok,address=172.28.0.2:6379,slaves=2,sentinels=3
```

### 2. Real-time PubSub Event Streaming
Dengarkan seluruh orkestrasi internal failover menggunakan `redis-cli`:
```bash
redis-cli -p 26379 -h 127.0.0.1 PSUBSCRIBE "*"
```
Event stream yang harus diamati:
*   `+sdown` : Node dinyatakan subjective down.
*   `-sdown` : Node pulih dari subjective down.
*   `+odown` : Master dinyatakan objective down.
*   `+vote-for-leader` : Sentinel memberikan suara konsensus.
*   `+switch-master` : Master baru berhasil dipilih dan dipromosikan.

---

## 14. Benchmarking & Performance: Failover Latency Validation

Gunakan Bash Script berikut untuk mengukur **Mean Time to Recovery (MTTR)**:

```bash
#!/usr/bin/env bash
set -e

SENTINEL_IP="127.0.0.1"
SENTINEL_PORT=26379
MASTER_NAME="mymaster"

echo "=== 1. Memeriksa Master Aktif ==="
OLD_MASTER=$(redis-cli -h $SENTINEL_IP -p $SENTINEL_PORT SENTINEL get-master-addr-by-name $MASTER_NAME | head -n 1)
echo "Master aktif saat ini: $OLD_MASTER"

echo "=== 2. Mematikan Master Aktif (Simulasi Crash) ==="
START_TIME=$(date +%s%N)
docker stop redis-master > /dev/null

echo "Menunggu Sentinel mendeteksi failover..."
NEW_MASTER=""
while true; do
    CURRENT_MASTER=$(redis-cli -h $SENTINEL_IP -p $SENTINEL_PORT SENTINEL get-master-addr-by-name $MASTER_NAME 2>/dev/null | head -n 1 || true)
    if [ "$CURRENT_MASTER" != "$OLD_MASTER" ] && [ -n "$CURRENT_MASTER" ]; then
        NEW_MASTER=$CURRENT_MASTER
        END_TIME=$(date +%s%N)
        break
    fi
    sleep 0.1
done

ELAPSED_MS=$(( (END_TIME - START_TIME) / 1000000 ))
echo "=== FAILOVER SELESAI ==="
echo "Master Baru Terpilih : $NEW_MASTER"
echo "Total Downtime (RTO) : ${ELAPSED_MS} ms"
```

---

## 15. Hands-on Lab Mini-Project

### Skenario:
Sistem E-Commerce Payment Gateway membutuhkan sistem Redis HA tanpa downtime saat node utama mengalami *hardware failure*.

### Tugas:
1. Jalankan konfigurasi Docker Compose dari Seksi 08.
2. Jalankan aplikasi worker Go (`go run main.go`).
3. Eksekusi crash injection pada node master:
   ```bash
   docker pause redis-master
   ```
4. Pantau log Go client: amati berapa banyak request yang error/retry, dan catat saat aplikasi otomatis beralih ke Master baru (`redis-replica-1` atau `redis-replica-2`).
5. Pulihkan kembali node master lama:
   ```bash
   docker unpause redis-master
   ```
6. Amati Sentinel secara otomatis mendemosikan node master lama menjadi Replica di bawah master baru (`+convert-to-slave`).

---

## 16. Automated Testing & Verification

Automated Integration Test menggunakan Bash & Test Harness:

```bash
#!/usr/bin/env bash
# File: verify_ha.sh
set -euo pipefail

PASS="SuperSecretAuth123!"

echo "[TEST] 1. Validasi Jumlah Sentinel..."
COUNT=$(redis-cli -p 26379 SENTINEL sentinels mymaster | grep -c "ip" || true)
if [ "$COUNT" -ge 2 ]; then
    echo ">> OK: Terdeteksi ($COUNT) peer sentinels."
else
    echo ">> FAILED: Sentinel quorum peer tidak lengkap."
    exit 1
fi

echo "[TEST] 2. Menulis data ke Master..."
MASTER_IP=$(redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster | head -n 1)
redis-cli -h $MASTER_IP -p 6379 -a $PASS SET validation_key "INTEGRITY_VERIFIED" > /dev/null 2>&1

echo "[TEST] 3. Memverifikasi Replikasi Data ke Slaves..."
REPLICA_IP="172.28.0.3"
VAL=$(redis-cli -h $REPLICA_IP -p 6379 -a $PASS GET validation_key 2>/dev/null)

if [ "$VAL" == "INTEGRITY_VERIFIED" ]; then
    echo ">> OK: Data berhasil direplikasi secara asinkron ke $REPLICA_IP."
else
    echo ">> FAILED: Data replication desync."
    exit 1
fi

echo "ALL INTEGRATION CHECKS PASSED!"
```

---

## 17. Troubleshooting Guide

### Gejala 1: Sentinel Tidak Mau Memilih Leader (Failover Macet)
*   **Akar Masalah:** Sentinel yang aktif tidak mencapai ambang batas *Majority*. Contoh: 2 dari 3 Sentinel mati, tersisa 1 Sentinel. Quorum diset 1. Status `ODOWN` terpenuhi tapi Sentinel tidak bisa membentuk *Majority* ($\lfloor 3/2 \rfloor + 1 = 2$).
*   **Solusi:** Pastikan minimal $(N/2) + 1$ Sentinel selalu *alive* dan saling terhubung di jaringan.

### Gejala 2: Master Lama Kembali Menyala tapi Menolak Write
*   **Akar Masalah:** Sentinel mengonfigurasi master lama menjadi replika (`slaveof <new-master-ip>`). Mode `read-only` aktif secara default pada replika.
*   **Solusi:** Ini adalah perilaku normal (*expected*). Aplikasi klien yang benar tidak boleh menulis ke node tersebut, melainkan harus meminta discovery IP master baru ke Sentinel.

### Gejala 3: Error `READONLY You can't write against a read only replica` di Client
*   **Akar Masalah:** Klien caching IP master lama via koneksi pool statis dan tidak menangkap update dari Sentinel PubSub `+switch-master`.
*   **Solusi:** Gunakan client library resmi yang *Sentinel-aware* (e.g., `go-redis/v9`, `ioredis`, `Lettuce`).

---

## 18. Checklist Produksi

- [ ] **Sentinel Instance Count:** Menggunakan jumlah ganjil Sentinel (minimal 3, rekomendasi 5 untuk Multi-DC).
- [ ] **Cross-AZ Deployment:** Masing-masing Sentinel dan Redis Node diletakkan pada Availability Zone (AZ) independen.
- [ ] **Split-Brain Configuration:** Parameter `min-replicas-to-write` diisi $\ge 1$ dan `min-replicas-max-lag` diisi $\le 10$ pada seluruh node Redis.
- [ ] **Simetris Authentication:** `requirepass` dan `masterauth` dikonfigurasi sama persis di setiap master dan replica.
- [ ] **Down Detection Tuning:** Nilai `down-after-milliseconds` diatur proporsional (rekomendasi 3000ms - 5000ms) untuk mencegah *flapping failover* akibat spike jaringan transien.
- [ ] **Script Permission:** File `sentinel.conf` memiliki izin read/write bagi sistem operasi pengguna redis daemon.
- [ ] **Client Reconnect Strategy:** Client SDK mengimplementasikan exponential backoff dan dynamic topology reload.

---

## 19. Ringkasan Eksekutif

Redis Sentinel menyediakan High Availability (HA) lapisan enterprise untuk topologi Master-Replica tanpa memerlukan *hardware load-balancer* mahal. Sistem ini mengandalkan:
1. **Deteksi Berbasis Quorum (`ODOWN`):** Mencegah *false alarm* dari satu pengamat yang terisolasi.
2. **Leader Consensus:** Memilih satu orkestrator tunggal untuk mengeksekusi transisi peran node Redis secara aman.
3. **Dynamic Client Discovery:** Membebaskan arsitektur aplikasi dari keterikatan alamat IP statis.

Dengan mengonfigurasi pengamanan *split-brain* (`min-replicas-to-write`) dan mengadopsi driver Sentinel-native, sistem backend mampu mencapai *near-zero downtime* dengan Mean Time to Recovery (MTTR) di bawah 5 detik saat terjadi bencana infrastruktur.

---

## 20. Referensi & Bacaan Lanjutan
*   **Dokumentasi Resmi Redis Sentinel:** [https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/](https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel