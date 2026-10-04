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
