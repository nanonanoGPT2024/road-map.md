# BAB 02: Tipe Data Maju, Polimorfisme & Abstraksi Nol-Biaya
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedakan Mekanisme Dispatch**: Mengurai representasi memori, biaya instruksi CPU, dan karakteristik *cache locality* antara *static dispatch* (monomorphization) dan *dynamic dispatch* (`dyn Trait` fat pointers / vtables).
2. **Merancang Sistem Berbasis Zero-Cost Abstractions**: Mengimplementasikan *Type-State Pattern* dan *Zero-Sized Types (ZST)* untuk menggeser validasi logika bisnis runtime ke fase kompilasi (*compile-time invariants*) dengan *runtime overhead* 0 byte.
3. **Menguasai Sistem Trait Tingkat Lanjut**: Mengimplementasikan *Associated Types*, *Higher-Rank Trait Bounds* (`for<'a>`), *Marker Traits*, dan *Blanket Implementations* secara tepat guna untuk menghindari polusi parameter generik.
4. **Mengoptimalkan Ukuran Biner dan Waktu Kompilasi**: Mendiagnosis dan memitigasi *monomorphization bloat* pada sistem berskala besar menggunakan teknik *inner-function outlining* dan *polymorphic dynamic boundaries*.
5. **Membangun Arsitektur Enterprise Extensible**: Merancang *plugin pipeline* berperforma tinggi dengan latensi sub-mikrodetik yang menggabungkan kecepatan kompilasi statis dengan fleksibilitas dispatch dinamis.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Rust Ownership, Borrowing, dan Lifetimes Tingkat Dasar hingga Menengah** (BAB 01).
- Pemahaman mendalam tentang alokasi memori sistem: *Stack*, *Heap*, *Pointer Indirection*, serta representasi data biner pada arsitektur x86_64/AArch64.
- Konsep dasar OOP dan Polimorfisme: Interface, Virtual Method Table (vtable), dan Template/Generics dari bahasa seperti C++ atau Java.
- Familiaritas dengan utilitas profiling dan analisis biner: `cargo-bloat`, `cargo-expand`, `objdump`/`gdb`/`lldb`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Monomorphization vs Dynamic Dispatch (vtable)

Rust mengimplementasikan polimorfisme melalui dua strategi utama yang berdampak langsung pada tata letak memori dan pemanfaatan instruksi mesin:

##### A. Monomorphization (Static Dispatch)
Ketika fungsi generik dideklarasikan dengan trait bound:
```rust
fn process<T: Consumer>(consumer: T) {
    consumer.consume();
}
```
Kompiler Rust (*rustc*) menduplikasi dan mengkhususkan fungsi tersebut untuk setiap tipe konkret yang memanggilnya. Proses ini disebut **monomorphization**.

* **Karakteristik Internal**:
  - **Inlining**: Kompiler dan LLVM dapat melakukan *inlining* kode secara agresif karena alamat fungsi target diketahui saat kompilasi. Tidak ada instruksi `CALL` tidak langsung (`call *%rax`).
  - **Loop Unrolling & Vectorization**: Karena tipe dan ukuran konkret diketahui, LLVM dapat menerapkan optimasi SIMD dan *loop unrolling*.
  - **Binary Bloat**: Jika tipe $T$ dipanggil dengan 50 tipe berbeda, kompilasi menghasilkan 50 instansiasi fungsi di segmen teks biner (`.text`), yang berpotensi membebani CPU Instruction Cache (I-Cache).

##### B. Dynamic Dispatch (`dyn Trait`)
Ketika polimorfisme runtime dibutuhkan (misalnya koleksi heterogen `Vec<Box<dyn Consumer>>`), Rust menggunakan tipe tak berukuran pasti (*unsized type*) `dyn Trait` melalui referensi atau pointer pintar (*fat pointer*).

* **Representasi Memori Fat Pointer**:
  Fat pointer pada target 64-bit berukuran tepat **16 byte** (2 word):
  1. Pointer ke data konkret pada heap/stack (`*const ()` / `*mut ()`).
  2. Pointer ke Virtual Method Table / vtable (`*const ()`).

```
Fat Pointer (16 bytes):
+-----------------------------------+-----------------------------------+
|  Data Pointer (8 bytes)           |  Vtable Pointer (8 bytes)         |
|  *const Data                      |  *const VTable                    |
+-----------------------------------+-----------------------------------+
           |                                       |
           v                                       v
   +------------------+                   +------------------+
   |   Concrete Data  |                   | Destructor (drop)|
   |   Instance       |                   | Size (bytes)     |
   |                  |                   | Alignment        |
   +------------------+                   | Method 1 Pointer |
                                          | Method 2 Pointer |
                                          +------------------+
```

* **Struktur Internal Vtable Rust**:
  Vtable Rust dibuat secara statis di segmen data biner (`.rodata`). Struktur vtable mencakup:
  - Destructor drop glue: Pointer fungsi pembersihan data konkret (`core::ops::Drop::drop`).
  - Ukuran alokasi memori tipe konkret (`size: usize`).
  - Batas perataan memori tipe konkret (`align: usize`).
  - Daftar pointer fungsi ke masing-masing metode yang didefinisikan dalam trait.

* **Penalti Performa**:
  - Penunjuk tidak langsung ganda: Mengambil pointer vtable $\rightarrow$ Mengambil pointer fungsi target $\rightarrow$ Melakukan jump via `CALL register`.
  - Menggagalkan *inlining* oleh LLVM.
  - Penalti *Branch Target Buffer (BTB)* dan potensi *Branch Misprediction* pada siklus CPU pipeline jika tipe konkret sering berganti di dalam loop kritis.

---

#### 3.2. Object Safety (Dyn-Compatibility)
Tidak semua trait dapat diubah menjadi `dyn Trait`. Sebuah trait memenuhi syarat *Object Safe* jika dan hanya jika:
1. Trait tidak memerlukan bound `Self: Sized` (secara implisit trait tidak mengharuskan ukuran diketahui pada waktu kompilasi untuk seluruh representasi).
2. Semua metodenya memenuhi kriteria:
   - Tidak memiliki generic type parameter.
   - Menggunakan `Self` hanya sebagai tipe receiver yang berada di balik pointer (misal: `&self`, `&mut self`, `Box<Self>`). Metode tidak boleh menerima argumen bertipe `Self` secara nilai atau mengembalikan tipe `Self`.
   - Tidak menggunakan *associated functions* tanpa parameter `self` (static factory methods).

---

#### 3.3. Associated Types vs Generic Type Parameters

Pertimbangan antara `Trait<T>` dan `Trait::{ type Item; }` didasarkan pada relasi kardinalitas tipe:

* **Generic Parameter (`Trait<T>`)**:
  - Memungkinkan relasi **1-ke-Banyak** (*one-to-many*).
  - Satu tipe konkret dapat mengimplementasikan trait yang sama berulang kali dengan parameter tipe berbeda.
  - *Use Case*: `From<T>`, di mana `MyType` dapat dibentuk dari `String`, `u64`, atau `&[u8]`.

* **Associated Type (`type Item;`)**:
  - Menetapkan relasi **1-ke-1** (*one-to-one mapping*).
  - Menghindari polusi penulisan tipe tingkat tinggi (*type parameter explosion*).
  - Mengunci implementasi: Untuk satu tipe konkret implementor, hanya ada tepat satu tipe keluaran terkait.
  - *Use Case*: `Iterator`, di mana sebuah `VecIterator` hanya menghasilkan satu tipe item konkret tertentu.

---

#### 3.4. Zero-Sized Types (ZST) & The Type-State Pattern

* **Zero-Sized Types (ZST)**:
  Struktur data seperti `struct Empty;` atau `PhantomData<T>` berukuran **0 byte** (`std::mem::size_of::<T>() == 0`). 
  
  Kompiler Rust mengoptimalkan ZST hingga tingkat di mana manipulasi tipe tersebut tidak menghasilkan kode assembly untuk alokasi atau pergeseran memori, namun status tipe tetap divalidasi secara ketat oleh *type checker*.

* **Type-State Pattern**:
  Pola rekayasa perangkat lunak di mana status siklus hidup objek (misal: *Unauthenticated*, *Authenticated*, *Executing*, *Terminated*) dimodelkan sebagai ZST yang disematkan ke dalam generic parameter struct. Transisi status mengonsumsi instance lama melalui pemindahan kepemilikan (*move semantics*), sehingga menghasilkan status baru secara statis dan mengeliminasi bug akibat akses status yang tidak valid pada runtime.

---

### 4. Why & What

| Fitur / Paradigma | Mengapa Digunakan? (Masalah Arsitektural) | Apa Mekanisme Kerjanya? (Solusi Rust) |
|---|---|---|
| **Zero-Cost Abstractions** | Mencegah trade-off antara keterbacaan kode (*clean abstractions*) dan efisiensi instruksi CPU/memori. | Kompilator mengevaluasi dan meratakan (*flattening*) abstraksi menjadi instruksi mesin langsung yang setara dengan penulisan manual bahasa C/Assembly. |
| **Type-State Pattern** | Mencegah runtime assertion error (seperti `IllegalStateException`) saat operasi dijalankan pada state yang tidak valid. | Merepresentasikan status mesin sebagai generic ZST. Fungsi tertentu hanya diimplementasikan untuk tipe status tertentu; transisi status memindahkan (`move`) kepemilikan. |
| **Blanket Implementations** | Mengurangi boilerplate kode duplikatif pada library skala besar. | Mengimplementasikan trait secara otomatis untuk semua tipe yang memenuhi kondisi/trait lain yang ditentukan (contoh: `impl<T: Display> ToString for T`). |
| **Higher-Rank Trait Bounds (HRTB)** | Mendukung trait bound yang memerlukan fleksibilitas lifetime universal tanpa mengikat lifetime tersebut ke parameter struct/fungsi pemanggil. | Menggunakan sintaks `for<'a>` untuk menyatakan bahwa implementasi trait valid untuk rentang lifetime `'a` berapapun. |

---

### 5. How (Workflow & Decision Tree)

Berikut adalah panduan pemilihan strategi polimorfisme dalam arsitektur perangkat lunak enterprise:

```
                          [Kebutuhan Polimorfisme]
                                     |
             +-----------------------+-----------------------+
             |                                               |
   Koleksi Bersifat Homogen?                       Koleksi Bersifat Heterogen?
   (Satu tipe per container/call)                 (Banyak tipe dalam satu struktur)
             |                                               |
             v                                               v
    [Static Dispatch]                             Berapa estimasi variasi tipe?
             |                                               |
     Beban Kompilasi/Biner                   +---------------+---------------+
     Kritis vs Throughput?                   |                               |
             |                         Terbatas/Tertutup              Terbuka/Plugin
     +-------+-------+                 (Bounded variants)             (Open hierarchy)
     |               |                       |                               |
 Throughput       Ukuran Biner               v                               v
 Maksimal           Kritis             [Tagged Enum /                 [dyn Trait]
     |               |                 enum_dispatch]             Fat Pointer Heap
     v               v                       |                               |
[Generics +    [Outline Function             v                               v
 Trait Bounds]   Non-Generic Logic]    Cache-Friendly Data          Dynamic Dispatch
 (Monomorphized)                       No Heap, Zero Indirection    (vtable overhead)
```

#### Langkah Penerapan Type-State Pattern:
1. **Definisikan State Marker**: Buat serangkaian unit struct ZST (`pub struct Draft;`, `pub struct Signed;`).
2. **Definisikan Context Struct**: Buat struct generik penampung data inti dengan `std::marker::PhantomData<State>`.
3. **Isolasi Method via Trait / Direct Impl**:
   - Tulis `impl Transaction<Draft> { pub fn sign(self) -> Transaction<Signed> { ... } }`.
   - Hindari mengekspos metode final (seperti `broadcast()`) pada implementasi blok `Draft`.
4. **Enforce Drop Semantics**: Pastikan resource dilepaskan atau dikonsumsi pada status akhir.

---

### 6. Analogy & Diagram ASCII

#### Analogi Vtable vs Monomorfisasi:
- **Monomorfisasi**: Seperti mencetak manual panduan kerja khusus untuk setiap divisi. Tim Finansial mendapat buku panduan Finansial, tim IT mendapat buku IT. Eksekusi sangat cepat tanpa membaca indeks, namun rak buku kantor menjadi sangat tebal.
- **Dynamic Dispatch (`dyn Trait`)**: Seperti satu kartu tugas generik berisi alamat meja dan nomor telepon departemen ahli yang harus dihubungi. Rak buku sangat tipis, namun setiap langkah kerja membutuhkan waktu panggilan telepon (indirection) untuk mencari tahu apa yang harus dilakukan.

#### Diagram Komparasi Tata Letak Memori

```
1. Static Polymorphism (Monomorphized)
Stack Frame:
[Concrete Struct Type A: 24 bytes] -> Value directly embedded in stack
Panggilan fungsi: CALL direct_address_to_impl_A (Hardcoded offset)

2. Dynamic Polymorphism (dyn Trait via Box<dyn Trait>)
Stack Frame:
+------------------------------------+------------------------------------+
| Pointer Heap Data: 0x7FFF0010 (8B) | Pointer Vtable: 0x555500A0 (8B)    |
+------------------------------------+------------------------------------+
               |                                      |
               v                                      v
Heap Alokasi: [Concrete Type A (24B)]   Data Read-Only (.rodata):
                                        +--------------------------------+
                                        | Drop Glue: 0x55550020          |
                                        | Size: 24, Align: 8             |
                                        | fn execute(): 0x55550040       |
                                        +--------------------------------+
Panggilan fungsi:
  MOV RAX, [Vtable_Ptr + 16]   ; Ambil pointer fn execute
  MOV RDI, Data_Ptr            ; Masukkan self pointer sebagai argumen pertama
  CALL RAX                     ; Indirect jump
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Bukti Pengukuran Memori Zero-Cost Abstraction vs Fat Pointer

```rust
use std::mem::size_of;

trait Worker {
    fn work(&self);
}

struct FastWorker {
    pub id: u64,
}

impl Worker for FastWorker {
    fn work(&self) {
        println!("Worker {} processing", self.id);
    }
}

// Marker ZST
struct ActiveState;

// Struct memanfaatkan ZST
struct StateEngine<S> {
    id: u32,
    _state: std::marker::PhantomData<S>,
}

fn main() {
    // 1. Verifikasi ukuran Zero-Sized Type
    assert_eq!(size_of::<ActiveState>(), 0);
    
    // 2. Struct dengan ZST memiliki ukuran sama persis dengan field primitifnya
    assert_eq!(size_of::<StateEngine<ActiveState>>(), size_of::<u32>());
    
    // 3. Concrete Instance vs Fat Pointer Trait Object
    let concrete = FastWorker { id: 101 };
    let dyn_ref: &dyn Worker = &concrete;
    let boxed_dyn: Box<dyn Worker> = Box::new(concrete);

    println!("Ukuran Concrete struct: {} bytes", size_of::<FastWorker>()); // 8 bytes
    println!("Ukuran Reference statis: {} bytes", size_of::<&FastWorker>()); // 8 bytes
    println!("Ukuran Fat Pointer (&dyn Worker): {} bytes", size_of::<&dyn Worker>()); // 16 bytes
    println!("Ukuran Boxed Fat Pointer: {} bytes", size_of::<Box<dyn Worker>>()); // 16 bytes

    dyn_ref.work();
    boxed_dyn.work();
}
```

---

#### 7.2. Practical Example: Pipeline Transformasi Data Berkecepatan Tinggi

Implementasi arsitektur enterprise menggunakan kombinasi *Associated Types*, *Marker Trait*, dan *Blanket Implementation* untuk memproses stream data analitik tanpa alokasi memori heap runtime.

```rust
use std::fmt::Debug;

pub trait IngestionPayload: Send + Sync + Debug + 'static {
    type Identifier: Copy + Eq + std::hash::Hash + Debug;
    fn extract_id(&self) -> Self::Identifier;
}

pub trait Transformer<Input: IngestionPayload> {
    type Output;
    type Error: std::error::Error + Send + Sync + 'static;

    fn transform(&self, input: Input) -> Result<Self::Output, Self::Error>;
}

// Marker trait untuk menandakan komputasi zero-copy
pub trait ZeroCopySafe: Sized {}

// Struct Data Pipeline
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct MetricId(pub u64);

#[derive(Debug)]
pub struct RawTelemetry {
    pub sensor_id: MetricId,
    pub temperature: f64,
    pub timestamp_epoch_ms: u64,
}

impl IngestionPayload for RawTelemetry {
    type Identifier = MetricId;
    #[inline(always)]
    fn extract_id(&self) -> Self::Identifier {
        self.sensor_id
    }
}

impl ZeroCopySafe for RawTelemetry {}

#[derive(Debug)]
pub struct NormalizedTelemetry {
    pub id: MetricId,
    pub temp_kelvin: f64,
}

// Implementasi Transformer spesifik
pub struct TelemetryNormalizer;

#[derive(thiserror::Error, Debug)]
pub enum PipelineError {
    #[error("Nilai sensor di luar batas fisik: {0}")]
    UnrealisticReading(f64),
}

impl Transformer<RawTelemetry> for TelemetryNormalizer {
    type Output = NormalizedTelemetry;
    type Error = PipelineError;

    #[inline]
    fn transform(&self, input: RawTelemetry) -> Result<Self::Output, Self::Error> {
        if input.temperature < -273.15 {
            return Err(PipelineError::UnrealisticReading(input.temperature));
        }
        
        Ok(NormalizedTelemetry {
            id: input.extract_id(),
            temp_kelvin: input.temperature + 273.15,
        })
    }
}

// Blanket Implementation: Secara otomatis membungkus semua Transformer dengan fungsionalitas Audit Log
pub trait AuditableTransformer<Input: IngestionPayload>: Transformer<Input> {
    fn transform_and_audit(&self, input: Input) -> Result<Self::Output, Self::Error>
    where
        Self::Output: Debug,
    {
        let id = input.extract_id();
        let result = self.transform(input);
        match &result {
            Ok(out) => println!("[AUDIT SUCCESS] ID: {:?} | Output: {:?}", id, out),
            Err(err) => eprintln!("[AUDIT ERROR] ID: {:?} | Error: {:?}", id, err),
        }
        result
    }
}

impl<T, Input> AuditableTransformer<Input> for T 
where 
    T: Transformer<Input>,
    Input: IngestionPayload,
{}

pub fn run_pipeline() {
    let raw = RawTelemetry {
        sensor_id: MetricId(42),
        temperature: 25.5,
        timestamp_epoch_ms: 1700000000000,
    };

    let normalizer = TelemetryNormalizer;
    let _ = normalizer.transform_and_audit(raw);
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah Arsitektural: High-Frequency Trading (HFT) Execution Engine
Sistem perdagangan instrumen keuangan membutuhkan arsitektur pipeline order dengan karakteristik:
1. **Zero-Latency Invariants**: Tidak boleh ada kemungkinan order dikirimkan ke pasar bursa (`Routed`) sebelum melewati pemeriksaan batas risiko (`RiskChecked`) dan penandatanganan kriptografis (`Signed`).
2. Pemeriksaan berbasis runtime (seperti `if order.status != Status::RiskChecked`) membuang puluhan siklus CPU per transaksi dan rentan terhadap human error dari pengembang.
3. Namun, protokol konektivitas broker target (FIX Engine, Binary Packet, REST Fallback) perlu dihubungkan secara modular menggunakan sistem antarmuka berbasis traits.

#### Solusi Arsitektur:
- Menggunakan **Type-State Pattern** untuk siklus hidup Order, menjamin validasi alur 100% pada saat kompilasi.
- Menggunakan **Monomorphization Outlining Pattern** untuk adapter broker demi meminimalkan ukuran I-cache instruction binary.

```rust
use std::marker::PhantomData;

// --- DOMAIN ZERO-SIZED STATES ---
pub struct Draft;
pub struct Signed;
pub struct RiskChecked;
pub struct Routed;

// --- ORDER CORE ---
pub struct Order<State> {
    pub order_id: u128,
    pub symbol: String,
    pub quantity: u32,
    pub price: u64, // Scaled integer (misal: 10000 = $1.0000)
    _state: PhantomData<State>,
}

// Implementasi fungsi yang hanya ada pada State Draft
impl Order<Draft> {
    pub fn new(order_id: u128, symbol: impl Into<String>, quantity: u32, price: u64) -> Self {
        Self {
            order_id,
            symbol: symbol.into(),
            quantity,
            price,
            _state: PhantomData,
        }
    }

    pub fn sign(self, cryptographic_key: &[u8]) -> Result<Order<Signed>, &'static str> {
        if cryptographic_key.is_empty() {
            return Err("Kunci kriptografis tidak valid");
        }
        // Konsumsi self, hasilkan state Signed tanpa alokasi heap
        Ok(Order {
            order_id: self.order_id,
            symbol: self.symbol,
            quantity: self.quantity,
            price: self.price,
            _state: PhantomData,
        })
    }
}

// Implementasi fungsi yang hanya ada pada State Signed
impl Order<Signed> {
    pub fn verify_risk(self, max_notional_limit: u64) -> Result<Order<RiskChecked>, &'static str> {
        let notional = self.quantity as u64 * self.price;
        if notional > max_notional_limit {
            return Err("Limit risiko terlampaui: Order ditolak");
        }
        
        Ok(Order {
            order_id: self.order_id,
            symbol: self.symbol,
            quantity: self.quantity,
            price: self.price,
            _state: PhantomData,
        })
    }
}

// --- GATEWAY ADAPTER INTERFACE ---
pub trait BrokerConnector {
    type ExecutionAck;
    type ConnectionError: std::error::Error;

    // Memaksa bahwa HANYA order dengan status RiskChecked yang bisa diproses
    fn dispatch_order(&mut self, order: Order<RiskChecked>) -> Result<Self::ExecutionAck, Self::ConnectionError>;
}

// --- CONCRETE BROKER IMPLEMENTATION ---
pub struct NasdaqOuchConnector {
    pub session_token: u32,
}

#[derive(Debug)]
pub struct OrderAck {
    pub exchange_order_id: u64,
    pub status: &'static str,
}

#[derive(thiserror::Error, Debug)]
pub enum OuchError {
    #[error("Koneksi socket terputus")]
    SocketDisconnected,
}

impl BrokerConnector for NasdaqOuchConnector {
    type ExecutionAck = OrderAck;
    type ConnectionError = OuchError;

    fn dispatch_order(&mut self, order: Order<RiskChecked>) -> Result<Self::ExecutionAck, Self::ConnectionError> {
        // Transisi terminal ke Routed (hanya representasi logika lokal)
        let _terminal_order: Order<Routed> = Order {
            order_id: order.order_id,
            symbol: order.symbol,
            quantity: order.quantity,
            price: order.price,
            _state: PhantomData,
        };

        // Kirim paket biner ke bursa secara zero-copy
        Ok(OrderAck {
            exchange_order_id: 9988772211,
            status: "ACCEPTED",
        })
    }
}

// Entrypoint simulasi transaksi enterprise
pub fn process_order_lifecycle() -> Result<OrderAck, Box<dyn std::error::Error>> {
    let order = Order::new(1001, "NVDA", 500, 120_0000);
    
    // Pipeline eksekusi statis yang rigid:
    let signed_order = order.sign(b"enterprise_secret_hsm_key")?;
    let validated_order = signed_order.verify_risk(100_000_0000)?;
    
    let mut connector = NasdaqOuchConnector { session_token: 0xDEADBEEF };
    let ack = connector.dispatch_order(validated_order)?;

    Ok(ack)
}
```

---

### 9. Trade-offs: Analisis Matriks Rekayasa

| Karakteristik | Static Dispatch (Generics, Monomorphization) | Dynamic Dispatch (`dyn Trait` Fat Pointer) |
|---|---|---|
| **Eksekusi Instruksi (CPU Cycles)** | Optimal. Panggilan fungsi langsung (*direct call*), mendukung *full inlining* dan SIMD autovectorization oleh LLVM. | Sub-optimal. Panggilan via *pointer indirection* (vtable), instruksi jump tidak langsung (`call *%rax`), kegagalan *inlining*. |
| **Pemanfaatan Memory Cache (I-Cache)** | Buruk pada skala tipe ekstrem. Terjadinya *binary bloat* meningkatkan kemungkinan *Instruction Cache Misses*. | Sangat baik. Hanya ada satu representasi fungsi di memori `.text`, menghemat penggunaan *L1 Instruction Cache*. |
| **Waktu Kompilasi (Compile-time)** | Lambat. Kompiler memproses AST dan LLVM IR berulang kali untuk setiap tipe instansiasi konkret. | Cepat. Kompiler hanya memproses interface satu kali dan menghasilkan struktur vtable. |
| **Ukuran Biner Eksekusi (.text segment)** | Membesar secara linear seiring bertambahnya permutasi tipe konkret. | Statis dan minimalis. |
| **Fleksibilitas Desain Sistem** | Terkunci pada waktu kompilasi. Tipe harus diketahui secara eksplisit pada setiap batas modul. | Sangat fleksibel. Memungkinkan arsitektur *runtime plugin*, dynamic container heterogen (`Vec<Box<dyn T>>`). |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Lifetime Trait Object Defaulting ke `'static`
* **Gejala**: Error kompilasi `lifetime may not live long enough` saat mengembalikan trait object referensi lokal.
* **Akar Masalah**: Tipe `Box<dyn Trait>` secara implisit mengasumsikan trait bound `Box<dyn Trait + 'static>`. Jika trait object meminjam data dari scope lokal, batasan default ini melanggar model ownership.
* **Solusi Perbaikan**: Definisikan lifetime eksplisit:
  ```rust
  // SALAH: Mengasumsikan 'static secara implisit
  fn get_processor(data: &Context) -> Box<dyn Processor> { ... }

  // BENAR: Deklarasikan keterikatan lifetime referensi konkret
  fn get_processor<'a>(data: &'a Context) -> Box<dyn Processor + 'a> { ... }
  ```

#### Kasus 2: Pelanggaran Kriteria Object Safety
* **Gejala**: Pesan kesalahan `the trait cannot be made into an object because it requires Self: Sized` atau `method has generic type parameters`.
* **Akar Masalah**: Vtable memerlukan ukuran layout tetap. Jika metode trait menerima generic parameter `fn parse<U: Read>(&self, input: U)`, rustc tidak dapat membuat pointer fungsi statis di vtable karena ukuran dan variasi `U` tak hingga.
* **Solusi Perbaikan**: Pisahkan metode non-object-safe ke sub-trait atau batasi dengan `where Self: Sized`:
  ```rust
  pub trait SuperService {
      // Metode ini aman untuk dyn Trait
      fn dispatch(&self, id: u64);

      // Sembunyikan metode generic dari vtable
      fn ingest_generic<T: IngestionPayload>(&self, data: T) 
      where 
          Self: Sized;
  }
  ```

#### Kasus 3: Monomorphization Bloat Menggandakan Logika Panjang Non-Generik
* **Gejala**: Waktu link (`rust-lld`) melambat drastis dan biner bengkak dari 15MB menjadi 120MB.
* **Akar Masalah**: Seluruh blok fungsi generik besar diduplikasi untuk setiap tipe data, meskipun 90% logikanya tidak berhubungan dengan tipe tersebut.
* **Solusi Perbaikan**: Gunakan teknik **Inner Function Outlining**:
  ```rust
  // BURUK: Semua kode ini dimonomorfisasi berulang kali
  pub fn write_payload<T: Serialize>(item: &T, path: &str) {
      println!("Inisialisasi path log...");
      let serialized = serde_json::to_vec(item).unwrap();
      std::fs::write(path, serialized).unwrap();
  }

  // BAIK: Pisahkan logika I/O non-generik ke fungsi internal konkret
  pub fn write_payload_optimized<T: Serialize>(item: &T, path: &str) {
      let serialized = serde_json::to_vec(item).unwrap();
      internal_write_bytes(path, &serialized); // Logika besar dipusatkan
  }

  fn internal_write_bytes(path: &str, data: &[u8]) {
      println!("Inisialisasi path log...");
      std::fs::write(path, data).unwrap();
  }
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Trait Boundaries Segregation**: Terapkan *Interface Segregation Principle*. Buat trait kecil dan modular (`Reader`, `Writer`), lalu satukan via *Supertraits* (`pub trait ReadWriter: Reader + Writer {}`).
- [ ] **Type-State Invariants Enforcement**: Gunakan `PhantomData` untuk validasi status objek yang kritis, guna mencegah percabangan logika berbasis runtime (`assert!(status == ACTIVE)`).
- [ ] **Heap Mitigation**: Gunakan `enum_dispatch` crate jika variasi polimorfisme runtime Anda bersifat tertutup (*closed-set variants*), untuk menghindari alokasi `Box<dyn Trait>` dan fat pointer dereference.
- [ ] **Coherence Guarding**: Manfaatkan Newtype Pattern (`struct MyWrapper(ForeignType)`) saat perlu mengimplementasikan foreign trait pada foreign struct untuk mematuhi aturan *Orphan Rule*.
- [ ] **Marker Trait Audit**: Tandai tipe-tipe transfer aman dengan `Send` dan `Sync` secara sadar. Jangan gunakan `unsafe impl Send` tanpa audit dokumen invariant pointer raw.
- [ ] **Diagnostic Binary Inspection**: Jalankan `cargo bloat --release --crates` dan `cargo bloat --release --split-sections` secara rutin di pipeline CI/CD untuk mendeteksi monomorphization explosion sejak dini.

---

### 12. Hands-on Practice

Buatlah implementasi lengkap sebuah extensible pipeline audit logging industri. Simpan semua kode ini di subdirektori proyek Anda: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Proyek Cargo
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
cargo init --lib
```

#### Langkah 2: Konfigurasi `Cargo.toml`
Buka berkas `hands-on/m02/Cargo.toml` dan sesuaikan dependensinya:
```toml
[package]
name = "m02_zero_cost_arch"
version = "0.1.0"
edition = "2021"

[dependencies]
thiserror = "1.0"

[dev-dependencies]
criterion = "0.5"
```

#### Langkah 3: Implementasi Pustaka Utama `hands-on/m02/src/lib.rs`
```rust
use std::marker::PhantomData;
use std::fmt::Debug;

// 1. Definisikan HRTB Trait untuk validasi referensi payload
pub trait Evaluator {
    // Higher-Rank Trait Bound: Harus bisa memproses payload dengan lifetime apapun
    fn evaluate<'a>(&self, input: &'a str) -> bool;
}

pub struct SecurityScanner;
impl Evaluator for SecurityScanner {
    fn evaluate<'a>(&self, input: &'a str) -> bool {
        !input.contains("DROP TABLE") && !input.contains("<script>")
    }
}

// 2. Type-State Pipeline Pattern
pub struct Unverified;
pub struct Verified;
pub struct Processed;

#[derive(Debug, PartialEq, Eq)]
pub struct TransactionPayload<S> {
    pub account_id: u64,
    pub amount: u64,
    pub statement: String,
    _state: PhantomData<S>,
}

impl TransactionPayload<Unverified> {
    pub fn new(account_id: u64, amount: u64, statement: impl Into<String>) -> Self {
        Self {
            account_id,
            amount,
            statement: statement.into(),
            _state: PhantomData,
        }
    }

    pub fn run_security_check<E: Evaluator>(
        self, 
        evaluator: &E
    ) -> Result<TransactionPayload<Verified>, &'static str> {
        if evaluator.evaluate(&self.statement) {
            Ok(TransactionPayload {
                account_id: self.account_id,
                amount: self.amount,
                statement: self.statement,
                _state: PhantomData,
            })
        } else {
            Err("Anomali keamanan terdeteksi pada pernyataan transaksi")
        }
    }
}

impl TransactionPayload<Verified> {
    pub fn execute_transaction(self) -> TransactionPayload<Processed> {
        // Eksekusi core transaksi
        TransactionPayload {
            account_id: self.account_id,
            amount: self.amount,
            statement: self.statement,
            _state: PhantomData,
        }
    }
}

// 3. Dynamic Dispatch Boundary (Plugin Fallback)
pub trait LedgerPlugin: Send + Sync {
    fn name(&self) -> &'static str;
    fn record_ledger(&self, account: u64, amount: u64) -> Result<(), String>;
}

pub struct EnterpriseLedgerEngine {
    plugins: Vec<Box<dyn LedgerPlugin>>,
}

impl EnterpriseLedgerEngine {
    pub fn new() -> Self {
        Self { plugins: Vec::new() }
    }

    pub fn register_plugin(&mut self, plugin: Box<dyn LedgerPlugin>) {
        self.plugins.push(plugin);
    }

    pub fn commit(&self, payload: &TransactionPayload<Processed>) -> Result<(), String> {
        for plugin in &self.plugins {
            plugin.record_ledger(payload.account_id, payload.amount)?;
        }
        Ok(())
    }
}
```

#### Langkah 4: Pengujian Integrasi Unit `hands-on/m02/tests/pipeline_test.rs`
Buat direktori `tests/` dan file `tests/pipeline_test.rs`:
```rust
use m02_zero_cost_arch::*;

struct MockDatabaseLogger;
impl LedgerPlugin for MockDatabaseLogger {
    fn name(&self) -> &'static str {
        "MockDatabaseLogger"
    }

    fn record_ledger(&self, account: u64, amount: u64) -> Result<(), String> {
        println!("Logging to DB: acc {} transfer {}", account, amount);
        Ok(())
    }
}

#[test]
fn test_type_state_transition_success() {
    let tx = TransactionPayload::new(12345, 5000, "Normal Invoice Payment");
    let scanner = SecurityScanner;

    // Compile-time guaranteed transitions
    let verified_tx = tx.run_security_check(&scanner).expect("Validasi gagal");
    let processed_tx = verified_tx.execute_transaction();

    let mut engine = EnterpriseLedgerEngine::new();
    engine.register_plugin(Box::new(MockDatabaseLogger));

    let result = engine.commit(&processed_tx);
    assert!(result.is_ok());
}

#[test]
fn test_security_violation() {
    let malicious_tx = TransactionPayload::new(999, 10, "DROP TABLE users;");
    let scanner = SecurityScanner;

    let result = malicious_tx.run_security_check(&scanner);
    assert!(result.is_err());
}
```

Uji hands-on Anda dengan perintah:
```bash
cargo test
```

---

### 13. Exercise

#### Level Easy
Buat struct `Celsius(pub f64)` dan `Fahrenheit(pub f64)`. Implementasikan trait bawaan standar `From<Celsius> for Fahrenheit` dan `From<Fahrenheit> for Celsius`. Pastikan kedua implementasi zero-allocation dan verifikasi menggunakan unit test asserting akurasi konversi.

#### Level Medium
Buat trait `StorageBackend` dengan associated type `type RecordId;` dan `type Error;`. Implementasikan trait ini pada dua tipe: `MemoryStorage` (menggunakan RecordId = `u64`) dan `DistributedStorage` (menggunakan RecordId = `String`). Tulis fungsi generik `sync_records<S: StorageBackend>(storage: &mut S, id: S::RecordId) -> Result<(), S::Error>` yang membuktikan konsistensi tipe asosiasi tanpa duplikasi tanda tangan generic.

#### Level Hard
Rancang State Machine menggunakan Type-State Pattern untuk koneksi protokol jaringan: `Disconnected`, `Connecting`, `Connected`, `Suspended`.
- Hanya status `Connecting` yang dapat bertransisi ke `Connected` atau `Disconnected`.
- Status `Connected` memiliki metode `send_packet(&self, data: &[u8])` dan `suspend(self) -> Connection<Suspended>`.
- Buktikan bahwa mencoba memanggil `send_packet` langsung dari status `Disconnected` atau `Connecting` memicu **compile-time error**.

---

### 14. Challenge

**Skenario**: Anda adalah Core Platform Architect di bank digital tier-1. Anda diminta mendesain *Zero-Allocation Async Message Routing Engine*.

**Spesifikasi Masalah**:
1. Sistem menerima payload `NetworkFrame<'a>` yang meminjam slice byte langsung dari buffer ring kernel (epoll/io_uring).
2. Sistem memiliki rantai interceptor (*middleware*). Sebagian interceptor adalah tipe statis (diketahui pada waktu kompilasi untuk latensi sub-mikrodetik, misalnya: Auth Check, Rate Limiter), dan sebagian lainnya merupakan plugin dinamis pihak ketiga (`dyn Interceptor`) yang dimuat via dynamic linking (.so/.dll).
3. Anda **dilarang keras** mengalokasikan heap (`Box`, `Vec`, dsb.) pada critical path transaksi normal.
4. Buat arsitektur pipeline komposit yang:
   - Menggunakan *Static Tuple Chaining* atau *Variadic Generics Emulation* untuk menggabungkan middleware statis menjadi satu eksekusi tunggal monomorfik tanpa loop.
   - Menggunakan Higher-Rank Trait Bounds (`for<'buf>`) untuk memastikan reference buffer tidak mengalami kebocoran memori melewati masa hidup frame jaringan.
   - Sediakan fallback boundary terisolasi untuk dynamic dispatch tanpa merusak optimasi inline pada interceptor statis.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Berapa ukuran memori standar dari fat pointer `&dyn Trait` pada platform x86_64, dan apa isi dari masing-masing komponen memorinya?
2. Mengapa Zero-Sized Types (ZST) tidak memakan ruang memori runtime sedikitpun meskipun dapat memiliki implementasi trait dan methods?
3. Sebutkan dua alasan utama mengapa sebuah trait **tidak** memenuhi syarat Object Safety!
4. Apa perbedaan mendasar antara `trait Transformer<T>` dengan `trait Transformer { type Output; }` dalam hal batasan implementasi pada tipe konkret?
5. Mengapa penambahan banyak parameter generik pada fungsi kritis dapat menyebabkan pembengkakan ukuran file biner (*monomorphization bloat*)?

#### 5 Pertanyaan Intermediate
6. Bagaimana cara compiler Rust membersihkan memori heap yang dialokasikan di dalam `Box<dyn Trait>` ketika instance tersebut keluar dari scope (drop)?
7. Dalam kondisi apa kita sebaiknya memilih `enum_dispatch` dibandingkan dengan `Box<dyn Trait>`? Jelaskan dari perspektif branch prediction dan heap allocation!
8. Apa fungsi dari Higher-Rank Trait Bounds (HRTB) dengan sintaks `for<'a>` dan masalah apa yang dipecahkannya dibandingkan lifetime generik biasa (`<'a>`)?
9. Apa yang dimaksud dengan *Blanket Implementation* dalam Rust dan sebutkan satu contoh penggunaannya di standard library (`std`)!
10. Bagaimana teknik *Inner-Function Outlining* dapat secara efektif memitigasi waktu kompilasi dan mempertahankan performa L1 Instruction Cache pada fungsi generik?

#### 3 Skenario Kasus Produksi
11. **Skenario Produksi 1**: Sebuah microservice pemrosesan gambar mengalami penurunan performa (latensi naik drastis dari 2ms ke 45ms) setelah seorang developer mengubah arsitektur pipeline dari:
    `fn process<P: Pipeline>(p: P)` menjadi `fn process(p: &dyn Pipeline)`.
    Jelaskan analisis profiling Anda terkait CPU pipeline, instruksi per siklus (IPC), dan inlining yang menyebabkan fenomena ini!
12. **Skenario Produksi 2**: Anda memiliki struct `DatabasePool<State>`. Developer junior mencoba menambahkan generic status runtime menggunakan field enum:
    ```rust
    pub enum State { Connected, Disconnected }
    pub struct DatabasePool { state: State }
    ```
    Mengapa pendekatan di atas kurang optimal untuk transaksi berskala ultra-reliabel dibandingkan Type-State Pattern berbasis ZST, dan bagaimana konsekuensinya terhadap unit test?
13. **Skenario Produksi 3**: Tim Anda mendesain sistem plugin modular menggunakan Rust. Salah satu developer menulis trait:
    ```rust
    pub trait Plugin {
        fn process_event<T: serde::Serialize>(&self, event: T);
    }
    ```
    Ketika mereka mencoba mendaftarkan plugin via `Vec<Box<dyn Plugin>>`, rustc menolak kompilasi dengan keras. Apa penyebab teknisnya, dan bagaimana restrukturisasi trait yang harus dilakukan tanpa mengorbankan serialisasi event?

---

#### Kunci Jawaban Evaluasi Pemahaman

1. **Ukuran Fat Pointer**: Berukuran 16 byte (2 word/8 byte per pointer). Komponen pertama adalah **Data Pointer** (alamat memori data instance konkret), dan komponen kedua adalah **Vtable Pointer** (alamat tabel metode virtual di segmen `.rodata`).
2. **Karakteristik ZST**: ZST memiliki `size_of::<T>() == 0`. Kompiler Rust sepenuhnya menyadari bahwa ZST tidak memerlukan alokasi byte untuk membedakan nilainya, sehingga seluruh representasinya dihilangkan saat kode mesin dihasilkan, namun tetap digunakan oleh *borrow checker* dan *type checker* di fase kompilasi.
3. **Syarat Batal Object Safety**: Trait memerlukan `Self: Sized`, memiliki metode yang menerima/mengembalikan tipe `Self` secara nilai, atau metode yang memiliki parameter generik sendiri.
4. **Perbedaan Associated Types vs Generics**: Generic parameter `Trait<T>` mengizinkan multiple implementation (satu struct bisa mengimplementasikan `Trait<A>` dan `Trait<B>`). Associated type `type Output;` membatasi tipe konkret untuk hanya memiliki **satu** implementasi unik dari trait tersebut.
5. **Akar Monomorphization Bloat**: rustc menduplikasi instruksi mesin untuk setiap kombinasi tipe konkret yang digunakan. Jika ada 100 variasi tipe pada fungsi besar, akan tercipta 100 salinan kode assembly yang hampir identik di blok executable.
6. **Drop Glue pada Trait Object**: Vtable fat pointer menyimpan pointer fungsi destructor pertama bernama *drop glue*. Saat `Box<dyn Trait>` keluar dari scope, drop glue membaca metadata alignment dan size yang ada di vtable, memanggil destruktor tipe konkret implementor, lalu melepaskan blok memori pada heap allocator.
7. **Pilihan `enum_dispatch`**: Ketika variasi tipe konkret bersifat terbatas dan tertutup. Pola ini tidak membutuhkan alokasi heap pointer indirection, melainkan menggunakan `match` jump table lokal yang flat, sangat ramah pada L1 Data/Instruction Cache dan mudah diprediksi oleh CPU Branch Predictor.
8. **Fungsi HRTB (`for<'a>`)**: Digunakan untuk menetapkan batasan bahwa trait harus valid untuk *semua* lifetime `'a` yang mungkin dimasukkan saat runtime, bukan hanya satu lifetime tetap yang diikat oleh struct atau signature pemanggil. Esensial untuk closure dan parser memori buffer lokal.
9. **Blanket Implementation**: Kemampuan mengimplementasikan trait pada *semua* tipe yang memenuhi kondisi trait lain secara global. Contoh di std: `impl<T: Display> ToString for T` secara instan memberikan metode `.to_string()` pada tipe apapun yang telah mengimplementasikan `Display`.
10. **Mekanisme Inner Outlining**: Kode non-generik dipindahkan keluar dari blok fungsi generik ke dalam private helper function konkret. Hal ini membuat duplikasi LLVM IR berkurang drastis; hanya adapter parsing kecil yang dimonomorfisasi, sementara logika kompleks di-*share* pada satu lokasi biner `.text`.
11. **Analisis Skenario 1**: Pengalihan ke `&dyn Pipeline` mematikan kapabilitas LLVM untuk melakukan *function inlining*. Instruksi pemrosesan piksel/gambar loop mikro tidak dapat di-*unroll* atau divaktorisasi menggunakan instruksi SIMD (AVX-512/NEON). Penunjuk ganda pada loop ketat mengakibatkan *Branch Target Buffer (BTB) thrashing* dan *pipeline stalls*, meruntuhkan efisiensi IPC.
12. **Analisis Skenario 2**: Pendekatan enum runtime memindahkan beban pengecekan ke percabangan runtime (`match self.state`). Ini menyisakan celah bug berupa *runtime panic* / `IllegalState` saat dev lupa mengecek status, serta mewajibkan penulisan puluhan unit test defensif untuk memvalidasi error handling di setiap status ilegal. Type-State ZST memvalidasi ini secara statis: kode yang melanggar urutan operasi **tidak akan pernah berhasil dikompilasi**.
13. **Analisis Skenario 3**: Metode generic `fn process_event<T: Serialize>` melanggar aturan object safety karena vtable tidak dapat memuat jumlah entry tak berhingga untuk semua kemungkinan tipe `T`. Solusinya adalah mengubah metode tersebut agar menerima trait object `&dyn ErasedSerialize` (menggunakan crate seperti `erased-serde`), atau membatasi serialisasi pada format payload konkret/tertentu seperti slice byte `&[u8]` atau struct enum wrapper sebelum dikirimkan ke plugin.

---

### 16. Summary

1. **Abstraksi Nol-Biaya (Zero-Cost Abstraction)** di Rust menjamin bahwa kode tingkat tinggi yang aman, ekspresif, dan modular dikompilasi menjadi representasi assembly yang sama optimalnya—atau lebih optimal—dibandingkan kode tingkat rendah yang ditulis manual.
2. **Static Dispatch (Monomorphization)** memberikan performa komputasi murni tertinggi melalui *inlining* dan autovectorization, namun memiliki konsekuensi pembengkakan ukuran biner (*binary bloat*) dan waktu kompilasi yang meningkat.
3. **Dynamic Dispatch (`dyn Trait`)** menyediakan fleksibilitas sistem, *extensibility*, dan ukuran biner yang ringkas melalui mekanisme Fat Pointer (16 bytes) dan vtable, dengan trade-off berupa *runtime indirection* dan batasan *Object Safety*.
4. **Type-State Pattern** yang dikombinasikan dengan **Zero-Sized Types (ZST)** merepresentasikan pendekatan terbaik untuk membangun sistem enterprise yang tangguh: mengonversi aturan integritas bisnis runtime menjadi batasan struktural waktu kompilasi tanpa penalti performa sama sekali.