# BAB 10: Quiz, Challenge, & Knowledge Check
**Pengujian Enterprise, Observabilitas, & Delivery**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Foundations of Property-Based Testing vs. Example-Based Testing
Jelaskan perbedaan fundamental antara pengujian berbasis contoh (*example-based testing* seperti ScalaTest flat spec) dan pengujian berbasis properti (*property-based testing* menggunakan ScalaCheck/Discipline). Bagaimana mekanisme *test case reduction* (*shrinking*) bekerja di balik layar ketika sebuah invarian dilanggar, dan mengapa *shrinkers* bawaan dapat menyebabkan *infinite loop* atau hasil yang tidak minimal jika diterapkan pada tipe data kustom tanpa *lawful shrinker*?

### Soal 1.2: Context Propagation & Thread-Local Fallacy in Asynchronous Runtimes
Dalam sistem berbasis JVM tradisional, `ThreadLocal` sering digunakan untuk propagasi konteks observabilitas (misalnya SLF4J MDC atau tracing context). Mengapa pendekatan `ThreadLocal` secara fundamental rusak (*flawed*) ketika diintegrasikan dengan runtime berbasis non-blocking/fiber seperti Cats Effect (`IO`) atau ZIO? Bagaimana abstraksi fungsional murni seperti `IOLocal` atau `FiberRef` mengisolasi dan mempropagasi konteks eksekusi melintasi *fiber boundaries*?

### Soal 1.3: Verification Paradigms: Bytecode Mocking vs. In-Memory Interpreters
Dalam ekosistem Scala modern, penggunaan framework mock bytecode runtime (seperti Mockito atau PowerMock) secara luas dianggap sebagai *anti-pattern*, terutama pada arsitektur berbasis *purely functional programming* (Tagless Final atau ZIO environment). Uraikan kelemahan teknis penggunaan bytecode manipulation mocks dalam konteks konkurensi fungsional, dan jelaskan bagaimana *In-Memory Functional Interpreters* (menggunakan `Ref`, `Deferred`, atau pure *state monad*) memberikan jaminan *type safety* dan *deterministic testing* yang superior.

### Soal 1.4: Observability Pillars & OpenTelemetry Architecture in Scala
Uraikan arsitektur propagasi *distributed tracing* W3C TraceContext (`traceparent` dan `tracestate`) dalam ekosistem microservices Scala. Apa trade-off arsitektural antara menggunakan Java Agent berbasis bytecode injection otomatis (`opentelemetry-javaagent`) versus instrumentasi eksplisit fungsional tingkat kode (*in-code semantic instrumentation*) menggunakan library native seperti `otel4s` atau `natchez`?

### Soal 1.5: Compilation & Artifact Delivery: JIT Containers vs. GraalVM Native Image
Bandingkan implikasi operasional pengemasan aplikasi Scala enterprise antara container berbasis JVM standar (menggunakan `sbt-native-packager` dengan Eclipse Temurin/OpenJDK) versus GraalVM Native Image binary. Tinjau perbandingannya dari metrik:
1. *Cold-start latency* dan waktu inisialisasi kelas.
2. *Peak throughput* dan *profile-guided optimization* (PGO).
3. Hambatan refleksi runtime (*reflection metadata*) pada framework serialisasi (Circe, Borer) dan sistem aktor.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnosing Log Context Pollution in Asynchronous HTTP Pipelines
Sebuah sistem transaksi keuangan menggunakan http4s dan Cats Effect. Tim operasi menemukan anomali kritis: log transaksi dari Akun Nasabah X yang diproses secara konkuren tiba-tiba mencantumkan `tenant_id` dan `correlation_id` milik Akun Nasabah Y pada sistem agregasi log (Elasticsearch).
* **Pertanyaan Teknis:** Jelaskan akar penyebab kebocoran konteks (*context bleeding*) ini terkait interaksi antara `org.slf4j.MDC` statis dengan *thread pool work-stealing executor*. Tuliskan pola perbaikan (*remediation pattern*) menggunakan log4cats bersama `cats.effect.IOLocal` untuk memastikan isolasi konteks log per *fiber*.

### Soal 2.2: Mitigating Exhaustion & Non-Termination in ScalaCheck Custom Generators
Perhatikan cuplikan generator ScalaCheck untuk domain perbankan berikut:

```scala
case class ValidatedTransfer(sender: UUID, recipient: UUID, amount: BigDecimal)

val invalidGen: Gen[ValidatedTransfer] = for {
  s <- Arbitrary.arbitrary[UUID]
  r <- Arbitrary.arbitrary[UUID]
  a <- Arbitrary.arbitrary[BigDecimal]
} yield ValidatedTransfer(s, r, a)

val transferGen: Gen[ValidatedTransfer] = 
  invalidGen.suchThat(t => t.sender != t.recipient && t.amount > 0 && t.amount < 10000)
```

Ketika dijalankan dalam CI pipeline, suite pengujian tiba-tiba gagal secara intermiten dengan pesan error: `Gave up after 100 failed checks. (Generator exhaustion)`.
* **Pertanyaan Teknis:** Jelaskan mengapa kombinator `.suchThat` menyebabkan kelelahan generator (*generator exhaustion*). Rekonstruksi generator di atas menggunakan combinator `Gen` yang deterministik (`choose`, `map`, `flatMap`) tanpa membuang sampel (*filtering*), dan jelaskan bagaimana ScalaCheck mengelola parameter `Gen.Parameters.size`.

### Soal 2.3: Lifecycle Orchestration & Port Collisions in Testcontainers-Scala
Dalam *suite* pengujian integrasi enterprise dengan 400+ *test cases*, pengembang menggunakan `testcontainers-scala` untuk memutar instance PostgreSQL dan Apache Kafka. Pengujian berjalan lambat dan sering mengalami kegagalan akibat *bind port exceptions* serta Docker daemon OOM (*Out Of Memory*).
* **Pertanyaan Teknis:** 
1. Bedakan strategi siklus hidup container antara `ForEachTestContainer`, `ForAllTestContainers`, dan implementasi Singleton Container Pattern yang diorkestrasi secara manual.
2. Bagaimana mekanisme penataan resource cleanup melalui `Resource[IO, *]` atau `sbt.Tests.Cleanup` agar resource container dihentikan secara deterministik bahkan saat proses `sbt test` di-*abort* secara paksa (SIGINT/SIGTERM)?

### Soal 2.4: Bridging Unmanaged Asynchronous Callback to Traced Fiber Context
Anda sedang mengintegrasikan Java AWS SDK v2 (berbasis `CompletableFuture`) atau Kafka Producer Java Client ke dalam pipeline stream Cats Effect. Trace context OpenTelemetry (`Span`) hilang tepat setelah eksekusi callback jaringan dari thread pool AWS/Kafka kembali ke pool fiber Cats Effect.
* **Pertanyaan Teknis:** Tuliskan struktur abstraksi bridging menggunakan `IO.async` yang mengekstrak span aktif, menyuntikkan (*inject*) konteks ke dalam Java callback executor, dan mengembalikannya ke fiber run-loop Cats Effect menggunakan `IOLocal.getAndSet` tanpa merusak pohon rentang (*span tree*) distributed tracing.

### Soal 2.5: Classpath Conflict & Fat-JAR Deduplication Strategy in `sbt-assembly`
Saat mengeksekusi *task* `assembly` pada aplikasi multi-modul yang memadukan library Pekko/Akka, Netty, dan berbagai client gRPC, build gagal dengan kesalahan fatal:
`[error] deduplicate: different file contents found in the following: reference.conf, module-info.class, META-INF/services/...`
* **Pertanyaan Teknis:** Mengapa `MergeStrategy.first` atau `MergeStrategy.concat` naif terhadap `reference.conf` akan menyebabkan sistem aktor gagal menginisialisasi plugin saat runtime? Tuliskan konfigurasi `assemblyMergeStrategy` berbasis pattern-matching yang membedakan penanganan file konfigurasi HOCON, file SPI (*Service Provider Interface*), dan file metadata modular JVM secara presisi.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Silent Latency Spike & Fiber Starvation Incident
* **Konteks:** Sistem API pembayaran berbasis high-throughput microservice (Cats Effect 3, http4s, Doobie, HikariCP) mengalami insiden produksi: Latensi p99 meroket dari 45ms menjadi 18.000ms secara eksponensial di bawah beban 15.000 RPS. Metrik CPU pod Kubernetes berada pada 35%, memori JVM stabil pada 45% (tidak ada indikasi GC thrashing), namun Prometheus melaporkan metrik `cats_effect_compute_pool_active_threads` jenuh (*saturated*) dan `hikari_pool_connection_timeout_total` melonjak tajam.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda menganalisis korelasi metrik antara thread pool komputasi Cats Effect dengan connection pool HikariCP? Identifikasi kesalahan kode (*code smell*) yang paling umum terjadi ketika memanggil operasi database JDBC pemblokir (*blocking*) di dalam run-loop fungsional.
  2. Susun langkah diagnosis taktis menggunakan instrumentasi OpenTelemetry spans, Java Thread Dumps (`jstack`), dan perbaikan struktural pada level kode (pemisahan boundary *compute pool* vs *blocking pool*).

### Skenario B: Distributed Double-Spending & Flaky Integration Test Race
* **Konteks:** Tim QA menemukan *flaky test* pada integrasi sistem transfer dana antar dompet digital. Dari 100 kali eksekusi CI, sekitar 3 kali pengujian integrasi gagal: dua transfer saldo konkuren sebesar Rp 500.000 dieksekusi secara simultan pada akun dengan sisa saldo Rp 600.000. Ekspektasi pengujian: satu transaksi berhasil, satu transaksi ditolak dengan `InsufficientBalanceException`. Namun, hasil aktual pada pengujian yang gagal menunjukkan saldo akhir menjadi -Rp 400.000 (inkonsistensi data). Basis data pengujian menggunakan PostgreSQL via Testcontainers.
* **Pertanyaan Diagnostik:**
  1. Identifikasi skenario *concurrency anomaly* (misalnya: *Read Committed race condition* atau *lost update*) yang terjadi pada level SQL dan level isolasi transaksi PostgreSQL default.
  2. Bagaimana Anda merancang skenario pengujian konkuren deterministik menggunakan ScalaTest bersama utilitas fungsional (`cats.effect.IO.parSequence` atau `cats.effect.Deferred` sebagai *latch synchronizer*) untuk menjamin kedua request menyentuh database tepat pada milidetik yang sama tanpa bergantung pada `Thread.sleep`?

### Skenario C: Multi-Tenant Tracing Topology & Privacy Compliance (GDPR/PCI-DSS)
* **Konteks:** Anda adalah Principal Architect untuk platform SaaS perbankan multi-tenant berskala global. Sistem memproses jutaan event per detik melalui Apache Kafka, Akka Streams, dan ClickHouse. Regulasi PCI-DSS dan GDPR mewajibkan bahwa data sensitif (*Personally Identifiable Information* seperti PAN, CVV, dan Nama Lengkap) tidak boleh bocor ke sink telemetry (Prometheus, OpenTelemetry Jaeger/Tempo, Grafana Loki). Namun, tim investigasi *fraud* membutuhkan tracing terperinci hingga level identifikasi akun bermasalah.
* **Pertanyaan Diagnostik:**
  1. Rancang arsitektur filtering dan redaksi data telemetri (*telemetry sanitization*) pada level aplikasi Scala (sebelum span/log diekspor) versus level OpenTelemetry Collector pipeline. Apa trade-off performa CPU/memory pada node aplikasi jika sanitasi dilakukan via in-app functional interceptors?
  2. Bagaimana Anda mendesain arsitektur trace context propagation yang membawa `tenant_id` dan `user_id` terenkripsi non-reversibel (misal: HMAC dengan rotasi kunci berkala) menggunakan OpenTelemetry Baggage tanpa melanggar batasan ukuran header HTTP/Kafka metadata?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Resilient Integration Harness & Distributed Telemetry Engine

#### 1. Problem Statement
Bangun sebuah modul pengujian integrasi end-to-end dan instrumentasi observabilitas produksi untuk modul **"Core Settlement Clearing Engine"**. Modul ini memproses instruksi debit/kredit dengan persistensi event-sourcing sederhana, mengonsumsi event transfer dari Kafka, memvalidasi dan memutasi state akun di PostgreSQL, serta melaporkan metrik operasional dan trace terdistribusi.

#### 2. Technical Requirements
1. **Functional Core & Isolation:**
   - Gunakan Stack Scala 3 atau Scala 2.13 dengan Cats Effect 3 / ZIO 2.
   - Definisikan aljabar transfer akun: `transfer(from: AccountId, to: AccountId, amount: Money): F[Either[TransferError, TransferReceipt]]`.
2. **Propagasi Observabilitas Murni (Pure Tracing & Logging):**
   - Implementasikan context propagation manual/otomatis menggunakan `IOLocal` (Cats Effect) atau `FiberRef` (ZIO) yang merekam `TraceId`, `SpanId`, `CorrelationId`, dan `TenantId`.
   - Pastikan bahwa setiap pemanggilan basis data dan pengiriman event Kafka disuntikkan (*injected*) W3C TraceContext ke metadata headers.
   - Sediakan metric meter:
     - Counter: `transfers_total` (labels: `status`, `tenant_id`).
     - Histogram: `transfer_duration_seconds` (explicit buckets).
3. **Property-Based Testing Spec:**
   - Implementasikan property test menggunakan ScalaCheck: "Untuk sembarang akun $A$ dan $B$ dengan saldo awal acak, jumlah total uang di akun $A + B$ harus selalu konstan (*invariant conservation*) setelah sembarang permutasi dan transfer konkuren dieksekusi".
   - Buat custom shrinker yang memvalidasi bahwa jika terjadi kegagalan saldo negatif, generator mereduksi jumlah transfer seminimal mungkin (*minimal failing case*).
4. **Integration Test Environment:**
   - Setup pengujian integrasi berbasis `testcontainers-scala` untuk PostgreSQL dan Apache Kafka.
   - Pengujian harus memiliki arsitektur deterministik tanpa race condition: gunakan `Deferred` atau `CountDownLatch` fungsional untuk menguji 50 transfer simultan yang memperebutkan saldo terbatas.

#### 3. Strict Constraints
* **Dilarang keras** menggunakan `Thread.sleep` dalam kode implementasi maupun pengujian.
* **Dilarang keras** menggunakan `org.slf4j.MDC` secara mutabel langsung tanpa wrapper isolasi fiber.
* **Zero Mocking Framework:** Dilarang mengimpor library Mockito, PowerMock, atau EasyMock. Integrasi eksternal harus diverifikasi via real Testcontainers atau functional in-memory stub algebra (`Ref[IO, Map[AccountId, Money]]`).
* Waktu eksekusi keseluruhan suite pengujian (termasuk *spin-up* container) tidak boleh melebihi 45 detik pada lingkungan CI standar (2 vCPU, 4GB RAM).

#### 4. Expected Deliverables & Test Output
1. File implementasi algebra dan interpretasinya (`SettlementEngine.scala`).
2. Modul observabilitas (`TelemetryContext.scala`) yang menangani trace correlation injection.
3. Suite pengujian properti (`SettlementPropertySpec.scala`).
4. Suite pengujian integrasi container (`SettlementIntegrationSpec.scala`).
5. Cuplikan log terstruktur JSON yang membuktikan trace context (`trace_id`, `span_id`) terkorelasi dari HTTP controller hingga database commit.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal runtime fiber vs thread OS pada JVM, serta dampaknya terhadap mekanisme `ThreadLocal`.
- [ ] Prinsip matematis Property-Based Testing: Generator distributions, sizing parameters, dan shrinking algorithms.
- [ ] Standar W3C TraceContext (format `traceparent` dan `tracestate`) serta bagaimana konteks diserialisasi melintasi batas jaringan (HTTP, gRPC, Kafka).
- [ ] Perbedaan fungsional antara `Testcontainers-scala` per-suite lifecycle versus singleton lifecycle management.
- [ ] Implikasi arsitektur runtime dari GraalVM SubstrateVM terhadap Scala bytecode: *closed-world assumption*, inisialisasi *build-time* vs *run-time*, dan konfigurasi refleksi JNI.
- [ ] Mekanisme penggabungan artefak (`assemblyMergeStrategy`) pada sbt untuk konfigurasi TypeSafe HOCON (`reference.conf`) dan file SPI (`META-INF/services`).

### Saya tidak perlu menghafal:
- [ ] Sintaks exact baris per baris untuk konfigurasi Dockerfile multi-stage atau declarative pipeline CI/CD (GitHub Actions / GitLab CI).
- [ ] Pola ekspresi reguler (Regex) internal dari parsing string ISO timestamp pada log parser.
- [ ] Seluruh daftar method spesifik yang ada pada Java SDK OpenTelemetry internal (cukup memahami abstraksi fungsional Tracing/Span pada layer Scala).
- [ ] Kode heksadesimal spesifik status flag bitwise pada W3C traceparent header.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan memperbaiki pipeline pengujian sbt untuk mengeksekusi integrasi Testcontainers secara paralel dengan alokasi port dinamis tanpa *collision*.
- [ ] Mengimplementasikan *pure context propagation* logging menggunakan `log4cats` yang terisolasi per-fiber tanpa kebocoran memori.
- [ ] Mendiagnosis dan menyelesaikan *thread pool starvation* pada aplikasi berbasis Cats Effect/ZIO yang berinteraksi dengan API Java non-asinkron (*blocking I/O*).
- [ ] Menulis custom ScalaCheck generator dan custom *shrinkers* untuk tipe data domain enterprise yang kompleks tanpa memicu kegagalan *generator exhaustion*.
- [ ] Menginstrumentasi tracingspan manual pada titik integrasi sistem asinkron fungsional untuk mengidentifikasi latensi p99 pada Grafana Tempo atau Jaeger.