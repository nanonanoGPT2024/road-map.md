# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Modern Android & Kotlin Coroutines/Flow Internal**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Transformasi Bytecode, Continuation Passing Style (CPS), dan State Machine
Jelaskan secara mendalam bagaimana Kotlin Compiler mentransformasikan sebuah fungsi dengan modifier `suspend` menjadi bytecode JVM biasa. Uraikan peran interface `Continuation<T>`, parameter sintetis `$completion`, class turunan `SuspendLambda` / `ContinuationImpl`, serta bagaimana variabel lokal dan *suspension points* (titik suspensi) direpresentasikan sebagai label numerik dalam sebuah struktur kontrol *state machine* (`switch/tableswitch`). Mengapa eksekusi coroutine tidak memblokir thread sistem operasi pada tingkat kernel saat mencapai suspension point?

### Soal 1.2: Anatomi dan Mekanisme CoroutineContext
`CoroutineContext` diimplementasikan secara struktural menyerupai kombinasi antara tipe *Indexed Set* dan *Heterogeneous Map*. Uraikan:
1. Hubungan tipe data antara `CoroutineContext`, `Element`, dan `Key<E>`.
2. Algoritma operasi penambahan operator `plus` (`+`) pada `CoroutineContext` (khususnya penanganan `CombinedContext`).
3. Bagaimana mekanisme resolusi context inheritance bekerja saat coroutine baru diinisialisasi melalui coroutine builder (`launch` / `async`) dari sebuah `CoroutineScope` induk?

### Soal 1.3: Structured Concurrency dan Propagasi Kegagalan
Dalam paradigma *Structured Concurrency*, kegagalan (*uncaught exception*) pada satu child coroutine dapat membatalkan seluruh hierarki coroutine di bawah parent yang sama. Jelaskan:
1. Siklus hidup (state transitions) dari sebuah `Job` (`New`, `Active`, `Completing`, `Cancelling`, `Cancelled`, `Completed`).
2. Perbedaan fundamental antara `CancellationException` dengan exception turunan lainnya dalam mekanisme propagasi pembatalan.
3. Alur komprehensif bagaimana suatu exception non-cancellation dialirkan dari leaf node (child terdalam) menuju root node, serta kapan `CoroutineExceptionHandler` dieksekusi.

### Soal 1.4: Kontrak Eksekusi Cold Flow vs. Hot Flow
Ditinjau dari perspektif arsitektur reaktif dan alokasi memori internal:
1. Apa perbedaan mendasar dalam siklus emisi data antara *Cold Stream* (`Flow`) dan *Hot Stream* (`SharedFlow` / `StateFlow`)?
2. Bagaimana `SharedFlow` mengelola array buffer internal, pointer `head`, replay cache, dan suspended emitters ketika kapasitas buffer mencapai batas maksimal?
3. Mengapa pemanggilan operator terminal seperti `.collect()` pada Cold Flow akan selalu menginisialisasi ulang seluruh rantai operator upstream, sedangkan pada Hot Flow tidak?

### Soal 1.5: Isolasi Kegagalan: `Job` vs. `SupervisorJob`
Diberikan sebuah hierarki coroutine dengan parent scope. Uraikan perbedaan mendasar implementasi internal penanganan error antara `Job()` dan `SupervisorJob()`:
1. Mengapa meletakkan `SupervisorJob()` sebagai parameter argument pada coroutine builder seperti `launch(SupervisorJob()) { ... }` merupakan sebuah *anti-pattern* umum yang tidak memberikan proteksi supervisi terhadap child di dalamnya?
2. Bagaimana seharusnya `SupervisorJob` diintegrasikan secara benar ke dalam lifecycle komponen Android (misalnya pada custom scope di layer Data/Repository)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Thread Starvation dan Saturasi `Dispatchers.IO` vs `Dispatchers.Default`
Secara default, `Dispatchers.IO` dan `Dispatchers.Default` berbagi kumpulan thread pool yang sama (*shared worker threads* pada `LimitingDispatcher` / `CoroutineScheduler`). 
- Jelaskan skenario di mana operasi blocking I/O legacy (seperti pemanggilan database SQLite non-reactive atau network read lama tanpa timeout) dapat menyebabkan *thread starvation*.
- Bagaimana mekanisme `Dispatchers.IO.limitedParallelism(x)` memitigasi starvation tersebut tanpa mengorbankan alokasi thread global aplikasi?
- Apa dampak performa yang terjadi jika developer secara ceroboh mengeksekusi komputasi intensif CPU di dalam `Dispatchers.IO`?

### Soal 2.2: Context Preservation Invariant dan `flowOn` Operator
Dalam implementasi engine `kotlinx.coroutines.flow`, terdapat aturan ketat: *Flow collection execution and emission must happen within the same CoroutineContext*.
```kotlin
// Kode Bermasalah:
fun fetchPrices(): Flow<Double> = flow {
    withContext(Dispatchers.IO) {
        emit(networkApi.getPrice()) // Throws IllegalStateException
    }
}
```
1. Jelaskan alasan teknis mengapa runtime Flow secara eksplisit melarang pemanggilan `emit()` dari context yang berbeda dengan context collector dan memunculkan error context preservation violation!
2. Bagaimana operator `flowOn` secara internal menyelesaikan masalah ini dengan menyisipkan buffer `Channel` (melalui `ChannelFlow`) di antara upstream emitter dan downstream collector?

### Soal 2.3: `Dispatchers.Unconfined`, Event Loop, dan Risiko StackOverflow
1. Bagaimana cara kerja internal `Dispatchers.Unconfined` dalam mengeksekusi coroutine hingga suspension point pertama, dan thread mana yang mengambil alih eksekusi setelah resumed?
2. Dalam kondisi seperti apa pemanggilan berantai coroutine pada `Dispatchers.Unconfined` dapat mengakibatkan *StackOverflowError* atau reentrancy bug?
3. Bagaimana Kotlin coroutine runtime menggunakan struktur `EventLoop` internal untuk mencegah stack explosion pada recursive resumptions?

### Soal 2.4: Lifecycle-Aware Flow Collection di Android: Evaluasi Kritis
Evaluasi dua pendekatan konsumsi data stream Flow di layer UI (Activity/Fragment):
- **Pendekatan A:** Menggunakan `lifecycleScope.launchWhenStarted { flow.collect { ... } }` (deprecated).
- **Pendekatan B:** Menggunakan `lifecycleScope.launch { repeatOnLifecycle(Lifecycle.State.STARTED) { flow.collect { ... } } }`.

Jelaskan secara mendalam dari perspektif lifecycle coroutine: mengapa Pendekatan A dapat menyebabkan *resource/upstream leaking* dan *unnecessary background processing* meskipun view sedang berada di latar belakang (background state), dan bagaimana Pendekatan B merekonstruksi serta membatalkan coroutine tree secara deterministik mengikuti lifecycle event Android?

### Soal 2.5: Bridge Non-Cancellable Code dan Continuation Leaks
Saat mengonversi listener berbasis callback legacy ke dalam bentuk suspending function menggunakan `suspendCancellableCoroutine`:
```kotlin
suspend fun LocationClient.awaitCurrentLocation(): Location = suspendCancellableCoroutine { cont ->
    val listener = object : LocationListener {
        override fun onLocation(location: Location) {
            cont.resume(location)
        }
    }
    requestLocationUpdates(listener)
    // Titik evaluasi
}
```
1. Masalah fatal apa yang terjadi pada memori dan alur eksekusi jika coroutine pemanggil dibatalkan (*cancelled*) sebelum `onLocation` terpanggil pada cuplikan kode di atas?
2. Tuliskan implementasi perbaikan mutlak menggunakan `cont.invokeOnCancellation` untuk membatalkan listener platform native, dan jelaskan mengapa `resume()` tidak boleh dipanggil dua kali jika terjadi *race condition* antara pembatalan dan emisi data native.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Produksi Skala Besar — Starvation, Worker Deadlock, dan ANR Cascade
Sebuah aplikasi e-commerce enterprise dengan puluhan juta pengguna aktif mengalami lonjakan drastis angka *Application Not Responding* (ANR) hingga mencapai 3.2% setelah rilis versi baru. Tim infrastruktur mengamati bahwa ANR tidak hanya terjadi di thread Main, tetapi worker thread juga macet total.

Berdasarkan thread dump Android Vitals:
- Ditemukan 64 thread dari pool `DefaultDispatcher-worker-*` berada dalam status `WAITING` atau `TIMED_WAITING` pada pemanggilan socket native blocking JNI dan parsing payload JSON raksasa.
- Komponen rendering UI (yang menggunakan `Dispatchers.Main.immediate`) mulai membeku karena beberapa coroutine UI menunggu hasil `withContext(Dispatchers.Default)` yang tertahan di antrean eksekusi (*task queue starvation*).
- Tim engineer sebelumnya menggabungkan tracking telemetry analitik, caching disk, dan sinkronisasi data katalog dalam satu scope global yang tidak memiliki batas paralelisme.

**Pertanyaan Diagnostik & Arsitektural:**
1. Analisis akar penyebab sistemik bagaimana kehabisan thread pada coroutine dispatcher pool dapat melumpuhkan rendering UI meskipun `Dispatchers.Main` memiliki dedicated Looper.
2. Rancang strategi arsitektural komprehensif untuk mengisolasi resource pool: Tentukan pemisahan dispatcher, konfigurasi `limitedParallelism`, dan manajemen antrean IO vs CPU task.
3. Berikan konfigurasi step-by-step untuk melakukan audit thread dump coroutine saat runtime menggunakan `kotlinx-coroutines-debug` pada internal build untuk melacak lokasi tepat coroutine yang menggantung (*hung/leaked coroutines*).

---

### Skenario B: Kasus Finansial — Concurrency Race Condition pada State Mutasi & Double Debit
Sebuah aplikasi neobank mengalami insiden finansial: Sejumlah nasabah melaporkan saldo mereka terpotong dua kali (*double debit*) saat melakukan otorisasi transaksi pada jaringan internet yang tidak stabil (flapping network).

Investigasi awal pada `PaymentViewModel` menemukan kode berikut:
```kotlin
class PaymentViewModel(
    private val paymentRepository: PaymentRepository
) : ViewModel() {

    private val _paymentState = MutableStateFlow<PaymentState>(PaymentState.Idle)
    val paymentState: StateFlow<PaymentState> = _paymentState.asStateFlow()

    fun submitPayment(transactionId: String, amount: BigDecimal) {
        if (_paymentState.value is PaymentState.Processing) return

        viewModelScope.launch {
            _paymentState.value = PaymentState.Processing
            try {
                val result = paymentRepository.executeDebit(transactionId, amount)
                _paymentState.value = PaymentState.Success(result)
            } catch (e: Exception) {
                _paymentState.value = PaymentState.Error(e.message)
            }
        }
    }
}
```

Pada UI layer, tombol submit memicu `submitPayment()` setiap kali tombol diklik. Ketika latency tinggi dan user menekan tombol secara agresif (*rage clicks*), terjadi celah waktu sepersekian milidetik yang menyebabkan dua coroutine diluncurkan bersamaan sebelum state `Processing` terpasang.

**Pertanyaan Diagnostik & Arsitektural:**
1. Bedah secara mendalam kelemahan kode di atas dari perspektif *atomic state transition* dan *thread safety* (suspension points vs thread preemption). Mengapa evaluasi `if (_paymentState.value is ...)` gagal mencegah *concurrent execution*?
2. Mengapa penggunaan `Mutex` atau primitif atomik (`AtomicBoolean` / `compareAndSet`) lebih valid di sini daripada sekadar mengandalkan `Dispatchers.Main`?
3. Rancang ulang implementasi `PaymentViewModel` tersebut menggunakan pendekatan atomik murni (misalnya: CAS operation pada state, atau integrasi operator `Flow` berbasis channel processing seperti `.conflate()` / UI-event flattening) yang menjamin secara matematis bahwa tidak akan pernah ada lebih dari satu operasi transfer yang tereksekusi secara simultan untuk identitas transaksi yang sama.

---

### Skenario C: Kasus Skalabilitas & Desain Sistem — Real-Time Ticker & Backpressure Collapse
Anda sedang mendesain sistem charting bursa saham real-time (Crypto/Stock Ticker) di Android. Backend memancarkan update harga melalui WebSocket dengan frekuensi ekstrem (hingga 5.000 update/detik pada jam sibuk/market opening). 

Di sisi Android:
- Data diterima oleh WebSocket client pada background thread.
- Data dialirkan ke repository, difilter, dihitung indikator teknikalnya (MA, RSI), lalu ditampilkan pada custom charting UI Canvas di Main thread.
- Main thread hanya mampu me-render frame pada 60fps/120fps (1 frame setiap ~8.3ms hingga 16.6ms).
- Percobaan awal menggunakan `MutableSharedFlow` default mengakibatkan *OutOfMemoryError* (OOM) dan UI stuttering (jank masif) karena collector UI tidak mampu mengimbangi laju upstream (klasik kasus *backpressure mismatch*).

**Pertanyaan Diagnostik & Arsitektural:**
1. Analisis kelemahan penggunaan strategi buffer default pada `SharedFlow` / `Channel` dalam menangani throughput sebesar 5.000 ops/detik terhadap alokasi heap Android.
2. Evaluasi trade-off arsitektural dari tiga strategi mitigasi backpressure berikut untuk use case ini:
   - `conflate()`
   - `buffer(capacity = X, onBufferOverflow = BufferOverflow.DROP_OLDEST)`
   - Windowing/Sampling berbasis waktu (misalnya `sample(16.milliseconds)`)
3. Tuliskan arsitektur data pipeline dari WebSocket hingga UI: Di layer mana kalkulasi indikator teknikal harus dieksekusi, di layer mana *downsampling* harus dilakukan, dan bagaimana implementasi konkret pipeline Kotlin Flow yang menjamin rendering 60/120 FPS tanpa alokasi memori yang memicu *Garbage Collection (GC) thrashing*.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Resilient Offline-First Synchronization Engine
Rancang dan bangun sebuah modul engine sinkronisasi data (*Data Sync Engine*) offline-first skala enterprise menggunakan Kotlin Coroutines & Flow murni (tanpa library reactive pihak ketiga seperti RxJava).

#### Problem Statement
Aplikasi lapangan untuk logistik membutuhkan sinkronisasi ribuan record data audit secara lokal (Room DB) ke remote server. Jaringan di lapangan sering putus-nyambung (*lossy network*), baterai perangkat terbatas, dan pengiriman event tidak boleh menyebabkan UI tersendat atau memori bocor saat activity/fragment di-destroy oleh Android OS (misal karena konfigurasi berubah atau process death).

#### Requirements
1. **Dynamic Rate-Limiting Dispatcher:** Bangun eksekutor yang membatasi konkurensi upload paralel maksimal $N$ task (default: 3 worker paralel) menggunakan `limitedParallelism` atau Coroutine Channel, bukan dengan membuat thread manual.
2. **Backpressure & Batching Pipeline:** Aliran data transaksi dari database lokal harus di-stream menggunakan `Flow`, di-batch secara adaptif (misal: kirim per 50 item atau setiap window waktu 500ms, mana yang tercapai lebih dulu) sebelum dikirimkan ke network endpoint.
3. **Resilient Retry Policy dengan Exponential Backoff & Jitter:** Jika transmisi gagal karena `IOException`, engine harus mengulang secara otomatis dengan rumus interval:
   $$T = \min(T_{\max}, T_{\text{base}} \times 2^{\text{attempt}}) \pm \text{jitter}$$
   Jika exception adalah `HttpUnauthorized (401)`, engine harus menghentikan seluruh antrean seketika, men-trigger mekanisme refresh token secara atomik (single-flight execution), lalu melanjutkan antrean tanpa membuat duplikasi transaksi.
4. **Lifecycle-Aware, Zero-Leak Memory Safety:** Engine harus mengekspos `StateFlow<SyncStatus>` yang mengabarkan progres sinkronisasi (`Idle`, `Syncing(percentage)`, `Failed(error)`). UI harus mengonsumsi state ini secara aman tanpa memicu background processing saat app diminimize.
5. **Circuit Breaker Mechanism:** Jika terjadi kegagalan berturut-turut sebanyak 5 kali, sinkronisasi harus otomatis di-pause selama 30 detik (state `CircuitOpen`) sebelum mencoba masuk ke state `Half-Open`.

#### Constraints
- Wajib mematuhi kaidah *Structured Concurrency*: Menggunakan parent custom `CoroutineScope` terikat dengan lifecycle application daemon, dengan `SupervisorJob` terisolasi.
- Mutasi state internal (seperti penghitungan attempt, status circuit breaker) wajib thread-safe tanpa menggunakan keyword `synchronized` Java (gunakan `Mutex`, `AtomicReference`, atau aktor berbasis Channel).
- Tidak boleh terjadi alokasi memori linear ($O(N)$) yang menyebabkan GC pressure saat memproses antrean $100.000$ transaksi lokal.

#### Expected Output
1. File implementasi Kotlin murni: `ResilientSyncEngine.kt`.
2. Unit Test komprehensif menggunakan `kotlinx-coroutines-test` (`StandardTestDispatcher`, `runTest`, `advanceTimeBy`, `Turbine` untuk flow testing) yang memverifikasi:
   - Mekanisme batching berbasis threshold ukuran dan waktu.
   - Perilaku Exponential Backoff saat failure disimulasikan.
   - Isolasi kegagalan (satu task gagal tidak mematikan scope sync engine utama).
   - Eksekusi atomic single-flight saat refresh token terjadi.

---

## 5. Knowledge Check & Checklist

Tinjau penguasaan materi Anda terhadap bab ini secara objektif.

### Saya harus memahami:
- [ ] Mekanisme transformasi kode Kotlin suspend ke JVM bytecode via State Machine dan objek Continuation Passing Style (CPS).
- [ ] Peran mendalam interface `CoroutineContext`, `Element`, `Key`, serta algoritma penggabungan context menggunakan operator `+`.
- [ ] Perbedaan internal siklus hidup `Job` vs `SupervisorJob` dan alur perambatan exception (kapan exception ditelan, diteruskan, atau memicu crash).
- [ ] Arsitektur internal `StateFlow` dan `SharedFlow`: buffer allocation, emitter suspension, backpressure handling, dan perbedaan deterministik dibanding cold `Flow`.
- [ ] Bahaya lifecycle Android legacy (`launchWhenX`) vs pendekatan deterministik (`repeatOnLifecycle`, `flowWithLifecycle`).
- [ ] Batasan threading model Android: Hubungan antara `Dispatchers.Default`, `Dispatchers.IO`, thread pool sharing, dan pemanfaatan `limitedParallelism`.
- [ ] Invarian preservasi context (`Context Preservation`) pada Kotlin Flow dan prinsip kerja operator `flowOn`.

### Saya tidak perlu menghafal:
- [ ] Nilai konstanta numerik internal JVM bytecode instruction (misal: kode opcode spesifik untuk state machine switch).
- [ ] Implementasi algoritma red-black tree atau struktur data mikro di balik internal compiler synthetic classes.
- [ ] Tanda tangan method biner yang digenerate otomatis oleh compiler (`$completion: Continuation`, `label: Int`) selama memahami konsep CPS secara arsitektural.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis ANR dan coroutine deadlock melalui interpretasi mentah Android/JVM Thread Dump dan Coroutine Dump.
- [ ] Merancang thread-safe state holder di ViewModel menggunakan `StateFlow` dan primitif sinkronisasi non-blocking (`Mutex`, CAS) untuk mencegah race condition.
- [ ] Mengonversi callback asinkronus platform native/C++ ke suspending API tanpa memicu memory leak menggunakan `suspendCancellableCoroutine` dan cancellation handler yang tepat.
- [ ] Menangani stream data throughput tinggi (high-frequency) menggunakan kombinasi operator backpressure Flow (`conflate`, `buffer`, `sample`, `debounce`) tanpa memicu stuttering/GC pressure.
- [ ] Menulis unit test deterministik untuk kode asynchronous kompleks menggunakan `TestScope`, `StandardTestDispatcher`, dan virtual time manipulation (`advanceTimeBy`).