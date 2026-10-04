# Bab 09 Module 01: Enterprise Testing Strategy: Unit to Distributed Integration

---

## Seksi 01: Identitas Modul
* **Track:** Backend Engineering & Cloud Native Architecture
* **Kategori:** 04-Backend-and-Database
* **Topik:** Spring Boot Enterprise Architecture
* **Modul:** Bab 09 Module 01 — Enterprise Testing Strategy: Unit to Distributed Integration
* **Tingkat Kesulitan:** Advanced / Principal Engineer
* **Prasyarat:** Pemahaman mendalam tentang Spring Boot Core, Spring Data JPA, Spring Security, Docker/Containerization, Apache Kafka, RestTemplate/WebClient, dan Mockito.

---

## Seksi 02: Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. Merancang arsitektur pengujian piramida terdistribusi (*Test Pyramid*) yang mencakup *isolated unit testing*, *slice testing*, *containerized integration testing*, dan *Consumer-Driven Contract Testing*.
2. Mengimplementasikan pengujian unit berkinerja tinggi menggunakan JUnit 5, AssertJ, dan Mockito dengan mematuhi prinsip deterministik dan zero context overhead.
3. Mengoptimalkan siklus pengujian Spring Context melalui pemanfaatan Spring Test Slices (`@DataJpaTest`, `@WebMvcTest`) dan mitigasi degradasi cache ApplicationContext.
4. Mengoperasikan Testcontainers secara mutakhir (termasuk *Dynamic Property Source*, *Reusable Containers*, dan arsitektur *Singleton Container Pattern*) untuk PostgreSQL dan Apache Kafka.
5. Membangun dan memverifikasi kontrak komunikasi antar-layanan terdistribusi (*distributed contract testing*) menggunakan Pact.
6. Mengintegrasikan pengujian arsitektur deklaratif menggunakan ArchUnit guna menegakkan invariant arsitektural dan batas modular (*boundary enforcement*).

---

## Seksi 03: Concept Map Diagram (ASCII)

```
+-----------------------------------------------------------------------------------------+
|                              TEST PYRAMID & BOUNDARIES                                  |
+-----------------------------------------------------------------------------------------+
                                          / \
                                         /   \
                                        / E2E \  <-- Synthetic Canary, Distributed Tracing
                                       /-------\
                                      / Contract\  <-- Pact / Spring Cloud Contract
                                     /-----------\
                                    / Integration \  <-- Testcontainers (Postgres, Kafka)
                                   /---------------\
                                  / Component Slices\  <-- @WebMvcTest, @DataJpaTest
                                 /-------------------\
                                /     Unit Tests      \  <-- JUnit 5, AssertJ, Mockito
                               +-----------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------------+
|                        SPRING TEST CONTEXT MANAGEMENT PIPELINE                          |
+-----------------------------------------------------------------------------------------+
 [Test Execution] 
        |
        +---> Pure Unit Test? --------> (No Spring Context) -> Instant Execution (~ms)
        |
        +---> Slice Test? ------------> (@WebMvcTest / @DataJpaTest) -> Partial Context
        |
        +---> Full Integration Test? -> (@SpringBootTest + @Testcontainers)
                     |
                     +---> Context Cache Key Match? 
                                  |
                                  +--> YES: Reuse ApplicationContext (Fast)
                                  +--> NO : Instantiate & Bootstrap Context (~secs)
                                                 |
                                                 v
                                    Inject Dynamic Properties 
                                    (@DynamicPropertySource)
                                                 |
                                                 v
                                    Containers Lifecycle (Ryuk/Moby)
```

---

## Seksi 04: Mengapa Relevan

Dalam arsitektur sistem monolitik modular maupun microservices skala enterprise, pengujian perangkat lunak sering kali terjebak dalam dua ekstrem:
1. **The Inverted Test Pyramid (Ice-Cream Cone Anti-pattern):** Terlalu bergantung pada pengujian *end-to-end* (E2E) yang lambat, *flaky*, rapuh terhadap perubahan lingkungan, dan sulit di-debug.
2. **Mock-Heavy Unit Testing:** Unit test yang memberikan rasa aman semu (*false sense of security*) karena seluruh dependensi eksternal (basis data, message broker, downstream API) di-mock secara naif tanpa memvalidasi schema drift atau perilaku konkurensi dunia nyata.

Modul ini memberikan metodologi terstruktur untuk membangun sistem pengujian deterministik, cepat, dan representatif terhadap kondisi produksi. Dengan mengombinasikan *Slice Testing* untuk isolasi layer, *Testcontainers* untuk dependensi infrastruktur nyata, *Pact* untuk verifikasi kontrak API, dan *ArchUnit* untuk tata kelola arsitektur, organisasi dapat mencapai *Zero Defect Deployments* dengan pipeline CI/CD yang terukur.

---

## Seksi 05: Anatomi Konsep Inti

### 1. Spring Context Caching Engine & Dirty Context
Spring Test Framework memiliki kapabilitas *Context Caching*. Saat menjalankan test suite, Spring membuat *cache key* berdasarkan parameter konfigurasi (seperti `@ContextConfiguration`, `@ActiveProfiles`, `@TestPropertySource`). Jika test berikutnya memiliki profil dan konfigurasi yang sama persis, Spring me-reuse context tersebut.
* **Bahaya `@DirtiesContext`:** Anotasi ini memaksa Spring meruntuhkan (*teardown*) dan membangun ulang (*rebuild*) konteks aplikasi. Pada enterprise suite dengan ratusan integration test, penggunaan `@DirtiesContext` yang tidak terkontrol dapat mendegradasi waktu CI dari 3 menit menjadi 45 menit.

### 2. Spring Test Slices Architecture
Daripada memuat keseluruhan graph objek melalui `@SpringBootTest`, Spring menyediakan slice khusus:
* `@WebMvcTest`: Hanya memuat layer controller, filter, interceptor, dan converter. Layer service dan repository wajib di-mock menggunakan `@MockBean`.
* `@DataJpaTest`: Hanya mengonfigurasi JPA entities, Spring Data repositories, dan database connection (default: embedded/in-memory, disarankan di-override dengan real DB container). Menjalankan test secara transaksional secara default dan melakukan *rollback* di akhir pengujian.

### 3. Testcontainers & Dynamic Property Source
Testcontainers mengabstraksi Moby/Docker API untuk meluncurkan *disposable containers* selama test lifecycle.
* `@DynamicPropertySource`: Mekanisme statis untuk mendaftarkan properti dinamis (seperti dynamic port mapped oleh Docker host: `dbContainer.getMappedPort(5432)`) ke dalam Spring `Environment` sebelum `ApplicationContext` dikonfigurasi.

### 4. Consumer-Driven Contract Testing (CDCT)
Pada arsitektur terdistribusi, pengujian integrasi langsung antar-service (E2E) sangat mahal dan rentan *downtime*. CDCT membalik kontrol integrasi:
* **Consumer** mendefinisikan ekspektasi (kontrak JSON / schema / HTTP verb / response).
* Kontrak tersebut digenerate menjadi *Pact File* dan dipublikasikan ke Pact Broker.
* **Provider** mengunduh kontrak dan memvalidasi implementasi aktualnya secara independen tanpa bergantung pada runtime consumer.

### 5. Invariant Architecture Testing (ArchUnit)
ArchUnit menganalisis bytecode Java (menggunakan ASM) untuk mengevaluasi aturan arsitektur sistem secara otomatis, seperti: "Layer Controller tidak boleh mengakses Repository secara langsung" atau "Domain Model tidak boleh memiliki dependensi ke Framework Spring/Persistence".

---

## Seksi 06: Panduan Implementasi Step-by-Step

### Tahap 1: Konfigurasi Dependensi Maven Core Enterprise Testing
Pastikan dependensi berikut terdaftar di `pom.xml`:

```xml
<dependencies>
    <!-- Core Spring Test Starter -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-test</artifactId>
        <scope>test</scope>
    </dependency>

    <!-- Testcontainers Suite -->
    <dependency>
        <groupId>org.testcontainers</groupId>
        <artifactId>testcontainers</artifactId>
        <version>1.19.7</version>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.testcontainers</groupId>
        <artifactId>junit-jupiter</artifactId>
        <version>1.19.7</version>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.testcontainers</groupId>
        <artifactId>postgresql</artifactId>
        <version>1.19.7</version>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.testcontainers</groupId>
        <artifactId>kafka</artifactId>
        <version>1.19.7</version>
        <scope>test</scope>
    </dependency>

    <!-- Pact Contract Testing -->
    <dependency>
        <groupId>au.com.dius.pact.consumer</groupId>
        <artifactId>junit5</artifactId>
        <version>4.6.7</version>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>au.com.dius.pact.provider</groupId>
        <artifactId>junit5spring</artifactId>
        <version>4.6.7</version>
        <scope>test</scope>
    </dependency>

    <!-- ArchUnit Core -->
    <dependency>
        <groupId>com.tngtech.archunit</groupId>
        <artifactId>archunit-junit5</artifactId>
        <version>1.3.0</version>
        <scope>test</scope>
    </dependency>

    <!-- Awaitility for Asynchronous Verification -->
    <dependency>
        <groupId>org.awaitility</groupId>
        <artifactId>awaitility</artifactId>
        <version>4.2.1</version>
        <scope>test</scope>
    </dependency>
</dependencies>
```

### Tahap 2: Pola Singleton Testcontainer
Untuk mencegah pembuatan ulang container pada setiap test class yang menyebabkan fragmentasi resource dan eksekusi lambat, bangun base container abstract class.

---

## Seksi 07: Contoh Kasus Sederhana (Isolated Unit Test)

Berikut adalah contoh isolated unit test murni untuk domain logic tanpa memuat Spring Context sama sekali. Menggunakan AssertJ dan Mockito extension.

```java
package com.enterprise.order.domain;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class OrderPricingServiceTest {

    @Mock
    private DiscountPolicyPort discountPolicyPort;

    @InjectMocks
    private OrderPricingService pricingService;

    @Test
    @DisplayName("Harus menghitung harga total dengan potongan diskon jika diskon aktif")
    void shouldCalculateTotalWithDiscountSuccessfully() {
        // Arrange
        String customerId = "CUST-001";
        BigDecimal rawPrice = new BigDecimal("100.00");
        given(discountPolicyPort.findApplicablePercentage(customerId))
                .willReturn(Optional.of(new BigDecimal("0.15"))); // 15% discount

        // Act
        BigDecimal finalPrice = pricingService.calculateFinalPrice(customerId, rawPrice);

        // Assert
        assertThat(finalPrice)
                .isEqualByComparingTo(new BigDecimal("85.00"));
    }

    @Test
    @DisplayName("Harus melempar exception saat nilai raw price bernilai negatif")
    void shouldThrowExceptionWhenRawPriceIsNegative() {
        // Arrange
        String customerId = "CUST-001";
        BigDecimal invalidPrice = new BigDecimal("-10.00");

        // Act & Assert
        assertThatThrownBy(() -> pricingService.calculateFinalPrice(customerId, invalidPrice))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Price must be positive");
    }
}
```

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah arsitektur pengujian multi-layer lengkap untuk domain Order Processing yang melibatkan Database PostgreSQL, Apache Kafka, dan REST Endpoints.

### 1. Abstract Container Base (Reusable Infrastructure Context)

```java
package com.enterprise.order.infrastructure;

import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.KafkaContainer;
import org.testcontainers.utility.DockerImageName;

public abstract class AbstractIntegrationTestBase {

    private static final PostgreSQLContainer<?> POSTGRES_CONTAINER;
    private static final KafkaContainer KAFKA_CONTAINER;

    static {
        POSTGRES_CONTAINER = new PostgreSQLContainer<>(DockerImageName.parse("postgres:16-alpine"))
                .withDatabaseName("orders_test_db")
                .withUsername("test_user")
                .withPassword("test_password")
                .withReuse(true);

        KAFKA_CONTAINER = new KafkaContainer(DockerImageName.parse("confluentinc/cp-kafka:7.6.0"))
                .withReuse(true);

        POSTGRES_CONTAINER.start();
        KAFKA_CONTAINER.start();
    }

    @DynamicPropertySource
    static void registerDynamicProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES_CONTAINER::getJdbcUrl);
        registry.add("spring.datasource.username", POST