# Kurikulum Enterprise: Spring Boot (Bab 09 - Modul 02)
## Enterprise Testing Strategy: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membedah** cara kerja internal Spring TestContext Framework (TCF), khususnya mekanisme kalkulasi cache context (`MergedContextConfiguration`) guna mengeliminasi overhead *cold start* pengujian.
- **Merancang dan Mengimplementasikan** arsitektur *integration test* berbasis *real infrastructure* menggunakan Testcontainers secara terisolasi, deterministik, dan *ephemeral* (PostgreSQL, Apache Kafka, Redis).
- **Menerapkan Pola Singleton Container Pattern** dan `@DynamicPropertySource` untuk meminimalkan *spin-up overhead* pada CI/CD pipeline berskala enterprise.
- **Mengeliminasi Anti-Pattern Pengujian** seperti penggunaan `@DirtiesContext` secara serampangan, ketergantungan pada *in-memory DB* (H2) yang memunculkan *false positives*, serta *flaky tests* akibat *asynchronous race conditions*.
- **Mengeksekusi Consumer-Driven Contract Testing (CDCT)** menggunakan Pact / Spring Cloud Contract untuk memvalidasi kompatibilitas komunikasi microservices terdistribusi tanpa memerlukan *full end-to-end environment*.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
- **Java 21 LTS**: Fitur *records*, *sealed interfaces*, *pattern matching*, dan struktur konkurensi modern.
- **Spring Boot 3.3+ Core Internals**: Dependency Injection, Auto-Configuration, ApplicationContext lifecycle.
- **Dasar Testing**: JUnit 5 Platform (`@ExtendWith`, dynamic lifecycle hooks), Mockito, AssertJ.
- **Containerization Fundamentals**: Docker architecture, bridge networking, bind mounts, serta Docker socket communication (`/var/run/docker.sock`).
- **Database Migrations**: Flyway atau Liquibase workflow.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Spring TestContext Framework (TCF) Lifecycle & Context Caching Internals
Ketika sebuah *test class* dieksekusi dengan `@SpringBootTest`, Spring tidak serta merta membuat `ApplicationContext` baru untuk setiap kelas. Spring mengandalkan `TestContextManager`, yang mendelegasikan pemuatan konteks ke `CacheAwareContextLoaderDelegate`.

```
[JUnit 5 Test Runner]
       │
       ▼
[TestContextManager]
       │
       ▼
[CacheAwareContextLoaderDelegate] ───(Look up)───► [ContextCache (DefaultContextCache)]
       │                                                    │
       ├── Context Ditemukan (Cache HIT) ◄──────────────────┤ (Key: MergedContextConfiguration)
       │   └── Inject dependencies ke Test Class             │
       │                                                    │
       └── Context Tidak Ada (Cache MISS) ──────────────────┘
           ├── Bootstrap Context via ApplicationContextFactory
           ├── Jalankan EnvironmentPostProcessor & BeanDefinitionLoader
           ├── Simpan di ContextCache Map
           └── Return Context instance
```

##### Struktur Kunci `MergedContextConfiguration`
Kunci cache konteks diturunkan dari konfigurasi unik yang dikompilasi ke dalam `MergedContextConfiguration`. Jika dua buah kelas pengujian memiliki sedikit saja perbedaan pada komponen berikut, Spring menganggapnya sebagai *cache miss*:
1. `locations` / `classes` (konfigurasi root)
2. `activeProfiles`
3. `propertySourceDescriptors` / `inline properties` (misal `@SpringBootTest(properties = "...")`)
4. `contextCustomizers` (termasuk yang digenerate oleh `@MockBean`, `@SpyBean`, `@DynamicPropertySource`)

> **Catatan Kritis**: Penggunaan `@MockBean` pada sebuah *test class* secara dinamis menambahkan `MockitoContextCustomizer` ke dalam set `ContextCustomizers`. Akibatnya, `MergedContextConfiguration` berubah, memicu pembuatan `ApplicationContext` baru secara penuh dan menggandakan waktu eksekusi CI/CD.

#### B. Testcontainers Internal Architecture: Docker Socket & Ryuk
Testcontainers memanfaatkan Java Docker Client API yang berkomunikasi via UNIX Domain Socket (`/var/run/docker.sock`) atau TCP Socket (Docker for Mac/Windows/Remote). 

1. **Resource Reaper (Moby / Ryuk)**: 
   Saat JVM menginisialisasi `org.testcontainers.DockerClientFactory`, container `testcontainers/ryuk` otomatis diorkestrasi terlebih dahulu. Ryuk membuka koneksi TCP duplex dua arah dengan Java runtime. Jika JVM crash, terbunuh (`SIGKILL`), atau selesai secara normal, koneksi terputus dan Ryuk mengeksekusi penghapusan massal container, network, dan volume berlabel `org.testcontainers=true`.
2. **Ephemeral Port Allocation**: 
   Testcontainers tidak pernah melakukan *hardcode port binding* host (seperti `5432:5432`). Host port dialokasikan secara acak oleh Docker engine (misal `49152:5432`), menghindari tabrakan port pada server CI/CD paralel. Host port dinamis ini kemudian diinjeksikan ke dalam `ConfigurableEnvironment` Spring Boot melalui abstraksi `@DynamicPropertySource`.

---

### 4. Why & What

| Dimensi | In-Memory (H2, Fongo, Embedded Kafka) | Real Engine via Testcontainers |
| :--- | :--- | :--- |
| **Paritas Fitur Engine** | Rendah. Dialek SQL berbeda, tidak mendukung tipe data spesifik (PostgreSQL `JSONB`, spatial index, extensions). | 100% Identik dengan Production (Production-like fidelity). |
| **State Isolation** | Rapuh. Sering terjadi residu data antar-test class jika *thread pool* lambat di-*reset*. | Tinggi. Container dapat di-wipe atau di-*reset* secara atomik. |
| **Konkurensi & Locking**| Locking semantics H2 sangat primitif dibandingkan MVCC (Multi-Version Concurrency Control) PostgreSQL. | Validasi transaksi `SELECT ... FOR UPDATE` dan deadlock berjalan nyata. |
| **Startup Overhead** | Sangat cepat (~50-200ms). | Moderat (~2-5 detik pertama kali via image pulling & container start). |
| **Reliabilitas Pengujian**| Rawan menimbulkan *false positives* (Lolos di test, crash di production). | Sangat deterministik; mengeliminasi risiko kegagalan tak terduga saat rilis. |

---

### 5. How (Workflow Detail)

Alur integrasi pengujian skala produksi yang optimal mengikuti alur:

```
[Commit Code] 
      │
      ▼
1. Unit Tests Execution (Pure Mockito, fast feedback < 10s)
      │
      ▼
2. Architecture & Contract Tests (ArchUnit, Pact Consumer Tests)
      │
      ▼
3. Slice Tests Execution (@JsonTest, @WebMvcTest, Mocked Service layer)
      │
      ▼
4. Distributed Integration Tests
      │
      ├── Setup Testcontainers Base Infrastructure (Postgres, Kafka, Redis)
      ├── Apply Schema Migrations (Flyway/Liquibase)
      ├── Dynamic Property Registration (dynamic ports injection)
      ├── Execute Scenarios with Awaitility for Asynchronous Assertions
      │
      ▼
5. Context Teardown (Singleton Containers preserved until JVM termination)
      │
      ▼
[Build Artifact & Publish]
```

---

### 6. Analogy & Diagram ASCII

#### Context Pollution vs Shared Context Cache
Bayangkan `ApplicationContext` adalah sebuah **Laboratorium Steril**. 

```
Model A: Dirtying Context (@DirtiesContext atau Flawed @MockBean)
========================================================================
[Test Class A] ──> [Buka Lab 1 (Context Baru: 15 detik)] ──> Eksekusi ──> Lab Terkontaminasi!
                                                                                │
[Test Class B] ──> [Hancurkan Lab 1, Buka Lab 2 (15 detik)] ──> Eksekusi ◄──────┘ (Total: 30 detik)

Model B: Clean Shared Context (Production-Grade Test Strategy)
========================================================================
[Test Class A] ──┐
                 ├───► [Buka Lab Steril 1 (15 detik)] ──> Bersihkan DB (10ms)
[Test Class B] ──┘                                    ──> Eksekusi Class B Langsung! (Total: 15.01 detik)
```

---

### 7. Practical Implementation (Standar Industri)

Implementasi arsitektur dasar pengujian terdistribusi: PostgreSQL 16 + Apache Kafka + Redis, memanfaatkan *Shared Singleton Container Pattern* untuk memaksimalkan *reuse* konteks Spring.

#### Struktur Direktori Modul
```
src/test/java/com/enterprise/testing/
├── infrastructure/
│   └── BaseIntegrationTest.java
├── ledger/
│   ├── LedgerServiceIntegrationTest.java
│   └── LedgerSliceTest.java
```

#### A. Base Singleton Integration Test (Fondasi Kritis)
```java
package com.enterprise.testing.infrastructure;

import org.junit.jupiter.api.Tag;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.KafkaContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.utility.DockerImageName;

/**
 * Base abstract class yang mengelola lifecycle container eksternal.
 * Menggunakan manual static initialization untuk menjamin singleton container
 * hidup sepanjang keseluruhan lifecycle JVM JUnit, mencegah re-creation antar test class.
 */
@Tag("integration")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
public abstract class BaseIntegrationTest {

    private static final DockerImageName POSTGRES_IMAGE = DockerImageName.parse("postgres:16-alpine");
    private static final DockerImageName KAFKA_IMAGE = DockerImageName.parse("confluentinc/cp-kafka:7.6.0");
    private static final DockerImageName REDIS_IMAGE = DockerImageName.parse("redis:7.2-alpine");

    protected static final PostgreSQLContainer<?> POSTGRES_CONTAINER;
    protected static final KafkaContainer KAFKA_CONTAINER;
    protected static final GenericContainer<?> REDIS_CONTAINER;

    static {
        POSTGRES_CONTAINER = new PostgreSQLContainer<>(POSTGRES_IMAGE)
                .withDatabaseName("enterprise_db")
                .withUsername("sa")
                .withPassword("secret")
                .withReuse(true);
        POSTGRES_CONTAINER.start();

        KAFKA_CONTAINER = new KafkaContainer(KAFKA_IMAGE)
                .withReuse(true);
        KAFKA_CONTAINER.start();

        REDIS_CONTAINER = new GenericContainer<>(REDIS_IMAGE)
                .withExposedPorts(6379)
                .waitingFor(Wait.forLogMessage(".*Ready to accept connections.*\\n", 1))
                .withReuse(true);
        REDIS_CONTAINER.start();
    }

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        // Dynamic PostgreSQL Configuration
        registry.add("spring.datasource.url", POSTGRES_CONTAINER::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES