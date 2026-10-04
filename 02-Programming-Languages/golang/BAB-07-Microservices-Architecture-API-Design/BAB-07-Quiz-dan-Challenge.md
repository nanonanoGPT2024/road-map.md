# BAB 07: Quiz, Challenge, & Knowledge Check
**Bab 07: Advanced Concurrency, Synchronization Primitives, & Memory Visibility**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Propagasi dan Pembatalan pada `context.Context`
Jelaskan secara mendalam bagaimana pohon pembatalan (*cancellation tree*) bekerja di dalam paket `context`. Ketika sebuah `parent context` dibatalkan via fungsi `cancel()`, bagaimana mekanisme internal Go menyebarkan sinyal pembatalan ke seluruh *child context*? Mengapa `context.Background()` tidak pernah dibatalkan, dan bagaimana goroutine yang memblokir pada `select` case `<-ctx.Done()` dieksekusi kembali oleh scheduler runtime?

### Soal 1.2: Trade-off Ekstrem: `sync.Mutex` vs `sync.RWMutex`
Secara teori, `sync.RWMutex` lebih diunggulkan untuk beban kerja dengan rasio pembaca (*readers*) yang jauh lebih tinggi daripada penulis (*writers*). Namun, dalam arsitektur prosesor *multi-socket* (NUMA) modern dengan *read contention* yang sangat masif, mengapa implementasi `sync.RWMutex` di Go justru dapat menghasilkan degradasi performa (*cache-line bouncing*) yang lebih parah dibandingkan pemakaian `sync.Mutex` biasa atau implementasi *atomic lock-free*?

### Soal 1.3: Anatomi Goroutine Leak Akibat Unbuffered Channel
Ditinjau dari manajemen memori Go Runtime, jelaskan mengapa sebuah goroutine yang mengirim data ke sebuah *unbuffered channel* tanpa adanya penerima (*receiver*) aktif diklasifikasikan sebagai *permanent memory leak*. Mengapa *Garbage Collector* (GC) Go tidak dapat mendeteksi atau mereklamasi memori stack goroutine tersebut, meskipun variabel channel lokal di fungsi pemanggil sudah berada di luar *scope* (tidak lagi terjangkau)?

### Soal 1.4: Invariant dan Race Condition pada `sync.WaitGroup`
Paket dokumentasi Go secara eksplisit melarang pemanggilan `wg.Add()` di dalam *body* goroutine yang baru saja di-*spawn* (misalnya: `go func() { wg.Add(1); ... }()`). Bedah secara internal race condition apa yang terjadi terhadap variabel counter internal `sync.WaitGroup` dan pemanggil `wg.Wait()`. Apa konsekuensi deterministik dan non-deterministik dari pelanggaran aturan ini?

### Soal 1.5: Sequential Consistency dan Atomics (`sync/atomic`) vs Mutex
Operasi primitif pada `sync/atomic` (seperti `atomic.CompareAndSwapInt64` atau `atomic.StorePointer`) menawarkan performa tinggi tanpa *context switch* tingkat OS/runtime. Jelaskan bagaimana *memory barrier* (*hardware memory fence*) yang di-injeksi oleh operasi atomic memastikan *happens-before relationship* (sesuai spesifikasi Go Memory Model), dan jelaskan keterbatasan operasi atomic murni saat Anda perlu memproteksi multi-field invariant pada sebuah *struct*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Transisi State `sync.Mutex`: Normal Mode vs Starvation Mode
Go Runtime memperkenalkan *Starvation Mode* pada implementasi `sync.Mutex` (sejak Go 1.8). 
1. Apa kondisi presisi (*threshold*) yang memicu transisi dari *Normal Mode* ke *Starvation Mode*?
2. Bagaimana semantik penyerahan kepemilikan lock (*lock handoff*) berubah saat mutex berada dalam *Starvation Mode*?
3. Apa trade-off throughput keseluruhan vs pencegahan *tail latency* (p99/p999 latency) yang dihasilkan dari mekanisme ini?

### Soal 2.2: Siklus Hidup Objek dan Victim Cache pada `sync.Pool`
`sync.Pool` sering disalahartikan sebagai in-memory cache berdurasi panjang. Jelaskan bagaimana interaksi antara `sync.Pool` dan Go Garbage Collector bekerja sejak Go 1.13 (mekanisme *victim cache*). Jika sistem mengalami *high-throughput allocation burst* tepat sebelum siklus STW (*Stop-The-World*) / GC concurrent phase berjalan, kapan objek di dalam pool benar-benar di-sweep dan di-deallokasi dari heap? Mengapa pool lokal menggunakan kombinasi *private pointer* dan *shared ring-buffer* (`poolDequeue`) dengan akses *lock-free CAS* vs *work-stealing*?

### Soal 2.3: Cache-Line Bouncing dan False Sharing pada Concurrency Go
Perhatikan potongan kode berikut:
```go
type Metrics struct {
    readOps  uint64
    writeOps uint64
}
```
Jika `readOps` di-update secara masif oleh 32 goroutine di core CPU yang berbeda via `atomic.AddUint64`, dan `writeOps` di-update oleh 32 goroutine lainnya secara independen, jelaskan fenomena *False Sharing* yang terjadi pada CPU L1/L2 cache-line (64 bytes). Bagaimana cara Anda merekayasa memori *struct* tersebut (menggunakan struct padding) untuk mengeliminasi cache coherency invalidation traffic antar-core?

### Soal 2.4: Mekanisme Low-Level Channel: `hchan`, `sudog`, dan Runtime Scheduler
Ketika sebuah goroutine melakukan operasi receive `<-ch` pada channel kosong, runtime Go tidak memblokir kernel thread OS (M), melainkan memarkir goroutine (G). 
Jelaskan interaksi struktural antara:
1. `hchan` (termasuk lock internal, circular buffer, dan `waitq`).
2. Struktur `sudog` yang dialokasikan untuk membungkus goroutine G.
3. Fungsi runtime `gopark()` dan pasangannya `goready()` saat goroutine lain akhirnya mengirimkan data ke channel tersebut.

### Soal 2.5: Deteksi Data Race dengan ThreadSanitizer (`-race`)
Flags `-race` pada Go toolchain menggunakan modifikasi algoritma ThreadSanitizer v2 (TSan). Jelaskan bagaimana compiler menginjeksi instrumentasi pada setiap instruksi pembacaan dan penulisan memori (*memory access shadow mapping*). Mengapa executable dengan flag `-race` mengonsumsi 2x hingga 10x lebih banyak memori dan mengalami penurunan CPU throughput hingga 2x-20x? Sebutkan satu jenis data race tersembunyi yang **tidak dapat** dideteksi oleh TSan secara deterministik jika jalur kode (*code path*) tersebut tidak dieksekusi selama masa runtime uji!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Goroutine Explosion & Out-of-Memory (OOM) pada Edge Proxy
Sebuah API Edge Proxy berbasis Go menangani rata-rata 15.000 RPS. Selama lonjakan trafik jaringan lokal, upstream payment service pihak ketiga mengalami degradasi laten dari 50ms menjadi 15 detik sebelum akhirnya timeout. Dalam 45 detik, jumlah goroutine pada Edge Proxy melonjak dari 800 menjadi 350.000 goroutine, menyebabkan konsumsi memory melonjak drastis hingga Linux Kernel OOM-Killer mematikan proses utama (`exit code 137`).

Setelah dilakukan post-mortem, ditemukan potongan kode HTTP Client berikut:
```go
func ForwardPayment(ctx context.Context, req *PaymentRequest) (*PaymentResponse, error) {
    ch := make(chan *PaymentResponse)
    go func() {
        // http.Client tanpa konfigurasi Timeout eksplisit pada Transport
        resp, err := client.Post("https://upstream-pay/charge", "application/json", req.Body)
        if err == nil {
            ch <- parseResponse(resp)
        }
    }()

    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    case res := <-ch:
        return res, nil
    }
}
```

**Pertanyaan Diagnostik:**
1. Di mana akar penyebab goroutine leak pada kode di atas saat `ctx` mencapai timeout terlebih dahulu sebelum HTTP call selesai?
2. Mengapa setting `Timeout` pada level `http.Client` tidak cukup jika `Transport` bawaan kehabisan connection pool?
3. Tuliskan refaktor lengkap kode di atas dengan mengimplementasikan channel buffering yang tepat, penanganan context propagation ke level `http.NewRequestWithContext`, dan pembersihan resource body request/response untuk menjamin zero-leak.

---

### Skenario B: Race Condition dan Token Invalidation Loop pada Distributed Cache Layer
Sebuah sistem autentikasi terdistribusi menggunakan cache lokal in-memory berbasis `sync.Map` untuk menyimpan *access token* yang validitasnya diperiksa secara berkala. Jika token kedaluwarsa, sistem harus mengambil token baru dari OAuth Provider pusat. Hanya **satu** goroutine yang diizinkan memanggil OAuth Provider untuk memperbarui token (karena rate-limit yang ketat), sementara request lain yang datang bersamaan harus menunggu token baru tersebut siap.

Berikut implementasi awal yang menyebabkan insiden produksi:
```go
var tokenCache sync.Map // key: string, value: *Token

func GetAuthToken(tenantID string) (*Token, error) {
    val, exists := tokenCache.Load(tenantID)
    if exists {
        tok := val.(*Token)
        if time.Now().Before(tok.ExpiresAt) {
            return tok, nil
        }
    }

    // Mengambil token baru jika expired atau tidak ada
    newToken, err := fetchOAuthTokenFromRemote(tenantID)
    if err != nil {
        return nil, err
    }

    tokenCache.Store(tenantID, newToken)
    return newToken, nil
}
```

**Pertanyaan Diagnostik:**
1. Identifikasi *race condition check-then-act* (Time-of-Check to Time-of-Use) yang menyebabkan fenomena *Thundering Herd* atau *Stampede Request* ke OAuth Provider pusat saat masa kadaluarsa token tiba.
2. Mengapa `sync.Map` gagal menyelesaikan masalah sinkronisasi *in-flight computation* ini?
3. Rekayasa solusi menggunakan paket `golang.org/x/sync/singleflight` yang dipadukan dengan strategi caching lokal berlapis untuk memastikan:
   * Tepat 1 HTTP request ke remote provider per kedaluwarsa token.
   * Goroutine lain secara elegan menunggu (*share the result*).
   * Penanganan error tidak men-cache failure state secara permanen.

---

### Skenario C: Bottleneck Desain Arsitektur: Dynamic Goroutines vs Worker Pool vs Token Bucket Semaphore
Anda diminta merancang subsistem ingestion pipeline yang memproses 50.000 log record berukuran rata-rata 2 KB per detik yang datang dari Kafka broker. Setiap log record memerlukan dekompresi data, validasi schema, dan penulisan batch ke database ClickHouse. Target sistem adalah menggunakan resources seminimal mungkin (CPU limit 4 core, RAM limit 1 GB) tanpa memicu GC throttling yang berlebihan.

Terdapat 3 proposal desain arsitektur konkuren:
* **Proposal 1 (Dynamic Spawning):** Tiap record log yang di-poll dari Kafka langsung dieksekusi dalam goroutine mandiri (`go process(record)`).
* **Proposal 2 (Fixed Worker Pool via Channel):** Menggunakan `N = NumCPU * 2` worker goroutines yang terus-menerus membaca record dari sebuah unbuffered channel sentral.
* **Proposal 3 (Bounded Semaphore Pipeline):** Menggunakan dynamic goroutines yang dibatasi oleh weighted-semaphore (`golang.org/x/sync/semaphore`) dipadukan dengan channel ber-buffer per-batch (`[]LogRecord`) dan `sync.Pool` untuk buffer dekompresi.

**Pertanyaan Diagnostik:**
1. Analisis performa dan alokasi memory (heap allocation & GC overhead) dari Proposal 1. Mengapa alokasi stack 2 KB per goroutine dapat melumpuhkan sistem pada throughput 50.000 RPS di lingkungan container dengan RAM 1 GB?
2. Apa kelemahan Proposal 2 jika salah satu worker mengalami bottleneck I/O sinkron saat batch-flush ke ClickHouse? Bagaimana *lock contention* pada antrean buffer channel internal mempengaruhi utilisasi CPU?
3. Buat evaluasi perbandingan komprehensif mengapa Proposal 3 (atau variasi ring-buffer) paling unggul dari perspektif Go Memory Model, cache-locality, dan isolasi kegagalan (*backpressure*).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Concurrent Batch Pipeline with Backpressure, Graceful Shutdown, & Dynamic Throttling (`ResilientBatchWorkerPool`)

#### Problem Statement
Anda ditugaskan membangun engine inti *streaming batch processor* di Go yang mampu menerima stream data kontinu, mengelompokkannya ke dalam *micro-batch* berdasarkan kuota ukuran (**Size-based**) atau batas waktu tunggu (**Time-based / Ticker**), memproses batch tersebut secara konkuren menggunakan pool pekerja yang adaptif, dan mendukung *Graceful Shutdown* secara deterministik tanpa kehilangan 1 data pun saat menerima sinyal `SIGINT`/`SIGTERM`.

#### Requirements & System Specifications
1. **Engine Interface:**
   Engine harus diimplementasikan sebagai sebuah struct thread-safe:
   ```go
   type BatchProcessor[T any] struct {
       // internal state synchronization primitives
   }

   func NewBatchProcessor[T any](cfg Config, handler BatchHandler[T]) *BatchProcessor[T]
   func (bp *BatchProcessor[T]) Submit(ctx context.Context, item T) error
   func (bp *BatchProcessor[T]) Shutdown(ctx context.Context) error
   ```
2. **Batching Rules (Dual Trigger):**
   * *Batch Size*: Ketika akumulasi item mencapai `cfg.MaxBatchSize` (misal 500 item), batch langsung dikirim ke antrean eksekusi worker tanpa menunggu timer.
   * *Batch Timeout*: Jika kuota ukuran belum tercapai, namun durasi `cfg.FlushInterval` (misal 100ms) habis, batch parsial yang ada harus segera di-flush.
3. **Adaptive Backpressure & Non-blocking Safety:**
   * Jika internal buffer atau antrean worker penuh, pemanggilan `Submit()` harus menghormati `ctx.Done()`. Jangan pernah melakukan alokasi unbuffered channel tanpa bound yang bisa mengakibatkan OOM.
4. **Deterministic Graceful Draining:**
   * Saat `Shutdown(ctx)` dipanggil:
     1. Stop menerima item baru via `Submit()` (kembalikan `ErrEngineShutdown`).
     2. Drains seluruh item yang masih tersisa di buffer lokal dan buat batch terakhir.
     3. Tunggu seluruh batch aktif selesai dieksekusi oleh worker pool.
     4. Jika shutdown melebihi timeout pada `ctx`, kembalikan `context.DeadlineExceeded` dengan melampirkan jumlah item yang belum sempat diproses.
5. **Zero Data Race:**
   * Wajib lolos pengetesan dengan Go race detector: `go test -race -v -count=10 ./...`

#### Constraints
* **Hanya gunakan Standard Library** (`sync`, `sync/atomic`, `context`, `time`, `os/signal`) dan modul resmi `golang.org/x/sync` (diperbolehkan menggunakan `errgroup` atau `semaphore`). Tidak boleh memakai library messaging/queueing pihak ketiga.
* Gunakan **Generics Go 1.18+** agar pipeline dapat memproses tipe data apa pun (`[T any]`).
* Alokasi heap harus diminimalisir; implementasikan penggunaan kembali *slice* memory buffer batch.

#### Expected Output
* File kode sumber yang modular, clean, berstandar idiomatis Go (`gofmt`, tanpa deadlocks).
* Unit testing komprehensif yang memvalidasi:
  * Concurrent Submission (minimal 50 goroutine serentak men-submit 100.000 item).
  * Time-based flush trigger verifikasi (batch ter-flush walau item < `MaxBatchSize`).
  * Graceful shutdown verifikasi (semua submitted item diproses utuh saat shutdown di-trigger di tengah-tengah beban pemrosesan).

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan engineering Anda sebelum melangkah ke topik arsitektur sistem tingkat lanjut berikutnya:

### Saya harus memahami:
- [ ] Aturan formal Go Memory Model: Definisi eksisnya *Happens-Before relationship* antara channel communication, goroutine creation/destruction, dan mutex lock/unlock.
- [ ] Arsitektur internal runtime scheduler Go (Model M:P:G: Machine, Processor, Goroutine) dan bagaimana *preemptive scheduling* (berbasis signal sysmon sejak Go 1.14) bekerja saat goroutine menjalankan tight loop.
- [ ] Semantik internal starvation mode pada `sync.Mutex` vs normal mode spin-locking.
- [ ] Alasan mendasar mengapa copy-by-value pada primitive sinkronisasi (`sync.Mutex`, `sync.WaitGroup`, `sync.Cond`) merupakan bug fatal (*pass by pointer requirement*).
- [ ] Perbedaan fungsionalitas antara `sync.Cond` vs Channel dalam implementasi *broadcast notifications*.
- [ ] Mekanisme deteksi deadlock Go runtime: Mengapa Go hanya mendeteksi deadlock global (seluruh goroutine tertidur) dan gagal mendeteksi sub-deadlock (kebocoran sebagian goroutine).

### Saya tidak perlu menghafal:
- [ ] Nilai eksak konstanta internal runtime Go (misal: konstanta `mutexStarvationThresholdNs = 1e6`, atau kapasitas presisi internal ring-buffer scheduler). Cukup pahami rasionalitas desainnya.
- [ ] Implementasi assembly tingkat rendah per arsitektur CPU (AMD64 vs ARM64) untuk instruksi atomic, selain memahami bahwa mereka menggunakan instruksi atomic hardware (seperti `LOCK CMPXCHG` pada x86).
- [ ] Urutan baris per baris kode sumber fungsi `runtime.gopark()`. Pahami perannya dalam state transition goroutine dari `_Grunning` ke `_Gwaiting`.

### Saya harus bisa melakukan:
- [ ] Menulis pipeline konkuren berbasis channel dengan pemenuhan kaidah *single-writer closure* (channel hanya boleh ditutup oleh pengirim/goroutine yang memproduksinya).
- [ ] Mengidentifikasi dan membasmi *goroutine leaks* di kode produksi menggunakan tool profiling `pprof` (analisis profil `goroutine` dan `trace`).
- [ ] Mengisolasi *critical section* secara optimal guna meminimalisir durasi penahanan lock (*lock contention minimization*).
- [ ] Menggunakan `golang.org/x/sync/errgroup` untuk orkestrasional komputasi paralel multi-task yang aman dengan penanganan kegagalan (*error short-circuiting*).
- [ ] Menjalankan dan menganalisis laporan dari ThreadSanitizer via perintah `go test -race` dan `go build -race` pada pipeline CI/CD enterprise.