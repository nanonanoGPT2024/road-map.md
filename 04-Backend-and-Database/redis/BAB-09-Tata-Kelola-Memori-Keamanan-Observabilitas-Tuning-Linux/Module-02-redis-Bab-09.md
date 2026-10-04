# BAB 09: Tata Kelola Memori, Keamanan, Observabilitas, & Tuning Linux
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonfigurasi dan membedah mekanisme internal alokator memori `jemalloc`, kalkulasi *Copy-on-Write* (COW), serta arsitektur algoritma *eviction* berbasis aproksimasi (LRU/LFU) di Redis.
- Mengimplementasikan sistem keamanan berlapis mencakup *Role-Based Access Control* (RBAC) via Redis ACL v2, enkripsi transit *mutual TLS* (mTLS), dan mitigasi serangan injeksi protokol.
- Merancang arsitektur observabilitas komprehensif menggunakan metrik *engine internal* (`INFO`, `LATENCY ENGINE`, `SLOWLOG`) yang diekspor ke Prometheus serta divisualisasikan pada Grafana.
- Menerapkan rekayasa performa tingkat kernel Linux (*OS-level tuning*): eliminasi *Transparent Huge Pages* (THP), optimasi subsistem memori virtual (`vm.overcommit_memory`, `swappiness`), serta mitigasi antrean soket jaringan (`somaxconn`, `backlog`).
- Memitigasi masalah fragmentasi memori aktif (`activedefrag`) dan lonjakan latensi (*p99/p99.9 spikes*) pada beban kerja tinggi (*high-throughput, ultra-low latency*).

---

### 2. Prerequisite
- Pemahaman mendalam tentang struktur data fundamental Redis (Strings, Hashes, Lists, Sets, Sorted Sets, Streams).
- Pemahaman administrasi sistem Linux tingkat menengah (konfigurasi `sysctl`, manajemen memori virtual, *paging*, hak akses file, dan *systemd*).
- Pengetahuan dasar tentang kriptografi kunci publik (X.509, CA, sertifikat TLS/SSL, dan algoritma *cipher*).
- Pemahaman jaringan TCP/IP (siklus hidup *socket*, *TCP handshake*, dan *network buffer*).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Arsitektur Alokasi Memori dan Fragmentasi (jemalloc)
Redis tidak mengalokasikan memori langsung dari kernel untuk setiap objek individual menggunakan `malloc()` sistem standar secara mentah; melainkan menggunakan alokator performa tinggi, umumnya **jemalloc**. 

```
+-----------------------------------------------------------------------+
|                             REDIS PROCESS                             |
|  +-----------------------------------------------------------------+  |
|  | dictEntry / robj (Redis Objects)                                |  |
|  +-----------------------------------------------------------------+  |
|                                  | (jemalloc API: je_malloc)          |
|  +-------------------------------+---------------------------------+  |
|  | jemalloc Runtime:                                               |  |
|  | - Small classes: [8B, 16B, 32B, ..., 14KB]                      |  |
|  | - Large classes: [16KB, 32KB, ..., 2MB] (Extents)              |  |
|  | - Arenas (Thread-specific / Shared)                            |  |
|  +-----------------------------------------------------------------+  |
+----------------------------------+------------------------------------+
                                   | Virtual Memory Pages (mmap/brk)
+----------------------------------v------------------------------------+
|                         LINUX KERNEL MEMORY                           |
|  [ Physical RAM (4KB Pages) ] <---> [ Swap Space ]                    |
+-----------------------------------------------------------------------+
```

1. **Arenas and Extents:** `jemalloc` membagi memori ke dalam *arenas* terpisah guna mengurangi kontensi thread. Untuk alokasi berukuran kecil (*small allocations*), jemalloc membulatkan ukuran ke dalam *size classes* tertentu (misal: permintaan 38 byte dialokasikan ke keranjang 48 byte). Selisih ukuran ini menimbulkan **fragmentasi internal**.
2. **External Fragmentation:** Terjadi ketika halaman memori (biasanya berukuran 4 KB) dialokasikan, sebagian data di dalamnya dibebaskan (`DEL`), tetapi sisa data lain dalam halaman tersebut masih aktif. Akibatnya, halaman memori virtual tersebut tidak dapat dikembalikan ke sistem operasi via `madvise(MADV_DONTNEED)`.
3. **Active Defragmentation (`activedefrag`):** Fitur runtime Redis yang memindai ruang kunci (*keyspace*) secara berkala saat server tidak dalam kondisi saturasi beban, mengalokasikan ulang objek ke blok memori yang berdekatan (*contiguous*), dan membebaskan blok memori lama yang terfragmentasi.

#### B. Mekanisme Copy-on-Write (COW) saat Forking (BGSAVE & AOF Rewrite)
Ketika Redis menjalankan snapshot RDB (`BGSAVE`) atau `BGREWRITEAOF`, sistem memanggil *system call* `fork()`. 

- Kernel Linux menduplikasi *page table* dari proses induk (*parent*) ke proses anak (*child*), tanpa menyalin fisik halaman RAM secara langsung. Penanda halaman diatur menjadi *read-only*.
- Jika klien menulis data ke Redis induk selama proses *background child* berjalan, CPU memicu pengecualian *page fault*. Kernel kemudian menyalin halaman memori fisik berukuran 4 KB tersebut ke lokasi baru (*Copy-on-Write*) dan mengizinkan modifikasi pada salinan proses induk.
- **Dampak Transparent Huge Pages (THP):** Jika kernel mengaktifkan THP (ukuran halaman 2 MB, bukan 4 KB), satu mutasi minor pada string 10-byte akan memaksa Linux menduplikasi keseluruhan blok 2 MB. Hal ini dapat melipatgandakan alokasi memori secara instan, memicu kondisi *Out-of-Memory* (OOM) Killer, dan menyebabkan lonjakan latensi p99.

#### C. Algoritma Eviction Approximated LRU dan LFU
Redis tidak menyimpan linked-list absolut untuk implementasi *Least Recently Used* (LRU) karena struktur tersebut membutuhkan pointer ganda (`prev` dan `next`) sebesar 16 byte per objek, yang mengakibatkan *overhead* memori signifikan.

- **Approximated LRU:** Setiap objek Redis (`robj`) memiliki metadata `lru:LRU_BITS` (24-bit). Saat evaluasi *eviction*, Redis mengambil sampel acak sebanyak $N$ kunci (dikonfigurasi melalui `maxmemory-samples`, *default* 5), memasukkannya ke dalam *eviction pool* (array berukuran 16 elemen yang diurutkan berdasarkan waktu *idle*), dan mengeliminasi kunci dengan waktu *idle* terlama.
- **Approximated LFU (Least Frequently Used):** 24 bit dibagi menjadi dua komponen:
  1. **8-bit Counter (0–255):** Menggunakan *Morris Counter* (peningkatan probabilistik berdasarkan parameter `lfu-log-factor`).
  2. **16-bit Last Decrement Time (LDT):** Menit waktu UNIX yang digunakan untuk meluruhkan counter secara berkala berdasarkan parameter `lfu-decay-time`.

```
  24-bit Metadata Field in robj:
  +--------------------------+---------------------------+
  |  16-bit LDT              |  8-bit Counter            |
  |  (Last Decrement Time)   |  (Logistic Morris Counter)|
  +--------------------------+---------------------------+
```

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional / Default | Standar Arsitektur Produksi Enterprise |
| :--- | :--- | :--- |
| **Alokasi Memori** | Mengandalkan alokasi dinamis tanpa batas (`maxmemory 0`). | Menetapkan batas rigid `maxmemory` (~70-75% dari total RAM), mengaktifkan `activedefrag`, dan tuning `maxmemory-samples`. |
| **Keamanan** | Autentikasi tunggal `requirepass`, koneksi *plaintext* port 6379. | ACL granular per-layanan (prinsip *least privilege*), autentikasi timbal balik (mTLS), penonaktifan/penggantian nama perintah berbahaya. |
| **Observabilitas** | Eksekusi ad-hoc `redis-cli monitor` (membebani CPU hingga drop performa). | Pemanfaatan Prometheus Redis Exporter berbasis metrik *engine*, konfigurasi `latency-monitor-threshold`, analisis metrik jemalloc. |
| **Konfigurasi Linux** | Nilai *default* distribusi OS (`THP: always`, `overcommit: 0`). | `THP: never`, `vm.overcommit_memory = 1`, pengoptimalan `somaxconn`, serta alokasi swap minimal yang terkontrol. |

---

### 5. How (Workflow Detail)

Alur kerja audit, tuning, dan pengamanan instance Redis produksi:

```
[1. Linux Kernel Tuning] 
   └── Nonaktifkan THP -> Atur overcommit_memory=1 -> Besarkan somaxconn & tcp_backlog
[2. Redis Memory Baseline Setup]
   └── Tetapkan maxmemory -> Pilih Eviction Policy -> Kalibrasi activedefrag
[3. Cryptographic & Access Hardening]
   └── Generate PKI (CA, Certs) -> Enable TLS on Engine -> Definisikan ACL Rules
[4. Telemetry Pipeline Attachment]
   └── Configure SLOWLOG -> Set latency-monitor-threshold -> Attach Prometheus Exporter
```

1. **Fase Kernel Sanitization:**
   - Ubah `/sys/kernel/mm/transparent_hugepage/enabled` ke `never`.
   - Modifikasi parameter kernel via `/etc/sysctl.conf`:
     ```ini
     vm.overcommit_memory = 1
     net.core.somaxconn = 65535
     vm.swappiness = 1
     net.ipv4.tcp_max_syn_backlog = 65535
     ```
2. **Fase Tata Kelola Memori Engine:**
   - Hitung kebutuhan kapasitas Redis:
     $$\text{RAM Maksimal Redis} = \text{Total RAM Fisik} - (\text{Estimasi COW overhead} + \text{OS Overhead})$$
   - Konfigurasi limit memori dan strategi alokasi pada `redis.conf`:
     ```ini
     maxmemory 12gb
     maxmemory-policy allkeys-lru
     maxmemory-samples 10
     activedefrag yes
     active-defrag-ignore-bytes 100mb
     active-defrag-threshold-lower 10
     active-defrag-threshold-upper 30
     active-defrag-cycle-min 5
     active-defrag-cycle-max 50
     ```
3. **Fase Penerapan Keamanan (mTLS & ACL):**
   - Bangun infrastruktur sertifikat X.509 (*Mutual TLS*).
   - Buat user ACL fungsional di `users.acl` dengan pembatasan *keyspace* dan perintah (hindari izin `+@all`).
4. **Fase Instrumentasi & Telemetri:**
   - Aktifkan engine latensi: `CONFIG SET latency-monitor-threshold 20` (dalam milidetik).
   - Konfigurasi log lambat (*slow log*): `CONFIG SET slowlog-log-slower-than 10000` (10 milidetik).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Memori Redis sebagai Sistem Perpustakaan Modern

Bayangkan memori Redis seperti sebuah perpustakaan modern dengan batas ruang tetap:
- **`jemalloc`** adalah pustakawan pengelola rak. Buku tidak disimpan di sembarang celah, melainkan diletakkan pada slot rak standar berukuran tetap (8cm, 16cm, 32cm). Jika Anda menaruh buku 10cm di rak 16cm, ada 6cm ruang kosong yang terbuang (**Internal Fragmentation**).
- **`activedefrag`** adalah staf pembersih malam yang mengatur ulang buku-buku agar rak yang setengah kosong terkonsolidasi menjadi satu rak padat, mengosongkan rak lainnya sehingga bisa dipakai kembali (**Compaction**).
- **`fork()` COW** seperti mempekerjakan fotografer untuk mengarsipkan seluruh isi buku perpustakaan. Daripada menyalin jutaan buku secara fisik saat itu juga, staf perpustakaan hanya mencetak lembar baru saat ada pembaca yang hendak mencoret-coret halaman buku tertentu selama proses pemotretan berlangsung.

```
ALUR VERIFIKASI KEAMANAN & AKSES KUNCI (mTLS + ACL):

[ Client Application ]
       |
       | 1. TCP Handshake + mTLS Negotiation (Verify Server CA & Client Cert)
       v
+-----------------------------------------------------------------+
| TLS Termination Layer (redis-server engine)                    |
+-----------------------------------------------------------------+
       |
       | 2. Decrypted Command Packet (e.g., "HGET order:1024 status")
       v
+-----------------------------------------------------------------+
| ACL Layer Verification                                          |
| Check:                                                          |
| - Authenticated User? -> 'payment-service'                      |
| - Allowed Command?    -> 'HGET' matches +@read or +hget         |
| - Allowed Key Pattern?-> 'order:1024' matches ~order:*          |
+-----------------------------------------------------------------+
       |
       | Validated
       v
+-----------------------------------------------------------------+
| Redis Execution Engine (Single-Threaded Event Loop Core)        |
+-----------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Implementasi Praktis Konfigurasi Hardening & Monitoring

##### 1. Template `redis.conf` Enterprise (Ekstrak Krusial)
```ini
# --- JARINGAN & TLS ---
port 0
tls-port 6379
tls-cert-file /etc/redis/tls/redis.crt
tls-key-file /etc/redis/tls/redis.key
tls-ca-cert-file /etc/redis/tls/ca.crt
tls-auth-clients yes
tls-protocols "TLSv1.2 TLSv1.3"
tls-ciphers DEFAULT:!MEDIUM:!LOW:!EXP:!aNULL:!eNULL

# --- MANAJEMEN MEMORI ---
maxmemory 8589934592
maxmemory-policy volatile-lfu
maxmemory-samples 10
activedefrag yes
active-defrag-ignore-bytes 200mb
active-defrag-threshold-lower 15
active-defrag-threshold-upper 35

# --- KEAMANAN & ACL ---
aclfile /etc/redis/users.acl

# --- KINERJA & LATENSI ---
latency-monitor-threshold 10
slowlog-log-slower-than 5000
slowlog-max-len 1024
tcp-backlog 65535
tcp-keepalive 300
```

##### 2. File Definisi ACL (`/etc/redis/users.acl`)
```text
user default off
user prometheus_monitor on #b3c9b74070e1763131ec8b50 ~* +client +info +slowlog +latency +ping
user order_service on >Str0ngAuthP@ssw0rd! ~order:* ~customer:* +@read +@write -@admin -@dangerous -flushdb -flushall -keys
```

##### 3. Klien Go Terhubung dengan mTLS dan ACL
```go
package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/redis/go-redis/v9"
)

func createSecureRedisClient() (*redis.Client, error) {
	// 1. Muat Root CA Sertifikat
	caCert, err := os.ReadFile("/etc/redis/tls/ca.crt")
	if err != nil {
		return nil, fmt.Errorf("gagal membaca CA cert: %w", err)
	}
	caCertPool := x509.NewCertPool()
	if !caCertPool.AppendCertsFromPEM(caCert) {
		return nil, fmt.Errorf("gagal parsing CA cert")
	}

	// 2. Muat Sertifikat & Kunci Klien (mTLS)
	clientCert, err := tls.LoadX509KeyPair(
		"/etc/redis/tls/client.crt",
		"/etc/redis/tls/client.key",
	)
	if err != nil {
		return nil, fmt.Errorf("gagal membaca client keypair: %w", err)
	}

	// 3. Bangun TLS Config
	tlsConfig := &tls.Config{
		Certificates: []tls.Certificate{clientCert},
		RootCAs:      caCertPool,
		MinVersion:   tls.VersionTLS13,
		ServerName:   "redis.production.internal",
	}

	// 4. Inisialisasi Klien Redis dengan Pengguna ACL
	rdb := redis.NewClient(&redis.Options{
		Addr:         "redis.production.internal:6379",
		Username:     "order_service",
		Password:     "Str0ngAuthP@ssw0rd!",
		TLSConfig:    tlsConfig,
		ReadTimeout:  200 * time.Millisecond,
		WriteTimeout: 200 * time.Millisecond,
		PoolSize:     50,
		MinIdleConns: 10,
	})

	return rdb, nil
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	client, err := createSecureRedisClient()
	if err != nil {
		log.Fatalf("Inisialisasi Redis Client gagal: %v", err)
	}
	defer client.Close()

	key := "order:1001"
	err = client.HSet(ctx, key, "status", "PAID", "amount", 450000).Err()
	if err != nil {
		log.Fatalf("Operasi HSET ditolak: %v", err)
	}

	val, err := client.HGetAll(ctx, key).Result()
	if err != nil {
		log.Fatalf("Operasi HGETALL ditolak: %v", err)
	}

	fmt.Printf("Data order terverifikasi: %+v\n", val)
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Insiden Lonjakan Latensi p99 & OOM-Kill di E-Commerce Skala Besar
* **Konteks:** Sistem manajemen sesi dan inventaris e-commerce memproses 180.000 QPS pada jam sibuk (*Flash Sale*). Node Redis memiliki RAM fisik 64 GB.
* **Gejala:** 
  1. Setiap 60 menit, terjadi spike latensi dari 1.5ms menjadi 1800ms.
  2. Akhirnya, proses Redis mati secara mendadak akibat sinyal kernel `SIGKILL` (Out-of-Memory Killer).
* **Investigasi Mendalam (Root Cause Analysis):**
  1. Ditemukan bahwa opsi `save 60 10000` aktif, memaksa operasi `bgsave` setiap jam.
  2. Parameter kernel `transparent_hugepage/enabled` disetel ke `always`.
  3. Saat *child process* mengeksekusi *snapshot*, terjadi mutasi tinggi pada data session induk.
  4. Karena THP aktif, alokasi memori fisik per modifikasi adalah 2 MB (bukan 4 KB). Akibatnya, rasio COW melonjak hingga 34 GB dalam 3 menit.
  5. Penggunaan memori total = 42 GB (Redis Parent) + 34 GB (COW) = 76 GB. Karena melampaui RAM fisik 64 GB tanpa swap, OOM killer mengeliminasi proses parent.
* **Langkah Mitigasi dan Rekayasa Ulang:**
  1. **Kernel Level:**
     ```bash
     echo never > /sys/kernel/mm/transparent_hugepage/enabled
     sysctl -w vm.overcommit_memory=1
     sysctl -w vm.swappiness=1
     ```
  2. **Persistensi:** Nonaktifkan `save` reguler pada instance master. Alihkan pencadangan RDB berkala ke replika sekunder (*read-replica*).
  3. **Konfigurasi Memori Engine:**
     - Turunkan `maxmemory` menjadi `40gb` (menyisakan ruang bebas sebesar 24 GB untuk operasi background dan buffer jaringan).
     - Ganti *eviction policy* ke `volatile-lfu` agar data sesi yang jarang diakses tereliminasi terlebih dahulu secara bertahap sebelum memori mencapai limit absolut.
* **Hasil:** Latensi p99 stabil pada level 0.8ms – 1.2ms, eliminasi total OOM events, dan penurunan alokasi memori COW dari 34 GB menjadi 1.8 GB selama proses sinkronisasi replika.

---

### 9. Trade-offs

```
                       PERFORMANCE / LATENCY
                             /\
                            /  \
                           /    \
                          /      \
                         /        \
   COST EFFICIENCY /    /__________\    SECURITY / DURABILITY
   HIGH DENSITY         (TRADE-OFF)     (TLS, AOF fsync, Strict ACL)
```

| Keputusan Arsitektural | Keuntungan Utama | Kompensasi / Konsekuensi (Trade-off) |
| :--- | :--- | :--- |
| **Enkripsi Transit (mTLS)** | Keamanan paket data end-to-end terjamin; perlindungan terhadap serangan MITM dan inspeksi paket. | Penurunan throughput Redis sekitar 15% - 25% dan peningkatan pemanfaatan CPU akibat proses kriptografi enkripsi/dekripsi paket. |
| **`activedefrag yes`** | Menghindari fragmentasi memori eksternal jangka panjang tanpa perlu me-restart service Redis. | Peningkatan latensi sesaat dan lonjakan siklus CPU jika threshold alokasi diatur terlalu agresif pada saat traffic puncak. |
| **Approximated LFU vs LRU** | Mencegah eliminasi kunci penting yang sering diakses saat terjadi lonjakan data temporer (*burst reads*). | Membutuhkan proses kalibrasi parameter sensitif (`lfu-log-factor` dan `lfu-decay-time`) agar pola akses tercermin akurat. |
| **`maxmemory-samples 10` (vs 5)** | Keputusan eviction mendekati true-LRU teoritis, mengurangi risiko penggusuran data yang keliru (*false evictions*). | Peningkatan tipis pada overhead CPU saat memori mencapai kapasitas penuh dan operasi write sedang berlangsung. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal yang Sering Terjadi:
1. **Membiarkan `vm.overcommit_memory = 0`:** 
   * *Gejala:* Perintah `BGSAVE` atau `BGREWRITEAOF` gagal dieksekusi dengan galat `Can't save in background: fork: Cannot allocate memory`.
   * *Akar Masalah:* Mode overcommit heuristik Linux menolak alokasi memori virtual proses anak karena mengasumsikan kebutuhan RAM akan berlipat ganda penuh, meskipun mekanisme Copy-on-Write hanya memakai sebagian kecil memori.
2. **Penggunaan Wildcard Berbahaya pada Pola Kunci ACL:**
   * Memberikan izin `~*` kepada microservice tertentu membuka celah eksfiltrasi data antar domain bisnis (misalnya modul *payment* dapat membaca data *auth*).
3. **Mengabaikan `INFO memory` - Metrik `mem_fragmentation_ratio`:**
   * Jika rasio > 1.5, sistem mengalami fragmentasi eksternal yang parah (banyak alokasi RAM kosong terkunci di level alokator OS).
   * Jika rasio < 1.0, sistem sedang mengalami *paging out* ke swap disk, yang menyebabkan degradasi performa drastis (*latency spike* ratusan milidetik).

#### Panduan Troubleshooting Operasional

```bash
# 1. Analisis Alokasi Memori Mendalam
redis-cli MEMORY DOCTOR
redis-cli MEMORY STATS

# 2. Identifikasi Latensi Engine
redis-cli LATENCY LATEST
redis-cli LATENCY DOCTOR

# 3. Analisis Perintah Lambat
redis-cli SLOWLOG GET 10

# 4. Deteksi Fragmentasi dan Status Allocator
redis-cli INFO memory | grep -E "used_memory_human|used_memory_rss_human|mem_fragmentation_ratio"
```

---

### 11. Best Practices (Production Checklist)

#### Kernel & OS Level
- [ ] Nonaktifkan Transparent Huge Pages (THP) secara permanen melalui *init system* atau konfigurasi *grub*.
- [ ] Atur parameter kernel `vm.overcommit_memory = 1`.
- [ ] Tentukan `net.core.somaxconn` dan `net.ipv4.tcp_max_syn_backlog` minimal pada angka `65535`.
- [ ] Tetapkan `vm.swappiness = 1` (tetap aktifkan swap kecil sebagai fail-safe agar kernel tidak langsung memicu panik OOM-Kill).

#### Redis Configuration Level
- [ ] Alokasikan `maxmemory` dengan batas aman: maksimal 70% dari kapasitas RAM fisik server.
- [ ] Tentukan kebijakan *eviction* eksplisit (contoh: `volatile-lfu` untuk caching, `noeviction` untuk message broker).
- [ ] Aktifkan `activedefrag` jika beban kerja didominasi oleh operasi update dan delete yang intensif.
- [ ] Ganti nama perintah administratif kritis (*rename-command*) atau isolasi aksesnya menggunakan file ACL khusus:
  ```ini
  rename-command FLUSHALL ""
  rename-command FLUSHDB ""
  rename-command DEBUG ""
  ```

#### Keamanan & Observabilitas
- [ ] Terapkan konfigurasi mTLS untuk seluruh lalu lintas data lintas-node dan koneksi aplikasi.
- [ ] Gunakan pengguna ACL terpisah per aplikasi dengan batasan pola kunci (*key pattern*) yang spesifik.
- [ ] Integrasikan `redis_exporter` dengan Prometheus dan pantau parameter:
  - `redis_connected_clients`
  - `redis_memory_used_bytes` vs `redis_memory_max_bytes`
  - `redis_mem_fragmentation_ratio`
  - `redis_evicted_keys_total`
  - `redis_rejected_connections_total`

---

### 12. Hands-on Practice

Simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`.

#### Langkah 1: Otomasi Konfigurasi Kernel Linux
Buat script sistem tuning: `hands-on/m02/01_kernel_tuning.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[*] Menerapkan Linux Kernel Tuning untuk Redis..."

# 1. Nonaktifkan THP
if test -f /sys/kernel/mm/transparent_hugepage/enabled; then
   echo never > /sys/kernel/mm/transparent_hugepage/enabled
fi
if test -f /sys/kernel/mm/transparent_hugepage/defrag; then
   echo never > /sys/kernel/mm/transparent_hugepage/defrag
fi

# 2. Terapkan konfigurasi sysctl secara persisten
cat << 'EOF' > /etc/sysctl.d/99-redis-performance.conf
vm.overcommit_memory = 1
vm.swappiness = 1
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_keepalive_time = 300
EOF

sysctl --system > /dev/null

echo "[✓] Kernel Tuning berhasil diaplikasikan."
```

#### Langkah 2: Pembuatan Sertifikat mTLS
Simpan script sertifikat: `hands-on/m02/02_generate_tls.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

DIR="hands-on/m02/tls"
mkdir -p "$DIR" && cd "$DIR"

echo "[*] Menyiapkan Mutual TLS PKI..."

# 1. Root CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -sha256 -key ca.key -days 3650 \
  -subj "/C=ID/ST=Jakarta/O=TechOrg/CN=InternalRedisCA" -out ca.crt

# 2. Server Certificate
openssl genrsa -out redis-server.key 2048
openssl req -new -key redis-server.key \
  -subj "/C=ID/ST=Jakarta/O=TechOrg/CN=redis.production.internal" -out redis-server.csr
openssl x509 -req -in redis-server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out redis-server.crt -days 365 -sha256

# 3. Client Certificate
openssl genrsa -out redis-client.key 2048
openssl req -new -key redis-client.key \
  -subj "/C=ID/ST=Jakarta/O=TechOrg/CN=order-service" -out redis-client.csr
openssl x509 -req -in redis-client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out redis-client.crt -days 365 -sha256

echo "[✓] Sertifikat mTLS selesai digenerasi di $DIR"
```

#### Langkah 3: Deployment Redis Enterprise via Docker Compose
Simpan konfigurasi komparatif: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'

services:
  redis-enterprise:
    image: redis:7.2-alpine
    container_name: redis-enterprise-node
    command: [
      "redis-server",
      "/usr/local/etc/redis/redis.conf"
    ]
    ports:
      - "6379:6379"
    volumes:
      - ./redis.conf:/usr/local/etc/redis/redis.conf:ro
      - ./users.acl:/usr/local/etc/redis/users.acl:ro
      - ./tls:/etc/redis/tls:ro
      - redis_data:/data
    sysctls:
      net.core.somaxconn: 65535

  redis-exporter:
    image: oliver006/redis_exporter:v1.55.0-alpine
    container_name: redis-metrics-exporter
    environment:
      - REDIS_ADDR=redis://redis-enterprise:6379
      - REDIS_USER=prometheus_monitor
      - REDIS_PASSWORD=MonitorSuperSecret123!
    ports:
      - "9121:9121"
    depends_on:
      - redis-enterprise

volumes:
  redis_data:
```

---

### 13. Exercise

#### Level Easy
1. Ubah konfigurasi instans Redis runtime agar alokasi batas memori menjadi 512 Megabytes tanpa me-restart service.
2. Identifikasi kunci-kunci yang mengonsumsi memori terbesar menggunakan modul perintah native `MEMORY USAGE`.

#### Level Medium
1. Definisikan pengguna ACL baru bernama `worker_cache` yang hanya memiliki hak akses:
   - Pola kunci `cache:temp:*`
   - Kategori perintah `@read` dan `@write`
   - Larangan mutlak (*blacklisted*) untuk perintah mutasi tipe data list (`LPUSH`, `RPUSH`, `LPOP`).
2. Uji aturan ACL tersebut menggunakan perintah `AUTH` dari `redis-cli` dan catat struktur penolakannya.

#### Level Hard
1. Buat program Go yang menyimulasikan fragmentasi memori aktif:
   - Masukkan 500.000 record dengan ukuran acak (100 byte - 8 KB).
   - Hapus secara acak 70% dari kunci-kunci tersebut.
   - Baca metrik `used_memory`, `used_memory_rss`, dan `mem_fragmentation_ratio` dari `INFO memory`.
   - Picu proses defragmentasi aktif via CLI (`CONFIG SET activedefrag yes`) dan dokumentasikan perubahan kurva rasio fragmentasi hingga nilainya kembali stabil di bawah 1.25.

---

### 14. Challenge

**Skenario Tantangan Produksi:**
Sebuah platform perbankan digital skala nasional sedang memigrasikan sistem transaksi kartunya ke klaster Redis in-memory. Parameter operasional yang wajib dipenuhi:
1. **SLA Latensi:** p99.99 tidak boleh melampaui 3.5ms di bawah beban transaksi 250.000 QPS.
2. **Kepatuhan Regulasi Keuangan:** Semua transmisi jaringan internal wajib terenkripsi menggunakan cipher TLSv1.3 modern dengan validasi identitas mutual (mTLS). Tidak boleh ada transmisi kata sandi terbuka (*plaintext credentials*).
3. **Penyimpanan:** Kapasitas RAM dialokasikan maksimal 32 GB per node, dengan rasio fragmentasi memori (*fragmentation ratio*) tidak boleh melebihi 1.30.

**Tugas Rekayasa Anda:**
Rancang arsitektur implementasi menyeluruh (*end-to-end*) yang memuat konfigurasi kernel Linux, file konfigurasi mesin Redis (`redis.conf`), skema otentikasi multi-tier ACL, dan aturan alarm Prometheus (*Prometheus Alerting Rules*). Skema ini harus mampu mengantisipasi lonjakan beban tanpa memicu *eviction thrashing*, kebocoran memori virtual, ataupun degradasi akibat proses enkripsi TLS.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa alokator default sistem operasi (`glibc malloc`) umumnya digantikan oleh `jemalloc` dalam kompilasi engine Redis?
2. Apa implikasi mendasar bagi klien jika batas `maxmemory` tercapai dan kebijakan diatur ke `noeviction`?
3. Parameter kernel apakah yang jika dibiarkan aktif (*enabled*) dapat melipatgandakan kebutuhan memori fisik secara signifikan saat Redis mengeksekusi proses `BGSAVE`?
4. Perintah native Redis manakah yang digunakan untuk memantau metrik latensi engine secara real-time tanpa membebani performa CPU sever seperti halnya perintah `MONITOR`?
5. Apakah peran dari file `ca.crt` dalam implementasi keamanan Mutual TLS (mTLS) di Redis?

#### B. Pertanyaan Intermediate
1. Jelaskan bagaimana algoritma *Approximated LFU* di Redis merepresentasikan frekuensi dan resensi akses sebuah kunci hanya dalam metadata berukuran 24 bit!
2. Bagaimana mekanisme interaksi antara `used_memory` dan `used_memory_rss` saat mengindikasikan bahwa instans Redis sedang mengalami kondisi *swapping*?
3. Dalam kondisi beban tulis (*write*) tinggi, mengapa pengaturan `vm.overcommit_memory = 1` diwajibkan oleh Redis? Apa yang terjadi jika disetel ke nilai `0`?
4. Sebutkan perbedaan mendasar antara implementasi ACL berbasis `redis.conf` statis dibandingkan menggunakan file eksternal terpisah `aclfile`!
5. Mengapa fitur `activedefrag` membutuhkan ambang batas bawah (`active-defrag-threshold-lower`) dan ambang batas atas (`active-defrag-threshold-upper`), bukan hanya satu nilai ambang absolut?

#### C. Skenario Kasus Produksi
1. **Analisis Skenario 1:**
   Sebuah node Redis 7.0 dengan konfigurasi `maxmemory 16gb` melaporkan `used_memory: 12gb`, namun metrik sistem operasi Linux via `top` menunjukkan `RES` (Resident Memory) proses redis-server telah mencapai `29gb`. Apa yang sedang terjadi pada instans tersebut, apa saja kemungkinan penyebabnya, dan langkah diagnostik sistem apa yang harus diambil?
2. **Analisis Skenario 2:**
   Setelah tim infrastruktur mengaktifkan enkripsi mTLS pada klaster Redis yang menangani 100.000 QPS, terdeteksi kenaikan drastis pada penggunaan satu core CPU hingga menyentuh 100%, disertai lonjakan latensi p99. Mengapa hal ini terjadi pada Redis yang berarsitektur *event-driven*, dan arsitektur mitigasi apa yang perlu diterapkan?
3. **Analisis Skenario 3:**
   Sebuah microservice analitik baru diizinkan membaca data dari Redis cache menggunakan akun ACL terbatas. Namun, beberapa detik setelah microservice tersebut dijalankan, sistem monitoring memicu alarm: p99 latensi seluruh aplikasi lain melonjak dari 1ms ke 400ms secara konsisten, meskipun CPU dan memori Redis masih berada di bawah 40%. Pemeriksaan awal menunjukkan microservice analitik hanya menjalankan perintah baca. Temukan akar masalah perintah yang berpotensi dijalankan oleh microservice tersebut dan bagaimana konfigurasi ACL yang tepat untuk mencegahnya!

---

### Kunci Jawaban & Solusi Quiz

#### Jawaban Basic
1. `jemalloc` dirancang khusus untuk meminimalkan fragmentasi memori eksternal, mendukung manajemen thread-arena yang efisien, mengembalikan memori yang tidak terpakai kembali ke kernel secara lebih terprediksi, dan menyediakan data statistik alokasi memori internal yang detail (`malloc_stats`).
2. Redis akan menolak seluruh perintah penulisan (*write*) atau mutasi data baru yang membutuhkan tambahan memori (mengembalikan pesan galat: `OOM command not allowed when used memory > 'maxmemory'`), namun instans masih dapat melayani permintaan pembacaan (*read*).
3. **Transparent Huge Pages (THP).**
4. Perintah `LATENCY LATEST`, `LATENCY HISTORY`, atau `SLOWLOG GET`.
5. `ca.crt` (Certificate Authority root) bertindak sebagai jangkar kepercayaan (*trust anchor*) yang digunakan oleh Redis server untuk memvalidasi dan memverifikasi keaslian sertifikat publik yang dikirimkan oleh klien penyeru sebelum mengizinkan jabat tangan mTLS terbentuk.

#### Jawaban Intermediate
1. 24-bit dibagi menjadi dua: 16 bit untuk *Last Decrement Time* (LDT) yang menyimpan stempel waktu menit untuk meluruhkan nilai hitungan, dan 8 bit sisanya sebagai *Morris Counter* logaritmik yang menghitung frekuensi akses secara probabilistik (nilai maksimal 255 mewakili hingga jutaan akses aktual).
2. Jika `used_memory_rss` lebih kecil daripada `used_memory` (dan `mem_fragmentation_ratio < 1.0`), artinya sebagian memori fisik Redis telah dipindahkan keluar (*paged out*) dari RAM fisik ke disk *swap space* oleh kernel Linux, yang menandakan terjadinya saturasi memori sistem.
3. Nilai `0` memaksa kernel mengevaluasi ketersediaan memori saat pemanggilan `fork()` menggunakan heuristik ketat. Jika alokasi proses virtual dianggap melebihi ruang bebas, `fork()` akan ditolak dengan error `Cannot allocate memory`. Nilai `1` menginstruksikan kernel untuk selalu mengizinkan overcommit, sehingga proses background child dapat langsung diinisiasi di bawah asumsi mekanisme Copy-on-Write.
4. Menggunakan `aclfile` memungkinkan perubahan ACL yang dimodifikasi melalui perintah runtime (`ACL SETUSER`, `ACL SAVE`) disimpan secara persisten langsung ke file konfigurasi tanpa me-restart server Redis. Sebaliknya, modifikasi ACL di dalam `redis.conf` tidak dapat ditimpa secara atomik saat runtime melalui perintah `ACL SAVE`.
5. Pendekatan dua ambang batas (*lower* dan *upper*) digunakan untuk menerapkan mekanisme kerja dinamis: proses defragmentasi hanya dimulai dengan konsumsi CPU rendah (misal: 5%) saat fragmentasi menyentuh batas bawah, lalu secara bertahap meningkatkan alokasi siklus CPU hingga mencapai persentase siklus maksimal (misal: 50%) seiring fragmentasi mendekati ambang batas atas. Ini mencegah defragmentasi membebani CPU secara agresif pada tahap awal.

#### Jawaban Skenario Kasus Produksi
1. **Analisis Skenario 1:**
   - *Penyebab:* Terjadi fragmentasi eksternal memori yang ekstrem (`mem_fragmentation_ratio > 2.0`), atau Redis memegang banyak alokasi struktur data I/O buffer besar (misalnya `client query buffer` atau `output buffer` akibat adanya koneksi klien lambat yang mengeksekusi query besar).
   - *Langkah Diagnostik:*
     1. Jalankan `redis-cli INFO memory` untuk memeriksa rasio `mem_fragmentation_ratio`, alokasi `clientbuf_normal`, dan `clientbuf_pubsub`.
     2. Jalankan `redis-cli CLIENT LIST` dan sortir berdasarkan kolom `omem` (output buffer memory) dan `qbuf` (query buffer) untuk menemukan koneksi klien yang menahan buffer data.
     3. Jalankan `redis-cli MEMORY DOCTOR` untuk melihat rekomendasi otomatis dari engine.
     4. Jika terbukti fragmentasi eksternal murni, aktifkan `activedefrag yes`.
2. **Analisis Skenario 2:**
   - *Penyebab:* Proses *cryptographic handshake* TLS dan operasi enkripsi/dekripsi stream data merupakan komputasi CPU intensif. Karena Redis memproses koneksi jaringan dan perintah utama di dalam single-threaded loop (atau thread I/O terbatas), beban TLS menempati siklus core CPU tersebut, sehingga timbul fenomena *head-of-line blocking* pada pemrosesan antrean perintah reguler.
   - *Mitigasi Arsitektur:*
     1. Konfigurasi Threaded I/O untuk penanganan operasi baca-tulis socket jaringan: `io-threads 4` dan `io-threads-do-reads yes`.
     2. Gunakan *TLS Session Resumption* atau *TLS Session Tickets* pada level klien untuk meminimalkan beban komputasi handshake penuh (*full handshake*).
     3. Alternatif arsitektur: Gunakan arsitektur TLS Termination Proxy lokal berkinerja tinggi (seperti Envoy atau HAProxy) di depan Redis node, terhubung ke Redis lokal via UNIX Domain Socket (UDS) atau loopback interface.
3. **Analisis Skenario 3:**
   - *Penyebab:* Microservice analitik kemungkinan mengeksekusi operasi pembacaan yang memblokir engine (*blocking read commands*), seperti memanggil perintah `KEYS *`, `HGETALL` pada hash raksasa, atau `SMEMBERS` pada set beranggotakan jutaan elemen. Karena Redis bersifat single-threaded dalam eksekusi data perintah, perintah $O(N)$ ini menahan pemrosesan antrean seluruh klien lain selama ratusan milidetik.
   - *Mitigasi & Hardening ACL:*
     1. Cek riwayat eksekusi melalui `redis-cli SLOWLOG GET 5` untuk menangkap nama perintah dan waktu eksekusinya.
     2. Modifikasi ACL pengguna microservice analitik tersebut agar perintah berbahaya seperti `KEYS` diblokir total, serta ganti pola baca aplikasi ke mode pagination berbasis kursor:
        ```text
        ACL SETUSER analytics_service -keys +scan +hscan +sscan
        ```
     3. Terapkan konfigurasi `rename-command KEYS ""` di level engine instance jika perintah tersebut memang tidak diizinkan untuk seluruh layanan.

---

### 16. Summary

Pengelolaan Redis pada beban kerja produksi berskala enterprise memerlukan pemahaman komprehensif melampaui manipulasi struktur data di tingkat aplikasi. Redis beroperasi sebagai sistem yang sangat bergantung pada karakteristik memori dan kernel Linux yang mendasarinya. 

Tata kelola memori yang optimal menuntut keseimbangan antara kapasitas memori fisik, mekanisme alokasi non-linear dari `jemalloc`, perilaku *Copy-on-Write* pada proses `fork()`, serta pemilihan strategi *eviction* (LRU/LFU) yang disesuaikan secara presisi dengan karakteristik data.

Penerapan keamanan modern menuntut penghapusan paradigma perimeter statis masa lalu. Dengan mengintegrasikan sistem autentikasi berbasis ACL v2 yang menerapkan prinsip *least-privilege*, bersama enkripsi Mutual TLS (mTLS) dan penonaktifan perintah administratif berbahaya, Redis dapat dioperasikan secara andal di lingkungan multi-tenant dan cloud-native. 

Seluruh konfigurasi ini wajib ditopang oleh fondasi sistem operasi yang kokoh—menonaktifkan *Transparent Huge Pages* (THP), mengizinkan *overcommit memory*, dan mengoptimalkan antrean soket jaringan kernel—serta dipantau secara kontinu menggunakan instrumen observabilitas native dan telemetri metrik Prometheus. Melalui kombinasi praktik rekayasa ini, sistem Redis dapat mencapai performa throughput tinggi dengan latensi sub-milidetik secara konsisten, aman, dan tanpa gangguan operasional.