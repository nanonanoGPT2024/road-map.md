# Bab 03: Functional Programming & Lambdas
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah Dekompilasi Bytecode:** Memahami representasi JVM dari lambdas, instansiasi `FunctionN`, synthetic classes, dan mekanisme *variable capture*.
- **Menguasai Inlining Semantics:** Mengimplementasikan kata kunci `inline`, `noinline`, dan `crossinline` secara tepat berdasarkan analisis profiler alokasi heap dan batas biner DEX/Class size.
- **Mendesain Arsitektur Functional Core, Imperative Shell (FCIS):** Membangun sistem pemrosesan transaksi deterministik bebas *side-effects* dengan *Railway-Oriented Programming* (ROP).
- **Mencegah Degenerasi Performa Runtime:** Mengidentifikasi dan mengeliminasi *heap pollution*, *boxing/unboxing overhead*, serta *hidden allocation* akibat capture variabel kontekstual pada loop berfrekuensi tinggi.
- **Membangun Abstraksi FP Tingkat Lanjut:** Mengimplementasikan teknik *Currying*, *Partial Application*, dan *Monadic Composition* yang aman tanpa mengorbankan performa eksekusi JVM.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda harus memiliki pemahaman mendalam tentang:
- **Kotlin Fundamentals:** OOP, Type System, Null Safety, dan Higher-Order Functions (HOF) tingkat dasar.
- **Java Virtual Machine (JVM) Internals:** Memory Model (Stack vs. Heap, Garbage Collection lifecycle), Class Loading, dan Eksekusi Bytecode dasar.
- **Tooling:** Familiaritas dengan decompiler bytecode (`javap -c -v` atau IntelliJ Bytecode Decompiler) dan profiler memory (JProfiler, VisualVM, atau Async-Profiler).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanisme Representasi Lambda pada JVM
Di balik layar JVM, lambda Kotlin bukan fungsi biasa. Kompiler `kotlinc` mengubah lambda menjadi objek yang mengimplementasikan salah satu antarmuka fungsional bawaan Kotlin: `kotlin.jvm.functions.Function0` hingga `Function22` (merepresentasikan arity dari 0 hingga 22 argumen).

```
+-------------------------------------------------------------+
|                        Lambda Expression                    |
|                        val sum = { a: Int, b: Int -> a + b }|
+-------------------------------------------------------------+
                               |
                               v (kotlinc compiler)
+-------------------------------------------------------------+
| Generated Synthetic Class: PaymentEngineKt$sum$1            |
| implements kotlin.jvm.functions.Function2<Integer, ...>     |
+-------------------------------------------------------------+
| + invoke(p1: Object, p2: Object): Object                    |
|   + unbox Integer -> int                                    |
|   + add primitives                                          |
|   + box int -> Integer                                      |
+-------------------------------------------------------------+
```

Jika lambda **tidak meng-capture variabel** di luar cakupannya (*stateless*), compiler membuat instansiasi **Singleton** (`INSTANCE`), meminimalkan *allocation pressure*. Namun, jika lambda **meng-capture variabel** (*stateful*), instansiasi objek kelas sintetis baru dilakukan **setiap kali** alur kode melewati blok deklarasi tersebut.

#### B. Variable Capture dan Heap Wrappers (`Ref.ObjectRef`, `Ref.IntRef`)
Ketika lambda mengakses atau memutasi variabel lokal yang dideklarasikan di luar tubuhnya, kompiler tidak dapat sekadar menyalin nilai primitif ke stack lambda karena siklus hidup stack variabel lokal bisa berakhir sebelum lambda dieksekusi. Kompiler menyelesaikan ini dengan membungkus variabel tersebut ke dalam heap-allocated wrapper:

```kotlin
fun calculateTotal(): Int {
    var total = 0 // Tipe primitif pada stack
    listOf(1, 2, 3).forEach {
        total += it // Lambda meng-capture dan memutasi 'total'
    }
    return total
}
```

Dekomposisi bytecode ekuivalen dalam representasi Java:
```java
public static final int calculateTotal() {
    final Ref.IntRef total = new Ref.IntRef(); // ALOKASI HEAP!
    total.element = 0;
    Iterable $this$forEach$iv = CollectionsKt.listOf(new Integer[]{1, 2, 3});
    for (Object element$iv : $this$forEach$iv) {
        int it = ((Number)element$iv).intValue();
        total.element += it; // Mutasi via referensi heap
    }
    return total.element;
}
```
*Dampak arsitektur:* Iterasi berulang yang melibatkan lambda capture menciptakan *GC pressure* masif pada subsistem throughput tinggi (misalnya: gateway pembayaran atau streaming broker).

#### C. Inlining Compiler Transformations: `inline`, `noinline`, `crossinline`
Kata kunci `inline` menginstruksikan kompiler untuk menyalin bytecode dari HOF dan lambda langsung ke *call-site*.

1. **`inline`:**
   - Menghilangkan instansiasi objek `FunctionN`.
   - Mengeliminasi alokasi wrapper `Ref.*`.
   - Menghilangkan overhead pemanggilan virtual method `invoke()`.
   - Mendukung **Non-Local Returns** (`return` di dalam lambda akan keluar dari fungsi luar tempat lambda dipanggil).

2. **`noinline`:**
   - Digunakan saat HOF menerima beberapa lambda, namun ada satu atau lebih parameter lambda yang ingin disimpan ke dalam properti, diteruskan ke fungsi non-inline lain, atau dieksekusi secara terpisah. Parameter yang ditandai `noinline` tetap diinstansiasi sebagai objek `FunctionN`.

3. **`crossinline`:**
   - Mengizinkan *inlining* kode lambda, namun **menolak Non-Local Return**.
   - Wajib digunakan jika lambda akan dieksekusi di dalam konteks eksekusi yang berbeda (misalnya: di dalam anonymous class, runnable, coroutine launcher lokal, atau closure thread pool).

---

### 4. Why & What

| Paradigma / Pendekatan | Karakteristik | Keuntungan Enterprise | Kerugian / Trade-off |
| :--- | :--- | :--- | :--- |
| **Object-Oriented Execution (Stateful)** | State terikat kuat pada kelas, mutabilitas internal dominan. | Model mental mudah dipetakan ke domain fisik. | Rentan race condition pada konkurensi tinggi, dependensi tersembunyi, testing butuh mocking kompleks. |
| **Standard Functional (No Inline)** | Menggunakan lambda & pipeline functions (`map`, `filter`). | Kode deklaratif, stateless, thread-safe secara intrinsik. | Overhead alokasi objek heap tinggi, polusi GC pada critical path (latency spike). |
| **Zero-Allocation Inlined Functional** | FP idioms dengan `inline`, `crossinline`, value classes. | Deklaratif, readability tinggi, performa mendekati loop C/Assembly, zero-GC. | Binary footprint (DEX/JAR) membengkak (*code bloat*), stack trace lebih rumit dibaca saat debug. |

Mengapa arsitektur ini penting? Dalam arsitektur microservices modern (seperti event processing via Kafka atau gRPC low-latency endpoints), 80% latensi p99 disebabkan oleh *Stop-The-World* GC pauses. Menulis kode fungsional yang idiomatis tanpa memahami alokasi JVM adalah anti-pattern yang merusak SLA produksi.

---

### 5. How (Workflow detail)

Alur perancangan pipeline fungsional performa tinggi:

```
[ Domain Request Payload ]
            │
            ▼
┌───────────────────────────────────────┐
│ 1. Parse & Ingress Boundary           │
│    (Imperative Shell)                 │
└──────────────────┬────────────────────┘
                   │ Pass Immutable Value Objects
                   ▼
┌───────────────────────────────────────┐
│ 2. Monadic Composition Validation     │
│    (Functional Core: Pure Inline ROP) │
└──────────────────┬────────────────────┘
                   │
         ┌─────────┴─────────┐
         │ Is Valid?         │
         ▼                   ▼
      [ Failure ]         [ Success ]
         │                   │
         │                   ▼
         │       ┌───────────────────────────────────────┐
         │       │ 3. Core Domain Transformation Pipeline│
         │       │    (Curried Pure Calculations)        │
         │       └───────────┬───────────────────────────┘
         │                   │ Emit Side-Effect Commands
         ▼                   ▼
┌───────────────────────────────────────┐
│ 4. Execution & Persistence Boundary   │
│    (Imperative Shell: IO, DB, Network)│
└───────────────────────────────────────┘
```

1. **Ingress Boundary:** Menerima raw payload eksternal, validasi format kasar (Boundary Layer).
2. **Monadic Chain:** Mengeksekusi rentetan validasi bisnis menggunakan tipe `Result<T>` atau `Either<L, R>` tanpa `try-catch` terpusat.
3. **Pure Execution:** Mengalkulasi perubahan state dengan fungsi deterministik yang menerima parameter data murni dan menghasilkan domain event.
4. **Imperative Shell:** Menerapkan hasil ke database, memancarkan event ke Kafka, atau mengembalikan response HTTP.

---

### 6. Analogy & Diagram ASCII

#### Analogi Pabrik Perakitan
- **Regular Lambdas (Non-inlined):** Setiap kali instruksi perakitan dijalankan, Anda mencetak buku manual baru (*instansiasi objek lambda*), menyewa pekerja kontrak baru untuk membaca buku tersebut (*alokasi memory*), mengeksekusi instruksi, lalu membuang buku itu ke tempat sampah (*GC overhead*).
- **Inlined Lambdas:** Instruksi perakitan diukir langsung ke mesin konveyor (*inlining bytecode*). Pekerja tidak perlu membaca buku baru; instruksi menyatu secara fisik dengan mesin. Cepat, tanpa sampah, namun mesin menjadi lebih besar secara fisik (*binary size*).

```
NON-INLINED BYTECODE EXECUTION:
Thread Stack                    Heap Memory
+-----------------------+       +-----------------------------+
| callerFunction()      | ----> | PaymentEngineKt$sum$1       | (Allocated per loop)
|   vtable lookup       |       +-----------------------------+
|   invokeinterface     | ----> | Ref$IntRef (Captured state) |
+-----------------------+       +-----------------------------+

INLINED BYTECODE EXECUTION:
Thread Stack
+------------------------------------+
| callerFunction()                   |
|   ILOAD / IADD (Direct Opcode)     | -> Zero Heap Interaction
|   No intermediate interface call   | -> Flat stack execution
+------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Perbedaan `crossinline` dan Non-Local Returns

```kotlin
package com.enterprise.fp.basics

// Inline standar mengizinkan non-local return
inline fun executeFast(block: () -> Unit) {
    println("Engine Start")
    block()
    println("Engine Stop")
}

// Menggunakan crossinline untuk mencegah non-local return keluar dari caller
inline fun executeAsync(crossinline block: () -> Unit) {
    val runnable = Runnable {
        // Lambda dieksekusi di context Runnable, non-local return dilarang di sini!
        block()
    }
    runnable.run()
}

fun testExecution() {
    executeFast {
        println("Working...")
        return // Menghentikan testExecution() SEPENUHNYA. "Engine Stop" TIDAK DICETAK!
    }

    executeAsync {
        println("Async Working...")
        // return // COMPILE ERROR: 'return' is not allowed here
    }
}
```

#### B. Practical Example: Functional Composition & Currying Engine
Engine utilitas fungsional tingkat lanjut tanpa dependensi eksternal:

```kotlin
package com.enterprise.fp.engine

// Type alias untuk Pipeline Function
typealias Transformation<T> = (T) -> T

// Infix composition: f andThen g <=> g(f(x))
infix fun <A, B, C> ((A) -> B).andThen(crossinline after: (B) -> C): (A) -> C {
    return { x: A -> after(this(x)) }
}

// Infix composition: f compose g <=> f(g(x))
infix fun <A, B, C> ((B) -> C).compose(crossinline before: (A) -> B): (A) -> C {
    return { x: A -> this(before(x)) }
}

// Currying primitives untuk fungsi 3-argumen
fun <P1, P2, P3, R> ((P1, P2, P3) -> R).curried(): (P1) -> (P2) -> (P3) -> R =
    { p1 -> { p2 -> { p3 -> this(p1, p2, p3) } } }

// Uncurrying
fun <P1, P2, P3, R> ((P1) -> (P2) -> (P3) -> R).uncurried(): (P1, P2, P3) -> R =
    { p1, p2, p3 -> this(p1)(p2)(p3) }
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Domain: High-Throughput Financial Transaction Validation & Risk Assessment Engine

Pada skenario perbankan, ribuan transaksi divalidasi per detik. Kita harus menerapkan Railway-Oriented Programming (ROP) berbasis fungsional murni untuk menghindari lemparan eksepsi (`throw Exception`), yang membebani kinerja JVM dengan alokasi *stack trace traversal*.

```kotlin
package com.enterprise.banking.pipeline

import java.math.BigDecimal
import java.time.Instant

// 1. Domain Entities & Value Objects (Immutable)
@JvmInline
value class AccountId(val value: String)
@JvmInline
value class Currency(val code: String)

data class Transaction(
    val id: String,
    val sourceAccount: AccountId,
    val targetAccount: AccountId,
    val amount: BigDecimal,
    val currency: Currency,
    val timestamp: Instant
)

sealed interface DomainError {
    data class InvalidAmount(val reason: String) : DomainError
    data class SanctionedEntity(val accountId: AccountId) : DomainError
    data class InsufficientFunds(val balance: BigDecimal, val requested: BigDecimal) : DomainError
}

// 2. Monadic Functional Result (Zero-Overhead Functional Pipeline)
sealed class FResult<out E, out T> {
    data class Success<out T>(val value: T) : FResult<Nothing, T>()
    data class Failure<out E>(val error: E) : FResult<E, Nothing>()

    inline fun <R> map(transform: (T) -> R): FResult<E, R> = when (this) {
        is Success -> Success(transform(value))
        is Failure -> this
    }

    inline fun <R> flatMap(transform: (T) -> FResult<@UnsafeVariance E, R>): FResult<E, R> = when (this) {
        is Success -> transform(value)
        is Failure -> this
    }

    inline fun onFailure(action: (E) -> Unit): FResult<E, T> {
        if (this is Failure) action(error)
        return this
    }
}

// 3. Functional Core: Pure Pipeline Steps (Tanpa Side Effects)
object TransactionValidationRules {

    val validatePositiveAmount: (Transaction) -> FResult<DomainError, Transaction> = { tx ->
        if (tx.amount > BigDecimal.ZERO) {
            FResult.Success(tx)
        } else {
            FResult.Failure(DomainError.InvalidAmount("Amount must be strictly positive: ${tx.amount}"))
        }
    }

    fun validateSanctionList(blacklist: Set<AccountId>): (Transaction) -> FResult<DomainError, Transaction> = { tx ->
        if (blacklist.contains(tx.sourceAccount) || blacklist.contains(tx.targetAccount)) {
            FResult.Failure(DomainError.SanctionedEntity(if (blacklist.contains(tx.sourceAccount)) tx.sourceAccount else tx.targetAccount))
        } else {
            FResult.Success(tx)
        }
    }

    fun validateSufficientBalance(ledgerBalance: BigDecimal): (Transaction) -> FResult<DomainError, Transaction> = { tx ->
        if (ledgerBalance >= tx.amount) {
            FResult.Success(tx)
        } else {
            FResult.Failure(DomainError.InsufficientFunds(balance = ledgerBalance, requested = tx.amount))
        }
    }
}

// 4. Enterprise Pipeline Orchestrator (Functional Core with Inlined Mechanics)
class TransactionEngine(private val sanctionList: Set<AccountId>) {

    // Higher-order pipeline builder
    inline fun processTransaction(
        transaction: Transaction,
        currentBalanceProvider: (AccountId) -> BigDecimal,
        crossinline onPersistence: (Transaction) -> Unit
    ): FResult<DomainError, Transaction> {

        val currentBalance = currentBalanceProvider(transaction.sourceAccount)

        // Monadic Composition (Chaining logic using inlined flatMaps)
        return TransactionValidationRules.validatePositiveAmount(transaction)
            .flatMap(TransactionValidationRules.validateSanctionList(sanctionList))
            .flatMap(TransactionValidationRules.validateSufficientBalance(currentBalance))
            .map { validatedTx ->
                // Imperative shell operation bridged safely via functional boundary
                onPersistence(validatedTx)
                validatedTx
            }
    }
}
```

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya & Batasan (*Drawback*) |
| :--- | :--- | :--- |
| **Agresif Menggunakan `inline`** | Menghilangkan alokasi heap untuk kelas instansiasi lambda dan wrapper primitive. Performa eksekusi setara kode imperatif flat. | Ukuran file bytecode (`.class`/`.dex`) melonjak (*code bloat*). Kompilasi lambat. Pemanggilan internal privat dibatasi (harus `internal` dengan annotation `@PublishedApi`). |
| **Railway-Oriented (Result ADT)** | Alur eksekusi deterministik, penanganan error eksplisit via type-system, tidak ada latency spike akibat exception stack trace generation. | Overhead pada developer learning-curve. Kode terkadang lebih verbose dibandingkan standard `try-catch` jika domain flow tidak linier. |
| **Deep Currying & Partial Application** | Modularity komponen maksimal. Memungkinkan *Dependency Injection* tanpa framework via *partial application closures*. | Menghasilkan rantai pemanggilan fungsi bersarang (*deep call stack*), rentan terhadap overhead dereferensial pointer jika tidak di-inline dengan baik. |

---

### 10. Common Mistakes & Troubleshooting

#### A. Capturing Variables in Tight Loops (Anti-Pattern)
```kotlin
// ERROR CRITICAL: Alokasi Ref.IntRef masif di dalam Hot Path
fun processEvents(events: List<Event>): Int {
    var count = 0
    // forEach inline, tetapi lambda di bawah meng-capture variabel lokal jika dikirim ke HOF non-inline!
    events.forEach { event ->
        if (event.isValid) count++ // Aman JIKA forEach inline.
    }
    return count
}

// Namun jika diteruskan ke HOF non-inline:
fun submitToWorkerPool(events: List<Event>, executor: ( () -> Unit ) -> Unit) {
    var state = 0
    for (event in events) {
        // MENCIPTAKAN INSTANSI BARU SETIAP ITERASI KARENA VARIABLE CAPTURE!
        executor {
            state += event.weight 
        }
    }
}
```
*Solusi:* Hindari pemutasian variabel lokal di dalam closure yang dilempar ke thread eksternal. Gunakan reduksi fungsional murni (`fold`, `reduce`) atau *Atomic/Thread-safe wrappers* yang dialokasikan di luar loop secara eksplisit.

#### B. Kesalahan Konfigurasi Inlining `@PublishedApi`
Jika fungsi bertanda `inline` mengakses field atau fungsi private, kode gagal dikompilasi:
```kotlin
class PaymentService {
    private val secretKey: String = "sk_live_123" // Private property

    // COMPILE ERROR: Public inline function cannot access non-public member
    inline fun executePayment(action: (String) -> Unit) {
        action(secretKey)
    }
}
```
*Solusi:*
```kotlin
class PaymentService {
    @PublishedApi
    internal val secretKey: String = "sk_live_123" // Aman untuk inline

    inline fun executePayment(action: (String) -> Unit) {
        action(secretKey)
    }
}
```

#### C. Unintended Non-Local Returns Menghancurkan Alur Aplikasi
```kotlin
fun evaluateUsers(users: List<User>) {
    users.forEach { user ->
        if (!user.isActive) {
            return // BUG: Ini keluar dari evaluateUsers(), BUKAN seperti 'continue' di loop!
        }
        sendNotification(user)
    }
}
```
*Solusi:* Gunakan *labeled return* (`return@forEach`) untuk mensimulasikan semantik `continue`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan `inline` Secara Proporsional:** Berikan tanda `inline` hanya pada fungsi yang menerima argumen fungsi (*higher-order functions*). Jangan meng-inline fungsi reguler bertubuh besar (risiko *code bloat*).
- [ ] **Pertahankan Purity pada Functional Core:** Pastikan fungsi transformasi data bersifat referensial transparan (input identik selalu menghasilkan output identik tanpa mengubah state global).
- [ ] **Batasi Arity Pemanggilan:** Jaga lambda tetap di bawah 22 parameter untuk menghindari runtuhnya optimasi antarmuka fungsional standar JVM.
- [ ] **Amankan Concurrency Context:** Gunakan `crossinline` pada argumen fungsi yang dilempar ke thread pools, coroutines worker, atau scheduled tasks untuk mencegah return non-lokal ilegal.
- [ ] **Pilih Functional Over Exceptions untuk Business Logic:** Gunakan ADT (seperti `sealed interface Result`) alih-alih melempar exception untuk domain failures. Exception hanya untuk kegagalan infrastruktur/sistemik fatal (*Out of Memory, DB Connection Failure*).

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/m02/
├── build.gradle.kts
└── src/
    └── main/
        └── kotlin/
            └── com/enterprise/fp/
                ├── AllocationBenchmark.kt
                └── BytecodeInspection.kt
```

#### Langkah 1: Siapkan `build.gradle.kts`
```kotlin
plugins {
    kotlin("jvm") version "1.9.22"
    application
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jetbrains.kotlin:kotlin-stdlib")
}
```

#### Langkah 2: Buat File `BytecodeInspection.kt`
```kotlin
package com.enterprise.fp

class BytecodeInspection {
    // Skenario A: Non-inlined & Non-capturing
    fun regularLambda(): () -> Int {
        return { 42 }
    }

    // Skenario B: Capturing Lambda
    fun capturingLambda(factor: Int): () -> Int {
        return { factor * 2 }
    }

    // Skenario C: Inlined High-Order Function
    inline fun computeFast(a: Int, operation: (Int) -> Int): Int {
        return operation(a)
    }
}
```

#### Langkah 3: Kompilasi dan Bongkar Bytecode
Jalankan perintah berikut di terminal:
```bash
./gradlew compileKotlin
cd build/classes/kotlin/main/com/enterprise/fp/

# Analisis struktur synthetic class yang dihasilkan:
ls -la

# Disassemble class capturing:
javap -c -v BytecodeInspection.class
```
*Hasil observasi:* Perhatikan kemunculan file sintetis `BytecodeInspection$regularLambda$1.class` dan `BytecodeInspection$capturingLambda$1.class`, yang memverifikasi bahwa stateful lambda menghasilkan class dan objek instansiasi baru.

---

### 13. Exercises

#### Level Easy
Buat extension function `inline fun <T> T.applyIf(condition: Boolean, block: T.() -> T): T` yang menerapkan transformasi pada objek penerima hanya jika nilai boolean bernilai `true`. Pastikan tidak ada alokasi memori tambahan.
- **Kriteria Evaluasi:** Tidak ada boxing variabel boolean; fungsi harus bersifat inline; compilable tanpa peringatan compiler.

#### Level Medium
Implementasikan fungsi higher-order `memoize()` generic untuk fungsi unary: `fun <A, R> ((A) -> R).memoize(): (A) -> R`. Modifikasi fungsi ini agar thread-safe menggunakan konkurensi berbasis `ConcurrentHashMap` dan cegah terjadinya komputasi ganda jika dipanggil bersamaan (*thundering herd problem* via `computeIfAbsent`).
- **Kriteria Evaluasi:** Benar-benar thread-safe; mempertahankan referensial transparan; penanganan memory leaks dari map yang tumbuh tanpa batas (pertimbangkan mitigasi batas ukuran cache sederhana).

#### Level Hard
Rancang komponen *Circuit Breaker Functional Pipeline* berbasis ROP murni tanpa mutasi state eksternal (gunakan immutabilitas total dengan memodelkan transisi state: `Closed`, `Open`, `HalfOpen` via ADT). Pipeline harus menerima request fungsional: `(Req) -> FResult<CircuitBreakerError, Res>`, dan menghasilkan state baru dari Circuit Breaker bersamaan dengan hasil pemrosesan.
- **Kriteria Evaluasi:** Tidak menggunakan `AtomicReference` atau variabel mutable (`var`); seluruh status transisi dipetakan fungsional; alokasi heap minimal.

---

### 14. Challenge

**Skenario Kasus:** Anda diminta oleh sebuah bursa perdagangan kripto berkecepatan tinggi (*Ultra Low-Latency Order Matching Engine*) untuk mendesain modul pemfilteran dan validasi order buku besar (*Order Book Ledger Validator*).
Modul ini menerima antrian order sebesar **100.000 transaksi/detik**.

**Spesifikasi Teknis:**
1. Validasi mencakup: pemeriksaan batas margin kredit, format order ID (UUID v4 format), limit ukuran bid/ask, serta timestamp drift tidak melebihi 200 ms dari clock server.
2. Anda **dilarang keras** menggunakan konstruksi `try-catch` di seluruh validation critical path.
3. Anda **dilarang keras** menghasilkan sampah GC objek pada setiap evaluasi order. Artinya:
   - Dilarang mengalokasikan objek closure baru pada saat iterasi validation pipeline dijalankan.
   - Pengecekan harus tersusun secara fungsional melalui teknik *Inline Combinators*.
   - Objek `Order` harus direpresentasikan seefisien mungkin (gunakan `value class` atau flattened data layout).
4. Hasil pemrosesan harus berupa tipe data terpadu (Union/Result ADT) yang menyediakan informasi error komprehensif tanpa pemanggilan stack-trace capture.

**Tugas Anda:** Desain seluruh skema data, HOF combinator, dan arsitektur fungsi validasi ini secara fungsional murni. Sertakan analisis teoritis terkait alokasi memori heap vs stack dari solusi yang Anda tawarkan.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa antarmuka JVM yang dihasilkan oleh compiler Kotlin ketika kita mendeklarasikan lambda dengan signature `(String, Double) -> Boolean`?
2. Kapan sebuah lambda di-cache sebagai instansiasi singleton oleh runtime Kotlin?
3. Mengapa kata kunci `inline` tidak direkomendasikan untuk disematkan pada semua fungsi dalam proyek Kotlin Anda?
4. Mengapa kita tidak dapat melakukan *non-local return* di dalam lambda yang dikirimkan ke parameter bertanda `crossinline`?
5. Objek apa yang diinstansiasikan oleh compiler Kotlin ketika sebuah lambda memutasi variabel lokal bertipe primitif `var counter: Long`?

#### Pertanyaan Intermediate
6. Jelaskan risiko pemanggilan `@PublishedApi` terhadap stabilitas *binary compatibility* dan enkapsulasi kode enterprise!
7. Dalam Functional Programming, apa perbedaan mendasar antara *Currying* dan *Partial Application*?
8. Bagaimana pengaruh inlining HOF terhadap ukuran stack trace saat terjadi kegagalan/exception di level produksi?
9. Apa perbedaan esensial pada level bytecode antara penggunaan *Functional Interface (SAM)* Java dengan *Function Type Lambda* Kotlin?
10. Mengapa Railway-Oriented Programming (ROP) menggunakan tipe data seperti `Result` atau `Either` secara inheren lebih cepat daripada error handling berbasis `throw Exception` pada alur validasi transaksi bervolume tinggi?

#### Skenario Kasus Produksi
11. **Skenario 1:** Sebuah aplikasi backend mengalami degradasi performa p99 latency yang sangat buruk setiap beberapa menit. Profiling memory menggunakan VisualVM menunjukkan bahwa jutaan objek `kotlin.jvm.internal.Ref$ObjectRef` membanjiri Eden Space. Berdasarkan pengetahuan Anda tentang lambda internals, apa yang sedang terjadi di kode sumber dan bagaimana cara Anda memperbaikinya?
12. **Skenario 2:** Anda memiliki pipeline eksekusi:
    ```kotlin
    inline fun executeTask(crossinline block: () -> Unit) {
        val pool = Executors.newFixedThreadPool(4)
        pool.submit { block() }
    }
    ```
    Apakah kode di atas valid? Jika parameter `crossinline` dihilangkan, apa pesan error kompilasi yang muncul dan mengapa arsitektur JVM menolak hal tersebut?
13. **Skenario 3:** Tim Anda menulis kode fungsional pipeline menggunakan chain methods standar library: `list.filter { ... }.map { ... }.take(10)`. Di lingkungan produksi dengan jutaan items, memori heap meluap (*OutOfMemoryError*). Mengapa ini terjadi dan jelaskan transformasi fungsional apa yang harus diterapkan tanpa meninggalkan paradigma FP?

---

#### Kunci Jawaban & Evaluasi

1. **Antarmuka:** `kotlin.jvm.functions.Function2<String, Double, Boolean>`.
2. **Kondisi Singleton:** Ketika lambda bersifat *stateless*, artinya tidak meng-capture variabel atau state dari scope luarnya (*non-capturing closure*).
3. **Alasan Batasan Inline:** Inlining menyalin seluruh instruksi bytecode ke setiap call site. Jika fungsi berukuran besar di-inline di banyak tempat, file biner (`.dex`/`.jar`) akan mengalami *code bloat*, menghancurkan efisiensi Instruction Cache (I-Cache) CPU, dan memperlambat proses kompilasi.
4. **Mekanisme Crossinline:** Karena lambda tersebut dieksekusi di thread, context, atau anonymous class lain yang lifecycle-nya berbeda dari fungsi pemanggil (*caller*). JVM tidak dapat me-unwind call stack caller dari thread yang berbeda.
5. **Objek Wrapper:** `kotlin.jvm.internal.Ref.LongRef` yang dialokasikan di memori heap.
6. **Dampak PublishedApi:** Properti internal dipaksa memiliki visibilitas publik pada level bytecode. Siapapun dari modul binary luar dapat mengakses properti tersebut, merusak abstraksi enkapsulasi domain internal.
7. **Currying vs Partial:** Currying mengubah fungsi dengan arity $N$ menjadi rangkaian $N$ fungsi masing-masing ber-arity 1: $f(a, b) \rightarrow f(a)(b)$. Partial application adalah mengikat sebagian argumen pada suatu fungsi untuk menghasilkan fungsi baru dengan arity yang lebih kecil: $f(a, b, c) \xrightarrow{\text{bind } a} f(b, c)$.
8. **Dampak Stack Trace:** Pemanggilan frame method dari HOF yang di-inline dihilangkan dari JVM stack trace. Ini membuat pembacaan posisi baris error menjadi seolah-olah terjadi langsung di dalam fungsi pemanggil (*caller*).
9. **Bytecode SAM vs Lambda:** Kotlin Functional Types dikompilasi menjadi instansiasi tipe internal Kotlin `FunctionN`. Java SAM Functional Interfaces dapat memanfaatkan instruksi JVM tingkat rendah `invokedynamic` (jika didukung target JVM compiler) yang lebih efisien dalam instansiasi dan linkage runtime.
10. **ROP vs Exception Throughput:** Membuat `Exception` membutuhkan operasi *native* JVM `fillInStackTrace()`, yang memindai seluruh thread stack execution saat eksepsi dibuat. ROP hanya mengembalikan representasi objek data diskrit biasa tanpa memindai stack, sehingga menghemat jutaan siklus CPU.
11. **Analisis Skenario 1:** Terjadi *variable capture* lokal mutable (`var`) di dalam blok loop yang memanggil lambda. Perbaikan: Ubah pendekatan imperatif tersebut menjadi reduksi fungsional murni (`fold`, `reduce`), atau lokalisasikan mutasi state ke dalam kelas objek pemegang state tunggal di luar loop sehingga tidak ada alokasi wrapper `Ref.*` instan pada setiap iterasi.
12. **Analisis Skenario 2:** Kode tersebut valid karena menggunakan `crossinline`. Jika `crossinline` dihapus, compiler memberikan error: *"Can't inline 'block' here: it may contain non-local returns, which are not supported in this context"*. JVM tidak mendukung eksekusi instruksi return caller stack frame dari context `Executor` thread pool yang berbeda.
13. **Analisis Skenario 3:** Standar `Iterable` operators (`filter`, `map`) bersifat *eager* (menghasilkan intermediate `ArrayList` baru di setiap tahapan pipeline chain). Pada jutaan item, intermediate collections ini menghabiskan memori heap. Perbaikan: Ubah koleksi menjadi pemrosesan *lazy* menggunakan `asSequence()` sebelum operasi pipeline, diakhiri dengan terminal operator (misalnya: `toList()`). Hal ini memproses data secara per-elemen (*streamlined element-by-element evaluation*) tanpa alokasi intermediate collection.

---

### 16. Summary

- Pemrograman Fungsional idiomatik di Kotlin pada sistem enterprise memerlukan kesadaran penuh terhadap abstraksi JVM di bawahnya.
- Lambda yang meng-capture variabel lokal memicu alokasi wrapper `Ref.*` di heap dan objek sintetis `FunctionN`, yang meningkatkan latensi GC pada *critical data path*.
- Modifikator `inline` mengeliminasi overhead alokasi ini secara drastis, tetapi harus diimbangi dengan pertimbangan ukuran binary. Gunakan `crossinline` jika lambda didelegasikan ke konteks eksekusi asinkron/eksternal, dan `noinline` untuk parameter fungsional yang disimpan sebagai state.
- Pola *Functional Core, Imperative Shell* yang dikombinasikan dengan *Railway-Oriented Programming* menghasilkan sistem deterministik, mudah diuji, bebas exception stack-walk penalty, dan memiliki daya tahan tinggi untuk infrastruktur komputasi beban tinggi.