# BAB 06: Quiz, Challenge, & Knowledge Check
**Reactive Streams & Asynchronous Flow**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Cold Stream vs Hot Stream Lifecycle
Jelaskan perbedaan mendasar antara *Cold Stream* (`Flow`) dan *Hot Stream* (`SharedFlow`/`StateFlow`) dalam konteks alokasi sumber daya, waktu eksekusi kode produsen (*producer block*), dan persistensi data ketika tidak ada *collector* aktif. Bagaimana *suspension lifecycle* memengaruhi *producer* pada masing-masing jenis stream?

### Soal 1.2: Mekanisme Backpressure: Suspending Flow vs Reactive Streams `request(n)`
Spesifikasi *Reactive Streams* (seperti RxJava atau Project Reactor) mengimplementasikan protokol *pull-based backpressure* eksplisit berbasis sinyal `Subscription.request(long n)`. Jelaskan bagaimana Kotlin Coroutines `Flow` menyelesaikan masalah *backpressure* tanpa parameter ukuran buffer eksplisit `request(n)`, dan bagaimana mekanisme *suspension cooperativity* berperan di level JVM call stack.

### Soal 1.3: Prinsip Exception Transparency
Kotlin Flow secara ketat menegakkan aturan *Exception Transparency*.
1. Mengapa memanggil blok emisi di dalam `try-catch` seperti:
   ```kotlin
   flow {
       try { emit(value) } catch (e: Throwable) { /* handle */ }
   }
   ```
   dianggap sebagai anti-pattern berat dan melanggar prinsip desain Flow?
2. Bagaimana operator `catch` bekerja secara internal untuk menangani kegagalan *upstream* tanpa menelan kegagalan *downstream*?

### Soal 1.4: Context Preservation dan Pelanggaran Emisi Lintas-Konteks
Mengapa kode berikut secara deterministik melemparkan `IllegalStateException` saat dijalankan?
```kotlin
fun fetchPrices(): Flow<Double> = flow {
    withContext(Dispatchers.IO) {
        emit(loadFromRemote()) // Mengapa ini dilarang?
    }
}
```
Jelaskan konsep *Context Preservation*, peran operator `flowOn`, serta bagaimana engine Flow memeriksa kepatuhan `CoroutineContext` saat fungsi `emit` dieksekusi.

### Soal 1.5: Taksonomi Semantik: `StateFlow`, `SharedFlow`, dan `Channel`
Bandingkan `StateFlow`, `SharedFlow`, dan `Channel` berdasarkan kriteria berikut:
- *Multicasting capability* (Unicast vs Multicast).
- Penanganan *equality check* (`equals()`) pada emisi nilai berturut-turut yang identik.
- Karakteristik *buffer exhaustion strategy* saat kapasitas terlampaui.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Concurrency Bottleneck pada Operator Flattening
Diberikan tiga skenario transformasi data asinkron menggunakan operator:
- `flatMapConcat`
- `flatMapMerge` (dengan `concurrency = DEFAULT_CONCURRENCY`)
- `flatMapLatest`

Jika *upstream* memancarkan 1.000 event per detik dan setiap pemanggilan transformasi *downstream* membutuhkan waktu 100 ms I/O:
1. Bedah apa yang terjadi pada memori heap dan *thread pool* pada masing-masing operator.
2. Operator mana yang berisiko menyebabkan *unbounded memory growth*, dan mana yang berpotensi menyebabkan pembatalan job (*job cancellation cascading*) secara terus-menerus?

### Soal 2.2: Memory Leak dan Deadlock pada Konfigurasi `SharingStarted`
Sebuah sistem backend menggunakan `flow.shareIn(scope, started = SharingStarted.Eagerly, replay = 1000)`.
1. Apa implikasi struktural jika `scope` yang digunakan adalah *application-wide scope* (misal: `GlobalScope` atau *unbounded custom singleton scope*), namun *collector*-nya memiliki siklus hidup pendek (*ephemeral*)?
2. Mengapa kombinasi `SharingStarted.WhileSubscribed()` dengan parameter `stopTimeoutMillis` dan `replayExpirationMillis` krusial untuk mencegah fenomena *upstream churn* pada arsitektur terdistribusi/koneksi WebSocket?

### Soal 2.3: Perilaku Lossy vs Non-Lossy: `buffer()`, `conflate()`, dan `collectLatest()`
Ketika downstream collector mengalami degradasi performa (*slow consumer*):
1. Telusuri trace eksekusi internal saat menggunakan `buffer(capacity = 2, onBufferOverflow = BufferOverflow.DROP_OLDEST)` dibandingkan dengan `conflate()`.
2. Apa perbedaan semantik mendasar antara emisi yang "dibuang di buffer" oleh `conflate()` versus emisi yang "prosesnya dibatalkan di tengah jalan" oleh `collectLatest()`? Kapan penggunaan `collectLatest()` justru menjadi ancaman integritas data (misal: *partial state writes*)?

### Soal 2.4: Bridging Reactive Streams: Interoperabilitas Context & MDC Propagation
Saat menjembatani `org.reactivestreams.Publisher` ke Kotlin `Flow` (via `asFlow()`) dan kembali ke RxJava/Reactor (via `asPublisher()`), masalah umum yang terjadi pada enterprise tracing adalah hilangnya konteks diagnostik (seperti Slf4j MDC / Micrometer Tracing context).
1. Mengapa context switching antara thread *Reactive Streams Engine* (Netty EventLoop/Scheduler) dan Coroutine *Dispatcher* memutus MDC propagation secara *default*?
2. Bagaimana mekanisme mutasi `CoroutineContext` dengan memanfaatkan `ThreadContextElement` untuk menjamin konsistensi *tracing span* di sepanjang *stream pipeline*?

### Soal 2.5: Internal Channel Coroutine Leak pada Operator `produceIn`
Perhatikan cuplikan berikut:
```kotlin
fun monitorSystem(): ReceiveChannel<Telemetry> {
    return telemetryFlow.produceIn(serviceScope)
}
```
Jika konsumen hanya membaca 5 elemen pertama menggunakan `channel.receive()` lalu mengabaikan objek `ReceiveChannel` tersebut tanpa memanggil pembatalan:
1. Apa status coroutine internal yang dibuat oleh `produceIn` di dalam `serviceScope`?
2. Jelaskan struktur memori dan rantai referensi yang menyebabkan kebocoran coroutine dan memori, serta bagaimana mitigasi yang sesuai dengan paradigma *Structured Concurrency*.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Critical Out-of-Memory Incident pada Ingestion Pipeline IoT
**Latar Belakang:**
Sebuah gateway microservice bertugas memproses telemetri dari 50.000 perangkat IoT. Setiap perangkat mengirim paket status setiap 50 ms melalui protokol MQTT. Pipeline pemrosesan diimplementasikan menggunakan Kotlin Coroutines:
```kotlin
mqttEventFlow
    .flowOn(Dispatchers.IO)
    .flatMapMerge(concurrency = 256) { packet ->
        flow {
            val validated = validator.validate(packet)
            val enriched = enricher.enrich(validated)
            emit(enriched)
        }
    }
    .flowOn(Dispatchers.Default)
    .onEach { enrichedPacket ->
        databaseWriter.writeToTimescaleDB(enrichedPacket)
    }
    .launchIn(serverScope)
```
**Insiden:**
Pada jam beban puncak, sistem mengalami lonjakan latensi tajam pada `TimescaleDB` (waktu tulis naik dari 2 ms menjadi 450 ms). Dalam 3 menit, JVM mengalami crash dengan error `java.lang.OutOfMemoryError: Java heap space`. Analisis dump heap menunjukkan jutaan objek `Continuation` dan `MqttPacket` menggantung di antrean memori.

**Pertanyaan Diagnostik:**
1. Di mana letak kesalahan arsitektural pada pemilihan operator dan manajemen *backpressure* pada pipeline di atas?
2. Mengapa isolasi `flowOn(Dispatchers.Default)` tidak melindungi sistem dari lonjakan heap saat downstream (`databaseWriter`) melambat?
3. Rancang ulang pipeline tersebut dengan menerapkan mekanisme kontrol aliran (*rate limiting* / *batching* / *bounded buffer with drop policy*) yang aman tanpa memicu crash JVM. Sertakan pseudocode/solusi Kotlin.

---

### Skenario B: Race Condition dan State Loss pada Engine Transaksi Dompet Digital
**Latar Belakang:**
Sebuah core ledger engine menangani pembaruan saldo akun menggunakan `StateFlow` untuk menyinkronkan snapshot saldo ke downstream audit-trail logger dan push notification service:
```kotlin
class WalletAccount(val accountId: String) {
    private val _balanceState = MutableStateFlow(LedgerSnapshot(balance = BigDecimal.ZERO, sequence = 0L))
    val balanceState: StateFlow<LedgerSnapshot> = _balanceState.asStateFlow()

    suspend fun applyCredit(amount: BigDecimal, transactionId: String) {
        val current = _balanceState.value
        val newSnapshot = LedgerSnapshot(
            balance = current.balance.add(amount),
            sequence = current.sequence + 1L
        )
        // Simulasi validasi external asynchronous
        ledgerAuditClient.verifyTx(transactionId)
        _balanceState.value = newSnapshot
    }
}
```
**Insiden:**
Saat dilakukan pengujian beban dengan eksekusi paralel tinggi (100 concurrent requests masuk serentak untuk akun yang sama), ditemukan bahwa:
- Saldo akhir tidak konsisten (jauh lebih rendah dari total kredit yang masuk).
- Downstream audit logger yang mengonsumsi `balanceState.collect { ... }` kehilangan lebih dari 40% pembaruan sequence angka (beberapa sequence terlewati).

**Pertanyaan Diagnostik:**
1. Analisis kegagalan *thread-safety* dan kondisi *race condition* pada mutasi `_balanceState.value`. Mengapa `StateFlow` tidak bertindak sebagai *atomic transactional variable*?
2. Mengapa downstream collector kehilangan event sequence transaksi tertentu? Jelaskan konsep *conflation* dan *structural equality check* pada `StateFlow`.
3. Rekonstruksi implementasi class `WalletAccount` agar:
   - Pembaruan saldo bersifat *strictly atomic* dan *thread-safe* bebas race condition.
   - Semua event transaksi dijamin terkirim ke downstream tanpa terpotong (*zero message loss*).

---

### Skenario C: Trade-off Migrasi Arsitektur Reaktif: Project Reactor (Spring WebFlux) ke Kotlin Flow
**Latar Belakang:**
Sebuah bank investasi sedang mengevaluasi modernisasi layer orkestrasi trading valuta asing (Forex). Sistem saat ini berbasis Java dengan Spring WebFlux + Project Reactor:
```java
public Flux<TradeConfirmation> executeOrder(Flux<OrderRequest> orders) {
    return orders
        .publishOn(Schedulers.boundedElastic())
        .filter(this::riskCheck)
        .flatMap(this::routeToLiquidityProvider, 32)
        .retryWhen(Retry.backoff(3, Duration.ofMillis(100)))
        .timeout(Duration.ofSeconds(2));
}
```
Tim arsitek ingin melakukan migrasi penuh ke Kotlin Coroutines dan Asynchronous Flow, dengan hipotesis bahwa kode akan menjadi lebih mudah dibaca (*imperative-style reactive*), menghilangkan *callback-hell-like chaining*, dan mengurangi overhead alokasi memori. Namun, tim operasional ragu terkait performa throughput absolut dan determinisme eksekusi.

**Pertanyaan Diagnostik:**
1. Bedah trade-off arsitektural antara Project Reactor `Flux` dan Kotlin `Flow` dalam aspek:
   - Alokasi memori runtime (analisis alokasi objek operator chaining Reactor vs state-machine suspension Flow).
   - Kompleksitas debugging stack trace (Project Reactor Assembly/Execution trace vs Coroutine Debugger & Stack Recovery).
2. Tuliskan padanan kode idiomatik dari pipeline Reactor di atas menggunakan Kotlin Flow, dengan memastikan seluruh karakteristik bisnis (*bounded concurrency*, *exponential backoff retry*, dan *cancellation on timeout*) terakomodasi secara presisi.
3. Kapan Anda menyarankan tim enterprise untuk **TIDAK** memigrasikan sistem Project Reactor mereka ke Kotlin Flow? Berikan batasan teknis yang objektif.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Frequency Fault-Tolerant Order Book Aggregator

#### Problem Statement
Anda diminta untuk membangun komponen inti dari *Crypto Trading Terminal*: sebuah **Order Book Stream Aggregator** berlatensi rendah. Komponen ini harus mengonsumsi data *raw market ticks* dari 3 bursa eksternal (mocked via asynchronous Flows), menyelaraskan format, menyaring fluktuasi *out-of-order*, menggabungkan (*zip/merge*) penawaran terbaik (*Best Bid & Offer - BBO*), dan mengeksposnya ke UI/Konsumen melalui stream tunggal yang stabil dan tahan gangguan (*resilient*).

#### Requirements
1. **Multi-Source Ingestion & Concurrency:**
   - Konsumsi data secara paralel dari 3 provider: `"Binance"`, `"Coinbase"`, dan `"Kraken"`.
   - Masing-masing stream provider memancarkan tick harga dengan rate yang tidak menentu (10 ms - 200 ms per tick). Gunakan simulasi emisi asinkron.
2. **Data Model:**
   ```kotlin
   data class MarketTick(
       val exchange: String,
       val symbol: String,
       val price: Double,
       val volume: Double,
       val timestamp: Long
   )
   
   data class AggregatedBBO(
       val symbol: String,
       val bestBidPrice: Double,
       val bestBidExchange: String,
       val bestAskPrice: Double,
       val bestAskExchange: String,
       val spread: Double,
       val updatedAt: Long
   )
   ```
3. **Resilience & Fault Isolation:**
   - Jika salah satu provider melempar exception (misal: simulasi network failure), stream utama **tidak boleh mati**.
   - Provider yang gagal harus diisolasi dan diupayakan rekoneksi (*retry*) dengan strategi *exponential backoff* (maksimal 3 kali percobaan) tanpa mengganggu konsumsi data dari provider lain yang sehat.
4. **Adaptive Backpressure & Throttling:**
   - Konsumen hilir (UI Renderer) dibatasi hanya mampu memproses pembaruan maksimal setiap **100 ms**.
   - Implementasikan kebijakan non-blocking: jika pembaruan datang terlalu cepat saat konsumen sedang merender, gunakan teknik *conflation* cerdas yang tetap menjamin tick harga terbaru tidak pernah terlewat.
5. **State Exposure:**
   - Komponen akhir harus mengekspos `StateFlow<AggregatedBBO?>` yang menyimpan state BBO saat ini untuk setiap snapshot instan.

#### Constraints
- **Zero-Blocking Code:** Dilarang keras menggunakan `Thread.sleep()`, `synchronized`, atau tipe data blocking (`BlockingQueue`). Wajib menggunakan suspending functions dan primitif non-blocking coroutines.
- **Resource Cleanup:** Saat `CoroutineScope` aggregator dibatalkan, semua koneksi mock stream harus menutup alokasi sumber dayanya secara bersih menggunakan declarative completion (`onCompletion`).
- Menggunakan Kotlin Coroutines Core library (`kotlinx-coroutines-core`) standar.

#### Expected Output
1. File implementasi fungsional mandiri (`OrderBookAggregator.kt`) yang mencakup:
   - Definisi class aggregator.
   - Setup mock feed providers.
   - Pipeline transformasi dan operator error-handling.
2. Blok verifikasi `fun main() = runBlocking { ... }` yang mendemonstrasikan:
   - Stream berjalan lancar menerima data dari 3 exchange.
   - Injeksi failure pada salah satu provider dan proses self-healing-nya.
   - Downstream rendering berjalan tepat pada rate interval yang ditentukan tanpa lag memori.

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan penguasaan materi Anda sebelum melangkah ke topik sistem terdistribusi lanjut:

### Saya harus memahami:
- [ ] Mekanisme internal `FlowCollector` dan representasi emisi nilai sebagai pemanggilan fungsi suspensi tunggal `emit(value)`.
- [ ] Perbedaan internal runtime antara `Channel` (antrean berbasis komunikasi antar-coroutine via memori terbagi) dan `Flow` (komposisi pipeline fungsional non-alokatif).
- [ ] Prinsip *Exception Transparency* dan mengapa operator `catch` hanya menangkap exception dari *upstream*, bukan *downstream*.
- [ ] Aturan ketat *Context Preservation*: mengapa konteks korutin downstream mengendalikan eksekusi upstream kecuali diubah secara eksplisit menggunakan `flowOn`.
- [ ] Semantik teknis alokasi buffer: perbedaan `BufferOverflow.SUSPEND`, `BufferOverflow.DROP_OLDEST`, dan `BufferOverflow.DROP_LATEST`.
- [ ] Perbedaan implementasi level rendah antara `StateFlow` (berbasis `AtomicReference` + `conflation` bawaan) dan `SharedFlow` (berbasis array ring buffer terkonfigurasi).
- [ ] Sifat pembersihan deklaratif coroutine pada operator `onCompletion`, termasuk cara membedakan terminasi normal vs terminasi akibat pembatalan (*cancellation*).

### Saya tidak perlu menghafal:
- [ ] Setiap variasi signature method dari operator transformasi matematika kompleks pada `Flow` (cukup pahami operator fundamental: `map`, `filter`, `transform`, `reduce`, `fold`).
- [ ] Nilai numerik konstanta internal sistem, seperti ukuran default buffer coroutines (`DEFAULT_CONCURRENCY` = 16 atau `BUFFERED` = 64). Ini dapat berubah antar-versi library runtime.
- [ ] Seluruh sintaks interoperabilitas Java Reactive Streams (`FlowAdapters`, `ReactiveStreamsProvider`) di luar pola konversi standar `.asFlow()` dan `.asPublisher()`.

### Saya harus bisa melakukan:
- [ ] Melakukan isolasi konteks eksekusi thread secara presisi menggunakan `flowOn` tanpa melanggar context preservation rules.
- [ ] Menangani *slow consumer backpressure* di sistem produksi menggunakan kombinasi `buffer()`, `conflate()`, atau `collectLatest()` secara tepat sesuai use-case bisnis.
- [ ] Mencegah dan mendeteksi memory leak akibat *hot streams* (`SharedFlow`/`StateFlow`) yang tetap berjalan pada scope yang salah (*inappropriate lifecycle scope*).
- [ ] Menulis unit test deterministik untuk memvalidasi *asynchronous flow* menggunakan `kotlinx-coroutines-test`, `Turbine`, dan *virtual time scheduling* (`TestScope`/`advanceUntilIdle`).
- [ ] Menggabungkan (*merge/zip/combine*) banyak stream data independen dengan penanganan kegagalan individual (*fault isolation*) agar tidak mematikan pipeline keseluruhan.