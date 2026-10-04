# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Data Access Layer & Persistence Architecture**
**Kategori: 04-Backend-and-Database (Spring Boot)**

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengonfigurasi** arsitektur *Dynamic Routing DataSource* berbasis `AbstractRoutingDataSource` untuk memisahkan beban *Read/Write* (Master-Replica) secara otomatis via AOP dan integrasi `@Transactional(readOnly = true)`.
- **Mengevaluasi dan Mengatasi** limitasi *Hibernate 6.x Semantic Query Model* (SQM) terkait pemrosesan *batching*, eliminasi *N+1 queries* menggunakan dynamic entity graph, serta isolasi konkurensi data tingkat lanjut (*Optimistic Locking* via `@Version` vs *Pessimistic Locking* dengan klausa `SKIP LOCKED`).
- **Mengimplementasikan** pola *Multi-Tenancy* terisolasi (*Database-per-tenant* dan *Schema-per-tenant*) menggunakan `CurrentTenantIdentifierResolver` dan `MultiTenantConnectionProvider`.
- **Melakukan Profiling, Tuning, dan Debugging** koneksi pool *HikariCP* pada skala enterprise, memitigasi *Connection Leak*, serta mengoptimalkan *Statement Caching* untuk memangkas p99 *latency* sistem hingga di bawah 15ms.

---

## 2. Prerequisites
Sebelum mempelajari materi ini, peserta wajib menguasai:
- **Core Spring & JPA**: Lifecycle Spring Beans, ApplicationContext, dasar ORM Hibernate (Entity, Lifecycle states: Transient, Managed, Detached, Removed).
- **Relational Database Internals**: ACID semantics, MVCC (Multi-Version Concurrency Control), Transaction Isolation Levels (`READ_COMMITTED`, `REPEATABLE_READ`, `SERIALIZABLE`), serta indeks B-Tree.
- **Java Platform**: Java 21 LTS (Records, Pattern Matching, Virtual Threads concurrency implications), ThreadLocal memory models.
- **Software Stack**: JDK 21, Spring Boot 3.3+, Docker Engine (PostgreSQL 16), Maven 3.9+.

---

## 3. Concept & Internal Architecture

### 3.1 Hibernate 6.x Engine & Persistence Context Lifecycle
Pada Hibernate 6.x (fondasi JPA di Spring Boot 3.x), mesin translasi HQL/JPQL dirombak total menggunakan **Semantic Query Model (SQM)**. Berbeda dengan parser Antlr v2 pada Hibernate 5, SQM memparsing kueri langsung menjadi *Abstract Syntax Tree* (AST) berbasis tipe data, yang kemudian dikompilasi ke SQL native melalui arsitektur *SQL AST Tree*.

```
[JPQL / Criteria API]
        │
        ▼
┌─────────────────────────┐
│ SQM (Semantic Query Model)│ ── Validasi semantic, type-check
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│       SQL AST Tree      │ ── Optimasi tree, dialect translation
└─────────────────────────┘
        │
        ▼
   [Native SQL]
```

Dalam sebuah transaksi JPA, entitas berada di dalam `PersistenceContext` (Level 1 Cache). L1 Cache bertindak sebagai *transactional write-behind buffer* dan *identity map*:
1. **Identity Map**: Menjamin bahwa dalam satu *session*, dua pembacaan baris data yang sama akan selalu menghasilkan referensi objek Java yang identik (`o1 == o2`).
2. **Write-Behind (Deferred Execution)**: Mutasi entitas (`setBalance()`, `persist()`, `merge()`) tidak serta-merta mengeksekusi SQL ke database. Perubahan dicatat sebagai entri *EntityEntry* dan *Status* dalam *StatefulPersistenceContext*.
3. **ActionQueue**: Menyimpan aksi database (`EntityInsertAction`, `EntityUpdateAction`, `EntityDeleteAction`). Urutan eksekusi saat `flush()`:
   - `OrphanRemovalAction`
   - `EntityInsertAction` / `EntityIdentityInsertAction`
   - `EntityUpdateAction`
   - `QueuedOperationCollectionAction`
   - `CollectionRemoveAction`
   - `CollectionUpdateAction`
   - `CollectionRecreateAction`
   - `EntityDeleteAction`

### 3.2 Dynamic Read/Write Splitting Menggunakan AbstractRoutingDataSource
Pada sistem high-throughput, mendistribusikan kueri *Read* ke beberapa database *Read-Replica* dan membatasi kueri *Write* ke *Primary Master* adalah hal esensial.

Spring menyediakan abstraksi `org.springframework.jdbc.datasource.lookup.AbstractRoutingDataSource`. Mekanisme internalnya bergantung pada `determineCurrentLookupKey()`, yang dievaluasi **tepat sebelum** Hibernate meminjam koneksi fisik dari pool:

```
[Application Request]
         │
         ▼
┌─────────────────────────────────┐
│  @Transactional(readOnly = ?)  │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ TransactionSynchronizationManager│
│ isCurrentTransactionReadOnly()  │
└─────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│ RoutingDataSource.determineCurrentLookupKey()│
└──────────────────────────────────────────────┘
     │                                  │
     │ Key = "WRITE"                    │ Key = "READ"
     ▼                                  ▼
┌─────────────────┐             ┌─────────────────┐
│  Primary Pool   │             │  Replica Pool   │
│  (HikariCP-W)   │             │  (HikariCP-R)   │
└─────────────────┘             └─────────────────┘
```

> **Perhatian Arsitektur**: Spring JPA mengikat koneksi database ke thread pada saat transaksi dimulai (`TransactionInterceptor`). Jika Anda menggunakan *Lazy Loading* di luar transaksi atau menggunakan konfigurasi *Open Session In View* (OSIV), rute datasource bisa terperangkap pada koneksi yang salah atau bocor ke pool lain.

### 3.3 HikariCP: Fast-Path Connection Borrowing & Concurrency Engine
HikariCP mencapai microsecond-level overhead dibanding pool lama (DBCP, C3P0) berkat:
1. **Bytecode Engineering**: Mengeliminasi delegasi wrapper melalui perakitan bytecode via Javassist.
2. **FastList**: Pengganti `ArrayList` tanpa pengecekan batasan indeks secara redundan dan traversal pencarian elemen secara mundur (*tail-to-head*), yang optimal untuk siklus penutupan `Statement`.
3. **ConcurrentBag**: Struktur data *lock-free* internal yang menggunakan ThreadLocal caching untuk meminjam koneksi tanpa *contention lock* global. Jika thread saat ini sebelumnya memegang koneksi tertentu dan koneksi tersebut `STATE_NOT_IN_USE`, koneksi tersebut langsung diambil kembali melalui operasi CAS (*Compare-And-Swap*).

---

## 4. Why & What

| Pendekatan / Fitur | Mengapa Dibutuhkan (Why) | Apa Karakteristiknya (What) | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Dynamic Routing DataSource** | Menghilangkan bottleneck I/O pada single master instance di arsitektur read-heavy. | Mengarahkan `Connection` secara cerdas ke pool Master atau Slave berdasarkan flag transaksi. | Rasio *Read-to-Write* database $\ge 70:30$. |
| **Hibernate JDBC Batching** | Mengurangi RTT (*Round Trip Time*) jaringan antar application server dan DB server dari $N$ trip menjadi $\lceil N / batch\_size \rceil$. | Mengirim kumpulan perintah SQL (`PreparedStatement.addBatch()`) secara atomik dalam satu blok jaringan. | Import data, sinkronisasi bulk event, update status masal. |
| **Pessimistic Write (SKIP LOCKED)** | Mencegah anomali double-processing pada distributed job/worker queue tanpa terkunci menunggu row. | Mengunci row yang belum diakuisisi worker lain; jika terkunci, baris tersebut langsung dilewati (*non-blocking skip*). | Antrean task internal database, penarikan tiket/voucher berurutan. |
| **Optimistic Locking (@Version)** | Mencegah *lost updates* tanpa menahan exclusive database row lock yang membebani concurrency. | Memvalidasi kolom version pada klausa `WHERE id = ? AND version = ?`. Jika termodifikasi, lempar exception. | Transaksi finansial standar, pembaruan master data, sistem inventori umum. |

---

## 5. How: Workflow Detail

### Workflow 1: Read/Write Split Routing Execution Flow
1. **Invokasi Service**: Client mengeksekusi metode `@Transactional(readOnly = true)`.
2. **Transaction Interception**: `TransactionInterceptor` Spring memproses metadata transaksi dan mendaftarkannya ke `TransactionSynchronizationManager`.
3. **Resource Binding**: Hibernate membutuhkan koneksi dari `DataSource`.
4. **Lookup Routing**: `RoutingDataSource.determineCurrentLookupKey()` dieksekusi. Ia memeriksa `TransactionSynchronizationManager.isCurrentTransactionReadOnly()`.
5. **Connection Acquisition**:
   - Jika `true`, ambil referensi koneksi dari `ReplicaHikariPool`.
   - Jika `false`, ambil referensi koneksi dari `PrimaryHikariPool`.
6. **Execution & Release**: Query dieksekusi, data dikembalikan, transaksi ditutup, dan koneksi dikembalikan ke pool masing-masing.

### Workflow 2: Safe High-Volume Batching Pipeline
1. Nonaktifkan pembuatan ID bertipe `GenerationType.IDENTITY` karena Hibernate harus mengeksekusi `INSERT` langsung demi mendapatkan autoincrement ID, yang secara permanen **menonaktifkan** batching.
2. Gunakan `GenerationType.SEQUENCE` dengan allocation size yang terkalibrasi atau gunakan algoritma *TSID / UUID v7*.
3. Urutkan *insert* dan *update* via konfigurasi Hibernate: `hibernate.order_inserts=true` dan `hibernate.order_updates=true` untuk mencegah fragmentasi batching buffer.
4. Lakukan `entityManager.flush()` dan `entityManager.clear()` secara periodik setiap kelipatan $batch\_size$ guna mencegah heap bloat dan OOM (*Out Of Memory*).

---

## 6. Analogy & Diagram ASCII

### Analogi: Sistem Pos dan Pengantaran Logistik
Bayangkan sebuah kantor ekspedisi pos terpadu:
- **Persistence Context (L1 Cache)**: Meja kerja kurir. Ketika paket tiba untuk diubah alamatnya, kurir tidak langsung lari ke gudang pusat. Kurir menumpuk paket-paket tersebut di mejanya, mencatat semua koreksi pada lembar manifest sementara (*Identity Map & Write-Behind*).
- **ActionQueue & Batching**: Alih-alih mengantar satu surat ke truk pengangkut setiap 30 detik (*no batching*), kurir menunggu sampai kotak surat penuh berisi 50 surat (*batch_size=50*), lalu mengangkutnya sekaligus menggunakan troli ke truk ekspedisi (*PreparedStatement.executeBatch()*).
- **Read/Write Splitting**: Loket pembayaran/penerimaan barang baru hanya ada di Gedung Master (*Primary/Write*). Namun, untuk menanyakan status resi atau mengecek lokasi barang, pelanggan dialihkan ke 3 gedung satelit di seberang jalan (*Replica/Read*).

### Sequence Diagram: Dynamic Routing DataSource Interception

```
[ Thread ]      [ Spring TX Mgr ]    [ RoutingDataSource ]   [ Primary Pool ]   [ Replica Pool ]   [ Target DB ]
    │                   │                      │                     │                  │                │
    ├─ executeMethod() ─►                      │                     │                  │                │
    │  (@Transactional) │                      │                     │                  │                │
    │                   ├─ initContext() ──────┼─────────────────────┼──────────────────┼────────────────┤
    │                   │  (readOnly=true)     │                     │                  │                │
    │                   │                      │                     │                  │                │
    │  JPA Repository ──┼──────────────────────► getConnection()     │                  │                │
    │  Query Execution  │                      ├─ determineKey()     │                  │                │
    │                   │                      │  Key: READ_REPLICA  │                  │                │
    │                   │                      │                     │                  │                │
    │                   │                      ├─ borrowConnection()─┼──────────────────►                │
    │                   │                      │                     │                  ├─ Connection ───►
    │                   │                      │                     │                  │  Established   │
    │                   │                      ◄─ return Connection ─┼──────────────────┴────────────────┤
    │                   │                      │                     │                  │                │
    │◄─ Return Data ────┴──────────────────────┴─────────────────────┴──────────────────┴────────────────┤
```

---

## 7. Code Implementation: Standard Production

Struktur paket untuk implementasi:
```
com.enterprise.persistence/
├── config/
│   ├── DataSourceConfiguration.java
│   ├── RoutingDataSource.java
│   └── RoutingDataSourceContext.java
├── domain/
│   ├── model/
│   │   ├── Account.java
│   │   └── LedgerEntry.java
│   └── repository/
│       ├── AccountRepository.java
│       └── LedgerEntryRepository.java
└── service/
    └── FinancialLedgerService.java
```

### 7.1 Dynamic Master-Replica Infrastructure Configuration

```java
package com.enterprise.persistence.config;

public final class RoutingDataSourceContext {
    private static final ThreadLocal<DataSourceType> CONTEXT = new ThreadLocal<>();

    private RoutingDataSourceContext() {}

    public enum DataSourceType {
        PRIMARY,
        REPLICA
    }

    public static void set(DataSourceType dataSourceType) {
        CONTEXT.set(dataSourceType);
    }

    public static DataSourceType get() {
        return CONTEXT.get();
    }

    public static void clear() {
        CONTEXT.remove();
    }
}
```

```java
package com.enterprise.persistence.config;

import org.springframework.jdbc.datasource.lookup.AbstractRoutingDataSource;
import org.springframework.transaction.support.Transaction