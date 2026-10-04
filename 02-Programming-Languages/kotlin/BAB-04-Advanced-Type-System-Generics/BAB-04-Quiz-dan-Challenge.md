# BAB 04: Quiz, Challenge, & Knowledge Check
**Advanced Type System & Generics**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Declaration-Site vs Use-Site Variance
Java menerapkan *use-site variance* secara eksklusif via *wildcards* (`? extends T` dan `? super T`), sedangkan Kotlin memperkenalkan *declaration-site variance* (`out T` dan `in T`) di samping tetap mendukung *type projection* (*use-site variance*). 
Jelaskan batasan teoritis dan ergonomi desain API pada Java yang coba dipecahkan oleh *declaration-site variance* Kotlin. Berikan justifikasi mengapa antarmuka seperti `List<out E>` di Kotlin secara inheren aman sebagai tipe *covariant*, dan apa konsekuensi arsitekturalnya terhadap parameter fungsi di dalam antarmuka tersebut.

### Soal 1.2: Top Type, Bottom Type, dan Hubungan Subtyping
Dalam sistem tipe Kotlin, hierarki subtyping diatur secara matematis oleh *Top Type* (`Any?`) dan *Bottom Type* (`Nothing`).
Uraikan bagaimana Kotlin menyusun relasi subtyping antara tipe-tipe primitif ter-boxing, objek non-nullable, objek nullable, `Unit`, dan `Nothing`. Mengapa ekspresi seperti `throw IllegalStateException()` atau `return` dapat memiliki tipe `Nothing`, dan bagaimana hal ini dieksploitasi oleh *type checker* Kotlin untuk melakukan *control flow analysis* dan *smart casting*?

### Soal 1.3: Implikasi Batasan Non-Nullable Generic
Secara default, parameter tipe generik `T` pada fungsi `fun <T> process(value: T)` memiliki batas atas (*upper bound*) implisit berupa `Any?`.
Jelaskan risiko laten yang dapat timbul di *production* jika Anda berasumsi `T` adalah *non-nullable*, khususnya saat berinteraksi dengan API Java atau parsing deserialisasi JSON. Bagaimana cara membatasi parameter tipe tersebut secara eksplisit agar strictly *non-nullable*, dan mengapa notasi `where T : Any` lebih disarankan dibanding alternatif lainnya pada definisi class yang kompleks?

### Soal 1.4: Type Erasure & Reified Type Parameters
JVM mengeksekusi bytecode dengan menghapus informasi tipe generik (*type erasure*) demi menjaga kompatibilitas mundur dengan versi pre-Java 5.
Jelaskan secara teknis mengapa Kotlin melarang operasi seperti `if (value is T)` atau `T::class.java` pada generic function reguler, dan bagaimana kata kunci `inline` yang dikombinasikan dengan `reified` mampu mem-bypass batasan JVM ini di tingkat bytecode. Apa *trade-off* performa dan batasan arsitektur (misalnya terkait *reflection* dan *binary size*) dari penggunaan `reified`?

### Soal 1.5: Star-Projection (`*`) vs Explicit Bound (`Any?`)
Banyak pengembang keliru menganggap `List<*>` identik dengan `List<Any?>`.
Jelaskan perbedaan fundamental antara star-projection `*` dan tipe eksplisit `Any?` berdasarkan konsep *existential types*. Mengapa Anda diizinkan membaca elemen dari `List<*>` sebagai `Any?`, tetapi dilarang keras menuliskan elemen apa pun (kecuali `Nothing`) ke dalam `MutableList<*>`? Bagaimana mekanisme compiler menjamin integritas tipe pada titik ini?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Autoboxing Trap pada `@JvmInline value class` dengan Generics
Perhatikan cuplikan arsitektur sistem transaksi moneter berikut:
```kotlin
@JvmInline
value class TransactionId(val raw: Long)

fun <T> persist(entityId: T) {
    DatabaseEngine.write(entityId.hashCode())
}

fun main() {
    val txId = TransactionId(10029384L)
    persist(txId) // Kasus A
    val list: List<TransactionId> = listOf(txId) // Kasus B
}
```
Analisis apa yang terjadi pada layer JVM bytecode untuk **Kasus A** dan **Kasus B**. Kapan *value class* mengalami boxing paksa kembali menjadi objek di heap memory, dan bagaimana hal tersebut berdampak pada garbage collection (GC) latency pada sistem *high-throughput low-latency*?

### Soal 2.2: F-Bounded Polymorphism dan Recursive Type Bounds
Dalam perancangan Fluent Builder DSL bertingkat (misalnya SQL Query Builder atau Data Pipeline Builder), implementasi inheritance sederhana sering kali merusak method chaining tipe turunan.
Bagaimana Anda memanfaatkan *recursive type bound* (F-bounded polymorphism) di Kotlin menggunakan sintaks:
```kotlin
abstract class StageBuilder<T : StageBuilder<T>> {
    abstract fun self(): T
    fun withTimeout(ms: Long): T = self().also { /* config */ }
}
```
Jelaskan mengapa pendekatan ini dibutuhkan untuk menghindari *unsafe downcasting* pada *subclass*, dan apa kelemahan (*leaky abstraction*) dari F-bounded polymorphism jika diakses oleh pemanggil API awam?

### Soal 2.3: Unchecked Casts & Deferred Heap Pollution
Perhatikan implementasi *in-memory cache* generik di bawah ini yang memicu *warning* `UNCHECKED_CAST`:
```kotlin
class TypedRegistry {
    private val store = HashMap<String, Any>()

    fun <T> register(key: String, item: T) {
        store[key] = item as Any
    }

    @Suppress("UNCHECKED_CAST")
    fun <T> get(key: String): T {
        return store[key] as T // Titik X
    }
}

fun main() {
    val registry = TypedRegistry()
    registry.register("timeout", 5000) // Int
    val timeout: String = registry.get("timeout") // Titik Y
    println(timeout.lowercase()) // Titik Z
}
```
Secara spesifik, di manakah `ClassCastException` pertama kali dilempar: **Titik X**, **Titik Y**, atau **Titik Z**? Uraikan transformasi bytecode JVM yang menyebabkan fenomena *deferred heap pollution* ini terjadi.

### Soal 2.4: Intersection Types via Generic Constraints (`where`)
Kotlin tidak memiliki sintaks union type formal (`A | B`), namun mendukung *intersection types* terbatas melalui generic constraints.
Analisis rancangan fungsi berikut:
```kotlin
fun <T> executeSafely(resource: T) 
    where T : AutoCloseable, T : Comparable<T> {
    // Business logic
}
```
Bagaimana compiler Kotlin memvalidasi pemanggilan fungsi ini terhadap tipe argumen yang diberikan? Bagaimana JVM meng-generate bytecode (khususnya *synthetic bridge methods* dan batasan *single class multiple interfaces*) untuk menjalankan fungsi tersebut tanpa melanggar model eksekusi JVM?

### Soal 2.5: `@UnsafeVariance` Escape Hatch dan Ancaman Mutabilitas
Dalam library standard Kotlin, antarmuka `Collection<out E>` mendeklarasikan:
```kotlin
public fun contains(element: @UnsafeVariance E): Boolean
```
Parameter `element` berada pada posisi *in* (posisi parameter fungsi), padahal tipe `E` dideklarasikan sebagai *covariant* (`out E`). 
Jelaskan mengapa compiler melarang parameter covariant muncul di posisi *in*, apa alasan teknis di balik penambahan `@UnsafeVariance` pada kasus spesifik `contains()`, dan bahaya fatal apa yang terjadi pada integritas memori jika Anda menyalahgunakan `@UnsafeVariance` pada method mutasi seperti `fun add(element: @UnsafeVariance E)`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Serialization Bottleneck pada Ultra High-Throughput Streaming Engine
Sebuah platform analitik finansial memproses 1.500.000 pesan/detik menggunakan Apache Kafka dan framework internal Kotlin. Komponen *Message Router* bertugas menerima *payload* biner mentah, men-deserialize ke tipe event generik `Envelope<T>`, lalu meneruskannya ke handler spesifik.

```kotlin
interface EventHandler<in T : DomainEvent> {
    fun handle(event: T)
}

class EventRouter {
    private val handlers = mutableMapOf<KClass<*>, EventHandler<*>>()

    fun <T : DomainEvent> register(clazz: KClass<T>, handler: EventHandler<T>) {
        handlers[clazz] = handler
    }

    fun dispatch(rawJson: String, targetType: KClass<out DomainEvent>) {
        val event = JacksonMapper.readValue(rawJson, targetType.java)
        val handler = handlers[targetType] as? EventHandler<DomainEvent>
        handler?.handle(event) // Heap allocation spike & ClassCastException di production
    }
}
```

*   **Gejala:** Profiler (Async-Profiler) mendeteksi 45% CPU cycles habis di alokasi `java.lang.reflect.Method` dan GC pauses akibat *boxing* serta pembuatan wrapper reflektif untuk parsing generic event. Sesekali terjadi `ClassCastException` di thread pool pemrosesan saat tipe event polymorphism bertingkat dipanggil.
*   **Pertanyaan Diagnostik:**
    1. Mengapa casting `handlers[targetType] as? EventHandler<DomainEvent>` tidak aman dan berpotensi gagal secara runtime di bawah JVM type erasure?
    2. Rancang ulang arsitektur `EventRouter` menggunakan kombinasi *Type-safe Heterogeneous Container*, *Reified Inline Function*, atau *Type Tokens* agar proses registrasi dan dispatching berjalan zero-allocation (tanpa boxing) dan compile-time type-safe!

---

### Skenario B: Type-Safe Phantom State Machine pada Distributed Payment Saga
Sebuah sistem *payment orchestrator* terdistribusi mengalami insiden di mana transaksi di-settle dua kali (*double capture*) akibat developer baru memanggil fungsi `capture()` pada transaksi yang statusnya masih `PENDING_AUTHORIZATION`, bukan `AUTHORIZED`. Kode lama mengandalkan *enum checking* di runtime yang ternyata terlewat di unit test:

```kotlin
// Desain lama yang rapuh
class PaymentTransaction(
    val id: UUID,
    var state: State,
    val amount: Long
) {
    fun capture() {
        if (this.state != State.AUTHORIZED) {
            // Sering kali developer lain lupa memanggil validasi ini saat batch processing
        }
        // Kirim request settlement ke bank provider
    }
}
```

*   **Tujuan:** Arsitek menuntut kegagalan transisi status transaksi harus dihentikan **pada saat compile-time**, bukan runtime exception, tanpa menambah overhead alokasi objek heap baru di setiap transisi state (*zero-overhead compile-time state-machine*).
*   **Pertanyaan Diagnostik:**
    1. Bagaimana Anda merancang pola **Phantom Types** di Kotlin menggunakan Generics, `@JvmInline value class`, dan *sealed interfaces* tanpa payload runtime?
    2. Tuliskan implementasi kode lengkap yang membuktikan bahwa pemanggilan `transaction.capture()` hanya valid jika dipanggil pada instance `PaymentTransaction<Authorized>`, dan akan memicu *compile error* jika dipanggil pada `PaymentTransaction<PendingAuthorization>`!

---

### Skenario C: Plugin Architecture Variance & Binary Compatibility Dilemma
Anda adalah Lead Architect yang sedang mendesain SDK modul perbankan terbuka (*open banking platform*). SDK ini menyediakan kontrak generik untuk integrasi *Third-Party Providers* (TPP):

```kotlin
// SDK Core (Dibuat oleh tim Anda)
interface AccountProvider<T : AccountDetails> {
    fun fetchAccount(accountId: String): T
}

interface AccountConsumer<T : AccountDetails> {
    fun consume(provider: AccountProvider<T>)
}
```

*   **Masalah Arsitektural:** Tim TPP A membuat implementasi untuk `CheckingAccountDetails` (subtipe dari `AccountDetails`). Namun, ketika mereka mencoba mengoper `AccountProvider<CheckingAccountDetails>` ke dalam `AccountConsumer<AccountDetails>`, compiler menolaknya dengan error *Type Mismatch*.
*   Tim internal mengusulkan menambahkan anotasi pemutus keamanan tipe atau casting mentah `as AccountProvider<AccountDetails>`.
*   **Pertanyaan Diagnostik:**
    1. Berdasarkan aturan Liskov Substitution Principle (LSP) dan PECS (*Producer-Extends, Consumer-Super*), mengapa compiler menolak kode TPP A?
    2. Bagaimana Anda harus merekayasa ulang interface `AccountProvider` dan `AccountConsumer` menggunakan *Declaration-site Variance* (`in`/`out`) agar backward compatible secara biner dan fleksibel digunakan oleh ribuan TPP dengan subtipe berbeda tanpa merusak type safety?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Type-Safe Event Bus with Compile-Time Filtering & Zero-Allocation Dispatcher

#### Problem Statement
Sebuah sistem reactive-trading internal membutuhkan engine bus event lokal yang menghubungkan *market-data feeds* dengan *execution algorithms*. Solusi eksisting berbasis Guava EventBus atau Spring ApplicationEventPublisher dibatalkan karena menimbulkan overhead boxing primitif, alokasi array refleksi, dan tidak adanya jaminan compile-time safety saat menyaring jenis event spesifik (menyebabkan silent drop atau runtime cast failure).

#### Requirements
1. **Type-Safe Subscriptions:** Bangun class `TypeSafeEventBus` yang mendukung registrasi subscriber berdasarkan tipe event konkret tanpa memasukkan string nama kelas atau manual parsing.
2. **Variance-Compliant Hierarchy:** 
   * Publisher harus bersifat *covariant-safe*: Producer event turunan (`OrderCancelledEvent`) harus bisa dialirkan ke subscriber yang mendengarkan tipe induk (`OrderEvent`).
   * Subscriber harus bersifat *contravariant-safe*: Handler untuk tipe umum harus dapat menerima tipe event yang lebih spesifik.
3. **Reified Inline Syntax:** Menyediakan ekstensi fungsi reified (e.g., `eventBus.subscribe<T> { event -> ... }`) untuk menyederhanakan registrasi.
4. **Compile-time Intersection Filter:** Mengimplementasikan generic extension function untuk subscriber yang hanya mendengarkan event yang memenuhi dua kriteria sekaligus (mengimplementasikan `MarketEvent` DAN `AuditableEvent`) via generic constraint `where`.
5. **No Reflection in Hot-Path:** Operasi `publish(event: E)` tidak boleh memanggil `java.lang.reflect.*` secara langsung pada hot-path eksekusi. Pemetaan handler harus dipetakan menggunakan token tipe yang efisien.

#### Constraints
* **Memory Limit:** Zero allocation pada pemanggilan loop eksekusi `publish()` (manfaatkan data structure internal array/primitive array cache jika diperlukan, hindari pembuatan iterator baru).
* **Strict Type Safety:** Tidak boleh menggunakan anotasi `@Suppress("UNCHECKED_CAST")` di luar boundary inisialisasi kontainer internal. Tidak boleh ada runtime error `ClassCastException` di sisi pemanggil.
* **Compatibility:** Berjalan optimal pada JVM target 17/21.

#### Expected Output
1. File implementasi Kotlin utuh yang memuat:
   * Interface & Class `TypeSafeEventBus`.
   * Type token mechanism yang aman.
   * Extension functions untuk DSL subscription.
2. Unit test demonstrasi yang membuktikan:
   * Event terkirim ke hierarki subscriber yang benar (polymorphic dispatch).
   * Compile error jika mencoba me-register event bus dengan tipe yang tidak kompatibel.
   * Tidak ada alokasi heap iterator saat `publish()` dijalankan (dapat ditunjukkan via assertions atau struktur loop manual).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Aturan matematis subtyping: Liskov Substitution Principle (LSP) dalam kerangka Covariance (`out`), Contravariance (`in`), dan Invariance.
- [ ] Batasan fisik Type Erasure pada JVM bytecode dan bagaimana metadata tipe disimpan dalam signature class/method.
- [ ] Mekanisme kerja `inline` dan `reified` di level decompiled bytecode (`javap -c`).
- [ ] Peran dan hierarki tipe intrinsik: Mengapa `Nothing` adalah subtipe dari semua tipe data, dan mengapa `Any?` adalah supertipe universal.
- [ ] Perbedaan fungsional dan implikasi keamanan tipe antara `*` (star projection) dan `Any?`.
- [ ] Hubungan antara Value Classes (`@JvmInline`), Generics, dan Autoboxing overhead di runtime.
- [ ] Pola F-Bounded Polymorphism dan teknik *Phantom Types* untuk compile-time domain modeling.
- [ ] Bahaya Heap Pollution yang ditimbulkan oleh penyalahgunaan `@Suppress("UNCHECKED_CAST")` dan `@UnsafeVariance`.

### Saya tidak perlu menghafal:
- [ ] Representasi exact binary metadata descriptor generik di format classfile JVM (`Signature` attribute string specifications).
- [ ] Sintaks *bridge method* internal yang di-generate compiler JVM untuk kasus F-bounds kompleks.
- [ ] Detail algoritma spesifik *type inference solver* milik compiler Kotlin (K2 frontend algorithm).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan memperbaiki *compile error* terkait variansi (`Type parameter T is declared as 'out' but occurs in 'in' position`).
- [ ] Menghilangkan alokasi objek pada generic pipeline menggunakan `@JvmInline value class` dan generic non-boxing patterns.
- [ ] Mengonversi sistem validasi berbasis runtime exceptions menjadi compile-time safe state-machine menggunakan *Phantom Types*.
- [ ] Membangun generic DSL dan type-safe heterogeneous containers yang bebas dari unchecked casts di sisi consumer.
- [ ] Membaca bytecode hasil decompile Kotlin (via IntelliJ / `javap`) untuk menganalisis apakah generic function Anda memicu alokasi heap atau boxing yang tidak diinginkan.