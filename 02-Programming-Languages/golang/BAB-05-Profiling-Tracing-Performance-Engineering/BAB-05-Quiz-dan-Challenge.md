# BAB 05: Quiz, Challenge, & Knowledge Check
**Bab 05: Concurrency Primitives, Channels, & Memory Synchronization**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: M:N Scheduler vs 1:1 OS Threading Model
Jelaskan secara mendalam bagaimana Go Runtime mengelola konkurensi menggunakan model *M:N Scheduler* (arsitektur G-M-P: *Goroutine, Machine, Processor*). Bandingkan dengan model *1:1 threading* pada sistem operasi konvensional dalam konteks:
1. Alokasi memori awal dan pertumbuhan *execution stack* (2KB dynamic stack vs fixed OS stack).
2. Mekanisme dan *overhead cost* dari *context switching* antar-Goroutine dibanding *thread context switch* pada level CPU register.
3. Strategi *work-stealing* dan *sysmon (system monitor)* saat Goroutine melakukan operasi *blocking system call*.

### Soal 1.2: Channel Synchronization Semantics
Pada Go runtime, *channel* bukan sekadar thread-safe queue melainkan instrumen transfer kepemilikan data (*memory ownership transfer*). 
1. Bedakan semantik internal antara *unbuffered channel* (*rendezvous pattern*) dan *buffered channel*. 
2. Jelaskan urutan eksekusi memori (*happens-before relationship*) saat operasi *send* (`ch <- v`) dan *receive* (`<-ch`) berlangsung pada kedua jenis channel tersebut.
3. Kapan tepatnya runtime Go memindahkan Goroutine ke status `waiting` (mengubah state ke `_Gwaiting` dan mendaftarkannya pada *sudog* queue internal channel)?

### Soal 1.3: Evaluasi Deterministik pada `select` Statement
Statement `select` digunakan untuk mengontrol multiple channel operations. 
1. Bagaimana algoritma runtime Go mengevaluasi cabang-cabang `case` yang aktif secara simultan? Mengapa pemilihan cabang bersifat *pseudo-random* dan bukan *top-down evaluation* seperti pada `switch` statement konvensional?
2. Apa dampak implementasi `default` clause terhadap *CPU utilization* jika diletakkan di dalam *tight infinite loop* (`for { select { ... default: } }`)? Jelaskan fenomena *busy-waiting/CPU spinning* yang terjadi.

### Soal 1.4: Semantik Operasional `sync.WaitGroup` dan State Management
`sync.WaitGroup` memiliki counter internal 64-bit yang merepresentasikan state `[counter32, waiter32]`. 
1. Mengapa pemanggilan method `.Add()` harus selalu dilakukan sebelum Goroutine baru di-spawn, bukan di dalam body Goroutine itu sendiri?
2. Apa yang terjadi secara fatal pada runtime ketika counter internal `sync.WaitGroup` bernilai negatif? Mengapa runtime Go memilih untuk melakukan `panic: sync: negative WaitGroup counter` tanpa mekanisme recovery?
3. Jelaskan perbedaan use-case fundamental antara `sync.WaitGroup` dengan *signaling pattern* menggunakan `chan struct{}`.

### Soal 1.5: Data Race vs Race Condition
Dalam literatur rekayasa perangkat lunak konkuren, istilah *Data Race* dan *Race Condition* sering tertukar padahal merujuk pada kelas anomali yang berbeda.
1. Definisikan secara formal perbedaan teknis antara *Data Race* (pada tingkat instruksi memori) dan *Race Condition* (pada tingkat integritas logika aplikasi).
2. Apakah sebuah program Go yang dinyatakan bersih oleh runtime race detector (`go test -race`) dijamin 100% bebas dari *Race Condition*? Berikan analisis logis Anda.
3. Bagaimana instrumen ThreadSanitizer (TSan) pada flag `-race` melacak akses memori konkuren? Apa konsekuensi performa (*CPU overhead* dan *memory footprint*) saat binary dijalankan dengan flag ini di lingkungan testing?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Lifecycle & State Mutation pada Closed Channel
Bedah struktur data internal `hchan` di dalam runtime Go (`src/runtime/chan.go`). 
1. Analisis apa yang terjadi pada register dan memori jika program mengeksekusi:
   - Operasi read dari *closed channel* yang masih memiliki buffer.
   - Operasi read dari *closed channel* yang buffernya kosong.
   - Operasi write ke *closed channel*.
   - Operasi penutupan (`close()`) kedua kali pada channel yang sama (*double close*).
   - Operasi penutupan pada `nil channel`.
2. Jelaskan idiom `v, ok := <-ch` dan bagaimana variabel Boolean `ok` dimanfaatkan untuk mencegah infinite processing loop pada *closed channel*.

### Soal 2.2: Memory Model, Memory Barrier, & Register Caching
Tinjau kode berikut:
```go
var a string
var done bool

func setup() {
    a = "system initialization completed"
    done = true
}

func main() {
    go setup()
    for !done {
    }
    print(a)
}
```
1. Berdasarkan spesifikasi *Go Memory Model*, mengapa program di atas tidak dijamin akan mencetak string `"system initialization completed"` atau bahkan dapat mengalami *infinite loop* permanen jika dikompilasi dengan optimasi compiler tingkat tinggi (`-O2` equivalent)?
2. Jelaskan konsep *instruction reordering* oleh compiler/CPU hardware dan ketiadaan *memory barrier/fence* pada variabel primitif tanpa sinkronisasi eksplisit.
3. Bagaimana paket `sync/atomic` menyelesaikan masalah ini tanpa memerlukan overhead dari lock berbasis kernel/OS?

### Soal 2.3: Diagnosis Root-Cause: Goroutine Leakage
Goroutine leak adalah salah satu penyebab utama degradasi memori bertahap (*silent OOM crash*) di Go production.
1. Analisis kode di bawah ini, tunjukkan di mana letak kebocoran alokasi Goroutine, dan jelaskan mengapa garbage collector (GC) Go tidak dapat membersihkan Goroutine yang macet (*blocked*):
```go
func queryFirstSuccess(ctx context.Context, urls []string) string {
    ch := make(chan string)
    for _, url := range urls {
        go func(u string) {
            res := executeHTTPCall(u)
            ch <- res
        }(url)
    }
    return <-ch
}
```
2. Jelaskan metodologi investigasi profil produksi menggunakan `net/http/pprof` untuk mengisolasi Goroutine leak secara real-time. Informasi spesifik apa yang harus dianalisis dari endpoint `/debug/pprof/goroutine?debug=2`?

### Soal 2.4: Mutex Contention: Barging Mode vs Starvation Mode
Paket `sync.Mutex` mengimplementasikan algoritma hybrid kompleks untuk menghindari *starvation* tanpa mengorbankan *high throughput*.
1. Jelaskan perbedaan mendasar antara *Normal Mode* (*barging strategy*) dan *Starvation Mode* pada `sync.Mutex`.
2. Kondisi ambang batas (*threshold*) apa yang memicu transisi dari Normal Mode ke Starvation Mode?
3. Mengapa pada skenario throughput read yang sangat tinggi, `sync.RWMutex` terkadang menghasilkan performa yang **lebih buruk** dibandingkan `sync.Mutex` standar akibat fenomena *cache-line contention* (*cache bouncing*) pada arsitektur CPU multi-core?

### Soal 2.5: Internal Semantics dari `sync.Pool` & Siklus Garbage Collection
1. Bagaimana struktur data internal `sync.Pool` memanfaatkan konsep *thread-local storage* via `poolLocal` per-P (*Processor*) untuk meminimalisasi *lock contention* antar Goroutine?
2. Jelaskan daur hidup objek di dalam `sync.Pool` saat fase *Stop-The-World* (STW) dan *Concurrent Sweep* pada Garbage Collector Go. 
3. Mengapa `sync.Pool` tidak boleh digunakan sebagai basis implementasi *Stateful Connection Pool* (seperti TCP/Database connection pool) atau *Long-lived Cache*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Goroutine Storm dan Kematian OOM Pasca-Deployment
*Konteks Sistem:*  
Sebuah microservice analitik memproses webhook ingest data telemetri dengan beban puncak 35.000 request/detik. Arsitektur kode awal mengimplementasikan penanganan asynchronous sebagai berikut:
```go
func (h *Handler) IngestWebhook(w http.ResponseWriter, r *http.Request) {
    payload := h.parse(r)
    go func(data Payload) {
        enriched := h.enrichmentService.Process(data) // Memakan waktu 200ms - 2s (I/O bound)
        h.database.Persist(enriched)
    }(payload)
    w.WriteHeader(http.StatusAccepted)
}
```
*Insiden:*  
Beberapa menit setelah load spike terjadi, alokasi memori instance melonjak dari 400MB menjadi 32GB dalam 90 detik. Node crash akibat `OOMKilled` oleh Linux Kernel. Output metrik CPU menunjukkan 100% usage dengan `runtime.morestack` dan `runtime.gcBgMarkWorker` mendominasi profil CPU.

*Pertanyaan Diagnostik:*
1. Mengapa alokasi un-bounded goroutine (`go func()`) menghancurkan stabilitas memori, meskipun stack awal goroutine hanya 2KB? (Analisis dalam konteks *stack growth*, closure allocation escape to heap, dan beban GC pacing).
2. Rancang arsitektur refactoring menggunakan idiom Go terstandarisasi untuk membatasi konkurensi (Backpressure / Bounded Worker Pool / Dynamic Semaphore). Sertakan struktur kendali channel atau sinkronisasi yang digunakan.
3. Bagaimana mekanisme penolakan beban (*load shedding*) jika antrean (*queue*) tugas di memori telah mencapai batas toleransi latensi sistem?

---

### Skenario B: Double-Spending Silent Bug pada Multi-Account Transaction
*Konteks Sistem:*  
Platform pembayaran digital memfasilitasi transfer saldo antar pengguna menggunakan basis data in-memory terdistribusi dengan cache lokal. Pengembang mengamankan mutasi akun menggunakan granular mutex per wallet:

```go
type Wallet struct {
    sync.Mutex
    ID      string
    Balance int64
}

func Transfer(from, to *Wallet, amount int64) error {
    from.Lock()
    defer from.Unlock()

    to.Lock()
    defer to.Unlock()

    if from.Balance < amount {
        return ErrInsufficientFunds
    }

    from.Balance -= amount
    to.Balance += amount
    return nil
}
```

*Insiden:*  
Pada kondisi normal sistem berjalan tanpa kendala. Namun, saat flash sale, ketika ribuan transaksi transfer timbal balik terjadi secara serentak (misal: Transaksi 1 mentransfer dari Akun A ke Akun B, sementara Transaksi 2 mentransfer dari Akun B ke Akun A pada mikrodetik yang sama), sistem membeku (*freeze*). Request timeout massal, server berhenti merespons, dan CPU utilization anjlok ke mendekati 0%.

*Pertanyaan Diagnostik:*
1. Identifikasi secara matematis dan logis akar masalah dari insiden di atas. Kelemahan sinkronisasi apa yang teraktivasi (sebutkan 4 kondisi Coffman yang terpenuhi)?
2. Tuliskan perbaikan kode Go yang deterministik untuk mencegah terjadinya kondisi tersebut dengan menerapkan *Lock Ordering/Lock Hierarchy Pattern* berdasarkan komparasi properti unik resource (`ID`).
3. Bandingkan solusi *Lock Ordering* di atas dengan pendekatan serial execution berbasis *Actor Model / CSP Channel-driven Coordinator*. Apa trade-off latensi dan kompleksitas kodenya?

---

### Skenario C: Bottleneck pada High-Throughput Aggregator: Mutex vs CSP Channel
*Konteks Sistem:*  
Sebuah sistem High-Frequency Trading Telemetry bertugas mengagregasi 1.000.000 metriks numerik per detik dari berbagai thread koneksi jaringan ke dalam sebuah struktur data histogram global di dalam memori.

*Arsitektur yang Diperdebatkan:*
- **Tim Alpha** menyarankan penggunaan pendekatan *Communicating Sequential Processes (CSP)*: Setiap event dikirim ke sebuah `chan Metric` terpusat yang memiliki buffer 100.000, kemudian satu buah worker goroutine membaca channel tersebut dan memutasi map histogram secara eksklusif (bebas dari lock primitives).
- **Tim Beta** menyarankan pendekatan *Shared Memory with Sharded Mutex*: Membagi histogram ke dalam 64 atau 128 *shards*, di mana masing-masing shard dilindungi oleh sebuah `sync.Mutex`. Goroutine produsen menghitung hash dari ID metrik dan memutasi shard yang sesuai secara langsung.

*Pertanyaan Diagnostik:*
1. Mengapa pendekatan Tim Alpha (CSP single consumer terpusat) dipastikan mengalami bottleneck parah pada beban 1.000.000 event/detik? Analisis batasan konkurensi channel internal lock dan overhead context-switch pada unbuffered/buffered single channel.
2. Analisis proposal Tim Beta: Bahaya arsitektur apa pada level CPU hardware yang dapat terjadi jika struct shard array tidak memiliki memori padding (*cache line false sharing*)?
3. Formulasikan rekomendasi arsitektur final Anda untuk mencapai throughput 1.000.000 event/detik dengan latensi sub-milidetik pada Go runtime modern.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Resilient Worker Pool Engine

#### Problem Description
Di lingkungan enterprise, pemrosesan batch tak terbatas (*unbounded batch processing*) sering kali meruntuhkan sistem downstream (seperti database atau payment gateway) akibat tidak adanya kontrol *concurrency flow*, ketiadaan mekanisme *graceful shutdown*, serta ketiadaan proteksi terhadap *worker panic*. 

Anda diminta untuk merancang dan mengimplementasikan sebuah library Worker Pool independen, thread-safe, dan *production-grade* di Go tanpa dependensi eksternal pihak ketiga (*pure standard library*).

#### Functional & Architectural Requirements
1. **Bounded Concurrency & Queue:**
   - Pool harus memiliki kapasitas worker tetap ($N$) dan kapasitas antrean buffer ($M$).
   - Jika antrean penuh, pool harus menyediakan mekanisme *Task Rejection Strategy* yang terukur:
     - Policy A: Block sampai antrean longgar dengan batas waktu (*Timeout Context*).
     - Policy B: Drop task dan kembalikan error eksplisit (`ErrQueueFull`).
2. **Panic Resilience & Self-Healing:**
   - Jika sebuah task memicu runtime panic, worker yang bersangkutan **tidak boleh mati permanen**, dan aplikasi utama **tidak boleh crash**.
   - Pool harus menangkap panic via `recover()`, mengekstrak stack trace, mencatat log kegagalan, dan worker harus siap memproses task berikutnya secara normal.
3. **Graceful Degradation & Shutdown:**
   - Mendukung method `Shutdown(ctx context.Context) error`.
   - Ketika proses shutdown diinisiasi:
     - Pool berhenti menerima task baru (mengembalikan `ErrPoolClosed`).
     - Seluruh task yang sudah berada di dalam internal queue harus dieksekusi hingga tuntas.
     - Operasi shutdown harus menunggu hingga seluruh worker selesai bekerja, atau berhenti paksa jika deadline pada parameter `ctx` terlampaui (*timeout*).
4. **Metrics Exposure:**
   - Sediakan method thread-safe `Stats() PoolStats` yang mengembalikan data atomik:
     - `ActiveWorkers int64`
     - `QueuedTasks int64`
     - `CompletedTasks int64`
     - `FailedTasks int64` (termasuk panic).

#### Constraints & Standard
- Wajib menggunakan primitives standar: `sync`, `sync/atomic`, `context`, `time`.
- Dilarang keras memicu *Data Race*. Validasi penuh dengan `go test -race -count=100`.
- Zero goroutine leak pasca-pemanggilan `Shutdown()`.

#### Expected Contract (API Signature)
```go
package workerpool

import (
    "context"
    "errors"
    "time"
)

var (
    ErrPoolClosed = errors.New("worker pool is closed")
    ErrQueueFull  = errors.New("task queue is full")
)

type Task func(ctx context.Context) error

type PoolStats struct {
    ActiveWorkers  int64
    QueuedTasks    int64
    CompletedTasks int64
    FailedTasks    int64
}

type Pool interface {
    Submit(ctx context.Context, task Task) error
    SubmitWithTimeout(task Task, timeout time.Duration) error
    Shutdown(ctx context.Context) error
    Stats() PoolStats
}

func New(workerCount int, queueSize int) Pool {
    // Implementasikan struktur engine di sini
}
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis sebelum melangkah ke topik lanjutan (Advanced Network Programming, Reflection, & Runtime Internals).

### Saya harus memahami:
- [ ] Arsitektur internal M:N scheduler Go (relasi antara Goroutine `G`, Thread `M`, dan Logical Processor `P`).
- [ ] Anatomi struktur data `hchan`, `waitq`, dan `sudog` di dalam runtime channel.
- [ ] Hukum *Go Memory Model* dan definisi formal relasi *happens-before* pada channel, mutex, dan operasi atomic.
- [ ] Perbedaan siklus hidup starvation vs normal barging mode pada implementasi `sync.Mutex`.
- [ ] Mekanisme deteksi anomali memori oleh ThreadSanitizer (`-race`) dan batas kemampuan deteksinya terhadap logic race condition.
- [ ] Karakteristik performa Goroutine stack (alokasi awal 2KB, dynamic splitting/contiguous stack copying) vs OS thread stack.
- [ ] Dampak alokasi closure pada concurrent loops terhadap escape analysis dan garbage collection overhead.

### Saya tidak perlu menghafal:
- [ ] Angka pasti magic constant internal runtime Go (misal: batas starvation 1ms pada mutex, atau kapasitas pasti buffer sudog cache).
- [ ] Instruksi assembly CPU spesifik yang digenerate oleh compiler untuk *atomic operations* pada berbagai varian arsitektur hardware (misal: perbedaan X86 `LOCK CMPXCHG` vs ARM `LDREX/STREX`).
- [ ] Seluruh baris implementasi low-level dari `runtime/proc.go` dan `runtime/chan.go`.

### Saya harus bisa melakukan:
- [ ] Menganalisis dan membaca Goroutine Stack Dump dari endpoint `pprof` untuk menemukan root-cause *deadlock* atau *goroutine leak*.
- [ ] Menulis tes konkurensi deterministik yang menguji skenario eksekusi paralel tinggi menggunakan flag `-race`.
- [ ] Mengimplementasikan pola *Fan-Out / Fan-In* dan *Bounded Worker Pool* secara idiomatik dan aman dari kebocoran memori.
- [ ] Memilih secara tepat kapan harus menggunakan *Channel communication (CSP)* dan kapan harus menggunakan *Low-level Mutex/Atomic synchronization (Shared Memory)* berdasarkan metrik latensi dan beban sistem.
- [ ] Mengimplementasikan *Graceful Shutdown* sistemik yang mengoordinasikan pembatalan context antar-komponen tanpa menyisakan *orphan goroutines*.