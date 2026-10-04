# BAB 06: Pola Persistensi, State Management, & Ekonomi Game

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendesain** arsitektur persistensi hibrida (*Hot In-Memory State* + *Cold Durable Storage*) yang memenuhi Service Level Agreement (SLA) latensi tick game $\le 15\text{ ms}$ tanpa mengorbankan integritas data finansial.
- **Mengimplementasikan** sistem *Double-Entry Bookkeeping* berbasis Relational Database Management System (RDBMS) dengan *ACID guarantees* untuk mencegah anomali *item duplication* (*duping*) dan manipulasi ekonomi oleh *autonomous agents*.
- **Mengembangkan** mekanisme *State Management* terdistribusi menggunakan kombinasi *Optimistic Concurrency Control* (OCC) dan *Pessimistic Locking* sesuai skenario mutasi *state*.
- **Membangun** pipeline mitigasi *dual-write problem* menggunakan *Transactional Outbox Pattern* dan *Idempotency Keys* untuk sinkronisasi mutasi antara game server, Redis, dan database persisten.
- **Mendiagnosis** dan **memitigasi** *edge cases* transaksi konkuren: *circular deadlocks*, *phantom reads*, *race conditions*, serta *split-brain states* pada autonomous agent cluster.

---

## 2. Concept Overview

Sistem backend game modern—khususnya yang melibatkan *autonomous agents*, integrasi machine learning, dan open-economy—beroperasi pada perpotongan dua kebutuhan yang saling bertolak belakang: **throughput mutasi ultra-tinggi** (latensi milidetik) dan **konsistensi absolut data ekonomi** (zero tolerance terhadap data loss atau anomali saldo).

```
+-------------------------------------------------------------------------+
|                              GAME ENGINE TICK                           |
|                      (Volatile State: Latency < 16ms)                   |
|  - Posisi spatial (X, Y, Z)                                             |
|  - Pergerakan physics, directional vectors                              |
|  - Frame-to-frame interpolation                                         |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                        SEMI-DURABLE STATE (REDIS)                       |
|                     (Session & AI Context: TTL Based)                   |
|  - Agent Short-Term Memory (Context window buffer)                      |
|  - Cooldown timers, active buffs/debuffs                                |
|  - Lock distributed mutexes & rate limiters                             |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                     TRANSACTIONAL LEDGER (POSTGRESQL)                   |
|                   (Durable State: Strong ACID Guarantees)               |
|  - Currency balances (Gold, Gems, Tokens)                               |
|  - Inventory ownership & provenance graph                               |
|  - Immutable Double-Entry Ledger journal entries                        |
+-------------------------------------------------------------------------+
```

### Taksonomi State Game Server

1. **Ephemeral/Volatile State**: Data berumur pendek yang diproses per tick (posisi transformasi, kecepatan, target raycasting). State ini tidak pernah ditulis langsung ke persistent disk; jika node server mati, state dapat direkonstruksi dari state dunia terakhir atau diabaikan.
2. **Semi-Durable State**: State runtime yang harus bertahan dari transient disconnect atau crash worker node tunggal, namun tidak memerlukan jaminan ACID relasional (misal: intent queue autonomous agent, cooldown skill, sesi WebSocket). State ini umumnya disimpan di distributed memory store (Redis Cluster / DragonflyDB).
3. **Durable/Transactional State**: Entitas ekonomi inti, inventaris pemain/agen, dan riwayat transaksi. Mutasi pada layer ini wajib mematuhi aturan strict serializability atau read-committed dengan deterministic lock ordering.

### Dualitas Engine: Tick Loop vs Transaction Ledger

Game engine konvensional mengandalkan loop deterministik:
$$\Delta t = t_{now} - t_{last}$$

Jika thread tick ini diblokir oleh operasi I/O database relasional (yang tipikal memakan waktu $2-50\text{ ms}$), seluruh simulasi dunia akan mengalami *hitch* (*frame drop*). Oleh karena itu, arsitektur backend harus memisahkan **Execution Phase** (in-memory, non-blocking) dari **Persistence/Settlement Phase** (asynchronous transactional processing via transactional outbox atau synchronous ledger call offloaded to dedicated worker pools).

---

## 3. Why It Matters

Kegagalan dalam memisahkan state transient dan transactional secara presisi menyebabkan kerusakan ekonomi dan eksploitasi sistemik:

1. **Item Duplication Exploit ("Duping")**:
   Terjadi ketika pemain atau autonomous agent melakukan transfer aset ke entitas lain secara paralel dengan memicu crash server atau *network partition*. Jika inventaris dikurangi di memori tetapi belum di-commit ke disk saat crash terjadi, entitas penerima telah menerima data di disk, sementara entitas pengirim mendapatkan kembali itemnya saat recovery (Rollback Asymmetry).
2. **Runaway Agent Inflation**:
   Autonomous AI Agent yang diizinkan melakukan *arbitrage loop* secara otonom dapat mengeksploitasi celah desinkronisasi harga atau pembulatan mata uang. Tanpa *Double-Entry Ledger*, uang tercipta dari ketiadaan (*money out of thin air*) tanpa terdeteksi hingga likuiditas seluruh sistem kolaps.
3. **The Dual-Write Hazard**:
   Menulis ke Redis terlebih dahulu kemudian ke database relasional tanpa koordinasi transaksional terdistribusi dapat menghasilkan state drift permanen ketika koneksi ke database database drop setelah Redis sukses ditulis.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur mutasi ekonomi yang dipicu oleh Autonomous AI Agent, diproses melalui Redis State Layer, diverifikasi oleh Core Transaction Engine, dan dicatat secara atomik ke dalam PostgreSQL Ledger.

```
+------------------+         +--------------------+
| Autonomous Agent |         | Human Player (App) |
+------------------+         +--------------------+
         |                             |
         +--------------+--------------+
                        |
                        v [gRPC / HTTPS with Idempotency-Key]
         +---------------------------------------------+
         |            API Gateway / Game Gateway       |
         +---------------------------------------------+
                        |
                        v
         +---------------------------------------------+
         |         Distributed Lock Manager            |
         |         (Redis Redlock: Mutex Resource)     |
         +---------------------------------------------+
                        |
                        +----------------------+
                        | (Acquire Lock OK)    | (Lock Contention)
                        v                      v
         +-----------------------------+  +------------+
         |      Ledger Service         |  | HTTP 409 / |
         |   (Transaction Orchestrator)|  | Retry Back |
         +-----------------------------+  +------------+
                        |
       +----------------+----------------+
       | (PostgreSQL ACID Transaction)   |
       v                                 v
+-------------------------------+ +-------------------------------+
|  ledger_entries (Append-Only) | |  accounts (Balance Constraint)|
|  - Entry ID                   | |  - Account ID                 |
|  - Transaction ID             | |  - Balance (CHECK >= 0)       |
|  - Debit Account              | |  - Nonce / Version (OCC)      |
|  - Credit Account             | +-------------------------------+
|  - Amount                     |
+-------------------------------+
       |
       v (Commit Transaction)
+-----------------------------------------------+
|          Transactional Outbox Table           |
| (Events to be published to Event Broker)      |
+-----------------------------------------------+
       |
       v [Debezium / CDC Poller]
+-----------------------------------------------+
|               Apache Kafka / NATS             |
+-----------------------------------------------+
       |
       +------------------------+
       v                        v
+------------------+   +------------------------+
| Read-Model Cache |   | Analytics / Audit Sink |
| (Redis Cluster)  |   | (ClickHouse / S3)      |
+------------------+   +------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### Double-Entry Bookkeeping (Pembukuan Berpasangan)

Dalam sistem ekonomi enterprise, mutasi saldo akun tidak pernah dilakukan dengan operasi primitif seperti:
$$\text{balance} \leftarrow \text{balance} + x$$
Operasi tersebut melanggar prinsip non-repudiation dan memusnahkan jejak audit.

Sebagai gantinya, digunakan prinsip **Persamaan Akuntansi Dasar**:
$$\sum \text{Debit} = \sum \text{Kredit}$$

Setiap perpindahan nilai diwujudkan dalam satu `Transaction` yang membawahi minimal dua `LedgerEntry`:
- **Debit**: Rekening tujuan atau penambahan aset.
- **Credit**: Rekening sumber atau pengurangan kewajiban/ekuitas.
- **Invariant**: Saldo bersih dari seluruh baris dalam satu transaksi wajib sama dengan nol ($\sum \text{Delta} = 0$).

```
Transaksi Transfer 100 Gold dari Agent_A ke Agent_B:
----------------------------------------------------------------------
Entry 1: Debit  Akun Agent_B (Asset: Gold)       +100 Gold
Entry 2: Credit Akun Agent_A (Asset: Gold)       -100 Gold
----------------------------------------------------------------------
Total Balance Delta:                             0   (Zero-Sum Integrity)
```

Untuk menjamin tidak ada uang tercipta dari ketiadaan, sistem menyediakan akun khusus bernama **System Mint Account** (Ekuitas/Penerbit) dan **System Sink Account** (Expense/Pembakaran Pajak/Gold Sink).

### Optimistic Concurrency Control (OCC) vs. Pessimistic Locking

| Parameter | Optimistic Concurrency Control (OCC) | Pessimistic Locking (`SELECT FOR UPDATE`) |
| :--- | :--- | :--- |
| **Prinsip Kerja** | Izinkan baca bersamaan, validasi versi saat commit (`WHERE version = @v`). | Kunci baris pada database level sejak awal baca hingga transaksi tuntas. |
| **Beban Latensi** | Sangat rendah saat *low-to-moderate contention*. | Menghambat throughput; latensi meningkat linier terhadap *contention*. |
| **Resiko Kegagalan**| *Rollback & Retry overhead* saat terjadi benturan paralel tinggi. | Deadlock terdistribusi jika penguncian urutan resource tidak teratur. |
| **Use-Case Terbaik**| Perubahan profil agent, equip inventory, task state otonom. | Akun likuiditas tinggi, auction house, transfer peer-to-peer instan. |

### Distributed Lock Ordering & Deadlock Prevention

Jika Agent 1 mentransfer dana ke Agent 2 bersamaan dengan Agent 2 mentransfer ke Agent 1:
- Thread A mengunci `Agent 1`, lalu meminta lock `Agent 2`.
- Thread B mengunci `Agent 2`, lalu meminta lock `Agent 1`.
- **Hasil**: Circular Deadlock pada RDBMS atau Distributed Lock engine.

**Solusi Standar**: *Deterministic Resource Ordering*.
Sebelum melakukan locking pada dua atau lebih akun, urutkan ID resource secara leksikografis:
$$\text{lock\_order} = \text{sort}([ID_A, ID_B])$$
Kunci resource dengan ID terkecil terlebih dahulu, baru kemudian resource dengan ID yang lebih besar. Pendekatan ini secara matematis mengeliminasi kemungkinan terjadinya cyclic wait condition (salah satu dari empat syarat Coffman Deadlock).

---

## 6. Production-Ready Code Implementation

Implementasi berikut menggunakan Python 3.12, SQLAlchemy 2.0 (Async Engine), PostgreSQL, dan Redis. Kode ini mencakup arsitektur ledger yang utuh: penanganan konkurensi berbasis skema, locking terurut, validasi idempotency, serta eksekusi transaksi atomik.

### 6.1. Schema Setup & Domain Models

```python
# models.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    String, Numeric, ForeignKey, CheckConstraint, 
    Index, UniqueConstraint, DateTime
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(12), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(precision=24, scale=4), nullable=False, default=Decimal("0.0000"))
    version: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("balance >= 0", name="chk_account_balance_non_negative"),
        UniqueConstraint("owner_id", "currency", name="uq_owner_currency"),
    )

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    entries: Mapped[list["LedgerEntry"]] = relationship("LedgerEntry", back_populates="transaction")

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Nilai amount positif = Debit, nilai amount negatif = Credit
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=24, scale=4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="entries")
    account: Mapped["Account"] = relationship("Account")

    __table_args__ = (
        CheckConstraint("amount <> 0", name="chk_ledger_amount_not_zero"),
    )
```

### 6.2. Domain Service & Ledger Engine

```python
# ledger_service.py
import uuid
import logging
from decimal import Decimal
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
import redis.asyncio as aioredis

from models import Account, Transaction, LedgerEntry

logger = logging.getLogger("LedgerEngine")

class InsufficientFundsException(Exception):
    pass

class ConcurrencyConflictException(Exception):
    pass

class InvalidTransactionException(Exception):
    pass

class IdempotencyViolationException(Exception):
    pass

class LedgerService:
    def __init__(self, session: AsyncSession, redis_client: aioredis.Redis):
        self.session = session
        self.redis = redis_client

    async def transfer_funds(
        self,
        idempotency_key: str,
        source_account_id: uuid.UUID,
        destination_account_id: uuid.UUID,
        amount: Decimal,
        description: str
    ) -> uuid.UUID:
        """
        Mengeksekusi transfer dana atomik berbasis double-entry bookkeeping dengan
        deterministic lock ordering dan perlindungan idempotensi terdistribusi.
        """
        if amount <= Decimal("0.0000"):
            raise InvalidTransactionException("Jumlah transfer harus lebih besar dari 0.0000")

        if source_account_id == destination_account_id:
            raise InvalidTransactionException("Akun sumber dan tujuan tidak boleh identik")

        # 1. Distributed Idempotency Guard (Redis Layer)
        lock_key = f"idempotency:lock:{idempotency_key}"
        # Set lock dengan TTL 30 detik untuk menolak duplicate in-flight requests
        is_new_request = await self.redis.set(lock_key, "PROCESSING", nx=True, ex=30)
        if not is_new_request:
            raise IdempotencyViolationException("Permintaan sedang diproses atau idempotency key telah dipakai.")

        try:
            # 2. Periksa apakah transaksi dengan idempotency key ini sudah berhasil di-commit sebelumnya
            existing_tx_stmt = select(Transaction.id).where(Transaction.idempotency_key == idempotency_key)
            result = await self.session.execute(existing_tx_stmt)
            existing_tx_id = result.scalar_one_or_none()
            if existing_tx_id:
                logger.info(f"Idempotency hit! Transaksi {existing_tx_id} sudah selesai.")
                return existing_tx_id

            # 3. Deterministic Resource Ordering (Cegah Deadlock)
            accounts_to_lock = sorted([source_account_id, destination_account_id])

            # Ambil accounts menggunakan SELECT FOR UPDATE dengan urutan pasti
            stmt = (
                select(Account)
                .where(Account.id.in_(accounts_to_lock))
                .order_by(Account.id)
                .with_for_update()
            )
            accounts_res = await self.session.execute(stmt)
            locked_accounts = {acc.id: acc for acc in accounts_res.scalars().all()}

            if len(locked_accounts) != 2:
                raise InvalidTransactionException("Salah satu atau kedua entitas akun tidak ditemukan.")

            src_acc = locked_accounts[source_account_id]
            dst_acc = locked_accounts[destination_account_id]

            # Verifikasi currency match
            if src_acc.currency != dst_acc.currency:
                raise InvalidTransactionException("Mata uang akun sumber dan tujuan tidak sesuai.")

            # Verifikasi saldo mencukupi
            if src_acc.balance < amount:
                raise InsufficientFundsException(
                    f"Saldo tidak mencukupi. Tersedia: {src_acc.balance}, Dibutuhkan: {amount}"
                )

            # 4. Buat Master Record Transaksi
            tx = Transaction(
                id=uuid.uuid4(),
                idempotency_key=idempotency_key,
                description=description
            )
            self.session.add(tx)

            # 5. Buat Ledger Entries (Double-Entry: Net Delta == 0)
            # Entry 1: Pengurangan saldo pengirim (Credit)
            credit_entry = LedgerEntry(
                id=uuid.uuid4(),
                transaction_id=tx.id,
                account_id=src_acc.id,
                amount=-amount
            )
            # Entry 2: Penambahan saldo penerima (Debit)
            debit_entry = LedgerEntry(
                id=uuid.uuid4(),
                transaction_id=tx.id,
                account_id=dst_acc.id,
                amount=amount
            )
            self.session.add_all([credit_entry, debit_entry])

            # 6. Mutasi Snapshot Saldo Akun
            src_acc.balance -= amount
            src_acc.version += 1

            dst_acc.balance += amount
            dst_acc.version += 1

            # 7. Commit Transaksi Database
            await self.session.commit()

            # Tandai status permanen di Redis untuk fast-path cache
            await self.redis.set(f"idempotency:done:{idempotency_key}", str(tx.id), ex=86400)
            return tx.id

        except IntegrityError as ie:
            await self.session.rollback()
            logger.error(f"Integritas database terlanggar pada tx {idempotency_key}: {str(ie)}")
            raise ConcurrencyConflictException("Konflik integritas transaksi terjadi.") from ie
        except Exception as e:
            await self.session.rollback()
            raise e
        finally:
            # Hapus transient lock
            await self.redis.delete(lock_key)
```

### 6.3. Integration Test Harness

```python
# test_ledger.py
import asyncio
import uuid
from decimal import Decimal
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import redis.asyncio as aioredis

from models import Base, Account
from ledger_service import LedgerService, InsufficientFundsException

DATABASE_URL = "postgresql+asyncpg://game_dev:game_dev_pwd@localhost:5432/game_economy"
REDIS_URL = "redis://localhost:6379/0"

@pytest_asyncio.fixture
async def setup_env():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield async_session, redis_client

    await engine.dispose()
    await redis_client.aclose()

async def run_concurrent_transfers():
    # Demonstrasi ketahanan terhadap Race Conditions & Deadlock
    engine = create_async_engine(DATABASE_URL, echo=False, pool_size=20)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    # Inisialisasi Akun
    acc1_id, acc2_id = uuid.uuid4(), uuid.uuid4()
    async with session_factory() as init_session:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        
        acc1 = Account(id=acc1_id, owner_id="agent_alpha", currency="GOLD", balance=Decimal("1000.0000"))
        acc2 = Account(id=acc2_id, owner_id="agent_beta", currency="GOLD", balance=Decimal("1000.0000"))
        init_session.add_all([acc1, acc2])
        await init_session.commit()

    async def transfer_task(idemp_suffix: int, src: uuid.UUID, dst: uuid.UUID, amt: Decimal):
        async with session_factory() as session:
            service = LedgerService(session, redis_client)
            key = f"tx_concurrent_test_{idemp_suffix}"
            try:
                await service.transfer_funds(
                    idempotency_key=key,
                    source_account_id=src,
                    destination_account_id=dst,
                    amount=amt,
                    description=f"Transfer test {idemp_suffix}"
                )
            except Exception as exc:
                return f"Err: {type(exc).__name__}"
            return "OK"

    # Jalankan simulasi traffic: Alpha -> Beta dan Beta -> Alpha terjadi di waktu yang sama
    tasks = []
    for i in range(25):
        tasks.append(transfer_task(i, acc1_id, acc2_id, Decimal("10.0000")))
        tasks.append(transfer_task(i + 100, acc2_id, acc1_id, Decimal("10.0000")))

    results = await asyncio.gather(*tasks)
    print(f"Hasil Eksekusi Transaksi: OK={results.count('OK')}, Failure={len(results) - results.count('OK')}")

    # Validasi Integritas Konsistensi Saldo Akhir
    async with session_factory() as session:
        acc1 = await session.get(Account, acc1_id)
        acc2 = await session.get(Account, acc2_id)
        print(f"Saldo Akhir Alpha: {acc1.balance}")
        print(f"Saldo Akhir Beta: {acc2.balance}")
        assert acc1.balance + acc2.balance == Decimal("2000.0000"), "Fatal: Konservasi ekonomi bocor!"

if __name__ == "__main__":
    asyncio.run(run_concurrent_transfers())
```

---

## 7. Edge Cases & Failure Modes

### 1. The Disconnect Exploit (Asynchronous State Inconsistency)
- **Skenario**: Seorang pemain menginisiasi trade dengan autonomous agent. Client mengirim perintah `ConfirmTrade`, lalu sengaja memutus koneksi internet (*pulling the cable*) sebelum menerima jawaban server.
- **Dampak Kegagalan**: Jika server mengandalkan *client acknowledge* untuk finalisasi penulisan database, transaksi berada dalam status *half-open*. Agen menganggap trade batal, sementara akun pemain sudah didebit atau sebaliknya.
- **Mitigasi**: Pola *Two-Phase Commit with Server-Authoritative Timeout*. Status transaksi disimpan sebagai `PENDING` di PostgreSQL dengan `expires_at`. Sebuah background orchestrator secara otomatis melakukan auto-revert (membatalkan settlement) jika waktu kadaluarsa terlampaui tanpa dependent event yang valid.

### 2. Phantom Negative Balance via Micro-Transactions
- **Skenario**: Autonomous agent memicu 100 aksi paralel secara simultan, masing-masing meminta pemotongan 1 unit Gold dari akun yang hanya memiliki 10 unit Gold.
- **Dampak Kegagalan**: Pada isolasi level default `Read Committed`, kueri validasi `if account.balance >= 1` lolos untuk semua 100 thread karena membaca snapshot yang belum terpotong, menyebabkan saldo minus (`-90 Gold`).
- **Mitigasi**:
  1. Penegakan PostgreSQL Table Constraint: `CHECK (balance >= 0)`.
  2. Penggunaan `SELECT ... FOR UPDATE` terurut atau OCC version checking:
     ```sql
     UPDATE accounts 
     SET balance = balance - 1, version = version + 1 
     WHERE id = :id AND version = :expected_version AND balance >= 1;
     ```

### 3. Redis Cache Invalidation Drift (Split-Brain Read Model)
- **Skenario**: Mutasi saldo berhasil di-commit di PostgreSQL, namun proses aplikasi mati seketika sebelum mengeksekusi instruksi `redis.set(cache_key, new_balance)`.
- **Dampak Kegagalan**: Membaca saldo dari cache menyajikan nilai lama (*stale state*), memungkinkan agent mengeksekusi aksi berbasis data kadaluarsa.
- **Mitigasi**: Jangan pernah mengandalkan manual cache updates dalam handler transaksi aplikasi (*Dual-Write Anti-Pattern*). Gunakan arsitektur **Change Data Capture (CDC)** (misal: Debezium) yang membaca write-ahead log (WAL) PostgreSQL dan memancarkan update event ke Redis/Kafka secara asinkron namun bergaransi atomik terhadap database commit.

---

## 8. Trade-offs & Alternatif Solusi

```
                       LATENCY vs. INTEGRITY TRADEOFF
                              
 Latency: < 1ms                                             Latency: > 20ms
 Consistency: Weak                                          Consistency: Strict ACID
 Audit: None                                                Audit: Full Provenance
 
 [Pure Redis Memory] <---> [Write-Behind Cache] <---> [Transactional Ledger]
 (Ephemeral ticks)         (Batch Queue Engine)        (Double-Entry RDBMS)
      │                            │                            │
      │ Skenario:                  │ Skenario:                  │ Skenario:
      │ Transform, Aggro,          │ Player XP, Kill Count,     │ Hard Currency, Real-Money
      │ Spatial Physics            │ Drop Rate Tracking         │ Auction House, Trade Items
```

### Analisis Komparatif

1. **Transactional Outbox Pattern vs. Two-Phase Commit (2PC / XA Transactions)**:
   - *2PC*: Membutuhkan koordinator transaksi terdistribusi yang memblokir semua node sampai seluruh storage (misal: Postgres + Redis) siap. Tidak cocok untuk game server karena latensi tinggi dan rentan ketersediaan (*availability killer* jika satu node down).
   - *Transactional Outbox*: Menyimpan pesan event ke tabel outbox di dalam transaksi RDBMS yang sama. Event relay worker memancarkan event ke message broker secara asinkron. Memberikan performa optimal dengan garansi *At-Least-Once Delivery*.

2. **In-Memory Volatile Simulation vs. Persistent Tick Mutation**:
   - Menulis setiap tick ke database disk mustahil dicapai pada rate 60 Hz.
   - Solusi: Seluruh kalkulasi combat dan navigasi agent dilakukan sepenuhnya di *volatile memory* (RAM). Persistensi hanya terjadi pada state transitions: `Engage`, `Loot_Acquired`, `Death`, atau snapshot periodik setiap interval $\Delta T = 60\text{ detik}$.

---

## 9. Best Practices & Standard Industri

1. **Immutable Historical Records**:
   Tabel `ledger_entries` tidak boleh memiliki izin SQL `UPDATE` atau `DELETE`. Batasi akses level database (*Postgres Roles*):
   ```sql
   REVOKE UPDATE, DELETE ON TABLE ledger_entries FROM game_server_role;
   GRANT SELECT, INSERT ON TABLE ledger_entries FROM game_server_role;
   ```
2. **Numeric Precision Safeguards**:
   Hindari penggunaan tipe data floating point IEEE 754 (`FLOAT`, `DOUBLE`) untuk nilai mata uang. Gunakan fixed-point arbitrary precision: `NUMERIC(24, 4)` atau integer skala mikro/nano ($1\text{ Gold} = 10^6\text{ Satuan Basis}$) guna mencegah eksploitasi akumulasi error pembulatan.
3. **Idempotency Key Lifespan**:
   Idempotency key wajib dibuat oleh pemrakarsa transaksi (Client/Agent) menggunakan UUID v4 yang dipadukan dengan hash isi payload transaksi. Simpan key di Redis dengan TTL minimal 24 jam untuk menolak replikasi request akibat network retry.
4. **Circuit Breakers on Ledger Spikes**:
   Terapkan *token bucket rate limiter* per agent. Jika anomali logic menyebabkan autonomous agent mengeksekusi lebih dari 50 mutasi/detik, putus koneksi agent secara otomatis ke safe mode untuk mengisolasi potensi *infinite loop bug*.

---

## 10. Hands-on Lab Exercise

### Deskripsi Lab
Anda ditugaskan mengimplementasikan pipeline transfer dana otonom antar dua AI Agent yang aman terhadap *concurrency race condition* dan *double-spending*, dengan memverifikasi bahwa total ekuitas sistem tetap nol (*Zero-Sum Conservation*).

### Setup Environment
1. Jalankan instance PostgreSQL dan Redis menggunakan Docker:
   ```bash
   docker run -d --name lab-postgres -e POSTGRES_USER=game_dev -e POSTGRES_PASSWORD=game_dev_pwd -e POSTGRES_DB=game_economy -p 5432:5432 postgres:16-alpine
   docker run -d --name lab-redis -p 6379:6379 redis:7-alpine
   ```
2. Pasang dependensi Python:
   ```bash
   pip install sqlalchemy asyncpg redis pydantic pytest pytest-asyncio
   ```

### Task 1: Setup DDL Constraints
Buat file `setup_db.sql` dan eksekusi pada instance database:
```sql
CREATE TABLE accounts (
    id UUID PRIMARY KEY,
    owner_id VARCHAR(64) NOT NULL,
    currency VARCHAR(12) NOT NULL,
    balance NUMERIC(24, 4) NOT NULL DEFAULT 0.0000,
    version INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT chk_account_balance_non_negative CHECK (balance >= 0.0000),
    CONSTRAINT uq_owner_currency UNIQUE (owner_id, currency)
);

CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE ledger_entries (
    id UUID PRIMARY KEY,
    transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE RESTRICT,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    amount NUMERIC(24, 4) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT chk_ledger_amount_not_zero CHECK (amount <> 0.0000)
);

-- Indexing for Ledger Analytics
CREATE INDEX idx_ledger_entries_acc_tx ON ledger_entries(account_id, transaction_id);
```

### Task 2: Eksekusi Uji Penetrasi Konkurensi
Gunakan file implementasi `test_ledger.py` dari **Bagian 6.3**. 

Jalankan script untuk menguji 50 mutasi transfer paralel antara dua akun yang saling mentransfer dana secara acak:
```bash
python test_ledger.py
```

### Expected Output
```text
Hasil Eksekusi Transaksi: OK=50, Failure=0
Saldo Akhir Alpha: 1000.0000
Saldo Akhir Beta: 1000.0000
```
Verifikasi bahwa:
1. Tidak ada error `DeadlockDetectedError` yang lolos ke level worker aplikasi (teratasi oleh *Resource Ordering*).
2. Saldo total tetap tepat `2000.0000 GOLD`.

### Verification Query
Jalankan kueri SQL berikut untuk memverifikasi konsistensi *Double-Entry*:
```sql
-- Seluruh total entry dalam sistem WAJIB menghasilkan delta 0
SELECT SUM(amount) AS total_delta FROM ledger_entries;
```
Output yang valid:
```text
 total_delta 
-------------
      0.0000
```

```sql
-- Bandingkan saldo terhitung dari ledger entries dengan snapshot di tabel accounts
SELECT 
    a.id, 
    a.balance AS snapshot_balance, 
    COALESCE(SUM(le.amount), 0) AS calculated_balance
FROM accounts a
LEFT JOIN ledger_entries le ON a.id = le.account_id
GROUP BY a.id, a.balance;
```
Output yang valid: Nilai `snapshot_balance` identik dengan `calculated_balance` untuk seluruh akun. Jika terdapat diskrepansi, telah terjadi korupsi integritas data ekonomi.