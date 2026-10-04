// File: src/engine.rs
use std::marker::PhantomData;
use std::time::{SystemTime, UNIX_EPOCH};

// ============================================================================
// 1. TYPE-STATE MARKERS (Zero-Sized Types)
// ============================================================================
pub struct Unvalidated;
pub struct Validated;
pub struct Signed;
pub struct Executed;

// ============================================================================
// 2. DOMAIN ENTITY & TRANSITIONS
// ============================================================================
#[derive(Debug)]
pub struct Transaction<State> {
    pub id: u64,
    pub amount: u64, // Disimpan dalam satuan terkecil (cents / satoshis)
    pub sender: String,
    pub recipient: String,
    pub signature: Option<Vec<u8>>,
    _state: PhantomData<State>, // Menandai tipe tanpa menambah ukuran memori
}

// Method untuk State: Unvalidated
impl Transaction<Unvalidated> {
    pub fn new(id: u64, amount: u64, sender: String, recipient: String) -> Self {
        Transaction {
            id,
            amount,
            sender,
            recipient,
            signature: None,
            _state: PhantomData,
        }
    }

    pub fn validate(self) -> Result<Transaction<Validated>, &'static str> {
        if self.amount == 0 {
            return Err("Nominal transaksi harus lebih dari nol");
        }
        if self.sender.is_empty() || self.recipient.is_empty() {
            return Err("Pengirim dan penerima harus valid");
        }

        // Transisi State secara Zero-Cost
        Ok(Transaction {
            id: self.id,
            amount: self.amount,
            sender: self.sender,
            recipient: self.recipient,
            signature: None,
            _state: PhantomData,
        })
    }
}

// Method untuk State: Validated
impl Transaction<Validated> {
    pub fn sign(self, private_key: &[u8]) -> Result<Transaction<Signed>, &'static str> {
        if private_key.is_empty() {
            return Err("Kunci privat tidak valid untuk penandatanganan");
        }

        // Dummy proses hashing & signature
        let dummy_sig = vec![0xDE, 0xAD, 0xBE, 0xEF];

        Ok(Transaction {
            id: self.id,
            amount: self.amount,
            sender: self.sender,
            recipient: self.recipient,
            signature: Some(dummy_sig),
            _state: PhantomData,
        })
    }
}

// Method untuk State: Signed
impl Transaction<Signed> {
    // Fungsi ini mengeksekusi order menggunakan Settlement Protocol
    pub fn execute_with<S: SettlementGateway>(
        self,
        gateway: &S,
    ) -> Result<Transaction<Executed>, &'static str> {
        gateway.settle(self.id, self.amount, &self.recipient)?;

        Ok(Transaction {
            id: self.id,
            amount: self.amount,
            sender: self.sender,
            recipient: self.recipient,
            signature: self.signature,
            _state: PhantomData,
        })
    }
}

// ============================================================================
// 3. SETTLEMENT ABSTRACTION (Dynamic & Static Compatible)
// ============================================================================
pub trait SettlementGateway {
    fn settle(&self, tx_id: u64, amount: u64, recipient: &str) -> Result<(), &'static str>;
}

pub struct SwiftGateway {
    pub bic_code: String,
}

impl SettlementGateway for SwiftGateway {
    fn settle(&self, tx_id: u64, amount: u64, recipient: &str) -> Result<(), &'static str> {
        println!(
            "[SWIFT Settlement] BIC: {} | TX: {} | Sent {} units to {}",
            self.bic_code, tx_id, amount, recipient
        );
        Ok(())
    }
}

pub struct CryptoGateway {
    pub network: String,
}

impl SettlementGateway for CryptoGateway {
    fn settle(&self, tx_id: u64, amount: u64, recipient: &str) -> Result<(), &'static str> {
        println!(
            "[Crypto Settlement] Net: {} | TX: {} | Broadcasted {} to {}",
            self.network, tx_id, amount, recipient
        );
        Ok(())
    }
}

// ============================================================================
// 4. TRANSACTION ROUTER (Dynamic Strategy)
// ============================================================================
pub struct SettlementRouter {
    gateways: Vec<Box<dyn SettlementGateway>>,
}

impl SettlementRouter {
    pub fn new() -> Self {
        Self {
            gateways: Vec::new(),
        }
    }

    pub fn register_gateway(&mut self, gw: Box<dyn SettlementGateway>) {
        self.gateways.push(gw);
    }

    pub fn broadcast_all(&self, tx_id: u64, amount: u64, recipient: &str) {
        for gw in &self.gateways {
            // Dynamic Dispatch via VTable
            if let Err(e) = gw.settle(tx_id, amount, recipient) {
                eprintln!("Gagal mengirim via gateway: {}", e);
            }
        }
    }
}

// ============================================================================
// 5. RUNTIME VALIDATION & VERIFICATION
// ============================================================================
fn main() {
    println!("=== ENGINE TRANSAKSI FINANSIAL MEMULAI INITIALISASI ===");

    // Verifikasi Ukuran Memori (Zero-Cost Invariant)
    println!(
        "Ukuran Transaction<Unvalidated>: {} bytes",
        std::mem::size_of::<Transaction<Unvalidated>>()
    );
    println!(
        "Ukuran Transaction<Signed>:      {} bytes",
        std::mem::size_of::<Transaction<Signed>>()
    );
    assert_eq!(
        std::mem::size_of::<Transaction<Unvalidated>>(),
        std::mem::size_of::<Transaction<Signed>>(),
        "FATAL: PhantomData tidak boleh menambah ukuran memori!"
    );

    // Alur Transaksi Sah
    let tx = Transaction::new(1001, 500_000, "ACC-001".into(), "ACC-002".into());
    println!("\n[State 1] Transaksi Dibuat: {:?}", tx);

    let validated_tx = tx.validate().expect("Validasi transaksi gagal");
    println!("[State 2] Transaksi Divalidasi: {:?}", validated_tx);

    let signed_tx = validated_tx
        .sign(&[0x01, 0x02, 0x03])
        .expect("Penandatanganan gagal");
    println!("[State 3] Transaksi Ditandatangani: {:?}", signed_tx);

    // Settlement via Static Dispatch
    let swift = SwiftGateway {
        bic_code: "BOFAUS3N".into(),
    };
    let executed_tx = signed_tx
        .execute_with(&swift)
        .expect("Gagal memproses settlement");
    println!("[State 4] Transaksi Selesai: {:?}", executed_tx);

    // Demonstrasi Dynamic Routing Strategy
    println!("\n=== BROADCAST MULTI-GATEWAY (Dynamic Dispatch) ===");
    let mut router = SettlementRouter::new();
    router.register_gateway(Box::new(SwiftGateway {
        bic_code: "CHASUS33".into(),
    }));
    router.register_gateway(Box::new(CryptoGateway {
        network: "Ethereum-Mainnet".into(),
    }));

    router.broadcast_all(9999, 1_250_000, "TREASURY-COLD-STORAGE");
}
