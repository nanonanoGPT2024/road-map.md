# Kurikulum Enterprise: Kotlin Multiplatform & K2 Compiler Architecture
## Bab 10: Kotlin Multiplatform & K2 Compiler
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Software Engineer / Staff Architect diharapkan mampu:
- **Menganalisis dan Membedah Siklus Kompilasi K2 (Frontend IR / FIR):** Memahami arsitektur internal pipeline K2, desugaring AST, resolusi tipe semantik dua tahap, serta perbedaannya dengan pipeline legacy (FE1.0).
- **Mendesain Arsitektur Produksi Kotlin Multiplatform (KMP):** Merancang arsitektur aplikasi berskala enterprise (iOS, Android, JVM Backend, Wasm) menggunakan *Hierarchical Project Structure*, pemisahan *Domain-Driven Core*, dan abstraksi *platform-specific primitives*.
- **Menguasai Model Memori Kotlin/Native Generasi Baru:** Mengelola alokasi heap, siklus hidup garbage collector non-blocking (Concurrent Mark and Sweep), serta integrasi *interop* bebas kebocoran memori (C-interop & Swift/Objective-C interop).
- **Mengoptimalkan Kinerja Kompilasi & Build Cache:** Mengonfigurasi toolchain Gradle, K2 compiler options, *incremental compilation*, klib generation, dan optimasi *linking time* pada artifact biner native/JVM.
- **Mengidentifikasi & Menangani Edge Cases Lintas Platform:** Menyelesaikan isu-isu kompleks seperti *concurrency deadlocks* lintas thread boundary OS, ABI compatibility, serta *symbol mangling* pada biner native.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer harus memiliki pemahaman mendalam tentang:
- **Kotlin Core & Coroutines:** *Structured concurrency*, *Flow backpressure*, *Coroutines internals* (Continuation-Passing Style/CPS), dan *Memory visibility guarantees*.
- **Operating System & Runtime Fundamentals:** Virtual memory, threads, POSIX threads (pthreads), pointers, dan mekanisme JVM Runtime (HotSpot, JIT compilation, Classloading).
- **Build Systems:** Gradle Enterprise internals (Configuration Cache, Build Cache, Composite Builds, Kotlin DSL).
- **Sistem Target:** Dasar-dasar LLVM toolchain, Mach-O vs ELF binary formats, CocoaPods/SPM distribution mechanisms, serta Objective-C runtime semantics.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Pipeline Kompilasi K2 Compiler (Frontend IR / FIR)

Arsitektur compiler legacy (FE1.0) menggunakan struktur data berbasis PSI (*Program Structure Interface*) dan *BindingContext* (peta raksasa pemetaan AST ke metadata semantik) yang menyebabkan konsumsi memori masif ($O(N)$ terhadap jumlah node sintaksis) dan cache invalidation yang lambat.

K2 merevolusi pipeline ini dengan memperkenalkan **FIR (Frontend Intermediate Representation)**:

```
[Source Code (*.kt)]
        │
        ▼
   [Lexer / PSI] ─────────► [Light-Tree] (Zero-alloc AST mode)
        │
        ▼
   [Raw FIR Builder]
        │
        ▼
   [FIR Phases (1..12)] ──► Resolusi Tipe, Kontrak, Smart-Casts secara Bertahap
        │                   (Desugaring dilakukan lebih awal dan deterministik)
        ▼
  [FIR2IR Generator]   ──► Pemetaan FIR ke Unified Backend IR
        │
        ├────────────────────────┬────────────────────────┬───────────────────┐
        ▼                        ▼                        ▼                   ▼
[JVM Backend IR]        [Native Backend IR]      [JS Backend IR]     [Wasm Backend IR]
        │                        │                        │                   │
  [JVM Bytecode]          [LLVM Bitcode]            [JavaScript]         [Wasm Binary]
        │                        │
     (.class)               (LLVM Clang)
                                 │
                            (.dylib/.so/.a)
```

1. **Light-Tree Parsing:** K2 tidak mewajibkan pembuatan PSI struktural IntelliJ secara menyeluruh dalam mode batch compilation. Light-Tree menghasilkan pohon sintaksis berbasis event dengan jejak memori minimal.
2. **FIR Transformation Phases:** Resolusi tipe dibagi menjadi 12 stage deterministik. Pemisahan deklarasi tipe tubuh fungsi (*body analysis*) dan kepala fungsi (*signature analysis*) memungkinkan kompilasi paralel sejati pada level method/class.
3. **Smart Cast Resolution Engine:** K2 menggunakan *Control Flow Graph* (CFG) modern yang menghitung *data-flow variables* secara modular tanpa dependensi mutasi global State BindingContext.
4. **Backend IR Generation:** Unified IR menerima FIR yang sepenuhnya telah divalidasi. Backend khusus target (JVM, Native LLVM, JS, Wasm) menerima IR identik secara semantik, mengurangi inkonsistensi perilaku lintas platform.

#### 3.2 Kotlin/Native Memory Manager & Garbage Collection (Modern Runtime)

Kotlin/Native telah sepenuhnya mengabaikan model memori lama (*legacy memory manager* berbasis `freeze()` dan *thread-isolation model*). Runtime modern mengadopsi model konkurensi mirip JVM:

- **Shared Mutable State:** Seluruh objek dapat dimutasi dan diakses secara paralel dari thread mana pun asalkan menggunakan mekanisme sinkronisasi (`AtomicRef`, Mutex, atau Coroutines Mutex).
- **Concurrent Mark and Sweep (CMS) Garbage Collector:**
  - GC berjalan di thread terpisah (*background GC worker*).
  - Alokasi memori menggunakan *thread-local allocation buffers* (TLAB) berbasis *mimalloc* berkinerja tinggi untuk mengurangi kontensi lock global.
  - Siklus penandaan (*marking phase*) berjalan secara konkuren dengan thread eksekusi mutator, dengan *Stop-the-World* (STW) pauses seminimal mungkin (hanya pada *safepoints* untuk root processing dan sweep terminal phases).
- **Finalization & Reference Tracking:** Weak references dan siklus Objective-C interop (melalui ARC) diselesaikan oleh *Cycle Collector* khusus yang melacak siklus retain count lintas batas biner Native runtime dan Apple Runtime.

#### 3.3 Hierarchical Multiplatform Source Sets & KLIB Infrastructure

Metadata KMP dikompilasi ke dalam format `.klib` (*Kotlin Library*). Berbeda dengan `.jar` yang berisi bytecode JVM, `.klib` berisi:
- Serialized IR (Unified IR proto format).
- Metadata declarations (deskripsi semantik K2).
- Target-specific bits (LLVM bitcode stubs, C-headers, WebAssembly type definitions).

Struktur hirarkis mengizinkan sharing kode antar target spesifik:
- `commonMain`: Hanya kode agnostik murni (stdlib platform-agnostic).
- `nativeMain`: Bersama untuk Apple (iOS/macOS), Linux, Windows (akses ke C-interop dasar dan POSIX).
- `appleMain`: Bersama untuk iOS, macOS, watchOS, tvOS (akses ke framework Apple Cocoa, Foundation, CoreGraphics via Objective-C runtime).
- `iosMain`: Implementasi spesifik device iOS (UIKit, SecureEnclave).

---

### 4. Why & What

| Dimensi Arsitektural | Pendekatan Monolitik / Platform Silo | KMP dengan K2 Compiler Engine |
| :--- | :--- | :--- |
| **Logic Reuse vs Native UI** | Rewrite total logic di Swift (iOS) & Kotlin (Android) atau kompromi UI (React Native / Flutter engine canvas overhead). | **100% Native Execution & Native UI.** Berbagi logika bisnis, security, state machine, dan database; UI tetap native via SwiftUI/Compose. |
| **Compiler Compilation Time** | FE1.0: Lambat pada codebase besar karena memory thrashing BindingContext. | **K2 FIR Engine:** Reduksi waktu kompilasi hingga 50-70%, memory footprint compiler turun drastis, paralelisme pipeline native. |
| **Memory Isolation Safety** | Model legacy K/N: Mutasi lintas thread melempar `InvalidMutabilityException` jika objek tidak di-freeze. | **Modern K/N CMS Runtime:** Konkurensi multi-thread identik dengan POSIX/Java Memory Model tanpa ritual `freeze()`. |
| **Interoperabilitas Native** | Bridge berbasis JSON/JNI serialize-deserialize yang lambat (React Native, Flutter Platform Channels). | **Direct C/LLVM & ObjC Pointer ABI Interop.** Zero-overhead invocation via pointer translation langsung pada layer binary runtime. |

---

### 5. How (Workflow Detail)

Alur kerja implementasi arsitektur produksi KMP K2:

```
[Architectural Layer]           [Build & Target Compilation]            [Runtime Execution]
┌─────────────────────────┐     ┌───────────────────────────────┐      ┌───────────────────────────┐
│ Domain Core (K2 Logic)  │ ──► │ FIR Frontend Processing       │ ───► │ JVM Runtime (ART/HotSpot) │
│ - UseCases & Repos      │     │ (Parallel Semantics Check)    │      └───────────────────────────┘
│ - State Machines        │     └──────────────┬────────────────┘      ┌───────────────────────────┐
│ - Coroutine Flows       │                    ▼                       │ Apple Native Runtime      │
└───────────┬─────────────┘     ┌───────────────────────────────┐ ───► │ (Mach-O dyld, objc-arc,   │
            │                   │ Backend IR Desugaring         │      │  Darwin pthreads)         │
            ▼                   │ - Lowering Phases             │      └───────────────────────────┘
┌─────────────────────────┐     │ - Target ABI CodeGen          │      ┌───────────────────────────┐
│ Platform Interop Layer  │ ──► └──────────────┬────────────────┘ ───► │ Wasm/Browser Runtime      │
│ - expect/actual         │                    ▼                       │ (Wasm GC Engine)          │
│ - cinterop / def files  │     ┌───────────────────────────────┐      └───────────────────────────┘
└─────────────────────────┘     │ Packaging Artifacts           │
                                │ (.klib, .framework, .jar)     │
                                └───────────────────────────────┘
```

1. **Konfigurasi K2 Target:** Aktifkan compiler K2 secara mutlak pada `gradle.properties` menggunakan `kotlin.experimental.tryK2=true` (untuk Kotlin < 2.0) atau beralih ke toolchain Kotlin 2.0+ di mana K2 merupakan compiler *default*.
2. **Definisi Unified Models:** Implementasikan model data dan state engine di `commonMain` menggunakan Kotlinx Serialization dan Coroutines.
3. **Resolusi Platform API:**
   - Gunakan `expect`/`actual` **hanya** untuk lapisan abstraksi tipis (low-level primitives seperti hardware drivers, secure storage, dynamic crypto hardware).
   - Hindari mengekspos `actual` classes berukuran masif; gunakan interfaces dan dynamic dependency injection factory.
4. **Binary Linkage Configuration:**
   - Target iOS: Konfigurasi CocoaPods plugin atau Swift Package Manager (SPM) bridge dengan dynamic framework linkage untuk dev, static framework untuk release binary-size optimization.
5. **Memory Safety Hardening:** Konfigurasi custom GC parameters pada runtime flags jika memproses streaming batch beban tinggi.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur FIR K2 vs Legacy FE1.0
- **FE1.0 (BindingContext):** Seperti seorang arsitek yang menggambar denah rumah raksasa pada selembar kertas kanvas tunggal. Setiap kali ada perubahan kecil pada jendela kamar tidur, seluruh denah dari lantai 1 hingga atap harus divalidasi ulang secara bersamaan sambil mengunci meja kerja.
- **K2 (Frontend IR):** Seperti sistem perakitan modular prefabrikasi. Denah dipecah menjadi modul independen berstandar internasional (FIR phases). Struktur baja dipasang terlebih dahulu (signature analysis), kemudian dinding interior diisi secara paralel oleh beberapa kru tanpa saling memblokir (body analysis).

```
FE1.0 Pipeline (Bottleneck monolith):
[Source Code] ──► [PSI Parser] ──► [BindingContext (Global God Map)] ──► [Old Backend]
                                      │ (Single Thread Concurrency Lock)
                                      └─ High Memory Allocation & Thrashing

K2 FIR Pipeline (Staged, Modular, Streamlined):
[Source Code] ──► [Light-Tree] ──► [Raw FIR]
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
          [Phase 1: Imports]                         [Phase 2: Configs]
                   │                                           │
                   └─────────────────────┬─────────────────────┘
                                         ▼
                             [Phase 3: Supertypes]
                                         │
                                         ▼
                     [Phase 4..11: Signatures & Status]
                                         │ (Parallel Processing)
                                         ▼
                       [Phase 12: Function Body Resolution]
                                         │
                                         ▼
                                   [Unified IR]
                                         │
                  ┌──────────────────────┼──────────────────────┐
                  ▼                      ▼                      ▼
              [JVM IR]               [Native IR]             [JS IR]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Safe Expect/Actual Abstraction di K2

*File: `commonMain/kotlin/com/enterprise/core/crypto/EntropyProvider.kt`*
```kotlin
package com.enterprise.core.crypto

// Definisi kontrak platform via Interface (Best Practice dibanding expect class)
interface EntropyProvider {
    fun generateSecureSeed(byteCount: Int): ByteArray
}

expect fun getPlatformEntropyProvider(): EntropyProvider
```

*File: `jvmMain/kotlin/com/enterprise/core/crypto/EntropyProvider.jvm.kt`*
```kotlin
package com.enterprise.core.crypto

import java.security.SecureRandom

class JvmEntropyProvider : EntropyProvider {
    private val secureRandom = SecureRandom()

    override fun generateSecureSeed(byteCount: Int): ByteArray {
        val bytes = ByteArray(byteCount)
        secureRandom.nextBytes(bytes)
        return bytes
    }
}

actual fun getPlatformEntropyProvider(): EntropyProvider = JvmEntropyProvider()
```

*File: `nativeMain/kotlin/com/enterprise/core/crypto/EntropyProvider.native.kt`*
```kotlin
package com.enterprise.core.crypto

import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.usePinned
import platform.posix.open
import platform.posix.read
import platform.posix.close
import platform.posix.O_RDONLY

class PosixEntropyProvider : EntropyProvider {
    @OptIn(ExperimentalForeignApi::class)
    override fun generateSecureSeed(byteCount: Int): ByteArray {
        val buffer = ByteArray(byteCount)
        val fd = open("/dev/urandom", O_RDONLY)
        check(fd >= 0) { "Gagal mengakses /dev/urandom. Return code: $fd" }
        
        try {
            buffer.usePinned { pinned ->
                val bytesRead = read(fd, pinned.addressOf(0), byteCount.toULong())
                check(bytesRead.toLong() == byteCount.toLong()) { "Entropi tidak mencukupi" }
            }
        } finally {
            close(fd)
        }
        return buffer
    }
}

actual fun getPlatformEntropyProvider(): EntropyProvider = PosixEntropyProvider()
```

#### 7.2 Practical Example: Enterprise Reactive Transaction Engine dengan Atomic State Machine

*File: `commonMain/kotlin/com/enterprise/engine/TransactionEngine.kt`*
```kotlin
package com.enterprise.engine

import kotlinx.atomicfu.atomic
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

sealed interface TransactionState {
    data object Idle : TransactionState
    data class Processing(val txId: String) : TransactionState
    data class Success(val txId: String, val timestamp: Long) : TransactionState
    data class Failed(val txId: String, val reason: String) : TransactionState
}

data class TransactionPayload(val txId: String, val amountUnits: Long)

interface PlatformVault {
    suspend fun signPayload(data: ByteArray): ByteArray
}

class EnterpriseTransactionCoordinator(
    private val vault: PlatformVault,
    private val dispatcher: CoroutineDispatcher = Dispatchers.Default
) {
    // Thread-safe lock-free references compliant with K2 native memory model
    private val _currentState = MutableStateFlow<TransactionState>(TransactionState.Idle)
    val currentState: StateFlow<TransactionState> = _currentState.asStateFlow()

    private val executionLock = Mutex()
    private val executionCounter = atomic(0L)

    suspend fun executeTransaction(payload: TransactionPayload): Result<Unit> = withContext(dispatcher) {
        executionLock.withLock {
            if (_currentState.value is TransactionState.Processing) {
                return@withContext Result.failure(IllegalStateException("Engine sibuk memproses transaksi lain."))
            }

            _currentState.value = TransactionState.Processing(payload.txId)
            
            runCatching {
                // Simulasi validasi bisnis dan penandatanganan kriptografis native
                val rawData = "${payload.txId}:${payload.amountUnits}:${executionCounter.incrementAndGet()}".encodeToByteArray()
                val signature = vault.signPayload(rawData)
                
                // Emulasi transmisi jaringan
                delay(150)
                
                check(signature.isNotEmpty()) { "Tanda tangan biner tidak valid." }
                
                _currentState.value = TransactionState.Success(
                    txId = payload.txId,
                    timestamp = 1717986912000L // Deterministic enterprise epoch
                )
            }.onFailure { error ->
                _currentState.value = TransactionState.Failed(
                    txId = payload.txId,
                    reason = error.message ?: "Unknown Exception"
                )
            }
        }
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Tier-1 Digital Bank Offline-First Ledger Synchronization Engine
- **Volume:** 5 juta DAU (Daily Active Users), transaksi moneter offline-to-online syncing.
- **Tantangan Arsitektur:** 
  1. Penulisan core enkripsi double-ratchet dan audit ledger SQLite wajib identik antara iOS dan Android untuk menjamin konsistensi hash kriptografis balance.
  2. Implementasi legacy di Android (Kotlin) dan iOS (Swift) menghasilkan *divergent edge cases* di mana pembulatan floating point dan salt hashing berbeda $0.001\%$, mengakibatkan ledger mismatch pada jutaan baris rekonsiliasi.
  3. Kotlin/Native 1.9 dengan legacy memory manager sering mengalami `InvalidMutabilityException` saat background synchronization thread mencoba menulis data ke SQLite driver iOS.

#### Solusi Arsitektur Menggunakan KMP K2:
1. **Penyatuan Core Engine:** Memindahkan enkripsi ledger, SQLite database schema management, state synchronization engine, dan conflict resolution algorithms ke `shared/engine` (KMP).
2. **K2 Compiler Rollout:** Migrasi ke Kotlin 2.0+ K2 compiler. Menghapus semua kode `freeze()`, beralih ke `AtomicRef` dari `kotlinx.atomicfu` dan standard Kotlin Coroutines Mutex.
3. **Swift Direct Export via KMP Framework:** Menghasilkan static `.framework` Mach-O binary dengan Objective-C interop header.

```
                  ┌──────────────────────────────────────────────┐
                  │            Client Edge Interface             │
                  │   (Android Jetpack Compose / iOS SwiftUI)    │
                  └──────────────┬────────────────┬──────────────┘
                                 │                │
            (Direct UI Binding)  │                │ (SwiftUI Flow Observation)
                                 ▼                ▼
                  ┌──────────────────────────────────────────────┐
                  │         Shared KMP Core Architecture         │
                  │  ┌────────────────────────────────────────┐  │
                  │  │       Domain Flow State Machine        │  │
                  │  └───────────────────┬────────────────────┘  │
                  │                      ▼                       │
                  │  ┌────────────────────────────────────────┐  │
                  │  │      Ledger Cryptographic Engine       │  │
                  │  │ (K2 Uniform Cross-Target Semantics)    │  │
                  │  └───────────────────┬────────────────────┘  │
                  │                      ▼                       │
                  │  ┌────────────────────────────────────────┐  │
                  │  │       SQLDelight / Room KMP DB         │  │
                  │  └───────────────────┬────────────────────┘  │
                  └──────────────────────┼───────────────────────┘
                                         │
                       ┌─────────────────┴─────────────────┐
                       ▼                                   ▼
          ┌────────────────────────┐          ┌────────────────────────┐
          │      JVM Core (ART)    │          │  Darwin Native Core    │
          │ - java.security        │          │ - Apple Security.frame │
          │ - Android SQLite API   │          │ - POSIX SQLite link    │
          └────────────────────────┘          └────────────────────────┘
```

#### Hasil Metrik Produksi:
- **Ledger Inconsistency Rate:** Turun drastis dari 0.001% ke 0.00000% (Zero Divergence).
- **Time to Market:** Fitur sinkronisasi perbankan baru hanya diimplementasikan 1 kali di `sharedMain`.
- **Compiler Performance:** Peningkatan build time development iOS/Android shared module dari 3 menit 40 detik menjadi 1 menit 12 detik berkat K2 Frontend Pipeline.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Monolithic Expect / Actual Class** | Terlihat natural bagi developer Java/OOP lama. | Tight coupling. Sulit dilakukan mocking/unit testing di test module. K2 compiler mengharuskan signature identik secara ketat hingga default arguments. |
| **Interface + Factory Delegation** | Loose coupling. Sangat mudah di-mock dalam testing suite commonMain. | Sedikit overhead virtual method call lookup table (V-table dispatch), boilerplate injection code meningkat. |
| **Static Framework Linkage (iOS)** | Eksekusi runtime lebih cepat (dyld tidak butuh symbol relocation saat cold app start). Dead code elimination via LLVM LTO (*Link Time Optimization*). | Ukuran biner binary akhir membesar jika di-embed ke beberapa dynamic modules (duplikasi symbols). Build time release lebih lama. |
| **Dynamic Framework Linkage (iOS)** | Build phase cepat, binary sharing antar targets (misal App Extension + Main App). | Cold start aplikasi sedikit terhambat karena Apple dynamic loader (`dyld`) harus mereferensikan library symbols saat startup. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Memory Leak pada Swift/Objective-C Callback Bridge
*Masalah:* Menyimpan lambda Kotlin di Swift UI Controller menyebabkan circular reference (ARC Swift dan Kotlin GC saling menahan referensi).
```kotlin
// SALAH: Strong reference cycle terbentuk
class NativeCallbackManager {
    var onComplete: (() -> Unit)? = null
}
```
*Solusi:* Putuskan siklus referensi secara eksplisit atau gunakan weak wrapper:
```kotlin
// BENAR: Menggunakan pola lifecycle-aware detachment
class NativeCallbackManager {
    private var onComplete: (() -> Unit)? = null

    fun registerCallback(callback: () -> Unit) {
        this.onComplete = callback
    }

    fun trigger() {
        onComplete?.invoke()
    }

    fun detach() {
        // Wajib dipanggil saat Swift deinit/viewDidDisappear
        this.onComplete = null
    }
}
```

#### 10.2 Crash Akses C-Pointer Menggunakan K2 Native Engine
*Masalah:* Mengakses native pointer setelah memory block dialokasikan dan di-free di luar cakupan pinning/arena.
*Troubleshooting Step:*
1. Periksa penggunaan `kotlinx.cinterop.Arena`. Jangan pernah mengembalikan pointer C keluar dari lambda block `memScoped { ... }`.
2. Gunakan `usePinned` pada `ByteArray` Kotlin saat mempassing memory buffer ke C API untuk mencegah Garbage Collector memindahkan memory block selama POSIX function berjalan.

#### 10.3 Inkompatibilitas ABI karena Perubahan Default Parameter pada K2
*Masalah:* K2 menerapkan resolusi default parameters yang sangat ketat pada `expect`/`actual`. Jika Anda menambahkan default parameter pada `expect` tetapi mendefinisikannya kembali pada `actual`, compiler K2 akan melempar:
`Error: actual function cannot have default argument values`.
*Solusi:* Definisikan default parameter **hanya** pada deklarasi `expect`. File deklarasi `actual` tidak boleh menyertakan nilai default.

---

### 11. Best Practices (Production Checklist)

- [ ] **K2 Flag Enforcement:** Pastikan Gradle properties mengaktifkan compiler K2 tanpa fallback:
  ```properties
  kotlin.suppressVersionWarnings=false
  kotlin.experimental.tryK2=false # Hapus jika sudah di Kotlin >= 2.0.0
  ```
- [ ] **Hierarchical Source Sets:** Hindari membuat source set manual. Gunakan struktur default modern:
  ```kotlin
  kotlin {
      applyDefaultHierarchyTemplate()
  }
  ```
- [ ] **Static/Dynamic Framework Strategy:** Tentukan konfigurasi build type secara presisi pada `build.gradle.kts`:
  ```kotlin
  listOf(
      iosX64(),
      iosArm64(),
      iosSimulatorArm64()
  ).forEach { target ->
      target.binaries.framework {
          baseName = "SharedEngine"
          isStatic = true // Static framework untuk release performance
      }
  }
  ```
- [ ] **Strict Memory Usage via Coroutine Context:** Pastikan thread dispatcher di native menggunakan bounded context (`Dispatchers.Default` atau custom IO dispatcher KMP).
- [ ] **Prevent Platform API Leakage:** Common module tidak boleh bergantung pada runtime library platform. Abstraksi OS harus 100% terisolasi di dalam layer internal.

---

### 12. Hands-on Practice (Implementasi Bertahap)

Implementasikan project shared module enterprise pada folder: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Gradle Script Enterprise KMP
*File: `hands-on/m02/build.gradle.kts`*
```kotlin
plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.kotlinx.serialization)
}

kotlin {
    applyDefaultHierarchyTemplate()

    jvm {
        testRuns["test"].executionTask.configure {
            useJUnitPlatform()
        }
    }

    listOf(
        iosX64(),
        iosArm64(),
        iosSimulatorArm64()
    ).forEach { iosTarget ->
        iosTarget.binaries.framework {
            baseName = "EnterpriseTelemetry"
            isStatic = true
            export(libs.kotlinx.coroutines.core)
        }
    }

    sourceSets {
        commonMain.dependencies {
            implementation(libs.kotlinx.coroutines.core)
            implementation(libs.kotlinx.serialization.json)
            implementation(libs.kotlinx.atomicfu)
        }
        commonTest.dependencies {
            implementation(kotlin("test"))
            implementation(libs.kotlinx.coroutines.test)
        }
        jvmMain.dependencies {
            implementation(libs.slf4j.api)
        }
    }
}
```

#### Langkah 2: Pembuatan Abstraksi File Persistence
*File: `hands-on/m02/src/commonMain/kotlin/com/enterprise/telemetry/DiskJournal.kt`*
```kotlin
package com.enterprise.telemetry

expect class PlatformDiskJournal() {
    fun appendLine(path: String, line: String)
    fun readLines(path: String): List<String>
}
```

*File: `hands-on/m02/src/jvmMain/kotlin/com/enterprise/telemetry/DiskJournal.jvm.kt`*
```kotlin
package com.enterprise.telemetry

import java.io.File

actual class PlatformDiskJournal actual constructor() {
    actual fun appendLine(path: String, line: String) {
        File(path).appendText("$line\n", Charsets.UTF_8)
    }

    actual fun readLines(path: String): List<String> {
        val file = File(path)
        if (!file.exists()) return emptyList()
        return file.readLines(Charsets.UTF_8)
    }
}
```

*File: `hands-on/m02/src/nativeMain/kotlin/com/enterprise/telemetry/DiskJournal.native.kt`*
```kotlin
package com.enterprise.telemetry

import kotlinx.cinterop.*
import platform.posix.*

actual class PlatformDiskJournal actual constructor() {
    @OptIn(ExperimentalForeignApi::class)
    actual fun appendLine(path: String, line: String) {
        val file = fopen(path, "a") ?: throw IllegalStateException("Cannot open file: $path")
        try {
            val content = "$line\n"
            fputs(content, file)
        } finally {
            fclose(file)
        }
    }

    @OptIn(ExperimentalForeignApi::class)
    actual fun readLines(path: String): List<String> {
        val file = fopen(path, "r") ?: return emptyList()
        val result = mutableListOf<String>()
        try {
            memScoped {
                val bufferSize = 1024
                val buffer = allocArray<ByteVar>(bufferSize)
                var currentLine = ""
                while (fgets(buffer, bufferSize, file) != null) {
                    val chunk = buffer.toKString()
                    currentLine += chunk
                    if (currentLine.endsWith("\n")) {
                        result.add(currentLine.trimEnd('\n'))
                        currentLine = ""
                    }
                }
                if (currentLine.isNotEmpty()) {
                    result.add(currentLine)
                }
            }
        } finally {
            fclose(file)
        }
        return result
    }
}
```

#### Langkah 3: Implementation Engine di Common Main
*File: `hands-on/m02/src/commonMain/kotlin/com/enterprise/telemetry/TelemetryEngine.kt`*
```kotlin
package com.enterprise.telemetry

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

class TelemetryEngine(
    private val journal: PlatformDiskJournal,
    private val journalPath: String,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
) {
    private val writeMutex = Mutex()
    private val _eventStream = MutableSharedFlow<String>(extraBufferCapacity = 64)
    val eventStream: SharedFlow<String> = _eventStream.asSharedFlow()

    init {
        scope.launch {
            _eventStream.collect { rawPayload ->
                writeMutex.withLock {
                    journal.appendLine(journalPath, rawPayload)
                }
            }
        }
    }

    fun track(eventName: String, attributes: Map<String, String>) {
        val serialized = "$eventName|${attributes.entries.joinToString(",") { "${it.key}=${it.value}" }}"
        _eventStream.tryEmit(serialized)
    }

    suspend fun getPersistedLogs(): List<String> = writeMutex.withLock {
        journal.readLines(journalPath)
    }
}
```

---

### 13. Exercise

#### Level: Easy
Implementasikan expect/actual function `getSystemUpTimeMillis(): Long` yang mengakses `SystemClock.uptimeMillis()` di Android/JVM dan `clock_gettime(CLOCK_MONOTONIC)` di target iOS/Native.

#### Level: Medium
Buat sebuah KMP thread-safe cache engine `EnterpriseMemoryCache<K : Any, V : Any>` dengan eviction policy berbasis Least-Recently-Used (LRU). Engine harus dapat digunakan secara konkuren oleh ribuan coroutines secara simultan pada target Kotlin/JVM dan Kotlin/Native tanpa terjadi race condition.

#### Level: Hard
Kembangkan Custom Native Pointer Arena wrapper yang mengalokasikan memory block di POSIX C Runtime, mengisi array of structures (misal: koordinat Geo-Spatial $X, Y, Z$ bertipe data Float64), memproses matrix transformation langsung via pointer arithmetic di dalam runtime C, dan mengembalikan memory mapped projection langsung ke Kotlin tanpa alokasi memori berlebih di heap Kotlin/Native.

---

### 14. Challenge

**Tantangan Sistem Finansial: Zero-Allocation Biometric Stream Linker**
Sebuah bank multinasional meminta arsitektur modul biner KMP yang menghubungkan pembaca sidik jari hardware (eksternal POSIX library via C-interop) ke SQLite Cipher database.

*Ketentuan Arsitektur:*
1. Data biner raw fingerprint template tidak boleh di-copy ke dalam heap garbage collection Kotlin (Heap memory must be 0-bytes allocated for data security against cold-boot attacks).
2. Data template harus dioperasikan langsung menggunakan direct native memory pointers (`CPointer<ByteVar>`).
3. State machine verifikasi harus ditulis murni pada `commonMain` menggunakan K2 compiler contracts untuk memastikan bahwa fungsi autentikasi hanya dapat dipanggil jika memory block native telah diverifikasi status enkripsinya.
4. Framework harus dikompilasi ke iOS Dynamic/Static Framework dan Android AAR, dengan integrasi test suite otomatis pada platform host.
5. Sediakan benchmark report yang membuktikan tidak ada interupsi Stop-the-World GC selama throughput streaming mencapai 120 FPS frame parsing.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara representasi Light-Tree pada K2 dan PSI pada compiler FE1.0?**
   - *Jawaban:* PSI membuat full structural object tree di memory IntelliJ platform yang berat dan persistent, sedangkan Light-Tree pada K2 adalah tree representasi parsing yang ringan, berorientasi event, dan hemat alokasi memori untuk mode kompilasi batch.
2. **Apakah fungsi `freeze()` masih wajib dipanggil pada Kotlin/Native modern di Kotlin 2.0?**
   - *Jawaban:* Tidak. `freeze()` sudah dideprecate dan tidak lagi diperlukan karena runtime Kotlin/Native modern telah mendukung Shared Mutable State secara native menggunakan Concurrent Mark and Sweep (CMS) GC.
3. **Mengapa file metadata `.klib` tidak berisi JVM bytecode?**
   - *Jawaban:* Karena `.klib` dirancang untuk Kotlin Multiplatform frontend/backend consumption yang berisi serialized IR (Unified IR) dan deklarasi metadata kompilasi, bukan bytecode akhir target eksekusi spesifik JVM.
4. **Pada fase kompilasi mana desugaring (penyederhanaan sintaksis) terjadi di K2?**
   - *Jawaban:* Desugaring terjadi lebih awal pada fase FIR (Frontend IR) sebelum IR diserahkan ke backend spesifik platform, memastikan konsistensi semantik di semua target.
5. **Dapatkah kita mendefinisikan nilai argumen default pada fungsi `actual` jika sudah ada pada `expect`?**
   - *Jawaban:* Tidak, nilai argumen default hanya boleh dideklarasikan pada fungsi `expect`.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Jelaskan mekanisme Stop-the-World (STW) pada Garbage Collector Kotlin/Native generasi baru!**
   - *Jawaban:* STW pause pada Native CMS GC terjadi secara sangat singkat, terutama pada saat penentuan *root set* awal dan resolusi siklus final reference tracking, sedangkan fase penelusuran (marking) dan pembersihan (sweeping) berjalan konkuren bersama background mutator threads.
7. **Bagaimana K2 Compiler menyelesaikan masalah kompilasi lambat akibat recursive type inference?**
   - *Jawaban:* Melalui arsitektur FIR multi-phase yang memisahkan resolusi signature fungsi dari body functions, sehingga type-inference dependencies diisolasi per unit pemanggilan tanpa melakukan resolving global AST yang saling mengunci.
8. **Apa peran dari `usePinned` dalam manipulasi array Kotlin saat melakukan C-interop?**
   - *Jawaban:* `usePinned` mem-pin memory buffer objek Kotlin di heap agar Garbage Collector tidak memindahkan alamat fisiknya saat pointer array tersebut diakses oleh C-runtime secara langsung.
9. **Bagaimana Hierarchical Multiplatform Project menghindari duplikasi implementasi antara platform yang sekeluarga (misal: iOS dan macOS)?**
   - *Jawaban:* Melalui pengelompokan source set hirarkis (seperti `appleMain`), di mana kode yang memanggil API Foundation/Darwin dikompilasi sekali ke dalam intermediate klib yang diwarisi oleh `iosMain` dan `macosMain`.
10. **Apa implikasi menggunakan `isStatic = true` vs `isStatic = false` pada output iOS framework?**
    - *Jawaban:* `isStatic = true` menghasilkan static library yang di-link ke final application binary pada build time (start time lebih cepat, optimasi dead code LLVM), sedangkan dynamic framework (`false`) ditautkan pada launch time oleh dynamic linker OS (start time terpengaruh, binary sharing mudah).

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario:** Aplikasi enterprise Anda mengalami crash `SIGSEGV (Address boundary error)` secara acak hanya di perangkat iOS produksi, tepat setelah operasi pemanggilan fungsi C-interop selesai dijalankan. Di Android dan unit testing JVM, kode berjalan 100% normal. Apa root cause arsitekturalnya dan bagaimana mengatasinya?
    - *Solusi & Analisis:* Root cause paling mungkin adalah penggunaan pointer yang dialokasikan di dalam scope `memScoped { ... }` yang keluar dari block lifecyclenya (Dangling Pointer), atau pointer array dialokasikan via unpinned Kotlin array yang kemudian dipindahkan posisinya oleh Kotlin/Native CMS GC saat sweeping thread berjalan. Solusinya: Pastikan memory native dialokasikan menggunakan unmanaged arena jika ingin bertahan di luar block, atau bungkus buffer Kotlin menggunakan `.usePinned { ... }` sebelum pointer diteruskan ke fungsi POSIX C.

12. **Skenario:** Build server enterprise Anda mengalami lonjakan penggunaan memory (OOM Heap) dan lambat saat mengompilasi module KMP besar yang memiliki ratusan klib dependencies setelah beralih ke K2. Analisis parameter toolchain yang harus disesuaikan!
    - *Solusi & Analisis:* Pada K2, proses paralelisme backend IR generation mengonsumsi thread dan RAM lebih tinggi jika JVM garbage collector compiler tidak dioptimalkan. Parameter tuning: (1) Naikkan Gradle daemon max heap size di `gradle.properties`: `org.gradle.jvmargs=-Xmx8g -XX:+UseG1GC`. (2) Aktifkan native compilation memory optimization: `kotlin.native.binary.prelinkCaches=enable`. (3) Gunakan Kotlin compiler daemon memory management: `kotlin.daemon.jvmargs=-Xmx4g`.

13. **Skenario:** Tim iOS mengeluhkan bahwa method Coroutines Flow yang diekspor dari KMP Shared framework ke Swift menghasilkan interface yang tidak ergonomis (muncul tipe wrapper opaque yang sulit diobservasi di SwiftUI). Arsitektur bridge apa yang harus didesain di layer KMP?
    - *Solusi & Analisis:* Swift/Objective-C interop engine KMP tidak memetakan interface generics `Flow<T>` secara langsung ke Combine atau `AsyncSequence` Swift secara native. Arsitektur solusinya: Buat adapter layer di `appleMain` (atau wrapper class) yang mengonversi `Flow<T>` menjadi wrapper class yang mengekspos callback berbasis cancellation token (seperti `subscribe(onEach: (T) -> Unit, onCompletion: () -> Unit): Disposable`), atau gunakan library arsitektur KMP modern (misal SKIE) yang secara otomatis melakukan rewrite pada LLVM IR backend level untuk mengubah `Flow` menjadi Swift native `AsyncSequence`.

---

### 16. Summary

- **Pipeline K2 (Frontend IR):** Mengeliminasi bottleneck arsitektur FE1.0 BindingContext dengan Light-Tree parsing dan 12-fase FIR processing, menghasilkan kompilasi yang signifikan lebih cepat, isolasi memori rendah, serta konsistensi IR di semua target.
- **Model Konkurensi KMP Modern:** Runtime Kotlin/Native modern telah beralih ke Shared Mutable State dengan Garbage Collector bertipe Concurrent Mark and Sweep (CMS), menghilangkan kebutuhan isolasi state berbasis freeze legacy.
- **Arsitektur Produksi:** Arsitektur KMP enterprise berfokus pada isolasi Business Logic di `commonMain`, membatasi `expect`/`actual` pada boundary tipis menggunakan Interface Delegation, dan mengoptimalkan binary linkage Mach-O/ELF untuk target platform akhir.