# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Bahasa & Sistem Tipe Modern**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Type Hierarchy & Bottom Type
Jelaskan posisi arsitektural dari `Any`, `Any?`, `Nothing`, dan `Nothing?` dalam sistem tipe Kotlin. Mengapa `Nothing` diklasifikasikan sebagai *uninhabited type* (bottom type), dan bagaimana Kotlin compiler memanfaatkannya secara matematis dalam analisis aliran kontrol (*control-flow analysis*) saat mengevaluasi ekspresi seperti `throw Exception()` atau pemanggilan fungsi `TODO()`?

### Soal 1.2: Semantik Immutability (`val` vs Deep Immutability)
Mengapa deklarasi referensi menggunakan `val` di Kotlin bukan merupakan sinonim dari *pure immutability*? Jelaskan perbedaan semantiknya dengan `const val` pada level kompilasi dan runtime, serta analisis bagaimana sebuah objek bertipe `val` tetap dapat menyebabkan efek samping (*side-effects*) dalam lingkungan konkuren jika membungkus *mutable state*.

### Soal 1.3: Mekanisme Bytecode Representasi Nullability
Kotlin membedakan tipe non-nullable (`T`) dan nullable (`T?`) pada tingkat bahasa. Bagaimana JVM—yang secara native tidak memiliki konsep *first-class nullability* pada tipe primitif maupun referensi—merepresentasikan perbedaan ini dalam bytecode yang dihasilkan? Jelaskan peran instruksi runtime assertions seperti `Intrinsics.checkNotNullParameter`.

### Soal 1.4: Syarat Deterministik Smart Casting
Kotlin menyediakan fitur *Smart Cast* otomatis menggunakan operator `is` atau pemeriksaan null. Sebutkan kondisi pasti di mana compiler **menolak** melakukan smart cast meskipun developer telah melakukan pemeriksaan tipe/null secara eksplisit di baris sebelumnya. Jelaskan alasan teknis mengapa compiler mengambil keputusan defensif tersebut pada skenario `var` dan *custom getter*.

### Soal 1.5: Komparasi Semantik `Unit` vs `Nothing` vs Java `void`
Jelaskan perbedaan mendasar antara `kotlin.Unit`, `kotlin.Nothing`, dan `void` pada Java. Mengapa Kotlin memilih mendesain `Unit` sebagai *singleton object* nyata (`Unit` inherits from `Any`) alih-alih mengadopsi mekanisme *keyword-level absence of value* seperti `void` pada Java? Apa implikasinya terhadap paradigma *generic programming*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Jebakan Platform Types (`T!`) dan Runtime Null-Pointers
Diberikan kode Java legasi:
```java
public class UserRegistry {
    public static String getRawMetadata(String key) {
        return key.equals("valid") ? "DATA" : null;
    }
}
```
Jika method di atas dikonsumsi oleh Kotlin tanpa anotasi nullability eksplisit (`@Nullable`/`@NotNull`), compiler akan menginferensinya sebagai *Platform Type* (`String!`).
* Jelaskan mengapa Kotlin compiler tidak memaksakan penanganan *null-safety* saat kompilasi pada *Platform Type*.
* Tunjukkan bagaimana skenario ini dapat memicu **deferred NullPointerException** (NPE yang meledak jauh dari titik integrasi awal) dan bagaimana cara mengamankan batas interoperabilitas (*interop boundary*) tersebut secara idiomatik.

### Soal 2.2: Analisis Alokasi Memori: Primitive Arrays vs Boxed Collections
Analisis perbedaan representasi memori, *cache locality*, dan overhead *Garbage Collection* (GC) antara:
1. `Array<Int>`
2. `List<Int>`
3. `IntArray`

Jelaskan kapan proses *autoboxing* dan *unboxing* terjadi di balik layar pada masing-masing struktur data tersebut, dan apa dampaknya jika diproses di dalam *hot path* (misalnya loop pemrosesan data real-time 10.000.000 iterasi).

### Soal 2.3: Evaluasi Operator Elvis (`?:`) dan Precedence Short-Circuit
Bedah pohon sintaks abstrak (AST) dan evaluasi eksekusi dari ekspresi berikut:
```kotlin
val result = fetchCache()?.process() ?: calculateDefault().also { logFallback() }
```
Jika `fetchCache()` mengembalikan objek non-null, namun method `process()` mengembalikan `null`:
* Apakah `calculateDefault()` akan dieksekusi?
* Bagaimana compiler menginterpretasikan *precedence* antara operator Safe Call (`?.`) dan Elvis Operator (`?:`)?
* Apa potensi *logical bug* tersembunyi jika `calculateDefault()` adalah operasi I/O yang berat?

### Soal 2.4: Anomali Structural Equality (`==`) vs Referential Equality (`===`) pada Boxed Primitives
Perhatikan potongan kode berikut:
```kotlin
val a: Int? = 1000
val b: Int? = 1000
val c: Int = 1000
val d: Int = 1000

println(a === b) // Evaluasi 1
println(c === d) // Evaluasi 2

val x: Int? = 127
val y: Int? = 127
println(x === y) // Evaluasi 3
```
Jelaskan output dari ketiga evaluasi di atas pada JVM target 17+. Mengapa Evaluasi 1 dan Evaluasi 3 menghasilkan output yang berbeda meskipun keduanya membandingkan referensi dari tipe `Int?` yang memiliki nilai sama? Hubungkan jawaban Anda dengan mekanisme JVM Integer Cache.

### Soal 2.5: Smart Cast Bypass via Local Copy Snapshot
Diberikan class berikut:
```kotlin
class OrderProcessor {
    var customerToken: String? = null

    fun process() {
        if (customerToken != null) {
            // ERROR: Smart cast to 'String' is impossible, because 'customerToken' is a mutable property
            // that could have been mutated by this time
            sendNotification(customerToken)
        }
    }

    private fun sendNotification(token: String) { /* I/O */ }
}
```
* Jelaskan skenario persis bagaimana `customerToken` dapat berubah menjadi `null` di antara blok `if` check dan pemanggilan `sendNotification(customerToken)` dalam eksekusi multi-threaded.
* Tuliskan minimal 2 pola refaktorisasi idiomatis yang direkomendasikan untuk menyelesaikan error kompilasi ini tanpa menggunakan operator *force-unwrap* (`!!`).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike dan GC Pauses pada High-Throughput Ingestion Engine
Sebuah microservice analitik finansial berbasis Ktor menangani *throughput* 50.000 transaksi per detik. Metrik APM (Application Performance Monitoring) menunjukkan adanya *Stop-the-World* (STW) GC pauses berkala berdurasi 300ms–800ms yang mengakibatkan *upstream timeout*. 

Setelah dilakukan profiling memori via JProfiler/Async-Profiler, ditemukan bahwa alokasi memori didominasi oleh objek `java.lang.Long` dan `java.lang.Double` sementara dalam jumlah jutaan per detik. Kode pipeline transformasi data terlihat seperti ini:

```kotlin
data class MarketTick(val timestamp: Long, val price: Double, val volume: Double)

fun aggregateMetrics(ticks: List<MarketTick?>): Map<Long, Double> {
    return ticks
        .filterNotNull()
        .groupBy { it.timestamp / 1000 }
        .mapValues { (_, tickGroup) ->
            tickGroup.map { it.price * it.volume }.sum()
        }
}
```

**Pertanyaan Diagnostik & Solusi:**
1. Bedah secara mendalam di mana saja proses *boxing/unboxing* tersembunyi dan pembuatan objek intermediet terjadi pada fungsi `aggregateMetrics`.
2. Rancang ulang arsitektur fungsi tersebut agar mendekati karakteristik *zero-allocation* (meminimalkan alokasi heap secara drastis) dengan memanfaatkan struktur data primitif khusus atau teknik streaming/imperatif yang ramah terhadap L1/L2 CPU cache.

---

### Skenario B: Coroutine Worker Crash akibat Platform Type Nullability Leak
Sebuah sistem backend e-commerce mengonsumsi pesan transaksi dari Apache Kafka menggunakan Java Client library lama. Objek event di-deserialisasi menjadi objek Java DTO tanpa validasi nullability:

```java
// Legacy Java DTO
public class PaymentEvent {
    private String transactionId;
    private String paymentGatewayCode; // Bisa bernilai null jika transaksi via internal wallet
    // getters and setters...
}
```

Developer Kotlin mengonsumsi event ini dengan kode worker coroutine berikut:

```kotlin
suspend fun handleEvent(event: PaymentEvent) {
    val gatewayCode = event.paymentGatewayCode // Tipe: String!
    val metricsKey = gatewayCode.uppercase()  // Crash di sini: NPE di thread pool coroutine
    metricsService.record(metricsKey)
}
```

Ironisnya, crash ini tidak terjadi saat unit test dijalankan karena data mock selalu mengisi `paymentGatewayCode`. Di production, crash menyebabkan thread coroutine unhandled exception dan *Kafka Consumer group rebalance storm*.

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa compiler Kotlin meloloskan pemanggilan `.uppercase()` secara langsung pada `event.paymentGatewayCode` tanpa compiler error atau warning?
2. Bagaimana mekanisme *null-defensive boundary layer* harus dirancang untuk memutus sepenuhnya dependensi *Platform Types* dari layer integrasi data eksternal sebelum masuk ke domain logic inti?

---

### Skenario C: Architectural Trade-off: Value Class vs Sealed Interface vs Boxed Types pada Domain Identifier
Anda bertindak sebagai Lead Architect yang sedang mendesain modul Identity & Access Management (IAM) tingkat enterprise. Modul ini memproses miliaran operasi validasi ID entitas per hari (`UserId`, `TenantId`, `RoleId`).

Developer tim mengajukan tiga proposal desain untuk mencegah *primitive obsession* (mencegah bug di mana `UserId` tertukar dengan `TenantId` yang sama-sama berupa raw `String` atau `UUID`):

* **Proposal 1:** Menggunakan `typealias UserId = String`
* **Proposal 2:** Menggunakan `data class UserId(val value: String)`
* **Proposal 3:** Menggunakan `@JvmInline value class UserId(val value: String)`

**Pertanyaan Evaluasi Kritis:**
1. Bedah kelemahan teknis fatal dari Proposal 1 terkait jaminan *type-safety* saat kompilasi.
2. Analisis konsekuensi alokasi heap dan performa eksekusi antara Proposal 2 (`data class`) dan Proposal 3 (`value class`).
3. Jelaskan skenario spesifik di mana Proposal 3 (`value class`) **tetap terpaksa mengalami boxing** menjadi objek heap alih-alih di-*inline* sebagai primitif murni oleh compiler Kotlin. Apa dampaknya pada perancangan API (misalnya saat berinteraksi dengan collections atau generic interfaces)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Zero-Leak Event Validation Pipeline
Anda diminta membangun sebuah *ingestion processor* independen untuk sistem sensor IoT berkecepatan tinggi yang menerima sinyal mentah berupa representasi teks dan bilangan. Pipeline ini harus tahan terhadap kebocoran `null`, bebas alokasi heap yang tidak perlu pada *hot path*, dan menerapkan sistem tipe Kotlin secara maksimal.

#### Requirements:
1. **Domain Types:**
   * Definisikan representasi ID sensor menggunakan `@JvmInline value class SensorId(val raw: String)`. Tambahkan validasi agar `raw` tidak boleh kosong (lempar `IllegalArgumentException`).
   * Rancang model data status pembacaan sensor menggunakan `sealed class` atau `sealed interface SensorPayload` dengan varian:
     * `Temperature(val value: Double)`
     * `Humidity(val percentage: Double)`
     * `Diagnostic(val code: Int, val message: String)`
     * `Malfunction(val errorCode: Int, val isTerminal: Boolean)`
2. **Result Monad Architecture:**
   * Bangun tipe monad fungsional sendiri (jangan gunakan library eksternal): `sealed interface IngestionResult<out T, out E>`
     * Varian `Success<out T>` yang membawa data `T`.
     * Varian `Failure<out E>` yang membawa data error `E`.
     * Manfaatkan subtipe `Nothing` agar varian dapat dikomposisikan secara kovarian (`out`).
3. **Parsing & Processing Function:**
   * Buat fungsi:
     ```kotlin
     fun processRawStream(
         sensorIdRaw: String?,
         typeRaw: String?,
         valueRaw: Double?,
         metaCode: Int?
     ): IngestionResult<SensorPayload, PipelineError>
     ```
   * Seluruh parameter input mensimulasikan data mentah tidak tepercaya (bisa `null`).
   * Hilangkan seluruh kemungkinan crash akibat `NullPointerException`. Penggunaan operator `!!` dilarang keras (*zero tolerance*).
   * Validasi tipe data dan kembalikan `PipelineError` (rancang domain error menggunakan `sealed interface PipelineError` yang membedakan kegagalan *MissingMetadata*, *CorruptedPayload*, dan *UnknownSensor*).
   * Gunakan pattern matching `when` secara komprehensif (*exhaustive evaluation* tanpa cabang `else` pada sealed hierarchy).

#### Constraints:
* Zero usage of Java reflection / dynamic reflection.
* Target runtime: Kotlin JVM 1.9+ / JVM 21.
* Tidak boleh memicu pembentukan objek baru jika input gagal divalidasi pada pemeriksaan awal (gunakan singleton error variants via `data object` di dalam hierarki error).

#### Expected Output:
Kode implementasi murni (*self-contained*) yang memvalidasi kasus uji berikut tanpa throwing exception:
1. Input valid memproduksi `IngestionResult.Success(SensorPayload.Temperature)`.
2. Input dengan nilai `null` di parameter wajib memproduksi `IngestionResult.Failure(PipelineError.MissingMetadata)`.
3. Demonstrasi evaluasi *exhaustive* pada layer pemanggil menggunakan ekspresi `when (val res = processRawStream(...))`.

---

## 5. Knowledge Check & Checklist

Verifikasi pemahaman konseptual dan kesiapan praktikal sebelum melanjutkan ke Bab berikutnya.

### Saya harus memahami:
- [ ] Diagram lengkap hierarki sistem tipe Kotlin (Hubungan antara `Any?`, `Any`, `Nothing?`, `Nothing`, dan subtype primitif/objek).
- [ ] Mengapa Kotlin tidak mendukung konsep *raw types* seperti pada Java dan bagaimana *variance* dasar berinteraksi dengan hierarki nullability.
- [ ] Mekanisme deteksi nullability pada boundary layer Java interop melalui *Platform Types* (`T!`) serta bahaya implikasinya.
- [ ] Aturan mutabilitas vs visibilitas yang mengatur apakah suatu variabel dapat di-*smart-cast* oleh compiler.
- [ ] Mekanisme memory representation tipe primitif di JVM: kapan Kotlin mengompilasi `Int` menjadi primitif `int` dan kapan menjadi referensi `java.lang.Integer`.
- [ ] Peran `const val` sebagai inlined compile-time constant vs `val` sebagai runtime immutable reference dengan backing field / getter.

### Saya tidak perlu menghafal:
- [ ] String hashcode unik algoritma name-mangling untuk `@JvmInline value class` pada level bytecode.
- [ ] Nomor spesifik bytecode opcodes JVM (misalnya perbedaan opcodes `checkcast`, `invokestatic`, atau `ifnull`).
- [ ] Seluruh daftar internal method bawaan dari class `kotlin.jvm.internal.Intrinsics`.

### Saya harus bisa melakukan:
- [ ] Mengonversi kode integrasi Java yang rentan menjadi batas sistem (*boundary*) yang 100% aman dari NPE menggunakan null-safe contract atau DTO sanitization layer.
- [ ] Menggunakan operator Elvis (`?:`), Safe Call (`?.`), dan Safe Cast (`as?`) secara proporsional tanpa menulis antipattern nested chains yang sulit dibaca.
- [ ] Melakukan dekompilasi Kotlin Bytecode ke Java via IntelliJ IDEA / Decompiler Tool untuk menganalisis alokasi tersembunyi (*hidden boxing overhead*).
- [ ] Mengatasi kegagalan smart-cast pada mutable properties menggunakan teknik *local snapshot capture* atau scoping functions (`let`, `run`) secara idiomatik.
- [ ] Merancang arsitektur model domain berbasis `sealed interface` dan `data object` untuk menciptakan sistem *type-safe* yang memaksa penanganan komprehensif saat waktu kompilasi.