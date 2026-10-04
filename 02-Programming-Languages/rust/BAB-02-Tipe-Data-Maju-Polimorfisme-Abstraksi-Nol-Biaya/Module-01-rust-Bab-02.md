# MODUL 02 — BAB 01: TIPE DATA MAJU, POLIMORFISME, & ABSTRAKSI NOL-BIAYA

---

## SEKSI 01 — IDENTITAS MODUL

| Parameter | Keterangan |
| :--- | :--- |
| **Kode Modul** | `RUST-ADV-0201` |
| **Kategori** | `02-Programming-Languages` |
| **Jalur Kurikulum** | *Systems Architecture & High-Performance Computing with Rust* |
| **Tingkat Kesulitan** | *Advanced (Tingkat Lanjut)* |
| **Prasyarat** | Pemahaman mendalam tentang *Ownership*, *Borrowing*, *Lifetimes*, dan Sintaksis Dasar Rust (*Struct*, *Enum*, *Pattern Matching*). |
| **Estimasi Waktu Belajar** | 10–14 Jam (Teori, Eksplorasi Memori, & Implementasi Laboratorium) |

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Membedakan** mekanisme internal *Static Dispatch* (monomorfisasi) dan *Dynamic Dispatch* (`dyn Trait` via vtable fat pointer) dari perspektif eksekusi CPU dan instruksi biner.
2. **Merancang dan Mengimplementasikan** *Type-State Pattern* memanfaatkan sistem tipe Rust dan `PhantomData` untuk memvalidasi transisi *state machine* sepenuhnya pada waktu kompilasi (*compile-time invariant enforcement*).
3. **Mengeksploitasi Prinsip Zero-Cost Abstraction** dalam arsitektur berkinerja tinggi, termasuk optimasi memori seperti *Niche Value Optimization* dan penghapusan *overhead runtime*.
4. **Mengevaluasi Karakteristik Object Safety** pada sebuah *trait* dan merestrukturisasi API agar dapat diekspos sebagai *trait object* tanpa melanggar batasan ukuran biner dan konvensi pemanggilan (*calling convention*).
5. **Menerapkan *Associated Types* vs *Generic Type Parameters*** secara tepat guna menyusun abstraksi antarmuka domain yang ergonomis dan minim ambiguitas tipe.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Tipe Data Sebagai Bukti Matematis (*Curry-Howard Correspondence*)
Dalam bahasa dengan sistem tipe statis tingkat tinggi seperti Rust, sebuah tipe bukan sekadar cetak biru (*blueprint*) pengalokasian memori berukuran sekian *byte*. Tipe data adalah proposisi logis, dan nilai dari tipe tersebut adalah bukti keberadaannya. Ketika Anda menulis program Rust:
- **Tipe adalah Validasi Kompilasi:** Jika kode Anda lolos kompilasi (*compile-pass*), Anda telah membuktikan secara matematis bahwa tidak ada *undefined state* yang dieksekusi.
- **Abstraksi Bukan Musuh Kinerja:** Di paradigma berorientasi objek tradisional (seperti Java atau C++ pra-modern), abstraksi identik dengan *runtime overhead* (alokasi *heap*, *pointer indirection*, *garbage collection pressure*). Di Rust, abstraksi tingkat tinggi (seperti iterator, penutupan/*closures*, dan *generic traits*) dikompilasi menjadi representasi tingkat rendah (*low-level assembly*) yang identik atau bahkan lebih optimal dibandingkan kode C yang ditulis manual. Ini adalah esensi dari mantra Bjarne Stroustrup: *"What you don't use, you don't pay for. And further: What you do use, you couldn't hand code any better."*

### Mental Model: Fat Pointer vs Monomorphization
Bayangkan dua cara untuk menjalankan sebuah fungsi pada tipe data konkret:
1. **Monomorfisasi (Static Dispatch):** Kompiler menduplikat logika algoritma untuk setiap tipe konkret yang memanggilnya. Ini seperti mencetak buku panduan terpisah untuk setiap bahasa. Tidak ada kamus yang perlu dibawa saat bepergian; pembaca membaca langsung bahasa aslinya secara instan (*inline execution*).
2. **Trait Object (Dynamic Dispatch):** Anda membawa satu buku berbahasa netral bersama seorang penerjemah (*vtable*). Memori menyimpan pointer ke data mentah dan pointer ke tabel fungsi. Setiap panggilan memerlukan satu lompatan *pointer* tambahan untuk menemukan fungsi yang relevan.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Perbandingan Alur Kompilasi dan Memori: Static vs Dynamic Dispatch

```
[KODE SUMBER]
  fn process<T: Summary>(item: T)   VS   fn process(item: &dyn Summary)
               │                                       │
               ▼ (Kompilasi)                           ▼ (Kompilasi)
   ┌───────────────────────┐               ┌────────────────────────┐
   │    Monomorfisasi      │               │ Trait Object Creation  │
   │  rustc menggandakan   │               │   Membentuk Fat Pointer│
   │ fungsi untuk T1, T2   │               │      (Data + Vtable)   │
   └───────────┬───────────┘               └───────────┬────────────┘
               │                                       │
               ▼ (Eksekusi Biner)                      ▼ (Eksekusi Biner)
   ┌───────────────────────┐               ┌────────────────────────┐
   │ Biner:                │               │ Biner:                 │
   │  process_Tweet()      │               │  process()             │
   │  process_Article()    │               │   Hanya 1 fungsi       │
   └───────────┬───────────┘               └───────────┬────────────┘
               │                                       │
               ▼ (Runtime)                             ▼ (Runtime)
   ┌───────────────────────┐               ┌────────────────────────┐
   │ Langsung lompat ke    │               │ Dereferensi ganda:     │
   │ alamat instruksi      │               │ 1. Baca Pointer Vtable │
   │ (Inlineable/No Cost)  │               │ 2. Lompat ke pointer fn│
   └───────────────────────┘               └────────────────────────┘
```

### 2. Anatomi Memori: Fat Pointer (`&dyn Trait`)

```
               &dyn Trait (Ukuran = 2 Pointer / 16 Byte pada x86_64)
              ┌────────────────────────┬────────────────────────┐
              │    DATA POINTER        │     VTABLE POINTER     │
              │       (8 Byte)         │        (8 Byte)        │
              └───────────┬────────────┴───────────┬────────────┘
                          │                        │
                          ▼                        ▼
               ┌──────────────────────┐ ┌───────────────────────────────────┐
               │ Nilai Struktur Data  │ │ VTABLE (Virtual Method Table)     │
               │ Konkret di Stack/Heap│ ├───────────────────────────────────┤
               │                      │ │ destructor: fn(*mut ())           │
               │ struct Order {       │ │ size: usize                       │
               │   id: u64,           │ │ align: usize                      │
               │   amount: f64        │ │ method_1: fn(*const ()) -> Ret    │
               │ }                    │ │ method_2: fn(*const (), Arg) -> ()│
               └──────────────────────┘ └───────────────────────────────────┘
```

### 3. Diagram Alur Type-State Pattern (Compile-Time State Machine)

```
        RawInput Data
              │
              ▼
   ┌──────────────────────┐
   │ Order<Unvalidated>   │ ──(Fungsi: .validate())──► Gagal (Error)
   └──────────────────────┘
              │ (Valid)
              ▼
   ┌──────────────────────┐
   │  Order<Validated>    │ ──(Fungsi: .execute())──► Error: Method Not Found!
   └──────────────────────┘                         (Ditolak saat kompilasi)
              │
              ▼ (Fungsi: .sign(Key))
   ┌──────────────────────┐
   │   Order<Signed>      │
   └──────────────────────┘
              │
              ▼ (Fungsi: .execute())
   ┌──────────────────────┐
   │  Order<Executed>     │
   └──────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Layout Memori dan ABI (*Application Binary Interface*)
1. **Sized vs Dynamically Sized Types (DST):**
   - Sebagian besar tipe di Rust memiliki ukuran yang diketahui pada saat kompilasi (`Sized`).
   - Tipe seperti `[T]` (slice tanpa referensi) atau `dyn Trait` adalah *Dynamically Sized Types* (DST). Karena kompiler tidak mengetahui berapa alokasi stack yang harus disediakan untuk DST, tipe ini tidak dapat disimpan secara langsung di dalam variabel stack reguler. DST *wajib* diletakkan di balik pointer: `&dyn Trait`, `&mut dyn Trait`, `Box<dyn Trait>`, atau `Arc<dyn Trait>`.

2. **Anatomi Fat Pointer:**
   - Pointer tipis (*thin pointer*) untuk tipe `&T` hanya berisi alamat memori sebesar 8 byte (pada arsitektur 64-bit).
   - Pointer lebar (*fat pointer*) untuk `&dyn Trait` berukuran 16 byte, terdiri atas:
     - **Pointer Data (`*mut ()`):** Menunjuk ke instansiasi data konkret di heap atau stack.
     - **Pointer Vtable (`*const ()`):** Menunjuk ke tabel fungsi statis yang dibuat oleh kompiler di segmen data konstan biner (`.rodata`).

3. **Struktur Internal Vtable Rust:**
   Vtable Rust secara internal mencakup:
   - Pointer destruktor (`drop_in_place`), yang bertugas membersihkan data konkret saat fat pointer di-*drop*.
   - Ukuran data konkret (`size`), digunakan oleh deallocator runtime.
   - Penyelarasan data (*alignment*), memastikan manipulasi memori tidak menyebabkan CPU *unaligned access exception*.
   - Serangkaian penunjuk fungsi (*function pointers*) untuk setiap metode yang didefinisikan dalam *trait*.

4. **Niche Value Optimization:**
   Sistem tata letak tipe data Rust mengeksploitasi bit-bit yang tidak valid (*niches*) dari suatu tipe untuk merepresentasikan varian data lain tanpa menambah ukuran alokasi memori.
   - Contoh: Tipe `&T`, `Box<T>`, dan `core::num::NonZeroU64` dijamin tidak pernah bernilai nol (`0x0` / `null`).
   - Akibatnya, `Option<&T>` atau `Option<Box<T>>` memiliki ukuran yang identik persis dengan pointer biasa (8 byte), karena nilai `None` dipetakan ke alamat `0x0`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Monomorfisasi (Static Polymorphism)
Ketika Anda menulis:
```rust
fn print_val<T: std::fmt::Display>(val: T) {
    println!("{}", val);
}
```
Kompiler Rust melakukan *monomorphization*, yaitu menggandakan fungsi untuk setiap tipe `T` yang dipanggil di seluruh program. Jika Anda memanggil `print_val(5u32)` dan `print_val("abc")`, berkas biner akhir akan menghasilkan dua simbol assembly berbeda: `print_val_u32` dan `print_val_str`.

* **Kelebihan:** 
  - Tidak ada *indirection overhead*.
  - Kompiler memiliki visibilitas penuh untuk melakukan *function inlining*, *loop unrolling*, dan *dead-code elimination*.
* **Kekurangan:**
  - *Code bloat* (ukuran file biner membesar).
  - Peningkatan waktu kompilasi (*compile-time latency*).
  - *Instruction-cache (I-cache) thrashing* jika terlalu banyak instansiasi fungsi berskala besar dipanggil bergantian.

### 2. Dynamic Dispatch via Trait Objects (`dyn Trait`)
Dynamic dispatch menunda resolusi pemanggilan fungsi hingga *runtime*. Untuk membuat sebuah trait dapat diubah menjadi trait object (`dyn Trait`), trait tersebut wajib memenuhi syarat **Object Safety**. 

Berdasarkan RFC 0255 dan standar Rust terkini, sebuah trait dikatakan *Object Safe* jika:
1. Trait tersebut tidak mensyaratkan `Self: Sized` (artinya ia mengizinkan ukuran objek bervariasi).
2. Semua metodenya memenuhi kriteria:
   - Menggunakan penerima `&self`, `&mut self`, `Box<Self>`, dsb. (Bukan mengambil `self` secara *by-value*, kecuali ada penanda `where Self: Sized`).
   - Tidak memiliki parameter generic (`fn parse<U>(&self, input: U)` tidak aman secara objek).
   - Tidak mengembalikan tipe `Self`.

Jika Anda melanggar aturan ini, kompiler tidak dapat mengonstruksi vtable yang seragam karena tanda tangan fungsi bervariasi tergantung pada implementornya.

### 3. Associated Types vs Generic Type Parameters
- Gunakan **Associated Types** ketika hanya boleh ada **satu implementasi konkret** per satu tipe dasar. 
  Contoh: Trait `Iterator` hanya memiliki `type Item`. Sebuah `Vec<u8>` hanya dapat diiterasi menghasilkan elemen bertipe `u8`.
- Gunakan **Generic Parameters** ketika Anda ingin mengizinkan **banyak implementasi** untuk tipe yang sama.
  Contoh: Trait `From<T>` mengizinkan `String` mengimplementasikan `From<&str>`, `From<char>`, dan `From<Box<str>>`.

### 4. Zero-Cost Type-State Pattern
*Type-State Pattern* memetakan status logika ke dalam tipe data *compile-time*. Dengan memanfaatkan struktur zero-sized (`struct Unvalidated;`, `struct Validated;`), kita dapat menyematkannya ke dalam struktur data utama via tipe generic atau penanda `PhantomData<T>`. Karena struktur kosong memiliki ukuran 0 byte (`std::mem::size_of::<Unvalidated>() == 0`), semua validasi transisi alur program dijamin oleh sistem tipe dan terhapus seluruhnya saat kode dikompilasi menjadi *machine code*.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode yang mendemonstrasikan sintaksis lanjut: *Static Dispatch*, *Dynamic Dispatch*, serta penggunaan *Associated Types* versus *Generics*.

```rust
// File: src/main.rs
use std::fmt::Debug;

// 1. Trait dengan Associated Type
pub trait Serializer {
    type Output; // Associated type: satu tipe output per implementor
    type Error: Debug;

    fn serialize(&self) -> Result<Self::Output, Self::Error>;
}

// 2. Trait dengan Object Safety untuk Dynamic Dispatch
pub trait NotificationTarget {
    fn send_alert(&self, message: &str) -> Result<(), &'static str>;
}

// Implementasi tipe konkret A
#[derive(Debug)]
pub struct SlackNotifier {
    pub webhook_url: String,
}

impl NotificationTarget for SlackNotifier {
    fn send_alert(&self, message: &str) -> Result<(), &'static str> {
        println!("[SLACK: {}] -> {}", self.webhook_url, message);
        Ok(())
    }
}

// Implementasi tipe konkret B
#[derive(Debug)]
pub struct PagerDutyNotifier {
    pub service_key: String,
}

impl NotificationTarget for PagerDutyNotifier {
    fn send_alert(&self, message: &str) -> Result<(), &'static str> {
        println!("[PAGERDUTY: {}] -> CRITICAL: {}", self.service_key, message);
        Ok(())
    }
}

// 3. Static Dispatch: Menggunakan Monomorfisasi Generics
// Kompiler akan membuat versi terpisah untuk SlackNotifier dan PagerDutyNotifier
pub fn dispatch_static<T: NotificationTarget>(target: &T, msg: &str) {
    target.send_alert(msg).expect("Failed static notification");
}

// 4. Dynamic Dispatch: Menggunakan Fat Pointer (&dyn Trait)
// Hanya ada satu fungsi di biner, menggunakan resolusi vtable saat runtime
pub fn dispatch_dynamic(target: &dyn NotificationTarget, msg: &str) {
    target.send_alert(msg).expect("Failed dynamic notification");
}

// Implementasi Serializer untuk SlackNotifier
impl Serializer for SlackNotifier {
    type Output = String;
    type Error = std::io::Error;

    fn serialize(&self) -> Result<Self::Output, Self::Error> {
        Ok(format!("webhook={}", self.webhook_url))
    }
}

fn main() {
    let slack = SlackNotifier {
        webhook_url: String::from("https://hooks.slack.com/services/xyz"),
    };
    let pager = PagerDutyNotifier {
        service_key: String::from("PD-SEC-KEY-999"),
    };

    println!("--- 1. STATIC DISPATCH (Zero-Cost Monomorphization) ---");
    dispatch_static(&slack, "Disk usage at 92%");
    dispatch_static(&pager, "Database replica unreachable");

    println!("\n--- 2. DYNAMIC DISPATCH (Heterogeneous Collections) ---");
    // Heterogeneous collection hanya mungkin menggunakan dyn Trait
    let notifiers: Vec<Box<dyn NotificationTarget>> = vec![
        Box::new(slack),
        Box::new(pager),
    ];

    for notifier in notifiers.iter() {
        dispatch_dynamic(notifier.as_ref(), "Global Cluster Failover Event");
    }

    println!("\n--- 3. ZERO-SIZED INSPECTION ---");
    println!("Ukuran pointer referensi biasa: {} bytes", std::mem::size_of::<&SlackNotifier>());
    println!("Ukuran Fat Pointer (&dyn NotificationTarget): {} bytes", std::mem::size_of::<&dyn NotificationTarget>());
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi arsitektural dari implementasi di atas:

1. **Baris 5–10 (`pub trait Serializer`):** Mendeklarasikan *associated type* `type Output;` dan `type Error;`. Ini membatasi implementasi hanya menghasilkan tepat satu tipe output untuk `SlackNotifier`. Pemanggil tidak perlu menuliskan *type signature generic* yang rumit seperti `Serializer<Output, Error>`.
2. **Baris 13–15 (`pub trait NotificationTarget`):** Memenuhi syarat *object safety* karena:
   - Metodenya memiliki penerima `&self`.
   - Tidak mengembalikan `Self`.
   - Tidak memiliki fungsi generic inline.
3. **Baris 38–41 (`pub fn dispatch_static<T: NotificationTarget>`):** Parameter tipe `T` diselesaikan saat kompilasi. Kompiler menyalin instruksi fungsi dan menyisipkan lompatan alamat langsung (*direct call*) atau meng-*inline* pemanggilan metode `send_alert`.
4. **Baris 45–48 (`pub fn dispatch_dynamic(target: &dyn NotificationTarget)`):** Parameter menerima fat pointer sebesar 16 byte. Pada level instruksi perakitan (*assembly*), prosesor membaca pointer data dari register pertama dan membaca alamat vtable dari register kedua, kemudian melakukan *indirect jump* (`call rax` atau setara) ke fungsi `send_alert`.
5. **Baris 63–66 (`let notifiers: Vec<Box<dyn NotificationTarget>>`):** Variabel ini mendemonstrasikan keunggulan absolut Dynamic Dispatch: menyimpan beberapa instansiasi tipe data yang berbeda (*heterogeneous types*) dalam struktur data berurutan tunggal. Ini mustahil dilakukan melalui *Static Dispatch* generik biasa karena `Vec<T>` mengharuskan setiap elemen memiliki ukuran memori yang seragam secara statis.
6. **Baris 73–74 (`std::mem::size_of`):** Mengonfirmasi secara empiris bahwa `&SlackNotifier` berukuran 8 byte (arsitektur 64-bit), sedangkan fat pointer `&dyn NotificationTarget` berukuran 16 byte (8 byte data pointer + 8 byte vtable pointer).

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Engine Matching & Settlement Transaksi Finansial
Pada sistem pemrosesan transaksi valuta asing (*foreign exchange*) atau *cryptocurrency execution engine*, kecepatan dan integritas absolut terhadap keadaan data adalah prioritas utama. 

**Tantangan Arsitektur:**
1. **Pencegahan Kondisi Tidak Sah:** Transaksi tidak boleh dieksekusi sebelum melalui proses validasi parameter dan penandatanganan kriptografis (*cryptographic signature*). Memeriksa status transaksi dengan `if order.status == Status::Signed` saat waktu eksekusi membuang siklus CPU (cabang kode / *branch misprediction*) dan rentan lolos jika ada celah logika pemrograman.
2. **Fleksibilitas Protokol Multi-Settlement:** Mesin harus mendukung pengiriman transaksi ke *settlement layer* yang berbeda (misalnya: SWIFT, FIX Engine, atau On-Chain Mempool) secara dinamis sesuai konfigurasi rute, namun kalkulasi validasi internalnya harus berjalan pada kecepatan raw memory tanpa alokasi (*zero-cost*).

**Solusi:**
- Terapkan **Type-State Pattern** untuk menjamin kompilasi gagal jika developer mencoba memanggil `.execute()` pada order yang belum berstatus `Signed`.
- Kombinasikan dengan **Zero-Sized Types (ZST)** dan *PhantomData* agar *State Machine* tidak memakan memori runtime sama sekali.
- Gunakan *Dynamic Dispatch* hanya pada batas I/O modul (*Settlement Strategy*), sementara seluruh *Domain Core* menggunakan *Static Dispatch*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi skala produksi mesin transaksi finansial yang mendemonstrasikan seluruh konsep.

```rust
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
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Metrik Penilaian | Static Dispatch (`impl Trait` / Generics) | Dynamic Dispatch (`Box<dyn Trait>` / `&dyn Trait`) |
| :--- | :--- | :--- |
| **Mekanisme Eksekusi** | Monomorfisasi waktu kompilasi; panggilan fungsi langsung (*direct call*). | Resolusi tabel virtual (*vtable*) waktu *runtime*; *indirect pointer jump*. |
| **Kinerja CPU** | **Maksimal**. Kompiler dapat melakukan *inline* kode instruksi mesin. | **Lebih Rendah**. Ada latensi dereferensi pointer vtable dan *I-cache miss*. |
| **Ukuran Memori (Pointer)** | Pointer reguler (8 byte pada arsitektur 64-bit). | Fat pointer (16 byte: 8 byte data pointer + 8 byte vtable pointer). |
| **Ukuran Biner Kode** | **Membesar** (*Code Bloat*) jika trait diimplementasikan oleh banyak tipe. | **Stabil/Kecil**. Hanya ada satu implementasi instruksi fungsi pemanggil. |
| **Waktu Kompilasi** | **Lebih Lama**. Kompiler harus men-generalisasi setiap varian tipe. | **Lebih Cepat**. Kompiler hanya memverifikasi *type-signature* antarmuka. |
| **Heterogeneous Collections**| **Tidak Didukung**. `Vec<T>` memerlukan tipe data seragam yang identik. | **Didukung Penuh**. `Vec<Box<dyn Trait>>` dapat menyimpan berbagai struktur. |
| **Optimalisasi Kompiler** | Memungkinkan optimasi SIMD, *loop unrolling*, dan penghapusan batas cabang. | Mengurangi ruang optimasi kompiler karena adanya batasan pointer dinamis. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Pelanggaran Object Safety Melalui Pemanggilan Generic Method
Jika Anda menambahkan fungsi generik ke dalam sebuah trait:
```rust
pub trait StorageEngine {
    fn persist<T: serde::Serialize>(&self, item: T); // MELANGGAR OBJECT SAFETY
}
```
Kompiler Rust akan menolak kode tersebut jika digunakan sebagai `dyn StorageEngine`.
*Penyebab:* Rust membuat vtable dengan penunjuk fungsi yang ukurannya harus pasti pada waktu pembuatan trait. Karena `T` dapat berupa tipe tak terbatas, jumlah pointer yang harus dimasukkan ke dalam vtable tidak terhingga. 
*Solusi:* Hindari generic method pada trait objek, atau gunakan *type erasure* via `serde_json::Value` / buffer biner `&[u8]`.

### 2. Lifetime Implicit pada Trait Objects
Saat Anda menulis `Box<dyn Trait>`, Rust secara otomatis menerapkan batasan *lifetime* implisit `'static`:
```rust
// Kode ini secara default diinterpretasikan sebagai Box<dyn Trait + 'static>
fn process(engine: Box<dyn Trait>) { ... }
```
Jika instansiasi data awal Anda meminjam nilai dengan lifetime non-statis (`&'a`), Anda akan menghadapi error peminjaman (*borrow checker error*). 
*Solusi:* Nyatakan lifetime secara eksplisit jika menerima data pinjaman: `Box<dyn Trait + 'a>`.

### 3. Masalah *Drop* pada Heterogeneous Collections
Ketika `Box<dyn Trait>` keluar dari *scope*, destruktor tipe konkret yang mendasarinya dieksekusi melalui pointer `drop_in_place` pada vtable. Jika trait meminjam data tanpa manajemen drop yang benar, atau jika ada destruktor yang memicu *circular dependency*, kebocoran memori dapat terjadi secara tersembunyi.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengabaikan Penanda `?Sized` pada Fungsi Generic
```rust
// SALAH: Tipe T diasumsikan Sized secara default
fn log_item<T: Display>(item: &T) { ... }

// BENAR: Mengizinkan pemanggilan baik untuk Sized maupun Dynamically Sized Types (seperti str)
fn log_item<T: Display + ?Sized>(item: &T) { ... }
```
*Mengapa ini terjadi:* Semua parameter generic tipe `T` di Rust secara implisit memiliki batasan `T: Sized`. Jika Anda ingin fungsi generic Anda dapat memproses `&str` atau `&dyn Trait` secara langsung tanpa membungkusnya ulang, Anda wajib menambahkan batasan rileksasi `+ ?Sized`.

### Kesalahan 2: Menggunakan Dynamic Dispatch di Loop Berfrekuensi Tinggi (*Hot Path*)
```rust
// ANTI-PATTERN: Pemanggilan vtable di dalam loop 10 juta iterasi
for i in 0..10_000_000 {
    engine.process_tick(&data[i]); // dynamic dispatch indirection penalty
}
```
*Cara Menghindari:* Pada layer arsitektur performa kritis (*hot path*), gunakan strategi polimorfisme statis menggunakan parameter generic, atau kelompokkan pemrosesan (*batch processing*) sehingga dynamic dispatch hanya terjadi satu kali per kumpulan data besar (*batch*).

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prinsip Monomorfisasi Utama (Static by Default):** Buat seluruh antarmuka domain publik menggunakan static generics (`impl Trait` atau parameter `T`). Gunakan `dyn Trait` hanya pada batas sistem luar (*I/O Boundaries*, *Dependency Injection*, *Plugin Architectures*).
2. **Pola *Sealed Traits*:** Jika Anda ingin mengekspos sebuah trait kepada publik namun melarang pengguna luar menambahkan implementasi pada trait tersebut:
   ```rust
   mod private {
       pub trait Sealed {}
   }

   pub trait PublicInterface: private::Sealed {
       fn restricted_call(&self);
   }

   // Implementasikan penanda Sealed hanya untuk struct internal Anda
   impl private::Sealed for MyInternalStruct {}
   impl PublicInterface for MyInternalStruct {
       fn restricted_call(&self) { ... }
   }
   ```
3. **Penyusutan Alokasi Biner Menggunakan Delegasi Trait Objek Tipis:** Jika monomorfisasi memicu pembengkakan biner (*code bloat*) yang ekstrem pada fungsi berukuran besar, delegasikan implementasi internal fungsi generic tersebut ke fungsi bantuan privat yang menggunakan dynamic dispatch.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Niche Value Optimization pada Custom Enums
Eksploitasi penataan memori rustc untuk mengeliminasi alokasi ruang diskriminan (*discriminant byte*):
```rust
// Berukuran 8 bytes (pointer) karena 0x0 digunakan untuk varian None
type OptimizedRef<'a> = Option<&'a u64>;

// Menggunakan NonZero untuk mengeliminasi ruang enum discriminant
use std::num::NonZeroU64;

// Berukuran tepat 8 bytes, BUKAN 16 bytes!
struct FastId {
    inner: Option<NonZeroU64>,
}
```

### 2. Eliminasi Dynamic Dispatch Melalui Enum Dispatch
Jika jumlah tipe implementor dari sebuah trait telah diketahui (*closed set*), hindari penggunaan `dyn Trait` sepenuhnya. Gantilah dengan *Enum Polymorphism*.
Panggilan metode pada `enum` di-dispatch menggunakan instruksi lompatan langsung (*switch table / direct branch*) yang jauh lebih ramah terhadap algoritma prediksi percabangan (*branch predictor*) pada arsitektur CPU modern dibandingkan *vtable dynamic dispatch*.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Eksploitasi Pointer dan Keselamatan Memori
1. **Pencegahan Eksploitasi Vtable Hijacking:** Pada bahasa seperti C++, tabel vtable yang terletak di memori heap rentan terhadap eksploitasi penulisan ulang memori (*vtable spraying/hijacking*). Rust meletakkan seluruh vtable pada segmen memori yang berstatus *Read-Only Data* (`.rodata`). Percobaan modifikasi terhadap isi tabel fungsi virtual akan memicu sinyal terminasi kernel (*Segmentation Fault / SIGSEGV*) instan.
2. **Kekakuan Invarian Melalui Typestate:**
   Dengan mengonsumsi kepemilikan nilai (`self` by-value) saat transisi status:
   ```rust
   // Validated di-drop dari stack, digantikan sepenuhnya oleh Signed
   pub fn sign(self, ...) -> Transaction<Signed>
   ```
   Mustahil bagi penyerang untuk melakukan eksploitasi *Double Spending* atau manipulasi transisi status parsial karena instansiasi status lama telah dimusnahkan secara fisik dari memori oleh sistem kepemilikan Rust.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Menginspeksi Vtable dan Fat Pointer di Runtime
Untuk membedah fat pointer secara langsung saat proses debugging menggunakan transmute tingkat rendah:

```rust
use std::mem;

fn debug_fat_pointer(trait_obj: &dyn SettlementGateway) {
    // Membaca representasi biner dari fat pointer (16 bytes)
    let (data_ptr, vtable_ptr): (usize, usize) = unsafe {
        mem::transmute(trait_obj)
    };

    println!("[DEBUG TRACE]");
    println!("├─ Alamat Data Instansiasi: 0x{:X}", data_ptr);
    println!("└─ Alamat VTable di .rodata: 0x{:X}", vtable_ptr);
}
```

### Inspeksi Perakitan (Assembly Analysis)
Anda dapat memverifikasi bahwa *Zero-Cost Abstractions* benar-benar bekerja dengan memeriksa instruksi mesin menggunakan alat seperti `cargo-asm` atau compiler explorer:
- Panggilan ke fungsi generic yang di-*monomorphize* dengan benar akan menghasilkan instruksi pemanggilan langsung:
  `call my_project::target_function`
- Sebaliknya, panggilan ke trait object akan menghasilkan pemanggilan dereferensi ganda:
  `mov rax, qword ptr [rdi + 8]` dilanjutkan dengan `call qword ptr [rax + 24]`.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌────────────────────────────────────────────────────────────────────────────┐
│                      RUST TYPE & DISPATCH CHEAT SHEET                      │
├────────────────────────────────────────────────────────────────────────────┤
│ 1. STATIC DISPATCH:                                                        │
│    fn run<T: Trait>(x: T)     -> Inlining penuh, monomorfisasi, biner besar│
│    fn run(x: impl Trait)      -> Gula sintaksis untuk generics di atas     │
│                                                                            │
│ 2. DYNAMIC DISPATCH:                                                       │
│    fn run(x: &dyn Trait)      -> Fat pointer (16 byte), indirect call      │
│    fn run(x: Box<dyn Trait>)  -> Fat pointer di heap, heterogeneous ok     │
│                                                                            │
│ 3. OBJECT SAFETY CHECKLIST:                                                │
│    [✓] Trait TIDAK mewajibkan Self: Sized                                  │
│    [✓] Metode menggunakan &self, &mut self, Box<Self>                      │
│    [✗] Metode TIDAK boleh memiliki parameter generik                       │
│    [✗] Metode TIDAK boleh mengembalikan tipe Self                          │
│                                                                            │
│ 4. ASSOCIATED TYPES VS GENERICS:                                           │
│    trait Trait { type Out; }  -> Tepat SATU implementasi per tipe          │
│    trait Trait<Out> { ... }   -> Mengizinkan BANYAK implementasi per tipe  │
│                                                                            │
│ 5. ZERO-COST PATTERNS:                                                     │
│    PhantomData<T>             -> Penanda tipe statis (Ukuran: 0 Byte)      │
│    NonZeroU64 / Option<&T>    -> Niche Value Optimization (Tanpa Tag Byte) │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Berapa ukuran memori dari variabel bertipe `&dyn NotificationTarget` pada arsitektur 64-bit?**
   - A. 8 byte
   - B. 16 byte
   - C. 24 byte
   - D. Ukurannya tergantung ukuran struct konkret yang diimplementasikannya

2. **Apa yang dilakukan kompiler Rust terhadap fungsi generik selama fase kompilasi?**
   - A. Menghubungkannya dengan vtable dinamis
   - B. Membungkus argumen ke dalam `Box<T>` secara otomatis
   - C. Melakukan monomorfisasi dengan menduplikasi fungsi untuk setiap tipe konkret yang dipanggil
   - D. Mengubah seluruh tipe data menjadi penunjuk biner `void*`

3. **Manakah dari deklarasi trait berikut yang secara fundamental MELANGGAR prinsip *Object Safety*?**
   - A. `fn execute(&self) -> bool;`
   - B. `fn process(&mut self, payload: &[u8]);`
   - C. `fn create_new() -> Self;`
   - D. `fn calculate(&self, val: u64) -> u64;`

4. **Kapan Anda sebaiknya memilih *Associated Type* daripada *Generic Parameter* pada sebuah trait?**
   - A. Ketika trait tersebut harus dapat diimplementasikan beberapa kali untuk satu tipe data
   - B. Ketika hanya boleh ada satu implementasi spesifik dari trait tersebut untuk tipe yang bersangkutan
   - C. Ketika trait tersebut memerlukan alokasi heap dinamis
   - D. Ketika trait tersebut tidak memiliki metode apapun

5. **Apa dampak utama penggunaan `PhantomData<T>` terhadap tata letak memori (*memory layout*) suatu *struct*?**
   - A. Menambahkan padding 8 byte untuk penyelarasan pointer
   - B. Mengubah *struct* tersebut menjadi fat pointer secara otomatis
   - C. Tidak menambah ukuran memori sama sekali (berukuran 0 byte)
   - D. Mengunci *struct* agar tidak bisa dipindahkan (*pinned*) di memori

---

### Soal Tingkat Lanjutan (Intermediate)

6. **Mengapa pemanggilan metode pada `dyn Trait` umumnya menghasilkan performa eksekusi CPU yang sedikit lebih lambat dibandingkan dengan monomorfisasi generik?**
   - A. Karena memori heap harus selalu dialokasikan ulang pada setiap panggilan
   - B. Karena prosesor harus melakukan dereferensi pointer ganda (vtable) dan membatasi peluang *inlining* oleh kompiler
   - C. Karena *borrow checker* bekerja secara aktif selama eksekusi program (*runtime overhead*)
   - D. Karena Rust menggunakan sistem Garbage Collector khusus untuk fat pointer

7. **Perhatikan kode berikut:**
   ```rust
   struct StateA;
   struct StateB;
   struct Context<S> { _marker: std::marker::PhantomData<S> }
   
   impl Context<StateA> {
       fn transition(self) -> Context<StateB> {
           Context { _marker: std::marker::PhantomData }
       }
   }
   ```
   **Apa keuntungan arsitektural utama dari pola di atas dibandingkan menggunakan enum state biasa?**
   - A. Mengurangi alokasi heap menjadi nol dan memvalidasi transisi state saat waktu kompilasi
   - B. Mengizinkan mutasi konkuren tanpa memerlukan mutex
   - C. Menghasilkan file biner yang lebih kecil dibandingkan seluruh pendekatan lain
   - D. Mengizinkan deserialisasi JSON otomatis tanpa pustaka pihak ketiga

8. **Diberikan tipe `Option<Box<u64>>`. Berapa ukuran memori struktur data tersebut pada sistem 64-bit dan optimasi apa yang diterapkan oleh kompiler?**
   - A. 16 byte, dengan diskriminan 8 byte
   - B. 8 byte, berkat Niche Value Optimization yang memanfaatkan fakta bahwa pointer alokasi heap tidak pernah bernilai null
   - C. 12 byte, menggunakan teknik bit-packing
   - D. 24 byte, karena pointer heap memerlukan representasi vtable

9. **Jika sebuah trait didefinisikan sebagai `pub trait Compute: Sized`, bisakah trait tersebut digunakan sebagai `Box<dyn Compute>`? Jelaskan alasannya.**
   - A. Bisa, karena `Box` selalu mengalokasikan memori di heap yang ukurannya teratur
   - B. Bisa, karena semua trait di Rust secara otomatis aman secara objek (*object safe*)
   - C. Tidak bisa, karena batasan `Sized` melarang trait tersebut diekspos sebagai Dynamically Sized Type (DST)
   - D. Tidak bisa, kecuali ditambahkan atribut `#[repr(C)]`

10. **Bagaimana cara menangani situasi di mana Anda memerlukan koleksi heterogen yang berisi berbagai tipe data berbeda yang mengimplementasikan trait yang sama, namun sebagian besar operasi internalnya tetap menuntut efisiensi eksekusi *hot-path* maksimal?**
    - A. Gunakan `Vec<Box<dyn Any>>` dan lakukan downcasting secara rekursif di setiap iterasi loop
    - B. Tulis ulang kode menggunakan pointer mentah `*const ()` tanpa verifikasi tipe data
    - C. Gunakan *Enum Dispatch* jika kumpulan tipe terbatas, atau gunakan arsitektur *batching* di mana dynamic dispatch hanya dipanggil satu kali per blok data masif
    - D. Selalu gunakan `Vec<impl Trait>` di dalam struktur data internal

---

### Kunci Jawaban & Rasionalisasi

1. **B (16 byte):** Fat pointer selalu terdiri dari dua pointer berukuran masing-masing 8 byte (pada mesin 64-bit): pointer ke data alamat konkret dan pointer ke vtable.
2. **C:** Monomorfisasi menduplikasi kode fungsi secara terpisah untuk setiap variasi tipe parameter konkret yang digunakan dalam basis kode program.
3. **C:** Fungsi `fn create_new() -> Self;` melanggar *object safety* karena mengembalikan tipe `Self` dan tidak memiliki penerima referensi `&self`. Kompiler tidak mengetahui ukuran alokasi memori konkret yang harus dikembalikan ketika tipe implementor diabstraksi menjadi trait object.
4. **B:** *Associated Type* memastikan bahwa implementor hanya memiliki tepat satu relasi tipe pasangan, yang secara drastis menyederhanakan deklarasi antarmuka dan membatasi ambiguitas tipe.
5. **C:** `PhantomData<T>` secara teknis dijamin oleh kompiler sebagai tipe dengan ukuran 0 byte (*Zero-Sized Type*) yang tidak memakan alokasi ruang memori fisik sama sekali.
6. **B:** Dynamic dispatch memerlukan pembacaan pointer vtable sebelum melompat ke alamat fungsi yang dituju (*indirect call*), yang mengakibatkan CPU tidak dapat melakukan *inlining* dan rentan mengalami *instruction cache miss*.
7. **A:** *Type-State Pattern* mengeliminasi pemeriksaan kondisi status di runtime (`if-checks`) dan mencegah transisi status ilegal langsung saat proses kompilasi tanpa beban alokasi memori tambahan.
8. **B:** Nilai penunjuk `Box` dijamin valid dan tidak pernah bernilai nol (`0x0`), sehingga nilai `0x0` dieksploitasi oleh kompiler untuk merepresentasikan varian `None` secara langsung pada ruang pointer 8 byte tersebut.
9. **C:** Trait object memerlukan tipe yang *unsized* pada saat runtime (`dyn Trait: ?Sized`). Menambahkan batasan `Self: Sized` secara eksplisit mencabut sifat *object safety* dari trait tersebut.
10. **C:** *Enum Dispatch* menyediakan lompatan percabangan langsung yang efisien tanpa *fat pointer overhead*, dan pendekatan *batching* meminimalkan frekuensi eksekusi resolusi vtable dinamis.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: High-Throughput In-Memory Pipeline Engine

#### Spesifikasi Fungsional:
Anda diminta untuk membangun sebuah mesin pemrosesan data aliran (*stream pipeline processing engine*) mandiri menggunakan Rust yang mematuhi batasan arsitektur berikut:

1. **Komponen Type-State:**
   Buat pipeline pengolahan data paket jaringan dengan transisi status:
   `Packet<Raw>` ➔ `Packet<Parsed>` ➔ `Packet<Encrypted>` ➔ `Packet<Dispatched>`.
   - Data paket mentah hanya boleh berupa buffer byte `Vec<u8>`.
   - Method `.parse()` hanya tersedia untuk `Packet<Raw>`.
   - Method `.encrypt()` hanya tersedia untuk `Packet<Parsed>`.
   - Transisi ke `Packet<Dispatched>` hanya dapat dipanggil jika paket telah berstatus `Encrypted`.
   - Buktikan bahwa alur status ini tidak dapat dilompati secara ilegal (misal: langsung memanggil `.encrypt()` dari status `Raw`).

2. **Polimorfisme Ganda (Hybrid Architecture):**
   - Definisikan trait `CompressionCodec` dengan associated type untuk konfigurasi kompresi. Implementasikan secara **Static Dispatch** untuk algoritma kompresi berkecepatan tinggi (misalnya: *Snappy* atau *Zstd* dummy).
   - Definisikan trait `TransportAdapter` yang bersifat **Object-Safe**. Buat implementasi konkret untuk `TcpTransport` dan `UdpTransport`.
   - Buat struktur `PipelineDispatcher` yang menyimpan koleksi `Vec<Box<dyn TransportAdapter>>` untuk mendistribusikan paket yang telah diolah ke beberapa protokol jaringan secara dinamis.

3. **Verifikasi Zero-Cost:**
   - Gunakan pernyataan pengujian unit (`#[test]`) dengan `std::mem::size_of` untuk membuktikan secara empiris bahwa `Packet<Raw>` dan `Packet<Encrypted>` memiliki ukuran memori yang identik di stack.
   - Buat pengujian integrasi sederhana yang menjalankan alur pemrosesan dari buffer mentah hingga paket disalurkan ke seluruh transport adapter yang terdaftar.