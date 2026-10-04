# Module 02: Deep Dive Struktur Data Inti, Memory Layout, & Optimasi Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis layout memori internal Redis hingga level byte, termasuk struktur `redisObject`, Simple Dynamic Strings (SDS), Listpack, Intset, Quicklist, Dict, dan Skiplist.
- Mengidentifikasi mekanisme alokasi memori jemalloc (*arenas*, *bins*, *chunks*) serta penyebab utama *external* dan *internal memory fragmentation*.
- Mengimplementasikan pola optimasi *memory density* tingkat lanjut seperti *hash bucketization* untuk mereduksi *memory footprint* hingga lebih dari 70% di lingkungan berskala terabita (*terabyte-scale*).
- Mengonfigurasi dan mengoperasikan *Active Defragmentation Engine* tanpa menimbulkan degradasi *latency* pada *throughput* tinggi ($>100\text{k RPS}$).
- Melakukan audit performa dan profil konsumsi RAM menggunakan native tooling Redis (`MEMORY USAGE`, `MEMORY DOCTOR`, Jemalloc profiling) secara presisi.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
- Arsitektur *single-threaded event loop* Redis (AE Library) dan Non-blocking I/O (epoll/kqueue).
- Konsep dasar struktur data dasar C: *pointer*, *struct padding*, *alignment boundaries*, dan representasi biner memori.
- Konsep Virtual Memory, Anonymous Pages, Swap, dan *Operating System Page Cache* pada Linux Kernel.
- Pemahaman dasar perintah Redis CLI: manipulasi String, Hash, List, Set, dan Sorted Set.

---

## 3. Concept & Internal Architecture

Redis sering disalahartikan hanya sebagai *key-value store* sederhana berbasis teks. Secara arsitektural, Redis adalah sebuah *data structure server* in-memory dengan kontrol memori tingkat rendah (*low-level byte packing*) yang sangat ketat untuk meminimalkan *overhead* pointer C standard.

```
                    +------------------------------------+
                    |        redisObject (16 bytes)      |
                    |  - type: 4 bits                    |
                    |  - encoding: 4 bits                |
                    |  - lru/lfu: 24 bits                |
                    |  - refcount: 32 bits               |
                    |  - *ptr: 64 bits (pointer ke data) |
                    +-----------------+------------------+
                                      |
              +-----------------------+-----------------------+
              | (raw / embstr)                                | (ziplist / listpack / intset)
              v                                               v
+-------------------------------+             +----------------------------------+
|      SDS (sdshdr8 - 3 bytes)  |             |      Listpack Flat Byte Array    |
|  - len: uint8_t (1 byte)      |             |  - <total_bytes> (4 bytes)       |
|  - alloc: uint8_t (1 byte)    |             |  - <num_elements> (2 bytes)      |
|  - flags: uint8_t (1 byte)    |             |  - Entry 1 (len + payload + len) |
|  - buf[]: byte string + '\0'  |             |  - Entry 2 ...                   |
+-------------------------------+             |  - 0xFF (End marker, 1 byte)     |
                                              +----------------------------------+
```

### 3.1 The `redisObject` Structure
Setiap key dan value yang disimpan di dalam Redis dibungkus oleh struct `redisObject`. Definisi struct pada Redis source code (`server.h`):

```c
struct redisObject {
    unsigned type:4;       // 4 bits: OBJ_STRING, OBJ_LIST, OBJ_SET, OBJ_ZSET, OBJ_HASH
    unsigned encoding:4;   // 4 bits: OBJ_ENCODING_RAW, OBJ_ENCODING_EMBSTR, OBJ_ENCODING_HT, dll.
    unsigned lru:24;       // 24 bits: LRU clock timestamp atau LFU counter
    int refcount;          // 4 bytes (32 bits): Reference counting untuk shared objects
    void *ptr;             // 8 bytes (64 bits): Pointer ke payload aktual
}; // Total ukuran = 4 + 4 + 24 bits + 4 bytes + 8 bytes = 16 bytes.
```
Setiap *key-value pair* setidaknya mengorbankan **16 bytes** hanya untuk metadata `redisObject`, belum termasuk struct `dictEntry` (24-32 bytes) dari hash table global Redis dan overhead jemalloc.

---

### 3.2 Simple Dynamic String (SDS)
Redis tidak menggunakan string standar bahasa C (`char*` terminated by `\0`) karena C string tidak *binary-safe*, membutuhkan $O(N)$ untuk kalkulasi panjang string, dan rentan terhadap *buffer overflow*. Redis mengimplementasikan **SDS**.

Pada Redis 7.x, header SDS dipecah menjadi 5 tipe (`sdshdr5`, `sdshdr8`, `sdshdr16`, `sdshdr32`, `sdshdr64`) untuk menghemat memori berdasarkan panjang payload:

```c
struct __attribute__ ((__packed__)) sdshdr8 {
    uint8_t len;         // 1 byte: Jumlah bytes terpakai
    uint8_t alloc;       // 1 byte: Total alokasi memori (tidak termasuk header dan null-terminator)
    unsigned char flags; // 1 byte: 3 bit terbawah mendefinisikan tipe (sdshdr8), 5 bit cadangan
    char buf[];          // Flexible array member: payload data + '\0'
};
```
Karakteristik SDS:
- **Binary-Safe**: Membaca string berdasarkan properti `len`, bukan byte terminasi `\0`. Redis dapat menyimpan citra terkompresi, protobuf, atau byte mentah.
- **O(1) String Length**: Pembacaan panjang string selalu instan.
- **Pre-allocation & Lazy Freeing**: Menghindari *system call* alokasi ulang berulang kali saat melakukan `APPEND`.

#### String Encodings: `int`, `embstr`, dan `raw`
1. **`int`**: Jika string bernilai numerik integer 64-bit yang dapat diparsing, Redis tidak mengalokasikan SDS. Nilai integer disimpan langsung di dalam pointer `void *ptr` dari `redisObject` (8 byte).
2. **`embstr`**: Untuk string dengan panjang $\le 44\text{ bytes}$. Redis mengalokasikan struct `redisObject` dan struct `sdshdr8` dalam **satu blok memori kontinu** via jemalloc:
   $$\text{redisObject (16 bytes)} + \text{sdshdr8 (3 bytes)} + \text{payload (maks 44 bytes)} + \text{null-term (1 byte)} = 64\text{ bytes}$$
   Angka **64 bytes** ini merupakan ukuran satu *CPU Cache Line* dan ukuran satu *bin* alokasi jemalloc, memaksimalkan efisiensi *CPU L1/L2 cache locality* dan zero pointer-chasing.
3. **`raw`**: Digunakan jika panjang string $> 44\text{ bytes}$. Redis melakukan **dua kali alokasi terpisah**: alokasi pertama untuk `redisObject`, dan alokasi kedua untuk struct `sdshdr*` beserta buffernya. Pointer `*ptr` menunjuk ke alamat alokasi kedua.

---

### 3.3 Listpack (Pengganti Ziplist di Redis 7+)
Historisnya, Redis menggunakan `ziplist` untuk memadatkan Hash, List, dan Sorted Set. Namun, `ziplist` rentan terhadap masalah fatal: **Cascading Updates** (di mana modifikasi satu entry memicu pergeseran offset semua entry berikutnya secara rekursif). Sejak Redis 7.0, `ziplist` sepenuhnya digantikan oleh **Listpack**.

Listpack adalah array biner padat serial tanpa pointer C. Layout byte Listpack:
```
<total_bytes: 4B> <num_elements: 2B> <entry-1> <entry-2> ... <entry-N> <0xFF: 1B>
```
Struktur setiap entry dalam Listpack:
```
+------------------+-----------------------------+-----------------------+
|  encoding-type   |       element-data          |   backlen (1-5 bytes) |
+------------------+-----------------------------+-----------------------+
```
`backlen` menyimpan panjang entry tersebut (tidak termasuk `backlen` itu sendiri). Desain brilian ini memungkinkan iterasi bolak-balik (dari kiri ke kanan maupun kanan ke kiri) **tanpa** menyimpan ukuran entry sebelumnya, sehingga menghapus fenomena *cascading update*.

---

### 3.4 Quicklist
Tipe data Redis `List` (misal: `LPUSH`, `RPUSH`) diimplementasikan menggunakan **Quicklist**.
Quicklist adalah linked list dua arah (*doubly linked list*) yang node-nodenya bukan berupa elemen individual, melainkan sebuah **Listpack**. 

```
[Quicklist Node 1: Listpack] <---> [Quicklist Node 2: Listpack] <---> [Quicklist Node 3: Listpack]
     (Contains N elements)               (Contains N elements)               (Contains N elements)
```
Tujuannya adalah menyeimbangkan efisiensi memori dari struktur data padat (*sequential memory listpack*) dengan fleksibilitas manipulasi modifikasi linked list ($O(1)$ push/pop di head dan tail) tanpa overhead fragmentasi masif.

---

### 3.5 Dict (Hash Table)
Struktur Hash Table Redis menggunakan teknik *incremental rehashing*. 
Definisi struct:
```c
struct dict {
    dictType *type;
    dictEntry **ht_table[2]; // Dua hash table untuk keperluan incremental rehashing
    unsigned long ht_used[2];
    long rehashidx;          // bernilai -1 jika tidak sedang rehashing
    int16_t pauserehash;
};
```
Struktur node entry:
```c
struct dictEntry {
    void *key;
    union {
        void *val;
        uint64_t u64;
        int64_t s64;
        double d;
    } v;
    struct dictEntry *next;  // Chaining bucket collision resolution
}; // Total ukuran = 8 + 8 + 8 = 24 bytes (pada arsitektur 64-bit)
```
Saat rehashing terjadi, elemen dipindahkan secara bertahap setiap kali operasi pembacaan/penulisan dipanggil, atau via cron task server, mencegah CPU spike yang membekukan request klien.

---

### 3.6 Intset
Jika Redis Set (`SADD`) seluruh anggotanya merupakan bilangan bulat (*integers*) bertanda dan jumlahnya di bawah ambang batas `set-max-intset-entries`, Redis menyimpannya dalam `intset`.
```c
struct intset {
    uint32_t encoding; // INTSET_ENC_INT16, INTSET_ENC_INT32, INTSET_ENC_INT64
    uint32_t length;   // Jumlah elemen
    int8_t contents[]; // Sorted array bilangan bulat
};
```
Karakteristik:
- Memory footprint sangat kecil: array integer flat yang terurut tanpa hashing collision overhead.
- Operasi pencarian menggunakan Binary Search ($O(\log N)$).
- **Auto-upgrade**: Jika set awalnya berisi elemen `int16_t` lalu dimasukkan nilai bernilai `int32_t`, seluruh array otomatis di-*upgrade* ke 32-bit dalam satu batch realokasi memori. Proses upgrade bersifat searah (*never downgrades*).

---

### 3.7 Skiplist
Sorted Set (`ZSET`) saat berukuran besar tidak lagi menggunakan Listpack, melainkan kombinasi **Dict + Skiplist (zset)**.
- **Dict**: Memetakan `member -> score` dengan kecepatan pencarian $O(1)$.
- **Skiplist**: Menyusun node terurut berdasarkan skor untuk operasi *range queries* (`ZRANGEBYSCORE`, `ZREVRANGE`) dengan kompleksitas $O(\log N)$.

```
Level 3:  [Node 1] ------------------------------------> [Node 8]
Level 2:  [Node 1] --------------> [Node 4] -----------> [Node 8]
Level 1:  [Node 1] ----> [Node 2]-> [Node 4] ----> [Node 6]-> [Node 8]
```
Redis menggunakan probabilistic skip list dengan level generasi acak bernilai bias $p = 0.25$, menghasilkan rata-rata overhead pointer yang jauh lebih rendah (1.33 pointer per node) dibandingkan AVL Tree atau Red-Black Tree (2-3 pointer per node) tanpa kebutuhan rotasi node yang kompleks.

---

### 3.8 Alokator Memori Jemalloc & Fragmentasi
Redis secara default menggunakan alokator memori **jemalloc** di Linux.
- **Size Classes**: Jemalloc tidak mengalokasikan ukuran byte sembarang. Alokasi dikelompokkan ke dalam kategori ukuran tertentu (*Small bins*: 8, 16, 32, 48, 64, 80, 96, 112, 128, ..., 512 bytes).
- **Internal Fragmentation**: Jika aplikasi meminta 33 bytes, jemalloc akan mengembalikan slot bin berukuran 48 bytes. Sisa 15 bytes terbuang (*wasted memory*).
- **External Fragmentation**: Terjadi ketika memori virtual telah dilepaskan oleh Redis (`DEL`), tetapi tersebar di berbagai page memori jemalloc sehingga OS tidak dapat merebut kembali (*reclaim*) page tersebut secara fisik.
- Indikator: $\text{mem\_fragmentation\_ratio} = \frac{\text{used\_memory\_rss}}{\text{used\_memory}}$.
  - Ideal: $1.0 < \text{ratio} < 1.5$.
  - Bahaya: $\text{ratio} > 1.5$ (fragmentasi parah, risiko OOM Killer) atau $< 1.0$ (terjadi memory swapping ke disk).

---

## 4. Why & What

| Pertanyaan | Analisis Teknis |
| :--- | :--- |
| **Why not standard C-strings?** | String standar C membutuhkan pemindaian $O(N)$ untuk menghitung panjang byte, memicu latency pada serialisasi. C-strings membatasi data hanya pada ASCII/UTF-8 yang tidak mengandung null character `\0`, merusak integrasi format protokol binary (Protobuf, MessagePack, Avro). |
| **Why Listpack instead of Linked List?** | Node `doubly linked list` membutuhkan alokasi memori independen untuk setiap item: 1 node = payload + 8 byte `prev` pointer + 8 byte `next` pointer. Listpack menyimpan seluruh data dalam satu larik byte sequential yang padat tanpa overhead pointer dan cache friendly. |
| **Why bucketize Hash entries?** | 100 juta string keys membutuhkan 100 juta struct `dictEntry` + `redisObject`, menghasilkan overhead metadata $> 4.8\text{ GB}$. Dengan memecahnya ke dalam Hash berbasis Listpack, metadata global Redis dihemat hingga lebih dari 70%. |
| **What is Active Defragmentation?** | Fitur background engine Redis yang memanfaatkan kemampuan introspeksi jemalloc untuk memindai page memori yang kosong sebagian, mengalokasikan ulang data ke page lain yang padat, dan mengembalikan memori fisik yang kosong ke Kernel tanpa mematikan server. |

---

## 5. How (Workflow Detail)

### 5.1 Siklus Hidup Transisi Encoding String
```
Input: SET key value
          |
Is integer between -9223372036854775808 and 9223372036854775807?
     /        \
   YES         NO
   /             \
Encoding: INT    Length <= 44 bytes?
                  /        \
                YES         NO
                /             \
       Encoding: EMBSTR     Encoding: RAW
```

1. **Mutasi Data**: Jika string dengan tipe `embstr` dimodifikasi menggunakan perintah mutasi seperti `APPEND` atau `SETRANGE`, Redis **pasti** langsung mengubah encoding objek tersebut menjadi `raw`, meskipun panjang hasil akhirnya tetap $\le 44\text{ bytes}$. Hal ini terjadi karena layout memori `embstr` bersifat *read-only* terikat (satu blok alokasi kontinu jemalloc) dan tidak dirancang untuk ekspansi in-place.

---

### 5.2 Siklus Hidup Transisi Encoding Hash
```
Input: HSET hash_key field value
                |
Field & Value length <= hash-max-listpack-value (default 64)
AND
Total fields <= hash-max-listpack-entries (default 512)
          /           \
        YES            NO
        /                \
  Encoding: LISTPACK   Encoding: HASHTABLE (dict)
```

- Ketika kondisi batas dilanggar (misalnya panjang field mencapai 65 byte atau total elemen ke-513 masuk), Redis mengalokasikan Hash Table baru secara instan.
- Seluruh elemen dalam Listpack di-*unpack*, dikonversi menjadi node `dictEntry`, di-hash dengan SipHash, lalu dimasukkan ke dalam bucket table.
- **Peringatan Performa**: Transisi ini adalah proses satu arah (*one-way*). Menghapus field setelah konversi ke `hashtable` **tidak akan pernah** mengembalikan struktur memori kembali ke `listpack`.

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi Kontainer Logistik vs Koper Padat

- **Raw String / Hashtable** ibarat mengirim 10 paket kecil menggunakan 10 truk kontainer terpisah. Masing-masing truk memiliki supir, kabin, surat izin, dan konsumsi bensin independen (overhead pointer dan metadata). Ruang kargo sangat lapang, tetapi biayanya sangat boros.
- **Listpack** ibarat memasukkan 10 paket kecil tersebut ke dalam satu koper berukuran pas, divakum kedap udara tanpa ada ruang sisa. Mengambil barang di tengah membutuhkan kita untuk membuka kunci dan membongkar pakaian di atasnya, tetapi penghematan ruang mencapai batas absolut.

### 6.2 Diagram Layout Memori Komparatif

#### EMBSTR vs RAW String Memory Layout
```
EMBSTR (Single Allocation - 64 bytes total):
+-----------------------------+-----------------------+----------------------------+---+
| redisObject Header (16B)    | sdshdr8 Header (3B)   | Payload String (max 44B)   |\0 |
+-----------------------------+-----------------------+----------------------------+---+
^
|-- jemalloc arena allocation chunk boundary (Single block) ---------------------------|

RAW (Two Independent Allocations):
Allocation 1:
+-----------------------------+
| redisObject Header (16B)    |
|   ptr ----------------------+--------+
+-----------------------------+        |
                                       v
Allocation 2:                          +---------------------+-------------------+---+
                                       | sdshdr8/16/32 (3B+) | Payload String    |\0 |
                                       +---------------------+-------------------+---+
```

#### Komparasi Hash Table vs Listpack
```
Standard Dict Layout (Fragmented Pointer Chasing):
Dict -> [Bucket 0] -> dictEntry (24B) -> key SDS ("user:id")
                                      -> val SDS ("1001")
        [Bucket 1] -> NULL
        [Bucket 2] -> dictEntry (24B) -> key SDS ("user:role")
                                      -> val SDS ("admin")

Listpack Layout (Single Contiguous Flat Byte Array):
+------------+-----------+-----------------------------------+-----------------------------------+------+
| TotBytes4B | NumElem2B | Entry1: "user:id" | Entry2: "1001"| Entry3: "user:role"| Entry4:"admin"| 0xFF |
+------------+-----------+-----------------------------------+-----------------------------------+------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membedah Encoding & Memory Overhead via CLI

Buka terminal `redis-cli` dan jalankan rentetan pengujian alokasi byte berikut:

```bash
# 1. Alokasi Integer
127.0.0.1:6379> SET test_int 42
OK
127.0.0.1:6379> OBJECT ENCODING test_int
"int"
127.0.0.1:6379> MEMORY USAGE test_int
(integer) 48

# 2. Alokasi EMBSTR (44 Karakter)
127.0.0.1:6379> SET test_str_short "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OK
127.0.0.1:6379> STRLEN test_str_short
(integer) 44
127.0.0.1:6379> OBJECT ENCODING test_str_short
"embstr"
127.0.0.1:6379> MEMORY USAGE test_str_short
(integer) 64

# 3. Alokasi RAW (45 Karakter - Naik 1 byte saja)
127.0.0.1:6379> SET test_str_long "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OK
127.0.0.1:6379> STRLEN test_str_long
(integer) 45
127.0.0.1:6379> OBJECT ENCODING test_str_long
"raw"
127.0.0.1:6379> MEMORY USAGE test_str_long
(integer) 88   # Kenaikan drastis akibat alokasi terpisah jemalloc
```

---

### 7.2 Practical Example: Enterprise Memory Optimizer (Go Engine)

Implementasi teknik **Hash Bucketization (Sharding)** menggunakan Go dengan driver `redis/go-redis/v9`. Pola arsitektur ini memecah 10 juta flat string key ke dalam Hash-Hash terpartisi berukuran Listpack secara deterministik.

```go
package main

import (
	"context"
	"crypto/sha1"
	"encoding/binary"
	"fmt"
	"log"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	// BUCKET_SIZE harus selaras dengan hash-max-listpack-entries (default 512)
	BucketSize uint64 = 512
)

type OptimizedCacheClient struct {
	rdb *redis.Client
}

func NewOptimizedCacheClient(addr string) *OptimizedCacheClient {
	rdb := redis.NewClient(&redis.Options{
		Addr:         addr,
		PoolSize:     64,
		MinIdleConns: 16,
		ReadTimeout:  2 * time.Second,
		WriteTimeout: 2 * time.Second,
	})
	return &OptimizedCacheClient{rdb: rdb}
}

// hashPartition menghitung ID bucket dan ID field dalam bucket
func hashPartition(key string) (string, string) {
	hasher := sha1.New()
	hasher.Write([]byte(key))
	digest := hasher.Sum(nil)

	// Ambil 8 byte pertama untuk representasi 64-bit integer
	num := binary.BigEndian.Uint64(digest[:8])

	bucketID := num / BucketSize
	bucketKey := fmt.Sprintf("bkt:%010d", bucketID)
	return bucketKey, key
}

// SetOptimized menyimpan data ke dalam Hash Listpack
func (c *OptimizedCacheClient) SetOptimized(ctx context.Context, key string, val string) error {
	bucketKey, field := hashPartition(key)
	return c.rdb.HSet(ctx, bucketKey, field, val).Err()
}

// GetOptimized mengambil data dari Hash Listpack
func (c *OptimizedCacheClient) GetOptimized(ctx context.Context, key string) (string, error) {
	bucketKey, field := hashPartition(key)
	val, err := c.rdb.HGet(ctx, bucketKey, field).Result()
	if err == redis.Nil {
		return "", fmt.Errorf("key not found")
	}
	return val, err
}

func main() {
	ctx := context.Background()
	client := NewOptimizedCacheClient("localhost:6379")

	// Baseline Ping
	if err := client.rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Koneksi Redis gagal: %v", err)
	}

	totalEntries := 10000
	log.Printf("Memulai injeksi %d key ter-bucketisasi...", totalEntries)

	pipe := client.rdb.Pipeline()
	for i := 0; i < totalEntries; i++ {
		key := "usr_session_" + strconv.Itoa(i)
		val := "token_abc123_payload_payload_payload"
		bucketKey, field := hashPartition(key)
		pipe.HSet(ctx, bucketKey, field, val)

		if i%500 == 0 && i > 0 {
			if _, err := pipe.Exec(ctx); err != nil {
				log.Fatalf("Pipeline exec failed: %v", err)
			}
			pipe = client.rdb.Pipeline()
		}
	}
	// Flush sisa pipeline
	pipe.Exec(ctx)
	log.Println("Data berhasil disimpan. Verifikasi encoding memori...")

	// Cek encoding salah satu bucket acak
	sampleBucket, _ := hashPartition("usr_session_42")
	encoding, err := client.rdb.ObjectEncoding(ctx, sampleBucket).Result()
	if err != nil {
		log.Fatalf("Gagal membaca encoding: %v", err)
	}

	memUsage, _ := client.rdb.MemoryUsage(ctx, sampleBucket).Result()

	fmt.Printf("Bucket: %s\n", sampleBucket)
	fmt.Printf("Encoding type: %s (Harus bernilai 'listpack')\n", encoding)
	fmt.Printf("Memory usage bucket: %d bytes\n", memUsage)
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### 8.1 Studi Kasus: Ad-Tech User Profile & Frequency Capping Engine
- **Skala Beban**: Platform periklanan digital global memproses $1.000.000.000$ (1 Miliar) *User Frequency Caps* harian.
- **Karakteristik Data**: User ID (UUID v4 36 bytes) $\to$ Impression Counter (Integer 1-4 bytes).

### 8.2 Pendekatan Konvensional (Naive Approach)
Penyimpanan langsung menggunakan flat String:
```
SET "usr:f47ac10b-58cc-4372-a567-0e02b2c3d479" "12"
```
Analisis Konsumsi RAM per item:
- `dictEntry` (Global Hash Table): $24\text{ bytes}$
- Kunci `usr:UUID...` (SDS Header + String 40B + null): $44\text{ bytes}$
- Nilai `redisObject` (Metadata integer): $16\text{ bytes}$
- Alokasi `jemalloc` bin padding overhead: $\sim 8\text{ bytes}$
- **Total per item**: $\approx 92\text{ bytes}$ fisik per record.
- **Total Kebutuhan RAM**:
  $$1.000.000.000 \times 92\text{ bytes} \approx 92.000.000.000\text{ bytes} \approx \mathbf{92\text{ GB RAM}}$$
Ditambah fragmentasi memori ($1.4\times$), infrastruktur membutuhkan kluster memori sebesar **128 GB+**, dengan biaya bulanan AWS ElastiCache yang sangat masif.

---

### 8.3 Pendekatan Optimized (Bucketized Hash with Listpack)
Memecah penyimpanan menggunakan hash partitioning:
- Ambil modulo hash dari User ID ke dalam $2.000.000$ Bucket Hash (`bkt:0` hingga `bkt:1999999`).
- Setiap bucket rata-rata menampung 500 fields.
- Konfigurasi engine: `hash-max-listpack-entries 512`, `hash-max-listpack-value 64`.

Struktur:
```
HSET bkt:12345 "f47ac10b-58cc-4372-a567-0e02b2c3d479" 12
```

Analisis Konsumsi RAM per item dalam Listpack:
- Tidak ada pointer `dictEntry` per user.
- Tidak ada `redisObject` per user.
- Encoding Listpack byte:
  - String entry UUID (1 byte header + 36 byte string + 1 byte backlen) = $38\text{ bytes}$
  - Integer entry (1 byte numeric header + 1 byte payload + 1 byte backlen) = $3\text{ bytes}$
  - Total per record: **$41\text{ bytes}$** murni data flat sequential.
- Overhead Bucket Hash:
  - $2.000.000$ bucket Hash $\times 64\text{ bytes}$ metadata $\approx 128\text{ MB}$ (dapat diabaikan).
- **Total Kebutuhan RAM Baru**:
  $$1.000.000.000 \times 41\text{ bytes} + \text{overhead} \approx 41.2\text{ GB RAM}$$

### 8.4 Hasil Produksi

| Parameter | Naive Approach | Bucketized Listpack | Efisiensi |
| :--- | :--- | :--- | :--- |
| **Total Memory Terpakai** | 92.4 GB | 41.5 GB | **$\approx 55.1\%$ Penghematan RAM** |
| **P99 Read Latency** | 0.85 ms | 0.98 ms | Perbedaan tidak signifikan (<0.15ms) |
| **P99 Write Latency** | 0.92 ms | 1.10 ms | Komputasi Listpack scanning termitigasi |
| **Infrastruktur AWS** | 4x cache.r6g.xlarge | 2x cache.r6g.large | **Reduksi Biaya Server: 62%** |

---

## 9. Trade-offs

Menggunakan layout memori yang dipadatkan memiliki konsekuensi arsitektural yang harus diperhitungkan:

```
+-------------------------------------------------------------+
|                     DESAIN ARSITEKTUR                       |
|                                                             |
|   Memory-Optimized (Listpack)    Speed-Optimized (Dict)    |
|   ----------------------------   -----------------------    |
|   [+] Densitas RAM Maksimal      [-] Memory Overhead Tinggi |
|   [-] CPU Overhead saat Search   [+] O(1) Absolute Lookup   |
|   [-] BigKey Risk jika threshold [+] Per-key TTL Native     |
|       dinaikkan berlebihan       [-] Fragmentasi Tinggi     |
+-------------------------------------------------------------+
```

### 9.1 CPU vs Memory Density
- **Keuntungan**: Densitas memori meningkat drastis. Biaya infrastruktur server berkurang hingga ribuan dolar per bulan. CPU Cache Locality meningkat karena Listpack berada dalam contiguous physical page.
- **Kerugian**: Pencarian elemen dalam Listpack adalah $O(N)$ scanning linier. Jika `hash-max-listpack-entries` diubah ke angka ekstrem (misal 5.000), CPU time melonjak drastis saat pencarian field, memblokir *single-threaded event loop* Redis dan menyebabkan lonjakan p99 latency.

### 9.2 Granularitas Fitur Native (Key-level TTL)
- Pada flat key (`SET user:123`), Redis mendukung masa kedaluwarsa native individual (`EXPIRE user:123 60`).
- Pada Hash Bucketization (`HSET bkt:1 user:123 val`), TTL hanya berlaku di level **Bucket**, bukan di level field individual. Untuk menerapkan TTL per-field, aplikasi harus mengelola timestamp kedaluwarsa secara manual di dalam value dan melakukan *lazy cleanup* saat pembacaan data.

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent Demotion dari `embstr` ke `raw`
**Kesalahan**: Melakukan mutasi append pada string pendek dengan ekspektasi string tetap berada pada single allocation buffer.
```bash
SET greeting "hello"
OBJECT ENCODING greeting   # Output: "embstr"
APPEND greeting " world"
OBJECT ENCODING greeting   # Output: "raw" (Meskipun total huruf hanya 11 byte!)
```
**Dampak**: Terjadi fragmentasi memori ganda di heap jemalloc.
**Solusi**: Selalu lakukan *overwrite* penuh (`SET key value`) alih-alih `APPEND` jika data Anda berukuran $\le 44\text{ bytes}$.

---

### 10.2 Jebakan Melampaui Threshold Konfigurasi Secara Tidak Sengaja
Menambahkan satu field saja dengan panjang 65 byte pada struktur hash yang diatur `hash-max-listpack-value 64` akan memicu konversi instan ke Hash Table penuh.

**Troubleshooting Detection Command**:
```bash
# Lakukan pemindaian memory footprint dan deteksi big keys
redis-cli --bigkeys
redis-cli --memkeys

# Analisis tipe data spesifik
redis-cli --scan --pattern "bkt:*" | while read key; do
    echo -n "$key: "
    redis-cli OBJECT ENCODING "$key"
done | grep -v listpack
```

---

### 10.3 Salah Menangani External Fragmentation
Seringkali `INFO memory` menunjukkan `used_memory_rss` jauh lebih tinggi dari `used_memory`, mengindikasikan fragmentasi memori. Mengabaikannya dapat memicu Linux Kernel OOM-Killer mematikan proses Redis.

**Langkah Diagnosis & Mitigasi**:
```bash
# 1. Periksa rasio fragmentasi
redis-cli INFO memory | grep mem_fragmentation_ratio
# Jika > 1.5, fragmentasi tinggi.

# 2. Cek status defragmenter
redis-cli INFO stats | grep defrag

# 3. Aktifkan Active Defragmentation secara real-time
redis-cli CONFIG SET activedefrag yes
redis-cli CONFIG SET active-defrag-ignore-bytes 100mb
redis-cli CONFIG SET active-defrag-threshold-lower 10
redis-cli CONFIG SET active-defrag-threshold-upper 30
redis-cli CONFIG SET active-defrag-cycle-min 5
redis-cli CONFIG SET active-defrag-cycle-max 25
```

---

## 11. Best Practices (Production Checklist)

| Area | Konfigurasi / Pola Rekomendasi | Justifikasi Teknis |
| :--- | :--- | :--- |
| **Max Memory Policy** | `maxmemory-policy volatile-lru` atau `allkeys-lru` | Mencegah panik alokasi jemalloc saat Redis mencapai batas RAM fisik OS. |
| **Hash Limits** | `hash-max-listpack-entries 512`<br>`hash-max-listpack-value 64` | Nilai batas optimal penyeimbang konsumsi CPU Cache Line L1 vs Kompresi Listpack. |
| **Set Limits** | `set-max-intset-entries 512` | Mencegah scanning $O(\log N)$ Intset mengonsumsi clock cycle berlebih pada data non-numerik. |
| **Sorted Set Limits**| `zset-max-listpack-entries 128`<br>`zset-max-listpack-value 64` | Mempertahankan kecepatan agregasi listpack sebelum beralih ke Skiplist pointers. |
| **Kernel Overcommit**| `vm.overcommit_memory = 1` | Menghindari kegagalan background BGSAVE/AOF rewrite fork karena OS page table check. |
| **Linux Transparent Huge Pages** | `echo never > /sys/kernel/mm/transparent_hugepage/enabled` | **Wajib**. THP meningkatkan copy-on-write latency drastis selama operasi `BGSAVE`. |
| **Jemalloc Arena Tuning** | Bind Redis worker thread ke dedicated jemalloc arena via `MALLOC_CONF` | Menghindari arena lock contention saat Redis I/O Threads aktif. |

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'
services:
  redis-memory-lab:
    image: redis:7.2-alpine
    container_name: redis-memory-lab
    command: >
      redis-server
      --port 6379
      --maxmemory 512mb
      --activedefrag yes
      --active-defrag-ignore-bytes 50mb
      --active-defrag-threshold-lower 10
      --hash-max-listpack-entries 512
      --hash-max-listpack-value 64
    ports:
      - "6379:6379"
```

### File: `hands-on/m02/benchmark.py`
Jalankan skrip ini untuk membuktikan komparasi penggunaan memori fisik antara skema Naive vs skema Listpack-Optimized.

```python
import redis
import time
import sys

def get_memory_info(r):
    info = r.info('memory')
    return {
        'used_memory_human': info['used_memory_human'],
        'used_memory': info['used_memory'],
        'used_memory_rss_human': info['used_memory_rss_human'],
        'fragmentation': info['mem_fragmentation_ratio']
    }

def main():
    r = redis.Redis(host='localhost', port=6379, db=0)
    try:
        r.ping()
    except redis.ConnectionError:
        print("Error: Jalankan docker-compose up terlebih dahulu!")
        sys.exit(1)

    print("=== TAHAP 1: Benchmark Skema Naive (Flat Strings) ===")
    r.flushall()
    start_mem = get_memory_info(r)['used_memory']
    
    pipe = r.pipeline()
    total_records = 100000
    for i in range(total_records):
        pipe.set(f"user:session:{i}", "token_xyz_987654321_abcdef")
        if i % 5000 == 0:
            pipe.execute()
            pipe = r.pipeline()
    pipe.execute()
    
    naive_mem = get_memory_info(r)
    diff_naive = naive_mem['used_memory'] - start_mem
    print(f"Naive Used Memory: {naive_mem['used_memory_human']}")
    print(f"Delta Memori Naive: {diff_naive / (1024*1024):.2f} MB")
    
    print("\n=== TAHAP 2: Benchmark Skema Optimized (Listpack Hash Partition) ===")
    r.flushall()
    start_mem = get_memory_info(r)['used_memory']
    
    pipe = r.pipeline()
    for i in range(total_records):
        # 100000 items / 500 items per bucket = 200 buckets
        bucket_id = i // 500
        field = str(i)
        pipe.hset(f"bkt:{bucket_id}", field, "token_xyz_987654321_abcdef")
        if i % 5000 == 0:
            pipe.execute()
            pipe = r.pipeline()
    pipe.execute()
    
    opt_mem = get_memory_info(r)
    diff_opt = opt_mem['used_memory'] - start_mem
    print(f"Optimized Used Memory: {opt_mem['used_memory_human']}")
    print(f"Delta Memori Optimized: {diff_opt / (1024*1024):.2f} MB")

    # Ambil sample bucket encoding
    sample_encoding = r.object('encoding', 'bkt:0').decode('utf-8')
    print(f"\nVerifikasi Encoding Bucket 0: {sample_encoding}")
    
    savings = (1 - (diff_opt / diff_naive)) * 100
    print(f"\n=======================================================")
    print(f"HASIL AKHIR EFISIENSI: MEMORY SAVED = {savings:.2f}%")
    print(f"=======================================================")

if __name__ == '__main__':
    main()
```

### Eksekusi Praktikum
```bash
# 1. Jalankan container
cd hands-on/m02/
docker compose up -d

# 2. Setup Virtualenv dan jalankan benchmark
python3 -m venv venv
source venv/bin/activate
pip install redis
python benchmark.py

# 3. Inspeksi interaktif jemalloc
redis-cli MEMORY STATS
redis-cli MEMORY DOCTOR
```

---

## 13. Exercise

### 13.1 Level: Easy
1. Simpan sebuah string dengan panjang tepat 44 karakter dan nilai numerik 999999.
2. Gunakan perintah `OBJECT ENCODING` untuk memverifikasi jenis encoding keduanya.
3. Lakukan mutasi `SETRANGE` pada string 44-karakter tersebut pada index ke-0 dan verifikasi perubahan encoding apa yang terjadi.

### 13.2 Level: Medium
1. Buat sebuah Set dengan 500 elemen angka berurutan bertipe integer (`1` sampai `500`).
2. Verifikasi bahwa encoding-nya adalah `intset`.
3. Masukkan 1 elemen baru berupa string non-numerik: `"501a"`.
4. Periksa kembali encoding-nya menggunakan `OBJECT ENCODING`. Amati penggunaan memori via `MEMORY USAGE`. Apakah encoding dapat kembali ke `intset` jika string `"501a"` dihapus menggunakan `SREM`? Buktikan.

### 13.3 Level: Hard
1. Buat skrip Python/Bash untuk mengidentifikasi apakah terdapat Hash di instance Redis Anda yang beralih encoding dari `listpack` menjadi `hashtable`.
2. Jika terdeteksi Hash yang menggunakan `hashtable`, periksa berapa jumlah field dan ukuran byte terbesar dari field di dalamnya.
3. Tuliskan logika migrasi aman (*zero-downtime*) untuk memecah hash tersebut menjadi beberapa hash berbasis `listpack`.

---

## 14. Challenge

### Arsitektur Skala Besar: Real-time Multi-tenant Gaming Inventory
Sebuah MMORPG memiliki 50 juta pemain aktif harian. Setiap pemain memiliki daftar inventory yang terdiri dari maksimal 150 item ID (berupa ID integer 32-bit) beserta durability level-nya (angka 1-100).
- **Batasan Sistem**: 
  - Total memori Redis yang dialokasikan di AWS ElastiCache tidak boleh melebihi **8 GB RAM**.
  - Operasi pengecekan item harus memiliki latensi p99 $< 2\text{ ms}$.
- **Tantangan**:
  1. Rancang arsitektur struktur data Redis yang paling optimal untuk menyimpan 50 juta inventory tersebut dengan batasan RAM $\le 8\text{ GB}$. (Struktur data apa yang dipilih? Bagaimana pengemasan byte-nya?)
  2. Hitung estimasi penggunaan byte secara matematis membuktikan rancangan Anda muat di bawah 8 GB.
  3. Bagaimana strategi penanganan perubahan data jika seorang pemain mendapatkan item ke-151?

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Mengapa alokasi string berukuran $\le 44\text{ bytes}$ pada Redis disebut `embstr`?
2. Berapa total overhead memori murni yang dimiliki oleh struct `redisObject` pada arsitektur 64-bit?
3. Sebutkan kelemahan utama struktur C standard string (`char*`) sehingga Redis mengimplementasikan Simple Dynamic String (SDS)!
4. Berapakah batas maksimum alokasi jemalloc yang menyebabkan `embstr` dipatok pada batas string 44 byte?
5. Mengapa tipe data `intset` selalu memelihara data secara terurut (*sorted*)?

### 15.2 Pertanyaan Intermediate
6. Jelaskan apa masalah fundamental pada arsitektur `ziplist` yang menyebabkan developer Redis mendesain ulang strukturnya menjadi `listpack` pada Redis 7.0!
7. Jika sebuah Hash berbasis `listpack` beralih (*downgrade/upgrade*) menjadi `hashtable` karena melanggar batas `hash-max-listpack-entries`, apa yang terjadi pada layout memorinya jika kita menghapus kembali elemen-elemen tersebut hingga di bawah ambang batas?
8. Bagaimana `quicklist` menggabungkan keunggulan linked list konvensional dengan Listpack?
9. Jelaskan perbedaan mendasar antara internal fragmentation dan external fragmentation pada alokator jemalloc di Redis!
10. Mengapa Linux Kernel Transparent Huge Pages (THP) sangat direkomendasikan untuk **dimatikan** (`disabled`) pada node Redis produksi?

### 15.3 Skenario Kasus Produksi
11. **Kasus 1**: Tim SRE Anda melaporkan alarm kritis: `mem_fragmentation_ratio` Redis Cluster melonjak hingga 2.4, sementara alokasi memori aktual (`used_memory`) baru mencapai 40% dari batas `maxmemory`. Apa analisis akar masalah sistemik Anda, dan langkah darurat non-disruptif apa yang harus diambil?
12. **Kasus 2**: Sebuah microservice logging menulis miliaran data metrik menggunakan perintah `APPEND metric:2026-03:app_id <payload>`. Setelah 1 bulan, utilisasi RAM meledak 4x lipat lebih besar dibanding estimasi ukuran payload murni data log. Identifikasi penyebab internal SDS engine yang mendasari masalah ini!
13. **Kasus 3**: Anda diminta mendesain sistem token rate-limiting untuk 200 juta API Key unik. Parameter teknis: Setiap API Key memerlukan 2 metadata (Token Bucket Count dan Last Timestamp). Bagaimana Anda menyusun skema kuncinya di Redis agar memory footprint-nya di bawah 5 GB RAM?

---

## 15.4 Kunci Jawaban & Panduan Pembahasan Quiz

<details>
<summary>Lihat Kunci Jawaban & Pembahasan</summary>

### Jawaban Basic
1. **Karena Embedded Struct**: Alokasi memori untuk header `redisObject` dan header beserta buffer `sdshdr` disatukan (*embedded*) dalam satu kali pemanggilan fungsi malloc kontinu.
2. **16 Bytes**: Terdiri dari 4 bits type + 4 bits encoding + 24 bits lru/lfu + 4 bytes refcount + 8 bytes pointer `*ptr`.
3. **Kelemahan C-Strings**: Kompleksitas $O(N)$ untuk kalkulasi panjang karakter, tidak binary-safe (terhenti jika membaca biner `\0`), serta rentan *buffer overflow* karena tidak melacak alokasi kapasitas buffer.
4. **Ukuran Bin 64 Bytes**: Batas ukuran alokasi fixed class jemalloc adalah 64 bytes (sesuai panjang CPU Cache Line). $64 - 16\text{ (redisObject)} - 3\text{ (sdshdr8)} - 1\text{ (null term)} = 44\text{ bytes}$.
5. **Pencarian Cepat via Binary Search**: Agar pencarian keberadaan elemen ($O(\log N)$) dapat dilakukan tanpa membutuhkan overhead pointer hash table.

### Jawaban Intermediate
6. **Cascading Updates**: Pada `ziplist`, setiap entry menyimpan panjang entry sebelumnya (`prevlen`). Jika sebuah entry di tengah membesar ukurannya melampaui 254 bytes, ukuran `prevlen` entry berikutnya harus membengkak dari 1 byte ke 5 bytes. Ini memicu efek domino realokasi memori beruntun di seluruh entry berikutnya. Listpack menghilangkan field `prevlen` dan menggantinya dengan `backlen` milik entry itu sendiri.
7. **Tidak Terjadi Downgrade**: Konversi layout memori di Redis bersifat *one-way* (searah). Memori akan tetap berformat `hashtable` (*dict*) untuk menghindari *churn* siklus alokasi CPU yang berat.
8. **Hybrid Approach**: Quicklist menggunakan linked list untuk menghubungkan node-node, tetapi setiap node individual berisi flat byte buffer `listpack`. Ini membatasi panjang Listpack agar terhindar dari latency salin-memori saat ekspansi, sekaligus mengeliminasi overhead pointer antar-elemen individual.
9. **Internal vs External**:
   - *Internal*: Ruang memori terbuang di dalam alokasi bin jemalloc yang tidak terpakai penuh (misal: meminta 33 byte tetapi dialokasikan 48 byte).
   - *External*: Ruang memori bebas tersebar di luar halaman fisik sehingga page OS tidak dapat direclaim ke Kernel.
10. **Copy-on-Write (CoW) Overhead**: Saat proses `BGSAVE` atau replikasi fork dilakukan, penulisan 1 byte saja pada halaman memori akan memaksa OS menyalin seluruh alokasi Huge Page (2 MB alih-alih 4 KB standard page), menyebabkan memori meledak dan latensi engine membeku (*spikes*).

### Jawaban Kasus Produksi
11. **Analisis Skenario 1**: 
    - Penyebab: Banyak operasi alokasi dan dealokasi kunci dinamis dengan berbagai variasi ukuran data secara agresif, membuat jemalloc gagal mengembalikan virtual page yang lowong ke kernel OS.
    - Solusi: Aktifkan fitur runtime Active Defragmentation secara dinamis via `CONFIG SET activedefrag yes`, lalu atur `active-defrag-cycle-min 10` dan `active-defrag-cycle-max 50`. Pantau `INFO stats` parameter `active_defrag_hits` hingga rasio turun mendekati 1.2 tanpa mengorbankan p99 latency.
12. **Analisis Skenario 2**: 
    - Penyebab: SDS menggunakan algoritma alokasi eksponensial (*pre-allocation*). Setiap kali operasi `APPEND` melebihi ukuran buffer awal, SDS mengalokasikan ruang ganda (*2x alloc*) jika ukuran di bawah 1 MB. Selain itu, mutasi pertama otomatis mendemosikan string dari `embstr` ke `raw`, menggandakan alokasi jemalloc chunk dan menyisakan banyak unused buffer memory (`alloc - len`).
13. **Analisis Skenario 3**: 
    - Gunakan teknik **Hash Partitioning (Bucketization)** dengan target 512 entri per Listpack Hash.
    - API Key di-hash ke 400.000 bucket (`bkt:<id>`).
    - Nilai count dan timestamp digabungkan menjadi bit-packed binary payload (misal: 4 byte integer count + 4 byte epoch integer = 8 byte payload).
    - Memori: 200 juta entri $\times \sim 35\text{ bytes}$ format Listpack $\approx 7\text{ GB}$. Jika dipadatkan lebih lanjut dengan ID integer: $200\text{M} \times 16\text{ bytes} \approx 3.2\text{ GB RAM}$, berhasil lolos di bawah limit 5 GB.
</details>

---

## 16. Summary

```
===================================================================================
                             REDIS MEMORY TAXONOMY
===================================================================================
Tipe Data   Batas Default / Kondisi         Encoding Padat       Encoding Standar
-----------------------------------------------------------------------------------
STRING      <= 44 bytes                    embstr               raw
STRING      Integer 64-bit                 int                  raw
HASH        entries <= 512 & val <= 64B    listpack             hashtable (dict)
LIST        Default (Redis 7+)             quicklist (listpack) -
SET         entries <= 512 & all integers  intset               hashtable (dict)
ZSET        entries <= 128 & val <= 64B    listpack             skiplist + dict
===================================================================================
```

Menguasai tata letak memori internal (*internal memory layout*) membedakan seorang developer Redis pemula dengan seorang **Enterprise System Architect**. Penghematan puluhan gigabyte RAM dan mitigasi lonjakan latency di sistem berskala masif tidak dicapai dengan menambah kapasitas perangkat keras, melainkan melalui pemahaman mendalam atas representasi biner data di level CPU cache line, struct packing, dan karakteristik alokator jemalloc.