## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** FDE-ARC-0601
* **Nama Modul:** Rapid Prototyping & Bespoke Solution Engineering: Membangun Modul Kustom Berkecepatan Tinggi, FFI Bindings, Plugin Architectures, Upstream-First Philosophy
* **Kategori:** 06-Architecture-and-System-Design
* **Tingkat Kesulitan:** Advanced / Senior Level
* **Prasyarat:** 
  * Kemahiran dalam minimal satu bahasa *systems programming* (Rust, C++, atau Go).
  * Pemahaman mendalam tentang tata kelola memori sistem operasi (*virtual memory*, *stack*, *heap*, *paging*).
  * Familiaritas dengan konsep *Application Binary Interface* (ABI) dan *Application Programming Interface* (API).
  * Pemahaman *Distributed Version Control System* (Git branching, rebasing, submodule/subtree workflows).
* **Durasi Estimasi:** 12 Jam Pembelajaran (6 Jam Teori & Arsitektur, 6 Jam Praktikum & Debugging Sistem Tingkat Rendah).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, *Forward Deployed Engineer* (FDE) diharapkan mampu:

1. **Merancang dan Mengimplementasikan Solusi Bespoke dengan Presisi:** Mampu membangun ekstensi perangkat lunak kustom yang menjawab kebutuhan operasional klien dalam hitungan hari tanpa mengorbankan integritas arsitektur produk inti.
2. **Menguasai Foreign Function Interface (FFI) & Cross-Language Interoperability:** Mengonstruksi integrasi biner lintas bahasa (misal: Rust ke Go/Python, C++ ke Node.js) secara aman tanpa memicu *undefined behavior*, kebocoran memori (*memory leak*), atau *panic unwinding* lintas *boundary*.
3. **Membangun Arsitektur Plugin Terisolasi & Berperforma Tinggi:** Mengevaluasi dan mengimplementasikan mekanisme plugin berbasis *Dynamic Shared Libraries* (`dlopen`), IPC/gRPC (HashiCorp `go-plugin`), dan WebAssembly (Wasm/WASI) untuk isolasi kegagalan (*fault domain isolation*).
4. **Mengeksekusi Filosofi Upstream-First secara Konsisten:** Menerapkan strategi rekayasa balik (*reverse-engineering hook points*) dan abstraksi konfigurasi agar kode kustom dapat diintegrasikan kembali ke repositori inti (*upstream core*) tanpa menciptakan cabang kode yang terfragmentasi (*unmergeable forks*).
5. **Mengelola Garansi ABI dan Serialisasi Memori Lintas Runtime:** Menjamin stabilitas *Application Binary Interface* (ABI) menggunakan representasi `#[repr(C)]`, *memory layout alignment*, dan pembebasan memori deterministik menggunakan *custom allocators*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                          [Kebutuhan Klien Spesifik / Edge Cases]
                                             │
                                             ▼
                 ┌────────────────────────────────────────────────────────┐
                 │ Rapid Prototyping & Bespoke Solution Engineering (FDE) │
                 └───────────────────────────┬────────────────────────────┘
                                             │
     ┌───────────────────────────────────────┼────────────────────────────────────────┐
     ▼                                       ▼                                        ▼
┌─────────────────────────┐     ┌─────────────────────────┐             ┌─────────────────────────┐
│       FFI BINDINGS      │     │   PLUGIN ARCHITECTURES  │             │  UPSTREAM-FIRST DESIGN  │
└────────────┬────────────┘     └────────────┬────────────┘             └────────────┬────────────┘
             │                               │                                       │
  ┌──────────┴──────────┐         ┌──────────┴──────────┐                 ┌──────────┴──────────┐
  │ • C ABI Exposure    │         │ • Shared Libs (.so) │                 │ • Hook Injection    │
  │ • Zero-Copy Buffers │         │ • IPC / HashiCorp   │                 │ • Generic Abstraction│
  │ • Memory Ownership  │         │ • WebAssembly (WASI)│                 │ • Anti-Fork Branch  │
  │ • Panic Boundaries  │         │ • Sandbox Isolation │                 │ • Patch Lifecycle   │
  └─────────────────────┘         └─────────────────────┘                 └─────────────────────┘
             │                               │                                       │
             └───────────────────────────────┼───────────────────────────────────────┘
                                             ▼
                               ┌───────────────────────────┐
                               │ Production-Grade Runtime  │
                               │  (Performant, Stable,     │
                               │   Maintainable Bespoke)   │
                               └───────────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sebagai *Forward Deployed Engineer* (FDE), Anda ditempatkan tepat di garis batas antara produk inti perusahaan (*core product*) dan ekosistem enterprise klien yang sarat dengan sistem legasi, protokol proprietary, regulasi keamanan yang ketat, serta volume data ekstrem. 

1. **Jarak Antara Roadmap Produk dan Kenyataan Lapangan:** Tim produk inti bekerja dalam sprint berbasis triwulan untuk membangun fitur yang melayani pasar umum. Namun, klien enterprise bernilai jutaan dolar sering kali membutuhkan parser biner kustom untuk mainframe IBM, integrasi enkripsi khusus perangkat keras (HSM), atau logika inferensi latensi rendah yang harus aktif dalam hitungan minggu.
2. **Biaya Forking yang Mematikan (Fork Debt):** Jalan pintas yang paling sering diambil oleh insinyur amatir adalah menduplikasi repositori inti (*forking*), menyuntikkan logika kustom klien, dan mendeploy salinan tersebut. Dalam tempo enam bulan, *fork* tersebut kehilangan kompatibilitas dengan rilis *upstream*. Pembaruan keamanan (*security patches*) tidak dapat diterapkan, dan beban pemeliharaan teknis (*maintenance overhead*) meledak.
3. **Kompromi Performa dan Bahasa Pemrograman:** Platform enterprise mungkin ditulis dalam Go demi produktivitas jaringan atau Python untuk sains data, tetapi operasi kustom klien menuntut komputasi matematis/kriptografi berkinerja tinggi yang hanya bisa ditangani oleh Rust atau C++. FFI dan Plugin System adalah satu-satunya jembatan yang memungkinkan *throughput* jutaan *events per second* (eps) tanpa harus merombak ulang arsitektur produk host.

---

## SEKSI 05 — APA ITU (WHAT)

### Bespoke Solution Engineering
*Bespoke Solution Engineering* adalah metodologi rekayasa sistem yang memproduksi modul perangkat lunak yang disesuaikan secara unik untuk kebutuhan operasional spesifik sebuah entitas (klien/mitra), dirancang dengan standar kualitas, performa, dan observabilitas kelas produksi, namun dibungkus dalam batas-batas modularitas yang ketat agar tidak mencemari basis kode umum (*core codebase*).

### Foreign Function Interface (FFI)
FFI adalah mekanisme komputasi tingkat rendah di mana program yang ditulis dalam satu bahasa pemrograman dapat memanggil rutin atau fungsi yang dikompilasi dalam bahasa pemrograman lain. FFI beroperasi pada tingkat ABI (Application Binary Interface), umumnya menggunakan konvensi pemanggilan C (C Calling Convention / `cdecl` atau `System V AMD64 ABI`).

### Plugin Architecture
Pola arsitektur perangkat lunak yang memisahkan fungsionalitas inti (*host*) dari fungsionalitas ekstensi (*guest/plugin*). Mekanisme komunikasi antar-keduanya dapat dilakukan melalui:
* **Dynamic Linking (`dlopen`/`LoadLibrary`):** Memori bersama (*in-process shared memory*), latensi mendekati nol nanodetik, namun risiko *crash* plugin meruntuhkan seluruh proses *host*.
* **Inter-Process Communication (IPC):** Plugin berjalan pada proses terpisah via gRPC/Unix Domain Sockets. Menjamin isolasi penuh (*fault tolerance*), dengan biaya penalti serialisasi/deserialisasi dan *context-switching*.
* **WebAssembly (WASM/WASI):** Eksekusi kode biner terkompilasi di dalam *sandbox runtime in-process* (misal: Wasmtime, Wasmer). Memberikan keamanan memori tingkat tinggi, portabilitas platform, dan performa tinggi mendekati *native*.

### Upstream-First Philosophy
Doktrin rekayasa di mana setiap perubahan, titik kait (*hook point*), antarmuka abstrak, atau perbaikan bug yang dibuat saat menangani klien harus diposisikan agar dapat langsung digabungkan ke repositori utama (*upstream product*). Kode spesifik klien diisolasi ke dalam konfigurasi atau modul plugin, sementara fondasi yang memungkinkan kode tersebut dieksekusi harus menjadi aset permanen produk inti.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Mekanisme Memori Lintas Batas FFI (Cross-Boundary Memory Management)
Ketika runtime bahasa yang menggunakan *Garbage Collector* (Go, Python, Java) berinteraksi dengan bahasa berorientasi sistem manual/RAII (C, C++, Rust), terdapat dua aturan fundamental yang tidak boleh dilanggar:

* **Ownership Transparan:** Runtime yang mengalokasikan blok memori adalah satu-satunya runtime yang berhak mendealokasikannya (*Allocator Affinity*). Jika Rust mengalokasikan `Vec<u8>` menggunakan `jemalloc`, Go/Cgo tidak boleh memanggil `free()` standar sistem operasi terhadap penunjuk (*pointer*) tersebut. Solusinya: modul pengekspor harus mengekspos fungsi destruktor spesifik (misal: `rust_free_buffer()`).
* **Representasi Biner yang Stabil:** Tata letak struktur data harus eksplisit. Kompiler modern secara default mengacak urutan *field* dalam *struct* demi optimasi *padding* (misal: Rust ABI tidak stabil). Oleh karena itu, kita harus memaksakan tata letak C murni menggunakan anotasi `#[repr(C)]`.

```
       Go Runtime (Host)                    Rust Core (Guest FFI)
  ┌─────────────────────────┐             ┌─────────────────────────┐
  │ Allocates Go Pointer    │             │ Expects C-compatible    │
  │ GC tracks memory        │             │ byte array layout       │
  └────────────┬────────────┘             └────────────┬────────────┘
               │                                       │
               │  1. Unsafe Pointer Casting            │
               ├──────────────────────────────────────>│  Reads buffer
               │                                       │  (Zero-Copy)
               │                                       │
               │  2. Allocate Response                 │
               │<──────────────────────────────────────┤  Rust Allocator
               │                                       │  creates buffer
               │                                       │
               │  3. Free Memory Request               │
               ├──────────────────────────────────────>│  Calls explicit
               │                                       │  deallocator function
  ┌────────────┴────────────┐             ┌────────────┴────────────┐
  │ Continue processing     │             │ Memory returned cleanly │
  └─────────────────────────┘             └─────────────────────────┘
```

### 2. Penanganan Panic/Exceptions pada Batas FFI
Mekanisme *unwinding* saat terjadi `panic!` pada Rust atau `throw` pada C++ yang melintasi batas C ABI akan menghasilkan status *Undefined Behavior* (UB), yang hampir selalu memicu `SIGSEGV` atau *abort* instan pada proses host.
* **Strategi Mitigasi:** Seluruh fungsi eksternal FFI wajib dibungkus dalam blok penangkap kesalahan (`std::panic::catch_unwind` di Rust). Status kegagalan harus dipetakan ke kode kesalahan biner bertipe numerik (*integer status code*) atau `enum` bergaya C.

### 3. Pipeline Upstream-First dalam Siklus Hidup Proyek Klien
Untuk mencegah terjadinya percabangan kode permanen (*permanent code divergence*), insinyur FDE mengikuti siklus 4 tahap:

1. **Abstraksi Hook Point:** Identifikasi bagian mana dari *core product* yang kaku. Daripada menempelkan logika klien langsung di sana, buat sebuah *Plugin Interface* atau *Event Interceptor* abstrak di *upstream core*.
2. **Deploy via Local Injection:** Tulis modul kustom klien yang mengimplementasikan *interface* tersebut, dikompilasi secara independen sebagai *shared object* (`.so` / `.dylib`) atau WASM blob.
3. **Pull Request Upstream:** Kirimkan *Hook Point* dan *Interface* tersebut ke *mainline core product*. Tim produk inti akan menerimanya karena fitur tersebut membuat platform lebih modular tanpa membawa beban kode spesifik klien.
4. **Maintenance Rebase:** Saat rilis versi produk inti berikutnya keluar, modul bespoke klien tidak perlu dirombak total—cukup diperbarui mengikuti kontrak ABI antarmuka yang telah resmi menjadi bagian dari *upstream*.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah arsitektur detail sistem FDE tingkat tinggi yang menggabungkan integrasi FFI performa tinggi, sandboxing plugin dinamis, dan isolasi memori:

```
+---------------------------------------------------------------------------------------+
| HOST PROCESS (Enterprise Orchestrator / Ingestion Engine)                             |
| Runtime: Go / Core Engine Process                                                     |
|                                                                                       |
|  +--------------------------+         +--------------------------------------------+  |
|  | Pipeline Scheduler       |         | Core Upstream Hook Manager                 |  |
|  | (Event Ingestion)        |         | (Plugin Registry & ABI Life-Cycle)         |  |
|  +------------+-------------+         +---------------------+----------------------+  |
|               |                                             |                         |
|               | Pass Payload Pointer                        | Direct Symbol Lookup    |
|               v                                             v                         |
|  +---------------------------------------------------------------------------------+  |
|  | FFI INTEROP BOUNDARY LAYER (cgo / dlsym)                                        |  |
|  | - Direct Memory Pinning (No GC Relocation)                                      |  |
|  | - Status Code Translation & OOM Sentinel Checks                                 |  |
|  +--------------------+-------------------------------------+----------------------+  |
+-----------------------|-------------------------------------|-------------------------+
                        | Raw Shared Pointer                  |
                        | (Zero-Copy Transfer)                | Unix Domain Socket / IPC
                        v                                     v
+------------------------------------+   +----------------------------------------------+
| IN-PROCESS NATIVE BESPOKE PLUGIN   |   | OUT-OF-PROCESS BESPOKE EXTENSION (ISOLATED)  |
| Runtime: Rust (cdylib, #[repr(C)]) |   | Architecture: HashiCorp go-plugin or WASM    |
|                                    |   | Runtime: Wasmtime / Isolated Subprocess      |
|  +------------------------------+  |   |                                              |
|  | Safe Entry Boundary          |  |   |  +----------------------------------------+  |
|  | (catch_unwind guard)         |  |   |  | WASI Virtual Memory Sandbox            |  |
|  +--------------+---------------+  |   |  | Memory Limits: Max 128MB               |  |
|                 v                  |   |  +-------------------+--------------------+  |
|  +------------------------------+  |   |                      ^                       |
|  | High-Throughput Processing   |  |   |                      |                       |
|  | (e.g. SIMD Decrypt/Parser)   |  |   |  +-------------------+--------------------+  |
|  +--------------+---------------+  |   |  | IPC / Wasm Host-Function Adapter       |  |
|                 v                  |   |  | Bidirectional Ring Buffer              |  |
|  +------------------------------+  |   |  +----------------------------------------+  |
|  | Explicit Allocator Export    |  |   +----------------------------------------------+
|  | (bespoke_free_buffer)        |  |
|  +------------------------------+  |
+------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah demonstrasi minimal pembuatan Rust dynamic shared library yang mengekspor fungsi C-ABI untuk enkripsi XOR sederhana secara *in-place* (zero-copy), kemudian dipanggil oleh aplikasi host Go via Cgo.

### Rust Component (`libbespoke.rs`)
```rust
// Cargo.toml:
// [lib]
// crate-type = ["cdylib"]

use std::panic::catch_unwind;
use std::slice;

#[repr(C)]
pub enum FfiStatus {
    Ok = 0,
    NullPointer = 1,
    PanicOccurred = 2,
}

#[no_mangle]
pub unsafe extern "C" fn bespoke_xor_transform(
    data: *mut u8,
    len: usize,
    key: u8,
) -> FfiStatus {
    let result = catch_unwind(|| {
        if data.is_null() {
            return FfiStatus::NullPointer;
        }

        // Membentuk slice langsung dari pointer tanpa alokasi memori tambahan
        let buffer = slice::from_raw_parts_mut(data, len);
        for byte in buffer.iter_mut() {
            *byte ^= key;
        }

        FfiStatus::Ok
    });

    match result {
        Ok(status) => status,
        Err(_) => FfiStatus::PanicOccurred,
    }
}
```

### Go Host Component (`main.go`)
```go
package main

/*
#cgo LDFLAGS: -L. -lbespoke
#include <stdint.h>
#include <stddef.h>

typedef enum {
    OK = 0,
    NULL_POINTER = 1,
    PANIC_OCCURRED = 2
} FfiStatus;

FfiStatus bespoke_xor_transform(uint8_t* data, size_t len, uint8_t key);
*/
import "C"
import (
	"fmt"
	"unsafe"
)

func main() {
	payload := []byte("RAHASIA_PERUSAHAAN_ENTERPRISE_KLIEN")
	key := byte(0xAA)

	fmt.Printf("Data Asli: %s\n", string(payload))

	// Mengambil pointer langsung ke buffer slice Go (In-place mutation)
	ptr := (*C.uint8_t)(unsafe.Pointer(&payload[0]))
	length := C.size_t(len(payload))

	status := C.bespoke_xor_transform(ptr, length, C.uint8_t(key))
	if status != C.OK {
		panic(fmt.Sprintf("Transformasi FFI gagal dengan status: %d", status))
	}

	fmt.Printf("Data Terenkripsi (Hex): %X\n", payload)

	// Dekripsi kembali menggunakan operasi invers yang sama
	C.bespoke_xor_transform(ptr, length, C.uint8_t(key))
	fmt.Printf("Data Didekripsi: %s\n", string(payload))
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus nyata tingkat enterprise: Ingestion Gateway produk inti perlu memproses payload mentah berformat biner kustom perbankan (berisi data sensitif), mengekstrak nomor rekening, memvalidasi checksum, dan mengembalikan struktur data terurai (*parsed struct*).

Solusi diimplementasikan dengan Rust untuk kecepatan dan keamanan memori mutlak, diekspor melalui C ABI ke Go Engine, dengan garansi penanganan alokasi/deallokasi memori dua arah yang aman.

### 1. Rust Bespoke Engine (`bespoke_parser/src/lib.rs`)

```rust
use std::ffi::CString;
use std::os::raw::c_char;
use std::panic::catch_unwind;
use std::slice;

#[repr(C)]
pub struct AccountRecord {
    pub account_id: u64,
    pub balance_cents: i64,
    pub is_active: bool,
    pub metadata_json: *mut c_char, // Dialokasikan oleh Rust, harus dibebaskan oleh Rust
}

#[repr(C)]
#[derive(Debug, PartialEq, Eq)]
pub enum ParseResultCode {
    Success = 0,
    InvalidPayload = 1,
    ChecksumMismatch = 2,
    NullArgument = 3,
    InternalPanic = 4,
}

#[no_mangle]
pub unsafe extern "C" fn parse_bespoke_banking_frame(
    raw_bytes: *const u8,
    length: usize,
    out_record: *mut AccountRecord,
) -> ParseResultCode {
    let result = catch_unwind(|| {
        if raw_bytes.is_null() || out_record.is_null() {
            return ParseResultCode::NullArgument;
        }

        let input = slice::from_raw_parts(raw_bytes, length);

        // Frame Specification: [4 bytes MAGIC (0xFA 0xCE 0x00 0x01)] + [8 bytes ID] + [8 bytes Balance] + [1 byte Checksum]
        if input.len() < 21 {
            return ParseResultCode::InvalidPayload;
        }

        if &input[0..4] != &[0xFA, 0xCE, 0x00, 0x01] {
            return ParseResultCode::InvalidPayload;
        }

        // Kalkulasi checksum sederhana (XOR sum)
        let mut computed_checksum: u8 = 0;
        for &byte in &input[0..20] {
            computed_checksum ^= byte;
        }

        if computed_checksum != input[20] {
            return ParseResultCode::ChecksumMismatch;
        }

        let account_id = u64::from_be_bytes(input[4..12].try_into().unwrap());
        let balance_cents = i64::from_be_bytes(input[12..20].try_into().unwrap());

        // Membuat string JSON heap-allocated
        let json_meta = format!(
            "{{\"engine\":\"bespoke-rust\",\"processed_epoch\":{}}}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs()
        );

        let c_json = match CString::new(json_meta) {
            Ok(c) => c.into_raw(),
            Err(_) => return ParseResultCode::InternalPanic,
        };

        // Mengisi struct luaran
        (*out_record).account_id = account_id;
        (*out_record).balance_cents = balance_cents;
        (*out_record).is_active = balance_cents > 0;
        (*out_record).metadata_json = c_json;

        ParseResultCode::Success
    });

    result.unwrap_or(ParseResultCode::InternalPanic)
}

#[no_mangle]
pub unsafe extern "C" fn free_bespoke_record(record: *mut AccountRecord) {
    if record.is_null() {
        return;
    }

    // Bebaskan metadata JSON yang dialokasikan oleh CString::into_raw
    if !(*record).metadata_json.is_null() {
        let _ = CString::from_raw((*record).metadata_json);
        (*record).metadata_json = std::ptr::null_mut();
    }
}
```

### 2. Go Production Host Engine (`engine/gateway.go`)

```go
package main

/*
#cgo LDFLAGS: -L./lib -lbespoke_parser
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>

typedef enum {
    SUCCESS = 0,
    INVALID_PAYLOAD = 1,
    CHECKSUM_MISMATCH = 2,
    NULL_ARGUMENT = 3,
    INTERNAL_PANIC = 4
} ParseResultCode;

typedef struct {
    uint64_t account_id;
    int64_t balance_cents;
    bool is_active;
    char* metadata_json;
} AccountRecord;

ParseResultCode parse_bespoke_banking_frame(
    const uint8_t* raw_bytes,
    size_t length,
    AccountRecord* out_record
);

void free_bespoke_record(AccountRecord* record);
*/
import "C"
import (
	"errors"
	"fmt"
	"time"
	"unsafe"
)

type ProcessedAccount struct {
	ID           uint64
	BalanceUSD   float64
	IsActive     bool
	MetadataJSON string
}

// IngestionEngine bertanggung jawab melakukan parsing payload performa tinggi
type IngestionEngine struct{}

func (e *IngestionEngine) ParseRawFrame(data []byte) (*ProcessedAccount, error) {
	if len(data) == 0 {
		return nil, errors.New("payload kosong")
	}

	var rawRecord C.AccountRecord

	// Panggil FFI Boundary
	cBytes := (*C.uint8_t)(unsafe.Pointer(&data[0]))
	cLen := C.size_t(len(data))

	status := C.parse_bespoke_banking_frame(cBytes, cLen, &rawRecord)

	// Pastikan pembersihan memori Rust dipanggil saat fungsi keluar
	defer C.free_bespoke_record(&rawRecord)

	switch status {
	case C.SUCCESS:
		// Berhasil, petik hasil konversi C string ke Go native string
		meta := C.GoString(rawRecord.metadata_json)
		return &ProcessedAccount{
			ID:           uint64(rawRecord.account_id),
			BalanceUSD:   float64(rawRecord.balance_cents) / 100.0,
			IsActive:     bool(rawRecord.is_active),
			MetadataJSON: meta,
		}, nil
	case C.INVALID_PAYLOAD:
		return nil, errors.New("frame biner rusak atau header tidak sesuai")
	case C.CHECKSUM_MISMATCH:
		return nil, errors.New("integritas data gagal: checksum mismatch")
	case C.NULL_ARGUMENT:
		return nil, errors.New("argumen pointer FFI null")
	case C.INTERNAL_PANIC:
		return nil, errors.New("unhandled native core panic tertangkap")
	default:
		return nil, fmt.Errorf("kode status FFI tidak dikenal: %d", status)
	}
}

func main() {
	engine := &IngestionEngine{}

	// Menyiapkan Payload Valid:
	// Magic: FA CE 00 01
	// Account ID: 00 00 00 00 00 0F 42 40 (1,000,000)
	// Balance:    00 00 00 00 00 07 A1 20 ($5,000.00 -> 500000 cents)
	rawPayload := []byte{
		0xFA, 0xCE, 0x00, 0x01,
		0x00, 0x00, 0x00, 0x00, 0x00, 0x0F, 0x42, 0x40,
		0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0xA1, 0x20,
	}

	// Hitung XOR Checksum
	var cs byte = 0
	for _, b := range rawPayload {
		cs ^= b
	}
	rawPayload = append(rawPayload, cs)

	start := time.Now()
	res, err := engine.ParseRawFrame(rawPayload)
	duration := time.Since(start)

	if err != nil {
		fmt.Printf("Gagal memproses frame: %v\n", err)
		return
	}

	fmt.Printf("[PROD SUCCESS] Durasi Pemrosesan: %v\n", duration)
	fmt.Printf("ID Akun       : %d\n", res.ID)
	fmt.Printf("Saldo (USD)   : $%.2f\n", res.BalanceUSD)
	fmt.Printf("Status Aktif  : %t\n", res.IsActive)
	fmt.Printf("Metadata JSON : %s\n", res.MetadataJSON)
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Pendekatan | Dynamic Shared Lib (C-ABI / FFI) | Out-of-Process IPC (gRPC/Unix Sockets) | WebAssembly Sandbox (WASI) | Upstream Direct Patching |
| :--- | :--- | :--- | :--- | :--- |
| **Latensi Eksekusi** | Ultra Rendah (~10-50 ns call overhead). | Moderat (~10-100 µs IPC serialisasi). | Rendah (~100-300 ns call overhead). | Terendah (Zero overhead, inlineable). |
| **Isolasi Kerusakan (Blast Radius)** | **Nol:** SIGSEGV pada ekstensi mematikan seluruh host process. | **Penuh:** Host bertahan jika plugin crash / killed via OOM. | **Tinggi:** Memory trapped dalam isolated runtime memory page. | **Nol:** Bug merusak seluruh runtime inti. |
| **Beban Pemeliharaan (Maintenance)** | Menengah (harus menjaga kompatibilitas ABI). | Rendah (kontrak Protobuf/gRPC yang fleksibel). | Rendah (Wasm runtime mengabstraksi platform). | **Sangat Tinggi:** Menimbulkan resiko merge conflict berkepanjangan. |
| **Kompleksitas Distribusi** | Tinggi (harus kompilasi per arsitektur target OS/CPU). | Menengah (binary terpisah yang didistribusikan bersama). | Sangat Rendah (satu biner `.wasm` untuk semua OS). | Nihil (terpaket otomatis dalam release core). |
| **Keamanan Memori** | Rawan kebocoran manual dan buffer overflow. | Terproteksi oleh batas proses OS. | Terproteksi secara kriptografis & memori terisolasi. | Bergantung pada bahasa produk inti. |

---

## SEKSI 11 — BEST PRACTICES

1. **Prinsip Single Memory Owner:** Selalu terapkan pola *Borrower / Allocator-Freer*. Jika Go memberikan pointer ke Rust, Rust hanya boleh membaca/menulis memori tersebut tanpa mendealokasikannya. Jika Rust mengalokasikan memori untuk dikembalikan ke Go, sertakan fungsi *destructor* FFI khusus dari Rust yang dieksekusi via `defer` di Go.
2. **Karantina Unsafe Code:** Seluruh kode Rust yang menggunakan penanda `unsafe` untuk konversi pointer harus diisolasi di balik modul `ffi::safe_bridge`. Modul bisnis lainnya di dalam plugin harus tetap 100% *safe Rust*.
3. **Penyematan Hook Point Generik pada Upstream Core:** Saat merancang *hook* di produk inti untuk kebutuhan satu klien, jangan pernah gunakan istilah spesifik klien (contoh buruk: `execute_client_bca_checksum()`). Namai secara generik (contoh baik: `register_payload_validator_interceptor()`).
4. **Validasi ABI Statically Menggunakan CI:** Gunakan alat otomatis seperti `cargo-semver-checks` atau `abi-dumper` di pipeline CI untuk memverifikasi bahwa perubahan kode di produk inti tidak merusak keselarasan memori (*memory alignment*) atau urutan *struct* yang digunakan oleh modul bespoke.
5. **Observabilitas Lintas Batas:** Propagasikan konteks tracing (*Distributed Tracing Context* / OpenTelemetry traceparent) melintasi batas FFI/Plugin. Catat metrik durasi pemanggilan plugin secara independen untuk mendeteksi *bottleneck* performa di kode bespoke klien.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Melewatkan Penanganan Panic Melintasi Batas ABI:** Membiarkan fungsi FFI melakukan *unwinding panic* tanpa ditangkap oleh `catch_unwind`. Hal ini akan seketika menghasilkan status pemutusan abnormal (*Core Dump*) pada sistem produksi klien.
2. **Mengabaikan Go GC Pointer Tracking (`cgo` pointer passing rules):** Mengirimkan pointer Go yang menunjuk ke pointer Go lain ke dalam C/Rust runtime. Aturan Cgo melarang menyimpan pointer Go di heap eksternal karena Go Garbage Collector dapat memindahkan memori tersebut secara acak saat fase *compaction*.
3. **Deallokasi Silang (Cross-Allocator Free):** Mengalokasikan array string di Rust menggunakan `alloc::alloc` lalu mencoba membebaskannya di Go atau C menggunakan `C.free()`. Hal ini merusak struktur internal *memory arena* dan memicu `glibc malloc error: invalid pointer`.
4. **Hardcoding Logika Klien di Upstream Trunk:** Menulis `if clientID == "BANK_ABC" { ... }` langsung di dalam repositori inti produk. Ini merupakan pelanggaran fatal terhadap arsitektur FDE yang menjamin kode inti tetap bersih dan netral terhadap kebutuhan partikular satu entitas.
5. **Pengepakan Struct yang Berbeda Antara Dua Bahasa:** Lupa menambahkan anotasi `#[repr(C)]` pada struct di Rust atau `__attribute__((packed))` di C ketika bertukar data biner dengan Go, menyebabkan *offset* setiap *field* bergeser karena optimasi *byte alignment* kompiler.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Safe String Manipulation across FFI
* **Skenario:** Klien enterprise mengharuskan penyamaran (*masking*) nomor kartu kredit (16 digit) menjadi format `************1234` di dalam data stream latensi tinggi.
* **Tugas:** 
  1. Tulis pustaka Rust (`masker.rs`) yang menerima `*const c_char` dan mengembalikan `*mut c_char` yang baru dialokasikan dengan nomor kartu terenkripsi.
  2. Implementasikan penangkap `panic` untuk mengembalikan *null pointer* jika string input bukan UTF-8 valid.
  3. Buat wrapper Go yang mengonsumsi modul tersebut, mengubahnya menjadi `string` Go, dan membersihkan alokasi memori Rust tanpa terjadi *leak*.

### Latihan 2: Desain Upstream-Friendly Plugin Registry Interface
* **Skenario:** Engine pemrosesan dokumen perusahaan Anda hanya mendukung PDF. Satu klien meminta sistem mendukung parsing format biner proprietary `.dat`.
* **Tugas:**
  1. Buat arsitektur *Plugin Engine* di Go menggunakan interface `DocumentParser` dengan fungsi:
     ```go
     type DocumentParser interface {
         CanParse(magicHeader []byte) bool
         ExtractText(payload []byte) (string, error)
     }
     ```
  2. Rancang implementasi pemuatan dinamis menggunakan HashiCorp `go-plugin` (IPC via Unix Domain Socket).
  3. Demonstrasikan bagaimana modul klien `.dat` dapat berjalan secara mandiri dan crash-nya plugin tersebut tidak menghentikan host engine Go utama.

### Latihan 3: Git Rebase & Upstream Sync Simulation
* **Skenario:** Anda telah membuat cabang `bespoke-client-x` dari repositori produk inti versi `v2.4.0`. Sementara Anda mengerjakan fitur klien, tim produk inti merilis `v2.5.0` yang merombak package konfigurasi.
* **Tugas:**
  1. Simulasikan skenario ini menggunakan repositori git lokal.
  2. Identifikasi *conflict chunk*.
  3. Lakukan abstraksi *Hook Interface* secara terpisah, lalu rebase cabang kustom Anda di atas `v2.5.0` tanpa meninggalkan jejak modifikasi kotor (*clean commit history*).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Mengapa penanda `#[no_mangle]` sangat fundamental saat mengekspor fungsi Rust untuk dihubungkan melalui C ABI?**
   * *Jawaban Singkat:* Kompiler Rust secara default mengubah (*mangle*) nama simbol fungsi internal dengan hash acak untuk mendukung fitur unik (*namespacing*, *overloading*). `#[no_mangle]` mematikan perilaku ini sehingga nama simbol fungsi tetap identik saat dicari oleh *dynamic linker* runtime lain.

2. **Apa yang terjadi pada memori proses host jika fungsi C ABI Rust mengembalikan raw pointer `CString::into_raw()` dan host membuang referensi pointer tersebut tanpa memanggil fungsi destructor Rust?**
   * *Jawaban Singkat:* Terjadi kebocoran memori permanen (*leak*). Pointer tersebut dialokasikan di atas heap Rust dan telah dilepaskan dari kendali borrow-checker, sehingga memori tersebut tidak akan pernah dibebaskan sampai seluruh proses aplikasi host berhenti.

3. **Kapan Anda sebagai FDE harus memilih WebAssembly (WASI) dibandingkan Native C ABI (Dynamic Shared Object)?**
   * *Jawaban Singkat:* Saat kode kustom yang dijalankan tidak dipercaya (*untrusted code*), dibuat oleh pihak ketiga, rawan mengalami kegagalan memori, atau sistem host memerlukan jaminan portabilitas lintas platform (misal ARM64 dan AMD64) tanpa perlu mengompilasi biner native terpisah untuk setiap target infrastruktur.

4. **Sebutkan dua resiko utama implementasi Cgo pada aplikasi Go berkinerja tinggi!**
   * *Jawaban Singkat:* Biaya *context-switching* pemanggilan fungsi Cgo (~50-100 nanodetik per panggilan karena perubahan stack runtime Go ke thread native POSIX) dan komplikasi pengelolaan Goroutine stack resizing yang dapat menyebabkan bottleneck saat jumlah konkurensi sangat tinggi.

5. **Apa indikator utama bahwa sebuah solusi bespoke klien melanggar filosofi "Upstream-First"?**
   * *Jawaban Singkat:* Ketika perubahan tersebut mengharuskan pembuatan salinan cabang kode (*fork*) yang tidak mungkin lagi digabungkan (*unmergeable*) ke cabang rilis utama produk inti tanpa merusak alur kerja pengguna standar lainnya.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **The Rust FFI Omnibus:** Koleksi pola arsitektur interkoneksi biner multi-bahasa (http://jakegoulding.com/rust-ffi-omnibus/).
* **The Go Memory Model & Cgo Rules:** Dokumentasi internal Go Runtime mengenai batas transmisi pointer (`os/exec`, `runtime/cgo`).
* **Book: "Building Distributed Plugins with HashiCorp go-plugin":** Dokumentasi arsitektur HashiCorp terkait IPC-based isolation.
* **Wasmtime Deep Dive Docs:** Runtime architecture and host-to-guest WebAssembly memory mapping (https://docs.wasmtime.dev/).
* **"Upstream First" by Red Hat Enterprise Architecture Group:** Metodologi industri dalam mencegah *technical divergence* pada software ekosistem enterprise.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Rekayasa solusi bespoke bagi seorang FDE bukanlah jalan pintas (*hack*), melainkan bentuk kedisiplinan arsitektur tertinggi di mana ekstensi kustom dibangun dengan kecepatan kilat melalui isolasi kontrak biner yang ketat.
2. Interoperabilitas lintas bahasa via FFI menyediakan latensi minimal, namun menuntut kehati-hatian ekstrem terhadap batas alokasi memori (*allocator boundaries*), keselarasan biner (`#[repr(C)]`), dan pencegahan transmisi *panic*.
3. Model arsitektur plugin terisolasi (IPC dan WASM) menawarkan perlindungan *blast radius* yang jauh lebih tinggi dibandingkan *dynamic shared libraries* in-process, dengan trade-off berupa biaya latensi serialisasi.
4. Filosofi *Upstream-First* menjamin bahwa seluruh titik integrasi (*hook points*) diabstraksikan dan dikontribusikan kembali ke *codebase* utama, menjamin keberlanjutan produk jangka panjang dan menghilangkan ancaman *code divergence*.

---

## SEKSI 17 — GLOSARIUM

* **ABI (Application Binary Interface):** Standar antarmuka biner tingkat rendah antara dua modul biner program; mendikte urutan peletakan register, keselarasan data memori, dan konvensi pemanggilan stack.
* **cgo:** Perangkat utilitas kompiler Go yang memungkinkan package Go memanggil kode C secara langsung.
* **cdylib:** Tipe output kompilasi pustaka Rust yang menghasilkan pustaka biner dinamis yang dapat diakses oleh bahasa pemrograman lain melalui konvensi pemanggilan C.
* **In-place Mutation:** Operasi pengubahan data langsung pada blok memori yang sedang digunakan tanpa perlu menyalin atau mengalokasikan array penampung baru.
* **Panic Unwinding:** Proses traversal dan pembersihan stack frame yang terjadi saat program runtime mengalami terminasi tak terduga (*runtime panic*).
* **WASI (WebAssembly System Interface):** Standar antarmuka modular yang menyediakan akses abstraksi sistem operasi (berkas, soket, jam) ke program WebAssembly secara aman.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Peringatan Lingkungan Lab:** Pastikan workstation peserta memiliki toolchain kompilasi lengkap: `gcc` / `clang`, `rustup` (stable toolchain), dan `go` versi 1.20 ke atas. Sistem operasi berbasis Linux/POSIX sangat dianjurkan untuk mendalami `LD_LIBRARY_PATH` debugging.
* **Fokus Pelatihan:** Jangan biarkan peserta menyelesaikan latihan hands-on hanya dengan membuat kode "berjalan". Uji hasil pekerjaan mereka menggunakan detektor kebocoran memori seperti `valgrind` atau alat bawaan Go: `go test -race` dan AddressSanitizer (`-fsanitize=address`).
* **Poin Penekanan Diskusi:** Tekankan bahwa solusi FFI terbaik adalah solusi FFI yang tidak perlu ditulis. Dorong siswa untuk selalu mengevaluasi arsitektur berbasis interface standar/WASM sebelum memutuskan terjun ke dynamic shared object FFI yang berbahaya.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi:** 1.0.0
* **Tanggal Rilis:** 2025-02-15
* **Author:** Principal Technical Architect & Forward Deployment Lead
* **Perubahan Terakhir:** 
  * Peluncuran kurikulum resmi Forward Deployed Engineer (FDE).
  * Penambahan implementasi FFI Rust-Go real-time frame parser dengan garansi pembersihan memori.
  * Penyempurnaan pedoman metodologi Upstream-First untuk arsitektur produk enterprise.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `05-Data-Engineering-and-Pipelines / FDE-DAT-0504 — Ultra-Low Latency Streaming & Event Architectures`
* **Modul Saat Ini:** `06-Architecture-and-System-Design / FDE-ARC-0601 — Rapid Prototyping & Bespoke Solution Engineering: Membangun Modul Kustom Berkecepatan Tinggi, FFI Bindings, Plugin Architectures, Upstream-First Philosophy`
* **Modul Berikutnya:** `06-Architecture-and-System-Design / FDE-ARC-0602 — Legacy Core System Modernization: Strangler Fig Pattern, CDC, and Zero-Downtime Data Interception`