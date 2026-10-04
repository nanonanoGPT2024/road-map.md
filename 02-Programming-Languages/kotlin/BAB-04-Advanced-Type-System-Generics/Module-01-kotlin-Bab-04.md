# Advanced Type System & Generics

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 02-Programming-Languages
*   **Mata Pelajaran:** Kotlin
*   **Bab:** 04 — Sistem Tipe Tingkat Lanjut & Meta-pemrograman
*   **Modul:** 01 — Advanced Type System & Generics
*   **Tingkat Kesulitan:** Advanced / L4
*   **Prasyarat:** Pemahaman OOP Kotlin mendalam, pemahaman dasar JVM Bytecode, pemahaman fungsi generic dasar (`<T>`), Null Safety mechanics (`T?` vs `Any`).
*   **Alokasi Waktu Belajar:** 180 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik mampu:
1. Membedah arsitektur sistem tipe Kotlin (*subtyping lattice*, *bounded polymorphism*, dan representasi *type erasure* di level JVM bytecode).
2. Mengimplementasikan *Declaration-site Variance* (`out` dan `in`) serta *Use-site Variance* (*Type Projections*) untuk menyelesaikan problem *subtyping* polimorfik tanpa mengorbankan *type safety*.
3. Menganalisis batasan JVM Type Erasure dan mengatasinya menggunakan kombinasi `inline` functions, `reified` type parameters, dan *Type Tokens*.
4. Mengonstruksi generic constraints tingkat lanjut (multiple bounds `where`, intersection types via multiple bounds, recursively bound types / CRTP).
5. Merancang pustaka tipe fungsional berkinerja tinggi (*zero-cost abstractions*) dengan mengoptimalkan eliminasi overhead boxing primitif dan memory footprint allocation.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Prinsip Substitusi Liskov (LSP) dan Dilema Generic
Secara intuitif, jika `Dog` adalah subtype dari `Animal`, seorang programmer pemula sering mengasumsikan bahwa `List<Dog>` adalah subtype dari `List<Animal>`. Asumsi ini salah dalam sistem tipe invarian (seperti Java arrays secara semantik tidak aman, atau Java generics default).

```
   Dog <: Animal
       =/=>
List<Dog> <: List<Animal>
```

Jika `MutableList<Dog>` diperlakukan sebagai `MutableList<Animal>`, Anda dapat memasukkan `Cat` (yang juga merupakan `Animal`) ke dalam list tersebut via referensi `MutableList<Animal>`. Ketika list dibaca kembali sebagai `MutableList<Dog>`, program akan crash saat runtime dengan `ClassCastException`.

### Mental Model: Producer vs Consumer (PECS / OLIE)
Di Java, berlaku prinsip PECS (*Producer Extends, Consumer Super*). Di Kotlin, mental model ini disederhanakan dan diperkuat di level sintaksis deklarasi:
*   **`out` = PRODUCER:** Tipe data hanya *keluar* (read-only / covariance). Jika class Anda hanya menghasilkan instans `T` (metode mengembalikan `T`), aman untuk mengizinkan subtyping: `Class<Sub>` adalah subtype dari `Class<Super>`.
*   **`in` = CONSUMER:** Tipe data hanya *masuk* (write-only / contravariance). Jika class Anda hanya mengonsumsi `T` (metode menerima `T` sebagai argumen), subtyping dibalik: `Class<Super>` adalah subtype dari `Class<Sub>`.

### Lattice Sistem Tipe Kotlin
Kotlin memodelkan sistem tipe sebagai lattice berarah terikat (bounded lattice):
*   Top Type: `Any?` (mencakup semua tipe nullable dan non-nullable).
*   Non-nullable Top Type: `Any`.
*   Bottom Type: `Nothing` (subtype dari setiap tipe yang valid).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

```
                            +-------------------+
                            |       Any?        | (Ultimate Top Type)
                            +---------+---------+
                                      |
                      +---------------+---------------+
                      |                               |
              +-------v-------+               +-------v-------+
              |      Any      |               |     Null      |
              +-------+-------+               +---------------+
                      |
        +-------------+-------------+
        |                           |
+-------v-------+           +-------v-------+
|    Number     |           |  CharSequence |
+-------+-------+           +-------+-------+
        |                           |
+-------v-------+           +-------v-------+
|      Int      |           |    String     |
+-------+-------+           +-------+-------+
        |                           |
        +-------------+-------------+
                      |
              +-------v-------+
              |    Nothing    | (Ultimate Non-Nullable Bottom Type)
              +-------+-------+
                      |
              +-------v-------+
              |   Nothing?    | (Type of 'null' literal)
              +---------------+
```

### Alur Resolusi Tipe pada Kompiler (Frontend Resolution)

```
[ Generic Source Code ] 
          |
          v
[ Kotlin Compiler Frontend (K2/FIR) ]
          |
          +---> 1. Check Variance Position Validation (in vs out)
          |        - Method Return -> Covariant (out) Position
          |        - Method Param  -> Contravariant (in) Position
          |
          +---> 2. Solve Generic Constraints
          |        - Check bounds (T : UpperBound, T : Interface)
          |        - Resolve Type Projections (Star projection '*')
          |
          v
[ Intermediate Representation (IR) ]
          |
          +---> Strip Generic Information (Type Erasure to Upper Bounds)
          +---> Synthetic Cast Insertions at call sites
          +---> Inlining Reified Functions (Replace Type Parameters with Class Literals)
          |
          v
[ JVM Bytecode Execution ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. JVM Type Erasure & Metadata
JVM tidak memiliki konsep native untuk generics terparameterisasi dinamis pada runtime (karena kompatibilitas mundur dengan Java 1.4). Saat kompilasi:
*   Setiap `List<T>` menjadi `List` mentah (raw type) di JVM bytecode.
*   `T` di-erase ke upper bound-nya. Jika `T` tidak memiliki bound eksplisit, di-erase menjadi `java.lang.Object`. Jika `T : Number`, di-erase menjadi `java.lang.Number`.
*   Kompiler Kotlin menambahkan metadata via anotasi `@Metadata` pada class file bytecode. Metadata ini berisi protobuf binary yang mendeskripsikan informasi generic Kotlin yang sebenarnya, memungkinkan interoperabilitas antar modul Kotlin tanpa kehilangan informasi nullability atau variance.

### 2. Declaration-site vs Use-site Variance
*   **Declaration-site Variance (`out` / `in` pada class header):**
    ```kotlin
    interface ReadOnlyRepository<out T> { // T hanya boleh di covariant position
        fun getById(id: String): T       // Valid: T diekspos sebagai return type
        // fun save(entity: T)            // COMPILE ERROR: Type parameter T is in 'in'-position
    }
    ```
    Keuntungan: Pengguna class tidak perlu mendeklarasikan wildcard `? extends T` berulang kali seperti pada Java.

*   **Use-site Variance (Type Projection):**
    Diperlukan ketika kelas invariant (seperti `MutableList<E>`) harus digunakan secara fleksibel pada fungsi tertentu.
    ```kotlin
    fun copy(from: Array<out Any>, to: Array<Any>) { ... }
    ```
    Bytecode yang dihasilkan setara dengan Java `Array<? extends Object>`.

### 3. Reification Mechanics
Instansiasi tipe generic seperti `T::class.java` atau `item is T` dilarang secara standar karena runtime JVM tidak mengetahui apa itu `T`. 
Kotlin mengatasi ini via `inline fun <reified T>`. Mekanismenya:
1.  Fungsi ditandai `inline`.
2.  Kompiler menyalin *body* fungsi langsung ke call-site saat kompilasi.
3.  Di call-site, tipe konkret sudah diketahui pasti oleh kompiler (misal: `findService<DatabaseService>()`).
4.  Kompiler mengganti referensi `T::class.java` menjadi bytecode `DatabaseService.class` secara langsung (LDC instruction).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Covariance (`out`), Contravariance (`in`), dan Invariance

Definisi formal hubungan subtyping:
Diberikan tipe $A$ dan $B$, di mana $A \le B$ ($A$ adalah subtype dari $B$), dan konstruktor tipe $F<T>$:

$$\begin{aligned}
\text{Covariant:} \quad & A \le B \implies F<A> \le F<B> \quad (\text{Kotlin: } \texttt{out } T) \\
\text{Contravariant:} \quad & A \le B \implies F<B> \le F<A> \quad (\text{Kotlin: } \texttt{in } T) \\
\text{Invariant:} \quad & F<A> \text{ dan } F<B> \text{ tidak memiliki relasi subtyping}
\end{aligned}$$

#### Aturan Posisi Varians (Position Rules)
Kompiler Kotlin memberlakukan aturan restriktif berdasarkan posisi tipe dalam deklarasi:
*   **Posisi Out (Output):** Nilai kembalian fungsi, properti generic `val`.
*   **Posisi In (Input):** Argumen fungsi, properti generic `var` (karena `var` membangkitkan getter/out dan setter/in sekaligus).

| Variance Keyword | Valid Positions | Subtyping Relation ($Dog \le Animal$) | Java Equivalent |
| :--- | :--- | :--- | :--- |
| *(None - Invariant)* | In & Out | $Box<Dog> \neq Box<Animal>$ | `Box<T>` |
| `out` (Covariant) | Out only | $Producer<Dog> \le Producer<Animal>$ | `Producer<? extends Animal>` |
| `in` (Contravariant)| In only | $Consumer<Animal> \le Consumer<Dog>$ | `Consumer<? super Dog>` |

### Star-Projection (`*`)
Star-projection digunakan saat kita tidak mengetahui atau tidak peduli dengan argumen tipe konkret, namun tetap ingin mempertahankan type-safety:
*   Untuk `Foo<out T : UpperBound>`: `Foo<*>` berarti `Foo<out UpperBound>`. Anda dapat membaca nilai sebagai `UpperBound`.
*   Untuk `Foo<in T>`: `Foo<*>` berarti `Foo<in Nothing>`. Anda tidak dapat menulis nilai apa pun ke dalamnya (karena tidak ada instans `Nothing`), hanya membaca `Any?`.
*   Untuk `Foo<T>` (invarian): `Foo<*>` memproyeksikan `out Any?` untuk pembacaan dan `in Nothing` untuk penulisan.

### Multiple Bounds & Intersection Types
Kotlin mendukung recursive constraint dan multiple bounds menggunakan sintaks `where`:
```kotlin
fun <T> process(item: T) where T : CharSequence, T : Comparable<T>
```
Secara internal, kompiler memastikan bahwa instans `T` harus mengimplementasikan kedua antarmuka. Pada level JVM bytecode, representasi tipe di-erase ke bound pertama (`CharSequence`), dan pemanggilan metode dari bound kedua (`Comparable`) akan disuntikkan checkcast eksplisit (*bridge method/synthetic cast*).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi varians deklarasi, *type projection*, recursive generics, dan *reified type parameters*.

```kotlin
// 1. Model Domain Hierarki
open class Payload(val traceId: String)
class OrderPayload(traceId: String, val orderId: Long) : Payload(traceId)

// 2. Declaration-Site Covariance (Producer)
interface EventSource<out T : Payload> {
    fun emit(): T
}

// 3. Declaration-Site Contravariance (Consumer)
interface EventSink<in T : Payload> {
    fun consume(event: T)
}

// 4. Invariant Processor dengan Use-Site Variance
class EventPipeline<T : Payload> {
    private val buffer = mutableListOf<T>()

    fun transferFrom(source: EventSource<T>) {
        buffer.add(source.emit())
    }

    // Use-site projection: Source memproduksi subtype dari T
    fun mergeSource(externalSource: EventSource<out T>) {
        buffer.add(externalSource.emit())
    }

    // Use-site projection: Sink mengonsumsi supertype dari T
    fun drainTo(targetSink: EventSink<in T>) {
        for (item in buffer) {
            targetSink.consume(item)
        }
        buffer.clear()
    }
}

// 5. Multiple Bounds & Recursive Bounds (CRTP)
interface Entity<T : Entity<T>> {
    fun merge(other: T): T
}

fun <T> deduplicateAndSort(items: List<T>): List<T> 
    where T : Entity<T>, T : Comparable<T> {
    return items.distinct().sorted()
}

// 6. Reified Types untuk Mengakali Type Erasure
inline fun <reified T : Payload> filterPayloadType(list: List<Payload>): List<T> {
    val results = mutableListOf<T>()
    for (item in list) {
        if (item is T) { // Valid karena T reified
            results.add(item)
        }
    }
    return results
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 2–3:** `Payload` dan `OrderPayload` mendefinisikan relasi subtipe $OrderPayload \le Payload$.
*   **Baris 6:** `interface EventSource<out T : Payload>`. Keyword `out` menyatakan bahwa `EventSource` kovarian terhadap `T`. Konsekuensinya: `EventSource<OrderPayload>` adalah subtipe sah dari `EventSource<Payload>`. Kompiler melarang penambahan metode seperti `fun put(item: T)` pada interface ini.
*   **Baris 11:** `interface EventSink<in T : Payload>`. Keyword `in` menyatakan kontravariansi. `EventSink<Payload>` merupakan subtipe sah dari `EventSink<OrderPayload>`. Sebuah sink yang mampu menangani sembarang `Payload` secara logis aman untuk dialokasikan guna menangani `OrderPayload`.
*   **Baris 16:** `class EventPipeline<T : Payload>` adalah invarian. Objek pipeline memegang state mutable, menjadikannya produsen sekaligus konsumen internal.
*   **Baris 24:** `fun mergeSource(externalSource: EventSource<out T>)`. Ini merupakan contoh *use-site variance*. Walaupun `EventSource` sudah covariant di level deklarasi, pola ini menunjukkan cara memperlakukan tipe argumen sebagai produsen eksplisit pada level fungsi.
*   **Baris 29:** `fun drainTo(targetSink: EventSink<in T>)`. Menjamin bahwa sink yang menerima data dapat berupa tipe generic $T$ atau supertype dari $T$.
*   **Baris 38–39:** `interface Entity<T : Entity<T>>`. Menerapkan idiom *Curiously Recurring Template Pattern* (CRTP). Ini menjamin method `merge` hanya dapat menggabungkan tipe konkret yang sama persis, bukan sembarang turunan `Entity`.
*   **Baris 42–43:** `where T : Entity<T>, T : Comparable<T>`. Blok batasan ganda (*multiple bounds*). Kompiler memastikan bahwa tipe substitusi `T` harus memenuhi kedua kontrak interface secara simultan.
*   **Baris 48:** `inline fun <reified T : Payload> filterPayloadType(...)`. Operator `reified` hanya dapat digunakan bersama `inline`. Pada baris 51, ekspresi `item is T` dapat dikompilasi karena informasi tipe `T` diinjeksi langsung ke call site sebagai `instanceof` bytecode terhadap kelas target konkret.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Konteks Masalah
Dalam arsitektur *Event-Driven Microservices*, sering dibutuhkan sistem *In-Memory Event Bus & Pipeline Broker* yang menangani ratusan event types berbeda (misal: `TransactionCreated`, `UserRegistered`, `FraudAlertDetected`).

### Masalah Desain Klasik
1.  **Type Safety vs Flexibility:** Menggunakan bus berbasis `Any` memerlukan *unsafe casting* manual (`as TransactionCreated`) pada setiap handler. Ini rawan melempar `ClassCastException` di production runtime.
2.  **Covariant Stream Demultiplexing:** Handler yang menangani `DomainEvent` dasar tidak dapat didaftarkan untuk mendengarkan channel event spesifik jika publisher bersifat invarian.
3.  **Deserialization Breakdown:** Serializer/deserializer JSON/Protobuf kehilangan konteks parameter generic kompleks ketika runtime JVM melakukan *type erasure*, menyebabkan error pemetaan nested generic types (seperti `EventWrapper<List<Order>>`).

### Solusi Arsitektural
Membangun *Strongly-Typed Asynchronous Event Bus* dengan:
*   Declaration-site variance untuk Event Channels.
*   Reified Type Tokens untuk dynamic event routing.
*   Contravariant subscriber dispatcher.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi *High-Performance Typed Event Dispatcher*:

```kotlin
package com.architecture.generics.eventbus

import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList
import kotlin.reflect.KClass

// 1. Domain Event Hierarchy
interface DomainEvent {
    val eventId: String
    val timestamp: Long
}

data class OrderCreatedEvent(
    override val eventId: String,
    override val timestamp: Long,
    val orderId: String,
    val amountCents: Long
) : DomainEvent

data class FraudDetectedEvent(
    override val eventId: String,
    override val timestamp: Long,
    val riskScore: Double
) : DomainEvent

// 2. Contravariant Event Listener (Consumer)
fun interface EventListener<in E : DomainEvent> {
    fun onEvent(event: E)
}

// 3. Covariant Event Envelope (Producer)
interface EventEnvelope<out E : DomainEvent> {
    val traceId: String
    val payload: E
}

private class EventEnvelopeImpl<out E : DomainEvent>(
    override val traceId: String,
    override val payload: E
) : EventEnvelope<E>

// 4. Central Type-Safe Event Bus
class TypeSafeEventBus {
    // Menyimpan mapping KClass ke daftar listener invarian berbasis Star-Projection
    private val subscribers = ConcurrentHashMap<KClass<*>, CopyOnWriteArrayList<EventListener<*>>>()

    // Registrasi bertipe reified (Use-Site & Runtime Reification)
    inline fun <reified E : DomainEvent> subscribe(listener: EventListener<E>) {
        subscribeInternal(E::class, listener)
    }

    @PublishedApi
    internal fun <E : DomainEvent> subscribeInternal(clazz: KClass<E>, listener: EventListener<E>) {
        val list = subscribers.computeIfAbsent(clazz) { CopyOnWriteArrayList() }
        list.add(listener)
    }

    // Publish dengan kovariansi penuh
    @Suppress("UNCHECKED_CAST")
    fun <E : DomainEvent> publish(event: E) {
        val targetClass = event::class
        val listeners = subscribers[targetClass] ?: return
        
        for (rawListener in listeners) {
            // Unchecked cast internal aman karena registrasi diisolasi oleh generic contract subscribeInternal
            val listener = rawListener as EventListener<E>
            listener.onEvent(event)
        }
    }

    // Envelope Factory Pattern memanfaatkan Covariance
    fun <E : DomainEvent> wrap(traceId: String, event: E): EventEnvelope<E> {
        return EventEnvelopeImpl(traceId, event)
    }

    // Polimorphic Envelope Processing
    fun processEnvelope(envelope: EventEnvelope<DomainEvent>) {
        println("Processing Trace [${envelope.traceId}] for Event [${envelope.payload.eventId}]")
        publish(envelope.payload)
    }
}

// 5. Eksekusi End-to-End
fun main() {
    val bus = TypeSafeEventBus()

    // Registrasi Listener Tipe Spesifik
    bus.subscribe<OrderCreatedEvent> { event ->
        println("Order Handler: Order ${event.orderId} processed with amount: ${event.amountCents}")
    }

    // Registrasi General Domain Listener via Consumer Polymorphism
    val genericListener = EventListener<DomainEvent> { event ->
        println("Audit Logger: Generic Event Received: ${event.eventId} at ${event.timestamp}")
    }
    
    // DomainEvent listener dapat menangani OrderCreatedEvent secara valid
    bus.subscribeInternal(OrderCreatedEvent::class, genericListener)

    // Penerbitan Event Konkret
    val orderEvent = OrderCreatedEvent(
        eventId = "EVT-9001",
        timestamp = System.currentTimeMillis(),
        orderId = "ORD-4412",
        amountCents = 150_000
    )

    // Covariance Proof:
    // EventEnvelopeImpl<OrderCreatedEvent> dapat dilempar ke fungsi yang meminta EventEnvelope<DomainEvent>
    val envelope: EventEnvelope<OrderCreatedEvent> = bus.wrap("TRACE-XYZ-88", orderEvent)
    bus.processEnvelope(envelope)
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Declaration-site Variance (Kotlin) vs Use-site Variance (Java Wildcards)

| Dimensi Arsitektural | Kotlin Declaration-site (`out`/`in`) | Java Use-site Wildcards (`? extends`/`? super`) |
| :--- | :--- | :--- |
| **Ergonomi API** | **Sangat Tinggi.** Didefinisikan sekali di interface, otomatis berlaku di semua call-site. | **Rendah.** Pembuat method harus menulis `List<? extends T>` di setiap parameter method. |
| **Fleksibilitas Mutasi** | Terbatas pada kelas yang secara alami read-only atau write-only. | Tinggi pada mutable collection (dapat diubah sifatnya secara parsial di call site). |
| **Kompleksitas Mental Model** | Rendah. Konsep Producer/Consumer langsung terefleksi via `out`/`in`. | Tinggi. Rawan membingungkan developer mengenai perbedaan `extends` vs `super`. |

### Reified Inline Functions vs Java Type Tokens (`Class<T>`)

| Dimensi | Kotlin `inline fun <reified T>` | Java Type Token (`Class<T> clazz`) |
| :--- | :--- | :--- |
| **Overhead Bytecode** | Terjadi *code bloat* jika fungsi yang di-inline berukuran besar dan dipanggil di banyak tempat. | Ukuran binary stabil; implementasi fungsi hanya ada satu di method area. |
| **Syntactic Cleanliness**| Sintaksis bersih: `bus.subscribe<MyEvent>()`. | Memerlukan passing parameter eksplisit: `bus.subscribe(MyEvent.class)`. |
| **Interoperabilitas Java** | **Nol.** Tidak dapat dipanggil secara wajar dari kode Java murni. | Sempurna. Didukung native oleh Java Reflection. |
| **Dukungan Primitif** | Mendukung pengecekan tipe tanpa overhead jika tipe primitif terdefinisi. | Boxing otomatis ke `java.lang.Integer`, dll. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The `@UnsafeVariance` Escape Hatch
Terkadang tipe kovarian (`out T`) harus muncul pada posisi parameter fungsi (`in`). Contoh klasik: `Collection<out E>.contains(element: E)`.
Secara matematis, `contains` membaca argument, sehingga $E$ berada pada posisi contravariant (`in`). Ini memicu error kompilasi.

```kotlin
// Kompiler menolak kode ini secara default:
interface BadSet<out T> {
    fun contains(element: T): Boolean // Compile Error: Type parameter T is in 'in'-position
}

// Solusi Kompiler Kotlin via Anotasi Internal:
interface SafeSet<out T> {
    fun contains(element: @UnsafeVariance T): Boolean // Divalidasi aman secara operasional
}
```
**Pitfall:** Menggunakan `@UnsafeVariance` secara sembarangan pada operasi yang memodifikasi state internal akan menghancurkan *runtime type-safety* dan mengakibatkan `ClassCastException`. Anotasi ini hanya boleh digunakan jika metode hanya membaca parameter untuk komparasi identitas/kesetaraan (`equals`, `contains`).

### 2. Primitive Array Variance Invariance
Meskipun `Int` adalah subtype dari `Number`, `Array<Int>` **bukan** subtype dari `Array<Number>` (invarian). Terlebih lagi:
`IntArray` sama sekali **bukan** `Array<Int>`. 
*   `Array<Int>` dikompilasi ke `java.lang.Integer[]` (boxed array).
*   `IntArray` dikompilasi ke `int[]` (primitive unboxed array).
Mencoba mentransfer atau memproyeksikan `IntArray` ke `Array<out Number>` akan gagal pada level kompilasi.

### 3. Dynamic Casts vs Erased Generics
Ekspresi berikut ini:
```kotlin
fun <T> checkList(list: List<Any?>) {
    if (list is List<T>) { // COMPILE ERROR: Cannot check for instance of erased type
        println("Matched!")
    }
}
```
Kompiler melarang ini karena informasi generic list telah di-erase. Anda hanya diizinkan memeriksa:
```kotlin
if (list is List<*>) { ... } // Star projection match: Valid
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Memakai `var` pada Properti Interface Covariant (`out`)
```kotlin
// ANTI-PATTERN:
interface Repository<out T> {
    var lastRetrieved: T // COMPILE ERROR!
}
```
**Mengapa Terjadi:** Properti `var` secara otomatis menghasilkan getter (`fun get(): T` -> out position) dan setter (`fun set(value: T)` -> in position). Posisi setter melanggar aturan kovarian `out`.

**Solusi:** Gunakan `val` untuk class covariant:
```kotlin
// CORRECT:
interface Repository<out T> {
    val lastRetrieved: T
}
```

---

### Mistake 2: Type Argument Erasure pada Star Projection Map Casting
```kotlin
// ANTI-PATTERN:
fun processPayloads(map: Map<String, Any>) {
    @Suppress("UNCHECKED_CAST")
    val typedMap = map as Map<String, List<OrderPayload>> 
    // Tidak aman! Saat runtime JVM hanya mengecek apakah 'map' adalah instans dari java.util.Map.
    // Isi di dalam list tidak divalidasi sama sekali!
    val item: OrderPayload = typedMap["orders"]!![0] // ClassCastException di sini saat runtime!
}
```
**Solusi:** Terapkan parsing defensif bertahap menggunakan inline reified functions atau library type token terverifikasi.

---

### Mistake 3: Overuse `reified` Membengkakkan Bytecode (*Inlining Bloat*)
```kotlin
// ANTI-PATTERN:
inline fun <reified T> hugeProcessingPipeline(data: String) {
    // 500 baris kode kompleks parsing, database query, logging
}
```
**Mengapa Terjadi:** Menyematkan 500 baris kode di setiap titik pemanggilan (*call-site*) menduplikasi bytecode ribuan kali, merusak cache instruction CPU (L1i cache miss).

**Solusi:** Gunakan pola *Delegation to Private Non-reified Core*:
```kotlin
// CORRECT:
inline fun <reified T> optimizedPipeline(data: String) {
    // Tangkap class literal, delegasikan eksekusi berat ke fungsi reguler
    internalNonInlinedCore(data, T::class.java)
}

fun internalNonInlinedCore(data: String, targetClass: Class<*>) {
    // 500 baris logika terisolasi di satu tempat di bytecode
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Bound Declaration:** Selalu definisikan upper bound eksplisit jika tipe generik tidak diharapkan bernilai nullable atau `Any?`. Gunakan `<T : Any>` untuk mencegah masuknya nilai `null` tanpa sengaja.
2.  **Prinsip OLIE pada Desain API:** *Out for Output, In for Input*. Jika Anda merancang interface yang fungsinya murni mengembalikan data (misal: DAO, Factory, Stream), deklarasikan selalu sebagai `out`. Jika murni konsumsi data (misal: Serializer, Validator, Renderer), deklarasikan sebagai `in`.
3.  **Gunakan Typealiases untuk Konstruk Generic Kompleks:**
    Generics bertingkat sulit dibaca oleh engineer lain.
    ```kotlin
    // Hindari repetisi:
    val registry: ConcurrentHashMap<KClass<out Payload>, List<EventListener<in Payload>>>
    
    // Terapkan:
    typealias PayloadClass = KClass<out Payload>
    typealias PayloadConsumers = List<EventListener<in Payload>>
    val registry: ConcurrentHashMap<PayloadClass, PayloadConsumers>
    ```
4.  **Star-Projection Hygiene:** Jangan gunakan `*` jika interface generic Anda memiliki multiple type parameters yang memiliki dependensi antar satu sama lain. Batasi penggunaan `*` murni pada utility atau inspecting logic.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Autoboxing Overhead pada Generics
JVM Generic hanya bekerja pada tipe referensi (`java.lang.Object`). Ketika tipe primitif seperti `Int`, `Double`, atau `Long` dipetakan ke type parameter `T`, JVM melakukan autoboxing otomatis (`int` -> `Integer`).

```kotlin
fun <T> sumGeneric(list: List<T>, operation: (T, T) -> T): T // Mengakibatkan alokasi jutaan objek Integer di heap
```

#### Mitigasi:
1.  Untuk operasi intensif CPU / memori, sediakan overload berbasis primitive arrays (`IntArray`, `LongArray`) daripada `List<T>`.
2.  Gunakan `@JvmSuppressWildcards` dan `@JvmWildcard` untuk mengontrol emisi generic bytecode saat interoperabilitas dengan Java, mengurangi pembuatan method synthetic bridge yang tidak perlu.
3.  Manfaatkan `inline value class` (yang diperkenalkan di Kotlin modern) untuk membungkus tipe generic tanpa alokasi memori tambahan di heap runtime:

```kotlin
@JvmInline
value class Identifier<out T : Entity<*>>(val rawId: String)
// Bytecode yang dikompilasi akan diperlakukan sebagai String biasa tanpa wrapper object alokasi heap.
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### Type Confusion via Unchecked Casts
Kelemahan paling umum pada generic systems adalah *Type Confusion*, yang timbul ketika developer menggunakan `@Suppress("UNCHECKED_CAST")` tanpa validasi matematis yang ketat. 

Jika penyerang berhasil mengontrol data input yang diarahkan ke unsafe cast, mereka dapat mengeksploitasi memory corruptions (pada native layer) atau Denial of Service melalui *unhandled class cast crashes*.

### Hardening Checklist
* [ ] Tidak ada `@Suppress("UNCHECKED_CAST")` yang terpapar ke public API boundary.
* [ ] Setiap internal unchecked cast harus didahului dengan `KClass.isInstance()` atau `reified is T` check jika call-site memungkinkan.
* [ ] Cegah Prototype Pollution pada generic dictionary: Ketika menerima nested generic maps dari untrusted network payload (JSON), jangan lakukan deserialisasi langsung ke `Map<String, T>`. Terapkan skema parsing yang memvalidasi struktur leaf-node secara konkret.

```kotlin
// Defensive Casting Boundary Pattern
fun <T : Any> safeCastPayload(rawObject: Any, targetToken: KClass<T>): Result<T> {
    return if (targetToken.isInstance(rawObject)) {
        Result.success(targetToken.java.cast(rawObject))
    } else {
        Result.failure(SecurityException("Type confusion detected: Expected ${targetToken.qualifiedName} but found ${rawObject::class.qualifiedName}"))
    }
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Debugging Type Erasure di Runtime
Karena tipe di-erase saat eksekusi bytecode, *stack trace* standar tidak menunjukkan parameter generic aktual dari list atau map yang menyebabkan kegagalan casting.

### Strategi Logging Contextual Generic
Suntikkan runtime type awareness ke dalam interceptor logging:

```kotlin
open class TypeTag<T> {
    // Menangkap representasi tipe via anonymous class reflection (Super Type Token Idiom)
    val type: java.lang.reflect.Type = 
        (javaClass.genericSuperclass as java.lang.reflect.ParameterizedType).actualTypeArguments[0]
}

inline fun <reified T> buildDebugContext(item: T): Map<String, String> {
    return mapOf(
        "concreteType" to (item?.let { it::class.qualifiedName } ?: "NULL"),
        "parameterType" to T::class.java.canonicalName,
        "isBoxedPrimitive" to (T::class.javaPrimitiveType != null).toString()
    )
}
```

### Memeriksa Bytecode Dekompilasi
Untuk memverifikasi apakah varians atau inlining bekerja optimal tanpa unnecessary object creation:
1.  Gunakan IntelliJ IDEA: `Tools` > `Kotlin` > `Show Kotlin Bytecode`.
2.  Klik tombol `Decompile` untuk melihat terjemahan Java setaranya.
3.  Cek keberadaan instruksi berikut:
    *   `CHECKCAST`: Menandakan titik di mana synthetic cast disuntikkan.
    *   `INVOKEVIRTUAL java/lang/Integer.valueOf`: Menandakan terjadi autoboxing heap allocation.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```kotlin
// ==============================================================================
// KOTLIN ADVANCED GENERICS QUICK REFERENCE
// ==============================================================================

// 1. VARIANCE
interface Producer<out T>  // Covariant     (T hanya keluar / return type)
interface Consumer<in T>   // Contravariant (T hanya masuk / parameter type)
interface Processor<T>     // Invariant     (T keluar & masuk)

// 2. SUBTYPING PRINCIPLES (Misal Dog <: Animal)
// Producer<Dog> <: Producer<Animal>     (Valid: Covariant)
// Consumer<Animal> <: Consumer<Dog>     (Valid: Contravariant)
// Processor<Dog> != Processor<Animal>   (Strict Invariant)

// 3. USE-SITE VARIANCE (TYPE PROJECTION)
fun copy(from: Array<out Any>, to: Array<in String>)

// 4. STAR-PROJECTION
val anyList: List<*> = listOf("A", 1, true) // List<out Any?>
val anySink: Consumer<*>                    // Consumer<in Nothing>

// 5. GENERIC CONSTRAINTS
fun <T : Number> processNumber(input: T)    // Single upper bound
fun <T> multiBounds(item: T)                // Multiple upper bounds
    where T : CharSequence, T : Appendable

// 6. REIFICATION (JVM ERASURE WORKAROUND)
inline fun <reified T> isInstance(value: Any): Boolean = value is T
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Jawablah pertanyaan berikut untuk menguji ketajaman pemahaman sistem tipe Kotlin Anda:

### Tingkat Dasar (Basic)
1. **Mengapa kode berikut gagal dikompilasi?**
   ```kotlin
   fun printList(list: MutableList<Any>) { ... }
   val strings: MutableList<String> = mutableListOf("A", "B")
   printList(strings)
   ```
2. **Kapan Anda wajib menggunakan `in` keyword pada deklarasi type parameter?**
3. **Apakah `Nothing?` dan `Nothing` adalah tipe yang sama? Jelaskan perbedaannya dalam lattice sistem tipe Kotlin.**
4. **Apa representasi dari `Array<out Any>` saat dikonversi ke JVM Bytecode?**
5. **Dapatkah parameter bertipe `reified` dideklarasikan pada fungsi standar non-inlined? Mengapa?**

### Tingkat Menengah (Intermediate)
6. **Diberikan interface `Comparator<in T>`. Jika `Shape` adalah supertype dari `Circle`, apakah `Comparator<Shape>` dapat digunakan di fungsi yang membutuhkan `Comparator<Circle>`? Jelaskan mekanisme teoritisnya.**
7. **Perhatikan deklarasi berikut:**
   ```kotlin
   interface Transformer<T> {
       fun transform(input: T): T
   }
   ```
   **Dapatkah parameter generic `T` pada interface tersebut diubah menjadi `out T` atau `in T`? Berikan argumentasi berdasarkan posisi tipe.**
8. **Jelaskan apa fungsi dan bahaya dari anotasi `@UnsafeVariance`. Berikan skenario konkrit di mana Kotlin Standard Library terpaksa menggunakannya.**
9. **Apa perbedaan fungsional antara `List<*>` dan `List<Any>`?**
10. **Bagaimana cara kerja idiomatik *Curiously Recurring Template Pattern (CRTP)* di Kotlin untuk memaksakan fungsi builder fluent API mengembalikan subtipe konkret dari turunan class-nya?**

---

### Kunci Jawaban & Evaluasi Mandiri

1. `MutableList<T>` bersifat invarian. Jika diizinkan, `printList` dapat memanggil `list.add(123)` (memasukkan integer ke dalam objek mutable yang referensi aslinya adalah list of strings), merusak runtime type safety.
2. Saat type parameter tersebut hanya dikonsumsi sebagai parameter fungsi (input argument) dan tidak pernah dikembalikan sebagai return type atau diekspos sebagai public property getter.
3. Berbeda. `Nothing` adalah bottom type mutlak untuk seluruh non-nullable types, tidak memiliki instance. `Nothing?` adalah bottom type untuk nullable types dan hanya memiliki satu nilai yang mungkin: `null`.
4. `java.lang.Object[]` dengan metadata wildcard `? extends Object` di Java calling convention.
5. Tidak bisa. Mekanisme `reified` bergantung secara fundamental pada compiler inlining; bytecode fungsi harus disalin langsung ke call-site di mana tipe konkret dapat disubstitusikan secara literal.
6. Ya, bisa. Karena `Comparator<in T>` bersifat contravariant. Hubungan subtyping-nya terbalik: jika $Circle \le Shape$, maka $Comparator<Shape> \le Comparator<Circle>$.
7. Tidak bisa keduanya. `T` digunakan pada *in-position* (sebagai `input: T`) dan sekaligus pada *out-position* (sebagai return type `: T`). Maka `Transformer<T>` harus strictly invariant.
8. `@UnsafeVariance` menonaktifkan pengecekan posisi variance oleh compiler. Bahayanya: dapat memicu `ClassCastException` jika state internal dimutasi dengan tipe yang tidak kompatibel. Stdlib menggunakannya pada `Collection<out E>.contains(@UnsafeVariance element: E)` demi usability pencarian elemen.
9. `List<Any>` hanya dapat memuat elemen yang strictly non-null (`Any`), sedangkan `List<*>` memproyeksikan `List<out Any?>`, yang berarti elemen dapat berupa objek apa pun termasuk `null`.
10. Dengan mendeklarasikan batasan generic bertingkat: `abstract class Builder<T : Builder<T>> { abstract fun self(): T }`. Subclass mengimplementasikannya dengan `class ConcreteBuilder : Builder<ConcreteBuilder>() { override fun self() = this }`.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang: Generic Type-Safe Heterogeneous Container (DI Service Locator)

#### Spesifikasi Proyek:
Anda ditugaskan membangun sebuah *Micro Dependency Injection Container* berperforma tinggi dengan *Zero Reflection Overhead* saat dependency retrieval.

#### Kebutuhan Fungsional:
1.  **Strict Type Registration:**
    Mendukung pendaftaran instans singleton melalui fungsi generic:
    ```kotlin
    val container = ContainerRegistry()
    container.register<DatabaseConnection>(PostgresConnection())
    ```
2.  **Factory Provider Binding:**
    Mendukung pendaftaran factory dengan siklus hidup transient:
    ```kotlin
    container.registerFactory<PaymentService> { 
        PaymentService(container.resolve<DatabaseConnection>()) 
    }
    ```
3.  **Covariant Multi-Retrieval:**
    Mampu mengekstrak semua services yang mengimplementasikan interface tertentu (misal: mencari semua `HealthCheck` services) memanfaatkan *type variance projections*:
    ```kotlin
    val checks: List<HealthCheck> = container.resolveAll<HealthCheck>()
    ```
4.  **Circular Dependency Detection:**
    Implementasikan sistem pelacakan berbasis recursive type graph yang melempar exception `CircularDependencyException` jika instance $A$ membutuhkan $B$, dan $B$ membutuhkan $A$.
5.  **Thread Safety:**
    Semua operasi registrasi dan resolusi harus aman dijalankan secara konkuren (*lock-free* atau menggunakan concurrent primitive data structures).

#### Acceptance Criteria:
*   Tidak ada penggunaan method `java.lang.Class.forName` (gunakan KClass dan reification murni).
*   Zero `as` unhandled casting warning (semua casting harus di-containment secara aman atau divalidasi via safe reflection API).
*   Sertakan unit test komprehensif yang memvalidasi kovariansi tipe pada hierarchical components.