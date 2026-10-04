# Kurikulum Enterprise Rekayasa Perangkat Lunak: PHP Modern
## Kategori: 02-Programming-Languages
### BAB-05: Enterprise Database Persistence & Concurrency
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Senior Software Engineer / Technical Architect diharapkan mampu:
1. **Mendiagnosis dan Mengeliminasi Race Conditions**: Menguasai manajemen konkurensi tingkat lanjut menggunakan *Optimistic Locking* (CAS pattern) dan *Pessimistic Locking* (`SELECT ... FOR UPDATE`, `SKIP LOCKED`, `NOWAIT`) pada mesin basis data relasional tingkat tinggi (PostgreSQL / MySQL InnoDB).
2. **Merancang Mekanisme Transaksi Berdaya Tahan Tinggi**: Mengimplementasikan *Deadlock Detection and Resilience Engine* di lapisan aplikasi PHP dengan algoritma *Exponential Backoff and Full Jitter*.
3. **Mengisolasi Multi-Tenancy Persistence**: Membangun arsitektur persistensi *multi-tenant* enterprise (*Database-per-tenant*, *Schema-per-tenant*, dan *Shared Schema with Row-Level Security*) yang aman, adaptif, dan terisolasi secara kriptografis serta logis.
4. **Mengelola Connection Lifecycle pada Runtimes Asinkron**: Mengoptimalkan siklus hidup koneksi basis data pada runtime persisten (RoadRunner, FrankenPHP, Swoole) versus stateless (PHP-FPM), mencegah *connection leak*, *transaction contamination*, dan *stale state*.
5. **Menerapkan Distributed Saga Orchestration**: Mengabstraksikan persistensi transaksi lintas batas bounded-context menggunakan orkestrasi Saga lokal berbasis *Outbox Pattern*.

---

### 2. Prerequisite
Sebelum mendalami modul ini, engineer harus memiliki pemahaman mendalam tentang:
* **PHP 8.2+**: *Strict typing*, *Attribute reflections*, *Enums*, *Readonly classes*, *Fibers*, dan penanganan *Exceptions*.
* **RDBMS Internals**: Mekanisme Multi-Version Concurrency Control (MVCC), Write-Ahead Logging (WAL), Buffer Pool, dan implementasi B-Tree Locking.
* **SQL Standard & Engine Quirks**: Transaction Isolation Levels (`READ UNCOMMITTED`, `READ COMMITTED`, `REPEATABLE READ`, `SERIALIZABLE`), fenomena anomali data (*Dirty Read*, *Non-repeatable Read*, *Phantom Read*, *Write Skew*).
* **Linux Networking & Socket Management**: Unix Domain Sockets vs TCP/IP Sockets, port exhaustion, SO_REUSEPORT, dan connection pooling (e.g., PgBouncer, ProxySQL).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Concurrency Mechanics & MVCC Under the Hood
Basis data relasional modern seperti PostgreSQL dan MySQL InnoDB tidak sekadar mengunci baris saat operasi baca dilakukan; mereka memanfaatkan **Multi-Version Concurrency Control (MVCC)**.

```
                    ┌───────────────────────────────────────────────┐
                    │               PostgreSQL / MySQL              │
                    │               Storage Engine                  │
                    └──────────────────────┬────────────────────────┘
                                           │
            ┌──────────────────────────────┴──────────────────────────────┐
            ▼                                                             ▼
┌───────────────────────────────┐                             ┌───────────────────────────────┐
│           PESSIMISTIC         │                             │          OPTIMISTIC           │
│   (Lock-Based Concurrency)    │                             │       (MVCC / CAS Flow)       │
├───────────────────────────────┤                             ├───────────────────────────────┤
│ • Strict Locking (X-Lock/S)   │                             │ • No read locks acquired      │
│ • Block on conflict           │                             │ • Check version at commit/upd │
│ • High Contention, Fast Write │                             │ • Low Contention, Fast Reads  │
│ • Risk: Deadlocks             │                             │ • Risk: High Abort/Retry Rate │
└───────────────────────────────┘                             └───────────────────────────────┘
```

* **Pessimistic Locking**: Menggunakan lock fisik pada storage engine.
  * `FOR UPDATE` (Exclusive Lock / X-Lock): Menahan baris dari pembacaan pengunci lain dan penulisan pengunci lain hingga transaksi selesai (`COMMIT` atau `ROLLBACK`).
  * `FOR SHARE` (Shared Lock / S-Lock): Memperbolehkan transaksi lain membaca data, namun mencegah modifikasi data tersebut hingga semua S-lock dilepas.
  * `NOWAIT`: Menginstruksikan RDBMS untuk langsung melempar error (`SQLSTATE 55P03` di PG atau `1205` di MySQL) jika baris terkunci, alih-alih mengantre.
  * `SKIP LOCKED`: Melewati baris yang terkunci dari *result-set*. Ini merupakan fondasi primitif berkinerja tinggi untuk implementasi *Database-backed Message Queue / Worker Engine*.
* **Optimistic Locking**: Tidak ada *lock* eksplisit pada level RDBMS saat membaca. Sebagai gantinya, baris memuat atribut versioning (`version INT` atau `updated_at TIMESTAMP(6)`). Modifikasi dilakukan secara atomik menggunakan instruksi *Compare-And-Swap (CAS)*:
  ```sql
  UPDATE accounts 
  SET balance = balance - 100, version = version + 1 
  WHERE id = 'acc-123' AND version = 4;
  ```
  Jika *affected rows* bernilai 0, telah terjadi modifikasi konkuren (*lost update prevention*), dan PHP wajib menangani kondisi ini melalui *Application-level Retry* atau *Abort*.

#### B. Isolation Levels dan Write Skew Anomaly
Pada tingkat isolasi `REPEATABLE READ`, MVCC mengambil *snapshot* data pada awal transaksi (Postgres) atau pada instruksi `SELECT` pertama (MySQL). Hal ini mencegah *Non-repeatable Read*, tetapi membuka celah **Write Skew**:
Dua transaksi paralel memeriksa kondisi bisnis global (misal: "Setidaknya harus ada 1 dokter yang berjaga di rumah sakit").
* Transaksi A mengecek ada 2 dokter. Transaksi A menonaktifkan Dokter 1.
* Transaksi B mengecek ada 2 dokter. Transaksi B menonaktifkan Dokter 2.
* Hasil akhir: 0 dokter berjaga. Tidak ada *dirty write*, tidak ada baris tumpang tindih yang diupdate secara langsung, namun konsistensi logis runtuh. 
Solusi enterprise: Menggunakan `SERIALIZABLE` isolation level dengan *predicate locks* (PostgreSQL SSI - Serializable Snapshot Isolation) atau melakukan eskalasi ke *Pessimistic Locking* secara eksplisit (`FOR UPDATE`).

#### C. Connection Lifecycle: PHP-FPM vs Application Runtimes (RoadRunner/FrankenPHP)
* **PHP-FPM**: Bersifat *Share-Nothing Architecture*. Setiap *request* memicu instansiasi objek koneksi PDO baru atau menggunakan `PDO::ATTR_PERSISTENT`. Pada koneksi persisten FPM, terdapat risiko fatal: jika suatu *request* mengalami *fatal error* di tengah transaksi yang terbuka (`BEGIN TRANSACTION`), koneksi tersebut kembali ke pool FPM dalam status *transaction active*, mengontaminasi *request* berikutnya.
* **Worker-Based Runtimes (RoadRunner, FrankenPHP, Swoole)**: Aplikasi PHP berada di memori secara permanen (*long-running process*). Objek `PDO` atau database proxy dipertahankan lintas ribuan *request*. Masalah yang muncul bergeser ke:
  1. *Stale Connection*: Server DB memutus socket akibat *idle timeout* (`wait_timeout`).
  2. *Connection State Leaks*: Transaksi yang tidak ter-rollback saat terjadi *uncaught exception*, manipulasi *session variables* (`SET timezone`), atau temporary tables.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Architecture Standard |
| :--- | :--- | :--- |
| **Concurrency Control** | Blind `UPDATE` tanpa validasi state; asumsi transaksi ACID menyelesaikan seluruh race condition. | Kombinasi *Optimistic CAS* untuk skenario baca-tinggi dan *Pessimistic SKIP LOCKED/NOWAIT* untuk ledger keuangan & antrean. |
| **Deadlock Handling** | Aplikasi melempar HTTP 500 saat database mengembalikan `SQLSTATE[40001]`. | Transaksi dibungkus dalam *Deadlock Resilient Execution Pipeline* dengan *Exponential Backoff* dan *Jitter*. |
| **Multi-Tenancy** | Single database dengan `WHERE tenant_id = ?` manual, rentan terhadap insiden kebocoran data antar-tenant (*Data Bleed*). | Skema *Tenant-Aware Session Resolver* dengan integrasi native *PostgreSQL Row-Level Security (RLS)* atau *Dynamic Multi-Database Switching*. |
| **Koneksi Transaksi** | `setAutoCommit(true)` secara default, transaksi dibuka terlalu dini sebelum komputasi berat. | Prinsip *Short-Lived Transaction Boundaries*; koneksi didapat sesaat sebelum mutasi, dan dilepas instan pasca *Commit*. |

---

### 5. How (Workflow Detail)

```
[Inisiasi Mutasi Data]
         │
         ▼
[Pilih Strategi Konkurensi]
         │
         ├───────────────────────────────┐
         ▼                               ▼
[Pessimistic Path]              [Optimistic Path]
         │                               │
         │ Acquire Transaction           │ Baca Entitas & Ambil Current Version
         │ Run SELECT ... FOR UPDATE     │ Komputasi State Baru di PHP Memory
         │ (Optional: NOWAIT)            │ Lakukan UPDATE ... WHERE version = :old
         │ Validasi State & Update       │ Cek Affected Rows
         │ Commit                        │   ├── Rows == 1: Berhasil, Commit
         │                               │   └── Rows == 0: Throw ConcurrentModificationException
         │                               │                     │
         │                               │                     ▼
         │                        [Deadlock / Concurrency Handler]
         │                               │
         ▼                               │ Hitung Backoff: (2^attempt * 100ms) + rand(0, 50ms)
[Terjadi Deadlock (SQLSTATE 40001)?]     │ Cek Max Retries
         │                               │
         ├── YA ──> Abort & Rollback ────┘
         └── TIDAK ──> Complete
```

Workflow mitigasi kegagalan transaksi konkuren:
1. **Identifikasi Konteks Bisnis**:
   * *High-contention, Low-latency* (contoh: Penjualan Tiket Flash Sale): Gunakan *Pessimistic Locking with Timeout/NOWAIT* atau Redis Pre-decrementing.
   * *Low-contention, Collaborative-editing* (contoh: Master Data, CMS, Dokumen Kebijakan): Gunakan *Optimistic Locking*.
2. **Eksekusi Blok Transaksi**: Jalankan logika dalam closure transaksional yang terisolasi.
3. **Deteksi Error State Database**: Periksa `PDOException->getCode()` atau `errorInfo[0]`.
   * Postgres: `40001` (*serialization_failure*), `40P01` (*deadlock_detected*), `55P03` (*lock_not_available*).
   * MySQL: `40001` (Deadlock / ER_LOCK_DEADLOCK 1213), `HY000` (ER_LOCK_WAIT_TIMEOUT 1205).
4. **Resilience Action**: Rollback transaksi secara instan untuk melepaskan seluruh kunci parsial pada RDBMS, tunda thread selama interval jittered, lalu ulangi closure hingga batas *max retries*.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konkurensi: Peminjaman Arsip Fisik Rahasia
* **Pessimistic Locking**: Seorang petugas masuk ke ruang arsip, mengambil dokumen, lalu **mengunci pintu ruang arsip dari dalam**. Petugas lain yang ingin mengakses dokumen harus berbaris di luar sampai petugas pertama selesai dan membuka pintu. Jika petugas membawa gembok dengan opsi `NOWAIT`, petugas lain yang mencoba membuka pintu dan mendapatinya terkunci akan langsung pergi tanpa menunggu.
* **Optimistic Locking**: Arsip bebas diakses. Petugas memfotokopi dokumen yang memiliki cap **"Revisi 12"**. Petugas keluar ke mejanya untuk melakukan revisi. Saat kembali menyerahkan perubahan, petugas memeriksa apakah cap dokumen asli masih "Revisi 12". Jika rekan lain telah memasukkan "Revisi 13", revisi petugas pertama **ditolak**. Petugas harus memfotokopi ulang Revisi 13 dan mengulang pekerjaannya.

#### Arsitektur Persistensi Multi-Tenant Enterprise

```
                                  Client Request
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │   Tenant Context Resolver   │
                         │ (Subdomain / JWT / Header)  │
                         └──────────────┬──────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
             [Schema-Per-Tenant Path]        [Shared-RLS Path]
                         │                             │
                         ▼                             ▼
           SET search_path TO tenant_a;     SET LOCAL app.current_tenant = 't_123';
                         │                             │
                         ▼                             ▼
           ┌───────────────────────────┐ ┌───────────────────────────┐
           │ PostgreSQL (Tenant Schema)│ │ PostgreSQL Table with RLS │
           │  ┌─────────────────────┐  │ │  ┌─────────────────────┐  │
           │  │ schema: tenant_a    │  │ │  │ WHERE tenant_id =   │  │
           │  │ table: orders       │  │ │  │ CURRENT_SETTING(...)│  │
           │  └─────────────────────┘  │ │  └─────────────────────┘  │
           └───────────────────────────┘ └───────────────────────────┘
```

---

### 7. Practical Implementation (Enterprise Standard)

Berikut adalah implementasi *Concurrency & Transaction Manager* berstandar enterprise dengan kemampuan penanganan *Deadlock Recovery*, *Optimistic Locking*, dan *Pessimistic Orchestration* menggunakan PHP 8.3.

#### Core Engine Implementation

```php
<?php

declare(strict_types=1);

namespace Enterprise\Persistence\Concurrency;

use PDO;
use PDOException;
use Throwable;
use Closure;
use Psr\Log\LoggerInterface;

final readonly class DeadlockException extends \RuntimeException {}
final readonly class OptimisticLockException extends \RuntimeException {}

enum LockMode
{
    case PESSIMISTIC_WRITE;
    case PESSIMISTIC_READ;
    case PESSIMISTIC_WRITE_NOWAIT;
    case PESSIMISTIC_WRITE_SKIP_LOCKED;
    case NONE;

    public function toSql(string $driver = 'pgsql'): string
    {
        return match ($this) {
            self::PESSIMISTIC_WRITE => 'FOR UPDATE',
            self::PESSIMISTIC_READ => $driver === 'pgsql' ? 'FOR SHARE' : 'LOCK IN SHARE MODE',
            self::PESSIMISTIC_WRITE_NOWAIT => 'FOR UPDATE NOWAIT',
            self::PESSIMISTIC_WRITE_SKIP_LOCKED => 'FOR UPDATE SKIP LOCKED',
            self::NONE => '',
        };
    }
}

final class TransactionManager
{
    private const int MAX_RETRIES = 5;
    private const int BASE_BACKOFF_MS = 50;

    public function __construct(
        private PDO $connection,
        private ?LoggerInterface $logger = null
    ) {
        // Pastikan PDO diatur ke Exception mode
        $this->connection->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    }

    /**
     * Menjalankan operasi dalam transaksi dengan algoritma Retry Exponential Backoff + Jitter
     * untuk menangani transient error (Deadlocks / Serialization Failure).
     *
     * @template T
     * @param Closure(PDO): T $operation
     * @return T
     * @throws Throwable
     */
    public function executeTransactional(Closure $operation, string $isolationLevel = 'READ COMMITTED'): mixed
    {
        $attempts = 0;

        while (true) {
            $attempts++;
            try {
                if ($this->connection->inTransaction()) {
                    return $operation($this->connection);
                }

                $this->connection->exec("SET TRANSACTION ISOLATION LEVEL {$isolationLevel}");
                $this->connection->beginTransaction();

                $result = $operation($this->connection);

                $this->connection->commit();
                return $result;
            } catch (Throwable $e) {
                if ($this->connection->inTransaction()) {
                    try {
                        $this->connection->rollBack();
                    } catch (PDOException $rbException) {
                        $this->logger?->critical('Gagal melakukan rollback transaksi', [
                            'exception' => $rbException,
                            'original_exception' => $e
                        ]);
                    }
                }

                if ($this->isDeadlockOrSerializationFailure($e) && $attempts < self::MAX_RETRIES) {
                    $this->logger?->warning("Terdeteksi deadlock/konflik serialisasi. Upaya percobaan ulang {$attempts}...", [
                        'attempt' => $attempts,
                        'error_code' => $e->getCode(),
                        'message' => $e->getMessage()
                    ]);

                    $this->applyBackoffWithJitter($attempts);
                    continue;
                }

                throw $e;
            }
        }
    }

    private function isDeadlockOrSerializationFailure(Throwable $e): bool
    {
        if (!$e instanceof PDOException) {
            return false;
        }

        $sqlState = (string)$e->getCode();
        $errorCode = $e->errorInfo[1] ?? 0;

        // PostgreSQL: 40001 (serialization_failure), 40P01 (deadlock_detected), 55P03 (lock_not_available)
        // MySQL: 40001 (ER_LOCK_DEADLOCK 1213), HY000 (ER_LOCK_WAIT_TIMEOUT 1205)
        return in_array($sqlState, ['40001', '40P01', '55P03'], true) 
            || $errorCode === 1213 
            || $errorCode === 1205;
    }

    private function applyBackoffWithJitter(int $attempt): void
    {
        // Exponential backoff: base * 2^(attempt-1)
        $backoffMs = self::BASE_BACKOFF_MS * (2 ** ($attempt - 1));
        // Full jitter: random between 0 and backoffMs
        $jitterMs = random_int(0, (int) $backoffMs);
        $totalSleepUs = (int) (($backoffMs + $jitterMs) * 1000);

        usleep($totalSleepUs);
    }
}
```

#### Production-Grade Repository Implementasi Optimistic & Pessimistic Locking

```php
<?php

declare(strict_types=1);

namespace Enterprise\Persistence\Repository;

use Enterprise\Persistence\Concurrency\DeadlockException;
use Enterprise\Persistence\Concurrency\LockMode;
use Enterprise\Persistence\Concurrency\OptimisticLockException;
use PDO;
use RuntimeException;

final readonly class AccountBalance
{
    public function __construct(
        public string $accountId,
        public int $balanceInCents,
        public int $version
    ) {}
}

final class AccountLedgerRepository
{
    public function __construct(
        private PDO $db
    ) {}

    /**
     * Membaca akun dengan Pessimistic Lock
     */
    public function findByIdForUpdate(string $accountId, LockMode $lockMode = LockMode::PESSIMISTIC_WRITE): ?AccountBalance
    {
        $driver = (string)$this->db->getAttribute(PDO::ATTR_DRIVER_NAME);
        $lockSql = $lockMode->toSql($driver);

        $stmt = $this->db->prepare("
            SELECT id, balance_cents, version 
            FROM account_ledgers 
            WHERE id = :id 
            {$lockSql}
        ");

        $stmt->execute(['id' => $accountId]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            return null;
        }

        return new AccountBalance(
            accountId: (string)$row['id'],
            balanceInCents: (int)$row['balance_cents'],
            version: (int)$row['version']
        );
    }

    /**
     * Mutasi akun dengan Pessimistic Lock (Safe Direct Update)
     */
    public function updateBalancePessimistic(string $accountId, int $amountDeltaInCents): void
    {
        $stmt = $this->db->prepare("
            UPDATE account_ledgers 
            SET balance_cents = balance_cents + :delta,
                updated_at = CURRENT_TIMESTAMP(6)
            WHERE id = :id
        ");

        $executed = $stmt->execute([
            'delta' => $amountDeltaInCents,
            'id' => $accountId
        ]);

        if (!$executed || $stmt->rowCount() === 0) {
            throw new RuntimeException("Gagal melakukan pembaruan saldo akun: {$accountId}");
        }
    }

    /**
     * Mutasi akun menggunakan Optimistic Locking (Compare-And-Swap)
     */
    public function updateBalanceOptimistic(AccountBalance $account, int $newBalanceInCents): void
    {
        $stmt = $this->db->prepare("
            UPDATE account_ledgers 
            SET balance_cents = :new_balance,
                version = version + 1,
                updated_at = CURRENT_TIMESTAMP(6)
            WHERE id = :id AND version = :expected_version
        ");

        $stmt->execute([
            'new_balance' => $newBalanceInCents,
            'id' => $account->accountId,
            'expected_version' => $account->version
        ]);

        if ($stmt->rowCount() === 0) {
            throw new OptimisticLockException(
                "Konflik konkurensi terdeteksi pada akun [{$account->accountId}]. " .
                "State telah dimodifikasi oleh transaksi paralel. Version target: {$account->version}"
            );
        }
    }
}
```

#### Penggunaan Komposisi pada Service Layer

```php
<?php

declare(strict_types=1);

namespace Enterprise\Persistence\Service;

use Enterprise\Persistence\Concurrency\TransactionManager;
use Enterprise\Persistence\Concurrency\LockMode;
use Enterprise\Persistence\Repository\AccountLedgerRepository;
use InvalidArgumentException;
use Psr\Log\LoggerInterface;

final readonly class TransferService
{
    public function __construct(
        private TransactionManager $txManager,
        private AccountLedgerRepository $ledgerRepo,
        private LoggerInterface $logger
    ) {}

    public function transferPessimistic(string $fromAccountId, string $toAccountId, int $amountInCents): void
    {
        if ($amountInCents <= 0) {
            throw new InvalidArgumentException("Nominal transfer harus positif");
        }

        // PENTING: Mencegah Deadlock akibat Cyclic Lock Wait
        // Selalu urutkan penguncian ID sumber daya secara deterministik (Alphabetical Ordering)
        $locks = [$fromAccountId, $toAccountId];
        sort($locks, SORT_STRING);

        $this->txManager->executeTransactional(function () use ($fromAccountId, $toAccountId, $amountInCents, $locks): void {
            // Lock entitas sesuai urutan leksikografis
            $accounts = [];
            foreach ($locks as $id) {
                $acc = $this->ledgerRepo->findByIdForUpdate($id, LockMode::PESSIMISTIC_WRITE);
                if ($acc === null) {
                    throw new InvalidArgumentException("Akun {$id} tidak ditemukan");
                }
                $accounts[$id] = $acc;
            }

            $sourceAccount = $accounts[$fromAccountId];
            if ($sourceAccount->balanceInCents < $amountInCents) {
                throw new InvalidArgumentException("Saldo akun {$fromAccountId} tidak mencukupi");
            }

            // Eksekusi mutasi
            $this->ledgerRepo->updateBalancePessimistic($fromAccountId, -$amountInCents);
            $this->ledgerRepo->updateBalancePessimistic($toAccountId, $amountInCents);

            $this->logger->info("Transfer {$amountInCents} cents dari {$fromAccountId} ke {$toAccountId} berhasil.");
        });
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus Produksi: Flash Sale & Double-Spending Ledger Engine
* **Konteks**: Platform e-commerce fintech memproses kampanye flash sale untuk unit inventaris terbatas (500 unit smartphone premium) dengan 15.000 konkurensi *request* checkout per detik (RPS).
* **Insiden**: Terjadi overselling (terjual 548 unit dari 500 unit) dan puluhan *database deadlock crash* saat menggunakan transaksi konvensional:
  ```sql
  -- IMPLEMENTASI CACAT SEBELUMNYA
  SELECT stock FROM products WHERE id = 1; -- PHP mengecek stock > 0
  UPDATE products SET stock = stock - 1 WHERE id = 1;
  ```
* **Akar Masalah**:
  1. *Race Condition*: Ribuan proses membaca nilai `stock` yang sama sebelum salah satu proses berhasil menuliskan `stock - 1`.
  2. *Contention Bottleneck*: Penggunaan `SELECT ... FOR UPDATE` tunggal di baris produk menyebabkan barisan antrean *lock wait* yang melebihi batas koneksi pool PostgreSQL, mengakibatkan *cascading connection starvation*.
* **Solusi Arsitektur Enterprise**:
  1. **Two-Phase Inventory Reservation**:
     Memisahkan pencatatan agregat inventaris dari baris tunggal menggunakan teknik **Inventory Bucket Sharding** atau langsung memanfaatkan **Atomic Decrement with Floor Assertion**:
     ```sql
     UPDATE inventory 
     SET reserved = reserved + 1 
     WHERE product_id = :id AND (total - reserved) >= 1;
     ```
  2. **Worker Processing dengan `FOR UPDATE SKIP LOCKED`**:
     Jika menggunakan *reservation queue* berbasis RDBMS, pesanan di-buffer ke dalam tabel antrean. Kumpulan *PHP daemon worker* (menggunakan RoadRunner) menarik task tanpa mengalami blokade:
     ```sql
     SELECT order_id FROM pending_orders 
     WHERE status = 'QUEUED' 
     ORDER BY created_at ASC 
     LIMIT 50 
     FOR UPDATE SKIP LOCKED;
     ```
* **Hasil**:
  * Tingkat keberhasilan mutasi inventaris 100% akurat (tepat 500 unit).
  * Error rate akibat deadlock turun dari 8.4% menjadi **0.00%**.
  * Latensi rata-rata p99 turun dari 4.2 detik menjadi 118 milidetik.

---

### 9. Trade-offs

| Dimensi | Optimistic Locking | Pessimistic Locking | Row-Level Security (RLS) | Separate Schema Per Tenant |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput (High Contention)** | **Buruk**: Tingkat kegagalan abort/retry melonjak drastis, membuang resource CPU. | **Tinggi (Terkendali)**: Menahan thread, namun menjamin eksekusi urut tanpa komputasi ulang sia-sia. | **Tinggi**: Overhead parser filter query sangat minimal (< 3%). | **Sangat Tinggi**: Isolasi fisik buffer pool di RDBMS berjalan optimal. |
| **Throughput (Low Contention)** | **Sangat Tinggi**: Nol overhead penguncian RDBMS, performa baca MVCC murni. | **Sedang**: Tetap terjadi overhead akuisisi lock dan pencatatan lock-table engine. | **Tinggi**: Tetap konsisten. | **Tinggi**. |
| **Deadlock Risk** | **Nol Mutlak**: Tidak ada lock yang ditahan silang di RDBMS. | **Tinggi**: Berisiko fatal jika urutan akuisisi lock di kode aplikasi tidak seragam. | Tidak berpengaruh langsung. | Tidak berpengaruh langsung. |
| **Database Cost & Ops** | Rendah: Skema sederhana, kompatibel dengan segala arsitektur DB. | Rendah - Sedang: Membutuhkan *connection-pooler* (PgBouncer) yang presisi. | Rendah: Maintenance single schema migration. | **Sangat Tinggi**: Biaya migrasi skema per tenant, DDL bottleneck saat tenant berjumlah ribuan. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Long-Running Transaction with Locks
* **Kesalahan**: Menjalankan panggilan API pihak ketiga (misal: Payment Gateway, Webhook) atau komputasi file kriptografis di dalam blok `$txManager->executeTransactional(...)`.
* **Dampak**: X-Lock pada baris database ditahan selama ratusan milidetik atau detik, mengakibatkan connection pool RDBMS penuh, latensi merambat naik (*cascading failure*), dan memicu *Lock Wait Timeout Exceeded*.
* **Solusi**: Hanya buka transaksi database pada saat mutasi data siap dilakukan. Tarik data eksternal **sebelum** membuka transaksi.

#### 2. Cyclic Deadlock Susceptibility
* **Kesalahan**: Thread 1 mengunci Akun A lalu Akun B. Thread 2 secara bersamaan mengunci Akun B lalu Akun A.
* **Dampak**: Terjadi Deadlock instan. Engine basis data terpaksa membunuh salah satu transaksi (*Deadlock Victim*).
* **Solusi**: Normalisasi urutan lock (*Lock Ordering Pattern*). Urutkan Primary Key yang akan dikunci secara askending (`sort($ids, SORT_STRING)`) sebelum memanggil `FOR UPDATE`.

#### 3. State Pollution di Long-Running PHP Runtimes (RoadRunner/Swoole)
* **Kesalahan**: Mengubah variabel sesi koneksi SQL tanpa mengembalikannya ke nilai semula:
  ```php
  $pdo->exec("SET LOCAL app.current_tenant = 'tenant_A'");
  ```
  Pada PHP-FPM, koneksi dibersihkan pada akhir request jika tidak persisten. Pada Swoole/RoadRunner, koneksi diambil oleh request berikutnya milik `tenant_B`, yang langsung mewarisi context `tenant_A` jika terjadi kegagalan sanitasi.
* **Solusi**: Selalu gunakan `DISCARD ALL` (PostgreSQL) saat mengembalikan koneksi ke pool, atau bungkus pengaturan variabel sesi dalam blok `try ... finally` menggunakan transaksi lokal (`SET LOCAL`).

---

### 11. Best Practices (Production Checklist)

- [ ] **Transaction Execution Boundary**: Pastikan waktu eksekusi di dalam transaksi RDBMS tidak melebihi **50ms**.
- [ ] **Strict Lock Ordering**: Seluruh pemanggilan multi-row pessimistic lock telah diurutkan secara deterministik menggunakan string sorting pada ID unik.
- [ ] **Deadlock Recovery Engine**: Seluruh transaksi vital enterprise wajib dibungkus pipeline retry transaksional dengan batasan maksimum percobaan (3-5 kali) dan jittered sleep.
- [ ] **Explicit Isolation Level**: Jangan berasumsi isolasi default database selalu aman. Deklarasikan secara eksplisit (`READ COMMITTED` atau `REPEATABLE READ`) sesuai skenario bisnis.
- [ ] **Skip Locked for Queues**: Hapus operasi polling tabel `UPDATE orders SET status = 'PROCESSING' WHERE id = (SELECT id FROM ...)` yang memicu full scan lock. Gantikan dengan pattern `SELECT ... FOR UPDATE SKIP LOCKED`.
- [ ] **Optimistic Version Guard**: Pastikan kolom penanda versi (*version increment*) dilindungi constraint database (`CHECK (version >= 0)`) dan diikutsertakan dalam klausa `WHERE`.
- [ ] **Safe Schema Switching**: Pada implementasi Multi-Tenant Schema-per-tenant, gunakan fungsi sanitasi ketat untuk identifier nama skema guna mencegah *SQL Injection via Schema Name*:
  ```php
  $safeSchema = preg_replace('/[^a-zA-Z0-9_]/', '', $tenantSchema);
  $pdo->exec(sprintf('SET search_path TO %s', $safeSchema));
  ```

---

### 12. Hands-on Practice
Bangun struktur direktori berikut di environment development Anda:

```bash
mkdir -p hands-on/m02/src hands-on/m02/tests
cd hands-on/m02
composer init --no-interaction --name="enterprise/persistence-concurrency" --autoload="src/"
composer require monolog/monolog
```

#### File: `hands-on/m02/src/TenantContext.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\Persistence;

use RuntimeException;

final class TenantContext
{
    private static ?string $currentTenantId = null;

    public static function setTenantId(string $tenantId): void
    {
        if (!preg_match('/^[a-z0-9_]+$/', $tenantId)) {
            throw new RuntimeException("Format Identifier Tenant Tidak Valid: {$tenantId}");
        }
        self::$currentTenantId = $tenantId;
    }

    public static function getTenantId(): string
    {
        return self::$currentTenantId ?? throw new RuntimeException("Tenant context belum diinisialisasi");
    }

    public static function clear(): void
    {
        self::$currentTenantId = null;
    }
}
```

#### File: `hands-on/m02/src/MultiTenantConnectionFactory.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\Persistence;

use PDO;

final class MultiTenantConnectionFactory
{
    public function __construct(
        private string $dsn,
        private string $username,
        private string $password
    ) {}

    public function createConnectionForTenant(string $tenantId): PDO
    {
        $pdo = new PDO($this->dsn, $this->username, $this->password, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_PERSISTENT => false
        ]);

        // Menerapkan isolasi via PostgreSQL Row-Level Security session variable
        // Menggunakan prepared statement untuk mencegah injection
        $stmt = $pdo->prepare("SET LOCAL app.current_tenant_id = :tenant_id");
        $stmt->execute(['tenant_id' => $tenantId]);

        return $pdo;
    }
}
```

#### File: `hands-on/m02/run_concurrency_test.php`
```php
<?php

declare(strict_types=1);

require_once __DIR__ . '/vendor/autoload.php';

use Enterprise\Persistence\Concurrency\TransactionManager;
use Enterprise\Persistence\Concurrency\OptimisticLockException;
use Enterprise\Persistence\Repository\AccountLedgerRepository;
use Enterprise\Persistence\Repository\AccountBalance;

// Setup SQLite In-Memory Database dengan Mode Emulasi Locking
$pdo = new PDO('sqlite::memory:');
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

$pdo->exec("
    CREATE TABLE account_ledgers (
        id TEXT PRIMARY KEY,
        balance_cents INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
    )
");

$pdo->exec("INSERT INTO account_ledgers VALUES ('ACC_01', 100000, 1, datetime('now'))");

$repo = new AccountLedgerRepository($pdo);

echo "1. Menguji Berhasilnya Optimistic Locking Mutasi Pertama...\n";
$account = new AccountBalance('ACC_01', 100000, 1);
$repo->updateBalanceOptimistic($account, 80000);
echo "Mutasi 1 Berhasil. Saldo: 80000. Version naik ke 2.\n";

echo "2. Menguji Deteksi Konflik Optimistic Locking dengan Versi Usang (Version = 1)...\n";
try {
    // Mencoba update menggunakan entity dengan snapshot versi lama (1), padahal database sudah versi (2)
    $staleAccount = new AccountBalance('ACC_01', 80000, 1);
    $repo->updateBalanceOptimistic($staleAccount, 50000);
    echo "GAGAL: Konflik konkurensi tidak terdeteksi!\n";
} catch (OptimisticLockException $e) {
    echo "SUKSES: Konflik Terdeteksi Secara Presisi!\n";
    echo "Pesan Exception: " . $e->getMessage() . "\n";
}
```

Jalankan script untuk menguji mekanisme proteksi:
```bash
php hands-on/m02/run_concurrency_test.php
```

---

### 13. Exercise

#### Level: Easy
Implementasikan method PHP pada class repository bernama `acquireLockWithTimeout(string $resourceId, int $timeoutSeconds): bool` yang mengeksekusi PostgreSQL query `SET LOCAL lock_timeout = '2s'` lalu melakukan `SELECT ... FOR UPDATE`. Tangani error jika batas timeout tercapai tanpa membuat aplikasi melempar *unhandled exception*.

#### Level: Medium
Rancang sebuah modul `DeadlockSimulator` menggunakan `pcntl_fork()` untuk melahirkan 2 child process PHP independen yang saling mengunci dua baris database dalam urutan terbalik secara konkuren. Gunakan `TransactionManager` yang telah dibangun pada Section 7 untuk membuktikan bahwa retry loop berhasil meredam kegagalan tanpa satu pun child process melempar fatal error ke shell.

#### Level: Hard
Bangun implementasi *Database-Backed Distributed Job Queue* di PHP 8.3 dengan kriteria:
1. Mengambil batch job berukuran $N$ menggunakan `SELECT id, payload FROM jobs WHERE status = 'PENDING' LIMIT :limit FOR UPDATE SKIP LOCKED`.
2. Jika worker crash, lock harus otomatis terlepas via rollback transaction.
3. Wajib memisahkan pool koneksi baca (Read Replica) dan pool koneksi tulis (Master Node) secara transparan di dalam `TransactionManager`. Jika transaksi dibuka, seluruh instruksi baca dan tulis di dalam closure dialihkan ke Master Node secara konsisten.

---

### 14. Challenge

#### Skenario: Arsitektur High-Contention Flash Sale Ticket Allocation Engine
Sebuah platform penjualan konser berskala raksasa menjual 50.000 tiket dalam waktu 3 menit. Kategori festival hanya memiliki 1 baris agregat stok tiket di PostgreSQL untuk menyederhanakan pelaporan keuangan.
Ketika 20.000 request per detik menghantam baris agregat tersebut secara paralel, terjadi fenomena:
1. *Row Lock Contention*: Antrean koneksi menunggu row-level exclusive lock membengkak hingga mencapai limit PgBouncer (max client connections exhausted).
2. Latensi API melonjak dari 15ms menjadi > 12.000ms.
3. RDBMS mengalami saturasi CPU 100% hanya untuk mengelola graf *Lock Wait Queue* dan deteksi deadlock internal.

#### Syarat Penyelesaian Arsitektur:
* **Tantangan Mutasi**: Anda dilarang keras menggunakan Redis/in-memory store untuk sumber kebenaran stok utama (State harus persisten secara ACID di RDBMS PostgreSQL untuk kepatuhan regulasi audit perbankan).
* **Target Latensi**: Wajib mempertahankan p99 response time di bawah **150 milidetik** di bawah beban konkurensi 10.000 RPS.
* **Integritas Mutasi**: Tidak boleh terjadi *negative inventory* (overselling) dan tidak boleh ada tiket yang terkunci permanen jika pengguna membatalkan checkout (*Abandoned Cart*).
* **Rancangan yang Ditagih**:
  1. Skema DDL tabel database pendukung strategi mitigasi contention (Gunakan konsep *Inventory Sharding / Ticket Bucketing*).
  2. Implementasi algoritma PHP 8.3 untuk mendistribusikan mutasi penguncian baris secara acak/merata ke dalam shard-shard baris tersebut.
  3. Mekanisme agregasi balance stok instan tanpa melakukan table lock global.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)
1. Apa perbedaan mendasar antara perilaku klausa `NOWAIT` dan `SKIP LOCKED` pada statement `SELECT ... FOR UPDATE`?
2. Mengapa isolasi level `REPEATABLE READ` pada PostgreSQL standar masih mengizinkan anomali *Write Skew* terjadi?
3. Pada runtime PHP-FPM, apa bahaya keamanan fatal yang dapat terjadi jika koneksi `PDO::ATTR_PERSISTENT => true` digunakan bersamaan dengan transaksi yang gagal di-rollback saat uncaught Exception?
4. Kapan kita wajib memprioritaskan penggunaan *Optimistic Locking* dibandingkan *Pessimistic Locking*?
5. Apa kode SQLSTATE standar ANSI yang dikembalikan oleh sebagian besar RDBMS relasional saat transaksi terpilih menjadi korban deadlock (*Deadlock Victim*)?

#### Bagian 2: Intermediate (Analisis Kasus Singkat)
6. Perhatikan kode berikut:
   ```php
   $pdo->beginTransaction();
   $stock = $pdo->query("SELECT stock FROM products WHERE id = 10 FOR UPDATE")->fetchColumn();
   $client = new \GuzzleHttp\Client();
   $response = $client->post('https://payment.external.com/charge');
   $pdo->exec("UPDATE products SET stock = stock - 1 WHERE id = 10");
   $pdo->commit();
   ```
   Sebutkan minimal 2 pelanggaran fatal arsitektur persistensi pada potongan kode di atas dan jelaskan dampak operasionalnya pada sistem produksi dengan beban 2.000 concurrent user.
7. Mengapa pengurutan akuisisi lock secara deterministik (misalnya sorting ID leksikografis) dapat mengeliminasi *Deadlock Siklik* pada operasi mutasi dua arah antar-akun?
8. Bagaimana implementasi *Row-Level Security* (RLS) di PostgreSQL bekerja sama dengan session variable untuk mencegah kebocoran data (*Data Bleed*) antar tenant pada aplikasi multi-tenant berarsitektur *Shared Database - Shared Schema*?
9. Mengapa algoritma retry deadlock wajib menyertakan komponen **Full Jitter** selain **Exponential Backoff**?
10. Pada arsitektur runtime persisten modern seperti FrankenPHP atau RoadRunner, mengapa kita tidak boleh menyimpan objek transaksi database aktif (`PDOTransaction`) di dalam static property atau singleton service?

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus A**: 
    Aplikasi core banking Anda mengalami degradasi di mana PostgreSQL melempar ribuan error: `SQLSTATE[55P03]: Lock not available: 7 ERROR: canceling statement due to lock timeout`. Setelah ditelusuri, sebuah modul laporan analitik (BI) bulanan berjalan bersamaan dengan transaksi mutasi rekening pengguna reguler. Keduanya berjalan pada isolasi default `READ COMMITTED`. Rancang solusi arsitektural di sisi konfigurasi koneksi PHP dan PostgreSQL untuk memisahkan beban kerja ini secara tuntas tanpa menambah replika database fisik baru.
12. **Skenario Kasus B**:
    Sebuah sistem lelang online mencatat penawaran harga tertinggi (*Highest Bidder*). Modul ini diimplementasikan dengan Optimistic Locking (`version`). Ketika barang lelang memasuki 10 detik terakhir, 500 penawar mengajukan harga secara hampir serentak. Tingkat penolakan transaksi (*transaction abort rate*) melonjak hingga 94%, menyebabkan pengalaman pengguna hancur karena tawaran mereka ditolak sistem meskipun harga yang diajukan lebih tinggi. Bagaimana Anda merekayasa ulang alur persistensi ini agar throughput penawaran dapat diterima secara optimal tanpa merusak integritas urutan harga?
13. **Skenario Kasus C**:
    Platform SaaS Anda menerapkan arsitektur *Schema-per-Tenant* di PostgreSQL. Ketika jumlah klien enterprise meningkat mencapai 2.500 tenant, eksekusi migrasi skema database aplikasi PHP memakan waktu 4 jam dan kerap mengalami out-of-memory. Selain itu, pool connection PgBouncer sering kehabisan memori akibat banyaknya tracking metadata catalog skema database. Bagaimana Anda mengevaluasi trade-off arsitektur ini dan langkah transformasi apa yang harus diambil untuk skala tenant berikutnya?

---

### 16. Summary

1. **Konkurensi Bukan Monolit**: Tidak ada satu mekanisme konkurensi universal. *Optimistic Locking (CAS)* ideal untuk skenario benturan rendah (*Low Contention, High Read*), sedangkan *Pessimistic Locking* (`FOR UPDATE`, `SKIP LOCKED`, `NOWAIT`) mutlak dibutuhkan untuk entitas keuangan, reservasi, dan sistem antrean.
2. **Resilience by Design**: Deadlock di basis data relasional bukanlah bug fungsional, melainkan respons alami RDBMS terhadap konflik ketergantungan siklik. Lapisan aplikasi PHP enterprise wajib mengimplementasikan pola **Self-Healing Transaction** menggunakan kombinasi *Exponential Backoff* dan *Randomized Jitter*.
3. **Deterministik Mencegah Deadlock**: Kunci utama mengeliminasi kebuntuan multi-resource lock adalah penyeragaman urutan akses data secara absolut (Deterministic Resource Ordering).
4. **Prinsip Transaksi Singkat (Short-Lived Transactions)**: Database transaction adalah sumber daya yang sangat mahal. Dilarang keras menempatkan operasi network I/O, disk I/O berat, atau parsing payload JSON masif di dalam transaction boundary database.
5. **Modern Runtime Awareness**: Peralihan dari PHP-FPM ke runtime modern berbasis worker (RoadRunner, FrankenPHP) menuntut pemahaman mendalam tentang siklus hidup socket, pembersihan state transaksional antar-request, serta mitigasi connection starvation yang berpotensi melumpuhkan keseluruhan worker pool.