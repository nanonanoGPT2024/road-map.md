# SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Back-End Java Specialist & Enterprise Architecture
* **Kategori:** 02-Programming-Languages
* **Bab:** 05 — Advanced Enterprise Data Architecture
* **Modul:** 01 — Data Persistence, ORM & Database Performance Tuning
* **Tingkat Kesulitan:** Advanced / Senior Engineer
* **Prasyarat:** Pemahaman mendalam tentang Java Concurrency, Arsitektur Memori JVM, Relational Algebra (SQL standar ANSI), serta protokol JDBC tingkat dasar.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Mendekonstruksi Lifecycle dan State Entity JPA:** Memahami transisi status entitas (*Transient, Managed, Detached, Removed*) dalam *Persistence Context* dan mengontrol siklus *Flush* serta *Dirty Checking Engine*.
2. **Menganalisis dan Menyelesaikan Anti-Pattern ORM:** Mendeteksi, mereproduksi, dan memitigasi problem $N+1$ query, *Cartesian Product Problem*, dan *Accidental Lazy Loading* menggunakan `JOIN FETCH`, `EntityGraph`, dan Proyeksi DTO.
3. **Mengonfigurasi dan Mengoptimasi Connection Pool (HikariCP):** Mengkalkulasi alokasi *pool size* optimal berbasis *Little's Law* dan *Amdahl's Law*, serta mendeteksi *connection leak* pada lingkungan multi-threading.
4. **Mendesain Mekanisme Konkurensi Database Terdistribusi:** Mengimplementasikan *Optimistic Locking* (berbasis versi) dan *Pessimistic Locking* (`PESSIMISTIC_WRITE`, `PESSIMISTIC_READ`) untuk mencegah *Lost Updates* dan *Phantom Reads*.
5. **Melakukan Database Performance Tuning Komprehensif:** Mengintegrasikan strategi *batch processing* JDBC/Hibernate, pemanfaatan *Second-Level Cache* (L2C), optimalisasi struktur indeks B-Tree, dan interpretasi *Query Execution Plan* (EXPLAIN ANALYZE).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: *The Impedance Mismatch Illusion*
Object-Relational Mapping (ORM) bukanlah abstraksi tanpa beban (*leaky abstraction*). Java memandang data sebagai jejaring graf objek yang terhubung melalui pointer memori, memiliki identitas referensial, dan bergantung pada enkapsulasi. Sebaliknya, Relational Database Management System (RDBMS) memandang data sebagai relasi himpunan matematis berdimensi dua, yang dinormalisasi, diakses melalui aljabar relasional, dan terikat pada batas transaksi ACID.

```
       Paradigma Objek (Java)                 Paradigma Relasional (RDBMS)
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│ • Graf Objek & Pointer Memori   │  vs   │ • Tuple & Aljabar Relasional    │
│ • Enkapsulasi, Polimorfisme     │  ───  │ • Skema Kaku & Normalisasi      │
│ • Identitas berbasis Pointer    │       │ • Identitas berbasis Primary Key│
│ • Navigasi via Asosiasi Titik   │       │ • Navigasi via Relasi JOIN      │
└─────────────────────────────────┘       └─────────────────────────────────┘
```

Seorang Senior Engineer tidak boleh menganggap ORM sebagai "penyihir otomatis pembuat SQL". ORM harus diperlakukan sebagai **state manager sinkronisasi memori-ke-disk**. Kode Java Anda beroperasi di RAM, sedangkan data Anda berada di disk non-volatile di balik latensi I/O jaringan. Setiap traversal relasi objek (`order.getCustomer().getAddress()`) yang tidak dirancang dengan sadar adalah potensi perjalanan jaringan (*network round-trip*) yang mematikan performa aplikasi secara eksponensial.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah representasi end-to-end arsitektur persistence Java: dari lapisan aplikasi, manajemen state di dalam Hibernate/JPA, connection pool HikariCP, hingga lapisan kernel RDBMS.

```
+---------------------------------------------------------------------------------------+
|                                    JVM RUNTIME                                        |
|                                                                                       |
|  [ Aplikasi Service / Use Case ]                                                      |
|           │                                                                           |
|           ▼                                                                           |
|  [ EntityManager / SessionImpl ]                                                      |
|   ┌─────────────────────────────────────────────────────────────────────────────────┐ │
|   │                           PERSISTENCE CONTEXT (L1 CACHE)                        │ │
|   │  • Entity Identity Map (Key: Class + PK -> Object Ref)                          │ │
|   │  • Snapshot Map (State awal entitas untuk Dirty Checking)                       │ │
|   │  • ActionQueue (InsertAction, UpdateAction, DeleteAction terurut)               │ │
|   └────────────────────────────────────────┬────────────────────────────────────────┘ │
|                                            │ flush()                                  |
|                                            ▼                                          |
|  [ Hibernate Hydration & SQL Generator Engine ]                                       |
|                                            │                                          |
|                                            ▼                                          |
|  [ JDBC Driver API Layer ] (PreparedStatement, Batching Queue)                        |
|                                            │                                          |
|                                            ▼                                          |
|  [ HikariCP (Connection Pool) ]                                                       |
|   ┌─────────────────────────────────────────────────────────────────────────────────┐ │
|   │  FastList<IConnection>   ConcurrentBag (ThreadLocal -> Shared CopyOnWriteArrayList)│
|   │  SynchronousQueue / Semaphore (Wait timeout handoff)                            │ │
|   └────────────────────────────────────────┬────────────────────────────────────────┘ │
+--------------------------------------------│------------------------------------------+
                                             │ Socket Write (TCP Packets)
                                             ▼
+---------------------------------------------------------------------------------------+
|                                  RDBMS SERVER ENGINE                                  |
|                                                                                       |
|  [ Network Listener / Connection Worker Thread ]                                      |
|                        │                                                              |
|                        ▼                                                              |
|  [ Query Parser, Rewriter, Cost-Based Optimizer (CBO) ]                               |
|                        │                                                              |
|                        ▼                                                              |
|  [ Execution Engine ] ◄───► [ Lock Manager ] (Row-Level Locks, MVCC Snapshot)        |
|            │                                                                          |
|            ├───► [ Buffer Pool / Shared Buffers (SRAM/DRAM) ]                         |
|            │               │                                                          |
|            │               ▼ (Page Eviction / Checkpoint)                             |
|            ▼       [ Table Space / Data Files (.ibd / heap) ]                         |
|  [ Write-Ahead Logging (WAL / Redo Log Engine) ] ──► [ Disk Persistent Storage ]     |
+---------------------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Persistence Context & First-Level Cache (L1)
*Persistence Context* bertindak sebagai isolasi transaksi dalam-memori. Anatomi utamanya terdiri atas dua map internal:
*   **Identity Map:** Memetakan pasangan `(Tipe Entitas, Primary Key)` ke referensi memori Java dari instansi entitas. Ini menjamin bahwa dalam satu *EntityManager*, kueri berulang terhadap entitas dan ID yang sama mengembalikan referensi pointer objek identik (`a == b` bernilai `true`), mencegah instansiasi ganda.
*   **Snapshot Map:** Saat entitas dimuat dari database, Hibernate membuat duplikat byte-by-byte dari nilai properti entitas tersebut ke dalam array internal. 

### 2. Dirty Checking Mechanism
Mekanisme pendeteksian modifikasi bekerja saat proses `flush()` dipicu:
1. Hibernate melakukan iterasi terhadap semua entitas dalam Identity Map dengan status `MANAGED`.
2. Array status saat ini dari entitas dibandingkan nilai-per-nilai dengan array yang tersimpan di Snapshot Map.
3. Jika ditemukan divergensi nilai properti, Hibernate membuat `EntityUpdateAction` baru dan memasukkannya ke dalam `ActionQueue`.
4. Komparasi kustom dapat diterapkan melalui interceptor, tetapi komparasi *deep-reflection* default memiliki *overhead* CPU $O(N \times M)$ dengan $N$ adalah jumlah entitas terkelola dan $M$ adalah jumlah atribut.

### 3. ActionQueue & Flush Ordering
Hibernate tidak mengeksekusi SQL secara acak saat Anda memanggil `persist()` atau `remove()`. Semua aksi ditunda (*write-behind execution*) hingga `flush()` dipanggil, lalu dieksekusi berdasarkan deterministik dependensi urutan:
1. `OrphanRemovalAction`
2. `EntityInsertAction`
3. `EntityUpdateAction`
4. `QueuedOperationCollectionAction`
5. `EntityDeleteAction`

Urutan deterministik ini mencegah terjadinya pelanggaran *foreign key constraint* pada level database.

### 4. HikariCP Internals: Micro-Optimized Pooling
HikariCP mencapai latensi minimal melalui tiga optimasi tingkat rendah:
*   **`ConcurrentBag`:** Struktur data *lock-free* yang didesain khusus. Setiap thread pekerja yang meminta koneksi pertama-tama akan memeriksa `ThreadLocal<IConnection>` miliknya. Jika ada koneksi tak terpakai yang cocok, koneksi langsung diambil tanpa melewati *central lock contention*.
*   **`FastList`:** Eliminasi overhead bounds-checking dari `ArrayList` standar Java. Saat sebuah PreparedStatement ditutup, `FastList.remove()` melakukan pencarian dari elemen terakhir (LIFO), memangkas kompleksitas penghapusan statement dari $O(N)$ menjadi $O(1)$.
*   **Javassist Bytecode Generation:** HikariCP menghasilkan kelas proxy JDBC langsung menjadi instruksi bytecode native yang tipis, mempercepat eksekusi delegasi method hingga level instruksi CPU inline.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Siklus Hidup Entitas (Entity Lifecycle State Machine)

```
                       persist()
   ┌──────────────┐ ─────────────► ┌─────────────┐
   │  TRANSIENT   │                │   MANAGED   │ ◄─── find(), getReference(), Query
   └──────────────┘ ◄───────────── └──────┬──────┘
         ▲              remove()          │
         │                                │ detach(), clear(), close()
         │                                ▼
   ┌─────┴────────┐                ┌─────────────┐
   │   REMOVED    │                │  DETACHED   │
   └──────────────┘                └──────┬──────┘
                                          │
                                          ▼ merge()
                                   ┌─────────────┐
                                   │   MANAGED   │ (Returns NEW Instance)
                                   └─────────────┘
```

*   **Transient:** Objek baru yang diinstansiasi dengan operator `new`. RDBMS tidak memiliki catatan tentangnya; tidak ada ID terasosiasi; tidak berada di dalam Persistence Context.
*   **Managed:** Objek memiliki identitas basis data (Primary Key) dan terikat secara aktif ke Persistence Context. Setiap mutasi state pada objek ini akan diawasi secara otomatis oleh *Dirty Checking*.
*   **Detached:** Objek memiliki identitas basis data, namun Persistence Context yang memuatnya telah ditutup (`close()`), dibersihkan (`clear()`), atau objek tersebut dikeluarkan secara eksplisit (`detach()`). Modifikasi pada status objek ini tidak akan menghasilkan query `UPDATE` database.
*   **Removed:** Entitas ditandai untuk dihapus dari database pada saat siklus `flush()` berikutnya berjalan.

### 2. The $N+1$ Query Problem & Cartesian Explosion
Secara default, pemetaan relasi JPA bertipe `@OneToMany` atau `@ManyToMany` dikonfigurasi secara `FetchType.LAZY`. Ketika aplikasi mengambil daftar $N$ entitas induk, query pertama dieksekusi:

$$\text{Query 1: } \texttt{SELECT * FROM orders LIMIT 100;}$$

Jika loop aplikasi membaca koleksi anak dari setiap order:

$$\text{Query } 2 \dots N+1: \texttt{SELECT * FROM order\_items WHERE order\_id = ?;}$$

Aplikasi mengeksekusi $1 + N$ query SQL terpisah. Ini menyebabkan latensi *network round-trip* yang masif. 

Namun, jika diselesaikan secara ceroboh dengan melakukan *Fetch Join* ganda pada dua koleksi independen:
```java
// Anti-pattern: Multiple collections JOIN FETCH
SELECT o FROM Order o 
JOIN FETCH o.items 
JOIN FETCH o.paymentTransactions
```
RDBMS akan mengalikan kedua himpunan menghasilkan perkalian kartesius (*Cartesian Product*): jika sebuah order memiliki 50 items dan 10 payment transactions, Hibernate akan menerima $1 \times 50 \times 10 = 500$ baris data per order dari database. Hal ini menyebabkan ledakan alokasi memori heap JVM dan kegagalan OutOfMemoryError (OOM).

Solusi definitif:
*   Gunakan `JOIN FETCH` atau `@EntityGraph` hanya untuk **satu** relasi koleksi per query.
*   Gunakan `@BatchSize(size = 50)` atau Proyeksi DTO langsung untuk relasi koleksi lainnya.

### 3. Sizing Database Connection Pool: Little's Law
Mengalokasikan pool connection terlalu besar adalah penyebab nomor satu degradasi throughput database. Berdasarkan teori antrean dan *Little's Law*:

$$L = \lambda \times W$$

Di mana:
*   $L$ = Jumlah rata-rata request di dalam sistem.
*   $\lambda$ = Laju kedatangan request (throughput).
*   $W$ = Waktu tunggu / durasi pemrosesan (latensi).

Pada level perangkat keras CPU RDBMS, jika jumlah koneksi aktif melebihi jumlah core CPU fisik secara signifikan, sistem operasi akan menghabiskan mayoritas waktu clock CPU untuk melakukan **Context Switching** antar-thread alih-alih mengeksekusi komputasi kueri yang sebenarnya.

Formula empiris PostgreSQL / HikariCP untuk batas atas ukuran pool:

$$\text{Pool Size} = (\text{Core CPU Server DB} \times 2) + \text{Effective Spindle Count (Disk Count)}$$

Untuk server RDBMS dengan 8 Core CPU dan 1 SSD berkecepatan tinggi:

$$\text{Pool Size} = (8 \times 2) + 1 = 17 \text{ koneksi.}$$

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi implementasi JDBC murni tingkat rendah dengan optimasi performa maksimal: penggunaan *Connection Pooling* programmatic melalui HikariCP, *Batch Execution*, dan *Streaming Results* via Fetch Size untuk menghindari JVM Heap Exhaustion.

```java
package com.enterprise.persistence.fundamental;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;

public class HighPerformanceJdbcEngine {

    private final DataSource dataSource;

    public HighPerformanceJdbcEngine() {
        this.dataSource = initializePool();
    }

    private DataSource initializePool() {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl("jdbc:postgresql://localhost:5432/trade_db");
        config.setUsername("db_operator");
        config.setPassword("SuperSecureSecret123!");
        
        // Tuning Ukuran Pool Berdasarkan Kapasitas Core DB (cth: 4 Core DB)
        config.setMaximumPoolSize(9);
        config.setMinimumIdle(9); // Fixed pool size menghilangkan overhead dynamic allocation
        
        // Timeout & Leak Detection
        config.setConnectionTimeout(3000); // 3 detik
        config.setIdleTimeout(600000);
        config.setMaxLifetime(1800000); // 30 menit
        config.setLeakDetectionThreshold(5000); // Trigger warning jika connection ditahan > 5s
        
        // Performance Caching Flags untuk JDBC Driver
        config.addDataSourceProperty("cachePrepStmts", "true");
        config.addDataSourceProperty("prepStmtCacheSize", "250");
        config.addDataSourceProperty("prepStmtCacheSqlLimit", "2048");
        config.addDataSourceProperty("useServerPrepStmts", "true");

        return new HikariDataSource(config);
    }

    public record AuditLogRecord(long id, String source, String payload) {}

    public void executeHighThroughputBatch(List<AuditLogRecord> records) throws SQLException {
        final String sql = "INSERT INTO audit_logs (id, source, payload) VALUES (?, ?, ?)";

        try (Connection connection = dataSource.getConnection()) {
            // Nonaktifkan auto-commit untuk mengontrol batas transaksi secara eksplisit
            connection.setAutoCommit(false);

            try (PreparedStatement stmt = connection.prepareStatement(sql)) {
                int batchCounter = 0;
                final int BATCH_SIZE = 1000;

                for (AuditLogRecord record : records) {
                    stmt.setLong(1, record.id());
                    stmt.setString(2, record.source());
                    stmt.setString(3, record.payload());
                    stmt.addBatch();

                    batchCounter++;
                    if (batchCounter % BATCH_SIZE == 0) {
                        stmt.executeBatch();
                        stmt.clearBatch(); // Kosongkan memori buffer JDBC statement
                    }
                }

                // Eksekusi sisa query yang belum mencapai threshold batch
                if (batchCounter % BATCH_SIZE != 0) {
                    stmt.executeBatch();
                }

                connection.commit(); // Atomic commit ke disk storage
            } catch (SQLException ex) {
                connection.rollback();
                throw ex;
            } finally {
                connection.setAutoCommit(true);
            }
        }
    }

    public List<AuditLogRecord> streamMassiveResultSet(long minId) throws SQLException {
        final String sql = "SELECT id, source, payload FROM audit_logs WHERE id >= ?";
        List<AuditLogRecord> results = new ArrayList<>();

        try (Connection connection = dataSource.getConnection();
             PreparedStatement stmt = connection.prepareStatement(sql, 
                     ResultSet.TYPE_FORWARD_ONLY, 
                     ResultSet.CONCUR_READ_ONLY)) {

            // Mencegah JDBC memuat seluruh data ke JVM Heap sekaligus
            stmt.setFetchSize(500);
            stmt.setLong(1, minId);

            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    results.add(new AuditLogRecord(
                            rs.getLong("id"),
                            rs.getString("source"),
                            rs.getString("payload")
                    ));
                }
            }
        }
        return results;
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 24–27:** `config.setMaximumPoolSize(9)` dan `config.setMinimumIdle(9)`. Mengatur nilai yang sama menghasilkan strategi *fixed-size pool*. Ini menghilangkan alokasi dinamis memori dan latensi penambahan thread saat traffic spiking tiba-tiba.
*   **Baris 31:** `config.setLeakDetectionThreshold(5000)`. Jika sebuah worker thread memegang koneksi keluar dari pool selama lebih dari 5.000 milidetik tanpa mengembalikannya, HikariCP akan mencetak exception stack trace lengkap yang menunjukkan lokasi pasti kode yang menahan koneksi tersebut.
*   **Baris 34–37:** Optimasi PreparedStatement Caching. Menginstruksikan driver JDBC PostgreSQL/MySQL untuk menyimpan struktur parsed query tree di memori klien JVM dan menggunakan prepared statement sisi server, menghindari CPU parsing overhead pada database secara berulang.
*   **Baris 48:** `connection.setAutoCommit(false)`. Secara default, JDBC driver membungkus setiap statement individu ke dalam transaksi implisit mandiri (`BEGIN ... COMMIT`). Mematikan auto-commit menyatukan ribuan operasi insert ke dalam satu blok log transaksi fisik tunggal di RDBMS.
*   **Baris 60–63:** `stmt.executeBatch()` dan `stmt.clearBatch()`. `executeBatch()` mengirimkan payload perintah yang telah di-buffer sebagai satu kesatuan paket protokol TCP ke RDBMS. `stmt.clearBatch()` membebaskan referensi parameter dari memori internal driver untuk mencegah alokasi memori membengkak.
*   **Baris 69–73:** Penanganan `commit()` dan `rollback()`. Memastikan atomisitas komprehensif. Kegagalan parsial pada record ke-950 dari 1.000 akan membatalkan seluruh operasi secara absolut, mencegah inkonsistensi status database (*partial data corruption*).
*   **Baris 89:** `stmt.setFetchSize(500)`. Tanpa konfigurasi ini, driver JDBC standar (terutama MySQL/Postgre) akan mencoba mengalirkan jutaan record hasil query ke memori RAM aplikasi secara instan, memicu kegagalan fatal `java.lang.OutOfMemoryError: Java heap space`. Fetch size memaksa driver menarik data dalam kepingan blok 500 baris menggunakan kursor database.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Insiden Degradasi Pembayaran Kilat (Flash Sale Payment System)
* **Konteks:** Sebuah platform e-commerce enterprise mengalami lonjakan transaksi pada saat event Midnight Flash Sale (50.000 transaksi pembayaran per menit).
* **Gejala:** 
  1. Waktu respon API checkout melonjak drastis dari 80ms menjadi 18.000ms.
  2. Aplikasi mengalami *Connection Pool Exhaustion* (`HikariPool-1 - Connection is not available, request timed out after 30000ms`).
  3. Database CPU mencapai utilitas 100%, namun I/O throughput (disk write) anjlok hingga titik terendah.
* **Akar Masalah (Root Cause Analysis):**
  1. **N+1 Query:** Pada entity `PaymentOrder`, developer memetakan `@OneToMany List<OrderItem> items` dengan konfigurasi relasi default. Untuk setiap order, aplikasi melakukan kueri tambahan ke tabel `order_items`. Total kueri membengkak menjadi $50.000 \times N$ kueri.
  2. **Race Condition pada Saldo Pengguna:** Menggunakan update implisit tanpa locking:
     ```sql
     -- Skenario Lost Update
     UPDATE accounts SET balance = balance - 100 WHERE id = 1;
     ```
     Dua worker thread membaca saldo secara bersamaan, menyebabkan fenomena saldo minus atau kehilangan uang (*Lost Updates*).
  3. **Connection Leak:** Pada method notifikasi webhook pihak ketiga yang memakan waktu timeout hingga 10 detik, developer membungkusnya di dalam method service beranotasi `@Transactional`. Akibatnya, koneksi database fisik dari HikariCP ditahan selama 10 detik penuh hanya untuk menunggu respons jaringan I/O pihak ketiga!
* **Solusi Terpadu:**
  1. Mengisolasi pemanggilan I/O jaringan di luar batas `@Transactional`.
  2. Menerapkan **Optimistic Locking** berbasis kolom versi `@Version` untuk transaksi normal, dan **Pessimistic Locking** terisolasi (`SELECT FOR UPDATE`) khusus transaksi saldo kritis dengan durasi eksekusi terpangkas.
  3. Mengganti traversal entitas menggunakan **JPA Projection** berbasis DTO dan optimasi query kustom dengan `JOIN FETCH`.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA

Berikut adalah arsitektur kode produksi berstandar enterprise yang memitigasi seluruh kelemahan performa di atas:

### 1. Lapisan Model Entitas
```java
package com.enterprise.persistence.production.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "payment_orders", indexes = {
    @Index(name = "idx_order_customer_created", columnList = "customer_id, created_at DESC")
})
public class PaymentOrder {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "customer_id", nullable = false)
    private Long customerId;

    @Column(name = "total_amount", nullable = false, precision = 19, scale = 4)
    private BigDecimal totalAmount;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private OrderStatus status;

    @Version
    @Column(name = "version")
    private Long version; // Menjamin Optimistic Locking

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<OrderItem> items = new ArrayList<>();

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    public enum OrderStatus { PENDING, PROCESSING, SETTLED, FAILED }

    // Helper method bidirectional mapping
    public void addItem(OrderItem item) {
        items.add(item);
        item.setOrder(this);
    }

    // Getters and Setters diabaikan demi keringkasan kode
    public Long getId() { return id; }
    public Long getCustomerId() { return customerId; }
    public BigDecimal getTotalAmount() { return totalAmount; }
    public Long getVersion() { return version; }
    public List<OrderItem> getItems() { return items; }
    public void setStatus(OrderStatus status) { this.status = status; }
}
```

```java
package com.enterprise.persistence.production.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "order_items")
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "order_id", nullable = false)
    private PaymentOrder order;

    @Column(name = "sku", nullable = false, length = 64)
    private String sku;

    @Column(name = "price", nullable = false, precision = 19, scale = 4)
    private BigDecimal price;

    public void setOrder(PaymentOrder order) { this.order = order; }
    public Long getId() { return id; }
    public String getSku() { return sku; }
    public BigDecimal getPrice() { return price; }
}
```

### 2. DTO Projection Berkinerja Tinggi
```java
package com.enterprise.persistence.production.dto;

import java.math.BigDecimal;

public record OrderSummaryProjection(
    Long orderId,
    Long customerId,
    BigDecimal totalAmount,
    int totalItems
) {}
```

### 3. Lapisan Repositori Data
```java
package com.enterprise.persistence.production.repository;

import com.enterprise.persistence.production.dto.OrderSummaryProjection;
import com.enterprise.persistence.production.entity.PaymentOrder;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface PaymentOrderRepository extends JpaRepository<PaymentOrder, Long> {

    // 1. Mengatasi N+1 Menggunakan Fetch Join
    @Query("SELECT o FROM PaymentOrder o JOIN FETCH o.items WHERE o.id = :id")
    Optional<PaymentOrder> findByIdWithItemsEager(@Param("id") Long id);

    // 2. Pessimistic Write Lock untuk Mengunci Baris (SELECT FOR UPDATE)
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT o FROM PaymentOrder o WHERE o.id = :id")
    Optional<PaymentOrder> findByIdExclusiveLock(@Param("id") Long id);

    // 3. Proyeksi Konstruktor Langsung Menghindari Overhead Instansiasi Entitas
    @Query("""
        SELECT new com.enterprise.persistence.production.dto.OrderSummaryProjection(
            o.id, o.customerId, o.totalAmount, CAST(COUNT(i.id) AS int)
        )
        FROM PaymentOrder o
        LEFT JOIN o.items i
        WHERE o.id = :id
        GROUP BY o.id, o.customerId, o.totalAmount
    """)
    Optional<OrderSummaryProjection> findSummaryById(@Param("id") Long id);
}
```

### 4. Lapisan Service Transaksional
```java
package com.enterprise.persistence.production.service;

import com.enterprise.persistence.production.entity.PaymentOrder;
import com.enterprise.persistence.production.repository.PaymentOrderRepository;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PaymentProcessingService {

    private final PaymentOrderRepository orderRepository;
    private final ExternalPaymentGatewayClient externalGatewayClient;

    public PaymentProcessingService(PaymentOrderRepository orderRepository,
                                    ExternalPaymentGatewayClient externalGatewayClient) {
        this.orderRepository = orderRepository;
        this.externalGatewayClient = externalGatewayClient;
    }

    /**
     * Pola Eksekusi Kritis: JANGAN memegang transaksi database saat memanggil I/O Jaringan!
     */
    public void processPaymentPipeline(Long orderId) {
        // Langkah 1: Eksekusi perubahan state dalam transaksi pendek
        PaymentOrder order = prepareOrderForProcessing(orderId);

        // Langkah 2: Panggilan Jaringan (I/O) tanpa memegang koneksi DB!
        boolean isSuccess = externalGatewayClient.executeThirdPartyCharge(
                order.getId(), 
                order.getTotalAmount()
        );

        // Langkah 3: Finalisasi status di transaksi pendek berikutnya
        finalizePaymentStatus(orderId, isSuccess);
    }

    @Transactional(propagation = Propagation.REQUIRED, isolation = Isolation.READ_COMMITTED)
    public PaymentOrder prepareOrderForProcessing(Long orderId) {
        PaymentOrder order = orderRepository.findById(orderId)
                .orElseThrow(() -> new IllegalArgumentException("Order tidak ditemukan: " + orderId));

        if (order.getStatus() != PaymentOrder.OrderStatus.PENDING) {
            throw new IllegalStateException("Hanya order PENDING yang dapat diproses!");
        }

        order.setStatus(PaymentOrder.OrderStatus.PROCESSING);
        return order; 
        // Dirty checking otomatis meng-update order saat transaksi commit,
        // mengecek kolom @Version secara otomatis.
    }

    @Transactional(propagation = Propagation.REQUIRED, isolation = Isolation.READ_COMMITTED)
    public void finalizePaymentStatus(Long orderId, boolean paymentSuccess) {
        try {
            PaymentOrder order = orderRepository.findById(orderId)
                    .orElseThrow(() -> new IllegalArgumentException("Order tidak ditemukan: " + orderId));

            if (paymentSuccess) {
                order.setStatus(PaymentOrder.OrderStatus.SETTLED);
            } else {
                order.setStatus(PaymentOrder.OrderStatus.FAILED);
            }
        } catch (OptimisticLockingFailureException ex) {
            // Tangani error konkurensi di mana thread lain telah mengubah versi order ini
            throw new IllegalStateException("Konflik data terdeteksi! Transaksi dibatalkan.", ex);
        }
    }
}
```

```java
package com.enterprise.persistence.production.service;

import org.springframework.stereotype.Component;
import java.math.BigDecimal;

@Component
public class ExternalPaymentGatewayClient {
    public boolean executeThirdPartyCharge(Long orderId, BigDecimal amount) {
        // Simulasi latensi jaringan external gateway (2000ms)
        try {
            Thread.sleep(2000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
        return true;
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Paradigma Pengambilan Data: JPA Entity vs DTO Projection vs Native SQL

| Karakteristik | JPA Managed Entity | DTO Projection (JPQL) | Native SQL / jOOQ |
| :--- | :--- | :--- | :--- |
| **Overhead Memori** | **Sangat Tinggi** (Memuat Snapshot Map, First-Level Cache, Dirty Checking Tracking). | **Rendah** (Hanya instansiasi objek POJO/Record sederhana). | **Minimal** (Mapping langsung dari kursor JDBC). |
| **Throughput / Latensi** | Lambat jika membaca dataset besar (> 10k rows). | Sangat Cepat. | Kecepatan Bare-Metal (Maksimal). |
| **Fleksibilitas Mutasi** | **Tinggi** (Dirty checking otomatis meng-generate query UPDATE). | **Tidak Ada** (Read-Only immutable data). | Mutasi eksplisit via perintah manual SQL. |
| **Type Safety** | Tinggi (Validasi JPA via compile-time IDE). | Tinggi (Compile-time type check). | Rendah (Kecuali menggunakan Type-Safe DSL seperti jOOQ). |
| **Kasus Penggunaan Ideal** | Operasi transaksional kompleks OLTP (1-10 entitas termodifikasi). | Read-heavy queries, Dashboard, Pagination view, API Responses. | Batch processing masif, Analytic Queries (OLAP), Window Functions. |

### 2. Strategi Concurrency Control: Optimistic Locking vs Pessimistic Locking

| Karakteristik | Optimistic Locking (`@Version`) | Pessimistic Locking (`SELECT FOR UPDATE`) |
| :--- | :--- | :--- |
| **Mekanisme** | Validasi non-blocking saat commit via statement: `WHERE id = ? AND version = ?`. | Database menahan baris data dengan *Exclusive Row-Level Lock*. |
| **Overhead Lock Database**| Nol overhead pada Lock Manager DBMS. | Tinggi (Menyandera slot lock table & thread worker DB). |
| **Deadlock Risk** | Nol. | Tinggi jika locking diakses tidak terurut antar-tabel. |
| **Toleransi Konflik** | Unggul pada rasio baca tinggi, konflik tulis rendah (*Low Contention*). | Wajib pada rasio tulis tinggi dengan data kritis (*High Contention*). |
| **Konsekuensi Kegagalan** | Melempar exception ke aplikasi (`OptimisticLockException`), menuntut implementasi mekanisme retry. | Thread pengakses lain terblokir (*queueing*) hingga lock dilepas via commit/rollback. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

1. **LazyInitializationException pada Detached Entities:**
   * *Problem:* Mengakses `order.getItems().size()` di luar layer transaksi (misalnya di Controller atau Serializer Jackson JSON). Persistence context sudah ditutup, namun proxy belum di-hydrate.
   * *Mitigasi:* Jangan pernah mengirim entitas JPA keluar dari Service Boundary ke REST Controller. Selalu konversi ke Record DTO pada Service Layer menggunakan query yang sudah memuat data yang diperlukan.
2. **Koleksi `Set` vs `List` pada Pemetaan `@ManyToMany` dan `@OneToMany`:**
   * *Problem:* Menggunakan `java.util.List` untuk dua asosiasi `@ManyToMany` atau `@OneToMany` berbeda memicu error `MultipleBagFetchException` di Hibernate karena ketidakmampuan membangun representasi Cartesian list.
   * *Mitigasi:* Gunakan `java.util.Set` untuk asosiasi relasi, atau gunakan `FetchMode.SUBSELECT` untuk memisahkan kueri penarikan koleksi anak.
3. **Primary Key Generation: Identitas Mengacaukan Batching:**
   * *Problem:* Penggunaan `GenerationType.IDENTITY` menonaktifkan fitur JDBC Batching pada Hibernate secara total! Basis data harus mengeksekusi statement `INSERT` secara langsung dan seketika untuk mendapatkan nilai autoincrement ID (`getGeneratedKeys()`), sehingga eksekusi tunda (*Write-Behind*) pada Persistence Context tidak dapat dijalankan.
   * *Mitigasi:* Gunakan `GenerationType.SEQUENCE` yang mendukung alokasi pre-allocation menggunakan optimizer `pooled-lo`:
   ```java
   @Id
   @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "seq_gen")
   @SequenceGenerator(name = "seq_gen", sequenceName = "order_seq", allocationSize = 50)
   private Long id;
   ```
4. **Pola HashCode dan Equals pada Managed Entities:**
   * *Problem:* Menggunakan ID autoincrement pada implementasi `equals()` dan `hashCode()`. Sebelum disimpan, ID bernilai `null`. Saat disimpan, ID terisi. Ini merusak integritas struktur data `HashSet` atau `HashMap` jika entitas dimasukkan ke dalam Set sebelum operasi `persist()` dijalankan.
   * *Mitigasi:* Gunakan Business Key alami yang immutable (seperti UUID transaksi/email) atau terapkan `equals` berbasis kesamaan referensi kelas absolut, bukan field database mentah:
   ```java
   @Override
   public boolean equals(Object o) {
       if (this == o) return true;
       if (!(o instanceof PaymentOrder other)) return false;
       return id != null && id.equals(other.getId());
   }
   @Override
   public int hashCode() {
       return getClass().hashCode(); // Tetap konstan sebelum dan sesudah persist
   }
   ```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Kesalahan Fatal: Menggunakan `open-in-view = true` (OSIV)
* **Pola Buruk:** Membiarkan konfigurasi default Spring Boot `spring.jpa.open-in-view=true`. Ini memaksa filter HTTP memegang koneksi database fisik dari request masuk hingga response JSON selesai ditulis ke socket browser! Jika terjadi latensi jaringan klien, koneksi database terkunci.
* **Perbaikan:** Matikan secara mutlak di file properti:
  ```properties
  spring.jpa.open-in-view=false
  ```
  Atasi semua kebutuhan data menggunakan DTO Projections eksplisit di dalam batas `@Transactional`.

### 2. Kesalahan: Memanggil Method `@Transactional` dari Kelas yang Sama (Self-Invocation)
* **Pola Buruk:**
  ```java
  @Service
  public class OrderService {
      public void process() {
          this.persistInternal(); // Anotasi @Transactional di-bypass total!
      }

      @Transactional
      public void persistInternal() {
          // Operasi DB
      }
  }
  ```
* **Mekanisme Kegagalan:** Spring Transactional bekerja menggunakan Dynamic AOP Proxy. Panggilan dari dalam objek yang sama (`this`) tidak melewati proxy interceptor Spring, sehingga tidak ada transaksi yang dibuka (`BEGIN`), memicu kegagalan auto-commit liar atau Dirty Checking yang tidak bekerja.
* **Perbaikan:** Pindahkan method tersebut ke Service terpisah atau inject reference bean kelas itu sendiri melalui constructor.

### 3. Kesalahan: Menggunakan `findAll()` untuk Memeriksa Keberadaan Data
* **Pola Buruk:**
  ```java
  if (orderRepository.findAll().stream().anyMatch(o -> o.getTrackingNumber().equals(target))) {
      // do something
  }
  ```
  Ini menarik jutaan row dari database ke JVM heap hanya untuk mengecek ketersediaan satu data.
* **Perbaikan:** Gunakan kueri SQL `EXISTS`:
  ```java
  boolean existsByTrackingNumber(String trackingNumber);
  ```
  RDBMS akan berhenti mengeksekusi segera setelah mencocokkan indeks baris pertama via statement: `SELECT 1 FROM orders WHERE tracking_number = ? LIMIT 1;`.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Definisikan Nilai Statement Timeout dan Lock Timeout:**
   Jangan biarkan transaksi menggantung selamanya menunggu antrean lock. Selalu set timeout secara deklaratif:
   ```properties
   # Properti Postgres / JDBC
   spring.jpa.properties.jakarta.persistence.query.timeout=5000
   spring.datasource.hikari.connection-timeout=3000
   ```
2. **Karantina Operasi Batch ke Transaksi Khusus:**
   Lakukan `flush()` dan `clear()` berkala pada EntityManager saat memproses data berukuran besar untuk menjaga Persistence Context tetap ramping:
   ```java
   for (int i = 0; i < entities.size(); i++) {
       entityManager.persist(entities.get(i));
       if (i % 50 == 0) {
           entityManager.flush(); // Tulis SQL ke buffer database
           entityManager.clear(); // Hapus seluruh objek dari First-Level Cache RAM
       }
   }
   ```
3. **Pisahkan Database Read Replica (CQRS Pattern):**
   Rancang arsitektur DataSource routing (`AbstractRoutingDataSource`) yang memisahkan koneksi Master (Write) dan Read-Replica (Read-Only) secara otomatis berdasarkan flag `@Transactional(readOnly = true)`.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Optimalisasi Indeks B-Tree: Aturan Kolom Komposit (*Leftmost Prefix Rule*)
Pembuatan indeks komposit `CREATE INDEX idx_user_status_date ON orders(user_id, status, created_at);` bekerja berdasarkan pohon biner seimbang.
*   Query `WHERE user_id = 10 AND status = 'PAID'` $\rightarrow$ **Index Scan Optimal**.
*   Query `WHERE status = 'PAID' AND created_at > '2023-01-01'` $\rightarrow$ **Full Table Scan!** Karena kueri melewatkan elemen *leftmost prefix* (`user_id`).
*   **Kaidah Desain Indeks:** Urutkan kolom dalam indeks komposit berdasarkan:
    1. Kolom Pencarian Kesetaraan (*Equality match*, e.g., `user_id = ?`)
    2. Kolom Pengurutan (*Sorting Order*, e.g., `ORDER BY created_at`)
    3. Kolom Jangkauan (*Range match*, e.g., `amount > 500`)

### 2. Konfigurasi Second-Level Cache (L2C) dengan Redisson / Ehcache
Gunakan Second-Level Cache hanya untuk data yang **jarang dimutasi namun sangat sering dibaca** (seperti Master Wilayah, Tarif Pajak, Konfigurasi Sistem):

```java
@Entity
@Table(name = "tax_rates")
@Cacheable
@org.hibernate.annotations.Cache(usage = CacheConcurrencyStrategy.READ_ONLY)
public class TaxRate {
    @Id
    private Long id;
    private BigDecimal percentage;
}
```
*Jangan pernah* meletakkan entitas transaksional volatil tinggi di L2C, karena overhead invalidasi cache antar-node cluster via jaringan akan menghancurkan skalabilitas aplikasi secara keseluruhan.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. SQL Injection pada Dynamic JPQL & Criteria API
Meskipun menggunakan ORM, SQL Injection tetap dapat terjadi jika merangkai string kueri secara manual!

* **Kode Sangat Rentan (Vulnerable Code):**
  ```java
  // Fatal: Penggabungan string mentah
  String query = "SELECT u FROM User u WHERE u.username = '" + userInput + "'";
  return entityManager.createQuery(query, User.class).getResultList();
  ```
* **Kode Aman (Remediated Code):**
  ```java
  // Wajib: Bind parameters menggunakan Named Parameter
  String safeQuery = "SELECT u FROM User u WHERE u.username = :username";
  return entityManager.createQuery(safeQuery, User.class)
                      .setParameter("username", userInput)
                      .getResultList();
  ```

### 2. Database Least Privilege Principle
User yang digunakan oleh pool koneksi aplikasi runtime Java **tidak boleh** memiliki status `SUPERUSER` atau hak `DDL` (seperti `CREATE TABLE`, `DROP TABLE`, `ALTER TABLE`). Batasi izin pengguna hanya ke `SELECT, INSERT, UPDATE, DELETE` pada skema database yang relevan. Perubahan skema harus didelegasikan sepenuhnya ke tool migrasi terisolasi seperti Flyway atau Liquibase yang dieksekusi terpisah pada pipeline deployment CI/CD.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Konfigurasi Logging Presisi Tinggi (Bebas Polusi Log)
Menyalakan `show-sql: true` pada Spring Boot adalah anti-pattern performa di produksi karena mencetak langsung ke konsol `System.out` yang bersifat memblokir thread eksekusi (*synchronous I/O*). Gunakan SLF4J logger terstruktur:

```yaml
# application.yml
logging:
  level:
    org.hibernate.SQL: DEBUG
    org.hibernate.orm.jdbc.bind: TRACE # Mencetak nilai binding parameter
    org.hibernate.stat: DEBUG          # Hibernate Metrics & Statistics
    com.zaxxer.hikari: DEBUG           # Hikari Connection Pool State
```

### 2. Analisis Query Melalui EXPLAIN ANALYZE
Saat mengoptimasi slow query, ambil query native yang dicetak Hibernate dan jalankan langsung pada shell RDBMS menggunakan `EXPLAIN (ANALYZE, BUFFERS)`:

```sql
EXPLAIN (ANALYZE, BUFFERS) 
SELECT o.id, o.total_amount 
FROM payment_orders o 
WHERE o.customer_id = 99823 AND o.created_at >= '2026-01-01 00:00:00';
```
Periksa output berikut:
*   **Seq Scan (Sequential Scan):** RDBMS memindai seluruh isi tabel di disk. Solusi: Buat indeks yang mencakup parameter filter.
*   **Index Scan vs Bitmap Index Scan vs Index Only Scan:** *Index Only Scan* adalah skenario terbaik karena seluruh kolom yang diminta kueri dapat diekstraksi langsung dari pohon indeks memori tanpa perlu mengakses blok tabel fisik (*Heap Fetch*).

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+-----------------------------------+----------------------------------------------------------------------------------+
| AREA                              | PERATURAN ARSITEKTURAL UTAMA                                                     |
+-----------------------------------+----------------------------------------------------------------------------------+
| Relasi JPA                        | Hindari FetchType.EAGER pada relasi asosiasi. Selalu gunakan LAZY secara default.|
+-----------------------------------+----------------------------------------------------------------------------------+
| Mitigasi N+1                      | Gunakan JOIN FETCH atau @EntityGraph untuk 1 relasi koleksi; @BatchSize untuk    |
|                                   | koleksi berlapis. Gunakan DTO Projection untuk read-only query.                 |
+-----------------------------------+----------------------------------------------------------------------------------+
| Transaksi                         | JANGAN meletakkan network call (HTTP/gRPC/Third-party API) di dalam lingkup      |
|                                   | method @Transactional.                                                           |
+-----------------------------------+----------------------------------------------------------------------------------+
| Connection Pool                   | Rumus HikariCP: Pool Size = (Core DB * 2) + Spindle. Nyalakan fixed-size pool    |
|                                   | (minIdle = maxPoolSize). Aktifkan leakDetectionThreshold = 5000ms.               |
+-----------------------------------+----------------------------------------------------------------------------------+
| Konkurensi Kritis                 | Gunakan Optimistic Locking (@Version) untuk proteksi pembaruan multi-user.      |
|                                   | Gunakan Pessimistic Locking (SELECT FOR UPDATE) untuk pemrosesan saldo/inventori |
|                                   | bernilai kritis tinggi.                                                          |
+-----------------------------------+----------------------------------------------------------------------------------+
| Identitas Entitas                 | Gunakan GenerationType.SEQUENCE (dengan pooled-lo) untuk mengaktifkan JDBC       |
|                                   | Batching secara maksimal. IDENTITY menonaktifkan batching.                       |
+-----------------------------------+----------------------------------------------------------------------------------+
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa yang terjadi pada pemanggilan method `save()` atau `persist()` pada sebuah entitas berelasi JPA di dalam blok `@Transactional`? Apakah query `INSERT` langsung terkirim ke database saat baris tersebut dieksekusi?**
   * *Jawaban:* Tidak secara langsung (kecuali ID generator bertipe `IDENTITY`). Entitas dimasukkan ke dalam Persistence Context dengan status `MANAGED` dan aksinya dimasukkan ke dalam `ActionQueue`. Kueri SQL `INSERT` baru dikirim ke database saat siklus `flush()` terjadi (baik secara eksplisit, sebelum eksekusi kueri JPQL lain, atau saat transaksi berakhir sebelum proses *commit*).

2. **Mengapa implementasi `FetchType.EAGER` dianggap sebagai anti-pattern pada aplikasi berskala besar?**
   * *Jawaban:* `FetchType.EAGER` memicu pengambilan data relasi yang tidak fleksibel pada setiap kali entitas induk dimuat, bahkan ketika business logic yang sedang berjalan tidak membutuhkan data anak tersebut. Hal ini menyebabkan pemborosan alokasi memori heap, latensi kueri yang lambat, dan sering kali secara tidak sadar memicu problem $N+1$ query di balik layar saat menggunakan query JPQL biasa.

3. **Apa perbedaan mendasar antara method `EntityManager.find()` dan `EntityManager.getReference()`?**
   * *Jawaban:* `find()` melakukan lookup ke Persistence Context, dan jika data tidak ada, langsung mengeksekusi kueri `SELECT` SQL ke database dan mengembalikan entitas nyata yang ter-hydrate penuh. `getReference()` tidak langsung mengeksekusi kueri SQL; ia mengembalikan proxy objek Hibernate kosong (*lazy entity placeholder*) yang hanya memiliki atribut ID terisi, dan baru mengeksekusi query database saat metode getter non-ID dari objek tersebut diakses.

4. **Bagaimana cara mencegah `LazyInitializationException` tanpa menyalakan konfigurasi `spring.jpa.open-in-view=true`?**
   * *Jawaban:* Dengan memastikan data yang dibutuhkan oleh presentation layer dimuat sebelum transaksi berakhir di Service Layer, yaitu dengan memanfaatkan DTO Projections, query kustom menggunakan klausa `JOIN FETCH`, atau menggunakan spesifikasi JPA `@EntityGraph`.

5. **Apa fungsi utama dari kolom `@Version` dalam entitas JPA?**
   * *Jawaban:* Untuk mengaktifkan mekanisme *Optimistic Concurrency Control*. Setiap kali entitas di-update, Hibernate secara otomatis membandingkan nilai versi dan menaikkan nomor versinya sebesar 1 (`SET version = version + 1 WHERE id = ? AND version = ?`). Jika ada transaksi lain yang telah memodifikasi baris tersebut sebelumnya, update akan mengembalikan angka 0 baris terpengaruh, memicu `OptimisticLockException` untuk mencegah data tertimpa (*Lost Update*).

---

### Soal Tingkat Menengah (Intermediate)

6. **Diberikan skenario: Sebuah method `@Transactional` mengeksekusi pencarian 5.000 data entitas, lalu mengubah satu kolom atribut pada setiap entitas tersebut. Mengapa latency eksekusi transaksi ini melonjak tinggi di akhir siklus method, dan bagaimana cara memperbaikinya?**
   * *Jawaban:* Hibernate menahan 5.000 objek dalam First-Level Cache (Identity Map) dan menyimpan 5.000 salinan awal di Snapshot Map. Pada saat `flush()`, *Dirty Checking Engine* harus membandingkan $5.000 \times M$ atribut secara reflektif, menghasilkan lonjakan CPU dan GC pressure masif. Solusi: Gunakan kueri *Bulk Update* JPQL (`UPDATE Order o SET o.status = :status WHERE ...`) yang mengeksekusi satu statement SQL langsung ke database tanpa memuat ribuan entitas ke memori L1 cache, atau lakukan proses batching berkala dengan kombinasi `flush()` dan `clear()`.

7. **Mengapa penambahan indeks B-Tree yang terlalu banyak pada sebuah tabel justru dapat menghancurkan performa aplikasi pada sistem bertipe Write-Heavy (High Throughput OLTP)?**
   * *Jawaban:* Setiap operasi `INSERT`, `UPDATE`, dan `DELETE` tidak hanya memodifikasi blok data tabel utama, tetapi juga mengharuskan RDBMS memperbarui setiap struktur pohon B-Tree indeks yang terdaftar pada tabel tersebut secara sinkron. Operasi penulisan indeks melibatkan reorganisasi balancing node, *page split*, penulisan tambahan ke Write-Ahead Log (WAL), dan fragmentasi disk, yang secara drastis menurunkan throughput IOPS penulisan database.

8. **Kapan Anda harus memilih `PESSIMISTIC_WRITE` daripada `@Version` (Optimistic Locking)? Jelaskan analisis trade-off teknisnya!**
   * *Jawaban:* `PESSIMISTIC_WRITE` (`SELECT FOR UPDATE`) wajib dipilih saat rasio konflik penulisan (*contention rate*) sangat tinggi pada data finansial/inventori krusial (misal: flash sale tiket konser dengan stok terbatas). Pada skenario ini, jika menggunakan Optimistic Locking, mayoritas transaksi akan gagal melempar `OptimisticLockException` dan harus di-retry berulang kali, yang justru memboroskan sumber daya komputasi. Trade-offnya: `PESSIMISTIC_WRITE` menahan lock baris fisik di database, menyebabkan thread lain harus mengantre (*thread blocking*), sehingga menurunkan konkurensi paralel sistem secara keseluruhan.

9. **Jelaskan mekanisme kerja *Phantom Read* dan bagaimana tingkat isolasi transaksi (*Isolation Level*) database mencegah fenomena tersebut!**
   * *Jawaban:* *Phantom Read* terjadi ketika Transaksi A mengeksekusi kueri pembacaan rentang baris data (`SELECT * FROM orders WHERE amount > 100`), kemudian Transaksi B menyisipkan data baru yang memenuhi kriteria tersebut (`INSERT INTO orders ... amount = 150`) dan melakukan *commit*. Jika Transaksi A mengeksekusi kueri yang sama lagi, baris baru ("phantom row") akan tiba-tiba muncul. Isolasi `REPEATABLE READ` (pada banyak RDBMS melalui implementasi MVCC) atau `SERIALIZABLE` (melalui Range/Gap Locks) mencegah hal ini dengan cara menyajikan snapshot snapshot point-in-time yang konsisten sepanjang umur Transaksi A berlangsung.

10. **Bagaimana cara HikariCP mengeliminasi kebuntuan (*Deadlock*) koneksi saat thread bertingkat memerlukan lebih dari satu koneksi database secara simultan?**
    * *Jawaban:* HikariCP tidak dapat secara mandiri mendeteksi *distributed logical application deadlock*, namun menyediakan konfigurasi `connectionTimeout`. Jika thread gagal mendapatkan koneksi sekunder dalam jangka waktu batas (default: 30 detik), HikariCP membatalkan antrean dengan melempar `SQLException: Connection is not available`. Namun, konfigurasi pool size minimal berbasis teori antrean:
    
      $$\text{Max Pool Size} = \text{Thread Count} \times (\text{Maksimum Koneksi Simultan Per Thread} - 1) + 1$$
      
      harus diterapkan oleh arsitek sistem untuk membuktikan secara matematis bahwa kelaparan koneksi (*deadlock starvation*) tidak akan pernah tercapai.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: Real-Time High-Throughput E-Wallet & Ledger Engine

#### Deskripsi
Bangunlah sebuah core mini-service finansial (*Double-Entry Bookkeeping Ledger Engine*) menggunakan Java 21, Spring Boot 3, PostgreSQL, dan HikariCP yang mampu memproses mutasi saldo transfer dana antar-rekening secara konkuren, presisi, tanpa terjadi saldo minus, bebas *Lost Update*, dan mampu memitigasi problem performa persistensi.

#### Spesifikasi Fungsional & Kebutuhan Teknis:
1. **Schema Persistensi:**
   * Buat tabel `wallets` (id, user_id, balance, version, created_at).
   * Buat tabel `ledger_entries` (id, transaction_id, source_wallet_id, destination_wallet_id, amount, status, created_at).
   * Gunakan `GenerationType.SEQUENCE` dengan allocation size 50.
2. **Implementasi Anti-Lost Update:**
   * Buat method transfer dana: `void transferFunds(Long fromWalletId, Long toWalletId, BigDecimal amount)`.
   * Implementasikan penguncian akun menggunakan **Pessimistic Locking** (`SELECT FOR UPDATE`).
   * **Wajib:** Terapkan pengurutan penguncian (*Lock Ordering by Primary Key ID ASC*) untuk mencegah terjadinya database **Deadlock** ketika Wallet A mentransfer ke Wallet B secara bersamaan dengan Wallet B mentransfer ke Wallet A:
     ```java
     // Hint pencegahan deadlock:
     Long firstId = fromId < toId ? fromId : toId;
     Long secondId = fromId < toId ? toId : fromId;
     // Lock firstId terlebih dahulu, kemudian lock secondId!
     ```
3. **Optimasi Batching & Reporting:**
   * Buat sebuah batch job endpoint untuk memasukkan 10.000 dummy audit record menggunakan JDBC Batching berukuran kepingan (*chunk*) 500 baris.
   * Buat kueri summary transaksi reporting bulanan menggunakan **DTO Constructor Projection** (jangan memuat relasi JPA mentah).
4. **Verifikasi Beban Konkurensi (Testing Benchmark):**
   * Tulis sebuah unit/integration test menggunakan `java.util.concurrent.ExecutorService` yang menjalankan 100 thread secara simultan.
   * Seluruh 100 thread harus mencoba memotong saldo dari satu dompet yang sama (Saldo awal: Rp 1.000.000, setiap thread memotong Rp 20.000).
   * **Hasil Pengujian yang Lulus:** Tepat 50 transaksi harus berhasil, 50 transaksi lainnya harus gagal melempar *InsufficientBalanceException*, saldo akhir dompet harus bernilai **tepat Rp 0.00**, dan tidak boleh ada satupun *Deadlock Exception* tercatat di log!
5. **Observabilitas HikariCP:**
   * Set `leakDetectionThreshold = 3000`.
   * Tulis satu unit test yang memicu koneksi sengaja ditahan lebih dari 3 detik untuk membuktikan bahwa *Leak Detection Mechanism* HikariCP aktif dan mencetak stack trace warning di konsol logger.