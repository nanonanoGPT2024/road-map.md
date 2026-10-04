# Kurikulum Lengkap Penguasaan Rekayasa Perangkat Lunak Scala
*Mastering Modern Pragmatic Functional and Object-Oriented Programming on the JVM*

---

## 1. Panduan Kursus & Pola Pikir (Course Overview & Mindset)

Selamat datang di silabus rekayasa sistem terdistribusi berbasis bahasa **Scala (Scala 3 Focus)**. Kursus ini dirancang khusus untuk membawa Anda dari pemahaman dasar JVM hingga tingkat arsitek sistem reaktif, data pipeline skala petabyte, dan layanan backend dengan konkurensi masif.

### Filosofi Inti: Pragmatic Multi-Paradigm
Scala bukan sekadar "Java yang lebih ringkas" atau "Haskell yang dipaksakan di JVM". Filosofi sejati Scala adalah peleburan alami antara dua paradigma dominan:
1. **Object-Oriented Programming (OOP) Lanjutan**: Modularitas, dekomposisi sistem komponen, dan enkapsulasi tipe data.
2. **Pure Functional Programming (FP)**: Transparansi referensial (*referential transparency*), determinisme fungsional, dan pemodelan aljabar yang bebas efek samping tersembunyi (*side-effects*).

Melalui Scala 3 (Dotty), bahasa ini menyempurnakan landasan matematisnya (*Dependent Object Types - DOT calculus*), menghasilkan sistem tipe ekspresif yang mampu mendeteksi kesalahan arsitektur pada fase kompilasi (*compile-time correctness*) alih-alih meledak saat *runtime*.

### Mental Model & Mindset Transisi
* **Dari Java/C#**: Hilangkan kebiasaan menggunakan *shared mutable state*, modifikasi objek in-place, penggunaan `null`, dan *exception throwing* yang tidak terlacak. Di Scala, data bersifat imutabel secara *default*, dan kontrol alur digerakkan oleh tipe data aljabar (*Algebraic Data Types*).
* **Dari Go/Python**: Jangan takut pada kedalaman sistem tipe Scala. Scala menggeser beban verifikasi logika dari *runtime integration test* langsung ke kompilator melalui *Type Classes*, variansi tipe, dan *Contextual Abstractions*.
* **Ekosistem Produksi**: Anda akan diarahkan untuk membangun sistem menggunakan paradigma *Functional Effect Systems* modern (`Cats Effect`, `ZIO`, atau `Fs2`) yang menjadi fondasi layanan *cloud-native* berkinerja tinggi saat ini.

---

## 2. Peta Jalan Pembelajaran (Learning Roadmap)

```text
Eksplorasi Kurikulum Scala (10 Bab)
├── [Bab 01] Fondasi Bahasa & Ekosistem Scala
├── [Bab 02] Pemrograman Berorientasi Objek Lanjutan
├── [Bab 03] Fondasi Pemrograman Fungsional
├── [Bab 04] Sistem Koleksi Scala & Evaluasi
├── [Bab 05] Sistem Pengetikan Tingkat Lanjut (Advanced Type System)
├── [Bab 06] Abstraksi Kontekstual & Type Classes (Scala 3)
├── [Bab 07] Konkurensi Asinkron & Actor Architecture
├── [Bab 08] Functional Effect Systems (Cats Effect & ZIO)
├── [Bab 09] Data Streaming Reaktif & Integrasi Sistem
└── [Bab 10] Pengujian Enterprise, Observabilitas, & Delivery
```

---

## 3. Navigasi Detail Modul (Bab 01 s/d Bab 10)

### [Bab 01: Fondasi Bahasa & Ekosistem Scala](./bab-01-fondasi-bahasa-dan-ekosistem/README.md)
Fondasi infrastruktur *tooling*, JVM runtime, dan perbedaan fundamental semantik kode Scala 3.
* [01.1 Toolchain & Arsitektur Ekosistem: sbt, Scala CLI, dan JVM Runtime](./bab-01-fondasi-bahasa-dan-ekosistem/01-toolchain-sbt-scala-cli.md)
* [01.2 Nilai, Variabel, dan Kontrol Alur Berbasis Ekspresi](./bab-01-fondasi-bahasa-dan-ekosistem/02-ekspresi-dan-variabel.md)
* [01.3 Definisi Fungsi Dasar dan Manajemen Lingkup Akses](./bab-01-fondasi-bahasa-dan-ekosistem/03-fungsi-dasar-dan-scope.md)

### [Bab 02: Pemrograman Berorientasi Objek Lanjutan](./bab-02-oop-lanjutan/README.md)
Implementasi OOP yang bersih menggunakan paradigma Scala tanpa degradasi kemurnian data.
* [02.1 Classes, Constructors, Case Classes, dan Immutability Semantics](./bab-02-oop-lanjutan/01-classes-case-classes.md)
* [02.2 Singletons, Companion Objects, dan Factory Patterns](./bab-02-oop-lanjutan/02-objects-dan-companion.md)
* [02.3 Traits, Linearized Mixin Composition, dan Hirarki Tipe Any](./bab-02-oop-lanjutan/03-traits-dan-linearization.md)

### [Bab 03: Fondasi Pemrograman Fungsional](./bab-03-fondasi-pemrograman-fungsional/README.md)
Pemisahan murni antara komputasi logika bisnis dan penanganan efek samping.
* [03.1 Pure Functions, First-Class Functions, Currying, dan PHOF](./bab-03-fondasi-pemrograman-fungsional/01-pure-functions-hof-currying.md)
* [03.2 Algebraic Data Types (ADTs) & Exhaustive Pattern Matching](./bab-03-fondasi-pemrograman-fungsional/02-adts-dan-pattern-matching.md)
* [03.3 Penanganan Kesalahan Idiomatis: Option, Either, dan Try](./bab-03-fondasi-pemrograman-fungsional/03-error-handling-idiomatis.md)

### [Bab 04: Sistem Koleksi Scala & Evaluasi](./bab-04-koleksi-dan-evaluasi/README.md)
Eksplorasi mendalam atas performa hierarki koleksi standar dan strategi evaluasi komputasi.
* [04.1 Arsitektur Hirarki Koleksi: Immutable vs Mutable Collections](./bab-04-koleksi-dan-evaluasi/01-arsitektur-koleksi.md)
* [04.2 Operasi Transformasi Koleksi Tingkat Tinggi (Fold, Map, FlatMap, Scan)](./bab-04-koleksi-dan-evaluasi/02-transformasi-fungsional-koleksi.md)
* [04.3 Strategi Evaluasi: Eager, Lazy (LazyList), dan View Pipeline Optimization](./bab-04-koleksi-dan-evaluasi/03-lazy-evaluation-dan-views.md)

### [Bab 05: Sistem Pengetikan Tingkat Lanjut (Advanced Type System)](./bab-05-advanced-type-system/README.md)
Memaksimalkan kompilator Scala untuk menjamin keabsahan invariansi sistem domain.
* [05.1 Generics dan Variansi Sistem Tipe: Covariance, Contravariance, Invariance](./bab-05-advanced-type-system/01-generics-dan-variansi.md)
* [05.2 Type Bounds (Upper, Lower), Context Bounds, dan Opaque Types](./bab-05-advanced-type-system/02-type-bounds-opaque-types.md)
* [05.3 Intersection Types, Union Types, dan Generalized Type Constraints](./bab-05-advanced-type-system/03-union-intersection-constraints.md)

### [Bab 06: Abstraksi Kontekstual & Type Classes (Scala 3)](./bab-06-abstraksi-kontekstual/README.md)
Penguasaan pola *ad-hoc polymorphism* modern menggantikan arsitektur implisit klasik.
* [06.1 Given Instances, Using Clauses, dan Resolusi Parameter Konteks](./bab-06-abstraksi-kontekstual/01-givens-dan-using-clauses.md)
* [06.2 Extension Methods dan Implementasi Pola Type Classes](./bab-06-abstraksi-kontekstual/02-extension-methods-typeclasses.md)
* [06.3 Context Functions dan Migrasi dari Implicits Scala 2](./bab-06-abstraksi-kontekstual/03-context-functions-dan-migrasi.md)

### [Bab 07: Konkurensi Asinkron & Actor Architecture](./bab-07-konkurensi-dan-actors/README.md)
Pemrograman paralel non-blocking dan model aktor terdistribusi pada JVM.
* [07.1 Scala Future, Promise, dan Konfigurasi ExecutionContext](./bab-07-konkurensi-dan-actors/01-futures-promises-execution-context.md)
* [07.2 Komposisi Asinkron Kompleks dan Mitigasi Race Condition](./bab-07-konkurensi-dan-actors/02-komposisi-asinkron-dan-koordinasi.md)
* [07.3 Paradigma Actor Model Menggunakan Apache Pekko / Akka](./bab-07-konkurensi-dan-actors/03-actor-model-dan-supervision.md)

### [Bab 08: Functional Effect Systems (Cats Effect & ZIO)](./bab-08-functional-effect-systems/README.md)
Standar industri arsitektur mikroservis Scala berbasis komputasi monadik murni.
* [08.1 Anatomi Effect System: IO Monad, Referential Transparency, dan Purity](./bab-08-functional-effect-systems/01-io-monad-dan-referential-transparency.md)
* [08.2 Model Konkurensi Hijau: Fibers, Concurrency Primitives (Ref, Deferred)](./bab-08-functional-effect-systems/02-fibers-ref-deferred.md)
* [08.3 Resource Management: Resource Handling Aljabar dan Bracket Pattern](./bab-08-functional-effect-systems/03-resource-safety-dan-bracket.md)

### [Bab 09: Data Streaming Reaktif & Integrasi Sistem](./bab-09-data-streaming-dan-integrasi/README.md)
Manajemen aliran data kontinu dengan *backpressure* otomatis dan interaksi eksternal.
* [09.1 Reactive Stream Processing dengan FS2 (Functional Streams for Scala)](./bab-09-data-streaming-dan-integrasi/01-fs2-stream-processing.md)
* [09.2 Serialisasi JSON Deklaratif Performa Tinggi (Circe / zio-json Derivation)](./bab-09-data-streaming-dan-integrasi/02-json-codec-derivation.md)
* [09.3 Akses Basis Data Fungsional Transaksional (Skunk / Doobie)](./bab-09-data-streaming-dan-integrasi/03-database-access-skunk-doobie.md)

### [Bab 10: Pengujian Enterprise, Observabilitas, & Delivery](./bab-10-testing-observabilitas-delivery/README.md)
Standar pengujian tingkat produksi, instrumen metrik, dan optimasi artefak akhir.
* [10.1 Property-Based Testing dan Unit Testing Modern (MUnit & ScalaCheck)](./bab-10-testing-observabilitas-delivery/01-munit-dan-scalacheck.md)
* [10.2 Distributed Tracing & Observabilitas Terdistribusi (OpenTelemetry, Prometheus)](./bab-10-testing-observabilitas-delivery/02-observability-opentelemetry.md)
* [10.3 Kontainerisasi, Tuning GC JVM, dan GraalVM Native Image Compilation](./bab-10-testing-observabilitas-delivery/03-packaging-graalvm-tuning.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title
**"AegisLedger: Real-Time Distributed Financial Transaction Engine & Fraud Ingestion Pipeline"**

### Arsitektur & Gambaran Sistem
AegisLedger adalah mesin inti perbankan terdistribusi (*distributed core banking engine*) yang menangani penegakan *double-entry bookkeeping*, validasi saldo real-time, dan deteksi kecurangan (*fraud scoring*) asinkron menggunakan pendekatan *event-sourcing*. 

```text
[HTTP API Ingestion: Http4s/Tapir]
                │
                ▼
      [Domain Validation]
        (Pure Types / ADTs)
                │
        ┌───────┴───────┐
        ▼               ▼
[Transactor Pool]  [Event Publisher]
  (Skunk/Doobie)       (FS2 / Kafka)
        │               │
        ▼               ▼
  [Postgres DB]   [Fraud Engine Stream]
                    (Cats Effect Fibers)
```

### Kebutuhan Teknis Minimum (Tech Stack Requirements)
1. **Runtime & Bahasa**: Scala 3 (versi 3.3 LTS atau lebih tinggi), JDK 21 Temurin.
2. **Concurrency & Effect Runtime**: `Cats Effect 3` atau `ZIO 2`. Mengharamkan penggunaan `scala.concurrent.Future` secara mentah pada lapisan domain inti.
3. **HTTP & API Layer**: `Http4s` terintegrasi dengan `Tapir` untuk penyediaan dokumentasi OpenAPI/Swagger otomatis secara tipe-aman (*end-to-end type safety*).
4. **Data Persistence**: `Skunk` (PostgreSQL Driver Non-blocking murni) atau `Doobie` dengan skema migrasi terisolasi.
5. **Streaming Pipeline**: `FS2 Kafka` untuk memproses *ledger events* secara asinkron dengan garansi semantik pengiriman *at-least-once*.
6. **Data Serialization**: `Circe` atau `zio-json` dengan kompilasi otomatis (*macro derivation*) tanpa *runtime reflection*.
7. **Pengujian Komprehensif**:
   * *Unit Tests* & *Property-Based Tests* menggunakan `ScalaCheck` untuk memvalidasi hukum matematika perbankan (total debit harus selalu seimbang dengan total kredit dalam sembarang permutasi acak).
   * *Integration Tests* menggunakan `Testcontainers-scala` untuk postgresql dan broker kafka.
8. **Observabilitas**: Ekspor metrik latensi persentil P99 dan jejak terdistribusi via `OpenTelemetry SDK`.

### Standar Kriteria Kelulusan (Definition of Done)
* **Zero Mutation**: Tidak ada penggunaan ekspresi `var`, koleksi yang dapat berubah (`mutable`), atau fungsi tanpa transparansi referensial di dalam paket logika domain bisnis.
* **Exhaustive Matching**: Kompilator berjalan dengan konfigurasi `-Werror` dan `-Wunused:all`. Tidak boleh ada peringatan (*warning*) *match non-exhaustive*.
* **Resource Safety**: Seluruh koneksi eksternal terbungkus dalam `Resource` monad untuk mencegah kebocoran *socket* atau *file descriptor* saat kondisi panik atau terminasi pod/kontainer (*graceful shutdown*).
* **Throughput Target**: Mampu memproses sedikitnya 2.500 transaksi per detik (TPS) pada skenario evaluasi konkuren terdistribusi lokal tanpa inkonsistensi saldo.