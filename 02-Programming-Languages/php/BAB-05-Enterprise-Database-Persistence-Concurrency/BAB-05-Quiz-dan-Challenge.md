# BAB 05: Quiz, Challenge, & Knowledge Check
**Enterprise Database Persistence & Concurrency**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Life-Cycle State Mesin ORM dan Identity Map Pattern
Jelaskan siklus hidup entitas (*Entity Life-cycle*) dalam implementasi *Data Mapper* (seperti Doctrine ORM): *New/Transient*, *Managed/Persistent*, *Detached*, dan *Removed*. Bagaimana mekanisme internal *Identity Map* mencegah instansiasi objek ganda untuk satu baris data (*row*) yang sama dalam satu request PHP-FPM, dan apa dampaknya terhadap konsumsi memori saat memproses *batch processing* jutaan baris data jika *Unit of Work* tidak di-clear secara berkala?

### Soal 1.2: Anatomi ANSI SQL Isolation Levels vs Database Anomalies
Uraikan matriks anomali konkurensi database (*Dirty Read*, *Non-Repeatable Read*, *Phantom Read*, dan *Serialization Anomaly / Write Skew*) terhadap 4 tingkat isolasi standar ANSI SQL:
1. `READ UNCOMMITTED`
2. `READ COMMITTED`
3. `REPEATABLE READ`
4. `SERIALIZABLE`

Jelaskan mengapa implementasi `REPEATABLE READ` pada MySQL (InnoDB via MVCC + Next-Key Locking) memiliki karakteristik penanganan anomali yang berbeda secara mendasar dibandingkan PostgreSQL (MVCC Snapshot Isolation tanpa lock gap)?

### Soal 1.3: Emulated vs Native Prepared Statements pada Driver PDO
Jelaskan perbedaan arsitektural antara native prepared statement dan emulated prepared statement (`PDO::ATTR_EMULATE_PREPARES => true` vs `false`) pada ekstensi PDO PHP. Analisis dari sudut pandang:
- *Round-trip network overhead* antara aplikasi PHP dan database engine.
- Kerentanan keamanan terhadap eksploitasi SQL Injection (khususnya *character-encoding bypass* seperti GBK/Big5 atau *second-order SQLi*).
- Kemampuan driver dalam melakukan *type hinting* / *type casting* native data types (integer, boolean, float) langsung dari layer C database client.

### Soal 1.4: Pessimistic vs Optimistic Locking Trade-Offs
Bandingkan mekanisme *Pessimistic Locking* (`SELECT ... FOR UPDATE` dan `SELECT ... LOCK IN SHARE MODE`) dengan *Optimistic Locking* (berbasis kolom `@Version` integer atau timestamp):
- Bagaimana *lock acquisition* dan *lock contention* bekerja di tingkat database engine pada masing-masing pendekatan?
- Kapan Anda harus memilih Pessimistic Locking dibanding Optimistic Locking pada sistem transaksi finansial dengan konkurensi ekstrim? Uraikan metrik performa (*throughput*, *latency*, *rollback rate*) yang memvalidasi keputusan tersebut.

### Soal 1.5: Shared-Nothing Architecture PHP vs Persistence Connection
Arsitektur PHP berbasis *Shared-Nothing* mendikte bahwa seluruh *state* memori musnah saat siklus request berakhir (*request termination*). Berdasarkan premis tersebut:
- Mengapa penggunaan persistent connection (`PDO::ATTR_PERSISTENT => true`) di lingkungan PHP-FPM modern sering kali dianggap sebagai *anti-pattern* yang memicu kegagalan sistem katastropik?
- Masalah apa yang timbul terkait *uncommitted transactions*, variabel sesi database (`SET time_zone`, `SET NAMES`), dan alokasi batas koneksi database engine (*connection starvation*)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Deadlock Graph Analysis & Resilient Retry Mechanism
Perhatikan representasi visual dari kutipan Deadlock Engine Log (InnoDB) berikut:

```text
*** (1) TRANSACTION:
TRANSACTION 283941, ACTIVE 0 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 2 lock struct(s), heap size 1136, 1 row lock(s)
MySQL thread id 42, OS thread handle 1407, query id 8901 updating
UPDATE accounts SET balance = balance - 100 WHERE id = 10
*** (2) TRANSACTION:
TRANSACTION 283942, ACTIVE 0 sec starting index read
mysql tables in use 1, locked 1
2 lock struct(s), heap size 1136, 1 row lock(s)
MySQL thread id 43, OS thread handle 1408, query id 8902 updating
UPDATE accounts SET balance = balance + 100 WHERE id = 20
*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 58 page no 3 n bits 72 index PRIMARY of table accounts trx id 283941 lock_mode X locks rec but not gap waiting
Record lock, heap no 2 PHYSICAL RECORD: n_fields 4; ... id=20
*** (2) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 58 page no 3 n bits 72 index PRIMARY of table accounts trx id 283942 lock_mode X locks rec but not gap waiting
Record lock, heap no 3 PHYSICAL RECORD: n_fields 4; ... id=10
*** WE ROLL BACK TRANSACTION (1)
```

1. Jelaskan urutan eksekusi (*interleaving execution order*) yang menyebabkan siklus saling kunci (*deadly embrace*) di atas.
2. Rancang struktur arsitektur *Deadlock Retry Handler* di PHP 8.x yang mengimplementasikan *Exponential Backoff* dengan *Full Jitter Algorithm*. Jelaskan mengapa penambahan komponen *random jitter* wajib dilakukan untuk mencegah fenomena *Thundering Herd* pada koneksi database worker!

### Soal 2.2: Transaction Boundary Leaking pada Nested Database Transactions
PHP frameworks kerap memfasilitasi abstraksi "Nested Transaction" menggunakan `DB::beginTransaction()` berulang kali, yang diimplementasikan di balik layar menggunakan Database `SAVEPOINT`.
- Uraikan bagaimana perilaku transaksi database jika terjadi *unhandled exception* pada *Savepoint 2* di dalam *Savepoint 1*, lalu aplikasi menangkap (*catch*) exception tersebut tanpa melakukan *re-throw* atau *rollback to savepoint* secara eksplisit.
- Bagaimana kondisi koneksi database saat dikembalikan ke connection pool jika terjadi *Transaction Leaking* (transaksi terbuka yang tidak di-commit maupun di-rollback secara tuntas)?

### Soal 2.3: Connection Pooling Middleware Internals (PgBouncer / ProxySQL)
Karena runtime PHP tidak memiliki *built-in multithreaded connection pool*, arsitektur enterprise menggunakan middleware proxy layer seperti PgBouncer atau ProxySQL.
- Jelaskan perbedaan 3 mode pooling pada PgBouncer: *Session Pooling*, *Transaction Pooling*, dan *Statement Pooling*.
- Analisis mengapa fitur-fitur native berikut akan rusak (*broken/corrupted state*) jika Anda menggunakan mode **Transaction Pooling**:
  1. Prepared Statements non-emulated (`PREPARE` / `EXECUTE`).
  2. Temporary Tables (`CREATE TEMPORARY TABLE`).
  3. Session-level locking (`pg_advisory_lock` atau `GET_LOCK`).

### Soal 2.4: Write Skew Anomaly Diagnostic pada Snapshot Isolation
Dua dokter (Dokter A dan Dokter B) terdaftar sebagai dokter jaga (*on-call*). Aturan bisnis menegaskan: **"Minimal harus ada satu dokter yang bertugas menjaga rumah sakit setiap saat."**
Kedua dokter mencoba mengajukan izin cuti sakit secara bersamaan pada waktu yang persis sama. 

Database menggunakan Isolation Level `REPEATABLE READ` (PostgreSQL Snapshot Isolation).

```sql
-- Transaksi 1 (Dokter A)
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT COUNT(*) FROM doctors WHERE on_call = true; -- Return: 2
UPDATE doctors SET on_call = false WHERE id = 'A';
COMMIT;

-- Transaksi 2 (Dokter B)
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT COUNT(*) FROM doctors WHERE on_call = true; -- Return: 2
UPDATE doctors SET on_call = false WHERE id = 'B';
COMMIT;
```

- Jelaskan secara mekanistik internal MVCC mengapa kedua transaksi di atas berhasil di-`COMMIT` tanpa memicu serialization failure, yang berakhir pada pelanggaran aturan bisnis (jumlah dokter jaga = 0).
- Bagaimana solusi deterministik di PHP/Database layer untuk memitigasi anomali ini tanpa mendegradasi seluruh transaksi aplikasi ke level `SERIALIZABLE` yang lambat?

### Soal 2.5: The Dual-Write Problem & Transactional Outbox Pattern
Pada arsitektur Microservices/Event-Driven menggunakan PHP, kebutuhan umum adalah menyimpan data ke MySQL/PostgreSQL dan secara bersamaan mempublikasikan event domain ke Apache Kafka / RabbitMQ.
- Analisis kegagalan struktural dari skenario berikut:
  ```php
  $db->beginTransaction();
  $orderRepository->save($order);
  $messageBroker->publish('OrderCreated', $order->toJson()); // Titik Kegagalan A
  $db->commit(); // Titik Kegagalan B
  ```
- Rancang implementasi **Transactional Outbox Pattern** berbasis PHP:
  1. Skema tabel outbox di database yang sama.
  2. Mekanisme change capture (Poller Worker vs Debezium CDC).
  3. Jaminan pengiriman (*Guaranteed Delivery*): Mengapa pola ini menjamin *At-Least-Once Delivery* dan bagaimana sistem penerima (*consumer*) harus dirancang dengan prinsip *Idempotency*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Flash-Sale Crash & Connection Exhaustion
**Kondisi Sistem:**
Sebuah platform E-Commerce berskala enterprise menjalankan 40 instance PHP-FPM workers di Kubernetes (setiap pod memiliki `pm.max_children = 50`, total kapasitas concurrent PHP worker: 2.000). Basis data menggunakan Single Primary RDS PostgreSQL berukuran `db.r6g.4xlarge` (maksimal konfigurasi `max_connections = 2000`).

Pada event Flash Sale (10.000 request/detik masuk ke gateway), sistem tiba-tiba mengalami *cascading failure*:
1. Latensi database melonjak dari 5ms menjadi 18.000ms.
2. Muncul error masif pada PHP-FPM: `SQLSTATE[08006] [7] FATAL: remaining connection slots are reserved for non-replication superuser connections`.
3. CPU RDS PostgreSQL menyentuh 100%, tetapi utilitas I/O disk (IOPS) sangat rendah.
4. Kubernetes mulai membunuh pod PHP-FPM karena *Liveness Probe* gagal merespons dalam batasan batas waktu (*timeout*).

```
[Clients] ---> [Ingress] ---> [40x PHP-FPM Pods (2000 Conns)] ---> [RDS PostgreSQL (max_conn: 2000)]
                                                                           ^
                                                               CPU 100% (Context Switching Collapse)
```

**Pertanyaan Diagnostik:**
1. Apa akar penyebab (*root cause*) teknis dari kegagalan server database tersebut? Mengapa mengalokasikan `max_connections` sebesar 2000 langsung ke database engine merupakan kesalahan fatal arsitektur, meskipun RAM mencukupi?
2. Bagaimana Anda merestrukturisasi *connection management layer* aplikasi PHP tersebut menggunakan PgBouncer? Tentukan parameter sizing: Berapa jumlah instance PgBouncer, mode pooling yang dipilih, serta rasio koneksi backend PostgreSQL pool yang ideal berdasarkan formula sizing thread CPU core database?
3. Langkah mitigasi apa yang wajib dikonfigurasi di level PHP (PDO timeout, connection retry, circuit breaker) agar PHP-FPM tidak mengalami blocking thread ketika database kehabisan kapasitas?

---

### Skenario B: Double-Spending Race Condition pada High-Frequency Ledger
**Kondisi Sistem:**
Sebuah aplikasi dompet digital (*Fintech*) memproses transaksi pengiriman saldo. Sistem memisahkan logika validasi saldo dan eksekusi transfer dana ke dalam dua lapisan service.

Ditemukan kasus fraud di mana user "Attacker" mengirimkan 10 request transfer dana sebesar Rp 100.000 secara serentak (konkuren dalam rentang milidetik yang sama) melalui skrip script-kiddie HTTP pipeline, padahal saldo awal Attacker hanya Rp 100.000. 

Hasil akhir pada database: Saldo Attacker menjadi **minus Rp 900.000**, dan 10 transaksi penarikan berhasil terkonfirmasi.

Berikut potongan kode PHP yang bermasalah:

```php
final class WalletService
{
    public function transfer(int $userId, int $recipientId, int $amount): void
    {
        $wallet = $this->walletRepo->findByUserId($userId); // Line 1
        
        if ($wallet->getBalance() < $amount) {              // Line 2
            throw new InsufficientBalanceException("Saldo tidak mencukupi");
        }
        
        $this->db->transaction(function () use ($wallet, $recipientId, $amount) {
            $wallet->deduct($amount);                       // Line 3: $balance -= $amount
            $this->walletRepo->save($wallet);               // Line 4: UPDATE wallets SET balance = :b WHERE id = :id
            
            $recipientWallet = $this->walletRepo->findByUserIdForUpdate($recipientId);
            $recipientWallet->add($amount);
            $this->walletRepo->save($recipientWallet);
            
            $this->auditLogRepo->createTransferLog($wallet->getId(), $recipientId, $amount);
        });
    }
}
```

**Pertanyaan Diagnostik:**
1. Bedah anomali konkurensi (*Time-of-Check to Time-of-Use / TOCTOU*) yang terjadi pada kode di atas. Mengapa penggunaan transaksi database pada *Line 3* sama sekali tidak melindungi sistem dari *race condition*?
2. Tuliskan refaktor menyeluruh potongan kode di atas menggunakan pendekatan:
   - **Solusi 1 (Database Pessimistic Locking):** Penguncian data secara eksplisit di level baris.
   - **Solusi 2 (Atomic Update Constraint):** Penghapusan pengecekan di level aplikasi dan mengandalkan *Database Engine Invariants* (`CHECK (balance >= 0)` atau `WHERE balance >= :amount`).
3. Bandingkan dampak performa (*throughput* dan *deadlock vulnerability*) antara Solusi 1 dan Solusi 2 jika sistem menerima 5.000 transaksi serentak pada akun pedagang (*merchant*) yang sama!

---

### Skenario C: The "Read-Your-Own-Writes" Replication Lag Crisis
**Kondisi Sistem:**
Sebuah platform media sosial enterprise menggunakan topologi PostgreSQL Database: 1 Primary Node (Read/Write) dan 4 Read Replica Nodes (Read-Only) yang dihubungkan melalui *Asynchronous Streaming Replication*.

Aplikasi PHP menggunakan mekanisme pemisahan koneksi database:
- `DB::connection('write')` diarahkan ke Primary Node.
- `DB::connection('read')` diarahkan secara acak (round-robin) ke Replicas.

Alur pengguna saat memposting komentar baru:
1. Client mengeksekusi `POST /posts/123/comments` (PHP menulis data ke Primary).
2. Server merespons dengan HTTP Status `302 Redirect` ke `/posts/123`.
3. Client secara instan mengeksekusi `GET /posts/123`.
4. PHP mengeksekusi query `SELECT` pada Read Replica untuk menampilkan post beserta komentar.

**Permasalahan:**
Pengguna membanjiri tim support dengan komplain bahwa komentar mereka "hilang" sesaat setelah diposting. Namun, jika halaman di-refresh beberapa detik kemudian, komentar tersebut baru muncul. Metrik pemantauan menunjukkan *Replication Lag* berkisar antara 100ms hingga 800ms saat traffic puncak.

```
[User Browser]
  |  1. POST /comments (Write)
  v
[PHP-FPM Worker] -------------------> [Primary DB]
  |                                        |
  |  2. HTTP 302 Redirect                  | Asynchronous Replication
  v                                        | (Lag: 100ms - 800ms)
[User Browser]                             v
  |  3. GET /posts (Read)            [Replica Node]
  v                                        |
[PHP-FPM Worker] -------------------> [Replica Node] (Stale Read! Komentar belum ada)
```

**Pertanyaan Diagnostik:**
1. Mengapa memindahkan seluruh query pembacaan ke Primary Node merupakan anti-pattern yang melanggar tujuan skalabilitas dari *read/write splitting*?
2. Rancang solusi arsitektural komprehensif untuk memastikan konsistensi **Read-Your-Own-Writes (Causal Consistency)** bagi user yang memodifikasi data, tanpa mengorbankan performa user lain yang hanya bertindak sebagai pembaca (*pure readers*).
3. Bagaimana implementasi teknis solusi tersebut menggunakan kombinasi:
   - Penandaan sesi pengguna (Cookie/Header/Session timestamp atau Database Log Sequence Number / LSN).
   - Middleware PHP yang secara cerdas merutekan koneksi ke Primary jika waktu replikasi belum melampaui LSN write terakhir dari sesi user tersebut.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Inventory Ledger & Reservation Engine

#### 1. Problem Statement
Anda ditugaskan merancang *Core Engine* reservasi tiket konser skala jutaan pengguna. Terdapat 1 konser eksklusif dengan kapasitas 500 kursi (*inventory limit*). Tiket diperebutkan oleh 50.000 pengguna secara bersamaan tepat pada pukul 12:00:00 UTC. 

Sistem **TIDAK BOLEH** mengalami *overselling* (jumlah kursi terpesan > 500), **TIDAK BOLEH** kehilangan data saldo kursi (*data corruption/lost updates*), dan **HARUS** menangani pembatalan reservasi otomatis jika pembayaran tidak diselesaikan dalam batas waktu 10 menit (*TTL release mechanism*).

#### 2. Technical Requirements
1. **PHP Runtime:** PHP 8.3+ Native (Strict Types, Readonly Properties).
2. **Database Engine:** PostgreSQL 15+ atau MySQL 8.0+.
3. **Database Schema:**
   - Tabel `inventories` (id, event_id, total_stock, reserved_stock, version).
   - Tabel `reservations` (id, user_id, event_id, status ['PENDING', 'CONFIRMED', 'EXPIRED'], expires_at, created_at).
   - Tabel `outbox_events` (id, event_type, payload, status ['PENDING', 'PROCESSED'], created_at).
4. **Idempotency Guarantee:**
   - Endpoint reservasi menerima `Idempotency-Key` pada header HTTP. Request ganda dengan key yang sama tidak boleh memicu pengurangan stok ganda.
5. **Concurrency Strategy:**
   - Gunakan pendekatan *Pessimistic Locking with Skip Locked* ATAU *Atomic Decrement with Check Constraints* untuk mencegah thread blocking massal.
6. **Fault Tolerance:**
   - Implementasikan *Retry Handler* untuk menangani *Deadlock Exceptions* dan *Serialization Failures* secara otomatis.
7. **Audit & Eventing:**
   - Setiap mutasi reservasi wajib menulis data audit ke tabel `outbox_events` di dalam batas transaksi yang sama (*Atomic Transaction Boundary*).

#### 3. Constraints
- DILARANG menggunakan framework (Gunakan PDO murni dengan konfigurasi enterprise).
- DILARANG menggunakan Redis untuk sistem reservasi utama (Database relational adalah *Single Source of Truth*).
- DILARANG menggunakan query mentah yang rentan terhadap SQL Injection (Wajib native prepared statements).
- Wajib menyertakan penanganan sinyal pembatalan / timeout transaksi database (`PDO::ATTR_TIMEOUT` dan `statement_timeout`).

#### 4. Expected Output
Sediakan satu set file kode produksi PHP:
1. `Schema.sql`: DDL tabel lengkap dengan indexes, constraints, dan tipe data yang optimal.
2. `ReservationEngine.php`: Kelas layanan utama yang menangani proses pemesanan kursi, validasi kuota, pembuatan outbox record, dan idempotency key check.
3. `DeadlockResilientExecutor.php`: Utility wrapper yang mengeksekusi *database closure* dengan retry mechanism berbasis exponential backoff + jitter.
4. `StressTestSimulation.php`: Skrip CLI PHP yang mensimulasikan minimal 50 concurrent process (menggunakan `pcntl_fork` atau `fiber/amphp/swoole`) untuk membuktikan:
   - Tidak ada kursi yang *oversold*.
   - Konsistensi antara `inventories.reserved_stock` dan total baris di tabel `reservations`.

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan pemahaman arsitektural Anda sebelum melanjutkan ke bab berikutnya.

### Saya harus memahami:
- [ ] Mekanisme internal MVCC (Multi-Version Concurrency Control) pada PostgreSQL dan MySQL (InnoDB), termasuk bagaimana undo log dan tuple visibility bekerja.
- [ ] Perbedaan konkret antara *Pessimistic Lock* (`FOR UPDATE`, `FOR SHARE`, `SKIP LOCKED`, `NOWAIT`) dan dampaknya terhadap *thread queue latency*.
- [ ] Mengapa *Optimistic Locking* tidak cocok diterapkan pada kondisi *high write-contention* (tingkat kegagalan transaksi mendekati 100%).
- [ ] Semua jenis anomali database ANSI SQL: Dirty Read, Non-Repeatable Read, Phantom Read, Read/Write Skew, dan Lost Updates.
- [ ] Batasan teknis arsitektur Shared-Nothing PHP-FPM terkait pemeliharaan koneksi database persisten, dan mengapa pooling layer eksternal (PgBouncer/ProxySQL) menjadi kebutuhan wajib di skala enterprise.
- [ ] Dinamika *Replication Lag* pada topologi Primary-Replica dan strategi penjaminan konsistensi *Read-Your-Own-Writes*.
- [ ] Masalah integritas data *Dual-Write Problem* pada arsitektur terdistribusi dan penyelesaiannya via *Transactional Outbox Pattern*.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik error code spesifik vendor database (misal: MySQL Error 1213 untuk deadlock, PostgreSQL 40P01), selama memahami SQLSTATE generik (`40001` untuk serialization failure/deadlock) dan tahu letak log diagnosanya.
- [ ] Sintaks ekstensi proprietary SQL vendor yang non-standar, cukup memahami konsep portabel ANSI SQL standard dan perilaku driver PDO.
- [ ] Algoritma internal C-source code PostgreSQL / MySQL dalam menghitung biaya eksekusi query (*Cost-Based Optimizer*), cukup memahami interpretasi visual dari perintah `EXPLAIN ANALYZE`.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengurai log *Deadlock Engine Graph* untuk merestrukturisasi urutan query aplikasi agar bebas dari saling kunci (*circular waits*).
- [ ] Mengkonfigurasi parameter driver PDO PHP secara ketat untuk kebutuhan enterprise (`ERRMODE_EXCEPTION`, `EMULATE_PREPARES => false`, `FETCH_ASSOC`, integer/float native typing).
- [ ] Merancang skema database transaksional yang kebal terhadap race condition menggunakan kombinasi *Check Constraints*, *Unique Indexes*, dan klausa *Atomic Update*.
- [ ] Mengimplementasikan *Resilient Transaction Wrapper* dengan penanganan error transient (Deadlock, Connection Lost, Lock Timeout) menggunakan strategi retry exponential backoff + jitter di PHP 8.x.
- [ ] Membangun mekanisme *Transactional Outbox Pattern* yang menjamin konsistensi antara mutasi data relasional lokal dengan message broker eksternal tanpa risiko data korup akibat *partial network partition*.