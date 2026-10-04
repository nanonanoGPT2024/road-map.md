# Kurikulum Rekayasa Perangkat Lunak Enterprise: Java
## Kategori: 02-Programming-Languages
### BAB 05: Data Persistence, ORM & Database Performance Tuning
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis dan Membedah Internal Hibernate 6.x & JPA**: Menjelajahi siklus hidup *Persistence Context*, mekanisme *Dirty Checking* berbasis *Bytecode Enhancement*, struktur *ActionQueue*, dan implementasi *Two-Level Caching* (L1 & L2) terdistribusi.
- **Menguasai Arsitektur Connection Pooling**: Menyetel dan mengoptimalkan HikariCP pada level produksi menggunakan metrik latensi *pool checkout*, *thread starvation analysis*, dan algoritma lock-free `ConcurrentBag`.
- **Mengimplementasikan Pola Multi-Tenancy & Read-Write Replica Routing**: Membangun routing dinamis tingkat enterprise memanfaatkan `AbstractRoutingDataSource` untuk pemisahan *Read/Write* dan isolasi data *tenant*.
- **Menerapkan Advanced Concurrency Control & Isolation**: Mengelola anomali konkurensi database (*Lost Updates*, *Write Skew*, *Phantom Reads*) melalui *Optimistic Locking* dengan *backoff retry* serta *Pessimistic Locking* berdaya tahan tinggi.
- **Mengeliminasi Hambatan Performa Eksekusi Batch**: Merancang arsitektur batch insertion/updation skala jutaan baris data menggunakan JDBC Batching, *stateless sessions*, dan *memory-conscious flush/clear cycles*.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Java Virtual Machine (JVM) Internals**: Manajemen memori heap, GC ergonomics, dan thread model Java 21+.
- **Database Relasional & SQL Tingkat Lanjut**: Paham tentang transaction isolation levels (Read Committed, Repeatable Read, Serializable), B-Tree Indexing, dan analisis `EXPLAIN ANALYZE`.
- **Dasar Java Persistence API (JPA)**: Familiar dengan pemetaan relasi entitas `@OneToMany`, `@ManyToOne`, `@ManyToMany`, dan query dasar menggunakan JPQL/HQL.
- **Spring Framework Core**: Mekanisme Dependency Injection, Dynamic Proxies, dan Spring AOP (khususnya cara kerja `@Transactional`).

---

### 3. Concept & Internal Architecture

#### 3.1. Anatomi Internal Persistence Context & Lifecycle
Hibernate mengimplementasikan spesifikasi JPA melalui arsitektur berorientasi status. Jantung dari Hibernate adalah `EntityManager` (yang membungkus `SessionImpl`), di mana `PersistenceContext` bertindak sebagai *Unit of Work* dan *First-Level Cache* (L1 Cache).

```
+-----------------------------------------------------------------------+
| Hibernate SessionImpl (L1 Cache / Unit of Work)                      |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  | PersistenceContext                                              |  |
|  |  - EntityUniqueKey (Entity Class + ID) -> Entity Instance       |  |
|  |  - EntityEntry (Loaded State Array, Status: MANAGED, READ_ONLY) |  |
|  +-----------------------------------------------------------------+  |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  | ActionQueue                                                     |  |
|  |  - EntityInsertAction       - EntityUpdateAction                |  |
|  |  - EntityDeleteAction       - CollectionRecreateAction          |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

##### Mekanisme Dirty Checking
Secara default, saat entitas dimuat dari database:
1. Hibernate menyimpan snapshot array status asli entitas (`LoadedState`) di dalam metadata `EntityEntry`.
2. Saat terjadi sinkronisasi atau pemanggilan `flush()`, Hibernate membandingkan nilai properti saat ini dari objek Java dengan array `LoadedState` snapshot tersebut melalui refleksi.
3. **Bytecode Enhancement Optimization**: Pada skala produksi enterprise, refleksi ini memicu overhead CPU dan memori. Mengaktifkan *bytecode enhancement* (via plugin Hibernate Gradle/Maven) mengubah setter class entitas secara langsung saat kompilasi. Modifikasi field akan langsung menandai entitas sebagai *dirty* via *bitset mask*, menghilangkan kebutuhan array snapshot ganda dan scanning reflektif berbasis O(N).

##### The ActionQueue & Flush Order
Hibernate tidak langsung mengeksekusi SQL saat method entitas atau `save()` dipanggil. Seluruh operasi diubah menjadi action objek dan dimasukkan ke dalam `ActionQueue`. Saat terjadi `flush()`, operasi dieksekusi dengan urutan yang sudah diprediksi untuk mencegah pelanggaran *Foreign Key*:
1. `OrphanRemovalAction`
2. `EntityInsertAction` / `EntityIdentityInsertAction`
3. `EntityUpdateAction`
4. `QueuedOperationCollectionAction`
5. `CollectionRemoveAction`
6. `CollectionUpdateAction`
7. `CollectionRecreateAction`
8. `EntityDeleteAction`

#### 3.2. HikariCP Internals: Lock-Free Concurrency
HikariCP mencapai latensi mikrodetik melalui eliminasi overhead sinkronisasi thread:
- **`ConcurrentBag`**: Struktur data internal HikariCP. Alih-alih menggunakan antrean blocking (`LinkedBlockingQueue`), `ConcurrentBag` memprioritaskan peminjaman koneksi yang terikat pada thread yang sama melalui `ThreadLocal`.
  1. Thread meminjam koneksi: Cek daftar lokal (`ThreadLocal<List<Object>>`). Jika ada koneksi tak terpakai, segera klaim via CAS (*Compare-And-Swap*).
  2. Jika kosong di `ThreadLocal`, pindah mencari ke shared list umum menggunakan scanning *lock-free*.
  3. Jika masih kosong, thread menggunakan `SynchronousQueue` untuk menunggu hingga koneksi lain dikembalikan (handoff mechanism).
- **FastList**: Pengganti `ArrayList` standar Java. Menghilangkan validasi batas array (`rangeCheck`) dan memungkinkan penghapusan elemen dari indeks terakhir ke depan, yang secara drastis mempercepat siklus operasi JDBC `Statement.close()`.

#### 3.3. Arsitektur Dynamic DataSource Routing
Untuk aplikasi enterprise berskala tinggi, beban transaksi dipisahkan antara *Primary/Leader* (Write) dan *Secondary/Follower* (Read-Only).

```
Application Layer -> [ @Transactional(readOnly = true/false) ]
                                  |
                                  v
                      TransactionInterceptor
                                  |
                                  v
                 TransactionSynchronizationManager
              (isCurrentTransactionReadOnly() -> true/false)
                                  |
                                  v
                    AbstractRoutingDataSource
                    (determineCurrentLookupKey)
                     /                      \
                    /                        \
    (Write Operations)                      (Read Operations)
            v                                       v
    Primary HikariCP Pool                 Replica HikariCP Pool
            |                                       |
            v                                       v
    PostgreSQL Primary                    PostgreSQL Read-Replica
```

Alur kerja routing:
1. Spring mengevaluasi konteks `@Transactional`.
2. `TransactionSynchronizationManager` menyimpan metadata transaksi (apakah read-only atau read-write).
3. Implementasi kustom `AbstractRoutingDataSource` membaca metadata tersebut dan mengembalikan kunci lookup yang sesuai (`WRITE` atau `READ`).
4. Routing DataSource mengambil koneksi dari sub-pool HikariCP yang tepat.
5. Karena koneksi dibatasi per transaksi, pemisahan ini mewajibkan koneksi diikat *sebelum* Hibernate membuka session JDBC fisik. Hal ini diselesaikan menggunakan wrapper `LazyConnectionDataSourceProxy`.

---

### 4. Why & What

| Dimensi | Pendekatan Naif / Tradisional | Arsitektur Enterprise Modern |
| :--- | :--- | :--- |
| **Connection Pooling** | Default pool (Tomcat JDBC / DBCP) tanpa metrik latency, pooling sizing sembarangan ($N \times 100$). | HikariCP ter-tuning presisi via formula Little's Law, metrik thread pool monitoring via Micrometer. |
| **Transaction Management** | `@Transactional` tanpa parameter eksplisit pada class controller atau service; tercampur operasi IO eksternal. | Service terisolasi ketat, read-only demarcation terpisah, transaksi pendek (short-lived) tanpa IO blocking. |
| **Dirty Checking** | Reflektif snapshot memory scanning per flush event. | Build-time Bytecode Enhancement; mutasi field dideteksi instan via bitwise flags. |
| **Database Scalability** | Single monolithic database instance; semua query dihantamkan ke Primary. | Read-Write splitting via `AbstractRoutingDataSource` & multi-tenant dynamic schema resolution. |
| **Locking Strategy** | Tanpa locking (rawan *lost updates*) atau Pessimistic Lock berlebihan (pemicu *deadlock*). | *Optimistic Locking* dengan exponentional backoff retry untuk OLTP, *Pessimistic Lock* selektif dengan query timeout. |

---

### 5. How: Transaction Execution Workflow

Di bawah ini adalah alur komprehensif penanganan eksekusi transaksi yang melibatkan ORM, DataSource Proxy, Transaction Synchronization Manager, dan HikariCP:

```
[Service Layer]         [TxInterceptor]     [LazyConnectionProxy]   [RoutingDataSource]   [HikariCP Pool]       [Hibernate Engine]
       |                       |                      |                     |                    |                     |
 1. invokeMethod() ----------> |                      |                     |                    |                     |
       |                 2. Init Context              |                     |                    |                     |
       |                    Set readOnly flag         |                     |                    |                     |
       |                       |                      |                     |                    |                     |
       |                 3. Open Session ----------------------------------------------------------------------------> |
       |                       |                      |                     |                    |                4. Initialize Session
       |                       |                      |                     |                    |                   Create ActionQueue
       |                       |                      |                     |                    |                     |
       |                 5. Execute Entity Query      |                     |                    |                     |
       |                       | -------------------> |                     |                    |                     |
       |                       |               6. Need Real Conn?           |                    |                     |
       |                       |                      | ----------> 7. determineKey()            |                     |
       |                       |                      |                     |                    |                     |
       |                       |                      | <------------------ |                    |                     |
       |                       |                      |                     |                    |                     |
       |                       |                      | 8. getConnection() --------------------> |                     |
       |                       |                      |                     |             9. ThreadLocal scan          |
       |                       |                      |                     |                Borrow Conn               |
       |                       |                      | <--------------------------------------- |                     |
       |                       |                      |                                                                |
       |                       |                      | 10. Pass connection to Hibernate Session --------------------> |
       |                       |                      |                                                                |
       |                       |                      |                                                          11. Execute SQL
       |                       |                      |                                                              Put in L1 Cache
       |                       |                      |                                                                |
       | <------------------------------------------------------------------------------------------------------------ |
       |
 12. Modify Entity
       |
 13. Exit Method ------------> |
                               | 14. commit()
                               | ----------------------------------------------------------------------------> |
                               |                                                                         15. flush()
                               |                                                                             Detect Dirty State
                               |                                                                             Sort ActionQueue
                               |                                                                             Execute Batch SQL
                               |                                                                         16. Physical Commit
                               |                                                                               |
                               | 17. Close Connection -------------------------------------------------------> |
                               |                      |                                                        |
                               |                      | 18. returnToPool() --------------------> |             |
                               |                      |                                   19. Release to       |
                               |                      |                                       ConcurrentBag    |
```

---

### 6. Analogy & ASCII Diagram

#### Analogi: Sistem Pengelolaan Inventaris Gudang Fisik
Bayangkan sebuah gudang e-commerce berkapasitas masif:
- **First-Level Cache (L1)**: Meja kerja pribadi operator (`Session`). Operator mengambil katalog barang dari rak pusat, lalu meletakkannya di mejanya. Selama ia bekerja, jika butuh data barang itu lagi, ia cukup melihat mejanya sendiri (tidak perlu jalan kaki ke rak utama). Meja ini musnah ketika shift operator selesai.
- **Bytecode Enhancement**: Operator menempelkan sensor alarm pada setiap kotak di mejanya. Saat ia memodifikasi isi kotak, lampu sensor langsung menyala merah (*dirty*). Tanpa sensor (default ORM), saat shift berakhir operator terpaksa membongkar dan memeriksa seluruh isi kotak satu per satu untuk mengecek apakah ada barang yang berubah (Reflective comparison).
- **Second-Level Cache (L2)**: Rak penyimpanan etalase bersama di tengah gudang (Redis / Hazelcast). Bisa diakses oleh semua operator.
- **HikariCP ConcurrentBag**: Sistem loker kunci kendaraan gudang. Setiap sopir punya nomor gantungan baju sendiri (*ThreadLocal*). Jika kunci cadangannya ada di gantungannya, ia langsung ambil tanpa antre. Jika tidak ada, ia melihat papan kunci bersama (*Shared Pool*), dan jika masih kosong, ia menunggu sopir lain menyerahkan kunci ke tangannya (*Hand-off*).

---

### 7. Simple & Practical Examples

Berikut adalah implementasi sistem persistensi tingkat produksi menggunakan Java 21 dan Spring Boot 3 / Hibernate 6.

#### 7.1. Konfigurasi Dynamic Routing & HikariCP
Konfigurasi ini memisahkan koneksi Master/Replica secara transparan berdasarkan anotasi `@Transactional(readOnly = ...)`.

```java
package com.enterprise.persistence.config;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.datasource.LazyConnectionDataSourceProxy;
import org.springframework.jdbc.datasource.lookup.AbstractRoutingDataSource;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import javax.sql.DataSource;
import java.util.HashMap;
import java.util.Map;

@Configuration
public class RoutingDataSourceConfig {

    public enum DataSourceType {
        PRIMARY, REPLICA
    }

    public static class TransactionRoutingDataSource extends AbstractRoutingDataSource {
        @Override
        protected Object determineCurrentLookupKey() {
            boolean isReadOnly = TransactionSynchronizationManager.isCurrentTransactionReadOnly();
            return isReadOnly ? DataSourceType.REPLICA : DataSourceType.PRIMARY;
        }
    }

    private HikariConfig createHikariConfig(String poolName, String jdbcUrl, String user, String pass, int maxPoolSize) {
        HikariConfig config = new HikariConfig();
        config.setPoolName(poolName);
        config.setJdbcUrl(jdbcUrl);
        config.setUsername(user);
        config.setPassword(pass);
        config.setMaximumPoolSize(maxPoolSize);
        config.setMinimumIdle(maxPoolSize / 2);
        config.setIdleTimeout(300_000); // 5 menit
        config.setMaxLifetime(1_800_000); // 30 menit
        config.setConnectionTimeout(20_000); // 20 detik
        config.setLeakDetectionThreshold(10_000); // Deteksi koneksi bocor setelah 10 detik

        // Optimasi tingkat JDBC Driver MySQL/PostgreSQL
        config.addDataSourceProperty("cachePrepStmts", "true");
        config.addDataSourceProperty("prepStmtCacheSize", "250");
        config.addDataSourceProperty("prepStmtCacheSqlLimit", "2048");
        config.addDataSourceProperty("useServerPrepStmts", "true");
        return config;
    }

    @Bean(name = "primaryDataSource")
    public DataSource primaryDataSource() {
        HikariConfig config = createHikariConfig(
            "PrimaryPool", 
            "jdbc:postgresql://10.0.1.10:5432/core_banking", 
            "db_admin", 
            "P@ssw0rdPrimary!", 
            20
        );
        return new HikariDataSource(config);
    }

    @Bean(name = "replicaDataSource")
    public DataSource replicaDataSource() {
        HikariConfig config = createHikariConfig(
            "ReplicaPool", 
            "jdbc:postgresql://10.0.1.11:5432/core_banking", 
            "db_readonly", 
            "P@ssw0rdReplica!", 
            40
        );
        return new HikariDataSource(config);
    }

    @Bean(name = "routingDataSource")
    public DataSource routingDataSource(
            @Qualifier("primaryDataSource") DataSource primary,
            @Qualifier("replicaDataSource") DataSource replica) {
        TransactionRoutingDataSource routingDataSource = new TransactionRoutingDataSource();
        Map<Object, Object> targetDataSources = new HashMap<>();
        targetDataSources.put(DataSourceType.PRIMARY, primary);
        targetDataSources.put(DataSourceType.REPLICA, replica);

        routingDataSource.setTargetDataSources(targetDataSources);
        routingDataSource.setDefaultTargetDataSource(primary);
        return routingDataSource;
    }

    @Primary
    @Bean
    public DataSource dataSource(@Qualifier("routingDataSource") DataSource routingDataSource) {
        // WAJIB: Membungkus dengan LazyConnectionDataSourceProxy agar evaluasi route
        // ditunda sampai statement dieksekusi, sehingga @Transactional terbaca sempurna.
        return new LazyConnectionDataSourceProxy(routingDataSource);
    }
}
```

#### 7.2. Implementasi High-Performance Entity dengan Concurrency Control
Berikut entity implementasi dengan optimasi performa: ID generator pool-allocated, versioning concurrency, equals/hashCode yang aman, dan mapping immutable.

```java
package com.enterprise.persistence.model;

import jakarta.persistence.*;
import org.hibernate.annotations.Cache;
import org.hibernate.annotations.CacheConcurrencyStrategy;
import org.hibernate.annotations.NaturalId;
import org.hibernate.annotations.NaturalIdCache;
import org.hibernate.proxy.HibernateProxy;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

@Entity
@Table(name = "bank_accounts", indexes = {
    @Index(name = "idx_account_num", columnList = "account_number")
})
@Cacheable
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE, region = "accountCache")
@NaturalIdCache
public class BankAccount implements Serializable {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "bank_account_seq_gen")
    @SequenceGenerator(
        name = "bank_account_seq_gen", 
        sequenceName = "seq_bank_account", 
        allocationSize = 50 // Mencegah round-trip database setiap fetch ID baru
    )
    private Long id;

    @NaturalId
    @Column(name = "account_number", nullable = false, unique = true, updatable = false, length = 32)
    private String accountNumber;

    @Column(name = "holder_name", nullable = false, length = 100)
    private String holderName;

    @Column(name = "balance", nullable = false, precision = 19, scale = 4)
    private BigDecimal balance;

    @Version
    @Column(name = "version", nullable = false)
    private Long version;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected BankAccount() {
        // Diperlukan Hibernate
    }

    public BankAccount(String accountNumber, String holderName, BigDecimal balance) {
        this.accountNumber = Objects.requireNonNull(accountNumber, "Account number cannot be null");
        this.holderName = Objects.requireNonNull(holderName, "Holder name cannot be null");
        this.balance = Objects.requireNonNull(balance, "Balance cannot be null");
        this.updatedAt = Instant.now();
    }

    public void credit(BigDecimal amount) {
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Credit amount must be positive");
        }
        this.balance = this.balance.add(amount);
        this.updatedAt = Instant.now();
    }

    public void debit(BigDecimal amount) {
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Debit amount must be positive");
        }
        if (this.balance.compareTo(amount) < 0) {
            throw new IllegalStateException("Insufficient funds");
        }
        this.balance = this.balance.subtract(amount);
        this.updatedAt = Instant.now();
    }

    // Hibernate-safe equals & hashCode menggunakan Java UUID / Natural ID
    @Override
    public final boolean equals(Object o) {
        if (this == o) return true;
        if (o == null) return false;
        Class<?> oEffectiveClass = o instanceof HibernateProxy proxy 
            ? proxy.getHibernateLazyInitializer().getPersistentClass() 
            : o.getClass();
        Class<?> thisEffectiveClass = this instanceof HibernateProxy proxy 
            ? proxy.getHibernateLazyInitializer().getPersistentClass() 
            : this.getClass();
        if (thisEffectiveClass != oEffectiveClass) return false;
        BankAccount that = (BankAccount) o;
        return getAccountNumber() != null && Objects.equals(getAccountNumber(), that.getAccountNumber());
    }

    @Override
    public final int hashCode() {
        return getClass().hashCode();
    }

    // Getters
    public Long getId() { return id; }
    public String getAccountNumber() { return accountNumber; }
    public String getHolderName() { return holderName; }
    public BigDecimal getBalance() { return balance; }
    public Long getVersion() { return version; }
    public Instant getUpdatedAt() { return updatedAt; }
}
```

#### 7.3. Service Layer dengan Concurrency Retry Strategy
Implementasi penyelesaian transaksi konkuren yang menangani `OptimisticLockException` melalui *Exponential Backoff Retry Pattern*.

```java
package com.enterprise.persistence.service;

import com.enterprise.persistence.model.BankAccount;
import jakarta.persistence.EntityManager;
import jakarta.persistence.OptimisticLockException;
import jakarta.persistence.PersistenceContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;

@Service
public class AccountBalanceService {

    private static final Logger log = LoggerFactory.getLogger(AccountBalanceService.class);
    private static final int MAX_RETRY_ATTEMPTS = 3;

    @PersistenceContext
    private EntityManager entityManager;

    private final TransactionTemplate transactionTemplate;

    public AccountBalanceService(PlatformTransactionManager transactionManager) {
        this.transactionTemplate = new TransactionTemplate(transactionManager);
        this.transactionTemplate.setIsolationLevel(TransactionDefinition.ISOLATION_READ_COMMITTED);
        this.transactionTemplate.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }

    public void transferWithOptimisticRetry(String fromAccountNum, String toAccountNum, BigDecimal amount) {
        int attempt = 0;
        while (attempt < MAX_RETRY_ATTEMPTS) {
            attempt++;
            try {
                // Eksekusi unit kerja dalam batasan transaksi yang terisolasi
                transactionTemplate.execute(status -> {
                    BankAccount source = findByAccountNumberForUpdate(fromAccountNum);
                    BankAccount destination = findByAccountNumberForUpdate(toAccountNum);

                    source.debit(amount);
                    destination.credit(amount);

                    // Flush eksplisit untuk mendeteksi konflik versi sebelum commit
                    entityManager.flush();
                    return null;
                });
                
                log.info("Transfer berhasil pada percobaan ke-{}", attempt);
                return;
            } catch (Exception ex) {
                if (isOptimisticLockingException(ex)) {
                    log.warn("Konflik terdeteksi pada attempt {}. Melakukan retry...", attempt);
                    if (attempt >= MAX_RETRY_ATTEMPTS) {
                        throw new IllegalStateException("Gagal memproses transaksi setelah limit retry tercapai.", ex);
                    }
                    backoff(attempt);
                } else {
                    // Non-concurrency error langsung rethrow
                    throw ex;
                }
            }
        }
    }

    private BankAccount findByAccountNumberForUpdate(String accountNumber) {
        return entityManager.createQuery(
                "SELECT b FROM BankAccount b WHERE b.accountNumber = :accNum", BankAccount.class)
                .setParameter("accNum", accountNumber)
                .getSingleResult();
    }

    private boolean isOptimisticLockingException(Throwable ex) {
        Throwable current = ex;
        while (current != null) {
            if (current instanceof OptimisticLockException || 
                current instanceof org.hibernate.StaleObjectStateException) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    private void backoff(int attempt) {
        try {
            long delay = (long) (Math.random() * 50) + (attempt * 100L);
            Thread.sleep(delay);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Thread interrupted during retry backoff", e);
        }
    }
}
```

---

### 8. Real World Case Study: High-Throughput Fintech Payment Gateway

#### 8.1. Konteks & Masalah
Sebuah platform Payment Gateway enterprise memproses $12.000$ *transactions per second* (TPS) pada momen *Flash Sale*. Sistem sebelumnya mengalami *cascading failure* dengan indikasi:
1. **Database Bottleneck**: 95% CPU usage pada database PostgreSQL utama.
2. **Connection Exhaustion**: HikariCP sering melempar `ConnectionTimeoutException: AppPool - Connection is not available, request timed out after 30000ms`.
3. **Deadlocks**: Mutasi balance wallet paralel saling memblokir (*Cyclic Dependency Locking*).
4. **Latency Degradation**: P99 naik dari 35ms melonjak ke 14.800ms.

#### 8.2. Root Cause Analysis (RCA)
- **Koneksi Tercekat IO**: Transaksi `@Transactional` membungkus panggilan REST API ke *third-party payment provider* (latensi 800ms). Koneksi database tetap ditahan (*held open*) selama network call berlangsung!
- **Dirty Checking Overhead**: Penggunaan JPA entities besar dengan 80+ kolom dievaluasi tanpa *bytecode enhancement*, membebani garbage collection hingga memicu *Stop-the-World* pause.
- **Write Amplification pada Reporting**: Query reporting operasional dieksekusi langsung pada instans database Primary.

#### 8.3. Solusi Arsitektural & Hasil Benchmarking
1. **Architectural Decoupling**: Transaksi database dipersingkat menjadi $<10$ms dengan memisahkan call I/O pihak ketiga ke luar boundary transaksi database.
2. **Implementation of CQRS & DataSource Routing**: Memecah query dashboard dan audit ke Postgres Read-Replicas via `AbstractRoutingDataSource`.
3. **Pessimistic Strict Ordering**: Akun pengirim dan penerima di-lock menggunakan Pessimistic Write dengan pengurutan ID numerik (`ORDER BY ID ASC`) untuk mencegah *Cyclic Wait Deadlock*.

```java
// Locking dengan Determinitic Ordering untuk Mencegah Deadlock
public void executeDeterministicTransfer(Long senderId, Long receiverId, BigDecimal amount) {
    Long firstLockId = senderId.compareTo(receiverId) < 0 ? senderId : receiverId;
    Long secondLockId = senderId.compareTo(receiverId) < 0 ? receiverId : senderId;

    // Lock resource dalam urutan yang deterministik
    BankAccount first = entityManager.find(BankAccount.class, firstLockId, LockModeType.PESSIMISTIC_WRITE);
    BankAccount second = entityManager.find(BankAccount.class, secondLockId, LockModeType.PESSIMISTIC_WRITE);

    BankAccount sender = senderId.equals(first.getId()) ? first : second;
    BankAccount receiver = receiverId.equals(first.getId()) ? first : second;

    sender.debit(amount);
    receiver.credit(amount);
}
```

| Metrik Kinerja | Sebelum Solusi | Setelah Solusi Arsitektural |
| :--- | :--- | :--- |
| **Throughput Stabil** | 1.800 TPS (Saturasi) | 14.500 TPS |
| **P99 Latency** | 14.800 ms | 42 ms |
| **HikariCP Active Leases** | 100% (Starvation) | Rata-rata 35% capacity |
| **Deadlock Events / Hari** | 1.450 insiden | 0 insiden |

---

### 9. Trade-offs: Architectural Matrix

```
       [KONSISTENSI & KONTROL]
                 ^
                 |      (Pessimistic Locking)
                 |       Latency: Tinggi
                 |       Throughput: Rendah - Sedang
                 |       Safety: Paling Tinggi
                 |
                 |                 (Optimistic + Retry)
                 |                  Latency: Rendah (di bawah persaingan rendah)
                 |                  Throughput: Sangat Tinggi
                 |                  Risk: Abort cascade bila kontensi tinggi
                 |
+----------------------------------------------------> [SKALABILITAS / THROUGHPUT]
                 |
                 |      (Read-Write Replica Routing)
                 |       Latency: Minimum
                 |       Scale: Horizontal Read
                 |       Trade-off: Replication Lag (Eventual Consistency)
                 |
                 v
       [RISIKO INKONSISTENSI DATA]
```

| Pola / Strategi | Keuntungan Performa | Biaya Komputasi & Memori | Kompleksitas Operasional | Risiko Arsitektural |
| :--- | :--- | :--- | :--- | :--- |
| **Optimistic Locking** | Tidak mengunci baris DB fisik; non-blocking throughput tinggi. | Minimal, hanya butuh alokasi 1 field version. | Rendah - Sedang (butuh retry handler). | Kegagalan masif (*retry storm*) saat terjadi *flash-crowd* pada baris yang sama. |
| **Pessimistic Locking** | Menjamin integritas mutlak data; tidak ada CPU waste untuk retry. | Mahal. Thread database tertahan hingga release. | Rendah (ditangani database engine). | Risiko fatal *Deadlock* dan *HikariCP Pool Depletion*. |
| **L2 Cache (Hazelcast/Redis)** | Mencegah round-trip network & IO ke SQL Database secara drastis. | Sangat Tinggi (RAM cluster terdistribusi). | Tinggi (Cache Invalidation, serialization overhead). | *Stale Data* jika ada modifikasi direct-update di database tanpa melewati L2 provider. |
| **JDBC Batch Updates** | Mengurangi jutaan Network Syscalls menjadi single batch payload. | Memori JVM meningkat sementara menampung *batch list*. | Rendah (otomatis via config JPA). | Identity Generation `GenerationType.IDENTITY` mematikan batching ini secara diam-diam! |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Pitfall 1: Kerusakan Batch Insert Akibat `GenerationType.IDENTITY`
- **Gejala**: Parameter `hibernate.jdbc.batch_size=50` sudah disetel, tetapi proses insert 100.000 data tetap memakan waktu puluhan detik dengan log query memunculkan statement `insert` satu per satu.
- **Akar Masalah**: Strategi `IDENTITY` memaksa database melakukan kalkulasi auto-increment saat eksekusi query. Hibernate *wajib* mengetahui ID entitas sesaat setelah `persist()`, sehingga Hibernate terpaksa mengeksekusi `insert` secara instan via JDBC dan mendisable mekanisme batching.
- **Solusi**: Ubah ke `GenerationType.SEQUENCE` dengan optimizer `pooled-lo` atau `allocationSize` yang memadai (misal: 50).

#### 10.2. Pitfall 2: Open Session in View (OSIV) Anti-Pattern
- **Gejala**: Database connection pool habis tanpa beban transaksi penulisan yang tinggi; banyak thread HTTP tertahan di status `WAITING`.
- **Akar Masalah**: Framework mengaktifkan `spring.jpa.open-in-view=true`. Session JPA tetap terbuka saat rendering respons JSON di Controller. Jika Jackson memicu lazy loading relasi yang belum ter-fetch, koneksi database dipinjam kembali secara implisit di layer web presentation.
- **Solusi**: Matikan OSIV secara mutlak di level konfigurasi:
  ```properties
  spring.jpa.open-in-view=false
  ```
  Gunakan DTO Projection atau JPQL `JOIN FETCH` eksplisit di layer repository.

#### 10.3. Pitfall 3: HikariCP Connection Leak
- **Gejala**: Log memunculkan:
  `App-Pool - Connection leak detection triggered for org.postgresql.jdbc.PgConnection@6b... on thread X, stack trace follows...`
- **Akar Masalah**: Peminjaman koneksi manual via DataSource native yang tidak ditutup di dalam blok `try-with-resources`, atau proses komputasi CPU-bound/I/O lambat berada di dalam lingkup `@Transactional`.
- **Solusi**: Setel `leakDetectionThreshold` (misal 5000ms). Pisahkan komputasi berat ke luar boundary `@Transactional`:
  ```java
  // SALAH: Koneksi ditahan saat I/O lambat
  @Transactional
  public void processOrder(OrderRequest request) {
      Order order = orderRepo.findById(request.id());
      paymentGatewayClient.callExternalHttpApi(); // 5000ms BLOCKING!
      order.markPaid();
  }

  // BENAR: Koneksi hanya diambil saat transaksi DB fisik
  public void processOrder(OrderRequest request) {
      paymentGatewayClient.callExternalHttpApi(); // Diluar transaksi DB
      orderService.updateOrderSuccess(request.id()); // Masuk ke @Transactional pendek (<5ms)
  }
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Nonaktifkan Hibernate DDL Auto di Produksi**: Pastikan `spring.jpa.hibernate.ddl-auto=validate` atau `none`. Gunakan migrator schema formal seperti Liquibase atau Flyway.
- [ ] **Kunci Ukuran Pool HikariCP**: Set nilai `maximum-pool-size` sama dengan `minimum-idle`. Ini mencegah overhead alokasi dan dealokasi koneksi dinamis oleh OS saat load spike.
- [ ] **Formula Ukuran Pool**: Terapkan formula standar hardware:
  $$\text{Pool Size} = T_n \times (\text{Core Count} \times 2) + \text{Spindle/Effective Disk Count}$$
- [ ] **Konfigurasi Logging Statement Tanpa Log Formatting Overhead**: Jangan gunakan `show-sql: true` pada `application.yml` karena melakukan `System.out.println` yang mengunci thread secara blocking. Gunakan logger engine:
  `logging.level.org.hibernate.SQL=DEBUG` dan `logging.level.org.hibernate.orm.jdbc.bind=TRACE`.
- [ ] **Gunakan DTO Projection untuk Query Read-Only**: Hindari me-load seluruh Managed Entity jika tujuannya hanya mengirim data transfer object (DTO).
- [ ] **Matikan Default Dirty Checking Snapshot via Bytecode Enhancement**: Tambahkan `hibernate-enhance-maven-plugin` pada fase kompilasi untuk otomatisasi deteksi mutasi entity yang efisien.

---

### 12. Hands-on Practice

Buat dan simpan file implementasi pada direktori: `hands-on/m02/`

#### Struktur Direktori Proyek:
```
hands-on/m02/
├── pom.xml
└── src/
    └── main/
        ├── java/
        │   └── com/enterprise/batch/
        │       ├── BatchApplication.java
        │       ├── config/
        │       │   └── PersistenceConfig.java
        │       ├── entity/
        │       │   └── SettlementTransaction.java
        │       ├── repository/
        │       │   └── SettlementRepository.java
        │       └── service/
        │           └── BatchSettlementService.java
        └── resources/
            └── application.yml
```

#### File: `hands-on/m02/pom.xml`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.3</version>
        <relativePath/>
    </parent>

    <groupId>com.enterprise</groupId>
    <artifactId>persistence-tuning-lab</artifactId>
    <version>1.0.0</version>
    <name>persistence-tuning-lab</name>

    <properties>
        <java.version>21</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.hibernate.orm.tooling</groupId>
                <artifactId>hibernate-enhance-maven-plugin</artifactId>
                <version>6.4.4.Final</version>
                <executions>
                    <execution>
                        <configuration>
                            <failOnError>true</failOnError>
                            <enableDirtyTracking>true</enableDirtyTracking>
                            <enableAssociationManagement>true</enableAssociationManagement>
                        </configuration>
                        <goals>
                            <goal>enhance</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```

#### File: `hands-on/m02/src/main/resources/application.yml`
```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/enterprise_db
    username: postgres
    password: postgrespassword
    driver-class-name: org.postgresql.Driver
    hikari:
      pool-name: EnterpriseBatchHikariPool
      maximum-pool-size: 15
      minimum-idle: 15
      connection-timeout: 30000
      leak-detection-threshold: 5000
  jpa:
    hibernate:
      ddl-auto: create-drop
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        jdbc:
          batch_size: 100
          order_inserts: true
          order_updates: true
          batch_versioned_data: true
        generate_statistics: false
```

#### File: `hands-on/m02/src/main/java/com/enterprise/batch/entity/SettlementTransaction.java`
```java
package com.enterprise.batch.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;

@Entity
@Table(name = "settlement_transactions")
public class SettlementTransaction {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "settlement_seq")
    @SequenceGenerator(name = "settlement_seq", sequenceName = "seq_settlement_tx", allocationSize = 100)
    private Long id;

    @Column(nullable = false, length = 64)
    private String transactionReference;

    @Column(nullable = false, precision = 15, scale = 2)
    private BigDecimal amount;

    @Column(nullable = false, length = 12)
    private String status;

    @Column(nullable = false)
    private Instant createdAt;

    protected SettlementTransaction() {}

    public SettlementTransaction(String transactionReference, BigDecimal amount, String status) {
        this.transactionReference = transactionReference;
        this.amount = amount;
        this.status = status;
        this.createdAt = Instant.now();
    }

    public Long getId() { return id; }
    public String getTransactionReference() { return transactionReference; }
    public BigDecimal getAmount() { return amount; }
    public String getStatus() { return status; }
    public Instant getCreatedAt() { return createdAt; }
}
```

#### File: `hands-on/m02/src/main/java/com/enterprise/batch/service/BatchSettlementService.java`
```java
package com.enterprise.batch.service;

import com.enterprise.batch.entity.SettlementTransaction;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.UUID;

@Service
public class BatchSettlementService {

    private static final Logger log = LoggerFactory.getLogger(BatchSettlementService.class);
    private static final int BATCH_SIZE = 100;

    @PersistenceContext
    private EntityManager entityManager;

    /**
     * Memproses bulk data secara efisien tanpa membebani L1 Persistence Context
     * yang berisiko menyebabkan java.lang.OutOfMemoryError.
     */
    @Transactional(propagation = Propagation.REQUIRED)
    public void processHighVolumeInsert(int totalRecords) {
        log.info("Memulai batch insertion untuk {} record...", totalRecords);
        long startTime = System.currentTimeMillis();

        for (int i = 0; i < totalRecords; i++) {
            SettlementTransaction tx = new SettlementTransaction(
                "TX-" + UUID.randomUUID(),
                BigDecimal.valueOf(100.50 + i),
                "SETTLED"
            );

            entityManager.persist(tx);

            // Bersihkan L1 Cache secara periodik berdasarkan ukuran batch
            if (i > 0 && i % BATCH_SIZE == 0) {
                entityManager.flush(); // Tulis data pending ke database buffer socket
                entityManager.clear(); // Hapus seluruh entity dari memori L1 cache
            }
        }

        // Tulis sisa entitas di luar kelipatan batch size
        entityManager.flush();
        entityManager.clear();

        long duration = System.currentTimeMillis() - startTime;
        log.info("Batch insertion selesai dalam {} ms!", duration);
    }
}
```

---

### 13. Exercises

#### Level Easy
Ubah mapping entitas pada `BankAccount` agar menggunakan optimasi `DynamicUpdate` dari Hibernate.
- **Tugas**: Tambahkan `@DynamicUpdate` pada kelas entity.
- **Validasi**: Verifikasi melalui logging SQL bahwa query `UPDATE` yang dihasilkan hanya mencakup kolom yang diubah nilainya, bukan seluruh kolom entitas.

#### Level Medium
Buat kustom interceptor atau repository implementation untuk mencegah *accidental cartesian product* pada pemanggilan data collection bersarang.
- **Tugas**: Buat relasi parent-child-grandchild (`Customer` -> `Order` -> `OrderItem`). Tulis query JPQL yang mengambil data pelanggan beserta relasinya tanpa menghasilkan $N \times M$ rows memory explosion di JDBC driver.
- **Validasi**: Gunakan assertion statistik Hibernate untuk memastikan total queries dieksekusi tepat 2 kali (*Split Query fetching*).

#### Level Hard
Rancang modul implementasi Hibernate Second-Level Cache (L2) menggunakan Redis / Redisson.
- **Tugas**: Integrasikan Redisson Hibernate Cache Provider. Konfigurasikan strategi `READ_WRITE` cache concurrency pada entitas katalog.
- **Validasi**: Matikan database PostgreSQL sesaat setelah pemanggilan pertama (`findById`). Buktikan query pemanggilan kedua dengan ID yang sama berhasil diselesaikan 100% dari cache tanpa melempar SQL Connection Exception.

---

### 14. Challenges

Skenario: Anda memimpin arsitektur core banking untuk migrasi sistem tabungan dengan 50 juta pengguna aktif.
- **Tantangan**: Saat tanggal 1 setiap bulan, sistem memicu *Interest Accrual Process* (perhitungan bunga bulanan) secara paralel pada 50 juta akun.
- **Spesifikasi & Kendala**:
  1. Waktu proses total tidak boleh melebihi 60 menit.
  2. Akun pengguna dapat tetap melakukan transaksi penarikan dana di ATM/Mobile Apps secara simultan selama batch processing berjalan tanpa mengalami crash atau blocking yang melebihi 500ms.
  3. Hindari `OutOfMemoryError` pada cluster microservices pod Spring Boot yang hanya memiliki RAM Heap 2GB.
  4. Rancang skema partisi transaksi, isolasi locking, pemanfaatan HikariCP, dan arsitektur persistensinya secara lengkap tanpa mengorbankan integritas data ACID (dilarang terjadi inkonsistensi saldo sebesar 1 Rupiah pun).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Soal)
1. **Mengapa strategi `GenerationType.IDENTITY` mematikan fitur JDBC batching di Hibernate?**
   - *Jawaban*: Karena database perlu mengeksekusi statement SQL `INSERT` seketika untuk mendapatkan nilai auto-increment primary key ID yang dihasilkan DB engine, sehingga Hibernate tidak dapat menunda eksekusi SQL ke dalam batch.

2. **Apa peran utama dari `ActionQueue` pada arsitektur internal Hibernate?**
   - *Jawaban*: Mengantrekan, mengelompokkan, dan mengurutkan operasi DML (Insert, Update, Delete) agar sinkronisasi ke database saat fase `flush()` dilakukan dalam sequence deterministik yang aman dari pelanggaran Foreign Key.

3. **Apa fungsi dari class `LazyConnectionDataSourceProxy` pada arsitektur Read-Write replica routing?**
   - *Jawaban*: Menunda peminjaman koneksi fisik JDBC dari DataSource sampai statement SQL pertama benar-benar dieksekusi, memungkinkan penentuan lookup routing key membaca konteks transaksi `@Transactional(readOnly = ...)` secara akurat.

4. **Bagaimana mekanisme `ConcurrentBag` di HikariCP meminimalkan thread contention?**
   - *Jawaban*: Menggunakan referensi thread-local cache untuk peminjaman koneksi lock-free, disusul compare-and-swap (CAS) lock-free scanning, dan mekanisme synchronous handoff queue.

5. **Apa dampak membiarkan `spring.jpa.open-in-view=true` (OSIV) di sistem enterprise berskala tinggi?**
   - *Jawaban*: Session database tetap terbuka hingga HTTP response selesai ditulis, menahan koneksi HikariCP terlalu lama di layer presentasi dan menyebabkan *connection pool exhaustion*.

#### Intermediate Level (5 Soal)
6. **Kapan anomali *Write Skew* terjadi, dan mengapa isolation level `REPEATABLE READ` tidak selalu dapat mencegahnya?**
   - *Jawaban*: *Write Skew* terjadi ketika dua transaksi membaca data tumpang tindih yang sama, melihat snapshot yang konsisten, namun memodifikasi data terpisah yang melanggar invariant bisnis global. `REPEATABLE READ` hanya mengunci baris individual yang dibaca/dimutasi, bukan predikat kondisi secara keseluruhan.

7. **Jelaskan perbedaan struktural cara kerja dirty checking reflektif default dengan Hibernate Bytecode Enhancement.**
   - *Jawaban*: Reflektif default mengalokasikan array ganda (`LoadedState`) saat entitas di-load dan membandingkan field satu per satu saat flush. Bytecode enhancement memodifikasi class file pada bytecode level untuk menandai flag/bitset dirty secara instan tepat saat setter dieksekusi, menghemat alokasi memori dan CPU cycles.

8. **Mengapa `entityManager.clear()` mutlak diperlukan saat memproses jutaan baris data pada satu transaksi batch?**
   - *Jawaban*: Untuk mengosongkan L1 Cache (Persistence Context). Jika tidak dibersihkan, Hibernate akan terus menyimpan reference setiap instance objek Java di memori hingga memicu `java.lang.OutOfMemoryError: Java heap space`.

9. **Apa perbedaan antara lock mode `PESSIMISTIC_READ` dan `PESSIMISTIC_WRITE` pada PostgreSQL?**
   - *Jawaban*: `PESSIMISTIC_READ` menggunakan statement SQL `FOR SHARE` (memperbolehkan thread lain membaca tapi melarang mengubah/menghapus), sedangkan `PESSIMISTIC_WRITE` menggunakan `FOR UPDATE` (mengunci baris secara eksklusif baik dari pembacaan locking lain maupun mutasi).

10. **Bagaimana anomali *Lost Update* dapat diatasi secara mutlak menggunakan Optimistic Locking?**
    - *Jawaban*: Melalui kolom `@Version`. Saat proses commit dilakukan, Hibernate menyertakan nomor versi pada klausa WHERE (`WHERE id = ? AND version = ?`). Jika versi di database sudah berubah akibat transaksi lain, jumlah row yang ter-update adalah 0, memicu Hibernate melempar `OptimisticLockException`.

#### Production Scenarios (3 Soal)

11. **Skenario 1**:
    Sebuah aplikasi e-commerce mendadak menolak transaksi pelanggan baru di jam sibuk dengan exception `HikariPool-1 - Connection is not available, request timed out after 30000ms`. Saat diteliti, utilization CPU database engine hanya 12%, dan memori server DB masih tersisa 70%.
    - **Analisis Root Cause**: Terjadi *thread starvation* di layer aplikasi atau kebocoran koneksi (*connection leak*). Penyebab paling umum adalah eksekusi synchronous network call (seperti third-party payment, log service, atau email notifications) di dalam blok `@Transactional`, menahan koneksi DB fisik tanpa memanfaatkannya.
    - **Solusi Terapeutik**: Aktifkan `leakDetectionThreshold=5000` di konfigurasi HikariCP untuk melacak stack trace pemegang koneksi yang lambat. Ekstrak seluruh blocking I/O ke luar method `@Transactional`. Pastikan connection pool sizing dihitung berbasis *Little's Law*.

12. **Skenario 2**:
    Tim Core System melaporkan terjadinya peningkatan deadlock signifikan di PostgreSQL pada tabel `wallets` saat transaksi settlement batch dieksekusi secara multithreading:
    `ERROR: deadlock detected; Process 14210 waits for ExclusiveLock on tuple (42, 12) of relation "wallets"...`
    - **Analisis Root Cause**: Terjadi locking silang (*Cyclic Lock Dependency*). Thread A meminjam Lock Wallet #10 lalu mencoba me-lock Wallet #20. Di waktu bersamaan, Thread B meminjam Lock Wallet #20 lalu mencoba me-lock Wallet #10.
    - **Solusi Terapeutik**: Wajibkan standardisasi urutan locking resource secara determinitik. Urutkan ID Wallet sebelum eksekusi query lock dilakukan (misal `sort(accountA.id, accountB.id)`), sehingga seluruh thread selalu me-lock dalam urutan yang identik (misal ID lebih kecil terlebih dahulu).

13. **Skenario 3**:
    Sebuah query laporan operasional JPQL me-load 5.000 data entitas `Merchant` beserta list `Store` dan data `Promotion` miliknya. Query menghasilkan ribuan duplicate rows dan respons service memakan waktu 45 detik.
    - **Analisis Root Cause**: Terjadi masalah *Cartesian Product Problem* akibat melakukan ganda `JOIN FETCH` pada lebih dari satu asosiasi bag/collection secara simultan (`SELECT m FROM Merchant m JOIN FETCH m.stores JOIN FETCH m.promotions`).
    - **Solusi Terapeutik**: Pecah query multi-join fetch menjadi beberapa query terpisah yang memanfaatkan Hibernate collection cache atau batch fetch (`@BatchSize(size = 50)`), atau proyeksikan data langsung ke record/DTO menggunakan interface projection flat tanpa me-load entitas managed ke L1 session.

---

### 16. Summary

1. **Persistence Context adalah Identity Map & Unit of Work**: Mengelola siklus hidup entitas melalui L1 Cache dan menyinkronkan data secara teratur via `ActionQueue`.
2. **Bytecode Enhancement adalah Kunci Skalabilitas Hibernate**: Menggantikan mekanisme reflection-based dirty checking bawaan dengan state tracking berbasis instruksi langsung di bytecode class, secara drastis mengurangi alokasi CPU dan heap memory.
3. **HikariCP Mengandalkan Algoritma Lock-Free**: Memanfaatkan `ConcurrentBag` dan struktur data custom `FastList` untuk mengeliminasi thread contention dan alokasi array yang tidak perlu pada performa throughput puncak.
4. **Pemisahan Traffic Baca & Tulis Mengurangi Beban Database Leader**: Memanfaatkan `AbstractRoutingDataSource` yang dikombinasikan dengan `LazyConnectionDataSourceProxy` memungkinkan segmentasi transaksi ke Primary vs Read-Replicas secara transparan.
5. **Batch Processing Skala Masif Memerlukan Pengendalian Memori Eksplisit**: Hindari `GenerationType.IDENTITY`, gunakan `allocationSize` sequence yang optimal, aktifkan penataan urutan SQL inserts/updates, dan kosongkan L1 cache secara berkala via kombinasi `flush()` dan `clear()`.