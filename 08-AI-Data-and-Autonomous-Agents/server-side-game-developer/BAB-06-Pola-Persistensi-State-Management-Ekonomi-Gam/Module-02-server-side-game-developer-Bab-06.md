# Kurikulum Rekayasa Backend Game Enterprise
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB-06: Pola Persistensi, State Management, dan Ekonomi Game
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik pada tingkat *Lead/Principal Game Server Engineer* ditargetkan mampu:
*   **Menganalisis & Mengisolasi Masalah Konkurensi Kritis:** Mengidentifikasi celah eksploitasi replikasi item (*item duplication* / *dupe glitch*), pembelanjaan ganda (*double-spending*), dan anomali saldo negatif (*negative balance*) pada sistem terdistribusi berskala tinggi (>50.000 DAU bersamaan/CCU).
*   **Merancang Sistem Buku Besar Akuntansi Ganda (*Double-Entry Bookkeeping Ledger*):** Mengimplementasikan model persistensi finansial game yang *immutable*, terverifikasi secara kriptografis atau melalui relasi debit-kredit ketat dengan auditabilitas zero-loss.
*   **Mengorkestrasi Transaksi Terdistribusi Lintas Layanan:** Menerapkan pola *Saga (Orchestration-based)* dan *Two-Phase Commit (2PC)* lokal dengan penanganan *compensating transactions* untuk transaksi multi-layanan (e.g., Inventory Service, Wallet Service, Marketplace/Auction Service).
*   **Mengembangkan Pola *Write-Behind (Write-Back) Caching*:** Membangun *persistence pipeline* asinkron berbasis log dengan Redis dan Apache Kafka/Pulsar untuk memitigasi *database write bottleneck* tanpa mengorbankan durabilitas state saat terjadi *crash* pada server game (*split-brain/node failure*).
*   **Mengimplementasikan Mekanisme Konkurensi Lanjutan:** Menerapkan *Optimistic Concurrency Control* (OCC) dengan *version vector* dan *Pessimistic Locking* adaptif via Distributed Lock Manager (DLM/Redlock) untuk transaksi bursa lelang (*auction house*) berfrekuensi tinggi.

---

### 2. Prerequisite

Sebelum mempelajari materi ini, peserta diharapkan telah menguasai:
*   **Sistem Basis Data Internal:** Pemahaman mendalam tentang *Isolation Levels* SQL (Read Committed, Repeatable Read, Serializable), WAL (*Write-Ahead Logging*), serta struktur data pohon (B-Tree, LSM-Tree).
*   **Komputasi Konkurensi & Memory Model:** Goroutines/Channels (Go), Async/Await & Event Loop (Node.js/C#), Thread Safety, Mutex, CAS (*Compare-And-Swap*), dan Memory Barrier.
*   **Protokol Komunikasi Jaringan:** gRPC/Protobuf, WebSockets, dan TCP streaming dalam ekosistem *stateful game server*.
*   **Dasar Arsitektur Game Backend:** Konsep *tick rate*, *spatial partitioning*, *session affinity*, dan modul persistensi dasar (Modul 01).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Anatomi Kegagalan State Ekonomi Game
Pada game multipemain massal (MMO) atau game dengan ekonomi dinamis (Gacha, RPG, Mobile Shooters), *game state* tersebar di dua ranah utama:
1.  **Ephemeral In-Memory State:** Berada di memori proses *Dedicated Game Server* (DGS) untuk memproses logika berkecepatan tinggi (10–60 Hz).
2.  **Durable Persistent State:** Berada di klaster penyimpanan database (RDBMS, NoSQL, Cache Engines) untuk keabsahan aset bernilai nyata.

Titik rentan paling destruktif dalam arsitektur ini muncul dari diskrepansi sinkronisasi antara *in-memory mutation* dan *durable write*. Jika pemain melakukan *trade*, server mengalami crash sebelum data *write* ke database selesai, item dapat tertinggal di kedua pemain (Replikasi Item / Dupe).

```
[Attacker A] --(Trade Item)--> [Victim B]
      |                              |
[Memory DGS: Item Moved to B]        |
      |                              |
[DGS Crashes unexpectedly before DB Flush]
      |                              |
[DB Recovery: A still has Item, B also logged item reception elsewhere -> DUPE!]
```

#### Paradigma Buku Besar Berpasangan (*Double-Entry Ledger*)
Sistem game modern kelas enterprise menolak pembaruan skalar sederhana seperti `UPDATE wallets SET balance = balance + 100 WHERE user_id = 'X'`. Mutasi semacam ini tidak memiliki jejak audit (*audit trail*), rentan terhadap *lost update*, dan tidak memungkinkan rekonstruksi keadaan (*state reconstruction*).

Sistem enterprise mengadopsi prinsip akuntansi:
$$\sum \text{Debit} - \sum \text{Kredit} = 0$$

Setiap mutasi mata uang adalah transfer antar setidaknya dua akun buku besar (misalnya: dari `System:Mint_Reward` ke `User:Wallet:Gems`). Tidak ada saldo yang diciptakan tanpa sumber akun penyeimbang.

```
+----------------------------------------------------------------------------------+
|                            TRANSACTION BATCH #982341                             |
+----------------------------------------------------------------------------------+
| Entry ID | Source Account       | Destination Account  | Amount | Currency | Ref |
+----------+----------------------+----------------------+--------+----------+-----+
| TX_01    | System:World_Drop    | User:PlayerA:Gold    | +500   | GOLD     | Q-9 |
| TX_02    | User:PlayerA:Gold    | System:Tax_Sink      | -25    | GOLD     | T-1 |
| TX_03    | User:PlayerA:Gold    | User:PlayerB:Gold    | -475   | GOLD     | P2P |
+----------------------------------------------------------------------------------+
```

#### Write-Behind Log Pipeline dengan Ring-Buffer In-Memory
Untuk menangani mutasi inventaris dan gold ribuan pemain per detik tanpa menumbangkan database operasional (RDBMS), arsitektur *Write-Behind* menggunakan Redis stream atau queue berbasis Kafka dengan retensi *Memory-Mapped Files* (mmap). 

Setiap kali mutasi state divalidasi oleh *Authoritative Game Server*:
1.  State lokal di-update seketika (Latensi < 1ms).
2.  *Mutation Event* ditulis ke in-memory transactional WAL via Redis Hash & Stream.
3.  Pekerja latar belakang (*Persistence Worker Daemon*) mengonsumsi stream secara *batch-drain* dan melakukan *bulk upsert* ke basis data permanen.

```
[DGS Core Logic]
       |
  (1) Local Memory Mutation (CAS lock-free)
       |
  (2) Append to Local WAL (MMap / Redis Ring Buffer)
       |
       v
 [Persistence Bridge Worker]  <--- Backpressure Monitor
       |
  (3) Micro-batching (Interval: 100ms / Size: 1000 ops)
       |
       v
 [PostgreSQL / CockroachDB Cluster] (ACID Write-Ahead Log)
```

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Direct Database Mutex) | Pendekatan Enterprise (Event-Sourced & Double-Entry) |
| :--- | :--- | :--- |
| **Keamanan Transaksi** | `UPDATE table SET val = val - x` berisiko *race condition* dan *deadlock* masif pada *high-concurrency*. | *Immutable append-only ledger*; setiap record diverifikasi lewat serialisasi sekuensial. |
| **Resiliensi Crash** | Data *unsaved* di memori hilang seketika saat DGS crash; potensi rollback parsial atau duplikasi item. | State dapat dibangun kembali (*rehydrated*) ke detik terakhir melalui replay *Append-Only Log* (AOL). |
| **Audit & Anti-Cheat** | Hanya menyimpan nilai akhir (`current_balance`). Mustahil melacak sumber eksploitasi. | Jejak audit 100% lengkap: waktu, *session id*, *action trigger*, akun sumber, akun target, dan *hash signature*. |
| **Throughput IO** | Terhambat oleh I/O Disk Latency DB (~5-50ms per network round-trip per user). | Pemrosesan in-memory (~sub-millisecond) dengan asinkronisasi I/O batch processing (10.000+ ops/detik). |

---

### 5. How (Workflow Detail)

#### Alur Transaksi Saga Orkestratif: Pembelian Marketplace Antar Pemain (P2P Trade)
Transaksi antar-layanan (Service Inventory A $\rightarrow$ Service Escrow $\rightarrow$ Service Inventory B $\rightarrow$ Service Wallet) tidak boleh menggunakan protokol *Two-Phase Commit* (2PC) yang memblokir resource jaringan secara berkepanjangan pada skala game cloud-native. Sebagai gantinya, digunakan arsitektur **Orchestrated Saga Pattern**.

```
[Client B (Buyer)] ---> [Saga Orchestrator] <--- [Client A (Seller)]
                              |
     +------------------------+------------------------+
     | Step 1: Reserve Currency                        |
     v                                                 |
[Wallet Service]                                       |
  - Check Buyer Balance >= Price                       |
  - State: HOLD (Pending_Escrow)                       |
     |                                                 |
     | (Success: Ack)                                  |
     +------------------------>+                       |
                               | Step 2: Lock & Transfer Item
                               v
                        [Inventory Service]
                          - Verify Seller Item Validity
                          - Lock Item ID: ITEM-88899
                          - Transfer to Buyer Inventory (State: Provisional)
                               |
     +-------------------------+
     | (Success: Ack)
     v
[Saga Orchestrator]
     |
     | Step 3: Finalize Financial Settlement
     +-------------------------------------------------+
     |                                                 |
     v                                                 v
[Wallet Service]                              [Market Tax Service]
  - Deduct Escrow Currency                      - Credit System Fee
  - Credit Seller Balance
     |
     +---> [Saga Complete: Commit Event Published]
```

*Jika Langkah 2 Gagal (Misal: Item telah ditukar di sesi lain tepat sebelum lock dieksekusi):*
1.  Orchestrator menerima sinyal `ITEM_LOCKED_OR_INVALID`.
2.  Orchestrator mengeksekusi aksi kompensasi: `WalletService.ReleaseCurrencyHold(BuyerID, Amount)`.
3.  State dikembalikan ke status konsisten tanpa intervensi manual; klien menerima notifikasi `TRADE_ABORTED`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Brankas Kasino Terpadu
Bayangkan sebuah kasino kelas dunia:
*   Pemain tidak membawa uang tunai ke meja roulette; mereka menggunakan *chip*.
*   Di meja, bandar tidak mencetak atau memusnahkan chip dari udara; setiap chip yang masuk ke meja berasal dari *Rack* bandar dan berpindah ke kotak taruhan pemain (*Double-entry*).
*   Jika terjadi insiden (lampu padam mendadak / DGS crash), kasino tidak menebak berapa sisa chip setiap pemain. Kamera CCTV dan slip pencatatan di meja (*Event Sourced WAL*) diputar ulang untuk mengetahui status pasti setiap keping chip pada detik terakhir sebelum lampu padam.

#### Arsitektur Persistensi End-to-End

```
+---------------------------------------------------------------------------------------+
|                                GAME PRODUCTION RUNTIME                                 |
+---------------------------------------------------------------------------------------+
                                   |
                         [Edge Game Gateway]
                                   |
       +---------------------------+---------------------------+
       |                                                       |
[DGS Pod 1 (Room A)]                                    [DGS Pod 2 (Room B)]
  - Local Memory State                                    - Local Memory State
  - In-Memory RingBuffer                                  - In-Memory RingBuffer
       |                                                       |
       +---------------------------+---------------------------+
                                   | (Write Mutation Events)
                                   v
             +-------------------------------------------+
             |         Redis Cluster Engine (Stream)     |
             |   Streams: `stream:economy:mutations`     |
             +-------------------------------------------+
                                   |
                 +-----------------+-----------------+
                 | Worker Group (Consumer Group)     |
                 v                                   v
    [Persistence Engine Pod 1]          [Persistence Engine Pod 2]
         - JSON Schema Validation            - Anti-Fraud Delta Check
         - Batch Aggregator (100ms)          - Batch Aggregator (100ms)
                 |                                   |
                 +-----------------+-----------------+
                                   | (Bulk Execute with OCC)
                                   v
             +-------------------------------------------+
             |     PostgreSQL Cluster (Primary/Replica)  |
             |  - Table: `accounts`                      |
             |  - Table: `ledger_entries` (Immutable)    |
             |  - Table: `inventories` (Versioned)       |
             +-------------------------------------------+
                                   |
                         (CDC / Debezium Pipeline)
                                   v
             +-------------------------------------------+
             |   ClickHouse / Snowflake Data Warehouse   |
             |       (Real-Time Economy Balance &        |
             |         Inflation Metric Tracker)         |
             +-------------------------------------------+
```

---

### 7. Simple Example vs Practical Example

#### Simple Example: Pola Mutasi Naif yang Cacat Produksi (Anti-Pattern)

```go
// JANGAN GUNAKAN INI DI PRODUKSI: Rawan Race Condition & Double Spending!
func HandlePurchaseNaif(db *sql.DB, playerID string, itemID string, cost int64) error {
    var balance int64
    // 1. SELECT balance (Rawan Non-Repeatable Read)
    err := db.QueryRow("SELECT wallet_gold FROM players WHERE id = $1", playerID).Scan(&balance)
    if err != nil {
        return err
    }

    if balance < cost {
        return errors.New("insufficient balance")
    }

    // Jika terjadi concurrent request di sini, balance akan salah hitung (Lost Update)
    _, err = db.Exec("UPDATE players SET wallet_gold = wallet_gold - $1 WHERE id = $2", cost, playerID)
    if err != nil {
        return err
    }

    _, err = db.Exec("INSERT INTO inventory (player_id, item_id) VALUES ($1, $2)", playerID, itemID)
    return err
}
```

#### Practical Example: Enterprise Double-Entry Ledger Engine dengan Optimistic Locking & Idempotensi (Go)

```go
package economy

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"errors"
	"fmt"
	"time"
)

var (
	ErrInsufficientFunds   = errors.New("insufficient balance in source account")
	ErrConcurrentMutation  = errors.New("concurrent state mutation detected; retry transaction")
	ErrTransactionConflict = errors.New("idempotency key collision with differing payload")
)

type AccountType string

const (
	AccountTypeSystemMint AccountType = "SYSTEM_MINT"
	AccountTypePlayer     AccountType = "PLAYER_WALLET"
	AccountTypeSystemSink AccountType = "SYSTEM_SINK"
)

type LedgerEntry struct {
	SourceAccountID      string
	DestinationAccountID string
	CurrencyType         string
	Amount               int64
	ReferenceType        string
	ReferenceID          string
}

type EconomyService struct {
	db *sql.DB
}

func NewEconomyService(db *sql.DB) *EconomyService {
	return &EconomyService{db: db}
}

// ExecuteDoubleEntryTransfer menjamin bahwa transfer aset selalu bernilai zero-sum
// menggunakan PostgreSQL Transaction dengan isolation level Serializable atau Repeatable Read + Explicit Locking.
func (s *EconomyService) ExecuteDoubleEntryTransfer(
	ctx context.Context,
	idempotencyKey string,
	entry LedgerEntry,
) error {
	if entry.Amount <= 0 {
		return errors.New("transfer amount must be strictly positive")
	}

	tx, err := s.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// 1. Idempotency Check: Mencegah replay attack atau duplikasi network retry
	payloadHash := s.hashEntryPayload(entry)
	var existingHash string
	err = tx.QueryRowContext(ctx,
		`SELECT payload_hash FROM transaction_idempotency WHERE idempotency_key = $1 FOR UPDATE`,
		idempotencyKey,
	).Scan(&existingHash)

	if err == nil {
		if existingHash == payloadHash {
			// Request telah sukses diproses sebelumnya, kembalikan OK (Idempotent replay)
			return tx.Commit()
		}
		return ErrTransactionConflict
	} else if !errors.Is(err, sql.ErrNoRows) {
		return fmt.Errorf("failed to check idempotency: %w", err)
	}

	// 2. Lock Source Account & Verify Sufficient Funds (Pessimistic Row-Level Lock strictly ordered)
	// Kita mengunci row berdasarkan urutan leksikografis UUID/Account ID untuk menghindari Deadlock.
	firstLockID, secondLockID := entry.SourceAccountID, entry.DestinationAccountID
	if firstLockID > secondLockID {
		firstLockID, secondLockID = secondLockID, firstLockID
	}

	_, err = tx.ExecContext(ctx, `SELECT id FROM game_accounts WHERE id IN ($1, $2) FOR UPDATE`, firstLockID, secondLockID)
	if err != nil {
		return fmt.Errorf("failed to acquire row locks: %w", err)
	}

	var sourceBalance int64
	var sourceAccType AccountType
	err = tx.QueryRowContext(ctx,
		`SELECT balance, account_type FROM game_accounts WHERE id = $1 AND currency = $2`,
		entry.SourceAccountID, entry.CurrencyType,
	).Scan(&sourceBalance, &sourceAccType)
	if err != nil {
		return fmt.Errorf("failed to fetch source balance: %w", err)
	}

	// Akun bertipe SYSTEM_MINT diperbolehkan menghasilkan saldo negatif (asalkan under control)
	if sourceAccType != AccountTypeSystemMint && sourceBalance < entry.Amount {
		return ErrInsufficientFunds
	}

	// 3. Mutasi Nilai pada Master Account
	_, err = tx.ExecContext(ctx,
		`UPDATE game_accounts SET balance = balance - $1, updated_at = NOW(), version = version + 1 
		 WHERE id = $2 AND currency = $3`,
		entry.Amount, entry.SourceAccountID, entry.CurrencyType,
	)
	if err != nil {
		return fmt.Errorf("failed to debit source account: %w", err)
	}

	_, err = tx.ExecContext(ctx,
		`UPDATE game_accounts SET balance = balance + $1, updated_at = NOW(), version = version + 1 
		 WHERE id = $2 AND currency = $3`,
		entry.Amount, entry.DestinationAccountID, entry.CurrencyType,
	)
	if err != nil {
		return fmt.Errorf("failed to credit destination account: %w", err)
	}

	// 4. Catat Immutable Audit Ledger (Append-Only)
	ledgerID := fmt.Sprintf("LEDGER-%d", time.Now().UnixNano())
	_, err = tx.ExecContext(ctx,
		`INSERT INTO audit_ledger (
			id, source_account_id, destination_account_id, currency, amount, 
			reference_type, reference_id, created_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())`,
		ledgerID, entry.SourceAccountID, entry.DestinationAccountID, entry.CurrencyType,
		entry.Amount, entry.ReferenceType, entry.ReferenceID,
	)
	if err != nil {
		return fmt.Errorf("failed to append to audit ledger: %w", err)
	}

	// 5. Simpan Idempotency Key
	_, err = tx.ExecContext(ctx,
		`INSERT INTO transaction_idempotency (idempotency_key, payload_hash, created_at) 
		 VALUES ($1, $2, NOW())`,
		idempotencyKey, payloadHash,
	)
	if err != nil {
		return fmt.Errorf("failed to write idempotency lock: %w", err)
	}

	return tx.Commit()
}

func (s *EconomyService) hashEntryPayload(entry LedgerEntry) string {
	raw := fmt.Sprintf("%s:%s:%s:%d:%s:%s",
		entry.SourceAccountID, entry.DestinationAccountID, entry.CurrencyType,
		entry.Amount, entry.ReferenceType, entry.ReferenceID,
	)
	hash := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(hash[:])
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Insiden: Replikasi Item & Hiperinflasi Cross-Server Marketplace (MMO Skala Global)
*   **Konteks Operasional:** Game MMORPG dengan 1,2 juta CCU membagi dunia menjadi klaster realm/shard independen dengan satu Global Auction House (AH) terpusat.
*   **Vulnerability Pattern (Exploit Vector):** Penyerang memicu transfer item dari inventory server lokal ke AH server via network latency simulator (pembatasan bandwidth mendadak).
    *   *Step 1:* Penyerang meletakkan Item Legendaris di AH Listing.
    *   *Step 2:* Client memutus paket ACK network menuju shard DGS tepat saat server shard sedang memproses status "ITEM_SENT_TO_AUCTION".
    *   *Step 3:* Mekanisme *fallback timeout* internal shard mengasumsikan transaksi gagal dan mengembalikan item ke inventory lokal pemain via auto-rollback.
    *   *Step 4:* Sementara itu, Auction House Server telah memvalidasi penerimaan item karena tidak adanya konsensus terdistribusi atomik.
    *   *Hasil:* Item berhasil terduplikasi menjadi 2, dieksploitasi puluhan ribu kali dalam 4 jam, menyebabkan keruntuhan nilai tukar mata uang in-game sebesar 380%.

#### Solusi Arsitektural Definitif
Engineering Team mengganti integrasi RPC longgar tersebut dengan arsitektur **Distributed Outbox Pattern dengan Two-Phase Commit Reservation Ticket**:

```
[Local Shard DGS]                     [Outbox Processor]                   [Global Auction DB]
       |                                      |                                     |
1. Begin Local DB TX                          |                                     |
   - Move Item to PENDING_DEPOSIT             |                                     |
   - Write to local `outbox_events`           |                                     |
2. Commit Local DB TX                         |                                     |
       |                                      |                                     |
       +------------------------------------->| (Reads CDC / Polling Outbox)        |
                                              |                                     |
                                              | 3. Lock & Insert Listing            |
                                              |------------------------------------>|
                                              |    (With Idempotency Key)           |
                                              |<------------------------------------|
                                              |    [Success: Listing Confirmed]     |
                                              |                                     |
                                      4. Notify Shard                               |
                                      - Set Item Status = CONSUMED                  |
                                      - Clear Reservation                           |
```

*Metrik Pasca-Perbaikan:* Terjadinya zero-duplication selama 18 bulan masa operasional pasca-rilis; rata-rata latensi pendaftaran lelang tetap di bawah 45ms dengan *idempotency guarantee* 100%.

---

### 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Biaya / Konsekuensi Negatif | Skenario Penggunaan yang Ideal |
| :--- | :--- | :--- | :--- |
| **Strict Synchronous DB Locking (Pessimistic `FOR UPDATE`)** | Mencegah anomali konkurensi secara mutlak; konsistensi ACID langsung terbaca (*Read-Your-Writes*). | Latensi tinggi ($O(N)$ terhadap koneksi DB); potensi *database thread exhaustion* dan *cascading lock contention*. | Transaksi bernilai sangat tinggi: Pembelian via Real-Money / Premium Currency, Transfer Guild Bank. |
| **Optimistic Concurrency Control (OCC via Versioning)** | Non-blocking read; throughput tinggi saat minim konflik; utilisasi CPU database lebih efisien. | Eksekusi transaksi harus di-*retry* saat terjadi konflik versi; *latency spike* jika contention meningkat tajam. | Inventory updates reguler, Crafting, Looting di dungeon instanced. |
| **Write-Behind Caching (Queue/Stream In-Memory Buffer)** | Latensi sub-millisecond bagi pemain; database terlindungi dari beban *write spike* masif. | Kompleksitas arsitektur tinggi; risiko kehilangan data (*data loss window*) jika node broker memori hancur sebelum flush. | Pembaruan status game non-finansial: Posisi karakter, Player XP, Degradasi durability senjata. |
| **Event Sourcing + Double-Entry Ledger** | Auditabilitas tak terbatas; audit forensik anti-fraud 100%; rollback berbasis waktu deterministik. | Kebutuhan storage disk membengkak drastis; latensi query saldo membutuhkan *read projection/snapshots*. | Sistem Perbankan Game, Dompet Mata Uang Utama, Central Auction House. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Blind Balance Updates
*   **Kasus:** Menulis kueri SQL menggunakan nilai absolut yang dihitung di level aplikasi:
    ```sql
    -- BUG: Mengabaikan mutasi yang terjadi di thread lain secara konkuren
    UPDATE accounts SET balance = 500 WHERE id = 'user-1';
    ```
*   **Solusi Produksi:** Gunakan ekspresi delta atomik terproteksi batas bawah:
    ```sql
    UPDATE accounts 
    SET balance = balance - 100 
    WHERE id = 'user-1' AND balance >= 100;
    -- Wajib periksa RowsAffected. Jika 0, lemparkan error Insufficient Balance.
    ```

#### 2. Kesalahan: Distributed Deadlock Akibat Urutan Lock yang Acak
*   **Kasus:** Trade P2P antara User A dan User B. Thread 1 mengunci User A lalu User B. Bersamaan dengan itu, Thread 2 (reverse trade/request) mengunci User B lalu User A. Terjadi kebuntuan (*Deadlock*).
*   **Solusi Produksi:** *Canonical Resource Ordering*. Urutkan identitas sumber daya secara deterministik sebelum mengambil lock:
    ```go
    // Lock selalu diakuisisi dengan urutan ID terkecil ke terbesar
    var firstLock, secondLock string
    if userAID < userBID {
        firstLock, secondLock = userAID, userBID
    } else {
        firstLock, secondLock = userBID, userAID
    }
    acquireLock(firstLock)
    acquireLock(secondLock)
    ```

#### Panduan Troubleshooting Lapangan (Root-Cause Matrix)

```
Gejala: Saldo Gold User Tiba-tiba Negatif
├── 1. Periksa Constraint Database
│    └── Apakah skema memiliki CHECK (balance >= 0)?
│         ├── TIDAK: Segera terapkan migrasi DDL ALTER TABLE ... ADD CONSTRAINT chk_positive_balance CHECK (balance >= 0);
│         └── YA: Lanjutkan ke langkah 2.
├── 2. Periksa Race Condition pada Async Queue Worker
│    └── Apakah worker memproses event out-of-order untuk satu partition key?
│         └── Verifikasi Partition Key pada Kafka/RabbitMQ: Wajib menggunakan `player_id`, BUKAN round-robin!
└── 3. Analisis Jejak Idempotency
     └── Apakah ada network retry dari gateway yang menggunakan ID transaksi berbeda untuk aksi yang sama?
          └── Verifikasi validitas Idempotency-Key pada ingress HTTP/gRPC layer.
```

---

### 11. Best Practices (Production Checklist)

#### Security & Anti-Duplication
- [ ] Semua tabel saldo memiliki constraint tingkat basis data: `CHECK (balance >= 0)`.
- [ ] Klien game **TIDAK PERNAH** mengirimkan besaran pengurangan saldo atau harga item; klien hanya mengirim aksi intent (e.g., `BuyItem(catalog_id)`), server yang menentukan harga mutlak.
- [ ] Seluruh endpoint transaksi game wajib menyertakan `idempotency_key` yang digenerasi secara unik oleh mesin state klien dan divalidasi oleh Redis/DB `SETNX`.
- [ ] Nilai hash (*Cryptographic Hash Chaining*) diikutsertakan pada record ledger historis bernilai tinggi untuk mendeteksi manipulasi basis data oleh orang dalam (*malicious internal DBA*).

#### Concurrency & Performance
- [ ] Gunakan isolasi *Read Committed* yang dipadukan dengan *Pessimistic Row-Locking* terpilih (`SELECT ... FOR UPDATE`) dengan canonical ordering untuk mencegah deadlock.
- [ ] Terapkan batas waktu transaksi yang ketat pada database driver: `SET statement_timeout = '2000ms'`.
- [ ] Terapkan *Snapshotting* periodik pada event-sourced aggregate (setiap 100 event) guna mencegah penalti latensi pembacaan (*state rehydration bottleneck*).

#### Observability & Telemetry
- [ ] Catat metrik delta inflasi: `economy_currency_minted_total` vs `economy_currency_burned_total`.
- [ ] Pasang alert otomatis via Prometheus/Grafana jika deviasi rasio *Sink/Mint* melebihi ambang batas aman dalam kurun waktu 1 jam.

---

### 12. Hands-on Practice

Target Direktori: `hands-on/m02/`

#### Langkah 1: Persiapan Lingkungan
Buat file `docker-compose.yml` di dalam direktori `hands-on/m02/` untuk menjalankan dependensi PostgreSQL:

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: game_eng
      POSTGRES_PASSWORD: supersecurepassword
      POSTGRES_DB: game_economy
    ports:
      - "5432:5432"
    command: postgres -c max_connections=200 -c shared_buffers=256MB
```

Jalankan container:
```bash
docker compose up -d
```

#### Langkah 2: Skema Basis Data Produksi
Buat file `schema.sql` dan inisialisasi tabel:

```sql
CREATE TABLE game_accounts (
    id VARCHAR(64) PRIMARY KEY,
    currency VARCHAR(16) NOT NULL,
    balance BIGINT NOT NULL,
    account_type VARCHAR(32) NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT chk_positive_balance CHECK (balance >= 0 OR account_type = 'SYSTEM_MINT')
);

CREATE TABLE audit_ledger (
    id VARCHAR(64) PRIMARY KEY,
    source_account_id VARCHAR(64) NOT NULL,
    destination_account_id VARCHAR(64) NOT NULL,
    currency VARCHAR(16) NOT NULL,
    amount BIGINT NOT NULL,
    reference_type VARCHAR(32) NOT NULL,
    reference_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE transaction_idempotency (
    idempotency_key VARCHAR(128) PRIMARY KEY,
    payload_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed Initial System Accounts
INSERT INTO game_accounts (id, currency, balance, account_type) VALUES 
('SYS_MINT_GOLD', 'GOLD', 0, 'SYSTEM_MINT'),
('SYS_SINK_TAX', 'GOLD', 0, 'SYSTEM_SINK'),
('PLAYER_ALICE', 'GOLD', 1000, 'PLAYER_WALLET'),
('PLAYER_BOB', 'GOLD', 200, 'PLAYER_WALLET');
```

Jalankan ke database:
```bash
docker exec -i $(docker compose ps -q postgres) psql -U game_eng -d game_economy < schema.sql
```

#### Langkah 3: Eksekusi Load Test Konkuren
Buat file `main.go` di `hands-on/m02/` dengan menyematkan kode dari Seksi 7, tambahkan eksekutor stress-test berikut:

```go
package main

import (
	"context"
	"database/sql"
	"fmt"
	"math/rand"
	"sync"
	"sync/atomic"
	"time"

	_ "github.com/lib/pq"
)

func main() {
	connStr := "postgres://game_eng:supersecurepassword@localhost:5432/game_economy?sslmode=disable"
	db, err := sql.Open("postgres", connStr)
	if err != nil {
		panic(err)
	}
	defer db.Close()
	db.SetMaxOpenConns(50)

	svc := NewEconomyService(db) // Merujuk implementasi Section 7

	var wg sync.WaitGroup
	concurrentRequests := 50
	var successCount int64
	var failureCount int64

	fmt.Println("Memulai simulasi transfer konkuren intensif...")

	startTime := time.Now()
	for i := 0; i < concurrentRequests; i++ {
		wg.Add(1)
		go func(iteration int) {
			defer wg.Done()
			idempotencyKey := fmt.Sprintf("IDEMP-KEY-%d-%d", iteration, rand.Intn(5)) // Simulasi network duplicate

			entry := LedgerEntry{
				SourceAccountID:      "PLAYER_ALICE",
				DestinationAccountID: "PLAYER_BOB",
				CurrencyType:         "GOLD",
				Amount:               50,
				ReferenceType:        "PEER_TRADE",
				ReferenceID:          fmt.Sprintf("TRADE-REF-%d", iteration),
			}

			err := svc.ExecuteDoubleEntryTransfer(context.Background(), idempotencyKey, entry)
			if err != nil {
				atomic.AddInt64(&failureCount, 1)
			} else {
				atomic.AddInt64(&successCount, 1)
			}
		}(i)
	}

	wg.Wait()
	fmt.Printf("Selesai dalam %v!\nSukses: %d, Gagal/Tertolak: %d\n", time.Since(startTime), successCount, failureCount)

	// Verifikasi Total Konservasi Aset
	var aliceBal, bobBal int64
	_ = db.QueryRow("SELECT balance FROM game_accounts WHERE id = 'PLAYER_ALICE'").Scan(&aliceBal)
	_ = db.QueryRow("SELECT balance FROM game_accounts WHERE id = 'PLAYER_BOB'").Scan(&bobBal)
	fmt.Printf("Verifikasi Saldo Akhir -> Alice: %d, Bob: %d (Total Tetap: %d)\n", aliceBal, bobBal, aliceBal+bobBal)
}
```

Jalankan pengujian:
```bash
go mod init economy_practice
go get github.com/lib/pq
go run main.go
```

---

### 13. Tiered Exercises

#### Level Easy
*   **Tugas:** Tambahkan kolom `account_status` (`ACTIVE`, `FROZEN`, `BANNED`) pada tabel `game_accounts`. Modifikasi query transaksi pada kode `ExecuteDoubleEntryTransfer` agar membatalkan mutasi dan mengembalikan error khusus `ErrAccountFrozen` jika akun sumber atau akun destinasi berstatus non-aktif.
*   **Kriteria Sukses:** Pengujian unit memverifikasi bahwa akun yang di-freeze tidak dapat mengirim maupun menerima balance.

#### Level Medium
*   **Tugas:** Buat background task *Reconciliation Audit Daemon* dalam bahasa Go yang berjalan setiap interval tertentu. Worker ini melakukan agregasi sum:
    $$\sum \text{Ledger Debit/Credit} \stackrel{?}{=} \text{Current Balance}$$
    Worker akan memunculkan alarm *Data Corruption Warning* jika ditemukan selisih delta antara agregat histori transaksi di `audit_ledger` dengan nilai aktual di `game_accounts.balance`.
*   **Kriteria Sukses:** Log peringatan terpicu secara presisi saat kita memodifikasi nilai `game_accounts.balance` secara paksa via SQL shell tanpa melalui ledger.

#### Level Hard
*   **Tugas:** Rancang dan implementasikan struktur data *In-Memory Write-Behind Ring Buffer* thread-safe tanpa *global mutex* (menggunakan atomic pointer swapping atau channel berkapasitas tinggi) yang menampung hingga 100.000 log mutasi status XP per detik, dan secara deterministik mem-flush state tersebut ke PostgreSQL dalam batch berukuran 5.000 records.
*   **Kriteria Sukses:** Database throughput tetap stabil di bawah 60% CPU utilization saat load simulator membanjiri server dengan 80.000 events/sec, tanpa ada drop event ketika proses dimatikan via sinyal `SIGINT/SIGTERM` (*graceful shutdown flush*).

---

### 14. Open-Ended Production Challenge

#### Skenario: Arsitektur Ekonomi Global "Dynamic Currency Arbitrage & Black Swan Crash"
Anda ditunjuk sebagai Principal Backend Architect untuk game MMORPG lintas platform global berbasis WebSockets/gRPC. Permainan memiliki fitur:
1.  **Global Player Exchange:** Pemain di Server Asia, Server Amerika, dan Server Eropa dapat memperdagangkan komoditas langka di bursa yang sama secara *real-time*.
2.  **Volatile Token Currency:** Nilai tukar mata uang internal berfluktuasi bebas setiap menit berdasarkan penawaran dan permintaan (*Automated Market Maker / AMM* di backend).

**Kondisi Krisis (Tantangan):**
Terjadi insiden jaringan global di mana konektivitas antara shard game Asia dan database pusat mengalami *intermittent network partition* (paket hilang 40%, latensi membengkak dari 15ms menjadi 3.500ms) selama 20 menit saat terjadi *event diskon tahunan*. 

**Ekspektasi Solusi:**
Rancang dokumen arsitektur dan mitigasi teknis sistematis:
*   Bagaimana mencegah *arbitrage exploitation* di mana pemain regional memanfaatkan jeda update harga pasar lokal vs global untuk memborong item murah dan menjualnya kembali di region lain?
*   Bagaimana desain arsitektur persistensi Anda menerapkan kompromi teorema CAP (*Consistency vs Availability*)? Apakah Anda memilih memutus fungsionalitas perdagangan di region terdampak (*CP mode*) atau mengizinkan perdagangan berbasis kuota lokal terisolasi (*AP mode with eventual reconciliation boundaries*)? Buktikan rasionalisasi bisnis dan teknis Anda!
*   Sajikan diagram alur data dan pseudo-kode mekanisme sinkronisasi state saat jaringan kembali normal (*Post-Partition Healing Phase*) untuk memastikan tidak ada mata uang yang tercetak ganda.

---

### 15. Comprehensive Diagnostic Quiz

#### Pertanyaan Level Basic (5 Soal)
1. **Mengapa penggunaan perintah `UPDATE players SET gold = gold - 50` tanpa klausa proteksi rentan menyebabkan saldo negatif?**
   * *Jawaban:* Karena tanpa klausa evaluasi saldo lokal seperti `AND gold >= 50` atau constraint database `CHECK (gold >= 0)`, transaksi yang berjalan paralel dapat membaca saldo tersisa yang valid secara bersamaan, mengeksekusi pengurangan berganda, dan menghasilkan nilai saldo di bawah nol.

2. **Apa yang dimaksud dengan sifat *Append-Only* dalam pola persistensi *Ledger*?**
   * *Jawaban:* Record yang telah masuk tidak boleh diubah (`UPDATE`) atau dihapus (`DELETE`). Setiap koreksi kesalahan atau pembalikan nilai harus dimasukkan sebagai record transaksi baru yang menyeimbangkan record sebelumnya.

3. **Apa fungsi utama dari *Idempotency Key* pada transaksi ekonomi game?**
   * *Jawaban:* Mencegah pemrosesan ganda (*duplicate execution*) atas aksi yang sama ketika klien melakukan pengiriman ulang (*retry*) akibat terputusnya koneksi atau timeout jaringan sebelum menerima respons konfirmasi dari server.

4. **Kapan *Pessimistic Locking* lebih disukai daripada *Optimistic Concurrency Control* (OCC) dalam backend game?**
   * *Jawaban:* Ketika probabilitas konflik transaksi (*contention rate*) sangat tinggi pada sumber daya yang sama, seperti lelang item langka tunggal (*high-demand auction item*), di mana OCC akan membuang siklus komputasi karena retry loop yang terus-menerus gagal.

5. **Apa kelemahan utama dari pola *Write-Behind (Write-Back) Caching*?**
   * *Jawaban:* Risiko kehilangan data (*data loss*) jika node penyimpan cache in-memory mengalami crash mendadak (*ungraceful power-loss/kill*) sebelum data berhasil di-flush ke basis data persisten.

#### Pertanyaan Level Intermediate (5 Soal)
6. **Bagaimana cara mencegah kebuntuan (*Deadlock*) secara deterministik ketika dua pemain mentransfer aset satu sama lain pada saat yang sama?**
   * *Jawaban:* Terapkan aturan penguncian berurutan secara kanonikal (*Resource Ordering/Lock Hierarchy*). Kunci entitas sumber daya berdasarkan urutan leksikografis terkecil ke terbesar dari ID entitas (misal: selalu kunci ID `User_A` sebelum `User_B` jika `User_A` < `User_B`), apapun arah aliran transfernya.

7. **Mengapa arsitektur *Two-Phase Commit* (2PC) tradisional berbasis koordinator terpusat dihindari untuk transaksi mikro berkecepatan tinggi antar microservices game?**
   * *Jawaban:* 2PC bersifat *blocking synchronous protocol*. Jika koordinator atau salah satu partisipan mengalami kelambatan jaringan atau down saat fase commit, resource lock pada seluruh partisipan tertahan, menyebabkan latensi melonjak tajam dan menghentikan throughput transaksi sistem secara sistemik.

8. **Apa perbedaan struktural antara *Account Type: SYSTEM_MINT* dan *Account Type: PLAYER_WALLET* pada sistem Double-Entry?**
   * *Jawaban:* `PLAYER_WALLET` tunduk pada batasan saldo non-negatif mutlak ($\ge 0$). Sedangkan `SYSTEM_MINT` berperan sebagai representasi sumber pasokan tak terbatas (*fiat injection source*), sehingga diizinkan memiliki saldo negatif sebagai indikator total pasokan mata uang yang telah diterbitkan ke dalam dunia game.

9. **Dalam implementasi Optimistic Locking berbasis versi, apa yang terjadi jika dua worker membaca `version = 4` dan sama-sama mencoba mengupdate state ke database?**
   * *Jawaban:* Worker pertama yang kuerinya dieksekusi akan berhasil mengupdate versi menjadi `5` (`RowsAffected = 1`). Worker kedua akan mendapati kondisi `WHERE version = 4` tidak terpenuhi lagi (`RowsAffected = 0`). Aplikasi mendeteksi ini sebagai tabrakan konkurensi (*stale data*) dan memicu pembacaan ulang state terbaru atau menggagalkan aksi.

10. **Bagaimana mekanisme *Compensating Transaction* bekerja dalam Pola Saga Orkestrasi saat step transfer item gagal?**
    * *Jawaban:* Kompensasi bukanlah rollback berbasis physical snapshot, melainkan serangkaian aksi bisnis penyeimbang yang dieksekusi secara maju (*forward-recovery*). Contoh: Jika step pemberian item gagal, orchestrator akan memanggil aksi kompensasi untuk mengembalikan mata uang yang sebelumnya telah terpotong dari dompet pembeli kembali ke status semula.

#### Skenario Kasus Produksi (3 Kasus)

11. **Skenario Kasus 1: Gacha Roll Spam Exploit**
    * *Masalah:* Seorang pemain mengirimkan payload gacha roll via bot sebanyak 50 request secara simultan dalam 5 milidetik menggunakan token gacha yang hanya cukup untuk 1 kali roll. Pemeriksaan server menunjukkan saldo pemain berkurang menjadi minus, atau pemain mendapatkan 50 item gacha dengan hanya membayar 1 token.
    * *Akar Masalah:* Server logic membaca saldo token secara asinkron tanpa lock transaksi atau pembaruan delta yang terisolasi (*Time-of-Check to Time-of-Use / TOCTOU flaw*).
    * *Solusi Remediasi Rekayasa:*
      1. Terapkan Single-Flight Locking berbasis Redis Redlock pada `player_id` untuk aksi Gacha, menolak eksekusi jika proses gacha sebelumnya untuk user tersebut belum selesai.
      2. Eksekusi konsumsi token secara atomik di basis data:
         ```sql
         UPDATE player_wallets SET gacha_tokens = gacha_tokens - 1 
         WHERE player_id = $1 AND gacha_tokens >= 1;
         ```
      3. Gacha roll item generation hanya dieksekusi **jika dan hanya jika** mutasi token mengembalikan *Rows Affected = 1*.

12. **Skenario Kasus 2: Auction House Sniping Collision**
    * *Masalah:* Sistem lelang game menampilkan lonjakan latensi hingga 12 detik dan memicu error `504 Gateway Timeout` masif saat senjata legendaris langka dilelang dengan metode "Buyout Now". Ratusan pemain mengklik tombol Buyout pada detik yang sama. Database connection pool langsung terkuras habis (*exhausted*).
    * *Akar Masalah:* Semua request memperebutkan row lock yang sama (`SELECT ... FOR UPDATE WHERE item_id = 'XYZ'`). Antrean thread yang menunggu lock memblokir connection pool RDBMS, melumpuhkan transaksi modul lain yang tidak berhubungan.
    * *Solusi Remediasi Rekayasa:*
      1. Isolasi pool database lelang dari pool transaksi inti pemain.
      2. Letakkan Distributed Mutex di layer memory/cache terdepan (Redis via evaluasi script Lua atomik) untuk mengeliminasi 99% request yang kalah cepat di layer ingress sebelum menyentuh koneksi database.
      3. Kueri SQL lelang menggunakan klausa non-blocking:
         ```sql
         SELECT id FROM auction_listings WHERE id = $1 AND status = 'OPEN' FOR UPDATE NOWAIT;
         ```
         Jika lock gagal diperoleh, segera kembalikan status `ERR_ITEM_ALREADY_ACQUIRED` tanpa membiarkan koneksi menggantung.

13. **Skenario Kasus 3: Phantom Rollback saat Shard Server Crash**
    * *Masalah:* Server Shard DGS zona Dungeon mengalami *Segmentation Fault* mendadak. Setelah boot ulang, 4 anggota party mendapati item hasil boss drop mereka hilang dari tas, namun *durability* armor mereka tetap berkurang sesuai pertarungan terakhir.
    * *Akar Masalah:* *Inconsistent Flush Boundaries*. Logika pengurangan durability dieksekusi via synchronous RPC langsung ke Auth-Service, sedangkan perolehan item disimpan di in-memory cache DGS yang dijadwalkan untuk di-flush hanya saat pemain berpindah zona (*Area Transition Flush*).
    * *Solusi Remediasi Rekayasa:*
      1. Terapkan prinsip kesatuan transaksional: Jangan pernah memisahkan persistensi biaya (*cost/consumption*) dengan persistensi hasil (*reward/drop*).
      2. Event penyelesaian Boss Dungeon wajib memancarkan *Dungeon Completion Envelope* atomik yang berisi mutasi status menyeluruh (Reward + Durability Damage).
      3. Dungeon DGS tidak boleh menganggap event selesai sebelum menerima status *Persistence Acknowledged* dari persistensi terpusat via gRPC sync-barrier.

---

### 16. Summary

*   **Ekonomi Game Membutuhkan Disiplin Finansial Perbankan:** Pembaruan state ekonomi game tidak boleh diperlakukan sebagai variabel floating point bebas. Arsitektur *Double-Entry Bookkeeping* berbasis *append-only ledger* menjamin integritas aset tanpa kebocoran (*zero-leakage*) dan auditabilitas anti-cheat mutlak.
*   **Isolasi Konkurensi adalah Garda Terdepan Anti-Exploit:** Sebagian besar celah duplikasi item (*dupe glitch*) berakar dari fenomena *race condition* dan penanganan asinkronisasi yang longgar. Penerapan canonical lock ordering, idempotency hashing, dan constraint database non-negatif adalah harga mati bagi integritas sistem game produksi.
*   **Keseimbangan Skalabilitas via Hybrid Write Patterns:** Gunakan *Pessimistic Strict Locking* untuk transaksi finansial bernilai tinggi, *Optimistic Concurrency Control* untuk pembaruan inventaris harian frekuensi menengah, dan *Write-Behind Pipeline* untuk state telemetri performa tinggi berskala masif.

---
*Materi berlanjut ke Modul 03: Arsitektur Game Distributed Messaging, Fault Tolerance, dan Disaster Recovery.*