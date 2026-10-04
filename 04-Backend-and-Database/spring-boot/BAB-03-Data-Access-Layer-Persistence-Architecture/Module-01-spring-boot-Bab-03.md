# Data Access Layer & Persistence Architecture

---

## 01: Identitas Modul

* **Domain Kurikulum:** Backend Engineering & Enterprise Distributed Systems
* **Track:** Java / Spring Boot Ecosystem (`04-Backend-and-Database`)
* **Kode Modul:** `SB-PERSIST-03-001`
* **Prasyarat Pengetahuan:**
  * Core Java (Java 17/21+ LTS): Generics, Reflection, Dynamic Proxies, Concurrency (Virtual Threads/Platform Threads).
  * Dasar-dasar RDBMS: Relational Algebra, ACID Properties, Transaction Isolation Levels, Indexing (B-Tree/GIN).
  * Fundamental Spring: Application Context, Inversion of Control (IoC), Dependency Injection (DI), Spring Bean Lifecycle.
* **Tingkat Kompleksitas:** Advanced / Production-Grade Architecture
* **Target Runtime:** Spring Boot 3.3+, Spring Data JPA 3.3+, Hibernate 6.5+, PostgreSQL 16+, HikariCP 5.1+.

---

## 02: Learning Objectives

Setelah menyelesaikan modul ini, Principal/Senior Engineer ditargetkan mampu:

1. **Mendekonstruksi Lifecycle dan State Entity Hibernate 6:** Menganalisis transisi state (*Transient*, *Persistent/Managed*, *Detached*, *Removed*) serta mengontrol sinkronisasi `EntityManager` ke PostgreSQL melalui mekanisme *ActionQueue* dan write-behind caching.
2. **Merancang Dynamic Filtering & Query Composition Berkinerja Tinggi:** Mengimplementasikan dynamic query type-safe menggunakan JPA Criteria API, JPA Specifications, dan QueryDSL untuk mengeliminasi vulnerability runtime SQL error.
3. **Mengeliminasi N+1 Select Problem:** Menerapkan strategi optimasi query melalui `JOIN FETCH`, `@EntityGraph` (Dynamic/Named), Projections (DTO/Interface-based), dan Batch Fetching (`default_batch_fetch_size`).
4. **Mengonfigurasi Connection Pooling HikariCP Tingkat Lanjut:** Menghitung ukuran connection pool optimal berdasarkan rumus hardware saturation (Amdahl's/Little's Law) dan mengonfigurasi parameter *leak detection*, *timeout*, dan *statement caching*.
5. **Mengaudit dan Mengamankan Lapisan Akses Data:** Mencegah Blind SQL Injection, mengeksekusi Auditing terdistribusi via Spring Data Auditing / Hibernate Envers, serta memvalidasi query footprint via Micrometer metrics.

---

## 03: Concept Map Diagram

```
+----------------------------------------------------------------------------------------------------+
|                               SPRING DATA PERSISTENCE ARCHITECTURE                                 |
+----------------------------------------------------------------------------------------------------+
                                                │
                                    [Spring Application Context]
                                                │
               ┌────────────────────────────────┴────────────────────────────────┐
               ▼                                                                 ▼
   [Spring Data Repositories]                                       [Declarative Transactions]
   ├── JpaRepository<T, ID>                                         ├── @Transactional(ReadOnly=true/false)
   ├── JpaSpecificationExecutor<T>                                  ├── TransactionInterceptor (AOP)
   └── QuerydslPredicateExecutor<T>                                 └── PlatformTransactionManager
               │                                                                 │
               └────────────────────────────────┬────────────────────────────────┘
                                                ▼
                                    [Hibernate 6.x JPA Engine]
                                                │
               ┌────────────────────────────────┼────────────────────────────────┐
               ▼                                ▼                                ▼
      [Entity Lifecycle]               [Query Optimizations]             [First-Level Cache]
      ├── Transient                     ├── EntityGraph (Fetch/Load)     ├── Persistence Context
      ├── Managed                       ├── Projections (DTO/Tuple)      └── ActionQueue (Flush Mode)
      ├── Detached                      └── Criteria / QueryDSL                          │
      └── Removed                               │                                        │
               │                                └────────────────────────────────────────┘
               └────────────────────────────────┬────────────────────────────────┘
                                                ▼
                                   [JDBC Layer & Connection Pool]
                                                │
                                  [HikariCP Connection Pool]
                                  ├── MaximumPoolSize Calculation
                                  ├── ConnectionTimeout / IdleTimeout
                                  └── LeakDetectionThreshold
                                                │
                                                ▼
                                    [PostgreSQL 16 Engine]
                                  ├── Relational Engine / WAL
                                  └── MVCC & Transaction Isolation
```

---

## 04: Mengapa Relevan

Lapisan Data Access (*Persistence Layer*) merupakan subsistem dengan tingkat kegagalan performa (*latency degradation*) dan resource contention tertinggi dalam arsitektur backend enterprise. Sebagian besar insiden sistem berskala masif tidak bersumber dari lapisan transport (HTTP/gRPC), melainkan degradasi throughput database akibat:

1. **Abstraksi ORM yang Bocor (*Leaky Abstraction*):** Pengembang sering memperlakukan ORM sebagai in-memory collection, memicu ribuan kueri SQL tidak efisien (*N+1 problem*), Cartesian Product joins, dan saturasi memory pada heap space (OOM).
2. **Koneksi Database Sebagai Scarce Resource:** Thread contention pada connection pool terjadi ketika ukuran HikariCP dikonfigurasi secara sembarangan, menyebabkan connection starving dan request timeout berantai (*cascading failure*).
3. **Dirty Writes dan Concurrency Anomaly:** Ketidakpahaman atas Entity State dan Transaction Isolation (Read Committed vs Repeatable Read) menyebabkan inkonsistensi data finansial atau inventaris yang krusial.

Penguasaan arsitektur ini membedakan software engineer pemula yang hanya menggunakan antarmuka boilerplate `CrudRepository` dengan Principal/Lead Engineer yang mampu merancang sistem pemrosesan jutaan transaksi per detik dengan latensi persentil P99 di bawah 10ms.

---

## 05: Anatomi Konsep Inti

### 1. JPA & Hibernate 6 Architecture Internals
Hibernate 6 mentranslasikan Java Persistence API ke dalam Abstract Syntax Tree (AST) baru yang disebut **Semantic Query Model (SQM)**. SQM menghasilkan SQL native yang lebih ramping dan teroptimasi dibandingkan arsitektur HQL berbasis Antlr v2 lama pada Hibernate 5.

```
+-------------------------------------------------------------------------------------+
|                                 HIBERNATE 6 INTERNAL ENGINE                         |
+-------------------------------------------------------------------------------------+
|  [HQL / Criteria Query] ──> [Semantic Query Model (SQM)] ──> [SQL AST] ──> [Native SQL] |
+-------------------------------------------------------------------------------------+
```

### 2. Entity Lifecycle States
Setiap objek yang dikelola oleh JPA berada dalam salah satu dari empat status relasional terhadap `Persistence Context`:

* **Transient (New):** Objek diinisialisasi via operator `new`. Tidak memiliki database identity (`@Id` bernilai `null` atau default) dan belum diasosiasikan dengan session.
* **Managed (Persistent):** Objek diasosiasikan dengan `EntityManager` aktif dan memiliki representasi primary key pada database. Segala mutasi field via setter akan dipantau via dirty-checking engine saat session flush.
* **Detached:** Objek memiliki database identity namun session/EntityManager yang memuatnya telah ditutup (`em.close()`) atau di-clear (`em.clear()`). Mutasi state tidak dipantau secara otomatis.
* **Removed:** Objek ditandai untuk dihapus dari database melalui `em.remove(entity)` dan akan dieksekusi melalui SQL `DELETE` saat proses flush.

```
       [new Entity()]
             │
             ▼
      +──────────────+    persist() / save()     +──────────────+
      |  TRANSIENT   | ────────────────────────> |   MANAGED    | ◄─────────┐
      +──────────────+                           +──────────────+           │
                                                   │     │   ▲              │
                            close() / clear() /    │     │   │ merge()      │ find() /
                            detach()               │     │   │              │ query
                                                   ▼     ▼   │              │
                                         +──────────────+  +──────────────+ │
                                         |   DETACHED   |  |   REMOVED    | │
                                         +──────────────+  +──────────────+ │
                                                                 │          │
                                                                 ▼          │
                                                          [DB DELETE SQL]   │
                                                                            │
      Database Record ──────────────────────────────────────────────────────┘
```

### 3. Flush Type & ActionQueue Execution
Dirty-checking mengevaluasi seluruh managed entity saat `FlushModeType.AUTO` (default) terpicu. Hibernate tidak langsung mengirim statement SQL ke PostgreSQL setiap kali setter dipanggil. Seluruh mutasi dijadwalkan dalam `ActionQueue` internal dengan urutan deterministik:
1. `EntityInsertAction` / `EntityIdentityInsertAction`
2. `EntityUpdateAction`
3. `CollectionRemoveAction`
4. `CollectionUpdateAction`
5. `CollectionRecreateAction`
6. `EntityDeleteAction`

### 4. N+1 Problem & Fetch Strategies
N+1 problem terjadi ketika pengambilan $N$ parent records menghasilkan $1$ initial query ditambah $N$ query susulan untuk mengambil relasi *Lazy-loaded*.

$$\text{Total Queries} = 1 + N$$

* **Dynamic Fetching (`JOIN FETCH`):** Melakukan `INNER JOIN` atau `LEFT JOIN` secara eksplisit pada query HQL/JPQL untuk meng-eager load asosiasi dalam single network round-trip.
* **Entity Graph (`@EntityGraph`):** Menyediakan template declaratif (*FetchGraph* vs *LoadGraph*) untuk menentukan atribut relasional mana yang harus di-fetch secara Eager tanpa mengubah struktur statis pemodelan entity.

---

## 06: Panduan Implementasi Step-by-Step

### 1. Inisialisasi Dependensi Maven (`pom.xml`)

Gunakan dependensi production-grade berikut:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.0</version>
        <relativePath/>
    </parent>
    <groupId>com.enterprise.persistence</groupId>
    <artifactId>persistence-core</artifactId>
    <version>1.0.0-SNAPSHOT</version>

    <properties>
        <java.version>21</java.version>
        <querydsl.version>5.1.0</querydsl.version>
        <hypersistence-utils.version>3.7.3</hypersistence-utils.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>io.hypersistence</groupId>
            <artifactId>hypersistence-utils-hibernate-63</artifactId>
            <version>${hypersistence-utils.version}</version>
        </dependency>
        <!-- QueryDSL Engine -->
        <dependency>
            <groupId>com.querydsl</groupId>
            <artifactId>querydsl-jpa</artifactId>
            <version>${querydsl.version}</version>
            <classifier>jakarta</classifier>
        </dependency>
        <dependency>
            <groupId>com.querydsl</groupId>
            <artifactId>querydsl-apt</artifactId>
            <version>${querydsl.version}</version>
            <classifier>jakarta</classifier>
            <scope>provided</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>com.mysema.maven</groupId>
                <artifactId>apt-maven-plugin</artifactId>
                <version>1.1.3</version>
                <executions>
                    <execution>
                        <goals>
                            <goal>process</goal>
                        </goals>
                        <configuration>
                            <outputDirectory>target/generated-sources/java</outputDirectory>
                            <processor>com.querydsl.apt.jpa.JPAAnnotationProcessor</processor>
                        </configuration>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```

---

## 07: Contoh Kasus Sederhana

Berikut implementasi repository standar Spring Data JPA untuk entity sederhana:

```java
package com.enterprise.persistence.simple;

import jakarta.persistence.*;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Entity
@Table(name = "simple_tenants")
public class SimpleTenant {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false, unique = true, length = 50)
    private String code;

    @Column(nullable = false)
    private String name;

    protected SimpleTenant() {}

    public SimpleTenant(String code, String name) {
        this.code = code;
        this.name = name;
    }

    public UUID getId() { return id; }
    public String getCode() { return code; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
}

@Repository
public interface SimpleTenantRepository extends JpaRepository<SimpleTenant, UUID> {
    Optional<SimpleTenant> findByCode(String code);
}
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Contoh kasus tingkat enterprise berikut mengimplementasikan **Order Management System** dengan optimasi fetching, auditing, dynamic querying menggunakan JPA Specification & QueryDSL, pessimistic/optimistic concurrency control, dan custom connection pool tuning.

### 1. Base Entity Abstract Class (Auditing & Optimistic Locking)

```java
package com.enterprise.persistence.core.entity;

import jakarta.persistence.*;
import org.springframework.data.annotation.CreatedBy;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedBy;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.Instant;
import java.util.Objects;

@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class AbstractBaseEntity<ID> {

    @Version
    @Column(name = "version", nullable = false)
    private Long version;

    @CreatedDate
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @LastModifiedDate
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @CreatedBy
    @Column(name = "created_by", nullable = false, updatable = false, length = 100)
    private String createdBy;

    @LastModifiedBy
    @Column(name = "updated_by", nullable = false, length = 100)
    private String updatedBy;

    public abstract ID getId();

    public Long getVersion() { return version; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public String getCreatedBy() { return createdBy; }
    public String getUpdatedBy() { return updatedBy; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        AbstractBaseEntity<?> that = (AbstractBaseEntity<?>) o;
        return getId() != null && Objects.equals(getId(), that.getId());
    }

    @Override
    public int hashCode() {
        return getClass().hashCode();
    }
}
```

### 2. Domain Model: Order & OrderItem Entities

```java
package com.enterprise.persistence.order.entity;

import com.enterprise.persistence.core.entity.AbstractBaseEntity;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.util.*;

@Entity
@Table(
    name = "orders",
    indexes = {
        @Index(name = "idx_orders_customer_id", columnList = "customer_id"),
        @Index(name = "idx_orders_status_created_at", columnList = "status, created_at DESC")
    }
)
@NamedEntityGraph(
    name = "Order.withItemsAndCustomer",
    attributeNodes = {
        @NamedAttributeNode("items")
    }
)
public class Order extends AbstractBaseEntity<UUID> {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "customer_id", nullable = false)
    private UUID customerId;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private OrderStatus status;

    @Column(name = "total_amount", nullable = false, precision = 18, scale = 4)
    private BigDecimal totalAmount;

    @OneToMany(
        mappedBy = "order",
        cascade = CascadeType.ALL,
        orphanRemoval = true,
        fetch = FetchType.LAZY
    )
    private Set<OrderItem> items = new HashSet<>();

    protected Order() {}

    public Order(UUID customerId) {
        this.customerId = Objects.requireNonNull(customerId, "Customer ID must not be null");
        this.status = OrderStatus.PENDING;
        this.totalAmount = BigDecimal.ZERO;
    }

    public void addItem(String sku, int quantity, BigDecimal unitPrice) {
        OrderItem item = new OrderItem(this, sku, quantity, unitPrice);
        this.items.add(item);
        recalculateTotal();
    }

    public void removeItem(OrderItem item) {
        this.items.remove(item);
        item.setOrder(null);
        recalculateTotal();
    }

    private void recalculateTotal() {
        this.totalAmount = this.items.stream()
            .map(OrderItem::getSubtotal)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }

    public void markAsProcessing() {
        if (this.status != OrderStatus.PENDING) {
            throw new IllegalStateException("Hanya order berstatus PENDING yang dapat diproses.");
        }
        this.status = OrderStatus.PROCESSING;
    }

    @Override
    public UUID getId() { return id; }
    public UUID getCustomerId() { return customerId; }
    public OrderStatus getStatus() { return status; }
    public BigDecimal getTotalAmount() { return totalAmount; }
    public Set<OrderItem> getItems() { return Collections.unmodifiableSet(items); }
}
```

```java
package com.enterprise.persistence.order.entity;

import com.enterprise.persistence.core.entity.AbstractBaseEntity;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.util.Objects;
import java.util.UUID;

@Entity
@Table(
    name = "order_items",
    indexes = {
        @Index(name = "idx_order_items_order_id", columnList = "order_id"),
        @Index(name = "idx_order_items_sku", columnList = "sku")
    }
)
public class OrderItem extends AbstractBaseEntity<UUID> {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "order_id", nullable = false, foreignKey = @ForeignKey(name = "fk_order_items_order_id"))
    private Order order;

    @Column(name = "sku", nullable = false, length = 64)
    private String sku;

    @Column(name = "quantity", nullable = false)
    private int quantity;

    @Column(name = "unit_price", nullable = false, precision = 18, scale = 4)
    private BigDecimal unitPrice;

    @Column(name = "subtotal", nullable = false, precision = 18, scale = 4)
    private BigDecimal subtotal;

    protected OrderItem() {}

    public OrderItem(Order order, String sku, int quantity, BigDecimal unitPrice) {
        if (quantity <= 0) throw new IllegalArgumentException("Quantity must be greater than zero");
        this.order = Objects.requireNonNull(order, "Order reference cannot be null");
        this.sku = Objects.requireNonNull(sku, "SKU cannot be null");
        this.unitPrice = Objects.requireNonNull(unitPrice, "Unit price cannot be null");
        this.quantity = quantity;
        this.subtotal = unitPrice.multiply(BigDecimal.valueOf(quantity));
    }

    @Override
    public UUID getId() { return id; }
    public Order getOrder() { return order; }
    void setOrder(Order order) { this.order = order; }
    public String getSku() { return sku; }
    public int getQuantity() { return quantity; }
    public BigDecimal getUnitPrice() { return unitPrice; }
    public BigDecimal getSubtotal() { return subtotal; }
}
```

```java
package com.enterprise.persistence.order.entity;

public enum OrderStatus {
    PENDING,
    PROCESSING,
    COMPLETED,
    CANCELLED
}
```

### 3. Read-Optimized Projection DTO

```java
package com.enterprise.persistence.order.dto;

import com.enterprise.persistence.order.entity.OrderStatus;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record OrderSummaryDTO(
    UUID orderId,
    UUID customerId,
    OrderStatus status,
    BigDecimal totalAmount,
    long totalItemsCount,
    Instant createdAt
) {}
```

### 4. JPA Specifications untuk Dynamic Search

```java
package com.enterprise.persistence.order.repository;

import com.enterprise.persistence.order.entity.Order;
import com.enterprise.persistence.order.entity.OrderStatus;
import jakarta.persistence.criteria.Predicate;
import org.springframework.data.jpa.domain.Specification;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public final class OrderSpecifications {

    private OrderSpecifications() {}

    public record FilterCriteria(
        UUID customerId,
        OrderStatus status,
        BigDecimal minAmount,
        BigDecimal maxAmount,
        Instant createdAfter,
        Instant createdBefore
    ) {}

    public static Specification<Order> buildStrictFilter(FilterCriteria criteria) {
        return (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();

            if (criteria.customerId() != null) {
                predicates.add(cb.equal(root.get("customerId"), criteria.customerId()));
            }
            if (criteria.status() != null) {
                predicates.add(cb.equal(root.get("status"), criteria.status()));
            }
            if (criteria.minAmount() != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("totalAmount"), criteria.minAmount()));
            }
            if (criteria.maxAmount() != null) {
                predicates.add(cb.lessThanOrEqualTo(root.get("totalAmount"), criteria.maxAmount()));
            }
            if (criteria.createdAfter() != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("createdAt"), criteria.createdAfter()));
            }
            if (criteria.createdBefore() != null) {
                predicates.add(cb