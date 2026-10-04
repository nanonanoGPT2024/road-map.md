# BAB 03: Quiz, Challenge, & Knowledge Check
**Bab 03: Struktur Data Komposit, Memory Layout, dan Slice/Map Internals**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi dan Semantik Slice Header:**  
   Jelaskan secara struktural representasi internal dari sebuah *slice* pada Go runtime (`runtime.slice` / `reflect.SliceHeader`). Mengapa melewatkan (*passing*) slice sebagai argumen fungsi bersifat *pass-by-value*, namun mutasi pada elemennya dapat berdampak pada *caller* aslinya? Dalam kondisi apa mutasi tersebut justru terputus (*decoupled*) dari pemanggil?

2. **Perbedaan Fundamental Nil Slice vs Empty Slice:**  
   Bedakan representasi memori, alokasi heap, dan perilaku runtime antara `var s []int` (*nil slice*) dan `s := []int{}` (*empty non-nil slice*). Jelaskan dampaknya terhadap fungsi bawaan seperti `len()`, `cap()`, pengecekan kesetaraan pointer data, serta serialisasi JSON menggunakan `encoding/json`.

3. **Struktur Internal Map Go (`hmap` & `bmap`):**  
   Uraikan arsitektur internal hash map Go (`runtime.hmap`). Jelaskan bagaimana *hash chaining* diimplementasikan menggunakan *bucket* (`runtime.bmap`), peran array `tophash` dalam mempercepat pencarian *key*, dan apa yang memicu proses *growth* (*incremental evacuation/rehashing*).

4. **Array vs Slice: Karakteristik Memori dan Evaluasi Stack vs Heap:**  
   Bandingkan alokasi dan penanganan array bertipe `[1024]byte` dengan slice `[]byte` sebesar 1024 elemen di Go. Bagaimana compiler menentukan apakah array dialokasikan pada *stack frame* atau *escaped* ke *heap*, dan apa implikasi performa *copy-on-assignment* pada array berukuran besar?

5. **Struct Memory Alignment dan Padding Rules:**  
   Pada arsitektur 64-bit (*word size* = 8 byte), jelaskan mengapa `struct { a bool; b int64; c bool }` mengonsumsi 24 byte, sedangkan `struct { b int64; a bool; c bool }` hanya mengonsumsi 16 byte. Sebutkan aturan aligment dasar yang diterapkan oleh compiler Go.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Sub-slice Memory Leak Vulnerability:**  
   Analisis potongan kode berikut dari sudut pandang Garbage Collector (GC):
   ```go
   func ReadTelemetry() []byte {
       largePayload := make([]byte, 100*1024*1024) // 100 MB
       // ... membaca data ke largePayload ...
       return largePayload[:16]
   }
   ```
   Mengapa kode ini berpotensi menyebabkan *memory leak* jangka panjang di sistem produksi? Berikan implementasi koreksi idiomatis dengan karakteristik zero-retention terhadap buffer lama.

2. **Evolusi Algoritma Slice Growth (Go 1.18+):**  
   Sebelum Go 1.18, kapasitas slice dilipatgandakan (2x) jika `< 1024` dan dinaikkan 1.25x jika `>= 1024`. Bagaimana algoritma pertumbuhan kapasitas `growslice` diimplementasikan pada versi Go modern saat ini? Mengapa formula transisi mulus (*smooth transition curve*) dan *memory class sizing* diterapkan?

3. **Fatal Crash pada Concurrent Map Access vs Slice Data Corruption:**  
   Mengapa akses konkuren tanpa sinkronisasi pada `map` menghasilkan crash fatal yang tidak dapat ditangkap oleh `recover()` (`fatal error: concurrent map read and map write`), sedangkan operasi konkuren `append` pada `slice` umumnya "hanya" menyebabkan kehilangan data (*data race/silent data corruption*) tanpa crash langsung? Jelaskan mekanisme internal pendeteksian konkurensi pada `hmap`.

4. **Map Memory Deallocation Paradox:**  
   Jika Anda mengalokasikan 10 juta elemen ke dalam sebuah Go `map[string][1024]byte`, kemudian menghapus seluruh elemen tersebut menggunakan fungsi `delete(m, k)`, apakah konsumsi memori resident (*RSS*) dari proses Go akan berkurang secara signifikan? Mengapa `hmap` tidak pernah menyusutkan jumlah bucket-nya? Bagaimana solusi teknis untuk melepaskan memori tersebut?

5. **Pointer vs Value Receiver pada Mutasi Struct:**  
   Tinjau struct berikut:
   ```go
   type Node struct {
       Data []int
   }
   func (n Node) Add(val int) {
       n.Data = append(n.Data, val)
   }
   ```
   Jika `n.Data` memiliki kapasitas berlebih (`cap > len`), pemanggilan `n.Add(42)` memodifikasi elemen array dasar dari *caller*. Namun, jika kapasitas telah penuh (`cap == len`), modifikasi tersebut tidak terlihat oleh pemanggil. Uraikan secara presisi mekanisme internal yang mendasari anomali perilaku ini.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latensi Garbage Collection Tinggi akibat Pointer-Dense Structs
Sebuah layanan *in-memory cache* menyimpan 50.000.000 objek data pengguna. Struktur data didefinisikan sebagai berikut:
```go
type UserSession struct {
    SessionID   *string
    UserID      *int64
    Metadata    map[string]string
    Permissions []*string
}
```
Meskipun beban CPU request stabil, p99 dan p99.9 latency mengalami lonjakan berkala hingga ratusan milidetik. Profiling CPU menunjukkan bahwa fungsi `runtime.scanobject` dan `runtime.gcDrain` mengonsumsi 40% dari total siklus CPU.
* **Pertanyaan Diagnostik:**
  1. Mengapa keberadaan pointer massal di dalam struct memperlambat fase Mark pada Garbage Collector?
  2. Bagaimana Anda mendesain ulang skema struktur data di atas agar *pointerless* atau ramah terhadap scan GC tanpa mengurangi integritas domain model?

### Skenario B: Crash Fatal Produksi Akibat Dynamic Configuration Map
Sebuah gateway microservice memuat konfigurasi routing dinamis ke dalam variabel global `var RouteTable = make(map[string]BackendTarget)`. Setiap 30 detik, sebuah background goroutine memperbarui route table secara langsung:
```go
func refreshRoutes() {
    newRoutes := fetchFromConsul()
    for k, v := range newRoutes {
        RouteTable[k] = v // Write operation
    }
}
```
Pada saat trafik mencapai 15.000 RPS, aplikasi tiba-tiba terminasi mendadak dengan status exit code 2 dan pesan:  
`fatal error: concurrent map iteration and map write`.
* **Pertanyaan Diagnostik:**
  1. Mengapa penggunaan `sync.Mutex` konvensional di seluruh blok pembacaan route dapat menimbulkan *contention bottleneck* yang parah pada throughput setinggi ini?
  2. Bandingkan dua pendekatan arsitektur untuk menyelesaikan isu ini secara *race-free* dengan performa baca mendekati nol overhead:
     - Menggunakan `sync.RWMutex`.
     - Menggunakan *atomic pointer swap* (`atomic.Pointer[map[string]BackendTarget]`).

### Skenario C: Pembengkakan Memori 200% pada Ingestion Pipeline IoT
Sebuah worker pool memproses paket data biner dari sensor IoT. Setiap detik, 10.000 struct `SensorPacket` dialokasikan ke heap:
```go
type SensorPacket struct {
    IsActive   bool      // 1 byte
    SensorID   int64     // 8 byte
    IsAlert    bool      // 1 byte
    FirmwareVer int32    // 4 byte
    Timestamp  int64     // 8 byte
    Flag       byte      // 1 byte
    Payload    [3]byte   // 3 byte
}
```
Hasil audit infrastruktur menunjukkan konsumsi RAM melonjak 2x lebih besar dari estimasi matematis payload mentah (raw payload 26 byte).
* **Pertanyaan Diagnostik:**
  1. Hitung total ukuran memori aktual dari `SensorPacket` berdasarkan aturan memory alignment pada arsitektur 64-bit dan identifikasi berapa byte padding yang terbuang sia-sia.
  2. Susun ulang (*reorder*) urutan field di dalam struct agar mencapai ukuran sekecil mungkin (*optimal packing*), dan hitung efisiensi penghematan memori yang didapatkan secara persentase.

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Performance Zero-Allocation Circular Byte Ring Buffer**

### Deskripsi Masalah:
Sistem streaming telemetri memerlukan mekanisme buffering data biner sementara berbasis *ring buffer* (*circular buffer*) untuk menampung aliran paket byte mentah yang masuk dari koneksi TCP sebelum diproses oleh batch writer. Implementasi buffer berbasis slice standar sering memicu realokasi, `append` tak terkontrol, serta alokasi memori heap tinggi yang membebani Garbage Collector.

### Requirements:
1. Buat tipe data struct `RingBuffer` dengan kapasitas tetap (*fixed capacity*) yang ditentukan saat inisialisasi: `NewRingBuffer(capacity int) *RingBuffer`.
2. Implementasikan antarmuka:
   - `Write(p []byte) (n int, err error)`: Menulis *slice* byte ke buffer. Jika kapasitas tidak mencukupi, kembalikan error `ErrBufferFull` (tidak boleh melakukan alokasi dinamis baru).
   - `Read(p []byte) (n int, err error)`: Membaca byte dari buffer ke slice tujuan `p`. Jika buffer kosong, kembalikan `0, io.EOF`.
   - `Len() int`: Mengembalikan jumlah byte yang saat ini tersedia untuk dibaca.
   - `Cap() int`: Mengembalikan kapasitas maksimum buffer.
   - `Reset()`: Mengosongkan buffer secara instan tanpa merealokasi array dasar.
3. Thread-safety: Operasi `Read`, `Write`, `Reset`, dan `Len` harus aman dieksekusi secara konkuren oleh banyak goroutine produsen dan konsumen menggunakan `sync.Mutex` atau optimasi *lock-free* atomics.
4. **Memory Constraint:** Struct `RingBuffer` harus dioptimalkan *field alignment*-nya.

### Benchmark & Validation Constraints:
- Operasi `Write` dan `Read` pada *buffer* yang sudah diinisialisasi harus mencapai **0 allocs/op** pada pengujian *benchmark*.
- Jalankan race detector: `go test -race` dan pastikan tidak ada race condition terdeteksi.

### Expected Output:
Sebuah modul Go yang lolos verifikasi benchmark:
```text
BenchmarkRingBuffer_WriteRead-8    50000000    24.1 ns/op    0 B/op    0 allocs/op
PASS
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Representasi memori konkret dari slice header: pointer ke underlying array, length, dan capacity.
- [ ] Aturan pergeseran sub-slice: batas-batas operasi slicing `s[low:high:max]` (*3-index slicing*) dan proteksi kapasitas.
- [ ] Layout internal hash map Go: relasi `hmap`, `bmap`, `tophash`, overflow buckets, dan mekanisme load factor (> 6.5).
- [ ] Mengapa Go map iterasi sengaja dibuat *pseudo-random* oleh Go runtime.
- [ ] Konsep Word Boundary, Aligment Rules, dan Padding Bytes pada kompilasi struct.
- [ ] Perilaku *pointer vs value semantics* ketika memodifikasi slice atau struct di dalam method/fungsi.
- [ ] Mekanisme deteksi race condition internal pada `hmap` yang memicu unrecoverable panic.

### Saya tidak perlu menghafal:
- [ ] Konstanta internal bit exact Go hash map (seperti nilai pasti `loadFactorNum` atau mask bit internal runtime hash).
- [ ] Alamat virtual memory eksak tempat struct dialokasikan oleh compiler.
- [ ] Angka pasti algoritma ekspansi memori runtime untuk setiap kelas ukuran allocator runtime (`sizeclasses.go`).

### Saya harus bisa melakukan:
- [ ] Menghitung manual alokasi ukuran struct dan menyusun ulang urutan field untuk meminimalkan padding byte menggunakan `unsafe.Sizeof` dan `unsafe.Alignof`.
- [ ] Mencegah kebocoran memori akibat retensi backing array pada slice berukuran besar dengan menggunakan fungsi `copy()`.
- [ ] Mendiagnosis dan mengeliminasi bug konkurensi pada struct dan map menggunakan `-race` toolchain bawaan Go.
- [ ] Memilih dengan tepat kapan harus menggunakan `sync.RWMutex`, `sync.Map`, atau `atomic.Pointer` untuk skenario akses pembacaan tinggi.
- [ ] Menulis benchmark Go menggunakan `testing.B` dan memverifikasi metrik alokasi memori melalui `-benchmem`.