# Kurikulum Enterprise Rust: BAB-07 Metaprogramming & Macro System
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** alur kerja internal *compiler pipeline* `rustc` selama fase *macro expansion*, khususnya interaksi antara *compiler driver*, AST (*Abstract Syntax Tree*), dan dynamic library makro prosedural.
- **Merancang dan mengimplementasikan** tiga varian *Procedural Macros* (*Custom Derive*, *Attribute-like*, dan *Function-like*) tingkat lanjut menggunakan `syn`, `quote`, dan `proc-macro2` dengan arsitektur modular.
- **Mengelola** *span hygiene* dan menghasilkan pesan kesalahan kompilasi (*compile-time diagnostics*) yang presisi menggunakan `syn::Error` dan `compile_error!`.
- **Mengeliminasi** kebutuhan *runtime reflection* pada arsitektur microservices performa tinggi dengan memindahkan komputasi validasi dan serialisasi ke fase kompilasi (*zero runtime overhead*).
- **Mengoptimalkan** metrik *build time* dan mitigasi dampak bloat biner akibat ekspansi makro pada monorepo skala enterprise.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi fondasional berikut:
- Pemahaman mendalam tentang *trait system*, *generics*, *associated types*, dan *lifetime elision* di Rust.
- Penguasaan dasar *Declarative Macros* (`macro_rules!`) serta pemahaman konsep *Pattern Matching* dan *Token Trees*.
- Pemahaman arsitektur manajemen proyek multi-crate (*Cargo Workspaces*).
- Konsep dasar teori kompilasi: *Lexical Analysis* (Lexing), *Syntactic Analysis* (Parsing), dan representasi pohon sintaksis (*AST/HIR/MIR*).

---

### 3. Concept & Internal Architecture

#### 3.1 Kompilasi Rust & Posisi Procedural Macro
Procedural Macro di Rust pada dasarnya adalah *compiler plugin* resmi. Crate makro prosedural tidak dikompilasi untuk arsitektur target aplikasi runtime, melainkan dikompilasi ke format *dynamic library* (`dylib`/`so`/`dll`) untuk mesin *host* tempat kompilator berjalan.

```
+-------------------------------------------------------------------------+
|                              rustc Frontend                             |
+-------------------------------------------------------------------------+
   | (Source Code .rs)
   v
[Lexer] --------> TokenStream (host: raw tokens)
                    |
                    v
[Parser] -------> AST (Abstract Syntax Tree)
                    |
                    v
          +-------------------+
          | Expansion Engine  |<====== Dynamic Link / RPC ======> [Proc Macro dylib]
          +-------------------+                                    (syn -> AST)
                    |                                              (Transformation)
                    | (Expanded AST)                               (quote -> TokenStream)
                    v
[Type Checking] -> HIR (High-Level Intermediate Representation)
                    |
                    v
[Borrow Checker] -> MIR (Mid-Level Intermediate Representation)
                    |
                    v
[LLVM Backend]  -> Machine Code (Target Executable / Library)
```

Ketika `rustc` mendeteksi atribut makro (misal: `#[derive(MyMacro)]` atau `#[my_attribute]`), proses berikut terjadi:
1. Kompilator menghentikan pemrosesan linear AST.
2. Token yang diasosiasikan dengan target diubah menjadi `proc_macro::TokenStream`.
3. Kompilator mengeksekusi fungsi makro di dalam *proc-macro dylib* yang telah di-*load* ke memori kompilator.
4. Fungsi makro menerima `TokenStream`, memanipulasinya, dan mengembalikan `TokenStream` baru.
5. Kompilator mem-parsing kembali `TokenStream` hasil ekspansi tersebut ke dalam AST utama, lalu melanjutkan ke tahap *type-checking* dan *borrow-checking*.

#### 3.2 Ekosistem Trinitas Metaprogramming: `proc_macro`, `syn`, dan `quote`
- **`proc_macro`**: Crate primitif yang disediakan oleh kompilator Rust (`rustc`). Sangat terbatas dan terikat pada runtime kompilator. Tipe-tipenya tidak dapat digunakan di luar konteks eksekusi kompilasi aktif.
- **`proc_macro2`**: Abstraksi *mirror* dari `proc_macro`. Memungkinkan struktur data token dimanipulasi di luar konteks kompilator langsung (misalnya pada *unit test* standar atau integrasi non-compiler).
- **`syn`**: Parser berbasis *parser-combinator* yang mengubah `TokenStream` mentah menjadi struktur data AST Rust yang terstruktur (`syn::DeriveInput`, `syn::ItemFn`, `syn::ItemStruct`, dll.).
- **`quote`**: Alat *quasi-quoting* yang menyediakan makro `quote!` untuk mengonversi struktur data Rust kembali menjadi `TokenStream` melalui interpolasi sintaksis.

#### 3.3 Anatomi Span dan Macro Hygiene
*Hygiene* adalah jaminan kompilator bahwa pengidentifikasi (*identifier*) yang dideklarasikan di dalam makro tidak akan bentrok (*clash*) atau secara tidak sengaja membayangi (*shadow*) pengidentifikasi pada kode pemanggil, dan sebaliknya.
- **Declarative Macros (`macro_rules!`)**: Menerapkan *semi-hygienic scope*. Kompilator melacak asal identifier.
- **Procedural Macros**: Bersifat *unhygienic* secara default berdasarkan `Span::call_site()`. Jika makro menghasilkan variabel bernama `temp`, dan kode pengguna juga memiliki `temp`, konflik penamaan dapat terjadi jika tidak ditangani dengan benar.
- **Span Types**:
  - `Span::call_site()`: Mengikat konteks span ke lokasi di mana makro dipanggil. Pesan error akan mengarah ke baris kode pengguna.
  - `Span::def_site()`: Mengikat konteks ke definisi makro itu sendiri (masih eksperimental di beberapa API).
  - `Span::mixed_site()`: Higiene hibrida di mana variabel bersifat lokal terhadap makro, tetapi *items* dan *type names* dapat diakses secara global.

---

### 4. Why & What

| Paradigma | Implementasi (Java / Go / Node.js) | Implementasi Rust (Procedural Macros) |
| :--- | :--- | :--- |
| **Mekanisme** | Dynamic Reflection (Runtime inspection, class metadata). | Static Metaprogramming (AST manipulation at compile-time). |
| **Runtime Cost** | Latensi tinggi, alokasi heap untuk metadata, lookup hashmap dinamis. | **Zero runtime cost**. Kode yang dihasilkan setara dengan kode yang ditulis manual. |
| **Error Detection** | Sering terjadi *runtime failure* (misal: `IllegalArgumentException` saat startup). | **Compile-time failure**. Error langsung menghentikan proses *build*. |
| **Binary Size** | Relatif stabil, runtime metadata disimpan terpisah. | Berpotensi terjadi *binary bloat* jika fungsi duplikasi di-inline secara masif. |
| **Safety** | Rentan bypass type-system (type casting, `Object` / `interface{}`). | Type safety penuh, melewati borrow-checker dan type-system secara utuh. |

**Kapan Menggunakan Procedural Macros?**
- Mengurangi *boilerplate* repetitif yang tidak dapat ditangani oleh generics atau declarative macros (misal: serialisasi khusus, implementasi protokol RPC, validasi skema database).
- Membangun antarmuka deklaratif untuk arsitektur enterprise (misal: dependency injection compile-time, tracing spans, circuit-breaker injection).

**Kapan Menghindari Procedural Macros?**
- Operasi logika yang dapat diselesaikan menggunakan Generic Functions, Trait composition, atau Declarative Macros.
- Proyek dengan dependensi minim di mana peningkatan *compile time* tidak dapat ditoleransi.

---

### 5. How (Workflow Detail)

Arsitektur crate wajib dipisahkan menjadi minimal dua crate karena batasan fundamental Rust: **sebuah crate tidak dapat sekaligus menjadi pendefinisi proc-macro dan konsumennya**.

#### Arsitektur Workspace
```
enterprise-core/
├── Cargo.toml (Workspace Root)
├── core-lib/
│   ├── Cargo.toml (Consumer/Runtime logic)
│   └── src/lib.rs
└── core-macros/
    ├── Cargo.toml (proc-macro = true)
    └── src/lib.rs
```

#### Alur Eksekusi Procedural Macro:
1. **Definisi Manifestasi**: Tandai crate sebagai penyedia makro di `core-macros/Cargo.toml`:
   ```toml
   [lib]
   proc-macro = true
   ```
2. **Parsing**: Menerima `TokenStream` dan mem-parsing ke `syn::DeriveInput` atau `syn::Item`.
3. **Analisis Semantik**: Menelusuri fields, attributes (`#[...]`), dan types dari AST.
4. **Validasi**: Memeriksa invarian arsitektur (misal: memastikan field memiliki atribut tertentu). Jika gagal, lemparkan `syn::Error`.
5. **Codegen (Sintesis)**: Menghasilkan kode Rust menggunakan `quote!`.
6. **Emisi**: Mengembalikan `TokenStream` yang kompatibel dengan kompilator.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Mesin CNC Industri
Bayangkan Procedural Macro sebagai **Mesin CNC Presisi Otomatis**:
- **Source Code (AST)** adalah *Cetak Biru (Blueprint)* yang digambar oleh software engineer.
- **`syn`** adalah *Scanner Digital* yang membaca cetak biru tersebut menjadi instruksi terstruktur untuk mesin.
- **Logika Macro** adalah *Program Komputer CNC* yang memvalidasi apakah cetak biru memenuhi standar struktural bangunan.
- **`quote`** adalah *Mata Bor dan Pemotong Laser* yang memotong baja mentah secara instan menjadi suku cadang fungsional (*Expanded Code*).
- Tidak ada runtime overhead: ketika mesin CNC selesai bekerja, yang dikirim ke pelanggan adalah baja kokoh yang sudah jadi, bukan mesin CNC-nya.

#### Diagram Interaksi Data Kompilator
```
[User Struct Definition]
       |
       | raw tokens
       v
+--------------------------------------------------------------+
| core-macros (dylib executed by rustc)                        |
|                                                              |
|  +--------------------+                                      |
|  | syn::parse2(...)   |                                      |
|  +--------------------+                                      |
|            |                                                 |
|            v (syn::DeriveInput AST)                          |
|  +--------------------+                                      |
|  | AST Traversal      |                                      |
|  | Extract Attributes |                                      |
|  | Type Validation    |                                      |
|  +--------------------+                                      |
|            |                                                 |
|            v (Target Metadata)                               |
|  +--------------------+                                      |
|  | quote! { ... }     |                                      |
|  +--------------------+                                      |
|            |                                                 |
|            v (proc_macro2::TokenStream)                      |
+--------------------------------------------------------------+
       |
       | tokens converted to proc_macro::TokenStream
       v
[Integrated into Primary AST]
       |
       v
[Borrow Checker & LLVM Codegen]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Custom Derive `InspectFields`
Implementasi macro derive yang mencetak daftar nama field dari sebuah `struct` saat kompilasi.

**`core-macros/src/lib.rs`**:
```rust
use proc_macro::TokenStream;
use quote::quote;
use syn::{parse_macro_input, Data, DeriveInput, Fields};

#[proc_macro_derive(InspectFields)]
pub fn derive_inspect_fields(input: TokenStream)::TokenStream {
    // 1. Parse input menjadi AST
    let input = parse_macro_input!(input as DeriveInput);
    let struct_name = &input.ident;

    // 2. Ekstrak data field struct
    let field_names = match &input.data {
        Data::Struct(data_struct) => match &data_struct.fields {
            Fields::Named(fields_named) => {
                fields_named.named.iter().map(|f| {
                    let ident = &f.ident;
                    quote! { stringify!(#ident) }
                }).collect::<Vec<_>>()
            }
            Fields::Unnamed(_) | Fields::Unit => {
                return syn::Error::new_spanned(
                    struct_name,
                    "InspectFields hanya mendukung struct dengan named fields",
                )
                .to_compile_error()
                .into();
            }
        },
        _ => {
            return syn::Error::new_spanned(
                struct_name,
                "InspectFields hanya mendukung Struct, bukan Enum/Union",
            )
            .to_compile_error()
            .into();
        }
    };

    // 3. Sintesis kode implementasi
    let expanded = quote! {
        impl #struct_name {
            pub fn field_names() -> &'static [&'static str] {
                &[#(#field_names),*]
            }
        }
    };

    // 4. Konversi kembali ke proc_macro::TokenStream
    TokenStream::from(expanded)
}
```

---

#### 7.2 Practical Example: Enterprise Audit Logging Attribute Macro
Attribute macro `#[audit_trace]` yang menyuntikkan instrumentasi logging mikrodetik ke dalam fungsi asynchronous, mengekstrak argumen pemanggilan, dan menangani propagasi `Result`.

**`core-macros/src/lib.rs`**:
```rust
use proc_macro::TokenStream;
use quote::quote;
use syn::{parse_macro_input, ItemFn, ReturnType};

#[proc_macro_attribute]
pub fn audit_trace(_attr: TokenStream, item: TokenStream) -> TokenStream {
    let input_fn = parse_macro_input!(item as ItemFn);
    
    let fn_vis = &input_fn.vis;
    let fn_sig = &input_fn.sig;
    let fn_ident = &fn_sig.ident;
    let fn_args = &fn_sig.inputs;
    let fn_output = &fn_sig.output;
    let fn_block = &input_fn.block;
    let fn_generics = &fn_sig.generics;
    let (impl_generics, ty_generics, where_clause) = fn_generics.split_for_impl();

    let fn_name_str = fn_ident.to_string();

    // Validasi apakah fungsi async
    if fn_sig.asyncness.is_none() {
        return syn::Error::new_spanned(
            fn_sig.fn_token,
            "Attribute #[audit_trace] hanya dapat diaplikasikan pada fungsi asynchronous (`async fn`)",
        )
        .to_compile_error()
        .into();
    }

    let expanded = quote! {
        #fn_vis #fn_sig {
            let __audit_start_instant = ::std::time::Instant::now();
            let __audit_fn_name = #fn_name_str;
            
            ::log::info!(
                target: "enterprise::audit", 
                "[AUDIT_START] Invoking: {}", 
                __audit_fn_name
            );

            // Eksekusi body asli fungsi di dalam closure async
            let __result_future = async move #fn_block;
            let __result = __result_future.await;

            let __audit_duration = __audit_start_instant.elapsed();
            
            ::log::info!(
                target: "enterprise::audit", 
                "[AUDIT_END] Completed: {} in {} microseconds", 
                __audit_fn_name, 
                __audit_duration.as_micros()
            );

            __result
        }
    };

    TokenStream::from(expanded)
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: High-Throughput Financial Ledger Event Engine
Sebuah platform perbankan digital memproses jutaan transaksi per detik menggunakan Kafka. Setiap event transaksi wajib memenuhi kriteria:
1. Memiliki skema invariant yang divalidasi saat kompilasi.
2. Membaca metadata enkripsi dari field attribute.
3. Menghasilkan implementasi deserialisasi zero-copy biner kustom untuk mengeliminasi beban CPU akibat parsing JSON/Protobuf runtime generic.

#### Desain Solusi: Custom Derive `LedgerPayload` dengan Helper Attributes
Arsitektur makro membaca atribut field seperti `#[ledger(encrypted)]` dan `#[ledger(max_value = 1_000_000)]`, memvalidasi limit secara statis pada fase kompilasi, dan meng-generate parser biner deterministik.

```
       Source Code with DSL Attributes
                     |
                     v
   +------------------------------------+
   |  #[derive(LedgerPayload)]          |
   |  struct SettlementEvent {          |
   |      #[ledger(encrypted)]          |
   |      account_id: [u8; 32],         |
   |      #[ledger(max_val = 500_000)]  |
   |      amount_cents: u64,            |
   |  }                                 |
   +------------------------------------+
                     |
       (Compile-Time Macro Processing)
                     |
        +------------+------------+
        |                         |
        v                         v
 [Static AST Checker]    [Byte-Blit Serializer Engine]
 (Reject if max_val < 0) (Emit unsafe fast memory casting code)
        |                         |
        +------------+------------+
                     |
                     v
        Zero-Cost Native Binary Code
```

#### Implementasi Production-Grade Crate Macro:

**`ledger-macros/src/lib.rs`**:
```rust
use proc_macro::TokenStream;
use quote::quote;
use syn::{
    parse_macro_input, Data, DeriveInput, Error, Fields, LitInt, Meta, NestedMeta,
};

#[proc_macro_derive(LedgerPayload, attributes(ledger))]
pub fn derive_ledger_payload(input: TokenStream) -> TokenStream {
    let input = parse_macro_input!(input as DeriveInput);
    let name = &input.ident;

    let fields = match &input.data {
        Data::Struct(data_struct) => match &data_struct.fields {
            Fields::Named(fields_named) => &fields_named.named,
            _ => {
                return Error::new_spanned(
                    name,
                    "LedgerPayload hanya mendukung struct dengan named fields",
                )
                .to_compile_error()
                .into();
            }
        },
        _ => {
            return Error::new_spanned(name, "Hanya struct yang didukung")
                .to_compile_error()
                .into();
        }
    };

    let mut validation_statements = Vec::new();
    let mut field_names = Vec::new();

    for field in fields {
        let field_ident = field.ident.as_ref().unwrap();
        field_names.push(field_ident);

        // Parsing inner attribute: #[ledger(...)]
        for attr in &field.attrs {
            if attr.path.is_ident("ledger") {
                let meta = match attr.parse_meta() {
                    Ok(m) => m,
                    Err(e) => return e.to_compile_error().into(),
                };

                if let Meta::List(meta_list) = meta {
                    for nested in meta_list.nested {
                        if let NestedMeta::Meta(Meta::NameValue(nv)) = nested {
                            if nv.path.is_ident("max_val") {
                                if let syn::Lit::Int(lit_int) = &nv.lit {
                                    let max_val: u64 = match lit_int.base10_parse() {
                                        Ok(val) => val,
                                        Err(err) => return err.to_compile_error().into(),
                                    };

                                    // Suntikkan validasi run-time statis
                                    validation_statements.push(quote! {
                                        if self.#field_ident > #max_val {
                                            return ::core::result::Result::Err(
                                                "Field value exceeds compile-time max_val ceiling"
                                            );
                                        }
                                    });
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    let expanded = quote! {
        impl #name {
            #[inline(always)]
            pub fn validate_schema(&self) -> ::core::result::Result<(), &'static str> {
                #(#validation_statements)*
                ::core::result::Result::Ok(())
            }
        }
    };

    TokenStream::from(expanded)
}
```

---

### 9. Trade-offs

| Dimensi | Keuntungan Metaprogramming (Macro) | Biaya / Kerugian Metaprogramming |
| :--- | :--- | :--- |
| **Performance** | Maksimal. Menghilangkan layer dispatch dinamis, alokasi memori runtime, dan overhead abstraksi. | Tidak berdampak negatif pada performa binary runtime. |
| **Latency** | Sangat rendah. Jalur eksekusi langsung dapat di-inline oleh LLVM. | Compile-time latency melonjak drastis. Parsing AST dengan `syn` memerlukan alokasi banyak node di heap. |
| **Scalability** | Skalabilitas kode terjaga: jutaan line boilerplate dapat diabstraksi dengan 5 baris deklarasi atribut. | Skalabilitas CI/CD terancam: build pipeline memakan waktu lebih lama seiring meningkatnya penggunaan macro. |
| **Cost** | Menghemat biaya resource server runtime (CPU/RAM lebih efisien). | Meningkatkan kebutuhan resource mesin CI worker (CPU core dan RAM tinggi untuk kompilasi). |
| **Maintainability**| Mencegah duplikasi human error dalam repetisi kode transaksi/protokol. | Kurva belajar tim curam. Debugging AST macro memerlukan keahlian mendalam (`cargo-expand`). |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Emisi Identifier Tanpa Absolute Path Qualified
- **Penyebab**: Menghasilkan kode dengan tipe standar seperti `Result`, `Ok`, `Option` secara langsung (`quote! { Result<(), Error> }`). Jika pemanggil macro meng-override `type Result = CustomResult`, kode kompilasi akan rusak.
- **Solusi**: Selalu gunakan absolute canonical paths yang berakar pada `::core` atau `::std`:
  ```rust
  // BENAR:
  quote! { ::core::result::Result<(), ::core::fmt::Error> }
  ```

#### Kasus 2: Span Error yang Menunjuk ke Seluruh Struct, Bukan ke Token Spesifik
- **Penyebab**: Memakai `ident` dari struct utama untuk pelaporan error field parsial. Engineer pemanggil akan kesulitan menemukan field mana yang menyebabkan kerusakan pada struct berisi 100 field.
- **Solusi**: Gunakan `syn::Error::new_spanned(field_token, "pesan spesifik")` langsung pada field atau attribute terkait.

#### Kasus 3: Panicking di Dalam Macro Logic
- **Penyebab**: Memanggil `.unwrap()` atau `.expect()` saat parsing AST token di dalam proc-macro. Hal ini menyebabkan kompilator panik (*internal compiler error/ICE*) dengan stack trace jelek tanpa konteks file/line number pengguna.
- **Solusi**: Ubah error parsing menjadi `syn::Error::into_compile_error()` dan kembalikan ke kompilator sebagai TokenStream:
  ```rust
  let lit_int: LitInt = match syn::parse2(stream) {
      Ok(val) => val,
      Err(err) => return err.to_compile_error().into(),
  };
  ```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Isolated Crate Structure**: Pisahkan macro crate secara tegas dengan sufiks `-macros` atau `-derive`. Jangan gabungkan runtime logic ke dalam macro crate.
2. [ ] **Double Workspace Dependency Pattern**: Re-export macro dari runtime crate agar pengguna hanya perlu mengimpor satu crate dependen.
3. [ ] **Explicit Fully-Qualified Paths**: Seluruh referensi tipe bawaan Rust wajib menggunakan `::core::*` atau `::alloc::*` (kompatibel dengan `#![no_std]`).
4. [ ] **Avoid Heavy Build Dependencies in Macros**: Jaga dependensi `core-macros` seminimal mungkin (idealnya hanya `syn`, `quote`, `proc-macro2`). Hindari dependensi jaringan atau parser besar yang memperlambat kompilasi.
5. [ ] **Automated Expansion Testing**: Selalu sediakan test suite menggunakan `trybuild` untuk memverifikasi bahwa kode salah menghasilkan *compile error* yang sesuai harapan, dan kode valid dapat dikompilasi.
6. [ ] **Zero Unsafe Generation**: Hindari menghasilkan blok `unsafe` melalui makro kecuali didokumentasikan secara ketat dan invariant keselamatan diverifikasi oleh compiler assertion.

---

### 12. Hands-on Practice

Ikuti langkah-langkah praktikum berikut untuk membangun framework mini derive validation enterprise. Seluruh implementasi disimpan di direktori `hands-on/m02/`.

#### Langkah 1: Siapkan Cargo Workspace
Buat struktur direktori:
```bash
mkdir -p hands-on/m02/macro-workspace
cd hands-on/m02/macro-workspace
```

Buat file root `Cargo.toml`:
```toml
[workspace]
members = [
    "enterprise-validator",
    "enterprise-validator-derive",
]
resolver = "2"
```

#### Langkah 2: Buat Macro Derive Crate
```bash
cargo new --lib enterprise-validator-derive
```
Konfigurasi `enterprise-validator-derive/Cargo.toml`:
```toml
[package]
name = "enterprise-validator-derive"
version = "0.1.0"
edition = "2021"

[lib]
proc-macro = true

[dependencies]
proc-macro2 = "1.0"
quote = "1.0"
syn = { version = "2.0", features = ["full", "extra-traits"] }
```

Tulis logika makro pada `enterprise-validator-derive/src/lib.rs`:
```rust
use proc_macro::TokenStream;
use quote::quote;
use syn::{parse_macro_input, Data, DeriveInput, Error, Fields, LitInt, Meta, NestedMeta};

#[proc_macro_derive(Validator, attributes(validate))]
pub fn derive_validator(input: TokenStream) -> TokenStream {
    let input = parse_macro_input!(input as DeriveInput);
    let struct_name = &input.ident;

    let fields = match &input.data {
        Data::Struct(data_struct) => match &data_struct.fields {
            Fields::Named(f) => &f.named,
            _ => {
                return Error::new_spanned(struct_name, "Validator only supports named fields")
                    .to_compile_error()
                    .into()
            }
        },
        _ => {
            return Error::new_spanned(struct_name, "Validator only supports structs")
                .to_compile_error()
                .into()
        }
    };

    let mut checks = Vec::new();

    for field in fields {
        let field_name = &field.ident;

        for attr in &field.attrs {
            if attr.path.is_ident("validate") {
                let meta = match attr.parse_meta() {
                    Ok(m) => m,
                    Err(e) => return e.to_compile_error().into(),
                };

                if let Meta::List(list) = meta {
                    for item in list.nested {
                        if let NestedMeta::Meta(Meta::NameValue(nv)) = item {
                            if nv.path.is_ident("min") {
                                if let syn::Lit::Int(val) = nv.lit {
                                    let min_val: i64 = val.base10_parse().unwrap();
                                    checks.push(quote! {
                                        if (self.#field_name as i64) < #min_val {
                                            return ::core::result::Result::Err(
                                                concat!("Field ", stringify!(#field_name), " below threshold")
                                            );
                                        }
                                    });
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    let expanded = quote! {
        impl #struct_name {
            pub fn validate(&self) -> ::core::result::Result<(), &'static str> {
                #(#checks)*
                ::core::result::Result::Ok(())
            }
        }
    };

    TokenStream::from(expanded)
}
```

#### Langkah 3: Buat Core Runtime Consumer Crate
```bash
cargo new enterprise-validator
```
Konfigurasi `enterprise-validator/Cargo.toml`:
```toml
[package]
name = "enterprise-validator"
version = "0.1.0"
edition = "2021"

[dependencies]
enterprise-validator-derive = { path = "../enterprise-validator-derive" }
```

Implementasikan logika runtime di `enterprise-validator/src/main.rs`:
```rust
use enterprise_validator_derive::Validator;

#[derive(Debug, Validator)]
struct WorkerConfig {
    #[validate(min = 1)]
    concurrency: u32,
    #[validate(min = 100)]
    buffer_capacity: usize,
}

fn main() {
    let valid_cfg = WorkerConfig {
        concurrency: 4,
        buffer_capacity: 256,
    };
    assert!(valid_cfg.validate().is_ok());

    let invalid_cfg = WorkerConfig {
        concurrency: 0,
        buffer_capacity: 50,
    };
    let validation_result = invalid_cfg.validate();
    println!("Hasil Validasi Kasus Invalid: {:?}", validation_result);
    assert!(validation_result.is_err());
}
```

#### Langkah 4: Jalankan dan Analisis Ekspansi Makro
1. Jalankan aplikasi:
   ```bash
   cargo run -p enterprise-validator
   ```
2. Pasang tool inspeksi `cargo-expand` (jika belum ada):
   ```bash
   cargo install cargo-expand
   ```
3. Lakukan inspeksi kode hasil ekspansi kompilator:
   ```bash
   cargo expand -p enterprise-validator
   ```

---

### 13. Exercise

#### 13.1 Level Easy: Custom Derive `FieldCount`
- **Instruksi**: Buat macro derive `#[derive(FieldCount)]` yang menghasilkan konstanta asosiasi `pub const FIELD_COUNT: usize = N;` pada struct, di mana `N` adalah jumlah total field pada struct tersebut.
- **Kriteria**: Jika diaplikasikan pada struct kosong (unit struct), menghasilkan nilai 0. Jika diaplikasikan pada enum, kembalikan compile error.

#### 13.2 Level Medium: Attribute Macro `#[retry(attempts = 3)]`
- **Instruksi**: Buat attribute macro yang membungkus fungsi sinkron yang mengembalikan `Result<T, E>`. Macro harus menyuntikkan loop yang mengulang eksekusi fungsi sebanyak nilai `attempts` jika terjadi error.
- **Kriteria**: Nilai `attempts` harus divalidasi saat kompilasi. Jika `attempts == 0`, kompilasi harus dihentikan dengan pesan error: `"attempts must be greater than zero"`.

#### 13.3 Level Hard: Custom Derive `BinarySerialize` (No-std compatible)
- **Instruksi**: Implementasikan macro derive untuk serialisasi struct biner ke dalam byte-buffer (`[u8; N]`). Struct hanya berisi primitive types integer (`u8`, `u16`, `u32`, `u64`). Macro harus menghitung ukuran buffer total `N` saat kompilasi (`const SIZE: usize = ...`) dan menghasilkan metode `fn to_le_bytes(&self) -> [u8; Self::SIZE]`.
- **Kriteria**: Tidak boleh menggunakan alokasi heap (`Vec`). Jika terdapat field dengan tipe yang tidak dikenal, lempar span compile error tepat di posisi identifier tipe field tersebut.

---

### 14. Challenge

#### Skenario: Type-Safe Compile-Time Routing & Role-Based Access Control (RBAC) Generator
Anda ditugaskan oleh Chief Architect untuk membangun sub-sistem routing internal RPC performa tinggi pada enterprise banking engine.

**Spesifikasi Desain**:
1. Buat attribute-like macro `#[rpc_service(prefix = "/api/v1")]`.
2. Macro diaplikasikan pada sebuah `trait` Rust yang berisi definisi method async.
3. Tiap method pada trait memiliki attribute khusus: `#[route(path = "/transfer", method = "POST", roles("Admin", "Operator"))]`.
4. **Tuntutan Kompilasi**:
   - Macro harus secara otomatis menghasilkan:
     - Struct Server Dispatcher yang mengimplementasikan router routing deterministik berbasis static string matching (tanpa regex runtime).
     - Validasi statis: Parameter fungsi wajib mengimplementasikan trait `Send + Sync + 'static`.
     - Pengecekan authorization role: Macro menyuntikkan pengecekan metadata role sebelum memanggil fungsi handler sebenarnya.
   - Jika route path didaftarkan ganda (*duplicate path*) dalam trait yang sama, gagalkan kompilasi secara instan menggunakan `syn::Error` yang menunjuk tepat ke duplikasi route kedua.
   - Waktu kompilasi makro tidak boleh melebihi 2 detik pada target crate.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual)

1. **Mengapa crate yang mendefinisikan procedural macro wajib mendeklarasikan `proc-macro = true` di file `Cargo.toml`?**
   - A. Agar library dapat dibungkus sebagai binary WebAssembly runtime.
   - B. Menginstruksikan kompilator untuk mengompilasi crate tersebut sebagai dylib khusus host yang ditautkan ke kompilator `rustc`.
   - C. Mengaktifkan fitur unstable dari nightly compiler secara otomatis.
   - D. Menghilangkan ketergantungan pada libc sistem operasi target.

2. **Perbedaan mendasar antara `proc_macro::TokenStream` dan `proc_macro2::TokenStream` adalah:**
   - A. `proc_macro2` berjalan lebih lambat namun aman dari memory leak.
   - B. `proc_macro` adalah representasi native AST sedangkan `proc_macro2` adalah bytecode string.
   - C. `proc_macro` hanya hidup di dalam eksekusi kompilasi aktif `rustc`, sedangkan `proc_macro2` adalah abstraksi runtime-independent yang dapat digunakan pada unit testing reguler.
   - D. Tidak ada perbedaan, `proc_macro2` adalah alias usang dari `proc_macro`.

3. **Operasi interpolasi repetisi pada makro `quote!` dituliskan dengan sintaks:**
   - A. `$(#variable)*`
   - B. `#(#variable),*`
   - C. `for val in #variable { val }`
   - D. `@repeat(#variable)`

4. **Apa implikasi menggunakan `Span::call_site()` saat membuat error diagnostic menggunakan `syn::Error`?**
   - A. Error kompilasi akan menunjuk ke baris kode implementasi internal makro itu sendiri.
   - B. Error kompilasi akan diarahkan ke kode pengguna tempat makro tersebut dieksekusi atau dipanggil.
   - C. Kompilator menolak melaporkan error dan melakukan abort runtime.
   - D. Kompilator mengubah warning menjadi error fatal.

5. **Apa fungsi utama dari tipe `syn::DeriveInput`?**
   - A. Menampung AST lengkap dari tipe data (struct, enum, union) yang didekorasi oleh custom derive macro.
   - B. Menyimpan token mentah sebelum melalui proses tokenisasi.
   - C. Mengonversi bytecode intermediate LLVM ke syntax Rust.
   - D. Menjalankan garbage collection pada memory kompilator.

---

#### Bagian 2: Intermediate (Analisis Kasus Singkat)

6. **Diberikan potongan kode makro berikut:**
   ```rust
   let expanded = quote! {
       fn process() -> Result<(), String> {
           Ok(())
       }
   };
   ```
   **Mengapa kode di atas melanggar kaidah Enterprise Production Standard Rust Macro?**
   - Jawaban harus menjelaskan: Ketiadaan path qualification (`::core::result::Result`, `::std::string::String`) yang membuat kode rentan patah akibat shadowing identifier dari sisi pengguna.

7. **Bagaimana cara sebuah attribute procedural macro menghapus item yang didekorasinya agar item asli tidak pernah dikompilasi ke binary akhir?**
   - Jawaban harus menjelaskan: Makro cukup mengembalikan `TokenStream::new()` kosong tanpa memancarkan kembali item aslinya ke stream kompilasi.

8. **Mengapa pemanggilan method `.to_string()` pada `TokenStream` untuk manipulasi string mentah sangat tidak disarankan dibandingkan penelusuran AST berbasis `syn`?**
   - Jawaban harus menjelaskan: Kehilangan informasi *Span metadata* (posisi file, line number, hygiene context) yang membuat pesan error kompilator rusak dan membuka celah bug akibat parsing parsing string non-deterministik.

9. **Apa perbedaan antara helper attribute internal (`inert attribute`) dan attribute macro (`active attribute`)?**
   - Jawaban harus menjelaskan: Inert attributes (seperti `#[serde(...)]` atau `#[validate(...)]`) tidak dieksekusi sendiri oleh kompilator melainkan dikonsumsi oleh derive macro lain, sedangkan active attributes mentransformasi atau menggantikan item yang diatribusinya secara langsung.

10. **Bagaimana arsitektur memory proc macro terisolasi dari program target saat kompilasi *cross-compilation* (misal: Host x86_64 Linux, Target aarch64 Android)?**
    - Jawaban harus menjelaskan: Proc macro crate dikompilasi ke arsitektur Host (x86_64) dan berjalan pada proses host `rustc`, sedangkan emitted token-stream akan dikompilasi ulang oleh backend LLVM menuju target akhir (aarch64).

---

#### Bagian 3: Production Scenarios

11. **Skenario 1**: Sebuah tim enterprise mengeluhkan waktu kompilasi monorepo meningkat dari 2 menit menjadi 14 menit setelah memperkenalkan ratusan derive macro kustom. Setelah diteliti, ukuran binary proc-macro dylib mencapai 500MB.
    - *Tugas*: Rancang strategi optimasi kompilasi untuk memangkas *build latency* tersebut tanpa menghapus derive macro fungsional yang sudah berjalan.

12. **Skenario 2**: Anda menemukan bug di mana custom derive macro menghasilkan implementasi trait yang menyebabkan konflik (*conflicting implementations*) ketika dua tipe generik yang berbeda digunakan oleh client (`impl<T> MyTrait for T` vs `impl<T> MyTrait for Wrapper<T>`).
    - *Tugas*: Bagaimana Anda mendesain ulang arsitektur emisi token dari derive macro agar memanfaatkan *Autoref-based Specialization* atau *marker trait pattern* untuk mencegah tabrakan implementasi?

13. **Skenario 3**: Sebuah attribute macro `#[secure_actor]` menyuntikkan dependensi state mutabel global ke dalam sebuah struct. Ketika unit test dijalankan paralel (`cargo test`), terjadi data race sporadis saat runtime.
    - *Tugas*: Tunjukkan bagaimana macro seharusnya memanfaatkan compile-time validation untuk menegakkan bahwa semua field yang disuntikkan secara otomatis memenuhi trait bound `Send + Sync + 'static`, serta gunakan span error untuk menolak struct yang mencoba menginjeksi pointer mentah (`*const T` / `*mut T`).

---

### Kunci Jawaban Evaluasi

#### Bagian 1: Basic
1. **B** — Menginstruksikan kompilator untuk mengompilasi crate sebagai dylib host untuk plugin `rustc`.
2. **C** — `proc_macro` terisolasi di compiler execution engine, sedangkan `proc_macro2` dapat digunakan di luar context compiler (seperti test suite biasa).
3. **B** — `#(#variable),*` adalah sintaks valid interpolasi koleksi pada macro `quote!`.
4. **B** — `call_site()` mengaitkan span diagnostics ke baris pemanggilan kode di pengguna akhir.
5. **A** — `syn::DeriveInput` adalah root node AST yang merepresentasikan data types (`struct`, `enum`, `union`).

#### Bagian 2: Intermediate
6. **Kelemahan Kode**: Tipe `Result`, `String`, dan varian `Ok` tidak menggunakan fully-qualified absolute path. Jika pemanggil mendeklarasikan `enum Result {}` atau menggunakan scope no-std, kompilasi akan langsung crash (*broken expansion*). Solusi wajib: `::core::result::Result`, `::core::result::Result::Ok`, dan `::alloc::string::String`.
7. **Mekanisme Penghapusan**: Makro attribute mengembalikan `proc_macro::TokenStream::new()` (stream kosong) tanpa menyertakan kembali token input asal. Kompilator akan menelan item tersebut dari pohon sintaksis akhir.
8. **Kerugian String Parsing**: Mengonversi AST ke String membuang struktur span (`Span`). Jika string dimanipulasi dengan regex dan dilempar kembali, line number error pengguna hilang, hygiene hancur, dan performa kompilasi menurun drastis akibat serialisasi ulang token.
9. **Inert vs Active**: Inert attribute didefinisikan lewat metadata `attributes(...)` pada derive macro; kompilator tidak menjalankannya melainkan membiarkannya dibaca oleh derive macro. Active attribute adalah proc-macro independen yang mengeksekusi transformasi kode secara langsung dan menggantikan deklarasi aslinya.
10. **Isolasi Arsitektur**: Kompilator Rust membagi target kompilasi: Proc macro dikompilasi menggunakan target triple mesin Host (lingkungan kompilasi lokal) agar dapat dimuat ke dynamic linker `rustc`. Hasil dari ekspansi makro berupa kode Rust murni yang kemudian dikompilasi oleh compiler backend menuju target triple tujuan cross-compile.

#### Bagian 3: Production Scenarios
11. **Solusi Skenario 1**:
    - Minimalkan dependensi pada proc-macro crate (gunakan `default-features = false` pada `syn`, hanya aktifkan feature flag yang benar-benar dipakai seperti `parsing`, `clone-impls`).
    - Pisahkan runtime parsing berat ke crate runtime reguler; buat macro hanya memancarkan pemanggilan fungsi generik runtime daripada menghasilkan kode inline yang masif di setiap pemanggilan (*reduce code explosion*).
    - Manfaatkan tool seperti `cargo-bloat` dan aktifkan sccache pada CI worker.
12. **Solusi Skenario 2**:
    - Hindari emisi implementasi blanket impl (`impl<T> Trait for T`).
    - Alihkan macro untuk mengikat implementasi secara eksplisit pada concrete type (`impl #struct_name #ty_generics`) dengan where-clause preservation (`#where_clause`).
    - Jika membutuhkan fallback dispatch, gunakan Autoref-based specialization trick (menghasilkan wrapper struct internal dan memanfaatkan resolusi method deref Rust yang deterministik).
13. **Solusi Skenario 3**:
    - Pada fase parsing AST di dalam makro, telusuri setiap tipe field struct.
    - Jika terdeteksi tipe `syn::Type::Ptr`, lempar `syn::Error::new_spanned(field.ty, "Raw pointers are strictly forbidden inside #[secure_actor]")`.
    - Di dalam emisi `quote!`, hasilkan static assertion block:
      ```rust
      const _: () = {
          fn __assert_send_sync<T: ::core::marker::Send + ::core::marker::Sync>() {}
          fn __verification_anchor() {
              __assert_send_sync::<#struct_name>();
          }
      };
      ```
    - Dengan teknik ini, data race dicegah sejak fase type-checking kompilator tanpa runtime penalty.

---

### 16. Summary

- **Procedural Macros** adalah compiler extensions yang beroperasi mentransformasikan token source code sebelum kompilator melakukan type checking, borrow checking, dan LLVM machine generation.
- **Trinitas Metaprogramming Rust** terdiri dari: `proc_macro2` (infrastruktur token agnostik), `syn` (parser tokenizer menjadi AST), dan `quote` (generator token via interpolasi quasi-quoting).
- Pada arsitektur enterprise modern, proc macro digunakan untuk meniadakan **runtime reflection overhead**, memvalidasi business invariants dan security schemas secara statis, serta menghasilkan adapter serilisasi performa tinggi secara otomatis.
- Disiplin penulisan macro level produksi menuntut **span diagnostics presisi**, penanganan namespace menggunakan **fully qualified canonical paths**, mitigasi peningkatan build latency, serta penolakan pola pemrograman tidak aman (*unsafe invariants*) langsung dari fase kompilasi.