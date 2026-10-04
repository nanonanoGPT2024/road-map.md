# BAB 10 MODULE 01: KOTLIN MULTIPLATFORM & K2 COMPILER

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 02-Programming-Languages
*   **Mata Pelajaran:** Advanced Kotlin Engineering
*   **Modul:** Bab 10 Module 01: Kotlin Multiplatform (KMP) & K2 Compiler Architecture
*   **Prasyarat:** Pemahaman mendalam tentang Kotlin OOP, Functional Programming, Coroutines & Asynchronous Programming, Gradle Build Scripting (Kotlin DSL), serta dasar-dasar arsitektur sistem operasi (JVM, POSIX/Darwin, Native).
*   **Tingkat Kesulitan:** Tingkat Lanjut (Advanced / Level 400)
*   **Alokasi Waktu Pembelajaran:** 8 Jam Teori, 12 Jam Praktikum & Bedah Kasus
*   **Versi Target:** Kotlin 2.0+ (Default K2 Compiler), Gradle 8.5+, JDK 21

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:

1.  **Menganalisis** arsitektur K2 Compiler Pipeline (Frontend IR / FIR, Unified Backend IR, dan Desugaring Engine) serta membedakannya secara struktural dari Frontend 1.0 (FE 1.0).
2.  **Merancang dan Mengonfigurasi** Hierarchical Source Sets pada Gradle DSL untuk proyek multiplatform yang menargetkan JVM, Android, iOS (Native), dan WebAssembly (Wasm).
3.  **Mengimplementasikan** mekanisme abstraksi kode platform silang menggunakan pola `expect`/`actual` serta memadukannya dengan Dependency Injection berbasis Interface.
4.  **Mendiagnosis dan Mengatasi** runtime constraints pada Kotlin/Native, termasuk New Memory Manager (Tracing Garbage Collector) dan Swift/Objective-C interoperability boundaries.
5.  **Mengoptimasi** siklus kompilasi dan ukuran biner multiplatform menggunakan Link-Time Optimization (LTO), Dead Code Elimination (DCE), dan konfigurasi caching Gradle terdistribusi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: "Code Reuse" vs "Shared Logic, Native Execution"

Tradisi pengembangan platform silang klasik (seperti Cordova atau WebView hybrid) beroperasi dengan asumsi **pembungkusan (wrapping)**: menulis satu aplikasi web lalu menjalankannya di dalam container platform. Solusi cross-platform modern berbasis VM (seperti Flutter) menggunakan pendekatan **re-rendering kanvas**: mengabaikan sistem UI asli dan menggambar seluruh komponen piksel demi piksel menggunakan engine grafis kustom.

```
Pendekatan Hybrid:      [ Web App ] -> [ WebView Bridge ] -> [ Platform OS ]
Pendekatan Engine:      [ Dart Logic + Custom Render Engine (Impeller/Skia) ] -> [ Canvas OS ]
Pendekatan KMP:         [ Shared Kotlin Business Logic ]
                                      |
                 +--------------------+--------------------+
                 |                                         |
                 v                                         v
         [ Transpiled/Bytecode ]                  [ Native Binary ]
         (JVM Bytecode via K2)                 (Mach-O/ELF via LLVM)
                 |                                         |
                 v                                         v
       [ Native Android Runtime ]                [ iOS Darwin Kernel ]
       (Native Jetpack Compose)                  (Native SwiftUI)
```

Kotlin Multiplatform (KMP) mengadopsi mental model **Bukan-UI-Tunggal (Non-Monolithic UI)**. KMP memisahkan logika bisnis (state, jaringan, basis data, analitik) dari subsistem presentasi visual. Logika dieksekusi secara native pada setiap target:
*   Pada **JVM/Android**, kode Kotlin dikompilasi menjadi bytecode Java standar (`.class`).
*   Pada **iOS/macOS**, kode Kotlin dikompilasi melalui LLVM langsung menjadi biner mesin native (`.a`, `.framework`, `.xcframework`).
*   Pada **Web**, kode Kotlin dikompilasi menjadi biner Wasm atau JavaScript AST.

### Mental Model Kompiler K2: Dekomposisi FIR

Kompiler K2 harus dipahami sebagai prosesor dua tahap independen yang dihubungkan oleh Intermediate Representation (IR). K2 meninggalkan model lama *Resolved Binding Trace* (yang menyimpan informasi semantik di memori dalam tabel global raksasa) dan beralih ke **Tree-based FIR (Frontend Intermediate Representation)**. Mental model K2 adalah aliran transformasi data:

$$\text{Source Code} \xrightarrow{\text{Lex/Parse}} \text{Raw AST} \xrightarrow{\text{FIR Building}} \text{FIR Trees} \xrightarrow{\text{Type Resolution / Contracts}} \text{Desugared FIR} \xrightarrow{\text{Backend IR Generator}} \text{Unified IR} \xrightarrow{\text{Target Emitter}} \text{Artifact}$$

K2 Compiler memperlakukan kompilasi platform silang sebagai pohon resolusi tipe modular: tipe data pada `commonMain` diselesaikan secara deklaratif terlebih dahulu, lalu diikat (*bound*) secara statis ke platform target spesifik pada fase backend.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Pipeline Kompilasi K2 Compiler (Unified Multiplatform Pipeline)

```
+-----------------------------------------------------------------------------------+
|                              KOTLIN SOURCE FILES (.kt)                            |
|             (commonMain, jvmMain, androidMain, iosMain, nativeMain, wasmMain)     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        FRONTEND K2 (FIR - Frontend IR)                            |
|  - Fast Lexer & Parser (Parallel File Processing)                                 |
|  - Raw FIR Generation                                                             |
|  - Resolution Stages (Imports, Supertypes, Parameter Status, Types, Contracts)   |
|  - Control Flow Analysis (CFA) & Smart Cast Calculation                           |
|  - Type-safe diagnostics (Checkers)                                               |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                           BACKEND IR GENERATOR (FIR2IR)                           |
|  - Desugaring of Language Features (Coroutines, Lambdas, Inline Classes)           |
|  - Expect/Actual Static Linkage & Verification                                    |
|  - Generation of Unified Kotlin IR (Intermediate Representation)                  |
+-----------------------------------------------------------------------------------+
                                         |
        +--------------------------------+--------------------------------+
        |                                |                                |
        v                                v                                v
+----------------+              +----------------+              +-------------------+
| JVM IR BACKEND |              | NATIVE BACKEND |              | WASM/JS BACKEND   |
| (K2 -> Bytecode|              | (K2 -> LLVM IR)|              | (K2 -> Wasm/JS IR)|
+----------------+              +----------------+              +-------------------+
        |                                |                                |
        v                                v                                v
+----------------+              +----------------+              +-------------------+
| Java Bytecode  |              | LLVM Bitcode   |              | WebAssembly (Wasm)|
| (.class / .jar)|              | Generator      |              | (.wasm) / JS Files|
+----------------+              +----------------+              +-------------------+
                                         |
                                         v
                                +----------------+
                                | Clang / LLVM   |
                                | Toolchain Linker
                                +----------------+
                                         |
                                         v
                                +----------------+
                                | Native Binary  |
                                | (.klib, .a,    |
                                |  .xcframework) |
                                +----------------+
```

### Hierarki Source Set Standar KMP

```
                         +-----------------------+
                         |      commonMain       |
                         |  (Zero Platform Dep)  |
                         +-----------------------+
                                     |
               +---------------------+---------------------+
               |                                           |
               v                                           v
     +-------------------+                       +-------------------+
     |   concurrentMain  |                       |     nativeMain    |
     |   (JVM + Native)  |                       |  (C-Interop Base) |
     +-------------------+                       +-------------------+
               |                                           |
        +------+------+                             +------+------+
        |             |                             |             |
        v             v                             v             v
  +-----------+ +-----------+                 +-----------+ +-----------+
  |  jvmMain  | |androidMain|                 | appleMain | | linuxMain |
  +-----------+ +-----------+                 +-----------+ +-----------+
                                                    |
                                             +------+------+
                                             |             |
                                             v             v
                                       +-----------+ +-----------+
                                       |  iosMain  | | macosMain |
                                       +-----------+ +-----------+
                                             |
                                      +------+------+
                                      |             |
                                      v             v
                                +-----------+ +-----------+
                                |iosArm64   | |iosSimulator
                                |Main       | |Arm64Main  |
                                +-----------+ +-----------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. FIR (Frontend Intermediate Representation) Engine

Sebelum Kotlin 2.0 (Frontend 1.0), kompilator menggunakan struktur data berbasis *BindingContext* yang memiliki kompleksitas waktu dan memori tinggi akibat banyaknya *hashmap lookup* interdependen yang dieksekusi secara rekursif. Karakteristik internal arsitektur K2/FIR:

*   **Pohon AST Semantik Parsial (Semantic Trees):** FIR adalah pohon semantik bertipe parsial yang secara progresif menyelesaikan tipe (*type-resolution phases*) melalui tahapan yang disebut **Phased Resolution Compiler Passes**.
*   **Struktur Imutabel:** Mengurangi secara signifikan fragmentasi heap pada daemon kompilator.
*   **Parallel File Level Analysis:** File dalam modul yang sama dianalisis secara independen di thread yang berbeda berkat ketiadaan status pembeda global (*no global mutable context*).

### 2. Resolusi Statis `expect` dan `actual`

Deklarasi `expect` dan `actual` diselesaikan secara murni pada waktu kompilasi (*compile-time binding*), **bukan** via mekanisme polimorfisme runtime virtual call table (vtable):

*   Ketika kompilator memproses target (misalnya iOS), backend native mencocokkan Fully Qualified Name (FQN) dan tanda tangan tipe (*type signature*) dari `expect` declaration dengan `actual` declaration.
*   Jika implementasi `actual` tidak ditemukan untuk modul target tertentu, fase `FIR2IR` melempar kesalahan kompilasi: `Expected declaration must have an actual declaration in platform module`.
*   Pada level biner, tidak ada overhead pemanggilan fungsi tambahan; fungsi dieksekusi sebagai native symbol atau direct JVM bytecode `invokestatic`/`invokevirtual`.
*   Kotlin 2.0 menyelaraskan aturan: deklarasi `actual typealias` divalidasi secara ketat untuk mencegah kebocoran invariant ABI platform silang.

### 3. Native Memory Architecture (Kotlin/Native Modern)

Mulai dari runtime baru yang kini menjadi satu-satunya model pada K2:

*   **Freezed State Ditinggalkan:** Aturan *legacy* `freeze()` yang membekukan objek untuk membagikannya antar-thread telah dihapus secara total.
*   **Shared Heap:** Objek Kotlin dapat dialokasikan dan dibagikan secara bebas di thread mana pun tanpa memicu `InvalidMutabilityException`.
*   **Tracing Garbage Collector:** Menggunakan Stop-the-World (STW) GC non-blocking berbasis CMS (Concurrent Mark & Sweep) paralel.
*   **Interop ARC Bridge:** Ketika objek Kotlin diekspos ke iOS (Objective-C/Swift), mereka dibungkus dalam representasi wrapper pointer berbasis Apple ARC (Automatic Reference Counting). Siklus referensi antara ARC dan Kotlin GC ditangani melalui mekanisme *external reference root tracking*.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Unified Backend IR (Intermediate Representation)

Backend IR adalah representasi perantara universal yang memungkinkan satu optimasi kompiler (*lowering passes*) dapat diaplikasikan ke semua target. Contoh *lowering* meliputi:
*   Transformasi *inline functions* dan parameter *reified*.
*   Penurunan status *coroutine state machines* (mengubah suspensi fungsi menjadi implementasi class turunan `ContinuationImpl` berbasis tabel `switch-case`).
*   Optimasi struktur data `value class`.

Karena backend JVM, Native, dan JS/Wasm berbagi representasi IR yang sama, penambahan fitur sintaksis baru pada bahasa Kotlin secara otomatis tersedia di semua target kompilasi tanpa perlu merekayasa ulang generator biner dari awal.

### 2. Desugaring Language Features pada K2

Proses desugaring pada K2 memecah abstraksi tingkat tinggi Kotlin ke instruksi primitif:

```
[Kotlin: inline value class Token(val value: String)]
                          |
             (K2 IR Lowering Pass)
                          |
                          v
[JVM: Direct java.lang.String reference with static method transformations]
[Native: Direct unboxed const char* pointer wrapper without heap allocation]
```

Smart-cast pada K2 menggunakan algoritma pelacakan *flow-sensitive analysis* baru. Algoritma ini memvalidasi reassignment dalam ekspresi lambda, pemecahan kondisi boolean bersarang, dan kontrak platform silang yang sebelumnya menghasilkan kegagalan inferensi (*type inference failed*) pada FE 1.0.

### 3. ABI Compatibility dan Metadata (`.klib`)

Ketika sebuah pustaka KMP dikompilasi untuk digunakan oleh modul lain:
*   Target JVM menghasilkan `.jar` standar dengan metadata Kotlin termuat di annotation `@Metadata`.
*   Target Native dan Wasm menghasilkan file biner `.klib` (Kotlin Library).
*   File `.klib` berisi:
    1.  Bytecode IR ter-serialisasi (Protobuf format).
    2.  Metadata manifest K2 Compiler.
    3.  Header deklarasi tipe yang diakses oleh linker K2 dan LLVM.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi fundamental struktur multiplatform hierarkis: mendefinisikan layer enkripsi simetris menggunakan algoritma AES-GCM, di mana `commonMain` menetapkan kontrak tipe native melalui `expect`, sedangkan `jvmMain` dan `iosMain` mengikat implementasi platform engine kriptografi secara langsung.

### 1. Struktur Modul Gradle (`build.gradle.kts`)

```kotlin
plugins {
    alias(libs.plugins.kotlinMultiplatform)
    alias(libs.plugins.androidLibrary)
}

kotlin {
    // 1. Target JVM Standar (Backend / CLI)
    jvm {
        testRuns["test"].executionTask.configure {
            useJUnitPlatform()
        }
    }

    // 2. Target Android
    androidTarget {
        compilations.all {
            kotlinOptions {
                jvmTarget = "21"
            }
        }
    }

    // 3. Target Apple Native (iOS 64-bit devices & Simulator)
    listOf(
        iosArm64(),
        iosSimulatorArm64()
    ).forEach { target ->
        target.binaries.framework {
            baseName = "SecureCryptoCore"
            isStatic = true
        }
    }

    // 4. Hierarchical Source Set Configuration
    sourceSets {
        commonMain.dependencies {
            implementation(libs.kotlinx.coroutines.core)
        }

        commonTest.dependencies {
            implementation(libs.kotlin.test)
        }

        val jvmAndAndroidMain = create("jvmAndAndroidMain") {
            dependsOn(commonMain.get())
        }

        jvmMain.get().dependsOn(jvmAndAndroidMain)
        androidMain.get().dependsOn(jvmAndAndroidMain)

        iosMain.get().dependsOn(commonMain.get())
    }
}
```

### 2. Common Code: Kontrak `expect` (`commonMain/PlatformCrypto.kt`)

```kotlin
package com.enterprise.crypto

/**
 * Metadata representasi data terenkripsi.
 */
data class EncryptedPayload(
    val ciphertext: ByteArray,
    val iv: ByteArray,
    val authenticationTag: ByteArray
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is EncryptedPayload) return false
        return ciphertext.contentEquals(other.ciphertext) &&
                iv.contentEquals(other.iv) &&
                authenticationTag.contentEquals(other.authenticationTag)
    }

    override fun hashCode(): Int {
        var result = ciphertext.contentHashCode()
        result = 31 * result + iv.contentHashCode()
        result = 31 * result + authenticationTag.contentHashCode()
        return result
    }
}

/**
 * Abstraksi platform kriptografi untuk AES-256 GCM.
 */
expect class PlatformAESEncryptor(secretKeyBytes: ByteArray) {
    fun encrypt(plaintext: ByteArray): EncryptedPayload
    fun decrypt(payload: EncryptedPayload): ByteArray
}
```

### 3. Implementasi Target JVM (`jvmMain/PlatformCrypto.kt`)

```kotlin
package com.enterprise.crypto

import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec
import java.security.SecureRandom

actual class PlatformAESEncryptor actual constructor(secretKeyBytes: ByteArray) {
    private val keySpec = SecretKeySpec(secretKeyBytes, "AES")
    private val secureRandom = SecureRandom()

    private companion object {
        const val GCM_TAG_LENGTH_BITS = 128
        const val IV_LENGTH_BYTES = 12
        const val AES_GCM_NO_PADDING = "AES/GCM/NoPadding"
    }

    actual fun encrypt(plaintext: ByteArray): EncryptedPayload {
        val iv = ByteArray(IV_LENGTH_BYTES)
        secureRandom.nextBytes(iv)

        val cipher = Cipher.getInstance(AES_GCM_NO_PADDING)
        val spec = GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv)
        cipher.init(Cipher.ENCRYPT_MODE, keySpec, spec)

        val cipherWithTag = cipher.doFinal(plaintext)
        
        // Pemisahan tag dari ciphertext standard Java JCE
        val tagOffset = cipherWithTag.size - (GCM_TAG_LENGTH_BITS / 8)
        val ciphertext = cipherWithTag.copyOfRange(0, tagOffset)
        val tag = cipherWithTag.copyOfRange(tagOffset, cipherWithTag.size)

        return EncryptedPayload(ciphertext = ciphertext, iv = iv, authenticationTag = tag)
    }

    actual fun decrypt(payload: EncryptedPayload): ByteArray {
        val cipher = Cipher.getInstance(AES_GCM_NO_PADDING)
        val spec = GCMParameterSpec(GCM_TAG_LENGTH_BITS, payload.iv)
        cipher.init(Cipher.DECRYPT_MODE, keySpec, spec)

        val combined = payload.ciphertext + payload.authenticationTag
        return cipher.doFinal(combined)
    }
}
```

### 4. Implementasi Target iOS (`iosMain/PlatformCrypto.kt`)

```kotlin
package com.enterprise.crypto

import kotlinx.cinterop.*
import platform.CoreCrypto.*
import platform.Security.SecRandomCopyBytes
import platform.Security.kSecRandomDefault
import platform.posix.size_t

@OptIn(ExperimentalForeignApi::class)
actual class PlatformAESEncryptor actual constructor(secretKeyBytes: ByteArray) {
    private val key = secretKeyBytes.copyOf()

    private companion object {
        const val IV_LENGTH_BYTES = 12
        const val TAG_LENGTH_BYTES = 16
    }

    actual fun encrypt(plaintext: ByteArray): EncryptedPayload {
        val iv = ByteArray(IV_LENGTH_BYTES)
        val randomStatus = iv.usePinned { pinnedIv ->
            SecRandomCopyBytes(kSecRandomDefault, IV_LENGTH_BYTES.convert(), pinnedIv.addressOf(0))
        }
        check(randomStatus == 0) { "SecRandomCopyBytes gagal menghasilkan IV yang aman: $randomStatus" }

        val ciphertext = ByteArray(plaintext.size)
        val tag = ByteArray(TAG_LENGTH_BYTES)

        memScoped {
            val keyPtr = key.refTo(0).getPointer(this)
            val ivPtr = iv.refTo(0).getPointer(this)
            val plainPtr = if (plaintext.isNotEmpty()) plaintext.refTo(0).getPointer(this) else null
            val cipherPtr = if (ciphertext.isNotEmpty()) ciphertext.refTo(0).getPointer(this) else null
            val tagPtr = tag.refTo(0).getPointer(this)

            val status = CCCryptorGCM(
                kCCEncrypt,
                kCCAlgorithmAES,
                keyPtr,
                key.size.convert<size_t>(),
                ivPtr,
                iv.size.convert<size_t>(),
                null,
                0.convert<size_t>(),
                plainPtr,
                plaintext.size.convert<size_t>(),
                cipherPtr,
                tagPtr,
                TAG_LENGTH_BYTES.convert<size_t>()
            )

            check(status == kCCSuccess) { "Kompilasi CCCryptorGCM Enkripsi Gagal dengan status: $status" }
        }

        return EncryptedPayload(ciphertext, iv, tag)
    }

    actual fun decrypt(payload: EncryptedPayload): ByteArray {
        val plaintext = ByteArray(payload.ciphertext.size)

        memScoped {
            val keyPtr = key.refTo(0).getPointer(this)
            val ivPtr = payload.iv.refTo(0).getPointer(this)
            val cipherPtr = if (payload.ciphertext.isNotEmpty()) payload.ciphertext.refTo(0).getPointer(this) else null
            val tagPtr = payload.authenticationTag.refTo(0).getPointer(this)
            val plainPtr = if (plaintext.isNotEmpty()) plaintext.refTo(0).getPointer(this) else null

            // CCCryptorGCMOneshot / CCCryptorGCM (kCCDecrypt)
            val status = CCCryptorGCM(
                kCCDecrypt,
                kCCAlgorithmAES,
                keyPtr,
                key.size.convert<size_t>(),
                ivPtr,
                payload.iv.size.convert<size_t>(),
                null,
                0.convert<size_t>(),
                cipherPtr,
                payload.ciphertext.size.convert<size_t>(),
                plainPtr,
                tagPtr,
                payload.authenticationTag.size.convert<size_t>()
            )

            check(status == kCCSuccess) { "Kompilasi CCCryptorGCM Dekripsi Gagal atau Mac GCM mismatch: $status" }
        }

        return plaintext
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `build.gradle.kts`
*   **Baris 7–11 (`jvm { ... }`):** Mendefinisikan target kompilasi JVM. K2 akan menggunakan *FIR-to-JVM Bytecode Backend* untuk menghasilkan file `.class` dengan metadata Kotlin 2.0.
*   **Baris 19–27 (`listOf(iosArm64(), ...)`):** Mendefinisikan platform hardware iOS aktual (A-series/M-series Apple Silicon untuk device, dan Apple Silicon Simulator). Kompilator mengarahkan output ke pipeline LLVM native.
*   **Baris 24 (`isStatic = true`):** Menginstruksikan linker untuk menghasilkan static framework, menghindari overhead dynamic library loading pada iOS runtime.
*   **Baris 38–45 (`Hierarchical Source Sets`):** Membuat `jvmAndAndroidMain` sebagai intermediate source set. Fitur ini memungkinkan kode dibagi langsung antara JVM desktop/server dan Android SDK tanpa duplikasi implementasi.

### Analisis File `commonMain/PlatformCrypto.kt`
*   **Baris 6–26 (`data class EncryptedPayload`):** Tipe data murni tanpa dependensi native. Karena array di Kotlin mengecek kesamaan referensi secara default pada `equals()`, metode `equals()` dan `hashCode()` di-override menggunakan `.contentEquals()` dan `.contentHashCode()` untuk mencegah kegagalan verifikasi integritas data struktural.
*   **Baris 31 (`expect class PlatformAESEncryptor`):** Menginstruksikan K2 Frontend bahwa simbol `com.enterprise.crypto.PlatformAESEncryptor` adalah kontrak kompilasi statis. Simbol ini tidak memiliki implementasi pada tahap `commonMain` dan wajib dipenuhi oleh semua daun (*leaves*) dari hierarki target source set.

### Analisis File `jvmMain/PlatformCrypto.kt`
*   **Baris 8 (`actual class PlatformAESEncryptor`):** Implementasi nyata pada target JVM. Kompiler mencocokkan ini dengan deklarasi `expect`.
*   **Baris 9 (`private val keySpec = ...`):** Menggunakan Java Cryptography Architecture (JCA) langsung dari runtime JVM host (`javax.crypto`).
*   **Baris 26–33:** Mengimplementasikan ekstraksi manual tag autentikasi. JCA menyatukan Ciphertext dan Auth Tag di bagian ekor buffer output `doFinal()`, sehingga pemisahan diperlukan untuk mempertahankan kompatibilitas struktur data platform.

### Analisis File `iosMain/PlatformCrypto.kt`
*   **Baris 3–7 (`import kotlinx.cinterop.*`, `import platform.CoreCrypto.*`):** K-Native C-Interop Bridge. K2 mengimpor deklarasi header sistem POSIX/Darwin C secara instan tanpa JNI overhead.
*   **Baris 9 (`@OptIn(ExperimentalForeignApi::class)`):** Menandai penggunaan pointer dan memori mentah native C, wajib diaktifkan pada Kotlin 2.0 untuk menjaga batas keamanan memori.
*   **Baris 20–23 (`SecRandomCopyBytes`):** Memanggil API sistem operasi iOS langsung via C-Interop untuk menghasilkan Cryptographically Secure Pseudorandom Number.
*   **Baris 29 (`memScoped { ... }`):** Blok manajemen alokasi arena memori native C. Semua variabel pointer C yang dialokasikan di dalam scope ini dijamin akan dideallokasikan dari native stack/arena segera setelah blok eksekusi keluar, mencegah kebocoran memori native OS.
*   **Baris 35–49 (`CCCryptorGCM`):** Pemanggilan fungsi native C murni dari Apple `CoreCrypto` library. `refTo(0).getPointer(this)` mengonversi array byte Kotlin yang dikunci di memori (*pinned memory*) menjadi pointer bertipe `const void*`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Bisnis & Regulasi
Sebuah konglomerat perbankan internasional membangun sistem audit transaksi dan sinkronisasi tanda tangan digital offline (*Offline-First Digital Ledger*). Sistem ini harus di-deploy ke:
1.  **Mobile Banking App:** Target iOS (SwiftUI) dan Android (Jetpack Compose).
2.  **Point of Sale (POS) Edge Hardware:** Menggunakan Linux Native ARM64.
3.  **Core Gateway Audit Engine:** Berjalan di JVM Kubernetes Cluster (Spring Boot).

### Kendala Teknis & Non-Fungsional
1.  **Zero-Tolerance Memory Leak:** Pada daemon POS Edge Linux dan iOS Mobile Client, memori tidak boleh terfragmentasi atau bocor.
2.  **Strict Thread Isolation:** Perhitungan hash transaksi harus dijalankan di thread pool terisolasi di background, membebaskan thread antarmuka grafis di platform mobile.
3.  **Deterministic Compilation:** Waktu kompilasi CI/CD pipelines lama (dengan Kompiler Kotlin 1.9) mencapai 45 menit, yang harus dipangkas hingga di bawah 15 menit menggunakan optimasi K2 Pipeline dan Cache Hierarkis.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut arsitektur implementasi nyata enterprise: Ledger Sync Manager yang mengelola queue transaksi berbasis thread-safe state machine, melakukan hashing payload, dan mengeksekusi sinkronisasi terenkripsi via platform silang.

### 1. Model Domain & State Engine (`commonMain`)

```kotlin
package com.enterprise.ledger

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Entitas Transaksi Terverifikasi.
 */
data class TransactionRecord(
    val id: String,
    val timestampUnixMs: Long,
    val amountMinorUnits: Long,
    val payloadHash: String
)

sealed interface LedgerState {
    data object Idle : LedgerState
    data object Processing : LedgerState
    data class Synced(val count: Int) : LedgerState
    data class Error(val reason: String) : LedgerState
}

/**
 * Hash Engine Interface, menggantikan ketergantungan murni expect-actual dengan
 * inversion of control berbasis dependency injection.
 */
interface CryptoHasher {
    fun sha256(data: ByteArray): String
}

/**
 * Platform Network Transport Adapter.
 */
interface NetworkTransport {
    suspend fun transmit(records: List<TransactionRecord>): Boolean
}

/**
 * Enterprise Production Ledger Manager.
 */
class EnterpriseLedgerManager(
    private val hasher: CryptoHasher,
    private val transport: NetworkTransport,
    private val dispatcher: CoroutineDispatcher = Dispatchers.Default
) {
    private val _state = MutableStateFlow<LedgerState>(LedgerState.Idle)
    val state: StateFlow<LedgerState> = _state.asStateFlow()

    private val queue = mutableListOf<TransactionRecord>()
    private val mutex = Mutex()
    private val scope = CoroutineScope(dispatcher + SupervisorJob())

    suspend fun submitTransaction(id: String, timestamp: Long, amount: Long, payload: ByteArray) {
        withContext(dispatcher) {
            val hash = hasher.sha256(payload)
            val record = TransactionRecord(
                id = id,
                timestampUnixMs = timestamp,
                amountMinorUnits = amount,
                payloadHash = hash
            )
            
            mutex.withLock {
                queue.add(record)
            }
        }
    }

    fun triggerSynchronization() {
        scope.launch {
            mutex.withLock {
                if (queue.isEmpty()) return@launch
                _state.value = LedgerState.Processing

                val snapshot = queue.toList()
                try {
                    val success = transport.transmit(snapshot)
                    if (success) {
                        queue.clear()
                        _state.value = LedgerState.Synced(snapshot.size)
                    } else {
                        _state.value = LedgerState.Error("Transport rejected batch payload")
                    }
                } catch (e: Exception) {
                    _state.value = LedgerState.Error(e.message ?: "Unknown Transmit Error")
                }
            }
        }
    }

    fun shutdown() {
        scope.cancel()
    }
}
```

### 2. Implementasi High-Performance Hasher pada JVM (`jvmMain`)

```kotlin
package com.enterprise.ledger

import java.security.MessageDigest

class JvmCryptoHasher : CryptoHasher {
    override fun sha256(data: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val hashBytes = digest.digest(data)
        return hashBytes.joinToString("") { "%02x".format(it) }
    }
}
```

### 3. Implementasi Zero-Allocation Hasher pada Apple/POSIX Native (`iosMain`)

```kotlin
package com.enterprise.ledger

import kotlinx.cinterop.*
import platform.CoreCrypto.CC_SHA256
import platform.CoreCrypto.CC_SHA256_DIGEST_LENGTH

@OptIn(ExperimentalForeignApi::class)
class AppleNativeCryptoHasher : CryptoHasher {
    override fun sha256(data: ByteArray): String {
        val digest = ByteArray(CC_SHA256_DIGEST_LENGTH)
        
        digest.usePinned { pinnedDigest ->
            if (data.isEmpty()) {
                CC_SHA256(null, 0u, pinnedDigest.addressOf(0).reinterpret())
            } else {
                data.usePinned { pinnedData ->
                    CC_SHA256(
                        pinnedData.addressOf(0),
                        data.size.convert(),
                        pinnedDigest.addressOf(0).reinterpret()
                    )
                }
            }
        }

        // Fast hexadecimal formatting tanpa memicu heavy string allocations
        val chars = CharArray(CC_SHA256_DIGEST_LENGTH * 2)
        val hexArray = "0123456789abcdef".toCharArray()
        for (i in 0 until CC_SHA256_DIGEST_LENGTH) {
            val v = digest[i].toInt() and 0xFF
            chars[i * 2] = hexArray[v ushr 4]
            chars[i * 2 + 1] = hexArray[v and 0x0F]
        }
        return chars.concatToString()
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Pola `expect`/`actual` vs Dependency Injection (Interfaces)

| Karakteristik | `expect` / `actual` Language Feature | Interface Abstraction + Dependency Injection |
| :--- | :--- | :--- |
| **Resolusi Binding** | Kompilasi statis (Waktu kompilasi via K2). | Dinamis (Waktu eksekusi via implementasi class). |
| **Overhead Runtime** | **Nol overhead.** Resolusi langsung pada target assembly/bytecode. | Sedikit overhead: virtual call table dispatch (`invokeinterface`). |
| **Kemudahan Testing** | Sulit di-mock di unit test `commonTest` jika dideklarasikan pada level global. | Sangat mudah di-mock menggunakan mock framework (MockK, dsb). |
| **Struktur API** | Terikat erat pada struktur fisik platform silang. | Arsitektur fleksibel, memenuhi kaidah Dependency Inversion Principle. |
| **Rekomendasi Pemakaian** | Utilitas hardware inti, logging sistem, format floating-point. | Bisnis logic, Network layer, Repository, Database. |

### 2. Perbandingan Model KMP vs Pendekatan Kompetitor

| Kriteria Analisis | Kotlin Multiplatform (K2) | Flutter (Dart VM) | React Native (Hermes Engine) |
| :--- | :--- | :--- | :--- |
| **Arsitektur Rendering** | Native Asli (SwiftUI / Jetpack Compose). | Kanvas kustom (Impeller Engine). | Native Views dimediasi Fabric/JSI Bridge. |
| **Interop Overhead** | **Nol ke JVM, Direct C/Obj-C call di Native.** | C-Interop kompleks via FFI; isolasi thread engine. | Overhead serialisasi serialization via JSI boundary. |
| **Ukuran Binary Overhead** | Minimal (~500KB - 2MB overhead runtime KMP). | Besar (+15MB - 30MB base rendering engine bundle). | Sedang (+5MB - 10MB Hermes JS Engine). |
| **Akses Fitur OS Terbaru** | Langsung (Day 0 via C-Interop / Native Binding). | Tergantung pembaruan wrapper plugin dari Google/komunitas. | Tergantung bridging library pihak ketiga. |
| **Adopsi Parsial** | Sangat Mudah (Hanya sharing 1 class modul logic). | Sulit (Model "All-or-Nothing" untuk rendering UI). | Moderat (Membutuhkan integrasi container root view). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Swift/Objective-C Name Mangling pada Kotlin Coroutines
Fungsi `suspend` di Kotlin diekspor ke iOS Objective-C header sebagai fungsi dengan *completion handlers*:
```kotlin
// commonMain
suspend fun fetchTransaction(id: String): TransactionRecord
```
diterjemahkan di Swift menjadi:
```swift
func fetchTransaction(id: String, completionHandler: @escaping (TransactionRecord?, Error?) -> Void)
```
*Pitfall:* Di Swift 5.5+ yang memiliki `async/await`, Swift compiler mencoba menjembatani ini secara otomatis. Namun, pembatalan (*cancellation*) dari Swift Task **tidak** dipropagasikan ke Kotlin `Job` tree secara default.
*Solusi:* Wajib menggunakan wrapper interop seperti library `SKIE` yang menghasilkan Swift Concurrency bindings asli dengan *two-way task cancellation propagation*.

### 2. Exception Handling Across Binary Boundaries
Pengecualian (*Exceptions*) yang tidak tertangkap (*uncaught*) di shared Kotlin Native code tidak dapat ditangkap oleh Swift `do-catch` biasa kecuali diberi anotasi secara eksplisit:
```kotlin
// ERROR RUNTIME KETIKA DILEMANG DARI SWIFT:
fun executeCriticalOperation() {
    throw NetworkException("Connection Lost")
}
```
*Dampak:* Aplikasi iOS akan langsung **CRASH (Fatal SIGABRT)** tanpa memicu blok `catch` Swift.
*Mitigasi:* Wajib menyematkan `@Throws(NetworkException::class)` pada semua public API yang dipanggil dari Swift:
```kotlin
@Throws(NetworkException::class)
fun executeCriticalOperation() {
    throw NetworkException("Connection Lost")
}
```

### 3. Penggunaan Global Variables pada Native Singletons
Di era arsitektur Kotlin Native Legacy, variabel global berada dalam status `frozen` permanen. Pada K2 Memory Manager modern, variabel tingkat atas (`top-level state`) bersifat mutabel secara global lintas thread. 
*Pitfall:* Mengakses `var` global dari banyak thread native tanpa mekanisme `AtomicReference` atau Coroutine Synchronization (`Mutex`) dapat memicu kerusakan memori race-condition yang tidak terdeteksi oleh kompilator.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Menggunakan `expect`/`actual` untuk Membungkus Bisnis Logic

```kotlin
// ❌ ANTI-PATTERN: Menggunakan expect/actual untuk membedakan algoritma bisnis
expect class TaxCalculator {
    fun calculateVat(amount: Double): Double
}

// jvmMain
actual class TaxCalculator {
    actual fun calculateVat(amount: Double): Double = amount * 0.11
}

// iosMain
actual class TaxCalculator {
    actual fun calculateVat(amount: Double): Double = amount * 0.11
}
```
**Perbaikan:** Tempatkan logika bisnis di `commonMain`. Platform spesifik hanya ditujukan untuk hardware binding atau platform-native dependencies.
```kotlin
// ✅ REFACTOR IDIOMATIK: Murni di commonMain
class TaxCalculator(private val vatPercentage: Double = 0.11) {
    fun calculateVat(amount: Double): Double = amount * vatPercentage
}
```

### Anti-Pattern 2: Kebocoran Tipe Platform ke dalam Common Interface

```kotlin
// ❌ ANTI-PATTERN: Mengekspos tipe platform JDK atau Darwin ke commonMain
expect class DeviceInfoProvider {
    fun getLaunchIntent(): java.awt.Intent // Error pada iOS
}
```
**Perbaikan:** Lakukan pemurnian abstraksi tipe data murni Kotlin tanpa dependensi framework platform pada deklarasi `expect`.
```kotlin
// ✅ IDIOMATIK: Gunakan tipe data murni Kotlin
data class AppIntentDescriptor(val action: String, val targetPackage: String)

expect class DeviceInfoProvider {
    fun getLaunchIntent(): AppIntentDescriptor
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### 1. Modularisasi API Surface Multiplatform
Batasi visibilitas kode yang terekspos ke platform eksternal (iOS/Swift). Jangan biarkan semua file internal bertipe `public`. Gunakan modifier visibilitas `internal` untuk class pembantu KMP, dan gunakan anotasi `@HiddenFromObjC` untuk mencegah linker native mengekspor simbol internal ke Objective-C Header (`.h`), yang meminimalkan overhead binary footprint dan konflik simbol.

```kotlin
import kotlin.native.HiddenFromObjC

@HiddenFromObjC
class InternalPipelineCoordinator {
    // Tidak akan dikompilasi ke dalam framework header iOS
}
```

### 2. Standar Konfigurasi Gradle K2 Modern (Gradle 8.5+, Kotlin 2.0+)
Pastikan flags berikut diatur pada `gradle.properties` untuk memanfaatkan K2 engine secara maksimal:

```properties
# Mengaktifkan daemon kompilator paralel
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configuration-cache=true

# Memaksa penggunaan K2 Compiler
kotlin.experimental.tryK2=false # Kotlin 2.0 menggunakan K2 secara default

# Caching dan Optimasi Kotlin/Native
kotlin.native.enableKlibsCrossCompilation=true
kotlin.native.cacheKind=none
```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Link-Time Optimization (LTO) & Binary Size Reduction
Secara default, proses kompilasi debug pada iOS menghasilkan binary framework berukuran besar karena menyertakan metadata DWARF debug info lengkap. Untuk release produksi pada pipeline CI/CD:

```kotlin
// build.gradle.kts
kotlin {
    targets.withType<org.jetbrains.kotlin.gradle.plugin.mpp.KotlinNativeTarget> {
        binaries.withType<org.jetbrains.kotlin.gradle.plugin.mpp.Framework> {
            if (buildType == org.jetbrains.kotlin.gradle.plugin.mpp.NativeBuildType.RELEASE) {
                // Aktifkan optimasi LTO bitcode LLVM
                freeCompilerArgs += listOf(
                    "-opt",                 // Optimasi level -O3 pada LLVM backend
                    "-Xdisable-phases=DevirtualizationAnalysis", // Bypass analitik berlebih
                    "-Xbinary=bundleId=com.enterprise.app"
                )
            }
        }
    }
}
```

### 2. Penanganan Memory Allocator pada Kotlin Native
Mulai Kotlin 2.0, allocator default untuk Apple targets adalah **mimalloc** (alokator performa tinggi dari Microsoft). Jangan pernah mengubah alokator kembali ke standar `sys_alloc` kecuali menghadapi platform embedded mikro tertentu, karena `mimalloc` mengurangi lock-contention pada multi-threaded concurrency secara signifikan.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Zero-Memory Residual Data Hardening
Saat memproses kata sandi, Private Key, atau data identitas sensitif di dalam shared KMP code, garbage collection cycle (baik di JVM maupun di Native Tracing GC) tidak menjamin kapan memory buffer dibersihkan. Memory dump attack dapat membaca plain secret jika data dibiarkan mengapung di heap.

```kotlin
package com.enterprise.security

import kotlin.contracts.ExperimentalContracts
import kotlin.contracts.InvocationKind
import kotlin.contracts.contract

/**
 * Struktur memory wrapper aman untuk data rahasia platform silang.
 */
class EphemeralSecret(private val payload: ByteArray) {
    private var destroyed = false

    @OptIn(ExperimentalContracts::class)
    inline fun <R> use(block: (ByteArray) -> R): R {
        contract {
            callsInPlace(block, InvocationKind.EXACTLY_ONCE)
        }
        check(!destroyed) { "Secret data telah dimusnahkan dari memori" }
        return try {
            block(payload)
        } finally {
            destroy()
        }
    }

    fun destroy() {
        if (!destroyed) {
            // Memory zeroing
            payload.fill(0.toByte())
            destroyed = true
        }
    }
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Debugging platform silang sering kali terhambat akibat crash stacktrace pada iOS Native yang hilang/mengarah ke assembly memory address tanpa informasi baris kode Kotlin.

### Konfigurasi Symbolication Stacktrace (iOS Darwin)
Untuk memulihkan deobfuscated Kotlin stacktrace dari Apple `.crash` logs, kompilator harus menghasilkan file symbol pendamping (`.dSYM`). Pastikan konfigurasi kompilasi mengaktifkan embedding dSYM:

```kotlin
kotlin {
    listOf(iosArm64(), iosSimulatorArm64()).forEach {
        it.binaries.framework {
            baseName = "SharedCore"
            embedBitcode = "disable"
            // Pastikan dSYM selalu diekspor pada release build
            freeCompilerArgs += listOf("-g")
        }
    }
}
```

### Unified Multiplatform Logger Engine Architecture

```kotlin
package com.enterprise.logging

enum class LogLevel { DEBUG, INFO, WARN, ERROR }

expect object PlatformLogger {
    fun writeLog(level: LogLevel, tag: String, message: String, throwable: Throwable? = null)
}

// JVM Implementation: Slf4j / Logback Bridge
// jvmMain
actual object PlatformLogger {
    actual fun writeLog(level: LogLevel, tag: String, message: String, throwable: Throwable?) {
        val out = "[$tag] - $message ${throwable?.stackTraceToString() ?: ""}"
        when (level) {
            LogLevel.DEBUG -> println("[DEBUG] $out")
            LogLevel.INFO -> println("[INFO] $out")
            LogLevel.WARN -> System.err.println("[WARN] $out")
            LogLevel.ERROR -> System.err.println("[ERROR] $out")
        }
    }
}

// iOS Native Implementation: Unified Logging System (os_log)
// iosMain
import platform.darwin.OS_LOG_TYPE_DEBUG
import platform.darwin.OS_LOG_TYPE_DEFAULT
import platform.darwin.OS_LOG_TYPE_ERROR
import platform.darwin.OS_LOG_TYPE_FAULT
import platform.darwin.__os_log_simple
import platform.darwin.os_log_create

actual object PlatformLogger {
    private val osLog = os_log_create("com.enterprise.app", "NativeCore")

    actual fun writeLog(level: LogLevel, tag: String, message: String, throwable: Throwable?) {
        val logType = when(level) {
            LogLevel.DEBUG -> OS_LOG_TYPE_DEBUG
            LogLevel.INFO -> OS_LOG_TYPE_DEFAULT
            LogLevel.WARN -> OS_LOG_TYPE_ERROR
            LogLevel.ERROR -> OS_LOG_TYPE_FAULT
        }
        val composed = "[$tag] $message" + (throwable?.let { " Exception: " + it.message } ?: "")
        __os_log_simple(osLog, logType, composed)
    }
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Perbandingan Karakteristik Arsitektur K2 vs K1

| Atribut / Perilaku | Frontend 1.0 (Kotlin <= 1.9) | K2 Compiler (Kotlin >= 2.0) |
| :--- | :--- | :--- |
| **Pipeline Parsing Semantik** | BindingContext AST Lookup | FIR (Frontend Intermediate Representation) |
| **Waktu Kompilasi Modul Besar**| Baseline ($1\times$) | Hingga $2\times$ lebih cepat (Multithreading Parsing) |
| **Resolusi `expect`/`actual`** | Longgar; sering false negative | Divalidasi ketat pada fase IR Linking |
| **Smart Cast Engine** | Kaku pada complex closure scope | Flow-Sensitive Analysis penuh |
| **Konfigurasi Flag** | Default | Otomatis diaktifkan sejak Kotlin 2.0.0 |

### Gradle DSL Quick Cheatsheet

```kotlin
// Inisialisasi KMP Target Standard
kotlin {
    jvm()
    androidTarget()
    iosArm64()
    iosSimulatorArm64()
    wasmJs { browser() }
    
    sourceSets {
        commonMain.dependencies { /* Platform Agnostic Dependencies */ }
        jvmMain.dependencies { /* JVM / Java Dependencies */ }
        iosMain.dependencies { /* Darwin / C-Interop Dependencies */ }
    }
}
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa fungsi utama dari FIR (Frontend Intermediate Representation) pada arsitektur Kompiler K2?**
   * A. Menghasilkan biner LLVM langsung dari file `.kt`.
   * B. Menggantikan struktur BindingContext dengan pohon semantik bertipe parsial yang mendukung paralelisasi kompilasi.
   * C. Menerjemahkan kode Kotlin langsung menjadi kode sumber Java.
   * D. Mengeliminasi kebutuhan akan garbage collection pada runtime Kotlin/Native.
   * *Jawaban:* **B**. FIR berfungsi menggantikan representasi internal BindingContext lama, menyederhanakan pelacakan semantik tipe dan memungkinkan paralelisasi analisis file pada fase frontend kompiler.

2. **Di mana deklarasi kata kunci `expect` harus ditempatkan dalam struktur hierarki source set KMP?**
   * A. Pada target platform paling spesifik seperti `iosMain` atau `androidMain`.
   * B. Di file kompilasi eksternal Gradle `build.gradle.kts`.
   * C. Pada `commonMain` atau intermediate source set hierarkis yang lebih tinggi.
   * D. Di dalam blok kode C-interop `.def`.
   * *Jawaban:* **C**. Kata kunci `expect` berfungsi mendeklarasikan kontrak antarmuka di root source set (`commonMain`) atau modul induk, untuk kemudian dipenuhi oleh `actual` di target platform turunan.

3. **Bagaimana mekanisme resolusi kode `expect`/`actual` dieksekusi secara teknis?**
   * A. Melalui refleksi dinamis saat runtime aplikasi berjalan.
   * B. Melalui pencarian statis waktu kompilasi (*compile-time static binding*) oleh backend IR.
   * C. Melalui Objective-C Runtime dynamic message dispatching.
   * D. Menggunakan JNI invocation interface pada semua platform.
   * *Jawaban:* **B**. Kompiler K2 menyelesaikan pasangan `expect`/`actual` secara statis pada fase kompilasi/linking IR, menghasilkan pemanggilan metode langsung tanpa overhead vtable dinamis.

4. **Apa status dari memori model berbasis "Freezing" (`freeze()`) pada Kotlin/Native di era Kotlin 2.0 (K2)?**
   * A. Masih wajib dipanggil sebelum membagikan objek antar-thread.
   * B. Ditinggalkan sepenuhnya (*deprecated and removed*) dan digantikan oleh New Memory Manager dengan Tracing Concurrent GC.
   * C. Menjadi satu-satunya cara mengalokasikan memori native di iOS.
   * D. Dipindahkan ke dalam modul `kotlinx-coroutines`.
   * *Jawaban:* **B**. Model legacy freeze() telah ditinggalkan sepenuhnya. Kotlin/Native modern menggunakan tracing GC non-blocking berbasis CMS yang memungkinkan alokasi dan referensi objek bebas di seluruh thread.

5. **Artefak apa yang dihasilkan oleh kompilasi Kotlin Native library yang berisi serialisasi IR dan metadata?**
   * A. File `.jar`
   * B. File `.class`
   * C. File `.klib`
   * D. File `.so`
   * *Jawaban:* **C**. Format pustaka standar untuk Kotlin Native dan Wasm adalah `.klib` (Kotlin Library), yang mengemas metadata K2 Compiler dan representasi biner IR AST.

---

### Soal Tingkat Menengah (Intermediate)

6. **Mengapa pengecualian runtime (*uncaught exception*) pada kode Kotlin yang dieksekusi dari Swift dapat memicu crash Fatal SIGABRT meskipun dibungkus dalam blok `do-catch` Swift?**
   * A. Swift sama sekali tidak mendukung mekanisme penanganan exception.
   * B. Fungsi Kotlin tidak dianotasi dengan `@Throws`, sehingga kompiler tidak memetakan Kotlin exception menjadi pointer `NSError**` pada header Objective-C.
   * C. Memory GC Kotlin belum diaktifkan saat pemanggilan dilakukan.
   * D. Objective-C Runtime tidak mengizinkan pemanggilan fungsi suspensi.
   * *Jawaban:* **B**. Secara default, Kotlin/Native melempar uncaught exception langsung ke abort handler. Untuk menjembatani exception ke mekanisme `NSError` Swift, fungsi Kotlin wajib disematkan anotasi `@Throws`.

7. **Ditinjau dari pipeline K2 Compiler, apa peran komponen "FIR2IR"?**
   * A. Menerjemahkan biner Java Bytecode langsung ke Swift binary.
   * B. Mengonversi pohon FIR semantik yang telah tervalidasi tipe datanya menjadi Unified Backend Intermediate Representation (IR).
   * C. Mengunduh pustaka dependensi Gradle secara otomatis.
   * D. Mengurai teks kode sumber menjadi Token Lexer.
   * *Jawaban:* **B**. FIR2IR adalah jembatan transformasi antara tahap analisa semantik frontend K2 (FIR) menuju representasi perantara backend terpadu (Kotlin Backend IR).

8. **Manakah dari teknik berikut yang paling tepat untuk mengoptimasi ukuran biner framework biner Kotlin Native pada build Release iOS?**
   * A. Menggunakan `isStatic = false` pada seluruh framework.
   * B. Mengaktifkan Link-Time Optimization (LTO) via flags kompilator `-opt` dan bypass devirtualization berlebih.
   * C. Mematikan coroutines engine.
   * D. Mengompilasi seluruh source code di `iosMain` menggunakan `sys_alloc`.
   * *Jawaban:* **B**. Mengarahkan kompiler LLVM untuk menggunakan optimasi `-opt` (setara dengan -O3 LTO) melakukan dead-code elimination mendalam dan inlining assembly lintas unit kompilasi.

9. **Apa keuntungan dari Hierarchical Source Sets dibandingkan model flat platform pada konfigurasi KMP Gradle?**
   * A. Memungkinkan pembagian kode parsial (misal: antarmuka bersama khusus POSIX, atau intermediate JVM+Android) tanpa mendefinisikan ulang `expect`/`actual` redundan.
   * B. Mengurangi ukuran instalasi Gradle JDK.
   * C. Menghilangkan kebutuhan penulisan unit testing.
   * D. Memaksa arsitektur UI tunggal di semua target.
   * *Jawaban:* **A**. Hierarchical Source Sets mengizinkan pembuatan layer intermediate (seperti `appleMain`, `nativeMain`, `jvmAndAndroidMain`) sehingga kode yang kompatibel pada kelompok platform tertentu dapat dibagi secara natural.

10. **Perhatikan skenario berikut:**
    ```kotlin
    // commonMain
    expect class HardwareSecurityToken {
        fun readUid(): String
    }
    // iosMain
    actual typealias HardwareSecurityToken = MyPlatformNativeToken
    ```
    **Kapan implementasi `actual typealias` di atas valid dalam arsitektur K2?**
    * A. Hanya jika `MyPlatformNativeToken` adalah kelas Java.
    * B. Kapan saja, karena K2 mengizinkan pemenuhan deklarasi tipe `expect` menggunakan kelas konkret platform yang sudah ada selama tanda tangan fungsi cocok.
    * C. Tidak pernah diizinkan pada arsitektur K2 karena melanggar aturan ABI immutability.
    * D. Hanya jika dideklarasikan di dalam file Swift.
    * *Jawaban:* **B**. `actual typealias` adalah fitur resmi Kotlin yang valid untuk memenuhi kontrak `expect` dengan mengarahkan secara langsung ke kelas native yang telah ada pada platform SDK bersangkutan tanpa overhead wrapper.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: Cross-Platform Hardware-Backed Persistent Vault

### Spesifikasi Kebutuhan Teknis
Rancang dan bangun modul pustaka Kotlin Multiplatform mandiri dengan K2 Compiler yang mengimplementasikan sistem penyimpanan data *Key-Value* persisten yang aman dan terenkripsi:

1.  **Target Arsitektur:**
    *   `jvm`: Enkripsi file lokal menggunakan Java SecretKeyStore & AES-256 GCM.
    *   `iosArm64` / `iosSimulatorArm64`: Integrasi langsung menggunakan iOS Native Keychain Services API (`SecItemAdd`, `SecItemCopyMatching`) via C-Interop.
2.  **Struktur Modul:**
    *   Gunakan Hierarchical Source Set.
    *   Pisahkan API kontrak di `commonMain` dalam bentuk antarmuka `SecureStorageVault`.
    *   Jangan gunakan dependensi library pihak ketiga untuk kriptografi; wajib menggunakan API bawaan platform OS (JCE untuk JVM, Security.framework untuk iOS).
3.  **Kebutuhan Kode:**
    *   Gunakan fungsi thread-safe `StateFlow` atau Coroutines `Mutex` untuk mengantisipasi concurrent access dari banyak thread.
    *   Implementasikan pembersihan memori aman (*zeroing bytes*) saat proses enkripsi dan pembacaan selesai.
    *   Buat Unit Test pada `commonTest` yang menguji integritas simpan-baca-hapus data, dan jalankan perintah verifikasi:
        ```bash
        ./gradlew jvmTest iosSimulatorArm64Test --configuration-cache
        ```

### Kriteria Kelulusan Evaluasi (Checklist)
*   [ ] Proyek berhasil dikompilasi tanpa flag legacy pada Kotlin 2.0+ engine.
*   [ ] Tidak ada memory leak saat eksekusi pointer C-interop (`memScoped` atau `usePinned` digunakan secara disiplin pada implementasi iOS).
*   [ ] Test lolos 100% pada JVM Test task dan iOS Simulator ARM64 test runner.
*   [ ] File `build.gradle.kts` memanfaatkan konvensi deklarasi modern tanpa dependensi usang.