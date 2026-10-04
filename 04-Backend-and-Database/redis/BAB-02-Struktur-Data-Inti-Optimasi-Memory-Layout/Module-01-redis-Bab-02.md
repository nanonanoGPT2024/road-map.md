# Bab 02 Module 01: Struktur Data Inti & Optimasi Memory Layout

---

## 01 Identitas Modul
* **Track:** 04-Backend-and-Database
* **Course:** Redis Core Engineering & Architecture
* **Module:** Bab 02 Module 01
* **Judul:** Struktur Data Inti & Optimasi Memory Layout
* **Prasyarat:** Pemahaman arsitektur sistem operasi (virtual memory, page allocation), dasar protokol TCP/IP, dan kemahiran dalam Go (v1.21+) serta C dasar.
* **Tingkat Kesulitan:** Intermediate to Advanced
* **Estimasi Waktu:** 180 Menit

---

## 02 Learning Objectives
1. Menganalisis representasi internal *in-memory* dari struktur data Redis (`robj`, `sds`, `dict`, `skiplist`, `ziplist`/`listpack`).
2. Mengkonfigurasi dan merekayasa ambang batas (*threshold*) encoding memori untuk menekan alokasi heap via jemalloc.
3. Mengukur konsumsi memori dan fragmentasi rasio secara deterministik menggunakan perintah analitik (`MEMORY USAGE`, `DEBUG OBJECT`, `MEMORY MALLOC-STATS`).
4. Mengimplementasikan teknik kompresi struktural pada level aplikasi untuk dataset skala multi-gigabyte.

---

## 03 Concept Map Diagram ASCII

```text
+-----------------------------------------------------------------------------------+
|                              REDIS OBJECT (robj)                                  |
|   type: 4 bits | encoding: 4 bits | lru/lfu: 24 bits | refcount: 4B | ptr: 8B     |
+-----------------------------------------------------------------------------------+
                                         |
     +-----------------+-----------------+-----------------+-----------------+
     |                 |                 |                 |                 |
     v                 v                 v                 v                 v
+---------+       +---------+       +---------+       +---------+       +---------+
| STRING  |       |  LIST   |       |  HASH   |       |   SET   |       |  ZSET   |
+---------+       +---------+       +---------+       +---------+       +---------+
     |                 |                 |                 |                 |
 [OBJ_ENCODING]   [OBJ_ENCODING]    [OBJ_ENCODING]    [OBJ_ENCODING]    [OBJ_ENCODING]
     |                 |                 |                 |                 |
     +-> INT           +-> LISTPACK      +-> LISTPACK      +-> INTSET        +-> LISTPACK
     +-> EMBSTR        +-> QUICKLIST     +-> HT (Dict)     +-> HT (Dict)     +-> SKIPLIST
     +-> RAW                                                                     + Dict
```

---

## 04 Mengapa Relevan
Redis menyimpan seluruh set data aktif di dalam RAM. Efisiensi representasi bit dan byte per entry secara langsung menentukan total cost of ownership (TCO) infrastruktur. Kesalahan pemilihan tipe data dan pengabaian internal encoding dapat memicu overhead pointer hingga 400% lebih besar daripada payload aktual, yang berakibat pada:
* Degradasi performa akibat CPU cache-miss (*L1/L2/L3 cache misses*).
* Lonjakan memori yang memicu Linux Out-Of-Memory (OOM) Killer.
* Tingginya jeda I/O saat proses fork snapshotting (RDB) dan replication sync.

---

## 05 Anatomi Konsep Inti

### 1. Redis Object Layer (`redisObject` / `robj`)
Setiap entitas key-value dalam Redis dibungkus dalam struct `robj` berukuran 16 byte:
```c
struct redisObject {
    unsigned type:4;        // Tipe data (OBJ_STRING, OBJ_LIST, dll.)
    unsigned encoding:4;    // Representasi fisik (OBJ_ENCODING_RAW, LISTPACK, dll.)
    unsigned lru:24;        // Metadata LRU clock / LFU data
    int refcount;           // Reference counter (4 bytes)
    void *ptr;              // Pointer ke memory payload aktual (8 bytes)
};
```

### 2. SDS (Simple Dynamic Strings)
Pengganti string standar C (`char*`) yang binary-safe, terhindar dari buffer overflow, dan memiliki akses $O(1)$ length:
* `sdshdr5`, `sdshdr8`, `sdshdr16`, `sdshdr32`, `sdshdr64`.
* **EMBSTR** mengalokasikan `robj` dan `sdshdr` dalam satu chunk memori berurutan (single `malloc` call, $\le 44$ bytes).
* **RAW** memisahkan alokasi `robj` dan `sdshdr` (dua `malloc` calls, $> 44$ bytes).

### 3. Listpack (Modern Memory Optimization)
Struktur data sekuensial linear kontinu di memori tanpa pointer traversal, menggantikan `ziplist` untuk memitigasi *cascading-update problem*. Digunakan oleh Hash, ZSet, dan List pada kapasitas data kecil (`entries <= threshold`).

### 4. Hash Table (`dict`) & Rehash
Implementasi hash table berbasis array bucket dinamis. Jika membesar melebihi `hash-max-listpack-entries`, struktur diubah menjadi `dict` dengan pointer overhead per entry sebesar ~24-32 bytes. Redis melakukan *incremental rehashing* untuk mendistribusikan beban migrasi bucket.

---

## 06 Panduan Implementasi Step-by-Step

### Optimasi Konfigurasi Runtime (`redis.conf`)
Jalankan konfigurasi berikut untuk memaksimalkan densitas kompresi berbasis struktur contiguous memory:

```ini
# Meningkatkan ambang batas listpack sebelum bermutasi ke Dictionary / Skiplist
hash-max-listpack-entries 1024
hash-max-listpack-value 128

zset-max-listpack-entries 512
zset-max-listpack-value 64

set-max-intset-entries 1024

# Quicklist compression depth (List)
list-max-listpack-size -2
list-compress-depth 1
```

Eksekusi via Redis CLI untuk verifikasi dinamis:
```bash
redis-cli CONFIG SET hash-max-listpack-entries 1024
redis-cli CONFIG SET hash-max-listpack-value 128
```

---

## 07 Contoh Kasus Sederhana

Membandingkan konsumsi memori antara String terfragmentasi dengan Kompaksi Hash Struct:

```bash
# Skenario 1: Flat String (Boros Memori: 1.000.000 key = 1.000.000 robj + SDS overhead)
# SET user:1000:name "Budi"
# SET user:1000:email "budi@domain.id"

# Skenario 2: Optimized Hash Bucket (Hemat Memori: 1 robj listpack per bucket)
# User ID 1000 -> Bucket ID = 1000 / 100 = 10
HSET user:bucket:10 1000:name "Budi" 1000:email "budi@domain.id"

# Analisis Encoding
OBJECT ENCODING user:bucket:10
# Output: listpack
```

---

## 08 Implementasi Production-Grade Lengkap Kode

Implementasi client-side Go library untuk **Transparent Hash Sharding Engine** yang otomatis mengubah flat key-value pairs ke compact Listpack buckets secara deterministik.

```go
// package main: Memory-Optimized Key-Value Storage using Redis Hash Sharding
package main

import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

type CompactStore struct {
	client     *redis.Client
	bucketMask uint32
}

func NewCompactStore(client *redis.Client, numBuckets uint32) *CompactStore {
	return &CompactStore{
		client:     client,
		bucketMask: numBuckets - 1,
	}
}

func (c *CompactStore) getBucketKey(key string) (string, string) {
	h := sha256.Sum256([]byte(key))
	val := binary.BigEndian.Uint32(h[0:4])
	bucketID := val & c.bucketMask
	return fmt.Sprintf("hsh:bkt:%d", bucketID), key
}

func (c *CompactStore) Set(ctx context.Context, key string, value string) error {
	bucketKey, field := c.getBucketKey(key)
	return c.client.HSet(ctx, bucketKey, field, value).Err()
}

func (c *CompactStore) Get(ctx context.Context, key string) (string, error) {
	bucketKey, field := c.getBucketKey(key)
	return c.client.HGet(ctx, bucketKey, field).Result()
}

func main() {
	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{
		Addr:         "localhost:6379",
		Password:     "",
		DB:           0,
		PoolSize:     50,
		MinIdleConns: 10,
		ReadTimeout:  200 * time.Millisecond,
		WriteTimeout: 200 * time.Millisecond,
	})

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Gagal terhubung ke Redis: %v", err)
	}

	// Gunakan 1024 bucket (pastikan bernilai perpangkatan 2)
	store := NewCompactStore(rdb, 1024)

	// Simpan data
	testKey := "session:token:usr_01HTJYZ32"
	testVal := "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"

	if err := store.Set(ctx, testKey, testVal); err != nil {
		log.Fatalf("Gagal menulis ke store: %v", err)
	}

	// Ambil data
	retrieved, err := store.Get(ctx, testKey)
	if err != nil {
		log.Fatalf("Gagal membaca dari store: %v", err)
	}

	fmt.Printf("Key [%s] berhasil dimuat: %s\n", testKey, retrieved)

	// Validasi representasi encoding internal
	bucketKey, _ := store.getBucketKey(testKey)
	encoding, err := rdb.ObjectEncoding(ctx, bucketKey).Result()
	if err != nil {
		log.Fatalf("Gagal mengambil encoding: %v", err)
	}
	fmt.Printf("Redis Bucket [%s] Internal Encoding: %s\n", bucketKey, encoding)
}
```

---

## 09 Diagram Alur Kerja ASCII

```text
[Aplikasi Menulis Key:Value]
             |
             v
[Algoritma Hashing Client (SHA256)]
             |
             +---> [Hitung Bucket Index: Hash(Key) & Mask]
             |
             v
[Kirim Perintah HSET hsh:bkt:<id> <key> <val>]
             |
             v
+----------------------- Redis Server Engine ------------------------+
|                                                                    |
|  Apakah elemen hash > hash-max-listpack-entries                    |
|  ATAU panjang value > hash-max-listpack-value?                     |
|                                                                    |
|               +-----------------+-----------------+                |
|               | Ya                                | Tidak          |
|               v                                   v                |
|      [Tipe: OBJ_ENCODING_HT]           [Tipe: OBJ_ENCODING_LISTPACK]|
|      - Menggunakan Dict pointers       - Contiguous byte array     |
|      - Overhead ~32 bytes/field        - Overhead minimum 1 byte   |
|      - CPU Cache Miss Tinggi           - L1/L2 Cache Friendly      |
+--------------------------------------------------------------------+
```

---

## 10 Analisis Trade-offs

| Dimensi | String Biasa (`SET`) | Sharded Hash Compact (`HSET` Listpack) |
| :--- | :--- | :--- |
| **Konsumsi Memori (10M keys)** | ~1.1 GB - 1.5 GB | ~200 MB - 300 MB |
| **Time Complexity Read/Write** | $O(1)$ deterministik | $O(1)$ amortized + $O(N)$ scanning di CPU cache ($N \le 1024$) |
| **Granular Key Eviction / TTL** | Mendukung native TTL per key | TTL hanya bisa dipasang pada level bucket |
| **Kompleksitas Aplikasi** | Sangat Rendah (Native K-V) | Menengah (Perlu abstraction layer di client) |
| **Dampak CPU Latency** | Rendah | Sedikit meningkat saat decoding byte listpack |

---

## 11 Best Practices & Antipatterns

### Best Practices
* **Keep Payload $\le 44$ bytes** jika menggunakan plain string untuk menjaga alokasi tetap pada encoding `EMBSTR`.
* **Normalisasi Key Naming:** Jangan gunakan namespace terlalu panjang (contoh buruk: `production:indonesia:jakarta:service:ecommerce:user:123`, ubah menjadi `usr:123`).
* **Kombinasikan Bitmaps / IntSet** untuk filtering status ID bilangan bulat.

### Antipatterns
* Menyimpan ribuan JSON string flat berukuran mini ($<100$ bytes) menggunakan perintah `SET` mandiri.
* Membiarkan ukuran array/hash tumbuh secara tidak terkontrol (melewati batas `max-listpack`), menyebabkan mutasi spontan ke struktur pointer (`dict` / `skiplist`) dan mendegradasi throughput.

---

## 12 Security Hardening
1. **Disable Dangerous Commands:** Nonaktifkan perintah inspeksi memori berbiaya tinggi di lingkungan produksi yang berpotensi memblokir single thread.
   ```text
   rename-command DEBUG ""
   rename-command KEYS ""
   ```
2. **Restrict Memory Introspection:** Perintah `MEMORY USAGE` memiliki kompleksitas waktu $O(N)$. Batasi akses execution role menggunakan Redis ACL:
   ```text
   ACL SETUSER app-service on >SecretPass123! ~hsh:bkt:* +@read +@write -MEMORY -DEBUG
   ```

---

## 13 Observabilitas & Debugging

Gunakan sub-perintah `MEMORY` dan `OBJECT` untuk mendiagnosis tata letak memori:

```bash
# 1. Cek tipe encoding memori
OBJECT ENCODING hsh:bkt:102

# 2. Analisis rincian konsumsi memori key spesifik (dalam byte)
MEMORY USAGE hsh:bkt:102 SAMPLES 0

# 3. Inspeksi metadata internal jemalloc
MEMORY MALLOC-STATS

# 4. Mendeteksi fragmentasi global
INFO memory
# Evaluasi nilai: mem_fragmentation_ratio
# Nilai > 1.5 menandakan fragmentasi parah; < 1.0 menandakan paging/swapping
```

---

## 14 Benchmarking & Performance

Jalankan uji komparasi throughput dan alokasi memori menggunakan `redis-benchmark`:

```bash
# Skenario A: Benchmarking Flat String Keys
redis-benchmark -t set -n 1000000 -r 1000000 -d 32 -c 50 -q

# Skenario B: Benchmarking HSET pada Sharded Bucket
redis-benchmark -n 1000000 -r 1024 -c 50 -q HSET hsh:bkt:__rand_int__ field_val 32bytespayloadhere___________123
```

**Target Eksekusi Metrik:**
* Latency $p99 \le 1.2\text{ ms}$ pada kedua skenario.
* Skenario B menghemat penggunaan RAM $\ge 65\%$ berdasarkan pembacaan `used_memory` di `INFO memory`.

---

## 15 Hands-on Lab Mini-Project

### Skenario
Rancang pipeline migrasi cache session pengguna sebanyak 100.000 entry dari implementasi flat string ke compact listpack hash.

### Direktori & File Eksekusi
```bash
mkdir -p redis-memory-lab && cd redis-memory-lab
go mod init redis-memory-lab
go get github.com/redis/go-redis/v9
```

### Lab Script (`lab_migration.go`)
```go
package main

import (
	"context"
	"fmt"
	"log"
	"runtime"
	"time"

	"github.com/redis/go-redis/v9"
)

const TotalRecords = 100_000

func main() {
	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
	rdb.FlushDB(ctx)

	// Tahap 1: Injeksi Format Flat String
	start := time.Now()
	pipe := rdb.Pipeline()
	for i := 0; i < TotalRecords; i++ {
		pipe.Set(ctx, fmt.Sprintf("sess:flat:%d", i), "token_val_abc123xyz", 0)
		if i%5000 == 0 {
			_, _ = pipe.Exec(ctx)
		}
	}
	_, _ = pipe.Exec(ctx)
	
	info1, _ := rdb.Info(ctx, "memory").Result()
	log.Printf("Flat Strings Selesai dimuat dalam %v", time.Since(start))

	// Bersihkan DB untuk komparasi murni
	rdb.FlushDB(ctx)
	runtime.GC()

	// Tahap 2: Injeksi Format Compact Hash (1000 bucket)
	start = time.Now()
	pipe = rdb.Pipeline()
	for i := 0; i < TotalRecords; i++ {
		bkt := i % 1000
		pipe.HSet(ctx, fmt.Sprintf("sess:compact:%d", bkt), fmt.Sprintf("u:%d", i), "token_val_abc123xyz")
		if i%5000 == 0 {
			_, _ = pipe.Exec(ctx)
		}
	}
	_, _ = pipe.Exec(ctx)
	log.Printf("Compact Sharded Hash Selesai dimuat dalam %v", time.Since(start))
	
	info2, _ := rdb.Info(ctx, "memory").Result()

	fmt.Println("--- PERBANDINGAN PENGGUNAAN MEMORI ---")
	fmt.Println("Gunakan redis-cli INFO memory untuk memverifikasi selisih used_memory_human.")
	_ = info1
	_ = info2
}
```

---

## 16 Automated Testing & Verification

File pengujian deterministik (`store_test.go`):

```go
package main

import (
	"context"
	"testing"

	"github.com/redis/go-redis/v9"
)

func TestCompactStoreEncoding(t *testing.T) {
	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
	defer rdb.Close()

	store := NewCompactStore(rdb, 16)
	testKey := "user:session:99"
	testVal := "active_authenticated"

	if err := store.Set(ctx, testKey, testVal); err != nil {
		t.Fatalf("Expected nil, got %v", err)
	}

	val, err := store.Get(ctx, testKey)
	if err != nil || val != testVal {
		t.Fatalf("Expected %s, got %s (err: %v)", testVal, val, err)
	}

	bucketKey, _ := store.getBucketKey(testKey)
	enc, err := rdb.ObjectEncoding(ctx, bucketKey).Result()
	if err != nil {
		t.Fatalf("Gagal mengambil encoding: %v", err)
	}

	// Validasi bahwa optimasi listpack bekerja
	if enc != "listpack" {
		t.Errorf("Ekspektasi encoding 'listpack', tetapi diperoleh '%s'", enc)
	}
}
```

Eksekusi:
```bash
go test -v -run TestCompactStoreEncoding
```

---

## 17 Troubleshooting Guide

| Gejala Masalah | Investigasi | Solusi Remediasi |
| :--- | :--- | :--- |
| Perintah `HSET` menjadi lambat, CPU $100\%$. | Jalankan `OBJECT ENCODING <key>`. Jika `hashtable`, periksa ukuran hash. | Batasi item per hash agar tidak melewati batas konfigurasi. Turunkan nilai `hash-max-listpack-entries`. |
| `mem_fragmentation_ratio` $> 1.8$. | Periksa `INFO memory`. Alokator jemalloc menahan page yang telah di-*free*. | Aktifkan background defragmentation: `CONFIG SET activedefrag yes`. |
| Mutasi spontan string ke `RAW`. | String dimodifikasi melebihi batas 44 bytes via `APPEND` atau *in-place modification*. | Hindari penggabungan string server-side jika ingin mempertahankan struktur alokasi `EMBSTR`. |

---

## 18 Checklist Produksi
- [ ] Atur konfigurasi `hash-max-listpack-entries` dan `zset-max-listpack-entries` sesuai batas toleransi CPU L1/L2 cache target host.
- [ ] Verifikasi bahwa client library menggunakan single continuous connection pool tanpa memory leaks di goroutine.
- [ ] Aktifkan `activedefrag yes` di instans dengan volume write/update tinggi.
- [ ] Pasang alerting threshold jika `mem_fragmentation_ratio` $< 0.9$ (indikasi swapping) atau $> 1.6$.
- [ ] Audit skema key naming untuk memastikan overhead prefix string seminimal mungkin.

---

## 19 Ringkasan Eksekutif
* Struktur objek internal Redis (`robj`) menyumbang overhead tetap sebesar 16 byte di luar payload aktual; optimasi memori berfokus pada reduksi jumlah `robj` per entitas data.
* Encoding sekuensial contiguous (`listpack`, `intset`, `embstr`) mengeliminasi *pointer overhead* dan memaksimalkan *CPU memory locality*.
* Pengelompokan flat key-value pairs ke dalam *sharded compact hash* secara konsisten mampu menekan footprint memori RAM hingga $60\text{--}80\%$ tanpa menurunkan latensi operasi $O(1)$.

---

## 20 Referensi & Bacaan Lanjutan
* Antirez (Salvatore Sanfilippo). *Redis internals: sds, ziplist and listpack evolution.*
* Redis Documentation: *Memory Optimization Specification (Official Docs).*
* jemalloc Architecture Guide: *Scalable Memory Allocation.*
* Cormen, Leiserson, Rivest, Stein. *Introduction to Algorithms: Skip Lists and Hash Tables.*