# BAB 06: Quiz, Challenge, & Knowledge Check
**Konkurensi Tingkat Tinggi: Goroutines, Channels, Runtime Scheduler (GMP), dan Sinkronisasi Memori**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Evolusi Alokasi Stack Goroutine vs Thread OS:**
   Jelaskan perbedaan mendasar antara *segmented stack* (Go pra-1.4) dengan *contiguous stack allocation* yang digunakan Go saat ini. Mengapa footprint awal goroutine dapat ditekan hingga ~2 KB sementara OS thread membutuhkan 1–8 MB, dan bagaimana mekanisme runtime mendeteksi serta mengeksekusi penggandaan ukuran stack saat terjadi stack overflow pada fungsi tertentu?

2. **Empat Aksioma Perilaku Channel (Channel Axioms):**
   Analisis perilaku deterministik runtime Go terhadap 4 skenario operasi channel berikut:
   * Mengirim data ke channel bernilai `nil`.
   * Menerima data dari channel bernilai `nil`.
   * Mengirim data ke channel yang telah di-`close()`.
   * Menerima data dari channel yang telah di-`close()`.
   Jelaskan status goroutine (misal: *blocked indefinitely/deadlock*, *panic*, atau mengembalikan zero value) beserta implementasi internal yang menyebabkannya.

3. **Semantik Evaluasi dan Pseudo-Randomness pada Konstruksi `select`:**
   Bagaimana Go runtime mengevaluasi statement `select` ketika terdapat lebih dari satu channel yang siap (*ready*) secara bersamaan? Mengapa Go tidak mengevaluasi case secara sekuensial dari atas ke bawah, bagaimana algoritma permutasi pseudo-random diimplementasikan, dan apa implikasi penambahan blok `default` terhadap pemblokiran pemanggilan goroutine?

4. **Hubungan Formal *Happens-Before* pada Channels:**
   Berdasarkan spesifikasi *The Go Memory Model*, jelaskan relasi formal *happens-before* antara:
   * Pengiriman data pada unbuffered channel dan penyelesaian operasi penerimaan data yang berkorespondensi.
   * Penutupan (*closing*) channel dengan penerimaan nilai zero-value oleh receiver.
   * Pengiriman data ke-$k$ pada buffered channel berkapasitas $C$ dengan penerimaan data ke-$(k - C)$.

5. **Trade-off Mekanisme Sinkronisasi: `sync.Mutex` vs `sync.RWMutex`:**
   Meskipun `sync.RWMutex` secara teoritis lebih unggul untuk beban kerja *read-heavy*, dalam kondisi arsitektur multi-core dengan konkurensi pembacaan sangat tinggi (*massive reader contention*), `sync.RWMutex` dapat mengalami degradasi performa yang lebih buruk daripada `sync.Mutex` standar. Mengapa fenomena *cache-line bouncing* dan atomic counter manipulation pada struct `RWMutex` memicu bottleneck tersebut?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme GMP Scheduler saat Blocking Syscall vs Network Poller:**
   Ketika sebuah Goroutine ($G$) melakukan pemanggilan syscall yang memblokir (misal: *blocking disk I/O* via `entersyscall`) versus *network I/O* via runtime network poller (`netpoll`), jelaskan transisi state yang terjadi pada Processor ($P$) dan Machine/OS Thread ($M$). Kapan $P$ melepaskan $M$ (*handoff*) untuk mencari/membuat $M$ baru, dan kapan $M$ cukup diparkirkan sementara?

2. **Struktur Data Internal Channel (`runtime.hchan`) dan Algoritma Direct-Copy:**
   Bongkar struktur data `runtime.hchan`. Jelaskan fungsi dari `waitq` (`sudog`), circular ring buffer, dan mutex internal `lock`. Dalam kondisi apa Go runtime melakukan optimasi zero-copy (*direct copy* dari stack $G_{sender}$ langsung ke stack $G_{receiver}$) tanpa menyentuh intermediate circular buffer?

3. **Prinsip Deteksi TSan pada `-race` Flag dan Blind Spot-nya:**
   Bagaimana ThreadSanitizer (TSan) yang ditanamkan melalui flag `-race` melacak akses memori menggunakan *shadow memory* dan *state vector clocks*? Mengapa flag `-race` tidak mampu mendeteksi *logical race conditions* (seperti Check-Then-Act race), dan apa konsekuensi overhead CPU/memori saat flag ini diaktifkan di production?

4. **Anatomi dan Mitigasi Goroutine Leaks:**
   Diberikan potongan kode di bawah ini:
   ```go
   func QueryData(ctx context.Context) (string, error) {
       ch := make(chan string)
       go func() {
           val := expensiveExternalCall()
           ch <- val
       }()

       select {
       case res := <-ch:
           return res, nil
       case <-ctx.Done():
           return "", ctx.Err()
       }
   }
   ```
   Identifikasi jenis kebocoran memori yang terjadi jika `ctx` mengalami timeout sebelum `expensiveExternalCall()` selesai. Berapa lama memori goroutine dan objek `val` tertahan di heap, dan bagaimana refaktorisasi 1-baris tanpa mengubah business logic untuk mencegah leak tersebut secara permanen?

5. **Evolusi Preemption: Koperatif (Go < 1.14) vs Signal-Based Asynchronous Preemption (Go >= 1.14):**
   Sebelum Go 1.14, perulangan komputasi murni tanpa pemanggilan fungsi (`for {}`) dapat menyebabkan *scheduler starvation* karena compiler Go menyuntikkan instruksi preemption check (`morestack`) hanya pada prolog fungsi. Bagaimana runtime modern memanfaatkan sinyal POSIX OS (`SIGURG`) untuk memaksa preempt goroutine pada safe-points instruksi mesin tanpa overhead instrumentasi kompilasi berlebih?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike 100x & Thread Exhaustion pada Payment Gateway
Sebuah service microservice pemrosesan transaksi berbasis Go mengalami degradasi performa ekstrem di production saat traffic naik 4x:
* P99 Latency meroket dari 20ms menjadi 3.200ms.
* CPU utilization menyentuh 100% pada container Linux (4 vCPU, 8GB RAM).
* Dump pprof stack trace menunjukkan jumlah goroutine membengkak dari 1.500 menjadi 350.000.
* Lebih dari 70% goroutine tertahan pada state `runtime.gopark` dengan stack trace menunjukkan blok panggilan:
  `sync.runtime_SemacquireMutex` -> `database/sql.(*DB).conn` -> `sync.(*Mutex).Lock`.

**Tugas Diagnostik:**
1. Bedah akar penyebab struktural (*root cause*) mengapa goroutine count meledak padahal pool koneksi database dibatasi (`SetMaxOpenConns(50)`).
2. Bagaimana mekanisme Go runtime menangani contention antrean ribuan goroutine pada single mutex, dan mengapa hal tersebut memicu *cascading scheduler overhead* pada GMP scheduler?
3. Rancang arsitektur proteksi beban (*load shedding*) deterministik menggunakan kombinasi *bounded worker pool* dan channel semaphore yang menjamin latency P99 tetap < 50ms dengan mengorbankan sebagian request melalui status HTTP 429 / 503 (*fail-fast*).

---

### Skenario B: Silent Memory Corruption pada High-Frequency Trading (HFT) Cache Layer
Sebuah cache layer kustom dirancang untuk menyimpan orderbook harga secara lokal tanpa alokasi heap berulang:
```go
type PriceLevel struct {
    BidPrice uint64
    BidQty   uint64
    AskPrice uint64
    AskQty   uint64
}

type MarketCache struct {
    prices *PriceLevel
}

func (m *MarketCache) Update(bPrice, bQty, aPrice, aQty uint64) {
    m.prices = &PriceLevel{
        BidPrice: bPrice,
        BidQty:   bQty,
        AskPrice: aPrice,
        AskQty:   aQty,
    }
}

func (m *MarketCache) Read() PriceLevel {
    if m.prices == nil {
        return PriceLevel{}
    }
    return *m.prices
}
```
Pada lingkungan multi-core ARM64 (AWS Graviton3), modul engine trading sesekali mengeksekusi order dengan harga yang tidak pernah valid (misal: `BidPrice` dari update ke-10, tetapi `BidQty` dari update ke-9, atau crash akibat nil-pointer dereference yang sangat sporadis). Pemeriksaan `-race` pada laptop developer (x86_64) gagal menemukan anomali jika pengujian berjalan singkat.

**Tugas Diagnostik:**
1. Mengapa bug konsistensi ini muncul sangat sering pada arsitektur ARM64 tetapi jarang/sulit terdeteksi pada x86_64? Jelaskan perbedaan model memori (*Store Buffer / Out-of-Order execution vs TSO - Total Store Order*).
2. Tunjukkan secara tepat letak terjadinya *torn read* / *data race* pada pemanggilan `Read()` dan `Update()`.
3. Tuliskan implementasi perbaikan modern zero-allocation yang thread-safe menggunakan pointer swap via `atomic.Pointer[PriceLevel]` dari package `sync/atomic` (Go 1.19+), dan jelaskan memory order guarantee yang diberikan operasi tersebut.

---

### Skenario C: Arsitektur Telemetri Streaming 250.000 Event/Detik
Arsitektur ingest log real-time menerima rata-rata 250.000 log-event per detik yang harus diurai (*unmarshalled*), divalidasi, dan di-batching ke upstream buffer (Kafka producer) setiap 100ms atau setiap 1.000 record terkumpul (mana yang tercapai lebih dulu).

Arsitektur lama menggunakan pattern:
`1 Goroutine Reader -> Unbuffered Channel -> 100 Goroutine Workers -> Buffered Channel -> 1 Batcher Goroutine`.
Arsitektur ini gagal mencapai throughput target, menimbun latency, dan memicu garbage collection (GC) pause yang tidak dapat ditoleransi (> 15ms).

**Tugas Diagnostik:**
1. Mengapa abstraksi channel Go standar menjadi bottleneck utama (*scalability ceiling*) pada throughput ratusan ribu event per detik saat melibatkan context switching antar ratusan worker goroutines?
2. Bagaimana desain alokasi memori pada pattern ini memicu GC pressure, dan bagaimana penerapan `sync.Pool` dapat memotong alokasi heap hingga > 90%?
3. Rancang arsitektur alternatif pengganti antrean channel sentral, menggunakan segmentasi partisi (*sharded ring buffers*) berbasis hashing ID/CPU core ID, serta tentukan trade-off durabilitas vs throughput jika sinkronisasi memory barrier digunakan alih-alih channel locks.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Concurrent Batching Dispatcher Engine
Anda diminta mengimplementasikan sebuah modul Go murni kelas enterprise: **`ConcurrentBatcher[T any, R any]`**. Komponen ini bertindak sebagai buffer adaptif yang menerima item data secara konkuren, memprosesnya dalam batch mikro, dan mengembalikan hasil pemrosesan secara asinkron atau sinkron melalui mekanisme future/promise tanpa menyebabkan goroutine leak atau uncoordinated crash.

#### Persyaratan Fungsional & Teknis:
1. **Generic Engine:** Menggunakan Go Generics: `NewBatcher[T any, R any](cfg Config, handler BatchHandler[T, R])`.
2. **Batching Triggers (Kombinatorial):**
   Batch harus dikirim ke `BatchHandler` jika salah satu dari kondisi berikut terpenuhi:
   * Jumlah item dalam buffer internal mencapai `MaxBatchSize`.
   * Waktu tunggu item tertua dalam batch aktif telah melewati `FlushInterval`.
   * Sistem menerima instruksi graceful shutdown melalui penutupan context.
3. **Mekanisme Backpressure Adaptif:**
   Ketika downstream `BatchHandler` mengalami bottleneck dan kapasitas penampungan antrean penuh (`MaxQueueCapacity`), dispatcher harus menerapkan strategi backpressure yang dapat dikonfigurasi:
   * `Block`: Memblokir producer secara thread-safe hingga ada ruang kosong atau timeout context producer tercapai.
   * `DropOldest`: Mengeliminasi item tertua dalam antrean untuk menerima item baru (pencatatan metrik drop).
   * `FailFast`: Langsung mengembalikan error `ErrQueueFull` kepada caller tanpa blocking.
4. **Zero Goroutine Leak Guarantee:**
   Saat `Close()` atau `context.Done()` dipanggil, seluruh item yang tersisa dalam antrean harus di-flush hingga tuntas (*drain*), downstream batch handler menyelesaikan sisa pemrosesan, dan seluruh goroutine internal dipastikan terminasi (diverifikasi via `runtime.NumGoroutine()`).
5. **Thread Safety & Data Integrity:**
   Wajib lolos eksekusi uji stress race condition: `go test -race -count=5 -cpu=4,8,16`.

#### Batasan Implementasi (Constraints):
* Dilarang menggunakan dependency eksternal pihak ketiga (hanya package standar: `sync`, `sync/atomic`, `time`, `context`, `errors`).
* Dilarang menggunakan `time.Sleep()` untuk polling interval (harus menggunakan `time.Timer` / `time.Ticker` yang dikelola secara presisi untuk menghindari memory leak timer).
* Penggunaan `sync.Mutex` harus diminimalkan pada *hot path* pendaftaran item; utamakan optimasi batch-swap pointer atau bounded channels.

#### Expected Output Test Signature:
```go
func TestBatcher_ThroughputAndZeroLeak(t *testing.T) {
    // 1. Setup dispatcher dengan MaxBatchSize = 100, FlushInterval = 10ms
    // 2. Spawn 50 goroutines produsen, total mengirim 500.000 items
    // 3. Pastikan semua item terproses tanpa data corrupt / lost
    // 4. Trigger Shutdown()
    // 5. Assert: Tidak ada goroutine internal yang tertinggal
}
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal runtime Go Scheduler: Model relasi abstraksi $G$ (Goroutine), $M$ (OS Thread), dan $P$ (Logical Processor), serta algoritma *work-stealing*.
- [ ] Struktur internal struct `hchan`, fungsi dari circular buffer data, antrean `waitq` (`sudog`), serta kondisi optimasi stack direct-copy.
- [ ] 4 Aksioma Channel dan implikasi status runtime dari masing-masing kombinasi (nil/closed vs send/receive).
- [ ] Aturan formal *Happens-Before* dalam The Go Memory Model pada pertukaran data melalui channel, mutex, dan package `sync/atomic`.
- [ ] Mekanisme deteksi data race oleh ThreadSanitizer (`-race`), batasan shadow memory, dan trade-off komputasi saat profiling.
- [ ] Perbedaan interaksi arsitektur hardware terhadap visibilitas memori: Mengapa reordering instruksi pada arsitektur Weakly Ordered (ARM64) mengekspos bug yang tersembunyi pada arsitektur TSO (x86_64).
- [ ] Evolusi preemption scheduling Go: Transisi dari cooperative preemption via `morestack` prolog check ke asynchronous signal-based preemption (`SIGURG`).

### Saya tidak perlu menghafal:
- [ ] Alamat offset biner tepat dari field pada struct `runtime.g` atau `runtime.hchan` internal compiler Go.
- [ ] Detail instruksi perakitan assembly per-platform (misal: op-code biner instruksi CAS/Load-Linked/Store-Conditional pada prosesor ARM).
- [ ] Nilai konstanta internal empiris runtime Go (seperti durasi tepat polling netpoller dalam nanodetik atau konstanta hashing scheduler tick).

### Saya harus bisa melakukan:
- [ ] Menganalisis dump pprof goroutine (`goroutine blocking profile` dan `full stack trace`) untuk mengidentifikasi bottleneck semaphore, starvation, atau deadlock melingkar di sistem production.
- [ ] Memperbaiki bug konkurensi laten seperti goroutine leak yang diakibatkan oleh unbuffered channel tanpa consumer terikat atau context timeout yang tak tertangani.
- [ ] Mengimplementasikan pola sinkronisasi data non-blocking berkinerja tinggi menggunakan generic types `atomic.Pointer[T]` atau `atomic.Value` untuk read-heavy caching.
- [ ] Merancang pipeline pemrosesan data konkuren berskala masif dengan mengintegrasikan backpressure, worker pool dinamis, rate-limiting, dan graceful shutdown terkoordinasi.