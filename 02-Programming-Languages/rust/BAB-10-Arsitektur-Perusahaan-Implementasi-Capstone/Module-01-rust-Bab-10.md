# Modul Pembelajaran: Arsitektur Perusahaan & Implementasi Capstone (Rust)

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran:** 02-Programming-Languages
*   **Mata Pelajaran:** Pemrograman Sistem Rust Tingkat Lanjut
*   **Bab:** 10 — Arsitektur Perangkat Lunak Skala Besar & Capstone
*   **Modul:** 01 — Arsitektur Perusahaan & Implementasi Capstone
*   **Tingkat Kesulitan:** Advanced / Production-Grade
*   **Prasyarat:** Pemahaman mendalam tentang *Ownership/Borrowing*, *Concurrency* (`tokio`, `async/await`), *Trait System* & *Dynamic/Static Dispatch*, *Error Handling* (`thiserror`, `anyhow`), serta *Smart Pointers* (`Arc`, `Box`, `Pin`).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1.  **Merancang** struktur monorepo/workspace Rust berbasis *Hexagonal Architecture (Ports and Adapters)* dan *Clean Architecture* yang memisahkan *domain logic* murni dari *I/O driver*.
2.  **Menerapkan** pola *Inversion of Control* (IoC) dan *Dependency Injection* (DI) idiomatik Rust menggunakan *trait abstractions* tanpa mengorbankan performa *zero-cost abstraction*.
3.  **Mengisolasi** efek samping I/O (Database, Messaging Queue, HTTP) menggunakan *Contract Interfaces* (Traits) dan tipe data Domain yang kaya (*Rich Domain Model* menggunakan *Newtype Pattern*).
4.  **Mengimplementasikan** *Transactional Outbox Pattern* dan penanganan *Distributed Errors* berbasis *strongly typed system* Rust.
5.  **Membangun** proyek *Capstone* berskala *production-ready* yang siap di-*deploy* dengan *structured observability* (`tracing`), *graceful shutdown*, dan *health probes*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam ekosistem bahasa pemrograman berorientasi objek tradisional (seperti Java atau C#), arsitektur perusahaan sering kali bergantung pada *reflection*, *runtime dynamic proxies*, dan kontainer IoC otomatis (seperti Spring Context atau .NET DI Container).

```
Paradigma OOP Klasik (Runtime Dynamic):
[ Interface ] <--- (Runtime Dynamic Proxy / Reflection) <--- [ Concrete Class ]

Paradigma Rust Enterprise (Compile-Time Concrete):
[ Trait ] <--- (Compile-Time Monomorphization / Static Dispatch) <--- [ Concrete Struct ]
                atau (Explicit Arc<dyn Trait> Dynamic Dispatch)
```

Di Rust:
1.  **Kompilator Adalah Arsitek Pertama:** *Type system* bukan hanya alat validasi variabel, melainkan instrumen untuk menegakkan *invariant* arsitektural. Jika suatu status sistem tidak valid (misal: entitas order dibayar sebelum divalidasi), status tersebut harus mustahil direpresentasikan dalam *type level* (*Make Illegal States Unrepresentable*).
2.  **Explicit Over Implicit:** Tidak ada injeksi dependensi "gaib" (*no magic annotations*). Pengkabelan (*wiring*) komponen sistem dilakukan secara eksplisit pada *composition root* (biasanya di `main.rs`), memberikan visibilitas penuh atas siklus hidup dan *ownership* memori.
3.  **Ports and Adapters Alami:** Rust *Traits* bertindak sempurna sebagai *Ports* (kontrak batas), sedangkan *Structs* bersama blok `impl Trait for Struct` bertindak sebagai *Adapters*. Inti bisnis (*Core Domain*) tidak boleh memiliki dependensi crate eksternal selain dependensi standar atau primitif fundamental.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur *Ports and Adapters* (Hexagonal) yang diadaptasi untuk Rust Cargo Workspaces:

```
+-----------------------------------------------------------------------------------+
|                              CARGO WORKSPACE ROOT                                 |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   |                           ADAPTERS: DRIVING / INBOUND                     |   |
|   |     crates/api_http (Axum/Actix)            crates/cli                    |   |
|   +-------------------------------------+-------------------------------------+   |
|                                         |                                         |
|                                         v                                         |
|   +---------------------------------------------------------------------------+   |
|   |                     APPLICATION LAYER (crates/app)                        |   |
|   |  - Use Cases / Command Handlers / Query Handlers                          |   |
|   |  - Inbound Ports (Service Traits) & Outbound Ports (Repository Traits)    |   |
|   +-------------------------------------+-------------------------------------+   |
|                                         |                                         |
|                                         v                                         |
|   +---------------------------------------------------------------------------+   |
|   |                       DOMAIN LAYER (crates/domain)                        |   |
|   |  - Pure Domain Entities & Aggregates                                      |   |
|   |  - Value Objects (Newtypes)                                               |   |
|   |  - Domain Events & Domain Invariants                                      |   |
|   |  - NO EXTERNAL I/O DEPENDENCIES (Zero async, zero sqlx, zero network)     |   |
|   +-------------------------------------+-------------------------------------+   |
|                                         ^                                         |
|                                         | implements Outbound Ports               |
|   +-------------------------------------+-------------------------------------+   |
|   |                   ADAPTERS: DRIVEN / OUTBOUND                             |   |
|   |     crates/infra_postgres (sqlx)            crates/infra_kafka (rdkafka)  |   |
|   +---------------------------------------------------------------------------+   |
|                                                                                   |
+-----------------------------------------------------------------------------------+
                                         ^
                                         | Injeksi Dependensi Konkret
+----------------------------------------+------------------------------------------+
|                          COMPOSITION ROOT (src/main.rs)                           |
+-----------------------------------------------------------------------------------+
```

### Alur Eksekusi Data (Runtime Request Lifecycle)

```
[HTTP Client Request]
       |
       v
[Axum Router / Handler] (Inbound Adapter)
       |
       | Deserialisasi DTO & Validasi Sintaks
       v
[Use Case / Command Handler] (Application Service)
       |
       +---> [Domain Entity / Aggregate] (Business Rules & State Mutation)
       |
       +---> [Repository Port (Trait)] (Penyimpanan Status)
                   |
                   v (Injeksi Polimorfik)
             [PostgreSQL Adapter (SQLx)] (Driven Adapter)
                   |
                   v
             [Physical Database]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Pembagian Crate dalam Cargo Workspace

Struktur hierarki folder monorepo enterprise:

```text
enterprise-system/
├── Cargo.toml (Virtual Workspace)
├── crates/
│   ├── domain/               # Zero dependencies (kecuali serde/uuid optional)
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── entity/
│   │       └── value_objects/
│   ├── application/          # Use Cases + Port Definitions
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── ports/
│   │       └── use_cases/
│   ├── infra_postgres/       # Adapter Database (SQLx)
│   │   ├── Cargo.toml
│   │   └── src/
│   ├── api_http/             # Adapter Web API (Axum)
│   │   ├── Cargo.toml
│   │   └── src/
└── app_server/               # Composition Root (Binary)
    ├── Cargo.toml
    └── src/
        └── main.rs
```

### 2. Mekanisme Dynamic vs Static Dispatch pada Ports

Dalam arsitektur enterprise, port abstraksi dapat diimplementasikan dengan dua cara:

*   **Static Dispatch (`impl Trait` atau Generics `<T: Repository>`):**
    *   *Mekanisme:* Monomorphization saat *compile time*. Kompilator menduplikasi kode fungsi untuk setiap tipe konkret.
    *   *Kelebihan:* *Zero runtime overhead*, inlining fungsi, performa optimal.
    *   *Kekurangan:* *Binary bloat*, waktu kompilasi bertambah, struktur tipe menjadi sangat berjenjang (*generic pollution* pada Use Case).
*   **Dynamic Dispatch (`Box<dyn Trait>` atau `Arc<dyn Trait>`):**
    *   *Mekanisme:* Melibatkan *vtable pointer* (pointer ke tabel fungsi virtual) dan pointer ke data instance.
    *   *Kelebihan:* Pemisahan batas kompilasi yang bersih, arsitektur lebih fleksibel, modularitas mendekati OOP tanpa polusi generik.
    *   *Trade-off:* Sedikit penurunan performa akibat dereferensi pointer ganda (*indirect function call*) dan hambatan kompilator untuk melakukan *inlining*.

Untuk tingkat enterprise, kombinasi penggunaan **`Arc<dyn Trait + Send + Sync>`** sering kali menjadi standar industri karena kemudahan *wiring*, thread-safe sharing antar-*worker* tokio, dan perbedaan performa nanodetik yang tidak signifikan dibandingkan latensi I/O jaringan/database.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Domain-Driven Design (DDD) Invariants via Rust Type System

Dalam domain perbankan enterprise, sebuah akun tidak boleh memiliki saldo negatif jika tipe akunnya adalah `Debit`. Pada bahasa lain, aturan ini divalidasi dengan melemparkan runtime exception:

```rust
// Pendekatan Primitif (Anti-pattern di Rust):
struct Account {
    id: String,
    balance: f64, // Floating point error, unconstrained value
}
```

Dalam Rust Enterprise Architecture, kita memanfaatkan **Parse, Don't Validate**:

```rust
// Idiom Enterprise: Newtype Pattern & Non-Exhaustive States
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Money(u64); // Nilai dalam unit terkecil (sen/rupiah murni) untuk mencegah precision loss

impl Money {
    pub fn new(amount: u64) -> Self {
        Self(amount)
    }
    
    pub fn amount(&self) -> u64 {
        self.0
    }
}
```

### Type-State Pattern untuk Status Entitas

Entity yang memiliki *state machine* kompleks (misal: `Draft -> Submitted -> Approved -> Settled`) tidak boleh disimpan hanya dalam variabel `status: String`. Gunakan *Type-State Pattern* untuk menjamin transisi state dieksekusi dengan aman pada fase kompilasi:

```rust
pub struct Draft;
pub struct Submitted;
pub struct Approved;

pub struct Order<State> {
    pub id: uuid::Uuid,
    pub amount: Money,
    pub state: std::marker::PhantomData<State>,
}

impl Order<Draft> {
    pub fn new(amount: Money) -> Self {
        Self {
            id: uuid::Uuid::new_v4(),
            amount,
            state: std::marker::PhantomData,
        }
    }

    pub fn submit(self) -> Order<Submitted> {
        Order {
            id: self.id,
            amount: self.amount,
            state: std::marker::PhantomData,
        }
    }
}

impl Order<Submitted> {
    pub fn approve(self) -> Order<Approved> {
        Order {
            id: self.id,
            amount: self.amount,
            state: std::marker::PhantomData,
        }
    }
}
```
*Dampak arsitektur:* Tidak mungkin memanggil method yang khusus untuk `Approved` jika order masih dalam kondisi `Draft`. Kompiler menolaknya langsung di proses build.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL (Step-by-step)

Di bawah ini adalah implementasi minimalis satu kesatuan alur dari Domain, Port Abstraction, Service Implementation, hingga Composition Root menggunakan `Arc<dyn Trait>`.

```rust
use std::sync::Arc;
use thiserror::Error;

// ==========================================
// 1. DOMAIN LAYER
// ==========================================
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccountId(uuid::Uuid);

impl AccountId {
    pub fn new() -> Self {
        Self(uuid::Uuid::new_v4())
    }
    pub fn from_uuid(id: uuid::Uuid) -> Self {
        Self(id)
    }
    pub fn value(&self) -> uuid::Uuid {
        self.0
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Account {
    id: AccountId,
    balance: u64,
}

#[derive(Error, Debug)]
pub enum DomainError {
    #[error("Saldo tidak mencukupi untuk penarikan: tersedia {available}, diminta {requested}")]
    InsufficientFunds { available: u64, requested: u64 },
}

impl Account {
    pub fn new(id: AccountId, balance: u64) -> Self {
        Self { id, balance }
    }

    pub fn withdraw(&mut self, amount: u64) -> Result<(), DomainError> {
        if self.balance < amount {
            return Err(DomainError::InsufficientFunds {
                available: self.balance,
                requested: amount,
            });
        }
        self.balance -= amount;
        Ok(())
    }

    pub fn balance(&self) -> u64 {
        self.balance
    }

    pub fn id(&self) -> &AccountId {
        &self.id
    }
}

// ==========================================
// 2. APPLICATION LAYER (PORTS)
// ==========================================
#[derive(Error, Debug)]
pub enum RepositoryError {
    #[error("Entitas tidak ditemukan")]
    NotFound,
    #[error("Koneksi basis data terputus: {0}")]
    DatabaseFailure(String),
}

#[async_trait::async_trait]
pub trait AccountRepository: Send + Sync {
    async fn find_by_id(&self, id: &AccountId) -> Result<Account, RepositoryError>;
    async fn save(&self, account: &Account) -> Result<(), RepositoryError>;
}

// Use Case (Application Service)
pub struct WithdrawFundsUseCase {
    repo: Arc<dyn AccountRepository>,
}

#[derive(Error, Debug)]
pub enum UseCaseError {
    #[error("Kesalahan Domain: {0}")]
    Domain(#[from] DomainError),
    #[error("Kesalahan Repositori: {0}")]
    Repository(#[from] RepositoryError),
}

impl WithdrawFundsUseCase {
    pub fn new(repo: Arc<dyn AccountRepository>) -> Self {
        Self { repo }
    }

    pub async fn execute(&self, id: AccountId, amount: u64) -> Result<(), UseCaseError> {
        let mut account = self.repo.find_by_id(&id).await?;
        account.withdraw(amount)?;
        self.repo.save(&account).await?;
        Ok(())
    }
}

// ==========================================
// 3. INFRASTRUCTURE ADAPTER (MOCK/IN-MEMORY)
// ==========================================
use std::collections::HashMap;
use tokio::sync::RwLock;

pub struct InMemoryAccountRepository {
    storage: RwLock<HashMap<uuid::Uuid, u64>>,
}

impl InMemoryAccountRepository {
    pub fn new() -> Self {
        Self {
            storage: RwLock::new(HashMap::new()),
        }
    }
}

#[async_trait::async_trait]
impl AccountRepository for InMemoryAccountRepository {
    async fn find_by_id(&self, id: &AccountId) -> Result<Account, RepositoryError> {
        let read_guard = self.storage.read().await;
        match read_guard.get(&id.value()) {
            Some(&bal) => Ok(Account::new(id.clone(), bal)),
            None => Err(RepositoryError::NotFound),
        }
    }

    async fn save(&self, account: &Account) -> Result<(), RepositoryError> {
        let mut write_guard = self.storage.write().await;
        write_guard.insert(account.id().value(), account.balance());
        Ok(())
    }
}

// ==========================================
// 4. COMPOSITION ROOT
// ==========================================
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Wiring dependencies
    let repo = Arc::new(InMemoryAccountRepository::new());
    
    // Seed initial state
    let target_id = AccountId::new();
    repo.save(&Account::new(target_id.clone(), 1_000_000)).await?;

    let use_case = WithdrawFundsUseCase::new(repo.clone());

    // Execute application command
    println!("Mengeksekusi penarikan dana...");
    use_case.execute(target_id.clone(), 300_000).await?;

    let updated_account = repo.find_by_id(&target_id).await?;
    println!("Sisa saldo akun: IDR {}", updated_account.balance());

    Ok(())
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 7–21:** Implementasi *Newtype* `AccountId(uuid::Uuid)`. Mengenkapsulasi identitas agar terhindar dari *primitive obsession*. Tidak memungkinkan `UserId` tertukar dengan `AccountId` di parameter fungsi.
*   **Baris 24–49:** Domain Model murni (`Account`). Fungsi `withdraw` menegakkan aturan invariant bisnis: mutasi hanya berhasil bila saldo memenuhi syarat. Mengembalikan domain error bertipe (`DomainError::InsufficientFunds`), bebas dari framework atau asynchronous runtime.
*   **Baris 54–67:** Definisi *Outbound Port* melalui `#[async_trait::async_trait] pub trait AccountRepository: Send + Sync`. Kontrak ini menyatakan bahwa layer aplikasi membutuhkan dependensi persistensi yang aman dikirim melintasi batas thread tokio (`Send + Sync`).
*   **Baris 70–93:** Application Service `WithdrawFundsUseCase`. Menggunakan komposisi `Arc<dyn AccountRepository>`. Pola injeksi dependensi ini memungkinkan *loose coupling* penuh: layer use case tidak peduli apakah data disimpan di Postgres, Redis, atau InMemory.
*   **Baris 98–130:** Adapter konkret `InMemoryAccountRepository`. Menggunakan `tokio::sync::RwLock` untuk simulasi thread-safe concurrency. Adapter ini mengimplementasikan trait `AccountRepository`.
*   **Baris 135–154:** *Composition Root* di `main()`. Merupakan satu-satunya tempat di mana tipe adapter konkret diinisialisasi dan dihubungkan ke application service.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Skenario: Sistem Dompet Digital FinTech (High-Throughput Ledger)

Sistem FinTech menghadapi tiga tantangan kritis:
1.  **Double-Spending Mitigation:** Permintaan penarikan dana konkuren yang datang dalam rentang milidetik yang sama.
2.  **Audit Trail Kepatuhan Regulasi:** Setiap perpindahan dana harus menghasilkan jurnal ganda (*Double-Entry Bookkeeping*) yang *immutable*.
3.  **Database Outage Resilience:** Sistem pembayaran pihak ketiga (Payment Gateway) harus menerima webhook notifikasi settlement bahkan saat antrean penulisan database utama sedang padat, menggunakan pola *Transactional Outbox*.

### Arsitektur Solusi
*   Gunakan transaksi berbasis serialisasi eksplisit dengan **Pessimistic Locking (`SELECT FOR UPDATE`)** atau *Optimistic Locking* via version tracking dalam domain entity.
*   Pemisahan batas transactional boundaries menggunakan *Unit of Work* pattern idiomatik Rust.
*   Pemisahan command API menggunakan Axum framework dan persistensi relasional menggunakan `sqlx` dengan connection pooling (`PgPool`).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi skala industri untuk layer domain perbankan, port Unit of Work, dan integrasi Axum Web.

### Struktur Proyek Capstone

```text
├── Cargo.toml
└── src/
    ├── domain.rs
    ├── ports.rs
    ├── service.rs
    ├── adapter_sqlx.rs
    ├── api.rs
    └── main.rs
```

#### File: `Cargo.toml`
```toml
[package]
name = "enterprise_fintech"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.38", features = ["full"] }
axum = { version = "0.7", features = ["json"] }
sqlx = { version = "0.7", features = ["runtime-tokio-rustls", "postgres", "uuid", "chrono"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
uuid = { version = "1.8", features = ["v4", "serde"] }
thiserror = "1.0"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
async-trait = "0.1"
```

#### File: `src/domain.rs`
```rust
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct AccountId(pub Uuid);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct TransactionId(pub Uuid);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Money(pub i64); // Signed untuk kemudahan jurnal akuntansi

impl Money {
    pub fn zero() -> Self {
        Self(0)
    }
    pub fn is_positive(&self) -> bool {
        self.0 > 0
    }
}

#[derive(Error, Debug)]
pub enum LedgerError {
    #[error("Saldo tidak mencukupi untuk akun: {0:?}")]
    InsufficientFunds(AccountId),
    #[error("Nilai transfer harus positif, diterima: {0}")]
    InvalidAmount(i64),
    #[error("Akun sumber dan akun tujuan tidak boleh sama")]
    IdenticalAccounts,
}

#[derive(Debug, Clone)]
pub struct LedgerAccount {
    pub id: AccountId,
    pub balance: Money,
    pub version: i64, // Optimistic Locking
}

impl LedgerAccount {
    pub fn debit(&mut self, amount: Money) -> Result<(), LedgerError> {
        if !amount.is_positive() {
            return Err(LedgerError::InvalidAmount(amount.0));
        }
        if self.balance.0 < amount.0 {
            return Err(LedgerError::InsufficientFunds(self.id));
        }
        self.balance.0 -= amount.0;
        self.version += 1;
        Ok(())
    }

    pub fn credit(&mut self, amount: Money) -> Result<(), LedgerError> {
        if !amount.is_positive() {
            return Err(LedgerError::InvalidAmount(amount.0));
        }
        self.balance.0 += amount.0;
        self.version += 1;
        Ok(())
    }
}
```

#### File: `src/ports.rs`
```rust
use crate::domain::{AccountId, LedgerAccount, LedgerError, Money};
use async_trait::async_trait;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum StorageError {
    #[error("Database error: {0}")]
    Database(String),
    #[error("Entitas tidak ditemukan")]
    NotFound,
    #[error("Konflik konkurensi (Optimistic Lock Terpicu)")]
    ConcurrencyConflict,
}

#[async_trait]
pub trait LedgerRepository: Send + Sync {
    async fn get_account_for_update(&mut self, id: AccountId) -> Result<LedgerAccount, StorageError>;
    async fn update_account(&mut self, account: &LedgerAccount) -> Result<(), StorageError>;
    async fn record_entry(&mut self, from: AccountId, to: AccountId, amount: Money) -> Result<(), StorageError>;
}

// Unit of Work Port untuk mengontrol batas atomisitas transaksi
#[async_trait]
pub trait UnitOfWork: Send + Sync {
    async fn execute_transaction<F, R>(&self, f: F) -> Result<R, AppError>
    where
        F: for<'a> FnOnce(&'a mut dyn LedgerRepository) -> futures::future::BoxFuture<'a, Result<R, AppError>> + Send;
}

#[derive(Error, Debug)]
pub enum AppError {
    #[error("Domain error: {0}")]
    Domain(#[from] LedgerError),
    #[error("Storage error: {0}")]
    Storage(#[from] StorageError),
    #[error("Internal infrastructure failure: {0}")]
    Internal(String),
}
```

#### File: `src/service.rs`
```rust
use crate::domain::{AccountId, LedgerError, Money};
use crate::ports::{AppError, UnitOfWork};
use std::sync::Arc;

pub struct TransferService {
    uow: Arc<dyn UnitOfWork>,
}

impl TransferService {
    pub fn new(uow: Arc<dyn UnitOfWork>) -> Self {
        Self { uow }
    }

    pub async fn transfer(&self, from: AccountId, to: AccountId, amount: Money) -> Result<(), AppError> {
        if from == to {
            return Err(AppError::Domain(LedgerError::IdenticalAccounts));
        }

        self.uow.execute_transaction(move |repo| {
            Box::pin(async move {
                // Ambil state entitas dengan pessimistic/transactional guard
                let mut source_acc = repo.get_account_for_update(from).await?;
                let mut dest_acc = repo.get_account_for_update(to).await?;

                // Mutasi Domain Rules
                source_acc.debit(amount)?;
                dest_acc.credit(amount)?;

                // Persistensi Perubahan
                repo.update_account(&source_acc).await?;
                repo.update_account(&dest_acc).await?;
                repo.record_entry(from, to, amount).await?;

                Ok(())
            })
        }).await
    }
}
```

#### File: `src/api.rs`
```rust
use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::post,
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

use crate::domain::{AccountId, Money};
use crate::ports::AppError;
use crate::service::TransferService;

#[derive(Deserialize)]
pub struct TransferRequest {
    pub from_account_id: Uuid,
    pub to_account_id: Uuid,
    pub amount: i64,
}

#[derive(Serialize)]
pub struct ApiResponse<T> {
    pub success: bool,
    pub data: Option<T>,
    pub message: Option<String>,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, err_msg) = match self {
            AppError::Domain(ref e) => (StatusCode::UNPROCESSABLE_ENTITY, e.to_string()),
            AppError::Storage(ref e) => (StatusCode::CONFLICT, e.to_string()),
            AppError::Internal(ref e) => (StatusCode::INTERNAL_SERVER_ERROR, e.clone()),
        };

        let body = Json(ApiResponse::<()> {
            success: false,
            data: None,
            message: Some(err_msg),
        });

        (status, body).into_response()
    }
}

pub struct AppState {
    pub transfer_service: Arc<TransferService>,
}

pub fn create_router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/api/v1/transfers", post(handle_transfer))
        .with_state(state)
}

async fn handle_transfer(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<TransferRequest>,
) -> Result<impl IntoResponse, AppError> {
    state
        .transfer_service
        .transfer(
            AccountId(payload.from_account_id),
            AccountId(payload.to_account_id),
            Money(payload.amount),
        )
        .await?;

    Ok((
        StatusCode::OK,
        Json(ApiResponse {
            success: true,
            data: Some("Transfer completed successfully"),
            message: None,
        }),
    ))
}
```

#### File: `src/main.rs` (Composition Root & Production Server Bootstrap)
```rust
use std::sync::Arc;
use tokio::net::TcpListener;
use tracing::info;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod domain;
mod ports;
mod service;
mod api;

// Mock UnitOfWork untuk demonstrasi runnable langsung
struct MockLedgerRepository;

#[async_trait::async_trait]
impl ports::LedgerRepository for MockLedgerRepository {
    async fn get_account_for_update(&mut self, id: domain::AccountId) -> Result<domain::LedgerAccount, ports::StorageError> {
        Ok(domain::LedgerAccount {
            id,
            balance: domain::Money(5000),
            version: 1,
        })
    }
    async fn update_account(&mut self, _account: &domain::LedgerAccount) -> Result<(), ports::StorageError> {
        Ok(())
    }
    async fn record_entry(&mut self, _from: domain::AccountId, _to: domain::AccountId, _amount: domain::Money) -> Result<(), ports::StorageError> {
        Ok(())
    }
}

struct MockUnitOfWork;

#[async_trait::async_trait]
impl ports::UnitOfWork for MockUnitOfWork {
    async fn execute_transaction<F, R>(&self, f: F) -> Result<R, ports::AppError>
    where
        F: for<'a> FnOnce(&'a mut dyn ports::LedgerRepository) -> futures::future::BoxFuture<'a, Result<R, ports::AppError>> + Send,
    {
        let mut repo = MockLedgerRepository;
        f(&mut repo).await
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. Inisialisasi Observabilitas
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("Memulai inisialisasi sistem Fintech Enterprise...");

    // 2. Inisialisasi Driven Adapters
    let uow = Arc::new(MockUnitOfWork);

    // 3. Inisialisasi Application Services
    let transfer_service = Arc::new(service::TransferService::new(uow));

    // 4. Inisialisasi State Aplikasi
    let state = Arc::new(api::AppState { transfer_service });

    // 5. Inisialisasi Inbound Adapter (HTTP Axum Router)
    let app = api::create_router(state);

    // 6. Binding Socket Listener & Graceful Shutdown
    let addr = "0.0.0.0:8080";
    let listener = TcpListener::bind(addr).await?;
    info!("Server listening di http://{}", addr);

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    info!("Server berhasil dimatikan secara aman (gracefully terminated).");
    Ok(())
}

async fn shutdown_signal() {
    let ctrl_c = async {
        tokio::signal::ctrl_c()
            .await
            .expect("Gagal menginstal handler sinyal CTRL+C");
    };

    #[cfg(unix)]
    let terminate = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("Gagal menginstal handler sinyal SIGTERM")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Arsitektural | Dynamic Dispatch (`Arc<dyn Trait>`) | Static Dispatch (`Service<T: Trait>`) | Anemic Data (No Hexagonal) |
| :--- | :--- | :--- | :--- |
| **Waktu Kompilasi** | Cepat, monomorphization minimal | Lambat, kode berulang dikompilasi | Sangat Cepat |
| **Ukuran Binary** | Kecil dan terprediksi | Membengkak (*Binary Bloat*) | Kecil |
| **Performa Eksekusi** | Sedikit degradasi (vtable lookup) | Maksimal (*Zero-Cost*, Auto-inlining) | Maksimal |
| **Kemudahan Pemeliharaan** | Sangat Bersih, decouled | Kompleks (*Generic Type Pollution*) | Buruk (Tight Coupling) |
| **Uji Unit (Mocking)** | Sangat mudah (Mock struct apa saja) | Sulit dikonfigurasi saat generic bertingkat | Sulit tanpa I/O asli |

### Mengapa memilih `Arc<dyn Trait>` untuk Core Enterprise?
Pada aplikasi berbasis I/O (seperti perbankan, e-commerce, ERP), waktu eksekusi CPU pada *vtable dispatch* berkisar antara **1–3 nanodetik**, sedangkan operasi basis data Postgres atau transit jaringan memakan waktu **1–20 milidetik (1.000.000–20.000.000 nanodetik)**. Mengorbankan ergonomi kode demi static dispatch murni pada layer I/O enterprise adalah bentuk *premature optimization*.

---

## SEKSI 12 — EDGE CASES & PITFALLS

1.  **Async Trait Object Safety:**
    *   *Problem:* Di Rust pra-1.75, trait dengan method `async fn` tidak dapat dijadikan objek dinamis (`dyn Trait`) karena mengembalikan tipe `impl Future`, yang ukurannya tidak diketahui saat waktu kompilasi (*unsized*).
    *   *Solusi:* Gunakan crate `async-trait` yang mendesugaring kembalian method menjadi `Pin<Box<dyn Future<Output = T> + Send + 'async>>`.
2.  **Deadlock pada Nested In-Memory Concurrency:**
    *   Jika adapter mock menggunakan `tokio::sync::Mutex` atau `RwLock`, memanggil write-lock di dalam use-case yang memanggil write-lock kedua pada task yang sama akan menyebabkan runtime deadlock permanen.
3.  **Tergelincirnya Status Transaksi pada Pool Connection:**
    *   Jika menggunakan `sqlx::Pool`, transaksi dimulai dengan `pool.begin().await?`. Jika referensi koneksi transaksi terlepas dari scope tanpa pemanggilan `tx.commit().await?`, SQLx secara otomatis melakukan *Rollback*. Selalu pastikan error propagation (`?`) dievaluasi dengan benar agar status tidak menggantung.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Membocorkan Tipe Eksternal ke Domain Layer
*   *Kesalahan:* Menggunakan `sqlx::types::BigDecimal` atau `axum::Json` langsung di dalam entitas Domain.
*   *Dampak:* Melanggar aturan Clean Architecture. Domain menjadi terikat secara permanen ke framework eksternal tertentu.
*   *Perbaikan:* Buat *Primitive Wrappers* murni di crate domain, kemudian implementasikan konversi menggunakan trait `From` / `Into` di layer Adapter.

```rust
// SALAH:
// di domain/src/entity.rs
pub struct Invoice {
    pub amount: sqlx::types::BigDecimal, // Domain bocor ke SQLx
}

// BENAR:
// di domain/src/entity.rs
pub struct Invoice {
    pub amount: u64, // Domain murni
}
// di infra_postgres/src/model.rs
impl From<InvoiceRecord> for Invoice { ... }
```

### 2. Dependency Inversion Terbalik
*   *Kesalahan:* Crate Domain bergantung pada Crate Database (`domain -> infra_postgres`).
*   *Perbaikan:* Gunakan Cargo Workspace dependency boundary. Domain tidak boleh mencantumkan adapter pada `Cargo.toml`. Crate infrastructure yang harus bergantung pada domain (`infra_postgres -> domain`).

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Make Illegal States Unrepresentable:**
    Jangan pernah biarkan entitas berada dalam status yang tidak diizinkan oleh domain bisnis. Buat constructor privat (`pub(crate)`) dan gunakan *factory functions* yang mengembalikan `Result<Self, DomainError>`.
2.  **Separate Inbound and Outbound DTOs:**
    Jangan pernah menggunakan Domain Entities langsung sebagai payload respons HTTP atau record tabel SQLx. Pisahkan secara tegas:
    *   `RequestDTO` (API) -> `DomainCommand` (App) -> `DomainEntity` (Domain) -> `DatabaseRecord` (Infra).
3.  **Explicit Layer Boundaries via Cargo Workspaces:**
    Terapkan flag `-D warnings` dan gunakan linting `clippy` di seluruh workspace enterprise:
    ```toml
    # Cargo.toml Root
    [workspace.lints.rust]
    unsafe_code = "forbid"

    [workspace.lints.clippy]
    unwrap_used = "deny"
    expect_used = "deny"
    panic = "deny"
    ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

1.  **Connection Pooling Tuning:**
    Konfigurasikan ukuran pool `sqlx::postgres::PgPoolOptions` berdasarkan persamaan Little's Law dan kapasitas maksimum worker thread Tokio:
    ```rust
    let pool = PgPoolOptions::new()
        .max_connections(50)
        .min_connections(10)
        .acquire_timeout(Duration::from_secs(3))
        .idle_timeout(Duration::from_secs(600))
        .connect(&database_url)
        .await?;
    ```
2.  **Alokasi Heap Nol pada String Manipulation:**
    Gunakan `Cow<'static, str>` atau `compact_str::CompactStr` untuk identifier pendek daripada `std::string::String` guna memanfaatkan *small-string optimization* (SSO) pada stack.

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Pemberantasan Unsafe Code:**
    Terapkan `#![forbid(unsafe_code)]` di root crate Domain dan Application. Komponen enterprise core tidak boleh memiliki celah memory corruption.
2.  **Timing-Attack Resistance:**
    Saat memvalidasi kredensial (seperti API Keys atau hashing password entitas), gunakan komparasi *constant-time*:
    ```rust
    use subtle::ConstantTimeEq;
    pub fn verify_signature(a: &[u8], b: &[u8]) -> bool {
        a.ct_eq(b).into()
    }
    ```
3.  **Safe Deserialization Limits:**
    Lindungi endpoint HTTP dari serangan DoS berbasis Payload Memory Inflation dengan membatasi request size di layer Axum:
    ```rust
    use axum::extract::DefaultBodyLimit;
    // Maksimum payload JSON hanya 2 Megabyte
    let app = app.layer(DefaultBodyLimit::max(2 * 1024 * 1024));
    ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Sistem enterprise wajib menerapkan *Distributed Tracing Context*:

```rust
#[tracing::instrument(
    name = "transfer_funds",
    skip(self, uow),
    fields(
        sender_id = %from.0,
        receiver_id = %to.0,
        amount = %amount.0
    )
)]
pub async fn transfer(&self, from: AccountId, to: AccountId, amount: Money) -> Result<(), AppError> {
    tracing::info!("Memulai proses transfer antar entitas");
    // Seluruh log di dalam fungsi ini membawa metadata context trace_id
    Ok(())
}
```

*Format Log JSON untuk Produksi (Grafana/Loki/Datadog):*
```rust
tracing_subscriber::registry()
    .with(tracing_subscriber::EnvFilter::from_default_env())
    .with(tracing_subscriber::fmt::layer().json())
    .init();
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Pemisahan Tanggung Jawab:**
    *   *Domain:* Rules, Invariants, Entities, Enums (Bebas framework).
    *   *Application:* Use Cases, Orchestration, Inbound/Outbound Port Interfaces.
    *   *Adapters:* HTTP Controllers, Database Implementations, Messaging queues.
    *   *Composition Root:* File `main.rs`, bertanggung jawab mengikat instance menjadi satu struktur hidup.
*   **Pola Abstraksi Port:**
    ```rust
    #[async_trait]
    pub trait PortContract: Send + Sync { ... }
    type DynPort = Arc<dyn PortContract>;
    ```
*   **Prinsip Error Enterprise:**
    *   Gunakan `thiserror` di library internal / layer Domain & Application.
    *   Gunakan `anyhow` hanya di `main.rs` atau top-level execution runner.
    *   Jangan pernah biarkan panicking code (`unwrap()`, `expect()`) lolos ke runtime produksi.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa tujuan utama dari memisahkan *Domain Layer* sehingga tidak memiliki dependensi terhadap *I/O framework* eksternal?**
   * A. Mempercepat proses kompilasi binary akhir menjadi kurang dari 1 detik.
   * B. Memastikan aturan bisnis murni terisolasi, mudah diuji tanpa mocking I/O kompleks, dan bebas dari perubahan framework.
   * C. Mengizinkan compiler Rust mengaktifkan garbage collection secara otomatis.
   * D. Mengurangi konsumsi memori stack hingga 90%.

2. **Mengapa tipe data primitif seperti `f64` tidak disarankan untuk merepresentasikan uang dalam sistem perbankan?**
   * A. Karena `f64` tidak mengimplementasikan trait `Send + Sync`.
   * B. Karena `f64` memiliki batasan presisi floating-point IEEE-754 yang menyebabkan selisih pembulatan desimal.
   * C. Karena `f64` tidak dapat diubah ke format JSON oleh serde.
   * D. Karena memori `f64` dialokasikan secara eksklusif di heap.

3. **Trait bound `Send + Sync` pada sebuah Port Interface (`Arc<dyn Trait + Send + Sync>`) wajib dicantumkan jika:**
   * A. Kode berjalan di multi-threaded asynchronous runtime seperti Tokio.
   * B. Sistem hanya dijalankan pada single-core embedded micro-controller.
   * C. Anda tidak ingin menggunakan pointer vtable dinamis.
   * D. Trait tersebut berisi fungsi bertipe `unsafe fn`.

4. **Karakteristik utama dari *Composition Root* pada Rust Enterprise Architecture adalah:**
   * A. Ditempatkan di dalam layer `Domain` paling dalam.
   * B. Menggunakan macro `#[derive]` untuk menggenerasi database query.
   * C. Tempat di mana dependency konkret diinisialisasi dan diinjeksi ke Application Use Cases (biasanya di `main.rs`).
   * D. Berfungsi sebagai adapter inbound protokol HTTP.

5. **Apa fungsi dari macro `#[from]` yang disediakan oleh crate `thiserror`?**
   * A. Mengonversi tipe data secara otomatis menggunakan reflection runtime.
   * B. Mengimplementasikan trait `std::convert::From` secara otomatis untuk mempermudah propagasi error dengan operator `?`.
   * C. Menghapus jejak error traceback untuk meningkatkan performa CPU.
   * D. Memaksa compiler mengubah runtime panics menjadi string log.

### Soal Tingkat Menengah (Intermediate)

6. **Mengapa penggunaan `Arc<dyn Trait>` umumnya lebih disukai daripada generics mendalam (`UseCase<R: Repository>`) pada layer use-case Axum Handler berukuran besar?**
   * A. `Arc<dyn Trait>` menghilangkan kebutuhan alokasi heap pointer.
   * B. Mengurangi komplikasi tipe (*generic pollution*) pada Web Framework Router dan mencegah ledakan waktu kompilasi (*monomorphization bloat*).
   * C. Karena static dispatch tidak didukung pada compiler Rust edisi 2021 ke atas.
   * D. Dynamic dispatch mengeksekusi kode secara native lebih cepat daripada inline machine instructions.

7. **Pada pola *Type-State Pattern*, bagaimana cara mencegah pemanggilan operasi transaksi pada order yang belum disetujui?**
   * A. Memberikan atribut runtime check dengan loop `while` tak berujung.
   * B. Mengatur method transaksi hanya diimplementasikan untuk tipe `Order<Approved>`, sehingga pemanggilan pada `Order<Draft>` gagal pada saat kompilasi.
   * C. Melemparkan runtime exception via macro `panic!()` di dalam fungsi.
   * D. Menggunakan tipe `Option<Order>` pada database driver.

8. **Kelemahan terbesar saat mengimplementasikan async method di dalam Trait (`async fn`) secara manual tanpa `async-trait` sebelum stabilisasi menyeluruh pada dynamic dispatch adalah:**
   * A. Method tersebut tidak dapat mengembalikan nilai selain integer.
   * B. Trait tersebut kehilangan status *Object Safety* sehingga tidak dapat diinstansiasi menjadi `dyn Trait`.
   * C. Runtime Tokio menolak mengeksekusi thread yang berisi future.
   * D. Kompiler mematikan optimasi SIMD secara otomatis.

9. **Apa kegunaan utama pola *Transactional Outbox Pattern* dalam komunikasi antar sistem microservice?**
   * A. Menyimpan event pengiriman data di tabel basis data lokal dalam transaksi atomis yang sama dengan perubahan status bisnis sebelum dipublikasikan ke message broker eksternal.
   * B. Mengirimkan pesan HTTP langsung ke broker tanpa melibatkan memori disk.
   * C. Menghilangkan ketergantungan terhadap ACID relational databases.
   * D. Mempercepat serialisasi format protoc buffers.

10. **Bagaimana cara mencegah race condition *lost update* saat dua request konkuren mencoba mengurangi saldo dari akun yang sama secara bersamaan?**
    * A. Mengabaikan eksekusi transaksi yang kedua melalui statement `drop()`.
    * B. Menggunakan transactional database locks seperti `SELECT ... FOR UPDATE` (Pessimistic) atau *Version Field checking* (Optimistic Concurrency Control).
    * C. Mengubah tipe variabel akun menjadi `static mut`.
    * D. Mengaktifkan fitur `lazy_static` pada dependency Cargo.

---

### Kunci Jawaban Evaluasi

1. **B** — Isolasi aturan domain mencegah vendor lock-in dan menjaga integritas logika bisnis murni.
2. **B** — Representasi biner IEEE-754 menimbulkan masalah pembulatan; integer berbasis *cents* atau *fixed-point decimal* adalah keharusan.
3. **A** — Tokio menyebarkan *tasks* ke berbagai thread *worker*; data dan pointer abstraksi harus aman dikirim (`Send`) dan diakses referensinya (`Sync`).
4. **C** — Composition Root memegang peran tunggal dalam merakit dependensi konkret ke port use cases.
5. **B** — Macro `#[from]` otomatis meng-generate implementasi `From<SourceError> for TargetError`.
6. **B** — Menghindari *generic pollution* yang menjalar ke seluruh tipe handler API dan mempercepat feedback kompilator.
7. **B** — Kompilator menjamin secara statis bahwa method tidak terdaftar di vtable tipe state lain.
8. **B** — Dynamic dispatch memerlukan *known return size*; compiler tidak dapat menentukan ukuran `impl Future` tanpa box allocation (*Trait Object Safety rules*).
9. **A** — Menjamin *dual-write consistency* antara update database relasional dan antrean message broker.
10. **B** — *Locking* atau pembandingan versi atomis menjamin integritas *state* akun saat konkurensi paralel terjadi.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Tantangan Mandiri (Mini Project)

**Judul Proyek:** *High-Reliability Outbox Worker System*

#### Spesifikasi Kebutuhan:
1.  **Ekspansi Domain Layer:** Tambahkan entitas `OutboxMessage` yang memiliki atribut `id: Uuid`, `aggregate_type: String`, `payload: serde_json::Value`, dan `status: OutboxStatus (Pending, Sent, Failed)`.
2.  **Abstraksi Port Baru:** Buat trait `OutboxRepository: Send + Sync`:
    ```rust
    #[async_trait]
    pub trait OutboxRepository: Send + Sync {
        async fn fetch_pending(&self, limit: usize) -> Result<Vec<OutboxMessage>, StorageError>;
        async fn mark_as_sent(&self, id: Uuid) -> Result<(), StorageError>;
    }
    ```
3.  **Background Worker Process:** Buatlah Tokio background task terpisah di dalam `main.rs` yang berjalan secara periodik (setiap 1 detik):
    *   Membaca entitas yang berstatus `Pending`.
    *   Mensimulasikan pengiriman ke remote Kafka/RabbitMQ broker.
    *   Mengubah status entitas menjadi `Sent`.
4.  **Graceful Termination Integration:** Pastikan background task mendengarkan `tokio::sync::watch::Receiver` untuk shutdown signal. Task harus menyelesaikan pengiriman batch yang sedang berlangsung sebelum aplikasi benar-benar exit.
5.  **Quality Gate:** Sistem harus lolos `cargo clippy -- -D warnings` tanpa adanya toleransi terhadap `unwrap()`, dan coverage unit-test minimal 80% pada logic domain.