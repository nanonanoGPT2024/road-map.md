# Bab 05 Module 01: Deep Dive Generics, Trait Bounds, dan Arsitektur Monomorphization

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Merancang dan mengimplementasikan abstraksi tipe generic tingkat lanjut menggunakan *Trait Bounds*, *Associated Types*, dan *Where Clauses* tanpa menimbulkan overhead runtime.
*   Menganalisis mekanisme internal kompilasi Rust (*Monomorphization*) dan implikasinya terhadap *Instruction Cache* (I-Cache), ukuran biner (*Code Bloat*), dan waktu kompilasi (*LLVM IR generation*).
*   Mendiagnosis dan mengoptimalkan trade-off antara *Static Dispatch* (`impl Trait` / Generics) dan *Dynamic Dispatch* (`dyn Trait`) pada sistem berkinerja tinggi.
*   Menerapkan pola rekayasa *Monomorphization Thinning* (teknik pemisahan kode non-generic) untuk mereduksi footprint biner pada level sistem produksi.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda harus telah menguasai:
*   Model kepemilikan memori Rust: *Ownership*, *Borrowing rules*, dan *Lifetime annotations* dasar (`'a`).
*   Deklarasi dasar `struct`, `enum`, dan blok `impl`.
*   Dasar trait standar Rust: `Clone`, `Copy`, `Debug`, `Display`, dan `Default`.
*   Pemahaman dasar arsitektur CPU: *Instruction pipelining*, *Cache hierarchy* (L1I/L1D), dan *Virtual Method Table* (vtable).

---

### 3. Concept
Generics di Rust adalah mekanisme **polimorfisme parametrik statis** (*static parametric polymorphism*). Berbeda dengan bahasa berbasis Virtual Machine (seperti Java yang menggunakan *Type Erasure*) atau bahasa berorientasi objek dinamis (seperti Python yang mengandalkan *Duck Typing* runtime), Rust menyelesaikan seluruh parameter tipe generic pada saat kompilasi melalui proses **Monomorphization**.

Secara fundamental:
1.  **Zero-Cost Abstraction**: Generic tidak membawa penalti alokasi memori heap tambahan atau pointer indirection saat runtime. Struktur generic direpresentasikan langsung dalam tata letak memori konkretnya (*flat memory layout*).
2.  **Trait Bounds sebagai Type Constraints**: Trait bounds bukan sekadar interface; mereka adalah kontrak formal yang diverifikasi oleh *borrow checker* dan *type engine* (`rustc`) pada level AST/HIR (*High-Level Intermediate Representation*) untuk memastikan tipe pemanggil mengimplementasikan operasi biner, tata letak, atau konvensi pemanggilan yang valid.
3.  **Compile-time Specialization via LLVM**: Rust mengonversi fungsi generic menjadi N fungsi konkret di LLVM IR. Setiap instansiasi tipe mendapatkan alamat kode instruksi unik di segmen memori `.text`, memungkinkan LLVM melakukan inlining agresif, *loop vectorization* (SIMD), dan *dead-code elimination*.

---

### 4. Why
Dalam rekayasa sistem berskala besar (*low-latency systems*, *game engine*, atau *distributed infrastructure*):
*   **Penghapusan Indirect Call Overhead**: Dynamic dispatch (`dyn Trait`) menggunakan pemanggilan fungsi tak langsung via pointer vtable (`call *%rax`). Hal ini menyebabkan CPU branch predictor tidak dapat memprediksi target lompatan secara optimal, memicu *pipeline stall* (penalti ~10-20 cycle per pemanggilan). Generics mengonversi pemanggilan menjadi direct jump (`call symbol_name`) yang deterministik.
*   **Inter-procedural Optimization**: Kompiler tidak dapat melakukan inlining pada dynamic call karena target fungsi baru diketahui saat runtime. Dengan generics dan monomorphization, pemanggilan fungsi leaf berukuran kecil dapat di-*inline* secara penuh, menghilangkan setup *stack frame* (`push %rbp`, alokasi stack, dan `pop %rbp`).
*   **Strict Compile-time Safety**: Kesalahan tipe, ketidakcocokan thread-safety (`Send`/`Sync`), atau durasi pinjaman memori (*lifetimes*) tertangkap 100% pada fase kompilasi tanpa perlu fallback ke runtime assertions.

---

### 5. What
Komponen inti arsitektur Generic dan Trait Bounds meliputi:

*   **Generic Type Parameter (`<T>`)**: Placeholder abstrak untuk tipe data konkret yang akan disubstitusi saat kompilasi.
*   **Trait Bounds (`<T: Trait>`)**: Deklarasi batasan kapabilitas minimal yang harus dipenuhi oleh `T`.
*   **`where` Clause**: Notasi struktural lanjutan untuk mengekspresikan relasi bound yang kompleks, multi-trait, atau melibatkan associated types dan lifetimes tanpa mengaburkan signature fungsi.
*   **Associated Types (`type Item;`)**: Tipe yang terikat pada trait yang memungkinkan simplifikasi generic parameters (hubungan 1-ke-1 antara implementor dan tipe output).
*   **Higher-Ranked Trait Bounds / HRTB (`for<'a>`)**: Ekspresi trait bound yang harus valid untuk *sembarang* lifetime `'a`.
*   **Monomorphization Engine**: Subsistem kompiler Rust yang mengumpulkan (*mono item collector*), menduplikasi, dan menghasilkan kode mesin unik untuk setiap instansiasi tipe konkret.

---

### 6. How
Alur kerja kompilasi generic hingga eksekusi mesin:

```
[Generic Rust Source Code]
          │
          ▼
   HIR/MIR Analysis ───► Type Checking & Trait Resolution
          │
          ▼
Monomorphization Collector ───► Identifikasi semua instansiasi konkret (e.g., T = i32, T = String)
          │
          ▼
   LLVM IR Generation ────────► Duplikasi fungsi per tipe konkret (fn_i32, fn_String)
          │
          ▼
  LLVM Optimizations ─────────► Function Inlining, SIMD Vectorization, Loop Unrolling
          │
          ▼
     Linker (ld) ─────────────► Peletakan fungsi konkret pada segmen .text file biner ELF/Mach-O/PE
```

1.  **Type Checking**: Kompiler memvalidasi bahwa implementasi generic hanya memanggil metode yang didefinisikan dalam Trait Bounds yang ditentukan.
2.  **Monomorphization Collection**: MIR (*Mid-level Intermediate Representation*) mengidentifikasi titik pemanggilan (*call sites*) konkret di seluruh crate dependency.
3.  **Codegen Duplication**: Setiap tipe konkret menghasilkan salinan kode mesin LLVM IR tersendiri dengan *mangled name* unik (contoh: `_ZN3foo3bar17h5d4e280287a12345E`).
4.  **Machine Code Generation**: LLVM mentransformasikan IR konkret menjadi instruksi assembly native mesin target.

---

### 7. Analogy
Bayangkan sebuah **Pabrik Komponen Presisi**:

*   **Generics & Monomorphization (Static Dispatch)**: Seperti memiliki cetakan injeksi (*die-cast mold*) universal. Jika Anda memesan 1.000 mur berbahan **Baja**, pabrik mencetak 1.000 mur baja murni. Jika Anda memesan 1.000 mur berbahan **Kuningan**, pabrik mencetak mur kuningan murni. Masing-masing mur memiliki integritas struktural maksimum, pas sempurna pada bautnya tanpa celah, dan tidak membutuhkan adaptor tambahan. Namun, pabrik harus menyimpan dua cetakan fisik berbeda di gudang (*binary size bertambah*).
*   **Dynamic Dispatch (`dyn Trait`)**: Seperti mur berukuran fleksibel dengan mekanisme gerigi adaptif (*universal wrench/adjustable socket*). Anda hanya membawa satu perkakas di saku (*binary size kecil*), namun setiap kali memutar baut, perkakas tersebut memiliki kelonggaran mekanis, membuang torsi, dan beroperasi jauh lebih lambat daripada kunci pas berukuran pas (*runtime indirect call overhead*).

---

### 8. Diagram
Arsitektur Monomorphization vs Dynamic Trait Object di Memory:

```
=== MONOMORPHIZATION (Static Dispatch - Inlined / Direct) ===

Source:
fn process<T: Codec>(item: T) { item.encode(); }
process(PacketA);
process(PacketB);

Memory Layout (.text segment):
┌────────────────────────────────────────────────────────┐
│ symbol: process_PacketA                                │
│ Instructions: Direct call/Inlined PacketA::encode()     │
├────────────────────────────────────────────────────────┤
│ symbol: process_PacketB                                │
│ Instructions: Direct call/Inlined PacketB::encode()     │
└────────────────────────────────────────────────────────┘
Invocation:
CPU ──[ Direct Jump: 0x00401000 ]──► process_PacketA (No latency penalty)


=== DYNAMIC DISPATCH (Trait Object Fat Pointer) ===

Source:
fn process(item: &dyn Codec) { item.encode(); }

Memory Layout:
Stack Fat Pointer:               Heap / Static Memory:
┌─────────────────────┐          ┌───────────────────────┐
│ *data pointer       ├─────────►│ Instance Concrete Data│
├─────────────────────┤          └───────────────────────┘
│ *vtable pointer     ├─────┐
└─────────────────────┘     │    vtable (.rodata):
                            │    ┌───────────────────────┐
                            └───►│ size: 24, align: 8    │
                                 ├───────────────────────┤
                                 │ fn ptr: encode() ─────┼──┐
                                 └───────────────────────┘  │
Invocation:                                                 ▼
CPU ──[ Dereference vtable ]──► [ Indirect Jump ] ──► Concrete Code
(Branch misprediction risk + Inlining prohibited)
```

---

### 9. Simple Example
Penggunaan Generic Function dasar dengan *Trait Bounds* dan *Where Clause*.

```rust
use std::fmt::Display;

// Trait kustom untuk mendefinisikan kapabilitas kalkulasi metrik
pub trait Measurable {
    fn weight(&self) -> f64;
}

// Struct konkret
pub struct SensorData {
    pub value: f64,
}

impl Measurable for SensorData {
    fn weight(&self) -> f64 {
        self.value * 0.05
    }
}

// Fungsi Generic dengan multiple bounds via 'where' clause
pub fn evaluate_and_log<T>(item: &T, threshold: f64) -> bool
where
    T: Measurable + Display,
{
    // Static dispatch ke Display::fmt
    println!("Evaluating sensor payload: {}", item);

    // Static dispatch ke Measurable::weight
    item.weight() > threshold
}

impl Display for SensorData {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "SensorData(value: {:.2})", self.value)
    }
}

fn main() {
    let sensor = SensorData { value: 42.5 };
    let is_critical = evaluate_and_log(&sensor, 1.0);
    println!("Exceeds threshold: {}", is_critical);
}
```

---

### 10. Practical Example
Implementasi pipeline serialisasi dan transmisi data berkinerja tinggi (*Zero-Allocation In-Memory Processing Frame*) menggunakan associated types, generic bounds, dan teknik *Monomorphization Thinning*.

```rust
use std::io::{self, Write};

/// Trait protokol komunikasi zero-copy
pub trait ProtocolPacket {
    type Payload: AsRef<[u8]>;
    type Header;

    fn header(&self) -> &Self::Header;
    fn payload(&self) -> &Self::Payload;
    fn packet_id(&self) -> u16;
}

/// Trait untuk backend serialisasi biner
pub trait Serializer<P>
where
    P: ProtocolPacket,
{
    type Error: std::error::Error + Send + Sync + 'static;
    fn serialize<W: Write>(&self, packet: &P, writer: &mut W) -> Result<usize, Self::Error>;
}

// Concrete Packet Definition
#[derive(Debug)]
pub struct TelemetryHeader {
    pub timestamp: u64,
    pub source_id: u32,
}

pub struct TelemetryPacket {
    pub header: TelemetryHeader,
    pub payload_buffer: Vec<u8>,
}

impl ProtocolPacket for TelemetryPacket {
    type Payload = Vec<u8>;
    type Header = TelemetryHeader;

    #[inline(always)]
    fn header(&self) -> &Self::Header {
        &self.header
    }

    #[inline(always)]
    fn payload(&self) -> &Self::Payload {
        &self.payload_buffer
    }

    #[inline(always)]
    fn packet_id(&self) -> u16 {
        0x0F01
    }
}

// Production Engine: Menggunakan generic bound dengan Monomorphization Thinning
pub struct NetworkIngestEngine<S> {
    serializer: S,
}

impl<S> NetworkIngestEngine<S> {
    pub fn new(serializer: S) -> Self {
        Self { serializer }
    }

    /// Outer generic method: Bertanggung jawab atas interface type-safe & inlining
    pub fn process_and_send<P, W>(&self, packet: &P, writer: &mut W) -> io::Result<usize>
    where
        P: ProtocolPacket,
        S: Serializer<P>,
        W: Write,
    {
        let mut temp_buffer = Vec::with_capacity(512);

        // Serialization step via static dispatch
        self.serializer
            .serialize(packet, &mut temp_buffer)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;

        // Monomorphization Thinning: delegasikan operasi I/O berat ke non-generic inner function
        // untuk mencegah duplikasi kode I/O di segmen binary .text
        Self::write_raw_frame(writer, packet.packet_id(), &temp_buffer)
    }

    /// Inner non-generic function: LLVM hanya mengompilasi kode ini SATU KALI.
    fn write_raw_frame(writer: &mut dyn Write, packet_id: u16, data: &[u8]) -> io::Result<usize> {
        let id_bytes = packet_id.to_be_bytes();
        let len_bytes = (data.len() as u32).to_be_bytes();

        let mut total_bytes = 0;
        total_bytes += writer.write(&id_bytes)?;
        total_bytes += writer.write(&len_bytes)?;
        total_bytes += writer.write(data)?;
        writer.flush()?;

        Ok(total_bytes)
    }
}

// Serializer konkret
pub struct RawTelemetrySerializer;

impl Serializer<TelemetryPacket> for RawTelemetrySerializer {
    type Error = io::Error;

    fn serialize<W: Write>(&self, packet: &TelemetryPacket, writer: &mut W) -> Result<usize, Self::Error> {
        let ts_bytes = packet.header().timestamp.to_be_bytes();
        let src_bytes = packet.header().source_id.to_be_bytes();
        
        writer.write_all(&ts_bytes)?;
        writer.write_all(&src_bytes)?;
        writer.write_all(packet.payload().as_ref())?;
        
        Ok(8 + 4 + packet.payload().as_ref().len())
    }
}

fn main() -> io::Result<()> {
    let packet = TelemetryPacket {
        header: TelemetryHeader {
            timestamp: 1700000000,
            source_id: 101,
        },
        payload_buffer: vec![0xDE, 0xAD, 0xBE, 0xEF],
    };

    let serializer = RawTelemetrySerializer;
    let engine = NetworkIngestEngine::new(serializer);

    let mut stdout_sink = io::stdout();
    let bytes_written = engine.process_and_send(&packet, &mut stdout_sink)?;

    eprintln!("\nSuccess: Transmitted {} wire bytes.", bytes_written);
    Ok(())
}
```

---

### 11. Real World Example
**Studi Kasus: Toko Mesin Query Database Kolumnar (Mirip Arsitektur Polars & Apache Arrow DataFusion)**

Pada engine database analitikal modern, jutaan baris data diproses per detik. Penggunaan dynamic dispatch pada loop pemrosesan batch (*vectorized query evaluation*) akan merusak throughput akibat vtable indirection overhead pada setiap kalkulasi sel.

```rust
// Arsitektur Polimorfisme Statis pada Vectorized Compute Kernel
pub trait ArrowPrimitiveType {
    type Native: Copy + std8::ops::Add<Output = Self::Native> + Send + Sync;
}

pub struct Int32Type;
impl ArrowPrimitiveType for Int32Type {
    type Native = i32;
}

pub struct Float32Type;
impl ArrowPrimitiveType for Float32Type {
    type Native = f32;
}

pub struct PrimitiveArray<T: ArrowPrimitiveType> {
    values: Vec<T::Native>,
}

impl<T: ArrowPrimitiveType> PrimitiveArray<T> {
    pub fn new(values: Vec<T::Native>) -> Self {
        Self { values }
    }

    /// SIMD-friendly vectorized kernel melalui static dispatch murni
    pub fn vector_add(&self, rhs: &Self) -> Self {
        assert_eq!(self.values.len(), rhs.values.len());
        
        // Kompiler Rust dan LLVM dapat langsung melihat loop operasi tipe primitif konkret.
        // Hasil kompilasi: Instruksi AVX-512 / AVX2 (vaddps atau vpaddd) tanpa runtime branching.
        let result: Vec<T::Native> = self.values
            .iter()
            .zip(rhs.values.iter())
            .map(|(&a, &b)| a + b)
            .collect();

        PrimitiveArray::new(result)
    }
}
```
**Dampak Arsitektural di Skala Industri:**
Jika `vector_add` ditulis dengan `Box<dyn Datum>`, CPU harus menyelesaikan pointer deference per elemen, menonaktifkan kemampuan *auto-vectorization* (AVX2/AVX-512) LLVM. Dengan generics, performa pemrosesan meningkat **8x hingga 15x lipat**, mencapai batas *memory-bandwidth saturation*.

---

### 12. Trade-offs
Memilih Generics (Static Dispatch via Monomorphization) vs Trait Objects (Dynamic Dispatch):

| Parameter | Generics (Monomorphization) | Trait Objects (`dyn Trait`) |
| :--- | :--- | :--- |
| **Execution Speed** | Maksimal (Inlined, Zero Branch Delay, SIMD enabled) | Terbuka overhead indirect call (~1.5–3x lebih lambat pada tight loops) |
| **Memory Allocation**| Flat layout pada stack/heap (Zero fat-pointer overhead) | Fat pointer (Pointer data + pointer vtable = 16 bytes di arch 64-bit) |
| **Binary Size** | **Negatif**: Mengalami *Code Bloat* jika diinstansiasi dengan banyak tipe | **Positif**: Ukuran biner konstan, hanya ada satu salinan implementasi kode |
| **I-Cache Performance**| Berisiko *Instruction Cache Eviction* jika biner membengkak | Ramah I-Cache (menggunakan kembali segmen instruksi yang sama) |
| **Compilation Time** | Lama (LLVM harus mengoptimasi setiap variasi tipe konkret) | Cepat (LLVM hanya memproses satu fungsi abstract interface) |
| **Heterogeneous Coll**| Tidak memungkinkan koleksi heterogen langsung (`Vec<T>` homogen) | Mengizinkan koleksi heterogen secara alami (`Vec<Box<dyn Trait>>`) |

---

### 13. When To Use
*   Gunakan generics pada **Hot Paths**, komputasi intensif, inner-loops, dan layer abstraksi I/O throughput tinggi di mana latensi bernilai mikrodetik/nanodetik.
*   Gunakan saat merancang **Core Libraries** atau utility data structures (seperti `Option<T>`, `Result<T, E>`, collections) yang harus beroperasi transparan pada tipe pemanggil.
*   Gunakan saat compiler perlu mengetahui ukuran konkret tipe data pada compile-time (`Sized`) untuk alokasi memori stack.

---

### 14. When NOT To Use
*   Jangan gunakan jika Anda membutuhkan **Heterogeneous Collections**. Contoh: Sebuah container UI rendering engine yang menyimpan daftar tombol, teks, dan canvas (`Vec<Box<dyn Widget>>`). Menggunakan generic murni akan memaksa container menjadi homogen (`Vec<Button>`).
*   Hindari generic tak terbatas pada sistem **Embedded Ultra-Constrained** (Flash ROM < 64KB). Monomorphization masif dapat melebihi kapasitas memori instruksi hardware mikroprosesor.
*   Hindari pada layer **Public API Boundary / Dynamic Plugin Loading** di mana tipe ditentukan saat runtime via shared library (`.so` / `.dll`).

---

### 15. Common Mistakes

#### 1. Leaking Monomorphization Overhead (Generic Code Bloat)
Membungkus seluruh blok fungsi masif ke dalam parameter generic, padahal hanya satu operasi kecil yang bergantung pada `T`.
```rust
// BURUK: Seluruh 200 baris kode logging, network setup, & error handling 
// diduplikasi LLVM untuk setiap tipe T.
fn handle_request<T: Serialize>(data: T) {
    // 200 lines of complex boilerplate socket initialization...
    let serialized = data.serialize();
    // 100 lines of metrics telemetry...
}
```

#### 2. Over-constraining Trait Bounds
Mendefinisikan bound yang tidak dibutuhkan pada level `struct`, alih-alih meletakkannya pada blok `impl`.
```rust
// BURUK: Membatasi struct deklarasi memicu cascading bound requirements di seluruh codebase
struct Container<T: Clone + Send + Sync + std::fmt::Debug> {
    inner: T,
}

// BAIK: Biarkan struct sefleksibel mungkin, berikan bounds hanya pada impl yang relevan
struct Container<T> {
    inner: T,
}

impl<T: std::fmt::Debug> Container<T> {
    fn dump_state(&self) {
        println!("{:?}", self.inner);
    }
}
```

#### 3. Mengabaikan Sized Bound Implicit
Secara default, seluruh generic parameter di Rust memiliki bound implisit `T: Sized`. Jika parameter Anda dilewatkan via referensi dan dapat bekerja dengan tipe dinamis seperti `str` atau `[u8]`, tidak melonggarkan bound adalah sebuah kesalahan.
```rust
// Pembatasan implisit: T: Sized
fn process_buffer<T: ?Sized + AsRef<[u8]>>(buf: &T) {
    let bytes = buf.as_ref();
    // Dapat menerima &[u8], String, str, Vec<u8> tanpa alokasi baru
}
```

---

### 16. Best Practices (Production Checklist)
*   [ ] **Gunakan `where` clause** untuk signature fungsi dengan lebih dari satu trait bound demi keterbacaan kode (*code readability*).
*   [ ] **Terapkan Monomorphization Thinning**: Pisahkan logika *type-agnostic* ke dalam *non-generic private inner functions* (terutama untuk fungsi berukuran besar).
*   [ ] **Audit binary bloat** pada pipeline CI menggunakan tool `cargo-bloat` atau `cargo-llvm-lines`.
*   [ ] **Pilih Associated Types** jika relasi trait dengan tipe pendukung bersifat 1-ke-1 (misal `Iterator::Item`). Gunakan Generic Trait Parameters (`Trait<T>`) hanya jika suatu tipe perlu mengimplementasikan trait yang sama berkali-kali untuk target berbeda (misal `From<u32>` dan `From<u64>`).
*   [ ] Tambahkan compiler attribute `#[inline]` secara bijak pada generic functions kecil; hindari pemberian inline pada generic functions masif untuk melindungi L1 I-cache.

---

### 17. Troubleshooting

#### Masalah 1: Rust Compiler Error `E0277` (Trait bound not satisfied)
```text
error[E0277]: the trait bound `CustomType: Clone` is not satisfied
  --> src/main.rs:12:15
   |
12 |     let x = duplicate(&item);
   |             ^^^^^^^^^ the trait `Clone` is not implemented for `CustomType`
```
*Akar Masalah:* Tipe konkret yang dipassing ke generic function tidak mengimplementasikan trait yang disyaratkan oleh signature fungsi.
*Solusi:* Derive trait jika memungkinkan (`#[derive(Clone)]`) atau implementasikan trait secara eksplisit untuk `CustomType`.

#### Masalah 2: Binary Bloat Tak Terkendali (Code footprint membengkak ratusan megabyte)
*Akar Masalah:* Sebuah fungsi generic diinstansiasi dengan ratusan kombinasi tipe unik di seluruh sistem, dan seluruh fungsionalitasnya di-inline secara agresif.
*Diagnosa via CLI:*
```bash
cargo install cargo-llvm-lines
cargo llvm-lines --release
```
Output akan menunjukkan fungsi generic mana yang menghasilkan salinan baris instruksi LLVM IR terbanyak.
*Solusi:* Lakukan refactoring ke arah *Dynamic Dispatch* (`&dyn Trait`) pada layer non-critical path, atau isolasi cabang logika non-generic menggunakan pointer slicing (`&[u8]`).

---

### 18. Exercise
**Instruksi Pengerjaan:**
Rancang sebuah struktur data generic bernama `RingBuffer<T, const CAP: usize>` (menggunakan Const Generics dan Trait Bounds).
1.  Struktur data harus menyimpan buffer statis array `[Option<T>; CAP]` tanpa alokasi heap (`Vec`).
2.  Implementasikan method `push(&mut self, item: T) -> Option<T>` yang mengembalikan data terlama jika buffer penuh (*overwrite old elements*).
3.  Implementasikan method generic `drain_into<W>(&mut self, writer: &mut W) -> Result<usize, std::io::Error>` yang hanya aktif jika `T: AsRef<[u8]>` dan `W: std::io::Write`.

---

### 19. Challenge
**Tugas Arsitektural Tingkat Lanjut:**
Buat sebuah **Zero-Cost Serialization Dispatch Engine** yang memenuhi kondisi berikut:
1.  Definisikan trait `ComponentStore` dengan associated type `EntityId` dan generic iterator access.
2.  Implementasikan strategi hybrid: Evaluasi hot-path pemrosesan entity menggunakan full-monomorphized generics, tetapi simpan koleksi sub-engines di dalam top-level orchestrator menggunakan heterogen vector (`Vec<Box<dyn SystemDispatch>>`).
3.  Buktikan efektivitas monomorphization dengan memeriksa representasi assembly LLVM menggunakan `cargo asm` (atau Compiler Explorer/Godbolt): Tunjukkan bahwa loop utama pada implementasi konkret tidak memuat satu pun instruksi dereferensi vtable (`call *%reg`), melainkan direct call berurutan atau instruksi register ter-vectorize.

---

### 20. Summary
*   Generics di Rust beroperasi di bawah prinsip **Zero-Cost Abstractions** melalui mekanisme kompilasi **Monomorphization**.
*   Monomorphization mengonversi abstraksi tipe generic menjadi kode mesin spesifik pada LLVM IR, menghasilkan performa eksekusi setara kode tangan C, memungkinkan inlining, dan mendukung SIMD auto-vectorization.
*   Kelemahan esensial monomorphization adalah **Code Bloat** dan penambahan waktu kompilasi (*LLVM compilation latency*), serta risiko degradasi *Instruction Cache* jika fungsi generic berukuran besar diinstansiasi secara berlebihan.
*   Rekayasa Rust standar industri menerapkan **Monomorphization Thinning**: Menjaga outer API tetap generic dan type-safe, seraya mendelegasikan payload komputasi berat non-generic ke fungsi privat berbasis pointers/slices (`&[u8]`, `&dyn Trait`) guna mengoptimalkan ruang biner.