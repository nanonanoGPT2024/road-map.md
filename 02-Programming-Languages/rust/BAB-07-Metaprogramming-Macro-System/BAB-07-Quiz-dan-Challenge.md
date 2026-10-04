# BAB 07: Quiz, Challenge, & Knowledge Check
**Metaprogramming & Macro System**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Hygiene Identitas dan Resolusi Simbol (`macro_rules!` vs Procedural Macros)**  
   Jelaskan perbedaan mendasar antara *hygiene system* pada `macro_rules!` (berbasis *edition hygiene* / semi-hygienic) dengan Procedural Macros (`proc_macro`). Mengapa `macro_rules!` secara otomatis mencegah *variable shadowing* terhadap variabel di luar cakupannya (*scope* pemanggil), sementara implementasi `proc_macro` manual rentan terhadap *hygiene leakage* jika tidak menangani `Span::call_site()` versus `Span::mixed_site()` dengan tepat?

2. **Taksonomi Token Tree dan Fragment Specifiers**  
   Pada `macro_rules!`, sebutkan fungsi serta implikasi parsing dari fragment specifiers berikut: `ident`, `path`, `expr`, `ty`, dan `tt`. Mengapa fragment `expr` tidak dapat langsung diikuti oleh sembarang operator token (seperti `+` atau `-`) di dalam pola matcher macro, dan bagaimana aturan *matcher ambiguity restrictions* di Rust Compiler (`rustc`) mencegah *backtracking parser* eksponensial?

3. **Crate Boundary Constraint pada Procedural Macro**  
   Mengapa Rust mewajibkan implementasi Procedural Macro (`custom derive`, `attribute-like`, dan `function-like`) dideklarasikan di dalam crate terpisah dengan tipe `proc-macro = true` di file `Cargo.toml`? Jelaskan implikasi arsitektur kompilasi ini terhadap relasi *host architecture* (arsitektur mesin tempat compiler berjalan) versus *target architecture* (arsitektur tujuan kompilasi target *binary*).

4. **Karakteristik Tiga Pilar Procedural Macro**  
   Bandingkan ketiga jenis Procedural Macro di Rust:
   * Custom Derive (`#[derive(Trait)]`)
   * Attribute-like Macro (`#[custom_attribute]`)
   * Function-like Macro (`custom_macro!(...)`)  
   
   Tinjau berdasarkan: (a) input AST / `TokenStream` yang diterima, (b) kemampuan memodifikasi, mengganti, atau menambah item asli, dan (c) lokasi penempatan yang valid dalam sintaksis Rust.

5. **Trade-off Metaprogramming: Macro vs Trait Monomorphization**  
   Kapan Anda secara definitif memilih *compile-time code generation* menggunakan macro dibandingkan memanfaatkan *generic trait resolution* dengan *monomorphization*? Analisis dari perspektif *binary footprint (code bloat)*, batas ekspresi sistem tipe Rust (misal: *variadic arguments* atau manipulasi struktur *field* secara dinamis), dan waktu kompilasi (*compile-time overhead*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **AST Lowering, Expansion Phases, dan `cargo expand`**  
   Jelaskan fase kompilasi di mana *macro expansion* dijalankan oleh `rustc` relatif terhadap *lexical analysis*, *parsing*, *type checking* (HIR lowering), dan *borrow checking* (MIR construction). Apa implikasi struktural jika sebuah macro menghasilkan kode yang bergantung pada evaluasi tipe data (type inference), dan mengapa macro Rust tidak memiliki akses ke informasi semantik tipe pada saat ekspansi berlangsung?

2. **Dinamika Span dan Rekayasa Compiler Error Diagnostics**  
   Dalam ekosistem `proc_macro2` dan `syn`, jelaskan perbedaan fungsional antara `Span::call_site()`, `Span::def_site()`, dan `Span::mixed_site()`. Bagaimana cara Anda memanfaatkan manipulasi `Span` pada `proc_macro` kustom untuk mengarahkan pesan galat kompilasi (`compile_error!`) secara presisi ke atribut *field* tertentu dari sebuah `struct`, bukan ke keseluruhan deklarasi *struct* tersebut?

3. **Limitasi Rekursi dan *Macro Recursion Limit***  
   Bagaimana mekanisme internal `macro_rules!` dalam menangani rekursi token (misal: *push-down automaton pattern*)? Apa yang terjadi pada kompilator ketika batas rekursi terlampaui, mengapa atribut `#![recursion_limit = "..."]` diperlukan, dan bagaimana arsitektur macro rekursif yang buruk dapat menyebabkan *compiler stack overflow*?

4. **Troubleshooting Macro-Generated Trait Bounds & Generic Lifetimes**  
   Perhatikan kasus di mana sebuah Procedural Derive Macro menghasilkan implementasi `impl<T> MyTrait for Struct<T>`. Jika `Struct<T>` memiliki klausa `where T: 'a + Debug`, pendekatan apa yang harus diambil oleh *macro author* saat mengurai AST melalui `syn::Generics` (khususnya pembagian antara `split_for_impl`, `impl_generics`, `ty_generics`, dan `where_clause`) untuk memastikan bahwa *generic lifetimes*, *const generics*, dan *generic bounds* tidak tereduksi atau terduplikasi yang berakibat pada compiler error `E0283` / `E0277`?

5. **Soundness Hazards pada Macro-Generated `unsafe` Blocks**  
   Mengapa penulisan macro yang menghasilkan blok `unsafe` (misal: implementasi otomatis trait `Send`/`Sync`, atau casting memori via raw pointers) dianggap sebagai risiko tinggi terhadap *soundness* library? Strategi isolasi apa yang harus diterapkan—seperti penggunaan *hygienic hidden modules* (`const _: () = { ... };`), penamaan alias fully qualified paths (`::core::marker::Sync`), dan verifikasi invarian statis—untuk memitigasi eksploitasi keamanan?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Waktu Kompilasi Ekstrem pada Monorepo Skala Enterprise
Sebuah monorepo backend perbankan berbasis microservices berbasis Rust mengalami lonjakan durasi kompilasi pipeline CI dari 8 menit menjadi 48 menit. Tim mendapati bahwa hampir setiap *Data Transfer Object* (DTO) dan entitas database (lebih dari 1.500 `struct`) mengimplementasikan *custom derive chain* yang masif: `#[derive(Serialize, Deserialize, Validate, EntQuery, AuditTrail, GraphQlObject)]`. Setiap derive crate melakukan *full parsing* AST menggunakan `syn` dengan fitur `features = ["full"]` diaktifkan secara redundan, serta menghasilkan ribuan baris kode per DTO yang memperbesar beban *monomorphization* dan penulisan metadata disk.
* **Pertanyaan Diagnostik:**
  1. Bagaimana metodologi Anda dalam memprofil fase kompilasi `rustc` menggunakan *flags* seperti `-Z self-profile` atau *crate compilation timing graphs* (`cargo build --timings`) untuk membuktikan bahwa *macro expansion* dan *parsing overhead* adalah biang keladinya?
  2. Langkah arsitektural refactoring apa yang harus diterapkan pada *macro crates* tersebut (misal: seleksi fitur `syn`, konsolidasi *single-pass derive macro*, teknik *declarative codegen reduction*, atau transisi ke *blanket implementations*) guna memotong durasi kompilasi tanpa mengorbankan fitur validasi dan audit?

### Skenario B: *Unhygienic Shadowing* dan Namespace Hijacking pada Library Multitenant
Sebuah distributed storage engine menggunakan macro deklaratif internal untuk routing eksekusi RPC:
```rust
macro_rules! dispatch_rpc {
    ($handler:ident, $payload:expr) => {
        let context = SecurityContext::from_ambient();
        if context.is_authorized() {
            $handler($payload);
        } else {
            panic!("Unauthorized access");
        }
    };
}
```
Seorang teknisi di tim implementasi menulis handler yang di dalamnya terdapat variabel lokal bernama `context`:
```rust
let context = get_untrusted_user_input();
dispatch_rpc!(process_transaction, context);
```
Setelah rilis patch, terjadi insiden di mana data sensitif bocor dan otorisasi *bypassed* karena terjadi interaksi aneh antara variabel lokal dan kode hasil ekspansi macro pada kasus penggunaan pola pointer passing tertentu.
* **Pertanyaan Diagnostik:**
  1. Identifikasi celah kerapuhan semantik pada macro `dispatch_rpc!` di atas. Mengapa penggunaan token literal `SecurityContext` dan variabel lokal tanpa fully qualified path dan proper hygiene berisiko menimbulkan *name collision*, *silent shadowing*, atau pembobolan context?
  2. Desain ulang macro tersebut menjadi solusi yang *bulletproof*, menerapkan fully qualified path syntax (`::core`, `$crate`), dan pastikan penanganan variabel di dalam macro tidak dapat dibajak (*tampered*) oleh simbol-simbol di scope pemanggil.

### Skenario C: Dualitas Arsitektur Domain Specific Language (DSL): Macro AST vs Runtime Interpretation
Tim Data Streaming Platform sedang mendesain modul *Filter Engine* untuk memproses jutaan event log per detik secara real-time. Tim terbelah menjadi dua kubu:
* **Kubu A:** Mengusulkan *embedded Procedural Macro DSL* (`filter_rules!(SELECT WHERE cpu > 80 AND service == "auth")`) yang langsung menghasilkan Rust native code dan *type-safe closures* pada saat kompilasi (*zero-overhead native execution*).
* **Kubu B:** Mengusulkan *runtime AST evaluation* menggunakan interpreter ringan atau JIT engine berbasis byte-code parser, yang membaca aturan dari Consul/etcd secara dinamis tanpa perlu rekompilasi binary Rust.
* **Pertanyaan Diagnostik:**
  1. Analisis komparatif mendalam antara kedua pendekatan tersebut berdasarkan metrik throughput, memory footprint, cold-start latency, dan fleksibilitas operasional produksi (*zero-downtime rule updates*).
  2. Usulkan arsitektur hibrida (*hybrid design pattern*) di mana validasi sintaksis dan optimasi struktur DSL dieksekusi secara ketat, namun pembaruan aturan tetap dapat dilakukan tanpa me-restart atau me-recompile seluruh klaster microservices.

---

## 4. Chapter Challenge

### Tantangan Praktis: Mengembangkan Custom Procedural Derive Macro `#[derive(StrictValidate)]`

#### Problem Context
Di sistem pemrosesan finansial, DTO yang masuk melalui serialisasi sering kali memiliki aturan validasi field yang ketat (misal: batasan range numerik, panjang string minimal/maksimal). Penggunaan library validasi berbasis runtime parsing sering kali menambahkan alokasi memori berlebih dan lambat. Anda ditugaskan membangun sistem validasi *compile-time derived* yang menghasilkan evaluasi kode native tanpa *regular expression overhead* dan tanpa alokasi heap baru saat validasi berlangsung.

#### Requirements
1. Buat sebuah workspace Cargo dengan dua crate:
   * `strict_validate`: Library core yang mendefinisikan trait `StrictValidate` dan tipe error `ValidationError`.
   * `strict_validate_derive`: Crate bertipe `proc-macro = true` yang menyediakan derive macro `StrictValidate`.
2. Macro harus mendukung atribut level *field*:
   * `#[validate(range(min = 10, max = 100))]`: Valid untuk tipe numerik primitif (`u32`, `i64`, `f64`, dll).
   * `#[validate(len(min = 3, max = 32))]`: Valid untuk tipe referensi string (`&str`) dan `String`.
3. Trait `StrictValidate` memiliki signature method:
   ```rust
   pub trait StrictValidate {
       fn validate(&self) -> Result<(), ValidationError>;
   }
   ```
4. Jika field tidak memiliki atribut `#[validate(...)]`, field tersebut diabaikan saat validasi.
5. Macro harus menghasilkan evaluasi *fail-fast* (berhenti pada error pertama) atau mengumpulkan semua error ke dalam `ValidationError::Multiple(Vec<&'static str>)` tanpa melakukan alokasi memori string baru di heap (gunakan static string slices untuk nama field dan deskripsi error).

#### Constraints
* Implementasikan parsing atribut menggunakan crate `syn` dan emisi token menggunakan `quote`.
* Macro harus mengeluarkan pesan error kompilasi yang ramah (`syn::Error::into_compile_error`) jika:
  * Atribut diaplikasikan pada tipe data yang salah (misal: `len` diterapkan pada tipe numerik).
  * Struktur data yang di-derive berupa `enum` atau `union` (hanya `struct` dengan *named fields* yang didukung).
* Seluruh referensi tipe di dalam kode yang dihasilkan macro harus menggunakan format Fully Qualified Path (`::core::result::Result`, `::core::primitive::str`, dll) agar kebal terhadap *hygiene collision*.

#### Expected Output
Contoh penggunaan yang harus lolos uji:

```rust
use strict_validate::StrictValidate;

#[derive(Debug, StrictValidate)]
pub struct TransactionRequest {
    #[validate(len(min = 5, max = 34))]
    pub iban: String,

    #[validate(range(min = 1, max = 10_000_000))]
    pub amount_cents: u64,

    pub note: Option<String>, // Tidak divalidasi
}

fn main() {
    let valid_tx = TransactionRequest {
        iban: "DE89370400440532013000".to_string(),
        amount_cents: 500_000,
        note: None,
    };
    assert!(valid_tx.validate().is_ok());

    let invalid_tx = TransactionRequest {
        iban: "ABC".to_string(), // Error: len < 5
        amount_cents: 0,         // Error: range < 1
        note: None,
    };
    assert!(invalid_tx.validate().is_err());
}
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara declarative macro (`macro_rules!`) dan procedural macro (`proc_macro`).
- [ ] Anatomi TokenStream, TokenTree, Ident, Group, Literal, dan Punct pada level AST kompilator Rust.
- [ ] Cara kerja *hygiene system* Rust: kapan identifier aman dari benturan nama dan kapan span dapat membocorkan konteks (*Span::call_site* vs *Span::mixed_site*).
- [ ] Siklus hidup macro expansion dalam tahapan kompilasi `rustc` (sebelum type checking dan borrow checking).
- [ ] Implikasi procedural macro terhadap overhead waktu kompilasi (*compile-time degradation*) dan teknik optimasi dependensi parser (`syn` features gating).
- [ ] Struktur penanganan generik (`syn::Generics`, lifetimes, where clauses) agar implementasi trait yang dihasilkan macro tidak memutus kontrak batas tipe kompilator.

### Saya tidak perlu menghafal:
- [ ] Struktur data internal dan representasi bit-level dari setiap varian enum AST di crate `syn` (cukup mengandalkan dokumentasi `syn` dan alat bantu seperti `synstructure`).
- [ ] Seluruh tabel karakter dan token specifier regex matcher `macro_rules!` yang jarang dipakai; pahami pola fundamental (`$($x:expr),*`, `$(...)+`, dsb.).
- [ ] Kode implementasi internal parsing literal integer/float; delegasikan ke parser utility standar seperti `syn::parse::Parse` dan `syn::LitInt`.

### Saya harus bisa melakukan:
- [ ] Menulis macro `macro_rules!` tingkat lanjut yang menerapkan teknik *TT muncher* (token tree recursive consuming) dan *internal rule tagging* (`@internal`).
- [ ] Membangun Custom Derive Macro dari nol menggunakan ekosistem `proc_macro`, `syn`, dan `quote`.
- [ ] Menghasilkan compiler diagnostics yang presisi menggunakan `syn::Error::new_spanned` yang mengarah tepat ke baris kode sumber yang salah.
- [ ] Melakukan debugging dan *disassembling* kode hasil ekspansi macro secara langsung menggunakan `cargo expand` atau `rustc --pretty=expanded`.
- [ ] Menulis *declarative macro* anti-pecah yang sepenuhnya aman dari namespace collision menggunakan pola `$crate::path::to::Item`.
- [ ] Melakukan analisis profil kompilasi untuk memetakan beban *codegen* dan waktu ekspansi macro pada level build pipeline.