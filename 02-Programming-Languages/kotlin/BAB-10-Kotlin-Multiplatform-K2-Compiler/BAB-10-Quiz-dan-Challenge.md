# BAB 10: Quiz, Challenge, & Knowledge Check
**Kotlin Multiplatform & K2 Compiler**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik dan Resolusi `expect` / `actual`
Jelaskan secara mendalam bagaimana compiler Kotlin menyelesaikan deklarasi `expect` dan `actual` pada fase kompilasi. Mengapa mekanisme ini tidak dapat disamakan secara semantik maupun performa dengan interface/abstraksi berbasis runtime polymorphism atau Dependency Injection? Analisis konsekuensinya terhadap ukuran biner (*binary footprint*) dan *virtual method table (vtable) dispatch*.

### Soal 1.2: Evolusi Arsitektur K1 ke K2 (Frontend IR / FIR)
Compiler K1 lama memproses AST (*Abstract Syntax Tree*) berbasis PSI (*Program Structure Interface*) secara berulang pada fase resolusi, analisis semantik, dan pengecekan tipe (*type-checking*). Jelaskan bagaimana arsitektur Frontend Intermediate Representation (FIR) pada Compiler K2 mendesain ulang *pipeline* ini. Bagaimana representasi data FIR meminimalisasi *memory allocation* dan mempercepat *symbol resolution*?

### Soal 1.3: Arsitektur Kotlin/Native Modern Memory Manager
Pada Kotlin/Native generasi awal, model konkurensi memberlakukan aturan ketat: *immutable objects can be shared, mutable objects cannot be shared across threads* (mekanisme `freeze()`). Jelaskan arsitektur **New Memory Manager** yang diperkenalkan secara stabil pada versi modern. Bagaimana Garbage Collector (GC) baru menangani *concurrent sweeping*, alokasi memori bersama (*shared mutable state*), dan siklus referensi (*reference cycles*) antar-thread?

### Soal 1.4: Hierarchical Multiplatform Project Structure (HMPP)
Sebelum hadirnya HMPP, sourceSet pada KMP bersifat bifurkasi kaku: kode umum hanya bisa ditulis di `commonMain` atau langsung di target spesifik (misal: `jvmMain`, `iosX64Main`). Jelaskan bagaimana HMPP memvalidasi pembagian kode di *intermediate sourceSet* (contoh: `appleMain`, `nativeMain`). Bagaimana Klib (*Kotlin Library*) merepresentasikan metadata dan deklarasi intermediate symbols ini sebelum linking akhir dilakukan?

### Soal 1.5: Peningkatan Smart Casts dan Flow-Sensitive Typing pada K2
Salah satu perbaikan paling signifikan pada K2 adalah analisis kontrol alur (*control-flow analysis*) dan *smart casting*. Jelaskan perbedaan mendasar algoritma analisis tipe data antara K1 dan K2 ketika menangani:
1. *Smart casting* pada variabel lokal di dalam *closure* atau *inline lambda*.
2. Evaluasi percabangan kompleks dengan operator logika majemuk (`&&`, `||`, contracts).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: `expect actual` via Type Alias vs Direct Implementation
Perhatikan deklarasi berikut untuk implementasi primitif thread-safe:
```kotlin
// commonMain
expect class AtomicIntRef(initialValue: Int) {
    fun get(): Int
    fun incrementAndGet(): Int
}

// jvmMain
actual typealias AtomicIntRef = java.util.concurrent.atomic.AtomicInteger
```
Analisis implikasi penggunaan `actual typealias` dibanding implementasi class pembungkus (*wrapper class*). Tinjau dari sudut pandang *inline optimization*, overhead *object allocation*, kesesuaian ABI (*Application Binary Interface*), dan limitasi jika platform native membutuhkan pemetaan memori yang berbeda.

### Soal 2.2: Transisi Compiler Plugin K1 (Synthetic Resolve/IR) ke FIR2IR
Jika sebuah tim memelihara compiler plugin custom di K1 yang memanipulasi *class generation* (misalnya: injeksi metadata otomatis menggunakan `SyntheticResolveExtension`), kegagalan apa yang pasti dihadapi saat bermigrasi ke K2? Jelaskan pemisahan peran antara `FirExtensionRegistrar` (FIR frontend phase) dan `IrGenerationExtension` (Backend phase) pada K2 Compiler Architecture.

### Soal 2.3: Interop ABI & Objective-C/Swift Bridge (`cinterop`)
Saat mengekspor library KMP ke CocoaPods/Swift Package Manager melalui biner `.xcframework`, bagaimana Kotlin/Native memetakan konvensi pemanggilan kode (*calling conventions*), referensi memori (*reference counting*), dan penanganan error:
1. Mengapa fungsi Kotlin bertanda suspend dikonversi menjadi completion handler di Swift?
2. Bagaimana Kotlin memetakan generic parameters invariant vs covariant ke Objective-C lightweight generics, dan di mana titik batas (*type erasure boundaries*) kegagalannya?

### Soal 2.4: Diagnostik Klib Serialization & Binary Incompatibility
Ketika mempublikasikan library multiplatform, Klib menyimpan bitcode Intermediate Representation (IR) serta deklarasi metadata. Jika sebuah library di-*compile* menggunakan compiler versi $X$ dan dikonsumsi oleh project dengan compiler versi $Y$:
1. Kapan status *IR ABI stability* terpenuhi?
2. Mengapa error seperti `IrLinkageError` atau *unresolved symbols* terjadi pada Klib di level backend linking, meskipun proses resolusi sintaks di IDE tampak valid?

### Soal 2.5: Linker Bottleneck dan LLVM Code Generation
Pada target Kotlin/Native (iOS/macOS), kompilasi backend melibatkan konversi Kotlin IR ke LLVM Bitcode sebelum akhirnya dikompilasi ke *machine code* oleh linker (`ld64` atau `lld`).
1. Mengapa fasa *linkage* pada Kotlin/Native membutuhkan waktu dan memori yang sangat tinggi dibanding JVM?
2. Bagaimana mekanisme K2 Compiler dan optimasi flag kompilasi (misal: `-Xbinary=bundleId`, cache LLVM) memitigasi waktu *linking* pada lingkungan CI/CD?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Crash OOM pada Gradle Worker Saat Kompilasi Monorepo Skala Enterprise
* **Konteks:** Perusahaan fintech mengonversi monorepo multi-modul (terdiri dari 60 modul Kotlin, 4 target: JVM, Android, iOS Arm64, iOS Simulator Arm64) dari K1 ke K2 Compiler (Kotlin 2.0+). Tim CI/CD mendeteksi bahwa *build agent* (RAM 32GB) mengalami terminasi proses secara acak (*killed by SIGKILL / OOM-killer*) saat menjalankan task `:shared:linkPodReleaseFrameworkIosArm64` bersamaan dengan task backend Kotlin JVM.
* **Gejala:** 
  - Gradle Daemon crash dengan exit code 137.
  - LLVM backend mengonsumsi RSS memory > 18GB secara tiba-tiba.
  - K2 FIR cache tidak terdistribusi antar worker tasks.
* **Pertanyaan Diagnostik:**
  1. Analisis arsitektur alokasi memori antara Gradle Daemon worker heap, Kotlin Compiler daemon, dan subproses LLVM. Di mana letak titik kebocoran atau akumulasi memori terbesar pada skenario tersebut?
  2. Susun serangkaian konfigurasi `gradle.properties` dan strategi modifikasi pipeline build (termasuk worker isolation, parallel execution controls, dan LLVM bitcode caching) untuk menstabilkan build agent tanpa mendegradasi performa timbal balik secara masif.

---

### Skenario B: Fatal Exception & Memory Corruption Saat Concurrency Crossing Border (Swift - Kotlin)
* **Konteks:** Sebuah aplikasi perbankan modern menggunakan KMP untuk enkripsi data payload. Modul enkripsi berjalan di background worker pool memanfaatkan Kotlinx Coroutines. Ketika fungsi enkripsi dipanggil berulang kali secara paralel dari Swift (Task iOS concurrency / GCD) menuju objek KMP, aplikasi mengalami crash intermiten:
  `objc[2341]: autorelease pool page ... corrupted` atau `EXC_BAD_ACCESS (SIGSEGV)` pada runtime LLVM Kotlin Native.
* **Gejala:**
  - Kode di Swift:
    ```swift
    Task.detached(priority: .background) {
        let cryptoEngine = KMPCryptoEngine()
        let result = try await cryptoEngine.encryptPayload(data: payload)
        // handle result
    }
    ```
  - `KMPCryptoEngine` menyimpan pointer referensi C (*StableRef*) ke native platform cryptor iOS (`CommonCrypto`).
* **Pertanyaan Diagnostik:**
  1. Bagaimana siklus hidup `StableRef` diatur di antara siklus deteksi Kotlin Tracing GC dan Swift Automatic Reference Counting (ARC)? Mengapa operasi konkuren di Swift Task memicu `EXC_BAD_ACCESS` jika `StableRef` tidak di-dispose secara deterministik?
  2. Tunjukkan perbaikan arsitektur memori pada lapisan bridge `cinterop` ini agar alokasi `COpaquePointer` / `StableRef` bersifat thread-safe dan memori bebas dari *use-after-free* maupun *memory leak*.

---

### Skenario C: Migrasi Library Legacy JVM-Only ke KMP dengan Kontrak Binary Compatibility (ABI)
* **Konteks:** Platform SDK perbankan berbasis JVM (digunakan oleh ratusan modul client perbankan Java & Kotlin) harus dimigrasikan menjadi Kotlin Multiplatform untuk mendukung aplikasi iOS tanpa mengubah API publik bagi konsumen Java/JVM yang ada.
* **Gejala:**
  - Konsumen Java di internal bank menggunakan class reflection, method overload bawaan Java, dan primitive blocking I/O stream.
  - Perubahan sederhana seperti memindahkan class ke `commonMain` dan mengubah I/O menjadi Kotlin Multiplatform non-blocking I/O (`kotlinx-io`) merusak biner downstream (menghasilkan `NoSuchMethodError` atau `NoClassDefFoundError` pada runtime konsumen Java).
* **Pertanyaan Diagnostik:**
  1. Bagaimana cara merancang arsitektur modul KMP baru agar target JVM tetap memproduksi signature biner, metadata classfile, dan anotasi Java-friendly (seperti `@JvmOverloads`, `@JvmStatic`, `@JvmName`, dan `@Throws`) yang identik secara biner (100% ABI compliant) dengan versi legacy?
  2. Jelaskan trade-off antara penggunaan *facade pattern* di level source code (JVM-only wrapper module) versus penggunaan `expect actual` langsung pada level root SDK.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Multiplatform Thread-Safe Token-Bucket Rate Limiter Engine

#### Problem:
Rancang dan implementasikan library KMP minimal (core engine) yang mengimplementasikan algoritma **Token-Bucket Rate Limiter** thread-safe untuk mengontrol *throughput* outgoing API requests. Engine ini harus berjalan secara deterministik dan optimal pada dua runtime yang sangat berbeda: **JVM (Java 21+)** dan **Native Darwin (iOS Arm64/Simulator)** menggunakan **K2 Compiler**.

#### Requirements:
1. **Multiplatform Architecture:**
   - Direktori `commonMain`: Berisi kontrak abstraction rate limiter, time provider abstraction (monotonically increasing time), dan logic throttling token calculation tanpa blocking.
   - Implementasi state token bucket harus atomic dan non-blocking (lock-free CAS: Compare-And-Swap pattern).
2. **Platform Primitives:**
   - **JVM Target:** Wajib memanfaatkan implementasi berbasis *lock-free primitives* standar JVM (misal: `java.util.concurrent.atomic.AtomicLong` via `expect/actual typealias`).
   - **Native Target:** Wajib memanfaatkan Kotlin/Native atomic primitives (`kotlin.concurrent.AtomicLong` atau memory model atomics baru) tanpa menggunakan legacy `@SharedImmutable` atau `freeze()`.
3. **K2 Configuration:**
   - Project harus dikonfigurasi menggunakan Kotlin 2.0+ dengan flag `-language-version 2.0`.
   - Mengaktifkan pengecekan strict ABI validation (Binary Compatibility Validator plugin).
4. **Swift/Darwin Export:**
   - Menyediakan interface API yang bersih ketika diakses oleh Swift:
     ```swift
     let limiter = RateLimiter(capacity: 100, refillRatePerSecond: 10)
     if limiter.tryAcquire(tokens: 1) {
         // Proceed
     }
     ```
   - Memastikan tidak ada symbol collision dan memory retain cycle ketika di-retain oleh struktur ARC Swift.

#### Constraints:
- **Zero Third-Party Concurrency Dependencies:** Dilarang menggunakan library eksternal (dilarang menggunakan AtomicFU pihak ketiga atau library utilitas concurrency lainnya). Hanya boleh memanfaatkan Kotlin Standard Library dan platform C/Java runtime bindings.
- **Allocation Profile:** Operasi pemanggilan method `tryAcquire(tokens: Long): Boolean` harus bersifat *zero-allocation* pada steady state (tidak boleh menciptakan alokasi objek baru ke heap pada setiap pengecekan).

#### Expected Output:
1. File `build.gradle.kts` lengkap dengan konfigurasi target multiplatform (JVM & iOS targets), konfigurasi compiler K2, dan framework linkage export.
2. Source code lengkap untuk struktur file:
   - `commonMain/.../RateLimiter.kt` (State machine logic token bucket & CAS operation)
   - `commonMain/.../PlatformAtomic.kt` (`expect` contract)
   - `jvmMain/.../PlatformAtomic.kt` (`actual` implementation)
   - `nativeMain/.../PlatformAtomic.kt` (`actual` implementation)
3. Unit test di `commonTest` yang menguji integritas *thread contention*: 10 concurrent workers mencoba mengonsumsi token yang terbatas secara agresif, memastikan total token yang sukses dialokasikan tepat sesuai limit tanpa terjadi over-allocation (*race condition check*).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal K2 Compiler: Transisi Frontend PSI ke FIR (Frontend Intermediate Representation) dan perbedaannya dengan Kotlin Backend IR.
- [ ] Pipeline resolusi simbol `expect` dan `actual` pada compile-time serta mekanisme `typealias` untuk eliminasi wrapping overhead.
- [ ] Arsitektur New Memory Manager Kotlin/Native: Tracing Garbage Collector, alokasi memori heap terpadu, dan eliminasi paradigma *frozen state*.
- [ ] Hierarchical Multiplatform Project Structure (HMPP) dan struktur Klib: Serialisasi metadata dan symbol resolution di *intermediate sourceSet*.
- [ ] Mekanisme interoperabilitas memory boundary antara Swift/Objective-C ARC dan Kotlin/Native GC (termasuk pinning, `StableRef`, dan pointer life-cycle).
- [ ] Smart cast improvements pada K2: DFA (Data Flow Analysis), type contracts, dan pemrosesan alur kendali logika majemuk.
- [ ] Perbedaan eksekusi dan linking antara dynamic framework vs static framework pada output Kotlin/Native Darwin targets.

### Saya tidak perlu menghafal:
- [ ] Struktur byte-order internal dan skema biner file serialisasi format `.klib`.
- [ ] Nama-nama class internal private compiler AST K1 versi legacy (seperti `JetTypeReference`, `BindingContextImpl`).
- [ ] Command-line flag mendalam untuk toolchain LLVM C-compiler yang dibungkus otomatis oleh task `cinterop`.
- [ ] ABI mangling algorithm spesifik yang dihasilkan Kotlin/Native untuk bridging Objective-C protocols.

### Saya harus bisa melakukan:
- [ ] Mendesain struktur arsitektur library Kotlin Multiplatform yang bersih memisahkan *business logic* platform-agnostic dengan platform-specific APIs.
- [ ] Melakukan profiling dan debugging build time KMP: Mendiagnosis bottleneck antara compileKotlin tasks, Klib generation, dan LLVM Native Linking.
- [ ] Menulis bridge interoperabilitas C / Objective-C menggunakan `cinterop` def file dan menangani konversi pointer (`CPointer`, `StableRef`) secara aman tanpa kebocoran memori (*memory leak*).
- [ ] Melakukan migrasi compiler plugin atau codebase dari Kotlin 1.9 ke Kotlin 2.0+ (K2) dan menyelesaikan issue *flow typing* atau *symbol resolution ambiguity*.
- [ ] Menggunakan Binary Compatibility Validator (`binary-compatibility-validator`) untuk menjaga stabilitas public ABI library multiplatform antar-rilis versi produksi.