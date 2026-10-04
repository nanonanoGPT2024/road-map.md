# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**BAB 10: PENGUJIAN ENTERPRISE, OBSERVABILITAS & DELIVERY**
**Topik: Scala Enterprise Ecosystem (Cats Effect 3, Otel4s, Testcontainers, GraalVM)**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur observabilitas terdistribusi (*distributed tracing*, *structured metrics*, dan *contextual logging*) berbasis W3C Trace Context pada runtime asynchronous functional (Cats Effect 3 / ZIO 2) tanpa kehilangan konteks saat fiber switching.
- Mengembangkan test harness otomatis terisolasi (*end-to-end integration testing*) menggunakan Testcontainers-Scala untuk PostgreSQL dan Apache Kafka dengan optimasi lifecycle container dan reuse pattern.
- Mengisolasi dan memitigasi isu *high cardinality metrics* dan *allocation overhead* pada JVM runtime skala tinggi.
- Membangun pipeline delivery kontainer enterprise berbasis *Multi-Stage Dockerfile* dan *GraalVM Native Image* dengan optimasi footprint memori (< 64MB RSS) serta startup time (< 50ms).

---

## 2. Prerequisite
- Pemahaman mendalam mengenai Cats Effect 3 runtime (`IO`, `Fiber`, `Resource`, `IOLocal`) atau ZIO 2 (`ZIO`, `FiberRef`).
- Pemahaman dasar Docker engine, network bridging, dan container lifecycle.
- Pemahaman protokol W3C Trace Context (`traceparent`, `tracestate`) dan arsitektur OpenTelemetry (Collector, Exporter, SDK).
- Penguasaan build tool `sbt` (multi-module project, dependency management, compiler plugin settings).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Masalah ThreadLocal vs. Asynchronous Fibers
Dalam arsitektur Java/JVM enterprise tradisional, context propagation (seperti MDC pada Logback dan OpenTelemetry `ThreadLocalScopeTracker`) mengandalkan `java.lang.ThreadLocal`. Ketika thread mengeksekusi request, context ID (misal `trace_id`) ditempelkan pada thread tersebut.

Pada functional asynchronous runtime seperti Cats Effect atau ZIO, eksekusi kode dibagi menjadi ratusan ribu unit komputasi ringan (*fibers*) yang dijadwalkan secara *cooperative multi-tasking* di atas thread pool berukuran kecil (biasanya seukuran `Runtime.getRuntime().availableProcessors()`). Sebuah fiber dapat memulai komputasi di `Thread-A`, melakukan operasi I/O asinkron, tersuspensi, dan melanjutkan eksekusi di `Thread-B`. 

```
Java ThreadLocal Model:
[Request 1] ---> (Thread-A: Trace-1) ------------------------> Selesai

Cats Effect / Fiber Model:
[Fiber 1] -----> (Thread-A) --[I/O Wait]--> (Thread-B) ------> Selesai
Context Hilang jika bergantung pada ThreadLocal!
```

Solusi enterprise murni membutuhkan abstraksi context carrier yang terikat pada siklus hidup fiber, yaitu `IOLocal` (Cats Effect) atau `FiberRef` (ZIO). Abstraksi ini menyalin context frame saat fiber di-*fork* dan menggabungkan modifikasi context saat fiber di-*join*.

### 3.2 Arsitektur OpenTelemetry Pure-FP (`otel4s`)
Library seperti `otel4s` mengintegrasikan OpenTelemetry API/SDK secara native ke dalam cats-effect type classes:
- Context disimpan di dalam immutable environment state (`cats.mtl.Local` atau `IOLocal`).
- Pembuatan span membungkus eksekusi `IO[A]` ke dalam bracket resource pattern:
  1. Buat span (`start`).
  2. Bawa span context ke child fibers via `IOLocal`.
  3. Tangkap status keberhasilan/kegagalan (*case of error: set span error status & record exception*).
  4. Tutup span (`end`).

### 3.3 Testcontainers Internals & Lifecycle Management
Testcontainers-Scala mengotomatisasi pengujian integrasi dengan berbicara langsung ke Docker daemon melalui Unix Domain Socket (`/var/run/docker.sock`) atau Windows named pipe via Java Docker Client (Docker-Java).

```
+----------------------------------------------------------------------+
|                           SBT Test Runner                            |
|  +----------------------------------------------------------------+  |
|  | Spec / Test Suite (ScalaTest / MUnit)                          |  |
|  |  - Starts PostgreSQLContainer & KafkaContainer                  |  |
|  |  - Mapped Dynamic Ports (e.g. 5432 -> 32789)                   |  |
|  |  - Injects dynamic JDBC URL to Typelevel Resource Pool          |  |
|  +----------------------------------------------------------------+  |
+-----------------------------------|----------------------------------+
                                    | Docker API (TCP/Socket)
                                    v
+----------------------------------------------------------------------+
|                            Docker Daemon                             |
|  +-------------------------+      +-------------------------------+  |
|  | Ryuk (Resource Reaper)  |      | testcontainers/postgresql     |  |
|  | Cleans up on JVM abort  |      | Dynamic bridge network        |  |
|  +-------------------------+      +-------------------------------+  |
+----------------------------------------------------------------------+
```

Fitur kritikal:
- **Ryuk Container**: Kontainer sidecar yang dijalankan Testcontainers untuk memastikan semua kontainer database/broker yang dibuat akan dimusnahkan secara paksa jika JVM crash atau sbt di-terminate secara abnormal.
- **Port Mapping Arbitrasi**: Testcontainers mengabaikan host port statis untuk mencegah konflik port di CI environment, memetakan exposed port container ke random unassigned dynamic port di host.

---

## 4. Why & What

| Dimensi | Mengapa Dibutuhkan? | Apa Implikasinya jika Gagal Diimplementasikan? |
| :--- | :--- | :--- |
| **Fiber-safe Tracing** | Menjamin log dan trace terdistribusi merefleksikan alur transaksi riil lintas microservice. | Logging MDC menjadi korup; trace ID tertukar antar transaksi nasabah berbeda yang dieksekusi pada worker thread yang sama. |
| **Testcontainers** | Menyediakan pengujian deterministik terhadap dependency riil (PostgreSQL engine, Kafka partitions). | *H2 in-memory illusion*: SQL query lolos di H2 saat unit test, namun meledak di produksi karena perbedaan dialek, locking behavior, dan JSON syntax. |
| **Metric Cardinality Control** | Mengukur performa (latency histogram, throughput) tanpa membebani collector. | Out-Of-Memory (OOM) pada Prometheus/Grafana Mimir karena penambahan dynamic parameter (misal `user_id` atau `order_id`) sebagai label metric. |
| **GraalVM Native Image** | Meminimalisasi memory footprint dan meniadakan cold-start di Kubernetes (HPA / Serverless). | Latensi P99 spiking hingga 5-10 detik saat autoscaling pod baru di-spin up akibat JIT warm-up dan classloading overhead. |

---

## 5. How (Workflow Detail)

### Alur Observabilitas Request Masuk hingga Export
1. **Ingress Extraction**: HTTP Server (Http4s) menerima HTTP request, mengambil header `traceparent` via W3C Propagator.
2. **Context Injection**: Header dikonversi menjadi `SpanContext` dan disimpan ke dalam fiber context (`IOLocal`).
3. **Execution & Child Spans**: Lapisan Service dan Database (Doobie / Skunk) membuat child span menggunakan kombinasi cats-effect resource syntax.
4. **Structured Logging**: Logback/SLF4J dikombinasikan dengan correlation provider yang membaca tracing context dari fiber untuk menempelkan `trace_id` dan `span_id` pada setiap output JSON.
5. **Metric Recording**: Menghitung bucket latensi (`Histogram`) dan throughput (`Counter`) menggunakan Otel4s Metric API.
6. **Egress Propagation**: Client downstream menyuntikkan current trace context ke HTTP request headers/Kafka record headers berikutnya.

---

## 6. Analogy & Diagram ASCII

### Analogi: Konvoi Truk Ekspedisi vs. Papan Nama Supir
- **Tradisional (ThreadLocal)**: Bagaikan menempelkan nama supir pada truk tertentu. Selama supir itu mengendarai truk itu terus, barang aman. Namun di functional async runtime, barang dipindah-pindah antar supir secara estafet dalam hitungan milidetik. Jika nama supir pertama ditempel di truk, penerima paket akan membaca identitas yang salah.
- **Fiber-Safe (IOLocal)**: Dokumen jalan (manifest) ditempelkan langsung pada **paket barangnya** (Fiber context). Siapa pun supir yang memindahkan paket tersebut di rest-area (thread pool), manifest bawaan paket tersebut selalu akurat.

```
Distributed Trace & Metric Flow (Pure Functional Architecture):

  [HTTP Request with W3C Header]
                 |
                 v
   +---------------------------+
   | Http4s Ingress Middleware | ---> Injeksi SpanContext ke IOLocal
   +---------------------------+
                 |
                 +-------------------------------------------------------+
                 |                                                       |
                 v                                                       v
   +---------------------------+                           +---------------------------+
   | Business Service (Fiber)  |                           | SLF4J / Logback Appender  |
   | - Child Span: "processTx" |                           | - Tarik TraceId dr Fiber  |
   +---------------------------+                           | - Output: JSON Structured |
                 |                                         +---------------------------+
                 v                                                       |
   +---------------------------+                                         v
   | Database Layer (Skunk)    |                                 [FluentBit / Vector]
   | - Child Span: "sql:insert"|                                         |
   +---------------------------+                                         v
                 |                                                 [Elastic/Loki]
                 v
   +---------------------------+
   | Otel BatchSpanProcessor   | ---> Protobuf via gRPC ---> [Otel Collector]
   +---------------------------+                                   |
                                                    +--------------+--------------+
                                                    |                             |
                                                    v                             v
                                            [Jaeger / Tempo]             [Prometheus / Mimir]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Dynamic Lifecycle Testcontainers-Scala
Contoh setup integrasi pengujian suite dengan PostgreSQL Testcontainers.

```scala
// File: src/test/scala/com/enterprise/test/PostgresContainerSpec.scala
package com.enterprise.test

import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.matchers.should.Matchers
import com.dimafeng.testcontainers.scalatest.TestContainerForAll
import com.dimafeng.testcontainers.PostgreSQLContainer
import java.sql.DriverManager

class PostgresContainerSpec extends AnyFunSuite with Matchers with TestContainerForAll {

  override val containerDef: PostgreSQLContainer.Def = PostgreSQLContainer.Def(
    dockerImageName = "postgres:16-alpine",
    databaseName = "enterprise_test_db",
    username = "app_user",
    password = "secret_password"
  )

  test("Container harus terpasang dan melayani query database sederhana") {
    withContainers { postgres =>
      val connection = DriverManager.getConnection(
        postgres.jdbcUrl,
        postgres.username,
        postgres.password
      )
      try {
        val statement = connection.createStatement()
        val resultSet = statement.executeQuery("SELECT 1 AS alive_flag")
        resultSet.next() shouldBe true
        resultSet.getInt("alive_flag") shouldBe 1
      } finally {
        connection.close()
      }
    }
  }
}
```

### 7.2 Practical Example: Enterprise Observability with Cats Effect 3 & Otel4s
Kode produksi mengombinasikan tracing context propagation, histogram metrik, dan structured logging.

```scala
// File: src/main/scala/com/enterprise/telemetry/PaymentService.scala
package com.enterprise.telemetry

import cats.effect.{IO, IOApp, ExitCode}
import cats.syntax.all.*
import org.typelevel.otel4s.trace.Tracer
import org.typelevel.otel4s.metrics.Meter
import org.typelevel.otel4s.Attribute
import org.typelevel.otel4s.OtelJava
import io.opentelemetry.api.GlobalOpenTelemetry
import java.util.UUID
import scala.concurrent.duration.*

case class PaymentRequest(paymentId: UUID, accountId: String, amount: BigDecimal)
case class PaymentResponse(paymentId: UUID, status: String, approvalCode: String)

trait PaymentService[F[_]] {
  def processPayment(req: PaymentRequest): F[PaymentResponse]
}

class InstrumentedPaymentService(
    tracer: Tracer[IO],
    meter: Meter[IO]
) extends PaymentService[IO] {

  // Metrik inisialisasi: Histogram latensi transaksi dan Counter total eksekusi
  private val latencyHistogram = meter
    .histogram[Double]("payment.processing.duration.seconds")
    .withDescription("Durasi pemrosesan pembayaran")
    .withUnit("s")
    .create

  private val totalCounter = meter
    .counter[Long]("payment.requests.total")
    .withDescription("Total request pembayaran masuk")
    .create

  override def processPayment(req: PaymentRequest): IO[PaymentResponse] = {
    tracer.span("processPayment").use { span =>
      for {
        _ <- span.addAttributes(
          Attribute("payment.id", req.paymentId.toString),
          Attribute("account.id", req.accountId),
          Attribute("payment.amount", req.amount.toDouble)
        )
        _ <- totalCounter.flatMap(_.inc(Attribute("account.tier", "enterprise")))
        startTime <- IO.realTime
        
        // Simulasi dependensi eksternal (Core Banking Engine)
        response <- executeExternalCall(req).handleErrorWith { ex =>
          span.recordException(ex) >>
            IO.raiseError(new RuntimeException(s"Payment processing failed: ${ex.getMessage}"))
        }
        
        endTime <- IO.realTime
        duration = (endTime - startTime).toMillis.toDouble / 1000.0
        _ <- latencyHistogram.flatMap(_.record(duration, Attribute("status", "SUCCESS")))
      } yield response
    }
  }

  private def executeExternalCall(req: PaymentRequest): IO[PaymentResponse] = {
    tracer.span("callCoreBankingEngine").use { innerSpan =>
      for {
        _ <- innerSpan.addAttribute(Attribute("engine.endpoint", "grpc://engine.internal:9090"))
        // Simulasi jeda I/O network
        _ <- IO.sleep(35.millis)
        approvalCode = UUID.randomUUID().toString.take(8).toUpperCase
      } yield PaymentResponse(req.paymentId, "APPROVED", approvalCode)
    }
  }
}

object ProductionApp extends IOApp {
  override def run(args: List[String]): IO[ExitCode] = {
    // Inisialisasi Otel Java SDK Wrapper ke Otel4s
    val otel = OtelJava.forTracerProvider[IO](GlobalOpenTelemetry.getTracerProvider)
    
    for {
      tracer <- otel.tracerProvider.get("com.enterprise.billing")
      meter  <- OtelJava.forMeterProvider[IO](GlobalOpenTelemetry.getMeterProvider).meterProvider.get("com.enterprise.billing")
      service = new InstrumentedPaymentService(tracer, meter)
      
      request = PaymentRequest(UUID.randomUUID(), "ACC-INDONESIA-001", BigDecimal("75000000.00"))
      res <- service.processPayment(request)
      _   <- IO.println(s"Payment Execution Result: $res")
    } yield ExitCode.Success
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Payment Settlement Engine (High Throughput, Strict SLA)
- **Karakteristik Beban**: 40.000 TPS, latensi p99 < 15ms.
- **Masalah Awal**:
  1. Penggunaan standard Java agent (`-javaagent:opentelemetry-javaagent.jar`) menambahkan GC pressure ekstrem (heap churn naik 400%) akibat alokasi dynamic dynamic bytecode injection pada cats-effect run loop.
  2. Prometheus scraper mengalami *out-of-memory crash* setiap 4 jam karena engineer memasukkan `merchant_transaction_id` sebagai tag metrik (*metric explosion* dengan jutaan unique label pairs).
  3. Logback MDC kehilangan korelasi trace context saat HTTP service mendispatch database write asinkron di thread worker berbeda.

### Solusi Arsitektural:
1. **Pembersihan Agent**: Menghapus runtime bytecode instrumentation, menggantinya dengan pure functional explicit tracing via `otel4s` dan compile-time tracing macro.
2. **Kardinalitas Terkendali**: Standarisasi policy metrik:
   - Tag diperbolehkan hanya yang bernilai diskrit terbatas (*finite enum values*): `bank_code` (BCA, MANDIRI, BRI), `status` (SUCCESS, REJECTED), `error_code` (ERR_INSUFFICIENT_FUNDS, ERR_TIMEOUT).
   - Seluruh identifier unik (`payment_id`, `card_pan`, `session_id`) dilarang masuk ke metric system; hanya diperbolehkan masuk ke OpenTelemetry Trace Spans dan JSON Log Attributes.
3. **Penyelarasan Tracing Context**: Mengikat W3C context propagator ke Cats Effect `IOLocal`, lalu mengalirkan header secara otomatis via client middleware (`org.http4s.client.middleware.Metrics`).
4. **Hasil**:
   - Heap footprint turun dari 12 GB menjadi 3.5 GB pada beban yang sama.
   - P99 latency terpangkas dari 65ms (efek JIT/agent reflection overhead) menjadi 9.2ms.
   - 100% trace visibility tercapai tanpa trace-loss antar fiber hops.

---

## 9. Trade-offs

| Pendekatan | Kelebihan | Kelemahan | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Java Agent Instrumentation** | Zero-code modification, instan diaktifkan via JVM args. | Alokasi obyek tinggi, GC pause tinggi, overhead pada fiber runloop, rawan bocor context di async boundary. | Legacy non-FP applications atau transisi awal monitoring tanpa modifikasi codebase. |
| **Pure FP SDK (`otel4s`)** | Zero reflection, memory-efficient, deterministic lifecycle, fiber context propagation 100% aman. | Memerlukan modifikasi kode eksplisit, pemahaman kuat terhadap functional stack (`cats-effect`). | Greenfield FP services, high-throughput microservices, latency-critical apps. |
| **H2 In-Memory DB Testing** | Sangat cepat, hemat resource CI/CD machine, tidak butuh Docker daemon. | Dialek SQL tidak identik, tidak mendukung locking postgres riil, melewatkan bug konkurensi database level. | Validasi logic repository murni non-SQL-dependent, simple unit testing. |
| **Testcontainers-Scala** | 100% parity dengan database produksi, isolasi data sempurna antar build. | Startup overhead kontainer (5-15 detik), butuh Docker daemon di CI worker, konsumsi RAM besar. | Enterprise integration tests, validasi migration scripts (Flyway/Liquibase), E2E. |
| **GraalVM Native Image** | Cold start < 20ms, RSS memory konsisten < 64MB, image Docker sangat kecil. | Compile time sangat lama (5-15 menit), keterbatasan dynamic class loading & reflection config rumit. | Kubernetes scale-to-zero (Knative/Serverless), CLI tools, short-lived event processing. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 High Cardinality Metric Leakage
- **Gejala**: Memory usage pada Prometheus/Promscale/Mimir melesat naik hingga OOM; query Grafana timeout.
- **Akar Masalah**:
  ```scala
  // ERROR FATAL: Menyertakan dynamic payload ID ke label metrik!
  counter.inc(Attribute("invoice.id", req.invoiceId.toString)) 
  ```
- **Solusi**: Hanya gunakan atribut kategorikal berhingga (*low cardinality*):
  ```scala
  // BENAR: Menggunakan status pembayaran atau channel
  counter.inc(Attribute("payment.method", req.paymentMethod.name))
  ```

### 10.2 Tracing Loss pada Cats Effect Fiber Boundary
- **Gejala**: Log menunjukkan `trace_id: ""` atau `trace_id: 0000000000000000` di tengah flow yang melibatkan `IO.both` atau `.start`.
- **Akar Masalah**: Mengandalkan MDC logger Java native tanpa bridging ke `IOLocal`.
- **Solusi**: Gunakan library functional logging seperti `log4cats` yang dikombinasikan dengan fiber-aware context provider:
  ```scala
  // Integrasikan MDC dengan IOLocal provider
  implicit val logger: StructuredLogger[IO] = Slf4jLogger.getLoggerFromContext[IO]
  ```

### 10.3 Port Contention & Zombie Containers di CI Pipeline
- **Gejala**: Build CI gagal dengan error `Bind for 0.0.0.0:5432 failed: port is already allocated` atau disk runner habis.
- **Akar Masalah**: Hardcoded port binding pada container test setup, atau mematikan Ryuk reaper container via environment variable `TESTCONTAINERS_RYUK_DISABLED=true`.
- **Solusi**: Jangan pernah binding port ke host port statis. Selalu baca dynamic assigned port via `container.mappedPort(5432)`. Pastikan Ryuk container diizinkan berjalan untuk membersihkan kontainer saat agent CI di-cancel.

---

## 11. Best Practices (Production Checklist)

- [ ] **Deterministic Testing**: Menggunakan Testcontainers dengan pinning versi spesifik (contoh: `postgres:16.2-alpine`, bukan `postgres:latest`).
- [ ] **Health & Readiness Endpoints**: Menyediakan dual health check:
  - `/health/liveness`: Cek internal JVM thread-deadlock, return 200 selama process berjalan.
  - `/health/readiness`: Cek konektivitas riil ke PostgreSQL pool dan Kafka broker (timeout 1 detik).
- [ ] **Resource Limits (K8s)**: Menyetel memory limits dengan headroom GC yang tepat:
  - `JVM -XX:MaxRAMPercentage=75.0`
  - Sisakan 25% memory pod untuk overhead off-heap, JVM native memory, dan thread stacks.
- [ ] **Context Propagation Egress**: Pastikan downstream HTTP/Kafka client selalu disuntikkan trace context melalui middleware (W3C standard).
- [ ] **Sanitized Logging**: Pastikan parameter PII (Personally Identifiable Information) seperti nomor kartu kredit, password, atau balance tidak masuk ke attribute span tracing ataupun log payload.
- [ ] **Multi-stage Distroless Containers**: Menghindari base image Linux penuh. Gunakan `gcr.io/distroless/java17-debian12` atau `distroless/static-debian12` (untuk native binaries) guna mereduksi CVE security scanner alert.

---

## 12. Hands-on Practice

Buatlah sistem verifikasi terintegrasi di direktori: `hands-on/m02/`

### File Structure:
```
hands-on/m02/
├── build.sbt
├── project/
│   └── plugins.sbt
└── src/
    ├── main/
    │   └── scala/
    │       └── com/enterprise/delivery/
    │           └── AccountRepository.scala
    └── test/
        └── scala/
            └── com/enterprise/delivery/
                └── AccountRepositoryITSpec.scala
```

### 1. `project/plugins.sbt`
```scala
addSbtPlugin("io.spray" % "sbt-revolver" % "0.10.0")
addSbtPlugin("com.github.sbt" % "sbt-native-packager" % "1.9.16")
```

### 2. `build.sbt`
```scala
ThisBuild / scalaVersion := "3.3.3"
ThisBuild / organization := "com.enterprise"

lazy val root = (project in file("."))
  .settings(
    name := "enterprise-testing-telemetry",
    libraryDependencies ++= Seq(
      "org.typelevel" %% "cats-effect" % "3.5.4",
      "org.postgresql" % "postgresql" % "42.7.2",
      "org.scalatest" %% "scalatest" % "3.2.18" % Test,
      "com.dimafeng" %% "testcontainers-scala-scalatest" % "0.41.3" % Test,
      "com.dimafeng" %% "testcontainers-scala-postgresql" % "0.41.3" % Test
    )
  )
```

### 3. `src/main/scala/com/enterprise/delivery/AccountRepository.scala`
```scala
package com.enterprise.delivery

import java.sql.Connection
import scala.util.Using

case class Account(id: String, balance: BigDecimal, status: String)

class AccountRepository {

  def initSchema(implicit conn: Connection): Unit = {
    Using.resource(conn.createStatement()) { stmt =>
      stmt.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
          id VARCHAR(64) PRIMARY KEY,
          balance NUMERIC(18, 4) NOT NULL,
          status VARCHAR(16) NOT NULL
        );
        """
      )
    }
  }

  def upsert(acc: Account)(implicit conn: Connection): Unit = {
    val sql = 
      """
      INSERT INTO accounts (id, balance, status)
      VALUES (?, ?, ?)
      ON CONFLICT (id) DO UPDATE SET
        balance = EXCLUDED.balance,
        status = EXCLUDED.status;
      """
    Using.resource(conn.prepareStatement(sql)) { ps =>
      ps.setString(1, acc.id)
      ps.setBigDecimal(2, acc.balance.bigDecimal)
      ps.setString(3, acc.status)
      ps.executeUpdate()
    }
  }

  def findById(id: String)(implicit conn: Connection): Option[Account] = {
    val sql = "SELECT id, balance, status FROM accounts WHERE id = ?"
    Using.resource(conn.prepareStatement(sql)) { ps =>
      ps.setString(1, id)
      Using.resource(ps.executeQuery()) { rs =>
        if (rs.next()) {
          Some(Account(
            rs.getString("id"),
            rs.getBigDecimal("balance"),
            rs.getString("status")
          ))
        } else None
      }
    }
  }
}
```

### 4. `src/test/scala/com/enterprise/delivery/AccountRepositoryITSpec.scala`
```scala
package com.enterprise.delivery

import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.matchers.should.Matchers
import com.dimafeng.testcontainers.scalatest.TestContainerForAll
import com.dimafeng.testcontainers.PostgreSQLContainer
import java.sql.DriverManager

class AccountRepositoryITSpec extends AnyFunSuite with Matchers with TestContainerForAll {

  override val containerDef: PostgreSQLContainer.Def = PostgreSQLContainer.Def(
    dockerImageName = "postgres:16-alpine"
  )

  test("Menyimpan dan membaca Account secara akurat dari container Postgres") {
    withContainers { postgres =>
      implicit val conn = DriverManager.getConnection(
        postgres.jdbcUrl,
        postgres.username,
        postgres.password
      )

      try {
        val repo = new AccountRepository()
        repo.initSchema

        val accountId = "ACC-ID-999"
        val newAccount = Account(accountId, BigDecimal("1250000.5000"), "ACTIVE")

        repo.upsert(newAccount)

        val retrieved = repo.findById(accountId)
        retrieved shouldBe defined
        retrieved.get.id shouldBe accountId
        retrieved.get.balance shouldBe BigDecimal("1250000.5000")
        retrieved.get.status shouldBe "ACTIVE"

      } finally {
        conn.close()
      }
    }
  }
}
```

### Eksekusi:
```bash
sbt test
```

---

## 13. Exercise

### Level Easy
Tambahkan migration method pada `AccountRepository` yang mengubah kolom `status` menjadi `VARCHAR(32)` dan tambahkan integration test untuk menguji proses alter table tersebut pada PostgreSQL container berjalan.

### Level Medium
Buat sebuah implementasi `FiberTraceContext` berbasis `cats.effect.IOLocal` yang menyimpan W3C `traceparent` (string), lalu buat dua parallel fibers (`IO.both`) dan buktikan melalui unit test bahwa kedua fiber turunan tersebut mewarisi `traceparent` yang identik dari parent fiber.

### Level Hard
Implementasikan custom Otel `SpanExporter` in-memory yang mengumpulkan seluruh span latency, lalu gunakan untuk memverifikasi bahwa query lambat (simulasi via `pg_sleep(1)`) secara akurat mencatat span dengan atribut `app.slow_query = true` jika eksekusi melebihi threshold 500ms.

---

## 14. Challenge

**Skenario**: Sistem Core-Banking Ledger berskala 50.000 TPS mengalami *split-brain context logging* dan degradasi latensi tinggi setiap kali Kafka producer down.

**Tugas Arsitektur**:
1. Rancang arsitektur pipeline telemetry non-blocking menggunakan Cats Effect 3, FS2 (Functional Streams for Scala), dan OpenTelemetry OTLP Exporter.
2. Mekanisme telemetry harus memiliki *in-memory circular ring buffer* (maksimal alokasi RAM 128MB). Jika buffer penuh akibat backend collector lambat, telemetry harus melakukan *graceful dropping* dengan menghitung drop-counter tanpa pernah memblokir thread eksekusi perbankan utama.
3. Buat skema konfigurasi Kubernetes Pod spec yang mengombinasikan JVM cgroup memory tuning (`-XX:MaxRAMPercentage`), probe liveness/readiness, serta Otel Sidecar DaemonSet agent.
4. Tuliskan analisis teoritis dan failure-mode recovery plan jika network segment ke OTLP gRPC endpoint terputus selama 10 menit.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Mengapa `ThreadLocal` rentan mengalami desinkronisasi konteks saat digunakan di functional async runtime seperti Cats Effect atau ZIO?
2. Apa fungsi kontainer `Ryuk` yang di-spin up secara otomatis oleh framework Testcontainers?
3. Sebutkan dua header utama yang didefinisikan dalam spesifikasi standar W3C Trace Context!
4. Mengapa kita tidak boleh membinding host port kontainer secara statis (misal: `-p 5432:5432`) di continuous integration (CI) environment?
5. Apa perbedaan fundamental antara metric bertipe `Counter` dan `Histogram`?

### 5 Pertanyaan Intermediate
1. Bagaimana cara `IOLocal` menangani propagasi konteks saat sebuah fiber melakukan branching via parallel evaluation (`IO.parSequence` / `parTraverse`)?
2. Jelaskan bahaya arsitektural dari fenomena *Metric Cardinality Explosion* terhadap sistem time-series database seperti Prometheus!
3. Mengapa integrasi tracing via Java Agent bytecode instrumentation sering kali menghasilkan performa lebih buruk dibanding Pure FP manual instrumenting pada Typelevel stack?
4. Apa peran `testcontainers.reuse.enable=true` dalam mempercepat feedback cycle pengujian lokal dan bagaimana implikasinya terhadap state leakage?
5. Bagaimana cara memvalidasi bahwa trace ID yang dihasilkan oleh Ingress Gateway diteruskan secara aman ke outgoing downstream HTTP call?

### 3 Skenario Kasus Produksi
1. **Kasus 1**: Setelah rilis versi baru, pod Kubernetes Anda mengalami OOMKilled secara acak. Log analyzer menunjukkan tracing agent membuat jutaan object `SpanContext` per detik saat terjadi database retry loop. Langkah isolasi dan patch apa yang harus dipasang?
2. **Kasus 2**: Unit test Anda lolos 100% menggunakan H2 In-Memory DB. Namun ketika diuji via Testcontainers PostgreSQL, terjadi error `PSQLException: ERROR: current transaction is aborted, commands ignored until end of transaction block`. Jelaskan penyebab arsitektural perbedaan perilaku ini!
3. **Kasus 3**: Tim DevOps menuntut pemangkasan startup time aplikasi dari 12 detik menjadi di bawah 100ms untuk mendukung auto-scaling Kubernetes HPA saat flash-sale. Analisis trade-off yang harus dihadapi jika aplikasi Scala Cats-Effect tersebut dikompilasi menjadi GraalVM Native Image!

---

## 16. Summary

- **Observabilitas Functional**: Membutuhkan mekanisme context propagation berbasis fiber (`IOLocal` / `FiberRef`). Konsep imperatif berbasis `ThreadLocal` tidak aman dan merusak jejak telemetri.
- **Enterprise Testing Parity**: Uji integrasi harus mencerminkan kondisi riil database engine menggunakan Testcontainers. Hindari in-memory emulation jika menguji fitur konkurensi, ACID locking, dan query kompleks.
- **Metric Discipline**: Pisahkan secara tegas antara data metrik (kardinalitas rendah, agregasi performa) dan data trace/log (kardinalitas tinggi, detail transaksional).
- **Delivery Efisien**: Pilihan antara standard JVM runtime (throughput maksimal jangka panjang) dan GraalVM Native Image (startup instan, footprint memori ultra-rendah) harus didasarkan pada SLA beban dan pola autoscaling sistem produksi.