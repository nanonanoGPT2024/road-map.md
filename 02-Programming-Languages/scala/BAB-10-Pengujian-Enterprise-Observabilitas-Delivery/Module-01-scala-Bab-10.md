# Bab 10 Module 01: Pengujian Enterprise, Observabilitas, & Delivery

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** `SCALA-ENT-1001`
* **Nama Modul:** Pengujian Enterprise, Observabilitas, & Delivery
* **Kategori Kurikulum:** `02-Programming-Languages` / `scala`
* **Tingkat Kesulitan:** Advanced / Enterprise-Grade
* **Prasyarat:**
  * Pemahaman mendalam tentang Scala 3 (Metaprogramming dasar, Contextual Abstractions / Given & Using).
  * Penguasaan pemrograman fungsional asinkron dan efek (`cats.effect.IO` atau `zio.ZIO`).
  * Konsep dasar containerization (Docker) dan protokol jaringan (HTTP/gRPC).
* **Stack Teknologi:**
  * Scala 3.3+ (LTS)
  * Cats Effect 3.5+
  * MUnit / Weaver-test
  * ScalaCheck (Property-Based Testing)
  * Testcontainers-scala (PostgreSQL & Kafka)
  * OpenTelemetry Java SDK / Tracing API
  * sbt 1.9+ & `sbt-native-packager`

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:

1. **Mendesain Strategi Pengujian Berlapis (Testing Pyramid):** Mengimplementasikan unit test murni fungsional, property-based testing untuk memvalidasi invarian domain, dan end-to-end integration testing berbasis ephemeral container.
2. **Mengisolasi dan Menguji Efek Samping Kompleks:** Memanfaatkan `Testcontainers-scala` untuk pengujian integrasi database dan messaging broker tanpa bergantung pada lingkungan eksternal statis.
3. **Mengimplementasikan Observabilitas Terdistribusi:** Menginstrumentasikan aplikasi Scala dengan OpenTelemetry (Distributed Tracing, Metrics, dan Structured Logging) yang mempertahankan konteks asinkron melintasi batas *fiber*.
4. **Membangun Pipeline Delivery Nir-Cacat:** Mengonfigurasi build sbt deterministik, membuat image kontainer produksi yang aman, minimalis, dan teroptimasi, serta mengotomatisasi pengujian dalam siklus CI/CD enterprise.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa perangkat lunak enterprise, pengujian dan observabilitas bukanlah aktivitas tambahan di akhir siklus hidup rilis (*afterthought*), melainkan bagian integral dari desain sistem:

```
+-----------------------------------------------------------------------+
|                    MENTAL MODEL PENGEMBANGAN ENTERPRISE               |
|                                                                       |
|  [ Domain Core ] ---> [ Mathematical Laws & Properties ]              |
|        |              - Purity menjamin determinisme                  |
|        |              - ScalaCheck membuktikan properti invarian      |
|        v                                                              |
|  [ Integration ] ---> [ Ephemeral Reality Testing ]                   |
|        |              - Hindari mock berlebihan                       |
|        |              - Uji terhadap dependensi nyata (Testcontainers)|
|        v                                                              |
|  [ Production  ] ---> [ Observability as Correctness Verification ]   |
|                       - Tracing melacak dependensi runtime             |
|                       - Metrik memvalidasi degradasi performa         |
+-----------------------------------------------------------------------+
```

1. **Efek sebagai Nilai (*Effects as Values*):** Program Scala fungsional mendeskripsikan komputasi sebagai nilai data (`IO[A]`). Oleh karena itu, pengujian tidak mengeksekusi efek samping secara mutatif, melainkan mengevaluasi deskripsi aljabar tersebut dalam lingkungan uji terkontrol.
2. **Hindari *Mocking* yang Rapuh:** Alih-alih membuat mock tiruan untuk dependensi I/O (seperti PostgreSQL atau Kafka) yang menyembunyikan inkonsistensi dialek SQL atau komparasi konkurensi, gunakan kontainer efemeral (*ephemeral containers*) yang identik dengan lingkungan produksi.
3. **Observabilitas adalah Pengujian di Lingkungan Produksi:** Telemetri (Trace, Metric, Log) merupakan perluasan dari sistem tipe dan pengujian. *Trace ID* harus menjadi warga kelas satu yang dipropagasikan secara otomatis melintasi eksekusi asynchronous *fibers*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### A. Arsitektur Pengujian Integrasi dengan Testcontainers

Alur siklus hidup pengujian integrasi yang mengisolasi database dan menguji dependensi I/O:

```
 +-----------------------------------------------------------------------+
 |                     MUnit / Cats Effect Test Suite                    |
 +-----------------------------------------------------------------------+
        |                                                   |
        | 1. Inisialisasi Resource                          | 4. Assertions
        v                                                   v
 +----------------------+                           +-------------------+
 | Testcontainers Scala |                           | Domain Repository |
 +----------------------+                           +-------------------+
        |                                                   ^
        | 2. Spin-up                                        | 3. Flyway
        v                                                   |    Migration
 +----------------------------------------------------------+-----------+
 | Docker Daemon (Host / CI)                                            |
 |  +----------------------------------------------------------------+  |
 |  | PostgreSQL Ephemeral Container (Dynamic Port: e.g., 32789)     |  |
 |  +----------------------------------------------------------------+  |
 +----------------------------------------------------------------------+
```

### B. Konteks Propagasi Tracing Terdistribusi

Propagasi *Tracing Context* (W3C TraceContext) melintasi Cats Effect `Fiber` menggunakan `IOLocal`:

```
 [ HTTP Request ] -> Headers: "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
         |
         v
 +-----------------------------------------------------------------------+
 | HTTP Middleware (Extract SpanContext)                                 |
 | Store in: IOLocal[TraceContext]                                       |
 +-----------------------------------------------------------------------+
         |
         | Fiber Fork (cats.effect.IO.cede / Async Boundary)
         v
 +-----------------------------------+   +-------------------------------+
 | Fiber-A: Payment Service          |   | Fiber-B: Audit Log Producer   |
 | Context: Inherited TraceContext   |   | Context: Inherited TraceContext|
 | Action: Exec DB Transaction       |   | Action: Push to Kafka         |
 +-----------------------------------+   +-------------------------------+
         \                                   /
          \                                 /
           v                               v
 +-----------------------------------------------------------------------+
 | OpenTelemetry Exporter (gRPC / OTLP) -> Collector / Jaeger / Grafana  |
 +-----------------------------------------------------------------------+
```

### C. Pipeline Delivery Produksi (CI/CD ke Kontainer)

```
 [ git push main ]
         |
         v
 +-----------------------------------------------------------------------+
 | Continuous Integration (CI Engine)                                    |
 |  1. sbt scalafmtCheckAll                                              |
 |  2. sbt test (Unit & Property-based Tests)                            |
 |  3. sbt IntegrationTest/test (Testcontainers Driven)                 |
 |  4. sbt "dependencyCheck; scapegoat"                                  |
 +-----------------------------------------------------------------------+
         |
         v (Artifact Verification Passed)
 +-----------------------------------------------------------------------+
 | Artifact Packaging                                                    |
 |  - sbt Docker/publishLocal                                            |
 |  - Multi-stage packaging (Eclipse Temurin / Distroless base)          |
 |  - Non-root user: uid 10001 (Security Hardening)                      |
 +-----------------------------------------------------------------------+
         |
         v
 [ Container Registry ] ----> [ Kubernetes Cluster Delivery ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Test Harness Execution Engine (Cats Effect + MUnit)

Eksekusi pengujian fungsional berjalan di atas runloop Cats Effect:
* Pengujian didefinisikan sebagai ekspresi `IO[Unit]`.
* Runtime MUnit Cats Effect mengeksekusi test runner di atas `IORuntime` internal.
* Eksekusi assertion tidak melempar eksepsi mutatif secara langsung jika ditulis dalam format aljabar, melainkan dievaluasi sebagai kegagalan komputasi (`IO.raiseError` atau `Either.Left`).

### 2. Testcontainers-scala Internals

* Berkomunikasi langsung dengan Docker daemon melalui Docker Java API Client via Unix Socket (`/var/run/docker.sock`) atau Windows Named Pipe.
* Menetapkan *random dynamic port mapping* untuk mencegah port conflict saat pengujian paralel dijalankan.
* Menggunakan kontainer *Ryuk* (`testcontainers/ryuk`) untuk membersihkan kontainer yatim (*orphaned containers*) jika proses JVM pengujian crash secara tiba-tiba (*SIGKILL*).

### 3. OpenTelemetry Context Engine

* `SpanContext` OpenTelemetry bersifat *immutable*.
* Dalam lingkungan multi-threaded murni, konteks disimpan di `ThreadLocal`. Namun, karena Cats Effect mengabstraksikan thread menjadi *Fiber* (green threads/m:n scheduling), `ThreadLocal` biasa akan bocor atau hilang ketika Fiber berpindah antar worker thread JVM.
* Solusi: Menggunakan Cats Effect `IOLocal`, yang secara internal menyalin state konteks saat fiber melakukan operasi *forking*.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Property-Based Testing (PBT) vs Example-Based Testing

Contoh pengujian konvensional (*Example-Based Testing*) hanya membuktikan bahwa sistem berfungsi untuk input tertentu (misalnya, input `5` menghasilkan `10`). 

Property-Based Testing (ScalaCheck) membalik paradigma ini:
* Developer mendefinisikan sifat-sifat universal sistem (*invarian* atau *hukum aljabar*).
* Mesin PBT menghasilkan ratusan hingga ribuan kombinasi input acak (*generators*).
* Jika ditemukan input yang menyebabkan kegagalan, mesin akan menjalankan algoritma penyusutan (*shrinking*) untuk mencari input terkecil yang mereproduksi kegagalan tersebut.

**Tiga Hukum Universal Domain:**
1. **Inversibilitas (Round-trip):** Mengubah data ke representasi lain dan mengembalikannya harus menghasilkan nilai awal:
   $$\forall x \in Domain, \quad deserialize(serialize(x)) \equiv x$$
2. **Idempotensi:** Mengeksekusi mutasi berulang kali harus menghasilkan state yang setara dengan eksekusi pertama:
   $$\forall x, \quad f(f(x)) \equiv f(x)$$
3. **Invarian Domain:** Atribut invariant tidak boleh terlanggar dalam kondisi apa pun:
   $$\forall account, \quad account.balance \ge 0$$

### Distributed Tracing: The W3C Trace Context Standard

Observabilitas enterprise menuntut korelasi permintaan end-to-end. Spesifikasi W3C terdiri dari:
* `traceparent`: Format: `version-trace_id-parent_id-trace_flags`
  * `version`: 2 hex chars (`00`)
  * `trace_id`: 32 hex chars (unik untuk satu end-to-end workflow)
  * `parent_id`: 16 hex chars (mengidentifikasi caller span)
  * `trace_flags`: 8-bit field (e.g., `01` untuk recorded/sampled)
* `tracestate`: Menyimpan metadata spesifik sistem tracing vendor-specific tanpa memodifikasi `traceparent`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode yang mendemonstrasikan Property-Based Testing dengan ScalaCheck dan Unit Testing efek murni dengan MUnit Cats Effect.

```scala
// File: src/test/scala/com/enterprise/domain/AccountSuite.scala
package com.enterprise.domain

import munit.CatsEffectSuite
import org.scalacheck.Prop.*
import org.scalacheck.Gen
import cats.effect.IO

// 1. Model Domain Murni
case class Money(amount: BigDecimal) {
  require(amount >= 0, "Uang tidak boleh bernilai negatif")
  def +(that: Money): Money = Money(this.amount + that.amount)
  def -(that: Money): Either[String, Money] =
    if (this.amount >= that.amount) Right(Money(this.amount - that.amount))
    else Left("Saldo tidak mencukupi")
}

case class Account(id: String, balance: Money) {
  def deposit(amount: Money): Account = copy(balance = balance + amount)
  def withdraw(amount: Money): Either[String, Account] =
    balance.-(amount).map(newBalance => copy(balance = newBalance))
}

// 2. Test Suite Menggunakan MUnit Cats Effect
class AccountSuite extends CatsEffectSuite {

  // Generator ScalaCheck
  val genMoney: Gen[Money] = 
    Gen.chooseNum(0L, 1000000000L).map(cents => Money(BigDecimal(cents) / 100))

  // Property 1: Round-trip / Symmetry (Deposit lalu Withdraw menghasilkan saldo semula)
  test("Property: Melakukan deposit dan withdraw dengan nilai yang sama menghasilkan balance awal") {
    val property = forAll(genMoney, genMoney) { (initialBalance, txAmount) =>
      val account = Account("acc-123", initialBalance)
      val result = account.deposit(txAmount).withdraw(txAmount)
      result == Right(account)
    }
    
    // Konversi ScalaCheck Property ke Assertion MUnit
    IO(property.check()).map(result => assert(result.passed, s"Property gagal: $result"))
  }

  // Efek Asinkron Cats Effect Test
  test("Cats Effect: Akun harus dapat memproses transaksi asinkron secara deterministik") {
    for {
      accountRef <- IO.ref(Account("acc-001", Money(BigDecimal(100.00))))
      _          <- accountRef.update(_.deposit(Money(BigDecimal(50.00))))
      finalAcc   <- accountRef.get
    } yield {
      assertEquals(finalAcc.balance, Money(BigDecimal(150.00)))
    }
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 9–15 (`Money`):** Nilai domain (*Value Object*) yang memiliki invarian: tidak boleh negatif. Fungsi penambahan (`+`) bersifat tertutup pada domain `Money`. Fungsi pengurangan (`-`) mengembalikan `Either[String, Money]` untuk memodelkan kegagalan secara fungsional tanpa runtime exceptions.
* **Baris 24 (`class AccountSuite extends CatsEffectSuite`):** Kelas suite pengujian yang diintegrasikan dengan runtime Cats Effect, memungkinkan suite mengeksekusi ekspresi `IO[Unit]` secara native.
* **Baris 27–28 (`val genMoney`):** Mendefinisikan generator data ScalaCheck. Mengambil angka bertipe numerik acak antara `0` hingga `1.000.000.000` sen untuk mencegah anomali pembulatan *floating-point*, kemudian membaginya dengan 100 sebagai format desimal mata uang.
* **Baris 31 (`forAll(genMoney, genMoney)`):** Membentuk universal quantification ($\forall initialBalance, txAmount$). ScalaCheck akan mengeksekusi blok kode di dalamnya sebanyak 100 kali iterasi dengan data yang divariasikan secara ekstrim (termasuk nilai-nilai batas seperti 0).
* **Baris 33–34:** Memvalidasi invarian fungsional: $Account + X - X = Account$. Jika kondisi `result == Right(account)` bernilai false, pengujian langsung gagal dan ScalaCheck akan menyusutkan nilai `txAmount` ke nilai terkecil yang memicu error.
* **Baris 42–49:** Pengujian efek konkuren menggunakan `IO.ref` (Cats Effect atomic reference). Ini membuktikan bahwa mutasi state akun diisolasi dalam memori fungsional murni tanpa race conditions.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Financial Payment Settlement Service

Sebuah startup FinTech memproses transfer dana antar-bank skala enterprise. Sistem ini memiliki SLA 99.999% ketersediaan dan zero data-loss tolerance.

**Kebutuhan Sistem:**
1. **Pengujian Integrasi:** Repositori transaksi harus diuji langsung terhadap PostgreSQL nyata (menggunakan PostgreSQL jsonb dan locking row-level `FOR UPDATE`), bukan H2 atau mock in-memory, untuk menjamin semantik transaksi database yang presisi.
2. **Observabilitas:** Setiap mutasi settlement harus memancarkan span tracing yang membawa atribut bisnis (`account_id`, `transaction_id`, `amount`) dan metrik latensi yang dapat dikonsumsi oleh OpenTelemetry Collector.
3. **Packaging:** Layanan harus dikemas ke dalam Docker image berbasis minimal runtime dengan isolasi hak akses (non-root) untuk mencegah eksploitasi kontainer.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

### 1. Konfigurasi `build.sbt` Lengkap

```scala
ThisBuild / scalaVersion := "3.3.1"
ThisBuild / version      := "1.0.0"
ThisBuild / organization := "com.enterprise"

lazy val root = (project in file("."))
  .enablePlugins(JavaAppPackaging, DockerPlugin)
  .settings(
    name := "settlement-service",
    libraryDependencies ++= Seq(
      // Cats Effect Ecosystem
      "org.typelevel" %% "cats-effect" % "3.5.3",
      
      // Database Persistence (Doobie / Skunk / JDBC)
      "org.postgresql" % "postgresql" % "42.7.1",
      "org.flywaydb"   % "flyway-core" % "10.6.0",
      "com.zaxxer"     % "HikariCP"    % "5.1.0",
      
      // Observability: OpenTelemetry
      "io.opentelemetry" % "opentelemetry-api" % "1.34.1",
      "io.opentelemetry" % "opentelemetry-sdk" % "1.34.1",
      "io.opentelemetry" % "opentelemetry-exporter-otlp" % "1.34.1",
      
      // Testing Frameworks
      "org.scalameta" %% "munit"               % "1.0.0-M10" % Test,
      "org.typelevel" %% "munit-cats-effect"   % "2.0.0-M4"  % Test,
      "org.scalacheck" %% "scalacheck"         % "1.17.0"    % Test,
      "com.dimafeng"  %% "testcontainers-scala-munit"      % "0.41.2" % Test,
      "com.dimafeng"  %% "testcontainers-scala-postgresql" % "0.41.2" % Test
    ),
    
    // Docker Packaging Settings
    dockerBaseImage    := "eclipse-temurin:21-jre-alpine",
    dockerUpdateLatest := true,
    dockerExposedPorts := Seq(8080, 9464),
    dockerUsername     := Some("enterprise"),
    Docker / daemonUser := "appuser",
    Docker / daemonUserUid := Some("10001")
  )
```

### 2. Trace Context Wrapper Menggunakan `IOLocal`

```scala
// File: src/main/scala/com/enterprise/telemetry/TraceContext.scala
package com.enterprise.telemetry

import cats.effect.{IO, IOLocal}
import io.opentelemetry.api.trace.{Span, Tracer}

case class TraceContext(traceId: String, spanId: String)

object TraceContext {
  def create(using tracer: Tracer): IO[(TraceContext, Span)] = IO {
    val span = tracer.spanBuilder("operation").startSpan()
    val ctx = TraceContext(
      span.getSpanContext.getTraceId,
      span.getSpanContext.getSpanId
    )
    (ctx, span)
  }
}

trait Traced[F[_]] {
  def getContext: F[TraceContext]
  def childSpan[A](name: String)(fa: F[A]): F[A]
}

class IOTraced(local: IOLocal[TraceContext], tracer: Tracer) extends Traced[IO] {
  def getContext: IO[TraceContext] = local.get

  def childSpan[A](name: String)(fa: IO[A]): IO[A] = {
    for {
      parent <- local.get
      span <- IO(tracer.spanBuilder(name).startSpan())
      newCtx = TraceContext(span.getSpanContext.getTraceId, span.getSpanContext.getSpanId)
      result <- local.set(newCtx) *> fa.guarantee(IO(span.end()))
    } yield result
  }
}
```

### 3. Komponen Repositori Settlement

```scala
// File: src/main/scala/com/enterprise/settlement/SettlementRepository.scala
package com.enterprise.settlement

import cats.effect.IO
import java.sql.Connection
import java.util.UUID

case class SettlementRecord(id: UUID, accountId: String, amount: BigDecimal, status: String)

class SettlementRepository(getConnection: IO[Connection]) {
  
  def insert(record: SettlementRecord): IO[Unit] = {
    getConnection.bracket { conn =>
      IO.blocking {
        val sql = "INSERT INTO settlements (id, account_id, amount, status) VALUES (?, ?, ?, ?)"
        val stmt = conn.prepareStatement(sql)
        stmt.setObject(1, record.id)
        stmt.setString(2, record.accountId)
        stmt.setBigDecimal(3, record.amount.bigDecimal)
        stmt.setString(4, record.status)
        stmt.executeUpdate()
      }
    }(conn => IO.blocking(conn.close()))
  }

  def findById(id: UUID): IO[Option[SettlementRecord]] = {
    getConnection.bracket { conn =>
      IO.blocking {
        val sql = "SELECT id, account_id, amount, status FROM settlements WHERE id = ?"
        val stmt = conn.prepareStatement(sql)
        stmt.setObject(1, id)
        val rs = stmt.executeQuery()
        if (rs.next()) {
          Some(SettlementRecord(
            rs.getObject("id", classOf[UUID]),
            rs.getString("account_id"),
            rs.getBigDecimal("amount"),
            rs.getString("status")
          ))
        } else None
      }
    }(conn => IO.blocking(conn.close()))
  }
}
```

### 4. Integration Test Suite dengan Testcontainers

```scala
// File: src/test/scala/com/enterprise/settlement/SettlementRepositoryITSpec.scala
package com.enterprise.settlement

import munit.CatsEffectSuite
import com.dimafeng.testcontainers.munit.TestContainerForAll
import com.dimafeng.testcontainers.PostgreSQLContainer
import cats.effect.IO
import org.flywaydb.core.Flyway
import java.sql.DriverManager
import java.util.UUID

class SettlementRepositoryITSpec extends CatsEffectSuite with TestContainerForAll {

  override val containerDef: PostgreSQLContainer.Def = PostgreSQLContainer.Def(
    dockerImageName = "postgres:16-alpine"
  )

  def runMigrations(container: PostgreSQLContainer): Unit = {
    val flyway = Flyway.configure()
      .dataSource(container.jdbcUrl, container.username, container.password)
      .load()
    
    // Inisialisasi skema secara dinamis untuk integration testing
    val conn = DriverManager.getConnection(container.jdbcUrl, container.username, container.password)
    try {
      val stmt = conn.createStatement()
      stmt.execute(
        """
        CREATE TABLE IF NOT EXISTS settlements (
          id UUID PRIMARY KEY,
          account_id VARCHAR(64) NOT NULL,
          amount NUMERIC(18, 4) NOT NULL,
          status VARCHAR(32) NOT NULL
        );
        """
      )
    } finally {
      conn.close()
    }
  }

  test("Repository harus menyimpan dan membaca SettlementRecord secara deterministik dari database PostgreSQL") {
    withContainers { postgres =>
      runMigrations(postgres)
      
      val acquireConnection = IO.blocking(
        DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password)
      )
      
      val repo = new SettlementRepository(acquireConnection)
      val recordId = UUID.randomUUID()
      val settlement = SettlementRecord(recordId, "ACC-GLOBAL-778", BigDecimal("45000.50"), "PENDING")

      for {
        _         <- repo.insert(settlement)
        retrieved <- repo.findById(recordId)
      } yield {
        assertEquals(retrieved, Some(settlement))
      }
    }
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Testing Frameworks: ScalaTest vs Weaver-Test vs MUnit

| Fitur / Parameter | ScalaTest | Weaver-Test | MUnit |
| :--- | :--- | :--- | :--- |
| **Gaya Desain** | Beragam (*FunSuite, WordSpec, FlatSpec*) | Murni Fungsional, CE/ZIO native | Minimalis, Terfokus, Extensible |
| **Dukungan Scala 3** | Penuh, namun codebase warisan (*macro heavy*) | Dirancang langsung untuk CE3 | Sangat ringan, dibangun untuk Scala 3 |
| **Eksekusi Paralel** | Kompleks dikonfigurasi secara aman | Default parallel per file test | Paralel via runner standard sbt |
| **Cats Effect Native** | Membutuhkan dependensi pihak ketiga | Ya, pengujian adalah `IO[Expectations]` | Ya, via modul `munit-cats-effect` |
| **Kecepatan Kompilasi**| Lambat karena meta-programming masif | Cepat | Sangat Cepat |

### Dependensi Integrasi: Ephemeral Testcontainers vs Embedded In-Memory

| Fitur / Parameter | Testcontainers | Embedded (e.g., H2 / In-Memory Kafka) |
| :--- | :--- | :--- |
| **Fidelitas Produksi** | 100% Identik (Dialek SQL, Concurrency, Locking) | Rendah (Beda Dialek SQL, Beda Semantik Lock) |
| **Startup Overhead** | 3 - 10 Detik per kontainer | < 500 Milidetik |
| **Kebutuhan Host** | Memerlukan Docker Daemon | Hanya memerlukan JVM |
| **Isolasi State** | Sempurna (Jaringan dan Storage terisolasi) | Rawan bocor (*static shared state*) |

### Observabilitas: OpenTelemetry SDK vs Kamon

| Dimensi | OpenTelemetry (OTel) | Kamon |
| :--- | :--- | :--- |
| **Standarisasi** | Standar Industri Global (CNCF) | Proprietary Scala Toolkit |
| **Instrumentasi** | Ekstensif via OTel Java Agent & Manual API | Sangat idiomatis Scala & Akka |
| **Dukungan Multi-bahasa**| Ya, semua platform cloud mendukung | Khusus ekosistem JVM/Scala |
| **Vendor Lock-in** | Tidak ada (dapat dialihkan ke Jaeger/OTLP) | Rendah, namun ekosistem modul terbatas |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Fiber Switching dan Kehilangan Konteks MDC / ThreadLocal:**
   * *Problem:* Logging framework klasik (Logback) menggunakan `MDC` yang berbasis `ThreadLocal`. Saat sebuah komputasi Cats Effect berpindah thread akibat non-blocking I/O (`IO.cede`), *Trace ID* dalam MDC menghilang atau bahkan mengaitkan trace milik request pengguna lain.
   * *Mitigasi:* Gunakan `IOLocal` atau library logging khusus seperti `log4cats` yang dikombinasikan dengan kontekstual fiber, jangan pernah menulis langsung ke `org.slf4j.MDC` di dalam thread pool Cats Effect.
2. **Kelebihan Kapasitas Koneksi (*Connection Starvation*) di Testcontainers:**
   * *Problem:* Test runner yang menjalankan ratusan file test secara paralel memicu spin-up puluhan PostgreSQL container, menghabiskan memori RAM host dan socket port.
   * *Mitigasi:* Gunakan pola *Shared Container* menggunakan objek singleton atau gunakan fitur `reusable(true)` dengan mengaktifkan flag `testcontainers.reuse.enable=true` pada file `~/.testcontainers.properties`.
3. **ScalaCheck Shrinking Hang (Infinite Loop):**
   * *Problem:* Algoritma shrinking bawaan ScalaCheck dapat mengalami loop tak terbatas jika tipe data rekursif memiliki batasan (*constraints*) yang saling bertentangan.
   * *Mitigasi:* Selalu validasi properti menggunakan custom `Shrink` instance yang dibatasi kedalamannya atau nonaktifkan shrinking otomatis untuk model objek yang sangat kompleks.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan `Thread.sleep` untuk Pengujian Asinkron

*Salah:*
```scala
// SALAH: Rawan flaky test dan memblokir worker thread pool!
test("Memeriksa status proses settlement") {
  triggerJob()
  Thread.sleep(3000) // Berharap proses selesai dalam 3 detik
  assertEquals(checkStatus(), "COMPLETED")
}
```

*Benar:*
```scala
// BENAR: Gunakan polling fungsional deterministik dengan timeouts
test("Memeriksa status proses settlement dengan polling") {
  val checkStatusWithRetry: IO[Unit] = {
    checkStatus.flatMap {
      case "COMPLETED" => IO.unit
      case _           => IO.sleep(100.millis) *> checkStatusWithRetry
    }.timeout(5.seconds)
  }

  for {
    _ <- triggerJob
    _ <- checkStatusWithRetry
  } yield ()
}
```

### 2. Mengabaikan Shutdown Lifecycle Resource Testcontainer

*Salah:*
```scala
// SALAH: Meninggalkan koneksi database terbuka yang menyebabkan pool exhaustion
test("Kueri data") {
  val conn = DriverManager.getConnection("jdbc:postgresql:...")
  val res = conn.createStatement().executeQuery("...")
  // Lupa menutup conn dan res
}
```

*Benar:*
```scala
// BENAR: Gunakan abstraksi Resource atau bracket pattern
test("Kueri data dengan isolasi lifecycle") {
  val connResource = Resource.make(
    IO.blocking(DriverManager.getConnection("jdbc:postgresql:..."))
  )(conn => IO.blocking(conn.close()))

  connResource.use { conn =>
    IO.blocking {
      // Eksekusi kueri aman di sini
    }
  }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Pemisahan Test Suite Berdasarkan Beban (*Test Tagging*):**
   Pisahkan tes unit cepat dari tes integrasi lambat pada level build:
   ```scala
   // Di build.sbt
   lazy val IntegrationTest = config("it") extend(Test)
   Defaults.itSettings
   ```
2. **Kompilasi Deterministik:**
   Gunakan flag `-Xfatal-warnings` pada compiler Scala di CI server untuk memastikan tidak ada unhandled pattern match atau deprecated methods yang lolos ke produksi.
3. **Structured Logging Berformat JSON:**
   Di lingkungan containerized (Kubernetes), jangan mencetak log plain text multi-line (seperti stack trace mentah). Gunakan formatter JSON (`logstash-logback-encoder`) agar log engine (FluentBit/Vector) dapat mem-parsing field `trace_id`, `span_id`, dan `severity` secara langsung.
4. **Security Principle of Least Privilege:**
   Jangan pernah mengeksekusi kontainer sebagai user `root` (UID 0). Konfigurasikan `daemonUser` khusus pada Docker plugin dengan UID statis (misal `10001`).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

1. **SBT Layer Caching di Dockerfile Multi-stage:**
   Kunci kecepatan CI/CD adalah caching dependensi JAR. Dependensi Scala jarang berubah dibanding kode bisnis.
   * Strategi: Salin berkas `project/*.sbt` dan `build.sbt` terlebih dahulu, jalankan `sbt update`, baru kemudian salin kode sumber (`src/`) untuk proses kompilasi.
2. **Testcontainers Reuse:**
   Setel `testcontainers.reuse.enable=true` pada workstation developer lokal untuk menghindari instansiasi ulang kontainer basis data yang memakan waktu belasan detik setiap kali perintah `sbt test` dijalankan.
3. **Penyetelan Heap JVM CI Server:**
   Eksekusi kompilasi Scala 3 dan sbt membutuhkan optimasi flag memory:
   ```bash
   export SBT_OPTS="-Xms2048M -Xmx4096M -Xss4M -XX:+UseG1GC"
   ```

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Sanitisasi Log dari Data Sensitif (PII):**
   Sebelum data dipancarkan ke span OpenTelemetry atau file log, terapkan sistem tipe berbasis *Value Classes* atau *Opaque Types* dengan custom representation:
   ```scala
   opaque type CreditCardNumber = String
   object CreditCardNumber {
     def apply(raw: String): CreditCardNumber = raw
     extension (cc: CreditCardNumber) {
       def masked: String = "XXXX-XXXX-XXXX-" + cc.takeRight(4)
     }
   }
   ```
2. **Dependency Vulnerability Scanning:**
   Integrasikan plugin `sbt-dependency-check` ke dalam pipeline untuk memblokir build secara otomatis jika ditemukan CVE dengan skor CVSS > 7.0:
   ```scala
   dependencyCheckFailBuildOnCVSS := 7.0f
   ```
3. **Distroless Container Execution:**
   Gunakan base image *distroless* atau minimal JRE Alpine yang tidak menyertakan package manager (`apk`, `apt`) atau shell binary (`/bin/sh`, `/bin/bash`) untuk meminimalisir attack surface dari remote code execution (RCE).

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Implementasi logging terstruktur yang terikat secara atomik dengan OpenTelemetry Span Context:

```scala
// File: src/main/scala/com/enterprise/telemetry/JsonTracedLogger.scala
package com.enterprise.telemetry

import cats.effect.IO
import org.slf4j.LoggerFactory

class JsonTracedLogger(name: String, traced: Traced[IO]) {
  private val underlying = LoggerFactory.getLogger(name)

  def info(message: String): IO[Unit] = {
    traced.getContext.flatMap { ctx =>
      IO.blocking {
        // Logstash / OpenTelemetry Compatible Log Output
        underlying.info(
          s"""{"message": "$message", "trace_id": "${ctx.traceId}", "span_id": "${ctx.spanId}"}"""
        )
      }
    }
  }
}
```

### Panduan Debugging Kegagalan CI

Jika sebuah integration test gagal di CI lingkungan headless:
1. Aktifkan Testcontainers container logging:
   ```scala
   container.configure { c =>
     c.withLogConsumer(new org.testcontainers.containers.output.Slf4jLogConsumer(logger))
   }
   ```
2. Tangkap Docker events dan alokasi memori kontainer untuk mendeteksi *OOM-Killed (Exit Code 137)* pada runner berkapasitas rendah.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Cheatsheet SBT & Delivery

| Perintah sbt | Deskripsi |
| :--- | :--- |
| `sbt test` | Menjalankan seluruh Unit Test dan Property Tests |
| `sbt "testOnly *AccountSuite"` | Menjalankan satu suite pengujian spesifik |
| `sbt Docker/publishLocal` | Melakukan kompilasi dan membungkus aplikasi ke Docker Daemon lokal |
| `sbt dependencyUpdates` | Memeriksa versi library dependensi yang kedaluwarsa |

### W3C Tracing Header Parsing Matrix

```
Header: traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
                     ^^ -------------------------------- ^--------------- ^^
                  Version             Trace ID               Parent ID     Flags (01 = Sampled)
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic

1. **Apa tujuan utama dari algoritma *Shrinking* pada Property-Based Testing?**
   * A. Mempercepat eksekusi unit test dengan melewati skenario yang redundan.
   * B. Mengurangi penggunaan memori pada JVM saat membangkitkan objek acak.
   * C. Menyusutkan input kompleks yang gagal ke bentuk paling sederhana untuk mempermudah root cause analysis.
   * D. Mengompresi byte code aplikasi sebelum dibungkus ke dalam kontainer.
   *(Kunci: C — Algoritma shrinking bertujuan menyederhanakan input kegagalan ke bentuk paling minimal).*

2. **Mengapa penggunaan `ThreadLocal` biasa berbahaya untuk melacak konteks trace di Cats Effect?**
   * A. Cats Effect melarang penggunaan library eksternal.
   * B. Komputasi fiber dapat berpindah antar thread pool worker secara asinkron sehingga konteks trace menjadi hilang atau tertukar.
   * C. `ThreadLocal` menyebabkan *deadlock* pada runtime Cats Effect.
   * D. `ThreadLocal` secara otomatis mengubah tipe data menjadi mutable.
   *(Kunci: B — Mekanisme cooperative multi-tasking pada fiber runtime membuat keterikatan thread fisik menjadi tidak deterministik).*

3. **Peran kontainer Ryuk dalam Testcontainers adalah:**
   * A. Mengompilasi kode program ke native binary.
   * B. Memastikan kontainer yang dibuat selama sesi tes dibersihkan saat JVM berhenti, meskipun JVM mengalami crash.
   * C. Mengenkripsi kredensial database di dalam lingkungan uji.
   * D. Menangani injeksi ketergantungan (*dependency injection*).
   *(Kunci: B — Ryuk bertugas membersihkan lingering containers/networks).*

4. **Dalam format W3C Trace Context (`traceparent`), berapa panjang karakter heksadesimal untuk field `trace_id`?**
   * A. 16 karakter.
   * B. 64 karakter.
   * C. 32 karakter.
   * D. 128 karakter.
   *(Kunci: C — 32 karakter heksadesimal merepresentasikan 16-byte integer).*

5. **Apa keuntungan utama menjalankan aplikasi kontainer dengan user non-root (misal UID 10001)?**
   * A. Menghindari pembatasan memori dari kernel Linux.
   * B. Membatasi dampak keamanan jika terjadi container breakout atau eksploitasi RCE.
   * C. Menghindari kebutuhan penulisan berkas log ke disk.
   * D. Mempercepat startup time JVM di dalam kontainer.
   *(Kunci: B — Prinsip keamanan *least privilege* membatasi akses ke OS host jika container dikompromikan).*

### Soal Intermediate

6. **Diberikan skenario di mana integration test memicu error `connection refused` secara intermiten pada PostgreSQL Testcontainers. Apa akar masalah yang paling mungkin?**
   * A. Port database di-hardcode ke `5432` di dalam suite pengujian alih-alih mengambil alokasi dynamic mapped port dari container.
   * B. Eksekusi pengujian kekurangan heap space JVM.
   * C. ScalaCheck gagal menyusutkan data transaksi.
   * D. Pengujian dijalankan di dalam container tanpa hak akses sudo.
   *(Kunci: A — Testcontainers memetakan port secara dinamis untuk mencegah port collision antar tes).*

7. **Kapan teknik Property-Based Testing LEBIH UNGGUL daripada pengujian Example-Based konvensional?**
   * A. Ketika menguji tampilan visual UI.
   * B. Ketika menguji serialization/deserialization aljabar dan batasan invarian matematis.
   * C. Ketika hanya ada satu kemungkinan nilai kembalian dari fungsi.
   * D. Ketika menguji konfigurasi file YAML statis.
   *(Kunci: B — Domain yang memiliki sifat simetri dan invarian matematis sangat optimal divalidasi dengan ribuan kombinasi input PBT).*

8. **Bagaimana cara mengisolasi transaksi database per-test case menggunakan Flyway dan Testcontainers tanpa membuat kontainer baru setiap kali test dieksekusi?**
   * A. Menghentikan Docker daemon di antara setiap test case.
   * B. Menjalankan `flyway.clean()` diikuti `flyway.migrate()` di dalam lifecycle `beforeEach` atau menggunakan rollbacked nested transactions.
   * C. Menghapus tabel secara manual menggunakan truncate script non-transaksional.
   * D. Melakukan restart pada sbt session.
   *(Kunci: B — Membersihkan skema atau merollback transaksi mempertahankan efisiensi runtime tanpa spin-up kontainer baru).*

9. **Apa konsekuensi dari tidak mendefinisikan flag `-XX:+UseContainerSupport` pada JVM versi lama di dalam container environment?**
   * A. JVM akan crash seketika saat membaca instruksi Scala 3.
   * B. JVM akan membaca memori dan CPU total dari host node fisik, bukan limit resource cgroups container, yang dapat memicu *OOMKilled*.
   * C. Container tidak dapat mengekspos port jaringan keluar.
   * D. OpenTelemetry SDK akan menolak mengirimkan trace data.
   *(Kunci: B — Container support memastikan JVM mematuhi batasan kuota memori/core yang diatur oleh cgroups kontainer).*

10. **Dalam implementasi Cats Effect, jika sebuah trace span dibuat namun terjadi unhandled exception di dalam fiber, konstruksi apa yang menjamin span tersebut tetap ditutup (`span.end()`)?**
    * A. `IO.pure`
    * B. `IO.guarantee` atau `Resource.make`
    * C. `IO.async_`
    * D. `IO.race`
    *(Kunci: B — `guarantee` dan `Resource` menyediakan garansi pembersihan resource meskipun komputasi dibatalkan atau berakhir error).*

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek: "Resilient Ledger Delivery Harness"

Bangun pipeline pengujian integrasi dan observabilitas menyeluruh untuk subsistem **Buku Besar Finansial (Financial Ledger)**:

#### Spesifikasi Fungsional:
1. **Model Domain & Property Testing:**
   * Buat domain model `JournalEntry` (Debit dan Kredit).
   * Gunakan **ScalaCheck** untuk membuktikan bahwa untuk seluruh variasi transaksi acak, invarian dasar double-entry bookkeeping selalu terpenuhi:
     $$\sum \text{Debit} - \sum \text{Kredit} = 0$$
2. **Integration Test Suite dengan Testcontainers:**
   * Jalankan PostgreSQL Container secara otomatis menggunakan `Testcontainers-scala`.
   * Eksekusi migrasi skema tabel `ledger_entries` dengan Flyway.
   * Buat class `LedgerRepository` yang mengimplementasikan operasi penyimpanan dan pembacaan menggunakan Cats Effect `IO`.
   * Buktikan ketahanan konkurensi: Gunakan `parTraverse` dari Cats Effect untuk mengeksekusi 50 transaksi secara konkuren ke database dan verifikasi integritas saldonya.
3. **Observability Pipeline:**
   * Bungkus pemanggilan database di dalam span OpenTelemetry bertajuk `ledger.persist`.
   * Catat metrik durasi query ke dalam Prometheus registry tiruan / trace exporter in-memory.
   * Pastikan TraceContext tidak hilang di antara operasi konkuren `parTraverse`.
4. **CI/CD Deployment Artifact:**
   * Tuliskan konfigurasi plugin `sbt-native-packager` yang memproduksi minimal container image berbasis `alpine` non-root.
   * Tulis berkas shell script `/scripts/run-ci.sh` yang menjalankan:
     1. Analisis statis dan pengecekan pemformatan.
     2. Eksekusi seluruh pengujian.
     3. Pembuatan Docker image secara lokal dan verifikasi bahwa image tersebut dapat di-*spin-up* dan merespon endpoint `/healthz`.

#### Kriteria Keberhasilan:
* Tidak ada pengujian flaky; 100% test lulus pada lingkungan bersih (clean runner).
* Tidak ada hardcoded credentials atau IP address (seluruh koneksi dinamis dari Testcontainers).
* Image kontainer yang dihasilkan berukuran < 250 MB dan berjalan di bawah UID non-root.