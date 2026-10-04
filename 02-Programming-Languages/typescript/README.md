# Kurikulum Komprehensif Enterprise TypeScript Engineering

Selamat datang di repositori kurikulum resmi **Enterprise TypeScript Engineering**. Kurikulum ini dirancang berdasarkan standar industri modern dan taksonomi pembelajaran teknis [roadmap.sh: TypeScript](https://roadmap.sh/typescript). Kurikulum ini bertujuan mentransformasi pengembang dari tingkat sintaksis dasar menuju penguasaan arsitektural sistem tipe, pemrograman level tipe (*type-level programming*), rekayasa kompilator (*compiler engineering*), serta integrasi monorepo skala enterprise.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
TypeScript bukan sekadar "JavaScript dengan anotasi tipe". TypeScript adalah **sistem verifikasi pembuktian statis (*static proof-verification system*) berbasis teori tipe struktural (*structural type system*)** yang berjalan di atas JavaScript. Menguasai TypeScript berarti memahami interaksi dinamis antara fase waktu kompilasi (*compile-time*) dan fase waktu eksekusi (*runtime*).

Pendekatan kurikulum ini mengeliminasi paradigma penulisan tipe defensif/permisif (`any`, `as unknown as T`) dan menggantinya dengan:
* **Soundness & Precision**: Memaksimalkan akurasi inference mesin analisis aliran kontrol (*Control Flow Analysis*).
* **Zero Runtime Overhead**: Memanfaatkan sistem tipe untuk menegakkan invarian logika bisnis tanpa menambah jejak byte (*bundle size footprint*) pada hasil kompilasi JavaScript.
* **Type-Level Metaprogramming**: Memperlakukan sistem tipe sebagai bahasa fungsional murni turing-lengkap (*Turing-complete pure functional language*) untuk memvalidasi arsitektur perangkat lunak secara otomatis.

### Model Mental (*Mental Model*)
* **Types as Sets**: Tipe data adalah himpunan nilai yang valid. Operator union (`|`) merepresentasikan gabungan himpunan (*set union*), operator intersection (`&`) merepresentasikan irisan himpunan (*set intersection*), `unknown` adalah himpunan universal (*top type*), dan `never` adalah himpunan kosong (*bottom type*).
* **Erasure Semantic**: Semua konstruksi tipe (*type aliases, interfaces, generics, type arguments*) akan dihapus (*erased*) total saat kompilasi. Kode runtime tidak boleh bergantung pada keberadaan tipe, kecuali konstruksi hibrida resmi (*enums*, parameter properties pada *classes*).
* **Structural Subtyping**: Kesetaraan tipe ditentukan murni oleh bentuk dan kapabilitas data (*shape and members*), bukan dari deklarasi nama atau hierarki pewarisan eksplisit (*nominal subtyping*).

### Prasyarat (*Prerequisites*)
* Pemahaman mendalam tentang ECMAScript Modern (ES2022+): Closures, Prototypal Inheritance, Asynchronous Event Loop, Symbols, dan Proxy.
* Pengalaman membangun aplikasi backend (Node.js/Bun) atau frontend modern (React/Next.js/Vue).
* Pemahaman fundamental mengenai Command Line Interface (CLI) dan ekosistem paket Node.js (`npm`/`pnpm`).

---

## 2. Learning Roadmap

```text
========================================================================================================
                          ENTERPRISE TYPESCRIPT CURRICULUM ARCHITECTURE
========================================================================================================

 [BAB 01: Core Semantics & Execution Architecture]
       │
       ├──► [BAB 02: Structural Typing & Shape Contracts]
       │         │
       │         └──► [BAB 03: Functions, Signatures, & Context Execution]
       │                   │
       └───────────────────┴──► [BAB 04: Advanced Generics & Parametric Polymorphism]
                                     │
       ┌─────────────────────────────┴─────────────────────────────┐
       │                                                           │
 [BAB 05: Type-Level Programming & Metaprogramming]       [BAB 06: Control Flow Analysis & Type Guards]
       │                                                           │
       └─────────────────────────────┬─────────────────────────────┘
                                     │
                         [BAB 07: OOP & Modern Decorators]
                                     │
                         [BAB 08: Ambient Context & Declaration Files]
                                     │
                         [BAB 09: Compiler Internals & Monorepo Tooling]
                                     │
                         [BAB 10: Production Hardening & Runtime Validation]
                                     │
                                     ▼
                   [ENTERPRISE CAPSTONE SPECIFICATION]
========================================================================================================
```

---

## 3. Navigasi Detail Modul (Bab 01 – Bab 10)

### [Bab 01: Core Semantics & Execution Architecture](./bab-01/README.md)
Fondasi eksekusi TypeScript, arsitektur *two-phase pipeline*, siklus hidup kompilasi, serta distingsi fundamental antara sistem tipe struktural dan nominal.
* [Modul 01: Arsitektur Kompilasi dan Model Mental Tipe](./bab-01/01-arsitektur-kompilasi-dan-mental-model.md)
* [Modul 02: Primitive Types, Top Types (any vs unknown), dan Bottom Type (never)](./bab-01/02-primitive-dan-structural-typing.md)

### [Bab 02: Structural Typing & Shape Contracts](./bab-02/README.md)
Pendalaman kontrak data, semantik ekstensibilitas objek, proteksi mutasi memori (*immutability*), dan fenomena *excess property checks*.
* [Modul 01: Type Aliases vs Interfaces: Arsitektur, Kinerja, dan Deklarasi Penggabungan](./bab-02/01-interfaces-vs-type-aliases.md)
* [Modul 02: Structural Subtyping, Freshness, dan Excess Property Checks](./bab-02/02-structural-subtyping-dan-excess-property-checks.md)
* [Modul 03: Tuples, Readonly Modifiers, dan Const Assertions (`as const`)](./bab-02/03-tuples-dan-immutability-semantics.md)

### [Bab 03: Functions, Signatures, & Context Execution](./bab-03/README.md)
Spesifikasi kontrak eksekusi fungsi, polimorfisme tanda tangan (*overloads*), pelacakan leksikal konteks eksekusi, dan propagasi inferensi argumen.
* [Modul 01: Function Overloads, Signature Implementation, dan Polimorfisme](./bab-03/01-function-overloads-dan-polymorphism.md)
* [Modul 02: Explicit Contextual Typing (`this` parameter) dan Callbacks](./bab-03/02-this-typing-dan-execution-context.md)
* [Modul 03: Higher-Order Functions, Generic Inference, dan Narrowing Scope](./bab-03/03-higher-order-functions-dan-callback-narrowing.md)

### [Bab 04: Advanced Generics & Parametric Polymorphism](./bab-04/README.md)
Rekayasa tipe data berparameter generik, penerapan batas kemampuan tipe (*constraints*), variansi tipe data matematis, dan abstraksi tinggi.
* [Modul 01: Generic Constraints (`extends`), Type Parameter Dependencies, dan Default Arguments](./bab-04/01-generic-constraints-dan-type-parameters.md)
* [Modul 02: Type Variance: Covariance, Contravariance, Invariance, dan Bivariance](./bab-04/02-type-variance-covariance-contravariance.md)
* [Modul 03: Generic Instantiation Depth dan Rekayasa Higher-Rank Polymorphism](./bab-04/03-generic-instantiation-dan-defaults.md)

### [Bab 05: Type-Level Programming & Metaprogramming](./bab-05/README.md)
Pemrograman fungsional murni pada level tipe TypeScript: komputasi tipe bersyarat, ekstraksi tipe inferensial, transformasi pemetaan, dan manipulasi string literal.
* [Modul 01: Conditional Types dan Pattern Matching Menggunakan Keyword `infer`](./bab-05/01-conditional-types-dan-infer-inference.md)
* [Modul 02: Mapped Types, Key Remapping via `as`, dan Homomorphic Filtering](./bab-05/02-mapped-types-dan-key-remapping.md)
* [Modul 03: Template Literal Types, Recursive Types, dan Dynamic Deep Path Navigation](./bab-05/03-template-literal-types-dan-recursive-types.md)

### [Bab 06: Control Flow Analysis & Type Guards](./bab-06/README.md)
Mekanisme analisis aliran kontrol (*CFA*) internal kompilator, pembedahan aljabar tipe data (*Tagged/Discriminated Unions*), dan jaminan validitas eksekusi statis.
* [Modul 01: Discriminated Unions, Tagged Variants, dan Exhaustiveness Checking via `never`](./bab-06/01-discriminated-unions-dan-exhaustive-never.md)
* [Modul 02: Custom Type Guards (`is`) dan Assertion Signatures (`asserts condition`)](./bab-06/02-custom-type-guards-dan-assertion-signatures.md)

### [Bab 07: Object-Oriented TypeScript & Modern Decorators](./bab-07/README.md)
Implementasi paradigma berorientasi objek tingkat tinggi dan metaprogramming runtime modern menggunakan standar TC39 Stage 3 Decorators.
* [Modul 01: Advanced OOP: Abstract Classes, Access Modifiers, Polymorphic `this`, dan Mixins](./bab-07/01-oop-patterns-access-modifiers-abstract-classes.md)
* [Modul 02: TC39 Stage 3 Decorators vs Legacy Experimental Reflection Metadata](./bab-07/02-decorators-stage-3-vs-experimental-metadata.md)

### [Bab 08: Ambient Context & Declaration Files](./bab-08/README.md)
Integrasi modul eksternal, pembuatan distribusi pustaka (*library publishing*), pemetaan pustaka JavaScript murni (*shims/ambient declarations*), dan modifikasi global tipe.
* [Modul 01: Authoring Declaration Files (`.d.ts`), Triple-Slash Directives, dan Ambient Namespaces](./bab-08/01-ambient-declarations-dan-dts-authoring.md)
* [Modul 02: Module Augmentation, Declaration Merging, dan Global Scope Pollution Handling](./bab-08/02-module-resolution-interop-dan-global-augmentation.md)

### [Bab 09: Compiler Internals & Monorepo Tooling](./bab-09/README.md)
Dekomposisi internal `tsc`, konfigurasi mendalam `tsconfig.json`, optimasi performa monorepo menggunakan Composite Projects, dan inspeksi Abstract Syntax Tree (AST).
* [Modul 01: `tsconfig.json` Architecture: Module Resolution (`NodeNext`), Strict Soundness Flags](./bab-09/01-tsconfig-deep-dive-dan-strict-soundness.md)
* [Modul 02: Project References, Composite Projects, Build Caching, dan Subpath Exports](./bab-09/02-project-references-dan-monorepo-architectures.md)
* [Modul 03: TypeScript Compiler API: Program, TypeChecker, AST Traversal, dan Custom Transformers](./bab-09/03-typescript-compiler-api-dan-ast-traversal.md)

### [Bab 10: Production Hardening & Runtime Validation](./bab-10/README.md)
Penyelesaian masalah divergensi runtime vs kompilasi: integrasi schema validation zero-cost, diagnostik profil kompilasi, serta strategi migrasi basis kode skala enterprise.
* [Modul 01: Profiling Waktu Kompilasi: `--extendedDiagnostics`, Trace Analysis, dan Anti-Patterns](./bab-10/01-type-checking-performance-dan-diagnostics.md)
* [Modul 02: Zero-Cost Runtime Type Safety: TypeBox vs Zod vs ArkType vs Typia](./bab-10/02-runtime-validation-boundary-patterns.md)
* [Modul 03: Production Deployment: Strict Linting, CI/CD Type Validations, dan Gradual Migration](./bab-10/03-production-ci-cd-dan-gradual-migration.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**"AetherBus": Type-Safe Distributed Event Orchestration Engine & Query DSL**

### Gambaran Umum
Siswa diwajibkan merancang dan membangun pustaka (*library framework*) berbasis TypeScript modern dari awal (*from scratch*) tanpa menggunakan anotasi `any` tunggal pun. Proyek ini menggabungkan arsitektur *event-driven* dengan sebuah *Query DSL builder* internal yang sepenuhnya aman secara tipe (*end-to-end compile-time type-safe*).

### Persyaratan Arsitektural & Fungsional
1. **Event Schema Registry (Type-Level Meta Engine)**:
   * Menggunakan recursive generic types untuk memetakan nama topik/event secara hierarkis (misal: `"order.created"`, `"payment.invoice.paid"`).
   * Menegakkan strictly typed payload: Setiap subscriber event hanya menerima payload yang tepat sesuai definisi schema yang diregistrasi, dideteksi menggunakan *Template Literal Types* dan *Mapped Types*.
2. **Type-Safe Query DSL Builder**:
   * Implementasi *Fluent Interface* (Builder Pattern) yang memungkinkan pengguna melakukan *filtering*, *selection*, dan *mutation* pada entitas basis data virtual.
   * Auto-complete cerdas untuk field bersarang (*nested field paths*) hingga kedalaman 5 tingkat menggunakan format `"user.profile.address.city"`.
   * Melarang kompilasi jika pengguna mencoba memfilter field yang tidak kompatibel dengan operator komparasi (contoh: komparator `$gt` hanya diizinkan untuk data bertipe `number` atau `Date`).
3. **Runtime Schema Boundary Verification**:
   * Validasi data eksternal yang masuk (*inbound JSON payload*) pada batas runtime menggunakan integrasi skema (Zod atau Typia) yang secara otomatis menyinkronkan *Static Type Signature* dengan representasi *Runtime Validator*.
   * Mengembalikan *Discriminated Union Result Object* (`{ success: true, data: T } | { success: false, errors: ValidationError[] }`) tanpa melempar runtime exception (*no throwing unhandled errors*).
4. **Monorepo & Build Tooling**:
   * Penataan basis kode menggunakan pnpm workspaces dan TypeScript Project References (`composite: true`).
   * Konfigurasi dual packaging (ESM dan CommonJS) dengan subpath exports resmi yang dipetakan pada `package.json`.
   * Ekstraksi otomatis file deklarasi tipe (`.d.ts`) menggunakan `api-extractor` atau build pipeline `tsc`.
5. **Zero-Warning Strict Linting**:
   * Wajib lolos verifikasi `tsc --noEmit` dengan opsi `strict: true`, `exactOptionalPropertyTypes: true`, `noImplicitReturns: true`, dan `noFallthroughCasesInSwitch: true`.

### Kriteria Kelulusan (*Evaluation Rubrics*)
* **Type Soundness (40%)**: Tidak ada penggunaan `any`, tidak ada type casting agresif (`as unknown as T`), minim penggunaan non-null assertion operator (`!`).
* **Type-Level Engineering Complexity (30%)**: Implementasi inference yang bersih pada inferensi parameter fungsi generic, penggunaan *conditional types*, *infer keyword*, dan *discriminated unions* yang tepat guna.
* **Architecture & Clean Code (20%)**: Struktur repositori modular, pemisahan layer runtime vs deklarasi tipe, penerapan best practices modern Node.js/TypeScript.
* **Testing & Verification (10%)**: Pengujian statis tipe menggunakan `tsd` atau `@total-typescript/type-testing` dan unit testing logika runtime menggunakan Vitest.

---
*Kurikulum ini dipelihara secara ketat untuk menjamin kualifikasi engineer siap pakai dalam menangani arsitektur perangkat lunak mission-critical.*