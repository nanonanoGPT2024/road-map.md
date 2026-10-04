# BAB 05: Quiz, Challenge, & Knowledge Check
**Data Persistence, ORM & Database Performance Tuning**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Siklus Hidup Koneksi Database Fisik vs Connection Pooling
Jelaskan secara mendalam alur komputasi dan overhead *network I/O* pada sistem operasi (OS) saat aplikasi mengeksekusi kueri menggunakan `DriverManager.getConnection()` murni tanpa pooling, dibandingkan dengan penggunaan connection pooler berperforma tinggi seperti HikariCP. Apa saja trade-off alokasi resource OS (TCP 3-way handshake, TLS negotiation, thread allocation) yang dieliminasi oleh pooling?

### Soal 1.2: State Transitions & Persistence Context pada JPA
Jelaskan empat state dari sebuah entity dalam JPA specification (`Transient`, `Managed`, `Detached`, `Removed`). Uraikan bagaimana Hibernate mengelola entity tersebut di dalam *First-Level Cache* (L1 Cache), kapan tepatnya *dirty checking mechanism* dipicu, serta jelaskan perbedaan mendasar antara invokasi `EntityManager.flush()` dan `TransactionManager.commit()`.

### Soal 1.3: Anatomi Teknis $N+1$ Query Problem
Mengapa deklarasi relasi `FetchType.LAZY` pada `@OneToMany` atau `@ManyToOne` tidak serta-merta mengeliminasi masalah $N+1$ query, dan dalam skenario apa fetch type tersebut justru menjadi bumerang performa? Bandingkan kelebihan dan kekurangan dari tiga strategi mitigasi berikut: `JOIN FETCH` (JPQL), JPA Entity Graph (`@EntityGraph`), dan batch fetching via `@BatchSize`.

### Soal 1.4: Isolasi Transaksi dan Fenomena Konkurensi Database
Uraikan pemetaan level isolasi transaksi ANSI SQL (`READ UNCOMMITTED`, `READ COMMITTED`, `REPEATABLE READ`, `SERIALIZABLE`) terhadap fenomena anomali baca: *Dirty Read*, *Non-Repeatable Read*, dan *Phantom Read*. Bagaimana mekanisme implementasi underlying engine (seperti MVCC pada PostgreSQL/MySQL InnoDB) membedakan perlakuan terhadap anomali-anomali tersebut tanpa memblokir pembacaan data secara menyeluruh?

### Soal 1.5: Indeks Database B-Tree & Leftmost Prefix Rule
Diberikan sebuah composite index pada tabel relational: `CREATE INDEX idx_user_trx ON transactions (tenant_id, status, created_at);`. Jelaskan mengapa query dengan filter `WHERE status = 'SUCCESS' AND created_at >= '2024-01-01'` gagal memanfaatkan indeks secara optimal. Bagaimana struktur B-Tree memvalidasi *leftmost prefix rule*, dan bagaimana peran *Index Skip Scan* atau *Composite Index Ordering* dalam optimasi kasus tersebut?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Hibernate Second-Level (L2) Cache Invalidation & Direct SQL Desynchronization
Ketika mengintegrasikan distributed L2 cache (seperti Redis atau Hazelcast) dengan Hibernate:
1. Bagaimana Hibernate mengelola konsistensi data antara L1, L2, dan tabel fisik database saat terjadi write operations?
2. Apa yang terjadi jika sebuah background worker memperbarui baris data langsung melalui JDBC Native Query atau Spring Data `@Modifying @Query` bypass entity lifecycle? Mengapa hal ini menimbulkan stale data pada L2 cache dan bagaimana arsitektur penanganannya?

### Soal 2.2: Root Cause Analysis: HikariCP Connection Starvation & Thread Exhaustion
Sebuah microservice berbasis Spring Boot melaporkan lonjakan drastis pada metrik latency p99 dari 20ms menjadi 30.000ms. CPU utilization hanya 12%, namun thread dump menunjukkan ratusan thread berada pada state `WAITING (parking)` di baris `com.zaxxer.hikari.pool.HikariPool.getConnection()`. 
1. Rumuskan langkah sistematis untuk mendiagnosis apakah insiden ini disebabkan oleh *Connection Leak*, ukuran pool (`maximumPoolSize`) yang *under-provisioned*, atau transaksi yang mengalami *I/O block* (misalnya memanggil REST API pihak ketiga di dalam blok `@Transactional`).
2. Bagaimana formula matematis Brian Goetz / HikariCP Team dalam menentukan pool size optimal berdasarkan kapasitas CPU core dan disk I/O?

### Soal 2.3: Concurrency Control Under Extreme Write Load: Optimistic vs Pessimistic Locking
Pada sistem flash-sale dengan 5.000 concurrent update per detik pada satu baris data inventaris:
1. Mengapa penggunaan *Optimistic Locking* (`@Version`) justru memicu fenomena *Cascading Rollback*, pemborosan CPU, dan kegagalan transaksi massal (*starvation*)?
2. Sebaliknya, bagaimana *Pessimistic Locking* (`PESSIMISTIC_WRITE` / `SELECT ... FOR UPDATE`) memengaruhi antrean lock pada level database engine? Kapan query tersebut berisiko memicu *Deadlock (OS Error 1213 / SQLState 40P01)* dan bagaimana strategi mitigasinya?

### Soal 2.4: Bottleneck Deep Pagination pada Skala Puluhan Juta Baris
Analisis query berikut pada tabel dengan 50.000.000 data:
```sql
SELECT * FROM audit_logs WHERE tenant_id = 'c4ca4238' ORDER BY created_at DESC LIMIT 50 OFFSET 1000000;
```
1. Jelaskan mengapa performa query menurun secara linear seiring bertambahnya nilai `OFFSET`, ditinjau dari cara storage engine membaca leaf node B-Tree dan data pages ke dalam buffer pool.
2. Rancang ulang query tersebut menggunakan teknik **Keyset Pagination (Seek Method)** dan **Deferred Join**, lalu buktikan bagaimana teknik ini mempertahankan konstanta waktu eksekusi $O(\log N)$ atau stabil pada latensi rendah.

### Soal 2.5: Replikasi Asinkron Database & Read-After-Write Consistency
Pada topologi Master-Replica (Read-Write Splitting) menggunakan framework routing datasource (seperti `AbstractRoutingDataSource`):
1. Masalah apa yang timbul ketika seorang pengguna membuat transaksi perbankan baru (diarahkan ke Master), lalu langsung diarahkan ke halaman detail transaksi (diarahkan ke Replica) sebelum replikasi binlog/WAL selesai diproses (*Replication Lag*)?
2. Bagaimana pola arsitektural di layer Java application untuk menjamin *Read-After-Write Consistency* tanpa menghilangkan keuntungan skalabilitas dari Read-Replica?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Produksi – Memory Leak & GC Pause Akibat Batch Ingestion
Sebuah service ingestion data finansial memproses file CSV berisi 2.000.000 mutasi transaksi setiap malam. Proses dieksekusi menggunakan Spring Batch dan Hibernate JPA standard repository:
```java
@Transactional
public void processBatch(List<TransactionDTO> dtos) {
    for (TransactionDTO dto : dtos) {
        Transaction tx = mapper.toEntity(dto);
        transactionRepository.save(tx);
    }
}
```
**Gejala:** Setelah memproses sekitar 150.000 baris, heap memory JVM melonjak hingga 98%, memicu *Stop-the-World (STW) Garbage Collection Pause* selama 45 detik, dan akhirnya service crash dengan error: `java.lang.OutOfMemoryError: Java heap space`.

**Pertanyaan Diagnostik:**
1. Mengapa pemanggilan `transactionRepository.save()` di dalam satu konteks `@Transactional` besar menyebabkan akumulasi objek tak tertangani di memory, meskipun DTO diproses secara iterative?
2. Rancang arsitektur refactoring menyeluruh yang mencakup:
   - Pengaturan Hibernate Session / Persistence Context management (`clear()` dan `flush()`).
   - Konfigurasi parameter JDBC Batch Size (`spring.jpa.properties.hibernate.jdbc.batch_size` dan order inserts/updates).
   - Penggunaan Native JDBC `PreparedStatement.executeBatch()` atau Hibernate `StatelessSession` sebagai alternatif ORM overhead.

---

### Skenario B: Kasus Integritas Data – Lost Updates & Deadlock pada Akun Multi-Threaded
Aplikasi dompet digital (e-wallet) melayani transfer saldo antar-pengguna secara simultan. Terjadi dua request bersamaan:
- **Transaksi 1:** User A mentransfer Rp 500.000 ke User B.
- **Transaksi 2:** User B mentransfer Rp 200.000 ke User A.

Kode transaksi dituliskan sebagai berikut:
```java
@Transactional(isolation = Isolation.READ_COMMITTED)
public void transferBalance(UUID fromUserId, UUID toUserId, BigDecimal amount) {
    UserAccount from = accountRepository.findById(fromUserId).orElseThrow();
    UserAccount to = accountRepository.findById(toUserId).orElseThrow();
    
    from.debit(amount);
    to.credit(amount);
    
    accountRepository.save(from);
    accountRepository.save(to);
}
```
**Gejala:** Pada jam sibuk, sistem mendeteksi lonjakan exception `CannotAcquireLockException` / `DeadlockLoserDataAccessException`. Lebih buruk lagi, terjadi kasus anomali di mana saldo total dari User A dan User B berkurang secara misterius (*lost update* / inkonsistensi saldo agregat).

**Pertanyaan Diagnostik:**
1. Gambarkan secara presisi urutan eksekusi (*interleaving execution timeline*) yang memicu terjadinya circular wait (deadlock) pada transaksi di atas.
2. Mengapa level isolasi `READ_COMMITTED` tidak mampu mencegah *Lost Update* pada pembacaan saldo awal?
3. Rancang perbaikan sistem ini menggunakan pendekatan **Deterministic Lock Acquisition Ordering** dan **Pessimistic Row-Level Locking**, lengkap dengan kode penanganannya untuk mencegah deadlock dan race condition.

---

### Skenario C: Keputusan Arsitektur – Multi-Tenancy Architecture Trade-Offs
Anda adalah Principal Architect pada perusahaan SaaS B2B Enterprise yang sedang membangun sistem ERP core. Sistem ini akan melayani:
- 1.000 Tenant tier UMKM (throughput rendah, budget minim).
- 5 Tenant Tier Fortune-500 (throughput sangat tinggi, compliance audit ISO/SOC2 super ketat, mensyaratkan isolasi data mutlak).

Tim engineering sedang memperdebatkan tiga model arsitektur data persistence:
1. **Database-per-Tenant** (Isolasi fisik database penuh).
2. **Schema-per-Tenant** (Satu instance database, schema terpisah).
3. **Shared Database, Shared Schema / Discriminator Column** (Satu database, satu schema, tabel dibedakan via `tenant_id`).

**Pertanyaan Evaluasi Teknis:**
1. Bedah trade-off performa, kompleksitas connection pool (HikariCP resource exhaustion), database migration maintenance (Flyway/Liquibase), dan risiko kebocoran data (*cross-tenant data leakage*) dari ketiga pendekatan tersebut.
2. Rancang strategi **Hybrid Multi-Tenancy Architecture** yang menjembatani kebutuhan enterprise vs tier UMKM dalam satu codebase Spring Boot / JPA! Bagaimana cara implementasi dinamis routing databasenya (`MultiTenantConnectionProvider` & `CurrentTenantIdentifierResolver`)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Financial Ledger Ingestion Engine

#### Deskripsi Masalah
Anda diminta membangun komponen core dari sistem *Ledger Account Service*. Modul ini harus mampu memproses jutaan jurnal mutasi finansial (double-entry bookkeeping: debit & credit) secara massal dengan konsistensi data absolut (ACID), zero data loss, sub-millisecond database insertion throughput, dan bebas dari masalah $N+1$ serta memory leak.

#### Requirements
1. **Double-Entry Consistency Constraint:**
   Setiap transaksi finansial wajib memiliki minimal dua mutasi (1 debit, 1 credit) yang nilai agregat balance-nya bernilai nol ($\sum Debit - \sum Credit = 0$). Kegagalan satu baris mutasi harus membatalkan seluruh transaksi secara atomic.
2. **High-Performance Ingestion:**
   Sistem harus mampu menyerap dan menyimpan minimal **10.000 mutasi/detik** ke dalam database PostgreSQL menggunakan optimasi JDBC Batching via Spring Data JPA / Hibernate, dengan parameter konfigurasi pool HikariCP yang tertata terukur.
3. **Audit Balance Report with Keyset Pagination:**
   Implementasikan REST API untuk membaca riwayat mutasi rekening per pengguna. API tidak boleh menggunakan `PageRequest.of(page, size)` standar yang berbasis `OFFSET`. Wajib mengimplementasikan **Keyset Pagination (Seek Method)** berdasarkan `(created_at, transaction_id)` tuple.
4. **Resilient Concurrency:**
   Implementasikan penarikan saldo/pembaruan rekening dengan proteksi terhadap race condition menggunakan deterministic lock sorting atau pessimistic lock dengan timeout terukur (mencegah thread hanging).
5. **Execution Plan Telemetry:**
   Kueri audit balance wajib memiliki indeks yang tepat, dibuktikan dengan keluaran `EXPLAIN (ANALYZE, BUFFERS)` yang membuktikan *Index Scan* (bukan *Seq Scan*) dan zero temporary disk spills.

#### Constraints
- Framework: Java 17/21, Spring Boot 3.x, Spring Data JPA / Hibernate 6.x.
- Database: PostgreSQL 15+.
- Memory restriction: JVM Max Heap `-Xmx512m` (Aplikasi tidak boleh mengalami OOM saat memproses 500.000 data dalam satu antrean batch).
- Koneksi database: HikariCP maksimal 20 koneksi.

#### Expected Output
1. File DDL PostgreSQL yang dilengkapi indexing optimal (Composite Indexes, Check Constraints untuk double-entry balance).
2. Kode Implementasi Entity JPA lengkap dengan relasinya, lifecycle hooks, dan optimasi fetch.
3. Service layer yang mengimplementasikan pemrosesan batch data menggunakan JDBC batching / chunking execution yang bersih dari First-Level cache saturation (`em.clear()` / stateless).
4. Repository layer dengan implementasi Keyset Pagination native query atau Criteria API.
5. Laporan hasil `EXPLAIN ANALYZE` beserta benchmark ringkas (bisa berupa test harness via JUnit + Testcontainers) yang membuktikan throughput target tercapai di bawah limitasi memory 512MB.

---

## 5. Knowledge Check & Checklist

Tinjau penguasaan materi Anda sebelum melangkah ke bab berikutnya. Tandai checkbox yang relevan.

### Saya harus memahami:
- [ ] Perbedaan mendalam siklus hidup koneksi via OS Socket vs Connection Pooler (HikariCP state machine).
- [ ] Empat JPA entity state (`Transient`, `Managed`, `Detached`, `Removed`) dan implikasinya pada First-Level Cache.
- [ ] Mekanisme internal Hibernate Dirty Checking dan algoritma snapshot verification saat `flush()`.
- [ ] Penyebab utama $N+1$ query problem serta limitasi `JOIN FETCH` terhadap multiple `BagFetchException`.
- [ ] Perilaku ANSI SQL Transaction Isolation Levels dan representasi fisiknya pada engine MVCC (PostgreSQL/InnoDB).
- [ ] Cara membaca dan membedah output `EXPLAIN ANALYZE` database engine (*Seq Scan, Index Scan, Index Only Scan, Bitmap Heap Scan, Hash Join, Nested Loop*).
- [ ] Anatomi B-Tree index: composite indexing, column selectivity, B-Tree leaf fragmentation, dan *Leftmost Prefix Rule*.
- [ ] Bahaya performa Deep Pagination via `LIMIT ... OFFSET` dan keunggulan matematis Keyset Pagination.
- [ ] Risiko data desynchronization pada Hibernate L2 Cache akibat Native SQL Query bypass.
- [ ] Arsitektur Read-Write replica, replikasi lag, serta teknik routing penanganannya di level aplikasi.

### Saya tidak perlu menghafal:
- [ ] Seluruh puluhan parameter konfigurasi internal Hibernate/HikariCP secara verbatim (cukup memahami parameter vital seperti `maximumPoolSize`, `connectionTimeout`, `leakDetectionThreshold`, `batch_size`).
- [ ] Sintaks khusus ekstensi SQL vendor-spesifik kuno (cukup kuasai ANSI SQL dan Postgres/MySQL modern dialect).
- [ ] Binary format protokol komunikasi jaringan JDBC (cukup pahami alur abstraksi Socket I/O dan pooling).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengeliminasi $N+1$ query problem menggunakan Query Plan Profiler, `@EntityGraph`, atau JPQL `JOIN FETCH`.
- [ ] Mengonfigurasi dan melakukan tuning koneksi HikariCP berdasarkan beban workload (IO-bound vs CPU-bound) dan rumus sizing standar industri.
- [ ] Menulis kueri pagination performa tinggi menggunakan Keyset Pagination (Cursor/Seek Method) untuk data bervolume jutaan baris.
- [ ] Mengimplementasikan *Pessimistic Locking* dan *Optimistic Locking* dengan error-handling terstruktur untuk skenario konkurensi tinggi.
- [ ] Melakukan profiling dan debugging bottleneck alokasi memory JVM akibat akumulasi L1 Cache pada pemrosesan batch berukuran masif.
- [ ] Menggunakan `EXPLAIN (ANALYZE, BUFFERS)` untuk menemukan indeks yang hilang atau penggunaan resource disk/memory berlebih pada query production.
- [ ] Mengimplementasikan dynamic database routing (Master-Replica split atau Multi-tenancy architecture) pada Spring Boot ecosystem.