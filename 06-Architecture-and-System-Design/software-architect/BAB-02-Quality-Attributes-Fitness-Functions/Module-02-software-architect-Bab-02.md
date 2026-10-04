# Module 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Quality Attributes & Architectural Fitness Functions**  
**Topik: Software Architect | Kategori: 06-Architecture-and-System-Design**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengukur** Quality Attribute Requirements (QARs) menggunakan skenario terukur (*System Quality Attribute Scenarios*) berbasis standar ISO/IEC 25010.
- **Merancang & Mengimplementasikan** *Automated Architectural Fitness Functions* (AFF) untuk mendeteksi *architectural drift* dan *bit rot* pada pipeline CI/CD.
- **Mengembangkan** pengujian struktur arsitektur statis (*Static Code-Level Fitness Function*) menggunakan engine berbasis *Abstract Syntax Tree* (AST) dan refleksi byte-code (ArchUnit).
- **Membangun** pengujian arsitektur dinamis (*Dynamic Operational Fitness Function*) yang memvalidasi *resilience*, *throughput*, dan *latency budgets* melalui integrasi pengujian beban sintetik (*synthetic load*) dan metrik observabilitas (Prometheus/OpenTelemetry).
- **Mengevaluasi & Mengelola** kompromi arsitektural (*architectural trade-offs*) antara performa, skalabilitas, keamanan, dan biaya operasional secara kuantitatif.

---

## 2. Prerequisite
Untuk memahami modul ini secara komprehensif, Anda harus menguasai:
- **Konsep Arsitektur Perangkat Lunak:** Pemahaman mendalam mengenai Hexagonal/Clean/Layered Architecture, Bounded Contexts (DDD), dan distributed systems primitives.
- **Bahasa Pemrograman:** Java (JDK 17+) atau Go/Kotlin dengan pemahaman OOP, Reflection, dan Dependency Injection.
- **CI/CD & Devops Automation:** Docker, GitHub Actions/GitLab CI, dan konsep dasar infrastructure-as-code.
- **Dasar Observabilitas:** Metrik time-series (Prometheus), query language (PromQL), dan load-testing framework (k6 atau Gatling).

---

## 3. Concept & Internal Architecture (Mendalam)

### Definisi dan Taksonomi Architectural Fitness Functions
Menurut Neal Ford, Rebecca Parsons, dan Patrick Kua (*Building Evolutionary Architectures*), **Architectural Fitness Function** adalah:
> *"Mekanisme objektif dan terukur yang digunakan untuk memverifikasi integritas karakteristik arsitektur sistem dari waktu ke waktu."*

Fitness function meminjam terminologi dari algoritma genetika, di mana sebuah fungsi mengevaluasi seberapa dekat suatu solusi terhadap tujuan yang ditargetkan. Dalam arsitektur perangkat lunak, fungsi ini mengevaluasi apakah sistem memenuhi Quality Attributes (Karakteristik Arsitektur) yang telah ditetapkan saat sistem berevolusi.

```
+-------------------------------------------------------------------------+
|                  ARCHITECTURAL FITNESS FUNCTIONS (AFF)                  |
+------------------------------------+------------------------------------+
|               STATIC               |              DYNAMIC               |
+------------------------------------+------------------------------------+
| Dijalankan saat build/compile time | Dijalankan saat staging/production |
| Memvalidasi struktur & kode        | Memvalidasi perilaku runtime       |
| - Layering & Dependency Direction  | - Latency & Throughput (SLA/SLO)   |
| - Package Isolation                | - Fault Tolerance (Chaos Injection)|
| - Circular Dependencies            | - Memory Leak & Resource Saturation|
| - Class/Method Naming & Annotations| - Security Hardening (Dynamic Scan)|
+------------------------------------+------------------------------------+
|               ATOMIC               |              HOLISTIC              |
+------------------------------------+------------------------------------+
| Mengevaluasi satu karakteristik    | Mengevaluasi kombinasi karakteristik|
| secara terisolasi                  | yang saling berinteraksi           |
| Contoh: Package A tidak boleh      | Contoh: Security audit logging     |
| depend ke Package B                | tidak boleh menurunkan p99 latency |
|                                    | melewati 100ms                     |
+------------------------------------+------------------------------------+
```

### Mekanisme Kerja Internal Static Fitness Functions
Static fitness functions (seperti ArchUnit) bekerja dengan membaca *compiled bytecode* (contoh: `.class` files pada JVM) dan memetakan struktur tersebut ke dalam graph in-memory:
1. **Bytecode Parsing:** Parser membaca struktur file biner (menggunakan pustaka seperti ASM).
2. **Graph Construction:** Membentuk model domain internal yang merepresentasikan packages, classes, methods, fields, inheritance hierarchy, dan dependency call-graphs.
3. **Rule Evaluation:** Predikat logis dievaluasi terhadap graph tersebut. Setiap pemanggilan metode, implementasi interface, atau deklarasi tipe yang melanggar batasan predikat akan memicu *assertion failure*.

### Mekanisme Kerja Internal Dynamic Fitness Functions
Dynamic fitness functions memvalidasi karakteristik runtime melalui closed-loop feedback:
1. **Traffic Generation:** Beban sintetik diarahkan ke target environment (staging/ephemeral environment).
2. **Perturbation (Opsional):** Kegagalan sistemik diinjeksikan (misalnya, memutus akses network downstream service, membunuh container).
3. **Telemetry Interrogation:** Engine fitness function mengekstrak metrik dari sistem telemetri (misalnya querying Prometheus untuk 99th percentile response time, error rate percentage, saturasi memori).
4. **Threshold Verification:** Membandingkan nilai metrik aktual dengan *Architectural Threshold* yang didefinisikan (Service Level Objective). Jika melanggar, deployment digagalkan secara otomatis.

---

## 4. Why & What

### Mengapa Architectural Drift Terjadi?
*Architectural Drift* adalah fenomena degradasi arsitektur perangkat lunak secara bertahap yang disebabkan oleh ketidaksesuaian antara arsitektur yang dirancang (*intended architecture*) dan arsitektur yang sebenarnya diimplementasikan (*realized architecture*). 

Faktor penyebab:
1. **Pressure to Deliver:** Tekanan tenggat waktu menyebabkan engineer mengambil jalan pintas (contoh: memanggil database repository langsung dari controller/UI layer tanpa melewati domain service).
2. **Cognitive Load & Team Scaling:** Anggota tim baru tidak memahami batasan arsitektural yang telah ditetapkan sebelumnya.
3. **Lack of Automated Enforcement:** Arsitektur yang hanya didokumentasikan di dokumen PDF/Wiki cepat usang dan tidak dipatuhi (*dead documentation*).

### Solusi: Architecture as Code & Continuous Verification
Dengan Architectural Fitness Functions, arsitektur bertransformasi dari sekadar diagram statis menjadi tes unit/integrasi yang dapat dieksekusi secara berulang (*executable architectural assertions*). Setiap kali kode di-push:
- Jika ada *layering violation*, build gagal.
- Jika latensi $p99$ melebihi Service Level Objective (SLO), promotion ke production ditolak.
- Keberlanjutan sistem dijamin secara matematis dan deterministik.

---

## 5. How (Workflow Detail)

Berikut adalah diagram alir integrasi Fitness Function dalam Software Delivery Lifecycle (SDLC):

```
Developer Push 
      │
      ▼
[ Git Pre-commit Hook ] ────> Linting & Secret Detection
      │
      ▼
[ CI Build Stage ] ─────────> Kompilasi & Unit Tests
      │
      ▼
[ Static Fitness Functions ]─> ArchUnit: Validasi Layering, Hexagonal Boundary,
      │                      Tidak Ada Cyclic Dependency
      │ (Pass)
      ▼
[ Container Image Build ] ──> Image Scanning (Trivy)
      │
      ▼
[ Deploy to Ephemeral Env ] ─> Spin-up isolated environment
      │
      ▼
[ Dynamic Fitness Functions ]
      ├── A. Chaos Injection: Matikan 1 instance Redis/DB replica
      ├── B. Load Testing: Injeksi beban target via k6 (1000 RPS)
      └── C. Metric Query: PromQL query -> Ambil p99 Latency & Error Rate
      │
      ├──> Error Rate > 0.1% ATAU p99 > 80ms? 
      │           │
      │         (Yes) ──> BUILD FAILED, Alert Architect, Drop Env
      │           │
      │          (No)
      ▼
[ Canary Deployment to Prod ]
      │
      ▼
[ Continuous Fitness Functions ] ──> Observability Alerting (Prometheus/Grafana)
                                    monitoring architectural invariants
```

---

## 6. Analogy & Diagram ASCII

### Analogi Jembatan Gantung vs Dynamic Fitness Function
Sebuah jembatan gantung dirancang untuk menahan beban 50 ton dan terpaan angin hingga 120 km/jam.
- **Static Fitness Function:** Memeriksa ketebalan kabel baja, komposisi beton, dan sudut baut sebelum jembatan dibuka untuk umum.
- **Dynamic Fitness Function:** Sensor seismik dan sensor regangan (*strain gauges*) yang dipasang permanen pada jembatan. Ketika beban lalu lintas padat digabungkan dengan hembusan angin kencang, sensor secara aktif mengukur apakah getaran jembatan tetap berada di dalam rentang frekuensi aman. Jika getaran melampaui ambang batas aman, sistem lampu lalu lintas otomatis menutup akses ke jembatan.

### Diagram: Hexagonal Architecture Fitness Boundary Enforcement

```
+--------------------------------------------------------------------------+
|                        ARCHITECTURAL BOUNDARY                            |
|                                                                          |
|  [ INCOMING ADAPTERS ]                                                   |
|   (REST Controller, gRPC Handler, Messaging Consumer)                    |
|           │                                                              |
|           ▼ (Calls directly or via Command Bus)                          |
|  [ APPLICATION CORE (USE CASES / PORTS) ]                                |
|   (OrderService, ProcessPaymentUseCase)                                  |
|           │                                                              |
|           ▼ (Direct access - Invariant Rules Apply)                      |
|  [ DOMAIN ENTITIES & VALUE OBJECTS ]                                     |
|   (Order, OrderLine, Money)                                              |
|           ▲                                                              |
|           │ (DILARANG: Domain TIDAK BOLEH memanggil Infrastructure)      |
|           │ (DILARANG: Infrastructure TIDAK BOLEH diakses UI langsung)   |
|           │                                                              |
|  [ OUTGOING ADAPTERS (INFRASTRUCTURE) ]                                  |
|   (PostgreSQL Repository, Kafka Producer, Redis Cache)                   |
+--------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### Static Fitness Function (ArchUnit)
Implementasi rule engine di Java untuk memvalidasi Clean Architecture dan mencegah *circular dependencies*.

```java
package com.enterprise.architecture.fitness;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.lang.ArchRule;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.Architectures.onionArchitecture;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

public class ArchitecturalBoundaryFitnessTest {

    private static JavaClasses importedClasses;

    @BeforeAll
    static void setUp() {
        importedClasses = new ClassFileImporter()
                .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
                .importPackages("com.enterprise.banking");
    }

    @Test
    @DisplayName("AFF-01: Domain layer must not depend on Application, Infrastructure, or UI")
    void domainMustBeCompletelyIsolated() {
        ArchRule domainIsolationRule = noClasses()
                .that().resideInAPackage("..domain..")
                .should().dependOnClassesThat()
                .resideInAnyPackage("..application..", "..infrastructure..", "..interfaces..");

        domainIsolationRule.check(importedClasses);
    }

    @Test
    @DisplayName("AFF-02: Enforce Strict Onion/Hexagonal Architecture Style")
    void enforceOnionArchitecture() {
        ArchRule onionRule = onionArchitecture()
                .domainModels("com.enterprise.banking.domain.model..")
                .domainServices("com.enterprise.banking.domain.service..")
                .applicationServices("com.enterprise.banking.application..")
                .adapter("persistence", "com.enterprise.banking.infrastructure.persistence..")
                .adapter("rest", "com.enterprise.banking.interfaces.rest..");

        onionRule.check(importedClasses);
    }

    @Test
    @DisplayName("AFF-03: Zero Cyclic Dependencies across Packages")
    void freeOfCycles() {
        ArchRule cyclePreventionRule = slices()
                .matching("com.enterprise.banking.(*)..")
                .should().beFreeOfCycles();

        cyclePreventionRule.check(importedClasses);
    }

    @Test
    @DisplayName("AFF-04: Interfaces Layer must not talk directly to Persistence Layer")
    void restLayerMustNotDirectlyAccessPersistence() {
        ArchRule restIsolationRule = noClasses()
                .that().resideInAPackage("..interfaces.rest..")
                .should().dependOnClassesThat()
                .resideInAPackage("..infrastructure.persistence..");

        restIsolationRule.check(importedClasses);
    }
}
```

### Dynamic Operational Fitness Function (k6 + Prometheus PromQL)
Skrip verifikasi dinamis berbasis JavaScript (k6) yang memeriksa *Quality of Service (QoS)* sebagai fitness gate di staging.

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom Metrics for Fitness Function Evaluation
export let failureRate = new Rate('aff_sla_violations');
export let transactionDuration = new Trend('aff_payment_duration');

export let options = {
  stages: [
    { duration: '30s', target: 50 },  // Ramp up
    { duration: '1m', target: 200 },  // Steady state sustained high load
    { duration: '30s', target: 0 },   // Ramp down
  ],
  thresholds: {
    // FITNESS RULE 1: 99% of requests must complete under 150ms
    'http_req_duration': ['p(99)<150'],
    // FITNESS RULE 2: Failure rate strictly lower than 0.01%
    'aff_sla_violations': ['rate<0.0001'],
    // FITNESS RULE 3: Custom trend for specific critical business endpoint
    'aff_payment_duration': ['p(95)<100'],
  },
};

const BASE_URL = __ENV.TARGET_ENV_URL || 'https://staging.internal.bank.com';

export default function () {
  const payload = JSON.stringify({
    accountFrom: "ACC-99812",
    accountTo: "ACC-11244",
    amount: 1500000,
    currency: "IDR"
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Idempotency-Key': `k6-${__VU}-${__ITER}-${Date.now()}`
    },
  };

  let res = http.post(`${BASE_URL}/api/v1/payments/transfer`, payload, params);

  // Evaluate Fitness Invariants
  let success = check(res, {
    'status is 200 OK': (r) => r.status === 200,
    'body contains transactionId': (r) => JSON.parse(r.body).transactionId !== undefined,
  });

  if (!success) {
    failureRate.add(1);
  } else {
    failureRate.add(0);
    transactionDuration.add(res.timings.duration);
  }

  sleep(0.05); // Rapid concurrent calls
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Konteks: Global Payment Gateway (Transparansi SLA & Zero Cascading Failure)
*Perusahaan:* FinTech Multinational Processing Platform.  
*Beban:* 15,000 Transaksi per Detik (TPS) pada jam sibuk global.  
*Isu Arsitektural:* Tim sering merilis *feature update* yang secara tidak sengaja menambahkan *blocking I/O operations* di dalam downstream calls, serta meloloskan query non-indexed ke Postgres, yang memicu *cascading exhaustion* pada database connection pools.

### Implementasi Architectural Fitness Function Pipeline
Perusahaan mengimplementasikan pipeline 3 lapis untuk memvalidasi Quality Attributes:

```
[ Git Push / PR ]
       │
       ▼
 1. Structural Fitness (ArchUnit)
    - Verifikasi bahwa TIDAK ADA code path dari `PaymentRouter` yang memanggil `DatabaseRepository` 
      secara synchronous.
    - Rule: Wajib menggunakan `NonBlockingPaymentPort`.
       │
       ▼ (Merge to Staging)
 2. Dynamic Performance & Resilience Gate (k6 + Toxiproxy + Prometheus)
    - Toxiproxy menyuntikkan latency 250ms pada 3rd-party Card Processor.
    - Fitness Function memverifikasi Circuit Breaker:
      *Metrik:* Error rate PaymentRouter harus tetap di bawah 2%.
      *Metrik:* Request yang timeout HARUS dialihkan ke alternative route dalam waktu < 50ms.
       │
       ▼ (Pass)
 3. Production Continuous Canary Gate
    - Argo Rollouts mengirimkan 5% traffic produksi ke versi baru.
    - Prometheus membandingkan Canary Error Rate terhadap Baseline Error Rate selama 10 menit.
    - JIKA: canary_p99_latency > baseline_p99_latency * 1.15 -> Auto-Rollback seketika.
```

### Hasil Operasional:
- *MTBF (Mean Time Between Failures)* meningkat sebesar **340%**.
- Insiden *Cascading Database Lock* turun menjadi **0 kejadian per kuartal**.
- Deteksi *architectural regressions* berpindah dari *Production Incident* menjadi *PR-Blocker*.

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

Implementasi Fitness Functions membutuhkan trade-off yang harus diseimbangkan oleh Architect:

| Dimensi | Keuntungan (Pros) | Biaya / Trade-off (Cons) | Strategi Mitigasi |
| :--- | :--- | :--- | :--- |
| **CI/CD Pipeline Duration** | Mencegah regresi arsitektur sebelum masuk fase rilis. | Static analysis & comprehensive AST parsing menambah durasi pipeline 2–10 menit. Dynamic testing menambah 15–30 menit. | Jalankan static tests pada setiap PR; jalankan heavy dynamic testing (Chaos/Load) secara terjadwal (Nightly) atau hanya pada tag release. |
| **Infrastructure Cost** | Mencegah insiden *outage* bernilai jutaan dolar di production. | Membutuhkan *ephemeral staging environment* yang representatif secara kapasitas dengan production. | Gunakan simulasi containerized (Testcontainers) dan load test dengan scaling multiplier yang diturunkan (*downscaled load extrapolation*). |
| **Developer Velocity** | Batasan arsitektural jelas; mempermudah onboarding engineer baru tanpa code review manual yang melelahkan. | Tingginya *false positive* jika aturan terlalu kaku (brittle tests), yang dapat memicu frustrasi tim developer (*alert fatigue*). | Terapkan rule exceptions secara pragmatis melalui anotasi arsitektur resmi (misal: `@ArchIgnore`) dengan kewajiban review dari Principal Architect. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Brittle Class-Name Matching Rules
*Kesalahan:* Menulis ArchUnit rules berdasarkan regex nama kelas, misalnya `classes().that().haveSimpleNameEndingWith("Service")`. Developer mengubah nama menjadi `OrderManager`, dan aturan tersebut diabaikan secara diam-diam (*silent bypass*).  
*Solusi:* Evaluasi berdasarkan implementasi Java Interface, Type Inheritance, atau Custom Annotation (misal: `@DomainService`).

### 2. Flaky Dynamic Tests due to Shared Environments
*Kesalahan:* Menjalankan dynamic latency fitness function di shared staging environment di mana tim lain juga sedang menjalankan batch process atau integration tests, menyebabkan test gagal secara acak.  
*Solusi:* Isolasi penuh via Ephemeral Staging Environments (menggunakan Kubernetes Helm/Argo preview apps) dengan hardware affinity dan isolasi network yang terkontrol.

### 3. Fitness Functions Tidak Terintegrasi dengan Build System
*Kesalahan:* Static analysis dieksekusi secara manual lewat dashboard SonarQube tanpa memblokir proses Git Merge. Tim mengabaikan *warning dashboard*.  
*Solusi:* Kunci PR merge button: fitness function wajib menghasilkan exit code `0`. Jika gagal, PR berstatus *Checks Failed* dan tidak dapat dimerge (*hard gate*).

---

## 11. Best Practices (Production Checklist)

| Kategori | Action Item | Target Verifikasi | Status |
| :--- | :--- | :--- | :--- |
| **Static Guardrails** | Semua Domain Model bebas dari dependensi library pihak ketiga (termasuk Spring Framework, Hibernate, Jackson annotations). | ArchUnit Tests PASS | [ ] |
| **Cyclic Dependency** | Package graph modular monolit atau microservice packages bebas dari siklus sirkular. | SlicesRule.beFreeOfCycles() PASS | [ ] |
| **Latency Budget** | P99 latency API inti berada di bawah SLA (misal: < 100ms) pada kapasitas 1.5x peak traffic. | k6 Thresholds PASS | [ ] |
| **Fault Isolation** | Jika downstream database mati, fallback mechanism atau circuit breaker aktif dalam waktu < 2 detik tanpa *thread starvation*. | LitmusChaos / Chaos Mesh PASS | [ ] |
| **Telemetry Invariants** | Semua outbound HTTP client wajib menginjeksi OpenTelemetry distributed tracing headers (`traceparent`). | Static bytecode audit PASS | [ ] |
| **Security Assertions**| Tidak ada controller layer endpoint yang tidak memiliki decorator autentikasi/otorisasi yang eksplisit. | ArchUnit Security Rule PASS | [ ] |

---

## 12. Hands-on Practice

Buatlah proyek otomasi architectural fitness test lokal lengkap.

### Struktur Direktori:
```
hands-on/m02/
├── pom.xml
└── src
    ├── main
    │   └── java
    │       └── com
    │           └── enterprise
    │               └── order
    │                   ├── application
    │                   │   └── OrderApplicationService.java
    │                   ├── domain
    │                   │   ├── model
    │                   │   │   └── Order.java
    │                   │   └── repository
    │                   │       └── OrderRepository.java
    │                   └── infrastructure
    │                       └── persistence
    │                           └── PostgresOrderRepository.java
    └── test
        └── java
            └── com
                └── enterprise
                    └── order
                        └── architecture
                            └── StrictHexagonalFitnessTest.java
```

### File 1: `pom.xml`
```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.enterprise</groupId>
    <artifactId>architectural-fitness-lab</artifactId>
    <version>1.0.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <junit.jupiter.version>5.9.2</junit.jupiter.version>
        <archunit.version>1.1.0</archunit.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-api</artifactId>
            <version>${junit.jupiter.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <version>${junit.jupiter.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>com.tngtech.archunit</groupId>
            <artifactId>archunit-junit5</artifactId>
            <version>${archunit.version}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.0.0-M9</version>
            </plugin>
        </plugins>
    </build>
</project>
```

### File 2: `Order.java` (Domain Entity)
```java
package com.enterprise.order.domain.model;

import java.math.BigDecimal;
import java.util.UUID;

public class Order {
    private final UUID id;
    private BigDecimal totalAmount;

    public Order(UUID id, BigDecimal totalAmount) {
        this.id = id;
        this.totalAmount = totalAmount;
    }

    public UUID getId() { return id; }
    public BigDecimal getTotalAmount() { return totalAmount; }
}
```

### File 3: `OrderRepository.java` (Domain Port)
```java
package com.enterprise.order.domain.repository;

import com.enterprise.order.domain.model.Order;
import java.util.Optional;
import java.util.UUID;

public interface OrderRepository {
    Optional<Order> findById(UUID id);
    void save(Order order);
}
```

### File 4: `OrderApplicationService.java` (Application Service)
```java
package com.enterprise.order.application;

import com.enterprise.order.domain.model.Order;
import com.enterprise.order.domain.repository.OrderRepository;
import java.util.UUID;

public class OrderApplicationService {
    private final OrderRepository repository;

    public OrderApplicationService(OrderRepository repository) {
        this.repository = repository;
    }

    public Order getOrder(UUID id) {
        return repository.findById(id)
                .orElseThrow(() -> new RuntimeException("Order Not Found"));
    }
}
```

### File 5: `PostgresOrderRepository.java` (Infrastructure Adapter)
```java
package com.enterprise.order.infrastructure.persistence;

import com.enterprise.order.domain.model.Order;
import com.enterprise.order.domain.repository.OrderRepository;
import java.util.Optional;
import java.util.UUID;

public class PostgresOrderRepository implements OrderRepository {
    @Override
    public Optional<Order> findById(UUID id) {
        // Implementasi SQL DB simulation
        return Optional.of(new Order(id, java.math.BigDecimal.TEN));
    }

    @Override
    public void save(Order order) {
        // SQL Persist simulation
    }
}
```

### File 6: `StrictHexagonalFitnessTest.java` (The Fitness Function)
```java
package com.enterprise.order.architecture;

import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "com.enterprise.order")
public class StrictHexagonalFitnessTest {

    @ArchTest
    public static final ArchRule domain_should_not_depend_on_infrastructure =
        noClasses().that().resideInAPackage("..domain..")
                   .should().dependOnClassesThat()
                   .resideInAPackage("..infrastructure..");

    @ArchTest
    public static final ArchRule domain_should_not_depend_on_application =
        noClasses().that().resideInAPackage("..domain..")
                   .should().dependOnClassesThat()
                   .resideInAPackage("..application..");

    @ArchTest
    public static final ArchRule application_should_not_depend_on_infrastructure =
        noClasses().that().resideInAPackage("..application..")
                   .should().dependOnClassesThat()
                   .resideInAPackage("..infrastructure..");
}
```

### Langkah Eksekusi Praktikum:
1. Pindah ke direktori: `cd hands-on/m02/`
2. Jalankan kompilasi dan architectural unit tests:
   ```bash
   mvn clean test
   ```
   *Ekspektasi:* **BUILD SUCCESS (Tests run: 3, Failures: 0, Errors: 0)**
3. **Simulasikan Pelanggaran Arsitektur:**  
   Buka file `Order.java` (Domain), lalu tambahkan dependensi ilegal ke layer infrastructure:
   ```java
   private com.enterprise.order.infrastructure.persistence.PostgresOrderRepository leak;
   ```
4. Jalankan kembali `mvn clean test`.
5. *Ekspektasi Kegagalan Deterministik:*
   ```text
   [ERROR] Failures: 
   [ERROR] StrictHexagonalFitnessTest.domain_should_not_depend_on_infrastructure
   Field <com.enterprise.order.domain.model.Order.leak> has type <com.enterprise.order.infrastructure.persistence.PostgresOrderRepository> in (Order.java:9)
   [ERROR] Tests run: 3, Failures: 1, Errors: 0, Skipped: 0
   ```
6. Hapus dependensi ilegal tersebut untuk mengembalikan status build menjadi hijau (*green*).

---

## 13. Exercise

### Level Easy:
Tuliskan ArchUnit rule yang mewajibkan semua interface repository (yang berada di package `..domain.repository..`) harus memiliki akhiran nama (`SimpleName`) berakhiran `Repository`.

### Level Medium:
Tuliskan ArchUnit rule yang memvalidasi bahwa tidak ada class di seluruh sistem yang boleh memanggil `System.out.println()` atau `System.err.println()`, melainkan harus selalu menggunakan framework logging (misalnya SLF4J / `org.slf4j.Logger`), dan cegah penggunaan anotasi `@Transactional` dari Spring di dalam layer Domain.

### Level Hard:
Rancang skenario Continuous Architectural Fitness Function berbasis GitHub Actions Workflow YAML yang:
1. Membangun target sistem menggunakan Docker Compose (Service + Redis + Postgres).
2. Mengeksekusi skrip k6 untuk menembak endpoint `/checkout`.
3. Membaca file ringkasan metrik hasil k6 (`summary.json`).
4. Jika persentil ke-95 ($p95$) latensi melebihi 120ms, workflow wajib membatalkan *automated deployment* dan memicu webhook pemberitahuan insiden arsitektur ke Slack channel tim arsitek.

---

## 14. Challenge

### Studi Kasus Produksi: "The Rogue Event Producer Leak"
Sebuah perusahaan logistik skala enterprise memiliki arsitektur modular monolitik yang sedang dalam fase transisi ke *Event-Driven Microservices*. Aturan arsitekturnya adalah:
- Domain Module tidak boleh mempublikasikan domain event secara synchronous ke Apache Kafka broker (karena operasi jaringan blocking dapat memicu distributed transaction failures).
- Publikasi event wajib melalui implementasi **Transactional Outbox Pattern** lokal di database Postgres masing-masing module.

**Tantangan Anda:**
1. Desain sebuah mekanisme Architectural Fitness Function otomatis (gabungan ArchUnit statis dan Dynamic Test) yang mampu mendeteksi secara mutlak jika ada engineer yang mencoba menginjeksi Kafka Producer Client (`org.apache.kafka.clients.producer.Producer`) secara langsung ke dalam package Domain Service atau Application Layer.
2. Fitness function tersebut juga harus mampu memverifikasi bahwa *Outbox Publisher background worker* tidak mengalami degradasi latensi publikasi event melebihi SLA 500 milidetik sejak transaksi database lokal di-commit. Uraikan spesifikasi teknis arsitektur fitness testing tersebut.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara Functional Requirement dan Quality Attribute Requirement (QAR)?**  
   *Jawaban:* Functional requirement mendefinisikan apa yang harus dilakukan sistem (fungsionalitas/fitur bisnis spesifik), sedangkan QAR mendefinisikan bagaimana sistem menjalankan fungsionalitas tersebut dalam hal performa, ketersediaan, keamanan, evolvabilitas, dan pemeliharaan (karakteristik operasional).
2. **Apa yang dimaksud dengan Architectural Drift?**  
   *Jawaban:* Kondisi di mana struktur implementasi aktual kode menyimpang secara perlahan dari desain arsitektur yang dirancang semula akibat perubahan tak terkontrol atau ketidakpatuhan developer seiring berjalannya waktu.
3. **Mengapa Static Fitness Function dijalankan pada fase paling awal dari CI/CD pipeline?**  
   *Jawaban:* Mengikuti prinsip *shift-left*; static fitness function berjalan cepat dalam hitungan detik saat kompilasi/unit test, memberikan umpan balik instan kepada developer dengan biaya komputasi dan penundaan minimal sebelum resource dialokasikan untuk deployment staging.
4. **Sebutkan dua contoh metrik yang divalidasi oleh Dynamic Fitness Function!**  
   *Jawaban:* Latensi percentile (contoh: $p99 < 100ms$) dan persentase tingkat kegagalan (*error rate/SLA violations* di bawah 0.01%).
5. **Apa fungsi dari library ArchUnit dalam ekosistem Java?**  
   *Jawaban:* Sebagai engine pengujian statis yang mengimpor compiled bytecode Java ke dalam struktur graph memori untuk menegakkan aturan dependensi arsitektur, pola layering, dan konvensi penamaan melalui unit test assertions.

### Bagian 2: Intermediate (5 Pertanyaan)
1. **Bagaimana cara mencegah Cyclic Dependency antar package menggunakan Architectural Fitness Function?**  
   *Jawaban:* Menggunakan rule `slices().matching("package.(*)..").should().beFreeOfCycles()`. ArchUnit akan menganalisis Graph Teori dependensi antar paket; jika ditemukan directed graph tertutup ($A \to B \to C \to A$), build akan di-fail seketika.
2. **Apa yang dimaksud dengan Atomic vs Holistic Fitness Function? Berikan contohnya.**  
   *Jawaban:* *Atomic* mengevaluasi satu karakteristik terisolasi (misalnya: Layer Domain tidak boleh mengimpor framework Spring). *Holistic* mengevaluasi interaksi kompleks antara beberapa atribut (misalnya: meningkatkan enkripsi security payload tidak boleh membuat p95 throughput database turun di bawah 5000 RPS).
3. **Mengapa pengujian latensi (Performance Fitness Function) tidak valid jika dieksekusi di shared test environment?**  
   *Jawaban:* Karena adanya fenomena *noisy neighbors* (komputasi, I/O disk, dan bandwidth jaringan dipakai bersama oleh proses lain), sehingga hasil pengukuran latensi menjadi *flaky*, bervariasi tinggi, dan tidak deterministik.
4. **Jelaskan peran Transactional Outbox Pattern dalam konteks Quality Attribute "Reliability & Event Consistency"!**  
   *Jawaban:* Mencegah *dual-write problem* dengan menyimpan event bisnis ke dalam tabel database yang sama dengan entitas domain dalam satu atomic transaction ACID, memastikan event tidak akan hilang jika message broker sedang down saat transaksi commit.
5. **Bagaimana Architectural Fitness Function mendukung paradigma "Evolutionary Architecture"?**  
   *Jawaban:* AFF bertindak sebagai pagar pengaman (*guardrails*). Arsitek dapat memperbolehkan sistem berubah dan berevolusi secara cepat (misalnya mengganti framework atau library) dengan jaminan otomatis bahwa karakteristik arsitektur fundamental (ketersediaan, keamanan, modularitas) tidak terdegradasi.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

#### Skenario 1: The Accidental O(N) Query Leak
*Kasus:* Tim developer merilis fitur baru pada sistem e-commerce di mana pada layer presentation (GraphQL Resolver), developer secara tidak sengaja memanggil method database secara berulang di dalam loop (masalah N+1 Query). Di local machine dengan 10 item data, performa terasa normal. Di staging dengan data besar, latensi melonjak drastis.  
*Pertanyaan:* Fitness function seperti apa yang harus dipasang untuk mencegah masalah ini lolos ke production?  
*Jawaban & Analisis:*  
1. *Static Fitness Rule:* Menggunakan ArchUnit untuk melarang pemanggilan langsung method repository/database queries dari dalam GraphQL Resolvers atau REST Controllers.  
2. *Dynamic Synthetic Query Count Gate:* Menjalankan integration test menggunakan QuickPerf atau test assertion SQL execution count. Aturan fitness: Pada endpoint `/orders`, pemanggilan SQL statements tidak boleh melebihi batas konstan $O(1)$ untuk $N$ items (maksimal $K$ queries per request). Jika query count proporsional terhadap ukuran data input ($O(N)$), test gagal.

#### Skenario 2: The Unchecked Database Replica Lag
*Kasus:* Sistem perbankan menerapkan arsitektur *Read-Write Database Splitting*. Karena volume transaksi tinggi, terjadi *replication lag* sebesar 4 detik ke read-replica. Developer baru menulis fitur pencatatan transfer dana, di mana setelah write commit ke primary, sistem langsung melakukan read status transfer dari read-replica, menyebabkan transfer tampak "hilang" dan membingungkan nasabah.  
*Pertanyaan:* Rancang Dynamic Fitness Function untuk mendeteksi arsitektur yang rentan terhadap read-replica lag ini.  
*Jawaban & Analisis:*  
1. Di environment CI/Staging, implementasikan Chaos Fitness Function: Injeksikan artificial replication lag buatan (misal: 5 detik) pada database replica menggunakan tools network emulation.  
2. Eksekusi End-to-End Dynamic Test: Buat transaksi transfer, lalu segera akses API pembaca status.  
3. Assert fitness rule: API read harus menerapkan pola *Read-Your-Own-Writes Consistency* (misal: merutekan read query ke master node jika transaksi terjadi dalam interval < 10 detik, atau menggunakan token-based routing). Jika respons API membaca status stale/kosong, build digagalkan.

#### Skenario 3: The Framework Lock-in Encroachment
*Kasus:* Sebuah perusahaan enterprise memutuskan aturan arsitektur: "Core Domain Logic harus murni POJO/POCO dan independen dari vendor/cloud framework." Enam bulan kemudian, ditemukan bahwa 40% class di dalam Domain Entity telah dianotasi dengan `@Table`, `@Entity` (JPA/Hibernate), dan `@JsonProperty` (Jackson), serta bergantung langsung pada AWS SDK S3 client.  
*Pertanyaan:* Apa akar masalah tata kelola ini, dan tuliskan ArchUnit fitness function spesifik untuk membersihkan dan mengunci Domain dari framework lock-in tersebut secara permanen.  
*Jawaban & Analisis:*  
Akar masalah adalah tata kelola arsitektur berbasis manual code review tanpa *automated enforcement gate*.  
Fitness function untuk mengunci domain:
```java
@Test
void domainMustBeZeroFrameworkDependent() {
    ArchRule cleanDomainRule = classes()
        .that().resideInAPackage("..domain..")
        .should().onlyDependOnClassesThat()
        .resideInAnyPackage(
            "java..", 
            "..domain.."
        );
    cleanDomainRule.check(importedClasses);
}
```
Aturan ini secara instan menggagalkan build jika ada class domain yang mengimpor package `javax.persistence..`, `jakarta.persistence..`, `com.fasterxml.jackson..`, atau `software.amazon.awssdk..`. Framework-specific mappings dipindahkan sepenuhnya ke adapter layer di infrastructure.

---

## 16. Summary
Architectural Fitness Functions (AFF) mengubah Quality Attribute Requirements (QARs) dari sekadar dokumen spesifikasi non-fungsional statis menjadi **artefak kode yang dapat diuji dan dieksekusi secara otomatis**.

Kunci implementasi arsitektur produksi:
1. **Static Fitness Functions (ArchUnit, AST Analyzers):** Berjalan di build-time untuk menjaga modularitas, arah dependensi (Hexagonal/Clean Architecture), dan mencegah siklus dependensi sirkular secara instan.
2. **Dynamic Fitness Functions (k6, Chaos Engineering, PromQL Gates):** Berjalan di staging/canary deployment untuk memverifikasi SLO operasional seperti latensi persentil ($p99$), throughput, dan resiliensi saat terjadi kegagalan infrastruktur.
3. **Shift-Left Architecture Governance:** Mengotomatiskan validasi batasan arsitektur dalam CI/CD pipeline menjamin sistem dapat berevolusi secara cepat tanpa risiko degradasi struktural (*architectural decay*). Arsitektur perangkat lunak tidak lagi dinilai berdasarkan opini, melainkan dibuktikan secara deterministik oleh kode pengujian arsitektur itu sendiri.