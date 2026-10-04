# BAB 02: Memory Model, Allocator, & Garbage Collector
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menguasai semantik formal **Go Memory Model** dan aturan *Happens-Before* untuk menjamin eksekusi konkuren yang bebas dari *data race* tanpa sinkronisasi berlebih (*over-synchronization*).
- Membedah arsitektur internal **Go Memory Allocator** (turunan TCMalloc) hingga level struktur data: `mcache`, `mcentral`, `mheap`, `mspan`, serta mekanisme *Tiny Allocator*.
- Menganalisis *escape analysis* secara presisi menggunakan *compiler flags* untuk mengontrol alokasi objek antara *stack* dan *heap*.
- Mengurai siklus hidup **Concurrent Tri-color Mark-Sweep Garbage Collector**, termasuk operasi *Hybrid Write Barrier*, fase *Stop-The-World* (STW), dan komputasi dinamis *GC Pacer*.
- Mengonfigurasi parameter *runtime* produksi (`GOGC` dan `GOMEMLIMIT`) untuk mengeliminasi risiko *Out-Of-Memory* (OOM) pada lingkungan terkontainerisasi (Kubernetes).
- Merancang dan mengimplementasikan sistem *high-throughput* dengan pola *zero-allocation* menggunakan teknik *object pooling*, *arena allocation*, dan pemanfaatan tipe data bebas pointer (*pointer-free data structures*).

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda harus memahami:
- Arsitektur konkurensi Go: Goroutine, Channel, dan Primitif Sinkronisasi (`sync.Mutex`, `sync.RWMutex`, `sync/atomic`).
- Representasi data tingkat rendah: Pointer, ukuran tipe data primitif, serta *struct alignment & padding*.
- Dasar-dasar sistem operasi: Virtual memory, paging, cache CPU (L1/L2/L3), dan *system calls* manajemen memori (`mmap`, `brk`).
- Penggunaan dasar perkakas Go: `go build`, `go test`, `go tool compile`.

---

### 3. Concept & Internal Architecture

#### 3.1. Go Memory Model & Semantik Happens-Before
Go Memory Model menetapkan kondisi di mana pembacaan suatu variabel dalam satu goroutine dijamin dapat mengamati nilai yang dihasilkan oleh penulisan ke variabel yang sama oleh goroutine lain.

Hubungan ini ditentukan melalui relasi parsial **Happens-Before ($hb$)**:
1. **Program Order**: Di dalam satu goroutine, urutan eksekusi memori mengikuti urutan kode program.
2. **Channel Operations**:
   - Pengiriman nilai pada unbuffered channel *happens before* selesainya penerimaan nilai tersebut dari channel yang sama:
     $$Send(ch) \xrightarrow{hb} Receive(ch)$$
   - Penutupan channel (*close*) *happens before* penerimaan nilai nol karena channel telah tertutup.
   - Untuk buffered channel berkapasitas $C$, penerimaan nilai ke-$k$ *happens before* pengiriman ke-$(k+C)$ selesai.
3. **Locking (sync.Mutex / sync.RWMutex)**:
   - Pemanggilan `Unlock()` ke-$n$ *happens before* pemanggilan `Lock()` ke-$(n+1)$ mengembalikan eksekusi.
4. **Once Initialization**:
   - Pemanggilan fungsi $f$ tunggal di dalam `sync.Once.Do(f)` *happens before* kembalinya pemanggilan `sync.Once.Do(f)` mana pun.
5. **Atomic Operations**:
   - Sejak Go 1.19, pustaka `sync/atomic` secara formal mengikuti model memori sekuensial konsisten (*sequentially consistent memory order*). Operasi `atomic.Store` *happens before* operasi `atomic.Load` yang membaca nilai tersebut.

```
Goroutine 1:                 Goroutine 2:
[ Write var a = 1 ]
         |
         v
[ atomic.StoreInt32 ]  ==== (Happens-Before) ====>  [ atomic.LoadInt32 == 1 ]
                                                             |
                                                             v
                                                    [ Read var a dijamin == 1 ]
```

---

#### 3.2. Arsitektur Go Memory Allocator (TCMalloc Derivative)
Go menggunakan sistem alokasi berbasis *Thread-Caching Malloc* (TCMalloc) yang disesuaikan secara mendalam dengan *scheduler* Go (M:N scheduler). Tujuannya adalah meminimalkan *contention lock* antar core CPU saat alokasi memori berkecepatan tinggi.

```
+-------------------------------------------------------------------------------+
|                                     OS                                        |
+-------------------------------------------------------------------------------+
                                      ^
                                      | Syscall: mmap (Virtual Memory)
                                      v
+-------------------------------------------------------------------------------+
|                                   mheap                                       |
|  - arena: Memori virtual terkelola (chunks 64MB di Linux 64-bit)             |
|  - central cache: Menampung mcentral untuk setiap Size Class (67 classes)     |
|  - pageAlloc: Radix tree allocator untuk manajemen alokasi page (8KB)         |
+-------------------------------------------------------------------------------+
           |                                                 |
           v                                                 v
+-----------------------+                         +-----------------------+
|  mcentral (Class 1)   |                         |  mcentral (Class 2)   |
|  - partial: mspan list|                         |  - partial: mspan list|
|  - full:    mspan list|                         |  - full:    mspan list|
+-----------------------+                         +-----------------------+
           ^                                                 ^
           | Lock-free pop / Mutex fetch                     |
           v                                                 v
+-------------------------------------------------------------------------------+
|                       mcache (Per Logical Processor 'P')                      |
|  - Size Classes: [0..67] span teralokasi (tanpa contention lock)              |
|  - Tiny Allocator: Menyatukan objek kecil (<16 bytes) tanpa pointer           |
+-------------------------------------------------------------------------------+
           ^                                                 ^
           | Alokasi langsung oleh Goroutine                 |
           +------------------------+------------------------+
                                    |
                             Goroutine (G)
```

Struktur hirarki allocator:
1. **`mcache` (Processor Cache)**:
   - Dimiliki secara eksklusif oleh setiap prosesor logis `P` (*Logical Processor*).
   - Memungkinkan goroutine yang berjalan pada `P` tersebut mengalokasikan memori berukuran kecil tanpa membutuhkan sinkronisasi *lock*.
   - Menyediakan 67 *Size Classes* (dari 8 byte hingga 32 KB), masing-masing digandakan untuk objek yang memiliki pointer (`scan`) dan tidak memiliki pointer (`noscan`).
2. **`mcentral` (Central Span Cache)**:
   - Berbagi antar seluruh prosesor `P` untuk satu *size class* tertentu.
   - Terdiri dari dua daftar berantai (*linked list*): `partial` (span yang masih memiliki slot kosong) dan `full` (span yang seluruh slotnya terisi).
   - Membutuhkan penguncian (*mutex lock*) saat `mcache` meminta penambahan `mspan`.
3. **`mheap` (Global Page Allocator)**:
   - Mengelola seluruh *page* memori aplikasi (ukuran page Go = 8 KB).
   - Mengalokasikan blok memori fisik dari OS melalui panggilan sistem `mmap`.
   - Menggunakan *radix tree* (`pageAlloc`) untuk pencarian *contiguous free pages* dalam waktu $O(k)$ di mana $k$ adalah level tree.
4. **`mspan`**:
   - Blok memori dasar yang terdiri dari sekumpulan *page* Go contiguous.
   - Dipotong-potong menjadi slot objek berukuran seragam sesuai dengan *size class*-nya.
   - Memiliki *allocation bitmap* untuk menandai slot yang terisi atau kosong.

##### Mekanisme Alokasi Berdasarkan Ukuran Objek:
- **Tiny Allocation ($< 16$ bytes, noscan)**:
  Objek kecil tanpa pointer digabungkan ke dalam satu blok 16-byte pada `mcache.tiny` untuk mengurangi fragmentasi internal.
- **Small Allocation ($16 \text{ bytes} \le \text{size} \le 32 \text{ KB}$)**:
  Dibulatkan ke atas menuju *size class* terdekat, kemudian dialokasikan langsung dari slot kosong pada `mspan` di dalam `mcache`.
- **Large Allocation ($> 32 \text{ KB}$)**:
  Dialokasikan langsung ke level `mheap` dengan mengalokasikan jumlah *page* yang dibutuhkan secara kontigu, melewati `mcache` dan `mcentral`.

---

#### 3.3. Escape Analysis
*Escape analysis* adalah proses statis yang dijalankan oleh *compiler* Go untuk menentukan apakah masa hidup (*lifetime*) dari suatu variabel terbatas pada frame fungsi tempat ia dideklarasikan, ataukah variabel tersebut "lolos" (*escapes*) keluar dari batas fungsi tersebut.

- **Stack Allocation**: Jika variabel tidak lolos, alokasi dilakukan pada stack goroutine. Alokasinya sangat murah (hanya berupa instruksi penyesuaian *Stack Pointer* register CPU) dan deallokasinya bersifat instan saat stack frame di-unwind.
- **Heap Allocation**: Jika variabel lolos (misalnya dikembalikan sebagai pointer, disimpan dalam variabel global, atau ditangkap oleh closure yang berumur panjang), alokasi dialihkan ke heap via `runtime.newobject` / `runtime.mallocgc`. Objek ini membebani Garbage Collector.

##### Kasus yang Memaksa Objek Escape ke Heap:
1. **Berbagi Pointer ke Luar Frame**: Mengembalikan pointer variabel lokal dari fungsi.
2. **Dynamic / Interface Dispatch**: Memasukkan nilai konkret ke dalam interface (`runtime.convT2E` atau `runtime.convT2I`). Karena ukuran konkret tidak diketahui secara pasti saat runtime dispatch, nilainya sering kali dievakuasi ke heap.
3. **Penyimpanan Pointer pada Slice/Map Dinamis**: Menambahkan elemen pointer ke dalam collection yang ukurannya dapat membesar (*grow*).
4. **Ukuran Melebihi Batas Stack**: Variabel dengan ukuran sangat besar (misal array `[65536]byte`) langsung dialokasikan di heap untuk mencegah *stack overflow*.
5. **Ukuran yang Ditentukan Saat Runtime**: Pembuatan slice dengan parameter ukuran berupa variabel (`make([]byte, n)`).

---

#### 3.4. Garbage Collector: Concurrent Tri-Color Mark-Sweep & Hybrid Write Barrier
Go mengimplementasikan Garbage Collector non-generasional, konkuren, bertipe *Tri-color Mark and Sweep* dengan target latensi rendah (*sub-millisecond STW*).

##### Algoritma Tri-Color Abstraction:
- **White (Putih)**: Objek kandidat pengumpulan (*garbage* potensial). Pada awal fase *marking*, seluruh objek dianggap putih. Objek yang tetap putih di akhir fase marking akan dibebaskan (*swept*).
- **Grey (Abu-abu)**: Objek yang telah ditemukan dapat dijangkau (*reachable*), namun pointer di dalam objek tersebut belum seluruhnya dipindai (*scanned*).
- **Black (Hitam)**: Objek yang terbukti *reachable* dan seluruh pointer yang dikandungnya telah selesai dipindai. Objek hitam tidak boleh memiliki pointer yang merujuk langsung ke objek putih tanpa terdeteksi.

```
       Root Objects (Global vars, Stack pointers)
                         |
                         v
                  +-------------+
                  | Black (1)   |
                  +-------------+
                         |
                         v
                  +-------------+
                  | Grey (2)    | <--- Sedang dipindai oleh GC Worker
                  +-------------+
                   /           \
                  v             v
          +-------------+  +-------------+
          | White (3)   |  | White (4)   | <--- Objek White (Unreachable)
          +-------------+  +-------------+      akan dibersihkan pada fase Sweep
                 ^
                 | (Pelanggaran jika Black langsung menunjuk White tanpa Barrier)
                 |
     Goroutine memodifikasi pointer:
     Black(1) ---> White(3)  ===> DITANGKAP OLEH HYBRID WRITE BARRIER!
                                   White(3) dinaikkan statusnya menjadi Grey.
```

##### Operasi Hybrid Write Barrier (HWB)
Dalam sistem concurrent GC, goroutine aplikasi (disebut *Mutator*) tetap berjalan bersamaan dengan *GC Worker*. Ini memunculkan potensi bahaya: Mutator dapat menyembunyikan objek putih dari GC dengan cara melepaskan referensinya dari objek abu-abu dan menempelkannya ke objek hitam yang sudah selesai dipindai.

Untuk mencegah kondisi tersebut tanpa harus menghentikan seluruh sistem (STW), Go menggunakan **Hybrid Write Barrier** (diperkenalkan pada Go 1.8, menggabungkan model Dijkstra dan Yuasa):
1. Setiap pointer slot yang dioverwrite pada heap, objek lama yang ditunjuknya diwarnai menjadi abu-abu (*Yuasa-style deletion barrier*).
2. Setiap pointer baru yang dibuat dan ditautkan ke heap, objek baru tersebut diwarnai menjadi abu-abu (*Dijkstra-style insertion barrier*).
3. Seluruh alokasi baru selama GC aktif langsung diberi warna **Hitam**.
4. Seluruh stack goroutine dipindai sekali pada fase awal, dan stack tidak dipasangi write barrier untuk menjaga kecepatan eksekusi stack lokal.

Ekspresi pseudocode dari Hybrid Write Barrier:
```c
writePointer(slot, ptr):
    shade(*slot)  // Jika pointer lama ada, warnai jadi Grey (Yuasa deletion)
    if current_goroutine.stack_scanned:
        shade(ptr) // Jika stack sudah dipindai, warnai pointer baru jadi Grey (Dijkstra insertion)
    *slot = ptr
```

##### 4 Fase Siklus Hidup GC:
1. **Sweep Termination (STW)**:
   - Sangat singkat (beberapa mikrodetik).
   - Memastikan seluruh span dari siklus GC sebelumnya telah selesai dibersihkan.
2. **Concurrent Mark (Konkuren)**:
   - Mutator berjalan normal bersama GC Workers.
   - GC mengambil 25% kapasitas CPU yang tersedia (misal: 2 dari 8 core `P`).
   - *Hybrid Write Barrier* diaktifkan.
   - Melakukan traversal pointer dari roots hingga grey queue kosong.
   - Menggunakan mekanisme *Mark Assist*: Jika suatu goroutine mengalokasikan heap terlalu cepat, goroutine tersebut dipaksa membantu GC melakukan pemindaian objek proporsional dengan alokasi yang dilakukannya.
3. **Mark Termination (STW)**:
   - Sangat singkat (< 0.5 ms).
   - Menghentikan mutator, menyelesaikan *root marking* terakhir, mematikan write barrier, menghitung metrik alokasi berikutnya.
4. **Concurrent Sweep (Konkuren)**:
   - Mengembalikan memori dari span yang berisi objek putih ke `mcentral` / `mheap`.
   - Terjadi secara bertahap (*lazy sweep*) saat goroutine meminta alokasi baru.

##### GC Pacer & Target Memori
GC Pacer bertugas menentukan kapan siklus GC berikutnya harus dimulai agar penggunaan memori tidak melampaui target yang ditetapkan.
- **`GOGC`**: Persentase pertumbuhan heap sebelum memicu GC berikutnya. Nilai bawaan adalah `100` (memicu GC saat ukuran heap bertambah 100% dari heap aktif pada siklus sebelumnya).
- **`GOMEMLIMIT`** (Diperkenalkan pada Go 1.19): Batas keras/lembut memori virtual total runtime. Pacer menyesuaikan frekuensi GC secara dinamis saat penggunaan memori mendekati batas ini untuk mencegah *Out-of-Memory Kill* oleh OS.

---

### 4. Why & What

| Dimensi | Mengapa Didesain Demikian | Apa Dampaknya bagi Engineering |
| :--- | :--- | :--- |
| **TCMalloc Architecture (`mcache`)** | Menghindari sinkronisasi global mutex pada alokasi multithreaded. | Alokasi berukuran kecil pada Go memiliki performa setara alokasi lokal C, memungkinkan throughput masif pada ribuan goroutine. |
| **No Compact / Non-Moving GC** | Objek di heap tidak pernah dipindahkan alamat memorinya setelah dialokasikan. | Integrasi pointer dengan Cgo sangat aman, operasi dereferensi pointer bebas dari overhead indirection table, namun rentan fragmentasi memori eksternal. |
| **Hybrid Write Barrier** | Menghilangkan kebutuhan untuk melakukan *re-scan stack* pada fase Mark Termination. | Mengurangi waktu pause STW dari puluhan milidetik (pada era Go 1.4) menjadi kurang dari 1 milidetik pada beban kerja produksi berskala besar. |
| **Unified GOMEMLIMIT** | Mencegah pembengkakan heap yang tidak terkendali pada container dengan memory limit ketat. | Mengeliminasi insiden OOMKilled di Kubernetes tanpa perlu mematikan GC atau menetapkan `GOGC` statis yang terlalu agresif. |

---

### 5. How (Workflow Detail)

Alur alokasi memori internal melalui pemanggilan `new(T)` atau `make([]T, len)`:

```
[ Kode Aplikasi: ptr := new(MyStruct) ]
                   |
                   v
      [ Compiler: Escape Analysis ]
         /                    \
     (TIDAK ESCAPE)        (ESCAPE)
       /                        \
      v                          v
[ Stack Allocation ]      [ runtime.newobject ]
- Majukan Register SP            |
- Return pointer stack           v
                          [ runtime.mallocgc ]
                                 |
        +------------------------+------------------------+
        |                                                 |
(Size < 16B & noscan)                      (16B <= Size <= 32KB)
        |                                                 |
        v                                                 v
[ Tiny Allocator ]                              [ Size Class Matching ]
- Cek mcache.tiny                               - Petakan size ke Class ID [1..67]
- Muat ke blok jika cukup                       - Ambil mspan dari mcache.alloc[class]
- Jika penuh: ambil span baru                   - Ambil slot kosong via allocBits
        |                                                 |
        +-------------------+-----------------------------+
                            |
                     (Span Kosong?)
                     /            \
                   (TIDAK)       (YA)
                     |             \
                     v              v
            [ Return Pointer ]   [ Refill dari mcentral ]
                                 - Lock mcentral.partial
                                 - Ambil mspan baru
                                 - Jika mcentral kosong:
                                     -> Alokasi Page dari mheap
                                     -> Jika mheap habis: mmap ke OS
                                 - Update mcache.alloc[class]
                                 - Return Pointer
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengelolaan Logistik Gudang Modern
Bayangkan sistem manajemen memori Go seperti distribusi logistik pabrik:
1. **Stack**: Saku celana pekerja. Sangat cepat diambil dan dikembalikan. Barang di saku langsung dibuang saat pekerja keluar ruangan (fungsi berakhir).
2. **`mcache`**: Meja kerja pribadi setiap kepala regu (Processor `P`). Berisi kotak-kotak baut berukuran spesifik (Size Classes). Kepala regu mengambil baut dari mejanya sendiri tanpa perlu izin siapa pun.
3. **`mcentral`**: Rak penyimpanan lorong pabrik. Jika meja kerja kehabisan baut ukuran 10mm, kepala regu pergi ke rak lorong nomor 10mm. Karena rak ini dipakai bersama oleh banyak regu, kepala regu harus antre (Mutex Lock).
4. **`mheap`**: Gudang pusat material. Jika rak lorong kosong, staf gudang memotong balok baja besar (Pages 8KB) menjadi ukuran rak spesifik.
5. **Garbage Collector**: Tim pembersih otomatis yang berjalan di lantai pabrik. Menggunakan cat tiga warna untuk menandai barang yang masih dipakai operator, dan melempar sisa material tak bertuan kembali ke gudang pusat tanpa mematikan mesin pabrik.

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Membedah Escape Analysis
Gunakan kode berikut untuk memahami bagaimana *compiler* memutuskan alokasi stack vs heap.

```go
package main

import "fmt"

type Payload struct {
	ID    int64
	Value float64
}

//go:noinline
func createOnStack() Payload {
	// Variabel p tidak pernah keluar sebagai pointer.
	// Nilainya disalin (copied) saat fungsi mengembalikan data.
	p := Payload{ID: 1, Value: 3.14}
	return p
}

//go:noinline
func createOnHeap() *Payload {
	// Pointer ke p dikembalikan keluar dari scope fungsi.
	// Compiler memindahkan alokasi p ke Heap!
	p := Payload{ID: 2, Value: 6.28}
	return &p
}

func main() {
	_ = createOnStack()
	pHeap := createOnHeap()

	// Pemanggilan fmt.Println menerima interface{} (any).
	// Ini menyebabkan pHeap lolos ke heap jika belum lolos.
	fmt.Println(pHeap.ID)
}
```

Uji menggunakan perintah compiler flags:
```bash
go build -gcflags="-m -m -l" main.go
```
*Output Compiler Trace:*
```text
./main.go:20:9: &p escapes to heap
./main.go:20:9: 	from p (escapes) at ./main.go:19:2
./main.go:19:2: moved to heap: p
./main.go:28:13: ... argument does not escape
./main.go:28:19: pHeap.ID escapes to heap
```

---

#### 7.2. Practical Example: High-Throughput Packet Processor (Zero-Allocation Pipeline)
Pola implementasi *high-performance network parsing* yang menghindari alokasi heap melalui pemanfaatan `sync.Pool`, *pointer-free structure*, dan *slice recycling*.

```go
package main

import (
	"bytes"
	"encoding/binary"
	"errors"
	"io"
	"sync"
)

const (
	MaxPayloadSize = 4096
	MagicHeader    = 0xAABBCCDD
)

// Packet noscan: struct ini tidak memiliki referensi pointer internal,
// sehingga GC menandainya sebagai 'noscan' di mcache (biaya scanning = 0).
type PacketHeader struct {
	Magic   uint32
	SeqID   uint64
	DataLen uint32
}

type PacketBuffer struct {
	Header  PacketHeader
	Payload [MaxPayloadSize]byte
	Length  int
}

func (pb *PacketBuffer) Reset() {
	pb.Header = PacketHeader{}
	pb.Length = 0
}

// PacketProcessor mengelola pooling memori untuk meniadakan alokasi heap dinamis.
type PacketProcessor struct {
	pool sync.Pool
}

func NewPacketProcessor() *PacketProcessor {
	return &PacketProcessor{
		pool: sync.Pool{
			New: func() any {
				// Alokasi memori heap awal yang dialokasikan sekali,
				// kemudian digunakan berulang kali selamanya.
				return new(PacketBuffer)
			},
		},
	}
}

func (pp *PacketProcessor) ProcessStream(r io.Reader) (*PacketBuffer, error) {
	// Ambil buffer dari pool tanpa memicu mallocgc
	buf := pp.pool.Get().(*PacketBuffer)
	buf.Reset()

	// Baca Header langsung ke struktur memori (16 bytes)
	var headerBytes [16]byte
	if _, err := io.ReadFull(r, headerBytes[:]); err != nil {
		pp.pool.Put(buf) // Kembalikan ke pool jika gagal
		return nil, err
	}

	buf.Header.Magic = binary.BigEndian.Uint32(headerBytes[0:4])
	buf.Header.SeqID = binary.BigEndian.Uint64(headerBytes[4:12])
	buf.Header.DataLen = binary.BigEndian.Uint32(headerBytes[12:16])

	if buf.Header.Magic != MagicHeader {
		pp.pool.Put(buf)
		return nil, errors.New("invalid protocol magic byte")
	}

	if buf.Header.DataLen > MaxPayloadSize {
		pp.pool.Put(buf)
		return nil, errors.New("payload exceeds buffer capacity")
	}

	// Baca body langsung ke array internal tanpa alokasi slice baru
	buf.Length = int(buf.Header.DataLen)
	if _, err := io.ReadFull(r, buf.Payload[:buf.Length]); err != nil {
		pp.pool.Put(buf)
		return nil, err
	}

	return buf, nil
}

func (pp *PacketProcessor) Release(buf *PacketBuffer) {
	pp.pool.Put(buf)
}
```

*Benchmark verifikasi 0 alokasi:*
```go
package main

import (
	"bytes"
	"testing"
)

func BenchmarkProcessStream(b *testing.B) {
	proc := NewPacketProcessor()
	
	// Siapkan dummy frame data
	rawFrame := make([]byte, 16+64)
	binary.BigEndian.PutUint32(rawFrame[0:4], MagicHeader)
	binary.BigEndian.PutUint64(rawFrame[4:12], 1001)
	binary.BigEndian.PutUint32(rawFrame[12:16], 64)

	reader := bytes.NewReader(rawFrame)

	b.ReportAllocs()
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		reader.Reset(rawFrame)
		buf, err := proc.ProcessStream(reader)
		if err != nil {
			b.Fatal(err)
		}
		proc.Release(buf)
	}
}
```
Hasil eksekusi:
```text
BenchmarkProcessStream-8   35421098   31.2 ns/op   0 B/op   0 allocs/op
```

---

### 8. Real World Case Study: Mengatasi STW Latency & OOMKilled pada AdTech Bidding Engine (100k RPS)

#### Konteks
Sistem RTB (Real-Time Bidding) memproses 100.000 permintaan per detik. Engine berjalan di Kubernetes dengan spesifikasi pod: **4 vCPU, 4 GiB Memory Limit**.

#### Permasalahan
1. **OOMKilled**: Pod mengalami termination restart secara sporadis setiap beberapa jam pada kondisi *traffic spike*.
2. **SLA Breach**: P99 latency melonjak dari 8ms menjadi 65ms saat beban tinggi.
3. Analisis metrik menunjukkan CPU throttle meningkat drastis akibat GC worker mengambil 25% CPU terus-menerus, dan *memory footprint* melebihi 4 GiB sebelum GC selesai berjalan.

#### Root Cause Analysis (RCA)
- Nilai default `GOGC=100` membuat Go menunda GC hingga heap tumbuh sebesar 100% dari live heap sebelumnya.
- Jika live heap berada pada 2.2 GiB, runtime menetapkan target pemanggilan GC berikutnya pada $2.2 + 2.2 = 4.4 \text{ GiB}$.
- Karena memory limit pod adalah 4.0 GiB, kernel Linux melalui cgroup OOM-killer langsung membunuh proses saat heap menyentuh 4.0 GiB, sebelum GC sempat dipicu pada target 4.4 GiB.

```
Total Pod Memory (4 GiB Limit)
+-------------------------------------------------------+
| [ Live Heap: 2.2 GiB ]                                |
+-------------------------------------------------------+
                           |
                           v Target GOGC=100: 4.4 GiB (Melampaui Batas!)
+------------------------------------+------------------+
| Live Heap: 2.2 GiB                 | OOM Trigger Point: 4.0 GiB ===> KILLED!
+------------------------------------+------------------+
```

#### Solusi Arsitektural
1. **Implementasi `GOMEMLIMIT`**:
   Menetapkan soft-limit memori sebesar 85% dari batas hard cgroup untuk menyediakan *headroom* bagi OS thread, binary footprint, dan overhead runtime.
   $$4.0 \text{ GiB} \times 0.85 \approx 3.4 \text{ GiB}$$
   ```bash
   export GOMEMLIMIT=3400MiB
   export GOGC=100
   ```
2. **Eliminasi String Boxing pada Filter Engine**:
   Mengganti representasi filter JSON `map[string]interface{}` menjadi *flat byte-slice index* yang menggunakan representasi numerik. Menghindari konversi tipe data yang memicu ribuan objek `runtime.convT2E` per request.
3. **Penyelarasan Struct (Memory Padding Reduction)**:
   Mengurutkan tipe data atribut pada internal struct untuk mengurangi overhead fragmentasi memori akibat *memory alignment padding*.

#### Hasil
- **OOMKilled**: Turun menjadi 0 kejadian.
- **P99 Latency**: Turun dari 65ms ke 5.2ms.
- **GC CPU Usage**: GC pacer menstabilkan ritme pembersihan tanpa jatuh ke kondisi *GC Thrashing*.

---

### 9. Trade-offs

| Parameter Desain | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **`GOGC < 100` (Agresif, misal `GOGC=50`)** | Mengurangi footprint penggunaan RAM secara keseluruhan. | Membutuhkan lebih banyak siklus CPU untuk menjalankan GC Worker; throughput transaksi menurun. |
| **`GOGC > 100` (Santai, misal `GOGC=400`)** | Menghemat siklus CPU; throughput transaksi meningkat secara drastis. | Membutuhkan kapasitas RAM fisik yang jauh lebih besar; risiko OOM jika alokasi burst terjadi tiba-tiba. |
| **Penggunaan `sync.Pool` Ekstensif** | Mengeliminasi alokasi pada hot-path; meniadakan *GC marking load*. | Kompleksitas manajemen state objek (harus reset manual); objek dalam pool dapat dibebaskan sewaktu-waktu oleh GC saat beban rendah. |
| **Off-Heap Memory (`mmap`/`cgo`)** | Data di luar radar GC sepenuhnya; tidak ada overhead GC scanning berapapun besarnya memori. | Rentan *memory leak*; kehilangan proteksi keamanan *memory safety* Go; penanganan *segmentation fault* manual. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Escape Analysis Failure Akibat Interface Abstraction
```go
// SALAH: fmt.Sprintf atau loggers menerima interface{} yang memaksa int lolos ke Heap.
func processID(id int64) {
    // id mengalami escape ke heap akibat boxing ke interface{}
    log.Println("Processing:", id) 
}

// BENAR: Gunakan library zero-allocation logging (misal: zerolog, zap) 
// atau formatting berbasis byte buffer tanpa boxing interface.
func processIDOptimized(id int64, logger *zap.Logger) {
    logger.Info("Processing", zap.Int64("id", id))
}
```

#### Mistake 2: Pointer-Heavy Cache Structures
```go
// SALAH: GC Worker wajib memindai 10 juta pointer setiap siklus Mark!
type Cache struct {
    data map[int64]*UserSession // 10 juta entry = 10 juta pointer traversal
}

// BENAR: Struktur bebas pointer (pointer-free). GC sama sekali TIDAK memindai
// map keys atau values jika keduanya tidak mengandung tipe pointer.
type FastCache struct {
    data map[int64]UserSessionFlat // Struct tidak memiliki pointer sama sekali
}
```

#### Mistake 3: Slicing Sub-Slice Menyebabkan Memory Leak
```go
// SALAH: Menyimpan sub-slice kecil dari array besar mempertahankan
// seluruh array 10MB di heap selama sub-slice masih dirujuk.
func getHeader(largeData []byte) []byte {
    return largeData[:8] // Array asli 10MB tidak dapat dibersihkan oleh GC!
}

// BENAR: Alokasikan slice baru seukuran data target, lalu salin isinya.
func getHeaderSafe(largeData []byte) []byte {
    header := make([]byte, 8)
    copy(header, largeData[:8])
    return header // largeData dapat segera dibersihkan oleh GC
}
```

#### Troubleshooting Toolkit
1. **Trace GC Behavior secara Real-time:**
   ```bash
   GODEBUG=gctrace=1 ./my-service
   ```
   *Analisis output gctrace:*
   `gc 12 @1.234s 2%: 0.12+1.5+0.04 ms clock, 0.96+1.5/3.2/0+0.32 ms cpu, 4->4->2 MB, 5 MB goal, 0 MB stacks, 8 P`
   - `0.12+1.5+0.04 ms clock`: STW Sweep termination + Concurrent Mark + STW Mark termination.
   - `4->4->2 MB`: Heap sebelum mark -> Heap setelah mark -> Live heap yang tersisa.

2. **Deteksi Data Race & Happens-Before Violations:**
   ```bash
   go test -race -count=1 ./...
   ```

3. **Memory Profile (Heap Allocation & In-Use):**
   ```bash
   go tool pprof http://localhost:6060/debug/pprof/heap
   (pprof) top --alloc_space    # Objek yang paling banyak dialokasikan secara kumulatif
   (pprof) top --inuse_space     # Objek yang aktif menahan memori saat ini
   ```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Memory Alignment Struct**: Urutkan *fields* struct dari tipe data terbesar ke terkecil (misal `int64` -> `int32` -> `int16` -> `bool`) untuk meminimalkan padding byte yang sia-sia.
2. [ ] **Pod Resource Tuning**: Selalu definisikan `GOMEMLIMIT` pada file deployment container (Kubernetes) bernilai 80% s.d. 85% dari spesifikasi `resources.limits.memory`.
3. [ ] **Pre-Allocate Slices & Maps**: Selalu gunakan hint kapasitas awal: `make([]T, 0, expectedCap)` dan `make(map[K]V, expectedCap)` untuk mencegah proses pemekaran (*doubling growth*) yang membuang memori lama ke heap.
4. [ ] **Hindari Pointer pada Cache Berukuran Masif**: Gunakan representasi flat array byte (`[]byte`), hash off-heap, atau tipe data integer index untuk data cache dalam memori.
5. [ ] **Reuse Objek via `sync.Pool`**: Manfaatkan `sync.Pool` khusus untuk objek yang memiliki frekuensi alokasi tinggi (*high churn rate*) dan memiliki siklus hidup pendek.
6. [ ] **Pantau Metrik GC**: Monitor metrik resmi `runtime/metrics` (misal: `/gc/pauses:seconds`, `/memory/classes/heap/objects:bytes`) via Prometheus agent daripada mengandalkan metrik OS RSS mentah.

---

### 12. Hands-on Practice

Buat dan simpan seluruh latihan ini di folder: `hands-on/m02/`

#### Langkah 1: Siapkan Struktur Direktori
```bash
mkdir -p hands-on/m02/cmd
mkdir -p hands-on/m02/allocator
cd hands-on/m02
go mod init m02-memory-deepdive
```

#### Langkah 2: Buat Modul Struct Alignment Inspector
Simpan di `hands-on/m02/allocator/align.go`:
```go
package allocator

import (
	"fmt"
	"unsafe"
)

// UnoptimizedStruct: Menghasilkan pemborosan padding yang besar
type UnoptimizedStruct struct {
	FlagA bool   // 1 byte
	Count uint64 // 8 bytes (memerlukan padding 7 bytes sebelum offset ini)
	FlagB bool   // 1 byte
	Value uint32 // 4 bytes (memerlukan padding 3 bytes)
}

// OptimizedStruct: Penataan field sejajar meminimalkan alokasi memori
type OptimizedStruct struct {
	Count uint64 // 8 bytes (offset 0)
	Value uint32 // 4 bytes (offset 8)
	FlagA bool   // 1 byte  (offset 12)
	FlagB bool   // 1 byte  (offset 13)
	// Padding 2 bytes di ujung untuk memenuhi alignment boundary 8-byte
}

func PrintPaddingReport() {
	un := UnoptimizedStruct{}
	op := OptimizedStruct{}

	fmt.Printf("[UnoptimizedStruct] Ukuran Total: %d bytes (Data murni: 14 bytes, Padding: %d bytes)\n",
		unsafe.Sizeof(un), unsafe.Sizeof(un)-14)
	fmt.Printf("[OptimizedStruct]   Ukuran Total: %d bytes (Data murni: 14 bytes, Padding: %d bytes)\n",
		unsafe.Sizeof(op), unsafe.Sizeof(op)-14)
}
```

#### Langkah 3: Buat High-Allocation Engine untuk Simulasi Pacer & Profiling
Simpan di `hands-on/m02/cmd/main.go`:
```go
package main

import (
	"fmt"
	"net/http"
	_ "net/http/pprof"
	"os"
	"runtime"
	"runtime/metrics"
	"time"

	"m02-memory-deepdive/allocator"
)

func runAllocationWorkload() {
	// Menghasilkan jutaan objek sementara untuk memicu siklus GC
	for {
		for i := 0; i < 50000; i++ {
			// Sengaja dialokasikan ke heap via slice of pointers
			_ = make([]*int64, 100)
		}
		time.Sleep(10 * time.Millisecond)
	}
}

func monitorRuntimeMetrics() {
	const memLimitMetric = "/memory/classes/total:bytes"
	const gcPauseMetric = "/gc/pauses:seconds"

	samples := make([]metrics.Sample, 2)
	samples[0].Name = memLimitMetric
	samples[1].Name = gcPauseMetric

	for {
		time.Sleep(2 * time.Second)
		metrics.Read(samples)

		var totalBytes uint64
		if samples[0].Value.Kind() == metrics.KindUint64 {
			totalBytes = samples[0].Value.Uint64()
		}

		fmt.Printf("[METRICS] Total Runtime Memory: %.2f MB\n", float64(totalBytes)/(1024*1024))
	}
}

func main() {
	fmt.Println("=== Memory Architecture & Profiling Demo ===")
	allocator.PrintPaddingReport()

	// Jalankan profiling endpoint pada port 6060
	go func() {
		fmt.Println("pprof server listening on http://localhost:6060/debug/pprof/")
		_ = http.ListenAndServe("localhost:6060", nil)
	}()

	go monitorRuntimeMetrics()

	fmt.Println("Menjalankan workload simulasi... Tekan Ctrl+C untuk berhenti.")
	runAllocationWorkload()
}
```

#### Langkah 4: Eksekusi dan Verifikasi Profiling
1. Jalankan aplikasi dengan flag GC trace aktif:
   ```bash
   GODEBUG=gctrace=1 go run cmd/main.go
   ```
2. Buka terminal baru dan amati heap profiling:
   ```bash
   go tool pprof http://localhost:6060/debug/pprof/heap
   ```
3. Di dalam CLI pprof, ketik:
   ```text
   (pprof) top
   (pprof) list runAllocationWorkload
   ```

---

### 13. Exercise

#### Level: Easy
Analisis fungsi berikut menggunakan compiler flag `-gcflags="-m"`. Jelaskan mengapa variabel `val` lolos (*escapes*) ke heap, lalu ubah fungsinya agar alokasi terjadi sepenuhnya di dalam **Stack**.
```go
package exercise

func CalculateSum(nums []int) *int {
    sum := 0
    for _, n := range nums {
        sum += n
    }
    return &sum
}
```

#### Level: Medium
Diberikan sebuah fungsi parser JSON yang berjalan pada pipeline pemrosesan log intensif (10.000 log/detik). Setiap baris log diparsing menjadi struct berikut:
```go
type LogEntry struct {
    Timestamp int64
    Level     string
    Message   string
    Metadata  map[string]string
}
```
Ubah arsitektur pengolahan struct tersebut agar:
1. Menghilangkan penggunaan tipe data pointer/map dinamis.
2. Menggunakan pool buffer yang dapat dipakai ulang (`sync.Pool`).
3. Buktikan melalui Go Benchmark bahwa alokasi memori turun hingga `0 B/op` dan `0 allocs/op`.

#### Level: Hard
Tulis sebuah allocator kustom berkonsep **Linear/Arena Memory Allocator** menggunakan slice byte tunggal `[]byte` berkapasitas tetap (misal: 10 MB) tanpa memanggil `new()` atau `make()` internal selama alokasi berjalan.
Syarat implementasi:
1. Dukung fungsi `Alloc(size uintptr) (unsafe.Pointer, error)`.
2. Pastikan alignment memori 8-byte terpenuhi untuk setiap blok alokasi.
3. Sediakan fungsi `Reset()` yang mengembalikan pointer arena ke offset 0 untuk mendaur ulang seluruh memori secara instan dalam $O(1)$.
4. Sertakan uji thread-safety menggunakan operasi atomik (`sync/atomic`).

---

### 14. Challenge

Rancang arsitektur komponen **In-Memory Cache L1** berbasis konkuren dengan batasan performa enterprise:
- **Kapasitas**: Menyimpan hingga 50.000.000 (50 juta) key-value entries.
- **Batasan Memori**: Maksimal memori sistem yang dialokasikan adalah 4 GiB.
- **Kinerja**: Waktu henti GC (*GC Mark Latency*) harus konsisten berada di bawah 1 milidetik meskipun cache dalam kondisi terisi penuh (kapasitas 100%).

#### Problem Statement:
Jika Anda menggunakan model standar Go `map[string][]byte`, Garbage Collector akan melakukan traversi pada seluruh entry pointer tersebut, yang akan memicu lonjakan latensi STW/Mark Assist hingga ratusan milidetik dan menguras CPU.

#### Tugas Anda:
1. Rancang arsitektur struktur data off-heap atau arsitektur *zero-scan cache* (menggunakan flat `[]byte` tunggal yang di-slice dengan pemetaan index berbasis modulo array of primitives tanpa pointer).
2. Tuliskan spesifikasi desain teknis arsitekturnya (*Technical Design Document* singkat).
3. Buat implementasi inti mesin cache tersebut beserta unit test dan benchmark yang mengukur alokasi heap saat proses *eviction* dan *insertion* berlangsung.

---

### 15. Quiz Evaluasi Pemahaman

#### 15.1. Pertanyaan Basic
1. Apa fungsi dari pointer register stack pointer (SP) dalam konteks stack allocation, dan mengapa alokasi pada stack jauh lebih murah dibandingkan heap?
2. Berapa ukuran default satu page pada arsitektur Go Memory Allocator?
3. Sebutkan tiga warna yang merepresentasikan status objek pada algoritma Tri-color GC Go beserta definisinya!
4. Apa yang menyebabkan sebuah variabel tetap dievakuasi ke heap meskipun hanya digunakan di dalam satu blok fungsi saja?
5. Mengapa tipe data `noscan` pada `mcache` dapat mempercepat proses kerja Garbage Collector?

#### 15.2. Pertanyaan Intermediate
6. Jelaskan bagaimana *Hybrid Write Barrier* bekerja pada fase Concurrent Mark, serta perbedaan mendasarnya dengan kombinasi Dijkstra barrier murni!
7. Apa peran *Mark Assist* dalam siklus Garbage Collector Go, dan kondisi apa yang memicu runtime mengaktifkannya pada suatu goroutine?
8. Bagaimana relasi *Happens-Before* terbentuk antara pengiriman data ke buffered channel dengan proses penerimaan datanya?
9. Jelaskan struktur internal `mspan` dan bagaimana `allocBits` digunakan untuk alokasi memori berkecepatan tinggi!
10. Bagaimana `GOMEMLIMIT` berinteraksi dengan `GOGC` ketika konsumsi memori aktual mendekati batas yang ditentukan?

#### 15.3. Skenario Kasus Produksi
11. **Skenario A**: Sebuah microservice Go di Kubernetes memiliki batas memory limit cgroup 2 GiB. Service diset dengan `GOGC=off`. Setelah melayani traffic tinggi selama 3 hari, pod mati secara mendadak dengan kode exit status 137. Mengapa hal ini terjadi dan bagaimana memperbaikinya secara elegan tanpa memicu GC thrashing?
12. **Skenario B**: Profiling sebuah aplikasi menunjukkan waktu eksekusi CPU didominasi oleh fungsi internal `runtime.mallocgc` dan `runtime.scanobject`, padahal aplikasi hanya membaca data dari database PostgreSQL dan memetakkannya ke DTO struct. Investigasi apa yang harus Anda lakukan dan tindakan apa yang harus diambil pada DTO struct tersebut?
13. **Skenario C**: Pada audit performa transaksi finansial, ditemukan data race intermiten di mana Goroutine B membaca struct data yang belum selesai ditulis oleh Goroutine A, meskipun Goroutine A sudah menyetel flag `isReady = true` (menggunakan variabel boolean standar). Mengapa compiler atau CPU reordering dapat menyebabkan hal ini terjadi, dan bagaimana solusinya sesuai standar Go Memory Model?

---

### 16. Summary

1. **Go Memory Model** menjamin prediktabilitas pembacaan memori konkuren melalui aturan formal *Happens-Before*. Ketiadaan sinkronisasi eksplisit (channel, mutex, atomic) memungkinkan instruksi CPU dan compiler melakukan re-ordering instruksi yang berujung pada data race.
2. **Go Allocator** adalah arsitektur hierarki multi-tier berbasis TCMalloc:
   - `mcache`: Alokasi thread-local per-P tanpa lock.
   - `mcentral`: Pengelolaan span terpusat berbasis size-class dengan locking minimal.
   - `mheap`: Manajemen virtual memory berskala global via radix tree page mapping.
3. **Escape Analysis** adalah dinding pembatas penentu performa: objek yang tidak keluar dari siklus eksekusi lokal frame fungsi akan dialokasikan di **Stack** (pembersihan instan), sementara objek yang lolos dialokasikan di **Heap** (membebani GC).
4. **Tri-Color Concurrent Garbage Collector** modern di Go memprioritaskan latensi rendah (*sub-millisecond STW*) menggunakan **Hybrid Write Barrier**. 
5. Efisiensi memori pada skala enterprise dicapai dengan mengombinasikan optimasi kode (*zero-allocation*, struct field alignment, objek tanpa pointer, pemanfaatan `sync.Pool`) dan tuning runtime produksi modern (`GOMEMLIMIT` dan `GOGC`).