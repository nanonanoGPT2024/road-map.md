# Kurikulum Komprehensif: Pemrograman Modern Kotlin (Enterprise & Multiplatform)

Selamat datang di repositori kurikulum resmi **Kotlin Developer Roadmap**. Silabus ini dirancang oleh *Senior Technical Curriculum Architect* untuk mentransformasi rekayasawan perangkat lunak dari tingkat pemula/menengah menjadi arsitek sistem yang menguasai ekosistem Kotlin secara mendalam—mulai dari dasar perancangan bahasa, sistem pengetikan ketat, konkurensi skala tinggi berbasis Coroutines dan Flow, hingga implementasi backend modern dan arsitektur Kotlin Multiplatform (KMP).

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Kotlin bukan sekadar "Java tanpa *boilerplate*"; Kotlin adalah bahasa berorientasi objek dan fungsional yang pragmatis, mengedepankan keamanan tipe (*type safety*), ekspresif, dan memiliki interoperabilitas tanpa gesekan (*seamless interoperability*) dengan runtime Java serta ekosistem *native*. 

Dalam kurikulum ini, Anda akan diarahkan untuk:
- **Think in Kotlin**: Menghentikan kebiasaan menulis sintaks Java/Python dalam sintaks Kotlin. Menggunakan konsep *immutability*, *smart casts*, *expressions over statements*, dan *functional pipelines*.
- **Master Concurrency without Threads**: Memahami model asinkron *non-blocking* dengan *Structured Concurrency*, membedah cara kerja Coroutine engine di level runtime tanpa overhead thread tingkat sistem operasi.
- **Production-Ready Engineering**: Menulis kode yang teruji, aman terhadap *null pointer exceptions*, memiliki arsitektur modular, hemat memori, dan siap dideploy di lingkungan kontainer mikroservis berskala enterprise.

### Prasyarat (Prerequisites)
- Pemahaman dasar algoritma, struktur data, dan konsep pemrograman berorientasi objek (OOP).
- Pengalaman dasar menggunakan salah satu bahasa bertipe statis atau dinamis (Java, TypeScript, C#, Go, atau Python).
- JDK 17+ atau JDK 21 (LTS) terpasang di lingkungan kerja lokal Anda bersama IDE IntelliJ IDEA.

---

## 2. Learning Roadmap

```plaintext
                    [KOTLIN ENTERPRISE CURRICULUM]
                                  │
    ┌─────────────────────────────┴─────────────────────────────┐
    ▼                                                           ▼
[FOUNDATION & IDIOMS]                                 [ADVANCED CONCURRENCY]
├─ Bab 01: Fondasi Bahasa & Sistem Tipe                ├─ Bab 05: Coroutines & Structured Concurrency
├─ Bab 02: Paradigma OOP Idiomatis                     └─ Bab 06: Reactive Streams & Asynchronous Flow
├─ Bab 03: Functional Programming & Lambdas
└─ Bab 04: Advanced Type System & Generics
                                  │
    ┌─────────────────────────────┴─────────────────────────────┐
    ▼                                                           ▼
[JVM RUNTIME & ARCHITECTURE]                          [ENTERPRISE ECOSYSTEM]
├─ Bab 07: Koleksi, Ekstensi & Serialization           ├─ Bab 09: Modern Backend & Clean Architecture
└─ Bab 08: Interoperabilitas Java & JVM Internals      └─ Bab 10: Kotlin Multiplatform & K2 Compiler
                                  │
                                  ▼
                [ENTERPRISE FINAL CAPSTONE PROJECT]
```

---

## 3. Navigasi Detail Modul (Bab 01 s/d Bab 10)

### Bab 01: Fondasi Bahasa & Sistem Tipe Modern
Memahami sintaks fundamental, eliminasi `NullPointerException` di tingkat kompilasi, serta mekanisme evaluasi ekspresi Kotlin.
- [`01-fondasi-bahasa/01-sintaks-ekspresi-dan-variabel.md`](./01-fondasi-bahasa/01-sintaks-ekspresi-dan-variabel.md): Analisis perbandingan `val` vs `var`, *type inference*, kontrol alur berbasis ekspresi (`when`, `if-else`), dan *basic types*.
- [`01-fondasi-bahasa/02-null-safety-dan-type-system.md`](./01-fondasi-bahasa/02-null-safety-dan-type-system.md): Pembedahan mendalam *nullable types* (`T?`), operator elvis (`?:`), *safe call* (`?.`), *force unwrap* (`!!`), platform types, serta *smart casting*.
- [`01-fondasi-bahasa/03-fungsi-dan-parameter.md`](./01-fondasi-bahasa/03-fungsi-dan-parameter.md): *Named arguments*, *default parameters*, *vararg*, *single-expression functions*, dan *tail-recursive optimization* (`tailrec`).

### Bab 02: Paradigma OOP Idiomatis di Kotlin
Membangun hierarki objek yang aman, deklaratif, dan memanfaatkan fitur kelas tingkat lanjut tanpa kelemahan arsitektur warisan.
- [`02-oop-idiomatis/01-konstruktor-dan-properti.md`](./02-oop-idiomatis/01-konstruktor-dan-properti.md): Konstruktor primer/sekunder, *custom accessors* (getter/setter), *backing fields* (`field`), dan evaluasi *late-initialized properties* (`lateinit` vs `lazy`).
- [`02-oop-idiomatis/02-data-dan-sealed-hierarki.md`](./02-oop-idiomatis/02-data-dan-sealed-hierarki.md): Penerapan `data class` (destructuring, `copy()`), `sealed class` dan `sealed interface` untuk pemodelan *Algebraic Data Types* (ADT).
- [`02-oop-idiomatis/03-pewarisan-dan-delegasi.md`](./02-oop-idiomatis/03-pewarisan-dan-delegasi.md): Desain berbasis komposisi lewat *Class Delegation* (`by`), implementasi *Property Delegation* bawaan (`observable`, `vetoable`), serta aturan modifier `open`, `abstract`, dan `override`.

### Bab 03: Functional Programming & Scope Functions
Menguasai kapabilitas fungsional kelas satu (*first-class citizen*), efisiensi alokasi memori lambda, dan manipulasi konteks objek.
- [`03-functional-programming/01-lambdas-dan-high-order-functions.md`](./03-functional-programming/01-lambdas-dan-high-order-functions.md): *Higher-order functions*, sintaks lambda, *function references* (`::`), *type aliases*, dan pemanggilan *trailing lambdas*.
- [`03-functional-programming/02-inline-functions-dan-reified.md`](./03-functional-programming/02-inline-functions-dan-reified.md): Analisis bytecode modifier `inline`, pencegahan alokasi objek dengan `noinline` & `crossinline`, serta penghapusan batasan runtime dengan `reified`.
- [`03-functional-programming/03-scope-functions-idiomatis.md`](./03-functional-programming/03-scope-functions-idiomatis.md): Matriks komparasi arsitektural penggunaan `let`, `run`, `with`, `apply`, dan `also` berdasarkan *return value* dan *context object reference* (`this` vs `it`).

### Bab 04: Advanced Type System & Generics
Merancang pustaka dan komponen reusable dengan pengetikan tingkat lanjut yang aman dari eror waktu kompilasi.
- [`04-advanced-generics/01-generics-dan-subtyping.md`](./04-advanced-generics/01-generics-dan-subtyping.md): Parameter tipe data, *generic constraints* (`where`), tipe invarian, dan mekanisme *type erasure* pada level runtime.
- [`04-advanced-generics/02-variance-in-out.md`](./04-advanced-generics/02-variance-in-out.md): Konsep kovariansi (`out`) vs kontravariansi (`in`), perbandingan konsep *declaration-site variance* Kotlin vs *use-site wildcard* Java (`*` projection).
- [`04-advanced-generics/03-operator-overloading-dan-value-classes.md`](./04-advanced-generics/03-operator-overloading-dan-value-classes.md): Konvensi operator kustom, domain modeling zero-cost abstraction menggunakan `@JvmInline value class`.

### Bab 05: Asynchronous Programming: Coroutines Core
Mengimplementasikan komputasi paralel dan I/O non-blocking berbasis *Structured Concurrency*.
- [`05-coroutines-core/01-fondasi-coroutine-suspension.md`](./05-coroutines-core/01-fondasi-coroutine-suspension.md): State machine internal fungsi `suspend`, Coroutine vs Thread, mekanisme *continuation passing style* (CPS).
- [`05-coroutines-core/02-structured-concurrency-lifecycle.md`](./05-coroutines-core/02-structured-concurrency-lifecycle.md): Orkes pemanggilan `CoroutineScope`, `launch`, `async`, siklus hidup `Job`, hierarki `SupervisorJob`, serta mekanisme propagasi pembatalan (*cancellation*).
- [`05-coroutines-core/03-dispatchers-dan-exception-handling.md`](./05-coroutines-core/03-dispatchers-dan-exception-handling.md): Manajemen alokasi thread (`Dispatchers.Default`, `IO`, `Main`, `Unconfined`), implementasi `CoroutineExceptionHandler`, dan penanganan error pada thread konkurensi tinggi.

### Bab 06: Reactive Streams & Asynchronous Flow
Arsitektur aliran data reaktif asinkron menggunakan Kotlin Flow dengan konsumsi memori yang dapat diprediksi.
- [`06-reactive-flow/01-cold-flow-dan-pipeline-operators.md`](./06-reactive-flow/01-cold-flow-dan-pipeline-operators.md): Prinsip dasar *cold streams*, deklarasi pemancar data (`flow { ... }`), operator transformasi (`map`, `filter`), kombinasi (`zip`, `combine`), dan *flattening* (`flatMapConcat`, `flatMapMerge`, `flatMapLatest`).
- [`06-reactive-flow/02-hot-streams-stateflow-sharedflow.md`](./06-reactive-flow/02-hot-streams-stateflow-sharedflow.md): Manajemen status aplikasi berbasis event-driven menggunakan `SharedFlow` vs `StateFlow`, strategi *replay*, *buffer overflow*, dan isolasi mutabilitas.
- [`06-reactive-flow/03-backpressure-dan-flow-testing.md`](./06-reactive-flow/03-backpressure-dan-flow-testing.md): Penanganan *backpressure* (`buffer`, `conflate`), manajemen konteks (`flowOn`), serta pengujian unit *flow* menggunakan pustaka `Turbine`.

### Bab 07: Koleksi, Ekstensi & Serialization
Manipulasi data tingkat tinggi dengan performa optimal serta serialisasi data terstruktur.
- [`07-koleksi-dan-data/01-collections-vs-sequences.md`](./07-koleksi-dan-data/01-collections-vs-sequences.md): Eager evaluation (`List`, `Set`, `Map`) vs lazy evaluation (`Sequence`) untuk dataset berskala besar, profiling alokasi objek sementara (*intermediate buffers*).
- [`07-koleksi-dan-data/02-extension-functions-dsl.md`](./07-koleksi-dan-data/02-extension-functions-dsl.md): Pemanfaatan *Extension Functions/Properties*, *Type-safe builders*, anotasi `@DslMarker`, dan pembuatan Internal Domain Specific Language (DSL).
- [`07-koleksi-dan-data/03-modern-serialization.md`](./07-koleksi-dan-data/03-modern-serialization.md): Integrasi `kotlinx.serialization` untuk payload format JSON/Protobuf, *polymorphic serialization*, dan serializer kustom untuk tipe kompleks.

### Bab 08: Interoperabilitas Java & JVM Internals
Membongkar eksekusi Kotlin di atas Java Virtual Machine (JVM) dan integrasi dua arah dengan kode Java eksisting.
- [`08-jvm-internals/01-interoperabilitas-dua-arah.md`](./08-jvm-internals/01-interoperabilitas-dua-arah.md): Anotasi interoperabilitas `@JvmStatic`, `@JvmOverloads`, `@JvmField`, pemetaan penanganan eksepsi (`@Throws`), serta penanganan *SAM conversions*.
- [`08-jvm-internals/02-dekompilasi-bytecode-dan-optimasi.md`](./08-jvm-internals/02-dekompilasi-bytecode-dan-optimasi.md): Analisis JVM bytecode menggunakan IntelliJ Bytecode Viewer, dekompilasi ke Java source, identifikasi overhead sintaks tersembunyi (*synthetic methods*, *bridge methods*).
- [`08-jvm-internals/03-reflection-dan-ksp.md`](./08-jvm-internals/03-reflection-dan-ksp.md): Operasi runtime melalui `kotlin-reflect` vs kompilasi modern berbasis *Kotlin Symbol Processing* (KSP) untuk pembuatan kode otomatis.

### Bab 09: Modern Backend & Clean Architecture
Membangun servis mikro (*microservices*) berkinerja tinggi, modular, dan terisolasi secara domain.
- [`09-backend-architecture/01-ktor-framework-fondasi.md`](./09-backend-architecture/01-ktor-framework-fondasi.md): Pembuatan microservice asinkron menggunakan Ktor Engine (Netty/CIO), routing modular, konfigurasi *content negotiation*, validasi payload, dan *authentication/authorization plugins*.
- [`09-backend-architecture/02-akses-data-dan-database.md`](./09-backend-architecture/02-akses-data-dan-database.md): Integrasi basis data relasional menggunakan *JetBrains Exposed* (SQL DSL vs DAO) dan *Spring Data R2DBC* berorientasi Coroutines, serta isolasi koneksi basis data.
- [`09-backend-architecture/03-clean-architecture-dan-di.md`](./09-backend-architecture/03-clean-architecture-dan-di.md): Implementasi pemisahan dependensi (Domain, Data, Presentation layers), Dependency Injection fungsional & pragmatis menggunakan Koin framework.

### Bab 10: Kotlin Multiplatform & K2 Compiler
Mempersiapkan kode inti untuk multi-target dan memahami fondasi arsitektur kompilator masa depan.
- [`10-kmp-dan-compiler/01-arsitektur-kmp-dasar.md`](./10-kmp-dan-compiler/01-arsitektur-kmp-dasar.md): Struktur proyek multiplatform (`commonMain`, `jvmMain`, `iosMain`, `jsMain`), mekanisme isolasi platform dengan pola `expect`/`actual`.
- [`10-kmp-dan-compiler/02-arsitektur-k2-compiler.md`](./10-kmp-dan-compiler/02-arsitektur-k2-compiler.md): Memahami arsitektur kompilator Kotlin 2.0 (K2), pemisahan Frontend IR (*Internal Representation*), FIR (Frontend Intermediate Representation), dan akselerasi kecepatan kompilasi.
- [`10-kmp-dan-compiler/03-observability-dan-produksi.md`](./10-kmp-dan-compiler/03-observability-dan-produksi.md): Metrik operasional, distributed tracing, pemetaan *coroutine context* ke MDC (Mapped Diagnostic Context), Micrometer, Prometheus, dan strategi kontainerisasi Docker distroless.

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Sistem
**Distributed Real-Time Financial Ledger & Transaction Engine (K-Ledger)**

### Deskripsi Sistem
Sebuah sistem pemrosesan transaksi keuangan terdistribusi berdaya tampung tinggi (*high-throughput*) yang memproses mutasi saldo multi-rekening secara real-time. Sistem ini menerapkan arsitektur *event-driven*, berbasis non-blocking I/O menggunakan Ktor dan Coroutines, dengan jaminan audit trail immutable menggunakan event sourcing pattern.

### Kebutuhan Fungsional & Teknis (Enterprise Stack)
1. **Runtime & Language**: Kotlin 2.0+ pada JDK 21 LTS.
2. **Web Framework**: Ktor Server dengan CIO Engine (Coroutines I/O), fully non-blocking.
3. **Database Layer**: JetBrains Exposed DSL terintegrasi dengan HikariCP dan PostgreSQL (berjalan di Docker) untuk ACID transaction idempotency.
4. **Asynchronous Processing**:
   - Pemrosesan transfer dana simultan menggunakan Channel dan SharedFlow.
   - Pemanfaatan `CoroutineScope` terisolasi dengan `SupervisorJob` dan penanganan *backpressure* adaptif.
5. **Security & Validation**:
   - Autentikasi berbasis JWT dengan *custom auth plugin*.
   - Domain-level validation memanfaatkan `sealed interface` sebagai *failure/success result wrap* (Result Monad pattern).
6. **Code Sharing Core (KMP Ready)**:
   - Modul `kledger-core` berupa Kotlin Multiplatform yang mendefinisikan skema Domain, Rules Validasi, dan Serializer tanpa ketergantungan pada JVM, sehingga dapat diimpor langsung oleh backend maupun mobile client.
7. **Observability**:
   - Logging terstruktur JSON dengan Coroutine MDC tracing (`transaction_id` & `user_id` diteruskan lintas dispatchers).
   - Metrics endpoint Prometheus (`/metrics`) mengekspos *latency percentiles* (p95, p99) dan *active coroutine count*.

### Standar Kelulusan Capstone
1. **Zero Uncaught Exceptions**: Tidak ada transaksi yang gagal dengan exception unhandled runtime; semua kegagalan ditangkap sebagai domain state ADT (`sealed class TransactionResult`).
2. **Concurrent Safety**: Teruji aman terhadap skenario *race-condition* saldo minus melalui integrasi stress-test (minimal 1.000 konkurensi transfer simultan menggunakan *virtual coroutines load test*).
3. **High Code Coverage**: Minimal 85% test coverage menggunakan `kotlin.test`, `mockk`, dan pustaka pengujian asinkron `Turbine`.

---
*Kurikulum ini dipertahankan secara aktif agar selalu sinkron dengan rilis stabil Kotlin dan ekosistem JetBrains.*