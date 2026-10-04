# BAB 07: Quiz, Challenge, & Knowledge Check
**Koleksi, Ekstensi & Serialization**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Karakteristik Read-Only vs Immutable pada Abstraksi Koleksi
Di Kotlin, antarmuka `List<T>` secara teknis didefinisikan sebagai *read-only interface*, bukan *immutable interface*. 
* Jelaskan secara mendalam perbedaan arsitektural antara kedua konsep tersebut pada level implementasi JVM.
* Apa risiko runtime dan konsekuensi thread-safety jika sebuah referensi `List<T>` secara internal mereferensikan instance underlying `ArrayList` yang dimutasi oleh thread lain melalui antarmuka `MutableList<T>`?

### Soal 1.2: Model Eksekusi Koleksi: Eager Evaluation (Iterables) vs Lazy Pipelining (Sequences)
Kotlin menyediakan dua pendekatan manipulasi data: `Iterable` standar dan `Sequence`.
* Analisis perbedaan traversal data secara horizontal (multi-pass) pada `Iterable` versus traversal vertikal (single-pass pipelining) pada `Sequence`.
* Pada kondisi volume data dan karakteristik operasi transformasi (seperti `map`, `filter`, `take`) seperti apa penggunaan `Sequence` menghasilkan penurunan alokasi memori yang signifikan, dan kapan overhead state machine pada `Sequence` justru menurunkan throughput eksekusi dibandingkan `Iterable`?

### Soal 1.3: Mekanisme Desugaring Bytecode pada Extension Functions
Extension functions sering disalahpahami sebagai mutasi langsung terhadap struktur class target.
* Bagaimana compiler Kotlin mengonversi deklarasi extension function ke dalam JVM bytecode? 
* Jelaskan mengapa resolusi pemanggilan extension function bersifat statis (*static dispatch*) dan apa yang terjadi jika sebuah extension function didefinisikan dengan signature yang persis sama dengan member function yang sudah ada pada class tersebut?

### Soal 1.4: Batasan Arsitektural Extension Properties
Berbeda dengan regular properties pada sebuah class, extension properties di Kotlin memiliki restriksi ketat terkait state management.
* Mengapa extension properties dilarang memiliki *backing field* (`field`)?
* Jelaskan bagaimana compiler memproses extension properties dengan custom getter dan setter, serta bagaimana state sintetis dapat disimulasikan tanpa memicu kebocoran memori (*memory leak*).

### Soal 1.5: Compile-Time Code Generation pada `kotlinx.serialization` vs Runtime Reflection
Framework serialisasi konvensional (seperti Jackson atau Gson) sangat bergantung pada Java Reflection API untuk inspeksi metadata tipe data saat runtime.
* Bagaimana compiler plugin `kotlinx.serialization` bekerja secara fundamental untuk mengeliminasi ketergantungan pada runtime reflection?
* Jelaskan peran interface `KSerializer<T>`, serial descriptor, dan bagaimana compiler menghasilkan class `$serializer` tersembunyi saat sebuah class diberi anotasi `@Serializable`.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Churn Memory & GC Overhead pada Operasi Koleksi
Perhatikan cuplikan kode pemrosesan streaming event berfrekuensi tinggi berikut:

```kotlin
fun processBatch(events: List<TelemetryEvent>): List<NormalizedEvent> {
    return events
        .filter { it.isValid }
        .map { it.toNormalized() }
        .sortedBy { it.timestamp }
}
```

* Bedah alokasi objek perantara (*intermediate collections*) yang dialokasikan di JVM heap saat method ini dieksekusi untuk 100.000 batch per detik.
* Bagaimana Anda mendesain ulang implementasi ini menggunakan `buildList`, in-place sorting, atau custom buffer pooling guna menekan laju alokasi memori (*allocation rate*) dan mengeliminasi tekanan pada JVM Garbage Collector?

### Soal 2.2: Resolusi Receiver Conflict dan Shadowing pada Extension Scoping
Analisis cuplikan kode berikut yang mendefinisikan extension di dalam class lain (*member extension function*):

```kotlin
class Dispatcher {
    fun execute() = println("Dispatcher.execute")
}

class Worker {
    fun execute() = println("Worker.execute")

    fun Dispatcher.runTask() {
        execute() // Pemanggilan ambigu
        this@Worker.execute()
        this.execute()
    }
}
```

* Manakah method yang dieksekusi oleh pemanggilan `execute()` tanpa kualifikasi? Mengapa *extension receiver* atau *dispatch receiver* memiliki preseden tertentu dalam resolusi simbol Kotlin?
* Jelaskan keterbatasan interoperabilitas Java saat memanggil member extension function seperti `runTask` di atas dari kode Java murni.

### Soal 2.3: Serialisasi Polimorfik dan Keamanan Tipe (Type-Discriminator Injection)
Pada arsitektur event-driven, Anda mengimplementasikan polymorphic serialization menggunakan sealed hierarchy:

```kotlin
@Serializable
sealed interface AuditPayload {
    @Serializable @SerialName("USER_LOGIN")
    data class Login(val userId: String) : AuditPayload

    @Serializable @SerialName("PAYMENT_EXEC")
    data class Payment(val amount: Double) : AuditPayload
}
```

* Bagaimana `kotlinx.serialization` menyematkan dan membaca metadata tipe (`type-discriminator`) ke dalam struktur JSON?
* Apa konsekuensi arsitektural jika arsitektur microservice upstream menambahkan subclass baru tanpa registrasi pada engine downstream? Bagaimana Anda mengimplementasikan fallback handler/default deserializer untuk menjamin backward/forward compatibility tanpa memicu `SerializationException`?

### Soal 2.4: Diagnostik Memory Leak Akibat Capturing Receiver pada Extension Lambdas
Sebuah utility extension didefinisikan untuk mempermudah eksekusi task asinkron:

```kotlin
fun Context.launchScopedTask(block: suspend () -> Unit) {
    AppScope.launch {
        trackContextAccess(this@launchScopedTask)
        block()
    }
}
```

* Bagaimana lambda closure di atas dapat secara diam-diam menahan instance `Context` (misalnya lifecycle-sensitive object) pada heap memory meskipun siklus hidup object tersebut telah berakhir?
* Bagaimana cara mengaudit kebocoran referensi ini melalui heap dump analysis (misal via Eclipse MAT atau JProfiler), dan bagaimana memperbaikinya secara idiomatik?

### Soal 2.5: Zero-Allocation Custom Serializer untuk Inline/Value Classes
Diberikan sebuah Value Class:

```kotlin
@JvmInline
value class TransactionId(val rawUuid: String)
```

Secara default, serialisasi value class dapat memicu boxing overhead jika tidak diatur dengan cermat saat dialirkan ke streaming serializer.
* Rancang struktur `KSerializer<TransactionId>` kustom yang memanfaatkan direct primitive/string encoding tanpa mengalokasikan instance wrapper baru selama siklus serialisasi dan deserialisasi.
* Bagaimana validasi format string UUID dapat diintegrasikan secara langsung pada level `Decoder` sebelum representasi data diinstansiasi?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: OOM Crash pada Pipeline Ekstraksi Log Skala Besar (Scale/Bottleneck)
Sebuah background service ingestion log mengalami crash produksi berupa `java.lang.OutOfMemoryError: Java heap space` saat memproses file batch sebesar 4 GB yang berisi data JSON berformat NDJSON (Newline Delimited JSON). Layanan berjalan dengan batasan JVM flag `-Xmx1g`.

Investigasi awal menunjukkan kode berikut:
```kotlin
fun parseAndAggregateLogs(file: File): Map<String, Int> {
    return file.readLines()
        .map { Json.decodeFromString<LogEntry>(it) }
        .filter { it.severity == "ERROR" }
        .groupBy { it.serviceName }
        .mapValues { it.value.size }
}
```

* **Pertanyaan Diagnostik:**
  1. Identifikasi minimal 3 anti-pattern performa memori pada kode di atas yang menyebabkan heap exhaustion secara masif.
  2. Rancang arsitektur refactoring berbasis streaming parsing (`File.useLines`, lazy Sequences, atau Flow) dan manual aggregation map mutasi in-place yang mampu memproses file 4 GB tersebut secara stabil dengan penggunaan heap konstan di bawah 64 MB. Sertakan implementasi kode yang lengkap.

---

### Skenario B: Silent Data Corruption dan ConcurrentModificationException pada Caching Layer (Race Condition)
Platform e-commerce Anda memiliki in-memory cache berkinerja tinggi untuk menyimpan katalog produk aktif. Cache service mengekspos data katalog sebagai berikut:

```kotlin
@Service
class ProductCatalogCache {
    private val cachedProducts: MutableList<Product> = ArrayList()

    fun getActiveProducts(): List<Product> = cachedProducts

    suspend fun refreshCatalog(newProducts: List<Product>) = withContext(Dispatchers.IO) {
        cachedProducts.clear()
        cachedProducts.addAll(newProducts)
    }
}
```

Di bawah beban 15.000 Request per Second (RPS), logging backend mulai mendeteksi serangkaian error:
* Sporadic `java.util.ConcurrentModificationException` pada thread pool pemanggil `getActiveProducts().forEach { ... }`.
* Fenomena data race di mana consumer menerima list kosong (`size == 0`) saat proses refresh berlangsung, yang menyebabkan katalog produk pada homepage hilang sesaat bagi pengguna (*blackout product*).

* **Pertanyaan Diagnostik:**
  1. Mengapa eksposisi `List<Product>` dari `MutableList<Product>` gagal memberikan thread-safety runtime meskipun tipe kembaliannya bersifat read-only?
  2. Bandingkan trade-off arsitektural dari tiga solusi berikut untuk mengatasi masalah ini:
     * Penggunaan `CopyOnWriteArrayList` dari `java.util.concurrent`.
     * Penggunaan Kotlin Persistent Collections (`kotlinx.collections.immutable` - `PersistentList`).
     * Atomic reference swapping (`AtomicReference<List<Product>>`) yang membungkus list unmodifiable.
  3. Implementasikan solusi yang memberikan performa pembacaan (*read throughput*) paling optimal dengan zero-locking overhead.

---

### Skenario C: Migrasi Microservice ke GraalVM Native Image & Kotlinx Serialization (Architecture & Trade-off)
Tim Anda sedang memigrasikan enterprise backend berbasis Spring Boot/Jackson ke Ktor microservice ultra-ringan yang dikompilasi menjadi GraalVM Native Image. Saat mengganti Jackson dengan `kotlinx.serialization`, sistem runtime mengalami serangkaian kegagalan kritis di level staging:

1. **Unknown Fields Failure:** Layanan upstream sering mengirim payload JSON dengan field tambahan baru yang menyebabkan layanan downstream crash dengan `SerializationException: UnknownKeyException`.
2. **Missing Defaults:** Field pada payload upstream yang bernilai `null` meng-override nilai *default parameter* yang didefinisikan pada Kotlin data class, atau sebaliknya, field yang tidak dikirim memicu parsing error.
3. **Circular Reference Crash:** Terjadi `StackOverflowError` saat serialisasi relasi bidirectional entity (misalnya `User` memiliki daftar `Order`, dan `Order` memiliki referensi balik ke `User`).

* **Pertanyaan Diagnostik:**
  1. Bagaimana konfigurasi instansiasi `Json { ... }` builder yang tepat untuk menangani kompatibilitas skema yang fleksibel (*lenient mode*, unknown keys handling, dan explicit nulls policy)?
  2. Mengapa arsitektur native compiler (`kotlinx.serialization`) secara fundamental tidak mendukung graph serialisasi dengan relasi sirkular (*bidirectional cyclic graph*) secara out-of-the-box seperti Jackson?
  3. Rancang strategi pemodelan Data Transfer Object (DTO) menggunakan extension mapper pattern untuk memisahkan domain entity internal dari exposure network DTO, sehingga mengeliminasi circular reference secara total tanpa kompromi performa.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Audit Log Ingestion Engine
Rancang dan implementasikan engine ingestion log terdistribusi yang memproses batch stream berdensitas tinggi, memfilter anomali, melakukan desensitisasi data rahasia (*PII masking*), dan mengekspor hasilnya ke format NDJSON terkompresi.

#### 1. Problem Statement
Sistem menerima raw event logs dalam volume masif (puluhan ribu event per file batch). Anda diminta membangun engine pemrosesan yang menerapkan konvensi modern: pure streaming tanpa eagerly loading data ke memory, deserialisasi reflection-free, DSL berbasis extension function untuk manipulasi data, dan custom serialization untuk data sensitif.

#### 2. Requirements & Functional Constraints
1. **Model Hierarchy (Sealed Class):**
   * Interface dasar: `AuditEvent`.
   * Tipe konkret: `AuthEvent` (properti: `userId`, `ipAddress`, `timestamp`, `status`), `TransactionEvent` (properti: `transactionId`, `userId`, `amount`, `creditCardNumber`, `timestamp`), dan `SystemAlertEvent` (properti: `source`, `level`, `message`, `timestamp`).
2. **Custom Serializer (PII Masking):**
   * Field `creditCardNumber` pada `TransactionEvent` **tidak boleh** diserialisasikan dalam bentuk teks terbuka (*plaintext*).
   * Rancang custom serializer `MaskedCardSerializer` yang secara otomatis mentransformasi string kartu kredit (misal: `"4111222233334444"`) menjadi `"4111-XXXX-XXXX-4444"` secara inline saat encode/decode.
3. **Collection Processing Pipeline:**
   * Gunakan pendekatan `Sequence` atau streaming reader langsung dari `InputStream` / `BufferedReader`.
   * Saring (filter) hanya event yang terjadi dalam rentang 24 jam terakhir dan status auth bukan `FAILURE`.
   * Lakukan agregasi volume transaksi per mata uang/user menggunakan collection primitives yang hemat alokasi memori.
4. **Extension DSL:**
   * Buat extension functions pada `Sequence<AuditEvent>` atau tipe terkait:
     * `.maskSensitiveData()`
     * `.groupByUserAndCount(): Map<String, Int>`
     * `.toNdjsonStream(outputStream: OutputStream)`
5. **Runtime Memory Limit:**
   * Aplikasi harus mampu memproses file input sebesar **500 MB** dengan batasan alokasi JVM Heap **`-Xmx64m`**. Pelanggaran memori (`OutOfMemoryError`) menandakan kegagalan otomatis. Zero reflection library diperbolehkan (hanya gunakan `kotlinx.serialization`).

#### 3. Expected Output
* Kode sumber Kotlin lengkap yang modular dan siap produksi.
* Log output eksekusi yang mendemonstrasikan pembacaan, transformasi data, dan penulisan output NDJSON yang valid.
* Verifikasi konsumsi memori stabil (profiling assertions atau log runtime memory usage: `Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory()`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan semantik dan arsitektural antara Read-Only Collections (`kotlin.collections.*`) dengan Immutable Collections murni (`kotlinx.collections.immutable.*`).
- [ ] Dampak alokasi memori perantara (*intermediate buffers*) pada evaluasi `Iterable` vs pipelining vertikal pada `Sequence`.
- [ ] Mekanisme dekompilasi JVM bytecode dari Extension Functions sebagai Java `public static final` methods dengan receiver sebagai argumen pertama.
- [ ] Aturan resolusi *Static Dispatch* pada Extension Functions dan interaksinya dengan class polymorphism (Virtual Dispatch).
- [ ] Konsep *Dispatch Receiver* vs *Extension Receiver* serta implikasi scoping dan resolusi ambiguitas pemanggilan method.
- [ ] Perbedaan mendasar arsitektur serialisasi *compile-time generated metadata* (`kotlinx.serialization`) vs *runtime reflection-based inspection* (Jackson/Gson).
- [ ] Cara kerja polymorphic serialization pada `kotlinx.serialization` menggunakan `SerializersModule` dan penanganan *class discriminator*.
- [ ] Strategi penanganan skema data dinamis: deserialisasi fallback, `ignoreUnknownKeys`, `encodeDefaults`, dan explicit null safety.

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap seluruh implementasi ratusan operator transformasi pada Kotlin Standard Library (seperti nama eksak variasi `windowed`, `zipWithNext`, `scan`). Anda hanya perlu memahami kapan menggunakan folding/reducing lazily vs eagerly.
- [ ] Karakteristik opcode JVM spesifik (`INVOKESTATIC`, `INVOKEVIRTUAL`) secara detail, asalkan memahami konsekuensi pemanggilan statis vs dinamis.
- [ ] Format biner internal dari engine serialisasi spesifik (Protobuf/CBOR) di luar model decoding/encoding `kotlinx.serialization`.

### Saya harus bisa melakukan:
- [ ] Melakukan dekompilasi kode Kotlin ke Java/Bytecode di IDE (IntelliJ IDEA / Android Studio) untuk memverifikasi footprint alokasi extension function dan collection loops.
- [ ] Mengidentifikasi dan memitigasi memory leak yang timbul dari capturing closure pada extension lambdas yang berumur panjang.
- [ ] Memilih secara tepat antara `Iterable`, `Sequence`, atau in-place mutation buffer (`buildList`, pooling) berdasarkan volume data, frekuensi eksekusi, dan latency SLA.
- [ ] Mengimplementasikan custom `KSerializer<T>` untuk tipe data primitif, value class, atau external third-party classes yang tidak dapat dianotasi langsung dengan `@Serializable`.
- [ ] Memperbaiki masalah performa dan crash `OutOfMemoryError` akibat eager batch collection processing dengan mengonversinya menjadi lazy zero-allocation streaming pipeline.