# BAB 10: Quiz, Challenge, & Knowledge Check
**Bab 10: Advanced Concurrency, Synchronization Primitives, & The Go Memory Model**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Contiguous Stacks vs Segmented Stacks
Jelaskan evolusi alokasi memori stack goroutine dari implementasi *segmented stack* (pra-Go 1.4) ke *contiguous stack*. Bagaimana mekanisme `runtime.morestack` mengeksekusi stack copying, dan apa dampaknya terhadap overhead pointer invalidation serta fenomena *hot-split problem* pada eksekusi loop fungsi rekursif?

### Soal 1.2: Anatomi Internal Struktur Channel (`hchan`)
Secara struktural, Go channel adalah wrapper sinkronisasi berbasis alokasi heap. Bedah komponen internal dari struct `runtime.hchan` (meliputi `buf`, `elemsize`, `lock`, `sendq`, dan `recvq`). Mengapa channel yang unbuffered (`buf = nil` atau `dataqsiz = 0`) dapat mengeksekusi *direct copy* antar-goroutine stack (`sudog.elem`), dan bagaimana lock pada `hchan` tetap menjamin memory safety meskipun operasinya berlabel "channel communication"?

### Soal 1.3: Go Memory Model & Relasi "Happens-Before"
Dalam spesifikasi resmi *Go Memory Model*, definisikan secara matematis relasi *Happens-Before* ($\prec$). Analisis keabsahan kode berikut: Jika Goroutine A melakukan inisialisasi terhadap variabel global non-atomik `data = 42` lalu memanggil `close(ch)`, dan Goroutine B mendeteksi `<-ch`, apakah pembacaan `data` oleh Goroutine B dijamin bernilai `42` pada arsitektur CPU dengan Weak Memory Ordering (seperti ARM64)? Buktikan dengan aturan formil *Happens-Before*.

### Soal 1.4: Dynamic Behavior `sync.Mutex`: Normal vs Starvation Mode
Jelaskan algoritma adaptif internal pada `sync.Mutex` yang membedakan **Normal Mode** dan **Starvation Mode**. Parameter runtime apa yang memicu transisi dari Normal ke Starvation Mode, bagaimana status kepemilikan lock dialihkan langsung via scheduler queue, dan apa trade-off latensi *tail latency (p99)* versus *raw throughput* pada fase transisi ini?

### Soal 1.5: Semantik `sync.Cond` vs Spurious Wakeup
Mengapa `sync.Cond` mewajibkan adanya instansiasi `sync.Locker` yang di-lock sebelum pemanggilan `.Wait()`, dan mengapa evaluasi kondisi predicate *harus* selalu dieksekusi di dalam loop `for !condition { cond.Wait() }` alih-alih `if` statement? Jelaskan bahaya *spurious wakeup* dan interaksi signal/broadcast dalam context switching thread pool sistem operasi.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Siklus Hidup `sync.Pool`, CPU Contention, & GC Epoch
Struktur `sync.Pool` menggunakan representasi array `[P]poolLocal` per-logical processor (P). Jelaskan bagaimana mekanisme *private* (`private interface{}`) dan *shared list* (`shared poolChain`) bekerja untuk meminimalisasi CPU cache contention. Bagaimana mekanisme *lock-free work stealing* diimplementasikan saat processor P kehabisan alokasi lokal, dan apa yang terjadi secara eksak pada objek di dalam `sync.Pool` saat *Stop-The-World* (STW) / GC sweeping phase (kaitkan dengan varian `poolLocal` dan `poolVictim` pada Go runtime modern)?

### Soal 2.2: Memory Reordering & Pitfall Double-Checked Locking
Perhatikan potongan kode inisialisasi singleton berikut:
```go
type SafeState struct {
    data *Payload
}
var instance *SafeState
var mu sync.Mutex

func GetInstance() *SafeState {
    if instance == nil { // Check 1
        mu.Lock()
        defer mu.Unlock()
        if instance == nil { // Check 2
            instance = &SafeState{data: &Payload{Val: 100}}
        }
    }
    return instance
}
```
Tanpa penggunaan `sync.Once` atau `sync/atomic`, jelaskan skenario instruksi assembly reordering (baik di level compiler maupun CPU out-of-order execution) yang menyebabkan goroutine pengakses membaca instance yang *partially initialized* (pointer `instance` tidak nil, namun pointer `data` masih nil atau corrupted).

### Soal 2.3: Cache Line Bouncing & False Sharing pada Atomic Counters
Sebuah distributed counter diimplementasikan menggunakan slice: `type ShardedCounter [8]atomic.Int64`. Saat dieksekusi oleh 8 goroutine paralel secara intensif pada mesin 8-core CPU, performa throughput justru drop drastis hingga 70% dibanding single-core. Identifikasi akar masalah pada level arsitektur L1/L2 cache line (False Sharing / MESI Protocol). Tuliskan definisi struct korektif yang memanfaatkan struct padding (`cpu.CacheLinePadSize`) untuk mengisolasi boundary cache line!

### Soal 2.4: Diagnostik Goroutine Leak via Blocked Channel & Finalizer Failure
Perhatikan kasus produksi berikut:
```go
func QueryFirstResponse(ctx context.Context, replicas []string) string {
    ch := make(chan string)
    for _, r := range replicas {
        go func(node string) {
            ch <- fetch(node)
        }(r)
    }
    return <-ch
}
```
Jelaskan mekanisme runtime yang menyebabkan goroutine leak pada kode di atas setelah respons pertama diterima. Mengapa runtime Garbage Collector tidak dapat mendaur ulang (freeing) alokasi memori goroutine yang terblokir pada channel send, meskipun variabel channel `ch` sudah keluar dari scope stack pemanggil dan tidak lagi dapat diakses?

### Soal 2.5: Deep Dive Assembly `sync/atomic` vs Mutex Syscall
Jelaskan perbedaan mendasar instruksi tingkat assembly arsitektur x86_64 antara eksekusi `atomic.CompareAndSwapInt64` (instruksi `LOCK CMPXCHG`) dengan `sync.Mutex.Lock()` ketika terjadi kontensi tinggi. Pada titik instruksi mana `sync.Mutex` menghentikan instruksi CPU *active spinning* (`PAUSE`) dan memanggil runtime scheduler via `runtime.gopark` untuk mendelegasikan eksekusi goroutine ke status waiting?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike & Read-Lock Thrashing pada Service Catalog
* **Kasus:** Sebuah microservice katalog produk menangani 250.000 RPS (Read: 98%, Write: 2%). Service menggunakan `sync.RWMutex` untuk memproteksi map in-memory cache. Terjadi degradasi performa masif saat p99 latency melonjak dari 1.2 ms menjadi 450 ms, disertai CPU utilization melonjak ke 100% pada semua core, padahal network bandwidth dan memory heap masih jauh di bawah batas toleransi.
* **Gejala Profiler:** `pprof` CPU dump menunjukkan konsumsi CPU didominasi oleh `sync.(*RWMutex).RLock` dan `sync.(*RWMutex).RUnlock` yang saling berebut memodifikasi atomik reader counter di cache line yang sama.
* **Pertanyaan Diagnostik:**
  1. Mengapa pola penggunaan `sync.RWMutex` dengan frekuensi read sangat tinggi pada multi-core server (32+ core) dapat memicu *cache invalidation storm* pada L3 cache?
  2. Rancang arsitektur cache pengganti yang thread-safe menggunakan pendekatan **Copy-On-Write (COW)** berbasis `atomic.Pointer` atau **Striped/Sharded Lock Map**. Jelaskan trade-off memori dan latensi dari kedua solusi tersebut!

### Skenario B: Distributed Order Settlement Engine Race Condition
* **Kasus:** Sebuah financial engine memproses pemotongan saldo concurrent menggunakan goroutine worker. Terjadi selisih saldo (balance mismatch) pada 0.001% transaksi bernilai tinggi. Kode produksi menggunakan struktur channel fan-out worker pool:
```go
type Account struct {
    Balance int64
}

func (a *Account) Deduct(amount int64) bool {
    current := atomic.LoadInt64(&a.Balance)
    if current >= amount {
        // Simulasi high load scheduler interruption
        runtime.Gosched()
        return atomic.CompareAndSwapInt64(&a.Balance, current, current-amount)
    }
    return false
}
```
* **Insiden:** Dalam tes load testing masif, beberapa transaksi valid di-reject (CAS gagal), dan pada evaluasi saldo, terjadi kondisi di mana penarikan dana lolos melebihi limit saldo (overdrawn).
* **Pertanyaan Diagnostik:**
  1. Identifikasi *Time-of-Check to Time-of-Use (TOCTOU)* bug pada implementasi `Deduct` di atas! Mengapa pemanggilan `CAS` tunggal tanpa loop mitigasi menyebabkan kegagalan konsistensi?
  2. Rekonstruksi fungsi `Deduct` tersebut menjadi wait-free / lock-free atomic loop yang formal dan tahan terhadap intervensi preemptive scheduler, lengkap dengan validasi saldo negatif!

### Skenario C: Graceful Shutdown Failure pada Real-Time Stream Processor
* **Kasus:** Daemon Go memproses streaming ingestion via Kafka, mendistribusikannya ke 50 worker goroutine yang menulis batch ke ClickHouse via buffering channel. Saat instance menerima sinyal `SIGTERM`, sistem memanggil handler shutdown. Namun, 5-10% batch data terakhir hilang (data loss), dan beberapa goroutine memicu panic: `send on closed channel`.
* **Arsitektur Eksisting:**
```go
var jobs = make(chan Batch, 1000)

func stop() {
    close(jobs)
    // Menunggu worker secara manual menggunakan time.Sleep(5 * time.Second)
}
```
* **Pertanyaan Diagnostik:**
  1. Bedah titik kegagalan arsitektur shutdown di atas yang memicu race condition: pengiriman data baru oleh Kafka consumer goroutine ke channel `jobs` yang sudah ditutup vs terminasi dini oleh `time.Sleep`.
  2. Rancang pola **Orchestrated Graceful Drain Pipeline** yang presisi tanpa `time.Sleep`, memanfaatkan gabungan `sync.WaitGroup`, `context.WithCancelCause`, channel koordinasi dua arah, dan runtime draining validation!

---

## 4. Chapter Challenge

### Tantangan Praktis: Lock-Free High-Performance Ring Buffer Task Queue (Bounded SPMC / MPMC)

#### Problem
Library channel bawaan Go memiliki overhead lock internal (`hchan.lock`) yang dapat menjadi bottleneck pada sistem I/O ultra-low-latency (seperti sistem order execution finansial atau network packet processor) yang membutuhkan jutaan operasi per detik dengan determinisme latensi sub-mikrodetik.

#### Requirements
1. **Implementasi Struktur:** Bangun struktur data Ring Buffer berkuran tetap (*bounded*) thread-safe bernama `DisruptorQueue[T any]` dengan prinsip Lock-Free / Wait-Free, memanfaatkan paket `sync/atomic`.
2. **Kapasitas Ukuran:** Ukuran buffer harus bernilai *power-of-two* ($2^N$) agar operasi modulo penentuan indeks slot menggunakan bitwise AND (`index & (capacity - 1)`).
3. **Mekanisme Backpressure:**
   - Produser harus menunggu (*spin/yield/block*) jika buffer penuh tanpa menyebabkan CPU lock-up (gunakan exponential backoff: spin `PAUSE` $\to$ `runtime.Gosched()` $\to$ sleeper / notification).
   - Konsumen harus dapat membaca event dalam urutan yang tepat tanpa data corruption atau double consumption.
4. **Zero-Allocation Execution:** Operasi `Push(item T) bool` dan `Pop() (T, bool)` tidak boleh mengalokasikan memori baru di heap (0 allocs/op) selama masa runtime aktif setelah inisialisasi buffer selesai.
5. **Memory Barrier:** Gunakan atomic load-acquire dan store-release semantics untuk memastikan integritas memori pada saat item data ditulis sebelum indeks urutan (sequence) dipublikasikan.

#### Constraints
- Dilarang mengimpor library concurrency pihak ketiga.
- Dilarang menggunakan `sync.Mutex`, `sync.RWMutex`, atau primitives `chan` bawaan Go di dalam hot path `Push`/`Pop`.
- Wajib lolos pengetesan flag race detector Go: `go test -race -cpu 4,8,16 -count=5`.
- Wajib memiliki pengujian benchmark throughput: minimal $15.000.000$ op/sec pada modern multi-core x86_64/ARM64.

#### Expected Output
1. File implementasi `queue.go` berisi struct `DisruptorQueue[T any]`, konstruktor `NewDisruptorQueue[T](size int)`, method `Push(val T)`, `Pop() (T, bool)`, serta utilitas mitigasi *False Sharing* via cache line padding.
2. File pengujian `queue_test.go` yang memvalidasi integritas data: 1.000.000 data unik diproduksi dan seluruh 1.000.000 data harus dikonsumsi tanpa ada yang duplikat, hilang, atau corrupt under race condition testing.
3. Hasil output benchmark performa (`BenchmarkDisruptorQueue` vs standard Go Channel buffered).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Model memori internal goroutine (stack frame growth dari 2KB, dynamic stack copying via contiguous memory).
- [ ] Representasi data `runtime.hchan`, siklus pengiriman direct stack copy `sudog` vs buffer ring queue.
- [ ] Aturan formil *Go Memory Model: Happens-Before* pada inisialisasi package, goroutine spawn, channel operations, mutex lock/unlock, dan `sync.Once`.
- [ ] Perilaku internal `sync.Mutex` mode starvation, dynamic active spinning (syarat multi-core, P > 1), dan transisi runtime `gopark` / `goready`.
- [ ] Arsitektur internal `sync.Pool`: struktur `poolLocal`, P-indexed storage, pinning thread (`runtime_procPin`), lock-free stealing via double-ended queues (`poolChain`), serta interaksi STW Garbage Collection.
- [ ] Masalah arsitektur CPU: Cache Lines (64-byte), Cache Coherency (MESI), CPU Memory Barriers, dan False Sharing.
- [ ] Semantik pembacaan dan penulisan memory secara atomik (`atomic.Load`, `atomic.Store`, `atomic.CompareAndSwap`, `atomic.Pointer`).

### Saya tidak perlu menghafal:
- [ ] Nilai konstanta numerik hardcoded runtime (contoh: batas waktu 1ms starvation mode pada `sync.Mutex`, konstanta `active_spin = 4`, atau `sysmon` tick period).
- [ ] Opcode spesifik bytecode assembly x86_64 atau ARM64 untuk instruksi low-level (cukup memahami implikasi fungsional seperti instruksi `LOCK` prefix atau `DMB` memory barrier).
- [ ] Implementasi internal scheduler code C-like dalam direktori `/src/runtime/proc.go` secara baris-per-baris.

### Saya harus bisa melakukan:
- [ ] Mendeteksi dan merekonstruksi kode yang mengandung goroutine leak menggunakan alat profiler `net/http/pprof` dan static trace.
- [ ] Menganalisis dan memperbaiki race condition tersembunyi dengan interpretasi log stack trace `go test -race`.
- [ ] Mengimplementasikan pola sinkronisasi konkurensi tingkat lanjut (Worker Pools, Fan-In/Fan-Out, Semaphore, Cancellation Pipeline, Dynamic Sharded Mutex).
- [ ] Mengoptimalkan kode concurrent throughput tinggi dengan menghilangkan False Sharing menggunakan struct alignment & cache-padding (`[64]byte`).
- [ ] Merancang gracefully closing multi-stage concurrent pipelines tanpa risiko panic `send on closed channel` atau data loss.