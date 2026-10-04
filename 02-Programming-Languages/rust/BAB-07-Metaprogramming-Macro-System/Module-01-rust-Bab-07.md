# Bab 07 Module 01: Metaprogramming & Macro System

---

## SEKSI 01 — IDENTITAS MODUL

*   **Domain:** Sistem Pemrograman Bahasa Tingkat Tinggi & Rekayasa Kompiler
*   **Track:** Rust Advanced Systems Programming
*   **Module ID:** `RUST-07-01`
*   **Prasyarat:**
    *   Penguasaan Rust Ownership, Borrowing, dan Lifetimes (`RUST-01` - `RUST-03`).
    *   Pemahaman Traits, Associated Types, dan Generic Programming (`RUST-04`).
    *   Struktur Proyek Cargo, Workspace, dan Dependency Management (`RUST-05`).
*   **Target Audience:** Systems Engineers, Infrastructure Engineers, Rust Library Authors, Backend Architects.
*   **Durasi Estimasi:** 6 - 8 Jam (Membaca mendalam + Praktik Hands-On).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Membedakan** secara fundamental paradigma manipulasi kode pada level *Abstract Syntax Tree (AST)* antara *Declarative Macros* (`macro_rules!`) dan *Procedural Macros* (`proc_macro`).
2.  **Menganalisis** alur kerja kompilasi rustc dalam tahapan *tokenization*, *macro expansion*, dan *hygiene resolution*.
3.  **Mengonstruksi** *Declarative Macros* tingkat lanjut menggunakan teknik *Token-Tree Munching* (TT Munchers), *Push-down Automata*, dan *Internal Rules Pattern*.
4.  **Mengimplementasikan** *Custom Derive*, *Attribute-like*, dan *Function-like Procedural Macros* memanfaatkan crate `syn`, `quote`, dan `proc-macro2`.
5.  **Mengevaluasi** batas higienisitas (*hygiene*) macro, mitigasi polusi *namespace*, serta penggunaan `$crate` untuk portabilitas library.
6.  **Mendiagnosis** dan **mengoptimasi** degradasi waktu kompilasi (*compile-time bloat*) yang diakibatkan oleh ekspansi makro rekursif yang tidak terkontrol.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Perbedaan Paradigma: Metaprogramming C/C++ vs Rust

Dalam bahasa seperti C/C++, preprosesor bekerja melalui substitusi teks murni (*lexical text substitution*) sebelum fase parsing dimulai. Hal ini rentan terhadap *scope leakage*, evaluasi ganda ekspresi, dan kegagalan inferensi tipe:

```c
// C Preprocessor: Bahaya Substitusi Tekstual
#define SQUARE(x) x * x
int result = SQUARE(1 + 2); // Terekspansi menjadi: 1 + 2 * 1 + 2 = 5 (BUKAN 9)
```

Rust menolak pendekatan ini. Dalam Rust, metaprogramming beroperasi langsung pada struktur data sintaksis:

```
[Kode Sumber (.rs)] 
        │
        ▼ (Tokenisasi / Lexing)
[TokenStream] ──► [Rust Macro Engine] ──► [Modified TokenStream / AST]
                                                │
                                                ▼ (Type Checking & Borrow Check)
                                        [HIR / MIR / LLVM IR]
```

### Mental Model: Token Stream sebagai Objek Kelas Satu

1.  **Bukan String, Melainkan Token:** Makro di Rust tidak memanipulasi `String` mentah, melainkan `TokenStream`. Setiap elemen adalah `TokenTree`—bisa berupa `Ident`, `Punct`, `Literal`, atau kelompok bertanda kurung `Group` (`()`, `[]`, `{}`).
2.  **Hygiene:** Secara default, variabel yang dideklarasikan di dalam makro tidak akan "bocor" ke konteks pemanggil, begitu pula sebaliknya. Kompiler memberikan *SyntaxContext* (tanda pengenal unik/warna sintaksis) pada setiap identifier.
3.  **AST-Aware Execution:** Ekspansi makro terjadi pada tahapan sintaksis, sebelum *Type Checking* (analisis semantik) dan *Borrow Checking*. Makro tidak tahu *tipe* dari sebuah ekspresi; makro hanya tahu bahwa itu adalah struktur sintaksis bertipe `expr`, `ident`, `path`, atau `ty`.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Kompilasi dan Macro Expansion

```
 +-----------------------------------------------------------------------+
 |                            rustc Front-End                            |
 +-----------------------------------------------------------------------+
                                    │
                               Source Code
                                    │
                                    ▼
                           +-----------------+
                           | Lexer / Scanner |
                           +-----------------+
                                    │
                               TokenStream
                                    │
                                    ▼
                      +---------------------------+
                      | Early Syntax Expansion   |
                      | (Built-in macros & cfg)  |
                      +---------------------------+
                                    │
                                    ▼
            +───────────────────────────────────────────────+
            │               Macro Expander                  │
            │                                               │
            │   macro_rules!            Procedural Macro    │
            │   (Pattern Matching)      (Separate Process/  │
            │          │                 Shared Dynamic Lib)│
            │          ▼                        │           │
            │   [AST Substitution]              ▼           │
            │          │                 [syn -> AST ->     │
            │          │                  quote -> Tokens]  │
            +──────────┼────────────────────────┼───────────+
                       │                        │
                       └───────────┬────────────┘
                                   │
                                   ▼
                       +-----------------------+
                       | AST (Expanded Code)   |
                       +-----------------------+
                                   │
                                   ▼
                       +-----------------------+
                       | Name Resolution &     |
                       | Hygiene Verification  |
                       +-----------------------+
                                   │
                                   ▼
                       +-----------------------+
                       | Type Checking (HIR)   |
                       +-----------------------+
                                   │
                                   ▼
                       +-----------------------+
                       | Borrow Checker (MIR)  |
                       +-----------------------+
                                   │
                                   ▼
                       +-----------------------+
                       | LLVM IR & Codegen     |
                       +-----------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi Declarative Macros (`macro_rules!`)

Declarative macro menggunakan pencocokan pola struktural (*pattern matching*) mirip dengan ekspresi `match`, namun dievaluasi pada level sintaksis token:

```rust
macro_rules! my_macro {
    // Matcher Pattern
    (pattern_to_match) => {
        // Transcriber / Code generation
    };
    // Matcher dengan designator
    ($var:ident : $type:ty) => {
        let $var: $type;
    };
}
```

#### Matcher Designators (Pemberi Tanda Tipe Token):
*   `ident`: Pengenal/Identifier nama fungsi, variabel, struct (contoh: `foo`, `MyStruct`).
*   `expr`: Ekspresi valid yang menghasilkan nilai (contoh: `2 + 2`, `get_val()`).
*   `ty`: Tipe data (contoh: `i32`, `Vec<String>`, `&'a str`).
*   `path`: Jalur modul atau tipe (contoh: `std::collections::HashMap`).
*   `pat`: Pola pencocokan (contoh: `Some(x)`, `_`, `1..=5`).
*   `stmt`: Statement tunggal (contoh: `let x = 5;`).
*   `block`: Blok instruksi yang dibungkus kurung kurawal `{ ... }`.
*   `item`: Definisi item top-level (contoh: `fn foo() {}`, `struct Bar;`).
*   `meta`: Isi dari atribut (contoh: `derive(Debug)`).
*   `tt`: *Token Tree* tunggal (semua token tunggal atau blok yang dikurung).
*   `literal`: Nilai literal konstan (contoh: `"string"`, `42`, `true`).
*   `vis`: Visibilitas (contoh: `pub`, `pub(crate)`).
*   `lifetime`: Anotasi lifetime (contoh: `'a`).

#### Repetisi Syntactic:
Format: `$ ( ... ) SEP REP`
*   `SEP`: Separator opsional (contoh: `,`, `;`).
*   `REP`: Simbol frekuensi:
    *   `*` : 0 atau lebih repetisi.
    *   `+` : 1 atau lebih repetisi.
    *   `?` : 0 atau 1 repetisi (opsional).

### 2. Anatomi Procedural Macros

Procedural Macros adalah fungsi Rust murni yang dieksekusi oleh kompiler selama proses kompilasi. Fungsi ini berperan sebagai fungsi transformasi sintaksis:

$$\text{Function Signature: } f(\text{TokenStream}) \to \text{TokenStream}$$

Procedural Macros terbagi atas tiga kategori:

| Kategori | Definisi Signature Atribut | Contoh Pemanggilan |
| :--- | :--- | :--- |
| **Custom Derive** | `#[proc_macro_derive(MyTrait, attributes(helper))]` | `#[derive(MyTrait)]` |
| **Attribute-like**| `#[proc_macro_attribute]` | `#[my_route(GET, "/api")]` |
| **Function-like** | `#[proc_macro]` | `sql_query!("SELECT * FROM users")` |

Procedural macro **wajib** diisolasi dalam *crate* terpisah yang memiliki konfigurasi `Cargo.toml`:
```toml
[lib]
proc-macro = true
```

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Macro Hygiene (Higienisitas Sintaksis)

Secara historis, masalah terbesar makro adalah kontaminasi variabel. Rust menerapkan higiene parsial (*Partial Hygiene*) melalui konsep *Syntax Context*:

*   **Ident Hygiene:** Variabel lokal yang dibuat di dalam makro `macro_rules!` memiliki konteks sintaksis yang berbeda dari konteks pemanggil (*caller*).
*   **Item Hygiene:** Item (seperti `struct`, `fn`) tidak sepenuhnya higienis di `macro_rules!`. Path item harus di-resolve secara berhati-hati.

#### Masalah Name Resolution & Solusi `$crate`
Ketika library Anda mengekspor declarative macro, macro tersebut akan diekspansi di dalam *crate* pengguna (konsumen). Jika makro Anda mereferensikan tipe dari crate Anda sendiri atau dependensi lain, pemanggil mungkin tidak mengimpor modul tersebut ke dalam scope mereka.

```rust
// SALAH (Rapuh terhadap scope konsumen)
macro_rules! create_vec {
    ($val:expr) => {
        std::vec::Vec::from([$val]) // GAGAL jika konsumen meng-override atau men-shadow `std`
    };
}

// BENAR (Higienis secara path resolution)
#[macro_export]
macro_rules! create_vec {
    ($val:expr) => {
        $crate::reexport_std::vec::Vec::from([$val])
    };
}
```
Keyword `$crate` akan diekspansi menjadi path absolut crate pendefinisi makro (`::nama_crate_anda`) saat dipanggil dari luar, menjamin isolasi referensi dependensi.

### 2. TT-Munching (Token-Tree Muncher Pattern)

TT-Muncher adalah pola komputasi rekursif di mana declarative macro memproses input token selangkah demi selangkah. Pola ini membaca satu atau lebih token dari kepala (*head*), memprosesnya, dan meneruskan sisa ekor token (*tail*) kembali ke makro itu sendiri secara rekursif hingga basis terminasi tercapai.

Arsitektur TT-Muncher:
1.  **State Machine:** Menjaga akumulator state dalam tanda kurung tertentu.
2.  **Base Case:** Pola matcher untuk kondisi terminasi (biasanya input kosong).
3.  **Recursive Step:** Memisahkan token terdepan, memutasi state, dan memanggil ulang dirinya.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi declarative macro bertipe TT-Muncher yang mem-parsing konfigurasi dictionary/map berbasis tipe statis kuat dengan validasi sintaksis.

```rust
// File: src/lib.rs

#[macro_export]
macro_rules! typed_map {
    // -------------------------------------------------------------
    // Entry point: Menginisialisasi accumulator (internal state)
    // -------------------------------------------------------------
    ( @init $( $tail:tt )* ) => {
        {
            let mut map = ::std::collections::HashMap::new();
            $crate::typed_map!(@munch map, $( $tail )*);
            map
        }
    };

    // -------------------------------------------------------------
    // Base Case: Ketika semua token telah diproses (Tail kosong)
    // -------------------------------------------------------------
    ( @munch $map:ident, ) => {};

    // -------------------------------------------------------------
    // Recursive Step 1: Matching format `KEY => VALUE, TAIL...`
    // -------------------------------------------------------------
    ( @munch $map:ident, $key:literal => $val:expr, $( $tail:tt )* ) => {
        $map.insert($key, $val);
        $crate::typed_map!(@munch $map, $( $tail )*);
    };

    // -------------------------------------------------------------
    // Recursive Step 2: Menangani trailing comma pada elemen terakhir
    // -------------------------------------------------------------
    ( @munch $map:ident, $key:literal => $val:expr ) => {
        $map.insert($key, $val);
    };

    // -------------------------------------------------------------
    // Public API Interface
    // -------------------------------------------------------------
    ( $( $tokens:tt )* ) => {
        $crate::typed_map!(@init $( $tokens )*)
    };
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_typed_map_construction() {
        let scores = typed_map! {
            "Alice" => 100,
            "Bob" => 85,
            "Charlie" => 92,
        };

        assert_eq!(scores.get("Alice"), Some(&100));
        assert_eq!(scores.get("Bob"), Some(&85));
        assert_eq!(scores.len(), 3);
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 3:** `#[macro_export]` menandai makro agar dapat diakses publik oleh crate eksternal yang mengimpor crate ini, menempatkannya di root namespace crate.
*   **Baris 8:** `( @init $( $tail:tt )* ) => {` mendefinisikan *internal sub-rule*. Karakter `@` adalah konvensi sintaksis idiomatik untuk menandai aturan privat (tidak untuk dipanggil langsung oleh konsumen makro). Pola `$( $tail:tt )*` menangkap seluruh token yang dikirimkan.
*   **Baris 10:** `let mut map = ::std::collections::HashMap::new();` mengalokasikan instance hashmap pada konteks pemanggil, menggunakan absolute path `::std` untuk menghindari konflik identifier local `std`.
*   **Baris 11:** `$crate::typed_map!(@munch map, $( $tail )*);` mengeksekusi rekursi pertama menuju parsing token, meneruskan identifier `map` dan sisa token. Penggunaan `$crate` menjaga resolusi deterministik namespace.
*   **Baris 18:** `( @munch $map:ident, ) => {};` adalah **Base Case**. Jika token stream tersisa hanya sebuah koma (atau kosong melalui pencocokan akhir), makro berhenti berekspansi.
*   **Baris 23:** `( @munch $map:ident, $key:literal => $val:expr, $( $tail:tt )* ) => {` merupakan **Recursive Engine**.
    *   `$map:ident` menangkap identifier variabel map.
    *   `$key:literal` memastikan kunci harus berupa literal konstan (mencegah komputasi runtime sembarang sebagai identifier kunci jika tidak diinginkan).
    *   `=>` token separator harfiah.
    *   `$val:expr` mengekstrak sembarang ekspresi valid Rust sebagai value.
    *   `$( $tail:tt )*` memisahkan seluruh sisa token stream ke dalam variabel `$tail`.
*   **Baris 24:** `$map.insert($key, $val);` menyuntikkan statement insert ke blok caller.
*   **Baris 25:** `$crate::typed_map!(@munch $map, $( $tail )*);` melakukan pemanggilan rekursif untuk memproses elemen berikutnya dari token stream yang tersisa.
*   **Baris 37-39:** `( $( $tokens:tt )* ) => { $crate::typed_map!(@init $( $tokens )*) };` adalah entri publik utama. Apapun input yang diberikan oleh konsumen akan dialihkan ke engine `@init`.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Konteks Masalah
Dalam arsitektur mikroservis finansial performa tinggi, sistem harus mendekode event payload dari format raw JSON/Binary ke domain struct, sekaligus memvalidasi batas nilai (*business constraints*) secara otomatis tanpa membebani overhead runtime (*zero runtime penalty* di luar komparasi dasar) dan tanpa boilerplate kode validasi manual repetitif di setiap model DTO.

### Kebutuhan
Kita membutuhkan macro derive custom: `#[derive(ValidateRange)]` yang membaca anotasi atribut helper:
`#[range(min = 10, max = 100)]`
dan menghasilkan implementasi trait:

```rust
pub trait RuntimeValidator {
    fn validate(&self) -> Result<(), String>;
}
```

Makro harus:
1.  Menginspeksi setiap field dari struct pada waktu kompilasi.
2.  Mengekstrak atribut batas minimum dan maksimum.
3.  Membuat blok kode evaluasi batas secara deterministik.
4.  Memberikan compile error yang jelas jika atribut diterapkan pada tipe data yang tidak kompatibel.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Struktur Workspace Cargo:
```text
validation_engine/
├── Cargo.toml
├── validator_derive/
│   ├── Cargo.toml
│   └── src/lib.rs
└── core_app/
    ├── Cargo.toml
    └── src/main.rs
```

### 1. `validator_derive/Cargo.toml`
```toml
[package]
name = "validator_derive"
version = "0.1.0"
edition = "2021"

[lib]
proc-macro = true

[dependencies]
syn = { version = "2.0", features = ["full", "extra-traits"] }
quote = "1.0"
proc-macro2 = "1.0"
```

### 2. `validator_derive/src/lib.rs`
Implementasi Procedural Macro:

```rust
use proc_macro::TokenStream;
use proc_macro2::TokenStream as TokenStream2;
use quote::quote;
use syn::{
    parse_macro_input, Data, DeriveInput, Fields, LitInt, Meta,
};

#[proc_macro_derive(ValidateRange, attributes(range))]
pub fn derive_validate_range(input: TokenStream) -> TokenStream {
    // Parsing TokenStream mentah menjadi AST Rust menggunakan syn
    let input = parse_macro_input!(input as DeriveInput);

    let struct_name = &input.ident;
    let validations = generate_field_validations(&input.data);

    // Sintesis kode implementasi menggunakan quote
    let expanded = quote! {
        impl RuntimeValidator for #struct_name {
            fn validate(&self) -> Result<(), String> {
                #validations
                Ok(())
            }
        }
    };

    // Mengembalikan hasil konversi TokenStream2 kembali ke proc_macro::TokenStream
    TokenStream::from(expanded)
}

fn generate_field_validations(data: &Data) -> TokenStream2 {
    let fields = match data {
        Data::Struct(data_struct) => match &data_struct.fields {
            Fields::Named(fields_named) => &fields_named.named,
            _ => panic!("ValidateRange hanya mendukung Named Structs"),
        },
        _ => panic!("ValidateRange hanya dapat digunakan pada Struct"),
    };

    let mut checks = Vec::new();

    for field in fields {
        let field_name = match &field.ident {
            Some(ident) => ident,
            None => continue,
        };

        for attr in &field.attrs {
            if !attr.path().is_ident("range") {
                continue;
            }

            let mut min_val: Option<i64> = None;
            let mut max_val: Option<i64> = None;

            // Parsing nested meta attributes #[range(min = 1, max = 10)]
            if let Err(err) = attr.parse_nested_meta(|meta| {
                if meta.path.is_ident("min") {
                    let value = meta.value()?;
                    let lit: LitInt = value.parse()?;
                    min_val = Some(lit.base10_parse::<i64>()?);
                    Ok(())
                } else if meta.path.is_ident("max") {
                    let value = meta.value()?;
                    let lit: LitInt = value.parse()?;
                    max_val = Some(lit.base10_parse::<i64>()?);
                    Ok(())
                } else {
                    Err(meta.error("Atribut range tidak didukung (gunakan 'min' atau 'max')"))
                }
            }) {
                panic!("Gagal mem-parsing atribut #[range]: {}", err);
            }

            let field_str = field_name.to_string();

            if let Some(min) = min_val {
                checks.push(quote! {
                    if (self.#field_name as i64) < #min {
                        return Err(format!(
                            "Validasi gagal: Field '{}' bernilai {}, batas minimum {}",
                            #field_str, self.#field_name, #min
                        ));
                    }
                });
            }

            if let Some(max) = max_val {
                checks.push(quote! {
                    if (self.#field_name as i64) > #max {
                        return Err(format!(
                            "Validasi gagal: Field '{}' bernilai {}, batas maksimum {}",
                            #field_str, self.#field_name, #max
                        ));
                    }
                });
            }
        }
    }

    quote! {
        #( #checks )*
    }
}
```

### 3. `core_app/Cargo.toml`
```toml
[package]
name = "core_app"
version = "0.1.0"
edition = "2021"

[dependencies]
validator_derive = { path = "../validator_derive" }
```

### 4. `core_app/src/main.rs`
Konsumsi Macro pada Domain Model:

```rust
use validator_derive::ValidateRange;

pub trait RuntimeValidator {
    fn validate(&self) -> Result<(), String>;
}

#[derive(Debug, ValidateRange)]
pub struct TransactionRequest {
    #[range(min = 1, max = 1000000)]
    pub amount: u64,

    #[range(min = 18, max = 120)]
    pub user_age: u8,

    pub note: String, // Field tanpa anotasi tidak divalidasi
}

fn main() {
    let valid_txn = TransactionRequest {
        amount: 50_000,
        user_age: 25,
        note: "Payment for server hosting".to_string(),
    };

    let invalid_txn = TransactionRequest {
        amount: 0, // Melanggar min = 1
        user_age: 15, // Melanggar min = 18
        note: "Unauthorized payload".to_string(),
    };

    println!("Status Validasi Transaksi 1: {:?}", valid_txn.validate());
    assert!(valid_txn.validate().is_ok());

    println!("Status Validasi Transaksi 2: {:?}", invalid_txn.validate());
    assert!(invalid_txn.validate().is_err());
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Parameter | Declarative Macros (`macro_rules!`) | Procedural Macros (`proc_macro`) | Generics & Trait System | Build Script (`build.rs`) |
| :--- | :--- | :--- | :--- | :--- |
| **Domain Operasi** | Pola Pencocokan Token AST | Transformasi TokenStream via Rust Code Arbitrer | Sistem Tipe & Komputasi Monomorphization | I/O Sistem, File Code-Gen, External Link |
| **Ekspresivitas** | Terbatas pada pola sintaksis deklaratif | Lengkap (Turing-complete melalui fungsi Rust) | Terikat pada semantik constraint type-system | Bebas (Menulis teks Rust ke file `$OUT_DIR`) |
| **Kecepatan Kompilasi** | Sangat Cepat (In-compiler parsing) | Lambat (Harus compile crate macro terpisah lebih dulu) | Cepat hingga Sedang (Overhead monomorphization) | Paling Lambat (Kompilasi dan eksekusi binary biner) |
| **Kurva Pembelajaran** | Menengah (Sintaks unik regex-like) | Tinggi (Membutuhkan pemahaman AST, `syn`, `quote`) | Rendah hingga Menengah | Rendah (Menulis kode standar Rust imperatif) |
| **Debugging Complexity** | Sulit (Ekspansi trace terbatas) | Sangat Sulit (Runtime macro terjadi saat compile-time) | Mudah (Compiler error pesan tipe sangat eksplisit) | Mudah (Standard debug printing/file inspection) |
| **Hygiene Isolation** | Otomatis untuk Identifiers | Manual (Harus hati-hati mendefinisikan `Span`) | Sepenuhnya Absolut (Dibatasi scope Rust murni) | Nihil (Raw string generation) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Follow-set Ambiguity Restrictions
Dalam `macro_rules!`, setelah matcher seperti `$e:expr` tidak semua karakter diizinkan mengikutinya. Rust menerapkan batasan *Follow-Set* untuk menjaga agar parser dapat beroperasi secara deterministik tanpa melihat arbitrary lookahead tokens:
*   Setelah `$e:expr`, token yang diizinkan mengikutinya **hanya**: `=>`, `,`, atau `;`.
*   Jika Anda mencoba mendeklarasikan: `($e:expr $i:ident)` -> Kompiler akan melempar fatal error: `error: `$e:expr` is followed by `$i:ident`, which is not allowed for `expr` fragments`.

### 2. Recursion Limit Exhaustion
Ekspansi makro rekursif memiliki default ceiling limit (biasanya 128 rekursi) untuk mencegah kompiler crash akibat infinite loop:
```rust
#![recursion_limit = "256"] // Solusi jika ekspansi TT-muncher Anda sah membutuhkan kedalaman lebih
```

### 3. Span Pollution pada Procedural Macros
Saat menggunakan `syn` dan `quote`, jika Anda membuat token baru menggunakan `proc_macro2::Span::call_site()`, error compiler akan mengarah ke lokasi pemanggilan makro, bukan ke field yang bermasalah.
*Mitigasi:* Selalu kaitkan identifier baru dengan `field.span()` dari field aslinya agar pesan kesalahan compiler menunjuk persis pada baris definisi sumber data.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mengabaikan Parentheses pada Evaluasi Math
```rust
// SALAH:
macro_rules! mul {
    ($a:expr, $b:expr) => { $a * $b };
}
// Panggilan: mul!(1 + 2, 3 + 4) => 1 + 2 * 3 + 4 = 11 (Bukan 21)

// BENAR:
macro_rules! mul {
    ($a:expr, $b:expr) => { ($a) * ($b) };
}
```

### 2. Namespace Collision pada Import Helper Function
```rust
// SALAH:
macro_rules! log_data {
    ($val:expr) => {
        log_internal($val); // Gagal jika fungsi log_internal tidak diimpor di file pemanggil!
    };
}

// BENAR:
macro_rules! log_data {
    ($val:expr) => {
        $crate::__private::log_internal($val); // Resolusi mutlak via internal export
    };
}
```

### 3. Menggunakan `macro_rules!` Ketika Trait / Generics Cukup
Banyak developer pemula menggunakan macro untuk membuat polymorphism semu yang sebenarnya dapat diselesaikan jauh lebih bersih, aman, dan terbaca menggunakan generic standard function:
```rust
// ANTI-PATTERN:
macro_rules! print_len {
    ($item:expr) => { println!("{}", $item.len()); };
}

// IDIOMATIC RUST:
fn print_len<T: ExactSizeIterator>(item: &T) {
    println!("{}", item.len());
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Pola Extension Trait:** Buat traits publik di runtime crate, implementasikan traits tersebut via derive macro, jangan pernah meng-inject arbitrary method langsung ke struct tanpa abstraction contract.
2.  **Double-crate Pattern:** Saat mempublikasikan procedural macro, struktur crate standar industri adalah:
    *   `my_library_core`: Berisi trait definisi, tipe data runtime, dan re-exports.
    *   `my_library_macros`: Crate tipe `proc-macro = true` murni.
    *   `my_library`: Re-export macro dari `my_library_macros` dan tipe dari `my_library_core`.
3.  **Fail-Fast dengan `compile_error!`:** Jangan biarkan procedural macro panik (`panic!`) tanpa konteks. Selalu konversi parsing error menjadi:
    ```rust
    syn::Error::new(span, "Deskripsi error spesifik").to_compile_error()
    ```
    Ini merender pesan kesalahan native rustc yang elegan dengan penanda visual merah pada baris kode yang rusak.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Memangkas Waktu Kompilasi via Crate Features `syn`
Library `syn` berukuran sangat besar. Mengimpor seluruh fitur default akan memperlambat kompilasi dependensi hingga berkali lipat.
```toml
# BURUK (Mengompilasi seluruh parser Rust):
syn = { version = "2.0", features = ["full"] }

# OPTIMAL (Hanya parsing derive dan data structures):
syn = { version = "2.0", default-features = false, features = ["derive", "parsing", "printing", "clone-impls"] }
```

### 2. Runtime Inlining & Codegen Explosion
Hindari membuat blok instruksi berulang yang masif di dalam transcriber loop makro. Delegasikan isi loop ke *generic monomorphic helper functions* untuk menghindari membengkaknya ukuran file binary (*code bloat*).

```rust
// HINDARI: Menghasilkan 500 baris logika yang sama untuk 50 field
quote! {
    #(
        // 10 baris parsing logika kompleks diulang di sini untuk tiap field
    )*
}

// SARAN: Delegasikan ke fungsi runtime umum
quote! {
    #(
        $crate::__private::validate_bounds(&self.#field_names, #mins, #maxs)?;
    )*
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Arbitrary Code Execution saat Build Time
Procedural Macros dieksekusi di host machine developer/CI server. Ini berarti macro memiliki hak akses sistem operasi penuh (membaca file, network access, environment variables).
*Hardening Guideline:*
*   Jangan pernah membaca environment variables sensitif secara implisit di dalam macro tanpa deklarasi eksplisit.
*   Gunakan alat auditing seperti `cargo-geiger` dan `cargo-vet` untuk memverifikasi supply-chain dependency crate procedural macro.

### 2. Path Injection Protection
Jika macro mengizinkan path konfigurasi dinamis (misal: memuat schema SQL file `sql_query!("path/to/schema.sql")`), validasi bahwa path tersebut tidak keluar dari root crate directory (`../`) untuk menghindari Arbitrary File Read vulnerability pada sistem build.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk melihat hasil ekspansi makro dan mendiagnosis kesalahan tokenisasi, gunakan toolchain resmi berikut:

### 1. Tooling `cargo-expand`
Instalasi:
```bash
cargo install cargo-expand
```
Eksekusi inspeksi ekspansi:
```bash
# Menampilkan seluruh ekspansi AST dari file main.rs
cargo expand

# Menampilkan ekspansi modul tertentu
cargo expand tests::test_typed_map_construction
```

### 2. Built-in rustc Compiler Flags
Jika tidak dapat menginstal tool eksternal, gunakan flag unstable compiler:
```bash
cargo rustc -- -Z unpretty=expanded
```

### 3. Debugging TokenStream pada Procedural Macro
Cetak langsung representasi visual token ke konsol saat kompilasi berjalan:
```rust
#[proc_macro_derive(MyMacro)]
pub fn derive(input: TokenStream) -> TokenStream {
    eprintln!("TOKENS INPUT:\n{:#?}", input);
    // ...
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Macro Fragment Specifiers Quick Reference
*   `$x:ident` $\to$ Identifier (`my_var`, `UserStruct`).
*   `$x:expr` $\to$ Ekspresi matematika/logika (`1 + 1`, `compute()`).
*   `$x:ty` $\to$ Tipe data (`String`, `i32`, `Option<T>`).
*   `$x:path` $\to$ Module/Type path (`std::sync::Arc`).
*   `$x:stmt` $\to$ Statement (`let a = 10;`).
*   `$x:block` $\to$ Scope block (`{ let z = 10; z * 2 }`).
*   `$x:literal` $\to$ Constant literal (`"hello"`, `100`, `0.5`).
*   `$x:pat` $\to$ Pattern matching arm (`Some(val)`, `(x, y)`).
*   `$x:tt` $\to$ Single Token Tree.

### Procedural Macro Matrix
*   **Derive:** Digunakan untuk augmentasi traits bawaan/kustom pada Struct/Enum.
*   **Attribute:** Menggantikan atau membungkus item (fungsi, struct, module) secara mutlak.
*   **Function-like:** Menghasilkan kode arbitrary dari input custom syntax domain-specific language (DSL).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1.  **Pada fase kompilasi manakah makro diekspansi oleh compiler rustc?**
    *   A. Setelah type checking dan borrow check.
    *   B. Setelah tokenization/lexing dan sebelum analisis semantik/type checking.
    *   C. Bersamaan dengan pembuatan kode mesin oleh LLVM.
    *   D. Sebelum tokenization berjalan (pada raw source text).
    *   *Jawaban yang benar: B. Makro beroperasi pada TokenStream/AST sebelum type checking.*

2.  **Apa fungsi dari keyword `$crate` dalam deklarasi `macro_rules!`?**
    *   A. Mengalokasikan memori heap untuk variabel makro.
    *   B. Mengakses root crate tempat konsumen memanggil makro.
    *   C. Menyediakan path absolut ke crate yang mendefinisikan makro tersebut agar import aman secara higienis.
    *   D. Mencegah makro berekspansi lebih dari satu kali.
    *   *Jawaban yang benar: C.*

3.  **Mengapa Procedural Macro harus selalu didefinisikan dalam crate terpisah dengan tipe `proc-macro = true`?**
    *   A. Karena proc macro harus dikompilasi ke target arsitektur host compiler, bukan target akhir program.
    *   B. Karena aturan sistem file Rust melarang penggabungan file struct dan macro.
    *   C. Agar ukuran binary aplikasi utama mengecil secara otomatis.
    *   D. Untuk menghindari konflik memori thread-safe.
    *   *Jawaban yang benar: A. Proc macro adalah plugin host compiler yang dieksekusi saat proses kompilasi host.*

4.  **Desainator matcher mana yang mencocokkan sembarang token tunggal atau blok berkurung utuh?**
    *   A. `$x:ident`
    *   B. `$x:meta`
    *   C. `$x:tt`
    *   D. `$x:literal`
    *   *Jawaban yang benar: C.*

5.  **Simbol repetisi apa yang digunakan dalam `macro_rules!` jika elemen tersebut boleh muncul 0 kali atau tidak terbatas?**
    *   A. `?`
    *   B. `+`
    *   C. `*`
    *   D. `#`
    *   *Jawaban yang benar: C.*

---

### Soal Tingkat Lanjutan (Intermediate)

6.  **Apa yang terjadi jika Anda memetakan matcher `$e:expr` yang langsung diikuti oleh tanda kurung kurawal `{` tanpa separator yang valid dalam `macro_rules!`?**
    *   A. Kompiler otomatis menambahkan tanda titik koma.
    *   B. Kompiler mengeluarkan compile error pelanggaran follow-set ambiguity rules.
    *   C. Macro berhasil diekspansi tanpa peringatan.
    *   D. Program mengalami panic saat runtime.
    *   *Jawaban yang benar: B.*

7.  **Apa konsekuensi teknis dari penggunaan `Span::call_site()` saat men-generate identifier baru pada procedural macro jika terjadi error sintaksis?**
    *   A. Kompiler akan menunjuk compiler error ke definisi macro di library, bukan ke file pengguna.
    *   B. Kompiler akan memetakan error context ke lokasi di mana macro dipanggil, bukan ke spesifik field/elemen penyebabnya.
    *   C. Error syntax akan diabaikan dan berubah menjadi runtime exception.
    *   D. Kecepatan kompilasi meningkat secara drastis.
    *   *Jawaban yang benar: B.*

8.  **Apa perbedaan mendasar antara hygiene `macro_rules!` dan hygiene Procedural Macro?**
    *   A. Procedural macro sepenuhnya higienis secara default terhadap seluruh type.
    *   B. `macro_rules!` memiliki hygiene otomatis untuk local identifiers, sedangkan Procedural Macro memerlukan manipulasi explicit `Span` untuk mengatur hygiene context.
    *   C. `macro_rules!` tidak mendukung hygiene sama sekali.
    *   D. Keduanya sama-sama unhygienic seperti C-Preprocessor.
    *   *Jawaban yang benar: B.*

9.  **Di bawah kondisi apa compiler Rust akan menghentikan evaluasi declarative macro dengan error `recursion limit reached`?**
    *   A. Ketika memory RAM compiler melebihi batas sistem operasi.
    *   B. Ketika kedalaman pemanggilan rekursif makro melebihi batas (default 128) tanpa mencapai basis terminasi.
    *   C. Ketika makro dipanggil di dalam thread asynchronous.
    *   D. Ketika makro menghasilkan tipe data yang tidak mengimplementasikan trait `Copy`.
    *   *Jawaban yang benar: B.*

10. **Bagaimana cara paling idiomatik untuk mengembalikan multiple compiler errors dari sebuah Procedural Macro menggunakan crate `syn`?**
    *   A. Menggunakan `panic!("error 1\nerror 2")`.
    *   B. Mengakumulasi instance `syn::Error`, menggabungkannya via `.combine()`, lalu memanggil `.to_compile_error()`.
    *   C. Mengembalikan `TokenStream::new()` kosong.
    *   D. Menulis log error langsung ke file `target/error.log`.
    *   *Jawaban yang benar: B.*

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek:
Rancang dan implementasikan sebuah Procedural Macro bertipe Attribute: `#[timed_execution]` yang dapat disematkan di atas sembarang fungsi asynchronous maupun synchronous.

### Spesifikasi Kebutuhan Teknis:
1.  **Crate Setup:** Buat Cargo workspace dengan dua crate: `perf_tracker` (runtime) dan `perf_tracker_macros` (proc-macro).
2.  **Macro Behavior:**
    *   Macro harus mengukur durasi eksekusi fungsi menggunakan `std::time::Instant`.
    *   Mencetak nama fungsi, argumen identifikasi (jika ada), dan durasi eksekusi dalam mikrodetik (`µs`) atau milidetik (`ms`) ke `stdout` atau logger tracing.
    *   Harus mempertahankan integritas *return type* dari fungsi asli secara transparan tanpa merusak flow control (`Result`, `Option`, atau tipe data primitif).
    *   Dapat menangani fungsi synchronous (`fn`) dan fungsi asynchronous (`async fn`).

### Kode Uji Konsumsi yang Harus Didukung:
```rust
#[timed_execution]
fn compute_heavy_task(iterations: u64) -> u64 {
    let mut sum = 0;
    for i in 0..iterations {
        sum = sum.wrapping_add(i);
    }
    sum
}

#[timed_execution]
async fn fetch_remote_resource() -> Result<String, ()> {
    // Simulasi delay async
    tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
    Ok("Data Stream".to_string())
}
```

### Kriteria Kelulusan:
1.  Kompilasi sukses tanpa error menggunakan `cargo check` dan `cargo test`.
2.  Hasil output runtime menunjukkan jejak durasi eksekusi saat fungsi dijalankan.
3.  Implementasi menggunakan crate `syn`, `quote`, dan menangani preserve visibility (`pub`, `pub(crate)`), function signature, dan doc comments.