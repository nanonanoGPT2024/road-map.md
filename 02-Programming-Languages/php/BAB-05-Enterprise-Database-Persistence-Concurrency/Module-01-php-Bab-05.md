# KURIKULUM PHP ENTERPRISE LEVEL
## Kategori: 02-Programming-Languages
### Bab 05: Enterprise Architecture & Data Management
#### Modul 01: Enterprise Database Persistence & Concurrency

---

```
================================================================================
MODUL 05-01: ENTERPRISE DATABASE PERSISTENCE & CONCURRENCY
================================================================================
TINGKAT KESULITAN : ADVANCED / ENTERPRISE
PRASYARAT        : PHP 8.2+, Advanced OOP, Basic PDO & Relational Database (RDBMS)
ALOKASI WAKTU     : 180 - 240 MENIT PEMBELAJARAN MENDALAM
AUTHOR           : Senior Technical Curriculum Architect
================================================================================
```

---

### SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** Backend Engineering & Enterprise Architecture
* **Topik Inti:** Database Persistence Patterns, Transaction Isolation Levels, Concurrency Control (Pessimistic vs Optimistic), Distributed Locking, Unit of Work Architecture, dan Deadlock Mitigation.
* **Target Khalayak:** Staff Software Engineer, Senior Backend Developer, Enterprise Software Architect yang mendesain sistem pemrosesan transaksi kritis (fintech, e-commerce berkapasitas tinggi, logistik) menggunakan ekosistem PHP modern.
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang *PHP Data Objects* (PDO) dan ekstensi MySQL/PostgreSQL.
  * Pemahaman tentang model konkurensi proses PHP (PHP-FPM, worker pools, process isolation).
  * Dasar-dasar teori basis data relasional, ACID properties, dan indeks B-Tree.

---

### SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:

1. **Menganalisis Internal RDBMS Concurrency Engine:** Membedakan cara kerja Multi-Version Concurrency Control (MVCC), Two-Phase Locking (2PL), dan *lock trees* (Record Locks, Gap Locks, Next-Key Locks) pada database engine modern (MySQL InnoDB / PostgreSQL).
2. **Mengonfigurasi dan Mengontrol Transaction Isolation Levels:** Menentukan trade-off antara throughput dan anomali data (*Dirty Read*, *Non-Repeatable Read*, *Phantom Read*, *Write Skew*) pada level `READ UNCOMMITTED`, `READ COMMITTED`, `REPEATABLE READ`, dan `SERIALIZABLE`.
3. **Mengimplementasikan Concurrency Control Strategies:** Mengembangkan mekanisme *Optimistic Concurrency Control* (OCC) dengan versioning/timestamps dan *Pessimistic Concurrency Control* (PCC) menggunakan klausa lock eksplisit (`FOR UPDATE`, `FOR UPDATE NOWAIT`, `FOR UPDATE SKIP LOCKED`).
4. **Membangun Custom Persistence Engine:** Merancang arsitektur persistence decoupling berbasis pola *Data Mapper*, *Identity Map*, dan *Unit of Work (UoW)* dari nol tanpa ketergantungan framework berat.
5. **Mengelola Kegagalan Transaksi dan Distributed Race Conditions:** Mengembangkan automated deadlock retry mechanisms dengan *exponential backoff & jitter*, serta mengimplementasikan *Distributed Lock* berbasis database advisory locks dan Redis Redlock.

---

### SEKSI 03 — MINDSET & MENTAL MODEL

#### Paradoks Model "Shared-Nothing" PHP vs "Shared-State" Database

Dalam ekosistem PHP, runtime beroperasi dengan model **Shared-Nothing Architecture**. Setiap HTTP request ditangani oleh proses PHP worker independen (PHP-FPM) yang mengalokasikan memori terisolasi dan dihancurkan setelah eksekusi selesai (*ephemeral state*).

```
   [ Request 1 ] ---> [ PHP-FPM Worker 1 ] (Memory Isolated) ---+
                                                                |---> [ SHARED DATABASE STATE ]
   [ Request 2 ] ---> [ PHP-FPM Worker 2 ] (Memory Isolated) ---+     (Race Conditions Occur Here)
```

Sebaliknya, database persistence layer adalah **Shared-State Architecture**. Ketika ribuan worker PHP yang independen mengakses baris data yang sama secara bersamaan (misalnya: alokasi stok tiket konser atau pemotongan saldo rekening), ilusi isolasi PHP runtuh di level database.

#### Mental Model: The Bank Teller Analogy
Bayangkan database sebagai sebuah buku kas manual fisik yang disimpan di brankas bersama (*Shared Database*). PHP Worker adalah kasir (*Tellers*) yang bekerja di bilik masing-masing tanpa interkom:
* **Tanpa Concurrency Control:** Dua kasir membaca saldo Rp 1.000.000 secara bersamaan. Keduanya menyetujui penarikan Rp 800.000. Kasir A menulis saldo sisa Rp 200.000. Kasir B kemudian menimpa saldo dengan Rp 200.000. **Hasil:** Saldo akhir Rp 200.000 padahal uang yang keluar Rp 1.600.000 (*Double Spending / Lost Update*).
* **Pessimistic Locking:** Kasir A memegang buku kas, menguncinya, memverifikasi, menulis perubahan, dan mengembalikannya ke brankas. Kasir B harus berdiri mengantre menunggu buku kas dilepas.
* **Optimistic Locking:** Kasir A mencatat nomor versi buku (misal: Versi 42). Saat hendak menulis, Kasir A mengecek apakah versinya masih 42. Jika Kasir B telah mendahuluinya mengubah ke Versi 43, Kasir A membatalkan transaksi (*Conflict Abort*) dan membaca ulang dari awal.

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

#### 1. Concurrency Anomalies vs Isolation Levels

```
+------------------+-----------------+----------------------+-------------------+------------------+
| Isolation Level  | Dirty Read      | Non-Repeatable Read  | Phantom Read      | Write Skew       |
+------------------+-----------------+----------------------+-------------------+------------------+
| READ UNCOMMITTED | ANOMALI TERJADI | ANOMALI TERJADI      | ANOMALI TERJADI   | ANOMALI TERJADI  |
| READ COMMITTED   | AMAN            | ANOMALI TERJADI      | ANOMALI TERJADI   | ANOMALI TERJADI  |
| REPEATABLE READ  | AMAN            | AMAN                 | TERGANTUNG ENGINE | ANOMALI TERJADI  |
| SERIALIZABLE     | AMAN            | AMAN                 | AMAN              | AMAN             |
+------------------+-----------------+----------------------+-------------------+------------------+
*Catatan: InnoDB MySQL mencegah Phantom Read pada level REPEATABLE READ menggunakan Next-Key Locks.
```

#### 2. Siklus Unit of Work & Identity Map Pattern

```
 [ Client Layer ]
        │
        ▼
 [ Application Service ] ─────────── (1) Fetch Entity (ID: 101) ───────────┐
        │                                                                  │
        ▼                                                                  ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │ Unit of Work Context                                                         │
 │                                                                              │
 │  ┌────────────────────────────────────────────────────────────────────────┐  │
 │  │ Identity Map (Cache L1 dalam Request)                                  │  │
 │  │ [ ID: 101 ] ──> Instance of AccountEntity (Snapshot: Balance = 5000)   │  │
 │  └────────────────────────────────────────────────────────────────────────┘  │
 │                                                                              │
 │  (2) Modifikasi Entity State: $account->withdraw(2000)                       │
 │      State: Balance = 3000 (DIRTY)                                           │
 │                                                                              │
 │  (3) Commit Transaksi / Persist Phase:                                       │
 │      a. Change Tracking Engine mendeteksi delta (Dirty Check).              │
 │      b. Membangun topological dependency graph (Insert -> Update -> Delete). │
 │      c. Eksekusi SQL terstruktur dalam 1 Database Transaction.               │
 └──────────────────────────────────────┬───────────────────────────────────────┘
                                        │
                                        ▼ (4) Atomic SQL Flush
                       ┌─────────────────────────────────┐
                       │ RDBMS (Pessimistic / OCC Logic) │
                       └─────────────────────────────────┘
```

#### 3. Optimistic vs Pessimistic Locking Timeline

```
PESSIMISTIC LOCKING (PCC)                OPTIMISTIC CONCURRENCY CONTROL (OCC)
Worker A             Worker B            Worker A             Worker B
   │                    │                   │                    │
   ├── BEGIN            │                   ├── BEGIN            ├── BEGIN
   ├── SELECT FOR       │                   ├── SELECT (v=1)     ├── SELECT (v=1)
   │   UPDATE (Lock Acquired)               │                    │
   │                    ├── BEGIN           ├── Compute Changes  ├── Compute Changes
   │                    ├── SELECT FOR      │                    ├── UPDATE SET ...,
   │                    │   UPDATE (BLOCKED)│                    │   version=2 WHERE
   ├── UPDATE Data      │   ...             │                    │   id=1 AND version=1
   ├── COMMIT (Released)│   ...             │                    │   (Rows affected: 1)
   │                    ├── Lock Acquired   │                    ├── COMMIT
   │                    ├── UPDATE Data     ├── UPDATE SET ...,  │
   │                    ├── COMMIT          │   version=2 WHERE  │
   │                    │                   │   id=1 AND version=1
                                            │   (Rows affected: 0 -> CONFLICT EXCEPTION)
                                            ├── ROLLBACK / RETRY
```

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

#### 1. Multi-Version Concurrency Control (MVCC) & Undo Logs
Database engine relasional enterprise (seperti MySQL InnoDB atau PostgreSQL) tidak mengunci baris hanya untuk pembacaan (*consistent read*). Mereka mengimplementasikan **MVCC**:
* Setiap modifikasi data menciptakan versi rekaman lama di dalam **Undo Log Segment**.
* Baris fisik database memuat pointer sistem:
  * `DB_TRX_ID`: ID transaksi terakhir yang menyisipkan/memperbarui baris tersebut.
  * `DB_ROLL_PTR`: Roll pointer yang menunjuk ke Undo Record sebelumnya.
* Saat sebuah query pembacaan berjalan pada level `REPEATABLE READ`, engine membuat struktur memori bernama **Read View** yang merekam transaksi mana saja yang sedang aktif pada momen tersebut. Query hanya melihat baris dari transaksi yang sudah di-commit sebelum Read View dibuat.

#### 2. Anatomi Lock Tree: Record, Gap, dan Next-Key Locks
Untuk memahami perilaku `SELECT ... FOR UPDATE`, developer wajib memahami topologi locking InnoDB:
* **Record Lock:** Penguncian indeks fisik persis pada leaf node indeks B-Tree.
* **Gap Lock:** Penguncian ruang/interval kosong *di antara* nilai indeks, atau sebelum nilai pertama / setelah nilai terakhir. Tujuannya mencegah transaksi lain menyisipkan (*INSERT*) data baru ke dalam rentang tersebut (mencegah *Phantom Rows*).
* **Next-Key Lock:** Kombinasi dari **Record Lock** pada entri indeks ditambah **Gap Lock** pada area sebelum rekaman tersebut.

```
Index B-Tree Values:     [ 10 ]               [ 20 ]               [ 30 ]
Gaps:              ( -inf , 10 )        ( 10 , 20 )          ( 20 , 30 )       ( 30 , +inf )
                        ▲                    ▲
                        │                    │
Next-Key Lock on 20: ───┴────────────────────┘  (Mengunci rentang (10, 20] )
```

#### 3. PDO Driver Mechanism & Connection Pool Problem
PHP secara arsitektural tidak memiliki thread-safe connection pooling bawaan seperti Java (HikariCP) atau Go (`database/sql`). 
* Ekstensi `pdo_mysql` berkomunikasi langsung via soket UNIX atau TCP dengan database server.
* Penggunaan `PDO::ATTR_PERSISTENT => true` mempertahankan soket koneksi terbuka antar-request PHP-FPM, tetapi memiliki risiko state pollution: variabel sesi SQL, lock yang menggantung, atau uncommitted transactions yang tertinggal jika worker mengalami fatal error / timeout.
* Di lingkungan skala enterprise modern, koneksi pooling ditangani oleh proxy lapisan infrastruktur seperti **ProxySQL** (untuk MySQL) atau **PgBouncer** (untuk PostgreSQL), bukan persisten connection bawaan PHP.

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI

#### 1. Anomali Concurrency Secara Formal
* **Dirty Read (G0):** Transaksi $T_1$ memodifikasi baris. Transaksi $T_2$ membaca baris tersebut sebelum $T_1$ melakukan commit. Jika $T_1$ melakukan rollback, data yang dibaca oleh $T_2$ tidak pernah valid secara logis.
* **Non-Repeatable / Fuzzy Read (A2):** Transaksi $T_1$ membaca baris data. Transaksi $T_2$ mengubah baris tersebut dan melakukan commit. Transaksi $T_1$ membaca ulang baris tersebut dan menemukan nilai yang berbeda.
* **Phantom Read (A3):** Transaksi $T_1$ membaca himpunan baris yang memenuhi kriteria klausa `WHERE`. Transaksi $T_2$ menyisipkan (*INSERT*) data baru yang memenuhi kriteria tersebut dan commit. Transaksi $T_1$ mengulang pembacaan dan menemukan baris baru ("hantu").
* **Write Skew:** Terjadi pada level snapshot isolation di mana dua transaksi independen membaca data yang tumpang tindih, mengidentifikasi bahwa invariansi valid, namun membuat mutasi yang saling bertentangan ketika digabungkan.
  * *Contoh Klasik:* Aturan rumah sakit: minimal 1 dokter harus bertugas jaga. Dokter A dan Dokter B sama-sama bertugas. Keduanya mengajukan cuti secara simultan. Masing-masing transaksi memeriksa: "Apakah dokter lain sedang jaga?" $\rightarrow$ Ya. Keduanya disetujui. Hasil: 0 dokter jaga (Invariansi bisnis hancur).

#### 2. Two-Phase Locking (2PL) Protocol
Sistem database menjamin serializability menggunakan Two-Phase Locking:
1. **Growing Phase:** Transaksi boleh meminta lock (Shared/Exclusive), tetapi tidak boleh melepaskan lock apa pun.
2. **Shrinking Phase:** Transaksi boleh melepaskan lock, tetapi tidak boleh meminta lock baru.

Dalam praktik praktis RDBMS (Strict 2PL), semua exclusive locks ditahan sampai akhir transaksi (`COMMIT` atau `ROLLBACK`) untuk mencegah cascading aborts.

#### 3. Formula Backoff & Jitter untuk Deadlock
Ketika transaksi gagal akibat deadlock (SQLState `40001` / MySQL Error `1213`), mekanisme *retry* harus menggunakan algoritma **Full Jitter Exponential Backoff** untuk mencegah *thundering herd problem* (di mana transaksi yang bertabrakan mencoba kembali persis pada waktu yang sama dan bertabrakan ulang):

$$Backoff = \text{random}(0, \min(Cap, Base \times 2^{attempt}))$$

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi sistem eksekusi transaksi yang resilien menggunakan PHP 8.2+, memanfaatkan abstraksi PDO, Strict Typing, Savepoints, dan Automatic Deadlock Retries dengan Exponential Backoff & Jitter.

```php
<?php

declare(strict_types=1);

namespace Enterprise\Persistence;

use PDO;
use PDOException;
use Throwable;
use Closure;
use RuntimeException;
use InvalidArgumentException;

/**
 * Representasi Transaction Isolation Level standar SQL.
 */
enum IsolationLevel: string
{
    case READ_UNCOMMITTED = 'READ UNCOMMITTED';
    case READ_COMMITTED   = 'READ COMMITTED';
    case REPEATABLE_READ  = 'REPEATABLE READ';
    case SERIALIZABLE     = 'SERIALIZABLE';
}

/**
 * Driver type database target.
 */
enum DatabaseDriver: string
{
    case MYSQL = 'mysql';
    case POSTGRES = 'pgsql';
}

final class TransactionManager
{
    private const int MAX_RETRIES = 5;
    private const int BASE_BACKOFF_MS = 50;
    private const int CAP_BACKOFF_MS = 1000;

    // Error code standard SQLSTATE untuk Deadlock dan Serialization Failure
    private const array RETRYABLE_SQLSTATES = [
        '40001', // Serialization failure / Deadlock (Standard SQL)
        '40P01', // Deadlock detected (PostgreSQL)
        '1213',  // Deadlock found when trying to get lock (MySQL internal code)
        '1205',  // Lock wait timeout exceeded (MySQL internal code)
    ];

    public function __construct(
        private readonly PDO $pdo,
        private readonly DatabaseDriver $driver = DatabaseDriver::MYSQL
    ) {
        $this->pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $this->pdo->setAttribute(PDO::ATTR_EMULATE_PREPARES, false);
    }

    /**
     * Mengeksekusi unit kerja dalam transaksi terisolasi dengan penanganan deadlock otomatis.
     *
     * @template T
     * @param Closure(PDO): T $unitOfWork
     * @param IsolationLevel $isolationLevel
     * @return T
     * @throws Throwable
     */
    public function transactional(
        Closure $unitOfWork,
        IsolationLevel $isolationLevel = IsolationLevel::REPEATABLE_READ
    ): mixed {
        if ($this->pdo->inTransaction()) {
            throw new RuntimeException("Nested transactional context must use savepoints explicitly.");
        }

        $attempt = 0;

        while (true) {
            $attempt++;
            try {
                $this->setIsolationLevel($isolationLevel);
                $this->pdo->beginTransaction();

                $result = $unitOfWork($this->pdo);

                $this->pdo->commit();
                return $result;
            } catch (Throwable $e) {
                if ($this->pdo->inTransaction()) {
                    try {
                        $this->pdo->rollBack();
                    } catch (PDOException $rollbackException) {
                        // Log rollback failure if connection died completely
                    }
                }

                if ($this->isRetryableException($e) && $attempt <= self::MAX_RETRIES) {
                    $this->sleepWithJitter($attempt);
                    continue;
                }

                throw $e;
            }
        }
    }

    /**
     * Menjalankan closure dalam Savepoint context (Nested Transaction Simulation).
     *
     * @template T
     * @param string $savepointName
     * @param Closure(PDO): T $unitOfWork
     * @return T
     * @throws Throwable
     */
    public function executeInSavepoint(string $savepointName, Closure $unitOfWork): mixed
    {
        if (!$this->pdo->inTransaction()) {
            throw new RuntimeException("Savepoints can only be used within an active transaction.");
        }

        // Sanitasi nama savepoint untuk mencegah injection pada identifier
        if (!preg_match('/^[a-zA-Z0-9_]+$/', $savepointName)) {
            throw new InvalidArgumentException("Invalid savepoint identifier: {$savepointName}");
        }

        $this->pdo->exec("SAVEPOINT {$savepointName}");

        try {
            $result = $unitOfWork($this->pdo);
            $this->pdo->exec("RELEASE SAVEPOINT {$savepointName}");
            return $result;
        } catch (Throwable $e) {
            $this->pdo->exec("ROLLBACK TO SAVEPOINT {$savepointName}");
            throw $e;
        }
    }

    private function setIsolationLevel(IsolationLevel $level): void
    {
        $sql = match ($this->driver) {
            DatabaseDriver::MYSQL => "SET TRANSACTION ISOLATION LEVEL {$level->value}",
            DatabaseDriver::POSTGRES => "SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL {$level->value}",
        };

        $this->pdo->exec($sql);
    }

    private function isRetryableException(Throwable $e): bool
    {
        if (!$e instanceof PDOException) {
            return false;
        }

        $sqlState = (string)$e->getCode();
        $errorInfo = $e->errorInfo[1] ?? null;

        if (in_array($sqlState, self::RETRYABLE_SQLSTATES, true)) {
            return true;
        }

        if ($errorInfo !== null && in_array((string)$errorInfo, self::RETRYABLE_SQLSTATES, true)) {
            return true;
        }

        // String matching fallback untuk pesan error driver spesifik
        $message = strtolower($e->getMessage());
        return str_contains($message, 'deadlock') || str_contains($message, 'lock wait timeout');
    }

    private function sleepWithJitter(int $attempt): void
    {
        // Exponential backoff: Base * 2^(attempt - 1)
        $maxBackoff = min(self::CAP_BACKOFF_MS, self::BASE_BACKOFF_MS * (2 ** ($attempt - 1)));
        
        // Full Jitter: random antara 0 sampai calculated maxBackoff
        $jitteredMs = random_int(0, $maxBackoff);

        usleep($jitteredMs * 1000);
    }
}
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi arsitektur dari implementasi `TransactionManager` di atas:

1. **Baris 20–26 (`IsolationLevel` Enum):** Menerapkan type-safety ketat untuk Isolation Level SQL standar ANSI-SQL92. Mencegah konfigurasi transaksi yang *invalid* sebelum mencapai level parsing SQL di database.
2. **Baris 39–47 (`RETRYABLE_SQLSTATES` Array):** Memetakan kode status standar industri:
   * `40001`: Kode ANSI SQLSTATE untuk *serialization failure*, dipicu saat transaksi bersaing pada level isolation tinggi.
   * `1213`: MySQL error code khusus engine InnoDB saat algoritma *Deadlock Detection* memutuskan transaksi ini sebagai korban (*victim*).
   * `1205`: MySQL lock wait timeout, terjadi jika resource terkunci melebihi `innodb_lock_wait_timeout`.
3. **Baris 51–54 (`__construct` Options):** Menonaktifkan `PDO::ATTR_EMULATE_PREPARES` menjamin *native prepared statements* dijalankan langsung oleh database server. Ini memastikan data binding dikirim secara biner terpisah dari string SQL, mencegah *SQL Injection* dan meningkatkan performa query berulang.
4. **Baris 67–70 (Nested Transaction Guard):** PDO tidak mendukung *nested physical transactions* (pemanggilan ganda `beginTransaction()` pada satu koneksi akan memicu Exception atau silent commit di driver tertentu). Guard clause ini memaksa pemrogram menggunakan Savepoint jika ingin menjalankan sub-transaksi logis.
5. **Baris 78–80 (`setIsolationLevel`):** Menyetel tingkat isolasi tepat sebelum `beginTransaction()`. Di MySQL, mengubah isolasi sesi berlaku untuk transaksi berikutnya yang dibuka.
6. **Baris 97–100 (Deadlock Evaluation & Retry Loop):** Menangkap exception, memeriksa apakah failure bersumber dari race condition/deadlock yang *recoverable*, dan mengulang eksekusi closure $N$ kali tanpa merusak konsistensi data.
7. **Baris 112–132 (`executeInSavepoint`):** Menggunakan native SQL `SAVEPOINT`, `RELEASE SAVEPOINT`, dan `ROLLBACK TO SAVEPOINT`. Ini memungkinkan rollback parsial pada operasi bersarang tanpa membatalkan transaksi utama.
8. **Baris 160–168 (`sleepWithJitter`):** Mengimplementasikan rumus Full Jitter $U(0, \min(Cap, Base \cdot 2^{attempt}))$. Jitter memecah sinkronisasi antar-thread/worker yang bersaing sehingga collision rate pada percobaan ulang berikutnya turun mendekati nol.

---

### SEKSI 09 — STUDI KASUS NYATA

#### Skenario Sistem: "Flash-Sale Multi-Tenant Inventory & Financial Ledger Balancing"

**Deskripsi Masalah Bisnis:**
Sebuah platform e-commerce enterprise berskala jutaan pengguna aktif menyelenggarakan Flash-Sale produk teknologi edisi terbatas (stok: 50 unit). Pada detik pertama pembukaan, masuk 10.000 permintaan pembelian konkuren per detik.

**Invariansi Bisnis Kritis (Business Invariants):**
1. **Zero Overselling:** Stok inventaris tidak boleh kurang dari 0 (Tidak boleh ada 51 pembeli yang berhasil *checkout*).
2. **Double-Entry Ledger Integrity:** Setiap pemotongan saldo pembeli harus memiliki pasangan *credit* yang tepat ke saldo pedagang (*merchant*) dan pembagian *platform fee*. Jumlah total mutasi debit dan kredit wajib $\sum (\text{Debit} - \text{Credit}) = 0$.
3. **High Throughput / Low Latency:** Kegagalan stok habis pada 1 produk tidak boleh mengunci (*lock*) produk lain yang tidak terkait. Transaksi harus bebas dari bottleneck global locking.

**Analisis Titik Rawan Anomali:**
* Jika menggunakan `SELECT balance FROM accounts WHERE id = 1` dilanjutkan dengan update di PHP, ribuan request membaca data snapshot yang sama (*Lost Update Anomaly*).
* Jika menggunakan `SELECT ... FOR UPDATE` tanpa pengurutan (*deterministic ordering*) ID entitas, Request A mengunci (Akun 1 $\rightarrow$ Akun 2) sementara Request B mengunci (Akun 2 $\rightarrow$ Akun 1). Ini memicu **Circular Deadlock**.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem produksi penuh yang memadukan **Unit of Work Pattern**, **Pessimistic Locking dengan Deterministic Resource Ordering**, serta **Double-Entry Ledger Architecture** menggunakan PHP 8.2+.

```php
<?php

declare(strict_types=1);

namespace Enterprise\Ledger;

use PDO;
use PDOException;
use RuntimeException;
use InvalidArgumentException;
use DateTimeImmutable;

// -----------------------------------------------------------------------------
// DOMAIN MODELS & VALUE OBJECTS
// -----------------------------------------------------------------------------

final readonly class Money
{
    public function __construct(public int $amountInCents)
    {
        if ($this->amountInCents < 0) {
            throw new InvalidArgumentException("Amount cannot be negative.");
        }
    }

    public function add(Money $other): self
    {
        return new self($this->amountInCents + $other->amountInCents);
    }

    public function subtract(Money $other): self
    {
        if ($other->amountInCents > $this->amountInCents) {
            throw new RuntimeException("Insufficient funds for subtraction.");
        }
        return new self($this->amountInCents - $other->amountInCents);
    }
}

final class Account
{
    public function __construct(
        public readonly int $id,
        public readonly string $accountNumber,
        private Money $balance,
        private int $version
    ) {}

    public function getBalance(): Money
    {
        return $this->balance;
    }

    public function getVersion(): int
    {
        return $this->version;
    }

    public function debit(Money $amount): void
    {
        $this->balance = $this->balance->subtract($amount);
    }

    public function credit(Money $amount): void
    {
        $this->balance = $this->balance->add($amount);
    }

    public function incrementVersion(): void
    {
        $this->version++;
    }
}

final class ProductInventory
{
    public function __construct(
        public readonly int $id,
        public readonly string $sku,
        private int $availableStock,
        private int $version
    ) {
        if ($this->availableStock < 0) {
            throw new InvalidArgumentException("Stock cannot be initialized to negative value.");
        }
    }

    public function getAvailableStock(): int
    {
        return $this->availableStock;
    }

    public function getVersion(): int
    {
        return $this->version;
    }

    public function reserve(int $quantity): void
    {
        if ($quantity <= 0) {
            throw new InvalidArgumentException("Quantity must be greater than zero.");
        }
        if ($this->availableStock < $quantity) {
            throw new RuntimeException("Insufficient stock for product SKU: {$this->sku}.");
        }
        $this->availableStock -= $quantity;
    }
}

// -----------------------------------------------------------------------------
// IDENTITY MAP PATTERN
// -----------------------------------------------------------------------------

final class IdentityMap
{
    /** @var array<string, object> */
    private array $map = [];

    public function get(string $class, int $id): ?object
    {
        $key = $this->buildKey($class, $id);
        return $this->map[$key] ?? null;
    }

    public function set(int $id, object $entity): void
    {
        $key = $this->buildKey($entity::class, $id);
        $this->map[$key] = $entity;
    }

    public function clear(): void
    {
        $this->map = [];
    }

    private function buildKey(string $class, int $id): string
    {
        return "{$class}:{$id}";
    }
}

// -----------------------------------------------------------------------------
// REPOSITORY LAYER WITH CONCURRENCY LOCKING
// -----------------------------------------------------------------------------

final class AccountRepository
{
    public function __construct(
        private readonly PDO $pdo,
        private readonly IdentityMap $identityMap
    ) {}

    /**
     * Mengambil account dengan Pessimistic Exclusive Lock (FOR UPDATE).
     */
    public function findByIdForUpdate(int $id): Account
    {
        // Tetap eksekusi query lock ke database untuk menjamin row-level locking fisik
        $stmt = $this->pdo->prepare(
            "SELECT id, account_number, balance_cents, version 
             FROM accounts 
             WHERE id = :id 
             FOR UPDATE"
        );
        $stmt->execute(['id' => $id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            throw new RuntimeException("Account with ID {$id} not found.");
        }

        $account = new Account(
            id: (int)$row['id'],
            accountNumber: (string)$row['account_number'],
            balance: new Money((int)$row['balance_cents']),
            version: (int)$row['version']
        );

        $this->identityMap->set($account->id, $account);
        return $account;
    }

    public function update(Account $account): void
    {
        $stmt = $this->pdo->prepare(
            "UPDATE accounts 
             SET balance_cents = :balance, version = version + 1 
             WHERE id = :id"
        );

        $stmt->execute([
            'balance' => $account->getBalance()->amountInCents,
            'id' => $account->id,
        ]);

        $account->incrementVersion();
    }
}

final class InventoryRepository
{
    public function __construct(
        private readonly PDO $pdo,
        private readonly IdentityMap $identityMap
    ) {}

    public function findByIdForUpdate(int $id): ProductInventory
    {
        $stmt = $this->pdo->prepare(
            "SELECT id, sku, available_stock, version 
             FROM product_inventory 
             WHERE id = :id 
             FOR UPDATE"
        );
        $stmt->execute(['id' => $id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            throw new RuntimeException("Inventory for product ID {$id} not found.");
        }

        $inventory = new ProductInventory(
            id: (int)$row['id'],
            sku: (string)$row['sku'],
            availableStock: (int)$row['available_stock'],
            version: (int)$row['version']
        );

        $this->identityMap->set($inventory->id, $inventory);
        return $inventory;
    }

    public function update(ProductInventory $inventory): void
    {
        $stmt = $this->pdo->prepare(
            "UPDATE product_inventory 
             SET available_stock = :stock, version = version + 1 
             WHERE id = :id"
        );

        $stmt->execute([
            'stock' => $inventory->getAvailableStock(),
            'id' => $inventory->id,
        ]);
    }
}

// -----------------------------------------------------------------------------
// CORE SETTLEMENT SERVICE WITH DEADLOCK PREVENTION VIA DETERMINISTIC ORDERING
// -----------------------------------------------------------------------------

final class FlashSaleOrderProcessor
{
    public function __construct(
        private readonly PDO $pdo,
        private readonly AccountRepository $accountRepo,
        private readonly InventoryRepository $inventoryRepo,
        private readonly IdentityMap $identityMap
    ) {}

    /**
     * Memproses pesanan Flash Sale:
     * 1. Mengunci inventaris produk.
     * 2. Mengunci akun sumber dan target secara DETERMINISTIK (Sorting ID) guna mencegah Deadlock 2PL.
     * 3. Membuat Ledger Record (Double-Entry Bookkeeping).
     * 4. Memperbarui seluruh state secara atomik.
     */
    public function processOrder(
        int $buyerAccountId,
        int $merchantAccountId,
        int $productId,
        int $quantity,
        Money $totalPrice
    ): void {
        $this->identityMap->clear();

        // 1. Kunci resource Inventory terlebih dahulu
        $inventory = $this->inventoryRepo->findByIdForUpdate($productId);
        $inventory->reserve($quantity);

        // 2. Deadlock Prevention Strategy: Deterministic Locking Order
        // Selalu kunci akun dengan ID terkecil terlebih dahulu, baru ID yang lebih besar!
        $accountIds = [$buyerAccountId, $merchantAccountId];
        sort($accountIds, SORT_NUMERIC);

        /** @var array<int, Account> $lockedAccounts */
        $lockedAccounts = [];
        foreach ($accountIds as $id) {
            $lockedAccounts[$id] = $this->accountRepo->findByIdForUpdate($id);
        }

        $buyerAccount = $lockedAccounts[$buyerAccountId];
        $merchantAccount = $lockedAccounts[$merchantAccountId];

        // 3. Mutasi State Domain
        $buyerAccount->debit($totalPrice);
        $merchantAccount->credit($totalPrice);

        // 4. Double-Entry Ledger Entry Insertion
        $this->recordLedgerEntry(
            debitAccountId: $buyerAccount->id,
            creditAccountId: $merchantAccount->id,
            amount: $totalPrice,
            referenceType: 'FLASH_SALE_PURCHASE',
            referenceId: "PRD-{$productId}"
        );

        // 5. Persist State Changes
        $this->inventoryRepo->update($inventory);
        $this->accountRepo->update($buyerAccount);
        $this->accountRepo->update($merchantAccount);
    }

    private function recordLedgerEntry(
        int $debitAccountId,
        int $creditAccountId,
        Money $amount,
        string $referenceType,
        string $referenceId
    ): void {
        $stmt = $this->pdo->prepare(
            "INSERT INTO financial_ledger 
             (debit_account_id, credit_account_id, amount_cents, reference_type, reference_id, created_at) 
             VALUES (:debit_id, :credit_id, :amount, :ref_type, :ref_id, :created_at)"
        );

        $now = (new DateTimeImmutable())->format('Y-m-d H:i:s');

        $stmt->execute([
            'debit_id' => $debitAccountId,
            'credit_id' => $creditAccountId,
            'amount' => $amount->amountInCents,
            'ref_type' => $referenceType,
            'ref_id' => $referenceId,
            'created_at' => $now,
        ]);
    }
}

// -----------------------------------------------------------------------------
// INTEGRATION TEST & RUNNER
// -----------------------------------------------------------------------------

// Inisialisasi koneksi Database SQLite in-memory untuk verifikasi fungsionalitas
$pdo = new PDO('sqlite::memory:');
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

// Setup Schema
$pdo->exec("
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY,
        account_number TEXT NOT NULL,
        balance_cents INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE product_inventory (
        id INTEGER PRIMARY KEY,
        sku TEXT NOT NULL,
        available_stock INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE financial_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        debit_account_id INTEGER NOT NULL,
        credit_account_id INTEGER NOT NULL,
        amount_cents INTEGER NOT NULL,
        reference_type TEXT NOT NULL,
        reference_id TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
");

// Fixture Data
$pdo->exec("INSERT INTO accounts (id, account_number, balance_cents, version) VALUES (1, 'ACC-BUYER-01', 500000, 1)"); // Saldo 5.000,00
$pdo->exec("INSERT INTO accounts (id, account_number, balance_cents, version) VALUES (2, 'ACC-MERCHANT-01', 100000, 1)"); // Saldo 1.000,00
$pdo->exec("INSERT INTO product_inventory (id, sku, available_stock, version) VALUES (100, 'PHONE-FLAGSHIP-01', 50, 1)"); // Stok 50

$identityMap = new IdentityMap();
$accountRepo = new AccountRepository($pdo, $identityMap);
$inventoryRepo = new InventoryRepository($pdo, $identityMap);
$processor = new FlashSaleOrderProcessor($pdo, $accountRepo, $inventoryRepo, $identityMap);

// Eksekusi Pesanan
$pdo->beginTransaction();
try {
    $processor->processOrder(
        buyerAccountId: 1,
        merchantAccountId: 2,
        productId: 100,
        quantity: 2,
        totalPrice: new Money(200000) // Harga 2.000,00
    );
    $pdo->commit();
    echo "TRANSAKSI SUKSES DIVERIFIKASI SECARA ATOMIK.\n";
} catch (Throwable $e) {
    $pdo->rollBack();
    echo "TRANSAKSI GAGAL: " . $e->getMessage() . "\n";
}

// Verifikasi State Akhir
$buyer = $accountRepo->findByIdForUpdate(1);
$merchant = $accountRepo->findByIdForUpdate(2);
$product = $inventoryRepo->findByIdForUpdate(100);

echo "Sisa Saldo Pembeli  : " . $buyer->getBalance()->amountInCents . " cents (Ekspektasi: 300000)\n";
echo "Sisa Saldo Merchant : " . $merchant->getBalance()->amountInCents . " cents (Ekspektasi: 300000)\n";
echo "Sisa Stok Produk    : " . $product->getAvailableStock() . " unit (Ekspektasi: 48)\n";
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih mekanisme konkurensi adalah keputusan trade-off antara **Throughput (Latency)**, **Data Consistency**, dan **Complexity Overhead**.

| Dimensi Parameter | Pessimistic Locking (`SELECT FOR UPDATE`) | Optimistic Locking (`OCC Version Check`) | Distributed Lock (Redis / Redlock) | Message Queue Serialization (Saga/Worker) |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput di Kontensi Tinggi** | **Rendah** (Thread antre & blocking pada level DB engine). | **Sangat Rendah** (High Abort/Retry Rate membuang CPU). | **Sedang** (Overhead latensi jaringan ke Redis). | **Sangat Tinggi** (Request diubah menjadi async job). |
| **Throughput di Kontensi Rendah** | **Tinggi** (Lock cepat dilepas). | **Maksimal** (Zero Lock Overhead, hanya conditional update). | **Sedang** (Tambahan RTT ke Redis cache layer). | **Rendah/Asinkron** (User harus menunggu polling worker). |
| **Resiko Deadlock** | **Tinggi** (Membutuhkan strict deterministic lock ordering). | **Nol** (Tidak ada physical DB row holding). | **Nol pada DB** (Risiko starvation atau TTL expiration). | **Nol** (Data diproses strictly serial per partition key). |
| **Overhead Sumber Daya** | DB Connection & Lock Table Memory. | CPU Cycles untuk pemrosesan retry logic. | Redis Memory, Network Latency, & Clock Drift Drift Risks. | Broker Infra (Kafka/RabbitMQ) & State Machine Store. |
| **Best Used For** | Finansial Core, Ledger, Alokasi Stok Flash-Sale Rendah-Sedang. | Pembaruan Profil Pengguna, Dokumen Kolaboratif, Master Data. | Koordinasi resource multi-cluster/multi-service (Mikroservis). | Event-Driven Architectures, Booking Pesawat Skala Global. |

#### Perbandingan Pola Arsitektur Persistence: Active Record vs Data Mapper

```
ACTIVE RECORD (e.g., Laravel Eloquent)
┌───────────────────────────────────────────────┐
│ User Model                                    │
│ - Data Properties ($name, $email)             │
│ - Persistence Logic (save(), delete(), pdo)   │ ──> COUPLED TO DATABASE SCHEMA
│ - Business Logic (calculateBonus())           │
└───────────────────────────────────────────────┘
  Kelebihan : Cepat untuk prototyping, developer experience instan.
  Kelemahan : Melanggar Single Responsibility Principle (SRP), sulit di-unit-test secara terisolasi tanpa DB nyata.

DATA MAPPER (e.g., Doctrine ORM / Custom Enterprise UoW)
┌─────────────────────┐      ┌─────────────────────────┐      ┌──────────────────────┐
│ User Entity         │      │ UserRepository / Mapper │      │ Database             │
│ (Pure Domain State) │ <──> │ (Translates Entity <->  │ <──> │ (Relational Schema)  │
│ (No DB Dependency)  │      │  Table Rows via SQL)    │      │                      │
└─────────────────────┘      └─────────────────────────┘      └──────────────────────┘
  Kelebihan : Strict Separation of Concerns, Domain Logic murni dan testable 100%.
  Kelemahan : Boilerplate tinggi, kurva pembelajaran arsitektur lebih terjal.
```

---

### SEKSI 12 — EDGE CASES & PITFALLS

#### 1. The Phantom Next-Key Lock Traps on Non-Existent Rows
Saat mengeksekusi:
```sql
SELECT * FROM orders WHERE tracking_code = 'TRX-999' FOR UPDATE;
```
Jika baris dengan `tracking_code = 'TRX-999'` **tidak ditemukan** di database, dan kolom tersebut memiliki index:
* InnoDB tidak hanya mengembalikan empty result, melainkan memasang **Gap Lock** pada interval tempat nilai tersebut seharusnya berada.
* Jika ada 100 worker mencoba mengecek tracking code baru yang berbeda pada interval yang sama secara bersamaan, mereka semua akan saling memblokir (*Gap Lock Contention*) dan memicu **Deadlock Cascade** saat mencoba melakukan `INSERT`.

#### 2. Auto-Commit Truncation & Implicit DDL Commits
Di MySQL, pengeksekusian perintah DDL (*Data Definition Language*) seperti:
```sql
ALTER TABLE accounts ADD COLUMN temporary_flag INT;
CREATE TABLE temp_log (...);
```
secara internal akan memicu **Implicit Commit** secara otomatis pada transaksi aktif yang sedang berjalan. Jika operasi DDL ditempatkan di tengah-tengah blok `beginTransaction()` PHP, transaksi sebelumnya tidak akan bisa di-rollback lagi.

#### 3. Transaction Starvation via Lock Wait Timeout
Jika transaksi $T_1$ menahan lock pada baris populer selama 60 detik (misalnya karena memanggil HTTP API eksternal di dalam blok transaksi), transaksi lain ($T_2, T_3, \dots, T_n$) yang mencoba mengakses baris tersebut akan hang dan akhirnya melempar:
`PDOException: SQLSTATE[HY000]: General error: 1205 Lock wait timeout exceeded; try restarting transaction`
* **Golden Rule:** Dilarang keras melakukan I/O eksternal (cURL, Microservice HTTP Call, Kirim Email, Redis Call Lambat) di dalam blok physical transaction database!

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

#### Mistake 1: Read-Modify-Write Race Condition (The "Lost Update")
* **Kode Anti-Pattern:**
  ```php
  // FATAL: Dua request bersamaan membaca 100, keduanya menulis 90!
  $account = $repo->find(1); // Normal SELECT tanpa lock
  $account->balance -= 10;
  $repo->save($account);     // UPDATE accounts SET balance = 90 WHERE id = 1
  ```
* **Solusi Benar:**
  Gunakan Atomic Direct Update jika mutasi bersifat sederhana, atau gunakan `FOR UPDATE` jika terdapat validasi logika domain yang kompleks:
  ```sql
  -- Solusi Atomic SQL
  UPDATE accounts SET balance = balance - 10 WHERE id = 1 AND balance >= 10;
  ```

#### Mistake 2: Non-Deterministic Lock Ordering (The Deadlock Engine)
* **Kode Anti-Pattern:**
  ```php
  function transfer(int $fromId, int $toId, int $amount): void {
      $from = $repo->findByIdForUpdate($fromId); // Worker 1 locks ID 1
      $to = $repo->findByIdForUpdate($toId);     // Worker 2 locks ID 2
      // Jika Worker 1 transfer 1 -> 2 DAN Worker 2 transfer 2 -> 1 secara bersamaan => DEADLOCK INSTAN!
  }
  ```
* **Solusi Benar:**
  Urutkan akuisisi lock berdasarkan determinisme ID:
  ```php
  function transfer(int $fromId, int $toId, int $amount): void {
      $firstId = min($fromId, $toId);
      $secondId = max($fromId, $toId);
      
      $firstAccount = $repo->findByIdForUpdate($firstId);
      $secondAccount = $repo->findByIdForUpdate($secondId);
  }
  ```

#### Mistake 3: Menelan Exception di dalam Rollback Catch Block
* **Kode Anti-Pattern:**
  ```php
  try {
      $pdo->beginTransaction();
      // work...
      $pdo->commit();
  } catch (\Exception $e) {
      $pdo->rollBack();
      // TIDAK MELEMPAR EXCEPTION KEMBALI!
      // Caller mengira proses sukses padahal data gagal disimpan!
  }
  ```
* **Solusi Benar:**
  Selalu re-throw exception atau bungkus ke dalam Domain-Specific Exception setelah `rollBack()` dipanggil.

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Shortest Transaction Lifetime:** Buka koneksi transaksi selambat mungkin, lakukan kalkulasi berat dan pemrosesan format data di luar transaksi, commit secepat mungkin.
2. **Deterministic Locking Order:** Terapkan pengurutan alfanumerik atau integer pada seluruh entity ID sebelum menjalankan query penguncian (`FOR UPDATE`).
3. **Explicit Column Selection on Locks:** Jangan gunakan `SELECT * FOR UPDATE`. Sebutkan hanya kolom yang dibutuhkan untuk meminimalisasi pembacaan row storage sekunder.
4. **Idempotency Keys Enforcement:** Pastikan seluruh transaksi mutasi finansial/state kritis menyertakan `idempotency_key` unik pada tabel transaksi dengan konstrain `UNIQUE INDEX` untuk menangkal *network retry duplication*.
5. **Use `NOWAIT` or `SKIP LOCKED` When Applicable:**
   * `SELECT ... FOR UPDATE NOWAIT`: Gagal seketika jika baris terkunci, mencegah worker PHP menggantung (*fail-fast architecture*).
   * `SELECT ... FOR UPDATE SKIP LOCKED`: Mengabaikan baris yang sedang dikunci transaksi lain. Pola ideal untuk mengimplementasikan *Database Job Queue Worker*.

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

#### Indeks yang Selaras dengan Row Locking
Ketika database mengeksekusi `SELECT ... FOR UPDATE`, InnoDB harus menemukan baris target menggunakan **Indeks**. Jika kriteria `WHERE` tidak menggunakan kolom yang terindeks:
* InnoDB terpaksa melakukan **Full Table Scan**.
* Akibatnya: **Setiap baris dan setiap *gap* dalam tabel akan dikunci secara eksklusif**. Tabel terkunci total untuk seluruh operasi insert dan update dari transaksi lain.

```sql
-- Buruk (Mengunci Seluruh Tabel jika sku tidak di-index):
SELECT * FROM product_inventory WHERE sku = 'MACBOOK-M3' FOR UPDATE;

-- Solusi: Tambahkan B-Tree Index eksplisit
CREATE UNIQUE INDEX idx_product_inventory_sku ON product_inventory (sku);
```

#### Read-Write Splitting Aware Transactions
Dalam arsitektur skala enterprise yang menggunakan arsitektur Read-Replicas:
* Pastikan `TransactionManager` selalu mengarahkan koneksi ke **Primary (Master) Database Node** saat transaksi dibuka.
* Jangan jalankan query read transaksional ke Replikasi Slave karena **Replication Lag** (asynchronous binlog shipping) akan menyebabkan data yang dibaca usang (*stale read*), merusak keputusan logika locking Anda.

---

### SEKSI 16 — KEAMANAN & HARDENING

#### 1. Transaction-Induced Denial of Service (DoS) Starvation
Penyerang dapat mengeksploitasi endpoint transaksi lambat dengan membuka ratusan koneksi HTTP konkuren secara simultan untuk menahan baris kunci tertentu. Hal ini menghabiskan pool koneksi database (*Max Connections Exhaustion*).
* **Mitigasi:**
  * Pasang timeout agresif di level database: `SET SESSION innodb_lock_wait_timeout = 3;` (Gagal dalam 3 detik jika resource sibuk).
  * Batasi jumlah worker PHP-FPM dan pasang rate limiting pada API gateway berdasarkan `user_id` / `client_ip`.

#### 2. SQL Injection dalam Identifier Lock Dinamis
Developer sering melakukan sanitasi prepared statement pada nilai parameter (*values*), namun lupa melakukan sanitasi pada Savepoint Name atau Table Name dinamis.
* **Mitigasi:**
  Gunakan strict regex whitelist (`/^[a-zA-Z0-9_]+$/`) untuk seluruh identifier SQL dinamis yang tidak dapat di-parameterisasi oleh native prepared statements.

---

### SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

#### 1. Real-time Lock & Deadlock Inspection SQL (MySQL 8.0+)
Gunakan diagnostic query berikut untuk mendeteksi transaksi mana yang sedang memblokir transaksi lain:

```sql
SELECT 
    r.trx_id waiting_trx_id,
    r.trx_mysql_thread_id waiting_thread,
    r.trx_query waiting_query,
    b.trx_id blocking_trx_id,
    b.trx_mysql_thread_id blocking_thread,
    b.trx_query blocking_query,
    TIMESTAMPDIFF(SECOND, r.trx_wait_started, NOW()) AS wait_age_seconds
FROM performance_schema.data_lock_waits w
JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_engine_transaction_id
JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_engine_transaction_id;
```

#### 2. OpenTelemetry Tracing Span Decorator untuk Transaksi
Bungkus eksekusi `TransactionManager` dengan span APM untuk memantau durasi penahanan transaksi secara visual:

```php
<?php

declare(strict_types=1);

namespace Enterprise\Telemetry;

use Enterprise\Persistence\TransactionManager;
use Enterprise\Persistence\IsolationLevel;
use Closure;

final class ObservableTransactionManager
{
    public function __construct(
        private readonly TransactionManager $innerManager
    ) {}

    public function transactional(
        Closure $unitOfWork,
        IsolationLevel $isolationLevel = IsolationLevel::REPEATABLE_READ
    ): mixed {
        $startTime = microtime(true);
        $transactionId = bin2hex(random_bytes(8));
        
        error_log("[TX-START] ID: {$transactionId} | Level: {$isolationLevel->value}");

        try {
            $result = $this->innerManager->transactional($unitOfWork, $isolationLevel);
            $durationMs = (microtime(true) - $startTime) * 1000;
            error_log("[TX-COMMIT] ID: {$transactionId} | Duration: {$durationMs}ms");
            return $result;
        } catch (\Throwable $e) {
            $durationMs = (microtime(true) - $startTime) * 1000;
            error_log("[TX-ROLLBACK] ID: {$transactionId} | Duration: {$durationMs}ms | Error: {$e->getMessage()}");
            throw $e;
        }
    }
}
```

---

### SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ENTERPRISE PERSISTENCE CHEAT SHEET                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. ACID ISOLATION LEVELS MATRIX                                                        │
│    - Read Committed   : Mencegah Dirty Read. Standard default PostgreSQL.              │
│    - Repeatable Read  : Mencegah Dirty & Non-Repeatable Read. Standard default MySQL.  │
│    - Serializable     : Strict 2PL. Mencegah Write Skew tapi mengorbankan koncurrency. │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. CONCURRENCY CONTROL PATTERNS                                                        │
│    - Pessimistic Locking : SELECT ... FOR UPDATE (Use for High Contention/Fintech)     │
│    - Optimistic Locking  : UPDATE ... WHERE version = :v (Use for Low Contention Web)  │
│    - Queue Serialization : Kafka / RabbitMQ Async (Use for Ultra-High Volume Traffic)  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. DEADLOCK PREVENTION INVARIANTS                                                      │
│    - Deterministic Ordering: Always sort resource IDs ascending before locking!        │
│    - Keep TX Short         : No API Calls, No Heavy Compute inside DB Transactions.    │
│    - Retry with Full Jitter: Sleep(random(0, min(Cap, Base * 2^attempt))).             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. ESSENTIAL ENGINE COMMANDS                                                           │
│    - MySQL Deadlock Status : SHOW ENGINE INNODB STATUS;                                │
│    - Non-blocking Row Lock : SELECT * FROM tbl WHERE id = 1 FOR UPDATE NOWAIT;        │
│    - Queue Extraction Lock : SELECT * FROM tbl WHERE status='NEW' FOR UPDATE SKIP LOCKED;│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### Kuis Tingkat Dasar (Basic)

1. **Apa perbedaan mendasar antara anomali *Dirty Read* dan *Non-Repeatable Read*?**
   * *Jawaban:* Dirty Read terjadi ketika transaksi membaca perubahan data dari transaksi lain yang **belum di-commit** (dan mungkin di-rollback). Non-Repeatable Read terjadi ketika transaksi membaca data yang sama dua kali, tetapi transaksi lain telah **mengubah dan melakukan commit** di antara kedua pembacaan tersebut, menghasilkan nilai yang berbeda.

2. **Mengapa pemanggilan fungsi pengiriman email atau API pihak ketiga di dalam blok transaksi database dianggap sebagai arsitektur yang buruk?**
   * *Jawaban:* Karena operasi I/O eksternal memiliki latensi tak terbatas atau tidak terprediksi. Menahannya di dalam transaksi akan memperpanjang durasi pemegangan Database Locks (*Lock Hold Time*), menghabiskan connection pool, dan menyebabkan antrean blocking / lock wait timeout massal pada transaksi lain.

3. **Apa fungsi dari klausa SQL `FOR UPDATE SKIP LOCKED`?**
   * *Jawaban:* Klausa ini menginstruksikan engine database untuk mengunci baris yang tersedia dan secara otomatis melompati/mengabaikan baris yang sedang dikunci oleh transaksi lain, tanpa memblokir atau menunggu pelepasan lock. Ini adalah pola dasar untuk membangun concurrent message queues berbasis tabel relasional.

4. **Mengapa kita tidak boleh mengandalkan `PDO::ATTR_PERSISTENT => true` secara sembarangan di PHP-FPM?**
   * *Jawaban:* Karena koneksi persisten dipertahankan lintas request HTTP. Jika request sebelumnya mengalami fatal error atau unhandled exception di tengah transaksi, status koneksi (transaksi yang menggantung, session variable yang termutasi, temporary tables) dapat bocor ke request pengguna berikutnya.

5. **Apa yang dijamin oleh sifat *Atomicity* dalam prinsip ACID?**
   * *Jawaban:* Menjamin bahwa seluruh rangkaian operasi mutasi data dalam satu unit transaksi harus dieksekusi secara tuntas seluruhnya (*all*), atau jika terjadi satu kegagalan, seluruh modifikasi dibatalkan tanpa jejak (*nothing*).

---

#### Kuis Tingkat Menengah (Intermediate)

6. **Bagaimana anomali *Write Skew* dapat terjadi pada Isolation Level Snapshot Isolation (Repeatable Read)? Berikan satu contoh konkret.**
   * *Jawaban:* Write Skew terjadi ketika dua transaksi membaca data set yang sama, memeriksa invariansi bersama yang valid, tetapi melakukan modifikasi pada baris yang *berbeda* sehingga merusak invariansi global ketika keduanya commit. Contoh: Dua dokter jaga bersamaan meminta cuti. Kedua transaksi memeriksa `SELECT count(*) FROM on_call_doctors` (hasil: 2). Keduanya menyetujui penghapusan data jaga dokter masing-masing karena mengira dokter lain tetap berjaga. Hasil akhir: 0 dokter jaga.

7. **Mengapa pengurutan ID secara deterministik (*Deterministic Lock Ordering*) dapat menjamin terhindarnya Circular Deadlock pada Two-Phase Locking?**
   * *Jawaban:* Circular Deadlock membutuhkan kondisi mutual waiting yang membentuk siklus ($T_1 \rightarrow T_2 \rightarrow T_1$). Dengan memaksa semua transaksi meminta lock berdasarkan urutan monotonik yang sama (misal: ID terkecil ke terbesar), ketergantungan siklis menjadi mustahil terbentuk karena tidak ada transaksi yang dapat meminta resource bernilai lebih rendah jika ia sudah memegang resource bernilai lebih tinggi.

8. **Jelaskan cara kerja *Gap Lock* pada MySQL InnoDB dan bagaimana gap lock bisa memicu deadlock saat dua transaksi melakukan `INSERT` konkuren!**
   * *Jawaban:* Gap Lock mengunci interval/ruang kosong di antara indeks, bukan baris fisiknya. Jika dua transaksi sama-sama memasang Gap Lock pada interval yang sama (Gap Lock kompatibel antar shared/exclusive), lalu kedua transaksi mencoba melakukan `INSERT` ke dalam gap tersebut, kedua transaksi akan saling menunggu pelepasan Gap Lock satu sama lain untuk mengubahnya menjadi Insert Intention Lock, yang berujung pada Deadlock seketika.

9. **Apa keuntungan arsitektur *Unit of Work* dibandingkan pendekatan *Active Record `$model->save()`* tradisional dalam konteks efisiensi koneksi dan lock duration?**
   * *Jawaban:* Active Record melakukan update seketika saat `$model->save()` dipanggil, menahan lock baris sepanjang eksekusi script PHP. Unit of Work menunda seluruh operasi I/O database, mengumpulkan seluruh perubahan di memori (Change Tracking), menghitung urutan paling optimal, membuka transaksi fisik, melakukan *batch write* instan, dan melakukan commit dalam hitungan milidetik di akhir siklus kerja.

10. **Mengapa penambahan random jitter wajib diterapkan pada algoritma *Exponential Backoff Retry* saat menangani deadlock transaksi?**
    * *Jawaban:* Tanpa jitter, transaksi-transaksi yang bertabrakan akan menghitung durasi tunggu yang persis sama ($Base \times 2^1, Base \times 2^2$). Akibatnya, mereka akan bangun secara serentak dan kembali mengakses baris yang sama persis di momen yang sama (*Lock Collision Synchronization*). Jitter memecah keserentakan ini dengan menambahkan variasi acak pada waktu tunda.

---

### SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

#### Judul Proyek: "High-Concurrency Real-Time Auction Bidding & Escrow Settlement Engine"

#### Deskripsi Spesifikasi Proyek:
Anda diminta merancang subsistem lelang barang mewah (*Real-Time Luxury Auction Engine*) yang mampu menangani ribuan penawaran harga (*bids*) per detik untuk satu barang lelang, dengan aturan finansial yang ketat:

1. **Persyaratan Fungsional:**
   * **Domain Entity:** `AuctionItem`, `Bidder`, `EscrowWallet`, `BidHistory`.
   * **Escrow Hold Mechanism:** Saat bidder menempatkan tawaran (*bid*):
     * Saldo bidder harus dikunci/ditahan (*hold*) di dompet escrow sebesar nilai bid.
     * Jika bidder sebelumnya terkalahkan (*outbid*), saldo hold milik bidder sebelumnya harus secara otomatis dilepas dan dikembalikan (*refund*) ke saldo aktifnya.
     * Nilai bid baru harus lebih tinggi minimal 5% dari nilai *current highest bid*.
   * **Auction Closure Settle:** Saat lelang selesai:
     * Dana escrow dari highest bidder dialihkan permanen ke dompet pelelang (*seller*).
     * Kepemilikan barang dipindahkan secara atomik.

2. **Persyaratan Teknis & Arsitektur:**
   * Menggunakan PHP 8.2+ dengan `declare(strict_types=1);`.
   * Tidak boleh menggunakan framework apa pun (Pure Native PHP dengan PDO).
   * Implementasikan **Optimistic Concurrency Control (OCC)** pada entity `AuctionItem` untuk menangani bids masuk, ATAU gunakan **Pessimistic Locking dengan Retry Handler**.
   * Wajib menyertakan skrip simulasi konkurensi (menggunakan `pcntl_fork` atau multi-process CLI script) yang membuktikan bahwa sistem dijalankan oleh 20 worker simultan:
     * **Tidak terjadi over-allocation saldo escrow.**
     * **Highest bid selalu konsisten dan tidak pernah ada penawaran lebih rendah yang menimpa penawaran lebih tinggi.**
     * **Ledger saldo debit-kredit tetap imbang ($\sum \text{Balance} = \text{Initial}$).**

#### Kriteria Keberhasilan Verifikasi:
* Skrip stress-test memunculkan zero unhandled fatal exceptions.
* Seluruh serialization failure / deadlock ditangani oleh middleware retry dengan logging transparan.
* Verifikasi integritas ledger double-entry membuktikan 100% konsistensi balance setelah 500 penawaran konkuren selesai diproses.