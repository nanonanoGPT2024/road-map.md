# BAB 04: Quiz, Challenge, & Knowledge Check
**Penanganan Galat & Sistem I/O Idiomatik**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Alokasi & Kontrak Eksekusi Galat
Jelaskan perbedaan mendasar secara arsitektur eksekusi antara *recoverable error* menggunakan tipe `Result<T, E>` dengan *unrecoverable error* via `panic!`. Bedah bagaimana mekanisme *stack unwinding* bekerja saat `panic!` dipicu, implikasi performanya terhadap resource deallocation (RAII), serta kondisi spesifik apa yang memaksa runtime Rust melakukan fallback langsung ke operasi *abort* (`panic = "abort"`).

### Soal 1.2: Desugaring Operator `?` dan Trait `From`
Operator `?` bukan sekadar *syntactic sugar* untuk ekspresi `match`. Uraikan proses *desugaring* formal dari operator `?` ketika dievaluasi oleh *compiler* Rust (merujuk pada trait `std::ops::Try` dan `std::convert::From`). Bagaimana mekanisme konversi tipe error secara implisit terjadi tanpa memerlukan explicit mapping manual dari pemanggil fungsi?

### Soal 1.3: Abstraksi Buffer I/O vs Direct Syscalls
Mengapa operasi I/O berulang langsung melalui struct `std::fs::File` (yang mengimplementasikan `Read` dan `Write`) tanpa pembungkus buffer memicu degradasi performa sistem operasi secara masif? Analisis perbedaan alur kerja instruksi CPU dan interaksi kernel (*context switch*, `read(2)` / `write(2)` *system calls*) antara unbuffered I/O dengan buffered I/O via `BufReader<R>` dan `BufWriter<W>`.

### Soal 1.4: Arsitektur Ekosistem Galat: `thiserror` vs `anyhow`
Dalam perancangan perangkat lunak Rust idiomatik berstandar *enterprise*, terdapat pemisahan tegas antara penanganan error pada level *Library* dan level *Application*. Jelaskan secara mendalam:
1. Mengapa pustaka publik (*crates*) diwajibkan menggunakan concrete error types berbasis `enum` dengan derivasi `thiserror` (atau implementasi manual `std::error::Error`)?
2. Mengapa aplikasi akhir (*binary crates*) lebih direkomendasikan mengadopsi dynamic error reporting seperti `anyhow::Result<T>`?
3. Apa bahaya arsitektural jika sebuah *library crate* mengekspos tipe error dynamic trait object seperti `Box<dyn std::error::Error>` kepada downstream consumer-nya?

### Soal 1.5: Integritas Jalur Berkas: `Path`, `PathBuf`, dan Representasi Non-UTF-8
Sistem berkas modern (POSIX vs Windows) memiliki representasi byte array yang berbeda untuk nama berkas dan direktori. Mengapa Rust secara eksplisit memisahkan `std::path::Path` / `PathBuf` dari tipe `&str` / `String`? Jelaskan relasi internal antara `Path`/`PathBuf` dengan `std::ffi::OsStr`/`OsString`, serta apa konsekuensi keamanannya jika Anda mengasumsikan seluruh path di sistem operasi adalah UTF-8 valid.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Memory Layout & Niche Value Optimization pada `Result<T, E>`
Pertimbangkan tipe data `Result<(), std::io::Error>` dan `Result<std::num::NonZeroUsize, ()>`.
Jelaskan bagaimana Rust compiler mengoptimalkan ukuran memori (*layout*) kedua tipe tersebut melalui mekanisme *Niche Value Optimization* (atau *Null Pointer Optimization*). Mengapa `size_of::<Option<Box<T>>>()` setara dengan `size_of::<Box<T>>()`, dan bagaimana prinsip yang sama berlaku pada `Result<T, E>` jika salah satu tipe memiliki nilai diskriminan kosong/invalid?

### Soal 2.2: Semantik Crash Consistency: `BufWriter::flush` vs `File::sync_all`
Perhatikan potongan kode berikut:
```rust
use std::fs::File;
use std::io::{BufWriter, Write};

fn persist_critical_transaction(data: &[u8]) -> std::io::Result<()> {
    let file = File::create("/var/data/ledger.wal")?;
    let mut writer = BufWriter::new(file);
    writer.write_all(data)?;
    writer.flush()?;
    Ok(())
}
```
Jika mesin host mengalami *power-loss* mendadak 1 milidetik setelah fungsi di atas mengembalikan `Ok(())`, jelaskan secara teknis mengapa data transaksi tersebut berkemungkinan besar hilang atau rusak (*zeroed/corrupted*). Apa perbedaan mutlak antara mentransfer byte dari Rust userspace buffer ke kernel buffer (`flush`), dengan flushing dirty OS page cache ke non-volatile physical storage via `sync_all()` (`fsync(2)`) atau `sync_data()` (`fdatasync(2)`)?

### Soal 2.3: Interrupted System Calls (`EINTR`) dan Partial Writes
Dalam implementasi manual trait `Write`, jelaskan mengapa memanggil method `write(&[u8])` secara langsung pada objek I/O (seperti `TcpStream` atau `File`) tidak menjamin seluruh byte dalam irisan (*slice*) telah terkirim. Bagaimana penanganan error varian `std::io::ErrorKind::Interrupted` dan return value `Ok(n)` di mana `n < slice.len()` harus diorkestrasi secara idiomatik? Mengapa `write_all` adalah solusi standar, dan apa yang terjadi jika terjadi error di tengah-tengah eksekusi `write_all`?

### Soal 2.4: Dynamic Downcasting dan Error Source Chaining
Diberikan dynamic trait object `Box<dyn std::error::Error + 'static>`. Jelaskan mekanisme kerja method `Error::source(&self)` untuk menelusuri rantai kausalitas kegagalan (*error cause chain*). Bagaimana runtime Rust memanfaatkan *vtable* dan memory layout trait object untuk mengeksekusi method `downcast_ref::<TargetError>()` secara aman tanpa menimbulkan *undefined behavior* saat tipe konkret underlying tidak cocok?

### Soal 2.5: Deadlock dan Silent Failures pada Drop Trait `BufWriter`
Ketika sebuah instance `BufWriter<W>` keluar dari scope (*out of scope*), implementasi `Drop`-nya akan berusaha memanggil `flush()` secara implisit. 
1. Apa yang terjadi pada error I/O yang muncul selama pemanggilan `flush()` di dalam trait `Drop` tersebut? 
2. Mengapa silent failure ini terjadi, dan pola arsitektur apa yang wajib diimplementasikan pemrogram untuk menangkap galat penulisan buffer sebelum dekonstruksi terjadi (analisis penggunaan `into_inner()`)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck dan File Descriptor Exhaustion pada High-Throughput Log Aggregator
Sebuah mikroservis log ingestor yang ditulis dalam Rust memproses streaming log dari Apache Kafka dan menulisnya ke disk lokal ke dalam berkas log per-tenant (`/data/{tenant_id}/current.log`). Pada traffic puncak (150.000 log/detik untuk 10.000 tenant aktif), sistem mengalami lonjakan latensi p99 dari 2ms ke 4.500ms, CPU usage anjlok hingga 8% (menandakan I/O wait tinggi), dan sistem operasi mulai melemparkan panic:
`Os { code: 24, kind: Uncategorized, message: "Too many open files" }`.

Setelah audit kode, ditemukan fragmen berikut:
```rust
pub fn append_log(tenant_id: &str, payload: &[u8]) -> std::io::Result<()> {
    let path = format!("/data/{}/current.log", tenant_id);
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)?;
    file.write_all(payload)?;
    Ok(())
}
```

*   **Pertanyaan Diagnostik & Solusi:**
    1. Identifikasi 3 kelemahan fatal arsitektur I/O pada fungsi `append_log` di atas yang menyebabkan saturasi sistem call, degradasi performa I/O, dan penipisan *file descriptor* OS.
    2. Rancang arsitektur I/O pooling / caching idiomatik di Rust yang memadukan buffered write, batas maksimum deskriptor terbuka (menggunakan cache eviction policy), dan batch-flushing interval untuk menstabilkan pemrosesan log tersebut.

---

### Skenario B: Race Condition dan State Corruption pada Atomic File Rewrite
Aplikasi sistem terdistribusi menyimpan metadata konfigurasi penting pada berkas `/etc/cluster/node_state.json`. Ketika terjadi perubahan topologi cluster, fungsi berikut dipanggil untuk memperbarui konfigurasi:

```rust
pub fn update_state(new_state: &State) -> Result<(), Box<dyn std::error::Error>> {
    let path = "/etc/cluster/node_state.json";
    let serialized = serde_json::to_vec_pretty(new_state)?;
    
    // Tulis ulang berkas
    let mut file = std::fs::File::create(path)?; // Truncates existing file!
    file.write_all(&serialized)?;
    file.sync_all()?;
    Ok(())
}
```

Saat node mengalami lonjakan restat (*OOM-Killed* atau *host panic*) persis pada saat pembaruan state sedang berlangsung, sistem reboot dan gagal start dengan galat:
`EOF while parsing a value at line 1 column 0` (berkas kosong 0 byte) atau parsing corrupted partial JSON.

*   **Pertanyaan Diagnostik & Solusi:**
    1. Mengapa pemanggilan `File::create` yang mentruncate berkas secara langsung merupakan antipattern fatal untuk sistem *mission-critical*?
    2. Jelaskan langkah demi langkah pola perancangan **Atomic File Replacement** di POSIX systems menggunakan Rust (manfaatkan atomic rename via `rename(2)` / `std::fs::rename`).
    3. Mengapa direktori induk (`/etc/cluster/`) juga harus dibuka dan di-`sync_all()` setelah operasi rename berkas dilakukan? Apa dampaknya jika direktori induk tidak di-fsync saat crash sistem terjadi?

---

### Skenario C: Multi-Tier Storage Engine Library: Desain Domain Error Idiomatik
Anda memimpin perancangan pustaka *Embedded Key-Value Store* baru di Rust (`RustStore`). Pustaka ini memiliki tiga lapisan internal:
1. `DiskEngine`: Mengelola penulisan raw byte ke berkas via direct/buffered I/O.
2. `WalManager`: Mengelola siklus Write-Ahead Log, recovery parsing, dan CRC32 checksum.
3. `IndexTree`: Struktur data in-memory B-Tree yang mengelola pointer alamat log.

Konsumen pustaka Anda membutuhkan transparansi: mereka harus bisa mendeteksi secara programatis apakah sebuah error disebabkan oleh masalah hardware disk penuh (`NoSpaceLeft`), CRC corruption (mengharuskan recovery tool), data key tidak ditemukan (`KeyNotFound`), atau konkurensi terkunci (`LockContention`). Konsumen menolak keras digunakannya `anyhow` pada level library API.

*   **Pertanyaan Diagnostik & Solusi:**
    1. Rancang hierarki tipe galat Rust (`enum`) menggunakan crate `thiserror` yang memisahkan error internal tiap layer, namun menyatukannya pada sebuah enum root publik `RustStoreError`.
    2. Tunjukkan bagaimana Anda membungkus low-level `std::io::Error` ke dalam variant `RustStoreError::StorageFailure` tanpa kehilangan konteks pesan galat asli dan stack trace-nya (*error chaining*).
    3. Implementasikan pemetaan konversi otomatis (`From`) dari error subsystem ke root error, sambil mempertahankan kontrol eksplisit: error apa yang boleh diekspos ke publik dan detail implementasi apa yang harus disembunyikan (*information hiding*).

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Crash-Consistent, Checksummed Write-Ahead Log (WAL) Segment Rotator

#### Problem Statement
Dalam arsitektur basis data, Write-Ahead Log (WAL) adalah komponen absolut yang menjamin durability transaksi (ACID). Anda ditugaskan untuk mengimplementasikan sebuah modul mesin *WAL Segment Writer* berbasis Rust murni. Modul ini bertanggung jawab mencatat entri log biner secara terurut ke dalam berkas-berkas segmen disk dengan performa tinggi, proteksi terhadap silent data corruption (bit rot), dan jaminan atomisitas penulisan.

#### Requirements
1. **Definisi Record WAL**:
   Setiap record yang ditulis ke disk harus memiliki format biner berurutan (*framed layout*):
   * `Payload Length`: 4 byte (`u32`, Little-Endian).
   * `CRC32 Checksum`: 4 byte (`u32`, Little-Endian) dihitung dari data payload.
   * `Payload`: N byte (`&[u8]`).
2. **Buffer and Durability Modes**:
   Engine harus mendukung dua mode durabilitas:
   * `Durability::Buffered`: Menulis ke `BufWriter`, hanya melakukan `flush` ke OS tanpa explicit `sync_data`.
   * `Durability::ImmediateSync`: Menulis ke buffer, melakukan `flush`, lalu mengeksekusi `sync_data()` secara eksplisit pada underlying file descriptor.
3. **Automatic Log Rotation**:
   Segment file dinamai secara terurut: `wal_00000001.log`, `wal_00000002.log`, dst.
   Jika ukuran berkas aktif melampaui `max_segment_size` (misal 10MB) setelah sebuah record ditulis, berkas harus di-*flush*, di-*sync*, ditutup secara aman, dan berkas segmen baru diinisialisasi secara transparan.
4. **Resilient Reader / Integrity Check**:
   Implementasikan fungsi `WalReader` yang mampu membaca segment berkas dari awal hingga akhir, memvalidasi frame header, memeriksa CRC32 payload, dan mengembalikan iterator `Result<Vec<u8>, WalError>`. Jika reader mendeteksi partial write pada akhir berkas (misal crash sebelum payload selesai ditulis) atau CRC mismatch, reader harus mengembalikan tipe galat spesifik `WalError::CorruptedRecord` atau `WalError::IncompleteWrite`.
5. **No Panics Rule**:
   Dilarang keras menggunakan `.unwrap()`, `.expect()`, `panic!()`, atau indexing operator tidak aman (`slice[i]`) di dalam seluruh path eksekusi. Seluruh galat (I/O, checksum mismatch, segment rotation failure) wajib dikelola via custom enum `WalError` berbasis `thiserror`.

#### Constraints
* Tidak boleh menggunakan third-party WAL engine (harus dibangun di atas `std::fs`, `std::io`, dan trait standar Rust). Pustaka luar yang diizinkan hanya `crc32fast` untuk komputasi CRC dan `thiserror` untuk pembuatan error enum.
* Memory safe, zero UB (*undefined behavior*), tidak ada data loss untuk entri yang telah berhasil di-`ImmediateSync`.
* Error variant harus informatif, menyertakan metadata seperti byte offset lokasi korupsi saat pembacaan gagal.

#### Expected Output
Sebuah file crate Rust terstruktur (`lib.rs` dan unit integration tests) yang membuktikan keandalan engine:
```
wal_engine/
├── Cargo.toml
└── src/
    ├── error.rs     // Definisi WalError lengkap via thiserror
    ├── record.rs    // Serialisasi/deserialisasi Frame Header & CRC
    ├── segment.rs   // Logika rotasi berkas, management BufWriter, dan synchronization
    └── reader.rs    // Streaming iterator parser dengan integritas data verification
```
Test suite harus menyimulasikan:
1. Penulisan 50.000 record dengan random payload size memicu rotasi otomatis segmen secara mulus.
2. Injeksi bit-flip manual pada tengah-tengah file segmen log, dan memverifikasi reader mengembalikan `WalError::CorruptedRecord` persis pada record dan byte offset yang rusak.
3. Simulasi *truncated record* (hanya separuh byte tertulis di akhir file), memastikan reader melaporkan `WalError::IncompleteWrite` dan tidak mengalami crash (*panic*).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan semantik, alokasi heap, dan memory safety antara stack unwinding (`panic = "unwind"`) dan proses aborting (`panic = "abort"`).
- [ ] Desugaring operator `?` melalui trait `std::ops::Try` dan mekanisme konversi tipe galat otomatis melalui trait `std::convert::From`.
- [ ] Mengapa Rust mengadopsi explicit error handling via `Result<T, E>` dibandingkan exception-based model (C++/Java) dalam hal branch prediction, overhead performa, dan determinisme alur kendali.
- [ ] Konsekuensi operasional I/O system calls (`read(2)`, `write(2)`, `fsync(2)`, `fdatasync(2)`) dan biaya performa context switches antara userspace dan kernelspace.
- [ ] Peran `BufReader<R>` dan `BufWriter<W>` dalam memitigasi overhead syscalls serta bahaya *silent error drops* pada saat dekonstruksi instance `BufWriter`.
- [ ] Anatomi memory layout `Result<T, E>` dan pemanfaatan *Niche Value Optimization* untuk menekan alokasi memory padding diskriminan enum.
- [ ] Perbedaan implementasi abstraksi OS path: `Path`/`PathBuf` vs `OsStr`/`OsString` vs standard UTF-8 `str`/`String`.
- [ ] Pola partisi error sistem: penggunaan concrete error enums (`thiserror`) pada domain libraries versus dynamic polymorphic error reporting (`anyhow`) pada domain aplikasi/biner.
- [ ] Prinsip *Crash Consistency* pada penulisan berkas: mengapa `BufWriter::flush()` tidak menjamin durabilitas fisik pada media disk storage saat power-failure mendadak.
- [ ] Pola atomisitas manipulasi berkas (Atomic Write-and-Rename Pattern) dan kewajiban sinkronisasi metadata direktori induk via `fsync`.

### Saya tidak perlu menghafal:
- [ ] Kode numerik integer errno OS spesifik (misal: `libc::ENOENT = 2`, `libc::EACCES = 13`); gunakan abstraksi `std::io::ErrorKind`.
- [ ] Algoritma internal tabel lookup CRC32 bitwise polynomial; gunakan crate teruji seperti `crc32fast`.
- [ ] Spesifikasi byte layout implementasi proprietary filesystem tertentu (seperti ext4 inode layout, NTFS MFT internals, atau APFS b-trees).
- [ ] Sintaks macro expansion tingkat rendah dari procedural macro derive `thiserror::Error`.

### Saya harus bisa melakukan:
- [ ] Merancang dan menyusun hierarki tipe galat berbasis `enum` modular multi-layer menggunakan `thiserror` tanpa mengekspos internal dependencies.
- [ ] Mengonstruksi pipeline parsing dynamic error di application-level menggunakan `anyhow::Context` untuk menyematkan context diagnostics informatif tanpa kehilangan source error.
- [ ] Mengimplementasikan pembacaan dan penulisan berkas biner performa tinggi menggunakan buffer I/O (`BufReader`, `BufWriter`) yang crash-safe dan bebas dari *memory leaks*.
- [ ] Menangani galat non-blocking dan partial I/O (`ErrorKind::Interrupted`, `ErrorKind::WouldBlock`) secara elegan tanpa infinite-busy loops.
- [ ] Menulis algoritma modifikasi berkas atomic menggunakan *temporary file swap* (`std::fs::rename`) yang menjamin non-corruption state saat terjadi power-loss atau software crash.
- [ ] Melakukan downcasting dinamis runtime dari generic dynamic trait object error (`Box<dyn std::error::Error>`) ke concrete error type untuk eksekusi alur pemulihan (*error recovery flow*).