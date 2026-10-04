# BAB 03: Quiz, Challenge, & Knowledge Check
**Functional Programming & Scope Functions**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Matriks Perbandingan Scope Functions:**  
   Jelaskan secara komprehensif perbedaan arsitektural antara kelima scope functions bawaan Kotlin (`let`, `run`, `with`, `apply`, `also`) berdasarkan dua dimensi utama: *Context Object Reference* (`this` vs `it`) dan *Return Value* (*Lambda result* vs *Context object*). Berikan rasionalisasi teknis kapan sebuah fungsi harus mengembalikan context object versus lambda result.

2. **First-Class Functions & SAM Conversion:**  
   Bagaimana Kotlin merepresentasikan functional type (misalnya `(String, Int) -> Boolean`) di level JVM bytecode? Jelaskan mekanisme *Single Abstract Method* (SAM) Conversion untuk interoperabilitas Java-Kotlin dan bagaimana compiler mengoptimalkan alokasi instance lambda statis vs non-statis.

3. **Immutability vs Read-Only Interfaces:**  
   Dalam paradigma Functional Programming (FP), jelaskan perbedaan mendasar antara tipe data *Read-Only* (seperti `kotlin.collections.List`) dan *Immutable Data Structure* yang sesungguhnya. Mengapa `val list: List<T>` di Kotlin tidak menjamin immutability absolut terhadap memory mutation di runtime JVM?

4. **Pure Functions dan Referential Transparency:**  
   Definisikan karakteristik *Pure Function* dan *Referential Transparency*. Tunjukkan contoh bagaimana mutasi state eksternal atau pemanggilan side-effect (seperti logging/I/O) di dalam operator transformasi koleksi (misal: `map` atau `filter`) melanggar prinsip ekuivalensi matematis dan menyulitkan optimasi kompilator/paralelisasi.

5. **Eager Evaluation (`Iterable`) vs Lazy Evaluation (`Sequence`):**  
   Bandingkan alur eksekusi pipeline pengolahan data antara `Iterable` dan `Sequence` saat memproses serangkaian chaining operator (`filter`, `map`, `take`). Jelaskan dampaknya terhadap alokasi memori intermediat (*intermediate collections*) dan kapan overhead overhead state-machine pada `Sequence` justru lebih lambat daripada `Iterable`.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Bytecode Analysis: Biaya Alokasi Lambda Non-Inline:**  
   Diberikan sebuah higher-order function non-inline:
   ```kotlin
   fun execute(block: () -> Unit) { block() }
   ```
   Jika fungsi tersebut dipanggil di dalam loop sebanyak $10^7$ kali dengan menangkap (*capturing*) variabel lokal dari outer-scope, jelaskan apa yang terjadi pada *heap allocation*, *Garbage Collector* (GC) pressure, dan bagaimana compiler merepresentasikannya ke dalam class `Function0`. Apa yang berubah jika lambda tersebut tidak meng-capture variabel apapun?

2. **Mekanika `inline`, `noinline`, dan `crossinline`:**  
   Mengapa *non-local returns* diizinkan secara default pada lambda argumen dari fungsi `inline`? Jelaskan skenario arsitektural di mana kata kunci `crossinline` wajib digunakan ketika lambda yang di-inline dilewatkan ke execution context lain (misalnya callback thread/coroutine runner), dan mengapa compiler melarang *non-local return* pada konteks tersebut.

3. **Debugging Scope Function Nesting & Shadowing:**  
   Perhatikan cuplikan kode anti-pattern berikut:
   ```kotlin
   user?.let {
       it.profile?.let {
           updateAddress(it) // 'it' merujuk ke mana?
       }
   }
   ```
   Analisis bahaya *variable shadowing* dan *scope pollution* yang ditimbulkan oleh penumpukan scope function berbasis `it` atau `this`. Bagaimana Anda merancang convention/linter rule untuk membatasi nesting level scope functions dan kapan *explicit naming* mutlak diwajibkan?

4. **Non-Local Return vs Labelled Return pada Inline Scope Functions:**  
   Analisis implikasi eksekusi dari kode berikut:
   ```kotlin
   fun processTransactions(transactions: List<Transaction>) {
       transactions.forEach {
           if (it.isInvalid()) return // Exit mana?
       }
       println("Batch processed successfully")
   }
   ```
   Bandingkan perilaku di atas dengan penggunaan `return@forEach`. Bagaimana bytecode merepresentasikan kedua model return ini dan apa risiko tersembunyi jika fungsi pembungkusnya diubah dari inline (`forEach`) menjadi non-inline utility function kustom?

5. **Tail Call Optimization (`tailrec`) Constraints:**  
   Bagaimana kata kunci `tailrec` mengubah pemanggilan fungsi rekursif menjadi instruksi loop imperatif (seperti `goto`/jump loop) pada level bytecode? Sebutkan tiga kondisi di mana compiler Kotlin akan memberikan warning atau menolak mengoptimasi fungsi yang diberi anotasi `tailrec` (misalnya wrapping dalam `try-catch` atau penambahan operasi setelah pemanggilan rekursif).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Masalah Bottleneck & Alokasi Skala Besar
Sebuah microservice analitik memproses stream transaksi keuangan dengan volume 50.000 events/detik. Service ini menggunakan pipeline functional bergaya idiomatik:
```kotlin
fun processBatch(events: List<RawEvent>): List<EnrichedEvent> {
    return events
        .filter { it.isValid }
        .map { it.toDomain() }
        .filter { it.amount > BigDecimal.ZERO }
        .map { enrichWithMetadata(it) }
        .sortedBy { it.timestamp }
}
```
**Masalah:** Profiling APM menunjukkan tingginya frekuensi *Minor GC* dan lonjakan *Stop-The-World* (STW) latency yang menyebabkan throughput service drop hingga 40%.  
**Pertanyaan Diagnostik:**
1. Bedah alokasi memori intermediat yang terjadi pada chaining pipeline di atas!
2. Rekonstruksi implementasi di atas agar memory-efficient tanpa mengorbankan keamanan functional, bandingkan opsi antara penggunaan `Sequence` vs in-place mutations/imperative primitive loops! Kapan `sortedBy` merusak karakteristik streaming lazy evaluation?

### Skenario B: Race Condition dan Scope Escape pada State Mutabel
Dalam aplikasi Android/KMP yang multi-threaded, terdapat arsitektur state repository:
```kotlin
class SessionManager {
    var currentSession: UserSession? = null

    fun performSecureAction() {
        currentSession?.let { session ->
            // Simulasi thread context switch terjadi di sini
            validateToken(session.token)
            executeNetworkCall(session.token)
        }
    }
}
```
**Masalah:** Pada sistem dengan thread pool konkuren, sering terjadi `NullPointerException` atau operasi dijalankan menggunakan token sesi yang sudah di-*invalidate* oleh background thread lain yang mengeksekusi `currentSession = null`.  
**Pertanyaan Diagnostik:**
1. Mengapa idiomatic idiom `currentSession?.let { ... }` dianggap aman terhadap NPE lokal, namun tetap rentan terhadap race condition logika state pada objek yang direferensikan?
2. Bagaimana mekanisme immutable snapshot, atomic reference, atau functional state copying dapat menyelesaikan masalah ini tanpa memblokir thread menggunakan `synchronized` locks yang mahal?

### Skenario C: Arsitektur & Trade-Off: Functional vs Clean Maintainability
Sebuah tim migrasi dari Java ke Kotlin secara berlebihan menerapkan konsep "Functional Everything". Seluruh alur pendaftaran pengguna ditulis dalam satu rantai scope function raksasa:
```kotlin
fun registerUser(dto: UserDto): Result<UserResponse> =
    dto.validate()
        .also { logIncomingRequest(it) }
        .run { toEntity() }
        .apply { hashPassword() }
        .let { repository.save(it) }
        .run { toResponse() }
        .also { sendWelcomeEmail(it) }
        .let { Result.success(it) }
```
**Masalah:** Ketika terjadi kegagalan validasi, logic error, atau exception di tengah rantai, stack trace yang dihasilkan sangat sulit di-*trace* pada tools seperti Sentry/Datadog. Debugging menggunakan breakpoints menjadi mimpi buruk, dan *side-effects* (`also`) bercampur dengan *pure transformations* (`run`/`let`).  
**Pertanyaan Diagnostik:**
1. Berikan kritik arsitektural terhadap penggunaan scope function sebagai *control-flow engine* pada arsitektur domain!
2. Rancang ulang arsitektur fungsi di atas menggunakan pola *Railway-Oriented Programming* (ROP) berbasis `Result<T>` atau functional Monad (`Either`), dengan pemisahan tegas antara *transformasi data murni*, *operasi I/O berisiko*, dan *side-effect logging*.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance In-Memory Event Aggregator (Zero-Intermediate Pipeline)

#### Deskripsi Masalah:
Anda ditugaskan membangun modul audit processing bernama `AuditPipelineStream`. Modul ini menerima log event mentah dalam jumlah sangat besar, memvalidasi integritas payload, mengonversi data, memfilter anomali, dan mengagregasi hasilnya ke dalam bucket ringkasan.

#### Spesifikasi & Requirements:
1. **Pipeline DSL:** Buat fluent functional API yang memungkinkan konfigurasi pipeline pemrosesan event menggunakan generic higher-order functions.
2. **Context-Preserving Scope Functions:** Implementasikan minimal dua custom scope-like extensions yang menggunakan contracts API (`kotlin.contracts`) untuk membantu compiler melakukan *smart-casting* setelah validasi data.
3. **Lazy Execution Pipeline:** Seluruh rantai transformasi (`validate`, `transform`, `filter`) harus bersifat lazy, diproses elemen per elemen tanpa mengalokasikan koleksi sementara sebelum tahap terminasi/agregasi.
4. **Resilience & Error Containment:** Jika sebuah event korup atau melempar exception selama transformasi, pipeline tidak boleh crash. Gunakan tipe functional `Result<T>` atau data class sealed untuk mengisolasi kegagalan ke dalam error sink, sementara event valid tetap terproses.

#### Constraints:
* **Zero Additional Allocations:** Dilarang membuat temporary `List` atau `Set` di setiap tahapan transformasi data sebelum operasi terminal (`collect`/`aggregate`).
* **No Reflection & No Third-Party Libraries:** Hanya diperbolehkan menggunakan Kotlin Standard Library standard.
* **Inline Optimization:** Semua core processing operators kustom harus di-inline secara tepat (`inline`, `noinline`, atau `crossinline` sesuai kebutuhan) untuk mencegah alokasi instance lambda pada level bytecode.
* **Thread-Safety:** Pipeline aggregator harus thread-safe saat terminal operation mengumpulkan metrik dari coroutine/worker thread yang berbeda.

#### Expected Output:
* File implementasi Kotlin yang mencakup:
  1. Kontrak data (`RawAuditLog`, `ProcessedAuditLog`, `AggregationMetrics`).
  2. Implementasi custom extension operators lengkap dengan pemanfaatan `inline` dan compiler `contract`.
  3. Kode demonstrasi yang memproses minimal 100.000 mock events secara concurrent, menampilkan performa throughput, dan mencetak bucket hasil agregasi serta daftar error isolation.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan matematis dan teknis antara Context Receiver/Object (`this`) vs Parameter Receiver (`it`) dalam scope functions.
- [ ] Mekanisme internal JVM dalam mengeksekusi lambda: implementasi interface `FunctionN`, synthetic methods, dan instance caching.
- [ ] Dampak penggunaan `inline` function terhadap ukuran biner (code bloat) versus penghematan memory profiling (mengeliminasi overhead instance `Function`).
- [ ] Batasan penggunaan non-local return dan peran krusial `crossinline` untuk menjaga context encapsulation.
- [ ] Mengapa pemanggilan `Sequence.sorted()` memaksa buffering seluruh state (merusak sifat pure streaming memory footprint).
- [ ] Kapan functional programming idioms justru menimbulkan penurunan performa dibandingkan imperative loops (analisis CPU cache locality vs pointer indirection).

### Saya tidak perlu menghafal:
- [ ] Kode internal generated name compiler untuk class closure lambda (misalnya: `MyClass$process$1`).
- [ ] Daftar angka byte identifier untuk JVM instruction set (misal: opcode number untuk `invokevirtual` vs `invokeinterface`).
- [ ] Implementasi internal method assembly Java Runtime untuk invoke-dynamic (`indy`).

### Saya harus bisa melakukan:
- [ ] Melakukan decompile bytecode Kotlin ke Java di IDE/CLI untuk memverifikasi apakah sebuah lambda mengalokasikan objek baru di heap.
- [ ] Menulis custom higher-order function dengan konfigurasi `inline`, `noinline`, dan `crossinline` secara presisi tanpa compiler warning.
- [ ] Memilih scope function yang tepat (`let`, `run`, `with`, `apply`, `also`) secara natural sesuai idiomatic table tanpa ragu.
- [ ] Mengonversi imperative mutation code bertingkat menjadi functional pipeline yang pure, readable, dan testable tanpa trade-off performa.
- [ ] Mendeteksi dan merefaktor anti-pattern *scope function chaining* berlebih yang mengorbankan readability dan debugging production stack trace.