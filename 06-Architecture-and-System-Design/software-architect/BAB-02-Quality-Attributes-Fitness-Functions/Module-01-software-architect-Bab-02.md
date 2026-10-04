## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `ARCH-06-B02-M01`
* **Nama Modul**: Software Quality Attributes & Fitness Functions: Karakteristik Arsitektur (Availability, Latency, Scalability, Modifiability), Automated Architectural Fitness Functions
* **Kategori**: `06-Architecture-and-System-Design`
* **Jalur Kurikulum**: Software Architect
* **Tingkat Kemahiran**: Advanced / Expert
* **Prasyarat**:
  * Pemahaman mendalam mengenai Software Design Patterns (Gang of Four) & Architectural Patterns (Hexagonal, Microservices, Event-Driven).
  * Pengalaman mengelola Continuous Integration / Continuous Deployment (CI/CD) pipelines.
  * Pemahaman metrik performa aplikasi (Throughput, Latency, Saturation, Error Rate).
* **Estimasi Waktu Selesai**: 8 Jam (Membaca, Analisis Studi Kasus, dan Praktik Laboratorium)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis** kebutuhan bisnis implisit dan eksplisit menjadi sekumpulan *Quality Attribute Scenarios* (QAS) yang terukur, formal, dan tidak ambigu untuk atribut Availability, Latency, Scalability, dan Modifiability.
2. **Mengevaluasi** kompromi arsitektural (*architectural trade-offs*) antar karakteristik yang saling bertentangan berdasarkan model formal (misalnya, CAP/PACELC theorem, Amdahl's Law, Little's Law).
3. **Merancang dan Mengimplementasikan** *Automated Architectural Fitness Functions* di dalam pipeline CI/CD untuk mencegah *architectural drift* dan *architectural erosion*.
4. **Membangun** sistem pengujian karakteristik struktural menggunakan *static code analysis rules* (seperti ArchUnit) serta pengujian operasional dinamis berbasis SLA/SLO (seperti k6 load testing gates).
5. **Menilai** derajat kopling, kohesi, dan stabilitas modular menggunakan metrik struktural software (Afferent Coupling, Efferent Coupling, Abstractness, Instability, Distance from Main Sequence).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                                BUSINESS GOALS & CONSTRAINTS
                                             │
                                             ▼
                                ARCHITECTURAL CHARACTERISTICS
                               (ISO/IEC 25010 Quality Attributes)
                    ┌────────────────────────┼────────────────────────┐
                    ▼                        ▼                        ▼
               OPERATIONAL              STRUCTURAL               CROSS-CUTTING
         ┌──────────┴──────────┐             │                        │
         ▼                     ▼             ▼                        ▼
    Availability            Latency     Modifiability            Security / Cost
    - MTBF / MTTR          - P95 / P99  - Coupling (Ca, Ce)
    - Redundancy           - Queuing    - Cohesion (LCOM)
    - Fault Isolation                   - Modularity
         │                     │             │                        │
         └──────────┬──────────┴─────────────┴────────────────────────┘
                    ▼
       QUALITY ATTRIBUTE SCENARIOS (QAS)
    [Source -> Stimulus -> Artifact -> Environment -> Response -> Measure]
                    │
                    ▼
       ARCHITECTURAL FITNESS FUNCTIONS
    (Evolutionary Architecture Verification)
         ┌──────────┴────────────────────────┐
         ▼                                   ▼
      STATIC                               DYNAMIC
   (Compile/CI Time)                 (Deploy/Runtime)
   - ArchUnit (Hexagonal boundaries) - Chaos Engineering (Chaos Mesh)
   - Dependency Cyclic Checks        - Automated Performance Gates (k6)
   - Modularity Metrics Gate         - Observability & SLO Drift Alerts
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sistem perangkat lunak jarang gagal karena kegagalan fungsi (*functional requirements*); hampir seluruh kegagalan katastropik bersumber dari ketidakmampuan sistem mempertahankan karakteristik kualitas arsitektur (*quality attributes*) di bawah tekanan beban, kegagalan infrastruktur, atau evolusi kode berskala besar.

1. **Pencegahan Architectural Drift & Decay**: Tanpa kontrol otomatis, entropi arsitektur akan selalu meningkat. Arsitektur berlapis murni (*layered architecture*) atau berbasis domain terisolasi (*ports & adapters*) akan runtuh menjadi *Big Ball of Mud* hanya dalam beberapa kuartal rilis akibat *shortcut* implementasi oleh tim pengembang.
2. **Kuantifikasi "Non-Functional Requirements" (NFR)**: Frasa seperti *"Sistem harus cepat"* atau *"Sistem harus reliable"* tidak berguna dalam rekayasa perangkat lunak. Karakteristik arsitektur harus didefinisikan secara presisi matematis dan probabilistik (contoh: P99 Tail Latency $\le 150\text{ms}$ pada beban puncak 10.000 RPS).
3. **Penerapan Evolutionary Architecture**: Pendekatan arsitektur modern menolak model *Big Design Up Front* (BDUF). Sebagai gantinya, arsitektur harus mampu berevolusi secara modular tanpa merusak karakteristik inti sistem. Hal ini hanya mungkin dilakukan jika batas-batas arsitektur dilindungi oleh *Architectural Fitness Functions* yang dieksekusi secara otomatis pada setiap perubahan basis kode.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Karakteristik Arsitektur (Software Quality Attributes)
Karakteristik arsitektur adalah dimensi non-fungsional dari sistem yang menentukan bagaimana sistem berperilaku di luar eksekusi logika bisnis murni. Mengacu pada standardisasi ISO/IEC 25010 dan literatur Software Architecture Institute (SEI CMU), karakteristik utama meliputi:

* **Availability**: Probabilitas sistem operasional dan dapat diakses ketika diminta oleh pengguna. Dihitung secara matematis sebagai rasio:
  $$\text{Availability} = \frac{\text{MTBF}}{\text{MTBF} + \text{MTTR}}$$
  *(MTBF = Mean Time Between Failures, MTTR = Mean Time To Repair)*.
* **Latency & Response Time**: Waktu yang dibutuhkan sistem untuk memproses *request* dari saat diterima hingga respons dikembalikan. Latensi tidak boleh dianalisis secara rata-rata (*mean*), melainkan melalui distribusi persentil (*Tail Latency* P90, P95, P99, P99.9) untuk menangkap anomali konkurensi dan antrean (*queuing delay*).
* **Scalability**: Kemampuan sistem untuk mempertahankan performa konstan (atau degradasi anggun) saat beban (*throughput*, data volume, konkurensi) bertambah, dengan menambahkan sumber daya komputasi secara linier atau sub-linier.
* **Modifiability**: Kemudahan sistem untuk diubah, diperluas, atau dipelihara tanpa menimbulkan regresi atau efek samping tak terduga (*blast radius* luas) pada modul lain.

### 2. Architectural Fitness Functions
Didefinisikan pertama kali oleh Neal Ford, Rebecca Parsons, dan Patrick Kua (*Building Evolutionary Architectures*), **Architectural Fitness Function** adalah mekanisme obyektif dan terukur yang digunakan untuk memvalidasi pemenuhan satu atau lebih karakteristik kualitas arsitektur. 

Fitness function bertindak sebagai unit test bagi arsitek:
* **Static Fitness Functions**: Memeriksa struktur kode, dependensi, pola arsitektur, dan metrik kompleksitas saat kompilasi atau *linting*.
* **Dynamic Fitness Functions**: Mengevaluasi metrik performa, keamanan, dan ketahanan (*resilience*) secara aktif selama pengujian integrasi beban atau pengawasan operasional langsung.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Operasional: Dari Kebutuhan Bisnis ke Automated Gate

Menerapkan fitness functions menuntut transformasi spesifikasi abstrak menjadi artefak komputasional:

```text
[Kebutuhan Bisnis] 
       │
       ▼
[Quality Attribute Scenario (QAS)]
   ├── Source (Pengguna eksternal, Sensor, Layanan dependen)
   ├── Stimulus (10.000 transaksi/detik serentak)
   ├── Artifact (Order Processing Engine)
   ├── Environment (Overload peak period, partial network split)
   ├── Response (Transaksi diterima, tidak ada inkonsistensi data)
   └── Response Measure (Latency P99 < 200ms, Error Rate < 0.01%)
       │
       ▼
[Spesifikasi Fitness Function]
   ├── Type: Dynamic Integration Test (k6) + Static Check (ArchUnit)
   ├── Threshold / Assertion Rule
   └── Trigger: CI Pipeline Commit / Nightly Pipeline
       │
       ▼
[Automated Evaluation in Pipeline] ──> PASS: Merge / Deploy
                                   └──> FAIL: Pipeline Blocked & Alert
```

### Mekanisme Metrik Modifiability: Robert C. Martin's Package Metrics
Modifiability dinilai secara kuantitatif melalui formula ketergantungan paket:

1. **Afferent Coupling ($C_a$)**: Jumlah kelas luar modul yang bergantung pada kelas di dalam modul tersebut. (Tingkat tanggung jawab).
2. **Efferent Coupling ($C_e$)**: Jumlah kelas di dalam modul yang bergantung pada kelas di luar modul tersebut. (Tingkat ketergantungan).
3. **Instability ($I$)**:
   $$I = \frac{C_e}{C_a + C_e} \quad (I \in [0, 1])$$
   * $I = 0$: Modul sangat stabil (sulit diubah karena banyak yang bergantung padanya).
   * $I = 1$: Modul sangat tidak stabil (mudah diubah karena tidak ada yang bergantung padanya).
4. **Abstractness ($A$)**: Rasio antara jumlah kelas/interface abstrak ($N_a$) terhadap total kelas ($N$).
   $$A = \frac{N_a}{N} \quad (A \in [0, 1])$$
5. **Distance from the Main Sequence ($D$)**: Deviasi dari rasio ideal antara stabilitas dan abstraksi:
   $$D = |A + I - 1| \quad (D \in [0, 1])$$
   Modul arsitektur yang ideal harus mendekati garis *Main Sequence* ($A + I = 1$). Modul di dekat $(A=0, I=0)$ berada di *Zone of Pain* (kaku, konkret, sulit diubah), sedangkan $(A=1, I=1)$ berada di *Zone of Uselessness* (terlalu abstrak tanpa implementasi riil).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Architectural Boundary Enforcement

```text
+-------------------------------------------------------------------------------+
|                       CLEAN / HEXAGONAL ARCHITECTURE GATES                    |
+-------------------------------------------------------------------------------+
|                                                                               |
|  [ INFRASTRUCTURE LAYER ]                                                     |
|  +-------------------------------------------------------------------------+  |
|  | PostgresAdapter, KafkaPublisher, RestController, RedisCache            |  |
|  +-------------------------------------------------------------------------+  |
|         │                                                       ▲             |
|         │ (Allowed: Implements ports)                          │ (FORBIDDEN)  |
|         ▼                                                       │             |
|  [ APPLICATION SERVICES / USE CASES ]                           │ ArchUnit    |
|  +-----------------------------------------------------------+  │ Triggers    |
|  | ProcessOrderService, CancelOrderService                   |  │ Pipeline    |
|  +-----------------------------------------------------------+  │ Failure!    |
|         │                                                       │             |
|         │ (Allowed: Operates on aggregates)                     │             |
|         ▼                                                       │             |
|  [ DOMAIN LAYER (CORE BUSINESS LOGIC) ]                         │             |
|  +-----------------------------------------------------------+  │             |
|  | Entities, Value Objects, Domain Events, Domain Services   ├──┴─────────────+
|  +-----------------------------------------------------------+
|    NO DEPENDENCIES OUTSIDE DOMAIN PERMITTED (Pure Invariant)
|
+-------------------------------------------------------------------------------+
```

### 2. CI/CD Architectural Verification Pipeline

```text
[ Git Push / PR Created ]
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ STAGE 1: Static Architectural Fitness Functions        │
│ ------------------------------------------------------ │
│ - ArchUnit: Package Layer Violations Check             │
│ - ArchUnit: Cyclic Dependency Detection                │
│ - Modularity Metric Guard: Max D-Score <= 0.3          │
└──────────────────────────┬─────────────────────────────┘
                           │ Passed
                           ▼
┌────────────────────────────────────────────────────────┐
│ STAGE 2: Ephemeral Environment Deployment              │
│ ------------------------------------------------------ │
│ - Spin-up Containerized Target Architecture            │
│ - Seed baseline test dataset                           │
└──────────────────────────┬─────────────────────────────┘
                           │ Succeeded
                           ▼
┌────────────────────────────────────────────────────────┐
│ STAGE 3: Dynamic Architectural Fitness Functions       │
│ ------------------------------------------------------ │
│ - k6 Load Test: Scalability (Linear resource usage)    │
│ - k6 Latency Test: P99 <= 120ms at 2,000 RPS           │
│ - Chaos Inject (Chaos Mesh): Kill Pod -> Availability  │
│   Assertion: Failover < 3s, HTTP Error Rate < 0.05%    │
└──────────────────────────┬─────────────────────────────┘
                           │ Passed
                           ▼
[ PR Approved / Merged to Production Trunk ]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah contoh implementasi Static Fitness Function menggunakan Java dan ArchUnit untuk menegakkan aturan isolasi Domain Layer: **Domain tidak boleh memiliki referensi ke layer infrastruktur, framework Spring, atau library eksternal.**

```java
package com.enterprise.architecture.fitness;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchRule;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

public class ArchitectureSanityFitnessTest {

    private final JavaClasses codebase = new ClassFileImporter()
            .importPackages("com.enterprise.app");

    @Test
    @DisplayName("Fitness Function: Domain Layer Must Be Completely Isolated")
    void domain_layer_should_not_depend_on_any_outer_layers() {
        ArchRule domainIsolationRule = noClasses()
                .that().resideInAPackage("..domain..")
                .should().dependOnClassesThat()
                .resideInAnyPackage("..infrastructure..", "..application..", "..interfaces..");

        domainIsolationRule.check(codebase);
    }

    @Test
    @DisplayName("Fitness Function: No Circular Dependencies Across Slices")
    void packages_should_be_free_of_cycles() {
        ArchRule cycleFreeRule = slices()
                .matching("com.enterprise.app.(*)..")
                .should().beFreeOfCycles();

        cycleFreeRule.check(codebase);
    }

    @Test
    @DisplayName("Fitness Function: Entities Must Enforce Strict Encapsulation")
    void entity_fields_must_be_private_or_protected() {
        ArchRule encapsulationRule = classes()
                .that().resideInAPackage("..domain.model..")
                .should().haveOnlyPrivateConstructors()
                .orShould().haveOnlyProtectedConstructors();

        encapsulationRule.check(codebase);
    }
}
```

Jika seorang software engineer melakukan impor kelas `com.enterprise.app.infrastructure.persistence.OrderJpaEntity` ke dalam `com.enterprise.app.domain.OrderAggregate`, eksekusi `mvn test` akan gagal dan menolak commit secara langsung.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Contoh menyeluruh ini mengintegrasikan **Dynamic Latency Fitness Function** menggunakan k6 yang dieksekusi di pipeline GitHub Actions. Jika P99 Tail Latency melebihi ambang batas atau *error rate* meningkat di bawah beban, pipeline akan gagal (*circuit breaker deployment*).

### 1. Script Uji Kinerja Karakteristik Arsitektur (`latency_scalability_fitness.js`)

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom Metrik Arsitektural
const failureRate = new Rate('architectural_failures');
const p99OrderLatency = new Trend('order_processing_latency', true);

export const options = {
  scenarios: {
    // Skenario Latensi: Beban konstan untuk memverifikasi Steady-State Latency
    latency_verification: {
      executor: 'constant-arrival-rate',
      rate: 1500, // 1,500 requests per second
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 100,
      maxVUs: 300,
    },
    // Skenario Skalabilitas: Peningkatan drastis (Spike Stress)
    scalability_stress_burst: {
      executor: 'ramping-arrival-rate',
      startRate: 100,
      timeUnit: '1s',
      preAllocatedVUs: 200,
      maxVUs: 1000,
      stages: [
        { duration: '30s', target: 500 },
        { duration: '1m', target: 3000 }, // Ramp-up masif
        { duration: '30s', target: 100 },  // Cool-down
      ],
      startTime: '2m', // Dimulai setelah skenario latensi selesai
    },
  },
  thresholds: {
    // ATURAN ARCHITECTURAL FITNESS: P99 Tail Latency < 120ms
    'http_req_duration{scenario:latency_verification}': ['p(99)<120'],
    
    // ATURAN ARCHITECTURAL FITNESS: Scalability Stress Failure < 0.5%
    'architectural_failures': ['rate<0.005'],
    
    // ATURAN ARCHITECTURAL FITNESS: System Max Latency P95 saat Burst < 300ms
    'http_req_duration{scenario:scalability_stress_burst}': ['p(95)<300'],
  },
};

export default function () {
  const payload = JSON.stringify({
    customerId: "cust-981249",
    items: [
      { sku: "SKU-PROD-01", quantity: 2 },
      { sku: "SKU-PROD-09", quantity: 1 }
    ],
    currency: "USD",
    checkoutTimestamp: Date.now()
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Trace-Sampled': 'true',
    },
    timeout: '2s'
  };

  const res = http.post('http://api-gateway.internal.net/v1/orders', payload, params);

  // Evaluasi Respons
  const success = check(res, {
    'status code is 201': (r) => r.status === 201,
    'idempotency header present': (r) => r.headers['X-Idempotency-Key'] !== undefined,
  });

  if (!success) {
    failureRate.add(1);
  } else {
    failureRate.add(0);
    p99OrderLatency.add(res.timings.duration);
  }

  sleep(0.01);
}
```

### 2. GitHub Actions Automation Workflow (`.github/workflows/architecture-fitness.yml`)

```yaml
name: Architecture Quality Gate

on:
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  static-structural-fitness:
    name: Run Static Fitness Tests (ArchUnit)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Codebase
        uses: actions/checkout@v4

      - name: Setup JDK 21
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'
          cache: maven

      - name: Execute Architectural Rules
        run: mvn clean test -Dtest=*FitnessTest

  dynamic-operational-fitness:
    name: Run Operational Dynamic Fitness (k6 Gate)
    needs: static-structural-fitness
    runs-on: ubuntu-latest
    services:
      order-service:
        image: ghcr.io/enterprise/order-service:${{ github.sha }}
        ports:
          - 8080:8080
        env:
          SPRING_PROFILES_ACTIVE: performance-test

    steps:
      - name: Checkout Codebase
        uses: actions/checkout@v4

      - name: Pull k6 Modern Runner
        run: docker pull grafana/k6:latest

      - name: Execute Dynamic Latency & Scalability Fitness Function
        run: |
          docker run --rm -i \
            --network="host" \
            -v $(pwd)/tests/perf:/tests \
            grafana/k6:latest run /tests/latency_scalability_fitness.js

      - name: Assert Pipeline Fitness Report
        if: failure()
        run: |
          echo "::error::Architectural Fitness Function failed! System violated latency or scalability SLA limits."
          exit 1
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Setiap keputusan arsitektur adalah kompromi (*trade-off*). Mengoptimalkan satu atribut hampir selalu mengorbankan atribut lain.

```text
+-----------------------+-----------------------+---------------------------------------------+
| Keputusan / Prioritas | Menguntungkan (+)     | Mengorbankan (-)                            |
+-----------------------+-----------------------+---------------------------------------------+
| Active-Active Multi-  | Availability: Tinggi  | Latency: Meningkat (akibat koordinasi       |
| Region Replication   | (Zero Downtime)       | write/cross-region konsensus). Biaya tinggi.|
+-----------------------+-----------------------+---------------------------------------------+
| Deep Layer Isolation  | Modifiability: Tinggi | Latency: Penurunan performa mikro (indirection|
| (Hexagonal + DTOs)    | Kopling rendah        | overhead, alokasi memori objek mapping).    |
+-----------------------+-----------------------+---------------------------------------------+
| In-Memory Caching     | Latency: Menurun drastis| Scalability & Modifiability: Kompleksitas   |
| Aggressive Strategy   | Throughput: Meningkat | cache invalidation, risiko stale data (CAP).|
+-----------------------+-----------------------+---------------------------------------------+
| Microservices Decoupled| Scalability: Independen| Latency: Jaringan RPC menambah RTT.       |
| by Domain Boundaries  | Modifiability: Tinggi | Availability: Butuh circuit breakers/retries|
+-----------------------+-----------------------+---------------------------------------------+
| Heavy Async Messaging | Latency (Client POV)  | Modifiability (Observabilitas alur bisnis   |
| (EDA / Event-Driven)  | Scalability: Elatis   | menjadi rumit, konsistensi data eventual).  |
+-----------------------+-----------------------+---------------------------------------------+
```

### Amdahl's Law dalam Konteks Scalability
Menambahkan node/core komputasi tidak meningkatkan skalabilitas secara linear jika terdapat komponen serial:
$$S_{\text{latency}}(s) = \frac{1}{(1 - p) + \frac{p}{s}}$$
Di mana $p$ adalah porsi sistem yang terparalelisasi, dan $s$ adalah faktor percepatan (*speedup*). Jika 10% dari kode transaksi Anda terikat pada *database lock* serial tunggal ($p = 0.9$), skalabilitas maksimum absolut sistem Anda dibatasi hingga $10\times$, terlepas dari penambahan ratusan replika server.

---

## SEKSI 11 — BEST PRACTICES

1. **Ubah NFR Menjadi Skenario Terdokumentasi (QAS Format)**: Jangan izinkan definisi non-fungsional tanpa 6 elemen wajib: *Source, Stimulus, Artifact, Environment, Response, dan Response Measure*.
2. **Fail Fast pada Static Fitness Functions**: Jalankan ArchUnit dan *package cycle analyzers* pada *pre-commit hook* atau tahap paling awal di CI pipeline. static checks berjalan dalam hitungan detik; dynamic load tests memakan waktu hitungan menit hingga jam.
3. **Simpan Fitness Function Dekat dengan Kode Sumber**: Hindari menaruh definisi arsitektural di dokumen wiki yang terpisah. Letakkan pengujian di direktori `/test/architecture/` di dalam repositori sistem itu sendiri.
4. **Hubungkan Architectural Decision Records (ADR) dengan Fitness Functions**: Setiap ADR yang diputuskan (misal: "ADR-004: Mengadopsi Outbox Pattern untuk Event Messaging") wajib menyertakan unit test atau verifikasi fitness function otomatis yang mengecek apakah implementasi sesuai keputusan tersebut.
5. **Implementasikan Progressive Stress Limits**: Tentukan *threshold* fitness function secara proporsional. Berikan margin toleransi degradasi (misal: P99 degradasi maksimum 5% per sprint) untuk mencegah false-alarm, namun tetap memblokir regresi substansial.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Mengabaikan "Long Tail Latency" (Menggunakan Average Latency)**: Latensi rata-rata menyembunyikan masalah serius. Jika rata-rata adalah 50ms, namun P99 adalah 4.000ms, maka 1 dari 100 pengguna Anda (atau 1 dari 100 panggilan RPC terdistribusi) mengalami degradasi sistem total.
2. **Arsitektur Berbasis Dokumen Pasif**: Arsitek membuat diagram Visio/Lucidchart yang indah, lalu tidak pernah memeriksanya lagi. Tanpa verifikasi berbasis kode (*executable architecture*), batas-batas desain akan terkikis dalam beberapa bulan oleh kebutuhan fitur mendesak.
3. **Menguji Latensi di Lingkungan Tiruan Tanpa Data**: Menguji endpoint pada database lokal kosong dengan 10 row data menghasilkan angka performa palsu. Uji latensi fitness function memerlukan representasi volume data produksi (*seed data*) dan latensi jaringan yang realistis.
4. **Kopling Tersembunyi (Hidden Coupling)**: Memisahkan modul ke dalam file/folder berbeda tetapi membiarkan mereka berbagi tabel basis data yang sama tanpa abstraksi (*Database-level coupling*). ArchUnit tidak dapat melihat ini; diperlukan database schema fitness rules.
5. **Fitness Functions Terlalu Otoriter/Rigid**: Mengunci sistem sedemikian ketat sehingga refaktorisasi internal yang aman malah memicu kegagalan pipeline. Fitness function harus menguji *invarian arsitektur*, bukan detail implementasi kelas privat.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Guided — Menulis ArchUnit Rule untuk Mencegah Kebocoran Layer
* **Konteks**: Modul `com.system.payment.domain` terdeteksi mengimpor dependensi Spring Data JPA dan AWS SDK.
* **Tugas**: Tulis aturan ArchUnit komprehensif yang memvalidasi bahwa seluruh *domain entities* dan *domain events*:
  1. Tidak menggunakan anotasi Spring/Framework (`org.springframework..`).
  2. Bebas dari package eksternal pihak ketiga kecuali dependensi standar pustaka inti bahasa (`java..`).
* **Keluaran**: Test file `DomainPurityFitnessTest.java` dengan status assertion hijau setelah mengisolasi dependensi tersebut.

### Latihan 2: Semi-Guided — Mengimplementasikan Cyclic Dependency & Instability Gate
* **Konteks**: Tim pengembang menambahkan dependensi baru antar modul secara sporadis sehingga sering terjadi *circular reference deadlock* saat *in-memory startup*.
* **Tugas**: 
  1. Tulis fitness function otomatis untuk memverifikasi bahwa antar *top-level slices* (modul fitur) tidak ada ketergantungan melingkar.
  2. Hitung metrik *Instability* ($I$) dari paket inti `com.system.core`. Pastikan paket tersebut memiliki nilai $I \le 0.3$.
* **Hint**: Manfaatkan `SlicesRuleDefinition.slices()` dan `metrics.ArchitectureMetrics` pada ArchUnit library.

### Latihan 3: Independent — Desain End-to-End Dynamic Resilience Fitness Function
* **Konteks**: Sistem transaksi e-commerce memiliki SLA Availability 99.95% dengan batas toleransi failover maksimum 5 detik ketika primary database crash.
* **Tugas**: 
  1. Buat pipeline skenario uji otomatis (bisa menggunakan script Bash/Python, k6, dan Docker Compose).
  2. Jalankan beban transaksi 500 RPS secara stabil.
  3. Matikan kontainer Primary DB secara mendadak (*chaos injection*).
  4. Ukur berapa lama waktu pemulihan hingga endpoint kembali merespons status `200 OK`.
  5. Buat assertion: Jika MTTR > 5 detik atau total data loss/inconsistency > 0, gagalkan build.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

**1. Sebuah sistem microservices memproses pesanan dengan rata-rata response time 40ms. Namun, metrik P99.9 menunjukkan angka 3.200ms. Arsitek sistem sebaiknya mengidentifikasi akar masalah di mana?**
* A. JVM Garbage Collection pause time, thread pool starvation, atau database lock contention serial.
* B. Rata-rata komputasi CPU algoritma domain model terlalu berat.
* C. Bandwidth jaringan upstream kehabisan kapasitas total secara menyeluruh.
* D. Kurangnya memori pada load balancer layer 7.
* *Jawaban yang benar*: **A**. Rata-rata yang sangat rendah dengan tail latency yang tinggi adalah indikator klasik dari antrean serial (*queuing delays*), kontensi penguncian (*locking*), atau interupsi periodik seperti GC stop-the-world pauses.

**2. Dalam formula metrik Martin, apa implikasi dari sebuah modul dengan Abstractness ($A = 0.1$) dan Instability ($I = 0.1$)?**
* A. Modul berada di Zone of Uselessness; banyak abstraksi yang tidak digunakan.
* B. Modul berada di Zone of Pain; modul sangat konkret, sulit diubah, tetapi banyak komponen lain bergantung padanya.
* C. Modul sangat modular, fleksibel, dan mudah direfaktorisasi tanpa resiko regresi.
* D. Modul memiliki ketergantungan melingkar yang tinggi.
* *Jawaban yang benar*: **B**. Modul dengan ketergantungan keluar sangat rendah ($I \to 0$, stabil/banyak yang bergantung padanya) dan abstraksi sangat rendah ($A \to 0$, murni implementasi konkret) berada di *Zone of Pain*, menjadikannya rigid dan sangat rapuh jika diubah.

**3. Pernyataan manakah yang paling akurat membedakan Functional Tests dengan Architectural Fitness Functions?**
* A. Functional tests dijalankan oleh QA; Architectural fitness functions dijalankan oleh DevOps.
* B. Functional tests memvalidasi *apa* yang dihasilkan sistem (*behavior correctness*); Fitness functions memvalidasi *bagaimana* karakteristik internal dan non-fungsional sistem dijaga saat kode berevolusi.
* C. Functional tests menggunakan assertions; Architectural fitness functions hanya menghasilkan visualisasi grafis tanpa status fail/pass.
* D. Functional tests diimplementasikan di CI; Architectural fitness functions hanya diimplementasikan di production runtime.
* *Jawaban yang benar*: **B**. Fitness functions bertindak sebagai penjaga integritas struktural dan atribut kualitas non-fungsional sistem melintasi siklus waktu, bukan sekadar memeriksa apakah $1 + 1 = 2$.

**4. Anda diminta merancang sistem dengan kriteria: "Sistem harus menangani lonjakan dari 1.000 menjadi 50.000 RPS dalam 30 detik tanpa penurunan latensi transaksi". Manakah strategi arsitektur yang paling tepat diuji oleh fitness function?**
* A. Horizontal Pod Autoscaler reaktif standar dengan scaling threshold 80% CPU.
* B. Predictive horizontal pre-provisioning atau autoscaling berbasis request-rate derivatif (bukan CPU semata), diuji dengan *ramp-up spike stress test*.
* C. Menambah kapasitas swap memori pada setiap node bare metal.
* D. Membungkus seluruh panggilan database dengan synchronous retries tak terbatas.
* *Jawaban yang benar*: **B**. CPU-based reactive autoscaling pada umumnya memakan waktu 2–5 menit untuk provisioning node baru, yang akan menyebabkan drop request pada lonjakan 30 detik. Skalabilitas elastis harus dirancang proaktif dan diuji dengan dynamic ramping fitness tests.

**5. Manakah karakteristik skenario di bawah ini yang TIDAK memenuhi format standar Quality Attribute Scenario (QAS) yang terukur?**
* A. "Pengguna eksternal melakukan 2.000 permintaan login serentak saat database sedang failover; sistem harus mengembalikan respons dalam < 500ms dengan tingkat kegagalan < 1%."
* B. "Developer baru menambahkan controller; sistem harus memvalidasi tidak ada circular dependency dalam kompilasi CI."
* C. "Sistem harus dirancang seaman mungkin menggunakan enkripsi terbaik agar hacker tidak dapat menembus basis data internal."
* D. "Sistem monitoring menginjeksi lonjakan traffic; artifact cache layer harus menjaga hit ratio > 90% pada steady-state."
* *Jawaban yang benar*: **C**. Pernyataan ini ambigu, menggunakan kata sifat subjektif ("seaman mungkin", "enkripsi terbaik"), tidak memiliki stimulus kuantitatif, tanpa lingkungan operasional spesifik, dan tanpa ukuran respons numerik (*response measure*).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Wajib**:
  * Ford, N., Parsons, R., Kua, P., & Sadalage, P. (2021). *Building Evolutionary Architectures: Automated Software Governance* (2nd Edition). O'Reilly Media.
  * Bass, L., Clements, P., & Kazman, R. (2021). *Software Architecture in Practice* (4th Edition). Addison-Wesley Professional.
  * Martin, R. C. (2017). *Clean Architecture: A Craftsman's Guide to Software Structure and Design*. Prentice Hall.
* **Standar Industri & Riset Formal**:
  * ISO/IEC 25010:2023 — *Systems and software engineering — Systems and software Quality Requirements and Evaluation (SQuaRE) — Product quality model*.
  * Dean, J., & Barroso, L. A. (2013). *The Tail at Scale*. Communications of the ACM, 56(2), 74-80.
* **Perkakas (Tooling)**:
  * [ArchUnit](https://www.archunit.org/) — Java architectural testing library.
  * [k6 by Grafana](https://k6.io/) — Modern developer-centric dynamic load and resilience testing tool.
  * [Chaos Mesh](https://chaos-mesh.org/) — Cloud-native Chaos Engineering platform for dynamic availability assertions.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Karakteristik kualitas arsitektur (*Availability, Latency, Scalability, Modifiability*) adalah fondasi non-fungsional penentu kelangsungan hidup perangkat lunak. Persyaratan ini tidak boleh dibiarkan ambigu dan harus diformulasikan ke dalam **Quality Attribute Scenarios (QAS)** yang memiliki parameter pengukuran konkret.
2. Latensi harus selalu dievaluasi menggunakan metrik distribusi persentil (**Tail Latency: P95, P99, P99.9**) untuk mengidentifikasi kontensi antrean dan starvation yang tersembunyi di balik angka rata-rata.
3. Arsitektur perangkat lunak secara alami mengalami degradasi (*architectural drift*) seiring waktu akibat tekanan kecepatan rilis.
4. **Architectural Fitness Functions** adalah pendekatan revolusioner dari paradigma *Evolutionary Architecture* untuk mengubah tata kelola arsitektur (*governance*) dari sekadar dokumen pasif menjadi kode verifikasi aktif (*executable tests*) di dalam CI/CD pipeline.
5. Kombinasi verifikasi statis (*Static Fitness Functions* via ArchUnit/metrics) dan dinamis (*Dynamic Fitness Functions* via load testing & chaos injection) menjamin sistem berevolusi secara modular tanpa mengorbankan stabilitas operasional.

---

## SEKSI 17 — GLOSARIUM

* **Architectural Drift**: Fenomena di mana implementasi sistem perlahan-lahan menyimpang dari arsitektur yang direncanakan semula karena perubahan kode yang tidak terkawal.
* **Tail Latency**: Waktu respons pada persentil ekstrem teratas dari populasi distribusi (misal P99 atau P99.9), merepresentasikan latensi terburuk yang dialami subset pengguna.
* **Quality Attribute Scenario (QAS)**: Format baku yang terdiri dari 6 komponen (Source, Stimulus, Artifact, Environment, Response, Measure) untuk mendeskripsikan kebutuhan kualitas sistem secara presisi.
* **Afferent Coupling ($C_a$)**: Jumlah kelas di luar modul yang bergantung pada modul tersebut.
* **Efferent Coupling ($C_e$)**: Jumlah kelas di dalam modul yang bergantung pada modul lain di luar dirinya.
* **Instability Index ($I$)**: Metrik struktural ($C_e / (C_a + C_e)$) yang menentukan ketahanan modul terhadap perubahan.
* **Zone of Pain**: Kondisi arsitektural di mana sebuah modul sangat stabil ($I \to 0$) tetapi sangat konkret ($A \to 0$), membuatnya sangat kaku dan berisiko tinggi saat dimodifikasi.
* **Evolutionary Architecture**: Pola arsitektur yang mendukung perubahan incremental dan terpandu di berbagai dimensi kualitas menggunakan fitness functions.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan**: Tegaskan kepada peserta didik bahwa mendefinisikan NFR tanpa *response measure* numerik adalah dosa arsitektur terburuk. Tolak tugas peserta jika mereka masih menulis deskripsi seperti *"sistem harus scalable"* atau *"latensi harus minimal"*.
* **Tantangan Praktik**: Dalam latihan ArchUnit, pengembang yang terbiasa dengan fleksibilitas Spring sering kali tergoda melakukan `@Autowired` komponen infrastruktur langsung ke domain. Gunakan kegagalan build lokal untuk menanamkan pemahaman *Ports & Adapters*.
* **Simulasi Nyata**: Untuk dynamic fitness test, disarankan tidak mengeksekusi pengujian performa di mesin pengembang (*localhost*) karena variasi background process lokal merusak validitas data P99. Arahkan peserta menggunakan container runner khusus atau pipeline agent terisolasi.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal | Perubahan | Author |
| :--- | :--- | :--- | :--- |
| `1.0.0` | 2025-02-15 | Inisialisasi materi perdana modul Architecture Quality Attributes & Fitness Functions | System Architecture Curriculum Guild |
| `1.1.0` | 2025-02-18 | Penambahan formula kuantitatif Martin's Metrics dan integrasi implementasi skrip k6 dynamic fitness gate | Senior Technical Curriculum Architect |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `ARCH-06-B01-M02` — *Domain-Driven Design (DDD) Strategic & Tactical Patterns in Distributed Systems*
* **Modul Sekarang**: `ARCH-06-B02-M01` — *Software Quality Attributes & Fitness Functions: Karakteristik Arsitektur & Automated Fitness Verification*
* **Modul Berikutnya**: `ARCH-06-B02-M02` — *Data Architecture: Polyglot Persistence, CQRS, Event Sourcing, & Distributed Consistency Models*